"""Foreign-futures flow sourcing for the LLM flow collector (P5-2).

Covers ``FuturesFlowCollector`` reading the ``market:structure:latest`` read-model
(``fut_foreign_net_qty`` / ``fut_foreign_net_qty_cum20``) and reflecting it in the
flow score, plus graceful degradation when the source is absent/stale/unreachable.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shared.llm.config import LLMConfig
from shared.llm.futures_flow_collector import FuturesFlowCollector

_GET_CLIENT = "shared.llm.futures_flow_collector.RedisClient.get_client"


def _collector(**cfg_overrides) -> FuturesFlowCollector:
    # Empty krx_api_key keeps basis/put-call out of the network path.
    cfg = LLMConfig(krx_api_key="", **cfg_overrides)
    return FuturesFlowCollector(config=cfg)


class _FakeRedis:
    """Minimal fake exposing hgetall (foreign flow) + xrevrange (microstructure)."""

    def __init__(self, hash_fields: dict[str, str] | None, *, raise_on_hget=False):
        self._hash = hash_fields
        self._raise = raise_on_hget

    def hgetall(self, _key):
        if self._raise:
            raise ConnectionError("redis down")
        return dict(self._hash) if self._hash is not None else {}

    def xrevrange(self, *_args, **_kwargs):
        return []


def _fresh_hash(net="12000", cum20="45000") -> dict[str, str]:
    fields = {"asof_ts": datetime.now().isoformat()}
    if net is not None:
        fields["fut_foreign_net_qty"] = net
    if cum20 is not None:
        fields["fut_foreign_net_qty_cum20"] = cum20
    return fields


# --------------------------------------------------------------------------- #
# _collect_foreign_flow
# --------------------------------------------------------------------------- #
def test_foreign_flow_present_fills_net_and_cum20(monkeypatch):
    collector = _collector()
    monkeypatch.setattr(_GET_CLIENT, lambda: _FakeRedis(_fresh_hash("12000", "45000")))

    net, cum20, missing = collector._collect_foreign_flow()

    assert net == 12000.0
    assert cum20 == 45000.0
    assert missing == []


def test_foreign_flow_absent_hash_degrades(monkeypatch):
    collector = _collector()
    monkeypatch.setattr(_GET_CLIENT, lambda: _FakeRedis({}))

    net, cum20, missing = collector._collect_foreign_flow()

    assert net is None
    assert cum20 is None
    assert missing == ["foreign_futures_unavailable"]


def test_foreign_flow_redis_error_degrades(monkeypatch):
    collector = _collector()
    monkeypatch.setattr(
        _GET_CLIENT, lambda: _FakeRedis(_fresh_hash(), raise_on_hget=True)
    )

    net, cum20, missing = collector._collect_foreign_flow()

    assert (net, cum20) == (None, None)
    assert missing == ["foreign_futures_unavailable"]


def test_foreign_flow_stale_snapshot_degrades(monkeypatch):
    collector = _collector(futures_structure_stale_seconds=3600)
    stale = {
        "fut_foreign_net_qty": "8000",
        "fut_foreign_net_qty_cum20": "20000",
        "asof_ts": (datetime.now() - timedelta(days=2)).isoformat(),
    }
    monkeypatch.setattr(_GET_CLIENT, lambda: _FakeRedis(stale))

    net, cum20, missing = collector._collect_foreign_flow()

    assert (net, cum20) == (None, None)
    assert missing == ["foreign_futures_stale"]


def test_foreign_flow_field_present_but_empty(monkeypatch):
    collector = _collector()
    hash_fields = {
        "fut_foreign_net_qty": "",  # source published the row but net missing
        "fut_foreign_net_qty_cum20": "30000",
        "asof_ts": datetime.now().isoformat(),
    }
    monkeypatch.setattr(_GET_CLIENT, lambda: _FakeRedis(hash_fields))

    net, cum20, missing = collector._collect_foreign_flow()

    assert net is None
    assert cum20 == 30000.0
    assert missing == ["foreign_futures"]


def test_foreign_flow_missing_timestamp_treated_stale(monkeypatch):
    # #458 positive-form (F3): a hash with no asof_ts is treated as STALE
    # (degrade to None), never as fresh — a corrupt/legacy timestamp-less
    # snapshot can't push a days-old net into the score as if it were live.
    collector = _collector(futures_structure_stale_seconds=3600)
    hash_fields = {"fut_foreign_net_qty": "5000"}  # no asof_ts
    monkeypatch.setattr(_GET_CLIENT, lambda: _FakeRedis(hash_fields))

    net, cum20, missing = collector._collect_foreign_flow()

    assert (net, cum20) == (None, None)
    assert missing == ["foreign_futures_stale"]


def test_foreign_flow_unparseable_timestamp_treated_stale(monkeypatch):
    # A present-but-garbage asof_ts must also degrade to stale, not fresh.
    collector = _collector(futures_structure_stale_seconds=3600)
    hash_fields = {"fut_foreign_net_qty": "5000", "asof_ts": "not-a-timestamp"}
    monkeypatch.setattr(_GET_CLIENT, lambda: _FakeRedis(hash_fields))

    net, cum20, missing = collector._collect_foreign_flow()

    assert (net, cum20) == (None, None)
    assert missing == ["foreign_futures_stale"]


def test_foreign_flow_missing_timestamp_fresh_when_gate_disabled(monkeypatch):
    # Staleness gate off (stale_seconds <= 0) → nothing is ever stale, even
    # without a timestamp; the value still reads through.
    collector = _collector(futures_structure_stale_seconds=0)
    hash_fields = {"fut_foreign_net_qty": "5000"}  # no asof_ts
    monkeypatch.setattr(_GET_CLIENT, lambda: _FakeRedis(hash_fields))

    net, _cum20, missing = collector._collect_foreign_flow()

    assert net == 5000.0
    assert missing == []


# --------------------------------------------------------------------------- #
# _compute_flow_score foreign term: deadband + bounded linear scale (F1)
# --------------------------------------------------------------------------- #
_DEADBAND = 2000.0
_FULL_SCALE = 15000.0
_WEIGHT = 5.0


def _foreign_score(net: float) -> float:
    return FuturesFlowCollector._compute_flow_score(
        None,
        None,
        {},
        foreign_futures=net,
        foreign_weight=_WEIGHT,
        foreign_deadband=_DEADBAND,
        foreign_full_scale=_FULL_SCALE,
    )


@pytest.mark.parametrize("net", [0.0, 1000.0, 2000.0, -1500.0, -2000.0])
def test_flow_score_foreign_deadband_zero_at_or_below_threshold(net):
    # |net| at/below the deadband contributes nothing — noise-level foreign net
    # can no longer flip a near-zero flow_score (the sign-only saturation bug).
    assert _foreign_score(net) == 0.0


@pytest.mark.parametrize(
    ("net", "expected"),
    [
        # linear ramp between deadband and full_scale, symmetric in sign
        (8000.0, (8000.0 - _DEADBAND) / (_FULL_SCALE - _DEADBAND) * _WEIGHT),
        (-8000.0, -(8000.0 - _DEADBAND) / (_FULL_SCALE - _DEADBAND) * _WEIGHT),
        # reaches the full ±weight exactly at full_scale, then saturates (bounded)
        (15000.0, 5.0),
        (30000.0, 5.0),
        (-30000.0, -5.0),
    ],
)
def test_flow_score_foreign_scaled_and_bounded(net, expected):
    assert _foreign_score(net) == pytest.approx(expected)


def test_flow_score_foreign_monotonic_in_magnitude():
    # Larger net → larger |contribution| (until saturation), unlike sign-only.
    assert abs(_foreign_score(9000.0)) > abs(_foreign_score(4000.0)) > 0.0


def test_flow_score_foreign_degenerate_config_falls_back_to_sign():
    # deadband/full_scale left at the 0.0 defaults (caller did not thread config)
    # → sign-only above the zero deadband, never a divide-by-zero.
    score = FuturesFlowCollector._compute_flow_score(
        None, None, {}, foreign_futures=8000.0, foreign_weight=5.0
    )
    assert score == 5.0


def test_flow_score_backward_compatible_without_foreign():
    # Existing callers (and micro-only paths) must be unchanged.
    score = FuturesFlowCollector._compute_flow_score(
        basis=0.5, put_call=1.2, micro_data={"microstructure_score": 2.5}
    )
    assert score == 2.5


# --------------------------------------------------------------------------- #
# collect() integration + missing-marker cleanup
# --------------------------------------------------------------------------- #
def test_collect_reflects_foreign_flow_and_drops_legacy_marker(monkeypatch):
    collector = _collector()
    monkeypatch.setattr(_GET_CLIENT, lambda: _FakeRedis(_fresh_hash("9000", "30000")))

    flow_data, missing = collector.collect()

    assert flow_data is not None
    assert flow_data.foreign_futures == 9000.0
    assert flow_data.foreign_futures_cum20 == 30000.0
    assert flow_data.foreign_futures_5d is None  # no 5d source in market:structure
    assert flow_data.institution_futures is None  # out of scope, no source
    # Only the foreign term contributes; deadband+scale (net 9000, deadband 2000,
    # full_scale 15000, weight 5.0): (9000-2000)/13000 * 5 = 2.69 → round(,1)=2.7.
    assert flow_data.flow_score == pytest.approx(2.7)
    # legacy always-on marker gone; foreign present so no foreign degrade marker
    assert "investor_flow_excluded" not in missing
    assert "foreign_futures_unavailable" not in missing
    assert "foreign_futures" not in missing


def test_collect_returns_none_when_all_sources_absent(monkeypatch):
    collector = _collector()
    monkeypatch.setattr(_GET_CLIENT, lambda: _FakeRedis({}))

    flow_data, missing = collector.collect()

    assert flow_data is None
    assert "foreign_futures_unavailable" in missing
    assert "investor_flow_excluded" not in missing


# --------------------------------------------------------------------------- #
# _parse_structure_asof tz handling (#593, F4)
# --------------------------------------------------------------------------- #
def test_parse_asof_tzaware_utc_converted_to_kst():
    # A tz-aware UTC asof must be converted to KST before the tz strip; a naive
    # strip would keep the UTC wall clock and skew the age by +9h.
    from datetime import UTC

    utc = datetime(2026, 7, 12, 1, 0, 0, tzinfo=UTC)  # == 10:00 KST
    parsed = FuturesFlowCollector._parse_structure_asof(utc.isoformat())

    assert parsed == datetime(2026, 7, 12, 10, 0, 0)  # KST-naive, host-TZ agnostic


def test_parse_asof_naive_passthrough():
    naive = datetime(2026, 7, 12, 10, 0, 0)
    assert FuturesFlowCollector._parse_structure_asof(naive.isoformat()) == naive


@pytest.mark.parametrize("value", ["not-a-timestamp", "", None])
def test_parse_asof_unparseable_returns_none(value):
    assert FuturesFlowCollector._parse_structure_asof(value) is None


def test_structure_fresh_utc_asof_reads_fresh_after_kst_conversion(monkeypatch):
    # A UTC-tagged asof for the *current* instant must read FRESH (age ~0) after
    # KST conversion; the pre-fix naive strip would make it look ~9h stale.
    from datetime import UTC

    collector = _collector(futures_structure_stale_seconds=3600)
    hash_fields = {
        "fut_foreign_net_qty": "5000",
        "asof_ts": datetime.now(UTC).isoformat(),
    }
    monkeypatch.setattr(_GET_CLIENT, lambda: _FakeRedis(hash_fields))

    net, _cum20, missing = collector._collect_foreign_flow()

    assert net == 5000.0
    assert missing == []
