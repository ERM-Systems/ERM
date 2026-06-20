from discord.ext import tasks
import discord
import logging
from erm import Bot
import discord.http

@tasks.loop(hours=5)
async def check_sessions(bot: Bot):
    async for session in bot.sessions.db.find({"dynamic": True}):
        guild = session["_id"]
        g = await bot.fetch_guild(guild)
        settings = await bot.settings.find(guild)
        channel = await bot.fetch_channel(settings["sessions"]["channel_id"])
        players = await bot.prc_api.get_server_players(guild)
        info = await bot.prc_api.get_server_status(guild)

        d = settings["sessions"]["start"].replace(
            "{user}",
            session["user"]
        ).replace(
            "{erlc.name}",
            info.name
        ).replace(
            "{erlc.code}",
            info.join_key
        ).replace(
            "{erlc.players}",
            info.current_players
        )
        s = await bot.http.edit_message(settings["session"]["channel_id"], session["message"], params=discord.http.MultipartParameters(payload = j, multipart=None, files=None))
        