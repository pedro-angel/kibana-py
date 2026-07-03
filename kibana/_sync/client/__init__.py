"""Synchronous Kibana client."""

import logging
from collections.abc import Mapping
from typing import Any

from elastic_transport import NodeConfig, Transport
from elastic_transport.client_utils import parse_cloud_id

from kibana._rate_limiter import RateLimiter
from kibana._sync.client._base import DEFAULT, BaseClient, DefaultType
from kibana._sync.client.actions import ActionsClient
from kibana._sync.client.agent_builder import AgentBuilderClient
from kibana._sync.client.alerting import AlertingClient
from kibana._sync.client.apm import ApmClient
from kibana._sync.client.cases import CasesClient
from kibana._sync.client.connectors import ConnectorsClient
from kibana._sync.client.dashboards import DashboardsClient
from kibana._sync.client.data_views import DataViewsClient
from kibana._sync.client.logstash import LogstashClient
from kibana._sync.client.maintenance_windows import MaintenanceWindowsClient
from kibana._sync.client.ml import MlClient
from kibana._sync.client.observability_ai_assistant import (
    ObservabilityAiAssistantClient,
)
from kibana._sync.client.saved_objects import SavedObjectsClient
from kibana._sync.client.security import SecurityClient
from kibana._sync.client.short_urls import ShortUrlsClient
from kibana._sync.client.slos import SlosClient
from kibana._sync.client.spaces import SpacesClient
from kibana._sync.client.status import StatusClient
from kibana._sync.client.streams import StreamsClient
from kibana._sync.client.synthetics import SyntheticsClient
from kibana._sync.client.task_manager import TaskManagerClient
from kibana._sync.client.upgrade_assistant import UpgradeAssistantClient
from kibana._sync.client.uptime import UptimeClient
from kibana._sync.client.visualizations import VisualizationsClient
from kibana._sync.client.workflows import WorkflowsClient
from kibana.exceptions import SpaceNotFoundError
from kibana.serializer import DEFAULT_SERIALIZERS

__all__ = ["Kibana", "SpaceScopedKibana", "DEFAULT", "DefaultType"]

# Set up logger
logger = logging.getLogger("kibana")


