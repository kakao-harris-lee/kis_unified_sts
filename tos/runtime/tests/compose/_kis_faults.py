"""A fault-injectable KIS 모의투자 (VTS) double — one scripted answer per CALL, not per path."""

from __future__ import annotations

import threading
from collections import deque
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from .test_kis_mock_e2e_honesty import _ORDER_PATH, _TOKEN_PATH, _broker_fact_paths
from .test_kis_mock_fill_finality_e2e import _witness_paths

__all__ = [
    "ORDER_PATH",
    "TOKEN_PATH",
    "Call",
    "FaultKind",
    "ScriptedKisBroker",
]

TOKEN_PATH = _TOKEN_PATH
ORDER_PATH = _ORDER_PATH

FAKE_BEARER_TOKEN = "fault-harness-fake-bearer-token-never-in-evidence"


class Call(Enum):
    """The five call classes one stock-MOCK tenant makes, plus the witness's own balance read."""

    TOKEN = "token"
    FACTS_BALANCE = "facts_balance"
    FACTS_QUOTE = "facts_quote"
    ORDER = "order"
    WITNESS_BALANCE = "witness_balance"
    DAILY_CCLD = "daily_ccld"


class FaultKind(Enum):
    """What one call answers. ``OK`` answers the call class's current healthy body."""

    OK = "ok"
    TOKEN_ERROR = "token_error"
    RT_CD_NOT_OK = "rt_cd_not_ok"
    HTTP_500 = "http_500"
    TIMEOUT = "timeout"


_TOKEN_ERROR_BODY: dict[str, Any] = {
    "error_code": "EGW00133",
    "error_description": "접근토큰 발급 잠시 후 다시 시도하세요(1분당 1회)",
}
_RATE_LIMITED_FIELDS: dict[str, Any] = {
    "rt_cd": "1",
    "msg_cd": "EGW00201",
    "msg1": "초당 거래건수를 초과하였습니다.",
}
_HTTP_500_BODY: dict[str, Any] = {"error_description": "internal server error"}


def _healthy_token_body() -> dict[str, Any]:
    return {"access_token": FAKE_BEARER_TOKEN, "expires_in": 86400}


def _healthy_facts_balance_body() -> dict[str, Any]:
    return {"rt_cd": "0", "msg1": "-", "output1": []}


def _healthy_quote_body(*, temp_stop_yn: str = "N") -> dict[str, Any]:
    return {"rt_cd": "0", "output": {"temp_stop_yn": temp_stop_yn}}


def order_ack_body(odno: str) -> dict[str, Any]:
    """One healthy ``order_cash`` ACK, in the measured wire shape."""
    return {
        "rt_cd": "0",
        "msg_cd": "APBK0013",
        "msg1": "정상처리",
        "output": {"ODNO": odno},
    }


def witness_balance_body(holdings: tuple[tuple[str, Decimal], ...]) -> dict[str, Any]:
    return {
        "rt_cd": "0",
        "output1": [
            {"pdno": symbol, "hldg_qty": format(quantity, "f")}
            for symbol, quantity in holdings
        ],
        "output2": [{"dnca_tot_amt": "1000000"}],
    }


def daily_ccld_body(rows: list[dict[str, str]]) -> dict[str, Any]:
    return {"rt_cd": "0", "output1": list(rows), "output2": {}}


