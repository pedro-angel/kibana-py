#!/usr/bin/env python3
"""
Security Management Example

Demonstrates the Kibana Security (roles and sessions) API:
1. Create or update a role (Elasticsearch + Kibana privileges)
2. Get a single role and list all roles
3. Query roles with paging, sorting and filters
4. Bulk create/update roles
5. Invalidate user sessions matching a query
6. Delete roles (cleanup)

Run this example:
    python examples/security_management.py
"""

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import ApiError, NotFoundError

PREFIX = resource_prefix(__file__)  # "kbnpy-security"


def main() -> None:
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    role_name = f"{PREFIX}-log-reader"
    bulk_names = [f"{PREFIX}-bulk-a", f"{PREFIX}-bulk-b"]
    created: list[tuple[str, str]] = [
        ("role", name) for name in [role_name, *bulk_names]
    ]

    try:
        # 1. Create or update a role
        client.security.create_or_update_role(
            name=role_name,
            description="Read-only access to example logs",
            elasticsearch={
                "cluster": ["monitor"],
                "indices": [{"names": [f"{PREFIX}-*"], "privileges": ["read"]}],
            },
            kibana=[{"base": ["read"], "spaces": ["default"]}],
            metadata={"created_by": "kibana-py example"},
        )
        print(f"Created role: {role_name}")

        # 2. Get it back, and list all roles
        role = client.security.get_role(name=role_name)
        print(f"Role description: {role.body['description']}")
        all_roles = client.security.get_all_roles()
        print(f"Total roles on the cluster: {len(all_roles.body)}")

        # 3. Query roles (paged, sorted, excluding reserved roles)
        result = client.security.query_roles(
            query=PREFIX,
            from_=0,
            size=10,
            sort={"field": "name", "direction": "asc"},
            filters={"showReservedRoles": False},
        )
        print(f"Roles matching '{PREFIX}': {result.body['total']}")

        # 4. Bulk create/update roles
        bulk = client.security.bulk_create_or_update_roles(
            roles={
                bulk_names[0]: {"elasticsearch": {"cluster": ["monitor"]}},
                bulk_names[1]: {
                    "elasticsearch": {},
                    "kibana": [{"base": ["read"], "spaces": ["*"]}],
                },
            }
        )
        print(f"Bulk result: {bulk.body}")

        # 5. Invalidate sessions for a specific (nonexistent) user.
        #    Requires superuser; match="all" would log out every user!
        invalidated = client.security.invalidate_sessions(
            match="query",
            query={"provider": {"type": "basic"}, "username": f"{PREFIX}-nobody"},
        )
        print(f"Invalidated sessions: {invalidated.body['total']}")

    except ApiError as e:
        print(f"API error: {e}")
    finally:
        # 6. Cleanup: delete everything the example created
        if should_cleanup():
            for name in [role_name, *bulk_names]:
                try:
                    client.security.delete_role(name=name)
                    print(f"Deleted role: {name}")
                except NotFoundError:
                    pass
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
