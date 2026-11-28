#!/usr/bin/env python3
"""P3 — 과거 분봉으로 tenant 의 봉별 결정을 다시 내고 커밋된 정답과 대조한다."""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import gzip
import io
import json
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_RENDER_SCRIPT_DIR = REPO_ROOT / "scripts" / "tos"
if str(_RENDER_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_RENDER_SCRIPT_DIR))

import render_paper_config as rpc  # noqa: E402

from tools.tos_cp3 import (  # noqa: E402
    TOS_CP3_VERSION,
    bars_explain,
    export_bars,
    hypothetical_pnl,
    inspect_session,
    synthetic_bars,
)
from tools.tos_cp3.fields_equivalence import (  # noqa: E402
    DEFAULT_STRATEGY_YAML,
    _contract_spec,
)
from tools.tos_cp3.live_producer.declaration import (  # noqa: E402
    LiveProducerRefused,
    fields_yaml_of,
    load_declaration,
)
from tools.tos_cp3.produce_fields import (  # noqa: E402
    DEFAULT_MIN_BARS_PER_DAY,
    AssetClass,
    FieldRecord,
    OpenAnchor,
    ProduceFieldsError,
    _apply_density_gate,
    _asset_class,
    load_bars,
    load_strategy_inputs,
    produce_bars_declarative,
    resolve_open_anchor,
)

__all__ = [
    "BARS_CSV_COLUMNS",
    "ENTRY_REFUSED_LABEL",
    "ENTRY_SIZE_DENIED",
    "ENTRY_UNIT_UNAVAILABLE",
    "FAKE_ACCOUNT",
    "FAKE_REVISION",
    "GAP_EXIT_FIRST_VISIBLE_BAR",
    "GAP_REENTRY_NEXT_BAR",
    "GOLDEN_COLUMNS",
    "GOLDEN_CONFIG_PATH",
    "GOLDEN_SCHEMA",
    "LIVE_GAP_LABEL",
    "SIMULATED_MODE",
    "SIMULATED_POSITION",
    "SOURCE_ID",
    "DecisionRun",
    "GoldenRun",
    "ReplayError",
    "ReplayJournalModeRefused",
    "ReplayResult",
    "TenantFacts",
    "bar_label",
    "decision_runs",
    "golden_diff",
    "golden_text",
    "journal_bytes",
    "load_bars_csv",
    "load_golden_config",
    "main",
    "render_json",
    "render_runs",
    "render_text",
    "replay",
    "run_golden",
    "synthetic_source",
    "synthetic_specs",
    "tenant_facts",
    "write_bars_csv",
    "write_synthetic_bars",
]

KST = ZoneInfo("Asia/Seoul")

REPLAY_SCHEMA = "tos-replay/1"
GOLDEN_SCHEMA = "tos-replay-golden/1"

SOURCE_ID = f"tos-cp3-replay/{TOS_CP3_VERSION}"

GOLDEN_CONFIG_PATH = REPO_ROOT / "config" / "tos_replay_golden.yaml"
TENANT_ROOT = REPO_ROOT / "config" / "tos_runtime"
MARKET_SCHEDULE_PATH = REPO_ROOT / "config" / "market_schedule.yaml"

JOURNAL_NAME = "journal.jsonl"
RENDER_DIRNAME = "render"
BAND_JOURNAL_NAME = "band.jsonl"

EXTERNAL_JOURNAL_MODE = "external"

# SAFETY: 실계좌가 아닌 열 자리 더미 — 렌더 테스트(tests/unit/scripts/test_render_*.py)가
# 쓰는 바로 그 값이고, 이 모듈은 환경 파일도 실계좌도 읽지 않는다
FAKE_ACCOUNT = "9999999999"
# SAFETY: 결정 경로가 읽지 않는 자리값 — 진짜 커밋 SHA 를 넣으면 같은 봉에서 정답 파일이
# 커밋마다 달라져 결정이 바뀐 것과 구별되지 않는다
FAKE_REVISION = "0" * 40

#: 저널 라벨의 모양. 커널 측(``tos/runtime/cp3/inspect_session.py``)과
#: ``produce_fields.derive_raw_event_id`` 가 쓰는 같은 모양을 다시 적는다 — 방화벽상
#: 그 모듈을 import 할 수 없다.
BAR_KEY_SEPARATOR = ":1m:"
BAR_KEY_STAMP_FORMAT = "%Y%m%dT%H%M%S%z"

BARS_CSV_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
BARS_CSV_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

GOLDEN_COLUMNS = ("first_kst", "last_kst", "bars", "decision_kind", "rule_id")
MISSING = "-"

#: 점검이 증거 없이 돈 봉의 평가 출처. 정답 머리에 적어 둬서, 이 값이 바뀌면(증거가
#: 섞이면) 정답 diff 가 먼저 말한다.
JOURNAL_ONLY = "journal_only"

#: 점검이 «리플레이에서 시뮬레이션한 포지션» 에 쓰는 토큰. 방화벽상 그 모듈
#: (``tos/runtime/cp3/position_sim.py::POSITION_MODE_SIMULATED``)을 import 할 수 없어
#: 여기 다시 적는다.
SIMULATED_MODE = "simulated"

#: 점검이 내는 «라이브가 재현하지 못할 수 있는 결정» 두 수의 키. 같은 이유로(방화벽상
#: ``tos/runtime/cp3/position_sim.py`` 를 import 할 수 없어) 여기 다시 적는다.
GAP_REENTRY_NEXT_BAR = "reentry_next_bar"
GAP_EXIT_FIRST_VISIBLE_BAR = "exit_first_visible_bar"

#: 점검이 내는 «라이브의 수량 도출이 거부해 열지 않은 진입» 두 수의 키. 같은 이유로
#: 여기 다시 적는다. ``entry_unit_unavailable`` 은 그 봉이 리스크 단위 자체를 인정하지
#: 못한 것(없음 · 정수 아님 · 양수 아님)이고, ``entry_size_denied`` 는 단위는 읽혔지만
#: 그 수량을 저작된 lot 정책 · 수량 상·하한 · 명목 한도가 거부한 것이다.
ENTRY_UNIT_UNAVAILABLE = "entry_unit_unavailable"
ENTRY_SIZE_DENIED = "entry_size_denied"

NOT_AN_ORDER = (
    "리플레이는 신호만 본다 — 승인 · 예약 · venue 한도 · 시간 인정 같은 커널 단계는 "
    "지나지 않는다(계획 §6)."
)
NO_POSITION = (
    "포지션을 모른다 — 청산 규칙은 보유 여부와 무관하게 발화하고, 가상 손익이 "
    "진입-청산을 짝짓는다."
)
#: 포지션을 켠 트리에서 :data:`NO_POSITION` 자리에 들어가는 문장. 체결 모델 한 줄과
#: «세션을 넘어 유지된다» 는 점검이 낸 문서에서 그대로 읽어 붙인다.
SIMULATED_POSITION = "포지션을 시뮬레이션한다"
#: 두 수가 세는 것 — 시뮬레이션에는 없고 라이브에는 있는 공백(:data:`SIMULATED_POSITION`
#: 줄의 체결 모델 문장이 그 공백을 말한다).
LIVE_GAP_LABEL = "라이브가 재현하지 못할 수 있는 결정"

ENTRY_REFUSED_LABEL = "라이브의 수량 도출이 거부해 열지 않은 진입"
PNL_LABEL = "가상 손익(체결 가정)"


