import asyncio
import datetime
import logging
import time

import discord
from discord.ext import tasks

from utils.constants import BLANK_COLOR


@tasks.loop(minutes=30, reconnect=True)
async def weekly_digest(bot):
    now = datetime.datetime.now(datetime.timezone.utc)

    async for guild_settings in bot.settings.db.find(
        {"weekly_digest.enabled": True, "weekly_digest.channel": {"$ne": None}}
    ):
        digest_config = guild_settings.get("weekly_digest", {})
        target_day = digest_config.get("day", 0)
        target_hour = digest_config.get("hour", 12)

        if now.weekday() != target_day:
            continue
        if abs(now.hour - target_hour) > 0 or now.minute >= 30:
            continue

        guild_id = guild_settings["_id"]
        guild = bot.get_guild(guild_id)
        if not guild:
            continue

        try:
            channel = await guild.fetch_channel(digest_config["channel"])
        except discord.HTTPException:
            continue

        week_ago = time.time() - (7 * 24 * 60 * 60)

        punishment_count = await bot.punishments.db.count_documents(
            {"Guild": guild_id, "Epoch": {"$gte": int(week_ago)}}
        )

        punishment_breakdown = {}
        async for doc in bot.punishments.db.find(
            {"Guild": guild_id, "Epoch": {"$gte": int(week_ago)}}
        ):
            ptype = doc.get("Type", "Unknown")
            punishment_breakdown[ptype] = punishment_breakdown.get(ptype, 0) + 1

        moderator_counts = {}
        async for doc in bot.punishments.db.find(
            {"Guild": guild_id, "Epoch": {"$gte": int(week_ago)}}
        ):
            mod = doc.get("Moderator", "Unknown")
            moderator_counts[mod] = moderator_counts.get(mod, 0) + 1

        shifts = []
        async for shift in bot.shift_management.shifts.db.find(
            {"Guild": guild_id, "EndEpoch": {"$ne": 0}, "StartEpoch": {"$gte": week_ago}}
        ):
            shifts.append(shift)

        total_shift_seconds = 0
        shifter_times = {}
        for shift in shifts:
            duration = shift["EndEpoch"] - shift["StartEpoch"]
            added = shift.get("AddedTime", 0)
            removed = shift.get("RemovedTime", 0)
            duration = duration + added - removed
            if duration < 0:
                duration = 0
            total_shift_seconds += duration
            user_id = shift["UserID"]
            shifter_times[user_id] = shifter_times.get(user_id, 0) + duration

        total_shift_hours = total_shift_seconds / 3600
        active_staff = len(shifter_times)

        top_shifters = sorted(shifter_times.items(), key=lambda x: x[1], reverse=True)[:5]
        top_shifters_text = ""
        for i, (user_id, secs) in enumerate(top_shifters, 1):
            hours = secs / 3600
            member = guild.get_member(user_id)
            name = member.mention if member else f"User {user_id}"
            top_shifters_text += f"> **{i}.** {name} — {hours:.1f}h\n"

        top_mods = sorted(moderator_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        top_mods_text = ""
        for i, (mod, count) in enumerate(top_mods, 1):
            top_mods_text += f"> **{i}.** {mod} — {count} punishments\n"

        breakdown_text = ""
        for ptype, count in sorted(punishment_breakdown.items(), key=lambda x: x[1], reverse=True):
            breakdown_text += f"> **{ptype}:** {count}\n"

        embed = discord.Embed(
            title="Weekly Digest",
            description=f"Summary for <t:{int(week_ago)}:D> — <t:{int(time.time())}:D>",
            color=BLANK_COLOR,
        )

        embed.add_field(
            name="Punishments",
            value=(
                f"> **Total:** {punishment_count}\n"
                f"{breakdown_text or '> None'}"
            ),
            inline=False,
        )

        embed.add_field(
            name="Top Moderators",
            value=top_mods_text or "> None",
            inline=False,
        )

        embed.add_field(
            name="Shifts",
            value=(
                f"> **Total Hours:** {total_shift_hours:.1f}h\n"
                f"> **Active Staff:** {active_staff}\n"
            ),
            inline=False,
        )

        embed.add_field(
            name="Top Shifters",
            value=top_shifters_text or "> None",
            inline=False,
        )

        embed.set_author(
            name=guild.name, icon_url=guild.icon.url if guild.icon else ""
        )

        try:
            await channel.send(embed=embed)
        except discord.HTTPException as e:
            logging.warning(f"Failed to send weekly digest in guild {guild_id}: {e}")
