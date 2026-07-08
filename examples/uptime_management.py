#!/usr/bin/env python3
"""
Uptime settings example.

Shows how to read the Kibana Uptime app settings, apply a partial update
(certificate alerting thresholds), and restore the original values.

Run this example:
    python examples/uptime_management.py
"""

from utils import get_kibana_config

from kibana import Kibana


def main() -> None:
    """Read, update, and restore the Kibana uptime settings."""
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    try:
        # Read the current uptime settings
        settings = client.uptime.get_settings().body
        print("Current uptime settings:")
        print(f"  heartbeatIndices: {settings['heartbeatIndices']}")
        print(f"  certExpirationThreshold: {settings['certExpirationThreshold']} days")
        print(f"  certAgeThreshold: {settings['certAgeThreshold']} days")
        print(f"  defaultConnectors: {settings['defaultConnectors']}")
        print(f"  defaultEmail: {settings['defaultEmail']}")

        # Partially update the certificate alerting thresholds. Provided keys
        # are merged with the existing settings; everything else is preserved.
        try:
            updated = client.uptime.update_settings(
                cert_expiration_threshold=14,
                cert_age_threshold=365,
            ).body
            print("\nAfter partial update:")
            print(f"  certExpirationThreshold: {updated['certExpirationThreshold']}")
            print(f"  certAgeThreshold: {updated['certAgeThreshold']}")
            print(f"  heartbeatIndices (unchanged): {updated['heartbeatIndices']}")
        finally:
            # Restore the original settings
            client.uptime.update_settings(
                heartbeat_indices=settings["heartbeatIndices"],
                cert_expiration_threshold=settings["certExpirationThreshold"],
                cert_age_threshold=settings["certAgeThreshold"],
                default_connectors=settings["defaultConnectors"],
                default_email=settings["defaultEmail"],
            )
            print("\nOriginal settings restored.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
