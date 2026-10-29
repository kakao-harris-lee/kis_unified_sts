"""Unit tests for P-SC — the stock MOCK cancel-shape probe (#948 step 1).

No test here opens a socket: ``probes_order.http_json`` is replaced by
:class:`_Broker`, a small stateful fake of the four KIS surfaces the probe
touches (quote, order-cash, order-rvsecncl, inquire-daily-ccld,
inquire-balance). ``shared.kis.auth.KISAuthManager`` is stubbed out.

What is pinned here, one group per way the probe could do harm or lie:

1. **The cancel wire form.** ``VTTC0013U`` is a mock TR, and every ``[필수]``
   field the official wrapper refuses as empty is present. An empty 원주문번호
   or 거래소코드 and a zero quantity are refused locally rather than sent — the
   wrapper's own ``ValueError`` would come back as an opaque broker rejection.
2. **REAL refusal.** The host and TR seals make a REAL *endpoint* unreachable;
   they say nothing about the CREDENTIAL. The paper stack really does export
   ``KIS_STOCK_MARKET=real``, so sourcing the wrong ``.env`` is the live
   mistake, and it has to be refused before the first socket.
3. **Session and trading-day refusal.** Outside the window, and on a day the
   tenant calendar declares closed, nothing is sent.
4. **Flat start.** Not just "the account looks empty" but "the surfaces
   PROVED it": a capped balance walk, a refusal, a throttle and a full page are
   each refusals, because a read that did not answer is not a flat account.
5. **Cleanup on the failure path.** A trial that raises still leaves the
   account flat, and the cleanup records its own outcome.
6. **The five-value verdict.** ``NEITHER_OBSERVED`` (the surface answered and
   showed neither) and ``UNDETERMINED`` (it did not answer) are different
   values. Collapsing them is how #948 step 2 would go fail-open.
7. **The order-call budget**, which is the only limit that bounds how MANY
   orders a loop may send.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.broker_probes import probes_order, probes_stock_cancel
from tools.broker_probes.common import (
    MOCK_HOST,
    ProbeCredentials,
    ProbeError,
    ProbeRun,
    SafetyViolation,
    assert_mock_trading_tr,
)
from tools.broker_probes.probes_order import (
    _STOCK_CANCEL_TR_MOCK,
    build_stock_cancel_body,
    odno_key,
)
from tools.broker_probes.probes_stock_cancel import (
    _CLEAN_FLAT,
    _CLEAN_STILL_LIVE,
    _PARTIAL_FILLED_FULLY,
    _READ_OK,
    _READ_TRANSIENT,
    _READ_TRUNCATED,
    _SHAPE_BOTH,
    _SHAPE_NONE,
    _SHAPE_ORIGINAL_FLAGGED,
    _SHAPE_SEPARATE_ROW,
    _SHAPE_UNDETERMINED,
    _STOP_NONE,
    OrderBudget,
    assert_mock_only_env,
    assert_session_window,
    classify_cancel_shape,
    classify_late_fill,
    load_config,
    probe_psc,
)

_ACCOUNT = "1234567890"
_SYMBOL = "005930"
_LAST_PRICE = "70200"
_ASPR_UNIT = "100"
_ORG_NO = "06010"

#: A KST instant inside the configured window on a KRX trading day.
#: 2026-11-02 is a Monday and is not in the tenant calendar's holiday list —
#: the day the 11-02 run is scheduled for.
_IN_WINDOW = datetime(2026, 11, 2, 10, 30, tzinfo=probes_stock_cancel.KST)


# ---------------------------------------------------------------------------
# the fake broker
# ---------------------------------------------------------------------------


class _Broker:
    """A stateful fake of the five surfaces P-SC touches.

    ``cancel_shape`` is the thing under measurement, so it is a knob: the probe
    must report what the surface showed, and each of the four shapes has to
    come out as its own verdict rather than as a default.
    """

    def __init__(
        self,
        *,
        cancel_shape: str = "separate_row",
        fills: bool = False,
        partial_fill: int | None = None,
        late_fill: bool = False,
        aspr_unit: str | None = _ASPR_UNIT,
        holding: int = 0,
        balance_pages: int = 1,
        ccld_page_rows: int | None = None,
        balance_rt_cd: str = "0",
        balance_http: int = 200,
    ) -> None:
        self.cancel_shape = cancel_shape
        self.fills = fills
        self.partial_fill = partial_fill
        self.late_fill = late_fill
        self.aspr_unit = aspr_unit
        self.holding = holding
        self.balance_pages = balance_pages
        self.ccld_page_rows = ccld_page_rows
        self.balance_rt_cd = balance_rt_cd
        self.balance_http = balance_http
        self.rows: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []
        self._next_odno = 8686

    # -- helpers --------------------------------------------------------
    def _odno(self) -> str:
        self._next_odno += 1
        return f"{self._next_odno:010d}"

    def _row(self, *, odno: str, qty: int, filled: int, price: str, side: str) -> dict:
        return {
            "ord_dt": "20261102",
            "odno": odno,
            # Space-padded zero is the measured wire form for an order that is
            # not an amend/cancel: P-NMPR-20260731T015139Z, profile
            # orgn_odno_wire_form.observed == "'         0'".
            "orgn_odno": "         0",
            "ord_dvsn_name": "지정가",
            "sll_buy_dvsn_cd": "02" if side == "BUY" else "01",
            "pdno": _SYMBOL,
            "prdt_name": "삼성전자",
            "ord_qty": str(qty),
            "ord_unpr": price,
            "ord_tmd": "103000",
            "tot_ccld_qty": str(filled),
            "tot_ccld_amt": str(filled * int(price or 0)),
            "avg_prvs": price,
            "rmn_qty": str(qty - filled),
            "cncl_yn": "N",
            "rjct_qty": "0",
        }

    def _find(self, odno: str) -> dict[str, Any] | None:
        for row in self.rows:
            if odno_key(row["odno"]) == odno_key(odno):
                return row
        return None

    # -- the surfaces ---------------------------------------------------
    def _quote(self) -> dict[str, Any]:
        out: dict[str, Any] = {"stck_prpr": _LAST_PRICE}
        if self.aspr_unit is not None:
            out["aspr_unit"] = self.aspr_unit
        return {"rt_cd": "0", "output": out}

    def _submit(self, body: dict[str, Any], tr_id: str) -> dict[str, Any]:
        qty = int(body["ORD_QTY"])
        side = "BUY" if tr_id.endswith("0802U") else "SELL"
        price = body["ORD_UNPR"]
        if side == "SELL":
            # The flatten is a 시장가 sell and fills fully — the behaviour P-11
            # measured for a 모의 market order.
            self.holding = max(0, self.holding - qty)
            filled = qty
        elif self.partial_fill is not None:
            filled = min(self.partial_fill, qty)
            self.holding += filled
        elif self.fills:
            filled = qty
            self.holding += filled
        else:
            filled = 0
        odno = self._odno()
        self.rows.append(
            self._row(odno=odno, qty=qty, filled=filled, price=price, side=side)
        )
        return {
            "rt_cd": "0",
            "msg_cd": "APBK0013",
            "msg1": "주문 전송 완료 되었습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": _ORG_NO,
                "ODNO": odno,
                "ORD_TMD": "103000",
            },
        }

    def _cancel(self, body: dict[str, Any]) -> dict[str, Any]:
        original = self._find(body["ORGN_ODNO"])
        if original is None:
            return {
                "rt_cd": "1",
                "msg_cd": "APBK0918",
                "msg1": "원주문을 찾을 수 없습니다",
            }
        # Read before either branch zeroes it: the cancelled quantity is what a
        # derived row would carry as its 주문수량.
        cancelled_qty = int(original["rmn_qty"] or 0) or int(original["ord_qty"])
        if self.cancel_shape in ("flag", "both"):
            original["cncl_yn"] = "Y"
            original["rmn_qty"] = "0"
        if self.cancel_shape in ("separate_row", "both"):
            original["rmn_qty"] = "0"
            derived = self._row(
                odno=self._odno(), qty=cancelled_qty, filled=0, price="0", side="BUY"
            )
            # Nothing is working on a cancel row, so 잔여수량 is 0 — otherwise
            # the row would read as live and the cleanup would chase it. Which
            # shape the broker really uses is what this probe measures; this is
            # the plausible one, and the `none` arm covers the other extreme.
            derived["rmn_qty"] = "0"
            derived["ord_dvsn_name"] = "취소"
            # The field the broker profile says is UNVERIFIED on a row a cancel
            # produced. Zero-padded here while the original order's own
            # `orgn_odno` is space-padded: the probe must canonicalise both.
            derived["orgn_odno"] = original["odno"]
            self.rows.append(derived)
        if self.cancel_shape == "none":
            # Accepted, and nothing on the surface changed. The pathological
            # case the five-value verdict exists for.
            pass
        if self.late_fill:
            original["tot_ccld_qty"] = str(int(original["tot_ccld_qty"]) + 1)
        return {
            "rt_cd": "0",
            "msg_cd": "APBK0013",
            "msg1": "주문 전송 완료 되었습니다.",
            "output": {
                "KRX_FWDG_ORD_ORGNO": _ORG_NO,
                "ODNO": self._odno(),
                "ORD_TMD": "103001",
            },
        }

    def _ccld(self, params: dict[str, Any]) -> dict[str, Any]:
        newest_first = list(reversed(self.rows))
        if self.ccld_page_rows is None:
            return {"rt_cd": "0", "msg1": "정상처리", "output1": newest_first}
        start = int(params.get("CTX_AREA_NK100") or 0)
        page = newest_first[start : start + self.ccld_page_rows]
        nxt = start + self.ccld_page_rows
        more = nxt < len(newest_first)
        return {
            "rt_cd": "0",
            "msg1": "정상처리",
            "output1": page,
            "ctx_area_fk100": str(nxt) if more else "",
            "ctx_area_nk100": str(nxt) if more else "",
        }

    def _balance(self, params: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if self.balance_rt_cd != "0" or self.balance_http != 200:
            return self.balance_http, {
                "rt_cd": self.balance_rt_cd,
                "msg_cd": "APBK0919",
                "msg1": "조회가 되지 않았습니다",
            }
        page = int(params.get("CTX_AREA_NK100") or 0)
        last_page = page >= self.balance_pages - 1
        rows = (
            [{"pdno": _SYMBOL, "hldg_qty": str(self.holding)}]
            if last_page and self.holding >= 0
            else [{"pdno": "000660", "hldg_qty": "3"}]
        )
        if not last_page:
            # Never the end of the set, so a cap test can exhaust the walk.
            return 200, {
                "rt_cd": "0",
                "output1": rows,
                "ctx_area_fk100": str(page + 1),
                "ctx_area_nk100": str(page + 1),
            }
        return 200, {
            "rt_cd": "0",
            "output1": rows,
            "output2": [{"dnca_tot_amt": "1000"}],
        }

    # -- the transport --------------------------------------------------
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
        self.calls.append(
            {
                "method": method,
                "url": url,
                "tr_id": headers.get("tr_id", ""),
                "params": dict(params or {}),
                "body": dict(json_body or {}),
            }
        )
        if "quotations/inquire-price" in url:
            payload: dict[str, Any] = self._quote()
        elif "trading/order-rvsecncl" in url:
            payload = self._cancel(json_body or {})
        elif "trading/order-cash" in url:
            payload = self._submit(json_body or {}, headers.get("tr_id", ""))
        elif "trading/inquire-daily-ccld" in url:
            payload = self._ccld(params or {})
        elif "trading/inquire-balance" in url:
            status, payload = self._balance(params or {})
            return status, payload, 1.0, "{}"
        else:  # pragma: no cover - an unexpected path is a test bug
            raise AssertionError(f"unexpected probe URL: {url}")
        return 200, payload, 1.0, "{}"

    # -- assertions helpers ---------------------------------------------
    def order_posts(self) -> list[dict[str, Any]]:
        return [c for c in self.calls if "trading/order-cash" in c["url"]]

    def cancel_posts(self) -> list[dict[str, Any]]:
        return [c for c in self.calls if "trading/order-rvsecncl" in c["url"]]


class _StubAuth:
    def get_auth_headers(self) -> dict[str, str]:
        return {"authorization": "Bearer stub"}


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exactly the env vars the stock credential path reads, all mock."""
    monkeypatch.setenv("KIS_STOCK_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_STOCK_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_STOCK_ACCOUNT_NO", _ACCOUNT)
    monkeypatch.setenv("KIS_STOCK_MARKET", "mock")
    monkeypatch.delenv("KIS_FUTURES_MARKET", raising=False)
    monkeypatch.delenv("KIS_REAL_TRADING", raising=False)
    monkeypatch.delenv("KIS_TOKEN_CACHE_DIR", raising=False)


