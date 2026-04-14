"""Secrets management via environment variables."""

import os


def get_kia_credentials() -> dict:
    """Get Kia Connect credentials from environment variables."""
    return {
        "username": os.environ.get("KIA_USERNAME"),
        "password": os.environ.get("KIA_PASSWORD"),
        "pin": os.environ.get("KIA_PIN"),
    }


def get_telegram_config() -> dict:
    """Get Telegram bot configuration from environment variables."""
    return {
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN"),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID"),
    }


def get_telegram_webhook_secret() -> str | None:
    """Get Telegram webhook secret token from environment variables."""
    return os.environ.get("TELEGRAM_WEBHOOK_SECRET")


def get_assistant_webhook_secret() -> str | None:
    """Get Assistant/IFTTT webhook secret from environment variables."""
    return os.environ.get("ASSISTANT_WEBHOOK_SECRET")


def get_tesla_credentials() -> dict:
    """Get Tesla credentials from environment variables."""
    return {
        "email": os.environ.get("TESLA_EMAIL"),
        "vin": os.environ.get("TESLA_VIN"),
        "refresh_token": os.environ.get("TESLA_REFRESH_TOKEN"),
    }
