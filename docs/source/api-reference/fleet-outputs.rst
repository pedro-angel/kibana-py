FleetOutputsClient
==================

Client for the Kibana Fleet outputs and connectivity API.

This client manages where Elastic Agents send their data and how they reach
the Elastic Stack: outputs (Elasticsearch, remote Elasticsearch, Logstash,
Kafka), Fleet Server hosts, Fleet proxies, agent binary download sources,
remote synced integrations status, and cloud connectors (technical preview
in Kibana 9.4).

All methods accept an optional ``space_id`` to target a specific Kibana
space.

.. currentmodule:: kibana._sync.client.fleet_outputs

.. autoclass:: FleetOutputsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Managing Outputs

   Outputs define the destinations agents send data to. Type-specific
   properties (Kafka authentication, remote Elasticsearch sync settings,
   ...) are passed via ``fields``:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # List outputs (the default Elasticsearch output always exists)
      outputs = client.fleet_outputs.get_outputs()
      for output in outputs.body["items"]:
          print(output["id"], output["type"], output["is_default"])

      # Create a Logstash output
      created = client.fleet_outputs.create_output(
          name="my-logstash",
          type="logstash",
          hosts=["logstash.example.com:5044"],
      )
      output_id = created.body["item"]["id"]

      # Create a Kafka output with type-specific fields
      kafka = client.fleet_outputs.create_output(
          name="my-kafka",
          type="kafka",
          hosts=["kafka.example.com:9092"],
          fields={
              "auth_type": "user_pass",
              "username": "fleet",
              "password": "secret",
              "topic": "agent-events",
          },
      )

      # Rename, check health, then delete
      client.fleet_outputs.update_output(output_id=output_id, name="renamed")
      health = client.fleet_outputs.get_output_health(output_id=output_id)
      print(health.body["state"])
      client.fleet_outputs.delete_output(output_id=output_id)

   .. rubric:: Fleet Server Hosts and Proxies

   .. code-block:: python

      # Create a proxy and a Fleet Server host that connects through it
      proxy = client.fleet_outputs.create_proxy(
          name="my-proxy", url="https://proxy.example.com:3128"
      )
      host = client.fleet_outputs.create_fleet_server_host(
          name="my-fleet-server",
          host_urls=["https://fleet.example.com:8220"],
          proxy_id=proxy.body["item"]["id"],
      )

      # List, update and delete
      hosts = client.fleet_outputs.get_fleet_server_hosts()
      client.fleet_outputs.update_fleet_server_host(
          item_id=host.body["item"]["id"], name="renamed-fleet-server"
      )
      client.fleet_outputs.delete_fleet_server_host(
          item_id=host.body["item"]["id"]
      )
      client.fleet_outputs.delete_proxy(item_id=proxy.body["item"]["id"])

   .. rubric:: Agent Binary Download Sources

   .. code-block:: python

      # Point agents at a private artifacts mirror
      source = client.fleet_outputs.create_agent_download_source(
          name="my-mirror",
          host="https://artifacts.example.com/downloads/",
      )
      source_id = source.body["item"]["id"]

      # name and host are required on every update
      client.fleet_outputs.update_agent_download_source(
          source_id=source_id,
          name="my-mirror-renamed",
          host="https://artifacts.example.com/downloads/",
      )
      client.fleet_outputs.delete_agent_download_source(source_id=source_id)

   .. rubric:: Remote Synced Integrations

   .. code-block:: python

      # Status of integrations synced to this cluster
      status = client.fleet_outputs.get_remote_synced_integrations_status()
      print(status.body["integrations"])

      # Status reported by the remote cluster behind a
      # remote_elasticsearch output with sync_integrations enabled
      remote = client.fleet_outputs.get_remote_synced_integrations_remote_status(
          output_id="my-remote-output-id"
      )

   .. rubric:: Cloud Connectors (Technical Preview)

   Cloud connectors hold reusable cloud credentials. For AWS, the
   ``external_id`` var must be a secret reference:

   .. code-block:: python

      created = client.fleet_outputs.create_cloud_connector(
          name="arn:aws:iam::123456789012:role/my-role",
          cloud_provider="aws",
          vars={
              "role_arn": {
                  "value": "arn:aws:iam::123456789012:role/my-role",
                  "type": "text",
              },
              "external_id": {
                  "value": {"id": "AbCdEfGhIjKlMnOpQrSt", "isSecretRef": True},
                  "type": "password",
              },
          },
      )
      connector_id = created.body["item"]["id"]

      usage = client.fleet_outputs.get_cloud_connector_usage(
          cloud_connector_id=connector_id
      )
      client.fleet_outputs.delete_cloud_connector(
          cloud_connector_id=connector_id, force=True
      )

AsyncFleetOutputsClient
-----------------------

Asynchronous version of the FleetOutputsClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.fleet_outputs.AsyncFleetOutputsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncFleetOutputsClient provides the same methods as
   FleetOutputsClient but all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create an output (async)
              created = await client.fleet_outputs.create_output(
                  name="async-logstash",
                  type="logstash",
                  hosts=["logstash.example.com:5044"],
              )
              output_id = created.body["item"]["id"]

              # Inspect it (async)
              health = await client.fleet_outputs.get_output_health(
                  output_id=output_id
              )
              print(health.body["state"])

              # Delete (async)
              await client.fleet_outputs.delete_output(output_id=output_id)

      asyncio.run(main())
