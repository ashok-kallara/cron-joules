"""Tesla API client wrapper using teslapy."""

import json
import logging

import teslapy

from services.config_service import get_tesla_token, set_tesla_token
from services.vehicle_client import VehicleStatus
from utils.secrets import get_tesla_credentials

logger = logging.getLogger(__name__)


def _make_cache_loader(email: str) -> callable:
    """Return a cache_loader that reads from Redis, falling back to the env-var token."""

    def load() -> dict:
        raw = get_tesla_token()
        if raw:
            logger.debug("Loaded Tesla token from Redis")
            return json.loads(raw)

        # Bootstrap: construct a minimal cache from the env-var refresh token so
        # teslapy can exchange it for a fresh access/refresh token pair.
        creds = get_tesla_credentials()
        bootstrap_token = creds.get("refresh_token", "")
        if not bootstrap_token:
            raise RuntimeError(
                "No Tesla token in Redis and TESLA_REFRESH_TOKEN env var is not set. "
                "Run scripts/tesla_auth.py once to authenticate."
            )

        logger.info("Bootstrapping Tesla token from TESLA_REFRESH_TOKEN env var")
        return {
            email: {
                "refresh_token": bootstrap_token,
                "access_token": "",
                "token_type": "Bearer",
                "expires_in": 0,
                "expiry": "2020-01-01 00:00:00.000000",
            }
        }

    return load


def _make_cache_dumper() -> callable:
    """Return a cache_dumper that persists the updated token to Redis."""

    def dump(cache: dict) -> None:
        set_tesla_token(json.dumps(cache))
        logger.debug("Persisted rotated Tesla token to Redis")

    return dump


class TeslaClient:
    """Client for Tesla Fleet API via teslapy."""

    def get_vehicle_status(self, force_refresh: bool = False) -> VehicleStatus:
        """Get current vehicle status from Tesla.

        Args:
            force_refresh: If True, wake the car for real-time data (takes ~30s)

        Returns:
            VehicleStatus with battery and charging info
        """
        creds = get_tesla_credentials()
        email = creds.get("email", "")
        vin = creds.get("vin", "")

        if not email:
            raise ValueError("TESLA_EMAIL environment variable is not set")

        with teslapy.Tesla(
            email,
            cache_loader=_make_cache_loader(email),
            cache_dumper=_make_cache_dumper(),
        ) as tesla:
            tesla.fetch_token()
            vehicles = tesla.vehicle_list()

            if not vehicles:
                raise ValueError("No vehicles found in Tesla account")

            # Select by VIN if provided, otherwise use the first vehicle
            vehicle = None
            if vin:
                vehicle = next((v for v in vehicles if v["vin"] == vin), None)
                if vehicle is None:
                    raise ValueError(f"No vehicle with VIN {vin} found in Tesla account")
            else:
                vehicle = vehicles[0]

            if force_refresh:
                logger.info("Waking Tesla for real-time data")
                vehicle.sync_wake_up()

            data = vehicle.get_vehicle_data()
            charge = data.get("charge_state", {})
            drive = data.get("drive_state", {})

            battery_level = charge.get("battery_level", 0)
            charging_state = charge.get("charging_state", "Disconnected")
            is_charging = charging_state == "Charging"
            is_plugged_in = charging_state != "Disconnected"
            estimated_range = int(charge.get("battery_range", 0))
            timestamp = drive.get("gps_as_of") or charge.get("timestamp")
            last_updated = str(timestamp) if timestamp else None

            logger.info(f"Tesla status: battery={battery_level}%, charging_state={charging_state}")

            return VehicleStatus(
                battery_level=battery_level,
                is_charging=is_charging,
                is_plugged_in=is_plugged_in,
                estimated_range=estimated_range,
                last_updated=last_updated,
            )


# Module-level singleton
_client: TeslaClient | None = None


def get_tesla_client() -> TeslaClient:
    """Get singleton TeslaClient instance."""
    global _client
    if _client is None:
        _client = TeslaClient()
    return _client
