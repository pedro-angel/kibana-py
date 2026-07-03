# Data Views

Data views (formerly *index patterns*) tell Kibana which Elasticsearch indices, data streams, and aliases to query. kibana-py exposes the full Data Views API as `client.data_views`: data view CRUD, runtime field management, field metadata, the default data view, and saved-object reference swapping.

## Creating Data Views

A data view needs a `title` — a comma-separated list of index patterns to search:

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your_api_key")

response = client.data_views.create(
    data_view={
        "title": "my-logs-*",
        "name": "My Logs",
        "timeFieldName": "@timestamp",
    }
)

view_id = response.body["data_view"]["id"]
print(f"Created data view: {view_id}")
```

Optional `data_view` keys include `id` (choose your own), `allowNoIndex`, `fieldFormats`, `runtimeFieldMap`, `sourceFilters`, `namespaces`, `type`, and `typeMeta`. Pass `override=True` to replace an existing data view with the same title.

:::{note}
Creating the *first* data view in a space implicitly makes it the default data view for that space (an undocumented Kibana behavior).
:::

## Reading, Listing, Updating, Deleting

```python
# List all data views in the space (summary fields only)
views = client.data_views.get_all()
for view in views.body["data_view"]:
    print(view["id"], view["title"])

# Get one data view, including its fields
view = client.data_views.get(view_id=view_id)
print(view.body["data_view"]["title"])

# Partial update: only the provided properties change
client.data_views.update(
    view_id=view_id,
    data_view={"name": "Renamed view"},
    refresh_fields=True,   # reload fields after the update
)

# Delete (cannot be recovered)
client.data_views.delete(view_id=view_id)
```

:::{tip}
Unlike the tech-preview Dashboards API, `data_views.update()` is a **partial** update — omitted properties keep their current values.
:::

## Runtime Fields

Runtime fields are computed at query time from a Painless script — no reindexing required. kibana-py covers the full runtime field lifecycle:

```python
# Create a runtime field
client.data_views.create_runtime_field(
    view_id=view_id,
    name="hour_of_day",
    runtime_field={
        "type": "long",
        "script": {
            "source": "emit(doc['@timestamp'].value.getHour())"
        },
    },
)

# Read it back
field = client.data_views.get_runtime_field(view_id=view_id, name="hour_of_day")

# Update the script
client.data_views.update_runtime_field(
    view_id=view_id,
    name="hour_of_day",
    runtime_field={
        "script": {
            "source": "emit(doc['@timestamp'].value.getHour() + 1)"
        },
    },
)

# Upsert (create or replace)
client.data_views.create_or_update_runtime_field(
    view_id=view_id,
    name="day_of_week",
    runtime_field={
        "type": "keyword",
        "script": {
            "source": "emit(doc['@timestamp'].value.getDayOfWeekEnum().toString())"
        },
    },
)

# Delete
client.data_views.delete_runtime_field(view_id=view_id, name="hour_of_day")
```

Runtime field responses include both the affected `fields` and the updated `data_view` object.

## Field Metadata

Customize how fields are presented in Kibana (labels, descriptions, popularity, formats):

```python
client.data_views.update_fields_metadata(
    view_id=view_id,
    fields={
        "response_code": {"customLabel": "Status"},
        "bytes": {"count": 5},  # boost popularity in field lists
    },
)
```

:::{note}
The 9.4.3 API spec documents the response as `{"acknowledged": true}`, but the live server returns the full updated `data_view` object.
:::

## The Default Data View

```python
# Get the default data view ID for the space
default = client.data_views.get_default()
print(default.body["data_view_id"])

# Set the default (force=True overrides an existing default)
client.data_views.set_default(data_view_id=view_id, force=True)
```

:::{note}
When no default is set, the live server returns `{"data_view_id": ""}` (an empty string). Also, the stored default is not validated — it can point at an already-deleted data view.
:::

## Swapping Saved Object References

When replacing one data view with another (for example after a migration), you can rewrite references in saved objects that point at the old view:

```python
# Preview what would change (no writes)
preview = client.data_views.preview_swap_references(
    from_id="old-view-id",
    to_id="new-view-id",
)
print(preview.body["result"])

# Perform the swap, optionally deleting the old data view afterwards
client.data_views.swap_references(
    from_id="old-view-id",
    to_id="new-view-id",
    delete=True,
)
```

Both methods accept optional filters: `from_type`, `for_id`, and `for_type` limit which referencing objects are rewritten.

## Space-Scoped Data Views

All operations accept `space_id`, or use a space-scoped client:

```python
response = client.data_views.create(
    data_view={"title": "marketing-*", "timeFieldName": "@timestamp"},
    space_id="marketing",
)

marketing = client.space("marketing")
views = marketing.data_views.get_all()
```

## Complete Example

```python
from kibana import Kibana
from kibana.exceptions import NotFoundError

with Kibana("http://localhost:5601", api_key="your_api_key") as client:
    created = client.data_views.create(
        data_view={
            "title": "kbnpy-demo-*",
            "name": "kibana-py demo",
            "timeFieldName": "@timestamp",
            "allowNoIndex": True,   # OK if no matching index exists yet
        }
    )
    view_id = created.body["data_view"]["id"]

    try:
        client.data_views.create_runtime_field(
            view_id=view_id,
            name="hour_of_day",
            runtime_field={
                "type": "long",
                "script": {"source": "emit(doc['@timestamp'].value.getHour())"},
            },
        )

        view = client.data_views.get(view_id=view_id)
        print(f"{view.body['data_view']['name']}: "
              f"{len(view.body['data_view'].get('fields', {}))} fields")
    finally:
        try:
            client.data_views.delete(view_id=view_id)
        except NotFoundError:
            pass
```

## Next Steps

- Build [Dashboards](dashboards.md) on top of your data views
- Manage data views across [Spaces](spaces.md)
- Browse `examples/data_views_management.py` in the repository for a runnable end-to-end script
