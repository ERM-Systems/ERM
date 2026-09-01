from discord.ext import tasks
import discord
import logging
from erm import Bot
from utils.utils import render_session_message, send_session_full
import discord.http
@tasks.loop(minutes=5, reconnect=True)
async def check_sessions(bot: Bot):
    async for session in bot.sessions.db.find({"started": True}):
        try:
            guild = session["_id"]
            settings = await bot.settings.find(guild)
            try:
                info = await bot.prc_api.get_server_status(guild)
            except: info = None

            if session.get("dynamic") and session.get("message"):
                try:
                    payload = render_session_message(
                        settings["sessions"]["start"],
                        {
                            "{user}": session["user"],
                            "{user_mentions}": " | ".join([f"<@{user}>" for user in session["voted_users"]]),
                            "{erlc.name}": info.name if info else "{erlc.name}",
                            "{erlc.code}": info.join_key if info else "{erlc.code}",
                            "{erlc.players}": str(info.current_players) if info else "{erlc.players}",
                        },
                    )
                    await bot.http.edit_message(
                        settings["sessions"]["channel_id"],
                        session["message"],
                        params=discord.http.MultipartParameters(payload=payload, multipart=None, files=None),
                    )
                except Exception as e:
                    logging.warning(f"session {guild} dynamic message: {str(e)}")

            if info:
                if info.current_players > session["analytics"]["max_players"]:
                    session["analytics"]["max_players"] = info.current_players
                session["analytics"]["player_counts"].append(info.current_players)

                if (
                    info.max_players
                    and info.current_players >= info.max_players
                    and not session.get("full_announced")
                ):
                    try:
                        if await send_session_full(bot, guild, info):
                            session["full_announced"] = True
                    except Exception as e:
                        logging.warning(f"session {guild} full announcement: {str(e)}")

                await bot.sessions.update(session)
        except Exception as e:
            logging.warning(f"error: {str(e)}")