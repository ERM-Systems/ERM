import asyncio
import base64
import datetime
import json
import logging
import re
import typing

import aiohttp
import discord
import discord.http
import pytz
import requests
from bson import ObjectId
from decouple import config
import roblox.users
from discord import Embed, InteractionResponse, Webhook
from discord.ext import commands
from fuzzywuzzy import fuzz
from pymongo.errors import DuplicateKeyError
from snowflake import SnowflakeGenerator
from zuid import ZUID

import utils.prc_api as prc_api
from utils.constants import BLANK_COLOR, RED_COLOR
from utils.prc_api import ServerStatus, Player


class ArgumentMockingInstance:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


tokenGenerator = ZUID(
    prefix="",
    length=64,
    timestamped=True,
    charset="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_",
)

generator = SnowflakeGenerator(192)
error_gen = ZUID(prefix="error_", length=10)
system_code_gen = ZUID(prefix="erm-systems-", length=7)


def removesuffix(input_string: str, suffix: str):
    if suffix and input_string.endswith(suffix):
        return input_string[: -len(suffix)]
    return input_string


def get_guild_icon(
    bot: typing.Union[commands.Bot, commands.AutoShardedBot], guild: discord.Guild
):
    if guild.icon is None:
        return bot.user.display_avatar.url
    else:
        return guild.icon.url


async def generalised_interaction_check_failure(
    responder: InteractionResponse | Webhook | typing.Callable,
):
    if isinstance(responder, typing.Callable):
        responder = responder()

    if isinstance(responder, InteractionResponse):
        await responder.send_message(
            embed=discord.Embed(
                title="Not Permitted",
                description="You are not permitted to interact with these buttons.",
                color=BLANK_COLOR,
            ),
            ephemeral=True,
        )
    else:
        await responder.send(
            embed=discord.Embed(
                title="Not Permitted",
                description="You are not permitted to interact with these buttons.",
                color=BLANK_COLOR,
            )
        )


async def has_whitelabel(bot, guild_id: int) -> bool:
    item = await bot.whitelabel.db.find_one({"GuildID": str(guild_id)})
    if item:
        guild = bot.get_guild(guild_id)
        token = item.get("Token")
        b64_userid = token.split(".")[0]
        user_id = base64.b64decode(b64_userid + "==").decode("utf-8")
        member = guild.get_member(int(user_id))
        if not member:
            try:
                member = await guild.fetch_member(int(user_id))
            except discord.NotFound:
                return False
        return True
    return False

async def get_roblox_by_username(user: str, bot, ctx: commands.Context):
    if "<@" in user:
        try:
            member_converted = await discord.ext.commands.MemberConverter().convert(
                ctx, user
            )
        except commands.BadArgument:
            return {"errors": ["Member could not be found in Discord."]}

        roblox_id = await bot.linking.get_roblox_id(member_converted.id)
        if not roblox_id:
            return {"errors": ["Member has not linked their Roblox account with ERM."]}
        return await bot.linking.get_roblox_info(roblox_id)

    client = roblox.Client()
    roblox_user = await client.get_user_by_username(user)
    if not roblox_user:
        return {"errors": ["Could not find user"]}
    else:
        return await bot.linking.get_roblox_info(roblox_user.id)


async def staff_check(bot_obj, guild, member):
    guild_settings = await bot_obj.settings.find_by_id(guild.id)
    member_role_ids = [r.id for r in member.roles]
    if guild_settings:
        if "role" in guild_settings["staff_management"].keys():
            if guild_settings["staff_management"]["role"] != "":
                if isinstance(guild_settings["staff_management"]["role"], list):
                    for role_id in guild_settings["staff_management"]["role"]:
                        if role_id in member_role_ids:
                            return True
                elif isinstance(guild_settings["staff_management"]["role"], int):
                    if guild_settings["staff_management"]["role"] in member_role_ids:
                        return True
    if (
        member.guild_permissions.manage_messages
        or member.guild_permissions.administrator
    ):
        return True
    return False


