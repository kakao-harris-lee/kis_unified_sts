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
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.config.dotenv_guard import read_explicit_dotenv  # noqa: E402
from tools.broker_probes.common import (  # noqa: E402
    resolve_credentials,
    secret_fingerprint,
)
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
    SEED_DROP_DENSITY,
    SEED_DROP_NO_RAW_ROWS,
    Bar,
    FreezeStep,
    Seed,
    build_seed,
    freeze_step,
)
from tools.tos_cp3.live_producer.sinks import (  # noqa: E402
    ObservationJournal,
    acquire_session_lock,
    append_bar_part,
    market_digest,
    refuse_if_journal_exists,
    refuse_if_partitions_exist,
)
from tools.tos_cp3.live_producer.stitch_seed import StitchedSeed  # noqa: E402
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
from tools.tos_cp3.stitch import (  # noqa: E402
    STITCH_FILENAME,
    StitchManifest,
    rows_digest,
    write_manifest,
)

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
    received_ms: int,
) -> LineOutcome:
    """The pure half: a frozen frame in, at most one journal row out.

    ``raw_event_id`` and the fifteen ``FIELD_ORDER`` values come from B1a's own
    ``produce_bars``, so the same bar's real-time and offline lines join in B3.
    Two keys differ from B1a here (plan §1): ``source_id`` names this producer
    and ``received_ms`` records when the REST response arrived.

    **The row carries no ``as_of_ms``** (review B1). This function runs
    ``produce_bars`` — measured at ~0.44 s late in a session — so a stamp taken
    here would already have spent more than the tenant's whole 800 ms budget by
    the time the line is written. :meth:`~tools.tos_cp3.live_producer.sinks
    .ObservationJournal.append` takes it immediately before the replace, and
    refuses a row that arrives with one.

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
    """What the session reports back to the runner.

    The unpublished reasons are kept apart on purpose — merged, none of them
    says anything an operator can act on:

    * ``missing_no_successor`` — the minute TRADED (a raw row exists) but no
      strictly later row arrived inside G, so publication is skipped (plan
      §3.3). This is the 15:34 shape.
    * ``no_raw_row_for_minute`` — the minute produced no raw row at all, so
      there is no bar to publish. This is the 15:35-15:44 call-auction shape,
      and it is NOT a late feed (review M1).
    * ``late_completed`` — an OLDER bar completed after its own boundary had
      already passed. It is frozen into the frame and written to Parquet so B1a
      parity holds, but it is not published: a line stamped now would carry a
      fresh ``as_of_ms`` for a stale bar, and the runtime would consume it as
      the current observation (review M1).
    * ``skipped_behind`` — more than one bar completed in ONE poll; only the
      newest is published (plan §2 4), and the older ones — this boundary's own
      bar among them when a poll came back after the next bar had completed
      too — are counted here.
    * ``already_published`` — this boundary's bar was already published, as the
      catch-up of an earlier boundary whose poll returned late (review N1), so
      the boundary polls nothing. Without it the bar is frozen and unpublishable
      and the boundary would wait the full G and then claim
      ``missing_no_successor`` for a bar sitting in the frame.
    """

    published: int = 0
    skipped_behind: int = 0
    late_completed: int = 0
    missing_no_successor: int = 0
    no_raw_row_for_minute: int = 0
    already_published: int = 0
    omitted_unusable: int = 0
    produce_error: int = 0
    clock_regression: int = 0
    fetch_error: int = 0
    pre_boot_lines: int = 0
    max_stamp_to_replace_s: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "published": self.published,
            "skipped_behind": self.skipped_behind,
            "late_completed": self.late_completed,
            "missing_no_successor": self.missing_no_successor,
            "no_raw_row_for_minute": self.no_raw_row_for_minute,
            "already_published": self.already_published,
            "omitted_unusable": self.omitted_unusable,
            "produce_error": self.produce_error,
            "clock_regression": self.clock_regression,
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
    assembler: StitchedSeed = field(init=False)
    manifest: StitchManifest = field(init=False)
    quotes: Any = field(init=False)
    journal: ObservationJournal = field(init=False)
    log: EventLog = field(init=False)
    lock: Any = field(init=False, default=None)
    #: ``"<contract>:<day>" -> sha256`` of the raw response the day was parsed
    #: from. Becomes the manifest's ``source_sha256``.
    raw_digests: dict[str, str] = field(default_factory=dict)
    frozen: list[Bar] = field(default_factory=list)
    counters: Counters = field(default_factory=Counters)
    consecutive_produce_errors: int = 0
    #: The minute of the last bar a journal line was actually WRITTEN for. It
    #: only ever advances, and a boundary at or behind it has nothing left to do
    #: (review N1). Set after the write, never before: a bar that ended in
    #: ``omitted_unusable``, ``produce_error`` or a refused stamp was not
    #: published and must not silence its own boundary.
    last_published_minute: datetime | None = None

    def __post_init__(self) -> None:
        # The log exists before anything can refuse, so a refusal is recorded
        # in the session directory rather than only on the runner's stderr.
        self.log = EventLog(self.session_dir)

    # -- boot ------------------------------------------------------------

    def boot(self) -> None:
        """Everything that can refuse, before the first line is written.

        **The session lock comes first** (review L5). The partition and journal
        refusals below read the very state a second producer is about to
        create, so taking the lock after them is a race in which both processes
        see an empty tree and both proceed.
        """
        self.lock = acquire_session_lock(self.market_root)
        refuse_if_partitions_exist(
            self.market_root, asset_class=ASSET_CLASS, symbol=self.instrument
        )
        refuse_if_journal_exists(self.journal_path)

        self.calendar = load_runtime_calendar(
            self.config.calendar_yaml,
            covered_years=self.config.calendar_covered_years,
        )
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

        self.journal = ObservationJournal(
            self.journal_path, clock=lambda: int(self.clock.now().timestamp() * 1000)
        )
        self.quotes = self.quotes_factory(self.config, self.log)

        self.assembler = StitchedSeed(
            instrument=self.instrument,
            target=self.target,
            product=self.config.front_month_product,
            fetch_day=self._fetch_day,
        )
        self.seed = build_seed(
            target=self.target,
            calendar=self.calendar,
            strategy=self.strategy,
            anchor=self.anchor,
            min_bars_per_day=self.config.min_bars_per_day,
            max_calendar_days=self.config.max_seed_calendar_days,
            fetch_day=self._fetch_day,
            # The ONE seam (plan §3.2 :data:`SeedAssembler`). PR-2 passed
            # ``same_contract_seed`` here and measured the post-roll blackout
            # that follows; PR-2b passes the cross-contract assembler and
            # nothing else in this file's seed path changed.
            assembler=self.assembler,
        )
        self._assert_one_anchor()
        self._store_unadjusted_seed()
        self.manifest = self._write_manifest()
        self.log.event({"stage": "seed", **self._seed_lineage()})
        self._boot_today()

    def _fetch_day(self, day: date, contract: str) -> list[dict]:
        """One day's raw rows, fingerprinted for the manifest as they arrive.

        ``source_sha256`` is what lets a reader ask "were these partitions
        built from the responses the manifest claims?" — the responses
        themselves are far too large to commit (PR-1's single session was
        14 MB), so the digest travels instead of the bytes.
        """
        rows = self.quotes.history(contract, day)
        self.raw_digests[f"{contract}:{day.isoformat()}"] = rows_digest(rows)
        return rows

    def _store_unadjusted_seed(self) -> None:
        """Write every seed day under ITS OWN contract's partition, unadjusted.

        Plan §3.2a 「라벨은 진실하게」: the previous month's bars are stored as
        the previous month's, and the splice day's new-contract bars under the
        new month's — the evidence ``c_x100`` is recomputed from. The
        back-adjust is applied on READ (``load_window(stitch_manifest=…)``),
        never on write, because the legacy A05611 Parquet's date-label defect
        (plan §6.1) is exactly what happens when one instrument's values are
        stored under another's name.
        """
        for entry in self.seed.kept:
            append_bar_part(
                self.market_root,
                asset_class=ASSET_CLASS,
                symbol=entry.contract,
                bars=entry.bars,
            )
        if self.assembler.junction_new_bars:
            append_bar_part(
                self.market_root,
                asset_class=ASSET_CLASS,
                symbol=self.instrument,
                bars=self.assembler.junction_new_bars,
            )

    def _write_manifest(self) -> StitchManifest:
        """``<session dir>/market/stitch.json`` — written on EVERY session.

        Also with zero junctions (plan §9 MEDIUM-1). B1a and B2 refuse a data
        root that holds this file when they were not given it, and that
        refusal protects nothing if a same-contract session leaves the file
        out: the one run where the operator forgot the flag would be the one
        run where there was nothing to forget.
        """
        manifest = self.assembler.manifest(
            self.seed.kept, source_sha256=dict(self.raw_digests)
        )
        return write_manifest(self.market_root / STITCH_FILENAME, manifest)

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
            # Reason-tagged, not one count (review L3): a day the calendar
            # calls a trading day that returned ZERO rows may be a holiday the
            # calendar is missing, which is the defect plan §3.2 moved off
            # `shared/collector/historical/calendar.py` to avoid. Merged into a
            # density count it would be invisible.
            "dropped_days": [
                {
                    "day": str(s.day),
                    "raw_rows": s.raw_rows,
                    "parsed_rows": s.parsed_rows,
                    "reason": s.drop_reason,
                }
                for s in self.seed.sessions
                if not s.density_pass
            ],
            "dropped_no_raw_rows": sum(
                1 for s in self.seed.sessions if s.drop_reason == SEED_DROP_NO_RAW_ROWS
            ),
            "dropped_density": sum(
                1 for s in self.seed.sessions if s.drop_reason == SEED_DROP_DENSITY
            ),
            "calendar_covered_years": list(self.config.calendar_covered_years),
            "parser_env": dict(self.config.parser_env),
            "config_sha256": self.config.sha256,
            "source_id": SOURCE_ID,
            # Plan §3.2a. ``junctions`` is [] on a session with no splice and
            # the manifest is still written and still digested — B1a and B2
            # read it either way.
            "front_month_product": self.config.front_month_product,
            "stitch_manifest": str(self.market_root / STITCH_FILENAME),
            "stitch_manifest_sha256": self.manifest.sha256,
            "stitch_segments": [s.to_payload() for s in self.manifest.segments],
            "stitch_junctions": [j.to_payload() for j in self.manifest.junctions],
            "junction_new_contract_bars_stored_not_framed": len(
                self.assembler.junction_new_bars
            ),
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
        if not step.newly_frozen:
            return
        # The newest already-complete bar IS this boot's "current" bar: there is
        # no boundary yet, and the runner needs one real line to exist.
        newest = step.newly_frozen[-1]
        current = self._freeze(step, bar_minute=newest[1], at_boot=True)
        if current is not None:
            self.counters.pre_boot_lines += 1
            self._publish_bar(current, received_ms=received_ms)

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
        """Re-poll until THIS boundary's bar is complete, or until m+G.

        Freezing and publishing are separate (review M1). Every completed bar
        is frozen into the frame and written to Parquet on the poll that finds
        it, because B1a reads that frame and parity depends on every bar
        advancing the causal windows exactly once. The line written is for the
        bar this boundary is about — ``boundary - 1min`` — or, when a poll comes
        back so late that a NEWER bar completed in the same response, for that
        newest bar as a catch-up (:meth:`_publication_target`, review N1). An
        older bar that completes late is counted as ``late_completed`` and the
        loop KEEPS POLLING for the current one; the first cut returned on any
        newly frozen bar, which published a stale bar under a fresh stamp and
        then never looked for the current bar again (measured: 09:04 published
        at 09:06:01.85 while 09:05, complete at +2.5 s, was never published).
        """
        bar_minute = boundary - timedelta(minutes=1)
        if self._already_published(boundary, bar_minute):
            return
        self._sleep_until(boundary + timedelta(seconds=self.config.first_poll_delay_s))
        deadline = boundary + timedelta(
            seconds=self.config.missing_no_successor_timeout_s
        )
        raw_minutes: frozenset[datetime] = frozenset()
        while True:
            try:
                step, received_ms = self._poll()
            except RuntimeError as exc:
                self.counters.fetch_error += 1
                self.log.event(
                    {"stage": "fetch_error", "boundary": str(boundary), "why": str(exc)}
                )
                step, received_ms = None, None
            if step is not None:
                raw_minutes |= step.raw_minutes
                current = self._freeze(step, bar_minute=bar_minute)
                if current is not None:
                    self._publish_bar(current, received_ms=received_ms)
                    return
            if self._now_naive() >= deadline:
                self._record_unpublished(boundary, bar_minute, raw_minutes)
                return
            self.clock.sleep(self.config.repoll_pace_s)

    def _already_published(self, boundary: datetime, bar_minute: datetime) -> bool:
        """Has an earlier boundary's catch-up already published THIS bar?

        Then there is nothing to poll for (review N1). The bar is frozen, so no
        later ``freeze_step`` can return it again — polling the full G would
        find nothing and end in ``missing_no_successor``, a label that says "the
        minute traded but never completed" about a minute that completed and was
        published a boundary ago. Returning at once also keeps the loop's phase:
        the next boundary's first poll still lands at its own ``+δ``.
        """
        last = self.last_published_minute
        if last is None or bar_minute > last:
            return False
        self.counters.already_published += 1
        self.log.event(
            {
                "stage": "already_published",
                "boundary": str(boundary),
                "bar": str(bar_minute),
                "last_published_minute": str(last),
            }
        )
        return True

    def _record_unpublished(
        self,
        boundary: datetime,
        bar_minute: datetime,
        raw_minutes: frozenset[datetime],
    ) -> None:
        """Name WHY this boundary published nothing — the two reasons differ."""
        traded = bar_minute in raw_minutes
        stage = "missing_no_successor" if traded else "no_raw_row_for_minute"
        if traded:
            self.counters.missing_no_successor += 1
        else:
            self.counters.no_raw_row_for_minute += 1
        self.log.event(
            {
                "stage": stage,
                "boundary": str(boundary),
                "bar": str(bar_minute),
                "bar_minute_traded": traded,
                "timeout_s": self.config.missing_no_successor_timeout_s,
            }
        )

    def _poll(self) -> tuple[FreezeStep, int]:
        """One page, escalating to full pagination when it cannot reach back."""
        last_frozen = self.frozen[-1][1] if self.frozen else None
        rows = self.quotes.page(self.instrument, self.target)
        received_ms = self._received_ms()
        step = self._freeze_from(rows, last_frozen)
        if self._page_missed_bars(step, last_frozen):
            # Minutes between the page's oldest row and what is already frozen
            # are off the page and would never be frozen — the frame would get
            # a hole B1a does not have.
            rows = self.quotes.history(self.instrument, self.target)
            received_ms = self._received_ms()
            step = self._freeze_from(rows, last_frozen)
            self.log.event(
                {
                    "stage": "page_did_not_reach_back",
                    "last_frozen": str(last_frozen),
                    "session_start": str(self._session_start()),
                }
            )
        return step, received_ms

    def _session_start(self) -> datetime:
        return datetime.combine(self.target, self.window.start)

    def _page_missed_bars(self, step: FreezeStep, last_frozen: datetime | None) -> bool:
        """Does this page fail to reach back to where the frame must continue?

        Two cases, and the second was missing (review M2):

        * something is frozen — the page must reach at or before the last
          frozen minute, or the gap between them is lost;
        * **nothing is frozen yet** — the page must reach the session's OPEN
          minute, because the frame has to start there. The first cut only
          checked the first case, so if fetch errors right after the open
          outlasted a page span, the very first successful page started
          mid-morning and today's frame silently began there — a hole B1a does
          not have, in the one place no later poll can repair.
        """
        if step.oldest_raw_minute is None:
            return False
        floor = self._session_start() if last_frozen is None else last_frozen
        return step.oldest_raw_minute > floor

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

    # -- freezing and publication (separate on purpose — review M1) -------

    def _freeze(
        self, step: FreezeStep, *, bar_minute: datetime | None, at_boot: bool = False
    ) -> Bar | None:
        """Add every completed bar to the frame and Parquet; return the one to publish.

        ALL newly completed bars are frozen — B1a reads this frame and parity
        needs every bar to advance the causal windows exactly once. What comes
        back is the single bar this step publishes (:meth:`_publication_target`
        — *bar_minute*, or a newer bar that completed in the same response);
        the rest are counted and left unpublished, under the reason that is
        actually true of them:

        * ``at_boot`` — the morning already happened before this process
          existed. Those bars are not late, they are history, so they count as
          ``skipped_behind`` (plan §2 4's "one line per write").
        * in session, a bar OLDER than this boundary's bar — its own boundary
          came and went, so it is ``late_completed`` (review M1). It still
          enters the frame; it is simply never published.
        * in session, a bar at or after this boundary's bar that is not the one
          published — the plan's "several bars completed at once, publish the
          newest" case, so ``skipped_behind`` (plan §2 4). This is where
          *bar_minute* itself lands when a stalled poll overtook it.
        """
        if not step.newly_frozen:
            return None
        self.frozen.extend(step.newly_frozen)
        append_bar_part(
            self.market_root,
            asset_class=ASSET_CLASS,
            symbol=self.instrument,
            bars=step.newly_frozen,
        )
        current = self._publication_target(step, bar_minute)
        for bar in step.newly_frozen:
            if current is not None and bar[1] == current[1]:
                continue
            if not at_boot and bar_minute is not None and bar[1] < bar_minute:
                self.counters.late_completed += 1
                self.log.event(
                    {
                        "stage": "late_completed",
                        "bar": str(bar[1]),
                        "current_boundary_bar": str(bar_minute),
                        "frozen_into_frame": True,
                        "published": False,
                    }
                )
            else:
                self.counters.skipped_behind += 1
                self.log.event({"stage": "skipped_behind", "bar": str(bar[1])})
        return current

    def _publication_target(
        self, step: FreezeStep, bar_minute: datetime | None
    ) -> Bar | None:
        """The ONE bar of this step to publish: the newest, when it is not stale.

        Plan §2 4 is explicit — 「밀렸으면(여러 봉이 한꺼번에 완성) 가장 최근 완성 봉
        하나만 쓰고 건너뛴 봉은 skipped_behind 로」 — and the first cut published
        *bar_minute* instead, which is the same thing only while a poll returns
        inside its own minute. A poll that comes back after the next bar has
        also completed (review N1: one request can spend 3 x 10 s of transport
        timeout plus 2 x 2 s of backoff, and a ``history()`` escalation doubles
        that) froze both bars, and publishing the older one wrote a line over a
        frame that already ended at the newer one, so ``build_line`` dropped it
        as ``omitted_unusable`` — and the newer bar, frozen but unpublished,
        could never be published afterwards either.

        Nothing OLDER than *bar_minute* is ever returned: that bar's own
        boundary has passed and a fresh stamp on it would be consumed as the
        current observation (review M1), which is the whole reason freezing and
        publishing are separate. Because the target always comes from
        ``newly_frozen``, and a bar is frozen exactly once, the published
        minutes are strictly increasing and no bar is published twice.
        """
        if bar_minute is None:
            return None
        newest = step.newly_frozen[-1]
        return newest if newest[1] >= bar_minute else None

    def _publish_bar(self, bar: Bar, *, received_ms: int | None) -> None:
        """Compute the fifteen fields for *bar* and journal one line."""
        frame = bars_to_frame(list(self.seed.bars) + self.frozen)
        try:
            outcome = build_line(
                frame,
                symbol=self.instrument,
                strategy=self.strategy,
                contract_spec=self.contract_spec,
                anchor=self.anchor,
                bar_minute=bar[1],
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
        # The journal stamps as_of_ms here, AFTER the compute above (review B1).
        result = self.journal.append(outcome.row)
        if not result.written:
            # Plan §2 5: refuse this write and log it; the session goes on
            # (review L6). A clock that went backwards is a defect, but ending
            # the session loses every remaining minute of a market day too.
            self.counters.clock_regression += 1
            self.log.event(
                {
                    "stage": result.reason,
                    "bar": str(bar[1]),
                    "as_of_ms": result.as_of_ms,
                    "last_as_of_ms": self.journal.last_as_of_ms,
                    "written": False,
                }
            )
            return
        self.counters.published += 1
        self.last_published_minute = bar[1]
        self.counters.max_stamp_to_replace_s = max(
            self.counters.max_stamp_to_replace_s, result.stamp_to_replace_s
        )
        self.log.event(
            {
                "stage": "published",
                "bar": str(bar[1]),
                "raw_event_id": outcome.row["raw_event_id"],
                "as_of_ms": result.as_of_ms,
                "received_ms": outcome.row["received_ms"],
                "stamp_to_replace_s": result.stamp_to_replace_s,
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
        manifest = getattr(self, "manifest", None)
        summary = {
            "stage": "finish",
            "instrument": self.instrument,
            "date": str(self.target),
            "source_id": SOURCE_ID,
            "frozen_bars_today": len(self.frozen),
            "counters": self.counters.as_dict(),
            "market_sha256": digest,
            # What B1a and B2 must be given to reproduce this session's frame.
            "stitch_manifest_sha256": manifest.sha256 if manifest else None,
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
    """The real transport. Only reached with ``--confirm``.

    The cache path carries the app-key FINGERPRINT (review L2). Dropping that
    segment is what PR-1's own derivation exists to prevent: the stock
    ``KISToken`` cache keys on the domain alone, so two different app keys
    would share one token file and a reissue for one would hand the other a
    token its key never minted. ``secret_fingerprint`` is irreversible, so the
    path names the key without carrying it.
    """
    creds = resolve_credentials("futures", is_real=True)
    return Quotes(
        creds,
        log,
        config.transport,
        token_cache=config.token_cache_dir / secret_fingerprint(creds.app_key),
    )


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
