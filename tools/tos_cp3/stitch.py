"""The cross-contract (month-stitch) seed manifest — plan §3.2a.

A roll leaves the new front month with too few dense sessions to fill Setup D's
causal ``vol_window_bars`` (measured: 0 / 780 on 2026-10-12, plan §6.2), so the
seed's older sessions come from the PREVIOUS contract and are joined to the new
one by a Panama **difference** back-adjust. This module owns the one artifact
that makes that join reproducible — ``stitch.json`` — and the one alignment
function every reader uses.

**Why a manifest and not a flag.** B3 (``tools/tos_cp3/diff_decisions.py``)
refuses a (B1a, B2) pair whose input digests, line counts or ``raw_event_id``
order differ. B2 reads its frame through
``produce_fields.load_window``, so an alignment that lived only in a B1a flag
would make every stitched session an automatic B3 refusal (plan §9 HIGH-1).
The manifest is therefore the input to ``load_window`` itself, and the producer,
B1a and B2 all align through :func:`segment_offsets_x100` — one implementation,
no equivalence proof needed between three of them.

**What the manifest says, and what it deliberately does not.**

* Segments: ``(contract, [trading days])``, oldest first. A reader loads
  EXACTLY those pairs — never a date-range glob — so a sibling ``code=``
  partition in the same tree can never leak into the frame.
* Junctions: at most one (plan §3.2a 「접합 지점은 **최대 하나**」), carrying the
  splice day, the last common PARSED minute, both unadjusted closes and the
  integer ``c_x100 = P_new - P_old``.
* ``c`` is an integer in 1/100 units because the mini contract's tick is 0.02
  (PR #881) and a float difference does not land on that grid (plan §9 LOW-2).
* The splice day's NEW-contract bars are stored under their own contract's
  partition and are read back ONLY to recompute ``c_x100``. They are not part
  of the frame: two contracts' bars for one minute would hit B1a's duplicate
  timestamp refusal (plan §3.2a, re-review N-3).

Nothing here names a contract, a date or a price: every value comes from the
manifest the producer wrote, and the producer got them from
``shared/instruments/futures.py::get_front_month_code`` and the broker's own
rows.

Firewall: legacy side (``tools/``). No ``tos`` / ``tos_runtime`` import.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

#: The file name, and the place it sits: directly under the ``--data-root``
#: B1a and B2 are given, i.e. ``<session dir>/market/`` (plan §3.6's layout,
#: re-review N-2 — an earlier draft put it one level up, where B1a's own
#: ``--data-root`` check could never see it).
STITCH_FILENAME = "stitch.json"

#: Bumped when the on-disk shape changes. A reader refuses an unknown version
#: rather than guessing which keys it still understands.
STITCH_SCHEMA_VERSION = 1

#: The only alignment this manifest can declare. A ratio back-adjust would not
#: leave Setup D's state invariant (its windows are price DIFFERENCES), so the
#: value is pinned rather than offered as a choice.
STITCH_METHOD = "difference"

#: Price scale of ``c_x100`` and the two stored closes. Mirrors
#: ``produce_fields.PRICE_SCALE``; restated here so this module does not import
#: B1a (B1a imports this one).
PRICE_SCALE = 100

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class StitchError(RuntimeError):
    """The manifest is absent, malformed, or contradicts what was read."""


@dataclass(frozen=True)
class StitchSegment:
    """One contiguous run of trading days taken from ONE contract."""

    contract: str
    days: tuple[date, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "days": [day.isoformat() for day in self.days],
        }


@dataclass(frozen=True)
class StitchJunction:
    """The splice between two adjacent segments, and the constant it yields."""

    day: date
    common_minute: datetime
    old_contract: str
    new_contract: str
    old_close_x100: int
    new_close_x100: int
    c_x100: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "day": self.day.isoformat(),
            "common_minute": self.common_minute.isoformat(),
            "old_contract": self.old_contract,
            "new_contract": self.new_contract,
            "old_close_x100": self.old_close_x100,
            "new_close_x100": self.new_close_x100,
            "c_x100": self.c_x100,
        }


@dataclass(frozen=True)
class StitchManifest:
    """``stitch.json``'s content, plus the digest of the bytes it came from.

    ``sha256`` is the digest of the rendered file, which is what B3 compares
    through the window identity. It is ``None`` only for a manifest that has
    been built but not yet rendered.
    """

    symbol: str
    segments: tuple[StitchSegment, ...]
    junctions: tuple[StitchJunction, ...]
    source_sha256: Mapping[str, str]
    method: str = STITCH_METHOD
    schema_version: int = STITCH_SCHEMA_VERSION
    sha256: str | None = None
    path: Path | None = None

    @property
    def target_days(self) -> frozenset[date]:
        """Days whose bars carry the TARGET contract's own identity.

        B1a and B2 emit records only for these (plan §3.2a 「대상 종목이 아닌
        구간의 레코드를 출력하지 않는다」): stamping a previous-month bar with a
        ``raw_event_id`` naming this symbol is the very label error §3.2a's
        "라벨은 진실하게" rule exists to prevent.
        """
        return frozenset(
            day
            for segment in self.segments
            if segment.contract == self.symbol
            for day in segment.days
        )

    @property
    def all_days(self) -> tuple[date, ...]:
        return tuple(sorted(day for s in self.segments for day in s.days))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "symbol": self.symbol,
            "method": self.method,
            "segments": [segment.to_payload() for segment in self.segments],
            "junctions": [junction.to_payload() for junction in self.junctions],
            "source_sha256": dict(sorted(self.source_sha256.items())),
        }


def segment_offsets_x100(manifest: StitchManifest) -> dict[str, int]:
    """``contract -> the constant added to its OHLC``, in 1/100 price units.

    The newest segment — the target contract — is the reference and gets 0;
    every older segment gets the cumulative ``c_x100`` of the junctions between
    it and the target. With the at-most-one-junction rule this is simply
    ``{old: c_x100, new: 0}``, but the loop is written generally so that a
    future two-junction allowance cannot silently produce a wrong constant.
    """
    offsets: dict[str, int] = {manifest.segments[-1].contract: 0}
    running = 0
    for index in range(len(manifest.segments) - 2, -1, -1):
        running += manifest.junctions[index].c_x100
        offsets[manifest.segments[index].contract] = running
    return offsets


def shift_price_x100(value: float, offset_x100: int) -> float:
    """Add *offset_x100* to a price, on the 1/100 grid rather than in floats.

    Quantise first, add integers, divide once — so the result is exactly the
    grid point ``produce_fields.scaled_int_half_up`` would name for it.

    ⚠ **What this is and is not worth** (measured in
    ``tests/tools/test_cp3_stitch_seed.py::test_shift_price_x100_lands_on_the_
    grid_half_up_names``). On a price that is already on the 1/100 grid — every
    price this repo's ``parse_ohlcv`` produces from a KIS response — the naive
    ``value + offset_x100 / 100`` gives the SAME published integer, so the
    claim is NOT "this prevents an off-by-one on broker data". It prevents one
    on a value BETWEEN grid points: ``400.025`` shifted by one mini tick
    (``offset_x100 = 2``) publishes 40005 here and 40004 naively. Keeping the
    arithmetic exact costs nothing and means the shift never has to be
    re-reasoned about if a future input is not already quantised; it is not
    load-bearing for the current data.
    """
    if offset_x100 == 0:
        return float(value)
    return (int(math.floor(float(value) * PRICE_SCALE + 0.5)) + offset_x100) / float(
        PRICE_SCALE
    )


def close_x100_by_minute(bars: Iterable[Sequence[Any]]) -> dict[datetime, int]:
    """``minute -> close_x100`` for ``parse_ohlcv`` tuples.

    PARSED bars, never raw rows: the producer and the offline recomputation
    must pick the same minute, and a raw-row rule picks a different one
    whenever the last shared minute traded below ``KIS_MINUTE_BAR_MIN_VOLUME``
    on one leg only (plan §3.2a re-review N-3).
    """
    return {bar[1]: int(math.floor(float(bar[5]) * PRICE_SCALE + 0.5)) for bar in bars}


def derive_junction(
    *,
    day: date,
    old_contract: str,
    new_contract: str,
    old_bars: Iterable[Sequence[Any]],
    new_bars: Iterable[Sequence[Any]],
) -> StitchJunction:
    """``c_x100`` from the LAST minute both contracts have a parsed bar for.

    Not each leg's own last close: the expiring month stops trading before the
    successor does (measured 2026-10-08 — 15:19 against 15:45, evidence
    ``docs/broker-profiles/evidence/2026-10-14-cp3-pr2b-expired-contract``
    §4), so "each leg's last bar" would difference two different instants and
    fold a 26-minute price move into the constant.

    Raises:
        StitchError: the two contracts share no parsed minute on *day*. The
            constant is not invented — the producer refuses to start.
    """
    old = close_x100_by_minute(old_bars)
    new = close_x100_by_minute(new_bars)
    common = sorted(set(old) & set(new))
    if not common:
        raise StitchError(
            f"{old_contract} and {new_contract} share no parsed minute on "
            f"{day}: the back-adjust constant would have to be invented. Plan "
            "§3.2a 「공통 분이 없으면 기동 거부(값을 지어내지 않는다)」"
        )
    minute = common[-1]
    return StitchJunction(
        day=day,
        common_minute=minute,
        old_contract=old_contract,
        new_contract=new_contract,
        old_close_x100=old[minute],
        new_close_x100=new[minute],
        c_x100=new[minute] - old[minute],
    )


def build_manifest(
    *,
    symbol: str,
    segments: Sequence[StitchSegment],
    junctions: Sequence[StitchJunction],
    source_sha256: Mapping[str, str],
) -> StitchManifest:
    """Assemble and validate a manifest before it is written."""
    manifest = StitchManifest(
        symbol=symbol,
        segments=tuple(segments),
        junctions=tuple(junctions),
        source_sha256=dict(source_sha256),
    )
    _validate(manifest)
    return manifest


def render_manifest(manifest: StitchManifest) -> bytes:
    """The file's bytes. Stable: two identical manifests render identically."""
    return (
        json.dumps(manifest.to_payload(), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def write_manifest(path: Path, manifest: StitchManifest) -> StitchManifest:
    """Render *manifest* to *path* and return it carrying its own digest."""
    payload = render_manifest(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return StitchManifest(
        symbol=manifest.symbol,
        segments=manifest.segments,
        junctions=manifest.junctions,
        source_sha256=manifest.source_sha256,
        method=manifest.method,
        schema_version=manifest.schema_version,
        sha256=hashlib.sha256(payload).hexdigest(),
        path=path,
    )


def load_manifest(path: Path) -> StitchManifest:
    """Read and validate ``stitch.json``, carrying the digest of its bytes."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise StitchError(f"{path}: cannot be read ({exc})") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StitchError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise StitchError(f"{path}: not a JSON object")
    manifest = StitchManifest(
        symbol=_require_str(data, "symbol", path),
        segments=_read_segments(data, path),
        junctions=_read_junctions(data, path),
        source_sha256=_read_source_sha256(data, path),
        method=_require_str(data, "method", path),
        schema_version=_require_int(data, "schema_version", path),
        sha256=hashlib.sha256(raw).hexdigest(),
        path=path,
    )
    _validate(manifest)
    return manifest


def rows_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    """sha256 over a broker response's rows, canonicalised.

    What ``source_sha256`` records: the bytes the seed day's bars were parsed
    from. The raw responses themselves are too large to commit (PR-1's one
    session was 14 MB), so the manifest carries their fingerprint instead.
    """
    canonical = json.dumps(
        [dict(sorted(row.items())) for row in rows],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Validation and parsing helpers
# ---------------------------------------------------------------------------


def _require_str(data: dict[str, Any], key: str, path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise StitchError(f"{path}: {key!r} must be a non-empty string")
    return value


def _require_int(data: dict[str, Any], key: str, path: Path) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise StitchError(f"{path}: {key!r} must be an int")
    return value


def _read_segments(data: dict[str, Any], path: Path) -> tuple[StitchSegment, ...]:
    entries = data.get("segments")
    if not isinstance(entries, list) or not entries:
        raise StitchError(f"{path}: 'segments' must be a non-empty list")
    segments: list[StitchSegment] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise StitchError(f"{path}: a segment is not an object")
        days = entry.get("days")
        if not isinstance(days, list) or not days:
            raise StitchError(f"{path}: a segment has no days")
        segments.append(
            StitchSegment(
                contract=_require_str(entry, "contract", path),
                days=tuple(date.fromisoformat(str(day)) for day in days),
            )
        )
    return tuple(segments)


def _read_junctions(data: dict[str, Any], path: Path) -> tuple[StitchJunction, ...]:
    entries = data.get("junctions")
    if not isinstance(entries, list):
        raise StitchError(f"{path}: 'junctions' must be a list (possibly empty)")
    junctions: list[StitchJunction] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise StitchError(f"{path}: a junction is not an object")
        junctions.append(
            StitchJunction(
                day=date.fromisoformat(_require_str(entry, "day", path)),
                common_minute=datetime.fromisoformat(
                    _require_str(entry, "common_minute", path)
                ),
                old_contract=_require_str(entry, "old_contract", path),
                new_contract=_require_str(entry, "new_contract", path),
                old_close_x100=_require_int(entry, "old_close_x100", path),
                new_close_x100=_require_int(entry, "new_close_x100", path),
                c_x100=_require_int(entry, "c_x100", path),
            )
        )
    return tuple(junctions)


def _read_source_sha256(data: dict[str, Any], path: Path) -> dict[str, str]:
    entries = data.get("source_sha256")
    if not isinstance(entries, dict) or not entries:
        raise StitchError(
            f"{path}: 'source_sha256' must be a non-empty mapping — a manifest "
            "that does not say what it was derived from cannot be re-derived"
        )
    for key, value in entries.items():
        if not isinstance(value, str) or not _SHA256_RE.match(value):
            raise StitchError(f"{path}: source_sha256[{key!r}] is not a sha256")
    return {str(key): str(value) for key, value in entries.items()}


def _validate(manifest: StitchManifest) -> None:
    """Every structural rule plan §3.2a states, checked in one place."""
    where = manifest.path or "<manifest>"
    if manifest.schema_version != STITCH_SCHEMA_VERSION:
        raise StitchError(
            f"{where}: schema_version {manifest.schema_version} is not the "
            f"{STITCH_SCHEMA_VERSION} this reader understands"
        )
    if manifest.method != STITCH_METHOD:
        raise StitchError(
            f"{where}: method {manifest.method!r} is not {STITCH_METHOD!r}; a "
            "ratio adjust does not leave Setup D's price-difference windows "
            "invariant, so it is not an option this manifest can declare"
        )
    _validate_segments(manifest, where)
    _validate_junctions(manifest, where)


def _validate_segments(manifest: StitchManifest, where: Any) -> None:
    contracts = [segment.contract for segment in manifest.segments]
    if len(set(contracts)) != len(contracts):
        raise StitchError(f"{where}: a contract appears in two segments")
    if contracts[-1] != manifest.symbol:
        raise StitchError(
            f"{where}: the newest segment is {contracts[-1]!r} but the target "
            f"symbol is {manifest.symbol!r}; the target's own bars must be the "
            "last segment, since every older one is back-adjusted ONTO it"
        )
    if contracts.count(manifest.symbol) != 1:
        raise StitchError(f"{where}: {manifest.symbol!r} appears in two segments")
    previous: date | None = None
    for segment in manifest.segments:
        if list(segment.days) != sorted(set(segment.days)):
            raise StitchError(
                f"{where}: segment {segment.contract} days are not strictly "
                "increasing"
            )
        if previous is not None and segment.days[0] <= previous:
            raise StitchError(
                f"{where}: segment {segment.contract} starts at "
                f"{segment.days[0]} which is not after the previous segment's "
                f"last day {previous}; segments must not interleave"
            )
        previous = segment.days[-1]


def _validate_junctions(manifest: StitchManifest, where: Any) -> None:
    expected = len(manifest.segments) - 1
    if len(manifest.junctions) != expected:
        raise StitchError(
            f"{where}: {len(manifest.segments)} segment(s) need {expected} "
            f"junction(s), not {len(manifest.junctions)}"
        )
    if expected > 1:
        raise StitchError(
            f"{where}: {expected} junctions. Plan §3.2a allows at most ONE "
            "splice in a seed window — two means the window spans a whole "
            "contract month, which is not a seed this producer may assemble"
        )
    for index, junction in enumerate(manifest.junctions):
        older, newer = manifest.segments[index], manifest.segments[index + 1]
        if (junction.old_contract, junction.new_contract) != (
            older.contract,
            newer.contract,
        ):
            raise StitchError(
                f"{where}: junction {index} joins "
                f"{junction.old_contract}->{junction.new_contract} but sits "
                f"between {older.contract} and {newer.contract}"
            )
        if junction.day != older.days[-1]:
            raise StitchError(
                f"{where}: junction day {junction.day} is not the last day "
                f"{older.days[-1]} the walk assigned to {older.contract}. Plan "
                "§3.2a LOW-1: the splice day is the walk's own last "
                "previous-month seed day, never a recomputed expiry"
            )
        if junction.common_minute.date() != junction.day:
            raise StitchError(
                f"{where}: junction common_minute {junction.common_minute} is "
                f"not on the junction day {junction.day}"
            )
        if junction.c_x100 != junction.new_close_x100 - junction.old_close_x100:
            raise StitchError(
                f"{where}: c_x100 {junction.c_x100} != new_close_x100 "
                f"{junction.new_close_x100} - old_close_x100 "
                f"{junction.old_close_x100}"
            )


def assert_recomputed(
    manifest: StitchManifest, recomputed: Sequence[StitchJunction]
) -> None:
    """Refuse when a re-derived junction disagrees with the manifest.

    Plan §3.2a MEDIUM-3: without this, a producer that computed the wrong
    ``c`` has its mistake reproduced byte for byte by the offline run reading
    the same manifest, and the pair passes B3 while describing a frame nobody
    would accept. The offline side therefore re-reads the splice day's two
    UNADJUSTED partitions and recomputes rather than trusting the number.
    """
    if len(recomputed) != len(manifest.junctions):
        raise StitchError(
            f"recomputed {len(recomputed)} junction(s) from the partitions but "
            f"the manifest declares {len(manifest.junctions)}"
        )
    for declared, actual in zip(manifest.junctions, recomputed):
        differing = {
            key: (getattr(declared, key), getattr(actual, key))
            for key in (
                "day",
                "common_minute",
                "old_close_x100",
                "new_close_x100",
                "c_x100",
            )
            if getattr(declared, key) != getattr(actual, key)
        }
        if differing:
            raise StitchError(
                "the junction recomputed from the stored bars disagrees with "
                "the manifest: "
                + "; ".join(
                    f"{key} manifest={a!r} recomputed={b!r}"
                    for key, (a, b) in differing.items()
                )
                + ". A wrong c reproduced on both sides would pass B3 while "
                "describing a frame nobody would accept (plan §3.2a MEDIUM-3)"
            )
