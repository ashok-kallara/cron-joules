"""Scheduled battery check Lambda handler."""

import logging
import os
from datetime import datetime

from services.config_service import get_config, set_reminder_sent
from services.kia_client import get_vehicle_status
from services.telegram_client import send_reminder

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)


def handler(event: dict, context) -> dict:
    """Lambda handler for scheduled battery checks.

    Triggered at 7PM and 10PM daily by EventBridge.

    Args:
        event: EventBridge scheduled event
        context: Lambda context

    Returns:
        Response dict with status and battery info
    """
    logger.info(f"Battery check triggered: {event}")

    # Get configuration
    config = get_config()

    # Skip if vacation mode is enabled
    if config.vacation_mode:
        logger.info("Vacation mode enabled, skipping check")
        return {
            "status": "skipped",
            "reason": "vacation_mode",
        }

    # Get current hour to determine if this is 7PM or 10PM check
    current_hour = datetime.now().hour
    is_followup = current_hour >= 22  # 10PM or later is follow-up

    # If this is a follow-up and we haven't sent a reminder today, skip
    if is_followup and not config.reminder_sent_today:
        logger.info("No initial reminder sent today, skipping follow-up")
        return {
            "status": "skipped",
            "reason": "no_initial_reminder",
        }

    try:
        # Get vehicle status
        status = get_vehicle_status()
        logger.info(
            f"Vehicle status: battery={status.battery_level}%, "
            f"charging={status.is_charging}, plugged_in={status.is_plugged_in}"
        )

        # Check if reminder is needed
        needs_reminder = (
            status.battery_level < config.battery_threshold
            and not status.is_charging
            and not status.is_plugged_in
        )

        if needs_reminder:
            logger.info(f"Sending {'follow-up ' if is_followup else ''}reminder")
            send_reminder(status.battery_level, is_followup=is_followup)

            # Mark reminder as sent (for 7PM check)
            if not is_followup:
                set_reminder_sent(True)

            return {
                "status": "reminder_sent",
                "battery_level": status.battery_level,
                "is_followup": is_followup,
            }
        else:
            logger.info("No reminder needed")

            # Reset reminder flag at 7PM if battery is OK
            if not is_followup:
                set_reminder_sent(False)

            return {
                "status": "ok",
                "battery_level": status.battery_level,
                "is_charging": status.is_charging,
                "is_plugged_in": status.is_plugged_in,
            }

    except Exception as e:
        logger.exception(f"Error checking battery: {e}")
        return {
            "status": "error",
            "error": str(e),
        }
