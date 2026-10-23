"""S1a / S1b — the two residues the cross-contract seed does NOT remove.

Plan ``docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md`` §3.2a
「측정 S1a·S1b」. Evidence
``docs/broker-profiles/evidence/2026-10-14-cp3-pr2b-stitch-measurements/``.

**Offline.** Every input is a ``requests.jsonl`` a probe already recorded;
this module opens no socket and reads no credential.

⚠ **Stated precisely, because the loose version is false.** The static import
closure DOES reach ``tools.tos_cp3.quote_client`` — and through it ``httpx``
and ``shared.kis`` — because the frame helper
(``tools.tos_cp3.minute_probe.frame``) lives beside the probe's transport,
and reusing that helper is how this tool and the producer keep ONE definition
of the frame's shape. So the honest claims, both pinned by
``tests/tools/test_cp3_stitch_measure.py``, are: (1) no order path is
reachable at all, and (2) this module's own source constructs no ``Quotes``
and calls no ``page``/``history`` — the transport is in the graph and is
never reached. A test asserting "no transport in the closure" would have had
to be deleted or weakened the first time it was run; this one is true.

Committed rather than left in a scratch directory (review LOW-4): PR-1 and
#899's one-off derivations were not committed, and the consequence showed up
here — the evidence README could state the numbers but nobody could re-derive
them without rewriting the script. The raw responses stay private (they are
tens of MB); their sha256 travels in the output.

What the two measurements are:

* **S1a — path (a), the junction-crossing price difference.** On the target
  day's entry-window opening bars, perturb the back-adjust constant ``c_x100``
  across the measured spread range and count ``stall_ok`` / ``reversal_ok``
  flips. Also reports how far ``c`` would have to move before ANY flip, by
  bisection — a zero the size of a bracket means little without the distance
  to the edge.
* **S1b — path (b), the previous month's ATR standing in for the new one.**
  Compare ``hi_vol`` between the stitched frame and one where the splice
  session is taken from the NEW contract's own bars.

Both are measurements, not gates (plan §3.2a): a flip is reported to the
operator, it does not block.

Firewall: legacy side (``tools/``). No ``tos`` / ``tos_runtime`` import.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.collector.historical.ohlcv_parser import parse_ohlcv  # noqa: E402
from tools.tos_cp3.live_producer.stitch_seed import shift_bars  # noqa: E402
from tools.tos_cp3.minute_probe import frame as bars_to_frame  # noqa: E402
from tools.tos_cp3.produce_fields import (  # noqa: E402
    DEFAULT_MIN_BARS_PER_DAY,
    ContractSpecRegistry,
    ProducedBars,
    load_strategy_inputs,
    produce_bars,
    resolve_contract_spec,
    resolve_open_anchor,
)

#: The entry window's opening minutes — the only bars path (a) can reach
#: (plan §3.2a: `_close_window` and `prev_close` cross the junction there and
#: nowhere else).
WINDOW_MINUTES = tuple((9, minute) for minute in range(15))

#: Magnitudes probed before bisecting for the first flip, in 1/100 price
#: units. The top is ~327 index points — far past any plausible spread.
_LADDER = (2, 8, 32, 128, 512, 2048, 8192, 32768)


class StitchMeasureError(RuntimeError):
    """An input is missing or the measurement cannot be taken honestly."""


def load_raw_rows(paths: Sequence[Path]) -> dict[tuple[str, date], list[dict]]:
    """``(symbol, day) -> raw rows``, de-duplicated by minute, latest wins.

    The probes paginate backwards and the intraday run re-reads a growing day,
    so one ``(symbol, day)`` appears across many responses with overlapping
    rows. Keying on the row's own stamp and keeping the LAST occurrence gives
    the day as the final response saw it. A row whose ``stck_bsop_date`` is
    not the requested day is dropped: ``FID_PW_DATA_INCU_YN=Y`` can carry
    neighbouring days.
    """
    buckets: dict[tuple[str, date], dict[str, dict]] = {}
    for path in paths:
        if not path.is_file():
            raise StitchMeasureError(f"{path}: no such requests.jsonl")
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                event = json.loads(line)
                params = event.get("params") or {}
                symbol = params.get("FID_INPUT_ISCD")
                day_text = params.get("FID_INPUT_DATE_1")
                rows = event.get("rows")
                if not symbol or not day_text or not isinstance(rows, list):
                    continue
                day = date.fromisoformat(
                    f"{day_text[:4]}-{day_text[4:6]}-{day_text[6:]}"
                )
                bucket = buckets.setdefault((symbol, day), {})
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if str(row.get("stck_bsop_date")) != day_text:
                        continue
                    bucket[str(row.get("stck_cntg_hour"))] = row
    return {key: [bucket[k] for k in sorted(bucket)] for key, bucket in buckets.items()}


@dataclass(frozen=True)
class Inputs:
    """Everything resolved once and reused by both measurements."""

    raw: dict[tuple[str, date], list[dict]]
    symbol: str
    previous_symbol: str
    strategy: Any
    contract_spec: Any
    min_bars_per_day: int

    def bars(self, symbol: str, day: date) -> list[tuple]:
        rows = self.raw.get((symbol, day))
        if rows is None:
            raise StitchMeasureError(
                f"no recorded response for {symbol} {day} in the given "
                "requests.jsonl file(s)"
            )
        return parse_ohlcv(symbol, day.strftime("%Y%m%d"), {"output2": rows})

    def frame_bars(
        self, *, c_x100: int, previous_days: Sequence[date], target_days: Sequence[date]
    ) -> list[tuple]:
        """Previous-month days back-adjusted by ``c``, then the target's own."""
        out: list[tuple] = []
        for day in previous_days:
            out.extend(shift_bars(self.bars(self.previous_symbol, day), c_x100))
        for day in target_days:
            out.extend(self.bars(self.symbol, day))
        return out

    def gate(self, frame_bars: Sequence[tuple]) -> list[tuple]:
        """B1a's density gate — whole sessions in or out, same constant."""
        per_day: dict[date, int] = {}
        for bar in frame_bars:
            per_day[bar[1].date()] = per_day.get(bar[1].date(), 0) + 1
        keep = {d for d, n in per_day.items() if n >= self.min_bars_per_day}
        return [bar for bar in frame_bars if bar[1].date() in keep]

    def produce(
        self,
        frame_bars: Sequence[tuple],
        emit_days: Iterable[date],
        observer: Callable[[datetime, Mapping[str, Any]], None] | None = None,
    ) -> ProducedBars:
        ordered = sorted(self.gate(frame_bars), key=lambda bar: bar[1])
        if not ordered:
            raise StitchMeasureError("the density gate dropped every session")
        anchor = resolve_open_anchor(
            cli_value="auto",
            first_session=ordered[0][1].date(),
            last_session=ordered[-1][1].date(),
        )
        return produce_bars(
            bars_to_frame(list(ordered)),
            symbol=self.symbol,
            strategy=self.strategy,
            contract_spec=self.contract_spec,
            anchor=anchor,
            emit_days=frozenset(emit_days),
            observer=observer,
        )

    def fields_by_minute(
        self, frame_bars: Sequence[tuple], emit_days: Iterable[date]
    ) -> dict[datetime, dict[str, Any]]:
        produced = self.produce(frame_bars, emit_days)
        return {
            record.bar_kst.replace(tzinfo=None): record.fields
            for record in produced.records
        }


