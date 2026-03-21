
# Staff conduct is borked. Nothing saves so it needs to be redone, so I'm disabling infractions until they work properly.

import datetime
import discord
import pytz
from discord.ext import commands
from erm import is_management
from menus import (
    YesNoMenu,
    AcknowledgeMenu,
    YesNoExpandedMenu,
    CustomModalView,
    CustomSelectMenu,
    MultiSelectMenu,
    RoleSelect,
    ExpandedRoleSelect,
    MessageCustomisation,
    EmbedCustomisation,
    ChannelSelect,
)
from erm import Bot
from utils.constants import base_infraction_type
from utils.autocompletes import infraction_type_autocomplete_special
import asyncio
import logging


successEmoji = "<:ERMCheck:1111089850720976906>"
pendingEmoji = "<:ERMPending:1111097561588183121>"
errorEmoji = "<:ERMClose:1111101633389146223>"
embedColour = 0xED4348


class StaffConduct(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot

    
    async def check_settings(self, ctx: commands.Context):
        error_text = "<:ERMClose:1111101633389146223> **{},** this server isn't setup with ERM! Please run `/setup` to setup the bot before trying to manage infractions".format(
            ctx.author.name
        )
        guild_settings = await self.bot.settings.find_by_id(ctx.guild.id)
        if not guild_settings:
            await ctx.reply(error_text)
            return -1
        # Currently only infractions are developed for this
        if guild_settings.get("infractions") is not None:
            return 1
        else:
            return 0

    @commands.hybrid_group(
        name="infraction",
        description="Manage infractions with ease!",
        extras={"category": "Staff Conduct"},
    )
    @is_management()
    async def infraction(self, ctx: commands.Context):
        pass

    @infraction.command(
        name="manage",
        description="Manage staff infractions, staff conduct, and custom integrations!",
        extras={"category": "Staff Conduct"},
    )
    @is_management()
    async def manage(self, ctx: commands.Context):
        bot = self.bot
        guild_settings = await bot.settings.find_by_id(ctx.guild.id)
        
        result = await self.check_settings(ctx)
        if result == -1:
            return
        first_time_setup = bool(not result)
        message = await ctx.reply(
            f"{pendingEmoji} **{ctx.author.name},** welcome to the set-up for **Staff Conduct**! Please wait while your experience loads.",
        )
        # I'm going to kill whoever made it so you can't edit your already made config for staff conduct. you made my life harder
        if first_time_setup:
            guild_settings["infractions"] = {"infractions": []}
            view = YesNoExpandedMenu(ctx.author.id)
            await message.edit(
                content=f"{pendingEmoji} **{ctx.author.name},** it looks like your server hasn't setup **Staff Conduct**! Do you want to run the **First-time Setup** wizard?",
                view=view,
            )
            timeout = await view.wait()
            if timeout:
                return
            if not view.value:
                await message.edit(
                    content=f"{errorEmoji} **{ctx.author.name},** I have cancelled the setup wizard for **Staff Conduct.**",
                    view=None,
                )
                return

            embed = discord.Embed(
                title="<:ERMAlert:1113237478892130324> Information", color=embedColour
            )
            embed.set_thumbnail(
                url="https://cdn.discordapp.com/emojis/1113210855891423302.webp?size=96&quality=lossless"
            )
            embed.add_field(
                name="<:ERMList:1111099396990435428> What is Staff Conduct?",
                value=">>> Staff Conduct is a module within ERM which allows for infractions on your Staff team. Not only does it allow for manual punishments and infractions to others to be expanded and customised, it also allows for automatic punishments for those that don't meet activity requirements, integrating with other ERM modules.",
                inline=False,
            )
            embed.add_field(
                name="<:ERMList:1111099396990435428> How does this module work?",
                value=">>> For manual punishment assignment, you make your own Infraction Types, as dictated throughout this setup wizard. You can then infract staff members by using `/infract`, which will assign that Infraction Type to the staff individual. You will be able to see all infractions that individual has received, as well as any notes or changes that have been made over the course of their staff career.",
                inline=False,
            )
            embed.add_field(
                name="<:ERMList:1111099396990435428> If I have a Strike 1/2/3 system, do I have them as separate types?",
                value=">>> Curerently, you do have to manually do this yourself, however, it is coming soon!",
                inline=False,
            )
            embed.set_footer(
                text="This module is in beta, and bugs are to be expected. If you notice a problem with this module, report it via our Support server."
            )
            embed.timestamp = datetime.datetime.now()
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)

            view = AcknowledgeMenu(
                ctx.author.id, "Read the information in full before acknowledging."
            )
            await message.edit(
                content=f"{pendingEmoji} **{ctx.author.name},** please read all the information below before continuing.",
                embed=embed,
                view=view,
            )
            timeout = await view.wait()
            if timeout or not view.value:
                return
        while True:
            ac = await infraction_type_autocomplete_special(ctx.guild.id, bot)
            values = [
                discord.SelectOption(label = "Add Item", value = "add", emoji="<:ERMAdd:1113207792854106173>"),
                
            ] + ac
            values += [discord.SelectOption(label = "Finish", value = "finish", emoji = successEmoji)]
            await message.edit(
                content=f"{pendingEmoji} **{ctx.author.name},** select an option from the dropdown in order to configure the bot!",
                embed=None,
                view=(
                    view := CustomSelectMenu(
                        ctx.author.id,
                        options = values,
                        limit=1
                    )
                ),
            )
            timeout = await view.wait()
            if timeout:
                return
            if view.value == "add":
                await message.edit(
                    content=f"{pendingEmoji} **{ctx.author.name},** click the button below!",
                    embed=None,
                    view=(
                        view := CustomModalView(
                            ctx.author.id,
                            "Add an Infraction Type",
                            "Add Infraction Type",
                            [
                                (
                                    "type_name",
                                    discord.ui.TextInput(
                                        placeholder="e.g. Strike, Termination, Suspension, Blacklist",
                                        label="Name of Infraction Type",
                                    ),
                                )
                            ],
                        )
                    ),
                )
                await view.wait()
                if any(type["name"] == view.modal.type_name.value for type in guild_settings["infractions"]["infractions"]):
                    return await message.edit(
                        content = f"{errorEmoji} **{ctx.author.name},** this infraction type already exists"
                    )
                try:
                    infraction_type_name = view.modal.type_name.value
                except AttributeError:
                    return
                base_type = base_infraction_type
                base_type["name"] = infraction_type_name
                guild_settings["infractions"]["infractions"].append(base_type)
            elif view.value == "finish":
                await message.edit(
                    content=f"{successEmoji} **{ctx.author.name},** have a great day!",
                    embed=None,
                    view=None
                )
                return
            else:
                infraction_type_name = view.value
                base_type = [type for type in guild_settings["infractions"]["infractions"] if type["name"] == infraction_type_name][0]
            
            # This continuously iterates until they're done with this type. The view will probably expire before then so oh well...
            while True:
                await message.edit(
                    content=f"{pendingEmoji} **{ctx.author.name},** what actions do you want to add to **{infraction_type_name}**?",
                    view=(
                        view := CustomSelectMenu(
                            ctx.author.id,
                            [
                                discord.SelectOption(
                                    label="Add Role",
                                    description='Add a role, such as a "Strike" role to the individual',
                                    emoji="<:ERMAdd:1113207792854106173>",
                                    value="add_role",
                                ),
                                discord.SelectOption(
                                    label="Remove Role",
                                    description='Remove an individual role, such as "Trained", from an individual.',
                                    emoji="<:ERMRemove:1113207777662345387>",
                                    value="remove_role",
                                ),
                                discord.SelectOption(
                                    label="Send Message in Channel",
                                    description="Send a Custom Message in a Channel",
                                    emoji="<:ERMLog:1113210855891423302>",
                                    value="send_message",
                                ),
                                discord.SelectOption(
                                    label="Escalate",
                                    description="Escalate this infraction if too many of them occur",
                                    emoji="<:ERMLog:1113210855891423302>",
                                    value="escalate",
                                ),
                                discord.SelectOption(
                                    label = "Finish",
                                    description="Finish setting up this infraction type",
                                    value = "finish",
                                    emoji = successEmoji
                                )
                            ],
                        )
                    ),
                )

                await view.wait()

                value: list | None = None
                if isinstance(view.value, str):
                    value = view.value
                elif isinstance(view.value, list):
                    value = view.value[0]
                # WE NEED TO MAKE THESE MESSAGES MORE NOTICABLE FOR WHICH YOU PICKED
                # noticeable* 🤓
                # lol

                # Idk who's idea it was to use an if chain here but now it's match-case
                match value:
                    case "add_role":
                        await message.edit(
                            content=f"{pendingEmoji} **{ctx.author.name},** what roles do you wish to be assigned when \
                        a user receives a **{infraction_type_name}**?",
                            view=(view := ExpandedRoleSelect(ctx.author.id, limit=25)),
                        )
                        await view.wait()
                        addRoleList = [role.id for role in view.value]
                        base_type["role_changes"]["add"]["roles"] = addRoleList
                    case "remove_role":  # Add to Database. I'VE ADDED IT TO DATABASE BUDDY
                        await message.edit(
                            content=f"{pendingEmoji} **{ctx.author.name},** what roles do you wish to be removed when \
    a user receives a **{infraction_type_name}**?",
                            view=(view := ExpandedRoleSelect(ctx.author.id, limit=25)),
                        )
                        await view.wait()
                        removeRoleList = [role.id for role in view.value]
                        base_type["role_changes"]["add"]["roles"] = removeRoleList

                    case "send_message":
                        constant_msg_data = None
                        # Get Channel(s) to Send Message To
                        await message.edit(
                            content=f"{pendingEmoji} **{ctx.author.name},** please select the channel(s) you wish to send a message to upon a user receiving a **{infraction_type_name}**.",
                            view=(view := ChannelSelect(ctx.author.id, limit=5)),
                        )
                        await view.wait()

                        # Get Custom Message
                        view = MessageCustomisation(
                            ctx.author.id, persist=True, external=True
                        )
                        await message.edit(content=None, view=view)
                        await view.wait()
                        
                        updated_message = await ctx.channel.fetch_message(message.id)
                        message_data = {
                            "content": (
                                updated_message.content
                                if updated_message.content
                                != f"{pendingEmoji} **{ctx.author.name},** please set the message you wish to send a user upon receiving a **{infraction_type_name}**."
                                else ""
                            ),
                            "embeds": [i.to_dict() for i in updated_message.embeds],
                        }
                        yesNoValue = YesNoMenu(ctx.author.id)
                        await message.edit(
                            content=f"{pendingEmoji} **{ctx.author.name},** please confirm below that you wish to use the content shown below.\n\n{message_data['content']}",
                            embeds=[
                                discord.Embed.from_dict(i)
                                for i in message_data["embeds"]
                            ],
                            view=yesNoValue,
                        )
                        await yesNoValue.wait()
                        if yesNoValue.value:
                            break
                        elif not yesNoValue.value:
                            constant_msg_data = message_data
                        base_type["notifications"]["dm"] = constant_msg_data
                        base_type["notifications"]["dm"]["enabled"] = True

                    case "escalate":
                        types = await infraction_type_autocomplete_special(ctx.guild.id, bot) + [discord.SelectOption(label="Back", description="Head back to the previous menu", value="back")]
                        type = infraction_type_name
                        while type == infraction_type_name:
                            await message.edit(
                                content=f"{pendingEmoji} **{ctx.author.name},** what infraction type should this escalate to?.",
                                view=(view := CustomSelectMenu(
                                    ctx.author.id,
                                    types
                                    )
                                ),)
                            
                            await view.wait()
                            type = view.value
                            if type == "back":
                                break
                            if type == infraction_type_name:
                                await message.edit(
                                    content=f"{errorEmoji} **{ctx.author.name},** an infraction type cannot escalate to the same infraction type!.",view=None
                                )
                                await asyncio.sleep(2)

                        if type == "back":
                            continue
                        await message.edit(
                            content=f"{pendingEmoji} **{ctx.author.name},** how many infractions of the infraction type you're editing should be issued for this user before it's escalated?",
                            view = (view := CustomModalView(
                                ctx.author.id,
                                "Change threshold",
                                "Enter an infraction threshold",
                                [
                                    (
                                        "threshold",
                                        discord.ui.TextInput(label="Enter the threshold as a number only", style=discord.TextStyle.short)
                                    )
                                ]
                            ))
                        )
                        await view.wait()
                        # i dont think unknown will like this :(
                        while True:
                            try:
                                threshold = int(view.modal.threshold.value)
                                break
                            except TypeError:
                                await message.edit(
                                    content=f"{errorEmoji} **{ctx.author.name},** the value you entered is not a number. How many infractions of the infraction type you're editing should be issued for this user before it's escalated?",
                                    view = (view := CustomModalView(
                                        ctx.author.id,
                                        "Change threshold",
                                        "Enter an infraction threshold",
                                        [
                                            (
                                                "threshold",
                                                discord.ui.TextInput(style=discord.TextStyle.short)
                                            )
                                        ]
                                    ))
                                )
                                await view.wait()
                        base_type["escalation"] = {
                            "threshold": threshold,
                            "next_infraction": type
                        }
                    case "finish":
                        try:
                            await self.bot.settings.update(guild_settings)
                        except ValueError: # If nothing changes this loves to error out. idk why but don't ask me, probably a pymongo thing
                            logging.warning("_id failure")
                            pass
                        await message.edit(
                            content=f"{successEmoji} **{infraction_type_name}** has been successfully submitted!",
                            view=None,
                            embed=None,
                        )
                        break

async def setup(bot):
    await bot.add_cog(StaffConduct(bot))
