"""Async Kibana Security Exceptions API client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote
from kibana._sync.client.saved_objects import _build_multipart_body, _ndjson_bytes

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class AsyncExceptionListsClient(AsyncNamespaceClient):
    """Async client for the Kibana Security Exceptions API.

    Exception lists group **exception items** that prevent Elastic Security
    detection rules from generating alerts when their conditions match. An
    exception list container (``/api/exception_lists``) holds items
    (``/api/exception_lists/items``), each of which defines the field entries
    (``match``, ``match_any``, ``exists``, ``list``, ``nested``, ``wildcard``)
    that suppress rule alerts.

    This client also covers:

    - Shared exception lists (``POST /api/exceptions/shared``)
    - Rule default exception items
      (``POST /api/detection_engine/rules/{id}/exceptions``)
    - The Elastic Endpoint exception list (``/api/endpoint_list`` and
      ``/api/endpoint_list/items``), an agnostic list applied to all Elastic
      Endpoint agents

    Exception lists with ``namespace_type="single"`` are space-scoped, while
    ``namespace_type="agnostic"`` lists are shared across all Kibana spaces.
    Every method accepts an optional ``space_id`` to target a specific space
    (``None`` targets the default space or the space the client is scoped to).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a detection exception list with one item
        >>> created = await client.exception_lists.create(
        ...     name="Trusted hosts",
        ...     description="Hosts that never alert",
        ...     type="detection",
        ...     list_id="trusted-hosts",
        ... )
        >>> await client.exception_lists.create_item(
        ...     list_id="trusted-hosts",
        ...     name="Trusted host",
        ...     description="Ignore the build server",
        ...     entries=[{
        ...         "field": "host.name",
        ...         "operator": "included",
        ...         "type": "match",
        ...         "value": "build-server-01",
        ...     }],
        ... )
        >>>
        >>> # Clean up
        >>> await client.exception_lists.delete(list_id="trusted-hosts")
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncExceptionListsClient.

        Args:
            client: The parent AsyncKibana client instance to delegate
                requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> exception_lists_client = AsyncExceptionListsClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    # ------------------------------------------------------------------
    # Exception list containers
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        name: str,
        description: str,
        type: str,
        list_id: str | None = None,
        meta: dict[str, Any] | None = None,
        namespace_type: str | None = None,
        os_types: list[str] | None = None,
        tags: list[str] | None = None,
        version: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an exception list.

        ``POST /api/exception_lists``

        An exception list groups exception items and can be associated with
        detection rules. You can associate multiple exception lists with a
        single rule; an exception list must exist before its items can be
        created.

        Args:
            name: The name of the exception list.
            description: Describes the exception list.
            type: The type of exception list. One of ``"detection"``,
                ``"rule_default"``, ``"endpoint"``, ``"endpoint_trusted_apps"``,
                ``"endpoint_trusted_devices"``, ``"endpoint_events"``,
                ``"endpoint_host_isolation_exceptions"`` or
                ``"endpoint_blocklists"``.
            list_id: Human readable string identifier (e.g.
                ``"trusted-linux-processes"``). Generated if omitted.
            meta: Placeholder for metadata about the list.
            namespace_type: Determines whether the list is available in the
                current Kibana space only (``"single"``, the server default)
                or in all spaces (``"agnostic"``).
            os_types: Operating systems the list applies to. Entries must be
                one of ``"linux"``, ``"macos"`` or ``"windows"``.
            tags: String array containing words and phrases to help categorize
                exception lists.
            version: The document version (server default: 1).
            space_id: Optional space ID to create the exception list in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created exception list, including
            the generated ``id``, ``list_id``, ``_version``, ``tie_breaker_id``
            and audit fields.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            ConflictError: If a list with the same ``list_id`` already exists.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = await client.exception_lists.create(
            ...     name="Trusted processes",
            ...     description="Processes that never alert",
            ...     type="detection",
            ...     list_id="trusted-processes",
            ...     tags=["linux"],
            ... )
            >>> print(created.body["id"])
        """
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "type": type,
        }
        if list_id is not None:
            body["list_id"] = list_id
        if meta is not None:
            body["meta"] = meta
        if namespace_type is not None:
            body["namespace_type"] = namespace_type
        if os_types is not None:
            body["os_types"] = os_types
        if tags is not None:
            body["tags"] = tags
        if version is not None:
            body["version"] = version

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists", space_id)
        return await self.perform_request("POST", path, body=body)

    async def get(
        self,
        *,
        id: str | None = None,
        list_id: str | None = None,
        namespace_type: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get exception list details.

        ``GET /api/exception_lists``

        Gets the details of an exception list using the ``id`` or ``list_id``
        field.

        Args:
            id: Exception list's identifier. Either ``id`` or ``list_id`` must
                be specified.
            list_id: Human readable exception list string identifier, e.g.
                ``"trusted-linux-processes"``. Either ``id`` or ``list_id``
                must be specified.
            namespace_type: Determines whether the list is scoped to the
                current space (``"single"``, the server default) or shared
                across spaces (``"agnostic"``).
            space_id: Optional space ID to get the exception list from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the exception list.

        Raises:
            ValueError: If neither ``id`` nor ``list_id`` is provided.
            NotFoundError: If the exception list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.exception_lists.get(list_id="trusted-processes")
            >>> print(found.body["name"])
        """
        if id is None and list_id is None:
            raise ValueError("Either 'id' or 'list_id' must be provided")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if list_id is not None:
            params["list_id"] = list_id
        if namespace_type is not None:
            params["namespace_type"] = namespace_type

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists", space_id)
        return await self.perform_request("GET", path, params=params)

    async def update(
        self,
        *,
        name: str,
        description: str,
        type: str,
        id: str | None = None,
        list_id: str | None = None,
        _version: str | None = None,
        meta: dict[str, Any] | None = None,
        namespace_type: str | None = None,
        os_types: list[str] | None = None,
        tags: list[str] | None = None,
        version: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update an exception list.

        ``PUT /api/exception_lists``

        Updates an exception list using the ``id`` or ``list_id`` field. The
        ``name``, ``description`` and ``type`` fields are required by the API
        and replace the stored values.

        Args:
            name: The (new) name of the exception list.
            description: The (new) description of the exception list.
            type: The type of exception list (see :meth:`create`).
            id: Exception list's identifier. Either ``id`` or ``list_id`` must
                be specified.
            list_id: Human readable exception list string identifier. Either
                ``id`` or ``list_id`` must be specified.
            _version: The version id (returned when the list was created or
                fetched), used for optimistic concurrency control.
            meta: Placeholder for metadata about the list.
            namespace_type: ``"single"`` (server default) or ``"agnostic"``.
            os_types: Operating systems the list applies to (``"linux"``,
                ``"macos"``, ``"windows"``).
            tags: String array containing words and phrases to help categorize
                exception lists.
            version: The document version to set.
            space_id: Optional space ID to update the exception list in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated exception list.

        Raises:
            NotFoundError: If the exception list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.exception_lists.update(
            ...     list_id="trusted-processes",
            ...     name="Trusted processes (updated)",
            ...     description="Updated description",
            ...     type="detection",
            ... )
            >>> print(updated.body["name"])
        """
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "type": type,
        }
        if id is not None:
            body["id"] = id
        if list_id is not None:
            body["list_id"] = list_id
        if _version is not None:
            body["_version"] = _version
        if meta is not None:
            body["meta"] = meta
        if namespace_type is not None:
            body["namespace_type"] = namespace_type
        if os_types is not None:
            body["os_types"] = os_types
        if tags is not None:
            body["tags"] = tags
        if version is not None:
            body["version"] = version

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists", space_id)
        return await self.perform_request("PUT", path, body=body)

    async def delete(
        self,
        *,
        id: str | None = None,
        list_id: str | None = None,
        namespace_type: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an exception list.

        ``DELETE /api/exception_lists``

        Deletes an exception list using the ``id`` or ``list_id`` field.

        Args:
            id: Exception list's identifier. Either ``id`` or ``list_id`` must
                be specified.
            list_id: Human readable exception list string identifier. Either
                ``id`` or ``list_id`` must be specified.
            namespace_type: ``"single"`` (server default) or ``"agnostic"``.
            space_id: Optional space ID to delete the exception list from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the deleted exception list.

        Raises:
            ValueError: If neither ``id`` nor ``list_id`` is provided.
            NotFoundError: If the exception list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.exception_lists.delete(list_id="trusted-processes")
        """
        if id is None and list_id is None:
            raise ValueError("Either 'id' or 'list_id' must be provided")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if list_id is not None:
            params["list_id"] = list_id
        if namespace_type is not None:
            params["namespace_type"] = namespace_type

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists", space_id)
        return await self.perform_request("DELETE", path, params=params)

    async def find(
        self,
        *,
        filter: str | None = None,
        namespace_type: str | list[str] | None = None,
        page: int | None = None,
        per_page: int | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a paginated subset of exception lists.

        ``GET /api/exception_lists/_find``

        By default, the first page is returned, with 20 results per page.

        Args:
            filter: Filters the returned results according to the value of the
                specified field, using the
                ``exception-list.attributes.<field>:<value>`` /
                ``exception-list-agnostic.attributes.<field>:<value>`` KQL
                syntax (e.g. ``"exception-list.attributes.name:Trusted*"``).
            namespace_type: Determines whether the returned containers are
                associated with the current Kibana space (``"single"``, the
                server default) or available in all spaces (``"agnostic"``).
                Accepts a single value or a list of both.
            page: The page number to return.
            per_page: The number of exception lists to return per page.
            sort_field: Determines which field is used to sort the results.
            sort_order: Sort order, ``"asc"`` or ``"desc"``.
            space_id: Optional space ID to search in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``data`` (the exception lists), ``page``,
            ``per_page`` and ``total``.

        Raises:
            BadRequestError: If the filter syntax is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.exception_lists.find(per_page=50)
            >>> for exception_list in found.body["data"]:
            ...     print(exception_list["list_id"], exception_list["name"])
        """
        params: dict[str, Any] = {}
        if filter is not None:
            params["filter"] = filter
        if namespace_type is not None:
            params["namespace_type"] = namespace_type
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists/_find", space_id)
        return await self.perform_request(
            "GET", path, params=params if params else None
        )

    async def duplicate(
        self,
        *,
        list_id: str,
        namespace_type: str,
        include_expired_exceptions: bool = True,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Duplicate an exception list.

        ``POST /api/exception_lists/_duplicate``

        Duplicates an existing exception list and all of its items into a new
        list (named ``"<name> [Duplicate]"`` with a generated ``list_id``).

        Args:
            list_id: Human readable string identifier of the exception list to
                duplicate.
            namespace_type: ``"single"`` or ``"agnostic"``.
            include_expired_exceptions: Whether to include expired exception
                items (as defined by their ``expire_time``) in the duplicated
                list (default: True).
            space_id: Optional space ID to duplicate the exception list in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the newly created duplicate exception
            list.

        Raises:
            NotFoundError: If the source exception list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> duplicate = await client.exception_lists.duplicate(
            ...     list_id="trusted-processes",
            ...     namespace_type="single",
            ... )
            >>> print(duplicate.body["name"])
            Trusted processes [Duplicate]
        """
        params: dict[str, Any] = {
            "list_id": list_id,
            "namespace_type": namespace_type,
            "include_expired_exceptions": include_expired_exceptions,
        }

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists/_duplicate", space_id)
        return await self.perform_request("POST", path, params=params)

    async def export(
        self,
        *,
        id: str,
        list_id: str,
        namespace_type: str,
        include_expired_exceptions: bool = True,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Export an exception list as NDJSON.

        ``POST /api/exception_lists/_export``

        Exports an exception list and its associated items. The response body
        is NDJSON: one line for the list container, one line per exception
        item and a final export-details line. The parsed response body is a
        list of dicts (one per NDJSON line) and can be passed straight to
        :meth:`import_lists`.

        Note: unlike the read APIs, the export API requires **both** ``id``
        and ``list_id``.

        Args:
            id: Exception list's identifier (generated upon creation).
            list_id: Human readable exception list string identifier.
            namespace_type: ``"single"`` or ``"agnostic"``.
            include_expired_exceptions: Whether to include expired exception
                items (as defined by their ``expire_time``) in the export
                (default: True).
            space_id: Optional space ID to export the exception list from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            Response whose body is the NDJSON export (exception list, its
            items and an export-details summary line).

        Raises:
            BadRequestError: If ``id`` or ``list_id`` is missing or invalid.
            NotFoundError: If the exception list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = await client.exception_lists.get(list_id="trusted-processes")
            >>> exported = await client.exception_lists.export(
            ...     id=created.body["id"],
            ...     list_id=created.body["list_id"],
            ...     namespace_type="single",
            ... )
            >>> ndjson = exported.body
        """
        params: dict[str, Any] = {
            "id": id,
            "list_id": list_id,
            "namespace_type": namespace_type,
            "include_expired_exceptions": include_expired_exceptions,
        }

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists/_export", space_id)
        return await self.perform_request("POST", path, params=params)

    async def import_lists(
        self,
        *,
        file: bytes | str | list[dict[str, Any]],
        overwrite: bool | None = None,
        as_new_list: bool | None = None,
        filename: str = "import.ndjson",
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Import an exception list and its items from an NDJSON file.

        ``POST /api/exception_lists/_import``

        Imports exception lists and items from an NDJSON export (uploaded as
        ``multipart/form-data``).

        Args:
            file: NDJSON export content: raw ``bytes``/``str`` (e.g. the body
                returned by :meth:`export`), or a list of dicts (one per
                exported line), which is NDJSON-encoded automatically.
            overwrite: Determines whether existing exception lists with the
                same ``list_id`` are overwritten. If any exception items have
                the same ``item_id``, those are also overwritten
                (server default: False).
            as_new_list: Determines whether the list being imported will have
                a new ``list_id`` generated. Additional ``item_id``'s are
                generated for each exception item. Both the exception list and
                its items are overwritten (server default: False).
            filename: Filename advertised in the multipart upload.
            space_id: Optional space ID to import the exception list into.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the import summary: ``success``,
            ``success_count``, ``success_exception_lists``,
            ``success_count_exception_lists``,
            ``success_exception_list_items``,
            ``success_count_exception_list_items`` and an ``errors`` array.

        Raises:
            ValueError: If ``file`` is empty.
            BadRequestError: If the NDJSON payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> exported = await client.exception_lists.export(
            ...     id="...", list_id="trusted-processes",
            ...     namespace_type="single",
            ... )
            >>> result = await client.exception_lists.import_lists(
            ...     file=exported.body, as_new_list=True,
            ... )
            >>> print(result.body["success"])
            True
        """
        if file is None or (isinstance(file, (str, bytes, list)) and not file):
            raise ValueError("Parameter 'file' is required")

        params: dict[str, Any] = {}
        if overwrite is not None:
            params["overwrite"] = overwrite
        if as_new_list is not None:
            params["as_new_list"] = as_new_list

        body, content_type = _build_multipart_body(
            _ndjson_bytes(file), filename=filename
        )

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists/_import", space_id)
        return await self.perform_request(
            "POST",
            path,
            params=params if params else None,
            headers={"content-type": content_type},
            body=body,  # type: ignore[arg-type]
        )

    async def get_summary(
        self,
        *,
        id: str | None = None,
        list_id: str | None = None,
        namespace_type: str | None = None,
        filter: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an exception list summary.

        ``GET /api/exception_lists/summary``

        Retrieves a per-OS summary of the number of exception items in an
        exception list.

        Args:
            id: Exception list's identifier generated upon creation. Either
                ``id`` or ``list_id`` must be specified.
            list_id: Exception list's human readable identifier. Either ``id``
                or ``list_id`` must be specified.
            namespace_type: ``"single"`` (server default) or ``"agnostic"``.
            filter: Search filter clause (KQL over the exception list item
                saved object attributes).
            space_id: Optional space ID to read the summary from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the per-OS item counts: ``windows``,
            ``linux``, ``macos`` and ``total``. Note: the counts are grouped
            by the items' ``os_types``, so items without an ``os_types``
            value are not reflected in ``total``.

        Raises:
            ValueError: If neither ``id`` nor ``list_id`` is provided.
            NotFoundError: If the exception list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> summary = await client.exception_lists.get_summary(
            ...     list_id="trusted-processes"
            ... )
            >>> print(summary.body["total"])
        """
        if id is None and list_id is None:
            raise ValueError("Either 'id' or 'list_id' must be provided")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if list_id is not None:
            params["list_id"] = list_id
        if namespace_type is not None:
            params["namespace_type"] = namespace_type
        if filter is not None:
            params["filter"] = filter

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists/summary", space_id)
        return await self.perform_request("GET", path, params=params)

    # ------------------------------------------------------------------
    # Exception list items
    # ------------------------------------------------------------------

    async def create_item(
        self,
        *,
        list_id: str,
        name: str,
        description: str,
        entries: list[dict[str, Any]],
        type: str = "simple",
        comments: list[dict[str, Any]] | None = None,
        expire_time: str | None = None,
        item_id: str | None = None,
        meta: dict[str, Any] | None = None,
        namespace_type: str | None = None,
        os_types: list[str] | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an exception list item.

        ``POST /api/exception_lists/items``

        Creates an exception item and associates it with the specified
        exception list (which must already exist). Each entry describes a
        field condition; when a rule's conditions and an item's entries both
        match an event, no alert is generated.

        Args:
            list_id: Human readable string identifier of the exception list
                this item belongs to.
            name: Exception item's name.
            description: Describes the exception item.
            entries: The item's entries. Each entry is a dict with ``field``,
                ``operator`` (``"included"``/``"excluded"``) and ``type``
                (``"match"``, ``"match_any"``, ``"exists"``, ``"list"``,
                ``"nested"`` or ``"wildcard"``), plus a ``value`` where
                applicable.
            type: Exception item's type. Only ``"simple"`` is supported
                (default: ``"simple"``).
            comments: Array of ``{"comment": "..."}`` dicts attached to the
                item.
            expire_time: ISO 8601 date-time after which the item expires and
                no longer suppresses alerts.
            item_id: Human readable string identifier for the item. Generated
                if omitted.
            meta: Placeholder for metadata about the item.
            namespace_type: ``"single"`` (server default) or ``"agnostic"``.
                Must match the parent list's ``namespace_type``.
            os_types: Operating systems the item applies to (``"linux"``,
                ``"macos"``, ``"windows"``).
            tags: String array of words and phrases to help categorize items.
            space_id: Optional space ID to create the item in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created exception list item.

        Raises:
            BadRequestError: If the request body is invalid.
            NotFoundError: If the parent exception list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            ConflictError: If an item with the same ``item_id`` already
                exists.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> item = await client.exception_lists.create_item(
            ...     list_id="trusted-processes",
            ...     name="Trusted host",
            ...     description="Ignore the build server",
            ...     entries=[{
            ...         "field": "host.name",
            ...         "operator": "included",
            ...         "type": "match",
            ...         "value": "build-server-01",
            ...     }],
            ... )
            >>> print(item.body["item_id"])
        """
        body: dict[str, Any] = {
            "list_id": list_id,
            "name": name,
            "description": description,
            "entries": entries,
            "type": type,
        }
        if comments is not None:
            body["comments"] = comments
        if expire_time is not None:
            body["expire_time"] = expire_time
        if item_id is not None:
            body["item_id"] = item_id
        if meta is not None:
            body["meta"] = meta
        if namespace_type is not None:
            body["namespace_type"] = namespace_type
        if os_types is not None:
            body["os_types"] = os_types
        if tags is not None:
            body["tags"] = tags

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists/items", space_id)
        return await self.perform_request("POST", path, body=body)

    async def get_item(
        self,
        *,
        id: str | None = None,
        item_id: str | None = None,
        namespace_type: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an exception list item.

        ``GET /api/exception_lists/items``

        Gets the details of an exception list item using the ``id`` or
        ``item_id`` field.

        Args:
            id: Exception list item's identifier. Either ``id`` or ``item_id``
                must be specified.
            item_id: Human readable exception item string identifier. Either
                ``id`` or ``item_id`` must be specified.
            namespace_type: ``"single"`` (server default) or ``"agnostic"``.
            space_id: Optional space ID to get the item from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the exception list item.

        Raises:
            ValueError: If neither ``id`` nor ``item_id`` is provided.
            NotFoundError: If the exception list item does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> item = await client.exception_lists.get_item(item_id="trusted-host")
            >>> print(item.body["name"])
        """
        if id is None and item_id is None:
            raise ValueError("Either 'id' or 'item_id' must be provided")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if item_id is not None:
            params["item_id"] = item_id
        if namespace_type is not None:
            params["namespace_type"] = namespace_type

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists/items", space_id)
        return await self.perform_request("GET", path, params=params)

    async def update_item(
        self,
        *,
        name: str,
        description: str,
        entries: list[dict[str, Any]],
        type: str = "simple",
        id: str | None = None,
        item_id: str | None = None,
        list_id: str | None = None,
        _version: str | None = None,
        comments: list[dict[str, Any]] | None = None,
        expire_time: str | None = None,
        meta: dict[str, Any] | None = None,
        namespace_type: str | None = None,
        os_types: list[str] | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update an exception list item.

        ``PUT /api/exception_lists/items``

        Updates an exception list item using the ``id`` or ``item_id`` field.
        The ``name``, ``description``, ``type`` and ``entries`` fields are
        required by the API and replace the stored values.

        Args:
            name: The (new) exception item's name.
            description: The (new) description of the exception item.
            entries: The (new) item's entries (see :meth:`create_item`).
            type: Exception item's type. Only ``"simple"`` is supported
                (default: ``"simple"``).
            id: Exception item's identifier. Either ``id`` or ``item_id`` must
                be specified.
            item_id: Human readable exception item string identifier. Either
                ``id`` or ``item_id`` must be specified.
            list_id: Human readable string identifier of the parent exception
                list.
            _version: The version id (returned when the item was created or
                fetched), used for optimistic concurrency control.
            comments: Array of ``{"comment": "..."}`` dicts. Include existing
                comments (with their ``id``) to preserve them.
            expire_time: ISO 8601 date-time after which the item expires.
            meta: Placeholder for metadata about the item.
            namespace_type: ``"single"`` (server default) or ``"agnostic"``.
            os_types: Operating systems the item applies to (``"linux"``,
                ``"macos"``, ``"windows"``).
            tags: String array of words and phrases to help categorize items.
            space_id: Optional space ID to update the item in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated exception list item.

        Raises:
            NotFoundError: If the exception list item does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.exception_lists.update_item(
            ...     item_id="trusted-host",
            ...     name="Trusted host (updated)",
            ...     description="Updated entry",
            ...     entries=[{
            ...         "field": "host.name",
            ...         "operator": "included",
            ...         "type": "match",
            ...         "value": "build-server-02",
            ...     }],
            ... )
            >>> print(updated.body["entries"][0]["value"])
            build-server-02
        """
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "entries": entries,
            "type": type,
        }
        if id is not None:
            body["id"] = id
        if item_id is not None:
            body["item_id"] = item_id
        if list_id is not None:
            body["list_id"] = list_id
        if _version is not None:
            body["_version"] = _version
        if comments is not None:
            body["comments"] = comments
        if expire_time is not None:
            body["expire_time"] = expire_time
        if meta is not None:
            body["meta"] = meta
        if namespace_type is not None:
            body["namespace_type"] = namespace_type
        if os_types is not None:
            body["os_types"] = os_types
        if tags is not None:
            body["tags"] = tags

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists/items", space_id)
        return await self.perform_request("PUT", path, body=body)

    async def delete_item(
        self,
        *,
        id: str | None = None,
        item_id: str | None = None,
        namespace_type: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an exception list item.

        ``DELETE /api/exception_lists/items``

        Deletes an exception list item using the ``id`` or ``item_id`` field.

        Args:
            id: Exception item's identifier. Either ``id`` or ``item_id`` must
                be specified.
            item_id: Human readable exception item string identifier. Either
                ``id`` or ``item_id`` must be specified.
            namespace_type: ``"single"`` (server default) or ``"agnostic"``.
            space_id: Optional space ID to delete the item from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the deleted exception list item.

        Raises:
            ValueError: If neither ``id`` nor ``item_id`` is provided.
            NotFoundError: If the exception list item does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.exception_lists.delete_item(item_id="trusted-host")
        """
        if id is None and item_id is None:
            raise ValueError("Either 'id' or 'item_id' must be provided")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if item_id is not None:
            params["item_id"] = item_id
        if namespace_type is not None:
            params["namespace_type"] = namespace_type

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists/items", space_id)
        return await self.perform_request("DELETE", path, params=params)

    async def find_items(
        self,
        *,
        list_id: str | list[str],
        filter: str | list[str] | None = None,
        namespace_type: str | list[str] | None = None,
        search: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a paginated subset of exception list items.

        ``GET /api/exception_lists/items/_find``

        Returns the exception items of the specified list(s). By default, the
        first page is returned, with 20 results per page.

        Args:
            list_id: The ``list_id`` (or list of ``list_id``'s) of the
                exception lists whose items to fetch.
            filter: Filters the returned results according to the value of
                the specified field, using the
                ``exception-list.attributes.<field>:<value>`` KQL syntax.
                Accepts a single clause or a list of clauses (one per
                ``list_id``).
            namespace_type: ``"single"`` (server default) or ``"agnostic"``.
                Accepts a single value or a list of values (one per
                ``list_id``).
            search: Simple query string searched across the items.
            page: The page number to return.
            per_page: The number of exception list items to return per page.
            sort_field: Determines which field is used to sort the results.
            sort_order: Sort order, ``"asc"`` or ``"desc"``.
            space_id: Optional space ID to search in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``data`` (the exception list items),
            ``page``, ``per_page`` and ``total``.

        Raises:
            BadRequestError: If the filter syntax is invalid.
            NotFoundError: If the exception list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.exception_lists.find_items(
            ...     list_id="trusted-processes", per_page=50,
            ... )
            >>> print(found.body["total"])
        """
        params: dict[str, Any] = {"list_id": list_id}
        if filter is not None:
            params["filter"] = filter
        if namespace_type is not None:
            params["namespace_type"] = namespace_type
        if search is not None:
            params["search"] = search
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exception_lists/items/_find", space_id)
        return await self.perform_request("GET", path, params=params)

    # ------------------------------------------------------------------
    # Shared exception lists and rule default exceptions
    # ------------------------------------------------------------------

    async def create_shared_list(
        self,
        *,
        name: str,
        description: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a shared exception list.

        ``POST /api/exceptions/shared``

        An exception list groups exception items and can be associated with
        detection rules. A shared exception list can apply to multiple
        detection rules. This is a convenience endpoint that creates a
        ``detection`` type exception list with a generated ``list_id``.

        Args:
            name: The name of the shared exception list.
            description: Describes the shared exception list.
            space_id: Optional space ID to create the shared exception list
                in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created exception list (type
            ``"detection"``, generated ``list_id``).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> shared = await client.exception_lists.create_shared_list(
            ...     name="Shared exceptions",
            ...     description="Exceptions shared across rules",
            ... )
            >>> print(shared.body["type"])
            detection
        """
        body: dict[str, Any] = {
            "name": name,
            "description": description,
        }

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/exceptions/shared", space_id)
        return await self.perform_request("POST", path, body=body)

    async def create_rule_exceptions(
        self,
        *,
        id: str,
        items: list[dict[str, Any]],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create exception items for a detection rule's default list.

        ``POST /api/detection_engine/rules/{id}/exceptions``

        Creates exception items and adds them to the rule's default exception
        list (creating the ``rule_default`` list if it does not exist yet).

        Args:
            id: The detection rule's identifier — the rule's UUID ``id``, not
                the human readable ``rule_id``.
            items: The exception items to create. Each item is a dict with the
                same fields accepted by :meth:`create_item`, minus ``list_id``
                (``name``, ``description``, ``type``, ``entries`` and
                optionally ``comments``, ``expire_time``, ``item_id``,
                ``meta``, ``namespace_type``, ``os_types``, ``tags``).
            space_id: Optional space ID the rule lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            Response whose body is the array of created exception list items.

        Raises:
            BadRequestError: If the request body is invalid.
            NotFoundError: If the detection rule does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = await client.exception_lists.create_rule_exceptions(
            ...     id="4656dc92-5832-11ea-8e2d-0242ac130003",
            ...     items=[{
            ...         "name": "Rule exception",
            ...         "description": "Suppress the build server",
            ...         "type": "simple",
            ...         "entries": [{
            ...             "field": "host.name",
            ...             "operator": "included",
            ...             "type": "match",
            ...             "value": "build-server-01",
            ...         }],
            ...     }],
            ... )
            >>> print(created.body[0]["list_id"])
        """
        body: dict[str, Any] = {"items": items}

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/detection_engine/rules/{_quote(id)}/exceptions", space_id
        )
        return await self.perform_request("POST", path, body=body)

    # ------------------------------------------------------------------
    # Elastic Endpoint exception list
    # ------------------------------------------------------------------

    async def create_endpoint_list(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create the Elastic Endpoint exception list.

        ``POST /api/endpoint_list``

        Creates the agnostic Elastic Endpoint rule exception list (fixed
        ``list_id`` ``"endpoint_list"``), which is applied to all Elastic
        Endpoint agents. The operation is idempotent: if the list already
        exists, the server responds with ``200`` and an empty JSON object
        instead of the list.

        Args:
            space_id: Optional space ID to issue the request in (the endpoint
                list itself is space agnostic).
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created endpoint exception list,
            or an empty object (``{}``) if the list already existed.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = await client.exception_lists.create_endpoint_list()
            >>> # {} means the endpoint list already existed
            >>> print(response.body.get("list_id", "already existed"))
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint_list", space_id)
        return await self.perform_request("POST", path)

    async def create_endpoint_item(
        self,
        *,
        name: str,
        description: str,
        entries: list[dict[str, Any]],
        type: str = "simple",
        comments: list[dict[str, Any]] | None = None,
        item_id: str | None = None,
        meta: dict[str, Any] | None = None,
        os_types: list[str] | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an Elastic Endpoint exception list item.

        ``POST /api/endpoint_list/items``

        Creates an exception item in the Elastic Endpoint exception list. If
        the endpoint list does not exist yet, it is created first (see
        :meth:`create_endpoint_list`).

        Args:
            name: Exception item's name.
            description: Describes the exception item.
            entries: The item's entries (see :meth:`create_item`).
            type: Exception item's type. Only ``"simple"`` is supported
                (default: ``"simple"``).
            comments: Array of ``{"comment": "..."}`` dicts attached to the
                item.
            item_id: Human readable string identifier for the item. Generated
                if omitted.
            meta: Placeholder for metadata about the item.
            os_types: Operating systems the item applies to (``"linux"``,
                ``"macos"``, ``"windows"``).
            tags: String array of words and phrases to help categorize items.
            space_id: Optional space ID to issue the request in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created endpoint exception list
            item (``list_id`` is always ``"endpoint_list"``, ``namespace_type``
            ``"agnostic"``).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            ConflictError: If an item with the same ``item_id`` already
                exists.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> item = await client.exception_lists.create_endpoint_item(
            ...     name="Trusted process",
            ...     description="Ignore the backup agent",
            ...     os_types=["windows"],
            ...     entries=[{
            ...         "field": "process.executable.caseless",
            ...         "operator": "included",
            ...         "type": "match",
            ...         "value": "C:\\\\Program Files\\\\Backup\\\\agent.exe",
            ...     }],
            ... )
            >>> print(item.body["list_id"])
            endpoint_list
        """
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "entries": entries,
            "type": type,
        }
        if comments is not None:
            body["comments"] = comments
        if item_id is not None:
            body["item_id"] = item_id
        if meta is not None:
            body["meta"] = meta
        if os_types is not None:
            body["os_types"] = os_types
        if tags is not None:
            body["tags"] = tags

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint_list/items", space_id)
        return await self.perform_request("POST", path, body=body)

    async def get_endpoint_item(
        self,
        *,
        id: str | None = None,
        item_id: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an Elastic Endpoint exception list item.

        ``GET /api/endpoint_list/items``

        Gets the details of an endpoint exception list item using the ``id``
        or ``item_id`` field.

        Args:
            id: Exception item's identifier. Either ``id`` or ``item_id`` must
                be specified.
            item_id: Human readable exception item string identifier. Either
                ``id`` or ``item_id`` must be specified.
            space_id: Optional space ID to issue the request in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the endpoint exception list item.

        Raises:
            ValueError: If neither ``id`` nor ``item_id`` is provided.
            NotFoundError: If the item (or the endpoint list) does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> item = await client.exception_lists.get_endpoint_item(
            ...     item_id="trusted-process"
            ... )
            >>> print(item.body["name"])
        """
        if id is None and item_id is None:
            raise ValueError("Either 'id' or 'item_id' must be provided")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if item_id is not None:
            params["item_id"] = item_id

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint_list/items", space_id)
        return await self.perform_request("GET", path, params=params)

    async def update_endpoint_item(
        self,
        *,
        name: str,
        description: str,
        entries: list[dict[str, Any]],
        type: str = "simple",
        id: str | None = None,
        item_id: str | None = None,
        _version: str | None = None,
        comments: list[dict[str, Any]] | None = None,
        meta: dict[str, Any] | None = None,
        os_types: list[str] | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update an Elastic Endpoint exception list item.

        ``PUT /api/endpoint_list/items``

        Updates an endpoint exception list item using the ``id`` or
        ``item_id`` field. The ``name``, ``description``, ``type`` and
        ``entries`` fields are required by the API and replace the stored
        values.

        Args:
            name: The (new) exception item's name.
            description: The (new) description of the exception item.
            entries: The (new) item's entries (see :meth:`create_item`).
            type: Exception item's type. Only ``"simple"`` is supported
                (default: ``"simple"``).
            id: Exception item's identifier. Either ``id`` or ``item_id`` must
                be specified.
            item_id: Human readable exception item string identifier. Either
                ``id`` or ``item_id`` must be specified.
            _version: The version id (returned when the item was created or
                fetched), used for optimistic concurrency control.
            comments: Array of ``{"comment": "..."}`` dicts. Include existing
                comments (with their ``id``) to preserve them.
            meta: Placeholder for metadata about the item.
            os_types: Operating systems the item applies to (``"linux"``,
                ``"macos"``, ``"windows"``).
            tags: String array of words and phrases to help categorize items.
            space_id: Optional space ID to issue the request in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated endpoint exception list
            item.

        Raises:
            NotFoundError: If the item (or the endpoint list) does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.exception_lists.update_endpoint_item(
            ...     item_id="trusted-process",
            ...     name="Trusted process (updated)",
            ...     description="Updated entry",
            ...     os_types=["windows"],
            ...     entries=[{
            ...         "field": "process.executable.caseless",
            ...         "operator": "included",
            ...         "type": "match",
            ...         "value": "C:\\\\Program Files\\\\Backup\\\\agent2.exe",
            ...     }],
            ... )
            >>> print(updated.body["name"])
            Trusted process (updated)
        """
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "entries": entries,
            "type": type,
        }
        if id is not None:
            body["id"] = id
        if item_id is not None:
            body["item_id"] = item_id
        if _version is not None:
            body["_version"] = _version
        if comments is not None:
            body["comments"] = comments
        if meta is not None:
            body["meta"] = meta
        if os_types is not None:
            body["os_types"] = os_types
        if tags is not None:
            body["tags"] = tags

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint_list/items", space_id)
        return await self.perform_request("PUT", path, body=body)

    async def delete_endpoint_item(
        self,
        *,
        id: str | None = None,
        item_id: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an Elastic Endpoint exception list item.

        ``DELETE /api/endpoint_list/items``

        Deletes an endpoint exception list item using the ``id`` or
        ``item_id`` field.

        Args:
            id: Exception item's identifier. Either ``id`` or ``item_id`` must
                be specified.
            item_id: Human readable exception item string identifier. Either
                ``id`` or ``item_id`` must be specified.
            space_id: Optional space ID to issue the request in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the deleted endpoint exception list
            item.

        Raises:
            ValueError: If neither ``id`` nor ``item_id`` is provided.
            NotFoundError: If the item (or the endpoint list) does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.exception_lists.delete_endpoint_item(
            ...     item_id="trusted-process"
            ... )
        """
        if id is None and item_id is None:
            raise ValueError("Either 'id' or 'item_id' must be provided")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if item_id is not None:
            params["item_id"] = item_id

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint_list/items", space_id)
        return await self.perform_request("DELETE", path, params=params)

    async def find_endpoint_items(
        self,
        *,
        filter: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a paginated subset of Elastic Endpoint exception list items.

        ``GET /api/endpoint_list/items/_find``

        By default, the first page is returned, with 20 results per page.

        Args:
            filter: Filters the returned results according to the value of the
                specified field, using the
                ``exception-list-agnostic.attributes.<field>:<value>`` KQL
                syntax.
            page: The page number to return.
            per_page: The number of exception list items to return per page.
            sort_field: Determines which field is used to sort the results.
            sort_order: Sort order, ``"asc"`` or ``"desc"``.
            space_id: Optional space ID to issue the request in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``data`` (the endpoint exception list
            items), ``page``, ``per_page`` and ``total``.

        Raises:
            BadRequestError: If the filter syntax is invalid.
            NotFoundError: If the endpoint list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.exception_lists.find_endpoint_items(per_page=50)
            >>> print(found.body["total"])
        """
        params: dict[str, Any] = {}
        if filter is not None:
            params["filter"] = filter
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint_list/items/_find", space_id)
        return await self.perform_request(
            "GET", path, params=params if params else None
        )
