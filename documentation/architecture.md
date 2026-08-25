<!-- SPDX-License-Identifier: Attribution-NonCommercial-ShareAlike (CC BY-NC-SA) -->

# Architecture

This document describes how ERM is structured and how its layers  
interact at runtime.

---

## Entry Points

- `main.py` — Thin entrypoint. Calls `run()` from `erm.py`.  
- `erm.py` — Defines the `Bot` class, initializes all database  
  collections, loads cogs, and starts the task scheduler.  

---

## Directory Structure

```
erm/
├── cogs/          # Discord command groups (slash commands)
├── datamodels/    # MongoDB collection wrappers and typed data classes
├── events/        # Discord gateway event handlers
├── tasks/         # Background loops (discord.ext.tasks)
├── ui/            # Discord UI components (Views, Selects, Modals)
├── utils/         # Shared utilities, API clients, and helpers
├── menus.py       # Large collection of interactive menus and flows
├── helpers.py     # Test helpers and mock infrastructure
├── erm.py         # Bot class and startup logic
└── main.py        # Entrypoint
```

---

## Cogs

Cogs live in `cogs/` and contain the bot's slash command groups.  
They are loaded automatically on startup via `pkgutil.iter_modules`.

| Cog | Responsibility |
|-----|----------------|
| `Actions` | Automated server actions triggered by conditions |
| `ActivityMonitoring` | Staff activity monitoring and reporting |
| `ActivityNotices` | Leave of absence and reduced activity requests |
| `Configuration` | Server setup and settings management |
| `CustomCommands` | User-defined slash commands per server |
| `ERLC` | ER:LC in-game integration (bans, kicks, player lookup) |
| `GameLogging` | In-game event log forwarding to Discord channels |
| `Infractions` | Staff infraction tracking and management |
| `Jishaku` | Developer/debug REPL |
| `MC` | MapleCounty game integration |
| `OAuth2` | Discord OAuth2 flow handling |
| `Privacy` | User data and consent management |
| `Punishments` | Player punishment logging (warns, bans, kicks, BOLOs) |
| `Reminders` | Scheduled reminder creation and delivery |
| `Search` | Cross-guild search for punishments and shift records |
| `ShiftLogging` | Staff shift start, end, break, and quota tracking |
| `StaffConduct` | Staff conduct reviews and documentation |
| `Utility` | General-purpose utility commands |

---

## Events

Event handlers live in `events/` and are named after the Discord  
gateway event they handle. Each file is a standalone module registered  
on the bot at startup.

Notable events:

- `on_ready` — Performs post-startup initialisation  
- `on_message` — Handles custom command dispatch and message-based triggers  
- `on_guild_join` — Initialises guild settings on first join  
- `on_member_remove` — Cleans up shift state when a member leaves  
- `on_member_update` — Tracks role changes for staff management  
- `on_shift_start` / `on_shift_end` / `on_shift_edit` / `on_shift_void` — Custom  
  events dispatched internally when shift state changes  
- `on_break_start` / `on_break_end` — Custom events for shift break lifecycle  
- `on_punishment` / `on_punishment_delete` — Custom events for punishment lifecycle  
- `on_infraction_create` / `on_infraction_revoke` — Custom events for infraction lifecycle  
- `on_loa_accept` / `on_loa_deny` — Custom events for LOA request resolution  
- `on_command_error` / `on_error` — Global error handling and Sentry reporting  
- `on_staff_request_send` — Custom event for staff request dispatch  

---

## Tasks

Background tasks live in `tasks/` and use `discord.ext.tasks.loop`.  
They are started in `Bot.start_tasks()` in `erm.py` with a  
staggered 2-second delay between each to avoid startup load spikes.

| Task | Interval | Purpose |
|------|----------|----------|
| `check_reminders` | Periodic | Delivers due reminders to users |
| `check_loa` | Periodic | Expires LOA requests past their end date |
| `iterate_ics` | Periodic | Processes integration command storage |
| `iterate_prc_logs` | Periodic | Polls PRC API and forwards logs to Discord |
| `statistics_check` | Periodic | Updates analytics records |
| `tempban_checks` | Periodic | Lifts expired temporary bans |
| `check_whitelisted_car` | Periodic | Enforces whitelisted vehicle rules in-game |
| `change_status` | Runs once | Sets the bot's initial Discord presence status |
| `process_scheduled_pms` | Periodic | Delivers scheduled direct messages |
| `sync_weather` | Periodic | Syncs real-world weather to ERLC in-game weather |
| `iterate_conditions` | Periodic | Evaluates server conditions and triggers actions |
| `check_infractions` | Hourly | Reverts expired temporary role changes from infractions |
| `prc_automations` | Periodic | Runs configured PRC automation rules |
| `mc_discord_checks` | Periodic | Runs MapleCounty Discord integration checks |

`check_reminders` and `iterate_conditions` are controlled by  
`REMINDERS_ENABLED` and `ACTIONS_ENABLED` respectively and will not  
start if those are set to `FALSE`.

---

## Data Layer

### `datamodels/`

Each file in `datamodels/` wraps a MongoDB collection as a typed  
class. They inherit from `utils/mongo.py`'s `Document` class, which  
provides standard async CRUD operations (`find_by_id`, `insert`,  
`update_by_id`, `delete_by_id`, etc.).

All datamodel instances are attached to the `Bot` object at startup  
and accessed via `bot.db.<collection>` throughout the codebase.

### `utils/mongo.py`

Provides the `Document` base class used by all datamodels. Wraps  
`pymongo`'s async client with convenience methods.

---

## Utils

| Module | Purpose |
|--------|----------|
| `api.py` | FastAPI application exposing internal HTTP endpoints |
| `prc_api.py` | Client for the ER:LC PRC API with typed response models |
| `mc_api.py` | Client for the MapleCounty API |
| `utils.py` | General shared helpers used across cogs and tasks |
| `autocompletes.py` | Discord slash command autocomplete handlers |
| `conditions.py` | Condition evaluation logic used by the Actions system |
| `constants.py` | Base server config schema, colour constants, condition  |
| | and weather code mappings |
| `emojis.py` | `EmojiController` for resolving custom emoji by name |
| `paginators.py` | Reusable paginated embed components |
| `linking.py` | Account linking client for Roblox user resolution |
| `accounts.py` | Staff account lookup helpers |
| `AI.py` | AI API client wrapper |
| `hot_reload.py` | Development cog reloading utility |
| `log_tracker.py` | `LogTracker` for structured internal logging |
| `timestamp.py` | Time delta formatting helpers |
| `username_check.py` | `UsernameChecker` for flagging suspicious Roblox usernames |
| `task_loader.py` | Registers and starts all background tasks |
| `basedataclass.py` | `BaseDataClass` used by PRC and MC API response models |

---

## Internal API

`utils/api.py` runs a FastAPI application alongside the bot using  
`uvicorn`. It exposes HTTP endpoints used by the ERM website and  
panel. It is not required for basic bot operation and can be ignored  
for most development work.

---

## Menus


`menus.py` is a large single file containing the majority of the  
bot's interactive Discord UI flows — multi-step modals, confirmation  
prompts, paginated views, and context-sensitive menus. When adding  
new interactive flows, check `menus.py` first for existing patterns  
to follow or reuse.

Do not use this file for any new views, instead, please create a new file
in the `ui` folder and reference that. `menus.py` will be removed in a later
version of ERM.
