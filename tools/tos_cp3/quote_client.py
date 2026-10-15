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

#: The one quotation endpoint. Operator decision 2026-10-10: the CP-3 data
#: source is the real-key REST minute GET ``FHKIF03020200``.
QUOTE_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
TR = "FHKIF03020200"

#: The venue BAND read (band-via-producer plan 2026-10-15 §3.1). Operator
#: decision the same day: the band's source moves from a runtime MOCK GET to
#: THIS producer's REAL GET-only read, so band and price come from one domain
#: and the runtime keeps holding no credential at all.
#:
#: **Defined locally, on purpose** (§3.1). ``tools/broker_probes/
#: probes_venue_limits.py`` (P-VL) carries the same two literals, and importing
#: them from there would pull a module sealed to the MOCK host
#: (``assert_mock_host``) into a REAL-token transport. Two literals in two
#: modules is the lesser defect; the pair is pinned against P-VL's by a test.
BAND_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
BAND_TR = "FHMIF10000000"

#: The GET-only three-way gate (method + TR id + URL path).
#: :func:`~tools.broker_probes.common.assert_read_only_call` refuses anything
#: outside it BEFORE a socket is opened, so this tuple is where "zero real
#: futures orders" is enforced in code rather than promised in prose. Both
#: entries are GET, and this module has no POST code path at all.
ALLOWLIST = (
    ReadOnlyCall(TR, QUOTE_PATH, "CP3 minute quotation"),
    ReadOnlyCall(BAND_TR, BAND_PATH, "CP3 venue band (상한가·하한가·기준가)"),
)

#: The log stage one band attempt writes. Named so the post-session check
#: (runbook §7.2-d) and :mod:`~tools.tos_cp3.live_producer.band_probe` agree on
#: the string without either of them spelling it twice.
BAND_FETCH_STAGE = "band_fetch"


class BandResponseTooLarge(RuntimeError):
    """The band response grew past ``band_max_response_bytes`` while streaming.

    A ``RuntimeError``, so the caller folds it to a soft failure like any other
    broker-answer problem: no band line, and the session carries on. It exists
    because the time bound now lives in the band PROCESS's own ``timeout``,
    and a size cap is the part this layer can still enforce by itself — a
    48 MiB body hashed and parsed inside a 0.2 s budget was Codex's round-4
    F2 measurement.
    """


def _band_payload_or_none(raw: bytes) -> dict | None:
    """Parse EXACTLY the bytes that were hashed, or ``None``.

    Not ``response.json()``: a streamed response has no buffered ``.content``
    to re-read, and parsing anything other than the hashed bytes would mean
    the digest no longer names what was parsed.
    """
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


