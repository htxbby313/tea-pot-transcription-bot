import os
import sys
import logging
import asyncio
import datetime
import discord
from discord.ext import commands, tasks

import config
from transcriber import get_transcriber
from session_manager import SessionManager, VoiceSession
from announcer import ensure_audio_files
from tier_manager import tier_mgr


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("TranscriberBot")

# Configure Intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix=config.COMMAND_PREFIX,
    intents=intents,
    help_command=None
)

# Initialize Transcriber & Session Manager
transcriber = None
session_mgr = None

async def get_or_create_transcript_channel(guild: discord.Guild) -> discord.TextChannel:
    """Finds or creates the designated transcript text channel in the guild."""
    channel_name = config.DEFAULT_TRANSCRIPT_CHANNEL_NAME.lower().replace(" ", "-")
    
    # 1. Search for existing channel by name
    for channel in guild.text_channels:
        if channel.name.lower() == channel_name:
            return channel

    # 2. If not found, attempt to create it
    try:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False, read_message_history=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, create_public_threads=True, send_messages_in_threads=True, attach_files=True)
        }
        new_channel = await guild.create_text_channel(
            name=channel_name,
            topic="🫖 Automated Tea Pot voice channel transcripts & meeting records.",
            overwrites=overwrites,
            reason="Tea Pot Transcriber designated log channel"
        )
        logger.info(f"Created transcript channel #{channel_name} in {guild.name}")
        return new_channel
    except discord.Forbidden:
        # Fallback to system channel or first text channel
        if guild.system_channel:
            return guild.system_channel
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                return ch
        raise RuntimeError("Bot lacks permissions to view or create text channels.")

@tasks.loop(minutes=15)
async def auto_purge_retention_task():
    """Background task to auto-purge expired transcript threads based on server retention."""
    try:
        expired_ids = tier_mgr.get_expired_threads()
        if not expired_ids:
            return
        logger.info(f"Purging {len(expired_ids)} expired transcript threads...")
        for tid in expired_ids:
            thread_id = int(tid)
            try:
                thread = bot.get_channel(thread_id)
                if not thread:
                    thread = await bot.fetch_channel(thread_id)
                if thread and isinstance(thread, discord.Thread):
                    logger.info(f"Auto-purging expired transcript thread: {thread.name} (ID: {thread_id})")
                    await thread.delete(reason="Tea Pot Retention Policy Expired")
            except (discord.NotFound, discord.Forbidden) as e:
                logger.warning(f"Could not purge thread {thread_id}: {e}")
            finally:
                tier_mgr.remove_thread(thread_id)
    except Exception as e:
        logger.error(f"Error in auto_purge_retention_task: {e}", exc_info=True)

@bot.event
async def on_ready():
    global transcriber, session_mgr
    logger.info(f"🫖 Logged in as {bot.user.name} (ID: {bot.user.id})")
    
    # Pre-generate TTS audio assets
    ensure_audio_files()

    try:
        transcriber = get_transcriber()
        session_mgr = SessionManager(transcriber)
        logger.info("Transcriber and SessionManager initialized successfully.")
    except Exception as e:
        logger.error(f"Initialization error: {e}")

    # Start retention auto-purge loop
    if not auto_purge_retention_task.is_running():
        auto_purge_retention_task.start()

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="VCs | 🫖 /join or @mention"
        )
    )
    logger.info("🫖 Tea Pot Transcription Bot is ready and serving guilds.")


