"""P3 정답 — 출하 트리 다섯을 고정 구간에서 리플레이해 커밋된 결정과 대조한다.

이 파일만 CI 잡 ``tos-replay-golden`` 이 돌린다(.github/workflows/tos-firewall.yml).
고정본은 합성 분봉이다(공개 저장소 — 계획 §4.3).
"""

from __future__ import annotations

import collections
import gzip
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.tos_cp3 import replay as rp
from tools.tos_cp3 import synthetic_bars

REPO_ROOT = Path(__file__).resolve().parents[2]

GOLDEN_RUNS = rp.load_golden_config()
GOLDEN_TREES = tuple(spec.tree for spec in GOLDEN_RUNS)
BARS_DIR = GOLDEN_RUNS[0].bars_path.parent

#: 정답 표가 트리마다 반드시 담아야 하는 최소 — 진입도 청산도 없는 고정본은 규칙을
#: 하나도 지나지 않으므로, 그 정답은 「바뀌지 않았다」를 말할 힘이 없다.
MIN_SESSIONS_WITH = 3

#: 정답을 가져야 하는 트리의 정의 — 리플레이가 돌릴 수 있는 출하 트리 전부.
#: 트리를 하나 더하고 정답을 잊은 PR 을 이 핀이 잡는다.
REPLAYABLE_JOURNAL_MODE = rp.EXTERNAL_JOURNAL_MODE


def _replayable_trees() -> tuple[str, ...]:
    found: list[str] = []
    for candidate in sorted(rp.TENANT_ROOT.iterdir()):
        if not (candidate / "RENDER.yaml").is_file():
            continue
        # SAFETY: 건너뛰는 사유는 「저널을 렌더가 쓰는 트리」 하나뿐이다 — 모든 ReplayError 를 삼키면 리플레이 가능해야 할 새 트리가 다른 사유로 거부될 때 목록에서 조용히 빠지고, 아래 핀이 그 트리의 정답을 요구하지 않는다
        try:
            found.append(rp.tenant_facts(candidate).tree_id)
        except rp.ReplayJournalModeRefused:
            continue
    return tuple(found)


def test_every_replayable_shipped_tree_has_a_golden() -> None:
    assert set(_replayable_trees()) == set(GOLDEN_TREES)
    assert len(GOLDEN_TREES) == 5


#: 저널 모드만 바꿔 끼우는 최소 매니페스트 — 슬롯 하나와 그 대상 파일이 있어야
#: ``load_manifest`` 가 통과한다. 방향은 ``substitute`` 라 리플레이가 **저널 모드와
#: 무관한 사유**로 거부한다.
_TMP_MANIFEST = """tree_id: "{tree_id}"
direction:
  mode: "substitute"
journal:
  mode: "{journal_mode}"
slots:
  - file: "construction.yaml"
    key: "account"
    anchor: 'account: "TBD"'
    replacement: 'account: "{{value}}"'
    value: "account"
"""


def _tmp_tree(root: Path, *, tree_id: str, journal_mode: str) -> Path:
    """``RENDER.yaml`` 과 슬롯 대상 파일만 있는 tenant 트리 하나."""
    tree = root / tree_id
    tree.mkdir()
    (tree / "RENDER.yaml").write_text(
        _TMP_MANIFEST.format(tree_id=tree_id, journal_mode=journal_mode),
        encoding="utf-8",
    )
    (tree / "construction.yaml").write_text('account: "TBD"\n', encoding="utf-8")
    return tree


def test_a_tree_refused_for_another_reason_is_not_silently_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """저널 모드 아닌 사유로 거부된 트리는 목록에서 빠지지 않고 테스트를 깬다 (#1186)."""
    _tmp_tree(
        tmp_path, tree_id="tmp-no-direction", journal_mode=rp.EXTERNAL_JOURNAL_MODE
    )
    monkeypatch.setattr(rp, "TENANT_ROOT", tmp_path)
    with pytest.raises(rp.ReplayError, match="방향을 선언하지 않은 트리다"):
        _replayable_trees()


