"""Telegram Bot API client."""

import logging

import requests

from utils.secrets import get_telegram_config

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class TelegramClient:
    """Client for Telegram Bot API."""

    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        config = get_telegram_config()
        self.bot_token = bot_token or config["bot_token"]
        self.chat_id = chat_id or config["chat_id"]

        if not self.bot_token:
            raise ValueError("Telegram bot token not configured")

    @property
    def api_url(self) -> str:
        """Get base API URL for this bot."""
        return f"{TELEGRAM_API_BASE}{self.bot_token}"

    def send_message(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str = "HTML",
    ) -> dict:
        """Send a message to a chat.

        Args:
            text: Message text
            chat_id: Target chat ID (defaults to configured chat)
            parse_mode: Parse mode (HTML or Markdown)

        Returns:
            Telegram API response
        """
        target_chat = chat_id or self.chat_id
        if not target_chat:
            raise ValueError("No chat_id specified")

        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode,
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if not result.get("ok"):
            logger.error(f"Telegram API error: {result}")
            raise RuntimeError(f"Telegram API error: {result.get('description')}")

        return result

    def reply_to_message(
        self,
        text: str,
        chat_id: str,
        message_id: int,
        parse_mode: str = "HTML",
    ) -> dict:
        """Reply to a specific message.

        Args:
            text: Reply text
            chat_id: Chat ID
            message_id: Message ID to reply to
            parse_mode: Parse mode (HTML or Markdown)

        Returns:
            Telegram API response
        """
        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "reply_to_message_id": message_id,
            "parse_mode": parse_mode,
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_updates(self, offset: int | None = None) -> list[dict]:
        """Fetch pending updates via long-polling.

        Args:
            offset: Only return updates with update_id >= offset. Pass
                    (last_update_id + 1) to acknowledge processed updates.

        Returns:
            List of update objects from Telegram
        """
        url = f"{self.api_url}/getUpdates"
        params: dict = {"limit": 100}
        if offset is not None:
            params["offset"] = offset

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        result = response.json()

        if not result.get("ok"):
            raise RuntimeError(f"Telegram API error: {result.get('description')}")

        return result.get("result", [])


# Module-level singleton for warm reuse
_client: TelegramClient | None = None


def get_telegram_client() -> TelegramClient:
    """Get singleton TelegramClient instance."""
    global _client
    if _client is None:
        _client = TelegramClient()
    return _client


def send_message(text: str, chat_id: str | None = None) -> dict:
    """Convenience function to send a message.

    Args:
        text: Message text
        chat_id: Target chat ID (optional)

    Returns:
        Telegram API response
    """
    return get_telegram_client().send_message(text, chat_id=chat_id)


def send_reminder(
    battery_level: int,
    is_followup: bool = False,
    vehicle_name: str | None = None,
) -> dict:
    """Send a charging reminder message.

    Args:
        battery_level: Current battery percentage
        is_followup: Whether this is a follow-up reminder
        vehicle_name: Vehicle display name (defaults to VEHICLE_NAME env var)

    Returns:
        Telegram API response
    """
    if vehicle_name is None:
        from services.vehicle_client import get_vehicle_name

        vehicle_name = get_vehicle_name()

    if is_followup:
        text = (
            f"⚠️ <b>REMINDER:</b> {vehicle_name} still not charging!\n\n"
            f"🔋 Battery: {battery_level}%\n"
            f"Please plug in the charger."
        )
    else:
        text = (
            f"🔋 <b>{vehicle_name} Battery Low</b>\n\n"
            f"Battery: {battery_level}%\n"
            f"Charger not connected.\n\n"
            f"Please plug in to charge."
        )

    return send_message(text)


def get_updates(offset: int | None = None) -> list[dict]:
    """Convenience function to get pending Telegram updates.

    Args:
        offset: Only return updates with update_id >= offset

    Returns:
        List of update objects
    """
    return get_telegram_client().get_updates(offset=offset)
