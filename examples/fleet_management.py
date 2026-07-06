#!/usr/bin/env python3
"""
Fleet Core Management Example

This example shows the minimal code needed to:
1. Initialize Fleet (idempotent setup)
2. Check the current user's Fleet permissions
3. Read the global Fleet settings
4. Update a global Fleet setting and restore it
5. Read the Fleet settings for the current space
6. Check the health of a Fleet Server host (semantic 404 on a dev stack)

Run this example:
    python examples/fleet_management.py
"""

from utils import get_kibana_config

from kibana import Kibana
from kibana.exceptions import NotFoundError


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    try:
        # 1. Initialize Fleet (safe to call multiple times)
        setup = client.fleet.setup()
        print(f"Fleet initialized: {setup.body['isInitialized']}")

        # 2. Check the current user's Fleet permissions
        perms = client.fleet.check_permissions()
        print(f"Fleet permissions OK: {perms.body['success']}")

        # 3. Read the global Fleet settings
        settings = client.fleet.get_settings()
        prerelease = settings.body["item"]["prerelease_integrations_enabled"]
        print(f"Pre-release integrations enabled: {prerelease}")

        # 4. Update a global Fleet setting, then restore the original value
        client.fleet.update_settings(prerelease_integrations_enabled=not prerelease)
        print(f"Toggled pre-release integrations to {not prerelease}")
        client.fleet.update_settings(prerelease_integrations_enabled=prerelease)
        print(f"Restored pre-release integrations to {prerelease}")

        # 5. Read the Fleet settings for the current space
        space_settings = client.fleet.get_space_settings()
        prefixes = space_settings.body["item"]["allowed_namespace_prefixes"]
        print(f"Allowed namespace prefixes in this space: {prefixes}")

        # 6. Check Fleet Server health (no hosts on a dev stack -> 404)
        try:
            health = client.fleet.health_check(id="kbnpy-fleet-example-host")
            print(f"Fleet Server status: {health.body['status']}")
        except NotFoundError as e:
            print(f"No such Fleet Server host (expected on a dev stack): {e.message}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