async def handle_join_vc(ctx_or_interaction, user: discord.Member) -> Optional[VoiceSession]:
    """Helper to join VC, create thread, and start live transcription."""
    guild = user.guild
    if not user.voice or not user.voice.channel:
        msg = "❌ You must be in a voice channel to summon **Tea Pot**!"
        if hasattr(ctx_or_interaction, 'response'):
            await ctx_or_interaction.response.send_message(msg, ephemeral=True)
        else:
            await ctx_or_interaction.send(msg)
        return None

    vc_channel = user.voice.channel

    # Check if bot already connected
    existing_session = session_mgr.get_session(guild.id)
    if existing_session and existing_session.voice_client.is_connected():
        if existing_session.voice_channel.id == vc_channel.id:
            msg = f"🫖 Tea Pot is already transcribing **#{vc_channel.name}**! Thread: {existing_session.thread.mention}"
            if hasattr(ctx_or_interaction, 'response'):
                await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(msg)
            return existing_session
        else:
            await session_mgr.stop_session(guild.id)

    # Initial response
    if hasattr(ctx_or_interaction, 'response'):
        await ctx_or_interaction.response.defer()

    try:
        # 1. Locate or create transcript channel
        transcript_channel = await get_or_create_transcript_channel(guild)

        # 2. Connect to voice channel
        voice_client = guild.voice_client
        if voice_client and voice_client.is_connected():
            if voice_client.channel.id != vc_channel.id:
                await voice_client.move_to(vc_channel)
        else:
            voice_client = await vc_channel.connect()

        # 3. Create active session and thread
        session = await session_mgr.create_session(
            guild=guild,
            voice_channel=vc_channel,
            transcript_channel=transcript_channel,
            voice_client=voice_client,
            summoner=user
        )

        # 4. Announce in text channel
        announcement_embed = discord.Embed(
            title="🫖 Tea Pot Transcription Joined",
            description=(
                f"Joined **#{vc_channel.name}** and started live transcription.\n\n"
                f"📝 **Live Transcripts:** {session.thread.mention}\n"
                f"📢 **Transparency Notice:** Spoken audio in this voice channel is being transcribed in real-time."
            ),
            color=0x57F287
        )
        announcement_embed.set_footer(text="Use /leave or mention '@Tea Pot leave' to finish the session.")

        if hasattr(ctx_or_interaction, 'followup'):
            await ctx_or_interaction.followup.send(embed=announcement_embed)
        else:
            await ctx_or_interaction.send(embed=announcement_embed)

        return session

    except Exception as e:
        logger.error(f"Failed to join and start session: {e}", exc_info=True)
        err_msg = f"❌ Failed to start transcription: `{str(e)}`"
        if hasattr(ctx_or_interaction, 'followup'):
            await ctx_or_interaction.followup.send(err_msg)
        else:
            await ctx_or_interaction.send(err_msg)
        return None

# ==========================================
# Slash Commands
# ==========================================

@bot.slash_command(name="join", description="Summon Tea Pot to your current voice channel")
async def slash_join(ctx: discord.ApplicationContext):
    await handle_join_vc(ctx, ctx.author)

@bot.slash_command(name="transcribe", description="Start live Tea Pot transcription in your voice channel")
async def slash_transcribe(ctx: discord.ApplicationContext):
    await handle_join_vc(ctx, ctx.author)

@bot.slash_command(name="leave", description="Stop Tea Pot, export meeting transcript, and leave VC")
async def slash_leave(ctx: discord.ApplicationContext):
    guild = ctx.guild
    session = session_mgr.get_session(guild.id)
    if not session:
        await ctx.respond("❌ Tea Pot is not currently in an active voice session.", ephemeral=True)
        return

    await ctx.defer()
    duration_str = await session_mgr.stop_session(guild.id)
    
    embed = discord.Embed(
        title="🫖 Tea Pot — Transcription Stopped",
        description=f"Saved meeting transcript and left **#{session.voice_channel.name}**.\n\n📄 **Transcript:** Available in {session.thread.mention}",
        color=0xED4245
    )
    embed.add_field(name="Duration", value=duration_str, inline=True)
    await ctx.followup.send(embed=embed)

@bot.slash_command(name="pause", description="Pause live transcription without leaving the VC")
async def slash_pause(ctx: discord.ApplicationContext):
    session = session_mgr.get_session(ctx.guild.id)
    if not session:
        await ctx.respond("❌ No active transcription session found.", ephemeral=True)
        return
    session.is_paused = True
    await ctx.respond("⏸️ Tea Pot transcription is now **PAUSED**.")

@bot.slash_command(name="resume", description="Resume live transcription")
async def slash_resume(ctx: discord.ApplicationContext):
    session = session_mgr.get_session(ctx.guild.id)
    if not session:
        await ctx.respond("❌ No active transcription session found.", ephemeral=True)
        return
    session.is_paused = False
    await ctx.respond("▶️ Tea Pot transcription has **RESUMED**.")

@bot.slash_command(name="status", description="Check current transcription session status and stats")
async def slash_status(ctx: discord.ApplicationContext):
    session = session_mgr.get_session(ctx.guild.id)
    if not session:
        await ctx.respond("ℹ️ No active Tea Pot transcription session on this server.", ephemeral=True)
        return

    elapsed_sec = int(time.time() - session.start_time)
    mins, secs = divmod(elapsed_sec, 60)

    embed = discord.Embed(
        title="🫖 Tea Pot — Active Transcription Status",
        color=0x5865F2
    )
    embed.add_field(name="🔊 Channel", value=session.voice_channel.mention, inline=True)
    embed.add_field(name="⏱️ Elapsed Time", value=f"{mins}m {secs}s", inline=True)
    embed.add_field(name="📝 Thread", value=session.thread.mention, inline=True)
    embed.add_field(name="💬 Lines Recorded", value=str(len(session.entries)), inline=True)
    embed.add_field(name="👥 Active Speakers", value=str(len(session.speaker_counts)), inline=True)
    embed.add_field(name="⚙️ Status", value="⏸️ Paused" if session.is_paused else "🟢 Transcribing", inline=True)
    await ctx.respond(embed=embed)