def _config_file(tmp_path: Path, **overrides: Any) -> Path:
    """A P-SC config with the clocks wound down, written to ``tmp_path``.

    The windows are tiny so a whole run costs milliseconds; no assertion here
    is on an elapsed duration. Everything else matches the shipped file, so a
    key renamed there fails these tests rather than passing vacuously.
    """
    data: dict[str, Any] = {
        "schema_version": 1,
        "session": {
            "calendar_path": "config/tos_runtime/paper/calendar.yaml",
            "covered_years": [2026],
            "window": {"start": "09:00", "end": "15:20"},
        },
        "limits": {
            "pace_s": 0.001,
            "pace_s_floor": 0.001,
            "max_order_calls": 10,
            "max_quantity": 2,
            "cleanup": {"cancel_attempts": 2, "retry_s": 0.001},
        },
        "observation": {"cancel_window_s": 0.01, "poll_interval_s": 0.005},
        "flat_check": {"balance_max_pages": 5, "ccld_page_row_cap": 15},
        "trials": {
            "a": {"quantity": 1, "price_offset_pct": 25.0},
            "b": {"enabled": True, "quantity": 2, "price_offset_pct": 5.0},
        },
    }
    for dotted, value in overrides.items():
        node: Any = data
        parts = dotted.split(".")
        for part in parts[:-1]:
            node = node[part]
        if value is _DELETE:
            del node[parts[-1]]
        else:
            node[parts[-1]] = value
    path = tmp_path / "p-sc.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


