from discord.ext import tasks
import discord
import logging


@tasks.loop(hours=1)
async def change_status(bot):
    await bot.wait_until_ready()
    logging.info("Changing status")
    status = "⚡ /about | ermbot.xyz"
    activity = discord.CustomActivity(name=status)

    if not isinstance(bot, discord.AutoShardedBot):
        try:
            await bot.change_presence(activity=activity)
        except Exception as e:
            logging.warning(f"Failed to change presence: {e}")
        return

    for shard_id, shard in bot.shards.items():
        if shard.is_closed() or shard.is_ws_ratelimited():
            continue
        try:
            await bot.change_presence(activity=activity, shard_id=shard_id)
        except Exception as e:
            logging.warning(f"Failed to change presence on shard {shard_id}: {e}")
