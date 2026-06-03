"""CLI glue coverage for services.macro_overnight_collector.main.

The integration test covers collect_us_session / collect_fx_session
business logic; these tests cover the _cli() dispatch + main() wrapper.
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest

from services.macro_overnight_collector.main import _cli, main
from shared.macro.base import MacroSnapshot


def _snap(session: str) -> MacroSnapshot:
    return MacroSnapshot(
        ts_ms=1_700_000_000_000,
        session=session,
        sp500_close=5000.0 if session.startswith("overnight_us") else None,
        usdkrw=1355.0 if session == "overnight_fx" else None,
        collected_from=["yahoo" if "us" in session else "ecos"],
    )


@pytest.fixture(autouse=True)
def _patch_external_clients(monkeypatch):
    """Shared monkeypatches: fake Redis, AsyncMock CH, pass-through config."""
    monkeypatch.setattr(
        "redis.asyncio.from_url",
        lambda *_a, **_kw: fakeredis.aioredis.FakeRedis(),
    )
    fake_ch = AsyncMock()
    monkeypatch.setattr(
        "shared.db.client.AsyncClickHouseClient",
        lambda *_a, **_kw: fake_ch,
    )
    monkeypatch.setattr(
        "shared.db.config.ClickHouseConfig.from_env",
        classmethod(lambda _cls, database=None: MagicMock()),  # noqa: ARG005
    )
    from shared.macro.config import MacroCollectorConfig

    monkeypatch.setattr(
        "shared.macro.config.MacroCollectorConfig.from_yaml",
        classmethod(lambda _cls, *_a, **_kw: MacroCollectorConfig()),
    )
    return fake_ch


@pytest.mark.asyncio
async def test_cli_us_session_runs_and_closes_mirror_client(
    monkeypatch, _patch_external_clients
):
    monkeypatch.setenv("RUNTIME_STORAGE_CLICKHOUSE_MIRROR_ENABLED", "true")
    yahoo_stub = MagicMock()
    yahoo_stub.fetch_us_close_snapshot = AsyncMock(
        return_value=_snap("overnight_us_close")
    )
    monkeypatch.setattr(
        "shared.macro.sources.yahoo.YahooMacroSource",
        lambda *_a, **_kw: yahoo_stub,
    )

    rc = await _cli("us")

    assert rc == 0
    yahoo_stub.fetch_us_close_snapshot.assert_awaited_once()
    _patch_external_clients.connect.assert_awaited()
    _patch_external_clients.close.assert_awaited()


@pytest.mark.asyncio
async def test_cli_us_session_skips_clickhouse_when_mirror_disabled(
    monkeypatch, _patch_external_clients
):
    monkeypatch.delenv("RUNTIME_STORAGE_CLICKHOUSE_MIRROR_ENABLED", raising=False)
    yahoo_stub = MagicMock()
    yahoo_stub.fetch_us_close_snapshot = AsyncMock(
        return_value=_snap("overnight_us_close")
    )
    monkeypatch.setattr(
        "shared.macro.sources.yahoo.YahooMacroSource",
        lambda *_a, **_kw: yahoo_stub,
    )

    rc = await _cli("us")

    assert rc == 0
    yahoo_stub.fetch_us_close_snapshot.assert_awaited_once()
    _patch_external_clients.connect.assert_not_awaited()
    _patch_external_clients.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_cli_fx_session_runs_with_ecos_key(monkeypatch, _patch_external_clients):
    monkeypatch.setenv("ECOS_API_KEY", "test-key")

    ecos_stub = MagicMock()
    ecos_stub.fetch_fx_snapshot = AsyncMock(return_value=_snap("overnight_fx"))

    def _make_ecos(*args, **kwargs):
        return ecos_stub

    monkeypatch.setattr("shared.macro.sources.ecos.ECOSSource", _make_ecos)

    # aiohttp.ClientSession is used as async context manager in _cli for fx
    class _FakeAioSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr("aiohttp.ClientSession", lambda: _FakeAioSession())

    rc = await _cli("fx")

    assert rc == 0
    ecos_stub.fetch_fx_snapshot.assert_awaited_once()


@pytest.mark.asyncio
async def test_cli_unknown_session_returns_2(_patch_external_clients):
    rc = await _cli("bogus")
    assert rc == 2


def test_main_us_session_invokes_cli(monkeypatch):
    captured = {}

    async def fake_cli(kind):
        captured["kind"] = kind
        return 0

    monkeypatch.setattr("services.macro_overnight_collector.main._cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["macro_overnight_collector", "us"])

    rc = main()
    assert rc == 0
    assert captured["kind"] == "us"
