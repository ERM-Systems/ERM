import discord
from discord.ext import commands

from utils.constants import BLANK_COLOR
from utils.utils import activity_notice_channel


class OnRADeny(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ra_deny(
        self, s_loa: dict, denied_by: int, reason: str = "No reason provided."
    ):
        guild = self.bot.get_guild(s_loa["guild_id"])
        try:
            user = await guild.fetch_member(int(s_loa["user_id"]))
        except:
            return

        try:
            await user.send(
                embed=discord.Embed(
                    title="Activity Notice Denied",
                    description=f"Your {s_loa['type']} request in **{guild.name}** was denied.\n**Reason:** {reason}",
                    color=BLANK_COLOR,
                )
            )
        except:
            pass

        settings = await self.bot.settings.find_by_id(guild.id)
        msg = s_loa["message_id"]
        ra_channel_id = activity_notice_channel(settings, s_loa["type"])
        if not ra_channel_id:
            return
        ra_channel = guild.get_channel(ra_channel_id) or await guild.fetch_channel(
            ra_channel_id
        )
        messg = None
        try:
            messg = await ra_channel.fetch_message(msg)
        except:
            pass
        if not messg:
            return

        embed = messg.embeds[0]
        embed.title = f"{s_loa['type']} Denied"
        embed.colour = BLANK_COLOR
        try:
            denied_by_user = guild.get_member(denied_by) or await guild.fetch_member(
                denied_by
            )
        except:
            pass

        embed.set_footer(
            text=f"Denied by {denied_by_user.name if denied_by_user else 'n/a'}"
        )

        await messg.edit(embed=embed, view=None)

        view_item = await self.bot.views.db.find_one({"message_id": messg.id})
        await self.bot.views.delete_by_id(view_item["_id"])


async def setup(bot):
    await bot.add_cog(OnRADeny(bot))
