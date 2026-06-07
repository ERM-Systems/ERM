import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.constants import BLANK_COLOR

GREEN_MOTION = 0x57F287
RED_MOTION = 0xED4245


def _all_voted_ids(motion_doc: dict) -> set:
    ids = set()
    for entry in motion_doc.get("yes_votes", []):
        ids.add(entry["user_id"])
    for entry in motion_doc.get("no_votes", []):
        ids.add(entry["user_id"])
    for entry in motion_doc.get("abstain_votes", []):
        ids.add(entry["user_id"])
    return ids


def _build_motion_embed(motion_doc: dict, config: dict) -> discord.Embed:
    title = f"Motion {motion_doc['motion_number']}: {motion_doc['title']}"
    embed = discord.Embed(title=title, description=motion_doc["description"], color=BLANK_COLOR)

    yes_votes = motion_doc.get("yes_votes", [])
    no_votes = motion_doc.get("no_votes", [])
    abstain_votes = motion_doc.get("abstain_votes", [])
    total = len(yes_votes) + len(no_votes) + len(abstain_votes)

    def format_votes(votes, label):
        if not votes:
            return None
        lines = "\n".join(f"**{v['username']}** — {v['reason']}" for v in votes)
        return (label, lines, True)

    for result in [
        format_votes(yes_votes, "✅ Yes"),
        format_votes(no_votes, "❌ No"),
        format_votes(abstain_votes, "⬜ Abstain"),
    ]:
        if result:
            embed.add_field(name=result[0], value=result[1], inline=result[2])

    embed.add_field(name="Total Votes", value=str(total), inline=False)

    started_by = motion_doc.get("started_by_username", "Unknown")
    ts = int(motion_doc.get("created_at", datetime.datetime.now().timestamp()))
    threshold = config.get("pass_threshold_percent", 60)
    quorum = config.get("quorum_percent", 80)
    embed.set_footer(
        text=f"Pass threshold: {threshold}% · Quorum: {quorum}% · Vote Started by: {started_by} · <t:{ts}:f>"
    )
    return embed


async def _post_result_embed(bot, motion_doc: dict, config: dict, guild: discord.Guild):
    log_channel_id = config.get("log_channel_id", "")
    if not log_channel_id:
        return
    channel = guild.get_channel(int(log_channel_id))
    if not channel:
        return

    yes_votes = motion_doc.get("yes_votes", [])
    no_votes = motion_doc.get("no_votes", [])
    abstain_votes = motion_doc.get("abstain_votes", [])
    total = len(yes_votes) + len(no_votes) + len(abstain_votes)
    passed = motion_doc.get("passed", False)

    title = f"Motion Result: Motion {motion_doc['motion_number']}: {motion_doc['title']}"
    color = GREEN_MOTION if passed else RED_MOTION

    result_text = "**The motion has Passed!**" if passed else "**The motion has Failed!**"
    now_ts = int(datetime.datetime.now().timestamp())

    description = (
        f"{motion_doc['description']}\n\n"
        f"• Yes: {len(yes_votes)}\n"
        f"• No: {len(no_votes)}\n"
        f"• Abstain: {len(abstain_votes)}\n\n"
        f"{result_text}\n\n"
        f"<t:{now_ts}:f>"
    )

    embed = discord.Embed(title=title, description=description, color=color)
    try:
        await channel.send(embed=embed)
    except discord.HTTPException:
        pass


class ReasonModal(discord.ui.Modal):
    reason = discord.ui.TextInput(
        label="Reason for your vote",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
    )

    def __init__(self, view: "MotionView", vote_type: str):
        super().__init__(title="Vote Reason")
        self.vote_view = view
        self.vote_type = vote_type

    async def on_submit(self, interaction: discord.Interaction):
        await self.vote_view.record_vote(interaction, self.vote_type, self.reason.value)


