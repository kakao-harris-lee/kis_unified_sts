"""Tests for managed trading-universe dashboard endpoints."""

from __future__ import annotations

import importlib
import json
import logging
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _restore_universe_module():
    """Reload the universe route module under the real fastapi after each test.

    ``_client`` injects a fake ``fastapi`` into ``sys.modules`` and reloads
    ``services.dashboard.routes.universe`` under it, leaving the cached module
    with ``router`` bound to the fake ``_Router``. monkeypatch restores the
    ``fastapi`` entry, but not the reloaded module — a later ``create_app()``
    in the same process would then fail with ``'_Router' object has no
    attribute 'routes'``. Reloading in place (same module object) restores
    every existing reference, including the parent package attribute.
    """
    real_fastapi = sys.modules.get("fastapi")
    yield
    if real_fastapi is not None:
        sys.modules["fastapi"] = real_fastapi
    else:
        sys.modules.pop("fastapi", None)
    universe = sys.modules.get("services.dashboard.routes.universe")
    if universe is not None:
        importlib.reload(universe)


class _FakeRedis:
    def __init__(self, payloads: dict[str, object]) -> None:
        self.payloads = payloads
        self.expirations: dict[str, int] = {}
        self.lists: dict[str, list[str]] = {}

    def get(self, key: str) -> str | None:
        payload = self.payloads.get(key)
        if payload is None:
            return None
        return payload if isinstance(payload, str) else json.dumps(payload)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.payloads[key] = value
        if ex is not None:
            self.expirations[key] = ex

    def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds

    def lpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).insert(0, value)

    def ltrim(self, key: str, start: int, stop: int) -> None:
        self.lists[key] = self.lists.get(key, [])[start : stop + 1]

    def lrange(self, key: str, start: int, stop: int) -> list[str]:
        return self.lists.get(key, [])[start : stop + 1]


def _client(monkeypatch, payloads: dict[str, object]):
    fake_fastapi = types.ModuleType("fastapi")

    class _Router:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, *args, **kwargs):
            def _decorator(fn):
                return fn

            return _decorator

        def post(self, *args, **kwargs):
            def _decorator(fn):
                return fn

            return _decorator

    class _HTTPException(Exception):
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    def _query(default=None, **kwargs):
        return default

    fake_fastapi.APIRouter = _Router
    fake_fastapi.HTTPException = _HTTPException
    fake_fastapi.Query = _query
    monkeypatch.setitem(sys.modules, "fastapi", fake_fastapi)

    from services.dashboard.routes import universe

    importlib.reload(universe)
    fake = _FakeRedis(payloads)
    monkeypatch.setattr(universe, "_get_redis_client", lambda: fake)
    monkeypatch.setattr(universe, "_read_open_positions", lambda: ([], {}))
    return universe, fake


@pytest.mark.asyncio
async def test_universe_endpoint_builds_effective_snapshot(monkeypatch):
    universe, _fake = _client(
        monkeypatch,
        {
            "system:trade_targets:latest": {
                "codes": ["005930", "000660"],
                "names": {"005930": "삼성전자", "000660": "SK하이닉스"},
            },
            "system:daily_watchlist:latest": {
                "strategies": {"pattern_pullback": ["035720"]}
            },
            "system:daily_indicators:latest": {
                "indicators": {"005930": {}, "035720": {}}
            },
        },
    )

    body = await universe.get_trading_universe()

    assert body["codes"] == ["005930", "000660", "035720"]
    rows = {row["code"]: row for row in body["rows"]}
    assert rows["005930"]["name"] == "삼성전자"
    assert rows["000660"]["daily_indicator"] == "missing"


@pytest.mark.asyncio
async def test_universe_override_publishes_snapshot_and_audit(monkeypatch):
    universe, fake = _client(
        monkeypatch,
        {
            "system:trade_targets:latest": {
                "codes": ["005930", "000660"],
                "names": {"005930": "삼성전자", "000660": "SK하이닉스"},
            },
        },
    )

    body = await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(
            action="exclude",
            symbol="000660",
            name="SK하이닉스",
            reason="manual risk block",
            ttl_seconds=3600,
        )
    )

    assert body["codes"] == ["005930"]

    overrides = json.loads(fake.payloads["stock:universe:overrides"])
    assert "000660" in overrides["manual_exclude"]
    effective = json.loads(fake.payloads["stock:universe:effective:latest"])
    assert effective["codes"] == ["005930"]
    assert 0 < fake.expirations["stock:universe:effective:latest"] <= 3600
    assert fake.lists["stock:universe:audit"]

    audit_response = await universe.get_trading_universe_audit()
    assert audit_response["events"][0]["symbol"] == "000660"


