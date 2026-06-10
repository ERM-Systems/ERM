from utils.mongo import Document


class LogTimestamps(Document):
    async def get_timestamps(self, guild_id: int) -> dict:
        doc = await self.find_by_id(guild_id)
        if not doc:
            return {}
        return doc.get("timestamps", {})

    async def save_timestamps(self, guild_id: int, timestamps: dict):
        await self.upsert({"_id": guild_id, "timestamps": timestamps})
