import discord
from discord.ext import commands
from discord import app_commands
from erm import Bot, is_admin, require_settings, is_management
from utils.constants import BLANK_COLOR, RED_COLOR, CUSTOM_IDS_FOR_SESSIONS, SESSION_VIEW_TYPES
import discord.http
import json
from menus import CustomDropdown
from ui.CustomModals import CustomModalButton
from ui.Sessions import SessionsEmbedCreationView
from ui.Selects import SimpleTextChannelSelect
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
            if interaction.user.id in session["voted_users"]:
                action = "decrement"
            else:
                action = "increment"
            session["votes"] += 1 if action == "increment" else -1
            if action == "decrement":
                session["voted_users"].remove(interaction.user.id)
            else:
                session["voted_users"].append(interaction.user.id)
            
            if settings["sessions"].get("dynamic_button"):
                item = None

                for c in view.walk_children():
                    if isinstance(c, discord.ui.Button) and c.custom_id == f"vote_button:{guild.id}":
                        item = c
                        break

                if item is None:
                    return
                item.label = f"{session["votes"]}/{session["required_votes"]}"
                await interaction.response.edit_message(view=view)
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
            "required_votes": required_votes or settings["sessions"]["required_votes_default"] or 5,
            "analytics": {
                "max_players": 0,
                "player_counts": []
            }
        }

        d = settings["sessions"]["vote"].replace(
            "{user}",
            ctx.author.mention
        ).replace(
            "{vote_button_name}",
            settings["sessions"].get("vote_button_label", "vote") if not settings["sessions"].get("dynamic_button") else f"0/{session_data["required_votes"]}"
        ).replace(
            "{required_members}",
            str(required_votes or settings["sessions"]["required_votes_default"] or 5)
        )
        j = json.loads(d)
        if settings["sessions"].get("dynamic_button"):
            j["components"][0]["components"][0]["label"] = f"0/{session_data["required_votes"]}"

        msg = await self.bot.http.send_message(settings["sessions"]["channel_id"], params=discord.http.MultipartParameters(payload = j, multipart=None, files=None))
        session_data["vote_message"] = msg["id"]
        await self.bot.sessions.insert(session_data)
        return await (ctx.reply if not ctx.interaction else ctx.interaction.followup.send)(embed=discord.Embed(title = f"{self.bot.emoji_controller.get_emoji("success")} Successfully posted session vote message", description=f"You can find it at <#{settings["sessions"]["channel_id"]}>", colour=discord.Colour.green()), ephemeral=True)
    
    @session.command(name = "start", description="Start a session")
    @require_settings(["sessions"])
    @is_admin()
    async def _start(self, ctx: commands.Context):
        settings = await self.bot.settings.find(ctx.guild.id)
        if not settings:
            return
        session = await self.bot.sessions.find(ctx.guild.id)
        if not session:
            return await ctx.reply(embed=discord.Embed(
                title = "No Session",
                description="There is no active session."
            ))
        try:
            info = await self.bot.prc_api.get_server_status(ctx.guild.id)
        except:
            info = None
        if "{erlc.players}" in settings["sessions"]["start"]: session["dynamic"] = True
        d = settings["sessions"]["start"].replace(
            "{user}",
            ctx.author.mention
        ).replace(
            "{user_mentions}",
            f"{" | ".join([f"<@{user}>" for user in session["voted_users"]])}"
        ).replace(
            "{erlc.name}",
            info.name if info else "{erlc.name}"
        ).replace(
            "{erlc.code}",
            f"{info.join_key}" if info else "{erlc.code}"
        ).replace(
            "{erlc.players}",
            str(info.current_players if info else "{erlc.players}")
        )
        session["user"] = ctx.author.mention

        j = json.loads(d)
        channel = await ctx.guild.fetch_channel(settings["sessions"]["channel_id"])
        msg = await channel.fetch_message(session["vote_message"])
        view = discord.ui.View.from_message(msg)
        item = None

        for c in view.walk_children():
            if isinstance(c, discord.ui.Button) and c.custom_id == f"vote_button:{ctx.guild.id}":
                item = c
                break
        if item == None:
            pass
        else:
            item.disabled = True
        await msg.edit(view=view)
        s = await self.bot.http.send_message(settings["sessions"]["channel_id"], params=discord.http.MultipartParameters(payload = j, multipart=None, files=None))
        session["message"], session["channel"] = s["id"], settings["sessions"]["channel_id"]
        await self.bot.sessions.update(session)
        return await (ctx.reply if not ctx.interaction else ctx.interaction.followup.send)(embed=discord.Embed(title = f"{self.bot.emoji_controller.get_emoji("success")} Successfully posted session start message", description=f"You can find it at <#{settings["sessions"]["channel_id"]}>", colour=discord.Colour.green()), ephemeral=True)
    
    @session.command(name = "end", description="End a session")
    @require_settings(["sessions"])
    @is_admin()
    async def _end(self, ctx: commands.Context):
        settings = await self.bot.settings.find(ctx.guild.id)
        if not settings:
            return
        session = await self.bot.sessions.find(ctx.guild.id)
        if not session:
            return await ctx.reply(embed=discord.Embed(
                title = "No Session",
                description="There is no active session."
            ))
        try:
            info = await self.bot.prc_api.get_server_status(ctx.guild.id)
        except: info = None
        d = settings["sessions"]["shutdown"].replace(
            "{user}",
            ctx.author.mention
        ).replace(
            "{erlc.name}",
            info.name if info else "{erlc.name}"
        ).replace(
            "{erlc.code}",
            info.join_key if info else "{erlc.code}"
        ).replace(
            "{erlc.max_players}",
            str(session.get("analytics", {}).get("max_players", 0))
        )
        j = json.loads(d)
        await self.bot.http.send_message(settings["sessions"]["channel_id"], params=discord.http.MultipartParameters(payload = j, multipart=None, files=None))
        await self.bot.sessions.delete(session["_id"])
        return await (ctx.reply if not ctx.interaction else ctx.interaction.followup.send)(embed=discord.Embed(title = f"{self.bot.emoji_controller.get_emoji("success")} Successfully posted session end message", description=f"You can find it at <#{settings["sessions"]["channel_id"]}>", colour=discord.Colour.green()), ephemeral=True)
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

    
    @session.command(name="setup", description="Set up sessions for the first time")
    @is_management()
    @require_settings()
    async def _setup(self, ctx: commands.Context):
        settings = await self.bot.settings.find(ctx.guild.id)
        if not settings:
            return

        if settings.get("sessions", {}).get("channel_id"):
            return await ctx.reply(embed=discord.Embed(
                title="Already Configured",
                description="Sessions are already set up. Use `session config` to modify settings.",
                color=RED_COLOR,
            ))

        ch = SimpleTextChannelSelect()
        cont = discord.ui.Container(
            discord.ui.TextDisplay(
                "### Session Setup\n"
                "Welcome to the session setup wizard. First, select the channel where session messages will be sent."
            ),
            discord.ui.Separator(),
            discord.ui.ActionRow(ch),
        )
        msg = await ctx.reply(view=(view := discord.ui.LayoutView().add_item(cont)))
        await view.wait()
        channel_id = ch.values[0].id

        vote_options = [3, 5, 8, 10, 15, 20]
        sel = CustomDropdown(
            ctx.author.id,
            [discord.SelectOption(label=str(v), value=str(v)) for v in vote_options],
        )
        cont = discord.ui.Container(
            discord.ui.TextDisplay(
                "### Required Votes\n"
                "How many votes should be required before a session can start?"
            ),
            discord.ui.Separator(),
            discord.ui.ActionRow(sel),
        )
        await msg.edit(view=(view := discord.ui.LayoutView().add_item(cont)))
        await view.wait()
        required_votes = int(sel.values[0])

        guild_id = ctx.guild.id
        vote_json = json.dumps({
            "content": "",
            "components": [
                {
                    "type": 1,
                    "components": [
                        {"type": 2, "label": f"0/{required_votes}", "style": 1, "custom_id": f"vote_button:{guild_id}"},
                        {"type": 2, "label": "View Votes", "style": 2, "custom_id": f"view_votes_button:{guild_id}"},
                    ],
                }
            ],
            "embeds": [
                {
                    "title": "Session Vote",
                    "description": "{user} has started a session vote! **{required_members}** votes are required.",
                    "color": BLANK_COLOR,
                }
            ],
        })
        start_json = json.dumps({
            "content": "",
            "components": [
                {
                    "type": 1,
                    "components": [
                        {"type": 2, "label": "Join Server", "style": 5, "url": "https://erlc.gg/join/{erlc.code}"},
                    ],
                }
            ],
            "embeds": [
                {
                    "title": "Session Started",
                    "description": "A session has been started by {user}.\n\n**Players:** {erlc.players}",
                    "color": BLANK_COLOR,
                }
            ],
        })
        shutdown_json = json.dumps({
            "embeds": [
                {
                    "title": "Session Ended",
                    "description": "The session has been ended by {user}.\n\n**Max Players:** {erlc.max_players}",
                    "color": BLANK_COLOR,
                }
            ],
        })

        settings["sessions"] = {
            "channel_id": channel_id,
            "required_votes_default": required_votes,
            "dynamic_button": True,
            "vote_button_label": "vote",
            "vote": vote_json,
            "start": start_json,
            "shutdown": shutdown_json,
        }
        await self.bot.settings.update(settings)

        cont = discord.ui.Container(
            discord.ui.TextDisplay(
                "### Setup Complete\n"
                f"Sessions will be sent to <#{channel_id}> with **{required_votes}** votes required.\n\n"
                "Default vote, start, and end messages have been created. Use `session config` to customise them."
            ),
        )
        await msg.edit(view=discord.ui.LayoutView().add_item(cont))

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
                discord.SelectOption(label = "Start Message", description="Edit the start message", value = "start"),
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
                msg = await ctx.reply(view = (view := discord.ui.LayoutView().add_item(cont)))
            else:
                await msg.edit(view = (view := discord.ui.LayoutView().add_item(cont)))
            await view.wait()
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
                    await msg.edit(view = (view := discord.ui.LayoutView().add_item(cont)))
                    await view.wait()
                    print("e")
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
                    await msg.edit(view = (view := discord.ui.LayoutView().add_item(cont)))
                    await view.wait()
                    settings["sessions"]["vote_button_name"] = modal.values[0]
                    settings["sessions"]["required_votes_default"] = modal.values[1]
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