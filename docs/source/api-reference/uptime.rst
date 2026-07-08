UptimeClient
============

Client for the Kibana Uptime API.

The Uptime app in Kibana uses Heartbeat data to monitor the availability of
services. The Uptime settings API lets you read and update the app-wide
settings: the Heartbeat index pattern used to query monitoring data, TLS
certificate alerting thresholds, and default alert connectors and email
recipients.

Uptime settings are space-scoped: each Kibana space keeps its own settings
document. Every method accepts an optional ``space_id`` to target a specific
space.

Reading the settings requires ``read`` privileges for the uptime feature in
the Observability section of the Kibana feature privileges; updating them
requires ``all`` privileges.

.. currentmodule:: kibana._sync.client.uptime

.. autoclass:: UptimeClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Reading Settings

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      settings = client.uptime.get_settings()
      print(settings.body["heartbeatIndices"])
      print(settings.body["certAgeThreshold"])
      print(settings.body["certExpirationThreshold"])

   .. rubric:: Updating Settings

   Updates are partial: only the settings you pass are changed, other keys
   are preserved:

   .. code-block:: python

      # Update a single setting
      updated = client.uptime.update_settings(cert_age_threshold=365)
      print(updated.body["certAgeThreshold"])

      # Update several settings at once
      updated = client.uptime.update_settings(
          heartbeat_indices="heartbeat-*",
          cert_expiration_threshold=30,
          default_connectors=["my-connector-id"],
      )

AsyncUptimeClient
-----------------

Asynchronous version of the UptimeClient for use with async/await syntax.

.. autoclass:: kibana._async.client.uptime.AsyncUptimeClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncUptimeClient provides the same methods as UptimeClient but all
   methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Read settings (async)
              settings = await client.uptime.get_settings()

              # Update settings (async)
              await client.uptime.update_settings(cert_age_threshold=365)

      asyncio.run(main())
