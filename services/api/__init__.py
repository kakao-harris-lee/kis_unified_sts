"""API Gateway 모듈

FastAPI 기반 REST API.

Usage:
    from services.api import create_app

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

from services.api.app import create_app
from services.api.routes import router

__all__ = [
    "create_app",
    "router",
]
