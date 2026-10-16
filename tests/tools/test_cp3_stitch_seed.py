"""CP-3 PR-2b — the cross-contract (month-stitch) seed, plan §3.2a tests 1-6.

Hermetic: no socket, no credential, no KIS call. The quotation transport is a
fixture server and the clock a fake one.

Every clause these tests guard is red-proved here, either by its own
``test_red_*`` companion or by a case inside the test that shows the assertion
failing when the clause is removed. Two of the six items ARE each other's red
proof and are written that way on purpose (plan §3.2a: 「1 과 짝 — 정렬 절을
지워도 전부 초록이면 그 절은 아무것도 하지 않는 것」):

* item 1 says the alignment changes nothing that comes from a price DIFFERENCE;
* item 2 says it changes something that does not — ``stall_ok`` on a bar in the
  entry window right after the splice.

The fixture constants are the measured ones wherever a measurement exists:
``c_x100 = 344`` and the 15:19 / 15:45 session-end mismatch are from
``docs/broker-profiles/evidence/2026-10-14-cp3-pr2b-expired-contract``, and the
raw row shape uses the ``stck_`` date/time prefix that evidence §2 recorded on
a futures TR response.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from shared.collector.historical.ohlcv_parser import parse_ohlcv
from tools.tos_cp3 import diff_decisions as dd
from tools.tos_cp3 import emit_legacy_decisions as b2
from tools.tos_cp3 import produce_fields as b1a
from tools.tos_cp3 import stitch as stitch_mod
from tools.tos_cp3.live_producer import config as config_mod
from tools.tos_cp3.live_producer import producer as producer_mod
from tools.tos_cp3.live_producer import sinks as sinks_mod
from tools.tos_cp3.live_producer.config import LiveProducerRefused
from tools.tos_cp3.live_producer.stitch_seed import StitchedSeed, shift_bars
from tools.tos_cp3.minute_probe import frame as bars_to_frame
from tools.tos_cp3.produce_fields import (
    ContractSpecRegistry,
    ProduceFieldsError,
    load_strategy_inputs,
    produce_bars,
    resolve_contract_spec,
    resolve_open_anchor,
)
from tools.tos_cp3.stitch import (
    STITCH_FILENAME,
    StitchError,
    StitchSegment,
    build_manifest,
    derive_junction,
    load_manifest,
    render_manifest,
    rows_digest,
    write_manifest,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

OLD = "A05610"
NEW = "A05611"
#: The roll this PR was designed against: A05610 expires 2026-10-08 and
#: ``get_front_month_code(product="mini")`` moves to A05611 the next trading
#: day (2026-10-09 is a holiday, so that is 2026-10-12).
TARGET = date(2026, 10, 12)
SPLICE = date(2026, 10, 8)
#: Walk order is backwards from TARGET; these are the four trading days the
#: tenant calendar yields before it (2026-10-05 is a substitute holiday and
#: 10-03/10-04 a weekend).
SEED_DAYS = [date(2026, 10, 2), date(2026, 10, 6), date(2026, 10, 7), SPLICE]

OPEN_HM = (8, 45)
SESSION_BARS = 420  # 08:45..15:44, the real shape of a 2026 futures session
#: Measured on the 2026-10 roll (evidence §5): P_new - P_old at the last common
#: parsed minute, +3.44 index points on the mini 0.02 grid.
C_X100 = 344


# ---------------------------------------------------------------------------
# Synthetic market
# ---------------------------------------------------------------------------


def _stamp(day: date, index: int) -> datetime:
    return datetime(day.year, day.month, day.day, *OPEN_HM) + timedelta(minutes=index)


def _bar(code: str, day: date, index: int, close: float, half: float) -> tuple:
    """One ``parse_ohlcv``-shaped bar with a symmetric ``half``-wide range."""
    return (
        code,
        _stamp(day, index),
        close,
        round(close + half, 2),
        round(close - half, 2),
        close,
        50 + index % 11,
    )


def _flat_session(code: str, day: date, close: float, half: float) -> list[tuple]:
    return [_bar(code, day, i, close, half) for i in range(SESSION_BARS)]


def _zigzag(index: int, period: int = 7) -> float:
    phase = index % period
    half = period / 2
    return (phase / half) if phase < half else (2 - phase / half)


#: Two-bar impulses: a stretch away from VWAP, then a partial turn back that is
#: still beyond ``extreme_atr_mult``. Without them every bar returns at step 4
#: and ``stall_ok`` / ``reversal_ok`` are False everywhere — a fixture in which
#: item 1 would be vacuous (plan §9 LOW-2).
_SPIKES = {
    60: 8.0,
    61: 6.5,
    140: -8.0,
    141: -6.5,
    220: 9.0,
    221: 7.0,
    300: -9.0,
    301: -7.0,
}


def _spiky_session(
    code: str, day: date, scale: float, base: float = 400.0
) -> list[tuple]:
    bars: list[tuple] = []
    previous = base
    for index in range(SESSION_BARS):
        if index in _SPIKES:
            close = round(base + _SPIKES[index], 2)
        else:
            close = round(base + scale * (_zigzag(index) - 0.5) * 2, 2)
        bars.append(
            (
                code,
                _stamp(day, index),
                previous,
                round(max(previous, close) + scale * 0.2, 2),
                round(min(previous, close) - scale * 0.2, 2),
                close,
                50 + index % 17,
            )
        )
        previous = close
    return bars


def _raw_row(bar: tuple, *, volume: int | None = None) -> dict:
    """One KIS ``output2`` row.

    The date and time keys carry the ``stck_`` prefix while the OHLC keys carry
    ``futs_`` — the shape evidence
    ``2026-10-14-cp3-pr2b-expired-contract`` §2 measured on this very TR.
    """
    return {
        "stck_bsop_date": bar[1].strftime("%Y%m%d"),
        "stck_cntg_hour": bar[1].strftime("%H%M%S"),
        "futs_oprc": f"{bar[2]:.2f}",
        "futs_hgpr": f"{bar[3]:.2f}",
        "futs_lwpr": f"{bar[4]:.2f}",
        "futs_prpr": f"{bar[5]:.2f}",
        "cntg_vol": str(bar[6] if volume is None else volume),
    }


# ---------------------------------------------------------------------------
# Strategy / contract inputs
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def inputs() -> dict[str, Any]:
    return {
        "strategy": load_strategy_inputs(
            _REPO_ROOT / "config/strategies/futures/setup_d_vwap_reversion.yaml"
        ),
        "anchor": resolve_open_anchor(
            cli_value="auto", first_session=TARGET, last_session=TARGET
        ),
        "contract_spec": resolve_contract_spec(
            NEW,
            ContractSpecRegistry.from_yaml(str(_REPO_ROOT / "config/execution.yaml")),
        ),
    }


def _produce(bars, inputs: dict, *, emit_days=None):
    return produce_bars(
        bars_to_frame(list(bars)),
        symbol=NEW,
        strategy=inputs["strategy"],
        contract_spec=inputs["contract_spec"],
        anchor=inputs["anchor"],
        emit_days=emit_days,
    )


#: Published fields that come from a price DIFFERENCE, a ratio of differences,
#: or the clock. A constant added to every price must leave all of them alone.
TRANSLATION_INVARIANT = (
    "volume",
    "session_token",
    "atr14_x100",
    "z_x1000",
    "hi_vol",
    "stall_ok",
    "reversal_ok",
    "entry_window",
    "vwap_reverted",
    "eod",
)
#: Published fields that ARE prices. Each must move by exactly the constant.
TRANSLATION_SHIFTED = (
    "open_x100",
    "high_x100",
    "low_x100",
    "close_x100",
    "vwap_x100",
)


@pytest.fixture(scope="module")
def invariance_bars() -> list[tuple]:
    """Three sessions of ONE contract, with spikes, on real trading days."""
    bars: list[tuple] = []
    for index, day in enumerate([date(2026, 10, 6), date(2026, 10, 7), SPLICE]):
        bars.extend(_spiky_session(NEW, day, [3.0, 3.0, 3.8][index]))
    return bars


# ===========================================================================
# §3.2a 1 — translation invariance
# ===========================================================================


def test_item1_the_fixture_exercises_both_sides_of_every_gate(
    invariance_bars: list[tuple], inputs: dict
) -> None:
    """Plan §9 LOW-2: an all-permissive fixture would make item 1 vacuous.

    A frame whose ``hi_vol`` is True on every bar (the warm-up regime) or whose
    deeper gates are never reached tests nothing: a translation cannot flip a
    gate nobody evaluated. This asserts the fixture reaches BOTH sides —
    ``hi_vol`` False after the ``vol_warmup_bars`` warm-up, and at least one
    bar on which the setup ran all the way through ``reversal_ok``.
    """
    produced = _produce(invariance_bars, inputs)
    warm = inputs["strategy"].entry_config.vol_warmup_bars
    in_window = [r for r in produced.records if r.fields["entry_window"]]
    assert len(in_window) > warm
    after_warmup = in_window[warm:]
    assert any(not r.fields["hi_vol"] for r in after_warmup), "no hi_vol False bar"
    assert any(r.fields["hi_vol"] for r in after_warmup), "no hi_vol True bar"
    fired = [
        r
        for r in produced.records
        if r.fields["hi_vol"] and r.fields["stall_ok"] and r.fields["reversal_ok"]
    ]
    assert fired, "no bar reached reversal_ok — the deep gates are untested"


def test_item1_adding_the_grid_constant_moves_prices_and_nothing_else(
    invariance_bars: list[tuple], inputs: dict
) -> None:
    """The same frame, shifted by ``c_x100``: differences identical, prices +c.

    This is what plan §3.2a means by 「정렬은 접합 점프를 지운다」. It is only a
    claim about the published fields — the residues the alignment does NOT
    remove are measured as S1a / S1b, not asserted here.
    """
    plain = _produce(invariance_bars, inputs)
    shifted = _produce(shift_bars(invariance_bars, C_X100), inputs)
    assert len(plain.records) == len(shifted.records)
    for before, after in zip(plain.records, shifted.records):
        assert before.raw_event_id == after.raw_event_id
        for key in TRANSLATION_INVARIANT:
            assert before.fields[key] == after.fields[key], (key, before.raw_event_id)
        for key in TRANSLATION_SHIFTED:
            assert after.fields[key] - before.fields[key] == C_X100, (
                key,
                before.raw_event_id,
            )


def test_shift_price_x100_lands_on_the_grid_half_up_names() -> None:
    """The concrete input that separates the quantised shift from a naive one.

    On a price already on the 1/100 grid the two agree, so this is the input
    that makes the clause do something at all — and saying so is the point:
    a guard whose author cannot name a failing input is not guarding anything.
    Documented as a bounded claim in ``shift_price_x100``'s own docstring.
    """
    off_grid, one_tick = 400.025, 2  # half a mini tick, shifted by one tick
    assert (
        b1a.scaled_int_half_up(stitch_mod.shift_price_x100(off_grid, one_tick), 100)
        == 40005
    )
    assert b1a.scaled_int_half_up(off_grid + one_tick / 100.0, 100) == 40004
    # And on grid-aligned prices — everything parse_ohlcv emits — they agree,
    # which is why item 1 stays green with either form. Said out loud so the
    # clause is not read as doing more than it does.
    for on_grid in (400.00, 400.07, 1049.00, 1052.44):
        for offset in (C_X100, one_tick, -C_X100):
            assert b1a.scaled_int_half_up(
                stitch_mod.shift_price_x100(on_grid, offset), 100
            ) == b1a.scaled_int_half_up(on_grid + offset / 100.0, 100)


def test_item1_red_a_shift_that_is_not_a_translation_moves_the_gates(
    invariance_bars: list[tuple], inputs: dict
) -> None:
    """Red proof for the test above: the invariance is a property, not a tautology.

    Shift only the FIRST session — a step inside the frame rather than a
    constant over it, which is exactly what an unaligned splice is — and the
    boolean gates move. If the assertion above passed for this input too, it
    would be testing nothing.
    """
    first_day = invariance_bars[0][1].date()
    stepped = [
        (shift_bars([bar], C_X100)[0] if bar[1].date() == first_day else bar)
        for bar in invariance_bars
    ]
    plain = _produce(invariance_bars, inputs)
    broken = _produce(stepped, inputs)
    differing = [
        key
        for before, after in zip(plain.records, broken.records)
        for key in TRANSLATION_INVARIANT
        if before.fields[key] != after.fields[key]
    ]
    assert differing, "a non-uniform shift left every difference-derived field alone"


# ===========================================================================
# §3.2a 2 — the alignment contributes to the decision
# ===========================================================================


def _junction_market() -> tuple[list[tuple], list[tuple]]:
    """Two previous-month sessions, then the first new-month session.

    Shaped so the ONLY thing the alignment can reach at 09:00-09:14 of the new
    session is the stall guard's ``_close_window``: the previous month's closes
    are flat, so its ATR percentile is the same either way, and the splice's own
    true range sits on the 08:45 bar, outside the fourteen the entry window's
    ATR averages (plan §3.2a path (a)).
    """
    old: list[tuple] = []
    for day in (date(2026, 10, 7), SPLICE):
        old.extend(_flat_session(OLD, day, 400.00, 0.75))
    new: list[tuple] = []
    for index in range(SESSION_BARS):
        if index < 16:
            new.append(_bar(NEW, TARGET, index, 410.00, 0.46))
        elif index == 16:  # 09:01 — the dip the setup would fade
            new.append(
                (NEW, _stamp(TARGET, index), 410.00, 410.00, 397.50, 398.00, 120)
            )
        else:
            new.append(_bar(NEW, TARGET, index, 398.00, 0.46))
    return old, new


def test_item2_turning_the_alignment_off_flips_the_stall_guard(
    inputs: dict,
) -> None:
    """Plan §3.2a test 2 — and the red proof of the alignment clause itself.

    On a bar in the entry window of the session right after the splice, with
    ``hi_vol`` true, ``|z|`` past ``extreme_atr_mult`` and the spread wider than
    ``stall_buffer_atr_mult x ATR``, dropping the back-adjust flips ``stall_ok``.
    Delete the alignment and this test goes red, which is what makes item 1's
    invariance a statement about something rather than about nothing.
    """
    old, new = _junction_market()
    aligned = _produce(
        list(shift_bars(old, C_X100)) + new, inputs, emit_days=frozenset({TARGET})
    )
    unaligned = _produce(old + new, inputs, emit_days=frozenset({TARGET}))
    by_aligned = {r.bar_kst: r.fields for r in aligned.records}
    by_unaligned = {r.bar_kst: r.fields for r in unaligned.records}

    entry_config = inputs["strategy"].entry_config
    threshold = int(entry_config.extreme_atr_mult * 1000)
    flips = []
    for stamp, fields in by_aligned.items():
        if not (stamp.hour == 9 and stamp.minute <= 14):
            continue
        other = by_unaligned[stamp]
        if (fields["stall_ok"], fields["reversal_ok"]) != (
            other["stall_ok"],
            other["reversal_ok"],
        ):
            flips.append((stamp, fields, other))

    assert flips, "the alignment changed no decision in 09:00-09:14"
    stamp, fields, other = flips[0]
    # The plan's three preconditions on the bar that flips, asserted rather
    # than assumed: a flip on a bar the setup never gated would prove nothing.
    assert fields["hi_vol"] is True
    assert abs(fields["z_x1000"]) >= threshold
    buffer_x100 = entry_config.stall_buffer_atr_mult * fields["atr14_x100"]
    assert buffer_x100 < C_X100, (C_X100, buffer_x100)
    assert fields["stall_ok"] != other["stall_ok"]
    # The ATR and z are the SAME on both sides: the splice's own true range is
    # on the 08:45 bar and never enters this bar's fourteen (plan §3.2a).
    assert fields["atr14_x100"] == other["atr14_x100"]
    assert fields["z_x1000"] == other["z_x1000"]


# ===========================================================================
# §3.2a 3 — what ``c`` is derived from
# ===========================================================================


def _two_legs_with_different_session_ends() -> tuple[list[tuple], list[tuple]]:
    """The measured shape: the expiring month stops at 15:19, the new one 15:45.

    Evidence §4 (2026-10-08): the expiring leg's last raw minute was 15:19 and
    the successor's 15:45, 26 minutes apart. The plan's test fixes the same
    shape at 15:20 / 15:45; the point is identical and the numbers here are the
    measured ones.
    """
    old = [
        _bar(OLD, SPLICE, i, round(400.00 + 0.01 * (i % 7), 2), 0.3) for i in range(395)
    ]
    new = [
        _bar(NEW, SPLICE, i, round(403.44 + 0.01 * (i % 5), 2), 0.3)
        for i in range(SESSION_BARS + 1)
    ]
    assert old[-1][1].strftime("%H:%M") == "15:19"
    assert new[-1][1].strftime("%H:%M") == "15:45"
    return old, new


def test_item3_c_is_the_last_COMMON_minute_not_each_legs_own_last_close() -> None:
    old, new = _two_legs_with_different_session_ends()
    junction = derive_junction(
        day=SPLICE,
        old_contract=OLD,
        new_contract=NEW,
        old_bars=old,
        new_bars=new,
    )
    assert junction.common_minute == old[-1][1]
    assert junction.common_minute.strftime("%H:%M") == "15:19"
    expected_old = next(bar for bar in old if bar[1] == junction.common_minute)
    expected_new = next(bar for bar in new if bar[1] == junction.common_minute)
    assert junction.old_close_x100 == round(expected_old[5] * 100)
    assert junction.new_close_x100 == round(expected_new[5] * 100)
    assert junction.c_x100 == junction.new_close_x100 - junction.old_close_x100

    # RED: each leg's own last close is a DIFFERENT number, so the rule is
    # load-bearing. Taking it would difference 15:19 against 15:45 and fold 26
    # minutes of price move into the constant.
    each_legs_last = round(new[-1][5] * 100) - round(old[-1][5] * 100)
    assert each_legs_last != junction.c_x100


def test_item3_a_thin_last_common_RAW_minute_is_not_the_minute_chosen() -> None:
    """Both sides pick the last common PARSED bar (plan §3.2a re-review N-3).

    The last minute both legs have a RAW row for trades below
    ``KIS_MINUTE_BAR_MIN_VOLUME`` on one of them, so ``parse_ohlcv`` drops it
    there. A raw-row rule would make the producer and the offline recomputation
    pick different minutes and every stitched session would be refused.
    """
    old = [
        _bar(OLD, SPLICE, i, round(400.00 + 0.01 * (i % 7), 2), 0.3) for i in range(60)
    ]
    new = [
        _bar(NEW, SPLICE, i, round(403.44 + 0.01 * (i % 5), 2), 0.3) for i in range(60)
    ]
    thin_minute = new[-1][1]
    old_rows = [_raw_row(bar) for bar in old]
    new_rows = [_raw_row(bar) for bar in new[:-1]] + [_raw_row(new[-1], volume=5)]

    old_parsed = parse_ohlcv(OLD, SPLICE.strftime("%Y%m%d"), {"output2": old_rows})
    new_parsed = parse_ohlcv(NEW, SPLICE.strftime("%Y%m%d"), {"output2": new_rows})
    raw_common = sorted({bar[1] for bar in old} & {bar[1] for bar in new})
    assert raw_common[-1] == thin_minute, "the fixture's thin minute is not last"
    assert thin_minute not in {bar[1] for bar in new_parsed}, "the floor did not bite"

    junction = derive_junction(
        day=SPLICE,
        old_contract=OLD,
        new_contract=NEW,
        old_bars=old_parsed,
        new_bars=new_parsed,
    )
    # RED: the raw rule would have chosen `thin_minute`.
    assert junction.common_minute != thin_minute
    assert junction.common_minute == new_parsed[-1][1]


# ===========================================================================
# §3.2a 4 — refusals
# ===========================================================================


def test_item4_refuses_when_the_two_contracts_share_no_parsed_minute() -> None:
    old = [_bar(OLD, SPLICE, i, 400.00, 0.3) for i in range(10)]
    new = [_bar(NEW, SPLICE, i, 403.44, 0.3) for i in range(20, 30)]
    with pytest.raises(StitchError, match="share no parsed minute"):
        derive_junction(
            day=SPLICE,
            old_contract=OLD,
            new_contract=NEW,
            old_bars=old,
            new_bars=new,
        )


def test_item4_refuses_a_second_splice_in_one_seed_window() -> None:
    """Two previous months in one window is refused, in both places it can appear."""
    from tools.tos_cp3.live_producer.frame import SeedDay

    assembler = StitchedSeed(
        instrument=NEW, target=TARGET, product="mini", fetch_day=_unused_fetch
    )
    kept = [
        SeedDay(day=date(2026, 9, 8), contract="A05609", bars=()),
        SeedDay(day=SPLICE, contract=OLD, bars=()),
    ]
    with pytest.raises(LiveProducerRefused, match="at most ONE splice"):
        assembler.aligned_bars(kept)

    junction = stitch_mod.StitchJunction(
        day=SPLICE,
        common_minute=datetime(2026, 10, 8, 15, 19),
        old_contract=OLD,
        new_contract=NEW,
        old_close_x100=104900,
        new_close_x100=105244,
        c_x100=344,
    )
    with pytest.raises(StitchError, match="at most ONE splice"):
        build_manifest(
            symbol=NEW,
            segments=[
                StitchSegment("A05609", (date(2026, 9, 8),)),
                StitchSegment(OLD, (SPLICE,)),
                StitchSegment(NEW, (TARGET,)),
            ],
            junctions=[junction, junction],
            source_sha256={"x": "0" * 64},
        )


def _unused_fetch(day: date, contract: str) -> list[dict]:  # pragma: no cover
    raise AssertionError("no fetch should happen in this test")


def test_item4_b1a_and_b2_refuse_a_session_dir_whose_manifest_was_not_passed(
    stitched_session: StitchedSession,
) -> None:
    """Plan §9 MEDIUM-1 / re-review N-2, with §3.6's layout taken literally.

    ``--data-root`` is ``<session dir>/market`` and ``stitch.json`` sits
    directly inside it; the check looks exactly there.
    """
    assert (stitched_session.market_root / STITCH_FILENAME).is_file()
    for runner in (b1a.run, b2.run):
        with pytest.raises(ProduceFieldsError, match="no --stitch-manifest"):
            runner(
                **stitched_session.run_kwargs(out_name=f"no-flag-{runner.__module__}")
            )


def test_item4_refuses_a_manifest_that_targets_another_symbol(
    stitched_session: StitchedSession,
) -> None:
    kwargs = stitched_session.run_kwargs(
        out_name="wrong-symbol", with_manifest=True, symbol=OLD
    )
    with pytest.raises(ProduceFieldsError, match="but --symbol is"):
        b1a.run(**kwargs)


def test_item4_refuses_a_manifest_whose_c_x100_does_not_recompute(
    stitched_session: StitchedSession, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The sign-flipped manifest plan §3.2a test 4 names.

    Without this, a producer that derived the wrong ``c`` has its mistake
    reproduced byte for byte offline and the pair passes B3 (plan §9 MEDIUM-3).
    """
    payload = json.loads(
        (stitched_session.market_root / STITCH_FILENAME).read_text(encoding="utf-8")
    )
    assert payload["junctions"], "this session has no junction to flip"
    junction = payload["junctions"][0]
    junction["c_x100"] = -junction["c_x100"]
    junction["new_close_x100"] = junction["old_close_x100"] + junction["c_x100"]
    forged = tmp_path_factory.mktemp("forged") / STITCH_FILENAME
    forged.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")

    kwargs = stitched_session.run_kwargs(out_name="forged", with_manifest=True)
    kwargs["stitch_manifest"] = forged
    with pytest.raises(ProduceFieldsError, match="disagrees with"):
        b1a.run(**kwargs)


