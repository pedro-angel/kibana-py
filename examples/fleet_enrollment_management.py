#!/usr/bin/env python3
"""
Fleet Enrollment Management Example

This example shows the minimal code needed to:
1. Create an agent policy and an enrollment API key for it
2. List and fetch enrollment API keys
3. Read the policy's uninstall token
4. Create a Fleet Server service token
5. Get the Kubernetes agent manifest
6. Clean up (revoke the key, delete the policy)

Run this example:
    python examples/fleet_enrollment_management.py
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

    prefix = resource_prefix(__file__)  # "kbnpy-fleet-enrollment"
    policy_name = f"{prefix}-policy"
    key_name = f"{prefix}-key"
    policy_id = None
    key_id = None
    created: list[tuple[str, str]] = []
    try:
        # Idempotent start: clear only THIS example's own prior resources.
        # The agent policy name is unique-constrained, so a leftover run
        # would 409 on create. Dependency order: revoke any enrollment
        # keys tied to the stale policy before deleting the policy itself.
        stale = client.perform_request(
            "GET",
            "/api/fleet/agent_policies",
            params={"kuery": f'ingest-agent-policies.name:"{policy_name}"'},
        )
        for item in stale.body.get("items") or []:
            stale_policy_id = item["id"]
            stale_keys = client.fleet_enrollment.get_keys(
                kuery=f'policy_id:"{stale_policy_id}"'
            )
            for key in stale_keys.body.get("items") or []:
                client.fleet_enrollment.delete_key(key_id=key["id"])
            client.perform_request(
                "POST",
                "/api/fleet/agent_policies/delete",
                body={"agentPolicyId": stale_policy_id, "force": True},
            )

        # 1. Create a throwaway agent policy (enrollment keys belong to one)
        policy = client.perform_request(
            "POST",
            "/api/fleet/agent_policies",
            params={"sys_monitoring": False},
            body={"name": policy_name, "namespace": "default"},
        )
        policy_id = policy.body["item"]["id"]
        created.append(("fleet agent policy", policy_id))
        print(f"Created agent policy {policy_id}")

        # ... and an enrollment API key that agents use to join it
        created_key = client.fleet_enrollment.create_key(
            policy_id=policy_id, name=key_name
        )
        key_id = created_key.body["item"]["id"]
        created.append(("fleet enrollment key", key_id))
        print(f"Created enrollment key {key_id}")
        print(f"  Enroll agents with: {created_key.body['item']['api_key']}")

        # 2. List keys for the policy, then fetch one by ID
        keys = client.fleet_enrollment.get_keys(kuery=f'policy_id:"{policy_id}"')
        print(f"Policy has {keys.body['total']} enrollment key(s)")
        fetched = client.fleet_enrollment.get_key(key_id=key_id)
        print(
            f"Fetched key {fetched.body['item']['id']} (active={fetched.body['item']['active']})"
        )

        # 3. Read the uninstall token generated for the policy
        tokens = client.fleet_enrollment.get_uninstall_tokens(policy_id=policy_id)
        token_id = tokens.body["items"][0]["id"]
        decrypted = client.fleet_enrollment.get_uninstall_token(
            uninstall_token_id=token_id
        )
        print(f"Uninstall token for the policy: {decrypted.body['item']['token']}")

        # 4. Create a Fleet Server service token (no delete API — see the
        # cleanup note below; this is a documented, unavoidable leak).
        service_token = client.fleet_enrollment.create_service_token()
        print(f"Created service token {service_token.body['name']}")

        # 5. Get the Kubernetes manifest with our enrollment token baked in
        manifest = client.fleet_enrollment.get_kubernetes_manifest(
            fleet_server="https://fleet.example.com:8220",
            enrol_token=created_key.body["item"]["api_key"],
        )
        print(f"Kubernetes manifest: {len(manifest.body['item'])} bytes of YAML")
    finally:
        # 6. Clean up — revoke the enrollment key before deleting the
        # policy it belongs to.
        if should_cleanup():
            if key_id is not None:
                try:
                    client.fleet_enrollment.delete_key(key_id=key_id)
                    print(f"Revoked enrollment key {key_id}")
                except NotFoundError:
                    pass
            if policy_id is not None:
                client.perform_request(
                    "POST",
                    "/api/fleet/agent_policies/delete",
                    body={"agentPolicyId": policy_id},
                )
                print(f"Deleted agent policy {policy_id}")
        else:
            print_kept(created)
        # Note: the Fleet Server service token created above has no delete
        # API and cannot be revoked or cleaned up (documented leak).
        print(
            "Note: the Fleet Server service token created above cannot be "
            "deleted (no API)."
        )
        client.close()


if __name__ == "__main__":
    main()
