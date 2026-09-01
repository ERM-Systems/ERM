import discord
from discord.ext import commands
import typing
from menus import CustomModal
from base64 import urlsafe_b64decode, b64encode
import json
import logging


class SessionsEmbedCreationView(discord.ui.LayoutView):
    def __init__(self, bot: commands.Bot, type: typing.Literal['vote', 'staff_vote', 'start', 'boost', 'full', 'shutdown'],):
        super().__init__(timeout=None)
        self.cont = discord.ui.Container()
        self.type = type
        self.bot = bot
        match type:
            case 'vote':
                self.cont.add_item(
                    discord.ui.TextDisplay(
                        "### Create Session Vote Message\n"
                        "Please use Discohook to design your session vote message. When you are done, please press the button saying 'I Have Created My Message'. Please note that you may only have one message.\n"
                        "**Main Variables**\n"
                        "- Your vote button must be a button and must have the label set to `{vote_button}`. If it is not set to that, your vote button will not work.\n"
                        "- If you want a view votes button, you must have another button with the label set to `{view_votes_button}`, else, that will not work.\n"
                        "**Other Variables**\n"
                        "- {user}: The user initiating the session vote\n"
                        "- {vote_button_name}: The name of the vote button. If you select the dynamic button option (where the button's name changes on the amount of votes), this will say 'vote' by default.\n"
                        "- {required_members}: How many members are needed to start the vote\n"
                    )
                )
            case 'staff_vote':
                self.cont.add_item(
                    discord.ui.TextDisplay(
                        "### Create Staff Vote Message\n"
                        "Please use Discohook to design the vote message that only your staff may vote on. When you are done, please press the button saying 'I Have Created My Message'. Please note that you may only have one message.\n"
                        "**Main Variables**\n"
                        "- Your vote button must be a button and must have the label set to `{vote_button}`. If it is not set to that, your vote button will not work.\n"
                        "- If you want a view votes button, you must have another button with the label set to `{view_votes_button}`, else, that will not work.\n"
                        "**Other Variables**\n"
                        "- {user}: The user initiating the staff vote\n"
                        "- {vote_button_name}: The name of the vote button. If you select the dynamic button option (where the button's name changes on the amount of votes), this will say 'vote' by default.\n"
                        "- {required_members}: How many staff members are needed to start the session\n"
                    )
                )
            case 'boost':
                self.cont.add_item(discord.ui.TextDisplay(
                    "### Create Session Boost Message\n"
                    "Please use Discohook to create the message sent by /session boost when you want more players to join. When you are done, press the button saying 'I Have Created My Message'. Please note that you may only have one message.\n"
                    "**Main Variables and Notes**\n"
                    "- Only link buttons are permitted.\n"
                    "**Other Variables**\n"
                    "- {user}: The user asking for the boost\n"
                    "- {erlc}: A variable with references to your linked ERLC server\n"
                    "  - {erlc.name}: The name of your ER:LC server\n"
                    "  - {erlc.code}: The code to your ER:LC server\n"
                    "  - {erlc.players}: The players currently in your ER:LC server\n"
                ))
            case 'full':
                self.cont.add_item(discord.ui.TextDisplay(
                    "### Create Session Full Message\n"
                    "Please use Discohook to create the message sent once your server reaches its player limit. It is sent at most once per session. When you are done, press the button saying 'I Have Created My Message'. Please note that you may only have one message.\n"
                    "**Main Variables and Notes**\n"
                    "- Only link buttons are permitted.\n"
                    "**Other Variables**\n"
                    "- {erlc}: A variable with references to your linked ERLC server\n"
                    "  - {erlc.name}: The name of your ER:LC server\n"
                    "  - {erlc.code}: The code to your ER:LC server\n"
                    "  - {erlc.players}: The players in your ER:LC server\n"
                    "  - {erlc.max_players}: The maximum players your ER:LC server holds\n"
                ))
            case 'start':
                self.cont.add_item(discord.ui.TextDisplay(
                    "### Create Session Start Message\n"
                    "Please use Discohook to create your session start message. When you are done, press the button saying 'I Have Created My Message'. Please note that you may only have one message.\n"
                    "**Main Variables and Notes**\n"
                    "- You will not be able to add any other components than __link buttons__. Regular buttons and anything else will be ignored.\n"
                    "- It is advised that if you create a join URL, you set the code part to {erlc.code}. It will automatically change to your join code.\n"
                    "**Other Variables**\n"
                    "- {user}: The user who started the session\n"
                    "- {user_mentions}: The mentions of the users who voted.\n"
                    "- {erlc}: A variable with references to your linked ERLC server\n"
                    "  - {erlc.name}: The name of your ER:LC server\n"
                    "  - {erlc.code}: The code to your ER:LC server\n"
                    "  - {erlc.players}: The players in your ER:LC server. If this is present, your message will be edited every 5 minutes to reflect the current amount of members.\n"
                ))
            case 'shutdown':
                self.cont.add_item(discord.ui.TextDisplay(
                    "### Create Session End Message\n"
                    "Please use Discohook to create your session end message. When you are done, press the button saying 'I Have Created My Message'. Please note that you may only have one message.\n"
                    "**Main Variables and Notes**\n"
                    "- Only link buttons are permitted.\n"
                    "**Other Variables**:\n"
                    "- {user}: The user responsible for ending this session\n"
                    "- {erlc}: A variable with references to your linked ERLC server \n"
                    "  - {erlc.name}: The name of your ER:LC server\n"
                    "  - {erlc.max_players}: The highest amount of players."
                ))
        self.cont.add_item(discord.ui.Separator())
        self.row = discord.ui.ActionRow(discord.ui.Button(url="https://discohook.app", label="Access Discohook"))
        self.button = discord.ui.Button(
            label = "I Have Created My Message",
            style=discord.ButtonStyle.blurple
        )
        self.button.callback = self.submit
        self.row.add_item(self.button)
        self.cont.add_item(self.row)
        self.add_item(self.cont)
    async def submit(self, interaction: discord.Interaction):
        try:
            settings = await self.bot.settings.find(interaction.guild.id)
            if not settings.get('sessions'):
                return
            modal = CustomModal(
                "Submit Message",
                [
                    (
                        "url",
                        discord.ui.Label(
                            text="URL",
                            description="Please send your URL into this textbox.",
                            component=discord.ui.TextInput(max_length=3999)
                        )
                    )
                ]
            )
            await interaction.response.send_modal(modal)
            await modal.wait()
            val: str = modal.url.component.value
            if not val.startswith("https://discohook.app"):
                return await interaction.followup.send("This is not a valid discohook.app URL.", ephemeral=True)
            try:
                data_encoded = val.split("?data=")[1]
            except:
                return await interaction.followup.send("This discohook.app url does not have a message attached.")

            data = urlsafe_b64decode(data_encoded + "==").decode()
            try:
                data = json.loads(data)
            except:
                return await interaction.followup.send("The data is not valid. Please try again.")
            
            message = data["messages"][0]["data"]
            rows = message.get("components") or []
            buttons = [
                component
                for row in rows
                if row.get("type") == 1
                for component in row.get("components") or []
            ]

            if any(component.get("type") != 2 for component in buttons):
                return await interaction.followup.send("Your data has components that are not permitted.")

            if any(row.get("type") != 1 for row in rows):
                message["flags"] = (message.get("flags") or 0) | 1 << 15

            self.satisfied_conditions = not buttons and self.type not in ("vote", "staff_vote")
            for component in buttons:
                match self.type:
                    case 'vote' | 'staff_vote':
                        if component["label"] == "{vote_button}":
                            if not settings["sessions"].get("dynamic_button", False):
                                component["label"] = settings["sessions"].get("vote_button_label", "vote")
                            if component["style"] == 5: continue
                            component["custom_id"] = f"vote_button:{interaction.guild.id}"
                            self.satisfied_conditions = True
                            continue
                        if component["label"] == "{view_votes_button}":
                            if component["style"] == 5: continue
                            component["label"] = "View Votes"
                            component["custom_id"] = f"view_votes_button:{interaction.guild.id}"
                            continue
                        if component["style"] == 5:
                            if component.get("custom_id"):
                                del component["custom_id"]
                    case 'start':
                        if component["style"] == 5:
                            if component.get("custom_id"):
                                del component["custom_id"]
                            self.satisfied_conditions = True
                            break
                    case 'shutdown' | 'boost' | 'full':
                        if component["style"] == 5:
                            self.satisfied_conditions = True
                            break

            if not self.satisfied_conditions:
                return await interaction.followup.send("Your components are invalid for the specific type of embed you are making. This may be because you have regular buttons in the start and end styling (which only allow links) or you may have missing buttons in the vote area.")

            settings["sessions"][self.type] = json.dumps(message)
            await self.bot.settings.update(settings)
            self.stop()
        except Exception as e:
            logging.warning(f"Failed to save the session {self.type} message: {e}")
            await interaction.followup.send("That message could not be saved. Please try again.", ephemeral=True)