# --- B3's side of the refusal ---------------------------------------------


def _identity_lineages(
    b1a_sha: str | None, b2_sha: str | None, *, b2_has_key: bool = True
) -> dict[str, Any]:
    common = {
        "symbol": NEW,
        "market_open_kst": "08:45",
        "market_open_source": "config",
        "min_bars_per_day": 330,
        "window_start": "2026-10-02",
        "window_end": "2026-10-12",
    }
    b2_identity = dict(common)
    if b2_has_key:
        b2_identity["stitch_manifest_sha256"] = b2_sha
    return {
        dd.LABEL_FIELDS: SimpleNamespace(
            lineage={
                "dataset": {
                    "symbol": common["symbol"],
                    "min_bars_per_day": common["min_bars_per_day"],
                    "requested_start": common["window_start"],
                    "requested_end": common["window_end"],
                    "stitch_manifest_sha256": b1a_sha,
                },
                "strategy": {
                    "market_open_kst": common["market_open_kst"],
                    "market_open_source": common["market_open_source"],
                },
            }
        ),
        dd.LABEL_LEGACY: SimpleNamespace(
            lineage={"join": {"window_identity": b2_identity}}
        ),
    }


def test_item4_b3_refuses_a_pair_whose_only_difference_is_the_manifest_digest() -> None:
    """Plan re-review N-1: the digest is in the identity B3 actually compares."""
    assert "stitch_manifest_sha256" in dd.WINDOW_IDENTITY_FIELDS
    assert dd.B1A_IDENTITY_PROJECTION["stitch_manifest_sha256"] == (
        "dataset.stitch_manifest_sha256"
    )
    agreeing = _identity_lineages("a" * 64, "a" * 64)
    dd._check_window_identity(agreeing)  # does not raise
    with pytest.raises(dd.DiffDecisionsError, match="stitch_manifest_sha256"):
        dd._check_window_identity(_identity_lineages("a" * 64, "b" * 64))


