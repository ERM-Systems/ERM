import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import Decimal128, Int64, ObjectId
from pymongo import MongoClient

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

GUILD_COLLECTIONS = [
    {
        "key": "moderations",
        "db": "erm",
        "name": "punishments",
        "field": "Guild",
        "type": "long",
        "id_kind": "objectid",
        "longs": {"Snowflake", "UserID", "ModeratorID", "Guild", "Epoch", "UntilEpoch"},
        "dates": set(),
        "list_longs": set(),
    },
    {
        "key": "shifts",
        "db": "erm",
        "name": "shift_management",
        "field": "Guild",
        "type": "long",
        "id_kind": "objectid",
        "longs": {"UserID", "Guild"},
        "dates": set(),
        "list_longs": set(),
    },
    {
        "key": "infractions",
        "db": "erm",
        "name": "infractions",
        "field": "guild_id",
        "type": "long",
        "id_kind": "objectid",
        "longs": {
            "user_id",
            "guild_id",
            "issuer_id",
            "edited_by",
            "notification_channel_id",
            "notification_message_id",
        },
        "dates": set(),
        "list_longs": set(),
    },
    {
        "key": "loas",
        "db": "erm",
        "name": "leave_of_absences",
        "field": "guild_id",
        "type": "long",
        "id_kind": None,
        "longs": {"user_id", "guild_id", "message_id", "expiry"},
        "dates": set(),
        "list_longs": set(),
    },
    {
        "key": "applications",
        "db": "UserIdentity",
        "name": "Applications",
        "field": "guildID",
        "type": "string",
        "id_kind": "objectid",
        "longs": set(),
        "dates": set(),
        "list_longs": set(),
    },
    {
        "key": "applicationResponses",
        "db": "UserIdentity",
        "name": "ApplicationResponses",
        "field": "guildID",
        "type": "string",
        "id_kind": "objectid",
        "longs": set(),
        "dates": {"submittedAt"},
        "list_longs": set(),
    },
    {
        "key": "documentation",
        "db": "UserIdentity",
        "name": "Documentation",
        "field": "guildID",
        "type": "string",
        "id_kind": "objectid",
        "longs": set(),
        "dates": {"createdAt", "updatedAt", "faviconUpdatedAt"},
        "list_longs": set(),
    },
    {
        "key": "messages",
        "db": "UserIdentity",
        "name": "Messages",
        "field": "guild_id",
        "type": "long",
        "id_kind": "objectid",
        "longs": {"guild_id", "sender_id", "receiver_id", "timestamp"},
        "dates": set(),
        "list_longs": set(),
    },
    {
        "key": "staffRequests",
        "db": "UserIdentity",
        "name": "StaffRequests",
        "field": "guild_id",
        "type": "long",
        "id_kind": "objectid",
        "longs": {"user_id", "guild_id"},
        "dates": {"created_at"},
        "list_longs": {"acked"},
    },
    {
        "key": "auditLogs",
        "db": "UserIdentity",
        "name": "GuildAuditLogs",
        "field": "guild_id",
        "type": "string",
        "id_kind": "objectid",
        "longs": set(),
        "dates": {"timestamp"},
        "list_longs": set(),
    },
    {
        "key": "panelCommands",
        "db": "UserIdentity",
        "name": "PanelCommands",
        "field": "guild_id",
        "type": "long",
        "id_kind": "objectid",
        "longs": {"guild_id", "epoch"},
        "dates": {"expires_at"},
        "list_longs": set(),
    },
    {
        "key": "punishmentPresets",
        "db": "UserIdentity",
        "name": "PunishmentPresets",
        "field": "guildId",
        "type": "long",
        "id_kind": "objectid",
        "longs": {"guildId"},
        "dates": set(),
        "list_longs": set(),
    },
    {
        "key": "historicLogs",
        "db": "erm",
        "name": "saved_logs",
        "field": "_id",
        "type": "long",
        "id_kind": "long",
        "longs": {"_id", "guild_id", "timestamp"},
        "dates": set(),
        "list_longs": set(),
    },
    {
        "key": "reminders",
        "db": "erm",
        "name": "reminders",
        "field": "_id",
        "type": "long",
        "id_kind": "long",
        "longs": {"_id"},
        "dates": set(),
        "list_longs": set(),
    },
    {
        "key": "sessions",
        "db": "erm",
        "name": "sessions",
        "field": "_id",
        "type": "long",
        "id_kind": "long",
        "longs": {"_id", "votes", "required_votes", "created_at"},
        "dates": set(),
        "list_longs": {"voted_users"},
    },
    {
        "key": "sessionHistory",
        "db": "erm",
        "name": "session_history",
        "field": "guild_id",
        "type": "long",
        "id_kind": "objectid",
        "longs": {"guild_id", "started_at", "ended_at"},
        "dates": set(),
        "list_longs": set(),
    },
    {
        "key": "punishmentTypes",
        "db": "erm",
        "name": "punishment_types",
        "field": "_id",
        "type": "long",
        "id_kind": "long",
        "longs": {"_id"},
        "dates": set(),
        "list_longs": set(),
    },
    {
        "key": "priorities",
        "db": "UserIdentity",
        "name": "Priorities",
        "field": "guild_id",
        "type": "long",
        "id_kind": "objectid",
        "longs": {
            "guild_id",
            "user_id",
            "reviewed_by",
            "created_at",
            "reviewed_at",
            "priority_time",
        },
        "dates": set(),
        "list_longs": set(),
    },
    {
        "key": "settings",
        "db": "erm",
        "name": "settings",
        "field": "_id",
        "type": "long",
        "id_kind": "long",
        "longs": {"_id"},
        "dates": set(),
        "list_longs": set(),
    },
]

