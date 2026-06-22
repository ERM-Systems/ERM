from discord.ext import tasks
import discord
import logging
from erm import Bot
import discord.http
import json
@tasks.loop(minutes=5, reconnect=True)
async def check_sessions(bot: Bot):
    print("Ran!")
    async for session in bot.sessions.db.find({"dynamic": True}):
        print(f"Parsing session for guild {session["_id"]}")
        try:
            guild = session["_id"]
            g = await bot.fetch_guild(guild)
            settings = await bot.settings.find(guild)
            try:
                info = await bot.prc_api.get_server_status(guild)
            except: info = None
            print(info)
            d = settings["sessions"]["start"].replace(
                "{user}",
                session["user"]
            ).replace(
                "{erlc.name}",
                info.name if info else "{erlc.name}"
            ).replace(
                "{user_mentions}",
                f"{" | ".join([f"<@{user}>" for user in session["voted_users"]])}"
            ).replace(
                "{erlc.code}",
                f"{info.join_key}" if info else "{erlc.code}"
            ).replace(
                "{erlc.players}",
                str(info.current_players) if info else "{erlc.players}"
            )
            j = json.loads(d)
            await bot.http.edit_message(settings["sessions"]["channel_id"], session["message"], params=discord.http.MultipartParameters(payload = j, multipart=None, files=None))
            if info:
                if info.current_players > session["analytics"]["max_players"]:
                    session["analytics"]["max_players"] = info.current_players
                session["analytics"]["player_counts"].append(info.current_players)
                await bot.sessions.update(session)
        except Exception as e:
            logging.warning(f"error: {str(e)}")