"""Async Kibana Security Osquery API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class AsyncOsqueryClient(AsyncNamespaceClient):
    """Async client for the Kibana Security Osquery API.

    Run live queries against Elastic Agents with Osquery Manager, and manage
    reusable saved queries and scheduled query packs. The Osquery integration
    must be added to an agent policy for queries to actually execute on hosts.

    The API manages three resource types:

    - **Packs** (``/api/osquery/packs``): named sets of queries scheduled to
      run at an interval on the agent policies the pack is assigned to.
    - **Saved queries** (``/api/osquery/saved_queries``): reusable single
      queries that can be run as live queries or included in packs.
    - **Live queries** (``/api/osquery/live_queries``): one-off queries
      dispatched to a selection of agents, with per-action results.

    All Osquery resources are space-aware: every method accepts an optional
    ``space_id`` to target a specific space (``None`` targets the default
    space or the space the client is scoped to).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create a pack with one scheduled query
        >>> pack = await client.osquery.create_pack(
        ...     name="my_pack",
        ...     queries={
        ...         "uptime": {"query": "select * from uptime;", "interval": 3600}
        ...     },
        ... )
        >>> pack_id = pack.body["data"]["saved_object_id"]
        >>>
        >>> # Run a live query on all agents and fetch its results
        >>> live = await client.osquery.create_live_query(
        ...     query="select * from uptime;", agent_all=True
        ... )
        >>> action_id = live.body["data"]["action_id"]
        >>> details = await client.osquery.get_live_query(id=action_id)
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncOsqueryClient.

        Args:
            client: The parent AsyncKibana client instance to delegate
                requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> osquery_client = AsyncOsqueryClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    # ------------------------------------------------------------------
    # Packs
    # ------------------------------------------------------------------

    async def create_pack(
        self,
        *,
        name: str,
        queries: dict[str, Any],
        description: str | None = None,
        enabled: bool | None = None,
        policy_ids: list[str] | None = None,
        shards: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a query pack.

        Creates an Osquery pack: a named set of queries that are scheduled to
        run on the agent policies the pack is assigned to.

        Args:
            name: The pack name.
            queries: An object of queries keyed by query ID. Each value may
                contain ``query`` (the SQL to run), ``interval`` (seconds
                between runs), ``platform``, ``version``, ``ecs_mapping``,
                ``snapshot`` and ``removed``. Kibana requires ``query`` and
                ``interval`` for each entry.
            description: The pack description.
            enabled: Enables the pack. Enabled packs run on the agent
                policies listed in ``policy_ids``.
            policy_ids: A list of agent policy IDs to schedule the pack on.
            shards: An object with shard configuration for policies included
                in the pack. For each policy, set the shard configuration to
                a percentage (1-100) of target hosts.
            space_id: Optional space ID to create the pack in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose ``data`` object contains the created pack,
            including ``saved_object_id`` (use it for get/update/delete),
            ``name``, ``queries``, ``enabled`` and audit metadata.

        Raises:
            BadRequestError: If required fields are missing or invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> pack = await client.osquery.create_pack(
            ...     name="my_pack",
            ...     description="Track uptime",
            ...     enabled=False,
            ...     queries={
            ...         "uptime": {
            ...             "query": "select * from uptime;",
            ...             "interval": 3600,
            ...         }
            ...     },
            ... )
            >>> print(pack.body["data"]["saved_object_id"])
        """
        body: dict[str, Any] = {
            "name": name,
            "queries": queries,
        }
        if description is not None:
            body["description"] = description
        if enabled is not None:
            body["enabled"] = enabled
        if policy_ids is not None:
            body["policy_ids"] = policy_ids
        if shards is not None:
            body["shards"] = shards

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/osquery/packs", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def find_packs(
        self,
        *,
        page: int | None = None,
        page_size: int | None = None,
        sort: str | None = None,
        sort_order: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a list of all query packs.

        Args:
            page: The page number to return. The default is 1.
            page_size: The number of results to return per page. The default
                is 20.
            sort: The field that is used to sort the results. The default is
                ``createdAt``.
            sort_order: Specifies the sort order, either ``asc`` or ``desc``.
            space_id: Optional space ID to list packs from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``page``, ``per_page``, ``total`` and
            a ``data`` list of packs. Live Kibana 9.4.3 returns flattened
            pack objects (``name``, ``queries``, ``saved_object_id``, ...),
            not the ``id``/``attributes`` wrapper shown in the OpenAPI
            example.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> packs = await client.osquery.find_packs(page=1, page_size=10)
            >>> for pack in packs.body["data"]:
            ...     print(pack["saved_object_id"], pack["name"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        if sort is not None:
            params["sort"] = sort
        if sort_order is not None:
            params["sortOrder"] = sort_order

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/osquery/packs", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def get_pack(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the details of a query pack using the pack ID.

        Args:
            id: The ID of the pack you want to retrieve (the pack's saved
                object ID).
            space_id: Optional space ID to get the pack from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose ``data`` object contains the pack:
            ``name``, ``description``, ``enabled``, ``queries``,
            ``policy_ids``, ``read_only`` and audit metadata.

        Raises:
            NotFoundError: If the pack does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> pack = await client.osquery.get_pack(
            ...     id="3c42c847-eb30-4452-80e0-728584042334"
            ... )
            >>> print(pack.body["data"]["name"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/osquery/packs/{_quote(id)}", space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_pack(
        self,
        *,
        id: str,
        name: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
        policy_ids: list[str] | None = None,
        queries: dict[str, Any] | None = None,
        shards: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a query pack using the pack ID.

        You cannot update a prebuilt pack. Note that the live Kibana server
        treats this as a replacement update: optional fields omitted from the
        request (for example ``description``) may be reset to their defaults,
        so pass every field you want to keep.

        Args:
            id: The ID of the pack you want to update (the pack's saved
                object ID).
            name: The pack name.
            description: The pack description.
            enabled: Enables the pack.
            policy_ids: A list of agent policy IDs to schedule the pack on.
            queries: An object of queries keyed by query ID (same shape as in
                :meth:`create_pack`).
            shards: An object with shard configuration for policies included
                in the pack. For each policy, set the shard configuration to
                a percentage (1-100) of target hosts.
            space_id: Optional space ID the pack lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose ``data`` object contains the updated
            pack. Live Kibana 9.4.3 returns the flattened pack (as in
            :meth:`create_pack`) when ``enabled`` is included in the request,
            and the raw saved object (``attributes`` wrapper) otherwise.

        Raises:
            BadRequestError: If the request body is invalid or the pack is
                prebuilt.
            NotFoundError: If the pack does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.osquery.update_pack(
            ...     id="3c42c847-eb30-4452-80e0-728584042334",
            ...     name="updated_pack_name",
            ...     description="Still tracking uptime",
            ...     queries={
            ...         "uptime": {
            ...             "query": "select * from uptime;",
            ...             "interval": 3600,
            ...         }
            ...     },
            ... )
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if enabled is not None:
            body["enabled"] = enabled
        if policy_ids is not None:
            body["policy_ids"] = policy_ids
        if queries is not None:
            body["queries"] = queries
        if shards is not None:
            body["shards"] = shards

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/osquery/packs/{_quote(id)}", space_id)
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_pack(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a query pack using the pack ID.

        Args:
            id: The ID of the pack you want to delete (the pack's saved
                object ID).
            space_id: Optional space ID to delete the pack from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty object body on success.

        Raises:
            NotFoundError: If the pack does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.osquery.delete_pack(
            ...     id="3c42c847-eb30-4452-80e0-728584042334"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(f"/api/osquery/packs/{_quote(id)}", space_id)
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Saved queries
    # ------------------------------------------------------------------

    async def create_saved_query(
        self,
        *,
        id: str,
        query: str,
        interval: str,
        description: str | None = None,
        ecs_mapping: dict[str, Any] | None = None,
        platform: str | None = None,
        removed: bool | None = None,
        snapshot: bool | None = None,
        version: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a saved query.

        Creates a reusable Osquery saved query that can be run as a live
        query or added to packs.

        Args:
            id: The saved query identifier (its name, for example
                ``"my_saved_query"``). This is distinct from the saved object
                ID generated by Kibana.
            query: The SQL query you want to run.
            interval: An interval, in seconds, on which to run the query,
                as a string (for example ``"60"``). The live server rejects
                integer values.
            description: The saved query description.
            ecs_mapping: Map osquery results columns or static values to
                Elastic Common Schema (ECS) fields, for example
                ``{"host.uptime": {"field": "total_seconds"}}``.
            platform: Restricts the query to a specified platform. The
                default is all platforms. To specify multiple platforms, use
                commas, for example ``"linux,darwin"``.
            removed: Indicates whether the query is removed.
            snapshot: Indicates whether the query is a snapshot.
            version: Uses the Osquery versions greater than or equal to the
                specified version string.
            space_id: Optional space ID to create the saved query in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose ``data`` object contains the created
            saved query, including ``saved_object_id`` (use it for
            get/update/delete) and audit metadata.

        Raises:
            BadRequestError: If required fields are missing or invalid.
            ConflictError: If a saved query with the same ``id`` exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> saved = await client.osquery.create_saved_query(
            ...     id="my_saved_query",
            ...     query="select * from uptime;",
            ...     interval="60",
            ...     description="Host uptime",
            ...     ecs_mapping={"host.uptime": {"field": "total_seconds"}},
            ... )
            >>> print(saved.body["data"]["saved_object_id"])
        """
        body: dict[str, Any] = {
            "id": id,
            "query": query,
            "interval": interval,
        }
        if description is not None:
            body["description"] = description
        if ecs_mapping is not None:
            body["ecs_mapping"] = ecs_mapping
        if platform is not None:
            body["platform"] = platform
        if removed is not None:
            body["removed"] = removed
        if snapshot is not None:
            body["snapshot"] = snapshot
        if version is not None:
            body["version"] = version

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/osquery/saved_queries", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def find_saved_queries(
        self,
        *,
        page: int | None = None,
        page_size: int | None = None,
        sort: str | None = None,
        sort_order: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a list of all saved queries.

        Args:
            page: The page number to return. The default is 1.
            page_size: The number of results to return per page. The default
                is 20.
            sort: The field that is used to sort the results. The default is
                ``createdAt``.
            sort_order: Specifies the sort order, either ``asc`` or ``desc``.
            space_id: Optional space ID to list saved queries from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``page``, ``per_page``, ``total`` and
            a ``data`` list of saved queries. Live Kibana 9.4.3 returns
            flattened objects where ``id`` is the saved query name and
            ``saved_object_id`` is the saved object ID, not the
            ``id``/``attributes`` wrapper shown in the OpenAPI example.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> queries = await client.osquery.find_saved_queries(page_size=100)
            >>> for saved in queries.body["data"]:
            ...     print(saved["saved_object_id"], saved["id"])
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        if sort is not None:
            params["sort"] = sort
        if sort_order is not None:
            params["sortOrder"] = sort_order

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/osquery/saved_queries", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def get_saved_query(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the details of a saved query using the query ID.

        Args:
            id: The ID of the saved query you want to retrieve (the saved
                query's saved object ID).
            space_id: Optional space ID to get the saved query from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose ``data`` object contains the saved query
            attributes (``id``, ``query``, ``interval``, ``ecs_mapping``,
            ``prebuilt``, ...) and audit metadata.

        Raises:
            NotFoundError: If the saved query does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> saved = await client.osquery.get_saved_query(
            ...     id="3c42c847-eb30-4452-80e0-728584042334"
            ... )
            >>> print(saved.body["data"]["query"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/osquery/saved_queries/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_saved_query(
        self,
        *,
        id: str,
        new_id: str,
        query: str | None = None,
        description: str | None = None,
        interval: str | None = None,
        ecs_mapping: dict[str, Any] | None = None,
        platform: str | None = None,
        removed: bool | None = None,
        snapshot: bool | None = None,
        version: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a saved query using the query ID.

        You cannot update a prebuilt saved query. Note that the live Kibana
        server treats this as a replacement update: optional fields omitted
        from the request (for example ``interval`` or ``description``) may be
        reset or removed, so pass every field you want to keep. Also note
        that while ``interval`` must be sent as a string, the server stores
        and returns it as an integer after an update.

        Args:
            id: The ID of the saved query you want to update (the saved
                query's saved object ID).
            new_id: The saved query identifier to set (the body ``id``
                field). Required by the server; pass the existing identifier
                to keep it unchanged, or a different one to rename the saved
                query.
            query: The SQL query you want to run.
            description: The saved query description.
            interval: An interval, in seconds, on which to run the query,
                as a string (for example ``"60"``).
            ecs_mapping: Map osquery results columns or static values to
                Elastic Common Schema (ECS) fields.
            platform: Restricts the query to a specified platform, for
                example ``"linux,darwin"``.
            removed: Indicates whether the query is removed.
            snapshot: Indicates whether the query is a snapshot.
            version: Uses the Osquery versions greater than or equal to the
                specified version string.
            space_id: Optional space ID the saved query lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose ``data`` object contains the updated
            saved query.

        Raises:
            BadRequestError: If the request body is invalid or the saved
                query is prebuilt.
            NotFoundError: If the saved query does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.osquery.update_saved_query(
            ...     id="3c42c847-eb30-4452-80e0-728584042334",
            ...     new_id="my_saved_query",
            ...     query="select * from uptime;",
            ...     interval="120",
            ... )
        """
        body: dict[str, Any] = {"id": new_id}
        if query is not None:
            body["query"] = query
        if description is not None:
            body["description"] = description
        if interval is not None:
            body["interval"] = interval
        if ecs_mapping is not None:
            body["ecs_mapping"] = ecs_mapping
        if platform is not None:
            body["platform"] = platform
        if removed is not None:
            body["removed"] = removed
        if snapshot is not None:
            body["snapshot"] = snapshot
        if version is not None:
            body["version"] = version

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/osquery/saved_queries/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_saved_query(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a saved query using the query ID.

        Args:
            id: The ID of the saved query you want to delete (the saved
                query's saved object ID).
            space_id: Optional space ID to delete the saved query from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty object body on success.

        Raises:
            NotFoundError: If the saved query does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.osquery.delete_saved_query(
            ...     id="3c42c847-eb30-4452-80e0-728584042334"
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/osquery/saved_queries/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Live queries
    # ------------------------------------------------------------------

    async def create_live_query(
        self,
        *,
        query: str | None = None,
        queries: list[dict[str, Any]] | None = None,
        saved_query_id: str | None = None,
        pack_id: str | None = None,
        agent_all: bool | None = None,
        agent_ids: list[str] | None = None,
        agent_platforms: list[str] | None = None,
        agent_policy_ids: list[str] | None = None,
        alert_ids: list[str] | None = None,
        case_ids: list[str] | None = None,
        event_ids: list[str] | None = None,
        ecs_mapping: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create and run a live query.

        Dispatches an Osquery query (or a pack of queries) to a selection of
        agents. Specify what to run via ``query``, ``queries``,
        ``saved_query_id`` or ``pack_id``, and select agents via
        ``agent_all``, ``agent_ids``, ``agent_platforms`` or
        ``agent_policy_ids``.

        Note: on a stack where no Elastic Agent has ever enrolled, the live
        server responds with a 500 ``index_not_found_exception`` (missing
        ``.fleet-agents`` index) instead of accepting the query.

        Args:
            query: The SQL query you want to run.
            queries: An array of queries to run. Each entry may contain
                ``id``, ``query``, ``platform``, ``version``,
                ``ecs_mapping``, ``snapshot`` and ``removed``.
            saved_query_id: The ID of a saved query to run.
            pack_id: The ID of the pack you want to run.
            agent_all: When True, the query runs on all agents.
            agent_ids: A list of agent IDs to run the query on.
            agent_platforms: A list of agent platforms to run the query on.
            agent_policy_ids: A list of agent policy IDs to run the query on.
            alert_ids: A list of alert IDs associated with the live query.
            case_ids: A list of case IDs associated with the live query.
            event_ids: A list of event IDs associated with the live query.
            ecs_mapping: Map osquery results columns or static values to
                Elastic Common Schema (ECS) fields.
            metadata: Custom metadata object associated with the live query.
            space_id: Optional space ID to run the live query in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose ``data`` object contains the queued live
            query: ``action_id``, ``agents``, ``expiration`` and a
            ``queries`` list with a per-query ``action_id`` (use it with
            :meth:`get_live_query_results`).

        Raises:
            BadRequestError: If the request body is invalid (e.g. no query
                and no pack specified).
            ApiError: If the query cannot be dispatched (e.g. no agents have
                ever enrolled on the stack).
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> live = await client.osquery.create_live_query(
            ...     query="select * from uptime;",
            ...     agent_all=True,
            ...     ecs_mapping={"host.uptime": {"field": "total_seconds"}},
            ... )
            >>> print(live.body["data"]["action_id"])
        """
        body: dict[str, Any] = {}
        if query is not None:
            body["query"] = query
        if queries is not None:
            body["queries"] = queries
        if saved_query_id is not None:
            body["saved_query_id"] = saved_query_id
        if pack_id is not None:
            body["pack_id"] = pack_id
        if agent_all is not None:
            body["agent_all"] = agent_all
        if agent_ids is not None:
            body["agent_ids"] = agent_ids
        if agent_platforms is not None:
            body["agent_platforms"] = agent_platforms
        if agent_policy_ids is not None:
            body["agent_policy_ids"] = agent_policy_ids
        if alert_ids is not None:
            body["alert_ids"] = alert_ids
        if case_ids is not None:
            body["case_ids"] = case_ids
        if event_ids is not None:
            body["event_ids"] = event_ids
        if ecs_mapping is not None:
            body["ecs_mapping"] = ecs_mapping
        if metadata is not None:
            body["metadata"] = metadata

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/osquery/live_queries", space_id)
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def find_live_queries(
        self,
        *,
        kuery: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        sort: str | None = None,
        sort_order: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a list of all live queries.

        Args:
            kuery: The kuery to filter the results by, for example
                ``"agent.id: 16d7caf5-efd2-4212-9b62-73dafc91fa13"``.
            page: The page number to return. The default is 1.
            page_size: The number of results to return per page. The default
                is 20.
            sort: The field that is used to sort the results. The default is
                ``createdAt``.
            sort_order: Specifies the sort order, either ``asc`` or ``desc``.
            space_id: Optional space ID to list live queries from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose ``data`` object contains the raw search
            response with an ``items`` list of live query actions.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> live_queries = await client.osquery.find_live_queries(page_size=10)
            >>> print(live_queries.body["data"]["total"])
        """
        params: dict[str, Any] = {}
        if kuery is not None:
            params["kuery"] = kuery
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        if sort is not None:
            params["sort"] = sort
        if sort_order is not None:
            params["sortOrder"] = sort_order

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path("/api/osquery/live_queries", space_id)
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    async def get_live_query(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the details of a live query using the query ID.

        Note: on the live Kibana 9.4.3 server, requesting an unknown live
        query ID returns a 500 error ("no elements in sequence") rather than
        a 404.

        Args:
            id: The ID of the live query result you want to retrieve (the
                live query ``action_id``).
            space_id: Optional space ID to get the live query from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose ``data`` object contains the live query
            details: ``action_id``, ``agents``, ``expiration``, ``status``
            and per-query result counts.

        Raises:
            ApiError: If the live query does not exist (the server returns
                a 500 rather than a 404) or another API error occurs.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> details = await client.osquery.get_live_query(
            ...     id="3c42c847-eb30-4452-80e0-728584042334"
            ... )
            >>> print(details.body["data"]["status"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/osquery/live_queries/{_quote(id)}", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def get_live_query_results(
        self,
        *,
        id: str,
        action_id: str,
        kuery: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        sort: str | None = None,
        sort_order: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get the results of a live query using the query action ID.

        Args:
            id: The ID of the live query result you want to retrieve (the
                live query ``action_id``).
            action_id: The ID of the query action that generated the live
                query results (the per-query ``action_id`` from the
                ``queries`` list of the live query).
            kuery: The kuery to filter the results by.
            page: The page number to return. The default is 1.
            page_size: The number of results to return per page. The default
                is 20.
            sort: The field that is used to sort the results. The default is
                ``createdAt``.
            sort_order: Specifies the sort order, either ``asc`` or ``desc``.
            space_id: Optional space ID to get the results from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose ``data`` object contains an ``edges``
            list of result documents and a ``total`` count.

        Raises:
            NotFoundError: If the query action does not exist ("Action not
                found").
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> results = await client.osquery.get_live_query_results(
            ...     id="3c42c847-eb30-4452-80e0-728584042334",
            ...     action_id="609c4c66-ba3d-43fa-afdd-53e244577aa0",
            ...     page_size=100,
            ... )
            >>> print(results.body["data"]["total"])
        """
        params: dict[str, Any] = {}
        if kuery is not None:
            params["kuery"] = kuery
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        if sort is not None:
            params["sort"] = sort
        if sort_order is not None:
            params["sortOrder"] = sort_order

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/osquery/live_queries/{_quote(id)}/results/{_quote(action_id)}",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )
