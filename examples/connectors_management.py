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

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import NotFoundError


def main() -> None:
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)  # "kbnpy-connectors"
    connector_id = f"{prefix}-conn"
    created: list[tuple[str, str]] = []

    try:
        # 1. List connector types, then only those usable by alerting rules
        types = client.connectors.list_types().body
        alerting_types = client.connectors.list_types(feature_id="alerting").body
        print(f"Connector types: {len(types)} total, {len(alerting_types)} alerting")

        # 2. Idempotent start: this connector uses a STABLE id, so clear any
        #    leftover from a previous kept run before creating fresh (own
        #    scope only — this example's own connector id).
        try:
            client.connectors.delete(id=connector_id)
            print(f"Cleared leftover connector {connector_id!r}")
        except NotFoundError:
            pass

        # 3. Create a server-log connector with a caller-specified ID.
        #    config/secrets are optional and default to {}.
        created_connector = client.connectors.create(
            id=connector_id,
            name=f"{prefix} example server log",
            connector_type_id=".server-log",
        ).body
        created.append(("connector", connector_id))
        print(
            f"Created connector: {created_connector['id']} "
            f"({created_connector['connector_type_id']})"
        )

        # 4. Retrieve it, and see it in the full listing
        fetched = client.connectors.get(id=connector_id).body
        print(f"Fetched connector name: {fetched['name']}")
        all_connectors = client.connectors.get_all().body
        print(f"Total connectors in space: {len(all_connectors)}")

        # 5. Update it. PUT is a full replacement: name is required, and
        #    omitted config/secrets are reset to {} on the server.
        updated = client.connectors.update(
            id=connector_id,
            name=f"{prefix} example server log (updated)",
        ).body
        print(f"Updated connector name: {updated['name']}")

        # 6. Run the connector
        result = client.connectors.execute(
            id=connector_id,
            params={"message": "Hello from kibana-py!", "level": "info"},
        ).body
        print(f"Execution status: {result['status']}")

        # 7. OAuth callback script (used by OAuth-based connectors, 9.4.0+)
        script = client.connectors.get_oauth_callback_script()
        print(f"OAuth callback script: {len(script.body)} bytes of JavaScript")
    finally:
        # 8. Clean up
        if should_cleanup():
            try:
                client.connectors.delete(id=connector_id)
                print(f"Deleted connector: {connector_id}")
            except Exception as cleanup_error:
                print(f"Cleanup note: {cleanup_error}")
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