class MotionView(discord.ui.View):
    def __init__(self, motion_id, bot):
        super().__init__(timeout=None)
        self.motion_id = str(motion_id)
        self.bot = bot

        self.yes_button = discord.ui.Button(
            label="Yes",
            style=discord.ButtonStyle.success,
            custom_id=f"yes_{self.motion_id}",
        )
        self.no_button = discord.ui.Button(
            label="No",
            style=discord.ButtonStyle.danger,
            custom_id=f"no_{self.motion_id}",
        )
        self.abstain_button = discord.ui.Button(
            label="Abstain",
            style=discord.ButtonStyle.secondary,
            custom_id=f"abstain_{self.motion_id}",
        )

        self.yes_button.callback = self._make_callback("yes")
        self.no_button.callback = self._make_callback("no")
        self.abstain_button.callback = self._make_callback("abstain")

        self.add_item(self.yes_button)
        self.add_item(self.no_button)
        self.add_item(self.abstain_button)

    def _make_callback(self, vote_type: str):
        async def callback(interaction: discord.Interaction):
            await self._handle_vote(interaction, vote_type)
        return callback

    async def _handle_vote(self, interaction: discord.Interaction, vote_type: str):
        from bson import ObjectId
        motion_doc = await self.bot.motions.db.find_one({"_id": ObjectId(self.motion_id)})
        if not motion_doc or motion_doc.get("status") != "active":
            await interaction.response.send_message("This motion is no longer active.", ephemeral=True)
            return

        settings = await self.bot.settings.find_by_id(interaction.guild.id)
        config = (settings or {}).get("democracy", {})
        voter_roles = config.get("voter_roles", [])

        if voter_roles:
            member_role_ids = [str(r.id) for r in interaction.user.roles]
            if not any(rid in member_role_ids for rid in voter_roles):
                await interaction.response.send_message("You don't have permission to vote.", ephemeral=True)
                return

        already_voted = _all_voted_ids(motion_doc)
        if str(interaction.user.id) in already_voted:
            await interaction.response.send_message("You have already voted on this motion.", ephemeral=True)
            return

        modal = ReasonModal(self, vote_type)
        await interaction.response.send_modal(modal)

    async def record_vote(self, interaction: discord.Interaction, vote_type: str, reason: str):
        from bson import ObjectId
        motion_doc = await self.bot.motions.db.find_one({"_id": ObjectId(self.motion_id)})
        if not motion_doc or motion_doc.get("status") != "active":
            await interaction.response.send_message("This motion is no longer active.", ephemeral=True)
            return

        already_voted = _all_voted_ids(motion_doc)
        if str(interaction.user.id) in already_voted:
            await interaction.response.send_message("You have already voted.", ephemeral=True)
            return

        entry = {
            "user_id": str(interaction.user.id),
            "username": interaction.user.display_name,
            "reason": reason,
        }

        field = f"{vote_type}_votes"
        await self.bot.motions.db.update_one(
            {"_id": ObjectId(self.motion_id)},
            {"$push": {field: entry}},
        )

        motion_doc = await self.bot.motions.db.find_one({"_id": ObjectId(self.motion_id)})

        settings = await self.bot.settings.find_by_id(interaction.guild.id)
        config = (settings or {}).get("democracy", {})

        await interaction.response.send_message(
            f"Your **{vote_type}** vote has been recorded.", ephemeral=True
        )

        # Update the original embed
        try:
            channel = interaction.guild.get_channel(int(config.get("motion_channel_id", 0)))
            if channel and motion_doc.get("message_id"):
                msg = await channel.fetch_message(int(motion_doc["message_id"]))
                embed = _build_motion_embed(motion_doc, config)
                await msg.edit(embed=embed)
        except (discord.HTTPException, ValueError):
            pass

        # Check resolution
        yes_votes = motion_doc.get("yes_votes", [])
        no_votes = motion_doc.get("no_votes", [])
        abstain_votes = motion_doc.get("abstain_votes", [])
        total_voted = len(yes_votes) + len(no_votes) + len(abstain_votes)
        quorum = config.get("quorum_percent", 80)

        voter_roles = config.get("voter_roles", [])
        total_eligible = 0
        for member in interaction.guild.members:
            member_role_ids = [str(r.id) for r in member.roles]
            if not voter_roles or any(rid in member_role_ids for rid in voter_roles):
                total_eligible += 1

        if total_eligible > 0 and (total_voted / total_eligible * 100) >= quorum:
            await self._resolve(interaction.guild, motion_doc, config, total_voted)

    async def _resolve(self, guild: discord.Guild, motion_doc: dict, config: dict, total_voted: int):
        from bson import ObjectId
        yes_count = len(motion_doc.get("yes_votes", []))
        threshold = config.get("pass_threshold_percent", 60)
        passed = total_voted > 0 and (yes_count / total_voted * 100) >= threshold

        now = datetime.datetime.utcnow()
        await self.bot.motions.db.update_one(
            {"_id": ObjectId(self.motion_id)},
            {"$set": {
                "status": "resolved",
                "resolved_at": now,
                "passed": passed,
            }},
        )

        motion_doc["status"] = "resolved"
        motion_doc["passed"] = passed

        await _post_result_embed(self.bot, motion_doc, config, guild)

        # Disable buttons on original message
        try:
            channel = guild.get_channel(int(config.get("motion_channel_id", 0)))
            if channel and motion_doc.get("message_id"):
                msg = await channel.fetch_message(int(motion_doc["message_id"]))
                for item in self.children:
                    item.disabled = True
                await msg.edit(view=self)
        except (discord.HTTPException, ValueError):
            pass


