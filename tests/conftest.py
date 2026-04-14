"""Pytest fixtures and configuration."""

import os
from unittest.mock import MagicMock

import pytest

# Environment variables required by services
os.environ.setdefault("UPSTASH_REDIS_REST_URL", "https://test.upstash.io")
os.environ.setdefault("UPSTASH_REDIS_REST_TOKEN", "test-token")
os.environ.setdefault("LOG_LEVEL", "DEBUG")


@pytest.fixture(autouse=True)
def kia_credentials(monkeypatch):
    """Inject Kia Connect credentials as environment variables."""
    monkeypatch.setenv("KIA_USERNAME", "test@example.com")
    monkeypatch.setenv("KIA_PASSWORD", "testpassword")
    monkeypatch.setenv("KIA_PIN", "1234")


@pytest.fixture(autouse=True)
def telegram_config(monkeypatch):
    """Inject Telegram configuration as environment variables."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001234567890")


@pytest.fixture(autouse=True)
def vehicle_provider(monkeypatch):
    """Set default vehicle provider env vars for tests."""
    monkeypatch.setenv("VEHICLE_PROVIDER", "kia")
    monkeypatch.setenv("VEHICLE_NAME", "EV6")


@pytest.fixture
def mock_vehicle_status():
    """Default mock VehicleStatus (low battery, not charging)."""
    from services.vehicle_client import VehicleStatus

    return VehicleStatus(
        battery_level=40,
        is_charging=False,
        is_plugged_in=False,
        estimated_range=120,
        last_updated="2024-01-15 10:30:00",
    )


@pytest.fixture
def mock_telegram_send():
    """Mock telegram send_message to avoid real HTTP calls."""
    from unittest.mock import patch

    with patch("services.telegram_client.requests") as mock_req:
        mock_req.post.return_value.json.return_value = {
            "ok": True,
            "result": {"message_id": 123},
        }
        mock_req.post.return_value.raise_for_status = MagicMock()
        yield mock_req
