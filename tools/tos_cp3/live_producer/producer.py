"""③ itself: the pure ``build_line`` and the thin outer loop around it.

Plan §3.5 splits the producer in two on purpose — a pure function that turns a
frame into one journal row, and a loop that does HTTP and file replacement —
so the field computation is testable without a clock or a socket.

**Why a batch re-run every minute rather than an incremental engine** (plan
§3.1): ``produce_bars`` calls ``check()`` exactly once per bar, and that single
call is what advances the setup's causal ATR / close / VWAP windows. Using the
same function keeps ONE definition of the fifteen fields; an incremental
implementation would be a second one needing its own equivalence proof. The
PR-1 M3 proxy measured the cost at 0.35 s worst case against the plan's 1.0 s
budget (that measurement is on a different contract month — evidence §4.1).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.config.dotenv_guard import read_explicit_dotenv  # noqa: E402
from tools.broker_probes.common import resolve_credentials  # noqa: E402
from tools.tos_cp3 import TOS_CP3_VERSION  # noqa: E402
from tools.tos_cp3.live_producer.calendar import (  # noqa: E402
    RuntimeCalendar,
    SessionWindow,
    load_runtime_calendar,
)
from tools.tos_cp3.live_producer.config import (  # noqa: E402
    LiveProducerConfig,
    LiveProducerRefused,
    assert_env_pins,
    load_config,
    read_query_credentials,
)
from tools.tos_cp3.live_producer.frame import (  # noqa: E402
    Bar,
    FreezeStep,
    Seed,
    build_seed,
    freeze_step,
    same_contract_seed,
)
from tools.tos_cp3.live_producer.sinks import (  # noqa: E402
    ObservationJournal,
    acquire_journal_lock,
    append_bar_part,
    market_digest,
    refuse_if_journal_exists,
    refuse_if_partitions_exist,
)
from tools.tos_cp3.minute_probe import frame as bars_to_frame  # noqa: E402
from tools.tos_cp3.produce_fields import (  # noqa: E402
    ContractSpecRegistry,
    OpenAnchor,
    ProduceFieldsError,
    StrategyInputs,
    load_strategy_inputs,
    produce_bars,
    resolve_contract_spec,
    resolve_open_anchor,
)
from tools.tos_cp3.quote_client import KST, QUOTE_PATH, TR, Quotes  # noqa: E402

#: The allowlist prefix added to ``bootproof_guard`` in this PR, and the full
#: ``source_id`` every line carries. The delimiter rule there means the prefix
#: matches ``tos-cp3-live`` exactly or ``tos-cp3-live/`` + anything.
SOURCE_PREFIX = "tos-cp3-live"
SOURCE_ID = f"{SOURCE_PREFIX}/{TOS_CP3_VERSION}"

#: The asset class segment of the Parquet layout B1a reads back.
ASSET_CLASS = "futures"


@dataclass(frozen=True)
class LineOutcome:
    """One attempt at a journal row: the row, or the reason there is none."""

    row: dict[str, Any] | None = None
    reason: str | None = None
    raw_event_id: str | None = None


def build_line(
    frame: Any,
    *,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: Any,
    anchor: OpenAnchor,
    bar_minute: datetime,
    now_ms: int,
    received_ms: int,
) -> LineOutcome:
    """The pure half: a frozen frame in, at most one journal row out.

    ``raw_event_id`` and the fifteen ``FIELD_ORDER`` values come from B1a's own
    ``produce_bars``, so the same bar's real-time and offline lines join in B3.
    Three keys differ from B1a (plan §1): ``as_of_ms`` is the stamp the caller
    is about to write with, ``source_id`` names this producer, and
    ``received_ms`` records when the REST response arrived.

    A last record that is not *bar_minute* is not a defect: ``produce_bars``
    omits a bar whose ATR/VWAP inputs cannot carry their published meaning, and
    B1a omits the same bar, so B3 does not diverge (plan §3.1). It is reported
    as ``omitted_unusable``.
    """
    import pandas as pd

    produced = produce_bars(
        frame,
        symbol=symbol,
        strategy=strategy,
        contract_spec=contract_spec,
        anchor=anchor,
    )
    last = produced.records[-1]
    # ``MarketContextReplay`` yields KST-AWARE stamps while the frozen frame and
    # ``parse_ohlcv`` carry naive KST wall time. Compared as-is, an aware and a
    # naive Timestamp for the same minute are never equal, so every line would
    # read as ``omitted_unusable`` and the producer would publish nothing at
    # all. Dropped the same way B1a's own ``_bar_lookup`` drops it.
    if pd.Timestamp(last.bar_kst).tz_localize(None) != pd.Timestamp(bar_minute):
        return LineOutcome(reason="omitted_unusable", raw_event_id=last.raw_event_id)
    return LineOutcome(
        row={
            "raw_event_id": last.raw_event_id,
            "source_id": SOURCE_ID,
            "instrument": last.instrument,
            "as_of_ms": now_ms,
            "received_ms": received_ms,
            "fields": last.fields,
        },
        raw_event_id=last.raw_event_id,
    )


class EventLog:
    """Append-only JSONL process log; also the ``Quotes`` recorder.

    The raw ``rows`` payload is replaced by its length: PR-1's own request log
    was 14 MB for one session, and the rows that matter are retained as the
    frozen Parquet frame (plan §3.6), not twice. Nothing here ever receives a
    header, a token or ``msg1`` — ``Quotes.page`` does not pass them.
    """

    def __init__(self, output: Path):
        output.mkdir(parents=True, exist_ok=True)
        self.output = output
        self.path = output / "producer-log.jsonl"

    def event(self, value: dict[str, Any]) -> None:
        payload = dict(value)
        rows = payload.pop("rows", None)
        if rows is not None:
            payload["row_count"] = len(rows)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


@dataclass
class Counters:
    """What the session reports back to the runner."""

    published: int = 0
    skipped_behind: int = 0
    missing_no_successor: int = 0
    omitted_unusable: int = 0
    produce_error: int = 0
    fetch_error: int = 0
    pre_boot_lines: int = 0
    max_stamp_to_replace_s: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "published": self.published,
            "skipped_behind": self.skipped_behind,
            "missing_no_successor": self.missing_no_successor,
            "omitted_unusable": self.omitted_unusable,
            "produce_error": self.produce_error,
            "fetch_error": self.fetch_error,
            "pre_boot_lines": self.pre_boot_lines,
            "max_stamp_to_replace_s": self.max_stamp_to_replace_s,
        }


@dataclass
class Clock:
    """Injected so the loop is testable without waiting a real minute."""

    now: Callable[[], datetime]
    sleep: Callable[[float], None]


@dataclass
class LiveProducer:
    """The thin outer loop: HTTP in, frozen frame and journal lines out."""

    config: LiveProducerConfig
    instrument: str
    target: date
    session_dir: Path
    journal_path: Path
    clock: Clock
    quotes_factory: Callable[[LiveProducerConfig, EventLog], Any]

    calendar: RuntimeCalendar = field(init=False)
    window: SessionWindow = field(init=False)
    strategy: StrategyInputs = field(init=False)
    anchor: OpenAnchor = field(init=False)
    contract_spec: Any = field(init=False)
    seed: Seed = field(init=False)
    quotes: Any = field(init=False)
    journal: ObservationJournal = field(init=False)
    log: EventLog = field(init=False)
    lock: Any = field(init=False, default=None)
    frozen: list[Bar] = field(default_factory=list)
    counters: Counters = field(default_factory=Counters)
    consecutive_produce_errors: int = 0

    def __post_init__(self) -> None:
        # The log exists before anything can refuse, so a refusal is recorded
        # in the session directory rather than only on the runner's stderr.
        self.log = EventLog(self.session_dir)

    # -- boot ------------------------------------------------------------

    def boot(self) -> None:
        """Everything that can refuse, before the first line is written."""
        self.calendar = load_runtime_calendar(self.config.calendar_yaml)
        if not self.calendar.is_trading_day(self.target):
            raise LiveProducerRefused(
                f"{self.target} is not a trading day in {self.calendar.path}"
            )
        self.window = self.calendar.window(
            self.config.calendar_session_id, self.config.calendar_session_phase
        )
        self.strategy = load_strategy_inputs(self.config.strategy_yaml)
        self.anchor = resolve_open_anchor(
            cli_value="auto", first_session=self.target, last_session=self.target
        )
        registry = ContractSpecRegistry.from_yaml(str(self.config.execution_yaml))
        self.contract_spec = resolve_contract_spec(self.instrument, registry)

        refuse_if_partitions_exist(
            self.market_root, asset_class=ASSET_CLASS, symbol=self.instrument
        )
        refuse_if_journal_exists(self.journal_path)
        self.lock = acquire_journal_lock(self.journal_path)
        self.journal = ObservationJournal(self.journal_path)
        self.quotes = self.quotes_factory(self.config, self.log)

        self.seed = build_seed(
            target=self.target,
            calendar=self.calendar,
            strategy=self.strategy,
            anchor=self.anchor,
            min_bars_per_day=self.config.min_bars_per_day,
            max_calendar_days=self.config.max_seed_calendar_days,
            fetch_day=lambda day, contract: self.quotes.history(contract, day),
            # The ONE seam plan §3.2a's cross-contract stitching (a later PR,
            # out of scope here) replaces. Same-contract seed, per plan §3.2.
            assembler=partial(same_contract_seed, instrument=self.instrument),
        )
        self._assert_one_anchor()
        append_bar_part(
            self.market_root,
            asset_class=ASSET_CLASS,
            symbol=self.instrument,
            bars=self.seed.bars,
        )
        self.log.event({"stage": "seed", **self._seed_lineage()})
        self._boot_today()

    @property
    def market_root(self) -> Path:
        return self.session_dir / "market"

    def _assert_one_anchor(self) -> None:
        """One anchor for the whole frame, or refuse.

        ``resolve_open_anchor`` refuses a window straddling the 2026-06-28
        open-anchor cutover, because one anchor cannot be right for both eras.
        The seed is assembled with the target's anchor, so re-resolving over the
        assembled window is what surfaces a seed that reached back past the
        cutover.
        """
        over_window = resolve_open_anchor(
            cli_value="auto",
            first_session=min(self.seed.days_used),
            last_session=self.target,
        )
        if over_window != self.anchor:
            raise LiveProducerRefused(
                f"the assembled frame {min(self.seed.days_used)}..{self.target} "
                f"resolves the open anchor to {over_window}, not the "
                f"{self.anchor} the seed was counted with"
            )

    def _seed_lineage(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "calendar_version": self.calendar.calendar_version,
            "session_window": f"{self.window.start}..{self.window.end}",
            "days_used": [str(day) for day in self.seed.days_used],
            "contracts_used": list(self.seed.contracts_used),
            "capacity": self.seed.capacity,
            "required": self.seed.required,
            "min_bars_per_day": self.seed.min_bars_per_day,
            "dropped_days": [
                {"day": str(s.day), "parsed_rows": s.parsed_rows}
                for s in self.seed.sessions
                if not s.density_pass
            ],
            "parser_env": dict(self.config.parser_env),
            "config_sha256": self.config.sha256,
            "source_id": SOURCE_ID,
        }

    def _boot_today(self) -> None:
        """Freeze today's already-complete bars and publish the newest one.

        A mid-session start would otherwise leave the morning out of the frame,
        and ``produce_bars`` over a frame missing today's earlier bars does not
        match B1a's. Full pagination is used here (not one page) because nothing
        is frozen yet. The one line written is the runner's "the producer is
        real" signal (plan §3.5); it is already STALE at boot and is counted
        separately as a pre-boot line (plan §5 M5, v2 review L1).
        """
        rows = self.quotes.history(self.instrument, self.target)
        received_ms = self._received_ms()
        step = freeze_step(
            rows,
            day=self.target,
            symbol=self.instrument,
            last_frozen_minute=None,
            session_ended=self._session_ended(),
        )
        self.log.event(
            {
                "stage": "boot_today",
                "raw_rows": len(rows),
                "frozen": len(step.newly_frozen),
                "deferred": [str(minute) for minute in step.deferred],
            }
        )
        if step.newly_frozen:
            self.counters.pre_boot_lines += 1
            self._publish(step, received_ms=received_ms)

    # -- session loop ----------------------------------------------------

    def run_session(self) -> None:
        """Walk minute boundaries to the session end, one decision each."""
        boundary = self._first_boundary()
        end = self.window.end_boundary(self.target)
        while boundary <= end:
            self._handle_boundary(boundary)
            if self.consecutive_produce_errors >= (
                self.config.max_consecutive_produce_errors
            ):
                raise LiveProducerRefused(
                    f"{self.consecutive_produce_errors} consecutive produce_error(s) "
                    "— stopping the producer (plan §3.5); the runner reports ABORT"
                )
            boundary += timedelta(minutes=1)

    def _first_boundary(self) -> datetime:
        """The next whole minute that is at least one bar past the session open."""
        opened = datetime.combine(self.target, self.window.start) + timedelta(minutes=1)
        now = self._now_naive().replace(second=0, microsecond=0) + timedelta(minutes=1)
        return max(opened, now)

    def _handle_boundary(self, boundary: datetime) -> None:
        bar_minute = boundary - timedelta(minutes=1)
        self._sleep_until(boundary + timedelta(seconds=self.config.first_poll_delay_s))
        deadline = boundary + timedelta(
            seconds=self.config.missing_no_successor_timeout_s
        )
        while True:
            try:
                step, received_ms = self._poll()
            except RuntimeError as exc:
                self.counters.fetch_error += 1
                self.log.event(
                    {"stage": "fetch_error", "boundary": str(boundary), "why": str(exc)}
                )
                step, received_ms = None, None
            if step is not None and step.newly_frozen:
                self._publish(step, received_ms=received_ms)
                return
            if self._now_naive() >= deadline:
                self.counters.missing_no_successor += 1
                self.log.event(
                    {
                        "stage": "missing_no_successor",
                        "boundary": str(boundary),
                        "bar": str(bar_minute),
                        "deferred": [str(m) for m in (step.deferred if step else ())],
                        "timeout_s": self.config.missing_no_successor_timeout_s,
                    }
                )
                return
            self.clock.sleep(self.config.repoll_pace_s)

    def _poll(self) -> tuple[FreezeStep, int]:
        """One page, escalating to full pagination when it cannot reach back."""
        last_frozen = self.frozen[-1][1] if self.frozen else None
        rows = self.quotes.page(self.instrument, self.target)
        received_ms = self._received_ms()
        step = self._freeze_from(rows, last_frozen)
        if (
            last_frozen is not None
            and step.oldest_raw_minute is not None
            and step.oldest_raw_minute > last_frozen
        ):
            # The page's oldest row is already newer than the last frozen bar,
            # so minutes between the two are off the page and would never be
            # frozen — the frame would get a hole B1a does not have.
            rows = self.quotes.history(self.instrument, self.target)
            received_ms = self._received_ms()
            step = self._freeze_from(rows, last_frozen)
            self.log.event(
                {"stage": "page_did_not_reach_back", "last_frozen": str(last_frozen)}
            )
        return step, received_ms

    def _freeze_from(
        self, rows: list[dict], last_frozen: datetime | None
    ) -> FreezeStep:
        return freeze_step(
            rows,
            day=self.target,
            symbol=self.instrument,
            last_frozen_minute=last_frozen,
            session_ended=self._session_ended(),
        )

    # -- publication -----------------------------------------------------

    def _publish(self, step: FreezeStep, *, received_ms: int | None) -> None:
        """Freeze every new bar, write them, and journal the newest one only."""
        self.frozen.extend(step.newly_frozen)
        append_bar_part(
            self.market_root,
            asset_class=ASSET_CLASS,
            symbol=self.instrument,
            bars=step.newly_frozen,
        )
        for behind in step.skipped_behind:
            self.counters.skipped_behind += 1
            self.log.event({"stage": "skipped_behind", "bar": str(behind[1])})

        bar = step.published
        if bar is None:
            raise LiveProducerRefused(
                "_publish was called with no newly frozen bar; a caller that "
                "publishes an empty step would write a line for the previous "
                "minute twice"
            )
        frame = bars_to_frame(list(self.seed.bars) + self.frozen)
        now = self.clock.now()
        try:
            outcome = build_line(
                frame,
                symbol=self.instrument,
                strategy=self.strategy,
                contract_spec=self.contract_spec,
                anchor=self.anchor,
                bar_minute=bar[1],
                now_ms=int(now.timestamp() * 1000),
                received_ms=(
                    self._received_ms() if received_ms is None else received_ms
                ),
            )
        except ProduceFieldsError as exc:
            self.counters.produce_error += 1
            self.consecutive_produce_errors += 1
            self.log.event(
                {"stage": "produce_error", "bar": str(bar[1]), "why": str(exc)}
            )
            return
        self.consecutive_produce_errors = 0
        if outcome.row is None:
            self.counters.omitted_unusable += 1
            self.log.event(
                {
                    "stage": outcome.reason,
                    "bar": str(bar[1]),
                    "last_raw_event_id": outcome.raw_event_id,
                }
            )
            return
        elapsed = self.journal.append(outcome.row)
        self.counters.published += 1
        self.counters.max_stamp_to_replace_s = max(
            self.counters.max_stamp_to_replace_s, elapsed
        )
        self.log.event(
            {
                "stage": "published",
                "bar": str(bar[1]),
                "raw_event_id": outcome.row["raw_event_id"],
                "as_of_ms": outcome.row["as_of_ms"],
                "received_ms": outcome.row["received_ms"],
                "stamp_to_replace_s": elapsed,
            }
        )

    # -- clock helpers ---------------------------------------------------

    def _now_naive(self) -> datetime:
        return self.clock.now().replace(tzinfo=None)

    def _session_ended(self) -> bool:
        return self._now_naive() >= self.window.end_boundary(self.target)

    def _sleep_until(self, when: datetime) -> None:
        self.clock.sleep(max(0.0, (when - self._now_naive()).total_seconds()))

    def _received_ms(self) -> int:
        received = getattr(self.quotes, "last_received_kst", None)
        if received is None:
            return int(self.clock.now().timestamp() * 1000)
        return int(received.timestamp() * 1000)

    # -- teardown --------------------------------------------------------

    def finish(self) -> dict[str, Any]:
        """Fingerprint the frozen frame and report. Always runs."""
        digest = market_digest(self.market_root) if self.market_root.is_dir() else {}
        summary = {
            "stage": "finish",
            "instrument": self.instrument,
            "date": str(self.target),
            "source_id": SOURCE_ID,
            "frozen_bars_today": len(self.frozen),
            "counters": self.counters.as_dict(),
            "market_sha256": digest,
        }
        (self.market_root / "sha256.json").parent.mkdir(parents=True, exist_ok=True)
        (self.market_root / "sha256.json").write_text(
            json.dumps(digest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (self.session_dir / "producer-summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        self.log.event(summary)
        for closeable in (
            getattr(getattr(self, "quotes", None), "http", None),
            self.lock,
        ):
            if closeable is not None:
                closeable.close()
        return summary


def _real_quotes(config: LiveProducerConfig, log: EventLog) -> Quotes:
    """The real transport. Only reached with ``--confirm``."""
    creds = resolve_credentials("futures", is_real=True)
    return Quotes(creds, log, config.transport, token_cache=config.token_cache_dir)


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
        "--date",
        type=date.fromisoformat,
        default=None,
        help="target session (default: today in KST)",
    )
    parser.add_argument("--confirm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI. Exit codes: ``0`` ok, ``1`` refusal, ``2`` bad arguments."""
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
                    "tr_id": TR,
                    "path": QUOTE_PATH,
                    "source_id": SOURCE_ID,
                    "journal": str(args.journal),
                    "session_dir": str(args.session_dir),
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
        clock=Clock(now=lambda: datetime.now(KST), sleep=_sleep),
        quotes_factory=_real_quotes,
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


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI tests
    raise SystemExit(main())
