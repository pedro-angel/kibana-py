"""AsyncSavedObjectsClient for managing Kibana Saved Objects."""

from typing import Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote


class AsyncSavedObjectsClient(AsyncNamespaceClient):
    """
    Async client for managing Kibana Saved Objects.

    Saved Objects in Kibana are entities like dashboards, visualizations, index patterns,
    and other configuration items. This client provides async methods to create, read, update,
    and delete saved objects.

    Common saved object types:
    - dashboard: Kibana dashboards
    - visualization: Visualizations
    - index-pattern: Index patterns
    - search: Saved searches
    - config: Kibana configuration
    """

    def __init__(
        self,
        client,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """
        Initialize AsyncSavedObjectsClient with optional space context.

        :param client: Parent AsyncBaseClient instance to delegate requests to
        :param default_space_id: Optional default space ID for all operations
        :param validate_spaces: Whether to validate space existence (default: True)
        """
        super().__init__(client, default_space_id, validate_spaces)

    async def create(
        self,
        *,
        type: str,
        attributes: dict[str, Any],
        id: str | None = None,
        overwrite: bool = False,
        references: list[dict[str, Any]] | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """
        Create a new saved object.

        :param type: Type of saved object (e.g., 'dashboard', 'visualization', 'index-pattern')
        :param attributes: Attributes of the saved object
        :param id: Optional ID for the saved object (auto-generated if not provided)
        :param overwrite: If true, overwrite existing object with the same ID
        :param references: Optional list of references to other saved objects
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Created saved object details
        :raises ValueError: If required parameters are missing
        :raises BadRequestError: If the saved object data is invalid
        :raises ConflictError: If a saved object with the same ID already exists
        :raises SpaceNotFoundError: If space doesn't exist and validation is enabled
        :raises InvalidSpaceIdError: If space ID format is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges
        """
        # Validate required parameters
        if not type:
            raise ValueError("Parameter 'type' is required")
        if attributes is None:
            raise ValueError("Parameter 'attributes' is required")

        # Build space-aware path
        if id:
            base_path = f"/api/saved_objects/{_quote(type)}/{_quote(id)}"
        else:
            base_path = f"/api/saved_objects/{type}"

        path = self._build_space_path(base_path, space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        # Build request body
        body: dict[str, Any] = {
            "attributes": attributes,
        }

        # Add optional fields to body
        if references is not None:
            body["references"] = references

        # Build query parameters
        params: dict[str, str] = {}
        if overwrite:
            params["overwrite"] = "true"

        # Make the request
        return await self.perform_request(
            method="POST",
            path=path,
            body=body,
            params=params if params else None,
        )

    async def get(
        self,
        *,
        type: str,
        id: str,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """
        Get a saved object by type and ID.

        :param type: Type of saved object
        :param id: ID of the saved object
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Saved object details
        :raises ValueError: If required parameters are missing
        :raises NotFoundError: If the saved object is not found
        :raises SpaceNotFoundError: If space doesn't exist and validation is enabled
        :raises InvalidSpaceIdError: If space ID format is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges
        """
        # Validate required parameters
        if not type:
            raise ValueError("Parameter 'type' is required")
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Build space-aware path
        path = self._build_space_path(
            f"/api/saved_objects/{_quote(type)}/{_quote(id)}", space_id
        )

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        # Make the request
        return await self.perform_request(
            method="GET",
            path=path,
        )

    async def find(
        self,
        *,
        type: str | list[str],
        search: str | None = None,
        search_fields: list[str] | None = None,
        page: int | None = None,
        per_page: int | None = None,
        sort_field: str | None = None,
        has_reference: dict[str, str] | None = None,
        fields: list[str] | None = None,
        space_id: str | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """
        Find saved objects asynchronously.

        :param type: Type(s) of saved objects to find
        :param search: Search string
        :param search_fields: Fields to search in
        :param page: Page number
        :param per_page: Items per page
        :param sort_field: Field to sort by
        :param has_reference: Filter by reference
        :param fields: Fields to include in response
        :param space_id: Optional space ID for space-scoped operations
        :return: ObjectApiResponse containing search results
        """
        params: dict[str, Any] = {"type": type}
        if search:
            params["search"] = search
        if search_fields:
            params["search_fields"] = (
                ",".join(search_fields)
                if isinstance(search_fields, list)
                else search_fields
            )
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        if sort_field:
            params["sort_field"] = sort_field
        if has_reference:
            params["has_reference"] = has_reference
        if fields:
            params["fields"] = ",".join(fields) if isinstance(fields, list) else fields

        path = self._build_space_path("/api/saved_objects/_find", space_id)
        return await self.perform_request("GET", path, params=params)

    async def update(
        self,
        *,
        type: str,
        id: str,
        attributes: dict[str, Any],
        version: str | None = None,
        references: list[dict[str, Any]] | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """
        Update an existing saved object.

        :param type: Type of saved object
        :param id: ID of the saved object
        :param attributes: Updated attributes (partial or full)
        :param version: Optional version for optimistic concurrency control
        :param references: Optional updated list of references
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Updated saved object details
        :raises ValueError: If required parameters are missing
        :raises NotFoundError: If the saved object is not found
        :raises ConflictError: If version conflict occurs
        :raises SpaceNotFoundError: If space doesn't exist and validation is enabled
        :raises InvalidSpaceIdError: If space ID format is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges
        """
        # Validate required parameters
        if not type:
            raise ValueError("Parameter 'type' is required")
        if not id:
            raise ValueError("Parameter 'id' is required")
        if attributes is None:
            raise ValueError("Parameter 'attributes' is required")

        # Build space-aware path
        path = self._build_space_path(
            f"/api/saved_objects/{_quote(type)}/{_quote(id)}", space_id
        )

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        # Build request body
        body: dict[str, Any] = {
            "attributes": attributes,
        }

        # Add optional fields to body
        if version is not None:
            body["version"] = version
        if references is not None:
            body["references"] = references

        # Make the request
        return await self.perform_request(
            method="PUT",
            path=path,
            body=body,
        )

    async def delete(
        self,
        *,
        type: str,
        id: str,
        force: bool = False,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[dict[str, Any]]:
        """
        Delete a saved object.

        :param type: Type of saved object
        :param id: ID of the saved object
        :param force: If true, force delete even if object has references
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Deletion confirmation
        :raises ValueError: If required parameters are missing
        :raises NotFoundError: If the saved object is not found
        :raises SpaceNotFoundError: If space doesn't exist and validation is enabled
        :raises InvalidSpaceIdError: If space ID format is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges
        """
        # Validate required parameters
        if not type:
            raise ValueError("Parameter 'type' is required")
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Build space-aware path
        path = self._build_space_path(
            f"/api/saved_objects/{_quote(type)}/{_quote(id)}", space_id
        )

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        # Build query parameters
        params: dict[str, str] = {}
        if force:
            params["force"] = "true"

        # Make the request
        return await self.perform_request(
            method="DELETE",
            path=path,
            params=params if params else None,
        )
