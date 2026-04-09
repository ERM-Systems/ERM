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

---

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/mikeywhiston/erm
cd erm
pip install -r requirements.txt
```

---

## Environment Variables

Copy `.env.template` to `.env` and fill in the required values.

```bash
cp .env.template .env
```

### Required

- `MONGO_URL` — MongoDB connection string (e.g. `mongodb://localhost:27017/erm`)  
- `ENVIRONMENT` — `PRODUCTION` or `DEVELOPMENT`  
- `PRODUCTION_BOT_TOKEN` — Bot token for the production environment  
- `DEVELOPMENT_BOT_TOKEN` — Bot token for the development environment  

### Optional — Bot Features

- `BLOXLINK_API_KEY` — Required for Roblox username lookups via Bloxlink  
- `AI_API_ENABLED` — `TRUE` or `FALSE`. Enables AI-powered features  
- `API_URL` / `API_AUTH` — Endpoint and auth token for the AI API  
- `REMINDERS_ENABLED` — `TRUE` or `FALSE`. Controls the Reminders cog  
- `ACTIONS_ENABLED` — `TRUE` or `FALSE`. Controls the Actions cog and  
  the `iterate_conditions` background task  

### Optional — Internal API

These are used by the FastAPI backend in `utils/api.py` and are not  
required for basic bot operation:

- `API_PRIVATE_KEY` / `API_STATIC_TOKEN` / `BASE_API_URL` / `PANEL_API_URL`  
- `IPC_SECRET_KEY` — Used for inter-process communication  

### Optional — OAuth2

Required only if running the website backend:

- `DEVELOPMENT_CLIENT_ID` / `PRODUCTION_CLIENT_ID`  
- `DEVELOPMENT_CLIENT_SECRET` / `PRODUCTION_CLIENT_SECRET`  
- `DEVELOPMENT_REDIRECT_URI` / `PRODUCTION_REDIRECT_URI`  

### Optional — Google Sheets

Required only for Activity Report and Duty Leaderboard spreadsheet exports:

- `TYPE`, `PROJECT_ID`, `PRIVATE_KEY_ID`, `PRIVATE_KEY`, `CLIENT_EMAIL`,  
  `CLIENT_ID`, `AUTH_URI`, `TOKEN_URI`, `AUTH_PROVIDER_X509_CERT_URL`,  
  `CLIENT_X509_CERT_URL`  
- `DUTY_LEADERBOARD_ID` / `ACTIVITY_REPORT_ID` — Google Sheets document IDs  

### Optional — MC API

- `MC_API_URL` / `MC_API_KEY` — Used by the MapleCounty integration  

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

When inviting the bot, the following are required:

- `Administrator` (the invite link in the README uses this)  
- `applications.commands` scope for slash command registration  

---

## Notes

- `CUSTOM_GUILD_ID` must remain `0`. Do not change this even when  
  self-hosting.  
- `DB_NAME` is commented out in `.env.template`. The default database  
  name is `erm`. Uncomment and set it only if you need a different name.  
- `GITHUB_TOKEN` is not used by the bot and is reserved for future use.  
