import logging
import typing

import aiohttp
from discord.ext import commands

logger = logging.getLogger(__name__)


class AccountLinking:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        bot.external_http_sessions.append(self.session)

    @staticmethod
    def _id_variants(value) -> list:
        try:
            return [int(value), str(int(value))]
        except (TypeError, ValueError):
            return [value]

    async def get_roblox_id(self, discord_id: int) -> typing.Optional[int]:
        document = await self.bot.oauth2_users.db.find_one(
            {"discord_id": {"$in": self._id_variants(discord_id)}}
        )
        if not document:
            return None

        try:
            return int(document["roblox_id"])
        except (KeyError, TypeError, ValueError):
            logger.warning(
                "Link document for Discord user %s has an unusable roblox_id", discord_id
            )
            return None

    async def get_discord_ids(self, roblox_id: int) -> list[int]:
        discord_ids = []
        async for document in self.bot.oauth2_users.db.find(
            {"roblox_id": {"$in": self._id_variants(roblox_id)}}
        ):
            try:
                discord_ids.append(int(document["discord_id"]))
            except (KeyError, TypeError, ValueError):
                continue
        return discord_ids

    async def get_discord_id(self, roblox_id: int) -> typing.Optional[int]:
        discord_ids = await self.get_discord_ids(roblox_id)
        return discord_ids[0] if discord_ids else None

    async def get_roblox_info(self, roblox_id) -> dict:
        if not roblox_id:
            return {"errors": [{"message": "No Roblox user ID was provided."}]}

        try:
            async with self.session.get(
                "https://users.roblox.com/v1/users/{}".format(roblox_id)
            ) as resp:
                return await resp.json()
        except (aiohttp.ClientError, ValueError) as e:
            logger.warning("Failed to fetch Roblox user %s: %s", roblox_id, e)
            return {"errors": [{"message": "Could not reach the Roblox API."}]}

    async def get_roblox_username(self, discord_id: int) -> typing.Optional[str]:
        roblox_id = await self.get_roblox_id(discord_id)
        if not roblox_id:
            return None

        info = await self.get_roblox_info(roblox_id)
        return info.get("name")