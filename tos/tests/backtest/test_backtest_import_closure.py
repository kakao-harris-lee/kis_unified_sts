"""§2.4 author-level lock for ``tos.backtest`` — the closure canaries live in the shared table."""

from __future__ import annotations

import tos.backtest
import tos.backtest._base
import tos.backtest.bars
import tos.backtest.calibration
import tos.backtest.converter
import tos.backtest.driver
import tos.backtest.fills
import tos.backtest.records
import tos.backtest.resolver
import tos.backtest.results
import tos.backtest.scenarios
import tos.backtest.vocabulary

from .._closure_table import POLICIES

_LOADED_SUBMODULES = {
    "tos.backtest": tos.backtest,
    "tos.backtest._base": tos.backtest._base,
    "tos.backtest.bars": tos.backtest.bars,
    "tos.backtest.calibration": tos.backtest.calibration,
    "tos.backtest.converter": tos.backtest.converter,
    "tos.backtest.driver": tos.backtest.driver,
    "tos.backtest.fills": tos.backtest.fills,
    "tos.backtest.records": tos.backtest.records,
    "tos.backtest.resolver": tos.backtest.resolver,
    "tos.backtest.results": tos.backtest.results,
    "tos.backtest.scenarios": tos.backtest.scenarios,
    "tos.backtest.vocabulary": tos.backtest.vocabulary,
}


def test_the_loaded_submodule_map_matches_the_policy() -> None:
    """Anti-phantom: this file's own map is the same submodule set the closure policy declares."""
    assert set(_LOADED_SUBMODULES) == set(POLICIES["backtest"].child_imports)


def test_the_core_type_is_referenced_for_typing_only_and_never_re_exported() -> None:
    """(§2.4) ``EngineCore`` is a **contract-typing** reference in one module, and nothing more."""
    assert not hasattr(tos.backtest, "EngineCore"), (
        "tos.backtest re-exports EngineCore — the harness's public surface must not offer the core "
        "it is forbidden to re-instantiate (design #33 §2.4)"
    )
    carriers = sorted(
        name
        for name, module in _LOADED_SUBMODULES.items()
        if "EngineCore" in vars(module)
    )
    assert carriers == ["tos.backtest.driver"], (
        f"EngineCore is named by {carriers} — slice #1 needs it in exactly one place, the driver's "
        "run signature (design #33 §4.1)"
    )
