# Alerting

The Alerting API lets you manage Kibana alerting rules programmatically: create rules, control their lifecycle (enable, disable, mute, snooze), rotate API keys, and schedule backfill runs. kibana-py exposes it as `client.alerting`, organized into:

- `client.alerting.rule` — rule CRUD and lifecycle operations
- `client.alerting.backfill` — backfill (catch-up) run scheduling
- `client.alerting.health()` and `client.alerting.rule_types()` — framework-level helpers

## Creating Rules

A rule needs a `name`, a `consumer` (the feature that owns it), a `rule_type_id`, a check `schedule`, and rule-type-specific `params`:

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your_api_key")

rule = client.alerting.rule.create(
    name="ES query rule",
    consumer="alerts",
    rule_type_id=".es-query",
    schedule={"interval": "1m"},
    params={
        "searchType": "esQuery",
        "size": 100,
        "timeWindowSize": 5,
        "timeWindowUnit": "m",
        "threshold": [10],
        "thresholdComparator": ">",
        "index": ["logs-*"],
        "timeField": "@timestamp",
        "esQuery": '{"query": {"match_all": {}}}',
    },
    tags=["ops"],
)

rule_id = rule.body["id"]
print(f"Created rule: {rule_id}")
```

Useful optional arguments:

- `id` — a caller-chosen rule ID (otherwise Kibana generates one)
- `actions` — a list of actions to run when the rule fires (each references a [connector](connectors.md))
- `enabled` — whether the rule starts enabled (default `True`)
- `notify_when` / `throttle` — notification cadence (`throttle` is deprecated in favor of per-action `frequency`)
- `alert_delay` — e.g. `{"active": 3}` to require consecutive matching runs before alerting
- `flapping` — e.g. `{"look_back_window": 10, "status_change_threshold": 3}`

### Attaching Actions

```python
rule = client.alerting.rule.create(
    name="CPU alert with notification",
    consumer="alerts",
    rule_type_id=".index-threshold",
    schedule={"interval": "1m"},
    params={
        "index": ["metrics-*"],
        "timeField": "@timestamp",
        "aggType": "avg",
        "aggField": "system.cpu.total.pct",
        "groupBy": "all",
        "timeWindowSize": 5,
        "timeWindowUnit": "m",
        "thresholdComparator": ">",
        "threshold": [0.9],
    },
    actions=[
        {
            "id": "my-connector-id",           # An existing connector
            "group": "threshold met",
            "params": {"message": "CPU above 90%"},
            "frequency": {"notify_when": "onActionGroupChange", "summary": False},
        }
    ],
)
```

## Reading and Searching Rules

```python
# Get a rule by ID
rule = client.alerting.rule.get(id=rule_id)
print(rule.body["name"], rule.body["enabled"])

# Search rules
found = client.alerting.rule.find(search="cpu", per_page=10)
for r in found.body["data"]:
    print(f"  {r['id']}: {r['name']} (enabled={r['enabled']})")

# List available rule types (returns a JSON array)
types = client.alerting.rule_types()
print([t["id"] for t in types.body])
```

:::{note}
On live Kibana 9.4.3, passing `sort_order` to `find()` without `sort_field` returns HTTP 406 — pass both together. `client.alerting.rule_types()` returns a bare JSON array, so iterate `types.body` directly.
:::

## Updating Rules

`update()` replaces the rule's user-editable attributes (`name`, `schedule`, `params`, `actions`, `tags`, ...). The `consumer` and `rule_type_id` cannot be changed:

```python
client.alerting.rule.update(
    id=rule_id,
    name="ES query rule (tightened)",
    schedule={"interval": "30s"},
    params={
        "searchType": "esQuery",
        "size": 100,
        "timeWindowSize": 5,
        "timeWindowUnit": "m",
        "threshold": [5],
        "thresholdComparator": ">",
        "index": ["logs-*"],
        "timeField": "@timestamp",
        "esQuery": '{"query": {"match_all": {}}}',
    },
)
```

## Rule Lifecycle

### Enable and Disable

```python
client.alerting.rule.disable(id=rule_id)

# Optionally untrack active alerts when disabling
client.alerting.rule.disable(id=rule_id, untrack=True)

client.alerting.rule.enable(id=rule_id)
```

### Mute and Unmute

Muting suppresses a rule's notifications while the rule keeps running:

```python
# Mute all alerts of a rule
client.alerting.rule.mute_all(id=rule_id)
client.alerting.rule.unmute_all(id=rule_id)

