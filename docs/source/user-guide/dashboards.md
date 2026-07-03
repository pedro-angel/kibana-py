# Dashboards

Kibana 9.4 introduces a first-class **Dashboards HTTP API** (technical preview) that lets you manage dashboards as code: create, read, search, upsert, and delete dashboards by ID, with a clean, flat data model instead of raw saved-object payloads. kibana-py exposes it as `client.dashboards`, and it is the recommended way to manage dashboards programmatically.

:::{warning}
The Dashboards API is in **technical preview** in Kibana 9.4 and may change in future releases. It replaces the deprecated `/api/saved_objects` CRUD routes for dashboard management (see [Saved Objects](saved-objects.md)).
:::

## Overview

With `client.dashboards` you can:

- Create dashboards with panels (markdown, Lens visualizations, images, and more)
- Retrieve a dashboard's full panel layout by ID
- Search dashboards by title/description and filter by tags
- Upsert dashboards with custom IDs for reproducible, GitOps-style provisioning
- Delete dashboards
- Scope every operation to a Kibana space

## The Response Envelope

Every Dashboards API response wraps the dashboard in an `{id, data, meta}` envelope:

```python
{
    "id": "d3f0c1a2-...",       # The dashboard ID
    "data": {                    # The dashboard definition (what you send)
        "title": "Team Overview",
        "description": "",
        "panels": [...],
        "options": {...},
        "tags": [],
        ...
    },
    "meta": {                    # Server-managed metadata (read-only)
        "created_at": "2026-07-03T10:00:00.000Z",
        "updated_at": "2026-07-03T10:00:00.000Z",
        "created_by": "u_...",
        "managed": False,
        "version": "WzEyMyw0XQ=="
    }
}
```

- **`data`** is the dashboard definition — the same shape you pass to `create()` and `update()`.
- **`meta`** carries server-managed fields you cannot write: timestamps, author, whether the dashboard is `managed` by Elastic, and a `version` token that changes on every write (useful for optimistic concurrency).

:::{note}
The server fills unspecified `data` fields with defaults in responses: a dashboard created with only a `title` comes back with `description: ""`, `panels: []`, `tags: []`, `filters: []`, and a fully populated `options` object. The echoed `data` is a superset of what you sent.
:::

## Creating Dashboards

### A Dashboard with a Markdown Panel

`create()` assigns a server-generated ID and returns the created dashboard:

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your_api_key")

markdown_panel = {
    "type": "markdown",
    "grid": {"x": 0, "y": 0, "w": 24, "h": 15},
    "config": {
        "title": "Notes",
        "content": "# Welcome\nCreated by kibana-py.",
        "settings": {"open_links_in_new_tab": True},
    },
}

dashboard = client.dashboards.create(
    title="Team Overview",
    description="Ops team landing dashboard",
    panels=[markdown_panel],
    tags=["ops-tag-id"],
    time_range={"from": "now-7d", "to": "now"},
    options={"hide_panel_titles": True},
)

dashboard_id = dashboard.body["id"]
print(f"Created dashboard: {dashboard_id}")

client.close()
```

### The Panel Model

Each entry in `panels` is a dict with three parts:

| Key | Description |
|--------|-------------|
| `type` | The panel type: `"markdown"`, `"vis"` (Lens visualization), `"image"`, `"discover_session"`, control panels, SLO/synthetics/APM embeddables, and more |
| `grid` | Placement on the 48-column grid: `x` and `y` are required; `w` (width, max 48, default 24) and `h` (height, default 15) are optional |
| `config` | Type-specific configuration — either inline ("by value") or `{"ref_id": ...}` to reference a library item ("by reference") |

Panels can also be grouped into collapsible **sections**: a section is a dict with a `title`, a `collapsed` flag, and nested `panels`.

### Other Dashboard Fields

`create()` and `update()` accept the full dashboard data model as keyword arguments:

- `query` — a search query applied to the dashboard, e.g. `{"expression": "status:active", "language": "kql"}` (language is `"kql"` or `"lucene"`)
- `filters` — filters applied across all panels
- `time_range` — `{"from": "now-7d", "to": "now"}`, accepting date math or ISO 8601 timestamps
- `refresh_interval` — auto-refresh setting `{"pause": bool, "value": milliseconds}`
- `options` — display settings such as `hide_panel_titles`, `use_margins`, `sync_colors`, `sync_cursor`, `sync_tooltips`, `auto_apply_filters`, `hide_panel_borders`
- `tags` — a list of tag IDs (max 100)
- `pinned_panels` — control panels and their state in the control group
- `access_control` — `{"access_mode": "default" | "write_restricted"}`; **only settable at creation time** (see below)

:::{note}
`create()` rejects an `id` in the body — the server always assigns one. To choose your own ID, use `update()`, which upserts (see [Custom IDs via Upsert](#custom-ids-via-upsert)).
:::

## Getting a Dashboard

`get()` returns the full dashboard, including the complete panel layout:

```python
dashboard = client.dashboards.get(id=dashboard_id)

