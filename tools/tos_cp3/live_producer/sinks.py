"""The two things ③ writes: the observation journal and B3's offline input.

**The journal is replaced whole, every time** (plan §2 3).
``JsonLinesObservationJournal.poll`` re-reads the entire file and refuses the
WHOLE poll on a half-written line — it deliberately has no
trailing-partial-line special case, and its own docstring says the fix belongs
upstream, in the collector. So each append writes every line to a temp file and
``os.replace``s it over the journal. Precedent in this repo:
``tools/tos_cp3/bootproof_journal.py::write_journal`` (#892).

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
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import IO, Any

from tools.tos_cp3.live_producer.config import LiveProducerRefused

#: Mirrors ``shared/storage/market_data_store.py::_BAR_COLUMNS``. Restated so
#: the written part file is readable by that store's duckdb reader without this
#: module importing a private name.
BAR_COLUMNS = ["code", "datetime", "open", "high", "low", "close", "volume"]


def acquire_journal_lock(path: Path) -> IO[str]:
    """Take an exclusive, non-blocking ``flock`` for this journal.

    Two producers on one journal would interleave whole-file replacements and
    each would drop the other's lines (plan §3.5). The lock lives in a sibling
    file because the journal itself is replaced by inode, which would drop a
    lock held on it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = (path.parent / (path.name + ".lock")).open("w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise LiveProducerRefused(
            f"another producer holds {path.name}.lock — two producers on one "
            "journal would each drop the other's lines (plan §3.5)"
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


@dataclass
class ObservationJournal:
    """Append-only content, atomic whole-file writes, monotone ``as_of_ms``."""

    path: Path
    lines: list[str] = field(default_factory=list)
    last_as_of_ms: int | None = None

    def append(self, row: dict[str, Any]) -> float:
        """Add one line and replace the file. Returns the stamp→replace seconds.

        That interval is the only part of the producer inside the tenant's
        800 ms freshness budget (plan §2 2: the network and compute happen
        BEFORE the stamp), so it is what M6 measures.

        Raises:
            LiveProducerRefused: ``as_of_ms`` did not advance. A reader only
                returns rows strictly newer than ``after_as_of_ms``, so a
                non-advancing stamp is a line nothing can ever consume; the
                clock going backwards is a defect and is not corrected here
                (plan §2 5).
        """
        as_of_ms = row["as_of_ms"]
        if self.last_as_of_ms is not None and as_of_ms <= self.last_as_of_ms:
            raise LiveProducerRefused(
                f"as_of_ms {as_of_ms} does not advance past {self.last_as_of_ms}; "
                "refusing the write rather than adjusting the clock (plan §2 5)"
            )
        began = time.perf_counter()
        self.lines.append(json.dumps(row, separators=(",", ":"), ensure_ascii=True))
        tmp = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text("".join(f"{line}\n" for line in self.lines), encoding="utf-8")
        os.replace(tmp, self.path)
        self.last_as_of_ms = as_of_ms
        return time.perf_counter() - began


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
    """
    base = market_root / asset_class / "minute" / f"code={symbol}"
    existing = sorted(base.glob("year=*/month=*/day=*/*.parquet"))
    if existing:
        raise LiveProducerRefused(
            f"{base} already holds {len(existing)} partition file(s), e.g. "
            f"{existing[0].name}. The writes here are append-only, so reusing a "
            "session directory duplicates timestamps and B1a refuses the whole "
            "window. Start a new session directory (plan §3.6)"
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
