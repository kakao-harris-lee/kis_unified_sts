"""``ProjectionExporter`` — atomic JSON export of an
:class:`~tos_runtime.operator.projection.OperatorProjection` build (TOS Phase 5 W4 plan §2
decision 7).

**Atomicity.** ``export()`` never lets a partially-written file become visible at the final
path: the JSON document is written to a temp file first (``path.with_suffix(".tmp")``), then
``os.replace`` — a single filesystem rename, atomic on every platform this runtime targets —
publishes it at the real path. A reader of the real path therefore either sees the PREVIOUS
complete export or the NEW complete export, never a half-written one.

**Failure never reaches the caller.** ``export()`` catches every exception a build-and-write
cycle can raise (a read callable inside the projection failing is already handled by
:class:`~tos_runtime.operator.projection.OperatorProjection` itself — see that module's own
docstring — so what this class additionally guards against is the WRITE side: an unwritable
directory, a serialization failure, a filesystem error mid-rename). On any such failure this
records :attr:`failures` (incremented) and :attr:`last_error` (``repr()`` of the exception) and
returns — it never raises and never partially writes the real path. This is deliberate: a
projection export is an OBSERVATION side effect, not a trading-path one, and observation
failures must never propagate into (or halt) the driver turn that triggers them (see
:meth:`tos_runtime.engine.driver.EngineDriver.bind_after_turn`) — the projection watches the
driver, the driver's own halt/latch machinery is the only thing allowed to stop a trading turn.

Firewall: stdlib only (``json``, ``os``, ``pathlib``) plus
``tos_runtime.operator.projection`` — no ``tos``/other ``tos_runtime`` import (this class must
not become a write port over anything besides its own destination JSON file; see
``tests/operator/test_no_write_port.py``).
"""

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
        #: This exporter's OWN write-side failure count — distinct from (and unaware of) the
        #: per-build ``export.failures``/``export.last_error`` fields the projection document
        #: itself carries for its read-callable failures (module docstring).
        self.failures = 0
        self.last_error: str | None = None

    def export(self) -> None:
        """Build one projection document and atomically publish it to ``self._path``.

        Never raises (module docstring's "failure never reaches the caller").
        """
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
        """Return this exporter's :meth:`export` bound method, for
        :meth:`tos_runtime.engine.driver.EngineDriver.bind_after_turn`."""
        return self.export
