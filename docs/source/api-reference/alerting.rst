AlertingClient
==============

Client for the Kibana Alerting API.

The Alerting API manages rules that run on schedules, detect conditions in
your data, and trigger actions (through :doc:`connectors <connectors>`) when
those conditions are met. The client exposes rule operations via
``client.alerting.rule``, backfill operations via ``client.alerting.backfill``,
and framework-level endpoints (health, rule types) directly on
``client.alerting``.

.. currentmodule:: kibana._sync.client.alerting

.. autoclass:: AlertingClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Framework Endpoints

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Alerting framework health
      health = client.alerting.health()
      print(health["alerting_framework_health"])

      # List the rule types available in this Kibana instance
      types = client.alerting.rule_types()
      for rule_type in types.body:
          print(rule_type["id"], rule_type["name"])

RulesClient
-----------

Client for Kibana Alerting rule operations, available as
``client.alerting.rule``.

Provides CRUD plus lifecycle operations (enable/disable, mute/unmute,
snooze/unsnooze, API-key rotation) for alerting rules.

.. autoclass:: RulesClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Creating Rules

   .. code-block:: python

      # Create an index threshold rule
      rule = client.alerting.rule.create(
          name="CPU Alert",
          consumer="alerts",
          rule_type_id=".index-threshold",
          schedule={"interval": "1m"},
          params={
              "index": ["logs-*"],
              "timeField": "@timestamp",
              "aggType": "count",
              "groupBy": "all",
              "threshold": [1000],
              "thresholdComparator": ">",
              "timeWindowSize": 5,
              "timeWindowUnit": "m",
          },
      )

      rule_id = rule.body["id"]

   .. rubric:: Finding and Retrieving Rules

   .. code-block:: python

      # Find rules by search term
      results = client.alerting.rule.find(search="cpu")
      for rule in results.body["data"]:
          print(rule["id"], rule["name"], rule["enabled"])

      # Get a single rule
      rule = client.alerting.rule.get(id=rule_id)

   .. rubric:: Rule Lifecycle

   .. code-block:: python

      # Disable and re-enable a rule
      client.alerting.rule.disable(id=rule_id)
      client.alerting.rule.enable(id=rule_id)

      # Mute/unmute all alerts for a rule
      client.alerting.rule.mute_all(id=rule_id)
      client.alerting.rule.unmute_all(id=rule_id)

      # Snooze notifications for one hour
      snoozed = client.alerting.rule.snooze(
          id=rule_id,
          schedule={
              "custom": {
                  "duration": "1h",
                  "start": "2026-07-03T00:00:00.000Z",
              }
          },
      )
      client.alerting.rule.unsnooze(
          rule_id=rule_id,
          schedule_id=snoozed["schedule"]["id"],
      )

      # Delete the rule
      client.alerting.rule.delete(id=rule_id)

BackfillClient
--------------

Client for Kibana Alerting backfill operations, available as
``client.alerting.backfill``.

Backfills run a rule over a historical time range. Only certain rule types
support backfills (e.g. detection rules); scheduling a backfill for an
unsupported rule type returns a per-item error in the response body.

.. autoclass:: BackfillClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Scheduling Backfills

   .. code-block:: python

      # Schedule a backfill over a historical range
      result = client.alerting.backfill.schedule(
          backfills=[
              {
                  "rule_id": "my-rule-id",
                  "ranges": [
                      {
                          "start": "2026-01-01T00:00:00.000Z",
                          "end": "2026-01-01T12:00:00.000Z",
                      }
                  ],
              }
          ]
      )

      # Find and inspect backfills
      backfills = client.alerting.backfill.find(rule_ids="my-rule-id")

Async Alerting Clients
----------------------

Asynchronous versions of the alerting clients for use with async/await
syntax. They provide the same methods as their synchronous counterparts, but
all methods are async and must be awaited:

.. code-block:: python

   from kibana import AsyncKibana
   import asyncio

   async def main():
       async with AsyncKibana("http://localhost:5601") as client:
           # Framework health (async)
           health = await client.alerting.health()

           # Create and enable a rule (async)
           rule = await client.alerting.rule.create(
               name="Async CPU Alert",
               consumer="alerts",
               rule_type_id=".index-threshold",
               schedule={"interval": "1m"},
               params={"index": ["logs-*"], "timeField": "@timestamp"},
           )
           await client.alerting.rule.disable(id=rule.body["id"])
           await client.alerting.rule.delete(id=rule.body["id"])

   asyncio.run(main())

.. autoclass:: kibana._async.client.alerting.AsyncAlertingClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

.. autoclass:: kibana._async.client.alerting.AsyncRulesClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

.. autoclass:: kibana._async.client.alerting.AsyncBackfillClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__
