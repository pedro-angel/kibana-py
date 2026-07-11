"""Async Kibana Synthetics API client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class AsyncSyntheticsClient(AsyncNamespaceClient):
    """Async client for the Kibana Synthetics API.

    Synthetics periodically checks the status of your services and
    applications from lightweight (HTTP, TCP, ICMP) and browser monitors.
    This client manages monitors, global parameters, and private locations,
    and can trigger on-demand test runs.

    All Synthetics resources are space-scoped: every method accepts an
    optional ``space_id`` to target a specific space (``None`` targets the
    default space or the space the client is scoped to).

    Note:
        Creating a monitor requires at least one location: either an Elastic
        managed location (cloud) or a private location. Private locations
        are backed by a Fleet agent policy (``agent_policy_id``).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a private location, then an HTTP monitor using it
        >>> loc = await client.synthetics.create_private_location(
        ...     label="My private location",
        ...     agent_policy_id="abc-123",
        ... )
        >>> monitor = await client.synthetics.create_monitor(
        ...     type="http",
        ...     name="My monitor",
        ...     url="https://example.com",
        ...     private_locations=[loc.body["id"]],
        ... )
        >>> await client.synthetics.delete_monitor(id=monitor.body["id"])
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncSyntheticsClient.

        Args:
            client: The parent AsyncKibana client instance to delegate
                requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> synthetics_client = AsyncSyntheticsClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    @staticmethod
    def _build_monitor_body(
        *,
        type: str | None,
        name: str | None,
        url: str | None,
        host: str | None,
        inline_script: str | None,
        locations: list[str] | None,
        private_locations: list[str] | None,
        schedule: dict[str, Any] | None,
        enabled: bool | None,
        tags: list[str] | None,
        alert: dict[str, Any] | None,
        labels: dict[str, str] | None,
        namespace: str | None,
        params: dict[str, Any] | None,
        retest_on_failure: bool | None,
        service_name: str | None,
        timeout: int | str | None,
        fields: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Assemble a monitor request body from common keyword arguments."""
        body: dict[str, Any] = {}
        if type is not None:
            body["type"] = type
        if name is not None:
            body["name"] = name
        if url is not None:
            body["url"] = url
        if host is not None:
            body["host"] = host
        if inline_script is not None:
            body["inline_script"] = inline_script
        if locations is not None:
            body["locations"] = locations
        if private_locations is not None:
            body["private_locations"] = private_locations
        if schedule is not None:
            body["schedule"] = schedule
        if enabled is not None:
            body["enabled"] = enabled
        if tags is not None:
            body["tags"] = tags
        if alert is not None:
            body["alert"] = alert
        if labels is not None:
            body["labels"] = labels
        if namespace is not None:
            body["namespace"] = namespace
        if params is not None:
            body["params"] = params
        if retest_on_failure is not None:
            body["retest_on_failure"] = retest_on_failure
        if service_name is not None:
            body["service.name"] = service_name
        if timeout is not None:
            body["timeout"] = timeout
        if fields:
            body.update(fields)
        return body

    # ----------------------------------------------------------------- #
    # Monitors                                                           #
    # ----------------------------------------------------------------- #

    async def get_monitors(
        self,
        *,
        filter: str | None = None,
        locations: str | list[str] | None = None,
        monitor_types: str | list[str] | None = None,
        page: int | None = None,
        per_page: int | None = None,
        projects: str | list[str] | None = None,
        query: str | None = None,
        schedules: str | list[str] | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        status: str | list[str] | None = None,
        tags: str | list[str] | None = None,
        use_logical_and_for: str | list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get monitors.

        Get a paginated list of synthetics monitors, optionally filtered by
        type, location, tags, project, schedule or status.

        Args:
            filter: Additional filtering criteria (KQL-style filter string).
            locations: The location IDs to filter by.
            monitor_types: The monitor types to filter by (``http``, ``tcp``,
                ``icmp``, ``browser``).
            page: The page number for paginated results.
            per_page: The number of monitors to return per page. Sent to the
                server as ``perPage`` (the documented ``per_page`` name is
                rejected by Kibana 9.4.3).
            projects: The project IDs to filter by.
            query: A free-text query string.
            schedules: The schedules (in minutes) to filter by.
            sort_field: The field to sort by. Kibana 9.4.3 accepts
                ``enabled``, ``status``, ``updated_at``, ``name.keyword``,
                ``tags.keyword``, ``project_id.keyword``, ``type.keyword``,
                ``schedule.keyword`` and ``journey_id`` (the documented
                ``name``/``createdAt``/``updatedAt`` values are rejected).
            sort_order: The sort order: ``asc`` or ``desc``.
            status: The monitor status to filter by (``up``, ``down``).
            tags: Tags to filter monitors by.
            use_logical_and_for: Fields (``tags``, ``locations``) that should
                be combined with logical AND instead of OR.
            space_id: Optional space ID to list monitors from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``monitors`` (list of monitor objects),
            ``page``, ``perPage``, ``total``, ``absoluteTotal`` and
            ``syncErrors``.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> response = await client.synthetics.get_monitors(
            ...     monitor_types="http", per_page=10
            ... )
            >>> for monitor in response.body["monitors"]:
            ...     print(monitor["name"])
        """
        query_params: dict[str, Any] = {}
        if filter is not None:
            query_params["filter"] = filter
        if locations is not None:
            query_params["locations"] = locations
        if monitor_types is not None:
            query_params["monitorTypes"] = monitor_types
        if page is not None:
            query_params["page"] = page
        if per_page is not None:
            query_params["perPage"] = per_page
        if projects is not None:
            query_params["projects"] = projects
        if query is not None:
            query_params["query"] = query
        if schedules is not None:
            query_params["schedules"] = schedules
        if sort_field is not None:
            query_params["sortField"] = sort_field
        if sort_order is not None:
            query_params["sortOrder"] = sort_order
        if status is not None:
            query_params["status"] = status
        if tags is not None:
            query_params["tags"] = tags
        if use_logical_and_for is not None:
            query_params["useLogicalAndFor"] = use_logical_and_for

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/synthetics/monitors", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=query_params or None,
            headers={"accept": "application/json"},
        )

    async def get_monitor(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a monitor.

        Get a synthetics monitor by config ID.

        Args:
            id: The config ID of the monitor.
            space_id: Optional space ID to get the monitor from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the full monitor object (``id``, ``name``,
            ``type``, ``locations``, ``schedule``, ``enabled``, type-specific
            fields such as ``url`` or ``host``, and audit metadata).

        Raises:
            NotFoundError: If no monitor exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> monitor = await client.synthetics.get_monitor(id="d4ba9d2f-...")
            >>> print(monitor.body["name"], monitor.body["type"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/synthetics/monitors/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def create_monitor(
        self,
        *,
        type: str,
        name: str,
        url: str | None = None,
        host: str | None = None,
        inline_script: str | None = None,
        locations: list[str] | None = None,
        private_locations: list[str] | None = None,
        schedule: dict[str, Any] | None = None,
        enabled: bool | None = None,
        tags: list[str] | None = None,
        alert: dict[str, Any] | None = None,
        labels: dict[str, str] | None = None,
        namespace: str | None = None,
        params: dict[str, Any] | None = None,
        retest_on_failure: bool | None = None,
        service_name: str | None = None,
        timeout: int | str | None = None,
        fields: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a monitor.

        Create a synthetics monitor of type ``http``, ``tcp``, ``icmp`` or
        ``browser``. The required type-specific field differs per type:
        ``url`` for HTTP monitors, ``host`` for TCP and ICMP monitors, and
        ``inline_script`` for browser monitors. At least one location is
        required, either Elastic managed (``locations``) or private
        (``private_locations``).

        Args:
            type: The monitor type: ``http``, ``tcp``, ``icmp`` or
                ``browser``.
            name: The monitor's name.
            url: The URL to monitor (required for ``http`` monitors).
            host: The host to ping or connect to (required for ``icmp`` and
                ``tcp`` monitors; may include the port, e.g.
                ``"example.com:443"``, for TCP).
            inline_script: The inline playwright script to run (required for
                ``browser`` monitors).
            locations: Elastic managed locations the monitor runs from.
            private_locations: Private location IDs or labels the monitor
                runs from.
            schedule: The monitor's schedule in minutes, for example
                ``{"number": "5", "unit": "m"}``.
            enabled: Whether the monitor is enabled (default ``True`` on the
                server).
            tags: An array of tags.
            alert: Alert configuration, for example
                ``{"status": {"enabled": True}, "tls": {"enabled": True}}``.
            labels: Custom key-value label pairs to add to the monitor.
            namespace: The data-stream namespace (defaults to the space
                name).
            params: Monitor variables available to the monitor's checks.
            retest_on_failure: Whether the monitor is retested on failure.
            service_name: The APM service name to associate with the monitor
                (sent as ``service.name``).
            timeout: Time in seconds before a check is considered failed.
            fields: Additional type-specific fields merged into the request
                body verbatim (for example ``{"max_redirects": 3}``,
                ``{"ssl.verification_mode": "none"}``,
                ``{"check": {"request": {"method": "POST"}}}``).
            space_id: Optional space ID to create the monitor in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created monitor, including its
            generated ``id``/``config_id`` and the resolved locations.

        Raises:
            BadRequestError: If the monitor definition is invalid or no
                location was provided.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> monitor = await client.synthetics.create_monitor(
            ...     type="http",
            ...     name="Example HTTP monitor",
            ...     url="https://example.com",
            ...     private_locations=["my-private-location-id"],
            ...     schedule={"number": "10", "unit": "m"},
            ...     tags=["example"],
            ... )
            >>> print(monitor.body["id"])
        """
        body = self._build_monitor_body(
            type=type,
            name=name,
            url=url,
            host=host,
            inline_script=inline_script,
            locations=locations,
            private_locations=private_locations,
            schedule=schedule,
            enabled=enabled,
            tags=tags,
            alert=alert,
            labels=labels,
            namespace=namespace,
            params=params,
            retest_on_failure=retest_on_failure,
            service_name=service_name,
            timeout=timeout,
            fields=fields,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/synthetics/monitors", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def update_monitor(
        self,
        *,
        id: str,
        type: str | None = None,
        name: str | None = None,
        url: str | None = None,
        host: str | None = None,
        inline_script: str | None = None,
        locations: list[str] | None = None,
        private_locations: list[str] | None = None,
        schedule: dict[str, Any] | None = None,
        enabled: bool | None = None,
        tags: list[str] | None = None,
        alert: dict[str, Any] | None = None,
        labels: dict[str, str] | None = None,
        namespace: str | None = None,
        params: dict[str, Any] | None = None,
        retest_on_failure: bool | None = None,
        service_name: str | None = None,
        timeout: int | str | None = None,
        fields: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a monitor.

        Update a synthetics monitor with a partial set of attributes; fields
        that are not provided keep their current values. The spec documents
        ``type`` as required in the request body, but Kibana 9.4.3 accepts
        partial updates without it.

        Args:
            id: The config ID of the monitor to update.
            type: The monitor type (``http``, ``tcp``, ``icmp`` or
                ``browser``). The type of an existing monitor cannot be
                changed.
            name: The monitor's name.
            url: The URL to monitor (``http`` monitors).
            host: The host to ping or connect to (``icmp``/``tcp`` monitors).
            inline_script: The inline playwright script (``browser``
                monitors).
            locations: Elastic managed locations the monitor runs from.
            private_locations: Private location IDs or labels the monitor
                runs from.
            schedule: The monitor's schedule, e.g.
                ``{"number": "5", "unit": "m"}``.
            enabled: Whether the monitor is enabled.
            tags: An array of tags.
            alert: Alert configuration.
            labels: Custom key-value label pairs.
            namespace: The data-stream namespace.
            params: Monitor variables.
            retest_on_failure: Whether the monitor is retested on failure.
            service_name: The APM service name (sent as ``service.name``).
            timeout: Time in seconds before a check is considered failed.
            fields: Additional type-specific fields merged into the request
                body verbatim.
            space_id: Optional space ID the monitor lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the updated monitor object.

        Raises:
            NotFoundError: If no monitor exists with the given ID.
            BadRequestError: If the update payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> updated = await client.synthetics.update_monitor(
            ...     id="d4ba9d2f-...",
            ...     name="Renamed monitor",
            ...     tags=["updated"],
            ... )
            >>> print(updated.body["name"])
            Renamed monitor
        """
        body = self._build_monitor_body(
            type=type,
            name=name,
            url=url,
            host=host,
            inline_script=inline_script,
            locations=locations,
            private_locations=private_locations,
            schedule=schedule,
            enabled=enabled,
            tags=tags,
            alert=alert,
            labels=labels,
            namespace=namespace,
            params=params,
            retest_on_failure=retest_on_failure,
            service_name=service_name,
            timeout=timeout,
            fields=fields,
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/synthetics/monitors/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_monitor(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a monitor.

        Delete a synthetics monitor by config ID.

        Args:
            id: The config ID of the monitor to delete.
            space_id: Optional space ID the monitor lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ApiResponse with a list of deletion results, for example
            ``[{"id": "...", "deleted": true}]``.

        Raises:
            NotFoundError: If no monitor exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.synthetics.delete_monitor(id="d4ba9d2f-...")
            >>> print(result.body[0]["deleted"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/synthetics/monitors/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    async def bulk_delete_monitors(
        self,
        *,
        ids: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete monitors.

        Delete multiple synthetics monitors by their config IDs in a single
        request.

        Args:
            ids: The config IDs of the monitors to delete.
            space_id: Optional space ID the monitors live in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with a ``result`` list; each entry contains
            ``id``, ``deleted`` and, for monitors that could not be deleted,
            an ``error`` message.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.synthetics.bulk_delete_monitors(
            ...     ids=["id-1", "id-2"]
            ... )
            >>> for item in result.body["result"]:
            ...     print(item["id"], item["deleted"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/synthetics/monitors/_bulk_delete", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"ids": ids},
        )

    async def test_monitor(
        self,
        *,
        monitor_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Trigger an on-demand test run for a monitor.

        Trigger a one-off test run for an existing monitor without waiting
        for its schedule. The monitor must have at least one location with a
        running agent for the test to actually execute. Generally available
        since 9.2.0.

        Args:
            monitor_id: The config ID of the monitor to test.
            space_id: Optional space ID the monitor lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the ``testRunId`` of the triggered run.

        Raises:
            NotFoundError: If no monitor exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> run = await client.synthetics.test_monitor(monitor_id="d4ba9d2f-...")
            >>> print(run.body["testRunId"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/synthetics/monitor/test/{_quote(monitor_id)}",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Global parameters                                                  #
    # ----------------------------------------------------------------- #

    async def get_params(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get parameters.

        Get all synthetics global parameters visible in the space. Parameter
        values are redacted unless the user has the proper read privileges.

        Args:
            space_id: Optional space ID to list parameters from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ApiResponse with a list of parameter objects (``id``, ``key``,
            ``description``, ``tags``, ``namespaces``).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> response = await client.synthetics.get_params()
            >>> for param in response.body:
            ...     print(param["key"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/synthetics/params", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_param(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a parameter.

        Get a synthetics global parameter by ID.

        Args:
            id: The ID of the parameter.
            space_id: Optional space ID to get the parameter from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the parameter (``id``, ``key``,
            ``description``, ``tags``, ``namespaces``).

        Raises:
            NotFoundError: If no parameter exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> param = await client.synthetics.get_param(id="a1b2c3")
            >>> print(param.body["key"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/synthetics/params/{_quote(id)}", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def create_param(
        self,
        *,
        key: str,
        value: str,
        description: str | None = None,
        tags: list[str] | None = None,
        share_across_spaces: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Add a parameter.

        Create a single synthetics global parameter that can be referenced
        by monitors.

        Args:
            key: The key of the parameter.
            value: The value associated with the parameter.
            description: A description of the parameter.
            tags: An array of tags to categorize the parameter.
            share_across_spaces: Whether the parameter should be shared
                across spaces.
            space_id: Optional space ID to create the parameter in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created parameter (``id``, ``key``,
            ``description``, ``tags``, ``namespaces``).

        Raises:
            BadRequestError: If the parameter definition is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> param = await client.synthetics.create_param(
            ...     key="my-api-token",
            ...     value="s3cret",
            ...     description="Token used by browser monitors",
            ... )
            >>> print(param.body["id"])
        """
        body: dict[str, Any] = {"key": key, "value": value}
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags
        if share_across_spaces is not None:
            body["share_across_spaces"] = share_across_spaces

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/synthetics/params", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def bulk_create_params(
        self,
        *,
        parameters: list[dict[str, Any]],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Add multiple parameters.

        Create several synthetics global parameters in a single request.
        Each entry must contain at least ``key`` and ``value`` and may also
        contain ``description``, ``tags`` and ``share_across_spaces``.

        Args:
            parameters: A list of parameter objects to create.
            space_id: Optional space ID to create the parameters in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ApiResponse with the list of created parameters (``id``,
            ``key``, ``namespaces``).

        Raises:
            BadRequestError: If a parameter definition is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> created = await client.synthetics.bulk_create_params(
            ...     parameters=[
            ...         {"key": "username", "value": "admin"},
            ...         {"key": "password", "value": "changeme"},
            ...     ]
            ... )
            >>> print(len(created.body))
            2
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/synthetics/params", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=parameters,  # type: ignore[arg-type]
        )

    async def update_param(
        self,
        *,
        id: str,
        key: str | None = None,
        value: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a parameter.

        Update a synthetics global parameter. Only the provided fields are
        changed.

        Note:
            Kibana 9.4.3 applies a new ``value`` but echoes the previously
            stored value in the response body (the ``value`` field is
            encrypted at rest and is not re-read after the write). A
            subsequent request reflects the new value.

        Args:
            id: The ID of the parameter to update.
            key: The new key of the parameter.
            value: The new value associated with the parameter.
            description: The new description of the parameter.
            tags: An array of updated tags to categorize the parameter.
            space_id: Optional space ID the parameter lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the updated parameter.

        Raises:
            NotFoundError: If no parameter exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> updated = await client.synthetics.update_param(
            ...     id="a1b2c3", description="Rotated 2026-07"
            ... )
            >>> print(updated.body["description"])
            Rotated 2026-07
        """
        body: dict[str, Any] = {}
        if key is not None:
            body["key"] = key
        if value is not None:
            body["value"] = value
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/synthetics/params/{_quote(id)}", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_param(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a parameter.

        Delete a synthetics global parameter by ID.

        Args:
            id: The ID of the parameter to delete.
            space_id: Optional space ID the parameter lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ApiResponse with a list of deletion results, for example
            ``[{"id": "...", "deleted": true}]``.

        Raises:
            NotFoundError: If no parameter exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.synthetics.delete_param(id="a1b2c3")
            >>> print(result.body[0]["deleted"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/synthetics/params/{_quote(id)}", space_id)
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    async def bulk_delete_params(
        self,
        *,
        ids: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete parameters.

        Delete multiple synthetics global parameters by ID in a single
        request.

        Args:
            ids: The IDs of the parameters to delete.
            space_id: Optional space ID the parameters live in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ApiResponse with a list of deletion results, for example
            ``[{"id": "...", "deleted": true}]``.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = await client.synthetics.bulk_delete_params(
            ...     ids=["id-1", "id-2"]
            ... )
            >>> print([item["deleted"] for item in result.body])
            [True, True]
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/synthetics/params/_bulk_delete", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"ids": ids},
        )

    # ----------------------------------------------------------------- #
    # Private locations                                                  #
    # ----------------------------------------------------------------- #

    async def get_private_locations(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get private locations.

        Get all synthetics private locations visible in the space.

        Args:
            space_id: Optional space ID to list private locations from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ApiResponse with a list of private location objects (``id``,
            ``label``, ``agentPolicyId``, ``isInvalid``, ``tags``, ``geo``,
            ``spaces``).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> response = await client.synthetics.get_private_locations()
            >>> for location in response.body:
            ...     print(location["label"], location["id"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/synthetics/private_locations", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_private_location(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a private location.

        Get a synthetics private location by ID or label.

        Args:
            id: The ID or label of the private location.
            space_id: Optional space ID to get the private location from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the private location (``id``, ``label``,
            ``agentPolicyId``, ``isInvalid``, ``tags``, ``geo``, ``spaces``).

        Raises:
            NotFoundError: If no private location exists with the given ID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> location = await client.synthetics.get_private_location(
            ...     id="e3134290-..."
            ... )
            >>> print(location.body["label"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/synthetics/private_locations/{_quote(id)}",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def create_private_location(
        self,
        *,
        label: str,
        agent_policy_id: str,
        tags: list[str] | None = None,
        geo: dict[str, float] | None = None,
        spaces: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a private location.

        Create a synthetics private location backed by a Fleet agent policy.
        Monitors assigned to the location run from Elastic Agents enrolled
        in that policy.

        Args:
            label: A label for the private location.
            agent_policy_id: The ID of the Fleet agent policy associated
                with the private location.
            tags: An array of tags to categorize the private location.
            geo: Geographic coordinates (WGS84) for the location, e.g.
                ``{"lat": 40.4, "lon": -3.7}``.
            spaces: Space IDs where the private location is available. If
                not provided, the private location is available in all
                spaces.
            space_id: Optional space ID to create the private location in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created private location (``id``,
            ``label``, ``agentPolicyId``, ``isServiceManaged``,
            ``isInvalid``, ``tags``, ``geo``, ``spaces``).

        Raises:
            BadRequestError: If the definition is invalid, the agent policy
                does not exist, or the agent policy is already used by
                another private location.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> location = await client.synthetics.create_private_location(
            ...     label="Madrid DC",
            ...     agent_policy_id="abc-123",
            ...     geo={"lat": 40.4, "lon": -3.7},
            ... )
            >>> print(location.body["id"])
        """
        body: dict[str, Any] = {
            "label": label,
            "agentPolicyId": agent_policy_id,
        }
        if tags is not None:
            body["tags"] = tags
        if geo is not None:
            body["geo"] = geo
        if spaces is not None:
            body["spaces"] = spaces

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/synthetics/private_locations", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def update_private_location(
        self,
        *,
        id: str,
        label: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a private location.

        Update the label of a synthetics private location. The label is the
        only editable attribute.

        Args:
            id: The ID of the private location to update.
            label: A new label for the private location (at least 1
                character long).
            space_id: Optional space ID the private location lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the updated private location.

        Raises:
            NotFoundError: If no private location exists with the given ID.
            BadRequestError: If the label is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> updated = await client.synthetics.update_private_location(
            ...     id="e3134290-...", label="Madrid DC (rack 2)"
            ... )
            >>> print(updated.body["label"])
            Madrid DC (rack 2)
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/synthetics/private_locations/{_quote(id)}",
            space_id,
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body={"label": label},
        )

    async def delete_private_location(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a private location.

        Delete a synthetics private location by ID. A location that still
        has monitors assigned to it cannot be deleted; delete or reassign
        the monitors first.

        Args:
            id: The ID of the private location to delete.
            space_id: Optional space ID the private location lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty body on success.

        Raises:
            NotFoundError: If no private location exists with the given ID.
            BadRequestError: If monitors are still assigned to the location.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> await client.synthetics.delete_private_location(id="e3134290-...")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/synthetics/private_locations/{_quote(id)}",
            space_id,
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )
