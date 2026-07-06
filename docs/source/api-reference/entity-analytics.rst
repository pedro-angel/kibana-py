EntityAnalyticsClient
=====================

Client for the Kibana Security Entity Analytics API.

Entity Analytics surfaces risk and privilege insights for entities (hosts,
users, services and generic entities) observed by the Elastic Security
solution. The client covers asset criticality, the risk scoring engine,
privileged user monitoring (including the privileged access detection ML
package), watchlists (Technical Preview in 9.4) and the Entity Store.

All Entity Analytics resources are space-scoped: every method accepts an
optional ``space_id`` to target a specific space.

.. note::
   The asset criticality endpoints are deprecated in Kibana 9.4 in favor of
   the Entity Store entity APIs, but remain fully functional. On deployments
   where Entity Store V2 is enabled, the legacy public risk engine routes
   (``schedule_risk_engine_now``, ``configure_risk_engine_saved_object``,
   ``cleanup_risk_engine``) are not registered and answer 404.

.. currentmodule:: kibana._sync.client.entity_analytics

.. autoclass:: EntityAnalyticsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Classifying Asset Criticality

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Upsert a single record
      client.entity_analytics.create_asset_criticality(
          id_field="host.name",
          id_value="web-01",
          criticality_level="high_impact",
          refresh="wait_for",
      )

      # Bulk upsert ("unassigned" removes an assignment)
      client.entity_analytics.bulk_upsert_asset_criticality(
          records=[
              {
                  "id_field": "user.name",
                  "id_value": "alice",
                  "criticality_level": "medium_impact",
              },
          ]
      )

      # Read and search records
      record = client.entity_analytics.get_asset_criticality(
          id_field="host.name", id_value="web-01"
      )
      found = client.entity_analytics.find_asset_criticality(
          kuery="criticality_level: high_impact", per_page=100
      )

      # Delete a record
      client.entity_analytics.delete_asset_criticality(
          id_field="host.name", id_value="web-01"
      )

   .. rubric:: Privileged User Monitoring

   .. code-block:: python

      # Initialize the Privilege Monitoring Engine for the space
      client.entity_analytics.init_monitoring_engine()

      # Add monitored users one by one or in bulk via CSV
      user = client.entity_analytics.create_monitored_user(name="admin-user")
      client.entity_analytics.upload_monitored_users_csv(
          file="admin-1\nadmin-2\n"
      )

      # Inspect and manage
      users = client.entity_analytics.list_monitored_users(
          kql="user.name: admin*"
      )
      client.entity_analytics.schedule_monitoring_engine_now()
      health = client.entity_analytics.get_monitoring_health()

      # Disable or remove the engine (data=True also deletes the users)
      client.entity_analytics.disable_monitoring_engine()
      client.entity_analytics.delete_monitoring_engine(data=True)

      # Privileged access detection (PAD) ML package
      client.entity_analytics.install_pad_package()
      pad = client.entity_analytics.get_pad_status()

   .. rubric:: Watchlists (Technical Preview)

   .. code-block:: python

      watchlist = client.entity_analytics.create_watchlist(
          name="High Risk Vendors",
          risk_modifier=1.5,
          description="High risk vendor watchlist",
      )
      watchlist_id = watchlist.body["id"]

      # Add entities from a CSV (matched against the Entity Store)
      client.entity_analytics.upload_watchlist_csv(
          watchlist_id=watchlist_id,
          file="type,name\nhost,web-01\n",
      )

      # Manual entity assignment by EUID
      client.entity_analytics.assign_watchlist_entities(
          watchlist_id=watchlist_id, euids=["host:web-01"]
      )
      client.entity_analytics.unassign_watchlist_entities(
          watchlist_id=watchlist_id, euids=["host:web-01"]
      )

      client.entity_analytics.delete_watchlist(id=watchlist_id)

   .. rubric:: Managing the Entity Store

   .. code-block:: python

      # Install engines and wait until the store is running
      client.entity_analytics.install_entity_store(
          entity_types=["host", "user"],
          log_extraction={"frequency": "5m", "lookbackPeriod": "12h"},
      )
      status = client.entity_analytics.get_entity_store_status(
          include_components=True
      )

      # Query and manage entities
      entities = client.entity_analytics.list_entities(
          entity_types=["host"], sort_field="entity.name", per_page=100
      )
      client.entity_analytics.create_entity(
          entity_type="host", document={"host": {"name": "web-01"}}
      )

      # Entity resolution: link duplicates to a canonical entity
      client.entity_analytics.link_entities(
          entity_ids=["host:web-01.internal"], target_id="host:web-01"
      )
      group = client.entity_analytics.get_entity_resolution_group(
          entity_id="host:web-01"
      )

      # Pause, resume or remove the store
      client.entity_analytics.stop_entity_store()
      client.entity_analytics.start_entity_store()
      client.entity_analytics.uninstall_entity_store()

AsyncEntityAnalyticsClient
--------------------------

Asynchronous version of the EntityAnalyticsClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.entity_analytics.AsyncEntityAnalyticsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncEntityAnalyticsClient provides the same methods as
   EntityAnalyticsClient but all methods are async and must be awaited:

   .. code-block:: python

      import asyncio

      from kibana import AsyncKibana

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Classify an asset (async)
              await client.entity_analytics.create_asset_criticality(
                  id_field="host.name",
                  id_value="web-01",
                  criticality_level="high_impact",
              )

              # Check the Entity Store (async)
              status = await client.entity_analytics.get_entity_store_status()
              print(status.body["status"])

              # Clean up (async)
              await client.entity_analytics.delete_asset_criticality(
                  id_field="host.name", id_value="web-01"
              )

      asyncio.run(main())
