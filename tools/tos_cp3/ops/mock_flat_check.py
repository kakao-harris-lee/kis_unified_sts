#!/usr/bin/env python3
"""Is the KIS 모의투자 stock account flat in one symbol? — GET only, nothing is sent.

``restart_stock_tenant.sh`` asks this before it archives a tenant's durable leaf:
an archived leaf with an open position would leave a position nobody's evidence
chain owns any more. Exit codes are the answer (there is no parsing of stdout):

    0  no holding AND no order still working        (flat — safe to archive)
    1  a read could not be completed                (unknown — treated as NOT flat)
    2  refused before any broker call               (fail closed, see below)
    3  the account holds some of that symbol, or an order for it is still
       working on the book                          (NOT flat — keep the leaf)

Two reads, because the holding alone does not answer the question. A runtime
limit entry that was ACKed and has not filled holds no quantity yet, and the
runtime cannot cancel it (#948): a check that read only the balance would say
flat, the leaf would be archived, and the order would fill afterwards into a
position no evidence chain owns — exactly what the check exists to prevent. So
the 주식일별주문체결조회 (``VTTC0081R``) rows for today are read too, and any row
with quantity still working is "not flat".

Both reads are WALKED to the broker's own end-of-set (:func:`walk_pages`) and
every unresolved answer — a page cap, a cursor that does not advance, a missing
``tr_cont`` header, an unreadable quantity — comes out as 1 or 3, never 0. The
asymmetry is the whole design: "not flat" costs a retry, "flat" archives a leaf
and cannot be taken back.

Safety properties, in the order they are checked — every one of them before the
first request leaves the host:

  * ``assert_no_live_futures_config()`` — the interlock every order-path probe
    runs first (``tools/broker_probes/common.py``).
  * the expected account fingerprint is REQUIRED (``--expect-account-fingerprint``
    or ``CP3_EXPECT_ACCOUNT_FP``, the ``*_EXPECT_ACCOUNT_FP`` spelling the probe
    runners use). Missing is a refusal, never an inferred account: the 2026-09-23
    INVALID_CHECK_ACNO outage was a key paired with the wrong account, and four
    app-key pairs live on this host.
  * ``resolve_credentials("stock", is_real=False)`` — mock only, and the only
    call site. Nothing here can be pointed at the real account: ``is_real=False``
    picks the mock base URL, ``MockTradingClient.trading_call`` re-asserts the
    mock host and a mock TR id, and a credential file that turned out to be the
    real one fails the fingerprint comparison above.
  * the credential file is read through the one bounded loader
    (``shared.config.dotenv_guard.read_explicit_dotenv``) — no ancestor search,
    so it cannot walk out of a worktree into the primary checkout's real
    ``.env`` (#698), and a hermetic test process reads nothing.
  * no secret is printed. Holdings are symbol codes and quantities; the account
    number appears nowhere, not even masked.

``mock_flatten.py`` imports the guards and the balance read from here, so the two
tools cannot drift into asking the broker two different questions.

Firewall: legacy side (``tools/``). No ``tos`` / ``tos_runtime`` import.
"""

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

#: ``CP3_EXPECT_ACCOUNT_FP`` follows the probe runners' ``*_EXPECT_ACCOUNT_FP``
#: (``tools/broker_probes/runners/run_p_sc.sh``), not a new spelling.
EXPECT_FP_ENV = "CP3_EXPECT_ACCOUNT_FP"
#: ``TOS_ENV_MOCK`` is ``setup_stock_mock_once.sh``'s name for the same file.
ENV_FILE_ENV = "TOS_ENV_MOCK"

#: The only keys read out of that file, and the only ones put in the environment.
CREDENTIAL_KEYS = ("KIS_STOCK_APP_KEY", "KIS_STOCK_APP_SECRET", "KIS_STOCK_ACCOUNT_NO")

EXIT_FLAT = 0
EXIT_UNREADABLE = 1
EXIT_REFUSED = 2
EXIT_HELD = 3

KST = ZoneInfo("Asia/Seoul")

BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
#: 주식잔고조회 (모의). ``trading_call`` refuses a TR that is not a mock one.
BALANCE_TR_ID = "VTTC8434R"

