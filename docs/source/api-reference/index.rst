API Reference
=============

Complete API reference for the Kibana Python client.

This section provides detailed documentation for all public classes, methods,
and exceptions in the kibana-py library. The documentation is automatically
generated from code docstrings and includes usage examples.

The client covers the Kibana 9.4 platform, Fleet and Security Solution APIs
across 39 namespaces — headlined by the new
:doc:`Dashboards HTTP API <dashboards>` (technical preview) — with full
synchronous and asynchronous parity.

.. toctree::
   :maxdepth: 2
   :caption: Client Classes

   client
   async-client

.. toctree::
   :maxdepth: 2
   :caption: Analytics

   dashboards
   visualizations
   data-views
   saved-objects
   short-urls

.. toctree::
   :maxdepth: 2
   :caption: Alerting

   alerting
   connectors
   cases
   maintenance-windows
   actions

.. toctree::
   :maxdepth: 2
   :caption: Observability

   slos
   synthetics
   uptime
   streams
   apm
   observability-ai-assistant

.. toctree::
   :maxdepth: 2
   :caption: Management

   spaces
   security
   ml
   logstash
   task-manager
   upgrade-assistant
   status

.. toctree::
   :maxdepth: 2
   :caption: AI

   agent-builder
   workflows

.. toctree::
   :maxdepth: 2
   :caption: Fleet

   fleet
   fleet-agents
   fleet-policies
   fleet-epm
   fleet-outputs
   fleet-enrollment

.. toctree::
   :maxdepth: 2
   :caption: Security Solution

   detection-engine
   exception-lists
   lists
   timeline
   endpoint
   entity-analytics
   osquery
   security-ai-assistant
   attack-discovery

.. toctree::
   :maxdepth: 2
   :caption: Error Handling

   exceptions

Overview
--------

The Kibana Python client provides both synchronous and asynchronous
interfaces for interacting with Kibana's REST API. The client is organized
into namespace clients that group related functionality:

Main Clients
^^^^^^^^^^^^

- :class:`~kibana.Kibana` - Synchronous client for Kibana API
- :class:`~kibana.AsyncKibana` - Asynchronous client for Kibana API
- :class:`~kibana.SpaceScopedKibana` - Space-scoped synchronous client
- :class:`~kibana.AsyncSpaceScopedKibana` - Space-scoped asynchronous client

Namespace Clients
^^^^^^^^^^^^^^^^^

Analytics
"""""""""

- :class:`~kibana._sync.client.dashboards.DashboardsClient` (``client.dashboards``) - Manage dashboards as code (tech preview)
- :class:`~kibana._sync.client.visualizations.VisualizationsClient` (``client.visualizations``) - Manage Lens visualizations (tech preview)
- :class:`~kibana._sync.client.data_views.DataViewsClient` (``client.data_views``) - Manage data views and runtime fields
- :class:`~kibana.SavedObjectsClient` (``client.saved_objects``) - Manage saved objects
- :class:`~kibana._sync.client.short_urls.ShortUrlsClient` (``client.short_urls``) - Create and resolve short URLs

Alerting
""""""""

- :class:`~kibana._sync.client.alerting.AlertingClient` (``client.alerting``) - Manage alerting rules and backfills
- :class:`~kibana._sync.client.connectors.ConnectorsClient` (``client.connectors``) - Manage connectors
- :class:`~kibana._sync.client.cases.CasesClient` (``client.cases``) - Open and track cases
- :class:`~kibana._sync.client.maintenance_windows.MaintenanceWindowsClient` (``client.maintenance_windows``) - Suppress rule notifications
- :class:`~kibana.ActionsClient` (``client.actions``) - Deprecated alias of ``client.connectors``

Observability
"""""""""""""

- :class:`~kibana._sync.client.slos.SlosClient` (``client.slos``) - Manage service level objectives
- :class:`~kibana._sync.client.synthetics.SyntheticsClient` (``client.synthetics``) - Manage synthetic monitors
- :class:`~kibana._sync.client.uptime.UptimeClient` (``client.uptime``) - Manage Uptime settings
- :class:`~kibana._sync.client.streams.StreamsClient` (``client.streams``) - Manage streams (tech preview)
- :class:`~kibana._sync.client.apm.ApmClient` (``client.apm``) - APM agent keys, configurations and annotations
- :class:`~kibana._sync.client.observability_ai_assistant.ObservabilityAiAssistantClient` (``client.observability_ai_assistant``) - AI Assistant chat completion

Management
""""""""""

- :class:`~kibana.SpacesClient` (``client.spaces``) - Manage Kibana Spaces
- :class:`~kibana._sync.client.security.SecurityClient` (``client.security``) - Manage roles and sessions
- :class:`~kibana._sync.client.ml.MlClient` (``client.ml``) - Machine learning saved objects
- :class:`~kibana._sync.client.logstash.LogstashClient` (``client.logstash``) - Centrally-managed Logstash pipelines
- :class:`~kibana._sync.client.task_manager.TaskManagerClient` (``client.task_manager``) - Task manager health
- :class:`~kibana._sync.client.upgrade_assistant.UpgradeAssistantClient` (``client.upgrade_assistant``) - Upgrade readiness
- :class:`~kibana._sync.client.status.StatusClient` (``client.status``) - Monitor server health