def test_a_tree_whose_render_writes_the_journal_is_still_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """상주 ``paper`` 트리처럼 저널을 렌더가 쓰는 트리는 정답을 요구하지 않는다."""
    _tmp_tree(tmp_path, tree_id="tmp-synthetic", journal_mode="synthetic_bootproof")
    monkeypatch.setattr(rp, "TENANT_ROOT", tmp_path)
    assert _replayable_trees() == ()


def test_every_golden_file_is_committed() -> None:
    for spec in GOLDEN_RUNS:
        assert spec.golden_path.is_file(), f"{spec.tree}: 정답 파일이 없다"
        assert spec.bars_path.is_file(), f"{spec.tree}: 고정본이 없다"


# ---------------------------------------------------------------------------
# 고정본은 합성이다 — 이 저장소는 공개돼 있다
# ---------------------------------------------------------------------------


def test_every_committed_bar_file_is_byte_equal_to_the_generator_output(
    tmp_path: Path,
) -> None:
    """커밋된 고정본은 설정의 합성 명세가 낸 **그 바이트**여야 한다."""
    # SAFETY: 이 검사가 답하는 실제 사고 — 2026-11-27, 이 작업의 첫 판이 호스트의 실제 분봉을 고정본으로 커밋했고(이 저장소는 공개다) 푸시 직전에 멈췄다. 이후 누가 실제 분봉을 이 디렉터리에 떨어뜨리면 그 파일은 생성기 출력과 바이트가 달라 여기서 빨갛게 된다
    specs = {spec.symbol: spec for spec in rp.synthetic_specs()}
    committed = sorted(path for path in BARS_DIR.iterdir() if path.is_file())
    assert committed, "고정본 디렉터리가 비어 있다"
    assert {path.name for path in committed} == {
        f"{symbol}.csv.gz" for symbol in specs
    }, "고정본 파일 집합이 synthetic 명세의 종목 집합과 다르다"
    for path in committed:
        spec = specs[path.name.removesuffix(".csv.gz")]
        rebuilt = tmp_path / path.name
        rp.write_bars_csv(synthetic_bars.build_frame(spec), rebuilt)
        assert path.read_bytes() == rebuilt.read_bytes(), (
            f"{path.name}: 커밋된 고정본이 seed={spec.seed} 명세의 출력과 다르다 — "
            "합성이 아닌 분봉이 들어왔거나, 명세를 바꾸고 "
            "`--write-synthetic-bars` 를 다시 돌리지 않았다"
        )


def test_the_committed_bars_are_on_a_tick_grid_with_positive_volume() -> None:
    """고정본의 가격은 그 종목 호가단위의 정수배이고 거래량은 양수다."""
    for spec in rp.synthetic_specs():
        frame = rp.load_bars_csv(BARS_DIR / f"{spec.symbol}.csv.gz")
        assert int(frame["volume"].min()) > 0
        for column in ("open", "high", "low", "close"):
            ticks = frame[column] / spec.tick
            assert (
                (ticks - ticks.round()).abs() < 1e-6
            ).all(), f"{spec.symbol}: {column} 이 호가단위 {spec.tick} 격자를 벗어났다"
        assert (frame["high"] >= frame["low"]).all()
        assert (frame["high"] >= frame["close"]).all()
        assert (frame["low"] <= frame["close"]).all()


@pytest.mark.parametrize("tree", GOLDEN_TREES)
def test_the_golden_says_its_bars_are_synthetic(tree: str) -> None:
    """정답 머리가 합성이라고 말하지 않으면, 아래 가상 손익이 시장 역사로 읽힌다."""
    specs = {spec.tree: spec for spec in GOLDEN_RUNS}
    text = specs[tree].golden_path.read_text(encoding="utf-8")
    assert "# bars\tsynthetic seed=" in text


