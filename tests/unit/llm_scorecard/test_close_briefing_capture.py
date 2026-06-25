"""Tests for the 15:30 close-briefing volume_surge scorecard capture hook."""

from __future__ import annotations

import json

import pytest

from scripts.analysis import llm_market_close_briefing as cb


class _FakeRedis:
    def __init__(self, value: str | None):
        self._value = value

    def get(self, key: str) -> str | None:
        assert key == "system:volume_surge:latest"
        return self._value


class _FakeLedger:
    def __init__(self, *_args, **_kwargs):
        self.saved: list[dict] = []

    def save_prediction(self, _date_kst, facet, _captured_at, payload, _confidence):
        self.saved.append({"facet": facet, "payload": payload})


@pytest.fixture
def patch_storage(monkeypatch):
    """Stub the runtime ledger + storage config so no SQLite file is touched."""
    led = _FakeLedger()
    monkeypatch.setattr(
        "shared.storage.runtime_ledger.SQLiteRuntimeLedger",
        lambda *_args, **_kwargs: led,
    )

    class _Storage:
        class runtime_storage:  # noqa: N801
            sqlite = ":memory:"

    monkeypatch.setattr(
        "shared.storage.config.StorageConfig.load_or_default",
        classmethod(lambda _cls: _Storage()),
    )
    return led


def _patch_redis(monkeypatch, value):
    monkeypatch.setattr(
        "shared.streaming.trading_state._get_redis",
        lambda: _FakeRedis(value),
    )


def test_captures_volume_surge_when_feed_present(monkeypatch, patch_storage):
    payload = {
        "generated_at": "2026-06-25T09:05:00+09:00",
        "date_kst": "2026-06-25",
        "surges": [
            {
                "code": "005930",
                "flag_time": "2026-06-25T09:05:00+09:00",
                "flag_price": 70000.0,
            },
        ],
    }
    _patch_redis(monkeypatch, json.dumps(payload))

    n = cb.capture_volume_surge_predictions()

    assert n == 1
    assert patch_storage.saved
    assert patch_storage.saved[0]["facet"] == "volume_surge"
    assert patch_storage.saved[0]["payload"]["surges"][0]["code"] == "005930"


def test_noop_when_feed_missing(monkeypatch, patch_storage):
    _patch_redis(monkeypatch, None)
    assert cb.capture_volume_surge_predictions() == 0
    assert patch_storage.saved == []


def test_noop_when_surges_empty(monkeypatch, patch_storage):
    _patch_redis(monkeypatch, json.dumps({"date_kst": "2026-06-25", "surges": []}))
    assert cb.capture_volume_surge_predictions() == 0
    assert patch_storage.saved == []


def test_best_effort_swallows_errors(monkeypatch):
    def _boom():
        raise RuntimeError("redis down")

    monkeypatch.setattr("shared.streaming.trading_state._get_redis", _boom)
    # Must not raise.
    assert cb.capture_volume_surge_predictions() == 0