def test_item4_b3_window_identity_refuses_a_b2_lineage_without_the_key() -> None:
    """A pre-stitch B2 paired with a stitched B1a, refused BY THE IDENTITY CHECK.

    Absence reads as ``None`` rather than raising — but it stays in the
    comparison, which is the whole point (plan §3.2a v7 re-review LOW): drop it
    and this exact pair passes.
    """
    refs = _identity_lineages("a" * 64, None, b2_has_key=False)
    assert (
        dd.b2_window_identity(refs[dd.LABEL_LEGACY].lineage)["stitch_manifest_sha256"]
        is None
    )
    with pytest.raises(dd.DiffDecisionsError, match="stitch_manifest_sha256"):
        dd._check_window_identity(refs)
    # And two pre-stitch sidecars still agree, so old artifact pairs are not
    # broken by the new field.
    dd._check_window_identity(_identity_lineages(None, None, b2_has_key=False))


# ===========================================================================
# The producer, end to end on the fixture market (items 5 and 6)
# ===========================================================================


class FakeClock:
    def __init__(self, start: datetime):
        self.moment = start.replace(tzinfo=producer_mod.KST)

    def now(self) -> datetime:
        return self.moment

    def sleep(self, seconds: float) -> None:
        self.moment += timedelta(seconds=max(0.0, seconds))


