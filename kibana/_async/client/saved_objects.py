"""AsyncSavedObjectsClient for managing Kibana Saved Objects."""

from __future__ import annotations

from typing import Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote
from kibana._sync.client.saved_objects import _build_multipart_body, _ndjson_bytes


class AsyncSavedObjectsClient(AsyncNamespaceClient):
    """Async client for managing Kibana Saved Objects.

    Saved Objects in Kibana are persistent entities that store configuration,
    user-created content, and application state. This includes dashboards,
    visualizations, index patterns, saved searches, and other Kibana objects.
    This client provides comprehensive CRUD operations with full support for
    Kibana Spaces.

    .. deprecated:: Kibana 8.7
        The single-object and bulk CRUD endpoints (``create``, ``get``,
        ``update``, ``delete``, ``find``, ``resolve`` and the ``bulk_*``
        methods) are deprecated in Kibana 9.4.3. Prefer the type-specific
        APIs (e.g. ``client.dashboards``, ``client.data_views``) or the
        spec-current ``export``/``import_objects`` APIs, which remain fully
        supported.

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
        - CRUD operations for all saved object types (deprecated endpoints)
        - Bulk create/get/update/delete/resolve operations
        - NDJSON export and multipart import (spec-current)
        - Space-scoped operations for multi-tenancy
        - Reference management between objects
        - Version control with optimistic concurrency

    Attributes:
        _default_space_id: Default space ID for operations if not specified per-request.
        _validate_spaces: Whether to validate space existence before operations.

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a dashboard
        >>> dashboard = await client.saved_objects.create(
        ...     type="dashboard",
        ...     attributes={
        ...         "title": "My Dashboard",
        ...         "description": "Sales analytics dashboard"
        ...     }
        ... )
        >>>
        >>> # Export objects as NDJSON and re-import them
        >>> exported = await client.saved_objects.export(
        ...     objects=[{"type": "dashboard", "id": dashboard["id"]}]
        ... )
        >>> result = await client.saved_objects.import_objects(
        ...     file=list(exported), overwrite=True
        ... )
        >>>
        >>> # Work with space-scoped saved objects
        >>> marketing_client = client.space("marketing")
        >>> dashboards = await marketing_client.saved_objects.find(type="dashboard")
    """

    def __init__(
        self,
        client,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize AsyncSavedObjectsClient with optional space context.

        Args:
            client: Parent AsyncBaseClient instance to delegate HTTP requests to.
            default_space_id: Optional default space ID for all operations.
                If provided, all operations will be scoped to this space unless
                overridden with the space_id parameter.
            validate_spaces: Whether to validate space existence before operations.
                When True (default), the client will verify that spaces exist
                before making API calls. Set to False for better performance if
                you're certain spaces exist.

        Example:
            >>> # Client without default space
            >>> saved_objects = AsyncSavedObjectsClient(base_client)
            >>>
            >>> # Client with default space
            >>> marketing_objects = AsyncSavedObjectsClient(
            ...     base_client,
            ...     default_space_id="marketing",
            ...     validate_spaces=True
            ... )
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
        initial_namespaces: list[str] | None = None,
        core_migration_version: str | None = None,
        type_migration_version: str | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Create a new saved object.

        ``POST /api/saved_objects/{type}`` or ``POST /api/saved_objects/{type}/{id}``

        .. deprecated:: Kibana 8.7
            Deprecated in Kibana 9.4.3. Use the type-specific APIs (e.g.
            ``client.dashboards.create``, ``client.data_views.create``) or
            :meth:`import_objects` instead.

        :param type: Type of saved object (e.g., 'dashboard', 'visualization', 'index-pattern')
        :param attributes: Attributes of the saved object
        :param id: Optional ID for the saved object (auto-generated if not provided)
        :param overwrite: If true, overwrite existing object with the same ID
        :param references: Optional list of references to other saved objects
        :param initial_namespaces: Identifiers of the spaces the object is
            shared into when it is created (for shareable object types)
        :param core_migration_version: The Kibana version that last migrated
            this document (preserve when creating objects outside of Kibana)
        :param type_migration_version: The type version that last migrated
            this document (preserve when creating objects outside of Kibana)
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
            >>> dashboard = await client.saved_objects.create(
            ...     type="dashboard",
            ...     attributes={
            ...         "title": "My Dashboard",
            ...         "description": "Dashboard description"
            ...     }
            ... )
            >>> print(dashboard["id"])

            >>> # Create with explicit ID in a specific space
            >>> dashboard = await client.saved_objects.create(
            ...     type="dashboard",
            ...     id="my-dashboard-id",
            ...     attributes={"title": "Marketing Dashboard"},
            ...     space_id="marketing"
            ... )
        """
        # Validate required parameters
        if not type:
            raise ValueError("Parameter 'type' is required")
        if attributes is None:
            raise ValueError("Parameter 'attributes' is required")

        # Build request path using base class utility
        if id:
            base_path = f"/api/saved_objects/{_quote(type)}/{_quote(id)}"
        else:
            base_path = f"/api/saved_objects/{_quote(type)}"

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
        if initial_namespaces is not None:
            body["initialNamespaces"] = initial_namespaces
        if core_migration_version is not None:
            body["coreMigrationVersion"] = core_migration_version
        if type_migration_version is not None:
            body["typeMigrationVersion"] = type_migration_version

        # Build query parameters
        params: dict[str, Any] = {}
        if overwrite:
            params["overwrite"] = overwrite

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
    ) -> ObjectApiResponse[Any]:
        """
        Get a saved object by type and ID.

        ``GET /api/saved_objects/{type}/{id}``

        .. deprecated:: Kibana 8.7
            Deprecated in Kibana 9.4.3. Use the type-specific APIs (e.g.
            ``client.dashboards.get``) or :meth:`export` instead.

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
            >>> dashboard = await client.saved_objects.get(
            ...     type="dashboard",
            ...     id="my-dashboard-id"
            ... )
            >>> print(dashboard["attributes"]["title"])
        """
        # Validate required parameters
        if not type:
            raise ValueError("Parameter 'type' is required")
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Build request path using base class utility
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

    async def resolve(
        self,
        *,
        type: str,
        id: str,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Resolve a saved object by type and ID.

        ``GET /api/saved_objects/resolve/{type}/{id}``

        Retrieves a single saved object by its ID, using any legacy URL
        aliases if they exist. Under certain circumstances when Kibana is
        upgraded, saved object migrations may necessitate regenerating some
        object IDs; this endpoint follows the alias to the new object.

        .. deprecated:: Kibana 8.7
            Deprecated in Kibana 9.4.3. Use the type-specific APIs (e.g.
            ``client.dashboards.get``) or :meth:`export` instead.

        :param type: Type of saved object
        :param id: ID of the saved object
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Resolution result with ``saved_object`` and ``outcome``
            ("exactMatch", "aliasMatch", or "conflict")
        :raises ValueError: If required parameters are missing
        :raises NotFoundError: If the saved object is not found
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> result = await client.saved_objects.resolve(
            ...     type="dashboard",
            ...     id="my-dashboard-id"
            ... )
            >>> print(result["outcome"], result["saved_object"]["id"])
        """
        # Validate required parameters
        if not type:
            raise ValueError("Parameter 'type' is required")
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Build request path using base class utility
        path = self._build_space_path(
            f"/api/saved_objects/resolve/{_quote(type)}/{_quote(id)}", space_id
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
        aggs: str | dict[str, Any] | None = None,
        default_search_operator: str | None = None,
        fields: str | list[str] | None = None,
        filter: str | None = None,
        has_no_reference: dict[str, str] | str | None = None,
        has_no_reference_operator: str | None = None,
        has_reference: dict[str, str] | str | None = None,
        has_reference_operator: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        search: str | None = None,
        search_fields: str | list[str] | None = None,
        sort_field: str | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Find saved objects.

        ``GET /api/saved_objects/_find``

        .. deprecated:: Kibana 8.7
            Deprecated in Kibana 9.4.3. Use the type-specific APIs (e.g.
            ``client.data_views.get_all``) or :meth:`export` instead.

        :param type: Type(s) of saved objects to find (string or list of strings)
        :param aggs: Aggregation structure, serialized as a JSON string
            (a dict is JSON-encoded automatically)
        :param default_search_operator: The default operator to use for the
            simple_query_string search ("AND" or "OR")
        :param fields: Attribute field(s) of the object to return in the
            response (string or list; lists are sent as repeated keys)
        :param filter: KQL string to filter on attributes or references
            (e.g. "dashboard.attributes.title: foo")
        :param has_no_reference: Filter to objects NOT having a reference to
            the given {"type": ..., "id": ...} object
        :param has_no_reference_operator: Operator ("AND"/"OR") for
            has_no_reference when multiple references are given
        :param has_reference: Filter to objects having a reference to the
            given {"type": ..., "id": ...} object
        :param has_reference_operator: Operator ("AND"/"OR") for has_reference
            when multiple references are given
        :param page: Page number
        :param per_page: Items per page
        :param search: An Elasticsearch simple_query_string query that filters
            the objects in the response
        :param search_fields: Field(s) to perform the search query against
            (string or list; lists are sent as repeated keys)
        :param sort_field: Field to sort by
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: ObjectApiResponse containing search results
        :raises BadRequestError: If the query parameters are invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> results = await client.saved_objects.find(
            ...     type=["dashboard", "tag"],
            ...     search="sales*",
            ...     search_fields=["title", "description"],
            ...     per_page=50,
            ... )
            >>> print(results["total"])
        """
        params: dict[str, Any] = {"type": type}
        if aggs is not None:
            params["aggs"] = aggs
        if default_search_operator is not None:
            params["default_search_operator"] = default_search_operator
        if fields is not None:
            params["fields"] = fields
        if filter is not None:
            params["filter"] = filter
        if has_no_reference is not None:
            params["has_no_reference"] = has_no_reference
        if has_no_reference_operator is not None:
            params["has_no_reference_operator"] = has_no_reference_operator
        if has_reference is not None:
            params["has_reference"] = has_reference
        if has_reference_operator is not None:
            params["has_reference_operator"] = has_reference_operator
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if search is not None:
            params["search"] = search
        if search_fields is not None:
            params["search_fields"] = search_fields
        if sort_field is not None:
            params["sort_field"] = sort_field

        path = self._build_space_path("/api/saved_objects/_find", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

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
    ) -> ObjectApiResponse[Any]:
        """
        Update an existing saved object.

        ``PUT /api/saved_objects/{type}/{id}``

        .. deprecated:: Kibana 8.7
            Deprecated in Kibana 9.4.3. Use the type-specific APIs (e.g.
            ``client.dashboards.update``) or :meth:`import_objects` with
            ``overwrite=True`` instead.

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
            >>> updated = await client.saved_objects.update(
            ...     type="dashboard",
            ...     id="my-dashboard-id",
            ...     attributes={"title": "Updated Dashboard Title"}
            ... )

            >>> # Update with version for optimistic concurrency
            >>> updated = await client.saved_objects.update(
            ...     type="dashboard",
            ...     id="my-dashboard-id",
            ...     attributes={"title": "Updated Title"},
            ...     version="WzEsMV0="
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
    ) -> ObjectApiResponse[Any]:
        """
        Delete a saved object.

        ``DELETE /api/saved_objects/{type}/{id}``

        .. deprecated:: Kibana 8.7
            Deprecated (and removed from the 9.4.3 OpenAPI spec, though still
            functional). Use the type-specific APIs (e.g.
            ``client.dashboards.delete``) instead.

        :param type: Type of saved object
        :param id: ID of the saved object
        :param force: If true, force delete objects that exist in multiple namespaces
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Deletion confirmation
        :raises ValueError: If required parameters are missing
        :raises NotFoundError: If the saved object is not found
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> await client.saved_objects.delete(
            ...     type="dashboard",
            ...     id="my-dashboard-id"
            ... )
        """
        # Validate required parameters
        if not type:
            raise ValueError("Parameter 'type' is required")
        if not id:
            raise ValueError("Parameter 'id' is required")

        # Build request path using base class utility
        path = self._build_space_path(
            f"/api/saved_objects/{_quote(type)}/{_quote(id)}", space_id
        )

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        # Build query parameters
        params: dict[str, Any] = {}
        if force:
            params["force"] = force

        # Make the request
        return await self.perform_request(
            method="DELETE",
            path=path,
            params=params if params else None,
        )

    async def bulk_create(
        self,
        *,
        objects: list[dict[str, Any]],
        overwrite: bool | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Create multiple saved objects in one request.

        ``POST /api/saved_objects/_bulk_create``

        .. deprecated:: Kibana 8.7
            Deprecated in Kibana 9.4.3. Use the type-specific APIs or
            :meth:`import_objects` instead.

        :param objects: List of objects to create. Each object supports keys
            like ``type`` (required), ``attributes`` (required), ``id``,
            ``references``, ``initialNamespaces``, ``coreMigrationVersion``
            and ``typeMigrationVersion``.
        :param overwrite: If true, overwrite existing objects with the same ID
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Bulk create results with a ``saved_objects`` array
        :raises ValueError: If required parameters are missing
        :raises BadRequestError: If any object payload is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> result = await client.saved_objects.bulk_create(
            ...     objects=[
            ...         {"type": "tag", "id": "tag-1",
            ...          "attributes": {"name": "one", "description": "", "color": "#000000"}},
            ...         {"type": "tag", "id": "tag-2",
            ...          "attributes": {"name": "two", "description": "", "color": "#ffffff"}},
            ...     ]
            ... )
            >>> print(len(result["saved_objects"]))
        """
        if not objects:
            raise ValueError("Parameter 'objects' is required")

        path = self._build_space_path("/api/saved_objects/_bulk_create", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        params: dict[str, Any] = {}
        if overwrite is not None:
            params["overwrite"] = overwrite

        return await self.perform_request(
            method="POST",
            path=path,
            body=objects,  # type: ignore[arg-type]
            params=params if params else None,
        )

    async def bulk_get(
        self,
        *,
        objects: list[dict[str, Any]],
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Get multiple saved objects in one request.

        ``POST /api/saved_objects/_bulk_get``

        .. deprecated:: Kibana 8.7
            Deprecated in Kibana 9.4.3. Use the type-specific APIs or
            :meth:`export` instead.

        :param objects: List of ``{"type": ..., "id": ...}`` descriptors
            (optionally with ``fields`` or ``namespaces``)
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Bulk get results with a ``saved_objects`` array (objects that
            were not found carry an ``error`` entry)
        :raises ValueError: If required parameters are missing
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> result = await client.saved_objects.bulk_get(
            ...     objects=[{"type": "dashboard", "id": "my-dashboard-id"}]
            ... )
            >>> print(result["saved_objects"][0]["attributes"]["title"])
        """
        if not objects:
            raise ValueError("Parameter 'objects' is required")

        path = self._build_space_path("/api/saved_objects/_bulk_get", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        return await self.perform_request(
            method="POST",
            path=path,
            body=objects,  # type: ignore[arg-type]
        )

    async def bulk_resolve(
        self,
        *,
        objects: list[dict[str, Any]],
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Resolve multiple saved objects in one request.

        ``POST /api/saved_objects/_bulk_resolve``

        Like :meth:`resolve` but for multiple objects: retrieves saved objects
        by ID, following legacy URL aliases if they exist.

        .. deprecated:: Kibana 8.7
            Deprecated in Kibana 9.4.3. Use the type-specific APIs or
            :meth:`export` instead.

        :param objects: List of ``{"type": ..., "id": ...}`` descriptors
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Bulk resolve results with a ``resolved_objects`` array; each
            entry has ``saved_object`` and ``outcome``
        :raises ValueError: If required parameters are missing
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> result = await client.saved_objects.bulk_resolve(
            ...     objects=[{"type": "dashboard", "id": "my-dashboard-id"}]
            ... )
            >>> print(result["resolved_objects"][0]["outcome"])
        """
        if not objects:
            raise ValueError("Parameter 'objects' is required")

        path = self._build_space_path("/api/saved_objects/_bulk_resolve", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        return await self.perform_request(
            method="POST",
            path=path,
            body=objects,  # type: ignore[arg-type]
        )

    async def bulk_update(
        self,
        *,
        objects: list[dict[str, Any]],
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Update multiple saved objects in one request.

        ``POST /api/saved_objects/_bulk_update``

        .. deprecated:: Kibana 8.7
            Deprecated in Kibana 9.4.3. Use the type-specific APIs or
            :meth:`import_objects` with ``overwrite=True`` instead.

        WARNING: Although still present in the Kibana 9.4.3 OpenAPI spec,
        this route is no longer registered on Kibana 9.4.3 servers; requests
        fall through to the create-saved-object route and fail with a 400
        ("expected a plain object value, but found [Array]"). Call
        :meth:`update` per object on 9.4.3.

        :param objects: List of update descriptors; each supports ``type``
            (required), ``id`` (required), ``attributes``, ``references``,
            ``version`` and ``namespace``.
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Bulk update results with a ``saved_objects`` array
        :raises ValueError: If required parameters are missing
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> result = await client.saved_objects.bulk_update(
            ...     objects=[{
            ...         "type": "dashboard",
            ...         "id": "my-dashboard-id",
            ...         "attributes": {"title": "New Title"},
            ...     }]
            ... )
        """
        if not objects:
            raise ValueError("Parameter 'objects' is required")

        path = self._build_space_path("/api/saved_objects/_bulk_update", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        return await self.perform_request(
            method="POST",
            path=path,
            body=objects,  # type: ignore[arg-type]
        )

    async def bulk_delete(
        self,
        *,
        objects: list[dict[str, Any]],
        force: bool | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Delete multiple saved objects in one request.

        ``POST /api/saved_objects/_bulk_delete``

        WARNING: When you delete a saved object, it cannot be recovered.

        .. deprecated:: Kibana 8.7
            Deprecated in Kibana 9.4.3. Use the type-specific APIs instead.

        :param objects: List of ``{"type": ..., "id": ...}`` descriptors
        :param force: If true, force delete objects that exist in multiple
            namespaces (applies to all objects in the request)
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Bulk delete results with a ``statuses`` array
        :raises ValueError: If required parameters are missing
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> result = await client.saved_objects.bulk_delete(
            ...     objects=[{"type": "tag", "id": "tag-1"}]
            ... )
            >>> print(result["statuses"][0]["success"])
        """
        if not objects:
            raise ValueError("Parameter 'objects' is required")

        path = self._build_space_path("/api/saved_objects/_bulk_delete", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        params: dict[str, Any] = {}
        if force is not None:
            params["force"] = force

        return await self.perform_request(
            method="POST",
            path=path,
            body=objects,  # type: ignore[arg-type]
            params=params if params else None,
        )

    async def export(
        self,
        *,
        objects: list[dict[str, str]] | None = None,
        type: str | list[str] | None = None,
        search: str | None = None,
        has_reference: dict[str, str] | list[dict[str, str]] | None = None,
        exclude_export_details: bool | None = None,
        include_references_deep: bool | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Export saved objects as NDJSON.

        ``POST /api/saved_objects/_export``

        Retrieves sets of saved objects that you want to import into Kibana.
        The response body is NDJSON: one exported object per line, plus (unless
        ``exclude_export_details=True``) a final export-details line. The
        parsed response body is a list of dicts.

        NOTE: ``objects`` cannot be combined with ``type``; pass one or the
        other. This API is space-aware: only objects belonging to the target
        space are exported.

        :param objects: List of ``{"type": ..., "id": ...}`` descriptors to export
        :param type: The saved object type(s) to include in the export
            (use ``"*"`` to export all types)
        :param search: Search for documents to export using the Elasticsearch
            Simple Query String syntax
        :param has_reference: Filter exported objects by reference: a single
            ``{"type": ..., "id": ...}`` dict or a list of them
        :param exclude_export_details: Do not add the export-details entry at
            the end of the stream
        :param include_references_deep: Include all of the referenced objects
            in the export
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Response whose body is the parsed NDJSON list of exported
            objects (iterate over it or serialize it back for import)
        :raises ValueError: If neither or invalid selector parameters are given
        :raises BadRequestError: If the export request is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> exported = await client.saved_objects.export(
            ...     objects=[{"type": "dashboard", "id": "my-dashboard-id"}],
            ...     include_references_deep=True,
            ... )
            >>> lines = list(exported)
            >>> print(lines[-1]["exportedCount"])
        """
        if objects is None and type is None:
            raise ValueError("Either 'objects' or 'type' must be provided")

        path = self._build_space_path("/api/saved_objects/_export", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        body: dict[str, Any] = {}
        if objects is not None:
            body["objects"] = objects
        if type is not None:
            body["type"] = type
        if search is not None:
            body["search"] = search
        if has_reference is not None:
            body["hasReference"] = has_reference
        if exclude_export_details is not None:
            body["excludeExportDetails"] = exclude_export_details
        if include_references_deep is not None:
            body["includeReferencesDeep"] = include_references_deep

        return await self.perform_request(
            method="POST",
            path=path,
            body=body,
        )

    async def import_objects(
        self,
        *,
        file: bytes | str | list[dict[str, Any]],
        create_new_copies: bool | None = None,
        overwrite: bool | None = None,
        compatibility_mode: bool | None = None,
        filename: str = "import.ndjson",
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Import saved objects from an NDJSON export file.

        ``POST /api/saved_objects/_import``

        Creates sets of Kibana saved objects from a file created by the export
        API (uploaded as ``multipart/form-data``). Saved objects can be
        imported only into the same version, a newer minor on the same major,
        or the next major. Exported saved objects are not backwards compatible
        and cannot be imported into an older version of Kibana.

        NOTE: ``create_new_copies`` cannot be combined with ``overwrite`` or
        ``compatibility_mode``.

        :param file: NDJSON export content: raw ``bytes``/``str``, or a list
            of saved-object dicts (e.g. the parsed body returned by
            :meth:`export`), which is NDJSON-encoded automatically
        :param create_new_copies: Create copies of the saved objects with
            regenerated IDs, resetting their origin references
        :param overwrite: Overwrite any existing objects with the same ID
        :param compatibility_mode: Apply various adjustments to the saved
            objects that are being imported to maintain compatibility between
            different Kibana versions (cannot be used with create_new_copies)
        :param filename: Filename advertised in the multipart upload
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Import result with ``success``, ``successCount`` and, on
            failure, an ``errors`` array
        :raises ValueError: If required parameters are missing
        :raises BadRequestError: If the import payload is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> exported = await client.saved_objects.export(
            ...     objects=[{"type": "dashboard", "id": "my-dashboard-id"}]
            ... )
            >>> result = await client.saved_objects.import_objects(
            ...     file=list(exported),
            ...     overwrite=True,
            ... )
            >>> print(result["success"], result["successCount"])
        """
        if file is None or (isinstance(file, (str, bytes, list)) and not file):
            raise ValueError("Parameter 'file' is required")

        path = self._build_space_path("/api/saved_objects/_import", space_id)

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        params: dict[str, Any] = {}
        if create_new_copies is not None:
            params["createNewCopies"] = create_new_copies
        if overwrite is not None:
            params["overwrite"] = overwrite
        if compatibility_mode is not None:
            params["compatibilityMode"] = compatibility_mode

        body, content_type = _build_multipart_body(
            _ndjson_bytes(file), filename=filename
        )

        return await self.perform_request(
            method="POST",
            path=path,
            body=body,  # type: ignore[arg-type]
            params=params if params else None,
            headers={"content-type": content_type},
        )

    async def resolve_import_errors(
        self,
        *,
        file: bytes | str | list[dict[str, Any]],
        retries: list[dict[str, Any]],
        create_new_copies: bool | None = None,
        compatibility_mode: bool | None = None,
        filename: str = "import.ndjson",
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Resolve errors from a previous import.

        ``POST /api/saved_objects/_resolve_import_errors``

        To resolve errors from the import API, you can retry certain saved
        objects, overwrite specific saved objects, or change references to
        different saved objects. The same file given to the import API is
        re-uploaded together with a list of retry operations.

        :param file: The same NDJSON content given to the import API: raw
            ``bytes``/``str`` or a list of saved-object dicts
        :param retries: The retry operations. Each entry requires ``type`` and
            ``id`` and supports ``overwrite``, ``destinationId``,
            ``replaceReferences``, ``ignoreMissingReferences``
        :param create_new_copies: Create copies of the saved objects with
            regenerated IDs, resetting their origin references
        :param compatibility_mode: Apply compatibility adjustments to the
            imported saved objects (cannot be used with create_new_copies)
        :param filename: Filename advertised in the multipart upload
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Result with ``success``, ``successCount`` and, on failure,
            an ``errors`` array
        :raises ValueError: If required parameters are missing
        :raises BadRequestError: If the payload is invalid
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> result = await client.saved_objects.resolve_import_errors(
            ...     file=exported_ndjson_bytes,
            ...     retries=[{
            ...         "type": "dashboard",
            ...         "id": "my-dashboard-id",
            ...         "overwrite": True,
            ...     }],
            ... )
            >>> print(result["success"])
        """
        if file is None or (isinstance(file, (str, bytes, list)) and not file):
            raise ValueError("Parameter 'file' is required")
        if retries is None:
            raise ValueError("Parameter 'retries' is required")

        path = self._build_space_path(
            "/api/saved_objects/_resolve_import_errors", space_id
        )

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        params: dict[str, Any] = {}
        if create_new_copies is not None:
            params["createNewCopies"] = create_new_copies
        if compatibility_mode is not None:
            params["compatibilityMode"] = compatibility_mode

        body, content_type = _build_multipart_body(
            _ndjson_bytes(file), retries=retries, filename=filename
        )

        return await self.perform_request(
            method="POST",
            path=path,
            body=body,  # type: ignore[arg-type]
            params=params if params else None,
            headers={"content-type": content_type},
        )

    async def rotate_encryption_key(
        self,
        *,
        batch_size: int | None = None,
        type: str | None = None,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Rotate the encryption key for encrypted saved objects.

        ``POST /api/encrypted_saved_objects/_rotate_key``

        Re-encrypts encrypted saved objects with the primary encryption key.
        Requires ``xpack.encryptedSavedObjects.keyRotation.decryptionOnlyKeys``
        to be configured in ``kibana.yml``; otherwise Kibana responds with a
        400 error. If a rotation is already in progress, Kibana responds 429.

        :param batch_size: Number of saved objects Kibana processes in each
            batch (default 10000)
        :param type: Limit rotation to only the given saved object type
            (e.g. "alert" or "api-key-pending-invalidation")
        :param space_id: Optional space ID for space-scoped operations
        :param validate_space: Override space validation setting for this operation
        :return: Rotation summary with ``total``, ``successful`` and ``failed``
        :raises BadRequestError: If key rotation is not configured in kibana.yml
        :raises AuthenticationException: If authentication fails
        :raises AuthorizationException: If insufficient privileges

        Example:
            >>> result = await client.saved_objects.rotate_encryption_key(
            ...     batch_size=1000, type="alert"
            ... )
            >>> print(result["successful"], result["failed"])
        """
        path = self._build_space_path(
            "/api/encrypted_saved_objects/_rotate_key", space_id
        )

        # Validate space if enabled
        await self._maybe_validate_space(space_id, validate_space)

        params: dict[str, Any] = {}
        if batch_size is not None:
            params["batch_size"] = batch_size
        if type is not None:
            params["type"] = type

        return await self.perform_request(
            method="POST",
            path=path,
            params=params if params else None,
        )
