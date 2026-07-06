#!/usr/bin/env python3
"""
Detection Engine (Security Detections) Management Example

This example shows the minimal code needed to:
1. Create a custom detection rule (disabled query rule)
2. Get and find the rule
3. Patch the rule (add tags)
4. Preview the alerts the rule would generate
5. Export the rule as NDJSON and re-import it
6. Search detection alerts (signals)
7. Clean up (delete the rule)

Run this example:
    python examples/detection_engine_management.py
"""

from datetime import UTC, datetime

from utils import get_kibana_config

from kibana import Kibana


def main():
    # Automatic configuration (env vars or elastic-start-local stack)
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    else:
        client = Kibana(kibana_url, basic_auth=basic_auth)

    rule_id = "kbnpy-example-detection-rule"
    try:
        # 1. Create a custom query rule (disabled so it does not execute)
        created = client.detection_engine.create_rule(
            type="query",
            name="kbnpy example rule",
            description="Example rule created by kibana-py",
            severity="low",
            risk_score=21,
            rule_id=rule_id,
            query='user.name: "kbnpy-example-nonexistent"',
            index=["logs-*"],
            interval="60m",
            from_="now-120m",
            enabled=False,
        )
        print(f"Created rule {created.body['id']} (rule_id={rule_id})")

        # 2. Get it back and find it by name
        fetched = client.detection_engine.get_rule(rule_id=rule_id)
        print(f"Fetched rule: {fetched.body['name']} ({fetched.body['severity']})")

        found = client.detection_engine.find_rules(
            filter='alert.attributes.name: "kbnpy example rule"'
        )
        print(f"Found {found.body['total']} rule(s) matching the name filter")

        # 3. Patch: add tags without touching the rest of the rule
        patched = client.detection_engine.patch_rule(
            rule_id=rule_id, tags=["kbnpy", "example"]
        )
        print(f"Patched rule tags: {patched.body['tags']}")

        # 4. Preview the alerts this rule would have generated
        preview = client.detection_engine.preview_rule(
            type="query",
            name="kbnpy example preview",
            description="Preview run",
            severity="low",
            risk_score=21,
            query='user.name: "kbnpy-example-nonexistent"',
            index=["logs-*"],
            invocation_count=1,
            timeframe_end=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            from_="now-6h",
            interval="1h",
        )
        print(f"Preview {preview.body['previewId']} ran; logs: {preview.body['logs']}")

        # 5. Export the rule as NDJSON, then re-import it (overwrite)
        exported = client.detection_engine.export_rules(
            objects=[{"rule_id": rule_id}], exclude_export_details=True
        )
        rules = list(exported)
        print(f"Exported {len(rules)} rule(s) as NDJSON")

        imported = client.detection_engine.import_rules(file=rules, overwrite=True)
        print(f"Import success={imported.body['success']}")

        # 6. Search detection alerts (none expected for this disabled rule)
        alerts = client.detection_engine.search_alerts(query={"match_all": {}}, size=1)
        print(f"Alerts in index: {alerts.body['hits']['total']['value']}")
    finally:
        # 7. Clean up
        client.detection_engine.delete_rule(rule_id=rule_id)
        print(f"Deleted rule {rule_id}")
        client.close()


if __name__ == "__main__":
    main()
