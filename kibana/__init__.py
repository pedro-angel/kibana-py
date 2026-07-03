"""Kibana Python Client."""

import logging

# Set up logging with NullHandler early so it's available during init
logger = logging.getLogger("kibana")
logger.addHandler(logging.NullHandler())

# Import version information
from kibana._version import __versionstr__


# Create version tuple from version string
def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse version string into tuple of integers."""
    try:
        parts = version_str.split(".")
        return tuple(int(part) for part in parts)
    except ValueError, AttributeError:
        return (0, 0, 0)


__version__ = _parse_version(__versionstr__)


# Check elastic-transport compatibility
def _check_transport_compatibility() -> None:
    """Check that elastic-transport version is compatible."""
    try:
        import elastic_transport

        # Get elastic-transport version
        transport_version = getattr(elastic_transport, "__version__", "unknown")

        # Parse version
        if transport_version != "unknown":
            try:
                major, minor = transport_version.split(".")[:2]
                major, minor = int(major), int(minor)

                # Check compatibility: >=9.1.0, <10
                if major < 9 or (major == 9 and minor < 1) or major >= 10:
                    import warnings

                    warnings.warn(
                        f"elastic-transport version {transport_version} may not be compatible. "
                        f"kibana-py requires elastic-transport>=9.1.0,<10",
                        UserWarning,
                        stacklevel=2,
                    )
            except ValueError, IndexError:
                # If we can't parse the version, just log a debug message
                logger.debug(
                    f"Could not parse elastic-transport version: {transport_version}"
                )

    except ImportError:
        # This should not happen since elastic-transport is a required dependency
        import warnings

        warnings.warn(
            "elastic-transport is not installed. kibana-py requires elastic-transport>=9.1.0,<10",
            UserWarning,
            stacklevel=2,
        )


# Perform compatibility check on import
_check_transport_compatibility()

from kibana._async.client import AsyncKibana, AsyncSpaceScopedKibana

# Import main client classes
from kibana._sync.client import Kibana, SpaceScopedKibana

# Import namespace clients
from kibana._sync.client.actions import ActionsClient
from kibana._sync.client.saved_objects import SavedObjectsClient
from kibana._sync.client.spaces import SpacesClient

# Import exceptions
from kibana.exceptions import (
    ApiError,
    AuthenticationException,
    AuthorizationException,
    BadRequestError,
    ConflictError,
    ConnectionError,
    ConnectionTimeout,
    InvalidSpaceIdError,
    KibanaException,
    NotFoundError,
    SerializationError,
    SpaceError,
    SpaceNotFoundError,
    SSLError,
    TransportError,
)

# Import serializers
from kibana.serializer import DEFAULT_SERIALIZERS, JSONSerializer, Serializer

# Try to import optional OrjsonSerializer
try:
    from kibana.serializer import OrjsonSerializer

    __all_serializers__ = [Serializer, JSONSerializer, OrjsonSerializer]
except ImportError:
    __all_serializers__ = [Serializer, JSONSerializer]

# Import utility functions, observability, and structured logging
from kibana._utils import deprecated, warn_deprecated
from kibana.logging import JSONFormatter  # noqa: E402
from kibana.observability import KibanaInstrumentor, configure_opentelemetry

# Public API
__all__ = [
    # Version
    "__version__",
    "__versionstr__",
    # Client
    "Kibana",
    "SpaceScopedKibana",
    "AsyncKibana",
    "AsyncSpaceScopedKibana",
    # Namespace clients
    "ActionsClient",
    "SavedObjectsClient",
    "SpacesClient",
    # Exceptions
    "KibanaException",
    "ApiError",
    "TransportError",
    "ConnectionError",
    "ConnectionTimeout",
    "SSLError",
    "AuthenticationException",
    "AuthorizationException",
    "NotFoundError",
    "ConflictError",
    "BadRequestError",
    "SerializationError",
    "SpaceError",
    "SpaceNotFoundError",
    "InvalidSpaceIdError",
    # Serializers
    "Serializer",
    "JSONSerializer",
    "DEFAULT_SERIALIZERS",
    # Observability
    "configure_opentelemetry",
    "KibanaInstrumentor",
    # Utilities
    "deprecated",
    "warn_deprecated",
    # Logging
    "JSONFormatter",
]

# Add OrjsonSerializer to __all__ if available
if "OrjsonSerializer" in dir():
    __all__.append("OrjsonSerializer")