def _in_window(stamp: datetime, target: date) -> bool:
    return stamp.date() == target and (stamp.hour, stamp.minute) in WINDOW_MINUTES


def measure_s1a(
    inputs: Inputs,
    *,
    target: date,
    previous_days: Sequence[date],
    c_x100: int,
    spread_range_x100: int,
) -> dict[str, Any]:
    """Perturb ``c`` across the measured spread range; count decision flips."""
    baseline = inputs.produce(
        inputs.frame_bars(
            c_x100=c_x100, previous_days=previous_days, target_days=[target]
        ),
        [target],
    )
    # `perturbed`/`flips` 가 다루는 것과 같은 형상으로 적는다 — 둘을 같은 타입으로
    # 두어야 `gates(base[s]) != gates(other[s])` 가 한 가지 값만 비교한다.
    base: dict[datetime, dict[str, Any]] = {
        record.bar_kst.replace(tzinfo=None): record.fields
        for record in baseline.records
    }
    window = [stamp for stamp in sorted(base) if _in_window(stamp, target)]
    if not window:
        raise StitchMeasureError(f"no 09:00-09:14 bar was emitted for {target}")

    def gates(fields: dict[str, Any]) -> tuple[bool, bool]:
        return (fields["stall_ok"], fields["reversal_ok"])

    def perturbed(delta: int) -> dict[datetime, dict[str, Any]]:
        return inputs.fields_by_minute(
            inputs.frame_bars(
                c_x100=c_x100 + delta,
                previous_days=previous_days,
                target_days=[target],
            ),
            [target],
        )

    def flips(other: dict[datetime, dict[str, Any]]) -> int:
        return sum(1 for s in window if gates(base[s]) != gates(other[s]))

    per_offset: list[dict[str, int]] = []
    moved_outside: dict[int, list[str]] = {}
    for delta in range(-spread_range_x100, spread_range_x100 + 1, 2):
        if delta == 0:
            continue
        other = perturbed(delta)
        per_offset.append({"delta_x100": delta, "flips": flips(other)})
        changed = sorted(
            {
                key
                for stamp in base
                for key in base[stamp]
                if base[stamp][key] != other[stamp][key]
                and not _in_window(stamp, target)
            }
        )
        if changed:
            moved_outside[delta] = changed

    margin = {
        "down": _first_flip(lambda d: flips(perturbed(d)) > 0, sign=-1),
        "up": _first_flip(lambda d: flips(perturbed(d)) > 0, sign=1),
    }
    probe = perturbed(spread_range_x100)
    threshold = int(inputs.strategy.entry_config.extreme_atr_mult * 1000)
    counts = [row["flips"] for row in per_offset]
    # Only a bar past the extreme threshold reaches the stall/reversal gates
    # at all; the rest are structurally False and cannot flip, so reporting
    # the flip count against all fifteen window bars would overstate it.
    live = [s.strftime("%H:%M") for s in window if abs(base[s]["z_x1000"]) >= threshold]
    # Key ORDER is the committed artifact's, so a re-run diffs clean against
    # `docs/broker-profiles/evidence/2026-10-14-cp3-pr2b-stitch-measurements/`
    # (review LOW-4: the README's §5 `diff` is only a claim if it holds).
    return {
        "measurement": "S1a — c sensitivity on the splice-crossing stall/reversal gates",
        "plan": "docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md §3.2a S1a",
        "target_day": target.isoformat(),
        "window_kst": "09:00-09:14",
        "window_bars": len(window),
        "c_x100": c_x100,
        "spread_range_x100": spread_range_x100,
        "bracket_x100": [c_x100 - spread_range_x100, c_x100 + spread_range_x100],
        "bracket_is_two_sided": True,
        "perturbations_run": len(per_offset),
        "perturbation_step_x100": 2,
        "flips_total": sum(counts),
        "flips_max_at_one_offset": max(counts),
        "offsets_with_any_flip": [r["delta_x100"] for r in per_offset if r["flips"]],
        # Only a bar past the extreme threshold reaches the stall/reversal
        # gates at all; the rest are structurally False and cannot flip, so a
        # denominator of 15 would overstate what was measured.
        "window_bars_that_can_flip_at_all": live,
        "window_bars_that_can_flip_at_all_count": len(live),
        "flip_margin_x100": margin,
        "flip_margin_in_spread_ranges": (
            round(abs(margin["down"]) / spread_range_x100, 2)
            if margin["down"] is not None
            else None
        ),
        "flip_margin_up_searched_to_x100": _LADDER[-1],
        "baseline_window_fields": {
            s.strftime("%H:%M"): {
                key: base[s][key]
                for key in (
                    "hi_vol",
                    "z_x1000",
                    "atr14_x100",
                    "stall_ok",
                    "reversal_ok",
                )
            }
            for s in window
        },
        "baseline_emitted_bars": len(base),
        "baseline_non_target_bars_replayed_not_emitted": (
            baseline.non_target_segment_bars
        ),
        "seed_days_previous_contract": [d.isoformat() for d in previous_days],
        "fields_that_moved_outside_the_window": sorted(
            {f for fields in moved_outside.values() for f in fields}
        ),
        "bars_that_moved_outside_the_window": (
            moved_bars := sorted(
                s.strftime("%H:%M")
                for s in base
                if not _in_window(s, target)
                and any(base[s][k] != probe[s][k] for k in base[s])
            )
        ),
        "bars_that_moved_outside_the_window_count": len(moved_bars),
        "offsets_at_which_something_moved_outside_the_window": len(moved_outside),
    }


