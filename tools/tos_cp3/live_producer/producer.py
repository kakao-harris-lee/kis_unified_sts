"""③ itself: the thin outer loop, and the CLI that starts it."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.indicators.fields import FieldsDocument  # noqa: E402
from tools.broker_probes.common import SafetyViolation  # noqa: E402
from tools.tos_cp3.live_producer.calendar import (  # noqa: E402
    RuntimeCalendar,
    SessionWindow,
    load_runtime_calendar,
)
from tools.tos_cp3.live_producer.config import (  # noqa: E402
    LiveProducerConfig,
    LiveProducerRefused,
)
from tools.tos_cp3.live_producer.declaration import (  # noqa: E402
    fields_yaml_digest,
    fields_yaml_of,
    load_declaration,
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
    store_unadjusted_seed,
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
from tools.tos_cp3.quote_client import KST  # noqa: E402
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
    tenant_tree: Path
    clock: Clock
    quotes_factory: Callable[[LiveProducerConfig, EventLog], Any]

    calendar: RuntimeCalendar = field(init=False)
    window: SessionWindow = field(init=False)
    strategy: StrategyInputs = field(init=False)
    document: FieldsDocument = field(init=False)
    anchor: OpenAnchor = field(init=False)
    contract_spec: Any = field(init=False)
    seed: Seed = field(init=False)
    assembler: StitchedSeed = field(init=False)
    manifest: StitchManifest = field(init=False)
    quotes: Any = field(init=False)
    journal: ObservationJournal = field(init=False)
    log: EventLog = field(init=False)
    lock: Any = field(init=False, default=None)
    raw_digests: dict[str, str] = field(default_factory=dict)
    frozen: list[Bar] = field(default_factory=list)
    counters: Counters = field(default_factory=Counters)
    consecutive_produce_errors: int = 0
    consecutive_fetch_error_minutes: int = 0
    published_minutes: set[datetime] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.log = EventLog(self.session_dir)

    @property
    def last_published_minute(self) -> datetime | None:
        """The newest minute a journal line was written for, or ``None``."""
        return max(self.published_minutes, default=None)

    def boot(self) -> None:
        """Everything that can refuse, before the first line is written."""
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
        self.document = self._load_declaration()
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
            assembler=self.assembler,
        )
        self._assert_one_anchor()
        self._store_unadjusted_seed()
        self.manifest = self._write_manifest()
        self.log.event({"stage": "seed", **self._seed_lineage()})
        self._boot_today()

    def _fetch_day(self, day: date, contract: str) -> list[dict]:
        """One day's raw rows, fingerprinted for the manifest as they arrive."""
        rows: list[dict] = self.quotes.history(contract, day)
        self.raw_digests[f"{contract}:{day.isoformat()}"] = rows_digest(rows)
        return rows

    def _store_unadjusted_seed(self) -> None:
        """Plan §3.2a 「라벨은 진실하게」 — see :func:`sinks.store_unadjusted_seed`."""
        store_unadjusted_seed(
            self.market_root,
            asset_class=self.config.asset_class,
            instrument=self.instrument,
            kept=self.seed.kept,
            junction_new_bars=self.assembler.junction_new_bars,
        )

    def _write_manifest(self) -> StitchManifest:
        """``<session dir>/market/stitch.json`` — written on EVERY session."""
        manifest = self.assembler.manifest(
            self.seed.kept, source_sha256=dict(self.raw_digests)
        )
        return write_manifest(self.market_root / STITCH_FILENAME, manifest)

    @property
    def market_root(self) -> Path:
        return self.session_dir / "market"

    @property
    def fields_yaml(self) -> Path:
        """The declaration this session publishes from."""
        return fields_yaml_of(self.tenant_tree)

    def _load_declaration(self) -> FieldsDocument:
        """Load and bind the tenant's declaration, or refuse to start."""
        document, record = load_declaration(
            self.tenant_tree, strategy=self.strategy, anchor=self.anchor
        )
        self.log.event(record)
        return document

    @property
    def fields_yaml_sha256(self) -> str:
        """Digest of the declaration's BYTES, as the lineage records it."""
        return fields_yaml_digest(self.fields_yaml)

    def _assert_one_anchor(self) -> None:
        """One anchor for the whole frame, or refuse."""
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
            fields_yaml=self.fields_yaml,
            fields_yaml_sha256=self.fields_yaml_sha256,
            fields_schema=self.document.schema,
            fields_catalog=self.document.catalog,
        )

    def _boot_today(self) -> None:
        """Freeze today's already-complete bars and publish the newest one."""
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
        newest = step.newly_frozen[-1]
        current = self._freeze(step, bar_minute=newest[1], at_boot=True)
        if current is not None:
            self.counters.pre_boot_lines += 1
            self._publish_bar(current, received_ms=received_ms)

    def run_session(self) -> None:
        """Walk minute boundaries to the session end, one decision each."""
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
        """Re-poll until THIS boundary's bar is complete, or until m+G."""
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
        """This boundary's verdict on the FEED (see :mod:`halt_policy`)."""
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
        """Is there nothing left for THIS boundary to poll for?"""
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
        """Is *bar_minute* a bar of the frozen frame?"""
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
        """Does this page fail to reach back to where the frame must continue?"""
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

    def _freeze(
        self, step: FreezeStep, *, bar_minute: datetime | None, at_boot: bool = False
    ) -> Bar | None:
        """Add every completed bar to the frame and Parquet; return the one to publish."""
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
        """The ONE bar of this step to publish: the newest, when it is not stale."""
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
                document=self.document,
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
        result = self.journal.append(outcome.row)
        if not result.written:
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

    def _raw_event_id(self, bar_minute: datetime) -> str:
        """B1a's join key for *bar_minute*, from B1a's own deriver."""
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


from tools.tos_cp3.live_producer.cli import (  # noqa: E402, F401
    build_parser,
    main,
)

if __name__ == "__main__":  # pragma: no cover - exercised through the CLI tests
    raise SystemExit(main())
