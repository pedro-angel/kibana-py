#!/usr/bin/env python3
"""
Example: check upgrade readiness with the Kibana Upgrade Assistant API.

The Upgrade Assistant reports whether the cluster is ready for a major
version upgrade and which deprecation issues remain. The API is in
Technical Preview in Kibana 9.4.
"""

from utils import get_kibana_config

from kibana import Kibana


def main():
    """Check the cluster's upgrade readiness status."""
    kibana_url, basic_auth, api_key = get_kibana_config()

    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    try:
        response = client.upgrade_assistant.status()
        status = response.body

        print("Upgrade Assistant status")
        print(f"  Ready for upgrade: {status['readyForUpgrade']}")
        if status.get("details"):
            print(f"  Details: {status['details']}")

        es_logs = status.get("recentEsDeprecationLogs", {})
        print(f"  Recent ES deprecation logs: {es_logs.get('count', 0)}")

        kibana_deprecations = status.get("kibanaApiDeprecations", [])
        print(f"  Kibana API deprecations: {len(kibana_deprecations)}")
        for deprecation in kibana_deprecations[:5]:
            print(f"    - [{deprecation.get('level')}] {deprecation.get('title')}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
