"""Async Kibana Streams API client."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse, SerializationError, Serializer

from kibana._async.client.utils import AsyncNamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class _ZipContentSerializer(Serializer):
    """Passthrough serializer for ``application/zip`` payloads.

    The content pack export API responds with a ZIP archive; this
    serializer hands the raw bytes through so the transport can wrap them
    in a ``BinaryApiResponse``.
    """

    mimetype = "application/zip"

    def dumps(self, data: Any) -> bytes:
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        raise SerializationError(
            f"Cannot serialize {type(data).__name__} into a ZIP archive"
        )

    def loads(self, data: bytes) -> bytes:
        return data


def _ensure_zip_response_serializer(client: Any) -> None:
    """Register the ``application/zip`` serializer on the client transport.

    Best-effort and idempotent: if the transport (or a mock stand-in) does
    not expose a serializer collection, the request proceeds without
    registration.

    :param client: Parent (sync or async) Kibana client instance
    """
    try:
        serializers = client._transport.serializers.serializers
    except AttributeError:
        return
    if "application/zip" not in serializers:
        serializers["application/zip"] = _ZipContentSerializer()


def _build_content_pack_multipart(
    include: dict[str, Any],
    content: bytes,
    filename: str,
) -> tuple[bytes, str]:
    """Build a ``multipart/form-data`` body for the content pack import API.

    :param include: Included-objects filter, JSON-encoded into the
        ``include`` form field (e.g. ``{"objects": {"all": {}}}``)
    :param content: Content pack archive (ZIP) bytes for the ``content``
        form field
    :param filename: Filename advertised for the uploaded archive part
    :return: Tuple of (body bytes, content-type header value with boundary)
    """
    boundary = f"kbnpy{uuid.uuid4().hex}"
    parts: list[bytes] = [
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="include"\r\n'
            "\r\n"
        ).encode()
        + json.dumps(include).encode("utf-8")
        + b"\r\n",
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="content"; '
            f'filename="{filename}"\r\n'
            "Content-Type: application/zip\r\n"
            "\r\n"
        ).encode()
        + content
        + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class AsyncStreamsClient(AsyncNamespaceClient):
    """Async client for the Kibana Streams API.

    Streams provide a single-pane experience to manage log (and other)
    data in Elasticsearch: routing (wired streams), processing pipelines,
    field mappings, lifecycle, significant-events queries and linked
    attachments (dashboards, rules, SLOs).

    All Streams APIs are marked as **Technical Preview** in Kibana 9.4 and
    may change in future releases. Streams must be enabled first (see
    :meth:`enable`); once enabled, Kibana manages wired root streams (in
    9.4 these are ``logs.ecs`` and ``logs.otel``) from which child streams
    can be forked.

    Streams are space-scoped: every method accepts an optional ``space_id``
    to target a specific space (``None`` targets the default space or the
    space the client is scoped to).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Enable streams, then fork a child stream from the ECS root
        >>> await client.streams.enable()
        >>> await client.streams.fork(
        ...     name="logs.ecs",
        ...     stream_name="logs.ecs.myapp",
        ...     where={"field": "service.name", "eq": "myapp"},
        ... )
        >>> streams = await client.streams.get_all()
        >>> print([s["name"] for s in streams.body["streams"]])
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncStreamsClient.

        Args:
            client: The parent AsyncKibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> streams_client = AsyncStreamsClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    async def enable(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Enable streams.

        Technical preview in 9.4. Enables the wired streams framework:
        Kibana creates the root streams (``logs.ecs`` and ``logs.otel`` in
        9.4) and the Elasticsearch resources backing them. The call is
        idempotent — enabling an already-enabled deployment is a no-op.

        Args:
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged`` and ``result``
            (``"created"`` when newly enabled, ``"noop"`` when already
            enabled).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> resp = await client.streams.enable()
            >>> print(resp.body["acknowledged"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/streams/_enable", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def disable(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Disable streams.

        Technical preview in 9.4. Disables the wired streams framework and
        deletes the stream definitions. Use with care: wired child streams
        and their configuration are removed.

        Args:
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged`` and ``result``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.streams.disable()
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/streams/_disable", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def resync(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Resync streams.

        Technical preview in 9.4. Rebuilds the Elasticsearch assets (index
        templates, ingest pipelines, component templates) backing all
        streams from the stored stream definitions. Useful when the assets
        have drifted from the definitions.

        Args:
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged`` and ``result``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.streams.resync()
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/streams/_resync", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def get_all(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the stream list.

        Technical preview in 9.4. Fetches the list of all streams (wired,
        classic and query streams) with their effective configuration.

        Args:
            space_id: Optional space ID to list streams from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with a ``streams`` list; every entry contains
            ``name``, ``type`` (``wired``/``classic``/``query``),
            ``description`` and the type-specific configuration.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> streams = await client.streams.get_all()
            >>> print([s["name"] for s in streams.body["streams"]])
            ['logs.ecs', 'logs.otel']
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/streams", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get(
        self,
        *,
        name: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a stream.

        Technical preview in 9.4. Fetches a stream definition and its
        related objects (dashboards, rules, queries) plus the caller's
        effective privileges on the stream.

        Args:
            name: The stream name (e.g. ``"logs.ecs"``).
            space_id: Optional space ID to get the stream from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``stream`` (definition), ``dashboards``,
            ``rules``, ``queries``, ``privileges`` and, for wired streams,
            ``inherited_fields`` and ``effective_*`` settings.

        Raises:
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> stream = await client.streams.get(name="logs.ecs")
            >>> print(stream.body["stream"]["type"])
            wired
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/streams/{_quote(name)}", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def upsert(
        self,
        *,
        name: str,
        stream: dict[str, Any],
        dashboards: list[str] | None = None,
        queries: list[dict[str, Any]] | None = None,
        rules: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create or update a stream.

        Technical preview in 9.4. Upserts the full stream definition
        together with its linked dashboards, rules and queries. The
        ``stream`` object must carry a ``type`` discriminator: ``"wired"``
        (with an ``ingest`` object containing a ``wired`` section),
        ``"classic"`` (``ingest`` with a ``classic`` section) or
        ``"query"`` (with a ``query`` object containing ``view`` and
        ``esql``).

        Args:
            name: The stream name (e.g. ``"logs.ecs.myapp"``).
            stream: The stream definition, e.g.
                ``{"type": "wired", "description": "...", "ingest": {
                "lifecycle": {"inherit": {}}, "processing": {"steps": []},
                "settings": {}, "failure_store": {"inherit": {}},
                "wired": {"fields": {}, "routing": []}}}``.
            dashboards: Dashboard IDs to link to the stream (defaults to an
                empty list; the API requires the field).
            queries: Significant-events queries to store on the stream; each
                item needs ``id``, ``title``, ``description`` and
                ``esql: {"query": ...}`` (defaults to an empty list).
            rules: Rule IDs to link to the stream (defaults to an empty
                list).
            space_id: Optional space ID to upsert the stream in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged`` and ``result``
            (``"created"`` or ``"updated"``).

        Raises:
            BadRequestError: If the definition fails validation.
            NotFoundError: If a parent stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.streams.upsert(
            ...     name="logs.ecs.myapp",
            ...     stream={
            ...         "type": "wired",
            ...         "description": "My app logs",
            ...         "ingest": {
            ...             "lifecycle": {"inherit": {}},
            ...             "processing": {"steps": []},
            ...             "settings": {},
            ...             "failure_store": {"inherit": {}},
            ...             "wired": {"fields": {}, "routing": []},
            ...         },
            ...     },
            ... )
        """
        body: dict[str, Any] = {
            "stream": stream,
            "dashboards": dashboards if dashboards is not None else [],
            "queries": queries if queries is not None else [],
            "rules": rules if rules is not None else [],
        }
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/streams/{_quote(name)}", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete(
        self,
        *,
        name: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a stream.

        Technical preview in 9.4. Deletes a stream definition and, for
        wired streams, the routing rule pointing at it from the parent
        stream. Root streams cannot be deleted.

        Args:
            name: The stream name (e.g. ``"logs.ecs.myapp"``).
            space_id: Optional space ID to delete the stream from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged`` and ``result``
            (``"deleted"``).

        Raises:
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.streams.delete(name="logs.ecs.myapp")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/streams/{_quote(name)}", space_id)
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    async def fork(
        self,
        *,
        name: str,
        stream_name: str,
        where: dict[str, Any],
        status: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Fork a stream.

        Technical preview in 9.4. Forks a wired stream: creates a child
        stream and adds a routing rule to the parent so that documents
        matching the ``where`` condition are routed to the child.

        Args:
            name: The parent stream name (e.g. ``"logs.ecs"``).
            stream_name: The name of the child stream to create; it must be
                prefixed by the parent name (e.g. ``"logs.ecs.myapp"``).
            where: Routing condition, e.g. ``{"field": "service.name",
                "eq": "myapp"}``. Conditions can be combined with ``and`` /
                ``or`` / ``not`` and the special ``{"always": {}}`` /
                ``{"never": {}}`` values.
            status: Optional routing rule status: ``"enabled"`` or
                ``"disabled"``.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged`` and ``result``
            (``"created"``).

        Raises:
            BadRequestError: If the condition or child name is invalid.
            NotFoundError: If the parent stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.streams.fork(
            ...     name="logs.ecs",
            ...     stream_name="logs.ecs.myapp",
            ...     where={"field": "service.name", "eq": "myapp"},
            ... )
        """
        body: dict[str, Any] = {
            "stream": {"name": stream_name},
            "where": where,
        }
        if status is not None:
            body["status"] = status
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/streams/{_quote(name)}/_fork", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_ingest(
        self,
        *,
        name: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get ingest stream settings.

        Technical preview in 9.4. Fetches only the ingest configuration of
        a stream: lifecycle, processing steps, index settings, failure
        store and the ``wired``/``classic`` specific section.

        Args:
            name: The stream name.
            space_id: Optional space ID to read from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``ingest`` object.

        Raises:
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> ingest = await client.streams.get_ingest(name="logs.ecs")
            >>> print(ingest.body["ingest"]["lifecycle"])
            {'dsl': {}}
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/streams/{_quote(name)}/_ingest", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_ingest(
        self,
        *,
        name: str,
        ingest: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update ingest stream settings.

        Technical preview in 9.4. Replaces the ingest configuration of a
        stream (lifecycle, processing steps, index settings, failure store
        and field mappings/routing for wired streams).

        Args:
            name: The stream name.
            ingest: The full ingest object, e.g. ``{"lifecycle":
                {"inherit": {}}, "processing": {"steps": []}, "settings":
                {}, "failure_store": {"inherit": {}}, "wired": {"fields":
                {...}, "routing": []}}``. Classic streams use a
                ``"classic"`` section instead of ``"wired"``. Note: when
                replaying a document returned by :meth:`get_ingest`, strip
                the read-only ``processing.updated_at`` field first —
                Kibana 9.4.3 rejects it on write.
            space_id: Optional space ID to update in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged`` and ``result``.

        Raises:
            BadRequestError: If the ingest object fails validation.
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> ingest = await client.streams.get_ingest(name="logs.ecs.myapp")
            >>> body = ingest.body["ingest"]
            >>> body["wired"]["fields"]["attributes.env"] = {"type": "keyword"}
            >>> await client.streams.update_ingest(name="logs.ecs.myapp", ingest=body)
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/streams/{_quote(name)}/_ingest", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body={"ingest": ingest},
        )

    async def get_query_settings(
        self,
        *,
        name: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get query stream settings.

        Technical preview, added in 9.4. Fetches the query configuration
        (the ES|QL query and optional field descriptions) of a query
        stream. Fails with a 400 error when the target is not a query
        stream.

        Args:
            name: The query stream name.
            space_id: Optional space ID to read from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the query stream settings.

        Raises:
            BadRequestError: If the stream is not a query stream.
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> settings = await client.streams.get_query_settings(
            ...     name="myquerystream"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/streams/{_quote(name)}/_query", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_query_settings(
        self,
        *,
        name: str,
        esql: str,
        field_descriptions: dict[str, str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Upsert query stream settings.

        Technical preview, added in 9.4. Creates or updates a query stream
        — a stream backed by an ES|QL query instead of ingested data.

        Args:
            name: The query stream name.
            esql: The ES|QL query backing the stream, e.g.
                ``"FROM logs.ecs, logs.ecs.* METADATA _id, _source | LIMIT 10"``.
            field_descriptions: Optional mapping of field name to
                human-readable description.
            space_id: Optional space ID to upsert in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged`` and ``result``
            (``"created"`` or ``"updated"``).

        Raises:
            BadRequestError: If the query fails validation.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.streams.update_query_settings(
            ...     name="myquerystream",
            ...     esql="FROM logs.ecs, logs.ecs.* METADATA _id, _source",
            ... )
        """
        body: dict[str, Any] = {"query": {"esql": esql}}
        if field_descriptions is not None:
            body["field_descriptions"] = field_descriptions
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/streams/{_quote(name)}/_query", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_queries(
        self,
        *,
        name: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get stream queries.

        Technical preview in 9.4. Fetches the significant-events queries
        linked to a stream.

        Args:
            name: The stream name.
            space_id: Optional space ID to read from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with a ``queries`` list; each entry has
            ``id``, ``title``, ``description``, ``esql`` and optional
            ``severity_score`` / ``evidence``.

        Raises:
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> queries = await client.streams.get_queries(name="logs.ecs")
            >>> print(len(queries.body["queries"]))
            0
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/streams/{_quote(name)}/queries", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def bulk_queries(
        self,
        *,
        name: str,
        operations: list[dict[str, Any]],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk update queries of a stream.

        Technical preview in 9.4. Executes multiple query upsert/delete
        operations on a stream in a single request.

        Args:
            name: The stream name.
            operations: List of operations. Each item is either
                ``{"index": {"id": ..., "title": ..., "description": ...,
                "esql": {"query": ...}}}`` to upsert a query or
                ``{"delete": {"id": ...}}`` to remove one.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged``.

        Raises:
            BadRequestError: If an operation fails validation.
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.streams.bulk_queries(
            ...     name="logs.ecs.myapp",
            ...     operations=[{"delete": {"id": "old-query"}}],
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/streams/{_quote(name)}/queries/_bulk", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"operations": operations},
        )

    async def upsert_query(
        self,
        *,
        name: str,
        query_id: str,
        title: str,
        esql: str,
        description: str | None = None,
        severity_score: float | None = None,
        evidence: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Upsert a query to a stream.

        Technical preview in 9.4. Creates or updates a significant-events
        query on a stream. Kibana validates the ES|QL shape: the query must
        read ``FROM <stream>, <stream>.*`` and include
        ``METADATA _id, _source``.

        Args:
            name: The stream name.
            query_id: The identifier of the query to upsert.
            title: Query title.
            esql: The ES|QL query string, e.g. ``"FROM logs.ecs.myapp,
                logs.ecs.myapp.* METADATA _id, _source | WHERE message
                LIKE \\"*error*\\""``.
            description: Optional query description.
            severity_score: Optional severity score for matching events.
            evidence: Optional list of evidence strings explaining why the
                query is significant.
            space_id: Optional space ID to upsert in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged``.

        Raises:
            BadRequestError: If the ES|QL query fails validation.
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.streams.upsert_query(
            ...     name="logs.ecs.myapp",
            ...     query_id="errors",
            ...     title="Error spike",
            ...     esql=(
            ...         "FROM logs.ecs.myapp, logs.ecs.myapp.* "
            ...         'METADATA _id, _source | WHERE message LIKE "*error*"'
            ...     ),
            ... )
        """
        body: dict[str, Any] = {
            "title": title,
            "esql": {"query": esql},
        }
        if description is not None:
            body["description"] = description
        if severity_score is not None:
            body["severity_score"] = severity_score
        if evidence is not None:
            body["evidence"] = evidence
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/streams/{_quote(name)}/queries/{_quote(query_id)}", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_query(
        self,
        *,
        name: str,
        query_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Remove a query from a stream.

        Technical preview in 9.4. Deletes a significant-events query from a
        stream.

        Args:
            name: The stream name.
            query_id: The identifier of the query to remove.
            space_id: Optional space ID to delete from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged``.

        Raises:
            NotFoundError: If the stream or query does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.streams.delete_query(
            ...     name="logs.ecs.myapp", query_id="errors"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/streams/{_quote(name)}/queries/{_quote(query_id)}", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    async def get_significant_events(
        self,
        *,
        name: str,
        from_: str,
        to: str,
        bucket_size: str,
        query: str | None = None,
        search_mode: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Read the significant events of a stream.

        Technical preview in 9.4. Evaluates the stream's
        significant-events queries over a time range and returns the
        occurrences bucketed by ``bucket_size`` together with change-point
        detection results.

        Args:
            name: The stream name.
            from_: Start of the time range (ISO 8601 date string, sent as
                the ``from`` query parameter).
            to: End of the time range (ISO 8601 date string).
            bucket_size: Bucket size for occurrence aggregation (e.g.
                ``"1h"``).
            query: Optional text to filter/search the queries with.
            search_mode: Optional search mode: ``"keyword"``,
                ``"semantic"`` or ``"hybrid"``.
            space_id: Optional space ID to read from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``significant_events`` (per-query
            occurrences and change points) and ``aggregated_occurrences``.

        Raises:
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> events = await client.streams.get_significant_events(
            ...     name="logs.ecs.myapp",
            ...     from_="2026-07-01T00:00:00.000Z",
            ...     to="2026-07-02T00:00:00.000Z",
            ...     bucket_size="1h",
            ... )
        """
        params: dict[str, Any] = {
            "from": from_,
            "to": to,
            "bucketSize": bucket_size,
        }
        if query is not None:
            params["query"] = query
        if search_mode is not None:
            params["searchMode"] = search_mode
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/streams/{_quote(name)}/significant_events", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def generate_significant_events(
        self,
        *,
        name: str,
        from_: str,
        to: str,
        connector_id: str | None = None,
        sample_docs_size: float | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Generate significant-events queries for a stream.

        Technical preview, added in 9.2. Uses an AI connector to analyze
        sample documents from the stream and generate candidate
        significant-events queries. Requires an AI connector: pass
        ``connector_id`` or configure a default AI connector in Kibana,
        otherwise the API responds with a 400 error.

        Args:
            name: The stream name.
            from_: Start of the sampling time range (ISO 8601 date string,
                sent as the ``from`` query parameter).
            to: End of the sampling time range (ISO 8601 date string).
            connector_id: Optional AI connector ID to use for generation.
            sample_docs_size: Optional number of sample documents to feed
                to the model.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the generated queries.

        Raises:
            BadRequestError: If no connector ID is provided and no default
                AI connector is configured.
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> generated = await client.streams.generate_significant_events(
            ...     name="logs.ecs.myapp",
            ...     from_="2026-07-01T00:00:00.000Z",
            ...     to="2026-07-02T00:00:00.000Z",
            ...     connector_id="my-ai-connector",
            ... )
        """
        params: dict[str, Any] = {
            "from": from_,
            "to": to,
        }
        if connector_id is not None:
            params["connectorId"] = connector_id
        if sample_docs_size is not None:
            params["sampleDocsSize"] = sample_docs_size
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/streams/{_quote(name)}/significant_events/_generate", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def preview_significant_events(
        self,
        *,
        name: str,
        from_: str,
        to: str,
        bucket_size: str,
        esql: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Preview significant events for an ad-hoc query.

        Technical preview in 9.4. Evaluates a candidate significant-events
        ES|QL query against a stream without saving it, returning bucketed
        occurrences and change-point analysis.

        Args:
            name: The stream name.
            from_: Start of the time range (ISO 8601 date string, sent as
                the ``from`` query parameter).
            to: End of the time range (ISO 8601 date string).
            bucket_size: Bucket size for occurrence aggregation (e.g.
                ``"1h"``).
            esql: The ES|QL query to preview; the same shape rules apply as
                for :meth:`upsert_query`.
            space_id: Optional space ID to run the preview in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``occurrences`` and ``change_points``
            for the previewed query.

        Raises:
            BadRequestError: If the ES|QL query fails validation.
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> preview = await client.streams.preview_significant_events(
            ...     name="logs.ecs.myapp",
            ...     from_="2026-07-01T00:00:00.000Z",
            ...     to="2026-07-02T00:00:00.000Z",
            ...     bucket_size="1h",
            ...     esql=(
            ...         "FROM logs.ecs.myapp, logs.ecs.myapp.* "
            ...         "METADATA _id, _source"
            ...     ),
            ... )
        """
        params: dict[str, Any] = {
            "from": from_,
            "to": to,
            "bucketSize": bucket_size,
        }
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/streams/{_quote(name)}/significant_events/_preview", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            params=params,
            headers={"accept": "application/json"},
            body={"query": {"esql": {"query": esql}}},
        )

    async def export_content(
        self,
        *,
        name: str,
        content_name: str,
        description: str,
        version: str,
        include: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Export stream content as a content pack.

        Technical preview in 9.4. Exports the stream's objects (queries,
        routing/child streams, mappings) as a content pack ZIP archive.

        Args:
            name: The stream name to export from.
            content_name: Name of the content pack (body field ``name``).
            description: Description of the content pack.
            version: Semantic version of the content pack (e.g.
                ``"1.0.0"``).
            include: Included-objects filter. Defaults to
                ``{"objects": {"all": {}}}``. A selective filter looks like
                ``{"objects": {"queries": [{"id": ...}], "mappings": True,
                "routing": [...]}}``.
            space_id: Optional space ID to export from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            BinaryApiResponse whose ``body`` holds the ZIP archive bytes
            (served with ``content-type: application/zip``).

        Raises:
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> exported = await client.streams.export_content(
            ...     name="logs.ecs.myapp",
            ...     content_name="myapp-pack",
            ...     description="My app stream content",
            ...     version="1.0.0",
            ... )
            >>> with open("myapp-pack.zip", "wb") as f:
            ...     _ = f.write(exported.body)
        """
        body: dict[str, Any] = {
            "name": content_name,
            "description": description,
            "version": version,
            "include": include if include is not None else {"objects": {"all": {}}},
        }
        _ensure_zip_response_serializer(self._client)
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/streams/{_quote(name)}/content/export", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/zip"},
            body=body,
        )

    async def import_content(
        self,
        *,
        name: str,
        content: bytes,
        include: dict[str, Any] | None = None,
        filename: str = "content_pack.zip",
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Import content into a stream.

        Technical preview in 9.4. Imports a content pack ZIP archive
        (uploaded as ``multipart/form-data``) into a stream, creating or
        updating the included objects.

        Args:
            name: The stream name to import into.
            content: Content pack archive bytes (e.g. the body returned by
                :meth:`export_content`).
            include: Included-objects filter, JSON-encoded into the
                ``include`` form field. Defaults to
                ``{"objects": {"all": {}}}``.
            filename: Filename advertised in the multipart upload (default:
                ``"content_pack.zip"``).
            space_id: Optional space ID to import into.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged`` and a ``result`` object
            listing ``created`` and ``updated`` streams.

        Raises:
            BadRequestError: If the archive or filter is invalid.
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> exported = await client.streams.export_content(
            ...     name="logs.ecs.myapp",
            ...     content_name="myapp-pack",
            ...     description="My app stream content",
            ...     version="1.0.0",
            ... )
            >>> await client.streams.import_content(
            ...     name="logs.ecs.myapp", content=exported.body
            ... )
        """
        multipart_body, content_type = _build_content_pack_multipart(
            include if include is not None else {"objects": {"all": {}}},
            content,
            filename,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/streams/{_quote(name)}/content/import", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={
                "accept": "application/json",
                "content-type": content_type,
            },
            body=multipart_body,  # type: ignore[arg-type]
        )

    async def get_attachments(
        self,
        *,
        name: str,
        query: str | None = None,
        attachment_types: list[str] | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get stream attachments.

        Technical preview, added in 9.3. Fetches the attachments
        (dashboards, rules, SLOs) linked to a stream, optionally filtered
        by search text, attachment type or tags.

        Args:
            name: The stream name (path parameter ``streamName``).
            query: Optional text to filter attachments by title.
            attachment_types: Optional list of attachment types to include:
                ``"dashboard"``, ``"rule"`` and/or ``"slo"``.
            tags: Optional list of tags to filter by.
            space_id: Optional space ID to read from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an ``attachments`` list; each entry has
            ``id``, ``type``, ``title``, ``tags`` and timestamps.

        Raises:
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> attachments = await client.streams.get_attachments(
            ...     name="logs.ecs.myapp",
            ...     attachment_types=["dashboard"],
            ... )
        """
        params: dict[str, Any] = {}
        if query is not None:
            params["query"] = query
        if attachment_types is not None:
            params["attachmentTypes"] = attachment_types
        if tags is not None:
            params["tags"] = tags
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/streams/{_quote(name)}/attachments", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    async def bulk_attachments(
        self,
        *,
        name: str,
        operations: list[dict[str, Any]],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk update attachments of a stream.

        Technical preview, added in 9.3. Executes multiple attachment
        link/unlink operations on a stream in a single request.

        Args:
            name: The stream name (path parameter ``streamName``).
            operations: List of operations. Each item is either
                ``{"index": {"id": ..., "type": ...}}`` to link an
                attachment or ``{"delete": {"id": ..., "type": ...}}`` to
                unlink one; ``type`` is ``"dashboard"``, ``"rule"`` or
                ``"slo"``.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged``.

        Raises:
            BadRequestError: If an operation fails validation.
            NotFoundError: If the stream does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.streams.bulk_attachments(
            ...     name="logs.ecs.myapp",
            ...     operations=[
            ...         {"index": {"id": "my-dashboard", "type": "dashboard"}},
            ...     ],
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/streams/{_quote(name)}/attachments/_bulk", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"operations": operations},
        )

    async def link_attachment(
        self,
        *,
        name: str,
        attachment_type: str,
        attachment_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Link an attachment to a stream.

        Technical preview, added in 9.3. Links an existing dashboard, rule
        or SLO to a stream so it shows up in the stream's overview.

        Args:
            name: The stream name (path parameter ``streamName``).
            attachment_type: The attachment type: ``"dashboard"``,
                ``"rule"`` or ``"slo"``.
            attachment_id: The ID of the object to link.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged``.

        Raises:
            NotFoundError: If the stream or the object does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.streams.link_attachment(
            ...     name="logs.ecs.myapp",
            ...     attachment_type="dashboard",
            ...     attachment_id="my-dashboard",
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/streams/{_quote(name)}/attachments/"
            f"{_quote(attachment_type)}/{_quote(attachment_id)}",
            space_id,
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
        )

    async def unlink_attachment(
        self,
        *,
        name: str,
        attachment_type: str,
        attachment_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Unlink an attachment from a stream.

        Technical preview, added in 9.3. Unlinks a dashboard, rule or SLO
        from a stream. The underlying object is not deleted.

        Args:
            name: The stream name (path parameter ``streamName``).
            attachment_type: The attachment type: ``"dashboard"``,
                ``"rule"`` or ``"slo"``.
            attachment_id: The ID of the object to unlink.
            space_id: Optional space ID to run the operation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged``.

        Raises:
            NotFoundError: If the stream or the attachment does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.streams.unlink_attachment(
            ...     name="logs.ecs.myapp",
            ...     attachment_type="dashboard",
            ...     attachment_id="my-dashboard",
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/streams/{_quote(name)}/attachments/"
            f"{_quote(attachment_type)}/{_quote(attachment_id)}",
            space_id,
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )
