"""The cross-process app-key request gate (#1125 — 2026-11-20 13:00–13:20 KST)."""

from __future__ import annotations

import stat
import threading
from pathlib import Path

import pytest
from tos_runtime.transport.kis_mock.pacer import (
    KisAppKeyPacer,
    KisPacing,
    KisPacingRefused,
)
from tos_runtime.transport.kis_mock.shared_pacer import (
    SharedAppKeyGate,
    SharedPacingRefused,
)

from ._fakes import FakeMonotonicSource


class _Clock:
    """A wall clock the test moves, shared by every gate instance in that test."""

    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.now = start
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        """Sleeping moves this clock instead of the wall — the whole test stays hermetic."""
        self.slept.append(seconds)
        self.now += seconds


def _gate(path: Path, clock: _Clock, *, max_rps: float = 2.0) -> SharedAppKeyGate:
    return SharedAppKeyGate(
        path=path, max_rps=max_rps, now_epoch_s=clock, sleep=clock.sleep
    )


def test_the_second_process_waits_out_the_first_processs_slot(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "pace" / "stock-mock.pace"
    first, second = _gate(path, clock), _gate(path, clock)

    first.acquire(wait_budget_s=4.0)
    assert clock.slept == []
    second.acquire(wait_budget_s=4.0)
    assert clock.slept == [pytest.approx(0.5)]


def test_three_tenants_never_land_inside_one_interval(tmp_path: Path) -> None:
    """The failing input: three processes asking at the same instant."""
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    grants: list[float] = []
    for _ in range(3):
        gate = _gate(path, clock)
        gate.acquire(wait_budget_s=4.0)
        grants.append(clock.now)

    gaps = [b - a for a, b in zip(grants, grants[1:])]
    assert gaps == [pytest.approx(0.5), pytest.approx(0.5)]


def test_a_slot_further_away_than_the_budget_refuses(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    _gate(path, clock, max_rps=0.1).acquire(wait_budget_s=4.0)

    with pytest.raises(SharedPacingRefused, match="not sent"):
        _gate(path, clock, max_rps=0.1).acquire(wait_budget_s=4.0)
    assert clock.slept == []


def test_an_elapsed_interval_does_not_wait(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    _gate(path, clock).acquire(wait_budget_s=4.0)
    clock.now += 10.0

    _gate(path, clock).acquire(wait_budget_s=4.0)
    assert clock.slept == []


@pytest.mark.parametrize("content", ["", "not a number", "9999999999999999999999 x"])
def test_a_corrupted_grant_file_grants_rather_than_stalling(
    tmp_path: Path, content: str
) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    path.write_text(content, encoding="utf-8")

    _gate(path, clock).acquire(wait_budget_s=4.0)
    assert clock.slept == []
    assert float(path.read_text(encoding="utf-8").strip()) == pytest.approx(clock.now)


def test_a_grant_dated_in_the_future_is_not_trusted(tmp_path: Path) -> None:
    """A clock that moved must not stall every tenant until it catches up."""
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    path.write_text(f"{clock.now + 3600:.6f}\n", encoding="utf-8")

    _gate(path, clock).acquire(wait_budget_s=4.0)
    assert clock.slept == []


def test_the_grant_file_and_its_directory_are_private(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "pace" / "stock-mock.pace"
    _gate(path, clock).acquire(wait_budget_s=4.0)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert not list(path.parent.glob("*.tmp"))


def test_a_non_positive_rate_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        SharedAppKeyGate(path=tmp_path / "p", max_rps=0.0)


class TestTheInProcessPacerSpendsTheSameBudget:
    """``KisAppKeyPacer`` keeps its own spacing AND takes the app key's shared slot."""

    def test_a_pacer_without_a_gate_is_unchanged(self, tmp_path: Path) -> None:
        del tmp_path
        pacer = KisAppKeyPacer(
            pacing=KisPacing(min_interval_ms=1, wait_budget_ms=4_000),
            monotonic=FakeMonotonicSource(start_ms=1_000),
        )
        assert pacer.acquire() == 1_000

    def test_a_pacer_with_a_gate_takes_the_shared_slot_too(
        self, tmp_path: Path
    ) -> None:
        clock, path = _Clock(), tmp_path / "stock-mock.pace"
        _gate(path, clock).acquire(wait_budget_s=4.0)
        pacer = KisAppKeyPacer(
            pacing=KisPacing(min_interval_ms=1, wait_budget_ms=4_000),
            monotonic=FakeMonotonicSource(start_ms=1_000),
            shared_gate=_gate(path, clock),
        )

        pacer.acquire()
        assert clock.slept == [pytest.approx(0.5)]

    def test_a_shared_refusal_reaches_the_caller_as_a_pacing_refusal(
        self, tmp_path: Path
    ) -> None:
        """So an order becomes `REJECT reason=throttled sent=false`, not an exception."""
        clock, path = _Clock(), tmp_path / "stock-mock.pace"
        _gate(path, clock, max_rps=0.1).acquire(wait_budget_s=4.0)
        pacer = KisAppKeyPacer(
            pacing=KisPacing(min_interval_ms=1, wait_budget_ms=1_000),
            monotonic=FakeMonotonicSource(start_ms=1_000),
            shared_gate=_gate(path, clock, max_rps=0.1),
        )

        with pytest.raises(KisPacingRefused):
            pacer.acquire()

    def test_a_held_lock_refuses_inside_the_budget(self, tmp_path: Path) -> None:
        clock, path = _Clock(), tmp_path / "stock-mock.pace"
        gate = SharedAppKeyGate(
            path=path, max_rps=2.0, now_epoch_s=clock, sleep=clock.sleep
        )
        held, done = threading.Event(), threading.Event()

        def _hold() -> None:
            from tos_runtime.transport.kis_mock.file_lock import exclusive_file_lock

            with exclusive_file_lock(path.with_name(path.name + ".lock"), wait_s=5.0):
                held.set()
                done.wait(5.0)

        holder = threading.Thread(target=_hold)
        holder.start()
        try:
            assert held.wait(5.0)
            with pytest.raises(SharedPacingRefused):
                gate.acquire(wait_budget_s=0.1)
        finally:
            done.set()
            holder.join(5.0)
