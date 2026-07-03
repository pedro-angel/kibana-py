# Platform APIs

Beyond the headline namespaces covered in their own guides ([Dashboards](dashboards.md), [Alerting](alerting.md), [Data Views](data-views.md), [Cases](cases.md), [Connectors](connectors.md), [Spaces](spaces.md), [Saved Objects](saved-objects.md), [Status](status-monitoring.md)), kibana-py covers the rest of the Kibana 9.4 platform API surface. This page gives a quick tour of each namespace with short, real examples.

Unless noted otherwise, all methods accept `space_id` (and `validate_spaces`) for space-scoped operation, and every namespace exists identically on `AsyncKibana`. Each namespace also has a runnable end-to-end script in the repository's `examples/` directory (`examples/<namespace>_management.py`).

## Security

Manage Kibana roles (including their Elasticsearch and Kibana privilege definitions) and invalidate user sessions. Not space-scoped — space access is granted *through* a role's `kibana` privilege entries.

```python
client.security.create_or_update_role(
    name="logs-reader",
    elasticsearch={"cluster": ["monitor"],
                   "indices": [{"names": ["logs-*"], "privileges": ["read"]}]},
    kibana=[{"base": ["read"], "spaces": ["default"]}],
)
role = client.security.get_role(name="logs-reader")
client.security.delete_role(name="logs-reader")
```

Also available: `get_all_roles()`, `bulk_create_or_update_roles(roles=...)`, `query_roles(query=..., from_=..., size=...)`, and `invalidate_sessions(match=..., query=...)`.

## Short URLs

Create short, shareable URLs backed by a locator (technical preview). Space-scoped.

```python
created = client.short_urls.create(
    locator_id="LEGACY_SHORT_URL_LOCATOR",
    params={"url": "/app/dashboards"},
    human_readable_slug=True,
)
resolved = client.short_urls.resolve(slug=created.body["slug"])
client.short_urls.delete(id=resolved.body["id"])
```

Note: on live 9.4.3, `accessDate`/`createDate` come back as epoch milliseconds (the spec says strings), and `delete()` returns HTTP 200 with a JSON `null` body.

## SLOs

Define Service Level Objectives over Elasticsearch data and track error budgets. Requires a Platinum (or trial) license.

```python
slo = client.slos.create(
    name="my-service availability",
    description="99% of requests are good over 30 days",
    indicator={"type": "sli.kql.custom",
               "params": {"index": "my-service-logs", "good": "status: ok",
                          "total": "", "timestampField": "@timestamp"}},
    time_window={"duration": "30d", "type": "rolling"},
    budgeting_method="occurrences",
    objective={"target": 0.99},
)
client.slos.find(kql_query='slo.name: "my-service*"')
client.slos.delete(slo_id=slo.body["id"])
```

Also available: `enable()` / `disable()` / `reset()`, `bulk_delete(slo_ids=...)` (+ `bulk_delete_status(task_id=...)`), `delete_instances(instances=...)`, `bulk_purge_rollup(slo_ids=..., purge_policy=...)` (note: live Kibana requires `purge_type` values `"fixed_age"`/`"fixed_time"` in snake_case), and `find_definitions()`.

## Synthetics

Manage synthetic monitors (HTTP, TCP, ICMP, browser), global parameters, and private locations, and trigger on-demand test runs. Creating a monitor requires at least one location — private locations are backed by a Fleet agent policy.

```python
loc = client.synthetics.create_private_location(
    label="My private location", agent_policy_id="abc-123",
)
monitor = client.synthetics.create_monitor(
    type="http", name="Example check", url="https://example.com",
    private_locations=[loc.body["id"]], schedule=10,
)
client.synthetics.get_monitors(query="Example*")
client.synthetics.delete_monitor(id=monitor.body["id"])
```

Also available: `test_monitor(monitor_id=...)`, parameter CRUD (`create_param(key=..., value=...)`, `get_params()`, `update_param(id=...)`, ...) and private location CRUD. Note: parameter *values* are write-only through the public API on 9.4.3 (reads never return `value`), and `get_monitors(sort_field=...)` accepts live values such as `"name.keyword"` / `"updated_at"` rather than the documented enum.

