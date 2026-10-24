"""③ itself: the thin outer loop, and the CLI that starts it.

Plan §3.5 splits the producer in two on purpose — a pure function that turns a
frame into one journal row, and a loop that does HTTP and file replacement —
so the field computation is testable without a clock or a socket. Since PR
#904's review that split is also a FILE split: the pure half is
:mod:`~tools.tos_cp3.live_producer.line`, the give-ups are
:mod:`~tools.tos_cp3.live_producer.halt_policy`, and the seed's own report is
:mod:`~tools.tos_cp3.live_producer.seed_lineage`. ``build_line`` is imported
back into this module's namespace, so a test that monkeypatches
``producer.build_line`` still reaches the call site below.

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
from tools.broker_probes.common import SafetyViolation  # noqa: E402
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
)
from tools.tos_cp3.live_producer.halt_policy import (  # noqa: E402
    STAGE_FETCH_ERROR_MINUTE,
    assert_the_session_can_still_happen,
    assert_worth_continuing,
    next_fetch_error_minutes,
)
from tools.tos_cp3.live_producer.line import (  # noqa: E402
    SOURCE_ID,
    build_line,
)
from tools.tos_cp3.live_producer.real_quotes import real_quotes  # noqa: E402
from tools.tos_cp3.live_producer.seed_lineage import seed_lineage  # noqa: E402
from tools.tos_cp3.live_producer.session_log import (  # noqa: E402
    STAGE_ALREADY_FROZEN,
    Counters,
    EventLog,
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
    derive_raw_event_id,
    load_strategy_inputs,
    resolve_contract_spec,
    resolve_open_anchor,
)
from tools.tos_cp3.quote_client import KST, QUOTE_ROUTES  # noqa: E402
from tools.tos_cp3.stitch import (  # noqa: E402
    STITCH_FILENAME,
    StitchManifest,
    rows_digest,
    write_manifest,
)


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
    #: Consecutive boundaries that POLLED and got nothing back from any poll —
    #: plan §3.5's fetch give-up (``max_consecutive_fetch_error_minutes``). A
    #: boundary the frame had already settled polls nothing, so it neither
    #: increments nor resets this: no feed information was gathered.
    consecutive_fetch_error_minutes: int = 0
    #: Every minute a journal line was actually WRITTEN for. A minute enters
    #: this set AFTER the write, never before: a bar that ended in
    #: ``omitted_unusable``, ``produce_error`` or a refused stamp was not
    #: published and must not silence its own boundary (review N1, and PR #898
    #: round-3 review I2 which pins that order with its own test).
    published_minutes: set[datetime] = field(default_factory=set)

    def __post_init__(self) -> None:
        # The log exists before anything can refuse, so a refusal is recorded
        # in the session directory rather than only on the runner's stderr.
        self.log = EventLog(self.session_dir)

    @property
    def last_published_minute(self) -> datetime | None:
        """The newest minute a journal line was written for, or ``None``.

        Derived from :attr:`published_minutes` rather than tracked beside it:
        two pieces of state advanced by hand on the same line are two places
        the publication rule lives, and this one is read by the boundary
        short-circuit below.
        """
        return max(self.published_minutes, default=None)

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
            self.market_root,
            asset_class=self.config.asset_class,
            symbol=self.instrument,
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
        # The TARGET day's window: a dated override (issue #924, e.g. the exam
        # day's late open/close) moves the first boundary and the session end.
        self.window = self.calendar.window(
            self.config.calendar_session_id,
            self.config.calendar_session_phase,
            self.target,
        )
        assert_the_session_can_still_happen(
            first_boundary=self._first_boundary(),
            window=self.window,
            target=self.target,
        )
        self.strategy = load_strategy_inputs(self.config.strategy_yaml)
        self.anchor = resolve_open_anchor(
            cli_value=self.config.open_anchor,
            first_session=self.target,
            last_session=self.target,
        )
        # Against the REGULAR window: the anchor counts the whole seed frame,
        # whose days opened at the regular time, so a dated override moves the
        # session window and not the anchor (issue #924).
        regular = self.calendar.window(
            self.config.calendar_session_id, self.config.calendar_session_phase
        )
        if self.config.open_anchor != "auto" and self.anchor.kst != (
            regular.start.strftime("%H:%M")
        ):
            raise LiveProducerRefused(
                f"open_anchor {self.anchor.kst} != the calendar's "
                f"{self.config.calendar_session_id} start {regular.start}"
            )
        registry = ContractSpecRegistry.from_yaml(
            str(self.config.execution_yaml), block=self.config.contract_spec_block
        )
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
        rows: list[dict] = self.quotes.history(contract, day)
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
                asset_class=self.config.asset_class,
                symbol=entry.contract,
                bars=entry.bars,
            )
        if self.assembler.junction_new_bars:
            append_bar_part(
                self.market_root,
                asset_class=self.config.asset_class,
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
            cli_value=self.config.open_anchor,
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
        return seed_lineage(
            instrument=self.instrument,
            target=self.target,
            calendar=self.calendar,
            window=self.window,
            seed=self.seed,
            config=self.config,
            manifest=self.manifest,
            assembler=self.assembler,
            market_root=self.market_root,
            source_id=SOURCE_ID,
        )

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
        """Walk minute boundaries to the session end, one decision each.

        Two give-ups, both plan §3.5, both checked after every boundary. They
        are separate counters because they are separate failures: the first is
        a bar this producer cannot BUILD, the second is a feed that is not
        answering at all (PR #904 review round 1 item A.1 — the first one
        counts only ``ProduceFieldsError`` and so could not see a dead feed).

        ⚠ The late-boot refusal is asked AGAIN here, on the boundary this loop
        will actually use (review round 2 LOW 3). ``boot()`` asks it too, but
        on an earlier clock reading — and the seed walk between the two is
        tens of paginated GETs, so it can carry the clock past the close by
        itself. Measured by the reviewer: a boot at 09:18:30 against a 09:21
        end, a seed that advanced the clock to 09:23, and a loop that then ran
        ZERO iterations and returned 0. Both calls are kept and neither is
        redundant: ``boot()``'s saves the seed walk a session cannot use, and
        this one is the one that actually guarantees the loop runs.
        """
        boundary = self._first_boundary()
        assert_the_session_can_still_happen(
            first_boundary=boundary, window=self.window, target=self.target
        )
        end = self.window.end_boundary(self.target)
        while boundary <= end:
            self._handle_boundary(boundary)
            assert_worth_continuing(
                consecutive_produce_errors=self.consecutive_produce_errors,
                max_consecutive_produce_errors=(
                    self.config.max_consecutive_produce_errors
                ),
                consecutive_fetch_error_minutes=self.consecutive_fetch_error_minutes,
                max_consecutive_fetch_error_minutes=(
                    self.config.max_consecutive_fetch_error_minutes
                ),
                fetch_error_total=self.counters.fetch_error,
                published_total=self.counters.published,
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
        if self._boundary_already_settled(boundary, bar_minute):
            return
        self._sleep_until(boundary + timedelta(seconds=self.config.first_poll_delay_s))
        deadline = boundary + timedelta(
            seconds=self.config.missing_no_successor_timeout_s
        )
        raw_minutes: frozenset[datetime] = frozenset()
        polled_ok = False
        while True:
            try:
                step, received_ms = self._poll()
            except SafetyViolation:
                # BEFORE the RuntimeError clause, because `SafetyViolation` IS
                # a RuntimeError (`ProbeError` -> `RuntimeError`). Without this
                # the allowlist gate refusing a PRICE call was counted as a
                # transport error and the session carried on — a pre-existing
                # hole of the same shape as the band path's was (PR #906
                # review round 1, MEDIUM-1): `SafetyViolation` subclasses
                # `ProbeError` subclasses `RuntimeError`, so the clause below
                # swallowed the allowlist gate's refusal and counted it as a
                # transport blip. `band_probe` carries the same clause for the
                # same reason. THIS is the one band-era change the minute loop
                # keeps; everything else about the band left this module when
                # the GET became its own process (band plan v3).
                raise
            except RuntimeError as exc:
                self.counters.fetch_error += 1
                self.log.event(
                    {"stage": "fetch_error", "boundary": str(boundary), "why": str(exc)}
                )
                step, received_ms = None, None
            if step is not None:
                polled_ok = True
                raw_minutes |= step.raw_minutes
                current = self._freeze(step, bar_minute=bar_minute)
                if current is not None:
                    self._publish_bar(current, received_ms=received_ms)
                    self._record_feed_health(boundary, polled_ok=True)
                    return
            if self._now_naive() >= deadline:
                self._record_unpublished(boundary, bar_minute, raw_minutes)
                self._record_feed_health(boundary, polled_ok=polled_ok)
                return
            self.clock.sleep(self.config.repoll_pace_s)

    def _record_feed_health(self, boundary: datetime, *, polled_ok: bool) -> None:
        """This boundary's verdict on the FEED (see :mod:`halt_policy`).

        Only boundaries that actually polled reach here — one the frame had
        already settled gathered no feed information, so it must neither
        increment the run nor reset it.
        """
        self.consecutive_fetch_error_minutes = next_fetch_error_minutes(
            self.consecutive_fetch_error_minutes, polled_ok=polled_ok
        )
        if not polled_ok:
            self.log.event(
                {
                    "stage": STAGE_FETCH_ERROR_MINUTE,
                    "boundary": str(boundary),
                    "consecutive": self.consecutive_fetch_error_minutes,
                }
            )

    def _boundary_already_settled(
        self, boundary: datetime, bar_minute: datetime
    ) -> bool:
        """Is there nothing left for THIS boundary to poll for?

        The question is about the FRAME, not about the last publication (PR
        #898 round-3 review I1/I2). ``freeze_step`` only ever returns bars
        strictly after the last frozen minute, so once the frame has moved past
        ``bar_minute`` no later poll can produce it. Three settled shapes, and
        each is logged as what it actually is:

        * the bar is in the frame and WAS published — an earlier boundary's
          catch-up covered it (review N1); ``already_published``.
        * the bar is in the frame and was NOT published — ``omitted_unusable``,
          ``produce_error``, a refused stamp or ``skipped_behind`` already
          counted it when it happened, so this boundary logs
          :data:`STAGE_ALREADY_FROZEN` and counts nothing. The first cut polled
          the full G here and then logged ``missing_no_successor`` with
          ``bar_minute_traded: true`` — "the minute traded but never completed"
          about a bar sitting completed in the frame (review I2).
        * the frame moved past the minute WITHOUT it — the minute left no bar
          at all, so the honest reason is :meth:`_record_unpublished`'s
          ``no_raw_row_for_minute``. The first cut answered
          ``already_published`` for it, because it compared against the last
          published minute alone: a catch-up that published m+2 made the m+1
          boundary claim m+1 had been published, for a minute that never
          existed (review I1).

        Returning at once keeps the loop's phase: the next boundary's first
        poll still lands at its own ``+δ``.
        """
        last_frozen = self.frozen[-1][1] if self.frozen else None
        if last_frozen is None or bar_minute > last_frozen:
            return False
        if not self._is_frozen(bar_minute):
            self._record_unpublished(boundary, bar_minute, frozenset())
            return True
        published = bar_minute in self.published_minutes
        if published:
            self.counters.already_published += 1
        self.log.event(
            {
                "stage": "already_published" if published else STAGE_ALREADY_FROZEN,
                "boundary": str(boundary),
                "bar": str(bar_minute),
                "raw_event_id": self._raw_event_id(bar_minute),
                "last_published_minute": str(self.last_published_minute),
                "last_frozen_minute": str(last_frozen),
            }
        )
        return True

    def _is_frozen(self, bar_minute: datetime) -> bool:
        """Is *bar_minute* a bar of the frozen frame?

        A scan, not a second index: the frame holds one session (≈420 bars) and
        this runs once a minute, so a mirror set would buy nothing and could
        drift from :attr:`frozen`, which is the frame B1a actually reads.
        """
        return any(bar[1] == bar_minute for bar in self.frozen)

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
                "raw_event_id": self._raw_event_id(bar_minute),
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
            asset_class=self.config.asset_class,
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
                        "raw_event_id": self._raw_event_id(bar[1]),
                        "current_boundary_bar": str(bar_minute),
                        "frozen_into_frame": True,
                        "published": False,
                    }
                )
            else:
                self.counters.skipped_behind += 1
                self.log.event(
                    {
                        "stage": "skipped_behind",
                        "bar": str(bar[1]),
                        "raw_event_id": self._raw_event_id(bar[1]),
                    }
                )
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
                {
                    "stage": "produce_error",
                    "bar": str(bar[1]),
                    "raw_event_id": self._raw_event_id(bar[1]),
                    "why": str(exc),
                }
            )
            return
        self.consecutive_produce_errors = 0
        if outcome.row is None:
            self.counters.omitted_unusable += 1
            self.log.event(
                {
                    "stage": outcome.reason,
                    "bar": str(bar[1]),
                    "raw_event_id": self._raw_event_id(bar[1]),
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
                    "raw_event_id": self._raw_event_id(bar[1]),
                    "as_of_ms": result.as_of_ms,
                    "last_as_of_ms": self.journal.last_as_of_ms,
                    "written": False,
                }
            )
            return
        self.counters.published += 1
        # AFTER the write, never before (review I2): the three returns above
        # are bars this boundary did not publish, and a minute recorded here
        # would silence its own boundary for a line that does not exist.
        self.published_minutes.add(bar[1])
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

    def _raw_event_id(self, bar_minute: datetime) -> str:
        """B1a's join key for *bar_minute*, from B1a's own deriver.

        Every per-bar log event carries it, so §3.6's reason map for bars the
        runtime never consumed keys on the exact string B3 joins on. Rebuilding
        the key in the extractor instead would be a second derivation of a join
        key, which is how two keys drift apart.
        """
        return derive_raw_event_id(self.instrument, bar_minute.replace(tzinfo=KST))

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
                    "market": config.market,
                    "tr_id": QUOTE_ROUTES[config.market][0],
                    "path": QUOTE_ROUTES[config.market][1],
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


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI tests
    raise SystemExit(main())
