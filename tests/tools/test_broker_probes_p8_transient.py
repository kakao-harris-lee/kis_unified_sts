"""P-8 separates a transport failure from a broker rejection.

The defect, measured. On 2026-09-28 a five-trial P-8 series ran under a host
cron on a detached ``origin/main`` worktree. Trial 1 measured
(``P-8-20260928T000506Z``). Trial 2 placed its order, got its amend accepted
(``rt_cd=0``, ODNO 558 -> 560), polled the coexistence surface at least once,
and then died:

    "errors": ["ConnectionError: ('Connection aborted.',
     RemoteDisconnected('Remote end closed connection without response'))"]

``P-8-20260928T000658Z`` carries no ``coexistence_ms``, no
``replace_issues_new_odno`` and no ``poll_granularity_ms``: the exception left
``probe_p8`` entirely, ``run.py`` salvaged the partial run and returned 5. The
cleanup cancel issued seconds later succeeded, so the transport was already
back. The runner then wrote

    VERDICT: STOP: P-8 2/5 오류 1건(브로커 거부 포함) — 1/5 성공 후 중단(재시도 금지)

and trials 3, 4 and 5 never ran. Nothing had been rejected. The same campaign
had classified a ``ReadTimeout`` the other way nine days earlier ("§3 중단
규칙(rate-limit)과 다른 종류라 1회 재시도"), and the README records the
contradiction (2026-09-11 campaign README, 09-28 and 09-30 blocks).

So this file pins, in both directions:

* a transport failure on the order-status GET buys ONE retry a whole poll
  interval later, and the trial carries on if that answers;
* two consecutive ones stop the TRIAL with a reason that says "transport", not
  "rejected", and leave no ``coexistence_ms`` to be mistaken for one;
* ``EGW00215``, the LEDGER-side throttle, behaves the same way;
* HTTP 429 and ``EGW00201`` do NOT — they are our own call rate, and "stop, no
  retry" is an account-protection rule that stays exactly as it was;
* an order-mutating call is never retried, however it fails;
* ``_cleanup`` still runs, and is still recorded, on every one of those paths.

No socket is opened: ``probes_order.http_json`` is replaced by a scripted
recorder that replays the 모의 futures behaviour the campaign artifacts show.
"""

from __future__ import annotations

import argparse
import itertools
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
import requests

#: Captured before ``no_sleeping`` replaces ``time.sleep`` process-wide. The
#: late-window test needs the deadline to really pass, and the deadline is
#: read from the real monotonic clock.
_REAL_SLEEP = time.sleep

from tools.broker_probes import common, probes_order
from tools.broker_probes.probes_order import (
    _CLEANUP_CANCELLED,
    _CLEANUP_NOTHING_TO_CANCEL,
    _P8_COEXISTENCE_PREFIX,
    _P8_STOP_PREFIX,
    POLICY_VERSION,
    probe_p8,
)

_ACCOUNT = "1234567890"
_SYMBOL = "A05610"  # the 2026-09-28 mini near-month contract
_LAST_PRICE = "1113.60"

#: Verbatim from ``P-8-20260928T000658Z.json:errors[0]``. The repr carries no
#: URL, which is why the runner could not tell what had failed either.
_CONNECTION_ABORTED = (
    "('Connection aborted.', RemoteDisconnected('Remote end closed connection "
    "without response'))"
)

#: 원장에서 허용 가능한 초당 거래건수를 초과하였습니다 — HTTP 500 + rt_cd=1,
#: as ``P-CA-20260930T015946Z.json`` poll #14 recorded it.
_LEDGER_THROTTLE = {
    "rt_cd": "1",
    "msg_cd": "EGW00215",
    "msg1": "원장에서 허용 가능한 초당 거래건수를 초과하였습니다.",
}

_NO_QTY = "모의투자 정정/취소할 수량이 없습니다."


class _StubAuth:
    def get_auth_headers(self) -> dict[str, str]:
        return {"authorization": "Bearer stub"}


@pytest.fixture
def futures_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIS_FUTURES_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_FUTURES_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", _ACCOUNT)
    monkeypatch.delenv("KIS_TOKEN_CACHE_DIR", raising=False)


@pytest.fixture(autouse=True)
def no_sleeping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real seconds buy these tests nothing. Both modules' clocks, because the
    pacer lives in ``common`` now."""
    monkeypatch.setattr(probes_order.time, "sleep", lambda _s: None)
    monkeypatch.setattr(common.time, "sleep", lambda _s: None)


@pytest.fixture
def defers(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Every ``Pacer.defer`` interval, in order — the retry's wait."""
    seen: list[float] = []
    original = common.Pacer.defer

    def _spy(self: common.Pacer, seconds: float) -> None:
        seen.append(seconds)
        original(self, seconds)

    monkeypatch.setattr(common.Pacer, "defer", _spy)
    return seen


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "probe_id": "P-8",
        "symbol": _SYMBOL,
        "asset": "futures",
        "confirm": True,
        "quantity": 1,
        "price_offset_pct": 10.0,
        "samples": 1,
        "margin_pct": 50.0,
        # 250 ms with pacing off, so the effective poll interval — and so the
        # retry's wait — is a number no other default could produce.
        "poll_ms": 250.0,
        "gap_ms": 0.0,
        "inter_trial_s": 0.0,
        "settle_seconds": 0.0,
        # Generous: the scripted broker, not the clock, decides when the loop
        # ends, so a retry cannot be refused for running out of window unless
        # a test asks for that.
        "visibility_timeout_s": 300.0,
        "balance_timeout_s": 2.0,
        "late_window_s": 0.05,
        "max_pages": 10,
        "allow_fill": False,
        "stock_order_type": "market",
        "pace_s": 0.0,
        "token_cache_dir": None,
        "out_dir": None,
        "note": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


