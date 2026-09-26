import os
import asyncio
import logging
from pathlib import Path
import discord
from gtts import gTTS

logger = logging.getLogger("Announcer")

ANNOUNCEMENT_TEXT = "Tea Pot Transcription is now active in this channel."
LEAVE_TEXT = "Tea Pot Transcription has ended."

AUDIO_DIR = Path(__file__).resolve().parent / "audio_assets"

def ensure_audio_files():
    """Generates the TTS alert files if they don't already exist."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    
    join_file = AUDIO_DIR / "transcription_active.mp3"
    if not join_file.exists():
        try:
            logger.info("Generating voice join announcement audio...")
            tts = gTTS(text=ANNOUNCEMENT_TEXT, lang='en', slow=False)
            tts.save(str(join_file))
        except Exception as e:
            logger.warning(f"Could not pre-generate join announcement audio: {e}")

    leave_file = AUDIO_DIR / "transcription_ended.mp3"
    if not leave_file.exists():
        try:
            tts = gTTS(text=LEAVE_TEXT, lang='en', slow=False)
            tts.save(str(leave_file))
        except Exception as e:
            logger.warning(f"Could not pre-generate leave announcement audio: {e}")

async def play_announcement(voice_client: discord.VoiceClient, announcement_type: str = "join"):
    """Plays an audible TTS alert into the voice channel to notify all participants."""
    if not voice_client or not voice_client.is_connected():
        return

    filename = "transcription_active.mp3" if announcement_type == "join" else "transcription_ended.mp3"
    audio_path = AUDIO_DIR / filename
    
    if not audio_path.exists():
        ensure_audio_files()

    if not audio_path.exists():
        logger.warning(f"Announcement audio file {audio_path} not found, skipping audio play.")
        return

    try:
        # If currently playing audio, stop
        if voice_client.is_playing():
            voice_client.stop()

        source = discord.FFmpegPCMAudio(str(audio_path))
        voice_client.play(source)

        # Wait until finished playing (short clip ~2-3 seconds)
        while voice_client.is_playing():
            await asyncio.sleep(0.2)

    except Exception as e:
        logger.error(f"Error playing voice announcement: {e}")
