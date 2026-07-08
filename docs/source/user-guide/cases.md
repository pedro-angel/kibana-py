# Cases

Cases let you open and track issues directly in Kibana: add assignees and tags, set severity and status, attach comments, alerts, and files, and push cases to external incident-management systems. kibana-py exposes the full Cases API as `client.cases`.

## Creating Cases

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your_api_key")

case = client.cases.create(
    title="Suspicious login activity",
    description="Multiple failed logins detected from unusual locations.",
    tags=["security", "auth"],
    severity="high",
)

case_id = case.body["id"]
case_version = case.body["version"]
print(f"Created case {case_id} (status: {case.body['status']})")
```

Key arguments:

- `owner` — the application that owns the case: `"cases"` (Stack Management, the default), `"observability"`, or `"securitySolution"`
- `severity` — `"low"` (default), `"medium"`, `"high"`, or `"critical"`
- `connector` — an external incident-management connector (`{"id", "name", "type", "fields"}`); defaults to the "none" connector
- `settings` — e.g. `{"syncAlerts": True}`; defaults to `{"syncAlerts": False}`
- `assignees` — a list of `{"uid": ...}` user profile objects (Platinum+ license)
- `category` and `custom_fields` — additional classification

## Reading and Searching Cases

```python
# Get a case by ID
case = client.cases.get(case_id=case_id)
print(case.body["title"], case.body["status"])

# Search cases with filters
found = client.cases.find(
    status="open",
    severity="high",
    tags="security",
    search="login",
    sort_field="createdAt",
    sort_order="desc",
    per_page=20,
)
print(f"{found.body['total']} matching cases "
      f"({found.body['count_open_cases']} open)")
for c in found.body["cases"]:
    print(f"  {c['id']}: {c['title']}")

# Aggregations across your cases
tags = client.cases.get_tags()          # all tags in use (JSON array)
reporters = client.cases.get_reporters()  # all reporters (JSON array)
```

## Updating Cases

The Cases update endpoint is a bulk `PATCH` with optimistic concurrency: every update must include the case's current `version`. kibana-py offers a single-case-friendly form:

```python
# Fetch the current version first
case = client.cases.get(case_id=case_id)

updated = client.cases.update(
    id=case_id,
    version=case.body["version"],
    status="in-progress",
    severity="critical",
)
# The response body is a LIST of updated cases
print(updated.body[0]["status"])
```

To update several cases at once, pass `cases` with raw API field names:

```python
client.cases.update(
    cases=[
        {"id": "case-1", "version": "WzUsMV0=", "status": "closed"},
        {"id": "case-2", "version": "WzYsMV0=", "tags": ["triaged"]},
    ]
)
```

:::{note}
A stale `version` raises `ConflictError` — re-fetch the case and retry. This protects concurrent workflows from clobbering each other's changes.
:::

## Comments and Alerts

```python
# Add a text comment
updated = client.cases.add_comment(
    case_id=case_id,
    comment="Investigating the failed logins.",
)
print(f"Comments: {updated.body['totalComment']}")

# Attach an alert to the case
client.cases.add_comment(
    case_id=case_id,
    type="alert",
    owner="cases",
    alert_id="alert-uuid",
    index=".alerts-observability.logs.alerts-default",
    rule={"id": "rule-id", "name": "My rule"},
)

# List attachments (paginated)
comments = client.cases.get_comments(case_id=case_id, per_page=10)
for comment in comments.body["comments"]:
    print(comment["type"], comment.get("comment", ""))

# Update / delete comments
first = comments.body["comments"][0]
client.cases.update_comment(
    case_id=case_id,
    id=first["id"],
    version=first["version"],
    comment="Updated comment text.",
)
client.cases.delete_comment(case_id=case_id, comment_id=first["id"])

# Alerts attached to a case, and cases attached to an alert
alerts = client.cases.get_alerts(case_id=case_id)          # JSON array
cases_for_alert = client.cases.get_cases_by_alert(alert_id="alert-uuid")
```

## Attaching Files

```python
with open("evidence.png", "rb") as f:
    client.cases.add_file(
        case_id=case_id,
        file=f.read(),
        filename="evidence.png",
        mime_type="image/png",
    )
```

Files are stored as `externalReference` attachments backed by a `file` saved object.

## User Actions (Audit Trail)

Every change to a case is recorded as a user action:

```python
actions = client.cases.find_user_actions(case_id=case_id, sort_order="asc")
for action in actions.body["userActions"]:
    print(action["type"], action["action"], action["created_at"])
```

## External Incident Management

Push a case to a configured connector (Jira, ServiceNow, etc.):

```python
# Find connectors usable with cases (JSON array)
connectors = client.cases.find_connectors()
for conn in connectors.body:
    print(conn["id"], conn["name"])

pushed = client.cases.push(case_id=case_id, connector_id="connector-id")
print(pushed.body["external_service"]["external_url"])
```

### Case Configuration

Configure default connectors, closure behavior, custom fields, and templates per owner:

```python
config = client.cases.get_configuration()

created = client.cases.create_configuration(
    closure_type="close-by-user",
    connector={"id": "none", "name": "none", "type": ".none", "fields": None},
    owner="cases",
)

client.cases.update_configuration(
    configuration_id=created.body["id"],
    version=created.body["version"],
    closure_type="close-by-pushing",
)
```

## Deleting Cases

`delete()` accepts one ID or a list (max 100):

```python
client.cases.delete(ids=case_id)
client.cases.delete(ids=["case-1", "case-2"])
```

## Space-Scoped Cases

All operations accept `space_id`, or use a space-scoped client:

```python
case = client.cases.create(
    title="Marketing incident",
    description="...",
    space_id="marketing",
)

marketing = client.space("marketing")
found = marketing.cases.find(status="open")
```

## Complete Example: Case Lifecycle

```python
from kibana import Kibana

with Kibana("http://localhost:5601", api_key="your_api_key") as client:
    # Open a case
    case = client.cases.create(
        title="kbnpy demo case",
        description="Created by kibana-py.",
        tags=["demo"],
        severity="medium",
    )
    case_id = case.body["id"]

    try:
        # Work the case
        client.cases.add_comment(case_id=case_id, comment="Looking into it.")

        current = client.cases.get(case_id=case_id)
        client.cases.update(
            id=case_id,
            version=current.body["version"],
            status="in-progress",
        )

        # Resolve it
        current = client.cases.get(case_id=case_id)
        client.cases.update(
            id=case_id,
            version=current.body["version"],
            status="closed",
        )
    finally:
        client.cases.delete(ids=case_id)
```

## Next Steps

- Configure [Connectors](connectors.md) to push cases to external systems
- Combine cases with [Alerting](alerting.md) to track alert investigations
- Browse `examples/cases_management.py` in the repository for a runnable end-to-end script
