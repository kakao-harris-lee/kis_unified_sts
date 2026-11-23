#!/usr/bin/env python3
"""Is the KIS 모의투자 stock account flat in one symbol? — GET only, nothing is sent."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

if TYPE_CHECKING:  # pragma: no cover - typing only
    from tools.broker_probes.common import ProbeCredentials
    from tools.broker_probes.probes_order import MockTradingClient

EXPECT_FP_ENV = "CP3_EXPECT_ACCOUNT_FP"
ENV_FILE_ENV = "TOS_ENV_MOCK"

CREDENTIAL_KEYS = ("KIS_STOCK_APP_KEY", "KIS_STOCK_APP_SECRET", "KIS_STOCK_ACCOUNT_NO")

EXIT_FLAT = 0
EXIT_UNREADABLE = 1
EXIT_REFUSED = 2
EXIT_HELD = 3

KST = ZoneInfo("Asia/Seoul")

BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
BALANCE_TR_ID = "VTTC8434R"

BALANCE_PARAMS: dict[str, str] = {
    "AFHR_FLPR_YN": "N",
    "OFL_YN": "",
    "INQR_DVSN": "02",
    "UNPR_DVSN": "01",
    "FUND_STTL_ICLD_YN": "N",
    "FNCG_AMT_AUTO_RDPT_YN": "N",
    "PRCS_DVSN": "01",
    "CTX_AREA_FK100": "",
    "CTX_AREA_NK100": "",
}

ORDER_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
ORDER_TR_ID = "VTTC0081R"

ORDER_PARAMS: dict[str, str] = {
    "SLL_BUY_DVSN_CD": "00",
    "CCLD_DVSN": "00",
    "INQR_DVSN": "00",
    "INQR_DVSN_3": "00",
    "ORD_GNO_BRNO": "",
    "ODNO": "",
    "INQR_DVSN_1": "",
    "EXCG_ID_DVSN_CD": "KRX",
}

MAX_PAGES = 5

CANCEL_CONFIRMED_QTY_KEYS = ("cnc_cfrm_qty", "cncl_cfrm_qty")

TR_CONT_REQUEST_NEXT = "N"
TR_CONT_MORE_CODES = ("M", "F")

DEFAULT_PACE_S = 2.5


class OpsRefusal(RuntimeError):
    """A precondition failed — nothing was sent, and nothing may be."""


class BalanceUnreadable(RuntimeError):
    """The broker answered, but not with a reading this tool may act on."""


def broker_transport_errors() -> tuple[type[BaseException], ...]:
    """What a broker call raises instead of answering."""
    import requests

    from tools.broker_probes.common import ProbeError

    return (requests.RequestException, ProbeError)


def six_digit_symbol(value: str) -> str:
    """argparse type: a 6-digit KRX symbol, so a typo cannot read another stock."""
    text = value.strip()
    if len(text) != 6 or not text.isdigit():
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a 6-digit KRX symbol (e.g. 005930)"
        )
    return text


def build_parser(prog: str, description: str) -> argparse.ArgumentParser:
    """The arguments both tools take. ``mock_flatten.py`` adds its own."""
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument("symbol", type=six_digit_symbol, help="6-digit KRX symbol")
    parser.add_argument(
        "--expect-account-fingerprint",
        default=None,
        metavar="FP",
        help=(
            "the mock stock account's account_fingerprint (12 hex). Required; "
            f"${EXPECT_FP_ENV} is read when the flag is absent."
        ),
    )
    parser.add_argument(
        "--env-file",
        default=None,
        metavar="PATH",
        help=f"the .env.mock carrying the mock keys (default ${ENV_FILE_ENV})",
    )
    parser.add_argument(
        "--token-cache-dir",
        default=None,
        metavar="PATH",
        help=(
            "probe-private token cache (default tools/broker_probes/results/"
            ".token_cache). Never the runtime's cache — invalidating that one "
            "would yank the token out from under a running session."
        ),
    )
    parser.add_argument(
        "--pace-s",
        type=float,
        default=DEFAULT_PACE_S,
        help=f"floor between this tool's own calls (default {DEFAULT_PACE_S})",
    )
    return parser


def resolve_expected_fingerprint(flag: str | None) -> str:
    """The account this tool is allowed to touch. Missing is a refusal."""
    expected = (flag if flag is not None else os.environ.get(EXPECT_FP_ENV, "")).strip()
    if not expected:
        raise OpsRefusal(
            "--expect-account-fingerprint (or "
            f"${EXPECT_FP_ENV}) is required. Read it off the mock account: "
            '`KIS_STOCK_ACCOUNT_NO=… PYTHONPATH=<저장소 루트> python -c "import os;from '
            "tools.broker_probes.common import account_fingerprint;"
            "print(account_fingerprint(os.environ['KIS_STOCK_ACCOUNT_NO']))\"` — "
            "this tool will not infer which account it may read."
        )
    return expected.lower()


def load_env_file(path: str | None) -> Path:
    """Put this file's mock credentials in the environment, overriding what is set."""
    from shared.config.dotenv_guard import read_explicit_dotenv

    chosen = Path(path or os.environ.get(ENV_FILE_ENV) or ".env.mock").expanduser()
    if not chosen.is_file():
        raise OpsRefusal(
            f"credential file not found: {chosen} — pass --env-file or export "
            f"${ENV_FILE_ENV} (runbook §7.2-f)"
        )
    chosen = chosen.resolve()
    values = read_explicit_dotenv(chosen, keys=CREDENTIAL_KEYS)
    missing = [key for key in CREDENTIAL_KEYS if not values.get(key)]
    if missing:
        raise OpsRefusal(f"{chosen} does not carry {', '.join(missing)}")
    os.environ.update(values)
    return chosen


