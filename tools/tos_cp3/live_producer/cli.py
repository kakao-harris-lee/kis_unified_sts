"""The CLI that starts ③: the flag surface, the dry run, and the exit codes.

:mod:`~tools.tos_cp3.live_producer.producer`'s own docstring has always called
that file two things — "the thin outer loop, and the CLI that starts it". This
is the second of those, moved out verbatim so the loop is one thing. It is the
same file split plan §3.5 made for
:mod:`~tools.tos_cp3.live_producer.line` (the pure per-bar half),
:mod:`~tools.tos_cp3.live_producer.halt_policy` (the give-ups) and
:mod:`~tools.tos_cp3.live_producer.declaration` (the tenant's fields.yaml).

**The entry point does not move.** ``producer.py`` re-exports
:func:`build_parser` and :func:`main`, so ``python -m
tools.tos_cp3.live_producer.producer`` — what ``run_tenant_session.sh`` step 8
runs — is unchanged, and so is every caller that reaches them through
``producer``.

:class:`~tools.tos_cp3.live_producer.producer.LiveProducer` is imported INSIDE
:func:`main` rather than at module scope: ``producer`` imports this module to
re-export, so a module-scope import here would close the loop. The same
deliberate deferral ``produce_fields.run()`` uses for the legacy driver.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.config.dotenv_guard import read_explicit_dotenv  # noqa: E402
from tools.tos_cp3.live_producer.config import (  # noqa: E402
    LiveProducerRefused,
    assert_env_pins,
    load_config,
    read_query_credentials,
)
from tools.tos_cp3.live_producer.line import SOURCE_ID  # noqa: E402
from tools.tos_cp3.live_producer.real_quotes import real_quotes  # noqa: E402
from tools.tos_cp3.quote_client import KST, QUOTE_ROUTES  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools/tos_cp3/live_producer",
        description=(
            "CP-3 ③ real-time fifteen-field producer: one journal line per "
            "completed minute bar, GET-only quotation TR, no order path."
        ),
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--instrument",
        required=True,
        help=(
            "the contract code, as an ARGUMENT only (plan §3.5): the runner "
            "computes the roll once and gives render, data dir and producer the "
            "same value"
        ),
    )
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument(
        "--tenant-tree",
        type=Path,
        required=True,
        help=(
            "the rendered tenant tree this session serves. Its fields.yaml "
            "computes the published fields (P2-c) and its strategies/ is what "
            "the publish set is checked against. REQUIRED: without a "
            "declaration there is nothing to publish, so the producer refuses "
            "rather than falling back to anything"
        ),
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=None,
        help="target session (default: today in KST)",
    )
    parser.add_argument("--confirm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI. Exit codes: ``0`` ok, ``1`` refusal, ``2`` bad arguments."""
    from tools.tos_cp3.live_producer.producer import Clock, LiveProducer

    args = build_parser().parse_args(argv)
    config = load_config(args.config, repo_root=REPO_ROOT)
    target = args.date or datetime.now(KST).date()
    if not args.confirm:
        print(
            json.dumps(
                {
                    "mode": "DRY_RUN",
                    "date": str(target),
                    "instrument": args.instrument,
                    "method": "GET",
                    "market": config.market,
                    "tr_id": QUOTE_ROUTES[config.market][0],
                    "path": QUOTE_ROUTES[config.market][1],
                    "source_id": SOURCE_ID,
                    "journal": str(args.journal),
                    "session_dir": str(args.session_dir),
                    "tenant_tree": str(args.tenant_tree),
                    "fields_yaml": str(args.tenant_tree / "fields.yaml"),
                    "first_poll_delay_s": config.first_poll_delay_s,
                    "missing_no_successor_timeout_s": (
                        config.missing_no_successor_timeout_s
                    ),
                    "orders": 0,
                }
            )
        )
        return 0

    os.umask(0o077)
    producer = LiveProducer(
        config=config,
        instrument=args.instrument,
        target=target,
        session_dir=args.session_dir,
        journal_path=args.journal,
        tenant_tree=args.tenant_tree,
        clock=Clock(now=lambda: datetime.now(KST), sleep=_sleep),
        quotes_factory=real_quotes,
    )
    try:
        assert_env_pins(config, os.environ)
        read_query_credentials(config, reader=read_explicit_dotenv, environ=os.environ)
        producer.boot()
        producer.run_session()
    except LiveProducerRefused as exc:
        print(f"live_producer: REFUSED — {exc}", file=sys.stderr)
        return 1
    finally:
        producer.finish()
    return 0


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)