class Kibana(BaseClient):
    """
    Synchronous client for Kibana.

    Provides a Pythonic interface to interact with Kibana's REST APIs.
    Each API group is exposed as a namespace attribute (``client.dashboards``,
    ``client.spaces``, ``client.alerting``, ...), mirroring the structure of
    the official Kibana API reference.

    Example usage:
        >>> from kibana import Kibana
        >>> client = Kibana(
        ...     hosts=["http://localhost:5601"],
        ...     api_key="your_api_key"
        ... )
        >>> # Use the client
        >>> client.close()

    Or use as a context manager:
        >>> with Kibana(hosts=["http://localhost:5601"]) as client:
        ...     # Use the client
        ...     pass
    """

    # Namespace clients (wired eagerly in __init__)
    actions: ActionsClient
    agent_builder: AgentBuilderClient
    alerting: AlertingClient
    apm: ApmClient
    cases: CasesClient
    connectors: ConnectorsClient
    dashboards: DashboardsClient
    data_views: DataViewsClient
    logstash: LogstashClient
    maintenance_windows: MaintenanceWindowsClient
    ml: MlClient
    observability_ai_assistant: ObservabilityAiAssistantClient
    saved_objects: SavedObjectsClient
    security: SecurityClient
    short_urls: ShortUrlsClient
    slos: SlosClient
    spaces: SpacesClient
    status: StatusClient
    streams: StreamsClient
    synthetics: SyntheticsClient
    task_manager: TaskManagerClient
    upgrade_assistant: UpgradeAssistantClient
    uptime: UptimeClient
    visualizations: VisualizationsClient
    workflows: WorkflowsClient

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
        _transport: Transport | None = None,
    ) -> None:
        """
        Initialize Kibana client.

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
        :param _transport: Pre-configured Transport instance (for testing)
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
                self._rate_limiter = RateLimiter(max_requests_per_second)
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

        # Create Transport instance
        transport = Transport(**transport_kwargs)

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

        logger.info("Kibana client initialized with %d node(s)", len(node_configs))

        # Set up rate limiting if configured
        if max_requests_per_second is not None:
            self._rate_limiter = RateLimiter(max_requests_per_second)
            logger.info(
                "Rate limiting enabled: %.1f requests/sec", max_requests_per_second
            )

        self._wire_namespaces()

    def _wire_namespaces(self) -> None:
        """Attach one client instance per Kibana API namespace."""
        self.actions = ActionsClient(self)
        self.agent_builder = AgentBuilderClient(self)
        self.alerting = AlertingClient(self)
        self.apm = ApmClient(self)
        self.cases = CasesClient(self)
        self.connectors = ConnectorsClient(self)
        self.dashboards = DashboardsClient(self)
        self.data_views = DataViewsClient(self)
        self.logstash = LogstashClient(self)
        self.maintenance_windows = MaintenanceWindowsClient(self)
        self.ml = MlClient(self)
        self.observability_ai_assistant = ObservabilityAiAssistantClient(self)
        self.saved_objects = SavedObjectsClient(self)
        self.security = SecurityClient(self)
        self.short_urls = ShortUrlsClient(self)
        self.slos = SlosClient(self)
        self.spaces = SpacesClient(self)
        self.status = StatusClient(self)
        self.streams = StreamsClient(self)
        self.synthetics = SyntheticsClient(self)
        self.task_manager = TaskManagerClient(self)
        self.upgrade_assistant = UpgradeAssistantClient(self)
        self.uptime = UptimeClient(self)
        self.visualizations = VisualizationsClient(self)
        self.workflows = WorkflowsClient(self)

    def close(self) -> None:
        """
        Close the client and release resources.

        This closes all connections in the connection pool.
        After calling close(), the client should not be used.
        """
        try:
            self._transport.close()
            logger.debug("Kibana client closed")
        except Exception as e:
            logger.warning("Error closing Kibana client: %s", e)

    def __enter__(self) -> Kibana:
        """Enter context manager."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager and close client."""
        self.close()

    def __repr__(self) -> str:
        """Return string representation of client."""
        return "<Kibana()>"

    def space(self, space_id: str, validate: bool = True) -> SpaceScopedKibana:
        """
        Create a space-scoped client instance.

        This method creates a new client instance that automatically operates within
        the specified space context. All operations performed through the returned
        client will be scoped to the specified space.

        :param space_id: The ID of the space to scope operations to
        :param validate: Whether to validate that the space exists (default: True)
        :return: SpaceScopedKibana instance scoped to the specified space
        :raises SpaceNotFoundError: If validate=True and the space doesn't exist
        :raises InvalidSpaceIdError: If the space_id format is invalid

        Example:
            >>> # Create a space-scoped client with validation
            >>> marketing_client = client.space("marketing")
            >>>
            >>> # Create a dashboard in the marketing space
            >>> dashboard = marketing_client.dashboards.create(
            ...     title="Marketing KPIs"
            ... )
            >>>
            >>> # Create space-scoped client without validation (for performance)
            >>> fast_client = client.space("marketing", validate=False)
        """
        return SpaceScopedKibana(self, space_id, validate)


def _build_node_options(
    *,
    verify_certs: DefaultType | bool,
    ca_certs: DefaultType | str,
    client_cert: DefaultType | str,
    client_key: DefaultType | str,
    ssl_assert_hostname: DefaultType | str,
    ssl_assert_fingerprint: DefaultType | str,
    ssl_version: DefaultType | int,
    ssl_context: DefaultType | Any,
    ssl_show_warn: DefaultType | bool,
    connections_per_node: DefaultType | int,
) -> dict[str, Any]:
    """Collect per-node (SSL/connection) options into NodeConfig kwargs."""
    options: dict[str, Any] = {}
    candidates = {
        "verify_certs": verify_certs,
        "ca_certs": ca_certs,
        "client_cert": client_cert,
        "client_key": client_key,
        "ssl_assert_hostname": ssl_assert_hostname,
        "ssl_assert_fingerprint": ssl_assert_fingerprint,
        "ssl_version": ssl_version,
        "ssl_context": ssl_context,
        "ssl_show_warn": ssl_show_warn,
        "connections_per_node": connections_per_node,
    }
    for key, value in candidates.items():
        if not isinstance(value, DefaultType):
            options[key] = value
    return options


