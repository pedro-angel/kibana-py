"""Async Kibana Security Lists API client."""

import re
import uuid
from typing import TYPE_CHECKING, Any

from elastic_transport import NdjsonSerializer, ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


def _values_file_bytes(file: bytes | str | list[str]) -> bytes:
    """Normalize a value-list import payload to newline-separated bytes.

    Accepts raw ``bytes``/``str`` (e.g. the content of a ``.txt``/``.csv``
    file) or a list of values, which are joined one-value-per-line.

    :param file: File content as bytes/str, or a list of values to encode
    :return: Newline-separated value bytes
    """
    if isinstance(file, bytes):
        return file
    if isinstance(file, str):
        return file.encode("utf-8")
    return ("\n".join(str(value) for value in file) + "\n").encode("utf-8")


def _build_multipart_body(file: bytes, *, filename: str) -> tuple[bytes, str]:
    """Build a ``multipart/form-data`` body for the list items import API.

    :param file: Newline-separated list item values for the ``file`` form field
    :param filename: Filename advertised for the uploaded file part. When a
        new list is created from the import, Kibana uses this filename as the
        list's ``id`` and ``name``.
    :return: Tuple of (body bytes, content-type header value with boundary)
    """
    boundary = f"kbnpy{uuid.uuid4().hex}"
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: text/plain\r\n"
            "\r\n"
        ).encode()
        + file
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return body, f"multipart/form-data; boundary={boundary}"


class _LenientNdjsonSerializer(NdjsonSerializer):
    """NDJSON serializer that tolerates plain-text lines.

    Kibana labels the list items export response ``application/ndjson``
    although its body is a plain newline-separated dump of the raw item
    values (e.g. ``10.0.0.1``), which are usually not valid JSON. The strict
    NDJSON serializer would raise ``SerializationError`` on such lines; this
    subclass falls back to returning the raw line as a string instead, while
    parsing lines that are valid JSON exactly like the strict serializer.
    """

    mimetype = "application/ndjson"

    def loads(self, data: bytes) -> list[Any]:
        lines: list[Any] = []
        for raw_line in re.split(b"[\n\r]", data):
            if not raw_line:
                continue
            try:
                lines.append(self.json_loads(raw_line))
            except ValueError, TypeError:
                lines.append(raw_line.decode("utf-8", "surrogatepass"))
        return lines


