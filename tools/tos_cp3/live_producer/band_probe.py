"""The band GET, as its own short-lived process (band plan v3, 2026-10-16).

One GET of ``FHMIF10000000``, one line into ``band.jsonl``, exit. Nothing else:
no loop, no clock to watch, no state to keep. The runner launches it under
``timeout`` after the open and reads its exit code.

**Why a process.** Three review rounds established that a Python process cannot
honestly bound its own synchronous HTTP call: httpx's ``read`` timeout bounds
one chunk, a deadline inside ``iter_bytes()`` sees only decoded content (so it
misses header reception and compressed bytes that decode to nothing), and a
worker thread leaves the caller blocking in ``client.close()``, hashes and
parses outside the budget, and strands ``KISAuthManager.get_token()``'s lock so
the next price poll waits on it. A process under ``timeout`` has none of those
holes, because SIGKILL does not negotiate.

**Credential separation is unchanged** (③ plan §3.4). This process reads the
two real futures QUERY keys ITSELF, from the ``env_file`` its own config names
— exactly as the producer does. The runner's environment and the runtime's
still hold no real key, and the runner's own guard still refuses to start if
they do.

**The token cache is SHARED with the producer** — one path, keyed by the app
key's fingerprint (:func:`~tools.tos_cp3.live_producer.real_quotes.real_quotes`).
In the normal case this process issues no token at all: the producer has been
running since before the open, so its cached token is valid and this one reads
it. That matters because KIS rate-limits token issuance, and it is why
``shared.kis.auth._save_token_cache_secure`` writes through a temp file and
``os.replace`` — with two processes on one file, an in-place write let a reader
see a truncated JSON document, whose cost is a needless re-issue.

**Exit codes** — the runner's whole interface to this program:

===  ==========================================================================
0    a band line was written
4    a DRY RUN: no ``--confirm``, so nothing was attempted and nothing written.
     Its own code because 0 means "there is a line now", and a caller that
     forgot ``--confirm`` would otherwise be told it succeeded. The runner
     always passes ``--confirm``, so it never sees this.
2    a REFUSAL before any GET, i.e. every ``LiveProducerRefused``: an existing
     ``band.jsonl``, a pre-open call, a config or credential refusal. No line,
     nothing attempted.
3    a SOFT failure: the GET ran and did not produce a usable line (transport,
     ``rt_cd != 0``, an absent field, a response past the size cap). No line.
1    the allowlist gate refused the call, or any other unexpected exception:
     traceback, and the runner treats it as a hard ABORT. This is the one code
     that means "a defect in this repo", not "the broker said no".
===  ==========================================================================

A failed CALENDAR read (``BandLineError`` out of
:func:`~tools.tos_cp3.live_producer.band_line.session_open_ms`) is deliberately
in the rc 1 group rather than rc 2: the runner computed the launch time with
that same function minutes earlier and aborted if it could not, so a failure
here means the config or calendar changed underneath a running session.

Firewall: legacy side (``tools/``). No ``tos`` / ``tos_runtime`` import.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
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
    band_values_from_payload,
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
from tools.tos_cp3.quote_client import BAND_PATH, BAND_TR, KST  # noqa: E402

#: The band request log, beside the producer's own. A SEPARATE file because the
#: two processes write independently and an interleaved append is a corrupt
#: line; the post-session TR check reads BOTH (runbook §7.2-d).
BAND_LOG_NAME = "band-log.jsonl"

#: Exit codes. Named so the runner and this module cannot drift.
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
) -> int:
    """Write the one band line, log it, and return the exit code.

    Split out of :func:`run` only because that function hit the repo's
    100-line function budget; the two halves are "may we call at all" and
    "record what came back".

    The ``trading_date`` is the one :func:`session_open_ms` derived from the
    producer's calendar — the same value the runner's read-side predicate
    compares this line against, so the writer and the reader cannot disagree
    about which day this is.
    """
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
        "tr_id": BAND_TR,
        "raw_payload_digest": read.raw_payload_digest,
        # One process, one line, so continuity is this run's own identity.
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
            "tr_id": BAND_TR,
            "path": BAND_PATH,
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
    now: object = None,
) -> int:
    """One attempt. Returns the exit code; raises only on a gate refusal.

    Args:
        quotes_factory: injected so the tests drive a fake transport. The real
            one resolves the REAL credentials (``real_quotes``).
        now: injected clock returning a KST-aware ``datetime``; defaults to the
            wall clock.
    """
    clock = now if now is not None else (lambda: datetime.now(KST))
    config = load_config(config_path, repo_root=REPO_ROOT)
    log = EventLog(session_dir, name=BAND_LOG_NAME)
    journal_path = band_journal_path(session_dir)

    # ⛔ Before anything else: this process creates the band journal, it never
    # writes into somebody else's. Same refusal the producer uses on the price
    # journal, for the same reason — every write replaces the file whole.
    refuse_if_journal_exists(journal_path)

    open_ms, trading_date = session_open_ms(
        config_path, repo_root=REPO_ROOT, day=target
    )
    at = clock()
    now_ms = int(at.timestamp() * 1000)
    if now_ms < open_ms:
        # The runner sleeps until open + one boundary, so reaching here means a
        # hand-run. Refuse rather than stamp a pre-open band the runtime would
        # use all day (band plan §4.4a's residual risk is largest then).
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
            values = band_values_from_payload(read.payload)
        except SafetyViolation:
            # BEFORE the RuntimeError clause, because it IS a RuntimeError.
            #
            # ⚠ The first cut of this function had the comment below claiming
            # the gate's refusal was re-raised "above this" and no clause doing
            # it — the identical false-premise defect PR #906 review round 1
            # found in `band.py`, written again in the same session. The test
            # `test_red_a_gate_refusal_in_the_probe_is_not_a_soft_failure`
            # caught it; the comment did not.
            raise
        except (RuntimeError, BandLineError) as exc:
            # A soft failure: the broker's answer, not a defect here. The
            # clause above keeps the gate's refusal out of this one — folding
            # it in here is how "zero real futures orders" would become a log
            # line on a session that reported success.
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
        print(
            json.dumps(
                {
                    "mode": "DRY_RUN",
                    "date": str(target),
                    "instrument": args.instrument,
                    "method": "GET",
                    "tr_id": BAND_TR,
                    "path": BAND_PATH,
                    "journal": str(band_journal_path(args.session_dir)),
                    "orders": 0,
                }
            )
        )
        return RC_DRY_RUN

    os.umask(0o077)
    try:
        # The credential read lives HERE, not in `run()` — the same split the
        # producer's own `main` uses. `run()` then takes its transport as an
        # argument, which is what lets the tests drive it with no credential
        # and no socket: `read_explicit_dotenv` does nothing at all in hermetic
        # mode, so a `run()` that read keys itself could not be tested without
        # defeating that guard.
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
        # ⚠ A refusal from `load_config` happens BEFORE `run()` opens the
        # event log, so an rc 2 session can leave no `band-log.jsonl` at all.
        # The evidence is this line in the runner's own log, and runbook
        # §7.2-d says so where it reads that file — "no band log" means
        # "never launched OR refused before the GET", not "never launched".
        print(f"band_probe: REFUSED — {exc}", file=sys.stderr)
        return RC_REFUSED


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI tests
    raise SystemExit(main())
