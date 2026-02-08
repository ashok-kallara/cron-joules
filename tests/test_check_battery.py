"""Tests for check_battery handler."""

from unittest.mock import patch

import pytest

from services.kia_client import VehicleStatus


class TestCheckBatteryHandler:
    """Tests for the scheduled battery check handler."""

    def test_skips_when_vacation_mode_enabled(self, lambda_context, dynamodb_table):
        """Should skip check when vacation mode is enabled."""
        # Set vacation mode in DynamoDB
        dynamodb_table.put_item(Item={"pk": "config", "vacation_mode": True})

        # Clear the cache to pick up the new table
        from services import config_service
        config_service.get_dynamodb_table.cache_clear()

        with patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table):
            from handlers.check_battery import handler

            result = handler({}, lambda_context)

        assert result["status"] == "skipped"
        assert result["reason"] == "vacation_mode"

    def test_sends_reminder_when_battery_low(
        self, lambda_context, dynamodb_table, mock_telegram_config
    ):
        """Should send reminder when battery is below threshold and not charging."""
        # Set up config
        dynamodb_table.put_item(
            Item={"pk": "config", "vacation_mode": False, "battery_threshold": 45}
        )

        mock_status = VehicleStatus(
            battery_level=30,
            is_charging=False,
            is_plugged_in=False,
            estimated_range=90,
        )

        with (
            patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table),
            patch("handlers.check_battery.get_vehicle_status", return_value=mock_status),
            patch("handlers.check_battery.send_reminder") as mock_send,
        ):
            from handlers.check_battery import handler

            # Clear cache
            from services import config_service
            config_service.get_dynamodb_table.cache_clear()

            result = handler({}, lambda_context)

        assert result["status"] == "reminder_sent"
        assert result["battery_level"] == 30
        mock_send.assert_called_once()

    def test_no_reminder_when_battery_ok(
        self, lambda_context, dynamodb_table, mock_telegram_config
    ):
        """Should not send reminder when battery is above threshold."""
        dynamodb_table.put_item(
            Item={"pk": "config", "vacation_mode": False, "battery_threshold": 45}
        )

        mock_status = VehicleStatus(
            battery_level=80,
            is_charging=False,
            is_plugged_in=False,
            estimated_range=240,
        )

        with (
            patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table),
            patch("handlers.check_battery.get_vehicle_status", return_value=mock_status),
            patch("handlers.check_battery.send_reminder") as mock_send,
        ):
            from handlers.check_battery import handler
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            result = handler({}, lambda_context)

        assert result["status"] == "ok"
        assert result["battery_level"] == 80
        mock_send.assert_not_called()

    def test_no_reminder_when_charging(
        self, lambda_context, dynamodb_table, mock_telegram_config
    ):
        """Should not send reminder when car is charging."""
        dynamodb_table.put_item(
            Item={"pk": "config", "vacation_mode": False, "battery_threshold": 45}
        )

        mock_status = VehicleStatus(
            battery_level=30,
            is_charging=True,  # Car is charging
            is_plugged_in=True,
            estimated_range=90,
        )

        with (
            patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table),
            patch("handlers.check_battery.get_vehicle_status", return_value=mock_status),
            patch("handlers.check_battery.send_reminder") as mock_send,
        ):
            from handlers.check_battery import handler
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            result = handler({}, lambda_context)

        assert result["status"] == "ok"
        assert result["is_charging"] is True
        mock_send.assert_not_called()

    def test_handles_kia_api_error(self, lambda_context, dynamodb_table):
        """Should handle errors from Kia API gracefully."""
        dynamodb_table.put_item(
            Item={"pk": "config", "vacation_mode": False, "battery_threshold": 45}
        )

        with (
            patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table),
            patch(
                "handlers.check_battery.get_vehicle_status",
                side_effect=Exception("API Error"),
            ),
        ):
            from handlers.check_battery import handler
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            result = handler({}, lambda_context)

        assert result["status"] == "error"
        assert "API Error" in result["error"]
