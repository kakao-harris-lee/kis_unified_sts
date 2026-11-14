"""``KisStockBrokerWitness`` — the real KIS 모의투자 ``BrokerWitness`` (W3 lane,"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, runtime_checkable
from zoneinfo import ZoneInfo

from tos_runtime.recon.ports import (
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
    WitnessUnavailable,
)
from tos_runtime.recon.witness_kis_client import (
    KisWitnessClientError,
    KisWitnessHttpClient,
    RawGetResponse,
)
from tos_runtime.recon.witness_kis_config import KisWitnessConfig, refuse_futures_asset
from tos_runtime.transport.kis_mock.account import KisAccountError, split_kis_account

__all__ = [
    "KisOrderRow",
    "KisStockBrokerWitness",
    "KisWitnessCredentialSession",
    "KisWitnessRequestCredentials",
    "KstDateSource",
    "SystemKstDateSource",
    "TrustedKstDateSource",
]

_TR_CONT_MORE_CODES = ("M", "F")

_YYYYMMDD = re.compile(r"[0-9]{8}")

_TR_CONT_REQUEST_NEXT = "N"

_CANCELLED = "Y"


def _decimal_or_none(value: Any) -> Decimal | None:
    """Best-effort ``Decimal`` coercion for a JSON-decoded numeric/string field."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (str, int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    return None


def _header_value(secret: bytes) -> str:
    """ASCII-decode one credential for its header. A non-ASCII credential is refused WITHOUT"""
    try:
        return secret.decode("ascii")
    except UnicodeDecodeError:
        pass
    raise ValueError("KIS credential is not ASCII — refusing to send it")


@runtime_checkable
class KisWitnessRequestCredentials(Protocol):
    """What one request needs, valid only inside the ``with`` block that produced it."""

    access_token: str

    def app_key(self) -> bytes:
        """The KIS app key bytes for the ``appkey`` header (raises once the block exits)."""
        ...

    def app_secret(self) -> bytes:
        """The KIS app secret bytes for the ``appsecret`` header (raises once the block"""
        ...


@runtime_checkable
class KisWitnessCredentialSession(Protocol):
    """The injected credential owner this witness asks for one request's credentials"""

    def request_credentials(
        self,
    ) -> AbstractContextManager[KisWitnessRequestCredentials]:
        """Token + app key/secret for one request, inside the ``with`` block only."""
        ...


@runtime_checkable
class KstDateSource(Protocol):
    """Supplies "today" in KST as ``YYYYMMDD`` — the one ambient-time fact 주식일별"""

    def today(self) -> str:
        """Return today's KST calendar date as ``YYYYMMDD``."""
        ...


class SystemKstDateSource:
    """Reads the real wall clock UNGATED by trusted time — kept for standalone measurement only."""

    _KST = ZoneInfo("Asia/Seoul")

    def today(self) -> str:
        return datetime.now(self._KST).strftime("%Y%m%d")


class _UnixMsReading(Protocol):
    @property
    def unix_ms(self) -> int: ...


class _WallClockLike(Protocol):
    """Structural stand-in for :class:`tos_runtime.calendar.ports.WallClockReference` — kept"""

    def read(self) -> _UnixMsReading | None: ...


class TrustedKstDateSource:
    """``today()`` from a :class:`~tos_runtime.calendar.ports.WallClockReference` — in production"""

    _KST = ZoneInfo("Asia/Seoul")

    def __init__(self, wall_clock: _WallClockLike) -> None:
        self._wall_clock = wall_clock

    def today(self) -> str:
        reading = self._wall_clock.read()
        if reading is None:
            raise WitnessUnavailable(
                "TrustedKstDateSource: no trusted wall-clock reading — refusing to guess the "
                "inquiry date"
            )
        return datetime.fromtimestamp(reading.unix_ms / 1000, tz=self._KST).strftime(
            "%Y%m%d"
        )


def _read_ctx_key(body: Mapping[str, Any], suffix: str, kind: str) -> str:
    name = f"ctx_area_{kind}{suffix}"
    return str(body.get(name) or "").strip()


@dataclass(frozen=True)
class _WalkOutcome:
    """The rows and (for the balance walk only) the ``output2`` block accumulated across"""

    pages: tuple[list[dict[str, Any]] | None, ...]
    output2_first: dict[str, Any] | None

    @property
    def containers_wellformed(self) -> bool:
        """Whether every page carried a genuine ``output1`` list."""
        return all(rows is not None for rows in self.pages)


def _refuse_instrument_conflict(row: KisOrderRow, *, queried: str) -> None:
    """A row must name the instrument it was asked for (PR-3b review HIGH 2). The witness"""
    if row.pdno is None or (queried and row.pdno != queried):
        raise WitnessUnavailable(
            f"KisStockBrokerWitness: order row {row.odno!r} names instrument {row.pdno!r}, "
            f"queried {queried or '(any)'!r} — a row that does not name the queried instrument "
            "cannot corroborate anything"
        )


