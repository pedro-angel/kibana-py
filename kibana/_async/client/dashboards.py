"""Async Kibana Dashboards API client."""

from __future__ import annotations

from typing import Any

from elastic_transport import ObjectApiResponse

from .utils import AsyncNamespaceClient, _quote


class AsyncDashboardsClient(AsyncNamespaceClient):
    """Async client for the Kibana Dashboards HTTP API.

    Technical preview in 9.4 (added in 9.4.0). The Dashboards API manages
    dashboards as code: each dashboard is addressed by its ID and represented
    by a flat ``data`` object. Responses are enveloped as
    ``{"id": ..., "data": {...}, "meta": {...}}`` where ``meta`` carries
    server-managed fields (``created_at``, ``updated_at``, ``created_by``,
    ``updated_by``, ``managed``, ``version``).

    The dashboard data model (the ``data`` object) supports:
        - ``title`` (required): human-readable dashboard title.
        - ``description``: short description of the dashboard.
        - ``panels``: list of panels and collapsible sections. Each panel has a
          ``type`` (e.g. ``"markdown"``, ``"vis"``, ``"image"``,
          ``"discover_session"``, control panels, SLO/synthetics/APM
          embeddables), a ``grid`` placement (``x``, ``y`` required; ``w`` up
          to 48, defaults 24; ``h`` defaults 15) and a type-specific
          ``config`` (either inline "by value" or ``ref_id`` "by reference").
          Sections are objects with a ``title``, ``collapsed`` flag and nested
          ``panels``.
        - ``options``: display/behavior settings (``auto_apply_filters``,
          ``hide_panel_borders``, ``hide_panel_titles``, ``sync_colors``,
          ``sync_cursor``, ``sync_tooltips``, ``use_margins``).
        - ``filters``: filters applied across all panels (simple condition
          filters, DSL filters, group filters or spatial filters).
        - ``query``: a search query ``{"expression": ..., "language": "kql" |
          "lucene"}`` applied to the dashboard.
        - ``time_range``: ``{"from": ..., "to": ..., "mode": "absolute" |
          "relative"}`` accepting date math (e.g. ``now-7d``) or ISO 8601
          timestamps.
        - ``refresh_interval``: ``{"pause": bool, "value": ms}`` auto-refresh
          setting.
        - ``tags``: list of tag IDs associated with the dashboard.
        - ``pinned_panels``: control panels and their state in the control
          group.
        - ``access_control``: ``{"access_mode": "default" |
          "write_restricted"}`` edit-access setting. Accepted only at
          creation time (:meth:`create`); ``PUT`` rejects it.
        - ``project_routing``: cross-project search routing behavior.

    Dashboards are space-scoped: every method accepts ``space_id`` to target
    a specific Kibana space (``None`` targets the default space or the
    client's default space).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a dashboard with a markdown panel
        >>> dashboard = await client.dashboards.create(
        ...     title="Team Overview",
        ...     panels=[
        ...         {
        ...             "type": "markdown",
        ...             "grid": {"x": 0, "y": 0, "w": 24, "h": 15},
        ...             "config": {"content": "# Welcome", "settings": {}},
        ...         }
        ...     ],
        ... )
        >>> dashboard_id = dashboard.body["id"]
        >>>
        >>> # Search dashboards
        >>> results = await client.dashboards.get_all(query="Team*")
        >>> for item in results.body["dashboards"]:
        ...     print(item["id"], item["data"]["title"])
    """

    async def get_all(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        query: str | None = None,
        tags: list[str] | None = None,
        excluded_tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Search dashboards.

        Technical preview in 9.4. Returns a paginated list of dashboards
        matching the search criteria. Each list entry contains summary fields
        (``title``, ``description``, ``tags``, ``time_range``,
        ``access_control``) but not the full panel layout — use :meth:`get`
        to retrieve a complete dashboard.

        Args:
            page: The page of results to return. Defaults to 1.
            per_page: The number of results to return per page. Defaults to 20.
            query: Filters results by ``title`` and ``description`` using
                Elasticsearch ``simple_query_string`` syntax (e.g.
                ``"sales*"``). Multi-word terms are OR-ed by default.
            tags: Tag IDs to include. When multiple are specified, dashboards
                matching any of the tag IDs are included (max 100).
            excluded_tags: Tag IDs to exclude. When multiple are specified,
                dashboards matching any of the tag IDs are excluded (max 100).
            space_id: Optional space ID to search dashboards in. ``None``
                targets the default space (or the client's default space).
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse whose body contains ``dashboards`` (a list of
            ``{"id", "data", "meta"}`` envelopes) plus ``page`` and
            ``total`` pagination fields.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.

        Example:
            >>> results = await client.dashboards.get_all(
            ...     query="sales*",
            ...     tags=["tag-id-1"],
            ...     per_page=10,
            ...     page=1,
            ... )
            >>> print(results.body["total"])
            >>> for item in results.body["dashboards"]:
            ...     print(item["id"], item["data"]["title"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if query is not None:
            params["query"] = query
        if tags is not None:
            params["tags"] = tags
        if excluded_tags is not None:
            params["excluded_tags"] = excluded_tags

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/dashboards", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params or None,
        )

    async def create(
        self,
        *,
        title: str,
        description: str | None = None,
        panels: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
        filters: list[dict[str, Any]] | None = None,
        query: dict[str, Any] | None = None,
        time_range: dict[str, Any] | None = None,
        refresh_interval: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        pinned_panels: list[dict[str, Any]] | None = None,
        access_control: dict[str, Any] | None = None,
        project_routing: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a dashboard.

        Technical preview in 9.4. Creates a dashboard with a server-assigned
        ID. The request body is the flat dashboard data object; the server
        rejects an ``id`` property in the body and assigns one itself. To
        create a dashboard with a custom ID, use :meth:`update`, which
        performs an upsert on ``PUT /api/dashboards/{id}``.

        Args:
            title: A human-readable title for the dashboard (required).
            description: A short description of the dashboard.
            panels: Panels and sections. Each panel is a dict with ``type``
                (e.g. ``"markdown"``, ``"vis"``, ``"image"``), ``grid``
                (``{"x", "y"}`` required, optional ``"w"`` <= 48 and ``"h"``)
                and a type-specific ``config`` (inline config or
                ``{"ref_id": ...}`` for library items). A section is a dict
                with ``title``, ``collapsed`` and nested ``panels``.
            options: Display and behavior settings, e.g.
                ``{"hide_panel_titles": True, "use_margins": False}``.
                Unspecified keys keep their server defaults.
            filters: Filters applied across all panels, including pinned
                panels (condition, DSL, group or spatial filters).
            query: Search query, e.g. ``{"expression": "status:active",
                "language": "kql"}`` (language is ``"kql"`` or ``"lucene"``).
            time_range: Time range, e.g. ``{"from": "now-7d", "to": "now",
                "mode": "relative"}``. ``from``/``to`` accept date math or
                ISO 8601 timestamps.
            refresh_interval: Auto-refresh setting ``{"pause": bool,
                "value": milliseconds}``.
            tags: Tag IDs to associate with this dashboard (max 100).
            pinned_panels: Control panels and their state in the control
                group.
            access_control: Access control settings, e.g. ``{"access_mode":
                "write_restricted"}`` to prevent edits by users without
                explicit write permission. Only settable at creation time —
                ``PUT /api/dashboards/{id}`` (:meth:`update`) rejects this
                field. Requires an identifiable user profile: under plain
                basic auth the server responds 400 ("Kibana could not
                determine the user profile ID for the caller").
            project_routing: Cross-project search routing behavior for the
                dashboard.
            space_id: Optional space ID to create the dashboard in.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse whose body is an ``{"id", "data", "meta"}``
            envelope for the created dashboard.

        Raises:
            ValueError: If ``title`` is missing.
            BadRequestError: If the dashboard data fails schema validation
                (including passing an ``id`` field via ``panels`` etc.).
            AuthenticationException: If authentication fails.

        Example:
            >>> dashboard = await client.dashboards.create(
            ...     title="Service health",
            ...     description="Ops overview",
            ...     tags=["ops-tag-id"],
            ...     time_range={"from": "now-24h", "to": "now"},
            ...     panels=[
            ...         {
            ...             "type": "markdown",
            ...             "grid": {"x": 0, "y": 0, "w": 48, "h": 6},
            ...             "config": {
            ...                 "content": "## Runbook links",
            ...                 "settings": {"open_links_in_new_tab": True},
            ...             },
            ...         }
            ...     ],
            ... )
            >>> print(dashboard.body["id"])
        """
        if not title:
            raise ValueError("Parameter 'title' is required")

        body: dict[str, Any] = {"title": title}
        if description is not None:
            body["description"] = description
        if panels is not None:
            body["panels"] = panels
        if options is not None:
            body["options"] = options
        if filters is not None:
            body["filters"] = filters
        if query is not None:
            body["query"] = query
        if time_range is not None:
            body["time_range"] = time_range
        if refresh_interval is not None:
            body["refresh_interval"] = refresh_interval
        if tags is not None:
            body["tags"] = tags
        if pinned_panels is not None:
            body["pinned_panels"] = pinned_panels
        if access_control is not None:
            body["access_control"] = access_control
        if project_routing is not None:
            body["project_routing"] = project_routing

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/dashboards", space_id)
        return await self.perform_request(
            "POST",
            path,
            body=body,
        )

    async def get(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a dashboard by ID.

        Technical preview in 9.4. Retrieves the full dashboard, including its
        complete panel layout.

        Args:
            id: The dashboard ID to retrieve.
            space_id: Optional space ID to get the dashboard from.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse whose body is an ``{"id", "data", "meta"}``
            envelope.

        Raises:
            ValueError: If ``id`` is missing.
            NotFoundError: If the dashboard does not exist.
            AuthenticationException: If authentication fails.

        Example:
            >>> dashboard = await client.dashboards.get(id="my-dashboard")
            >>> print(dashboard.body["data"]["title"])
            >>> for panel in dashboard.body["data"]["panels"]:
            ...     print(panel["type"], panel["grid"])
        """
        if not id:
            raise ValueError("Parameter 'id' is required")

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/dashboards/{_quote(id)}", space_id)
        return await self.perform_request(
            "GET",
            path,
        )

    async def update(
        self,
        *,
        id: str,
        title: str,
        description: str | None = None,
        panels: list[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
        filters: list[dict[str, Any]] | None = None,
        query: dict[str, Any] | None = None,
        time_range: dict[str, Any] | None = None,
        refresh_interval: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        pinned_panels: list[dict[str, Any]] | None = None,
        project_routing: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update (upsert) a dashboard by ID.

        Technical preview in 9.4. ``PUT /api/dashboards/{id}`` is an upsert:
        if the dashboard exists it is replaced with the provided data (the
        server responds 200); if it does not exist it is created with the
        given ID (the server responds 201). This is the way to create a
        dashboard with a custom ID, since :meth:`create` always assigns a
        server-generated ID and rejects an ``id`` in the body.

        Note that the provided data replaces the stored dashboard data —
        fields omitted from the call revert to their defaults rather than
        being preserved.

        Unlike :meth:`create`, this endpoint does not accept an
        ``access_control`` field — access control can only be set at
        creation time, and the server rejects it in a PUT body with a 400
        error.

        Args:
            id: The dashboard ID to update or create.
            title: A human-readable title for the dashboard (required).
            description: A short description of the dashboard.
            panels: Panels and sections. Each panel is a dict with ``type``
                (e.g. ``"markdown"``, ``"vis"``, ``"image"``), ``grid``
                (``{"x", "y"}`` required, optional ``"w"`` <= 48 and ``"h"``)
                and a type-specific ``config`` (inline config or
                ``{"ref_id": ...}`` for library items). A section is a dict
                with ``title``, ``collapsed`` and nested ``panels``.
            options: Display and behavior settings, e.g.
                ``{"hide_panel_titles": True, "use_margins": False}``.
            filters: Filters applied across all panels, including pinned
                panels (condition, DSL, group or spatial filters).
            query: Search query, e.g. ``{"expression": "status:active",
                "language": "kql"}`` (language is ``"kql"`` or ``"lucene"``).
            time_range: Time range, e.g. ``{"from": "now-7d", "to": "now",
                "mode": "relative"}``. ``from``/``to`` accept date math or
                ISO 8601 timestamps.
            refresh_interval: Auto-refresh setting ``{"pause": bool,
                "value": milliseconds}``.
            tags: Tag IDs to associate with this dashboard (max 100).
            pinned_panels: Control panels and their state in the control
                group.
            project_routing: Cross-project search routing behavior for the
                dashboard.
            space_id: Optional space ID where the dashboard lives.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse whose body is an ``{"id", "data", "meta"}``
            envelope for the updated or newly created dashboard.

        Raises:
            ValueError: If ``id`` or ``title`` is missing.
            BadRequestError: If the dashboard data fails schema validation.
            AuthenticationException: If authentication fails.

        Example:
            >>> # Create a dashboard with a custom ID (upsert)
            >>> dashboard = await client.dashboards.update(
            ...     id="team-overview",
            ...     title="Team Overview",
            ... )
            >>>
            >>> # Replace its content later
            >>> dashboard = await client.dashboards.update(
            ...     id="team-overview",
            ...     title="Team Overview v2",
            ...     tags=["team-tag-id"],
            ... )
        """
        if not id:
            raise ValueError("Parameter 'id' is required")
        if not title:
            raise ValueError("Parameter 'title' is required")

        body: dict[str, Any] = {"title": title}
        if description is not None:
            body["description"] = description
        if panels is not None:
            body["panels"] = panels
        if options is not None:
            body["options"] = options
        if filters is not None:
            body["filters"] = filters
        if query is not None:
            body["query"] = query
        if time_range is not None:
            body["time_range"] = time_range
        if refresh_interval is not None:
            body["refresh_interval"] = refresh_interval
        if tags is not None:
            body["tags"] = tags
        if pinned_panels is not None:
            body["pinned_panels"] = pinned_panels
        if project_routing is not None:
            body["project_routing"] = project_routing

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/dashboards/{_quote(id)}", space_id)
        return await self.perform_request(
            "PUT",
            path,
            body=body,
        )

    async def delete(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a dashboard by ID.

        Technical preview in 9.4. Permanently deletes the dashboard. The
        server responds 204 with an empty body on success.

        Args:
            id: The dashboard ID to delete.
            space_id: Optional space ID to delete the dashboard from.
            validate_spaces: Override space-existence validation for this call.

        Returns:
            ObjectApiResponse, empty for successful deletion (HTTP 204).

        Raises:
            ValueError: If ``id`` is missing.
            NotFoundError: If the dashboard does not exist.
            AuthenticationException: If authentication fails.

        Example:
            >>> await client.dashboards.delete(id="team-overview")
        """
        if not id:
            raise ValueError("Parameter 'id' is required")

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/dashboards/{_quote(id)}", space_id)
        return await self.perform_request(
            "DELETE",
            path,
        )
