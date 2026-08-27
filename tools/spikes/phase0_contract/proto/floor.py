"""floor 도출 + FWD-a-0 — 설계 §5.2.8 · §5.2.4.

레벨 문법 `EV-L{집합}[+Broker][+Security]` 를 파싱해 레벨별 kind 매핑의
**합집합**을 floor 로 삼는다.  FWD-a-0 의 계수 대상은
`required_kinds(e) ∩ floor(e) ∩ {PACKAGE, TEST, REVIEWER}` 다 (v2.0).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

PACKAGE = "PACKAGE"
TEST = "TEST"
REVIEWER = "REVIEWER"
FAULT = "FAULT"
RUNTIME = "RUNTIME"

SURFACE_KINDS = frozenset({PACKAGE, TEST, REVIEWER, FAULT, RUNTIME})

#: 충족 판정 대상 kind (§5.2.4).  RUNTIME·FAULT 는 존재만 필수다.
VERIFIABLE_KINDS = frozenset({PACKAGE, TEST, REVIEWER})

#: 레벨 → kind 매핑.  §5.2.8 이 규범 텍스트에서 도출했으나 명시 조항은 없다
#: (OQ-11 미판정).  L3 이상은 전부 RUNTIME.
LEVEL_KINDS: Mapping[int, frozenset[str]] = {
    0: frozenset({REVIEWER}),
    1: frozenset({PACKAGE, TEST}),
    2: frozenset({FAULT}),
    3: frozenset({RUNTIME}),
    4: frozenset({RUNTIME}),
    5: frozenset({RUNTIME}),
}

_LEVEL_RE = re.compile(
    r"^EV-L(?P<levels>\d(?:/L?\d)*)(?P<suffixes>(?:\+(?:Broker|Security))*)$"
)

PROFILE_DEPENDENT = "Profile-dependent"


class LevelSyntaxError(ValueError):
    """`minimum_evidence_level` 파싱 실패.  조용히 비우지 않고 중단한다 (T-48)."""


class ProfileDependentError(ValueError):
    """`Profile-dependent` 는 규범상 blocker 다 (K-13, §5.2.10)."""


@dataclass(frozen=True)
class EvidenceRow:
    """합성 evidence 픽스처 행."""

    evidence_id: str
    status: str
    minimum_evidence_level: str
    required_kinds: frozenset[str]


def parse_levels(raw: str) -> frozenset[int]:
    """레벨 집합을 파싱한다.  `EV-L0/1` 과 `EV-L0/L1` 은 같은 값이다 (T-47)."""
    text = (raw or "").strip()
    if not text:
        raise LevelSyntaxError("빈 minimum_evidence_level")
    if text == PROFILE_DEPENDENT:
        raise ProfileDependentError(f"{text} 는 차단 대상이지 기본값 대상이 아니다")
    match = _LEVEL_RE.match(text)
    if match is None:
        raise LevelSyntaxError(f"문법 밖 레벨 표기: {text!r}")
    levels = set()
    for token in match.group("levels").split("/"):
        levels.add(int(token.lstrip("L")))
    unknown = levels - set(LEVEL_KINDS)
    if unknown:
        raise LevelSyntaxError(f"매핑이 없는 레벨: {sorted(unknown)}")
    return frozenset(levels)


def floor(raw: str) -> frozenset[str]:
    """`floor(e)` — 레벨별 매핑의 합집합."""
    result: set[str] = set()
    for level in parse_levels(raw):
        result |= LEVEL_KINDS[level]
    return frozenset(result)


def countable_kinds(row: EvidenceRow, *, use_floor: bool = True) -> frozenset[str]:
    """FWD-a-0 의 계수 대상.

    `use_floor=False` 는 v1.9 규칙(floor 한정 없음)이며, superset 우회가
    실제로 성립했음을 보이는 **음성 대조군**으로만 쓴다.
    """
    base = frozenset(row.required_kinds) & VERIFIABLE_KINDS
    if not use_floor:
        return base
    return base & floor(row.minimum_evidence_level)


def fwd_a_0_satisfied(row: EvidenceRow, *, use_floor: bool = True) -> bool:
    """검증 가능 쌍이 0 개면 불충족 — "판정할 것이 없으니 통과"를 금지한다."""
    return bool(countable_kinds(row, use_floor=use_floor))


def fwd_a_0_failures(
    rows: Iterable[EvidenceRow], *, use_floor: bool = True
) -> tuple[str, ...]:
    """`status ∈ {PASS, READY}` 행 중 FWD-a-0 불충족 행의 id."""
    return tuple(
        row.evidence_id
        for row in rows
        if row.status in {"PASS", "READY"}
        and not fwd_a_0_satisfied(row, use_floor=use_floor)
    )


def superset_declared_pairs(rows: Iterable[EvidenceRow]) -> int:
    """`Σ_e |required_kinds(e) \\ floor(e)|` — U-10 지표."""
    total = 0
    for row in rows:
        total += len(frozenset(row.required_kinds) - floor(row.minimum_evidence_level))
    return total
