"""Tests for check_battery handler."""

from unittest.mock import patch

from handlers.check_battery import run_battery_check
from services.config_service import Config
from services.vehicle_client import VehicleStatus


class TestRunBatteryCheck:
    """Tests for the battery check function."""

    def test_skips_when_vacation_mode_enabled(self):
        """Should skip check when vacation mode is enabled."""
        with patch(
            "handlers.check_battery.get_config",
            return_value=Config(vacation_mode=True),
        ):
            result = run_battery_check(is_followup=False)

        assert result["status"] == "skipped"
        assert result["reason"] == "vacation_mode"

    def test_skips_followup_when_no_initial_reminder(self):
        """Should skip 10PM follow-up if 7PM reminder was never sent."""
        with patch(
            "handlers.check_battery.get_config",
            return_value=Config(vacation_mode=False, reminder_sent_today=False),
        ):
            result = run_battery_check(is_followup=True)

        assert result["status"] == "skipped"
        assert result["reason"] == "no_initial_reminder"

    def test_sends_reminder_when_battery_low(self):
        """Should send reminder when battery is below threshold and not charging."""
        mock_status = VehicleStatus(
            battery_level=30,
            is_charging=False,
            is_plugged_in=False,
            estimated_range=90,
        )

        with (
            patch(
                "handlers.check_battery.get_config",
                return_value=Config(vacation_mode=False, battery_threshold=45),
            ),
            patch("handlers.check_battery.get_vehicle_status", return_value=mock_status),
            patch("handlers.check_battery.send_reminder") as mock_send,
            patch("handlers.check_battery.set_reminder_sent") as mock_set,
        ):
            result = run_battery_check(is_followup=False)

        assert result["status"] == "reminder_sent"
        assert result["battery_level"] == 30
        assert result["is_followup"] is False
        mock_send.assert_called_once_with(30, is_followup=False)
        mock_set.assert_called_once_with(True)

    def test_sends_followup_reminder(self):
        """Should send follow-up reminder at 10PM if initial was sent."""
        mock_status = VehicleStatus(
            battery_level=30,
            is_charging=False,
            is_plugged_in=False,
            estimated_range=90,
        )

        with (
            patch(
                "handlers.check_battery.get_config",
                return_value=Config(
                    vacation_mode=False, battery_threshold=45, reminder_sent_today=True
                ),
            ),
            patch("handlers.check_battery.get_vehicle_status", return_value=mock_status),
            patch("handlers.check_battery.send_reminder") as mock_send,
            patch("handlers.check_battery.set_reminder_sent"),
        ):
            result = run_battery_check(is_followup=True)

        assert result["status"] == "reminder_sent"
        assert result["is_followup"] is True
        mock_send.assert_called_once_with(30, is_followup=True)

    def test_no_reminder_when_battery_ok(self):
        """Should not send reminder when battery is above threshold."""
        mock_status = VehicleStatus(
            battery_level=80,
            is_charging=False,
            is_plugged_in=False,
            estimated_range=240,
        )

        with (
            patch(
                "handlers.check_battery.get_config",
                return_value=Config(vacation_mode=False, battery_threshold=45),
            ),
            patch("handlers.check_battery.get_vehicle_status", return_value=mock_status),
            patch("handlers.check_battery.send_reminder") as mock_send,
            patch("handlers.check_battery.set_reminder_sent") as mock_set,
        ):
            result = run_battery_check(is_followup=False)

        assert result["status"] == "ok"
        assert result["battery_level"] == 80
        mock_send.assert_not_called()
        mock_set.assert_called_once_with(False)  # Reset reminder flag

    def test_no_reminder_when_charging(self):
        """Should not send reminder when car is already charging."""
        mock_status = VehicleStatus(
            battery_level=30,
            is_charging=True,
            is_plugged_in=True,
            estimated_range=90,
        )

        with (
            patch(
                "handlers.check_battery.get_config",
                return_value=Config(vacation_mode=False, battery_threshold=45),
            ),
            patch("handlers.check_battery.get_vehicle_status", return_value=mock_status),
            patch("handlers.check_battery.send_reminder") as mock_send,
            patch("handlers.check_battery.set_reminder_sent"),
        ):
            result = run_battery_check(is_followup=False)

        assert result["status"] == "ok"
        assert result["is_charging"] is True
        mock_send.assert_not_called()

    def test_no_reminder_when_plugged_in_not_charging(self):
        """Should not send reminder when plugged in (even if not actively charging)."""
        mock_status = VehicleStatus(
            battery_level=30,
            is_charging=False,
            is_plugged_in=True,
            estimated_range=90,
        )

        with (
            patch(
                "handlers.check_battery.get_config",
                return_value=Config(vacation_mode=False, battery_threshold=45),
            ),
            patch("handlers.check_battery.get_vehicle_status", return_value=mock_status),
            patch("handlers.check_battery.send_reminder") as mock_send,
            patch("handlers.check_battery.set_reminder_sent"),
        ):
            result = run_battery_check(is_followup=False)

        assert result["status"] == "ok"
        mock_send.assert_not_called()

    def test_handles_kia_api_error(self):
        """Should handle errors from Kia API gracefully."""
        with (
            patch(
                "handlers.check_battery.get_config",
                return_value=Config(vacation_mode=False, battery_threshold=45),
            ),
            patch(
                "handlers.check_battery.get_vehicle_status",
                side_effect=Exception("API Error"),
            ),
        ):
            result = run_battery_check(is_followup=False)

        assert result["status"] == "error"
        assert "API Error" in result["error"]