@pytest.mark.parametrize("tree", GOLDEN_TREES)
def test_the_replayed_decisions_match_the_committed_golden(tree: str) -> None:
    """``--golden check`` 가 그 트리에 대해 내는 판정 그대로."""
    text, code = rp.run_golden("check", only=[tree])
    assert code == 0, text


@pytest.mark.parametrize("mode", ["check", "update"])
def test_an_unknown_only_tree_is_refused_not_passed(mode: str) -> None:
    """오타 난 ``--only`` 는 아무것도 돌리지 않은 초록이 아니라 거부다 (#1185 리뷰 MEDIUM)."""
    with pytest.raises(rp.ReplayError, match="cp3-setup-d-lng"):
        rp.run_golden(mode, only=["cp3-setup-d-lng"])


def test_the_two_futures_trees_read_the_same_bars_and_decide_differently() -> None:
    """같은 프레임에서 LONG · SHORT 가 같은 결정을 내면 방향 대칭이 깨진 것이다."""
    specs = {spec.tree: spec for spec in GOLDEN_RUNS}
    long_spec = specs["cp3-setup-d-long"]
    short_spec = specs["cp3-setup-d-short"]
    assert long_spec.bars_path == short_spec.bars_path
    long_text = long_spec.golden_path.read_text(encoding="utf-8")
    short_text = short_spec.golden_path.read_text(encoding="utf-8")
    assert "# direction\tLONG" in long_text
    assert "# direction\tSHORT" in short_text
    assert _table(long_text) != _table(short_text)


def _table(text: str) -> list[str]:
    return [line for line in text.splitlines() if not line.startswith("# ")]


@pytest.mark.parametrize("tree", GOLDEN_TREES)
def test_a_golden_header_says_what_the_table_is_of(tree: str) -> None:
    """머리 없는 표는 어느 트리 · 어느 종목 · 어느 구간의 것인지 말하지 못한다."""
    specs = {spec.tree: spec for spec in GOLDEN_RUNS}
    lines = specs[tree].golden_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == f"# {rp.GOLDEN_SCHEMA}"
    header = dict(
        line.removeprefix("# ").split("\t", 1)
        for line in lines
        if line.startswith("# ") and "\t" in line
    )
    assert header["tree"] == tree
    assert header["symbol"] == specs[tree].symbol
    assert header["evaluation"] == rp.JOURNAL_ONLY
    assert int(header["bars_counted"]) > 0
    assert int(header["sessions"]) > 0
    assert ".." in header["window"]
    assert lines[len(header) + 1].split("\t") == list(rp.GOLDEN_COLUMNS)


def test_no_golden_carries_a_real_account_or_a_host_path() -> None:
    """정답은 커밋된다 — 계좌도 호스트 경로도 들어가지 않는다."""
    for spec in GOLDEN_RUNS:
        text = spec.golden_path.read_text(encoding="utf-8")
        assert rp.FAKE_ACCOUNT not in text
        assert "/home/" not in text


# ---------------------------------------------------------------------------
# 고정본이 규칙을 실제로 지나는가
# ---------------------------------------------------------------------------


def _runs_of(tree: str) -> list[list[str]]:
    specs = {spec.tree: spec for spec in GOLDEN_RUNS}
    lines = specs[tree].golden_path.read_text(encoding="utf-8").splitlines()
    body = [line for line in lines if not line.startswith("# ")]
    return [line.split("\t") for line in body[1:]]


