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

import contextlib
import hashlib
import json
import threading
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
#: (runbook §7.2-d) and :mod:`~tools.tos_cp3.live_producer.band` agree on the
#: string without either of them spelling it twice.
BAND_FETCH_STAGE = "band_fetch"


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


@dataclass
class _BandAttempt:
    """What the WORKER thread produces. It mutates no shared state at all.

    Everything the caller needs comes back in here, so a worker that finishes
    after the caller gave up has written nothing anybody reads (review round 3
    item: "the caller discards any late result").
    """

    raw: bytes | None = None
    status: int | None = None
    token_expired: bool = False
    error: str | None = None


def _new_band_client(timeout: httpx.Timeout) -> httpx.Client:
    """A FRESH client per band attempt, and that is the design, not an oversight.

    Three reasons, in order of how badly each would bite:

    * the caller aborts a stuck attempt by CLOSING this client from its own
      thread, which is what makes the worker's blocked socket read fail. A
      client shared with the minute path would mean a band timeout breaks
      price polling — the one thing that must never happen for the band's sake.
    * "use a fresh client for the next attempt after a forced close" is then
      true by construction: there is no closed client to reuse.
    * the band is read once or twice a day, so connection reuse buys nothing.
    """
    return httpx.Client(timeout=timeout, follow_redirects=False)


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
        #: How :meth:`band` gets its own client. A seam, because the tests
        #: need to hand the attempt an ``httpx.MockTransport`` that trickles
        #: headers and compressed fragments — the two reads that happen
        #: OUTSIDE ``iter_bytes()`` and that the previous bound missed.
        self.band_client_factory: Any = _new_band_client

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

    def _band_attempt(
        self,
        params: dict,
        timeout: httpx.Timeout,
        holder: dict,
        abort: threading.Event,
    ) -> _BandAttempt:
        """Runs ON THE WORKER THREAD. Returns everything; mutates nothing shared.

        The token acquire is INSIDE this thread deliberately. It is a network
        call (``KISAuthManager`` over ``requests``) whose timeout this module
        does not control, so acquiring it on the caller's thread first would
        leave exactly the unbounded wait the worker exists to bound.

        ⚠ The one shared thing it can touch is the token CACHE, through
        ``get_token()`` writing a fresh token to disk. That is idempotent, it is
        what any later attempt would do anyway, and it cannot write a band line
        or change this object's state. Everything else — the counters, the pace
        stamp, the request record, the expiry invalidation — belongs to the
        caller and is done there.
        """
        out = _BandAttempt()
        url = REAL_BASE_URL + BAND_PATH
        client = None
        try:
            token = self.auth.get_token()
            headers = {
                "authorization": "Bearer " + token,
                "appkey": self.creds.app_key,
                "appsecret": self.creds.app_secret,
                "tr_id": BAND_TR,
                "content-type": "application/json",
                # No compression. Defence in depth, NOT the bound: a gzip body
                # that decodes to nothing yet is read without `iter_bytes()`
                # ever yielding, which is one of the two reads the old in-loop
                # deadline could not see (the other is the headers). The bound
                # is the caller's thread join; this only removes a way for a
                # server to spend time invisibly.
                "accept-encoding": "identity",
            }
            client = self.band_client_factory(timeout)
            holder["client"] = client
            if abort.is_set():
                # The caller gave up before this thread got going. Nothing has
                # been sent yet, so leave without opening a socket.
                out.error = "band_total_budget_exceeded"
                return out
            received = bytearray()
            with client.stream("GET", url, headers=headers, params=params) as response:
                out.status = response.status_code
                for chunk in response.iter_bytes():
                    received.extend(chunk)
            out.raw = bytes(received)
        except (httpx.HTTPError, requests.RequestException, ValueError, OSError):
            # Includes the error a closed client raises on the blocked read,
            # which is how the caller's abort reaches this thread.
            out.error = "band_auth_http_or_json_error"
        finally:
            if client is not None:
                with contextlib.suppress(Exception):
                    client.close()
        return out

    def band(self, symbol: str) -> BandRead:
        """ONE paced, allowlisted GET of the venue band. No retry loop here.

        Three ways this differs from :meth:`page`, each one a requirement of
        the band plan §3.1:

        * **the raw bytes are hashed, and only those bytes are parsed.** The
          band line binds ``raw_payload_digest`` to what the broker actually
          sent; ``page()`` does not keep the bytes at all.
        * **the attempt logs its OWN ``tr_id``.** ``page()`` writes the module
          constant :data:`TR`, so a band call recorded through it would be
          invisible to the post-session check "every TR in
          ``producer-log.jsonl`` is one of the two, all GET" (§3.5, review
          LOW-2) — the check would pass while never having seen this call.
        * **one attempt, no retry.** The band's retry budget is TIME (every
          attempt must end before the next boundary minus δ, so the price poll
          is not pushed), not a count, so the loop lives in
          :mod:`~tools.tos_cp3.live_producer.band` where the clock is injected.

        **What the bound guarantees, exactly** (review round 3, Codex MEDIUM).
        THE CALLER returns within ``pace_s + request_timeout_s``, whatever
        httpx is doing, because the whole attempt runs on a worker thread and
        this method waits with ``join(budget)``. Two earlier attempts at this
        were both wrong, and both are worth naming because the second looked
        like a fix:

        1. four phase timeouts summing to the budget — httpx's ``read`` bounds
           ONE chunk, so a trickle has no total;
        2. a deadline checked inside the ``iter_bytes()`` loop — that loop sees
           only DECODED content, so header reception (entirely before the first
           yield) and compressed bytes that decode to nothing are both read
           without the check ever running. Codex measured 1.6 s against a 1 s
           budget with a gzip stream yielding every 100 ms.

        On timeout this method closes the attempt's client from this thread so
        the worker's blocked socket read fails, then raises **immediately**. It
        does NOT join the worker.

        ⚠ **The worker may outlive this call**, stated rather than implied:
        closing the client makes its read fail fast but not instantly, and a
        worker aborted before it even built its client notices only at
        ``abort``. A lingering worker cannot write a band line, cannot touch
        this object's state, and its result is discarded — the caller has
        already raised and never reads it. The thread is a daemon, so it cannot
        hold up process exit either.

        Raises:
            RuntimeError: on any transport/OAuth/JSON failure, ``rt_cd != 0``,
                or the total budget being exceeded. The caller writes no band
                line and logs ``band_fetch_failed``.
        """
        # ⛔ ON THE CALLER THREAD, BEFORE ANY NETWORK ACTIVITY EXISTS. The gate
        # is where "zero real futures orders" is enforced, so it runs before a
        # worker is submitted, never inside one.
        url = REAL_BASE_URL + BAND_PATH
        assert_read_only_call("GET", url, BAND_TR, ALLOWLIST)
        params = {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": symbol}
        # Per-phase INACTIVITY guards, not a total. No clamp: a
        # `max(0.001, ...)` floor RAISES the phases for a budget under 4 ms and
        # so loosens what it looks like it tightens. The minimum lives where a
        # reviewer can see it — `config.py` refuses a `request_timeout_s` below
        # `MIN_REQUEST_TIMEOUT_S`.
        budget_s = float(self.cfg["request_timeout_s"])
        phase = budget_s / 4.0
        timeout = httpx.Timeout(connect=phase, read=phase, write=phase, pool=phase)
        # The pace sleep stays on THIS thread: it is a deterministic sleep, not
        # a socket read, and `band.attempt_budget()` charges it on top of the
        # budget — so the caller's whole cost is pace + budget, as declared.
        time.sleep(max(0, self.cfg["pace_s"] - (time.monotonic() - self.last)))
        record: dict[str, Any] = {
            "stage": BAND_FETCH_STAGE,
            "started_kst": datetime.now(KST),
            "method": "GET",
            "tr_id": BAND_TR,
            "path": BAND_PATH,
            "params": params,
            "total_budget_s": budget_s,
        }
        self.last = time.monotonic()
        self.calls += 1
        holder: dict[str, Any] = {}
        abort = threading.Event()
        box: list[_BandAttempt] = []

        def run() -> None:
            # A worker that dies must SAY so. Without this the caller sees an
            # empty box and cannot tell a crash from a budget timeout, and it
            # would report the wrong one — the exact conflation this project
            # keeps paying for elsewhere.
            try:
                box.append(self._band_attempt(params, timeout, holder, abort))
            except BaseException:  # noqa: BLE001 - reported, never swallowed
                box.append(_BandAttempt(error="band_worker_crashed"))

        worker = threading.Thread(target=run, name="cp3-band-attempt", daemon=True)
        try:
            worker.start()
            worker.join(budget_s)
            if worker.is_alive():
                abort.set()
                client = holder.get("client")
                if client is not None:
                    # From THIS thread, so the worker's blocked read errors out.
                    with contextlib.suppress(Exception):
                        client.close()
                record["error"] = "band_total_budget_exceeded"
                raise RuntimeError(record["error"])
            if not box:
                # The thread ended without even reporting a crash. Nothing
                # known about the call, so it is named as its own thing rather
                # than borrowed from the timeout.
                record["error"] = "band_worker_vanished"
                raise RuntimeError(record["error"])
            outcome = box[0]
            record["http_status"] = outcome.status
            if outcome.error is not None or outcome.raw is None:
                record["error"] = outcome.error or "band_auth_http_or_json_error"
                raise RuntimeError(record["error"])
            raw = outcome.raw
            digest = hashlib.sha256(raw).hexdigest()
            record["raw_payload_digest"] = digest
            record["raw_payload_bytes"] = len(raw)
            payload = _band_payload_or_none(raw)
            if is_token_expired_error(payload or {}):
                # The caller owns every mutation of shared state, this one
                # included: the worker only reports the bytes it saw.
                self.auth.invalidate()
            # Expiry is handled BEFORE the status check, because KIS can report
            # it with a non-2xx status — same ordering reason as page().
            if outcome.status is None or not 200 <= outcome.status < 300:
                record["error"] = "band_auth_http_or_json_error"
                raise RuntimeError(record["error"])
            if payload is None:
                record["error"] = "band_auth_http_or_json_error"
                raise RuntimeError(record["error"])
            record["rt_cd"] = payload.get("rt_cd")
            # Message CLASS only, like page(): msg1 is human text.
            record["msg_cd"] = payload.get("msg_cd")
            if str(payload.get("rt_cd")) != "0":
                record["error"] = "band_auth_http_or_json_error"
                raise RuntimeError(record["error"])
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
