from utils.mongo import Document


class ScheduledSessions(Document):
    async def due(self, now: int) -> list:
        cursor = self.db.find(
            {"posted": {"$ne": True}, "scheduled_for": {"$lte": int(now)}}
        ).sort("scheduled_for", 1)
        return await cursor.to_list(length=None)

    async def upcoming(self, guildId: int) -> list:
        cursor = self.db.find({"guild": guildId, "posted": {"$ne": True}}).sort(
            "scheduled_for", 1
        )
        return await cursor.to_list(length=None)

    async def mark_posted(self, identifier) -> None:
        await self.db.update_one({"_id": identifier}, {"$set": {"posted": True}})

    async def cancel(self, guildId: int, identifier) -> bool:
        result = await self.db.delete_one(
            {"_id": identifier, "guild": guildId, "posted": {"$ne": True}}
        )
        return result.deleted_count > 0
