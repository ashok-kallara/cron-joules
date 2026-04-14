"""Tests for Kia client service and config service."""

import pytest
import responses as responses_lib

from services.config_service import (
    Config,
    get_config,
    set_battery_threshold,
    set_reminder_sent,
    set_vacation_mode,
)
from services.vehicle_client import VehicleStatus

UPSTASH_URL = "https://test.upstash.io"


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

    def test_status_stores_all_fields(self):
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
    """Tests for config service (Upstash Redis-backed)."""

    @responses_lib.activate
    def test_get_config_default_values(self):
        """Should return defaults when Redis has no stored values."""
        responses_lib.add(
            responses_lib.POST,
            UPSTASH_URL,
            json={"result": [None, None, None]},
        )

        config = get_config()

        assert config.vacation_mode is False
        assert config.battery_threshold == 45
        assert config.reminder_sent_today is False

    @responses_lib.activate
    def test_get_config_stored_values(self):
        """Should return stored values from Redis."""
        responses_lib.add(
            responses_lib.POST,
            UPSTASH_URL,
            json={"result": ["true", "60", "true"]},
        )

        config = get_config()

        assert config.vacation_mode is True
        assert config.battery_threshold == 60
        assert config.reminder_sent_today is True

    @responses_lib.activate
    def test_get_config_falls_back_to_defaults_on_error(self):
        """Should return default Config when Redis is unreachable."""
        responses_lib.add(
            responses_lib.POST,
            UPSTASH_URL,
            status=500,
        )

        config = get_config()

        assert config.vacation_mode is False
        assert config.battery_threshold == 45

    @responses_lib.activate
    def test_set_vacation_mode_true(self):
        """Should send HSET vacation_mode=true to Redis."""
        responses_lib.add(responses_lib.POST, UPSTASH_URL, json={"result": 1})

        set_vacation_mode(True)

        assert len(responses_lib.calls) == 1
        import json

        body = json.loads(responses_lib.calls[0].request.body)
        assert body == ["HSET", "config", "vacation_mode", "true"]

    @responses_lib.activate
    def test_set_vacation_mode_false(self):
        """Should send HSET vacation_mode=false to Redis."""
        responses_lib.add(responses_lib.POST, UPSTASH_URL, json={"result": 0})

        set_vacation_mode(False)

        import json

        body = json.loads(responses_lib.calls[0].request.body)
        assert body == ["HSET", "config", "vacation_mode", "false"]

    @responses_lib.activate
    def test_set_battery_threshold(self):
        """Should send HSET battery_threshold to Redis."""
        responses_lib.add(responses_lib.POST, UPSTASH_URL, json={"result": 0})

        set_battery_threshold(55)

        import json

        body = json.loads(responses_lib.calls[0].request.body)
        assert body == ["HSET", "config", "battery_threshold", "55"]

    def test_set_battery_threshold_rejects_invalid_values(self):
        """Should raise ValueError for out-of-range thresholds."""
        with pytest.raises(ValueError):
            set_battery_threshold(150)

        with pytest.raises(ValueError):
            set_battery_threshold(-10)

    @responses_lib.activate
    def test_set_reminder_sent(self):
        """Should send HSET reminder_sent_today to Redis."""
        responses_lib.add(responses_lib.POST, UPSTASH_URL, json={"result": 0})

        set_reminder_sent(True)

        import json

        body = json.loads(responses_lib.calls[0].request.body)
        assert body == ["HSET", "config", "reminder_sent_today", "true"]
