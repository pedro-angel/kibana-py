"""Asynchronous Kibana client."""

import logging
from collections.abc import Mapping
from typing import Any

from elastic_transport import AsyncTransport

from kibana._async.client._base import DEFAULT, AsyncBaseClient, DefaultType
from kibana._async.client.actions import AsyncActionsClient
from kibana._async.client.agent_builder import AsyncAgentBuilderClient
from kibana._async.client.alerting import AsyncAlertingClient
from kibana._async.client.apm import AsyncApmClient
from kibana._async.client.attack_discovery import AsyncAttackDiscoveryClient
from kibana._async.client.cases import AsyncCasesClient
from kibana._async.client.connectors import AsyncConnectorsClient
from kibana._async.client.dashboards import AsyncDashboardsClient
from kibana._async.client.data_views import AsyncDataViewsClient
from kibana._async.client.detection_engine import AsyncDetectionEngineClient
from kibana._async.client.endpoint import AsyncEndpointClient
from kibana._async.client.entity_analytics import AsyncEntityAnalyticsClient
from kibana._async.client.exception_lists import AsyncExceptionListsClient
from kibana._async.client.fleet import AsyncFleetClient
from kibana._async.client.fleet_agents import AsyncFleetAgentsClient
from kibana._async.client.fleet_enrollment import AsyncFleetEnrollmentClient
from kibana._async.client.fleet_epm import AsyncFleetEpmClient
from kibana._async.client.fleet_outputs import AsyncFleetOutputsClient
from kibana._async.client.fleet_policies import AsyncFleetPoliciesClient
from kibana._async.client.lists import AsyncListsClient
from kibana._async.client.logstash import AsyncLogstashClient
from kibana._async.client.maintenance_windows import AsyncMaintenanceWindowsClient
from kibana._async.client.ml import AsyncMlClient
from kibana._async.client.observability_ai_assistant import (
    AsyncObservabilityAiAssistantClient,
)
from kibana._async.client.osquery import AsyncOsqueryClient
from kibana._async.client.saved_objects import AsyncSavedObjectsClient
from kibana._async.client.security import AsyncSecurityClient
from kibana._async.client.security_ai_assistant import AsyncSecurityAiAssistantClient
from kibana._async.client.short_urls import AsyncShortUrlsClient
from kibana._async.client.slos import AsyncSlosClient
from kibana._async.client.spaces import AsyncSpacesClient
from kibana._async.client.status import AsyncStatusClient
from kibana._async.client.streams import AsyncStreamsClient
from kibana._async.client.synthetics import AsyncSyntheticsClient
from kibana._async.client.task_manager import AsyncTaskManagerClient
from kibana._async.client.timeline import AsyncTimelineClient
from kibana._async.client.upgrade_assistant import AsyncUpgradeAssistantClient
from kibana._async.client.uptime import AsyncUptimeClient
from kibana._async.client.visualizations import AsyncVisualizationsClient
from kibana._async.client.workflows import AsyncWorkflowsClient
from kibana._rate_limiter import AsyncRateLimiter
from kibana._sync.client import _build_node_configs, _build_node_options
from kibana.exceptions import SpaceNotFoundError
from kibana.serializer import DEFAULT_SERIALIZERS

__all__ = ["AsyncKibana", "AsyncSpaceScopedKibana", "DEFAULT", "DefaultType"]

# Set up logger
logger = logging.getLogger("kibana")


