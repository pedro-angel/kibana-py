#!/usr/bin/env python3
"""
Security Endpoint Management Example

This example shows the minimal code needed to:
1. List enrolled endpoint hosts (metadata) and read the response-actions state
2. Manage the reusable scripts library (create, get, download, delete)
3. Attempt a response action (isolate) and handle the semantic error the
   server returns when no host has the Elastic Defend integration installed

The Endpoint Management APIs (/api/endpoint/...) drive Elastic Defend. Response
actions require enrolled Defend endpoints; on a stack without any, the action
routes return a 400 that this example catches and reports.

Run this example:
    python examples/endpoint_management.py
"""

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import BadRequestError, NotFoundError


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)  # "kbnpy-endpoint"
    script_id = None
    created: list[tuple[str, str]] = []
    try:
        # 1. List enrolled endpoint hosts and read actions state
        hosts = client.endpoint.get_metadata_list(page_size=20)
        print(f"Enrolled endpoint hosts: {hosts.body['total']}")

        state = client.endpoint.get_actions_state()
        print(f"Response actions can encrypt: {state.body['data']['canEncrypt']}")

        # 2. Scripts library CRUD (works without enrolled endpoints).
        # Idempotent start: this example's script gets a server-assigned ID,
        # so there is no fixed ID to pre-delete. Instead clear this
        # example's OWN leftover scripts from earlier kept runs by matching
        # the name prefix (own scope only).
        existing_scripts = client.endpoint.get_scripts(page_size=100)
        stale_scripts = [
            s for s in existing_scripts.body["data"] if s["name"].startswith(prefix)
        ]
        for s in stale_scripts:
            try:
                client.endpoint.delete_script(script_id=s["id"])
            except NotFoundError:
                pass
        if stale_scripts:
            print(f"Cleared {len(stale_scripts)} leftover script(s)")

        created_script = client.endpoint.create_script(
            name=f"{prefix}-collect-logs",
            platform=["linux"],
            file_type="script",
            file=f"#!/bin/bash\necho {prefix}\n".encode(),
            filename="collect-logs.sh",
            description="Example script created by kibana-py",
            tags=["threatHunting"],
        )
        script_id = created_script.body["data"]["id"]
        created.append(("endpoint script", script_id))
        print(f"Created library script {script_id}")

        fetched = client.endpoint.get_script(script_id=script_id)
        print(f"  name={fetched.body['data']['name']}")

        download = client.endpoint.download_script(script_id=script_id)
        content = (
            download.body if isinstance(download.body, str) else download.body.decode()
        )
        print(f"  file starts with: {content.splitlines()[0]}")

        # 3. Attempt a response action; expect the Defend semantic error on a
        #    stack with no enrolled endpoints.
        try:
            client.endpoint.isolate(
                endpoint_ids=["example-endpoint-id"],
                comment="Isolating for investigation",
            )
            print("Isolate action submitted")
        except BadRequestError as exc:
            print(f"Isolate rejected (expected without Defend hosts): {exc}")
    finally:
        # 4. Clean up
        if script_id is not None:
            if should_cleanup():
                client.endpoint.delete_script(script_id=script_id)
                print(f"Deleted library script {script_id}")
            else:
                print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
