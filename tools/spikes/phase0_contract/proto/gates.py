"""게이트 평가기 — 설계 §4.2.1 의 11 술어와 §4.2.2 결합 규칙의 픽스처 구현.

핵심 가설은 `basis` 다.  설계 v2.1 은 "정상값이 이미 NOT_MET 인 10 개 술어에서는
fail-closed 와 입력 무시가 구별되지 않는다"고 인정하고 UNCHK-022 로 이연했다.
기여 항을 `(value, basis)` 로 두면 몇 개 술어에서 구별 가능해지는지를
`test_contracts.py` 의 T-2 가 실행으로 판정한다.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import NamedTuple

# --- 분류 (§4.2.1 표의 3 값) ------------------------------------------------
CHECKABLE = "CHECKABLE"
PARTIAL = "PARTIAL"
NMC = "NMC"
CLASSIFICATIONS = (CHECKABLE, PARTIAL, NMC)

# --- 기여값 -----------------------------------------------------------------
MET = "MET"
NOT_MET = "NOT_MET"

# --- basis (이 프로토타입이 추가하는 축) ------------------------------------
EVALUATED = "EVALUATED"
INPUT_MISSING = "INPUT_MISSING"
NOT_MACHINE_CHECKABLE = "NOT_MACHINE_CHECKABLE"
PARTIAL_UNVERIFIABLE = "PARTIAL_UNVERIFIABLE"
BASES = (EVALUATED, INPUT_MISSING, NOT_MACHINE_CHECKABLE, PARTIAL_UNVERIFIABLE)

# --- 게이트 종류 ------------------------------------------------------------
COMPLETION = "COMPLETION"
AUTHORITY = "AUTHORITY"


class EvaluationError(RuntimeError):
    """평가 중단.  판정 실패는 기본값이 아니다."""


@dataclass(frozen=True)
class Predicate:
    """술어 하나.  id 는 `(게이트, 행 순번)` 으로 부여한다 (U-11)."""

    gate: str
    row: int
    label: str
    classification: str
    input_key: str | None = None
    evaluator: Callable[[object], bool] | None = None

    @property
    def pid(self) -> str:
        return f"{self.gate}.{self.row}"


@dataclass(frozen=True)
class Gate:
    """게이트 하나.  AUTHORITY 게이트는 완료 술어를 갖지 않는다 (INV-C1)."""

    gid: str
    kind: str
    predicates: tuple[Predicate, ...] = field(default_factory=tuple)


class Evaluation(NamedTuple):
    """`(verdict, reasons, contributions)` — U-11 이 요구하는 3 항."""

    verdict: dict[str, str]
    reasons: dict[str, frozenset[str]]
    contributions: dict[str, tuple[str, str]]


# --- 술어별 기계 판정 함수 (픽스처 입력에 대한 술어) ------------------------


def _is_zero(value: object) -> bool:
    """계수값이 0 이어야 MET."""
    if not isinstance(value, int):
        raise EvaluationError(f"정수 입력이 아니다: {value!r}")
    return value == 0


def _all_present(value: object) -> bool:
    """존재 열이 전부 PRESENT 여야 MET."""
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise EvaluationError(f"시퀀스 입력이 아니다: {value!r}")
    return all(item == "PRESENT" for item in value)


#: 공개 별칭 — 뮤테이션 하네스가 술어를 재조립할 때 쓴다.
is_zero = _is_zero


def _all_executed(value: object) -> bool:
    """상태가 전부 실행 상태여야 MET."""
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise EvaluationError(f"시퀀스 입력이 아니다: {value!r}")
    return all(item in {"PASS", "READY"} for item in value)


# --- §4.2.1 표 11 행 --------------------------------------------------------
# 분포는 CHECKABLE 2 / PARTIAL 3 / NMC 6 이며 T-71 이 앵커로 고정한다.

_G1_PREDICATES = (
    Predicate("G1", 1, "19-step 에 stand-in 0", CHECKABLE, "stand_in_count", _is_zero),
    Predicate(
        "G1",
        2,
        "권위 actor·durable state owner 가 실제 구현에 결속",
        PARTIAL,
        "package_existence",
        _all_present,
    ),
    Predicate("G1", 3, "synthetic·VirtualBroker·transport 동일 검증 경계", NMC),
    Predicate("G1", 4, "정상·거부·UNKNOWN·crash 경로가 evidence 를 남김", NMC),
    Predicate(
        "G1",
        5,
        "root 없이 독립 패키지/프로세스로 실행 가능",
        PARTIAL,
        "reverse_import_count",
        _is_zero,
    ),
)

_G2_PREDICATES = (
    Predicate(
        "G2",
        1,
        "필수 Evidence row 가 EV-L1~L4 에서 실행·독립 리뷰",
        PARTIAL,
        "evidence_statuses",
        _all_executed,
    ),
    Predicate(
        "G2",
        2,
        "미실행 항목을 임의 PASS 로 바꾸지 않음",
        CHECKABLE,
        "vocabulary_violations",
        _is_zero,
    ),
    Predicate("G2", 3, "synthetic/VirtualBroker E2E·restart·partition 등 통과", NMC),
)

_G3_PREDICATES = (
    Predicate("G3", 1, "versioned contract·migration·rollback 동결", NMC),
    Predicate("G3", 2, "generation·credential·queue·network-route fencing", NMC),
    Predicate("G3", 3, "root 리팩터링의 유일한 시작 조건", NMC),
)


def build_gate_registry() -> dict[str, Gate]:
    """게이트 판정 레지스트리.  U-8b 의 허용 집합이 이 키에서 파생된다."""
    return {
        "G1": Gate("G1", COMPLETION, _G1_PREDICATES),
        "G2": Gate("G2", COMPLETION, _G2_PREDICATES),
        "G3": Gate("G3", COMPLETION, _G3_PREDICATES),
        # G4 는 권한 게이트다.  완료 술어를 갖지 않으며 G1~G3 는 이 값을 읽지
        # 않는다 (INV-C1).  U-8b 의 허용 집합은 이 `kind` 값으로 제외한다 —
        # id 리터럴이 아니므로 권한 게이트를 더 넣어도 새어나가지 않는다.
        "G4": Gate("G4", AUTHORITY, ()),
    }


def completion_gates(registry: Mapping[str, Gate]) -> tuple[str, ...]:
    """완료 게이트 id 를 순서대로."""
    return tuple(gid for gid, gate in registry.items() if gate.kind == COMPLETION)


def predicate_domain(registry: Mapping[str, Gate]) -> tuple[str, ...]:
    """술어 id 우주.  §4.2.1 표의 행이 유일 소스다 (U-11)."""
    return tuple(
        predicate.pid
        for gid in completion_gates(registry)
        for predicate in registry[gid].predicates
    )


def allowed_blocks_gate(registry: Mapping[str, Gate]) -> frozenset[str]:
    """U-8b — 제외 기준은 id 가 아니라 **종류(kind)** 다 (설계 v2.2).

    `allowed = { g ∈ gate_registry | kind(g) == COMPLETION }`.

    v2.1 의 `keys() − {G4}` 는 리터럴 목록을 리터럴 **단일 제외**로 바꾼 것이라
    두 번째 권한 게이트가 생기면 허용 집합에 자동 포함됐다.  종류로 올리면
    권한 게이트가 몇 개든 구조적으로 배제된다 (INV-C1).
    """
    return frozenset(gid for gid, gate in registry.items() if gate.kind == COMPLETION)


def classification_distribution(registry: Mapping[str, Gate]) -> dict[str, int]:
    """T-71 앵커용 분포."""
    counts = dict.fromkeys(CLASSIFICATIONS, 0)
    for gid in completion_gates(registry):
        for predicate in registry[gid].predicates:
            counts[predicate.classification] += 1
    return counts


def build_reasons(
    registry: Mapping[str, Gate], rows: Sequence[object]
) -> dict[str, frozenset[str]]:
    """U-8a — `blocks_gate=X` 인 항목의 id 가 게이트 X 의 사유 집합에 들어간다."""
    reasons: dict[str, frozenset[str]] = {}
    for gid in completion_gates(registry):
        reasons[gid] = frozenset(
            str(row.id) for row in rows if str(getattr(row, "blocks_gate", "")) == gid
        )
    return reasons


def build_reasons_ignoring_blocks_gate(
    registry: Mapping[str, Gate], rows: Sequence[object]
) -> dict[str, frozenset[str]]:
    """`blocks_gate` 를 읽지 않는 구현 — T-61·T-70 이 red 로 만들어야 하는 뮤턴트."""
    everyone = frozenset(
        str(row.id) for row in rows if str(getattr(row, "normative_ref", ""))
    )
    return dict.fromkeys(completion_gates(registry), everyone)


def _contribute(
    predicate: Predicate,
    inputs: Mapping[str, object],
    fold: Mapping[str, str | None],
    ignore_inputs: bool,
) -> tuple[str, str]:
    """술어 하나의 `(value, basis)` 를 판정한다 (§4.2.2 결합 규칙)."""
    if predicate.classification == NMC:
        # NMC 는 기계 판정 입력이 정의상 존재하지 않는다.  INV-C4.
        return fold.get(NMC) or NOT_MET, NOT_MACHINE_CHECKABLE

    if predicate.input_key is None or predicate.evaluator is None:
        raise EvaluationError(f"{predicate.pid}: 검사 가능 술어에 입력 결속이 없다")

    if ignore_inputs and predicate.classification == PARTIAL:
        # 뮤턴트 구현 — `부분` 은 어차피 NOT_MET 이므로 입력을 읽지 않는다.
        # §4.2.2 결합 규칙만 보면 이 구현도 규칙을 준수한다.
        return fold.get(PARTIAL) or NOT_MET, PARTIAL_UNVERIFIABLE

    if predicate.input_key not in inputs:
        # INV-C3 — 입력 부재는 UNKNOWN 이 아니라 NOT_MET.  basis 가 그 사실을 운반한다.
        return NOT_MET, INPUT_MISSING

    machine_met = predicate.evaluator(inputs[predicate.input_key])

    if predicate.classification == CHECKABLE:
        forced = fold.get(CHECKABLE)
        value = forced if forced is not None else (MET if machine_met else NOT_MET)
        return value, EVALUATED

    # PARTIAL — 검사 가능 부분을 실제로 읽은 뒤 검증 불가 부분 때문에 접는다.
    return fold.get(PARTIAL) or NOT_MET, PARTIAL_UNVERIFIABLE


def evaluate(
    registry: Mapping[str, Gate],
    inputs: Mapping[str, object],
    rows: Sequence[object],
    *,
    fold: Mapping[str, str | None] | None = None,
    ignore_inputs: bool = False,
    reasons_builder: Callable[..., dict[str, frozenset[str]]] = build_reasons,
) -> Evaluation:
    """`(verdict, reasons, contributions)` 를 돌려준다.

    `contributions` 는 술어 id → `(value, basis)` 의 **전역 사상**이며 정의역은
    §4.2.1 표 11 행 전부다.  공역 제약은 없다 — 11 항 전부 MET 인 벡터도 유효하다.
    `verdict` 는 contributions 의 논리곱으로 **파생**되며 독립 저장되지 않는다.
    """
    effective_fold: Mapping[str, str | None] = fold or {}
    contributions: dict[str, tuple[str, str]] = {}
    for gid in completion_gates(registry):
        for predicate in registry[gid].predicates:
            contributions[predicate.pid] = _contribute(
                predicate, inputs, effective_fold, ignore_inputs
            )

    verdict: dict[str, str] = {}
    for gid in completion_gates(registry):
        values = [contributions[p.pid][0] for p in registry[gid].predicates]
        verdict[gid] = MET if values and all(v == MET for v in values) else NOT_MET

    return Evaluation(verdict, reasons_builder(registry, rows), contributions)


def derive_verdict(
    registry: Mapping[str, Gate], contributions: Mapping[str, tuple[str, str]]
) -> dict[str, str]:
    """contributions 에서 verdict 를 다시 파생한다 — U-11 의 독립 저장 금지 검사용."""
    derived: dict[str, str] = {}
    for gid in completion_gates(registry):
        values = []
        for predicate in registry[gid].predicates:
            entry = contributions.get(predicate.pid)
            if entry is None:
                return {}
            values.append(entry[0])
        derived[gid] = MET if values and all(v == MET for v in values) else NOT_MET
    return derived
