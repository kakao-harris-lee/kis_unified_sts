#!/usr/bin/env python3
"""tos Phase-0 완료 계약 — D0-A 검사기, 증분 C1 (데이터-플레인 계약).

정본: ``docs/plans/2026-08-12-tos-phase0-completion-contract-design.md``
(blob 결속 — 이 파일은 절대 편집하지 않는다.  모호한 지점은
``python tools/tos_contract_index.py --locate <id>`` 로 절만 확인한다).

이 검사기는 증분 C1 이 강제하는 다음 등록 id만 다룬다::

    K-1 · K-2 · K-3 · K-4 · K-5/FWD-METRICS · K-6 · K-9 · K-11 · K-12 · K-13
    · K-14 · U-14

``DEFERRED_CONTRACTS`` 에 등재된 계약(U-12 · U-13 · U-15 · U-16 · U-17 ·
U-1a · T-71 축)은 C2 이후 소관이며, 이 파일에는 강제 지점이 없다
(UNCHK-019 축 — 정직 노출).

rc 의미론 (핀 — 이 문서가 정본):
    * 계약 위반(``Finding``) >= 1  ->  exit 1
    * 위반 0                       ->  exit 0
    완료 관측(§11 소관: FWD-a·planned_unassigned_pairs 등)은 rc 에 결합하지
    않는다 — "완료 관측 (§11 소관 · rc 비결합)" 섹션에 인쇄만 한다.  근거:
    §12.2 "신규 검사는 처음부터 green 인 상태로 도입" + "Phase 0 의 종료
    조건은 FWD-a 에만 걸린다"(§5.2.4) — 완료 미도달은 repo 결함이 아니다.
    U-12/U-15/U-16 상태 기계의 rc 결합(T-78/T-81/T-82)은 C2 소관이다.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path, PurePosixPath

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

CONFIG_REL = Path("config/tos_completion.yaml")
PART1_REL = Path(
    "tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv"
)
DEV_REL = Path("tos-spec/src/part-3-development/verification/EVIDENCE-REGISTER-DEV.csv")
REQUIRED_KINDS_REL = Path("tos-spec/src/verification/EVIDENCE-REQUIRED-KINDS.csv")
SURFACE_MAP_REL = Path("tos-spec/src/verification/EVIDENCE-SURFACE-MAP.csv")
UNCHECKABLE_REL = Path("tos-spec/src/verification/PHASE0-UNCHECKABLE-REGISTER.csv")
OQ11_REL = Path("tos-spec/src/part-1-foundation/decisions/OQ-11-DISPOSITION.md")
TOS_SPEC_SRC_REL = Path("tos-spec/src")

KIND_VOCAB = frozenset({"PACKAGE", "RUNTIME", "TEST", "FAULT", "REVIEWER"})
MARKER = "PLANNED_UNASSIGNED"

REGISTER_FIELDS = (
    "evidence_id",
    "domain",
    "title",
    "primary_adr",
    "criticality",
    "minimum_evidence_level",
    "status",
    "implementation_owner",
    "evidence_owner",
    "independent_reviewer",
    "verification_profile_version",
    "broker_capability_profile_version",
    "latest_run_id",
    "latest_result_date",
    "evidence_location",
    "notes",
)
REQUIRED_KINDS_FIELDS = ("evidence_id", "required_kinds", "basis")
SURFACE_MAP_FIELDS = (
    "evidence_id",
    "surface_kind",
    "surface_ref",
    "existence",
    "binding_basis",
)
UNCHECKABLE_FIELDS = (
    "id",
    "axis",
    "reason",
    "blocked_by",
    "owner_track",
    "exposed_in",
    "normative_ref",
    "closable",
    "blocks_gate",
)

# C2 이후 소관 — 이 파일에는 강제 지점이 없다 (UNCHK-019 축 · 정직 노출).
DEFERRED_CONTRACTS: tuple[str, ...] = (
    "U-12",
    "U-13",
    "U-15",
    "U-16",
    "U-17",
    "U-1a",
    "T-71",
)

_VERIFIABLE_LEVEL_KINDS = frozenset({"PACKAGE", "TEST", "REVIEWER"})
_OWNER_TRACK_RANGE_RE = re.compile(r"Phase \d+-\d+")


@dataclass(frozen=True)
class Finding:
    """계약 위반 한 건."""

    check_id: str
    message: str

    def __str__(self) -> str:  # noqa: D105
        return f"[{self.check_id}] {self.message}"


@dataclass
class CheckContext:
    """모든 강제 검사가 공유하는, 미리 로드된 코퍼스."""

    repo_root: Path
    config: dict[str, object] | None
    register_by_id: dict[str, dict[str, str]] | None
    register_rows: list[dict[str, str]]
    required_kinds_rows: list[dict[str, str]] | None
    required_kinds_by_id: dict[str, frozenset[str]] | None
    surface_map_rows: list[dict[str, str]] | None
    uncheckable_rows: list[dict[str, str]] | None
    level_kind_map: dict[int, frozenset[str]] | None
    preload_findings: dict[str, list[Finding]]
    observations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# floor 파생 (공용 함수 — §5.2.10)
# ---------------------------------------------------------------------------

_LEVEL_PREFIX = "EV-L"


def parse_level(value: str) -> set[int] | None:
    """§5.2.10 파싱 규율에 따라 ``minimum_evidence_level`` 원시값을 분해한다.

    Returns:
        ``None`` — 'Profile-dependent' (K-13 이 소비하는 표지).
        ``set[int]`` — 파싱된 레벨 집합.

    Raises:
        ValueError: 문법 밖 값 (T-48 축).  호출자는 건너뛰지 말고 위반으로
            취급해야 한다 — 하한이 조용히 비어서는 안 된다.
    """
    if value == "Profile-dependent":
        return None
    stripped = value.replace("+Broker", "").replace("+Security", "")
    if not stripped.startswith(_LEVEL_PREFIX):
        raise ValueError(f"'EV-L' 접두 없음: {value!r}")
    body = stripped[len(_LEVEL_PREFIX) :]
    if not body:
        raise ValueError(f"레벨 본문 없음: {value!r}")
    levels: set[int] = set()
    for chunk in body.split("/"):
        piece = chunk[1:] if chunk.startswith("L") else chunk
        if not piece.isdigit():
            raise ValueError(f"레벨 조각 파싱 실패: {value!r} (조각 {chunk!r})")
        levels.add(int(piece))
    if not levels:
        raise ValueError(f"레벨 집합이 공집합: {value!r}")
    return levels


def derive_floor(
    levels: Iterable[int], level_kind_map: dict[int, frozenset[str]]
) -> set[str]:
    """floor(levels) = ⋃ level_kind_map[l] — 합집합·비누적."""
    result: set[str] = set()
    for level in levels:
        result |= set(level_kind_map.get(level, frozenset()))
    return result


# ---------------------------------------------------------------------------
# 로더
# ---------------------------------------------------------------------------


def _load_yaml_config(path: Path) -> tuple[dict[str, object] | None, list[Finding]]:
    if not path.exists():
        return None, [Finding("U-14", f"config 부재(fail-closed): {path}")]
    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
    except Exception as exc:  # noqa: BLE001 — 파싱 실패 자체가 계약 위반
        return None, [Finding("U-14", f"config 파싱 실패: {exc}")]
    if not isinstance(data, dict):
        return None, [
            Finding("U-14", f"config 최상위가 매핑이 아님: {type(data).__name__}")
        ]
    return data, []


def _load_csv_rows(
    path: Path, expected_fields: tuple[str, ...], check_id: str
) -> tuple[list[dict[str, str]] | None, list[Finding]]:
    if not path.exists():
        return None, [Finding(check_id, f"파일 부재: {path}")]
    try:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = tuple(reader.fieldnames or ())
            if fieldnames != expected_fields:
                return None, [
                    Finding(
                        check_id,
                        f"헤더 불일치 ({path.name}): {fieldnames} != {expected_fields}",
                    )
                ]
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        return None, [Finding(check_id, f"파싱 실패 ({path.name}): {exc}")]
    return rows, []


def _load_registers(
    repo_root: Path,
) -> tuple[dict[str, dict[str, str]] | None, list[dict[str, str]], list[Finding]]:
    findings: list[Finding] = []
    combined: dict[str, dict[str, str]] = {}
    rows_all: list[dict[str, str]] = []
    ok = True
    for rel in (PART1_REL, DEV_REL):
        rows, errs = _load_csv_rows(repo_root / rel, REGISTER_FIELDS, "K-6")
        if rows is None:
            findings.extend(errs)
            ok = False
            continue
        rows_all.extend(rows)
        for row in rows:
            combined[row["evidence_id"]] = row
    if not ok:
        return None, rows_all, findings
    return combined, rows_all, findings


_OQ11_ROW_RE = re.compile(r"^\|\s*`EV-L(\d+)`\s*\|\s*(.+?)\s*\|", re.MULTILINE)
_OQ11_KIND_RE = re.compile(r"`([A-Z]+)`")


def _load_level_kind_map(
    path: Path,
) -> tuple[dict[int, frozenset[str]] | None, list[Finding]]:
    """OQ-11-DISPOSITION.md 의 승인된 매핑표(L0~L6, 7행)를 파싱한다."""
    if not path.exists():
        return None, [Finding("K-14", f"OQ-11 매핑표 문서 부재: {path}")]
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [Finding("K-14", f"OQ-11 매핑표 문서 읽기 실패: {exc}")]
    rows = _OQ11_ROW_RE.findall(text)
    mapping: dict[int, frozenset[str]] = {}
    for level_str, cell in rows:
        level = int(level_str)
        kinds = frozenset(_OQ11_KIND_RE.findall(cell))
        if not kinds or not kinds <= KIND_VOCAB:
            return None, [
                Finding("K-14", f"OQ-11 매핑표 어휘 밖: EV-L{level} -> {sorted(kinds)}")
            ]
        mapping[level] = kinds
    if sorted(mapping) != list(range(7)):
        return None, [
            Finding("K-14", f"OQ-11 매핑표가 L0..L6 전역이 아님: {sorted(mapping)}")
        ]
    return mapping, []


def build_context(repo_root: Path) -> CheckContext:
    """repo_root 아래 코퍼스를 전부 로드해 ``CheckContext`` 를 구성한다."""
    preload: dict[str, list[Finding]] = {}

    config, config_findings = _load_yaml_config(repo_root / CONFIG_REL)
    if config_findings:
        preload.setdefault("U-14", []).extend(config_findings)

    register_by_id, register_rows, register_findings = _load_registers(repo_root)
    if register_findings:
        preload.setdefault("K-6", []).extend(register_findings)

    required_kinds_rows, rk_findings = _load_csv_rows(
        repo_root / REQUIRED_KINDS_REL, REQUIRED_KINDS_FIELDS, "K-9"
    )
    if rk_findings:
        preload.setdefault("K-9", []).extend(rk_findings)
    required_kinds_by_id: dict[str, frozenset[str]] | None = None
    if required_kinds_rows is not None:
        required_kinds_by_id = {
            row["evidence_id"]: frozenset(row["required_kinds"].split("|"))
            for row in required_kinds_rows
        }

    surface_map_rows, map_findings = _load_csv_rows(
        repo_root / SURFACE_MAP_REL, SURFACE_MAP_FIELDS, "K-1"
    )
    if map_findings:
        preload.setdefault("K-1", []).extend(map_findings)

    uncheckable_rows, unchk_findings = _load_csv_rows(
        repo_root / UNCHECKABLE_REL, UNCHECKABLE_FIELDS, "U-14"
    )
    if unchk_findings:
        preload.setdefault("U-14", []).extend(unchk_findings)

    level_kind_map, level_findings = _load_level_kind_map(repo_root / OQ11_REL)
    if level_findings:
        preload.setdefault("K-14", []).extend(level_findings)

    return CheckContext(
        repo_root=repo_root,
        config=config,
        register_by_id=register_by_id,
        register_rows=register_rows,
        required_kinds_rows=required_kinds_rows,
        required_kinds_by_id=required_kinds_by_id,
        surface_map_rows=surface_map_rows,
        uncheckable_rows=uncheckable_rows,
        level_kind_map=level_kind_map,
        preload_findings=preload,
    )


# ---------------------------------------------------------------------------
# K-4 — binding_basis 해석 (DOC-ID §번호)
# ---------------------------------------------------------------------------

_BASIS_RE = re.compile(r"^(?P<doc>[A-Za-z0-9][A-Za-z0-9_.-]*)\s+§(?P<num>\d+)$")


@cache
def _resolve_basis_cached(doc_id: str, num: str, src_root: Path) -> str | None:
    if not src_root.is_dir():
        return f"소스 루트 부재: {src_root}"
    candidates = sorted(
        p
        for p in src_root.rglob(f"{doc_id}*.md")
        if "patches" not in p.relative_to(src_root).parts
    )
    if len(candidates) != 1:
        return f"DOC-ID {doc_id!r} 해석 실패 ({len(candidates)}개 일치)"
    try:
        text = candidates[0].read_text(encoding="utf-8")
    except OSError as exc:
        return f"DOC-ID {doc_id!r} 파일 읽기 실패: {exc}"
    heading_re = re.compile(rf"^##+\s*{re.escape(num)}[.\s]", re.MULTILINE)
    if not heading_re.search(text):
        return f"{doc_id} 안에 §{num} 헤딩 없음"
    return None


def _resolve_basis(basis: str, src_root: Path) -> str | None:
    m = _BASIS_RE.match(basis.strip())
    if not m:
        return f"basis 형식 불일치: {basis!r}"
    return _resolve_basis_cached(m.group("doc"), m.group("num"), src_root)


# ---------------------------------------------------------------------------
# K-12 — surface_ref 정규형
# ---------------------------------------------------------------------------


def _check_package_ref(ref: str, repo_root: Path) -> str | None:
    if ref == "":
        return "PACKAGE ref 비어 있음"
    if ref.startswith("./"):
        return f"PACKAGE ref './' 접두 거부: {ref!r}"
    if "\\" in ref:
        return f"PACKAGE ref 백슬래시 거부: {ref!r}"
    if "//" in ref:
        return f"PACKAGE ref 중복 슬래시 거부: {ref!r}"
    pure = PurePosixPath(ref)
    if pure.is_absolute():
        return f"PACKAGE ref 절대경로 거부: {ref!r}"
    if any(part == ".." for part in pure.parts):
        return f"PACKAGE ref '..' 조각 거부: {ref!r}"
    target = repo_root / ref
    if target.exists():
        resolved = target.resolve()
        try:
            resolved_rel = resolved.relative_to(repo_root.resolve())
        except ValueError:
            return f"PACKAGE ref symlink 이 repo 밖으로 해석됨: {ref!r}"
        if str(resolved_rel).replace("\\", "/") != ref:
            return (
                "PACKAGE ref 가 실제 경로와 불일치(대소문자/정규화): "
                f"{ref!r} != {resolved_rel!s}"
            )
    return None


def _check_byte_ref(ref: str) -> str | None:
    if ref == "" or ref != ref.strip():
        return f"ref 비정규(공백/빈값): {ref!r}"
    return None


# ---------------------------------------------------------------------------
# K-3 — pytest collect-only
# ---------------------------------------------------------------------------


def _collect_pytest_paths(refs: Iterable[str], repo_root: Path) -> set[str]:
    present: set[str] = set()
    for ref in refs:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q", ref],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            present.add(ref)
    return present


# ---------------------------------------------------------------------------
# 강제 검사들
# ---------------------------------------------------------------------------


def check_k1(ctx: CheckContext) -> list[Finding]:
    """K-1 — MAP 의 (evidence_id, surface_kind, surface_ref) 중복 금지."""
    findings = list(ctx.preload_findings.get("K-1", []))
    if ctx.surface_map_rows is None:
        return findings
    seen: set[tuple[str, str, str]] = set()
    for row in ctx.surface_map_rows:
        key = (row["evidence_id"], row["surface_kind"], row["surface_ref"])
        if key in seen:
            findings.append(Finding("K-1", f"MAP 중복 행: {key}"))
        else:
            seen.add(key)
    return findings


def check_k2(ctx: CheckContext) -> list[Finding]:
    """K-2 — required_kinds 어휘 + floor(evidence) ⊆ kinds."""
    findings: list[Finding] = []
    if (
        ctx.required_kinds_rows is None
        or ctx.register_by_id is None
        or ctx.level_kind_map is None
    ):
        return findings
    for row in ctx.required_kinds_rows:
        eid = row["evidence_id"]
        raw_kinds = row["required_kinds"]
        tokens = raw_kinds.split("|")
        kind_set = set(tokens)
        if not tokens or len(tokens) != len(kind_set) or not kind_set <= KIND_VOCAB:
            findings.append(
                Finding("K-2", f"{eid}: required_kinds 형식/어휘 위반 - {raw_kinds!r}")
            )
            continue
        reg_row = ctx.register_by_id.get(eid)
        if reg_row is None:
            continue  # phantom row — K-6/REV 소관
        try:
            levels = parse_level(reg_row["minimum_evidence_level"])
        except ValueError:
            continue  # K-14 가 별도 보고 (T-48 축)
        if levels is None:
            continue  # Profile-dependent — K-13 소관
        expected_floor = derive_floor(levels, ctx.level_kind_map)
        if not expected_floor <= kind_set:
            findings.append(
                Finding(
                    "K-2",
                    f"{eid}: kinds {sorted(kind_set)} 가 floor "
                    f"{sorted(expected_floor)} 를 포함하지 않음",
                )
            )
    return findings


def check_k3(ctx: CheckContext) -> list[Finding]:
    """K-3 — MAP 각 행의 기대 existence 재파생 대조."""
    findings: list[Finding] = []
    if ctx.surface_map_rows is None:
        return findings

    non_marker_test_refs = sorted(
        {
            row["surface_ref"]
            for row in ctx.surface_map_rows
            if row["surface_kind"] == "TEST" and row["surface_ref"] != MARKER
        }
    )
    collected_tests: set[str] = set()
    if non_marker_test_refs:
        collected_tests = _collect_pytest_paths(non_marker_test_refs, ctx.repo_root)

    for row in ctx.surface_map_rows:
        eid = row["evidence_id"]
        kind = row["surface_kind"]
        ref = row["surface_ref"]
        existence = row["existence"]

        if ref == MARKER:
            expected = "ABSENT"
        elif kind == "PACKAGE":
            expected = "PRESENT" if (ctx.repo_root / ref).exists() else "ABSENT"
        elif kind == "TEST":
            expected = "PRESENT" if ref in collected_tests else "ABSENT"
        elif kind == "REVIEWER":
            reg_row = (ctx.register_by_id or {}).get(eid)
            actual_reviewer = reg_row.get("independent_reviewer") if reg_row else None
            expected = "PRESENT" if actual_reviewer == ref else "ABSENT"
        elif kind in ("RUNTIME", "FAULT"):
            expected = "UNVERIFIABLE"
        else:
            findings.append(Finding("K-3", f"{eid}: 알 수 없는 surface_kind {kind!r}"))
            continue

        if expected != existence:
            findings.append(
                Finding(
                    "K-3",
                    f"{eid}/{kind}: existence={existence!r} 기대={expected!r} "
                    f"(ref={ref!r})",
                )
            )
    return findings


def check_k4(ctx: CheckContext) -> list[Finding]:
    """K-4 — binding_basis/basis 의 <DOC-ID> §<번호> 해석 가능성."""
    findings: list[Finding] = []
    src_root = ctx.repo_root / TOS_SPEC_SRC_REL
    if ctx.required_kinds_rows is not None:
        for row in ctx.required_kinds_rows:
            err = _resolve_basis(row["basis"], src_root)
            if err:
                findings.append(
                    Finding(
                        "K-4", f"{row['evidence_id']} (REQUIRED-KINDS basis): {err}"
                    )
                )
    if ctx.surface_map_rows is not None:
        for row in ctx.surface_map_rows:
            err = _resolve_basis(row["binding_basis"], src_root)
            if err:
                findings.append(
                    Finding("K-4", f"{row['evidence_id']} (MAP binding_basis): {err}")
                )
    return findings


def check_k5_fwd_metrics(ctx: CheckContext) -> list[Finding]:
    """K-5 쌍 지표 + FWD/REV/FWD2 (§5.3).  REV 만 계약 위반, 나머지는 인쇄뿐."""
    findings: list[Finding] = []
    if ctx.required_kinds_rows is None or ctx.surface_map_rows is None:
        return findings

    pairs: set[tuple[str, str]] = set()
    for row in ctx.required_kinds_rows:
        for kind in row["required_kinds"].split("|"):
            pairs.add((row["evidence_id"], kind))

    map_pairs: dict[tuple[str, str], dict[str, str]] = {
        (row["evidence_id"], row["surface_kind"]): row for row in ctx.surface_map_rows
    }

    unmapped = sorted(p for p in pairs if p not in map_pairs)
    planned_unassigned = sorted(
        p for p in pairs if p in map_pairs and map_pairs[p]["surface_ref"] == MARKER
    )
    ctx.observations.append(f"unmapped_pairs={len(unmapped)}")
    ctx.observations.append(f"planned_unassigned_pairs={len(planned_unassigned)}")

    superset = 0
    if ctx.register_by_id is not None and ctx.level_kind_map is not None:
        for row in ctx.required_kinds_rows:
            eid = row["evidence_id"]
            kinds = set(row["required_kinds"].split("|"))
            reg_row = ctx.register_by_id.get(eid)
            if reg_row is None:
                continue
            try:
                levels = parse_level(reg_row["minimum_evidence_level"])
            except ValueError:
                continue
            if levels is None:
                continue
            expected_floor = derive_floor(levels, ctx.level_kind_map)
            if kinds - expected_floor:
                superset += 1
    ctx.observations.append(f"superset_declared_pairs={superset}")

    # REV — MAP 의 모든 evidence_id 가 두 register 에 실재해야 한다 (phantom row).
    if ctx.register_by_id is not None:
        map_ids = {row["evidence_id"] for row in ctx.surface_map_rows}
        for eid in sorted(map_ids - ctx.register_by_id.keys()):
            findings.append(
                Finding(
                    "K-5/FWD-METRICS", f"REV 위반 — MAP 의 phantom evidence_id: {eid}"
                )
            )
    # FWD2(§5.3) — 비마커 PACKAGE/TEST ref 실재는 K-3 가 이미 포섭한다 (no-op).

    # FWD-a (§11 소관 · rc 비결합)
    unmet_zero: list[str] = []
    unmet: list[str] = []
    if (
        ctx.register_by_id is not None
        and ctx.required_kinds_by_id is not None
        and ctx.level_kind_map is not None
    ):
        for eid, row in ctx.register_by_id.items():
            status = row["status"]
            if status not in ("PASS", "READY"):
                continue
            kinds = ctx.required_kinds_by_id.get(eid)
            if kinds is None:
                continue
            try:
                levels = parse_level(row["minimum_evidence_level"])
            except ValueError:
                continue
            if levels is None:
                continue
            expected_floor = derive_floor(levels, ctx.level_kind_map)
            verifiable = kinds & expected_floor & _VERIFIABLE_LEVEL_KINDS
            if not verifiable:
                unmet_zero.append(eid)
                unmet.append(eid)
                continue
            needed = {"PRESENT"} if status == "PASS" else {"PRESENT", "STAND_IN"}
            ok = True
            for kind in verifiable:
                map_row = map_pairs.get((eid, kind))
                if map_row is None or map_row["existence"] not in needed:
                    ok = False
                    break
            if not ok:
                unmet.append(eid)

    ctx.observations.append(f"FWD-a-0 불충족 evidence_id={sorted(unmet_zero)}")
    ctx.observations.append(f"FWD-a 미충족 {len(unmet)}행 (표본={sorted(unmet)[:10]})")
    return findings


def check_k6(ctx: CheckContext) -> list[Finding]:
    """K-6 — REQUIRED-KINDS 의 evidence_id 집합 == floor-도출 가능 register 행."""
    findings = list(ctx.preload_findings.get("K-6", []))
    if ctx.register_by_id is None or ctx.required_kinds_rows is None:
        return findings
    floor_derivable = {
        eid
        for eid, row in ctx.register_by_id.items()
        if row["minimum_evidence_level"] != "Profile-dependent"
    }
    req_ids = {row["evidence_id"] for row in ctx.required_kinds_rows}
    for eid in sorted(floor_derivable - req_ids):
        findings.append(Finding("K-6", f"REQUIRED-KINDS 누락: {eid}"))
    for eid in sorted(req_ids - floor_derivable):
        findings.append(Finding("K-6", f"REQUIRED-KINDS 잉여: {eid}"))
    return findings


def check_k9(ctx: CheckContext) -> list[Finding]:
    """K-9 — EVIDENCE-REQUIRED-KINDS.csv 자체의 로드 무결성."""
    return list(ctx.preload_findings.get("K-9", []))


def check_k11(ctx: CheckContext) -> list[Finding]:
    """K-11 — 비마커 ref 재사용 시 서로 다른 § 를 요구."""
    findings: list[Finding] = []
    if ctx.surface_map_rows is None:
        return findings
    non_marker = [r for r in ctx.surface_map_rows if r["surface_ref"] != MARKER]
    by_ref: dict[str, list[dict[str, str]]] = {}
    for row in non_marker:
        by_ref.setdefault(row["surface_ref"], []).append(row)
    reuse_counts = {ref: len(rows) for ref, rows in by_ref.items() if len(rows) > 1}
    ctx.observations.append(f"ref_reuse_max={max(reuse_counts.values(), default=0)}")
    top = sorted(reuse_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    ctx.observations.append(f"ref_reuse_top={top}")
    for ref, rows in by_ref.items():
        if len(rows) < 2:
            continue
        seen_sections: dict[str, str] = {}
        for row in rows:
            basis = row["binding_basis"]
            if basis in seen_sections:
                findings.append(
                    Finding(
                        "K-11",
                        f"ref {ref!r} 재사용 - 동일 § ({basis}): "
                        f"{seen_sections[basis]} vs {row['evidence_id']}",
                    )
                )
            else:
                seen_sections[basis] = row["evidence_id"]
    return findings


def check_k12(ctx: CheckContext) -> list[Finding]:
    """K-12 — 비마커 surface_ref 정규형."""
    findings: list[Finding] = []
    if ctx.surface_map_rows is None:
        return findings
    for row in ctx.surface_map_rows:
        ref = row["surface_ref"]
        if ref == MARKER:
            continue
        eid = row["evidence_id"]
        kind = row["surface_kind"]
        if kind == "PACKAGE":
            err = _check_package_ref(ref, ctx.repo_root)
        else:
            err = _check_byte_ref(ref)
        if err:
            findings.append(Finding("K-12", f"{eid}/{kind}: {err}"))
    return findings


def check_k13(ctx: CheckContext) -> list[Finding]:
    """K-13 — Profile-dependent 행은 REQUIRED-KINDS/MAP 어디에도 등장 불가."""
    findings: list[Finding] = []
    if ctx.register_by_id is None:
        return findings
    profile_dependent_ids = sorted(
        eid
        for eid, row in ctx.register_by_id.items()
        if row["minimum_evidence_level"] == "Profile-dependent"
    )
    ctx.observations.append(f"profile_dependent_blocked={profile_dependent_ids}")
    req_ids = {row["evidence_id"] for row in (ctx.required_kinds_rows or [])}
    map_ids = {row["evidence_id"] for row in (ctx.surface_map_rows or [])}
    for eid in profile_dependent_ids:
        if eid in req_ids:
            findings.append(
                Finding("K-13", f"{eid}: Profile-dependent 인데 REQUIRED-KINDS 에 등장")
            )
        if eid in map_ids:
            findings.append(
                Finding("K-13", f"{eid}: Profile-dependent 인데 MAP 에 등장")
            )
    return findings


def check_k14(ctx: CheckContext) -> list[Finding]:
    """K-14 — 파싱된 레벨이 매핑 도메인(L0..L6) 밖이면 위반 (T-48 축 겸용)."""
    findings = list(ctx.preload_findings.get("K-14", []))
    if ctx.register_by_id is None or ctx.level_kind_map is None:
        return findings
    for eid, row in ctx.register_by_id.items():
        raw = row["minimum_evidence_level"]
        try:
            levels = parse_level(raw)
        except ValueError as exc:
            findings.append(Finding("K-14", f"{eid}: 레벨 파싱 실패 {raw!r} ({exc})"))
            continue
        if levels is None:
            continue
        for lvl in levels:
            if lvl not in ctx.level_kind_map:
                findings.append(
                    Finding(
                        "K-14", f"{eid}: 레벨 {lvl} (원본 {raw!r}) 이 매핑 도메인 밖"
                    )
                )
    return findings


def _parse_anchor_distribution(raw: str) -> dict[str, int] | None:
    result: dict[str, int] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or "=" not in part:
            return None
        key, _, val = part.partition("=")
        val = val.strip()
        if not val.isdigit():
            return None
        result[key.strip()] = int(val)
    return result


def check_u14(ctx: CheckContext) -> list[Finding]:
    """U-14 — 앵커(정본 A) == 구조 재파생(정본 B) 기계 대조.  + §13.2.1 지표."""
    findings = list(ctx.preload_findings.get("U-14", []))
    if ctx.config is None:
        return findings

    # T-76 — 레벨 분포 앵커.
    anchor_str = ctx.config.get("anchor_evidence_level_distribution")
    if not isinstance(anchor_str, str):
        findings.append(
            Finding("U-14", "config 에 anchor_evidence_level_distribution 없음")
        )
    elif ctx.register_by_id is not None:
        expected = _parse_anchor_distribution(anchor_str)
        if expected is None:
            findings.append(
                Finding("U-14", f"T-76 앵커 형식 파싱 실패: {anchor_str!r}")
            )
        else:
            actual = dict(
                Counter(
                    row["minimum_evidence_level"] for row in ctx.register_by_id.values()
                )
            )
            if expected != actual:
                keys = sorted(set(expected) | set(actual))
                diffs = [k for k in keys if expected.get(k) != actual.get(k)]
                findings.append(Finding("U-14", f"T-76 앵커 불일치: {diffs}"))

    # U-9a — closable=NO id 집합 앵커.
    ids_str = ctx.config.get("anchor_closable_no_ids")
    if not isinstance(ids_str, str):
        findings.append(Finding("U-14", "config 에 anchor_closable_no_ids 없음"))
    elif ctx.uncheckable_rows is not None:
        expected_ids = {s.strip() for s in ids_str.split(",") if s.strip()}
        actual_ids = {
            row["id"] for row in ctx.uncheckable_rows if row["closable"] == "NO"
        }
        if expected_ids != actual_ids:
            findings.append(
                Finding(
                    "U-14",
                    f"U-9a 앵커 불일치: expected={sorted(expected_ids)} "
                    f"actual={sorted(actual_ids)}",
                )
            )

    # U-14-b — 정책값(재파생 대상 아님) 존재/타입만 검증.
    for key in ("owner_track_range_max_width", "phase_min", "phase_max"):
        if key not in ctx.config:
            findings.append(Finding("U-14", f"config 키 부재: {key}"))
        elif not isinstance(ctx.config[key], int) or isinstance(ctx.config[key], bool):
            findings.append(
                Finding("U-14", f"config 키 {key} 타입 불일치: {ctx.config[key]!r}")
            )
    if "oq11_response_deadline" not in ctx.config:
        findings.append(Finding("U-14", "config 키 부재: oq11_response_deadline"))
    elif not isinstance(ctx.config["oq11_response_deadline"], str):
        findings.append(Finding("U-14", "config 키 oq11_response_deadline 타입 불일치"))

    # §13.2.1 지표 (비차단·인쇄).
    if ctx.uncheckable_rows is not None:
        closable_no_rows = sum(
            1 for row in ctx.uncheckable_rows if row["closable"] == "NO"
        )
        imprecise_owner_track = sum(
            1
            for row in ctx.uncheckable_rows
            if _OWNER_TRACK_RANGE_RE.search(row["owner_track"])
        )
        blank_normative_ref_rows = sum(
            1 for row in ctx.uncheckable_rows if not row["normative_ref"].strip()
        )
        ctx.observations.append(f"closable_no_rows={closable_no_rows}")
        ctx.observations.append(f"imprecise_owner_track={imprecise_owner_track}")
        ctx.observations.append(f"blank_normative_ref_rows={blank_normative_ref_rows}")

    return findings


CONTRACT_CHECKS: dict[str, Callable[[CheckContext], list[Finding]]] = {
    "K-1": check_k1,
    "K-2": check_k2,
    "K-3": check_k3,
    "K-4": check_k4,
    "K-5/FWD-METRICS": check_k5_fwd_metrics,
    "K-6": check_k6,
    "K-9": check_k9,
    "K-11": check_k11,
    "K-12": check_k12,
    "K-13": check_k13,
    "K-14": check_k14,
    "U-14": check_u14,
}


def run_checks(ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    for _check_id, fn in CONTRACT_CHECKS.items():
        findings.extend(fn(ctx))
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        required=True,
        help="D0-A 완료 계약 증분 C1(데이터-플레인) 강제 검사를 실행한다",
    )
    parser.parse_args(argv)  # --check 는 존재 자체가 게이트다; 값은 쓰지 않는다

    try:
        ctx = build_context(REPO_ROOT)
        findings = run_checks(ctx)
    except (
        Exception
    ) as exc:  # noqa: BLE001 — 내부 예외로 조용히 green 이 되어선 안 된다
        print(f"tos-completion-status: ERROR — 내부 예외 (rc=2): {exc}")
        return 2

    print("미구현(C2 이후) — 강제 지점 미등록:")
    for check_id in DEFERRED_CONTRACTS:
        print(f"  - {check_id}")
    print()

    print("완료 관측 (§11 소관 · rc 비결합):")
    for obs in ctx.observations:
        print(f"  {obs}")
    print()

    if findings:
        for finding in findings:
            print(str(finding))
        print(f"RESULT: RED (violations={len(findings)})")
        return 1

    print("RESULT: GREEN (violations=0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
