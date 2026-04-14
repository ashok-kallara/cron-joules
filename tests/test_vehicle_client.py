"""Tests for vehicle_client provider abstraction."""

from unittest.mock import MagicMock, patch

import pytest

from services.vehicle_client import VehicleStatus, get_vehicle_name, get_vehicle_provider, get_vehicle_status


class TestGetVehicleProvider:
    """Tests for get_vehicle_provider()."""

    def test_defaults_to_kia(self, monkeypatch):
        monkeypatch.delenv("VEHICLE_PROVIDER", raising=False)
        assert get_vehicle_provider() == "kia"

    def test_reads_env_var(self, monkeypatch):
        monkeypatch.setenv("VEHICLE_PROVIDER", "tesla")
        assert get_vehicle_provider() == "tesla"

    def test_normalises_to_lowercase(self, monkeypatch):
        monkeypatch.setenv("VEHICLE_PROVIDER", "TESLA")
        assert get_vehicle_provider() == "tesla"


class TestGetVehicleName:
    """Tests for get_vehicle_name()."""

    def test_kia_defaults_to_ev6(self, monkeypatch):
        monkeypatch.setenv("VEHICLE_PROVIDER", "kia")
        monkeypatch.delenv("VEHICLE_NAME", raising=False)
        assert get_vehicle_name() == "EV6"

    def test_tesla_defaults_to_tesla(self, monkeypatch):
        monkeypatch.setenv("VEHICLE_PROVIDER", "tesla")
        monkeypatch.delenv("VEHICLE_NAME", raising=False)
        assert get_vehicle_name() == "Tesla"

    def test_custom_name_overrides_default(self, monkeypatch):
        monkeypatch.setenv("VEHICLE_PROVIDER", "kia")
        monkeypatch.setenv("VEHICLE_NAME", "Niro EV")
        assert get_vehicle_name() == "Niro EV"


class TestGetVehicleStatus:
    """Tests for the get_vehicle_status() factory."""

    def test_routes_to_kia_client(self, monkeypatch):
        monkeypatch.setenv("VEHICLE_PROVIDER", "kia")

        mock_status = VehicleStatus(
            battery_level=70,
            is_charging=False,
            is_plugged_in=False,
            estimated_range=200,
        )
        mock_kia = MagicMock()
        mock_kia.get_vehicle_status.return_value = mock_status

        # Patch at the source module — vehicle_client uses lazy imports
        with patch("services.kia_client.get_kia_client", return_value=mock_kia):
            result = get_vehicle_status()

        assert result.battery_level == 70
        mock_kia.get_vehicle_status.assert_called_once_with(force_refresh=False)

    def test_routes_to_tesla_client(self, monkeypatch):
        monkeypatch.setenv("VEHICLE_PROVIDER", "tesla")

        mock_status = VehicleStatus(
            battery_level=85,
            is_charging=True,
            is_plugged_in=True,
            estimated_range=280,
        )
        mock_tesla = MagicMock()
        mock_tesla.get_vehicle_status.return_value = mock_status

        # Patch at the source module — vehicle_client uses lazy imports
        with patch("services.tesla_client.get_tesla_client", return_value=mock_tesla):
            result = get_vehicle_status()

        assert result.battery_level == 85
        mock_tesla.get_vehicle_status.assert_called_once_with(force_refresh=False)

    def test_passes_force_refresh(self, monkeypatch):
        monkeypatch.setenv("VEHICLE_PROVIDER", "kia")

        mock_kia = MagicMock()
        mock_kia.get_vehicle_status.return_value = VehicleStatus(
            battery_level=50, is_charging=False, is_plugged_in=False, estimated_range=150
        )

        with patch("services.kia_client.get_kia_client", return_value=mock_kia):
            get_vehicle_status(force_refresh=True)

        mock_kia.get_vehicle_status.assert_called_once_with(force_refresh=True)
