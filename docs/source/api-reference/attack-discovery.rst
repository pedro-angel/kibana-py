AttackDiscoveryClient
=====================

Client for the Kibana Security Attack Discovery API.

Attack discovery analyzes security alerts with AI (through a Kibana Gen AI
connector) and surfaces potential attack chains as "Attack discoveries". The
client covers ad-hoc generation, discovery search and bulk updates,
generation-run tracking, and Attack Discovery schedules (Kibana 9.4).

Attack Discovery resources are space-scoped: every method accepts an optional
``space_id`` to target a specific space. The ``securitySolutionAttackDiscovery``
feature must be enabled in the target space -- spaces using the pure
Elasticsearch solution view disable it (there, ``find_schedules`` reports
``total: 0`` even though schedules exist). Prefer a space created with
``solution="security"``.

.. currentmodule:: kibana._sync.client.attack_discovery

.. autoclass:: AttackDiscoveryClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Generating Attack Discoveries

   Generation needs a Gen AI connector. For OpenAI-compatible backends the
   connector's ``apiUrl`` must be the full ``/chat/completions`` endpoint.
   The ``_id`` field must be allowed in the anonymization fields:

   .. code-block:: python

      import time

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      connector = client.connectors.create(
          name="My GenAI connector",
          connector_type_id=".gen-ai",
          config={
              "apiProvider": "OpenAI",
              "apiUrl": "http://localhost:1234/v1/chat/completions",
              "defaultModel": "qwen/qwen3.5-9b",
          },
          secrets={"apiKey": "dummy-key"},
      )

      started = client.attack_discovery.generate(
          alerts_index_pattern=".alerts-security.alerts-default",
          anonymization_fields=[
              {"id": "f0", "field": "_id", "allowed": True, "anonymized": False},
              {"id": "f1", "field": "host.name", "allowed": True, "anonymized": True},
              {"id": "f2", "field": "user.name", "allowed": True, "anonymized": True},
          ],
          api_config={
              "actionTypeId": ".gen-ai",
              "connectorId": connector.body["id"],
          },
          size=100,
          start="now-24h",
          end="now",
      )
      execution_uuid = started.body["execution_uuid"]

      # Poll the generation until it completes (an LLM run can take minutes)
      while True:
          generation = client.attack_discovery.get_generation(
              execution_uuid=execution_uuid
          ).body["generation"]
          if generation["status"] in ("succeeded", "failed", "canceled"):
              break
          time.sleep(10)

   .. rubric:: Searching and Updating Discoveries

   .. code-block:: python

      # Search discoveries from the last day
      found = client.attack_discovery.find(
          start="now-24h", end="now", status=["open"], per_page=25
      )
      for discovery in found.body["data"]:
          print(discovery["id"], discovery.get("title"))

      # Acknowledge them in bulk
      ids = [d["id"] for d in found.body["data"]]
      if ids:
          client.attack_discovery.bulk_update(
              ids=ids, kibana_alert_workflow_status="acknowledged"
          )

      # List generation runs; dismiss one
      generations = client.attack_discovery.get_generations(size=20)
      client.attack_discovery.dismiss_generation(execution_uuid=execution_uuid)

   .. rubric:: Managing Schedules

   Schedules run attack discovery generation periodically. Their ``params``
   carry the alerts index pattern, the LLM connector configuration and the
   maximum number of alerts:

   .. code-block:: python

      created = client.attack_discovery.create_schedule(
          name="Daily attack discovery",
          params={
              "alerts_index_pattern": ".alerts-security.alerts-default",
              "api_config": {
                  "connectorId": connector.body["id"],
                  "actionTypeId": ".gen-ai",
                  "name": "My GenAI connector",
              },
              "size": 100,
          },
          schedule={"interval": "24h"},
      )
      schedule_id = created.body["id"]

      client.attack_discovery.enable_schedule(id=schedule_id)
      client.attack_discovery.disable_schedule(id=schedule_id)

      # Full update (all properties are required)
      client.attack_discovery.update_schedule(
          id=schedule_id,
          name="Daily attack discovery (100 alerts)",
          params=created.body["params"],
          schedule={"interval": "12h"},
          actions=[],
      )

      found = client.attack_discovery.find_schedules(per_page=100)
      client.attack_discovery.delete_schedule(id=schedule_id)

AsyncAttackDiscoveryClient
--------------------------

Asynchronous version of the AttackDiscoveryClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.attack_discovery.AsyncAttackDiscoveryClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncAttackDiscoveryClient provides the same methods as
   AttackDiscoveryClient but all methods are async and must be awaited:

   .. code-block:: python

      import asyncio

      from kibana import AsyncKibana

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Kick off a generation (async)
              started = await client.attack_discovery.generate(
                  alerts_index_pattern=".alerts-security.alerts-default",
                  anonymization_fields=[
                      {"id": "f0", "field": "_id",
                       "allowed": True, "anonymized": False},
                  ],
                  api_config={
                      "actionTypeId": ".gen-ai",
                      "connectorId": "my-connector-id",
                  },
                  size=100,
              )

              # Track it (async)
              generation = await client.attack_discovery.get_generation(
                  execution_uuid=started.body["execution_uuid"]
              )

              # Search discoveries (async)
              found = await client.attack_discovery.find(
                  start="now-24h", end="now"
              )

      asyncio.run(main())
