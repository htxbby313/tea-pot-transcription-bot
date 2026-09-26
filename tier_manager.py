import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import config

logger = logging.getLogger("TierManager")

DATA_FILE = Path(__file__).resolve().parent / "server_settings.json"

class TierManager:
    """
    Manages server subscription tiers, retention toggles, and thread auto-purge tracking.
    """
    def __init__(self):
        self.settings: Dict[str, Any] = {
            "guilds": {},    # guild_id -> { tier, retention_hours, auto_purge }
            "threads": {}    # thread_id -> { guild_id, created_at, expires_at }
        }
        self.load()

    def load(self):
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load server_settings.json: {e}")

    def save(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save server_settings.json: {e}")

    def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        gid = str(guild_id)
        if gid not in self.settings["guilds"]:
            self.settings["guilds"][gid] = {
                "tier": config.DEFAULT_SERVER_TIER,
                "retention_hours": config.DEFAULT_RETENTION_HOURS,
                "auto_purge": config.AUTO_PURGE_EXPIRED_THREADS
            }
            self.save()
        return self.settings["guilds"][gid]

    def set_guild_retention(self, guild_id: int, hours: int, auto_purge: bool) -> Dict[str, Any]:
        g_settings = self.get_guild_settings(guild_id)
        tier = g_settings.get("tier", "free")

        # Free tier restriction: max 48 hours
        if tier == "free":
            if hours > 48:
                hours = 48
            if hours < 24:
                hours = 24
            auto_purge = True  # Free tier must enforce auto-purge

        # Pro tier restriction: max 168 hours (7 days)
        elif tier == "pro":
            if hours > 168:
                hours = 168
            if hours <= 0:
                hours = 168

        # Premium tier: hours can be -1 (indefinite) and auto_purge is optional
        elif tier == "premium":
            if hours <= 0:
                hours = -1

        g_settings["retention_hours"] = hours
        g_settings["auto_purge"] = auto_purge
        self.save()
        return g_settings

    def set_guild_tier(self, guild_id: int, tier: str) -> Dict[str, Any]:
        tier = tier.lower()
        if tier not in ("free", "pro", "premium"):
            tier = "free"
        g_settings = self.get_guild_settings(guild_id)
        g_settings["tier"] = tier
        
        # Adjust default retention according to new tier
        if tier == "free":
            g_settings["retention_hours"] = 24
            g_settings["auto_purge"] = True
        elif tier == "pro":
            g_settings["retention_hours"] = 168
            g_settings["auto_purge"] = True
        elif tier == "premium":
            g_settings["retention_hours"] = -1
            g_settings["auto_purge"] = False

        self.save()
        return g_settings

    def can_download(self, guild_id: int) -> bool:
        """Returns True if guild is on Pro or Premium tier."""
        tier = self.get_guild_settings(guild_id).get("tier", "free")
        return tier in ("pro", "premium")

    def register_thread(self, guild_id: int, thread_id: int):
        """Registers a thread for retention auto-purge monitoring."""
        g_settings = self.get_guild_settings(guild_id)
        retention_hours = g_settings.get("retention_hours", 24)
        auto_purge = g_settings.get("auto_purge", True)

        now = time.time()
        expires_at = (now + retention_hours * 3600) if (retention_hours > 0 and auto_purge) else None

        self.settings["threads"][str(thread_id)] = {
            "guild_id": guild_id,
            "created_at": now,
            "expires_at": expires_at
        }
        self.save()

    def get_expired_threads(self) -> List[str]:
        """Returns list of thread_ids that have exceeded their retention duration."""
        now = time.time()
        expired = []
        for tid, data in list(self.settings["threads"].items()):
            exp = data.get("expires_at")
            if exp and now >= exp:
                expired.append(tid)
        return expired

    def remove_thread(self, thread_id: int):
        tid = str(thread_id)
        if tid in self.settings["threads"]:
            del self.settings["threads"][tid]
            self.save()

tier_mgr = TierManager()
