"""Base client implementation for Kibana."""

import base64
import logging
from collections.abc import Mapping
from typing import Any

from elastic_transport import (
    HttpHeaders,
    ObjectApiResponse,
    Transport,
    TransportApiResponse,
)

from kibana.exceptions import HTTP_EXCEPTIONS, ApiError
from kibana.observability import KibanaInstrumentor, span_context

# Set up logger
logger = logging.getLogger("kibana")


# Sentinel value for default parameters
class DefaultType:
    """Sentinel class for default parameter values."""

    pass


DEFAULT = DefaultType()


def _redact_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    """
    Redact sensitive information from headers for logging.

    :param headers: Original headers dictionary
    :return: Headers with sensitive values redacted
    """
    sensitive_keys = {
        "authorization",
        "x-api-key",
        "api-key",
        "x-elastic-api-key",
    }

    redacted = {}
    for key, value in headers.items():
        key_lower = key.lower()
        if key_lower in sensitive_keys:
            # Redact the value but show the auth type
            if value.startswith("ApiKey "):
                redacted[key] = "ApiKey [REDACTED]"
            elif value.startswith("Basic "):
                redacted[key] = "Basic [REDACTED]"
            elif value.startswith("Bearer "):
                redacted[key] = "Bearer [REDACTED]"
            else:
                redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value

    return redacted


_SENSITIVE_BODY_KEYS = {"secrets", "secret", "password", "token", "api_key", "apikey"}


def _redact_body_secrets(body: dict[str, Any]) -> dict[str, Any]:
    """
    Redact sensitive fields from a request body for safe logging.

    Connector creation/update payloads often contain a ``secrets`` dict with
    credentials (webhook URLs, passwords, API tokens, etc.).  This helper
    produces a shallow copy with those fields replaced by ``[REDACTED]``.

    :param body: Original request body dictionary
    :return: Copy of the body with sensitive values redacted
    """
    redacted: dict[str, Any] = {}
    for key, value in body.items():
        if key.lower() in _SENSITIVE_BODY_KEYS:
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            # One level of nesting (e.g. {"config": {"password": "x"}})
            redacted[key] = _redact_body_secrets(value)
        else:
            redacted[key] = value
    return redacted


def resolve_auth_headers(
    *,
    api_key: str | tuple[str, str] | None = None,
    basic_auth: tuple[str, str] | None = None,
    bearer_auth: str | None = None,
) -> dict[str, str]:
    """Resolve authentication credentials to HTTP headers.

    Converts authentication credentials into the appropriate HTTP Authorization
    header format. Supports three authentication methods with the following
    precedence: API key > Basic auth > Bearer token.

    Args:
        api_key: API key for authentication. Can be:
            - String: Base64-encoded API key (e.g., "VnVhQ2ZHY0JDZGJrU...")
            - Tuple: (id, api_key) which will be encoded as "id:api_key"
        basic_auth: Basic authentication credentials as (username, password)
            tuple. Will be base64-encoded automatically.
        bearer_auth: Bearer token string for JWT or OAuth authentication.

    Returns:
        Dictionary containing the Authorization header. Empty dict if no
        authentication credentials are provided.

    Example:
        >>> # API key as string
        >>> headers = resolve_auth_headers(api_key="VnVhQ2ZHY0JDZGJrU...")
        >>> print(headers)
        {'authorization': 'ApiKey VnVhQ2ZHY0JDZGJrU...'}
        >>>
        >>> # API key as tuple
        >>> headers = resolve_auth_headers(api_key=("my-id", "my-secret"))
        >>> print(headers)
        {'authorization': 'ApiKey bXktaWQ6bXktc2VjcmV0'}
        >>>
        >>> # Basic authentication
        >>> headers = resolve_auth_headers(basic_auth=("admin", "password"))
        >>> print(headers)
        {'authorization': 'Basic YWRtaW46cGFzc3dvcmQ='}
        >>>
        >>> # Bearer token
        >>> headers = resolve_auth_headers(bearer_auth="eyJhbGciOiJIUzI1...")
        >>> print(headers)
        {'authorization': 'Bearer eyJhbGciOiJIUzI1...'}
    """
    headers = {}

    # API key takes precedence
    if api_key is not None:
        if isinstance(api_key, tuple):
            # Tuple format: (id, api_key)
            api_key_id, api_key_secret = api_key
            api_key_str = f"{api_key_id}:{api_key_secret}"
            encoded = base64.b64encode(api_key_str.encode()).decode()
            headers["authorization"] = f"ApiKey {encoded}"
        else:
            # String format: already base64 encoded
            headers["authorization"] = f"ApiKey {api_key}"
    elif basic_auth is not None:
        # Basic authentication
        username, password = basic_auth
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        headers["authorization"] = f"Basic {encoded}"
    elif bearer_auth is not None:
        # Bearer token
        headers["authorization"] = f"Bearer {bearer_auth}"

    return headers


