import logging

import discord

from utils.utils import secure_logging

logger = logging.getLogger(__name__)

ACTIONS = (
    "send_message",
    "ping_role",
    "move_to_voice",
    "pm_player",
    "ingame_message",
    "ingame_hint",
)

INGAME_ACTIONS = ("pm_player", "ingame_message", "ingame_hint")

PERMISSION_LEVELS = ("staff", "admin", "management", "roles")


def normalise_trigger(value) -> str:
    return str(value or "").strip().lstrip(":;!/").strip().lower()


def snowflake(value) -> int:
    text = str(value or "").strip()
    if ":" in text:
        text = text.rsplit(":", 1)[-1]

    try:
        return int(text)
    except ValueError:
        return 0


def get_configuration(settings: dict) -> dict:
    return (settings or {}).get("ERLC", {}).get("ingame_commands", {}) or {}


def find_command(settings: dict, command: str):
    configuration = get_configuration(settings)
    trigger = normalise_trigger(command)
    if not trigger:
        return None

    for entry in configuration.get("commands") or []:
        if normalise_trigger(entry.get("trigger")) == trigger:
            return entry

    return None


def voice_target(entry: dict, argument: str) -> int:
    argument = argument.strip().lower()

    for target in entry.get("voice_channels") or []:
        if str(target.get("argument", "")).strip().lower() == argument:
            return snowflake(target.get("channel"))

    return snowflake(entry.get("channel"))


def parse_voice_argument(argument: str):
    parts = str(argument or "").split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return "", parts[0]

    return parts[0], parts[-1]


async def linked_member(bot, guild: discord.Guild, username: str):
    try:
        return await bot.accounts.roblox_to_discord(guild, username)
    except Exception:
        logger.warning("Could not resolve %s in guild %s", username, guild.id)
        return None


async def resolve_caller(bot, guild: discord.Guild, roblox_user_id: int):
    if not roblox_user_id:
        return None, ""

    username = ""
    try:
        roblox_user = await bot.roblox.get_user(roblox_user_id)
        username = roblox_user.name
    except Exception:
        logger.warning("Could not resolve Roblox user %s", roblox_user_id)

    member = None
    try:
        for discord_id in await bot.linking.get_discord_ids(roblox_user_id):
            member = guild.get_member(discord_id)
            if member:
                break
            try:
                member = await guild.fetch_member(discord_id)
                break
            except discord.NotFound:
                member = None
    except Exception:
        member = None

    return member, username


async def has_permission(bot, guild: discord.Guild, member, entry: dict) -> bool:
    permission = entry.get("permission") or {}
    if not permission.get("enabled"):
        return True

    if not member:
        return False

    level = permission.get("level")
    if level not in PERMISSION_LEVELS:
        level = "staff"

    if level == "roles":
        allowed = {snowflake(role) for role in permission.get("roles") or []}
        return any(role.id in allowed for role in member.roles)

    from erm import admin_check, management_check, staff_check

    checks = {
        "staff": staff_check,
        "admin": admin_check,
        "management": management_check,
    }

    try:
        return await checks[level](bot, guild, member)
    except Exception:
        logger.warning("Could not check %s permissions in guild %s", level, guild.id)
        return False


def fill(template: str, player: str, argument: str) -> str:
    return (
        str(template or "")
        .replace("{player}", player or "Unknown")
        .replace("{user}", player or "Unknown")
        .replace("{argument}", str(argument or ""))
        .strip()
    )


async def run_ingame_action(
        bot, guild: discord.Guild, entry: dict, member, player: str, argument: str
) -> bool:
    message = " ".join(fill(entry.get("message"), player, argument).split())
    if not message:
        return False

    action = entry.get("action")
    if action == "pm_player":
        if entry.get("pm_target") == "argument":
            target = next(iter(str(argument or "").split()), "")
        else:
            target = player
        if not target:
            return False
        command = f":pm {target} {message}"
        interpret_type, logged = "Command", command
    elif action == "ingame_message":
        command = f":m {message}"
        interpret_type, logged = "Message", message
    else:
        command = f":h {message}"
        interpret_type, logged = "Hint", message

    status_code = 0
    try:
        status_code, _ = await bot.prc_api.run_command(guild.id, command)
    except Exception:
        logger.warning("Could not run in-game command in guild %s", guild.id)

    executed = status_code == 200

    if member:
        try:
            await secure_logging(
                bot, guild.id, member.id, interpret_type, logged, not executed
            )
        except Exception:
            logger.warning("Could not log in-game command in guild %s", guild.id)

    return executed


def sendable(guild: discord.Guild, channel_id: int):
    channel = guild.get_channel(channel_id)
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return None
    if not channel.permissions_for(guild.me).send_messages:
        return None

    return channel


async def execute_ingame_command(
        bot,
        guild: discord.Guild,
        settings: dict,
        command: str,
        argument: str,
        roblox_user_id,
) -> bool:
    entry = find_command(settings, command)
    if not entry:
        return False

    action = entry.get("action")
    if action not in ACTIONS:
        return False

    member, username = await resolve_caller(bot, guild, snowflake(roblox_user_id))
    player = username or (member.display_name if member else "")

    if not await has_permission(bot, guild, member, entry):
        return False

    if action in INGAME_ACTIONS:
        return await run_ingame_action(bot, guild, entry, member, player, argument)

    if action == "move_to_voice":
        target_name, key = parse_voice_argument(argument)
        target = await linked_member(bot, guild, target_name) if target_name else member
        if not target or not target.voice:
            return False

        channel = guild.get_channel(voice_target(entry, key))
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            return False
        if not channel.permissions_for(guild.me).move_members:
            return False

        try:
            await target.move_to(channel)
        except discord.HTTPException:
            logger.warning("Could not move %s in guild %s", target.id, guild.id)
            return False

        return True

    channel = sendable(guild, snowflake(entry.get("channel")))
    if not channel:
        return False

    content = fill(entry.get("message"), player, argument)
    roles = []

    if action == "ping_role":
        roles = [
            discord.Object(id=role_id)
            for role_id in (snowflake(role) for role in entry.get("roles") or [])
            if role_id
        ]
        mentions = " ".join(f"<@&{role.id}>" for role in roles)
        content = f"{mentions} {content}".strip()

    if not content:
        return False

    try:
        await channel.send(
            content[:2000],
            allowed_mentions=discord.AllowedMentions(
                everyone=False, users=False, roles=roles
            ),
        )
    except discord.HTTPException:
        logger.warning("Could not send in-game command output to %s", channel.id)
        return False

    return True