async def admin_check(bot_obj, guild, member):
    guild_settings = await bot_obj.settings.find_by_id(guild.id)
    member_role_ids = [r.id for r in member.roles]
    if guild_settings:
        if "admin_role" in guild_settings["staff_management"].keys():
            if guild_settings["staff_management"]["admin_role"] != "":
                if isinstance(guild_settings["staff_management"]["admin_role"], list):
                    for role_id in guild_settings["staff_management"]["admin_role"]:
                        if role_id in member_role_ids:
                            return True
                elif isinstance(guild_settings["staff_management"]["admin_role"], int):
                    if guild_settings["staff_management"]["admin_role"] in member_role_ids:
                        return True
        if "management_role" in guild_settings["staff_management"].keys():
            if guild_settings["staff_management"]["management_role"] != "":
                if isinstance(
                    guild_settings["staff_management"]["management_role"], list
                ):
                    for role_id in guild_settings["staff_management"]["management_role"]:
                        if role_id in member_role_ids:
                            return True
                elif isinstance(
                    guild_settings["staff_management"]["management_role"], int
                ):
                    if guild_settings["staff_management"]["management_role"] in member_role_ids:
                        return True
    if member.guild_permissions.administrator:
        return True
    return False


async def sync_ingame_permission(bot_obj, guild, member, guild_settings, grant: bool):
    permission_sync = guild_settings.get("ERLC", {}).get("permission_sync", {})
    if not permission_sync.get("enabled", False):
        return

    member_role_ids = [r.id for r in member.roles]
    is_admin = any(role_id in permission_sync.get("administrator_roles", []) for role_id in member_role_ids)
    is_mod = any(role_id in permission_sync.get("moderator_roles", []) for role_id in member_role_ids)

    if not is_admin and not is_mod:
        return

    roblox_id = await bot_obj.linking.get_roblox_id(member.id)
    if not roblox_id:
        logging.warning(f"Could not resolve Roblox account for {member.id} in {guild.id}, skipping permission sync")
        return

    if is_admin:
        command = f":admin {roblox_id}" if grant else f":unadmin {roblox_id}"
    else:
        command = f":mod {roblox_id}" if grant else f":unmod {roblox_id}"

    try:
        status_code, response = await bot_obj.prc_api.run_command(guild.id, command)
        if status_code != 200:
            logging.warning(f"Permission sync command '{command}' failed for {member.id} in {guild.id}: {status_code} {response}")
    except Exception as e:
        logging.warning(f"Failed to sync in-game permission for {member.id} in {guild.id}: {e}")


def time_converter(parameter: str) -> int:
    conversions = {
        ("s", "seconds", " seconds"): 1,
        ("m", "minute", "minutes", " minutes"): 60,
        ("h", "hour", "hours", " hours"): 60 * 60,
        ("d", "day", "days", " days"): 24 * 60 * 60,
        ("w", "week", " weeks"): 7 * 24 * 60 * 60,
    }

    for aliases, multiplier in conversions.items():
        parameter = parameter.strip()
        for alias in aliases:
            if parameter[(len(parameter) - len(alias)) :].lower() == alias.lower():
                alias_found = parameter[(len(parameter) - len(alias)) :]
                number = parameter.split(alias_found)[0]
                number = number.replace("-", "")  # prevent those negative times!
                if not number.strip()[-1].isdigit():
                    continue
                if int(number.strip()) * multiplier > 31536000:
                    raise OverflowError(
                        "Time value exceeds the maximum allowed duration of 365 days."
                    )
                return int(number.strip()) * multiplier

    raise ValueError("Invalid time format")


class GuildCheckFailure(commands.CheckFailure):
    pass


def require_settings(setting_lists: list[str]=[]):
    async def predicate(ctx: commands.Context):
        if ctx.guild is None:
            return True
        settings = await ctx.bot.settings.find_by_id(ctx.guild.id)
        if not settings or not all(setting in settings for setting in setting_lists):
            raise GuildCheckFailure()
        else:
            return True

    return commands.check(predicate)


