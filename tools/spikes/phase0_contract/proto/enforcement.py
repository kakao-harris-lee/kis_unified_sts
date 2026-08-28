"""강제 지점 레지스트리 — 설계 §8.3 · U-2b.

`contract_id → 검사 함수` 의 dict 이며 `run_check()` 가 전 키를 순회한다.
**T-39 의 우주가 이 dict 의 키다** — 문서가 선언한 계약 목록이 아니다.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace

from . import floor, gates, register
from .config import cfg_int, cfg_list, cfg_pairs
from .floor import EvidenceRow, fwd_a_0_failures


@dataclass(frozen=True)
class Context:
    """검사 함수 하나가 보는 전부."""

    cfg: Mapping[str, int | str]
    rows: tuple[register.UnchkRow, ...]
    evidence: tuple[EvidenceRow, ...]
    registry: Mapping[str, gates.Gate]
    inputs: Mapping[str, object]
    evaluation: gates.Evaluation
    report: Mapping[str, int]

    def replaced(self, **changes: object) -> Context:
        return replace(self, **changes)


@dataclass(frozen=True)
class Finding:
    contract_id: str
    message: str


def _check_u1a(ctx: Context) -> list[str]:
    return register.check_u1a(ctx.rows, ctx.cfg)


def _check_u4(ctx: Context) -> list[str]:
    return register.check_u4(ctx.rows)


def _check_u8(ctx: Context) -> list[str]:
    return register.check_u8(ctx.rows)


def _check_u8a(ctx: Context) -> list[str]:
    return register.check_u8a(ctx.rows, ctx.registry, ctx.evaluation)


def _check_u8b(ctx: Context) -> list[str]:
    return register.check_u8b(ctx.rows, ctx.registry)


def _check_u9(ctx: Context) -> list[str]:
    return register.check_u9(ctx.rows, register.FIXTURE_CLAUSES)


def _check_u9a(ctx: Context) -> list[str]:
    return register.check_u9a(ctx.rows, ctx.cfg)


def _check_u10(ctx: Context) -> list[str]:
    return register.check_u10(ctx.rows, ctx.evidence, ctx.cfg, ctx.report)


def _check_u11(ctx: Context) -> list[str]:
    """U-11 — contributions 는 11 술어 전역 사상이고 verdict 는 그 논리곱이다."""
    domain = set(gates.predicate_domain(ctx.registry))
    actual = set(ctx.evaluation.contributions)
    problems: list[str] = []
    if actual != domain:
        problems.append(
            f"contributions 정의역 이탈: 누락 {sorted(domain - actual)} "
            f"잉여 {sorted(actual - domain)}"
        )
        return problems
    for pid, (value, basis) in ctx.evaluation.contributions.items():
        if value not in (gates.MET, gates.NOT_MET):
            problems.append(f"{pid}: 기여값 어휘 밖 {value!r}")
        if basis not in gates.BASES:
            problems.append(f"{pid}: basis 어휘 밖 {basis!r}")
    derived = gates.derive_verdict(ctx.registry, ctx.evaluation.contributions)
    if derived != dict(ctx.evaluation.verdict):
        problems.append(
            f"verdict 가 contributions 의 논리곱이 아니다: "
            f"저장 {ctx.evaluation.verdict} 파생 {derived}"
        )
    return problems


def _check_t71(ctx: Context) -> list[str]:
    """T-71 — §4.2.1 분류 분포 앵커."""
    cfg = dict(ctx.cfg)
    expected = {
        gates.CHECKABLE: cfg_int(cfg, "anchor_classification_checkable"),
        gates.PARTIAL: cfg_int(cfg, "anchor_classification_partial"),
        gates.NMC: cfg_int(cfg, "anchor_classification_nmc"),
    }
    actual = gates.classification_distribution(ctx.registry)
    if actual != expected:
        return [f"분류 분포 앵커 이탈: 기대 {expected} 실제 {actual}"]
    return []


def _check_t76(ctx: Context) -> list[str]:
    """T-76 — `floor()` **입력**의 원시값 앵커.

    `floor(e)` 는 두 입력에서 파생된다: 행이 선언한 `minimum_evidence_level`
    원시값과 레벨→kind 매핑.  어느 쪽이 조작돼도 FWD-a-0 판정이 조용히 바뀐다
    (L3 floor 에 PACKAGE 를 얹으면 padded `EV-L3` 가 통과한다).  T-39 의 우주는
    이 레지스트리의 키이므로, 앵커가 여기 없으면 그 조작에는 검출기가 없다.
    """
    cfg = dict(ctx.cfg)
    problems: list[str] = []

    expected_levels = {
        name: int(count)
        for name, count in cfg_pairs(cfg, "anchor_evidence_level_distribution").items()
    }
    actual_levels: dict[str, int] = {}
    for row in ctx.evidence:
        raw = row.minimum_evidence_level
        actual_levels[raw] = actual_levels.get(raw, 0) + 1
    if actual_levels != expected_levels:
        problems.append(
            f"레벨 원시값 분포 앵커 이탈: 기대 {expected_levels} 실제 {actual_levels}"
        )

    expected_kinds = {
        int(level): frozenset(part for part in kinds.split("|") if part)
        for level, kinds in cfg_pairs(cfg, "anchor_level_kinds").items()
    }
    actual_kinds = {
        level: frozenset(kinds) for level, kinds in floor.LEVEL_KINDS.items()
    }
    if actual_kinds != expected_kinds:
        problems.append(
            f"레벨→kind 매핑 앵커 이탈: 기대 "
            f"{ {k: sorted(v) for k, v in expected_kinds.items()} } 실제 "
            f"{ {k: sorted(v) for k, v in actual_kinds.items()} }"
        )
    return problems


def _check_fwd_a_0(ctx: Context) -> list[str]:
    """FWD-a-0 — 검증 가능 쌍이 0 개면 불충족."""
    failures = fwd_a_0_failures(ctx.evidence)
    return [f"{eid}: FWD-a-0 불충족 (검증 가능 쌍 0)" for eid in failures]


def build_registry() -> dict[str, Callable[[Context], list[str]]]:
    """강제 지점 레지스트리.  T-39 는 이 키 집합을 전개한다."""
    return {
        "U-1a": _check_u1a,
        "U-4": _check_u4,
        "U-8": _check_u8,
        "U-8a": _check_u8a,
        "U-8b": _check_u8b,
        "U-9": _check_u9,
        "U-9a": _check_u9a,
        "U-10": _check_u10,
        "U-11": _check_u11,
        "T-71": _check_t71,
        "T-76": _check_t76,
        "FWD-a-0": _check_fwd_a_0,
    }


def run_check(
    ctx: Context,
    *,
    registry: Mapping[str, Callable[[Context], list[str]]] | None = None,
    skip: frozenset[str] = frozenset(),
) -> list[Finding]:
    """전 강제 지점을 순회한다.  `skip` 은 T-39 의 제거 실험용이다."""
    effective = registry if registry is not None else build_registry()
    findings: list[Finding] = []
    for contract_id, check in effective.items():
        if contract_id in skip:
            continue
        for message in check(ctx):
            findings.append(Finding(contract_id, message))
    return findings


def key_count_canary(cfg: Mapping[str, int | str]) -> list[str]:
    """레지스트리 키 수의 count canary (§8.3 — 삭제만 잡고 추가 누락은 못 잡는다)."""
    expected = cfg_int(dict(cfg), "anchor_enforcement_key_count")
    actual = len(build_registry())
    if actual != expected:
        return [f"강제 지점 키 수 앵커 이탈: 기대 {expected} 실제 {actual}"]
    return []


def build_context(
    cfg: Mapping[str, int | str],
    *,
    rows: Sequence[register.UnchkRow] | None = None,
    evidence: Sequence[EvidenceRow] | None = None,
    registry: Mapping[str, gates.Gate] | None = None,
    inputs: Mapping[str, object] | None = None,
    reasons_builder=gates.build_reasons,
    report: Mapping[str, int] | None = None,
) -> Context:
    """기준 컨텍스트를 조립한다.  지표 report 는 파생값에서 만든다."""
    rows_t = tuple(rows if rows is not None else register.fixture_rows())
    evidence_t = tuple(
        evidence if evidence is not None else register.fixture_evidence()
    )
    gate_registry = dict(
        registry if registry is not None else gates.build_gate_registry()
    )
    inputs_d = dict(inputs if inputs is not None else register.fixture_inputs())
    evaluation = gates.evaluate(
        gate_registry, inputs_d, rows_t, reasons_builder=reasons_builder
    )
    report_d = dict(
        report if report is not None else register.metrics(rows_t, evidence_t, cfg)
    )
    return Context(
        cfg=cfg,
        rows=rows_t,
        evidence=evidence_t,
        registry=gate_registry,
        inputs=inputs_d,
        evaluation=evaluation,
        report=report_d,
    )


def violating_contexts(
    cfg: Mapping[str, int | str],
) -> dict[str, Context]:
    """키마다 **그 키만** 위반하는 컨텍스트.  T-39 의 입력물이다."""
    base_rows = register.fixture_rows()
    anchor_no = cfg_list(dict(cfg), "anchor_closable_no_ids")
    cases: dict[str, Context] = {}

    # U-1a — closable=YES 인데 소유 트랙 미배정
    cases["U-1a"] = build_context(
        cfg,
        rows=register.rows_replacing(
            base_rows, "PROTO-UNCHK-001", owner_track="미배정"
        ),
    )
    # U-4 — blocked_by 공란
    cases["U-4"] = build_context(
        cfg, rows=register.rows_replacing(base_rows, "PROTO-UNCHK-001", blocked_by="")
    )
    # U-8 — normative_ref 는 있는데 blocks_gate 공란
    cases["U-8"] = build_context(
        cfg, rows=register.rows_replacing(base_rows, "PROTO-UNCHK-004", blocks_gate="")
    )
    # U-8a — blocks_gate 를 읽지 않는 사유 집합 구현
    cases["U-8a"] = build_context(
        cfg, reasons_builder=gates.build_reasons_ignoring_blocks_gate
    )
    # U-8b — 판정 함수가 없는 target
    cases["U-8b"] = build_context(
        cfg,
        rows=register.rows_replacing(
            base_rows, "PROTO-UNCHK-004", blocks_gate="Phase 4"
        ),
    )
    # U-9 — closable=NO 행의 reason 을 자유 산문으로
    cases["U-9"] = build_context(
        cfg,
        rows=register.rows_replacing(base_rows, anchor_no[0], reason="나중에 봄"),
    )
    # U-9a — closable=NO 집합 변경 (인용은 유효하게 둬 U-9 와 겹치지 않게 한다)
    cases["U-9a"] = build_context(
        cfg,
        rows=register.rows_replacing(
            base_rows,
            "PROTO-UNCHK-003",
            closable="NO",
            reason="§5.2.7",
            owner_track="",
        ),
    )
    # U-10 — 지표 하나를 생성물에서 제거
    stale_report = dict(register.metrics(base_rows, register.fixture_evidence(), cfg))
    stale_report.pop(register.METRIC_BLANK_REF)
    cases["U-10"] = build_context(cfg, report=stale_report)
    # U-11 — contributions 에서 항 하나 제거 (전역성 위반)
    partial_ctx = build_context(cfg)
    broken = dict(partial_ctx.evaluation.contributions)
    broken.pop("G3.3")
    cases["U-11"] = partial_ctx.replaced(
        evaluation=gates.Evaluation(
            partial_ctx.evaluation.verdict, partial_ctx.evaluation.reasons, broken
        )
    )
    # T-71 — 술어 하나의 분류를 바꿔 분포 앵커 이탈
    mutated_registry = gates.build_gate_registry()
    g3 = mutated_registry["G3"]
    promoted = (
        gates.Predicate(
            g3.predicates[0].gate,
            g3.predicates[0].row,
            g3.predicates[0].label,
            gates.CHECKABLE,
            "stand_in_count",
            gates.is_zero,
        ),
        *g3.predicates[1:],
    )
    mutated_registry["G3"] = gates.Gate("G3", gates.COMPLETION, promoted)
    cases["T-71"] = build_context(cfg, registry=mutated_registry)
    # T-76 — 행 하나의 레벨 원시값을 바꿔 floor 입력을 조작한다.
    # (행을 **더하지** 않는다 — 행수가 바뀌면 FWD-a-0 컨텍스트와 서로 오염된다.)
    cases["T-76"] = build_context(
        cfg,
        evidence=tuple(
            (
                EvidenceRow(row.evidence_id, row.status, "EV-L2", row.required_kinds)
                if row.evidence_id == "PROTO-EV-003"
                else row
            )
            for row in register.fixture_evidence()
        ),
    )
    # FWD-a-0 — EV-L3 행을 READY 로 올린다 (검증 가능 쌍 0).
    # 레벨 원시값 분포는 그대로 두어 T-76 앵커를 건드리지 않는다.
    cases["FWD-a-0"] = build_context(
        cfg,
        evidence=tuple(
            (
                EvidenceRow(
                    row.evidence_id,
                    "READY",
                    row.minimum_evidence_level,
                    row.required_kinds,
                )
                if row.evidence_id == "PROTO-EV-003"
                else row
            )
            for row in register.fixture_evidence()
        ),
    )
    return cases