ARRIVAL_LAG_S = 1.1


class FakeQuotes:
    """GET-only by construction: it has no other method.

    No ``band`` method either, since band plan v3 (2026-10-16) moved that GET
    into its own process: a fake that still offered one would let a producer
    that called the band pass this suite.
    """

    def __init__(self, market: dict[tuple[str, date], list[dict]], clock: FakeClock):
        self.market, self.clock = market, clock
        self.http = None
        self.last_received_kst = clock.now()
        self.calls: list[tuple[str, date]] = []

    def _visible(self, symbol: str, day: date) -> list[dict]:
        rows = self.market.get((symbol, day), [])
        if day != TARGET:
            return rows
        now = self.clock.now().replace(tzinfo=None)
        return [
            row
            for row in rows
            if datetime.strptime(
                row["stck_bsop_date"] + row["stck_cntg_hour"], "%Y%m%d%H%M%S"
            )
            + timedelta(seconds=ARRIVAL_LAG_S)
            <= now
        ]

    def history(self, symbol: str, day: date) -> list[dict]:
        self.calls.append((symbol, day))
        self.clock.sleep(0.05)
        self.last_received_kst = self.clock.now()
        return self._visible(symbol, day)

    def page(self, symbol: str, day: date, cursor: str = "") -> list[dict]:
        return self.history(symbol, day)


