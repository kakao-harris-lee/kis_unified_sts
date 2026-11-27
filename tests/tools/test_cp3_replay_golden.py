"""P3 정답 — 출하 트리 다섯을 고정 구간에서 리플레이해 커밋된 결정과 대조한다.

이 파일만 CI 잡 ``tos-replay-golden`` 이 돌린다(.github/workflows/tos-firewall.yml).
고정본은 합성 분봉이다(공개 저장소 — 계획 §4.3).
"""

from __future__ import annotations

import collections
import gzip
from pathlib import Path

import pytest

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
        try:
            found.append(rp.tenant_facts(candidate).tree_id)
        except rp.ReplayError:
            continue
    return tuple(found)


def test_every_replayable_shipped_tree_has_a_golden() -> None:
    assert set(_replayable_trees()) == set(GOLDEN_TREES)
    assert len(GOLDEN_TREES) == 5


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
    """커밋된 고정본은 설정의 합성 명세가 낸 **그 바이트**여야 한다.

    # SAFETY: 이 검사가 답하는 실제 사고 — 2026-11-27, 이 작업의 첫 판이 호스트의 실제 분봉을 고정본으로 커밋했고(이 저장소는 공개다) 푸시 직전에 멈췄다. 이후 누가 실제 분봉을 이 디렉터리에 떨어뜨리면 그 파일은 생성기 출력과 바이트가 달라 여기서 빨갛게 된다
    """
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
    import yaml

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


def test_the_bars_fixtures_stay_small_enough_to_review() -> None:
    """고정본은 커밋된다 — 종목당 수백 KB 안에 둔다(계획 §4.3)."""
    for path in sorted(BARS_DIR.iterdir()):
        assert path.suffix == ".gz"
        packed = path.stat().st_size
        assert packed < 300_000, f"{path.name}: {packed} 바이트"
        assert len(gzip.decompress(path.read_bytes())) > 0
