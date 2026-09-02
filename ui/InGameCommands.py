import discord

from utils.constants import BLANK_COLOR, GREEN_COLOR
from utils.ingame_commands import normalise_trigger
from utils.utils import config_change_log, generator, int_failure_embed

ACTION_CHOICES = (
    ("send_message", "Send a Message", "Post a message into a Discord channel."),
    ("ping_role", "Ping a Role", "Post a message that mentions roles."),
    ("move_to_voice", "Move to Voice", "Move the caller into a voice channel."),
    ("pm_player", "PM a Player", "Send a private message in-game."),
    ("ingame_message", "In-Game Message", "Announce a message in-game."),
    ("ingame_hint", "In-Game Hint", "Send a hint in-game."),
)

PERMISSION_CHOICES = (
    ("anyone", "Anyone", "Any player may run this command."),
    ("staff", "Staff", "Staff members only."),
    ("admin", "Administrators", "Server administrators only."),
    ("management", "Management", "Management only."),
    ("roles", "Specific Roles", "Only members holding the roles you pick."),
)

ACTION_LABELS = {value: label for value, label, _ in ACTION_CHOICES}
PERMISSION_LABELS = {value: label for value, label, _ in PERMISSION_CHOICES}

TEXT_ACTIONS = ("send_message", "ping_role")


def default_entry(trigger: str, author_id: int) -> dict:
    return {
        "id": next(generator),
        "trigger": trigger,
        "action": "send_message",
        "channel": 0,
        "roles": [],
        "message": "",
        "pm_target": "caller",
        "voice_channels": [],
        "author": author_id,
        "permission": {"enabled": True, "level": "staff", "roles": []},
    }


def access_level(entry: dict) -> str:
    permission = entry.get("permission") or {}
    if not permission.get("enabled"):
        return "anyone"
    return permission.get("level", "staff")


def details(entry: dict) -> str:
    return (
        "> **Trigger:** ;{}\n".format(entry.get("trigger", "Unknown"))
        + "> **Command ID:** `{}`\n".format(entry.get("id", "N/A"))
        + "> **Action:** {}\n".format(
            ACTION_LABELS.get(entry.get("action"), "Unconfigured")
        )
        + "> **Access:** {}\n".format(
            PERMISSION_LABELS.get(access_level(entry), "Staff")
        )
        + "> **Creator:** <@{}>".format(entry.get("author", 0))
    )


def overview(guild: discord.Guild, commands: list) -> discord.Embed:
    embed = discord.Embed(title="In-Game Commands", color=BLANK_COLOR)
    for entry in commands:
        embed.add_field(
            name=";{}".format(entry.get("trigger", "Unknown")),
            value=details(entry),
            inline=False,
        )

    if not embed.fields:
        embed.add_field(
            name="No In-Game Commands",
            value="> No in-game commands were found to be associated with this server.",
            inline=False,
        )

    embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else "")
    return embed


class TriggerModal(discord.ui.Modal):
    def __init__(
        self,
        title: str,
        label: str = "Command Name",
        placeholder: str = "e.g. punish",
    ):
        super().__init__(title=title, timeout=600)
        self.trigger = discord.ui.TextInput(
            label=label,
            placeholder=placeholder,
            max_length=32,
        )
        self.add_item(self.trigger)
        self.interaction = None

    async def on_submit(self, interaction: discord.Interaction):
        self.interaction = interaction
        await interaction.response.defer()
        self.stop()


class MessageModal(discord.ui.Modal, title="Edit Message"):
    def __init__(self, current: str):
        super().__init__(timeout=600)
        self.message = discord.ui.TextInput(
            label="Message",
            placeholder="{player} was punished for {argument}",
            style=discord.TextStyle.paragraph,
            max_length=500,
            default=current or None,
            required=False,
        )
        self.add_item(self.message)
        self.interaction = None

    async def on_submit(self, interaction: discord.Interaction):
        self.interaction = interaction
        await interaction.response.defer()
        self.stop()


class OwnedView(discord.ui.View):
    def __init__(self, user_id: int, timeout: int = 600):
        super().__init__(timeout=timeout)
        self.user_id = user_id

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