class _Wire:
    """A 모의 futures broker whose open-order surface follows a script.

    ``poll_script`` is consumed one entry per ``inquire-ccnl`` call made BEFORE
    the first cleanup cancel; ``cleanup_script`` one per call after it. Running
    off the end of either repeats its last entry, so a test only writes the
    prefix it cares about.

    Tokens:

    ``both``       both ODNOs live — the coexistence shape.
    ``new_only``   only the amended order is live (the campaign's normal shape).
    ``live``       every order the broker actually holds — what a real book
                   walk returns, and the cleanup default.
    ``timeout``    ``requests.exceptions.ReadTimeout``.
    ``conn``       ``requests.exceptions.ConnectionError`` carrying a URL with
                   the account number in the query string, exactly as
                   ``requests`` renders one.
    ``chunked``    ``requests.exceptions.ChunkedEncodingError`` — the body-read
                   half of the transport set.
    ``throttle``   HTTP 500 + ``EGW00215``, the LEDGER throttle.
    ``no_rows``    ``rt_cd='7'`` + ``KIOK0560`` — this broker's empty-set
                   notation, a REJECTION shape and not a rate limit.
    ``rt_cd_zero`` a healthy page whose ``rt_cd`` is the JSON NUMBER ``0``.
                   ``str(x or "")`` turns that into ``""`` — the falsy-zero
                   trap ``call_evidence`` documents.
    ``http429``    HTTP 429, no body.
    ``egw00201``   HTTP 200 + ``EGW00201``, our own call rate in the body.
    """

    def __init__(
        self,
        *,
        poll_script: list[str] | None = None,
        cleanup_script: list[str] | None = None,
        submit_raises: BaseException | None = None,
        amend_raises: BaseException | None = None,
        submit_rejects: bool = False,
        amend_rejects: bool = False,
        amend_without_odno: bool = False,
        accept_before_raising: bool = False,
        delay_before: dict[int, float] | None = None,
    ) -> None:
        self.poll_script = list(poll_script or ["new_only"])
        # "live", not "new_only": the cleanup walk reads the BOOK, and the
        # whole point of the F1 case is a row the probe never named. A
        # scripted subset there would hide exactly what the walk exists to
        # find. In the ordinary flow the two are the same set.
        self.cleanup_script = list(cleanup_script or ["live"])
        self.submit_raises = submit_raises
        self.amend_raises = amend_raises
        self.submit_rejects = submit_rejects
        self.amend_rejects = amend_rejects
        self.amend_without_odno = amend_without_odno
        #: The hazard F1 names: the broker ACCEPTED the order and is resting
        #: it, and only the answer was lost. Without this the fake would make
        #: a lost POST look harmless, which is the assumption under review.
        self.accept_before_raising = accept_before_raising
        #: 1-based inquire index -> real seconds to burn first, for the
        #: late-window case. Real, because the fixture patches time.sleep out
        #: and the deadline is read from the real monotonic clock.
        self.delay_before = dict(delay_before or {})
        self.calls: list[dict[str, Any]] = []
        self.inquiries: list[str] = []
        self.cleanup_phase = False
        self._numbers = itertools.count(558)
        self._original = ""
        self._new = ""
        #: What the broker would actually show as resting. The scripted tokens
        #: choose WHICH of the two the poll is asked about; this decides
        #: whether either is really there, so a cancel and a listing cannot
        #: disagree the way a hand-maintained pair of sets would.
        self._live: set[str] = set()

    # -- helpers --------------------------------------------------------
    def _next_odno(self) -> str:
        return str(next(self._numbers)).rjust(10, "0")

    def _rows(self, odnos: list[str], *, honour_live: bool) -> list[dict[str, str]]:
        """``odnos`` rendered as open-order rows, space-padded as observed.

        ``honour_live`` is the difference between the two phases. The POLL is
        scripted: "both" means the surface shows both legs, which is the whole
        point of the token, and the script says when that stops. CLEANUP is
        not scripted — its listing has to agree with what the cancels have
        actually done, or the walk would report a cancelled order as resting.
        """
        return [
            {
                # Space-padded to TEN, which is what the campaign artifacts
                # measure on this surface — the same width the accept
                # response zero-pads to (P-8-20260928T000506Z:
                # odno_wire_format, submit "0000000512" len 10, query
                # "       512" len 10). The width matters here: the cancel of
                # an unaccounted row is reconstructed by re-padding the row,
                # so a fake that padded to 11 would "prove" a reconstruction
                # the broker never accepted.
                "odno": odno.lstrip("0").rjust(10),
                "pdno": _SYMBOL,
                "ord_qty": "1",
                "tot_ccld_qty": "0",
                "qty": "1",
            }
            for odno in odnos
            if odno and (not honour_live or odno in self._live)
        ]

    def _next_token(self) -> str:
        script = self.cleanup_script if self.cleanup_phase else self.poll_script
        return script.pop(0) if len(script) > 1 else script[0]

    # -- transport ------------------------------------------------------
    def __call__(
        self,
        _session: Any,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> tuple[int, dict[str, Any], float, str]:
        body = json_body or {}
        self.calls.append({"url": url, "method": method, "body": body})
        if "quotations/inquire-price" in url:
            return 200, {"rt_cd": "0", "output1": {"futs_prpr": _LAST_PRICE}}, 1.0, "{}"
        if "trading/inquire-ccnl" in url:
            return self._inquire()
        if "trading/order-rvsecncl" in url:
            return self._rvsecncl(body)
        if url.endswith("trading/order"):
            if self.submit_raises is not None:
                if self.accept_before_raising:
                    # Accepted, resting, and the answer never came back.
                    self._original = self._next_odno()
                    self._live.add(self._original)
                # Everything after this is the probe's ``finally``: there is
                # no poll loop left to serve. The phase normally flips on the
                # first cancel, and after a lost SUBMIT there are no ODNOs to
                # cancel, so without this the book walk would be answered
                # from the poll script.
                self.cleanup_phase = True
                raise self.submit_raises
            if self.submit_rejects:
                return (
                    200,
                    {"rt_cd": "1", "msg1": "모의투자 주문이 불가한 계좌입니다."},
                    1.0,
                    "{}",
                )
            self._original = self._next_odno()
            self._live.add(self._original)
            return 200, {"rt_cd": "0", "output": {"ODNO": self._original}}, 1.0, "{}"
        raise AssertionError(f"unexpected probe URL: {url}")

    def _inquire(self) -> tuple[int, dict[str, Any], float, str]:
        token = self._next_token()
        self.inquiries.append(token)
        delay = self.delay_before.pop(len(self.inquiries), None)
        if delay:
            _REAL_SLEEP(delay)
        if token == "timeout":
            raise requests.exceptions.ReadTimeout(
                "HTTPSConnectionPool(host='openapivts.koreainvestment.com', "
                "port=29443): Read timed out. (read timeout=15.0)"
            )
        if token == "conn":
            raise requests.exceptions.ConnectionError(
                "HTTPSConnectionPool(host='openapivts.koreainvestment.com', "
                "port=29443): Max retries exceeded with url: "
                f"/uapi/domestic-futureoption/v1/trading/inquire-ccnl?CANO={_ACCOUNT}"
                f"&ACNT_PRDT_CD=03 (Caused by {_CONNECTION_ABORTED})"
            )
        if token == "chunked":
            raise requests.exceptions.ChunkedEncodingError(
                "Connection broken: IncompleteRead(31 bytes read)"
            )
        if token == "throttle":
            return 500, dict(_LEDGER_THROTTLE), 1.0, str(_LEDGER_THROTTLE)
        if token == "http429":
            return 429, {}, 1.0, "Too Many Requests"
        if token == "rt_cd_zero":
            rows = self._rows([self._new], honour_live=self.cleanup_phase)
            return 200, {"rt_cd": 0, "output1": rows}, 1.0, "{}"
        if token == "no_rows":
            # This broker's empty-set notation on the sibling balance surface:
            # a REJECTION shape, not rt_cd=0 with an empty list
            # (P-BAL-20260731T114344Z).
            payload = {
                "rt_cd": "7",
                "msg_cd": "KIOK0560",
                "msg1": "조회할 내용이 없습니다",
                "output1": [],
            }
            return 200, payload, 1.0, str(payload)
        if token == "egw00201":
            payload = {
                "rt_cd": "1",
                "msg_cd": "EGW00201",
                "msg1": "초당 거래건수를 초과하였습니다.",
            }
            return 200, payload, 1.0, str(payload)
        if token == "live":
            shown = sorted(self._live)
        elif token == "both":
            shown = [self._original, self._new]
        else:
            shown = [self._new]
        rows = self._rows(shown, honour_live=self.cleanup_phase)
        return 200, {"rt_cd": "0", "output1": rows}, 1.0, "{}"

    def _rvsecncl(self, body: dict[str, Any]) -> tuple[int, dict[str, Any], float, str]:
        if body.get("RVSE_CNCL_DVSN_CD") == "01":
            if self.amend_raises is not None:
                if self.accept_before_raising:
                    self._live.discard(self._original)
                    self._new = self._next_odno()
                    self._live.add(self._new)
                self.cleanup_phase = True
                raise self.amend_raises
            if self.amend_rejects:
                return (
                    200,
                    {"rt_cd": "1", "msg1": "모의투자 정정주문이 불가합니다."},
                    1.0,
                    "{}",
                )
            # The amend consumes the original's quantity and rests under a
            # new number — all five 2026-07-31 trials and both 09-28 trials.
            self._live.discard(self._original)
            self._new = self._next_odno()
            self._live.add(self._new)
            output = {} if self.amend_without_odno else {"ODNO": self._new}
            return (
                200,
                {
                    "rt_cd": "0",
                    "msg1": "모의투자 정정주문이 완료 되었습니다.",
                    "output": output,
                },
                1.0,
                "{}",
            )
        # A cancel. Everything from here on is cleanup.
        self.cleanup_phase = True
        origin = str(body.get("ORGN_ODNO", ""))
        if origin not in self._live:
            return 200, {"rt_cd": "1", "msg1": _NO_QTY}, 1.0, "{}"
        self._live.discard(origin)
        return (
            200,
            {"rt_cd": "0", "msg1": "모의투자 취소주문이 완료 되었습니다."},
            1.0,
            "{}",
        )


def _install(monkeypatch: pytest.MonkeyPatch, wire: _Wire) -> _Wire:
    monkeypatch.setattr(probes_order, "http_json", wire)
    monkeypatch.setattr(
        "shared.kis.auth.KISAuthManager", lambda *a, **k: _StubAuth(), raising=True
    )
    return wire


def _anchored(captured: str, prefix: str) -> list[str]:
    return [
        line[len(prefix) :] for line in captured.splitlines() if line.startswith(prefix)
    ]


def _retry_records(run: Any, phase: str | None = None) -> list[dict[str, Any]]:
    records = [
        obs["retry_evidence"] for obs in run.observations if "retry_evidence" in obs
    ]
    if phase is None:
        return records
    return [r for r in records if r["phase"] == phase]


# ---------------------------------------------------------------------------
# One transport failure is survivable
# ---------------------------------------------------------------------------


def test_one_transport_failure_mid_poll_is_retried_and_the_trial_completes(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The 2026-09-28 trial-2 shape, with the fix: poll, drop, poll again.

    Before this change the ``ConnectionError`` left ``probe_p8`` and ``run.py``
    wrote an artifact with one error string and no measurement.
    """
    _install(monkeypatch, _Wire(poll_script=["both", "conn", "both", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "none"
    assert "coexistence_ms" in run.measurements
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}
    retried = _retry_records(run, "coexistence_poll")
    assert [r["retried"] for r in retried] == [True]
    assert retried[0]["transient_kind"] == "transport"
    out = capsys.readouterr().out
    assert _anchored(out, _P8_STOP_PREFIX) == ["none"]
    assert _anchored(out, _P8_COEXISTENCE_PREFIX) == ["measured"]


def test_the_retry_waits_one_whole_effective_poll_interval(
    monkeypatch: pytest.MonkeyPatch, futures_env: None, defers: list[float]
) -> None:
    """``wait()`` alone owes only the remainder of a gap the failed attempt
    already armed before it went out — on a 15 s read timeout inside a 250 ms
    interval, nothing at all. ``defer`` re-measures the interval from now."""
    _install(monkeypatch, _Wire(poll_script=["both", "timeout", "both", "new_only"]))

    run = probe_p8(_args(poll_ms=250.0, pace_s=0.0))

    assert run.measurements["stop_reason"] == "none"
    assert defers == [0.25]


def test_the_retry_waits_the_pacing_floor_when_it_is_wider(
    monkeypatch: pytest.MonkeyPatch, futures_env: None, defers: list[float]
) -> None:
    """The pacer will not release two calls closer than ``--pace-s``, so a
    narrower ``--poll-ms`` is not the interval the retry has to wait out. Same
    number the artifact reports as ``poll_granularity_ms``."""
    _install(monkeypatch, _Wire(poll_script=["both", "timeout", "both", "new_only"]))

    run = probe_p8(_args(poll_ms=100.0, pace_s=1.1))

    assert defers == [pytest.approx(1.1)]
    assert run.measurements["poll_granularity_ms"] == pytest.approx(1100.0)


def test_a_ledger_throttle_is_transient_too(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """``EGW00215`` is the LEDGER's throttle, not ours. ``is_rate_limited``
    never sees it, so before this change it fell through to the poll's
    "rows is not a list" arm and silently read as "nothing is live"."""
    _install(monkeypatch, _Wire(poll_script=["both", "throttle", "both", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "none"
    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 1}


@pytest.mark.parametrize("token", ["timeout", "conn", "chunked"])
def test_the_transient_set_is_the_three_shapes_the_transport_can_fail_in(
    monkeypatch: pytest.MonkeyPatch, futures_env: None, token: str
) -> None:
    """A read timeout, a cut connection and a truncated body are all "no
    intact answer arrived", and none of them is our call rate."""
    _install(monkeypatch, _Wire(poll_script=["both", token, "both", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "none"
    assert run.measurements["retries"]["transport"] == 1


# ---------------------------------------------------------------------------
# Two in a row stop the TRIAL — and say "transport", not "rejected"
# ---------------------------------------------------------------------------


def test_two_consecutive_transport_failures_stop_the_trial_as_transport(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The stop exists; what changed is that it NAMES itself.

    The 09-28 runner could only see an exit code and an error count, and wrote
    "오류 1건(브로커 거부 포함)" over a stop in which the broker refused
    nothing.
    """
    _install(monkeypatch, _Wire(poll_script=["both", "conn", "conn", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "transient:transport"
    out = capsys.readouterr().out
    assert _anchored(out, _P8_STOP_PREFIX) == ["transient:transport"]
    assert _anchored(out, _P8_COEXISTENCE_PREFIX) == ["not_measured"]
    # Both transients recorded; only the first bought a retry.
    assert [r["retried"] for r in _retry_records(run, "coexistence_poll")] == [
        True,
        False,
    ]
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}


def test_a_stopped_poll_reports_no_coexistence_and_says_why(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """An unobserved interval is not a zero one.

    ``coexistence_ms`` is quoted as an UPPER bound on how long both legs
    survived, and a loop cut short saw an unknown part of it. Reporting the
    truncated value would read LOW — toward "the replace was atomic", which is
    the fail-open direction for ``B_protective_request_complete``.
    """
    _install(monkeypatch, _Wire(poll_script=["both", "conn", "conn", "new_only"]))

    run = probe_p8(_args())

    assert "coexistence_ms" not in run.measurements
    assert "mode_determination" not in run.measurements
    skipped = [s for s in run.skips if s["what"] == "measurements.coexistence_ms"]
    assert skipped and "ABORTED" in skipped[0]["reason"]
    assert "stop_reason=transient:transport" in skipped[0]["reason"]
    # This one DID stop short, and says so — the other half of the pair.
    assert "did NOT elapse" in skipped[0]["reason"]
    assert any("NOT a broker rejection" in e for e in run.errors)
    # The partial sighting is kept as an observation, not promoted.
    assert any(o.get("coexistence_seen_before_stop") for o in run.observations)


def test_a_doubled_ledger_throttle_stops_the_trial_as_transient(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Same shape as the rate-limit case, and the same manufactured value.

    Measured on ``origin/main``: two ``EGW00215`` answers produced
    ``coexistence_ms: 0.29``, ``errors: []``, ``provenance_class: MEASURED``.
    The throttled body carries no ``output1``, the loop read that as "the
    original leg is gone", and the interval it then reported was the single
    poll that had actually answered.
    """
    _install(
        monkeypatch, _Wire(poll_script=["both", "throttle", "throttle", "new_only"])
    )

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "transient:ledger_throttle"
    assert _anchored(capsys.readouterr().out, _P8_STOP_PREFIX) == [
        "transient:ledger_throttle"
    ]
    assert "coexistence_ms" not in run.measurements


def test_the_facts_the_amend_response_established_survive_a_transport_stop(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """``P-8-20260928T000658Z`` lost ``replace_issues_new_odno`` to a failure
    that happened AFTER the broker had answered it: the amend was accepted and
    558 had already become 560. Those two come from the amend response, so
    they are recorded before the poll can stop."""
    _install(monkeypatch, _Wire(poll_script=["both", "conn", "conn", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["replace_issues_new_odno"] is True
    assert run.measurements["replace_rejected"] is False


def test_the_transport_excerpt_never_carries_the_request_query_string(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """``requests`` renders the failed URL in full and that URL carries CANO.
    ``redact()`` keys on field NAMES and cannot reach inside a raw string, and
    these artifacts are committed under ``docs/broker-profiles/evidence/``."""
    _install(monkeypatch, _Wire(poll_script=["both", "conn", "conn", "new_only"]))

    run = probe_p8(_args())

    blobs = " ".join(str(r) for r in _retry_records(run))
    assert _ACCOUNT not in blobs
    assert "CANO" not in blobs
    assert "ConnectionError" in blobs
    assert "<redacted>" in blobs


# ---------------------------------------------------------------------------
# Our own call rate is NOT transient — regression pins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", ["http429", "egw00201"])
def test_a_rate_limit_still_stops_at_once_with_no_retry(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
    token: str,
) -> None:
    """Pins the rule the 2026-09-17 incident bought, byte for byte.

    HTTP 429 and ``EGW00201`` mean WE called too fast, and the harness protects
    the account by stopping. The policy widening in this PR must not reach
    them: there is exactly one call for the failing poll, no retry record, and
    the series-level token is ``rate_limited``, which the runner stops on.

    The absent ``coexistence_ms`` is not a pin but a fix, and the worse half
    of this defect. Before the change the poll loop never looked at ``rt_cd``
    at all: a refusal carries no ``output1``, so it read as "no legs are
    live", which is the loop's own signal that coexistence has ENDED. Measured
    on ``origin/main``, a 429 on poll 2 produced ``coexistence_ms: 0.17`` with
    ``errors: []`` and ``provenance_class: MEASURED`` — a number nobody
    observed, in the direction that says the replace was atomic.
    """
    wire = _install(monkeypatch, _Wire(poll_script=["both", token, "both", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "rate_limited"
    assert _anchored(capsys.readouterr().out, _P8_STOP_PREFIX) == ["rate_limited"]
    assert _retry_records(run, "coexistence_poll") == []
    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 0}
    assert "coexistence_ms" not in run.measurements
    assert "mode_determination" not in run.measurements
    # The failing poll was issued ONCE. (The listings after it belong to
    # cleanup, which starts at the first cancel.)
    assert wire.inquiries[:2] == ["both", token]


def test_a_rate_limit_body_that_also_carries_the_ledger_code_still_stops(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Precedence, not coincidence: one answer can carry both signals, and the
    account-protection rule has to win. The two paths disagreed about this
    once already (#825 independent review F4)."""
    assert (
        common.classify_answer(429, {"msg_cd": "EGW00215"}, "Too Many Requests")
        == common.STATUS_RATE_LIMITED
    )


# ---------------------------------------------------------------------------
# Order-mutating calls are classified, never retried
# ---------------------------------------------------------------------------


def test_a_lost_submit_stops_the_series_and_cancels_what_it_orphaned(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Review F1, the serious one.

    A ``ReadTimeout`` on the submit says only that no ANSWER came back. The
    broker may have accepted the order and be resting it right now, under an
    ODNO this probe never saw — so ``odnos`` is empty, ``_cleanup`` cancels
    nothing, and the first version of this PR let the runner start trial N+1
    on top of it, up to ``P8_MAX_TRANSIENT_STOPS`` resting orders deep. Before
    the PR the escape at least stopped the series (rc 5).

    So: the series stops, AND the book is walked and the orphan cancelled.
    """
    wire = _install(
        monkeypatch,
        _Wire(
            submit_raises=requests.exceptions.ConnectionError(
                f"Max retries exceeded with url: /uapi/x?CANO={_ACCOUNT} "
                f"(Caused by {_CONNECTION_ABORTED})"
            ),
            accept_before_raising=True,
        ),
    )

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "order_state_unknown"
    assert _anchored(capsys.readouterr().out, _P8_STOP_PREFIX) == [
        "order_state_unknown"
    ]
    # Not resent: a second submit is the duplicate-order hazard P-2 measures.
    assert len([c for c in wire.calls if c["url"].endswith("trading/order")]) == 1
    assert [r["phase"] for r in _retry_records(run)] == ["submit"]

    found = run.measurements["unaccounted_live_orders"]
    assert found["status"] == "FOUND"
    assert found["canonical_keys"] == ["558"]
    assert list(found["cleanup_dispositions"].values()) == [_CLEANUP_CANCELLED]
    assert any("UNACCOUNTED LIVE ORDER" in e for e in run.errors)
    # And it really is gone from the book.
    assert wire._live == set()
    assert _ACCOUNT not in " ".join(run.errors)


def test_a_lost_amend_does_not_count_the_known_original_as_orphaned(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The amend consumed the original and rests under a number the probe
    never saw. ``_cleanup`` handles the original (it is known); the walk must
    find only the NEW leg, or the operator is sent after a row that already
    has a disposition of its own."""
    wire = _install(
        monkeypatch,
        _Wire(
            amend_raises=requests.exceptions.ReadTimeout("read timeout=15.0"),
            accept_before_raising=True,
        ),
    )

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "order_state_unknown"
    assert [r["phase"] for r in _retry_records(run)] == ["amend"]
    # The original was known, so _cleanup owned it...
    assert list(run.measurements["cleanup_dispositions"].values()) == [
        _CLEANUP_NOTHING_TO_CANCEL
    ]
    # ...and only the leg nobody saw is reported as unaccounted.
    found = run.measurements["unaccounted_live_orders"]
    assert found["status"] == "FOUND"
    assert found["canonical_keys"] == ["559"]
    assert wire._live == set()


def test_a_lost_submit_that_orphaned_nothing_says_so(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """ "The walk ran and the book was clean" is what lets the operator stop
    looking, so it has to be written down. Silence would be the same shape as
    no walk at all."""
    _install(
        monkeypatch,
        _Wire(
            submit_raises=requests.exceptions.ReadTimeout("read timeout=15.0"),
            accept_before_raising=False,
        ),
    )

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "order_state_unknown"
    found = run.measurements["unaccounted_live_orders"]
    assert found["status"] == "NONE_FOUND"
    assert not any("UNACCOUNTED LIVE ORDER" in e for e in run.errors)


def test_a_book_walk_that_cannot_answer_cancels_nothing_and_says_to_look(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Fail-closed, the same polarity cleanup uses: a walk that established
    nothing must not be read as "nothing is resting", and it must certainly
    not license cancelling rows it never saw."""
    wire = _install(
        monkeypatch,
        _Wire(
            submit_raises=requests.exceptions.ReadTimeout("read timeout=15.0"),
            accept_before_raising=True,
            cleanup_script=["conn"],
        ),
    )

    run = probe_p8(_args())

    found = run.measurements["unaccounted_live_orders"]
    assert found["status"] == "UNDETERMINED"
    assert found["liveness_evidence"]["outcome"] == "QUERY_NOT_AN_ANSWER"
    assert any("check 555" not in e for e in run.errors)
    assert any("by hand" in e for e in run.errors)
    # Nothing was cancelled, and the order is still on the book.
    assert wire._live != set()


def test_the_quote_phase_still_continues_because_nothing_is_resting(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The split F1 draws is "is an order's state unknown", not "is it a
    POST". The quote fails before anything is placed, so the next trial starts
    from a clean account and the series may continue."""
    wire = _install(monkeypatch, _Wire())
    monkeypatch.setattr(
        probes_order.MockTradingClient,
        "futures_last_price",
        lambda self, symbol: (_ for _ in ()).throw(
            requests.exceptions.ReadTimeout("read timeout=15.0")
        ),
    )

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "transient:transport"
    assert _anchored(capsys.readouterr().out, _P8_STOP_PREFIX) == [
        "transient:transport"
    ]
    assert [c for c in wire.calls if c["url"].endswith("trading/order")] == []
    assert "unaccounted_live_orders" not in run.measurements
    errors = " ".join(run.errors)
    assert "price lookup" in errors
    assert "duplicate-order hazard" not in errors


def test_each_unretried_phase_gives_its_own_reason(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Three phases, three reasons, no shared sentence that is false for one
    of them."""
    assert set(probes_order._P8_NO_RETRY_REASON) == {"quote", "submit", "amend"}
    _install(
        monkeypatch,
        _Wire(amend_raises=requests.exceptions.ReadTimeout("read timeout=15.0")),
    )

    run = probe_p8(_args())

    assert any("consume the original's quantity twice" in e for e in run.errors)
    assert not any("price lookup" in e for e in run.errors)


def test_a_query_rejection_mid_poll_does_not_end_the_coexistence_interval(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The other half of the manufactured-value defect, and the half
    ``classify_answer`` does not catch.

    A rejection carries no ``output1``, and the loop reads rows — so before
    this change ``rt_cd='7'`` + ``KIOK0560`` read as "no legs are live", which
    is the loop's own signal that coexistence has ENDED. It is not a rate
    limit, so the 429/``EGW00215`` arms never see it.

    It is recorded and SKIPPED rather than stopped on: whether this surface
    switches to a rejection shape once the book is empty has never been
    measured here, and stopping on it would abort a normal end-of-coexistence
    on an unmeasured hunch.
    """
    _install(
        monkeypatch,
        _Wire(poll_script=["both", "no_rows", "both", "new_only"]),
    )

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "none"
    assert run.measurements["coexistence_polls_not_answered"] == 1
    assert run.measurements["coexistence_polls_answered"] == 3
    # The interval survived the hole: the mark was set on poll 1, untouched on
    # poll 2, set again on poll 3, and only poll 4 ended it.
    assert run.measurements["coexistence_ms"] > 0.0
    recorded = [o for o in run.observations if "coexistence_poll_not_answered" in o]
    assert len(recorded) == 1
    assert recorded[0]["coexistence_poll_not_answered"]["msg_cd"] == "KIOK0560"


def test_a_poll_series_that_never_answers_reports_no_coexistence(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Nothing came back ``rt_cd=0`` for the whole window. Before the change
    that was ``coexistence_ms: 0.0`` with ``errors: []`` — "the replace was
    atomic", observed by nothing."""
    _install(monkeypatch, _Wire(poll_script=["no_rows"]))

    run = probe_p8(_args(visibility_timeout_s=0.3))

    assert run.measurements["stop_reason"] == "query_unanswered"
    assert "coexistence_ms" not in run.measurements
    assert "mode_determination" not in run.measurements
    assert run.measurements["coexistence_polls_answered"] == 0
    polls = run.measurements["coexistence_polls_not_answered"]
    assert polls > 0
    assert run.measurements["coexistence_not_answered_codes"] == {"KIOK0560": polls}
    out = capsys.readouterr().out
    assert _anchored(out, _P8_STOP_PREFIX) == ["query_unanswered"]
    # The window DID elapse here — nothing in it answered. Saying it did not
    # is the 2026-09-17 P-CA error, and the two-way ternary this replaced said
    # exactly that, plus "the stop is our own call rate", over a stop that was
    # neither.
    skipped = [s for s in run.skips if s["what"] == "measurements.coexistence_ms"]
    assert skipped and "DID elapse" in skipped[0]["reason"]
    assert "did NOT elapse" not in skipped[0]["reason"]
    # The false sentence, verbatim as the old ternary emitted it. (The real
    # message does mention the call rate — to say it was NOT the problem.)
    assert not any("The stop is our own call rate" in e for e in run.errors)
    assert any("answered rt_cd!=0 to every poll" in e for e in run.errors)


def test_the_unanswered_evidence_is_bounded_by_distinct_codes_not_by_polls(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """With ``--pace-s 0`` this loop runs tens of thousands of times a second
    — measured at 12,265 polls in a 0.3 s window — and one observation per
    poll would put a list that size into a committed artifact.

    One verbatim record per distinct ``msg_cd``; the counts are kept in full.
    """
    _install(monkeypatch, _Wire(poll_script=["no_rows"]))

    run = probe_p8(_args(visibility_timeout_s=0.3))

    recorded = [o for o in run.observations if "coexistence_poll_not_answered" in o]
    assert len(recorded) == 1
    polls = run.measurements["coexistence_polls_not_answered"]
    assert polls > 100, polls  # the loop really did spin
    assert run.measurements["coexistence_not_answered_codes"]["KIOK0560"] == polls


def test_a_stop_narration_exists_for_every_stop_the_poll_can_report() -> None:
    """A lookup with a missing key is a KeyError inside the ``finally``'s
    sibling path. Pin the three prefixes the loop can actually return."""
    assert set(probes_order._P8_STOP_NARRATION) == {
        probes_order._P8_STOP_TRANSIENT,
        probes_order._P8_STOP_RATE_LIMITED,
        probes_order._P8_STOP_QUERY_UNANSWERED,
    }


def test_a_transport_failure_on_the_quote_is_its_own_phase(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Nothing is resting yet, so this is a different fact from a failed
    submit. A reader told "submit" would go looking for an order that was
    never placed."""
    wire = _install(monkeypatch, _Wire())
    monkeypatch.setattr(
        probes_order.MockTradingClient,
        "futures_last_price",
        lambda self, symbol: (_ for _ in ()).throw(
            requests.exceptions.ReadTimeout("read timeout=15.0")
        ),
    )

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "transient:transport"
    assert [r["phase"] for r in _retry_records(run)] == ["quote"]
    assert _anchored(capsys.readouterr().out, _P8_STOP_PREFIX) == [
        "transient:transport"
    ]
    # No order was placed, so there is nothing to clean up and no disposition.
    assert [c for c in wire.calls if c["url"].endswith("trading/order")] == []
    assert "cleanup_dispositions" not in run.measurements
    # And the reason given is the QUOTE's reason. Saying "an order-mutating
    # call is never retried" about a GET is the same false-sentence shape as
    # the stop narration.
    errors = " ".join(run.errors)
    assert "price lookup" in errors
    assert "duplicate-order hazard" not in errors


def test_a_rejected_submit_is_still_a_rejection(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The one stop the "재시도 금지" rule was written for: 2026-09-11 and
    2026-09-16 both died here, and every remaining trial would have too."""
    _install(monkeypatch, _Wire(submit_rejects=True))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "rejected"
    assert _anchored(capsys.readouterr().out, _P8_STOP_PREFIX) == ["rejected"]
    assert any("submit rejected" in e for e in run.errors)


def test_a_dry_run_names_itself_rather_than_looking_like_a_clean_trial(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The runner always passes ``--confirm``; a ``dry_run`` token reaching it
    means the invocation and the runner disagree, and it stops."""
    _install(monkeypatch, _Wire())

    probe_p8(_args(confirm=False))

    assert _anchored(capsys.readouterr().out, _P8_STOP_PREFIX) == ["dry_run"]


# ---------------------------------------------------------------------------
# Cleanup keeps its guarantees
# ---------------------------------------------------------------------------


def test_cleanup_still_runs_and_is_still_recorded_after_a_transport_stop(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The ``finally`` is the reason the 09-28 trial left no order on the book
    despite dying mid-poll, and it has to stay that way. #732: the cleanup
    disposition is also what distinguishes a superseded original from one that
    is still resting."""
    _install(monkeypatch, _Wire(poll_script=["both", "conn", "conn", "new_only"]))

    run = probe_p8(_args())

    dispositions = list(run.measurements["cleanup_dispositions"].values())
    assert dispositions == [_CLEANUP_NOTHING_TO_CANCEL, _CLEANUP_CANCELLED]
    assert "cleanup_liveness_note" in run.measurements
    assert "amend_consumption_note" in run.measurements


def test_cleanup_still_runs_after_a_transport_failure_on_the_amend(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The submit succeeded, so an order IS resting; the amend never answered.
    The ``finally`` must cancel it rather than hand the operator an
    unaccounted-for order."""
    _install(
        monkeypatch,
        _Wire(amend_raises=requests.exceptions.ReadTimeout("read timeout=15.0")),
    )

    run = probe_p8(_args())

    assert list(run.measurements["cleanup_dispositions"].values()) == [
        _CLEANUP_CANCELLED
    ]


def test_the_cleanup_liveness_walk_survives_one_transport_failure(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """A walk that cannot answer counts the order as LIVE and raises an error
    telling the operator to cancel by hand — the opposite polarity to
    ``coexistence_ms``. One dropped connection should not cost that."""
    _install(
        monkeypatch,
        _Wire(
            poll_script=["both", "new_only"],
            cleanup_script=["conn", "new_only"],
        ),
    )

    run = probe_p8(_args())

    assert list(run.measurements["cleanup_dispositions"].values()) == [
        _CLEANUP_NOTHING_TO_CANCEL,
        _CLEANUP_CANCELLED,
    ]
    assert [r["retried"] for r in _retry_records(run, "cleanup_liveness")] == [True]


def test_two_transport_failures_in_the_cleanup_walk_count_the_order_as_live(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Fail-closed in the other direction: not knowing is not "not live", and
    the operator hears about it."""
    _install(
        monkeypatch,
        _Wire(poll_script=["both", "new_only"], cleanup_script=["conn"]),
    )

    run = probe_p8(_args())

    rejected = [
        o
        for o in run.observations
        if o.get("liveness_evidence", {}).get("outcome") == "QUERY_NOT_AN_ANSWER"
    ]
    assert rejected
    assert rejected[0]["liveness_evidence"]["status_kind"] == "TRANSIENT:transport"
    assert any("CLEANUP FAILED" in e for e in run.errors)


# ---------------------------------------------------------------------------
# The window bounds the retry
# ---------------------------------------------------------------------------


def test_a_window_that_never_opened_measures_nothing(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Review F2: zero polls is zero observations, whatever the stop says.

    With ``--visibility-timeout-s 0`` the loop never runs. ``answered`` and
    ``unanswered`` are both 0, so the ``query_unanswered`` guard does not
    fire and the run came out ``stop=none``, ``measured=True``,
    ``coexistence_ms: 0.0`` — a MEASURED artifact asserting an atomic replace
    off a window that never opened, which the runner then counted toward
    N>=5. The gate is ``answered > 0``, not "did something stop me".
    """
    _install(monkeypatch, _Wire(poll_script=["conn", "both", "new_only"]))

    run = probe_p8(_args(visibility_timeout_s=0.0))

    assert _retry_records(run, "coexistence_poll") == []
    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 0}
    # The loop never entered, so this is the natural end, not a stop...
    assert run.measurements["stop_reason"] == "none"
    # ...and it measured nothing.
    assert "coexistence_ms" not in run.measurements
    assert "mode_determination" not in run.measurements
    assert _anchored(capsys.readouterr().out, _P8_COEXISTENCE_PREFIX) == [
        "not_measured"
    ]
    skipped = [s for s in run.skips if s["what"] == "measurements.coexistence_ms"]
    assert skipped and "not one poll came back rt_cd=0" in skipped[0]["reason"]


def test_a_rejected_amend_measures_no_coexistence(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Review F3: no replace happened, so there is no interval.

    A rejected amend issues no new ODNO, so ``both`` can never be true and
    ``coexist_last`` stays None — which used to be written out as
    ``coexistence_ms: 0.0`` and counted by the runner as an agreeing "atomic"
    sample. ``replace_rejected`` is still measured; it is the INTERVAL that
    was not.
    """
    _install(monkeypatch, _Wire(amend_rejects=True))

    run = probe_p8(_args(visibility_timeout_s=0.1))

    assert run.measurements["replace_rejected"] is True
    assert run.measurements["replace_issues_new_odno"] is False
    assert run.measurements["stop_reason"] == "none"
    assert "coexistence_ms" not in run.measurements
    assert "mode_determination" not in run.measurements
    assert _anchored(capsys.readouterr().out, _P8_COEXISTENCE_PREFIX) == [
        "not_measured"
    ]
    skipped = [s for s in run.skips if s["what"] == "measurements.coexistence_ms"]
    assert skipped and "REJECTED the amend" in skipped[0]["reason"]


def test_an_accepted_amend_with_no_new_odno_measures_no_coexistence(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """``rt_cd=0`` with no ``output.ODNO``: the second leg the measurement
    compares against never existed, so neither did the interval."""
    _install(monkeypatch, _Wire(amend_without_odno=True))

    run = probe_p8(_args(visibility_timeout_s=0.1))

    assert run.measurements["replace_rejected"] is False
    assert run.measurements["replace_issues_new_odno"] is False
    assert "coexistence_ms" not in run.measurements
    skipped = [s for s in run.skips if s["what"] == "measurements.coexistence_ms"]
    assert skipped and "no new ODNO was issued" in skipped[0]["reason"]


def test_a_transient_after_the_deadline_says_the_window_elapsed(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Review F4, the case ``can_retry`` exists for, now actually exercised.

    Window 0.05 s, poll 1 answers, poll 2 burns 0.12 s and then fails. The
    transient surfaces AFTER the deadline, so the retry is refused — and the
    window was spent in FULL. The narration said "did NOT elapse", which is
    the 2026-09-17 P-CA error. The committed test for this used a 0 s window,
    where the loop never enters and the path is never taken.
    """
    _install(
        monkeypatch,
        _Wire(poll_script=["both", "conn", "new_only"], delay_before={2: 0.12}),
    )

    run = probe_p8(_args(visibility_timeout_s=0.05, poll_ms=1.0))

    assert run.measurements["stop_reason"] == "transient:transport"
    skipped = [s for s in run.skips if s["what"] == "measurements.coexistence_ms"]
    assert skipped and "DID elapse" in skipped[0]["reason"]
    assert "did NOT elapse" not in skipped[0]["reason"]
    # One transient, refused for the window rather than for being the second.
    records = _retry_records(run, "coexistence_poll")
    assert [r["retried"] for r in records] == [False]
    assert records[0]["not_retried_because"] == "window_already_closed"


def test_a_second_consecutive_transient_names_that_reason_instead(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The other refusal. Both used to carry only ``retried: false``, and a
    reader counting unhealthy links cannot add them together: one means the
    broker failed twice, the other means it failed once, late."""
    _install(monkeypatch, _Wire(poll_script=["both", "conn", "conn", "new_only"]))

    run = probe_p8(_args())

    records = _retry_records(run, "coexistence_poll")
    assert [r["retried"] for r in records] == [True, False]
    assert "not_retried_because" not in records[0]
    assert records[1]["not_retried_because"] == "second_consecutive_transient"
    skipped = [s for s in run.skips if s["what"] == "measurements.coexistence_ms"]
    assert "did NOT elapse" in skipped[0]["reason"]


def test_a_rate_limited_stop_records_the_envelope_it_points_at(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Review F5: the narration told the reader to see ``retry_evidence``,
    which ``retry_once`` writes only for TRANSIENTS — so the one stop with no
    record was the one pointing at it."""
    _install(monkeypatch, _Wire(poll_script=["both", "egw00201", "new_only"]))

    run = probe_p8(_args())

    recorded = [o for o in run.observations if "coexistence_poll_rate_limited" in o]
    assert len(recorded) == 1
    envelope = recorded[0]["coexistence_poll_rate_limited"]
    assert envelope["msg_cd"] == "EGW00201"
    assert envelope["rt_cd"] == "1"
    assert any("coexistence_poll_rate_limited" in e for e in run.errors)


def test_a_rate_limited_cleanup_walk_keeps_the_envelope_too(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Same regression on the other surface: an HTTP-200 ``EGW00201`` body
    used to land in the ``rt_cd!=0`` branch with its fields recorded, and now
    lands in the classified branch, which kept only ``status_kind``."""
    _install(
        monkeypatch,
        _Wire(poll_script=["both", "new_only"], cleanup_script=["egw00201"]),
    )

    run = probe_p8(_args())

    walks = [
        o["liveness_evidence"]
        for o in run.observations
        if o.get("liveness_evidence", {}).get("outcome") == "QUERY_NOT_AN_ANSWER"
    ]
    assert walks
    assert walks[0]["msg_cd"] == "EGW00201"
    assert walks[0]["rt_cd"] == "1"
    assert walks[0]["status_kind"] == "RATE_LIMITED"


def test_a_numeric_zero_rt_cd_is_a_healthy_answer(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Review F6: ``str(x or "")`` turns the JSON NUMBER ``0`` into ``""``,
    so a successful page read as a refusal — and a whole window of them would
    have stopped the series as ``query_unanswered``. ``call_evidence`` in this
    same PR documents the trap; the poll loop had re-introduced it."""
    _install(monkeypatch, _Wire(poll_script=["both", "rt_cd_zero", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "none"
    assert run.measurements["coexistence_polls_not_answered"] == 0
    assert run.measurements["coexistence_polls_answered"] >= 2
    assert "coexistence_ms" in run.measurements


# ---------------------------------------------------------------------------
# The runner template
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNERS_DIR = _REPO_ROOT / "tools" / "broker_probes" / "runners"
_RUNNER = _RUNNERS_DIR / "run_p8.sh"
_RUNNER_COMMON = _RUNNERS_DIR / "_common.sh"

#: Sourcing the credential file would print this. A guard that fires "before
#: any credential sourcing" is only worth the words if its absence is
#: observable.
_CREDENTIAL_SENTINEL = "CREDENTIAL_FILE_WAS_SOURCED"


def test_runner_template_is_tracked_and_executable() -> None:
    """The 2026-09-28 runner was neither, and it is gone: the only record of
    what it decided is one wrong sentence in the campaign README."""
    assert _RUNNER.is_file(), _RUNNER
    assert os.access(_RUNNER, os.X_OK), f"{_RUNNER} is not executable"


def test_runner_template_parses() -> None:
    result = subprocess.run(
        ["bash", "-n", str(_RUNNER)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_runner_template_passes_shellcheck() -> None:
    """On CI a missing shellcheck is a FAILURE, not a skip — and each file is
    checked ON ITS OWN.

    Two lessons, both paid for. The P-CA template's lint gate skipped on every
    developer host and its first real run was the CI job that failed the
    branch (plan §7.10). Then this gate passed locally on three files handed
    to shellcheck TOGETHER and failed on CI, which checked one: with several
    inputs shellcheck resolved a variable written in a runner and read in
    ``_common.sh``, and with one input it reported SC2034. A gate whose
    verdict depends on how many files you hand it is not a gate, so each file
    is checked alone AND the set is checked together.
    """
    shellcheck = shutil.which("shellcheck")
    if shellcheck is None:
        if os.environ.get("CI"):
            pytest.fail(
                "shellcheck is missing on CI, where this gate is meant to run; "
                "add it to the workflow rather than letting the check vanish"
            )
        pytest.skip("shellcheck is not installed locally — CI runs this gate")
    for argv in ([_RUNNER], [_RUNNER_COMMON], [_RUNNER, _RUNNER_COMMON]):
        result = subprocess.run(
            [shellcheck, "--severity=warning", *(str(f) for f in argv)],
            capture_output=True,
            text=True,
        )
        assert (
            result.returncode == 0
        ), f"{[f.name for f in argv]}: {result.stdout}{result.stderr}"


def test_runner_template_carries_no_instance_defaults() -> None:
    """Every ``P8_*`` instance value is read WITHOUT a ``:-`` default. A
    default is how one trial's symbol, window or fingerprint silently becomes
    the next trial's."""
    text = _RUNNER.read_text(encoding="utf-8")
    pairs = set(re.findall(r"\$\{(P8_[A-Z_]+):-([^}]*)\}", text))
    assert {name for name, default in pairs if default not in ("", "0")} == set(), pairs
    assert {name for name, _default in pairs} <= {
        "P8_ALLOW_SHARED_CHECKOUT",
        "P8_CRON_MARK",
        "P8_LOG",
    }, pairs


def test_runner_template_never_removes_itself() -> None:
    """The 2026-09-30 P-CA runner self-deleted after its first run, so attempts
    3 and 4 went out through a hand-made copy."""
    text = _RUNNER.read_text(encoding="utf-8")
    destructive = re.search(
        r"(?<![\w-])(rm|unlink|mv|shred|truncate)(?![\w-])|:\s*>[^>]", text
    )
    assert destructive is None, f"the runner runs a destructive command: {destructive}"
    self_references = [
        line for line in text.splitlines() if "$0" in line and "awk" not in line
    ]
    assert len(self_references) == 1, self_references
    assert "SCRIPT_DIR=" in self_references[0], self_references


def test_the_runner_expects_the_policy_version_the_probe_reports() -> None:
    """The handshake is only a handshake if the two literals agree today."""
    text = _RUNNER.read_text(encoding="utf-8")
    assert f"EXPECT_POLICY_VERSION={POLICY_VERSION}" in text


def test_the_runner_reads_the_prefixes_the_probe_prints() -> None:
    """The contract is two anchored lines. If the probe renames one, this
    breaks here rather than in a cron slot at 09:05 KST."""
    text = _RUNNER.read_text(encoding="utf-8")
    assert f"s/^{_P8_STOP_PREFIX}//p" in text
    assert f"s/^{_P8_COEXISTENCE_PREFIX}//p" in text


def _runner_repo(tmp_path: Path, *, detached: bool, dirty: bool) -> Path:
    """A throwaway git checkout holding a copy of the template, so the guards
    run against a real ``git`` rather than a stub."""
    repo = tmp_path / "repo"
    (repo / "tools" / "broker_probes" / "runners").mkdir(parents=True)
    shutil.copy2(_RUNNER, repo / "tools/broker_probes/runners/run_p8.sh")
    shutil.copy2(_RUNNER_COMMON, repo / "tools/broker_probes/runners/_common.sh")
    (repo / "tools/broker_probes/probes_order.py").write_text("", encoding="utf-8")
    shutil.copy2(_REPO_ROOT / ".gitignore", repo / ".gitignore")

    def git(*argv: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *argv],
            check=True,
            capture_output=True,
            text=True,
        )

    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)], check=True, capture_output=True
    )
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    git("add", "-A")
    git("commit", "-q", "-m", "runner")
    if detached:
        git("checkout", "-q", "--detach", "HEAD")
    if dirty:
        (repo / "untracked.txt").write_text("x", encoding="utf-8")
    return repo


def _publish_origin_main(repo: Path, ref: str = "HEAD") -> None:
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", ref],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", sha],
        check=True,
        capture_output=True,
    )


def _base_env(tmp_path: Path, repo: Path) -> dict[str, str]:
    env_file = tmp_path / "creds.env"
    env_file.write_text(f"echo {_CREDENTIAL_SENTINEL}\n", encoding="utf-8")
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "P8_LOG": str(tmp_path / "run.log"),
        "P8_CREDENTIAL_FILE": str(env_file),
        "P8_SYMBOL": _SYMBOL,
        "P8_TRIALS": "5",
        "P8_QUANTITY": "1",
        "P8_PRICE_OFFSET_PCT": "10.0",
        "P8_POLL_MS": "200",
        "P8_PACE_S": "1.1",
        "P8_VISIBILITY_TIMEOUT_S": "30",
        "P8_INTER_TRIAL_S": "0",
        "P8_MAX_TRANSIENT_STOPS": "2",
        "P8_EXPECT_KEY_FP": "deadbeefcafe",
        "P8_EXPECT_ACCOUNT_FP": "0123456789ab",
        "P8_TOKEN_CACHE": str(tmp_path / "token-cache"),
        "P8_EVIDENCE_DIR": str(tmp_path),
        "P8_NOTE": "runner guard test",
    }


def _run_runner(repo: Path, tmp_path: Path, **extra: str) -> Any:
    env = _base_env(tmp_path, repo)
    env.update(extra)
    return subprocess.run(
        ["bash", str(repo / "tools/broker_probes/runners/run_p8.sh")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )


def test_runner_aborts_on_a_checkout_that_is_not_detached(tmp_path: Path) -> None:
    """#793: a shared checkout lets a parallel lane move the branch under a
    running probe, and ``repo_commit`` is then stamped with a non-main commit.
    The 2026-09-28 run got this right and the artifact says so; the guard is
    here so the next one cannot get it wrong."""
    result = _run_runner(_runner_repo(tmp_path, detached=False, dirty=False), tmp_path)

    assert result.returncode != 0
    assert "ABORT:" in result.stdout
    assert "not a detached worktree" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def test_runner_aborts_on_a_dirty_checkout(tmp_path: Path) -> None:
    result = _run_runner(_runner_repo(tmp_path, detached=True, dirty=True), tmp_path)

    assert result.returncode != 0
    assert "is dirty" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def test_runner_aborts_when_head_is_not_an_ancestor_of_origin_main(
    tmp_path: Path,
) -> None:
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    (repo / "extra.txt").write_text("x", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "ahead"],
        check=True,
        capture_output=True,
    )
    _publish_origin_main(repo, "HEAD~1")

    result = _run_runner(repo, tmp_path)

    assert result.returncode != 0
    assert "is not an ancestor of origin/main" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def test_runner_accepts_a_clean_detached_ancestor_checkout(tmp_path: Path) -> None:
    """The guards must PASS on the shape the README prescribes, or they are
    just a way of never running."""
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)

    result = _run_runner(repo, tmp_path)

    assert "checkout ok:" in result.stdout
    assert "ABORT: required env P8_PYTHON is unset" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


@pytest.mark.parametrize("bad", ["0", "-1", "two", ""])
def test_runner_refuses_a_trial_count_that_is_not_a_positive_integer(
    tmp_path: Path, bad: str
) -> None:
    """``[ "$trial" -le "$P8_TRIALS" ]`` on a non-number is a shell diagnostic
    mid-series, not a reason."""
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)

    # P8_PYTHON only so require_env gets past it: the shape check below runs
    # before the interpreter is ever used.
    result = _run_runner(repo, tmp_path, P8_TRIALS=bad, P8_PYTHON="/bin/true")

    assert result.returncode != 0
    assert "P8_TRIALS" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


# ---------------------------------------------------------------------------
# The runner's STOP rule, end to end
# ---------------------------------------------------------------------------


def _fake_python(tmp_path: Path, *, script: list[str], dump: Path) -> Path:
    """A stand-in interpreter answering the three calls the runner makes.

    It lives OUTSIDE the checkout, like the real one: a freshly added detached
    worktree has no ``.venv``, and installing one into it is forbidden, so the
    runner takes ``P8_PYTHON`` and proves separately that the code it loads is
    this checkout's.

    ``script`` has one entry per probe invocation, ``"<rc>|<stdout lines, ~
    separated>"``; the last entry repeats. Each invocation also drops an
    artifact in ``FAKE_RESULTS_DIR``, so the copy path is exercised.
    """
    script_file = tmp_path / "probe-script.txt"
    script_file.write_text("\n".join(script) + "\n", encoding="utf-8")
    counter = tmp_path / "probe-count.txt"
    body = f"""#!/bin/sh
case "$1" in
  -c)
    case "$2" in
      *__file__*) printf "%s\\n%s\\n" "$FAKE_MODULE_PATH" "$FAKE_POLICY_VERSION" ;;
      *) printf "%s\\n" "$P8_EXPECT_ACCOUNT_FP" ;;
    esac
    ;;
  -m)
    for a in "$@"; do printf "%s\\n" "$a" >> {str(dump)!r}; done
    printf -- "--- end of invocation\\n" >> {str(dump)!r}
    n=$(cat {str(counter)!r} 2>/dev/null || echo 0)
    n=$((n + 1))
    printf "%s" "$n" > {str(counter)!r}
    line=$(sed -n "${{n}}p" {str(script_file)!r})
    [ -n "$line" ] || line=$(tail -1 {str(script_file)!r})
    rc=${{line%%|*}}
    mkdir -p "$FAKE_RESULTS_DIR"
    printf '{{}}' > "$FAKE_RESULTS_DIR/P-8-2026092800000$n.json"
    printf "%s\\n" "${{line#*|}}" | tr '~' '\\n'
    exit "$rc"
    ;;
esac
exit 0
"""
    script_path = tmp_path / "fake-python"
    script_path.write_text(body, encoding="utf-8")
    script_path.chmod(0o755)
    return script_path


def _fake_crontab(tmp_path: Path) -> Path:
    """A ``crontab`` on PATH that records what it was asked to do."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    seen = tmp_path / "crontab-calls.txt"
    stub = bindir / "crontab"
    stub.write_text(
        f"""#!/bin/sh
printf '%s\\n' "$*" >> {str(seen)!r}
case "$1" in
  -l) printf '%s\\n' "5 9 * * * /x/run_p8.sh # run_p8_20261005" ;;
  -)  cat > /dev/null ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return seen


def _run_series(
    tmp_path: Path,
    *,
    script: list[str],
    policy: str | None = None,
    with_crontab: bool = False,
    **extra: str,
) -> tuple[Any, list[list[str]], Path]:
    """Drive the whole template against a fake python.

    Returns ``(result, one argv list per probe invocation, evidence dir)``.
    """
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)
    dump = tmp_path / "probe-argv.txt"
    python = _fake_python(tmp_path, script=script, dump=dump)
    evidence = tmp_path / "evidence"
    evidence.mkdir()

    import hashlib

    # AFTER _base_env, which writes a sentinel-only credential file at the
    # same path: this one has to win.
    env = _base_env(tmp_path, repo)
    env_file = tmp_path / "creds.env"
    env_file.write_text(
        "KIS_FUTURES_APP_KEY=test-key\nKIS_FUTURES_ACCOUNT_NO=1234567890\n"
        f"echo {_CREDENTIAL_SENTINEL}\n",
        encoding="utf-8",
    )
    env.update(
        {
            "P8_PYTHON": str(python),
            "P8_CREDENTIAL_FILE": str(env_file),
            "P8_EXPECT_KEY_FP": hashlib.sha256(b"test-key").hexdigest()[:12],
            "P8_EVIDENCE_DIR": str(evidence),
            "FAKE_MODULE_PATH": str(repo / "tools/broker_probes/probes_order.py"),
            "FAKE_POLICY_VERSION": policy or POLICY_VERSION,
            "FAKE_RESULTS_DIR": str(repo / "tools/broker_probes/results"),
        }
    )
    if with_crontab:
        _fake_crontab(tmp_path)
        env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
        env["P8_CRON_MARK"] = "run_p8_20261005"
    env.update(extra)

    result = subprocess.run(
        ["bash", str(repo / "tools/broker_probes/runners/run_p8.sh")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    invocations: list[list[str]] = []
    if dump.exists():
        current: list[str] = []
        for line in dump.read_text(encoding="utf-8").splitlines():
            if line == "--- end of invocation":
                invocations.append(current)
                current = []
            else:
                current.append(line)
    return result, invocations, evidence


_OK = "0|P8_STOP=none~P8_COEXISTENCE=measured"
_TRANSPORT = "0|P8_STOP=transient:transport~P8_COEXISTENCE=not_measured"
_LEDGER = "0|P8_STOP=transient:ledger_throttle~P8_COEXISTENCE=not_measured"
_REJECTED = "0|P8_STOP=rejected~P8_COEXISTENCE=not_measured"
_RATE_LIMITED = "0|P8_STOP=rate_limited~P8_COEXISTENCE=not_measured"
_UNANSWERED = "0|P8_STOP=query_unanswered~P8_COEXISTENCE=not_measured"
_ORDER_UNKNOWN = "0|P8_STOP=order_state_unknown~P8_COEXISTENCE=not_measured"


def _verdict(stdout: str) -> str:
    lines = [ln for ln in stdout.splitlines() if "VERDICT:" in ln]
    assert len(lines) == 1, stdout
    return lines[0]


def test_a_transport_stop_does_not_cancel_the_rest_of_the_series(
    tmp_path: Path,
) -> None:
    """THE regression. 2026-09-28: trial 2 died on a ConnectionError mid-poll
    and the runner wrote

        VERDICT: STOP: P-8 2/5 오류 1건(브로커 거부 포함) — 1/5 성공 후 중단

    Trials 3, 4 and 5 never ran, and ``replace_semantics.mode`` still has no
    N>=5. Nothing had been rejected.
    """
    result, invocations, evidence = _run_series(
        tmp_path, script=[_OK, _TRANSPORT, _OK, _OK, _OK]
    )

    assert len(invocations) == 5
    verdict = _verdict(result.stdout)
    assert "COMPLETE" in verdict
    assert "trials_run=5/5" in verdict
    assert "measured=4" in verdict
    assert "transport_stops=1" in verdict
    assert "broker_rejections=0" in verdict
    assert result.returncode == 0
    assert len(sorted(evidence.glob("P-8-*.json"))) == 5


def test_the_verdict_never_adds_a_transport_stop_to_a_rejection(
    tmp_path: Path,
) -> None:
    """The counts are separate fields on one line, so "오류 1건(브로커 거부
    포함)" cannot be written: there is no field that holds both."""
    result, _invocations, _evidence = _run_series(
        tmp_path, script=[_TRANSPORT, _OK, _OK, _OK, _OK]
    )

    verdict = _verdict(result.stdout)
    assert "broker_rejections=0" in verdict
    assert "transport_stops=1" in verdict
    assert "rate_limit_stops=0" in verdict
    assert "measured=4" in verdict


def test_a_ledger_throttle_stop_also_leaves_the_series_running(
    tmp_path: Path,
) -> None:
    result, invocations, _evidence = _run_series(
        tmp_path, script=[_OK, _LEDGER, _OK, _OK, _OK]
    )

    assert len(invocations) == 5
    assert "transport_stops=1" in _verdict(result.stdout)


def test_a_broker_rejection_still_stops_the_series_at_once(tmp_path: Path) -> None:
    """2026-09-11 and 2026-09-16: the account could not place the order at
    all, and every remaining trial would have been refused identically."""
    result, invocations, _evidence = _run_series(
        tmp_path, script=[_OK, _REJECTED, _OK, _OK, _OK]
    )

    assert len(invocations) == 2
    verdict = _verdict(result.stdout)
    assert "STOP: the broker REJECTED trial 2" in verdict
    assert "broker_rejections=1" in verdict
    assert "transport_stops=0" in verdict
    assert result.returncode != 0


def test_a_rate_limit_stop_still_ends_the_series(tmp_path: Path) -> None:
    """Our own call rate. "Stop, never retry" is an account-protection rule
    and this PR does not widen it."""
    result, invocations, _evidence = _run_series(
        tmp_path, script=[_OK, _RATE_LIMITED, _OK, _OK, _OK]
    )

    assert len(invocations) == 2
    assert "rate_limit_stops=1" in _verdict(result.stdout)
    assert result.returncode != 0


def test_an_order_state_unknown_stop_ends_the_series(tmp_path: Path) -> None:
    """Review F1 at the series level. A submit or amend that never answered
    may be resting under an ODNO nobody saw; the one thing this runner must
    not do is place another order on top of it. Counted in its own field — it
    is not a broker rejection and not a transport stop."""
    result, invocations, _evidence = _run_series(
        tmp_path, script=[_OK, _ORDER_UNKNOWN, _OK, _OK, _OK]
    )

    assert len(invocations) == 2
    verdict = _verdict(result.stdout)
    assert "order_state_unknown_stops=1" in verdict
    assert "broker_rejections=0" in verdict
    assert "transport_stops=0" in verdict
    assert "unaccounted_live_orders" in result.stdout
    assert result.returncode != 0


def test_a_transport_stop_is_still_the_one_that_continues(tmp_path: Path) -> None:
    """The split must not have swallowed the thing this PR is for: a POLL
    transport stop still leaves the series running, which is the 2026-09-28
    regression."""
    result, invocations, _evidence = _run_series(
        tmp_path, script=[_OK, _TRANSPORT, _OK, _OK, _OK]
    )

    assert len(invocations) == 5
    verdict = _verdict(result.stdout)
    assert "transport_stops=1" in verdict
    assert "order_state_unknown_stops=0" in verdict
    assert result.returncode == 0


@pytest.mark.parametrize("bad", ["30s", "abc", "1.2.3", "", "."])
def test_runner_refuses_an_inter_trial_gap_that_is_not_a_number(
    tmp_path: Path, bad: str
) -> None:
    """Review F7. This value reaches ``sleep``, and ``set -u`` without
    ``set -e`` means a failed sleep is a warning on stderr and then trial N+1
    fires back to back against the same account — the pacing hazard the gap
    exists for. Every other shell-consumed numeric is already validated."""
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)

    result = _run_runner(repo, tmp_path, P8_INTER_TRIAL_S=bad, P8_PYTHON="/bin/true")

    assert result.returncode != 0
    assert "P8_INTER_TRIAL_S" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


@pytest.mark.parametrize("good", ["0", "1", "1.5", "0.25"])
def test_runner_accepts_a_plain_inter_trial_gap(tmp_path: Path, good: str) -> None:
    """The guard must pass the values the README prescribes, or it is just a
    way of never running."""
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)

    result = _run_runner(repo, tmp_path, P8_INTER_TRIAL_S=good)

    # Past the numeric gate, stopped at the next one.
    assert "ABORT: required env P8_PYTHON is unset" in result.stdout
    assert "P8_INTER_TRIAL_S must be" not in result.stdout


def test_an_unanswered_poll_series_ends_the_series(tmp_path: Path) -> None:
    """A surface that answered nothing for a whole window is not one to keep
    ordering against, and it is counted in its own field — not as a broker
    rejection and not as a transport stop."""
    result, invocations, _evidence = _run_series(
        tmp_path, script=[_OK, _UNANSWERED, _OK, _OK, _OK]
    )

    assert len(invocations) == 2
    verdict = _verdict(result.stdout)
    assert "query_unanswered_stops=1" in verdict
    assert "broker_rejections=0" in verdict
    assert "transport_stops=0" in verdict
    assert result.returncode != 0


def test_transport_stops_are_budgeted_rather_than_unlimited(tmp_path: Path) -> None:
    """A link that keeps dropping is a reason to come back later. The budget
    is an env value with no default, so an operator decides it per slot."""
    result, invocations, _evidence = _run_series(
        tmp_path,
        script=[_TRANSPORT, _TRANSPORT, _TRANSPORT, _OK, _OK],
        P8_MAX_TRANSIENT_STOPS="2",
    )

    assert len(invocations) == 3
    verdict = _verdict(result.stdout)
    assert "exceeds P8_MAX_TRANSIENT_STOPS=2" in verdict
    assert "transport_stops=3" in verdict
    assert result.returncode != 0


def test_a_zero_budget_stops_on_the_first_transport_stop(tmp_path: Path) -> None:
    """The old behaviour, available deliberately rather than by accident."""
    result, invocations, _evidence = _run_series(
        tmp_path, script=[_TRANSPORT, _OK], P8_MAX_TRANSIENT_STOPS="0"
    )

    assert len(invocations) == 1
    assert "exceeds P8_MAX_TRANSIENT_STOPS=0" in _verdict(result.stdout)


def test_a_probe_that_exits_non_zero_stops_the_series(tmp_path: Path) -> None:
    """A clean token from a process that then DIED is not a clean answer: the
    probe can print its verdict and still fail writing the artifact, and an
    order may be unaccounted for. Same rule run_p_ca.sh applies to HELD=."""
    result, invocations, _evidence = _run_series(
        tmp_path, script=["5|P8_STOP=none~P8_COEXISTENCE=measured", _OK]
    )

    assert len(invocations) == 1
    verdict = _verdict(result.stdout)
    assert "exited 5" in verdict
    assert "measured=0" in verdict


def test_a_missing_verdict_line_stops_the_series(tmp_path: Path) -> None:
    """Silence is not a state. That is what a probe which crashed before its
    ``finally`` looks like from out here, and it is the shape the 09-28 runner
    had to guess at."""
    result, invocations, _evidence = _run_series(
        tmp_path, script=["0|(no anchored line at all)", _OK]
    )

    assert len(invocations) == 1
    assert "P8_STOP=<none>" in _verdict(result.stdout)


def test_a_completed_trial_that_measured_nothing_is_counted_as_neither(
    tmp_path: Path,
) -> None:
    """``none`` plus ``not_measured`` is neither a stop nor a sample. Counting
    it as a sample is how an N>=5 gate gets satisfied by four trials."""
    result, invocations, _evidence = _run_series(
        tmp_path,
        script=["0|P8_STOP=none~P8_COEXISTENCE=not_measured", _OK, _OK, _OK, _OK],
    )

    assert len(invocations) == 5
    assert "measured=4" in _verdict(result.stdout)
    assert "no sample from a trial that did not stop" in result.stdout


def test_the_series_reports_whether_n_is_met(tmp_path: Path) -> None:
    """``mode_determination`` needs N>=5 AGREEING trials, and the runner is
    the only place that knows how many this slot produced."""
    met_dir = tmp_path / "met"
    met_dir.mkdir()
    met, _i, _e = _run_series(met_dir, script=[_OK])
    assert "N>=5 is met" in met.stdout

    short_dir = tmp_path / "short"
    short_dir.mkdir()
    short, _i2, _e2 = _run_series(short_dir, script=[_OK, _TRANSPORT, _OK, _OK, _OK])
    assert "N>=5 is NOT met" in short.stdout
    assert "stays unwritten" in short.stdout


def test_the_probe_argv_carries_the_instance_values_as_single_words(
    tmp_path: Path,
) -> None:
    _result, invocations, _evidence = _run_series(
        tmp_path, script=[_OK], P8_TRIALS="1", P8_NOTE="t3 P-8 trial, re-run"
    )

    argv = invocations[0]
    assert argv[:3] == ["-m", "tools.broker_probes.run", "P-8"]
    assert argv[argv.index("--symbol") + 1] == _SYMBOL
    assert argv[argv.index("--note") + 1] == "t3 P-8 trial, re-run | trial 1/1"
    assert "--confirm" in argv
    assert argv[argv.index("--visibility-timeout-s") + 1] == "30"


def test_a_copy_that_fails_warns_instead_of_vanishing(tmp_path: Path) -> None:
    """#831 F10, in P-8's shape: a copy that silently did nothing left the
    evidence only in the gitignored results directory, with no line saying so
    — and the next trial was told this one was already secured."""
    evidence = tmp_path / "locked"
    evidence.mkdir()
    evidence.chmod(0o500)
    try:
        result, invocations, _e = _run_series(
            tmp_path,
            script=[_OK, _OK],
            P8_TRIALS="2",
            P8_EVIDENCE_DIR=str(evidence),
        )
    finally:
        evidence.chmod(0o700)

    # The series is NOT stopped by a copy failure — the measurement happened.
    assert len(invocations) == 2
    warns = [ln for ln in result.stdout.splitlines() if "could NOT copy" in ln]
    assert len(warns) == 2, result.stdout
    assert "this trial's evidence is only in" in warns[0]
    assert "COMPLETE" in _verdict(result.stdout)


def test_runner_aborts_when_the_probe_reports_a_different_policy_version(
    tmp_path: Path,
) -> None:
    """A mismatch means the runner was copied out of a different tree — the
    2026-09-30 mistake — and an older probe prints no anchored line at all."""
    result, invocations, _evidence = _run_series(
        tmp_path, script=[_OK], policy="p-8-transient-policy/0"
    )

    assert result.returncode == 4
    assert "policy version mismatch" in result.stdout
    assert POLICY_VERSION in result.stdout
    assert invocations == []
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def test_runner_accepts_the_policy_version_the_probe_reports(tmp_path: Path) -> None:
    result, invocations, _evidence = _run_series(tmp_path, script=[_OK])

    assert f"probe policy version {POLICY_VERSION} matches this runner" in result.stdout
    assert invocations


def test_the_crontab_entry_is_retired_only_after_a_trial_has_run(
    tmp_path: Path,
) -> None:
    """#825 round-3 review F1, in P-8's shape: retiring the schedule on a run
    that never started a trial silently cancels the measurement."""
    ran = tmp_path / "ran"
    ran.mkdir()
    seen = ran / "crontab-calls.txt"
    result, invocations, _evidence = _run_series(
        ran, script=[_OK], P8_TRIALS="1", with_crontab=True
    )
    assert invocations
    assert "crontab entry matching 'run_p8_20261005' removed" in result.stdout
    assert seen.exists()

    # Now an early ABORT — a key fingerprint that is not this credential
    # set's, the 2026-09-23 INVALID_CHECK_ACNO shape. The schedule must
    # survive it, so the next slot can retry.
    other = tmp_path / "second"
    other.mkdir()
    seen2 = other / "crontab-calls.txt"
    aborted, invocations2, _e2 = _run_series(
        other,
        script=[_OK],
        with_crontab=True,
        P8_EXPECT_KEY_FP="deadbeefcafe",
    )
    assert aborted.returncode != 0
    assert "app key fingerprint mismatch" in aborted.stdout
    assert invocations2 == []
    assert not seen2.exists()
