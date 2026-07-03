CasesClient
===========

Client for the Kibana Cases API.

Cases are used to open and track issues directly in Kibana. You can add
assignees and tags to your cases, set their severity and status, and add
alerts, comments, and visualizations. You can also send cases to external
incident management systems by configuring connectors.

Cases are space-scoped: every method accepts an optional ``space_id`` to
target a specific space (``None`` targets the default space or the space the
client is scoped to).

.. currentmodule:: kibana._sync.client.cases

.. autoclass:: CasesClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Creating and Updating Cases

   Create a case, comment on it, then close it:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601", api_key="your_api_key")

      # Create a case
      case = client.cases.create(
          title="Suspicious login activity",
          description="Multiple failed logins detected.",
          tags=["security"],
      )
      case_id = case.body["id"]

      # Add a comment
      client.cases.add_comment(
          case_id=case_id, comment="Investigating.", owner="cases"
      )

      # Close the case (updates are versioned)
      updated = client.cases.update(
          id=case_id, version=case.body["version"], status="closed"
      )

   .. rubric:: Finding Cases

   Search cases with :meth:`~CasesClient.find`. The response contains the
   page of ``cases`` plus per-status counts:

   .. code-block:: python

      results = client.cases.find(tags=["security"])

      print(f"Open cases: {results.body['count_open_cases']}")
      for case in results.body["cases"]:
          print(case["id"], case["title"], case["status"])

   .. rubric:: Comments and User Actions

   .. code-block:: python

      # List comments on a case
      comments = client.cases.get_comments(case_id=case_id)

      # Retrieve the full activity (user actions) of a case
      actions = client.cases.find_user_actions(case_id=case_id)

   .. rubric:: External Incident Management Systems

   Cases can be pushed to external systems (Jira, ServiceNow, ...) through
   connectors:

   .. code-block:: python

      # List connectors available for cases
      connectors = client.cases.find_connectors()

      # Configure the default connector and settings for an owner
      config = client.cases.create_configuration(
          owner="cases",
          connector={
              "id": "jira-connector-id",
              "name": "Jira",
              "type": ".jira",
              "fields": None,
          },
          closure_type="close-by-user",
      )

      # Push a case to the configured external system
      client.cases.push(case_id=case_id, connector_id="jira-connector-id")

   .. rubric:: Alerts Attached to Cases

   .. code-block:: python

      # Get all alerts attached to a case
      alerts = client.cases.get_alerts(case_id=case_id)

      # Find the cases an alert is attached to
      cases = client.cases.get_cases_by_alert(alert_id="alert-id")

   .. rubric:: Deleting Cases

   .. code-block:: python

      # Delete one or more cases by ID
      client.cases.delete(ids=[case_id])

AsyncCasesClient
----------------

Asynchronous version of the CasesClient for use with async/await syntax.

.. autoclass:: kibana._async.client.cases.AsyncCasesClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncCasesClient provides the same methods as CasesClient but all
   methods are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Create a case (async)
              case = await client.cases.create(
                  title="Async case",
                  description="Created with the async client.",
              )

              # Comment and find (async)
              await client.cases.add_comment(
                  case_id=case.body["id"],
                  comment="Looking into it.",
                  owner="cases",
              )
              results = await client.cases.find(search="Async case")

              # Delete (async)
              await client.cases.delete(ids=[case.body["id"]])

      asyncio.run(main())
