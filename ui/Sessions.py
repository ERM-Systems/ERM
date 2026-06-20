import discord
from discord.ext import commands
import typing
from menus import CustomModal
from base64 import urlsafe_b64decode
import json

class SessionsEmbedCreationView(discord.ui.LayoutView):
    def __init__(self, bot: commands.Bot, type: typing.Literal['vote', 'start', 'shutdown']):
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
                        "- {erlc}: A variable with references to your linked ERLC server\n"
                        "  - {erlc.name}: The name of your ER:LC server\n"
                        "  - {erlc.code}: The code to your ER:LC server\n"
                    )
                )
            case 'start':
                self.cont.add_item(discord.ui.TextDisplay(
                    "### Create Session Start Message\n"
                    "Please use Discohook to create your session start message. When you are done, press the button saying 'I Have Created My Message'. Please note that you may only have one message.\n"
                    "**Main Variables and Notes**\n"
                    "- You will not be able to add any other components than __link buttons__. Regular buttons and anything else will be ignored.\n"
                    "- It is advised that if you create a join URL, you set the code part to {erlc.code}. It will automatically change to your join code.\n"
                    "**Other Variables**\n"
                    "- {user}: The user who started the session\n"
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
                    "- Only link buttons are permitted."
                    "**Other Variables**:"
                    "- {user}: The user responsible for ending this session"
                    "- {erlc}: A variable with references to your linked ERLC server "
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
    
    async def submit(self, interaction: discord.Interaction):
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
        data_encoded = val.replace("?data=", "")
        if not val.startswith("ey"): # ey is { in base64
            return await interaction.followup.send("This discohook.app url does not have a message attached.")
        
        data = urlsafe_b64decode(data_encoded).decode()
        try:
            data = json.loads(data)
        except:
            return await interaction.followup.send("The data is not valid. Please try again.")
        
        message = data["messages"][0]["data"]
        self.satisfied_conditions = False # Checks for buttons being correct.
        for component_block in message["components"]:
            for component in component_block:
                if not component["type"] == 2: # button
                    return await interaction.followup.send("Your data has components that are not permitted.")
                match self.type:
                    case 'vote':
                        if component["label"] == "{vote_button}":
                            component["custom_id"] = "vote_button"
                            self.satisfied_conditions = True
                            continue
                        if component["label"] == "{view_votes_button}":
                            component["custom_id"] = "view_votes_button"
                            continue
                    case 'start':
                        if component["style"] != 5:
                            self.satisfied_conditions = False
                            break
                    case 'shutdown':
                        if component["style"] != 5:
                            self.satisfied_conditions = False
                            break

        if not self.satisfied_conditions:
            return await interaction.followup.send("Your components are invalid for the specific type of embed you are making. This may be because you have regular buttons in the start and end styling (which only allow links) or you may have missing buttons in the vote area.")
        
        settings = await self.bot.settings.find(interaction.guild.id)
        if not settings.get('sessions'):
            settings["sessions"] = {
                "data": message
            }
        await self.bot.settings.update(settings)
        return await interaction.followup.send("Successfully saved embed.")