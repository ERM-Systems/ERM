import discord
from discord.ext import tasks
from erm import Bot
import time
@tasks.loop(seconds=5)
async def check_ping(bot: Bot):
    bot.saved_latencies["shards"].append(round(sum(l for _, l in bot.latencies) / len(bot.latencies) * 1000))

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

@check_ping.error
async def check_ping_e(error):
    print(f"Latency task error: {error}")
    check_ping.restart()