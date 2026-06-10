from collections import defaultdict
from discord.ext import commands


class LogTracker:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache = defaultdict(lambda: defaultdict(lambda: 0))
        self.loaded_guilds = set()

    async def load_guild(self, guild_id: int):
        if guild_id in self.loaded_guilds:
            return
        timestamps = await self.bot.log_timestamps.get_timestamps(guild_id)
        for log_type, ts in timestamps.items():
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

    async def save_guild(self, guild_id: int):
        if guild_id not in self.loaded_guilds:
            return
        await self.bot.log_timestamps.save_timestamps(
            guild_id, dict(self.cache[guild_id])
        )
