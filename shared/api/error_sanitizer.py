"""Error message sanitization for API responses.

Provides utilities to sanitize exception messages before exposing them
through API endpoints, preventing information leakage about internal
implementation details.

Features:
- Removes file paths and directory structures
- Strips module paths from exception types
- Sanitizes database connection strings
- Removes SQL query details
- Filters stack trace information
- Provides generic error categories

Usage:
    from shared.api.error_sanitizer import sanitize_error_message

    try:
        risky_operation()
    except Exception as e:
        safe_message = sanitize_error_message(e)
        return {"error": safe_message}
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# Common error categories for generic messaging
ERROR_CATEGORIES = {
    "ValueError": "Invalid input value",
    "TypeError": "Invalid data type",
    "KeyError": "Missing required field",
    "AttributeError": "Invalid operation",
    "FileNotFoundError": "Resource not found",
    "PermissionError": "Access denied",
    "ConnectionError": "Connection failed",
    "TimeoutError": "Request timeout",
    "RuntimeError": "Operation failed",
    "ImportError": "Configuration error",
    "ModuleNotFoundError": "Configuration error",
    "IndexError": "Invalid index",
    "ZeroDivisionError": "Invalid calculation",
    "NotImplementedError": "Operation not supported",
    "IOError": "Input/output error",
    "OSError": "System error",
}

# Patterns to remove from error messages
SENSITIVE_PATTERNS = [
    # File paths (Unix and Windows)
    (r'/[\w/.+-]+\.(py|yaml|yml|json|txt|conf|cfg|ini)', 'FILE'),
    (r'C:\\[\w\\/.+-]+\.(py|yaml|yml|json|txt|conf|cfg|ini)', 'FILE'),
    (r'/[\w/.+-]+/', 'PATH/'),
    (r'C:\\[\w\\/.+-]+\\', 'PATH\\'),

    # Database connection strings
    (r'(postgresql|mysql|redis|mongodb)://[^\s]+', 'DB_CONNECTION'),
    (r'(host|server|database|db)=[^\s;,)]+', 'DB_PARAM'),

    # SQL queries
    (r'SELECT\s+.+?\s+FROM\s+[\w.]+', 'SQL_QUERY'),
    (r'INSERT\s+INTO\s+[\w.]+', 'SQL_QUERY'),
    (r'UPDATE\s+[\w.]+\s+SET', 'SQL_QUERY'),
    (r'DELETE\s+FROM\s+[\w.]+', 'SQL_QUERY'),

    # IP addresses and ports
    (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?\b', 'HOST'),

    # Module paths in tracebacks
    (r'File "([^"]+)"', 'File "..."'),
    (r'line \d+', 'line N'),

    # API keys and tokens (basic patterns)
    (r'(api[_-]?key|token|secret|password)[\s:=]+[\w-]{16,}', 'CREDENTIAL'),

    # Python object references
    (r'<[\w.]+\sobject\sat\s0x[0-9a-fA-F]+>', 'OBJECT'),

    # Function signatures with full paths
    (r'[\w.]+\.[\w.]+\(.*?\)', 'function()'),
]


def _get_base_exception_type(exc: Exception) -> str:
    """Extract base exception type without module path.

    Args:
        exc: Exception instance

    Returns:
        Simple exception type name (e.g., "ValueError" instead of "builtins.ValueError")
    """
    exc_type = type(exc).__name__
    # Remove any module path prefixes
    return exc_type.split('.')[-1]


def _sanitize_message(message: str) -> str:
    """Remove sensitive patterns from error message.

    Args:
        message: Original error message

    Returns:
        Sanitized message with sensitive info removed
    """
    sanitized = message

    for pattern, replacement in SENSITIVE_PATTERNS:
        try:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        except re.error as e:
            logger.warning(f"Failed to apply sanitization pattern: {e}")
            continue

    return sanitized


def _get_generic_message(exc: Exception) -> str:
    """Get a generic error message based on exception type.

    Args:
        exc: Exception instance

    Returns:
        Generic error message for the exception category
    """
    exc_type = _get_base_exception_type(exc)

    # Check if we have a predefined generic message
    if exc_type in ERROR_CATEGORIES:
        return ERROR_CATEGORIES[exc_type]

    # Check for common base classes
    if isinstance(exc, ValueError):
        return ERROR_CATEGORIES["ValueError"]
    elif isinstance(exc, TypeError):
        return ERROR_CATEGORIES["TypeError"]
    elif isinstance(exc, KeyError):
        return ERROR_CATEGORIES["KeyError"]
    elif isinstance(exc, (ConnectionError, OSError)):
        return ERROR_CATEGORIES["ConnectionError"]
    elif isinstance(exc, TimeoutError):
        return ERROR_CATEGORIES["TimeoutError"]

    # Default generic message
    return "An error occurred while processing your request"


def sanitize_error_message(
    exc: Exception,
    include_type: bool = False,
    use_generic: bool = False,
) -> str:
    """Sanitize an exception for safe exposure through API.

    Removes sensitive information like file paths, database details,
    and internal implementation specifics while preserving enough
    information for debugging purposes.

    Args:
        exc: Exception to sanitize
        include_type: Whether to include exception type in output
        use_generic: If True, return only generic error category message

    Returns:
        Sanitized error message safe for API responses

    Examples:
        >>> exc = ValueError("Invalid config at /etc/app/config.yaml")
        >>> sanitize_error_message(exc)
        'Invalid config at FILE'

        >>> sanitize_error_message(exc, use_generic=True)
        'Invalid input value'

        >>> sanitize_error_message(exc, include_type=True)
        'ValueError: Invalid config at FILE'
    """
    try:
        if use_generic:
            return _get_generic_message(exc)

        # Get the error message
        error_msg = str(exc)

        # If message is empty or too generic, use category-based message
        if not error_msg or error_msg.strip() in ("", "None"):
            return _get_generic_message(exc)

        # Sanitize the message
        sanitized_msg = _sanitize_message(error_msg)

        # Truncate very long messages
        max_length = 200
        if len(sanitized_msg) > max_length:
            sanitized_msg = sanitized_msg[:max_length] + "..."

        # Optionally include exception type
        if include_type:
            exc_type = _get_base_exception_type(exc)
            return f"{exc_type}: {sanitized_msg}"

        return sanitized_msg

    except Exception as e:
        # Failsafe: if sanitization itself fails, return generic message
        logger.error(f"Error during message sanitization: {e}")
        return "An error occurred while processing your request"


def sanitize_error_dict(
    exc: Exception,
    include_type: bool = False,
    use_generic: bool = False,
) -> dict[str, str]:
    """Sanitize exception and return as dictionary for JSON responses.

    Args:
        exc: Exception to sanitize
        include_type: Whether to include exception type separately
        use_generic: If True, return only generic error category message

    Returns:
        Dictionary with sanitized error information

    Examples:
        >>> exc = ValueError("Invalid value")
        >>> sanitize_error_dict(exc, include_type=True)
        {'error': 'Invalid value', 'type': 'ValueError'}
    """
    result = {
        "error": sanitize_error_message(exc, include_type=False, use_generic=use_generic)
    }

    if include_type:
        result["type"] = _get_base_exception_type(exc)

    return result


__all__ = [
    "sanitize_error_message",
    "sanitize_error_dict",
]
