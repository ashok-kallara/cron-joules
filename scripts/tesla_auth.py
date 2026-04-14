#!/usr/bin/env python3
"""One-time Tesla OAuth authentication helper.

Run this locally ONCE to get your Tesla refresh token, then store the printed
token as a GitHub Actions Secret named TESLA_REFRESH_TOKEN.

Usage:
    uv run --env-file .env python scripts/tesla_auth.py

Requirements:
    - TESLA_EMAIL must be set in your .env file (or environment)
    - A web browser must be available to complete the OAuth flow
    - teslapy must be installed (included in project dependencies)

After running:
    1. A browser window opens for Tesla SSO login
    2. Complete login + MFA if enabled
    3. This script prints the refresh_token to stdout
    4. Copy it to GitHub → Settings → Secrets → New secret: TESLA_REFRESH_TOKEN
    5. Also set TESLA_EMAIL and (optionally) TESLA_VIN as secrets
"""

import json
import os
import sys

# Ensure src/ is on the path so we can reuse secrets.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def main() -> None:
    try:
        import teslapy
    except ImportError:
        print("ERROR: teslapy not installed. Run: uv sync")
        sys.exit(1)

    email = os.environ.get("TESLA_EMAIL")
    if not email:
        print("ERROR: TESLA_EMAIL environment variable is not set.")
        print("Add it to your .env file and rerun.")
        sys.exit(1)

    print(f"Authenticating Tesla account: {email}")
    print("A browser window will open for Tesla SSO login...")
    print()

    # Use a temp file so the token is captured after auth
    cache_file = "/tmp/tesla_auth_cache.json"

    with teslapy.Tesla(email, cache_file=cache_file) as tesla:
        if not tesla.authorized:
            tesla.fetch_token()

        cache_data = {}
        if os.path.exists(cache_file):
            with open(cache_file) as f:
                cache_data = json.load(f)

        token_data = cache_data.get(email, {})
        refresh_token = token_data.get("refresh_token")

        if not refresh_token:
            print("ERROR: Authentication succeeded but no refresh_token found in cache.")
            print("Full cache data:", json.dumps(cache_data, indent=2))
            sys.exit(1)

    # Clean up temp cache
    if os.path.exists(cache_file):
        os.remove(cache_file)

    print("=" * 60)
    print("Authentication successful!")
    print()
    print("Add these secrets to your GitHub repository:")
    print(f"  TESLA_EMAIL        = {email}")
    print(f"  TESLA_REFRESH_TOKEN = {refresh_token}")
    print()
    print("Optional (to target a specific vehicle if you have multiple):")

    # List vehicles and print VINs
    with teslapy.Tesla(email, cache_file=cache_file) as tesla:
        tesla.fetch_token()
        vehicles = tesla.vehicle_list()
        if vehicles:
            print("  Available vehicles:")
            for v in vehicles:
                print(f"    VIN: {v['vin']}  —  {v.get('display_name', 'Unknown')}")
            print()
            print("  TESLA_VIN = <paste VIN above, or leave unset to use first vehicle>")

    # Final cleanup
    if os.path.exists(cache_file):
        os.remove(cache_file)


if __name__ == "__main__":
    main()
