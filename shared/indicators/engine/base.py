"""Backend interface and result type for the indicator engine.

``IndicatorBackend`` is the abstraction every calculation provider implements —
TA-Lib today (:mod:`shared.indicators.engine.talib_backend`), a Numba/NumPy
backend for custom indicators later (WS-A5). Consumers depend only on this
interface and never on a concrete backend, so swapping or layering providers is
a registry change (see :mod:`shared.indicators.engine.registry`).
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow, flat_key


class IndicatorError(Exception):
    """Base error for the indicator engine."""


class UnsupportedIndicatorError(IndicatorError):
    """Raised when no registered backend can compute a requested indicator."""


class IndicatorComputationError(IndicatorError):
    """Raised when a backend fails to compute a supported indicator."""


@dataclass(frozen=True, eq=False)
class IndicatorResult:
    """The output of computing one :class:`IndicatorSpec` over one window.

    Attributes:
        spec: The spec that produced this result.
        series: Output-id -> full aligned series (leading warmup values NaN).
        latest: Output-id -> last finite scalar (NaN if the window is too short).
    """

    spec: IndicatorSpec
    series: Mapping[str, np.ndarray]
    latest: Mapping[str, float]

    def flat_latest(self) -> dict[str, float]:
        """Latest scalars re-keyed to canonical flat runtime keys.

        Non-finite values (warmup NaN / inf) are dropped so the cache never
        publishes a junk value. This is the exact shape the cache engine writes
        and the builder evaluator reads.
        """
        out: dict[str, float] = {}
        params = self.spec.param_map
        for output, value in self.latest.items():
            if value is None:
                continue
            numeric = float(value)
            if not math.isfinite(numeric):
                continue
            out[flat_key(self.spec.indicator_id, output, params)] = numeric
        return out


class IndicatorBackend(ABC):
    """A provider that computes some set of indicators.

    Subclasses declare which ids they cover (:meth:`supported_ids`) and how to
    compute one (:meth:`compute`). :meth:`compute_latest` has a working default
    (batch, take the finite tail); a backend with a genuine streaming path may
    override it for O(1) latest-value updates (WS-A2).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short backend identifier, used in logs and diagnostics."""

    @abstractmethod
    def supported_ids(self) -> frozenset[str]:
        """The catalog indicator ids this backend can compute."""

    def supports(self, indicator_id: str) -> bool:
        """Whether this backend can compute ``indicator_id``."""
        return indicator_id in self.supported_ids()

    @abstractmethod
    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        """Compute the full series + latest scalars for ``spec`` over ``window``.

        Raises:
            UnsupportedIndicatorError: if ``spec.indicator_id`` is not supported.
            IndicatorComputationError: if computation fails.
        """

    def compute_latest(
        self, spec: IndicatorSpec, window: OHLCVWindow
    ) -> dict[str, float]:
        """Return only the latest scalars, keyed by canonical flat key.

        Default implementation delegates to :meth:`compute`. Backends with a
        streaming fast-path override this.
        """
        return self.compute(spec, window).flat_latest()
