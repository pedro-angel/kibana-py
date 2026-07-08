"""Kibana Cases API client."""

import json
import uuid
from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._sync.client import Kibana

#: Default connector object used when a case is created without an
#: external incident-management connector.
DEFAULT_CASE_CONNECTOR: dict[str, Any] = {
    "id": "none",
    "name": "none",
    "type": ".none",
    "fields": None,
}


def _encode_multipart_file(
    file: bytes | str,
    filename: str,
    mime_type: str,
    extra_fields: dict[str, str] | None = None,
) -> tuple[bytes, str]:
    """Encode a file (plus optional form fields) as a multipart/form-data body.

    :param file: File content as bytes or text.
    :param filename: File name reported in the Content-Disposition header.
    :param mime_type: MIME type of the file part.
    :param extra_fields: Optional additional plain form fields.
    :return: Tuple of (body bytes, content-type header value with boundary).
    """
    boundary = f"kbnpy{uuid.uuid4().hex}"
    if isinstance(file, str):
        file = file.encode("utf-8")

    parts: list[bytes] = []
    if extra_fields:
        for name, value in extra_fields.items():
            parts.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n'
                    f"\r\n{value}\r\n"
                ).encode()
            )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode()
        + file
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class CasesClient(NamespaceClient):
    """Client for the Kibana Cases API.

    Cases are used to open and track issues directly in Kibana. You can add
    assignees and tags to your cases, set their severity and status, and add
    alerts, comments, and visualizations. You can also send cases to external
    incident management systems by configuring connectors.

    Cases are space-scoped: every method accepts an optional ``space_id`` to
    target a specific space (``None`` targets the default space or the space
    the client is scoped to).

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a case, comment on it, then close and delete it
        >>> case = client.cases.create(
        ...     title="Suspicious login activity",
        ...     description="Multiple failed logins detected.",
        ...     tags=["security"],
        ... )
        >>> case_id = case.body["id"]
        >>> client.cases.add_comment(
        ...     case_id=case_id, comment="Investigating.", owner="cases"
        ... )
        >>> updated = client.cases.update(
        ...     id=case_id, version=case.body["version"], status="closed"
        ... )
        >>> client.cases.delete(ids=[case_id])
    """

    def __init__(
        self,
        client: Kibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the CasesClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> cases_client = CasesClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    def create(
        self,
        *,
        title: str,
        description: str,
        owner: str = "cases",
        tags: list[str] | None = None,
        connector: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
        assignees: list[dict[str, Any]] | None = None,
        category: str | None = None,
        custom_fields: list[dict[str, Any]] | None = None,
        severity: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a case.

        You must have ``all`` privileges for the **Cases** feature in the
        **Management**, **Observability**, or **Security** section of the
        Kibana feature privileges, depending on the owner of the case you're
        creating.

        Args:
            title: A title for the case (maximum 160 characters).
            description: The description for the case.
            owner: The application that owns the case: ``"cases"`` (Stack
                Management, the default), ``"observability"``, or
                ``"securitySolution"``.
            tags: Words and phrases that help categorize cases. Defaults to
                an empty list (the API requires the field to be present).
            connector: An object that contains the connector configuration
                (``id``, ``name``, ``type``, ``fields``). Defaults to the
                "none" connector when omitted.
            settings: An object that contains the case settings, e.g.
                ``{"syncAlerts": True}``. Defaults to
                ``{"syncAlerts": False}`` when omitted (the API requires the
                field to be present).
            assignees: A list of users assigned to the case, each an object
                with a ``uid`` (user profile unique identifier). Requires a
                Platinum or Enterprise license.
            category: A word or phrase that categorizes the case (maximum
                50 characters).
            custom_fields: Custom field values for the case, each an object
                with ``key``, ``type`` and ``value``. Any optional custom
                fields not specified are set to null.
            severity: The severity of the case: ``"critical"``, ``"high"``,
                ``"low"`` (server default), or ``"medium"``.
            space_id: Optional space ID to create the case in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created case, including its
            ``id``, ``version``, ``status``, ``created_at``/``created_by``
            metadata, and the fields supplied on creation.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> case = client.cases.create(
            ...     title="Suspicious login activity",
            ...     description="Multiple failed logins detected.",
            ...     tags=["security", "auth"],
            ...     severity="high",
            ... )
            >>> print(case.body["status"])
            open
        """
        body: dict[str, Any] = {
            "title": title,
            "description": description,
            "owner": owner,
            "tags": tags if tags is not None else [],
            "connector": (
                connector if connector is not None else dict(DEFAULT_CASE_CONNECTOR)
            ),
            "settings": settings if settings is not None else {"syncAlerts": False},
        }
        if assignees is not None:
            body["assignees"] = assignees
        if category is not None:
            body["category"] = category
        if custom_fields is not None:
            body["customFields"] = custom_fields
        if severity is not None:
            body["severity"] = severity

        path = self._build_space_path("/api/cases", space_id, validate_spaces)
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get(
        self,
        *,
        case_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get case information.

        Returns details about a case, including its comments and alerts.

        Args:
            case_id: The identifier for the case. To retrieve case IDs, use
                :meth:`find`.
            space_id: Optional space ID to get the case from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the case, including ``comments``,
            ``totalComment``, ``totalAlerts`` and the case fields.

        Raises:
            NotFoundError: If the case does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> case = client.cases.get(case_id="a18b38a0-...-aad599a8564f")
            >>> print(case.body["title"])
        """
        path = self._build_space_path(
            f"/api/cases/{_quote(case_id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def update(
        self,
        *,
        id: str | None = None,
        version: str | None = None,
        assignees: list[dict[str, Any]] | None = None,
        category: str | None = None,
        close_reason: str | None = None,
        connector: dict[str, Any] | None = None,
        custom_fields: list[dict[str, Any]] | None = None,
        description: str | None = None,
        settings: dict[str, Any] | None = None,
        severity: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        title: str | None = None,
        cases: list[dict[str, Any]] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update one or more cases.

        The Cases update API is a bulk endpoint (``PATCH /api/cases`` with a
        ``{"cases": [...]}`` body). This method offers a single-case-friendly
        signature: pass ``id`` and ``version`` plus the fields to change, or
        pass ``cases`` with a list of case-update objects to update several
        cases at once.

        Args:
            id: The identifier of the case to update (single-case form).
            version: The current version of the case, as returned by
                :meth:`get` or :meth:`find` (single-case form; used for
                optimistic concurrency control).
            assignees: A list of users assigned to the case, each an object
                with a ``uid``.
            category: A word or phrase that categorizes the case.
            close_reason: The reason the case was closed (sent as
                ``closeReason``).
            connector: An object that contains the connector configuration.
            custom_fields: Custom field values (sent as ``customFields``).
            description: An updated description for the case.
            settings: An object that contains the case settings, e.g.
                ``{"syncAlerts": False}``.
            severity: The severity of the case: ``"critical"``, ``"high"``,
                ``"low"``, or ``"medium"``.
            status: The status of the case: ``"open"``, ``"in-progress"``,
                or ``"closed"``.
            tags: Updated tags for the case.
            title: An updated title for the case.
            cases: Bulk form — a list of case-update objects, each with
                ``id``, ``version`` and the fields to change (raw API field
                names, e.g. ``customFields``). Mutually exclusive with
                ``id``/``version`` and the per-field arguments.
            space_id: Optional space ID the cases live in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is a **list** of the updated cases.

        Raises:
            ValueError: If neither ``cases`` nor both ``id`` and ``version``
                are provided, or if both forms are mixed.
            BadRequestError: If the request body is invalid.
            ConflictError: If the version doesn't match the current case
                version.
            NotFoundError: If a case does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> case = client.cases.get(case_id="a18b38a0-...")
            >>> updated = client.cases.update(
            ...     id=case.body["id"],
            ...     version=case.body["version"],
            ...     status="closed",
            ... )
            >>> print(updated.body[0]["status"])
            closed
        """
        if cases is not None:
            if id is not None or version is not None:
                raise ValueError(
                    "Provide either 'cases' (bulk form) or 'id' and 'version' "
                    "(single-case form), not both"
                )
            case_updates = cases
        else:
            if id is None or version is None:
                raise ValueError(
                    "Parameters 'id' and 'version' are required when 'cases' "
                    "is not provided"
                )
            case_update: dict[str, Any] = {"id": id, "version": version}
            if assignees is not None:
                case_update["assignees"] = assignees
            if category is not None:
                case_update["category"] = category
            if close_reason is not None:
                case_update["closeReason"] = close_reason
            if connector is not None:
                case_update["connector"] = connector
            if custom_fields is not None:
                case_update["customFields"] = custom_fields
            if description is not None:
                case_update["description"] = description
            if settings is not None:
                case_update["settings"] = settings
            if severity is not None:
                case_update["severity"] = severity
            if status is not None:
                case_update["status"] = status
            if tags is not None:
                case_update["tags"] = tags
            if title is not None:
                case_update["title"] = title
            case_updates = [case_update]

        path = self._build_space_path("/api/cases", space_id, validate_spaces)
        return self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body={"cases": case_updates},
        )

    def delete(
        self,
        *,
        ids: str | list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete one or more cases.

        You must have ``all`` privileges for the **Cases** feature in the
        **Management**, **Observability**, or **Security** section of the
        Kibana feature privileges, depending on the owner of the cases you're
        deleting.

        Note: the live API requires the ``ids`` query parameter to be a
        JSON-array string (e.g. ``ids=["id1","id2"]``); this method encodes
        it for you.

        Args:
            ids: A case ID or list of case IDs to delete (maximum 100). To
                retrieve case IDs, use :meth:`find`.
            space_id: Optional space ID the cases live in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success (HTTP 204).

        Raises:
            NotFoundError: If a case does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.cases.delete(ids=["a18b38a0-...-aad599a8564f"])
        """
        if isinstance(ids, str):
            ids = [ids]
        # The cases API expects a JSON-array string, not repeated keys.
        params: dict[str, Any] = {"ids": json.dumps(list(ids), separators=(",", ":"))}

        path = self._build_space_path("/api/cases", space_id, validate_spaces)
        return self.perform_request(
            "DELETE",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def find(
        self,
        *,
        assignees: str | list[str] | None = None,
        category: str | list[str] | None = None,
        default_search_operator: str | None = None,
        from_: str | None = None,
        owner: str | list[str] | None = None,
        page: int | None = None,
        per_page: int | None = None,
        reporters: str | list[str] | None = None,
        search: str | None = None,
        search_fields: str | list[str] | None = None,
        severity: str | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        status: str | None = None,
        tags: str | list[str] | None = None,
        to: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Search cases.

        Retrieves a paginated subset of cases. By default the response
        includes the first page with 20 cases per page.

        Args:
            assignees: Filter cases by assignee user profile ``uid``. To
                filter for cases without assignees, use ``"none"``.
            category: Filter cases by category.
            default_search_operator: Operator (``"AND"`` or ``"OR"``, server
                default ``"OR"``) used to combine the search across
                ``search_fields``.
            from_: Return cases created on or after this date/time (sent as
                the ``from`` query parameter; accepts date math like
                ``"now-1d"``).
            owner: Filter by case owner application: ``"cases"``,
                ``"observability"``, or ``"securitySolution"``. Defaults to
                all owners the user has access to.
            page: The page number to return (server default 1).
            per_page: The number of cases per page (server default 20,
                maximum 100).
            reporters: Filter cases by the usernames of their reporters.
            search: A simple query string to filter cases.
            search_fields: The fields to perform the ``search`` against
                (e.g. ``"title"``, ``"description"``).
            severity: Filter by severity: ``"critical"``, ``"high"``,
                ``"low"``, or ``"medium"``.
            sort_field: Field to sort results by: ``"createdAt"`` (server
                default), ``"updatedAt"``, ``"closedAt"``, ``"title"``,
                ``"category"``, ``"status"``, or ``"severity"``.
            sort_order: Sort order: ``"asc"`` or ``"desc"`` (server default).
            status: Filter by case status: ``"open"``, ``"in-progress"``, or
                ``"closed"``.
            tags: Filter cases by tag.
            to: Return cases created on or before this date/time.
            space_id: Optional space ID to search cases in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``cases`` (the page of results),
            ``total``, ``page``, ``per_page`` and per-status counts
            (``count_open_cases``, ``count_in_progress_cases``,
            ``count_closed_cases``).

        Raises:
            BadRequestError: If a filter value is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = client.cases.find(tags="security", status="open")
            >>> print(found.body["total"])
        """
        params: dict[str, Any] = {}
        if assignees is not None:
            params["assignees"] = assignees
        if category is not None:
            params["category"] = category
        if default_search_operator is not None:
            params["defaultSearchOperator"] = default_search_operator
        if from_ is not None:
            params["from"] = from_
        if owner is not None:
            params["owner"] = owner
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        if reporters is not None:
            params["reporters"] = reporters
        if search is not None:
            params["search"] = search
        if search_fields is not None:
            params["searchFields"] = search_fields
        if severity is not None:
            params["severity"] = severity
        if sort_field is not None:
            params["sortField"] = sort_field
        if sort_order is not None:
            params["sortOrder"] = sort_order
        if status is not None:
            params["status"] = status
        if tags is not None:
            params["tags"] = tags
        if to is not None:
            params["to"] = to

        path = self._build_space_path("/api/cases/_find", space_id, validate_spaces)
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def get_alerts(
        self,
        *,
        case_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get all alerts attached to a case.

        Technical preview in 9.4; this functionality may be changed or
        removed in a future release.

        Args:
            case_id: The identifier for the case.
            space_id: Optional space ID the case lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is a **list** of alerts, each with
            ``id``, ``index`` and ``attached_at``.

        Raises:
            NotFoundError: If the case does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> alerts = client.cases.get_alerts(case_id="a18b38a0-...")
            >>> for alert in alerts.body:
            ...     print(alert["id"], alert["index"])
        """
        path = self._build_space_path(
            f"/api/cases/{_quote(case_id)}/alerts", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def get_cases_by_alert(
        self,
        *,
        alert_id: str,
        owner: str | list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the cases an alert is attached to.

        Technical preview in 9.4; this functionality may be changed or
        removed in a future release.

        Args:
            alert_id: The identifier for the alert.
            owner: Filter by case owner application: ``"cases"``,
                ``"observability"``, or ``"securitySolution"``.
            space_id: Optional space ID to search in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is a **list** of objects with the
            case ``id`` and ``title`` for each case the alert is attached to.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> cases = client.cases.get_cases_by_alert(alert_id="09f0c261...")
            >>> for case in cases.body:
            ...     print(case["id"], case["title"])
        """
        params: dict[str, Any] = {}
        if owner is not None:
            params["owner"] = owner

        path = self._build_space_path(
            f"/api/cases/alerts/{_quote(alert_id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def add_comment(
        self,
        *,
        case_id: str,
        type: str = "user",
        owner: str = "cases",
        comment: str | None = None,
        alert_id: str | list[str] | None = None,
        index: str | list[str] | None = None,
        rule: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Add a comment or alert to a case.

        Args:
            case_id: The identifier for the case.
            type: The attachment type: ``"user"`` (a text comment, the
                default) or ``"alert"``.
            owner: The application that owns the case: ``"cases"`` (default),
                ``"observability"``, or ``"securitySolution"``.
            comment: The comment text (required when ``type="user"``;
                maximum 30,000 characters).
            alert_id: The alert identifier(s) (required when
                ``type="alert"``).
            index: The alert index(es); the order must match ``alert_id``
                (required when ``type="alert"``).
            rule: The rule that is associated with the alerts (an object
                with ``id`` and ``name``; required when ``type="alert"``).
            space_id: Optional space ID the case lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated case, including the new
            attachment in ``comments``.

        Raises:
            BadRequestError: If the attachment body is invalid.
            NotFoundError: If the case does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = client.cases.add_comment(
            ...     case_id="a18b38a0-...",
            ...     comment="Investigating the failed logins.",
            ... )
            >>> print(updated.body["totalComment"])
            1
        """
        body: dict[str, Any] = {"type": type, "owner": owner}
        if comment is not None:
            body["comment"] = comment
        if alert_id is not None:
            body["alertId"] = alert_id
        if index is not None:
            body["index"] = index
        if rule is not None:
            body["rule"] = rule

        path = self._build_space_path(
            f"/api/cases/{_quote(case_id)}/comments", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def update_comment(
        self,
        *,
        case_id: str,
        id: str,
        version: str,
        type: str = "user",
        owner: str = "cases",
        comment: str | None = None,
        alert_id: str | list[str] | None = None,
        index: str | list[str] | None = None,
        rule: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a comment or alert attached to a case.

        Args:
            case_id: The identifier for the case.
            id: The identifier of the comment being updated.
            version: The current version of the comment, as returned by
                :meth:`get_comment` or :meth:`get_comments` (used for
                optimistic concurrency control).
            type: The attachment type: ``"user"`` (default) or ``"alert"``.
            owner: The application that owns the case: ``"cases"`` (default),
                ``"observability"``, or ``"securitySolution"``.
            comment: The updated comment text (required when
                ``type="user"``).
            alert_id: The alert identifier(s) (required when
                ``type="alert"``).
            index: The alert index(es) (required when ``type="alert"``).
            rule: The rule associated with the alerts (required when
                ``type="alert"``).
            space_id: Optional space ID the case lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated case, including the
            modified attachment in ``comments``.

        Raises:
            BadRequestError: If the attachment body is invalid.
            ConflictError: If the version doesn't match the current comment
                version.
            NotFoundError: If the case or comment does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = client.cases.update_comment(
            ...     case_id="a18b38a0-...",
            ...     id="8af6ac20-...",
            ...     version="Wzk1LDFd",
            ...     comment="Root cause identified.",
            ... )
        """
        body: dict[str, Any] = {
            "id": id,
            "version": version,
            "type": type,
            "owner": owner,
        }
        if comment is not None:
            body["comment"] = comment
        if alert_id is not None:
            body["alertId"] = alert_id
        if index is not None:
            body["index"] = index
        if rule is not None:
            body["rule"] = rule

        path = self._build_space_path(
            f"/api/cases/{_quote(case_id)}/comments", space_id, validate_spaces
        )
        return self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_comment(
        self,
        *,
        case_id: str,
        comment_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a case comment or alert.

        Args:
            case_id: The identifier for the case.
            comment_id: The identifier for the comment. To retrieve comment
                IDs, use :meth:`get` or :meth:`get_comments`.
            space_id: Optional space ID the case lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the attachment (``id``, ``version``,
            ``type``, ``comment`` or alert fields, and audit metadata).

        Raises:
            NotFoundError: If the case or comment does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> comment = client.cases.get_comment(
            ...     case_id="a18b38a0-...", comment_id="8af6ac20-..."
            ... )
            >>> print(comment.body["comment"])
        """
        path = self._build_space_path(
            f"/api/cases/{_quote(case_id)}/comments/{_quote(comment_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def get_comments(
        self,
        *,
        case_id: str,
        page: int | None = None,
        per_page: int | None = None,
        sort_order: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Find comments and alerts attached to a case.

        Retrieves a paginated list of case attachments via the
        ``GET /api/cases/{caseId}/comments/_find`` endpoint.

        Args:
            case_id: The identifier for the case.
            page: The page number to return (server default 1).
            per_page: The number of items per page (server default 20,
                maximum 100).
            sort_order: Sort order: ``"asc"`` or ``"desc"`` (server default).
            space_id: Optional space ID the case lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``comments`` (the page of
            attachments), ``total``, ``page`` and ``per_page``.

        Raises:
            NotFoundError: If the case does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> comments = client.cases.get_comments(
            ...     case_id="a18b38a0-...", per_page=10
            ... )
            >>> print(comments.body["total"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        if sort_order is not None:
            params["sortOrder"] = sort_order

        path = self._build_space_path(
            f"/api/cases/{_quote(case_id)}/comments/_find", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def delete_comment(
        self,
        *,
        case_id: str,
        comment_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a comment or alert from a case.

        Args:
            case_id: The identifier for the case.
            comment_id: The identifier for the comment to delete.
            space_id: Optional space ID the case lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success (HTTP 204).

        Raises:
            NotFoundError: If the case or comment does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.cases.delete_comment(
            ...     case_id="a18b38a0-...", comment_id="8af6ac20-..."
            ... )
        """
        path = self._build_space_path(
            f"/api/cases/{_quote(case_id)}/comments/{_quote(comment_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    def delete_all_comments(
        self,
        *,
        case_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete all comments and alerts from a case.

        Args:
            case_id: The identifier for the case.
            space_id: Optional space ID the case lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success (HTTP 204).

        Raises:
            NotFoundError: If the case does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> client.cases.delete_all_comments(case_id="a18b38a0-...")
        """
        path = self._build_space_path(
            f"/api/cases/{_quote(case_id)}/comments", space_id, validate_spaces
        )
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    def find_user_actions(
        self,
        *,
        case_id: str,
        page: int | None = None,
        per_page: int | None = None,
        sort_order: str | None = None,
        types: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Find case activity (user actions).

        Retrieves a paginated list of user activity for a case, such as
        status changes, comments, tag updates and connector changes.

        Args:
            case_id: The identifier for the case.
            page: The page number to return (server default 1).
            per_page: The number of items per page (server default 20,
                maximum 100).
            sort_order: Sort order: ``"asc"`` or ``"desc"`` (server default).
            types: Filter activity by type. Valid values include
                ``"action"``, ``"alert"``, ``"assignees"``, ``"attachment"``,
                ``"comment"``, ``"connector"``, ``"create_case"``,
                ``"description"``, ``"pushed"``, ``"settings"``,
                ``"severity"``, ``"status"``, ``"tags"``, ``"title"`` and
                ``"user"``.
            space_id: Optional space ID the case lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``userActions`` (the page of
            activity records), ``total``, ``page`` and ``perPage``.

        Raises:
            NotFoundError: If the case does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> activity = client.cases.find_user_actions(
            ...     case_id="a18b38a0-...", types=["status"]
            ... )
            >>> for action in activity.body["userActions"]:
            ...     print(action["action"], action["type"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        if sort_order is not None:
            params["sortOrder"] = sort_order
        if types is not None:
            params["types"] = types

        path = self._build_space_path(
            f"/api/cases/{_quote(case_id)}/user_actions/_find",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def push(
        self,
        *,
        case_id: str,
        connector_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Push a case to an external service.

        Sends the case to the external incident management system configured
        for the given connector (for example Jira, ServiceNow, or IBM
        Resilient).

        Args:
            case_id: The identifier for the case.
            connector_id: The identifier for the connector. To retrieve
                connector IDs, use :meth:`find_connectors`.
            space_id: Optional space ID the case lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the case, including the
            ``external_service`` push details.

        Raises:
            NotFoundError: If the case or connector does not exist.
            BadRequestError: If the connector is not usable for pushing.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> pushed = client.cases.push(
            ...     case_id="a18b38a0-...",
            ...     connector_id="0c3b3bc0-...",
            ... )
            >>> print(pushed.body["external_service"]["external_url"])
        """
        path = self._build_space_path(
            f"/api/cases/{_quote(case_id)}/connector/{_quote(connector_id)}/_push",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    def add_file(
        self,
        *,
        case_id: str,
        file: bytes | str,
        filename: str,
        mime_type: str = "text/plain",
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Attach a file to a case.

        The file is uploaded as ``multipart/form-data``. Note that the
        server restricts the allowed MIME types (images, text, CSV, JSON,
        PDF, and Office/zip documents by default) and the maximum file size
        (100 MiB by default, 10 MiB for images).

        Args:
            case_id: The identifier for the case.
            file: The file content as bytes or text.
            filename: The desired name of the file (also sent as the
                ``filename`` form field).
            mime_type: The MIME type of the file (default ``"text/plain"``).
            space_id: Optional space ID the case lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated case; the file appears
            as an attachment in ``comments``.

        Raises:
            BadRequestError: If the file type or size is not allowed.
            NotFoundError: If the case does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = client.cases.add_file(
            ...     case_id="a18b38a0-...",
            ...     file=b"investigation notes",
            ...     filename="notes.txt",
            ... )
        """
        body, content_type = _encode_multipart_file(
            file,
            filename,
            mime_type,
            extra_fields={"filename": filename},
        )
        path = self._build_space_path(
            f"/api/cases/{_quote(case_id)}/files", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={
                "accept": "application/json",
                "content-type": content_type,
            },
            body=body,  # type: ignore[arg-type]
        )

    def get_configuration(
        self,
        *,
        owner: str | list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get case settings (configuration).

        Retrieves the case configurations, which include the closure type,
        default connector, custom fields and templates. There is one
        configuration per case owner application.

        Args:
            owner: Filter by case owner application: ``"cases"``,
                ``"observability"``, or ``"securitySolution"``. Defaults to
                all owners the user has access to.
            space_id: Optional space ID to read the configuration from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is a **list** of configuration
            objects (``id``, ``version``, ``owner``, ``closure_type``,
            ``connector``, ``customFields``, ``templates``, ...).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> configs = client.cases.get_configuration(owner="cases")
            >>> for config in configs.body:
            ...     print(config["id"], config["closure_type"])
        """
        params: dict[str, Any] = {}
        if owner is not None:
            params["owner"] = owner

        path = self._build_space_path("/api/cases/configure", space_id, validate_spaces)
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def create_configuration(
        self,
        *,
        closure_type: str,
        connector: dict[str, Any] | None = None,
        owner: str = "cases",
        custom_fields: list[dict[str, Any]] | None = None,
        templates: list[dict[str, Any]] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Add case settings (configuration).

        Case settings include external connection details, custom fields and
        templates. Connectors are used to interface with external systems.
        You must create a connector before you can use it in your cases. If
        you set a default connector, it is automatically selected when you
        create cases in Kibana. If you use the create configuration API for
        an owner that already has a configuration, it is replaced.

        Args:
            closure_type: Whether a case is closed when it is pushed to an
                external system: ``"close-by-pushing"`` or
                ``"close-by-user"``.
            connector: An object that contains the default connector
                configuration (``id``, ``name``, ``type``, ``fields``).
                Defaults to the "none" connector when omitted.
            owner: The application that owns the configuration: ``"cases"``
                (default), ``"observability"``, or ``"securitySolution"``.
            custom_fields: Custom field definitions, each an object with
                ``key``, ``label``, ``type`` and ``required``.
            templates: Case templates (technical preview in 9.4).
            space_id: Optional space ID to store the configuration in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created configuration, including
            its ``id`` and ``version``.

        Raises:
            BadRequestError: If the configuration body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> config = client.cases.create_configuration(
            ...     closure_type="close-by-user",
            ...     owner="cases",
            ... )
            >>> print(config.body["id"])
        """
        body: dict[str, Any] = {
            "closure_type": closure_type,
            "connector": (
                connector if connector is not None else dict(DEFAULT_CASE_CONNECTOR)
            ),
            "owner": owner,
        }
        if custom_fields is not None:
            body["customFields"] = custom_fields
        if templates is not None:
            body["templates"] = templates

        path = self._build_space_path("/api/cases/configure", space_id, validate_spaces)
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def update_configuration(
        self,
        *,
        configuration_id: str,
        version: str,
        closure_type: str | None = None,
        connector: dict[str, Any] | None = None,
        custom_fields: list[dict[str, Any]] | None = None,
        templates: list[dict[str, Any]] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update case settings (configuration).

        Updates external connection details, custom fields and templates for
        a case configuration. Connectors are used to interface with external
        systems.

        Args:
            configuration_id: The identifier for the configuration. To
                retrieve configuration IDs, use :meth:`get_configuration`.
            version: The current version of the configuration, as returned
                by :meth:`get_configuration` (used for optimistic
                concurrency control).
            closure_type: Whether a case is closed when it is pushed to an
                external system: ``"close-by-pushing"`` or
                ``"close-by-user"``.
            connector: An object that contains the default connector
                configuration.
            custom_fields: Custom field definitions.
            templates: Case templates (technical preview in 9.4).
            space_id: Optional space ID the configuration lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated configuration, with its
            new ``version``.

        Raises:
            BadRequestError: If the configuration body is invalid.
            ConflictError: If the version doesn't match the current
                configuration version.
            NotFoundError: If the configuration does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = client.cases.update_configuration(
            ...     configuration_id="3297a0f0-...",
            ...     version="WzIwMiwxXQ==",
            ...     closure_type="close-by-pushing",
            ... )
        """
        body: dict[str, Any] = {"version": version}
        if closure_type is not None:
            body["closure_type"] = closure_type
        if connector is not None:
            body["connector"] = connector
        if custom_fields is not None:
            body["customFields"] = custom_fields
        if templates is not None:
            body["templates"] = templates

        path = self._build_space_path(
            f"/api/cases/configure/{_quote(configuration_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def find_connectors(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get case connectors.

        Retrieves information about the connectors that are supported for
        use in cases (Jira, ServiceNow, Swimlane, IBM Resilient, and Cases
        Webhook types).

        Args:
            space_id: Optional space ID to search connectors in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is a **list** of connectors usable
            in cases.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> connectors = client.cases.find_connectors()
            >>> for connector in connectors.body:
            ...     print(connector["id"], connector["actionTypeId"])
        """
        path = self._build_space_path(
            "/api/cases/configure/connectors/_find", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def get_reporters(
        self,
        *,
        owner: str | list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get case creators (reporters).

        Returns information about the users who opened cases.

        Args:
            owner: Filter by case owner application: ``"cases"``,
                ``"observability"``, or ``"securitySolution"``. Defaults to
                all owners the user has access to.
            space_id: Optional space ID to search in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is a **list** of reporters, each
            with ``username``, ``full_name``, ``email`` and ``profile_uid``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> reporters = client.cases.get_reporters(owner="cases")
            >>> for reporter in reporters.body:
            ...     print(reporter["username"])
        """
        params: dict[str, Any] = {}
        if owner is not None:
            params["owner"] = owner

        path = self._build_space_path("/api/cases/reporters", space_id, validate_spaces)
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    def get_tags(
        self,
        *,
        owner: str | list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get case tags.

        Aggregates and returns a list of all unique tags used in cases.

        Args:
            owner: Filter by case owner application: ``"cases"``,
                ``"observability"``, or ``"securitySolution"``. Defaults to
                all owners the user has access to.
            space_id: Optional space ID to search in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is a **list** of tag strings.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> tags = client.cases.get_tags()
            >>> print(tags.body)
            ['security', 'auth']
        """
        params: dict[str, Any] = {}
        if owner is not None:
            params["owner"] = owner

        path = self._build_space_path("/api/cases/tags", space_id, validate_spaces)
        return self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )
