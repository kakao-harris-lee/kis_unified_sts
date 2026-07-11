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


def test_foreign_flow_missing_timestamp_treated_fresh(monkeypatch):
    collector = _collector(futures_structure_stale_seconds=3600)
    hash_fields = {"fut_foreign_net_qty": "5000"}  # no asof_ts
    monkeypatch.setattr(_GET_CLIENT, lambda: _FakeRedis(hash_fields))

    net, _cum20, missing = collector._collect_foreign_flow()

    assert net == 5000.0
    assert missing == []


# --------------------------------------------------------------------------- #
# _compute_flow_score directional sign
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("net", "expected"),
    [(8000.0, 5.0), (-8000.0, -5.0), (0.0, 0.0)],
)
def test_flow_score_foreign_sign(net, expected):
    score = FuturesFlowCollector._compute_flow_score(
        None, None, {}, foreign_futures=net, foreign_weight=5.0
    )
    assert score == expected


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
    assert flow_data.flow_score == 5.0  # only the +foreign_weight term contributes
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
