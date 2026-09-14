import copy
import datetime
import json
import logging

import discord

logger = logging.getLogger(__name__)

NICKNAME_LIMIT = 32
VERIFY_BUTTON_ID = "erm_verify"
COMPONENTS_V2_FLAG = 1 << 15
MAX_ROWS = 5
MAX_ROW_BUTTONS = 5
ROBLOX_INVALID_USER = 3


class RobloxUnavailable(Exception):
    pass


class Cooldown:
    def __init__(self, seconds, limit=5000):
        self.seconds = seconds
        self.limit = limit
        self.used = {}

    def remaining(self, key, now):
        last = self.used.get(key)
        if last is not None and now - last < self.seconds:
            return self.seconds - (now - last)

        if len(self.used) >= self.limit:
            self.used = {
                entry: stamp for entry, stamp in self.used.items() if now - stamp < self.seconds
            }

        self.used[key] = now
        return 0


def get_configuration(settings):
    if not isinstance(settings, dict):
        return None

    verification = settings.get("verification")
    if not isinstance(verification, dict) or not verification.get("enabled"):
        return None

    return verification


def role_ids(value):
    if not isinstance(value, list):
        return []

    ids = []
    for entry in value:
        try:
            ids.append(int(entry))
        except (TypeError, ValueError):
            continue
    return ids


def account_created(info):
    if not isinstance(info, dict):
        return None

    created = info.get("created")
    if not isinstance(created, str) or not created:
        return None

    try:
        return datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        return None


def account_age_days(info, now=None):
    created = account_created(info)
    if created is None:
        return None

    now = now or datetime.datetime.now(tz=datetime.timezone.utc)
    return (now - created).days


def meets_requirements(info, verification, now=None):
    minimum = verification.get("min_account_age") or 0
    try:
        minimum = int(minimum)
    except (TypeError, ValueError):
        minimum = 0

    if minimum <= 0:
        return True, ""

    age = account_age_days(info, now)
    if age is None:
        return False, "Your Roblox account age could not be checked, try again shortly."

    if age < minimum:
        return False, f"Your Roblox account has to be at least {minimum} days old to verify here."

    return True, ""


def guild_replacements(guild):
    return {
        "{guild.name}": str(guild.name),
        "{guild.members}": str(guild.member_count or 0),
    }


def replacements(member, info, guild):
    return {
        "{roblox.username}": str(info.get("name") or ""),
        "{roblox.display_name}": str(info.get("displayName") or info.get("name") or ""),
        "{roblox.id}": str(info.get("id") or ""),
        "{member.mention}": f"<@{member.id}>",
        "{member.name}": str(member.name),
        "{member.id}": str(member.id),
        **guild_replacements(guild),
    }


def template_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and value:
        return json.dumps(value)
    return ""


def render(template, values):
    from utils.utils import render_session_message

    text = template_text(template)
    if not text:
        raise ValueError("That message is empty.")

    payload = render_session_message(text, values)
    if not isinstance(payload, dict):
        raise ValueError("That message could not be read, open it and save it again.")
    return payload


def add_verify_button(payload):
    payload = copy.deepcopy(payload)
    components = payload.get("components") or []
    rows = [row for row in components if isinstance(row, dict) and row.get("type") == 1]

    for row in rows:
        for button in row.get("components") or []:
            if isinstance(button, dict) and button.get("custom_id") == VERIFY_BUTTON_ID:
                return payload, ""

    if payload.get("flags", 0) & COMPONENTS_V2_FLAG:
        return payload, "This message layout needs its own Verify button, add one in the dashboard."

    button = {"type": 2, "style": 3, "label": "Verify", "custom_id": VERIFY_BUTTON_ID}

    for row in rows:
        buttons = row.get("components") or []
        if len(buttons) < MAX_ROW_BUTTONS and all(
            isinstance(entry, dict) and entry.get("type") == 2 for entry in buttons
        ):
            row["components"] = buttons + [button]
            return payload, ""

    if len(components) < MAX_ROWS:
        payload["components"] = components + [{"type": 1, "components": [button]}]
        return payload, ""

    return payload, "Your buttons are full, remove one or set one to Verify in the dashboard."


def can_manage_role(guild, role):
    if role is None or role.is_default() or role.managed:
        return False
    return guild.me.top_role > role


