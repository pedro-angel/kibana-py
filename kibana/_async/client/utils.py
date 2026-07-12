"""Utility classes and functions for async Kibana client namespace implementations."""

from __future__ import annotations

import re
import time
from typing import Any

from elastic_transport import ObjectApiResponse

from kibana._async.client._base import AsyncBaseClient
from kibana.exceptions import InvalidSpaceIdError, NotFoundError, SpaceNotFoundError


class AsyncNamespaceClient:
    """
    Base class for all async namespace clients (saved_objects, spaces, actions, etc.).

    Provides common functionality for making requests through the parent client,
    space support with validation and caching, and utility functions for
    parameter handling and URL encoding.
    """

    def __init__(
        self,
        client: AsyncBaseClient,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """
        Initialize AsyncNamespaceClient with optional space support.

        :param client: Parent AsyncBaseClient instance to delegate requests to
        :param default_space_id: Optional default space ID for all operations
        :param validate_spaces: Whether to validate space existence (default: True)
        """
        self._client = client
        self._default_space_id = default_space_id
        self._validate_spaces = validate_spaces
        self._space_cache: dict[str, bool] = {}  # Cache for space existence
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._cache_timestamps: dict[str, float] = {}

    def _build_space_path(self, base_path: str, space_id: str | None = None) -> str:
        """
        Build space-scoped API path with validation.

        Optimized for performance:
        - Fast path for non-space-scoped operations (zero overhead)
        - Format validation only for space-scoped operations

        Note: For async clients, space existence validation must be done
        separately in async methods that call this function.

        :param base_path: Base API path (e.g., "/api/actions/connector")
        :param space_id: Optional space ID to scope the operation to
        :return: Space-scoped path or original path if no space
        :raises InvalidSpaceIdError: If space ID format is invalid
        """
        effective_space_id = (
            space_id if space_id is not None else self._default_space_id
        )

        # Fast path for non-space-scoped operations - zero overhead
        if not effective_space_id:
            return base_path

        # Space-scoped path - validate format first (fast)
        self._validate_space_id_format(effective_space_id)

        return f"/s/{effective_space_id}{base_path}"

    def _validate_space_id_format(self, space_id: str) -> None:
        """
        Validate space ID format and raise exception if invalid.

        Space IDs must be lowercase, alphanumeric, hyphens, and underscores only.

        :param space_id: Space ID to validate
        :raises InvalidSpaceIdError: If space ID format is invalid
        """
        if not isinstance(space_id, str) or not space_id.strip():
            raise InvalidSpaceIdError(space_id)

        # Space IDs must be lowercase, alphanumeric, hyphens, underscores
        if not re.match(r"^[a-z0-9_-]+$", space_id):
            raise InvalidSpaceIdError(space_id)

    async def _maybe_validate_space(
        self,
        space_id: str | None = None,
        validate_space: bool | None = None,
    ) -> None:
        """Validate space existence if validation is enabled.

        Consolidates the repeated validation pattern used by async client methods.

        :param space_id: Explicit space ID (falls back to default_space_id)
        :param validate_space: Override for validation flag (falls back to instance setting)
        """
        should_validate = (
            validate_space if validate_space is not None else self._validate_spaces
        )
        if should_validate and (space_id or self._default_space_id):
            effective_space_id = (
                space_id if space_id is not None else self._default_space_id
            )
            if effective_space_id:
                await self._validate_space_exists(effective_space_id)

    async def _validate_space_exists(self, space_id: str) -> None:
        """
        Validate that a space exists, using cache when possible.

        Optimized for performance:
        - Fast cache lookup with minimal overhead
        - Efficient timestamp comparison
        - Early returns to minimize execution path

        :param space_id: Space ID to validate
        :raises SpaceNotFoundError: If space doesn't exist
        """
        # Fast cache lookup - check existence first to avoid timestamp lookup if not cached
        if space_id in self._space_cache:
            # Only get timestamp if space is in cache
            cache_time = self._cache_timestamps.get(space_id, 0)
            if time.time() - cache_time < self._cache_ttl:
                if self._space_cache[space_id]:
                    return  # Space exists and cache is valid - fast path
                else:
                    raise SpaceNotFoundError(space_id)

        # Cache miss or expired - validate with API
        current_time = time.time()
        try:
            # Use the spaces client to check if space exists
            spaces_client = getattr(self._client, "spaces", None)
            if not spaces_client:
                return  # No spaces client available, skip validation

            await spaces_client.get(id=space_id)
            # Space exists - cache the result
            self._space_cache[space_id] = True
            self._cache_timestamps[space_id] = current_time
        except NotFoundError:
            # The space genuinely does not exist (404): cache the negative result
            # so repeated calls fast-path, and surface it as SpaceNotFoundError.
            # Any OTHER error (auth, network, serialization) propagates WITHOUT
            # negatively caching -- a transient failure must not pin the space as
            # "missing" for the cache TTL.
            self._space_cache[space_id] = False
            self._cache_timestamps[space_id] = current_time
            raise SpaceNotFoundError(space_id) from None

    def _clear_space_cache(self, space_id: str | None = None) -> None:
        """
        Clear space cache for specific space or all spaces.

        :param space_id: Optional specific space ID to clear from cache.
                        If None, clears entire cache.
        """
        if space_id:
            self._space_cache.pop(space_id, None)
            self._cache_timestamps.pop(space_id, None)
        else:
            self._space_cache.clear()
            self._cache_timestamps.clear()

    async def perform_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Perform an async HTTP request via the parent client with space context enhancement.

        :param method: HTTP method (GET, POST, PUT, DELETE, etc.)
        :param path: API endpoint path
        :param params: Query parameters
        :param headers: Request headers
        :param body: Request body
        :return: API response
        :raises ApiError: If the API returns an error response (enhanced with space context)
        """
        try:
            return await self._client.perform_request(
                method=method,
                path=path,
                params=params,
                headers=headers,
                body=body,
            )
        except Exception as e:
            # Enhance error with space context if this is a space-scoped request
            enhanced_error = self._enhance_error_with_space_context(e, path)
            raise enhanced_error

    def _enhance_error_with_space_context(
        self, error: Exception, path: str
    ) -> Exception:
        """
        Add space context to error messages for debugging.

        :param error: Original exception
        :param path: API path that was requested
        :return: Enhanced exception with space context
        """
        # Extract space ID from path if it's space-scoped
        space_id = self._extract_space_id_from_path(path)

        if space_id and hasattr(error, "message"):
            # Enhance the error message with space context
            original_message = error.message
            error.message = f"[Space: {space_id}] {original_message}"

            # Also add space context to the string representation
            error.args = (f"[Space: {space_id}] {error.args[0]}",) + error.args[1:]

        return error

    def _extract_space_id_from_path(self, path: str) -> str | None:
        """
        Extract space ID from a space-scoped API path.

        :param path: API path (e.g., "/s/marketing/api/actions/connector")
        :return: Space ID if path is space-scoped, None otherwise
        """
        # Match space-scoped paths like "/s/{space_id}/api/..."
        match = re.match(r"^/s/([^/]+)/", path)
        return match.group(1) if match else None


# Import utility functions from sync version
from kibana._sync.client.utils import _quote  # noqa: F401

__all__ = [
    "AsyncNamespaceClient",
    "_quote",
]
