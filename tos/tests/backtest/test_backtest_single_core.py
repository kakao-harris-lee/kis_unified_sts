"""§2.4 / §8-4 — the per-bar core re-instantiation prohibition (design #33 §2.4, a hard constraint).

The tempting bypass is obvious: rebuild the ``EngineCore`` for each bar, the
``ProvisionalReservationLedger`` resets, the scope looks free again, and repeated sending "works".
The design forbids it twice over:

* **single-core parity is the point.** A backtest and a paper run must share the same core, the same
  sequencer, and the same ledger lifetime, or the backtest develops semantics paper does not have
  (design #31 §2.1/§12; 완주 메모 §3-2:63-65);
* **it forges headroom.** A reset manufactures capacity the real system does not have — the
  harness-layer form of RFC-002 §9.1:558's "producer-local counters SHALL NOT create headroom". The
  no-release constraint is an honest reflection of the RCL runtime's absence (``state.py:22``), not
  an obstacle to route around (design #33 §12.2-6).

Two independent seals are asserted here: the **runtime** guard (a driver refuses a second, different
core) and the **authoring-level** guard (no source in the package constructs an ``EngineCore`` at
all). The second is the #27 FD lesson in its D-E3 form — locking one call site is not locking the
package, so the whole source tree is swept by AST.

Regime tag: orchestration authoring evidence only; closes no EV (design #33 §1.1).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tos.backtest import (
    CoreReinstantiationError,
    FillMode,
    FillParameters,
    FillSide,
    MultiSymbolBacktestDriver,
    reference_bars,
)
from tos.engine import HaltReason

from ._backtest_fixtures import (
    build_core,
    build_driver,
    build_fill_model,
    instrument_key,
)

_BACKTEST_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "backtest"


def _ack_model():  # noqa: ANN202 - a local builder
    """An acknowledging band."""
    return build_fill_model(FillParameters(mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY))


def test_a_second_different_core_is_refused() -> None:
    """(§2.4) The runtime seal: one driver, one core, for the lifetime of the run."""
    fill_model = _ack_model()
    driver = build_driver(fill_model)
    first_core, _ = build_core(transmit=fill_model)
    driver.run(first_core, reference_bars(1))

    second_core, _ = build_core(transmit=fill_model)
    with pytest.raises(CoreReinstantiationError, match="already bound"):
        driver.run(second_core, reference_bars(1))


def test_re_running_the_same_core_is_allowed_and_keeps_the_reservation() -> None:
    """(§2.4) The *same* core may be re-run — and the scope stays occupied across runs.

    This is the positive half of the seal: continuing the run is fine, resetting it is not. The
    second run's tick is denied at the capacity stage, which is exactly the honest behaviour a real
    system without an RCL release path would show.
    """
    fill_model = _ack_model()
    driver = build_driver(fill_model)
    core, _ = build_core(transmit=fill_model)

    first = driver.run(core, reference_bars(1))
    assert first.handoff_count == 1

    second = driver.run(core, reference_bars(1))
    assert second.handoff_count == 1, "the second run must not hand off again"
    assert [halt.halt_reason for halt in second.halts] == [
        HaltReason.AT_MOST_ONE_EXPOSURE_HELD
    ]
    assert driver.bound_core is core
    assert core.ledger.admits_new_exposure(instrument_key()) is False


def test_the_reset_bypass_would_have_produced_a_second_send() -> None:
    """(§2.4) The bypass really *would* work — which is why the seal is not decorative.

    A fresh core per bar hands off twice for the same scope, forging headroom the real system does
    not have. Building the second core here is the test's own act, deliberately outside the driver;
    the package itself never does it (see the AST sweep below).
    """
    first_model = _ack_model()
    first_core, _ = build_core(transmit=first_model)
    build_driver(first_model).run(first_core, reference_bars(1))

    second_model = _ack_model()
    second_core, _ = build_core(transmit=second_model)
    build_driver(second_model).run(second_core, reference_bars(1))

    assert len(first_model.handoffs) == 1
    assert len(second_model.handoffs) == 1, (
        "two independent cores each hand off once — that is the forged headroom the §2.4 seal "
        "prevents a driver from reaching (RFC-002 §9.1:558)"
    )
    assert first_core is not second_core


def test_the_package_constructs_no_engine_core_anywhere() -> None:
    """(§2.4 authoring-level seal) No ``tos.backtest`` source instantiates an ``EngineCore``.

    The #27 FD lesson: locking one call site is not locking the package. Every shipped source is
    parsed and every ``EngineCore(...)`` call — however it is spelled — is reported.
    """
    sources = sorted(_BACKTEST_SRC.rglob("*.py"))
    assert sources, f"no tos.backtest sources found under {_BACKTEST_SRC}"

    offenders: list[str] = []
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else None
            )
            if name in {"EngineCore", "ProvisionalReservationLedger", "StrategyRegistry"}:
                offenders.append(f"{path.name}:{node.lineno} {name}()")
    assert offenders == [], (
        f"tos.backtest constructs engine state itself: {offenders} — the core, its ledger, and its "
        "registry are injected by the caller precisely so the harness cannot reset them "
        "(design #33 §2.4)"
    )


def test_the_driver_exposes_no_core_replacement_path() -> None:
    """(§2.4) There is no setter, no rebind, no reset — the seal cannot be undone from outside.

    The census covers **every** shipped driver, not the first one written: an N-lane driver that
    forgot the seal would reset one ledger for N scopes at once, so the multi-symbol driver is
    swept here rather than trusted to have inherited the discipline (design #37 §4 M17).
    """
    fill_model = _ack_model()
    drivers = {
        "BacktestDriver": build_driver(fill_model),
        "MultiSymbolBacktestDriver": MultiSymbolBacktestDriver(
            converters={}, fill_models={}, continuity_id="single-core-canary"
        ),
    }
    for name, driver in drivers.items():
        for forbidden in ("set_core", "rebind", "reset", "reset_core", "new_core", "rebuild"):
            assert not hasattr(driver, forbidden), (
                f"{name} exposes {forbidden!r} — a re-instantiation path defeats the seal"
            )


def test_every_shipped_driver_is_covered_by_the_replacement_canary() -> None:
    """(anti-phantom §0.5) The swept driver list is the shipped one — no stale subset.

    The existence direction: it is not enough that the two listed drivers are clean, the list must
    *be* the set of drivers the package exports. A third driver landing without its seal shows up
    here (design #37 §4 M17).

    Membership is **structural**, mirroring the run-result family's ``is_dataclass`` ∧
    ``closes_no_ev`` predicate: a driver is what carries ``bound_core`` — the §2.4 binding that is
    the seal's whole subject. A name-based test (``endswith("Driver")``) would let a
    ``LaneReplayHarness`` bind a core and escape the sweep in silence, which is the naming-versus-
    structure defect this suite refuses everywhere else.
    """
    import tos.backtest as package

    exported_drivers = {
        name
        for name, value in vars(package).items()
        if isinstance(value, type) and hasattr(value, "bound_core")
    }
    assert exported_drivers == {"BacktestDriver", "MultiSymbolBacktestDriver"}, (
        "the shipped driver set and this suite's swept list have drifted: "
        f"exported={sorted(exported_drivers)}"
    )


def test_the_ledger_survives_the_whole_multi_bar_run() -> None:
    """(§2.4) One ledger for the whole stream — the reservation from bar 1 is still there at bar N."""
    fill_model = _ack_model()
    driver = build_driver(fill_model)
    core, _ = build_core(transmit=fill_model)
    run = driver.run(core, reference_bars(5))

    reservation = core.ledger.outstanding(instrument_key())
    assert reservation is not None
    assert run.handoff_count == 1
    denials = [
        halt for halt in run.halts if halt.halt_reason is HaltReason.AT_MOST_ONE_EXPOSURE_HELD
    ]
    assert len(denials) == 4, "bars 2-5 must each be denied — one ledger, one reservation"