@bot.slash_command(name="export", description="Export the current transcript text file (Pro & Premium tiers)")
async def slash_export(ctx: discord.ApplicationContext):
    session = session_mgr.get_session(ctx.guild.id)
    if not session:
        await ctx.respond("❌ No active transcription session found.", ephemeral=True)
        return

    # Check tier permission
    if not tier_mgr.can_download(ctx.guild.id):
        g_settings = tier_mgr.get_guild_settings(ctx.guild.id)
        tier_name = g_settings.get("tier", "free").capitalize()
        await ctx.respond(
            f"ℹ️ **{tier_name} Tier Limitation:** Direct file downloads (`.txt`/`.md`) are enabled on **Pro** and **Premium** tiers.\n"
            f"Transcripts are viewable in the thread {session.thread.mention} during your active {g_settings.get('retention_hours', 24)}h retention window.",
            ephemeral=True
        )
        return

    await ctx.defer()
    elapsed_sec = int(time.time() - session.start_time)
    mins, secs = divmod(elapsed_sec, 60)
    duration_str = f"{mins}m {secs}s (In Progress)"
    
    file_content = session.generate_transcript_file_content(duration_str)
    buffer = io.BytesIO(file_content.encode("utf-8"))
    filename = f"TeaPot_Transcript_{session.voice_channel.name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    file = discord.File(buffer, filename=filename)
    
    await ctx.followup.send("📄 **Current Tea Pot Transcript Export:**", file=file)

@bot.slash_command(name="tier", description="View your server's current subscription tier & retention policy")
async def slash_tier(ctx: discord.ApplicationContext):
    g_settings = tier_mgr.get_guild_settings(ctx.guild.id)
    tier = g_settings.get("tier", "free").capitalize()
    hours = g_settings.get("retention_hours", 24)
    auto_purge = g_settings.get("auto_purge", True)
    can_dl = tier_mgr.can_download(ctx.guild.id)

    embed = discord.Embed(
        title=f"🫖 Tea Pot — Server Subscription & Retention",
        description=f"Settings for **{ctx.guild.name}**",
        color=0x10B981 if tier != "Free" else 0x5865F2
    )
    embed.add_field(name="Current Tier", value=f"**{tier} Tier**", inline=True)
    embed.add_field(
        name="Retention Window",
        value=f"{hours} Hours" if hours > 0 else "Permanent / Indefinite",
        inline=True
    )
    embed.add_field(
        name="Auto-Purge Toggle",
        value="🟢 Enabled" if auto_purge else "⚪ Disabled",
        inline=True
    )
    embed.add_field(
        name="Meeting File Downloads",
        value="✅ Enabled (.txt / .md)" if can_dl else "🔒 Disabled (Viewable in Discord)",
        inline=True
    )
    embed.add_field(
        name="Tier Summary",
        value=(
            "• **Free Tier (Chamomile):** 24h – 48h Retention with Auto-Purge Toggle\n"
            "• **Pro Tier (Earl Grey):** Up to 7 Days Retention + File Downloads (.txt / .md)\n"
            "• **Premium Tier (Matcha):** Indefinite Permanent Archiving + Optional Auto-Purge"
        ),
        inline=False
    )
    embed.set_footer(text="Admins can configure retention with /retention")
    await ctx.respond(embed=embed)

@bot.slash_command(name="retention", description="Configure transcript retention duration and auto-purge toggle")
async def slash_retention(
    ctx: discord.ApplicationContext,
    hours: discord.Option(int, "Retention duration in hours (e.g. 24, 48, 168 for 7 days, or -1 for permanent)", required=True),
    auto_purge: discord.Option(bool, "Enable auto-purging expired transcript threads", required=False, default=True)
):
    if not ctx.author.guild_permissions.manage_guild and not ctx.author.guild_permissions.administrator:
        await ctx.respond("❌ You need **Manage Server** permissions to change retention settings.", ephemeral=True)
        return

    g_settings = tier_mgr.set_guild_retention(ctx.guild.id, hours, auto_purge)
    actual_hours = g_settings["retention_hours"]
    tier_name = g_settings["tier"].capitalize()
    
    embed = discord.Embed(
        title="⚙️ Retention Policy Updated",
        color=0x57F287
    )
    embed.add_field(name="Server Tier", value=tier_name, inline=True)
    embed.add_field(
        name="Active Retention",
        value=f"{actual_hours} Hours" if actual_hours > 0 else "Indefinite Permanent",
        inline=True
    )
    embed.add_field(name="Auto-Purge Toggle", value="Enabled" if g_settings["auto_purge"] else "Disabled", inline=True)

    if tier_name == "Free" and hours > 48:
        embed.set_footer(text="Free tier is capped at 48 hours. Upgrade to Pro/Premium for 7-day or indefinite retention.")

    await ctx.respond(embed=embed)