async def update_ics(bot, ctx, channel, return_val: dict, ics_id: int):
    try:
        status: ServerStatus|None = await bot.prc_api.get_server_status(ctx.guild.id)
    except prc_api.ResponseFailure:
        status = None
    if not isinstance(status, ServerStatus):
        return return_val  # Invalid key

    try:
        queue: int = await bot.prc_api.get_server_queue(ctx.guild.id, minimal=True)
        players: list[Player] = await bot.prc_api.get_server_players(ctx.guild.id)
    except prc_api.ResponseFailure:
        return return_val  # fuck knows why
    mods: int = len(list(filter(lambda x: x.permission == "Server Moderator", players)))
    admins: int = len(
        list(filter(lambda x: x.permission == "Server Administrator", players))
    )
    total_staff: int = len(list(filter(lambda x: x.permission != "Normal", players)))

    if await bot.ics.db.count_documents({"_id": ics_id}):
        await bot.ics.db.update_one(
            {"_id": ics_id, "guild": ctx.guild.id},
            {
                "$set": {
                    "data": {
                        "join_code": status.join_key,
                        "players": status.current_players,
                        "max_players": status.max_players,
                        "queue": queue,
                        "staff": total_staff,
                        "admins": admins,
                        "mods": mods,
                    }
                }
            },
        )
    else:
        await bot.ics.insert(
            {
                "_id": ics_id,
                "guild": ctx.guild.id,
                "data": {
                    "join_code": status.join_key,
                    "players": status.current_players,
                    "max_players": status.max_players,
                    "queue": queue,
                    "staff": total_staff,
                    "admins": admins,
                    "mods": mods,
                },
                "associated_messages": [],
            }
        )

    return return_val


async def interpret_embed(bot, ctx, channel, embed: dict, ics_id: int):
    embed = discord.Embed.from_dict(embed)
    try:
        embed.title = await sub_vars(bot, ctx, channel, embed.title)
    except AttributeError:
        pass

    if str(var := await sub_vars(bot, ctx, channel, embed.author.name)) != "None":
        try:
            embed.set_author(name=await sub_vars(bot, ctx, channel, embed.author.name))
        except AttributeError:
            pass
    try:
        embed.description = await sub_vars(bot, ctx, channel, embed.description)
    except AttributeError:
        pass
    try:
        embed.set_footer(
            text=await sub_vars(bot, ctx, channel, embed.footer.text),
            icon_url=embed.footer.icon_url,
        )
    except AttributeError:
        pass
    for index, i in enumerate(embed.fields):
        embed.set_field_at(
            index,
            name=await sub_vars(bot, ctx, channel, i.name),
            value=await sub_vars(bot, ctx, channel, i.value),
        )

    if await bot.server_keys.db.count_documents({"_id": ctx.guild.id}) == 0:
        return embed

    return await update_ics(bot, ctx, channel, embed, ics_id)


async def interpret_content(bot, ctx, channel, content: str, ics_id):
    await update_ics(bot, ctx, channel, content, ics_id)
    return await sub_vars(bot, ctx, channel, content)


async def sub_vars(bot, ctx: commands.Context, channel, string, **kwargs):
    try:
        string = string.replace("{user}", ctx.author.mention)
        string = string.replace("{username}", ctx.author.name)
        string = string.replace("{display_name}", ctx.author.display_name)
        string = string.replace(
            "{time}", f"<t:{int(datetime.datetime.now().timestamp())}>"
        )
        string = string.replace("{server}", ctx.guild.name)
        string = string.replace("{channel}", channel.mention)
        string = string.replace("{prefix}", list(await get_prefix(bot, ctx))[-1])

        onduty: int = await bot.shift_management.shifts.db.count_documents(
            {"Guild": ctx.guild.id, "EndEpoch": 0}
        )

        string = string.replace("{onduty}", str(onduty))

        #### CUSTOM ER:LC VARS
        # Fetch whether they should even be allowed to use ER:LC vars
        if await bot.server_keys.db.count_documents({"_id": ctx.guild.id}) == 0:
            return string  # end here no point

        status: ServerStatus = await bot.prc_api.get_server_status(ctx.guild.id)
        if not isinstance(status, ServerStatus):
            return string  # Invalid key
        queue: int = await bot.prc_api.get_server_queue(ctx.guild.id, minimal=True)
        players: list[Player] = await bot.prc_api.get_server_players(ctx.guild.id)
        mods: int = len(
            list(filter(lambda x: x.permission == "Server Moderator", players))
        )
        admins: int = len(
            list(filter(lambda x: x.permission == "Server Administrator", players))
        )
        total_staff: int = len(
            list(filter(lambda x: x.permission != "Normal", players))
        )

        string = string.replace("{join_code}", status.join_key)
        string = string.replace("{players}", str(status.current_players))
        string = string.replace("{max_players}", str(status.max_players))
        string = string.replace("{queue}", str(queue))
        string = string.replace("{staff}", str(total_staff))
        string = string.replace("{admins}", str(admins))
        string = string.replace("{mods}", str(mods))

        return string
    except Exception:
        return string


