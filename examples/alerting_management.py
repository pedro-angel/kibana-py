#!/usr/bin/env python3
"""
Alerting Management Example

Demonstrates the Kibana Alerting API client (Kibana 9.4.3):

1. Framework health and available rule types
2. Creating an ".es-query" rule with a caller-chosen ID
3. Getting, finding and updating rules
4. Lifecycle operations: enable, mute/unmute, snooze/unsnooze, disable
5. Backfill endpoints
6. Cleanup

Run this example:
    python examples/alerting_management.py
"""

import uuid

from utils import get_kibana_config

from kibana import Kibana


def main() -> None:
    kibana_url, basic_auth, api_key = get_kibana_config()
    if api_key:
        client = Kibana(kibana_url, api_key=api_key)
    elif basic_auth:
        client = Kibana(kibana_url, basic_auth=basic_auth)
    else:
        client = Kibana(kibana_url)

    rule_id = f"kbnpy-alerting-example-{uuid.uuid4().hex[:8]}"

    try:
        # 1. Framework health and rule types
        health = client.alerting.health().body
        print(f"Alerting framework secure: {health['is_sufficiently_secure']}")

        rule_types = client.alerting.rule_types().body
        print(
            f"{len(rule_types)} rule types available, e.g. "
            f"{[t['id'] for t in rule_types[:3]]}"
        )

        # 2. Create a disabled .es-query rule with a chosen ID
        created = client.alerting.rule.create(
            id=rule_id,
            name="kbnpy example: error spike",
            consumer="alerts",
            rule_type_id=".es-query",
            schedule={"interval": "1m"},
            params={
                "searchType": "esQuery",
                "esQuery": '{"query":{"match_all":{}}}',
                "index": ["*"],
                "timeField": "@timestamp",
                "size": 1,
                "threshold": [0],
                "thresholdComparator": ">",
                "timeWindowSize": 5,
                "timeWindowUnit": "m",
            },
            enabled=False,
            tags=["kbnpy-example"],
            alert_delay={"active": 2},
        )
        print(f"Created rule {created.body['id']} ({created.body['name']})")

        # 3. Get, find, update
        rule = client.alerting.rule.get(id=rule_id).body
        print(f"Fetched rule, schedule: {rule['schedule']}")

        found = client.alerting.rule.find(
            search="kbnpy example",
            search_fields=["name"],
            sort_field="name",
            sort_order="asc",
            fields=["id", "name"],
        )
        print(f"Find matched {found.body['total']} rule(s)")

        updated = client.alerting.rule.update(
            id=rule_id,
            name="kbnpy example: error spike (updated)",
            schedule={"interval": "5m"},
            params=rule["params"],
            tags=rule["tags"],
        )
        print(f"Updated rule name: {updated.body['name']}")

        # 4. Lifecycle: enable, mute, snooze, unsnooze, unmute, disable
        client.alerting.rule.enable(id=rule_id)
        client.alerting.rule.mute_all(id=rule_id)
        snoozed = client.alerting.rule.snooze(
            id=rule_id,
            schedule={
                "custom": {"duration": "1h", "start": "2027-01-01T00:00:00.000Z"}
            },
        )
        schedule_id = snoozed.body["schedule"]["id"]
        print(f"Snoozed with schedule id {schedule_id}")
        client.alerting.rule.unsnooze(rule_id=rule_id, schedule_id=schedule_id)
        client.alerting.rule.unmute_all(id=rule_id)
        client.alerting.rule.disable(id=rule_id, untrack=True)
        print("Lifecycle operations complete")

        # 5. Backfills (only some rule types support scheduling backfills)
        backfills = client.alerting.backfill.find(per_page=5)
        print(f"Existing backfills: {backfills.body['total']}")

    finally:
        # 6. Cleanup
        try:
            client.alerting.rule.delete(id=rule_id)
            print(f"Deleted rule {rule_id}")
        except Exception:
            pass
        client.close()


if __name__ == "__main__":
    main()