def can_rename(guild, member):
    if member.id == guild.owner_id:
        return False
    return guild.me.top_role > member.top_role


async def resolve_account(bot, discord_id):
    roblox_id = await bot.linking.get_roblox_id(discord_id)
    if not roblox_id:
        return None

    info = await bot.linking.get_roblox_info(roblox_id)
    if not isinstance(info, dict):
        raise RobloxUnavailable()

    errors = info.get("errors")
    if errors:
        codes = {entry.get("code") for entry in errors if isinstance(entry, dict)}
        if ROBLOX_INVALID_USER in codes:
            return None
        raise RobloxUnavailable()

    if not info.get("name"):
        raise RobloxUnavailable()

    info.setdefault("id", roblox_id)
    return info


async def apply(bot, member, info, verification):
    guild = member.guild
    skipped = []

    wanted = role_ids(verification.get("verified_roles"))
    unwanted = role_ids(verification.get("unverified_roles"))

    add = []
    for role_id in wanted:
        role = guild.get_role(role_id)
        if role is None:
            continue
        if not can_manage_role(guild, role):
            skipped.append(role.name)
            continue
        if role not in member.roles:
            add.append(role)

    remove = []
    for role_id in unwanted:
        if role_id in wanted:
            continue
        role = guild.get_role(role_id)
        if role is None:
            continue
        if not can_manage_role(guild, role):
            skipped.append(role.name)
            continue
        if role in member.roles:
            remove.append(role)

    if add:
        try:
            await member.add_roles(*add, reason="ERM verification")
        except discord.HTTPException as exception:
            logger.error("[Verification] could not add roles in %s: %s", guild.id, exception)
            skipped.extend(role.name for role in add)

    if remove:
        try:
            await member.remove_roles(*remove, reason="ERM verification")
        except discord.HTTPException as exception:
            logger.error("[Verification] could not remove roles in %s: %s", guild.id, exception)
            skipped.extend(role.name for role in remove)

    renamed = False
    nickname = render_nickname(
        verification.get("nickname") or "", replacements(member, info, guild)
    )
    if nickname:
        if not can_rename(guild, member):
            skipped.append("nickname")
        else:
            try:
                await member.edit(nick=nickname, reason="ERM verification")
                renamed = True
            except discord.HTTPException as exception:
                logger.error(
                    "[Verification] could not rename %s in %s: %s", member.id, guild.id, exception
                )
                skipped.append("nickname")

    return {"added": add, "removed": remove, "renamed": renamed, "skipped": skipped}


def render_nickname(template, values):
    if not template:
        return ""

    rendered = template
    for token, value in values.items():
        rendered = rendered.replace(token, value)

    return rendered[:NICKNAME_LIMIT]


async def post_message(bot, guild):
    config = get_configuration(await bot.settings.find_by_id(guild.id))
    if not config:
        raise ValueError("Turn verification on and save it before posting the message.")

    try:
        channel_id = int(config.get("channel_id") or 0)
    except (TypeError, ValueError):
        channel_id = 0

    channel = guild.get_channel(channel_id) if channel_id else None
    if channel is None:
        raise ValueError("Pick a verify channel that still exists, then save.")
    if not isinstance(channel, discord.abc.Messageable):
        raise ValueError("That verify channel cannot hold messages, pick a text channel.")

    if not template_text(config.get("message")):
        raise ValueError("Your verify message is empty, write one and save it first.")

    payload, problem = add_verify_button(render(config.get("message"), guild_replacements(guild)))
    if problem:
        raise ValueError(problem)

    permissions = channel.permissions_for(guild.me)
    if not permissions.view_channel or not permissions.send_messages:
        raise ValueError(f"ERM cannot send messages in #{channel.name}.")
    if payload.get("embeds") and not permissions.embed_links:
        raise ValueError(f"ERM needs Embed Links in #{channel.name} to post that message.")

    try:
        await bot.http.send_message(
            channel.id,
            params=discord.http.MultipartParameters(payload=payload, multipart=None, files=None),
        )
    except discord.HTTPException as exception:
        logger.warning("[Verification] Discord refused the message in %s: %s", guild.id, exception)
        raise ValueError("Discord refused that message, check it in the dashboard and try again.")

    return channel.id
