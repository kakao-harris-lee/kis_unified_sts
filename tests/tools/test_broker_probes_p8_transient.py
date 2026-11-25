"""P-8 separates a transport failure from a broker rejection."""

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

_REAL_SLEEP = time.sleep

from tests.support.probe_auth import install_stub_auth
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
_SYMBOL = "A05610"
_LAST_PRICE = "1113.60"

_CONNECTION_ABORTED = (
    "('Connection aborted.', RemoteDisconnected('Remote end closed connection "
    "without response'))"
)

_LEDGER_THROTTLE = {
    "rt_cd": "1",
    "msg_cd": "EGW00215",
    "msg1": "원장에서 허용 가능한 초당 거래건수를 초과하였습니다.",
}

_NO_QTY = "모의투자 정정/취소할 수량이 없습니다."


@pytest.fixture
def futures_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIS_FUTURES_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_FUTURES_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", _ACCOUNT)
    monkeypatch.delenv("KIS_TOKEN_CACHE_DIR", raising=False)


@pytest.fixture(autouse=True)
def no_sleeping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real seconds buy these tests nothing. Both modules' clocks, because the"""
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
        "poll_ms": 250.0,
        "gap_ms": 0.0,
        "inter_trial_s": 0.0,
        "settle_seconds": 0.0,
        "visibility_timeout_s": 300.0,
        "balance_timeout_s": 2.0,
        "late_window_s": 0.05,
        "max_pages": 10,
        "allow_fill": False,
        "cancel_unaccounted": False,
        "stock_order_type": "market",
        "pace_s": 0.0,
        "token_cache_dir": None,
        "out_dir": None,
        "note": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