class ReplayError(RuntimeError):
    """리플레이가 거부한 사유 — 지어낸 결정보다 거부가 낫다."""


class ReplayJournalModeRefused(ReplayError):
    """저널을 렌더가 쓰는 트리 — 리플레이가 건넬 외부 저널 자리가 없다."""


@dataclass(frozen=True)
class TenantFacts:
    """출하 트리가 자기 ``RENDER.yaml`` 로 선언한, 리플레이가 읽는 전부."""

    tree_id: str
    tree_dir: Path
    market: str
    asset_class: AssetClass
    direction: str
    instrument_pattern: str | None
    declares_band: bool


@dataclass(frozen=True)
class DecisionRun:
    """결정이 같은 연속 봉 한 묶음 — 정답 표의 한 줄."""

    first_kst: str
    last_kst: str
    bars: int
    decision_kind: str
    rule_id: str


@dataclass(frozen=True)
class ReplayResult:
    """한 트리 한 구간의 리플레이 결과."""

    facts: TenantFacts
    symbol: str
    anchor: OpenAnchor
    sessions: tuple[date, ...]
    emitted_sessions: tuple[date, ...]
    bars_replayed: int
    bars_emitted: int
    omitted: tuple[tuple[str, str], ...]
    document: dict[str, Any]
    runs: tuple[DecisionRun, ...]
    pnl: dict[str, Any]
    # SAFETY: 분봉이 어디서 왔는지는 정답 머리에 실린다 — 합성 가격으로 뽑은 가상 손익을
    # 시장 역사로 읽는 것을 막는 유일한 표시다
    bars_source: str = MISSING

    @property
    def bars(self) -> list[dict[str, Any]]:
        """점검이 낸 봉 목록 — ``time_kst`` 는 날짜까지 붙은 것이다."""
        raw = self.document.get("bars")
        return list(raw) if isinstance(raw, list) else []

    @property
    def counted_bars(self) -> int:
        return sum(1 for bar in self.bars if bar.get("counted") is True)

    @property
    def position(self) -> dict[str, Any]:
        """점검이 낸 ``position`` 블록 — 꺼진 트리는 ``mode`` 가 ``None`` 이다."""
        raw = self.document.get("position")
        return dict(raw) if isinstance(raw, dict) else {}

    @property
    def position_mode(self) -> str | None:
        """``"simulated"`` · ``"recorded"``, 또는 포지션을 켜지 않은 트리면 ``None``."""
        mode = self.position.get("mode")
        return mode if isinstance(mode, str) else None

    @property
    def round_trips(self) -> list[dict[str, Any]]:
        """시뮬레이션이 낸 왕복 — 가상 손익이 세는 바로 그 체결들."""
        raw = self.position.get("round_trips")
        return [dict(trip) for trip in raw] if isinstance(raw, list) else []

    @property
    def live_gap(self) -> dict[str, int]:
        """시뮬레이션에 없고 라이브에 있는 공백의 크기 — 점검이 센 두 수."""
        raw = self.position.get("live_gap")
        source = raw if isinstance(raw, dict) else {}
        return {
            key: int(source.get(key) or 0)
            for key in (GAP_REENTRY_NEXT_BAR, GAP_EXIT_FIRST_VISIBLE_BAR)
        }

    @property
    def entry_refusals(self) -> dict[str, int]:
        """리플레이가 **열지 않은** 진입의 수 — 라이브의 도출도 거부하는 봉들."""
        raw = self.position.get("entry_refusals")
        source = raw if isinstance(raw, dict) else {}
        return {
            key: int(source.get(key) or 0)
            for key in (ENTRY_UNIT_UNAVAILABLE, ENTRY_SIZE_DENIED)
        }

    @property
    def simulation(self) -> dict[str, Any] | None:
        """리플레이가 쓴 체결 모델의 사실들, 또는 포지션을 켜지 않은 트리면 ``None``."""
        raw = self.position.get("simulation")
        # SAFETY: 모드가 simulated 일 때만 사실들을 내놓는다 — 다른 모드(기록된 세션)의 값을 여기로 흘리면 머리와 정답 머리가 시뮬레이션하지 않은 것을 시뮬레이션했다고 적는다
        if self.position_mode != SIMULATED_MODE or not isinstance(raw, dict):
            return None
        return dict(raw)

    @property
    def position_line(self) -> str:
        """머리에 적히는 포지션 한 줄 — 꺼진 트리는 §6 의 «포지션을 모른다»."""
        simulation = self.simulation
        if simulation is None:
            return NO_POSITION
        return (
            f"{SIMULATED_POSITION} — {simulation.get('fill_model')} "
            f"{simulation.get('carries_across_sessions')} "
            f"(price {simulation.get('price_field_key')} · "
            f"held_qty {simulation.get('held_qty')} "
            f"[{simulation.get('held_qty_source')}])"
        )

    @property
    def evaluations(self) -> tuple[str, ...]:
        return tuple(sorted({str(bar.get("evaluation")) for bar in self.bars}))

    @property
    def decided_sessions(self) -> tuple[str, ...]:
        """결정이 **난** 날들. 프레임의 첫 세션은 생산자의 웜업이 먹으므로 여기 없다."""
        return tuple(sorted({str(bar.get("time_kst"))[:10] for bar in self.bars}))

    @property
    def window(self) -> str:
        # SAFETY: 표가 덮는 구간은 결정이 난 날들이다 — 프레임의 구간을 적으면 머리의
        # 세션 수와 아래 봉 수가 어긋나고, 리뷰어가 웜업 세션을 빠진 날로 읽는다
        decided = self.decided_sessions
        if not decided:
            return MISSING
        return f"{decided[0]}..{decided[-1]}"

    @property
    def frame_window(self) -> str:
        """읽어 들인 프레임의 구간 — 웜업 세션까지 포함한다."""
        if not self.emitted_sessions:
            return MISSING
        return f"{self.emitted_sessions[0]}..{self.emitted_sessions[-1]}"


def tenant_facts(tree: str | Path) -> TenantFacts:
    """``RENDER.yaml`` 을 읽어 그 트리가 리플레이 가능한지까지 판정한다."""
    candidate = Path(tree)
    tree_dir = candidate if candidate.is_dir() else TENANT_ROOT / str(tree)
    if not tree_dir.is_dir():
        raise ReplayError(
            f"{tree_dir}: 그런 tenant 트리가 없다 (이름은 {TENANT_ROOT} 아래에서 찾는다)"
        )
    try:
        manifest = rpc.load_manifest(tree_dir)
    except rpc.RenderError as exc:
        raise ReplayError(f"{tree_dir}: 렌더 매니페스트를 읽지 못했다 — {exc}") from exc
    if manifest.journal_mode != EXTERNAL_JOURNAL_MODE:
        # SAFETY: 이 사유만 자기 예외형을 갖는 이유는 호출자가 사유 **하나만** 건너뛰고 나머지 거부는 전부 올려야 하기 때문이다 — 문구로 거르면 메시지 한 줄 바꾸는 PR 에서 리플레이 가능해야 할 트리가 정답 없이 조용히 빠진다
        raise ReplayJournalModeRefused(
            f"{manifest.tree_id}: journal.mode 가 {manifest.journal_mode!r} 다. "
            "리플레이는 자기가 만든 저널을 외부 저널로 건네므로 "
            f"{EXTERNAL_JOURNAL_MODE!r} 트리만 돌린다"
        )
    if manifest.direction_value is None:
        raise ReplayError(
            f"{manifest.tree_id}: 방향을 선언하지 않은 트리다. 방향이 가상 손익의 부호를 "
            "정하므로 LONG 으로 가정하지 않고 거부한다"
        )
    if manifest.market is None:
        raise ReplayError(
            f"{manifest.tree_id}: RENDER.yaml 이 market 을 선언하지 않는다 — 분봉을 어느 "
            "자산군 저장소에서 읽고 어느 계약 규격을 쓸지 정할 수 없다"
        )
    try:
        asset_class = _asset_class(manifest.market)
    except ProduceFieldsError as exc:
        raise ReplayError(f"{manifest.tree_id}: {exc}") from exc
    return TenantFacts(
        tree_id=manifest.tree_id,
        tree_dir=tree_dir,
        market=manifest.market,
        asset_class=asset_class,
        direction=manifest.direction_value,
        instrument_pattern=manifest.instrument_pattern,
        declares_band=any(slot.value == "band_journal_path" for slot in manifest.slots),
    )