COLLECTION_KEYS = [spec["key"] for spec in GUILD_COLLECTIONS]


def load_mongo_uri() -> str:
    if not ENV_PATH.exists():
        raise SystemExit(
            f"No .env found, ensure you followed our setup guide before importing."
        )
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "MONGO_URL":
            uri = value.strip().strip("'\"").strip()
            if uri:
                return uri
    raise SystemExit(
        "MONGO_URL not set in .env, ensure you followed our setup guide before importing."
    )


def parse_iso(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    return value


def parse_digit_str(value):
    if isinstance(value, str) and (
        value.isdigit() or (value.startswith("-") and value[1:].isdigit())
    ):
        return Int64(int(value))
    return value


def convert_doc(doc, spec, guild_long):
    out = {}
    for key, value in doc.items():
        if key in spec["dates"]:
            out[key] = parse_iso(value)
        elif key in spec["longs"]:
            out[key] = parse_digit_str(value)
        elif key in spec["list_longs"] and isinstance(value, list):
            out[key] = [parse_digit_str(v) for v in value]
        else:
            out[key] = value
    gid = doc.get("_id")
    if (
        spec["id_kind"] == "objectid"
        and isinstance(gid, str)
        and ObjectId.is_valid(gid)
    ):
        out["_id"] = ObjectId(gid)
    elif spec["id_kind"] == "long":
        out["_id"] = guild_long
    return out


def settings_to_bson(data, guild_long):
    out = {}
    for key, value in data.items():
        if key == "_id":
            out[key] = guild_long
        else:
            out[key] = value
    return out


def load_backup(path):
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise SystemExit(
            "Not a valid ERM backup JSON object, please ensure you obtained your backup from export.ermbot.xyz"
        )
    if "discordId" in data or "servers" in data:
        raise SystemExit(
            "This looks like a user-data export. Only server backups can be imported."
        )
    settings = data.get("settings")
    if not isinstance(settings, dict):
        raise SystemExit(
            "'settings' is missing or not an object in the backup, please re-export your backup from export.ermbot.xyz"
        )
    guild_id = settings.get("_id")
    if guild_id is None:
        raise SystemExit(
            "I was unable to extract the guild ID from the backup, please re-export your backup from export.ermbot.xyz."
        )
    for key in COLLECTION_KEYS:
        if key not in data:
            print(f"Warning: backup is missing collection key '{key}', skipping it.")
            data[key] = [] if key != "settings" else None
            continue
        if key != "settings" and not isinstance(data[key], list):
            print(f"Warning: collection '{key}' is not a list, skipping it.")
            data[key] = []
    return data, str(guild_id)


def main():
    uri = load_mongo_uri()
    path = input("Backup file path: ").strip()
    if not path:
        raise SystemExit(
            "The specified path cannot be found. Please ensure you entered the correct path to the backup file."
        )
    data, guild_id = load_backup(Path(path))

    counts = {
        key: (len(data[key]) if key != "settings" else 1) for key in COLLECTION_KEYS
    }
    total = sum(counts.values())
    print(f"Guild: {guild_id}")
    for key in COLLECTION_KEYS:
        if counts[key]:
            print(f"- {key}: {counts[key]}")
    print(f"A total of {total} documents will be imported.")
    if not total:
        raise SystemExit(
            "Backup contains no documents to import, please ensure you obtained your backup from export.ermbot.xyz and that it is not empty."
        )

    answer = input(f"Import {total} documents into MongoDB? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        print("Canceled.")
        return

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        client.admin.command("ping")
    except Exception as exc:
        raise SystemExit(f"Could not connect to MongoDB: {exc}")

    guild_long = Int64(guild_id)
    settings_doc = settings_to_bson(data["settings"], guild_long)
    client["erm"]["settings"].replace_one(
        {"_id": guild_long}, settings_doc, upsert=True
    )
    print("Guild settings imported.")

    imported = 1
    for spec in GUILD_COLLECTIONS:
        if spec["key"] == "settings":
            continue
        docs = [convert_doc(d, spec, guild_long) for d in data[spec["key"]]]
        if not docs:
            continue
        filter_value = guild_long if spec["type"] == "long" else guild_id
        col = client[spec["db"]][spec["name"]]
        col.delete_many({spec["field"]: filter_value})
        col.insert_many(docs)
        imported += len(docs)
        print(f"[{spec['key']}] restored {len(docs)} documents")
    client.close()
    print(f"Import complete. {imported} documents added.")


if __name__ == "__main__":
    main()
