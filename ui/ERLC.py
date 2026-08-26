from discord.ext import commands
from utils.constants import blank_color
from utils.utils import config_change_log
import discord
import typing

class callSignCheck(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: int, settings: dict = None):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id
        self.settings = settings or {}

        self.enabled_select = discord.ui.Select(
            placeholder="Select an option...",
            options=[
                discord.SelectOption(label="Enabled", value="enabled"),
                discord.SelectOption(label="Disabled", value="disabled"),
            ]
        )
        self.enabled_select.callback = self.enabled_callback
        self.add_item(self.enabled_select)

        self.add_whitelist_button = discord.ui.Button(
            label="Add Whitelist",
            style=discord.ButtonStyle.green,
            custom_id="add_whitelist"
        )
        self.add_whitelist_button.callback = self.add_whitelist_callback
        self.add_item(self.add_whitelist_button)

        self.delete_whitelist_button = discord.ui.Button(
            label="Delete Whitelist",
            style=discord.ButtonStyle.red,
            custom_id="delete_whitelist"
        )
        self.delete_whitelist_button.callback = self.delete_whitelist_callback
        self.add_item(self.delete_whitelist_button)

    async def enabled_callback(self, interaction: discord.Interaction):
        selected_value = self.enabled_select.values[0]
        sett = await self.bot.settings.find_by_id(interaction.guild.id)
        if not sett:
            sett = {}

        sett['ERLC']['callsign_check'] = {
            'enabled': selected_value == 'enabled'
        }
        await self.bot.settings.update_by_id(sett)

        embed = discord.Embed(
            title="Call Sign Check Status Updated",
            description=f"Call Sign Check is now **{selected_value.capitalize()}**.",
            color=blank_color
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def add_whitelist_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="This is a add whitelist UI",
            description="DUMMY",
            color=blank_color
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def delete_whitelist_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="This is a delete whitelist UI",
            description="DUMMY",
            color=blank_color
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class PMTargetMenu(discord.ui.View):
    def __init__(
        self,
        user_id: int,
        team: typing.Optional[str],
        usernames: list,
        team_count: int,
    ):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.value = None
        self.message = None

        options = []
        if team is not None:
            options.append(
                discord.SelectOption(
                    label=f"{team} Team",
                    description=(
                        f"All {team_count} player(s) currently on the {team} team."
                    ),
                    value="team",
                )
            )
        options.extend(
            discord.SelectOption(
                label=username,
                description="This player only.",
                value=f"player:{username}",
            )
            for username in usernames[:24]
        )

        self.target_select = discord.ui.Select(
            placeholder="Select who should receive this PM...",
            options=options,
        )
        self.target_select.callback = self.target_callback
        self.add_item(self.target_select)

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Not Permitted",
                description="You are not permitted to interact with this menu.",
                color=blank_color,
            ),
            ephemeral=True,
        )
        return False

    async def target_callback(self, interaction: discord.Interaction):
        self.value = self.target_select.values[0]
        self.target_select.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self) -> None:
        self.target_select.disabled = True
        if not self.message:
            return
        try:
            await self.message.edit(
                embed=discord.Embed(
                    title="Timed Out",
                    description="You did not select a target in time.",
                    color=blank_color,
                ),
                view=self,
            )
        except discord.HTTPException:
            pass