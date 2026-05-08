import discord
from discord.ext import tasks
from erm import Bot
import time
@tasks.loop(seconds=30)
async def check_ping(bot: Bot):
    for latency in bot.latencies:
        if not bot.saved_latencies.get(f"Shard {latency[0]}"):
            bot.saved_latencies[f"Shard {latency[0]}"] = []
        bot.saved_latencies[f"Shard {latency[0]}"].append((time.time() - bot.start_time, round(latency[1]*1000)))
        bot.saved_latencies[f"Shard {latency[0]}"] = bot.saved_latencies[f"Shard {latency[0]}"][-300:]