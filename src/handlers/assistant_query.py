"""Google Assistant / IFTTT webhook Lambda handler."""

import json
import logging
import os

from services.kia_client import get_vehicle_status
from utils.secrets import get_assistant_webhook_secret

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)


def handler(event: dict, context) -> dict:
    """Lambda handler for Google Assistant queries via IFTTT.

    IFTTT sends a webhook when you say "Hey Google, does my car need charging?"
    This handler checks the battery status and returns a response for IFTTT
    to announce via Google Home.

    Args:
        event: API Gateway event from IFTTT webhook
        context: Lambda context

    Returns:
        API Gateway response with spoken text for Google Assistant
    """
    logger.info(f"Assistant query received: {event}")

    try:
        # Verify webhook secret
        expected_secret = get_assistant_webhook_secret()
        if expected_secret:
            headers = event.get("headers") or {}
            # API Gateway may lowercase header names
            incoming_secret = headers.get("X-Webhook-Secret") or headers.get(
                "x-webhook-secret"
            )
            if incoming_secret != expected_secret:
                logger.warning("Assistant query request failed secret validation")
                return _response(401, {"error": "Unauthorized"})

        # Parse request body if present
        body = {}
        if event.get("body"):
            body = json.loads(event["body"])

        # Get vehicle status
        status = get_vehicle_status()
        logger.info(
            f"Vehicle status: battery={status.battery_level}%, "
            f"charging={status.is_charging}"
        )

        # Generate response text for Google Assistant to speak
        if status.is_charging:
            response_text = (
                f"Your EV6 is currently charging. "
                f"Battery is at {status.battery_level} percent."
            )
        elif status.is_plugged_in:
            response_text = (
                f"Your EV6 is plugged in but not charging. "
                f"Battery is at {status.battery_level} percent."
            )
        elif status.battery_level < 45:
            response_text = (
                f"Yes, your EV6 needs charging. "
                f"Battery is at {status.battery_level} percent and the charger is not connected."
            )
        else:
            response_text = (
                f"Your EV6 is at {status.battery_level} percent. "
                f"No charging needed yet."
            )

        return _response(200, {
            "status": "ok",
            "speech": response_text,
            "battery_level": status.battery_level,
            "is_charging": status.is_charging,
            "is_plugged_in": status.is_plugged_in,
        })

    except Exception as e:
        logger.exception(f"Error processing query: {e}")
        return _response(500, {
            "status": "error",
            "speech": "Sorry, I couldn't check your car's battery status right now.",
            "error": str(e),
        })


def _response(status_code: int, body: dict) -> dict:
    """Create API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
