"""AsyncActionsClient for managing Kibana Actions (connectors)."""

from typing import Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote


class AsyncActionsClient(AsyncNamespaceClient):
    """
    Async client for managing Kibana Actions (connectors).

    Actions in Kibana are connectors that enable integration with external systems
    for alerting, notifications, and automation. This client provides async methods to
    create, read, update, delete, and execute action connectors.

    Common connector types:
    - .webhook: HTTP webhooks
    - .slack: Slack messages
    - .email: Email notifications
    - .index: Elasticsearch index
    - .server-log: Server log entries
    - .pagerduty: PagerDuty incidents
    - .servicenow: ServiceNow tickets
    """

    def __init__(
        self,
        client,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """
        Initialize AsyncActionsClient with optional space context.

        :param client: Parent AsyncBaseClient instance to delegate requests to
        :param default_space_id: Optional default space ID for all operations
        :param validate_spaces: Whether to validate space existence (default: True)
        """
        super().__init__(client, default_space_id, validate_spaces)

    async def create(
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
        :raises SpaceNotFoundError: If space doesn't exist and validation is enabled
        :raises InvalidSpaceIdError: If space ID format is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges
        """
        # Validate required parameters
        if not name:
            raise ValueError("Parameter 'name' is required")
        if not connector_type_id:
            raise ValueError("Parameter 'connector_type_id' is required")
        if config is None:
            raise ValueError("Parameter 'config' is required")

        # Build space-aware path
        path = self._build_space_path("/api/actions/connector", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

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
        return await self.perform_request(
            method="POST",
            path=path,
            body=body,
        )

    async def get(
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
        :raises SpaceNotFoundError: If space doesn't exist and validation is enabled
        :raises InvalidSpaceIdError: If space ID format is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges
        """
        # Validate required parameters
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Build space-aware path
        path = self._build_space_path(f"/api/actions/connector/{_quote(id)}", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        # Make the request
        return await self.perform_request(
            method="GET",
            path=path,
        )

    async def get_all(
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
        :raises SpaceNotFoundError: If space doesn't exist and validation is enabled
        :raises InvalidSpaceIdError: If space ID format is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges
        """
        # Build space-aware path
        path = self._build_space_path("/api/actions/connectors", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        # Make the request
        return await self.perform_request(
            method="GET",
            path=path,
        )

    async def list_types(self) -> ObjectApiResponse[list[dict[str, Any]]]:
        """
        Get all available action connector types.

        :return: List of available connector types with their capabilities
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges
        """
        # Make the request
        return await self.perform_request(
            method="GET",
            path="/api/actions/connector_types",
        )

    async def update(
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
        :param space_id: Optional space ID to update the connector in
        :param validate_space: Override space validation setting for this operation
        :return: Updated connector details
        :raises ValueError: If id parameter is missing
        :raises NotFoundError: If the connector is not found
        :raises SpaceNotFoundError: If space doesn't exist and validation is enabled
        :raises InvalidSpaceIdError: If space ID format is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges
        """
        # Validate required parameters
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Build space-aware path
        path = self._build_space_path(f"/api/actions/connector/{_quote(id)}", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        # Build request body with only provided parameters
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if config is not None:
            body["config"] = config
        if secrets is not None:
            body["secrets"] = secrets

        # Make the request
        return await self.perform_request(
            method="PUT",
            path=path,
            body=body,
        )

    async def delete(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """
        Delete an action connector.

        :param id: Connector ID to delete
        :param space_id: Optional space ID to delete the connector from
        :param validate_space: Override space validation setting for this operation
        :return: Deletion confirmation
        :raises ValueError: If id parameter is missing
        :raises NotFoundError: If the connector is not found
        :raises SpaceNotFoundError: If space doesn't exist and validation is enabled
        :raises InvalidSpaceIdError: If space ID format is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges
        """
        # Validate required parameters
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Build space-aware path
        path = self._build_space_path(f"/api/actions/connector/{_quote(id)}", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        # Make the request
        return await self.perform_request(
            method="DELETE",
            path=path,
        )

    async def execute(
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
        :param space_id: Optional space ID to execute the connector in
        :param validate_space: Override space validation setting for this operation
        :return: Execution results
        :raises ValueError: If required parameters are missing
        :raises BadRequestError: If the execution parameters are invalid
        :raises NotFoundError: If the connector is not found
        :raises SpaceNotFoundError: If space doesn't exist and validation is enabled
        :raises InvalidSpaceIdError: If space ID format is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges
        """
        # Validate required parameters
        if not id:
            raise ValueError("Parameter 'id' is required")
        if params is None:
            raise ValueError("Parameter 'params' is required")

        # Build space-aware path
        path = self._build_space_path(
            f"/api/actions/connector/{_quote(id)}/_execute", space_id
        )

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        # Build request body
        body = {"params": params}

        # Make the request
        return await self.perform_request(
            method="POST",
            path=path,
            body=body,
        )
