"""Utility functions for the Kibana client."""

import functools
import warnings
from typing import Any


def warn_deprecated(
    message: str,
    *,
    category: type[Warning] = DeprecationWarning,
    stacklevel: int = 2,
) -> None:
    """
    Issue a deprecation warning.

    :param message: Warning message
    :param category: Warning category (default: DeprecationWarning)
    :param stacklevel: Stack level for warning (default: 2)
    """
    warnings.warn(message, category=category, stacklevel=stacklevel)


def deprecated(
    message: str,
    *,
    version: str | None = None,
    alternative: str | None = None,
) -> Any:
    """
    Decorator to mark functions or methods as deprecated.

    :param message: Deprecation message
    :param version: Version when the feature was deprecated
    :param alternative: Suggested alternative to use
    :return: Decorator function

    Example:
        @deprecated("This method is deprecated", version="1.0.0", alternative="new_method()")
        def old_method():
            pass
    """

    def decorator(func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build deprecation message
            full_message = f"{func.__name__} is deprecated"
            if version:
                full_message += f" since version {version}"
            full_message += f": {message}"
            if alternative:
                full_message += f". Use {alternative} instead"

            warn_deprecated(full_message, stacklevel=3)
            return func(*args, **kwargs)

        return wrapper

    return decorator
