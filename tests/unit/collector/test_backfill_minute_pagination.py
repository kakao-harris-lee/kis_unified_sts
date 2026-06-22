"""Tests for fetch_minute_async pagination retry on HTTP 500 / rt_cd != '0'.

Covers:
- Page 2 returns rt_cd != '0' twice then 200-with-rows → all pages collected (> 102 bars).
- Page 2 error persists past page_max_retries → loop breaks, returns gathered pages, no raise.
- A normal empty/last page still terminates without spurious retries.
"""

from __future__ import annotations

import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock


def _get_backfill_module():
    """Import the actual module (not the __init__ re-export which is a function)."""
    return importlib.import_module("shared.collector.historical.backfill")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(payload: dict | None = None) -> MagicMock:
    """Build a fake httpx response."""
    import json

    resp = MagicMock()
    if payload is None:
        resp.text = ""
        resp.json.return_value = {}
    else:
        resp.text = json.dumps(payload)
        resp.json.return_value = payload
    return resp


def _page_payload(rows: list[dict]) -> dict:
    return {"rt_cd": "0", "output2": rows}


def _error_payload() -> dict:
    """KIS-style error with rt_cd != '0'."""
    return {"rt_cd": "9", "msg1": "Internal error"}


def _make_rows(start: int, count: int) -> list[dict]:
    """Generate `count` dummy 1-min bar dicts, each with a unique stck_cntg_hour."""
    rows = []
    for i in range(count):
        hour = f"{(start + i):06d}"
        rows.append(
            {
                "stck_cntg_hour": hour,
                "futs_oprc": "380.0",
                "futs_hgpr": "381.0",
                "futs_lwpr": "379.5",
                "futs_prpr": "380.5",
                "cntg_vol": "100",
            }
        )
    return rows


def _patch_backfill_infra(monkeypatch, mod):
    """Neutralise token/rate-limiter/semaphore so tests don't need real KIS creds."""
    monkeypatch.setattr(
        mod, "_get_token", lambda domain="futures": MagicMock(get=lambda: "tok")
    )
    monkeypatch.setattr(mod, "_get_semaphore", lambda: asyncio.Semaphore(10))
    monkeypatch.setattr(mod, "_get_rate_limiter", lambda: MagicMock(wait=AsyncMock()))

    from shared.config.secrets import SecretsManager

    monkeypatch.setattr(
        SecretsManager, "kis_app_key", lambda self_or_cls, domain="futures": "k"
    )
    monkeypatch.setattr(
        SecretsManager, "kis_app_secret", lambda self_or_cls, domain="futures": "s"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_page2_error_twice_then_200_collects_all_pages(monkeypatch):
    """Page 2 returns rt_cd='9' twice, then succeeds.

    All rows from page 1 AND page 2 must be present — pagination retry works.
    """
    mod = _get_backfill_module()
    _patch_backfill_infra(monkeypatch, mod)

    # 102 rows on page 1 (KIS per-call max), 100 rows on page 2
    page1_rows = _make_rows(start=100000, count=102)
    page2_rows = _make_rows(start=200000, count=100)

    page1_payload = _page_payload(page1_rows)
    error_payload = _error_payload()
    page2_payload = _page_payload(page2_rows)

    call_count = {"n": 0}

    async def fake_get(url, *, headers=None, params=None):
        call_count["n"] += 1
        n = call_count["n"]
        if n == 1:
            return _make_response(page1_payload)
        elif n in (2, 3):
            return _make_response(error_payload)
        else:
            return _make_response(page2_payload)

    client = MagicMock()
    client.get = AsyncMock(side_effect=fake_get)

    code, date_str, result = asyncio.run(
        mod.fetch_minute_async(client, "A05601", "20260601")
    )

    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    rows = result.get("output2", [])
    # page1 (102) + page2 (100) = 202 total
    assert (
        len(rows) > 102
    ), f"Expected > 102 rows (page-2 retry not working); got {len(rows)}"
    assert len(rows) >= 200, f"Expected ~202 rows, got {len(rows)}"


def test_page2_error_persists_past_page_max_retries_returns_partial(monkeypatch):
    """Page 2 always errors → loop breaks, returns page-1 rows only, does NOT raise."""
    mod = _get_backfill_module()
    _patch_backfill_infra(monkeypatch, mod)

    page1_rows = _make_rows(start=100000, count=102)
    page1_payload = _page_payload(page1_rows)
    error_payload = _error_payload()

    call_count = {"n": 0}

    async def fake_get(url, *, headers=None, params=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _make_response(page1_payload)
        return _make_response(error_payload)

    client = MagicMock()
    client.get = AsyncMock(side_effect=fake_get)

    # Must not raise
    code, date_str, result = asyncio.run(
        mod.fetch_minute_async(client, "A05601", "20260601")
    )

    assert (
        "error" not in result
    ), f"Unexpected top-level error after exhausted retries: {result}"
    rows = result.get("output2", [])
    assert len(rows) == 102, f"Expected 102 rows (page 1 only), got {len(rows)}"

    # Total calls = 1 (page1) + PAGE_MAX_RETRIES (page2 retry exhaustion)
    page_max_retries = mod.PAGE_MAX_RETRIES
    assert (
        call_count["n"] == 1 + page_max_retries
    ), f"Expected {1 + page_max_retries} calls; got {call_count['n']}"


def test_empty_last_page_terminates_without_spurious_retries(monkeypatch):
    """An empty page 2 (genuine end-of-data) terminates immediately — no retry."""
    mod = _get_backfill_module()
    _patch_backfill_infra(monkeypatch, mod)

    page1_rows = _make_rows(start=100000, count=50)
    page1_payload = _page_payload(page1_rows)
    empty_payload = _page_payload([])  # rt_cd='0' but empty output2

    call_count = {"n": 0}

    async def fake_get(url, *, headers=None, params=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _make_response(page1_payload)
        return _make_response(empty_payload)

    client = MagicMock()
    client.get = AsyncMock(side_effect=fake_get)

    code, date_str, result = asyncio.run(
        mod.fetch_minute_async(client, "A05601", "20260601")
    )

    assert "error" not in result
    rows = result.get("output2", [])
    assert len(rows) == 50

    # Exactly 2 HTTP calls: page 1 + page 2 (empty → terminate, zero retries)
    assert (
        call_count["n"] == 2
    ), f"Expected exactly 2 HTTP calls (page1 + empty page2), got {call_count['n']}"
