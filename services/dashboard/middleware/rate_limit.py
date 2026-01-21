"""Rate limiting middleware."""
import logging
import time
from collections import defaultdict
from typing import Callable, Dict, List

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware.

    Uses a sliding window algorithm to track requests per client.
    Includes periodic cleanup to prevent memory leaks.

    In production, consider using Redis for distributed rate limiting.
    """

    def __init__(self, app, requests_per_window: int = 100, window_seconds: int = 60):
        """Initialize rate limiter.

        Args:
            app: The FastAPI application.
            requests_per_window: Maximum requests allowed per window.
            window_seconds: The time window in seconds.
        """
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self._request_times: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request.

        Note: X-Forwarded-For can be spoofed. In production, ensure your
        proxy is properly configured and only trust the first hop after
        your load balancer.
        """
        # Use client host directly for security
        # Don't blindly trust X-Forwarded-For as it can be spoofed
        if request.client:
            return request.client.host
        return "unknown"

    def _cleanup_old_entries(self) -> None:
        """Remove expired timestamps from all clients.

        This prevents memory leaks from clients that made requests
        in the past but are no longer active.
        """
        now = time.time()
        cutoff = now - self.window_seconds

        # Get list of keys to avoid modifying dict during iteration
        clients_to_check = list(self._request_times.keys())

        for client_id in clients_to_check:
            # Filter old timestamps
            self._request_times[client_id] = [
                ts for ts in self._request_times[client_id] if ts > cutoff
            ]
            # Remove empty entries to free memory
            if not self._request_times[client_id]:
                del self._request_times[client_id]

    def _get_request_count(self, client_id: str) -> int:
        """Get number of requests in current window."""
        return len(self._request_times[client_id])

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit for incoming requests."""
        current_time = time.time()

        # Periodic cleanup to prevent memory leaks
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries()
            self._last_cleanup = current_time

        client_id = self._get_client_id(request)
        cutoff = current_time - self.window_seconds

        # Cleanup old requests for this client
        self._request_times[client_id] = [
            t for t in self._request_times[client_id] if t > cutoff
        ]

        # Get current count
        request_count = self._get_request_count(client_id)

        # Check if over limit
        if request_count >= self.requests_per_window:
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={
                    "X-RateLimit-Limit": str(self.requests_per_window),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(self.window_seconds),
                },
            )

        # Record this request
        self._request_times[client_id].append(current_time)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = self.requests_per_window - self._get_request_count(client_id)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_window)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))

        return response
