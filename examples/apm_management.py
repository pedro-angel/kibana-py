#!/usr/bin/env python3
"""
APM Management Example

This example shows the minimal code needed to:
1. Create an APM agent configuration and read it back
2. Create a deployment annotation for a service and search for it
3. Upload a RUM source map, list source maps, and delete it
4. Clean up (delete the agent configuration)

Run this example:
    python examples/apm_management.py
"""

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana

PREFIX = resource_prefix(__file__)  # "kbnpy-apm"
SERVICE = f"{PREFIX}-svc"
ENVIRONMENT = "testing"


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    sourcemap_id = None
    created: list[tuple[str, str]] = []
    try:
        # 1. Create an agent configuration and read it back
        client.apm.create_or_update_agent_configuration(
            service_name=SERVICE,
            service_environment=ENVIRONMENT,
            settings={"transaction_sample_rate": "0.5"},
            agent_name="nodejs",
        )
        config = client.apm.get_agent_configuration(
            name=SERVICE, environment=ENVIRONMENT
        )
        print(f"Created agent configuration: {config.body['settings']}")
        total = len(client.apm.get_agent_configurations().body["configurations"])
        print(f"Agent configurations stored: {total}")

        # 2. Create a deployment annotation and search for it
        annotation = client.apm.create_annotation(
            service_name=SERVICE,
            timestamp="2026-07-03T12:00:00.000Z",
            service_version="1.2.3",
            service_environment=ENVIRONMENT,
            message="Deployed 1.2.3",
        )
        print(f"Created annotation {annotation.body['_id']}")
        # Note: annotations have no delete API; they live in the
        # observability-annotations index.
        found = client.apm.search_annotations(
            service_name=SERVICE,
            environment=ENVIRONMENT,
            start="2026-07-01T00:00:00.000Z",
            end="2026-07-05T00:00:00.000Z",
        )
        for entry in found.body["annotations"]:
            print(f"Found annotation: {entry['text']}")

        # 3. Upload a tiny RUM source map, list it, then delete it
        uploaded = client.apm.upload_sourcemap(
            service_name=SERVICE,
            service_version="1.2.3",
            bundle_filepath="http://localhost/static/js/bundle.js",
            sourcemap={
                "version": 3,
                "file": "bundle.js",
                "sources": ["app.js"],
                "names": [],
                "mappings": "AAAA",
            },
        )
        sourcemap_id = uploaded.body["id"]
        created.append(("APM source map", sourcemap_id))
        created.append(("APM agent configuration", f"{SERVICE}/{ENVIRONMENT}"))
        print(f"Uploaded source map {uploaded.body['identifier']}")
        listed = client.apm.get_sourcemaps(page=1, per_page=10)
        print(f"Source maps stored: {listed.body['total']}")
    finally:
        # 4. Clean up
        if should_cleanup():
            if sourcemap_id is not None:
                client.apm.delete_sourcemap(id=sourcemap_id)
                print(f"Deleted source map {sourcemap_id}")
            try:
                client.apm.delete_agent_configuration(
                    service_name=SERVICE, service_environment=ENVIRONMENT
                )
                print("Deleted agent configuration")
            except Exception:
                pass
        else:
            print_kept(created)
        # The deployment annotation has no delete API; it stays in the
        # observability-annotations index and cannot be torn down here.
        print("Note: the APM deployment annotation cannot be deleted (no API).")
        client.close()


if __name__ == "__main__":
    main()
