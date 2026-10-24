"""B5 — the per-pass Safety Authority witness heartbeat, and the stock tree's approved bound.

Measured incident (2026-10-24 stock MOCK dry-run): ``authority.yaml::containment_bound_ms`` was
1000 and the witness was checked at boot and next at the send boundary, so any signal more than a
second after boot reached item 16 with SAFETY_AUTHORITY unestablished — CURRENTNESS UNKNOWN, send
refused. Operator decision 2026-10-24, option (A): re-verify the witness every pass, and set the
STOCK tree's bound to 90000 (the 60 s closed-session evaluation cadence + one pass). paper, LONG
and SHORT keep 1000.

Each scenario boots the fixture tree with a COMMITTED tree's own ``authority.yaml`` copied in —
the value under test is the one that ships, never a number typed here. "Passes" are driven the
way the scheduler drives them: advance the clock by the pass gap, evaluate time (what the pacer
does: every pass while open, every ``time_evaluate_closed_interval_ms`` while closed), then the
heartbeat. The send boundary is the kis-mock dry_run path ``test_kis_mock_e2e_honesty.py`` drives.
The clock is :class:`~.test_compose_root.FakeMonotonicSource`, the one the time service and the
epoch service both read, so a session's worth of passes runs in seconds.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from tos.authority import CurrentnessWitness
from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.compose._authority_heartbeat import (
    AUTHORITY_WITNESS_LOST_KIND,
    AuthorityWitnessHeartbeat,
    with_authority_heartbeat,
)
from tos_runtime.compose._transport_wiring import TransportKind

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from .test_compose_root import FakeMonotonicSource, _compose, _reach_trusted
from .test_kis_mock_e2e_honesty import (
    _drive_crossing_tick,
    _evidence_kind_count,
    _outcomes,
    _sealed_mock_deployment,
)
from .test_marketfeed_wiring import (
    _write_critical_input_policy,
    _write_journal,
    _write_marketfeed_config,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_TREES = _REPO_ROOT / "config" / "tos_runtime"
_STOCK = "cp3-setup-d-stock-005930"
_OTHER_TREES = ("paper", "cp3-setup-d-long", "cp3-setup-d-short")


def _tree_value(tree: str, name: str, key: str) -> int:
    value = yaml.safe_load((_TREES / tree / name).read_text(encoding="utf-8"))[key]
    assert isinstance(value, int)
    return value


#: Every CP-3 tree's pacing, read from the stock tree (the scenarios' timeline).
_PASS_MS = _tree_value(_STOCK, "marketfeed.yaml", "poll_interval_ms")
_CLOSED_CADENCE_MS = _tree_value(
    _STOCK, "marketfeed.yaml", "time_evaluate_closed_interval_ms"
)
_MINUTE_MS = 60_000


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _boot(tree, tmp_path, config_dir, data_dir, custody_root, server, monkeypatch):
    """The fixture MOCK deployment (dry_run, fake KIS host) with ``tree``'s own
    ``authority.yaml`` — byte-copied, so its ``containment_bound_ms`` is the shipped one.
    """
    _sealed_mock_deployment(
        config_dir, custody_root, server, monkeypatch, mode="dry_run"
    )
    shutil.copyfile(_TREES / tree / "authority.yaml", config_dir / "authority.yaml")
    clock = FakeMonotonicSource()
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        monotonic_source=clock,
        transport_kind=TransportKind.KIS_MOCK,
    )
    _reach_trusted(runtime)
    return runtime, clock


def _passes(runtime, clock, *, total_ms: int, gap_ms: int, heartbeat=None) -> None:
    """Scheduler passes over ``total_ms``: clock forward ``gap_ms``, time evaluated, heartbeat."""
    for _ in range(total_ms // gap_ms):
        clock.next_value += gap_ms
        runtime.time_service.evaluate()
        if heartbeat is not None:
            heartbeat()


def _morning(runtime, clock, heartbeat=None) -> None:
    """08:55 boot -> five closed minutes at the closed cadence -> 09:00 open -> five open
    minutes at the poll interval -> the 09:05 signal is driven by the caller."""
    _passes(
        runtime,
        clock,
        total_ms=5 * _MINUTE_MS,
        gap_ms=_CLOSED_CADENCE_MS,
        heartbeat=heartbeat,
    )
    _passes(
        runtime, clock, total_ms=5 * _MINUTE_MS, gap_ms=_PASS_MS, heartbeat=heartbeat
    )


def _heartbeat(runtime) -> AuthorityWitnessHeartbeat:
    return AuthorityWitnessHeartbeat(
        runtime.authority_epoch_service, runtime.evidence_store
    )


def _close(runtime) -> None:
    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ---------------------------------------------------------------------------
# the committed values
# ---------------------------------------------------------------------------


def test_the_stock_bound_covers_the_closed_cadence_plus_one_pass() -> None:
    """The approved value's own justification, checked against the tree it ships in."""
    bound = _tree_value(_STOCK, "authority.yaml", "containment_bound_ms")
    assert bound == 90_000
    assert bound >= _CLOSED_CADENCE_MS + _PASS_MS


