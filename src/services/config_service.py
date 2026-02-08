"""Configuration service using DynamoDB."""

import os
from dataclasses import dataclass
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError


@dataclass
class Config:
    """Application configuration."""

    vacation_mode: bool = False
    battery_threshold: int = 45
    reminder_sent_today: bool = False


@lru_cache(maxsize=1)
def get_dynamodb_table():
    """Get cached DynamoDB table resource."""
    dynamodb = boto3.resource("dynamodb")
    table_name = os.environ.get("DYNAMODB_TABLE", "cron-joules-prod")
    return dynamodb.Table(table_name)


def get_config() -> Config:
    """Get current configuration from DynamoDB.

    Returns:
        Config object with current settings
    """
    table = get_dynamodb_table()

    try:
        response = table.get_item(Key={"pk": "config"})
        item = response.get("Item", {})
        return Config(
            vacation_mode=item.get("vacation_mode", False),
            battery_threshold=int(item.get("battery_threshold", 45)),
            reminder_sent_today=item.get("reminder_sent_today", False),
        )
    except ClientError:
        return Config()


def set_vacation_mode(enabled: bool) -> None:
    """Enable or disable vacation mode.

    Args:
        enabled: True to enable vacation mode, False to disable
    """
    table = get_dynamodb_table()
    table.update_item(
        Key={"pk": "config"},
        UpdateExpression="SET vacation_mode = :val",
        ExpressionAttributeValues={":val": enabled},
    )


def set_battery_threshold(threshold: int) -> None:
    """Set battery threshold for reminders.

    Args:
        threshold: Battery percentage threshold (0-100)
    """
    if not 0 <= threshold <= 100:
        raise ValueError("Threshold must be between 0 and 100")

    table = get_dynamodb_table()
    table.update_item(
        Key={"pk": "config"},
        UpdateExpression="SET battery_threshold = :val",
        ExpressionAttributeValues={":val": threshold},
    )


def set_reminder_sent(sent: bool) -> None:
    """Mark whether reminder was sent today.

    Args:
        sent: True if reminder was sent, False to reset
    """
    table = get_dynamodb_table()
    table.update_item(
        Key={"pk": "config"},
        UpdateExpression="SET reminder_sent_today = :val",
        ExpressionAttributeValues={":val": sent},
    )


def reset_daily_reminder() -> None:
    """Reset the daily reminder flag (call at start of each day)."""
    set_reminder_sent(False)
