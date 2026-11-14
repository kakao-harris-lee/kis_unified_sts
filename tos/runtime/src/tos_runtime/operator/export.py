"""``ProjectionExporter`` — atomic JSON export of an"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tos_runtime.operator.projection import OperatorProjection

__all__ = ["ProjectionExporter"]


class ProjectionExporter:
    """Builds ``projection`` and atomically writes it to ``path`` as JSON."""

    def __init__(self, path: Path, projection: OperatorProjection) -> None:
        self._path = path
        self._projection = projection
        self.failures = 0
        self.last_error: str | None = None

    def export(self) -> None:
        """Build one projection document and atomically publish it to ``self._path``."""
        try:
            document: dict[str, Any] = self._projection.build()
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(document, sort_keys=True)
            tmp_path = self._path.with_suffix(".tmp")
            tmp_path.write_text(payload)
            os.replace(tmp_path, self._path)
        except (
            Exception
        ) as exc:  # noqa: BLE001 - an export failure must never propagate
            self.failures += 1
            self.last_error = repr(exc)
            return

    def as_after_turn_callback(self) -> Callable[[], None]:
        """Return this exporter's :meth:`export` bound method, for"""
        return self.export