def _first_flip(flips_at: Any, *, sign: int) -> int | None:
    """Smallest |Δc| on the 0.02 grid that flips something, or ``None``.

    Geometric probe then bisection: a linear walk to 327 index points is
    thousands of ``produce_bars`` runs for a number that only needs its order
    of magnitude plus one tick of precision.
    """
    upper = next((m for m in _LADDER if flips_at(sign * m)), None)
    if upper is None:
        return None
    lower = 0
    while upper - lower > 2:
        mid = ((lower + upper) // 4) * 2
        if flips_at(sign * mid):
            upper = mid
        else:
            lower = mid
    return sign * upper


def observe_vol_window(
    inputs: Inputs,
    frame_bars: Sequence[tuple],
    *,
    emit_days: Sequence[date],
    source_by_day: dict[date, str],
) -> tuple[
    dict[date, dict[str, Any]],
    dict[datetime, Any],
    dict[date, list[tuple[datetime, date, float]]],
]:
    """``_atr_window`` composition and percentile reference, from the setup.

    Plan §3.2a S1b asks for both alongside the ``hi_vol`` count. Neither is a
    published field, and the window is filled mostly by bars ``produce_bars``
    replays without emitting, so they are read through its observer hook off
    the setup's own eval trace — ``ev["vol_ref"]`` IS the value
    ``_vol_reference`` returned. Nothing here re-derives a percentile.

    ``ev`` carries ``vol_ref`` on exactly the bars where ``_vol_reference``
    ran, which is exactly the bars that appended to ``_atr_window``, so the
    composition below is bookkeeping over that sequence rather than a second
    model of the deque. The current bar's ATR is appended AFTER the read, so
    the snapshot is taken BEFORE recording this bar's own contribution.

    Returns ``({emit day: snapshot}, {bar: ref}, {emit day: window contents})``,
    where the window contents are the ``(bar, session, atr)`` triples the
    window held when that day's first contributing bar read it.
    """
    window_bars = int(inputs.strategy.entry_config.vol_window_bars)
    wanted = set(emit_days)
    contributors: list[tuple[datetime, date, float]] = []
    snapshots: dict[date, dict[str, Any]] = {}
    windows: dict[date, list[tuple[datetime, date, float]]] = {}
    refs: dict[datetime, Any] = {}

    def observe(stamp: datetime, ev: Mapping[str, Any]) -> None:
        if "vol_ref" not in ev:
            return
        naive = stamp.replace(tzinfo=None)
        day = naive.date()
        if day in wanted and day not in snapshots:
            window = contributors[-window_bars:]
            by_source: dict[str, int] = {}
            for _, contributed, _ in window:
                key = f"{source_by_day[contributed]}:{contributed.isoformat()}"
                by_source[key] = by_source.get(key, 0) + 1
            reference = ev["vol_ref"]
            windows[day] = window
            snapshots[day] = {
                "first_contributing_bar_kst": naive.strftime("%H:%M"),
                "bars_in_window": len(window),
                "by_source": {key: by_source[key] for key in sorted(by_source)},
                "vol_ref_x10000": (
                    None if reference is None else round(float(reference) * 10000)
                ),
                "window_max_atr_x10000": (
                    round(max(a for _, _, a in window) * 10000) if window else None
                ),
            }
        refs[naive] = ev["vol_ref"]
        contributors.append((naive, day, float(ev["atr_14"])))

    inputs.produce(frame_bars, emit_days, observer=observe)
    missing = sorted(day for day in wanted if day not in snapshots)
    if missing:
        raise StitchMeasureError(
            "no bar advanced the causal ATR window on "
            + ", ".join(day.isoformat() for day in missing)
        )
    return snapshots, refs, windows


def compare_splice_contribution(
    windows: dict[str, list[tuple[datetime, date, float]]],
    snapshots: dict[str, dict[str, Any]],
    *,
    splice_day: date,
) -> dict[str, Any]:
    """What the substitution changes INSIDE the window, and where it ranks.

    Without this, a zero in ``hi_vol_differs`` reads as "the substitution
    changed nothing", which would be the wrong reading: the splice session's
    ATRs DO change: they simply may not reach the rank the percentile is taken
    at. Both halves are reported so the zero can only be read with its reason.
    """
    per_frame = {
        label: {stamp: atr for stamp, day, atr in windows[label] if day == splice_day}
        for label in windows
    }
    shared = sorted(set(per_frame["stitched"]) & set(per_frame["substituted"]))
    a, b = per_frame["stitched"], per_frame["substituted"]
    out: dict[str, Any] = {
        "splice_day_bars_in_window": len(shared),
        "splice_day_minutes_kst": (
            f"{shared[0]:%H:%M}-{shared[-1]:%H:%M}" if shared else None
        ),
        "atr_differs": sum(1 for s in shared if a[s] != b[s]),
        "atr_max_abs_difference_x10000": (
            round(max(abs(a[s] - b[s]) for s in shared) * 10000) if shared else None
        ),
    }
    for label, values in (("stitched", a), ("substituted", b)):
        reference = snapshots[label]["vol_ref_x10000"]
        out[f"atr_x10000_range_{label}"] = (
            [
                round(min(values[s] for s in shared) * 10000),
                round(max(values[s] for s in shared) * 10000),
            ]
            if shared
            else None
        )
        out[f"splice_day_bars_at_or_above_vol_ref_{label}"] = (
            None
            if reference is None
            else sum(1 for s in shared if round(values[s] * 10000) >= reference)
        )
    return out


def measure_s1b(
    inputs: Inputs,
    *,
    splice_day: date,
    previous_days: Sequence[date],
    compare_days: Sequence[date],
    c_x100: int,
    c_values_x100: Sequence[int],
    day_not_measured: str | None = None,
    day_not_measured_reason: str | None = None,
) -> dict[str, Any]:
    """``hi_vol`` with the splice session from each contract in turn.

    The substituted frame is a MEASUREMENT-ONLY hand manifest: it does not
    follow the front-month walk and no ``c_x100`` recomputation is asserted
    against it (plan §3.2a's v8 disposition). That is sound because ``hi_vol``
    reads only within-contract ATRs — which this function CHECKS rather than
    assumes, by re-running both frames at several ``c`` values.
    """

    def frames(c: int) -> tuple[list[tuple], list[tuple]]:
        stitched = inputs.frame_bars(
            c_x100=c,
            previous_days=[*previous_days, splice_day],
            target_days=compare_days,
        )
        substituted = inputs.frame_bars(
            c_x100=c,
            previous_days=previous_days,
            target_days=[splice_day, *compare_days],
        )
        return stitched, substituted

    def hi_vol(frame_bars: Sequence[tuple]) -> dict[datetime, bool]:
        return {
            stamp: fields["hi_vol"]
            for stamp, fields in inputs.fields_by_minute(
                frame_bars, compare_days
            ).items()
            if fields["entry_window"]
        }

    stitched, substituted = frames(c_x100)
    # Every EMITTED bar, for the honest "how many were compared" count, and
    # the entry-window subset, which is where hi_vol can differ at all.
    all_a = inputs.fields_by_minute(stitched, compare_days)
    all_b = inputs.fields_by_minute(substituted, compare_days)
    compared = sorted(set(all_a) & set(all_b))
    a, b = hi_vol(stitched), hi_vol(substituted)
    shared = sorted(set(a) & set(b))
    per_day: dict[str, Any] = {}
    for day in compare_days:
        stamps = [s for s in shared if s.date() == day]
        differing = [s for s in stamps if a[s] != b[s]]
        per_day[day.isoformat()] = {
            "bars_compared": sum(1 for s in compared if s.date() == day),
            "in_entry_window": len(stamps),
            "hi_vol_differs": len(differing),
            "first_difference_kst": (
                differing[0].strftime("%H:%M") if differing else None
            ),
            "last_difference_kst": (
                differing[-1].strftime("%H:%M") if differing else None
            ),
            "hi_vol_true_stitched": sum(a[s] for s in stamps),
            "hi_vol_true_substituted": sum(b[s] for s in stamps),
        }

    # Plan §3.2a S1b: report the window the percentile is taken over, not only
    # the hi_vol count. The 「완전한 비교」 claim for the last compare day is
    # exactly a claim about this composition — that one previous-month session
    # is left inside the window — so it is measured here instead of restated.
    sources = {
        "stitched": {
            **dict.fromkeys([*previous_days, splice_day], inputs.previous_symbol),
            **dict.fromkeys(compare_days, inputs.symbol),
        },
        "substituted": {
            **dict.fromkeys(previous_days, inputs.previous_symbol),
            **dict.fromkeys([splice_day, *compare_days], inputs.symbol),
        },
    }
    window_snapshots: dict[str, Any] = {}
    window_refs: dict[str, dict[datetime, Any]] = {}
    window_contents: dict[str, Any] = {}
    for label, index in (("stitched", 0), ("substituted", 1)):
        (
            window_snapshots[label],
            window_refs[label],
            window_contents[label],
        ) = observe_vol_window(
            inputs,
            frames(c_x100)[index],
            emit_days=compare_days,
            source_by_day=sources[label],
        )
    composition: dict[str, Any] = {}
    for day in compare_days:
        stamps = [s for s in shared if s.date() == day]
        composition[day.isoformat()] = {
            "stitched": window_snapshots["stitched"][day],
            "substituted": window_snapshots["substituted"][day],
            "vol_ref_differs_in_entry_window": sum(
                1
                for s in stamps
                if window_refs["stitched"].get(s) != window_refs["substituted"].get(s)
            ),
            "in_entry_window": len(stamps),
            "splice_day_contribution": compare_splice_contribution(
                {label: window_contents[label][day] for label in window_contents},
                {label: window_snapshots[label][day] for label in window_snapshots},
                splice_day=splice_day,
            ),
        }

    independence: dict[str, Any] = {}
    for label, index in (("stitched", 0), ("substituted", 1)):
        baseline = hi_vol(frames(c_x100)[index])
        by_c: dict[str, int] = {}
        for c in c_values_x100:
            # ONE frame build per c. The first cut had this call inside the
            # generator over `baseline.items()`, which rebuilt the frame and
            # re-ran produce_bars once PER BAR — 662 x 5 x 2 runs, so the
            # documented reproduction never finished. Caught by running it.
            other = hi_vol(frames(c)[index])
            by_c[str(c)] = sum(
                1 for stamp, value in baseline.items() if other.get(stamp) != value
            )
        independence[label] = {
            "in_window_bars": len(baseline),
            "hi_vol_differences_by_c_x100": by_c,
        }

    return {
        "measurement": "S1b — previous-month ATR substitution in the causal vol window",
        "plan": "docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md §3.2a S1b",
        "splice_day": splice_day.isoformat(),
        "frame_a_stitched": (
            f"{inputs.previous_symbol} "
            f"{[d.isoformat() for d in [*previous_days, splice_day]]} + "
            f"{inputs.symbol} {[d.isoformat() for d in compare_days]}"
        ),
        "frame_b_substituted": (
            f"{inputs.previous_symbol} {[d.isoformat() for d in previous_days]} + "
            f"{inputs.symbol} "
            f"{[d.isoformat() for d in [splice_day, *compare_days]]}"
        ),
        "compare_days": [d.isoformat() for d in compare_days],
        "per_day": per_day,
        "bars_compared_total": len(compared),
        "hi_vol_differences_total": sum(
            row["hi_vol_differs"] for row in per_day.values()
        ),
        "in_entry_window_total": sum(
            row["in_entry_window"] for row in per_day.values()
        ),
        "c_independence_check": independence,
        "c_values_checked_x100": list(c_values_x100),
        "atr_window_bars": int(inputs.strategy.entry_config.vol_window_bars),
        "vol_percentile": float(inputs.strategy.entry_config.vol_percentile),
        "vol_warmup_bars": int(inputs.strategy.entry_config.vol_warmup_bars),
        "min_atr_ratio": float(inputs.strategy.entry_config.min_atr_ratio),
        "atr_window_composition": composition,
        "day_not_measured": day_not_measured,
        "day_not_measured_reason": day_not_measured_reason,
    }


def render(payload: dict[str, Any]) -> bytes:
    """Byte-stable JSON: two runs over the same inputs render identically.

    Deliberately carries no run timestamp, for B1a's reason — a changed
    artifact must mean changed inputs or code, never merely a re-run.
    """
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stitch_measure",
        description=(
            "CP-3 PR-2b S1a/S1b — offline measurement of the residues the "
            "cross-contract seed does not remove. Reads recorded probe "
            "responses only; opens no socket."
        ),
    )
    parser.add_argument(
        "--requests",
        type=Path,
        action="append",
        required=True,
        help="a probe's requests.jsonl; repeat for each recorded run",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--symbol", required=True, help="the new (target) contract")
    parser.add_argument("--previous-symbol", required=True)
    parser.add_argument("--target", required=True, type=date.fromisoformat)
    parser.add_argument("--splice-day", required=True, type=date.fromisoformat)
    parser.add_argument(
        "--previous-day",
        action="append",
        required=True,
        type=date.fromisoformat,
        help="previous-month seed day BEFORE the splice day; repeat",
    )
    parser.add_argument(
        "--compare-day",
        action="append",
        required=True,
        type=date.fromisoformat,
        help="S1b comparison day on the new contract; repeat",
    )
    parser.add_argument(
        "--c-x100",
        required=True,
        type=int,
        help="the measured back-adjust constant (evidence 2026-10-14: 344)",
    )
    parser.add_argument(
        "--spread-range-x100",
        required=True,
        type=int,
        help="observed spread max-min over the junction window (evidence: 118)",
    )
    parser.add_argument(
        "--c-value-x100",
        action="append",
        type=int,
        default=None,
        help="extra c values for S1b's independence check; repeat",
    )
    parser.add_argument(
        "--strategy-yaml",
        type=Path,
        default=REPO_ROOT / "config/strategies/futures/setup_d_vwap_reversion.yaml",
    )
    parser.add_argument(
        "--min-bars-per-day", type=int, default=DEFAULT_MIN_BARS_PER_DAY
    )
    parser.add_argument(
        "--day-not-measured",
        default=None,
        help=(
            "a comparison day the plan asks for that this run could not take. "
            "Recorded IN the artifact, not only in prose: an absent day that "
            "is not named reads as a day with no difference"
        ),
    )
    parser.add_argument("--day-not-measured-reason", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI. Exit codes: ``0`` ok, ``2`` an input is missing or unusable."""
    args = build_parser().parse_args(argv)
    try:
        raw = load_raw_rows(args.requests)
        inputs = Inputs(
            raw=raw,
            symbol=args.symbol,
            previous_symbol=args.previous_symbol,
            strategy=load_strategy_inputs(args.strategy_yaml),
            contract_spec=resolve_contract_spec(
                args.symbol,
                ContractSpecRegistry.from_yaml(
                    str(REPO_ROOT / "config/execution.yaml")
                ),
            ),
            min_bars_per_day=args.min_bars_per_day,
        )
        previous_days = sorted({*args.previous_day, args.splice_day})
        s1a = measure_s1a(
            inputs,
            target=args.target,
            previous_days=previous_days,
            c_x100=args.c_x100,
            spread_range_x100=args.spread_range_x100,
        )
        s1b = measure_s1b(
            inputs,
            splice_day=args.splice_day,
            previous_days=sorted(args.previous_day),
            compare_days=sorted(args.compare_day),
            c_x100=args.c_x100,
            c_values_x100=sorted(set(args.c_value_x100 or [args.c_x100])),
            day_not_measured=args.day_not_measured,
            day_not_measured_reason=args.day_not_measured_reason,
        )
    except StitchMeasureError as exc:
        print(f"stitch_measure: {exc}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "CP3-PR2B-S1a.json").write_bytes(render(s1a))
    (args.out / "CP3-PR2B-S1b.json").write_bytes(render(s1b))
    (args.out / "CP3-PR2B-sources.json").write_bytes(
        render(
            {
                "source_sha256": {
                    (
                        path.name
                        if path.parent.name == ""
                        else (f"{path.parent.name}/{path.name}")
                    ): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in args.requests
                },
                "parsed_bar_counts": {
                    f"{symbol}:{day.isoformat()}": len(inputs.bars(symbol, day))
                    for symbol, day in sorted(raw, key=lambda k: (k[0], k[1]))
                    if day >= min(previous_days)
                },
                "density_gate": args.min_bars_per_day,
                "vol_window_bars": int(inputs.strategy.entry_config.vol_window_bars),
            }
        )
    )
    print(f"S1a flips_total={s1a['flips_total']} margin={s1a['flip_margin_x100']}")
    print(f"S1b hi_vol_differences_total={s1b['hi_vol_differences_total']}")
    print(f"wrote 3 artifacts to {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI tests
    raise SystemExit(main())