def staff_rank(member, admin_roles, management_roles):
    member_role_ids = {role.id for role in member.roles}
    if member_role_ids & set(management_roles):
        return "Management"
    if member_role_ids & set(admin_roles):
        return "Administrator"
    return "Moderator"


def get_elapsed_time(document):
    from datamodels.ShiftManagement import ShiftItem

    if isinstance(document, ShiftItem):
        new_document = {
            "Breaks": [
                {"StartEpoch": item.start_epoch, "EndEpoch": item.end_epoch}
                for item in document.breaks
            ],
            "StartEpoch": document.start_epoch,
            "EndEpoch": document.end_epoch,
            "AddedTime": document.added_time,
            "RemovedTime": document.removed_time,
        }
        document = new_document
    total_seconds = 0
    break_seconds = 0
    for br in document["Breaks"]:
        if br["EndEpoch"] != 0:
            break_seconds += int(br["EndEpoch"]) - int(br["StartEpoch"])
        else:
            break_seconds += int(
                datetime.datetime.now(tz=pytz.UTC).timestamp() - int(br["StartEpoch"])
            )

    total_seconds += (
        int(
            (
                document["EndEpoch"]
                if document["EndEpoch"] != 0
                else datetime.datetime.now(tz=pytz.UTC).timestamp()
            )
        )
        - int(document["StartEpoch"])
        + document.get("AddedTime", 0)
        - document["RemovedTime"]
    ) - break_seconds

    return total_seconds


async def get_prefix(bot, message):
    if not message.guild:
        return commands.when_mentioned_or(">")(bot, message)

    try:
        prefix = await bot.settings.find_by_id(message.guild.id)
        prefix = (prefix or {})["customisation"]["prefix"]
    except KeyError:
        return discord.ext.commands.when_mentioned_or(">")(bot, message)

    return commands.when_mentioned_or(prefix)(bot, message)


async def invis_embed(ctx: commands.Context, content: str, **kwargs) -> discord.Message:
    msg = await ctx.send(
        content=f"<:ERMCheck:1111089850720976906>  **{ctx.author.name}**, {content}",
        **kwargs,
    )
    return msg


async def failure_embed(
    ctx: commands.Context, content: str, **kwargs
) -> discord.Message:
    msg = await ctx.send(
        content=f"<:ERMClose:1111101633389146223>  **{ctx.author.name}**, {content}",
        **kwargs,
    )
    return msg


async def new_failure_embed(
    ctx: commands.Context, title: str, description: str, **kwargs
) -> discord.Message:
    msg = await ctx.send(
        embed=discord.Embed(title=title, description=description, color=BLANK_COLOR)
    )
    return msg


async def get_player_avatar_url(player_id):
    url = f"https://thumbnails.roblox.com/v1/users/avatar?userIds={player_id}&size=180x180&format=Png&isCircular=false"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data["data"][0]["imageUrl"]


async def run_command(bot, guild_id, username, message):
    while True:
        command = f":pm {username} {message}"
        command_response = await bot.prc_api.run_command(guild_id, command)
        if command_response[0] == 200:
            logging.info(f"Sent PM to {username} in guild {guild_id}")
            break
        elif command_response[0] == 429:
            retry_after = int(command_response[1].get("Retry-After", 5))
            logging.warning(f"Rate limited. Retrying after {retry_after} seconds.")
            await asyncio.sleep(retry_after)
        else:
            logging.warning(f"Failed to send PM to {username} in guild {guild_id}")
            break


def is_whitelisted(vehicle_name, whitelisted_vehicle):
    vehicle_year_match = re.search(r"\d{4}$", vehicle_name)
    whitelisted_year_match = re.search(r"\d{4}$", whitelisted_vehicle)
    if vehicle_year_match and whitelisted_year_match:
        vehicle_year = vehicle_year_match.group()
        whitelisted_year = whitelisted_year_match.group()
        if vehicle_year != whitelisted_year:
            return False
        vehicle_name_base = vehicle_name[: vehicle_year_match.start()].strip()
        whitelisted_vehicle_base = whitelisted_vehicle[
            : whitelisted_year_match.start()
        ].strip()
        return (
            fuzz.ratio(vehicle_name_base.lower(), whitelisted_vehicle_base.lower()) > 80
        )
    return False