def build_client(
    *,
    expected_fingerprint: str,
    probe_id: str,
    title: str,
    token_cache_dir: str | None = None,
    pace_s: float = DEFAULT_PACE_S,
) -> tuple[MockTradingClient, ProbeCredentials]:
    """Every guard, then a mock-only client. Raises :class:`OpsRefusal` otherwise."""
    from shared.kis.auth import KISAuthManager
    from tools.broker_probes.common import (
        ProbeError,
        ProbeRun,
        account_fingerprint,
        assert_no_live_futures_config,
        build_auth_config,
        probe_token_cache_dir,
        require_account,
        resolve_credentials,
    )
    from tools.broker_probes.probes_order import MockTradingClient as _Client

    assert_no_live_futures_config()
    try:
        creds = resolve_credentials("stock", is_real=False)
        require_account(creds)
    except ProbeError as exc:
        raise OpsRefusal(str(exc)) from exc
    actual = account_fingerprint(creds.account_no)
    if actual != expected_fingerprint:
        raise OpsRefusal(
            f"wired account fingerprint {actual!r} != expected "
            f"{expected_fingerprint!r} — the environment points at a different "
            "account than the one authorised. Fix the credential wiring; do not "
            "re-run with the observed value."
        )
    run = ProbeRun(probe_id=probe_id, title=title, mode="live", environment="mock")
    auth = KISAuthManager(
        build_auth_config(creds, probe_token_cache_dir(token_cache_dir)),
        use_singleton=False,
    )
    return _Client(creds, auth, run, pace_s=pace_s), creds


def header_value(headers: Mapping[str, str], name: str) -> str:
    """One response header, case-insensitively — the wire spells it, not us."""
    for key, value in headers.items():
        if key.lower() == name.lower():
            return str(value or "").strip()
    return ""


def walk_pages(
    client: MockTradingClient,
    *,
    path: str,
    tr_id: str,
    build_params: Callable[[str, str], dict[str, Any]],
    what: str,
    max_pages: int = MAX_PAGES,
) -> list[dict[str, Any]]:
    """Every ``output1`` row of every page, ending where the BROKER says it ends."""
    rows: list[dict[str, Any]] = []
    fk = nk = ""
    for page in range(max_pages):
        status, parsed, _ms, _text, headers = client.trading_get_with_headers(
            path,
            tr_id,
            params=build_params(fk, nk),
            tr_cont="" if page == 0 else TR_CONT_REQUEST_NEXT,
        )
        if status != 200 or parsed.get("rt_cd") != "0":
            raise BalanceUnreadable(
                f"{what} not readable: page {page} http {status} rt_cd "
                f"{parsed.get('rt_cd')} {parsed.get('msg1')}"
            )
        page_rows = parsed.get("output1")
        rows.extend(row for row in (page_rows or []) if isinstance(row, dict))
        tr_cont = header_value(headers, "tr_cont")
        if not tr_cont:
            raise BalanceUnreadable(
                f"{what} not readable: page {page} carried no tr_cont header, so "
                "'the broker ended the set' cannot be told from 'there is more'"
            )
        if tr_cont not in TR_CONT_MORE_CODES:
            return rows
        next_fk = str(parsed.get("ctx_area_fk100") or "").strip()
        next_nk = str(parsed.get("ctx_area_nk100") or "").strip()
        if not next_fk and not next_nk:
            raise BalanceUnreadable(
                f"{what} not readable: page {page} said tr_cont={tr_cont!r} (more "
                "follows) but returned no continuation key"
            )
        if (next_fk, next_nk) == (fk, nk):
            raise BalanceUnreadable(
                f"{what} not readable: continuation keys did not advance on page "
                f"{page} while tr_cont={tr_cont!r} still signalled more"
            )
        fk, nk = next_fk, next_nk
    raise BalanceUnreadable(
        f"{what} not readable: hit our {max_pages}-page cap while the broker was "
        "still offering more — this is OUR cap, not end-of-set"
    )


