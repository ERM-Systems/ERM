import discord

from utils.constants import BLANK_COLOR
from utils.ingame_commands import (
    ACTIONS,
    INGAME_ACTIONS,
    PERMISSION_LEVELS,
    normalise_trigger,
)
from utils.utils import config_change_log, int_failure_embed


class InGameCommandModal(discord.ui.Modal, title="Add In-Game Command"):
    trigger = discord.ui.TextInput(
        label="Trigger",
        placeholder="e.g. punish",
        max_length=32,
    )
    action = discord.ui.TextInput(
        label="Action",
        placeholder=(
            "send_message, ping_role, move_to_voice, pm_player, ingame_message,"
            " ingame_hint"
        ),
        max_length=32,
    )
    channel = discord.ui.TextInput(
        label="Channel ID",
        placeholder="Discord actions only, or the fallback voice channel",
        max_length=32,
        required=False,
    )
    message = discord.ui.TextInput(
        label="Message",
        placeholder="{player} was punished for {argument}",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False,
    )
    extra = discord.ui.TextInput(
        label="Roles, Voice Channels or PM Target",
        placeholder=(
            "ping_role: role IDs, move_to_voice: 1=channel ID,"
            " pm_player: argument to PM the named player"
        ),
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False,
    )

    def __init__(self):
        super().__init__(timeout=600)
        self.interaction = None

    async def on_submit(self, interaction: discord.Interaction):
        self.interaction = interaction
        await interaction.response.defer(ephemeral=True, thinking=True)
        self.stop()


class RemoveInGameCommandModal(discord.ui.Modal, title="Remove In-Game Command"):
    trigger = discord.ui.TextInput(
        label="Trigger",
        placeholder="e.g. punish",
        max_length=32,
    )

    def __init__(self):
        super().__init__(timeout=600)
        self.interaction = None

    async def on_submit(self, interaction: discord.Interaction):
        self.interaction = interaction
        await interaction.response.defer(ephemeral=True, thinking=True)
        self.stop()


class InGameCommandPermissionModal(discord.ui.Modal, title="In-Game Command Access"):
    trigger = discord.ui.TextInput(
        label="Trigger",
        placeholder="e.g. punish",
        max_length=32,
    )
    level = discord.ui.TextInput(
        label="Required Access",
        placeholder="anyone, staff, admin, management or roles",
        max_length=32,
    )
    roles = discord.ui.TextInput(
        label="Allowed Roles",
        placeholder="Role IDs, only used when the access is set to roles",
        max_length=200,
        required=False,
    )

    def __init__(self):
        super().__init__(timeout=600)
        self.interaction = None

    async def on_submit(self, interaction: discord.Interaction):
        self.interaction = interaction
        await interaction.response.defer(ephemeral=True, thinking=True)
        self.stop()


