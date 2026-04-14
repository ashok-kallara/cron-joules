"""Tests for telegram_webhook command processing."""

from unittest.mock import patch

import responses as responses_lib

from handlers.telegram_webhook import (
    handle_config,
    handle_status,
    handle_threshold,
    handle_vacation,
    process_command,
)
from services.vehicle_client import VehicleStatus

UPSTASH_URL = "https://test.upstash.io"


class TestProcessCommand:
    """Tests for the process_command dispatcher."""

    def test_dispatches_status(self):
        """Should call handle_status for /status."""
        with patch("handlers.telegram_webhook.handle_status", return_value="status reply") as mock:
            result = process_command("/status")
        assert result == "status reply"
        mock.assert_called_once()

    def test_dispatches_help(self):
        """Should return help text for /help."""
        result = process_command("/help")
        assert "Available commands" in result

    def test_dispatches_start(self):
        """Should return help text for /start."""
        result = process_command("/start")
        assert "Available commands" in result

    def test_unknown_command(self):
        """Should return unknown-command message for unrecognised commands."""
        result = process_command("/unknown")
        assert "Unknown command" in result
        assert "/help" in result

    def test_command_is_case_insensitive(self):
        """Should handle mixed-case commands."""
        with patch("handlers.telegram_webhook.handle_status", return_value="ok") as mock:
            process_command("/STATUS")
        mock.assert_called_once()


class TestHandleStatus:
    """Tests for /status command handler."""

    def test_returns_battery_info(self):
        """Should include battery level and range in response."""
        mock_status = VehicleStatus(
            battery_level=65,
            is_charging=False,
            is_plugged_in=False,
            estimated_range=200,
            last_updated="2024-01-15 10:30:00",
        )

        with patch("handlers.telegram_webhook.get_vehicle_status", return_value=mock_status):
            result = handle_status()

        assert "65%" in result
        assert "200" in result
        assert "Not charging" in result

    def test_shows_charging_status(self):
        """Should indicate charging when car is plugged in and charging."""
        mock_status = VehicleStatus(
            battery_level=80,
            is_charging=True,
            is_plugged_in=True,
            estimated_range=240,
        )

        with patch("handlers.telegram_webhook.get_vehicle_status", return_value=mock_status):
            result = handle_status()

        assert "Charging" in result

    def test_handles_api_error(self):
        """Should return an error message when Kia API fails."""
        with patch(
            "handlers.telegram_webhook.get_vehicle_status",
            side_effect=Exception("API error"),
        ):
            result = handle_status()

        assert "Error" in result


class TestHandleVacation:
    """Tests for /vacation command handler."""

    @responses_lib.activate
    def test_shows_current_status_when_no_args(self):
        """Should display current vacation mode when called with no arguments."""
        responses_lib.add(
            responses_lib.POST, UPSTASH_URL, json={"result": ["false", "45", "false"]}
        )

        result = handle_vacation([])

        assert "currently" in result.lower()

    @responses_lib.activate
    def test_enables_vacation_mode(self):
        """Should enable vacation mode for /vacation on."""
        responses_lib.add(responses_lib.POST, UPSTASH_URL, json={"result": 0})

        result = handle_vacation(["on"])

        assert "enabled" in result.lower()

    @responses_lib.activate
    def test_disables_vacation_mode(self):
        """Should disable vacation mode for /vacation off."""
        responses_lib.add(responses_lib.POST, UPSTASH_URL, json={"result": 0})

        result = handle_vacation(["off"])

        assert "disabled" in result.lower()

    def test_rejects_invalid_action(self):
        """Should return error for unknown vacation subcommand."""
        result = handle_vacation(["maybe"])

        assert "Invalid" in result


class TestHandleThreshold:
    """Tests for /threshold command handler."""

    @responses_lib.activate
    def test_shows_current_threshold_when_no_args(self):
        """Should display current threshold when called with no arguments."""
        responses_lib.add(
            responses_lib.POST, UPSTASH_URL, json={"result": ["false", "45", "false"]}
        )

        result = handle_threshold([])

        assert "45%" in result

    @responses_lib.activate
    def test_sets_valid_threshold(self):
        """Should update threshold for a valid value."""
        responses_lib.add(responses_lib.POST, UPSTASH_URL, json={"result": 0})

        result = handle_threshold(["60"])

        assert "60%" in result

    def test_rejects_out_of_range_threshold(self):
        """Should reject threshold values outside 0-100."""
        result = handle_threshold(["150"])

        assert "between 0 and 100" in result

    def test_rejects_non_numeric_threshold(self):
        """Should reject non-numeric threshold input."""
        result = handle_threshold(["abc"])

        assert "Invalid" in result


class TestHandleConfig:
    """Tests for /config command handler."""

    @responses_lib.activate
    def test_returns_all_settings(self):
        """Should display threshold, vacation mode, and reminder status."""
        responses_lib.add(
            responses_lib.POST, UPSTASH_URL, json={"result": ["false", "45", "false"]}
        )

        result = handle_config()

        assert "45%" in result
        assert "Disabled" in result  # vacation mode
