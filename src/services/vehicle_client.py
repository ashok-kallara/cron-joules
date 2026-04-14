"""Vehicle provider abstraction layer."""

import logging
import os
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass
class VehicleStatus:
    """Simplified vehicle status."""

    battery_level: int
    is_charging: bool
    is_plugged_in: bool
    estimated_range: int
    last_updated: str | None = None

    @property
    def needs_charging(self) -> bool:
        """Check if vehicle needs charging based on status."""
        return not self.is_charging and not self.is_plugged_in


class VehicleClient(Protocol):
    """Protocol that all vehicle clients must implement."""

    def get_vehicle_status(self, force_refresh: bool = False) -> VehicleStatus: ...


def get_vehicle_provider() -> str:
    """Get the configured vehicle provider (kia or tesla)."""
    return os.environ.get("VEHICLE_PROVIDER", "kia").lower()


def get_vehicle_name() -> str:
    """Get the configured vehicle display name."""
    provider = get_vehicle_provider()
    default = "Tesla" if provider == "tesla" else "EV6"
    return os.environ.get("VEHICLE_NAME", default)


def get_vehicle_status(force_refresh: bool = False) -> VehicleStatus:
    """Get vehicle status from the configured provider.

    Uses lazy imports so neither teslapy nor hyundai_kia_connect_api is imported
    unless actually needed.

    Args:
        force_refresh: If True, wake the car for real-time data (uses API quota)

    Returns:
        VehicleStatus with battery and charging info
    """
    provider = get_vehicle_provider()

    if provider == "tesla":
        from services.tesla_client import get_tesla_client

        return get_tesla_client().get_vehicle_status(force_refresh=force_refresh)
    else:
        from services.kia_client import get_kia_client

        return get_kia_client().get_vehicle_status(force_refresh=force_refresh)