class AsyncListsClient(AsyncNamespaceClient):
    """Async client for the Kibana Security Lists API.

    Value lists (``/api/lists``) hold values of a single Elasticsearch type
    (``ip``, ``keyword``, ``ip_range``, ...) that Security detection rule
    exceptions can reference, e.g. a list of malicious IP addresses. A value
    list is a container; the individual values live in list items
    (``/api/lists/items``), which can be managed one by one or imported from
    a newline-separated text file.

    Value lists are stored in per-space ``.lists-<space>`` and
    ``.items-<space>`` data streams that must exist before lists can be
    created; see :meth:`create_index` and :meth:`get_index_status`.

    All Lists APIs are space-scoped: every method accepts an optional
    ``space_id`` to target a specific space (``None`` targets the default
    space or the space the client is scoped to).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Make sure the value list data streams exist
        >>> status = await client.lists.get_index_status()
        >>>
        >>> # Create a list of bad IPs and add a value
        >>> created = await client.lists.create(
        ...     name="Bad ips", description="Known bad IPs", type="ip"
        ... )
        >>> list_id = created.body["id"]
        >>> await client.lists.create_item(list_id=list_id, value="192.0.2.1")
        >>>
        >>> # Export the values and clean up
        >>> exported = await client.lists.export_items(list_id=list_id)
        >>> await client.lists.delete(id=list_id)
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncListsClient.

        Args:
            client: The parent AsyncKibana client instance to delegate
                requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> lists_client = AsyncListsClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    def _enable_lenient_ndjson_parsing(self) -> None:
        """Swap in the lenient ``application/ndjson`` response serializer.

        The list items export endpoint responds with content type
        ``application/ndjson`` but a plain-text body of newline-separated
        values, which the strict NDJSON serializer cannot parse. This
        registers :class:`_LenientNdjsonSerializer` on this client's
        transport (idempotently); valid NDJSON payloads from other APIs are
        parsed exactly as before.
        """
        serializers = getattr(
            getattr(self._client, "_transport", None), "serializers", None
        )
        registry = getattr(serializers, "serializers", None)
        if isinstance(registry, dict) and not isinstance(
            registry.get("application/ndjson"), _LenientNdjsonSerializer
        ):
            registry["application/ndjson"] = _LenientNdjsonSerializer()

    # ----------------------------------------------------------------- lists

    async def create(
        self,
        *,
        name: str,
        description: str,
        type: str,
        id: str | None = None,
        meta: dict[str, Any] | None = None,
        version: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a value list.

        ``POST /api/lists``

        Creates a new value list container. The value list data streams must
        exist first (see :meth:`create_index`); otherwise Kibana responds
        with a 400 error.

        Args:
            name: Value list's name.
            description: Describes the value list.
            type: The Elasticsearch data type of the values the list holds,
                e.g. ``"ip"``, ``"ip_range"``, ``"keyword"``, ``"text"``,
                ``"date"``, ``"integer"``, ``"long"``, ``"double"``, and the
                other types accepted by the API.
            id: Optional identifier for the list (server-generated when
                omitted).
            meta: Placeholder for metadata about the value list.
            version: The document version number (defaults to 1).
            space_id: Optional space ID to create the list in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created list (``id``, ``name``,
            ``description``, ``type``, ``version``, ``_version``,
            ``created_at``/``created_by``, ``updated_at``/``updated_by``,
            ``tie_breaker_id``, ``immutable``).

        Raises:
            BadRequestError: If the payload is invalid or the value list data
                streams do not exist yet.
            ConflictError: If a list with the same ``id`` already exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = await client.lists.create(
            ...     name="Bad ips",
            ...     description="Known bad IPs",
            ...     type="ip",
            ...     id="bad-ips",
            ... )
            >>> print(created.body["id"])
            bad-ips
        """
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "type": type,
        }
        if id is not None:
            body["id"] = id
        if meta is not None:
            body["meta"] = meta
        if version is not None:
            body["version"] = version

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get value list details.

        ``GET /api/lists``

        Gets the details of a value list using the list ID.

        Args:
            id: Value list's identifier.
            space_id: Optional space ID to read the list from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the value list.

        Raises:
            NotFoundError: If the list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> fetched = await client.lists.get(id="bad-ips")
            >>> print(fetched.body["type"])
            ip
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
            params={"id": id},
        )

    async def update(
        self,
        *,
        id: str,
        name: str,
        description: str,
        _version: str | None = None,
        meta: dict[str, Any] | None = None,
        version: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a value list.

        ``PUT /api/lists``

        Updates a value list using the list ``id``. The original list is
        replaced, and all unspecified fields are deleted. You cannot modify
        the ``id`` value.

        Args:
            id: Value list's identifier.
            name: Value list's name.
            description: Describes the value list.
            _version: The version id returned when the list was retrieved.
                Use it to ensure updates are done against the latest version.
            meta: Placeholder for metadata about the value list.
            version: The document version number.
            space_id: Optional space ID to update the list in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated value list.

        Raises:
            NotFoundError: If the list does not exist.
            BadRequestError: If the payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.lists.update(
            ...     id="bad-ips",
            ...     name="Bad ips - updated",
            ...     description="Latest list of bad IPs",
            ... )
            >>> print(updated.body["name"])
            Bad ips - updated
        """
        body: dict[str, Any] = {
            "id": id,
            "name": name,
            "description": description,
        }
        if _version is not None:
            body["_version"] = _version
        if meta is not None:
            body["meta"] = meta
        if version is not None:
            body["version"] = version

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def patch(
        self,
        *,
        id: str,
        name: str | None = None,
        description: str | None = None,
        meta: dict[str, Any] | None = None,
        _version: str | None = None,
        version: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Patch a value list.

        ``PATCH /api/lists``

        Updates specific fields of an existing list using the list ``id``;
        unspecified fields keep their current values.

        Args:
            id: Value list's identifier.
            name: New value list's name.
            description: New description for the value list.
            meta: Placeholder for metadata about the value list.
            _version: The version id returned when the list was retrieved.
                Use it to ensure updates are done against the latest version.
            version: The document version number.
            space_id: Optional space ID to patch the list in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the patched value list.

        Raises:
            NotFoundError: If the list does not exist.
            BadRequestError: If the payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> patched = await client.lists.patch(id="bad-ips", name="New name")
            >>> print(patched.body["name"])
            New name
        """
        body: dict[str, Any] = {"id": id}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if meta is not None:
            body["meta"] = meta
        if _version is not None:
            body["_version"] = _version
        if version is not None:
            body["version"] = version

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists", space_id)
        return await self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete(
        self,
        *,
        id: str,
        delete_references: bool | None = None,
        ignore_references: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a value list.

        ``DELETE /api/lists``

        Deletes a value list using the list ID. When you delete a list, all
        of its list items are also deleted.

        Args:
            id: Value list's identifier.
            delete_references: Determines whether exception items referencing
                this value list should be deleted (default: false).
            ignore_references: Determines whether to delete the value list
                without performing any additional checks of where this list
                may be utilized (default: false).
            space_id: Optional space ID to delete the list from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the deleted value list.

        Raises:
            NotFoundError: If the list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> deleted = await client.lists.delete(id="bad-ips")
            >>> print(deleted.body["id"])
            bad-ips
        """
        params: dict[str, Any] = {"id": id}
        if delete_references is not None:
            params["deleteReferences"] = delete_references
        if ignore_references is not None:
            params["ignoreReferences"] = ignore_references

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists", space_id)
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
            params=params,
        )

    async def find(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        cursor: str | None = None,
        filter: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get value lists.

        ``GET /api/lists/_find``

        Gets a paginated subset of value lists. By default, the first page is
        returned, with 20 results per page.

        Args:
            page: The page number to return.
            per_page: The number of value lists to return per page.
            sort_field: Determines which field is used to sort the results.
            sort_order: Determines the sort order (``"asc"`` or ``"desc"``).
            cursor: Returns the lists that come after the last list returned
                in the previous call (use the ``cursor`` value returned in
                the previous response).
            filter: Filters the returned results according to the value of
                the specified field, using the ``<field>:<value>`` syntax.
            space_id: Optional space ID to search in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``data`` (array of lists), ``page``,
            ``per_page``, ``total`` and ``cursor``.

        Raises:
            BadRequestError: If the query parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.lists.find(filter="type:ip", per_page=50)
            >>> print(found.body["total"])
            1
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order
        if cursor is not None:
            params["cursor"] = cursor
        if filter is not None:
            params["filter"] = filter

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/_find", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
            params=params if params else None,
        )

    # ----------------------------------------------------------------- index

    async def create_index(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create value list data streams.

        ``POST /api/lists/index``

        Creates the ``.lists-<space>`` and ``.items-<space>`` data streams
        that store value lists and their items in the target space. On
        Kibana 9.4.3 this call is idempotent and responds with
        ``{"acknowledged": true}`` even when the data streams already exist.

        Args:
            space_id: Optional space ID to create the data streams in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``{"acknowledged": true}``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.lists.create_index()
            >>> print(result.body["acknowledged"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/index", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def get_index_status(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the status of value list data streams.

        ``GET /api/lists/index``

        Verifies that the ``.lists-<space>`` and ``.items-<space>`` data
        streams exist in the target space.

        Args:
            space_id: Optional space ID to check.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``list_index`` and ``list_item_index``
            booleans.

        Raises:
            NotFoundError: If the value list data streams do not exist (the
                error message names the missing data streams).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> status = await client.lists.get_index_status()
            >>> print(status.body["list_index"], status.body["list_item_index"])
            True True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/index", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def delete_index(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete value list data streams.

        ``DELETE /api/lists/index``

        Deletes the ``.lists-<space>`` and ``.items-<space>`` data streams
        of the target space **and all value lists and list items stored in
        them**. Use with extreme caution: any detection rule exceptions that
        reference value lists in this space stop matching.

        Args:
            space_id: Optional space ID whose data streams should be deleted.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``{"acknowledged": true}``.

        Raises:
            NotFoundError: If the value list data streams do not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.lists.delete_index(space_id="sandbox")
            >>> print(result.body["acknowledged"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/index", space_id)
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- items

    async def create_item(
        self,
        *,
        list_id: str,
        value: str,
        id: str | None = None,
        meta: dict[str, Any] | None = None,
        refresh: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a value list item.

        ``POST /api/lists/items``

        Creates a value list item and associates it with the specified value
        list. All list items in the same list must be the same type; e.g.
        each list item in an ``ip`` list must define a specific IP address.

        Args:
            list_id: Value list's identifier.
            value: The value used to evaluate exceptions.
            id: Optional identifier for the item (server-generated when
                omitted).
            meta: Placeholder for metadata about the value list item.
            refresh: Determines when changes made by the request are made
                visible to search: ``"true"``, ``"false"`` or ``"wait_for"``.
            space_id: Optional space ID to create the item in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created list item (``id``,
            ``list_id``, ``type``, ``value``, ``_version``, timestamps).

        Raises:
            NotFoundError: If the list does not exist.
            BadRequestError: If the value is invalid for the list's type.
            ConflictError: If an item with the same ``id`` already exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> item = await client.lists.create_item(
            ...     list_id="bad-ips", value="192.0.2.1", refresh="wait_for"
            ... )
            >>> print(item.body["value"])
            192.0.2.1
        """
        body: dict[str, Any] = {
            "list_id": list_id,
            "value": value,
        }
        if id is not None:
            body["id"] = id
        if meta is not None:
            body["meta"] = meta
        if refresh is not None:
            body["refresh"] = refresh

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/items", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_item(
        self,
        *,
        id: str | None = None,
        list_id: str | None = None,
        value: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a value list item.

        ``GET /api/lists/items``

        Gets the details of a value list item, either by the item's ``id``
        or by the pair of its list's ``list_id`` and the item ``value``.

        Args:
            id: Value list item's identifier. Required if ``list_id`` and
                ``value`` are not specified.
            list_id: Value list's identifier. Required if ``id`` is not
                specified.
            value: The item value to look up. Required if ``id`` is not
                specified.
            space_id: Optional space ID to read the item from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the list item when queried by
            ``id``, or an array of matching list items when queried by
            ``list_id`` and ``value``.

        Raises:
            ValueError: If neither ``id`` nor both ``list_id`` and ``value``
                are provided.
            NotFoundError: If the item does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> items = await client.lists.get_item(
            ...     list_id="bad-ips", value="192.0.2.1"
            ... )
            >>> print(items.body[0]["value"])
            192.0.2.1
        """
        if id is None and (list_id is None or value is None):
            raise ValueError("Provide either 'id' or both 'list_id' and 'value'")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if list_id is not None:
            params["list_id"] = list_id
        if value is not None:
            params["value"] = value

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/items", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
            params=params,
        )

    async def update_item(
        self,
        *,
        id: str,
        value: str,
        _version: str | None = None,
        meta: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a value list item.

        ``PUT /api/lists/items``

        Updates a value list item using the list item ID. The original item
        is replaced, and all unspecified fields are deleted. You cannot
        modify the ``id`` value.

        Args:
            id: Value list item's identifier.
            value: The new value used to evaluate exceptions.
            _version: The version id returned when the item was retrieved.
                Use it to ensure updates are done against the latest version.
            meta: Placeholder for metadata about the value list item.
            space_id: Optional space ID to update the item in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated list item.

        Raises:
            NotFoundError: If the item does not exist.
            BadRequestError: If the payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.lists.update_item(
            ...     id="item-id", value="192.0.2.2"
            ... )
            >>> print(updated.body["value"])
            192.0.2.2
        """
        body: dict[str, Any] = {
            "id": id,
            "value": value,
        }
        if _version is not None:
            body["_version"] = _version
        if meta is not None:
            body["meta"] = meta

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/items", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def patch_item(
        self,
        *,
        id: str,
        value: str | None = None,
        meta: dict[str, Any] | None = None,
        _version: str | None = None,
        refresh: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Patch a value list item.

        ``PATCH /api/lists/items``

        Updates specific fields of an existing value list item using the
        item ``id``; unspecified fields keep their current values.

        Args:
            id: Value list item's identifier.
            value: The new value used to evaluate exceptions.
            meta: Placeholder for metadata about the value list item.
            _version: The version id returned when the item was retrieved.
                Use it to ensure updates are done against the latest version.
            refresh: Determines when changes made by the request are made
                visible to search: ``"true"``, ``"false"`` or ``"wait_for"``.
            space_id: Optional space ID to patch the item in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the patched list item.

        Raises:
            NotFoundError: If the item does not exist.
            BadRequestError: If the payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> patched = await client.lists.patch_item(
            ...     id="item-id", value="192.0.2.3"
            ... )
            >>> print(patched.body["value"])
            192.0.2.3
        """
        body: dict[str, Any] = {"id": id}
        if value is not None:
            body["value"] = value
        if meta is not None:
            body["meta"] = meta
        if _version is not None:
            body["_version"] = _version
        if refresh is not None:
            body["refresh"] = refresh

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/items", space_id)
        return await self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_item(
        self,
        *,
        id: str | None = None,
        list_id: str | None = None,
        value: str | None = None,
        refresh: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a value list item.

        ``DELETE /api/lists/items``

        Deletes a value list item, either by the item's ``id`` or by the
        pair of its list's ``list_id`` and the item ``value``.

        Args:
            id: Value list item's identifier. Required if ``list_id`` and
                ``value`` are not specified.
            list_id: Value list's identifier. Required if ``id`` is not
                specified.
            value: The item value to delete. Required if ``id`` is not
                specified.
            refresh: Determines when changes made by the request are made
                visible to search: ``"true"``, ``"false"`` or ``"wait_for"``
                (default: ``"false"``).
            space_id: Optional space ID to delete the item from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the deleted list item when queried
            by ``id``, or an array of deleted list items when queried by
            ``list_id`` and ``value``.

        Raises:
            ValueError: If neither ``id`` nor both ``list_id`` and ``value``
                are provided.
            NotFoundError: If the item does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> deleted = await client.lists.delete_item(
            ...     list_id="bad-ips", value="192.0.2.1"
            ... )
        """
        if id is None and (list_id is None or value is None):
            raise ValueError("Provide either 'id' or both 'list_id' and 'value'")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if list_id is not None:
            params["list_id"] = list_id
        if value is not None:
            params["value"] = value
        if refresh is not None:
            params["refresh"] = refresh

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/items", space_id)
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
            params=params,
        )

    async def find_items(
        self,
        *,
        list_id: str,
        page: int | None = None,
        per_page: int | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        cursor: str | None = None,
        filter: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get value list items.

        ``GET /api/lists/items/_find``

        Gets a paginated subset of the value list items of a list. By
        default, the first page is returned, with 20 results per page.

        Args:
            list_id: Value list's identifier.
            page: The page number to return.
            per_page: The number of list items to return per page.
            sort_field: Determines which field is used to sort the results.
            sort_order: Determines the sort order (``"asc"`` or ``"desc"``).
            cursor: Returns the items that come after the last item returned
                in the previous call (use the ``cursor`` value returned in
                the previous response).
            filter: Filters the returned results according to the value of
                the specified field, using the ``<field>:<value>`` syntax.
            space_id: Optional space ID to search in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``data`` (array of list items), ``page``,
            ``per_page``, ``total`` and ``cursor``.

        Raises:
            BadRequestError: If the query parameters are invalid.
            NotFoundError: If the list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.lists.find_items(list_id="bad-ips")
            >>> print(found.body["total"])
            2
        """
        params: dict[str, Any] = {"list_id": list_id}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order
        if cursor is not None:
            params["cursor"] = cursor
        if filter is not None:
            params["filter"] = filter

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/items/_find", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
            params=params,
        )

    async def export_items(
        self,
        *,
        list_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Export value list items.

        ``POST /api/lists/items/_export``

        Exports the values of all items of a value list as a newline-
        separated text file.

        Note: Kibana labels the response ``application/ndjson`` although the
        body is a plain newline-separated dump of the raw values (this
        matches the format :meth:`import_items` accepts). The parsed
        response body is a list with one entry per exported value; values
        that are not valid JSON tokens (e.g. IP addresses) are returned as
        strings, while values that parse as JSON scalars (e.g. numbers) are
        returned as their parsed Python type.

        Args:
            list_id: The ``id`` of the value list to export.
            space_id: Optional space ID to export from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            Response whose body is the list of exported item values
            (iterate over it, or join with newlines to rebuild the file).

        Raises:
            NotFoundError: If the list does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> exported = await client.lists.export_items(list_id="bad-ips")
            >>> for value in exported:
            ...     print(value)
            192.0.2.1
            192.0.2.2
        """
        self._enable_lenient_ndjson_parsing()

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/items/_export", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/ndjson"},
            params={"list_id": list_id},
        )

    async def import_items(
        self,
        *,
        file: bytes | str | list[str],
        list_id: str | None = None,
        type: str | None = None,
        refresh: str | None = None,
        filename: str = "import.txt",
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Import value list items.

        ``POST /api/lists/items/_import``

        Imports a list of item values from a newline-separated ``.txt`` or
        ``.csv`` file (uploaded as ``multipart/form-data``). Values are
        imported into an existing list when ``list_id`` is given; otherwise
        a new list is created with ``id`` and ``name`` taken from
        ``filename`` and the type given by ``type``.

        Args:
            file: The file content: raw ``bytes``/``str`` of newline-
                separated values, or a list of values which is encoded
                one-value-per-line automatically.
            list_id: The ``id`` of the list to import items into. Required
                when importing to an existing list.
            type: The type of the importing list (e.g. ``"ip"``,
                ``"keyword"``). Required when importing a new list, i.e.
                when ``list_id`` is not specified.
            refresh: Determines when changes made by the request are made
                visible to search: ``"true"``, ``"false"`` or ``"wait_for"``.
            filename: Filename advertised in the multipart upload. When
                creating a new list it becomes the list's ``id`` and
                ``name``.
            space_id: Optional space ID to import into.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the list the items were imported
            into (the existing list, or the newly created one).

        Raises:
            ValueError: If ``file`` is empty or missing.
            NotFoundError: If ``list_id`` does not exist.
            BadRequestError: If neither ``list_id`` nor ``type`` is given,
                or a value is invalid for the list's type.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.lists.import_items(
            ...     file=["192.0.2.1", "192.0.2.2"],
            ...     list_id="bad-ips",
            ...     refresh="wait_for",
            ... )
            >>> print(result.body["id"])
            bad-ips
        """
        if file is None or (isinstance(file, (str, bytes, list)) and not file):
            raise ValueError("Parameter 'file' is required")

        params: dict[str, Any] = {}
        if list_id is not None:
            params["list_id"] = list_id
        if type is not None:
            params["type"] = type
        if refresh is not None:
            params["refresh"] = refresh

        body, content_type = _build_multipart_body(
            _values_file_bytes(file), filename=filename
        )

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/items/_import", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json", "content-type": content_type},
            params=params if params else None,
            body=body,  # type: ignore[arg-type]
        )

    # ------------------------------------------------------------ privileges

    async def get_privileges(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get value list privileges.

        ``GET /api/lists/privileges``

        Returns the value list and list item privileges of the calling user,
        including cluster and index privileges for the underlying data
        streams.

        Args:
            space_id: Optional space ID to check privileges in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``lists``, ``listItems`` and
            ``is_authenticated``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> privileges = await client.lists.get_privileges()
            >>> print(privileges.body["is_authenticated"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/lists/privileges", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )
