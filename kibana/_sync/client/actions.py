"""ActionsClient for managing Kibana Actions (connectors)."""

from typing import Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient, _quote


class ActionsClient(NamespaceClient):
    """Client for managing Kibana Actions (connectors).

    Actions in Kibana are connectors that enable integration with external systems
    for alerting, notifications, and automation workflows. This client provides
    comprehensive methods to create, read, update, delete, and execute action
    connectors with full support for Kibana Spaces.

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

    Attributes:
        _default_space_id: Default space ID for operations if not specified per-request.
        _validate_spaces: Whether to validate space existence before operations.

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a webhook connector
        >>> connector = client.actions.create(
        ...     name="Alert Webhook",
        ...     connector_type_id=".webhook",
        ...     config={"url": "https://example.com/webhook"},
        ...     secrets={"user": "admin", "password": "secret"}
        ... )
        >>>
        >>> # Execute the connector
        >>> result = client.actions.execute(
        ...     id=connector.body["id"],
        ...     params={"message": "Alert triggered!"}
        ... )
        >>>
        >>> # Work with space-scoped connectors
        >>> marketing_client = client.space("marketing")
        >>> connector = marketing_client.actions.create(
        ...     name="Marketing Webhook",
        ...     connector_type_id=".webhook",
        ...     config={"url": "https://marketing.example.com/webhook"}
        ... )
    """

    def __init__(
        self,
        client,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize ActionsClient with optional space context.

        Args:
            client: Parent BaseClient instance to delegate HTTP requests to.
            default_space_id: Optional default space ID for all operations.
                If provided, all operations will be scoped to this space unless
                overridden with the space_id parameter.
            validate_spaces: Whether to validate space existence before operations.
                When True (default), the client will verify that spaces exist
                before making API calls. Set to False for better performance if
                you're certain spaces exist.

        Example:
            >>> # Client without default space
            >>> actions = ActionsClient(base_client)
            >>>
            >>> # Client with default space
            >>> marketing_actions = ActionsClient(
            ...     base_client,
            ...     default_space_id="marketing",
            ...     validate_spaces=True
            ... )
        """
        super().__init__(client, default_space_id, validate_spaces)

    def create(
        self,
        *,
        name: str,
        connector_type_id: str,
        config: dict[str, Any],
        secrets: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """
        Create a new action connector.

        :param name: Display name for the connector
        :param connector_type_id: Type of connector (e.g., '.email', '.slack', '.webhook')
        :param config: Connector configuration (non-sensitive data)
        :param secrets: Connector secrets (sensitive data like API keys, passwords)
        :param space_id: Optional space ID to create the connector in
        :param validate_space: Override space validation setting for this operation
        :return: Created connector details
        :raises ValueError: If required parameters are missing
        :raises BadRequestError: If the connector configuration is invalid
        :raises ConflictError: If a connector with the same name already exists
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> # Create a webhook connector
            >>> connector = client.actions.create(
            ...     name="Alert Webhook",
            ...     connector_type_id=".webhook",
            ...     config={"url": "https://example.com/webhook"},
            ...     secrets={"user": "admin", "password": "secret"}
            ... )
            >>> print(connector["id"])

            >>> # Create a Slack connector in a specific space
            >>> slack_connector = client.actions.create(
            ...     name="Slack Alerts",
            ...     connector_type_id=".slack",
            ...     config={},
            ...     secrets={"webhookUrl": "https://hooks.slack.com/services/..."},
            ...     space_id="marketing"
            ... )
        """
        # Validate required parameters
        if not name:
            raise ValueError("Parameter 'name' is required")
        if not connector_type_id:
            raise ValueError("Parameter 'connector_type_id' is required")
        if config is None:
            raise ValueError("Parameter 'config' is required")

        # Build space-scoped path (includes validation)
        path = self._build_space_path(
            "/api/actions/connector", space_id, validate_spaces=validate_space
        )

        # Build request body
        body: dict[str, Any] = {
            "name": name,
            "connector_type_id": connector_type_id,
            "config": config,
        }

        # Add secrets if provided
        if secrets is not None:
            body["secrets"] = secrets

        # Make the request
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
    ) -> ObjectApiResponse[dict[str, Any]]:
        """
        Get an action connector by ID.

        :param id: Connector ID to retrieve
        :param space_id: Optional space ID to get the connector from
        :param validate_space: Override space validation setting for this operation
        :return: Connector details
        :raises ValueError: If id parameter is missing
        :raises NotFoundError: If the connector is not found
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> connector = client.actions.get(id="my-webhook-connector")
            >>> print(connector["name"])
            >>> print(connector["connector_type_id"])

            >>> # Get connector from specific space
            >>> connector = client.actions.get(id="my-connector", space_id="marketing")
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

        # Make the request
        return self.perform_request(
            method="GET",
            path=path,
        )

    def get_all(
        self,
        *,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[list[dict[str, Any]]]:
        """
        Get all action connectors.

        :param space_id: Optional space ID to get connectors from
        :param validate_space: Override space validation setting for this operation
        :return: List of all connectors
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> connectors = client.actions.get_all()
            >>> for connector in connectors:
            ...     print(f"{connector['name']}: {connector['connector_type_id']}")

            >>> # Get connectors from specific space
            >>> connectors = client.actions.get_all(space_id="marketing")
        """
        # Build space-scoped path
        path = self._build_space_path(
            "/api/actions/connectors", space_id, validate_spaces=validate_space
        )

        # Make the request
        return self.perform_request(
            method="GET",
            path=path,
        )

    def list_types(self) -> ObjectApiResponse[list[dict[str, Any]]]:
        """
        Get all available action connector types.

        :return: List of available connector types with their capabilities
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> types = client.actions.list_types()
            >>> for connector_type in types:
            ...     print(f"{connector_type['id']}: {connector_type['name']}")
            ...     if connector_type.get('enabled'):
            ...         print("  Status: Enabled")
        """
        # Make the request
        return self.perform_request(
            method="GET",
            path="/api/actions/connector_types",
        )

    def update(
        self,
        *,
        id: str,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        secrets: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """
        Update an existing action connector.

        :param id: Connector ID to update
        :param name: New display name for the connector (optional)
        :param config: New connector configuration (optional)
        :param secrets: New connector secrets (optional)
        :param space_id: Optional space ID where the connector exists
        :param validate_space: Override space validation setting for this operation
        :return: Updated connector details
        :raises ValueError: If id parameter is missing
        :raises NotFoundError: If the connector is not found
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> # Update connector name and config
            >>> updated = client.actions.update(
            ...     id="my-webhook-connector",
            ...     name="Updated Webhook",
            ...     config={"url": "https://new-endpoint.com/webhook"}
            ... )

            >>> # Update connector in specific space
            >>> updated = client.actions.update(
            ...     id="my-slack-connector",
            ...     secrets={"webhookUrl": "https://hooks.slack.com/services/new..."},
            ...     space_id="marketing"
            ... )
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

        # Build request body with only provided parameters
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if config is not None:
            body["config"] = config
        if secrets is not None:
            body["secrets"] = secrets

        # Make the request
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
    ) -> ObjectApiResponse[dict[str, Any]]:
        """
        Delete an action connector.

        :param id: Connector ID to delete
        :param space_id: Optional space ID where the connector exists
        :param validate_space: Override space validation setting for this operation
        :return: Deletion confirmation
        :raises ValueError: If id parameter is missing
        :raises NotFoundError: If the connector is not found
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> client.actions.delete(id="my-old-connector")

            >>> # Delete connector from specific space
            >>> client.actions.delete(id="my-connector", space_id="marketing")
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

        # Make the request
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
    ) -> ObjectApiResponse[dict[str, Any]]:
        """
        Execute an action connector with the provided parameters.

        :param id: Connector ID to execute
        :param params: Execution parameters specific to the connector type
        :param space_id: Optional space ID where the connector exists
        :param validate_space: Override space validation setting for this operation
        :return: Execution results
        :raises ValueError: If required parameters are missing
        :raises BadRequestError: If the execution parameters are invalid
        :raises NotFoundError: If the connector is not found
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> # Execute a webhook connector
            >>> result = client.actions.execute(
            ...     id="my-webhook-connector",
            ...     params={
            ...         "message": "Alert triggered!",
            ...         "severity": "high",
            ...         "timestamp": "2024-01-01T12:00:00Z"
            ...     }
            ... )
            >>> print(result["status"])

            >>> # Execute a Slack connector in specific space
            >>> result = client.actions.execute(
            ...     id="my-slack-connector",
            ...     params={
            ...         "message": "System alert: High CPU usage detected"
            ...     },
            ...     space_id="marketing"
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

        # Build request body
        body = {"params": params}

        # Make the request
        return self.perform_request(
            method="POST",
            path=path,
            body=body,
        )
