"""ConnectorsClient for managing Kibana connectors (actions)."""

from typing import Any

from elastic_transport import ApiResponse, ObjectApiResponse, TextSerializer

from kibana._sync.client.utils import NamespaceClient, _quote


class ConnectorsClient(NamespaceClient):
    """Client for the Kibana Connectors API (``/api/actions``).

    Connectors enable integration with external systems for alerting,
    notifications, and automation workflows. This client provides methods to
    create, read, update, delete, and run connectors, list the available
    connector types, and handle OAuth 2.0 callback flows, with full support
    for Kibana Spaces.

    Connectors can be scoped to specific spaces, enabling multi-tenancy where
    different teams or projects can have isolated sets of connectors.

    Common connector types:
        - .webhook: HTTP webhooks for custom integrations
        - .slack: Slack messages and notifications
        - .email: Email notifications
        - .index: Write to Elasticsearch indices
        - .server-log: Server log entries
        - .pagerduty: PagerDuty incident management
        - .servicenow: ServiceNow ticket creation
        - .teams: Microsoft Teams messages
        - .jira: Jira issue creation

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a webhook connector
        >>> connector = client.connectors.create(
        ...     name="Alert Webhook",
        ...     connector_type_id=".webhook",
        ...     config={"url": "https://example.com/webhook"},
        ...     secrets={"user": "admin", "password": "secret"}
        ... )
        >>>
        >>> # Run the connector
        >>> result = client.connectors.execute(
        ...     id=connector.body["id"],
        ...     params={"body": '{"message": "Alert triggered!"}'}
        ... )
        >>>
        >>> # Work with space-scoped connectors
        >>> marketing = client.space("marketing")
        >>> connector = marketing.connectors.create(
        ...     name="Marketing Log",
        ...     connector_type_id=".server-log",
        ... )
    """

    def __init__(
        self,
        client: Any,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize ConnectorsClient with optional space context.

        Args:
            client: Parent BaseClient instance to delegate HTTP requests to.
            default_space_id: Optional default space ID for all operations.
                If provided, all operations will be scoped to this space unless
                overridden with the ``space_id`` parameter.
            validate_spaces: Whether to validate space existence before
                operations. When True (default), the client verifies that
                spaces exist before making API calls. Set to False for better
                performance if you are certain spaces exist.
        """
        super().__init__(client, default_space_id, validate_spaces)

    def _ensure_script_serializer(self) -> None:
        """Register a text serializer for JavaScript response mimetypes.

        ``GET /api/actions/connector/_oauth_callback_script`` responds with
        ``content-type: application/javascript``, which elastic-transport has
        no serializer for by default. Registering a pass-through text
        serializer on the shared transport (idempotently) lets the response
        body come back as a plain string.
        """
        transport = getattr(self._client, "_transport", None)
        collection = getattr(transport, "serializers", None)
        registry = getattr(collection, "serializers", None)
        if isinstance(registry, dict):
            for mimetype in ("application/javascript", "text/javascript"):
                if mimetype not in registry:
                    registry[mimetype] = TextSerializer()

    def create(
        self,
        *,
        name: str,
        connector_type_id: str,
        id: str | None = None,
        config: dict[str, Any] | None = None,
        secrets: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a connector.

        Creates a new connector, optionally with a caller-specified ID
        (``POST /api/actions/connector`` or
        ``POST /api/actions/connector/{id}``).

        Args:
            name: The display name for the connector.
            connector_type_id: The connector type (e.g. ``.email``,
                ``.slack``, ``.webhook``, ``.index``, ``.server-log``).
            id: Optional caller-specified connector ID (1-36 characters).
                Useful for reproducible or pre-provisioned connector IDs.
                When omitted, Kibana generates a random UUID.
            config: The connector configuration details (non-sensitive data).
                Optional; defaults to ``{}`` on the server. Connector types
                without configuration (e.g. ``.server-log``, ``.slack``) do
                not need it.
            secrets: The connector secrets (sensitive data such as API keys,
                passwords, or tokens). Defaults to ``{}`` on the server.
            space_id: Optional space ID to create the connector in.
            validate_space: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created connector details.

        Raises:
            ValueError: If required parameters are empty.
            BadRequestError: If the connector configuration is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> # Create a webhook connector
            >>> connector = client.connectors.create(
            ...     name="Alert Webhook",
            ...     connector_type_id=".webhook",
            ...     config={"url": "https://example.com/webhook"},
            ...     secrets={"user": "admin", "password": "secret"},
            ... )
            >>> print(connector.body["id"])
            >>>
            >>> # Create a server-log connector with a fixed ID (no config)
            >>> connector = client.connectors.create(
            ...     id="my-server-log",
            ...     name="Server Log",
            ...     connector_type_id=".server-log",
            ... )
        """
        # Validate required parameters
        if not name:
            raise ValueError("Parameter 'name' is required")
        if not connector_type_id:
            raise ValueError("Parameter 'connector_type_id' is required")
        if id is not None and not id:
            raise ValueError("Parameter 'id' must be non-empty when provided")

        base_path = "/api/actions/connector"
        if id is not None:
            base_path = f"{base_path}/{_quote(id)}"

        # Build space-scoped path (includes validation)
        path = self._build_space_path(
            base_path, space_id, validate_spaces=validate_space
        )

        # Build request body
        body: dict[str, Any] = {
            "name": name,
            "connector_type_id": connector_type_id,
        }
        if config is not None:
            body["config"] = config
        if secrets is not None:
            body["secrets"] = secrets

        return self.perform_request(
            method="POST",
            path=path,
            body=body,
        )

    def get(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get connector information.

        Retrieves a connector by ID (``GET /api/actions/connector/{id}``).

        Args:
            id: The connector ID.
            space_id: Optional space ID to get the connector from.
            validate_space: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the connector details.

        Raises:
            ValueError: If ``id`` is empty.
            NotFoundError: If the connector is not found.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> connector = client.connectors.get(id="my-webhook-connector")
            >>> print(connector.body["name"])
            >>> print(connector.body["connector_type_id"])
        """
        # Validate required parameters
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Build space-scoped path
        path = self._build_space_path(
            f"/api/actions/connector/{_quote(id)}",
            space_id,
            validate_spaces=validate_space,
        )

        return self.perform_request(
            method="GET",
            path=path,
        )

    def get_all(
        self,
        *,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get all connectors.

        Retrieves all connectors in a space
        (``GET /api/actions/connectors``).

        Args:
            space_id: Optional space ID to get connectors from.
            validate_space: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is the list of connectors.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> connectors = client.connectors.get_all()
            >>> for connector in connectors.body:
            ...     print(f"{connector['name']}: {connector['connector_type_id']}")
        """
        # Build space-scoped path
        path = self._build_space_path(
            "/api/actions/connectors", space_id, validate_spaces=validate_space
        )

        return self.perform_request(
            method="GET",
            path=path,
        )

    def list_types(
        self,
        *,
        feature_id: str | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get connector types.

        Retrieves the available connector types
        (``GET /api/actions/connector_types``). No Kibana feature privileges
        are required to run this API.

        Args:
            feature_id: Optional filter to limit the retrieved connector
                types to those that support a specific feature, such as
                ``alerting``, ``cases``, ``uptime``, or ``siem``.
            space_id: Optional space ID to list connector types in.
            validate_space: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is the list of connector types.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> types = client.connectors.list_types()
            >>> for connector_type in types.body:
            ...     print(f"{connector_type['id']}: {connector_type['name']}")
            >>>
            >>> # Only connector types usable by alerting rules
            >>> alerting_types = client.connectors.list_types(feature_id="alerting")
        """
        # Build space-scoped path
        path = self._build_space_path(
            "/api/actions/connector_types",
            space_id,
            validate_spaces=validate_space,
        )

        params: dict[str, Any] = {}
        if feature_id is not None:
            params["feature_id"] = feature_id

        return self.perform_request(
            method="GET",
            path=path,
            params=params or None,
        )

    def update(
        self,
        *,
        id: str,
        name: str,
        config: dict[str, Any] | None = None,
        secrets: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a connector.

        Fully replaces a connector's user-editable attributes
        (``PUT /api/actions/connector/{id}``). This is a full-replace PUT,
        not a partial update: ``name`` is required, and any omitted
        ``config`` or ``secrets`` are reset to ``{}`` on the server.
        Connector types with required configuration fields (e.g. ``.index``,
        ``.webhook``) therefore reject updates that omit ``config``. The
        connector type itself cannot be changed.

        Args:
            id: The connector ID to update.
            name: The display name for the connector (required by the API).
            config: The full connector configuration to store. Omitting it
                resets the configuration to ``{}``; pass the complete desired
                configuration (fetch and merge the current one if needed).
            secrets: The full connector secrets to store. Omitting it resets
                the secrets to ``{}``.
            space_id: Optional space ID where the connector exists.
            validate_space: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the updated connector details.

        Raises:
            ValueError: If ``id`` or ``name`` is empty.
            BadRequestError: If the resulting connector is invalid (for
                example, ``config`` was omitted for a type that requires it).
            NotFoundError: If the connector is not found.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> # Full replace: always pass name and the complete config
            >>> updated = client.connectors.update(
            ...     id="my-webhook-connector",
            ...     name="Updated Webhook",
            ...     config={"url": "https://new-endpoint.com/webhook"},
            ...     secrets={"user": "admin", "password": "new-secret"},
            ... )
        """
        # Validate required parameters
        if not id:
            raise ValueError("Parameter 'id' is required")
        if not name:
            raise ValueError("Parameter 'name' is required")

        # Build space-scoped path
        path = self._build_space_path(
            f"/api/actions/connector/{_quote(id)}",
            space_id,
            validate_spaces=validate_space,
        )

        # PUT is a full replacement: name is always sent; omitted
        # config/secrets are defaulted to {} by the server.
        body: dict[str, Any] = {"name": name}
        if config is not None:
            body["config"] = config
        if secrets is not None:
            body["secrets"] = secrets

        return self.perform_request(
            method="PUT",
            path=path,
            body=body,
        )

    def delete(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a connector.

        Deletes a connector by ID (``DELETE /api/actions/connector/{id}``).
        WARNING: this action cannot be undone.

        Args:
            id: The connector ID to delete.
            space_id: Optional space ID where the connector exists.
            validate_space: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body (HTTP 204 on success).

        Raises:
            ValueError: If ``id`` is empty.
            NotFoundError: If the connector is not found.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> client.connectors.delete(id="my-old-connector")
        """
        # Validate required parameters
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Build space-scoped path
        path = self._build_space_path(
            f"/api/actions/connector/{_quote(id)}",
            space_id,
            validate_spaces=validate_space,
        )

        return self.perform_request(
            method="DELETE",
            path=path,
        )

    def execute(
        self,
        *,
        id: str,
        params: dict[str, Any],
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Run a connector.

        Runs a connector by ID with type-specific parameters
        (``POST /api/actions/connector/{id}/_execute``).

        Args:
            id: The connector ID to run.
            params: Execution parameters, whose shape depends on the
                connector type. For example, ``.server-log`` takes
                ``{"message": ...}``, ``.index`` takes
                ``{"documents": [...]}``.
            space_id: Optional space ID where the connector exists.
            validate_space: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the execution result (``status`` is
            ``"ok"`` or ``"error"``).

        Raises:
            ValueError: If required parameters are missing.
            BadRequestError: If the execution parameters are invalid.
            NotFoundError: If the connector is not found.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> # Run a server-log connector
            >>> result = client.connectors.execute(
            ...     id="my-server-log",
            ...     params={"message": "Alert triggered!", "level": "info"},
            ... )
            >>> print(result.body["status"])
            >>>
            >>> # Run an index connector
            >>> result = client.connectors.execute(
            ...     id="my-index-connector",
            ...     params={"documents": [{"message": "hello"}]},
            ... )
        """
        # Validate required parameters
        if not id:
            raise ValueError("Parameter 'id' is required")
        if params is None:
            raise ValueError("Parameter 'params' is required")

        # Build space-scoped path
        path = self._build_space_path(
            f"/api/actions/connector/{_quote(id)}/_execute",
            space_id,
            validate_spaces=validate_space,
        )

        return self.perform_request(
            method="POST",
            path=path,
            body={"params": params},
        )

    def oauth_callback(
        self,
        *,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
        error_description: str | None = None,
        session_state: str | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ApiResponse[Any]:
        """Handle OAuth callback.

        Handles the OAuth 2.0 authorization code callback from external
        providers and exchanges the authorization code for access and refresh
        tokens (``GET /api/actions/connector/_oauth_callback``). Added in
        Kibana 9.4.0.

        This endpoint is normally invoked by the user's browser as the OAuth
        provider's redirect URI; Kibana responds with an HTML page (or a
        redirect) that completes the flow.

        Args:
            code: The authorization code returned by the OAuth provider.
            state: The state parameter for CSRF protection.
            error: Error code if the authorization failed.
            error_description: Human-readable error description.
            session_state: Session state from the OAuth provider (e.g.
                Microsoft).
            space_id: Optional space ID scoping the callback.
            validate_space: Override space validation setting for this
                operation.

        Returns:
            TextApiResponse with the HTML completion page (HTTP 200), or the
            result of a redirect (HTTP 302).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> response = client.connectors.oauth_callback(
            ...     code="authorization-code",
            ...     state="csrf-state-token",
            ... )
            >>> print(response.meta.status)
        """
        # Build space-scoped path
        path = self._build_space_path(
            "/api/actions/connector/_oauth_callback",
            space_id,
            validate_spaces=validate_space,
        )

        params: dict[str, Any] = {}
        if code is not None:
            params["code"] = code
        if state is not None:
            params["state"] = state
        if error is not None:
            params["error"] = error
        if error_description is not None:
            params["error_description"] = error_description
        if session_state is not None:
            params["session_state"] = session_state

        return self.perform_request(
            method="GET",
            path=path,
            params=params or None,
        )

    def get_oauth_callback_script(
        self,
        *,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ApiResponse[Any]:
        """Get the OAuth callback script.

        Returns the JavaScript used by the OAuth callback completion page
        (``GET /api/actions/connector/_oauth_callback_script``). Added in
        Kibana 9.4.0.

        Args:
            space_id: Optional space ID scoping the request.
            validate_space: Override space validation setting for this
                operation.

        Returns:
            TextApiResponse whose body is the JavaScript source
            (``content-type: application/javascript``).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> script = client.connectors.get_oauth_callback_script()
            >>> print(script.body[:40])
        """
        # The response is served as application/javascript, which
        # elastic-transport cannot deserialize by default.
        self._ensure_script_serializer()

        # Build space-scoped path
        path = self._build_space_path(
            "/api/actions/connector/_oauth_callback_script",
            space_id,
            validate_spaces=validate_space,
        )

        return self.perform_request(
            method="GET",
            path=path,
        )
