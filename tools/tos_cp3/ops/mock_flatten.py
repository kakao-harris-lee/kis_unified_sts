#!/usr/bin/env python3
"""MOCK account only: market-SELL the whole holding of one symbol, then wait for flat."""

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

EXIT_FLAT = 0
EXIT_REJECTED = 1
EXIT_REFUSED = 2
EXIT_STILL_HELD = 3

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
            transport_yaml=args.transport_yaml,
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
        print(str(exc), file=sys.stderr)
        return EXIT_REJECTED
    except transport_errors as exc:
        print(f"broker call failed: {type(exc).__name__}", file=sys.stderr)
        return EXIT_REJECTED
    finally:
        client.close()


if __name__ == "__main__":  # pragma: no cover - CLI
    sys.exit(main())