#: The per-page parameters; the continuation keys are filled in per page by
#: :func:`walk_pages`. This read is WALKED, not one page: on 2026-08-05 the mock
#: account answered 25 holdings over two pages (P-BAL), and a single page that
#: missed the symbol's row would read here as "not held" — that is, as flat.
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
#: 주식일별주문체결조회 (모의). ``VTTC8001R`` is NOT the one — it answers empty on the
#: mock account; the runtime polls ``VTTC0081R`` (``config/tos_runtime/
#: cp3-setup-d-stock-*/fill_observer.yaml::order_inquiry_tr_id``) and so does
#: ``probes_order.stock_daily_ccld_verbose``. A mock (``V``-prefixed) read TR, so
#: ``trading_call``'s TR gate passes it with no allowlist change.
ORDER_TR_ID = "VTTC0081R"

#: The runtime's own parameters for this TR, verbatim
#: (``tos_runtime.recon.witness_kis._read_order_rows``), minus the account, the
#: date and the continuation keys, which are per call.
#:
#: ``CCLD_DVSN="00"`` (전체) rather than 미체결-only: whether the mock honours a
#: narrowing filter is not something this tool has measured, and a filter that
#: silently returned nothing would read as "no open order" — the one error this
#: check may not make. 전체 plus the local ``rmn_qty``/``cncl_yn`` test
#: (:func:`row_is_open`) can only over-report, never under-report.
#: ``INQR_DVSN="00"`` is 역순 (newest first), so a seconds-old order is on page 1.
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

#: Page cap for the continuation walk, the same 5 the cancel probe's flat-start
#: check uses (``config/broker_probes/stock_cancel_probe.yaml::flat_check.
#: balance_max_pages``). 모의 serves 15 rows per call (P-5b 실측), so five pages is
#: 75 rows of one symbol's single day against a tenant that sends a handful, and
#: 모의 answered 25 holdings in two pages on the balance side (P-BAL 2026-08-05).
#: Reaching the cap is NOT "nothing there": the broker was still offering more,
#: so the answer is unknown and this tool says so.
MAX_PAGES = 5

#: The REQUEST ``tr_cont`` for every page after the first, and the RESPONSE
#: values that mean "more follows" — the runtime's own
#: (``tos_runtime.recon.witness_kis._TR_CONT_REQUEST_NEXT`` / ``_MORE_CODES``).
TR_CONT_REQUEST_NEXT = "N"
TR_CONT_MORE_CODES = ("M", "F")

#: The probes' own floor between calls. 2.5 s is what the 11-20 scratchpad runs
#: used and it sits under the 2.0 rps the shared pacer allows the app key.
DEFAULT_PACE_S = 2.5


class OpsRefusal(RuntimeError):
    """A precondition failed — nothing was sent, and nothing may be."""


class BalanceUnreadable(RuntimeError):
    """The broker answered, but not with a reading this tool may act on.

    Raised by both reads (balance and open orders). The name is the one
    ``mock_flatten.py`` and the tests already import.
    """


def broker_transport_errors() -> tuple[type[BaseException], ...]:
    """What a broker call raises instead of answering.

    Caught — and printed as ``type(exc).__name__`` and nothing else — because
    ``requests`` puts the request URL in the exception it raises, and this
    client's URLs carry ``CANO``: an uncaught one would print the account number
    in a traceback. ``ProbeError`` is here for the same reason, not a different
    one: it is raised with whatever the call was doing at the time.
    """
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
            # PYTHONPATH=<repo root>, because `python -c` puts the CWD on
            # sys.path and the venv interpreter is run from anywhere.
            '`KIS_STOCK_ACCOUNT_NO=… PYTHONPATH=<저장소 루트> python -c "import os;from '
            "tools.broker_probes.common import account_fingerprint;"
            "print(account_fingerprint(os.environ['KIS_STOCK_ACCOUNT_NO']))\"` — "
            "this tool will not infer which account it may read."
        )
    return expected.lower()