class AsyncKibana(AsyncBaseClient):
    """
    Asynchronous client for Kibana.

    Provides a Pythonic async interface to interact with Kibana's REST APIs.
    Each API group is exposed as a namespace attribute (``client.dashboards``,
    ``client.spaces``, ``client.alerting``, ...), mirroring the structure of
    the official Kibana API reference.

    Example usage:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana(
        ...     hosts=["http://localhost:5601"],
        ...     api_key="your_api_key"
        ... )
        >>> # Use the client
        >>> await client.close()

    Or use as an async context manager:
        >>> async with AsyncKibana(hosts=["http://localhost:5601"]) as client:
        ...     # Use the client
        ...     pass
    """

    # Namespace clients (wired eagerly in __init__)
    actions: AsyncActionsClient
    agent_builder: AsyncAgentBuilderClient
    alerting: AsyncAlertingClient
    apm: AsyncApmClient
    attack_discovery: AsyncAttackDiscoveryClient
    cases: AsyncCasesClient
    connectors: AsyncConnectorsClient
    dashboards: AsyncDashboardsClient
    data_views: AsyncDataViewsClient
    detection_engine: AsyncDetectionEngineClient
    endpoint: AsyncEndpointClient
    entity_analytics: AsyncEntityAnalyticsClient
    exception_lists: AsyncExceptionListsClient
    fleet: AsyncFleetClient
    fleet_agents: AsyncFleetAgentsClient
    fleet_enrollment: AsyncFleetEnrollmentClient
    fleet_epm: AsyncFleetEpmClient
    fleet_outputs: AsyncFleetOutputsClient
    fleet_policies: AsyncFleetPoliciesClient
    lists: AsyncListsClient
    logstash: AsyncLogstashClient
    maintenance_windows: AsyncMaintenanceWindowsClient
    ml: AsyncMlClient
    observability_ai_assistant: AsyncObservabilityAiAssistantClient
    osquery: AsyncOsqueryClient
    saved_objects: AsyncSavedObjectsClient
    security: AsyncSecurityClient
    security_ai_assistant: AsyncSecurityAiAssistantClient
    short_urls: AsyncShortUrlsClient
    slos: AsyncSlosClient
    spaces: AsyncSpacesClient
    status: AsyncStatusClient
    streams: AsyncStreamsClient
    synthetics: AsyncSyntheticsClient
    task_manager: AsyncTaskManagerClient
    timeline: AsyncTimelineClient
    upgrade_assistant: AsyncUpgradeAssistantClient
    uptime: AsyncUptimeClient
    visualizations: AsyncVisualizationsClient
    workflows: AsyncWorkflowsClient

    def __init__(
        self,
        hosts: str | list[str | dict[str, Any]] | None = None,
        *,
        cloud_id: str | None = None,
        api_key: str | tuple[str, str] | None = None,
        basic_auth: tuple[str, str] | None = None,
        bearer_auth: str | None = None,
        headers: DefaultType | Mapping[str, str] = DEFAULT,
        request_timeout: DefaultType | None | float = DEFAULT,
        verify_certs: DefaultType | bool = DEFAULT,
        ca_certs: DefaultType | str = DEFAULT,
        client_cert: DefaultType | str = DEFAULT,
        client_key: DefaultType | str = DEFAULT,
        ssl_assert_hostname: DefaultType | str = DEFAULT,
        ssl_assert_fingerprint: DefaultType | str = DEFAULT,
        ssl_version: DefaultType | int = DEFAULT,
        ssl_context: DefaultType | Any = DEFAULT,
        ssl_show_warn: DefaultType | bool = DEFAULT,
        max_retries: DefaultType | int = DEFAULT,
        retry_on_status: DefaultType | list[int] = DEFAULT,
        retry_on_timeout: DefaultType | bool = DEFAULT,
        connections_per_node: DefaultType | int = DEFAULT,
        dead_node_backoff_factor: DefaultType | float = DEFAULT,
        max_dead_node_backoff: DefaultType | float = DEFAULT,
        node_class: DefaultType | Any = DEFAULT,
        node_pool_class: DefaultType | Any = DEFAULT,
        randomize_nodes_in_pool: DefaultType | bool = DEFAULT,
        max_requests_per_second: float | None = None,
        _transport: AsyncTransport | None = None,
    ) -> None:
        """
        Initialize AsyncKibana client.

        :param hosts: List of Kibana nodes to connect to. Can be a single string
            or a list of strings/dicts. Examples:
            - "http://localhost:5601"
            - ["http://localhost:5601", "http://localhost:5602"]
            - [{"host": "localhost", "port": 5601, "scheme": "http"}]
        :param cloud_id: Cloud ID for Elastic Cloud deployments
        :param api_key: API key for authentication. Can be:
            - Base64-encoded string
            - Tuple of (id, api_key)
        :param basic_auth: Basic authentication credentials as (username, password)
        :param bearer_auth: Bearer token for authentication
        :param headers: Custom headers to include in all requests
        :param request_timeout: Request timeout in seconds
        :param verify_certs: Whether to verify SSL certificates
        :param ca_certs: Path to CA certificate bundle
        :param client_cert: Path to client certificate
        :param client_key: Path to client private key
        :param ssl_assert_hostname: Hostname to verify in SSL certificate
        :param ssl_assert_fingerprint: SSL certificate fingerprint to verify
        :param ssl_version: SSL/TLS version to use
        :param ssl_context: Custom SSL context
        :param ssl_show_warn: Whether to show SSL warnings
        :param max_retries: Maximum number of retries for failed requests
        :param retry_on_status: HTTP status codes to retry on
        :param retry_on_timeout: Whether to retry on timeout
        :param connections_per_node: Number of connections per node
        :param dead_node_backoff_factor: Backoff factor for dead nodes
        :param max_dead_node_backoff: Maximum backoff time for dead nodes
        :param node_class: Custom node class
        :param node_pool_class: Custom node pool class
        :param randomize_nodes_in_pool: Whether to randomize node order
        :param max_requests_per_second: Optional rate limit (requests/sec).
            When set, outgoing requests are throttled using a token-bucket
            algorithm to prevent overwhelming the Kibana cluster.
        :param _transport: Pre-configured AsyncTransport instance (for testing)
        """
        # If transport is provided (for testing), use it directly
        if _transport is not None:
            super().__init__(_transport=_transport)
            # Store auth credentials for options() method
            self._api_key = api_key
            self._basic_auth = basic_auth
            self._bearer_auth = bearer_auth
            self._request_timeout = (
                request_timeout
                if not isinstance(request_timeout, DefaultType)
                else None
            )
            self._custom_headers = (
                headers if not isinstance(headers, DefaultType) else None
            )
            if max_requests_per_second is not None:
                self._rate_limiter = AsyncRateLimiter(max_requests_per_second)
            self._wire_namespaces()
            return

        # Validate that either hosts or cloud_id is provided
        if hosts is None and cloud_id is None:
            raise ValueError("Either 'hosts' or 'cloud_id' must be provided")

        # Build node configurations, applying SSL/connection options
        node_options = _build_node_options(
            verify_certs=verify_certs,
            ca_certs=ca_certs,
            client_cert=client_cert,
            client_key=client_key,
            ssl_assert_hostname=ssl_assert_hostname,
            ssl_assert_fingerprint=ssl_assert_fingerprint,
            ssl_version=ssl_version,
            ssl_context=ssl_context,
            ssl_show_warn=ssl_show_warn,
            connections_per_node=connections_per_node,
        )
        node_configs = _build_node_configs(hosts, cloud_id, node_options)

        # Build transport options
        transport_kwargs: dict[str, Any] = {
            "node_configs": node_configs,
            "serializers": DEFAULT_SERIALIZERS,
        }

        # Add retry options (these are valid Transport parameters)
        if not isinstance(max_retries, DefaultType):
            transport_kwargs["max_retries"] = max_retries
        if not isinstance(retry_on_status, DefaultType):
            transport_kwargs["retry_on_status"] = retry_on_status
        if not isinstance(retry_on_timeout, DefaultType):
            transport_kwargs["retry_on_timeout"] = retry_on_timeout

        # Add node pool options (these are valid Transport parameters)
        if not isinstance(node_class, DefaultType):
            transport_kwargs["node_class"] = node_class
        if not isinstance(node_pool_class, DefaultType):
            transport_kwargs["node_pool_class"] = node_pool_class
        if not isinstance(randomize_nodes_in_pool, DefaultType):
            transport_kwargs["randomize_nodes_in_pool"] = randomize_nodes_in_pool
        if not isinstance(dead_node_backoff_factor, DefaultType):
            transport_kwargs["dead_node_backoff_factor"] = dead_node_backoff_factor
        if not isinstance(max_dead_node_backoff, DefaultType):
            transport_kwargs["max_dead_node_backoff"] = max_dead_node_backoff

        # Create AsyncTransport instance
        transport = AsyncTransport(**transport_kwargs)

        # Initialize base client with transport
        super().__init__(_transport=transport)

        # Store authentication credentials
        self._api_key = api_key
        self._basic_auth = basic_auth
        self._bearer_auth = bearer_auth

        # Store request timeout
        if not isinstance(request_timeout, DefaultType):
            self._request_timeout = request_timeout

        # Store custom headers
        if not isinstance(headers, DefaultType):
            self._custom_headers = headers

        logger.info("AsyncKibana client initialized with %d node(s)", len(node_configs))

        # Set up rate limiting if configured
        if max_requests_per_second is not None:
            self._rate_limiter = AsyncRateLimiter(max_requests_per_second)
            logger.info(
                "Rate limiting enabled: %.1f requests/sec", max_requests_per_second
            )

        self._wire_namespaces()

    def _wire_namespaces(self) -> None:
        """Attach one client instance per Kibana API namespace."""
        self.actions = AsyncActionsClient(self)
        self.agent_builder = AsyncAgentBuilderClient(self)
        self.alerting = AsyncAlertingClient(self)
        self.apm = AsyncApmClient(self)
        self.attack_discovery = AsyncAttackDiscoveryClient(self)
        self.cases = AsyncCasesClient(self)
        self.connectors = AsyncConnectorsClient(self)
        self.dashboards = AsyncDashboardsClient(self)
        self.data_views = AsyncDataViewsClient(self)
        self.detection_engine = AsyncDetectionEngineClient(self)
        self.endpoint = AsyncEndpointClient(self)
        self.entity_analytics = AsyncEntityAnalyticsClient(self)
        self.exception_lists = AsyncExceptionListsClient(self)
        self.fleet = AsyncFleetClient(self)
        self.fleet_agents = AsyncFleetAgentsClient(self)
        self.fleet_enrollment = AsyncFleetEnrollmentClient(self)
        self.fleet_epm = AsyncFleetEpmClient(self)
        self.fleet_outputs = AsyncFleetOutputsClient(self)
        self.fleet_policies = AsyncFleetPoliciesClient(self)
        self.lists = AsyncListsClient(self)
        self.logstash = AsyncLogstashClient(self)
        self.maintenance_windows = AsyncMaintenanceWindowsClient(self)
        self.ml = AsyncMlClient(self)
        self.observability_ai_assistant = AsyncObservabilityAiAssistantClient(self)
        self.osquery = AsyncOsqueryClient(self)
        self.saved_objects = AsyncSavedObjectsClient(self)
        self.security = AsyncSecurityClient(self)
        self.security_ai_assistant = AsyncSecurityAiAssistantClient(self)
        self.short_urls = AsyncShortUrlsClient(self)
        self.slos = AsyncSlosClient(self)
        self.spaces = AsyncSpacesClient(self)
        self.status = AsyncStatusClient(self)
        self.streams = AsyncStreamsClient(self)
        self.synthetics = AsyncSyntheticsClient(self)
        self.task_manager = AsyncTaskManagerClient(self)
        self.timeline = AsyncTimelineClient(self)
        self.upgrade_assistant = AsyncUpgradeAssistantClient(self)
        self.uptime = AsyncUptimeClient(self)
        self.visualizations = AsyncVisualizationsClient(self)
        self.workflows = AsyncWorkflowsClient(self)

    async def close(self) -> None:
        """
        Close the client and release resources.

        This closes all connections in the connection pool.
        After calling close(), the client should not be used.
        """
        try:
            await self._transport.close()
            logger.debug("AsyncKibana client closed")
        except Exception as e:
            logger.warning("Error closing AsyncKibana client: %s", e)

    async def __aenter__(self) -> AsyncKibana:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager and close client."""
        await self.close()

    async def space(
        self, space_id: str, validate: bool = True
    ) -> AsyncSpaceScopedKibana:
        """
        Create a space-scoped client instance.

        This method creates a new client instance that automatically operates within
        the specified space context. All operations performed through the returned
        client will be scoped to the specified space.

        .. versionchanged:: 0.2.0
            This method is now a coroutine so that ``validate=True`` can
            actually check the space against the server (previously the check
            was silently skipped). Call it as ``await client.space("id")``.

        :param space_id: The ID of the space to scope operations to
        :param validate: Whether to validate that the space exists (default: True)
        :return: AsyncSpaceScopedKibana instance scoped to the specified space
        :raises SpaceNotFoundError: If validate=True and the space doesn't exist
        :raises InvalidSpaceIdError: If the space_id format is invalid

        Example:
            >>> # Create a space-scoped client with validation
            >>> marketing_client = await client.space("marketing")
            >>>
            >>> # Create a dashboard in the marketing space
            >>> dashboard = await marketing_client.dashboards.create(
            ...     title="Marketing KPIs"
            ... )
            >>>
            >>> # Create space-scoped client without validation (for performance)
            >>> fast_client = await client.space("marketing", validate=False)
        """
        scoped = AsyncSpaceScopedKibana(self, space_id, validate)
        if validate:
            await scoped._validate_space_on_creation()
        return scoped

    def __repr__(self) -> str:
        """Return string representation of client."""
        return "<AsyncKibana()>"


class AsyncSpaceScopedKibana:
    """
    Space-scoped async client that delegates to main client with space context.

    This class provides the same API surface as the main AsyncKibana client but
    automatically scopes all operations to a specific space. All child clients
    (dashboards, saved_objects, alerting, etc.) created through this instance
    inherit the space context and validation settings. Namespaces that are not
    space-aware (spaces, status, security, task_manager, upgrade_assistant,
    logstash) delegate to the parent client unscoped.

    Example:
        >>> # Create space-scoped client with validation
        >>> marketing_client = await client.space("marketing")
        >>>
        >>> # All operations are automatically scoped to "marketing" space
        >>> dashboard = await marketing_client.dashboards.create(
        ...     title="Marketing KPIs"
        ... )
        >>>
        >>> # Create space-scoped client without validation for performance
        >>> fast_client = await client.space("marketing", validate=False)
    """

    # Space-scoped namespace clients (wired eagerly in __init__)
    actions: AsyncActionsClient
    agent_builder: AsyncAgentBuilderClient
    alerting: AsyncAlertingClient
    apm: AsyncApmClient
    attack_discovery: AsyncAttackDiscoveryClient
    cases: AsyncCasesClient
    connectors: AsyncConnectorsClient
    dashboards: AsyncDashboardsClient
    data_views: AsyncDataViewsClient
    detection_engine: AsyncDetectionEngineClient
    endpoint: AsyncEndpointClient
    entity_analytics: AsyncEntityAnalyticsClient
    exception_lists: AsyncExceptionListsClient
    fleet: AsyncFleetClient
    fleet_agents: AsyncFleetAgentsClient
    fleet_enrollment: AsyncFleetEnrollmentClient
    fleet_epm: AsyncFleetEpmClient
    fleet_outputs: AsyncFleetOutputsClient
    fleet_policies: AsyncFleetPoliciesClient
    lists: AsyncListsClient
    maintenance_windows: AsyncMaintenanceWindowsClient
    ml: AsyncMlClient
    observability_ai_assistant: AsyncObservabilityAiAssistantClient
    osquery: AsyncOsqueryClient
    saved_objects: AsyncSavedObjectsClient
    security_ai_assistant: AsyncSecurityAiAssistantClient
    short_urls: AsyncShortUrlsClient
    slos: AsyncSlosClient
    streams: AsyncStreamsClient
    synthetics: AsyncSyntheticsClient
    timeline: AsyncTimelineClient
    uptime: AsyncUptimeClient
    visualizations: AsyncVisualizationsClient
    workflows: AsyncWorkflowsClient

    def __init__(
        self, client: AsyncKibana, space_id: str, validate: bool = True
    ) -> None:
        """
        Initialize space-scoped async client.

        Note: space existence validation is performed by
        ``AsyncKibana.space()`` (a coroutine), not by this constructor.

        :param client: The main AsyncKibana client to delegate to
        :param space_id: The space ID to scope operations to
        :param validate: Whether space validation is enabled for namespaces
        """
        self._client = client
        self._space_id = space_id
        self._validate = validate

        # Wire space-scoped namespace clients
        def scoped(cls: type) -> Any:
            return cls(
                client,
                default_space_id=space_id,
                validate_spaces=validate,
            )

        self.actions = scoped(AsyncActionsClient)
        self.agent_builder = scoped(AsyncAgentBuilderClient)
        self.alerting = scoped(AsyncAlertingClient)
        self.apm = scoped(AsyncApmClient)
        self.attack_discovery = scoped(AsyncAttackDiscoveryClient)
        self.cases = scoped(AsyncCasesClient)
        self.connectors = scoped(AsyncConnectorsClient)
        self.dashboards = scoped(AsyncDashboardsClient)
        self.data_views = scoped(AsyncDataViewsClient)
        self.detection_engine = scoped(AsyncDetectionEngineClient)
        self.endpoint = scoped(AsyncEndpointClient)
        self.entity_analytics = scoped(AsyncEntityAnalyticsClient)
        self.exception_lists = scoped(AsyncExceptionListsClient)
        self.fleet = scoped(AsyncFleetClient)
        self.fleet_agents = scoped(AsyncFleetAgentsClient)
        self.fleet_enrollment = scoped(AsyncFleetEnrollmentClient)
        self.fleet_epm = scoped(AsyncFleetEpmClient)
        self.fleet_outputs = scoped(AsyncFleetOutputsClient)
        self.fleet_policies = scoped(AsyncFleetPoliciesClient)
        self.lists = scoped(AsyncListsClient)
        self.maintenance_windows = scoped(AsyncMaintenanceWindowsClient)
        self.ml = scoped(AsyncMlClient)
        self.observability_ai_assistant = scoped(AsyncObservabilityAiAssistantClient)
        self.osquery = scoped(AsyncOsqueryClient)
        self.saved_objects = scoped(AsyncSavedObjectsClient)
        self.security_ai_assistant = scoped(AsyncSecurityAiAssistantClient)
        self.short_urls = scoped(AsyncShortUrlsClient)
        self.slos = scoped(AsyncSlosClient)
        self.streams = scoped(AsyncStreamsClient)
        self.synthetics = scoped(AsyncSyntheticsClient)
        self.timeline = scoped(AsyncTimelineClient)
        self.uptime = scoped(AsyncUptimeClient)
        self.visualizations = scoped(AsyncVisualizationsClient)
        self.workflows = scoped(AsyncWorkflowsClient)

    async def _validate_space_on_creation(self) -> None:
        """
        Validate space exists when creating space-scoped client.

        :raises SpaceNotFoundError: If the space doesn't exist
        """
        try:
            await self._client.spaces.get(id=self._space_id)
        except Exception as e:
            # Check if this is a "not found" error
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                raise SpaceNotFoundError(self._space_id)
            else:
                # Re-raise other errors (auth, network, etc.)
                raise

    @property
    def spaces(self) -> AsyncSpacesClient:
        """Get AsyncSpacesClient (not space-scoped; manages spaces themselves)."""
        return self._client.spaces

    @property
    def status(self) -> AsyncStatusClient:
        """Get AsyncStatusClient (not space-scoped; server-wide status)."""
        return self._client.status

    @property
    def security(self) -> AsyncSecurityClient:
        """Get AsyncSecurityClient (not space-scoped; roles and sessions are global)."""
        return self._client.security

    @property
    def task_manager(self) -> AsyncTaskManagerClient:
        """Get AsyncTaskManagerClient (not space-scoped; server-wide health)."""
        return self._client.task_manager

    @property
    def upgrade_assistant(self) -> AsyncUpgradeAssistantClient:
        """Get AsyncUpgradeAssistantClient (not space-scoped; cluster-wide status)."""
        return self._client.upgrade_assistant

    @property
    def logstash(self) -> AsyncLogstashClient:
        """Get AsyncLogstashClient (not space-scoped; pipelines are global)."""
        return self._client.logstash

    async def close(self) -> None:
        """
        Close the underlying client and release resources.

        This delegates to the main AsyncKibana client's close() method.
        """
        await self._client.close()

    async def __aenter__(self) -> AsyncSpaceScopedKibana:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager and close client."""
        await self.close()

    def __repr__(self) -> str:
        """Return string representation of space-scoped client."""
        return f"<AsyncSpaceScopedKibana(space_id='{self._space_id}', validate={self._validate})>"
