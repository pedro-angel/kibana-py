#!/usr/bin/env python3
"""
Synthetics management example.

Shows the full Synthetics workflow: create a global parameter, a private
location (backed by a throwaway Fleet agent policy), and an HTTP monitor
that runs from it; trigger an on-demand test run; then clean everything up.

No Elastic Agent needs to be enrolled: the monitor is fully manageable via
the API, it just never executes until an agent joins the policy.

Run this example:
    python examples/synthetics_management.py
"""

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import NotFoundError

PREFIX = resource_prefix(__file__)  # "kbnpy-synthetics"


def main() -> None:
    """Create, inspect, and delete synthetics resources."""
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    policy_id = monitor_id = location_id = param_id = None
    created: list[tuple[str, str]] = []
    try:
        # Idempotent start: clear only THIS example's own prior resources,
        # in the same dependency order as teardown (monitor -> private
        # location -> agent policy -> global parameter). The parameter key
        # and the Fleet agent policy name are the ones that can actually
        # 409 on re-run; the monitor/location are cleared too for hygiene.
        for m in client.synthetics.get_monitors(tags=[PREFIX]).body["monitors"]:
            if m["name"].startswith(f"{PREFIX}-monitor"):
                client.synthetics.delete_monitor(id=m["config_id"])
        try:
            stale_location = client.synthetics.get_private_location(
                id=f"{PREFIX}-location"
            )
            client.synthetics.delete_private_location(id=stale_location.body["id"])
        except NotFoundError:
            pass
        stale_policies = (
            client.perform_request(
                "GET",
                "/api/fleet/agent_policies",
                params={"kuery": f'ingest-agent-policies.name:"{PREFIX}-policy"'},
            ).body.get("items")
            or []
        )
        for p in stale_policies:
            client.perform_request(
                "POST",
                "/api/fleet/agent_policies/delete",
                body={"agentPolicyId": p["id"], "force": True},
            )
        for prm in client.synthetics.get_params().body:
            if prm["key"] == f"{PREFIX}-auth-token":
                client.synthetics.delete_param(id=prm["id"])

        # A global parameter that monitors can reference as ${auth-token}
        param = client.synthetics.create_param(
            key=f"{PREFIX}-auth-token",
            value="s3cret-value",
            description="Example parameter",
            tags=[PREFIX],
        ).body
        param_id = param["id"]
        created.append(("synthetics param", param_id))
        print(f"Created parameter: {param['key']} ({param_id})")

        # Private locations are backed by a Fleet agent policy
        policy = client.perform_request(
            "POST",
            "/api/fleet/agent_policies",
            body={"name": f"{PREFIX}-policy", "namespace": "default"},
        ).body["item"]
        policy_id = policy["id"]
        created.append(("fleet agent policy", policy_id))

        location = client.synthetics.create_private_location(
            label=f"{PREFIX}-location",
            agent_policy_id=policy_id,
            geo={"lat": 40.4, "lon": -3.7},
        ).body
        location_id = location["id"]
        created.append(("synthetics private location", location_id))
        print(f"Created private location: {location['label']} ({location_id})")

        # An HTTP monitor that runs from the private location every 10 min
        monitor = client.synthetics.create_monitor(
            type="http",
            name=f"{PREFIX}-monitor",
            url="https://example.com",
            private_locations=[location_id],
            schedule={"number": "10", "unit": "m"},
            tags=[PREFIX],
        ).body
        monitor_id = monitor["config_id"]
        created.append(("synthetics monitor", monitor_id))
        print(f"Created monitor: {monitor['name']} ({monitor_id})")

        # List monitors filtered by tag
        listing = client.synthetics.get_monitors(tags=[PREFIX], per_page=10).body
        print(f"Monitors tagged {PREFIX!r}: {len(listing['monitors'])}")

        # Rename the monitor (partial update)
        renamed = client.synthetics.update_monitor(
            id=monitor_id, name=f"{PREFIX}-monitor-renamed"
        ).body
        print(f"Renamed monitor to: {renamed['name']}")

        # Trigger an on-demand test run (executes once an agent is enrolled)
        run = client.synthetics.test_monitor(monitor_id=monitor_id).body
        print(f"Triggered test run: {run['testRunId']}")
    finally:
        # Clean up everything we created, in dependency order: monitor ->
        # private location -> agent policy -> global parameter.
        if should_cleanup():
            if monitor_id:
                client.synthetics.delete_monitor(id=monitor_id)
                print("Deleted monitor.")
            if location_id:
                client.synthetics.delete_private_location(id=location_id)
                print("Deleted private location.")
            if policy_id:
                client.perform_request(
                    "POST",
                    "/api/fleet/agent_policies/delete",
                    body={"agentPolicyId": policy_id, "force": True},
                )
                print("Deleted agent policy.")
            if param_id:
                client.synthetics.delete_param(id=param_id)
                print("Deleted parameter.")
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