def default_symbol(facts: TenantFacts) -> str | None:
    """트리가 종목을 하나로 못박았으면 그 종목, 아니면 ``None``."""
    pattern = facts.instrument_pattern
    if pattern is None or not pattern.isalnum():
        # SAFETY: 리터럴이 아닌 패턴(월물 여럿을 받는 선물 트리)에서 종목을 지어내면
        # 날짜와 맞지 않는 월물로 리플레이가 돌아 결정이 조용히 다른 계약의 것이 된다
        return None
    return pattern


def configured_open(market: str) -> tuple[int, int]:
    """``config/market_schedule.yaml`` 의 그 시장 정규장 개장 시각."""
    try:
        raw = yaml.safe_load(MARKET_SCHEDULE_PATH.read_text(encoding="utf-8")) or {}
        value = raw["market_schedule"][market]["regular"]["open"]
        hour_text, minute_text = str(value).strip().split(":")[:2]
        hour, minute = int(hour_text), int(minute_text)
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
        # SAFETY: 폴백 없이 거부한다 — 앵커가 15분 밀리면 모든 봉의 entry_window 가 함께
        # 밀리고, 발행된 bool 은 자기가 밀렸다는 것을 말할 수 없다
        raise ReplayError(
            f"{MARKET_SCHEDULE_PATH}: market_schedule.{market}.regular.open 을 읽지 "
            f"못했다 ({exc})"
        ) from exc
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ReplayError(
            f"{MARKET_SCHEDULE_PATH}: market_schedule.{market}.regular.open "
            f"{value!r} 이 HH:MM 이 아니다"
        )
    return hour, minute


def open_anchor(
    facts: TenantFacts, *, cli_value: str, first_session: date, last_session: date
) -> OpenAnchor:
    """이 구간의 개장 앵커 — 선물은 시대 규칙, 주식은 설정의 정규장 개장."""
    if cli_value != "auto" or facts.asset_class == "futures":
        try:
            return resolve_open_anchor(
                cli_value=cli_value,
                first_session=first_session,
                last_session=last_session,
            )
        except ProduceFieldsError as exc:
            raise ReplayError(str(exc)) from exc
    hour, minute = configured_open(facts.market)
    return OpenAnchor(hour, minute, f"config/market_schedule.yaml::{facts.market}")