async def int_failure_embed(interaction, content, **kwargs):
    try:
        await interaction.response.send_message(
            content=f"<:ERMClose:1111101633389146223>  **{interaction.user.name}**, {content}",
            **kwargs,
        )
    except discord.InteractionResponded:
        await interaction.followup.send(
            content=f"<:ERMClose:1111101633389146223>  **{interaction.user.name}**, {content}",
            **kwargs,
        )


async def int_pending_embed(interaction, content, **kwargs):
    try:
        await interaction.response.send_message(
            content=f"<:ERMPending:1111097561588183121>  **{interaction.user.name}**, {content}",
            **kwargs,
        )
    except discord.InteractionResponded:
        await interaction.followup.send(
            content=f"<:ERMPending:1111097561588183121>  **{interaction.user.name}**, {content}",
            **kwargs,
        )


async def pending_embed(
    ctx: commands.Context, content: str, **kwargs
) -> discord.Message:
    msg = await ctx.send(
        content=f"<:ERMPending:1111097561588183121>  **{ctx.author.name}**, {content}",
        **kwargs,
    )
    return msg


async def int_invis_embed(interaction, content, **kwargs):
    try:
        await interaction.response.send_message(
            content=f"<:ERMCheck:1111089850720976906>  **{interaction.user.name}**, {content}",
            **kwargs,
        )
    except discord.InteractionResponded:
        await interaction.followup.send(
            content=f"<:ERMCheck:1111089850720976906>  **{interaction.user.name}**, {content}",
            **kwargs,
        )


async def coloured_embed(
    ctx: commands.Context, content: str, **kwargs
) -> discord.Message:
    embed = Embed(color=0xED4348, description=f"{content}")
    msg = await ctx.send(embed=embed, **kwargs)
    return msg


async def int_coloured_embed(interaction, content, **kwargs):
    embed = Embed(color=0xED4348, description=f"{content}")
    try:
        await interaction.response.send_message(embed=embed, **kwargs)
    except discord.InteractionResponded:
        await interaction.edit_original_response(embed=embed, **kwargs)


async def request_response(bot, ctx, question, **kwargs):
    await ctx.send(
        content=f"<:ERMPending:1111097561588183121>  **{ctx.author.name}**, {question}",
        **kwargs,
    )
    try:
        response = await bot.wait_for(
            "message",
            check=lambda message: message.author == ctx.author
            and message.guild.id == ctx.guild.id,
            timeout=300,
        )
    except asyncio.TimeoutError:
        raise Exception("No response")
    return response


def make_ordinal(n):
    """
    Convert an integer into its ordinal representation::

        make_ordinal(0)   => '0th'
        make_ordinal(3)   => '3rd'
        make_ordinal(122) => '122nd'
        make_ordinal(213) => '213th'
    """
    n = int(n)
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]
    return str(n) + suffix


async def fetch_get_channel(target, identifier):
    channel = target.get_channel(identifier)
    if not channel:
        try:
            channel = await target.fetch_channel(identifier)
        except discord.NotFound:
            channel = None
        except discord.HTTPException as e:
            channel = None
    return channel


async def get_discord_by_roblox(bot, username):
    api_url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": True}
    async with aiohttp.ClientSession() as session:
        async with session.post(api_url, json=payload) as response:
            if response.status != 200:
                return None
            data = (await response.json()).get("data") or []

    if not data:
        return None
    return await bot.linking.get_discord_id(data[0]["id"])


async def log_command_usage(bot, guild, member, command_name):
    settings = await bot.settings.find_by_id(guild.id)
    if not settings:
        return
    if not settings.get("staff_management", {}).get("erm_log_channel"):
        return
    try:
        log_channel_id = settings.get("staff_management", {}).get("erm_log_channel")
    except (ValueError, TypeError):
        return
    log_channel = guild.get_channel(log_channel_id)
    if log_channel is None:
        return
    if not log_channel.permissions_for(guild.me).send_messages:
        return
    embed = discord.Embed(
        title="ERM Command Log",
        description=f"Command `{command_name}` used by {member.mention}",
        color=BLANK_COLOR,
    )
    embed.set_footer(text=f"User ID: {member.id}")
    embed.set_author(name=member.name, icon_url=member.display_avatar.url)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    await log_channel.send(embed=embed)


