import datetime
import json
import typing

import aiohttp
import discord
import pytz
import reactionmenu
import roblox
from decouple import config
from discord import app_commands
from discord.ext import commands
from reactionmenu import ViewButton, ViewMenu
from reactionmenu.abc import _PageController
import pytz
from datamodels.Settings import Settings
from datamodels.Warnings import WarningItem
from erm import (
    admin_predicate,
    generator,
    is_management,
    is_staff,
    management_predicate,
)
from menus import (
    ChannelSelect,
    CustomisePunishmentType,
    CustomModalView,
    CustomSelectMenu,
    EditWarning,
    RemoveWarning,
    RequestDataView,
    CustomExecutionButton,
    UserSelect,
    YesNoMenu,
    ManagementOptions,
    ManageTypesView,
    PunishmentTypeCreator,
    PunishmentModifier,
    CustomModal,
)
from utils.AI import AI
from utils.autocompletes import punishment_autocomplete, user_autocomplete
from utils.constants import BLANK_COLOR, GREEN_COLOR, ONE_WEEK, DAY_NAMES
from utils.paginators import SelectPagination, CustomPage, SelectPaginationV2, CustomPageV2
from utils.utils import (
    admin_check,
    failure_embed,
    removesuffix,
    get_roblox_by_username,
    failure_embed,
    require_settings,
    new_failure_embed,
    time_converter,
)
from utils.timestamp import td_format


