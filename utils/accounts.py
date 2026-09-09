import discord


class Accounts:
    def __init__(self, bot):
        self.bot = bot

    async def batch_user_ids(self, usernames: list):
        roblox_users = await self.bot.roblox.get_users_by_usernames(usernames, expand=False)
        return [user.id for user in roblox_users if user]

    async def roblox_to_discord(self, guild: discord.Guild, username: str, roles: list[int] = None, roblox_user_id=None):
        bot = self.bot

        if not roblox_user_id:
            roblox_user = await bot.roblox.get_user_by_username(username, expand=False)
            roblox_id = roblox_user.id
        else:
            roblox_id = roblox_user_id

        for discord_id in await bot.linking.get_discord_ids(roblox_id):
            member = guild.get_member(discord_id)
            if member:
                return member
            try:
                return await guild.fetch_member(discord_id)
            except discord.NotFound:
                pass

        # query members
        members = await guild.query_members(username)
        if not members:
            return None

        if roles is not None:
            for member in members:
                if any(role.id in roles for role in member.roles):
                    return member

        # if no roles specified OR no member with roles, return the first member found
        return members[0] if members else None

    async def discord_to_roblox(self, guild: discord.Guild, user_id: int):
        return await self.bot.linking.get_roblox_username(user_id)