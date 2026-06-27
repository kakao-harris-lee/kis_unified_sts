"""API Key authentication middleware."""
import asyncio
import hmac
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/",
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class APIKeyMiddleware:
    """Middleware for API key authentication.

    Supports both HTTP and WebSocket protocols.
    - HTTP: API key via X-API-Key header
    - WebSocket: API key via query parameter ?api_key=xxx
    """

    def __init__(self, app: ASGIApp, api_key: str, header_name: str = "X-API-Key"):
        self.app = app
        self.api_key = api_key
        self.header_name = header_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle incoming connections."""
        if scope["type"] == "http":
            await self._handle_http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self._handle_websocket(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle HTTP requests with API key validation."""
        request = Request(scope)
        path = request.url.path

        # Skip auth for public paths
        if self._is_public_path(path):
            await self.app(scope, receive, send)
            return

        # Check API key
        api_key = request.headers.get(self.header_name)

        if not self._validate_api_key(api_key):
            response = JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    async def _handle_websocket(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle WebSocket connections with API key validation.

        WebSocket auth is done via query parameter since headers
        are not always available for WebSocket upgrades.
        """
        # Parse query params from scope (Request doesn't work for WebSocket)
        query_string = scope.get("query_string", b"").decode()
        api_key = self._parse_query_param(query_string, "api_key")

        if not self._validate_api_key(api_key):
            # Fail closed. In some servers/test clients, awaiting receive() can hang
            # because the connect event may already be consumed or not delivered.
            # We attempt a best-effort receive with a short timeout to avoid deadlock.
            try:
                await asyncio.wait_for(receive(), timeout=0.2)
            except (TimeoutError, OSError, RuntimeError):
                # Timeout or connection errors are expected during WebSocket close
                pass

            await send({"type": "websocket.close", "code": 4001, "reason": "Unauthorized"})
            return

        await self.app(scope, receive, send)

    def _parse_query_param(self, query_string: str, param_name: str) -> str | None:
        """Parse a specific query parameter from query string."""
        from urllib.parse import parse_qs
        params = parse_qs(query_string)
        values = params.get(param_name)
        return values[0] if values else None

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        if path in PUBLIC_PATHS:
            return True
        return bool(path.startswith("/docs") or path.startswith("/redoc"))

    def _validate_api_key(self, api_key: str | None) -> bool:
        """Validate API key using timing-safe comparison.

        Uses hmac.compare_digest to prevent timing attacks.
        """
        if not api_key or not self.api_key:
            return False
        # Timing-safe comparison to prevent timing attacks
        return hmac.compare_digest(api_key.encode(), self.api_key.encode())
