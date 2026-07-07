#!/usr/bin/env python3
"""
Fleet Outputs Management Example

This example shows the minimal code needed to:
1. List Fleet outputs and inspect the default output
2. Create a Logstash output, update it and check its health
3. Create a Fleet proxy and a Fleet Server host that uses it
4. Clean up (delete everything this example created)

Run this example:
    python examples/fleet_outputs_management.py
"""

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import NotFoundError


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)  # "kbnpy-fleet-outputs"
    output_id = None
    proxy_id = None
    host_id = None
    created: list[tuple[str, str]] = []
    try:
        # 1. List outputs (the default Elasticsearch output always exists)
        outputs = client.fleet_outputs.get_outputs()
        for item in outputs.body["items"]:
            marker = " (default)" if item["is_default"] else ""
            print(f"Output: {item['name']} [{item['type']}]{marker}")

        # 2. Create a Logstash output, rename it and check its health
        created_output = client.fleet_outputs.create_output(
            name=f"{prefix}-logstash",
            type="logstash",
            hosts=["logstash.example.com:5044"],
        )
        output_id = created_output.body["item"]["id"]
        created.append(("fleet output", output_id))
        print(f"Created output {output_id}")

        client.fleet_outputs.update_output(
            output_id=output_id, name=f"{prefix}-logstash-renamed"
        )
        health = client.fleet_outputs.get_output_health(output_id=output_id)
        print(f"Output health: {health.body['state']}")

        # 3. Create a proxy and a Fleet Server host that connects through it
        proxy = client.fleet_outputs.create_proxy(
            name=f"{prefix}-proxy",
            url="https://proxy.example.com:3128",
        )
        proxy_id = proxy.body["item"]["id"]
        created.append(("fleet proxy", proxy_id))
        print(f"Created proxy {proxy_id}")

        host = client.fleet_outputs.create_fleet_server_host(
            name=f"{prefix}-fleet-server",
            host_urls=["https://fleet.example.com:8220"],
            proxy_id=proxy_id,
        )
        host_id = host.body["item"]["id"]
        created.append(("fleet server host", host_id))
        print(f"Created Fleet Server host {host_id}")
    finally:
        # 4. Clean up — dependency order: the Fleet Server host references
        # the proxy, so it must be deleted first.
        if should_cleanup():
            if host_id is not None:
                try:
                    client.fleet_outputs.delete_fleet_server_host(item_id=host_id)
                    print(f"Deleted Fleet Server host {host_id}")
                except NotFoundError:
                    pass
            if proxy_id is not None:
                try:
                    client.fleet_outputs.delete_proxy(item_id=proxy_id)
                    print(f"Deleted proxy {proxy_id}")
                except NotFoundError:
                    pass
            if output_id is not None:
                try:
                    client.fleet_outputs.delete_output(output_id=output_id)
                    print(f"Deleted output {output_id}")
                except NotFoundError:
                    pass
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
