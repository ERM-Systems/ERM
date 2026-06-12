<!-- SPDX-License-Identifier: Attribution-NonCommercial-ShareAlike (CC BY-NC-SA) -->

# Database Schema

This document describes the MongoDB collections used by ERM and  
their primary fields. All collections are accessed via their  
corresponding datamodel class in `datamodels/`.

The default database name is `erm`. This can be overridden with  
the `DB_NAME` environment variable.

---

## Collections

### `settings`

Per-guild bot configuration. One document per Discord server.

Key fields:

- `_id` — Discord guild ID  
- `antiping` — Antiping configuration (enabled, protected roles, bypass roles)  
- `staff_management` — Staff roles, management roles, LOA role, RA role, channel  
- `punishments` — Punishment log channels (general, kick, ban, BOLO)  
- `shift_management` — Shift role, quota, nickname prefix, maximum staff, role quotas  
- `shift_types` — List of custom shift type definitions  
- `game_security` — Game security webhook and channel configuration  
- `game_logging` — Channels for message logs, STS logs, and priority logs  
- `ERLC` — ER:LC integration settings (player log channel, kill log channel,  
  RDM channel, automatic shifts, elevation requirements)  
- `customisation` — Custom prefix  

The base schema is defined in `utils/constants.py` as `base_configuration`.

---

### `shifts`

Individual staff shift records.

Key fields:

- `_id` — Shift document ID  
- `UserID` — Discord user ID  
- `Guild` — Discord guild ID  
- `Type` — Shift type name  
- `StartEpoch` — Unix timestamp of shift start  
- `EndEpoch` — Unix timestamp of shift end (absent if shift is active)  
- `Breaks` — List of break objects, each with `StartEpoch` and `EndEpoch`  
- `Moderations` — List of moderation actions taken during the shift  
- `AddedTime` / `RemovedTime` — Manual time adjustments in seconds  

---

### `warnings`

Player punishment records (warnings, kicks, bans, BOLOs).

Key fields:

- `_id` — Document ID  
- `UserID` — Roblox user ID of the punished player  
- `Username` — Roblox username at time of punishment  
- `Type` — Punishment type name  
- `Reason` — Reason string  
- `Moderator` — Discord user ID of the issuing moderator  
- `Guild` — Discord guild ID  
- `Epoch` — Unix timestamp of the punishment  
- `ID` — Short human-readable punishment ID  

---

### `infractions`

Staff member infraction records.

Key fields:

- `_id` — Document ID  
- `user_id` — Discord user ID of the staff member  
- `guild_id` — Discord guild ID  
- `type` — Infraction type name  
- `reason` — Reason string  
- `moderator_id` — Discord user ID of the issuing moderator  
- `epoch` — Unix timestamp  
- `temp_roles_expire_at` — Unix timestamp for temporary role expiry (optional)  

---

### `activity_notices`

Leave of absence and reduced activity requests.

Key fields:

- `_id` — Document ID  
- `UserID` — Discord user ID  
- `Guild` — Discord guild ID  
- `Type` — `"LOA"` or `"RA"`  
- `StartEpoch` / `EndEpoch` — Duration of the notice  
- `Reason` — Reason string  
- `Status` — `"pending"`, `"accepted"`, or `"denied"`  
- `ReviewedBy` — Discord user ID of the reviewer  

---

### `custom_commands`

User-defined slash commands per guild.

Key fields:

- `_id` — Document ID  
- `Guild` — Discord guild ID  
- `Name` — Command name  
- `Response` — Response content  
- `Roles` — Role restrictions for command use  

---

### `reminders`

Scheduled reminder records.

Key fields:

- `_id` — Document ID  
- `UserID` — Discord user ID  
- `Guild` — Discord guild ID  
- `Message` — Reminder content  
- `Epoch` — Unix timestamp at which to deliver the reminder  
- `Channel` — Destination channel ID  

---

### `server_keys`

Per-guild ER:LC server API keys.

Key fields:

- `_id` — Discord guild ID  
- `Key` — ER:LC PRC API key  
- `ServerName` — ER:LC server name  

---

### `api_tokens`

ERM internal API access tokens.

Key fields:

- `_id` — Token string  
- `Guild` — Discord guild ID  
- `Scopes` — List of permitted API scopes  

---

### `analytics`

Guild-level usage analytics.

Key fields:

- `_id` — Discord guild ID  
- Various counters updated by the `statistics_check` background task  

