"""The band GET, as its own short-lived process (band plan v3, 2026-10-16)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.config.dotenv_guard import read_explicit_dotenv  # noqa: E402
from tools.broker_probes.common import SafetyViolation  # noqa: E402
from tools.tos_cp3.live_producer.band_line import (  # noqa: E402
    BAND_KEY_ORDER,
    BAND_LINE_KIND,
    BandLineError,
    TickLadderMismatch,
    band_values_from_payload,
    check_broker_tick,
    load_tick_ladder,
    session_open_ms,
)
from tools.tos_cp3.live_producer.config import (  # noqa: E402
    LiveProducerRefused,
    assert_env_pins,
    load_config,
    read_query_credentials,
)
from tools.tos_cp3.live_producer.line import SOURCE_ID  # noqa: E402
from tools.tos_cp3.live_producer.real_quotes import real_quotes  # noqa: E402
from tools.tos_cp3.live_producer.session_log import EventLog  # noqa: E402
from tools.tos_cp3.live_producer.sinks import (  # noqa: E402
    ObservationJournal,
    refuse_if_journal_exists,
)
from tools.tos_cp3.quote_client import BAND_ROUTES, KST  # noqa: E402

BAND_LOG_NAME = "band-log.jsonl"

RC_OK = 0
RC_REFUSED = 2
RC_SOFT_FAILURE = 3
RC_DRY_RUN = 4


def band_journal_path(session_dir: Path) -> Path:
    """Where the band line lands: the session dir's own ``band.jsonl``."""
    from tools.tos_cp3.live_producer.band_line import BAND_JOURNAL_NAME

    return session_dir / BAND_JOURNAL_NAME


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools/tos_cp3/live_producer/band_probe",
        description=(
            "CP-3 band probe: one GET-only FHMIF10000000 read, one band.jsonl "
            "line, then exit. No order path."
        ),
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--instrument",
        required=True,
        help="the contract code, as an ARGUMENT only — the runner computes the "
        "roll once and gives render, producer and this probe the same value",
    )
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=None,
        help="target session (default: today in KST)",
    )
    parser.add_argument("--confirm", action="store_true")
    return parser


def _publish(
    *,
    journal_path: Path,
    clock: Any,
    log: EventLog,
    instrument: str,
    trading_date: str,
    read: Any,
    values: dict[str, str],
    market: str,
) -> int:
    """Write the one band line, log it, and return the exit code."""
    journal = ObservationJournal(
        journal_path,
        clock=lambda: int(clock().timestamp() * 1000),
        key_order=BAND_KEY_ORDER,
    )
    row = {
        "kind": BAND_LINE_KIND,
        "source_id": SOURCE_ID,
        "instrument": instrument,
        "trading_date": trading_date,
        "tr_id": BAND_ROUTES[market][0],
        "raw_payload_digest": read.raw_payload_digest,
        "producer_continuity_id": f"band-probe/{os.getpid()}",
        **values,
    }
    outcome = journal.append(row)
    if not outcome.written:
        log.event({"stage": outcome.reason or "band_not_written"})
        return RC_SOFT_FAILURE
    log.event(
        {
            "stage": "band_published",
            "tr_id": BAND_ROUTES[market][0],
            "path": BAND_ROUTES[market][1],
            "instrument": instrument,
            "trading_date": row["trading_date"],
            "as_of_ms": outcome.as_of_ms,
            "raw_payload_digest": read.raw_payload_digest,
        }
    )
    return RC_OK


def run(
    *,
    config_path: Path,
    instrument: str,
    session_dir: Path,
    target: date,
    quotes_factory: object = real_quotes,
    now: Callable[[], datetime] | None = None,
) -> int:
    """One attempt. Returns the exit code; raises only on a gate refusal."""
    clock = now if now is not None else (lambda: datetime.now(KST))
    config = load_config(config_path, repo_root=REPO_ROOT)
    ladder = None
    if config.venue_policy_yaml is not None:
        try:
            ladder = load_tick_ladder(config.venue_policy_yaml)
        except BandLineError as exc:
            raise LiveProducerRefused(str(exc)) from exc
    log = EventLog(session_dir, name=BAND_LOG_NAME)
    journal_path = band_journal_path(session_dir)

    refuse_if_journal_exists(journal_path)

    open_ms, trading_date = session_open_ms(
        config_path, repo_root=REPO_ROOT, day=target
    )
    at = clock()
    now_ms = int(at.timestamp() * 1000)
    if now_ms < open_ms:
        raise LiveProducerRefused(
            f"{at.isoformat()} is before the session open for {target} "
            f"({open_ms} ms). The band is read at the first boundary AFTER the "
            "open; a pre-open response is the one most likely to carry "
            "yesterday's band (band plan §3.1)"
        )

    quotes = quotes_factory(config, log)  # type: ignore[operator]
    try:
        try:
            read = quotes.band(instrument)
            values = band_values_from_payload(read.payload, config.market)
            if ladder is not None:
                compared = check_broker_tick(read.payload, ladder)
                log.event({"stage": "band_tick_checked", **compared})
        except TickLadderMismatch as exc:
            log.event({"stage": "band_tick_mismatch", "why": str(exc)})
            return RC_SOFT_FAILURE
        except SafetyViolation:
            raise
        except (RuntimeError, BandLineError) as exc:
            log.event({"stage": "band_fetch_failed", "why": str(exc)})
            return RC_SOFT_FAILURE

        return _publish(
            journal_path=journal_path,
            clock=clock,
            log=log,
            instrument=instrument,
            trading_date=trading_date,
            read=read,
            values=values,
            market=config.market,
        )
    finally:
        http = getattr(quotes, "http", None)
        if http is not None:
            http.close()


def main(argv: list[str] | None = None) -> int:
    """CLI. See the module docstring for what each code means."""
    args = build_parser().parse_args(argv)
    target = args.date or datetime.now(KST).date()
    if not args.confirm:
        market = load_config(args.config, repo_root=REPO_ROOT).market
        print(
            json.dumps(
                {
                    "mode": "DRY_RUN",
                    "date": str(target),
                    "instrument": args.instrument,
                    "method": "GET",
                    "market": market,
                    "tr_id": BAND_ROUTES[market][0],
                    "path": BAND_ROUTES[market][1],
                    "journal": str(band_journal_path(args.session_dir)),
                    "orders": 0,
                }
            )
        )
        return RC_DRY_RUN

    os.umask(0o077)
    try:
        config = load_config(args.config, repo_root=REPO_ROOT)
        assert_env_pins(config, os.environ)
        read_query_credentials(config, reader=read_explicit_dotenv, environ=os.environ)
        return run(
            config_path=args.config,
            instrument=args.instrument,
            session_dir=args.session_dir,
            target=target,
        )
    except LiveProducerRefused as exc:
        print(f"band_probe: REFUSED — {exc}", file=sys.stderr)
        return RC_REFUSED


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI tests
    raise SystemExit(main())
