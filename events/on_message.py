import copy
import datetime
import logging
import string

import discord
import num2words
import roblox
from discord.ext import commands
from reactionmenu import Page, ViewButton, ViewMenu, ViewSelect

from erm import Bot
from utils.prc_api import Player
from utils.constants import BLANK_COLOR, GREEN_COLOR
from utils.utils import generator
from utils.utils import interpret_content, interpret_embed
from menus import CustomSelectMenu, GameSecurityActions
from utils.timestamp import td_format
from utils.utils import get_guild_icon, get_prefix, invis_embed


antipingCooldownSeconds = 45
antipingLastWarned = {}


def antiping_should_warn(guildId, userId):
    now = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
    key = (guildId, userId)
    last = antipingLastWarned.get(key, 0)
    if now - last < antipingCooldownSeconds:
        return False

    antipingLastWarned[key] = now
    if len(antipingLastWarned) > 10000:
        cutoff = now - antipingCooldownSeconds
        for stale in [k for k, v in antipingLastWarned.items() if v < cutoff]:
            antipingLastWarned.pop(stale, None)
    return True


antipingStrikes = {}


def antiping_settings(dataset):
    settings = dataset.get("antiping") if isinstance(dataset, dict) else None
    return settings if isinstance(settings, dict) else {}


def antiping_channel_id(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed or None


def antiping_channel_set(rule):
    raw = rule.get("ignored_channels") or []
    if not isinstance(raw, list):
        raw = [raw]
    return {parsed for parsed in (antiping_channel_id(item) for item in raw) if parsed}


def antiping_is_ignored(rule, channel):
    ignored = antiping_channel_set(rule)
    if not ignored:
        return False

    parent = getattr(channel, "parent_id", None)
    category = getattr(channel, "category_id", None)
    return bool({channel.id, parent, category} & ignored)


def antiping_role_list(guild, raw):
    if raw is None:
        return []
    if not isinstance(raw, list):
        raw = [raw]

    roles = []
    for item in raw:
        try:
            role = guild.get_role(int(item))
        except (TypeError, ValueError):
            role = None
        if role is not None:
            roles.append(role)
    return roles


def antiping_rules(dataset):
    settings = antiping_settings(dataset)
    stored = settings.get("rules")

    if isinstance(stored, list) and stored:
        return [
            rule
            for rule in stored
            if isinstance(rule, dict) and rule.get("enabled") is not False
        ]

    if not settings.get("role"):
        return []

    return [
        {
            "name": "Anti-Ping",
            "role": settings.get("role"),
            "bypass_role": settings.get("bypass_role"),
            "ignored_channels": settings.get("ignored_channels"),
            "use_hierarchy": settings.get("use_hierarchy") in [True, None],
            "log_channel": settings.get("log_channel"),
            "escalation": settings.get("escalation") or {},
            "shift": settings.get("shift") or {},
        }
    ]


def antiping_number(value, fallback, low):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed >= low else fallback


async def antiping_on_duty(bot, guild_id, user_id, shift):
    active = await bot.shift_management.shifts.db.find_one(
        {"UserID": user_id, "Guild": guild_id, "EndEpoch": 0}
    )

    if active:
        if shift.get("break_off_duty") is True:
            breaks = active.get("Breaks") or []
            if any(entry.get("EndEpoch") == 0 for entry in breaks):
                return False
        return True

    grace = antiping_number(shift.get("grace"), 0, 0)
    if grace <= 0:
        return False

    cutoff = datetime.datetime.now(tz=datetime.timezone.utc).timestamp() - grace
    recent = await bot.shift_management.shifts.db.find_one(
        {"UserID": user_id, "Guild": guild_id, "EndEpoch": {"$gte": cutoff}}
    )
    return recent is not None


async def antiping_protects(bot, rule, guild_id, member):
    shift = rule.get("shift") or {}
    mode = shift.get("mode") or "always"
    if mode not in ("off_duty", "on_duty"):
        return True

    try:
        on_duty = await antiping_on_duty(bot, guild_id, member.id, shift)
    except Exception as exception:
        logging.error(
            "[Anti-Ping] shift lookup failed for %s in %s: %s", member.id, guild_id, exception
        )
        return True

    return on_duty is False if mode == "off_duty" else on_duty


def antiping_action_block(guild, member, action):
    kicking = action == "kick"
    verb = "kick" if kicking else "time out"
    me = guild.me
    if me is None:
        return f"could not {verb}, the bot is not in the member list"

    if member == guild.owner:
        return f"cannot {verb} the server owner"

    if member.guild_permissions.administrator:
        return f"cannot {verb} an administrator"

    if kicking and not me.guild_permissions.kick_members:
        return "missing the Kick Members permission"

    if not kicking and not me.guild_permissions.moderate_members:
        return "missing the Moderate Members permission"

    if me.top_role <= member.top_role:
        return f"cannot {verb}, {member.top_role.name} is above the bot's role"

    return None


def antiping_timeout_block(guild, member):
    return antiping_action_block(guild, member, "timeout")


def antiping_record_strike(guild_id, user_id, rule_key, window):
    now = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
    key = (guild_id, user_id, rule_key)

    hits = [stamp for stamp in antipingStrikes.get(key, []) if now - stamp < window]
    hits.append(now)
    antipingStrikes[key] = hits

    if len(antipingStrikes) > 10000:
        for stale, stamps in list(antipingStrikes.items()):
            if not stamps or now - stamps[-1] > window:
                antipingStrikes.pop(stale, None)

    return len(hits)


async def antiping_escalate(bot, rule, message, role):
    escalation = rule.get("escalation") or {}
    if escalation.get("enabled") is not True:
        return None

    threshold = antiping_number(escalation.get("threshold"), 3, 2)
    window = antiping_number(escalation.get("window"), 600, 60)
    rule_key = rule.get("id") or rule.get("name") or "default"

    strikes = antiping_record_strike(
        message.guild.id, message.author.id, rule_key, window
    )
    if strikes < threshold:
        return None

    antipingStrikes.pop((message.guild.id, message.author.id, rule_key), None)
    reason = f"Pinged {role.name} {strikes} times after being warned"

    action = "kick" if escalation.get("action") == "kick" else "timeout"

    blocked = antiping_action_block(message.guild, message.author, action)
    if blocked:
        logging.error("[Anti-Ping] %s for %s", blocked, message.author.id)
        return blocked

    if action == "kick":
        try:
            await message.author.kick(reason=reason)
        except discord.Forbidden:
            logging.error("[Anti-Ping] discord refused the kick for %s", message.author.id)
            return "discord refused the kick, check the bot's role position"
        except discord.HTTPException as exception:
            logging.error("[Anti-Ping] kick failed: %s", exception)
            return "could not kick"

        return "kicked"

    duration = antiping_number(escalation.get("duration"), 300, 60)

    try:
        await message.author.timeout(
            datetime.timedelta(seconds=duration), reason=reason
        )
    except discord.Forbidden:
        logging.error("[Anti-Ping] discord refused the timeout for %s", message.author.id)
        return "discord refused the timeout, check the bot's role position"
    except discord.HTTPException as exception:
        logging.error("[Anti-Ping] timeout failed: %s", exception)
        return "could not time out"

    return f"timed out for {td_format(datetime.timedelta(seconds=duration))}"


async def antiping_log(bot, rule, message, mention, role, outcome):
    channel_id = antiping_channel_id(rule.get("log_channel"))
    if not channel_id:
        return

    channel = message.guild.get_channel(channel_id)
    if channel is None:
        return

    embed = discord.Embed(title="Anti-Ping Warning", color=BLANK_COLOR)
    embed.description = (
        f"{message.author.mention} pinged {mention.mention} in {message.channel.mention}."
    )
    embed.add_field(name="Protected Role", value=role.mention, inline=True)
    embed.add_field(
        name="Outcome", value=outcome or "Warned in channel", inline=True
    )
    embed.add_field(name="Message", value=f"[Jump]({message.jump_url})", inline=True)
    embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
    embed.timestamp = datetime.datetime.now(tz=datetime.timezone.utc)

    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as exception:
        logging.error("[Anti-Ping] could not write to the log channel: %s", exception)


class OnMessage(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        self._mention_cooldowns: dict[int, datetime.datetime] = {}

    @commands.Cog.listener("on_message")
    async def on_message(self, message: discord.Message):
        bot = self.bot
        bypass_role = None
        prefix = (await get_prefix(bot, message))[-1]

        # custom re-execution
        if message.content.startswith(prefix) or message.content.startswith(self.bot.user.mention):
            selected_prefix = prefix if message.content.startswith(prefix) else self.bot.user.mention
            args = message.content.split(selected_prefix)[1].strip().split(" ")

            try:
                command = args[0]
            except:
                pass

            punishment_types = await bot.punishment_types.get_punishment_types(guild_id=message.guild.id)
            default_types = ["warning", "kick", "ban"]
            aliases = {"warn": "warning"}
            if command.lower() in default_types or command.lower() in aliases.keys() or command.lower() in list(filter(lambda x: x != "", [(i if isinstance(i, dict) else {}).get("name", "").replace(" ", "-").lower() for i in (punishment_types or {}).get("types", [])])):
                if command.lower() in aliases.keys():
                    command = aliases[command.lower()]

                message.content = f"{prefix}punish " + args[1] + " " + command + " " + " ".join(args[2:])
                await bot.process_commands(message)
                return
            

        if not message.guild:
            return

       
        if not hasattr(bot, "settings"):
            return

        if message.author == bot.user:
            return

        if message.content.strip() in [f"<@{bot.user.id}>", f"<@!{bot.user.id}>"]:
            now = datetime.datetime.utcnow()
            last = self._mention_cooldowns.get(message.author.id)
            if last and (now - last).total_seconds() < 5:
                return
            self._mention_cooldowns[message.author.id] = now
            
            container = discord.ui.Container()
            section = discord.ui.Section(
                accessory=discord.ui.Thumbnail(
                    media=bot.user.display_avatar.with_format("png").url
                )
            )
            section.add_item(discord.ui.TextDisplay(
                f"### ERM\n"
                f"The all-in-one staff management bot for ER:LC communities.\n\n"
                f"**Prefix** — `{prefix}` or `/`\n"
                f"**Commands** — `{prefix}help`\n"
                f"**Servers** — {len(bot.guilds):,}\n"
                f"**Uptime** — <t:{int(bot.start_time)}:R>"
            ))
            container.add_item(section)
            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.ActionRow(
                discord.ui.Button(label="Website", url="https://ermbot.xyz"),
                discord.ui.Button(label="Support", url="https://discord.gg/uAfU26VRa8"),
                discord.ui.Button(label="Documentation", url="https://docs.ermbot.xyz"),
            ))
            await message.reply(view=discord.ui.LayoutView().add_item(container))
            return

        if not message.guild:
            return

        dataset = await bot.settings.find_by_id(message.guild.id)
        if dataset == None:
            return

        aa_detection = False
        aa_detection_channel = None
        webhook_channel = None
        remote_commands = False
        remote_command_channel = None

        if dataset.get("ERLC", {}).get("remote_commands"):
            remote_commands = True
            remote_command_channel = (
                dataset["ERLC"]["remote_commands"]["webhook_channel"]
                if dataset["ERLC"]["remote_commands"].get("webhook_channel", None)
                else None
            )

        if "game_security" in dataset.keys():
            if "enabled" in dataset["game_security"].keys():
                if (
                    "channel" in dataset["game_security"].keys()
                    and "webhook_channel" in dataset["game_security"].keys()
                ):
                    if dataset["game_security"]["enabled"] is True:
                        aa_detection = True
                        webhook_channel = dataset["game_security"]["webhook_channel"]
                        webhook_channel = discord.utils.get(
                            message.guild.channels, id=webhook_channel
                        )
                        aa_detection_channel = dataset["game_security"]["channel"]
                        aa_detection_channel = discord.utils.get(
                            message.guild.channels, id=aa_detection_channel
                        )

                        if webhook_channel != None:
                            if message.channel.id == webhook_channel.id:
                                for embed in message.embeds:
                                    if embed.description not in [
                                        "",
                                        None,
                                    ] and embed.title not in [
                                        "",
                                        None,
                                    ]:
                                        if (
                                            "kicked" in embed.description
                                            or "banned" in embed.description
                                        ):
                                            if (
                                                "Players Kicked" in embed.title
                                                or "Players Banned" in embed.title
                                            ):
                                                raw_content = embed.description

                                                if "kicked" in raw_content:
                                                    user, command = raw_content.split(
                                                        " kicked `"
                                                    )
                                                else:
                                                    user, command = raw_content.split(
                                                        " banned `"
                                                    )

                                                command = command.replace("`", "")
                                                code = embed.footer.text.split(
                                                    "Server: "
                                                )[1]
                                                if command.count(",") + 1 >= 5:
                                                    people_affected = (
                                                        command.count(",") + 1
                                                    )
                                                    roblox_user = user.split(":")[
                                                        0
                                                    ].replace("[", "")

                                                    roblox_client = roblox.Client()
                                                    try:
                                                        roblox_player = await roblox_client.get_user_by_username(
                                                            roblox_user
                                                        )
                                                    except roblox.UserNotFound:
                                                        return
                                                    thumbnails = await roblox_client.thumbnails.get_user_avatar_thumbnails(
                                                        [roblox_player], size=(420, 420)
                                                    )
                                                    thumbnail = thumbnails[0].image_url

                                                    embed = (
                                                        discord.Embed(
                                                            title=f"{self.bot.emoji_controller.get_emoji('security')} Abuse Detected",
                                                            color=BLANK_COLOR,
                                                        )
                                                        .add_field(
                                                            name="Staff Information",
                                                            value=(
                                                                f"> **Username:** {roblox_player.name}\n"
                                                                f"> **User ID:** {roblox_player.id}\n"
                                                                f"> **Profile Link:** [Click here](https://roblox.com/users/{roblox_player.id}/profile)\n"
                                                                f"> **Account Created:** <t:{int(roblox_player.created.timestamp())}>"
                                                            ),
                                                            inline=False,
                                                        )
                                                        .add_field(
                                                            name="Abuse Information",
                                                            value=(
                                                                f"> **Type:** {'Mass-Kick' if 'kicked' in raw_content else 'Mass-Ban'}\n"
                                                                f"> **Individuals Affected [{command.count(',')+1}]:** {command}\n"
                                                                f"> **At:** <t:{int(message.created_at.timestamp())}>"
                                                            ),
                                                            inline=False,
                                                        )
                                                        .set_thumbnail(url=thumbnail)
                                                    )
                                                    view = GameSecurityActions(bot)
                                                    if not "kicked" in raw_content:
                                                        view.enable_reflective_action()

                                                    pings = []
                                                    pings = [
                                                        (
                                                            (
                                                                message.guild.get_role(
                                                                    role_id
                                                                )
                                                            ).mention
                                                            if message.guild.get_role(
                                                                role_id
                                                            )
                                                            else None
                                                        )
                                                        for role_id in dataset.get(
                                                            "game_security", {}
                                                        ).get("role", [])
                                                    ]
                                                    pings = list(
                                                        filter(
                                                            lambda x: x is not None,
                                                            pings,
                                                        )
                                                    )

                                                    await aa_detection_channel.send(
                                                        (
                                                            ",".join(pings)
                                                            if pings != []
                                                            else ""
                                                        ),
                                                        embed=embed,
                                                        allowed_mentions=discord.AllowedMentions(
                                                            everyone=True,
                                                            users=True,
                                                            roles=True,
                                                            replied_user=True,
                                                        ),
                                                        view=view,
                                                    )
        if (
            remote_commands
            and remote_command_channel is not None
            and message.channel.id in [remote_command_channel]
        ):
            for embed in message.embeds:
                if not embed.description or not embed.title:
                    continue

                if "Player Kicked" in embed.title:
                    action_type = "Kick"
                elif "Player Banned" in embed.title:
                    action_type = "Ban"
                else:
                    continue

                raw_content = embed.description

                if ("kicked" not in raw_content and action_type == "Kick") or (
                    "banned" not in raw_content and action_type == "Ban"
                ):
                    continue

                try:
                    if action_type == "Kick":
                        user_info, command_info = raw_content.split("kicked ", 1)
                    else:
                        user_info, command_info = raw_content.split("banned ", 1)

                    user_info = user_info.strip()
                    command_info = command_info.strip()
                    roblox_user = (
                        user_info.split(":")[0]
                        .replace("[", "")
                        .replace("]", "")
                        .strip()
                    )
                    profile_link = user_info.split("(")[1].split(")")[0].strip()
                    roblox_id_str = profile_link.split("/")[-2]

                    if not roblox_id_str.isdigit():
                        raise ValueError(
                            f"Extracted Roblox ID is not a number: {roblox_id_str}"
                        )

                    roblox_id = int(roblox_id_str)

                    reason = command_info.split("`")[1].strip()
                except (IndexError, ValueError):
                    continue

                discord_user = await bot.linking.get_discord_id(roblox_id) or 0

                if discord_user == 0:
                    await message.add_reaction("❌")
                    return await message.add_reaction("6️⃣")

                user = message.guild.get_member(discord_user)
                if not user:
                    try:
                        user = await message.guild.fetch_member(discord_user)
                    except Exception as e:
                        await message.add_reaction("❌")
                        return await message.add_reaction("7️⃣")

                new_message = copy.copy(message)
                new_message.author = user
                prefix = (await get_prefix(bot, message))[-1]
                reason_info = command_info.split("`")[1].strip()
                split_index = reason_info.find(" ")
                if split_index != -1:
                    violator_user = reason_info[:split_index].strip()
                    reason = reason_info[split_index:].strip()
                else:
                    await message.add_reaction("❌")
                    return await message.add_reaction(
                        "🚫"
                    )  # return since no reason was
                if reason.endswith("- Player Not In Game"):
                    reason = reason[: -len("- Player Not In Game")]
                if not reason:
                    await message.add_reaction("❌")
                    return await message.add_reaction(
                        "🚫"
                    )  # return since no reason was provided
                new_message.content = (
                    f"{prefix}punish {violator_user} {action_type} {reason}"
                )
                await bot.process_commands(new_message)

        if (
            remote_commands
            and remote_command_channel is not None
            and message.channel.id in [remote_command_channel]
        ):
            for embed in message.embeds:
                if embed.description in ["", None] and embed.title in ["", None]:
                    break

                if not ":log" in embed.description:
                    break

                if "Command Usage" not in embed.title:
                    break

                raw_content = embed.description
                user, command = raw_content.split("used the command: ")

                profile_link = user.split("(")[1].split(")")[0]
                user = user.split("(")[0].replace("[", "").replace("]", "")
                try:
                    person = command.split(" ")[1]
                except IndexError:
                    logging.warning("IndexError in remote command usage embed")
                    break
                # Adding check for the command to see if only admin is using the ban command

                players: list[Player] = await self.bot.prc_api.get_server_players(
                    message.guild.id
                )
                try:
                    actual_players = []
                    key_maps = {}

                    for item in players:
                        if item.permission == "Normal":
                            actual_players.append(item)
                        else:
                            if item.permission not in key_maps:
                                key_maps[item.permission] = [item]
                            else:
                                key_maps[item.permission].append(item)

                    # Create a map for key roles
                    new_maps = [
                        "Server Owners",
                        "Server Administrators",
                        "Server Moderators",
                    ]
                    new_vals = [
                        key_maps.get("Server Owner", [])
                        + key_maps.get("Server Co-Owner", []),
                        key_maps.get("Server Administrator", []),
                        key_maps.get("Server Moderator", []),
                    ]
                    new_keymap = dict(zip(new_maps, new_vals))

                    user_permission = None
                    for role, players in new_keymap.items():
                        if any(plr.username == user for plr in players):
                            user_permission = role
                            break

                    # If the user is a Server Moderator and used the ban command
                    if user_permission == "Server Moderators" and "ban" in command:
                        await message.add_reaction("⛔")
                        return
                except Exception as e:
                    logging.warning(f"Error checking command permissions: {e}")
                    continue

                combined = ""
                for word in command.split(" ")[1:]:
                    if not bot.get_command(combined.strip()):
                        combined += word + " "
                    else:
                        item = bot.get_command(combined.strip())
                        if isinstance(item, commands.HybridCommand) and not isinstance(
                            item, commands.HybridGroup
                        ):
                            break
                        else:
                            combined += word + " "

                invoked_command = " ".join(combined.replace("`", "").split(" ")[:-1])
                _cmd = command

                discord_user = await bot.linking.get_discord_id(
                    int(profile_link.split("/")[4])
                ) or 0

                if discord_user == 0:
                    await message.add_reaction("❌")
                    return await message.add_reaction("6️⃣")

                user = message.guild.get_member(discord_user)
                if not user:
                    user = await message.guild.fetch_member(discord_user)
                    if not user:
                        await message.add_reaction("❌")
                        return await message.add_reaction("7️⃣")

                command = bot.get_command(invoked_command.lower().strip())
                if not command and not invoked_command.lower().strip() in ["warn", "warning", "kick", "ban"] + list(filter(lambda x: x != "", [(i if isinstance(i, dict) else {}).get("name", "") for i in (await bot.punishment_types.get_punishment_types(guild_id=message.guild.id) or {}).get("types", [])])):
                    await message.add_reaction("❌")
                    return await message.add_reaction("8️⃣")

                new_message = copy.copy(message)
                new_message.channel = await user.create_dm()
                new_message.author = user
                actual_username = next(
                    (
                        player.username
                        for player in actual_players
                        if person in player.username
                    ),
                    person,
                )
                new_message.content = (
                    (await get_prefix(bot, message))[-1]
                ) + _cmd.split(":log ")[1].split("`")[0].replace(
                    person, actual_username
                )
                await bot.process_commands(new_message)

        if isinstance(message.author, discord.User):
            return

        if message.author.bot:
            return

        if antiping_settings(dataset).get("enabled") is True and message.author != message.guild.owner:
            author_top = message.author.top_role

            for rule in antiping_rules(dataset):
                if antiping_is_ignored(rule, message.channel):
                    continue

                exempt = antiping_role_list(message.guild, rule.get("bypass_role"))
                if any(role in message.author.roles for role in exempt):
                    continue

                protected = antiping_role_list(message.guild, rule.get("role"))
                if not protected:
                    continue

                hierarchy = rule.get("use_hierarchy") is True
                match = None

                for mention in message.mentions:
                    if mention.bot or mention == message.author:
                        continue

                    for role in protected:
                        if role not in mention.roles or role in message.author.roles:
                            continue
                        if hierarchy and author_top >= role:
                            continue
                        if not await antiping_protects(bot, rule, message.guild.id, mention):
                            continue

                        match = (mention, role)
                        break

                    if match:
                        break

                if not match:
                    continue

                mention, role = match

                outcome = await antiping_escalate(bot, rule, message, role)
                speak = antiping_should_warn(message.guild.id, message.author.id)

                if not speak and outcome is None:
                    return

                title = f"Do not ping {role.name} or above!" if hierarchy else f"Do not ping {role.name}!"
                embed = discord.Embed(
                    title=title,
                    color=discord.Color.red(),
                    description=f"Do not ping those with {role.name}!\nIt is a violation of the rules, and you will be punished if you continue.",
                )
                try:
                    if message.reference:
                        msg = await message.channel.fetch_message(
                            message.reference.message_id
                        )
                        if msg.author == mention:
                            embed.set_image(url="https://i.imgur.com/pXesTnm.gif")
                except discord.NotFound:
                    pass
                embed.set_footer(
                    text=f'Thanks, {((dataset or {}).get("customisation") or {}).get("brand_name") or "ERM"}',
                    icon_url=get_guild_icon(bot, message.guild),
                )

                if speak:
                    ctx = await bot.get_context(message)
                    await ctx.reply(
                        f"{message.author.mention}",
                        embed=embed,
                        delete_after=15,
                    )

                await antiping_log(bot, rule, message, mention, role, outcome)
                return

        custom_commands = await bot.custom_commands.find_by_id(message.guild.id)
        if custom_commands is None:
            return

        prefix = (dataset or {}).get("customisation", {}).get("prefix", ">")

        if message.content.startswith(prefix):
            try:
                command_parts = message.content.split(" ")
                command = command_parts[0].replace(prefix, "").lower()
                channel_id = int(command_parts[1].replace("<#", "").replace(">", ""))
                channel = discord.utils.get(message.guild.text_channels, id=channel_id)
            except (IndexError, ValueError):
                command = message.content.replace(prefix, "").lower()
                channel = None

            if command in bot.all_commands:
                return

            ctx = await bot.get_context(message)
            if "commands" in custom_commands:
                if isinstance(custom_commands["commands"], list):
                    selected = next(
                        (
                            cmd
                            for cmd in custom_commands["commands"]
                            if cmd["name"].lower().replace(" ", "")
                            == command.lower().replace(" ", "")
                        ),
                        None,
                    )
                    is_command = selected is not None
                else:
                    is_command = False
            else:
                is_command = False

            if not is_command:
                return

            if not channel:
                channel = ctx.channel

            embeds = [
                await interpret_embed(bot, ctx, channel, embed, selected["id"])
                for embed in selected["message"]["embeds"]
            ]

            view = discord.ui.View()
            for item in selected.get("buttons", []):
                view.add_item(
                    discord.ui.Button(
                        label=item["label"],
                        url=item["url"],
                        row=item["row"],
                        style=discord.ButtonStyle.url,
                    )
                )

            if ctx.interaction:
                if (
                    not selected["message"]["content"]
                    and not selected["message"]["embeds"]
                ):
                    return await ctx.interaction.followup.send(
                        embed=discord.Embed(
                            title="Empty Command",
                            description="Due to Discord limitations, I am unable to send your reminder. Your message is most likely empty.",
                            color=discord.Color.red(),
                        )
                    )
                await ctx.interaction.followup.send(
                    embed=discord.Embed(
                        title=f"{self.bot.emoji_controller.get_emoji('success')} Command Ran",
                        description=f"I've just ran the custom command in {channel.mention}.",
                        color=discord.Color.green(),
                    )
                )
                msg = await channel.send(
                    content=await interpret_content(
                        bot,
                        ctx,
                        channel,
                        selected["message"]["content"],
                        selected["id"],
                    ),
                    embeds=embeds,
                    view=view,
                    allowed_mentions=discord.AllowedMentions(
                        everyone=True, users=True, roles=True, replied_user=True
                    ),
                )
            else:
                if (
                    not selected["message"]["content"]
                    and not selected["message"]["embeds"]
                ):
                    return await ctx.reply(
                        embed=discord.Embed(
                            title="Empty Command",
                            description="Due to Discord limitations, I am unable to send your reminder. Your message is most likely empty.",
                            color=discord.Color.red(),
                        )
                    )
                await ctx.reply(
                    embed=discord.Embed(
                        title=f"{self.bot.emoji_controller.get_emoji('success')} Command Ran",
                        description=f"I've just ran the custom command in {channel.mention}.",
                        color=discord.Color.green(),
                    )
                )
                msg = await channel.send(
                    content=await interpret_content(
                        bot,
                        ctx,
                        channel,
                        selected["message"]["content"],
                        selected["id"],
                    ),
                    embeds=embeds,
                    view=view,
                    allowed_mentions=discord.AllowedMentions(
                        everyone=True, users=True, roles=True, replied_user=True
                    ),
                )

            doc = await bot.ics.find_by_id(selected["id"]) or {}
            if doc is None:
                return
            doc["associated_messages"] = (
                [(channel.id, msg.id)]
                if not doc.get("associated_messages")
                else doc["associated_messages"] + [(channel.id, msg.id)]
            )
            doc["_id"] = ctx.guild.id
            await bot.ics.update_by_id(doc)

        return


async def setup(bot):
    await bot.add_cog(OnMessage(bot))
