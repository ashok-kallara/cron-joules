# AGENTS.md — Cron Joules

Cron Joules is a personal EV charging reminder system that supports **Kia EV6** and **Tesla**. It runs on GitHub Actions (no server, no Docker) and stores config in Upstash Redis. Notifications are sent via Telegram. The active vehicle is selected via the `VEHICLE_PROVIDER` environment variable.

## Project Layout

```
src/
├── main.py                   # CLI entry point: check-battery | poll-telegram
├── handlers/
│   ├── check_battery.py      # run_battery_check(is_followup) — core battery logic
│   ├── telegram_webhook.py   # process_command() and handle_* functions — bot commands
│   └── assistant_query.py    # run_assistant_query() — Google Assistant / IFTTT (future)
├── services/
│   ├── vehicle_client.py     # Provider abstraction: VehicleStatus, get_vehicle_status() factory
│   ├── kia_client.py         # hyundai_kia_connect_api wrapper (Kia provider)
│   ├── tesla_client.py       # teslapy wrapper with Redis token cache (Tesla provider)
│   ├── telegram_client.py    # Telegram Bot API wrapper (send + get_updates polling)
│   └── config_service.py     # Upstash Redis config CRUD + telegram offset + Tesla token
└── utils/
    └── secrets.py            # Environment variable reads for all credentials
scripts/
└── tesla_auth.py             # One-time Tesla OAuth helper — run locally, copy token to Secret
tests/
├── conftest.py               # Shared pytest fixtures
├── test_check_battery.py     # run_battery_check() unit tests
├── test_kia_client.py        # VehicleStatus + config_service tests (responses mock)
├── test_telegram_webhook.py  # process_command + handle_* tests
├── test_vehicle_client.py    # Provider factory routing tests
└── test_tesla_client.py      # TeslaClient + Redis cache handler tests
.github/workflows/
├── ci.yml                    # Lint + test on push/PR
├── cron-check.yml            # Battery check at 7PM & 10PM ET (4 DST-aware triggers)
└── telegram-poll.yml         # Telegram command poll every 30 minutes
pyproject.toml                # uv project config, pytest settings, ruff config
```

## Architecture

**How it runs**: GitHub Actions spins up a temporary Ubuntu VM on a schedule, runs `python src/main.py check-battery` or `poll-telegram`, then shuts down. No server, no container, no cloud infrastructure.

**Config storage**: Upstash Redis (free tier) via its REST API. All reads/writes go through `config_service.py`. The single Redis hash key is `config` with fields `vacation_mode`, `battery_threshold`, `reminder_sent_today`. Telegram poll offset is stored at key `telegram_offset`.

**Vehicle provider**: Selected via `VEHICLE_PROVIDER` env var (`kia` or `tesla`, default `kia`). `vehicle_client.py` is the public API — handlers import `get_vehicle_status()` and `get_vehicle_name()` from there. The two provider modules (`kia_client.py`, `tesla_client.py`) are imported lazily inside the factory so only the active provider's library is loaded.

**Secrets and variables**: All credentials are GitHub Actions Secrets/Variables injected as environment variables at runtime. `secrets.py` is a thin wrapper around `os.environ.get()`. Required:
- `VEHICLE_PROVIDER` (repo Variable: `kia` or `tesla`)
- `VEHICLE_NAME` (repo Variable, optional: display name, e.g. `EV6` or `Model 3`)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`
- Kia only: `KIA_USERNAME`, `KIA_PASSWORD`, `KIA_PIN`
- Tesla only: `TESLA_EMAIL`, `TESLA_REFRESH_TOKEN`, `TESLA_VIN` (optional)

**Telegram bot**: Runs in polling mode (not webhook). `poll-telegram` workflow calls `getUpdates` every 30 minutes, processes any pending commands, stores the last `update_id` in Redis to avoid reprocessing.

**DST handling**: `cron-check.yml` schedules 4 UTC cron times (7PM EDT + EST, 10PM EDT + EST). `main.py` checks `datetime.now(ZoneInfo("America/New_York")).hour` at runtime and exits early if the current ET hour isn't 19 or 22 — so the "wrong" DST trigger fires harmlessly.

## Development Commands

```bash
# Install all dependencies (including dev)
uv sync

# Run tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ --cov=src --cov-report=term-missing

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Test locally with a .env file
# Create .env with all required env vars, then:
uv run --env-file .env python src/main.py check-battery
uv run --env-file .env python src/main.py poll-telegram
```

## Testing Conventions

- **Framework**: pytest, no AWS mocking (boto3/moto are removed).
- **Config service mocking**: Use `responses` library (`responses.activate` decorator or `responses.RequestsMock()`) to intercept Upstash HTTP calls. The test URL is `https://test.upstash.io` (set in `conftest.py`).
- **Handler mocking**: Patch at the import name — e.g., `patch("handlers.check_battery.get_vehicle_status")`, not `patch("services.vehicle_client.get_vehicle_status")`.
- **Vehicle factory mocking**: Because `vehicle_client.get_vehicle_status()` uses lazy imports, patch at the source module: `patch("services.kia_client.get_kia_client", ...)` or `patch("services.tesla_client.get_tesla_client", ...)`.
- **Tesla mocking**: Mock `teslapy.Tesla` as a context manager. Set `__enter__` and `__exit__` on the mock instance.
- **Fixtures** in `tests/conftest.py`:
  - `kia_credentials`, `telegram_config`, `vehicle_provider` — all `autouse=True`, inject env vars via `monkeypatch`
  - `mock_vehicle_status` — default low-battery VehicleStatus (imported from `services.vehicle_client`)
  - `mock_telegram_send` — patches `services.telegram_client.requests` to avoid real HTTP

## Adding a New Telegram Command

1. Add a `handle_yourcommand() -> str` function in `src/handlers/telegram_webhook.py`.
2. Add the dispatch case to `process_command()` in the same file.
3. Add tests to `tests/test_telegram_webhook.py`.
4. If the command writes to config, add the corresponding `set_*` function to `config_service.py` (it calls `_redis("HSET", "config", "field", "value")`).

## Key Constraints

- **Python 3.11** only (`pyproject.toml` + GitHub Actions `python-version: '3.11'`).
- **No boto3**: AWS SDK is fully removed. Do not add it back.
- **Telegram response latency**: The bot polls every 30 minutes, so command responses are delayed up to 30 minutes. This is intentional — real-time response would require an always-on webhook endpoint.
- **Kia API quota**: `force_refresh=True` on `KiaClient.get_vehicle_status()` wakes the vehicle (~30s, uses API quota). The scheduled checks use cached data. Only use `force_refresh` if real-time accuracy is needed.
- **Tesla token rotation**: teslapy rotates the refresh token on every API call. The token is persisted in Upstash Redis (key `tesla_token`) after each run. The `TESLA_REFRESH_TOKEN` GitHub Secret is only used as a bootstrap on the very first run (before Redis has a stored token). Never rely on the env-var token being current after the first run.
- **Adding a new vehicle provider**: Create `src/services/<brand>_client.py` implementing `get_vehicle_status(force_refresh) -> VehicleStatus`. Add a branch in `vehicle_client.get_vehicle_status()`. Add tests. No changes needed in handlers.
- **GitHub Actions cron is best-effort**: Scheduled runs can be delayed up to ~15-30 minutes under load. For a charging reminder this is acceptable.
- **`_redis()` is private**: The internal Upstash HTTP function in `config_service.py` is not part of the public API. Use the named functions (`get_config`, `set_vacation_mode`, etc.) or add new ones rather than calling `_redis()` directly from outside the module.
