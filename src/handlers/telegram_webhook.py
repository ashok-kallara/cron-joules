"""Telegram bot command processing."""

import logging
import re

from services.config_service import get_config, set_battery_threshold, set_vacation_mode
from services.vehicle_client import get_vehicle_name, get_vehicle_status

logger = logging.getLogger(__name__)

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

        vehicle_name = get_vehicle_name()
        return (
            f"🚗 <b>{vehicle_name} Status</b>\n\n"
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
