SpacesClient
============

Client for managing Kibana Spaces through the Spaces API.

Spaces allow you to organize your Kibana objects (dashboards, visualizations, saved objects)
into separate, isolated areas. Each space can have its own set of saved objects and can be
used to implement multi-tenancy in Kibana.

.. currentmodule:: kibana

.. autoclass:: SpacesClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Overview

   The SpacesClient provides methods to create, retrieve, update, and delete Kibana Spaces.
   Spaces enable multi-tenancy by isolating saved objects and providing separate workspaces
   for different teams or use cases.

   .. rubric:: Creating Spaces

   Create a new space with the :meth:`~SpacesClient.create` method:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601")

      # Create a space
      space = client.spaces.create(
          id="marketing",
          name="Marketing Team",
          description="Space for the marketing team",
          color="#FF6B6B",
          initials="MK"
      )

      print(f"Created space: {space.body['id']}")

   .. rubric:: Space Configuration Options

   Spaces can be configured with various options:

   .. code-block:: python

      # Create space with disabled features
      space = client.spaces.create(
          id="sales",
          name="Sales Team",
          description="Sales team workspace",
          color="#4ECDC4",
          initials="ST",
          disabled_features=["dev_tools", "advancedSettings"]
      )

      # Create space with custom image URL
      space = client.spaces.create(
          id="engineering",
          name="Engineering",
          description="Engineering team space",
          image_url="https://example.com/logo.png"
      )

   .. rubric:: Listing and Retrieving Spaces

   Get all spaces or retrieve a specific space:

   .. code-block:: python

      # Get all spaces
      spaces = client.spaces.get_all()
      for space in spaces.body:
          print(f"{space['id']}: {space['name']}")

      # Get a specific space
      space = client.spaces.get(id="marketing")
      print(f"Space name: {space.body['name']}")
      print(f"Description: {space.body['description']}")

   .. rubric:: Updating Spaces

   Update space configuration:

   .. code-block:: python

      # Update space name and description
      updated = client.spaces.update(
          id="marketing",
          name="Marketing Department",
          description="Updated description for marketing team"
      )

      # Update disabled features
      updated = client.spaces.update(
          id="marketing",
          disabled_features=["dev_tools", "advancedSettings", "indexPatterns"]
      )

   .. rubric:: Deleting Spaces

   Delete a space and all its saved objects:

   .. code-block:: python

      # Delete a space
      client.spaces.delete(id="marketing")

   .. warning::
      Deleting a space permanently removes all saved objects within that space.
      This operation cannot be undone.

   .. rubric:: Space-Scoped Operations

   Use spaces with other API clients for multi-tenancy:

   .. code-block:: python

      # Create a space
      space = client.spaces.create(
          id="team-a",
          name="Team A",
          description="Team A workspace"
      )

      # Create a space-scoped client
      team_a_client = client.space("team-a")

      # Create connector in Team A's space
      connector = team_a_client.actions.create(
          name="Team A Webhook",
          connector_type_id=".webhook",
          config={"url": "https://team-a.example.com/webhook"}
      )

      # Create dashboard in Team A's space
      dashboard = team_a_client.saved_objects.create(
          type="dashboard",
          attributes={"title": "Team A Dashboard"}
      )

   .. rubric:: Error Handling

   Handle common errors when working with spaces:

   .. code-block:: python

      from kibana.exceptions import (
          NotFoundError,
          ConflictError,
          BadRequestError,
          InvalidSpaceIdError
      )

      try:
          space = client.spaces.create(
              id="my-space",
              name="My Space"
          )
      except ConflictError as e:
          print(f"Space already exists: {e.message}")
      except InvalidSpaceIdError as e:
          print(f"Invalid space ID: {e.space_id}")
      except BadRequestError as e:
          print(f"Invalid configuration: {e.message}")

      try:
          space = client.spaces.get(id="nonexistent")
      except NotFoundError as e:
          print(f"Space not found: {e.message}")

AsyncSpacesClient
-----------------

Asynchronous version of the SpacesClient for use with async/await syntax.

.. autoclass:: kibana._async.client.spaces.AsyncSpacesClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncSpacesClient provides the same methods as SpacesClient but all methods
   are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create space (async)
              space = await client.spaces.create(
                  id="async-space",
                  name="Async Space",
                  description="Created with async client"
              )

              # Get all spaces (async)
              spaces = await client.spaces.get_all()

              # Update space (async)
              updated = await client.spaces.update(
                  id="async-space",
                  name="Updated Async Space"
              )

              # Delete space (async)
              await client.spaces.delete(id="async-space")

      asyncio.run(main())

   .. rubric:: Concurrent Space Operations

   Perform multiple space operations concurrently:

   .. code-block:: python

      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create multiple spaces concurrently
              spaces = await asyncio.gather(
                  client.spaces.create(
                      id="team-a",
                      name="Team A",
                      description="Team A workspace"
                  ),
                  client.spaces.create(
                      id="team-b",
                      name="Team B",
                      description="Team B workspace"
                  ),
                  client.spaces.create(
                      id="team-c",
                      name="Team C",
                      description="Team C workspace"
                  )
              )

              print(f"Created {len(spaces)} spaces")

              # Get all spaces concurrently with their details
              space_details = await asyncio.gather(
                  client.spaces.get(id="team-a"),
                  client.spaces.get(id="team-b"),
                  client.spaces.get(id="team-c")
              )

      asyncio.run(main())
