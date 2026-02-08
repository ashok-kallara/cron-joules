"""AWS SSM Parameter Store secrets management."""

import os
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError


@lru_cache(maxsize=1)
def get_ssm_client():
    """Get cached SSM client."""
    return boto3.client("ssm")


def get_parameter(name: str, with_decryption: bool = True) -> str | None:
    """Get a parameter from SSM Parameter Store.

    Args:
        name: Parameter name (will be prefixed with /cron-joules/)
        with_decryption: Whether to decrypt SecureString parameters

    Returns:
        Parameter value or None if not found
    """
    ssm = get_ssm_client()
    full_name = f"/cron-joules/{name}"

    try:
        response = ssm.get_parameter(Name=full_name, WithDecryption=with_decryption)
        return response["Parameter"]["Value"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ParameterNotFound":
            return None
        raise


def get_kia_credentials() -> dict:
    """Get Kia Connect credentials from SSM or environment."""
    return {
        "username": os.environ.get("KIA_USERNAME") or get_parameter("kia/username"),
        "password": os.environ.get("KIA_PASSWORD") or get_parameter("kia/password"),
        "pin": os.environ.get("KIA_PIN") or get_parameter("kia/pin"),
    }


def get_telegram_config() -> dict:
    """Get Telegram bot configuration from SSM or environment."""
    return {
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN") or get_parameter("telegram/bot_token"),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID") or get_parameter("telegram/chat_id"),
    }


def get_telegram_webhook_secret() -> str | None:
    """Get Telegram webhook secret token from SSM or environment.

    This secret is used to verify that incoming webhook requests
    actually come from Telegram (X-Telegram-Bot-Api-Secret-Token header).
    """
    return os.environ.get("TELEGRAM_WEBHOOK_SECRET") or get_parameter("telegram/webhook_secret")


def get_assistant_webhook_secret() -> str | None:
    """Get Assistant/IFTTT webhook secret from SSM or environment.

    This secret must be sent as the X-Webhook-Secret header
    by IFTTT to authenticate requests to the assistant endpoint.
    """
    return os.environ.get("ASSISTANT_WEBHOOK_SECRET") or get_parameter("assistant/webhook_secret")
