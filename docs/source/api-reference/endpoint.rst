EndpointClient
==============

Client for the Kibana Security Endpoint Management API.

The Endpoint Management API (``/api/endpoint/...``) drives Elastic Defend. It
lists enrolled endpoint hosts and their metadata, runs *response actions*
against them (isolate/release a host, terminate or suspend a process, list
running processes, retrieve or upload a file, run a command or a script, scan
for malware, generate a memory dump, or cancel a pending action), inspects
action history/status, reads endpoint policy responses, manages the
protection-updates note on a Defend package policy, and manages the reusable
scripts library.

Response actions require the target hosts to have the Elastic Defend
integration installed and enrolled. Against a stack with no enrolled endpoints
those routes return an HTTP 400 (``The host does not have Elastic Defend
integration installed``).

All Endpoint Management APIs are space-scoped resources: every method accepts
an optional ``space_id`` to target a specific space.

.. currentmodule:: kibana._sync.client.endpoint

.. autoclass:: EndpointClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Listing Hosts and Actions

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # List enrolled endpoint hosts
      hosts = client.endpoint.get_metadata_list(
          host_statuses=["healthy"], page_size=50
      )
      print(hosts.body["total"])

      # Metadata for a single host
      host = client.endpoint.get_metadata(id="endpoint-id-1")

      # Response-actions state and history
      state = client.endpoint.get_actions_state()
      actions = client.endpoint.get_actions_list(commands=["isolate"])
      status = client.endpoint.get_actions_status(agent_ids=["agent-id-1"])
      details = client.endpoint.get_action_details(action_id="action-id-1")

   .. rubric:: Running Response Actions

   .. code-block:: python

      # Isolate / release a host
      client.endpoint.isolate(
          endpoint_ids=["endpoint-id-1"], comment="Investigating"
      )
      client.endpoint.unisolate(endpoint_ids=["endpoint-id-1"])

      # Terminate or suspend a process
      client.endpoint.kill_process(
          endpoint_ids=["endpoint-id-1"], parameters={"pid": 123}
      )
      client.endpoint.suspend_process(
          endpoint_ids=["endpoint-id-1"], parameters={"entity_id": "abc"}
      )

      # Collect data
      client.endpoint.get_running_processes(endpoint_ids=["endpoint-id-1"])
      client.endpoint.get_file(
          endpoint_ids=["endpoint-id-1"], parameters={"path": "/etc/passwd"}
      )
      client.endpoint.execute(
          endpoint_ids=["endpoint-id-1"],
          parameters={"command": "ls -la", "timeout": 600},
      )
      client.endpoint.scan(
          endpoint_ids=["endpoint-id-1"], parameters={"path": "/opt"}
      )

      # Upload a file to the host (multipart)
      action = client.endpoint.upload(
          endpoint_ids=["endpoint-id-1"],
          file=b"#!/bin/sh\necho hi\n",
          filename="fix.sh",
          parameters={"overwrite": True},
      )

      # Retrieve a file produced by a get_file / scan action
      info = client.endpoint.get_action_file_info(
          action_id="action-id-1", file_id="file-id-1"
      )
      blob = client.endpoint.download_action_file(
          action_id="action-id-1", file_id="file-id-1"
      )

      # Cancel a pending action
      client.endpoint.cancel(
          endpoint_ids=["endpoint-id-1"], parameters={"id": "action-id-1"}
      )

   .. rubric:: Policy Response and Protection Updates Note

   .. code-block:: python

      resp = client.endpoint.get_policy_response(agent_id="agent-id-1")

      client.endpoint.create_update_protection_updates_note(
          package_policy_id="package-policy-id-1",
          note="Pinned to 2024-01-01 protection artifacts",
      )
      note = client.endpoint.get_protection_updates_note(
          package_policy_id="package-policy-id-1"
      )

   .. rubric:: Managing the Scripts Library

   .. code-block:: python

      created = client.endpoint.create_script(
          name="collect-logs",
          platform=["linux"],
          file_type="script",
          file=b"#!/bin/sh\necho hi\n",
          filename="collect.sh",
          tags=["threatHunting"],
      )
      script_id = created.body["data"]["id"]

      client.endpoint.get_scripts(page_size=50)
      client.endpoint.get_script(script_id=script_id)
      client.endpoint.update_script(
          script_id=script_id, description="Updated"
      )
      client.endpoint.download_script(script_id=script_id)
      client.endpoint.delete_script(script_id=script_id)

AsyncEndpointClient
-------------------

Asynchronous version of the EndpointClient for use with async/await syntax.

.. currentmodule:: kibana._async.client.endpoint

.. autoclass:: AsyncEndpointClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncEndpointClient provides the same methods as EndpointClient but all
   methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # List hosts and read actions state (async)
              hosts = await client.endpoint.get_metadata_list()
              state = await client.endpoint.get_actions_state()

              # Create and clean up a library script (async)
              created = await client.endpoint.create_script(
                  name="collect-logs",
                  platform=["linux"],
                  file_type="script",
                  file=b"#!/bin/sh\necho hi\n",
                  filename="collect.sh",
              )
              await client.endpoint.delete_script(
                  script_id=created.body["data"]["id"]
              )

              # Isolate a host (async)
              await client.endpoint.isolate(endpoint_ids=["endpoint-id-1"])

      asyncio.run(main())
