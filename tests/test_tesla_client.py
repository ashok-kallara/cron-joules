"""Tests for TeslaClient and Redis token cache helpers."""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.tesla_client import TeslaClient, _make_cache_dumper, _make_cache_loader

FAKE_EMAIL = "test@example.com"
FAKE_TOKEN = {
    FAKE_EMAIL: {
        "refresh_token": "rt_abc123",
        "access_token": "at_xyz789",
        "token_type": "Bearer",
        "expires_in": 28800,
        "expiry": "2099-01-01 00:00:00.000000",
    }
}


class TestCacheLoader:
    """Tests for the Redis-backed cache loader."""

    def test_loads_token_from_redis(self):
        """Should return token dict from Redis when available."""
        with patch(
            "services.tesla_client.get_tesla_token",
            return_value=json.dumps(FAKE_TOKEN),
        ):
            loader = _make_cache_loader(FAKE_EMAIL)
            result = loader()

        assert result == FAKE_TOKEN

    def test_bootstraps_from_env_var_when_redis_empty(self, monkeypatch):
        """Should build a minimal token from TESLA_REFRESH_TOKEN when Redis is empty."""
        monkeypatch.setenv("TESLA_REFRESH_TOKEN", "rt_bootstrap")
        monkeypatch.setenv("TESLA_EMAIL", FAKE_EMAIL)

        with patch("services.tesla_client.get_tesla_token", return_value=None):
            loader = _make_cache_loader(FAKE_EMAIL)
            result = loader()

        assert result[FAKE_EMAIL]["refresh_token"] == "rt_bootstrap"

    def test_raises_when_no_token_and_no_env_var(self, monkeypatch):
        """Should raise RuntimeError when Redis is empty and env var is not set."""
        monkeypatch.delenv("TESLA_REFRESH_TOKEN", raising=False)
        monkeypatch.setenv("TESLA_EMAIL", FAKE_EMAIL)

        with patch("services.tesla_client.get_tesla_token", return_value=None):
            loader = _make_cache_loader(FAKE_EMAIL)
            with pytest.raises(RuntimeError, match="TESLA_REFRESH_TOKEN"):
                loader()


class TestCacheDumper:
    """Tests for the Redis-backed cache dumper."""

    def test_persists_token_to_redis(self):
        """Should call set_tesla_token with JSON-serialised cache."""
        with patch("services.tesla_client.set_tesla_token") as mock_set:
            dumper = _make_cache_dumper()
            dumper(FAKE_TOKEN)

        mock_set.assert_called_once_with(json.dumps(FAKE_TOKEN))


class TestTeslaClientGetVehicleStatus:
    """Tests for TeslaClient.get_vehicle_status()."""

    def _make_vehicle(self, battery_level=80, charging_state="Disconnected", range_mi=260):
        vehicle = MagicMock()
        vehicle.__getitem__ = lambda self, key: "VIN123" if key == "vin" else None
        vehicle.get_vehicle_data.return_value = {
            "charge_state": {
                "battery_level": battery_level,
                "charging_state": charging_state,
                "battery_range": range_mi,
                "timestamp": 1700000000,
            },
            "drive_state": {},
        }
        vehicle.sync_wake_up = MagicMock()
        return vehicle

    def test_returns_vehicle_status(self, monkeypatch):
        """Should return a VehicleStatus with data from Tesla API."""
        monkeypatch.setenv("TESLA_EMAIL", FAKE_EMAIL)
        monkeypatch.setenv("TESLA_VIN", "")

        vehicle = self._make_vehicle(battery_level=75, charging_state="Disconnected")
        mock_tesla_instance = MagicMock()
        mock_tesla_instance.__enter__ = MagicMock(return_value=mock_tesla_instance)
        mock_tesla_instance.__exit__ = MagicMock(return_value=False)
        mock_tesla_instance.vehicle_list.return_value = [vehicle]

        with patch("services.tesla_client.teslapy.Tesla", return_value=mock_tesla_instance):
            client = TeslaClient()
            status = client.get_vehicle_status()

        assert status.battery_level == 75
        assert status.is_charging is False
        assert status.is_plugged_in is False

    def test_charging_state_maps_correctly(self, monkeypatch):
        """Should set is_charging=True and is_plugged_in=True when charging."""
        monkeypatch.setenv("TESLA_EMAIL", FAKE_EMAIL)
        monkeypatch.setenv("TESLA_VIN", "")

        vehicle = self._make_vehicle(charging_state="Charging")
        mock_tesla_instance = MagicMock()
        mock_tesla_instance.__enter__ = MagicMock(return_value=mock_tesla_instance)
        mock_tesla_instance.__exit__ = MagicMock(return_value=False)
        mock_tesla_instance.vehicle_list.return_value = [vehicle]

        with patch("services.tesla_client.teslapy.Tesla", return_value=mock_tesla_instance):
            status = TeslaClient().get_vehicle_status()

        assert status.is_charging is True
        assert status.is_plugged_in is True

    def test_plugged_in_not_charging(self, monkeypatch):
        """Should set is_plugged_in=True but is_charging=False when stopped/complete."""
        monkeypatch.setenv("TESLA_EMAIL", FAKE_EMAIL)
        monkeypatch.setenv("TESLA_VIN", "")

        vehicle = self._make_vehicle(charging_state="Complete")
        mock_tesla_instance = MagicMock()
        mock_tesla_instance.__enter__ = MagicMock(return_value=mock_tesla_instance)
        mock_tesla_instance.__exit__ = MagicMock(return_value=False)
        mock_tesla_instance.vehicle_list.return_value = [vehicle]

        with patch("services.tesla_client.teslapy.Tesla", return_value=mock_tesla_instance):
            status = TeslaClient().get_vehicle_status()

        assert status.is_charging is False
        assert status.is_plugged_in is True

    def test_raises_when_no_vehicles(self, monkeypatch):
        """Should raise ValueError when no vehicles are in the account."""
        monkeypatch.setenv("TESLA_EMAIL", FAKE_EMAIL)
        monkeypatch.setenv("TESLA_VIN", "")

        mock_tesla_instance = MagicMock()
        mock_tesla_instance.__enter__ = MagicMock(return_value=mock_tesla_instance)
        mock_tesla_instance.__exit__ = MagicMock(return_value=False)
        mock_tesla_instance.vehicle_list.return_value = []

        with patch("services.tesla_client.teslapy.Tesla", return_value=mock_tesla_instance):
            with pytest.raises(ValueError, match="No vehicles"):
                TeslaClient().get_vehicle_status()

    def test_raises_when_email_missing(self, monkeypatch):
        """Should raise ValueError when TESLA_EMAIL is not set."""
        monkeypatch.delenv("TESLA_EMAIL", raising=False)

        with pytest.raises(ValueError, match="TESLA_EMAIL"):
            TeslaClient().get_vehicle_status()

    def test_force_refresh_wakes_car(self, monkeypatch):
        """Should call sync_wake_up when force_refresh=True."""
        monkeypatch.setenv("TESLA_EMAIL", FAKE_EMAIL)
        monkeypatch.setenv("TESLA_VIN", "")

        vehicle = self._make_vehicle()
        mock_tesla_instance = MagicMock()
        mock_tesla_instance.__enter__ = MagicMock(return_value=mock_tesla_instance)
        mock_tesla_instance.__exit__ = MagicMock(return_value=False)
        mock_tesla_instance.vehicle_list.return_value = [vehicle]

        with patch("services.tesla_client.teslapy.Tesla", return_value=mock_tesla_instance):
            TeslaClient().get_vehicle_status(force_refresh=True)

        vehicle.sync_wake_up.assert_called_once()
