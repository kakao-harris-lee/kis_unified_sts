"""The two things ③ writes: the observation journal and B3's offline input.

**The journal is replaced whole, every time** (plan §2 3).
``JsonLinesObservationJournal.poll`` re-reads the entire file and refuses the
WHOLE poll on a half-written line — it deliberately has no
trailing-partial-line special case, and its own docstring says the fix belongs
upstream, in the collector. So each append writes every line to a temp file and
``os.replace``s it over the journal. Precedent in this repo:
``tools/tos_cp3/bootproof_journal.py::write_journal`` (#892).

**The journal takes the stamp, not its caller** (plan §2 1-2; review B1).
:class:`ObservationJournal` reads the clock inside :meth:`~ObservationJournal
.append`, immediately before the temp write, and refuses a row that arrives
with an ``as_of_ms`` already on it. The reason is arithmetic: the tenant tree
declares ``max_age_ms: 800`` for all fifteen fields and ``marketfeed.yaml``
leaves 300 ms of that for the collector, while ``produce_bars`` was measured at
~0.44 s late in a session. A stamp taken before the compute would therefore be
STALE on arrival no matter how fast the write is. The interval inside the
budget — the one M6 reports as
:attr:`AppendOutcome.stamp_to_replace_s` — is exactly "stamp → temp write →
``os.replace``"; the network, the parse and the replay all happen before the
stamp and are decision latency (M2), not freshness.

**The Parquet side is append-only part files** (plan §3.6).
``ParquetMarketDataStore.append_minute_bars`` writes straight to the final
``part-<uuid>.parquet`` name, which is NOT atomic, so this module wraps it:
``.part-<uuid>.tmp`` then ``os.replace``. The temp name deliberately does not
end in ``.parquet`` — B1a's ``discover_input_files`` globs ``*.parquet`` and the
store's own reader uses ``rglob("*.parquet")``, so a half-written file with that
suffix would be READ after a crash (plan §3.6 v4 review L1).

⛔ ``replace_minute_day`` is not used: it ``rmtree``s the day partition and
rewrites it non-atomically, which opens a deletion window every minute — and a
crash in that window is precisely the input loss this arrangement exists to
prevent.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import IO, Any

from tools.tos_cp3.live_producer.config import LiveProducerRefused

#: Mirrors ``shared/storage/market_data_store.py::_BAR_COLUMNS``. Restated so
#: the written part file is readable by that store's duckdb reader without this
#: module importing a private name.
BAR_COLUMNS = ["code", "datetime", "open", "high", "low", "close", "volume"]


def acquire_session_lock(market_root: Path) -> IO[str]:
    """Take an exclusive, non-blocking ``flock`` on the SESSION, before any check.

    Two producers on one session would interleave whole-file journal
    replacements and append duplicate bars into one partition tree, and each
    would drop the other's lines (plan §3.5).

    **Scoped to the session directory, not the journal** (review L5). A
    per-journal lock lets two producers aimed at the same ``--session-dir`` with
    different ``--journal`` paths both pass, and they then both append to the
    same Parquet partitions — the duplicate timestamps B1a's ``_bar_lookup``
    refuses, i.e. the whole session's offline input lost.

    **Taken FIRST, before the partition/journal refusals** (review L5). Those
    refusals read the very state a second producer is about to create, so
    checking before locking is a race: both processes can see an empty tree and
    both proceed. The lock file lives inside the market root and is not a
    ``*.parquet`` file, so neither B1a's glob nor the store's reader sees it.
    """
    market_root.mkdir(parents=True, exist_ok=True)
    handle = (market_root / ".session.lock").open("w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise LiveProducerRefused(
            f"another producer holds the session lock under {market_root} — two "
            "producers on one session would duplicate partitions and drop each "
            "other's journal lines (plan §3.5)"
        ) from exc
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def refuse_if_journal_exists(path: Path) -> None:
    """The producer creates its journal; it never writes into somebody else's.

    Every write replaces the file WHOLE from the lines this process has in
    memory, so starting against an existing journal would silently delete what
    is already there — including the one synthetic ``cp3-bootproof-synthetic``
    row a previous wiring run left, which is also a row the #892 guard would
    have refused to let near a designated durable set. Same reasoning as
    :func:`refuse_if_partitions_exist`: one session directory, used once.
    """
    if path.exists() and path.stat().st_size > 0:
        raise LiveProducerRefused(
            f"{path} already holds {path.stat().st_size} byte(s). Every write "
            "here replaces the file whole, so an existing journal would be "
            "destroyed. Start a new session directory (plan §3.6)"
        )


#: Wire key order of a PRICE journal line, and the default of
#: :attr:`ObservationJournal.key_order`. Fixed so the file is byte-stable and
#: so a reader can diff it against B1a's own ``FieldRecord.to_payload`` order;
#: ``as_of_ms`` sits where B1a puts it even though this writer supplies it.
JOURNAL_KEY_ORDER = (
    "raw_event_id",
    "source_id",
    "instrument",
    "as_of_ms",
    "received_ms",
    "fields",
)


def _wall_clock_ms() -> int:
    return time.time_ns() // 1_000_000


@dataclass(frozen=True)
class AppendOutcome:
    """What one append did, including the M6 interval and any refusal."""

    written: bool
    as_of_ms: int
    #: Stamp → end of ``os.replace``. The ONLY part of the producer inside the
    #: tenant's 800 ms freshness budget, so it is what M6 measures.
    stamp_to_replace_s: float
    reason: str | None = None


@dataclass
class ObservationJournal:
    """Append-only content, atomic whole-file writes, monotone ``as_of_ms``.

    **This object owns the stamp** (review B1). ``as_of_ms`` is read from the
    clock here, immediately before the temp write — not by the caller before it
    computes the fifteen fields. The tenant tree declares ``max_age_ms: 800``
    with 300 ms left for the collector (``marketfeed.yaml``), and the measured
    cost of ``produce_bars`` at the end of a session is ~0.44 s, so a stamp
    taken before the compute would be older than the whole budget by the time
    the line lands. Plan §2 1-2 is explicit that the only interval inside the
    budget is "stamp → temp write → ``os.replace``"; everything before the
    stamp — network, parse, replay — is decision latency (M2), not freshness.
    """

    path: Path
    #: Injected so a test can pin the stamp. Epoch milliseconds.
    clock: Callable[[], int] = _wall_clock_ms
    #: The line's wire key order — an ARGUMENT since the band journal
    #: (band plan §3.2, review LOW-1). The band is a separate file with a
    #: different shape but exactly these semantics (whole-file atomic replace,
    #: the journal owns the stamp, a non-advancing stamp is refused), so it
    #: reuses this class instead of growing a second writer whose atomicity
    #: would need its own proof. ``as_of_ms`` must appear in it, or the stamp
    #: this object exists to own would be dropped on the way to the file.
    key_order: tuple[str, ...] = JOURNAL_KEY_ORDER
    lines: list[str] = field(default_factory=list)
    last_as_of_ms: int | None = None

    def __post_init__(self) -> None:
        if "as_of_ms" not in self.key_order:
            raise LiveProducerRefused(
                f"key_order {self.key_order} has no 'as_of_ms'; this journal "
                "owns the stamp, so a key order without it would write lines "
                "no reader can order or consume"
            )

    def append(self, row: dict[str, Any]) -> AppendOutcome:
        """Stamp *row*, add one line, and replace the file whole.

        Args:
            row: every journal key EXCEPT ``as_of_ms`` — the caller does not
                get to choose the stamp.

        Returns:
            The outcome. ``written=False`` with ``reason="clock_regression"``
            when the stamp did not advance: a reader returns only rows strictly
            newer than ``after_as_of_ms``, so a non-advancing stamp is a line
            nothing can ever consume. Plan §2 5 says to refuse THAT WRITE and
            log it — not to end the session (review L6) and not to adjust the
            clock. The caller counts it and goes on to the next minute.
        """
        if "as_of_ms" in row:
            raise LiveProducerRefused(
                "the caller supplied as_of_ms; the journal owns the stamp so it "
                "can be taken immediately before the replace (plan §2 1-2)"
            )
        missing = [key for key in self.key_order if key != "as_of_ms"]
        absent = [key for key in missing if key not in row]
        if absent:
            raise LiveProducerRefused(f"journal row is missing {absent}")

        as_of_ms = self.clock()
        if self.last_as_of_ms is not None and as_of_ms <= self.last_as_of_ms:
            return AppendOutcome(
                written=False,
                as_of_ms=as_of_ms,
                stamp_to_replace_s=0.0,
                reason="clock_regression",
            )
        began = time.perf_counter()
        stamped = {**row, "as_of_ms": as_of_ms}
        ordered = {key: stamped[key] for key in self.key_order}
        self.lines.append(json.dumps(ordered, separators=(",", ":"), ensure_ascii=True))
        tmp = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text("".join(f"{line}\n" for line in self.lines), encoding="utf-8")
        os.replace(tmp, self.path)
        elapsed = time.perf_counter() - began
        self.last_as_of_ms = as_of_ms
        return AppendOutcome(
            written=True, as_of_ms=as_of_ms, stamp_to_replace_s=elapsed
        )


def partition_dir(
    market_root: Path, *, asset_class: str, symbol: str, day: date
) -> Path:
    """The store's own minute-partition path for one day.

    Mirrors ``ParquetMarketDataStore._partition_dir`` (and B1a's
    ``discover_input_files``, which mirrors the same layout) so B1a run with
    ``--data-root <session dir>/market`` finds exactly these files.
    """
    return (
        market_root
        / asset_class
        / "minute"
        / f"code={symbol}"
        / f"year={day.year}"
        / f"month={day.month:02d}"
        / f"day={day.isoformat()}"
    )


def refuse_if_partitions_exist(
    market_root: Path, *, asset_class: str, symbol: str
) -> None:
    """A session directory is used once (plan §3.6, v4 review L2).

    The writes are append-only, so restarting into the same directory records
    the seed and the already-frozen bars a SECOND time; B1a's ``_bar_lookup``
    then refuses the duplicate timestamps and the whole session's offline input
    is lost. Refusing here turns that into a startup failure the runner reports.

    **Every ``code=`` directory, not just the traded symbol** (plan §3.2a). A
    cross-contract seed writes the previous month's days under that month's own
    partition, and right after a roll those may be the ONLY partitions a boot
    produces — a restart checking the traded symbol alone would find nothing,
    proceed, and duplicate every previous-month seed day. This is a check on
    THIS session directory's own emptiness; it is not the "sibling ``code=``
    means a mixed tree" heuristic plan §9 MEDIUM-1 rejects for B1a, which runs
    against the legacy root where several months always coexist.
    """
    base = market_root / asset_class / "minute"
    existing = sorted(base.glob("code=*/year=*/month=*/day=*/*.parquet"))
    if existing:
        raise LiveProducerRefused(
            f"{base} already holds {len(existing)} partition file(s), e.g. "
            f"{existing[0].relative_to(base)} (this session trades {symbol}). "
            "The writes here are append-only, so reusing a session directory "
            "duplicates timestamps and B1a refuses the whole window. Start a "
            "new session directory (plan §3.6)"
        )


def append_bar_part(
    market_root: Path,
    *,
    asset_class: str,
    symbol: str,
    bars: Sequence[tuple],
) -> tuple[Path, ...]:
    """Write *bars* as one new part file per day, atomically.

    Args:
        bars: ``parse_ohlcv`` tuples
            ``(code, naive-KST minute, open, high, low, close, volume)``.

    Returns:
        The final ``part-<uuid>.parquet`` paths, one per day touched.
    """
    import pandas as pd

    if not bars:
        return ()
    by_day: dict[date, list[tuple]] = {}
    for bar in bars:
        by_day.setdefault(bar[1].date(), []).append(bar)

    written: list[Path] = []
    for day, day_bars in sorted(by_day.items()):
        directory = partition_dir(
            market_root, asset_class=asset_class, symbol=symbol, day=day
        )
        directory.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        frame = pd.DataFrame(
            [
                {
                    "code": bar[0],
                    "datetime": pd.Timestamp(bar[1]),
                    "open": float(bar[2]),
                    "high": float(bar[3]),
                    "low": float(bar[4]),
                    "close": float(bar[5]),
                    "volume": int(bar[6]),
                }
                for bar in day_bars
            ]
        )[BAR_COLUMNS]
        # NOT "*.parquet": a crash between write and replace must leave a file
        # that neither B1a's glob nor the store's rglob picks up.
        tmp = directory / f".part-{token}.tmp"
        frame.to_parquet(tmp, index=False)
        final = directory / f"part-{token}.parquet"
        os.replace(tmp, final)
        written.append(final)
    return tuple(written)


def market_digest(market_root: Path) -> dict[str, str]:
    """sha256 of every written part file, keyed by its path under *market_root*.

    Written at session end (plan §3.6): the frozen frame is B3's only admissible
    offline input, so its bytes are fingerprinted where the evidence can cite
    them.
    """
    return {
        str(path.relative_to(market_root)): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(market_root.rglob("*.parquet"))
    }
