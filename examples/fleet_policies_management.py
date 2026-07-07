#!/usr/bin/env python3
"""
Fleet Policies Management Example

This example shows the minimal code needed to:
1. Create a Fleet agent policy
2. Attach a package policy (the lightweight "udp" integration) to it
3. Inspect the compiled policy (outputs + downloadable YAML)
4. Dry-run a package policy upgrade
5. Clean up (delete the package policy and the agent policy)

Run this example:
    python examples/fleet_policies_management.py
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

    prefix = resource_prefix(__file__)  # "kbnpy-fleet-policies"
    agent_policy_name = f"{prefix}-agent-policy"
    package_policy_name = f"{prefix}-udp-policy"
    agent_policy_id = None
    package_policy_id = None
    created: list[tuple[str, str]] = []
    try:
        # Idempotent start: clear only THIS example's own prior resources.
        # Both names are unique-constrained, so a leftover run would 409 on
        # create. Dependency order: the package policy references the
        # agent policy, so it must be deleted first.
        stale_pkg = client.fleet_policies.get_package_policies(
            kuery=f'ingest-package-policies.name:"{package_policy_name}"'
        )
        for item in stale_pkg.body.get("items") or []:
            client.fleet_policies.delete_package_policy(
                package_policy_id=item["id"], force=True
            )
        stale_policy = client.fleet_policies.get_agent_policies(
            kuery=f'ingest-agent-policies.name:"{agent_policy_name}"'
        )
        for item in stale_policy.body.get("items") or []:
            client.fleet_policies.delete_agent_policy(
                agent_policy_id=item["id"], force=True
            )

        # 1. Create an agent policy (sys_monitoring=False keeps it minimal)
        created_policy = client.fleet_policies.create_agent_policy(
            name=agent_policy_name,
            namespace="default",
            description="Created by the kibana-py fleet_policies example",
            monitoring_enabled=["logs", "metrics"],
            sys_monitoring=False,
        )
        agent_policy_id = created_policy.body["item"]["id"]
        created.append(("fleet agent policy", agent_policy_id))
        print(f"Created agent policy {agent_policy_id}")

        # 2. Attach a udp package policy (installs the package if needed).
        #    The latest package version is resolved via the EPM API. This
        #    installs the shared 'udp' registry package as a side effect,
        #    which this example does NOT uninstall (see the cleanup note).
        udp = client.perform_request("GET", "/api/fleet/epm/packages/udp")
        udp_version = udp.body["item"]["version"]
        pkg = client.options(
            request_timeout=120.0
        ).fleet_policies.create_package_policy(
            name=package_policy_name,
            package={"name": "udp", "version": udp_version},
            policy_ids=[agent_policy_id],
            inputs={
                "udp-udp": {
                    "enabled": True,
                    "streams": {
                        "udp.udp": {
                            "enabled": True,
                            "vars": {
                                "listen_address": "localhost",
                                "listen_port": 8964,
                                "data_stream.dataset": "kbnpy.example",
                            },
                        }
                    },
                }
            },
        )
        package_policy_id = pkg.body["item"]["id"]
        created.append(("fleet package policy", package_policy_id))
        print(f"Created package policy {package_policy_id} (udp {udp_version})")

        # 3. Inspect the policy: outputs and the elastic-agent.yml document
        outputs = client.fleet_policies.get_agent_policy_outputs(
            agent_policy_id=agent_policy_id
        )
        print(f"Data output: {outputs.body['item']['data']['output']['id']}")

        yaml_doc = client.fleet_policies.download_agent_policy(
            agent_policy_id=agent_policy_id
        )
        print(f"elastic-agent.yml starts with: {yaml_doc.body.splitlines()[0]}")

        # 4. Dry-run an upgrade of the package policy (no changes persisted)
        dry_run = client.fleet_policies.upgrade_package_policies_dry_run(
            package_policy_ids=[package_policy_id]
        )
        print(f"Upgrade dry run hasErrors: {dry_run.body[0]['hasErrors']}")
    finally:
        # 5. Clean up — package policy before agent policy (the package
        # policy references the agent policy).
        if should_cleanup():
            if package_policy_id is not None:
                try:
                    client.fleet_policies.delete_package_policy(
                        package_policy_id=package_policy_id, force=True
                    )
                    print(f"Deleted package policy {package_policy_id}")
                except NotFoundError as exc:
                    print(f"Could not delete package policy: {exc.message}")
            if agent_policy_id is not None:
                try:
                    client.fleet_policies.delete_agent_policy(
                        agent_policy_id=agent_policy_id, force=True
                    )
                    print(f"Deleted agent policy {agent_policy_id}")
                except NotFoundError as exc:
                    print(f"Could not delete agent policy: {exc.message}")
        else:
            print_kept(created)
        # Note: creating the package policy installs the 'udp' registry
        # package as a side effect; this example does not uninstall it
        # (documented leak — see fleet_epm_management.py to uninstall
        # packages explicitly).
        print("Note: the 'udp' integration package installed above is not uninstalled.")
        client.close()


if __name__ == "__main__":
    main()
