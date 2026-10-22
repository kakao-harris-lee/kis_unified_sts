"""The cross-contract seed assembler — plan §3.2a, producer side.

``build_seed`` walks trading days backwards and asks ONE callable two things:
which contract to request day *d* on, and how the kept days become a frame
(:data:`~tools.tos_cp3.live_producer.frame.SeedAssembler`). PR-2 answered both
with :func:`~tools.tos_cp3.live_producer.frame.same_contract_seed`, whose
measured consequence is a post-roll blackout of at least three trading days
(plan §6.2: 0 / 780 capacity on 2026-10-12). This module is the operator's
chosen disposition (2026-10-14): the same walk, but each day is requested on
**that day's own front month** and the previous month's bars are joined to the
new one by a Panama difference back-adjust.

What changes and what does not:

* **Day → contract** is ``get_front_month_code(product=…, target_date=d)`` —
  the very function that names today's instrument, not a second roll rule.
* **The density gate** is still B1a's, applied to ``(d, that day's contract)``.
* **The splice day** is the last seed day the WALK assigned to the previous
  month; ``get_expiry_date`` is deliberately not re-run, because it has no
  holiday correction and would name a closed Thursday in a month whose second
  Thursday is a holiday (plan §9 LOW-1).
* **The frame** carries the previous month's OHLC shifted by the integer
  ``c_x100``; volume is untouched.
* **What is stored** is unadjusted. The adjust happens on READ, through
  ``produce_fields.load_window(stitch_manifest=…)``, which is also what B1a and
  B2 call — one alignment implementation, not three (plan §9 HIGH-1).

What this does NOT remove: the previous month's ATR values still stand in for
the new month's while the vol window fills, and the spread moves between the
splice minute and the sessions that use it. Those two residues are measured as
S1a and S1b, not asserted away (plan §3.2a 「정렬이 무엇을 지우는가, 무엇을
남기는가」).

Firewall: legacy side. ``shared.*`` is allowed, ``tos`` / ``tos_runtime`` is not.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from shared.instruments.futures import get_front_month_code
from tools.tos_cp3.live_producer.config import LiveProducerRefused
from tools.tos_cp3.live_producer.frame import Bar, FetchDay, SeedDay
from tools.tos_cp3.minute_probe import frame as bars_to_frame
from tools.tos_cp3.stitch import (
    StitchError,
    StitchJunction,
    StitchManifest,
    StitchSegment,
    build_manifest,
    derive_junction,
    shift_price_x100,
)


def shift_bars(bars: Sequence[Bar], offset_x100: int) -> tuple[Bar, ...]:
    """``parse_ohlcv`` tuples with OHLC moved by *offset_x100*, volume as is."""
    if not offset_x100:
        return tuple(bars)
    return tuple(
        (
            bar[0],
            bar[1],
            shift_price_x100(bar[2], offset_x100),
            shift_price_x100(bar[3], offset_x100),
            shift_price_x100(bar[4], offset_x100),
            shift_price_x100(bar[5], offset_x100),
            bar[6],
        )
        for bar in bars
    )


@dataclass
class StitchedSeed:
    """The seed assembler, carrying everything the manifest needs afterwards.

    Stateful on purpose: the junction's ``c_x100`` needs the splice day's bars
    on BOTH contracts, and the second fetch must happen exactly once however
    many times ``build_seed`` calls this object (it calls it twice per walked
    day — once for the contract, once for the frame).
    """

    instrument: str
    target: date
    #: ``None`` for an instrument that does not roll (a stock symbol): every
    #: day is then requested on *instrument* itself, no junction can arise and
    #: the manifest carries one segment — the same zero-junction manifest a
    #: futures session without a splice writes.
    product: str | None
    fetch_day: FetchDay

    junction: StitchJunction | None = field(default=None, init=False)
    #: The splice day's NEW-contract parsed bars. Stored under that contract's
    #: own partition as the evidence ``c_x100`` is recomputed from, and kept
    #: OUT of the frame — two contracts' bars for one minute would hit B1a's
    #: duplicate-timestamp refusal (plan §3.2a re-review N-3).
    junction_new_bars: tuple[Bar, ...] = field(default=(), init=False)
    junction_new_rows: tuple[dict, ...] = field(default=(), init=False)

    def __post_init__(self) -> None:
        resolved = self.contract_for(self.target)
        if resolved != self.instrument:
            raise LiveProducerRefused(
                f"--instrument is {self.instrument!r} but "
                f"get_front_month_code(product={self.product!r}, "
                f"target_date={self.target}) is {resolved!r}. The seed walk "
                "names every past day's contract with that same function, so a "
                "disagreement here would splice the traded instrument against "
                "a month nobody is trading (plan §3.2a 「오늘의 종목을 정하는 "
                "바로 그 함수」)"
            )

    def contract_for(self, day: date) -> str:
        if self.product is None:
            return self.instrument
        return get_front_month_code(product=self.product, target_date=day)

    # -- the SeedAssembler interface -------------------------------------

    def __call__(self, day: date, kept: Sequence[SeedDay]) -> tuple[str, Any]:
        """``(contract to request for `day`, aligned frame built from `kept`)``."""
        return self.contract_for(day), bars_to_frame(list(self.aligned_bars(kept)))

    def aligned_bars(self, kept: Sequence[SeedDay]) -> tuple[Bar, ...]:
        """Every kept day's bars in time order, previous month shifted by ``c``."""
        ordered = sorted(kept, key=lambda entry: entry.day)
        if not ordered:
            return ()
        previous = self._previous_contract(ordered)
        if previous is None:
            return tuple(bar for entry in ordered for bar in entry.bars)
        junction = self._resolve_junction(ordered, previous)
        out: list[Bar] = []
        for entry in ordered:
            offset = junction.c_x100 if entry.contract == previous else 0
            out.extend(shift_bars(entry.bars, offset))
        return tuple(out)

    # -- segmentation ----------------------------------------------------

    def _previous_contract(self, ordered: Sequence[SeedDay]) -> str | None:
        """The ONE non-target contract in the kept days, or ``None``.

        Refuses two of them: plan §3.2a allows at most one splice in a seed
        window, and more than one means the window spans a whole contract
        month — a shape this producer does not assemble, rather than one it
        silently approximates.
        """
        others = sorted({e.contract for e in ordered if e.contract != self.instrument})
        if not others:
            return None
        if len(others) > 1:
            raise LiveProducerRefused(
                f"the seed window spans {len(others) + 1} contract months "
                f"({', '.join([*others, self.instrument])}): plan §3.2a allows "
                "at most ONE splice. Refusing rather than chaining two "
                "back-adjusts whose residues nobody has measured"
            )
        previous = others[0]
        newest_previous = max(e.day for e in ordered if e.contract == previous)
        earliest_target = min(
            (e.day for e in ordered if e.contract == self.instrument), default=None
        )
        if earliest_target is not None and earliest_target < newest_previous:
            raise LiveProducerRefused(
                f"{self.instrument} day {earliest_target} precedes {previous} "
                f"day {newest_previous}: the two months interleave, so there is "
                "no single splice point"
            )
        return previous

    def _resolve_junction(
        self, ordered: Sequence[SeedDay], previous: str
    ) -> StitchJunction:
        """Derive ``c_x100`` once, on the walk's own splice day."""
        splice_day = max(e.day for e in ordered if e.contract == previous)
        if self.junction is not None and self.junction.day == splice_day:
            return self.junction
        old_bars = next(
            e.bars for e in ordered if e.day == splice_day and e.contract == previous
        )
        rows = self.fetch_day(splice_day, self.instrument)
        new_bars = _parse(self.instrument, splice_day, rows)
        try:
            junction = derive_junction(
                day=splice_day,
                old_contract=previous,
                new_contract=self.instrument,
                old_bars=old_bars,
                new_bars=new_bars,
            )
        except StitchError as exc:
            raise LiveProducerRefused(str(exc)) from exc
        self.junction = junction
        self.junction_new_bars = tuple(new_bars)
        self.junction_new_rows = tuple(rows)
        return junction

    # -- the manifest ----------------------------------------------------

    def segments(self, kept: Sequence[SeedDay]) -> tuple[StitchSegment, ...]:
        """Seed segments plus the target day, which the producer writes today.

        The target day belongs to the instrument's own segment even when no
        seed day does: right after a roll every kept day is the previous
        month's, and the splice is then between the seed and today.
        """
        ordered = sorted(kept, key=lambda entry: entry.day)
        by_contract: dict[str, list[date]] = {}
        for entry in ordered:
            by_contract.setdefault(entry.contract, []).append(entry.day)
        by_contract.setdefault(self.instrument, []).append(self.target)
        if self.target in by_contract[self.instrument][:-1]:
            raise LiveProducerRefused(
                f"the seed walk kept the target day {self.target} itself; the "
                "frame would carry today's bars twice"
            )
        return tuple(
            StitchSegment(contract=contract, days=tuple(sorted(days)))
            for contract, days in sorted(
                by_contract.items(), key=lambda item: min(item[1])
            )
        )

    def manifest(
        self, kept: Sequence[SeedDay], *, source_sha256: dict[str, str]
    ) -> StitchManifest:
        """The ``stitch.json`` content — written on EVERY session, splice or not.

        Zero junctions is a legitimate manifest (plan §9 MEDIUM-1): B1a and B2
        refuse a session directory whose ``stitch.json`` they were not given,
        and that refusal only protects anything if the file is always there.
        """
        segments = self.segments(kept)
        junctions = [self.junction] if len(segments) > 1 else []
        if len(segments) > 1 and self.junction is None:
            raise LiveProducerRefused(
                "the seed spans two contracts but no junction was derived; the "
                "frame would be unaligned"
            )
        try:
            return build_manifest(
                symbol=self.instrument,
                segments=segments,
                junctions=[j for j in junctions if j is not None],
                source_sha256=source_sha256,
            )
        except StitchError as exc:
            raise LiveProducerRefused(str(exc)) from exc


def _parse(contract: str, day: date, rows: Sequence[dict]) -> list[Bar]:
    from shared.collector.historical.ohlcv_parser import parse_ohlcv

    return parse_ohlcv(contract, day.strftime("%Y%m%d"), {"output2": list(rows)})
