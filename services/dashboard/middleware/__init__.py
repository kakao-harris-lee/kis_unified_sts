"""Dashboard middleware modules."""
from services.dashboard.middleware.auth import APIKeyMiddleware

__all__ = ["APIKeyMiddleware"]