@pytest.mark.parametrize("tree", GOLDEN_TREES)
def test_the_golden_carries_entry_and_exit_runs_on_several_sessions(tree: str) -> None:
    """진입도 청산도 없는 정답은 「결정이 안 바뀌었다」를 증명하지 못한다.

    한 트리의 고정본이 어느 규칙도 지나지 않게 되면(가격이 너무 조용하면) 그 정답은
    기본 결정 한 줄로 남고, tenant YAML 을 바꿔도 바뀌지 않는다 — 조용히 아무것도
    지키지 않는 정답이다. 이 검사가 그것을 거부한다.
    """
    rows = _runs_of(tree)
    kinds = collections.Counter(row[3] for row in rows)
    assert kinds["ACTION"] > 0, f"{tree}: 진입(ACTION) 구간이 하나도 없다"
    assert kinds["FLAT"] > 0, f"{tree}: 청산(FLAT) 구간이 하나도 없다"
    for kind in ("ACTION", "FLAT"):
        sessions = {row[0][:10] for row in rows if row[3] == kind}
        assert len(sessions) >= MIN_SESSIONS_WITH, (
            f"{tree}: {kind} 이 {len(sessions)} 개 세션에서만 난다 "
            f"(최소 {MIN_SESSIONS_WITH})"
        )


@pytest.mark.parametrize("tree", GOLDEN_TREES)
def test_the_fired_rules_are_the_tenants_own_and_cover_entry_exit_eod(
    tree: str,
) -> None:
    """고정본에서 첫 일치가 된 규칙은 그 트리가 선언한 것들이고, 넷 이상이다.

    넷: 기본(R0) · 진입 · 되돌림/회복 청산 · EOD 청산. 그 아래로 떨어지면 고정본이
    규칙의 일부만 지나는 것이고, 지나지 않은 규칙의 변경은 정답이 못 잡는다.
    """
    declared = _declared_rule_ids(tree)
    fired = {row[4] for row in _runs_of(tree)}
    assert fired <= declared, f"{tree}: 선언에 없는 규칙 {sorted(fired - declared)}"
    assert len(fired) >= 4, f"{tree}: 첫 일치가 된 규칙이 {sorted(fired)} 뿐이다"


def _declared_rule_ids(tree: str) -> set[str]:
    """그 트리의 전략 YAML 이 선언한 규칙 id 전부 — 기본 결정까지."""
    from tools.tos_cp3 import bars_explain

    strategies = sorted((rp.TENANT_ROOT / tree / "strategies").glob("*.yaml"))
    assert len(strategies) == 1, f"{tree}: 전략 파일이 {len(strategies)} 개"
    policy = yaml.safe_load(strategies[0].read_text(encoding="utf-8"))["policy"]
    found = {
        bars_explain.rule_id_of(rule["decision"].get("rationale"))
        for rule in policy.get("rules") or []
    }
    found.add(bars_explain.rule_id_of((policy.get("default") or {}).get("rationale")))
    return {rule_id for rule_id in found if rule_id}


# ---------------------------------------------------------------------------
# 리플레이가 읽는 값 ↔ 라이브 생산자 설정 (#1186 리뷰 LOW)
# ---------------------------------------------------------------------------

PRODUCER_DIR = REPO_ROOT / "config" / "tos_probes"
# SAFETY: 선물 생산자(cp3-live-producer.yaml)는 `open_anchor: auto` 로 시대 규칙을 가리키므로 앵커 핀의 글롭에서 일부러 빠진다 — 이 글롭을 PRODUCER_GLOB 으로 넓히면 "auto" 를 HH:MM 으로 파싱하려다 깨진다(그 값의 핀은 test_cp3_replay.py 의 시대 규칙 테스트다)
STOCK_PRODUCER_GLOB = "cp3-live-producer-stock-*.yaml"
PRODUCER_GLOB = "cp3-live-producer*.yaml"


def _producer_config(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), f"{path}: 최상위가 매핑이 아니다"
    return raw


def _hhmm(value: Any) -> tuple[int, int]:
    hour_text, _, minute_text = str(value).strip().partition(":")
    return int(hour_text), int(minute_text)


