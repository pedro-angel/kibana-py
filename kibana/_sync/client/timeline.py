"""Kibana Security Timeline API client."""

import json
import uuid
from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


def _ndjson_bytes(file: bytes | str | list[dict[str, Any]]) -> bytes:
    """Normalize a Timeline import payload to NDJSON bytes.

    Accepts raw ``bytes``/``str`` (e.g. the body returned by the export API)
    or a list of timeline dicts, which are encoded one-JSON-per-line.

    :param file: NDJSON content as bytes/str, or a list of objects to encode
    :return: NDJSON-encoded bytes
    """
    if isinstance(file, bytes):
        return file
    if isinstance(file, str):
        return file.encode("utf-8")
    return ("\n".join(json.dumps(obj) for obj in file) + "\n").encode("utf-8")


def _build_import_body(
    file: bytes,
    *,
    is_immutable: str | None = None,
    filename: str = "timelines.ndjson",
) -> tuple[bytes, str]:
    """Build a ``multipart/form-data`` body for the Timeline import API.

    :param file: NDJSON file content for the ``file`` form field
    :param is_immutable: Optional ``"true"``/``"false"`` string for the
        ``isImmutable`` form field
    :param filename: Filename advertised for the uploaded file part
    :return: Tuple of (body bytes, content-type header value with boundary)
    """
    boundary = f"kbnpy{uuid.uuid4().hex}"
    parts: list[bytes] = []
    if is_immutable is not None:
        parts.append(
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="isImmutable"\r\n'
                "\r\n"
            ).encode()
            + is_immutable.encode("utf-8")
            + b"\r\n"
        )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/ndjson\r\n"
            "\r\n"
        ).encode()
        + file
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class TimelineClient(NamespaceClient):
    """Client for the Kibana Security Timeline API.

    Timelines are the Security Solution's workspace for investigating events
    and alerts. This client covers the full Security Timeline API surface:
    Timeline and Timeline-template CRUD, per-user draft Timelines, favorites,
    NDJSON export/import, prepackaged-Timeline installation, Timeline copies,
    investigation notes (``/api/note``) and pinned events
    (``/api/pinned_event``).

    All Timeline resources are space-scoped saved objects: a Timeline created
    in one space is not visible from another space. Every method accepts an
    optional ``space_id`` to target a specific space (``None`` targets the
    default space or the space the client is scoped to).

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a Timeline and attach a note to it
        >>> created = client.timeline.create(
        ...     timeline={"title": "Suspicious logons", "description": "..."}
        ... )
        >>> timeline_id = created.body["savedObjectId"]
        >>> client.timeline.create_note(
        ...     note={"timelineId": timeline_id, "note": "Check host-1 first"}
        ... )
        >>>
        >>> # Clean up
        >>> client.timeline.delete(saved_object_ids=[timeline_id])
    """

    def __init__(
        self,
        client: Kibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the TimelineClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> timeline_client = TimelineClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    # ------------------------------------------------------------------
    # Timelines (/api/timeline, /api/timelines)
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        timeline: dict[str, Any],
        status: str | None = None,
        template_timeline_id: str | None = None,
        template_timeline_version: int | None = None,
        timeline_id: str | None = None,
        timeline_type: str | None = None,
        version: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a Timeline or Timeline template.

        ``POST /api/timeline``. Creates a new saved Timeline or Timeline
        template from a ``SavedTimeline`` object (title, description,
        dateRange, columns, dataProviders, filters, ...).

        Args:
            timeline: The ``SavedTimeline`` object describing the Timeline
                (e.g. ``{"title": ..., "description": ..., "dateRange":
                {"start": ..., "end": ...}}``).
            status: Timeline status: ``"active"``, ``"draft"`` or
                ``"immutable"``.
            template_timeline_id: Unique identifier for the Timeline template
                (when creating a template).
            template_timeline_version: Timeline template version number.
            timeline_id: A unique identifier to assign to the Timeline.
            timeline_type: Type of Timeline: ``"default"`` or ``"template"``.
            version: Version of the Timeline.
            space_id: Optional space ID to create the Timeline in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created Timeline, including its
            ``savedObjectId`` and ``version``.

        Raises:
            ApiError: If there was an error creating the Timeline (the spec
                documents a 405 status for this case).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = client.timeline.create(
            ...     timeline={
            ...         "title": "My investigation",
            ...         "description": "Investigating a suspicious logon",
            ...     }
            ... )
            >>> print(created.body["savedObjectId"])
        """
        body: dict[str, Any] = {"timeline": timeline}
        if status is not None:
            body["status"] = status
        if template_timeline_id is not None:
            body["templateTimelineId"] = template_timeline_id
        if template_timeline_version is not None:
            body["templateTimelineVersion"] = template_timeline_version
        if timeline_id is not None:
            body["timelineId"] = timeline_id
        if timeline_type is not None:
            body["timelineType"] = timeline_type
        if version is not None:
            body["version"] = version

        path = self._build_space_path("/api/timeline", space_id, validate_spaces)
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get(
        self,
        *,
        id: str | None = None,
        template_timeline_id: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get Timeline or Timeline template details.

        ``GET /api/timeline``. Gets the details of an existing saved Timeline
        (by ``id``) or Timeline template (by ``template_timeline_id``).

        NOTE: the live Kibana 9.4.3 server returns HTTP 500 ("please provide
        id or template_timeline_id") when neither parameter is given, so this
        client requires at least one of them.

        Args:
            id: The ``savedObjectId`` of the Timeline to retrieve.
            template_timeline_id: The ID of the Timeline template to retrieve.
            space_id: Optional space ID to get the Timeline from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the Timeline, including its
            ``savedObjectId``, ``version`` and all ``SavedTimeline`` fields.

        Raises:
            ValueError: If neither ``id`` nor ``template_timeline_id`` is
                provided.
            NotFoundError: If the Timeline does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> timeline = client.timeline.get(id="15c1929b-...-56e234cc7c4e")
            >>> print(timeline.body["title"])
        """
        if id is None and template_timeline_id is None:
            raise ValueError("Either 'id' or 'template_timeline_id' must be provided")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if template_timeline_id is not None:
            params["template_timeline_id"] = template_timeline_id

        path = self._build_space_path("/api/timeline", space_id, validate_spaces)
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def get_all(
        self,
        *,
        only_user_favorite: bool | str | None = None,
        timeline_type: str | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        page_size: int | str | None = None,
        page_index: int | str | None = None,
        search: str | None = None,
        status: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get Timelines or Timeline templates.

        ``GET /api/timelines``. Gets a list of all saved Timelines or
        Timeline templates, with optional filtering, sorting and pagination.

        Args:
            only_user_favorite: If true, only Timelines marked as favorites
                by the current user are returned.
            timeline_type: Filter by type: ``"default"`` or ``"template"``.
            sort_field: Field to sort by: ``"title"``, ``"description"``,
                ``"updated"`` or ``"created"``.
            sort_order: Sort order: ``"asc"`` or ``"desc"``.
            page_size: How many results are returned per page.
            page_index: How many pages are skipped (1-based page number).
            search: Search for Timelines by their title.
            status: Filter by status: ``"active"``, ``"draft"`` or
                ``"immutable"``.
            space_id: Optional space ID to list Timelines from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``timeline`` (the list of Timelines)
            and ``totalCount``, plus favorite/template count summaries.

        Raises:
            BadRequestError: If invalid query parameters are supplied.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = client.timeline.get_all(
            ...     search="investigation", page_size=10, page_index=1
            ... )
            >>> print(found.body["totalCount"])
        """
        params: dict[str, Any] = {}
        if only_user_favorite is not None:
            params["only_user_favorite"] = only_user_favorite
        if timeline_type is not None:
            params["timeline_type"] = timeline_type
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order
        if page_size is not None:
            params["page_size"] = page_size
        if page_index is not None:
            params["page_index"] = page_index
        if search is not None:
            params["search"] = search
        if status is not None:
            params["status"] = status

        path = self._build_space_path("/api/timelines", space_id, validate_spaces)
        return self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    def update(
        self,
        *,
        timeline_id: str,
        version: str | None,
        timeline: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a Timeline.

        ``PATCH /api/timeline``. Updates an existing Timeline or Timeline
        template. You can update the title, description, date range, data
        providers and any other ``SavedTimeline`` field.

        Args:
            timeline_id: The ``savedObjectId`` of the Timeline or Timeline
                template being updated.
            version: The version of the Timeline being updated (from a
                previous read; may be None).
            timeline: The ``SavedTimeline`` object with the updated fields.
            space_id: Optional space ID the Timeline lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated Timeline with its new
            ``version``.

        Raises:
            NotFoundError: If the Timeline does not exist.
            ApiError: If the update is rejected (the spec documents a 405
                status for this case).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> current = client.timeline.get(id=timeline_id)
            >>> updated = client.timeline.update(
            ...     timeline_id=timeline_id,
            ...     version=current.body["version"],
            ...     timeline={"title": "Renamed investigation"},
            ... )
        """
        body: dict[str, Any] = {
            "timelineId": timeline_id,
            "version": version,
            "timeline": timeline,
        }

        path = self._build_space_path("/api/timeline", space_id, validate_spaces)
        return self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def delete(
        self,
        *,
        saved_object_ids: list[str],
        search_ids: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete Timelines or Timeline templates.

        ``DELETE /api/timeline``. Deletes one or more Timelines or Timeline
        templates by their saved object IDs (maximum 100 per call).

        Args:
            saved_object_ids: The list of ``savedObjectId`` values of the
                Timelines or Timeline templates to delete.
            search_ids: Saved search IDs that should be deleted alongside the
                Timelines.
            space_id: Optional space ID the Timelines live in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.timeline.delete(
            ...     saved_object_ids=["15c1929b-...-56e234cc7c4e"]
            ... )
        """
        body: dict[str, Any] = {"savedObjectIds": saved_object_ids}
        if search_ids is not None:
            body["searchIds"] = search_ids

        path = self._build_space_path("/api/timeline", space_id, validate_spaces)
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def resolve(
        self,
        *,
        id: str | None = None,
        template_timeline_id: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Resolve a saved Timeline or Timeline template.

        ``GET /api/timeline/resolve``. Like :meth:`get`, but uses the saved
        objects resolve semantics: the response wraps the Timeline in a
        ``timeline`` key together with an ``outcome`` (``exactMatch``,
        ``aliasMatch`` or ``conflict``) so callers can follow legacy-URL
        aliases after migrations.

        Args:
            id: The ID of the Timeline to resolve.
            template_timeline_id: The ID of the Timeline template to resolve.
            space_id: Optional space ID to resolve the Timeline in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the resolved ``timeline`` object and
            the resolve ``outcome``.

        Raises:
            ValueError: If neither ``id`` nor ``template_timeline_id`` is
                provided.
            BadRequestError: If the request is missing parameters.
            NotFoundError: If the Timeline was not found.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> resolved = client.timeline.resolve(id=timeline_id)
            >>> print(resolved.body["timeline"]["title"])
        """
        if id is None and template_timeline_id is None:
            raise ValueError("Either 'id' or 'template_timeline_id' must be provided")

        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id
        if template_timeline_id is not None:
            params["template_timeline_id"] = template_timeline_id

        path = self._build_space_path(
            "/api/timeline/resolve", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def copy(
        self,
        *,
        timeline_id_to_copy: str,
        timeline: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Copy a Timeline or Timeline template.

        ``POST /api/timeline/_copy``. Copies an existing Timeline or Timeline
        template (including its notes and pinned events) and returns the copy.

        NOTE: the 9.4.3 OpenAPI spec documents this operation as ``GET``, but
        the live server only registers ``POST`` and restricts the route to
        internal callers; this client sends the ``x-elastic-internal-origin``
        header the route requires.

        Args:
            timeline_id_to_copy: The ``savedObjectId`` of the Timeline to
                copy.
            timeline: The ``SavedTimeline`` object applied to the copy (e.g.
                a new ``title``).
            space_id: Optional space ID the Timeline lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the copied Timeline, including its
            new ``savedObjectId`` and ``version``.

        Raises:
            NotFoundError: If the source Timeline does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> copy = client.timeline.copy(
            ...     timeline_id_to_copy=timeline_id,
            ...     timeline={"title": "Copy of my investigation"},
            ... )
            >>> print(copy.body["savedObjectId"])
        """
        body: dict[str, Any] = {
            "timeline": timeline,
            "timelineIdToCopy": timeline_id_to_copy,
        }

        path = self._build_space_path("/api/timeline/_copy", space_id, validate_spaces)
        return self.perform_request(
            "POST",
            path,
            headers={
                "accept": "application/json",
                "x-elastic-internal-origin": "kibana-py",
            },
            body=body,
        )

    # ------------------------------------------------------------------
    # Draft Timelines (/api/timeline/_draft)
    # ------------------------------------------------------------------

    def get_draft(
        self,
        *,
        timeline_type: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the draft Timeline or Timeline template for the current user.

        ``GET /api/timeline/_draft``. Gets the details of the current user's
        draft Timeline (or Timeline template). If the user doesn't have a
        draft Timeline, an empty draft Timeline is created and returned.

        Args:
            timeline_type: The type of draft Timeline: ``"default"`` or
                ``"template"``.
            space_id: Optional space ID to get the draft Timeline from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the draft Timeline, including its
            ``savedObjectId`` and ``version``.

        Raises:
            AuthorizationException: If the user does not have the required
                permissions to create a draft Timeline.
            ConflictError: If a draft Timeline could not be created because
                one already exists with the given ``timelineId``.
            AuthenticationException: If authentication fails.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> draft = client.timeline.get_draft(timeline_type="default")
            >>> print(draft.body["status"])
            draft
        """
        path = self._build_space_path("/api/timeline/_draft", space_id, validate_spaces)
        return self.perform_request(
            "GET",
            path,
            params={"timelineType": timeline_type},
            headers={"accept": "application/json"},
        )

    def clean_draft(
        self,
        *,
        timeline_type: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a clean draft Timeline or Timeline template.

        ``POST /api/timeline/_draft``. Creates a clean draft Timeline (or
        Timeline template) for the current user. If the user already has a
        draft Timeline, the existing draft is cleared and returned.

        Args:
            timeline_type: The type of draft Timeline to create:
                ``"default"`` or ``"template"``.
            space_id: Optional space ID to create the draft Timeline in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the (cleared) draft Timeline,
            including its ``savedObjectId`` and ``version``.

        Raises:
            AuthorizationException: If the user does not have the required
                permissions to create a draft Timeline.
            ConflictError: If there is already a draft Timeline with the
                given ``timelineId``.
            AuthenticationException: If authentication fails.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> draft = client.timeline.clean_draft(timeline_type="default")
            >>> print(draft.body["savedObjectId"])
        """
        path = self._build_space_path("/api/timeline/_draft", space_id, validate_spaces)
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"timelineType": timeline_type},
        )

    # ------------------------------------------------------------------
    # Export / import / prepackaged (/api/timeline/_export, _import, ...)
    # ------------------------------------------------------------------

    def export(
        self,
        *,
        file_name: str,
        ids: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Export Timelines as an NDJSON file.

        ``POST /api/timeline/_export``. Exports the given Timelines as NDJSON
        (``application/ndjson``): one Timeline per line. The parsed response
        body is a list of Timeline dicts that can be passed straight to
        :meth:`import_timelines`.

        Args:
            file_name: The name of the file to export (query parameter used
                for the ``Content-Disposition`` of the download).
            ids: The ``savedObjectId`` values of the Timelines to export
                (1 to 1000 IDs).
            space_id: Optional space ID to export the Timelines from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is the parsed NDJSON list of
            exported Timelines.

        Raises:
            BadRequestError: If the export size limit was exceeded.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> exported = client.timeline.export(
            ...     file_name="timelines.ndjson", ids=[timeline_id]
            ... )
            >>> print(len(list(exported)))
            1
        """
        body: dict[str, Any] = {}
        if ids is not None:
            body["ids"] = ids

        path = self._build_space_path(
            "/api/timeline/_export", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            params={"file_name": file_name},
            body=body,
        )

    def import_timelines(
        self,
        *,
        file: bytes | str | list[dict[str, Any]],
        is_immutable: bool | str | None = None,
        filename: str = "timelines.ndjson",
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Import Timelines from an NDJSON export file.

        ``POST /api/timeline/_import``. Imports Timelines from an NDJSON file
        produced by :meth:`export`, uploaded as ``multipart/form-data`` (the
        content type the live server requires).

        Args:
            file: NDJSON export content: raw ``bytes``/``str``, or a list of
                Timeline dicts (e.g. the parsed body returned by
                :meth:`export`), which is NDJSON-encoded automatically.
            is_immutable: Whether the imported Timelines should be immutable
                (sent as the ``isImmutable`` form field; booleans are encoded
                as ``"true"``/``"false"``).
            filename: Filename advertised in the multipart upload; must have
                an ``.ndjson`` extension.
            space_id: Optional space ID to import the Timelines into.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the import result: ``success``,
            ``success_count``, ``timelines_installed``, ``timelines_updated``
            and an ``errors`` array.

        Raises:
            ValueError: If ``file`` is empty.
            BadRequestError: If the file extension is invalid.
            ConflictError: If the Timelines could not be imported.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> exported = client.timeline.export(
            ...     file_name="timelines.ndjson", ids=[timeline_id]
            ... )
            >>> result = client.timeline.import_timelines(file=list(exported))
            >>> print(result.body["success"])
        """
        if file is None or (isinstance(file, (str, bytes, list)) and not file):
            raise ValueError("Parameter 'file' is required")

        immutable_field: str | None
        if isinstance(is_immutable, bool):
            immutable_field = "true" if is_immutable else "false"
        else:
            immutable_field = is_immutable

        body, content_type = _build_import_body(
            _ndjson_bytes(file), is_immutable=immutable_field, filename=filename
        )

        path = self._build_space_path(
            "/api/timeline/_import", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"content-type": content_type},
            body=body,  # type: ignore[arg-type]
        )

    def install_prepackaged(
        self,
        *,
        timelines_to_install: list[dict[str, Any]] | None = None,
        timelines_to_update: list[dict[str, Any]] | None = None,
        prepackaged_timelines: list[dict[str, Any]] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Install or update prepackaged Timelines.

        ``POST /api/timeline/_prepackaged``. Installs or updates the Elastic
        prepackaged Timeline templates. When called with the default empty
        lists, the server computes which prepackaged Timelines are missing or
        outdated and installs/updates them.

        Args:
            timelines_to_install: Timelines to install (``ImportTimelines``
                objects). Defaults to an empty list.
            timelines_to_update: Timelines to update (``ImportTimelines``
                objects). Defaults to an empty list.
            prepackaged_timelines: The currently installed prepackaged
                Timelines (``TimelineSavedToReturnObject`` objects). Defaults
                to an empty list.
            space_id: Optional space ID to install the Timelines into.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the install result: ``success``,
            ``success_count``, ``timelines_installed``, ``timelines_updated``
            and an ``errors`` array.

        Raises:
            ApiError: If the installation was unsuccessful (500).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = client.timeline.install_prepackaged()
            >>> print(result.body["timelines_installed"])
        """
        body: dict[str, Any] = {
            "timelinesToInstall": (
                timelines_to_install if timelines_to_install is not None else []
            ),
            "timelinesToUpdate": (
                timelines_to_update if timelines_to_update is not None else []
            ),
            "prepackagedTimelines": (
                prepackaged_timelines if prepackaged_timelines is not None else []
            ),
        }

        path = self._build_space_path(
            "/api/timeline/_prepackaged", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Favorites (/api/timeline/_favorite)
    # ------------------------------------------------------------------

    def favorite(
        self,
        *,
        timeline_id: str | None,
        template_timeline_id: str | None = None,
        template_timeline_version: int | None = None,
        timeline_type: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Favorite (or unfavorite) a Timeline for the current user.

        ``PATCH /api/timeline/_favorite``. Toggles the favorite status of a
        Timeline or Timeline template for the current user: calling it once
        marks the Timeline as a favorite, calling it again removes the
        favorite mark. All four body fields are required by the API but may
        be null.

        Args:
            timeline_id: The ``savedObjectId`` of the Timeline (may be None
                when favoriting a template by its template ID).
            template_timeline_id: The Timeline template ID.
            template_timeline_version: The Timeline template version.
            timeline_type: The type of Timeline: ``"default"`` or
                ``"template"``.
            space_id: Optional space ID the Timeline lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the Timeline's ``savedObjectId``,
            new ``version`` and the ``favorite`` entries (empty after an
            unfavorite call).

        Raises:
            AuthorizationException: If the user does not have the required
                permissions to persist the favorite status.
            AuthenticationException: If authentication fails.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = client.timeline.favorite(
            ...     timeline_id=timeline_id, timeline_type="default"
            ... )
            >>> print(result.body["favorite"][0]["userName"])
        """
        body: dict[str, Any] = {
            "timelineId": timeline_id,
            "templateTimelineId": template_timeline_id,
            "templateTimelineVersion": template_timeline_version,
            "timelineType": timeline_type,
        }

        path = self._build_space_path(
            "/api/timeline/_favorite", space_id, validate_spaces
        )
        return self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Notes (/api/note)
    # ------------------------------------------------------------------

    def create_note(
        self,
        *,
        note: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Add a note to a Timeline.

        ``PATCH /api/note``. Creates a new note attached to a Timeline. To
        attach the note to a specific event or alert, set ``note["eventId"]``
        to that event's document ``_id``; omit ``eventId`` for a
        timeline-wide note. Requires the Timeline and Notes write privilege
        (``notes_write``).

        Args:
            note: The ``BareNote`` payload. Must include ``timelineId``; may
                include ``note`` (the text) and ``eventId``.
            space_id: Optional space ID the Timeline lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the persisted note under the
            ``note`` key, including its ``noteId`` and ``version``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = client.timeline.create_note(
            ...     note={"timelineId": timeline_id, "note": "Look at host-1"}
            ... )
            >>> print(created.body["note"]["noteId"])
        """
        path = self._build_space_path("/api/note", space_id, validate_spaces)
        return self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body={"note": note},
        )

    def update_note(
        self,
        *,
        note_id: str,
        note: dict[str, Any],
        version: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update an existing note.

        ``PATCH /api/note``. Updates an existing note by its saved object ID.
        Optionally pass ``version`` (from a previous read) for optimistic
        concurrency control. Requires the Timeline and Notes write privilege
        (``notes_write``).

        Args:
            note_id: The ``savedObjectId`` of the note to update.
            note: The ``BareNote`` payload with the changed fields. Must
                include ``timelineId``.
            version: Saved object version string from a previous read.
            space_id: Optional space ID the Timeline lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the persisted note under the
            ``note`` key, including its ``noteId`` and new ``version``.

        Raises:
            NotFoundError: If the note does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = client.timeline.update_note(
            ...     note_id=note_id,
            ...     note={"timelineId": timeline_id, "note": "Updated text"},
            ...     version=note_version,
            ... )
        """
        body: dict[str, Any] = {"note": note, "noteId": note_id}
        if version is not None:
            body["version"] = version

        path = self._build_space_path("/api/note", space_id, validate_spaces)
        return self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_notes(
        self,
        *,
        document_ids: str | list[str] | None = None,
        saved_object_ids: str | list[str] | None = None,
        page: int | str | None = None,
        per_page: int | str | None = None,
        search: str | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        filter: str | None = None,
        created_by_filter: str | None = None,
        associated_filter: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get notes.

        ``GET /api/note``. Returns Security Timeline notes. The server has
        three mutually exclusive query modes:

        1. ``document_ids`` set: returns notes whose ``eventId`` matches the
           given event document ``_id`` value(s); pagination is not applied.
        2. ``saved_object_ids`` set: returns notes linked to the given
           Timeline saved object ID(s); pagination is not applied.
        3. Neither set: lists notes with saved-objects find semantics using
           ``page``, ``per_page``, ``search``, ``sort_field``, ``sort_order``,
           ``filter``, ``created_by_filter`` and ``associated_filter``.

        Requires the Timeline and Notes read privilege (``notes_read``).

        Args:
            document_ids: Event document ``_id`` value(s) to match against
                each note's ``eventId``.
            saved_object_ids: Timeline ``savedObjectId`` value(s); returns
                notes that reference those Timelines.
            page: Page number for list mode (default 1).
            per_page: Page size for list mode (default 10).
            search: Search string (list mode only).
            sort_field: Field to sort by (list mode only).
            sort_order: Sort order, ``"asc"`` or ``"desc"`` (list mode only).
            filter: KQL filter string interpreted by the saved-objects layer
                (list mode only).
            created_by_filter: Kibana user profile UID; returns notes created
                by that user (list mode only).
            associated_filter: Restricts notes by how they relate to a
                Timeline and/or event: ``"all"``, ``"document_only"``,
                ``"saved_object_only"``, ``"document_and_saved_object"`` or
                ``"orphan"`` (list mode only).
            space_id: Optional space ID to get the notes from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``notes`` and ``totalCount``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> notes = client.timeline.get_notes(
            ...     saved_object_ids=timeline_id
            ... )
            >>> print(notes.body["totalCount"])
        """
        params: dict[str, Any] = {}
        if document_ids is not None:
            params["documentIds"] = document_ids
        if saved_object_ids is not None:
            params["savedObjectIds"] = saved_object_ids
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        if search is not None:
            params["search"] = search
        if sort_field is not None:
            params["sortField"] = sort_field
        if sort_order is not None:
            params["sortOrder"] = sort_order
        if filter is not None:
            params["filter"] = filter
        if created_by_filter is not None:
            params["createdByFilter"] = created_by_filter
        if associated_filter is not None:
            params["associatedFilter"] = associated_filter

        path = self._build_space_path("/api/note", space_id, validate_spaces)
        return self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    def delete_notes(
        self,
        *,
        note_id: str | None = None,
        note_ids: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete one or more notes.

        ``DELETE /api/note``. Deletes notes by saved object ID. Pass either
        ``note_id`` (single delete) or ``note_ids`` (bulk delete) — exactly
        one of the two. Requires the Timeline and Notes write privilege
        (``notes_write``).

        Args:
            note_id: Saved object ID of the single note to delete.
            note_ids: Saved object IDs of the notes to delete.
            space_id: Optional space ID the notes live in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            ValueError: If neither or both of ``note_id`` and ``note_ids``
                are provided.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.timeline.delete_notes(note_id="709f99c6-...-8e174e")
            >>> client.timeline.delete_notes(note_ids=["id-1", "id-2"])
        """
        if (note_id is None) == (note_ids is None):
            raise ValueError("Exactly one of 'note_id' or 'note_ids' must be provided")

        body: dict[str, Any]
        if note_id is not None:
            body = {"noteId": note_id}
        else:
            body = {"noteIds": note_ids}

        path = self._build_space_path("/api/note", space_id, validate_spaces)
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Pinned events (/api/pinned_event)
    # ------------------------------------------------------------------

    def pin_event(
        self,
        *,
        event_id: str,
        timeline_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Pin an event to a Timeline.

        ``PATCH /api/pinned_event``. Pins an event to an existing Timeline so
        it stays visible during the investigation.

        Args:
            event_id: The ``_id`` of the event document to pin.
            timeline_id: The ``savedObjectId`` of the Timeline to pin the
                event to.
            space_id: Optional space ID the Timeline lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the pinned event, including its
            ``pinnedEventId`` and ``version``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> pinned = client.timeline.pin_event(
            ...     event_id="d3a1d35a3e84...", timeline_id=timeline_id
            ... )
            >>> print(pinned.body["pinnedEventId"])
        """
        path = self._build_space_path("/api/pinned_event", space_id, validate_spaces)
        return self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body={"eventId": event_id, "timelineId": timeline_id},
        )

    def unpin_event(
        self,
        *,
        event_id: str,
        timeline_id: str,
        pinned_event_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Unpin an event from a Timeline.

        ``PATCH /api/pinned_event``. Unpins an event from a Timeline by
        passing the ``pinnedEventId`` returned when the event was pinned.

        Args:
            event_id: The ``_id`` of the event document to unpin.
            timeline_id: The ``savedObjectId`` of the Timeline the event is
                pinned to.
            pinned_event_id: The ``savedObjectId`` of the pinned event to
                unpin (returned by :meth:`pin_event`).
            space_id: Optional space ID the Timeline lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``{"unpinned": true}`` on success.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = client.timeline.unpin_event(
            ...     event_id="d3a1d35a3e84...",
            ...     timeline_id=timeline_id,
            ...     pinned_event_id=pinned_event_id,
            ... )
            >>> print(result.body["unpinned"])
            True
        """
        path = self._build_space_path("/api/pinned_event", space_id, validate_spaces)
        return self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body={
                "eventId": event_id,
                "timelineId": timeline_id,
                "pinnedEventId": pinned_event_id,
            },
        )
