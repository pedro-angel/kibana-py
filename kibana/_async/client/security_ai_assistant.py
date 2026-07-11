"""Async Kibana Security AI Assistant API client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._async.client.utils import AsyncNamespaceClient, _quote

if TYPE_CHECKING:
    from kibana._async.client import AsyncKibana


class AsyncSecurityAiAssistantClient(AsyncNamespaceClient):
    """Async client for the Kibana Security AI Assistant API.

    The Security AI Assistant helps security analysts triage alerts, write
    queries and investigate incidents through a large language model. This
    client manages the assistant's building blocks -- conversations, prompts,
    anonymization fields and Knowledge Base entries -- and can request model
    responses via :meth:`chat_complete` using any AI (``.gen-ai``,
    ``.bedrock``, ``.gemini``, ...) connector configured in Kibana.

    All Security AI Assistant resources are space-scoped: every method
    accepts an optional ``space_id`` to target a specific space (``None``
    targets the default space or the space the client is scoped to).

    Example:
        >>> from kibana import AsyncKibana
        >>> client = AsyncKibana("http://localhost:5601", api_key="...")
        >>>
        >>> # Create and find conversations
        >>> conv = await client.security_ai_assistant.create_conversation(
        ...     title="Suspicious login investigation",
        ... )
        >>> found = await client.security_ai_assistant.find_conversations(
        ...     filter="Suspicious",
        ... )
        >>>
        >>> # Ask the model a question through an AI connector
        >>> answer = await client.security_ai_assistant.chat_complete(
        ...     connector_id="my-openai-connector",
        ...     messages=[{"role": "user", "content": "What is a brute force attack?"}],
        ...     persist=False,
        ... )
        >>> print(answer.body["data"])
    """

    def __init__(
        self,
        client: AsyncKibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the AsyncSecurityAiAssistantClient.

        Args:
            client: The parent AsyncKibana client instance to delegate
                requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> security_ai_assistant_client = AsyncSecurityAiAssistantClient(
            ...     kibana_client
            ... )
        """
        super().__init__(client, default_space_id, validate_spaces)

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def create_conversation(
        self,
        *,
        title: str,
        api_config: dict[str, Any] | None = None,
        category: str | None = None,
        exclude_from_last_conversation_storage: bool | None = None,
        id: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        replacements: dict[str, str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a conversation.

        ``POST /api/security_ai_assistant/current_user/conversations``.
        Creates a new Security AI Assistant conversation for the current
        user, optionally seeded with messages and an LLM API configuration.

        Args:
            title: The conversation title.
            api_config: LLM API configuration, e.g. ``{"connectorId": "...",
                "actionTypeId": ".gen-ai", "model": "gpt-4",
                "provider": "OpenAI"}``. ``connectorId`` and ``actionTypeId``
                are required inside this object when it is provided.
            category: The conversation category: ``assistant`` or
                ``insights``.
            exclude_from_last_conversation_storage: Exclude this conversation
                from last-conversation storage.
            id: Optional caller-specified conversation ID.
            messages: The conversation messages. Each message requires
                ``content``, ``role`` (``system``, ``user`` or ``assistant``)
                and ``timestamp`` (ISO 8601).
            replacements: Replacements object used to anonymize/de-anonymize
                messages (mapping of replacement token to original value).
            space_id: Optional space ID to create the conversation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created conversation, including its
            server-assigned ``id``, ``createdAt``, ``createdBy`` and
            ``users``.

        Raises:
            BadRequestError: If required parameters are missing or invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> conv = await client.security_ai_assistant.create_conversation(
            ...     title="Security Discussion",
            ...     messages=[
            ...         {
            ...             "content": "Hello, how can I assist you today?",
            ...             "role": "system",
            ...             "timestamp": "2026-01-01T12:00:00Z",
            ...         }
            ...     ],
            ... )
            >>> print(conv.body["id"])
        """
        body: dict[str, Any] = {"title": title}
        if api_config is not None:
            body["apiConfig"] = api_config
        if category is not None:
            body["category"] = category
        if exclude_from_last_conversation_storage is not None:
            body["excludeFromLastConversationStorage"] = (
                exclude_from_last_conversation_storage
            )
        if id is not None:
            body["id"] = id
        if messages is not None:
            body["messages"] = messages
        if replacements is not None:
            body["replacements"] = replacements

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security_ai_assistant/current_user/conversations",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_conversation(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a conversation.

        ``GET /api/security_ai_assistant/current_user/conversations/{id}``.
        Gets the details of an existing conversation by its unique ID.

        Args:
            id: The conversation's ``id`` value.
            space_id: Optional space ID to get the conversation from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the conversation details (``id``,
            ``title``, ``messages``, ``apiConfig``, ``users``, ...).

        Raises:
            NotFoundError: If the conversation does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> conv = await client.security_ai_assistant.get_conversation(id="abc123")
            >>> print(conv.body["title"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/security_ai_assistant/current_user/conversations/{_quote(id)}",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_conversation(
        self,
        *,
        id: str,
        api_config: dict[str, Any] | None = None,
        category: str | None = None,
        exclude_from_last_conversation_storage: bool | None = None,
        messages: list[dict[str, Any]] | None = None,
        replacements: dict[str, str] | None = None,
        title: str | None = None,
        users: list[dict[str, Any]] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a conversation.

        ``PUT /api/security_ai_assistant/current_user/conversations/{id}``.
        Updates an existing conversation. Only the provided fields are
        modified.

        Args:
            id: The conversation's ``id`` value.
            api_config: Updated LLM API configuration (``connectorId`` and
                ``actionTypeId`` are required inside this object when it is
                provided).
            category: Updated conversation category: ``assistant`` or
                ``insights``. Note: on Kibana 9.4.3 the live server accepts
                this field but does not change the stored category.
            exclude_from_last_conversation_storage: Exclude this conversation
                from last-conversation storage.
            messages: Replacement list of conversation messages. Each message
                requires ``content``, ``role`` and ``timestamp``.
            replacements: Replacements object used to anonymize/de-anonymize
                messages.
            title: Updated conversation title.
            users: Users with access to the conversation, e.g.
                ``[{"id": "...", "name": "..."}]``.
            space_id: Optional space ID to update the conversation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the updated conversation.

        Raises:
            NotFoundError: If the conversation does not exist.
            BadRequestError: If the update payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.security_ai_assistant.update_conversation(
            ...     id="abc123",
            ...     title="Updated Security Discussion",
            ... )
            >>> print(updated.body["title"])
            Updated Security Discussion
        """
        body: dict[str, Any] = {"id": id}
        if api_config is not None:
            body["apiConfig"] = api_config
        if category is not None:
            body["category"] = category
        if exclude_from_last_conversation_storage is not None:
            body["excludeFromLastConversationStorage"] = (
                exclude_from_last_conversation_storage
            )
        if messages is not None:
            body["messages"] = messages
        if replacements is not None:
            body["replacements"] = replacements
        if title is not None:
            body["title"] = title
        if users is not None:
            body["users"] = users

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/security_ai_assistant/current_user/conversations/{_quote(id)}",
            space_id,
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_conversation(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a conversation.

        ``DELETE /api/security_ai_assistant/current_user/conversations/{id}``.
        Permanently deletes an existing conversation by its ID.

        Note: the 9.4.3 spec documents the deleted conversation as the
        response body, but the live server returns an empty object ``{}``.

        Args:
            id: The conversation's ``id`` value.
            space_id: Optional space ID to delete the conversation from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with an empty object body on success.

        Raises:
            NotFoundError: If the conversation does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.security_ai_assistant.delete_conversation(id="abc123")
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/security_ai_assistant/current_user/conversations/{_quote(id)}",
            space_id,
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    async def find_conversations(
        self,
        *,
        fields: list[str] | None = None,
        filter: str | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        is_owner: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get conversations.

        ``GET /api/security_ai_assistant/current_user/conversations/_find``.
        Lists the current user's conversations with search, filter, sort and
        pagination support.

        Args:
            fields: A list of fields to include in the response. If omitted,
                all fields are returned.
            filter: A search query to filter the conversations. Can match
                against titles, messages, or other conversation attributes.
            sort_field: Field to sort by: ``created_at``, ``title`` or
                ``updated_at``.
            sort_order: Sort order: ``asc`` or ``desc``.
            page: Page number (default 1).
            per_page: Conversations per page (default 20).
            is_owner: If True, only conversations owned by the current user
                are returned.
            space_id: Optional space ID to search conversations in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``page``, ``perPage``, ``total`` and the
            ``data`` array of conversations.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.security_ai_assistant.find_conversations(
            ...     filter="Security",
            ...     sort_field="created_at",
            ...     sort_order="desc",
            ... )
            >>> print(found.body["total"])
        """
        params: dict[str, Any] = {}
        if fields is not None:
            params["fields"] = fields
        if filter is not None:
            params["filter"] = filter
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if is_owner is not None:
            params["is_owner"] = is_owner

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security_ai_assistant/current_user/conversations/_find",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def delete_all_conversations(
        self,
        *,
        excluded_ids: list[str] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete all conversations.

        ``DELETE /api/security_ai_assistant/current_user/conversations``.
        Permanently deletes all of the current user's conversations in the
        target space. Conversations listed in ``excluded_ids`` are kept.

        Args:
            excluded_ids: Conversation IDs to exclude from deletion (they are
                kept; every other conversation is deleted).
            space_id: Optional space ID to delete conversations in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``success``, ``totalDeleted`` and
            ``failures``.

        Raises:
            BadRequestError: If the request body is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.security_ai_assistant.delete_all_conversations(
            ...     excluded_ids=["abc123"],
            ... )
            >>> print(result.body["totalDeleted"])
        """
        body: dict[str, Any] | None = None
        if excluded_ids is not None:
            body = {"excludedIds": excluded_ids}

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security_ai_assistant/current_user/conversations",
            space_id,
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    async def find_prompts(
        self,
        *,
        fields: list[str] | None = None,
        filter: str | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get prompts.

        ``GET /api/security_ai_assistant/prompts/_find``. Lists prompts with
        optional filters, sorting and pagination.

        Args:
            fields: List of specific fields to include in each returned
                prompt.
            filter: Search query string to filter prompts by matching fields.
            sort_field: Field to sort by: ``created_at``, ``is_default``,
                ``name`` or ``updated_at``.
            sort_order: Sort order: ``asc`` or ``desc``.
            page: Page number (default 1).
            per_page: Prompts per page (default 20).
            space_id: Optional space ID to search prompts in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``page``, ``perPage``, ``total`` and the
            ``data`` array of prompts.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.security_ai_assistant.find_prompts(
            ...     filter="security",
            ...     per_page=50,
            ... )
            >>> for prompt in found.body["data"]:
            ...     print(prompt["name"])
        """
        params: dict[str, Any] = {}
        if fields is not None:
            params["fields"] = fields
        if filter is not None:
            params["filter"] = filter
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security_ai_assistant/prompts/_find", space_id
        )
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def bulk_action_prompts(
        self,
        *,
        create: list[dict[str, Any]] | None = None,
        update: list[dict[str, Any]] | None = None,
        delete: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Apply a bulk action to prompts.

        ``POST /api/security_ai_assistant/prompts/_bulk_action``. Creates,
        updates and/or deletes multiple prompts in a single request. The
        delete action is applied to all prompts matching the filter query or
        to the listed prompt IDs.

        Args:
            create: List of prompts to create. Each prompt requires ``name``,
                ``content`` and ``promptType`` (``system`` or ``quick``).
                Note: on Kibana 9.4.3 the live server 500s when a prompt
                name contains KQL-special characters such as ``:`` (its
                internal duplicate-name check builds an unescaped KQL
                query), so avoid colons in prompt names.
            update: List of prompt updates. Each item requires ``id`` plus
                the fields to change (``content``, ``color``,
                ``categories``, ``isDefault``, ...).
            delete: Deletion criteria: ``{"ids": [...]}`` and/or
                ``{"query": "..."}``.
            space_id: Optional space ID to apply the bulk action in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``success``, ``prompts_count`` and an
            ``attributes`` object holding per-action ``results`` (``created``,
            ``updated``, ``deleted``, ``skipped``) and a ``summary``.

        Raises:
            BadRequestError: If the bulk action payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.security_ai_assistant.bulk_action_prompts(
            ...     create=[
            ...         {
            ...             "name": "New Security Prompt",
            ...             "content": "Please verify the security settings.",
            ...             "promptType": "quick",
            ...         }
            ...     ],
            ... )
            >>> print(result.body["attributes"]["results"]["created"][0]["id"])
        """
        body: dict[str, Any] = {}
        if create is not None:
            body["create"] = create
        if update is not None:
            body["update"] = update
        if delete is not None:
            body["delete"] = delete

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security_ai_assistant/prompts/_bulk_action",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Anonymization fields
    # ------------------------------------------------------------------

    async def find_anonymization_fields(
        self,
        *,
        fields: list[str] | None = None,
        filter: str | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        all_data: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get anonymization fields.

        ``GET /api/security_ai_assistant/anonymization_fields/_find``. Lists
        the anonymization fields that control which event fields are allowed
        to be sent to the model and which are anonymized first.

        Args:
            fields: Fields to return, e.g. ``["id", "field", "anonymized",
                "allowed"]``.
            filter: Search query, e.g. ``'field: "user.name"'``.
            sort_field: Field to sort by: ``created_at``, ``anonymized``,
                ``allowed``, ``field`` or ``updated_at``.
            sort_order: Sort order: ``asc`` or ``desc``.
            page: Page number (default 1).
            per_page: Anonymization fields per page (default 20).
            all_data: If True, additionally fetch all anonymization fields
                (returned under ``all``), otherwise fetch only the requested
                page.
            space_id: Optional space ID to search anonymization fields in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``page``, ``perPage``, ``total``, the
            ``data`` array, optional ``all`` array and ``aggregations``.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.security_ai_assistant.find_anonymization_fields(
            ...     filter='field: "host.name"',
            ... )
            >>> print(found.body["total"])
        """
        params: dict[str, Any] = {}
        if fields is not None:
            params["fields"] = fields
        if filter is not None:
            params["filter"] = filter
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if all_data is not None:
            params["all_data"] = all_data

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security_ai_assistant/anonymization_fields/_find",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def bulk_action_anonymization_fields(
        self,
        *,
        create: list[dict[str, Any]] | None = None,
        update: list[dict[str, Any]] | None = None,
        delete: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Apply a bulk action to anonymization fields.

        ``POST /api/security_ai_assistant/anonymization_fields/_bulk_action``.
        Creates, updates and/or deletes multiple anonymization fields in a
        single request. The delete action is applied to all fields matching
        the filter query or to the listed field IDs.

        Args:
            create: List of anonymization fields to create. Each item
                requires ``field`` (the ECS field name) and optionally
                ``allowed`` and ``anonymized`` booleans.
            update: List of anonymization field updates. Each item requires
                ``id`` plus the ``allowed``/``anonymized`` flags to change.
            delete: Deletion criteria: ``{"ids": [...]}`` and/or
                ``{"query": "..."}``.
            space_id: Optional space ID to apply the bulk action in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``success``, ``anonymization_fields_count``
            and an ``attributes`` object holding per-action ``results``
            (``created``, ``updated``, ``deleted``, ``skipped``) and a
            ``summary``.

        Raises:
            BadRequestError: If the bulk action payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.security_ai_assistant.bulk_action_anonymization_fields(
            ...     create=[
            ...         {"field": "host.name", "allowed": True, "anonymized": False},
            ...     ],
            ... )
            >>> print(result.body["attributes"]["summary"]["succeeded"])
        """
        body: dict[str, Any] = {}
        if create is not None:
            body["create"] = create
        if update is not None:
            body["update"] = update
        if delete is not None:
            body["delete"] = delete

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security_ai_assistant/anonymization_fields/_bulk_action",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Knowledge Base setup / status
    # ------------------------------------------------------------------

    async def get_knowledge_base(
        self,
        *,
        resource: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Read Knowledge Base status.

        ``GET /api/security_ai_assistant/knowledge_base`` or
        ``GET /api/security_ai_assistant/knowledge_base/{resource}`` when
        ``resource`` is provided. Returns the setup status of the assistant's
        Knowledge Base (ELSER model, Security Labs docs, user data, product
        documentation).

        Args:
            resource: Optional Knowledge Base resource identifier (e.g.
                ``security_labs``, ``defend_insights``, ``user``) to read the
                status for.
            space_id: Optional space ID to read the Knowledge Base status in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with status flags: ``elser_exists``,
            ``is_setup_available``, ``is_setup_in_progress``,
            ``security_labs_exists``, ``defend_insights_exists``,
            ``user_data_exists`` and ``product_documentation_status``.

        Raises:
            BadRequestError: If the request is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> status = await client.security_ai_assistant.get_knowledge_base()
            >>> print(status.body["elser_exists"])
        """
        base_path = "/api/security_ai_assistant/knowledge_base"
        if resource is not None:
            base_path = f"{base_path}/{_quote(resource)}"

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(base_path, space_id)
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def setup_knowledge_base(
        self,
        *,
        resource: str | None = None,
        model_id: str | None = None,
        ignore_security_labs: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Set up the Knowledge Base.

        ``POST /api/security_ai_assistant/knowledge_base`` or
        ``POST /api/security_ai_assistant/knowledge_base/{resource}`` when
        ``resource`` is provided. Installs and starts the ELSER model (if
        needed) and loads Knowledge Base content. Security Labs docs are
        installed by default unless ``ignore_security_labs`` is True.

        Args:
            resource: Optional Knowledge Base resource identifier (e.g.
                ``security_labs``, ``defend_insights``, ``user``) to set up.
            model_id: ELSER model ID to use when setting up the Knowledge
                Base. If not provided, a default model is used.
            ignore_security_labs: If True, skip installing Security Labs
                docs during setup. Defaults to False on the server.
            space_id: Optional space ID to set up the Knowledge Base in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``{"success": true}`` on success.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.security_ai_assistant.setup_knowledge_base(
            ...     ignore_security_labs=True,
            ... )
            >>> print(result.body["success"])
            True
        """
        params: dict[str, Any] = {}
        if model_id is not None:
            params["modelId"] = model_id
        if ignore_security_labs is not None:
            params["ignoreSecurityLabs"] = ignore_security_labs

        base_path = "/api/security_ai_assistant/knowledge_base"
        if resource is not None:
            base_path = f"{base_path}/{_quote(resource)}"

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(base_path, space_id)
        return await self.perform_request(
            "POST",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Knowledge Base entries
    # ------------------------------------------------------------------

    async def create_knowledge_base_entry(
        self,
        *,
        type: str,
        name: str,
        text: str | None = None,
        source: str | None = None,
        kb_resource: str | None = None,
        required: bool | None = None,
        vector: dict[str, Any] | None = None,
        index: str | None = None,
        field: str | None = None,
        description: str | None = None,
        query_description: str | None = None,
        input_schema: list[dict[str, Any]] | None = None,
        output_fields: list[str] | None = None,
        global_: bool | None = None,
        namespace: str | None = None,
        users: list[dict[str, Any]] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a Knowledge Base entry.

        ``POST /api/security_ai_assistant/knowledge_base/entries``. Creates
        either a ``document`` entry (inline text content) or an ``index``
        entry (an Elasticsearch index/data stream the assistant may query),
        depending on ``type``.

        Args:
            type: Entry type: ``document`` or ``index``.
            name: Name of the Knowledge Base entry.
            text: Entry content (required for ``document`` entries).
            source: Source document name or filepath (required for
                ``document`` entries).
            kb_resource: Knowledge Base resource grouping for the entry:
                ``security_labs``, ``defend_insights`` or ``user`` (required
                for ``document`` entries).
            required: Whether this document resource should always be
                included in the model context (``document`` entries only,
                defaults to False).
            vector: Optional pre-computed embeddings for ``document``
                entries: ``{"modelId": ..., "tokens": {...}}``.
            index: Index or data stream to query for content (required for
                ``index`` entries).
            field: Field to query for content (required for ``index``
                entries).
            description: Description of when this index should be queried,
                passed to the LLM as a tool description (required for
                ``index`` entries).
            query_description: Description of the query field, passed to the
                LLM as part of the tool input schema (required for ``index``
                entries).
            input_schema: Optional input-schema field definitions for
                ``index`` entries: ``[{"fieldName": ..., "fieldType": ...,
                "description": ...}]``.
            output_fields: Fields to extract from query results for ``index``
                entries; defaults to all fields.
            global_: Whether the entry is global (visible to all users).
                Sent as the ``global`` body field; defaults to False.
            namespace: Kibana space for the entry, defaults to the
                ``default`` space.
            users: Users with access to the entry, defaults to the current
                user. An empty array grants access to all users.
            space_id: Optional space ID to create the entry in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the created Knowledge Base entry,
            including its server-assigned ``id``.

        Raises:
            BadRequestError: If required fields for the entry type are
                missing or invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> entry = await client.security_ai_assistant.create_knowledge_base_entry(
            ...     type="document",
            ...     name="Password reset runbook",
            ...     kb_resource="user",
            ...     source="/runbooks/password-reset.md",
            ...     text="To reset a password, open the settings page ...",
            ... )
            >>> print(entry.body["id"])
        """
        body: dict[str, Any] = {"type": type, "name": name}
        if text is not None:
            body["text"] = text
        if source is not None:
            body["source"] = source
        if kb_resource is not None:
            body["kbResource"] = kb_resource
        if required is not None:
            body["required"] = required
        if vector is not None:
            body["vector"] = vector
        if index is not None:
            body["index"] = index
        if field is not None:
            body["field"] = field
        if description is not None:
            body["description"] = description
        if query_description is not None:
            body["queryDescription"] = query_description
        if input_schema is not None:
            body["inputSchema"] = input_schema
        if output_fields is not None:
            body["outputFields"] = output_fields
        if global_ is not None:
            body["global"] = global_
        if namespace is not None:
            body["namespace"] = namespace
        if users is not None:
            body["users"] = users

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security_ai_assistant/knowledge_base/entries",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def get_knowledge_base_entry(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Get a Knowledge Base entry.

        ``GET /api/security_ai_assistant/knowledge_base/entries/{id}``.
        Retrieves a Knowledge Base entry by its unique ID.

        Args:
            id: The unique identifier of the Knowledge Base entry.
            space_id: Optional space ID to get the entry from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the Knowledge Base entry.

        Raises:
            NotFoundError: If the entry does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> entry = await client.security_ai_assistant.get_knowledge_base_entry(
            ...     id="12345",
            ... )
            >>> print(entry.body["name"])
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/security_ai_assistant/knowledge_base/entries/{_quote(id)}",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            headers={"accept": "application/json"},
        )

    async def update_knowledge_base_entry(
        self,
        *,
        id: str,
        type: str,
        name: str,
        text: str | None = None,
        source: str | None = None,
        kb_resource: str | None = None,
        required: bool | None = None,
        vector: dict[str, Any] | None = None,
        index: str | None = None,
        field: str | None = None,
        description: str | None = None,
        query_description: str | None = None,
        input_schema: list[dict[str, Any]] | None = None,
        output_fields: list[str] | None = None,
        global_: bool | None = None,
        namespace: str | None = None,
        users: list[dict[str, Any]] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Update a Knowledge Base entry.

        ``PUT /api/security_ai_assistant/knowledge_base/entries/{id}``.
        Replaces an existing Knowledge Base entry. The body follows the same
        ``document``/``index`` union as
        :meth:`create_knowledge_base_entry`, so the type-specific required
        fields must be provided again.

        Args:
            id: The unique identifier of the Knowledge Base entry to update.
            type: Entry type: ``document`` or ``index``.
            name: Name of the Knowledge Base entry.
            text: Entry content (required for ``document`` entries).
            source: Source document name or filepath (required for
                ``document`` entries).
            kb_resource: Knowledge Base resource grouping for the entry:
                ``security_labs``, ``defend_insights`` or ``user`` (required
                for ``document`` entries).
            required: Whether this document resource should always be
                included in the model context (``document`` entries only).
            vector: Optional pre-computed embeddings for ``document``
                entries.
            index: Index or data stream to query for content (required for
                ``index`` entries).
            field: Field to query for content (required for ``index``
                entries).
            description: Description of when this index should be queried
                (required for ``index`` entries).
            query_description: Description of the query field (required for
                ``index`` entries).
            input_schema: Optional input-schema field definitions for
                ``index`` entries.
            output_fields: Fields to extract from query results for ``index``
                entries.
            global_: Whether the entry is global (visible to all users).
                Sent as the ``global`` body field.
            namespace: Kibana space for the entry.
            users: Users with access to the entry.
            space_id: Optional space ID to update the entry in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the updated Knowledge Base entry.

        Raises:
            NotFoundError: If the entry does not exist.
            BadRequestError: If the update payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> updated = await client.security_ai_assistant.update_knowledge_base_entry(
            ...     id="12345",
            ...     type="document",
            ...     name="Password reset runbook (updated)",
            ...     kb_resource="user",
            ...     source="/runbooks/password-reset.md",
            ...     text="Updated instructions ...",
            ... )
            >>> print(updated.body["name"])
        """
        body: dict[str, Any] = {"type": type, "name": name}
        if text is not None:
            body["text"] = text
        if source is not None:
            body["source"] = source
        if kb_resource is not None:
            body["kbResource"] = kb_resource
        if required is not None:
            body["required"] = required
        if vector is not None:
            body["vector"] = vector
        if index is not None:
            body["index"] = index
        if field is not None:
            body["field"] = field
        if description is not None:
            body["description"] = description
        if query_description is not None:
            body["queryDescription"] = query_description
        if input_schema is not None:
            body["inputSchema"] = input_schema
        if output_fields is not None:
            body["outputFields"] = output_fields
        if global_ is not None:
            body["global"] = global_
        if namespace is not None:
            body["namespace"] = namespace
        if users is not None:
            body["users"] = users

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/security_ai_assistant/knowledge_base/entries/{_quote(id)}",
            space_id,
        )
        return await self.perform_request(
            "PUT",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    async def delete_knowledge_base_entry(
        self,
        *,
        id: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Delete a Knowledge Base entry.

        ``DELETE /api/security_ai_assistant/knowledge_base/entries/{id}``.
        Deletes a Knowledge Base entry by its unique ID.

        Args:
            id: The unique identifier of the Knowledge Base entry to delete.
            space_id: Optional space ID to delete the entry from.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the ``id`` of the deleted entry.

        Raises:
            NotFoundError: If the entry does not exist.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> await client.security_ai_assistant.delete_knowledge_base_entry(
            ...     id="12345",
            ... )
        """
        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            f"/api/security_ai_assistant/knowledge_base/entries/{_quote(id)}",
            space_id,
        )
        return await self.perform_request(
            "DELETE",
            path,
            headers={"accept": "application/json"},
        )

    async def find_knowledge_base_entries(
        self,
        *,
        fields: list[str] | None = None,
        filter: str | None = None,
        sort_field: str | None = None,
        sort_order: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Find Knowledge Base entries.

        ``GET /api/security_ai_assistant/knowledge_base/entries/_find``.
        Finds Knowledge Base entries that match the given query, with
        sorting and pagination.

        Args:
            fields: A list of fields to include in the response. If not
                provided, all fields are included.
            filter: Search query to filter entries by specific criteria.
            sort_field: Field to sort by: ``created_at``, ``is_default``,
                ``title`` or ``updated_at``.
            sort_order: Sort order: ``asc`` or ``desc``.
            page: Page number (default 1).
            per_page: Entries per page (default 20).
            space_id: Optional space ID to search entries in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``page``, ``perPage``, ``total`` and the
            ``data`` array of Knowledge Base entries.

        Raises:
            BadRequestError: If a query parameter is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> found = await client.security_ai_assistant.find_knowledge_base_entries(
            ...     per_page=50,
            ... )
            >>> print(found.body["total"])
        """
        params: dict[str, Any] = {}
        if fields is not None:
            params["fields"] = fields
        if filter is not None:
            params["filter"] = filter
        if sort_field is not None:
            params["sort_field"] = sort_field
        if sort_order is not None:
            params["sort_order"] = sort_order
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security_ai_assistant/knowledge_base/entries/_find",
            space_id,
        )
        return await self.perform_request(
            "GET",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
        )

    async def bulk_action_knowledge_base_entries(
        self,
        *,
        create: list[dict[str, Any]] | None = None,
        update: list[dict[str, Any]] | None = None,
        delete: dict[str, Any] | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Apply a bulk action to Knowledge Base entries.

        ``POST /api/security_ai_assistant/knowledge_base/entries/_bulk_action``.
        Creates, updates and/or deletes multiple Knowledge Base entries in a
        single request. The delete action is applied to all entries matching
        the filter query or to the listed entry IDs.

        Args:
            create: List of entries to create. Each item follows the same
                ``document``/``index`` union as
                :meth:`create_knowledge_base_entry` (e.g. ``{"type":
                "document", "name": ..., "kbResource": ..., "source": ...,
                "text": ...}``).
            update: List of entry updates. Each item requires ``id`` plus the
                entry fields to change.
            delete: Deletion criteria: ``{"ids": [...]}`` and/or
                ``{"query": "..."}``.
            space_id: Optional space ID to apply the bulk action in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with ``success``, ``knowledgeBaseEntriesCount``
            and an ``attributes`` object holding per-action ``results``
            (``created``, ``updated``, ``deleted``, ``skipped``) and a
            ``summary``.

        Raises:
            BadRequestError: If the bulk action payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> result = await client.security_ai_assistant.bulk_action_knowledge_base_entries(
            ...     delete={"ids": ["123", "456"]},
            ... )
            >>> print(result.body["attributes"]["summary"]["succeeded"])
        """
        body: dict[str, Any] = {}
        if create is not None:
            body["create"] = create
        if update is not None:
            body["update"] = update
        if delete is not None:
            body["delete"] = delete

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security_ai_assistant/knowledge_base/entries/_bulk_action",
            space_id,
        )
        return await self.perform_request(
            "POST",
            path,
            headers={"accept": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    async def chat_complete(
        self,
        *,
        connector_id: str,
        messages: list[dict[str, Any]],
        persist: bool,
        conversation_id: str | None = None,
        is_stream: bool | None = None,
        lang_smith_api_key: str | None = None,
        lang_smith_project: str | None = None,
        model: str | None = None,
        prompt_id: str | None = None,
        response_language: str | None = None,
        content_references_disabled: bool | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Create a model response for a chat conversation.

        ``POST /api/security_ai_assistant/chat/complete``. Sends the chat
        messages to the LLM behind the given Kibana AI connector and returns
        the model response. Depending on the model and local setup this call
        can take a while; consider raising the request timeout via
        ``client.options(request_timeout=...)``.

        Args:
            connector_id: Kibana AI connector ID used to route the request
                (e.g. a ``.gen-ai`` connector).
            messages: List of chat messages exchanged so far. Each message
                requires ``role`` (``system``, ``user`` or ``assistant``)
                and typically ``content``; optional ``data`` and
                ``fields_to_anonymize`` attach anonymizable metadata.
            persist: Whether to persist the chat and response as a Security
                AI Assistant conversation.
            conversation_id: Existing conversation ID to continue (used with
                ``persist=True``).
            is_stream: If True, the response is streamed in chunks
                (``application/octet-stream``) instead of a single JSON
                object.
            lang_smith_api_key: API key for LangSmith integration.
            lang_smith_project: LangSmith project name for tracing.
            model: Model ID or name to use for the response (overrides the
                connector's default model).
            prompt_id: Prompt template identifier.
            response_language: ISO language code for the assistant's
                response.
            content_references_disabled: If True, the response will not
                include content references (sent as the
                ``content_references_disabled`` query parameter).
            space_id: Optional space ID to run the chat in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse with the model response. For non-streaming
            calls the body contains ``connector_id``, ``data`` (the response
            text), ``replacements``, ``trace_data`` and ``status``.

        Raises:
            BadRequestError: If the request payload is invalid.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            ApiError: If the connector call to the model fails.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = await client.options(request_timeout=120).security_ai_assistant.chat_complete(
            ...     connector_id="my-openai-connector",
            ...     messages=[
            ...         {"role": "user", "content": "What are common phishing techniques?"},
            ...     ],
            ...     persist=False,
            ... )
            >>> print(response.body["data"])
        """
        body: dict[str, Any] = {
            "connectorId": connector_id,
            "messages": messages,
            "persist": persist,
        }
        if conversation_id is not None:
            body["conversationId"] = conversation_id
        if is_stream is not None:
            body["isStream"] = is_stream
        if lang_smith_api_key is not None:
            body["langSmithApiKey"] = lang_smith_api_key
        if lang_smith_project is not None:
            body["langSmithProject"] = lang_smith_project
        if model is not None:
            body["model"] = model
        if prompt_id is not None:
            body["promptId"] = prompt_id
        if response_language is not None:
            body["responseLanguage"] = response_language

        params: dict[str, Any] = {}
        if content_references_disabled is not None:
            params["content_references_disabled"] = content_references_disabled

        await self._maybe_validate_space(space_id, validate_spaces)
        path = self._build_space_path(
            "/api/security_ai_assistant/chat/complete", space_id
        )
        return await self.perform_request(
            "POST",
            path,
            params=params if params else None,
            headers={"accept": "application/json"},
            body=body,
        )