def _write_calendar(tmp_path: Path, *, session_end: str = "09:20") -> Path:
    """The tenant calendar with a short target session, so the loop is cheap."""
    source = yaml.safe_load(
        (_REPO_ROOT / "config/tos_runtime/cp3-setup-d-long/calendar.yaml").read_text(
            encoding="utf-8"
        )
    )
    source["sessions"] = {
        "krx-index-futures": [
            {"phase": "CONTINUOUS", "start": "08:45", "end": session_end}
        ]
    }
    path = tmp_path / "calendar.yaml"
    path.write_text(yaml.safe_dump(source, allow_unicode=True), encoding="utf-8")
    return path


def _write_config(tmp_path: Path, **overrides: Any) -> Path:
    data = yaml.safe_load(
        (_REPO_ROOT / "config/tos_probes/cp3-live-producer.yaml").read_text(
            encoding="utf-8"
        )
    )
    data["calendar_yaml"] = str(_write_calendar(tmp_path))
    data["env_file"] = str(tmp_path / "env")
    data["token_cache_dir"] = str(tmp_path / "token-cache")
    data.update(overrides)
    (tmp_path / "env").write_text("KIS_FUTURES_APP_KEY=x\n", encoding="utf-8")
    path = tmp_path / "producer.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _fixture_market() -> dict[tuple[str, date], list[dict]]:
    """Four previous-month seed sessions, the splice day on both legs, today.

    The previous month's prices sit ``C_X100`` below the new month's, which is
    what makes the stored partitions and the aligned frame observably different
    in item 6.
    """
    market: dict[tuple[str, date], list[dict]] = {}
    for index, day in enumerate(SEED_DAYS):
        bars = _spiky_session(OLD, day, 3.0 + 0.2 * index, base=400.00)
        market[(OLD, day)] = [_raw_row(bar) for bar in bars]
    splice_new = _spiky_session(NEW, SPLICE, 3.6, base=400.00 + C_X100 / 100)
    market[(NEW, SPLICE)] = [_raw_row(bar) for bar in splice_new]
    today = _spiky_session(NEW, TARGET, 3.6, base=400.00 + C_X100 / 100)
    market[(NEW, TARGET)] = [_raw_row(bar) for bar in today]
    return market


@dataclass
class StitchedSession:
    """A booted producer session on disk, plus the handles the tests need."""

    producer: Any
    market: dict[tuple[str, date], list[dict]]
    out_root: Path

    @property
    def market_root(self) -> Path:
        return self.producer.market_root

    @property
    def manifest_path(self) -> Path:
        return self.market_root / STITCH_FILENAME

    def run_kwargs(
        self,
        *,
        out_name: str,
        with_manifest: bool = False,
        symbol: str = NEW,
        min_bars_per_day: int = 0,
    ) -> dict[str, Any]:
        """B1a/B2 arguments for this session, in §3.6's own shape.

        ``min_bars_per_day`` defaults to 0 here because the fixture's target
        session is deliberately truncated to keep the boundary loop short; the
        gate itself is B1a's own constant and has its own tests.
        """
        return {
            "data_root": self.market_root,
            "symbol": symbol,
            "start": SEED_DAYS[0],
            "end": TARGET,
            "strategy_yaml": _REPO_ROOT
            / "config/strategies/futures/setup_d_vwap_reversion.yaml",
            "out_dir": self.out_root / out_name,
            "min_bars_per_day": min_bars_per_day,
            "stitch_manifest": self.manifest_path if with_manifest else None,
        }


@pytest.fixture(scope="module")
def stitched_session(tmp_path_factory: pytest.TempPathFactory) -> StitchedSession:
    """Boot the producer once; every item 4-6 test reads the same session."""
    tmp_path = tmp_path_factory.mktemp("stitched")
    market = _fixture_market()
    config = config_mod.load_config(_write_config(tmp_path), repo_root=_REPO_ROOT)
    clock = FakeClock(datetime(TARGET.year, TARGET.month, TARGET.day, 9, 10))
    quotes = FakeQuotes(market, clock)
    producer = producer_mod.LiveProducer(
        config=config,
        instrument=NEW,
        target=TARGET,
        session_dir=tmp_path / "session",
        journal_path=tmp_path / "session" / "journal.jsonl",
        clock=producer_mod.Clock(now=clock.now, sleep=clock.sleep),
        quotes_factory=lambda _config, _log: quotes,
    )
    producer.boot()
    return StitchedSession(producer=producer, market=market, out_root=tmp_path / "out")


#: A target far enough past the roll that every seed day is already the new
#: month — the zero-junction case the manifest must still be written for.
UNSPLIT_TARGET = date(2026, 10, 19)
UNSPLIT_SEED_DAYS = [date(2026, 10, d) for d in (13, 14, 15, 16)]


