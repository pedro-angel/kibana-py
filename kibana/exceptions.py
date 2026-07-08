"""Exception classes for Kibana client.

This module defines the exception hierarchy for the Kibana Python client.
All exceptions inherit from KibanaException, with specific exception types
for different error scenarios.

Exception Hierarchy:
    KibanaException (base)
    ├── ApiError (HTTP API errors)
    │   ├── BadRequestError (400)
    │   ├── AuthenticationException (401)
    │   ├── AuthorizationException (403)
    │   ├── NotFoundError (404)
    │   └── ConflictError (409)
    ├── TransportError (connection errors)
    │   ├── ConnectionError
    │   │   ├── ConnectionTimeout
    │   │   └── SSLError
    ├── SerializationError (JSON serialization errors)
    └── SpaceError (space-related errors)
        ├── SpaceNotFoundError
        └── InvalidSpaceIdError
"""

from typing import Any

from elastic_transport import ApiResponseMeta


class KibanaException(Exception):
    """Base exception for all Kibana client errors.

    All exceptions raised by the Kibana client inherit from this class,
    making it easy to catch all Kibana-related errors.

    Example:
        >>> from kibana import Kibana
        >>> from kibana.exceptions import KibanaException
        >>>
        >>> client = Kibana("http://localhost:5601")
        >>> try:
        ...     client.actions.get(id="nonexistent")
        ... except KibanaException as e:
        ...     print(f"Kibana error: {e}")
    """

    pass


class ApiError(KibanaException):
    """API returned an error response.

    Raised when the Kibana API returns an HTTP error status code (4xx or 5xx).
    Contains the error message, response metadata, and full response body for
    debugging.

    Attributes:
        message: Human-readable error message extracted from the response.
        meta: API response metadata including status code, headers, and timing.
        body: Full response body from the API (may contain additional error details).
        status_code: HTTP status code of the error response.

    Example:
        >>> try:
        ...     client.actions.create(name="", connector_type_id=".webhook", config={})
        ... except ApiError as e:
        ...     print(f"API Error: {e.message}")
        ...     print(f"Status Code: {e.status_code}")
        ...     print(f"Response Body: {e.body}")
    """

    def __init__(
        self,
        message: str,
        meta: ApiResponseMeta,
        body: Any,
    ) -> None:
        """Initialize ApiError with error details.

        Args:
            message: Human-readable error message.
            meta: API response metadata from elastic-transport.
            body: Full response body from the API.
        """
        super().__init__(message)
        self.message = message
        self.meta = meta
        self.body = body
        self.status_code = meta.status

    def __str__(self) -> str:
        """Format as ``[<status>] <message>`` so the HTTP status is always visible."""
        return f"[{self.status_code}] {self.message}"


class TransportError(KibanaException):
    """Transport-level error.

    Raised when there's a problem with the HTTP transport layer, such as
    connection failures, timeouts, or SSL errors.

    Example:
        >>> try:
        ...     client = Kibana("http://invalid-host:5601")
        ...     client.status.get_status()
        ... except TransportError as e:
        ...     print(f"Connection error: {e}")
    """

    pass


class ConnectionError(TransportError):
    """Failed to connect to Kibana.

    Raised when the client cannot establish a connection to the Kibana server.
    This may indicate that Kibana is down, the URL is incorrect, or there are
    network connectivity issues.

    Example:
        >>> try:
        ...     client = Kibana("http://localhost:9999")  # Wrong port
        ...     client.status.get_status()
        ... except ConnectionError as e:
        ...     print(f"Cannot connect to Kibana: {e}")
    """

    pass


class ConnectionTimeout(ConnectionError):
    """Connection timed out.

    Raised when a connection attempt or request exceeds the configured timeout.
    This may indicate network issues or an overloaded Kibana server.

    Example:
        >>> client = Kibana("http://localhost:5601", request_timeout=1.0)
        >>> try:
        ...     client.actions.get_all()  # Slow operation
        ... except ConnectionTimeout as e:
        ...     print(f"Request timed out: {e}")
    """

    pass


class SSLError(ConnectionError):
    """SSL/TLS error.

    Raised when there's a problem with SSL/TLS certificate verification or
    the secure connection setup.

    Example:
        >>> try:
        ...     client = Kibana("https://localhost:5601")  # Self-signed cert
        ...     client.status.get_status()
        ... except SSLError as e:
        ...     print(f"SSL error: {e}")
    """

    pass


class AuthenticationException(ApiError):
    """Authentication failed (401).

    Raised when the provided credentials are invalid or missing. This indicates
    that the API key, basic auth credentials, or bearer token is incorrect or
    has expired.

    Example:
        >>> client = Kibana("http://localhost:5601", api_key="invalid")
        >>> try:
        ...     client.status.get_status()
        ... except AuthenticationException as e:
        ...     print(f"Authentication failed: {e.message}")
        ...     print("Please check your API key or credentials")
    """

    pass


