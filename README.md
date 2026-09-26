# 🫖 Tea Pot Transcription Bot

A real-time, stenographer-grade Discord bot that brews up exact voice channel transcriptions into timestamped, speaker-attributed text logs and dedicated meeting threads per server.

---

## ✨ Features

- 🫖 **Activity / Music Bot Style Summon**: Call Tea Pot into any voice channel with `/join`, `/transcribe`, or by mentioning `@Tea Pot join`.
- 🗣️ **Exact Speaker Attribution & Timestamps**: Accurately tracks who is speaking and posts lines formatted like:
  `🕒 14:22:05 | 🗣️ Alice: "Let's kick off the sprint review."`
- 🧵 **Server-Specific Channel & Per-Session Threads**:
  - Automatically manages a `#tea-pot-transcripts` channel in every server.
  - Automatically creates a dedicated public thread for every VC session (`🫖 [YYYY-MM-DD HH:MM] General`).
- 📢 **Audible Transparency & Notifications**:
  - Announces itself in the text channel with a transparency disclaimer.
  - Plays an audible voice chime in the VC (*"Tea Pot Transcription is now active in this channel"*) to ensure all participants are aware.

- ⚡ **Dual Cloud STT Engine Support**:
  - **OpenAI Whisper API** (`whisper-1`) for verbatim accuracy.
  - **Deepgram Nova-2** for streaming, real-time speed.
- 📄 **Automatic Meeting Minutes & Transcript Export**:
  - Uploads a full `.txt` transcript file when the session ends or when `/export` is run.
  - Generates speaker participation statistics (duration, line counts per person).
- 🚪 **Auto-Disconnect**: Detects when the voice channel becomes empty, finalizes the transcript, archives the thread, and leaves gracefully.
- 📦 **Downloadable & Distributable**: Portable setup with 1-click launchers (`start.bat`, `start.sh`) and Docker.

---

## 🚀 Quick Start Guide

### 1. Create your Discord Bot Application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and click **New Application**.
2. Give your bot a name (e.g., `Sonographer Transcriber`).
3. Navigate to the **Bot** tab on the left:
   - Click **Reset Token** (or **Copy Token**) and save your `DISCORD_BOT_TOKEN`.
   - Scroll down to **Privileged Gateway Intents** and enable:
     - ✅ **SERVER MEMBERS INTENT**
     - ✅ **MESSAGE CONTENT INTENT**
4. Navigate to **OAuth2** ➡️ **URL Generator**:
   - **Scopes**: select `bot` and `applications.commands`
   - **Bot Permissions**:
     - *General Permissions*: `Manage Channels` (for auto-creating `#voice-transcripts`), `View Channels`
     - *Text Permissions*: `Send Messages`, `Create Public Threads`, `Send Messages in Threads`, `Attach Files`, `Read Message History`
     - *Voice Permissions*: `Connect`, `Speak`, `Use Voice Activity`
5. Copy the generated **Invite URL** and paste it into your browser to invite the bot to your server!

---

### 2. Configure Environment (`.env`)

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your keys:
   ```env
   DISCORD_BOT_TOKEN=your_bot_token_here
   STT_PROVIDER=openai   # or 'deepgram'
   OPENAI_API_KEY=sk-... # or DEEPGRAM_API_KEY=...
   ```

---

### 3. Run the Bot

#### Windows (1-Click)
Double-click **`start.bat`**. It will automatically configure the Python virtual environment, install dependencies, and boot the bot!

#### Linux / macOS
```bash
chmod +x start.sh
./start.sh
```

#### Docker (Optional)
```bash
docker compose up -d
```

---

## 📋 Commands

| Command | Shortcut / Mention | Description |
| :--- | :--- | :--- |
| `/join` or `/transcribe` | `@Bot join` | Summons the bot into your current voice channel and starts transcribing |
| `/leave` | `@Bot leave` | Stops transcribing, posts summary & transcript `.txt` file, and leaves VC |
| `/status` | — | Shows live session duration, lines recorded, and active speakers |
| `/pause` | — | Temporarily pauses transcription |
| `/resume` | — | Resumes transcription |
| `/export` | — | Downloads the current transcript file without ending the session |
| `/help` | `@Bot help` | Displays full instructions and command list |

---

## 📁 Project Structure

```
discord-transcriber-bot/
├── bot.py                  # Main entrypoint, slash commands & event listeners
├── session_manager.py      # Multi-guild session tracker, thread creator & exporter
├── audio_sink.py           # Real-time voice receiver & speech segmenter
├── transcriber.py          # OpenAI Whisper & Deepgram STT adapters
├── announcer.py            # Audible VC chime & TTS generator
├── config.py               # Settings loader and validator
├── requirements.txt        # Python dependency manifest
├── start.bat               # 1-click Windows runner
├── start.sh                # Linux / macOS runner
├── Dockerfile              # Container image configuration
├── docker-compose.yml      # Container orchestration
├── .env.example            # Environment variables template
└── README.md               # Documentation
```

---

## 🔒 Privacy & Transparency Notice
This bot is designed to be fully compliant with two-party consent and transparency principles. When joining a voice channel:
1. It sends a message in the text channel indicating active transcription.
2. It plays an audible chime in the voice channel stating *"Voice transcription is now active"*.
3. Transcripts are scoped strictly to the server's dedicated `#voice-transcripts` channel.
