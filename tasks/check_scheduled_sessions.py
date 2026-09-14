import datetime
import logging

import discord
from discord.ext import tasks

from utils.constants import BLANK_COLOR
from utils.session_schedule import due_schedules
from utils.utils import create_session_vote, start_session

checkInterval = 30
maxAttempts = 3


async def _post(bot, document) -> None:
    guildId = document.get("guild")
    if not guildId:
        return

    createdBy = document.get("created_by") or bot.user.id
    kind = document.get("type") or "start"

    if kind == "vote":
        if await bot.sessions.find(guildId):
            return
        await create_session_vote(
            bot, guildId, createdBy, document.get("required_votes")
        )
        return

    await start_session(bot, guildId, createdBy)


async def _notify(bot, document, error) -> None:
    userId = document.get("created_by")
    if not userId:
        return

    try:
        user = bot.get_user(userId) or await bot.fetch_user(userId)
        await user.send(
            embed=discord.Embed(
                title="Scheduled Session Failed",
                description=f"Your scheduled session in <#{document.get('channel')}> could not be started.\n> {error}",
                color=BLANK_COLOR,
            )
        )
    except Exception as exception:
        logging.error(
            "[Scheduled Sessions] could not notify %s: %s", userId, exception
        )


async def _abandon(bot, document, error) -> None:
    try:
        await bot.scheduled_sessions.mark_posted(document["_id"])
    except Exception as exception:
        logging.error(
            "[Scheduled Sessions] could not mark %s posted: %s",
            document.get("_id"),
            exception,
        )

    await _notify(bot, document, error)


@tasks.loop(seconds=checkInterval, reconnect=True)
async def check_scheduled_sessions(bot):
    now = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())

    try:
        documents = await bot.scheduled_sessions.due(now)
    except Exception as exception:
        logging.error("[Scheduled Sessions] could not read schedules: %s", exception)
        return

    for document in due_schedules(documents, now):
        try:
            await _post(bot, document)
        except ValueError as error:
            logging.info(
                "[Scheduled Sessions] skipped %s in %s: %s",
                document.get("_id"),
                document.get("guild"),
                error,
            )
            await _abandon(bot, document, error)
            continue
        except Exception as exception:
            logging.error(
                "[Scheduled Sessions] failed to post %s in %s: %s",
                document.get("_id"),
                document.get("guild"),
                exception,
            )
            attempts = int(document.get("attempts") or 0) + 1
            if attempts >= maxAttempts:
                await _abandon(bot, document, exception)
            else:
                try:
                    await bot.scheduled_sessions.db.update_one(
                        {"_id": document["_id"]}, {"$set": {"attempts": attempts}}
                    )
                except Exception as error:
                    logging.error(
                        "[Scheduled Sessions] could not record attempt for %s: %s",
                        document.get("_id"),
                        error,
                    )
            continue

        try:
            await bot.scheduled_sessions.mark_posted(document["_id"])
        except Exception as exception:
            logging.error(
                "[Scheduled Sessions] could not mark %s posted: %s",
                document.get("_id"),
                exception,
            )


@check_scheduled_sessions.before_loop
async def before_check_scheduled_sessions(bot=None):
    pass
