"""CP-3 PR-2b — the cross-contract (month-stitch) seed, plan §3.2a tests 1-6."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from shared.collector.historical.ohlcv_parser import parse_ohlcv
from tools.tos_cp3 import legacy_setup_d_driver as legacy_driver  # noqa: E402
from tools.tos_cp3 import produce_fields as b1a
from tools.tos_cp3 import stitch as stitch_mod
from tools.tos_cp3.legacy_setup_d_driver import produce_bars  # noqa: E402
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
TARGET = date(2026, 10, 12)

TENANT_TREE = _REPO_ROOT / "config" / "tos_runtime" / "cp3-setup-d-long"
SPLICE = date(2026, 10, 8)
SEED_DAYS = [date(2026, 10, 2), date(2026, 10, 6), date(2026, 10, 7), SPLICE]

OPEN_HM = (8, 45)
SESSION_BARS = 420
C_X100 = 344


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
    """One KIS ``output2`` row."""
    return {
        "stck_bsop_date": bar[1].strftime("%Y%m%d"),
        "stck_cntg_hour": bar[1].strftime("%H%M%S"),
        "futs_oprc": f"{bar[2]:.2f}",
        "futs_hgpr": f"{bar[3]:.2f}",
        "futs_lwpr": f"{bar[4]:.2f}",
        "futs_prpr": f"{bar[5]:.2f}",
        "cntg_vol": str(bar[6] if volume is None else volume),
    }


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


def test_item1_the_fixture_exercises_both_sides_of_every_gate(
    invariance_bars: list[tuple], inputs: dict
) -> None:
    """Plan §9 LOW-2: an all-permissive fixture would make item 1 vacuous."""
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
    """The same frame, shifted by ``c_x100``: differences identical, prices +c."""
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
    """The concrete input that separates the quantised shift from a naive one."""
    off_grid, one_tick = 400.025, 2
    assert (
        b1a.scaled_int_half_up(stitch_mod.shift_price_x100(off_grid, one_tick), 100)
        == 40005
    )
    assert b1a.scaled_int_half_up(off_grid + one_tick / 100.0, 100) == 40004
    for on_grid in (400.00, 400.07, 1049.00, 1052.44):
        for offset in (C_X100, one_tick, -C_X100):
            assert b1a.scaled_int_half_up(
                stitch_mod.shift_price_x100(on_grid, offset), 100
            ) == b1a.scaled_int_half_up(on_grid + offset / 100.0, 100)


def test_item1_red_a_shift_that_is_not_a_translation_moves_the_gates(
    invariance_bars: list[tuple], inputs: dict
) -> None:
    """Red proof for the test above: the invariance is a property, not a tautology."""
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


def _junction_market() -> tuple[list[tuple], list[tuple]]:
    """Two previous-month sessions, then the first new-month session."""
    old: list[tuple] = []
    for day in (date(2026, 10, 7), SPLICE):
        old.extend(_flat_session(OLD, day, 400.00, 0.75))
    new: list[tuple] = []
    for index in range(SESSION_BARS):
        if index < 16:
            new.append(_bar(NEW, TARGET, index, 410.00, 0.46))
        elif index == 16:
            new.append(
                (NEW, _stamp(TARGET, index), 410.00, 410.00, 397.50, 398.00, 120)
            )
        else:
            new.append(_bar(NEW, TARGET, index, 398.00, 0.46))
    return old, new


def test_item2_turning_the_alignment_off_flips_the_stall_guard(
    inputs: dict,
) -> None:
    """Plan §3.2a test 2 — and the red proof of the alignment clause itself."""
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
    assert fields["hi_vol"] is True
    assert abs(fields["z_x1000"]) >= threshold
    buffer_x100 = entry_config.stall_buffer_atr_mult * fields["atr14_x100"]
    assert buffer_x100 < C_X100, (C_X100, buffer_x100)
    assert fields["stall_ok"] != other["stall_ok"]
    assert fields["atr14_x100"] == other["atr14_x100"]
    assert fields["z_x1000"] == other["z_x1000"]


def _two_legs_with_different_session_ends() -> tuple[list[tuple], list[tuple]]:
    """The measured shape: the expiring month stops at 15:19, the new one 15:45."""
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

    each_legs_last = round(new[-1][5] * 100) - round(old[-1][5] * 100)
    assert each_legs_last != junction.c_x100


def test_item3_a_thin_last_common_RAW_minute_is_not_the_minute_chosen() -> None:
    """Both sides pick the last common PARSED bar (plan §3.2a re-review N-3)."""
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
    assert junction.common_minute != thin_minute
    assert junction.common_minute == new_parsed[-1][1]


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


def test_item4_b1a_refuses_a_session_dir_whose_manifest_was_not_passed(
    stitched_session: StitchedSession,
) -> None:
    """Plan §9 MEDIUM-1 / re-review N-2, with §3.6's layout taken literally."""
    assert (stitched_session.market_root / STITCH_FILENAME).is_file()
    with pytest.raises(ProduceFieldsError, match="no --stitch-manifest"):
        b1a.run(**stitched_session.run_kwargs(out_name="no-flag-b1a"))


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
    """The sign-flipped manifest plan §3.2a test 4 names."""
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


class FakeClock:
    def __init__(self, start: datetime):
        self.moment = start.replace(tzinfo=producer_mod.KST)

    def now(self) -> datetime:
        return self.moment

    def sleep(self, seconds: float) -> None:
        self.moment += timedelta(seconds=max(0.0, seconds))


ARRIVAL_LAG_S = 1.1