class InGameCommandPermissions(OwnedView):
    def __init__(self, user_id: int, entry: dict, parent):
        super().__init__(user_id)
        self.entry = entry
        self.parent = parent
        self.build()

    def build(self):
        self.clear_items()
        level = access_level(self.entry)

        self.access = discord.ui.Select(
            placeholder="Who may run this command",
            row=0,
            options=[
                discord.SelectOption(
                    label=label,
                    value=value,
                    description=description,
                    default=value == level,
                )
                for value, label, description in PERMISSION_CHOICES
            ],
        )
        self.access.callback = self.access_callback
        self.add_item(self.access)

        if level == "roles":
            permission = self.entry.get("permission") or {}
            self.roles = discord.ui.RoleSelect(
                placeholder="Allowed Roles",
                row=1,
                min_values=0,
                max_values=10,
                default_values=[
                    discord.Object(id=role) for role in permission.get("roles") or []
                ],
            )
            self.roles.callback = self.roles_callback
            self.add_item(self.roles)

    async def apply(self, interaction: discord.Interaction):
        self.build()
        await interaction.response.edit_message(view=self)
        await self.parent.refresh()

    async def access_callback(self, interaction: discord.Interaction):
        value = self.access.values[0]
        permission = self.entry.setdefault(
            "permission", {"enabled": True, "level": "staff", "roles": []}
        )
        permission["enabled"] = value != "anyone"
        if value != "anyone":
            permission["level"] = value
        await self.apply(interaction)

    async def roles_callback(self, interaction: discord.Interaction):
        permission = self.entry.setdefault(
            "permission", {"enabled": True, "level": "roles", "roles": []}
        )
        permission["roles"] = [role.id for role in self.roles.values]
        await self.apply(interaction)


