"""Thin public shim over the engine-hosted reference calculators (P1-a).

The reference math formerly defined here now lives in
:mod:`shared.indicators.engine.reference_backend` — the single source of truth,
exposed to engine consumers through
:class:`~shared.indicators.engine.reference_backend.ReferenceBackend` and to
direct consumers through this module's re-exports. Import paths are unchanged
(``from shared.indicators.reference import ...``) and every symbol delegates to
the same implementation, so all existing consumers keep byte-identical values
(pinned by ``tests/unit/indicators/test_reference_contract.py``).

See ``docs/plans/2026-07-08-new-architecture-refactoring-plan.md`` §3 (P1-a).
"""

from __future__ import annotations

from shared.indicators.engine.reference_backend import (
    ADXCalculator,
    ADXConfig,
    ATRCalculator,
    ATRConfig,
    MFICalculator,
    StochRSICalculator,
    StochRSIConfig,
    wilder_rma,
    wilder_rsi,
)

__all__ = [
    "ADXCalculator",
    "ADXConfig",
    "ATRCalculator",
    "ATRConfig",
    "MFICalculator",
    "StochRSICalculator",
    "StochRSIConfig",
    "wilder_rma",
    "wilder_rsi",
]
