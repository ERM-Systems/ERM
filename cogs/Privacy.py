import datetime
import discord
from discord.ext import commands
from utils.constants import BLANK_COLOR
from utils.utils import generalised_interaction_check_failure

class Privacy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    class ConsentContainer(discord.ui.Container):
        def __init__(self, bot, user: discord.Member, data):
            super().__init__()
            self.bot = bot
            self.user = user
            self.action_row = discord.ui.ActionRow()
            self.add_item(discord.ui.Section(discord.ui.TextDisplay(
                (
                    "### User Configurations\n"
                    "This is where you can select your opted in features for ERM. All of these are on by default, however, you can change the status of these.\n\n"
                    "**Configurations**\n"
                    "> **Punishment Alerts**: Toggle being alerted when you are punished.\n"
                    "> **Shift Logging**: Consent to your shifts being logged by ERM.\n"
                    "> **Automatic Shifts**: Allow shifts to be started when you join a server you are a moderator in."
                )
            ), accessory=discord.ui.Thumbnail(media=user.avatar.with_format("png").url))).add_item(discord.ui.Separator())
            self.punishments_button = discord.ui.Button(label = "Punishment Alerts", emoji=bot.emoji_controller.get_emoji('check') if data.get("punishments", True) is True else bot.emoji_controller.get_emoji('xmark'), style=discord.ButtonStyle.green if data.get("punishments", True) is True else discord.ButtonStyle.red)
            self.shift_button = discord.ui.Button(label = "Shift Logging", emoji=bot.emoji_controller.get_emoji('check') if data.get("shift_reports", True) is True else bot.emoji_controller.get_emoji('xmark'), style=discord.ButtonStyle.green if data.get("shift_reports", True) is True else discord.ButtonStyle.red)
            self.automatic_shifts = discord.ui.Button(label = "Automatic Shifts", emoji=bot.emoji_controller.get_emoji('check') if data.get("automatic_shifts", True) is True else bot.emoji_controller.get_emoji('xmark'), style=discord.ButtonStyle.green if data.get("automatic_shifts", True) is True else discord.ButtonStyle.red)
            self.punishments_button.callback = self.punishments_enabled
            self.shift_button.callback = self.shift_logging_enabled
            self.automatic_shifts.callback = self.auto_shifts_enabled

            self.action_row.add_item(
                self.punishments_button
            ).add_item(
                self.shift_button
            ).add_item(
                self.automatic_shifts
            )
            self.add_item(self.action_row)
        async def punishments_enabled(self, interaction: discord.Interaction):
            enabled = True
            async for document in self.bot.consent.db.find({"_id": interaction.user.id}):
                enabled = (
                    document.get("punishments")
                    if document.get("punishments") is not None
                    else True
                )
            status = not enabled
            await self.bot.consent.upsert(
                {"_id": interaction.user.id, "punishments": status}
            )
            self.punishments_button.style = discord.ButtonStyle.green if status else discord.ButtonStyle.red
            self.punishments_button.emoji = self.bot.emoji_controller.get_emoji('check') if status else self.bot.emoji_controller.get_emoji('xmark')
            await interaction.response.edit_message(view=self.view)

        async def shift_logging_enabled(self, interaction: discord.Interaction):
            enabled = True
            async for document in self.bot.consent.db.find({"_id": interaction.user.id}):
                enabled: bool = (
                    document.get("shift_reports")
                    if document.get("shift_reports") is not None
                    else True
                )
            status = not enabled
            await self.bot.consent.upsert(
                {"_id": interaction.user.id, "shift_reports": status}
            )
            self.shift_button.style = discord.ButtonStyle.green if status else discord.ButtonStyle.red
            self.shift_button.emoji = self.bot.emoji_controller.get_emoji('check') if status else self.bot.emoji_controller.get_emoji('xmark')
            await interaction.response.edit_message(view=self.view)
            
        async def auto_shifts_enabled(self, interaction: discord.Interaction):
            enabled = True
            async for document in self.bot.consent.db.find({"_id": interaction.user.id}):
                enabled: bool = (
                    document.get("automatic_shifts")
                    if document.get("automatic_shifts") is not None
                    else True
                )
            status = not enabled
            await self.bot.consent.upsert(
                {"_id": interaction.user.id, "automatic_shifts": status}
            )
            self.automatic_shifts.style = discord.ButtonStyle.green if status else discord.ButtonStyle.red
            self.automatic_shifts.emoji = self.bot.emoji_controller.get_emoji('check') if status else self.bot.emoji_controller.get_emoji('xmark')
            await interaction.response.edit_message(view=self.view)
        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.user.id != self.user.id:
                await interaction.response.defer()
                await generalised_interaction_check_failure(interaction.followup)
                return False
            return True
    @commands.guild_only()
    @commands.hybrid_command(
        name="consent",
        description="Change your privacy settings.",
        extras={"category": "Privacy"},
    )
    async def consent(self, ctx: commands.Context):
        bot = self.bot
        data = await bot.consent.find_by_id(ctx.author.id)

        view = discord.ui.LayoutView()
        view.add_item(self.ConsentContainer(self.bot, ctx.author, data))
        await ctx.reply(view=view)


async def setup(bot):
    await bot.add_cog(Privacy(bot))
