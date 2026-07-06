FleetAgentsClient
=================

Client for the Kibana Fleet Elastic Agents API.

Manages Elastic Agents enrolled in Fleet: listing and inspecting agents,
per-agent operations (update, reassign, unenroll, upgrade, request
diagnostics, migrate, rollback), bulk variants of those operations, agent
action bookkeeping (status, cancel), diagnostics file uploads, agent status
summaries, and Fleet agents setup.

Fleet agent APIs are space-scoped: agents are visible in the Kibana space of
the agent policy they are assigned to. Every method accepts an optional
``space_id`` to target a specific space.

.. currentmodule:: kibana._sync.client.fleet_agents

.. autoclass:: FleetAgentsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Listing Agents and Status Summaries

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # List agents with a KQL filter and a status summary
      agents = client.fleet_agents.get_all(
          kuery='fleet-agents.status : "online"',
          per_page=50,
          get_status_summary=True,
      )
      for agent in agents.body["items"]:
          print(agent["id"], agent["status"], agent["policy_id"])

      # Aggregate status counts (optionally filtered by policy)
      summary = client.fleet_agents.get_status()
      print(summary.body["results"]["online"])

      # Distinct agent tags and upgradable versions
      tags = client.fleet_agents.get_tags()
      versions = client.fleet_agents.get_available_versions()

   .. rubric:: Managing Individual Agents

   .. code-block:: python

      # Inspect and update a single agent
      agent = client.fleet_agents.get(agent_id="agent-id-1", with_metrics=True)
      client.fleet_agents.update(
          agent_id="agent-id-1", tags=["production", "linux"]
      )

      # Reassign to another policy, upgrade, or unenroll
      client.fleet_agents.reassign(
          agent_id="agent-id-1", policy_id="agent-policy-id-2"
      )
      client.fleet_agents.upgrade(agent_id="agent-id-1", version="9.4.3")
      client.fleet_agents.unenroll(agent_id="agent-id-1", revoke=True)

   .. rubric:: Bulk Operations

   Bulk methods select agents either by an explicit list of agent IDs or by
   a KQL query string:

   .. code-block:: python

      # Upgrade every agent on a policy over one hour
      result = client.fleet_agents.bulk_upgrade(
          agents='fleet-agents.policy_id : "my-policy"',
          version="9.4.3",
          rollout_duration_seconds=3600,
      )
      print(result.body["actionId"])

      # Add and remove tags in bulk
      client.fleet_agents.bulk_update_tags(
          agents=["agent-id-1", "agent-id-2"],
          tags_to_add=["production"],
          tags_to_remove=["staging"],
      )

   .. rubric:: Agent Actions and Diagnostics

   .. code-block:: python

      # Request a diagnostics bundle and track the action
      created = client.fleet_agents.request_diagnostics(agent_id="agent-id-1")
      statuses = client.fleet_agents.get_action_status(per_page=10)

      # Cancel an in-progress action
      client.fleet_agents.cancel_action(action_id=created.body["actionId"])

      # Download and clean up uploaded files
      uploads = client.fleet_agents.get_uploads(agent_id="agent-id-1")
      for item in uploads.body["items"]:
          content = client.fleet_agents.get_file(
              file_id=item["id"], file_name=item["name"]
          )
          client.fleet_agents.delete_file(file_id=item["id"])

   .. rubric:: Fleet Setup

   .. code-block:: python

      setup = client.fleet_agents.get_setup_status()
      if not setup.body["isReady"]:
          print(setup.body["missing_requirements"])
      client.fleet_agents.initiate_setup()

AsyncFleetAgentsClient
----------------------

Asynchronous version of the FleetAgentsClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.fleet_agents.AsyncFleetAgentsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncFleetAgentsClient provides the same methods as FleetAgentsClient
   but all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # List agents (async)
              agents = await client.fleet_agents.get_all(per_page=50)

              # Bulk upgrade (async)
              result = await client.fleet_agents.bulk_upgrade(
                  agents='fleet-agents.policy_id : "my-policy"',
                  version="9.4.3",
              )

              # Track and cancel the action (async)
              statuses = await client.fleet_agents.get_action_status()
              await client.fleet_agents.cancel_action(
                  action_id=result.body["actionId"]
              )

      asyncio.run(main())