# Mute a single alert (instance) of a rule
client.alerting.rule.mute_alert(rule_id=rule_id, alert_id="server-1")
client.alerting.rule.unmute_alert(rule_id=rule_id, alert_id="server-1")
```

:::{note}
By default the live server validates that the alert instance exists and returns 404 for an alert that has never fired. To pre-emptively mute an alert that has not fired yet, pass `validate_alerts_existence=False`:

```python
client.alerting.rule.mute_alert(
    rule_id=rule_id, alert_id="server-1", validate_alerts_existence=False
)
```
:::

### Snoozing

Snoozing suppresses notifications for a scheduled period — useful for planned maintenance (see also [Maintenance Windows](platform-apis.md#maintenance-windows) for space-wide suppression):

```python
# Snooze for one hour starting at a given time
snoozed = client.alerting.rule.snooze(
    id=rule_id,
    schedule={
        "custom": {
            "duration": "1h",
            "start": "2026-07-04T00:00:00.000Z",
        }
    },
)

# The response contains the schedule ID needed to remove the snooze
schedule_id = snoozed.body["schedule"]["id"]

client.alerting.rule.unsnooze(rule_id=rule_id, schedule_id=schedule_id)
```

### Rotating the API Key

Rules run with an embedded API key. Rotate it after credential changes:

```python
client.alerting.rule.update_api_key(id=rule_id)
```

## Deleting Rules

```python
client.alerting.rule.delete(id=rule_id)
```

## Backfills

Backfills run a rule against a historical time range — for example after an outage, or when a rule was created late and you want it evaluated over past data. Backfills are supported by detection-style rule types.

```python
# Schedule a backfill over a past window (ISO 8601 timestamps)
result = client.alerting.backfill.schedule(
    backfills=[
        {
            "rule_id": rule_id,
            "ranges": [
                {
                    "start": "2026-07-01T00:00:00.000Z",
                    "end": "2026-07-01T12:00:00.000Z",
                }
            ],
            "run_actions": False,
        }
    ]
)

# Find scheduled backfills
backfills = client.alerting.backfill.find(rule_ids=rule_id)
for b in backfills.body["data"]:
    print(b["id"], b["status"])

# Get / delete a backfill by ID
backfill = client.alerting.backfill.get(id="backfill-id")
client.alerting.backfill.delete(id="backfill-id")
```

:::{note}
Two live-server behaviors to be aware of on Kibana 9.4.3:

- Scheduling a backfill for an unsupported rule type (e.g. `.es-query`) returns HTTP **200 with a per-item error object** (`"Backfill not supported..."`) rather than an error status — always inspect the response body.
- Backfill ranges older than roughly 90 days are rejected.
:::

## Framework Health

```python
health = client.alerting.health()
print(health.body["is_sufficiently_secure"])
print(health.body["alerting_framework_health"]["execution_health"]["status"])
```

## Space-Scoped Rules

Alerting rules are space-scoped. Every method accepts `space_id`, or use a space-scoped client:

```python
rule = client.alerting.rule.create(
    name="Marketing alert",
    consumer="alerts",
    rule_type_id=".es-query",
    schedule={"interval": "5m"},
    params={...},
    space_id="marketing",
)

# Or scope the client
marketing = client.space("marketing")
found = marketing.alerting.rule.find(search="Marketing*")
```

## Complete Example: Rule Lifecycle

```python
from kibana import Kibana
from kibana.exceptions import NotFoundError

with Kibana("http://localhost:5601", api_key="your_api_key") as client:
    rule = client.alerting.rule.create(
        name="kbnpy-demo-rule",
        consumer="alerts",
        rule_type_id=".es-query",
        schedule={"interval": "1m"},
        params={
            "searchType": "esQuery",
            "size": 100,
            "timeWindowSize": 5,
            "timeWindowUnit": "m",
            "threshold": [10],
            "thresholdComparator": ">",
            "index": ["logs-*"],
            "timeField": "@timestamp",
            "esQuery": '{"query": {"match_all": {}}}',
        },
        enabled=True,
    )
    rule_id = rule.body["id"]

    try:
        # Snooze it for planned maintenance
        snoozed = client.alerting.rule.snooze(
            id=rule_id,
            schedule={"custom": {"duration": "1h",
                                 "start": "2026-07-04T00:00:00.000Z"}},
        )
        client.alerting.rule.unsnooze(
            rule_id=rule_id, schedule_id=snoozed.body["schedule"]["id"]
        )

        # Disable, then re-enable
        client.alerting.rule.disable(id=rule_id)
        client.alerting.rule.enable(id=rule_id)
    finally:
        try:
            client.alerting.rule.delete(id=rule_id)
        except NotFoundError:
            pass
```

## Next Steps

- Set up [Connectors](connectors.md) for rule actions
- Use [Maintenance Windows](platform-apis.md#maintenance-windows) to suppress notifications across many rules
- See [Error Handling](error-handling.md) for exception patterns
- Browse `examples/alerting_management.py` in the repository for a runnable end-to-end script
