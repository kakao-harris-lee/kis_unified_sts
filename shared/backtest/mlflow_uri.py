"""Single source of truth for resolving the MLflow tracking URI.

All MLflow clients (the backtest tracker, RL model registry, `sts mlflow`
commands) resolve their tracking URI through :func:`resolve_tracking_uri` so the
deployment can route every client through the managed server with one env var
instead of each call site hardcoding ``sqlite:///mlflow.db``.
"""

from __future__ import annotations

import os

# Local sqlite store at the repo root — the default when no server is configured.
DEFAULT_TRACKING_URI = "sqlite:///mlflow.db"


def resolve_tracking_uri(explicit: str | None = None) -> str:
    """Return the MLflow tracking URI to use.

    Precedence: ``explicit`` argument > ``MLFLOW_TRACKING_URI`` env > local
    sqlite default.

    Setting ``MLFLOW_TRACKING_URI`` (e.g. ``http://localhost:5000`` for the
    docker ``mlflow`` service) routes run metadata through the server, so only
    the server process writes ``mlflow.db`` — avoiding the host-client +
    container double-writer contention on the sqlite file. Unset (or empty) →
    direct local sqlite, the previous behaviour.

    When the env points at an HTTP server, that server must be running
    (``docker compose up mlflow``) or clients will fail to connect — there is no
    silent fallback to sqlite, to avoid splitting runs across two stores.

    Args:
        explicit: A caller-supplied URI that overrides everything (e.g. a
            throwaway sqlite path in tests).

    Returns:
        The resolved tracking URI.
    """
    return explicit or os.environ.get("MLFLOW_TRACKING_URI") or DEFAULT_TRACKING_URI
