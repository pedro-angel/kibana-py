"""Unit tests for exception hierarchy."""

from elastic_transport import ApiResponseMeta


def test_kibana_exception_is_base_exception():
    """Test that KibanaException is the base exception class."""
    from kibana.exceptions import KibanaException

    exc = KibanaException("test message")
    assert isinstance(exc, Exception)
    assert str(exc) == "test message"


def test_api_error_with_meta_and_body():
    """Test ApiError stores meta, body, and status_code attributes."""
    from kibana.exceptions import ApiError

    meta = ApiResponseMeta(
        status=404,
        http_version="1.1",
        headers={},
        duration=0.1,
        node=None,
    )
    body = {"error": "Not found", "message": "Resource not found"}

    exc = ApiError("Resource not found", meta=meta, body=body)

    assert exc.message == "Resource not found"
    assert exc.meta == meta
    assert exc.body == body
    assert exc.status_code == 404
    # str() surfaces the HTTP status alongside the message
    assert str(exc) == "[404] Resource not found"


def test_transport_error_inheritance():
    """Test TransportError inherits from KibanaException."""
    from kibana.exceptions import KibanaException, TransportError

    exc = TransportError("transport failed")
    assert isinstance(exc, KibanaException)
    assert str(exc) == "transport failed"


def test_connection_error_inheritance():
    """Test ConnectionError inherits from TransportError."""
    from kibana.exceptions import ConnectionError, TransportError

    exc = ConnectionError("connection failed")
    assert isinstance(exc, TransportError)
    assert str(exc) == "connection failed"


def test_connection_timeout_inheritance():
    """Test ConnectionTimeout inherits from ConnectionError."""
    from kibana.exceptions import ConnectionError, ConnectionTimeout

    exc = ConnectionTimeout("connection timed out")
    assert isinstance(exc, ConnectionError)
    assert str(exc) == "connection timed out"


def test_ssl_error_inheritance():
    """Test SSLError inherits from ConnectionError."""
    from kibana.exceptions import ConnectionError, SSLError

    exc = SSLError("SSL verification failed")
    assert isinstance(exc, ConnectionError)
    assert str(exc) == "SSL verification failed"


def test_authentication_exception_is_401():
    """Test AuthenticationException is for 401 status."""
    from kibana.exceptions import ApiError, AuthenticationException

    meta = ApiResponseMeta(
        status=401,
        http_version="1.1",
        headers={},
        duration=0.1,
        node=None,
    )

    exc = AuthenticationException("Unauthorized", meta=meta, body={})
    assert isinstance(exc, ApiError)
    assert exc.status_code == 401


def test_authorization_exception_is_403():
    """Test AuthorizationException is for 403 status."""
    from kibana.exceptions import ApiError, AuthorizationException

    meta = ApiResponseMeta(
        status=403,
        http_version="1.1",
        headers={},
        duration=0.1,
        node=None,
    )

    exc = AuthorizationException("Forbidden", meta=meta, body={})
    assert isinstance(exc, ApiError)
    assert exc.status_code == 403


def test_not_found_error_is_404():
    """Test NotFoundError is for 404 status."""
    from kibana.exceptions import ApiError, NotFoundError

    meta = ApiResponseMeta(
        status=404,
        http_version="1.1",
        headers={},
        duration=0.1,
        node=None,
    )

    exc = NotFoundError("Not found", meta=meta, body={})
    assert isinstance(exc, ApiError)
    assert exc.status_code == 404


def test_conflict_error_is_409():
    """Test ConflictError is for 409 status."""
    from kibana.exceptions import ApiError, ConflictError

    meta = ApiResponseMeta(
        status=409,
        http_version="1.1",
        headers={},
        duration=0.1,
        node=None,
    )

    exc = ConflictError("Conflict", meta=meta, body={})
    assert isinstance(exc, ApiError)
    assert exc.status_code == 409


def test_bad_request_error_is_400():
    """Test BadRequestError is for 400 status."""
    from kibana.exceptions import ApiError, BadRequestError

    meta = ApiResponseMeta(
        status=400,
        http_version="1.1",
        headers={},
        duration=0.1,
        node=None,
    )

    exc = BadRequestError("Bad request", meta=meta, body={})
    assert isinstance(exc, ApiError)
    assert exc.status_code == 400


def test_serialization_error_inheritance():
    """Test SerializationError inherits from KibanaException."""
    from kibana.exceptions import KibanaException, SerializationError

    exc = SerializationError("Failed to serialize data")
    assert isinstance(exc, KibanaException)
    assert str(exc) == "Failed to serialize data"


def test_http_exceptions_mapping():
    """Test HTTP_EXCEPTIONS maps status codes to exception classes."""
    from kibana.exceptions import (
        HTTP_EXCEPTIONS,
        AuthenticationException,
        AuthorizationException,
        BadRequestError,
        ConflictError,
        NotFoundError,
    )

    assert HTTP_EXCEPTIONS[400] == BadRequestError
    assert HTTP_EXCEPTIONS[401] == AuthenticationException
    assert HTTP_EXCEPTIONS[403] == AuthorizationException
    assert HTTP_EXCEPTIONS[404] == NotFoundError
    assert HTTP_EXCEPTIONS[409] == ConflictError


def test_http_exceptions_mapping_completeness():
    """Test HTTP_EXCEPTIONS contains all expected status codes."""
    from kibana.exceptions import HTTP_EXCEPTIONS

    expected_codes = [400, 401, 403, 404, 409]
    for code in expected_codes:
        assert (
            code in HTTP_EXCEPTIONS
        ), f"Status code {code} missing from HTTP_EXCEPTIONS"


def test_space_error_inheritance():
    """Test that SpaceError inherits from KibanaException."""
    from kibana.exceptions import KibanaException, SpaceError

    error = SpaceError("Test space error")
    assert isinstance(error, KibanaException)
    assert isinstance(error, Exception)
    assert str(error) == "Test space error"


def test_space_not_found_error():
    """Test SpaceNotFoundError functionality."""
    from kibana.exceptions import KibanaException, SpaceError, SpaceNotFoundError

    error = SpaceNotFoundError("marketing")

    # Test inheritance
    assert isinstance(error, SpaceError)
    assert isinstance(error, KibanaException)
    assert isinstance(error, Exception)

    # Test attributes
    assert error.space_id == "marketing"
    assert str(error) == "Space not found: marketing"


def test_invalid_space_id_error():
    """Test InvalidSpaceIdError functionality."""
    from kibana.exceptions import InvalidSpaceIdError, KibanaException, SpaceError

    error = InvalidSpaceIdError("Invalid Space")

    # Test inheritance
    assert isinstance(error, SpaceError)
    assert isinstance(error, KibanaException)
    assert isinstance(error, Exception)

    # Test attributes
    assert error.space_id == "Invalid Space"
    assert str(error) == "Invalid space ID format: Invalid Space"


def test_space_exceptions_importable_from_main_module():
    """Test that space exceptions can be imported from main kibana module."""
    from kibana import InvalidSpaceIdError, SpaceError, SpaceNotFoundError

    # Test that they are the same classes
    from kibana.exceptions import InvalidSpaceIdError as DirectInvalidSpaceIdError
    from kibana.exceptions import SpaceError as DirectSpaceError
    from kibana.exceptions import SpaceNotFoundError as DirectSpaceNotFoundError

    assert SpaceError is DirectSpaceError
    assert SpaceNotFoundError is DirectSpaceNotFoundError
    assert InvalidSpaceIdError is DirectInvalidSpaceIdError
