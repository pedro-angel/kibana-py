"""Asynchronous Kibana client."""

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from elastic_transport import AsyncTransport, NodeConfig

from kibana._async.client._base import DEFAULT, AsyncBaseClient, DefaultType
from kibana._rate_limiter import AsyncRateLimiter
from kibana.exceptions import SpaceNotFoundError
from kibana.serializer import DEFAULT_SERIALIZERS

__all__ = ["AsyncKibana", "AsyncSpaceScopedKibana", "DEFAULT", "DefaultType"]

if TYPE_CHECKING:
    from kibana._async.client.actions import AsyncActionsClient
    from kibana._async.client.alerting import AsyncAlertingClient
    from kibana._async.client.saved_objects import AsyncSavedObjectsClient
    from kibana._async.client.spaces import AsyncSpacesClient
    from kibana._async.client.status import AsyncStatusClient

# Set up logger
logger = logging.getLogger("kibana")


class AsyncKibana(AsyncBaseClient):
    """
    Asynchronous client for Kibana.

    Provides a Pythonic async interface to interact with Kibana's REST APIs.

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
            return

        # Validate that either hosts or cloud_id is provided
        if hosts is None and cloud_id is None:
            raise ValueError("Either 'hosts' or 'cloud_id' must be provided")

        # Build node configurations
        node_configs = self._build_node_configs(hosts, cloud_id)

        # Build transport options
        transport_kwargs: dict[str, Any] = {
            "node_configs": node_configs,
            "serializers": DEFAULT_SERIALIZERS,
        }

        # Note: SSL/TLS options like verify_certs, ca_certs, client_cert, client_key
        # are configured on NodeConfig, not Transport. They are accepted here for
        # API compatibility but stored for future use when creating SSL contexts.
        # For now, we just accept them without error.

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

    def _build_node_configs(
        self,
        hosts: str | list[str | dict[str, Any]] | None,
        cloud_id: str | None,
    ) -> list[NodeConfig]:
        """
        Build NodeConfig objects from hosts or cloud_id.

        :param hosts: Host specifications
        :param cloud_id: Cloud ID for Elastic Cloud
        :return: List of NodeConfig objects
        """
        if cloud_id is not None:
            # Parse cloud_id and create NodeConfig
            # Cloud ID format: cluster_name:base64_encoded_data
            # The base64 data contains: cloud_host$es_uuid$kibana_uuid
            import base64

            try:
                _, encoded = cloud_id.split(":", 1)
                decoded = base64.b64decode(encoded).decode("utf-8")
                parts = decoded.split("$")

                if len(parts) >= 3:
                    cloud_host = parts[0]
                    kibana_uuid = parts[2]

                    # Construct Kibana URL
                    return [
                        NodeConfig(
                            scheme="https", host=f"{kibana_uuid}.{cloud_host}", port=443
                        )
                    ]
                else:
                    raise ValueError(f"Invalid cloud_id format: {cloud_id}")
            except Exception as e:
                raise ValueError(f"Failed to parse cloud_id: {e}")

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

                parsed = urlparse(host)

                scheme = parsed.scheme or "http"
                hostname = parsed.hostname or "localhost"
                port = parsed.port or (443 if scheme == "https" else 5601)

                node_config = NodeConfig(
                    scheme=scheme,
                    host=hostname,
                    port=port,
                    path_prefix=(
                        parsed.path if parsed.path and parsed.path != "/" else ""
                    ),
                )
                node_configs.append(node_config)
            elif isinstance(host, dict):
                # Create NodeConfig from dict
                node_config = NodeConfig(**host)
                node_configs.append(node_config)
            else:
                raise ValueError(f"Invalid host specification: {host}")

        return node_configs

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

    async def __aenter__(self) -> "AsyncKibana":
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager and close client."""
        await self.close()

    @property
    def actions(self) -> "AsyncActionsClient":
        """
        Access the Actions API for managing Kibana action connectors.

        Actions in Kibana are connectors that enable integration with external systems
        for alerting, notifications, and automation.

        :return: AsyncActionsClient instance for managing action connectors

        Example:
            >>> # Create a webhook connector
            >>> connector = await client.actions.create(
            ...     name="Alert Webhook",
            ...     connector_type_id=".webhook",
            ...     config={"url": "https://example.com/webhook"}
            ... )

            >>> # List all connectors
            >>> connectors = await client.actions.get_all()

            >>> # Execute a connector
            >>> result = await client.actions.execute(
            ...     id=connector.body["id"],
            ...     params={"message": "Test alert"}
            ... )
        """
        # Lazy initialization of AsyncActionsClient
        if not hasattr(self, "_actions_client"):
            from kibana._async.client.actions import AsyncActionsClient

            self._actions_client = AsyncActionsClient(self)
        return self._actions_client

    @property
    def spaces(self) -> "AsyncSpacesClient":
        """
        Get the Spaces client for managing Kibana Spaces.

        :return: AsyncSpacesClient instance
        """
        if not hasattr(self, "_spaces_client"):
            from kibana._async.client.spaces import AsyncSpacesClient

            self._spaces_client = AsyncSpacesClient(self)
        return self._spaces_client

    @property
    def status(self) -> "AsyncStatusClient":
        """
        Get the Status client for checking Kibana status.

        :return: AsyncStatusClient instance
        """
        if not hasattr(self, "_status_client"):
            from kibana._async.client.status import AsyncStatusClient

            self._status_client = AsyncStatusClient(self)
        return self._status_client

    @property
    def saved_objects(self) -> "AsyncSavedObjectsClient":
        """
        Access the Saved Objects API for managing Kibana saved objects.

        Saved Objects in Kibana are entities like dashboards, visualizations, index patterns,
        and other configuration items. This API provides methods to create, read, update,
        and delete saved objects.

        :return: AsyncSavedObjectsClient instance for managing saved objects

        Example:
            >>> # Create a dashboard
            >>> dashboard = await client.saved_objects.create(
            ...     type="dashboard",
            ...     attributes={"title": "My Dashboard"}
            ... )

            >>> # Get a saved object
            >>> obj = await client.saved_objects.get(
            ...     type="dashboard",
            ...     id="my-dashboard-id"
            ... )

            >>> # Update a saved object
            >>> updated = await client.saved_objects.update(
            ...     type="dashboard",
            ...     id="my-dashboard-id",
            ...     attributes={"title": "Updated Dashboard"}
            ... )

            >>> # Delete a saved object
            >>> await client.saved_objects.delete(
            ...     type="dashboard",
            ...     id="my-dashboard-id"
            ... )
        """
        # Lazy initialization of AsyncSavedObjectsClient
        if not hasattr(self, "_saved_objects_client"):
            from kibana._async.client.saved_objects import AsyncSavedObjectsClient

            self._saved_objects_client = AsyncSavedObjectsClient(self)
        return self._saved_objects_client

    @property
    def alerting(self) -> "AsyncAlertingClient":
        """
        Access the Alerting API for managing rules.

        :return: AsyncAlertingClient instance for managing rules.
        """
        # Lazy initialization of AsyncAlertingClient
        if not hasattr(self, "_alerting_client"):
            from kibana._async.client.alerting import AsyncAlertingClient

            self._alerting_client = AsyncAlertingClient(self)
        return self._alerting_client

    def space(self, space_id: str, validate: bool = True) -> "AsyncSpaceScopedKibana":
        """
        Create a space-scoped client instance.

        This method creates a new client instance that automatically operates within
        the specified space context. All operations performed through the returned
        client will be scoped to the specified space.

        :param space_id: The ID of the space to scope operations to
        :param validate: Whether to validate that the space exists (default: True)
        :return: AsyncSpaceScopedKibana instance scoped to the specified space
        :raises SpaceNotFoundError: If validate=True and the space doesn't exist
        :raises InvalidSpaceIdError: If the space_id format is invalid

        Example:
            >>> # Create a space-scoped client with validation
            >>> marketing_client = await client.space("marketing")
            >>>
            >>> # Create connector in the marketing space
            >>> connector = await marketing_client.actions.create(
            ...     name="Marketing Webhook",
            ...     connector_type_id=".webhook",
            ...     config={"url": "https://marketing.example.com/webhook"}
            ... )
            >>>
            >>> # Create space-scoped client without validation (for performance)
            >>> fast_client = await client.space("marketing", validate=False)
        """
        return AsyncSpaceScopedKibana(self, space_id, validate)

    def __repr__(self) -> str:
        """Return string representation of client."""
        return "<AsyncKibana()>"


