"""Async Kibana Security Endpoint Management API client."""

import json
import uuid
from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


def _build_multipart_body(
    *,
    fields: dict[str, Any],
    file: bytes | None = None,
    filename: str = "upload.bin",
    file_content_type: str = "application/octet-stream",
) -> tuple[bytes, str]:
    """Build a ``multipart/form-data`` body for the endpoint file-upload APIs.

    Text fields are emitted as plain form-data parts. Values that are lists,
    dicts, or booleans are JSON-encoded (Kibana parses those parts as JSON),
    matching how the Kibana UI submits the ``platform``/``tags`` arrays and
    the ``requiresInput`` boolean. When ``file`` is ``None`` no file part is
    appended (used by the scripts-library PATCH route for metadata-only
    updates).

    :param fields: Text/JSON form fields keyed by field name
    :param file: Optional raw file bytes for the ``file`` form field
    :param filename: Filename advertised for the uploaded file part
    :param file_content_type: Content type advertised for the file part
    :return: Tuple of (body bytes, content-type header value with boundary)
    """
    boundary = f"kbnpy{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        if value is None:
            continue
        if isinstance(value, (list, dict, bool)):
            rendered = json.dumps(value)
        else:
            rendered = str(value)
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n'
                "\r\n"
                f"{rendered}\r\n"
            ).encode()
        )
    if file is not None:
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; '
                f'filename="{filename}"\r\n'
                f"Content-Type: {file_content_type}\r\n"
                "\r\n"
            ).encode()
            + file
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class AsyncEndpointClient(AsyncNamespaceClient):
    """Async client for the Kibana Security Endpoint Management API.

    The Endpoint Management API (``/api/endpoint/...``) drives Elastic Defend:
    it lists enrolled endpoint hosts and their metadata, runs *response
    actions* against them (isolate/release a host, terminate or suspend a
    process, list running processes, retrieve or upload a file, run a command
    or a script, scan for malware, generate a memory dump, or cancel a
    pending action), inspects action history and status, reads endpoint policy
    responses, manages the protection-updates note on a Defend package policy,
    and manages the reusable scripts library.

    All Endpoint Management APIs are space-scoped: every method accepts an
    optional ``space_id`` to target a specific space (``None`` targets the
    default space or the space the client is scoped to).

    .. note:: Response actions require the target hosts to have the Elastic
       Defend integration installed and enrolled. Against a stack with no
       enrolled endpoints these routes return an HTTP 400 (``The host does
       not have Elastic Defend integration installed``).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # List enrolled endpoint hosts
        >>> hosts = await client.endpoint.get_metadata_list(host_statuses=["healthy"])
        >>>
        >>> # Isolate a host
        >>> action = await client.endpoint.isolate(
        ...     endpoint_ids=["endpoint-id-1"],
        ...     comment="Investigating suspicious activity",
        ... )
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncEndpointClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).
        """
        super().__init__(client, default_space_id, validate_spaces)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    async def get_metadata_list(
        self,
        *,
        host_statuses: list[str] | None = None,
        page: int | None = None,
        page_size: int | None = None,
        kuery: str | None = None,
        sort_field: str | None = None,
        sort_direction: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a metadata list of enrolled endpoint hosts.

        ``GET /api/endpoint/metadata``

        Args:
            host_statuses: Filter by agent health statuses. Any of
                ``healthy``, ``offline``, ``updating``, ``inactive``,
                ``unenrolled``. In the 9.4.3 spec this is marked required, but
                the live server accepts requests without it.
            page: Page number (default 1).
            page_size: Number of items per page (1-100, default 10).
            kuery: A KQL string to filter the hosts.
            sort_field: Field to sort by (e.g. ``enrolled_at``,
                ``metadata.host.hostname``, ``host_status``, ``last_checkin``).
            sort_direction: ``asc`` or ``desc``.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse whose body has ``data`` (list of host metadata),
            ``total``, ``page``, ``pageSize``, ``sortField`` and
            ``sortDirection``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> hosts = await client.endpoint.get_metadata_list(
            ...     host_statuses=["healthy"], page_size=50
            ... )
            >>> print(hosts.body["total"])
        """
        params: dict[str, Any] = {}
        if host_statuses is not None:
            params["hostStatuses"] = host_statuses
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        if kuery is not None:
            params["kuery"] = kuery
        if sort_field is not None:
            params["sortField"] = sort_field
        if sort_direction is not None:
            params["sortDirection"] = sort_direction

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/metadata", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def get_metadata(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get metadata for a single endpoint host.

        ``GET /api/endpoint/metadata/{id}``

        Args:
            id: The endpoint host ID.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the host metadata document.

        Raises:
            NotFoundError: If no endpoint with that ID exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> host = await client.endpoint.get_metadata(id="endpoint-id-1")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/endpoint/metadata/{_quote(id)}", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Actions: listing / status / details / files
    # ------------------------------------------------------------------
    async def get_actions_list(
        self,
        *,
        page: int | None = None,
        page_size: int | None = None,
        commands: list[str] | None = None,
        agent_ids: str | list[str] | None = None,
        user_ids: str | list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        agent_types: str | None = None,
        with_outputs: str | list[str] | None = None,
        types: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a list of all response actions.

        ``GET /api/endpoint/action``

        Args:
            page: Page number.
            page_size: Number of items per page.
            commands: Filter by response action command names (e.g.
                ``isolate``, ``unisolate``, ``kill-process``, ``execute``).
            agent_ids: A single agent ID or list of agent IDs (max 250).
            user_ids: A single user ID or list of user IDs (max 50).
            start_date: Start date (ISO 8601 or date-math) to filter actions.
            end_date: End date (ISO 8601 or date-math) to filter actions.
            agent_types: Agent type to filter by (``endpoint``,
                ``sentinel_one``, ``crowdstrike``,
                ``microsoft_defender_endpoint``).
            with_outputs: A single action ID or list of action IDs whose full
                output should be included (max 50).
            types: List of response action types (``automated``, ``manual``).
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the paginated action list.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> actions = await client.endpoint.get_actions_list(
            ...     commands=["isolate"], page_size=20
            ... )

        .. note:: On a stack that has never run a response action the backing
           index does not yet exist and the live server answers HTTP 404
           (``index_not_found_exception``) until the first action is created.
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        if commands is not None:
            params["commands"] = commands
        if agent_ids is not None:
            params["agentIds"] = agent_ids
        if user_ids is not None:
            params["userIds"] = user_ids
        if start_date is not None:
            params["startDate"] = start_date
        if end_date is not None:
            params["endDate"] = end_date
        if agent_types is not None:
            params["agentTypes"] = agent_types
        if with_outputs is not None:
            params["withOutputs"] = with_outputs
        if types is not None:
            params["types"] = types

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def get_actions_status(
        self,
        *,
        agent_ids: str | list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the response actions status for one or more agents.

        ``GET /api/endpoint/action_status``

        Args:
            agent_ids: A single agent ID or list of agent IDs (max 50).
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing per-agent action status data.

        Raises:
            NotFoundError: If an agent ID cannot be found.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> status = await client.endpoint.get_actions_status(
            ...     agent_ids=["agent-id-1", "agent-id-2"]
            ... )
        """
        params: dict[str, Any] = {"agent_ids": agent_ids}
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action_status", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def get_action_details(
        self,
        *,
        action_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the details of a single response action.

        ``GET /api/endpoint/action/{action_id}``

        Args:
            action_id: The ID of the response action.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the action details.

        Raises:
            NotFoundError: If the action does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> details = await client.endpoint.get_action_details(
            ...     action_id="action-id-1"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/endpoint/action/{_quote(action_id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_actions_state(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the overall response-actions state.

        ``GET /api/endpoint/action/state``

        Reports whether the current license/configuration allows response
        actions to be encrypted (``data.canEncrypt``).

        Args:
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse whose body has ``data`` with ``canEncrypt``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> state = await client.endpoint.get_actions_state()
            >>> print(state.body["data"]["canEncrypt"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/state", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_action_file_info(
        self,
        *,
        action_id: str,
        file_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get information about a file produced by a response action.

        ``GET /api/endpoint/action/{action_id}/file/{file_id}``

        Args:
            action_id: The ID of the response action that produced the file.
            file_id: The ID of the file.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the file metadata.

        Raises:
            NotFoundError: If the action or file does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> info = await client.endpoint.get_action_file_info(
            ...     action_id="action-id-1", file_id="file-id-1"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/endpoint/action/{_quote(action_id)}/file/{_quote(file_id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def download_action_file(
        self,
        *,
        action_id: str,
        file_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Download a file produced by a response action.

        ``GET /api/endpoint/action/{action_id}/file/{file_id}/download``

        The response body is the raw file (typically a password-protected zip
        archive), returned as ``bytes``.

        Args:
            action_id: The ID of the response action that produced the file.
            file_id: The ID of the file to download.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            Response whose ``body`` is the raw file content.

        Raises:
            NotFoundError: If the action or file does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> resp = await client.endpoint.download_action_file(
            ...     action_id="action-id-1", file_id="file-id-1"
            ... )
            >>> open("collected.zip", "wb").write(resp.body)
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/endpoint/action/{_quote(action_id)}/file/{_quote(file_id)}"
            "/download",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/octet-stream"},
        )

    # ------------------------------------------------------------------
    # Response actions (POST /api/endpoint/action/...)
    # ------------------------------------------------------------------
    def _action_body(
        self,
        *,
        endpoint_ids: list[str],
        agent_type: str | None,
        alert_ids: list[str] | None,
        case_ids: list[str] | None,
        comment: str | None,
        parameters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Assemble the common response-action request body."""
        body: dict[str, Any] = {"endpoint_ids": endpoint_ids}
        if agent_type is not None:
            body["agent_type"] = agent_type
        if alert_ids is not None:
            body["alert_ids"] = alert_ids
        if case_ids is not None:
            body["case_ids"] = case_ids
        if comment is not None:
            body["comment"] = comment
        if parameters is not None:
            body["parameters"] = parameters
        return body

    async def isolate(
        self,
        *,
        endpoint_ids: list[str],
        agent_type: str | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        comment: str | None = None,
        parameters: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Isolate one or more endpoint hosts from the network.

        ``POST /api/endpoint/action/isolate``

        Args:
            endpoint_ids: List of endpoint IDs to isolate (1-250).
            agent_type: Agent type (``endpoint``, ``sentinel_one``,
                ``crowdstrike``, ``microsoft_defender_endpoint``). Defaults to
                ``endpoint``.
            alert_ids: Optional alert IDs to associate with the action.
            case_ids: Optional case IDs to log the action against.
            comment: Optional comment.
            parameters: Optional parameters object.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created action.

        Raises:
            BadRequestError: If the host lacks the Elastic Defend integration.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> action = await client.endpoint.isolate(
            ...     endpoint_ids=["endpoint-id-1"], comment="Quarantine"
            ... )
        """
        body = self._action_body(
            endpoint_ids=endpoint_ids,
            agent_type=agent_type,
            alert_ids=alert_ids,
            case_ids=case_ids,
            comment=comment,
            parameters=parameters,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/isolate", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def unisolate(
        self,
        *,
        endpoint_ids: list[str],
        agent_type: str | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        comment: str | None = None,
        parameters: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Release an isolated endpoint host back onto the network.

        ``POST /api/endpoint/action/unisolate``

        Args:
            endpoint_ids: List of endpoint IDs to release (1-250).
            agent_type: Agent type. Defaults to ``endpoint``.
            alert_ids: Optional alert IDs to associate with the action.
            case_ids: Optional case IDs to log the action against.
            comment: Optional comment.
            parameters: Optional parameters object.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created action.

        Raises:
            BadRequestError: If the host lacks the Elastic Defend integration.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> action = await client.endpoint.unisolate(
            ...     endpoint_ids=["endpoint-id-1"]
            ... )
        """
        body = self._action_body(
            endpoint_ids=endpoint_ids,
            agent_type=agent_type,
            alert_ids=alert_ids,
            case_ids=case_ids,
            comment=comment,
            parameters=parameters,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/unisolate", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def kill_process(
        self,
        *,
        endpoint_ids: list[str],
        parameters: dict[str, Any],
        agent_type: str | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        comment: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Terminate a process on one or more endpoint hosts.

        ``POST /api/endpoint/action/kill_process``

        Args:
            endpoint_ids: List of endpoint IDs (1-250).
            parameters: Process selector. One of ``{"pid": <int>}``,
                ``{"entity_id": <str>}``, or ``{"process_name": <str>}``
                (``process_name`` is SentinelOne only).
            agent_type: Agent type. Defaults to ``endpoint``.
            alert_ids: Optional alert IDs to associate with the action.
            case_ids: Optional case IDs to log the action against.
            comment: Optional comment.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created action.

        Raises:
            BadRequestError: If the host lacks the Elastic Defend integration
                or the parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> action = await client.endpoint.kill_process(
            ...     endpoint_ids=["endpoint-id-1"], parameters={"pid": 123}
            ... )
        """
        body = self._action_body(
            endpoint_ids=endpoint_ids,
            agent_type=agent_type,
            alert_ids=alert_ids,
            case_ids=case_ids,
            comment=comment,
            parameters=parameters,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/kill_process", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def suspend_process(
        self,
        *,
        endpoint_ids: list[str],
        parameters: dict[str, Any],
        agent_type: str | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        comment: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Suspend a process on one or more endpoint hosts.

        ``POST /api/endpoint/action/suspend_process``

        Args:
            endpoint_ids: List of endpoint IDs (1-250).
            parameters: Process selector. One of ``{"pid": <int>}`` or
                ``{"entity_id": <str>}``.
            agent_type: Agent type. Defaults to ``endpoint``.
            alert_ids: Optional alert IDs to associate with the action.
            case_ids: Optional case IDs to log the action against.
            comment: Optional comment.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created action.

        Raises:
            BadRequestError: If the host lacks the Elastic Defend integration
                or the parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> action = await client.endpoint.suspend_process(
            ...     endpoint_ids=["endpoint-id-1"], parameters={"pid": 123}
            ... )
        """
        body = self._action_body(
            endpoint_ids=endpoint_ids,
            agent_type=agent_type,
            alert_ids=alert_ids,
            case_ids=case_ids,
            comment=comment,
            parameters=parameters,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/suspend_process", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_running_processes(
        self,
        *,
        endpoint_ids: list[str],
        agent_type: str | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        comment: str | None = None,
        parameters: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List the running processes on one or more endpoint hosts.

        ``POST /api/endpoint/action/running_procs``

        Args:
            endpoint_ids: List of endpoint IDs (1-250).
            agent_type: Agent type. Defaults to ``endpoint``.
            alert_ids: Optional alert IDs to associate with the action.
            case_ids: Optional case IDs to log the action against.
            comment: Optional comment.
            parameters: Optional parameters object.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created action.

        Raises:
            BadRequestError: If the host lacks the Elastic Defend integration.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> action = await client.endpoint.get_running_processes(
            ...     endpoint_ids=["endpoint-id-1"]
            ... )
        """
        body = self._action_body(
            endpoint_ids=endpoint_ids,
            agent_type=agent_type,
            alert_ids=alert_ids,
            case_ids=case_ids,
            comment=comment,
            parameters=parameters,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/running_procs", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_file(
        self,
        *,
        endpoint_ids: list[str],
        parameters: dict[str, Any],
        agent_type: str | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        comment: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Retrieve a file from one or more endpoint hosts.

        ``POST /api/endpoint/action/get_file``

        Args:
            endpoint_ids: List of endpoint IDs (1-250).
            parameters: Must include ``path`` (the absolute path of the file
                to retrieve on the host).
            agent_type: Agent type. Defaults to ``endpoint``.
            alert_ids: Optional alert IDs to associate with the action.
            case_ids: Optional case IDs to log the action against.
            comment: Optional comment.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created action (poll the file
            info/download routes with the returned action ID once complete).

        Raises:
            BadRequestError: If the host lacks the Elastic Defend integration
                or the parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> action = await client.endpoint.get_file(
            ...     endpoint_ids=["endpoint-id-1"],
            ...     parameters={"path": "/etc/passwd"},
            ... )
        """
        body = self._action_body(
            endpoint_ids=endpoint_ids,
            agent_type=agent_type,
            alert_ids=alert_ids,
            case_ids=case_ids,
            comment=comment,
            parameters=parameters,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/get_file", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def execute(
        self,
        *,
        endpoint_ids: list[str],
        parameters: dict[str, Any],
        agent_type: str | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        comment: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Run a shell command on one or more endpoint hosts.

        ``POST /api/endpoint/action/execute``

        Args:
            endpoint_ids: List of endpoint IDs (1-250).
            parameters: Must include ``command`` (the command line to run) and
                may include ``timeout`` (seconds).
            agent_type: Agent type. Defaults to ``endpoint``.
            alert_ids: Optional alert IDs to associate with the action.
            case_ids: Optional case IDs to log the action against.
            comment: Optional comment.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created action.

        Raises:
            BadRequestError: If the host lacks the Elastic Defend integration
                or the parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> action = await client.endpoint.execute(
            ...     endpoint_ids=["endpoint-id-1"],
            ...     parameters={"command": "ls -la", "timeout": 600},
            ... )
        """
        body = self._action_body(
            endpoint_ids=endpoint_ids,
            agent_type=agent_type,
            alert_ids=alert_ids,
            case_ids=case_ids,
            comment=comment,
            parameters=parameters,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/execute", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def scan(
        self,
        *,
        endpoint_ids: list[str],
        parameters: dict[str, Any],
        agent_type: str | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        comment: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Scan a file or directory on one or more endpoint hosts.

        ``POST /api/endpoint/action/scan``

        Args:
            endpoint_ids: List of endpoint IDs (1-250).
            parameters: Must include ``path`` (the folder or file to scan).
            agent_type: Agent type. Defaults to ``endpoint``.
            alert_ids: Optional alert IDs to associate with the action.
            case_ids: Optional case IDs to log the action against.
            comment: Optional comment.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created action.

        Raises:
            BadRequestError: If the host lacks the Elastic Defend integration
                or the parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> action = await client.endpoint.scan(
            ...     endpoint_ids=["endpoint-id-1"],
            ...     parameters={"path": "/opt"},
            ... )
        """
        body = self._action_body(
            endpoint_ids=endpoint_ids,
            agent_type=agent_type,
            alert_ids=alert_ids,
            case_ids=case_ids,
            comment=comment,
            parameters=parameters,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/scan", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def generate_memory_dump(
        self,
        *,
        endpoint_ids: list[str],
        parameters: dict[str, Any],
        agent_type: str | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        comment: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Generate a memory dump from one or more endpoint hosts.

        ``POST /api/endpoint/action/memory_dump``

        Args:
            endpoint_ids: List of endpoint IDs (1-250).
            parameters: Dump selector. Either ``{"type": "kernel"}`` for a
                full kernel dump, or ``{"type": "process", "pid": <int>}`` /
                ``{"type": "process", "entity_id": <str>}`` for a process.
            agent_type: Agent type. Defaults to ``endpoint``.
            alert_ids: Optional alert IDs to associate with the action.
            case_ids: Optional case IDs to log the action against.
            comment: Optional comment.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created action.

        Raises:
            BadRequestError: If the host lacks the Elastic Defend integration,
                the parameters are invalid, or the feature is disabled.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> action = await client.endpoint.generate_memory_dump(
            ...     endpoint_ids=["endpoint-id-1"],
            ...     parameters={"type": "kernel"},
            ... )

        .. note:: This action is gated behind a feature flag; on a stack where
           it is disabled the live server answers HTTP 400
           (``[request body.agent_type]: feature is disabled``).
        """
        body = self._action_body(
            endpoint_ids=endpoint_ids,
            agent_type=agent_type,
            alert_ids=alert_ids,
            case_ids=case_ids,
            comment=comment,
            parameters=parameters,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/memory_dump", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def run_script(
        self,
        *,
        endpoint_ids: list[str],
        parameters: dict[str, Any],
        agent_type: str | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        comment: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Run a script on one or more endpoint hosts.

        ``POST /api/endpoint/action/run_script``

        The shape of ``parameters`` depends on the ``agent_type``:

        - Elastic Defend (``endpoint``): ``{"scriptId": <str>,
          "scriptInput": <str>}`` referencing a scripts-library entry.
        - CrowdStrike raw: ``{"raw": <str>, "commandLine": <str>,
          "timeout": <int>}``.
        - CrowdStrike host path: ``{"hostPath": <str>, ...}``.
        - CrowdStrike cloud file: ``{"cloudFile": <str>, ...}``.
        - SentinelOne / Microsoft Defender variants also supported.

        Args:
            endpoint_ids: List of endpoint IDs (1-250).
            parameters: Script selector (see above).
            agent_type: Agent type. Defaults to ``endpoint``.
            alert_ids: Optional alert IDs to associate with the action.
            case_ids: Optional case IDs to log the action against.
            comment: Optional comment.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created action.

        Raises:
            BadRequestError: If the host lacks the Elastic Defend integration
                or the parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> action = await client.endpoint.run_script(
            ...     endpoint_ids=["endpoint-id-1"],
            ...     parameters={"scriptId": "script-id-1"},
            ... )
        """
        body = self._action_body(
            endpoint_ids=endpoint_ids,
            agent_type=agent_type,
            alert_ids=alert_ids,
            case_ids=case_ids,
            comment=comment,
            parameters=parameters,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/run_script", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def cancel(
        self,
        *,
        endpoint_ids: list[str],
        parameters: dict[str, Any],
        agent_type: str | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        comment: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Cancel a pending response action.

        ``POST /api/endpoint/action/cancel``

        Args:
            endpoint_ids: List of endpoint IDs (1-250).
            parameters: Must include ``id`` (the action ID to cancel).
            agent_type: Agent type. Defaults to ``endpoint``.
            alert_ids: Optional alert IDs to associate with the action.
            case_ids: Optional case IDs to log the action against.
            comment: Optional comment.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created cancellation action.

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> action = await client.endpoint.cancel(
            ...     endpoint_ids=["endpoint-id-1"],
            ...     parameters={"id": "action-id-1"},
            ... )
        """
        body = self._action_body(
            endpoint_ids=endpoint_ids,
            agent_type=agent_type,
            alert_ids=alert_ids,
            case_ids=case_ids,
            comment=comment,
            parameters=parameters,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/cancel", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def upload(
        self,
        *,
        endpoint_ids: list[str],
        file: bytes,
        filename: str = "upload.bin",
        agent_type: str | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        comment: str | None = None,
        parameters: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Upload a file to one or more endpoint hosts.

        ``POST /api/endpoint/action/upload``

        This is a ``multipart/form-data`` request: the file bytes are sent in
        the ``file`` part while the action fields are sent as JSON-encoded
        form parts.

        Args:
            endpoint_ids: List of endpoint IDs (1-250).
            file: Raw bytes of the file to upload.
            filename: Filename advertised for the uploaded file part.
            agent_type: Agent type. Defaults to ``endpoint``.
            alert_ids: Optional alert IDs to associate with the action.
            case_ids: Optional case IDs to log the action against.
            comment: Optional comment.
            parameters: Optional parameters object (e.g.
                ``{"overwrite": True}``).
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created action.

        Raises:
            BadRequestError: If the host lacks the Elastic Defend integration
                or the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> action = await client.endpoint.upload(
            ...     endpoint_ids=["endpoint-id-1"],
            ...     file=b"#!/bin/sh\\necho hi\\n",
            ...     filename="fix.sh",
            ...     parameters={"overwrite": True},
            ... )
        """
        fields: dict[str, Any] = {"endpoint_ids": endpoint_ids}
        if agent_type is not None:
            fields["agent_type"] = agent_type
        if alert_ids is not None:
            fields["alert_ids"] = alert_ids
        if case_ids is not None:
            fields["case_ids"] = case_ids
        if comment is not None:
            fields["comment"] = comment
        if parameters is not None:
            fields["parameters"] = parameters

        raw_body, content_type = _build_multipart_body(
            fields=fields, file=file, filename=filename
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/action/upload", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json", "content-type": content_type},
            body=raw_body,  # type: ignore[arg-type]
        )

    # ------------------------------------------------------------------
    # Policy response
    # ------------------------------------------------------------------
    async def get_policy_response(
        self,
        *,
        agent_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the most recent policy response for an endpoint host.

        ``GET /api/endpoint/policy_response``

        Args:
            agent_id: The endpoint agent ID whose policy response to fetch.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the policy response document.

        Raises:
            NotFoundError: If no policy response exists for the agent.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> resp = await client.endpoint.get_policy_response(agent_id="agent-1")
        """
        params: dict[str, Any] = {"agentId": agent_id}
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/policy_response", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Protection updates note
    # ------------------------------------------------------------------
    async def get_protection_updates_note(
        self,
        *,
        package_policy_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the protection-updates note for a Defend package policy.

        ``GET /api/endpoint/protection_updates_note/{package_policy_id}``

        Args:
            package_policy_id: The ID of the Elastic Defend package policy.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the note.

        Raises:
            NotFoundError: If the package policy does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> note = await client.endpoint.get_protection_updates_note(
            ...     package_policy_id="policy-id-1"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/endpoint/protection_updates_note/{_quote(package_policy_id)}",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def create_update_protection_updates_note(
        self,
        *,
        package_policy_id: str,
        note: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create or update the protection-updates note for a Defend policy.

        ``POST /api/endpoint/protection_updates_note/{package_policy_id}``

        Args:
            package_policy_id: The ID of the Elastic Defend package policy.
            note: The note text.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the created/updated note.

        Raises:
            NotFoundError: If the package policy does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.endpoint.create_update_protection_updates_note(
            ...     package_policy_id="policy-id-1",
            ...     note="Pinned to 2024-01-01 protection artifacts",
            ... )
        """
        body: dict[str, Any] = {}
        if note is not None:
            body["note"] = note
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/endpoint/protection_updates_note/{_quote(package_policy_id)}",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Scripts library
    # ------------------------------------------------------------------
    async def get_scripts(
        self,
        *,
        page: int | None = None,
        page_size: int | None = None,
        sort_field: str | None = None,
        sort_direction: str | None = None,
        kuery: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a list of scripts from the scripts library.

        ``GET /api/endpoint/scripts_library``

        Args:
            page: Page number (default 1).
            page_size: Number of items per page (1-1000, default 10).
            sort_field: Field to sort by (``name``, ``createdAt``,
                ``createdBy``, ``updatedAt``, ``updatedBy``, ``fileSize``).
            sort_direction: ``asc`` or ``desc``.
            kuery: A KQL query string to filter the scripts.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse whose body has ``data`` (list of scripts),
            ``total``, ``page``, ``pageSize``, ``sortField`` and
            ``sortDirection``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> scripts = await client.endpoint.get_scripts(page_size=50)
            >>> print(scripts.body["total"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        if sort_field is not None:
            params["sortField"] = sort_field
        if sort_direction is not None:
            params["sortDirection"] = sort_direction
        if kuery is not None:
            params["kuery"] = kuery

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/scripts_library", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def get_script(
        self,
        *,
        script_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a single script from the scripts library.

        ``GET /api/endpoint/scripts_library/{script_id}``

        Args:
            script_id: The ID of the script.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse containing the script metadata.

        Raises:
            NotFoundError: If the script does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> script = await client.endpoint.get_script(script_id="script-id-1")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/endpoint/scripts_library/{_quote(script_id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def create_script(
        self,
        *,
        name: str,
        platform: list[str],
        file_type: str,
        file: bytes,
        filename: str = "script.sh",
        description: str | None = None,
        example: str | None = None,
        instructions: str | None = None,
        path_to_executable: str | None = None,
        requires_input: bool | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a script in the scripts library.

        ``POST /api/endpoint/scripts_library``

        This is a ``multipart/form-data`` request: the script/archive bytes
        are sent in the ``file`` part; the ``platform`` and ``tags`` arrays
        and the ``requiresInput`` boolean are JSON-encoded form parts.

        Args:
            name: Name of the script.
            platform: Platforms supported by the script (any of ``linux``,
                ``macos``, ``windows``).
            file_type: ``script`` for a single script file, or ``archive`` for
                a .zip (in which case ``path_to_executable`` is required).
            file: Raw bytes of the script/archive file.
            filename: Filename advertised for the uploaded file part.
            description: Description of the script.
            example: Example usage of the script.
            instructions: Usage instructions, including supported input args.
            path_to_executable: For ``archive`` uploads, the relative path to
                the executable within the archive.
            requires_input: Whether the script requires input arguments.
            tags: Categorization tags. Valid values include
                ``remediationAction``, ``dataCollection``,
                ``networkDiagnostics``, ``networkAction``, ``systemInventory``,
                ``forensicCollection``, ``threatHunting``, ``discovery``,
                ``systemManagement``, ``userManagement``, ``troubleshooting``.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse whose body has ``data`` with the created script,
            including its ``id``, ``fileId``, ``fileHash`` and ``downloadUri``.

        Raises:
            BadRequestError: If the request is invalid (bad tag/platform, etc.).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> created = await client.endpoint.create_script(
            ...     name="collect-logs",
            ...     platform=["linux"],
            ...     file_type="script",
            ...     file=b"#!/bin/sh\\necho hi\\n",
            ...     filename="collect.sh",
            ... )
            >>> print(created.body["data"]["id"])
        """
        fields: dict[str, Any] = {
            "name": name,
            "platform": platform,
            "fileType": file_type,
        }
        if description is not None:
            fields["description"] = description
        if example is not None:
            fields["example"] = example
        if instructions is not None:
            fields["instructions"] = instructions
        if path_to_executable is not None:
            fields["pathToExecutable"] = path_to_executable
        if requires_input is not None:
            fields["requiresInput"] = requires_input
        if tags is not None:
            fields["tags"] = tags

        raw_body, content_type = _build_multipart_body(
            fields=fields, file=file, filename=filename
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/endpoint/scripts_library", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json", "content-type": content_type},
            body=raw_body,  # type: ignore[arg-type]
        )

    async def update_script(
        self,
        *,
        script_id: str,
        file: bytes | None = None,
        filename: str = "script.sh",
        name: str | None = None,
        platform: list[str] | None = None,
        file_type: str | None = None,
        description: str | None = None,
        example: str | None = None,
        instructions: str | None = None,
        path_to_executable: str | None = None,
        requires_input: bool | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a script in the scripts library.

        ``PATCH /api/endpoint/scripts_library/{script_id}``

        This is a ``multipart/form-data`` request. All fields are optional; a
        new ``file`` part is only sent when ``file`` is provided.

        Args:
            script_id: The ID of the script to update.
            file: Optional new script/archive bytes.
            filename: Filename advertised for the uploaded file part (only used
                when ``file`` is provided).
            name: New name.
            platform: New supported platforms.
            file_type: New file type (``script`` or ``archive``).
            description: New description.
            example: New example usage.
            instructions: New usage instructions.
            path_to_executable: New relative path to executable (archives).
            requires_input: Whether the script requires input arguments.
            tags: New categorization tags.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse whose body has ``data`` with the updated script.

        Raises:
            NotFoundError: If the script does not exist.
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.endpoint.update_script(
            ...     script_id="script-id-1",
            ...     description="Updated description",
            ... )
        """
        fields: dict[str, Any] = {}
        if name is not None:
            fields["name"] = name
        if platform is not None:
            fields["platform"] = platform
        if file_type is not None:
            fields["fileType"] = file_type
        if description is not None:
            fields["description"] = description
        if example is not None:
            fields["example"] = example
        if instructions is not None:
            fields["instructions"] = instructions
        if path_to_executable is not None:
            fields["pathToExecutable"] = path_to_executable
        if requires_input is not None:
            fields["requiresInput"] = requires_input
        if tags is not None:
            fields["tags"] = tags

        # When no new file is supplied, omit the file part entirely so the
        # PATCH only updates metadata.
        raw_body, content_type = _build_multipart_body(
            fields=fields, file=file, filename=filename
        )

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/endpoint/scripts_library/{_quote(script_id)}", space_id
        )
        return await self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json", "content-type": content_type},
            body=raw_body,  # type: ignore[arg-type]
        )

    async def delete_script(
        self,
        *,
        script_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a script from the scripts library.

        ``DELETE /api/endpoint/scripts_library/{script_id}``

        Args:
            script_id: The ID of the script to delete.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            NotFoundError: If the script does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.endpoint.delete_script(script_id="script-id-1")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/endpoint/scripts_library/{_quote(script_id)}", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    async def download_script(
        self,
        *,
        script_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Download the file backing a scripts-library entry.

        ``GET /api/endpoint/scripts_library/{script_id}/download``

        The response body is the raw script/archive file content.

        Args:
            script_id: The ID of the script to download.
            space_id: Optional space ID to scope the request to.
            validate_spaces: Override space validation for this operation.

        Returns:
            Response whose ``body`` is the raw file content (the exact type
            depends on the uploaded file: text scripts come back as ``str``,
            binary archives as ``bytes``).

        Raises:
            NotFoundError: If the script does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> resp = await client.endpoint.download_script(script_id="script-id-1")
            >>> open("script.sh", "wb").write(
            ...     resp.body if isinstance(resp.body, bytes)
            ...     else resp.body.encode()
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/endpoint/scripts_library/{_quote(script_id)}/download", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/octet-stream"},
        )