def _build_node_configs(
    hosts: str | list[str | dict[str, Any]] | None,
    cloud_id: str | None,
    node_options: dict[str, Any] | None = None,
) -> list[NodeConfig]:
    """
    Build NodeConfig objects from hosts or cloud_id.

    :param hosts: Host specifications
    :param cloud_id: Cloud ID for Elastic Cloud
    :param node_options: Extra NodeConfig options (SSL, connection pool)
    :return: List of NodeConfig objects
    """
    node_options = node_options or {}

    if cloud_id is not None:
        # Use the canonical elastic-transport parser: it handles ports
        # embedded in the cloud host (e.g. "host:9243$es_uuid$kibana_uuid")
        try:
            parsed = parse_cloud_id(cloud_id)
        except Exception as e:
            raise ValueError(f"Failed to parse cloud_id: {e}") from e
        if parsed.kibana_address is None:
            raise ValueError(f"Cloud ID does not contain a Kibana address: {cloud_id}")
        kibana_host, kibana_port = parsed.kibana_address
        return [
            NodeConfig(
                scheme="https", host=kibana_host, port=kibana_port, **node_options
            )
        ]

    # Parse hosts
    if isinstance(hosts, str):
        hosts = [hosts]

    if hosts is None:
        raise ValueError("hosts cannot be None when cloud_id is not provided")

    node_configs = []
    for host in hosts:
        if isinstance(host, str):
            # Parse URL string manually
            from urllib.parse import urlparse

            parsed_url = urlparse(host)

            scheme = parsed_url.scheme or "http"
            hostname = parsed_url.hostname or "localhost"
            port = parsed_url.port or (443 if scheme == "https" else 5601)

            node_config = NodeConfig(
                scheme=scheme,
                host=hostname,
                port=port,
                path_prefix=(
                    parsed_url.path
                    if parsed_url.path and parsed_url.path != "/"
                    else ""
                ),
                **node_options,
            )
            node_configs.append(node_config)
        elif isinstance(host, dict):
            # Create NodeConfig from dict (explicit keys win over shared options)
            node_config = NodeConfig(**{**node_options, **host})
            node_configs.append(node_config)
        else:
            raise ValueError(f"Invalid host specification: {host}")

    return node_configs


