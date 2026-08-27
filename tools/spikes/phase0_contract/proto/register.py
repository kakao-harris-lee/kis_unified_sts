"""UNCHK 레지스터 모델과 그 계약 — 설계 §13.

계약: U-1a(소유 트랙) · U-4(blocked_by) · U-8(blocks_gate 필수) ·
U-8a(사유 집합 기여) · U-8b(허용 집합 파생) · U-9(closable=NO 인용) ·
U-9a(앵커) · U-10(4 지표).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

from . import gates
from .config import cfg_int, cfg_list
from .floor import EvidenceRow, superset_declared_pairs

UNASSIGNED = "미배정"

#: owner_track 문법 토큰
_PHASE_SINGLE = re.compile(r"^Phase (\d+)$")
_PHASE_RANGE = re.compile(r"^Phase (\d+)-(\d+)$")
_GOV_TRACK = "GOV-001"

#: U-9 가 요구하는 "이 문서에서 원리적 한계를 확립한 절" 의 인용 문법
_CLAUSE_RE = re.compile(r"^§\d+(?:\.\d+)*$")

#: 픽스처 세계의 실재 절 목록.  실제 D0 구현에서는 문서 파싱으로 대체된다.
FIXTURE_CLAUSES = frozenset({"§13.5.2", "§5.2.7", "§4.2.2", "§8.3"})

# 지표 이름 — U-10 이 요구하는 4 개.
METRIC_SUPERSET = "superset_declared_pairs"
METRIC_IMPRECISE = "imprecise_owner_track"
METRIC_BLANK_REF = "blank_normative_ref_rows"
METRIC_CLOSABLE_NO = "closable_no_rows"
REQUIRED_METRICS = (
    METRIC_SUPERSET,
    METRIC_IMPRECISE,
    METRIC_BLANK_REF,
    METRIC_CLOSABLE_NO,
)


class OwnerTrackSyntaxError(ValueError):
    """owner_track 문법 위반.  조용히 통과시키지 않는다 (T-62)."""


@dataclass(frozen=True)
class UnchkRow:
    """UNCHK 레지스터 한 행 (합성 픽스처)."""

    id: str
    axis: str
    reason: str
    blocked_by: str
    owner_track: str
    normative_ref: str
    closable: str
    blocks_gate: str

    def with_(self, **changes: str) -> UnchkRow:
        """뮤테이션용 사본."""
        return replace(self, **changes)


# --- owner_track 문법 (임계값은 전부 설정에서) -------------------------------

EXACT = "EXACT"
RANGE = "RANGE"
NONE = "UNASSIGNED"


def classify_owner_track(value: str, cfg: Mapping[str, int | str]) -> str:
    """owner_track 을 `UNASSIGNED` / `EXACT` / `RANGE` 로 분류한다.

    문법 밖 값은 `OwnerTrackSyntaxError` 로 **거부**한다 — 기본값 없음.
    """
    phase_min = cfg_int(dict(cfg), "phase_min")
    phase_max = cfg_int(dict(cfg), "phase_max")
    max_width = cfg_int(dict(cfg), "owner_track_range_max_width")

    text = (value or "").strip()
    if text == "" or text == UNASSIGNED:
        return NONE

    has_range = False
    for token in text.split("+"):
        if token == _GOV_TRACK:
            continue
        single = _PHASE_SINGLE.match(token)
        if single is not None:
            phase = int(single.group(1))
            if not phase_min <= phase <= phase_max:
                raise OwnerTrackSyntaxError(f"phase 범위 밖: {token!r}")
            continue
        ranged = _PHASE_RANGE.match(token)
        if ranged is not None:
            low, high = int(ranged.group(1)), int(ranged.group(2))
            if not phase_min <= low < high <= phase_max:
                raise OwnerTrackSyntaxError(f"범위 경계 위반: {token!r}")
            if high - low > max_width:
                raise OwnerTrackSyntaxError(
                    f"범위 폭 {high - low} > 상한 {max_width}: {token!r}"
                )
            has_range = True
            continue
        raise OwnerTrackSyntaxError(f"문법 밖 owner_track 토큰: {token!r}")

    return RANGE if has_range else EXACT


# --- 계약 검사 --------------------------------------------------------------


def check_u1a(rows: Sequence[UnchkRow], cfg: Mapping[str, int | str]) -> list[str]:
    """U-1a — `closable=YES` 인데 소유 트랙이 없으면 차단."""
    problems: list[str] = []
    for row in rows:
        try:
            kind = classify_owner_track(row.owner_track, cfg)
        except OwnerTrackSyntaxError as exc:
            problems.append(f"{row.id}: {exc}")
            continue
        if row.closable == "YES" and kind == NONE:
            problems.append(f"{row.id}: closable=YES 인데 owner_track 미배정")
    return problems


def check_u4(rows: Sequence[UnchkRow]) -> list[str]:
    """U-4 — `blocked_by` 가 빈 행은 허용하지 않는다."""
    return [f"{row.id}: blocked_by 공란" for row in rows if not row.blocked_by.strip()]


def check_u8(rows: Sequence[UnchkRow]) -> list[str]:
    """U-8 — `normative_ref` 가 비어 있지 않으면 `blocks_gate` 필수."""
    return [
        f"{row.id}: normative_ref 가 있는데 blocks_gate 공란"
        for row in rows
        if row.normative_ref.strip() and not row.blocks_gate.strip()
    ]


def check_u8b(
    rows: Sequence[UnchkRow], registry: Mapping[str, gates.Gate]
) -> list[str]:
    """U-8b — 허용 집합은 게이트 레지스트리에서 파생된다 (리터럴 목록 금지)."""
    allowed = gates.allowed_blocks_gate(registry)
    return [
        f"{row.id}: blocks_gate={row.blocks_gate!r} 는 허용 집합 {sorted(allowed)} 밖"
        for row in rows
        if row.blocks_gate.strip() and row.blocks_gate not in allowed
    ]


def check_u8a(
    rows: Sequence[UnchkRow],
    registry: Mapping[str, gates.Gate],
    evaluation: gates.Evaluation,
) -> list[str]:
    """U-8a — `blocks_gate=X` 인 항목의 id 가 게이트 X 의 사유 집합에 있어야 한다.

    허용 집합 밖의 target 은 U-8b 소관이므로 여기서 재차 세지 않는다
    (두 계약이 겹치면 T-39 의 키 격리가 성립하지 않는다).
    """
    allowed = gates.allowed_blocks_gate(registry)
    problems: list[str] = []
    for row in rows:
        target = row.blocks_gate.strip()
        if not target or target not in allowed:
            continue
        if row.id not in evaluation.reasons.get(target, frozenset()):
            problems.append(f"{row.id}: {target} 사유 집합에 기여하지 않는다")

    # T-70 — 서로 다른 게이트의 (비어 있지 않은) 사유 집합이 동일하면 분리 실패.
    seen: dict[frozenset[str], str] = {}
    for gid, reason_set in evaluation.reasons.items():
        if not reason_set:
            continue
        if reason_set in seen:
            problems.append(f"{seen[reason_set]}·{gid} 사유 집합이 동일하다")
        else:
            seen[reason_set] = gid
    return problems


def check_u9(rows: Sequence[UnchkRow], clauses: frozenset[str]) -> list[str]:
    """U-9 — `closable=NO` 면 `reason` 이 해석 가능한 절 인용이어야 한다."""
    problems: list[str] = []
    for row in rows:
        if row.closable != "NO":
            continue
        text = row.reason.strip()
        if not _CLAUSE_RE.match(text):
            problems.append(f"{row.id}: reason 이 절 인용 문법이 아니다: {text!r}")
        elif text not in clauses:
            problems.append(f"{row.id}: reason 인용이 해석되지 않는다: {text!r}")
    return problems


def check_u9a(rows: Sequence[UnchkRow], cfg: Mapping[str, int | str]) -> list[str]:
    """U-9a — `closable=NO` 집합을 커밋된 앵커로 고정한다."""
    anchor = frozenset(cfg_list(dict(cfg), "anchor_closable_no_ids"))
    actual = frozenset(row.id for row in rows if row.closable == "NO")
    if actual != anchor:
        return [
            f"closable=NO 집합 앵커 이탈: 기대 {sorted(anchor)} 실제 {sorted(actual)}"
        ]
    return []


# --- U-10 지표 --------------------------------------------------------------


def metrics(
    rows: Sequence[UnchkRow],
    evidence: Sequence[EvidenceRow],
    cfg: Mapping[str, int | str],
) -> dict[str, int]:
    """U-10 의 4 지표를 **파생**한다."""
    imprecise = 0
    for row in rows:
        try:
            if classify_owner_track(row.owner_track, cfg) == RANGE:
                imprecise += 1
        except OwnerTrackSyntaxError:
            # 문법 밖 값은 U-1a 가 차단한다.  지표에서는 세지 않는다.
            continue
    return {
        METRIC_SUPERSET: superset_declared_pairs(evidence),
        METRIC_IMPRECISE: imprecise,
        METRIC_BLANK_REF: sum(1 for row in rows if not row.normative_ref.strip()),
        METRIC_CLOSABLE_NO: sum(1 for row in rows if row.closable == "NO"),
    }


def check_u10(
    rows: Sequence[UnchkRow],
    evidence: Sequence[EvidenceRow],
    cfg: Mapping[str, int | str],
    report: Mapping[str, int],
) -> list[str]:
    """U-10 — 4 지표가 생성물에 전문 노출되고 값이 파생값과 일치해야 한다."""
    derived = metrics(rows, evidence, cfg)
    problems: list[str] = []
    for name in REQUIRED_METRICS:
        if name not in report:
            problems.append(f"지표 미노출: {name}")
        elif report[name] != derived[name]:
            problems.append(
                f"지표 stale: {name} 노출 {report[name]} != 파생 {derived[name]}"
            )
    return problems


# --- 합성 픽스처 ------------------------------------------------------------


def fixture_rows() -> tuple[UnchkRow, ...]:
    """전 계약을 통과하는 기준 픽스처.  **합성이며 실제 레지스터가 아니다.**"""
    return (
        UnchkRow(
            id="PROTO-UNCHK-001",
            axis="프로파일 approved 술어",
            reason="승인 마커가 주석이라 로더에서 소실",
            blocked_by="마커를 값으로 승격",
            owner_track="GOV-001+Phase 1",
            normative_ref="",
            closable="YES",
            blocks_gate="",
        ),
        UnchkRow(
            id="PROTO-UNCHK-002",
            axis="RUNTIME/FAULT 표면 존재 검증",
            reason="정규 레지스터 부재",
            blocked_by="레지스터 신설",
            owner_track="Phase 2-5",
            normative_ref="",
            closable="YES",
            blocks_gate="",
        ),
        UnchkRow(
            id="PROTO-UNCHK-003",
            axis="독립 프로세스 실행",
            reason="firewall 은 역방향 import 부재만 증명",
            blocked_by="독립 실행 하네스",
            owner_track="Phase 3",
            normative_ref="",
            closable="YES",
            blocks_gate="",
        ),
        UnchkRow(
            id="PROTO-UNCHK-004",
            axis="+Security 의무의 검사·운반",
            reason="접미를 해석하는 검사가 없다",
            blocked_by="접미 의무 검사 계약 신설",
            owner_track="Phase 6",
            normative_ref="VER-PROTO §5 (:168)",
            closable="YES",
            blocks_gate="G2",
        ),
        UnchkRow(
            id="PROTO-UNCHK-005",
            axis="+Broker 의무의 검사·운반",
            reason="Broker 프로파일 결속 부재",
            blocked_by="Broker Capability Profile 결속",
            owner_track="Phase 4",
            normative_ref="VER-PROTO §5 (:168)",
            closable="YES",
            blocks_gate="G2",
        ),
        UnchkRow(
            id="PROTO-UNCHK-006",
            axis="권위 actor 결속의 RUNTIME 부분",
            reason="정규 서비스 목록 부재",
            blocked_by="서비스 레지스터 신설",
            owner_track="Phase 2",
            normative_ref="VER-PROTO §5 (:142)",
            closable="YES",
            blocks_gate="G1",
        ),
        UnchkRow(
            id="PROTO-UNCHK-007",
            axis="문서가 선언하지 않은 축",
            reason="§13.5.2",
            blocked_by="외부 기준 목록 도입 여부",
            owner_track="",
            normative_ref="",
            closable="NO",
            blocks_gate="",
        ),
        UnchkRow(
            id="PROTO-UNCHK-008",
            axis="G3 소비처 정의",
            reason="소비처의 범위·식별 규칙 부재",
            blocked_by="소비처 정의",
            owner_track="Phase 7",
            normative_ref="VER-PROTO §7 (:30)",
            closable="YES",
            blocks_gate="G3",
        ),
    )


def fixture_evidence() -> tuple[EvidenceRow, ...]:
    """FWD-a-0 기준 픽스처.  전 행이 FWD-a-0 를 충족한다."""
    return (
        EvidenceRow(
            evidence_id="PROTO-EV-001",
            status="READY",
            minimum_evidence_level="EV-L1",
            # floor = {PACKAGE, TEST}.  FAULT 는 floor 밖 초과 선언 1 쌍.
            required_kinds=frozenset({"PACKAGE", "TEST", "FAULT"}),
        ),
        EvidenceRow(
            evidence_id="PROTO-EV-002",
            status="PASS",
            minimum_evidence_level="EV-L0/1",
            required_kinds=frozenset({"REVIEWER", "PACKAGE", "TEST"}),
        ),
        EvidenceRow(
            evidence_id="PROTO-EV-003",
            status="NOT_IMPLEMENTED",
            minimum_evidence_level="EV-L3",
            required_kinds=frozenset({"RUNTIME"}),
        ),
    )


def fixture_inputs() -> dict[str, object]:
    """게이트 술어의 기계 판정 입력 (현재 상태 픽스처)."""
    return {
        "stand_in_count": 4,
        "package_existence": ["PRESENT", "PRESENT"],
        "reverse_import_count": 0,
        "evidence_statuses": ["READY", "PASS", "NOT_IMPLEMENTED"],
        "vocabulary_violations": 0,
    }


def all_met_inputs() -> dict[str, object]:
    """전 술어가 참이 되는 입력 (T-75 도달성 실험용)."""
    return {
        "stand_in_count": 0,
        "package_existence": ["PRESENT", "PRESENT"],
        "reverse_import_count": 0,
        "evidence_statuses": ["READY", "PASS"],
        "vocabulary_violations": 0,
    }


def all_checkable_registry() -> dict[str, gates.Gate]:
    """11 술어 전부를 CHECKABLE 로 분류한 **가정 미래** 레지스트리.

    §4.2.2 결합 규칙에서 PARTIAL·NMC 는 무조건 NOT_MET 이므로, all-MET 는
    분류가 전부 CHECKABLE 일 때만 도달 가능하다.  T-75 는 그 사실 자체를
    관측한다.
    """
    registry = gates.build_gate_registry()
    promoted: dict[str, gates.Gate] = {}
    counter = 0
    for gid, gate in registry.items():
        if gate.kind != gates.COMPLETION:
            promoted[gid] = gate
            continue
        new_predicates = []
        for predicate in gate.predicates:
            if predicate.classification == gates.CHECKABLE:
                new_predicates.append(predicate)
                continue
            counter += 1
            key = predicate.input_key or f"promoted_input_{counter}"
            new_predicates.append(
                gates.Predicate(
                    predicate.gate,
                    predicate.row,
                    predicate.label,
                    gates.CHECKABLE,
                    key,
                    predicate.evaluator or _always_true,
                )
            )
        promoted[gid] = gates.Gate(gid, gate.kind, tuple(new_predicates))
    return promoted


def _always_true(value: object) -> bool:
    """승격된 술어의 픽스처 판정 함수."""
    return bool(value)


def all_checkable_inputs(registry: Mapping[str, gates.Gate]) -> dict[str, object]:
    """`all_checkable_registry` 의 전 술어를 MET 으로 만드는 입력."""
    inputs = all_met_inputs()
    for gid in gates.completion_gates(registry):
        for predicate in registry[gid].predicates:
            if predicate.input_key and predicate.input_key not in inputs:
                inputs[predicate.input_key] = True
    return inputs


def rows_replacing(
    rows: Iterable[UnchkRow], row_id: str, **changes: str
) -> tuple[UnchkRow, ...]:
    """행 하나만 바꾼 사본 — 뮤테이션 헬퍼."""
    return tuple(row.with_(**changes) if row.id == row_id else row for row in rows)
