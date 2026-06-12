import discord
from discord.ext import tasks
from erm import Bot
import datetime
import aiohttp



@tasks.loop(hours=2)
async def check_whitelabel(bot: Bot):
    async for item in bot.whitelabel.db.find({}):
        try:
            guild = await bot.fetch_guild(int(item["GuildID"])) # looking at the db, guild ids aren't always ints
        except:
            return
        try:
            owner = await guild.fetch_member(int(item["DiscordID"]))
        except:
            return
        bot_member = guild.me
        time = datetime.datetime.now(tz=datetime.UTC)
        expiry = datetime.datetime.fromtimestamp(item["Expiry"])
        if expiry > time:
            await owner.send(embed=discord.Embed(
                title="Whitelabel Subscription Expired",
                description="Your whitelabel subscription has expired, therefore, the avatar, banner, and bio will be reset. Please renew your subscription through the web dashboard or open a ticket if you need assistance."
            ))
            await bot_member.edit(avatar=None, banner=None, bio=None, reason="Whitelabel subscription expired")
            return
        
        session = aiohttp.ClientSession()
        av = await (await session.post(item["UserData"]["AvatarURL"])).read()
        banner = await (await session.post(item["UserData"]["BannerURL"])).read()
        await bot_member.edit(avatar=av, banner=banner, bio=item["UserData"]["Bio"])
        
