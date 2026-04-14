"""Kia Connect API client wrapper."""

import logging

from hyundai_kia_connect_api import Vehicle, VehicleManager
from hyundai_kia_connect_api.const import BRANDS, REGIONS

from services.vehicle_client import VehicleStatus
from utils.secrets import get_kia_credentials

logger = logging.getLogger(__name__)

# Kia USA configuration
REGION = REGIONS[3]  # USA
BRAND = BRANDS[1]  # Kia


class KiaClient:
    """Client for interacting with Kia Connect API."""

    def __init__(self):
        self._manager: VehicleManager | None = None
        self._vehicle: Vehicle | None = None

    def _get_manager(self) -> VehicleManager:
        """Get or create VehicleManager instance."""
        if self._manager is None:
            creds = get_kia_credentials()

            if not all([creds["username"], creds["password"], creds["pin"]]):
                raise ValueError("Missing Kia Connect credentials")

            self._manager = VehicleManager(
                region=3,  # USA
                brand=1,  # Kia
                username=creds["username"],
                password=creds["password"],
                pin=creds["pin"],
            )

        return self._manager

    def _get_vehicle(self) -> Vehicle:
        """Get the first vehicle from the account."""
        if self._vehicle is None:
            manager = self._get_manager()
            manager.check_and_refresh_token()
            manager.update_all_vehicles_with_cached_state()

            if not manager.vehicles:
                raise ValueError("No vehicles found in Kia Connect account")

            # Get the first vehicle (EV6)
            vehicle_id = list(manager.vehicles.keys())[0]
            self._vehicle = manager.vehicles[vehicle_id]

        return self._vehicle

    def get_vehicle_status(self, force_refresh: bool = False) -> VehicleStatus:
        """Get current vehicle status.

        Args:
            force_refresh: If True, force refresh from vehicle (slower, uses API quota)

        Returns:
            VehicleStatus with battery and charging info
        """
        manager = self._get_manager()
        manager.check_and_refresh_token()

        if force_refresh:
            # Force refresh from vehicle (takes ~30s, uses API quota)
            logger.info("Force refreshing vehicle status from car")
            manager.force_refresh_all_vehicles_states()
        else:
            # Use cached data from Kia servers
            manager.update_all_vehicles_with_cached_state()

        vehicle = self._get_vehicle()

        return VehicleStatus(
            battery_level=vehicle.ev_battery_percentage or 0,
            is_charging=vehicle.ev_battery_is_charging or False,
            is_plugged_in=vehicle.ev_battery_is_plugged_in or False,
            estimated_range=vehicle.ev_driving_range or 0,
            last_updated=str(vehicle.last_updated_at) if vehicle.last_updated_at else None,
        )


# Module-level singleton for warm reuse
_client: KiaClient | None = None


def get_kia_client() -> KiaClient:
    """Get singleton KiaClient instance."""
    global _client
    if _client is None:
        _client = KiaClient()
    return _client
