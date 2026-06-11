# AGENTS.md

## Project Overview

ERM (Emergency Response Management) is a Discord bot for Roblox roleplay community management. It handles staff shift logging, punishments, infractions, activity monitoring, ER:LC game integration, and more.

**Stack:** Python 3.12 + discord.py + MongoDB (pymongo) + FastAPI (internal API)

---

## Quick Start

```bash
pip install -r requirements.txt
cp .env.template .env   # fill in MONGO_URL, bot token, ENVIRONMENT
python main.py
```

---

## Testing

```bash
pytest
```

Requires these env vars (no live Discord needed):
```
ENVIRONMENT=PRODUCTION
PRODUCTION_BOT_TOKEN=anystring
MONGO_URL=mongodb://localhost:27017/test
```

---

## Project Structure

See [documentation/architecture.md](documentation/architecture.md) for full details.

Key directories:
- `cogs/` — Discord slash command groups (loaded automatically)
- `datamodels/` — MongoDB collection wrappers (typed, async CRUD)
- `events/` — Discord gateway event handlers
- `tasks/` — Background loops (`discord.ext.tasks.loop`)
- `ui/` — Discord UI components (Views, Selects, Modals)
- `utils/` — Shared utilities, API clients, helpers

---

## Contribution Workflow

See [documentation/contributing.md](documentation/contributing.md) for full details.

- Branch from `Development`
- Branch prefix: `fix/`, `feat/`, `refactor/`, `docs/`, `chore/`
- Imperative commit messages, <72 char subject line
- Open PR against `Development` with clear description

### Code Style
- Python 3.12, match surrounding style
- All DB calls `async`/`await` — no blocking pymongo
- Use the `Document` class (from `utils/mongo.py`) for collection access
- Define documents on `self` in the cog `setup` hook — not in commands
- New interactive flows -> new file in `ui/`, **not** `menus.py`
- Use `utils/constants.py` for colors (`BLANK_COLOR`, `GREEN_COLOR`, `RED_COLOR`)
- Use `decouple.config()` for all env var access
- New background tasks -> `discord.ext.tasks.loop`, register in `utils/task_loader.py`

---

## AI Attribution

Per [documentation/coding-assistants.md](documentation/coding-assistants.md):
- **Do NOT** add `Signed-off-by` tags — only human contributors can certify DCO
- **DO** include an `Assisted-by: AGENT_NAME:MODEL_VERSION` tag (e.g. `Assisted-by: Claude 4.5 Sonnet`)

---

## Gotchas

- `DB_NAME` defaults to `erm`; uncomment in `.env` only if needed
- `GITHUB_TOKEN` is reserved for future use, not used by the bot
- Database schema reference: [documentation/database-schema.md](documentation/database-schema.md)
