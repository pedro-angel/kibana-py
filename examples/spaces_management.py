#!/usr/bin/env python3
"""Spaces management example.

Demonstrates the Kibana Spaces API surface:
1. Create a space with a solution view and custom appearance
2. List spaces (including the caller's authorized purposes)
3. Update a space (PUT requires id + name)
4. Copy a saved object from the default space into the new space
5. Share a saved object into the space and back (shareable references)
6. Clean everything up

Run:
    python examples/spaces_management.py
"""

from utils import get_kibana_config

from kibana import Kibana

SPACE_ID = "kbnpy-spaces-example"
DASHBOARD_ID = "kbnpy-spaces-example-dash"
INDEX_PATTERN_ID = "kbnpy-spaces-example-ip"


def main() -> None:
    kibana_url, basic_auth, api_key = get_kibana_config()
    client = Kibana(kibana_url, basic_auth=basic_auth, api_key=api_key)

    try:
        # 1. Create a space with an Observability solution view
        space = client.spaces.create(
            id=SPACE_ID,
            name="kibana-py example space",
            description="Created by examples/spaces_management.py",
            color="#2E7D32",
            initials="KP",
            disabled_features=["ml"],
            solution="oblt",
        )
        print(f"Created space: {space.body['id']} (solution={space.body['solution']})")

        # 2. List spaces with the purposes this user is authorized for
        spaces = client.spaces.get_all(include_authorized_purposes=True)
        for s in spaces.body:
            purposes = [p for p, ok in s.get("authorizedPurposes", {}).items() if ok]
            print(f"  - {s['id']}: {s['name']} (authorized: {', '.join(purposes)})")

        # 3. Update the space — PUT requires id AND name every time
        updated = client.spaces.update(
            id=SPACE_ID,
            name="kibana-py example space (updated)",
            color="#AD1457",
            solution="classic",
        )
        print(f"Updated space name: {updated.body['name']}")

        # 4. Copy a dashboard from the default space into the new space
        client.saved_objects.create(
            type="dashboard",
            id=DASHBOARD_ID,
            attributes={"title": "kibana-py spaces example dashboard"},
            overwrite=True,
        )
        copy_result = client.spaces.copy_saved_objects(
            spaces=[SPACE_ID],
            objects=[{"type": "dashboard", "id": DASHBOARD_ID}],
            include_references=True,
        )
        outcome = copy_result.body[SPACE_ID]
        print(f"Copied {outcome['successCount']} object(s) into '{SPACE_ID}'")

        # 5. Share an index-pattern into the space and back again
        client.saved_objects.create(
            type="index-pattern",
            id=INDEX_PATTERN_ID,
            attributes={"title": "kbnpy-spaces-example-*"},
            overwrite=True,
        )
        refs = client.spaces.get_shareable_references(
            objects=[{"type": "index-pattern", "id": INDEX_PATTERN_ID}]
        )
        print(f"Index pattern currently in spaces: {refs.body['objects'][0]['spaces']}")

        shared = client.spaces.update_objects_spaces(
            objects=[{"type": "index-pattern", "id": INDEX_PATTERN_ID}],
            spaces_to_add=[SPACE_ID],
            spaces_to_remove=[],
        )
        print(f"After sharing: {shared.body['objects'][0]['spaces']}")

        unshared = client.spaces.update_objects_spaces(
            objects=[{"type": "index-pattern", "id": INDEX_PATTERN_ID}],
            spaces_to_add=[],
            spaces_to_remove=[SPACE_ID],
        )
        print(f"After unsharing: {unshared.body['objects'][0]['spaces']}")

    finally:
        # 6. Clean up (deleting the space also deletes the objects copied into it)
        for type_, id_ in (
            ("dashboard", DASHBOARD_ID),
            ("index-pattern", INDEX_PATTERN_ID),
        ):
            try:
                client.saved_objects.delete(type=type_, id=id_, force=True)
            except Exception:
                pass
        try:
            client.spaces.delete(id=SPACE_ID)
            print(f"Deleted space '{SPACE_ID}'")
        except Exception:
            pass
        client.close()


if __name__ == "__main__":
    main()
