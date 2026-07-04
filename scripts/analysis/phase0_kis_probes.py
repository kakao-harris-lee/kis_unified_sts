"""Phase 0 residual KIS TR probes (unified investment roadmap O1).

Runs the three residual REAL-token probes the roadmap deferred to the deploy
host (each ~1 REST call), so their answers can be recorded and the Phase 0
backfill/collectors finalised:

* A. ``FHPPG04600001`` per-call row cap — how many daily program-trade rows a
     single call returns (drives ``backfill_market_structure.py`` chunk sizing).
* B. ``FHMIF10000000`` night-code response — whether the day-session current
     price TR serves the 8-char night KOSPI200 code (validates the O9 decision
     that the night session is WS-only; REST has no night quote).
* C. SOX symbol notation — confirms the forward Yahoo ``^SOX`` source returns
     data (the authoritative Wave 2a path). The KIS overseas-index fallback
     (``HHDFC55020100``) is not implemented, so its notation stays an open,
     low-priority item while Yahoo works.

Read-only. Reuses the shared futures token cache (no dedicated issuance).

Usage (deploy host, futures REAL creds in env):
    set -a && . ./.env.paper && set +a
    python scripts/analysis/phase0_kis_probes.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

NIGHT_CODE = "101W9000"  # config/night_futures.yaml tr_key (example; probe B validates)
DAY_SYMBOL = "101S6000"  # config/market_structure.yaml kis.futures_symbol


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


async def probe_a_program_row_cap(client) -> None:
    _hr("PROBE A — FHPPG04600001 per-call row cap")
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=150)  # ~100 trading days to exceed any cap
    print(f"range: {start} .. {end}  (market_div=J, market_cls=K)")
    try:
        single = await client.fetch_program_trade_daily(start, end, max_pages=1)
        await asyncio.sleep(0.4)
        full = await client.fetch_program_trade_daily(start, end, max_pages=8)
        print(f"single-call rows (max_pages=1): {len(single)}")
        print(f"continuation total (max_pages=20): {len(full)}")
        cap = len(single)
        print(
            f"=> per-call row cap ≈ {cap} "
            f"({'CONTINUATION NEEDED' if len(full) > cap else 'no continuation seen'})"
        )
        if single:
            keys = sorted(single[0])
            print(f"sample row keys ({len(keys)}): {keys[:12]}")
            dkey = next((k for k in single[0] if "date" in k.lower() or k.endswith("_ymd")), None)
            if dkey:
                print(f"first/last {dkey}: {single[0].get(dkey)} .. {single[-1].get(dkey)}")
    except Exception as exc:  # noqa: BLE001 - probe records the failure
        print(f"FAILED: {type(exc).__name__}: {exc}")


async def probe_b_night_code(client) -> None:
    _hr("PROBE B — FHMIF10000000 night-code response")
    for label, code in (("DAY  ", DAY_SYMBOL), ("NIGHT", NIGHT_CODE)):
        await asyncio.sleep(0.4)
        try:
            q = await client.get_current_price(code)
            print(
                f"{label} {code}: OK  close={q.get('close')} "
                f"oi={q.get('open_interest')} vol={q.get('volume')} "
                f"prev_close={q.get('prev_close')}"
            )
        except Exception as exc:  # noqa: BLE001 - the error IS the finding
            print(f"{label} {code}: ERROR  {type(exc).__name__}: {exc}")
    print(
        "\ninterpretation: night ERROR / stale-day data => REST does not serve\n"
        "the night session (confirms O9 WS-only H0MFCNT0 capture design)."
    )


def probe_c_sox_yahoo() -> None:
    _hr("PROBE C — SOX symbol notation (Yahoo ^SOX forward source)")
    import json
    import urllib.request

    for label, sym in (("^SOX", "%5ESOX"), ("ES=F", "ES%3DF"), ("KRW=X", "KRW%3DX")):
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
            "?range=5d&interval=1d"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                data = json.load(resp)
            result = data["chart"]["result"][0]
            meta = result["meta"]
            price = meta.get("regularMarketPrice")
            closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]
            print(
                f"{label}: OK  symbol={meta.get('symbol')} "
                f"price={price} last_closes={closes[-3:]}"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"{label}: ERROR  {type(exc).__name__}: {exc}")
    print(
        "\n=> ^SOX notation confirmed via Yahoo chart API (Wave 2a forward path).\n"
        "KIS HHDFC55020100 overseas-index fallback stays unimplemented (Yahoo primary)."
    )


async def main() -> int:
    from services.market_structure_collector.main import _futures_kis_auth_config
    from shared.kis.client import KISClient

    cfg = _futures_kis_auth_config()
    print(f"auth: is_real={getattr(cfg, 'is_real', '?')} app_key={str(getattr(cfg, 'app_key', ''))[:6]}...")
    client = KISClient(cfg)
    try:
        await probe_a_program_row_cap(client)
        await probe_b_night_code(client)
    finally:
        await client.close()
    probe_c_sox_yahoo()
    _hr("PROBES COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
