import datetime
import logging

from discord.ext import tasks

checkInterval = 30
graceDefault = 60

watched: dict[int, dict[int, int]] = {}


def _options(settings: dict) -> dict:
    return (settings or {}).get("sessions") or {}


def _clear(guildId: int, keep: set):
    tracked = watched.get(guildId)
    if not tracked:
        return

    for playerId in [pid for pid in tracked if pid not in keep]:
        tracked.pop(playerId, None)

    if not tracked:
        watched.pop(guildId, None)


async def _command(bot, guildId: int, command: str) -> bool:
    try:
        response = await bot.prc_api.run_command(guildId, command)
    except Exception as error:
        logging.warning(f"[AutoKick] command failed in {guildId}: {error}")
        return False

    if response[0] not in (200, 204):
        logging.warning(f"[AutoKick] {command!r} in {guildId} returned {response[0]}")
        return False

    return True


def grace_period(settings: dict) -> int:
    raw = _options(settings).get("auto_kick_grace")
    return max(0, int(graceDefault if raw is None else raw))


def is_staff(player) -> bool:
    """Only an explicit Normal counts as a player, so an unknown permission never
    gets somebody kicked."""
    return getattr(player, "permission", None) != "Normal"


def review_player(tracked: dict, playerId: int, now: int, grace: int) -> str:
    since = tracked.setdefault(playerId, now)

    if now - since < grace:
        return "wait"

    return "kick"


async def kick_guild(bot, guildId: int, settings: dict) -> int:
    if _options(settings).get("auto_kick") is not True:
        watched.pop(guildId, None)
        return 0

    try:
        players = await bot.prc_api.get_server_players(guildId)
    except Exception as error:
        logging.info(f"[AutoKick] no players for {guildId}: {error}")
        return 0

    civilians = [player for player in (players or []) if not is_staff(player)]
    _clear(guildId, {player.id for player in civilians})

    if not civilians:
        return 0

    now = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
    grace = grace_period(settings)
    tracked = watched.setdefault(guildId, {})
    kicked = 0

    for player in civilians:
        if review_player(tracked, player.id, now, grace) != "kick":
            continue

        if await _command(bot, guildId, f":kick {player.id}"):
            kicked += 1

        tracked.pop(player.id, None)

    return kicked


@tasks.loop(seconds=checkInterval, reconnect=True)
async def auto_kick(bot):
    try:
        async for settings in bot.settings.db.find({"sessions.auto_kick": True}):
            guildId = settings.get("_id")
            if not guildId:
                continue

            session = await bot.sessions.db.find_one({"_id": guildId})
            if session:
                watched.pop(guildId, None)
                continue

            try:
                await kick_guild(bot, guildId, settings)
            except Exception as error:
                logging.warning(f"[AutoKick] sweep failed for {guildId}: {error}")
    except Exception as error:
        logging.warning(f"[AutoKick] sweep failed: {error}")


@auto_kick.before_loop
async def before_auto_kick(bot=None):
    pass