async def config_change_log(bot, guild, member, data):
    setting = await bot.settings.find_by_id(guild.id)
    if not setting:
        return
    if not setting.get("staff_management", {}).get("erm_log_channel"):
        return
    try:
        log_channel_id = setting.get("staff_management", {}).get("erm_log_channel")
    except (ValueError, TypeError) as e:
        return
    log_channel = guild.get_channel(log_channel_id)
    if log_channel is None:
        return
    if not log_channel.permissions_for(guild.me).send_messages:
        return
    embed = discord.Embed(
        title="ERM Config Change Log",
        description=f"Configuration change made by {member.mention}",
        color=BLANK_COLOR,
    ).add_field(name="Configuration Change", value=data)
    embed.set_footer(text=f"User ID: {member.id}")
    embed.set_author(name=member.name, icon_url=member.display_avatar.url)
    embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
    await log_channel.send(embed=embed)


async def secure_logging(
    bot,
    guild_id,
    author_id,
    interpret_type: typing.Literal["Message", "Hint", "Command"],
    command_string: str,
    attempted: bool = False,
):
    settings = await bot.settings.find_by_id(guild_id)
    channel = ((settings or {}).get("game_security", {}) or {}).get("channel")
    try:
        channel = await (await bot.fetch_guild(guild_id)).fetch_channel(channel)
    except discord.HTTPException:
        channel = None
    if channel is None:
        return

    roblox_id = await bot.linking.get_roblox_id(author_id)
    if roblox_id:
        roblox_name = (await bot.linking.get_roblox_info(roblox_id)).get(
            "name", "Unknown"
        )
        actor = (
            f"[{roblox_name}:{roblox_id}]"
            f"(https://roblox.com/users/{roblox_id}/profile)"
        )
    else:
        actor = f"<@{author_id}> (no linked Roblox account)"

    if interpret_type == "Message":
        formatted_command = f"`:m {command_string}`"
    elif interpret_type == "Hint":
        formatted_command = f"`:h {command_string}`"
    else:
        formatted_command = f"`{command_string}`"

    server_status: ServerStatus = await bot.prc_api.get_server_status(guild_id)
    if not attempted:
        embed=discord.Embed(
            title="Remote Server Logs",
            description=f"{actor} used a command: {formatted_command}",
            color=RED_COLOR,
        )
    else:
        embed=discord.Embed(
            title="Attempted Command Execution",
            description=f"{actor} attempted to use the command: {formatted_command}",
            color=RED_COLOR,
        )
    embed.set_footer(
        text=f"Private Server: {server_status.join_key}"
    )
    await channel.send(embed=embed)


def render_session_message(template: str, replacements: dict) -> dict:
    def substitute(match):
        if match.group() not in replacements:
            return match.group()

        return json.dumps(str(replacements[match.group()]))[1:-1]

    try:
        return json.loads(re.sub(r"\{[\w.]+\}", substitute, template))
    except json.JSONDecodeError:
        raise ValueError("That message could not be rendered, please configure it again.")


async def get_session_status(bot, guild_id: int):
    try:
        return await bot.prc_api.get_server_status(guild_id)
    except Exception:
        return None


async def get_session_configuration(bot, guild_id: int, message_type: str) -> dict:
    settings = await bot.settings.find(guild_id)
    if not settings or not settings.get("sessions"):
        raise ValueError("Sessions have not been configured for this server.")

    sessions = settings["sessions"]
    if not sessions.get("channel_id"):
        raise ValueError("There is no session channel configured.")
    if not sessions.get(message_type):
        raise ValueError(f"There has been no {message_type} message configured.")

    return sessions