class BaseClient:
    """Base client class for Kibana and AsyncKibana.

    Provides common functionality for making requests, handling responses,
    and managing client options. This class is not meant to be instantiated
    directly; use Kibana or AsyncKibana instead.

    The BaseClient handles:
    - HTTP request execution via elastic-transport
    - Authentication header resolution (API key, basic auth, bearer token)
    - Response processing and error handling
    - Per-request configuration via the options() method

    Attributes:
        _transport: The elastic-transport Transport instance for HTTP requests.
        _headers: HTTP headers to include in requests.
        _api_key: API key for authentication (string or tuple).
        _basic_auth: Basic authentication credentials (username, password).
        _bearer_auth: Bearer token for authentication.
        _request_timeout: Request timeout in seconds.
        _custom_headers: Custom headers to include in all requests.
    """

    def __init__(self, _transport: Transport) -> None:
        """Initialize BaseClient with a transport instance.

        Args:
            _transport: Transport instance from elastic-transport for making
                HTTP requests to Kibana.

        Example:
            >>> from elastic_transport import Transport
            >>> transport = Transport(["http://localhost:5601"])
            >>> client = BaseClient(_transport=transport)
        """
        self._transport = _transport
        self._headers = HttpHeaders()
        self._api_key: str | tuple[str, str] | None = None
        self._basic_auth: tuple[str, str] | None = None
        self._bearer_auth: str | None = None
        self._request_timeout: float | None = None
        self._custom_headers: Mapping[str, str] | None = None
        self._rate_limiter: Any | None = None

    def options(
        self,
        *,
        api_key: DefaultType | str | tuple[str, str] = DEFAULT,
        basic_auth: DefaultType | tuple[str, str] = DEFAULT,
        bearer_auth: DefaultType | str = DEFAULT,
        headers: DefaultType | Mapping[str, str] = DEFAULT,
        request_timeout: DefaultType | float = DEFAULT,
    ) -> "BaseClient":
        """Create a new client instance with modified options.

        This method allows per-request configuration without modifying the
        original client instance. It creates a shallow copy with updated
        settings, enabling different authentication or configuration for
        specific requests.

        Args:
            api_key: API key for authentication. Can be:
                - String: Base64-encoded API key
                - Tuple: (id, api_key) to be encoded automatically
                If provided, takes precedence over other auth methods.
            basic_auth: Basic authentication credentials as (username, password)
                tuple. Used if api_key is not provided.
            bearer_auth: Bearer token string for authentication. Used if neither
                api_key nor basic_auth is provided.
            headers: Custom HTTP headers to include in requests. These will be
                merged with default headers.
            request_timeout: Request timeout in seconds. Overrides the default
                timeout for this client instance.

        Returns:
            A new BaseClient instance with the specified options applied.
            The original client remains unchanged.

        Example:
            >>> # Create client with default auth
            >>> client = Kibana("http://localhost:5601", api_key="default_key")
            >>>
            >>> # Make a request with different auth
            >>> special_client = client.options(api_key="special_key")
            >>> response = special_client.actions.get_all()
            >>>
            >>> # Original client still uses default auth
            >>> response = client.actions.get_all()
            >>>
            >>> # Use custom headers for a single request
            >>> custom_client = client.options(
            ...     headers={"X-Custom-Header": "value"},
            ...     request_timeout=30.0
            ... )
        """
        # Create a new instance with the same transport
        new_client = self.__class__(_transport=self._transport)

        # Copy existing settings
        new_client._api_key = self._api_key
        new_client._basic_auth = self._basic_auth
        new_client._bearer_auth = self._bearer_auth
        new_client._request_timeout = self._request_timeout
        new_client._custom_headers = self._custom_headers
        new_client._rate_limiter = self._rate_limiter

        # Apply new options if provided
        if not isinstance(api_key, DefaultType):
            new_client._api_key = api_key
        if not isinstance(basic_auth, DefaultType):
            new_client._basic_auth = basic_auth
        if not isinstance(bearer_auth, DefaultType):
            new_client._bearer_auth = bearer_auth
        if not isinstance(headers, DefaultType):
            new_client._custom_headers = headers
        if not isinstance(request_timeout, DefaultType):
            new_client._request_timeout = request_timeout

        return new_client

    def perform_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> ObjectApiResponse[Any]:
        """Perform an HTTP request to Kibana.

        This method handles the complete request lifecycle including:
        - Building authentication headers
        - Adding required Kibana headers (kbn-xsrf, content-type)
        - Creating OpenTelemetry spans for observability
        - Executing the request via elastic-transport
        - Processing the response and handling errors

        Args:
            method: HTTP method to use (GET, POST, PUT, DELETE, PATCH, etc.).
            path: API endpoint path starting with / (e.g., "/api/status").
            params: Optional query parameters as a dictionary. Will be URL-encoded
                and appended to the path.
            headers: Optional HTTP headers to include in the request. These will
                be merged with authentication and default headers.
            body: Optional request body as a dictionary. Will be JSON-serialized
                automatically.

        Returns:
            ObjectApiResponse containing the parsed JSON response body and
            metadata about the request/response.

        Raises:
            BadRequestError: If the request is malformed (400).
            AuthenticationException: If authentication fails (401).
            AuthorizationException: If insufficient privileges (403).
            NotFoundError: If the resource is not found (404).
            ConflictError: If there's a conflict (409).
            ApiError: For other API errors (4xx, 5xx status codes).
            TransportError: For connection or transport-level errors.

        Example:
            >>> # Simple GET request
            >>> response = client.perform_request("GET", "/api/status")
            >>> print(response.body["status"]["overall"]["level"])
            >>>
            >>> # POST request with body
            >>> response = client.perform_request(
            ...     "POST",
            ...     "/api/actions/connector",
            ...     body={
            ...         "name": "My Webhook",
            ...         "connector_type_id": ".webhook",
            ...         "config": {"url": "https://example.com"}
            ...     }
            ... )
            >>>
            >>> # Request with query parameters
            >>> response = client.perform_request(
            ...     "GET",
            ...     "/api/saved_objects/_find",
            ...     params={"type": "dashboard", "per_page": 10}
            ... )
        """
        # Build headers
        request_headers = {}

        # Apply rate limiting if configured
        if self._rate_limiter is not None:
            self._rate_limiter.acquire()

        # Add Content-Type header if body is present
        if body is not None:
            request_headers["content-type"] = "application/json"

        # Add kbn-xsrf header for non-GET requests (Kibana CSRF protection)
        if method.upper() != "GET":
            request_headers["kbn-xsrf"] = "true"

        # Add authentication headers
        auth_headers = resolve_auth_headers(
            api_key=self._api_key,
            basic_auth=self._basic_auth,
            bearer_auth=self._bearer_auth,
        )
        request_headers.update(auth_headers)

        # Add custom headers from options
        if self._custom_headers:
            request_headers.update(self._custom_headers)

        # Add per-request headers (these can override Content-Type if needed)
        if headers:
            request_headers.update(headers)

        # Build target URL with query parameters
        target = path
        if params:
            from urllib.parse import urlencode

            query_string = urlencode(params)
            target = f"{path}?{query_string}"

        # Log request details at DEBUG level with redacted headers
        if logger.isEnabledFor(logging.DEBUG):
            redacted_headers = _redact_sensitive_headers(request_headers)
            logger.debug(
                "Making %s request to %s with headers: %s",
                method,
                target,
                redacted_headers,
            )
            if body is not None:
                logger.debug("Request body: %s", _redact_body_secrets(body))

        # Build span attributes using OTel semantic conventions
        instrumentor = KibanaInstrumentor.get_instance()
        span_attrs: dict[str, Any] | None = None
        if instrumentor.is_enabled():
            span_attrs = {
                "http.request.method": method,
                "url.full": target,
                "url.path": path,
            }
            if params:
                span_attrs["url.query"] = str(params)

        # Prepare request kwargs
        request_kwargs: dict[str, Any] = {
            "method": method,
            "target": target,
        }

        if request_headers:
            request_kwargs["headers"] = request_headers
        if body is not None:
            request_kwargs["body"] = body
        if self._request_timeout is not None:
            request_kwargs["request_timeout"] = self._request_timeout

        with span_context(f"kibana.{method.lower()}", attributes=span_attrs) as span:
            # Perform the request
            response: TransportApiResponse = self._transport.perform_request(
                **request_kwargs
            )

            # Add response status to span
            if span is not None:
                span.set_attribute(
                    "http.response.status_code",
                    response.meta.status,
                )

            # Process the response (check for errors)
            return self._process_response(response)  # type: ignore[arg-type]

    def _process_response(
        self, response: ObjectApiResponse[Any]
    ) -> ObjectApiResponse[Any]:
        """
        Process API response and raise exceptions for error status codes.

        :param response: API response from transport
        :return: The response if successful
        :raises ApiError: If the response indicates an error
        """
        status = response.meta.status

        # Check if this is an error response
        if status >= 400:
            # Extract error message from response body
            error_message = self._extract_error_message(response.body)

            # Log error
            logger.debug(
                "Request failed with status %s: %s",
                status,
                error_message,
            )

            # Get the appropriate exception class for this status code
            exception_class = HTTP_EXCEPTIONS.get(status, ApiError)

            # Raise the exception
            raise exception_class(
                message=error_message,
                meta=response.meta,
                body=response.body,
            )

        # Log successful response at DEBUG level
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Request completed successfully with status %s",
                status,
            )
            # Log response body for debugging (truncate if too large)
            body_str = str(response.body)
            if len(body_str) > 500:
                body_str = body_str[:500] + "... [truncated]"
            logger.debug("Response body: %s", body_str)

        return response

    def _extract_error_message(self, body: Any) -> str:
        """
        Extract error message from response body.

        :param body: Response body
        :return: Error message string
        """
        if isinstance(body, dict):
            # Try common error message fields
            if "error" in body:
                error = body["error"]
                if isinstance(error, str):
                    return error
                elif isinstance(error, dict):
                    # Kibana often returns error as an object
                    if "message" in error:
                        return str(error["message"])
                    elif "reason" in error:
                        return str(error["reason"])
            elif "message" in body:
                return str(body["message"])

        # Fallback to generic message
        return f"API error occurred: {body}"