class SpaceScopedKibana:
    """
    Space-scoped client that delegates to main client with space context.

    This class provides the same API surface as the main Kibana client but
    automatically scopes all operations to a specific space. All child clients
    (dashboards, saved_objects, alerting, etc.) created through this instance
    inherit the space context and validation settings. Namespaces that are not
    space-aware (spaces, status, security, task_manager, upgrade_assistant,
    logstash) delegate to the parent client unscoped.

    Example:
        >>> # Create space-scoped client with validation
        >>> marketing_client = client.space("marketing")
        >>>
        >>> # All operations are automatically scoped to "marketing" space
        >>> dashboard = marketing_client.dashboards.create(
        ...     title="Marketing KPIs"
        ... )
        >>>
        >>> # Create space-scoped client without validation for performance
        >>> fast_client = client.space("marketing", validate=False)
    """

    # Space-scoped namespace clients (wired eagerly in __init__)
    actions: ActionsClient
    agent_builder: AgentBuilderClient
    alerting: AlertingClient
    apm: ApmClient
    cases: CasesClient
    connectors: ConnectorsClient
    dashboards: DashboardsClient
    data_views: DataViewsClient
    maintenance_windows: MaintenanceWindowsClient
    ml: MlClient
    observability_ai_assistant: ObservabilityAiAssistantClient
    saved_objects: SavedObjectsClient
    short_urls: ShortUrlsClient
    slos: SlosClient
    streams: StreamsClient
    synthetics: SyntheticsClient
    uptime: UptimeClient
    visualizations: VisualizationsClient
    workflows: WorkflowsClient

    def __init__(self, client: Kibana, space_id: str, validate: bool = True) -> None:
        """
        Initialize space-scoped client.

        :param client: The main Kibana client to delegate to
        :param space_id: The space ID to scope operations to
        :param validate: Whether to validate that the space exists
        :raises SpaceNotFoundError: If validate=True and the space doesn't exist
        """
        self._client = client
        self._space_id = space_id
        self._validate = validate

        # Validate space exists immediately if validation is enabled
        if validate:
            self._validate_space_on_creation()

        # Wire space-scoped namespace clients
        def scoped(cls: type) -> Any:
            return cls(
                client,
                default_space_id=space_id,
                validate_spaces=validate,
            )

        self.actions = scoped(ActionsClient)
        self.agent_builder = scoped(AgentBuilderClient)
        self.alerting = scoped(AlertingClient)
        self.apm = scoped(ApmClient)
        self.cases = scoped(CasesClient)
        self.connectors = scoped(ConnectorsClient)
        self.dashboards = scoped(DashboardsClient)
        self.data_views = scoped(DataViewsClient)
        self.maintenance_windows = scoped(MaintenanceWindowsClient)
        self.ml = scoped(MlClient)
        self.observability_ai_assistant = scoped(ObservabilityAiAssistantClient)
        self.saved_objects = scoped(SavedObjectsClient)
        self.short_urls = scoped(ShortUrlsClient)
        self.slos = scoped(SlosClient)
        self.streams = scoped(StreamsClient)
        self.synthetics = scoped(SyntheticsClient)
        self.uptime = scoped(UptimeClient)
        self.visualizations = scoped(VisualizationsClient)
        self.workflows = scoped(WorkflowsClient)

    def _validate_space_on_creation(self) -> None:
        """
        Validate space exists when creating space-scoped client.

        :raises SpaceNotFoundError: If the space doesn't exist
        """
        try:
            self._client.spaces.get(id=self._space_id)
        except Exception as e:
            # Check if this is a "not found" error
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                raise SpaceNotFoundError(self._space_id)
            else:
                # Re-raise other errors (auth, network, etc.)
                raise

    @property
    def spaces(self) -> SpacesClient:
        """Get SpacesClient (not space-scoped; manages spaces themselves)."""
        return self._client.spaces

    @property
    def status(self) -> StatusClient:
        """Get StatusClient (not space-scoped; server-wide status)."""
        return self._client.status

    @property
    def security(self) -> SecurityClient:
        """Get SecurityClient (not space-scoped; roles and sessions are global)."""
        return self._client.security

    @property
    def task_manager(self) -> TaskManagerClient:
        """Get TaskManagerClient (not space-scoped; server-wide health)."""
        return self._client.task_manager

    @property
    def upgrade_assistant(self) -> UpgradeAssistantClient:
        """Get UpgradeAssistantClient (not space-scoped; cluster-wide status)."""
        return self._client.upgrade_assistant

    @property
    def logstash(self) -> LogstashClient:
        """Get LogstashClient (not space-scoped; pipelines are global)."""
        return self._client.logstash

    def close(self) -> None:
        """
        Close the underlying client and release resources.

        This delegates to the main Kibana client's close() method.
        """
        self._client.close()

    def __enter__(self) -> SpaceScopedKibana:
        """Enter context manager."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager and close client."""
        self.close()

    def __repr__(self) -> str:
        """Return string representation of space-scoped client."""
        return f"<SpaceScopedKibana(space_id='{self._space_id}', validate={self._validate})>"
