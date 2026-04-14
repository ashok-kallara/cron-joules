"""Battery check logic."""

import logging

from services.config_service import get_config, set_reminder_sent
from services.vehicle_client import get_vehicle_status
from services.telegram_client import send_reminder

logger = logging.getLogger(__name__)


def run_battery_check(is_followup: bool = False) -> dict:
    """Run a battery check and send a reminder if needed.

    Args:
        is_followup: True if this is the 10PM follow-up check, False for 7PM

    Returns:
        Result dict with status and details
    """
    config = get_config()

    if config.vacation_mode:
        logger.info("Vacation mode enabled, skipping check")
        return {"status": "skipped", "reason": "vacation_mode"}

    if is_followup and not config.reminder_sent_today:
        logger.info("No initial reminder sent today, skipping follow-up")
        return {"status": "skipped", "reason": "no_initial_reminder"}

    try:
        status = get_vehicle_status()
        logger.info(
            f"Vehicle status: battery={status.battery_level}%, "
            f"charging={status.is_charging}, plugged_in={status.is_plugged_in}"
        )

        needs_reminder = (
            status.battery_level < config.battery_threshold
            and not status.is_charging
            and not status.is_plugged_in
        )

        if needs_reminder:
            logger.info(f"Sending {'follow-up ' if is_followup else ''}reminder")
            send_reminder(status.battery_level, is_followup=is_followup)

            if not is_followup:
                set_reminder_sent(True)

            return {
                "status": "reminder_sent",
                "battery_level": status.battery_level,
                "is_followup": is_followup,
            }
        else:
            logger.info("No reminder needed")

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
        return {"status": "error", "error": str(e)}
