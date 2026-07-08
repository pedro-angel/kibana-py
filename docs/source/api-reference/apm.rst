ApmClient
=========

Client for the Kibana APM (Application Performance Monitoring) API.

Covers the Kibana 9.4 APM UI endpoints: APM agent keys, APM Server schema,
service annotations, agent configurations, and RUM source maps.

The endpoints are space-scoped: every method accepts an optional ``space_id``
to route the request through the ``/s/{space_id}`` path prefix. Note that
agent configurations and source maps live in cluster-wide storage (the
``.apm-agent-configuration`` index and Fleet artifacts), so the same data is
visible from every space; the space prefix scopes the API route and its
privilege checks rather than the data.

Required privileges vary per endpoint: agent configuration and source map
writes need APM/APM settings write privileges; creating agent keys
additionally requires the ``manage_own_api_key`` cluster privilege.

.. currentmodule:: kibana._sync.client.apm

.. autoclass:: ApmClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Agent Configurations

   Centrally manage APM agent settings:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create or update an agent configuration
      client.apm.create_or_update_agent_configuration(
          service_name="opbeans-node",
          service_environment="production",
          settings={"transaction_sample_rate": "0.5"},
      )

      # List agent configurations
      for c in client.apm.get_agent_configurations().body["configurations"]:
          print(c["service"], c["settings"])

      # Delete an agent configuration
      client.apm.delete_agent_configuration(
          service_name="opbeans-node",
          service_environment="production",
      )

   .. rubric:: Agent Keys

   .. code-block:: python

      # Create an APM agent key (requires manage_own_api_key)
      key = client.apm.create_agent_key(
          name="my-agent-key",
          privileges=["event:write", "config_agent:read"],
      )

   .. rubric:: Service Annotations

   Mark deployments and other events on APM charts:

   .. code-block:: python

      # Create a deployment annotation
      client.apm.create_annotation(
          service_name="opbeans-node",
          timestamp="2026-07-03T12:00:00.000Z",
          service_version="1.2.3",
          message="Deployed 1.2.3",
      )

      # Search annotations for a service
      annotations = client.apm.search_annotations(
          service_name="opbeans-node",
          environment="production",
      )

   .. rubric:: RUM Source Maps

   .. code-block:: python

      # List uploaded source maps
      sourcemaps = client.apm.get_sourcemaps()

AsyncApmClient
--------------

Asynchronous version of the ApmClient for use with async/await syntax.

.. autoclass:: kibana._async.client.apm.AsyncApmClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncApmClient provides the same methods as ApmClient but all methods
   are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create an agent configuration (async)
              await client.apm.create_or_update_agent_configuration(
                  service_name="opbeans-node",
                  settings={"transaction_sample_rate": "0.5"},
              )

              # List configurations (async)
              configs = await client.apm.get_agent_configurations()

      asyncio.run(main())
