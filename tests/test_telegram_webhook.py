"""Tests for telegram_webhook handler."""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.kia_client import VehicleStatus

VALID_WEBHOOK_SECRET = "test-webhook-secret-token"


class TestTelegramWebhookHandler:
    """Tests for Telegram webhook handler."""

    def _make_event(self, text: str, chat_id: int = -1001234567890) -> dict:
        """Create a mock Telegram webhook event."""
        return {
            "headers": {
                "X-Telegram-Bot-Api-Secret-Token": VALID_WEBHOOK_SECRET,
            },
            "body": json.dumps({
                "message": {
                    "chat": {"id": chat_id},
                    "text": text,
                    "message_id": 123,
                }
            }),
        }

    def test_rejects_request_without_secret(self, lambda_context, mock_telegram_config):
        """Should reject requests missing the secret token header."""
        event = {
            "headers": {},
            "body": json.dumps({
                "message": {
                    "chat": {"id": -1001234567890},
                    "text": "/status",
                    "message_id": 123,
                }
            }),
        }

        with patch(
            "handlers.telegram_webhook.get_telegram_webhook_secret",
            return_value=VALID_WEBHOOK_SECRET,
        ):
            from handlers.telegram_webhook import handler

            result = handler(event, lambda_context)

        assert result["statusCode"] == 401

    def test_rejects_request_with_wrong_secret(self, lambda_context, mock_telegram_config):
        """Should reject requests with an incorrect secret token."""
        event = {
            "headers": {"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
            "body": json.dumps({
                "message": {
                    "chat": {"id": -1001234567890},
                    "text": "/status",
                    "message_id": 123,
                }
            }),
        }

        with patch(
            "handlers.telegram_webhook.get_telegram_webhook_secret",
            return_value=VALID_WEBHOOK_SECRET,
        ):
            from handlers.telegram_webhook import handler

            result = handler(event, lambda_context)

        assert result["statusCode"] == 401

    def test_status_command(self, lambda_context, mock_telegram_config):
        """Should return vehicle status for /status command."""
        mock_status = VehicleStatus(
            battery_level=65,
            is_charging=False,
            is_plugged_in=False,
            estimated_range=200,
            last_updated="2024-01-15 10:30:00",
        )

        mock_client = MagicMock()

        with (
            patch("handlers.telegram_webhook.get_vehicle_status", return_value=mock_status),
            patch("handlers.telegram_webhook.get_telegram_client", return_value=mock_client),
            patch(
                "handlers.telegram_webhook.get_telegram_webhook_secret",
                return_value=VALID_WEBHOOK_SECRET,
            ),
        ):
            from handlers.telegram_webhook import handler

            result = handler(self._make_event("/status"), lambda_context)

        assert result["statusCode"] == 200
        mock_client.reply_to_message.assert_called_once()
        call_args = mock_client.reply_to_message.call_args
        assert "65%" in call_args[0][0]  # Battery level in response

    def test_vacation_on_command(self, lambda_context, dynamodb_table, mock_telegram_config):
        """Should enable vacation mode for /vacation on command."""
        mock_client = MagicMock()

        with (
            patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table),
            patch("handlers.telegram_webhook.get_telegram_client", return_value=mock_client),
            patch(
                "handlers.telegram_webhook.get_telegram_webhook_secret",
                return_value=VALID_WEBHOOK_SECRET,
            ),
        ):
            from handlers.telegram_webhook import handler
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            result = handler(self._make_event("/vacation on"), lambda_context)

        assert result["statusCode"] == 200
        mock_client.reply_to_message.assert_called_once()
        call_args = mock_client.reply_to_message.call_args
        assert "enabled" in call_args[0][0].lower()

    def test_vacation_off_command(self, lambda_context, dynamodb_table, mock_telegram_config):
        """Should disable vacation mode for /vacation off command."""
        dynamodb_table.put_item(Item={"pk": "config", "vacation_mode": True})
        mock_client = MagicMock()

        with (
            patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table),
            patch("handlers.telegram_webhook.get_telegram_client", return_value=mock_client),
            patch(
                "handlers.telegram_webhook.get_telegram_webhook_secret",
                return_value=VALID_WEBHOOK_SECRET,
            ),
        ):
            from handlers.telegram_webhook import handler
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            result = handler(self._make_event("/vacation off"), lambda_context)

        assert result["statusCode"] == 200
        call_args = mock_client.reply_to_message.call_args
        assert "disabled" in call_args[0][0].lower()

    def test_threshold_command(self, lambda_context, dynamodb_table, mock_telegram_config):
        """Should set battery threshold for /threshold command."""
        mock_client = MagicMock()

        with (
            patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table),
            patch("handlers.telegram_webhook.get_telegram_client", return_value=mock_client),
            patch(
                "handlers.telegram_webhook.get_telegram_webhook_secret",
                return_value=VALID_WEBHOOK_SECRET,
            ),
        ):
            from handlers.telegram_webhook import handler
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            result = handler(self._make_event("/threshold 50"), lambda_context)

        assert result["statusCode"] == 200
        call_args = mock_client.reply_to_message.call_args
        assert "50%" in call_args[0][0]

    def test_threshold_invalid_value(self, lambda_context, dynamodb_table, mock_telegram_config):
        """Should reject invalid threshold values."""
        mock_client = MagicMock()

        with (
            patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table),
            patch("handlers.telegram_webhook.get_telegram_client", return_value=mock_client),
            patch(
                "handlers.telegram_webhook.get_telegram_webhook_secret",
                return_value=VALID_WEBHOOK_SECRET,
            ),
        ):
            from handlers.telegram_webhook import handler
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            result = handler(self._make_event("/threshold 150"), lambda_context)

        assert result["statusCode"] == 200
        call_args = mock_client.reply_to_message.call_args
        assert "between 0 and 100" in call_args[0][0]

    def test_help_command(self, lambda_context, mock_telegram_config):
        """Should return help text for /help command."""
        mock_client = MagicMock()

        with (
            patch("handlers.telegram_webhook.get_telegram_client", return_value=mock_client),
            patch(
                "handlers.telegram_webhook.get_telegram_webhook_secret",
                return_value=VALID_WEBHOOK_SECRET,
            ),
        ):
            from handlers.telegram_webhook import handler

            result = handler(self._make_event("/help"), lambda_context)

        assert result["statusCode"] == 200
        call_args = mock_client.reply_to_message.call_args
        assert "Available commands" in call_args[0][0]

    def test_config_command(self, lambda_context, dynamodb_table, mock_telegram_config):
        """Should return current config for /config command."""
        dynamodb_table.put_item(
            Item={"pk": "config", "vacation_mode": False, "battery_threshold": 45}
        )
        mock_client = MagicMock()

        with (
            patch("services.config_service.get_dynamodb_table", return_value=dynamodb_table),
            patch("handlers.telegram_webhook.get_telegram_client", return_value=mock_client),
            patch(
                "handlers.telegram_webhook.get_telegram_webhook_secret",
                return_value=VALID_WEBHOOK_SECRET,
            ),
        ):
            from handlers.telegram_webhook import handler
            from services import config_service

            config_service.get_dynamodb_table.cache_clear()

            result = handler(self._make_event("/config"), lambda_context)

        assert result["statusCode"] == 200
        call_args = mock_client.reply_to_message.call_args
        assert "45%" in call_args[0][0]

    def test_ignores_non_command_messages(self, lambda_context):
        """Should ignore messages that aren't commands."""
        with patch(
            "handlers.telegram_webhook.get_telegram_webhook_secret",
            return_value=VALID_WEBHOOK_SECRET,
        ):
            from handlers.telegram_webhook import handler

            result = handler(self._make_event("Hello, bot!"), lambda_context)

        assert result["statusCode"] == 200

    def test_handles_empty_body(self, lambda_context):
        """Should handle empty request body."""
        with patch(
            "handlers.telegram_webhook.get_telegram_webhook_secret",
            return_value=VALID_WEBHOOK_SECRET,
        ):
            from handlers.telegram_webhook import handler

            result = handler(
                {
                    "headers": {
                        "X-Telegram-Bot-Api-Secret-Token": VALID_WEBHOOK_SECRET,
                    },
                    "body": "{}",
                },
                lambda_context,
            )

        assert result["statusCode"] == 200