async def create_session_vote(
    bot, guild_id: int, user_id: int, required_votes: int | None = None, staff_only: bool = False
) -> int:
    message_type = "staff_vote" if staff_only else "vote"
    sessions = await get_session_configuration(bot, guild_id, message_type)
    if await bot.sessions.find(guild_id):
        raise ValueError("There is already an active session.")

    try:
        required = int(required_votes or sessions.get("required_votes_default") or 5)
    except (TypeError, ValueError):
        required = 5

    session = {
        "_id": guild_id,
        "user": user_id,
        "voted_users": [],
        "started": False,
        "staff_only": staff_only,
        "votes": 0,
        "required_votes": required,
        "created_at": int(datetime.datetime.now().timestamp()),
        "analytics": {"max_players": 0, "player_counts": []},
    }

    dynamic = sessions.get("dynamic_button")
    payload = render_session_message(
        sessions[message_type],
        {
            "{user}": f"<@{user_id}>",
            "{vote_button_name}": f"0/{required}"
            if dynamic
            else sessions.get("vote_button_label", "Vote"),
            "{required_members}": str(required),
        },
    )
    if dynamic:
        button = next(
            (
                component
                for row in payload.get("components") or []
                for component in row.get("components") or []
                if component.get("custom_id") == f"vote_button:{guild_id}"
            ),
            None,
        )
        if not button:
            raise ValueError("The vote message needs a vote button for the dynamic button to work.")
        button["label"] = f"0/{required}"

    message = await bot.http.send_message(
        sessions["channel_id"],
        params=discord.http.MultipartParameters(payload=payload, multipart=None, files=None),
    )
    session["vote_message"] = message["id"]
    await bot.sessions.insert(session)

    return sessions["channel_id"]


async def send_session_boost(bot, guild_id: int, user_id: int) -> int:
    sessions = await get_session_configuration(bot, guild_id, "boost")
    session = await bot.sessions.find(guild_id)
    if not session or not session.get("started"):
        raise ValueError("There is no session running right now.")

    info = await get_session_status(bot, guild_id)
    payload = render_session_message(
        sessions["boost"],
        {
            "{user}": f"<@{user_id}>",
            "{erlc.name}": str(info.name) if info else "{erlc.name}",
            "{erlc.code}": str(info.join_key) if info else "{erlc.code}",
            "{erlc.players}": str(info.current_players) if info else "{erlc.players}",
        },
    )

    await bot.http.send_message(
        sessions["channel_id"],
        params=discord.http.MultipartParameters(payload=payload, multipart=None, files=None),
    )

    return sessions["channel_id"]


async def send_session_full(bot, guild_id: int, info) -> bool:
    try:
        sessions = await get_session_configuration(bot, guild_id, "full")
    except ValueError:
        return False

    claim = await bot.sessions.db.update_one(
        {"_id": guild_id, "full_announced": {"$ne": True}},
        {"$set": {"full_announced": True}},
    )
    if not claim.modified_count:
        return False

    try:
        payload = render_session_message(
            sessions["full"],
            {
                "{erlc.name}": str(info.name) if info else "{erlc.name}",
                "{erlc.code}": str(info.join_key) if info else "{erlc.code}",
                "{erlc.players}": str(info.current_players) if info else "{erlc.players}",
                "{erlc.max_players}": str(info.max_players) if info else "{erlc.max_players}",
            },
        )

        await bot.http.send_message(
            sessions["channel_id"],
            params=discord.http.MultipartParameters(payload=payload, multipart=None, files=None),
        )
    except Exception:
        await bot.sessions.db.update_one(
            {"_id": guild_id}, {"$unset": {"full_announced": ""}}
        )
        raise

    return True


async def disable_vote_button(bot, guild_id: int, sessions: dict, session: dict):
    if not session.get("vote_message"):
        return

    try:
        channel = bot.get_channel(sessions["channel_id"]) or await bot.fetch_channel(
            sessions["channel_id"]
        )
        message = await channel.fetch_message(session["vote_message"])

        view = discord.ui.View.from_message(message)
        for child in view.walk_children():
            if isinstance(child, discord.ui.Button) and child.custom_id == f"vote_button:{guild_id}":
                child.disabled = True
                await message.edit(view=view)
                return
    except Exception as error:
        logging.warning(f"Could not disable the vote button in {guild_id}: {error}")


async def release_session_start(bot, guild_id: int, previous: dict | None) -> None:
    if previous is None:
        return await bot.sessions.delete(guild_id)

    await bot.sessions.db.update_one(
        {"_id": guild_id},
        {
            "$set": {"user": previous.get("user"), "started": False},
            "$unset": {"started_by": "", "started_at": ""},
        },
    )


