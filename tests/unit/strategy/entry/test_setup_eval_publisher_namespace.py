"""setup_eval key namespacing + structural history dedup.

Two producers write setup evaluations: the monolithic orchestrator's Setup
adapters and the decoupled ``services/decision_engine`` daemon. While the
decoupled chain runs in SHADOW they run at the same time against the same Redis
DB, so they must not share a key — a shadow row overwriting the orchestrator's
row for the same setup name makes both unreadable and makes the F-9 Gate 1 check
unable to say whose row it read.

The default (``key_suffix=""``) must stay byte-for-byte the orchestrator's
historical keys; only an explicit suffix moves them.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import fakeredis
import pytest

from shared.strategy.entry import setup_eval_publisher as sep

KST = ZoneInfo("Asia/Seoul")
_FIXED = datetime(2026, 9, 9, 10, 30, tzinfo=KST)
_DATE = _FIXED.date().isoformat()


@pytest.fixture
def redis_and_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[fakeredis.FakeStrictRedis]:
    """A fake sync Redis wired in, with the module's globals restored after."""
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(sep, "acquire_infra_clients", lambda: (fake, None))
    monkeypatch.setattr(sep, "now_kst", lambda: _FIXED)

    saved_log = dict(sep._last_eval_log)
    saved_history = dict(sep._history_state)
    sep._last_eval_log.clear()
    sep._history_state.clear()
    try:
        yield fake
    finally:
        sep._last_eval_log.clear()
        sep._last_eval_log.update(saved_log)
        sep._history_state.clear()
        sep._history_state.update(saved_history)


def _history_rows(fake: Any, key: str) -> list[dict]:
    return [json.loads(row) for row in fake.lrange(key, 0, -1)]


def test_default_suffix_writes_the_orchestrator_keys(
    redis_and_publisher: fakeredis.FakeStrictRedis,
) -> None:
    """No suffix = the historical key set, unchanged."""
    fake = redis_and_publisher
    sep.publish_setup_eval("setup_a_gap_reversion", "reject", "no_event_in_window")

    assert fake.hget("trading:futures:setup_eval", "setup_a_gap_reversion")
    assert fake.exists(f"trading:futures:setup_eval:history:{_DATE}")


def test_suffix_moves_both_the_hash_and_the_history_list(
    redis_and_publisher: fakeredis.FakeStrictRedis,
) -> None:
    fake = redis_and_publisher
    sep.publish_setup_eval(
        "setup_d_vwap_reversion", "reject", "no_atr", key_suffix=":shadow"
    )

    assert fake.hget("trading:futures:setup_eval:shadow", "setup_d_vwap_reversion")
    assert fake.exists(f"trading:futures:setup_eval:history:shadow:{_DATE}")
    # The unsuffixed keys are untouched.
    assert fake.exists("trading:futures:setup_eval") == 0
    assert fake.exists(f"trading:futures:setup_eval:history:{_DATE}") == 0


def test_two_producers_do_not_overwrite_each_other(
    redis_and_publisher: fakeredis.FakeStrictRedis,
) -> None:
    """The shadow daemon and the orchestrator can both report on the SAME setup."""
    fake = redis_and_publisher
    sep.publish_setup_eval("setup_d_vwap_reversion", "fired", "short")
    sep.publish_setup_eval(
        "setup_d_vwap_reversion", "reject", "no_vwap", key_suffix=":shadow"
    )

    monolith = json.loads(
        fake.hget("trading:futures:setup_eval", "setup_d_vwap_reversion")
    )
    shadow = json.loads(
        fake.hget("trading:futures:setup_eval:shadow", "setup_d_vwap_reversion")
    )
    assert monolith["outcome"] == "fired"
    assert shadow["reason"] == "no_vwap"


