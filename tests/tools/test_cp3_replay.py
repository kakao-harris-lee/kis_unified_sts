"""P3 — `replay.py` · `synthetic_bars.py` 단위: 저널 · 생략 봉 · 구간표 · 렌더 · 합성 분봉."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from tools.tos_cp3 import replay as rp
from tools.tos_cp3 import synthetic_bars as sb

REPO_ROOT = Path(__file__).resolve().parents[2]

FUTURES_TREE = "cp3-setup-d-long"
FUTURES_SYMBOL = "A05610"

#: 렌더 테스트가 쓰는 가짜 계좌가 적혀 있는 파일. 리플레이의 상수는 그 관례를 따르므로,
#: 그쪽이 값을 바꾸면 이 파일의 핀이 빨갛게 된다.
RENDER_TEST_PATH = (
    REPO_ROOT / "tests" / "unit" / "scripts" / "test_render_paper_config.py"
)

SESSIONS = (date(2026, 9, 14), date(2026, 9, 15))
BARS_PER_SESSION = 120


def _frame(*, zero_close_at: int | None = None) -> pd.DataFrame:
    """합성 선물 분봉 두 세션 — 삼각파라 ATR 이 0 이 아니고 값이 결정론적이다."""
    rows: list[dict[str, Any]] = []
    price = 400.0
    for day in SESSIONS:
        opening = datetime(day.year, day.month, day.day, 8, 45)
        for minute in range(BARS_PER_SESSION):
            price += 0.25 if (minute // 7) % 2 == 0 else -0.25
            rows.append(
                {
                    "timestamp": opening + timedelta(minutes=minute),
                    "open": price,
                    "high": price + 0.5,
                    "low": price - 0.5,
                    "close": price,
                    "volume": 100 + minute,
                }
            )
    if zero_close_at is not None:
        for column in ("open", "high", "low", "close"):
            rows[zero_close_at][column] = 0.0
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def replayed() -> rp.ReplayResult:
    """합성 봉으로 출하 선물 트리를 한 번 리플레이한 결과(모듈 전체가 공유)."""
    return rp.replay(
        FUTURES_TREE,
        symbol=FUTURES_SYMBOL,
        bars=_frame(),
        min_bars_per_day=0,
    )


# ---------------------------------------------------------------------------
# 저널 모양
# ---------------------------------------------------------------------------


def test_journal_rows_carry_exactly_the_keys_the_kernel_requires() -> None:
    """커널의 관측 저널은 키 하나만 비어도 그 폴 전체를 거부한다."""
    document, _record = _declaration()
    produced = rp.produce_bars_declarative(
        _frame(), symbol=FUTURES_SYMBOL, document=document
    )
    lines = (
        rp.journal_bytes(produced.records, instrument=FUTURES_SYMBOL)
        .decode("utf-8")
        .splitlines()
    )
    assert len(lines) == len(produced.records)
    for line in lines:
        row = json.loads(line)
        assert set(row) == {
            "raw_event_id",
            "source_id",
            "instrument",
            "as_of_ms",
            "fields",
        }
        assert row["instrument"] == FUTURES_SYMBOL
        assert row["source_id"] == rp.SOURCE_ID
        assert row["source_id"].startswith("tos-cp3-replay/")
        assert isinstance(row["as_of_ms"], int)
        assert row["fields"]


def test_as_of_ms_is_the_bars_own_labelled_minute() -> None:
    """``as_of_ms`` 는 그 봉의 라벨 분 — raw_event_id 의 시각과 같아야 한다."""
    document, _record = _declaration()
    produced = rp.produce_bars_declarative(
        _frame(), symbol=FUTURES_SYMBOL, document=document
    )
    for record in produced.records[:20]:
        label = rp.bar_label(
            {"raw_event_id": record.raw_event_id, "as_of_ms": record.as_of_ms}
        )
        from_as_of = datetime.fromtimestamp(record.as_of_ms / 1000, tz=rp.KST)
        assert label == from_as_of.strftime("%Y-%m-%dT%H:%M")


def _declaration() -> tuple[Any, dict[str, Any]]:
    facts = rp.tenant_facts(FUTURES_TREE)
    strategy = rp.load_strategy_inputs(rp.DEFAULT_STRATEGY_YAML)
    anchor = rp.open_anchor(
        facts,
        cli_value="auto",
        first_session=SESSIONS[0],
        last_session=SESSIONS[-1],
    )
    return rp.load_declaration(facts.tree_dir, strategy=strategy, anchor=anchor)


# ---------------------------------------------------------------------------
# 생략 봉
# ---------------------------------------------------------------------------


def test_an_unusable_bar_is_omitted_with_a_reason_and_never_journalled() -> None:
    """종가 0 인 봉은 발행되지 않고, 사유와 함께 생략으로 센다."""
    document, _record = _declaration()
    # 둘째 세션의 한 봉 — 첫 세션은 전부 웜업이라 결정 대상이 아니다.
    index = BARS_PER_SESSION + 30
    produced = rp.produce_bars_declarative(
        _frame(zero_close_at=index), symbol=FUTURES_SYMBOL, document=document
    )
    assert produced.omitted, "종가 0 인 봉이 생략으로 세지지 않았다"
    omitted_ids = {raw_event_id for raw_event_id, _reason in produced.omitted}
    assert all("close <= 0" in reason for _id, reason in produced.omitted)
    journalled = {
        json.loads(line)["raw_event_id"]
        for line in rp.journal_bytes(produced.records, instrument=FUTURES_SYMBOL)
        .decode("utf-8")
        .splitlines()
    }
    assert not (omitted_ids & journalled)


def test_the_header_and_the_text_both_name_the_omitted_bars(
    replayed: rp.ReplayResult,
) -> None:
    """생략 봉은 정답 머리의 수와 화면의 사유 줄 양쪽에 남는다."""
    with_omitted = _with_omitted(replayed)
    header = dict(rp.golden_header(with_omitted))
    assert header["bars_omitted"] == "1"
    assert "close <= 0" in rp.render_text(with_omitted)


def _with_omitted(result: rp.ReplayResult) -> rp.ReplayResult:
    import dataclasses

    return dataclasses.replace(
        result, omitted=((f"{FUTURES_SYMBOL}:1m:20260915T094500+0900", "close <= 0"),)
    )


# ---------------------------------------------------------------------------
# 결정 구간표
# ---------------------------------------------------------------------------


def test_runs_fold_consecutive_bars_with_the_same_decision() -> None:
    bars = [
        {
            "time_kst": "2026-09-15T09:00",
            "decision_kind": "NO_ACTION",
            "decision_rule_id": "R0",
        },
        {
            "time_kst": "2026-09-15T09:01",
            "decision_kind": "NO_ACTION",
            "decision_rule_id": "R0",
        },
        {
            "time_kst": "2026-09-15T09:02",
            "decision_kind": "ACTION",
            "decision_rule_id": "R1",
        },
    ]
    runs = rp.decision_runs(bars)
    assert [(run.first_kst, run.last_kst, run.bars, run.rule_id) for run in runs] == [
        ("2026-09-15T09:00", "2026-09-15T09:01", 2, "R0"),
        ("2026-09-15T09:02", "2026-09-15T09:02", 1, "R1"),
    ]


def test_a_session_boundary_breaks_a_run_even_when_the_decision_is_unchanged() -> None:
    """날이 바뀌면 새 줄 — 한 줄이 열흘을 덮으면 diff 가 어느 날인지 말하지 못한다."""
    bars = [
        {
            "time_kst": "2026-09-15T15:19",
            "decision_kind": "NO_ACTION",
            "decision_rule_id": "R0",
        },
        {
            "time_kst": "2026-09-16T09:00",
            "decision_kind": "NO_ACTION",
            "decision_rule_id": "R0",
        },
    ]
    runs = rp.decision_runs(bars)
    assert len(runs) == 2
    assert [run.bars for run in runs] == [1, 1]


def test_the_run_table_is_lossless_over_the_replayed_bars(
    replayed: rp.ReplayResult,
) -> None:
    """구간표의 봉 수 합은 점검이 낸 봉 수와 같다 — 접었을 뿐 버리지 않았다."""
    assert sum(run.bars for run in replayed.runs) == len(replayed.bars)
    assert replayed.runs


def test_golden_text_parses_back_into_the_same_runs(
    replayed: rp.ReplayResult,
) -> None:
    """정답 파일은 표 그대로 — 머리를 떼면 같은 구간들이 돌아온다."""
    lines = rp.golden_text(replayed).splitlines()
    assert lines[0] == f"# {rp.GOLDEN_SCHEMA}"
    header = [line for line in lines if line.startswith("# ")]
    body = [line for line in lines if not line.startswith("# ")]
    assert body[0].split("\t") == list(rp.GOLDEN_COLUMNS)
    assert len(header) == 1 + len(rp.golden_header(replayed))
    parsed = [
        rp.DecisionRun(
            first_kst=cells[0],
            last_kst=cells[1],
            bars=int(cells[2]),
            decision_kind=cells[3],
            rule_id=cells[4],
        )
        for cells in (line.split("\t") for line in body[1:])
    ]
    assert tuple(parsed) == replayed.runs


def test_the_golden_diff_names_the_bar_and_both_decisions() -> None:
    """``check`` 실패 출력은 리뷰어가 읽는 unified diff 다."""
    before = "x\n2026-09-15T09:05\t2026-09-15T09:08\t4\tNO_ACTION\tR0\ny\n"
    after = "x\n2026-09-15T09:05\t2026-09-15T09:08\t4\tACTION\tR1-ENTRY\ny\n"
    diff = rp.golden_diff(before, after, path=Path("golden/x.decisions.tsv"))
    assert "--- golden/x.decisions.tsv (committed)" in diff
    assert "+++ golden/x.decisions.tsv (replayed)" in diff
    assert "-2026-09-15T09:05\t2026-09-15T09:08\t4\tNO_ACTION\tR0" in diff
    assert "+2026-09-15T09:05\t2026-09-15T09:08\t4\tACTION\tR1-ENTRY" in diff


# ---------------------------------------------------------------------------
# 출하 트리 렌더 — 「그대로는 로드되지 않는다」
# ---------------------------------------------------------------------------


def test_the_shipped_tree_still_ships_with_tbd_coordinates() -> None:
    """리플레이가 렌더를 부르는 이유 — 출하 트리의 계좌·종목은 ``TBD`` 다."""
    tree = rp.TENANT_ROOT / FUTURES_TREE
    construction = (tree / "construction.yaml").read_text(encoding="utf-8")
    assert 'account: "TBD"' in construction
    assert 'instrument: "TBD"' in construction


def test_the_rendered_copy_carries_the_fake_account_and_the_symbol(
    tmp_path: Path,
) -> None:
    """임시 디렉터리의 렌더 사본에만 좌표가 채워진다 — 저장소는 그대로다."""
    result = rp.replay(
        FUTURES_TREE,
        symbol=FUTURES_SYMBOL,
        bars=_frame(),
        min_bars_per_day=0,
        workdir=tmp_path,
    )
    rendered = tmp_path / f"replay-{FUTURES_TREE}" / rp.RENDER_DIRNAME
    construction = (rendered / "construction.yaml").read_text(encoding="utf-8")
    assert f'account: "{rp.FAKE_ACCOUNT}"' in construction
    assert f'instrument: "{FUTURES_SYMBOL}"' in construction
    manifest = json.loads((rendered / "RENDERED.json").read_text(encoding="utf-8"))
    assert manifest["tree_id"] == FUTURES_TREE
    assert rp.FAKE_ACCOUNT not in (rendered / "RENDERED.json").read_text("utf-8")
    assert result.facts.direction == manifest["direction"] == "LONG"


def test_the_fake_account_is_the_one_the_render_tests_already_use() -> None:
    """가짜 계좌 값은 테스트 fixture 가 이미 쓰는 것을 쓴다(계획 §8)."""
    text = RENDER_TEST_PATH.read_text(encoding="utf-8")
    found = re.search(r'_FAKE_ACCOUNT = "(\d+)"', text)
    assert found is not None
    assert found.group(1) == rp.FAKE_ACCOUNT
    assert len(rp.FAKE_ACCOUNT) == 10 and rp.FAKE_ACCOUNT.isdigit()


def test_the_replay_reads_no_env_file() -> None:
    """실계좌의 원천은 환경 파일이다 — 리플레이는 그 어느 것도 읽지 않는다."""
    source = (REPO_ROOT / "tools" / "tos_cp3" / "replay.py").read_text("utf-8")
    assert ".env" not in source
    assert "environ" not in source


# ---------------------------------------------------------------------------
# 점검으로 넘어가는 경계
# ---------------------------------------------------------------------------


def test_every_bar_is_evaluated_from_the_journal_alone(
    replayed: rp.ReplayResult,
) -> None:
    """증거 DB 없이 돌므로 모든 봉이 ``journal_only`` 이고 ``counted`` 다."""
    assert replayed.evaluations == (rp.JOURNAL_ONLY,)
    assert replayed.counted_bars == len(replayed.bars)
    assert dict(rp.golden_header(replayed))["evaluation"] == rp.JOURNAL_ONLY


def test_only_the_second_session_is_decided_on(replayed: rp.ReplayResult) -> None:
    """첫 세션은 웜업으로 읽히고 결정은 내지 않는다(생산자의 입장 오프셋)."""
    assert replayed.sessions == SESSIONS
    decided = {str(bar["time_kst"])[:10] for bar in replayed.bars}
    assert decided == {SESSIONS[-1].isoformat()}
    assert replayed.bars_replayed == BARS_PER_SESSION


def test_the_bars_time_kst_carries_the_date(replayed: rp.ReplayResult) -> None:
    """점검의 ``HH:MM`` 에 날짜를 붙인다 — 여러 날을 한 번에 도는 리플레이이므로."""
    for bar in replayed.bars:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", str(bar["time_kst"]))


def test_the_hypothetical_pnl_block_says_what_it_is(
    replayed: rp.ReplayResult,
) -> None:
    """가상 손익은 실현 손익과 키 이름도 표기도 섞이지 않는다."""
    pnl = replayed.pnl
    assert pnl["hypothetical"] is True
    assert pnl["direction"] == "LONG"
    assert pnl["contract"] == "kospi200_mini"
    assert pnl["price_field"] == "close_x100"
    assert pnl["price_scale"] == 100
    assert "FILL_ALWAYS_ASSUMED" in pnl["assumptions"]
    assert "pnl" not in pnl["totals"]
    assert rp.PNL_LABEL in rp.render_text(replayed)


def test_the_text_output_says_what_the_replay_does_not_tell(
    replayed: rp.ReplayResult,
) -> None:
    text = rp.render_text(replayed)
    assert rp.NOT_AN_ORDER in text
    assert rp.NO_POSITION in text
    assert "A05610" in text and "futures LONG" in text


def test_the_json_output_carries_the_runs_and_the_inspection(
    replayed: rp.ReplayResult,
) -> None:
    document = json.loads(rp.render_json(replayed))
    assert document["schema"] == rp.REPLAY_SCHEMA
    assert document["tree"] == FUTURES_TREE
    assert len(document["decision_runs"]) == len(replayed.runs)
    assert document["inspection"]["bars"]
    assert document["not_an_order"] == rp.NOT_AN_ORDER


# ---------------------------------------------------------------------------
# 거부
# ---------------------------------------------------------------------------


def test_a_synthetic_journal_tree_is_refused() -> None:
    """상주 paper 트리는 자기 저널을 렌더가 쓴다 — 리플레이의 저널이 둘째 원천이 된다."""
    with pytest.raises(rp.ReplayError, match="journal.mode"):
        rp.tenant_facts("paper")


def test_an_unknown_tree_is_refused() -> None:
    with pytest.raises(rp.ReplayError, match="그런 tenant 트리가 없다"):
        rp.tenant_facts("cp3-setup-d-nope")


def test_a_futures_tree_has_no_default_symbol_and_the_cli_says_so(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """월물은 날짜에 따라 다르다 — 선물 트리는 ``--symbol`` 을 지어내지 않는다."""
    assert rp.default_symbol(rp.tenant_facts(FUTURES_TREE)) is None
    code = rp.main(["--tree", FUTURES_TREE, "--bars-csv", "/nonexistent.csv"])
    assert code == 2
    assert "--symbol 이 필요하다" in capsys.readouterr().err


def test_a_stock_tree_defaults_to_its_own_symbol() -> None:
    facts = rp.tenant_facts("cp3-setup-d-stock-000660")
    assert rp.default_symbol(facts) == "000660"
    assert facts.asset_class == "stock"


def test_both_bar_sources_at_once_are_refused(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = rp.main(
        [
            "--tree",
            FUTURES_TREE,
            "--symbol",
            FUTURES_SYMBOL,
            "--data-root",
            "/tmp",
            "--bars-csv",
            "/tmp/x.csv",
        ]
    )
    assert code == 2
    assert "정확히 하나가 필요하다" in capsys.readouterr().err


def test_a_window_with_no_sessions_left_after_the_seed_is_refused() -> None:
    with pytest.raises(rp.ReplayError, match="비교할 날이 없다"):
        rp.replay(
            FUTURES_TREE,
            symbol=FUTURES_SYMBOL,
            bars=_frame(),
            min_bars_per_day=0,
            seed_sessions=9,
        )


def test_an_anchor_the_declaration_does_not_count_from_is_refused() -> None:
    """선언이 08:45 에서 세는데 09:00 으로 돌리면 모든 entry_window 가 밀린다."""
    with pytest.raises(rp.ReplayError, match="fields.yaml"):
        rp.replay(
            FUTURES_TREE,
            symbol=FUTURES_SYMBOL,
            bars=_frame(),
            min_bars_per_day=0,
            market_open="09:00",
        )


# ---------------------------------------------------------------------------
# 고정본 CSV
# ---------------------------------------------------------------------------


def test_bars_csv_round_trips_the_frame_exactly(tmp_path: Path) -> None:
    """고정본은 값을 그대로 들고 간다 — 가격 한 자리가 바뀌면 결정이 바뀐다."""
    frame = _frame()
    path = tmp_path / "bars.csv.gz"
    assert rp.write_bars_csv(frame, path) == len(frame)
    back = rp.load_bars_csv(path)
    assert list(back.columns) == list(rp.BARS_CSV_COLUMNS)
    pd.testing.assert_frame_equal(frame[list(rp.BARS_CSV_COLUMNS)], back)


def test_the_gzip_fixture_is_byte_stable(tmp_path: Path) -> None:
    """같은 봉이면 같은 바이트 — 시각이 들어가면 커밋 diff 가 거짓말을 한다."""
    first, second = tmp_path / "a.csv.gz", tmp_path / "b.csv.gz"
    rp.write_bars_csv(_frame(), first)
    rp.write_bars_csv(_frame(), second)
    assert first.read_bytes() == second.read_bytes()


def test_a_csv_window_narrows_to_the_requested_days(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv.gz"
    rp.write_bars_csv(_frame(), path)
    narrowed = rp.load_bars_csv(path, start=SESSIONS[-1], end=SESSIONS[-1])
    assert set(narrowed["timestamp"].dt.date) == {SESSIONS[-1]}


def test_a_csv_missing_a_column_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text(
        "timestamp,open,high,low,close\n2026-09-15T09:00,1,1,1,1\n", "utf-8"
    )
    with pytest.raises(rp.ReplayError, match="열이 없다"):
        rp.load_bars_csv(path)


def test_a_csv_window_outside_the_fixture_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv.gz"
    rp.write_bars_csv(_frame(), path)
    with pytest.raises(rp.ReplayError, match="봉이 하나도 없다"):
        rp.load_bars_csv(path, start=date(2026, 1, 2), end=date(2026, 1, 3))


# ---------------------------------------------------------------------------
# 개장 앵커
# ---------------------------------------------------------------------------


def test_the_stock_anchor_comes_from_the_market_schedule_config() -> None:
    assert rp.configured_open("stock") == (9, 0)
    facts = rp.tenant_facts("cp3-setup-d-stock-005930")
    anchor = rp.open_anchor(
        facts,
        cli_value="auto",
        first_session=SESSIONS[0],
        last_session=SESSIONS[-1],
    )
    assert (anchor.hour, anchor.minute) == (9, 0)
    assert "market_schedule" in anchor.source


def test_the_futures_anchor_comes_from_the_era_rule() -> None:
    facts = rp.tenant_facts(FUTURES_TREE)
    anchor = rp.open_anchor(
        facts,
        cli_value="auto",
        first_session=SESSIONS[0],
        last_session=SESSIONS[-1],
    )
    assert (anchor.hour, anchor.minute) == (8, 45)


def test_an_unknown_market_schedule_key_is_refused() -> None:
    with pytest.raises(rp.ReplayError, match="regular.open"):
        rp.configured_open("crypto")


# ---------------------------------------------------------------------------
# 정답 설정
# ---------------------------------------------------------------------------


def test_the_golden_config_resolves_a_fixture_and_a_golden_for_every_run() -> None:
    """파일이 거기 있는지는 정답 테스트가 본다 — 여기서는 설정이 푸는 경로만."""
    runs = rp.load_golden_config()
    assert len(runs) >= 5
    for spec in runs:
        assert rp.tenant_facts(spec.tree).tree_id == spec.tree
        assert spec.min_bars_per_day == rp.DEFAULT_MIN_BARS_PER_DAY
        assert spec.bars_path.name.endswith(".csv.gz")
        assert spec.golden_path.name == f"{spec.tree}.decisions.tsv"


def test_a_golden_config_with_the_wrong_schema_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "golden.yaml"
    path.write_text("schema: nope\nruns: []\n", encoding="utf-8")
    with pytest.raises(rp.ReplayError, match="schema"):
        rp.load_golden_config(path)


def test_a_golden_config_with_no_runs_is_refused(tmp_path: Path) -> None:
    """정답 0 건은 초록이 아니라 거부다 — 비어 있는 등록부는 아무것도 지키지 않는다."""
    path = tmp_path / "golden.yaml"
    path.write_text(f"schema: {rp.GOLDEN_SCHEMA}\nruns: []\n", encoding="utf-8")
    with pytest.raises(rp.ReplayError, match="runs"):
        rp.load_golden_config(path)


def test_a_golden_config_without_a_synthetic_block_is_refused(tmp_path: Path) -> None:
    """고정본이 어디서 왔는지 말하지 못하는 설정은 거부한다(공개 저장소)."""
    path = tmp_path / "golden.yaml"
    path.write_text(f"schema: {rp.GOLDEN_SCHEMA}\nruns: []\n", encoding="utf-8")
    with pytest.raises(rp.ReplayError, match="synthetic"):
        rp.synthetic_specs(path)


# ---------------------------------------------------------------------------
# 합성 분봉
# ---------------------------------------------------------------------------


def _spec(**overrides: Any) -> sb.SyntheticSpec:
    base: dict[str, Any] = {
        "symbol": "A05610",
        "market": "futures",
        "seed": 7,
        "sessions": 3,
        "first_session": date(2026, 9, 1),
        "session_open": time(8, 45),
        "session_last": time(15, 34),
        "base_price": 420.0,
        "tick": 0.02,
        "price_decimals": 2,
        "vol_ticks": 2.2,
        "volume_base": 600,
        "volume_jitter": 900,
        "process": sb.ProcessParams(
            dev_persistence=0.985,
            anchor_drift_ticks=0.22,
            overnight_gap_ticks=9.0,
            burst_probability=0.012,
            burst_min_bars=25,
            burst_max_bars=75,
            burst_vol_mult=2.6,
            session_vol_sigma=0.42,
            wick_mult=0.9,
            volume_burst_mult=2.0,
        ),
    }
    base.update(overrides)
    return sb.SyntheticSpec(**base)


def test_the_generator_is_deterministic_for_a_seed() -> None:
    """같은 씨앗이면 같은 행 — 커밋된 고정본을 다시 뽑을 수 있어야 한다."""
    assert sb.generate_rows(_spec()) == sb.generate_rows(_spec())


def test_a_different_seed_gives_different_bars() -> None:
    assert sb.generate_rows(_spec()) != sb.generate_rows(_spec(seed=8))


def test_the_generator_uses_no_numpy_rng() -> None:
    """판 사이에서 흔들리지 않게 표준 라이브러리 ``random`` 만 쓴다."""
    source = (REPO_ROOT / "tools" / "tos_cp3" / "synthetic_bars.py").read_text("utf-8")
    assert "import random" in source
    assert "numpy" not in source
    assert "np.random" not in source


def test_every_session_is_a_full_contiguous_minute_range() -> None:
    """세션마다 개장부터 마지막 분까지 빈 분 없이 — 밀도 게이트를 넘어야 한다."""
    spec = _spec()
    frame = sb.build_frame(spec)
    assert spec.bars_per_session == 410
    per_session = frame.groupby(frame["timestamp"].dt.date).size()
    assert set(per_session) == {410}
    assert len(per_session) == spec.sessions
    assert all(day.weekday() < 5 for day in per_session.index)
    assert (per_session > rp.DEFAULT_MIN_BARS_PER_DAY).all()
    first = frame["timestamp"].iloc[0]
    assert (first.hour, first.minute) == (8, 45)


def test_prices_sit_on_the_tick_grid_and_ohlc_relations_hold() -> None:
    frame = sb.build_frame(_spec())
    for column in ("open", "high", "low", "close"):
        ticks = frame[column] / 0.02
        assert ((ticks - ticks.round()).abs() < 1e-6).all()
    assert (frame["high"] >= frame[["open", "close"]].max(axis=1)).all()
    assert (frame["low"] <= frame[["open", "close"]].min(axis=1)).all()
    assert (frame["volume"] > 0).all()
    assert (frame["low"] > 0).all()


def test_a_stock_spec_keeps_integer_prices() -> None:
    frame = sb.build_frame(
        _spec(
            symbol="005930",
            market="stock",
            session_open=time(9, 0),
            session_last=time(15, 19),
            base_price=72000,
            tick=100,
            price_decimals=0,
            vol_ticks=0.55,
        )
    )
    assert set(frame.groupby(frame["timestamp"].dt.date).size()) == {380}
    assert (frame["close"] % 100 == 0).all()


def test_a_spec_whose_volatility_would_cross_zero_is_refused() -> None:
    """0 이하 가격은 생략 게이트에 걸려 고정본을 조용히 짧게 만든다 — 먼저 거부한다."""
    with pytest.raises(sb.SyntheticBarsError, match="0 이하"):
        sb.generate_rows(_spec(base_price=0.1, vol_ticks=50.0))


def test_a_session_window_that_is_not_a_window_is_refused() -> None:
    backwards = _spec(session_open=time(15, 0), session_last=time(9, 0))
    with pytest.raises(sb.SyntheticBarsError, match="session_last"):
        assert backwards.bars_per_session


def test_the_shipped_spec_set_is_the_four_fixture_symbols() -> None:
    specs = {spec.symbol: spec for spec in rp.synthetic_specs()}
    assert set(specs) == {"005930", "000660", "005380", "A05610"}
    assert specs["A05610"].market == "futures"
    assert {spec.seed for spec in specs.values()} == {
        2026112701,
        2026112702,
        2026112703,
        2026112704,
    }
    for spec in specs.values():
        assert spec.sessions == 14
        assert rp.synthetic_source(spec) == f"synthetic seed={spec.seed}"


def test_the_synthetic_session_open_matches_the_market_schedule() -> None:
    """합성 세션의 개장은 설정의 정규장 개장이고, 트리 선언이 세는 기준과 같다."""
    for spec in rp.synthetic_specs():
        hour, minute = rp.configured_open(spec.market)
        assert (spec.session_open.hour, spec.session_open.minute) == (hour, minute)
