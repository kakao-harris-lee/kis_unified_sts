"""Required release snapshots fail closed and restore nested serving state."""

from __future__ import annotations

import pytest
from tos.engine.records import InstrumentKey
from tos_runtime.compose._broker_posttrade_wiring import DeferredKisWitness
from tos_runtime.posttrade.fill_fetch import PrefetchedSnapshot, snapshot_key
from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot, WitnessUnavailable

_DATE = "20261029"


class _CountingWitness:
    def __init__(self) -> None:
        self.calls: list[WitnessScope] = []
        self.snapshot = WitnessSnapshot(observed_at_generation=None, orders=())

    def observe(self, scope: WitnessScope) -> WitnessSnapshot:
        self.calls.append(scope)
        return self.snapshot


def _scope(symbol: str = "005930") -> WitnessScope:
    return WitnessScope(
        account="account-1",
        instrument_keys=(InstrumentKey(account="account-1", instrument=symbol),),
        order_dates=(_DATE,),
    )


def _prefetched(
    scope: WitnessScope,
    *,
    today: str = _DATE,
    started_ms: int = 100,
    finished_ms: int = 110,
) -> PrefetchedSnapshot:
    return PrefetchedSnapshot(
        key=snapshot_key(scope),
        today=today,
        outcome=WitnessSnapshot(observed_at_generation=None, orders=()),
        read_started_ms=started_ms,
        read_finished_ms=finished_ms,
    )


@pytest.mark.parametrize(
    "refusal", ("missing", "scope_mismatch", "date_change", "expired")
)
def test_serving_required_refuses_unusable_prefetch_without_live_read(
    refusal: str,
) -> None:
    expected_scope = _scope()
    other_scope = _scope("000660")
    today = {"value": _DATE}
    witness = DeferredKisWitness(lambda: today["value"])
    inner = _CountingWitness()
    witness.inner = inner  # type: ignore[assignment]

    snapshot: PrefetchedSnapshot | None = _prefetched(expected_scope)
    now = {"ms": 100}

    def now_ms() -> int:
        return now["ms"]

    if refusal == "missing":
        snapshot = None
    elif refusal == "scope_mismatch":
        snapshot = _prefetched(other_scope)
    elif refusal == "date_change":
        today["value"] = "20261030"
    elif refusal == "expired":
        now["ms"] = 111

    with witness.serving_required(
        snapshot,
        expected_scope=expected_scope,
        expected_today=_DATE,
        max_age_ms=10,
        now_ms=now_ms,
    ) as uses:
        with pytest.raises(WitnessUnavailable):
            witness.observe(expected_scope)

    assert inner.calls == []
    if refusal == "expired":
        assert [(use.verdict, use.age_ms) for use in uses] == [("expired", 11)]
    else:
        assert uses == []


def test_serving_required_restores_outer_serving_context_after_nested_refusal() -> None:
    outer_scope = _scope()
    required_scope = _scope("000660")
    outer_snapshot = _prefetched(outer_scope, started_ms=90, finished_ms=95)
    mismatched_snapshot = _prefetched(outer_scope, started_ms=1, finished_ms=2)
    witness = DeferredKisWitness(lambda: _DATE)
    inner = _CountingWitness()
    witness.inner = inner  # type: ignore[assignment]

    with witness.serving(
        outer_snapshot,
        max_age_ms=20,
        now_ms=lambda: 100,
    ) as outer_uses:
        assert witness.observe(outer_scope) is outer_snapshot.outcome

        with witness.serving_required(
            mismatched_snapshot,
            expected_scope=required_scope,
            expected_today=_DATE,
            max_age_ms=1,
            now_ms=lambda: 1_000,
        ):
            with pytest.raises(WitnessUnavailable):
                witness.observe(required_scope)

        # If the nested strict scope, clock, or age limit leaked, the outer snapshot would
        # be refused or the inner witness would be consulted here.
        assert witness.observe(outer_scope) is outer_snapshot.outcome

    assert [(use.verdict, use.age_ms) for use in outer_uses] == [
        ("served", 10),
        ("served", 10),
    ]
    assert inner.calls == []
