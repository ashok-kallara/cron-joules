"""Telegram webhook Lambda handler."""

import json
import logging
import os
import re

from services.config_service import get_config, set_battery_threshold, set_vacation_mode
from services.kia_client import get_vehicle_status
from services.telegram_client import get_telegram_client
from utils.secrets import get_telegram_webhook_secret

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

# Command help text
HELP_TEXT = """
<b>Cron Joules Bot</b>

Available commands:
• /status - Check current battery level
• /vacation on - Disable reminders
• /vacation off - Enable reminders
• /threshold &lt;number&gt; - Set battery threshold (e.g., /threshold 50)
• /config - Show current settings
• /help - Show this message
"""


def handler(event: dict, context) -> dict:
    """Lambda handler for Telegram webhook.

    Args:
        event: API Gateway event with Telegram update
        context: Lambda context

    Returns:
        API Gateway response
    """
    logger.info(f"Telegram webhook received: {event}")

    try:
        # Verify Telegram secret token
        expected_secret = get_telegram_webhook_secret()
        if expected_secret:
            headers = event.get("headers") or {}
            # API Gateway lowercases header names
            incoming_secret = headers.get("X-Telegram-Bot-Api-Secret-Token") or headers.get(
                "x-telegram-bot-api-secret-token"
            )
            if incoming_secret != expected_secret:
                logger.warning("Telegram webhook request failed secret validation")
                return _response(401, {"error": "Unauthorized"})

        # Parse Telegram update
        body = json.loads(event.get("body", "{}"))
        message = body.get("message", {})

        if not message:
            logger.info("No message in update, skipping")
            return _response(200, {"ok": True})

        chat_id = str(message.get("chat", {}).get("id"))
        text = message.get("text", "").strip()
        message_id = message.get("message_id")

        if not text or not text.startswith("/"):
            logger.info("Not a command, skipping")
            return _response(200, {"ok": True})

        # Process command
        response_text = process_command(text)

        # Send response
        client = get_telegram_client()
        client.reply_to_message(response_text, chat_id, message_id)

        return _response(200, {"ok": True})

    except Exception as e:
        logger.exception(f"Error processing webhook: {e}")
        return _response(200, {"ok": True})  # Always return 200 to Telegram


def process_command(text: str) -> str:
    """Process a bot command and return response text.

    Args:
        text: Command text (e.g., "/status")

    Returns:
        Response message
    """
    command = text.lower().split()[0]

    if command == "/status":
        return handle_status()
    elif command == "/vacation":
        args = text.split()[1:] if len(text.split()) > 1 else []
        return handle_vacation(args)
    elif command == "/threshold":
        args = text.split()[1:] if len(text.split()) > 1 else []
        return handle_threshold(args)
    elif command == "/config":
        return handle_config()
    elif command in ("/help", "/start"):
        return HELP_TEXT
    else:
        return f"Unknown command: {command}\n\nUse /help for available commands."


def handle_status() -> str:
    """Handle /status command."""
    try:
        status = get_vehicle_status()

        charging_status = "🔌 Charging" if status.is_charging else "⚡ Not charging"
        plugged_status = "Connected" if status.is_plugged_in else "Not connected"

        return (
            f"🚗 <b>EV6 Status</b>\n\n"
            f"🔋 Battery: {status.battery_level}%\n"
            f"📍 Range: ~{status.estimated_range} mi\n"
            f"{charging_status}\n"
            f"🔌 Charger: {plugged_status}\n"
            f"\n<i>Last updated: {status.last_updated or 'Unknown'}</i>"
        )
    except Exception as e:
        logger.exception(f"Error getting status: {e}")
        return f"❌ Error getting vehicle status: {e}"


def handle_vacation(args: list[str]) -> str:
    """Handle /vacation command."""
    if not args:
        config = get_config()
        status = "enabled 🏖️" if config.vacation_mode else "disabled"
        return (
            f"Vacation mode is currently <b>{status}</b>\n\n"
            f"Use /vacation on or /vacation off to change."
        )

    action = args[0].lower()
    if action == "on":
        set_vacation_mode(True)
        return "🏖️ <b>Vacation mode enabled</b>\n\nReminders are now disabled."
    elif action == "off":
        set_vacation_mode(False)
        return "✅ <b>Vacation mode disabled</b>\n\nReminders are now active."
    else:
        return "Invalid option. Use /vacation on or /vacation off"


def handle_threshold(args: list[str]) -> str:
    """Handle /threshold command."""
    if not args:
        config = get_config()
        return (
            f"Current battery threshold: <b>{config.battery_threshold}%</b>\n\n"
            f"Use /threshold &lt;number&gt; to change (e.g., /threshold 50)"
        )

    try:
        threshold = int(args[0])
        if not 0 <= threshold <= 100:
            return "❌ Threshold must be between 0 and 100"

        set_battery_threshold(threshold)
        return f"✅ Battery threshold set to <b>{threshold}%</b>"
    except ValueError:
        return "❌ Invalid number. Use /threshold &lt;number&gt; (e.g., /threshold 50)"


def handle_config() -> str:
    """Handle /config command."""
    config = get_config()
    vacation_status = "Enabled 🏖️" if config.vacation_mode else "Disabled"

    return (
        f"⚙️ <b>Current Settings</b>\n\n"
        f"🔋 Battery threshold: {config.battery_threshold}%\n"
        f"🏖️ Vacation mode: {vacation_status}\n"
        f"📬 Reminder sent today: {'Yes' if config.reminder_sent_today else 'No'}"
    )


def _response(status_code: int, body: dict) -> dict:
    """Create API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
