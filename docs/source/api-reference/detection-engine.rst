DetectionEngineClient
=====================

Client for the Kibana Security Detections API.

The detection engine powers Elastic Security: detection rules run over your
data and create detection alerts (historically called *signals*). This client
manages detection rules (CRUD, find, bulk actions, preview, NDJSON
export/import, Elastic prebuilt rules), detection alerts (search, workflow
status, tags, assignees, legacy signals migrations) and the per-space alerts
index.

Detection rules and alerts are space-scoped resources: a rule created in one
space is not visible from another space. Every method accepts an optional
``space_id`` to target a specific space.

.. note::

   The rule-exceptions endpoint
   (``POST /api/detection_engine/rules/{id}/exceptions``) is exposed on the
   ``exception_lists`` namespace.

.. currentmodule:: kibana._sync.client.detection_engine

.. autoclass:: DetectionEngineClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Managing Detection Rules

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a custom query rule (disabled)
      rule = client.detection_engine.create_rule(
          type="query",
          name="Suspicious login",
          description="Detects suspicious logins",
          severity="low",
          risk_score=21,
          query='user.name: "suspicious"',
          index=["logs-*"],
          interval="5m",
          from_="now-6m",
          enabled=False,
      )

      # Read, patch and find rules
      fetched = client.detection_engine.get_rule(rule_id=rule.body["rule_id"])
      client.detection_engine.patch_rule(
          rule_id=rule.body["rule_id"], tags=["triage"]
      )
      found = client.detection_engine.find_rules(
          filter='alert.attributes.tags: "triage"', per_page=50
      )

      # Full update -- also how you toggle `enabled` on 9.4.3
      client.detection_engine.update_rule(
          rule_id=rule.body["rule_id"],
          type="query",
          name="Suspicious login",
          description="Detects suspicious logins",
          severity="medium",
          risk_score=47,
          query='user.name: "suspicious"',
          enabled=True,
      )

      # Delete it
      client.detection_engine.delete_rule(rule_id=rule.body["rule_id"])

   .. rubric:: Bulk Actions, Export and Import

   .. code-block:: python

      # Add a tag to many rules at once
      client.detection_engine.bulk_action_rules(
          action="edit",
          query='alert.attributes.tags: "triage"',
          edit=[{"type": "add_tags", "value": ["reviewed"]}],
      )

      # Export rules as NDJSON and import them back
      exported = client.detection_engine.export_rules(
          objects=[{"rule_id": "my-rule"}], exclude_export_details=True
      )
      client.detection_engine.import_rules(file=list(exported), overwrite=True)

      # Install the Elastic prebuilt rules and Timeline templates
      status = client.detection_engine.get_prepackaged_rules_status()
      if status.body["rules_not_installed"]:
          client.detection_engine.install_prepackaged_rules()

   .. rubric:: Previewing Rules

   Preview the alerts a rule would generate without creating it:

   .. code-block:: python

      preview = client.detection_engine.preview_rule(
          type="query",
          name="Preview",
          description="Preview run",
          severity="low",
          risk_score=21,
          query='user.name: "suspicious"',
          index=["logs-*"],
          invocation_count=1,
          timeframe_end="2026-07-06T12:00:00.000Z",
          from_="now-6h",
          interval="1h",
      )
      print(preview.body["previewId"], preview.body["logs"])

   .. rubric:: Working with Detection Alerts

   .. code-block:: python

      # Search open alerts
      alerts = client.detection_engine.search_alerts(
          query={
              "bool": {
                  "filter": [
                      {"match": {"kibana.alert.workflow_status": "open"}}
                  ]
              }
          },
          size=10,
      )

      # Close alerts, tag them, assign them
      alert_ids = [hit["_id"] for hit in alerts.body["hits"]["hits"]]
      if alert_ids:
          client.detection_engine.set_alert_status(
              status="closed", signal_ids=alert_ids
          )
          client.detection_engine.set_alert_tags(
              ids=alert_ids, tags_to_add=["triaged"], tags_to_remove=[]
          )
          client.detection_engine.set_alert_assignees(
              ids=alert_ids, add=["u_profile_uid"], remove=[]
          )

AsyncDetectionEngineClient
--------------------------

Asynchronous version of the DetectionEngineClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.detection_engine.AsyncDetectionEngineClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncDetectionEngineClient provides the same methods as
   DetectionEngineClient but all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              rule = await client.detection_engine.create_rule(
                  type="query",
                  name="Async rule",
                  description="Created asynchronously",
                  severity="low",
                  risk_score=21,
                  query='user.name: "suspicious"',
                  enabled=False,
              )

              found = await client.detection_engine.find_rules(
                  filter='alert.attributes.name: "Async rule"'
              )

              await client.detection_engine.delete_rule(
                  rule_id=rule.body["rule_id"]
              )

      asyncio.run(main())
