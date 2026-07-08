"""Kibana Agent Builder API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


class AgentBuilderClient(NamespaceClient):
    """Client for the Kibana Agent Builder API.

    Agent Builder lets you create and manage AI agents, tools, skills and
    plugins, chat with agents (with conversation persistence and
    attachments), and expose agents through the A2A and MCP protocols.

    The core Agent Builder APIs (agents, tools, conversations, converse,
    A2A, MCP) are generally available since Kibana 9.2.0. The attachments,
    consumption, skills and plugins APIs are in technical preview (added in
    9.2.0-9.4.0). Chat-related operations (converse, A2A tasks, MCP tool
    calls) require a configured LLM connector.

    Agent Builder resources are space-scoped: every method accepts an
    optional ``space_id`` to target a specific space (``None`` targets the
    default space or the space the client is scoped to).

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create an ES|QL tool and an agent that can use it
        >>> client.agent_builder.create_tool(
        ...     id="my_ns.lookup",
        ...     type="esql",
        ...     description="Look up documents",
        ...     configuration={"query": "FROM my-index | LIMIT 10", "params": {}},
        ... )
        >>> client.agent_builder.create_agent(
        ...     id="my-agent",
        ...     name="My Agent",
        ...     description="Searches my data",
        ...     configuration={"tools": [{"tool_ids": ["my_ns.lookup"]}]},
        ... )
        >>>
        >>> # Chat with it (requires an LLM connector)
        >>> reply = client.agent_builder.converse(
        ...     input="What data do I have?", agent_id="my-agent"
        ... )
        >>> print(reply.body["response"]["message"])
    """

    def __init__(
        self,
        client: Kibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AgentBuilderClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> agent_builder_client = AgentBuilderClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    def list_agents(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List agents.

        ``GET /api/agent_builder/agents``. Generally available; added in
        9.2.0. Returns all agents visible to the current user, including the
        built-in Elastic AI agent.

        Args:
            space_id: Optional space ID to list agents from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing a ``results`` list of agent
            definitions (``id``, ``type``, ``name``, ``description``,
            ``configuration``, ``labels``, ``visibility``, ``readonly``...).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> agents = client.agent_builder.list_agents()
            >>> for agent in agents.body["results"]:
            ...     print(agent["id"], agent["name"])
        """
        path = self._build_space_path(
            "/api/agent_builder/agents", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def create_agent(
        self,
        *,
        id: str,
        name: str,
        description: str,
        configuration: dict[str, Any],
        avatar_color: str | None = None,
        avatar_symbol: str | None = None,
        labels: list[str] | None = None,
        visibility: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create an agent.

        ``POST /api/agent_builder/agents``. Generally available; added in
        9.2.0.

        Args:
            id: Unique identifier for the agent.
            name: Display name for the agent.
            description: Description of what the agent does.
            configuration: Configuration settings for the agent. Requires a
                ``tools`` key (a list of ``{"tool_ids": [...]}`` selections)
                and optionally ``instructions``, ``skill_ids``,
                ``plugin_ids``, ``workflow_ids`` and
                ``enable_elastic_capabilities``.
            avatar_color: Optional hex color code for the agent avatar.
            avatar_symbol: Optional symbol/initials for the agent avatar.
            labels: Optional labels for categorizing and organizing agents.
            visibility: Optional visibility setting: ``"public"``,
                ``"shared"`` or ``"private"``. Technical preview; added in
                9.4.0.
            space_id: Optional space ID to create the agent in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created agent definition.

        Raises:
            BadRequestError: If the request body is invalid or the agent ID
                already exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> created = client.agent_builder.create_agent(
            ...     id="search-helper",
            ...     name="Search Helper",
            ...     description="Helps searching content indices",
            ...     configuration={
            ...         "instructions": "Search indices prefixed content-.",
            ...         "tools": [{"tool_ids": ["platform.core.search"]}],
            ...     },
            ...     labels=["search"],
            ... )
            >>> print(created.body["id"])
            search-helper
        """
        body: dict[str, Any] = {
            "id": id,
            "name": name,
            "description": description,
            "configuration": configuration,
        }
        if avatar_color is not None:
            body["avatar_color"] = avatar_color
        if avatar_symbol is not None:
            body["avatar_symbol"] = avatar_symbol
        if labels is not None:
            body["labels"] = labels
        if visibility is not None:
            body["visibility"] = visibility

        path = self._build_space_path(
            "/api/agent_builder/agents", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_agent(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an agent by ID.

        ``GET /api/agent_builder/agents/{id}``. Generally available; added
        in 9.2.0.

        Args:
            id: The unique identifier of the agent.
            space_id: Optional space ID to get the agent from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the agent definition.

        Raises:
            NotFoundError: If the agent does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> agent = client.agent_builder.get_agent(id="elastic-ai-agent")
            >>> print(agent.body["name"])
            Elastic AI Agent
        """
        path = self._build_space_path(
            f"/api/agent_builder/agents/{_quote(id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def update_agent(
        self,
        *,
        id: str,
        name: str | None = None,
        description: str | None = None,
        configuration: dict[str, Any] | None = None,
        avatar_color: str | None = None,
        avatar_symbol: str | None = None,
        labels: list[str] | None = None,
        visibility: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update an agent.

        ``PUT /api/agent_builder/agents/{id}``. Generally available; added
        in 9.2.0. Performs a partial update: only the provided fields are
        changed.

        Args:
            id: The unique identifier of the agent to update.
            name: Updated display name for the agent.
            description: Updated description of what the agent does.
            configuration: Updated configuration settings for the agent
                (see :meth:`AgentBuilderClient.create_agent`).
            avatar_color: Updated hex color code for the agent avatar.
            avatar_symbol: Updated symbol/initials for the agent avatar.
            labels: Updated labels for categorizing and organizing agents.
            visibility: Updated visibility setting: ``"public"``,
                ``"shared"`` or ``"private"``. Technical preview; added in
                9.4.0.
            space_id: Optional space ID the agent lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated agent definition.

        Raises:
            NotFoundError: If the agent does not exist.
            BadRequestError: If the request body is invalid or the agent is
                read-only.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> updated = client.agent_builder.update_agent(
            ...     id="search-helper", description="Updated description"
            ... )
            >>> print(updated.body["description"])
            Updated description
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if configuration is not None:
            body["configuration"] = configuration
        if avatar_color is not None:
            body["avatar_color"] = avatar_color
        if avatar_symbol is not None:
            body["avatar_symbol"] = avatar_symbol
        if labels is not None:
            body["labels"] = labels
        if visibility is not None:
            body["visibility"] = visibility

        path = self._build_space_path(
            f"/api/agent_builder/agents/{_quote(id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def delete_agent(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete an agent.

        ``DELETE /api/agent_builder/agents/{id}``. Generally available;
        added in 9.2.0. Built-in (read-only) agents cannot be deleted.

        Args:
            id: The unique identifier of the agent to delete.
            space_id: Optional space ID the agent lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``{"success": true}`` on success.

        Raises:
            NotFoundError: If the agent does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = client.agent_builder.delete_agent(id="search-helper")
            >>> print(result.body["success"])
            True
        """
        path = self._build_space_path(
            f"/api/agent_builder/agents/{_quote(id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    def get_agent_consumption(
        self,
        *,
        agent_id: str,
        has_warnings: bool | None = None,
        search: str | None = None,
        search_after: list[Any] | None = None,
        size: int | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        usernames: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get agent consumption data.

        ``POST /api/agent_builder/agents/{agent_id}/consumption``. Technical
        preview; added in 9.4.0. Returns per-conversation token consumption
        aggregates for the given agent.

        Args:
            agent_id: The unique identifier of the agent.
            has_warnings: Filter to conversations with or without high-token
                warnings.
            search: Free-text search filter on conversation title.
            search_after: Cursor for pagination. Pass the ``search_after``
                value from the previous response.
            size: Number of results per page (1-100, default 25).
            sort_field: Field to sort results by: ``"updated_at"``,
                ``"total_tokens"`` or ``"round_count"`` (default
                ``"updated_at"``).
            sort_order: Sort direction: ``"asc"`` or ``"desc"`` (default
                ``"desc"``).
            usernames: Filter results to conversations by these usernames.
            space_id: Optional space ID the agent lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the consumption results and
            pagination cursor.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> consumption = client.agent_builder.get_agent_consumption(
            ...     agent_id="elastic-ai-agent",
            ...     size=10,
            ...     sort_field="total_tokens",
            ... )
        """
        body: dict[str, Any] = {}
        if has_warnings is not None:
            body["has_warnings"] = has_warnings
        if search is not None:
            body["search"] = search
        if search_after is not None:
            body["search_after"] = search_after
        if size is not None:
            body["size"] = size
        if sort_field is not None:
            body["sort_field"] = sort_field
        if sort_order is not None:
            body["sort_order"] = sort_order
        if usernames is not None:
            body["usernames"] = usernames

        path = self._build_space_path(
            f"/api/agent_builder/agents/{_quote(agent_id)}/consumption",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def list_tools(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List tools.

        ``GET /api/agent_builder/tools``. Generally available; added in
        9.2.0. Returns all tools, including the built-in ``platform.*``
        tools.

        Args:
            space_id: Optional space ID to list tools from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing a ``results`` list of tool
            definitions (``id``, ``type``, ``description``, ``tags``,
            ``configuration``, ``schema``, ``readonly``).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> tools = client.agent_builder.list_tools()
            >>> for tool in tools.body["results"]:
            ...     print(tool["id"], tool["type"])
        """
        path = self._build_space_path(
            "/api/agent_builder/tools", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def create_tool(
        self,
        *,
        id: str,
        type: str,
        configuration: dict[str, Any],
        description: str | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a tool.

        ``POST /api/agent_builder/tools``. Generally available; added in
        9.2.0.

        Args:
            id: Unique identifier for the tool. Tool IDs are namespaced with
                dots (e.g. ``"my_namespace.my_tool"``).
            type: The type of tool to create: ``"esql"``,
                ``"index_search"``, ``"workflow"`` or ``"mcp"``.
            configuration: Tool-specific configuration parameters. For an
                ``esql`` tool: ``{"query": "FROM idx | LIMIT 10",
                "params": {}}``; for an ``index_search`` tool:
                ``{"pattern": "my-index-*"}``.
            description: Description of what the tool does.
            tags: Optional tags for categorizing and organizing tools.
            space_id: Optional space ID to create the tool in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created tool definition,
            including the derived parameter ``schema``.

        Raises:
            BadRequestError: If the request body is invalid or the tool ID
                already exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> created = client.agent_builder.create_tool(
            ...     id="my_ns.error_count",
            ...     type="esql",
            ...     description="Count error logs",
            ...     configuration={
            ...         "query": "FROM logs-* | WHERE level == \\"error\\" | STATS COUNT(*)",
            ...         "params": {},
            ...     },
            ... )
            >>> print(created.body["id"])
            my_ns.error_count
        """
        body: dict[str, Any] = {
            "id": id,
            "type": type,
            "configuration": configuration,
        }
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags

        path = self._build_space_path(
            "/api/agent_builder/tools", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_tool(
        self,
        *,
        tool_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a tool by ID.

        ``GET /api/agent_builder/tools/{toolId}``. Generally available;
        added in 9.2.0.

        Args:
            tool_id: The unique identifier of the tool.
            space_id: Optional space ID to get the tool from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the tool definition.

        Raises:
            NotFoundError: If the tool does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> tool = client.agent_builder.get_tool(tool_id="my_ns.error_count")
            >>> print(tool.body["type"])
            esql
        """
        path = self._build_space_path(
            f"/api/agent_builder/tools/{_quote(tool_id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def update_tool(
        self,
        *,
        tool_id: str,
        configuration: dict[str, Any] | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a tool.

        ``PUT /api/agent_builder/tools/{toolId}``. Generally available;
        added in 9.2.0. Performs a partial update: only the provided fields
        are changed. Built-in (read-only) tools cannot be updated.

        Args:
            tool_id: The unique identifier of the tool to update.
            configuration: Updated tool-specific configuration parameters.
            description: Updated description of what the tool does.
            tags: Updated tags for categorizing and organizing tools.
            space_id: Optional space ID the tool lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated tool definition.

        Raises:
            NotFoundError: If the tool does not exist.
            BadRequestError: If the request body is invalid or the tool is
                read-only.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> updated = client.agent_builder.update_tool(
            ...     tool_id="my_ns.error_count", description="Updated"
            ... )
            >>> print(updated.body["description"])
            Updated
        """
        body: dict[str, Any] = {}
        if configuration is not None:
            body["configuration"] = configuration
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags

        path = self._build_space_path(
            f"/api/agent_builder/tools/{_quote(tool_id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def delete_tool(
        self,
        *,
        tool_id: str,
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a tool.

        ``DELETE /api/agent_builder/tools/{toolId}``. Generally available;
        added in 9.2.0. Built-in (read-only) tools cannot be deleted.

        Args:
            tool_id: The unique identifier of the tool to delete.
            force: If ``True``, removes the tool from agents that use it and
                then deletes it. If ``False`` (default) and any agent uses
                the tool, the request returns a 409 Conflict with the list
                of agents.
            space_id: Optional space ID the tool lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``{"success": true}`` on success.

        Raises:
            NotFoundError: If the tool does not exist.
            ConflictError: If the tool is in use by agents and ``force`` is
                not set.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = client.agent_builder.delete_tool(
            ...     tool_id="my_ns.error_count", force=True
            ... )
            >>> print(result.body["success"])
            True
        """
        params: dict[str, Any] = {}
        if force is not None:
            params["force"] = force

        path = self._build_space_path(
            f"/api/agent_builder/tools/{_quote(tool_id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "DELETE",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def execute_tool(
        self,
        *,
        tool_id: str,
        tool_params: dict[str, Any],
        connector_id: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Run a tool.

        ``POST /api/agent_builder/tools/_execute``. Generally available;
        added in 9.2.0. Executes a tool directly with the given parameters
        and returns its results. Tools with static configurations (for
        example an ES|QL tool without parameters) do not require an LLM
        connector.

        Args:
            tool_id: The ID of the tool to execute.
            tool_params: Parameters to pass to the tool execution. Must
                match the tool's parameter ``schema`` (pass ``{}`` for tools
                without parameters).
            connector_id: Optional connector ID for tools that require
                external integrations.
            space_id: Optional space ID the tool lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing a ``results`` list of typed tool
            results (for an ES|QL tool: a ``query`` result and an
            ``esql_results`` result with ``columns`` and ``values``).

        Raises:
            BadRequestError: If the tool does not exist or the parameters do
                not match the tool schema.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> executed = client.agent_builder.execute_tool(
            ...     tool_id="my_ns.error_count", tool_params={}
            ... )
            >>> for result in executed.body["results"]:
            ...     print(result["type"])
        """
        body: dict[str, Any] = {
            "tool_id": tool_id,
            "tool_params": tool_params,
        }
        if connector_id is not None:
            body["connector_id"] = connector_id

        path = self._build_space_path(
            "/api/agent_builder/tools/_execute", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def list_conversations(
        self,
        *,
        agent_id: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List conversations.

        ``GET /api/agent_builder/conversations``. Generally available; added
        in 9.2.0. Returns the conversations of the current user, optionally
        filtered by agent.

        Args:
            agent_id: Optional agent ID to filter conversations by.
            space_id: Optional space ID to list conversations from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing a ``results`` list of
            conversations.

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> conversations = client.agent_builder.list_conversations(
            ...     agent_id="elastic-ai-agent"
            ... )
            >>> for conversation in conversations.body["results"]:
            ...     print(conversation["id"], conversation["title"])
        """
        params: dict[str, Any] = {}
        if agent_id is not None:
            params["agent_id"] = agent_id

        path = self._build_space_path(
            "/api/agent_builder/conversations", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def get_conversation(
        self,
        *,
        conversation_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a conversation by ID.

        ``GET /api/agent_builder/conversations/{conversation_id}``.
        Generally available; added in 9.2.0.

        Args:
            conversation_id: The unique identifier of the conversation.
            space_id: Optional space ID the conversation lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the conversation, including its
            ``rounds`` of user input and agent responses.

        Raises:
            NotFoundError: If the conversation does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> conversation = client.agent_builder.get_conversation(
            ...     conversation_id="696ccd6d-4bff-4b26-a62e-522ccf2dcd16"
            ... )
            >>> print(conversation.body["title"])
        """
        path = self._build_space_path(
            f"/api/agent_builder/conversations/{_quote(conversation_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def delete_conversation(
        self,
        *,
        conversation_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a conversation by ID.

        ``DELETE /api/agent_builder/conversations/{conversation_id}``.
        Generally available; added in 9.2.0.

        Args:
            conversation_id: The unique identifier of the conversation to
                delete.
            space_id: Optional space ID the conversation lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``{"success": true}`` on success.

        Raises:
            NotFoundError: If the conversation does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> client.agent_builder.delete_conversation(
            ...     conversation_id="696ccd6d-4bff-4b26-a62e-522ccf2dcd16"
            ... )
        """
        path = self._build_space_path(
            f"/api/agent_builder/conversations/{_quote(conversation_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Conversation attachments
    # ------------------------------------------------------------------

    def list_attachments(
        self,
        *,
        conversation_id: str,
        include_deleted: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List conversation attachments.

        ``GET /api/agent_builder/conversations/{conversation_id}/attachments``.
        Technical preview; added in 9.2.0.

        Args:
            conversation_id: The unique identifier of the conversation.
            include_deleted: Whether to include deleted attachments in the
                list.
            space_id: Optional space ID the conversation lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the conversation's attachments.

        Raises:
            NotFoundError: If the conversation does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> attachments = client.agent_builder.list_attachments(
            ...     conversation_id="696ccd6d-4bff-4b26-a62e-522ccf2dcd16",
            ...     include_deleted=True,
            ... )
        """
        params: dict[str, Any] = {}
        if include_deleted is not None:
            params["include_deleted"] = include_deleted

        path = self._build_space_path(
            f"/api/agent_builder/conversations/{_quote(conversation_id)}/attachments",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def create_attachment(
        self,
        *,
        conversation_id: str,
        type: str,
        data: Any,
        description: str | None = None,
        hidden: bool | None = None,
        id: str | None = None,
        origin: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a conversation attachment.

        ``POST /api/agent_builder/conversations/{conversation_id}/attachments``.
        Technical preview; added in 9.2.0.

        Args:
            conversation_id: The unique identifier of the conversation.
            type: The type of the attachment (e.g. ``"text"``, ``"json"``,
                ``"esql"``, ``"visualization"``).
            data: Payload of the attachment (a string for ``text``
                attachments, an object for ``json`` attachments, ...).
            description: Human-readable description of the attachment.
            hidden: Whether the attachment should be hidden from the user.
            id: Optional custom ID for the attachment.
            origin: Origin string (for example, a saved object ID) for
                by-reference attachments. When provided, the content is
                resolved once at creation time.
            space_id: Optional space ID the conversation lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created attachment.

        Raises:
            NotFoundError: If the conversation does not exist.
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> attachment = client.agent_builder.create_attachment(
            ...     conversation_id="696ccd6d-4bff-4b26-a62e-522ccf2dcd16",
            ...     type="text",
            ...     data="Meeting notes contents",
            ...     description="Meeting notes",
            ... )
        """
        body: dict[str, Any] = {
            "type": type,
            "data": data,
        }
        if description is not None:
            body["description"] = description
        if hidden is not None:
            body["hidden"] = hidden
        if id is not None:
            body["id"] = id
        if origin is not None:
            body["origin"] = origin

        path = self._build_space_path(
            f"/api/agent_builder/conversations/{_quote(conversation_id)}/attachments",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def update_attachment(
        self,
        *,
        conversation_id: str,
        attachment_id: str,
        data: Any,
        description: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a conversation attachment's content.

        ``PUT /api/agent_builder/conversations/{conversation_id}/attachments/{attachment_id}``.
        Technical preview; added in 9.2.0. Creates a new version of the
        attachment with the provided content.

        Args:
            conversation_id: The unique identifier of the conversation.
            attachment_id: The unique identifier of the attachment to
                update.
            data: The new content for the attachment.
            description: Optional new description for the attachment.
            space_id: Optional space ID the conversation lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated attachment.

        Raises:
            NotFoundError: If the conversation or attachment does not exist.
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> updated = client.agent_builder.update_attachment(
            ...     conversation_id="696ccd6d-4bff-4b26-a62e-522ccf2dcd16",
            ...     attachment_id="att-1",
            ...     data="Updated contents",
            ... )
        """
        body: dict[str, Any] = {
            "data": data,
        }
        if description is not None:
            body["description"] = description

        path = self._build_space_path(
            f"/api/agent_builder/conversations/{_quote(conversation_id)}"
            f"/attachments/{_quote(attachment_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def rename_attachment(
        self,
        *,
        conversation_id: str,
        attachment_id: str,
        description: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Rename a conversation attachment.

        ``PATCH /api/agent_builder/conversations/{conversation_id}/attachments/{attachment_id}``.
        Technical preview; added in 9.2.0. Updates only the attachment's
        description (display name) without creating a new content version.

        Args:
            conversation_id: The unique identifier of the conversation.
            attachment_id: The unique identifier of the attachment to
                rename.
            description: The new description/name for the attachment.
            space_id: Optional space ID the conversation lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the renamed attachment.

        Raises:
            NotFoundError: If the conversation or attachment does not exist.
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> renamed = client.agent_builder.rename_attachment(
            ...     conversation_id="696ccd6d-4bff-4b26-a62e-522ccf2dcd16",
            ...     attachment_id="att-1",
            ...     description="Updated attachment name",
            ... )
        """
        body: dict[str, Any] = {
            "description": description,
        }

        path = self._build_space_path(
            f"/api/agent_builder/conversations/{_quote(conversation_id)}"
            f"/attachments/{_quote(attachment_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "PATCH",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def delete_attachment(
        self,
        *,
        conversation_id: str,
        attachment_id: str,
        permanent: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a conversation attachment.

        ``DELETE /api/agent_builder/conversations/{conversation_id}/attachments/{attachment_id}``.
        Technical preview; added in 9.2.0. By default the attachment is
        soft-deleted and can be restored with
        :meth:`AgentBuilderClient.restore_attachment`.

        Args:
            conversation_id: The unique identifier of the conversation.
            attachment_id: The unique identifier of the attachment to
                delete.
            permanent: If ``True``, permanently removes the attachment (only
                for unreferenced attachments).
            space_id: Optional space ID the conversation lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse acknowledging the deletion.

        Raises:
            NotFoundError: If the conversation or attachment does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> client.agent_builder.delete_attachment(
            ...     conversation_id="696ccd6d-4bff-4b26-a62e-522ccf2dcd16",
            ...     attachment_id="att-1",
            ... )
        """
        params: dict[str, Any] = {}
        if permanent is not None:
            params["permanent"] = permanent

        path = self._build_space_path(
            f"/api/agent_builder/conversations/{_quote(conversation_id)}"
            f"/attachments/{_quote(attachment_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "DELETE",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def restore_attachment(
        self,
        *,
        conversation_id: str,
        attachment_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Restore a soft-deleted conversation attachment.

        ``POST /api/agent_builder/conversations/{conversation_id}/attachments/{attachment_id}/_restore``.
        Technical preview; added in 9.2.0.

        Args:
            conversation_id: The unique identifier of the conversation.
            attachment_id: The unique identifier of the attachment to
                restore.
            space_id: Optional space ID the conversation lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the restored attachment.

        Raises:
            NotFoundError: If the conversation or attachment does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> restored = client.agent_builder.restore_attachment(
            ...     conversation_id="696ccd6d-4bff-4b26-a62e-522ccf2dcd16",
            ...     attachment_id="att-1",
            ... )
        """
        path = self._build_space_path(
            f"/api/agent_builder/conversations/{_quote(conversation_id)}"
            f"/attachments/{_quote(attachment_id)}/_restore",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
        )

    def update_attachment_origin(
        self,
        *,
        conversation_id: str,
        attachment_id: str,
        origin: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a conversation attachment's origin.

        ``PUT /api/agent_builder/conversations/{conversation_id}/attachments/{attachment_id}/origin``.
        Technical preview; added in 9.4.0. Links the attachment to an origin
        (for example a saved object) so its staleness can be tracked.

        Args:
            conversation_id: The unique identifier of the conversation.
            attachment_id: The unique identifier of the attachment.
            origin: The origin string (e.g. a saved object ID for
                visualizations and dashboards).
            space_id: Optional space ID the conversation lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated attachment.

        Raises:
            NotFoundError: If the conversation or attachment does not exist.
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> updated = client.agent_builder.update_attachment_origin(
            ...     conversation_id="696ccd6d-4bff-4b26-a62e-522ccf2dcd16",
            ...     attachment_id="att-1",
            ...     origin="abc123",
            ... )
        """
        body: dict[str, Any] = {
            "origin": origin,
        }

        path = self._build_space_path(
            f"/api/agent_builder/conversations/{_quote(conversation_id)}"
            f"/attachments/{_quote(attachment_id)}/origin",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def check_stale_attachments(
        self,
        *,
        conversation_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Check attachment staleness for a conversation.

        ``GET /api/agent_builder/conversations/{conversation_id}/attachments/stale``.
        Technical preview; added in 9.4.0. For origin-backed attachments,
        reports whether the stored content is out of date with respect to
        its origin; stale entries include the resolved data for resync.

        Args:
            conversation_id: The unique identifier of the conversation.
            space_id: Optional space ID the conversation lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing an ``attachments`` list of
            ``{"id", "is_stale", ...}`` entries.

        Raises:
            NotFoundError: If the conversation does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> staleness = client.agent_builder.check_stale_attachments(
            ...     conversation_id="696ccd6d-4bff-4b26-a62e-522ccf2dcd16"
            ... )
            >>> for entry in staleness.body["attachments"]:
            ...     print(entry["id"], entry["is_stale"])
        """
        path = self._build_space_path(
            f"/api/agent_builder/conversations/{_quote(conversation_id)}"
            "/attachments/stale",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Converse
    # ------------------------------------------------------------------

    def converse(
        self,
        *,
        input: str | None = None,
        agent_id: str | None = None,
        conversation_id: str | None = None,
        connector_id: str | None = None,
        inference_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        browser_api_tools: list[dict[str, Any]] | None = None,
        capabilities: dict[str, Any] | None = None,
        configuration_overrides: dict[str, Any] | None = None,
        prompts: dict[str, Any] | None = None,
        action: str | None = None,
        execution_mode: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Send a chat message to an agent.

        ``POST /api/agent_builder/converse``. Generally available; added in
        9.2.0. Requires a configured LLM connector. The request blocks until
        the agent produces its final response; use
        :meth:`AgentBuilderClient.converse_async` for a streaming
        server-sent-events variant.

        Args:
            input: The user input message to send to the agent.
            agent_id: The ID of the agent to chat with. Defaults to the
                built-in Elastic AI agent (``"elastic-ai-agent"``).
            conversation_id: Optional existing conversation ID to continue a
                previous conversation.
            connector_id: Optional connector ID for the agent to use for
                model routing. Mutually exclusive with ``inference_id``.
            inference_id: Optional inference endpoint ID for model routing
                (public alias for the same internal identifier as
                ``connector_id``). Mutually exclusive with ``connector_id``.
            attachments: Optional attachments to send with the message, each
                a dict with a required ``type`` and either ``data`` or
                ``origin``. Technical preview; added in 9.3.0.
            browser_api_tools: Optional browser API tools to be registered
                as LLM tools with a ``browser.*`` namespace; each requires
                ``id``, ``description`` and ``schema``.
            capabilities: Controls agent capabilities during conversation,
                e.g. ``{"visualizations": True}``.
            configuration_overrides: Runtime configuration overrides
                (``instructions``, ``tools``) applied for this execution
                only.
            prompts: Responses to confirmation prompts, keyed by prompt ID:
                ``{"<prompt_id>": {"allow": True}}``.
            action: The action to perform. ``"regenerate"`` re-executes the
                last round with the original input (requires
                ``conversation_id``).
            execution_mode: How to execute the agent: ``"local"`` or
                ``"task_manager"`` (sent as ``_execution_mode``).
                Experimental; added in 9.4.0.
            space_id: Optional space ID to converse in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``conversation_id``, the agent
            ``response`` (with its final ``message``), the intermediate
            ``steps`` and ``round_complete``.

        Raises:
            BadRequestError: If the request body is invalid.
            ApiError: If no (working) LLM connector is available.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> reply = client.agent_builder.converse(
            ...     input="What is Elasticsearch?",
            ...     agent_id="elastic-ai-agent",
            ... )
            >>> print(reply.body["response"]["message"])
        """
        body: dict[str, Any] = {}
        if input is not None:
            body["input"] = input
        if agent_id is not None:
            body["agent_id"] = agent_id
        if conversation_id is not None:
            body["conversation_id"] = conversation_id
        if connector_id is not None:
            body["connector_id"] = connector_id
        if inference_id is not None:
            body["inference_id"] = inference_id
        if attachments is not None:
            body["attachments"] = attachments
        if browser_api_tools is not None:
            body["browser_api_tools"] = browser_api_tools
        if capabilities is not None:
            body["capabilities"] = capabilities
        if configuration_overrides is not None:
            body["configuration_overrides"] = configuration_overrides
        if prompts is not None:
            body["prompts"] = prompts
        if action is not None:
            body["action"] = action
        if execution_mode is not None:
            body["_execution_mode"] = execution_mode

        path = self._build_space_path(
            "/api/agent_builder/converse", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def converse_async(
        self,
        *,
        input: str | None = None,
        agent_id: str | None = None,
        conversation_id: str | None = None,
        connector_id: str | None = None,
        inference_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        browser_api_tools: list[dict[str, Any]] | None = None,
        capabilities: dict[str, Any] | None = None,
        configuration_overrides: dict[str, Any] | None = None,
        prompts: dict[str, Any] | None = None,
        action: str | None = None,
        execution_mode: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Send a chat message to an agent (streaming).

        ``POST /api/agent_builder/converse/async``. Generally available;
        added in 9.2.0. Requires a configured LLM connector. The server
        responds with ``text/event-stream`` server-sent events; the whole
        stream is read and the raw SSE text is returned as the response
        body (a ``TextApiResponse`` at runtime). Parse the ``event:`` /
        ``data:`` lines to consume the individual events.

        Args:
            input: The user input message to send to the agent.
            agent_id: The ID of the agent to chat with. Defaults to the
                built-in Elastic AI agent (``"elastic-ai-agent"``).
            conversation_id: Optional existing conversation ID to continue a
                previous conversation.
            connector_id: Optional connector ID for the agent to use for
                model routing. Mutually exclusive with ``inference_id``.
            inference_id: Optional inference endpoint ID for model routing
                (public alias for the same internal identifier as
                ``connector_id``). Mutually exclusive with ``connector_id``.
            attachments: Optional attachments to send with the message, each
                a dict with a required ``type`` and either ``data`` or
                ``origin``. Technical preview; added in 9.3.0.
            browser_api_tools: Optional browser API tools to be registered
                as LLM tools with a ``browser.*`` namespace; each requires
                ``id``, ``description`` and ``schema``.
            capabilities: Controls agent capabilities during conversation,
                e.g. ``{"visualizations": True}``.
            configuration_overrides: Runtime configuration overrides
                (``instructions``, ``tools``) applied for this execution
                only.
            prompts: Responses to confirmation prompts, keyed by prompt ID:
                ``{"<prompt_id>": {"allow": True}}``.
            action: The action to perform. ``"regenerate"`` re-executes the
                last round with the original input (requires
                ``conversation_id``).
            execution_mode: How to execute the agent: ``"local"`` or
                ``"task_manager"`` (sent as ``_execution_mode``).
                Experimental; added in 9.4.0.
            space_id: Optional space ID to converse in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ApiResponse whose body is the raw server-sent-events text
            (``event: ...`` / ``data: {...}`` blocks).

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> stream = client.agent_builder.converse_async(
            ...     input="What is Elasticsearch?"
            ... )
            >>> for block in stream.body.split("\\n\\n"):
            ...     print(block)
        """
        body: dict[str, Any] = {}
        if input is not None:
            body["input"] = input
        if agent_id is not None:
            body["agent_id"] = agent_id
        if conversation_id is not None:
            body["conversation_id"] = conversation_id
        if connector_id is not None:
            body["connector_id"] = connector_id
        if inference_id is not None:
            body["inference_id"] = inference_id
        if attachments is not None:
            body["attachments"] = attachments
        if browser_api_tools is not None:
            body["browser_api_tools"] = browser_api_tools
        if capabilities is not None:
            body["capabilities"] = capabilities
        if configuration_overrides is not None:
            body["configuration_overrides"] = configuration_overrides
        if prompts is not None:
            body["prompts"] = prompts
        if action is not None:
            body["action"] = action
        if execution_mode is not None:
            body["_execution_mode"] = execution_mode

        path = self._build_space_path(
            "/api/agent_builder/converse/async", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "text/event-stream"},
            body=body,
        )

    # ------------------------------------------------------------------
    # A2A protocol
    # ------------------------------------------------------------------

    def get_a2a_card(
        self,
        *,
        agent_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get an agent's A2A (Agent2Agent protocol) card.

        ``GET /api/agent_builder/a2a/{agentId}.json``. Technical preview;
        added in 9.2.0. The card describes the agent's capabilities, skills
        and endpoint URL for A2A clients.

        Args:
            agent_id: The unique identifier of the agent.
            space_id: Optional space ID the agent lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the A2A agent card (``name``,
            ``description``, ``url``, ``version``, ``protocolVersion``,
            ``capabilities``, ``skills``...).

        Raises:
            NotFoundError: If the agent does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> card = client.agent_builder.get_a2a_card(
            ...     agent_id="elastic-ai-agent"
            ... )
            >>> print(card.body["protocolVersion"])
        """
        path = self._build_space_path(
            f"/api/agent_builder/a2a/{_quote(agent_id)}.json",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def send_a2a_task(
        self,
        *,
        agent_id: str,
        payload: dict[str, Any],
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Send an A2A (Agent2Agent protocol) task to an agent.

        ``POST /api/agent_builder/a2a/{agentId}``. Technical preview; added
        in 9.2.0. This endpoint implements the JSON-RPC A2A protocol; it is
        primarily intended for A2A SDKs rather than direct REST usage.
        Task execution requires a configured LLM connector.

        Args:
            agent_id: The unique identifier of the agent.
            payload: The JSON-RPC request payload, e.g.
                ``{"jsonrpc": "2.0", "id": "1", "method": "message/send",
                "params": {"message": {...}}}``.
            space_id: Optional space ID the agent lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the JSON-RPC response.

        Raises:
            NotFoundError: If the agent does not exist.
            BadRequestError: If the payload is not a valid JSON-RPC request.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> response = client.agent_builder.send_a2a_task(
            ...     agent_id="elastic-ai-agent",
            ...     payload={
            ...         "jsonrpc": "2.0",
            ...         "id": "task-1",
            ...         "method": "message/send",
            ...         "params": {
            ...             "message": {
            ...                 "role": "user",
            ...                 "parts": [{"kind": "text", "text": "Hello"}],
            ...                 "messageId": "msg-1",
            ...             }
            ...         },
            ...     },
            ... )
            >>> print(response.body["result"])
        """
        path = self._build_space_path(
            f"/api/agent_builder/a2a/{_quote(agent_id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=payload,
        )

    # ------------------------------------------------------------------
    # MCP protocol
    # ------------------------------------------------------------------

    def send_mcp_request(
        self,
        *,
        payload: dict[str, Any],
        namespace: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Send a request to the MCP (Model Context Protocol) server.

        ``POST /api/agent_builder/mcp``. Technical preview; added in 9.2.0.
        This endpoint implements the streamable-HTTP MCP transport
        (JSON-RPC); it is primarily intended for MCP clients rather than
        direct REST usage. The live server requires the ``Accept`` header to
        include both ``application/json`` and ``text/event-stream`` (set
        automatically). Tool calls that need an LLM require a configured
        connector; ``initialize`` and ``tools/list`` work without one.

        Args:
            payload: The JSON-RPC request payload, e.g.
                ``{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {...}}``.
            namespace: Comma-separated list of namespaces to filter tools.
                Only tools matching the specified namespaces will be
                returned.
            space_id: Optional space ID to target.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the JSON-RPC response.

        Raises:
            BadRequestError: If the payload is not a valid JSON-RPC request.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> response = client.agent_builder.send_mcp_request(
            ...     payload={
            ...         "jsonrpc": "2.0",
            ...         "id": 1,
            ...         "method": "initialize",
            ...         "params": {
            ...             "protocolVersion": "2024-11-05",
            ...             "capabilities": {},
            ...             "clientInfo": {"name": "my-client", "version": "1.0"},
            ...         },
            ...     },
            ... )
            >>> print(response.body["result"]["serverInfo"]["name"])
            elastic-mcp-server
        """
        params: dict[str, Any] = {}
        if namespace is not None:
            params["namespace"] = namespace

        path = self._build_space_path(
            "/api/agent_builder/mcp", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            params=params,
            headers={"accept": "application/json, text/event-stream"},
            body=payload,
        )

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    def list_skills(
        self,
        *,
        include_plugins: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List skills.

        ``GET /api/agent_builder/skills``. Technical preview; added in
        9.4.0.

        Args:
            include_plugins: Set to ``True`` to include skills from plugins.
            space_id: Optional space ID to list skills from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing a ``results`` list of skill
            definitions (``id``, ``name``, ``description``, ``tool_ids``,
            ``readonly``...).

        Raises:
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> skills = client.agent_builder.list_skills()
            >>> for skill in skills.body["results"]:
            ...     print(skill["id"])
        """
        params: dict[str, Any] = {}
        if include_plugins is not None:
            params["include_plugins"] = include_plugins

        path = self._build_space_path(
            "/api/agent_builder/skills", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    def create_skill(
        self,
        *,
        id: str,
        name: str,
        description: str,
        content: str,
        referenced_content: list[dict[str, Any]] | None = None,
        tool_ids: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a skill.

        ``POST /api/agent_builder/skills``. Technical preview; added in
        9.4.0. A skill packages reusable instructions (markdown) and tool
        references that agents can leverage.

        Args:
            id: Unique identifier for the skill.
            name: Human-readable name for the skill.
            description: Description of what the skill does.
            content: Skill instructions content (markdown).
            referenced_content: Optional list of referenced content entries,
                each with ``name``, ``relativePath`` and ``content``.
            tool_ids: Tool IDs from the tool registry that this skill
                references.
            space_id: Optional space ID to create the skill in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the created skill definition.

        Raises:
            BadRequestError: If the request body is invalid or the skill ID
                already exists.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> created = client.agent_builder.create_skill(
            ...     id="triage-errors",
            ...     name="Triage errors",
            ...     description="How to triage application errors",
            ...     content="# Triage\\n1. Check the error rate...",
            ...     tool_ids=["platform.core.search"],
            ... )
            >>> print(created.body["id"])
            triage-errors
        """
        body: dict[str, Any] = {
            "id": id,
            "name": name,
            "description": description,
            "content": content,
        }
        if referenced_content is not None:
            body["referenced_content"] = referenced_content
        if tool_ids is not None:
            body["tool_ids"] = tool_ids

        path = self._build_space_path(
            "/api/agent_builder/skills", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def get_skill(
        self,
        *,
        skill_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a skill by ID.

        ``GET /api/agent_builder/skills/{skillId}``. Technical preview;
        added in 9.4.0.

        Args:
            skill_id: The unique identifier of the skill.
            space_id: Optional space ID to get the skill from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the skill definition.

        Raises:
            NotFoundError: If the skill does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> skill = client.agent_builder.get_skill(skill_id="triage-errors")
            >>> print(skill.body["name"])
            Triage errors
        """
        path = self._build_space_path(
            f"/api/agent_builder/skills/{_quote(skill_id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def update_skill(
        self,
        *,
        skill_id: str,
        name: str | None = None,
        description: str | None = None,
        content: str | None = None,
        referenced_content: list[dict[str, Any]] | None = None,
        tool_ids: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a skill.

        ``PUT /api/agent_builder/skills/{skillId}``. Technical preview;
        added in 9.4.0. Performs a partial update: only the provided fields
        are changed. Built-in (read-only) skills cannot be updated.

        Args:
            skill_id: The unique identifier of the skill to update.
            name: Updated name for the skill.
            description: Updated description.
            content: Updated skill instructions content.
            referenced_content: Updated list of referenced content entries,
                each with ``name``, ``relativePath`` and ``content``.
            tool_ids: Updated tool IDs from the tool registry.
            space_id: Optional space ID the skill lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the updated skill definition.

        Raises:
            NotFoundError: If the skill does not exist.
            BadRequestError: If the request body is invalid or the skill is
                read-only.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> updated = client.agent_builder.update_skill(
            ...     skill_id="triage-errors", description="Updated"
            ... )
            >>> print(updated.body["description"])
            Updated
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if content is not None:
            body["content"] = content
        if referenced_content is not None:
            body["referenced_content"] = referenced_content
        if tool_ids is not None:
            body["tool_ids"] = tool_ids

        path = self._build_space_path(
            f"/api/agent_builder/skills/{_quote(skill_id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def delete_skill(
        self,
        *,
        skill_id: str,
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a skill.

        ``DELETE /api/agent_builder/skills/{skillId}``. Technical preview;
        added in 9.4.0. Built-in (read-only) skills cannot be deleted.

        Args:
            skill_id: The unique identifier of the skill to delete.
            force: If ``True``, removes the skill from agents that use it
                and then deletes it.
            space_id: Optional space ID the skill lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing ``{"success": true}`` on success.

        Raises:
            NotFoundError: If the skill does not exist.
            ConflictError: If the skill is in use by agents and ``force`` is
                not set.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> result = client.agent_builder.delete_skill(
            ...     skill_id="triage-errors"
            ... )
            >>> print(result.body["success"])
            True
        """
        params: dict[str, Any] = {}
        if force is not None:
            params["force"] = force

        path = self._build_space_path(
            f"/api/agent_builder/skills/{_quote(skill_id)}", space_id, validate_spaces
        )
        return self.perform_request(
            "DELETE",
            path,
            params=params,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Plugins
    # ------------------------------------------------------------------

    def list_plugins(
        self,
        *,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """List plugins.

        ``GET /api/agent_builder/plugins``. Technical preview; added in
        9.4.0. NOTE: on a default Kibana 9.4.3 configuration the plugins
        API is not enabled and responds with 404 (it is gated behind a
        feature flag).

        Args:
            space_id: Optional space ID to list plugins from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the installed Agent Builder
            plugins.

        Raises:
            NotFoundError: If the plugins API is not enabled.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> plugins = client.agent_builder.list_plugins()
        """
        path = self._build_space_path(
            "/api/agent_builder/plugins", space_id, validate_spaces
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def get_plugin(
        self,
        *,
        plugin_id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a plugin by ID.

        ``GET /api/agent_builder/plugins/{pluginId}``. Technical preview;
        added in 9.4.0. NOTE: on a default Kibana 9.4.3 configuration the
        plugins API is not enabled and responds with 404 (it is gated
        behind a feature flag).

        Args:
            plugin_id: The unique identifier of the plugin.
            space_id: Optional space ID to get the plugin from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the plugin definition.

        Raises:
            NotFoundError: If the plugin does not exist or the plugins API
                is not enabled.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> plugin = client.agent_builder.get_plugin(plugin_id="my-plugin")
        """
        path = self._build_space_path(
            f"/api/agent_builder/plugins/{_quote(plugin_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    def install_plugin(
        self,
        *,
        url: str,
        plugin_name: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Install a plugin.

        ``POST /api/agent_builder/plugins/install``. Technical preview;
        added in 9.4.0. NOTE: on a default Kibana 9.4.3 configuration the
        plugins API is not enabled and responds with 404 (it is gated
        behind a feature flag).

        Args:
            url: URL to install the plugin from (GitHub URL or direct zip
                URL).
            plugin_name: Optional name override for the plugin. Defaults to
                the manifest name.
            space_id: Optional space ID to install the plugin in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse containing the installed plugin definition.

        Raises:
            NotFoundError: If the plugins API is not enabled.
            BadRequestError: If the URL or plugin package is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> installed = client.agent_builder.install_plugin(
            ...     url="https://github.com/example/agent-plugin"
            ... )
        """
        body: dict[str, Any] = {
            "url": url,
        }
        if plugin_name is not None:
            body["plugin_name"] = plugin_name

        path = self._build_space_path(
            "/api/agent_builder/plugins/install", space_id, validate_spaces
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    def delete_plugin(
        self,
        *,
        plugin_id: str,
        force: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a plugin.

        ``DELETE /api/agent_builder/plugins/{pluginId}``. Technical preview;
        added in 9.4.0. NOTE: on a default Kibana 9.4.3 configuration the
        plugins API is not enabled and responds with 404 (it is gated
        behind a feature flag).

        Args:
            plugin_id: The unique identifier of the plugin to delete.
            force: If ``True``, removes the plugin even if it is referenced
                by agents.
            space_id: Optional space ID the plugin lives in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse acknowledging the deletion.

        Raises:
            NotFoundError: If the plugin does not exist or the plugins API
                is not enabled.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.

        Example:
            >>> client.agent_builder.delete_plugin(plugin_id="my-plugin")
        """
        params: dict[str, Any] = {}
        if force is not None:
            params["force"] = force

        path = self._build_space_path(
            f"/api/agent_builder/plugins/{_quote(plugin_id)}",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "DELETE",
            path,
            params=params,
            headers={"accept": "application/json"},
        )
