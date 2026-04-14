# Cron Joules

A GitHub Actions-based reminder system for EVs that sends Telegram notifications when your car needs charging. Supports **Kia EV6** and **Tesla**.

Runs entirely on GitHub Actions runners.

## Features

- **Scheduled Checks**: Checks battery at 7 PM and 10 PM daily (America/New_York, DST-aware)
- **Smart Reminders**: Only notifies when battery is below threshold AND charger is not connected
- **Follow-up Alerts**: Sends a second reminder at 10 PM if car still isn't charging after the 7 PM alert
- **Telegram Bot Commands** (responds within ~30 minutes via polling):
  - `/status` — Check current battery level and range
  - `/vacation on/off` — Disable/enable reminders when away
  - `/threshold <number>` — Set battery alert threshold (default: 45%)
  - `/config` — View current settings
- **Google Assistant** (future): Ask "Does my car need charging?" via IFTTT

## How It Works

```
GitHub Actions (cron)
    │
    ├── 7PM / 10PM ET ──▶ python src/main.py check-battery
    │                          │
    │                          ├── Reads config from Upstash Redis
    │                          ├── Fetches battery status from Kia Connect API
    │                          └── Sends Telegram message if needed
    │
    └── Every 30 min ──▶ python src/main.py poll-telegram
                               │
                               ├── Calls Telegram getUpdates API
                               ├── Processes any pending bot commands
                               └── Stores last update_id in Upstash Redis
```

**Storage**: Upstash Redis (free tier) stores three config values — `vacation_mode`, `battery_threshold`, `reminder_sent_today` — and the Telegram poll offset.