class InGameCommands(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if interaction.user.id == self.user_id:
            return True

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Not Permitted",
                description="You are not permitted to interact with this menu.",
                color=BLANK_COLOR,
            ),
            ephemeral=True,
        )
        return False

    async def configuration(self, guild_id: int):
        settings = await self.bot.settings.find_by_id(guild_id)
        erlc = settings.setdefault("ERLC", {})
        configuration = erlc.setdefault("ingame_commands", {})
        configuration.setdefault("enabled", False)
        configuration.setdefault("commands", [])
        return settings, configuration

    async def refresh(self, guild: discord.Guild):
        if not self.message:
            return

        _, configuration = await self.configuration(guild.id)

        embed = discord.Embed(
            title="In-Game Commands", description="", color=BLANK_COLOR
        )
        embed.description += "**Status:** {}\n\n".format(
            "Enabled" if configuration["enabled"] else "Disabled"
        )
        for command in configuration["commands"]:
            embed.description += "> **;{}** runs `{}`\n".format(
                command.get("trigger", ""), command.get("action", "")
            )
        if not configuration["commands"]:
            embed.description += "> No commands configured.\n"

        embed.set_author(
            name=guild.name,
            icon_url=guild.icon.url if guild.icon else "",
        )

        try:
            await self.message.edit(embed=embed)
        except discord.HTTPException:
            pass

    @discord.ui.select(
        placeholder="In-Game Commands",
        row=0,
        options=[
            discord.SelectOption(
                label="Enabled",
                value="enabled",
                description="Custom commands run their configured action.",
            ),
            discord.SelectOption(
                label="Disabled",
                value="disabled",
                description="Custom commands are ignored.",
            ),
        ],
        max_values=1,
    )
    async def toggle(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()

        settings, configuration = await self.configuration(interaction.guild.id)
        configuration["enabled"] = select.values[0] == "enabled"
        await self.bot.settings.update_by_id(settings)
        await config_change_log(
            self.bot,
            interaction.guild,
            interaction.user,
            f"In-Game Commands {select.values[0]}",
        )
        await self.refresh(interaction.guild)

    @discord.ui.button(label="Add Command", style=discord.ButtonStyle.secondary, row=1)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = InGameCommandModal()
        await interaction.response.send_modal(modal)
        if await modal.wait():
            return

        trigger = normalise_trigger(modal.trigger.value)
        action = modal.action.value.strip().lower()

        if not trigger:
            return await int_failure_embed(
                modal.interaction, "that trigger is not usable.", ephemeral=True
            )

        if action not in ACTIONS:
            return await int_failure_embed(
                modal.interaction,
                "you must pick one of {}.".format(
                    ", ".join(f"`{name}`" for name in ACTIONS)
                ),
                ephemeral=True,
            )

        channel_value = modal.channel.value.strip()
        if channel_value and not channel_value.isdigit():
            return await int_failure_embed(
                modal.interaction, "that channel ID is not a number.", ephemeral=True
            )

        channel_id = int(channel_value) if channel_value else 0
        if action not in INGAME_ACTIONS and not channel_id:
            return await int_failure_embed(
                modal.interaction, "that action needs a channel ID.", ephemeral=True
            )

        message = modal.message.value.strip()
        if action != "move_to_voice" and not message:
            return await int_failure_embed(
                modal.interaction, "that action needs a message.", ephemeral=True
            )

        settings, configuration = await self.configuration(interaction.guild.id)
        previous = next(
            (
                command
                for command in configuration["commands"]
                if normalise_trigger(command.get("trigger")) == trigger
            ),
            {},
        )

        entry = {
            "trigger": trigger,
            "action": action,
            "channel": channel_id,
            "roles": [],
            "message": message,
            "pm_target": "caller",
            "permission": previous.get("permission")
                          or {"enabled": True, "level": "staff", "roles": []},
            "voice_channels": [],
        }

        extra = modal.extra.value.strip()
        if extra and action == "ping_role":
            entry["roles"] = [
                int(role) for role in extra.replace(",", " ").split() if role.isdigit()
            ][:5]
        elif extra and action == "pm_player":
            if extra.lower() == "argument":
                entry["pm_target"] = "argument"
        elif extra and action == "move_to_voice":
            for pair in extra.split(","):
                argument, _, target = pair.partition("=")
                if argument.strip() and target.strip().isdigit():
                    entry["voice_channels"].append(
                        {
                            "argument": argument.strip().lower(),
                            "channel": int(target.strip()),
                        }
                    )

        if action == "ping_role" and not entry["roles"]:
            return await int_failure_embed(
                modal.interaction,
                "that action needs at least one role ID.",
                ephemeral=True,
            )

        entries = [
            command
            for command in configuration["commands"]
            if normalise_trigger(command.get("trigger")) != trigger
        ]

        if len(entries) >= 25:
            return await int_failure_embed(
                modal.interaction,
                "you already have 25 in-game commands.",
                ephemeral=True,
            )

        entries.append(entry)
        configuration["commands"] = entries
        await self.bot.settings.update_by_id(settings)
        await config_change_log(
            self.bot,
            interaction.guild,
            interaction.user,
            f"In-Game Command Added: {trigger}",
        )
        await self.refresh(interaction.guild)

        await modal.interaction.followup.send(
            embed=discord.Embed(
                title="Command Added",
                description=f"**;{trigger}** now runs `{action}`.",
                color=BLANK_COLOR,
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="Permissions", style=discord.ButtonStyle.secondary, row=2)
    async def permissions(
            self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = InGameCommandPermissionModal()
        await interaction.response.send_modal(modal)
        if await modal.wait():
            return

        trigger = normalise_trigger(modal.trigger.value)
        level = modal.level.value.strip().lower()

        if level != "anyone" and level not in PERMISSION_LEVELS:
            return await int_failure_embed(
                modal.interaction,
                "you must pick `anyone`, or one of {}.".format(
                    ", ".join(f"`{name}`" for name in PERMISSION_LEVELS)
                ),
                ephemeral=True,
            )

        settings, configuration = await self.configuration(interaction.guild.id)
        entry = next(
            (
                command
                for command in configuration["commands"]
                if normalise_trigger(command.get("trigger")) == trigger
            ),
            None,
        )

        if not entry:
            return await int_failure_embed(
                modal.interaction,
                f"no command is using **;{trigger}**.",
                ephemeral=True,
            )

        roles = [
            int(role)
            for role in modal.roles.value.replace(",", " ").split()
            if role.isdigit()
        ][:10]

        entry["permission"] = {
            "enabled": level != "anyone",
            "level": "staff" if level == "anyone" else level,
            "roles": roles,
        }

        await self.bot.settings.update_by_id(settings)
        await config_change_log(
            self.bot,
            interaction.guild,
            interaction.user,
            f"In-Game Command Permission Set: {trigger} ({level})",
        )
        await self.refresh(interaction.guild)

        await modal.interaction.followup.send(
            embed=discord.Embed(
                title="Permission Updated",
                description=f"**;{trigger}** is now limited to `{level}`.",
                color=BLANK_COLOR,
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="Remove Command", style=discord.ButtonStyle.danger, row=1)
    async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveInGameCommandModal()
        await interaction.response.send_modal(modal)
        if await modal.wait():
            return

        trigger = normalise_trigger(modal.trigger.value)
        settings, configuration = await self.configuration(interaction.guild.id)
        entries = [
            command
            for command in configuration["commands"]
            if normalise_trigger(command.get("trigger")) != trigger
        ]

        if len(entries) == len(configuration["commands"]):
            return await int_failure_embed(
                modal.interaction,
                f"no command is using **;{trigger}**.",
                ephemeral=True,
            )

        configuration["commands"] = entries
        await self.bot.settings.update_by_id(settings)
        await config_change_log(
            self.bot,
            interaction.guild,
            interaction.user,
            f"In-Game Command Removed: {trigger}",
        )
        await self.refresh(interaction.guild)

        await modal.interaction.followup.send(
            embed=discord.Embed(
                title="Command Removed",
                description=f"**;{trigger}** has been deleted.",
                color=BLANK_COLOR,
            ),
            ephemeral=True,
        )
