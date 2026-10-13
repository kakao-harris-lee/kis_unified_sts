"""CP-3 real-key minute quotation transport — GET-only, one allowlisted TR.

Extracted from ``tools/tos_cp3/minute_probe.py`` (PR-1, #894) so PR-2's live
field producer reuses the measured client instead of growing a second one. The
behaviour is PR-1's, unchanged: the three-way method/TR/path allowlist, the
app-key-fingerprinted PRIVATE token cache, the bounded retry that reduces every
transport/OAuth failure to one of two fixed tokens, and the token-expiry
re-issue that is detected BEFORE ``raise_for_status`` (a non-2xx expiry would
otherwise keep the cached token).

**GET-only, structurally.** There is no POST code path here, and
:func:`~tools.broker_probes.common.assert_read_only_call` refuses any method/TR/
path outside :data:`ALLOWLIST` before a socket is opened. This module imports
neither ``shared.execution`` nor ``tools.broker_probes.probes_real_order``, and
``tests/tools/test_cp3_live_producer.py`` pins that for the whole producer
module graph.

Firewall: legacy side (``tools/``). No ``tos`` / ``tos_runtime`` import.
"""

from __future__ import annotations

import time
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import requests

from shared.kis.auth import KISAuthManager, is_token_expired_error
from tools.broker_probes.common import (
    REAL_BASE_URL,
    ReadOnlyCall,
    assert_read_only_call,
    build_auth_config,
    secret_fingerprint,
)

KST = ZoneInfo("Asia/Seoul")

#: The one quotation endpoint. Operator decision 2026-10-10: the CP-3 data
#: source is the real-key REST minute GET ``FHKIF03020200``.
QUOTE_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
TR = "FHKIF03020200"
ALLOWLIST = (ReadOnlyCall(TR, QUOTE_PATH, "CP3 minute quotation"),)

#: ``FID_HOUR_CLS_CODE`` default. Mirrors
#: ``shared/collector/historical/backfill.py::fetch_minute_async``'s own
#: ``os.getenv("KIS_FUTURES_HOUR_CLS_CODE", "60")`` default; a caller that pins
#: the value passes it in ``cfg["hour_cls_code"]`` (plan §3.3 L9).
DEFAULT_HOUR_CLS_CODE = "60"


def raw_stamp(row: dict, day: date) -> datetime | None:
    """Date is checked BEFORE completion/parsing; PW_DATA may include other days."""
    day_text = str(
        row.get("stck_bsop_date") or row.get("futs_bsop_date") or day.strftime("%Y%m%d")
    )
    hour = str(row.get("stck_cntg_hour") or row.get("futs_cntg_hour") or "")
    if len(hour) == 4:
        hour += "00"
    try:
        stamp = datetime.strptime(day_text + hour, "%Y%m%d%H%M%S").replace(tzinfo=KST)
    except ValueError:
        return None
    return stamp if stamp.date() == day else None


def select_day(rows: list[dict], day: date) -> list[dict]:
    return [row for row in rows if raw_stamp(row, day) is not None]


