import discord
from discord.ext import tasks
from erm import Bot
import time
@tasks.loop(seconds=5)
async def check_ping(bot: Bot):
    for latency in bot.latencies:
        if not bot.saved_latencies["shards"].get(f"Shard {latency[0]}"):
            bot.saved_latencies["shards"][f"Shard {latency[0]}"] = []
        bot.saved_latencies["shards"][f"Shard {latency[0]}"].append(round(latency[1]*1000))
        bot.saved_latencies["shards"][f"Shard {latency[0]}"] = bot.saved_latencies["shards"][f"Shard {latency[0]}"][-300:]
    
    before = time.monotonic()
    user = await bot.fetch_user(993781395761676298)
    after = time.monotonic()
    rest_latency = round((after - before) * 1000)
    bot.saved_latencies["rest"].append(rest_latency)

    before = time.monotonic()
    user = await bot.db.command("ping")
    after = time.monotonic()
    db_latency = round((after - before) * 1000)
    bot.saved_latencies["db"].append(db_latency)