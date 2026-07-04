"""Verify / roll the KRX night-futures WS tr_key (unified roadmap O9).

The night KOSPI200 futures session (18:00–06:00 KST) is served only by the
realtime WebSocket H0MFCNT0. Subscribing with the wrong ``tr_key`` fails
*silently* (0 trades looks identical to a genuinely quiet window), so the
active near-month code must be confirmed against a live subscription before
the collector is trusted.

This tool, run during the active night session, subscribes to each candidate
code for a short window and reports which one actually streams trades. It also
prints the fo_cme_code.mst outright front-month for cross-reference.

Candidates (roadmap O9 ambiguity, 2026-07-02):
* ``101W9000`` — the code used by KIS's official H0MFCNT0 example
  (examples_llm/domestic_futureoption/krx_ngt_futures_ccnl); looks like the
  auto-rolling continuous night front-month short code (cf. day ``101S6000``).
* ``1A0YYMM``  — the fo_cme_code.mst 단축코드 outright front-month
  (e.g. ``1A01609`` = 2026-09). The roadmap spike assumed this column is the
  tr_key; this tool checks whether the WS actually accepts it.

Usage (deploy host, night session active, futures REAL creds in env):
    set -a && . ./.env.paper && set +a
    export REDIS_URL=redis://localhost:6379/1
    python scripts/analysis/verify_night_tr_key.py 101W9000 1A01609 --seconds 25
"""

from __future__ import annotations

import argparse
import io
import sys
import time
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

_MST_URL = "https://new.real.download.dws.co.kr/common/master/fo_cme_code.mst.zip"


def _mst_front_month() -> None:
    """Print outright KOSPI200 night codes from fo_cme_code.mst (cross-ref)."""
    print("\n--- fo_cme_code.mst outright KOSPI200 night codes ---")
    try:
        req = urllib.request.Request(_MST_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            raw = resp.read()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            text = zf.read(zf.namelist()[0]).decode("cp949", errors="replace")
    except Exception as exc:  # noqa: BLE001
        print(f"  mst fetch failed: {type(exc).__name__}: {exc}")
        return
    today_ym = date.today().year * 100 + date.today().month
    rows = []
    for line in text.splitlines():
        code = line[:9].strip()
        # outright single-month futures short codes look like 1A0YYMM; the
        # spread rows start with 2D0. Expiry YYYYMM sits after the ISIN/F flag.
        if not code.startswith("1A0"):
            continue
        expiry = None
        for tok in line.split():
            if len(tok) == 6 and tok.isdigit() and tok.startswith("20"):
                expiry = int(tok)
                break
        rows.append((code, expiry))
    rows.sort(key=lambda r: (r[1] or 0))
    front = next((c for c, e in rows if e and e >= today_ym), None)
    for code, expiry in rows:
        mark = "  <- front month" if code == front else ""
        print(f"  {code}  expiry={expiry}{mark}")
    print(f"  => mst outright front-month: {front}")


def _verify_live(codes: list[str], seconds: int) -> None:
    from services.night_futures_collector.main import _build_adapter

    adapter = _build_adapter()
    if adapter is None:
        print("ERROR: KIS_FUTURES_APP_KEY/SECRET not set — cannot open WS")
        return

    print(f"\n--- live H0MFCNT0 subscription probe ({seconds}s each) ---")
    try:
        adapter.connect()
        for code in codes:
            seen: list = []
            deadline = time.time() + seconds
            try:
                adapter.subscribe_night_trades([code], seen.append, until=deadline)
            except Exception as exc:  # noqa: BLE001
                print(f"  {code}: SUBSCRIBE ERROR {type(exc).__name__}: {exc}")
                continue
            if seen:
                last = seen[-1]
                print(
                    f"  {code}: {len(seen)} trades  =>  STREAMS  "
                    f"last price={getattr(last, 'price', '?')} "
                    f"symbol={getattr(last, 'symbol', '?')} "
                    f"oi={getattr(last, 'open_interest', '?')}"
                )
            else:
                print(f"  {code}: 0 trades  =>  silent (wrong code or quiet window)")
    finally:
        try:
            adapter.disconnect()
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("codes", nargs="*", default=["101W9000", "1A01609"])
    ap.add_argument("--seconds", type=int, default=25)
    ap.add_argument("--mst-only", action="store_true", help="skip the live WS probe")
    args = ap.parse_args()

    _mst_front_month()
    if not args.mst_only:
        _verify_live(args.codes or ["101W9000", "1A01609"], args.seconds)
    print("\n=> config/night_futures.yaml::tr_key should be the code that STREAMS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
