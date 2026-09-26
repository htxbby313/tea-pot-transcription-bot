import io
import time
import datetime
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import discord
import config
from audio_sink import LiveTranscribingSink
from transcriber import BaseTranscriber
from announcer import play_announcement
from tier_manager import tier_mgr


logger = logging.getLogger("SessionManager")

@dataclass
class TranscriptEntry:
    timestamp: float
    user_id: int
    user_name: str
    text: str

    @property
    def formatted_time(self) -> str:
        dt = datetime.datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%H:%M:%S")

class VoiceSession:
    """Manages an active recording and transcribing session for a single Discord guild/VC."""
    def __init__(
        self,
        guild: discord.Guild,
        voice_channel: discord.VoiceChannel,
        transcript_channel: discord.TextChannel,
        thread: discord.Thread,
        voice_client: discord.VoiceClient,
        transcriber: BaseTranscriber,
        summoner: discord.Member
    ):
        self.guild = guild
        self.voice_channel = voice_channel
        self.transcript_channel = transcript_channel
        self.thread = thread
        self.voice_client = voice_client
        self.transcriber = transcriber
        self.summoner = summoner
        
        self.start_time = time.time()
        self.entries: List[TranscriptEntry] = []
        self.sink: Optional[LiveTranscribingSink] = None
        self.is_paused = False
        self.speaker_counts: Dict[str, int] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._queue_worker_task: Optional[asyncio.Task] = None

    async def start(self):
        """Initializes the session, plays announcement, and starts audio recording."""
        # 1. Start posting queue worker
        self._queue_worker_task = asyncio.create_task(self._transcript_posting_loop())

        # 2. Play audio announcement into VC if enabled
        if config.PLAY_VOICE_ANNOUNCEMENT:
            try:
                await play_announcement(self.voice_client, "join")
            except Exception as e:
                logger.error(f"Failed to play join announcement: {e}")

        # 3. Create and attach LiveTranscribingSink
        self.sink = LiveTranscribingSink(
            on_speech_chunk=self.handle_speech_chunk,
            silence_timeout=config.SILENCE_TIMEOUT_SECONDS,
            max_chunk_duration=config.CHUNK_DURATION_SECONDS
        )

        # Py-Cord start_recording
        def on_recording_finished(sink, *args):
            logger.info(f"Recording finished for VC: {self.voice_channel.name}")

        self.voice_client.start_recording(self.sink, on_recording_finished)
        self.sink.start_monitoring(asyncio.get_event_loop())
        logger.info(f"Started live transcription for {self.guild.name} -> #{self.voice_channel.name}")

    async def handle_speech_chunk(self, user_id: int, wav_bytes: bytes, timestamp: float):
        """Called when a user finishes speaking a chunk of audio."""
        if self.is_paused:
            return

        # Resolve username
        member = self.guild.get_member(user_id)
        user_name = member.display_name if member else f"User_{user_id}"

        # Transcribe with Cloud API
        text = await self.transcriber.transcribe_audio(wav_bytes)
        if not text or len(text.strip()) == 0:
            return

        # Filter out common hallucinated filler from silent audio
        cleaned_text = text.strip()
        if cleaned_text.lower() in ("you", "thank you", "bye", "thanks for watching", ".", "..", "...", "subtitles by", "amara.org"):
            return

        entry = TranscriptEntry(
            timestamp=timestamp,
            user_id=user_id,
            user_name=user_name,
            text=cleaned_text
        )
        self.entries.append(entry)
        self.speaker_counts[user_name] = self.speaker_counts.get(user_name, 0) + 1

        # Queue for Discord thread posting
        await self._message_queue.put(entry)

    async def _transcript_posting_loop(self):
        """Worker that posts transcribed entries to the dedicated thread with rate-limit protection."""
        while True:
            try:
                entry = await self._message_queue.get()
                
                # Format: 🕒 `12:34:56` | 🗣️ **Alice**: "Hello everyone"
                msg_content = f"🕒 `{entry.formatted_time}` | 🗣️ **{entry.user_name}**: {entry.text}"
                
                try:
                    await self.thread.send(msg_content)
                except discord.HTTPException as e:
                    logger.error(f"Failed to send transcript to thread: {e}")
                
                # Small delay to respect Discord thread message rate limits
                await asyncio.sleep(0.3)
                self._message_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in transcript posting loop: {e}", exc_info=True)

    async def stop(self) -> str:
        """Stops the transcription, disconnects voice, generates summary file, and archives thread."""
        logger.info(f"Stopping session for {self.guild.name} -> #{self.voice_channel.name}")
        
        # 1. Stop audio sink
        if self.sink:
            self.sink.stop_monitoring()

        # 2. Stop recording if still active
        if self.voice_client.recording:
            try:
                self.voice_client.stop_recording()
            except Exception as e:
                logger.warning(f"Error stopping recording: {e}")

        # 3. Play leave announcement if connected
        if config.PLAY_VOICE_ANNOUNCEMENT and self.voice_client.is_connected():
            try:
                await play_announcement(self.voice_client, "leave")
            except Exception as e:
                logger.warning(f"Failed to play leave announcement: {e}")

        # 4. Disconnect from VC
        if self.voice_client.is_connected():
            try:
                await self.voice_client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting from VC: {e}")

        # 5. Flush queue & cancel worker
        if self._queue_worker_task:
            self._queue_worker_task.cancel()

        # 6. Generate final summary report & file
        duration_sec = int(time.time() - self.start_time)
        mins, secs = divmod(duration_sec, 60)
        hours, mins = divmod(mins, 60)
        duration_str = f"{hours}h {mins}m {secs}s" if hours > 0 else f"{mins}m {secs}s"

        full_transcript_text = self.generate_transcript_file_content(duration_str)

        # Send session recap embed to thread
        embed = discord.Embed(
            title="🫖 Tea Pot Transcription — Session Ended",
            description=f"Voice channel session in **#{self.voice_channel.name}** has completed.",
            color=0xED4245,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="⏱️ Total Duration", value=duration_str, inline=True)
        embed.add_field(name="💬 Total Lines Transcribed", value=str(len(self.entries)), inline=True)
        embed.add_field(name="👥 Active Speakers", value=str(len(self.speaker_counts)), inline=True)

        if self.speaker_counts:
            speaker_summary = "\n".join([f"• **{name}**: {count} lines" for name, count in sorted(self.speaker_counts.items(), key=lambda x: x[1], reverse=True)])
            embed.add_field(name="📊 Speaker Participation", value=speaker_summary[:1024], inline=False)

        # Check if server tier permits file downloads
        can_download = tier_mgr.can_download(self.guild.id)
        g_settings = tier_mgr.get_guild_settings(self.guild.id)
        tier_name = g_settings.get("tier", "free").capitalize()
        retention_hours = g_settings.get("retention_hours", 24)
        retention_text = f"{retention_hours} Hours" if retention_hours > 0 else "Indefinite / Permanent"

        embed.add_field(name="🫖 Server Tier", value=f"{tier_name} Tier", inline=True)
        embed.add_field(name="⏱️ Retention", value=retention_text, inline=True)

        if not can_download:
            embed.add_field(
                name="⬇️ Meeting File Export",
                value="*File downloads (.txt/.md) and permanent archives are available on Pro & Premium tiers. Transcripts remain viewable in this thread during the retention window.*",
                inline=False
            )

        # Upload transcript file to thread if permitted
        try:
            if can_download:
                file_buffer = io.BytesIO(full_transcript_text.encode("utf-8"))
                filename = f"TeaPot_Transcript_{self.voice_channel.name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                discord_file = discord.File(file_buffer, filename=filename)
                await self.thread.send(embed=embed, file=discord_file)
            else:
                await self.thread.send(embed=embed)
            
            # Archive thread to keep channel clean
            await self.thread.edit(archived=True, locked=False)
        except Exception as e:
            logger.error(f"Failed to send end embed/file: {e}")

        return duration_str


    def generate_transcript_file_content(self, duration_str: str) -> str:
        """Builds a clean, readable text document of the entire transcription."""
        lines = [
            "=" * 60,
            f"TEA POT TRANSCRIPTION BOT — MEETING TRANSCRIPT",
            "=" * 60,
            f"Server:        {self.guild.name} (ID: {self.guild.id})",
            f"Voice Channel: #{self.voice_channel.name}",
            f"Session Start: {datetime.datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Duration: {duration_str}",
            f"Summoned By:   {self.summoner.display_name} ({self.summoner.name})",
            f"STT Provider:  {config.STT_PROVIDER.upper()}",
            "=" * 60,
            "\nPARTICIPANTS & LINE COUNTS:",
        ]
        for name, count in self.speaker_counts.items():
            lines.append(f" - {name}: {count} lines")

        lines.append("\n" + "=" * 60)
        lines.append("TRANSCRIPT LOG:")
        lines.append("=" * 60 + "\n")

        if not self.entries:
            lines.append("(No speech was detected during this session)")
        else:
            for entry in self.entries:
                lines.append(f"[{entry.formatted_time}] {entry.user_name}: {entry.text}")

        lines.append("\n" + "=" * 60)
        lines.append("End of Transcript — Powered by Tea Pot Transcription Bot")
        lines.append("=" * 60)
        return "\n".join(lines)