@pytest.mark.asyncio
async def test_include_override_is_permanent_by_default(monkeypatch):
    universe, fake = _client(
        monkeypatch,
        {
            "system:trade_targets:latest": {
                "codes": ["005930"],
                "names": {"005930": "삼성전자"},
            },
        },
    )

    body = await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(
            action="include",
            symbol="000660",
            name="SK하이닉스",
        )
    )

    assert "000660" in body["codes"]
    overrides = json.loads(fake.payloads["stock:universe:overrides"])
    entry = overrides["manual_include"]["000660"]
    # Permanent: no expiry stamped.
    assert entry.get("expires_at") is None
    # Overrides key must not silently expire permanent picks.
    assert "stock:universe:overrides" not in fake.expirations


@pytest.mark.asyncio
async def test_include_override_honors_explicit_ttl(monkeypatch):
    universe, fake = _client(monkeypatch, {})

    await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(
            action="include",
            symbol="000660",
            ttl_seconds=3600,
        )
    )

    overrides = json.loads(fake.payloads["stock:universe:overrides"])
    entry = overrides["manual_include"]["000660"]
    assert entry.get("expires_at") is not None  # explicit TTL still respected
    # Key TTL should cover the requested horizon (not truncate it).
    assert fake.expirations["stock:universe:overrides"] >= 3600


@pytest.mark.asyncio
async def test_include_override_allows_missing_reason(monkeypatch):
    universe, fake = _client(monkeypatch, {})

    body = await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(action="include", symbol="000660")
    )

    assert "000660" in body["codes"]  # no reason_required error


@pytest.mark.asyncio
async def test_override_rejects_when_limit_reached(monkeypatch):
    monkeypatch.setenv("STOCK_UNIVERSE_MAX_OVERRIDES", "2")
    universe, _fake = _client(monkeypatch, {})

    await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(action="include", symbol="000660")
    )
    await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(action="include", symbol="005930")
    )

    with pytest.raises(universe.HTTPException) as excinfo:
        await universe.update_trading_universe_override(
            universe.UniverseOverrideRequest(action="include", symbol="035720")
        )
    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == "override_limit_reached"


@pytest.mark.asyncio
async def test_override_update_existing_allowed_at_limit(monkeypatch):
    monkeypatch.setenv("STOCK_UNIVERSE_MAX_OVERRIDES", "2")
    universe, _fake = _client(monkeypatch, {})

    await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(action="include", symbol="000660")
    )
    await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(action="include", symbol="005930")
    )

    # Re-including an already-present symbol is an update, not a new entry —
    # must not be blocked by the cap.
    body = await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(
            action="include", symbol="000660", reason="updated note"
        )
    )
    assert "000660" in body["codes"]


@pytest.mark.asyncio
async def test_override_remove_not_blocked_by_limit(monkeypatch):
    monkeypatch.setenv("STOCK_UNIVERSE_MAX_OVERRIDES", "2")
    universe, _fake = _client(monkeypatch, {})

    await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(action="include", symbol="000660")
    )
    await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(action="include", symbol="005930")
    )

    # At the cap, removing an existing entry must always be allowed.
    body = await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(action="remove", symbol="000660")
    )
    assert "000660" not in body["codes"]