## Uptime

Read and update the Uptime app settings (Heartbeat indices, certificate alerting thresholds, default connectors). Space-scoped; updates are partial.

```python
settings = client.uptime.get_settings()
print(settings.body["heartbeatIndices"])

updated = client.uptime.update_settings(cert_age_threshold=365)
print(updated.body["certAgeThreshold"])
```

## Streams

Manage wired log streams: routing, processing pipelines, field mappings, significant-events queries, and linked attachments (technical preview). Streams must be enabled first; the 9.4 wired roots are `logs.ecs` and `logs.otel`.

```python
client.streams.enable()
client.streams.fork(
    name="logs.ecs", stream_name="logs.ecs.myapp",
    where={"field": "service.name", "eq": "myapp"},
)
streams = client.streams.get_all()
print([s["name"] for s in streams.body["streams"]])
client.streams.delete(name="logs.ecs.myapp")
```

Also available: `get_ingest()` / `update_ingest()` (strip the read-only `processing.updated_at` field before writing back), query management (`upsert_query()`, `bulk_queries()`), significant events (`get_significant_events(from_=..., to=...)` — ISO 8601 timestamps only, no `now-24h` date math), content export/import (`export_content()` returns a ZIP as bytes), and dashboard/rule/SLO attachment linking.

## Workflows

Automate multi-step processes defined in YAML (GA since 9.4.0): create workflows, run them, and inspect executions, steps, and logs.

```python
created = client.workflows.create(yaml="""
name: my-workflow
enabled: true
triggers:
  - type: manual
steps:
  - name: log_step
    type: console
    with:
      message: "hello world"
""")
run = client.workflows.run(id=created.body["id"], inputs={})
execution = client.workflows.get_execution(execution_id=run.body["workflowExecutionId"])
logs = client.workflows.get_execution_logs(execution_id=run.body["workflowExecutionId"])
client.workflows.delete(id=created.body["id"])
```

Also available: `get_all()`, `update()`, `clone()` (new ID is `<id>-copy`), `bulk_create()` / `bulk_delete()`, `test()` / `test_step()` (dry runs), `get_executions()`, `cancel_execution()` / `resume_execution()`, `export()`, `get_schema()`, and `get_stats()`. Note: execution logs are indexed asynchronously — poll `get_execution_logs()` for a few seconds after an execution completes.

## Agent Builder

Create and manage AI agents, tools, and skills; chat with agents (with conversation persistence and attachments); and expose agents over the A2A and MCP protocols. Chat operations require a configured LLM connector.

```python
client.agent_builder.create_tool(
    id="my_ns.lookup", type="esql", description="Look up documents",
    configuration={"query": "FROM my-index | LIMIT 10", "params": {}},
)
client.agent_builder.create_agent(
    id="my-agent", name="My Agent", description="Searches my data",
    configuration={"tools": [{"tool_ids": ["my_ns.lookup"]}]},
)
reply = client.agent_builder.converse(input="What data do I have?", agent_id="my-agent")
print(reply.body["response"]["message"])
```

Also available: conversation and attachment management (`list_conversations()`, `create_attachment()`, ...), `execute_tool(tool_id=..., tool_params=...)`, `converse_async()` (server-sent events), `get_a2a_card()` / `send_a2a_task()`, `send_mcp_request()`, and skills CRUD. Note: the plugins routes (`list_plugins()`, ...) are documented in the 9.4.3 spec but not enabled on a default install (they return 404).

## APM

Manage APM agent keys, service annotations, agent configurations, and RUM source maps.

```python
client.apm.create_or_update_agent_configuration(
    service_name="opbeans-node", service_environment="production",
    settings={"transaction_sample_rate": "0.5"},
)
for c in client.apm.get_agent_configurations().body["configurations"]:
    print(c["service"], c["settings"])

client.apm.create_annotation(
    service_name="opbeans-node", timestamp="2026-07-03T00:00:00.000Z",
    service_version="1.2.3", message="Deployed 1.2.3",
)
```

