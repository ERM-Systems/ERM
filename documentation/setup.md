<!-- SPDX-License-Identifier: Attribution-NonCommercial-ShareAlike (CC BY-NC-SA) -->

# Setup Guide

This document covers how to get ERM running locally for development  
or self-hosted use.

---

## Requirements

- Python 3.12  
- A MongoDB instance (local or remote)  
- A Discord application with a bot token  
- `pip` or `pipenv`

Or, with Docker:
- Docker and Docker Compose

---

## Installation

### Manual

Clone the repository and install dependencies:

```bash
git clone https://github.com/ERM-Systems/ERM
cd erm
pip install -r requirements.txt
```

### Docker

Clone the repository:

```bash
git clone https://github.com/ERM-Systems/ERM
cd erm
```

Build and start the bot with MongoDB:

```bash
docker compose up -d --build
```

This starts two containers:
- **bot** — The ERM bot
- **mongo** — MongoDB 7 with a persistent volume

The bot waits for MongoDB to pass its healthcheck before starting.
`MONGO_URL` is automatically set to `mongodb://mongo:27017` by the
compose file — you do not need to set it in `.env`.

View logs:

```bash
docker compose logs -f bot
```

Stop and remove containers:

```bash
docker compose down
```

Stop and remove containers **and** database data:

```bash
docker compose down -v
```

---

## Environment Variables

Copy `.env.template` to `.env` and fill in the required values.

```bash
cp .env.template .env
```

### Required

- `MONGO_URL` — MongoDB connection string (e.g. `mongodb://localhost:27017/erm`)  
- `ENVIRONMENT` — `PRODUCTION`, `DEVELOPMENT`, or `ALPHA`. Do not use `CUSTOM`.  
- `PRODUCTION_BOT_TOKEN` — Bot token for the production environment  

### Required by Environment

- `DEVELOPMENT_BOT_TOKEN` — Required when `ENVIRONMENT=DEVELOPMENT`  
- `ALPHA_BOT_TOKEN` — Required when `ENVIRONMENT=ALPHA`  
- `CUSTOM_GUILD_ID` — Must be set to `0` regardless of usage. Do not change.

### Optional — Monitoring

- `SENTRY_URL` — Sentry DSN for error tracking (recommended)

### Optional — Bot Features

- `BLOXLINK_API_KEY` — Required for Roblox username lookups via Bloxlink  
- `AI_API_ENABLED` — `TRUE` or `FALSE`. Enables AI-powered features  
- `API_URL` / `API_AUTH` — Endpoint and auth token for the AI API  
- `REMINDERS_ENABLED` — `TRUE` or `FALSE`. Controls the Reminders cog  
- `ACTIONS_ENABLED` — `TRUE` or `FALSE`. Controls the Actions cog and  
  the `iterate_conditions` background task

### Optional — ERM API / Panel

- `API_PRIVATE_KEY` — Private key for the internal ERM API  
- `API_STATIC_TOKEN` — Static token for API authentication  
- `BASE_API_URL` — Base URL for the ERM API  
- `PANEL_API_URL` — URL for the ERM management panel  
- `IPC_SECRET_KEY` — Secret key for inter-process communication  

### Optional — OAuth2 (website)

Required only if running the ERM website/panel:

- `DEVELOPMENT_CLIENT_ID` / `PRODUCTION_CLIENT_ID` — Discord OAuth2 client IDs  
- `DEVELOPMENT_CLIENT_SECRET` / `PRODUCTION_CLIENT_SECRET` — Discord OAuth2 secrets  
- `DEVELOPMENT_REDIRECT_URI` / `PRODUCTION_REDIRECT_URI` — OAuth2 redirect URIs  

### Optional — Google Sheets

Required only for Activity Report and Duty Leaderboard spreadsheet exports:

- `TYPE`, `PROJECT_ID`, `PRIVATE_KEY_ID`, `PRIVATE_KEY`, `CLIENT_EMAIL`,  
  `CLIENT_ID`, `AUTH_URI`, `TOKEN_URI`, `AUTH_PROVIDER_X509_CERT_URL`,  
  `CLIENT_X509_CERT_URL`  
- `DUTY_LEADERBOARD_ID` / `ACTIVITY_REPORT_ID` — Google Sheets document IDs  

### Optional — MC API

- `MC_API_URL` / `MC_API_KEY` — Used by the MapleCounty integration

### Optional — Reserved

- `GITHUB_TOKEN` — Reserved for future use, not currently used by the bot  
- `DB_NAME` — Override the default database name (`erm`). Commented out by default.

---

## Running the Bot

```bash
python main.py
```

`main.py` is a thin entrypoint that calls `run()` from `erm.py`.  
The bot loads all cogs from the `cogs/` directory automatically on startup.  
Background tasks are staggered with a 30-second delay between each start  
to avoid hammering the database on boot.

---

## Running Tests

The test suite uses `pytest` and the CI workflow runs against Python 3.12.

```bash
pytest
```

The workflow also runs `flake8` with `--exit-zero`, meaning linting  
failures are reported but do not block the test run.

A minimal environment is required to run tests:

```
ENVIRONMENT=PRODUCTION
PRODUCTION_BOT_TOKEN=anystring
MONGO_URL=mongodb://localhost:27017/test
```

---

## Discord Bot Permissions

When inviting the bot, the following scopes are required:

- `bot`  
- `applications.commands`  

---

## Notes

- `CUSTOM_GUILD_ID` must remain `0`. Do not change this even when  
  self-hosting.  
- `DB_NAME` is commented out in `.env.template`. The default database  
  name is `erm`. Uncomment and set it only if you need a different name.  
- `GITHUB_TOKEN` is not used by the bot and is reserved for future use.  
