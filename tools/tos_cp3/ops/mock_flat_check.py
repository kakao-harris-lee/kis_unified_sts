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
from collections.abc import Sequence
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

#: ONE PAGE, and that bound is load-bearing: a holding that fell past page 1 would
#: read as "no row for this symbol", which this tool reports as flat. It is sound
#: here because ``INQR_DVSN: "02"`` returns up to 50 rows and this account holds one
#: share of each stock tenant's symbol — three rows today, and `STOCK_SYMBOLS` is
#: what would have to reach dozens for it to matter. If it ever does, follow the
#: continuation (``ctx_area_fk100`` / ``ctx_area_nk100`` echoed back with
#: ``tr_cont``) instead of widening this dict; do not leave the single page in
#: place with more symbols than it can carry.
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
#: 75 rows of one symbol's single day against a tenant that sends a handful.
#: Reaching it is NOT "no open order": the broker was still offering more, so the
#: answer is unknown and this tool says so.
ORDER_MAX_PAGES = 5

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


def holdings(client: MockTradingClient, creds: ProbeCredentials) -> dict[str, int]:
    """``{symbol: quantity}`` for this account, quantities summed per symbol."""
    params: dict[str, Any] = {
        "CANO": creds.cano,
        "ACNT_PRDT_CD": creds.acnt_prdt_cd,
        **BALANCE_PARAMS,
    }
    status, parsed, _ms, _tr = client.trading_call(
        "GET", BALANCE_PATH, BALANCE_TR_ID, params=params
    )
    if parsed.get("rt_cd") != "0":
        raise BalanceUnreadable(
            f"balance not readable: http {status} rt_cd {parsed.get('rt_cd')} "
            f"{parsed.get('msg1')}"
        )
    held: dict[str, int] = {}
    for row in parsed.get("output1") or []:
        code = str(row.get("pdno") or "")
        if code:
            held[code] = held.get(code, 0) + int(row.get("hldg_qty") or 0)
    return held


def row_is_open(row: dict[str, Any], symbol: str) -> bool:
    """Is this 주문체결 row still working on the book, for ``symbol``?

    ``rmn_qty > 0`` AND not flagged cancelled — both halves, as
    ``probes_stock_cancel._row_is_live`` has them: #948's open question is
    whether a cancel shows as the flag or as another row, so a reader that
    trusted one of them alone would be assuming the answer.

    A row whose ``pdno`` is blank counts as this symbol's: the query asked for
    one symbol, and an unattributable working quantity is not evidence of flat.
    """
    code = str(row.get("pdno") or "").strip()
    if code and code != symbol:
        return False
    try:
        remaining = int(str(row.get("rmn_qty") or "0").strip() or "0")
    except ValueError:
        # A quantity we cannot read is not a quantity we may call zero.
        return True
    cancelled = str(row.get("cncl_yn") or "").strip().upper() == "Y"
    return remaining > 0 and not cancelled


def open_orders(
    client: MockTradingClient,
    creds: ProbeCredentials,
    symbol: str,
    *,
    max_pages: int = ORDER_MAX_PAGES,
) -> list[dict[str, Any]]:
    """Today's rows for ``symbol`` that still have quantity working, walked to the end.

    The walk — not one page — because one page cannot tell "no open order" from
    "the open order is on page 2", and this is the read that decides whether a
    leaf may be archived. Anything short of the broker's own end-of-set raises
    :class:`BalanceUnreadable`, which the caller reports as unknown, never as
    flat.
    """
    day = datetime.now(KST).strftime("%Y%m%d")
    fk = nk = ""
    live: list[dict[str, Any]] = []
    for page in range(max_pages):
        params: dict[str, Any] = {
            "CANO": creds.cano,
            "ACNT_PRDT_CD": creds.acnt_prdt_cd,
            "INQR_STRT_DT": day,
            "INQR_END_DT": day,
            "PDNO": symbol,
            **ORDER_PARAMS,
            "CTX_AREA_FK100": fk,
            "CTX_AREA_NK100": nk,
        }
        status, parsed, _ms, _tr = client.trading_call(
            "GET", ORDER_PATH, ORDER_TR_ID, params=params
        )
        if parsed.get("rt_cd") != "0":
            raise BalanceUnreadable(
                f"open orders not readable: page {page} http {status} rt_cd "
                f"{parsed.get('rt_cd')} {parsed.get('msg1')}"
            )
        rows = parsed.get("output1")
        live.extend(
            row
            for row in (rows if isinstance(rows, list) else [])
            if isinstance(row, dict) and row_is_open(row, symbol)
        )
        next_fk = str(parsed.get("ctx_area_fk100") or "").strip()
        next_nk = str(parsed.get("ctx_area_nk100") or "").strip()
        if not next_fk and not next_nk:
            # The broker ended the set: every row of today was walked.
            return live
        if (next_fk, next_nk) == (fk, nk):
            # The same cursor again while still offering more — the next request
            # would repeat this page. The runtime refuses this too
            # (``witness_kis._walk_continuation``) rather than return a partial
            # list, and a partial list here reads as "no open order".
            raise BalanceUnreadable(
                f"open orders not readable: continuation keys did not advance on "
                f"page {page} — refusing a partial read"
            )
        fk, nk = next_fk, next_nk
    raise BalanceUnreadable(
        f"open orders not readable: hit our {max_pages}-page cap while the broker "
        "was still offering more — this is OUR cap, not end-of-set"
    )


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
