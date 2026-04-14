"""Google Assistant / IFTTT query handler."""

import logging

from services.vehicle_client import get_vehicle_name, get_vehicle_status

logger = logging.getLogger(__name__)


def run_assistant_query() -> dict:
    """Check battery status and return a spoken response for Google Assistant.

    Called via IFTTT when you say "Hey Google, does my car need charging?"

    Returns:
        Dict with speech text and battery details
    """
    status = get_vehicle_status()
    vehicle_name = get_vehicle_name()
    logger.info(f"Vehicle status: battery={status.battery_level}%, charging={status.is_charging}")

    if status.is_charging:
        speech = (
            f"Your {vehicle_name} is currently charging. "
            f"Battery is at {status.battery_level} percent."
        )
    elif status.is_plugged_in:
        speech = (
            f"Your {vehicle_name} is plugged in but not charging. "
            f"Battery is at {status.battery_level} percent."
        )
    elif status.battery_level < 45:
        speech = (
            f"Yes, your {vehicle_name} needs charging. "
            f"Battery is at {status.battery_level} percent and the charger is not connected."
        )
    else:
        speech = (
            f"Your {vehicle_name} is at {status.battery_level} percent. No charging needed yet."
        )

    return {
        "status": "ok",
        "speech": speech,
        "battery_level": status.battery_level,
        "is_charging": status.is_charging,
        "is_plugged_in": status.is_plugged_in,
    }