class InGameCommandModification(OwnedView):
    def __init__(self, user_id: int, entry: dict):
        super().__init__(user_id)
        self.entry = entry
        self.message = None
        self.saved = False
        self.build()

    def summary(self, guild: discord.Guild) -> discord.Embed:
        action = self.entry.get("action")
        level = access_level(self.entry)

        description = (
            "**Command Information**\n"
            + "> **Command ID:** `{}`\n".format(self.entry.get("id", "N/A"))
            + "> **Trigger:** ;{}\n".format(self.entry.get("trigger", ""))
            + "> **Action:** {}\n".format(ACTION_LABELS.get(action, "Unconfigured"))
            + "> **Access:** {}\n".format(PERMISSION_LABELS.get(level, "Staff"))
            + "> **Creator:** <@{}>\n".format(self.entry.get("author", 0))
        )

        if level == "roles":
            roles = (self.entry.get("permission") or {}).get("roles") or []
            description += "> **Allowed Roles:** {}\n".format(
                ", ".join(f"<@&{role}>" for role in roles) if roles else "None selected"
            )

        if action in TEXT_ACTIONS or action == "move_to_voice":
            channel = self.entry.get("channel")
            description += "> **Channel:** {}\n".format(
                f"<#{channel}>" if channel else "None selected"
            )

        if action == "ping_role":
            roles = self.entry.get("roles") or []
            description += "> **Mentioned Roles:** {}\n".format(
                ", ".join(f"<@&{role}>" for role in roles) if roles else "None selected"
            )

        if action == "pm_player":
            description += "> **Recipient:** {}\n".format(
                "The player named in the argument"
                if self.entry.get("pm_target") == "argument"
                else "The player who ran the command"
            )

        if action != "move_to_voice":
            description += "\n**Message**\n> {}".format(
                self.entry.get("message") or "No message set."
            )

        embed = discord.Embed(
            title="In-Game Commands", description=description, color=BLANK_COLOR
        )
        embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else "")
        return embed

    def complete(self) -> bool:
        action = self.entry.get("action")
        if action != "move_to_voice" and not self.entry.get("message"):
            return False
        if action in TEXT_ACTIONS and not self.entry.get("channel"):
            return False
        if action == "move_to_voice" and not self.entry.get("channel"):
            return False
        if action == "ping_role" and not self.entry.get("roles"):
            return False
        return True

    def build(self):
        self.clear_items()
        action = self.entry.get("action")

        self.action_select = discord.ui.Select(
            placeholder="What this command does",
            row=0,
            options=[
                discord.SelectOption(
                    label=label,
                    value=value,
                    description=description,
                    default=value == action,
                )
                for value, label, description in ACTION_CHOICES
            ],
        )
        self.action_select.callback = self.action_callback
        self.add_item(self.action_select)

        channel = self.entry.get("channel")
        if action in TEXT_ACTIONS:
            self.channel_select = discord.ui.ChannelSelect(
                placeholder="Channel to post in",
                row=1,
                min_values=0,
                max_values=1,
                channel_types=[discord.ChannelType.text],
                default_values=[discord.Object(id=channel)] if channel else [],
            )
            self.channel_select.callback = self.channel_callback
            self.add_item(self.channel_select)
        elif action == "move_to_voice":
            self.channel_select = discord.ui.ChannelSelect(
                placeholder="Voice channel to move into",
                row=1,
                min_values=0,
                max_values=1,
                channel_types=[
                    discord.ChannelType.voice,
                    discord.ChannelType.stage_voice,
                ],
                default_values=[discord.Object(id=channel)] if channel else [],
            )
            self.channel_select.callback = self.channel_callback
            self.add_item(self.channel_select)
        elif action == "pm_player":
            target = self.entry.get("pm_target", "caller")
            self.target_select = discord.ui.Select(
                placeholder="Who receives the message",
                row=1,
                options=[
                    discord.SelectOption(
                        label="The player who ran the command",
                        value="caller",
                        default=target == "caller",
                    ),
                    discord.SelectOption(
                        label="The player named in the argument",
                        value="argument",
                        default=target == "argument",
                    ),
                ],
            )
            self.target_select.callback = self.target_callback
            self.add_item(self.target_select)

        if action == "ping_role":
            self.roles_select = discord.ui.RoleSelect(
                placeholder="Roles to mention",
                row=2,
                min_values=0,
                max_values=5,
                default_values=[
                    discord.Object(id=role) for role in self.entry.get("roles") or []
                ],
            )
            self.roles_select.callback = self.roles_callback
            self.add_item(self.roles_select)

        if action != "move_to_voice":
            edit_message = discord.ui.Button(label="Edit Message", row=3)
            edit_message.callback = self.edit_message_callback
            self.add_item(edit_message)

        variables = discord.ui.Button(label="View Variables", row=3)
        variables.callback = self.variables_callback
        self.add_item(variables)

        permissions = discord.ui.Button(label="Permissions", row=3)
        permissions.callback = self.permissions_callback
        self.add_item(permissions)

        cancel = discord.ui.Button(
            label="Cancel", style=discord.ButtonStyle.danger, row=4
        )
        cancel.callback = self.cancel_callback
        self.add_item(cancel)

        save = discord.ui.Button(
            label="Save",
            style=discord.ButtonStyle.green,
            row=4,
            disabled=not self.complete(),
        )
        save.callback = self.save_callback
        self.add_item(save)

    async def refresh(self):
        if not self.message:
            return

        self.build()
        try:
            await self.message.edit(embed=self.summary(self.message.guild), view=self)
        except discord.HTTPException:
            pass

    async def action_callback(self, interaction: discord.Interaction):
        self.entry["action"] = self.action_select.values[0]
        await interaction.response.defer()
        await self.refresh()

    async def channel_callback(self, interaction: discord.Interaction):
        values = self.channel_select.values
        self.entry["channel"] = values[0].id if values else 0
        await interaction.response.defer()
        await self.refresh()

    async def target_callback(self, interaction: discord.Interaction):
        self.entry["pm_target"] = self.target_select.values[0]
        await interaction.response.defer()
        await self.refresh()

    async def roles_callback(self, interaction: discord.Interaction):
        self.entry["roles"] = [role.id for role in self.roles_select.values]
        await interaction.response.defer()
        await self.refresh()

    async def edit_message_callback(self, interaction: discord.Interaction):
        modal = MessageModal(self.entry.get("message", ""))
        await interaction.response.send_modal(modal)
        if await modal.wait():
            return

        self.entry["message"] = modal.message.value.strip()
        await self.refresh()

    async def variables_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="In-Game Command Variables",
                description=(
                    "`{player}` - The player who ran the command.\n"
                    "`{user}` - The same as `{player}`.\n"
                    "`{argument}` - Everything typed after the command."
                ),
                color=BLANK_COLOR,
            ),
            ephemeral=True,
        )

    async def permissions_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Command Access",
                description="Choose who may run **;{}**.".format(
                    self.entry.get("trigger", "")
                ),
                color=BLANK_COLOR,
            ),
            view=InGameCommandPermissions(self.user_id, self.entry, self),
            ephemeral=True,
        )

    async def cancel_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.saved = False
        self.stop()

    async def save_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.saved = True
        self.stop()