def _order_rows_or_refuse(
    outcome: _WalkOutcome, *, queried: str
) -> tuple[dict[str, Any], ...]:
    """Every row of a completed order walk, or refuse the whole read (issue #981)."""
    if not outcome.containers_wellformed:
        raise WitnessUnavailable(
            f"KisStockBrokerWitness: an order page for {queried or '(any)'!r} carried no "
            "output1 list (absent, null, or not a list) — a page that contributes no rows "
            "cannot be told from one that listed none, and a row it hid could be an orphan "
            "order; refusing to return a read missing it"
        )
    rows: list[dict[str, Any]] = []
    for page in outcome.pages:
        for row in page or ():
            if not isinstance(row, dict):
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: an order row for {queried or '(any)'!r} is "
                    f"{type(row).__name__}, not an object — a row this witness cannot read "
                    "could be an orphan order; refusing to drop it from the read"
                )
            rows.append(row)
    return tuple(rows)


@dataclass(frozen=True)
class KisOrderRow:
    """One 주식일별주문체결조회 (``VTTC0081R``) ``output1`` row, typed — the ONE parse of that row"""

    odno: str | None
    orgn_odno: str | None
    ord_dt: str | None
    pdno: str | None
    ord_qty: Decimal | None
    tot_ccld_qty: Decimal | None
    rmn_qty: Decimal | None
    rjct_qty: Decimal | None
    cancelled: bool

    @classmethod
    def from_wire(cls, row: Mapping[str, Any]) -> KisOrderRow:
        def _text(name: str) -> str | None:
            value = row.get(name)
            if not isinstance(value, str):
                return None
            return value.strip() or None

        ord_dt = str(row.get("ord_dt") or "").strip()
        return cls(
            odno=_text("odno"),
            orgn_odno=_text("orgn_odno"),
            ord_dt=ord_dt if _YYYYMMDD.fullmatch(ord_dt) is not None else None,
            pdno=_text("pdno"),
            ord_qty=_decimal_or_none(row.get("ord_qty")),
            tot_ccld_qty=_decimal_or_none(row.get("tot_ccld_qty")),
            rmn_qty=_decimal_or_none(row.get("rmn_qty")),
            rjct_qty=_decimal_or_none(row.get("rjct_qty")),
            cancelled=str(row.get("cncl_yn") or "").strip() == _CANCELLED,
        )