class ScriptedKisBroker:
    """A fault-injectable view of one :class:`FakeKisServer`, keyed by :class:`Call`."""

    def __init__(
        self,
        server: FakeKisServer,
        config_dir: Path,
        *,
        timeout_delay_s: float,
    ) -> None:
        self._server = server
        self._config_dir = config_dir
        self._timeout_delay_s = timeout_delay_s
        self._lock = threading.Lock()
        facts_balance, facts_quote = _broker_fact_paths(config_dir)
        self._paths: dict[Call, str] = {
            Call.TOKEN: TOKEN_PATH,
            Call.FACTS_BALANCE: facts_balance,
            Call.FACTS_QUOTE: facts_quote,
            Call.ORDER: ORDER_PATH,
        }
        self._healthy: dict[Call, dict[str, Any]] = {
            Call.TOKEN: _healthy_token_body(),
            Call.FACTS_BALANCE: _healthy_facts_balance_body(),
            Call.FACTS_QUOTE: _healthy_quote_body(),
            Call.ORDER: order_ack_body("FAULT-HARNESS-UNSET"),
            Call.WITNESS_BALANCE: witness_balance_body(()),
            Call.DAILY_CCLD: daily_ccld_body([]),
        }
        self._queues: dict[Call, deque[FaultKind]] = {call: deque() for call in Call}
        self._counts: dict[Call, int] = dict.fromkeys(Call, 0)
        for call in self._paths:
            self._arm(call)

    def bind_trading_date(self, date: str) -> None:
        """Arm the two witness GETs, whose query carries the trading date the runtime reports."""
        balance, orders = _witness_paths(self._config_dir, date)
        with self._lock:
            self._paths[Call.WITNESS_BALANCE] = balance
            self._paths[Call.DAILY_CCLD] = orders
        distinct = set(self._paths.values())
        assert len(distinct) == len(self._paths), sorted(self._paths.items())
        self._arm(Call.WITNESS_BALANCE)
        self._arm(Call.DAILY_CCLD)

    def order_ack(self, odno: str) -> None:
        """The ODNO the next healthy order POST answers with."""
        self._set_healthy(Call.ORDER, order_ack_body(odno))

    def witness(
        self,
        *,
        rows: list[dict[str, str]],
        holdings: tuple[tuple[str, Decimal], ...],
    ) -> None:
        """What the broker holds and what its daily-ccld walk reports — the "fill" half of a send."""
        self._set_healthy(Call.WITNESS_BALANCE, witness_balance_body(holdings))
        self._set_healthy(Call.DAILY_CCLD, daily_ccld_body(rows))

    def temporarily_halted(self, *, halted: bool) -> None:
        """``temp_stop_yn`` on the quote GET — the other way item 12's tradability goes None."""
        self._set_healthy(
            Call.FACTS_QUOTE, _healthy_quote_body(temp_stop_yn="Y" if halted else "N")
        )

    def script(self, call: Call, *faults: FaultKind) -> None:
        """Queue one answer per upcoming call of ``call``; later calls answer healthily."""
        if call is Call.TOKEN and FaultKind.RT_CD_NOT_OK in faults:
            raise ValueError(
                "ScriptedKisBroker: the token endpoint has no rt_cd — script TOKEN_ERROR"
            )
        with self._lock:
            self._queues[call].extend(faults)
        self._arm(call)

    def clear(self, call: Call) -> None:
        """Drop every queued fault for ``call`` (it answers healthily from the next call on)."""
        with self._lock:
            self._queues[call].clear()
        self._arm(call)

    def calls(self, call: Call) -> int:
        """How many requests of this class the server has answered."""
        with self._lock:
            return self._counts[call]

    def pending(self, call: Call) -> tuple[FaultKind, ...]:
        """The faults still queued for ``call`` — empty means every scripted fault was served."""
        with self._lock:
            return tuple(self._queues[call])

    def _set_healthy(self, call: Call, body: dict[str, Any]) -> None:
        with self._lock:
            self._healthy[call] = body
        if call in self._paths:
            self._arm(call)

    def _arm(self, call: Call) -> None:
        """(Re-)register ``call``'s route from the head of its fault queue, or healthy."""
        with self._lock:
            path = self._paths.get(call)
            if path is None:
                return
            queue = self._queues[call]
            fault = queue[0] if queue else FaultKind.OK
            status, body, delay_s, reset = self._answer(call, fault)
        self._server.set_response(
            path,
            status=status,
            body=body,
            delay_s=delay_s,
            reset=reset,
            on_request=lambda: self._advance(call),
        )

    def _advance(self, call: Call) -> None:
        """The fake server's post-bind hook: count this call and arm the route for the next one."""
        with self._lock:
            self._counts[call] += 1
            if self._queues[call]:
                self._queues[call].popleft()
        self._arm(call)

    def _answer(
        self, call: Call, fault: FaultKind
    ) -> tuple[int, dict[str, Any] | None, float, bool]:
        """``(status, body, delay_s, reset)`` for one call — the caller holds ``self._lock``."""
        healthy = self._healthy[call]
        if fault is FaultKind.OK:
            return 200, healthy, 0.0, False
        if fault is FaultKind.TOKEN_ERROR:
            return 403, _TOKEN_ERROR_BODY, 0.0, False
        if fault is FaultKind.RT_CD_NOT_OK:
            return 200, {**healthy, **_RATE_LIMITED_FIELDS}, 0.0, False
        if fault is FaultKind.HTTP_500:
            return 500, _HTTP_500_BODY, 0.0, False
        if fault is FaultKind.TIMEOUT:
            return 200, None, self._timeout_delay_s, True
        raise AssertionError(f"unhandled fault kind {fault!r}")
