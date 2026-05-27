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
        return await ctx.reply(f"{errorEmoji} **{ctx.author.mention}**, this command has been removed from ERM. Please configure infractions on the dashboard instead of here")

async def setup(bot):
    await bot.add_cog(StaffConduct(bot))
