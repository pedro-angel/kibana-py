SyntheticsClient
================

Client for the Kibana Synthetics API.

Synthetics periodically checks the status of your services and applications
from lightweight (HTTP, TCP, ICMP) and browser monitors. This client manages
monitors, global parameters, and private locations, and can trigger on-demand
test runs.

All Synthetics resources are space-scoped: every method accepts an optional
``space_id`` to target a specific space (``None`` targets the default space
or the space the client is scoped to).

.. note::
   Creating a monitor requires at least one location: either an Elastic
   managed location (cloud) or a private location. Private locations are
   backed by a Fleet agent policy (``agent_policy_id``).

.. currentmodule:: kibana._sync.client.synthetics

.. autoclass:: SyntheticsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Private Locations

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a private location backed by a Fleet agent policy
      loc = client.synthetics.create_private_location(
          label="My private location",
          agent_policy_id="abc-123",
      )
      location_id = loc.body["id"]

      # List private locations
      locations = client.synthetics.get_private_locations()

   .. rubric:: Monitors

   .. code-block:: python

      # Create an HTTP monitor running from the private location
      monitor = client.synthetics.create_monitor(
          type="http",
          name="My monitor",
          url="https://example.com",
          private_locations=[location_id],
          schedule={"number": "5", "unit": "m"},
          tags=["production"],
      )
      monitor_id = monitor.body["id"]

      # List monitors with filters
      monitors = client.synthetics.get_monitors(
          monitor_types="http", tags="production"
      )
      for m in monitors.body["monitors"]:
          print(m["id"], m["name"])

      # Update a monitor (partial update)
      client.synthetics.update_monitor(
          id=monitor_id,
          enabled=False,
      )

      # Trigger an on-demand test run
      test = client.synthetics.test_monitor(monitor_id=monitor_id)

      # Delete the monitor
      client.synthetics.delete_monitor(id=monitor_id)

   .. rubric:: Global Parameters

   Global parameters can be referenced from monitor configurations (e.g.
   ``${my_param}``):

   .. code-block:: python

      # Create a parameter
      param = client.synthetics.create_param(
          key="base_url",
          value="https://example.com",
      )

      # List parameters
      params = client.synthetics.get_params()

      # Bulk delete parameters
      client.synthetics.bulk_delete_params(ids=[param.body["id"]])

AsyncSyntheticsClient
---------------------

Asynchronous version of the SyntheticsClient for use with async/await syntax.

.. autoclass:: kibana._async.client.synthetics.AsyncSyntheticsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncSyntheticsClient provides the same methods as SyntheticsClient but
   all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a monitor (async)
              monitor = await client.synthetics.create_monitor(
                  type="http",
                  name="Async monitor",
                  url="https://example.com",
                  private_locations=["private-location-id"],
              )

              # List monitors (async)
              monitors = await client.synthetics.get_monitors()

              # Delete (async)
              await client.synthetics.delete_monitor(id=monitor.body["id"])

      asyncio.run(main())
