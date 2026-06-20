import discord
from discord.ext import commands
from discord import app_commands
from erm import Bot
from utils.constants import CUSTOM_IDS_FOR_SESSIONS

class Sessions(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component or not interaction.message:
            return
        id = interaction.data.get("custom_id")
        if not id.endswith(f":{interaction.guild.id}"):
            return
        id = id.removesuffix(f":{interaction.guild.id}")
        if not id in CUSTOM_IDS_FOR_SESSIONS:
            return

        guild = interaction.guild
        settings = await self.bot.settings.find(guild.id)
        if not settings: return
        view = discord.ui.View.from_message(interaction.message, timeout=None)
        session = await self.bot.sessions.find(guild.id)
        if not session:
            return
        if id == "vote_button":
            if interaction.user.id in session["voted_users"]:
                action = "decrement"
            else:
                action = "increment"
            await self.bot.sessions.increment(guild.id, 1 if action == "increment" else -1, "votes")
            if action == "decrement":
                session["voted_users"].remove(interaction.user.id)
            else:
                session["voted_users"].append(interaction.user.id)
            
            if settings["sessions"]["dynamic_button"]:
                item = None
                while item == None:
                    children = view.children
                    for c in children:
                        if isinstance(c, discord.ui.Container):
                            children = c.children
                        if isinstance(c, discord.ui.ActionRow):
                            children = c.children
                        if isinstance(c, discord.ui.Button) and c.custom_id == "vote_button":
                            item = c
                item.label = f"{session["votes"]}/{session["required_votes"]}"
                await interaction.response.edit_message(view=view)
            else:
                await interaction.response.send_message("Successfully counted your vote for the session." if action == "increment" else "Successfully removed your vote from the session.")
            await self.bot.sessions.update(guild.id)
            return


        