class InGameCommands(OwnedView):
    def __init__(self, bot, user_id: int):
        super().__init__(user_id)
        self.bot = bot
        self.message = None

    async def configuration(self, guild_id: int):
        settings = await self.bot.settings.find_by_id(guild_id) or {"_id": guild_id}
        erlc = settings.setdefault("ERLC", {})
        configuration = erlc.setdefault("ingame_commands", {})
        configuration.setdefault("commands", [])
        return settings, configuration

    async def refresh(self, guild: discord.Guild):
        if not self.message:
            return

        _, configuration = await self.configuration(guild.id)
        try:
            await self.message.edit(embed=overview(guild, configuration["commands"]))
        except discord.HTTPException:
            pass

    async def modify(
        self, interaction: discord.Interaction, entry: dict, existing: bool
    ):
        view = InGameCommandModification(self.user_id, entry)
        await interaction.followup.send(
            embed=view.summary(interaction.guild), view=view, ephemeral=True
        )
        view.message = await interaction.original_response()

        if await view.wait() or not view.saved:
            return

        settings, configuration = await self.configuration(interaction.guild.id)
        trigger = normalise_trigger(entry["trigger"])
        identifier = entry.get("id")
        commands = [
            command
            for command in configuration["commands"]
            if command.get("id") != identifier
            and normalise_trigger(command.get("trigger")) != trigger
        ]

        if not existing and len(commands) >= 25:
            return await interaction.followup.send(
                embed=discord.Embed(
                    title="Limit Reached",
                    description="You may only have 25 in-game commands.",
                    color=BLANK_COLOR,
                ),
                ephemeral=True,
            )

        commands.append(entry)
        configuration["commands"] = commands
        await self.bot.settings.update_by_id(settings)
        await config_change_log(
            self.bot,
            interaction.guild,
            interaction.user,
            "In-Game Command {}: {}".format(
                "Edited" if existing else "Created", trigger
            ),
        )
        await self.refresh(interaction.guild)

        await interaction.followup.send(
            embed=discord.Embed(
                title="{} Command {}".format(
                    self.bot.emoji_controller.get_emoji("success"),
                    "Edited" if existing else "Created",
                ),
                description=f"**;{trigger}** has been saved.",
                color=GREEN_COLOR,
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="Add", style=discord.ButtonStyle.green, row=0)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TriggerModal("Add In-Game Command")
        await interaction.response.send_modal(modal)
        if await modal.wait():
            return

        trigger = normalise_trigger(modal.trigger.value)
        if not trigger:
            return await int_failure_embed(
                modal.interaction, "that command name is not usable.", ephemeral=True
            )

        _, configuration = await self.configuration(interaction.guild.id)
        if any(
            normalise_trigger(command.get("trigger")) == trigger
            for command in configuration["commands"]
        ):
            return await int_failure_embed(
                modal.interaction, f"**;{trigger}** already exists.", ephemeral=True
            )

        await self.modify(
            modal.interaction, default_entry(trigger, interaction.user.id), False
        )

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, row=0)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TriggerModal(
            "Edit In-Game Command", label="Command ID", placeholder="The Command ID shown in the list"
        )
        await interaction.response.send_modal(modal)
        if await modal.wait():
            return

        try:
            identifier = int(modal.trigger.value.strip())
        except ValueError:
            return await int_failure_embed(
                modal.interaction,
                "a Command ID may only contain numbers, not letters.",
                ephemeral=True,
            )

        _, configuration = await self.configuration(interaction.guild.id)
        entry = next(
            (
                command
                for command in configuration["commands"]
                if command.get("id") == identifier
            ),
            None,
        )

        if not entry:
            return await int_failure_embed(
                modal.interaction,
                f"no command is using the ID `{identifier}`.",
                ephemeral=True,
            )

        await self.modify(modal.interaction, dict(entry), True)

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.danger, row=0)
    async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TriggerModal(
            "Remove In-Game Command",
            label="Command ID",
            placeholder="The Command ID shown in the list",
        )
        await interaction.response.send_modal(modal)
        if await modal.wait():
            return

        try:
            identifier = int(modal.trigger.value.strip())
        except ValueError:
            return await int_failure_embed(
                modal.interaction,
                "a Command ID may only contain numbers, not letters.",
                ephemeral=True,
            )

        settings, configuration = await self.configuration(interaction.guild.id)
        entry = next(
            (
                command
                for command in configuration["commands"]
                if command.get("id") == identifier
            ),
            None,
        )

        if not entry:
            return await int_failure_embed(
                modal.interaction,
                f"no command is using the ID `{identifier}`.",
                ephemeral=True,
            )

        trigger = entry.get("trigger", "")
        commands = [
            command
            for command in configuration["commands"]
            if command.get("id") != identifier
        ]

        configuration["commands"] = commands
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