class Quotes:
    """One paced, retrying, GET-only quotation client.

    Args:
        creds: the two futures query secrets, already resolved.
        recorder: anything with ``event(dict)`` and an ``output`` Path. The
            producer passes a small request log; PR-1's probe passes its
            evidence recorder.
        cfg: transport settings (``attempts``, ``pace_s``, ``retry_pause_s``,
            ``request_timeout_s``, ``max_pages``, optional ``hour_cls_code``).
        token_cache: the cache directory for THIS process's token. Defaults to
            PR-1's derivation under the recorder's output parent. The producer
            passes its own path — the stock ``KISToken`` cache keys on the
            domain only and never looks at the app key (plan §3.4).
    """

    def __init__(
        self,
        creds: Any,
        recorder: Any,
        cfg: Any,
        *,
        token_cache: Path | None = None,
    ):
        cache = (
            token_cache
            if token_cache is not None
            else recorder.output.parent
            / ".token-cache"
            / secret_fingerprint(creds.app_key)
        )
        self.auth = KISAuthManager(build_auth_config(creds, cache), use_singleton=False)
        self.creds, self.recorder, self.cfg = creds, recorder, cfg
        self.http = httpx.Client(
            timeout=cfg["request_timeout_s"], follow_redirects=False
        )
        self.last = 0.0
        self.calls = 0

    def page(self, symbol: str, day: date, cursor: str = "") -> list[dict]:
        url = REAL_BASE_URL + QUOTE_PATH
        assert_read_only_call("GET", url, TR, ALLOWLIST)
        params = {
            "FID_COND_MRKT_DIV_CODE": "F",
            "FID_INPUT_ISCD": symbol,
            "FID_HOUR_CLS_CODE": str(
                self.cfg.get("hour_cls_code", DEFAULT_HOUR_CLS_CODE)
            ),
            "FID_PW_DATA_INCU_YN": "Y",
            "FID_FAKE_TICK_INCU_YN": "N",
            "FID_INPUT_DATE_1": day.strftime("%Y%m%d"),
            "FID_INPUT_HOUR_1": cursor,
        }
        refreshed = False
        for attempt in range(self.cfg["attempts"]):
            time.sleep(max(0, self.cfg["pace_s"] - (time.monotonic() - self.last)))
            started = datetime.now(KST)
            try:
                # OAuth may raise ValueError or requests errors. Keep it in the
                # bounded retry; never persist their possibly sensitive text.
                token = self.auth.get_token()
                headers = {
                    "authorization": "Bearer " + token,
                    "appkey": self.creds.app_key,
                    "appsecret": self.creds.app_secret,
                    "tr_id": TR,
                    "content-type": "application/json",
                }
                started = datetime.now(KST)
                self.last_started_kst = started
                self.last = time.monotonic()
                self.calls += 1
                response = self.http.get(url, headers=headers, params=params)
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("quote response is not a mapping")
                self.last_received_kst = datetime.now(KST)
                rows = payload.get("output2") or []
                # Persist only quote rows + response status; never headers, token or msg1.
                self.recorder.event(
                    {
                        "started_kst": started,
                        "received_kst": self.last_received_kst,
                        "method": "GET",
                        "tr_id": TR,
                        "path": QUOTE_PATH,
                        "params": params,
                        "attempt": attempt + 1,
                        "rt_cd": payload.get("rt_cd"),
                        # Message CLASS only. msg1 is the human text and is
                        # never persisted; msg_cd is what names a refusal.
                        "msg_cd": payload.get("msg_cd"),
                        "http_status": response.status_code,
                        "rows": rows,
                    }
                )
                if is_token_expired_error(payload) and not refreshed:
                    # This manager owns only the app-key scoped private cache.
                    self.auth.invalidate()
                    refreshed = True
                    self.recorder.event(
                        {
                            "started_kst": started,
                            "token_invalidated": True,
                            "attempt": attempt + 1,
                            "params": params,
                        }
                    )
                # KIS can report expiry with non-2xx HTTP status. Detect it
                # above before generic HTTP retry, or the cached token persists.
                response.raise_for_status()
                if str(payload.get("rt_cd")) == "0" and isinstance(rows, list):
                    return [r for r in rows if isinstance(r, dict)]
                error = "broker_response"
            except (httpx.HTTPError, requests.RequestException, ValueError):
                error = "auth_http_or_json_error"
                self.recorder.event(
                    {"started_kst": started, "error": error, "params": params}
                )
            time.sleep(self.cfg["retry_pause_s"])
        raise RuntimeError(error)

    def history(self, symbol: str, day: date) -> list[dict]:
        result, seen, cursor = [], set(), ""
        for _ in range(self.cfg["max_pages"]):
            rows = self.page(symbol, day, cursor)
            result.extend(select_day(rows, day))
            stamps = [raw_stamp(r, day) for r in rows]
            stamps = [s for s in stamps if s is not None]
            if not stamps:
                return result
            next_cursor = min(stamps).strftime("%H%M%S")
            if next_cursor in seen:
                return result
            seen.add(next_cursor)
            cursor = next_cursor
        raise RuntimeError("history pagination capped: do not claim complete seed")
