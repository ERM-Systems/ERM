import datetime
import asyncio
from collections import defaultdict

import discord
from discord.ext import tasks

from utils.constants import BLANK_COLOR

GREEN_MOTION = 0x57F287
RED_MOTION = 0xED4245


@tasks.loop(minutes=2, reconnect=True)
async def check_motions(bot):
    try:
        guild_motions = defaultdict(list)

        async for motion in bot.motions.db.find({"status": "active"}):
            guild_motions[motion["guild_id"]].append(motion)

        for guild_id_str, motions in guild_motions.items():
            try:
                guild = bot.get_guild(int(guild_id_str))
                if not guild:
                    continue

                settings = await bot.settings.find_by_id(guild.id)
                if not settings:
                    continue

                config = settings.get("democracy", {})
                if not config.get("enabled"):
                    continue

                voter_roles = config.get("voter_roles", [])
                motion_channel_id = config.get("motion_channel_id", "")
                log_channel_id = config.get("log_channel_id", "")

                total_eligible = 0
                for member in guild.members:
                    if member.bot:
                        continue
                    if not voter_roles:
                        total_eligible += 1
                    else:
                        member_role_ids = [str(r.id) for r in member.roles]
                        if any(rid in member_role_ids for rid in voter_roles):
                            total_eligible += 1

                batch_size = 5
                for i in range(0, len(motions), batch_size):
                    batch = motions[i: i + batch_size]
                    await asyncio.gather(
                        *[
                            _process_motion(bot, guild, m, config, voter_roles, motion_channel_id, log_channel_id, total_eligible)
                            for m in batch
                        ],
                        return_exceptions=True,
                    )
                    if i + batch_size < len(motions):
                        await asyncio.sleep(1)

            except Exception as e:
                print(f"[check_motions] Error processing guild {guild_id_str}: {e}")

    except Exception as e:
        print(f"[check_motions] Top-level error: {e}")


async def _process_motion(bot, guild, motion_doc, config, voter_roles, motion_channel_id, log_channel_id, total_eligible):
    try:
        from bson import ObjectId

        yes_votes = motion_doc.get("yes_votes", [])
        no_votes = motion_doc.get("no_votes", [])
        abstain_votes = motion_doc.get("abstain_votes", [])
        total_voted = len(yes_votes) + len(no_votes) + len(abstain_votes)
        quorum = config.get("quorum_percent", 80)
        threshold = config.get("pass_threshold_percent", 60)

        # Check if quorum is met — resolve immediately
        if total_eligible > 0 and (total_voted / total_eligible * 100) >= quorum:
            passed = total_voted > 0 and (len(yes_votes) / total_voted * 100) >= threshold
            now = datetime.datetime.utcnow()
            await bot.motions.db.update_one(
                {"_id": motion_doc["_id"]},
                {"$set": {"status": "resolved", "resolved_at": now, "passed": passed}},
            )
            motion_doc["passed"] = passed
            await _post_result(bot, guild, motion_doc, config, log_channel_id)
            return

        # Check lazy ping
        now = datetime.datetime.utcnow()
        ends_at = motion_doc.get("ends_at")
        lazy_pinged = motion_doc.get("lazy_pinged", False)

        if ends_at and now > ends_at and not lazy_pinged:
            already_voted_ids = set()
            for entry in yes_votes + no_votes + abstain_votes:
                already_voted_ids.add(entry["user_id"])

            unvoted = []
            for member in guild.members:
                if member.bot:
                    continue
                if voter_roles:
                    member_role_ids = [str(r.id) for r in member.roles]
                    if not any(rid in member_role_ids for rid in voter_roles):
                        continue
                if str(member.id) not in already_voted_ids:
                    unvoted.append(member)

            if unvoted and motion_channel_id:
                channel = guild.get_channel(int(motion_channel_id))
                if channel:
                    mentions = " ".join(m.mention for m in unvoted)
                    try:
                        await channel.send(
                            f"**Lazy voters for Motion {motion_doc['motion_number']}: {motion_doc['title']}**\n{mentions}"
                        )
                    except discord.HTTPException:
                        pass

            await bot.motions.db.update_one(
                {"_id": motion_doc["_id"]},
                {"$set": {"lazy_pinged": True}},
            )

    except Exception as e:
        print(f"[check_motions] Error processing motion {motion_doc.get('_id')}: {e}")


async def _post_result(bot, guild, motion_doc, config, log_channel_id):
    if not log_channel_id:
        return
    channel = guild.get_channel(int(log_channel_id))
    if not channel:
        return

    yes_votes = motion_doc.get("yes_votes", [])
    no_votes = motion_doc.get("no_votes", [])
    abstain_votes = motion_doc.get("abstain_votes", [])
    passed = motion_doc.get("passed", False)

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

    embed = discord.Embed(
        title=f"Motion Result: Motion {motion_doc['motion_number']}: {motion_doc['title']}",
        description=description,
        color=color,
    )
    try:
        await channel.send(embed=embed)
    except discord.HTTPException:
        pass