Also available: `search_annotations(service_name=..., environment=..., start=..., end=...)` (the live server requires all three query params despite the spec marking them optional), `create_agent_key(name=..., privileges=...)`, `upload_sourcemap()` / `get_sourcemaps()` / `delete_sourcemap()`, and `save_server_schema()`.

## Maintenance Windows

Suppress rule notifications for scheduled periods — alerts are still created, but their actions do not run while a window is active. Requires Platinum+.

```python
created = client.maintenance_windows.create(
    title="Weekend maintenance",
    schedule={"custom": {"start": "2026-07-05T00:00:00.000Z", "duration": "2h"}},
)
mw_id = created.body["id"]
client.maintenance_windows.find(status="upcoming")
client.maintenance_windows.archive(id=mw_id)
client.maintenance_windows.delete(id=mw_id)
```

Also available: `get()`, `update()`, `unarchive()`. Note: windows with far-future start dates can report status `"finished"` due to the server's limited event-materialization horizon — prefer near-future starts.

## Machine Learning

Keep Kibana ML saved objects in sync with Elasticsearch ML jobs and trained models, and manage which spaces they belong to.

```python
# Simulate first to see what would change
result = client.ml.sync(simulate=True)
print(result.body["savedObjectsCreated"])

client.ml.update_jobs_spaces(
    job_ids=["my-job"], job_type="anomaly-detector",
    spaces_to_add=["marketing"], spaces_to_remove=[],
)
```

Also available: `update_trained_models_spaces(model_ids=..., spaces_to_add=..., spaces_to_remove=...)`. Per-item failures (unknown IDs) come back inside an HTTP 200 body as `{"success": false, "error": ...}` — check the response body.

## Logstash

Centrally manage Logstash pipeline definitions stored in Elasticsearch (technical preview, not space-scoped). Requires the `logstash_admin` role.

```python
client.logstash.create_or_update(
    id="hello-world",
    pipeline="input { stdin {} } output { stdout {} }",
    description="Just a simple pipeline",
    settings={"queue.type": "persisted"},
)
for p in client.logstash.get_all().body["pipelines"]:
    print(p["id"])
client.logstash.delete(id="hello-world")
```

## Task Manager

Inspect the health of Kibana's background-task runner (rules, actions, reporting, telemetry). Instance-level, not space-scoped.

```python
health = client.task_manager.health()
print(health.body["status"])
print(health.body["stats"]["capacity_estimation"]["status"])
```

## Upgrade Assistant

Check whether the cluster is ready for a major-version upgrade (technical preview, not space-scoped).

```python
status = client.upgrade_assistant.status()
print(status.body["readyForUpgrade"], "-", status.body["details"])
```

The live 9.4.3 response shape is `{readyForUpgrade, details, recentEsDeprecationLogs, kibanaApiDeprecations}` (the spec's example shows an older shape).

## Observability AI Assistant

Generate LLM chat completions with the Observability AI Assistant (technical preview). Requires a preconfigured AI connector; the response is a raw server-sent-event byte stream, not parsed JSON.

```python
response = client.observability_ai_assistant.chat_complete(
    connector_id="my-openai-connector",
    persist=False,
    messages=[{
        "@timestamp": "2026-07-03T00:00:00.000Z",
        "message": {"role": "user", "content": "Is my cluster healthy?"},
    }],
)
print(response.body)  # b'data: {...}\n\n... data: [DONE]'
```

:::{note}
LLM/connector failures are delivered *inside* the HTTP 200 stream as a `data: {"error": ...}` chunk — parse the stream rather than relying on the status code.
:::

## Next Steps

- Every namespace has full docstrings — see the [API Reference](../api-reference/index.rst) or use `help(client.<namespace>)`
- Runnable per-namespace scripts live in the repository's `examples/` directory
- See [Error Handling](error-handling.md) for the exception hierarchy shared by all namespaces
