import datetime
import logging

from discord.ext import tasks

from utils.area_of_play import active_region, enforcement_plan, outside_players

checkInterval = 60
graceDefault = 120
warnCooldown = 60

offenders: dict[int, dict[int, dict]] = {}


def _options(settings: dict) -> dict:
    return (settings or {}).get("area_of_play") or {}


def _clear(guild_id: int, keep: set):
    tracked = offenders.get(guild_id)
    if not tracked:
        return

    for player_id in [pid for pid in tracked if pid not in keep]:
        tracked.pop(player_id, None)

    if not tracked:
        offenders.pop(guild_id, None)


async def _command(bot, guild_id: int, command: str) -> bool:
    try:
        response = await bot.prc_api.run_command(guild_id, command)
    except Exception as error:
        logging.warning(f"[AOP] command failed in {guild_id}: {error}")
        return False

    if response[0] not in (200, 204):
        logging.warning(f"[AOP] {command!r} in {guild_id} returned {response[0]}")
        return False

    return True


def review_player(state: dict, now: int, grace: int, options: dict) -> str:
    """Decide what a player outside the area has earned, if anything."""
    if now - state["since"] < grace:
        return "wait"

    if now - state.get("last", 0) < warnCooldown:
        return "wait"

    state["warned"] += 1
    state["last"] = now

    return enforcement_plan(options, state["warned"])


async def enforce_guild(bot, guild_id: int, settings: dict, session: dict | None = None):
    region = active_region(settings, session)
    if not region:
        offenders.pop(guild_id, None)
        return 0

    options = _options(settings)

    try:
        players = await bot.prc_api.get_server_players(guild_id)
    except Exception as error:
        logging.info(f"[AOP] no players for {guild_id}: {error}")
        return 0

    outside = outside_players(players, region)
    _clear(guild_id, {player.id for player in outside})

    if not outside:
        return 0

    now = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
    rawGrace = options.get("grace_seconds")
    grace = max(0, int(graceDefault if rawGrace is None else rawGrace))
    tracked = offenders.setdefault(guild_id, {})
    acted = 0

    for player in outside:
        state = tracked.setdefault(player.id, {"since": now, "warned": 0, "last": 0})
        verdict = review_player(state, now, grace, options)

        if verdict == "wait":
            continue

        if verdict == "warn":
            message = options.get("warning_message") or (
                f"You are outside the area of play ({region['name']}). Return or you will be removed."
            )
            await _command(bot, guild_id, f":pm {player.username} {message}")
        elif verdict == "kick":
            if await _command(bot, guild_id, f":kick {player.id}"):
                tracked.pop(player.id, None)
        elif verdict == "ban":
            if await _command(bot, guild_id, f":ban {player.id}"):
                tracked.pop(player.id, None)
        elif verdict == "wanted":
            if await _command(bot, guild_id, f":wanted {player.username}"):
                tracked.pop(player.id, None)

        acted += 1

    return acted


@tasks.loop(seconds=checkInterval, reconnect=True)
async def enforce_aop(bot):
    try:
        async for settings in bot.settings.db.find({"area_of_play.enabled": True}):
            guild_id = settings.get("_id")
            if not guild_id:
                continue

            session = await bot.sessions.db.find_one({"_id": guild_id})
            if _options(settings).get("sessions_only") is True and not session:
                offenders.pop(guild_id, None)
                continue

            try:
                await enforce_guild(bot, guild_id, settings, session)
            except Exception as error:
                logging.warning(f"[AOP] enforcement failed for {guild_id}: {error}")
    except Exception as error:
        logging.warning(f"[AOP] enforcement sweep failed: {error}")


@enforce_aop.before_loop
async def before_enforce_aop(bot=None):
    pass