class AuthorizationException(ApiError):
    """Authorization failed (403).

    Raised when the authenticated user does not have sufficient privileges to
    perform the requested operation. The credentials are valid, but the user
    lacks the necessary permissions.

    Example:
        >>> try:
        ...     client.spaces.delete(id="default")  # Cannot delete default space
        ... except AuthorizationException as e:
        ...     print(f"Permission denied: {e.message}")
        ...     print("User lacks required privileges")
    """

    pass


class NotFoundError(ApiError):
    """Resource not found (404).

    Raised when the requested resource (connector, space, saved object, etc.)
    does not exist.

    Example:
        >>> try:
        ...     client.actions.get(id="nonexistent-connector")
        ... except NotFoundError as e:
        ...     print(f"Resource not found: {e.message}")
        ...     print("The connector may have been deleted")
    """

    pass


class ConflictError(ApiError):
    """Conflict error (409).

    Raised when the operation conflicts with the current state of the resource.
    Common causes include:
    - Creating a resource with an ID that already exists
    - Updating a resource with an outdated version
    - Deleting a resource that has dependencies

    Example:
        >>> try:
        ...     client.spaces.create(id="marketing", name="Marketing")
        ...     client.spaces.create(id="marketing", name="Marketing 2")  # Duplicate
        ... except ConflictError as e:
        ...     print(f"Conflict: {e.message}")
        ...     print("A space with this ID already exists")
    """

    pass


class BadRequestError(ApiError):
    """Bad request (400).

    Raised when the request is malformed or contains invalid parameters.
    This indicates a problem with the request data, such as:
    - Missing required parameters
    - Invalid parameter values
    - Malformed JSON
    - Invalid configuration

    Example:
        >>> try:
        ...     client.actions.create(
        ...         name="",  # Empty name
        ...         connector_type_id=".webhook",
        ...         config={}
        ...     )
        ... except BadRequestError as e:
        ...     print(f"Invalid request: {e.message}")
        ...     print("Check the request parameters")
    """

    pass


class SerializationError(KibanaException):
    """Failed to serialize/deserialize data.

    Raised when there's a problem converting data to/from JSON format.
    This may indicate incompatible data types or corrupted data.

    Example:
        >>> try:
        ...     # Attempting to serialize non-serializable object
        ...     client.actions.create(
        ...         name="Test",
        ...         connector_type_id=".webhook",
        ...         config={"callback": lambda x: x}  # Functions can't be serialized
        ...     )
        ... except SerializationError as e:
        ...     print(f"Serialization error: {e}")
    """

    pass


class SpaceError(KibanaException):
    """Base exception for space-related errors.

    Parent class for all space-specific errors. Use this to catch any
    space-related exception.

    Example:
        >>> try:
        ...     client.space("invalid space id!")
        ... except SpaceError as e:
        ...     print(f"Space error: {e}")
    """

    pass


class SpaceNotFoundError(SpaceError):
    """Raised when a specified space does not exist.

    This exception is raised when attempting to perform operations in a space
    that doesn't exist. The space may have been deleted or the ID may be incorrect.

    Attributes:
        space_id: The ID of the space that was not found.

    Example:
        >>> try:
        ...     client.actions.create(
        ...         name="Test",
        ...         connector_type_id=".webhook",
        ...         config={},
        ...         space_id="nonexistent"
        ...     )
        ... except SpaceNotFoundError as e:
        ...     print(f"Space '{e.space_id}' not found")
        ...     print("Please create the space first or check the space ID")
    """

    def __init__(self, space_id: str):
        """Initialize SpaceNotFoundError.

        Args:
            space_id: The ID of the space that was not found.
        """
        self.space_id = space_id
        super().__init__(f"Space not found: {space_id}")


class InvalidSpaceIdError(SpaceError):
    """Raised when a space ID format is invalid.

    Space IDs must be URL-friendly (lowercase, alphanumeric, hyphens, underscores).
    This exception is raised when a space ID contains invalid characters or format.

    Attributes:
        space_id: The invalid space ID that was provided.

    Example:
        >>> try:
        ...     client.spaces.create(
        ...         id="Invalid Space!",  # Contains spaces and special chars
        ...         name="Test Space"
        ...     )
        ... except InvalidSpaceIdError as e:
        ...     print(f"Invalid space ID: {e.space_id}")
        ...     print("Space IDs must be lowercase and URL-friendly")
    """

    def __init__(self, space_id: str):
        """Initialize InvalidSpaceIdError.

        Args:
            space_id: The invalid space ID that was provided.
        """
        self.space_id = space_id
        super().__init__(f"Invalid space ID format: {space_id}")


# Mapping of HTTP status codes to exception classes
HTTP_EXCEPTIONS: dict[int, type[ApiError]] = {
    400: BadRequestError,
    401: AuthenticationException,
    403: AuthorizationException,
    404: NotFoundError,
    409: ConflictError,
}
