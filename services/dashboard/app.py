"""FastAPI dashboard application."""
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def create_app(
    title: str = "KIS Unified Trading Dashboard",
    debug: bool = False,
) -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title=title,
        description="Real-time trading dashboard for KIS unified platform",
        version="1.0.0",
        debug=debug,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register API routes."""
    from services.dashboard.routes import signals, trading

    # Include API routers
    app.include_router(trading.router)
    app.include_router(signals.router)

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
        }

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {"message": "KIS Unified Trading Dashboard API"}
