#!/usr/bin/env python3
"""MOCK account only: market-SELL the whole holding of one symbol, then wait for flat.

Why it exists: a tenant whose leaf has to be archived must be flat first
(``mock_flat_check.py``), and the runtime cannot close that position itself —
the standing approval covers the 1-share entry BUY only (#960), and a cancel of
an already-sent mock order does not exist in the runtime (#948). So the position
is closed here, by hand, on the 모의투자 account. Operator standing approval
2026-11-20: mock tenants may be repaired intraday without asking.

This is the one tool in ``tools/tos_cp3/ops/`` that SENDS. Every guard is
``mock_flat_check.py``'s — imported, not re-implemented — and they all run before
the first request leaves the host:

    expected account fingerprint REQUIRED · assert_no_live_futures_config() ·
    resolve_credentials("stock", is_real=False) · mock host + mock TR id asserted
    inside MockTradingClient · nothing printed but symbol codes, quantities,
    rt_cd and the order number.

A credential file that turned out to be the REAL one cannot be reached: the real
account's fingerprint is not the expected one, so the refusal happens before any
client is built.

Exit codes:

    0  nothing was held, or the holding reached 0      (flat)
    1  the broker's answer is not one to act on: the sell was rejected, OR a
       balance read failed, OR a call raised instead of answering — which, after
       the sell went out, means the position is unknown rather than unchanged.
       Read the balance in the 모의투자 HTS before running this again.
    2  refused before any broker call                  (fail closed)
    3  sent and acknowledged, but still holding when the poll bound ran out

Firewall: legacy side (``tools/``). No ``tos`` / ``tos_runtime`` import.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Sequence

from tools.tos_cp3.ops.mock_flat_check import (
    BalanceUnreadable,
    OpsRefusal,
    broker_transport_errors,
    build_client,
    build_parser,
    holdings,
    load_env_file,
    resolve_expected_fingerprint,
)

# The same code space as mock_flat_check.py, so a wrapper can treat the two alike:
# 0 flat · 1 the broker's answer is not one to act on · 2 refused · 3 still held.
EXIT_FLAT = 0
EXIT_REJECTED = 1
EXIT_REFUSED = 2
EXIT_STILL_HELD = 3

#: 10 × 3 s. A mock market order on a liquid large cap fills in seconds during the
#: session; outside it, nothing fills and the tool says so rather than hanging.
DEFAULT_POLL_TRIES = 10
DEFAULT_POLL_INTERVAL_S = 3.0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser(
        "tools/tos_cp3/ops/mock_flatten.py",
        "MOCK only: market-SELL the whole holding of one symbol, then poll to flat.",
    )
    parser.add_argument(
        "--poll-tries",
        type=int,
        default=DEFAULT_POLL_TRIES,
        help=f"balance reads after the sell (default {DEFAULT_POLL_TRIES})",
    )
    parser.add_argument(
        "--poll-interval-s",
        type=float,
        default=DEFAULT_POLL_INTERVAL_S,
        help=f"seconds between those reads (default {DEFAULT_POLL_INTERVAL_S})",
    )
    args = parser.parse_args(argv)
    try:
        expected = resolve_expected_fingerprint(args.expect_account_fingerprint)
        load_env_file(args.env_file)
        client, creds = build_client(
            expected_fingerprint=expected,
            probe_id="cp3-ops-flatten",
            title="stock MOCK flatten",
            token_cache_dir=args.token_cache_dir,
            pace_s=args.pace_s,
        )
    except OpsRefusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    transport_errors = broker_transport_errors()
    try:
        qty = holdings(client, creds).get(args.symbol, 0)
        print(f"{args.symbol} holding {qty}")
        if qty <= 0:
            return EXIT_FLAT
        body = client.stock_order_body(args.symbol, qty, order_type="market")
        placed, status, parsed, _text, _ms = client.submit_stock_verbose(
            body, side="SELL"
        )
        print(
            "sell http",
            status,
            "rt_cd",
            parsed.get("rt_cd"),
            parsed.get("msg1"),
            "odno",
            placed.odno if placed else None,
        )
        if placed is None:
            return EXIT_REJECTED
        left = qty
        for _ in range(args.poll_tries):
            time.sleep(args.poll_interval_s)
            left = holdings(client, creds).get(args.symbol, 0)
            if left == 0:
                print(f"{args.symbol} flat")
                return EXIT_FLAT
        print(f"{args.symbol} still holding {left}")
        return EXIT_STILL_HELD
    except BalanceUnreadable as exc:
        # Before the sell this is "unknown, so do not send"; after it, "sent but
        # unconfirmed". Both are the same instruction to the operator: read the
        # balance in the 모의투자 HTS before running anything else at this symbol.
        print(str(exc), file=sys.stderr)
        return EXIT_REJECTED
    except transport_errors as exc:
        # Same instruction, and the type name only: the exception's own message
        # carries the request URL, and the URL carries CANO. Whether the sell
        # left the host is unknown — the 모의투자 HTS is what answers that.
        print(f"broker call failed: {type(exc).__name__}", file=sys.stderr)
        return EXIT_REJECTED
    finally:
        client.close()


if __name__ == "__main__":  # pragma: no cover - CLI
    sys.exit(main())
