import io
import logging
import aiohttp
from openai import AsyncOpenAI
import config

logger = logging.getLogger("Transcriber")

class BaseTranscriber:
    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        raise NotImplementedError

class OpenAITranscriber(BaseTranscriber):
    def __init__(self, api_key: str, model: str = "whisper-1", language: str = "en"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.language = language

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        if not audio_bytes or len(audio_bytes) < 1000:
            return ""
        try:
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = filename
            
            # Request verbatim transcription with punctuation
            kwargs = {
                "model": self.model,
                "file": audio_file,
                "response_format": "text"
            }
            if self.language and self.language != "auto":
                kwargs["language"] = self.language

            response = await self.client.audio.transcriptions.create(**kwargs)
            
            # Response is string if response_format="text"
            if isinstance(response, str):
                return response.strip()
            elif hasattr(response, "text"):
                return response.text.strip()
            return str(response).strip()
        except Exception as e:
            logger.error(f"OpenAI Whisper transcription error: {e}")
            return ""

class DeepgramTranscriber(BaseTranscriber):
    def __init__(self, api_key: str, model: str = "nova-2", language: str = "en"):
        self.api_key = api_key
        self.model = model
        self.language = language
        self.url = f"https://api.deepgram.com/v1/listen?model={self.model}&smart_format=true&punctuate=true"
        if self.language and self.language != "auto":
            self.url += f"&language={self.language}"

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        if not audio_bytes or len(audio_bytes) < 1000:
            return ""
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, data=audio_bytes, headers=headers) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        logger.error(f"Deepgram error {resp.status}: {err_text}")
                        return ""
                    data = await resp.json()
                    channels = data.get("results", {}).get("channels", [])
                    if channels and len(channels) > 0:
                        alternatives = channels[0].get("alternatives", [])
                        if alternatives and len(alternatives) > 0:
                            transcript = alternatives[0].get("transcript", "")
                            return transcript.strip()
            return ""
        except Exception as e:
            logger.error(f"Deepgram transcription error: {e}")
            return ""

def get_transcriber() -> BaseTranscriber:
    provider = config.STT_PROVIDER
    if provider == "deepgram":
        if not config.DEEPGRAM_API_KEY:
            raise ValueError("DEEPGRAM_API_KEY is not set in configuration")
        logger.info(f"Using Deepgram Transcriber (model: {config.DEEPGRAM_MODEL})")
        return DeepgramTranscriber(
            api_key=config.DEEPGRAM_API_KEY,
            model=config.DEEPGRAM_MODEL,
            language=config.LANGUAGE
        )
    else:
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in configuration")
        logger.info(f"Using OpenAI Whisper Transcriber (model: {config.OPENAI_WHISPER_MODEL})")
        return OpenAITranscriber(
            api_key=config.OPENAI_API_KEY,
            model=config.OPENAI_WHISPER_MODEL,
            language=config.LANGUAGE
        )