@pytest.fixture(scope="module")
def unsplit_session(tmp_path_factory: pytest.TempPathFactory) -> StitchedSession:
    tmp_path = tmp_path_factory.mktemp("unsplit")
    market = {
        (NEW, day): [_raw_row(bar) for bar in _spiky_session(NEW, day, 3.2)]
        for day in [*UNSPLIT_SEED_DAYS, UNSPLIT_TARGET]
    }
    config = config_mod.load_config(_write_config(tmp_path), repo_root=_REPO_ROOT)
    clock = FakeClock(
        datetime(UNSPLIT_TARGET.year, UNSPLIT_TARGET.month, UNSPLIT_TARGET.day, 9, 10)
    )
    quotes = FakeQuotes(market, clock)
    producer = producer_mod.LiveProducer(
        config=config,
        instrument=NEW,
        target=UNSPLIT_TARGET,
        session_dir=tmp_path / "session",
        journal_path=tmp_path / "session" / "journal.jsonl",
        clock=producer_mod.Clock(now=clock.now, sleep=clock.sleep),
        quotes_factory=lambda _config, _log: quotes,
    )
    producer.boot()
    return StitchedSession(producer=producer, market=market, out_root=tmp_path / "out")


def test_stitch_json_is_written_on_a_session_with_no_splice_at_all(
    unsplit_session: StitchedSession,
) -> None:
    """Plan §9 MEDIUM-1: 「`stitch.json` 은 항상 쓴다」, zero junctions included.

    The B1a/B2 refusal below only protects anything if the file is always
    there. If a same-contract session left it out, the one run where an
    operator forgot ``--stitch-manifest`` would be the one run with nothing to
    forget — and a short frame would be compared against the producer's.
    """
    manifest = load_manifest(unsplit_session.manifest_path)
    assert manifest.junctions == ()
    assert [segment.contract for segment in manifest.segments] == [NEW]
    assert manifest.segments[0].days[-1] == UNSPLIT_TARGET
    assert manifest.target_days == frozenset(manifest.all_days)
    assert manifest.sha256 is not None

    kwargs = unsplit_session.run_kwargs(out_name="unsplit", with_manifest=True)
    kwargs["start"], kwargs["end"] = UNSPLIT_SEED_DAYS[0], UNSPLIT_TARGET
    result = b1a.run(**kwargs)
    # Nothing is suppressed when the only segment IS the target's.
    assert (
        result.lineage["dataset"]["stitch"][
            "non_target_segment_bars_replayed_not_emitted"
        ]
        == 0
    )
    assert result.lineage["dataset"]["stitch_manifest_sha256"] == manifest.sha256

    no_flag = unsplit_session.run_kwargs(out_name="unsplit-no-flag")
    no_flag["start"], no_flag["end"] = UNSPLIT_SEED_DAYS[0], UNSPLIT_TARGET
    with pytest.raises(ProduceFieldsError, match="no --stitch-manifest"):
        b1a.run(**no_flag)


def test_the_fixture_session_really_is_stitched(
    stitched_session: StitchedSession,
) -> None:
    """Guard the other tests: a same-contract session would make them vacuous."""
    manifest = load_manifest(stitched_session.manifest_path)
    assert [segment.contract for segment in manifest.segments] == [OLD, NEW]
    assert len(manifest.junctions) == 1
    assert manifest.junctions[0].day == SPLICE
    assert manifest.junctions[0].new_contract == NEW
    assert manifest.target_days == frozenset({TARGET})
    assert manifest.source_sha256, "the manifest does not say what it came from"
    # The splice day is the walk's own last previous-month day, not a recomputed
    # expiry (plan §9 LOW-1).
    assert manifest.segments[0].days[-1] == SPLICE
    assert stitched_session.producer.seed.contracts_used == (OLD,)


# ===========================================================================
# §3.2a 5 — one frame, one alignment, no record outside the target segment
# ===========================================================================


def _canonical(frame: Any) -> bytes:
    """A frame's content as bytes, for an EXACT comparison.

    The two frames are built by different code paths (one from parsed tuples,
    one through Parquet), so their dtypes and index differ while their CONTENT
    must not. Serialising the columns that carry meaning is the comparison that
    says so.

    ⚠ **Every float goes through ``.hex()``, not ``f"{x:.2f}"``** (review
    MEDIUM-1). The first cut formatted to two decimals, which is the published
    precision — and therefore rounds away exactly the drift this test exists to
    find: the reviewer mutated
    :func:`~tools.tos_cp3.live_producer.stitch_seed.shift_bars` to add
    ``1e-9`` and all twenty-five tests stayed green. A comparison written at
    the precision of the thing it compares cannot detect a difference below
    that precision, and "the producer's frame equals the reconstruction" is a
    claim about the bits the next ``produce_bars`` will read, not about their
    printed form. ``float.hex()`` is exact and round-trips.
    """
    ordered = frame.sort_values("timestamp").reset_index(drop=True)
    return "\n".join(
        "|".join(
            [
                str(row.timestamp),
                float(row.open).hex(),
                float(row.high).hex(),
                float(row.low).hex(),
                float(row.close).hex(),
                str(int(row.volume)),
            ]
        )
        for row in ordered.itertuples()
    ).encode("utf-8")


def test_item5_the_reconstructed_frame_equals_the_producers_own(
    stitched_session: StitchedSession,
) -> None:
    """``load_window(stitch_manifest=…)`` rebuilds exactly what the producer fed.

    This is the parity claim the whole manifest exists for: the producer runs
    ``produce_bars`` on the frame below every minute, and B1a must see the same
    one after the session or every field would differ for a reason that looks
    like a defect.
    """
    producer = stitched_session.producer
    lived = bars_to_frame(list(producer.seed.bars) + producer.frozen)
    window = b1a.load_window(
        **{
            key: value
            for key, value in stitched_session.run_kwargs(
                out_name="unused", with_manifest=True
            ).items()
            if key != "out_dir"
        },
        market_open="auto",
    )
    assert _canonical(window.df) == _canonical(lived)
    assert window.stitch is not None
    assert window.stitch.manifest.junctions[0].c_x100 == C_X100
    assert window.stitch.offsets_x100 == {OLD: C_X100, NEW: 0}
    # The splice day's new-contract partition was read for the recomputation
    # and is NOT in the frame (re-review N-3): no day carries two contracts.
    assert window.stitch.recompute_input_files
    per_day = window.df.groupby(window.df["timestamp"].dt.date)["code"].nunique()
    assert set(per_day.unique()) == {1}


def _window_kwargs(session: StitchedSession, **overrides: Any) -> dict[str, Any]:
    """``load_window`` arguments for this session (no ``out_dir``)."""
    kwargs = {
        key: value
        for key, value in session.run_kwargs(
            out_name="unused", with_manifest=True
        ).items()
        if key != "out_dir"
    }
    kwargs["market_open"] = "auto"
    kwargs.update(overrides)
    return kwargs