@pytest.mark.parametrize("tree", _OTHER_TREES)
def test_paper_long_and_short_keep_1000(tree: str) -> None:
    assert _tree_value(tree, "authority.yaml", "containment_bound_ms") == 1000


# ---------------------------------------------------------------------------
# the stock tree (90000) with the heartbeat
# ---------------------------------------------------------------------------


def test_stock_boot_at_0855_signal_at_0905_is_17_of_17(
    tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
) -> None:
    runtime, clock = _boot(
        _STOCK, tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    _morning(runtime, clock, heartbeat=_heartbeat(runtime))

    _drive_crossing_tick(runtime, custody_root)
    outcomes = _outcomes(runtime)
    assert len(outcomes) == 17
    assert set(outcomes.values()) == {"SATISFIED"}, outcomes
    assert _evidence_kind_count(runtime, "SEND_SEALED") == 1
    assert _evidence_kind_count(runtime, "TRANSPORT_DRY_RUN") == 1
    assert _evidence_kind_count(runtime, AUTHORITY_WITNESS_LOST_KIND) == 0
    _close(runtime)


def test_red_stock_the_same_morning_without_the_heartbeat_is_refused(
    tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
) -> None:
    """What main does: the bound alone cannot carry ten minutes with no re-verification."""
    runtime, clock = _boot(
        _STOCK, tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    _morning(runtime, clock)

    _drive_crossing_tick(runtime, custody_root)
    assert _outcomes(runtime)["CURRENTNESS"] == "UNKNOWN"
    assert _evidence_kind_count(runtime, "SEND_SEALED") == 0
    _close(runtime)


@pytest.mark.parametrize("slow_pass_ms", [2_000, 10_000])
def test_stock_a_slow_send_pass_inside_the_session_keeps_authority(
    tmp_path, config_dir, data_dir, custody_root, server, monkeypatch, slow_pass_ms: int
) -> None:
    """One pass that ran ``slow_pass_ms`` (the kis-mock send pacing sleeps up to
    ``min_send_interval_ms`` 2000; the request timeout is 10 s) — inside the bound."""
    runtime, clock = _boot(
        _STOCK, tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    heartbeat = _heartbeat(runtime)
    _morning(runtime, clock, heartbeat=heartbeat)
    _passes(
        runtime, clock, total_ms=slow_pass_ms, gap_ms=slow_pass_ms, heartbeat=heartbeat
    )
    _passes(runtime, clock, total_ms=_MINUTE_MS, gap_ms=_PASS_MS, heartbeat=heartbeat)

    _drive_crossing_tick(runtime, custody_root)
    assert _outcomes(runtime)["CURRENTNESS"] == "SATISFIED"
    assert _evidence_kind_count(runtime, "SEND_SEALED") == 1
    assert _evidence_kind_count(runtime, AUTHORITY_WITNESS_LOST_KIND) == 0
    _close(runtime)


def test_stock_a_heartbeat_missed_past_90_s_refuses_and_stays_refused(
    tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
) -> None:
    """One gap past the bound expires the witness. On-time heartbeats afterwards do not revive
    it (the 2026-09-08 one-way door is intact): every later send is refused, loss recorded once.
    """
    runtime, clock = _boot(
        _STOCK, tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    heartbeat = _heartbeat(runtime)
    _morning(runtime, clock, heartbeat=heartbeat)
    bound = _tree_value(_STOCK, "authority.yaml", "containment_bound_ms")
    _passes(runtime, clock, total_ms=bound + 1, gap_ms=bound + 1, heartbeat=heartbeat)
    _passes(runtime, clock, total_ms=_MINUTE_MS, gap_ms=_PASS_MS, heartbeat=heartbeat)

    _drive_crossing_tick(runtime, custody_root)
    assert _outcomes(runtime)["CURRENTNESS"] == "UNKNOWN"
    assert _evidence_kind_count(runtime, "SEND_SEALED") == 0
    assert _evidence_kind_count(runtime, AUTHORITY_WITNESS_LOST_KIND) == 1
    assert runtime.authority_epoch_service.witness().present is False
    _close(runtime)


# ---------------------------------------------------------------------------
# paper / LONG / SHORT (1000): unchanged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tree", _OTHER_TREES)
def test_other_trees_a_pre_open_boot_still_loses_authority_at_the_open(
    tree, tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
) -> None:
    """Pinned as unchanged: at 1000 the 60 s closed cadence expires the witness even with the
    heartbeat, so a pre-open boot of these trees refuses at item 16 exactly as on main. Their
    bound is a separate decision once their step-4 path exists (operator 2026-10-24)."""
    runtime, clock = _boot(
        tree, tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    _morning(runtime, clock, heartbeat=_heartbeat(runtime))

    _drive_crossing_tick(runtime, custody_root)
    assert _outcomes(runtime)["CURRENTNESS"] == "UNKNOWN"
    assert _evidence_kind_count(runtime, "SEND_SEALED") == 0
    _close(runtime)


# ---------------------------------------------------------------------------
# wiring
# ---------------------------------------------------------------------------


def test_the_hook_beats_first_and_then_runs_the_wrapped_post_pass() -> None:
    """Heartbeat before the fill observer: an observer that raises cannot skip it."""
    calls: list[str] = []

    class _Service:
        def witness(self) -> CurrentnessWitness:
            calls.append("heartbeat")
            return CurrentnessWitness(present=True, within_containment_bound=True)

    class _Composed:
        authority_epoch_service = _Service()
        evidence_store = None

    def observer() -> None:
        calls.append("observer")
        raise RuntimeError("observer failed")

    hook = with_authority_heartbeat(_Composed(), observer)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        hook()
    assert calls == ["heartbeat", "observer"]
    with_authority_heartbeat(_Composed(), None)()  # type: ignore[arg-type]
    assert calls[-1] == "heartbeat"


def _stop_after_one():
    seen = {"n": 0}

    def _stop() -> bool:
        seen["n"] += 1
        return seen["n"] > 1

    return _stop


def test_the_composed_scheduler_pass_calls_the_composed_witness_once(
    tmp_path, config_dir, data_dir, custody_root, monkeypatch
) -> None:
    """Production wiring: one pass of the real ``run_forever`` loop calls the witness of the
    SAME epoch service instance the send boundary reads, once (synthetic transport — the
    heartbeat is transport-independent, so paper / LONG / SHORT get it too)."""
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    assert runtime.marketfeed is not None

    callers: list[object] = []
    original = SafetyAuthorityEpochService.witness

    def _spy(self):
        callers.append(self)
        return original(self)

    monkeypatch.setattr(SafetyAuthorityEpochService, "witness", _spy)
    runtime.marketfeed.run_forever(sleep=lambda _s: None, stop=_stop_after_one())
    assert callers == [runtime.authority_epoch_service]
    _close(runtime)
