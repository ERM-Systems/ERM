import discord
from discord.ext import tasks
from erm import Bot
import time
@tasks.loop(seconds=5)
async def check_ping(bot: Bot):
    try:
        bot.saved_latencies["shards"].append(round(sum(l for _, l in bot.latencies) / len(bot.latencies) * 1000))
    except:
        pass

    before = time.monotonic()
    user = await bot.db.command("ping")
    after = time.monotonic()
    db_latency = round((after - before) * 1000)
    bot.saved_latencies["db"].append(db_latency)