def journal_bytes(records: Sequence[FieldRecord], *, instrument: str) -> bytes:
    """발행된 봉들을 커널이 읽는 관측 저널 한 벌로."""
    lines = []
    for record in records:
        payload = {
            "raw_event_id": record.raw_event_id,
            "source_id": SOURCE_ID,
            "instrument": instrument,
            "as_of_ms": record.as_of_ms,
            "fields": record.fields,
        }
        lines.append(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
    return "".join(f"{line}\n" for line in lines).encode("utf-8")


def bar_label(bar: Mapping[str, Any]) -> str:
    """한 봉의 **날짜까지** 붙은 KST 시각."""
    raw = str(bar.get("raw_event_id") or "")
    _, _, stamp = raw.partition(BAR_KEY_SEPARATOR)
    try:
        labelled = datetime.strptime(stamp, BAR_KEY_STAMP_FORMAT)
    except ValueError:
        as_of = bar.get("as_of_ms")
        if not isinstance(as_of, int) or isinstance(as_of, bool):
            return MISSING
        labelled = datetime.fromtimestamp(as_of / 1000, tz=KST)
    return labelled.astimezone(KST).strftime("%Y-%m-%dT%H:%M")


def decision_runs(bars: Sequence[Mapping[str, Any]]) -> tuple[DecisionRun, ...]:
    """봉별 결정을 구간표로 접는다 — 세션이 바뀌거나 결정이 바뀌면 새 줄."""
    runs: list[DecisionRun] = []
    for bar in bars:
        kind = str(bar.get("decision_kind") or MISSING)
        rule_id = str(bar.get("decision_rule_id") or MISSING)
        label = str(bar.get("time_kst") or bar_label(bar))
        session = label[:10]
        if (
            runs
            and runs[-1].decision_kind == kind
            and runs[-1].rule_id == rule_id
            and runs[-1].last_kst[:10] == session
        ):
            previous = runs[-1]
            runs[-1] = dataclasses.replace(
                previous, last_kst=label, bars=previous.bars + 1
            )
            continue
        runs.append(
            DecisionRun(
                first_kst=label,
                last_kst=label,
                bars=1,
                decision_kind=kind,
                rule_id=rule_id,
            )
        )
    return tuple(runs)


def load_bars_csv(
    path: Path, *, start: date | None = None, end: date | None = None
) -> Any:
    """고정본 CSV(``.csv`` 또는 ``.csv.gz``)를 생산자가 읽는 프레임 모양으로."""
    import pandas as pd

    try:
        data = (
            gzip.decompress(path.read_bytes())
            if path.suffix == ".gz"
            else path.read_bytes()
        )
    except (OSError, gzip.BadGzipFile) as exc:
        raise ReplayError(f"{path}: 고정본을 읽지 못했다 ({exc})") from exc
    try:
        frame = pd.read_csv(io.BytesIO(data))
    except ValueError as exc:
        raise ReplayError(f"{path}: CSV 로 읽히지 않는다 ({exc})") from exc
    missing = [name for name in BARS_CSV_COLUMNS if name not in frame.columns]
    if missing:
        raise ReplayError(
            f"{path}: 열이 없다 {missing} — 고정본은 "
            f"{','.join(BARS_CSV_COLUMNS)} 를 가진다"
        )
    frame = frame[list(BARS_CSV_COLUMNS)].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    if frame.empty:
        raise ReplayError(f"{path}: 봉이 없다")
    return _window(frame, start=start, end=end, where=str(path))


def _window(frame: Any, *, start: date | None, end: date | None, where: str) -> Any:
    """``[start, end]`` 안의 봉만. 둘 다 ``None`` 이면 프레임 그대로."""
    if start is None and end is None:
        return frame
    days = frame["timestamp"].dt.date
    keep = days.map(
        lambda day: (start is None or day >= start) and (end is None or day <= end)
    )
    narrowed = frame[keep].reset_index(drop=True)
    if narrowed.empty:
        raise ReplayError(f"{where}: {start}..{end} 구간에 봉이 하나도 없다")
    return narrowed


def write_bars_csv(frame: Any, path: Path) -> int:
    """프레임을 고정본 CSV 로 쓴다 — 열만 추리고 값은 그대로."""
    text = frame[list(BARS_CSV_COLUMNS)].to_csv(
        index=False, date_format=BARS_CSV_TIME_FORMAT
    )
    payload = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        # SAFETY: mtime=0 — 시각이 들어가면 같은 봉으로 만든 고정본이 매번 다른 바이트가
        # 되어 커밋 diff 가 «데이터가 바뀌었다» 로 읽힌다
        path.write_bytes(gzip.compress(payload, mtime=0))
    else:
        path.write_bytes(payload)
    return int(len(frame))


def replay(
    tree: str | Path,
    *,
    symbol: str,
    bars: Any,
    min_bars_per_day: int = DEFAULT_MIN_BARS_PER_DAY,
    strategy_yaml: Path = DEFAULT_STRATEGY_YAML,
    market_open: str = "auto",
    seed_sessions: int = 0,
    bars_source: str = MISSING,
    workdir: Path | None = None,
) -> ReplayResult:
    """분봉 → 필드 → 결정 → 가상 손익. 임시 디렉터리 하나만 쓴다."""
    facts = tenant_facts(tree)
    if workdir is not None:
        return _replay_in(
            workdir,
            facts,
            symbol=symbol,
            frame=bars,
            min_bars_per_day=min_bars_per_day,
            strategy_yaml=strategy_yaml,
            market_open=market_open,
            seed_sessions=seed_sessions,
            bars_source=bars_source,
        )
    with tempfile.TemporaryDirectory(prefix="tos-replay-") as temporary:
        return _replay_in(
            Path(temporary),
            facts,
            symbol=symbol,
            frame=bars,
            min_bars_per_day=min_bars_per_day,
            strategy_yaml=strategy_yaml,
            market_open=market_open,
            seed_sessions=seed_sessions,
            bars_source=bars_source,
        )


def _replay_in(
    workdir: Path,
    facts: TenantFacts,
    *,
    symbol: str,
    frame: Any,
    min_bars_per_day: int,
    strategy_yaml: Path,
    market_open: str,
    seed_sessions: int,
    bars_source: str = MISSING,
) -> ReplayResult:
    """:func:`replay` 의 본체 — 작업 디렉터리가 정해진 뒤."""
    try:
        gated = _apply_density_gate(
            frame, min_bars_per_day=min_bars_per_day, loaded=int(len(frame))
        )
    except ProduceFieldsError as exc:
        raise ReplayError(str(exc)) from exc
    sessions = tuple(sorted({stamp.date() for stamp in gated["timestamp"]}))
    emitted = sessions[seed_sessions:]
    if not emitted:
        raise ReplayError(
            f"비교할 날이 없다: 프레임의 세션 {len(sessions)} 개 중 "
            f"{seed_sessions} 개를 시드로 뺐다"
        )
    anchor = open_anchor(
        facts,
        cli_value=market_open,
        first_session=sessions[0],
        last_session=sessions[-1],
    )
    try:
        strategy = load_strategy_inputs(strategy_yaml)
        document, _record = load_declaration(
            facts.tree_dir, strategy=strategy, anchor=anchor
        )
        produced = produce_bars_declarative(
            gated,
            symbol=symbol,
            document=document,
            emit_days=frozenset(emitted) if seed_sessions else None,
        )
    except (ProduceFieldsError, LiveProducerRefused) as exc:
        raise ReplayError(f"{facts.tree_id}: {exc}") from exc

    inspected, render_dir = _inspect_rendered(
        workdir, facts, symbol=symbol, records=produced.records
    )
    bars = inspected.get("bars")
    bars = bars if isinstance(bars, list) else []
    for bar in bars:
        # SAFETY: 점검의 `time_kst` 는 «HH:MM» 뿐이다 — 여러 날을 한 번에 도는 리플레이에서
        # 날짜를 붙이지 않으면 다른 날 09:31 두 개가 한 줄로 접히고 거래도 날짜 없이 적힌다
        bar["time_kst"] = bar_label(bar)
    fills = _relabel_fills(inspected, bars)

    return ReplayResult(
        facts=facts,
        symbol=symbol,
        anchor=anchor,
        sessions=sessions,
        emitted_sessions=tuple(emitted),
        bars_replayed=produced.bars_replayed,
        bars_emitted=len(produced.records),
        omitted=tuple(produced.omitted),
        document=inspected,
        runs=decision_runs(bars),
        pnl=_hypothetical(
            facts, symbol=symbol, render_dir=render_dir, bars=bars, fills=fills
        ),
        bars_source=bars_source,
    )


def _relabel_fills(
    inspected: dict[str, Any], bars: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    """시뮬레이션 체결의 시각을 **날짜까지** 붙인 라벨로 바꾸고 그 체결을 돌려준다."""
    position = inspected.get("position")
    if not isinstance(position, dict) or position.get("mode") != SIMULATED_MODE:
        return None
    labels = {str(bar.get("raw_event_id")): str(bar.get("time_kst")) for bar in bars}
    raw_trips = position.get("round_trips")
    round_trips = raw_trips if isinstance(raw_trips, list) else []
    for trip in round_trips:
        for side in ("entry", "exit"):
            label = labels.get(str(trip.get(f"{side}_raw_event_id")))
            if label is not None:
                trip[f"{side}_time_kst"] = label
    open_entry = position.get("open_fill")
    if isinstance(open_entry, dict):
        label = labels.get(str(open_entry.get("entry_raw_event_id")))
        if label is not None:
            open_entry["entry_time_kst"] = label
    else:
        open_entry = None
    return {"round_trips": round_trips, "open_entry": open_entry}


def _inspect_rendered(
    workdir: Path,
    facts: TenantFacts,
    *,
    symbol: str,
    records: Sequence[FieldRecord],
) -> tuple[dict[str, Any], Path]:
    """저널을 쓰고 트리를 렌더해, ``sts tos inspect`` 와 같은 하위 프로세스로 넘긴다."""
    session_dir = workdir / f"replay-{facts.tree_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    journal_path = session_dir / JOURNAL_NAME
    journal_path.write_bytes(journal_bytes(records, instrument=symbol))
    try:
        rendered = rpc.render(
            facts.tree_dir,
            session_dir / RENDER_DIRNAME,
            account=FAKE_ACCOUNT,
            instrument=symbol,
            revision=FAKE_REVISION,
            direction=facts.direction,
            journal_path=journal_path,
            band_journal_path=(
                session_dir / BAND_JOURNAL_NAME if facts.declares_band else None
            ),
        )
    except rpc.RenderError as exc:
        raise ReplayError(f"{facts.tree_id}: 렌더가 거부했다 — {exc}") from exc

    # SAFETY: 증거 없이(`with_evidence=False`) 돈다 — 이 세션은 엔진이 돈 적이 없으므로
    # 잎을 열라고 하면 거부되고, 열 수 있는 잎이 있으면 다른 날의 증거를 붙인다
    outcome = inspect_session.run(
        session=str(session_dir), as_json=True, with_evidence=False
    )
    if outcome.exit_code != 0:
        raise ReplayError(
            f"{facts.tree_id}: 점검이 거부했다 (exit {outcome.exit_code}) — "
            f"{outcome.stderr.strip() or '(사유 없음)'}"
        )
    try:
        inspected = json.loads(outcome.stdout)
    except json.JSONDecodeError as exc:
        raise ReplayError(
            f"{facts.tree_id}: 점검 출력이 JSON 이 아니다 ({exc})"
        ) from exc
    if not isinstance(inspected, dict):
        raise ReplayError(
            f"{facts.tree_id}: 점검이 JSON 객체가 아니라 "
            f"{type(inspected).__name__} 를 냈다"
        )
    inspected["schema"] = REPLAY_SCHEMA
    return inspected, rendered.out


def _hypothetical(
    facts: TenantFacts,
    *,
    symbol: str,
    render_dir: Path,
    bars: Sequence[Mapping[str, Any]],
    fills: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """«체결됐다면» 손익 — 가격 필드 · 배수 · 프로브 표 전부 설정에서."""
    fields_doc = yaml.safe_load(
        fields_yaml_of(facts.tree_dir).read_text(encoding="utf-8")
    )
    try:
        field, scale = export_bars._price_field(render_dir, fields_doc)
        spec = _contract_spec(
            symbol,
            asset_class=facts.asset_class,
            execution_yaml=export_bars.CONTRACT_SPEC_CONFIG,
        )
    except (bars_explain.ExplainRefusal, ValueError, TypeError, KeyError) as exc:
        raise ReplayError(
            f"{facts.tree_id}: 가격 필드 또는 계약 규격을 읽지 못해 가상 손익을 셀 수 "
            f"없다 ({type(exc).__name__}: {exc})"
        ) from exc
    contract = hypothetical_pnl.Contract(
        name=spec.name,
        multiplier_krw_per_point=spec.multiplier_krw_per_point,
        price_field=field,
        price_scale=scale,
    )
    return hypothetical_pnl.build_hypothetical_pnl(
        bars,
        direction=facts.direction,
        contract=contract,
        instrument=symbol,
        probe_rule_ids=bars_explain.load_probe_rule_ids(),
        # SAFETY: 과거 구간은 끝난 세션이다 — 닫지 않으면 진입만 있고 결과 없는 날이
        # 조용히 좋아 보인다
        session_ended=True,
        # SAFETY: 포지션을 켠 트리는 시뮬레이션이 낸 체결을 그대로 센다 — 여기서 결정을 다시 짝지으면 체결 모델이 둘이 되고, 표가 보여 준 손절 봉과 합계의 거래가 서로 다른 것을 말한다(계획 §4 S3)
        fills=fills,
    )


def _position_header(result: ReplayResult) -> tuple[tuple[str, str], ...]:
    """포지션을 켠 트리만 갖는 머리 줄 — 꺼진 트리의 정답은 바이트 동일하게 남는다."""
    facts = result.simulation
    if facts is None:
        return ()
    gap = result.live_gap
    return (
        ("position", SIMULATED_MODE),
        ("position_price_field", str(facts.get("price_field_key"))),
        ("position_bar_interval_ms", str(facts.get("bar_interval_ms"))),
        ("position_held_qty", str(facts.get("held_qty"))),
        ("position_round_trips", str(len(result.round_trips))),
        # SAFETY: 정답 머리는 공백의 크기도 적는다 — 「position simulated」만 적힌 머리는 그 표가 라이브와 같다는 주장으로 읽히고, 다음 단계가 그 표에서 손절·목표 임계를 고른다
        (f"position_{GAP_REENTRY_NEXT_BAR}", str(gap[GAP_REENTRY_NEXT_BAR])),
        (
            f"position_{GAP_EXIT_FIRST_VISIBLE_BAR}",
            str(gap[GAP_EXIT_FIRST_VISIBLE_BAR]),
        ),
    )


def golden_header(result: ReplayResult) -> tuple[tuple[str, str], ...]:
    """정답 파일의 머리 — 표가 무엇의 표인지."""
    return (
        ("tree", result.facts.tree_id),
        ("symbol", result.symbol),
        # SAFETY: 분봉의 출처를 머리에 적는다 — 합성 가격으로 뽑은 아래 결정과 가상 손익을
        # 시장 역사로 읽으면 없던 성과를 읽는 것이 된다
        ("bars", result.bars_source),
        ("market", result.facts.market),
        ("direction", result.facts.direction),
        ("open_anchor", result.anchor.kst),
        ("window", result.window),
        ("sessions", str(len(result.decided_sessions))),
        ("frame_window", result.frame_window),
        ("bars_replayed", str(result.bars_replayed)),
        ("bars_emitted", str(result.bars_emitted)),
        ("bars_omitted", str(len(result.omitted))),
        ("bars_counted", str(result.counted_bars)),
        ("evaluation", ",".join(result.evaluations) or MISSING),
    ) + _position_header(result)


def golden_text(result: ReplayResult) -> str:
    """커밋되는 정답 파일 그대로."""
    lines = [f"# {GOLDEN_SCHEMA}"]
    lines += [f"# {key}\t{value}" for key, value in golden_header(result)]
    lines.append("\t".join(GOLDEN_COLUMNS))
    lines += [
        "\t".join(
            (
                run.first_kst,
                run.last_kst,
                str(run.bars),
                run.decision_kind,
                run.rule_id,
            )
        )
        for run in result.runs
    ]
    return "\n".join(lines) + "\n"


def golden_diff(expected: str, actual: str, *, path: Path) -> str:
    """리뷰어가 읽는 unified diff — «어느 봉의 결정이 무엇에서 무엇으로»."""
    return "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"{_relative(path)} (committed)",
            tofile=f"{_relative(path)} (replayed)",
            n=2,
        )
    )


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


@dataclass(frozen=True)
class GoldenRun:
    """정답 한 건 — 어느 트리를 어느 고정본으로 돌려 어느 파일과 대조하나."""

    tree: str
    symbol: str
    bars_path: Path
    golden_path: Path
    min_bars_per_day: int
    seed_sessions: int


def _int_or(value: Any, default: int) -> int:
    """설정의 정수 한 칸 — 키가 없으면 기본값."""
    return default if value is None else int(value)


def _golden_document(path: Path) -> dict[str, Any]:
    """정답 설정 YAML 한 벌."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ReplayError(f"{path}: 정답 설정을 읽지 못했다 ({exc})") from exc
    if not isinstance(raw, dict):
        raise ReplayError(f"{path}: 최상위가 매핑이 아니다")
    if raw.get("schema") != GOLDEN_SCHEMA:
        raise ReplayError(
            f"{path}: schema 가 {raw.get('schema')!r} 다 — {GOLDEN_SCHEMA!r} 를 기대한다"
        )
    return raw


def synthetic_specs(
    path: Path = GOLDEN_CONFIG_PATH, *, symbols: Sequence[str] | None = None
) -> tuple[synthetic_bars.SyntheticSpec, ...]:
    """고정본을 만드는 합성 분봉 명세 — 설정의 ``synthetic`` 블록 그대로."""
    try:
        return synthetic_bars.specs_from_config(
            _golden_document(path), where=_relative(path), symbols=symbols
        )
    except synthetic_bars.SyntheticBarsError as exc:
        raise ReplayError(str(exc)) from exc


def synthetic_source(spec: synthetic_bars.SyntheticSpec) -> str:
    """정답 머리에 적히는 분봉 출처 — 합성이고, 어느 씨앗인지."""
    return f"synthetic seed={spec.seed}"


def write_synthetic_bars(path: Path = GOLDEN_CONFIG_PATH) -> list[tuple[Path, int]]:
    """설정의 종목 전부를 고정본으로 쓴다 — 커밋되는 분봉은 이것뿐이다."""
    bars_dir = REPO_ROOT / str(_golden_document(path).get("bars_dir") or "")
    written: list[tuple[Path, int]] = []
    for spec in synthetic_specs(path):
        target = bars_dir / f"{spec.symbol}.csv.gz"
        try:
            frame = synthetic_bars.build_frame(spec)
        except synthetic_bars.SyntheticBarsError as exc:
            raise ReplayError(str(exc)) from exc
        written.append((target, write_bars_csv(frame, target)))
    return written


def load_golden_config(path: Path = GOLDEN_CONFIG_PATH) -> tuple[GoldenRun, ...]:
    """``config/tos_replay_golden.yaml`` — 정답 집합은 설정이지 코드가 아니다."""
    raw = _golden_document(path)
    bars_dir = REPO_ROOT / str(raw.get("bars_dir") or "")
    golden_dir = REPO_ROOT / str(raw.get("golden_dir") or "")
    default_density = _int_or(raw.get("min_bars_per_day"), DEFAULT_MIN_BARS_PER_DAY)
    entries = raw.get("runs")
    if not isinstance(entries, list) or not entries:
        raise ReplayError(
            f"{path}: 'runs' 목록이 없다 — 정답 0 건은 초록이 아니라 거부다"
        )
    runs: list[GoldenRun] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReplayError(f"{path}: runs 항목이 매핑이 아니다 ({entry!r})")
        for key in ("tree", "symbol", "bars"):
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise ReplayError(f"{path}: runs 항목에 {key!r} 가 없다 ({entry!r})")
        tree = str(entry["tree"])
        runs.append(
            GoldenRun(
                tree=tree,
                symbol=str(entry["symbol"]),
                bars_path=bars_dir / str(entry["bars"]),
                golden_path=golden_dir / f"{tree}.decisions.tsv",
                min_bars_per_day=_int_or(
                    entry.get("min_bars_per_day"), default_density
                ),
                seed_sessions=_int_or(entry.get("seed_sessions"), 0),
            )
        )
    return tuple(runs)


def run_golden(
    mode: str,
    *,
    config_path: Path = GOLDEN_CONFIG_PATH,
    only: Iterable[str] = (),
) -> tuple[str, int]:
    """다섯 트리를 한 번에 — ``check`` 는 unified diff, ``update`` 는 덮어쓴다."""
    wanted = frozenset(only)
    lines: list[str] = []
    failures = 0
    sources = {
        item.symbol: synthetic_source(item) for item in synthetic_specs(config_path)
    }
    specs = load_golden_config(config_path)
    unknown = sorted(wanted - {spec.tree for spec in specs})
    if unknown:
        # SAFETY: 오타 난 --only 가 아무것도 돌리지 않고 exit 0 을 내면 리플레이하지 않은 트리가 통과로 읽힌다.
        raise ReplayError(
            f"{_relative(config_path)}: --only 가 가리킨 트리가 없다: "
            f"{', '.join(unknown)} — 아는 트리: "
            f"{', '.join(sorted(spec.tree for spec in specs))}"
        )
    for spec in specs:
        if wanted and spec.tree not in wanted:
            continue
        if spec.symbol not in sources:
            raise ReplayError(
                f"{_relative(config_path)}: {spec.symbol} 의 synthetic 명세가 없다 — "
                "커밋된 고정본이 어디서 왔는지 말할 수 없으면 정답을 쓰지 않는다"
            )
        frame = load_bars_csv(spec.bars_path)
        result = replay(
            spec.tree,
            symbol=spec.symbol,
            bars=frame,
            min_bars_per_day=spec.min_bars_per_day,
            seed_sessions=spec.seed_sessions,
            bars_source=sources[spec.symbol],
        )
        actual = golden_text(result)
        if mode == "update":
            previous = (
                spec.golden_path.read_text(encoding="utf-8")
                if spec.golden_path.is_file()
                else None
            )
            spec.golden_path.parent.mkdir(parents=True, exist_ok=True)
            spec.golden_path.write_text(actual, encoding="utf-8")
            state = "unchanged" if previous == actual else "wrote"
            lines.append(
                f"{state} {_relative(spec.golden_path)} "
                f"({len(result.runs)} runs, {result.counted_bars} bars)"
            )
            continue
        if not spec.golden_path.is_file():
            failures += 1
            lines.append(
                f"FAIL {spec.tree}: {_relative(spec.golden_path)} 가 없다 — "
                "`--golden update` 로 만들고 그 diff 를 리뷰에 싣는다"
            )
            continue
        expected = spec.golden_path.read_text(encoding="utf-8")
        if expected == actual:
            lines.append(
                f"ok   {spec.tree} ({len(result.runs)} runs, "
                f"{result.counted_bars} bars)"
            )
            continue
        failures += 1
        lines.append(f"FAIL {spec.tree}: 결정이 커밋된 정답과 다르다")
        lines.append(golden_diff(expected, actual, path=spec.golden_path).rstrip("\n"))
    if failures:
        lines.append(
            f"{failures} 개 트리의 결정이 바뀌었다. 의도한 변경이면 "
            "`python -m tools.tos_cp3.replay --golden update` 로 정답을 갱신해 같은 PR 에 "
            "싣는다 — 그 diff 가 리뷰 대상이다."
        )
    return "\n".join(lines) + "\n", (1 if failures else 0)


def _rule_labels(result: ReplayResult) -> tuple[tuple[str, str], ...]:
    """``(라벨, 규칙 id)`` — 점검 요약이 센 규칙 순서 그대로."""
    summary = result.document.get("summary")
    rules = summary.get("rules") if isinstance(summary, dict) else None
    if not isinstance(rules, list):
        return ()
    return tuple(
        (str(rule.get("label")), str(rule.get("rule_id")))
        for rule in rules
        if isinstance(rule, dict)
    )


def _per_session(result: ReplayResult) -> list[dict[str, Any]]:
    """날짜마다 — 봉 수 · 규칙별 발화 봉 수 · 그날 진입한 가상 거래의 손익."""
    labels = [label for label, _rule_id in _rule_labels(result)]
    rows: dict[str, dict[str, Any]] = {}
    for bar in result.bars:
        day = str(bar.get("time_kst") or MISSING)[:10]
        row = rows.setdefault(
            day, {"session": day, "bars": 0, "fired": dict.fromkeys(labels, 0)}
        )
        row["bars"] = int(row["bars"]) + 1
        views = bar.get("rules")
        if not isinstance(views, list):
            continue
        for view in views:
            if isinstance(view, dict) and view.get("fired") is True:
                label = str(view.get("label"))
                if label in row["fired"]:
                    row["fired"][label] += 1
    for trade in result.pnl.get("trades") or []:
        # SAFETY: 진입한 날에 올린다 — 날을 넘겨 청산된 거래를 청산일에 올리면 그날
        # 포지션을 열지도 않은 세션의 줄에 손익이 서고 진입일 줄은 빈다
        day = str(trade.get("entry_time_kst") or MISSING)[:10]
        entered = rows.get(day)
        if entered is None:
            continue
        entered["trades"] = _int_or(entered.get("trades"), 0) + 1
        entered["hypothetical_pnl_krw"] = str(
            _int_or(entered.get("hypothetical_pnl_krw"), 0)
            + int(float(trade.get("hypothetical_pnl_krw") or 0))
        )
    return [rows[key] for key in sorted(rows)]


def render_text(result: ReplayResult) -> str:
    """사람이 읽는 세 덩이 — 머리 · 날짜별 한 줄 · 가상 거래."""
    facts = result.facts
    lines = [
        f"리플레이 {facts.tree_id} · {result.symbol} "
        f"({facts.market} {facts.direction}) · 분봉 {result.bars_source}",
        f"구간 {result.window} · 세션 {len(result.decided_sessions)} · "
        f"결정 봉 {result.counted_bars} · 생략 봉 {len(result.omitted)} · "
        f"개장 {result.anchor.kst} ({result.anchor.source})",
        NOT_AN_ORDER,
        result.position_line,
        "",
    ]
    if result.omitted:
        reasons = sorted({reason for _id, reason in result.omitted})
        lines += [f"생략 사유: {'; '.join(reasons)}", ""]

    labels = [label for label, _rule_id in _rule_labels(result)]
    header = ["날짜".ljust(10), "봉".rjust(5)]
    header += [label.rjust(5) for label in labels]
    header += ["왕복".rjust(5), f"{PNL_LABEL}(원)".rjust(18)]
    lines.append(" ".join(header))
    for row in _per_session(result):
        cells = [str(row["session"]).ljust(10), str(row["bars"]).rjust(5)]
        cells += [str(row["fired"].get(label, 0)).rjust(5) for label in labels]
        cells += [str(row.get("trades", 0)).rjust(5)]
        cells += [_krw(row.get("hypothetical_pnl_krw")).rjust(18)]
        lines.append(" ".join(cells))
    for label, rule_id in _rule_labels(result):
        lines.append(f"  {label} = {rule_id}")
    lines.append("")

    totals = result.pnl.get("totals") or {}
    lines.append(
        f"{PNL_LABEL} — 가정: {', '.join(result.pnl.get('assumptions') or ())}"
    )
    lines.append(
        " ".join(
            [
                "진입".ljust(16),
                "규칙".ljust(18),
                "청산".ljust(16),
                "규칙".ljust(18),
                "포인트".rjust(10),
                "원".rjust(14),
            ]
        )
    )
    for trade in result.pnl.get("trades") or []:
        lines.append(
            " ".join(
                [
                    str(trade.get("entry_time_kst") or MISSING).ljust(16),
                    str(trade.get("entry_rule_id") or MISSING).ljust(18),
                    str(trade.get("exit_time_kst") or MISSING).ljust(16),
                    str(trade.get("exit_rule_id") or MISSING).ljust(18),
                    str(trade.get("points") or MISSING).rjust(10),
                    _krw(trade.get("hypothetical_pnl_krw")).rjust(14),
                ]
            )
        )
    lines.append(
        f"합계: 왕복 {totals.get('trades', 0)} · 승 {totals.get('wins', 0)} · "
        f"강제 청산 {totals.get('forced_closes', 0)} · "
        f"포인트 {totals.get('points') or MISSING} · "
        f"{PNL_LABEL} {_krw(totals.get('hypothetical_pnl_krw'))} 원"
    )
    skipped = result.pnl.get("skipped_decisions") or []
    unpriced = result.pnl.get("unpriced_decisions") or []
    if skipped or unpriced:
        lines.append(
            f"합계에서 뺀 결정 봉: 엔진 것이 아님 {len(skipped)} · "
            f"종가 없음 {len(unpriced)}"
        )
    lines += _round_trip_lines(result)
    return "\n".join(lines) + "\n"


def _round_trip_lines(result: ReplayResult) -> list[str]:
    """시뮬레이션이 낸 왕복 표 — 꺼진 트리에서는 한 줄도 나오지 않는다."""
    if result.simulation is None:
        return []
    gap = result.live_gap
    lines = ["", f"시뮬레이션 체결 — 왕복 {len(result.round_trips)}"]
    lines.append(
        f"{LIVE_GAP_LABEL}: {GAP_REENTRY_NEXT_BAR} "
        f"{gap[GAP_REENTRY_NEXT_BAR]} · {GAP_EXIT_FIRST_VISIBLE_BAR} "
        f"{gap[GAP_EXIT_FIRST_VISIBLE_BAR]} — 라이브는 전송이 미결인 봉에 포지션 "
        "이름공간이 없어 이 결정을 미루거나 내지 않는다"
    )
    refused = result.entry_refusals
    # SAFETY: 리스크 단위를 필드에서 읽는 트리의 「열지 않은 진입」 수를 사유별로 적는다 — 적지 않으면 진입이 적었던 날이 규칙 때문인지, 그 필드의 결손 때문인지, 수량이 봉투 밖이었기 때문인지 표만 보고는 알 수 없다
    lines.append(
        f"{ENTRY_REFUSED_LABEL}: "
        + " · ".join(f"{key} {refused[key]}" for key in refused)
        + " — 라이브의 수량 도출도 그 봉의 전송을 거부한다"
    )
    lines.append(
        " ".join(
            [
                "진입".ljust(16),
                "규칙".ljust(18),
                "청산".ljust(16),
                "규칙".ljust(18),
                "보유봉".rjust(6),
                "미실현".rjust(10),
                "bp".rjust(7),
            ]
        )
    )
    for trip in result.round_trips:
        lines.append(
            " ".join(
                [
                    str(trip.get("entry_time_kst") or MISSING).ljust(16),
                    str(trip.get("entry_rule_id") or MISSING).ljust(18),
                    str(trip.get("exit_time_kst") or MISSING).ljust(16),
                    str(trip.get("exit_rule_id") or MISSING).ljust(18),
                    str(trip.get("bars_held") or 0).rjust(6),
                    str(trip.get("unrealized") or 0).rjust(10),
                    str(trip.get("unrealized_bp") or 0).rjust(7),
                ]
            )
        )
    open_fill = result.position.get("open_fill")
    if isinstance(open_fill, dict):
        lines.append(
            f"미청산: {open_fill.get('entry_time_kst')} "
            f"{open_fill.get('entry_rule_id')} @ {open_fill.get('entry_price')}"
        )
    return lines


def _krw(value: Any) -> str:
    """원 표기 — 거래가 없는 날은 0 이 아니라 «없음» 이다."""
    if value is None or value == "":
        return MISSING
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return str(value)


def render_runs(result: ReplayResult) -> str:
    """결정 구간표만 — 정답 파일과 같은 모양."""
    return golden_text(result)


def render_json(result: ReplayResult) -> str:
    """기계용 — 머리 · 날짜별 · 구간표 · 가상 손익 · 점검 문서 전체."""
    document = {
        "schema": REPLAY_SCHEMA,
        "tree": result.facts.tree_id,
        "symbol": result.symbol,
        "market": result.facts.market,
        "direction": result.facts.direction,
        "open_anchor": {
            "kst": result.anchor.kst,
            "source": result.anchor.source,
        },
        "bars_source": result.bars_source,
        "window": result.window,
        "frame_window": result.frame_window,
        "frame_sessions": [day.isoformat() for day in result.emitted_sessions],
        "sessions": list(result.decided_sessions),
        "bars_replayed": result.bars_replayed,
        "bars_emitted": result.bars_emitted,
        "bars_counted": result.counted_bars,
        "omitted_bars": [
            {"raw_event_id": raw_event_id, "reason": reason}
            for raw_event_id, reason in result.omitted
        ],
        "not_an_order": NOT_AN_ORDER,
        # SAFETY: 키 이름은 고정이고 값이 그 실행의 포지션 문장이다 — 포지션을 켠 트리에서 「포지션을 모른다」가 남아 있으면 시뮬레이션한 손절을 신호 없는 발화로 읽는다
        "no_position": result.position_line,
        "position": result.position,
        "per_session": _per_session(result),
        "decision_runs": [dataclasses.asdict(run) for run in result.runs],
        "hypothetical_pnl": result.pnl,
        "inspection": result.document,
    }
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools.tos_cp3.replay",
        description=(
            "과거 분봉 위에서 출하 tenant 트리의 봉별 결정과 가상 손익을 다시 낸다. "
            "읽기 전용이고 주문 경로가 없다 — 신호만 본다."
        ),
    )
    parser.add_argument("--tree", default=None, help="tenant 트리 이름, 또는 그 경로")
    parser.add_argument(
        "--symbol",
        default=None,
        help="종목/월물 코드 (주식 트리는 기본값이 트리의 종목, 선물 트리는 필수)",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="분봉 Parquet 저장소 (호스트에만 있다; --from/--to 가 함께 필요하다)",
    )
    parser.add_argument(
        "--bars-csv",
        type=Path,
        default=None,
        help=(
            f"커밋된 합성 고정본 CSV/CSV.GZ ({','.join(BARS_CSV_COLUMNS)}) — "
            "시세 데이터는 커밋하지 않는다(저장소가 공개다)"
        ),
    )
    parser.add_argument(
        "--from",
        dest="window_from",
        type=date.fromisoformat,
        default=None,
        help="구간 시작 (포함). 앞 세션은 웜업으로 쓰이므로 보고 싶은 날보다 앞에 둔다",
    )
    parser.add_argument(
        "--to",
        dest="window_to",
        type=date.fromisoformat,
        default=None,
        help="구간 끝 (포함)",
    )
    parser.add_argument(
        "--seed-sessions",
        type=int,
        default=0,
        help="앞의 N 세션은 시드로만 쓰고 결정은 내지 않는다 (기본 0)",
    )
    parser.add_argument(
        "--min-bars-per-day",
        type=int,
        default=DEFAULT_MIN_BARS_PER_DAY,
        help=f"이보다 얇은 세션은 통째로 버린다 (기본 {DEFAULT_MIN_BARS_PER_DAY}, 0 은 해제)",
    )
    parser.add_argument(
        "--market-open",
        default="auto",
        help="개장 앵커 HH:MM, 또는 'auto'(선물은 시대 규칙, 주식은 설정의 정규장 개장)",
    )
    parser.add_argument(
        "--strategy-yaml",
        type=Path,
        default=DEFAULT_STRATEGY_YAML,
        help="선언 bind 검사가 읽는 전략 YAML (시드 길이·창의 출처)",
    )
    parser.add_argument("--json", dest="as_json", action="store_true")
    parser.add_argument(
        "--runs", action="store_true", help="결정 구간표만 (정답 파일과 같은 모양)"
    )
    parser.add_argument(
        "--write-synthetic-bars",
        action="store_true",
        help=(
            "리플레이하지 않고, 정답 설정의 synthetic 명세로 고정본 CSV.GZ 전부를 "
            "다시 쓴다. 커밋되는 분봉은 이것뿐이다 — 이 저장소는 공개돼 있다"
        ),
    )
    parser.add_argument(
        "--golden",
        choices=("check", "update"),
        default=None,
        help="출하 트리 전부를 고정본으로 돌려 커밋된 정답과 대조(check)하거나 갱신(update)",
    )
    parser.add_argument(
        "--golden-config",
        type=Path,
        default=GOLDEN_CONFIG_PATH,
        help=f"정답 설정 YAML (기본 {_relative(GOLDEN_CONFIG_PATH)})",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="--golden 과 함께: 이 트리만 (반복 가능)",
    )
    return parser


def _frame_for(args: argparse.Namespace, facts: TenantFacts, symbol: str) -> Any:
    """``--data-root`` 또는 ``--bars-csv`` 에서 프레임 하나."""
    if args.bars_csv is not None:
        return load_bars_csv(args.bars_csv, start=args.window_from, end=args.window_to)
    if args.window_from is None or args.window_to is None:
        raise ReplayError("--data-root 는 --from 과 --to 가 함께 필요하다")
    try:
        frame, _loaded = load_bars(
            args.data_root,
            asset_class=facts.asset_class,
            symbol=symbol,
            start=args.window_from,
            end=args.window_to,
            # SAFETY: 밀도 게이트는 리플레이가 한 번만 적용한다 — 두 번 걸면 둘째 호출이
            # 첫째가 이미 버린 날을 다시 세어 「전부 버렸다」로 거부한다
            min_bars_per_day=0,
        )
    except ProduceFieldsError as exc:
        raise ReplayError(str(exc)) from exc
    return frame


def _bars_source_of(args: argparse.Namespace) -> str:
    """이 실행이 읽은 분봉의 출처 — 화면과 정답 머리가 같은 말을 쓰게."""
    if args.bars_csv is not None:
        return f"csv {Path(args.bars_csv).name}"
    # SAFETY: 호스트 경로는 싣지 않는다 — 이 문자열은 `--json` 출력과 정답 머리에 실린다
    return "parquet (host market data)"


def main(argv: Sequence[str] | None = None) -> int:
    """하나의 트리를 돌리거나, 정답 전체를 대조/갱신한다."""
    args = _parser().parse_args(argv)
    try:
        if args.write_synthetic_bars:
            for target, rows in write_synthetic_bars(args.golden_config):
                print(f"wrote {_relative(target)} ({rows} synthetic bars)")
            return 0
        if args.golden is not None:
            text, code = run_golden(
                args.golden, config_path=args.golden_config, only=args.only
            )
            sys.stdout.write(text)
            return code
        if args.tree is None:
            raise ReplayError("--tree 또는 --golden 이 필요하다")
        if (args.data_root is None) == (args.bars_csv is None):
            raise ReplayError("--data-root 와 --bars-csv 중 정확히 하나가 필요하다")
        facts = tenant_facts(args.tree)
        symbol = args.symbol or default_symbol(facts)
        if not symbol:
            raise ReplayError(
                f"{facts.tree_id}: --symbol 이 필요하다 — 이 트리는 종목을 하나로 "
                "못박지 않았다(선물은 월물이 날짜에 따라 다르다)"
            )
        frame = _frame_for(args, facts, symbol)
        result = replay(
            facts.tree_dir,
            symbol=symbol,
            bars=frame,
            min_bars_per_day=args.min_bars_per_day,
            strategy_yaml=args.strategy_yaml,
            market_open=args.market_open,
            seed_sessions=args.seed_sessions,
            bars_source=_bars_source_of(args),
        )
    except ReplayError as exc:
        print(f"replay refused: {exc}", file=sys.stderr)
        return 2
    if args.as_json:
        sys.stdout.write(render_json(result))
    elif args.runs:
        sys.stdout.write(render_runs(result))
    else:
        sys.stdout.write(render_text(result))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
