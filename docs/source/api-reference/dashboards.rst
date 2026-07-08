DashboardsClient
================

Client for the new Kibana Dashboards HTTP API.

.. note::
   The Dashboards HTTP API is in **technical preview** (added in Kibana 9.4.0)
   and may change in future releases.

The Dashboards API manages dashboards as code: each dashboard is addressed by
its ID and represented by a flat ``data`` object. Responses are enveloped as
``{"id": ..., "data": {...}, "meta": {...}}`` where ``meta`` carries
server-managed fields (``created_at``, ``updated_at``, ``created_by``,
``updated_by``, ``managed``, ``version``).

Dashboards are space-scoped: every method accepts ``space_id`` to target a
specific Kibana space, or you can use a space-scoped client created with
``client.space("my-space")``.

.. currentmodule:: kibana._sync.client.dashboards

.. autoclass:: DashboardsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Overview

   The DashboardsClient provides methods to create, retrieve, search, update
   (upsert), and delete dashboards through the ``/api/dashboards`` endpoints.

   .. rubric:: The Dashboard Data Model

   The ``data`` object supports:

   - ``title`` (required) - human-readable dashboard title
   - ``description`` - short description of the dashboard
   - ``panels`` - list of panels and collapsible sections; each panel has a
     ``type`` (e.g. ``"markdown"``, ``"vis"``, ``"image"``,
     ``"discover_session"``), a ``grid`` placement (``x``, ``y`` required;
     ``w`` up to 48, defaults 24; ``h`` defaults 15) and a type-specific
     ``config`` (inline "by value" or ``ref_id`` "by reference")
   - ``options`` - display/behavior settings (``auto_apply_filters``,
     ``hide_panel_borders``, ``hide_panel_titles``, ``sync_colors``,
     ``sync_cursor``, ``sync_tooltips``, ``use_margins``)
   - ``filters`` - filters applied across all panels
   - ``query`` - a search query ``{"expression": ..., "language": "kql" | "lucene"}``
   - ``time_range`` - ``{"from": ..., "to": ...}`` accepting date math
     (e.g. ``now-7d``) or ISO 8601 timestamps
   - ``refresh_interval`` - ``{"pause": bool, "value": ms}`` auto-refresh setting
   - ``tags`` - list of tag IDs associated with the dashboard
   - ``pinned_panels`` - control panels and their state in the control group
   - ``access_control`` - ``{"access_mode": "default" | "write_restricted"}``
     edit-access setting; accepted only at creation time
     (:meth:`~DashboardsClient.create`)

   .. rubric:: Creating Dashboards

   Create a dashboard with the :meth:`~DashboardsClient.create` method. The
   server assigns the dashboard ID:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a dashboard with a markdown panel, tags and a time range
      created = client.dashboards.create(
          title="Team Overview",
          description="Key metrics for the team",
          tags=["team-tag-id"],
          time_range={"from": "now-7d", "to": "now"},
          panels=[
              {
                  "type": "markdown",
                  "grid": {"x": 0, "y": 0, "w": 48, "h": 8},
                  "config": {
                      "title": "Welcome",
                      "content": "# Team Overview\nManaged by *kibana-py*.",
                      "settings": {"open_links_in_new_tab": True},
                  },
              }
          ],
      )

      dashboard_id = created.body["id"]
      print(f"Created dashboard: {dashboard_id}")

   .. rubric:: Retrieving Dashboards

   Read a dashboard back with :meth:`~DashboardsClient.get`. Responses are
   ``{id, data, meta}`` envelopes:

   .. code-block:: python

      fetched = client.dashboards.get(id=dashboard_id)

      data = fetched.body["data"]
      print(f"Title: {data['title']}")
      print(f"Panels: {[p['type'] for p in data['panels']]}")
      print(f"Updated at: {fetched.body['meta']['updated_at']}")

   .. rubric:: Searching Dashboards

   List and filter dashboards with :meth:`~DashboardsClient.get_all`. The
   ``query`` parameter filters on ``title`` and ``description`` using
   Elasticsearch ``simple_query_string`` syntax:

   .. code-block:: python

      # Search dashboards with query/tags filters and pagination
      results = client.dashboards.get_all(
          query="Team*",
          tags=["team-tag-id"],
          per_page=10,
          page=1,
      )

      print(f"Total matches: {results.body['total']}")
      for item in results.body["dashboards"]:
          print(item["id"], item["data"]["title"])

   .. rubric:: Updating (Upserting) Dashboards

   :meth:`~DashboardsClient.update` performs an upsert via
   ``PUT /api/dashboards/{id}``: if the dashboard exists it is **replaced**
   with the provided data; if it does not exist it is created with the given
   ID. This is also the way to create a dashboard with a custom ID, since
   :meth:`~DashboardsClient.create` always assigns a server-generated ID:

   .. code-block:: python

      # Replace an existing dashboard (omitted fields revert to defaults)
      client.dashboards.update(
          id=dashboard_id,
          title="Team Overview (v2)",
          time_range={"from": "now-30d", "to": "now"},
      )

      # Upsert a dashboard at a custom ID
      client.dashboards.update(
          id="my-well-known-dashboard-id",
          title="Provisioned Dashboard",
      )

   .. warning::
      The provided data replaces the stored dashboard data — fields omitted
      from the call revert to their defaults rather than being preserved.
      Unlike :meth:`~DashboardsClient.create`, ``update`` does not accept an
      ``access_control`` field; access control can only be set at creation
      time.

   .. rubric:: Deleting Dashboards

   .. code-block:: python

      client.dashboards.delete(id=dashboard_id)

   .. rubric:: Space-Scoped Dashboards

   Dashboards live inside Kibana spaces:

   .. code-block:: python

      # Target a space explicitly
      dashboard = client.dashboards.create(
          title="Marketing KPIs",
          space_id="marketing",
      )

      # Or use a space-scoped client
      marketing = client.space("marketing")
      dashboard = marketing.dashboards.create(title="Marketing KPIs")

   .. rubric:: Error Handling

   .. code-block:: python

      from kibana.exceptions import (
          NotFoundError,
          BadRequestError,
          SpaceNotFoundError,
      )

      try:
          dashboard = client.dashboards.get(id="nonexistent")
      except NotFoundError:
          print("Dashboard not found")
      except BadRequestError as e:
          print(f"Invalid request: {e.message}")
      except SpaceNotFoundError as e:
          print(f"Space not found: {e.space_id}")

AsyncDashboardsClient
---------------------

Asynchronous version of the DashboardsClient for use with async/await syntax.

.. autoclass:: kibana._async.client.dashboards.AsyncDashboardsClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncDashboardsClient provides the same methods as DashboardsClient but
   all methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a dashboard (async)
              created = await client.dashboards.create(
                  title="Async Dashboard",
                  panels=[
                      {
                          "type": "markdown",
                          "grid": {"x": 0, "y": 0, "w": 24, "h": 15},
                          "config": {"content": "# Hello", "settings": {}},
                      }
                  ],
              )

              # Search dashboards (async)
              results = await client.dashboards.get_all(query="Async*")

              # Delete (async)
              await client.dashboards.delete(id=created.body["id"])

      asyncio.run(main())

   .. rubric:: Concurrent Operations

   Provision multiple dashboards concurrently:

   .. code-block:: python

      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              dashboards = await asyncio.gather(
                  client.dashboards.create(title="Dashboard 1"),
                  client.dashboards.create(title="Dashboard 2"),
                  client.dashboards.create(title="Dashboard 3"),
              )
              print(f"Created {len(dashboards)} dashboards")

      asyncio.run(main())