AI
""

- :class:`~kibana._sync.client.agent_builder.AgentBuilderClient` (``client.agent_builder``) - AI agents, tools, A2A and MCP
- :class:`~kibana._sync.client.workflows.WorkflowsClient` (``client.workflows``) - Automate YAML-defined workflows

Fleet
"""""

- :class:`~kibana._sync.client.fleet.FleetClient` (``client.fleet``) - Fleet setup, settings and health
- :class:`~kibana._sync.client.fleet_agents.FleetAgentsClient` (``client.fleet_agents``) - Elastic Agents, actions and status
- :class:`~kibana._sync.client.fleet_policies.FleetPoliciesClient` (``client.fleet_policies``) - Agent and package policies
- :class:`~kibana._sync.client.fleet_epm.FleetEpmClient` (``client.fleet_epm``) - Elastic Package Manager (integrations)
- :class:`~kibana._sync.client.fleet_outputs.FleetOutputsClient` (``client.fleet_outputs``) - Outputs, Fleet Server hosts, proxies and connectivity
- :class:`~kibana._sync.client.fleet_enrollment.FleetEnrollmentClient` (``client.fleet_enrollment``) - Enrollment keys, tokens and signing

Security Solution
"""""""""""""""""

- :class:`~kibana._sync.client.detection_engine.DetectionEngineClient` (``client.detection_engine``) - Detection rules and alerts
- :class:`~kibana._sync.client.exception_lists.ExceptionListsClient` (``client.exception_lists``) - Exception lists and endpoint exceptions
- :class:`~kibana._sync.client.lists.ListsClient` (``client.lists``) - Value lists and list items
- :class:`~kibana._sync.client.timeline.TimelineClient` (``client.timeline``) - Timelines, notes and pinned events
- :class:`~kibana._sync.client.endpoint.EndpointClient` (``client.endpoint``) - Endpoint management and response actions
- :class:`~kibana._sync.client.entity_analytics.EntityAnalyticsClient` (``client.entity_analytics``) - Entity analytics, entity store and asset criticality
- :class:`~kibana._sync.client.osquery.OsqueryClient` (``client.osquery``) - Osquery packs, saved queries and live queries
- :class:`~kibana._sync.client.security_ai_assistant.SecurityAiAssistantClient` (``client.security_ai_assistant``) - Security AI Assistant conversations and chat
- :class:`~kibana._sync.client.attack_discovery.AttackDiscoveryClient` (``client.attack_discovery``) - AI attack discoveries and schedules

Exception Classes
^^^^^^^^^^^^^^^^^

- :class:`~kibana.KibanaException` - Base exception class
- :class:`~kibana.ApiError` - API-level errors
- :class:`~kibana.TransportError` - Transport-level errors
- :class:`~kibana.SpaceError` - Space-related errors

Quick Start
-----------

Synchronous Client
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from kibana import Kibana

   # Initialize client
   client = Kibana(
       "http://localhost:5601",
       api_key="your_api_key"
   )

   # Use namespace clients
   status = client.status.get_status()
   dashboards = client.dashboards.get_all()
   connectors = client.connectors.get_all()
   spaces = client.spaces.get_all()

   # Close client
   client.close()

Asynchronous Client
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from kibana import AsyncKibana
   import asyncio

   async def main():
       # Initialize async client
       async with AsyncKibana("http://localhost:5601") as client:
           # Use namespace clients with await
           status = await client.status.get_status()
           dashboards = await client.dashboards.get_all()
           connectors = await client.connectors.get_all()
           spaces = await client.spaces.get_all()

   asyncio.run(main())

Space-Scoped Operations
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from kibana import Kibana

   client = Kibana("http://localhost:5601")

   # Create space-scoped client
   marketing_client = client.space("marketing")

   # All operations are scoped to "marketing" space
   dashboard = marketing_client.dashboards.create(
       title="Marketing KPIs"
   )
   connector = marketing_client.connectors.create(
       name="Marketing Webhook",
       connector_type_id=".webhook",
       config={"url": "https://example.com/webhook"}
   )

Error Handling
^^^^^^^^^^^^^^

.. code-block:: python

   from kibana import Kibana
   from kibana.exceptions import (
       NotFoundError,
       BadRequestError,
       SpaceNotFoundError
   )

   client = Kibana("http://localhost:5601")

   try:
       connector = client.connectors.get(id="my-connector")
   except NotFoundError:
       print("Connector not found")
   except BadRequestError as e:
       print(f"Invalid request: {e.message}")
   except SpaceNotFoundError as e:
       print(f"Space not found: {e.space_id}")

See Also
--------

- :doc:`../installation` - Installation instructions
- :doc:`../quickstart` - Quick start guide
- :doc:`../user-guide/index` - User guide with detailed examples
- :doc:`../examples/index` - Example code and patterns
