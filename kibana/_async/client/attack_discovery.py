"""Async Kibana Security Attack Discovery API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class AsyncAttackDiscoveryClient(AsyncNamespaceClient):
    """Async client for the Kibana Security Attack Discovery API.

    Attack discovery uses AI (via a Kibana Gen AI connector) to analyze
    security alerts and surface potential attack chains as "Attack
    discoveries". This client covers the full 9.4 public surface:

    - ad-hoc discovery generation (``generate``), retrieval (``find``) and
      bulk workflow-status/visibility updates (``bulk_update``),
    - generation runs metadata (``get_generations``, ``get_generation``,
      ``dismiss_generation``),
    - Attack Discovery schedules CRUD plus enable/disable and search
      (``create_schedule``, ``get_schedule``, ``update_schedule``,
      ``delete_schedule``, ``enable_schedule``, ``disable_schedule``,
      ``find_schedules``).

    All Attack Discovery resources are space-scoped: every method accepts an
    optional ``space_id`` to target a specific space (``None`` targets the
    default space or the space the client is scoped to).

    Note:
        The Attack Discovery Kibana feature must be enabled in the target
        space. Spaces using the pure Elasticsearch solution view (for
        example, a default space created with ``solution: "es"``) disable
        the ``securitySolutionAttackDiscovery`` feature: in such spaces
        ``find_schedules`` returns ``total: 0`` even though schedule
        create/get/update/delete/enable/disable still work. Use a space with
        the security solution view (or the classic view) for full
        functionality.

    Note:
        For OpenAI-compatible connectors (``.gen-ai``), the connector's
        ``apiUrl`` must be the *full* chat-completions endpoint (for example
        ``http://localhost:1234/v1/chat/completions``), not just the API
        base URL.

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Kick off an ad-hoc generation with a Gen AI connector
        >>> resp = await client.attack_discovery.generate(
        ...     alerts_index_pattern=".alerts-security.alerts-default",
        ...     anonymization_fields=[
        ...         {"id": "f1", "field": "_id", "allowed": True, "anonymized": False},
        ...         {"id": "f2", "field": "host.name", "allowed": True, "anonymized": True},
        ...     ],
        ...     api_config={"actionTypeId": ".gen-ai", "connectorId": "my-connector"},
        ...     size=25,
        ... )
        >>> execution_uuid = resp.body["execution_uuid"]
        >>>
        >>> # Poll the generation until it completes
        >>> gen = await client.attack_discovery.get_generation(execution_uuid=execution_uuid)
        >>> print(gen.body["generation"]["status"])
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncAttackDiscoveryClient.

        Args:
            client: The parent AsyncKibana client instance to delegate
                requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> attack_discovery_client = AsyncAttackDiscoveryClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    # ----------------------------------------------------------------- #
    # Attack discoveries (ad-hoc)                                        #
    # ----------------------------------------------------------------- #

    async def find(
        self,
        *,
        alert_ids: list[str] | None = None,
        connector_names: list[str] | None = None,
        enable_field_rendering: bool | None = None,
        end: str | None = None,
        ids: list[str] | None = None,
        include_unique_alert_ids: bool | None = None,
        page: int | None = None,
        per_page: int | None = None,
        search: str | None = None,
        scheduled: bool | None = None,
        shared: bool | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        start: str | None = None,
        status: list[str] | None = None,
        with_replacements: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Find Attack discoveries that match the search criteria.

        Supports free text search, filtering, pagination, and sorting
        (``GET /api/attack_discovery/_find``).

        Args:
            alert_ids: Filter results to Attack discoveries that include any
                of the provided alert IDs.
            connector_names: Filter results to Attack discoveries created by
                any of the provided human readable connector names (the
                ``connector_name`` property, e.g. ``"GPT-5 Chat"``), which
                are distinct from ``connector_id`` values.
            enable_field_rendering: Enables a markdown syntax used to render
                pivot fields, for example ``{{ user.name james }}``. Defaults
                to ``False`` on the server.
            end: End of the time range for the search. Accepts absolute
                timestamps (ISO 8601) or relative date math (e.g. ``"now"``).
            ids: Filter results to the Attack discoveries with the specified
                IDs.
            include_unique_alert_ids: If True, the response includes
                ``unique_alert_ids`` and ``unique_alert_ids_count``
                aggregated across the matched Attack discoveries.
            page: Page number to return. Defaults to 1 on the server.
            per_page: Number of Attack discoveries per page. Defaults to 10
                on the server.
            search: Free-text search query applied to relevant text fields
                (title, description, tags, etc.).
            scheduled: Use True to return only scheduled discoveries, False
                for only ad-hoc discoveries; omit for both.
            shared: Use True to return only shared discoveries, False for
                only those visible to the current user; omit for both.
            sort_field: Field used to sort results. In 9.4 only
                ``"@timestamp"`` is allowed.
            sort_order: Sort direction, ``"asc"`` or ``"desc"`` (server
                default ``"desc"``).
            start: Start of the time range for the search (ISO 8601 or date
                math such as ``"now-24h"``).
            status: Filter by alert workflow status; one or more of
                ``"open"``, ``"acknowledged"``, ``"closed"``.
            with_replacements: When True, returns discoveries with text
                replacements applied to the detailsMarkdown,
                entitySummaryMarkdown, summaryMarkdown, and title fields.
                Defaults to ``True`` on the server.
            space_id: Optional space ID to search in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``connector_names``, ``data`` (list
            of Attack discovery alerts), ``page``, ``per_page``, ``total``
            and ``unique_alert_ids_count``.

        Raises:
            BadRequestError: If the query parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.attack_discovery.find(
            ...     start="now-24h", end="now", status=["open"], per_page=10
            ... )
            >>> print(found.body["total"])
        """
        params: dict[str, Any] = {}
        if alert_ids is not None:
            params["alert_ids"] = alert_ids
        if connector_names is not None:
            params["connector_names"] = connector_names
        if enable_field_rendering is not None:
            params["enable_field_rendering"] = enable_field_rendering
        if end is not None:
            params["end"] = end
        if ids is not None:
            params["ids"] = ids
        if include_unique_alert_ids is not None:
            params["include_unique_alert_ids"] = include_unique_alert_ids
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if search is not None:
            params["search"] = search
        if scheduled is not None:
            params["scheduled"] = scheduled
        if shared is not None:
            params["shared"] = shared
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order
        if start is not None:
            params["start"] = start
        if status is not None:
            params["status"] = status
        if with_replacements is not None:
            params["with_replacements"] = with_replacements

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/attack_discovery/_find", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    async def bulk_update(
        self,
        *,
        ids: list[str],
        enable_field_rendering: bool | None = None,
        kibana_alert_workflow_status: str | None = None,
        visibility: str | None = None,
        with_replacements: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk update Attack discoveries.

        Performs bulk updates on multiple Attack discoveries, including
        workflow status changes and visibility settings, without requiring
        individual API calls for each alert
        (``POST /api/attack_discovery/_bulk``).

        Args:
            ids: Array of Attack Discovery IDs to update.
            enable_field_rendering: Enables a markdown syntax used to render
                pivot fields, for example ``{{ user.name james }}``. Defaults
                to ``False`` on the server.
            kibana_alert_workflow_status: When provided, updates the
                ``kibana.alert.workflow_status`` of the attack discovery
                alerts; one of ``"open"``, ``"acknowledged"``, ``"closed"``.
            visibility: When provided, updates the visibility of the alert;
                one of ``"not_shared"``, ``"shared"``.
            with_replacements: When True, returns the updated discoveries
                with text replacements applied. Defaults to ``True`` on the
                server.
            space_id: Optional space ID to update discoveries in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``data``: the array of updated Attack
            Discovery alert objects. IDs that match no existing discovery
            are silently ignored (the live server returns ``{"data": []}``
            rather than an error).

        Raises:
            BadRequestError: If the request parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.attack_discovery.bulk_update(
            ...     ids=["c0c8a8bb..."],
            ...     kibana_alert_workflow_status="acknowledged",
            ... )
            >>> print(len(updated.body["data"]))
        """
        update: dict[str, Any] = {"ids": ids}
        if enable_field_rendering is not None:
            update["enable_field_rendering"] = enable_field_rendering
        if kibana_alert_workflow_status is not None:
            update["kibana_alert_workflow_status"] = kibana_alert_workflow_status
        if visibility is not None:
            update["visibility"] = visibility
        if with_replacements is not None:
            update["with_replacements"] = with_replacements

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/attack_discovery/_bulk", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"update": update},
        )

    async def generate(
        self,
        *,
        alerts_index_pattern: str,
        anonymization_fields: list[dict[str, Any]],
        api_config: dict[str, Any],
        size: int,
        sub_action: str = "invokeAI",
        connector_name: str | None = None,
        end: str | None = None,
        filter: dict[str, Any] | None = None,
        model: str | None = None,
        replacements: dict[str, str] | None = None,
        start: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Generate attack discoveries from alerts.

        Initiates the generation of attack discoveries by analyzing security
        alerts using AI. Returns an execution UUID that can be used to track
        the generation progress and retrieve results
        (``POST /api/attack_discovery/_generate``). Results may also be
        retrieved via :meth:`find`.

        Note:
            The ``_id`` field must be present (and ``allowed``) in
            ``anonymization_fields``; otherwise the generation fails with
            "The _id field must be allowed to generate Attack discoveries."
            The alerts index is sorted on ``kibana.alert.risk_score``, so a
            custom index pattern must have a mapping for that field.

        Args:
            alerts_index_pattern: The (space specific) index pattern that
                contains the alerts to use as context, e.g.
                ``".alerts-security.alerts-default"``.
            anonymization_fields: The list of fields, and whether or not they
                are anonymized, allowed to be sent to LLMs. Each entry has
                ``id``, ``field``, ``allowed`` and ``anonymized`` keys.
                Consider using the output of the
                ``/api/security_ai_assistant/anonymization_fields/_find`` API.
            api_config: LLM API configuration with required ``connectorId``
                and ``actionTypeId`` keys (optionally ``model``,
                ``provider``, ``defaultSystemPromptId``).
            size: The maximum number of alerts to analyze.
            sub_action: LLM invocation mode, ``"invokeAI"`` (default) or
                ``"invokeStream"``.
            connector_name: Optional human readable connector name recorded
                on the generation.
            end: End of the alert time range (ISO 8601 or date math, e.g.
                ``"now"``).
            filter: An Elasticsearch query DSL object used to filter alerts.
            model: Optional model override.
            replacements: Optional anonymization replacements mapping
                (anonymized value -> original value).
            start: Start of the alert time range (e.g. ``"now-24h"``).
            space_id: Optional space ID to generate discoveries in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``execution_uuid``: the identifier for
            the attack discovery generation process, usable with
            :meth:`get_generation` and :meth:`dismiss_generation`.

        Raises:
            BadRequestError: If the generation configuration is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> resp = await client.attack_discovery.generate(
            ...     alerts_index_pattern=".alerts-security.alerts-default",
            ...     anonymization_fields=[
            ...         {"id": "f1", "field": "_id", "allowed": True,
            ...          "anonymized": False},
            ...     ],
            ...     api_config={
            ...         "actionTypeId": ".gen-ai",
            ...         "connectorId": "my-connector-id",
            ...     },
            ...     size=25,
            ...     start="now-24h",
            ...     end="now",
            ... )
            >>> print(resp.body["execution_uuid"])
        """
        body: dict[str, Any] = {
            "alertsIndexPattern": alerts_index_pattern,
            "anonymizationFields": anonymization_fields,
            "apiConfig": api_config,
            "size": size,
            "subAction": sub_action,
        }
        if connector_name is not None:
            body["connectorName"] = connector_name
        if end is not None:
            body["end"] = end
        if filter is not None:
            body["filter"] = filter
        if model is not None:
            body["model"] = model
        if replacements is not None:
            body["replacements"] = replacements
        if start is not None:
            body["start"] = start

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/attack_discovery/_generate", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ----------------------------------------------------------------- #
    # Generations                                                        #
    # ----------------------------------------------------------------- #

    async def get_generations(
        self,
        *,
        end: str | None = None,
        size: int | None = None,
        start: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the latest Attack Discovery generations metadata.

        Retrieves generation metadata for the current user, including
        execution status and statistics
        (``GET /api/attack_discovery/generations``).

        Args:
            end: End of the time range for filtering generations (ISO 8601
                or date math, e.g. ``"now"``).
            size: The maximum number of generations to retrieve (server
                default 50).
            start: Start of the time range for filtering generations (e.g.
                ``"now-24h"``).
            space_id: Optional space ID to list generations from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``generations``: a list of generation
            metadata objects (``execution_uuid``, ``status``,
            ``connector_id``, ``discoveries``, timing fields, ...). Note:
            despite the API description, on a live 9.4.3 server dismissed
            generations are still listed, with ``status: "dismissed"``.

        Raises:
            BadRequestError: If the query parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> gens = client.attack_discovery.get_generations(size=10)
            >>> for g in gens.body["generations"]:
            ...     print(g["execution_uuid"], g["status"])
        """
        params: dict[str, Any] = {}
        if end is not None:
            params["end"] = end
        if size is not None:
            params["size"] = size
        if start is not None:
            params["start"] = start

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/attack_discovery/generations", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    async def get_generation(
        self,
        *,
        execution_uuid: str,
        enable_field_rendering: bool | None = None,
        with_replacements: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a single Attack Discovery generation.

        Returns a specific generation, including all generated Attack
        discoveries and associated metadata such as execution status and
        statistics
        (``GET /api/attack_discovery/generations/{execution_uuid}``).

        Args:
            execution_uuid: The unique identifier for the generation
                execution, as returned by :meth:`generate`.
            enable_field_rendering: Enables a markdown syntax used to render
                pivot fields, for example ``{{ user.name james }}``. Defaults
                to ``False`` on the server.
            with_replacements: When True, returns discoveries with text
                replacements applied. Defaults to ``True`` on the server.
            space_id: Optional space ID to get the generation from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``generation`` (metadata including
            ``status``: one of ``started``, ``succeeded``, ``failed``,
            ``dismissed``, ``canceled``) and ``data`` (the generated Attack
            discoveries).

        Raises:
            NotFoundError: If no generation exists for the execution UUID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> gen = await client.attack_discovery.get_generation(
            ...     execution_uuid="edd26039-0990-4d9f-9829-2a1fcacb77b5"
            ... )
            >>> print(gen.body["generation"]["status"])
        """
        params: dict[str, Any] = {}
        if enable_field_rendering is not None:
            params["enable_field_rendering"] = enable_field_rendering
        if with_replacements is not None:
            params["with_replacements"] = with_replacements

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/attack_discovery/generations/{_quote(execution_uuid)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )

    async def dismiss_generation(
        self,
        *,
        execution_uuid: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Dismiss an Attack Discovery generation.

        Marks a generation as dismissed for the current user
        (``POST /api/attack_discovery/generations/{execution_uuid}/_dismiss``).

        Args:
            execution_uuid: The unique identifier for the generation
                execution, as returned by :meth:`generate`.
            space_id: Optional space ID the generation belongs to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the (dismissed) generation metadata
            object. The updated ``dismissed`` status becomes visible in
            :meth:`get_generations` shortly after (event-log refresh).

        Raises:
            NotFoundError: If no generation exists for the execution UUID.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.attack_discovery.dismiss_generation(
            ...     execution_uuid="edd26039-0990-4d9f-9829-2a1fcacb77b5"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/attack_discovery/generations/{_quote(execution_uuid)}/_dismiss",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    # ----------------------------------------------------------------- #
    # Schedules                                                          #
    # ----------------------------------------------------------------- #

    async def create_schedule(
        self,
        *,
        name: str,
        params: dict[str, Any],
        schedule: dict[str, Any],
        actions: list[dict[str, Any]] | None = None,
        enabled: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an Attack Discovery schedule.

        Creates a schedule that periodically generates attack discoveries
        (``POST /api/attack_discovery/schedules``). A schedule is backed by
        an alerting rule of type ``attack-discovery``.

        Args:
            name: The name of the schedule.
            params: The schedule configuration parameters. Required keys:
                ``alerts_index_pattern`` (index pattern to get alerts from),
                ``api_config`` (LLM configuration with ``connectorId``,
                ``actionTypeId`` and the connector ``name``) and ``size``
                (max number of alerts). Optional: ``query``, ``filters``,
                ``combined_filter``, ``start``, ``end``.
            schedule: The schedule interval, e.g. ``{"interval": "24h"}``.
            actions: Optional schedule actions (connector notifications).
            enabled: Whether the schedule is enabled (server default False).
            space_id: Optional space ID to create the schedule in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created schedule (``id``, ``name``,
            ``created_by``, ``updated_by``, ``created_at``, ``updated_at``,
            ``enabled``, ``params``, ``schedule``, ``actions``).

        Raises:
            BadRequestError: If the schedule properties are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> created = await client.attack_discovery.create_schedule(
            ...     name="Daily attack discovery",
            ...     params={
            ...         "alerts_index_pattern": ".alerts-security.alerts-default",
            ...         "api_config": {
            ...             "connectorId": "my-connector-id",
            ...             "actionTypeId": ".gen-ai",
            ...             "name": "My GenAI connector",
            ...         },
            ...         "size": 100,
            ...     },
            ...     schedule={"interval": "24h"},
            ... )
            >>> schedule_id = created.body["id"]
        """
        body: dict[str, Any] = {
            "name": name,
            "params": params,
            "schedule": schedule,
        }
        if actions is not None:
            body["actions"] = actions
        if enabled is not None:
            body["enabled"] = enabled

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/attack_discovery/schedules", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_schedule(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an Attack Discovery schedule by ID.

        Retrieves a single schedule
        (``GET /api/attack_discovery/schedules/{id}``).

        Args:
            id: The identifier of the schedule.
            space_id: Optional space ID to get the schedule from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the schedule details (``id``, ``name``,
            ``enabled``, ``params``, ``schedule``, ``actions``, audit
            fields).

        Raises:
            NotFoundError: If the schedule does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> schedule = await client.attack_discovery.get_schedule(id="b0ab787f-...")
            >>> print(schedule.body["name"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/attack_discovery/schedules/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_schedule(
        self,
        *,
        id: str,
        name: str,
        params: dict[str, Any],
        schedule: dict[str, Any],
        actions: list[dict[str, Any]],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update an Attack Discovery schedule.

        Replaces the schedule's properties
        (``PUT /api/attack_discovery/schedules/{id}``). All properties are
        required by the 9.4 API (this is a full update, not a patch).

        Args:
            id: The identifier of the schedule to update.
            name: The name of the schedule.
            params: The schedule configuration parameters (see
                :meth:`create_schedule` for the required keys).
            schedule: The schedule interval, e.g. ``{"interval": "12h"}``.
            actions: The schedule actions. Pass ``[]`` to keep no actions.
            space_id: Optional space ID the schedule belongs to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the updated schedule details.

        Raises:
            NotFoundError: If the schedule does not exist.
            BadRequestError: If the schedule properties are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.attack_discovery.update_schedule(
            ...     id="b0ab787f-...",
            ...     name="Renamed schedule",
            ...     params={
            ...         "alerts_index_pattern": ".alerts-security.alerts-default",
            ...         "api_config": {
            ...             "connectorId": "my-connector-id",
            ...             "actionTypeId": ".gen-ai",
            ...             "name": "My GenAI connector",
            ...         },
            ...         "size": 50,
            ...     },
            ...     schedule={"interval": "12h"},
            ...     actions=[],
            ... )
        """
        body: dict[str, Any] = {
            "name": name,
            "params": params,
            "schedule": schedule,
            "actions": actions,
        }

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/attack_discovery/schedules/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_schedule(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an Attack Discovery schedule.

        Deletes the schedule and its backing alerting rule
        (``DELETE /api/attack_discovery/schedules/{id}``).

        Args:
            id: The identifier of the schedule to delete.
            space_id: Optional space ID the schedule belongs to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the deleted schedule's ``id``.

        Raises:
            NotFoundError: If the schedule does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.attack_discovery.delete_schedule(id="b0ab787f-...")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/attack_discovery/schedules/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    async def enable_schedule(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Enable an Attack Discovery schedule.

        Starts periodic attack discovery generation for the schedule
        (``POST /api/attack_discovery/schedules/{id}/_enable``).

        Args:
            id: The identifier of the schedule to enable.
            space_id: Optional space ID the schedule belongs to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the schedule's ``id``.

        Raises:
            NotFoundError: If the schedule does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.attack_discovery.enable_schedule(id="b0ab787f-...")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/attack_discovery/schedules/{_quote(id)}/_enable", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def disable_schedule(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Disable an Attack Discovery schedule.

        Stops periodic attack discovery generation for the schedule
        (``POST /api/attack_discovery/schedules/{id}/_disable``).

        Args:
            id: The identifier of the schedule to disable.
            space_id: Optional space ID the schedule belongs to.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the schedule's ``id``.

        Raises:
            NotFoundError: If the schedule does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.attack_discovery.disable_schedule(id="b0ab787f-...")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/attack_discovery/schedules/{_quote(id)}/_disable", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def find_schedules(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        sort_direction: str | None = None,
        sort_field: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Find Attack Discovery schedules.

        Lists schedules with pagination and sorting
        (``GET /api/attack_discovery/schedules/_find``).

        Note:
            On a live 9.4.3 server the ``page`` parameter is off by one:
            the server treats an explicit ``page=N`` as page ``N + 1``
            (``page=1`` returns the *second* page). Omit ``page`` (or pass
            ``page=0``) to get the first page. Also, in spaces where the
            ``securitySolutionAttackDiscovery`` feature is disabled (e.g.
            spaces with the Elasticsearch solution view), this endpoint
            returns ``total: 0`` even though schedules exist.

        Args:
            page: Page number (see the note above about the live off-by-one
                behavior).
            per_page: Number of schedules per page (server default 10).
            sort_direction: Sort direction, ``"asc"`` or ``"desc"`` (server
                default ``"asc"``).
            sort_field: Field to sort by. Common fields: ``"name"``,
                ``"created_at"``, ``"updated_at"``, ``"enabled"``.
            space_id: Optional space ID to search in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``page``, ``per_page``, ``total`` and
            ``data`` (the list of schedules).

        Raises:
            BadRequestError: If the query parameters are invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.attack_discovery.find_schedules(per_page=100)
            >>> for s in found.body["data"]:
            ...     print(s["id"], s["name"], s["enabled"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if sort_direction is not None:
            params["sort_direction"] = sort_direction
        if sort_field is not None:
            params["sort_field"] = sort_field

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/attack_discovery/schedules/_find", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params or None,
            headers={"accept": "application/json"},
        )
