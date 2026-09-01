#!/usr/bin/env python3
"""tos Phase-0 완료 계약 — D0-A 검사기, 증분 C1 (데이터-플레인 계약).

정본: ``docs/plans/2026-08-12-tos-phase0-completion-contract-design.md``
(blob 결속 — 이 파일은 절대 편집하지 않는다.  모호한 지점은
``python tools/tos_contract_index.py --locate <id>`` 로 절만 확인한다).

이 검사기는 증분 C1 + C2a + C2b + C2c 가 강제하는 다음 등록 id만 다룬다::

    K-1 · K-2 · K-3 · K-4 · K-5/FWD-METRICS · K-6 · K-9 · K-11 · K-12 · K-13
    · K-14 · U-14 (C1)
    U-12 · U-13 · U-1a · U-4 · U-5 (C2a)
    U-15 (C2b — d0a_entry_state 9값 · d0a_entry_provenance_state 8값 두
    상태 기계의 승계.  좌변 명세·회귀 기준선은 ``tools/tos_entry_harness.sh``
    이며 그 판정 로직을 Python 으로 정확 복제한다.  우변은 §12.3.4 U-15-g
    사후 provenance 관측이다.)
    U-16 (C2c — §13.6.5 closable_no_provenance_state 12값 상태 기계.  판정
    입력을 격리 git 스냅샷 안에서 소비한다 — §13.6.5 "격리 스냅샷 기층".)

``DEFERRED_CONTRACTS`` 에 등재된 계약(T-71 축)은 C2c 이후 소관이며, 이
파일에는 강제 지점이 없다(UNCHK-019 축 — 정직 노출).  U-17 은 DEFERRED 가
아니라 ``--check`` 밖의 별도 강제 지점(가드 체인·live —
``tools/u17-verify.sh``)이다 — main() 이 별도 섹션으로 처분을 인쇄한다.

git 소비 규율 (C2a — §12.3.1 "공통: git 소비"): U-12/U-13 의 권위 판정
입력(OQ-11 아티팩트 · bound 문서 2종 · OQ-11 원장)은 워킹트리가 아니라
**HEAD blob** 을 ``git show HEAD:<path>`` 로 소비한다.  이력 판정(trigger
commit·도입 커밋)은 ``git log``/``git rev-list``/``git cat-file`` 로
파생한다.  config/tos_completion.yaml 은 C1 과 동일하게 워킹트리 소비.

U-16 은 조상성·원장·레지스터 blob 소비를 전부 **격리 git 스냅샷**
(``git clone --no-local --no-hardlinks`` + replace/grafts canary) 안에서
수행한다 — §13.6.5 "격리 스냅샷 기층".  판정 후 스냅샷은 즉시 삭제한다.

rc 의미론 (핀 — 이 문서가 정본):
    * 계약 위반(``Finding``) >= 1  ->  exit 1
    * 위반 0                       ->  exit 0
    완료 관측(§11 소관: FWD-a·planned_unassigned_pairs 등)은 rc 에 결합하지
    않는다 — "완료 관측 (§11 소관 · rc 비결합)" 섹션에 인쇄만 한다.  근거:
    §12.2 "신규 검사는 처음부터 green 인 상태로 도입" + "Phase 0 의 종료
    조건은 FWD-a 에만 걸린다"(§5.2.4) — 완료 미도달은 repo 결함이 아니다.
    U-12 상태 기계의 rc 결합(T-78 — 상태 ≠ NOT_REQUIRED 는 전부 위반)은
    C2a 에서 구현된다.  U-16 상태 기계의 rc 결합(T-82 — 상태 ≠
    NO_ROWS_CLEAR 는 전부 위반)은 C2c 에서 구현된다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
OQ11_LEDGER_REL = Path("tos-spec/src/part-1-foundation/decisions/OQ-11-RAISE-LEDGER.md")
# U-16 §13.6.5 — closable=NO 전이 승인 원장 (OQ-11 원장과 별도 파일 · U-16-b).
U16_LEDGER_REL = Path(
    "tos-spec/src/part-1-foundation/decisions/CLOSABLE-NO-APPROVAL-LEDGER.md"
)
TOS_SPEC_SRC_REL = Path("tos-spec/src")

# U-15 §12.3.4-R — tools/tos_entry_harness.sh 의 권위 입력 경로 (BP1/BP2 는
# U12_BOUND_PATHS 와 정확히 같은 두 문서).
STAMPS_REL = Path("docs/reviews/phase0-completion-contract")

# U-12 §12.3.1 BOUND_PATHS — 정확히 이 둘 · 이 표기(경로 문자열이 digest 입력에 실린다).
U12_BOUND_PATHS: tuple[Path, ...] = (
    Path("docs/plans/2026-08-12-tos-phase0-completion-contract-design.md"),
    Path("docs/plans/2026-08-11-tos-completion-development-plan.md"),
)

KIND_VOCAB = frozenset({"PACKAGE", "RUNTIME", "TEST", "FAULT", "REVIEWER"})
MARKER = "PLANNED_UNASSIGNED"

_UNSET = object()  # "인자 미전달" 표지 — None 과 구별해야 하는 캐시 우회용 sentinel.

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

# C2c 이후 소관 — 이 파일에는 강제 지점이 없다 (UNCHK-019 축 · 정직 노출).
# U-16 은 C2c 에서 CONTRACT_CHECKS 로 승격됐다.  U-17 은 DEFERRED 가 아니라
# `--check` 밖의 별도 강제 지점(가드 체인·live — tools/u17-verify.sh)이다.
DEFERRED_CONTRACTS: tuple[str, ...] = ("T-71",)

_VERIFIABLE_LEVEL_KINDS = frozenset({"PACKAGE", "TEST", "REVIEWER"})


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
    state_lines: list[str] = field(default_factory=list)
    oq11_artifact_head: dict[str, object] | None = None
    _owner_track_cache: dict[str, list[Finding]] | None = None


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


# ---------------------------------------------------------------------------
# C2a — git 소비 (커밋-전용 규율 · §12.3.1 "공통: git 소비")
# ---------------------------------------------------------------------------

_GIT_TIMEOUT = 30
_OQ11_YAML_FENCE_RE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)


def _git_show_blob(rel_path: Path, commit: str, repo_root: Path) -> bytes | None:
    """``git show <commit>:<rel_path>``.  blob 부재/실패 -> None (예외를 던지지 않는다)."""
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:{rel_path.as_posix()}"],
            cwd=repo_root,
            capture_output=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _parse_oq11_yaml_fence(blob: bytes) -> dict[str, object] | None:
    """아티팩트 본문 첫 fenced ```yaml 블록을 파싱한다."""
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        return None
    m = _OQ11_YAML_FENCE_RE.search(text)
    if not m:
        return None
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def _load_oq11_artifact_at(commit: str, repo_root: Path) -> dict[str, object] | None:
    """OQ-11 아티팩트(``OQ11_REL``)를 ``commit`` 시점 blob 에서 파싱한다."""
    blob = _git_show_blob(OQ11_REL, commit, repo_root)
    if blob is None:
        return None
    return _parse_oq11_yaml_fence(blob)


_OQ11_DISPOSITION_VOCAB = frozenset(
    {
        "RESOLVED_MAPPING_APPROVED",
        "RESOLVED_MAPPING_REJECTED",
        "DEFERRED_WITH_SCOPE",
        "REFUSED",
    }
)


def _bound_set_digest_from_getter(
    paths: Sequence[Path], get_bytes: Callable[[str], bytes | None]
) -> str | None:
    """U-12/U-15 digest 레시피 공용 코어 — 바이트 정확 복제.

    ``LC_ALL=C`` 정렬 후 각 경로의 바이트열(``get_bytes`` 가 공급) sha256 hex
    를 ``<hex>  <path>\\n`` 행으로 이어붙인 바이트열의 sha256 hex.  바이트를
    하나라도 얻지 못하면 ``None`` (호출자가 "불일치로 접는다"를 담당).
    """
    posix_paths = sorted({p.as_posix() for p in paths})
    lines: list[bytes] = []
    for p in posix_paths:
        blob = get_bytes(p)
        if blob is None:
            return None
        file_hash = hashlib.sha256(blob).hexdigest()
        lines.append(f"{file_hash}  {p}\n".encode())
    return hashlib.sha256(b"".join(lines)).hexdigest()


def _compute_bound_set_digest(
    paths: Sequence[Path], commit: str, repo_root: Path
) -> str | None:
    """U-12 digest 레시피 — ``commit`` 시점 blob 기준(커밋-전용 규율)."""
    return _bound_set_digest_from_getter(
        paths, lambda p: _git_show_blob(Path(p), commit, repo_root)
    )


def _compute_bound_set_digest_worktree(
    paths: Sequence[Path], repo_root: Path
) -> str | None:
    """U-15 R-2 digest 레시피 — **워킹트리 파일** 기준(§12.3.4-R 좌변 규율).

    ``_compute_bound_set_digest`` 와 레시피(정렬·해시 결합)를 공유하되,
    소스만 커밋 blob 대신 워킹트리 파일로 바뀐다.
    """

    def _read(p: str) -> bytes | None:
        try:
            return (repo_root / p).read_bytes()
        except OSError:
            return None

    return _bound_set_digest_from_getter(paths, _read)


def oq11_rebinding_required(
    commit: str,
    repo_root: Path,
    *,
    artifact: dict[str, object] | None = _UNSET,  # type: ignore[assignment]
) -> bool:
    """U-12 ① 트리거 술어 — 임의 커밋 ``commit`` 에서 평가 가능하게 함수화.

    (i) 아티팩트 blob 부재 (ii) disposition 어휘 밖 (iii) bound_paths 불일치
    (iv) digest 재계산 불일치(blob 부재 경로 포함) 중 하나라도 참이면 True.
    """
    if artifact is _UNSET:
        artifact = _load_oq11_artifact_at(commit, repo_root)
    if artifact is None:
        return True  # (i)
    disposition = artifact.get("disposition")
    if disposition not in _OQ11_DISPOSITION_VOCAB:
        return True  # (ii)
    declared_paths = artifact.get("bound_paths")
    expected_paths = {p.as_posix() for p in U12_BOUND_PATHS}
    if not isinstance(declared_paths, list) or set(declared_paths) != expected_paths:
        return True  # (iii)
    bound_digest = artifact.get("bound_set_digest")
    recomputed = _compute_bound_set_digest(U12_BOUND_PATHS, commit, repo_root)
    return recomputed is None or recomputed != bound_digest  # (iv)


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

    # C2a — U-12/U-13 권위 판정 입력: OQ-11 아티팩트는 HEAD blob 소비 (워킹트리 아님).
    oq11_artifact_head = _load_oq11_artifact_at("HEAD", repo_root)

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
        oq11_artifact_head=oq11_artifact_head,
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

    # §13.2.1 지표 (비차단·인쇄).  imprecise_owner_track 은 U-1a/U-4/U-5 공용 계산
    # (``_owner_track_report``) 으로 이관됐다 — 문법 판정(§13.6.4)과 계수를 단일
    # 소스로 결속해, C1 의 옛 정규식 계수(``Phase \d+-\d+`` 부분일치)와 값이
    # 갈라지지 않게 한다 — 실코퍼스 기준 두 계산이 동치임을 검증했다.
    if ctx.uncheckable_rows is not None:
        closable_no_rows = sum(
            1 for row in ctx.uncheckable_rows if row["closable"] == "NO"
        )
        blank_normative_ref_rows = sum(
            1 for row in ctx.uncheckable_rows if not row["normative_ref"].strip()
        )
        ctx.observations.append(f"closable_no_rows={closable_no_rows}")
        ctx.observations.append(f"blank_normative_ref_rows={blank_normative_ref_rows}")
    _owner_track_report(ctx)  # imprecise_owner_track·unassigned_owner_rows 관측 보장

    return findings


# ---------------------------------------------------------------------------
# U-12 — OQ-11 raise ledger 파싱 (HEAD blob 소비)
# ---------------------------------------------------------------------------

_LEDGER_HEADER = ("episode_id", "raised_at", "trigger_at_head", "closed_by")
_LEDGER_HEADING_RE = re.compile(r"^## 에피소드\s*$", re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^## ", re.MULTILINE)
_TABLE_SEPARATOR_RE = re.compile(r"^:?-+:?$")


@dataclass(frozen=True)
class LedgerRow:
    """OQ-11-RAISE-LEDGER.md 의 정규화된 한 행 (U-12 ② 행 스키마)."""

    episode_id: str
    raised_at: str
    trigger_at_head: str
    closed_by: str

    def as_tuple(self) -> tuple[str, str, str, str]:
        return (self.episode_id, self.raised_at, self.trigger_at_head, self.closed_by)


def _split_table_row(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


def _extract_md_table_after_heading(
    text: str, heading_re: re.Pattern[str]
) -> tuple[list[str], list[list[str]]] | None:
    """``heading_re`` 절 아래 첫 md 표를 (header, data_rows) 로 반환 (U-12/U-16 공용)."""
    m = heading_re.search(text)
    if not m:
        return None
    rest = text[m.end() :]
    next_m = _NEXT_HEADING_RE.search(rest)
    section = rest[: next_m.start()] if next_m else rest
    table_lines = [
        ln.strip() for ln in section.splitlines() if ln.strip().startswith("|")
    ]
    if not table_lines:
        return None
    header = _split_table_row(table_lines[0])
    body_lines = table_lines[1:]
    if body_lines:
        first_cells = _split_table_row(body_lines[0])
        if first_cells and all(_TABLE_SEPARATOR_RE.match(c) for c in first_cells):
            body_lines = body_lines[1:]
    data_rows = [_split_table_row(ln) for ln in body_lines]
    return header, data_rows


def _extract_episode_table(text: str) -> tuple[list[str], list[list[str]]] | None:
    """ "## 에피소드" 절 아래 첫 md 표를 (header, data_rows) 로 반환."""
    return _extract_md_table_after_heading(text, _LEDGER_HEADING_RE)


def _parse_utc_iso8601(value: str) -> datetime:
    v = value.strip()
    if v.endswith(("Z", "z")):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        raise ValueError("timezone 정보 없음(UTC 명시 필요)")
    return dt.astimezone(UTC)


def _validate_ledger_rows(
    header: list[str], data_rows: list[list[str]]
) -> tuple[list[LedgerRow] | None, str | None]:
    """U-12 ② 행 스키마 검증 — 필드 누락·형식 오류·중복 열린 행."""
    if tuple(header) != _LEDGER_HEADER:
        return None, f"헤더 불일치: {header} != {list(_LEDGER_HEADER)}"
    rows: list[LedgerRow] = []
    open_count = 0
    for idx, cells in enumerate(data_rows):
        if len(cells) != 4:
            return None, f"행 {idx}: 필드 수 불일치 ({len(cells)} != 4)"
        episode_id, raised_at, trigger_at_head, closed_by = cells
        if not episode_id.strip():
            return None, f"행 {idx}: episode_id 누락"
        if not raised_at.strip():
            return None, f"행 {idx}: raised_at 누락"
        if not trigger_at_head.strip():
            return None, f"행 {idx}: trigger_at_head 누락"
        try:
            _parse_utc_iso8601(raised_at)
        except ValueError as exc:
            return None, f"행 {idx}: raised_at 파싱 실패 ({exc})"
        if not closed_by.strip():
            open_count += 1
        rows.append(
            LedgerRow(
                episode_id.strip(),
                raised_at.strip(),
                trigger_at_head.strip(),
                closed_by.strip(),
            )
        )
    if open_count > 1:
        return None, f"열린 행 중복: {open_count}개"
    return rows, None


def _load_ledger_rows_at(
    commit: str, repo_root: Path
) -> tuple[list[LedgerRow] | None, str | None]:
    """원장을 ``commit`` 시점 blob 에서 로드·검증한다.  U-12 ①-②(1)(2)."""
    blob = _git_show_blob(OQ11_LEDGER_REL, commit, repo_root)
    if blob is None:
        return None, "원장 blob 부재"
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, f"원장 디코딩 실패: {exc}"
    table = _extract_episode_table(text)
    if table is None:
        return None, "원장 표 파싱 불가(## 에피소드 절 없음)"
    return _validate_ledger_rows(*table)


# ---------------------------------------------------------------------------
# U-12 — git 이력 구조 파생 (trigger_commit · 발효 커밋 · 행 도입 커밋)
# ---------------------------------------------------------------------------


def _resolve_commit(ref: str, repo_root: Path) -> str:
    """``ref``(``HEAD`` 등)를 실제 커밋 해시로 해석한다 — graph 조회 키 정합용."""
    result = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        check=True,
    )
    return result.stdout.strip()


def _git_ancestor_graph(
    commit: str, repo_root: Path
) -> dict[str, tuple[int, list[str]]]:
    """``commit`` 의 전체 조상(포함)을 ``{hash: (author_epoch, [parent hashes])}`` 로."""
    result = subprocess.run(
        ["git", "log", "--pretty=format:%H|%at|%P", commit],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        check=True,
    )
    graph: dict[str, tuple[int, list[str]]] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        h, at, parents = line.split("|", 2)
        parent_list = parents.split() if parents.strip() else []
        graph[h] = (int(at), parent_list)
    return graph


def _find_trigger_commit(
    head: str, graph: dict[str, tuple[int, list[str]]], repo_root: Path
) -> tuple[str, int] | None:
    """①-b — HEAD 에서 모든 부모를 역탐색, 술어 False 커밋에서 하강 중단.

    True-영역 R 을 구성하고 경계 B(부모 없음 ∨ 어떤 부모가 False)를 뽑아
    (author date 최소, commit id 사전순 최소) 로 유일화한다.
    """
    pred_cache: dict[str, bool] = {}

    def pred(c: str) -> bool:
        if c not in pred_cache:
            pred_cache[c] = oq11_rebinding_required(c, repo_root)
        return pred_cache[c]

    if head not in graph or not pred(head):
        return None

    boundary: set[str] = set()
    visited: set[str] = set()
    stack = [head]
    while stack:
        c = stack.pop()
        if c in visited:
            continue
        visited.add(c)
        if not pred(c):
            continue
        _, parents = graph.get(c, (0, []))
        if not parents:
            boundary.add(c)
            continue
        any_false = False
        for p in parents:
            if p in graph and pred(p):
                stack.append(p)
            else:
                any_false = True
        if any_false:
            boundary.add(c)

    if not boundary:
        return None
    best = min(boundary, key=lambda c: (graph[c][0], c))
    return best, graph[best][0]


def _find_introduction_commits(
    graph: dict[str, tuple[int, list[str]]], repo_root: Path, rel_path: Path
) -> list[str]:
    """D = {x : blob(x) 존재 ∧ ∀p∈parents(x): blob(p) 부재} — 파일 도입 커밋."""
    exists_cache: dict[str, bool] = {}

    def exists(c: str) -> bool:
        if c not in exists_cache:
            result = subprocess.run(
                ["git", "cat-file", "-e", f"{c}:{rel_path.as_posix()}"],
                cwd=repo_root,
                capture_output=True,
                timeout=_GIT_TIMEOUT,
                check=False,
            )
            exists_cache[c] = result.returncode == 0
        return exists_cache[c]

    found: list[str] = []
    for commit in graph:
        if not exists(commit):
            continue
        _, parents = graph[commit]
        if all(not exists(p) for p in parents):
            found.append(commit)
    return found


def _find_row_introduction_commits(
    graph: dict[str, tuple[int, list[str]]],
    repo_root: Path,
    target_row: tuple[str, str, str, str],
) -> list[str]:
    """행∈rows(x) ∧ ∀p: 행∉rows(p) — 정규화 4필드 튜플의 도입 커밋."""
    rows_cache: dict[str, set[tuple[str, str, str, str]]] = {}

    def rows_at(c: str) -> set[tuple[str, str, str, str]]:
        if c not in rows_cache:
            parsed, _err = _load_ledger_rows_at(c, repo_root)
            rows_cache[c] = {r.as_tuple() for r in parsed} if parsed else set()
        return rows_cache[c]

    found: list[str] = []
    for commit in graph:
        if target_row not in rows_at(commit):
            continue
        _, parents = graph[commit]
        if all(target_row not in rows_at(p) for p in parents):
            found.append(commit)
    return found


_DEADLINE_DAYS_RE = re.compile(r"^(\d+)d$")


def _parse_deadline_days(raw: str) -> int:
    m = _DEADLINE_DAYS_RE.match(raw.strip())
    if not m:
        raise ValueError(f"형식 밖(<정수>d 필요): {raw!r}")
    return int(m.group(1))


def derive_oq11_raise_state(ctx: CheckContext) -> tuple[str, str]:
    """U-12 §12.3.1 — 7값 상태 기계.  평가 순서 핀(문서 순서 그대로):

    1/2. 원장 blob 부재·표 파싱 불가·스키마 위반           -> RAISE_MALFORMED
    3.   required = oq11_rebinding_required(HEAD); False   -> NOT_REQUIRED (유일 통과)
    4.   (required) 열린 에피소드 0                         -> RAISE_MISSING
    5.   구조 파생 실패(trigger_commit·발효 커밋·행 도입     -> RAISE_PROVENANCE_UNVERIFIABLE
         커밋 중 |D| != 1)
    6.   trigger_at_head 기재 != 재파생 trigger_commit      -> RAISE_MALFORMED
    7.   config.oq11_response_deadline == 'DEADLINE_UNSET'  -> DEADLINE_UNSET
    8.   now - raised_at_effective <= deadline              -> PENDING_WITHIN
         >  deadline                                        -> NO_RESPONSE

    Returns:
        (state, detail) — detail 은 사람이 읽는 근거 문자열(rc 에 영향 없음).
    """
    repo_root = ctx.repo_root

    # 1/2.
    rows, err = _load_ledger_rows_at("HEAD", repo_root)
    if rows is None:
        return "RAISE_MALFORMED", err or "원장 로드 실패"

    # 3.
    required = oq11_rebinding_required(
        "HEAD", repo_root, artifact=ctx.oq11_artifact_head
    )
    if not required:
        return "NOT_REQUIRED", "재결속 불필요(트리거 4항 전부 불성립)"

    # 4.
    open_rows = [r for r in rows if not r.closed_by]
    if not open_rows:
        return "RAISE_MISSING", "재결속 트리거 성립 · 열린 에피소드 없음"
    open_row = open_rows[0]

    # 5 (trigger_commit).
    head_commit = _resolve_commit("HEAD", repo_root)
    graph = _git_ancestor_graph(head_commit, repo_root)
    trigger = _find_trigger_commit(head_commit, graph, repo_root)
    if trigger is None:
        return "RAISE_PROVENANCE_UNVERIFIABLE", "trigger_commit 유일화 실패"
    trigger_commit, trigger_epoch = trigger

    # 5 (LEDGER 발효 커밋).
    ledger_intro = _find_introduction_commits(graph, repo_root, OQ11_LEDGER_REL)
    if len(ledger_intro) != 1:
        return (
            "RAISE_PROVENANCE_UNVERIFIABLE",
            f"LEDGER 발효 커밋 |D|={len(ledger_intro)}",
        )
    ledger_intro_epoch = graph[ledger_intro[0]][0]
    trigger_at_derived_epoch = max(trigger_epoch, ledger_intro_epoch)

    # 5 (행 도입 커밋).
    row_intro = _find_row_introduction_commits(graph, repo_root, open_row.as_tuple())
    if len(row_intro) != 1:
        return "RAISE_PROVENANCE_UNVERIFIABLE", f"행 도입 커밋 |D|={len(row_intro)}"
    row_intro_epoch = graph[row_intro[0]][0]

    # 6.
    if open_row.trigger_at_head != trigger_commit:
        return (
            "RAISE_MALFORMED",
            f"trigger_at_head={open_row.trigger_at_head!r} != 재파생 trigger_commit="
            f"{trigger_commit!r}",
        )

    # 7.
    deadline_raw = (ctx.config or {}).get("oq11_response_deadline")
    if deadline_raw == "DEADLINE_UNSET":
        return "DEADLINE_UNSET", "config.oq11_response_deadline == DEADLINE_UNSET"
    if not isinstance(deadline_raw, str):
        return (
            "RAISE_MALFORMED",
            f"oq11_response_deadline 타입 불일치: {deadline_raw!r}",
        )
    try:
        deadline_days = _parse_deadline_days(deadline_raw)
    except ValueError as exc:
        return "RAISE_MALFORMED", f"oq11_response_deadline 형식 위반: {exc}"

    # 8.
    raised_at_epoch = int(_parse_utc_iso8601(open_row.raised_at).timestamp())
    raised_at_effective_epoch = min(
        raised_at_epoch, row_intro_epoch, trigger_at_derived_epoch
    )
    now_epoch = int(time.time())
    elapsed_days = (now_epoch - raised_at_effective_epoch) / 86400.0
    if elapsed_days <= deadline_days:
        return (
            "PENDING_WITHIN",
            f"elapsed={elapsed_days:.4f}d <= deadline={deadline_days}d",
        )
    return "NO_RESPONSE", f"elapsed={elapsed_days:.4f}d > deadline={deadline_days}d"


def check_u12(ctx: CheckContext) -> list[Finding]:
    """U-12 — oq11_raise_state 7값 상태 기계.  상태 != NOT_REQUIRED 는 전부 위반(T-78)."""
    state, detail = derive_oq11_raise_state(ctx)
    ctx.state_lines.append(f"oq11_raise_state={state}")
    if state == "NOT_REQUIRED":
        return []
    return [Finding("U-12", f"{state}: {detail}")]


# ---------------------------------------------------------------------------
# U-13 — deferred_scope 스키마 (§12.3.1 U-13 · OQ-11 아티팩트는 HEAD blob 소비)
# ---------------------------------------------------------------------------

_EVIDENCE_ID_RE = re.compile(r"^[A-Z]+-EV-[0-9]{3}$")


def check_u13(ctx: CheckContext) -> list[Finding]:
    """U-13-a..f — deferred_scope 존재/일치·GLOBAL/ROW_SUBSET 스키마·우주 결속."""
    findings: list[Finding] = []
    artifact = ctx.oq11_artifact_head
    if artifact is None:
        return findings  # 부재/파싱 실패는 U-12 트리거 술어 (i)/(ii) 가 이미 포섭

    disposition = artifact.get("disposition")
    has_scope = "deferred_scope" in artifact
    scope = artifact.get("deferred_scope")

    # U-13-a
    if disposition == "DEFERRED_WITH_SCOPE" and not has_scope:
        findings.append(
            Finding("U-13", "U-13-a: DEFERRED_WITH_SCOPE 인데 deferred_scope 없음")
        )
    if disposition != "DEFERRED_WITH_SCOPE" and has_scope:
        findings.append(
            Finding(
                "U-13", f"U-13-a: disposition={disposition!r} 인데 deferred_scope 존재"
            )
        )

    if not has_scope or not isinstance(scope, dict):
        return findings

    # U-13-d 우주 (+ 보조 fail-closed — 문법 밖 evidence_id 즉시 red)
    all_ids = [row["evidence_id"] for row in ctx.register_rows]
    bad_ids = sorted({eid for eid in all_ids if not _EVIDENCE_ID_RE.match(eid)})
    if bad_ids:
        findings.append(
            Finding("U-13", f"U-13-d: 레지스터에 문법 밖 evidence_id: {bad_ids}")
        )
    universe = {eid for eid in all_ids if _EVIDENCE_ID_RE.match(eid)}

    kind = scope.get("kind")
    if kind == "GLOBAL":
        # U-13-b
        if "rows" in scope:
            findings.append(Finding("U-13", "U-13-b: kind=GLOBAL 인데 rows 존재"))
        ctx.observations.append(
            "U-13 deferred_scope kind=GLOBAL — REFUSED 동일 처분(완료 관측)"
        )
    elif kind == "ROW_SUBSET":
        # U-13-c
        raw_rows = scope.get("rows")
        if not isinstance(raw_rows, list) or not raw_rows:
            findings.append(Finding("U-13", "U-13-c: rows 비었거나 부재"))
            rows_list: list[object] = raw_rows if isinstance(raw_rows, list) else []
        else:
            rows_list = raw_rows
            if len(rows_list) != len(set(rows_list)):
                findings.append(Finding("U-13", "U-13-c: rows 중복"))
        orphan = sorted(str(r) for r in (set(rows_list) - universe))
        if orphan:
            findings.append(
                Finding("U-13", f"U-13-c: rows 가 우주 밖 id 포함: {orphan}")
            )
        remainder_ok = scope.get("remainder_mapping_approved")
        if remainder_ok is not True:
            findings.append(
                Finding(
                    "U-13",
                    f"U-13-c: remainder_mapping_approved != true ({remainder_ok!r})",
                )
            )

        # U-13-e/f — DEFERRED_WITH_SCOPE 일 때 전문 인쇄(완료 관측 · rc 비결합).
        if disposition == "DEFERRED_WITH_SCOPE" and ctx.register_by_id is not None:
            judged = {
                eid
                for eid, row in ctx.register_by_id.items()
                if row["status"] in ("PASS", "READY")
            }
            rows_set = set(rows_list)
            fwd_a_excluded_rows = sorted(str(r) for r in (rows_set & judged))
            remainder_rows = sorted(str(r) for r in (rows_set - judged))
            ctx.observations.append(f"U-13 fwd_a_excluded_rows={fwd_a_excluded_rows}")
            ctx.observations.append(f"U-13 remainder_rows={remainder_rows}")
    else:
        findings.append(Finding("U-13", f"U-13-c: kind 어휘 밖 또는 누락: {kind!r}"))

    return findings


# ---------------------------------------------------------------------------
# U-15 — d0a_entry_state(9값) · d0a_entry_provenance_state(8값) 두 상태 기계
# (증분 C2b · §12.3.4-R · §12.3.4 U-15-g).  좌변 명세·회귀 기준선은
# ``tools/tos_entry_harness.sh`` — 이 섹션은 그 판정 로직의 Python 복제다.
# ---------------------------------------------------------------------------

_D0A_ENTRY_STATES: tuple[str, ...] = (
    "ENTRY_OK",
    "HARNESS_ABORTED",
    "FREEZE_VIOLATED",
    "REBINDING_REQUIRED",
    "APPROVAL_ABSENT",
    "APPROVAL_NOT_APPROVE",
    "APPROVAL_SCOPE_MISMATCH",
    "APPROVAL_PROVENANCE_UNVERIFIABLE",
    "APPROVAL_STALE",
)

_D0A_ENTRY_PROVENANCE_STATES: tuple[str, ...] = (
    "ENTRY_PROVENANCE_CLEAR",
    "NOT_STARTED",
    "PROVENANCE_UNVERIFIABLE",
    "MULTIPLE_INTRODUCTIONS",
    "ENTRY_TRAILER_MALFORMED",
    "PARENT_MISMATCH",
    "TRANSCRIPT_NOT_ENTRY_OK",
    "TRANSCRIPT_MISSING",
)


def _git_status_porcelain_paths(paths: Sequence[Path], repo_root: Path) -> str | None:
    """``git status --porcelain -- <paths...>``.  실패 -> ``None``."""
    args = ["git", "status", "--porcelain", "--", *[p.as_posix() for p in paths]]
    try:
        result = subprocess.run(
            args,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _git_ls_tree_dirs(rel: Path, commit: str, repo_root: Path) -> list[str]:
    """``git ls-tree -d --name-only <commit> <rel>/`` — 직계 하위 디렉터리만."""
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-d", "--name-only", commit, f"{rel.as_posix()}/"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    # LC_ALL=C 정렬 — ASCII 이름(타임스탬프 디렉터리)은 codepoint 순과 동치.
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def _git_cat_file_exists(ref: str, repo_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", ref],
            cwd=repo_root,
            capture_output=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _git_is_ancestor(ancestor: str, descendant: str, repo_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=repo_root,
            capture_output=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _git_log_touching(
    range_spec: str, paths: Sequence[Path], repo_root: Path
) -> str | None:
    args = [
        "git",
        "log",
        "--full-history",
        "--format=%H",
        range_spec,
        "--",
        *[p.as_posix() for p in paths],
    ]
    try:
        result = subprocess.run(
            args,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def derive_d0a_entry_state(ctx: CheckContext) -> tuple[str, str]:
    """§12.3.4-R U-15 — ``tools/tos_entry_harness.sh`` R-0~R-7 의 Python 복제.

    판정 미산출 경로 폐쇄 — 미예기 예외는 전부 ``HARNESS_ABORTED`` 로 접는다
    (하니스 ``trap EXIT`` 의 등가물).

    Returns:
        (state, detail) — detail 은 사람이 읽는 근거 문자열(rc 에 영향 없음).
    """
    try:
        return _derive_d0a_entry_state_inner(ctx)
    except Exception as exc:  # noqa: BLE001 — 판정 미산출 경로 폐쇄
        return "HARNESS_ABORTED", f"판정 미산출 상태로 종료 — 미예기 예외: {exc}"


def _derive_d0a_entry_state_inner(ctx: CheckContext) -> tuple[str, str]:
    repo_root = ctx.repo_root
    bp1, bp2 = U12_BOUND_PATHS
    expected_paths = {p.as_posix() for p in U12_BOUND_PATHS}
    want_sorted = sorted(expected_paths)

    # R-0 — 실행 시점 결속 + 권위 입력 전부의 동결 확인.
    try:
        _resolve_commit("HEAD", repo_root)
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        return "HARNESS_ABORTED", "git rev-parse 실패"

    for f in (bp1, bp2):
        if not (repo_root / f).exists():
            return "HARNESS_ABORTED", f"입력 부재: {f}"

    dirty = _git_status_porcelain_paths((bp1, bp2, OQ11_REL, STAMPS_REL), repo_root)
    if dirty is None:
        return "HARNESS_ABORTED", "git status 실패"
    if dirty.strip():
        return "FREEZE_VIOLATED", f"권위 입력 미커밋 변경: {dirty.strip()}"

    # R-1 — bound_paths 집합 == 계약이 요구하는 그 둘.
    artifact = ctx.oq11_artifact_head
    if artifact is None:
        return "REBINDING_REQUIRED", "아티팩트가 HEAD 에 부재 — U-12 (i)"
    declared_paths = artifact.get("bound_paths")
    if not isinstance(declared_paths, list) or set(declared_paths) != expected_paths:
        return "REBINDING_REQUIRED", "bound_paths 집합 불일치"

    # R-2 — bound_set_digest 재계산(워킹트리) == 보유값 · disposition 어휘.
    held = artifact.get("bound_set_digest")
    if not isinstance(held, str) or not held:
        return "REBINDING_REQUIRED", "bound_set_digest 미기재"
    calc = _compute_bound_set_digest_worktree(U12_BOUND_PATHS, repo_root)
    if calc is None or calc != held:
        return "REBINDING_REQUIRED", "bound_set_digest 불일치"
    disposition = artifact.get("disposition")
    if disposition not in _OQ11_DISPOSITION_VOCAB:
        return "REBINDING_REQUIRED", f"disposition 어휘 밖: {disposition!r}"

    # R-3 — 최신 verdict 스탬프. 우주=HEAD 트리 · 선택자=verdict.md 를 가진
    # 디렉터리 중 사전순(LC_ALL=C) 마지막.
    vd: str | None = None
    for d in _git_ls_tree_dirs(STAMPS_REL, "HEAD", repo_root):
        if _git_cat_file_exists(f"HEAD:{d}/verdict.md", repo_root):
            vd = d
    if vd is None:
        return "APPROVAL_ABSENT", "HEAD 에 verdict.md 를 가진 스탬프 없음"
    vbody_bytes = _git_show_blob(Path(f"{vd}/verdict.md"), "HEAD", repo_root)
    if vbody_bytes is None:
        return "APPROVAL_ABSENT", f"verdict.md 가 HEAD 에 부재: {vd}"
    verdict_doc = _parse_oq11_yaml_fence(vbody_bytes)
    if not isinstance(verdict_doc, dict):
        return "APPROVAL_ABSENT", f"verdict.md 파싱 실패: {vd}"

    # R-4 — 심판 계열·판정 어휘.
    adjudicator = verdict_doc.get("adjudicator")
    verdict_val = verdict_doc.get("verdict")
    if adjudicator != "codex" or verdict_val != "approve":
        return (
            "APPROVAL_NOT_APPROVE",
            f"adjudicator={adjudicator!r} verdict={verdict_val!r}",
        )

    # R-5 — 심사 범위 == 요구 결속 경로 집합.
    reviewed_paths = verdict_doc.get("reviewed_plan_paths")
    if not isinstance(reviewed_paths, list) or sorted(reviewed_paths) != want_sorted:
        return "APPROVAL_SCOPE_MISMATCH", "reviewed_plan_paths 불일치"

    # R-6 — reviewed_at_head 가 HEAD 의 조상인가.
    reviewed_at_head = verdict_doc.get("reviewed_at_head")
    if not isinstance(reviewed_at_head, str) or not reviewed_at_head:
        return "APPROVAL_PROVENANCE_UNVERIFIABLE", "reviewed_at_head 미기재"
    if not _git_cat_file_exists(f"{reviewed_at_head}^{{commit}}", repo_root):
        return (
            "APPROVAL_PROVENANCE_UNVERIFIABLE",
            "커밋 부재 — 얕은 클론·이력 재작성",
        )
    if not _git_is_ancestor(reviewed_at_head, "HEAD", repo_root):
        return (
            "APPROVAL_PROVENANCE_UNVERIFIABLE",
            "reviewed_at_head 가 HEAD 의 조상이 아님",
        )

    # R-7 — 승인 이후 bound_paths 를 건드린 커밋 — 공집합인가.
    touch = _git_log_touching(f"{reviewed_at_head}..HEAD", (bp1, bp2), repo_root)
    if touch is None:
        return "HARNESS_ABORTED", "git log 실패"
    if touch.strip():
        return "APPROVAL_STALE", f"승인 이후 변경: {touch.strip()}"

    return "ENTRY_OK", "R-0~R-7 전부 기대와 일치"


# ---------------------------------------------------------------------------
# U-15-g — d0a_entry_provenance_state (§12.3.4 U-15-g 사후 관측)
# ---------------------------------------------------------------------------

_ENTRY_TRAILER_KEYS: tuple[str, ...] = (
    "Entry-Transcript",
    "Entry-Transcript-Run",
    "Entry-Transcript-SHA256",
)
_RUN_OPEN_RE = re.compile(r"^R-0 head=(\S+)\s*$", re.MULTILINE)
_ENTRY_STATE_LINE_RE = re.compile(r"^d0a_entry_state=(\S+)\s*$", re.MULTILINE)
_SHA256_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _git_rev_list_full_history(
    rel_path: Path, repo_root: Path, ref: str = "HEAD"
) -> list[str] | None:
    """후보 축소 — ``git rev-list --full-history <ref> -- <rel_path>``."""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--full-history", ref, "--", rel_path.as_posix()],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_parents(commit: str, repo_root: Path) -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%P", commit],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.split()


def _git_commit_message(commit: str, repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%B", commit],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _git_shallow_boundary_commits(repo_root: Path) -> set[str]:
    """``.git/shallow`` 경계 커밋 집합 — 얕은 클론에서 부모 정보가 절단된 커밋."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", "shallow"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if result.returncode != 0:
        return set()
    shallow_path = repo_root / result.stdout.strip()
    if not shallow_path.exists():
        return set()
    try:
        return {
            ln.strip() for ln in shallow_path.read_text().splitlines() if ln.strip()
        }
    except OSError:
        return set()


def _find_config_introduction_commits(
    rel_path: Path, repo_root: Path
) -> list[str] | None:
    """U-15-g-1 — D = {x ⊑ HEAD : path∈tree(x) ∧ ∀p∈parents(x): path∉tree(p)}.

    후보 축소는 ``git rev-list --full-history`` 로 하고, 판정은 후보 위
    구조 술어(부모 tree 의 blob 존재 여부)로 한다.  얕은 클론 경계 등
    부모 정보가 신뢰 불가하면 ``None`` (호출자가 PROVENANCE_UNVERIFIABLE
    로 접는다).
    """
    candidates = _git_rev_list_full_history(rel_path, repo_root)
    if candidates is None:
        return None
    shallow_boundary = _git_shallow_boundary_commits(repo_root)
    found: list[str] = []
    for c in candidates:
        if not _git_cat_file_exists(f"{c}:{rel_path.as_posix()}", repo_root):
            continue
        if c in shallow_boundary:
            return None  # 부모 정보 절단 — 신뢰 불가
        parents = _git_parents(c, repo_root)
        if parents is None:
            return None
        if all(
            not _git_cat_file_exists(f"{p}:{rel_path.as_posix()}", repo_root)
            for p in parents
        ):
            found.append(c)
    return found


def _parse_entry_trailers(message: str) -> dict[str, str] | None:
    """U-15-f-5 — 트레일러 3종 각각 정확히 1회 + 형식 검증.  위반 -> ``None``."""
    values: dict[str, str] = {}
    for key in _ENTRY_TRAILER_KEYS:
        pattern = re.compile(rf"^{re.escape(key)}: (.*)$", re.MULTILINE)
        matches = pattern.findall(message)
        if len(matches) != 1:
            return None
        values[key] = matches[0].strip()
    run_str = values["Entry-Transcript-Run"]
    if not run_str.isdigit() or int(run_str) < 1:
        return None
    sha_str = values["Entry-Transcript-SHA256"]
    if not _SHA256_HEX_RE.match(sha_str):
        return None
    if not values["Entry-Transcript"].strip():
        return None
    return values


def _locate_transcript_run(text: str, k: int) -> tuple[str, str] | None:
    """RUNS(U-15-e 4c-2) — k(1-기반) 번째 run 의 (R-0 head, 상태) 를 반환.

    run 범위 = 그 ``R-0 head=`` 라인부터 다음 ``R-0 head=`` 직전.  그 범위
    안의 ``d0a_entry_state=`` 라인이 정확히 1개가 아니면 형식 미충족.
    """
    opens = list(_RUN_OPEN_RE.finditer(text))
    if k < 1 or k > len(opens):
        return None
    start = opens[k - 1]
    end = opens[k].start() if k < len(opens) else len(text)
    r0_head = start.group(1)
    span = text[start.end() : end]
    status_matches = _ENTRY_STATE_LINE_RE.findall(span)
    if len(status_matches) != 1:
        return None
    return r0_head, status_matches[0]


def derive_d0a_entry_provenance_state(ctx: CheckContext) -> tuple[str, str]:
    """§12.3.4 U-15-g — d0a_entry_provenance_state (8값) 사후 관측.

    전순서(핀): PROVENANCE_UNVERIFIABLE > MULTIPLE_INTRODUCTIONS >
    ENTRY_TRAILER_MALFORMED > PARENT_MISMATCH > TRANSCRIPT_NOT_ENTRY_OK >
    TRANSCRIPT_MISSING > ENTRY_PROVENANCE_CLEAR (각 경로는 상호 배타적).
    """
    try:
        return _derive_provenance_state_inner(ctx)
    except Exception as exc:  # noqa: BLE001 — 판정 미산출 경로 폐쇄
        return "PROVENANCE_UNVERIFIABLE", f"미예기 예외: {exc}"


def _derive_provenance_state_inner(ctx: CheckContext) -> tuple[str, str]:
    repo_root = ctx.repo_root

    # U-15-g-1 — D 구조 정의.
    d_list = _find_config_introduction_commits(CONFIG_REL, repo_root)
    if d_list is None:
        return "PROVENANCE_UNVERIFIABLE", "도입 커밋 구조 파생 불가(부모 신뢰 불가)"
    if len(d_list) == 0:
        return "NOT_STARTED", f"{CONFIG_REL} 도입 커밋 없음(비차단·정상)"
    if len(d_list) > 1:
        return (
            "MULTIPLE_INTRODUCTIONS",
            f"도입 커밋 |D|={len(d_list)}: {sorted(d_list)}",
        )

    d = d_list[0]
    message = _git_commit_message(d, repo_root)
    if message is None:
        return "PROVENANCE_UNVERIFIABLE", f"커밋 메시지 조회 실패: {d}"

    # U-15-f-5 — 트레일러 3종.
    trailers = _parse_entry_trailers(message)
    if trailers is None:
        return "ENTRY_TRAILER_MALFORMED", "트레일러 3종 형식 위반(누락/중복/형식오류)"

    t_path = trailers["Entry-Transcript"]
    t_run = int(trailers["Entry-Transcript-Run"])
    t_sha = trailers["Entry-Transcript-SHA256"].lower()

    # 지목 transcript — HEAD blob 소비.  경로 부재 -> TRANSCRIPT_MISSING
    # (SHA 계산 불가이므로 ENTRY_TRAILER_MALFORMED 가 아니다).
    blob = _git_show_blob(Path(t_path), "HEAD", repo_root)
    if blob is None:
        return "TRANSCRIPT_MISSING", f"transcript 경로가 HEAD 에 부재: {t_path}"

    actual_sha = hashlib.sha256(blob).hexdigest()
    if actual_sha != t_sha:
        return (
            "ENTRY_TRAILER_MALFORMED",
            f"SHA256 불일치: trailer={t_sha} actual={actual_sha}",
        )

    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        return "TRANSCRIPT_MISSING", "transcript 디코딩 실패"

    run_info = _locate_transcript_run(text, t_run)
    if run_info is None:
        return "TRANSCRIPT_MISSING", f"run {t_run} 부재 또는 형식 미충족"
    run_r0_head, run_status = run_info

    parents = _git_parents(d, repo_root)
    parent = parents[0] if parents and len(parents) == 1 else None
    if parent is None or run_r0_head != parent:
        return (
            "PARENT_MISMATCH",
            f"run R-0 head={run_r0_head!r} != parent(d)={parent!r}",
        )
    if run_status != "ENTRY_OK":
        return "TRANSCRIPT_NOT_ENTRY_OK", f"run 상태={run_status}"

    return "ENTRY_PROVENANCE_CLEAR", f"d={d} run={t_run} 전부 정합"


def check_u15(ctx: CheckContext) -> list[Finding]:
    """U-15 — d0a_entry_state(9값) · d0a_entry_provenance_state(8값) 승계.

    rc 결합: ``d0a_entry_state`` != ``ENTRY_OK`` 는 전부 위반.
    ``d0a_entry_provenance_state`` 는 ``{ENTRY_PROVENANCE_CLEAR,
    NOT_STARTED}`` 만 green, 나머지 여섯은 전부 위반.
    """
    findings: list[Finding] = []

    entry_state, entry_detail = derive_d0a_entry_state(ctx)
    ctx.state_lines.append(f"d0a_entry_state={entry_state}")
    if entry_state != "ENTRY_OK":
        findings.append(
            Finding("U-15", f"d0a_entry_state={entry_state}: {entry_detail}")
        )

    prov_state, prov_detail = derive_d0a_entry_provenance_state(ctx)
    ctx.state_lines.append(f"d0a_entry_provenance_state={prov_state}")
    if prov_state not in ("ENTRY_PROVENANCE_CLEAR", "NOT_STARTED"):
        findings.append(
            Finding("U-15", f"d0a_entry_provenance_state={prov_state}: {prov_detail}")
        )

    return findings


# ---------------------------------------------------------------------------
# U-16 — closable_no_provenance_state (12값 · §13.6.5).  판정 입력은 격리
# git 스냅샷(clone + replace/grafts canary) 안에서만 소비한다.
# ---------------------------------------------------------------------------

_U16_STATE_ORDER: tuple[str, ...] = (
    "CONSUMER_ABSENT",
    "PROVENANCE_UNVERIFIABLE",
    "APPROVAL_MALFORMED",
    "APPROVAL_MISSING",
    "APPROVAL_SAME_COMMIT",
    "APPROVAL_AFTER",
    "APPROVAL_CONTENT_DRIFT",
    "APPROVAL_HEAD_INVALID",
    "APPROVAL_ROW_MUTATED",
    "APPROVAL_UNBOUND",
    "APPROVAL_ORDER_INVALID",
    "NO_ROWS_CLEAR",
)
_U16_RANK: dict[str, int] = {name: idx for idx, name in enumerate(_U16_STATE_ORDER)}

_U16_LEDGER_HEADER: tuple[str, ...] = (
    "row_id",
    "transition",
    "row_content_digest",
    "approved_at_head",
    "reviewer_ref",
    "rationale_ref",
)
_U16_LEDGER_HEADING_RE = re.compile(r"^## 승인 행\s*$", re.MULTILINE)
_U16_RATIONALE_RE = re.compile(r"^(?P<ref>.+?)\s+§(?P<num>\d+(?:\.\d+)*)$")


class _U16Unverifiable(Exception):
    """U-16 구조 파생 실패 — 전역 PROVENANCE_UNVERIFIABLE 로 접는 내부 신호."""


@dataclass(frozen=True)
class U16ApprovalRow:
    """``CLOSABLE-NO-APPROVAL-LEDGER.md`` "## 승인 행" 표의 정규화된 한 행."""

    row_id: str
    transition: str
    row_content_digest: str
    approved_at_head: str
    reviewer_ref: str
    rationale_ref: str

    def structural_key(self) -> tuple[str, str, str]:
        return (self.row_id, self.transition, self.row_content_digest)


# ---------------------------------------------------------------------------
# U-16 — 격리 스냅샷 기층
# ---------------------------------------------------------------------------


def _create_u16_snapshot(repo_root: Path) -> tuple[Path | None, Path | None]:
    """``git clone --no-local --no-hardlinks`` + replace/grafts canary.

    Returns:
        (snapshot_root, cleanup_root) — 실패 시 ``(None, None)`` (fail-closed).
        호출자는 ``cleanup_root`` 를 판정 후 ``shutil.rmtree`` 로 삭제한다.
    """
    cleanup_root = Path(tempfile.mkdtemp(prefix="tos-u16-snap-"))
    dest = cleanup_root / "snapshot"
    env = dict(os.environ)
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        result = subprocess.run(
            ["git", "clone", "--no-local", "--no-hardlinks", str(repo_root), str(dest)],
            capture_output=True,
            timeout=_GIT_TIMEOUT * 4,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        shutil.rmtree(cleanup_root, ignore_errors=True)
        return None, None
    if result.returncode != 0:
        shutil.rmtree(cleanup_root, ignore_errors=True)
        return None, None

    try:
        rep = subprocess.run(
            ["git", "replace", "-l"],
            cwd=dest,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        shutil.rmtree(cleanup_root, ignore_errors=True)
        return None, None
    if rep.returncode != 0 or rep.stdout.strip():
        shutil.rmtree(cleanup_root, ignore_errors=True)
        return None, None

    try:
        gp = subprocess.run(
            ["git", "rev-parse", "--git-path", "info/grafts"],
            cwd=dest,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        shutil.rmtree(cleanup_root, ignore_errors=True)
        return None, None
    if gp.returncode != 0:
        shutil.rmtree(cleanup_root, ignore_errors=True)
        return None, None
    grafts_rel = gp.stdout.strip()
    grafts_path = Path(grafts_rel)
    if not grafts_path.is_absolute():
        grafts_path = dest / grafts_path
    if grafts_path.exists():
        shutil.rmtree(cleanup_root, ignore_errors=True)
        return None, None

    return dest, cleanup_root


def _git_cat_file_commit_parents_raw(commit: str, repo_root: Path) -> list[str] | None:
    """``git --no-replace-objects cat-file commit <x>`` 의 parent 줄 직접 파싱 (㉠)."""
    try:
        result = subprocess.run(
            ["git", "--no-replace-objects", "cat-file", "commit", commit],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    parents: list[str] = []
    for line in result.stdout.splitlines():
        if line.startswith("parent "):
            parents.append(line[len("parent ") :].strip())
        elif not line.strip():
            break
    return parents


def _u16_safe_parents(commit: str, repo_root: Path) -> list[str] | None:
    """부모 재파생(㉠) — raw cat-file 과 ``%P`` 뷰 불일치 시 ``None``.

    ㉢ 얕은 경계(``.git/shallow`` 목록) 커밋은 부모 *객체*가 조회 불가하므로
    (metadata 상 parent 줄이 살아 있어도) 무조건 ``None`` — 그렇지 않으면
    얕은 클론에서 부모의 blob 조회가 조용히 "ABSENT" 로 성공해버려
    PROVENANCE_UNVERIFIABLE 를 우회한다.  (호출자는 전부 전역
    ``_U16Unverifiable`` 로 접는다 — 이 저장소 규모에서 로컬/전역 경계
    분기는 T-82 배터리가 요구하지 않아 단순화했다.)
    """
    if commit in _git_shallow_boundary_commits(repo_root):
        return None
    raw = _git_cat_file_commit_parents_raw(commit, repo_root)
    if raw is None:
        return None
    via_format = _git_parents(commit, repo_root)
    if via_format is None:
        return None
    if sorted(raw) != sorted(via_format):
        return None
    return raw


# ---------------------------------------------------------------------------
# U-16 — 원장·레지스터 blob 파싱
# ---------------------------------------------------------------------------


def _load_u16_ledger_rows_at(
    commit: str, repo_root: Path
) -> tuple[list[U16ApprovalRow] | None, str, str | None]:
    """``## 승인 행`` 표를 ``commit`` blob 에서 파싱.

    Returns:
        (rows, error_class, detail) — ``error_class`` 는 ``""``(성공) ·
        ``"ABSENT"``(blob/절 부재) · ``"MALFORMED"``(스키마 위반) 중 하나.
    """
    blob = _git_show_blob(U16_LEDGER_REL, commit, repo_root)
    if blob is None:
        return None, "ABSENT", "원장 blob 부재"
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, "ABSENT", f"원장 디코딩 실패: {exc}"
    table = _extract_md_table_after_heading(text, _U16_LEDGER_HEADING_RE)
    if table is None:
        return None, "ABSENT", "원장 표 파싱 불가(## 승인 행 절 없음)"
    header, data_rows = table
    if tuple(header) != _U16_LEDGER_HEADER:
        return None, "MALFORMED", f"헤더 불일치: {header} != {list(_U16_LEDGER_HEADER)}"
    rows: list[U16ApprovalRow] = []
    for idx, cells in enumerate(data_rows):
        if len(cells) != len(_U16_LEDGER_HEADER):
            return None, "MALFORMED", f"행 {idx}: 필드 수 불일치"
        row_id, transition, digest, approved_at_head, reviewer_ref, rationale_ref = (
            c.strip() for c in cells
        )
        if not all(
            (row_id, transition, digest, approved_at_head, reviewer_ref, rationale_ref)
        ):
            return None, "MALFORMED", f"행 {idx}: 필드 공란"
        rows.append(
            U16ApprovalRow(
                row_id,
                transition,
                digest,
                approved_at_head,
                reviewer_ref,
                rationale_ref,
            )
        )
    return rows, "", None


_U16LedgerCache = dict[str, tuple[list[U16ApprovalRow] | None, str, str | None]]


def _ledger_rows_cached(
    commit: str, repo_root: Path, cache_: _U16LedgerCache
) -> tuple[list[U16ApprovalRow] | None, str, str | None]:
    if commit not in cache_:
        cache_[commit] = _load_u16_ledger_rows_at(commit, repo_root)
    return cache_[commit]


def _load_uncheckable_rows_at(
    commit: str, repo_root: Path
) -> dict[str, dict[str, str]] | None:
    """{id: row} — ``UNCHECKABLE_REL`` 을 ``commit`` blob 에서 파싱.  실패 -> ``None``."""
    blob = _git_show_blob(UNCHECKABLE_REL, commit, repo_root)
    if blob is None:
        return None
    try:
        text = blob.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None
    try:
        reader = csv.DictReader(text.splitlines())
        fieldnames = tuple(reader.fieldnames or ())
        if fieldnames != UNCHECKABLE_FIELDS:
            return None
        rows = list(reader)
    except csv.Error:
        return None
    return {row["id"]: row for row in rows}


def _row_canonical_digest(row: dict[str, str]) -> str:
    """U-16-c v2.20 g2 — 열이름 정렬(``LC_ALL=C``) + ``<열>=<값>\\0`` 연접 sha256."""
    parts: list[bytes] = []
    for key in sorted(row.keys()):
        parts.append(f"{key}={row[key]}".encode() + b"\x00")
    return hashlib.sha256(b"".join(parts)).hexdigest()


def _u16_heading_present(text: str, num: str) -> bool:
    num_re = re.escape(num)
    heading_re = re.compile(rf"^#{{1,6}}\s*{num_re}[.\s]", re.MULTILINE)
    literal_re = re.compile(rf"^#{{1,6}}.*§{num_re}(?!\d)", re.MULTILINE)
    return bool(heading_re.search(text) or literal_re.search(text))


def _resolve_rationale_ref(value: str, repo_root: Path, src_root: Path) -> bool:
    """g4 — ``<repo 상대경로 또는 tos-spec DOC-ID> §<번호>`` 해석 (워킹트리 소비 · K-4 방식)."""
    m = _U16_RATIONALE_RE.match(value.strip())
    if not m:
        return False
    ref, num = m.group("ref"), m.group("num")
    candidate = repo_root / ref
    if candidate.is_file():
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            return False
        return _u16_heading_present(text, num)
    if not src_root.is_dir():
        return False
    matches = sorted(
        p
        for p in src_root.rglob(f"{ref}*.md")
        if "patches" not in p.relative_to(src_root).parts
    )
    if len(matches) != 1:
        return False
    try:
        text = matches[0].read_text(encoding="utf-8")
    except OSError:
        return False
    return _u16_heading_present(text, num)


# ---------------------------------------------------------------------------
# U-16 — 구조 파생 (EDGES · c_APP · C_R)
# ---------------------------------------------------------------------------


def _u16_compute_edges(
    row_id: str,
    candidates: list[str],
    repo_root: Path,
    states_cache: dict[str, dict[str, dict[str, str]] | None],
) -> list[tuple[str | None, str, str]]:
    """EDGES(r) — 후보(레지스터 touching 커밋) 위 부모별 상태 비교.

    Returns:
        [(parent_or_None, commit, edge_type)] — ``parent`` 가 ``None`` 이면
        무부모(∅, state=ABSENT).
    """

    def rows_at(c: str) -> dict[str, dict[str, str]] | None:
        if c not in states_cache:
            states_cache[c] = _load_uncheckable_rows_at(c, repo_root)
        return states_cache[c]

    def state_of(c: str) -> str:
        rows = rows_at(c)
        if rows is None:
            return "ABSENT"
        row = rows.get(row_id)
        return row["closable"] if row else "ABSENT"

    edges: list[tuple[str | None, str, str]] = []
    for c in candidates:
        if state_of(c) != "NO":
            continue
        parents = _u16_safe_parents(c, repo_root)
        if parents is None:
            raise _U16Unverifiable(f"부모 파생 실패(EDGES): {c}")
        if not parents:
            edges.append((None, c, "ABSENT->NO"))
            continue
        for p in parents:
            state_p = state_of(p)
            if state_p == "NO":
                continue
            edges.append((p, c, f"{state_p}->NO"))
    return edges


def _u16_compute_c_app(
    structural_key: tuple[str, str, str],
    head_commit: str,
    repo_root: Path,
    ledger_cache: _U16LedgerCache,
) -> list[str]:
    """c_APP(a) = {x ⊑ HEAD : a∈rows(x:원장) ∧ ∀p: a∉rows(p:원장)}."""
    candidates = _git_rev_list_full_history(U16_LEDGER_REL, repo_root, ref=head_commit)
    if candidates is None:
        raise _U16Unverifiable("원장 이력 조회 실패(c_APP)")

    def has_key(c: str) -> bool:
        rows, _err, _detail = _ledger_rows_cached(c, repo_root, ledger_cache)
        if rows is None:
            return False
        return any(r.structural_key() == structural_key for r in rows)

    found: list[str] = []
    for c in candidates:
        if not has_key(c):
            continue
        parents = _u16_safe_parents(c, repo_root)
        if parents is None:
            raise _U16Unverifiable(f"부모 파생 실패(c_APP): {c}")
        if all(not has_key(p) for p in parents):
            found.append(c)
    return found


def _get_ledger_row_by_key(
    commit: str,
    key: tuple[str, str, str],
    repo_root: Path,
    ledger_cache: _U16LedgerCache,
) -> U16ApprovalRow | None:
    rows, _err, _detail = _ledger_rows_cached(commit, repo_root, ledger_cache)
    if rows is None:
        return None
    for r in rows:
        if r.structural_key() == key:
            return r
    return None


def _u16_compute_c_r(
    reviewer_ref: str, target_blob: bytes, edge_commit: str, repo_root: Path
) -> list[str]:
    """C_R(c) — ``reviewer_ref`` blob(``target_blob``)의 도입 커밋, ``c`` 조상 한정."""
    candidates = _git_rev_list_full_history(
        Path(reviewer_ref), repo_root, ref=edge_commit
    )
    if candidates is None:
        raise _U16Unverifiable("reviewer_ref 이력 조회 실패(C_R)")
    blob_cache: dict[str, bytes | None] = {}

    def blob_at(c: str) -> bytes | None:
        if c not in blob_cache:
            blob_cache[c] = _git_show_blob(Path(reviewer_ref), c, repo_root)
        return blob_cache[c]

    found: list[str] = []
    for c in candidates:
        if blob_at(c) != target_blob:
            continue
        parents = _u16_safe_parents(c, repo_root)
        if parents is None:
            raise _U16Unverifiable(f"부모 파생 실패(C_R): {c}")
        if all(blob_at(p) != target_blob for p in parents):
            found.append(c)
    return found


# ---------------------------------------------------------------------------
# U-16 — 후보 행 평가 (g1~g6 · h · 전순서)
# ---------------------------------------------------------------------------


def _u16_evaluate_candidate(
    a: U16ApprovalRow,
    edge_commit: str,
    head_row: dict[str, str],
    repo_root: Path,
    src_root: Path,
    ledger_cache: _U16LedgerCache,
    head_commit: str,
) -> str:
    """단일 후보 행이 단일 간선을 «덮는가» 평가.  ``"OK"`` 또는 위반 상태명."""
    c_app_list = _u16_compute_c_app(
        a.structural_key(), head_commit, repo_root, ledger_cache
    )
    if len(c_app_list) == 0:
        return "PROVENANCE_UNVERIFIABLE"
    if len(c_app_list) > 1:
        return "APPROVAL_MALFORMED"
    c_app = c_app_list[0]

    # g4 (rank 3) — SAME_COMMIT/AFTER(5/6)보다 앞서 평가해 전순서를 지킨다.
    if not _resolve_rationale_ref(a.rationale_ref, repo_root, src_root):
        return "APPROVAL_MALFORMED"

    if c_app == edge_commit:
        return "APPROVAL_SAME_COMMIT"
    if not _git_is_ancestor(c_app, edge_commit, repo_root):
        return "APPROVAL_AFTER"

    # g2
    if _row_canonical_digest(head_row) != a.row_content_digest:
        return "APPROVAL_CONTENT_DRIFT"

    # g3
    if not _git_is_ancestor(a.approved_at_head, edge_commit, repo_root):
        return "APPROVAL_HEAD_INVALID"
    reviewer_blob = _git_show_blob(Path(a.reviewer_ref), a.approved_at_head, repo_root)
    if reviewer_blob is None:
        return "APPROVAL_HEAD_INVALID"

    # g5
    row_at_capp = _get_ledger_row_by_key(
        c_app, a.structural_key(), repo_root, ledger_cache
    )
    if row_at_capp is None or row_at_capp != a:
        return "APPROVAL_ROW_MUTATED"

    # h
    try:
        reviewer_text = reviewer_blob.decode("utf-8")
    except UnicodeDecodeError:
        return "APPROVAL_UNBOUND"
    if a.row_content_digest not in reviewer_text:
        return "APPROVAL_UNBOUND"

    # g6
    c_r = _u16_compute_c_r(a.reviewer_ref, reviewer_blob, edge_commit, repo_root)
    if not c_r:
        return "PROVENANCE_UNVERIFIABLE"
    if not any(x != c_app and _git_is_ancestor(x, c_app, repo_root) for x in c_r):
        return "APPROVAL_ORDER_INVALID"

    return "OK"


def _u16_edge_status(
    row_id: str,
    edge_type: str,
    edge_commit: str,
    head_rows: list[U16ApprovalRow],
    head_row: dict[str, str],
    repo_root: Path,
    src_root: Path,
    ledger_cache: _U16LedgerCache,
    head_commit: str,
) -> str | None:
    """단일 간선의 위반 상태 — ``None`` 이면 정확히 한 행이 덮어 문제 없음."""
    candidates = [
        a for a in head_rows if a.row_id == row_id and a.transition == edge_type
    ]
    if not candidates:
        return "APPROVAL_MISSING"
    statuses: list[str] = []
    ok_count = 0
    for a in candidates:
        status = _u16_evaluate_candidate(
            a, edge_commit, head_row, repo_root, src_root, ledger_cache, head_commit
        )
        if status == "OK":
            ok_count += 1
        else:
            statuses.append(status)
    if ok_count >= 2:
        return "APPROVAL_MALFORMED"
    if ok_count == 1:
        return None
    return min(statuses, key=lambda s: _U16_RANK[s])


def _u16_orphan_present(
    head_rows: list[U16ApprovalRow], all_edges: list[tuple[str, str | None, str, str]]
) -> bool:
    """고아 행 — 같은 (row_id, transition) 간선이 하나도 없는 승인 행 존재?"""
    edge_pairs = {(row_id, edge_type) for row_id, _p, _c, edge_type in all_edges}
    return any((a.row_id, a.transition) not in edge_pairs for a in head_rows)


# ---------------------------------------------------------------------------
# U-16 — 최상위 오케스트레이션
# ---------------------------------------------------------------------------


def _derive_u16_state_inner(ctx: CheckContext, snap_root: Path) -> tuple[str, str]:
    repo_root = snap_root
    src_root = ctx.repo_root / TOS_SPEC_SRC_REL

    head_commit = _resolve_commit("HEAD", repo_root)

    register_head = _load_uncheckable_rows_at(head_commit, repo_root)
    if register_head is None:
        return "CONSUMER_ABSENT", "레지스터 부재/파싱 실패"

    ledger_cache: _U16LedgerCache = {}
    head_ledger_rows, err_class, detail = _ledger_rows_cached(
        head_commit, repo_root, ledger_cache
    )
    if head_ledger_rows is None:
        if err_class == "ABSENT":
            return "CONSUMER_ABSENT", detail or "원장 부재"
        return "APPROVAL_MALFORMED", detail or "원장 스키마 위반"

    no_rows = sorted(
        rid for rid, row in register_head.items() if row.get("closable") == "NO"
    )
    if not no_rows:
        return "NO_ROWS_CLEAR", "NO_ROWS(HEAD) 공집합"

    register_candidates = _git_rev_list_full_history(
        UNCHECKABLE_REL, repo_root, ref=head_commit
    )
    if register_candidates is None:
        return "PROVENANCE_UNVERIFIABLE", "레지스터 이력 조회 실패"

    states_cache: dict[str, dict[str, dict[str, str]] | None] = {
        head_commit: register_head
    }
    all_edges: list[tuple[str, str | None, str, str]] = []
    for row_id in no_rows:
        edges = _u16_compute_edges(row_id, register_candidates, repo_root, states_cache)
        if not edges:
            return (
                "PROVENANCE_UNVERIFIABLE",
                f"{row_id}: EDGES 공집합(공집합 통과 금지)",
            )
        for p, c, et in edges:
            all_edges.append((row_id, p, c, et))

    worst: list[str] = []
    if _u16_orphan_present(head_ledger_rows, all_edges):
        worst.append("APPROVAL_MALFORMED")

    for row_id, _p, c, et in all_edges:
        status = _u16_edge_status(
            row_id,
            et,
            c,
            head_ledger_rows,
            register_head[row_id],
            repo_root,
            src_root,
            ledger_cache,
            head_commit,
        )
        if status is not None:
            worst.append(status)

    if not worst:
        return "NO_ROWS_CLEAR", "전 NO 행·간선 전순서 위반 0"
    final = min(worst, key=lambda s: _U16_RANK[s])
    return final, f"위반 상태 집합={sorted(set(worst))}"


def derive_u16_state(ctx: CheckContext) -> tuple[str, str]:
    """§13.6.5 U-16 — closable_no_provenance_state (12값).

    판정 미산출 경로 폐쇄 — 미예기 예외·구조 파생 실패는 전부
    ``PROVENANCE_UNVERIFIABLE`` 로 접는다(fail-closed).
    """
    snap_root, cleanup_root = _create_u16_snapshot(ctx.repo_root)
    if snap_root is None:
        return "PROVENANCE_UNVERIFIABLE", "격리 스냅샷 생성/canary 실패"
    try:
        return _derive_u16_state_inner(ctx, snap_root)
    except _U16Unverifiable as exc:
        return "PROVENANCE_UNVERIFIABLE", str(exc)
    except Exception as exc:  # noqa: BLE001 — 판정 미산출 경로 폐쇄
        return "PROVENANCE_UNVERIFIABLE", f"미예기 예외: {exc}"
    finally:
        if cleanup_root is not None:
            shutil.rmtree(cleanup_root, ignore_errors=True)


def check_u16(ctx: CheckContext) -> list[Finding]:
    """U-16 — closable_no_provenance_state.  ``NO_ROWS_CLEAR`` 외 전부 위반(T-82)."""
    state, detail = derive_u16_state(ctx)
    ctx.state_lines.append(f"closable_no_provenance_state={state}")
    if state == "NO_ROWS_CLEAR":
        return []
    return [Finding("U-16", f"{state}: {detail}")]


# ---------------------------------------------------------------------------
# U-1a · U-4 · U-5 — UNCHECKABLE 레지스터 규칙 (§13.6.4 · §13.3)
# ---------------------------------------------------------------------------

_OWNER_TRACK_RANGE_FULL_RE = re.compile(r"^Phase (\d+)-(\d+)$")
_OWNER_TRACK_UNIT_RE = re.compile(r"^(?:GOV-001|Phase (\d+))$")


def _validate_owner_track_value(
    value: str, phase_min: int, phase_max: int, max_width: int
) -> tuple[bool, bool]:
    """owner_track 문법 판정(§13.6.4).  Returns (valid, is_range).

    ``range`` 는 단독으로만 허용된다 — '+' 결합체의 각 유닛은 range 문법을
    받아들이지 않으므로(``_OWNER_TRACK_UNIT_RE``), 결합 시도는 자연히 거부된다.
    """
    range_m = _OWNER_TRACK_RANGE_FULL_RE.match(value)
    if range_m:
        low, high = int(range_m.group(1)), int(range_m.group(2))
        valid = phase_min <= low < high <= phase_max and (high - low) <= max_width
        return valid, True
    for unit in value.split("+"):
        unit_m = _OWNER_TRACK_UNIT_RE.match(unit)
        if not unit_m:
            return False, False
        phase_str = unit_m.group(1)
        if phase_str is not None and not (phase_min <= int(phase_str) <= phase_max):
            return False, False
    return True, False


def _owner_track_report(ctx: CheckContext) -> dict[str, list[Finding]]:
    """U-1a/U-4/U-5 공용 계산 — ``ctx`` 에 캐시해 관측(§13.2.1)을 1회만 인쇄한다."""
    if ctx._owner_track_cache is not None:
        return ctx._owner_track_cache

    result: dict[str, list[Finding]] = {"U-1a": [], "U-4": []}
    if ctx.uncheckable_rows is None or ctx.config is None:
        ctx._owner_track_cache = result
        return result

    raw_width = ctx.config.get("owner_track_range_max_width")
    raw_phase_min = ctx.config.get("phase_min")
    raw_phase_max = ctx.config.get("phase_max")
    config_valid = (
        isinstance(raw_width, int)
        and not isinstance(raw_width, bool)
        and isinstance(raw_phase_min, int)
        and not isinstance(raw_phase_min, bool)
        and isinstance(raw_phase_max, int)
        and not isinstance(raw_phase_max, bool)
    )
    width: int = raw_width if isinstance(raw_width, int) else 0
    phase_min: int = raw_phase_min if isinstance(raw_phase_min, int) else 0
    phase_max: int = raw_phase_max if isinstance(raw_phase_max, int) else 0

    imprecise_count = 0
    unassigned_count = 0
    for row in ctx.uncheckable_rows:
        rid = row["id"]
        closable = row["closable"]
        owner_track = row["owner_track"]
        blocked_by = row["blocked_by"]

        # U-4
        if not blocked_by.strip():
            result["U-4"].append(Finding("U-4", f"{rid}: blocked_by 공란"))

        if closable == "YES":
            stripped = owner_track.strip()
            if not stripped or stripped == "미배정":
                result["U-1a"].append(
                    Finding("U-1a", f"{rid}: closable=YES 인데 owner_track 미배정")
                )
                unassigned_count += 1
            elif config_valid:
                valid, is_range = _validate_owner_track_value(
                    stripped, phase_min, phase_max, width
                )
                if not valid:
                    result["U-1a"].append(
                        Finding("U-1a", f"{rid}: owner_track 문법 밖: {owner_track!r}")
                    )
                elif is_range:
                    imprecise_count += 1
        elif closable == "NO":
            if owner_track.strip():
                result["U-1a"].append(
                    Finding(
                        "U-1a",
                        f"{rid}: closable=NO 인데 owner_track 비공란: {owner_track!r}",
                    )
                )
        else:
            result["U-1a"].append(
                Finding("U-1a", f"{rid}: closable 어휘 밖: {closable!r}")
            )

    ctx.observations.append(f"imprecise_owner_track={imprecise_count}")
    ctx.observations.append(f"unassigned_owner_rows={unassigned_count}")
    ctx._owner_track_cache = result
    return result


def check_u1a(ctx: CheckContext) -> list[Finding]:
    """U-1a — closable=YES 미배정('공란'/'미배정')·closable=NO 비공란·문법 밖."""
    return list(_owner_track_report(ctx)["U-1a"])


def check_u4(ctx: CheckContext) -> list[Finding]:
    """U-4 — blocked_by 공란 행 (§13.3)."""
    return list(_owner_track_report(ctx)["U-4"])


def check_u5(ctx: CheckContext) -> list[Finding]:
    """U-5 — unassigned_owner_rows 1급 지표 인쇄 (완료 관측 · rc 비결합 · 위반 없음)."""
    _owner_track_report(ctx)
    return []


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
    "U-12": check_u12,
    "U-13": check_u13,
    "U-15": check_u15,
    "U-16": check_u16,
    "U-1a": check_u1a,
    "U-4": check_u4,
    "U-5": check_u5,
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

    print("미구현(C2c 이후) — 강제 지점 미등록:")
    for check_id in DEFERRED_CONTRACTS:
        print(f"  - {check_id}")
    print()

    print("--check 밖 강제 지점:")
    print("  - U-17 → tools/u17-verify.sh (가드 체인·live)")
    print()

    print("상태 라인 (rc 비결합 — 상태별 rc 결합은 해당 check_id 의 Finding 이 담당):")
    for line in ctx.state_lines:
        print(f"  {line}")
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
