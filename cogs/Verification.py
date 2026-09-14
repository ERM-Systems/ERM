import logging
import math
import time

import discord
from discord.ext import commands

from utils import verification
from utils.constants import BLANK_COLOR, GREEN_COLOR, RED_COLOR

VERIFY_COOLDOWN_SECONDS = 10

LINK_URL = (
    "https://authorize.roblox.com/?client_id=5489705006553717980"
    "&response_type=code&redirect_uri=https://verify.ermbot.xyz/auth"
    "&scope=openid+profile&state={user_id}"
)

logger = logging.getLogger(__name__)
cooldown = verification.Cooldown(VERIFY_COOLDOWN_SECONDS)


def notice(title, description, color=BLANK_COLOR):
    return discord.Embed(title=title, description=description, color=color)


def link_view(user_id):
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label="Link Roblox", url=LINK_URL.format(user_id=user_id)))
    return view


class VerifyView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Verify", style=discord.ButtonStyle.green, custom_id=verification.VERIFY_BUTTON_ID
    )
    async def verify(self, interaction: discord.Interaction, _: discord.ui.Button):
        await run_verification(self.bot, interaction)


async def verify_member(bot, member):
    wait = cooldown.remaining((member.guild.id, member.id), time.monotonic())
    if wait:
        return notice("Slow Down", f"Try again in {math.ceil(wait)} seconds."), None, None

    config = verification.get_configuration(await bot.settings.find_by_id(member.guild.id))
    if not config:
        return notice("Not Available", "Verification is not set up in this server."), None, None

    try:
        info = await verification.resolve_account(bot, member.id)
    except verification.RobloxUnavailable:
        return (
            notice(
                "Roblox Is Not Responding",
                "ERM could not reach Roblox, try again in a minute.",
                RED_COLOR,
            ),
            None,
            None,
        )

    if not info:
        return (
            notice(
                "Link Your Account",
                "Your Roblox account is not linked to ERM yet. "
                "Link it with the button below, then verify again.",
            ),
            link_view(member.id),
            None,
        )

    allowed, reason = verification.meets_requirements(info, config)
    if not allowed:
        return notice("Cannot Verify", reason, RED_COLOR), None, None

    result = await verification.apply(bot, member, info, config)

    lines = [f"You are verified as **{info.get('name')}**."]
    if result["skipped"]:
        lines.append(
            "ERM could not apply: {}. Its role may sit below the ones it needs to manage.".format(
                ", ".join(sorted(set(result["skipped"])))
            )
        )

    return notice("Verified", "\n".join(lines), GREEN_COLOR), None, (info, config)


async def run_verification(bot, interaction):
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        embed, view, verified = await verify_member(bot, interaction.user)
    except Exception as exception:
        logger.error(
            "[Verification] %s in %s failed: %s",
            interaction.user.id,
            interaction.guild.id,
            exception,
        )
        embed = notice(
            "Something Went Wrong", "ERM could not verify you right now, try again shortly.", RED_COLOR
        )
        view, verified = None, None

    reply = {"embed": embed, "ephemeral": True}
    if view:
        reply["view"] = view
    await interaction.followup.send(**reply)

    if verified:
        info, config = verified
        await send_welcome_dm(bot, interaction.user, info, config)


async def send_welcome_dm(bot, member, info, config):
    if member.bot or not config.get("dm_enabled") or not verification.template_text(config.get("dm_message")):
        return

    try:
        payload = verification.render(
            config["dm_message"], verification.replacements(member, info, member.guild)
        )
    except ValueError:
        logger.error("[Verification] the direct message in %s could not be rendered", member.guild.id)
        return

    try:
        channel = await member.create_dm()
        await bot.http.send_message(
            channel.id,
            params=discord.http.MultipartParameters(payload=payload, multipart=None, files=None),
        )
    except discord.HTTPException as exception:
        logger.info("[Verification] could not message %s: %s", member.id, exception)


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(VerifyView(self.bot))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        try:
            config = verification.get_configuration(
                await self.bot.settings.find_by_id(member.guild.id)
            )
            if not config or not config.get("auto_verify"):
                return

            info = await verification.resolve_account(self.bot, member.id)
            if not info:
                return

            allowed, _ = verification.meets_requirements(info, config)
            if not allowed:
                return

            await verification.apply(self.bot, member, info, config)
        except verification.RobloxUnavailable:
            logger.info("[Verification] Roblox unavailable, %s joined %s unverified", member.id, member.guild.id)
            return
        except Exception as exception:
            logger.error("[Verification] could not verify %s in %s: %s", member.id, member.guild.id, exception)
            return

        await send_welcome_dm(self.bot, member, info, config)

    @commands.hybrid_command(
        name="verify",
        description="Verify your Roblox account in this server.",
        extras={"ephemeral": True},
    )
    @commands.guild_only()
    async def verify(self, ctx: commands.Context):
        config = verification.get_configuration(await self.bot.settings.find_by_id(ctx.guild.id))

        if config and not config.get("command_enabled"):
            return await ctx.send(
                embed=notice("Not Available", "This server has turned the verify command off."),
                ephemeral=True,
            )

        if not ctx.interaction:
            return await ctx.send(
                embed=notice("Use the Slash Command", "Run `/verify` so ERM can reply privately.")
            )

        await run_verification(self.bot, ctx.interaction)


async def setup(bot):
    await bot.add_cog(Verification(bot))
