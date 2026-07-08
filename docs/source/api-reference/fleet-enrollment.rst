FleetEnrollmentClient
=====================

Client for the Kibana Fleet enrollment keys and tokens API.

This namespace covers the Fleet APIs used to enroll Elastic Agents and Fleet
Servers: enrollment API keys, Fleet Server service tokens, Logstash API keys,
uninstall tokens for tamper-protected agents, the message signing service key
pair, and the Kubernetes agent manifest.

All operations are space-aware: every method accepts an optional ``space_id``
to target a specific space.

.. currentmodule:: kibana._sync.client.fleet_enrollment

.. autoclass:: FleetEnrollmentClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Managing Enrollment API Keys

   Enrollment API keys are tied to an agent policy; agents present the key to
   Fleet Server to enroll into that policy:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create an enrollment API key for an agent policy
      created = client.fleet_enrollment.create_key(
          policy_id="agent-policy-id", name="my-enrollment-key"
      )
      key_id = created.body["item"]["id"]
      enrollment_token = created.body["item"]["api_key"]

      # List keys (optionally filtered with KQL) and fetch one by ID
      keys = client.fleet_enrollment.get_keys(
          per_page=50, kuery='policy_id:"agent-policy-id"'
      )
      key = client.fleet_enrollment.get_key(key_id=key_id)

      # Revoke the key (it is marked inactive, not removed)
      client.fleet_enrollment.delete_key(key_id=key_id)

   .. rubric:: Service Tokens and Logstash API Keys

   .. code-block:: python

      # Service token for enrolling a Fleet Server (remote=True for the
      # elastic/fleet-server-remote service account)
      token = client.fleet_enrollment.create_service_token()
      remote_token = client.fleet_enrollment.create_service_token(remote=True)

      # API key for a Logstash output. Note: requires basic (user)
      # authentication - Elasticsearch cannot derive an API key from
      # another API key.
      logstash_key = client.fleet_enrollment.create_logstash_api_key()

   .. rubric:: Uninstall Tokens

   Uninstall tokens are generated per agent policy and are required to
   uninstall tamper-protected Elastic Agents:

   .. code-block:: python

      # List token metadata (no decrypted values)
      tokens = client.fleet_enrollment.get_uninstall_tokens(
          policy_id="agent-policy-id"
      )
      token_id = tokens.body["items"][0]["id"]

      # Fetch one decrypted token
      decrypted = client.fleet_enrollment.get_uninstall_token(
          uninstall_token_id=token_id
      )
      print(decrypted.body["item"]["token"])

   .. rubric:: Message Signing and Kubernetes Manifests

   .. code-block:: python

      # Rotate the Fleet message signing key pair (irreversible; all agents
      # must be re-enrolled afterwards, hence the explicit acknowledge)
      client.fleet_enrollment.rotate_message_signing_key_pair(acknowledge=True)

      # Kubernetes manifest as JSON ({"item": "<yaml>"}) with the Fleet URL
      # and enrollment token substituted in
      manifest = client.fleet_enrollment.get_kubernetes_manifest(
          fleet_server="https://fleet.example.com:8220",
          enrol_token=enrollment_token,
      )

      # ... or as a raw YAML download (response body is the YAML string)
      yaml_text = client.fleet_enrollment.download_kubernetes_manifest().body

AsyncFleetEnrollmentClient
--------------------------

Asynchronous version of the FleetEnrollmentClient for use with async/await
syntax.

.. autoclass:: kibana._async.client.fleet_enrollment.AsyncFleetEnrollmentClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncFleetEnrollmentClient provides the same methods as
   FleetEnrollmentClient but all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create and revoke an enrollment API key (async)
              created = await client.fleet_enrollment.create_key(
                  policy_id="agent-policy-id", name="async-enrollment-key"
              )
              key_id = created.body["item"]["id"]

              keys = await client.fleet_enrollment.get_keys(per_page=50)
              await client.fleet_enrollment.delete_key(key_id=key_id)

              # Tokens and manifests (async)
              tokens = await client.fleet_enrollment.get_uninstall_tokens()
              manifest = await client.fleet_enrollment.get_kubernetes_manifest()

      asyncio.run(main())
