#!/usr/bin/env python3
"""
Cases Management Example

Demonstrates the Kibana Cases API:
1. Create a case with tags and a severity
2. Add, update and list comments
3. Update the case status (bulk PATCH via a single-case-friendly helper)
4. Search cases and aggregate tags
5. Inspect the case activity log (user actions)
6. Clean up

Run this example:
    python examples/cases_management.py
"""

from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana


def main():
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)  # "kbnpy-cases"
    tag = f"{prefix}-tag"
    created: list[tuple[str, str]] = []
    try:
        # 0. Idempotent start: cases get server-assigned IDs, so find this
        # example's OWN cases by their namespaced tag (own scope only) and
        # delete them before creating fresh.
        leftovers = client.cases.find(tags=tag, per_page=100)
        leftover_ids = [c["id"] for c in leftovers.body["cases"]]
        if leftover_ids:
            client.cases.delete(ids=leftover_ids)
            print(f"Cleared {len(leftover_ids)} leftover case(s) tagged {tag}")

        # 1. Create a case
        case = client.cases.create(
            title=f"{prefix} Suspicious login activity",
            description="Multiple failed logins detected from a single IP.",
            tags=[tag, "security"],
            severity="high",
        )
        case_id = case.body["id"]
        created.append(("case", case_id))
        print(f"✓ Created case: {case_id}")
        print(f"  Status: {case.body['status']}, severity: {case.body['severity']}")

        # 2. Add a comment, then edit it
        commented = client.cases.add_comment(
            case_id=case_id, comment="Investigating the source IP."
        )
        comment = commented.body["comments"][-1]
        print(f"✓ Added comment: {comment['id']}")

        client.cases.update_comment(
            case_id=case_id,
            id=comment["id"],
            version=comment["version"],
            comment="Source IP belongs to a known scanner; blocking it.",
        )
        comments = client.cases.get_comments(case_id=case_id)
        print(f"  Case now has {comments.body['total']} comment(s)")

        # 3. Move the case to in-progress (PATCH /api/cases is a bulk API;
        #    update() wraps it with an id/version single-case signature)
        fetched = client.cases.get(case_id=case_id)
        updated = client.cases.update(
            id=case_id, version=fetched.body["version"], status="in-progress"
        )
        print(f"✓ Updated status: {updated.body[0]['status']}")

        # 4. Search cases and aggregate tags
        found = client.cases.find(tags=tag, per_page=5)
        print(f"✓ Found {found.body['total']} case(s) tagged {tag}")
        tags = client.cases.get_tags(owner="cases")
        print(f"  All case tags: {tags.body}")

        # 5. Review the activity log
        activity = client.cases.find_user_actions(case_id=case_id, sort_order="asc")
        actions = [
            f"{action['action']}:{action['type']}"
            for action in activity.body["userActions"]
        ]
        print(f"✓ Activity log: {actions}")

    finally:
        # 6. Clean up
        if should_cleanup():
            case_ids = [ident for kind, ident in created if kind == "case"]
            if case_ids:
                client.cases.delete(ids=case_ids)
                print(f"✓ Deleted {len(case_ids)} case(s)")
        else:
            print_kept(created)
        client.close()


if __name__ == "__main__":
    main()