def load_env_file(path: str | None) -> Path:
    """Put this file's mock credentials in the environment, overriding what is set.

    Read through ``shared.config.dotenv_guard.read_explicit_dotenv``, the repo's
    only sanctioned reader for an operator-named file (#698, enforced by
    ``tests/unit/config/test_dotenv_call_gate.py``): no ancestor search, so it
    cannot walk out of a worktree into the primary checkout's real ``.env``, and
    a hermetic test process reads nothing at all — which lands here as "the file
    does not carry …", never as credentials in a test.

    Override is the point: the named file decides which account this run touches,
    and the fingerprint gate in :func:`build_client` then checks that it is the
    authorised one.
    """
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
    """Every guard, then a mock-only client. Raises :class:`OpsRefusal` otherwise.

    Imported lazily so :func:`load_env_file` has already run when the credential
    resolution reads the environment.
    """
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
        # Same semantics as probes_real_order.assert_account_fingerprint, without
        # importing the real-money order probe into a mock-only tool.
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
    """Every ``output1`` row of every page, ending where the BROKER says it ends.

    End-of-set is the ``tr_cont`` RESPONSE header, which is the runtime's rule
    (``witness_kis._walk_continuation``) and not a matter of taste here: the
    mock echoes non-empty ``ctx_area_*`` cursors on its LAST page too (2026-08-05
    P-BAL saw ``tr_cont='D'`` with the keys still set), so a walk that read the
    cursors alone would either loop or call a complete read a partial one.

    A missing header is refused rather than read as end-of-set — the opposite of
    the runtime's tolerance, deliberately: a wrong "the set ended here" in this
    tool means "flat", and an archived leaf cannot be un-archived. Everything
    unresolved raises :class:`BalanceUnreadable`; nothing here returns a short
    list quietly.
    """
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
        if code:
            held[code] = held.get(code, 0) + int(row.get("hldg_qty") or 0)
    return held


def int_or_none(value: Any) -> int | None:
    """The row's quantity as an int, or ``None`` when the row does not say.

    Missing, ``None``, blank and unparseable all come back ``None`` — they are
    the same thing here (the broker did not tell us) and none of them is zero.
    """
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def row_is_open(row: dict[str, Any], symbol: str) -> bool:
    """Is this 주문체결 row still working on the book, for ``symbol``?

    Closed has to be PROVEN; open is what everything else means. The quantity
    rule is the runtime's (``tos_runtime.posttrade.fill_observer._fill_state``,
    which answers UNKNOWN the moment a quantity is None):

    * ``rmn_qty`` when it reads, else ``ord_qty - tot_ccld_qty`` when both do;
    * no readable remainder at all — blank, missing, ``None``, not a number —
      is OPEN. A blank ``rmn_qty`` on a working order was the round-1 HIGH:
      read as 0 it made the row "closed", the check said flat, and the leaf
      was archived with an order still live on the book.
    * quantities that contradict each other (negative, or
      ``filled + remaining != ordered``) are OPEN for the same reason.

    ``cncl_yn='Y'`` closes the row only when a remainder was readable — a
    cancelled row we cannot quantify is still open as far as this gate is
    concerned. (Whether a cancel shows as this flag or as its own row is #948's
    open question; the flag is believed only alongside a number.)

    A row whose ``pdno`` is blank counts as this symbol's: the query asked for
    one symbol, and an unattributable working quantity is not evidence of flat.
    """
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
    if str(row.get("cncl_yn") or "").strip().upper() == "Y":
        return False
    return remaining > 0


def open_orders(
    client: MockTradingClient, creds: ProbeCredentials, symbol: str
) -> list[dict[str, Any]]:
    """Today's rows for ``symbol`` that still have quantity working, walked to the end.

    The walk — not one page — because one page cannot tell "no open order" from
    "the open order is on page 2", and this is the read that decides whether a
    leaf may be archived. Anything short of the broker's own end-of-set raises
    :class:`BalanceUnreadable`, which the caller reports as unknown, never as
    flat.
    """
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
        # Only when the balance is clear: an order still working is the other
        # way this symbol is not flat (#948 — the runtime cannot cancel it).
        working = open_orders(client, creds, args.symbol)
    except BalanceUnreadable as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_UNREADABLE
    except transport_errors as exc:
        # The message would carry the request URL, and the URL carries CANO.
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
