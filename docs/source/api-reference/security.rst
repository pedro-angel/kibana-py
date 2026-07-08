SecurityClient
==============

Client for the Kibana Security (roles and sessions) API.

Provides role management (create-or-update, get, query, bulk update and
delete Kibana roles, including their Elasticsearch and Kibana privilege
definitions) and user-session invalidation.

The Security API is not space-scoped: roles and sessions are global to the
Kibana instance. Space-level access is granted through the ``kibana``
privilege entries of a role (each entry lists the ``spaces`` it applies to).

.. currentmodule:: kibana._sync.client.security

.. autoclass:: SecurityClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Managing Roles

   Create or update a role with
   :meth:`~SecurityClient.create_or_update_role`:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create or update a role
      client.security.create_or_update_role(
          name="my-role",
          elasticsearch={
              "cluster": ["monitor"],
              "indices": [{"names": ["logs-*"], "privileges": ["read"]}],
          },
          kibana=[{"base": ["read"], "spaces": ["default"]}],
      )

      # Retrieve it
      role = client.security.get_role(name="my-role")
      print(role.body["name"])

   .. rubric:: Listing and Querying Roles

   .. code-block:: python

      # List all roles
      roles = client.security.get_all_roles()
      for role in roles.body:
          print(role["name"])

      # Query roles with paging and sorting
      results = client.security.query_roles(
          query="my-role",
          size=10,
          sort={"field": "name", "direction": "asc"},
      )
      for role in results.body["roles"]:
          print(role["name"])

   .. rubric:: Bulk Operations and Deletion

   .. code-block:: python

      # Create or update several roles at once
      client.security.bulk_create_or_update_roles(
          roles={
              "role-a": {
                  "elasticsearch": {"cluster": ["monitor"]},
              },
              "role-b": {
                  "kibana": [{"base": ["read"], "spaces": ["default"]}],
              },
          }
      )

      # Delete a role
      client.security.delete_role(name="my-role")

   .. rubric:: Invalidating Sessions

   Invalidate user sessions (requires superuser privileges):

   .. code-block:: python

      # Invalidate sessions for a specific user of the basic realm
      result = client.security.invalidate_sessions(
          match="query",
          query={
              "provider": {"type": "basic"},
              "username": "some-user",
          },
      )
      print(f"Invalidated {result.body['total']} sessions")

   .. warning::
      Calling :meth:`~SecurityClient.invalidate_sessions` with
      ``match="all"`` logs out every user of the Kibana instance. Prefer
      ``match="query"`` with a narrow ``query`` to target specific sessions.

AsyncSecurityClient
-------------------

Asynchronous version of the SecurityClient for use with async/await syntax.

.. autoclass:: kibana._async.client.security.AsyncSecurityClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncSecurityClient provides the same methods as SecurityClient but all
   methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a role (async)
              await client.security.create_or_update_role(
                  name="async-role",
                  elasticsearch={"cluster": ["monitor"]},
              )

              # List roles (async)
              roles = await client.security.get_all_roles()

              # Delete the role (async)
              await client.security.delete_role(name="async-role")

      asyncio.run(main())