data = dashboard.body["data"]
print(f"Title: {data['title']}")
for panel in data["panels"]:
    print(f"  - {panel['type']} at {panel['grid']}")

meta = dashboard.body["meta"]
print(f"Created: {meta['created_at']}, managed: {meta['managed']}")
```

A missing dashboard raises `NotFoundError`.

## Searching Dashboards

`get_all()` returns a paginated list. Search entries contain summary fields (`title`, `description`, `tags`, `time_range`, `access_control`) but **not** the full panel layout — use `get()` for that:

```python
# Search by title/description (simple_query_string syntax)
results = client.dashboards.get_all(query="Team*")
print(f"Total matches: {results.body['total']}")
for item in results.body["dashboards"]:
    print(f"  {item['id']}: {item['data']['title']}")

# Filter by tags (dashboards matching ANY of the tag IDs)
results = client.dashboards.get_all(tags=["ops-tag-id"])

# Exclude tags
results = client.dashboards.get_all(query="Team*", excluded_tags=["archived-tag-id"])

# Pagination
page1 = client.dashboards.get_all(query="Team*", per_page=10, page=1)
page2 = client.dashboards.get_all(query="Team*", per_page=10, page=2)
```

The response body is `{"dashboards": [...], "page": n, "total": n}`, where each entry is an `{id, data, meta}` envelope.

:::{note}
Tag filters match tag IDs as opaque strings — the server does not validate that the tag IDs exist, on reads or writes.
:::

## Updating Dashboards (Upsert)

`update()` calls `PUT /api/dashboards/{id}`, which is an **upsert**:

- If the dashboard exists, it is **replaced** with the provided data (HTTP 200).
- If it does not exist, it is **created** with the given ID (HTTP 201).

```python
updated = client.dashboards.update(
    id=dashboard_id,
    title="Team Overview v2",
    description="Updated by kibana-py",
    panels=[markdown_panel],
    time_range={"from": "now-24h", "to": "now"},
)
```

:::{warning}
**`update()` is a full replace, not a partial update.** The provided data replaces the entire stored dashboard: fields omitted from the call revert to their defaults. If you update only the `title`, all panels are removed. To make a targeted change, `get()` the dashboard first, modify the `data` dict, and pass the full definition back:

```python
current = client.dashboards.get(id=dashboard_id).body["data"]

client.dashboards.update(
    id=dashboard_id,
    title="New title",
    description=current.get("description"),
    panels=current.get("panels"),
    options=current.get("options"),
    tags=current.get("tags"),
    time_range=current.get("time_range"),
)
```
:::

(custom-ids-via-upsert)=
### Custom IDs via Upsert

Because `create()` always assigns a server-generated ID, `update()` with a fresh ID is *the* way to create a dashboard with a custom, stable ID — ideal for dashboards managed in version control:

```python
# Creates the dashboard if "team-overview" doesn't exist (HTTP 201)
dashboard = client.dashboards.update(
    id="team-overview",
    title="Team Overview",
    panels=[markdown_panel],
)
print(dashboard.meta.status)  # 201 on create, 200 on replace

# Re-running the same call replaces it idempotently (HTTP 200)
```

## Deleting Dashboards

```python
response = client.dashboards.delete(id="team-overview")
print(response.meta.status)  # 204, empty body
```

Deleting a missing dashboard raises `NotFoundError`.

## Space-Scoped Dashboards

Dashboards are space-scoped: a dashboard created in one space is not visible from another. Every method accepts `space_id`, or you can use a space-scoped client:

```python
# Per-call space targeting
dashboard = client.dashboards.create(
    title="Marketing KPIs",
    space_id="marketing",
)
dashboard = client.dashboards.get(id=dashboard.body["id"], space_id="marketing")

# Or scope the whole client to a space
marketing = client.space("marketing")
results = marketing.dashboards.get_all(query="KPIs*")
```

See [Spaces](spaces.md) for details on space management.

## Access Control

The `access_control` field restricts who can edit a dashboard:

```python
dashboard = client.dashboards.create(
    title="Locked dashboard",
    access_control={"access_mode": "write_restricted"},
)
```

Two caveats:

- `access_control` is **create-only**: `update()` does not accept it, and the server rejects it in a PUT body with a 400 error.
- Setting it requires an identifiable user profile. Under plain basic authentication the server responds 400 ("Kibana could not determine the user profile ID for the caller") — use an API key or a real user session.

## Live Server Behavior (Kibana 9.4.3)

kibana-py is tested against a live Kibana 9.4.3 stack. A few observed behaviors to be aware of:

- **`time_range.mode` is dropped.** The API schema accepts `{"from", "to", "mode"}` (mode: `"absolute"` or `"relative"`), but the server persists only `from`/`to` — don't expect `mode` to round-trip on reads.
- **Status codes:** `create()` returns HTTP 201; `update()` returns 200 on replace and 201 on create-via-upsert; `delete()` returns 204 with an empty body. Check `response.meta.status` if you need to distinguish upsert outcomes.
- **Defaults are filled in.** Responses echo a `data` object that is a superset of what you sent (empty `description`, default `options`, empty lists).
- **`meta.version` changes on every write** — treat it as an opaque optimistic-concurrency token.
- **Tag IDs are not validated** on create/update; arbitrary strings are accepted and matched verbatim by search filters.

## Async Usage

The async client mirrors the sync API exactly:

```python
import asyncio
from kibana import AsyncKibana