class AsyncSpaceScopedKibana:
    """
    Space-scoped async client that delegates to main client with space context.

    This class provides the same API surface as the main AsyncKibana client but
    automatically scopes all operations to a specific space. All child clients
    (actions, saved_objects, etc.) created through this instance will inherit
    the space context and validation settings.

    Example:
        >>> # Create space-scoped client with validation
        >>> marketing_client = client.space("marketing")
        >>>
        >>> # All operations are automatically scoped to "marketing" space
        >>> connector = await marketing_client.actions.create(
        ...     name="Marketing Webhook",
        ...     connector_type_id=".webhook",
        ...     config={"url": "https://marketing.example.com/webhook"}
        ... )
        >>>
        >>> # Create space-scoped client without validation for performance
        >>> fast_client = client.space("marketing", validate=False)
    """

    def __init__(
        self, client: AsyncKibana, space_id: str, validate: bool = True
    ) -> None:
        """
        Initialize space-scoped async client.

        :param client: The main AsyncKibana client to delegate to
        :param space_id: The space ID to scope operations to
        :param validate: Whether to validate that the space exists
        :raises SpaceNotFoundError: If validate=True and the space doesn't exist
        """
        self._client = client
        self._space_id = space_id
        self._validate = validate

        # Note: For async, we can't validate synchronously in __init__
        # Validation will happen on first use if enabled

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
    def actions(self) -> "AsyncActionsClient":
        """
        Get AsyncActionsClient with space scope.

        Returns an AsyncActionsClient instance that automatically operates within
        the space context of this AsyncSpaceScopedKibana instance.

        :return: AsyncActionsClient scoped to this space

        Example:
            >>> marketing_client = client.space("marketing")
            >>> # This connector will be created in the "marketing" space
            >>> connector = await marketing_client.actions.create(
            ...     name="Marketing Webhook",
            ...     connector_type_id=".webhook",
            ...     config={"url": "https://marketing.example.com/webhook"}
            ... )
        """
        if not hasattr(self, "_actions_client"):
            from kibana._async.client.actions import AsyncActionsClient

            self._actions_client = AsyncActionsClient(
                self._client,
                default_space_id=self._space_id,
                validate_spaces=self._validate,
            )
        return self._actions_client

    @property
    def saved_objects(self) -> "AsyncSavedObjectsClient":
        """
        Get AsyncSavedObjectsClient with space scope.

        Returns an AsyncSavedObjectsClient instance that automatically operates within
        the space context of this AsyncSpaceScopedKibana instance.

        :return: AsyncSavedObjectsClient scoped to this space

        Example:
            >>> marketing_client = client.space("marketing")
            >>> # This dashboard will be created in the "marketing" space
            >>> dashboard = await marketing_client.saved_objects.create(
            ...     type="dashboard",
            ...     attributes={"title": "Marketing Dashboard"}
            ... )
        """
        if not hasattr(self, "_saved_objects_client"):
            from kibana._async.client.saved_objects import AsyncSavedObjectsClient

            self._saved_objects_client = AsyncSavedObjectsClient(
                self._client,
                default_space_id=self._space_id,
                validate_spaces=self._validate,
            )
        return self._saved_objects_client

    @property
    def spaces(self) -> "AsyncSpacesClient":
        """
        Get AsyncSpacesClient (not space-scoped).

        The AsyncSpacesClient is used for managing spaces themselves and is not
        scoped to a particular space. It uses the same client as the parent
        AsyncKibana instance.

        :return: AsyncSpacesClient for managing spaces
        """
        return self._client.spaces

    @property
    def status(self) -> "AsyncStatusClient":
        """
        Get AsyncStatusClient (not space-scoped).

        The AsyncStatusClient provides server-wide status information and is not
        scoped to a particular space. It uses the same client as the parent
        AsyncKibana instance.

        :return: AsyncStatusClient for monitoring server status
        """
        return self._client.status

    async def close(self) -> None:
        """
        Close the underlying client and release resources.

        This delegates to the main AsyncKibana client's close() method.
        """
        await self._client.close()

    async def __aenter__(self) -> "AsyncSpaceScopedKibana":
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager and close client."""
        await self.close()

    def __repr__(self) -> str:
        """Return string representation of space-scoped client."""
        return f"<AsyncSpaceScopedKibana(space_id='{self._space_id}', validate={self._validate})>"