def holdings(client: MockTradingClient, creds: ProbeCredentials) -> dict[str, int]:
    """``{symbol: quantity}`` for this account, quantities summed per symbol."""

    def build_params(fk: str, nk: str) -> dict[str, Any]:
        return {
            "CANO": creds.cano,
            "ACNT_PRDT_CD": creds.acnt_prdt_cd,
            **BALANCE_PARAMS,
            "CTX_AREA_FK100": fk,
            "CTX_AREA_NK100": nk,
        }

    rows = walk_pages(
        client,
        path=BALANCE_PATH,
        tr_id=BALANCE_TR_ID,
        build_params=build_params,
        what="balance",
    )
    held: dict[str, int] = {}
    for row in rows:
        code = str(row.get("pdno") or "")
        if not code:
            continue
        qty = int_or_none(row.get("hldg_qty"))
        if qty is None:
            # SAFETY: a blank 보유수량 summed as 0 reports a held account flat.
            raise BalanceUnreadable(
                f"balance not readable: the {code} row carried hldg_qty="
                f"{row.get('hldg_qty')!r}, which is not a quantity"
            )
        held[code] = held.get(code, 0) + qty
    return held


def int_or_none(value: Any) -> int | None:
    """The row's quantity as an int, or ``None`` when the row does not say."""
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def cancel_confirmed_qty(row: dict[str, Any]) -> int | None:
    """취소확인수량 — what the broker says the cancel withdrew (v1_국내주식-005)."""
    for key in CANCEL_CONFIRMED_QTY_KEYS:
        if key in row:
            return int_or_none(row.get(key))
    return None


def row_is_open(row: dict[str, Any], symbol: str) -> bool:
    """Is this 주문체결 row still working on the book, for ``symbol``?"""
    code = str(row.get("pdno") or "").strip()
    if code and code != symbol:
        return False
    ordered = int_or_none(row.get("ord_qty"))
    filled = int_or_none(row.get("tot_ccld_qty"))
    remaining = int_or_none(row.get("rmn_qty"))
    if remaining is None and ordered is not None and filled is not None:
        remaining = ordered - filled
    if remaining is None or remaining < 0:
        return True
    if ordered is not None and filled is not None and filled + remaining != ordered:
        return True
    if remaining == 0:
        return False
    if str(row.get("cncl_yn") or "").strip().upper() == "Y":
        # SAFETY: cncl_yn=Y is the cancel ACCEPTED, not the remainder withdrawn — a
        # row with quantity left can still fill, so only 취소확인수량 closes it.
        confirmed = cancel_confirmed_qty(row)
        return confirmed is None or confirmed < remaining
    return True


def open_orders(
    client: MockTradingClient, creds: ProbeCredentials, symbol: str
) -> list[dict[str, Any]]:
    """Today's rows for ``symbol`` that still have quantity working, walked to the end."""
    day = datetime.now(KST).strftime("%Y%m%d")

    def build_params(fk: str, nk: str) -> dict[str, Any]:
        return {
            "CANO": creds.cano,
            "ACNT_PRDT_CD": creds.acnt_prdt_cd,
            "INQR_STRT_DT": day,
            "INQR_END_DT": day,
            "PDNO": symbol,
            **ORDER_PARAMS,
            "CTX_AREA_FK100": fk,
            "CTX_AREA_NK100": nk,
        }

    rows = walk_pages(
        client,
        path=ORDER_PATH,
        tr_id=ORDER_TR_ID,
        build_params=build_params,
        what="open orders",
    )
    return [row for row in rows if row_is_open(row, symbol)]


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser(
        "tools/tos_cp3/ops/mock_flat_check.py",
        "GET-only: does the stock MOCK account hold this symbol?",
    ).parse_args(argv)
    try:
        expected = resolve_expected_fingerprint(args.expect_account_fingerprint)
        load_env_file(args.env_file)
        client, creds = build_client(
            expected_fingerprint=expected,
            probe_id="cp3-ops-flat-check",
            title="stock MOCK flat check",
            token_cache_dir=args.token_cache_dir,
            pace_s=args.pace_s,
        )
    except OpsRefusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    transport_errors = broker_transport_errors()
    try:
        held = holdings(client, creds)
        print("holdings", {code: qty for code, qty in held.items() if qty})
        if held.get(args.symbol, 0):
            return EXIT_HELD
        working = open_orders(client, creds, args.symbol)
    except BalanceUnreadable as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_UNREADABLE
    except transport_errors as exc:
        print(f"broker call failed: {type(exc).__name__}", file=sys.stderr)
        return EXIT_UNREADABLE
    finally:
        client.close()
    if working:
        print(
            f"{args.symbol} open orders",
            [
                {"odno": str(row.get("odno") or ""), "rmn_qty": row.get("rmn_qty")}
                for row in working
            ],
        )
        return EXIT_HELD
    print(f"{args.symbol} flat (no holding, no order working)")
    return EXIT_FLAT


if __name__ == "__main__":  # pragma: no cover - CLI
    sys.exit(main())