class _Delete:
    """Sentinel: remove this key from the generated config."""


_DELETE = _Delete()


def _args(config: Path, tmp_path: Path, **overrides: Any) -> argparse.Namespace:
    base: dict[str, Any] = {
        "probe_id": "P-SC",
        "symbol": _SYMBOL,
        "asset": "stock",
        "confirm": True,
        "quantity": 1,
        "price_offset_pct": 10.0,
        "samples": 1,
        "margin_pct": 50.0,
        "token_cache_dir": str(tmp_path / "tc"),
        "out_dir": str(tmp_path / "out"),
        "note": "test",
        "config": str(config),
        "trial": "both",
    }
    base.update(overrides)
    return argparse.Namespace(**base)


@pytest.fixture
def install(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Install a broker as the transport and freeze the clock inside the window."""

    def _install(broker: _Broker, *, now: datetime = _IN_WINDOW) -> _Broker:
        monkeypatch.setattr(probes_order, "http_json", broker)
        monkeypatch.setattr(
            "shared.kis.auth.KISAuthManager", lambda *a, **k: _StubAuth(), raising=True
        )
        monkeypatch.setattr(probes_stock_cancel, "_now", lambda: now)
        monkeypatch.setattr(time, "sleep", lambda _s: None)
        return broker

    return _install


# ---------------------------------------------------------------------------
# 1. the cancel wire form
# ---------------------------------------------------------------------------


def test_the_cancel_tr_is_a_mock_tr() -> None:
    """``VTTC0013U`` — 모의. The 실전 twin would be refused by the seal."""
    assert _STOCK_CANCEL_TR_MOCK == "VTTC0013U"
    assert_mock_trading_tr(_STOCK_CANCEL_TR_MOCK)  # must not raise
    with pytest.raises(SafetyViolation):
        assert_mock_trading_tr("TTTC0013U")


def test_cancel_body_carries_every_required_field_verbatim() -> None:
    """Source: ``examples_llm/domestic_stock/order_rvsecncl`` ``[v1_국내주식-003]``.

    The identifiers go back on the wire EXACTLY as the accept response gave
    them — zero padding included. Canonicalising before sending is a different
    operation from canonicalising for a comparison.
    """
    body = build_stock_cancel_body(
        "12345678",
        "90",
        orgn_odno="0000008687",
        krx_fwdg_ord_orgno=_ORG_NO,
        remaining_qty=1,
    )
    assert body == {
        "CANO": "12345678",
        "ACNT_PRDT_CD": "90",
        "KRX_FWDG_ORD_ORGNO": _ORG_NO,
        "ORGN_ODNO": "0000008687",
        "ORD_DVSN": "00",
        "RVSE_CNCL_DVSN_CD": "02",
        "ORD_QTY": "1",
        "ORD_UNPR": "0",
        "QTY_ALL_ORD_YN": "Y",
        "EXCG_ID_DVSN_CD": "KRX",
    }


@pytest.mark.parametrize(
    ("kwargs", "needle"),
    [
        (
            {"orgn_odno": "", "krx_fwdg_ord_orgno": _ORG_NO, "remaining_qty": 1},
            "ORGN_ODNO",
        ),
        (
            {"orgn_odno": "1", "krx_fwdg_ord_orgno": "", "remaining_qty": 1},
            "KRX_FWDG_ORD_ORGNO",
        ),
        (
            {"orgn_odno": "1", "krx_fwdg_ord_orgno": _ORG_NO, "remaining_qty": 0},
            "잔여수량",
        ),
    ],
)
def test_cancel_body_refuses_locally_rather_than_sending(
    kwargs: dict[str, Any], needle: str
) -> None:
    """Each of these is a ``[필수]`` field the wrapper refuses as empty."""
    with pytest.raises(ProbeError, match=needle):
        build_stock_cancel_body("12345678", "90", **kwargs)


# ---------------------------------------------------------------------------
# 2. REAL refusal
# ---------------------------------------------------------------------------


def test_mock_env_passes(mock_env: None) -> None:
    record = assert_mock_only_env()
    assert record["verdict"] == "MOCK_ONLY"
    assert record["observed"]["KIS_STOCK_MARKET"] == "mock"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("KIS_STOCK_MARKET", "real"),
        ("KIS_FUTURES_MARKET", "real"),
        ("KIS_REAL_TRADING", "true"),
        ("KIS_REAL_TRADING", "1"),
    ],
)
def test_refuses_a_real_environment(
    mock_env: None, monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    """The failing input the host seal cannot catch: a REAL CREDENTIAL.

    The paper stack exports ``KIS_STOCK_MARKET=real`` because stock quotes need
    the real key, so a probe that inherited the paper ``.env`` would hold a real
    app key while every host assertion still passed.
    """
    monkeypatch.setenv(name, value)
    with pytest.raises(SafetyViolation, match=name):
        assert_mock_only_env()


def test_a_real_environment_sends_nothing(
    mock_env: None,
    monkeypatch: pytest.MonkeyPatch,
    install: Any,
    tmp_path: Path,
) -> None:
    broker = install(_Broker())
    monkeypatch.setenv("KIS_STOCK_MARKET", "real")
    with pytest.raises(SafetyViolation):
        probe_psc(_args(_config_file(tmp_path), tmp_path))
    assert broker.calls == [], "a refused run must not have touched the broker"


def test_refuses_futures_asset(mock_env: None, tmp_path: Path) -> None:
    with pytest.raises(ProbeError, match="STOCK probe"):
        probe_psc(_args(_config_file(tmp_path), tmp_path, asset="futures"))


def test_refuses_without_a_symbol(mock_env: None, tmp_path: Path) -> None:
    with pytest.raises(ProbeError, match="--symbol"):
        probe_psc(_args(_config_file(tmp_path), tmp_path, symbol=""))


# ---------------------------------------------------------------------------
# 3. session and trading-day refusal
# ---------------------------------------------------------------------------


def test_window_accepts_an_instant_inside_it(tmp_path: Path) -> None:
    record = assert_session_window(load_config(_config_file(tmp_path)), _IN_WINDOW)
    assert record["trading_day"] is True
    assert record["window_kst"] == "09:00-15:20"


@pytest.mark.parametrize(
    "when",
    [
        datetime(2026, 11, 2, 8, 59, tzinfo=probes_stock_cancel.KST),
        datetime(2026, 11, 2, 15, 21, tzinfo=probes_stock_cancel.KST),
    ],
)
def test_refuses_outside_the_window(tmp_path: Path, when: datetime) -> None:
    with pytest.raises(ProbeError, match="outside the configured window"):
        assert_session_window(load_config(_config_file(tmp_path)), when)


def test_refuses_a_weekend(tmp_path: Path) -> None:
    saturday = datetime(2026, 11, 7, 10, 0, tzinfo=probes_stock_cancel.KST)
    with pytest.raises(ProbeError, match="not a KRX trading day"):
        assert_session_window(load_config(_config_file(tmp_path)), saturday)


def test_refuses_a_declared_holiday(tmp_path: Path) -> None:
    """2026-12-25 is in the tenant calendar's ``holidays`` (크리스마스)."""
    christmas = datetime(2026, 12, 25, 10, 0, tzinfo=probes_stock_cancel.KST)
    with pytest.raises(ProbeError, match="not a KRX trading day"):
        assert_session_window(load_config(_config_file(tmp_path)), christmas)


def test_refuses_a_year_the_calendar_does_not_cover(tmp_path: Path) -> None:
    """A holiday set that does not cover the year would call every weekday open."""
    later = datetime(2027, 11, 2, 10, 0, tzinfo=probes_stock_cancel.KST)
    with pytest.raises(ProbeError, match="outside it"):
        assert_session_window(load_config(_config_file(tmp_path)), later)


def test_outside_hours_sends_nothing(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    broker = install(
        _Broker(), now=datetime(2026, 11, 2, 16, 0, tzinfo=probes_stock_cancel.KST)
    )
    with pytest.raises(ProbeError, match="outside the configured window"):
        probe_psc(_args(_config_file(tmp_path), tmp_path))
    assert broker.calls == []


# ---------------------------------------------------------------------------
# 4. the flat-start proof
# ---------------------------------------------------------------------------


def test_refuses_when_the_symbol_is_already_held(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    broker = install(_Broker(holding=1))
    with pytest.raises(ProbeError, match="already holds 1 share"):
        probe_psc(_args(_config_file(tmp_path), tmp_path))
    assert broker.order_posts() == []


def test_refuses_when_an_order_is_already_on_the_book(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    broker = _Broker()
    broker.rows.append(
        broker._row(odno="0000001111", qty=1, filled=0, price="60000", side="BUY")
    )
    install(broker)
    with pytest.raises(ProbeError, match="open 005930 order row"):
        probe_psc(_args(_config_file(tmp_path), tmp_path))
    assert broker.order_posts() == []


def test_refuses_when_the_balance_walk_is_capped(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    """A walk that ran out of pages has NOT established "not held"."""
    broker = install(_Broker(balance_pages=99))
    with pytest.raises(ProbeError, match="PAGE_CAP"):
        probe_psc(_args(_config_file(tmp_path), tmp_path))
    assert broker.order_posts() == []


def test_refuses_when_the_balance_read_is_refused(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    broker = install(_Broker(balance_rt_cd="1"))
    with pytest.raises(ProbeError, match="REFUSED"):
        probe_psc(_args(_config_file(tmp_path), tmp_path))
    assert broker.order_posts() == []


def test_refuses_when_the_balance_read_is_throttled(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    """HTTP 429 is invisible in the parsed body — hence the verbose client call."""
    broker = install(_Broker(balance_http=429, balance_rt_cd="1"))
    with pytest.raises(ProbeError, match="RATE_LIMITED"):
        probe_psc(_args(_config_file(tmp_path), tmp_path))
    assert broker.order_posts() == []


def test_refuses_when_the_order_page_came_back_full(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    """A full page may have dropped rows, so "no order is open" is unproven.

    Three cancelled rows with a page row cap of 2: the flat check walks and the
    walk itself is capped, so the run refuses rather than concluding from a
    page that was full.
    """
    broker = _Broker(ccld_page_rows=1)
    for index in range(9):
        row = broker._row(
            odno=f"000000{index:04d}", qty=1, filled=0, price="60000", side="BUY"
        )
        row["cncl_yn"] = "Y"
        row["rmn_qty"] = "0"
        broker.rows.append(row)
    install(broker)
    with pytest.raises(ProbeError, match="PAGE_CAP"):
        probe_psc(_args(_config_file(tmp_path), tmp_path))
    assert broker.order_posts() == []


# ---------------------------------------------------------------------------
# 5. cleanup on the failure path
# ---------------------------------------------------------------------------


def test_cleanup_runs_and_cancels_when_a_trial_raises(
    mock_env: None, install: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The observation window blows up AFTER the order is resting.

    The cancel the probe would have sent never goes out, so the order is still
    on the book when the exception surfaces — exactly the state the ``finally``
    exists for.
    """
    broker = install(_Broker(cancel_shape="flag"))

    def _boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("observation exploded")

    monkeypatch.setattr(probes_stock_cancel, "_snapshot", _boom)
    with pytest.raises(RuntimeError, match="observation exploded"):
        probe_psc(_args(_config_file(tmp_path), tmp_path))
    assert broker.cancel_posts(), "the cleanup must have cancelled the resting order"
    assert all(not probes_stock_cancel._row_is_live(r) for r in broker.rows)


def test_the_cleanup_never_sells_a_holding_this_run_did_not_buy(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    """The failing input: the flat-start proof REFUSED, and shares are held.

    That is the one path where "flatten whatever the account holds" would sell
    somebody else's position — the flat-start guarantee is exactly what is
    missing there. ``placed`` is empty, so the cleanup does nothing at all.
    """
    broker = install(_Broker(holding=7))
    run = ProbeRun(probe_id="P-SC", title="t", mode="live", environment="MOCK_VTS")
    client = probes_order.MockTradingClient(
        ProbeCredentials(
            app_key="k",
            app_secret="s",
            account_no=_ACCOUNT,
            is_real=False,
            asset="stock",
        ),
        _StubAuth(),
        run,
        pace_s=0.0,
    )
    record = probes_stock_cancel._cleanup(
        client,
        run,
        OrderBudget(10),
        load_config(_config_file(tmp_path)),
        symbol=_SYMBOL,
        placed=[],
    )
    assert record["status"] == probes_stock_cancel._CLEAN_NOTHING_TO_DO
    assert "placed no accepted order" in record["reason"]
    assert broker.calls == [], "not even a read, let alone a sell"


def test_cleanup_reports_still_live_when_the_broker_ignores_the_cancel(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    """The broker accepts every cancel and changes nothing. Say so, do not pass."""
    install(_Broker(cancel_shape="none"))
    run = probe_psc(_args(_config_file(tmp_path), tmp_path))
    assert run.measurements["cleanup"]["status"] == _CLEAN_STILL_LIVE
    assert run.measurements["cleanup"]["orders_final_live"] >= 1


def test_the_account_ends_flat_after_a_full_fill(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    """Trial B fills fully: record that, sell it back, prove flat."""
    broker = install(_Broker(cancel_shape="flag", fills=True))
    run = probe_psc(_args(_config_file(tmp_path), tmp_path, trial="b"))
    assert (
        run.measurements["trial_b"]["partial_fill"]["outcome"] == _PARTIAL_FILLED_FULLY
    )
    assert run.measurements["cleanup"]["status"] == _CLEAN_FLAT
    assert broker.holding == 0
    sells = [c for c in broker.order_posts() if c["tr_id"].endswith("0801U")]
    assert len(sells) == 1, "exactly one flatten sell"
    assert sells[0]["body"]["ORD_DVSN"] == "01", "시장가, so the flatten does not rest"


def test_a_partial_fill_is_reported_when_the_broker_produces_one(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    """#980's input: 2 ordered, 1 filled, remainder cancelled."""
    broker = install(_Broker(cancel_shape="separate_row", partial_fill=1))
    run = probe_psc(_args(_config_file(tmp_path), tmp_path, trial="b"))
    partial = run.measurements["trial_b"]["partial_fill"]
    assert partial["outcome"] == probes_stock_cancel._PARTIAL_OBSERVED
    assert partial["filled_qty_before_cancel"] == 1
    assert run.measurements["cleanup"]["status"] == _CLEAN_FLAT
    assert broker.holding == 0


# ---------------------------------------------------------------------------
# 6. the five-value verdict
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("shape", "expected"),
    [
        ("flag", _SHAPE_ORIGINAL_FLAGGED),
        ("separate_row", _SHAPE_SEPARATE_ROW),
        ("both", _SHAPE_BOTH),
        ("none", _SHAPE_NONE),
    ],
)
def test_each_cancel_shape_comes_out_as_its_own_verdict(
    mock_env: None, install: Any, tmp_path: Path, shape: str, expected: str
) -> None:
    install(_Broker(cancel_shape=shape))
    run = probe_psc(_args(_config_file(tmp_path), tmp_path, trial="a"))
    assert run.measurements["trial_a"]["cancel_shape"]["shape"] == expected


def test_a_separate_row_records_the_unverified_profile_field(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    """``orgn_odno`` on a row a cancel produced — the thing #948 is blocked on."""
    install(_Broker(cancel_shape="separate_row"))
    run = probe_psc(_args(_config_file(tmp_path), tmp_path, trial="a"))
    record = run.measurements["trial_a"]["cancel_shape"]
    assert record["shape"] == _SHAPE_SEPARATE_ROW
    forms = record["derived_row_orgn_odno_forms"]
    assert forms, "the measured wire form must be recorded, not just the verdict"
    assert forms[0]["canonical_key"] == record["original_odno_key"]
    assert forms[0]["verbatim"].startswith("0"), "zero-padded, verbatim"


def test_an_unanswered_surface_is_undetermined_not_neither_observed() -> None:
    """The distinction #948 step 2 would go fail-open on.

    Same empty observation, two different causes: one snapshot answered and
    showed nothing (NEITHER_OBSERVED), the other never answered
    (UNDETERMINED). A reader that collapsed them would build a non-execution
    proof on a read that failed.
    """
    answered = [{"read_status": _READ_OK, "t_offset_ms": 0.0, "original_row": None}]
    unanswered = [
        {"read_status": _READ_TRANSIENT, "t_offset_ms": 0.0, "original_row": None}
    ]
    assert classify_cancel_shape(answered, "8687")["shape"] == _SHAPE_NONE
    assert classify_cancel_shape(unanswered, "8687")["shape"] == _SHAPE_UNDETERMINED
    assert classify_cancel_shape([], "8687")["shape"] == _SHAPE_UNDETERMINED


def test_a_truncated_page_cannot_establish_neither_observed() -> None:
    """A full page may have dropped the rows the negative verdict is about."""
    truncated = [
        {"read_status": _READ_TRUNCATED, "t_offset_ms": 0.0, "original_row": None}
    ]
    assert classify_cancel_shape(truncated, "8687")["shape"] == _SHAPE_UNDETERMINED


def test_a_truncated_page_still_counts_a_positive_observation() -> None:
    """A row that IS there is there, whatever else the page dropped."""
    seen = [
        {
            "read_status": _READ_TRUNCATED,
            "t_offset_ms": 12.0,
            "original_row": {"raw": {"cncl_yn": "Y"}},
            "derived_rows": [],
        }
    ]
    assert classify_cancel_shape(seen, "8687")["shape"] == _SHAPE_ORIGINAL_FLAGGED


def test_late_fill_after_the_cancel_ack_is_reported(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    """A fill that lands after the cancel is acknowledged — the #980 race."""
    install(_Broker(cancel_shape="flag", partial_fill=1, late_fill=True))
    run = probe_psc(_args(_config_file(tmp_path), tmp_path, trial="b"))
    late = run.measurements["trial_b"]["late_fill"]
    assert late["verdict"] == "LATE_FILL_OBSERVED_AFTER_CANCEL_ACK"
    assert late["filled_qty_before_cancel"] == 1
    assert late["peak_filled_qty_after_cancel"] == 2


def test_zero_observed_late_fills_is_not_zero_milliseconds() -> None:
    """P-FQP's rule: absence inside the window is 미확립, not a measured 0."""
    snapshots = [
        {
            "t_offset_ms": 0.0,
            "original_tot_ccld_qty": 0,
            "original_rmn_qty": 1,
            "original_cncl_yn": "Y",
            "read_status": _READ_OK,
        }
    ]
    record = classify_late_fill(
        filled_before_cancel=0, snapshots=snapshots, cancel_ack_rt_cd="0"
    )
    assert record["verdict"] == "NO_LATE_FILL_OBSERVED"
    assert record["first_growth_t_offset_ms"] is None
    assert "nothing here is a bound candidate" in record["feeds"]


def test_no_fill_quantity_read_is_undetermined() -> None:
    """An unread 총체결수량 is an unanswered question, not an answered 'no'."""
    snapshots = [
        {
            "t_offset_ms": 0.0,
            "original_tot_ccld_qty": None,
            "original_rmn_qty": None,
            "original_cncl_yn": None,
            "read_status": _READ_TRANSIENT,
        }
    ]
    record = classify_late_fill(
        filled_before_cancel=None, snapshots=snapshots, cancel_ack_rt_cd="0"
    )
    assert record["verdict"] == "UNDETERMINED_NO_FILL_QUANTITY_READ"


# ---------------------------------------------------------------------------
# 7. the order-call budget
# ---------------------------------------------------------------------------


def test_the_budget_refuses_rather_than_counting() -> None:
    budget = OrderBudget(2)
    budget.spend("a")
    budget.spend("b")
    assert budget.remaining == 0
    with pytest.raises(SafetyViolation, match="budget exhausted"):
        budget.spend("c")
    assert budget.describe() == {"limit": 2, "used": 2, "calls": ["a", "b"]}


def test_a_spent_budget_stops_the_run_before_the_next_order(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    """One call allowed: the submit goes out, the cancel does not.

    The run then fails with a SafetyViolation (``run.py`` writes no artifact
    for one), and the resting order is left for the operator — which the
    budget message says to raise deliberately rather than work around.
    """
    broker = install(_Broker(cancel_shape="flag"))
    with pytest.raises(SafetyViolation, match="budget exhausted"):
        probe_psc(
            _args(
                _config_file(tmp_path, **{"limits.max_order_calls": 1}),
                tmp_path,
                trial="a",
            )
        )
    assert len(broker.order_posts()) == 1
    assert broker.cancel_posts() == []


# ---------------------------------------------------------------------------
# config validation — every limit, no defaults
# ---------------------------------------------------------------------------


def test_the_shipped_config_loads() -> None:
    """The file the 11-02 run will actually read."""
    cfg = load_config()
    assert cfg.limits.pace_s >= cfg.limits.pace_s_floor >= 2.0
    assert cfg.trial_a.quantity <= cfg.limits.max_quantity
    assert cfg.session.start.strftime("%H:%M") == "09:00"
    assert cfg.session.end.strftime("%H:%M") == "15:20"
    assert (
        cfg.describe()["config_path"] == "config/broker_probes/stock_cancel_probe.yaml"
    )


@pytest.mark.parametrize(
    "key",
    [
        "limits.pace_s",
        "limits.max_order_calls",
        "limits.max_quantity",
        "limits.cleanup.cancel_attempts",
        "observation.cancel_window_s",
        "observation.poll_interval_s",
        "flat_check.balance_max_pages",
        "trials.a.quantity",
        "trials.b.enabled",
        "session.window.start",
    ],
)
def test_a_missing_limit_is_refused_not_defaulted(tmp_path: Path, key: str) -> None:
    path = _config_file(tmp_path, **{key: _DELETE})
    with pytest.raises(ProbeError, match="missing"):
        load_config(path)


def test_a_pace_below_its_own_floor_is_refused(tmp_path: Path) -> None:
    path = _config_file(tmp_path, **{"limits.pace_s": 0.0005})
    with pytest.raises(ProbeError, match="below limits.pace_s_floor"):
        load_config(path)


def test_a_quantity_above_the_cap_is_refused(tmp_path: Path) -> None:
    path = _config_file(tmp_path, **{"trials.b.quantity": 99})
    with pytest.raises(ProbeError, match="exceeds"):
        load_config(path)


def test_a_window_that_does_not_advance_is_refused(tmp_path: Path) -> None:
    path = _config_file(tmp_path, **{"session.window.end": "09:00"})
    with pytest.raises(ProbeError, match="not before end"):
        load_config(path)


def test_another_schema_version_is_refused(tmp_path: Path) -> None:
    path = _config_file(tmp_path, **{"schema_version": 2})
    with pytest.raises(ProbeError, match="schema_version"):
        load_config(path)


# ---------------------------------------------------------------------------
# artifact shape, and the structural safety claims
# ---------------------------------------------------------------------------


def test_artifact_shape(mock_env: None, install: Any, tmp_path: Path) -> None:
    broker = install(_Broker(cancel_shape="both"))
    run = probe_psc(_args(_config_file(tmp_path), tmp_path))
    payload = run.to_dict()

    assert payload["environment"] == "MOCK_VTS"
    assert payload["provenance_class"] == "MEASURED"
    assert payload["approval_status"] == "UNAPPROVED_CANDIDATE"
    for key in (
        "config",
        "mock_only_env_gate",
        "session_gate",
        "account",
        "flat_start",
        "trial_a",
        "trial_b",
        "cleanup",
        "order_call_budget",
    ):
        assert key in payload["measurements"], key

    trial = payload["measurements"]["trial_a"]
    assert trial["cancel_shape"]["shape"] == _SHAPE_BOTH
    assert trial["pre_cancel"]["original_row"]["raw"]["pdno"] == _SYMBOL
    assert trial["post_cancel_snapshots"], "every snapshot's rows are kept verbatim"
    assert trial["cancel"]["request_body"]["RVSE_CNCL_DVSN_CD"] == "02"
    assert payload["measurements"]["cleanup"]["status"] == _CLEAN_FLAT
    assert payload["measurements"]["order_call_budget"]["used"] == len(
        broker.order_posts()
    ) + len(broker.cancel_posts())

    written = Path(run.write(out_dir=tmp_path / "out"))
    assert written.exists()


def test_the_artifact_masks_the_account(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    """No account number, no key: ``redact`` masks CANO/ACNT_PRDT_CD everywhere."""
    install(_Broker(cancel_shape="flag"))
    run = probe_psc(_args(_config_file(tmp_path), tmp_path, trial="a"))
    blob = str(run.to_dict())
    assert _ACCOUNT not in blob
    assert _ACCOUNT[:8] not in blob
    assert "test-secret" not in blob
    assert run.measurements["account"]["fingerprint"]


def test_every_call_went_to_the_mock_host_with_a_mock_trading_tr(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    """The structural claim, asserted on the wire rather than on a docstring."""
    broker = install(_Broker(cancel_shape="both"))
    probe_psc(_args(_config_file(tmp_path), tmp_path))
    assert broker.calls
    for call in broker.calls:
        assert MOCK_HOST in call["url"], call["url"]
        if "/trading/" in call["url"]:
            assert_mock_trading_tr(call["tr_id"])


def test_a_stopped_trial_a_does_not_start_trial_b(
    mock_env: None, install: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rejected submit stops the run: no order goes on top of an unknown state."""
    broker = _Broker(cancel_shape="flag")

    def _reject(body: dict[str, Any], tr_id: str) -> dict[str, Any]:
        return {
            "rt_cd": "1",
            "msg_cd": "APBK0919",
            "msg1": "모의투자 주문이 불가한 계좌입니다",
        }

    monkeypatch.setattr(broker, "_submit", _reject)
    install(broker)
    run = probe_psc(_args(_config_file(tmp_path), tmp_path))
    assert run.measurements["trial_a"]["stopped_at"] == "submit"
    assert "trial_b" not in run.measurements
    assert any("trial A stopped" in skip["reason"] for skip in run.skips)


def test_trial_b_is_skipped_with_a_reason_when_disabled(
    mock_env: None, install: Any, tmp_path: Path
) -> None:
    install(_Broker(cancel_shape="flag"))
    run = probe_psc(
        _args(_config_file(tmp_path, **{"trials.b.enabled": False}), tmp_path)
    )
    assert "trial_b" not in run.measurements
    assert any("trials.b.enabled is false" in skip["reason"] for skip in run.skips)


def test_the_dry_run_sends_nothing_and_prints_the_cancel_body(
    mock_env: None, install: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broker = install(_Broker())
    run = probe_psc(_args(_config_file(tmp_path), tmp_path, confirm=False))
    assert broker.calls == []
    assert run.mode == "dry-run"
    body = run.observations[0]["dry_run_cancel_body"]
    assert body["RVSE_CNCL_DVSN_CD"] == "02"
    out = capsys.readouterr().out
    assert "PSC_STOP=dry_run" in out


def test_the_three_anchored_lines_are_printed_exactly_once(
    mock_env: None, install: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The runner template reads only these, on every path the probe leaves by."""
    install(_Broker(cancel_shape="flag"))
    probe_psc(_args(_config_file(tmp_path), tmp_path))
    out = capsys.readouterr().out.splitlines()
    for prefix in ("PSC_STOP=", "PSC_CANCEL_SHAPE=", "PSC_FLAT_AT_END="):
        assert len([line for line in out if line.startswith(prefix)]) == 1, prefix
    assert f"PSC_STOP={_STOP_NONE}" in out
    assert "PSC_FLAT_AT_END=yes" in out


# ---------------------------------------------------------------------------
# the runner template — the same three gates run_p_ca.sh and run_p8.sh carry
#
# Not new guards: these are the gates the two existing runner templates already
# have, applied to a third file of the same kind. Each was paid for once — the
# 2026-09-28 P-8 runner that deleted itself and left one wrong line as the only
# record, and the SC2034 verdict that depended on how many files shellcheck was
# handed.
# ---------------------------------------------------------------------------

_RUNNERS_DIR = (
    Path(__file__).resolve().parents[2] / "tools" / "broker_probes" / "runners"
)
_RUNNER = _RUNNERS_DIR / "run_p_sc.sh"
_RUNNER_COMMON = _RUNNERS_DIR / "_common.sh"


def test_the_runner_exists_and_is_executable() -> None:
    import os

    assert _RUNNER.is_file(), _RUNNER
    assert os.access(_RUNNER, os.X_OK), f"{_RUNNER} is not executable"


def test_the_policy_version_is_the_one_the_runner_expects() -> None:
    """The handshake constant. A runner copied out of another tree aborts.

    Pinned as a literal on purpose: changing the printed-line contract has to
    change this string, and changing this string has to change the runner.
    """
    assert probes_stock_cancel.POLICY_VERSION == "p-sc-cancel-shape/1"
    assert (
        f"EXPECT_POLICY_VERSION={probes_stock_cancel.POLICY_VERSION}"
        in _RUNNER.read_text(encoding="utf-8")
    )


def test_the_runner_shellchecks_alone_and_with_the_shared_helpers() -> None:
    """Both ways, because a verdict that depends on the input set is not a gate."""
    import os
    import shutil
    import subprocess

    shellcheck = shutil.which("shellcheck")
    if shellcheck is None:
        if os.environ.get("CI"):
            pytest.fail(
                "shellcheck is missing on CI, where this gate is meant to run; "
                "add it to the workflow rather than letting the check vanish"
            )
        pytest.skip("shellcheck is not installed locally — CI runs this gate")
    for argv in ([_RUNNER], [_RUNNER, _RUNNER_COMMON]):
        result = subprocess.run(
            [shellcheck, "--severity=warning", *(str(f) for f in argv)],
            capture_output=True,
            text=True,
        )
        assert (
            result.returncode == 0
        ), f"{[f.name for f in argv]}: {result.stdout}{result.stderr}"


def test_the_runner_carries_no_non_empty_instance_default() -> None:
    """A default is how one slot's symbol or fingerprint becomes the next one's.

    Only "off" defaults are allowed (empty, or the literal 0). The shared
    helpers must carry no ``PSC_`` name at all — they are prefix-free by
    construction, and a name creeping in there is one runner reading another's
    environment.
    """
    import re

    pairs = set(
        re.findall(r"\$\{(PSC_[A-Z_]+):-([^}]*)\}", _RUNNER.read_text(encoding="utf-8"))
    )
    assert not re.findall(r"\bPSC_[A-Z_]+", _RUNNER_COMMON.read_text(encoding="utf-8"))
    assert {name for name, default in pairs if default not in ("", "0")} == set(), pairs
    assert {name for name, _d in pairs} <= {
        "PSC_LOG",
        "PSC_ALLOW_SHARED_CHECKOUT",
        "PSC_CRON_MARK",
        "PSC_CONFIG",
    }, pairs


def test_the_runner_never_deletes_itself() -> None:
    """The 2026-09-28 defect: the only record of what ran was one wrong line."""
    import re

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


def test_the_runner_carries_no_limit_of_its_own() -> None:
    """Pacing, quantities and windows live in the YAML, not in two places.

    ``PSC_CONFIG`` names a FILE; it must not be joined by a variable that
    carries a number the config already owns.
    """
    import re

    text = _RUNNER.read_text(encoding="utf-8")
    forbidden = re.findall(
        r"\bPSC_(PACE_S|QUANTITY|PRICE_OFFSET_PCT|MAX_ORDER_CALLS|POLL_MS"
        r"|WINDOW_S|CANCEL_WINDOW_S|MAX_QUANTITY)\b",
        text,
    )
    assert not forbidden, (
        "these are limits the P-SC config owns; a runner variable for one is a "
        f"second source for it: {sorted(set(forbidden))}"
    )


def test_a_run_whose_probe_raises_still_leaves_a_salvageable_run(
    mock_env: None, install: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``run.py`` salvages the partially populated run; it must carry the gates."""
    ProbeRun.reset_salvage()
    install(_Broker(holding=1))
    with pytest.raises(ProbeError):
        probe_psc(_args(_config_file(tmp_path), tmp_path))
    salvaged = ProbeRun.salvage("P-SC")
    assert salvaged is not None
    assert salvaged.measurements["mock_only_env_gate"]["verdict"] == "MOCK_ONLY"
    assert salvaged.measurements["config"]["limits"]["max_order_calls"] == 10
