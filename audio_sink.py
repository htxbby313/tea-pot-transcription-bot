import io
import time
import wave
import asyncio
import logging
from typing import Dict, Optional, Callable, Awaitable
import discord
from discord.sinks.core import Sink

logger = logging.getLogger("AudioSink")

def pcm_to_wav(pcm_data: bytes, sample_rate: int = 48000, channels: int = 2, sample_width: int = 2) -> bytes:
    """Converts raw PCM audio bytes to standard WAV bytes in-memory."""
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    wav_io.seek(0)
    return wav_io.read()

class LiveTranscribingSink(Sink):
    """
    Custom Py-Cord Voice Sink that receives per-user audio streams in real-time,
    segments speech on pauses / chunk intervals, and dispatches them for STT transcription.
    """
    def __init__(
        self,
        on_speech_chunk: Callable[[int, bytes, float], Awaitable[None]],
        silence_timeout: float = 1.2,
        max_chunk_duration: float = 4.0,
        sample_rate: int = 48000,
        channels: int = 2,
        sample_width: int = 2
    ):
        super().__init__()
        self.on_speech_chunk = on_speech_chunk
        self.silence_timeout = silence_timeout
        self.max_chunk_duration = max_chunk_duration
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width

        # Bytes per second = 48000 * 2 channels * 2 bytes = 192,000 bytes/sec
        self.bytes_per_second = self.sample_rate * self.channels * self.sample_width
        self.min_chunk_bytes = int(self.bytes_per_second * 0.4) # Min 0.4s of audio
        self.max_chunk_bytes = int(self.bytes_per_second * self.max_chunk_duration)

        # Buffers & state per user_id
        self.buffers: Dict[int, bytearray] = {}
        self.last_audio_time: Dict[int, float] = {}
        self.chunk_start_time: Dict[int, float] = {}
        self.is_active = True
        self._monitor_task: Optional[asyncio.Task] = None

    def start_monitoring(self, loop: asyncio.AbstractEventLoop):
        """Starts the background silence detection & chunk dispatcher task."""
        self.is_active = True
        self._monitor_task = loop.create_task(self._monitor_buffers_loop())

    def stop_monitoring(self):
        """Stops the monitoring task and flushes remaining buffers."""
        self.is_active = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()

    def write(self, data: bytes, user: int):
        """Called by Py-Cord whenever a voice packet from a user arrives."""
        if not self.is_active or not data:
            return

        now = time.time()
        if user not in self.buffers:
            self.buffers[user] = bytearray()
            self.chunk_start_time[user] = now

        self.buffers[user].extend(data)
        self.last_audio_time[user] = now

    async def _monitor_buffers_loop(self):
        """Periodically checks all active speaker buffers for silence or size limits."""
        while self.is_active:
            try:
                await asyncio.sleep(0.3)
                now = time.time()
                users_to_process = list(self.buffers.keys())

                for user_id in users_to_process:
                    buf = self.buffers.get(user_id)
                    if not buf:
                        continue

                    last_time = self.last_audio_time.get(user_id, 0)
                    start_time = self.chunk_start_time.get(user_id, now)
                    silence_duration = now - last_time
                    chunk_duration = now - start_time
                    buf_len = len(buf)

                    # Trigger transcription if:
                    # 1. User paused speaking for > silence_timeout AND has spoken enough bytes
                    # 2. User has spoken continuously > max_chunk_duration
                    should_flush = False
                    if buf_len >= self.min_chunk_bytes and silence_duration >= self.silence_timeout:
                        should_flush = True
                    elif buf_len >= self.max_chunk_bytes:
                        should_flush = True

                    if should_flush:
                        audio_data = bytes(buf)
                        # Clear buffer for next chunk
                        self.buffers[user_id] = bytearray()
                        self.chunk_start_time[user_id] = now
                        
                        # Convert to WAV bytes
                        wav_bytes = pcm_to_wav(
                            audio_data,
                            sample_rate=self.sample_rate,
                            channels=self.channels,
                            sample_width=self.sample_width
                        )
                        
                        # Dispatch async task for transcription & posting
                        asyncio.create_task(self._safe_dispatch(user_id, wav_bytes, start_time))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in audio sink monitor loop: {e}", exc_info=True)

    async def _safe_dispatch(self, user_id: int, wav_bytes: bytes, timestamp: float):
        try:
            await self.on_speech_chunk(user_id, wav_bytes, timestamp)
        except Exception as e:
            logger.error(f"Error in on_speech_chunk dispatch for user {user_id}: {e}", exc_info=True)

    def cleanup(self):
        super().cleanup()
        self.stop_monitoring()
        self.buffers.clear()