---

### `consent`

User privacy consent records.

Key fields:

- `_id` — Discord user ID  
- `Consent` — Boolean  

---

### `oauth2_users`

Linked OAuth2 user accounts.

Key fields:

- `_id` — Discord user ID  
- `RobloxID` — Linked Roblox user ID  
- `AccessToken` / `RefreshToken` — OAuth2 credentials  

---

### `views`

Persistent Discord UI component state, allowing Views to survive  
bot restarts.

Key fields:

- `_id` — Document ID  
- `view_type` — View type identifier (e.g. `"LOAMenu"`)  
- `message_id` — Discord message ID the view is attached to  
- `args` — Serialized constructor arguments for view reconstruction  

---

### `actions`

Configured server automation actions. One document per action.

Key fields:

- `_id` — Document ID  
- `guild_id` — Discord guild ID  
- `title` — Action name  
- `condition` — The condition type to evaluate  
- `condition_value` — Threshold value for the condition  
- `condition_operator` — Comparison operator (`==`, `!=`, `<`, `<=`, `>`, `>=`)  
- `action_type` — Action to take (e.g. `"dm"`, `"message"`, `"set_perms"`)  
- `action_config` — Action-specific configuration (channel, message content, etc.)  
- `cooldown` — Cooldown between triggers in seconds  

---

### `punishment_types`

Custom punishment type definitions per guild.

Key fields:

- `_id` — Discord guild ID  
- `types` — List of punishment type objects, each with:  
  - `name` — Type name  
  - `type` — Underlying action (`warn`, `kick`, `ban`, `bolo`)  
  - `effect` — Optional in-game effect  
  - `revocable` — Whether the punishment can be revoked  

---

### `custom_flags`

Custom moderation flags per guild.

Key fields:

- `_id` — Discord guild ID  
- `flags` — List of flag name strings  

---

### `link_strings`

Key-value string store for linking-related features (guild ID keyed).

---

### `fivem_links`

FiveM server links associated with Discord guilds.

---

### `logged_command_data` (aliased as `IntegrationCommandStorage`)

Logged integration command execution data for auditing.

Key fields:

- `_id` — Document ID  
- `guild_id` — Discord guild ID  
- `user_id` — Discord user ID  
- `command` — Command name  
- `args` — Command arguments  
- `timestamp` — Unix timestamp  

---

### `saved_logs`

Preserved log entries for archival or review.

---

### `staff_connections`

Per-guild staff member connection tracking for activity and  
cross-reference lookups.

---

### `staff_conduct_config`

Per-guild staff conduct review configuration.

Key fields:

- `_id` — Discord guild ID  
- `channels` — Configured channels for conduct reviews  
- `roles` — Role-based access configuration  
- `questions` — Review question templates  

---

### `maple_keys`

MapleCounty integration API keys.

Key fields:

- `_id` — Authentication identifier  
- `Key` — API key string  

---

### `prohibited_use_keys`

Keys flagged for prohibited or abusive use.

---

### `errors`

Logged runtime error records for diagnostic review.

Key fields:

- `_id` — Document ID  
- `timestamp` — Unix timestamp of the error  
- `error` — Error type/message  
- `traceback` — Full traceback string  
- `guild_id` — Guild where the error occurred (if applicable)  

---

### `pending_oauth2`

Temporary OAuth2 state records for in-progress authentication flows.

Key fields:

- `_id` — State token  
- `user_id` — Discord user ID  
- `expires_at` — Unix timestamp for state expiry  

---

### `log_timestamps`

Timestamps used for log polling cursors (e.g., last-checked time  
for PRC log iteration).

---

### `whitelabel`

Whitelabel bot subscription instances (stored in `ERMProcessing`  
database, not the main `erm` database).

Key fields:

- `_id` — Document ID  
- `GuildID` — Discord guild ID the whitelabel bot serves  
- `Status` — Subscription status (active/inactive)  

---

## Notes

- All collections are initialized in `erm.py` and attached to the  
  `Bot` instance as `bot.db.<collection_name>`.  
- Document IDs (`_id`) are typically either Discord snowflake integers  
  or MongoDB `ObjectId` values depending on the collection.  
- The `Document` base class in `utils/mongo.py` provides standard  
  async CRUD methods. Prefer those where possible, but raw pymongo  
  calls (`find_one`, `find`, `aggregate`) may be necessary for  
  operations not exposed by the `Document` class.  
