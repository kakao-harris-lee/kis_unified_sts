"""Catalog <-> engine registry single-source-of-truth guardrail.

Every builder-catalog indicator marked ``runtime_supported`` must be computable
by the indicator engine, so "adding a new indicator = register it in the engine"
holds and the builder never offers an indicator it cannot actually compute.
"""

from __future__ import annotations

import pytest

pytest.importorskip("talib")

from shared.indicators.engine import default_engine  # noqa: E402
from shared.strategy_builder.catalog import load_capabilities  # noqa: E402


def test_runtime_supported_catalog_indicators_are_engine_supported() -> None:
    supported = default_engine().supported_ids()
    caps = load_capabilities()
    missing = [
        indicator.id
        for indicator in caps.indicators
        if indicator.runtime_supported and indicator.id not in supported
    ]
    assert not missing, (
        f"catalog runtime_supported ids not registered in the engine: {missing} "
        "(register them in a backend's _TABLE)"
    )


def test_implemented_catalog_indicators_are_engine_supported() -> None:
    """Every catalog id the builder marks ``implemented`` must be computable.

    ``implemented`` is the flag the picker uses to allow adding an indicator to
    a strategy; if the engine cannot compute it, the builder evaluator reports it
    ``missing`` and the condition never fires. This is the backend half of the
    bidirectional guardrail (the frontend half lives in
    ``strategy-builder-ui/src/lib/builder/catalogSot.test.ts``).
    """
    supported = default_engine().supported_ids()
    caps = load_capabilities()
    missing = [
        indicator.id
        for indicator in caps.indicators
        if indicator.implemented and indicator.id not in supported
    ]
    assert not missing, (
        f"catalog implemented ids not computable by the engine: {missing} "
        "(wire them into a backend's _TABLE or set implemented: false)"
    )
