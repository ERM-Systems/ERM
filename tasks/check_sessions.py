from discord.ext import tasks
import discord
import logging
from erm import Bot
import discord.http

@tasks.loop(minutes=5)
async def check_sessions(bot: Bot):
    async for session in bot.sessions.db.find({"dynamic": True}):
        guild = session["_id"]
        g = await bot.fetch_guild(guild)
        settings = await bot.settings.find(guild)
        channel = await bot.fetch_channel(settings["sessions"]["channel_id"])
        players = await bot.prc_api.get_server_players(guild)
        try:
            info = await bot.prc_api.get_server_status(guild)
        except: info = None
        d = settings["sessions"]["start"].replace(
            "{user}",
            session["user"]
        ).replace(
            "{erlc.name}",
            info.name if info else "{erlc.name}"
        ).replace(
            "{erlc.code}",
            f"`{info.join_key}`" if info else "{erlc.code}"
        ).replace(
            "{erlc.players}",
            str(info.current_players) if info else "{erlc.players}"
        )
        await bot.http.edit_message(settings["session"]["channel_id"], session["message"], params=discord.http.MultipartParameters(payload = j, multipart=None, files=None))
        if info:
            if info.current_players > session["analytics"]["max_players"]:
                session["analytics"]["max_players"] = info.current_players
            session["analytics"]["player_counts"].append(info.current_players)
            await bot.sessions.update(session)
        