class Punishments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.guild_only()
    @commands.hybrid_command(
        name="punish",
        aliases=["p"],
        description="Punish a user",
        extras={"category": "Punishments"},
        usage="punish <user> <type> <reason>",
    )
    @is_staff()
    @require_settings()
    @app_commands.autocomplete(type=punishment_autocomplete)
    @app_commands.autocomplete(user=user_autocomplete)
    @app_commands.describe(type="The type of punishment to give.")
    @app_commands.describe(
        user="What's their username? You can mention a Discord user, or provide a ROBLOX username."
    )
    @app_commands.describe(reason="What is your reason for punishing this user?")
    async def punish(self, ctx, user: str, type: str, *, reason: str):
        if type.lower() == "warn":
            type = "Warning"

        settings = await self.bot.settings.find_by_id(ctx.guild.id) or {}
        if not settings:
            return await ctx.send(
                embed=discord.Embed(
                    title="Not Setup",
                    description="Your server is not setup.",
                    color=BLANK_COLOR,
                )
            )

        if not (settings.get("punishments") or {}).get("enabled", False):
            return await ctx.send(
                embed=discord.Embed(
                    title="Not Enabled",
                    description="Your server has punishments disabled.",
                    color=BLANK_COLOR,
                )
            )

        auto_punish = settings.get("ERLC", {}).get("auto_punish", False)
        present_unpermitted_warning = False
        if auto_punish is True:
            server_staff = await self.bot.prc_api.get_server_staff(ctx.guild.id)
            roblox_username = await self.bot.accounts.discord_to_roblox(ctx.guild, ctx.author.id)
            if type.strip().lower() == "ban" and auto_punish is True:
                if not (await admin_predicate(ctx) or await management_predicate(ctx) or roblox_username in [i.username for i in list(filter(lambda x: x.permission != "Server Moderator", server_staff))]):
                    present_unpermitted_warning = True

        flags = []
        if "--kick" in reason.lower() or (auto_punish and type.lower() == "kick"):
            flags.append("autokick")
            reason = reason.replace("--kick", "")
        elif "--ban" in reason.lower() or (auto_punish and type.lower() == "ban"):
            flags.append("autoban")
            reason = reason.replace("--ban", "")

        if self.bot.punishments_disabled is True:
            return await new_failure_embed(
                ctx,
                "Maintenance",
                "This command is currently disabled as ERM is currently undergoing maintenance updates. This command will be turned off briefly to ensure that no data is lost during the maintenance.",
            )

        roblox_user = await get_roblox_by_username(user, self.bot, ctx)
        roblox_client = roblox.Client()
        if not roblox_user or roblox_user.get("errors") is not None:
            return await ctx.send(
                embed=discord.Embed(
                    title="Could not find player",
                    description="I could not find a Roblox player with that username.",
                    color=BLANK_COLOR,
                )
            )

        roblox_player = await roblox_client.get_user(roblox_user["id"])
        thumbnails = await roblox_client.thumbnails.get_user_avatar_thumbnails(
            [roblox_player], type=roblox.thumbnails.AvatarThumbnailType.headshot
        )
        thumbnail = thumbnails[0].image_url

        # Get and verify punishment type
        punishment_types = await self.bot.punishment_types.get_punishment_types(
            ctx.guild.id
        )
        types = (punishment_types or {}).get("types", [])
    
        preset_types = ["Warning", "Kick", "Ban", "BOLO"]

        enabled_punishments = (punishment_types or {}).get("default_punishments", [])
        enabled_defaults = {
            p["name"].lower()
            for p in enabled_punishments
            if p.get("enabled", False)
        }
        actual_types = []
        for item in preset_types:
            if not enabled_defaults or item.lower() in enabled_defaults:
                actual_types.append(item)
        for item in types:
            if isinstance(item, str):
                actual_types.append(item)
            else:
                actual_types.append(item["name"])

        if type.lower().strip() not in [i.lower().strip() for i in actual_types]:
            return await ctx.send(
                embed=discord.Embed(
                    title="Incorrect Type",
                    description="The punishment type you provided is invalid.",
                    color=BLANK_COLOR,
                )
            )

        msg = None

        for item in actual_types:
            safe_item = item.lower().split()
            if safe_item == type.lower().split():
                actual_type = item
                break
        else:
            return await ctx.send(
                embed=discord.Embed(
                    title="Incorrect Type",
                    description="The punishment type you provided is invalid.",
                    color=BLANK_COLOR,
                )
            )

        if type.lower() in ["tempban", "temporary ban"]:
            return await ctx.send(
                embed=discord.Embed(
                    title="Not Supported",
                    description="Temporary Bans are not supported.",
                    color=BLANK_COLOR,
                )
            )

        oid = await self.bot.punishments.insert_warning(
            ctx.author.id,
            ctx.author.name,
            roblox_player.id,
            roblox_player.name,
            ctx.guild.id,
            reason,
            actual_type,
            datetime.datetime.now(tz=pytz.UTC).timestamp(),
        )

        current_shift = await self.bot.shift_management.get_current_shift(
            ctx.author, ctx.guild.id
        )
        is_online = bool(current_shift)
        if is_online:
            await self.bot.shift_management.shifts.db.update_one(
                {"_id": current_shift["_id"]}, {"$push": {"Moderations": oid}}
            )

        self.bot.dispatch("punishment", oid)

        warning: WarningItem = await self.bot.punishments.fetch_warning(oid)
        newline = "\n"
        if "autoban" in flags and (await admin_predicate(ctx) or await management_predicate(ctx) or roblox_username in [i.username for i in list(filter(lambda x: x.permission != "Server Moderator", server_staff))]):
            try:
                await self.bot.prc_api.run_command(
                    ctx.guild.id, ":ban {}".format(warning.user_id)
                )
            except:
                pass
        elif "autokick" in flags:
            try:
                await self.bot.prc_api.run_command(
                    ctx.guild.id, ":kick {}".format(warning.username)
                )
            except:
                pass

        embed = discord.Embed(
                title=f"{self.bot.emoji_controller.get_emoji('success')} Logged Punishment",
                description=("I have successfully logged the following punishment!"),
                color=GREEN_COLOR,
            ).add_field(
                name="Punishment",
                value=(
                    f"> **Player:** {warning.username}\n"
                    f"> **Type:** {warning.warning_type}\n"
                    f"> **Moderator:** <@{warning.moderator_id}>\n"
                    f"> **Reason:** {warning.reason}\n"
                    f"> **At:** <t:{int(warning.time_epoch)}>\n"
                    f'{"> **Until:** <t:{}>{}".format(int(warning.until_epoch), newline) if warning.until_epoch is not None else ""}'
                    f"> **ID:** `{warning.snowflake}`\n"
                    f"> **Custom Flags:** {'`N/A`' if len(flags) == 0 else '{}'.format(', '.join(flags))}"
                ),
                inline=False,
        )
        
        if present_unpermitted_warning:
            embed.add_field(
                name="Auto-Ban Failed",
                value="> You do not hold Server Administrator privileges in the private server, and you do not hold an Admin Role, which means that you are unable to auto-ban this individual.",
                inline=False,
            )

        await (ctx.send if not msg else msg.edit)(
            embed=embed.set_thumbnail(url=thumbnail),
            view=None
        )


    @commands.hybrid_group(
        name="punishment",
        description="Punishment commands",
        extras={"category": "Punishments"},
        aliases=["pm"],
    )
    @is_staff()
    async def punishments(self, ctx: commands.Context):
        await ctx.invoke(self.bot.get_command("punishment manage"))

    # Punishment Manage command, containing `types`, `void` and `modify`
    @commands.guild_only()
    @punishments.command(
        name="manage",
        description="Manage punishments",
        extras={"category": "Punishments"},
    )
    @require_settings()
    # @is_management()
    @is_staff()
    async def punishment_manage(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Staff Options",
            description="Using this menu, you can **Manage Punishment Types** as well as **Modify Punishment**.",
            color=BLANK_COLOR,
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon)
        view = ManagementOptions(ctx.author.id)
        settings = await self.bot.settings.find_by_id(ctx.guild.id)

        msg = await ctx.send(embed=embed, view=view)
        await view.wait()

        if view.value == "modify":
            try:
                punishment_id = int(view.modal.punishment_id.value.strip())
            except ValueError:
                return await msg.edit(
                    embed=discord.Embed(
                        title="Invalid Punishment ID",
                        description="This punishment ID is invalid.",
                        color=BLANK_COLOR,
                    ),
                    view=None,
                )

            punishment = await self.bot.punishments.find_warning_by_spec(
                snowflake=punishment_id, guild_id=ctx.guild.id
            )
            if not punishment:
                return await msg.edit(
                    embed=discord.Embed(
                        title="Invalid Punishment ID",
                        description="This punishment ID is invalid.",
                        color=BLANK_COLOR,
                    ),
                    view=None,
                )

            if (
                punishment["ModeratorID"] != ctx.author.id
                and not await management_predicate(ctx)
                and not await admin_predicate(ctx)
            ):
                return await msg.edit(
                    embed=discord.Embed(
                        title="Access Denied",
                        description="You are unable to edit other people's punishments as you only have the Staff permission.",
                        color=BLANK_COLOR,
                    )
                )

            view = PunishmentModifier(self.bot, ctx.author.id, punishment)
            await view.refresh_ui(msg)
            await view.wait()
            await msg.edit(
                embed=discord.Embed(
                    title=f"{self.bot.emoji_controller.get_emoji('success')} Modified!",
                    description="Successfully modified this punishment!",
                    color=GREEN_COLOR,
                ),
                view=None,
            )

        elif view.value == "types":
            if not await management_predicate(ctx):
                return await msg.edit(
                    embed=discord.Embed(
                        title="Not Permitted",
                        description="You are not permitted to access this panel.",
                        color=BLANK_COLOR,
                    ),
                    view=None,
                )
            punishment_types = await self.bot.punishment_types.get_punishment_types(
                ctx.guild.id
            )
            if not punishment_types:
                punishment_types = {"types": []}

            punishment_types = punishment_types["types"]

            def setup_embed() -> discord.Embed:
                embed = discord.Embed(title="Punishment Types", color=BLANK_COLOR)
                embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon)
                return embed

            filtered = list(filter(lambda x: isinstance(x, dict), punishment_types))
            embeds = []
            associations = {}
            if len(embeds) == 0:
                embeds.append(setup_embed())

            for item in filtered:

                if len(embeds[-1].fields) > 15:
                    embeds[-1].add_field(
                        name="Limitation",
                        value="You cannot have more than 15 custom punishment types.",
                        inline=False,
                    )
                    break

                embeds[-1].add_field(
                    name=item["name"],
                    value=(
                        f"> **Name:** {item['name']}\n"
                        f"> **ID:** {item.get('id', (temporary_id := next(generator)))}\n"
                        f"> **Channel:** <#{item['channel']}>"
                    ),
                    inline=False,
                )
                associations[temporary_id] = item
            if len(embeds[0].fields) == 0:
                embeds[0].add_field(
                    name="No Punishment Types",
                    value="There are no custom punishment types in this server.",
                    inline=False,
                )
            manage_types_view = ManageTypesView(self.bot, ctx.author.id)
            await msg.edit(embed=embeds[0], view=manage_types_view)
            await manage_types_view.wait()
            if manage_types_view.value == "create":
                data = {
                    "id": next(generator),
                    "name": manage_types_view.name_for_creation,
                    "channel": None,
                }
                embed = discord.Embed(
                    title="Punishment Type Creation",
                    description=(
                        f"> **Name:** {data['name']}\n"
                        f"> **ID:** {data['id']}\n"
                        f"> **Punishment Channel:** {'<#{}>'.format(data.get('channel', None)) if data.get('channel', None) is not None else 'Not set'}\n"
                    ),
                    color=BLANK_COLOR,
                )

                view = PunishmentTypeCreator(ctx.author.id, data)
                await msg.edit(view=view, embed=embed)
                await view.wait()
                if view.cancelled is True:
                    return

                punishment_types.append(view.dataset)

                await self.bot.punishment_types.upsert(
                    {"_id": ctx.guild.id, "types": punishment_types}
                )
                await msg.edit(
                    embed=discord.Embed(
                        title=f"{self.bot.emoji_controller.get_emoji('success')} Type Created",
                        description="Your punishment type has been created!",
                        color=GREEN_COLOR,
                    ),
                    view=None,
                )
            elif manage_types_view.value == "delete":
                if not await management_predicate(ctx):
                    return await msg.edit(
                        embed=discord.Embed(
                            title="Not Permitted",
                            description="You are not permitted to access this panel.",
                            color=BLANK_COLOR,
                        )
                    )
                try:
                    type_id = int(manage_types_view.selected_for_deletion.strip())
                except ValueError:
                    return await msg.edit(
                        embed=discord.Embed(
                            title="Invalid Punishment Type",
                            description="The ID you have provided is not associated with a punishment type.",
                            color=BLANK_COLOR,
                        ),
                        view=None,
                    )
                if len(punishment_types) == 0:
                    return await msg.edit(
                        embed=discord.Embed(
                            title="Invalid Punishment Type",
                            description="The ID you have provided is not associated with a punishment type.",
                            color=BLANK_COLOR,
                        ),
                        view=None,
                    )
                if type_id not in [t.get("id") for t in list(filtered)]:
                    if not associations.get(type_id):
                        return await msg.edit(
                            embed=discord.Embed(
                                title="Invalid Punishment Type",
                                description="The ID you have provided is not associated with a punishment type.",
                                color=BLANK_COLOR,
                            ),
                            view=None,
                        )
                for item in filtered:
                    if item.get("id") == type_id or item == associations.get(type_id):
                        punishment_types.remove(item)
                        break

                await self.bot.punishment_types.upsert(
                    {"_id": ctx.guild.id, "types": punishment_types}
                )
                await msg.edit(
                    embed=discord.Embed(
                        title=f"{self.bot.emoji_controller.get_emoji('success')} Type Deleted",
                        description="Your Punishment Type has been deleted!",
                        color=GREEN_COLOR,
                    ),
                    view=None,
                )

    @commands.hybrid_group(
        name="bolo",
        description="Manage the server's BOLO list.",
        extras={"category": "Punishments"},
    )
    async def bolo(self, ctx):
        pass

    @commands.guild_only()
    @bolo.command(
        name="active",
        description="View the server's active BOLOs.",
        extras={"category": "Punishments", "ignoreDefer": True},
        aliases=["search", "lookup"],
    )
    @app_commands.autocomplete(user=user_autocomplete)
    @app_commands.describe(user="The user to search for.")
    @is_staff()
    @require_settings()
    async def active(self, ctx, user: str = None):

        async def task(interaction: discord.Interaction, _):
            modal = CustomModal(
                "Mark as Complete",
                [
                    (
                        "bolo",
                        discord.ui.TextInput(
                            placeholder="The ID for the BOLO you are marking as complete",
                            label="BOLO ID",
                        ),
                    )
                ],
                {"ephemeral": True, "thinking": True},
            )

            await interaction.response.send_modal(modal)
            timeout = await modal.wait()
            if timeout:
                return
            try:
                id = int(modal.bolo.value)
            except ValueError:
                return await modal.interaction.followup.send(
                    embed=discord.Embed(
                        title="Invalid Identifier",
                        description="I could not find a BOLO associating with that ID. Please ensure you have entered the correct ID.",
                        color=BLANK_COLOR,
                    )
                )

            matching_docs = list(
                filter(
                    lambda x: x is not None,
                    [
                        await bot.punishments.find_warning_by_spec(
                            snowflake=id,
                            warning_type="BOLO",
                            guild_id=interaction.guild.id,
                        )
                    ],
                )
            )

            if len(matching_docs) == 0:
                return await modal.interaction.followup.send(
                    embed=discord.Embed(
                        title="Invalid Identifier",
                        description="I could not find a BOLO associating with that ID. Please ensure you have entered the correct ID.",
                        color=BLANK_COLOR,
                    )
                )

            doc = matching_docs[0]

            await bot.punishments.insert_warning(
                ctx.author.id,
                ctx.author.name,
                doc["UserID"],
                doc["Username"],
                ctx.guild.id,
                f"BOLO marked as complete by {ctx.author} ({ctx.author.id}). Original BOLO Reason was {doc['Reason']} made by {doc['Moderator']} ({doc['ModeratorID']})",
                "Ban",
                datetime.datetime.now(tz=pytz.UTC).timestamp(),
            )

            await bot.punishments.remove_warning_by_snowflake(id)

            await modal.interaction.followup.send(
                embed=discord.Embed(
                    title=f"{self.bot.emoji_controller.get_emoji('success')} Completed BOLO",
                    description="This BOLO has been marked as complete successfully.",
                    color=GREEN_COLOR,
                )
            )
            return

        async def deny_task(interaction: discord.Interaction, _):
            modal = CustomModal(
                "Mark as Denied",
                [
                    (
                        "bolo",
                        discord.ui.TextInput(
                            placeholder="The ID for the BOLO you are marking as denied",
                            label="BOLO ID",
                        ),
                    )
                ],
                {"ephemeral": True, "thinking": True},
            )

            await interaction.response.send_modal(modal)
            timeout = await modal.wait()
            if timeout:
                return
            try:
                id = int(modal.bolo.value)
            except ValueError:
                return await modal.interaction.followup.send(
                    embed=discord.Embed(
                        title="Invalid Identifier",
                        description="I could not find a BOLO associating with that ID. Please ensure you have entered the correct ID.",
                        color=BLANK_COLOR,
                    )
                )

            # bro i just realised someone could use this to erase a non-bolo...
            matching_docs = list(
                filter(
                    lambda x: x is not None,
                    [
                        await bot.punishments.find_warning_by_spec(
                            snowflake=id,
                            warning_type="BOLO",
                            guild_id=interaction.guild.id,
                        )
                    ],
                )
            )

            if len(matching_docs) == 0:
                return await modal.interaction.followup.send(
                    embed=discord.Embed(
                        title="Invalid Identifier",
                        description="I could not find a BOLO associating with that ID. Please ensure you have entered the correct ID.",
                        color=BLANK_COLOR,
                    )
                )

            doc = matching_docs[0]

            await bot.punishments.remove_warning_by_snowflake(id)

            await modal.interaction.followup.send(
                embed=discord.Embed(
                    title=f"{self.bot.emoji_controller.get_emoji('success')} Denied BOLO",
                    description="This BOLO has been marked as denied successfully.\nIt has been erased from the active BOLO list.",
                    color=GREEN_COLOR,
                )
            )
            return

        if self.bot.punishments_disabled is True:
            return await failure_embed(
                ctx,
                "This command is currently disabled as ERM is currently undergoing maintenance updates. This command will be turned off briefly to ensure that no data is lost during the maintenance. It will be returned shortly.",
            )

        bot = self.bot
        if user is None:
            bolos = await bot.punishments.get_guild_bolos(ctx.guild.id)
            msg = None
            if len(bolos) == 0:
                return await ctx.reply(
                    embed=discord.Embed(
                        title="No Entries",
                        description="There are no active BOLOs in this server.",
                        color=BLANK_COLOR,
                    )
                )
            embeds = []

            embed = discord.Embed(
                title="Active Ban BOLOs",
                color=BLANK_COLOR,
            )

            embed.set_author(
                name=ctx.guild.name,
                icon_url=ctx.guild.icon,
            )

            embed.set_footer(
                text="Click 'Mark as Complete' or 'Deny BOLO' and enter the BOLO ID."
            )

            embeds.append(embed)

            for entry in bolos:
                if len(embeds[-1].fields) == 4:
                    new_embed = discord.Embed(
                        title="Active Ban BOLOs",
                        color=BLANK_COLOR,
                    )

                    new_embed.set_author(
                        name=ctx.guild.name,
                        icon_url=ctx.guild.icon,
                    )

                    embeds.append(new_embed)

                warning: WarningItem = await bot.punishments.fetch_warning(entry["_id"])

                embeds[-1].add_field(
                    name=f"{warning.username} ({warning.user_id})",
                    inline=False,
                    value=(
                        f"> **Moderator:** <@{warning.moderator_id}>\n"
                        f"> **Reason:** {warning.reason}\n"
                        f"> **At:** <t:{int(warning.time_epoch)}>\n"
                        f"> **ID:** `{warning.snowflake}`"
                    ),
                )

            for embed in embeds:
                embed.title += " [{}]".format(len(bolos))

            view = discord.ui.View()
            view.add_item(
                CustomExecutionButton(
                    ctx.author.id,
                    "Mark as Complete",
                    discord.ButtonStyle.secondary,
                    func=task,
                )
            )
            view.add_item(
                CustomExecutionButton(
                    ctx.author.id,
                    "Deny BOLO",
                    discord.ButtonStyle.danger,
                    func=deny_task,
                )
            )

            paginator = SelectPagination(
                self.bot,
                ctx.author.id,
                [
                    CustomPage(embeds=[embed], view=view, identifier=str(index + 1))
                    for index, embed in enumerate(embeds)
                ],
            )
            current_page = paginator.get_current_view()

            msg = await ctx.reply(embed=embeds[0], view=current_page)

        else:
            roblox_user = await get_roblox_by_username(user, bot, ctx)
            if roblox_user is None:
                return await ctx.send(
                    embed=discord.Embed(
                        title="Could not find player",
                        description="I could not find a Roblox player with that username.",
                        color=BLANK_COLOR,
                    )
                )

            if roblox_user.get("errors") is not None:
                return await ctx.send(
                    embed=discord.Embed(
                        title="Could not find player",
                        description="I could not find a Roblox player with that username.",
                        color=BLANK_COLOR,
                    )
                )

            user = [
                i
                async for i in bot.punishments.find_warnings_by_spec(
                    ctx.guild.id, user_id=roblox_user["id"], bolo=True
                )
            ]
            bolos = user

            if user is None:
                return await ctx.reply(
                    embed=discord.Embed(
                        title="No Entries",
                        description="There are no active BOLOs for this user in this server.",
                        color=BLANK_COLOR,
                    )
                )

            if len(bolos) == 0:
                return await ctx.reply(
                    embed=discord.Embed(
                        title="No Entries",
                        description="There are no active BOLOs for this user in this server.",
                        color=BLANK_COLOR,
                    )
                )

            embeds = []

            embed = discord.Embed(
                title="Active Ban BOLOs",
                color=BLANK_COLOR,
            )

            embed.set_author(
                name=ctx.guild.name,
                icon_url=ctx.guild.icon,
            )

            embed.set_footer(
                text="Click 'Mark as Complete' or 'Deny BOLO' and enter the BOLO ID."
            )

            embeds.append(embed)

            for entry in bolos:
                if len(embeds[-1].fields) == 4:
                    new_embed = discord.Embed(
                        title="Active Ban BOLOs",
                        color=BLANK_COLOR,
                    )

                    new_embed.set_author(
                        name=ctx.guild.name,
                        icon_url=ctx.guild.icon,
                    )

                    embeds.append(new_embed)

                warning: WarningItem = await bot.punishments.fetch_warning(entry["_id"])

                embeds[-1].add_field(
                    name=f"{warning.username} ({warning.user_id})",
                    inline=False,
                    value=(
                        f"> **Moderator:** <@{warning.moderator_id}>\n"
                        f"> **Reason:** {warning.reason}\n"
                        f"> **At:** <t:{int(warning.time_epoch)}>\n"
                        f"> **ID:** `{warning.snowflake}`"
                    ),
                )

            for embed in embeds:
                embed.title += " [{}]".format(len(bolos))

            view = discord.ui.View()
            view.add_item(
                CustomExecutionButton(
                    ctx.author.id,
                    "Mark as Complete",
                    discord.ButtonStyle.secondary,
                    func=task,
                )
            )
            view.add_item(
                CustomExecutionButton(
                    ctx.author.id,
                    "Deny BOLO",
                    discord.ButtonStyle.danger,
                    func=deny_task,
                )
            )

            paginator = SelectPagination(
                self.bot,
                ctx.author.id,
                [
                    CustomPage(embeds=[embed], view=view, identifier=str(index + 1))
                    for index, embed in enumerate(embeds)
                ],
            )
            current_page = paginator.get_current_view()

            msg = await ctx.reply(embed=embeds[0], view=current_page)


    @punishments.command(
        name="leaderboard",
        description="View the server's punishment leaderboard.",
        extras={"category": "Punishments"},
    )
    @is_staff()
    @require_settings()
    @app_commands.describe(
        timeframe="The timeframe to view the leaderboard for (e.g. '1d', '1w', '1m'). Leave blank for all time.",
        role="Filter the leaderboard to only show members with this role.",
    )
    async def punishment_leaderboard(self, ctx: commands.Context, role: typing.Optional[discord.Role] = None, timeframe: typing.Optional[str] = None):
        gt_time = 0
        if timeframe not in ["", None, " ", "all", "total"]:
            gt_time = int(datetime.datetime.now().timestamp()) - time_converter(timeframe)

        title = "Punishment Leaderboard"
        if role:
            title += f" — {role.name}"

        embed = discord.Embed(
            title=title,
            description="**Total Punishments**\n",
            color=BLANK_COLOR,
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon)

        match_filter = {"Guild": ctx.guild.id, "Epoch": {"$gte": gt_time}}
        if role:
            role_member_ids = [m.id for m in role.members]
            match_filter["ModeratorID"] = {"$in": role_member_ids}

        pipeline = [
            {"$match": match_filter},
            {
                "$group": {
                    "_id": {
                        "moderator": "$ModeratorID",
                        "guild": "$Guild"
                    },
                    "moderationCount": {"$sum": 1}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "ModeratorID": "$_id.moderator",
                    "Guild": "$_id.guild",
                    "ModerationCount": "$moderationCount"
                }
            }
        ]

        results = await (await self.bot.punishments.db.aggregate(pipeline)).to_list(length=None)
        sorted_results = sorted(
            results, key=lambda x: x["ModerationCount"], reverse=True
        )
        pages = []
        for index, item in enumerate(sorted_results):
            embed.description += "> **{}**. <@{}> • {} moderations\n".format(
                index + 1, item["ModeratorID"], f"{item['ModerationCount']:,}",
            )
            if len(embed.description) > 2000:
                pages.append(CustomPage(
                    embeds=[embed], identifier=str(len(pages) + 1)
                ))
                embed = discord.Embed(
                    title="Punishment Leaderboard",
                    description="**Total Punishments**\n",
                    color=BLANK_COLOR,
                )
                embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon)
        
        if len(pages) == 0 or pages[-1].embeds[0] != embed:
            pages.append(CustomPage(
                embeds=[embed], identifier=str(len(pages) + 1)
            ))

        
        if len(sorted_results) == 0:
            embed.description = "> There are no punishments in this server."
        
        paginator = SelectPagination(
            self.bot,
            ctx.author.id,
            pages
        )
        await ctx.send(
            embed=pages[0].embeds[0],
            view=paginator.get_current_view(),
        )
        

    @commands.guild_only()
    @commands.hybrid_command(
        name="tempban",
        aliases=["tb", "tba"],
        description="Tempbans a user.",
        extras={"category": "Punishments"},
        with_app_command=True,
    )
    @is_staff()
    @app_commands.autocomplete(user=user_autocomplete)
    @app_commands.describe(user="What's their ROBLOX username?")
    @app_commands.describe(time="How long are you banning them for? (s/m/h/d)")
    @app_commands.describe(reason="What is your reason for punishing this user?")
    async def tempban(self, ctx, user, time: str, *, reason):
        if self.bot.punishments_disabled is True:
            return await new_failure_embed(
                ctx,
                "Maintenance",
                "This command is currently disabled as ERM is currently undergoing maintenance updates. This command will be turned off briefly to ensure that no data is lost during the maintenance.",
            )

        try:
            amount = time_converter(time)
        except ValueError:
            return await ctx.send(
                embed=discord.Embed(
                    title="Invalid Time",
                    description="The time provided is invalid.",
                    color=BLANK_COLOR,
                )
            )

        roblox_user = await get_roblox_by_username(user, self.bot, ctx)
        roblox_client = roblox.Client()
        if not roblox_user or roblox_user.get("errors") is not None:
            return await ctx.send(
                embed=discord.Embed(
                    title="Could not find player",
                    description="I could not find a Roblox player with that username.",
                    color=BLANK_COLOR,
                )
            )

        roblox_player = await roblox_client.get_user(roblox_user["id"])
        thumbnails = await roblox_client.thumbnails.get_user_avatar_thumbnails(
            [roblox_player], type=roblox.thumbnails.AvatarThumbnailType.headshot
        )
        thumbnail = thumbnails[0].image_url

        oid = await self.bot.punishments.insert_warning(
            ctx.author.id,
            ctx.author.name,
            roblox_player.id,
            roblox_player.name,
            ctx.guild.id,
            reason,
            "Temporary Ban",
            datetime.datetime.now(tz=pytz.UTC).timestamp(),
            datetime.datetime.now(tz=pytz.UTC).timestamp() + amount,
        )

        self.bot.dispatch("punishment", oid)

        warning: WarningItem = await self.bot.punishments.fetch_warning(oid)
        newline = "\n"
        await ctx.send(
            embed=discord.Embed(
                title=f"{self.bot.emoji_controller.get_emoji('success')} Logged Punishment",
                description=("I have successfully logged the following punishment!"),
                color=GREEN_COLOR,
            )
            .add_field(
                name="Punishment",
                value=(
                    f"> **Player:** {warning.username}\n"
                    f"> **Moderator:** <@{warning.moderator_id}>\n"
                    f"> **Reason:** {warning.reason}\n"
                    f"> **At:** <t:{int(warning.time_epoch)}>\n"
                    f'{"> **Until:** <t:{}>{}".format(int(warning.until_epoch), newline) if warning.until_epoch is not None else ""}'
                    f"> **ID:** `{warning.snowflake}`"
                ),
                inline=False,
            )
            .set_thumbnail(url=thumbnail)
        )


    @punishments.command(
        name="analytics",
        description="View punishment analytics overview for the server.",
        extras={"category": "Punishments"},
    )
    @is_staff()
    @require_settings()
    @app_commands.describe(
        timeframe="The timeframe to analyze (e.g. '7d', '30d', '1w'). Leave blank for all time."
    )
    async def punishment_analytics(self, ctx: commands.Context, timeframe: typing.Optional[str] = None):
        page_aliases = {
            "overview": "Overview", "summary": "Overview", "stats": "Overview",
            "staff": "Staff", "moderators": "Staff", "mods": "Staff",
            "offenders": "Offenders", "repeat": "Offenders", "players": "Offenders",
        }
        start_alias = None
        if timeframe and timeframe.lower() in page_aliases:
            start_alias = timeframe.lower()
            timeframe = None

        gt_time = 0
        timeframe_label = "All Time"
        if timeframe and timeframe.lower() not in ["all", "total"]:
            gt_time = int(datetime.datetime.now().timestamp()) - time_converter(timeframe)
            timeframe_label = f"Last {timeframe}"

        now = int(datetime.datetime.now().timestamp())

        pipeline = [
            {"$match": {"Guild": ctx.guild.id, "Epoch": {"$gte": gt_time}}},
            {"$addFields": {"date": {"$toDate": {"$multiply": ["$Epoch", 1000]}}}},
            {"$facet": {
                "total": [{"$count": "count"}],
                "by_type": [
                    {"$group": {"_id": "$Type", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                ],
                "top_staff": [
                    {"$group": {"_id": "$ModeratorID", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 5},
                ],
                "top_offenders": [
                    {"$group": {"_id": {"user_id": "$UserID", "username": "$Username"}, "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 5},
                ],
                "busiest_day": [
                    {"$group": {"_id": {"$dayOfWeek": "$date"}, "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 1},
                ],
                "this_week": [
                    {"$match": {"Epoch": {"$gte": now - ONE_WEEK}}},
                    {"$count": "count"},
                ],
                "last_week": [
                    {"$match": {"Epoch": {"$gte": now - (2 * ONE_WEEK), "$lt": now - ONE_WEEK}}},
                    {"$count": "count"},
                ],
            }},
        ]

        result = [doc async for doc in await self.bot.punishments.db.aggregate(pipeline)]
        data = result[0]

        total = data["total"][0]["count"] if data["total"] else 0
        if total == 0:
            container = discord.ui.Container()
            container.add_item(discord.ui.TextDisplay("### Punishment Analytics\n> There are no punishments in this server for the selected timeframe."))
            return await ctx.send(view=discord.ui.LayoutView().add_item(container), allowed_mentions=discord.AllowedMentions.none())

        day_names = DAY_NAMES
        busiest_day = day_names.get(data["busiest_day"][0]["_id"], "Unknown") if data["busiest_day"] else "N/A"

        this_week_count = data["this_week"][0]["count"] if data["this_week"] else 0
        last_week_count = data["last_week"][0]["count"] if data["last_week"] else 0
        if last_week_count > 0:
            change_pct = ((this_week_count - last_week_count) / last_week_count) * 100
            trend_text = f"{'+' if change_pct >= 0 else ''}{change_pct:.0f}%"
        elif this_week_count > 0:
            trend_text = "New activity"
        else:
            trend_text = "No recent activity"

        type_breakdown = "\n".join(f"> **{r['_id']}:** {r['count']:,}" for r in data["by_type"])
        staff_lines = "\n".join(
            f"> **{i + 1}.** <@{item['_id']}> - {item['count']:,} punishments"
            for i, item in enumerate(data["top_staff"])
        )
        offender_lines = "\n".join(
            f"> **{i + 1}.** {item['_id'].get('username', 'Unknown')} - {item['count']:,} punishments"
            for i, item in enumerate(data["top_offenders"])
        )

        overview_page = discord.ui.Container()
        overview_page.add_item(discord.ui.TextDisplay(
            f"### Punishment Analytics\n"
            f"> **Timeframe:** {timeframe_label}\n"
            f"> **Total Punishments:** {total:,}\n"
            f"> **Busiest Day:** {busiest_day}\n"
            f"> **Week-over-Week:** {trend_text}"
        ))
        overview_page.add_item(discord.ui.Separator())
        overview_page.add_item(discord.ui.TextDisplay(
            f"**Breakdown by Type**\n{type_breakdown or '> None'}"
        ))

        staff_page = discord.ui.Container()
        staff_page.add_item(discord.ui.TextDisplay(
            f"### Punishment Analytics\n**Most Active Staff**\n{staff_lines or '> None'}"
        ))

        offender_page = discord.ui.Container()
        offender_page.add_item(discord.ui.TextDisplay(
            f"### Punishment Analytics\n**Top Repeat Offenders**\n{offender_lines or '> None'}"
        ))

        pages = [
            CustomPageV2(containers=[overview_page], identifier="Overview", aliases=["overview", "summary", "stats"]),
            CustomPageV2(containers=[staff_page], identifier="Staff", aliases=["staff", "moderators", "mods"]),
            CustomPageV2(containers=[offender_page], identifier="Offenders", aliases=["offenders", "repeat", "players"]),
        ]
        paginator = SelectPaginationV2(self.bot, ctx.author.id, pages)
        await ctx.send(view=paginator.get_current_view(alias=start_alias), allowed_mentions=discord.AllowedMentions.none())

    @punishments.command(
        name="staff",
        description="View detailed punishment stats for a specific staff member.",
        extras={"category": "Punishments"},
    )
    @is_staff()
    @require_settings()
    @app_commands.describe(
        member="The staff member to view stats for.",
        timeframe="The timeframe to analyze (e.g. '7d', '30d'). Leave blank for all time.",
    )
    async def punishment_staff(self, ctx: commands.Context, member: discord.Member, timeframe: typing.Optional[str] = None):
        gt_time = 0
        timeframe_label = "All Time"
        if timeframe and timeframe.lower() not in ["all", "total"]:
            gt_time = int(datetime.datetime.now().timestamp()) - time_converter(timeframe)
            timeframe_label = f"Last {timeframe}"

        pipeline = [
            {"$match": {"Guild": ctx.guild.id, "ModeratorID": member.id, "Epoch": {"$gte": gt_time}}},
            {"$addFields": {"date": {"$toDate": {"$multiply": ["$Epoch", 1000]}}}},
            {"$facet": {
                "total": [{"$count": "count"}],
                "by_type": [
                    {"$group": {"_id": "$Type", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                ],
                "by_hour": [
                    {"$group": {"_id": {"$hour": "$date"}, "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 3},
                ],
                "top_players": [
                    {"$group": {"_id": {"user_id": "$UserID", "username": "$Username"}, "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 5},
                ],
                "recent": [
                    {"$sort": {"Epoch": -1}},
                    {"$limit": 5},
                    {"$project": {"Username": 1, "Type": 1, "Epoch": 1}},
                ],
            }},
        ]

        result = [doc async for doc in await self.bot.punishments.db.aggregate(pipeline)]
        data = result[0]

        total = data["total"][0]["count"] if data["total"] else 0
        if total == 0:
            container = discord.ui.Container()
            container.add_item(discord.ui.TextDisplay(f"### Staff Analytics\n> <@{member.id}> has no punishments logged for the selected timeframe."))
            return await ctx.send(view=discord.ui.LayoutView().add_item(container), allowed_mentions=discord.AllowedMentions.none())

        type_breakdown = "\n".join(f"> **{r['_id']}:** {r['count']:,}" for r in data["by_type"])
        hour_lines = "\n".join(f"> **{r['_id']:02d}:00 UTC:** {r['count']:,}" for r in data["by_hour"])
        player_lines = "\n".join(
            f"> **{i + 1}.** {r['_id'].get('username', 'Unknown')} - {r['count']:,}"
            for i, r in enumerate(data["top_players"])
        )
        recent_lines = "\n".join(
            f"> **{r.get('Username', 'Unknown')}** - {r.get('Type', '?')} - <t:{int(r.get('Epoch', 0))}:R>"
            for r in data["recent"]
        )

        overview_page = discord.ui.Container()
        overview_page.add_item(discord.ui.TextDisplay(
            f"### Staff Analytics - {member.display_name}\n"
            f"> **Timeframe:** {timeframe_label}\n"
            f"> **Total Punishments:** {total:,}"
        ))
        overview_page.add_item(discord.ui.Separator())
        overview_page.add_item(discord.ui.TextDisplay(
            f"**By Type**\n{type_breakdown or '> None'}"
        ))
        overview_page.add_item(discord.ui.Separator())
        overview_page.add_item(discord.ui.TextDisplay(
            f"**Most Active Hours**\n{hour_lines or '> N/A'}"
        ))

        details_page = discord.ui.Container()
        details_page.add_item(discord.ui.TextDisplay(
            f"### Staff Analytics - {member.display_name}\n**Most Punished Players**\n{player_lines or '> None'}"
        ))
        details_page.add_item(discord.ui.Separator())
        details_page.add_item(discord.ui.TextDisplay(
            f"**Recent Punishments**\n{recent_lines or '> None'}"
        ))

        pages = [
            CustomPageV2(containers=[overview_page], identifier="Overview", aliases=["overview", "summary", "stats"]),
            CustomPageV2(containers=[details_page], identifier="Details", aliases=["details", "players", "recent"]),
        ]
        paginator = SelectPaginationV2(self.bot, ctx.author.id, pages)
        await ctx.send(view=paginator.get_current_view(), allowed_mentions=discord.AllowedMentions.none())

    @punishments.command(
        name="player",
        description="View punishment history and trends for a specific player.",
        extras={"category": "Punishments"},
    )
    @is_staff()
    @require_settings()
    @app_commands.autocomplete(user=user_autocomplete)
    @app_commands.describe(
        user="The Roblox username or Discord mention to look up.",
        timeframe="The timeframe to analyze (e.g. '7d', '30d'). Leave blank for all time.",
    )
    async def punishment_player(self, ctx: commands.Context, user: str, timeframe: typing.Optional[str] = None):
        gt_time = 0
        timeframe_label = "All Time"
        if timeframe and timeframe.lower() not in ["all", "total"]:
            gt_time = int(datetime.datetime.now().timestamp()) - time_converter(timeframe)
            timeframe_label = f"Last {timeframe}"

        roblox_user = await get_roblox_by_username(user, self.bot, ctx)
        if not roblox_user or roblox_user.get("errors"):
            return await ctx.send(
                embed=discord.Embed(
                    title="Could not find player",
                    description="I could not find a Roblox player with that username.",
                    color=BLANK_COLOR,
                )
            )

        pipeline = [
            {"$match": {"Guild": ctx.guild.id, "UserID": roblox_user["id"], "Epoch": {"$gte": gt_time}}},
            {"$facet": {
                "total": [{"$count": "count"}],
                "by_type": [
                    {"$group": {"_id": "$Type", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                ],
                "by_moderator": [
                    {"$group": {"_id": "$ModeratorID", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 5},
                ],
                "chronological": [
                    {"$sort": {"Epoch": 1}},
                    {"$project": {"Type": 1, "Epoch": 1, "ModeratorID": 1, "Reason": 1}},
                ],
            }},
        ]

        result = [doc async for doc in await self.bot.punishments.db.aggregate(pipeline)]
        data = result[0]

        total = data["total"][0]["count"] if data["total"] else 0
        if total == 0:
            container = discord.ui.Container()
            container.add_item(discord.ui.TextDisplay(f"### Player Analytics\n> **{roblox_user['name']}** has no punishments for the selected timeframe."))
            return await ctx.send(view=discord.ui.LayoutView().add_item(container), allowed_mentions=discord.AllowedMentions.none())

        all_punishments = data["chronological"]

        escalation = " → ".join(p.get("Type", "?") for p in all_punishments[-10:])

        if len(all_punishments) >= 2:
            gaps = [all_punishments[i]["Epoch"] - all_punishments[i - 1]["Epoch"] for i in range(1, len(all_punishments))]
            avg_gap = sum(gaps) / len(gaps)
            if avg_gap < 3600:
                avg_gap_text = f"{avg_gap / 60:.0f} minutes"
            elif avg_gap < 86400:
                avg_gap_text = f"{avg_gap / 3600:.1f} hours"
            else:
                avg_gap_text = f"{avg_gap / 86400:.1f} days"
        else:
            avg_gap_text = "N/A"

        try:
            roblox_player = await self.bot.roblox.get_user(roblox_user["id"])
            thumbnails = await self.bot.roblox.thumbnails.get_user_avatar_thumbnails(
                [roblox_player], type=roblox.thumbnails.AvatarThumbnailType.headshot
            )
            thumbnail = thumbnails[0].image_url
        except Exception:
            thumbnail = None

        type_breakdown = "\n".join(f"> **{r['_id']}:** {r['count']:,}" for r in data["by_type"])
        mod_lines = "\n".join(f"> <@{r['_id']}> - {r['count']:,}" for r in data["by_moderator"])
        recent_lines = "\n".join(
            f"> **{r.get('Type', '?')}** by <@{r.get('ModeratorID', 0)}> - <t:{int(r.get('Epoch', 0))}:R>\n> {r.get('Reason', 'No reason')}"
            for r in all_punishments[-5:]
        )

        header_text = (
            f"### Player Analytics - {roblox_user['name']}\n"
            f"> **Timeframe:** {timeframe_label}\n"
            f"> **Total Punishments:** {total:,}\n"
            f"> **Avg. Time Between:** {avg_gap_text}"
        )

        overview_page = discord.ui.Container()
        if thumbnail:
            section = discord.ui.Section(accessory=discord.ui.Thumbnail(media=thumbnail))
            section.add_item(header_text)
            overview_page.add_item(section)
        else:
            overview_page.add_item(discord.ui.TextDisplay(header_text))
        overview_page.add_item(discord.ui.Separator())
        overview_page.add_item(discord.ui.TextDisplay(
            f"**By Type**\n{type_breakdown or '> None'}"
        ))
        overview_page.add_item(discord.ui.Separator())
        overview_page.add_item(discord.ui.TextDisplay(
            f"**Issued By**\n{mod_lines or '> None'}"
        ))

        history_page = discord.ui.Container()
        history_page.add_item(discord.ui.TextDisplay(
            f"### Player Analytics - {roblox_user['name']}\n"
            f"**Escalation Pattern (Last 10)**\n> {escalation}" if escalation else
            f"### Player Analytics - {roblox_user['name']}\n**Escalation Pattern**\n> N/A"
        ))
        history_page.add_item(discord.ui.Separator())
        history_page.add_item(discord.ui.TextDisplay(
            f"**Recent Punishments**\n{recent_lines or '> None'}"
        ))

        pages = [
            CustomPageV2(containers=[overview_page], identifier="Overview", aliases=["overview", "summary", "stats"]),
            CustomPageV2(containers=[history_page], identifier="History", aliases=["history", "escalation", "recent"]),
        ]
        paginator = SelectPaginationV2(self.bot, ctx.author.id, pages)
        await ctx.send(view=paginator.get_current_view(), allowed_mentions=discord.AllowedMentions.none())

    @punishments.command(
        name="top",
        description="View the top repeat offenders in the server.",
        extras={"category": "Punishments"},
    )
    @is_staff()
    @require_settings()
    @app_commands.describe(
        timeframe="The timeframe to analyze (e.g. '7d', '30d'). Leave blank for all time.",
        type="Filter by punishment type (e.g. 'Warning', 'Ban').",
    )
    @app_commands.autocomplete(type=punishment_autocomplete)
    async def punishment_top(self, ctx: commands.Context, timeframe: typing.Optional[str] = None, type: typing.Optional[str] = None):
        gt_time = 0
        timeframe_label = "All Time"
        if timeframe and timeframe.lower() not in ["all", "total"]:
            gt_time = int(datetime.datetime.now().timestamp()) - time_converter(timeframe)
            timeframe_label = f"Last {timeframe}"

        match_filter = {"Guild": ctx.guild.id, "Epoch": {"$gte": gt_time}}
        if type:
            match_filter["Type"] = {"$regex": f"^{type}$", "$options": "i"}

        pipeline = [
            {"$match": match_filter},
            {"$facet": {
                "total": [{"$count": "count"}],
                "offenders": [
                    {"$group": {
                        "_id": {"user_id": "$UserID", "username": "$Username"},
                        "count": {"$sum": 1},
                        "latest": {"$max": "$Epoch"},
                        "types": {"$addToSet": "$Type"},
                    }},
                    {"$sort": {"count": -1}},
                    {"$limit": 20},
                ],
            }},
        ]

        result = [doc async for doc in await self.bot.punishments.db.aggregate(pipeline)]
        data = result[0]

        total = data["total"][0]["count"] if data["total"] else 0
        if total == 0:
            container = discord.ui.Container()
            container.add_item(discord.ui.TextDisplay("### Top Offenders\n> No punishments found for the selected filters."))
            return await ctx.send(view=discord.ui.LayoutView().add_item(container), allowed_mentions=discord.AllowedMentions.none())

        filter_text = f" ({type})" if type else ""
        offender_lines = "\n".join(
            f"> **{i + 1}.** {item['_id'].get('username', 'Unknown')} - **{item['count']:,}** punishments\n>    Types: {', '.join(item['types'])} | Last: <t:{int(item['latest'])}:R>"
            for i, item in enumerate(data["offenders"])
        )

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(
            f"### Top Offenders{filter_text}\n"
            f"> **{timeframe_label}** - {total:,} total punishments"
        ))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(offender_lines))

        await ctx.send(view=discord.ui.LayoutView().add_item(container), allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    await bot.add_cog(Punishments(bot))