def test_the_density_gate_drops_a_thin_day_from_the_STITCHED_frame(
    stitched_session: StitchedSession,
) -> None:
    """The gate runs on the cross-contract frame too, with B1a's own constant.

    Review MEDIUM-2: every other stitched test passes ``min_bars_per_day=0``
    (the fixture's target session is deliberately truncated to keep the
    boundary loop short), so the gate call in ``load_stitched_bars`` was never
    executed and deleting it stayed green — a copy of the gate that nothing
    exercised. This runs the real constant over the same session and checks
    that the thin day leaves and the dense ones stay.

    The thin day here is the realistic shape, not a contrivance: a producer
    that stopped early leaves exactly this — full previous-month seed days and
    a part-written target day.
    """
    gate = b1a.DEFAULT_MIN_BARS_PER_DAY
    ungated = b1a.load_window(**_window_kwargs(stitched_session, min_bars_per_day=0))
    per_day = ungated.df.groupby(ungated.df["timestamp"].dt.date).size()
    assert 0 < per_day[TARGET] < gate, (
        f"the fixture's target day holds {per_day.get(TARGET)} bars; the test "
        "is vacuous unless it is thin"
    )
    assert all(per_day[day] >= gate for day in SEED_DAYS)

    gated = b1a.load_window(**_window_kwargs(stitched_session, min_bars_per_day=gate))
    kept = set(gated.df["timestamp"].dt.date)
    assert TARGET not in kept, "the thin target day survived the density gate"
    assert kept == set(SEED_DAYS)
    assert gated.bars_loaded == int(len(ungated.df))  # PRE-gate count, as B1a reports


def test_the_declared_window_must_be_exactly_the_manifests_span(
    stitched_session: StitchedSession,
) -> None:
    """Both directions, because only one of them was refused (review LOW-1).

    B1a and B2 take the same ``--start``/``--end``, so a window label that is
    not true of the frame is agreed on by both sides and invisible to B3. The
    wider case was silently accepted by the first cut.
    """
    b1a.load_window(**_window_kwargs(stitched_session))  # the exact span is fine
    with pytest.raises(ProduceFieldsError, match="not the stitch manifest's own span"):
        b1a.load_window(
            **_window_kwargs(stitched_session, start=date(2026, 9, 1))
        )  # wider
    with pytest.raises(ProduceFieldsError, match="not the stitch manifest's own span"):
        b1a.load_window(
            **_window_kwargs(stitched_session, end=date(2026, 10, 19))
        )  # wider
    with pytest.raises(ProduceFieldsError, match="not the stitch manifest's own span"):
        b1a.load_window(
            **_window_kwargs(stitched_session, start=SEED_DAYS[1])
        )  # narrower


def test_a_session_holding_only_the_PREVIOUS_months_partitions_is_refused(
    tmp_path: Path,
) -> None:
    """Restarting into a post-roll session directory must still be refused.

    Review LOW-2. Right after a roll the seed is entirely the previous month,
    so a producer that crashed after writing it leaves ``code=A05610`` and NO
    ``code=A05611`` at all. The first cut's check globbed the traded symbol
    only: it would find nothing, let the restart proceed, and append every
    previous-month seed day a second time — the duplicate timestamps that cost
    B1a the whole session's input.
    """
    market_root = tmp_path / "market"
    sinks_mod.append_bar_part(
        market_root,
        asset_class=producer_mod.ASSET_CLASS,
        symbol=OLD,
        bars=_flat_session(OLD, SPLICE, 400.00, 0.75)[:5],
    )
    traded = market_root / producer_mod.ASSET_CLASS / "minute" / f"code={NEW}"
    assert not traded.exists(), "the fixture must hold no partition for the traded code"

    with pytest.raises(LiveProducerRefused, match="already holds"):
        sinks_mod.refuse_if_partitions_exist(
            market_root, asset_class=producer_mod.ASSET_CLASS, symbol=NEW
        )
    # An empty tree is still accepted — the refusal is about THIS directory's
    # emptiness, not about sibling months being present anywhere.
    sinks_mod.refuse_if_partitions_exist(
        tmp_path / "fresh", asset_class=producer_mod.ASSET_CLASS, symbol=NEW
    )


def test_item5_no_record_is_emitted_for_a_non_target_segment(
    stitched_session: StitchedSession,
) -> None:
    """Plan §3.2a 「대상 종목이 아닌 구간의 레코드를 출력하지 않는다」.

    The previous month's bars advance the causal windows and are then dropped —
    counted in the lineage, never stamped with a ``raw_event_id`` naming this
    symbol, which is the label error §3.2a's truthfulness rule forbids.
    """
    result = b1a.run(
        **stitched_session.run_kwargs(out_name="b1a-stitched", with_manifest=True)
    )
    emitted_days = {record.bar_kst.date() for record in result.records}
    assert emitted_days == {TARGET}
    stitch_block = result.lineage["dataset"]["stitch"]
    dropped = stitch_block["non_target_segment_bars_replayed_not_emitted"]
    assert dropped > 0, "no previous-month bar was replayed — the test is vacuous"
    assert result.lineage["dataset"]["bars_replayed"] - result.lineage["dataset"][
        "omitted_bars"
    ]["count"] - dropped == len(result.records)
    assert (
        result.lineage["dataset"]["stitch_manifest_sha256"]
        == load_manifest(stitched_session.manifest_path).sha256
    )
    assert stitch_block["junction_recompute_only_bars"] > 0


def test_item5_b2_reads_the_same_frame_through_the_same_loader(
    stitched_session: StitchedSession,
) -> None:
    """B1a and B2 must agree on the window identity, digest included (HIGH-1)."""
    fields = b1a.run(
        **stitched_session.run_kwargs(out_name="pair-b1a", with_manifest=True)
    )
    legacy = b2.run(
        **stitched_session.run_kwargs(out_name="pair-b2", with_manifest=True)
    )
    refs = {
        dd.LABEL_FIELDS: SimpleNamespace(lineage=fields.lineage),
        dd.LABEL_LEGACY: SimpleNamespace(lineage=legacy.lineage),
    }
    identity, _entry = dd._check_window_identity(refs)
    assert identity["stitch_manifest_sha256"] == (
        load_manifest(stitched_session.manifest_path).sha256
    )
    assert [r.raw_event_id for r in fields.records] == [
        r.raw_event_id for r in legacy.records
    ]


def test_item5_b3_refuses_a_stitched_b1a_against_an_unstitched_b2(
    stitched_session: StitchedSession,
) -> None:
    """The pair plan §9 HIGH-1 is about, refused by the window-identity check."""
    fields = b1a.run(
        **stitched_session.run_kwargs(out_name="refuse-b1a", with_manifest=True)
    )
    legacy = b2.run(
        **stitched_session.run_kwargs(out_name="refuse-b2", with_manifest=True)
    )
    unstitched = json.loads(json.dumps(legacy.lineage))
    unstitched["join"]["window_identity"].pop("stitch_manifest_sha256")
    refs = {
        dd.LABEL_FIELDS: SimpleNamespace(lineage=fields.lineage),
        dd.LABEL_LEGACY: SimpleNamespace(lineage=unstitched),
    }
    with pytest.raises(dd.DiffDecisionsError, match="stitch_manifest_sha256"):
        dd._check_window_identity(refs)


