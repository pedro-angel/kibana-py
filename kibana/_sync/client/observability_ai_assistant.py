"""Kibana Observability AI Assistant API client."""

from typing import TYPE_CHECKING, Any

from elastic_transport import ObjectApiResponse

from kibana._sync.client.utils import NamespaceClient

if TYPE_CHECKING:
    from kibana._sync.client import Kibana


class ObservabilityAiAssistantClient(NamespaceClient):
    """Client for the Kibana Observability AI Assistant API.

    The Observability AI Assistant chat completion API generates responses
    from a large language model (LLM) based on the current conversation
    context. It also handles any tool (function) requests within the
    conversation, which may trigger multiple calls to the underlying LLM.

    The API is marked as **Technical Preview** in Kibana 9.4 and may change
    or be removed in a future release.

    The API requires a preconfigured AI (LLM) connector (for example an
    OpenAI, Azure OpenAI or Amazon Bedrock connector) identified by
    ``connector_id``. Conversations are space-scoped: every method accepts
    an optional ``space_id`` to target a specific space (``None`` targets
    the default space or the space the client is scoped to).

    Note:
        On success (HTTP 200) Kibana streams the model output as
        server-sent events (``data: {...}`` chunks terminated by
        ``data: [DONE]``) with content type ``application/octet-stream``,
        so the returned response body is the raw event stream rather than
        a parsed JSON object.

    Example:
        >>> from kibana import Kibana
        >>> client = Kibana("http://localhost:5601", api_key="...")
        >>>
        >>> response = client.observability_ai_assistant.chat_complete(
        ...     connector_id="my-openai-connector",
        ...     persist=False,
        ...     messages=[
        ...         {
        ...             "@timestamp": "2026-07-03T00:00:00.000Z",
        ...             "message": {
        ...                 "role": "user",
        ...                 "content": "Is my Elasticsearch cluster healthy?",
        ...             },
        ...         }
        ...     ],
        ... )
        >>> print(response.body)  # raw SSE stream of completion chunks
    """

    def __init__(
        self,
        client: Kibana,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """Initialize the ObservabilityAiAssistantClient.

        Args:
            client: The parent Kibana client instance to delegate requests to.
            default_space_id: Optional default space ID for all operations.
            validate_spaces: Whether to validate space existence before
                space-scoped operations (default: True).

        Example:
            >>> ai_assistant_client = ObservabilityAiAssistantClient(kibana_client)
        """
        super().__init__(client, default_space_id, validate_spaces)

    def chat_complete(
        self,
        *,
        messages: list[dict[str, Any]],
        connector_id: str,
        persist: bool,
        actions: list[dict[str, Any]] | None = None,
        conversation_id: str | None = None,
        disable_functions: bool | None = None,
        instructions: list[str | dict[str, Any]] | None = None,
        title: str | None = None,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> ObjectApiResponse[Any]:
        """Generate a chat completion.

        Technical preview in 9.4. Creates a new chat completion by using the
        Observability AI Assistant. The API returns the model's response
        based on the current conversation context, and handles any tool
        requests within the conversation (which may trigger multiple calls
        to the underlying LLM).

        Args:
            messages: An array of message objects containing the conversation
                history. Each message requires ``@timestamp`` (ISO 8601
                string) and a ``message`` object with at least a ``role``
                (one of ``"system"``, ``"assistant"``, ``"function"``,
                ``"user"``, ``"elastic"``) plus optional ``content``,
                ``name``, ``event``, ``data`` and ``function_call`` fields.
            connector_id: A unique identifier for the AI (LLM) connector.
            persist: Indicates whether the conversation should be saved to
                storage. If True, the conversation is saved and available in
                Kibana.
            actions: An array of function definitions the model may call.
                Each function object has ``name``, ``description`` and JSON
                schema ``parameters``.
            conversation_id: A unique identifier for the conversation if you
                are continuing an existing conversation.
            disable_functions: Flag indicating whether all function calls
                should be disabled for the conversation. If True, no calls
                to functions are made.
            instructions: An array of instruction objects, which can be
                either simple strings or detailed objects with ``id`` and
                ``text`` fields.
            title: A title for the conversation.
            space_id: Optional space ID to run the conversation in.
            validate_spaces: Override space validation setting for this
                operation.

        Returns:
            ObjectApiResponse whose body is the raw server-sent event stream
            of chat completion chunks (``data: {...}`` lines terminated by
            ``data: [DONE]``). At runtime Kibana serves it with content type
            ``application/octet-stream``, so the body is bytes, not parsed
            JSON.

        Raises:
            BadRequestError: If the request body fails validation (e.g.
                missing ``messages`` or ``connectorId``).
            NotFoundError: If no connector or inference endpoint exists for
                ``connector_id``.
            AuthenticationException: If authentication fails.
            AuthorizationException: If insufficient privileges.
            SpaceNotFoundError: If the space doesn't exist and validation is
                enabled.

        Example:
            >>> response = client.observability_ai_assistant.chat_complete(
            ...     connector_id="my-openai-connector",
            ...     persist=False,
            ...     disable_functions=True,
            ...     messages=[
            ...         {
            ...             "@timestamp": "2026-07-03T00:00:00.000Z",
            ...             "message": {"role": "user", "content": "Hello"},
            ...         }
            ...     ],
            ...     instructions=["Answer concisely."],
            ... )
            >>> print(response.meta.status)
            200
        """
        body: dict[str, Any] = {
            "messages": messages,
            "connectorId": connector_id,
            "persist": persist,
        }
        if actions is not None:
            body["actions"] = actions
        if conversation_id is not None:
            body["conversationId"] = conversation_id
        if disable_functions is not None:
            body["disableFunctions"] = disable_functions
        if instructions is not None:
            body["instructions"] = instructions
        if title is not None:
            body["title"] = title

        path = self._build_space_path(
            "/api/observability_ai_assistant/chat/complete",
            space_id,
            validate_spaces,
        )
        return self.perform_request(
            "POST",
            path,
            headers={"accept": "text/event-stream, application/json"},
            body=body,
        )
