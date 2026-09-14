import logging

import discord


def _options(settings: dict) -> dict:
    return ((settings or {}).get("sessions") or {}).get("channel_locks") or {}


def locked_channels(settings: dict) -> list[int]:
    options = _options(settings)
    if options.get("enabled") is not True:
        return []

    return [
        int(channel)
        for channel in (options.get("channels") or [])
        if str(channel).isdigit()
    ]


def lock_role_id(settings: dict, guildId: int) -> int:
    role = _options(settings).get("role")
    if role is None or not str(role).isdigit():
        return int(guildId)

    return int(role)


def next_overwrite(current, locked: bool, restore=None):
    overwrite = current or discord.PermissionOverwrite()
    overwrite.send_messages = False if locked else restore
    return overwrite


async def _resolve(guild, channelId: int):
    channel = guild.get_channel(channelId)
    if channel is not None:
        return channel

    try:
        return await guild.fetch_channel(channelId)
    except Exception as error:
        logging.warning(f"[Sessions] lock channel {channelId} missing in {guild.id}: {error}")
        return None


async def apply_channel_locks(bot, guild, settings: dict, locked: bool) -> tuple[int, list[int]]:
    channels = locked_channels(settings)
    if not channels:
        return 0, []

    roleId = lock_role_id(settings, guild.id)
    role = guild.get_role(roleId)
    if role is None:
        logging.warning(f"[Sessions] lock role {roleId} missing in {guild.id}")
        return 0, channels

    previous = _options(settings).get("previous") or {}
    reason = "Session started" if locked else "Session ended"
    changed = 0
    failed = []
    restore = {}

    for channelId in channels:
        channel = await _resolve(guild, channelId)
        if channel is None:
            failed.append(channelId)
            continue

        current = channel.overwrites_for(role)
        if locked:
            restore[str(channelId)] = current.send_messages

        try:
            await channel.set_permissions(
                role,
                overwrite=next_overwrite(current, locked, previous.get(str(channelId))),
                reason=reason,
            )
            changed += 1
        except discord.Forbidden:
            logging.warning(f"[Sessions] no permission to lock {channelId} in {guild.id}")
            failed.append(channelId)
        except Exception as error:
            logging.warning(f"[Sessions] could not lock {channelId} in {guild.id}: {error}")
            failed.append(channelId)

    try:
        if locked:
            await bot.settings.db.update_one(
                {"_id": guild.id},
                {"$set": {"sessions.channel_locks.previous": restore}},
            )
        else:
            await bot.settings.db.update_one(
                {"_id": guild.id},
                {"$unset": {"sessions.channel_locks.previous": ""}},
            )
    except Exception as error:
        logging.warning(f"[Sessions] could not store lock state in {guild.id}: {error}")

    return changed, failed