async def start_session(bot, guild_id: int, user_id: int) -> int | None:
    try:
        sessions = await get_session_configuration(bot, guild_id, "start")
    except ValueError:
        sessions = None

    now = int(datetime.datetime.now().timestamp())

    try:
        previous = await bot.sessions.db.find_one_and_update(
            {"_id": guild_id, "started": {"$ne": True}},
            {
                "$set": {
                    "user": f"<@{user_id}>",
                    "started": True,
                    "started_by": user_id,
                    "started_at": now,
                },
                "$setOnInsert": {
                    "voted_users": [],
                    "votes": 0,
                    "required_votes": 0,
                    "created_at": now,
                    "analytics": {"max_players": 0, "player_counts": []},
                },
            },
            upsert=True,
        )
    except DuplicateKeyError:
        raise ValueError("There is already an active session.")

    session = await bot.sessions.find(guild_id)

    if sessions:
        try:
            info = await get_session_status(bot, guild_id)
            if "{erlc.players}" in sessions["start"]:
                session["dynamic"] = True

            payload = render_session_message(
                sessions["start"],
                {
                    "{user}": f"<@{user_id}>",
                    "{user_mentions}": " | ".join([f"<@{user}>" for user in session["voted_users"]]),
                    "{erlc.name}": info.name if info else "{erlc.name}",
                    "{erlc.code}": info.join_key if info else "{erlc.code}",
                    "{erlc.players}": str(info.current_players) if info else "{erlc.players}",
                },
            )

            message = await bot.http.send_message(
                sessions["channel_id"],
                params=discord.http.MultipartParameters(payload=payload, multipart=None, files=None),
            )
        except Exception:
            await release_session_start(bot, guild_id, previous)
            raise

        session["message"], session["channel"] = message["id"], sessions["channel_id"]
        await disable_vote_button(bot, guild_id, sessions, session)

    await bot.sessions.update(session)

    return sessions["channel_id"] if sessions else None


async def monitor_session_logs(bot, guild_id: int, started_at: int, ended_at: int) -> dict:
    counts = {"commands": 0, "kills": 0, "joins": 0}

    async def within(fetch, key):
        try:
            entries = await fetch(guild_id)
        except Exception:
            return
        counts[key] = len(
            [entry for entry in entries if started_at <= entry.timestamp <= ended_at]
        )

    await within(bot.prc_api.fetch_server_logs, "commands")
    await within(bot.prc_api.fetch_kill_logs, "kills")
    await within(bot.prc_api.fetch_player_logs, "joins")

    return counts


async def end_session(bot, guild_id: int, user_id: int) -> int | None:
    try:
        sessions = await get_session_configuration(bot, guild_id, "shutdown")
    except ValueError:
        sessions = None

    session = await bot.sessions.find(guild_id)
    if not session:
        raise ValueError("There is no active session.")

    if sessions:
        info = await get_session_status(bot, guild_id)
        payload = render_session_message(
            sessions["shutdown"],
            {
                "{user}": f"<@{user_id}>",
                "{erlc.name}": info.name if info else "{erlc.name}",
                "{erlc.code}": info.join_key if info else "{erlc.code}",
                "{erlc.max_players}": str(session.get("analytics", {}).get("max_players", 0)),
            },
        )

        await bot.http.send_message(
            sessions["channel_id"],
            params=discord.http.MultipartParameters(payload=payload, multipart=None, files=None),
        )

    ended_at = int(datetime.datetime.now().timestamp())
    started_at = session.get("started_at") or session.get("created_at") or ended_at
    analytics = session.get("analytics", {})

    await bot.session_history.insert(
        {
            "_id": ObjectId(),
            "guild_id": guild_id,
            "started_by": session.get("started_by") or session.get("user"),
            "ended_by": user_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "votes": session.get("votes", 0),
            "voted_users": session.get("voted_users", []),
            "max_players": analytics.get("max_players", 0),
            "player_counts": analytics.get("player_counts", []),
            "logs": await monitor_session_logs(bot, guild_id, started_at, ended_at),
        }
    )
    await bot.sessions.delete(session["_id"])

    return sessions["channel_id"] if sessions else None