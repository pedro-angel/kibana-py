#!/usr/bin/env python3
"""
Status API Example

Demonstrates the Kibana Status namespace (read-only, no cleanup needed):
1. Checking overall health and core service statuses (GET /api/status)
2. Fetching the status in the legacy v7 format
3. Reading operational statistics (GET /api/stats)
4. Listing registered Kibana features (GET /api/features, technical preview)

Run this example:
    python examples/status_management.py
"""

from utils import get_kibana_config

from kibana import Kibana


def main() -> None:
    """Walk through the Status API surface."""
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    try:
        # 1. Overall status (default v8 format: status.core + status.plugins)
        status = client.status.get_status().body
        print(f"Kibana {status['version']['number']} ({status['name']})")
        print(f"Overall: {status['status']['overall']['level']}")
        for service, info in status["status"]["core"].items():
            print(f"  core/{service}: {info['level']}")
        degraded = [
            name
            for name, plugin in status["status"]["plugins"].items()
            if plugin["level"] != "available"
        ]
        print(f"Plugins not available: {degraded or 'none'}")

        # 2. Legacy v7 format (status.statuses is a list)
        legacy = client.status.get_status(v7format=True).body
        print(f"\nv7 state: {legacy['status']['overall']['state']}")

        # 3. Operational statistics (9.x field names)
        stats = client.status.get_stats().body
        heap = stats["process"]["memory"]["heap"]
        print(f"\nUptime: {stats['process']['uptime_ms'] / 3600000:.1f} h")
        print(
            f"Heap: {heap['used_bytes'] / 1e6:.0f} MB"
            f" / {heap['total_bytes'] / 1e6:.0f} MB"
        )
        print(f"Avg response time: {stats['response_times']['avg_ms']:.0f} ms")

        # 4. Features registry (technical preview in 9.4)
        features = client.status.get_features().body
        print(f"\nRegistered features: {len(features)}")
        for feature in features[:5]:
            print(f"  {feature['id']}: {feature['name']}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
