"""Configuration service using Upstash Redis."""

import logging
import os
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

CONFIG_KEY = "config"
TELEGRAM_OFFSET_KEY = "telegram_offset"
TESLA_TOKEN_KEY = "tesla_token"


@dataclass
class Config:
    """Application configuration."""

    vacation_mode: bool = False
    battery_threshold: int = 45
    reminder_sent_today: bool = False


def _redis(command: str, *args) -> object:
    """Execute a Redis command via Upstash REST API."""
    url = os.environ.get("UPSTASH_REDIS_REST_URL", "")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

    if not url or not token:
        raise RuntimeError("UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN must be set")

    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json=[command, *args],
        timeout=5,
    )
    response.raise_for_status()
    return response.json().get("result")


def get_config() -> Config:
    """Get current configuration from Redis.

    Returns:
        Config object with current settings, or defaults if Redis is unreachable
    """
    try:
        values = _redis(
            "HMGET", CONFIG_KEY, "vacation_mode", "battery_threshold", "reminder_sent_today"
        )
        vacation_mode, battery_threshold, reminder_sent_today = values
        return Config(
            vacation_mode=vacation_mode == "true" if vacation_mode is not None else False,
            battery_threshold=int(battery_threshold) if battery_threshold is not None else 45,
            reminder_sent_today=reminder_sent_today == "true"
            if reminder_sent_today is not None
            else False,
        )
    except Exception as e:
        logger.warning(f"Failed to get config from Redis, using defaults: {e}")
        return Config()


def set_vacation_mode(enabled: bool) -> None:
    """Enable or disable vacation mode.

    Args:
        enabled: True to enable vacation mode, False to disable
    """
    _redis("HSET", CONFIG_KEY, "vacation_mode", "true" if enabled else "false")


def set_battery_threshold(threshold: int) -> None:
    """Set battery threshold for reminders.

    Args:
        threshold: Battery percentage threshold (0-100)
    """
    if not 0 <= threshold <= 100:
        raise ValueError("Threshold must be between 0 and 100")
    _redis("HSET", CONFIG_KEY, "battery_threshold", str(threshold))


def set_reminder_sent(sent: bool) -> None:
    """Mark whether reminder was sent today.

    Args:
        sent: True if reminder was sent, False to reset
    """
    _redis("HSET", CONFIG_KEY, "reminder_sent_today", "true" if sent else "false")


def reset_daily_reminder() -> None:
    """Reset the daily reminder flag (call at start of each day)."""
    set_reminder_sent(False)


def get_telegram_poll_offset() -> int | None:
    """Get the last processed Telegram update_id.

    Returns:
        Last update_id, or None if no updates have been processed yet
    """
    try:
        result = _redis("GET", TELEGRAM_OFFSET_KEY)
        return int(result) if result is not None else None
    except Exception as e:
        logger.warning(f"Failed to get telegram offset: {e}")
        return None


def set_telegram_poll_offset(offset: int) -> None:
    """Store the last processed Telegram update_id.

    Args:
        offset: The update_id of the last successfully processed update
    """
    _redis("SET", TELEGRAM_OFFSET_KEY, str(offset))


def get_tesla_token() -> str | None:
    """Get the stored Tesla OAuth token JSON from Redis.

    Returns:
        Token JSON string, or None if not yet stored
    """
    try:
        return _redis("GET", TESLA_TOKEN_KEY)
    except Exception as e:
        logger.warning(f"Failed to get Tesla token from Redis: {e}")
        return None


def set_tesla_token(token_json: str) -> None:
    """Persist the Tesla OAuth token JSON to Redis.

    Args:
        token_json: Full token cache JSON string from teslapy
    """
    _redis("SET", TESLA_TOKEN_KEY, token_json)
