import discord
from discord.ext import commands
from discord import app_commands
from erm import Bot, is_admin, require_settings, is_management
from utils.constants import CUSTOM_IDS_FOR_SESSIONS, SESSION_VIEW_TYPES
import json
from menus import CustomDropdown
from ui.CustomModals import CustomModalButton
from ui.Sessions import SessionsEmbedCreationView
from ui.Selects import SimpleTextChannelSelect
from utils.utils import create_session_vote, end_session, send_session_boost, staff_check, start_session
import utils.prc_api as prc_api
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import io, asyncio
import datetime

def is_erlc_server_linked():
    async def predicate(ctx: commands.Context):
        if ctx.guild is None:
            return False
        guild_id = ctx.guild.id

        try:
            await ctx.bot.prc_api.get_server_status(guild_id)
        except prc_api.ResponseFailure as exc:
            error = prc_api.ServerLinkNotFound(platform="erlc")
            try:
                error.code = exc.json_data.get("code") or exc.status_code
            except json.JSONDecodeError:
                pass
            raise error

        return True

    return commands.check(predicate)

class Sessions(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        plt.style.use("dark_background")
        self.fig, self.ax = plt.subplots(figsize=(8, 6))

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
            if session.get("staff_only"):
                try:
                    is_staff = await staff_check(self.bot, guild, interaction.user)
                except KeyError:
                    is_staff = False
                if not is_staff:
                    return await interaction.response.send_message(
                        "Only staff can vote on this session.", ephemeral=True
                    )
            if interaction.user.id in session["voted_users"]:
                action = "decrement"
            else:
                action = "increment"
            session["votes"] += 1 if action == "increment" else -1
            if action == "decrement":
                session["voted_users"].remove(interaction.user.id)
            else:
                session["voted_users"].append(interaction.user.id)
            
            dynamic = settings["sessions"].get("dynamic_button")
            try:
                required = int(session["required_votes"])
            except (TypeError, ValueError):
                required = 0
            reached = required > 0 and session["votes"] >= required

            item = None
            for c in view.walk_children():
                if isinstance(c, discord.ui.Button) and c.custom_id == f"vote_button:{guild.id}":
                    item = c
                    break

            if item is not None:
                if dynamic:
                    item.label = f"{session["votes"]}/{session["required_votes"]}"
                item.disabled = reached

            if item is not None and (dynamic or reached):
                await interaction.response.edit_message(view=view)
                if not dynamic:
                    await interaction.followup.send("Successfully counted your vote for the session." if action == "increment" else "Successfully removed your vote from the session.")
            else:
                await interaction.response.send_message("Successfully counted your vote for the session." if action == "increment" else "Successfully removed your vote from the session.")
            await self.bot.sessions.update(session)
            return
        elif id == "view_votes_button":
            print("e")
            cont = discord.ui.Container(
                discord.ui.TextDisplay(
                    "### Voters\n"
                    f"{"".join([f"- <@{str(user)}>\n" for user in session["voted_users"]]) or "> No people have voted for the session."}"
                )
            )
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(cont), ephemeral=True)

    @commands.hybrid_group(name = "session", description="Session-related commands")
    async def session(self, ctx: commands.Context):
        if not ctx.invoked_subcommand:
            return await ctx.reply(embed=discord.Embed(title="Invalid Subcommand", description="No valid subcommand was invoked."))

    @session.command(name = "vote", description="Create a session vote")
    @require_settings(["sessions"])
    @is_admin()
    @app_commands.describe(required_votes="The votes required for the session to start", staff_only="A special staff-only vote for sessions.")
    async def _vote(self, ctx: commands.Context, required_votes: int | None=None, staff_only: bool = False):
        try:
            channel_id = await create_session_vote(self.bot, ctx.guild.id, ctx.author.id, required_votes, staff_only)
        except ValueError as error:
            return await ctx.reply(embed=discord.Embed(title = "Session", description=str(error)))
        return await (ctx.reply if not ctx.interaction else ctx.interaction.followup.send)(embed=discord.Embed(title = f"{self.bot.emoji_controller.get_emoji("success")} Successfully posted session vote message", description=f"You can find it at <#{channel_id}>", colour=discord.Colour.green()), ephemeral=True)
    
    @session.command(name = "start", description="Start a session")
    @require_settings(["sessions"])
    @is_admin()
    async def _start(self, ctx: commands.Context):
        try:
            channel_id = await start_session(self.bot, ctx.guild.id, ctx.author.id)
        except ValueError as error:
            return await ctx.reply(embed=discord.Embed(title = "Session", description=str(error)))
        description = f"You can find it at <#{channel_id}>" if channel_id else "Nothing was sent because the sessions channel isn't configured."
        return await (ctx.reply if not ctx.interaction else ctx.interaction.followup.send)(embed=discord.Embed(title = f"{self.bot.emoji_controller.get_emoji("success")} Successfully started the session", description=description, colour=discord.Colour.green()), ephemeral=True)

    @session.command(name = "end", description="End a session")
    @require_settings(["sessions"])
    @is_admin()
    async def _end(self, ctx: commands.Context):
        try:
            channel_id = await end_session(self.bot, ctx.guild.id, ctx.author.id)
        except ValueError as error:
            return await ctx.reply(embed=discord.Embed(title = "Session", description=str(error)))
        description = f"You can find it at <#{channel_id}>" if channel_id else "Nothing was sent because the sessions channel isn't configured."
        return await (ctx.reply if not ctx.interaction else ctx.interaction.followup.send)(embed=discord.Embed(title = f"{self.bot.emoji_controller.get_emoji("success")} Successfully ended the session", description=description, colour=discord.Colour.green()), ephemeral=True)
    def generate_graph(self, session):
        """
        Generates player graph.
        Very blocking so run in an executor
        """
        self.ax.clear()
        self.ax.plot(session["analytics"]["player_counts"], label="Current Players")
        self.ax.set_xticks([])
        self.ax.set_title("Player Graph")
        self.ax.set_ylabel("Player Count")
        self.ax.legend(loc='upper center', ncol=8, frameon=True)
        self.ax.margins(x=0)
        self.fig.tight_layout()

        buf = io.BytesIO()
        self.fig.savefig(buf, format="png", bbox_inches="tight", dpi=100, facecolor="black")
        buf.seek(0)
        return buf
    @session.command(name = "boost", description="Ask for more players to join the running session")
    @require_settings(["sessions"])
    @is_admin()
    async def _boost(self, ctx: commands.Context):
        try:
            channel_id = await send_session_boost(self.bot, ctx.guild.id, ctx.author.id)
        except ValueError as error:
            return await ctx.reply(embed=discord.Embed(title = "Session", description=str(error)))
        return await (ctx.reply if not ctx.interaction else ctx.interaction.followup.send)(embed=discord.Embed(title = f"{self.bot.emoji_controller.get_emoji("success")} Successfully posted the boost message", description=f"You can find it at <#{channel_id}>", colour=discord.Colour.green()), ephemeral=True)
    @session.command(name = "info", description="View analytics about your session")
    @require_settings(["sessions"])
    @is_erlc_server_linked()
    async def _info(self, ctx: commands.Context):
        session = await self.bot.sessions.find(ctx.guild.id)
        if not session or not session.get("message"):
            return await ctx.reply(embed=discord.Embed(
                title = "No Session",
                description="There is no active session."
            ))
        combined = await self.bot.prc_api.get_server_info(ctx.guild.id, "mod_calls")
        info = combined["status"]
        cont = discord.ui.Container(discord.ui.TextDisplay(
            "### Session Status\n"
            "Below are some analytics regarding your current session. ERM collects data such as your player counts and max player counts and these are deleted when the session is over."
        ))
        graph = await asyncio.get_event_loop().run_in_executor(None, self.generate_graph, session)
        cont.add_item(discord.ui.Separator())
        cont.add_item(discord.ui.TextDisplay(
            "### Player Analytics\n"
            f"> **Current Amount of Players**: {info.current_players}\n"
            f"> **Current Amount of Modcalls**: {len(combined["mod_calls"])}\n"
            f"> **Highest Player Count**: {session["analytics"]["max_players"]}"
        ))
        cont.add_item(discord.ui.Separator())
        file = discord.File(graph, filename="graph.png")
        cont.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(discord.UnfurledMediaItem("attachment://graph.png"))))
        cont.add_item(discord.ui.Separator())
        cont.add_item(discord.ui.ActionRow(discord.ui.Button(url=f"https://erlc.gg/join/{info.join_key}", label="Join Server")))
        return await ctx.reply(view=discord.ui.LayoutView().add_item(cont), files=[file])

    
    @session.command(name = "config", description = "Manage the session config")
    @is_management()
    @require_settings()
    async def _config(self, ctx: commands.Context):
        settings = await self.bot.settings.find(ctx.guild.id)
        if not settings:
            return
        if not settings.get("sessions"):
            settings["sessions"] = {}
        sel = CustomDropdown(
            ctx.author.id, 
            [
                discord.SelectOption(label = "Channel", description="Select the channel for sessions to be sent to.", value="channel"),
                discord.SelectOption(label = "Vote Message", description="Edit the session vote message", value="vote"),
                discord.SelectOption(label = "Staff Vote Message", description="Edit the vote message only staff may vote on", value="staff_vote"),
                discord.SelectOption(label = "Start Message", description="Edit the start message", value = "start"),
                discord.SelectOption(label = "Boost Message", description="Edit the message asking for more players", value = "boost"),
                discord.SelectOption(label = "Full Message", description="Edit the message sent when the server fills up", value = "full"),
                discord.SelectOption(label = "End Message", description="Edit the session end message", value = "shutdown"),
                discord.SelectOption(label = "Other Options", description="Edit other options, such as the dynamic button.", value = "other"),
                discord.SelectOption(label = "Finish", description="Finish editing these options.", value = "done")   
            ]
        )
        msg: discord.Message = None
        while True:
            cont = discord.ui.Container(
                discord.ui.TextDisplay(
                    "### Configure Sessions\n"
                    "Please select the item in the dropdown below to configure sessions."
                ),
                discord.ui.Separator(),
                discord.ui.ActionRow(sel)
            )
            
            if not msg:
                msg = await ctx.reply(view = (view := discord.ui.LayoutView(timeout=None).add_item(cont)))
            else:
                await msg.edit(view = (view := discord.ui.LayoutView(timeout=None).add_item(cont)))
            if await view.wait():
                return
            match sel.values[0]:
                case "channel":
                    ch = SimpleTextChannelSelect(default_values=[discord.SelectDefaultValue(id=settings["sessions"].get("channel_id", 0), type=discord.SelectDefaultValueType.channel)])
                    cont = discord.ui.Container(
                        discord.ui.TextDisplay(
                            "### Set Session Channel\n"
                            "Please select the channel for session messages to be sent to"
                        ),
                        discord.ui.Separator(),
                        discord.ui.ActionRow(ch)
                    )
                    await msg.edit(view = (view := discord.ui.LayoutView(timeout=None).add_item(cont)))
                    await view.wait()
                    settings['sessions']["channel_id"] = ch.values[0].id
                case "other":
                    modal = CustomModalButton(
                        ctx.author.id,
                        "Set Other Options",
                        "Set Other Options",
                        [
                            (
                                "vote_button_name",
                                discord.ui.Label(
                                    text = "Vote Button Label",
                                    description="If you are not using the dynamic button, set a vote label name.",
                                    component=discord.ui.TextInput(
                                        default = settings["sessions"].get("vote_button_label", "vote")
                                    )
                                )
                            ),
                            (
                                "default_required_votes",
                                discord.ui.Label(
                                    text = "Default Required Votes",
                                    description="If a user does not specify the amount of votes, this will be used instead.",
                                    component=discord.ui.TextInput(default = settings["sessions"].get("required_votes_default", 5))
                                )
                            ),
                            (
                                "dynamic_button",
                                discord.ui.Label(
                                    text = "Dynamic Button",
                                    description="Do you wish to enable the dynamic button?",
                                    component=discord.ui.Checkbox(default = settings["sessions"].get("dynamic_button", False))
                                )
                            )
                        ]
                    )
                    cont = discord.ui.Container(
                        discord.ui.TextDisplay(
                            "### Other Options\n"
                            "Please press the button below to continue!"
                        ),
                        discord.ui.Separator(),
                        discord.ui.ActionRow(modal)
                    )
                    await msg.edit(view = (view := discord.ui.LayoutView(timeout=None).add_item(cont)))
                    await view.wait()
                    settings["sessions"]["vote_button_label"] = modal.values[0]
                    try:
                        settings["sessions"]["required_votes_default"] = max(1, int(modal.values[1]))
                    except (TypeError, ValueError):
                        settings["sessions"]["required_votes_default"] = 5
                    settings["sessions"]["dynamic_button"] = bool(modal.values[2])
                case "done":
                    await self.bot.settings.update(settings)
                    return await msg.edit(view=discord.ui.LayoutView().add_item(discord.ui.TextDisplay("### Success\nYour settings were successfully saved!")))
                case val if sel.values[0] in SESSION_VIEW_TYPES:
                    await self.bot.settings.update(settings)
                    await msg.edit(view=(view:=SessionsEmbedCreationView(self.bot, type=val)))
                    await view.wait()
                    settings = await self.bot.settings.find(ctx.guild.id)
        
async def setup(bot: Bot):
    await bot.add_cog(Sessions(bot))