**Secrets**: Stored as GitHub Actions Secrets, injected as environment variables at runtime. Nothing is in the code.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python package manager
- A [GitHub](https://github.com) account (repo can be public or private)
- **Kia**: A [Kia Connect](https://www.kia.com/us/en/kia-connect) account with your EV6 registered  
  **Tesla**: A Tesla account (OAuth authentication via `scripts/tesla_auth.py`)
- A Telegram account

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/yourusername/cron-joules.git
cd cron-joules
uv sync
```

### 2. Create a Telegram bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Save the **bot token** (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Start a chat with the bot or add it to a group
5. Get your **chat ID** using [@userinfobot](https://t.me/userinfobot)

### 3. Create an Upstash Redis database

1. Sign up at [console.upstash.com](https://console.upstash.com) (free, no credit card required)
2. Create a new Redis database — any region, Global type
3. On the database page, copy:
   - **REST URL** (looks like `https://xxx.upstash.io`)
   - **REST Token**
4. Initialise the config (run once from your terminal):

```bash
curl -X POST "$UPSTASH_REDIS_REST_URL" \
  -H "Authorization: Bearer $UPSTASH_REDIS_REST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '["HSET", "config", "vacation_mode", "false", "battery_threshold", "45", "reminder_sent_today", "false"]'
```

### 4. Add GitHub Actions Secrets and Variables

In your repo: **Settings → Secrets and variables → Actions**

**Secrets** (sensitive — never visible in logs):

| Secret name | Where to find it |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From @BotFather in step 2 |
| `TELEGRAM_CHAT_ID` | From @userinfobot in step 2 |
| `UPSTASH_REDIS_REST_URL` | From Upstash dashboard in step 3 |
| `UPSTASH_REDIS_REST_TOKEN` | From Upstash dashboard in step 3 |
| `KIA_USERNAME` | Kia Connect email _(Kia only)_ |
| `KIA_PASSWORD` | Kia Connect password _(Kia only)_ |
| `KIA_PIN` | Kia Connect PIN _(Kia only)_ |
| `TESLA_EMAIL` | Your Tesla account email _(Tesla only)_ |
| `TESLA_REFRESH_TOKEN` | Output of `scripts/tesla_auth.py` _(Tesla only)_ |
| `TESLA_VIN` | Your car's VIN _(Tesla only, optional if only one vehicle)_ |

**Variables** (non-sensitive, visible in logs — add under "Variables" tab):

| Variable name | Value |
|---|---|
| `VEHICLE_PROVIDER` | `kia` or `tesla` |
| `VEHICLE_NAME` | Display name in messages, e.g. `EV6` or `Model 3` (optional) |

#### Tesla one-time authentication

Before adding `TESLA_REFRESH_TOKEN`, run this locally once:

```bash
TESLA_EMAIL=your@email.com uv run python scripts/tesla_auth.py
```

This opens a browser for Tesla SSO login and prints your refresh token. Copy it to the GitHub Secret.

### 5. Push to main — you're live

Once the secrets are set, push to the `main` branch. The workflows activate automatically.

**Test immediately** without waiting for the schedule: go to **Actions → Battery Check → Run workflow**.

## Workflows

| Workflow | Schedule | What it does |
|---|---|---|
| `cron-check.yml` | 7 PM & 10 PM ET daily | Checks battery, sends Telegram reminder if needed |
| `telegram-poll.yml` | Every 30 minutes | Fetches pending bot commands and responds |
| `ci.yml` | Every push / PR | Runs linting and tests |

The battery check uses four UTC cron triggers (for 7 PM/10 PM × EDT/EST) to handle DST automatically. The script checks the current Eastern time at runtime and exits early if it's not actually 7 PM or 10 PM ET.

## Local Development

### Run tests

```bash
uv run pytest tests/ -v
```

### Run with coverage

```bash
uv run pytest tests/ --cov=src --cov-report=term-missing
```

### Lint and format

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

### Run locally against real APIs

Create a `.env` file (this is git-ignored):

```bash
KIA_USERNAME=your-email@example.com
KIA_PASSWORD=yourpassword
KIA_PIN=1234
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_CHAT_ID=-1001234567890
UPSTASH_REDIS_REST_URL=https://xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-token
```

Then run:

```bash
# Load .env and run battery check
uv run --env-file .env python src/main.py check-battery

# Load .env and poll for Telegram commands
uv run --env-file .env python src/main.py poll-telegram
```

## Bot Commands

Send these to your bot in Telegram. The bot responds on the next poll (within ~30 minutes):

| Command | Description |
|---|---|
| `/status` | Current battery %, estimated range, and charging state |
| `/vacation on` | Disable all reminders (e.g. when away for the week) |
| `/vacation off` | Re-enable reminders |
| `/threshold 50` | Set alert threshold to 50% (accepts 0–100) |
| `/config` | Show current threshold, vacation mode, and today's reminder status |
| `/help` | Show available commands |

## Configuration

Config is stored in Upstash Redis and updated via bot commands. You can also set it directly:

```bash
# Disable reminders (vacation mode)
curl -X POST "$UPSTASH_REDIS_REST_URL" \
  -H "Authorization: Bearer $UPSTASH_REDIS_REST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '["HSET", "config", "vacation_mode", "true"]'

# Change battery threshold to 60%
curl -X POST "$UPSTASH_REDIS_REST_URL" \
  -H "Authorization: Bearer $UPSTASH_REDIS_REST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '["HSET", "config", "battery_threshold", "60"]'
```

## Troubleshooting

**No reminder sent when battery is low**
- Check the workflow run logs in the Actions tab
- Verify your Kia Connect credentials are correct (`/status` command is a quick test)
- Make sure `vacation_mode` isn't enabled (`/config`)

**Bot not responding to commands**
- Commands are processed on the next poll (up to 30 minutes later)
- Check the `telegram-poll` workflow run in the Actions tab for errors
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are correct

**Workflow not running on schedule**
- GitHub Actions cron can be delayed up to ~30 minutes during high load — this is normal
- Scheduled workflows are automatically disabled if the repo has no activity for 60 days. Re-enable them in the Actions tab.
- To trigger immediately, use **Actions → [workflow name] → Run workflow**

**"No vehicles found" error**
- Make sure your EV6 is registered and visible in the Kia Connect mobile app
- Kia Connect accounts occasionally require re-authentication — try logging out and back in to the app

## Cost

| Service | Free tier | Usage |
|---|---|---|
| GitHub Actions | 2,000 min/month (private) or unlimited (public) | ~100–150 min/month |
| Upstash Redis | 10,000 commands/day | ~100 commands/day |

**Monthly cost: $0**

## License

MIT
