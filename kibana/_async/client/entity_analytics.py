"""Async Kibana Security Entity Analytics API client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote
from kibana._sync.client.entity_analytics import _build_csv_multipart_body, _csv_bytes

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class AsyncEntityAnalyticsClient(AsyncNamespaceClient):
    """Async client for the Kibana Security Entity Analytics API.

    Entity Analytics surfaces risk and privilege insights for entities
    (hosts, users, services and generic entities) observed by the Elastic
    Security solution. This client covers the Kibana 9.4.3 Entity Analytics
    REST APIs:

    - **Asset criticality** (``/api/asset_criticality``): classify how
      critical an entity is (deprecated in 9.4 in favor of the Entity Store).
    - **Risk engine** (``/api/risk_score/engine``): schedule, configure and
      clean up the risk scoring engine.
    - **Privilege monitoring** (``/api/entity_analytics/monitoring``):
      manage the Privilege Monitoring Engine and monitored privileged users,
      including CSV bulk upload.
    - **Privileged access detection** (``.../privileged_user_monitoring/pad``):
      install and inspect the PAD ML package.
    - **Watchlists** (``/api/entity_analytics/watchlists``): group entities
      and apply risk modifiers (Technical Preview in 9.4).
    - **Entity Store** (``/api/security/entity_store``): install, manage and
      query the entity store, including direct entity CRUD and entity
      resolution (linking).

    All Entity Analytics resources are space-scoped: every method accepts an
    optional ``space_id`` to target a specific space (``None`` targets the
    default space or the space the client is scoped to).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Classify an asset and read it back
        >>> await client.entity_analytics.create_asset_criticality(
        ...     id_field="host.name",
        ...     id_value="my-host",
        ...     criticality_level="high_impact",
        ... )
        >>> record = await client.entity_analytics.get_asset_criticality(
        ...     id_field="host.name", id_value="my-host"
        ... )
        >>>
        >>> # Install the Entity Store and check its status
        >>> await client.entity_analytics.install_entity_store(entity_types=["host"])
        >>> status = await client.entity_analytics.get_entity_store_status()
        >>> print(status.body["status"])
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncEntityAnalyticsClient.

        Args:
            client: The parent AsyncKibana client instance to delegate
                requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> entity_analytics_client = AsyncEntityAnalyticsClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    # ------------------------------------------------------------------
    # Asset criticality
    # ------------------------------------------------------------------

    async def create_asset_criticality(
        self,
        *,
        id_field: str,
        id_value: str,
        criticality_level: str,
        refresh: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Upsert an asset criticality record.

        .. deprecated:: 9.4
            The asset criticality APIs are deprecated; manage asset
            criticality through the Entity Store entity APIs instead
            (e.g. :meth:`update_entity`).

        ``POST /api/asset_criticality``. Creates or updates (upserts) the
        asset criticality record for the given entity. If a record already
        exists for the specified entity, that record is overwritten. If no
        record exists, a new record is created.

        Args:
            id_field: The field representing the entity identifier. One of
                ``"host.name"``, ``"user.name"``, ``"service.name"``,
                ``"entity.id"``.
            id_value: The identifier of the entity (e.g. the host name).
            criticality_level: The criticality level. One of
                ``"low_impact"``, ``"medium_impact"``, ``"high_impact"``,
                ``"extreme_impact"``.
            refresh: If ``"wait_for"``, wait for a refresh so the created
                record is visible to subsequent searches.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created/updated record
            (``id_field``, ``id_value``, ``criticality_level``,
            ``@timestamp``, ``asset`` and the entity field object).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> record = await client.entity_analytics.create_asset_criticality(
            ...     id_field="host.name",
            ...     id_value="my-host",
            ...     criticality_level="high_impact",
            ...     refresh="wait_for",
            ... )
            >>> print(record.body["criticality_level"])
            high_impact
        """
        body: dict[str, Any] = {
            "id_field": id_field,
            "id_value": id_value,
            "criticality_level": criticality_level,
        }
        if refresh is not None:
            body["refresh"] = refresh

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/asset_criticality", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_asset_criticality(
        self,
        *,
        id_field: str,
        id_value: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an asset criticality record.

        .. deprecated:: 9.4
            The asset criticality APIs are deprecated; manage asset
            criticality through the Entity Store entity APIs instead.

        ``GET /api/asset_criticality``. Gets the asset criticality record
        for the given entity.

        Args:
            id_field: The field representing the entity identifier. One of
                ``"host.name"``, ``"user.name"``, ``"service.name"``,
                ``"entity.id"``.
            id_value: The identifier of the entity.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the asset criticality record.

        Raises:
            NotFoundError: If no record exists for the entity.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> record = await client.entity_analytics.get_asset_criticality(
            ...     id_field="host.name", id_value="my-host"
            ... )
            >>> print(record.body["criticality_level"])
        """
        params: dict[str, Any] = {"id_field": id_field, "id_value": id_value}
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/asset_criticality", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def delete_asset_criticality(
        self,
        *,
        id_field: str,
        id_value: str,
        refresh: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an asset criticality record.

        .. deprecated:: 9.4
            The asset criticality APIs are deprecated; manage asset
            criticality through the Entity Store entity APIs instead.

        ``DELETE /api/asset_criticality``. Deletes the asset criticality
        record for the given entity. If no record exists, the response
        reports ``deleted: false`` (no error is raised).

        Args:
            id_field: The field representing the entity identifier. One of
                ``"host.name"``, ``"user.name"``, ``"service.name"``,
                ``"entity.id"``.
            id_value: The identifier of the entity.
            refresh: If ``"wait_for"``, wait for a refresh so the deletion is
                visible to subsequent searches.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``deleted`` (bool) and, if a record was
            deleted, the deleted ``record``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.delete_asset_criticality(
            ...     id_field="host.name",
            ...     id_value="my-host",
            ...     refresh="wait_for",
            ... )
            >>> print(result.body["deleted"])
            True
        """
        params: dict[str, Any] = {"id_field": id_field, "id_value": id_value}
        if refresh is not None:
            params["refresh"] = refresh

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/asset_criticality", space_id)
        return await self.perform_request(
            "DELETE",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def bulk_upsert_asset_criticality(
        self,
        *,
        records: list[dict[str, Any]],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk upsert asset criticality records.

        .. deprecated:: 9.4
            The asset criticality APIs are deprecated; manage asset
            criticality through the Entity Store entity APIs instead.

        ``POST /api/asset_criticality/bulk``. Bulk creates or updates (up to
        1000) asset criticality records. If a record already exists for the
        specified entity, that record is overwritten. In addition to the
        regular criticality levels, bulk upload accepts the special
        ``"unassigned"`` level, which removes the record's criticality
        assignment.

        Args:
            records: Records to upsert. Each record requires ``id_field``
                (one of ``"host.name"``, ``"user.name"``, ``"service.name"``,
                ``"entity.id"``), ``id_value`` and ``criticality_level``
                (``"low_impact"``, ``"medium_impact"``, ``"high_impact"``,
                ``"extreme_impact"`` or ``"unassigned"``).
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``errors`` (per-record failures, with the
            record index) and ``stats`` (``successful``/``failed``/``total``).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.bulk_upsert_asset_criticality(
            ...     records=[
            ...         {
            ...             "id_field": "host.name",
            ...             "id_value": "my-host",
            ...             "criticality_level": "high_impact",
            ...         },
            ...         {
            ...             "id_field": "user.name",
            ...             "id_value": "my-user",
            ...             "criticality_level": "low_impact",
            ...         },
            ...     ]
            ... )
            >>> print(result.body["stats"]["successful"])
            2
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/asset_criticality/bulk", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"records": records},
        )

    async def find_asset_criticality(
        self,
        *,
        sort_field: str | None = None,
        sort_direction: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        kuery: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List asset criticality records.

        .. deprecated:: 9.4
            The asset criticality APIs are deprecated; manage asset
            criticality through the Entity Store entity APIs instead.

        ``GET /api/asset_criticality/list``. Lists asset criticality
        records, paging, sorting and filtering as needed.

        Args:
            sort_field: The field to sort by. One of ``"id_value"``,
                ``"id_field"``, ``"criticality_level"``, ``"@timestamp"``.
            sort_direction: The order to sort by: ``"asc"`` or ``"desc"``.
            page: The page number to return (>= 1).
            per_page: The number of records to return per page (1-1000).
            kuery: A KQL string to filter the records
                (e.g. ``'host.name: my-host'``).
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``records``, ``total``, ``page`` and
            ``per_page``.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.entity_analytics.find_asset_criticality(
            ...     kuery="criticality_level: high_impact",
            ...     sort_field="@timestamp",
            ...     sort_direction="desc",
            ...     per_page=100,
            ... )
            >>> print(found.body["total"])
        """
        params: dict[str, Any] = {}
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_direction is not None:
            params["sort_direction"] = sort_direction
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if kuery is not None:
            params["kuery"] = kuery

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/asset_criticality/list", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Risk engine
    # ------------------------------------------------------------------

    async def schedule_risk_engine_now(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Run the risk scoring engine immediately.

        ``POST /api/risk_score/engine/schedule_now``. Schedules the risk
        scoring engine to run as soon as possible. Use this to recalculate
        entity risk scores after updating the risk engine configuration.

        Note: on Kibana deployments where Entity Store V2 is enabled, the
        legacy risk engine routes are not registered and this endpoint
        returns a plain 404 (``NotFoundError``).

        Args:
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``success`` (bool).

        Raises:
            NotFoundError: If the risk engine routes are not available
                (e.g. Entity Store V2 is enabled).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.schedule_risk_engine_now()
            >>> print(result.body["success"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/risk_score/engine/schedule_now", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def configure_risk_engine_saved_object(
        self,
        *,
        enable_reset_to_zero: bool | None = None,
        exclude_alert_statuses: list[str] | None = None,
        exclude_alert_tags: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        page_size: int | None = None,
        range: dict[str, str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Configure the risk engine saved object.

        ``PATCH /api/risk_score/engine/saved_object/configure``. Configures
        the risk engine saved object with new settings such as the alert
        date range, excluded alert statuses/tags and entity filters.

        Note: on Kibana deployments where Entity Store V2 is enabled, the
        legacy risk engine routes are not registered and this endpoint
        returns a plain 404 (``NotFoundError``).

        Args:
            enable_reset_to_zero: Whether risk scores of entities without
                recent alerts are reset to zero.
            exclude_alert_statuses: Alert workflow statuses to exclude from
                risk scoring (e.g. ``["closed"]``).
            exclude_alert_tags: Alert tags to exclude from risk scoring.
            filters: Entity filters. Each filter requires ``entity_types``
                (list of ``"host"``/``"user"``/``"service"``) and ``filter``
                (a KQL string).
            page_size: Number of entities to score per page (100-10000).
            range: The alert date range to consider, an object with
                ``start`` and ``end`` date-math strings
                (e.g. ``{"start": "now-30d", "end": "now"}``).
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``risk_engine_saved_object_configured``
            (bool) on success.

        Raises:
            NotFoundError: If the risk engine routes are not available
                (e.g. Entity Store V2 is enabled) or the risk engine has not
                been initialized.
            BadRequestError: If the configuration is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.entity_analytics.configure_risk_engine_saved_object(
            ...     range={"start": "now-30d", "end": "now"},
            ...     exclude_alert_statuses=["closed"],
            ... )
        """
        body: dict[str, Any] = {}
        if enable_reset_to_zero is not None:
            body["enable_reset_to_zero"] = enable_reset_to_zero
        if exclude_alert_statuses is not None:
            body["exclude_alert_statuses"] = exclude_alert_statuses
        if exclude_alert_tags is not None:
            body["exclude_alert_tags"] = exclude_alert_tags
        if filters is not None:
            body["filters"] = filters
        if page_size is not None:
            body["page_size"] = page_size
        if range is not None:
            body["range"] = range

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/risk_score/engine/saved_object/configure", space_id
        )
        return await self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def cleanup_risk_engine(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Clean up the risk engine, deleting all risk scoring data.

        ``DELETE /api/risk_score/engine/dangerously_delete_data``.
        Permanently cleans up the risk engine by deleting the risk scoring
        task, removing risk score transforms and deleting all risk score
        data and indices. **This operation destroys data and cannot be
        undone.**

        Note: on Kibana deployments where Entity Store V2 is enabled, the
        legacy risk engine routes are not registered and this endpoint
        returns a plain 404 (``NotFoundError``).

        Args:
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``risk_engine_cleanup`` (bool); on partial
            failure the body contains a ``cleanup_agent_policies`` /
            ``errors`` task failure payload.

        Raises:
            NotFoundError: If the risk engine routes are not available
                (e.g. Entity Store V2 is enabled).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.cleanup_risk_engine()
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/risk_score/engine/dangerously_delete_data", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Privilege Monitoring Engine
    # ------------------------------------------------------------------

    async def init_monitoring_engine(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Initialize the Privilege Monitoring Engine.

        ``POST /api/entity_analytics/monitoring/engine/init``. Initializes
        the Privilege Monitoring Engine for the space, creating the
        monitored-users index and the monitoring task. The call is
        idempotent: initializing an already-started engine succeeds.

        Args:
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the engine ``status``
            (e.g. ``"started"``) and, on failure, an ``error`` object.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.init_monitoring_engine()
            >>> print(result.body["status"])
            started
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/entity_analytics/monitoring/engine/init", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def disable_monitoring_engine(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Disable the Privilege Monitoring Engine.

        ``POST /api/entity_analytics/monitoring/engine/disable``. Disables
        the Privilege Monitoring Engine without deleting its data. Use
        :meth:`init_monitoring_engine` to re-enable it.

        Args:
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the engine ``status``
            (e.g. ``"disabled"``) and, on failure, an ``error`` object.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.disable_monitoring_engine()
            >>> print(result.body["status"])
            disabled
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/entity_analytics/monitoring/engine/disable", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def schedule_monitoring_engine_now(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Run the Privilege Monitoring Engine immediately.

        ``POST /api/entity_analytics/monitoring/engine/schedule_now``.
        Schedules the Privilege Monitoring Engine task to run as soon as
        possible instead of waiting for its next scheduled run.

        Args:
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``success`` (bool).

        Raises:
            NotFoundError: If the monitoring engine has not been initialized.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.schedule_monitoring_engine_now()
            >>> print(result.body["success"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/entity_analytics/monitoring/engine/schedule_now", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def delete_monitoring_engine(
        self,
        *,
        data: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete the Privilege Monitoring Engine.

        ``DELETE /api/entity_analytics/monitoring/engine/delete``. Deletes
        the Privilege Monitoring Engine, removing its task and saved object.

        Args:
            data: If True, also delete the engine's data (the monitored
                users index). Defaults to False on the server.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``deleted`` (bool).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.delete_monitoring_engine(data=True)
            >>> print(result.body["deleted"])
            True
        """
        params: dict[str, Any] = {}
        if data is not None:
            params["data"] = data

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/entity_analytics/monitoring/engine/delete", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def get_monitoring_health(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the health of the Privilege Monitoring Engine.

        ``GET /api/entity_analytics/monitoring/privileges/health``. Runs a
        health check on privilege monitoring and returns the engine status
        for the space.

        Args:
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``status`` (e.g. ``"not_installed"``,
            ``"started"``, ``"disabled"``), a ``users`` count summary when
            installed, and an ``error`` object on engine failure.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> health = await client.entity_analytics.get_monitoring_health()
            >>> print(health.body["status"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/entity_analytics/monitoring/privileges/health", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_monitoring_privileges(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Check the current user's privilege-monitoring privileges.

        ``GET /api/entity_analytics/monitoring/privileges/privileges``. Runs
        a privileges check for privilege monitoring, reporting which
        Elasticsearch index privileges the current user holds.

        Args:
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``privileges`` (per-index privilege
            flags) and ``has_all_required`` (bool).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.get_monitoring_privileges()
            >>> print(result.body["has_all_required"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/entity_analytics/monitoring/privileges/privileges", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Monitored (privileged) users
    # ------------------------------------------------------------------

    async def create_monitored_user(
        self,
        *,
        name: str,
        monitoring_labels: list[dict[str, Any]] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a new monitored (privileged) user.

        ``POST /api/entity_analytics/monitoring/users``. Adds a user to
        privileged user monitoring. The user is marked as privileged with
        source ``"api"``.

        Args:
            name: The name of the user to monitor.
            monitoring_labels: Optional labels to associate with the user.
                Each label object supports ``field``, ``value`` and
                ``source`` (one of ``"api"``, ``"csv"``, ``"index_sync"``).
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created monitored-user document
            (``id``, ``user``, ``labels``, ``entity_analytics_monitoring``,
            ``@timestamp``).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> user = await client.entity_analytics.create_monitored_user(
            ...     name="admin-user"
            ... )
            >>> print(user.body["user"]["is_privileged"])
            True
        """
        body: dict[str, Any] = {"user": {"name": name}}
        if monitoring_labels is not None:
            body["entity_analytics_monitoring"] = {"labels": monitoring_labels}

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/entity_analytics/monitoring/users", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def update_monitored_user(
        self,
        *,
        id: str,
        doc: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a monitored user.

        ``PUT /api/entity_analytics/monitoring/users/{id}``. Applies a
        partial update to a monitored-user document.

        Args:
            id: The ID of the monitored-user document to update.
            doc: The partial monitored-user document to apply. Supports
                ``user`` (``{"name": ..., "is_privileged": ...}``),
                ``labels`` (``{"sources": [...], "source_ids": [...],
                "source_integrations": [...]}``) and
                ``entity_analytics_monitoring`` (``{"labels": [...]}``).
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated monitored-user document.

        Raises:
            NotFoundError: If the monitored user does not exist.
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.entity_analytics.update_monitored_user(
            ...     id="OflsOZ8BiXLbCmmNbJ9J",
            ...     doc={"user": {"name": "admin-user", "is_privileged": True}},
            ... )
            >>> print(updated.body["user"]["name"])
            admin-user
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/entity_analytics/monitoring/users/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=doc,
        )

    async def delete_monitored_user(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a monitored user.

        ``DELETE /api/entity_analytics/monitoring/users/{id}``. Removes a
        user from privileged user monitoring.

        Args:
            id: The ID of the monitored-user document to delete.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``acknowledged`` (bool).

        Raises:
            NotFoundError: If the monitored user does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.delete_monitored_user(
            ...     id="OflsOZ8BiXLbCmmNbJ9J"
            ... )
            >>> print(result.body["acknowledged"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/entity_analytics/monitoring/users/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    async def list_monitored_users(
        self,
        *,
        kql: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List monitored (privileged) users.

        ``GET /api/entity_analytics/monitoring/users/list``. Lists all
        monitored users in the space, optionally filtered with KQL.

        Args:
            kql: KQL query to filter the monitored users
                (e.g. ``'user.name: admin*'``).
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is a list of monitored-user
            documents.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> users = await client.entity_analytics.list_monitored_users(
            ...     kql="user.name: admin*"
            ... )
            >>> for user in users.body:
            ...     print(user["user"]["name"])
        """
        params: dict[str, Any] = {}
        if kql is not None:
            params["kql"] = kql

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/entity_analytics/monitoring/users/list", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def upload_monitored_users_csv(
        self,
        *,
        file: bytes | str,
        filename: str = "users.csv",
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk upsert monitored users via CSV upload.

        ``POST /api/entity_analytics/monitoring/users/_csv``. Uploads a CSV
        file (as ``multipart/form-data``) containing one user name per line
        to add or update multiple monitored users at once.

        Args:
            file: The CSV content as ``bytes`` or ``str`` (one user name per
                line).
            filename: Filename advertised in the multipart upload.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``errors`` and ``stats``
            (``successfulOperations``/``failedOperations``/``uploaded``/
            ``totalOperations``).

        Raises:
            ValueError: If ``file`` is empty.
            BadRequestError: If the CSV payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.upload_monitored_users_csv(
            ...     file="admin-1\\nadmin-2\\n"
            ... )
            >>> print(result.body["stats"]["uploaded"])
            2
        """
        if not file:
            raise ValueError("Parameter 'file' is required")

        body, content_type = _build_csv_multipart_body(
            _csv_bytes(file), filename=filename
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/entity_analytics/monitoring/users/_csv", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json", "content-type": content_type},
            body=body,  # type: ignore[arg-type]
        )

    # ------------------------------------------------------------------
    # Privileged access detection (PAD)
    # ------------------------------------------------------------------

    async def install_pad_package(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Install the privileged access detection (PAD) package.

        ``POST /api/entity_analytics/privileged_user_monitoring/pad/install``.
        Installs the privileged access detection integration package, which
        provides machine-learning jobs for detecting anomalous privileged
        activity. The call is idempotent.

        Args:
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with a confirmation ``message``.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.install_pad_package()
            >>> print(result.body["message"])
            Successfully installed privileged access detection package.
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/entity_analytics/privileged_user_monitoring/pad/install", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    async def get_pad_status(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the status of the privileged access detection (PAD) package.

        ``GET /api/entity_analytics/privileged_user_monitoring/pad/status``.
        Reports whether the PAD integration package is installed, whether
        its ML module has been set up, and the state of its ML jobs.

        Args:
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``package_installation_status``
            (``"complete"``/``"incomplete"``), ``ml_module_setup_status``
            and ``jobs`` (per-job state).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> status = await client.entity_analytics.get_pad_status()
            >>> print(status.body["package_installation_status"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/entity_analytics/privileged_user_monitoring/pad/status", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Watchlists (Technical Preview)
    # ------------------------------------------------------------------

    async def create_watchlist(
        self,
        *,
        name: str,
        risk_modifier: float,
        description: str | None = None,
        managed: bool | None = None,
        entity_sources: list[dict[str, Any]] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a new watchlist.

        Technical preview in 9.4. ``POST /api/entity_analytics/watchlists``.
        Creates a watchlist that groups entities and applies a risk score
        modifier to them, optionally creating and linking entity sources.

        Args:
            name: Unique name for the watchlist.
            risk_modifier: Risk score modifier associated with the watchlist
                (0-2).
            description: Description of the watchlist.
            managed: Whether the watchlist is managed by the system.
            entity_sources: Optional entity sources to create and link to
                the watchlist. Each source requires ``type`` (one of
                ``"index"``, ``"entity_analytics_integration"``, ``"store"``)
                and ``name``, and supports ``enabled``, ``indexPattern``,
                ``identifierField``, ``integrationName``, ``matchers``,
                ``filter``, ``queryRule`` and ``range``.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created watchlist (``id``,
            ``name``, ``riskModifier``, ``entitySourceIds``, ``createdAt``,
            ``updatedAt``).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> watchlist = await client.entity_analytics.create_watchlist(
            ...     name="High Risk Vendors",
            ...     risk_modifier=1.5,
            ...     description="High risk vendor watchlist",
            ... )
            >>> print(watchlist.body["id"])
        """
        body: dict[str, Any] = {"name": name, "riskModifier": risk_modifier}
        if description is not None:
            body["description"] = description
        if managed is not None:
            body["managed"] = managed
        if entity_sources is not None:
            body["entitySources"] = entity_sources

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/entity_analytics/watchlists", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def list_watchlists(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List all watchlists.

        Technical preview in 9.4.
        ``GET /api/entity_analytics/watchlists/list``. Lists all watchlists
        in the space.

        Args:
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is a list of watchlists.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> watchlists = await client.entity_analytics.list_watchlists()
            >>> for watchlist in watchlists.body:
            ...     print(watchlist["name"], watchlist["riskModifier"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/entity_analytics/watchlists/list", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_watchlist(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a watchlist by ID.

        Technical preview in 9.4.
        ``GET /api/entity_analytics/watchlists/{id}``.

        Args:
            id: The ID of the watchlist.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the watchlist (``id``, ``name``,
            ``riskModifier``, ``entitySourceIds``, ``entityCount``, ...).

        Raises:
            ApiError: If the watchlist does not exist (Kibana 9.4.3 answers
                500 ``"Watchlist config ... not found"`` rather than 404).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> watchlist = await client.entity_analytics.get_watchlist(
            ...     id="b8b48d31-3026-45c0-aa8a-b8ed7f86ade8"
            ... )
            >>> print(watchlist.body["name"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/entity_analytics/watchlists/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_watchlist(
        self,
        *,
        id: str,
        name: str,
        risk_modifier: float,
        description: str | None = None,
        managed: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update an existing watchlist.

        Technical preview in 9.4.
        ``PUT /api/entity_analytics/watchlists/{id}``. Updates a watchlist's
        name, description, risk modifier or managed flag. ``name`` and
        ``risk_modifier`` are required by the API even when unchanged.

        Args:
            id: The ID of the watchlist to update.
            name: Unique name for the watchlist.
            risk_modifier: Risk score modifier associated with the watchlist
                (0-2).
            description: Description of the watchlist.
            managed: Whether the watchlist is managed by the system.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated watchlist.

        Raises:
            ApiError: If the watchlist does not exist (Kibana 9.4.3 answers
                500 ``"Watchlist config ... not found"`` rather than 404).
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.entity_analytics.update_watchlist(
            ...     id="b8b48d31-3026-45c0-aa8a-b8ed7f86ade8",
            ...     name="High Risk Vendors",
            ...     risk_modifier=1.8,
            ... )
            >>> print(updated.body["riskModifier"])
            1.8
        """
        body: dict[str, Any] = {"name": name, "riskModifier": risk_modifier}
        if description is not None:
            body["description"] = description
        if managed is not None:
            body["managed"] = managed

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/entity_analytics/watchlists/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_watchlist(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a watchlist by ID.

        Technical preview in 9.4.
        ``DELETE /api/entity_analytics/watchlists/{id}``. Deletes a
        watchlist. This route is supported by Kibana 9.4.3 but is not
        documented in its OpenAPI specification.

        Args:
            id: The ID of the watchlist to delete.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``deleted`` (bool).

        Raises:
            ApiError: If the watchlist does not exist (Kibana 9.4.3 answers
                500 ``"Watchlist config ... not found"`` rather than 404).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.delete_watchlist(
            ...     id="b8b48d31-3026-45c0-aa8a-b8ed7f86ade8"
            ... )
            >>> print(result.body["deleted"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/entity_analytics/watchlists/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    async def upload_watchlist_csv(
        self,
        *,
        watchlist_id: str,
        file: bytes | str,
        filename: str = "watchlist.csv",
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Upload a CSV file to add entities to a watchlist.

        Technical preview in 9.4.
        ``POST /api/entity_analytics/watchlists/{watchlist_id}/csv_upload``.
        Uploads a CSV file (as ``multipart/form-data``) whose rows identify
        entities to add to the watchlist. The CSV requires a header row that
        includes a ``type`` column (e.g. ``type,name``); entities are
        matched against the Entity Store, which must be installed.

        Args:
            watchlist_id: The ID of the watchlist.
            file: The CSV content as ``bytes`` or ``str``, including the
                header row (e.g. ``"type,name\\nuser,alice\\n"``).
            filename: Filename advertised in the multipart upload.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``total``, ``successful``, ``failed``,
            ``unmatched`` and per-row ``items``.

        Raises:
            ValueError: If ``file`` is empty.
            NotFoundError: If the watchlist does not exist.
            BadRequestError: If the CSV is malformed (e.g. missing the
                required ``type`` header field).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.upload_watchlist_csv(
            ...     watchlist_id="b8b48d31-3026-45c0-aa8a-b8ed7f86ade8",
            ...     file="type,name\\nuser,alice\\nhost,web-01\\n",
            ... )
            >>> print(result.body["successful"])
        """
        if not file:
            raise ValueError("Parameter 'file' is required")

        body, content_type = _build_csv_multipart_body(
            _csv_bytes(file), filename=filename
        )
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/entity_analytics/watchlists/{_quote(watchlist_id)}/csv_upload",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json", "content-type": content_type},
            body=body,  # type: ignore[arg-type]
        )

    async def assign_watchlist_entities(
        self,
        *,
        watchlist_id: str,
        euids: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Manually assign entities to a watchlist.

        Technical preview in 9.4 (added in 9.4.0).
        ``POST /api/entity_analytics/watchlists/{watchlist_id}/entities/assign``.
        Assigns Entity Store entities (by EUID) to the watchlist. The Entity
        Store must be installed.

        Args:
            watchlist_id: The ID of the watchlist.
            euids: The entity unique IDs (EUIDs) to assign, e.g.
                ``["host:web-01"]``.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``successful``, ``failed``, ``not_found``,
            ``total`` and per-entity ``items``.

        Raises:
            NotFoundError: If the watchlist does not exist or the Entity
                Store indices are missing.
            ApiError: Kibana 9.4.3 answers 500 ``"Unexpected entity store
                record"`` when the entity was created through the entity
                CRUD APIs and has not been materialized by the Entity Store
                transform.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.assign_watchlist_entities(
            ...     watchlist_id="b8b48d31-3026-45c0-aa8a-b8ed7f86ade8",
            ...     euids=["host:web-01"],
            ... )
            >>> print(result.body["successful"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/entity_analytics/watchlists/{_quote(watchlist_id)}/entities/assign",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"euids": euids},
        )

    async def unassign_watchlist_entities(
        self,
        *,
        watchlist_id: str,
        euids: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Manually unassign entities from a watchlist.

        Technical preview in 9.4 (added in 9.4.0). ``POST
        /api/entity_analytics/watchlists/{watchlist_id}/entities/unassign``.
        Removes manually-assigned Entity Store entities (by EUID) from the
        watchlist.

        Args:
            watchlist_id: The ID of the watchlist.
            euids: The entity unique IDs (EUIDs) to unassign.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``successful``, ``failed``, ``not_found``,
            ``total`` and per-entity ``items``.

        Raises:
            NotFoundError: If the watchlist does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.unassign_watchlist_entities(
            ...     watchlist_id="b8b48d31-3026-45c0-aa8a-b8ed7f86ade8",
            ...     euids=["host:web-01"],
            ... )
            >>> print(result.body["successful"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/entity_analytics/watchlists/{_quote(watchlist_id)}"
            "/entities/unassign",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"euids": euids},
        )

    # ------------------------------------------------------------------
    # Entity Store
    # ------------------------------------------------------------------

    async def install_entity_store(
        self,
        *,
        entity_types: list[str] | None = None,
        log_extraction: dict[str, Any] | None = None,
        history_snapshot: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Install the Entity Store.

        ``POST /api/security/entity_store/install``. Installs the Entity
        Store for the space, creating the entity indices, transforms and
        extraction tasks for the requested entity types.

        Args:
            entity_types: The entity types to install engines for, from
                ``"user"``, ``"host"``, ``"service"``, ``"generic"``.
                Defaults to all types on the server.
            log_extraction: Log extraction settings. Supports ``frequency``,
                ``lookbackPeriod``, ``delay``, ``fieldHistoryLength``,
                ``filter``, ``additionalIndexPatterns``,
                ``excludedIndexPatterns``, ``docsLimit``, ``maxLogsPerPage``,
                ``maxLogsPerWindow``, ``maxLogsPerWindowCapBehavior``
                (``"defer"``/``"drop"``) and ``maxTimeWindowSize``.
            history_snapshot: History snapshot settings
                (``{"frequency": "24h"}``).
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``ok`` (bool).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.install_entity_store(
            ...     entity_types=["host"],
            ...     log_extraction={"frequency": "5m", "lookbackPeriod": "12h"},
            ... )
            >>> print(result.body["ok"])
            True
        """
        body: dict[str, Any] = {}
        if entity_types is not None:
            body["entityTypes"] = entity_types
        if log_extraction is not None:
            body["logExtraction"] = log_extraction
        if history_snapshot is not None:
            body["historySnapshot"] = history_snapshot

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/security/entity_store/install", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def uninstall_entity_store(
        self,
        *,
        entity_types: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Uninstall the Entity Store.

        ``POST /api/security/entity_store/uninstall``. Uninstalls Entity
        Store engines, removing their transforms, tasks and indices. When
        ``entity_types`` is omitted, all engines are uninstalled.

        Args:
            entity_types: The entity types to uninstall engines for, from
                ``"user"``, ``"host"``, ``"service"``, ``"generic"``.
                Defaults to all installed types.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``ok`` (bool).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.uninstall_entity_store()
            >>> print(result.body["ok"])
            True
        """
        body: dict[str, Any] = {}
        if entity_types is not None:
            body["entityTypes"] = entity_types

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/security/entity_store/uninstall", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def update_entity_store(
        self,
        *,
        log_extraction: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update the Entity Store configuration.

        ``PUT /api/security/entity_store``. Updates the log extraction
        configuration of the installed Entity Store.

        Args:
            log_extraction: The log extraction settings to update. Supports
                the same keys as :meth:`install_entity_store`
                (``frequency``, ``lookbackPeriod``, ``delay``,
                ``fieldHistoryLength``, ``filter``,
                ``additionalIndexPatterns``, ``excludedIndexPatterns``,
                ``docsLimit``, ``maxLogsPerPage``, ``maxLogsPerWindow``,
                ``maxLogsPerWindowCapBehavior``, ``maxTimeWindowSize``).
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``ok`` (bool).

        Raises:
            BadRequestError: If the request body is invalid.
            NotFoundError: If the Entity Store is not installed.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.update_entity_store(
            ...     log_extraction={"frequency": "10m", "lookbackPeriod": "6h"}
            ... )
            >>> print(result.body["ok"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/security/entity_store", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body={"logExtraction": log_extraction},
        )

    async def get_entity_store_status(
        self,
        *,
        include_components: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the status of the Entity Store.

        ``GET /api/security/entity_store/status``. Returns the overall
        Entity Store status (``"not_installed"``, ``"installing"``,
        ``"running"``, ``"stopped"`` or ``"error"``) and the status of each
        engine.

        Args:
            include_components: If True, include the status of the Entity
                Store's underlying components (transforms, index templates,
                indices, tasks, ...) for each engine.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``status`` and ``engines`` (per-engine
            ``type``, ``status`` and configuration; plus ``components`` when
            requested).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> status = await client.entity_analytics.get_entity_store_status(
            ...     include_components=True
            ... )
            >>> print(status.body["status"])
            running
        """
        params: dict[str, Any] = {}
        if include_components is not None:
            params["include_components"] = include_components

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/security/entity_store/status", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def start_entity_store(
        self,
        *,
        entity_types: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Start Entity Store engines.

        ``PUT /api/security/entity_store/start``. Starts (resumes) the
        installed Entity Store engines. When ``entity_types`` is omitted,
        all installed engines are started.

        Args:
            entity_types: The entity types whose engines to start, from
                ``"user"``, ``"host"``, ``"service"``, ``"generic"``.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``ok`` (bool).

        Raises:
            NotFoundError: If the Entity Store is not installed.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.start_entity_store()
            >>> print(result.body["ok"])
            True
        """
        body: dict[str, Any] = {}
        if entity_types is not None:
            body["entityTypes"] = entity_types

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/security/entity_store/start", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def stop_entity_store(
        self,
        *,
        entity_types: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Stop Entity Store engines.

        ``PUT /api/security/entity_store/stop``. Stops (pauses) the
        installed Entity Store engines without uninstalling them. When
        ``entity_types`` is omitted, all installed engines are stopped.

        Args:
            entity_types: The entity types whose engines to stop, from
                ``"user"``, ``"host"``, ``"service"``, ``"generic"``.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``ok`` (bool).

        Raises:
            NotFoundError: If the Entity Store is not installed.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.stop_entity_store()
            >>> print(result.body["ok"])
            True
        """
        body: dict[str, Any] = {}
        if entity_types is not None:
            body["entityTypes"] = entity_types

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/security/entity_store/stop", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def list_entities(
        self,
        *,
        filter: str | None = None,
        size: int | None = None,
        search_after: str | None = None,
        source: list[str] | None = None,
        fields: list[str] | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        filter_query: str | None = None,
        entity_types: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List Entity Store entities.

        ``GET /api/security/entity_store/entities``. Lists entities stored
        in the Entity Store, with paging, sorting and filtering.

        Args:
            filter: An ES query-string filter
                (e.g. ``'host.name: "web-01"'``).
            size: Maximum number of entities to return (cursor-style
                pagination, used with ``search_after``).
            search_after: Cursor returned by a previous call, to fetch the
                next batch of results.
            source: Index patterns to search for entities.
            fields: Restrict the entity fields returned.
            sort_field: The field to sort by.
            sort_order: The sort order: ``"asc"`` or ``"desc"``.
            page: The page number to return (page-style pagination).
            per_page: The number of entities per page (up to 10000).
            filter_query: An additional filter as a JSON DSL query string.
            entity_types: Restrict results to these entity types, from
                ``"user"``, ``"host"``, ``"service"``, ``"generic"``.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``records``, ``total``, ``page``,
            ``per_page`` and an ``inspect`` object with the executed query.

        Raises:
            NotFoundError: If the Entity Store indices do not exist.
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> entities = await client.entity_analytics.list_entities(
            ...     entity_types=["host"],
            ...     sort_field="entity.name",
            ...     sort_order="asc",
            ...     per_page=100,
            ... )
            >>> print(entities.body["total"])
        """
        params: dict[str, Any] = {}
        if filter is not None:
            params["filter"] = filter
        if size is not None:
            params["size"] = size
        if search_after is not None:
            params["searchAfter"] = search_after
        if source is not None:
            params["source"] = source
        if fields is not None:
            params["fields"] = fields
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if filter_query is not None:
            params["filterQuery"] = filter_query
        if entity_types is not None:
            params["entity_types"] = entity_types

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/security/entity_store/entities", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def create_entity(
        self,
        *,
        entity_type: str,
        document: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an Entity Store entity.

        ``POST /api/security/entity_store/entities/{entityType}``. Creates
        an entity document directly in the Entity Store. The Entity Store
        must be installed for the given entity type.

        Args:
            entity_type: The entity type: ``"user"``, ``"host"``,
                ``"service"`` or ``"generic"``.
            document: The entity document. Must contain the type's identity
                field (e.g. ``{"host": {"name": "web-01"}}`` for hosts) and
                supports ``entity``, ``asset``, ``labels``, ``tags``,
                ``event`` and ``@timestamp``. If ``entity.id`` is provided
                it must match the EUID the server generates
                (e.g. ``"host:web-01"``).
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``ok`` (bool).

        Raises:
            BadRequestError: If the document is invalid (e.g. a supplied
                ``entity.id`` doesn't match the generated EUID).
            NotFoundError: If the Entity Store is not installed for the
                entity type.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.create_entity(
            ...     entity_type="host",
            ...     document={"host": {"name": "web-01"}},
            ... )
            >>> print(result.body["ok"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/security/entity_store/entities/{_quote(entity_type)}", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=document,
        )

    async def update_entity(
        self,
        *,
        entity_type: str,
        document: dict[str, Any],
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update an Entity Store entity.

        ``PUT /api/security/entity_store/entities/{entityType}``. Updates
        (upserts) an entity document in the Entity Store.

        Args:
            entity_type: The entity type: ``"user"``, ``"host"``,
                ``"service"`` or ``"generic"``.
            document: The entity document to apply. Must contain the type's
                identity field (e.g. ``{"host": {"name": "web-01"}}``).
            force: If True, force the update even when the entity does not
                already exist. Defaults to False on the server.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``ok`` (bool).

        Raises:
            BadRequestError: If the document is invalid.
            NotFoundError: If the entity does not exist and ``force`` is not
                set, or the Entity Store is not installed.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.update_entity(
            ...     entity_type="host",
            ...     document={
            ...         "host": {"name": "web-01"},
            ...         "labels": {"env": "prod"},
            ...     },
            ...     force=True,
            ... )
            >>> print(result.body["ok"])
            True
        """
        params: dict[str, Any] = {}
        if force is not None:
            params["force"] = force

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/security/entity_store/entities/{_quote(entity_type)}", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
            body=document,
        )

    async def bulk_update_entities(
        self,
        *,
        entities: list[dict[str, Any]],
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Bulk update Entity Store entities.

        ``PUT /api/security/entity_store/entities/bulk``. Updates (upserts)
        multiple entity documents in a single request.

        Args:
            entities: The entities to update. Each entry requires ``type``
                (``"user"``, ``"host"``, ``"service"`` or ``"generic"``)
                and ``doc`` (the entity document, as accepted by
                :meth:`update_entity`). Unlike :meth:`create_entity`, bulk
                updates do not create missing documents (even with
                ``force``): those rows are reported in ``errors`` as 404
                ``document_missing_exception`` items.
            force: If True, force the updates. Defaults to False on the
                server.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``ok`` (bool) and per-entity ``errors``.

        Raises:
            BadRequestError: If the request body is invalid.
            NotFoundError: If the Entity Store is not installed.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.bulk_update_entities(
            ...     entities=[
            ...         {"type": "host", "doc": {"host": {"name": "web-01"}}},
            ...         {"type": "user", "doc": {"user": {"name": "alice"}}},
            ...     ],
            ...     force=True,
            ... )
            >>> print(result.body["ok"], result.body["errors"])
            True []
        """
        params: dict[str, Any] = {}
        if force is not None:
            params["force"] = force

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security/entity_store/entities/bulk", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
            body={"entities": entities},
        )

    async def delete_entity(
        self,
        *,
        entity_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an Entity Store entity.

        ``DELETE /api/security/entity_store/entities/``. Deletes an entity
        document from the Entity Store by its EUID.

        Args:
            entity_id: The entity unique ID (EUID) of the entity to delete,
                e.g. ``"host:web-01"``.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``deleted`` (bool).

        Raises:
            NotFoundError: If the entity or the Entity Store indices do not
                exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.delete_entity(
            ...     entity_id="host:web-01"
            ... )
            >>> print(result.body["deleted"])
            True
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/security/entity_store/entities/", space_id)
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
            body={"entityId": entity_id},
        )

    async def get_entity_resolution_group(
        self,
        *,
        entity_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the resolution group of an entity.

        ``GET /api/security/entity_store/resolution/group``. Returns the
        resolution group for an entity: the target (canonical) entity and
        the alias entities linked to it.

        Args:
            entity_id: The entity unique ID (EUID) of the entity,
                e.g. ``"host:web-01"``.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``target`` (the canonical entity
            document), ``aliases`` (linked entities) and ``group_size``.

        Raises:
            NotFoundError: If the entity does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> group = await client.entity_analytics.get_entity_resolution_group(
            ...     entity_id="host:web-01"
            ... )
            >>> print(group.body["group_size"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security/entity_store/resolution/group", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            params={"entity_id": entity_id},
            headers={"accept": "application/json"},
        )

    async def link_entities(
        self,
        *,
        entity_ids: list[str],
        target_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Link entities to a target entity (entity resolution).

        ``POST /api/security/entity_store/resolution/link``. Marks the
        given entities as aliases of the target entity, merging them into
        one resolution group.

        Args:
            entity_ids: The EUIDs of the entities to link as aliases.
            target_id: The EUID of the target (canonical) entity.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``linked``, ``skipped`` and ``target_id``.

        Raises:
            NotFoundError: If an entity does not exist.
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.link_entities(
            ...     entity_ids=["host:web-01.internal"],
            ...     target_id="host:web-01",
            ... )
            >>> print(result.body["linked"])
            ['host:web-01.internal']
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security/entity_store/resolution/link", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"entity_ids": entity_ids, "target_id": target_id},
        )

    async def unlink_entities(
        self,
        *,
        entity_ids: list[str],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Unlink entities from their resolution group.

        ``POST /api/security/entity_store/resolution/unlink``. Removes the
        alias links of the given entities, splitting them out of their
        resolution group.

        Args:
            entity_ids: The EUIDs of the entities to unlink.
            space_id: Optional space ID for space-scoped operations.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``unlinked`` and ``skipped``.

        Raises:
            NotFoundError: If an entity does not exist.
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.entity_analytics.unlink_entities(
            ...     entity_ids=["host:web-01.internal"]
            ... )
            >>> print(result.body["unlinked"])
            ['host:web-01.internal']
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security/entity_store/resolution/unlink", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body={"entity_ids": entity_ids},
        )
