#!/usr/bin/env python3
"""
Connectors Management Example

Demonstrates the ConnectorsClient (Kibana 9.4 Connectors API):

1. Listing connector types (optionally filtered by feature)
2. Creating connectors, including with a caller-specified ID
3. Retrieving and listing connectors
4. Updating a connector (full-replace PUT semantics)
5. Running (executing) a connector
6. Fetching the OAuth callback script (added in 9.4.0)
7. Deleting connectors

Note: ``client.actions`` is a deprecated alias of ``client.connectors``.

Run this example:
    python examples/connectors_management.py
"""

import uuid

from utils import get_kibana_config

from kibana import Kibana


def main() -> None:
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    connector_id = f"kbnpy-connectors-ex-{uuid.uuid4().hex[:8]}"

    try:
        # 1. List connector types, then only those usable by alerting rules
        types = client.connectors.list_types().body
        alerting_types = client.connectors.list_types(feature_id="alerting").body
        print(f"Connector types: {len(types)} total, {len(alerting_types)} alerting")

        # 2. Create a server-log connector with a caller-specified ID.
        #    config/secrets are optional and default to {}.
        created = client.connectors.create(
            id=connector_id,
            name="kbnpy example server log",
            connector_type_id=".server-log",
        ).body
        print(f"Created connector: {created['id']} ({created['connector_type_id']})")

        # 3. Retrieve it, and see it in the full listing
        fetched = client.connectors.get(id=connector_id).body
        print(f"Fetched connector name: {fetched['name']}")
        all_connectors = client.connectors.get_all().body
        print(f"Total connectors in space: {len(all_connectors)}")

        # 4. Update it. PUT is a full replacement: name is required, and
        #    omitted config/secrets are reset to {} on the server.
        updated = client.connectors.update(
            id=connector_id,
            name="kbnpy example server log (updated)",
        ).body
        print(f"Updated connector name: {updated['name']}")

        # 5. Run the connector
        result = client.connectors.execute(
            id=connector_id,
            params={"message": "Hello from kibana-py!", "level": "info"},
        ).body
        print(f"Execution status: {result['status']}")

        # 6. OAuth callback script (used by OAuth-based connectors, 9.4.0+)
        script = client.connectors.get_oauth_callback_script()
        print(f"OAuth callback script: {len(script.body)} bytes of JavaScript")
    finally:
        # 7. Clean up
        try:
            client.connectors.delete(id=connector_id)
            print(f"Deleted connector: {connector_id}")
        except Exception as cleanup_error:
            print(f"Cleanup note: {cleanup_error}")
        client.close()


if __name__ == "__main__":
    main()
