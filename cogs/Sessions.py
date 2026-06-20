import discord
from discord.ext import commands
from discord import app_commands
from erm import Bot, is_admin, require_settings
from utils.constants import CUSTOM_IDS_FOR_SESSIONS
import discord.http
import json

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
            
            if settings["sessions"].get("dynamic_button"):
                item = None
                while not item:
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
        elif id == "view_voters_button":
            cont = discord.ui.Container(
                discord.ui.TextDisplay(
                    "### Voters\n"
                    f"{"".join(["-" + str(user) + "\n" for user in session["voted_users"]])}"
                )
            )
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(cont))

    @commands.hybrid_group(name = "session", description="Session-related commands")
    async def session(self, ctx: commands.Context):
        if not ctx.invoked_subcommand:
            return await ctx.reply(embed=discord.Embed(title="Invalid Subcommand", description="No valid subcommand was invoked."))

    @session.command(name = "vote", description="Create a session vote")
    @require_settings(["sessions"])
    @is_admin()
    @app_commands.describe(required_votes="The votes required for the session to start")
    async def _vote(self, ctx: commands.Context, required_votes: int | None=None):
        settings = await self.bot.settings.find(ctx.guild.id)
        if not settings:
            return
        if await self.bot.sessions.find(ctx.guild.id):
            return await ctx.reply(embed=discord.Embed(
                title = "Current Session",
                description="There is already an active session."
            ))
        
        session_data = {
            "_id": ctx.guild.id,
            "user": ctx.author.id,
            "voted_users": [],
            "started": False,
            "votes": 0,
            "required_votes": required_votes or settings["sessions"]["required_votes_default"] or 5
        }

        d = settings["sessions"]["d"].replace(
            "{user}",
            ctx.author.mention
        ).replace(
            "{vote_button_name}",
            settings["sessions"].get("vote_button_name", "vote")
        ).replace(
            "{required_members}",
            required_votes or settings["sessions"]["required_votes_default"] or 5
        )
        j = json.loads(d)
        if settings["sessions"].get("dynamic_button"):
            j["components"][0]["label"] = f"0/{session_data["required_votes"]}"

        await self.bot.http.send_message(settings["session"]["channel_id"], params=discord.http.MultipartParameters(payload = j, multipart=None, files=None))
        await self.bot.sessions.insert(session_data)
        await ctx.reply("Successfully sent session message.")

async def setup(bot: Bot):
    await bot.add_cog(Sessions(bot))