@dataclass(frozen=True)
class BandRead:
    """One band response: the parsed body and the digest of its RAW bytes."""

    payload: dict[str, Any]
    #: sha256 of ``response.content``, taken BEFORE ``.json()`` (band plan
    #: §3.1). The band line binds the runtime's evidence row to the bytes the
    #: broker actually sent, and a digest of a re-serialised parse would be a
    #: digest of this process's json writer instead.
    raw_payload_digest: str


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

    def band(self, symbol: str) -> BandRead:
        """ONE paced, allowlisted, synchronous GET of the venue band.

        Three ways this differs from :meth:`page`, each one a requirement of
        the band plan §3.1:

        * **the raw bytes are hashed, and only those bytes are parsed.** The
          band line binds ``raw_payload_digest`` to what the broker actually
          sent; ``page()`` does not keep the bytes at all.
        * **the attempt logs its OWN ``tr_id``.** ``page()`` writes the module
          constant :data:`TR`, so a band call recorded through it would be
          invisible to the post-session check "every TR in the request logs is
          one of the two, all GET" (§3.5, review LOW-2).
        * **one attempt, no retry.** Scheduling and retry are the RUNNER's, not
          this module's.

        **Where the total-time bound lives: not here** (band plan v3,
        2026-10-16 operator decision). Three rounds of review established that
        this process cannot bound its own HTTP call honestly:

        1. four phase timeouts summing to the budget — httpx's ``read`` bounds
           ONE chunk, so a trickle has no total;
        2. a deadline inside the ``iter_bytes()`` loop — that loop sees only
           DECODED content, so header reception and compressed bytes that
           decode to nothing are read without the check running;
        3. a worker thread with ``join(budget)`` — the caller then blocks in
           ``client.close()``, hashing and parsing still run outside the
           budget, and an abandoned worker holds
           ``KISAuthManager.get_token()``'s lock so the next ``page()`` waits
           on it.

        So the band GET now runs in its own short-lived PROCESS
        (:mod:`tools.tos_cp3.live_producer.band_probe`) under the runner's
        ``timeout``, which is a bound no in-process trick can match: SIGKILL
        does not negotiate. What stays here is what this layer can honestly
        promise — per-phase INACTIVITY guards, and a **streamed size cap** so
        a body cannot grow unboundedly before anyone looks at it.

        Raises:
            RuntimeError: on any transport/OAuth/JSON failure, ``rt_cd != 0``,
                or a response past ``band_max_response_bytes``. The caller
                writes no band line.
        """
        # ⛔ BEFORE ANY NETWORK ACTIVITY. The gate is where "zero real futures
        # orders" is enforced, so nothing — not even a DNS lookup — precedes it.
        url = REAL_BASE_URL + BAND_PATH
        assert_read_only_call("GET", url, BAND_TR, ALLOWLIST)
        params = {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": symbol}
        # Per-phase INACTIVITY guards. No clamp: a `max(0.001, ...)` floor
        # RAISES the phases for a tiny budget and so loosens what it looks like
        # it tightens. The floor is `config.MIN_REQUEST_TIMEOUT_S`, refused at
        # load time where a reviewer can see it.
        budget_s = float(self.cfg["request_timeout_s"])
        phase = budget_s / 4.0
        timeout = httpx.Timeout(connect=phase, read=phase, write=phase, pool=phase)
        cap = int(self.cfg["max_response_bytes"])
        time.sleep(max(0, self.cfg["pace_s"] - (time.monotonic() - self.last)))
        record: dict[str, Any] = {
            "stage": BAND_FETCH_STAGE,
            "started_kst": datetime.now(KST),
            "method": "GET",
            "tr_id": BAND_TR,
            "path": BAND_PATH,
            "params": params,
            "max_response_bytes": cap,
        }
        try:
            # OAuth may raise ValueError or requests errors; both are failures
            # of this attempt and neither is ever persisted as text.
            token = self.auth.get_token()
            headers = {
                "authorization": "Bearer " + token,
                "appkey": self.creds.app_key,
                "appsecret": self.creds.app_secret,
                "tr_id": BAND_TR,
                "content-type": "application/json",
                # No compression: a gzip body that decodes to nothing yet is
                # bytes read for no visible progress, and the size cap below
                # should count what the wire carried.
                "accept-encoding": "identity",
            }
            self.last = time.monotonic()
            self.calls += 1
            received = bytearray()
            with self.http.stream(
                "GET", url, headers=headers, params=params, timeout=timeout
            ) as response:
                record["http_status"] = response.status_code
                for chunk in response.iter_bytes():
                    received.extend(chunk)
                    if len(received) > cap:
                        # Stop reading rather than hashing an unbounded body.
                        # The `with` closes the stream on the way out.
                        raise BandResponseTooLarge(
                            f"band response exceeded {cap} bytes"
                        )
            # EXACTLY the bytes received, hashed before anything parses them.
            raw = bytes(received)
            digest = hashlib.sha256(raw).hexdigest()
            record["raw_payload_digest"] = digest
            record["raw_payload_bytes"] = len(raw)
            payload = _band_payload_or_none(raw)
            if is_token_expired_error(payload or {}):
                # This manager owns only the app-key scoped private cache.
                self.auth.invalidate()
            # Expiry is handled BEFORE the status check, because KIS can report
            # it with a non-2xx status — same ordering reason as page().
            response.raise_for_status()
            if payload is None:
                raise ValueError("band response is not a JSON mapping")
            record["rt_cd"] = payload.get("rt_cd")
            # Message CLASS only, like page(): msg1 is human text.
            record["msg_cd"] = payload.get("msg_cd")
            if str(payload.get("rt_cd")) != "0":
                raise ValueError("band response carries rt_cd != 0")
        except BandResponseTooLarge as exc:
            record["error"] = "band_response_too_large"
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
            stamps = [s for s in stamps if s is not None]
            if not stamps:
                return result
            next_cursor = min(stamps).strftime("%H%M%S")
            if next_cursor in seen:
                return result
            seen.add(next_cursor)
            cursor = next_cursor
        raise RuntimeError("history pagination capped: do not claim complete seed")