class FakeQuotes:
    """GET-only by construction: it has no other method."""

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
    source["session_overrides"] = {}
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
    """Four previous-month seed sessions, the splice day on both legs, today."""
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
        """B1a/B2 arguments for this session, in §3.6's own shape."""
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
        tenant_tree=TENANT_TREE,
        clock=producer_mod.Clock(now=clock.now, sleep=clock.sleep),
        quotes_factory=lambda _config, _log: quotes,
    )
    producer.boot()
    return StitchedSession(producer=producer, market=market, out_root=tmp_path / "out")


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
        tenant_tree=TENANT_TREE,
        clock=producer_mod.Clock(now=clock.now, sleep=clock.sleep),
        quotes_factory=lambda _config, _log: quotes,
    )
    producer.boot()
    return StitchedSession(producer=producer, market=market, out_root=tmp_path / "out")


def test_stitch_json_is_written_on_a_session_with_no_splice_at_all(
    unsplit_session: StitchedSession,
) -> None:
    """Plan §9 MEDIUM-1: 「`stitch.json` 은 항상 쓴다」, zero junctions included."""
    manifest = load_manifest(unsplit_session.manifest_path)
    assert manifest.junctions == ()
    assert [segment.contract for segment in manifest.segments] == [NEW]
    assert manifest.segments[0].days[-1] == UNSPLIT_TARGET
    assert manifest.target_days == frozenset(manifest.all_days)
    assert manifest.sha256 is not None

    kwargs = unsplit_session.run_kwargs(out_name="unsplit", with_manifest=True)
    kwargs["start"], kwargs["end"] = UNSPLIT_SEED_DAYS[0], UNSPLIT_TARGET
    result = b1a.run(**kwargs)
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
    assert manifest.segments[0].days[-1] == SPLICE
    assert stitched_session.producer.seed.contracts_used == (OLD,)


def _canonical(frame: Any) -> bytes:
    """A frame's content as bytes, for an EXACT comparison."""
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
    """``load_window(stitch_manifest=…)`` rebuilds exactly what the producer fed."""
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
    """The gate runs on the cross-contract frame too, with B1a's own constant."""
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
    assert gated.bars_loaded == int(len(ungated.df))


def test_the_declared_window_must_be_exactly_the_manifests_span(
    stitched_session: StitchedSession,
) -> None:
    """Both directions, because only one of them was refused (review LOW-1)."""
    b1a.load_window(**_window_kwargs(stitched_session))
    with pytest.raises(ProduceFieldsError, match="not the stitch manifest's own span"):
        b1a.load_window(**_window_kwargs(stitched_session, start=date(2026, 9, 1)))
    with pytest.raises(ProduceFieldsError, match="not the stitch manifest's own span"):
        b1a.load_window(**_window_kwargs(stitched_session, end=date(2026, 10, 19)))
    with pytest.raises(ProduceFieldsError, match="not the stitch manifest's own span"):
        b1a.load_window(**_window_kwargs(stitched_session, start=SEED_DAYS[1]))


def test_a_session_holding_only_the_PREVIOUS_months_partitions_is_refused(
    tmp_path: Path,
) -> None:
    """Restarting into a post-roll session directory must still be refused."""
    market_root = tmp_path / "market"
    sinks_mod.append_bar_part(
        market_root,
        asset_class="futures",
        symbol=OLD,
        bars=_flat_session(OLD, SPLICE, 400.00, 0.75)[:5],
    )
    traded = market_root / "futures" / "minute" / f"code={NEW}"
    assert not traded.exists(), "the fixture must hold no partition for the traded code"

    with pytest.raises(LiveProducerRefused, match="already holds"):
        sinks_mod.refuse_if_partitions_exist(
            market_root, asset_class="futures", symbol=NEW
        )
    sinks_mod.refuse_if_partitions_exist(
        tmp_path / "fresh", asset_class="futures", symbol=NEW
    )


def test_item5_no_record_is_emitted_for_a_non_target_segment(
    stitched_session: StitchedSession,
) -> None:
    """Plan §3.2a 「대상 종목이 아닌 구간의 레코드를 출력하지 않는다」."""
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


def test_item6_each_seed_partition_holds_the_unadjusted_parsed_response(
    stitched_session: StitchedSession,
) -> None:
    """What is stored is what the broker returned, under its own contract's name."""
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
                expected = expected[: len(stored)]
            assert len(stored) == len(expected), (segment.contract, day)
            for bar, (_, row) in zip(expected, stored.iterrows()):
                assert row["code"] == segment.contract
                assert row["datetime"].to_pydatetime() == bar[1]
                assert round(float(row["close"]) * 100) == round(bar[5] * 100)
                assert int(row["volume"]) == int(bar[6])
            checked += 1
    assert checked >= len(SEED_DAYS)

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
    """A replayed bar leaves by exactly one of three doors; the lineage says so."""
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
    produced = legacy_driver.produce_bars(
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
    b1a.build_lineage(produced=produced, **kwargs)
    with pytest.raises(ProduceFieldsError, match="non-target stitch-segment bars"):
        b1a.build_lineage(produced=short_by_one, **kwargs)
    assert result.lineage["dataset"]["bars_emitted"] == len(produced.records)


def test_the_producer_refuses_an_instrument_the_roll_function_disagrees_with() -> None:
    """``--instrument`` and the per-day walk must name the same function's output."""
    with pytest.raises(LiveProducerRefused, match="get_front_month_code"):
        StitchedSeed(
            instrument="A05612", target=TARGET, product="mini", fetch_day=_unused_fetch
        )
