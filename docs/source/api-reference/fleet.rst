FleetClient
===========

Client for the Kibana Fleet core API.

Fleet provides centralized management of Elastic Agents and their policies.
This client covers the Fleet internals: initializing Fleet, reading and
updating the global and per-space Fleet settings, checking Fleet Server
health, and checking the current user's Fleet permissions.

All Fleet APIs are space-aware: every method accepts an optional
``space_id`` to target a specific Kibana space.

.. currentmodule:: kibana._sync.client.fleet

.. autoclass:: FleetClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Initializing Fleet

   Fleet setup creates the Elasticsearch resources Fleet needs to operate.
   It is idempotent and safe to call multiple times:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      result = client.fleet.setup()
      print(result.body["isInitialized"])   # True
      print(result.body["nonFatalErrors"])  # []

   .. rubric:: Checking Permissions and Fleet Server Health

   .. code-block:: python

      # Check whether the current user can use Fleet
      perms = client.fleet.check_permissions()
      if not perms.body["success"]:
          print(perms.body["error"])  # e.g. "MISSING_PRIVILEGES"

      # Also verify Fleet Server setup privileges
      perms = client.fleet.check_permissions(fleet_server_setup=True)

      # Check the health of a configured Fleet Server host by its ID
      health = client.fleet.health_check(id="fleet-server-host-id-1")
      print(health.body["status"])  # "ONLINE" or "OFFLINE"

   .. rubric:: Global Fleet Settings

   .. code-block:: python

      # Read the global Fleet settings
      settings = client.fleet.get_settings()
      item = settings.body["item"]
      print(item["prerelease_integrations_enabled"])

      # Update a setting (only the provided fields are changed)
      client.fleet.update_settings(prerelease_integrations_enabled=True)

      # Configure automatic deletion of unenrolled agents
      client.fleet.update_settings(
          delete_unenrolled_agents={
              "enabled": True,
              "is_preconfigured": False,
          }
      )

   .. rubric:: Per-Space Fleet Settings

   Space settings restrict which data stream namespace prefixes may be used
   in a Kibana space. Note that Kibana 9.4.3 rejects prefixes containing a
   ``-`` character:

   .. code-block:: python

      # Read the space settings for the default space
      space_settings = client.fleet.get_space_settings()
      print(space_settings.body["item"]["allowed_namespace_prefixes"])

      # Restrict namespaces in a specific space
      client.fleet.update_space_settings(
          allowed_namespace_prefixes=["teama", "teamb"],
          space_id="marketing",
      )

      # Remove all restrictions again
      client.fleet.update_space_settings(
          allowed_namespace_prefixes=[],
          space_id="marketing",
      )

AsyncFleetClient
----------------

Asynchronous version of the FleetClient for use with async/await syntax.

.. autoclass:: kibana._async.client.fleet.AsyncFleetClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncFleetClient provides the same methods as FleetClient but all
   methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Initialize Fleet (async)
              result = await client.fleet.setup()
              print(result.body["isInitialized"])

              # Read and update the global settings (async)
              settings = await client.fleet.get_settings()
              await client.fleet.update_settings(
                  prerelease_integrations_enabled=True
              )

              # Check permissions (async)
              perms = await client.fleet.check_permissions()
              print(perms.body["success"])

      asyncio.run(main())