class StartMotionModal(discord.ui.Modal, title="Start a Motion"):
    motion_title = discord.ui.TextInput(
        label="Motion Title",
        style=discord.TextStyle.short,
        required=True,
        max_length=200,
    )
    motion_description = discord.ui.TextInput(
        label="Motion Description",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000,
    )

    def __init__(self, bot, config: dict):
        super().__init__()
        self.bot = bot
        self.config = config

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        motion_channel_id = self.config.get("motion_channel_id", "")
        if not motion_channel_id:
            await interaction.followup.send("Motion channel is not configured.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(int(motion_channel_id))
        if not channel:
            await interaction.followup.send("Motion channel not found.", ephemeral=True)
            return

        # Atomic increment for motion number
        result = await self.bot.db["motion_counters"].find_one_and_update(
            {"_id": str(interaction.guild.id)},
            {"$inc": {"count": 1}},
            upsert=True,
            return_document=True,
        )
        motion_number = result["count"]

        lazy_timeout = self.config.get("lazy_vote_timeout_seconds", 86400)
        now = datetime.datetime.utcnow()
        ends_at = now + datetime.timedelta(seconds=lazy_timeout)

        motion_doc = {
            "guild_id": str(interaction.guild.id),
            "motion_number": motion_number,
            "message_id": "",
            "channel_id": motion_channel_id,
            "created_by": str(interaction.user.id),
            "started_by_username": interaction.user.display_name,
            "title": self.motion_title.value,
            "description": self.motion_description.value,
            "yes_votes": [],
            "no_votes": [],
            "abstain_votes": [],
            "status": "active",
            "pass_threshold_percent": self.config.get("pass_threshold_percent", 60),
            "quorum_percent": self.config.get("quorum_percent", 80),
            "created_at": now,
            "ends_at": ends_at,
            "lazy_pinged": False,
            "resolved_at": None,
            "passed": None,
        }

        insert_result = await self.bot.motions.db.insert_one(motion_doc)
        motion_id = insert_result.inserted_id
        motion_doc["_id"] = motion_id

        view = MotionView(motion_id, self.bot)
        embed = _build_motion_embed(motion_doc, self.config)

        msg = await channel.send(embed=embed, view=view)
        self.bot.add_view(view, message_id=msg.id)

        await self.bot.motions.db.update_one(
            {"_id": motion_id},
            {"$set": {"message_id": str(msg.id)}},
        )

        await interaction.followup.send(
            f"Motion {motion_number} started in {channel.mention}.", ephemeral=True
        )


class DemocracyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    motion = app_commands.Group(name="motion", description="Manage server motions")

    @motion.command(name="start", description="Start a new motion for the council to vote on")
    @app_commands.guild_only()
    async def motion_start(self, interaction: discord.Interaction):
        settings = await self.bot.settings.find_by_id(interaction.guild.id)
        config = (settings or {}).get("democracy", {})

        if not config.get("enabled"):
            await interaction.response.send_message("The motions system is not enabled.", ephemeral=True)
            return

        creation_roles = config.get("creation_roles", [])
        if creation_roles:
            member_role_ids = [str(r.id) for r in interaction.user.roles]
            if not any(rid in member_role_ids for rid in creation_roles):
                await interaction.response.send_message("You don't have permission to start a motion.", ephemeral=True)
                return

        modal = StartMotionModal(self.bot, config)
        await interaction.response.send_modal(modal)

    @motion.command(name="end", description="Force-end an active motion")
    @app_commands.guild_only()
    @app_commands.describe(motion_id="The motion number to end")
    async def motion_end(self, interaction: discord.Interaction, motion_id: int):
        settings = await self.bot.settings.find_by_id(interaction.guild.id)
        config = (settings or {}).get("democracy", {})

        creation_roles = config.get("creation_roles", [])
        if creation_roles:
            member_role_ids = [str(r.id) for r in interaction.user.roles]
            if not any(rid in member_role_ids for rid in creation_roles):
                await interaction.response.send_message("You don't have permission to end motions.", ephemeral=True)
                return

        motion_doc = await self.bot.motions.db.find_one({
            "guild_id": str(interaction.guild.id),
            "motion_number": motion_id,
        })

        if not motion_doc:
            await interaction.response.send_message(f"Motion {motion_id} not found.", ephemeral=True)
            return

        if motion_doc.get("status") != "active":
            await interaction.response.send_message(f"Motion {motion_id} is not active.", ephemeral=True)
            return

        yes_votes = motion_doc.get("yes_votes", [])
        no_votes = motion_doc.get("no_votes", [])
        abstain_votes = motion_doc.get("abstain_votes", [])
        total_voted = len(yes_votes) + len(no_votes) + len(abstain_votes)
        threshold = config.get("pass_threshold_percent", 60)
        passed = total_voted > 0 and (len(yes_votes) / total_voted * 100) >= threshold

        now = datetime.datetime.utcnow()
        await self.bot.motions.db.update_one(
            {"_id": motion_doc["_id"]},
            {"$set": {
                "status": "resolved_manual",
                "resolved_at": now,
                "passed": passed,
            }},
        )
        motion_doc["status"] = "resolved_manual"
        motion_doc["passed"] = passed

        await _post_result_embed(self.bot, motion_doc, config, interaction.guild)
        await interaction.response.send_message(f"Motion {motion_id} has been ended.", ephemeral=True)

    @motion.command(name="status", description="Check the current tally of a motion")
    @app_commands.guild_only()
    @app_commands.describe(motion_id="The motion number to check")
    async def motion_status(self, interaction: discord.Interaction, motion_id: int):
        motion_doc = await self.bot.motions.db.find_one({
            "guild_id": str(interaction.guild.id),
            "motion_number": motion_id,
        })

        if not motion_doc:
            await interaction.response.send_message(f"Motion {motion_id} not found.", ephemeral=True)
            return

        yes = len(motion_doc.get("yes_votes", []))
        no = len(motion_doc.get("no_votes", []))
        abstain = len(motion_doc.get("abstain_votes", []))

        embed = discord.Embed(
            title=f"Motion {motion_id}: {motion_doc['title']}",
            description=f"✅ Yes: **{yes}**\n❌ No: **{no}**\n⬜ Abstain: **{abstain}**",
            color=BLANK_COLOR,
        )
        embed.add_field(name="Status", value=motion_doc.get("status", "unknown"), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(DemocracyCog(bot))
