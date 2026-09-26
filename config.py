import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Discord Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!").strip()
# Bot Branding
BOT_NAME = "Tea Pot Transcription Bot"
DEFAULT_TRANSCRIPT_CHANNEL_NAME = os.getenv("DEFAULT_TRANSCRIPT_CHANNEL_NAME", "tea-pot-transcripts").strip()


# Speech-to-Text Provider: 'openai' or 'deepgram'
STT_PROVIDER = os.getenv("STT_PROVIDER", "openai").strip().lower()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "").strip()

# STT Model Settings
OPENAI_WHISPER_MODEL = os.getenv("OPENAI_WHISPER_MODEL", "whisper-1").strip()
DEEPGRAM_MODEL = os.getenv("DEEPGRAM_MODEL", "nova-2").strip()
LANGUAGE = os.getenv("LANGUAGE", "en").strip()  # 'en' or ISO code

# Tier & Retention Configuration
DEFAULT_SERVER_TIER = os.getenv("DEFAULT_SERVER_TIER", "free").strip().lower() # 'free', 'pro', 'premium'
DEFAULT_RETENTION_HOURS = int(os.getenv("DEFAULT_RETENTION_HOURS", "24")) # 24, 48, 168 (7d), or -1 (indefinite)
AUTO_PURGE_EXPIRED_THREADS = os.getenv("AUTO_PURGE_EXPIRED_THREADS", "true").strip().lower() in ("true", "1", "yes")

# Audio Processing Settings

CHUNK_DURATION_SECONDS = float(os.getenv("CHUNK_DURATION_SECONDS", "3.5"))  # Process chunks of speech
SILENCE_TIMEOUT_SECONDS = float(os.getenv("SILENCE_TIMEOUT_SECONDS", "1.2")) # Silence before finalizing speech
PLAY_VOICE_ANNOUNCEMENT = os.getenv("PLAY_VOICE_ANNOUNCEMENT", "true").strip().lower() in ("true", "1", "yes")

def validate_config():
    errors = []
    if not DISCORD_BOT_TOKEN:
        errors.append("DISCORD_BOT_TOKEN is missing in .env")
    if STT_PROVIDER == "openai" and not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is required when STT_PROVIDER is set to 'openai'")
    elif STT_PROVIDER == "deepgram" and not DEEPGRAM_API_KEY:
        errors.append("DEEPGRAM_API_KEY is required when STT_PROVIDER is set to 'deepgram'")
    return errors
