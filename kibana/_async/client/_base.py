"""Async base client implementation for Kibana."""

import logging
from collections.abc import Mapping
from typing import Any, Self

from elastic_transport import (
    ApiResponse,
    AsyncTransport,
    HttpHeaders,
    ObjectApiResponse,
    TransportApiResponse,
)

# Import shared helpers from the sync version (they're not async)
from kibana._sync.client._base import (
    DEFAULT,
    DefaultType,
    _redact_body_secrets,
    _redact_sensitive_headers,
    encode_query_params,
    extract_error_message,
    resolve_auth_headers,
    wrap_api_response,
)
from kibana.exceptions import HTTP_EXCEPTIONS, ApiError
from kibana.observability import KibanaInstrumentor, span_context

__all__ = ["AsyncBaseClient", "DEFAULT", "DefaultType"]

# Set up logger
logger = logging.getLogger("kibana")


class AsyncBaseClient:
    """
    Async base client class for AsyncKibana.

    Provides common functionality for making async requests, handling responses,
    and managing client options.
    """

    def __init__(self, _transport: AsyncTransport) -> None:
        """
        Initialize AsyncBaseClient.

        :param _transport: AsyncTransport instance for making HTTP requests
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
    ) -> Self:
        """
        Create a new client instance with modified options.

        This allows per-request configuration without modifying the original client.

        :param api_key: API key for authentication
        :param basic_auth: Basic auth credentials (username, password)
        :param bearer_auth: Bearer token for authentication
        :param headers: Custom headers to include in requests
        :param request_timeout: Request timeout in seconds
        :return: New AsyncBaseClient instance with updated options
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

    async def perform_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        body: Any | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Perform an async HTTP request to Kibana.

        :param method: HTTP method (GET, POST, PUT, DELETE, etc.)
        :param path: API endpoint path
        :param params: Query parameters
        :param headers: Request headers
        :param body: Request body
        :return: API response
        :raises ApiError: If the API returns an error response
        """
        # Build headers
        request_headers = {}

        # Apply rate limiting if configured
        if self._rate_limiter is not None:
            await self._rate_limiter.acquire()

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
            target = f"{path}?{encode_query_params(params)}"

        # Log request details at DEBUG level with redacted headers
        if logger.isEnabledFor(logging.DEBUG):
            redacted_headers = _redact_sensitive_headers(request_headers)
            logger.debug(
                "Making async %s request to %s with headers: %s",
                method,
                target,
                redacted_headers,
            )
            if isinstance(body, dict):
                logger.debug("Request body: %s", _redact_body_secrets(body))
            elif body is not None:
                logger.debug("Request body: <%d raw bytes>", len(body))

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

        with span_context(
            f"kibana.async.{method.lower()}", attributes=span_attrs
        ) as span:
            # Perform the async request
            response: TransportApiResponse = await self._transport.perform_request(
                **request_kwargs
            )

            # Add response status to span
            if span is not None:
                span.set_attribute(
                    "http.response.status_code",
                    response.meta.status,
                )

            # Wrap the raw transport response in a typed ApiResponse and
            # check for errors
            return self._process_response(wrap_api_response(response))  # type: ignore[return-value]

    def _process_response(self, response: ApiResponse[Any]) -> ApiResponse[Any]:
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
                "Async request failed with status %s: %s",
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
                "Async request completed successfully with status %s",
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
        return extract_error_message(body)