class _Wire:
    """A 모의 futures broker whose open-order surface follows a script."""

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
        foreign_rows: list[dict[str, str]] | None = None,
        submit_rate_limited: bool = False,
        amend_rate_limited: bool = False,
        amend_ledger_throttled: bool = False,
        refuse_cancels: bool = False,
    ) -> None:
        self.poll_script = list(poll_script or ["new_only"])
        self.cleanup_script = list(cleanup_script or ["live"])
        self.submit_raises = submit_raises
        self.amend_raises = amend_raises
        self.submit_rejects = submit_rejects
        self.amend_rejects = amend_rejects
        self.amend_without_odno = amend_without_odno
        self.accept_before_raising = accept_before_raising
        self.delay_before = dict(delay_before or {})
        self.foreign_rows = [dict(r) for r in (foreign_rows or [])]
        self.submit_rate_limited = submit_rate_limited
        self.amend_rate_limited = amend_rate_limited
        self.amend_ledger_throttled = amend_ledger_throttled
        self.refuse_cancels = refuse_cancels
        self.calls: list[dict[str, Any]] = []
        self.inquiries: list[str] = []
        self.cleanup_phase = False
        self._numbers = itertools.count(558)
        self._original = ""
        self._new = ""
        self._live: set[str] = set()

    def _next_odno(self) -> str:
        return str(next(self._numbers)).rjust(10, "0")

    def _rows(self, odnos: list[str], *, honour_live: bool) -> list[dict[str, str]]:
        """``odnos`` rendered as open-order rows, space-padded as observed."""
        return [
            {
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
                    self._original = self._next_odno()
                    self._live.add(self._original)
                self.cleanup_phase = True
                raise self.submit_raises
            if self.submit_rate_limited:
                return 429, {}, 1.0, "Too Many Requests"
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
        if token == "sick":
            payload = {
                "rt_cd": "1",
                "msg_cd": "APBK0919",
                "msg1": "조회가 불가합니다",
            }
            return 200, payload, 1.0, str(payload)
        if token == "no_rows":
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
            rows = self._rows(sorted(self._live), honour_live=True)
            rows += [
                {
                    "odno": str(r.get("odno", "9999")).lstrip("0").rjust(10),
                    "pdno": r.get("pdno", _SYMBOL),
                    "ord_qty": r.get("ord_qty", "1"),
                    "tot_ccld_qty": "0",
                    "qty": "1",
                    **{
                        k: v
                        for k, v in r.items()
                        if k not in {"odno", "pdno", "ord_qty"}
                    },
                }
                for r in self.foreign_rows
            ]
            return 200, {"rt_cd": "0", "output1": rows}, 1.0, "{}"
        if token == "both":
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
            if self.amend_rate_limited:
                payload = {
                    "rt_cd": "1",
                    "msg_cd": "EGW00201",
                    "msg1": "초당 거래건수를 초과하였습니다.",
                }
                return 200, payload, 1.0, str(payload)
            if self.amend_ledger_throttled:
                return 500, dict(_LEDGER_THROTTLE), 1.0, str(_LEDGER_THROTTLE)
            if self.amend_rejects:
                return (
                    200,
                    {"rt_cd": "1", "msg1": "모의투자 정정주문이 불가합니다."},
                    1.0,
                    "{}",
                )
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
        self.cleanup_phase = True
        if self.refuse_cancels:
            return 200, {"rt_cd": "1", "msg1": "취소 불가"}, 1.0, "{}"
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
    install_stub_auth(monkeypatch)
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


def test_one_transport_failure_mid_poll_is_retried_and_the_trial_completes(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The 2026-09-28 trial-2 shape, with the fix: poll, drop, poll again."""
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
    """``wait()`` alone owes only the remainder of a gap the failed attempt"""
    _install(monkeypatch, _Wire(poll_script=["both", "timeout", "both", "new_only"]))

    run = probe_p8(_args(poll_ms=250.0, pace_s=0.0))

    assert run.measurements["stop_reason"] == "none"
    assert defers == [0.25]


def test_the_retry_waits_the_pacing_floor_when_it_is_wider(
    monkeypatch: pytest.MonkeyPatch, futures_env: None, defers: list[float]
) -> None:
    """The pacer will not release two calls closer than ``--pace-s``, so a"""
    _install(monkeypatch, _Wire(poll_script=["both", "timeout", "both", "new_only"]))

    run = probe_p8(_args(poll_ms=100.0, pace_s=1.1))

    assert defers == [pytest.approx(1.1)]
    assert run.measurements["poll_granularity_ms"] == pytest.approx(1100.0)


def test_a_ledger_throttle_is_transient_too(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """``EGW00215`` is the LEDGER's throttle, not ours. ``is_rate_limited``"""
    _install(monkeypatch, _Wire(poll_script=["both", "throttle", "both", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "none"
    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 1}


@pytest.mark.parametrize("token", ["timeout", "conn", "chunked"])
def test_the_transient_set_is_the_three_shapes_the_transport_can_fail_in(
    monkeypatch: pytest.MonkeyPatch, futures_env: None, token: str
) -> None:
    """A read timeout, a cut connection and a truncated body are all "no"""
    _install(monkeypatch, _Wire(poll_script=["both", token, "both", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "none"
    assert run.measurements["retries"]["transport"] == 1


def test_two_consecutive_transport_failures_stop_the_trial_as_transport(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The stop exists; what changed is that it NAMES itself."""
    _install(monkeypatch, _Wire(poll_script=["both", "conn", "conn", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "transient:transport"
    out = capsys.readouterr().out
    assert _anchored(out, _P8_STOP_PREFIX) == ["transient:transport"]
    assert _anchored(out, _P8_COEXISTENCE_PREFIX) == ["not_measured"]
    assert [r["retried"] for r in _retry_records(run, "coexistence_poll")] == [
        True,
        False,
    ]
    assert run.measurements["retries"] == {"transport": 1, "ledger_throttle": 0}


def test_a_stopped_poll_reports_no_coexistence_and_says_why(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """An unobserved interval is not a zero one."""
    _install(monkeypatch, _Wire(poll_script=["both", "conn", "conn", "new_only"]))

    run = probe_p8(_args())

    assert "coexistence_ms" not in run.measurements
    assert "mode_determination" not in run.measurements
    skipped = [s for s in run.skips if s["what"] == "measurements.coexistence_ms"]
    assert skipped and "ABORTED" in skipped[0]["reason"]
    assert "stop_reason=transient:transport" in skipped[0]["reason"]
    assert "did NOT elapse" in skipped[0]["reason"]
    assert any("NOT a broker rejection" in e for e in run.errors)
    assert any(o.get("coexistence_seen_before_stop") for o in run.observations)


def test_a_doubled_ledger_throttle_stops_the_trial_as_transient(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Same shape as the rate-limit case, and the same manufactured value."""
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
    """``P-8-20260928T000658Z`` lost ``replace_issues_new_odno`` to a failure"""
    _install(monkeypatch, _Wire(poll_script=["both", "conn", "conn", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["replace_issues_new_odno"] is True
    assert run.measurements["replace_rejected"] is False


def test_the_transport_excerpt_never_carries_the_request_query_string(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """``requests`` renders the failed URL in full and that URL carries CANO."""
    _install(monkeypatch, _Wire(poll_script=["both", "conn", "conn", "new_only"]))

    run = probe_p8(_args())

    blobs = " ".join(str(r) for r in _retry_records(run))
    assert _ACCOUNT not in blobs
    assert "CANO" not in blobs
    assert "ConnectionError" in blobs
    assert "<redacted>" in blobs


@pytest.mark.parametrize("token", ["http429", "egw00201"])
def test_a_rate_limit_still_stops_at_once_with_no_retry(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
    token: str,
) -> None:
    """Pins the rule the 2026-09-17 incident bought, byte for byte."""
    wire = _install(monkeypatch, _Wire(poll_script=["both", token, "both", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "rate_limited"
    assert _anchored(capsys.readouterr().out, _P8_STOP_PREFIX) == ["rate_limited"]
    assert _retry_records(run, "coexistence_poll") == []
    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 0}
    assert "coexistence_ms" not in run.measurements
    assert "mode_determination" not in run.measurements
    assert wire.inquiries[:2] == ["both", token]


def test_a_rate_limit_body_that_also_carries_the_ledger_code_still_stops(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Precedence, not coincidence: one answer can carry both signals, and the"""
    assert (
        common.classify_answer(429, {"msg_cd": "EGW00215"}, "Too Many Requests")
        == common.STATUS_RATE_LIMITED
    )


def test_a_lost_submit_stops_the_series_and_reports_what_it_orphaned(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A ``ReadTimeout`` on the submit says only that no ANSWER came back. The"""
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
    assert len([c for c in wire.calls if c["url"].endswith("trading/order")]) == 1
    assert [r["phase"] for r in _retry_records(run)] == ["submit"]
    assert _retry_records(run)[0]["not_retried_because"] == "single_shot_call"

    found = run.measurements["unaccounted_live_orders"]
    assert found["status"] == "FOUND_NOT_CANCELLED"
    assert found["canonical_keys"] == ["558"]
    assert any("UNACCOUNTED LIVE ORDER" in e for e in run.errors)
    assert _ACCOUNT not in " ".join(run.errors)


def test_an_unaccounted_order_is_not_cancelled_without_the_opt_in(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Review F5. The 모의 account is shared by the whole campaign, so a row"""
    wire = _install(
        monkeypatch,
        _Wire(
            submit_raises=requests.exceptions.ReadTimeout("read timeout=15.0"),
            accept_before_raising=True,
        ),
    )

    run = probe_p8(_args())

    found = run.measurements["unaccounted_live_orders"]
    assert found["status"] == "FOUND_NOT_CANCELLED"
    assert "cleanup_dispositions" not in found
    assert found["cancel_odno_would_send"] == {"558": "0000000558"}
    assert wire._live == {"0000000558"}
    assert not [c for c in wire.calls if c["body"].get("RVSE_CNCL_DVSN_CD") == "02"]


def test_the_opt_in_cancels_a_row_that_matches_this_trial(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """With ``--cancel-unaccounted`` the matching row IS cancelled, through"""
    wire = _install(
        monkeypatch,
        _Wire(
            submit_raises=requests.exceptions.ReadTimeout("read timeout=15.0"),
            accept_before_raising=True,
        ),
    )

    run = probe_p8(_args(cancel_unaccounted=True))

    found = run.measurements["unaccounted_live_orders"]
    assert found["status"] == "FOUND"
    assert list(found["cleanup_dispositions"].values()) == [_CLEANUP_CANCELLED]
    assert found["cancel_odno_sent"] == {"558": "0000000558"}
    assert wire._live == set()


@pytest.mark.parametrize(
    ("row", "why"),
    [
        ({"odno": "7001", "ord_qty": "7"}, "a different quantity"),
        ({"odno": "7002", "sll_buy_dvsn_cd": "01"}, "the opposite side"),
        ({"odno": "7003", "ord_unpr": "999.99"}, "a different price"),
    ],
)
def test_a_row_that_is_not_this_trials_order_is_never_cancelled(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    row: dict[str, str],
    why: str,
) -> None:
    """Review F5, the part no flag may override. P-5, P-11, P-EXT or an"""
    wire = _install(
        monkeypatch,
        _Wire(
            submit_raises=requests.exceptions.ReadTimeout("read timeout=15.0"),
            accept_before_raising=False,
            foreign_rows=[row],
        ),
    )

    run = probe_p8(_args(cancel_unaccounted=True))

    foreign = run.measurements["foreign_live_rows_present"]
    assert foreign["status"] == "FOREIGN_LIVE_ROWS_PRESENT"
    assert foreign["canonical_keys"] == [row["odno"]], why
    assert any("FOREIGN LIVE ROW" in e for e in run.errors)
    assert not [c for c in wire.calls if c["body"].get("RVSE_CNCL_DVSN_CD") == "02"]
    assert run.measurements["unaccounted_live_orders"]["status"] == "NONE_FOUND"


def test_the_match_records_which_criteria_it_could_actually_apply(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The order PRICE and the 매도매수구분 are not in the field set the"""
    _install(
        monkeypatch,
        _Wire(
            submit_raises=requests.exceptions.ReadTimeout("read timeout=15.0"),
            accept_before_raising=True,
        ),
    )

    run = probe_p8(_args())

    criteria = run.measurements["unaccounted_live_orders"]["match_criteria"]
    assert criteria["checked"] == ["pdno", "ord_qty"]
    assert criteria["not_carried_by_the_row"] == [
        "sll_buy_dvsn_cd",
        "ord_unpr|ord_idx",
    ]


def test_a_lost_amend_does_not_count_the_known_original_as_orphaned(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The amend consumed the original and rests under a number the probe"""
    _install(
        monkeypatch,
        _Wire(
            amend_raises=requests.exceptions.ReadTimeout("read timeout=15.0"),
            accept_before_raising=True,
        ),
    )

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "order_state_unknown"
    assert [r["phase"] for r in _retry_records(run)] == ["amend"]
    assert list(run.measurements["cleanup_dispositions"].values()) == [
        _CLEANUP_NOTHING_TO_CANCEL
    ]
    found = run.measurements["unaccounted_live_orders"]
    assert found["status"] == "FOUND_NOT_CANCELLED"
    assert found["canonical_keys"] == ["559"]


def test_a_lost_submit_that_orphaned_nothing_says_so(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    '"The walk ran and the book was clean" is what lets the operator stop'
    _install(
        monkeypatch,
        _Wire(
            submit_raises=requests.exceptions.ReadTimeout("read timeout=15.0"),
            accept_before_raising=False,
        ),
    )

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "order_state_unknown"
    assert run.measurements["unaccounted_live_orders"]["status"] == "NONE_FOUND"
    assert not any("UNACCOUNTED LIVE ORDER" in e for e in run.errors)


def test_a_book_walk_that_cannot_answer_cancels_nothing_and_says_to_look(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Fail-closed, the same polarity cleanup uses: a walk that established"""
    wire = _install(
        monkeypatch,
        _Wire(
            submit_raises=requests.exceptions.ReadTimeout("read timeout=15.0"),
            accept_before_raising=True,
            cleanup_script=["conn"],
        ),
    )

    run = probe_p8(_args(cancel_unaccounted=True))

    found = run.measurements["unaccounted_live_orders"]
    assert found["status"] == "UNDETERMINED"
    assert found["liveness_evidence"]["outcome"] == "QUERY_NOT_AN_ANSWER"
    assert any("by hand" in e for e in run.errors)
    assert wire._live != set()


def test_a_rate_limited_submit_is_not_narrated_as_a_broker_rejection(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Review F2. HTTP 429 made ``placed`` None, which read as ``rejected`` —"""
    _install(monkeypatch, _Wire(submit_rate_limited=True))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "rate_limited"
    assert _anchored(capsys.readouterr().out, _P8_STOP_PREFIX) == ["rate_limited"]
    assert any("RATE LIMITED on the submit" in e for e in run.errors)
    assert not any("submit rejected" in e for e in run.errors)
    refused = [o for o in run.observations if "order_call_refused" in o]
    assert refused and refused[0]["phase"] == "submit"


def test_a_rate_limited_amend_stops_the_series_instead_of_polling_on(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The worse half of F2: on the amend a rate limit was INVISIBLE —"""
    wire = _install(monkeypatch, _Wire(amend_rate_limited=True))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "rate_limited"
    assert _anchored(capsys.readouterr().out, _P8_STOP_PREFIX) == ["rate_limited"]
    assert any("RATE LIMITED on the amend" in e for e in run.errors)
    assert "coexistence_polls_used" not in run.measurements
    assert wire._live == set()


def test_a_ledger_throttled_amend_walks_the_book_before_stopping(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """``EGW00215`` is an answer, so strictly the amend was not accepted — but"""
    _install(monkeypatch, _Wire(amend_ledger_throttled=True))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "order_state_unknown"
    assert "unaccounted_live_orders" in run.measurements
    assert any("LEDGER THROTTLE on the amend" in e for e in run.errors)


def test_a_cleanup_error_stops_the_trial_counting_toward_n5(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Review F1. The poll loop ends with a sample, then ``_cleanup`` in the"""
    _install(
        monkeypatch,
        _Wire(
            poll_script=["both", "new_only"],
            cleanup_script=["conn"],
            refuse_cancels=True,
        ),
    )

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "none"
    assert "coexistence_ms" in run.measurements
    assert run.errors
    assert run.to_dict()["provenance_class"] == "NOT_MEASURED"
    assert _anchored(capsys.readouterr().out, _P8_COEXISTENCE_PREFIX) == [
        "not_measured"
    ]


def test_the_quote_phase_still_continues_because_nothing_is_resting(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The split F1 draws is "is an order's state unknown", not "is it a"""
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
    """Three phases, three reasons, no shared sentence that is false for one"""
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
    """The other half of the manufactured-value defect, and the half"""
    _install(
        monkeypatch,
        _Wire(poll_script=["both", "no_rows", "both", "new_only"]),
    )

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "none"
    assert run.measurements["coexistence_polls_not_answered"] == 1
    assert run.measurements["coexistence_polls_answered"] == 3
    assert run.measurements["coexistence_ms"] > 0.0
    recorded = [o for o in run.observations if "coexistence_poll_not_answered" in o]
    assert len(recorded) == 1
    assert recorded[0]["coexistence_poll_not_answered"]["msg_cd"] == "KIOK0560"


def test_a_poll_series_that_only_gets_sick_answers_stops_the_series(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Nothing came back ``rt_cd=0`` for the whole window, and not because the"""
    _install(monkeypatch, _Wire(poll_script=["sick"]))

    run = probe_p8(_args(visibility_timeout_s=0.3))

    assert run.measurements["stop_reason"] == "query_unanswered"
    assert "coexistence_ms" not in run.measurements
    assert "mode_determination" not in run.measurements
    assert run.measurements["coexistence_polls_answered"] == 0
    polls = run.measurements["coexistence_polls_not_answered"]
    assert polls > 0
    assert run.measurements["coexistence_not_answered_codes"] == {"APBK0919": polls}
    out = capsys.readouterr().out
    assert _anchored(out, _P8_STOP_PREFIX) == ["query_unanswered"]
    skipped = [s for s in run.skips if s["what"] == "measurements.coexistence_ms"]
    assert skipped and "DID elapse" in skipped[0]["reason"]
    assert "did NOT elapse" not in skipped[0]["reason"]
    assert not any("The stop is our own call rate" in e for e in run.errors)
    assert any("answered rt_cd!=0 to every poll" in e for e in run.errors)


def test_an_empty_book_for_the_whole_window_does_not_stop_the_series(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Review F4. This broker answers an EMPTY RESULT SET with a rejection"""
    _install(monkeypatch, _Wire(poll_script=["no_rows"]))

    run = probe_p8(_args(visibility_timeout_s=0.1))

    assert run.measurements["stop_reason"] == "none"
    assert "coexistence_ms" not in run.measurements
    assert _anchored(capsys.readouterr().out, _P8_COEXISTENCE_PREFIX) == [
        "not_measured"
    ]
    assert run.measurements["coexistence_not_answered_codes"]


def test_one_sick_answer_among_empty_ones_still_stops(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The quieter treatment is for a window that was ONLY the empty-set"""
    _install(monkeypatch, _Wire(poll_script=["no_rows", "sick"]))

    run = probe_p8(_args(visibility_timeout_s=0.3))

    assert run.measurements["stop_reason"] == "query_unanswered"
    assert set(run.measurements["coexistence_not_answered_codes"]) == {
        "KIOK0560",
        "APBK0919",
    }


def test_the_unanswered_evidence_is_bounded_by_distinct_codes_not_by_polls(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """With ``--pace-s 0`` this loop runs tens of thousands of times a second"""
    _install(monkeypatch, _Wire(poll_script=["sick"]))

    run = probe_p8(_args(visibility_timeout_s=0.3))

    recorded = [o for o in run.observations if "coexistence_poll_not_answered" in o]
    assert len(recorded) == 1
    polls = run.measurements["coexistence_polls_not_answered"]
    assert polls > 100, polls
    assert run.measurements["coexistence_not_answered_codes"]["APBK0919"] == polls


def test_a_stop_narration_exists_for_every_stop_the_poll_can_report() -> None:
    """A lookup with a missing key is a KeyError inside the ``finally``'s"""
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
    """Nothing is resting yet, so this is a different fact from a failed"""
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
    assert [c for c in wire.calls if c["url"].endswith("trading/order")] == []
    assert "cleanup_dispositions" not in run.measurements
    errors = " ".join(run.errors)
    assert "price lookup" in errors
    assert "duplicate-order hazard" not in errors


def test_a_rejected_submit_is_still_a_rejection(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The one stop the "재시도 금지" rule was written for: 2026-09-11 and"""
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
    """The runner always passes ``--confirm``; a ``dry_run`` token reaching it"""
    _install(monkeypatch, _Wire())

    probe_p8(_args(confirm=False))

    assert _anchored(capsys.readouterr().out, _P8_STOP_PREFIX) == ["dry_run"]


def test_cleanup_still_runs_and_is_still_recorded_after_a_transport_stop(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The ``finally`` is the reason the 09-28 trial left no order on the book"""
    _install(monkeypatch, _Wire(poll_script=["both", "conn", "conn", "new_only"]))

    run = probe_p8(_args())

    dispositions = list(run.measurements["cleanup_dispositions"].values())
    assert dispositions == [_CLEANUP_NOTHING_TO_CANCEL, _CLEANUP_CANCELLED]
    assert "cleanup_liveness_note" in run.measurements
    assert "amend_consumption_note" in run.measurements


def test_cleanup_still_runs_after_a_transport_failure_on_the_amend(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The submit succeeded, so an order IS resting; the amend never answered."""
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
    """A walk that cannot answer counts the order as LIVE and raises an error"""
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
    """Fail-closed in the other direction: not knowing is not "not live", and"""
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


def test_a_window_that_never_opened_measures_nothing(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Review F2: zero polls is zero observations, whatever the stop says."""
    _install(monkeypatch, _Wire(poll_script=["conn", "both", "new_only"]))

    run = probe_p8(_args(visibility_timeout_s=0.0))

    assert _retry_records(run, "coexistence_poll") == []
    assert run.measurements["retries"] == {"transport": 0, "ledger_throttle": 0}
    assert run.measurements["stop_reason"] == "none"
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
    """Review F3: no replace happened, so there is no interval."""
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
    """``rt_cd=0`` with no ``output.ODNO``: the second leg the measurement"""
    _install(monkeypatch, _Wire(amend_without_odno=True))

    run = probe_p8(_args(visibility_timeout_s=0.1))

    assert run.measurements["replace_rejected"] is False
    assert run.measurements["replace_issues_new_odno"] is False
    assert "coexistence_ms" not in run.measurements
    skipped = [s for s in run.skips if s["what"] == "measurements.coexistence_ms"]
    assert skipped and "no new ODNO was issued" in skipped[0]["reason"]


def test_a_lone_transient_after_the_deadline_is_the_natural_end(
    monkeypatch: pytest.MonkeyPatch,
    futures_env: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Review F3. Window 0.05 s, poll 1 answers with both legs live, poll 2"""
    _install(
        monkeypatch,
        _Wire(poll_script=["both", "conn", "new_only"], delay_before={2: 0.12}),
    )

    run = probe_p8(_args(visibility_timeout_s=0.05, poll_ms=1.0))

    assert run.measurements["stop_reason"] == "none"
    assert run.measurements["coexistence_ms"] > 0.0
    assert "mode_determination" in run.measurements
    assert _anchored(capsys.readouterr().out, _P8_COEXISTENCE_PREFIX) == ["measured"]
    records = _retry_records(run, "coexistence_poll")
    assert [r["retried"] for r in records] == [False]
    assert records[0]["not_retried_because"] == "window_already_closed"
    assert [s for s in run.skips if s["what"] == "measurements.coexistence_ms"] == []


def test_a_second_consecutive_transient_names_that_reason_instead(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The other refusal. Both used to carry only ``retried: false``, and a"""
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
    """Review F5: the narration told the reader to see ``retry_evidence``,"""
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
    """Same regression on the other surface: an HTTP-200 ``EGW00201`` body"""
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
    """Review F6: ``str(x or "")`` turns the JSON NUMBER ``0`` into ``""``,"""
    _install(monkeypatch, _Wire(poll_script=["both", "rt_cd_zero", "new_only"]))

    run = probe_p8(_args())

    assert run.measurements["stop_reason"] == "none"
    assert run.measurements["coexistence_polls_not_answered"] == 0
    assert run.measurements["coexistence_polls_answered"] >= 2
    assert "coexistence_ms" in run.measurements


_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNERS_DIR = _REPO_ROOT / "tools" / "broker_probes" / "runners"
_RUNNER = _RUNNERS_DIR / "run_p8.sh"
_RUNNER_COMMON = _RUNNERS_DIR / "_common.sh"

_CREDENTIAL_SENTINEL = "CREDENTIAL_FILE_WAS_SOURCED"


def test_runner_template_is_tracked_and_executable() -> None:
    """The 2026-09-28 runner was neither, and it is gone: the only record of"""
    assert _RUNNER.is_file(), _RUNNER
    assert os.access(_RUNNER, os.X_OK), f"{_RUNNER} is not executable"


def test_runner_template_parses() -> None:
    result = subprocess.run(
        ["bash", "-n", str(_RUNNER)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_runner_template_passes_shellcheck() -> None:
    """On CI a missing shellcheck is a FAILURE, not a skip — and each file is"""
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
    """Every ``P8_*`` instance value is read WITHOUT a ``:-`` default. A"""
    text = _RUNNER.read_text(encoding="utf-8")
    pairs = set(re.findall(r"\$\{(P8_[A-Z_]+):-([^}]*)\}", text))
    assert {name for name, default in pairs if default not in ("", "0")} == set(), pairs
    assert {name for name, _default in pairs} <= {
        "P8_ALLOW_SHARED_CHECKOUT",
        "P8_CANCEL_UNACCOUNTED",
        "P8_CRON_MARK",
        "P8_LOG",
    }, pairs


def test_runner_template_never_removes_itself() -> None:
    """The 2026-09-30 P-CA runner self-deleted after its first run, so attempts"""
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


def test_every_token_the_runner_branches_on_is_in_the_readme() -> None:
    """Review F7. The README is the documented recipe, and a token an"""
    runner = _RUNNER.read_text(encoding="utf-8")
    readme = (_RUNNERS_DIR / "README.md").read_text(encoding="utf-8")
    arms = set(re.findall(r"^  ([a-z_]+(?::\*)?)\)$", runner, re.M))
    assert "none" in arms and len(arms) >= 5, arms

    fence = re.search(r"P8_STOP=<(.+?)>", readme, re.S)
    assert fence, "the README no longer states the P8_STOP contract"
    documented = {t.strip() for t in fence.group(1).replace("\n", " ").split("|")}

    for arm in arms:
        if arm.endswith(":*"):
            prefix = arm.removesuffix("*")
            assert any(d.startswith(prefix) for d in documented), (arm, documented)
            continue
        assert arm in documented, (arm, documented)
        if arm != "none":
            assert f"`{arm}`" in readme, f"{arm} is handled but has no table row"


def test_the_liveness_walk_hands_back_rows_not_just_numbers() -> None:
    """Review F8. ``_cancel_one`` annotated this ``set[str] | None`` after it"""
    import inspect

    sig = inspect.signature(probes_order._live_odno_keys)
    assert "dict[str, dict[str, Any]] | None" in str(sig.return_annotation)
    cancel_src = inspect.getsource(probes_order._cancel_one)
    assert "live_keys: dict[str, dict[str, Any]] | None" in cancel_src


def test_the_runner_reads_the_prefixes_the_probe_prints() -> None:
    """The contract is two anchored lines. If the probe renames one, this"""
    text = _RUNNER.read_text(encoding="utf-8")
    assert f"s/^{_P8_STOP_PREFIX}//p" in text
    assert f"s/^{_P8_COEXISTENCE_PREFIX}//p" in text


def _runner_repo(tmp_path: Path, *, detached: bool, dirty: bool) -> Path:
    """A throwaway git checkout holding a copy of the template, so the guards"""
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
    """#793: a shared checkout lets a parallel lane move the branch under a"""
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
    """The guards must PASS on the shape the README prescribes, or they are"""
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
    """``[ "$trial" -le "$P8_TRIALS" ]`` on a non-number is a shell diagnostic"""
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)

    result = _run_runner(repo, tmp_path, P8_TRIALS=bad, P8_PYTHON="/bin/true")

    assert result.returncode != 0
    assert "P8_TRIALS" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


def _fake_python(tmp_path: Path, *, script: list[str], dump: Path) -> Path:
    """A stand-in interpreter answering the three calls the runner makes."""
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
    """Drive the whole template against a fake python."""
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)
    dump = tmp_path / "probe-argv.txt"
    python = _fake_python(tmp_path, script=script, dump=dump)
    evidence = tmp_path / "evidence"
    evidence.mkdir()

    import hashlib

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
    """THE regression. 2026-09-28: trial 2 died on a ConnectionError mid-poll"""
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
    """The counts are separate fields on one line, so "오류 1건(브로커 거부"""
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
    """2026-09-11 and 2026-09-16: the account could not place the order at"""
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
    """Our own call rate. "Stop, never retry" is an account-protection rule"""
    result, invocations, _evidence = _run_series(
        tmp_path, script=[_OK, _RATE_LIMITED, _OK, _OK, _OK]
    )

    assert len(invocations) == 2
    assert "rate_limit_stops=1" in _verdict(result.stdout)
    assert result.returncode != 0


def test_the_cancel_opt_in_reaches_the_probe_only_when_asked(
    tmp_path: Path,
) -> None:
    """Review F5. The flag authorises cancelling a live row the probe never"""
    off = tmp_path / "off"
    off.mkdir()
    _result, invocations, _e = _run_series(off, script=[_OK], P8_TRIALS="1")
    assert "--cancel-unaccounted" not in invocations[0]

    on = tmp_path / "on"
    on.mkdir()
    _result2, invocations2, _e2 = _run_series(
        on, script=[_OK], P8_TRIALS="1", P8_CANCEL_UNACCOUNTED="1"
    )
    assert "--cancel-unaccounted" in invocations2[0]


def test_an_order_state_unknown_stop_ends_the_series(tmp_path: Path) -> None:
    """Review F1 at the series level. A submit or amend that never answered"""
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
    """The split must not have swallowed the thing this PR is for: a POLL"""
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
    """Review F7. This value reaches ``sleep``, and ``set -u`` without"""
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)

    result = _run_runner(repo, tmp_path, P8_INTER_TRIAL_S=bad, P8_PYTHON="/bin/true")

    assert result.returncode != 0
    assert "P8_INTER_TRIAL_S" in result.stdout
    assert _CREDENTIAL_SENTINEL not in result.stdout + result.stderr


@pytest.mark.parametrize("good", ["0", "1", "1.5", "0.25"])
def test_runner_accepts_a_plain_inter_trial_gap(tmp_path: Path, good: str) -> None:
    """The guard must pass the values the README prescribes, or it is just a"""
    repo = _runner_repo(tmp_path, detached=True, dirty=False)
    _publish_origin_main(repo)

    result = _run_runner(repo, tmp_path, P8_INTER_TRIAL_S=good)

    assert "ABORT: required env P8_PYTHON is unset" in result.stdout
    assert "P8_INTER_TRIAL_S must be" not in result.stdout


def test_an_unanswered_poll_series_ends_the_series(tmp_path: Path) -> None:
    """A surface that answered nothing for a whole window is not one to keep"""
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
    """A link that keeps dropping is a reason to come back later. The budget"""
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
    """A clean token from a process that then DIED is not a clean answer: the"""
    result, invocations, _evidence = _run_series(
        tmp_path, script=["5|P8_STOP=none~P8_COEXISTENCE=measured", _OK]
    )

    assert len(invocations) == 1
    verdict = _verdict(result.stdout)
    assert "exited 5" in verdict
    assert "measured=0" in verdict


def test_a_missing_verdict_line_stops_the_series(tmp_path: Path) -> None:
    """Silence is not a state. That is what a probe which crashed before its"""
    result, invocations, _evidence = _run_series(
        tmp_path, script=["0|(no anchored line at all)", _OK]
    )

    assert len(invocations) == 1
    assert "P8_STOP=<none>" in _verdict(result.stdout)


def test_a_completed_trial_that_measured_nothing_is_counted_as_neither(
    tmp_path: Path,
) -> None:
    """``none`` plus ``not_measured`` is neither a stop nor a sample. Counting"""
    result, invocations, _evidence = _run_series(
        tmp_path,
        script=["0|P8_STOP=none~P8_COEXISTENCE=not_measured", _OK, _OK, _OK, _OK],
    )

    assert len(invocations) == 5
    assert "measured=4" in _verdict(result.stdout)
    assert "no sample from a trial that did not stop" in result.stdout


def test_the_series_reports_whether_n_is_met(tmp_path: Path) -> None:
    """``mode_determination`` needs N>=5 AGREEING trials, and the runner is"""
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
    """#831 F10, in P-8's shape: a copy that silently did nothing left the"""
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

    assert len(invocations) == 2
    warns = [ln for ln in result.stdout.splitlines() if "could NOT copy" in ln]
    assert len(warns) == 2, result.stdout
    assert "this trial's evidence is only in" in warns[0]
    assert "COMPLETE" in _verdict(result.stdout)


def test_runner_aborts_when_the_probe_reports_a_different_policy_version(
    tmp_path: Path,
) -> None:
    """A mismatch means the runner was copied out of a different tree — the"""
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
    """#825 round-3 review F1, in P-8's shape: retiring the schedule on a run"""
    ran = tmp_path / "ran"
    ran.mkdir()
    seen = ran / "crontab-calls.txt"
    result, invocations, _evidence = _run_series(
        ran, script=[_OK], P8_TRIALS="1", with_crontab=True
    )
    assert invocations
    assert "crontab entry matching 'run_p8_20261005' removed" in result.stdout
    assert seen.exists()

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