# ===========================================================================
# §3.2a 6 — label and value truthfulness
# ===========================================================================


def test_item6_each_seed_partition_holds_the_unadjusted_parsed_response(
    stitched_session: StitchedSession,
) -> None:
    """What is stored is what the broker returned, under its own contract's name.

    Plan §3.2a 「라벨은 진실하게 … 조정은 저장이 아니라 읽을 때 적용한다」. The
    legacy A05611 Parquet's date-label defect (plan §6.1) is what happens when
    one instrument's values are filed under another's name, so this checks both
    halves: the right contract directory, and values equal to ``parse_ohlcv`` of
    the raw response rather than the back-adjusted ones.
    """
    from shared.storage.market_data_store import ParquetMarketDataStore

    store = ParquetMarketDataStore(
        root=stitched_session.market_root, asset_class="futures"
    )
    manifest = load_manifest(stitched_session.manifest_path)
    checked = 0
    for segment in manifest.segments:
        for day in segment.days:
            rows = stitched_session.market.get((segment.contract, day))
            if rows is None:
                continue
            expected = parse_ohlcv(
                segment.contract, day.strftime("%Y%m%d"), {"output2": rows}
            )
            stored = store.get_minute_bars(segment.contract, start=day, end=day)
            if day == TARGET:
                # Today is still being written; compare the prefix that exists.
                expected = expected[: len(stored)]
            assert len(stored) == len(expected), (segment.contract, day)
            for bar, (_, row) in zip(expected, stored.iterrows()):
                assert row["code"] == segment.contract
                assert row["datetime"].to_pydatetime() == bar[1]
                assert round(float(row["close"]) * 100) == round(bar[5] * 100)
                assert int(row["volume"]) == int(bar[6])
            checked += 1
    assert checked >= len(SEED_DAYS)

    # RED for the "unadjusted" half: the FRAME the reader builds is shifted, so
    # equality above is a statement about storage, not a tautology.
    window = b1a.load_window(
        **{
            key: value
            for key, value in stitched_session.run_kwargs(
                out_name="unused", with_manifest=True
            ).items()
            if key != "out_dir"
        },
        market_open="auto",
    )
    splice_row = window.df[window.df["timestamp"] == _stamp(SPLICE, 0)].iloc[0]
    stored_splice = store.get_minute_bars(OLD, start=SPLICE, end=SPLICE)
    stored_close = float(
        stored_splice[stored_splice["datetime"] == _stamp(SPLICE, 0)]["close"].iloc[0]
    )
    assert round(float(splice_row["close"]) * 100) - round(stored_close * 100) == C_X100


def test_the_manifest_round_trips_and_is_byte_stable(
    stitched_session: StitchedSession, tmp_path: Path
) -> None:
    """Two writes of one manifest are identical bytes, and reading gives it back."""
    manifest = load_manifest(stitched_session.manifest_path)
    again = write_manifest(tmp_path / STITCH_FILENAME, manifest)
    assert again.sha256 == manifest.sha256
    assert render_manifest(again) == render_manifest(manifest)
    assert load_manifest(tmp_path / STITCH_FILENAME).to_payload() == (
        manifest.to_payload()
    )


def test_the_source_digest_names_the_responses_the_days_were_parsed_from(
    stitched_session: StitchedSession,
) -> None:
    manifest = load_manifest(stitched_session.manifest_path)
    for segment in manifest.segments:
        for day in segment.days:
            rows = stitched_session.market.get((segment.contract, day))
            if rows is None:
                continue
            key = f"{segment.contract}:{day.isoformat()}"
            if key in manifest.source_sha256:
                assert manifest.source_sha256[key] == rows_digest(rows)
    assert f"{OLD}:{SPLICE.isoformat()}" in manifest.source_sha256
    assert f"{NEW}:{SPLICE.isoformat()}" in manifest.source_sha256


def test_b1a_refuses_a_lineage_whose_three_exit_doors_do_not_add_up(
    stitched_session: StitchedSession,
) -> None:
    """A replayed bar leaves by exactly one of three doors; the lineage says so.

    Added with the non-target counter (plan §3.2a). B2 has always asserted its
    half of this chain and B1a asserted only the first half, so a counter that
    missed a bar would publish a sidecar whose own numbers do not add up while
    B3 compared the file happily. The failing input is right here: a
    ``ProducedBars`` whose non-target count is one short.
    """
    result = b1a.run(
        **stitched_session.run_kwargs(out_name="b1a-accounting", with_manifest=True)
    )
    window = b1a.load_window(
        **{
            key: value
            for key, value in stitched_session.run_kwargs(
                out_name="unused", with_manifest=True
            ).items()
            if key != "out_dir"
        },
        market_open="auto",
    )
    produced = b1a.produce_bars(
        window.df,
        symbol=NEW,
        strategy=window.strategy,
        contract_spec=window.contract_spec,
        anchor=window.anchor,
        emit_days=window.emit_days,
    )
    short_by_one = b1a.ProducedBars(
        records=produced.records,
        bars_replayed=produced.bars_replayed,
        omitted=produced.omitted,
        non_target_segment_bars=produced.non_target_segment_bars - 1,
    )
    warmup, first_session = b1a._bar_accounting(window.df)
    kwargs = {
        "jsonl_bytes": b1a.render_jsonl(produced.records),
        "symbol": NEW,
        "strategy": window.strategy,
        "contract_spec": window.contract_spec,
        "anchor": window.anchor,
        "data_root": stitched_session.market_root,
        "requested_start": SEED_DAYS[0],
        "requested_end": TARGET,
        "min_bars_per_day": 0,
        "bars_loaded": window.bars_loaded,
        "bars_after_density_gate": int(len(window.df)),
        "warmup_skipped": warmup,
        "first_session_dropped": first_session,
        "input_files": window.input_files,
        "stitch": window.stitch,
    }
    b1a.build_lineage(produced=produced, **kwargs)  # the honest one is accepted
    with pytest.raises(ProduceFieldsError, match="non-target stitch-segment bars"):
        b1a.build_lineage(produced=short_by_one, **kwargs)
    assert result.lineage["dataset"]["bars_emitted"] == len(produced.records)


def test_the_producer_refuses_an_instrument_the_roll_function_disagrees_with() -> None:
    """``--instrument`` and the per-day walk must name the same function's output."""
    with pytest.raises(LiveProducerRefused, match="get_front_month_code"):
        StitchedSeed(
            instrument="A05612", target=TARGET, product="mini", fetch_day=_unused_fetch
        )