def test_history_dedup_is_structural_not_per_measurement(
    redis_and_publisher: fakeredis.FakeStrictRedis,
) -> None:
    """One cause = one history row, however much its embedded numbers move.

    Reject reasons carry live measurements, so keying the dedup on the raw
    string appended one row per tick — the row explosion this fixes (it also
    affects the orchestrator, which uses the same publisher).
    """
    fake = redis_and_publisher
    for z in ("+0.42", "+0.91", "+1.55", "-0.30"):
        sep.publish_setup_eval(
            "setup_d_vwap_reversion", "reject", f"not_extreme(z={z},need±1.8)"
        )

    rows = _history_rows(fake, f"trading:futures:setup_eval:history:{_DATE}")
    assert len(rows) == 1, rows
    # The stored reason keeps its measurements — only the DEDUP key drops them.
    assert rows[0]["reason"] == "not_extreme(z=+0.42,need±1.8)"


def test_a_genuinely_new_cause_still_appends(
    redis_and_publisher: fakeredis.FakeStrictRedis,
) -> None:
    fake = redis_and_publisher
    sep.publish_setup_eval(
        "setup_d_vwap_reversion", "reject", "not_extreme(z=+0.42,need±1.8)"
    )
    sep.publish_setup_eval(
        "setup_d_vwap_reversion", "reject", "vol_below_gate(0.85<0.9)"
    )
    sep.publish_setup_eval("setup_d_vwap_reversion", "fired", "short")

    rows = _history_rows(fake, f"trading:futures:setup_eval:history:{_DATE}")
    assert [r["reason"] for r in rows] == [
        "not_extreme(z=+0.42,need±1.8)",
        "vol_below_gate(0.85<0.9)",
        "short",
    ]


def test_history_dedup_is_per_key_namespace(
    redis_and_publisher: fakeredis.FakeStrictRedis,
) -> None:
    """The shadow producer's dedup state must not swallow the orchestrator's row."""
    fake = redis_and_publisher
    sep.publish_setup_eval("setup_d_vwap_reversion", "reject", "no_atr")
    sep.publish_setup_eval(
        "setup_d_vwap_reversion", "reject", "no_atr", key_suffix=":shadow"
    )

    assert len(_history_rows(fake, f"trading:futures:setup_eval:history:{_DATE}")) == 1
    assert (
        len(_history_rows(fake, f"trading:futures:setup_eval:history:shadow:{_DATE}"))
        == 1
    )


# ---------------------------------------------------------------------------
# Failure reporting — the return value and the latched WARNING
# ---------------------------------------------------------------------------


class _BrokenRedis:
    """Every write fails, the way a Redis outage presents to this module."""

    def __init__(self, message: str = "redis down") -> None:
        self.message = message

    def hset(self, *_args: object, **_kwargs: object) -> None:
        raise ConnectionError(self.message)

    def expire(self, *_args: object, **_kwargs: object) -> None:
        raise ConnectionError(self.message)

    def rpush(self, *_args: object, **_kwargs: object) -> None:
        raise ConnectionError(self.message)


@pytest.fixture
def clean_failure_latch() -> Iterator[None]:
    saved = dict(sep._last_publish_failure)
    sep._last_publish_failure.clear()
    sep._last_eval_log.clear()
    try:
        yield
    finally:
        sep._last_publish_failure.clear()
        sep._last_publish_failure.update(saved)


def test_publish_returns_true_on_success(
    redis_and_publisher: fakeredis.FakeStrictRedis, clean_failure_latch: None
) -> None:
    assert sep.publish_setup_eval("setup_a_gap_reversion", "reject", "no_atr") is True


def test_publish_returns_true_when_no_client_is_wired(
    monkeypatch: pytest.MonkeyPatch, clean_failure_latch: None
) -> None:
    """Unwired is a deliberate configuration, not a failure."""
    monkeypatch.setattr(sep, "acquire_infra_clients", lambda: (None, None))
    assert sep.publish_setup_eval("setup_a_gap_reversion", "reject", "no_atr") is True


