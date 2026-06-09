from collections import defaultdict
from discord.ext import commands


class LogTracker:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache = defaultdict(lambda: defaultdict(lambda: 0))
        self.loaded_guilds = set()

    async def _load_guild(self, guild_id: int):
        if guild_id in self.loaded_guilds:
            return
        doc = await self.bot.db.log_timestamps.find_one({"_id": guild_id})
        if doc:
            for log_type, ts in doc.get("timestamps", {}).items():
                self.cache[guild_id][log_type] = ts
        self.loaded_guilds.add(guild_id)

    def get_last_timestamp(self, guild_id: int, log_type: str) -> int:
        if guild_id not in self.loaded_guilds:
            return int(self.bot.start_time)
        return self.cache[guild_id][log_type] or int(self.bot.start_time)

    def update_timestamp(self, guild_id: int, log_type: str, timestamp: int):
        self.cache[guild_id][log_type] = max(
            timestamp, self.cache[guild_id][log_type]
        )

    async def load_guild(self, guild_id: int):
        await self._load_guild(guild_id)

    async def save_guild(self, guild_id: int):
        if guild_id not in self.loaded_guilds:
            return
        await self.bot.db.log_timestamps.update_one(
            {"_id": guild_id},
            {"$set": {"timestamps": dict(self.cache[guild_id])}},
            upsert=True,
        )
