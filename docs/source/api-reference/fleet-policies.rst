FleetPoliciesClient
===================

Client for the Kibana Fleet agent and package policies API.

Agent policies define how Elastic Agents behave: which outputs they ship
data to, their monitoring settings and which integrations they run. Package
policies attach an integration package (with its inputs and variables) to
one or more agent policies. Agentless policies deploy an integration without
a self-managed Elastic Agent (Elastic Cloud / serverless only).

Fleet policies are space-aware resources: every method accepts an optional
``space_id`` to target a specific space.

.. currentmodule:: kibana._sync.client.fleet_policies

.. autoclass:: FleetPoliciesClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Managing Agent Policies

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create an agent policy (without the system monitoring package)
      created = client.fleet_policies.create_agent_policy(
          name="my-agent-policy",
          namespace="default",
          description="Policy for web servers",
          monitoring_enabled=["logs", "metrics"],
          sys_monitoring=False,
      )
      agent_policy_id = created.body["item"]["id"]

      # Get, update and list agent policies
      policy = client.fleet_policies.get_agent_policy(
          agent_policy_id=agent_policy_id
      )
      client.fleet_policies.update_agent_policy(
          agent_policy_id=agent_policy_id,
          name="my-agent-policy",
          namespace="default",
          description="Updated description",
      )
      policies = client.fleet_policies.get_agent_policies(
          kuery='ingest-agent-policies.name:"my-agent-policy"'
      )

      # Copy, then delete the copy
      copy = client.fleet_policies.copy_agent_policy(
          agent_policy_id=agent_policy_id, name="my-agent-policy (copy)"
      )
      client.fleet_policies.delete_agent_policy(
          agent_policy_id=copy.body["item"]["id"]
      )

   .. rubric:: Inspecting Compiled Policies

   .. code-block:: python

      # Full compiled policy document (what an enrolled agent receives)
      full = client.fleet_policies.get_full_agent_policy(
          agent_policy_id=agent_policy_id
      )

      # The same document as downloadable elastic-agent.yml (YAML string)
      yaml_doc = client.fleet_policies.download_agent_policy(
          agent_policy_id=agent_policy_id
      )
      print(yaml_doc.body)

      # Outputs used by one or many policies
      outputs = client.fleet_policies.get_agent_policy_outputs(
          agent_policy_id=agent_policy_id
      )
      bulk_outputs = client.fleet_policies.get_agent_policies_outputs(
          ids=[agent_policy_id]
      )

   .. rubric:: Managing Package Policies

   .. code-block:: python

      # Attach the "udp" integration using the simplified inputs format
      pkg = client.fleet_policies.create_package_policy(
          name="my-udp-policy",
          package={"name": "udp", "version": "2.5.1"},
          policy_ids=[agent_policy_id],
          inputs={
              "udp-udp": {
                  "enabled": True,
                  "streams": {
                      "udp.udp": {
                          "enabled": True,
                          "vars": {
                              "listen_address": "localhost",
                              "listen_port": 8964,
                              "data_stream.dataset": "udp.custom",
                          },
                      }
                  },
              }
          },
      )
      package_policy_id = pkg.body["item"]["id"]

      # Upgrade dry run, then upgrade to the latest installed version
      dry_run = client.fleet_policies.upgrade_package_policies_dry_run(
          package_policy_ids=[package_policy_id]
      )
      client.fleet_policies.upgrade_package_policies(
          package_policy_ids=[package_policy_id]
      )

      # Delete package policies (single or bulk)
      client.fleet_policies.delete_package_policy(
          package_policy_id=package_policy_id, force=True
      )

   .. rubric:: Agentless Policies

   Agentless policies are only supported in Elastic Cloud and serverless
   environments; self-managed deployments reject these calls with a 400
   error.

   .. code-block:: python

      created = client.fleet_policies.create_agentless_policy(
          name="my-agentless-policy",
          package={"name": "cspm", "version": "1.0.0"},
      )
      client.fleet_policies.delete_agentless_policy(
          policy_id=created.body["item"]["id"]
      )

AsyncFleetPoliciesClient
------------------------

Asynchronous version of the FleetPoliciesClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.fleet_policies.AsyncFleetPoliciesClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncFleetPoliciesClient provides the same methods as
   FleetPoliciesClient but all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              created = await client.fleet_policies.create_agent_policy(
                  name="async-agent-policy",
                  namespace="default",
                  sys_monitoring=False,
              )
              agent_policy_id = created.body["item"]["id"]

              yaml_doc = await client.fleet_policies.download_agent_policy(
                  agent_policy_id=agent_policy_id
              )

              await client.fleet_policies.delete_agent_policy(
                  agent_policy_id=agent_policy_id
              )

      asyncio.run(main())