@bot.slash_command(name="help", description="Show Tea Pot bot commands and guide")
async def slash_help(ctx: discord.ApplicationContext):
    embed = discord.Embed(
        title="🫖 Tea Pot Transcription Bot",
        description="A real-time voice channel transcriber that turns spoken conversations into exact, timestamped text logs and dedicated meeting threads.",
        color=0x5865F2
    )
    embed.add_field(
        name="🚀 How to Summon",
        value=(
            "• Join any voice channel\n"
            "• Type `/join` or `/transcribe`\n"
            "• Or mention `@Tea Pot join` in any text chat"
        ),
        inline=False
    )
    embed.add_field(
        name="📋 Commands",
        value=(
            "`/join` - Summons Tea Pot into your current VC\n"
            "`/leave` - Stops recording, exports full transcript, and leaves\n"
            "`/tier` - View server subscription tier and retention policy\n"
            "`/retention` - Set retention hours (24h/48h) and auto-purge toggle\n"
            "`/pause` / `/resume` - Pause or resume transcription\n"
            "`/status` - View current session stats and active speakers\n"
            "`/export` - Download current transcript (Pro/Premium)\n"
            "`/help` - Show this guide"
        ),
        inline=False
    )
    embed.add_field(
        name="📁 Where do transcripts go?",
        value=f"Transcripts are logged into dedicated threads inside the `#{config.DEFAULT_TRANSCRIPT_CHANNEL_NAME}` channel per server.",
        inline=False
    )
    await ctx.respond(embed=embed)



# ==========================================
# Mention & Prefix Command Listeners
# ==========================================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Check for direct bot mention
    if bot.user in message.mentions:
        content = message.content.lower()
        if any(w in content for w in ["join", "transcribe", "start", "record", "here"]):
            if isinstance(message.author, discord.Member):
                await handle_join_vc(message.channel, message.author)
                return
        elif any(w in content for w in ["leave", "stop", "disconnect", "bye", "end"]):
            session = session_mgr.get_session(message.guild.id)
            if session:
                duration_str = await session_mgr.stop_session(message.guild.id)
                await message.channel.send(f"⏹️ Stopped transcription and saved session log ({duration_str}).")
            else:
                await message.channel.send("❌ Not currently in a voice channel.")
            return
        elif "help" in content:
            # Send brief guide
            await message.channel.send("🎙️ To start transcribing, join a voice channel and type `/join` or mention me with `join`!")
            return

    await bot.process_commands(message)

# Prefix commands fallback
@bot.command(name="join")
async def prefix_join(ctx: commands.Context):
    await handle_join_vc(ctx, ctx.author)

@bot.command(name="leave")
async def prefix_leave(ctx: commands.Context):
    session = session_mgr.get_session(ctx.guild.id)
    if session:
        duration_str = await session_mgr.stop_session(ctx.guild.id)
        await ctx.send(f"⏹️ Left VC and uploaded meeting transcript in {session.thread.mention} ({duration_str}).")
    else:
        await ctx.send("❌ Not in an active voice session.")

# ==========================================
# Auto-leave when VC is empty
# ==========================================

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """Automatically ends session and leaves if all human users leave the voice channel."""
    if member.bot:
        return

    # Check if a voice channel became empty of non-bot members
    guild = member.guild
    session = session_mgr.get_session(guild.id)
    if not session:
        return

    vc = session.voice_channel
    # Count non-bot members in VC
    human_members = [m for m in vc.members if not m.bot]
    if len(human_members) == 0:
        logger.info(f"VC #{vc.name} in {guild.name} is now empty. Auto-disconnecting...")
        await asyncio.sleep(2) # Grace period
        # Re-check
        human_members = [m for m in vc.members if not m.bot]
        if len(human_members) == 0:
            await session_mgr.stop_session(guild.id)

# ==========================================
# Main Execution Entrypoint
# ==========================================

def main():
    errors = config.validate_config()
    if errors:
        print("\n" + "=" * 60)
        print("❌ CONFIGURATION ERROR(S) IN .env:")
        for err in errors:
            print(f"  • {err}")
        print("=" * 60)
        print("Please check and configure your .env file before starting the bot.")
        print("See .env.example for a template.\n")
        sys.exit(1)

    print("=" * 60)
    print("🫖 Starting Tea Pot Transcription Bot...")
    print(f"• STT Provider: {config.STT_PROVIDER.upper()}")
    print(f"• Default Transcripts Channel: #{config.DEFAULT_TRANSCRIPT_CHANNEL_NAME}")
    print(f"• Voice Announcement: {'Enabled' if config.PLAY_VOICE_ANNOUNCEMENT else 'Disabled'}")
    print("=" * 60)

    
    bot.run(config.DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    main()
