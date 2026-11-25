"""CP-3 real-key minute quotation transport — GET-only, allowlisted TRs only."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
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

QUOTE_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
TR = "FHKIF03020200"

BAND_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
BAND_TR = "FHMIF10000000"

STOCK_QUOTE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice"
STOCK_TR = "FHKST03010230"

QUOTE_ROUTES: dict[str, tuple[str, str, str]] = {
    "futures": (TR, QUOTE_PATH, "F"),
    "stock": (STOCK_TR, STOCK_QUOTE_PATH, "J"),
}

STOCK_BAND_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
STOCK_BAND_TR = "FHKST01010100"

BAND_ROUTES: dict[str, tuple[str, str, str]] = {
    "futures": (BAND_TR, BAND_PATH, "F"),
    "stock": (STOCK_BAND_TR, STOCK_BAND_PATH, "J"),
}

ALLOWLIST = (
    ReadOnlyCall(TR, QUOTE_PATH, "CP3 minute quotation"),
    ReadOnlyCall(STOCK_TR, STOCK_QUOTE_PATH, "CP3 stock minute quotation"),
    ReadOnlyCall(BAND_TR, BAND_PATH, "CP3 venue band (상한가·하한가·기준가)"),
    ReadOnlyCall(
        STOCK_BAND_TR, STOCK_BAND_PATH, "CP3 stock venue band (상한가·하한가·기준가)"
    ),
)


def market_allowlist(market: str) -> tuple[ReadOnlyCall, ...]:
    """The :data:`ALLOWLIST` entries of ONE market — the gate each call is checked against."""
    allowed = {QUOTE_ROUTES[market][0], BAND_ROUTES[market][0]}
    return tuple(entry for entry in ALLOWLIST if entry.tr_id in allowed)


BAND_FETCH_STAGE = "band_fetch"


class BandResponseEncoded(RuntimeError):
    """The band response arrived with a ``Content-Encoding`` other than identity."""


class BandResponseTooLarge(RuntimeError):
    """The band response grew past ``band_max_response_bytes`` while streaming."""


def _band_payload_or_none(raw: bytes) -> dict | None:
    """Parse EXACTLY the bytes that were hashed, or ``None``."""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


@dataclass(frozen=True)
class BandRead:
    """One band response: the parsed body and the digest of its RAW bytes."""

    payload: dict[str, Any]
    raw_payload_digest: str


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
    """One paced, retrying, GET-only quotation client."""

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

    def _initial_cursor(self, day: date) -> str:
        initial = self.cfg.get("initial_cursor", "")
        return str(initial(day) if callable(initial) else initial)

    def page(self, symbol: str, day: date, cursor: str = "") -> list[dict]:
        market = self.cfg.get("market", "futures")
        tr_id, path, division = QUOTE_ROUTES[market]
        url = REAL_BASE_URL + path
        assert_read_only_call("GET", url, tr_id, market_allowlist(market))
        params = {
            "FID_COND_MRKT_DIV_CODE": division,
            "FID_INPUT_ISCD": symbol,
            "FID_PW_DATA_INCU_YN": "Y",
            "FID_FAKE_TICK_INCU_YN": "N",
            "FID_INPUT_DATE_1": day.strftime("%Y%m%d"),
            "FID_INPUT_HOUR_1": cursor or self._initial_cursor(day),
        }
        if market == "futures":
            params["FID_HOUR_CLS_CODE"] = str(
                self.cfg.get("hour_cls_code", DEFAULT_HOUR_CLS_CODE)
            )
        refreshed = False
        for attempt in range(self.cfg["attempts"]):
            time.sleep(max(0, self.cfg["pace_s"] - (time.monotonic() - self.last)))
            started = datetime.now(KST)
            try:
                token = self.auth.get_token()
                headers = {
                    "authorization": "Bearer " + token,
                    "appkey": self.creds.app_key,
                    "appsecret": self.creds.app_secret,
                    "tr_id": tr_id,
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
                self.recorder.event(
                    {
                        "started_kst": started,
                        "received_kst": self.last_received_kst,
                        "method": "GET",
                        "tr_id": tr_id,
                        "path": path,
                        "params": params,
                        "attempt": attempt + 1,
                        "rt_cd": payload.get("rt_cd"),
                        "msg_cd": payload.get("msg_cd"),
                        "http_status": response.status_code,
                        "rows": rows,
                    }
                )
                if is_token_expired_error(payload) and not refreshed:
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

    def band(self, symbol: str) -> BandRead:
        """ONE paced, allowlisted, synchronous GET of the venue band."""
        market = self.cfg.get("market", "futures")
        band_tr, band_path, division = BAND_ROUTES[market]
        url = REAL_BASE_URL + band_path
        assert_read_only_call("GET", url, band_tr, market_allowlist(market))
        params = {"FID_COND_MRKT_DIV_CODE": division, "FID_INPUT_ISCD": symbol}
        budget_s = float(self.cfg["request_timeout_s"])
        phase = budget_s / 4.0
        timeout = httpx.Timeout(connect=phase, read=phase, write=phase, pool=phase)
        cap = int(self.cfg["max_response_bytes"])
        time.sleep(max(0, self.cfg["pace_s"] - (time.monotonic() - self.last)))
        record: dict[str, Any] = {
            "stage": BAND_FETCH_STAGE,
            "started_kst": datetime.now(KST),
            "method": "GET",
            "tr_id": band_tr,
            "path": band_path,
            "params": params,
            "max_response_bytes": cap,
        }
        try:
            token = self.auth.get_token()
            headers = {
                "authorization": "Bearer " + token,
                "appkey": self.creds.app_key,
                "appsecret": self.creds.app_secret,
                "tr_id": band_tr,
                "content-type": "application/json",
                "accept-encoding": "identity",
            }
            self.last = time.monotonic()
            self.calls += 1
            received = bytearray()
            with self.http.stream(
                "GET", url, headers=headers, params=params, timeout=timeout
            ) as response:
                record["http_status"] = response.status_code
                encoding = (response.headers.get("content-encoding") or "").strip()
                if encoding and encoding.lower() != "identity":
                    record["content_encoding"] = encoding
                    raise BandResponseEncoded(
                        f"band response carries content-encoding {encoding!r}"
                    )
                for chunk in response.iter_raw():
                    if len(received) + len(chunk) > cap:
                        raise BandResponseTooLarge(
                            f"band response exceeded {cap} bytes"
                        )
                    received.extend(chunk)
            raw = bytes(received)
            digest = hashlib.sha256(raw).hexdigest()
            record["raw_payload_digest"] = digest
            record["raw_payload_bytes"] = len(raw)
            payload = _band_payload_or_none(raw)
            if is_token_expired_error(payload or {}):
                self.auth.invalidate()
            response.raise_for_status()
            if payload is None:
                raise ValueError("band response is not a JSON mapping")
            record["rt_cd"] = payload.get("rt_cd")
            record["msg_cd"] = payload.get("msg_cd")
            if str(payload.get("rt_cd")) != "0":
                raise ValueError("band response carries rt_cd != 0")
        except BandResponseTooLarge as exc:
            record["error"] = "band_response_too_large"
            raise RuntimeError(record["error"]) from exc
        except BandResponseEncoded as exc:
            record["error"] = "band_response_encoded"
            raise RuntimeError(record["error"]) from exc
        except (
            httpx.HTTPError,
            requests.RequestException,
            ValueError,
            UnicodeDecodeError,
        ) as exc:
            record["error"] = "band_auth_http_or_json_error"
            raise RuntimeError(record["error"]) from exc
        finally:
            self.recorder.event(record)
        return BandRead(payload=payload, raw_payload_digest=digest)

    def history(self, symbol: str, day: date) -> list[dict]:
        result, seen, cursor = [], set(), ""
        for _ in range(self.cfg["max_pages"]):
            rows = self.page(symbol, day, cursor)
            result.extend(select_day(rows, day))
            stamps = [raw_stamp(r, day) for r in rows]
            dated = [s for s in stamps if s is not None]
            if not dated:
                return result
            next_cursor = min(dated).strftime("%H%M%S")
            if next_cursor in seen:
                return result
            seen.add(next_cursor)
            cursor = next_cursor
        raise RuntimeError("history pagination capped: do not claim complete seed")
