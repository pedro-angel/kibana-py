"""Utility classes and functions for Kibana client namespace implementations."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from elastic_transport import ObjectApiResponse

from kibana._space_cache import SpaceValidationCache, shared_space_cache
from kibana._sync.client._base import BaseClient
from kibana.exceptions import InvalidSpaceIdError, NotFoundError, SpaceNotFoundError

# Space IDs must be lowercase alphanumerics, hyphens and underscores.
# Applied with fullmatch(), never match() + "$": "$" also matches *before* a
# trailing newline, so "marketing\n" would pass the check, be pasted into the
# path, and cost a real GET /api/spaces/space/marketing%0A that comes back as
# SpaceNotFoundError -- exactly the failure #74 exists to prevent.
_SPACE_ID_RE = re.compile(r"[a-z0-9_-]+")


def _check_space_id_format(space_id: str) -> None:
    """Reject a space ID that could not name a space, without asking the server.

    Internal (like every other ``_``-prefixed helper here): it is the single
    source of the rule, not new public API. The namespace clients of both trees
    reach it through ``_validate_space_id_format``; ``SpaceScopedKibana`` /
    ``AsyncSpaceScopedKibana`` call it directly, since they are not namespace
    clients. Purely local -- no request, no cache read or write -- which is what
    lets every caller run it *first*.

    :param space_id: Space ID to validate
    :raises InvalidSpaceIdError: If space ID format is invalid
    """
    if not isinstance(space_id, str) or not space_id.strip():
        raise InvalidSpaceIdError(space_id)

    if not _SPACE_ID_RE.fullmatch(space_id):
        raise InvalidSpaceIdError(space_id)


class NamespaceClient:
    """
    Base class for all namespace clients (saved_objects, spaces, actions, etc.).

    Provides common functionality for making requests through the parent client,
    space support with validation and caching, and utility functions for
    parameter handling and URL encoding.
    """

    def __init__(
        self,
        client: BaseClient,
        default_space_id: str | None = None,
        validate_spaces: bool = True,
    ) -> None:
        """
        Initialize NamespaceClient with optional space support.

        :param client: Parent BaseClient instance to delegate requests to
        :param default_space_id: Optional default space ID for all operations
        :param validate_spaces: Whether to validate space existence (default: True)
        """
        self._client = client
        self._default_space_id = default_space_id
        self._validate_spaces = validate_spaces

    @property
    def _space_validation_cache(self) -> SpaceValidationCache:
        """The parent client's space cache -- borrowed, never owned.

        Resolved per use rather than captured at construction, so a namespace
        client always follows its parent's *current* cache (``options()`` hands
        a clone the original's cache after the clone has wired its namespaces).
        """
        return shared_space_cache(self._client)

    @property
    def _space_cache(self) -> dict[str, bool]:
        """Live view of the shared cache's space-existence verdicts."""
        return self._space_validation_cache.entries

    @property
    def _cache_timestamps(self) -> dict[str, float]:
        """Live view of the shared cache's verdict timestamps (monotonic)."""
        return self._space_validation_cache.timestamps

    @property
    def _cache_ttl(self) -> float:
        """Seconds a cached verdict stays valid (shared with all namespaces)."""
        return self._space_validation_cache.ttl

    @_cache_ttl.setter
    def _cache_ttl(self, value: float) -> None:
        self._space_validation_cache.ttl = value

    def _build_space_path(
        self,
        base_path: str,
        space_id: str | None = None,
        validate_spaces: bool | None = None,
    ) -> str:
        """
        Build space-scoped API path with validation.

        Optimized for performance:
        - Fast path for non-space-scoped operations (zero overhead)
        - Minimal validation overhead for space-scoped operations

        :param base_path: Base API path (e.g., "/api/actions/connector")
        :param space_id: Optional space ID to scope the operation to
        :param validate_spaces: Override for validation flag. If ``None``,
            falls back to the instance-level ``_validate_spaces`` setting.
        :return: Space-scoped path or original path if no space
        :raises InvalidSpaceIdError: If space ID format is invalid
        :raises SpaceNotFoundError: If space doesn't exist and validation is enabled
        """
        effective_space_id = (
            space_id if space_id is not None else self._default_space_id
        )

        # Fast path for non-space-scoped operations - zero overhead
        if not effective_space_id:
            return base_path

        # Space-scoped path - validate format first (fast)
        self._validate_space_id_format(effective_space_id)

        # Validate space exists if validation is enabled
        should_validate = (
            validate_spaces if validate_spaces is not None else self._validate_spaces
        )
        if should_validate:
            self._validate_space_exists(effective_space_id)

        return f"/s/{effective_space_id}{base_path}"

    def _validate_space_id_format(self, space_id: str) -> None:
        """
        Validate space ID format and raise exception if invalid.

        Space IDs must be lowercase, alphanumeric, hyphens, and underscores only.

        :param space_id: Space ID to validate
        :raises InvalidSpaceIdError: If space ID format is invalid
        """
        _check_space_id_format(space_id)

    def _validate_space_exists(self, space_id: str) -> None:
        """
        Validate that a space exists, using the shared cache when possible.

        Optimized for performance:
        - Fast cache lookup with minimal overhead
        - Early returns to minimize execution path

        :param space_id: Space ID to validate
        :raises SpaceNotFoundError: If space doesn't exist
        """
        # Fast path: a live verdict from the client-wide cache, whichever
        # namespace (or space-scoped client) first paid for the lookup.
        cache = self._space_validation_cache
        cached = cache.lookup(space_id)
        if cached is not None:
            if cached:
                return  # Space exists and cache is valid - fast path
            raise SpaceNotFoundError(space_id)

        # Cache miss or expired - validate with API. Snapshot the generation
        # BEFORE asking: if an invalidation (a spaces.create/delete, say) lands
        # while this lookup is in flight, our answer is older than it and must
        # not overwrite it.
        generation = cache.generation
        try:
            spaces_client = getattr(self._client, "spaces", None)
            if not spaces_client:
                return  # No spaces client available, skip validation

            spaces_client.get(id=space_id)
            # Space exists - cache the result
            cache.remember(space_id, True, generation=generation)
        except NotFoundError:
            # The space genuinely does not exist (404): cache the negative result
            # so repeated calls fast-path, and surface it as SpaceNotFoundError.
            # Any OTHER error (auth, network, serialization) propagates WITHOUT
            # negatively caching -- a transient failure must not pin the space as
            # "missing" for the cache TTL.
            cache.remember(space_id, False, generation=generation)
            raise SpaceNotFoundError(space_id) from None

    def _clear_space_cache(self, space_id: str | None = None) -> None:
        """
        Clear the shared space cache for a specific space or all spaces.

        Affects every namespace client of this Kibana client, since they all
        share one cache.

        :param space_id: Optional specific space ID to clear from cache.
                        If None, clears entire cache.
        """
        self._space_validation_cache.invalidate(space_id)

    def perform_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> ObjectApiResponse[Any]:
        """
        Perform an HTTP request via the parent client with space context enhancement.

        :param method: HTTP method (GET, POST, PUT, DELETE, etc.)
        :param path: API endpoint path
        :param params: Query parameters
        :param headers: Request headers
        :param body: Request body
        :return: API response
        :raises ApiError: If the API returns an error response (enhanced with space context)
        """
        try:
            return self._client.perform_request(
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


def _quote(value: str, safe: str = "") -> str:
    """
    URL encode a string value for use in URL paths.

    This is a wrapper around urllib.parse.quote that provides consistent
    URL encoding behavior across all namespace clients.

    :param value: String value to encode
    :param safe: Characters that should not be encoded (default: empty string)
    :return: URL-encoded string

    Examples:
        >>> _quote("my dashboard")
        'my%20dashboard'
        >>> _quote("user@example.com")
        'user%40example.com'
        >>> _quote("path/to/resource", safe="/")
        'path/to/resource'
    """
    return quote(str(value), safe=safe)
