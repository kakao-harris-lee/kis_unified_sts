#!/usr/bin/env python3
"""Is the KIS 모의투자 stock account flat in one symbol? — GET only, nothing is sent.

``restart_stock_tenant.sh`` asks this before it archives a tenant's durable leaf:
an archived leaf with an open position would leave a position nobody's evidence
chain owns any more. Exit codes are the answer (there is no parsing of stdout):

    0  the account holds none of that symbol        (flat — safe to archive)
    1  the balance could not be read                (unknown — treated as NOT flat)
    2  refused before any broker call               (fail closed, see below)
    3  the account holds some of that symbol        (NOT flat — keep the leaf)

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
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

#: The probes' own floor between calls. 2.5 s is what the 11-20 scratchpad runs
#: used and it sits under the 2.0 rps the shared pacer allows the app key.
DEFAULT_PACE_S = 2.5


class OpsRefusal(RuntimeError):
    """A precondition failed — nothing was sent, and nothing may be."""


class BalanceUnreadable(RuntimeError):
    """The broker answered, but not with a balance this tool may act on."""


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
            '`KIS_STOCK_ACCOUNT_NO=… python -c "import os;from '
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
    try:
        held = holdings(client, creds)
    except BalanceUnreadable as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_UNREADABLE
    finally:
        client.close()
    print("holdings", {code: qty for code, qty in held.items() if qty})
    return EXIT_HELD if held.get(args.symbol, 0) else EXIT_FLAT


if __name__ == "__main__":  # pragma: no cover - CLI
    sys.exit(main())