@pytest.mark.asyncio
async def test_permanent_include_without_reason_logs_warning(monkeypatch, caplog):
    universe, _fake = _client(monkeypatch, {})

    with caplog.at_level(logging.WARNING, logger="services.dashboard.routes.universe"):
        await universe.update_trading_universe_override(
            universe.UniverseOverrideRequest(action="include", symbol="000660")
        )

    assert any(
        record.levelno == logging.WARNING and "000660" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_include_with_reason_no_warning(monkeypatch, caplog):
    universe, _fake = _client(monkeypatch, {})

    with caplog.at_level(logging.WARNING, logger="services.dashboard.routes.universe"):
        await universe.update_trading_universe_override(
            universe.UniverseOverrideRequest(
                action="include", symbol="000660", reason="operator pick"
            )
        )

    assert not any(record.levelno == logging.WARNING for record in caplog.records)


@pytest.mark.asyncio
async def test_temporary_include_without_reason_no_warning(monkeypatch, caplog):
    """Only *permanent* reason-less includes are worth flagging."""
    universe, _fake = _client(monkeypatch, {})

    with caplog.at_level(logging.WARNING, logger="services.dashboard.routes.universe"):
        await universe.update_trading_universe_override(
            universe.UniverseOverrideRequest(
                action="include", symbol="000660", ttl_seconds=3600
            )
        )

    assert not any(record.levelno == logging.WARNING for record in caplog.records)


@pytest.mark.asyncio
async def test_resolve_returns_known_name(monkeypatch):
    universe, _fake = _client(
        monkeypatch,
        {
            "system:trade_targets:latest": {
                "codes": ["005930"],
                "names": {"005930": "삼성전자"},
            },
        },
    )

    body = await universe.resolve_universe_symbol(code="005930")

    assert body == {"code": "005930", "name": "삼성전자", "known": True}


@pytest.mark.asyncio
async def test_resolve_returns_pending_for_unknown_code(monkeypatch):
    universe, _fake = _client(monkeypatch, {})

    body = await universe.resolve_universe_symbol(code="123456")

    assert body == {"code": "123456", "name": None, "known": False}


@pytest.mark.asyncio
async def test_resolve_rejects_bad_code(monkeypatch):
    universe, _fake = _client(monkeypatch, {})

    with pytest.raises(universe.HTTPException) as excinfo:
        await universe.resolve_universe_symbol(code="12ab")
    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
async def test_resolve_rejects_full_width_digits(monkeypatch):
    """Full-width/Unicode digits must not falsely satisfy the 6-digit check."""
    universe, _fake = _client(monkeypatch, {})

    with pytest.raises(universe.HTTPException) as excinfo:
        # U+FF10..U+FF15 = full-width "005930"
        await universe.resolve_universe_symbol(code="００５９３０")
    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "redis_key",
    [
        "system:universe:latest",  # screener_universe
        "system:daily_watchlist:latest",  # daily_watchlist
        "system:theme_targets:latest",  # theme_targets
        "system:daily_indicators:latest",  # daily_indicators
    ],
)
async def test_resolve_finds_name_in_each_raw_source(monkeypatch, redis_key):
    """Every raw source key feeds the name map, not just trade_targets.

    Uses the ``names`` dict shape ``extract_names`` understands. Note: of
    these four, only screener_universe (services/screener.py) and
    theme_targets (services/theme_discovery.py) actually publish a ``names``
    dict in production today. daily_watchlist (services/daily_scanner.py,
    scripts/daily_indicator_scanner.py's compat payload) and daily_indicators
    (scripts/daily_indicator_scanner.py) currently publish only scoring
    diagnostics under ``metadata`` (e.g. ``trade_trend_priority``), with no
    ``name``/``stock_name``/``prdt_name`` field — so in practice those two
    keys never carry a resolvable name today. This test still proves
    ``_build_name_map`` wires every source key through ``extract_names``
    correctly, independent of what today's producers happen to publish.
    """
    universe, _fake = _client(
        monkeypatch,
        {
            redis_key: {
                "codes": ["005930"],
                "names": {"005930": "삼성전자"},
            },
        },
    )

    body = await universe.resolve_universe_symbol(code="005930")

    assert body == {"code": "005930", "name": "삼성전자", "known": True}


@pytest.mark.asyncio
async def test_resolve_prefers_trade_targets_over_screener_universe(monkeypatch):
    """Merge order must match ``_merge_names``: trade_targets wins first."""
    universe, _fake = _client(
        monkeypatch,
        {
            "system:trade_targets:latest": {
                "codes": ["005930"],
                "names": {"005930": "삼성전자(fusion)"},
            },
            "system:universe:latest": {
                "codes": ["005930"],
                "names": {"005930": "삼성전자(screener)"},
            },
        },
    )

    body = await universe.resolve_universe_symbol(code="005930")

    assert body == {"code": "005930", "name": "삼성전자(fusion)", "known": True}


@pytest.mark.asyncio
async def test_resolve_finds_name_from_open_positions(monkeypatch):
    universe, _fake = _client(monkeypatch, {})
    monkeypatch.setattr(
        universe,
        "_read_open_positions",
        lambda: (["005930"], {"005930": "삼성전자"}),
    )

    body = await universe.resolve_universe_symbol(code="005930")

    assert body == {"code": "005930", "name": "삼성전자", "known": True}


@pytest.mark.asyncio
async def test_resolve_finds_name_from_manual_include_override(monkeypatch):
    universe, fake = _client(monkeypatch, {})
    fake.payloads["stock:universe:overrides"] = {
        "manual_include": {
            "005930": {
                "reason": "",
                "created_at": "2026-01-01T00:00:00+00:00",
                "expires_at": None,
                "operator": None,
                "name": "삼성전자",
            }
        },
        "manual_exclude": {},
        "updated_at": "2026-01-01T00:00:00+00:00",
    }

    body = await universe.resolve_universe_symbol(code="005930")

    assert body == {"code": "005930", "name": "삼성전자", "known": True}


def test_merge_names_is_importable_from_package():
    """``merge_names`` is the shared single source of merge-order truth.

    universe.py's ``_build_name_map`` and effective.py's
    ``build_effective_universe_snapshot`` must both delegate to this one
    function via the public package surface, not a private duplicate.
    """
    from shared.stock_universe import merge_names

    assert (
        merge_names(
            {"names": {"005930": "삼성전자(a)"}},
            {"names": {"005930": "삼성전자(b)"}},
        )
        == {"005930": "삼성전자(a)"}
    )
