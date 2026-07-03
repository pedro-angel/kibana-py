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

from utils import get_kibana_config

from kibana import Kibana


def main():
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    created_ids = []
    try:
        # 1. Create a case
        case = client.cases.create(
            title="kbnpy-example Suspicious login activity",
            description="Multiple failed logins detected from a single IP.",
            tags=["kbnpy-example-tag", "security"],
            severity="high",
        )
        case_id = case.body["id"]
        created_ids.append(case_id)
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
        found = client.cases.find(tags="kbnpy-example-tag", per_page=5)
        print(f"✓ Found {found.body['total']} case(s) tagged kbnpy-example-tag")
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
        if created_ids:
            client.cases.delete(ids=created_ids)
            print(f"✓ Deleted {len(created_ids)} case(s)")
        client.close()


if __name__ == "__main__":
    main()