async def main():
    async with AsyncKibana("http://localhost:5601", api_key="your_api_key") as client:
        created = await client.dashboards.create(
            title="Async dashboard",
            panels=[
                {
                    "type": "markdown",
                    "grid": {"x": 0, "y": 0, "w": 48, "h": 6},
                    "config": {"content": "async markdown", "settings": {}},
                }
            ],
        )
        dashboard_id = created.body["id"]

        results = await client.dashboards.get_all(query="Async*")
        print(results.body["total"])

        await client.dashboards.delete(id=dashboard_id)

asyncio.run(main())
```

## Complete Example: Dashboard Lifecycle

```python
from kibana import Kibana
from kibana.exceptions import NotFoundError

with Kibana("http://localhost:5601", api_key="your_api_key") as client:
    # Upsert a dashboard with a stable ID
    client.dashboards.update(
        id="service-health",
        title="Service Health",
        description="Managed by kibana-py",
        panels=[
            {
                "type": "markdown",
                "grid": {"x": 0, "y": 0, "w": 48, "h": 6},
                "config": {
                    "content": "## Runbook\n- [Escalation policy](https://example.com)",
                    "settings": {"open_links_in_new_tab": True},
                },
            }
        ],
        time_range={"from": "now-24h", "to": "now"},
    )

    # Verify it round-trips
    dashboard = client.dashboards.get(id="service-health")
    assert dashboard.body["data"]["title"] == "Service Health"

    # Find it by title
    results = client.dashboards.get_all(query="Service*")
    assert any(d["id"] == "service-health" for d in results.body["dashboards"])

    # Clean up
    try:
        client.dashboards.delete(id="service-health")
    except NotFoundError:
        pass
```

## Visualizations API

Kibana 9.4 also ships a companion **Visualizations HTTP API** (technical preview) for managing Lens visualizations, exposed as `client.visualizations`. It uses the same `{id, data, meta}` envelope as the Dashboards API.

Supported chart types include `metric`, `xy`, `pie`, `gauge`, `heatmap`, `tagcloud`, `regionmap`, `datatable`, `mosaic`, `treemap`, and `waffle`.

```python
# Create a metric visualization
created = client.visualizations.create(
    data={
        "type": "metric",
        "title": "Total log documents",
        "data_source": {
            "type": "data_view_spec",
            "index_pattern": "logs-*",
        },
        "query": {"expression": "", "language": "kql"},
        "metrics": [{"type": "primary", "operation": "count"}],
    }
)
viz_id = created.body["id"]

# Read it back
viz = client.visualizations.get(id=viz_id)
print(viz.body["data"]["title"])

# Update is a full replace and upserts on a fresh ID (HTTP 201), like dashboards
client.visualizations.update(
    id=viz_id,
    data={
        "type": "metric",
        "title": "Total log documents (renamed)",
        "data_source": {"type": "data_view_spec", "index_pattern": "logs-*"},
        "query": {"expression": "", "language": "kql"},
        "metrics": [{"type": "primary", "operation": "count"}],
    },
)

# Search by title
results = client.visualizations.get_all(query="Total log*")
print(results.body["meta"]["total"])

# Delete (HTTP 204)
client.visualizations.delete(id=viz_id)
```

:::{warning}
On live Kibana 9.4.3 the `search_fields` and `fields` query parameters of `client.visualizations.get_all()` trigger server-side `500 Internal Server Error` responses (a bug in the tech-preview API). Prefer the `query` parameter alone until this is fixed upstream. Also note that the created `data` echoed back is *normalized*: the server fills defaults (sampling, styling, `data_source.time_field`) and does not echo the request `query` filter verbatim.
:::

## Next Steps

- Learn about [Spaces](spaces.md) for multi-tenant dashboard management
- See [Saved Objects](saved-objects.md) for import/export of dashboards across instances
- Check [Error Handling](error-handling.md) for exception patterns
- Browse `examples/dashboards_management.py` and `examples/visualizations_management.py` in the repository for runnable end-to-end scripts