def _golden_default_density() -> int:
    """정답 설정의 기본 밀도 게이트 — 리플레이가 돌릴 때 쓰는 그 값."""
    # SAFETY: 최상위 기본값이 아니라 run 마다 실제로 넘어가는 값을 본다 — run 하나가 자기 min_bars_per_day 를 덮어쓰면 그 트리만 다른 세션 집합에서 도는데 최상위 값만 보는 핀은 그것을 통과시킨다
    used = {
        spec.min_bars_per_day for spec in rp.load_golden_config(rp.GOLDEN_CONFIG_PATH)
    }
    assert (
        len(used) == 1
    ), f"{rp.GOLDEN_CONFIG_PATH}: run 들이 서로 다른 min_bars_per_day 로 돈다 ({sorted(used)})"
    return used.pop()


def test_every_stock_producer_open_anchor_is_the_one_replay_reads() -> None:
    """주식 생산자의 개장 앵커와 리플레이가 읽는 개장 시각은 같은 값이어야 한다."""
    # SAFETY: 리플레이는 생산자 설정이 아니라 market_schedule.yaml 을 읽는다 — 한쪽만 바뀌면 리플레이의 모든 봉에서 minutes_since_open 이 밀려 entry_window 가 조용히 다른 창이 되고, 결정 정답의 diff 는 그것을 규칙이 바뀐 것과 구별해 주지 않는다
    configs = sorted(PRODUCER_DIR.glob(STOCK_PRODUCER_GLOB))
    assert configs, f"{PRODUCER_DIR}/{STOCK_PRODUCER_GLOB}: 생산자 설정이 하나도 없다"
    expected = rp.configured_open("stock")
    schedule = rp.MARKET_SCHEDULE_PATH.relative_to(REPO_ROOT)
    for path in configs:
        declared = _hhmm(_producer_config(path)["open_anchor"])
        assert declared == expected, (
            f"{path.relative_to(REPO_ROOT)}::open_anchor 가 {declared} 인데 "
            f"{schedule}::market_schedule.stock.regular.open 는 {expected} 다 "
            "— 한쪽이 움직였고 리플레이는 뒤쪽만 따른다"
        )


def test_every_producer_density_gate_is_the_golden_configs_default() -> None:
    """생산자 설정의 밀도 게이트와 정답 설정의 기본값은 같은 값이어야 한다."""
    # SAFETY: 게이트는 어느 날이 프레임에 들어가는지를 정한다 — 두 값이 갈리면 리플레이와 라이브 생산자가 **다른 세션 집합**에서 돌고, 바뀐 결정이 규칙 변경 때문인지 날 집합 변경 때문인지 구별되지 않는다
    configs = sorted(PRODUCER_DIR.glob(PRODUCER_GLOB))
    assert configs, f"{PRODUCER_DIR}/{PRODUCER_GLOB}: 생산자 설정이 하나도 없다"
    expected = _golden_default_density()
    golden = rp.GOLDEN_CONFIG_PATH.relative_to(REPO_ROOT)
    carried = 0
    for path in configs:
        value = _producer_config(path).get("min_bars_per_day")
        if value is None:
            continue
        carried += 1
        assert value == expected, (
            f"{path.relative_to(REPO_ROOT)}::min_bars_per_day 가 {value} 인데 "
            f"{golden}::min_bars_per_day 는 {expected} 다 "
            "— 한쪽이 움직였고 리플레이는 뒤쪽으로 돈다"
        )
    assert (
        carried
    ), f"{PRODUCER_DIR}/{PRODUCER_GLOB}: min_bars_per_day 를 적은 설정이 하나도 없다"


def test_the_bars_fixtures_stay_small_enough_to_review() -> None:
    """고정본은 커밋된다 — 종목당 수백 KB 안에 둔다(계획 §4.3)."""
    for path in sorted(BARS_DIR.iterdir()):
        assert path.suffix == ".gz"
        packed = path.stat().st_size
        assert packed < 300_000, f"{path.name}: {packed} 바이트"
        assert len(gzip.decompress(path.read_bytes())) > 0