class SessionManager:
    """Registry of active sessions across all guilds."""
    def __init__(self, transcriber: BaseTranscriber):
        self.transcriber = transcriber
        self.active_sessions: Dict[int, VoiceSession] = {} # guild_id -> VoiceSession

    def get_session(self, guild_id: int) -> Optional[VoiceSession]:
        return self.active_sessions.get(guild_id)

    async def create_session(
        self,
        guild: discord.Guild,
        voice_channel: discord.VoiceChannel,
        transcript_channel: discord.TextChannel,
        voice_client: discord.VoiceClient,
        summoner: discord.Member
    ) -> VoiceSession:
        # If an existing session exists, stop it first
        if guild.id in self.active_sessions:
            await self.stop_session(guild.id)

        # Create new dedicated thread in transcript channel
        timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        thread_name = f"🫖 [{timestamp_str}] {voice_channel.name}"
        
        thread = await transcript_channel.create_thread(
            name=thread_name[:100],
            type=discord.ChannelType.public_thread,
            reason=f"Tea Pot Live Voice Transcript for #{voice_channel.name}"
        )

        # Send initial banner embed
        embed = discord.Embed(
            title="🫖 Tea Pot Transcription — Session Active",
            description=(
                f"Now transcribing spoken audio from **#{voice_channel.name}** in real-time.\n"
                f"Transcripts will appear below as members speak."
            ),
            color=0x5865F2,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        # Server tier & retention info
        g_settings = tier_mgr.get_guild_settings(guild.id)
        tier_name = g_settings.get("tier", "free").capitalize()
        retention_hours = g_settings.get("retention_hours", 24)
        retention_text = f"{retention_hours} Hours (Auto-Purge)" if retention_hours > 0 else "Indefinite Archive"

        embed.add_field(name="🫖 Server Tier", value=f"{tier_name} Tier", inline=True)
        embed.add_field(name="⏱️ Retention", value=retention_text, inline=True)
        embed.set_footer(text="Transparency Notice: Audio in this voice channel is being transcribed by Tea Pot.")
        
        await thread.send(embed=embed)

        # Register thread for retention lifecycle management
        tier_mgr.register_thread(guild.id, thread.id)



        session = VoiceSession(
            guild=guild,
            voice_channel=voice_channel,
            transcript_channel=transcript_channel,
            thread=thread,
            voice_client=voice_client,
            transcriber=self.transcriber,
            summoner=summoner
        )
        await session.start()
        self.active_sessions[guild.id] = session
        return session

    async def stop_session(self, guild_id: int) -> Optional[VoiceSession]:
        session = self.active_sessions.pop(guild_id, None)
        if session:
            await session.stop()
        return session
