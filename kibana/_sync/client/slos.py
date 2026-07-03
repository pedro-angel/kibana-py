"""Kibana SLOs (Service Level Objectives) API client."""

from typing import Any

from elastic_transport import ObjectApiResponse

from .utils import NamespaceClient, _quote

#: Base path of the SLOs API. The official spec roots every SLO path at
#: ``/s/{spaceId}/api/observability/slos``; this client builds the space
#: prefix via ``_build_space_path`` so ``space_id=None`` targets the
#: default space.
_SLOS_PATH = "/api/observability/slos"


class SlosClient(NamespaceClient):
    """Client for the Kibana SLOs (Service Level Objectives) API.

    SLOs let you set measurable targets (availability, latency, ...) for your
    services based on Elasticsearch data and track error budgets against
    those targets. The SLO APIs require an appropriate license (Platinum or
    trial) and Kibana 8.12+ / 9.x.

    All endpoints are space-scoped: the official API paths are rooted at
    ``/s/{spaceId}/api/observability/slos``. Every method therefore accepts
    ``space_id`` (``None`` targets the default space) and
    ``validate_spaces`` to override space-existence validation per call.

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create an SLO based on a custom KQL indicator
        >>> slo = client.slos.create(
        ...     name="my-service availability",
        ...     description="99% of requests are good over 30 days",
        ...     indicator={
        ...         "type": "sli.kql.custom",
        ...         "params": {
        ...             "index": "my-service-logs",
        ...             "good": "status: ok",
        ...             "total": "",
        ...             "timestampField": "@timestamp",
        ...         },
        ...     },
        ...     time_window={"duration": "30d", "type": "rolling"},
        ...     budgeting_method="occurrences",
        ...     objective={"target": 0.99},
        ... )
        >>> slo_id = slo.body["id"]
        >>>
        >>> # Fetch it back, then clean up
        >>> client.slos.get(slo_id=slo_id)  # doctest: +SKIP
        >>> client.slos.delete(slo_id=slo_id)  # doctest: +SKIP
    """

    def find(
        self,
        *,
        kql_query: str | None = None,
        size: int | None = None,
        search_after: list[str] | None = None,
        page: int | None = None,
        per_page: int | None = None,
        sort_by: str | None = None,
        sort_direction: str | None = None,
        hide_stale: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a paginated list of SLOs with their summaries.

        ``GET /api/observability/slos``

        Args:
            kql_query: A valid KQL query to filter SLOs with, e.g.
                ``'slo.name:latency* and slo.tags : "prod"'``.
            size: The page size to use for cursor-based pagination (must be
                used together with ``search_after``). Default 1.
            search_after: The cursor to use for fetching the results from,
                when using a cursor-based pagination.
            page: The page number to return (default 1). Offset-based
                pagination; mutually exclusive with ``size``/``search_after``.
            per_page: The number of SLOs to return per page (default 25,
                maximum 5000).
            sort_by: Sort by field. One of ``"sli_value"``, ``"status"``,
                ``"error_budget_consumed"``, ``"error_budget_remaining"``
                (default ``"status"``).
            sort_direction: Sort order, ``"asc"`` (default) or ``"desc"``.
            hide_stale: Hide stale SLOs from the list as defined by the stale
                SLO threshold in SLO settings.
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse with ``page``, ``perPage``, ``total`` and
            ``results`` (a list of SLOs with their ``summary``).

        Raises:
            BadRequestError: If a query parameter is invalid (400).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).

        Example:
            >>> resp = client.slos.find(kql_query="slo.name:my-service*")
            >>> for slo in resp.body["results"]:
            ...     print(slo["name"], slo["summary"]["status"])
        """
        path = self._build_space_path(_SLOS_PATH, space_id, validate_spaces)
        params: dict[str, Any] = {}
        if kql_query is not None:
            params["kqlQuery"] = kql_query
        if size is not None:
            params["size"] = size
        if search_after is not None:
            params["searchAfter"] = search_after
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        if sort_by is not None:
            params["sortBy"] = sort_by
        if sort_direction is not None:
            params["sortDirection"] = sort_direction
        if hide_stale is not None:
            params["hideStale"] = hide_stale
        return self.perform_request(
            method="GET",
            path=path,
            params=params or None,
        )

    def create(
        self,
        *,
        name: str,
        description: str,
        indicator: dict[str, Any],
        time_window: dict[str, Any],
        budgeting_method: str,
        objective: dict[str, Any],
        id: str | None = None,
        settings: dict[str, Any] | None = None,
        group_by: str | list[str] | None = None,
        tags: list[str] | None = None,
        artifacts: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an SLO.

        ``POST /api/observability/slos``

        Args:
            name: A name for the SLO.
            description: A description for the SLO.
            indicator: The indicator (SLI) definition, e.g.
                ``{"type": "sli.kql.custom", "params": {...}}``. Supported
                types: ``sli.apm.transactionDuration``,
                ``sli.apm.transactionErrorRate``, ``sli.kql.custom``,
                ``sli.metric.custom``, ``sli.histogram.custom``,
                ``sli.metric.timeslice``.
            time_window: The SLO time window, e.g.
                ``{"duration": "30d", "type": "rolling"}`` or
                ``{"duration": "1M", "type": "calendarAligned"}``.
            budgeting_method: ``"occurrences"`` or ``"timeslices"``.
            objective: The objective, e.g. ``{"target": 0.99}``; timeslices
                budgeting also uses ``timesliceTarget`` and
                ``timesliceWindow``.
            id: An optional unique identifier for the SLO (8-36 characters);
                autogenerated when omitted.
            settings: Optional settings such as ``syncDelay``, ``frequency``,
                ``syncField`` and ``preventInitialBackfill``.
            group_by: Optional field or list of fields to generate one SLO
                per distinct value (e.g. ``"service.name"``).
            tags: Optional list of tags.
            artifacts: Optional links to related assets, e.g.
                ``{"dashboards": [{"id": "..."}]}``.
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse containing the ``id`` of the created SLO.

        Raises:
            BadRequestError: If the SLO definition is invalid (400).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).
            ConflictError: If an SLO with the same id already exists (409).

        Example:
            >>> resp = client.slos.create(
            ...     name="availability",
            ...     description="99% good over 7 days",
            ...     indicator={
            ...         "type": "sli.kql.custom",
            ...         "params": {
            ...             "index": "logs-*",
            ...             "good": "status: ok",
            ...             "total": "",
            ...             "timestampField": "@timestamp",
            ...         },
            ...     },
            ...     time_window={"duration": "7d", "type": "rolling"},
            ...     budgeting_method="occurrences",
            ...     objective={"target": 0.99},
            ... )
            >>> print(resp.body["id"])
        """
        path = self._build_space_path(_SLOS_PATH, space_id, validate_spaces)
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "indicator": indicator,
            "timeWindow": time_window,
            "budgetingMethod": budgeting_method,
            "objective": objective,
        }
        if id is not None:
            body["id"] = id
        if settings is not None:
            body["settings"] = settings
        if group_by is not None:
            body["groupBy"] = group_by
        if tags is not None:
            body["tags"] = tags
        if artifacts is not None:
            body["artifacts"] = artifacts
        return self.perform_request(
            method="POST",
            path=path,
            body=body,
        )

    def get(
        self,
        *,
        slo_id: str,
        instance_id: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an SLO by its identifier.

        ``GET /api/observability/slos/{sloId}``

        Args:
            slo_id: The SLO identifier.
            instance_id: The SLO instance identifier when retrieving a
                specific instance of a grouped SLO.
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse with the SLO definition and its ``summary``.

        Raises:
            NotFoundError: If the SLO does not exist (404).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).

        Example:
            >>> slo = client.slos.get(slo_id="my-slo-id")
            >>> print(slo.body["name"], slo.body["enabled"])
        """
        path = self._build_space_path(
            f"{_SLOS_PATH}/{_quote(slo_id)}", space_id, validate_spaces
        )
        params: dict[str, Any] = {}
        if instance_id is not None:
            params["instanceId"] = instance_id
        return self.perform_request(
            method="GET",
            path=path,
            params=params or None,
        )

    def update(
        self,
        *,
        slo_id: str,
        name: str | None = None,
        description: str | None = None,
        indicator: dict[str, Any] | None = None,
        time_window: dict[str, Any] | None = None,
        budgeting_method: str | None = None,
        objective: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
        group_by: str | list[str] | None = None,
        tags: list[str] | None = None,
        artifacts: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update an SLO.

        ``PUT /api/observability/slos/{sloId}``

        Performs a partial update: only the provided fields are changed.
        Updating fields that are part of the rollup transform (indicator,
        time window, budgeting method, objective, group_by or settings)
        triggers a re-computation of the SLO data.

        Args:
            slo_id: The SLO identifier.
            name: A new name for the SLO.
            description: A new description for the SLO.
            indicator: The indicator (SLI) definition.
            time_window: The SLO time window.
            budgeting_method: ``"occurrences"`` or ``"timeslices"``.
            objective: The objective, e.g. ``{"target": 0.99}``.
            settings: Settings such as ``syncDelay``, ``frequency``,
                ``syncField`` and ``preventInitialBackfill``.
            group_by: Field or list of fields to generate one SLO per
                distinct value.
            tags: List of tags.
            artifacts: Links to related assets, e.g.
                ``{"dashboards": [{"id": "..."}]}``.
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse with the updated SLO definition.

        Raises:
            BadRequestError: If the update payload is invalid (400).
            NotFoundError: If the SLO does not exist (404).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).

        Example:
            >>> resp = client.slos.update(
            ...     slo_id="my-slo-id",
            ...     description="Updated description",
            ...     tags=["prod"],
            ... )
        """
        path = self._build_space_path(
            f"{_SLOS_PATH}/{_quote(slo_id)}", space_id, validate_spaces
        )
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if indicator is not None:
            body["indicator"] = indicator
        if time_window is not None:
            body["timeWindow"] = time_window
        if budgeting_method is not None:
            body["budgetingMethod"] = budgeting_method
        if objective is not None:
            body["objective"] = objective
        if settings is not None:
            body["settings"] = settings
        if group_by is not None:
            body["groupBy"] = group_by
        if tags is not None:
            body["tags"] = tags
        if artifacts is not None:
            body["artifacts"] = artifacts
        return self.perform_request(
            method="PUT",
            path=path,
            body=body,
        )

    def delete(
        self,
        *,
        slo_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an SLO and its associated summary and rollup data.

        ``DELETE /api/observability/slos/{sloId}``

        Args:
            slo_id: The SLO identifier.
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse with an empty body (HTTP 204 on success).

        Raises:
            NotFoundError: If the SLO does not exist (404).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).

        Example:
            >>> client.slos.delete(slo_id="my-slo-id")
        """
        path = self._build_space_path(
            f"{_SLOS_PATH}/{_quote(slo_id)}", space_id, validate_spaces
        )
        return self.perform_request(
            method="DELETE",
            path=path,
        )

    def enable(
        self,
        *,
        slo_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Enable an SLO, resuming data rollup and summary computation.

        ``POST /api/observability/slos/{sloId}/enable``

        Args:
            slo_id: The SLO identifier.
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse with an empty body (HTTP 204 on success).

        Raises:
            NotFoundError: If the SLO does not exist (404).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).

        Example:
            >>> client.slos.enable(slo_id="my-slo-id")
        """
        path = self._build_space_path(
            f"{_SLOS_PATH}/{_quote(slo_id)}/enable", space_id, validate_spaces
        )
        return self.perform_request(
            method="POST",
            path=path,
        )

    def disable(
        self,
        *,
        slo_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Disable an SLO, stopping data rollup and summary computation.

        ``POST /api/observability/slos/{sloId}/disable``

        Args:
            slo_id: The SLO identifier.
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse with an empty body (HTTP 204 on success).

        Raises:
            NotFoundError: If the SLO does not exist (404).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).

        Example:
            >>> client.slos.disable(slo_id="my-slo-id")
        """
        path = self._build_space_path(
            f"{_SLOS_PATH}/{_quote(slo_id)}/disable", space_id, validate_spaces
        )
        return self.perform_request(
            method="POST",
            path=path,
        )

    def reset(
        self,
        *,
        slo_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Reset an SLO, deleting its data and recomputing it from scratch.

        ``POST /api/observability/slos/{sloId}/_reset``

        Args:
            slo_id: The SLO identifier.
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse with the reset SLO definition.

        Raises:
            NotFoundError: If the SLO does not exist (404).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).

        Example:
            >>> resp = client.slos.reset(slo_id="my-slo-id")
            >>> print(resp.body["version"])
        """
        path = self._build_space_path(
            f"{_SLOS_PATH}/{_quote(slo_id)}/_reset", space_id, validate_spaces
        )
        return self.perform_request(
            method="POST",
            path=path,
        )

    def delete_instances(
        self,
        *,
        instances: list[dict[str, Any]],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Batch delete rollup and summary data for SLO instances.

        ``POST /api/observability/slos/_delete_instances``

        Deletes the rollup and summary data for the given list of SLO id /
        instance id pairs. Useful for removing stale data of instances of a
        grouped SLO that no longer receive updates.

        Args:
            instances: A list of ``{"sloId": ..., "instanceId": ...}``
                objects identifying the instances to delete.
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse with an empty body (HTTP 204 on success).

        Raises:
            BadRequestError: If the payload is invalid (400).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).

        Example:
            >>> client.slos.delete_instances(
            ...     instances=[
            ...         {"sloId": "my-slo-id", "instanceId": "my-service"},
            ...     ]
            ... )
        """
        path = self._build_space_path(
            f"{_SLOS_PATH}/_delete_instances", space_id, validate_spaces
        )
        return self.perform_request(
            method="POST",
            path=path,
            body={"list": instances},
        )

    def bulk_delete(
        self,
        *,
        slo_ids: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk delete SLO definitions and their summary and rollup data.

        ``POST /api/observability/slos/_bulk_delete``

        The deletion occurs asynchronously: the response contains a
        ``taskId`` that can be polled with :meth:`bulk_delete_status` to
        retrieve the operation outcome.

        Args:
            slo_ids: A list of SLO definition ids to delete.
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse containing the ``taskId`` of the bulk deletion.

        Raises:
            BadRequestError: If the payload is invalid (400).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).

        Example:
            >>> resp = client.slos.bulk_delete(slo_ids=["slo-1", "slo-2"])
            >>> status = client.slos.bulk_delete_status(
            ...     task_id=resp.body["taskId"]
            ... )
        """
        path = self._build_space_path(
            f"{_SLOS_PATH}/_bulk_delete", space_id, validate_spaces
        )
        return self.perform_request(
            method="POST",
            path=path,
            body={"list": slo_ids},
        )

    def bulk_delete_status(
        self,
        *,
        task_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Retrieve the status of an asynchronous bulk deletion.

        ``GET /api/observability/slos/_bulk_delete/{taskId}``

        Args:
            task_id: The task id returned by :meth:`bulk_delete`.
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse with ``isDone``, per-SLO ``results`` and an
            optional ``error``.

        Raises:
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).

        Example:
            >>> status = client.slos.bulk_delete_status(task_id="...")
            >>> if status.body["isDone"]:
            ...     for result in status.body["results"]:
            ...         print(result["id"], result["success"])
        """
        path = self._build_space_path(
            f"{_SLOS_PATH}/_bulk_delete/{_quote(task_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            method="GET",
            path=path,
        )

    def bulk_purge_rollup(
        self,
        *,
        slo_ids: list[str],
        purge_policy: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Batch delete rollup and summary data according to a purge policy.

        ``POST /api/observability/slos/_bulk_purge_rollup``

        The deletion occurs asynchronously (Elasticsearch delete-by-query)
        and the response contains an Elasticsearch task id.

        Note:
            Kibana 9.4.3 expects ``purgeType`` values ``"fixed_age"`` /
            ``"fixed_time"`` (snake_case), although the official OpenAPI
            spec documents ``"fixed-age"`` / ``"fixed-time"``.

        Args:
            slo_ids: A list of SLO ids whose rollup data should be purged.
            purge_policy: Policy dictating which SLI documents to purge,
                either ``{"purgeType": "fixed_age", "age": "7d"}`` or
                ``{"purgeType": "fixed_time", "timestamp": "2024-01-01T00:00:00.000Z"}``.
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse containing the Elasticsearch ``taskId`` of the
            purge operation.

        Raises:
            BadRequestError: If the purge policy is invalid or would purge
                data inside an SLO time window (400).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).

        Example:
            >>> resp = client.slos.bulk_purge_rollup(
            ...     slo_ids=["my-slo-id"],
            ...     purge_policy={"purgeType": "fixed_age", "age": "30d"},
            ... )
            >>> print(resp.body["taskId"])
        """
        path = self._build_space_path(
            f"{_SLOS_PATH}/_bulk_purge_rollup", space_id, validate_spaces
        )
        return self.perform_request(
            method="POST",
            path=path,
            body={"list": slo_ids, "purgePolicy": purge_policy},
        )

    def find_definitions(
        self,
        *,
        include_outdated_only: bool | None = None,
        include_health: bool | None = None,
        tags: str | None = None,
        search: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the SLO definitions (without computed summaries).

        ``GET /api/observability/slos/_definitions``

        Note:
            The official OpenAPI spec documents this operation under
            ``/internal/observability/slos/_definitions``, but Kibana 9.4.3
            serves it on the public ``/api/observability/slos/_definitions``
            path (the internal path returns 404); this client uses the
            public path.

        Args:
            include_outdated_only: Indicates if the API returns only outdated
                SLOs or all SLOs.
            include_health: Include the health of the SLO transforms in the
                response.
            tags: Filter SLOs by tag (comma-separated list of tags).
            search: Filter SLOs by name, e.g. ``"my-service*"``.
            page: The page number to return.
            per_page: The number of SLOs to return per page (default 100,
                maximum 1000).
            space_id: Space to operate on; ``None`` targets the default space.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse with ``page``, ``perPage``, ``total`` and
            ``results`` (a list of SLO definitions).

        Raises:
            BadRequestError: If a query parameter is invalid (400).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).

        Example:
            >>> resp = client.slos.find_definitions(search="my-service*")
            >>> print(resp.body["total"])
        """
        path = self._build_space_path(
            f"{_SLOS_PATH}/_definitions", space_id, validate_spaces
        )
        params: dict[str, Any] = {}
        if include_outdated_only is not None:
            params["includeOutdatedOnly"] = include_outdated_only
        if include_health is not None:
            params["includeHealth"] = include_health
        if tags is not None:
            params["tags"] = tags
        if search is not None:
            params["search"] = search
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        return self.perform_request(
            method="GET",
            path=path,
            params=params or None,
        )