def test_publish_returns_false_and_warns_once_per_state_change(
    monkeypatch: pytest.MonkeyPatch, clean_failure_latch: None, caplog
) -> None:
    """A swallowed Redis error must be visible: WARNING once, plus a False return.

    Reporting it only at DEBUG made an outage indistinguishable from a healthy
    write and left the consuming daemon's degraded-state path unreachable.
    """
    monkeypatch.setattr(sep, "acquire_infra_clients", lambda: (_BrokenRedis(), None))
    monkeypatch.setattr(sep, "now_kst", lambda: _FIXED)

    with caplog.at_level("WARNING"):
        results = [
            sep.publish_setup_eval(
                "setup_d_vwap_reversion", "reject", f"not_extreme(z=+{i}.0,need±1.8)"
            )
            for i in range(5)
        ]

    assert results == [False] * 5, "every failed write must report False"
    warned = [r for r in caplog.records if "publish failed" in r.getMessage()]
    assert len(warned) == 1, [r.getMessage() for r in warned]
    assert "ConnectionError" in warned[0].getMessage()


def test_failure_latch_resets_after_a_success(
    monkeypatch: pytest.MonkeyPatch, clean_failure_latch: None, caplog
) -> None:
    """A second outage after a recovery must warn again."""
    broken = _BrokenRedis()
    healthy = fakeredis.FakeStrictRedis(decode_responses=True)
    client: list[object] = [broken]
    monkeypatch.setattr(sep, "acquire_infra_clients", lambda: (client[0], None))
    monkeypatch.setattr(sep, "now_kst", lambda: _FIXED)

    with caplog.at_level("WARNING"):
        assert (
            sep.publish_setup_eval("setup_a_gap_reversion", "reject", "no_atr") is False
        )
        client[0] = healthy
        assert (
            sep.publish_setup_eval("setup_a_gap_reversion", "reject", "no_atr") is True
        )
        client[0] = broken
        assert (
            sep.publish_setup_eval("setup_a_gap_reversion", "reject", "no_atr") is False
        )

    warned = [r for r in caplog.records if "publish failed" in r.getMessage()]
    assert len(warned) == 2, [r.getMessage() for r in warned]


def test_failure_latch_is_per_producer(
    monkeypatch: pytest.MonkeyPatch, clean_failure_latch: None, caplog
) -> None:
    """The shadow producer's outage must not silence the orchestrator's."""
    monkeypatch.setattr(sep, "acquire_infra_clients", lambda: (_BrokenRedis(), None))
    monkeypatch.setattr(sep, "now_kst", lambda: _FIXED)

    with caplog.at_level("WARNING"):
        sep.publish_setup_eval("setup_d_vwap_reversion", "reject", "no_atr")
        sep.publish_setup_eval(
            "setup_d_vwap_reversion", "reject", "no_atr", key_suffix=":shadow"
        )

    warned = [r for r in caplog.records if "publish failed" in r.getMessage()]
    assert len(warned) == 2, [r.getMessage() for r in warned]


def test_info_state_line_is_structural(
    redis_and_publisher: fakeredis.FakeStrictRedis, clean_failure_latch: None, caplog
) -> None:
    """A reason whose only change is its numbers is the SAME state — log once.

    This is the orchestrator path too: it previously logged one INFO per
    measurement for a cause that had not actually changed.
    """
    with caplog.at_level("INFO"):
        for z in ("+0.42", "+0.91", "+1.55"):
            sep.publish_setup_eval(
                "setup_d_vwap_reversion", "reject", f"not_extreme(z={z},need±1.8)"
            )
        sep.publish_setup_eval(
            "setup_d_vwap_reversion", "reject", "vol_below_gate(0.85<0.9)"
        )

    lines = [
        r.getMessage()
        for r in caplog.records
        if "no signal this cycle" in r.getMessage()
    ]
    assert len(lines) == 2, lines
