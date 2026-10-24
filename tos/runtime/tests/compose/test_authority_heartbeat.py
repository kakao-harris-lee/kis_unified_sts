"""B5 — the per-pass Safety Authority witness heartbeat, through the composed kis-mock runtime.

Measured incident (2026-10-24 stock MOCK dry-run): with ``authority.yaml::containment_bound_ms``
1000, a signal that arrived more than a second after boot reached the send boundary with
SAFETY_AUTHORITY unestablished, so CURRENTNESS was UNKNOWN and the send was refused — the witness
had been checked at boot and not again. These tests set the fixture tree's bound to that same
1000 and drive "passes" the way the scheduler does: advance the clock by one poll interval,
evaluate time (the pacer, session open), then the heartbeat. The send boundary itself is the
same kis-mock dry_run path ``test_kis_mock_e2e_honesty.py`` drives.

The clock is :class:`~.test_compose_root.FakeMonotonicSource` — the SAME one the time service
and the epoch service read — so five minutes of passes run in milliseconds.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
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

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: The stock / LONG / SHORT / resident trees' committed value (the incident's bound).
_TREE_BOUND_MS = 1000
#: marketfeed.yaml ``poll_interval_ms`` in every CP-3 tree.
_PASS_MS = 400
_FIVE_MINUTES_MS = 5 * 60 * 1000


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _set_bound(config_dir: Path, bound_ms: int) -> None:
    path = config_dir / "authority.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["containment_bound_ms"] = bound_ms
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _boot(
    tmp_path,
    config_dir,
    data_dir,
    custody_root,
    server,
    monkeypatch,
    *,
    bound_ms: int = _TREE_BOUND_MS,
):
    _sealed_mock_deployment(
        config_dir, custody_root, server, monkeypatch, mode="dry_run"
    )
    _set_bound(config_dir, bound_ms)
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


def _passes(runtime, clock, *, total_ms: int, heartbeat=None, gap_ms: int = _PASS_MS):
    """Scheduler passes over ``total_ms``: clock forward one interval, time evaluated (the
    pacer, session open), then the heartbeat when one is given."""
    for _ in range(total_ms // gap_ms):
        clock.next_value += gap_ms
        runtime.time_service.evaluate()
        if heartbeat is not None:
            heartbeat()


def _close(runtime) -> None:
    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_with_the_heartbeat_a_signal_five_minutes_after_boot_is_17_of_17(
    tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
) -> None:
    runtime, clock = _boot(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    heartbeat = AuthorityWitnessHeartbeat(
        runtime.authority_epoch_service, runtime.evidence_store
    )
    _passes(runtime, clock, total_ms=_FIVE_MINUTES_MS, heartbeat=heartbeat)

    _drive_crossing_tick(runtime, custody_root)
    outcomes = _outcomes(runtime)
    assert len(outcomes) == 17
    assert set(outcomes.values()) == {"SATISFIED"}, outcomes
    assert _evidence_kind_count(runtime, "SEND_SEALED") == 1
    assert _evidence_kind_count(runtime, "TRANSPORT_DRY_RUN") == 1
    assert _evidence_kind_count(runtime, AUTHORITY_WITNESS_LOST_KIND) == 0
    _close(runtime)


def test_red_without_the_heartbeat_the_same_signal_is_refused_at_currentness(
    tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
) -> None:
    """The incident, reproduced: same boot, same five minutes, no heartbeat."""
    runtime, clock = _boot(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    _passes(runtime, clock, total_ms=_FIVE_MINUTES_MS)

    _drive_crossing_tick(runtime, custody_root)
    outcomes = _outcomes(runtime)
    assert outcomes["CURRENTNESS"] == "UNKNOWN"
    assert _evidence_kind_count(runtime, "SEND_SEALED") == 0
    _close(runtime)


def test_one_missed_heartbeat_refuses_for_good_and_records_the_loss_once(
    tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
) -> None:
    """A pass gap past the bound (one long pass) expires the witness; later heartbeats on time
    do not revive it (the method's one-way door) — every later send is refused."""
    runtime, clock = _boot(
        tmp_path, config_dir, data_dir, custody_root, server, monkeypatch
    )
    heartbeat = AuthorityWitnessHeartbeat(
        runtime.authority_epoch_service, runtime.evidence_store
    )
    _passes(runtime, clock, total_ms=60_000, heartbeat=heartbeat)
    _passes(runtime, clock, total_ms=1_500, heartbeat=heartbeat, gap_ms=1_500)
    _passes(runtime, clock, total_ms=60_000, heartbeat=heartbeat)

    _drive_crossing_tick(runtime, custody_root)
    assert _outcomes(runtime)["CURRENTNESS"] == "UNKNOWN"
    assert _evidence_kind_count(runtime, "SEND_SEALED") == 0
    assert _evidence_kind_count(runtime, AUTHORITY_WITNESS_LOST_KIND) == 1
    _close(runtime)


#: marketfeed.yaml ``time_evaluate_closed_interval_ms`` in every CP-3 tree — the pacer's
#: evaluation spacing while the session is known closed (boot 08:55, open 09:00).
_CLOSED_CADENCE_MS = 60_000


@pytest.mark.parametrize(
    ("bound_ms", "expected_currentness"),
    [
        # The committed value: a pre-open boot loses the witness at the open. NOT fixed by
        # this PR — the bound is an approved value (option A proposes ~90000).
        (_TREE_BOUND_MS, "UNKNOWN"),
        # A bound that covers the closed cadence plus one pass: the heartbeat carries it.
        (90_000, "SATISFIED"),
    ],
)
def test_a_pre_open_boot_survives_the_closed_cadence_only_if_the_bound_covers_it(
    tmp_path,
    config_dir,
    data_dir,
    custody_root,
    server,
    monkeypatch,
    bound_ms: int,
    expected_currentness: str,
) -> None:
    runtime, clock = _boot(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        server,
        monkeypatch,
        bound_ms=bound_ms,
    )
    heartbeat = AuthorityWitnessHeartbeat(
        runtime.authority_epoch_service, runtime.evidence_store
    )
    # five closed minutes at the closed cadence, then two open minutes at the poll interval
    _passes(
        runtime,
        clock,
        total_ms=5 * _CLOSED_CADENCE_MS,
        heartbeat=heartbeat,
        gap_ms=_CLOSED_CADENCE_MS,
    )
    _passes(runtime, clock, total_ms=120_000, heartbeat=heartbeat)

    _drive_crossing_tick(runtime, custody_root)
    assert _outcomes(runtime)["CURRENTNESS"] == expected_currentness
    _close(runtime)


def test_the_hook_beats_first_and_then_runs_the_wrapped_post_pass() -> None:
    """Heartbeat before the fill observer: an observer that raises cannot skip it."""
    calls: list[str] = []

    class _Service:
        def witness(self):
            calls.append("heartbeat")
            from tos.authority import CurrentnessWitness

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
    """Production wiring: ``compose_paper_runtime`` hands the scheduler a heartbeat over the
    SAME epoch service instance the send boundary reads, and one pass calls it once (synthetic
    transport — the heartbeat is transport-independent; paper / LONG / SHORT get it too).
    """
    from tos_runtime.authority.epoch import SafetyAuthorityEpochService

    from .test_marketfeed_wiring import (
        _write_critical_input_policy,
        _write_journal,
        _write_marketfeed_config,
    )

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
    # one pass of the real loop: tick, the post-pass hook, then stop
    runtime.marketfeed.run_forever(sleep=lambda _s: None, stop=_stop_after_one())
    assert callers == [runtime.authority_epoch_service]
    _close(runtime)
