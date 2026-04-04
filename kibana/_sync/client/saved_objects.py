"""SavedObjectsClient for managing Kibana Saved Objects."""

from typing import Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient, _quote


class SavedObjectsClient(NamespaceClient):
    """Client for managing Kibana Saved Objects.

    Saved Objects in Kibana are persistent entities that store configuration,
    user-created content, and application state. This includes dashboards,
    visualizations, index patterns, saved searches, and other Kibana objects.
    This client provides comprehensive CRUD operations with full support for
    Kibana Spaces.

    Saved objects are scoped to spaces, enabling multi-tenancy where different
    teams or projects can maintain isolated sets of dashboards and visualizations.

    Common saved object types:
        - dashboard: Kibana dashboards with visualizations
        - visualization: Individual visualizations (charts, graphs, etc.)
        - index-pattern: Index patterns for data access
        - search: Saved searches and queries
        - config: Kibana configuration settings
        - lens: Lens visualizations
        - map: Maps visualizations
        - canvas-workpad: Canvas workpads
        - tag: Tags for organizing objects

    Key features:
        - CRUD operations for all saved object types
        - Space-scoped operations for multi-tenancy
        - Reference management between objects
        - Version control with optimistic concurrency
        - Bulk operations for efficiency

    Attributes:
        _default_space_id: Default space ID for operations if not specified per-request.
        _validate_spaces: Whether to validate space existence before operations.

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a dashboard
        >>> dashboard = client.saved_objects.create(
        ...     type="dashboard",
        ...     attributes={
        ...         "title": "My Dashboard",
        ...         "description": "Sales analytics dashboard"
        ...     }
        ... )
        >>>
        >>> # Get a saved object
        >>> obj = client.saved_objects.get(
        ...     type="dashboard",
        ...     id="my-dashboard-id"
        ... )
        >>> print(obj.body["attributes"]["title"])
        >>>
        >>> # Work with space-scoped saved objects
        >>> marketing_client = client.space("marketing")
        >>> dashboards = marketing_client.saved_objects.find(
        ...     type="dashboard"
        ... )
    """

    def __init__(
        self,
        client,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize SavedObjectsClient with optional space context.

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
            >>> saved_objects = SavedObjectsClient(base_client)
            >>>
            >>> # Client with default space
            >>> marketing_objects = SavedObjectsClient(
            ...     base_client,
            ...     default_space_id="marketing",
            ...     validate_spaces=True
            ... )
        """
        super().__init__(client, default_space_id, validate_spaces)

    def create(
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
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> # Create a dashboard
            >>> dashboard = client.saved_objects.create(
            ...     type="dashboard",
            ...     attributes={
            ...         "title": "My Dashboard",
            ...         "description": "Dashboard description"
            ...     }
            ... )
            >>> print(dashboard["id"])

            >>> # Create with explicit ID
            >>> dashboard = client.saved_objects.create(
            ...     type="dashboard",
            ...     id="my-dashboard-id",
            ...     attributes={"title": "My Dashboard"}
            ... )

            >>> # Create in a specific space
            >>> dashboard = client.saved_objects.create(
            ...     type="dashboard",
            ...     attributes={"title": "Marketing Dashboard"},
            ...     space_id="marketing"
            ... )
        """
        # Validate required parameters
        if not type:
            raise ValueError("Parameter 'type' is required")
        if attributes is None:
            raise ValueError("Parameter 'attributes' is required")

        # Build request path using base class utility (includes validation)
        if id:
            path = self._build_space_path(
                f"/api/saved_objects/{_quote(type)}/{_quote(id)}",
                space_id,
                validate_spaces=validate_space,
            )
        else:
            path = self._build_space_path(
                f"/api/saved_objects/{type}",
                space_id,
                validate_spaces=validate_space,
            )

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
        return self.perform_request(
            method="POST",
            path=path,
            body=body,
            params=params if params else None,
        )

    def get(
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
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> # Get a dashboard
            >>> dashboard = client.saved_objects.get(
            ...     type="dashboard",
            ...     id="my-dashboard-id"
            ... )
            >>> print(dashboard["attributes"]["title"])

            >>> # Get from a specific space
            >>> dashboard = client.saved_objects.get(
            ...     type="dashboard",
            ...     id="my-dashboard-id",
            ...     space_id="marketing"
            ... )
        """
        # Validate required parameters
        if not type:
            raise ValueError("Parameter 'type' is required")
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Build request path using base class utility
        path = self._build_space_path(
            f"/api/saved_objects/{_quote(type)}/{_quote(id)}",
            space_id,
            validate_spaces=validate_space,
        )

        # Make the request
        return self.perform_request(
            method="GET",
            path=path,
        )

    def find(
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
        Find saved objects.

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
        return self.perform_request("GET", path, params=params)

    def update(
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
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> # Update a dashboard
            >>> updated = client.saved_objects.update(
            ...     type="dashboard",
            ...     id="my-dashboard-id",
            ...     attributes={"title": "Updated Dashboard Title"}
            ... )

            >>> # Update with version for optimistic concurrency
            >>> updated = client.saved_objects.update(
            ...     type="dashboard",
            ...     id="my-dashboard-id",
            ...     attributes={"title": "Updated Title"},
            ...     version="WzEsMV0="
            ... )

            >>> # Update in a specific space
            >>> updated = client.saved_objects.update(
            ...     type="dashboard",
            ...     id="my-dashboard-id",
            ...     attributes={"title": "Updated Title"},
            ...     space_id="marketing"
            ... )
        """
        # Validate required parameters
        if not type:
            raise ValueError("Parameter 'type' is required")
        if not id:
            raise ValueError("Parameter 'id' is required")
        if attributes is None:
            raise ValueError("Parameter 'attributes' is required")

        # Build request path using base class utility
        path = self._build_space_path(
            f"/api/saved_objects/{_quote(type)}/{_quote(id)}",
            space_id,
            validate_spaces=validate_space,
        )

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
        return self.perform_request(
            method="PUT",
            path=path,
            body=body,
        )

    def delete(
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
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> # Delete a dashboard
            >>> client.saved_objects.delete(
            ...     type="dashboard",
            ...     id="my-dashboard-id"
            ... )

            >>> # Force delete
            >>> client.saved_objects.delete(
            ...     type="dashboard",
            ...     id="my-dashboard-id",
            ...     force=True
            ... )

            >>> # Delete from a specific space
            >>> client.saved_objects.delete(
            ...     type="dashboard",
            ...     id="my-dashboard-id",
            ...     space_id="marketing"
            ... )
        """
        # Validate required parameters
        if not type:
            raise ValueError("Parameter 'type' is required")
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Build request path using base class utility
        path = self._build_space_path(
            f"/api/saved_objects/{_quote(type)}/{_quote(id)}",
            space_id,
            validate_spaces=validate_space,
        )

        # Build query parameters
        params: dict[str, str] = {}
        if force:
            params["force"] = "true"

        # Make the request
        return self.perform_request(
            method="DELETE",
            path=path,
            params=params if params else None,
        )