class KisStockBrokerWitness:
    """A :class:`~tos_runtime.recon.ports.BrokerWitness` over the real KIS 모의투자 stock"""

    def __init__(
        self,
        *,
        config: KisWitnessConfig,
        client: KisWitnessHttpClient,
        credential_session: KisWitnessCredentialSession,
        date_source: KstDateSource,
        asset: str = "stock",
    ) -> None:
        """Wire this witness's dependencies (all injected — no ambient state beyond the"""
        refuse_futures_asset(asset)
        self._config = config
        self._client = client
        self._credential_session = credential_session
        self._date_source = date_source

    def observe(
        self,
        scope: WitnessScope,
        *,
        today: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
        before_balance: Callable[[], None] | None = None,
    ) -> WitnessSnapshot:
        """Observe this account's stock positions/cash and today's stock order fills."""
        try:
            cano, acnt_prdt_cd = self._split_account(scope.account)
            today = today or self._date_source.today()
            older_dates = sorted(set(scope.order_dates) - {today})
            dates = (today, *older_dates)
            rows: tuple[KisOrderRow, ...] = ()
            for date in older_dates:
                rows += self._read_order_rows(
                    cano, acnt_prdt_cd, scope, date, deadline_expired=deadline_expired
                )
            if before_balance is not None:
                before_balance()
            positions, cash, positions_complete = self._read_balance(
                cano, acnt_prdt_cd, scope, deadline_expired=deadline_expired
            )
            rows = (
                self._read_order_rows(
                    cano, acnt_prdt_cd, scope, today, deadline_expired=deadline_expired
                )
                + rows
            )
        except WitnessUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - the port's own two-outcome contract
            raise WitnessUnavailable(
                f"KisStockBrokerWitness.observe: could not complete — {type(exc).__name__}"
            ) from exc

        return WitnessSnapshot(
            observed_at_generation=scope.as_of_generation,
            orders=tuple(self._order_from_row(row) for row in rows),
            positions=positions,
            positions_complete=positions_complete,
            cash=cash,
            provenance="kis-mock-stock",
            independent_of_evidence_store=True,
            order_inquiry_date=today if len(dates) == 1 else None,
        )

    def order_rows(
        self,
        scope: WitnessScope,
        *,
        inquiry_date: str | None = None,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[str, tuple[KisOrderRow, ...]]:
        """One date's 주식일별주문체결조회 rows — no balance read (the post-ACK fill observer's"""
        try:
            cano, acnt_prdt_cd = self._split_account(scope.account)
            date = inquiry_date or self._date_source.today()
            return date, self._read_order_rows(
                cano, acnt_prdt_cd, scope, date, deadline_expired=deadline_expired
            )
        except WitnessUnavailable:
            raise
        except (
            Exception
        ) as exc:  # noqa: BLE001 - same two-outcome contract as observe()
            raise WitnessUnavailable(
                f"KisStockBrokerWitness.order_rows: could not complete — {type(exc).__name__}"
            ) from exc

    @staticmethod
    def _split_account(account: str) -> tuple[str, str]:
        """Split ``scope.account`` into KIS's ``(CANO, ACNT_PRDT_CD)`` pair."""
        try:
            parsed = split_kis_account(account)
        except KisAccountError as exc:
            raise WitnessUnavailable(
                f"KisStockBrokerWitness: scope.account is not a KIS 8-2 account ({exc}) — this "
                "witness cannot answer for a non-KIS-shaped account identifier."
            ) from None
        return parsed.cano, parsed.acnt_prdt_cd

    @staticmethod
    def _headers(
        credentials: KisWitnessRequestCredentials, *, tr_id: str, tr_cont: str
    ) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {credentials.access_token}",
            "appkey": _header_value(credentials.app_key()),
            "appsecret": _header_value(credentials.app_secret()),
            "tr_id": tr_id,
            "custtype": "P",
        }
        if tr_cont:
            headers["tr_cont"] = tr_cont
        return headers

    def _get_page(
        self, *, path: str, tr_id: str, params: Mapping[str, str], tr_cont: str
    ) -> RawGetResponse:
        with self._credential_session.request_credentials() as credentials:
            try:
                return self._client.get(
                    path,
                    headers=self._headers(credentials, tr_id=tr_id, tr_cont=tr_cont),
                    params=params,
                )
            except KisWitnessClientError as exc:
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: transport failure on {path} — "
                    f"{type(exc).__name__}"
                ) from exc

    def _walk_continuation(
        self,
        *,
        path: str,
        tr_id: str,
        build_params: Any,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> _WalkOutcome:
        """Walk ``CTX_AREA_FK100``/``NK100`` to completion, or raise."""
        pages: list[list[dict[str, Any]] | None] = []
        output2_first: dict[str, Any] | None = None
        fk = nk = ""
        for index in range(self._config.max_pages):
            if deadline_expired is not None and deadline_expired():
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: {tr_id} walk stopped by the caller's deadline "
                    f"before page {index} — refusing to return a partial order/holdings "
                    "list (the same answer our own max_pages cap gives)"
                )
            tr_cont = "" if index == 0 else _TR_CONT_REQUEST_NEXT
            response = self._get_page(
                path=path, tr_id=tr_id, params=build_params(fk, nk), tr_cont=tr_cont
            )
            if response.status != 200:
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: page {index} of {tr_id} returned HTTP "
                    f"{response.status} (expected 200) — refusing to trust its body"
                )
            if response.json is None:
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: page {index} of {tr_id} did not parse as "
                    "JSON"
                )
            body = response.json
            rt_cd = str(body.get("rt_cd") or "").strip()
            if rt_cd != "0":
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: page {index} of {tr_id} rejected "
                    f"(rt_cd={rt_cd!r}, msg_cd={body.get('msg_cd')!r})"
                )
            rows = body.get("output1")
            pages.append(rows if isinstance(rows, list) else None)
            if output2_first is None:
                out2 = body.get("output2")
                if isinstance(out2, list) and out2 and isinstance(out2[0], dict):
                    output2_first = out2[0]

            next_fk = _read_ctx_key(body, "100", "fk")
            next_nk = _read_ctx_key(body, "100", "nk")
            tr_cont_out = str(response.headers.get("tr_cont") or "").strip()
            more = tr_cont_out in _TR_CONT_MORE_CODES

            if not more:
                return _WalkOutcome(tuple(pages), output2_first)

            if not next_fk and not next_nk:
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: page {index} of {tr_id} answered "
                    f"tr_cont={tr_cont_out!r} (more follows) but returned no "
                    "continuation key — cannot walk further, refusing to return a "
                    "partial result"
                )
            if (next_fk, next_nk) == (fk, nk):
                raise WitnessUnavailable(
                    f"KisStockBrokerWitness: continuation keys did not advance on page "
                    f"{index} of {tr_id} while tr_cont={tr_cont_out!r} still signalled "
                    "more — a further request would repeat this page; refusing to loop "
                    "or return a partial result"
                )
            fk, nk = next_fk, next_nk
        raise WitnessUnavailable(
            f"KisStockBrokerWitness: {tr_id} walk stopped at max_pages="
            f"{self._config.max_pages} while the broker was still signalling more — "
            "this is OUR cap, not the broker's end-of-set; refusing to return a "
            "partial holdings/order list (contrast tools/broker_probes/probes_balance.py, "
            "which is allowed to report a lower bound — a WitnessSnapshot may not)"
        )

    def _read_balance(
        self,
        cano: str,
        acnt_prdt_cd: str,
        scope: WitnessScope,
        *,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[tuple[tuple[str, Decimal], ...], Decimal | None, bool]:
        """주식 잔고조회 — mirrors ``tools/broker_probes/probes_balance.py``'s own"""

        def build_params(fk: str, nk: str) -> dict[str, str]:
            return {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": fk,
                "CTX_AREA_NK100": nk,
            }

        outcome = self._walk_continuation(
            path=self._config.balance_path,
            tr_id=self._config.balance_tr_id,
            build_params=build_params,
            deadline_expired=deadline_expired,
        )

        instruments = {key.instrument for key in scope.instrument_keys}
        positions: list[tuple[str, Decimal]] = []
        complete = outcome.containers_wellformed
        for rows in outcome.pages:
            for row in rows if rows is not None else ():
                if not isinstance(row, dict):
                    complete = False
                    continue
                raw_symbol = row.get("pdno")
                symbol = raw_symbol.strip() if isinstance(raw_symbol, str) else ""
                qty = _decimal_or_none(row.get("hldg_qty"))
                if not symbol or qty is None:
                    complete = False
                    continue
                if qty <= 0:
                    continue
                if instruments and symbol not in instruments:
                    continue
                positions.append((symbol, qty))

        cash = (
            _decimal_or_none(outcome.output2_first.get("dnca_tot_amt"))
            if outcome.output2_first is not None
            else None
        )
        return tuple(positions), cash, complete

    def _read_order_rows(
        self,
        cano: str,
        acnt_prdt_cd: str,
        scope: WitnessScope,
        today: str,
        *,
        deadline_expired: Callable[[], bool] | None = None,
    ) -> tuple[KisOrderRow, ...]:
        """주식일별주문체결조회 — mirrors ``tools/broker_probes/probes_order.py``'s own"""
        symbols = [key.instrument for key in scope.instrument_keys] or [""]

        orders: list[KisOrderRow] = []
        for symbol in symbols:

            def build_params(
                fk: str, nk: str, *, symbol: str = symbol
            ) -> dict[str, str]:
                return {
                    "CANO": cano,
                    "ACNT_PRDT_CD": acnt_prdt_cd,
                    "INQR_STRT_DT": today,
                    "INQR_END_DT": today,
                    "SLL_BUY_DVSN_CD": "00",
                    "PDNO": symbol,
                    "CCLD_DVSN": "00",
                    "INQR_DVSN": "00",
                    "INQR_DVSN_3": "00",
                    "ORD_GNO_BRNO": "",
                    "ODNO": "",
                    "INQR_DVSN_1": "",
                    "CTX_AREA_FK100": fk,
                    "CTX_AREA_NK100": nk,
                    "EXCG_ID_DVSN_CD": "KRX",
                }

            outcome = self._walk_continuation(
                path=self._config.order_inquiry_path,
                tr_id=self._config.order_inquiry_tr_id,
                build_params=build_params,
                deadline_expired=deadline_expired,
            )
            for row in _order_rows_or_refuse(outcome, queried=symbol):
                parsed = KisOrderRow.from_wire(row)
                _refuse_instrument_conflict(parsed, queried=symbol)
                orders.append(parsed)
        return tuple(orders)

    @staticmethod
    def _order_from_row(row: KisOrderRow) -> WitnessOrder:
        filled_qty = row.tot_ccld_qty
        remaining_qty = row.rmn_qty

        if row.cancelled:
            state = WitnessOrderState.CANCELLED
        elif filled_qty is not None and filled_qty > 0:
            state = (
                WitnessOrderState.FILLED
                if remaining_qty is not None and remaining_qty <= 0
                else WitnessOrderState.PARTIAL
            )
        elif filled_qty is not None and filled_qty == 0:
            state = WitnessOrderState.ACKED
        else:
            state = WitnessOrderState.UNKNOWN

        return WitnessOrder(
            attempt_id=None,
            broker_execution_id=row.odno,
            quantity=filled_qty,
            remaining=remaining_qty,
            state=state,
            order_date=row.ord_dt,
        )
