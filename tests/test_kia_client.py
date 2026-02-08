"""Tests for Kia client service."""

import pytest

from services.kia_client import VehicleStatus


class TestVehicleStatus:
    """Tests for VehicleStatus dataclass."""

    def test_needs_charging_when_not_plugged(self):
        """Should indicate charging needed when not plugged in and not charging."""
        status = VehicleStatus(
            battery_level=30,
            is_charging=False,
            is_plugged_in=False,
            estimated_range=90,
        )
        assert status.needs_charging is True

    def test_no_charging_needed_when_plugged(self):
        """Should not indicate charging needed when plugged in."""
        status = VehicleStatus(
            battery_level=30,
            is_charging=False,
            is_plugged_in=True,
            estimated_range=90,
        )
        assert status.needs_charging is False

    def test_no_charging_needed_when_charging(self):
        """Should not indicate charging needed when already charging."""
        status = VehicleStatus(
            battery_level=30,
            is_charging=True,
            is_plugged_in=True,
            estimated_range=90,
        )
        assert status.needs_charging is False

    def test_status_with_all_fields(self):
        """Should correctly store all status fields."""
        status = VehicleStatus(
            battery_level=75,
            is_charging=True,
            is_plugged_in=True,
            estimated_range=225,
            last_updated="2024-01-15 10:30:00",
        )

        assert status.battery_level == 75
        assert status.is_charging is True
        assert status.is_plugged_in is True
        assert status.estimated_range == 225
        assert status.last_updated == "2024-01-15 10:30:00"


class TestConfigService:
    """Tests for config service."""

    def test_get_config_default_values(self, dynamodb_table):
        """Should return default values when no config exists."""
        from unittest.mock import patch

        with patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table):
            from services.config_service import get_config
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            config = get_config()

        assert config.vacation_mode is False
        assert config.battery_threshold == 45
        assert config.reminder_sent_today is False

    def test_get_config_stored_values(self, dynamodb_table):
        """Should return stored values when config exists."""
        from unittest.mock import patch

        dynamodb_table.put_item(
            Item={
                "pk": "config",
                "vacation_mode": True,
                "battery_threshold": 60,
                "reminder_sent_today": True,
            }
        )

        with patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table):
            from services.config_service import get_config
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            config = get_config()

        assert config.vacation_mode is True
        assert config.battery_threshold == 60
        assert config.reminder_sent_today is True

    def test_set_vacation_mode(self, dynamodb_table):
        """Should update vacation mode in DynamoDB."""
        from unittest.mock import patch

        with patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table):
            from services.config_service import set_vacation_mode, get_config
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            set_vacation_mode(True)
            config = get_config()

        assert config.vacation_mode is True

    def test_set_battery_threshold(self, dynamodb_table):
        """Should update battery threshold in DynamoDB."""
        from unittest.mock import patch

        with patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table):
            from services.config_service import set_battery_threshold, get_config
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            set_battery_threshold(55)
            config = get_config()

        assert config.battery_threshold == 55

    def test_set_battery_threshold_invalid(self, dynamodb_table):
        """Should reject invalid threshold values."""
        from unittest.mock import patch

        with patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table):
            from services.config_service import set_battery_threshold
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            with pytest.raises(ValueError):
                set_battery_threshold(150)

            with pytest.raises(ValueError):
                set_battery_threshold(-10)
