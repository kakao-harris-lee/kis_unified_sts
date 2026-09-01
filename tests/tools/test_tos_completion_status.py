"""Tests for tools/tos_completion_status.py — Phase-0 D0-A 검사기 증분 C1.

합성 미니 코퍼스는 tmp_path 아래 실제 코퍼스와 동일한 상대 경로 구조로
써지고, ``build_context()`` 가 그 트리를 직접 읽는다 — 모듈 상수를
monkeypatch 하지 않는다(``build_context`` 가 이미 ``repo_root`` 를
인자로 받으므로 필요 없다).
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "tos_completion_status.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("tos_completion_status", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tcs = _load_module()


# ---------------------------------------------------------------------------
# 합성 미니 코퍼스 — 기준선(GREEN)
# ---------------------------------------------------------------------------

DOC_ID = "MINI-DOC-001"
BASIS_5 = f"{DOC_ID} §5"
BASIS_6 = f"{DOC_ID} §6"

DOC_MD = """# Mini Doc

## 5. Evidence Strength Levels

body text.

## 6. Another Section

more body text.
"""

OQ11_TABLE = """## ③ 승인된 매핑표 (정본)

| `EV-Ln` | `surface_kind` | 근거 |
|---|---|---|
| `EV-L0` | `REVIEWER` | note |
| `EV-L1` | `PACKAGE`, `TEST` | note |
| `EV-L2` | `FAULT` | note |
| `EV-L3` | `RUNTIME` | note |
| `EV-L4` | `RUNTIME` | note |
| `EV-L5` | `RUNTIME` | note |
| `EV-L6` | `RUNTIME` | note |
"""


# ---------------------------------------------------------------------------
# U-12/U-13 — git 소비 코퍼스 fixture (bound 문서 2종 · OQ-11 아티팩트 · 원장)
# ---------------------------------------------------------------------------

U12_BOUND_DOC_A = "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md"
U12_BOUND_DOC_B = "docs/plans/2026-08-11-tos-completion-development-plan.md"
U12_DEFAULT_BOUND_DOCS: dict[str, bytes] = {
    U12_BOUND_DOC_A: b"mini design doc placeholder\n",
    U12_BOUND_DOC_B: b"mini dev-plan doc placeholder\n",
}


def _bound_set_digest(bound_docs: dict[str, bytes]) -> str:
    """U-12 digest 레시피의 순수-파이썬 재현(테스트 기입값 계산용 — git 미개입)."""
    lines: list[bytes] = []
    for p in sorted(bound_docs):
        file_hash = hashlib.sha256(bound_docs[p]).hexdigest()
        lines.append(f"{file_hash}  {p}\n".encode())
    return hashlib.sha256(b"".join(lines)).hexdigest()


U12_CORRECT_DIGEST = _bound_set_digest(U12_DEFAULT_BOUND_DOCS)
U12_BROKEN_DIGEST = "0" * 64


def _oq11_artifact_text(
    *,
    disposition: str = "RESOLVED_MAPPING_APPROVED",
    bound_paths: list[str] | None = None,
    digest: str = U12_CORRECT_DIGEST,
    deferred_scope: dict[str, object] | None = None,
) -> str:
    paths = (
        bound_paths if bound_paths is not None else [U12_BOUND_DOC_A, U12_BOUND_DOC_B]
    )
    data: dict[str, object] = {
        "disposition": disposition,
        "bound_set_digest": digest,
        "bound_paths": paths,
    }
    if deferred_scope is not None:
        data["deferred_scope"] = deferred_scope
    body = yaml.safe_dump(data, sort_keys=False)
    return f"```yaml\n{body}```\n\n" + OQ11_TABLE


def _ledger_text(rows: list[tuple[str, str, str, str]]) -> str:
    lines = [
        "# OQ-11 Raise Ledger (synthetic)",
        "",
        "## 에피소드",
        "",
        "| episode_id | raised_at | trigger_at_head | closed_by |",
        "|---|---|---|---|",
    ]
    for episode_id, raised_at, trigger_at_head, closed_by in rows:
        lines.append(
            f"| {episode_id} | {raised_at} | {trigger_at_head} | {closed_by} |"
        )
    return "\n".join(lines) + "\n"


def _git(
    repo: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, env=env, check=True
    )


def _git_init(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "tos-test@example.com")
    _git(repo, "config", "user.name", "TOS Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _git_commit_all(repo: Path, message: str, when: str) -> str:
    """워킹트리 전체를 스테이징해 커밋한다.  ``when``: UTC ISO-8601(``Z`` 허용)."""
    git_date = when[:-1] + " +0000" if when.endswith("Z") else when
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = git_date
    env["GIT_COMMITTER_DATE"] = git_date
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", message, env=env)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _git_current_branch(repo: Path) -> str:
    return _git(repo, "branch", "--show-current").stdout.strip()


def _git_checkout_new_branch(repo: Path, name: str) -> None:
    _git(repo, "checkout", "-q", "-b", name)


def _git_checkout(repo: Path, ref: str) -> None:
    _git(repo, "checkout", "-q", ref)


def _git_merge(repo: Path, other_ref: str, message: str, when: str) -> str:
    git_date = when[:-1] + " +0000" if when.endswith("Z") else when
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = git_date
    env["GIT_COMMITTER_DATE"] = git_date
    _git(repo, "merge", "--no-ff", "-q", "-m", message, other_ref, env=env)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _register_row(**overrides: str) -> dict[str, str]:
    row = {
        "evidence_id": "MINI-EV-001",
        "domain": "Mini",
        "title": "Mini One",
        "primary_adr": "ADR-MINI-001",
        "criticality": "Critical",
        "minimum_evidence_level": "EV-L1",
        "status": "NOT_IMPLEMENTED",
        "implementation_owner": "ai-impl",
        "evidence_owner": "operator",
        "independent_reviewer": "ai-review",
        "verification_profile_version": "1.0",
        "broker_capability_profile_version": "N/A",
        "latest_run_id": "",
        "latest_result_date": "",
        "evidence_location": "",
        "notes": "",
    }
    row.update(overrides)
    return row


REGISTER_ROW_1 = _register_row(
    evidence_id="MINI-EV-001", minimum_evidence_level="EV-L1"
)
REGISTER_ROW_2 = _register_row(
    evidence_id="MINI-EV-002", minimum_evidence_level="EV-L3"
)
REGISTER_ROW_3_PROFILE = _register_row(
    evidence_id="MINI-EV-003", minimum_evidence_level="Profile-dependent"
)

REQUIRED_KINDS_ROW_1 = {
    "evidence_id": "MINI-EV-001",
    "required_kinds": "PACKAGE|TEST",
    "basis": BASIS_5,
}
REQUIRED_KINDS_ROW_2 = {
    "evidence_id": "MINI-EV-002",
    "required_kinds": "RUNTIME",
    "basis": BASIS_5,
}

MAP_ROW_1 = {
    "evidence_id": "MINI-EV-001",
    "surface_kind": "PACKAGE",
    "surface_ref": "PLANNED_UNASSIGNED",
    "existence": "ABSENT",
    "binding_basis": BASIS_5,
}
MAP_ROW_2 = {
    "evidence_id": "MINI-EV-001",
    "surface_kind": "TEST",
    "surface_ref": "PLANNED_UNASSIGNED",
    "existence": "ABSENT",
    "binding_basis": BASIS_5,
}
MAP_ROW_3 = {
    "evidence_id": "MINI-EV-002",
    "surface_kind": "RUNTIME",
    "surface_ref": "PLANNED_UNASSIGNED",
    "existence": "ABSENT",
    "binding_basis": BASIS_5,
}

UNCHECKABLE_ROW_1 = {
    "id": "MINI-UNCHK-001",
    "axis": "mini axis",
    "reason": "mini reason",
    "blocked_by": "mini blocker",
    "owner_track": "",
    "exposed_in": "TOS-COMPLETION-STATUS",
    "normative_ref": "",
    "closable": "NO",
    "blocks_gate": "",
}
UNCHECKABLE_ROW_2_YES = {
    "id": "MINI-UNCHK-002",
    "axis": "mini axis 2",
    "reason": "mini reason 2",
    "blocked_by": "mini blocker 2",
    "owner_track": "Phase 2-5",
    "exposed_in": "TOS-COMPLETION-STATUS",
    "normative_ref": "",
    "closable": "YES",
    "blocks_gate": "",
}

CONFIG_BASE: dict[str, object] = {
    "owner_track_range_max_width": 3,
    "phase_min": 0,
    "phase_max": 7,
    "anchor_evidence_level_distribution": "EV-L1=1,EV-L3=1,Profile-dependent=1",
    "anchor_closable_no_ids": "MINI-UNCHK-001",
    "oq11_response_deadline": "DEADLINE_UNSET",
}


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_corpus(
    root: Path,
    *,
    register_rows: list[dict[str, str]] | None = None,
    required_kinds_rows: list[dict[str, str]] | None = None,
    map_rows: list[dict[str, str]] | None = None,
    uncheckable_rows: list[dict[str, str]] | None = None,
    config: dict[str, object] | None = None,
    oq11_text: str | None = None,
    doc_text: str | None = None,
    skip_required_kinds: bool = False,
    required_kinds_header_override: tuple[str, ...] | None = None,
    bound_docs: dict[str, bytes] | None = None,
    ledger_rows: list[tuple[str, str, str, str]] | None = None,
    ledger_text_override: str | None = None,
    git_commit: bool = True,
    commit_when: str = "2026-01-01T00:00:00Z",
) -> None:
    """합성 미니 코퍼스를 ``root`` 아래 실제 코퍼스와 같은 상대 경로로 쓴다.

    ``git_commit=True``(기본)면 전체를 한 커밋으로 묶는다 — U-12 의 권위
    판정 입력(OQ-11 아티팩트·bound 문서 2종·원장)이 HEAD blob 소비이므로,
    기본 fixture 값들은 서로 결속(digest 일치)해 ``oq11_raise_state
    =NOT_REQUIRED`` 가 되도록 맞춰져 있다.  U-12 전용 다중-커밋 이력
    시나리오는 ``git_commit=False`` 로 받아 호출자가 직접 커밋을 쌓는다.
    """
    if register_rows is None:
        register_rows = [REGISTER_ROW_1, REGISTER_ROW_2, REGISTER_ROW_3_PROFILE]
    if required_kinds_rows is None:
        required_kinds_rows = [REQUIRED_KINDS_ROW_1, REQUIRED_KINDS_ROW_2]
    if map_rows is None:
        map_rows = [MAP_ROW_1, MAP_ROW_2, MAP_ROW_3]
    if uncheckable_rows is None:
        uncheckable_rows = [UNCHECKABLE_ROW_1]
    if config is None:
        config = dict(CONFIG_BASE)
    if oq11_text is None:
        oq11_text = _oq11_artifact_text()
    if doc_text is None:
        doc_text = DOC_MD
    if bound_docs is None:
        bound_docs = U12_DEFAULT_BOUND_DOCS
    if ledger_text_override is not None:
        ledger_text = ledger_text_override
    else:
        ledger_text = _ledger_text(ledger_rows or [])

    # 두 register 파일에 걸쳐 나눠 쓴다 — 어느 쪽에 있든 검사기는 합쳐서 본다.
    part1_rows = register_rows[:1]
    dev_rows = register_rows[1:]
    _write_csv(root / tcs.PART1_REL, tcs.REGISTER_FIELDS, part1_rows)
    _write_csv(root / tcs.DEV_REL, tcs.REGISTER_FIELDS, dev_rows)

    if not skip_required_kinds:
        header = required_kinds_header_override or tcs.REQUIRED_KINDS_FIELDS
        _write_csv(root / tcs.REQUIRED_KINDS_REL, header, required_kinds_rows)

    _write_csv(root / tcs.SURFACE_MAP_REL, tcs.SURFACE_MAP_FIELDS, map_rows)
    _write_csv(root / tcs.UNCHECKABLE_REL, tcs.UNCHECKABLE_FIELDS, uncheckable_rows)

    config_path = root / tcs.CONFIG_REL
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    oq11_path = root / tcs.OQ11_REL
    oq11_path.parent.mkdir(parents=True, exist_ok=True)
    oq11_path.write_text(oq11_text, encoding="utf-8")

    ledger_path = root / tcs.OQ11_LEDGER_REL
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(ledger_text, encoding="utf-8")

    for rel, content in bound_docs.items():
        bound_path = root / rel
        bound_path.parent.mkdir(parents=True, exist_ok=True)
        bound_path.write_bytes(content)

    doc_path = root / "tos-spec" / "src" / "part-1-foundation" / f"{DOC_ID}-Spec.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(doc_text, encoding="utf-8")

    if git_commit:
        _git_init(root)
        _git_commit_all(root, "synthetic corpus", commit_when)


def _run(root: Path) -> list:
    ctx = tcs.build_context(root)
    return tcs.run_checks(ctx)


def _run_ctx(root: Path):
    ctx = tcs.build_context(root)
    findings = tcs.run_checks(ctx)
    return ctx, findings


def _ids(findings: list) -> set[str]:
    return {f.check_id for f in findings}


# ---------------------------------------------------------------------------
# 1. 양성(실코퍼스) — subprocess, rc 0
# ---------------------------------------------------------------------------


def test_real_corpus_check_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(_MODULE_PATH), "--check"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: GREEN (violations=0)" in result.stdout


def test_missing_check_flag_is_usage_error() -> None:
    result = subprocess.run(
        [sys.executable, str(_MODULE_PATH)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "--check" in result.stderr


# ---------------------------------------------------------------------------
# 2. 합성 양성
# ---------------------------------------------------------------------------


def test_synthetic_corpus_is_green(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    findings = _run(tmp_path)
    assert findings == [], [str(f) for f in findings]


# ---------------------------------------------------------------------------
# 3. K-1 — MAP 중복 행
# ---------------------------------------------------------------------------


def test_k1_duplicate_map_row_is_red(tmp_path: Path) -> None:
    write_corpus(tmp_path, map_rows=[MAP_ROW_1, dict(MAP_ROW_1), MAP_ROW_2, MAP_ROW_3])
    assert "K-1" in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 4. K-2 — floor 미포함 선언
# ---------------------------------------------------------------------------


def test_k2_floor_not_covered_is_red(tmp_path: Path) -> None:
    # MINI-EV-002 는 EV-L3 -> floor {RUNTIME} 인데 PACKAGE 만 선언한다.
    bad_required = [
        REQUIRED_KINDS_ROW_1,
        {"evidence_id": "MINI-EV-002", "required_kinds": "PACKAGE", "basis": BASIS_5},
    ]
    write_corpus(tmp_path, required_kinds_rows=bad_required)
    assert "K-2" in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 5. K-3 — 마커인데 손기입 PRESENT
# ---------------------------------------------------------------------------


def test_k3_hand_typed_presence_on_marker_is_red(tmp_path: Path) -> None:
    bad_map = [dict(MAP_ROW_1, existence="PRESENT"), MAP_ROW_2, MAP_ROW_3]
    write_corpus(tmp_path, map_rows=bad_map)
    assert "K-3" in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 6. K-4 — 미해석 basis
# ---------------------------------------------------------------------------


def test_k4_unresolvable_basis_is_red(tmp_path: Path) -> None:
    bad_required = [
        dict(REQUIRED_KINDS_ROW_1, basis="NOPE-DOC-999 §5"),
        REQUIRED_KINDS_ROW_2,
    ]
    write_corpus(tmp_path, required_kinds_rows=bad_required)
    assert "K-4" in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 7. K-6 — 누락·잉여
# ---------------------------------------------------------------------------


def test_k6_missing_from_required_kinds_is_red(tmp_path: Path) -> None:
    write_corpus(tmp_path, required_kinds_rows=[REQUIRED_KINDS_ROW_1])
    assert "K-6" in _ids(_run(tmp_path))


def test_k6_extra_in_required_kinds_is_red(tmp_path: Path) -> None:
    extra = {
        "evidence_id": "MINI-EV-999",
        "required_kinds": "RUNTIME",
        "basis": BASIS_5,
    }
    write_corpus(
        tmp_path,
        required_kinds_rows=[REQUIRED_KINDS_ROW_1, REQUIRED_KINDS_ROW_2, extra],
    )
    assert "K-6" in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 8. K-9 — 파일 부재·헤더 불일치
# ---------------------------------------------------------------------------


def test_k9_required_kinds_file_absent_is_red(tmp_path: Path) -> None:
    write_corpus(tmp_path, skip_required_kinds=True)
    assert "K-9" in _ids(_run(tmp_path))


def test_k9_required_kinds_header_mismatch_is_red(tmp_path: Path) -> None:
    write_corpus(
        tmp_path, required_kinds_header_override=("evidence_id", "required_kinds")
    )
    assert "K-9" in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 9. K-11 — 동일 ref 재사용 + 동일 § (서로 다른 § 면 GREEN)
# ---------------------------------------------------------------------------


def _k11_rows(same_section: bool) -> tuple[list, list, list]:
    register_rows = [
        REGISTER_ROW_1,
        REGISTER_ROW_2,
        REGISTER_ROW_3_PROFILE,
        _register_row(evidence_id="MINI-EV-004", minimum_evidence_level="EV-L1"),
    ]
    required_kinds_rows = [
        REQUIRED_KINDS_ROW_1,
        REQUIRED_KINDS_ROW_2,
        {
            "evidence_id": "MINI-EV-004",
            "required_kinds": "PACKAGE|TEST",
            "basis": BASIS_5,
        },
    ]
    shared_ref = "shared/pkg/module.py"
    second_basis = BASIS_5 if same_section else BASIS_6
    map_rows = [
        dict(MAP_ROW_1, surface_ref=shared_ref),
        MAP_ROW_2,
        MAP_ROW_3,
        {
            "evidence_id": "MINI-EV-004",
            "surface_kind": "PACKAGE",
            "surface_ref": shared_ref,
            "existence": "ABSENT",
            "binding_basis": second_basis,
        },
        {
            "evidence_id": "MINI-EV-004",
            "surface_kind": "TEST",
            "surface_ref": "PLANNED_UNASSIGNED",
            "existence": "ABSENT",
            "binding_basis": BASIS_5,
        },
    ]
    return register_rows, required_kinds_rows, map_rows


def test_k11_reused_ref_same_section_is_red(tmp_path: Path) -> None:
    register_rows, required_kinds_rows, map_rows = _k11_rows(same_section=True)
    write_corpus(
        tmp_path,
        register_rows=register_rows,
        required_kinds_rows=required_kinds_rows,
        map_rows=map_rows,
    )
    assert "K-11" in _ids(_run(tmp_path))


def test_k11_reused_ref_different_section_is_not_flagged(tmp_path: Path) -> None:
    register_rows, required_kinds_rows, map_rows = _k11_rows(same_section=False)
    write_corpus(
        tmp_path,
        register_rows=register_rows,
        required_kinds_rows=required_kinds_rows,
        map_rows=map_rows,
    )
    assert "K-11" not in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 10. K-12 — './' 접두 PACKAGE ref
# ---------------------------------------------------------------------------


def test_k12_dot_slash_prefix_package_ref_is_red(tmp_path: Path) -> None:
    bad_map = [dict(MAP_ROW_1, surface_ref="./x"), MAP_ROW_2, MAP_ROW_3]
    write_corpus(tmp_path, map_rows=bad_map)
    assert "K-12" in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 11. K-13 — Profile-dependent 가 REQUIRED-KINDS 에 등장
# ---------------------------------------------------------------------------


def test_k13_profile_dependent_in_required_kinds_is_red(tmp_path: Path) -> None:
    extra = {
        "evidence_id": "MINI-EV-003",
        "required_kinds": "RUNTIME",
        "basis": BASIS_5,
    }
    write_corpus(
        tmp_path,
        required_kinds_rows=[REQUIRED_KINDS_ROW_1, REQUIRED_KINDS_ROW_2, extra],
    )
    assert "K-13" in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 12. K-14 — 매핑 도메인 밖(EV-L9) + 도메인 안 정상 도출(양성)
# ---------------------------------------------------------------------------


def test_k14_out_of_domain_level_is_red(tmp_path: Path) -> None:
    bad_register = [
        dict(REGISTER_ROW_1, minimum_evidence_level="EV-L9"),
        REGISTER_ROW_2,
        REGISTER_ROW_3_PROFILE,
    ]
    write_corpus(tmp_path, register_rows=bad_register)
    assert "K-14" in _ids(_run(tmp_path))


def test_k14_in_domain_level_is_not_flagged(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    assert "K-14" not in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 13. T-48 축 — 문법 밖 값('garbage')
# ---------------------------------------------------------------------------


def test_t48_malformed_level_syntax_is_red(tmp_path: Path) -> None:
    bad_register = [
        dict(REGISTER_ROW_1, minimum_evidence_level="garbage"),
        REGISTER_ROW_2,
        REGISTER_ROW_3_PROFILE,
    ]
    write_corpus(tmp_path, register_rows=bad_register)
    findings = _run(tmp_path)
    assert findings, "문법 밖 값이 조용히 통과했다"


# ---------------------------------------------------------------------------
# 14. U-14 — T-76 앵커 불일치 · U-9a 앵커 불일치
# ---------------------------------------------------------------------------


def test_u14_t76_anchor_mismatch_is_red(tmp_path: Path) -> None:
    bad_config = dict(
        CONFIG_BASE,
        anchor_evidence_level_distribution="EV-L1=99,EV-L3=1,Profile-dependent=1",
    )
    write_corpus(tmp_path, config=bad_config)
    assert "U-14" in _ids(_run(tmp_path))


def test_u14_u9a_anchor_mismatch_is_red(tmp_path: Path) -> None:
    bad_config = dict(CONFIG_BASE, anchor_closable_no_ids="WRONG-ID")
    write_corpus(tmp_path, config=bad_config)
    assert "U-14" in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 15. config 부재
# ---------------------------------------------------------------------------


def test_config_absent_is_red(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    (tmp_path / tcs.CONFIG_REL).unlink()
    assert "U-14" in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 16. U-12 — oq11_raise_state 7값 상태 기계 (증분 C2a · T-78)
# ---------------------------------------------------------------------------


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _setup_required_repo(
    tmp_path: Path,
    *,
    deadline: str = "30d",
    commit1_when: str | None = None,
) -> tuple[str, datetime]:
    """트리거가 항상 성립(digest 불일치)하는 root 커밋 1개짜리 저장소.

    빈 원장(열린 에피소드 0)으로 시작한다.  반환값 = (root_commit, root_dt).
    """
    now = datetime.now(UTC)
    commit1_dt = (
        datetime.fromisoformat(commit1_when.replace("Z", "+00:00"))
        if commit1_when
        else now - timedelta(days=240)
    )
    write_corpus(
        tmp_path,
        config=dict(CONFIG_BASE, oq11_response_deadline=deadline),
        oq11_text=_oq11_artifact_text(digest=U12_BROKEN_DIGEST),
        ledger_rows=[],
        git_commit=False,
    )
    _git_init(tmp_path)
    commit1 = _git_commit_all(
        tmp_path, "root: broken digest + empty ledger", _iso(commit1_dt)
    )
    return commit1, commit1_dt


def _add_open_episode(
    tmp_path: Path,
    *,
    trigger_at_head: str,
    raised_at: str,
    commit_when: str,
    episode_id: str = "EP-1",
) -> str:
    ledger_path = tmp_path / tcs.OQ11_LEDGER_REL
    ledger_path.write_text(
        _ledger_text([(episode_id, raised_at, trigger_at_head, "")]), encoding="utf-8"
    )
    return _git_commit_all(tmp_path, "raise episode", commit_when)


def test_u12_synthetic_intact_repo_is_not_required(tmp_path: Path) -> None:
    """U-12 양성 — 합성 repo 무결(정합 digest·빈 원장) -> NOT_REQUIRED · GREEN."""
    write_corpus(tmp_path)
    ctx, findings = _run_ctx(tmp_path)
    assert "U-12" not in _ids(findings)
    assert "oq11_raise_state=NOT_REQUIRED" in ctx.state_lines


def test_u12_t78_1_raise_missing_when_no_open_episode(tmp_path: Path) -> None:
    _setup_required_repo(tmp_path, deadline="30d")
    ctx, findings = _run_ctx(tmp_path)
    assert "oq11_raise_state=RAISE_MISSING" in ctx.state_lines
    assert "U-12" in _ids(findings)


def test_u12_t78_2_pending_within_still_red(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    commit1, _ = _setup_required_repo(
        tmp_path, deadline="30d", commit1_when=_iso(now - timedelta(days=2))
    )
    row_when = now - timedelta(days=1)
    _add_open_episode(
        tmp_path,
        trigger_at_head=commit1,
        raised_at=_iso(row_when),
        commit_when=_iso(row_when),
    )
    ctx, findings = _run_ctx(tmp_path)
    assert "oq11_raise_state=PENDING_WITHIN" in ctx.state_lines
    assert "U-12" in _ids(findings)  # 미만료도 red


def test_u12_t78_3_no_response_after_deadline(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=200)
    commit1, _ = _setup_required_repo(tmp_path, deadline="30d", commit1_when=_iso(old))
    _add_open_episode(
        tmp_path, trigger_at_head=commit1, raised_at=_iso(old), commit_when=_iso(old)
    )
    ctx, findings = _run_ctx(tmp_path)
    assert "oq11_raise_state=NO_RESPONSE" in ctx.state_lines
    assert "U-12" in _ids(findings)


def test_u12_t78_4_future_raised_at_does_not_reset_clock(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=200)
    future = now + timedelta(days=365)
    commit1, _ = _setup_required_repo(tmp_path, deadline="30d", commit1_when=_iso(old))
    _add_open_episode(
        tmp_path, trigger_at_head=commit1, raised_at=_iso(future), commit_when=_iso(old)
    )
    ctx, findings = _run_ctx(tmp_path)
    assert "oq11_raise_state=NO_RESPONSE" in ctx.state_lines
    assert "U-12" in _ids(findings)


def test_u12_t78_5_deadline_unset(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    commit1, _ = _setup_required_repo(
        tmp_path, deadline="DEADLINE_UNSET", commit1_when=_iso(now - timedelta(days=2))
    )
    row_when = now - timedelta(days=1)
    _add_open_episode(
        tmp_path,
        trigger_at_head=commit1,
        raised_at=_iso(row_when),
        commit_when=_iso(row_when),
    )
    ctx, findings = _run_ctx(tmp_path)
    assert "oq11_raise_state=DEADLINE_UNSET" in ctx.state_lines
    assert "U-12" in _ids(findings)


def test_u12_t78_6_delayed_row_introduction_preserves_elapsed(tmp_path: Path) -> None:
    """지연 도입 — trigger_at_derived 가 경과를 보존해 NO_RESPONSE 유지.

    행 도입 시각(최근)을 기준으로 삼았다면 PENDING_WITHIN 이 나왔을 것이다.
    """
    now = datetime.now(UTC)
    old = now - timedelta(days=200)
    recent = now - timedelta(days=1)
    commit1, _ = _setup_required_repo(tmp_path, deadline="30d", commit1_when=_iso(old))
    _add_open_episode(
        tmp_path,
        trigger_at_head=commit1,
        raised_at=_iso(recent),
        commit_when=_iso(recent),
    )
    ctx, findings = _run_ctx(tmp_path)
    assert "oq11_raise_state=NO_RESPONSE" in ctx.state_lines


def test_u12_t78_7_trigger_at_head_mismatch_is_malformed(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    commit1, _ = _setup_required_repo(
        tmp_path, deadline="30d", commit1_when=_iso(now - timedelta(days=2))
    )
    row_when = now - timedelta(days=1)
    _add_open_episode(
        tmp_path,
        trigger_at_head="0" * 40,
        raised_at=_iso(row_when),
        commit_when=_iso(row_when),
    )
    ctx, findings = _run_ctx(tmp_path)
    assert "oq11_raise_state=RAISE_MALFORMED" in ctx.state_lines
    assert commit1  # trigger 재파생 자체는 성공(commit1) — 그 값과의 불일치가 위반 원인
    assert "U-12" in _ids(findings)


def test_u12_t78_8_trigger_commit_selection_is_deterministic_across_merge(
    tmp_path: Path,
) -> None:
    """2-parent 머지(한 부모 True·한 부모 False)에서 trigger_commit 유일화가 결정적."""
    write_corpus(
        tmp_path,
        config=dict(CONFIG_BASE, oq11_response_deadline="30d"),
        oq11_text=_oq11_artifact_text(
            digest=U12_CORRECT_DIGEST
        ),  # A: 정합 -> pred False
        ledger_rows=[],
        git_commit=False,
    )
    _git_init(tmp_path)
    commit_a = _git_commit_all(tmp_path, "A: correct digest", "2026-01-01T00:00:00Z")
    main_branch = _git_current_branch(tmp_path)

    _git_checkout_new_branch(tmp_path, "side")
    (tmp_path / tcs.OQ11_REL).write_text(
        _oq11_artifact_text(digest=U12_BROKEN_DIGEST), encoding="utf-8"
    )
    commit_b = _git_commit_all(tmp_path, "B: break digest", "2026-01-02T00:00:00Z")

    _git_checkout(tmp_path, main_branch)
    _git_commit_all(tmp_path, "C: no-op on main", "2026-01-03T00:00:00Z")

    commit_m = _git_merge(tmp_path, "side", "merge side", "2026-01-04T00:00:00Z")

    head_commit = tcs._resolve_commit("HEAD", tmp_path)
    assert head_commit == commit_m
    graph = tcs._git_ancestor_graph(head_commit, tmp_path)
    assert commit_m in graph
    assert commit_a in graph

    result1 = tcs._find_trigger_commit(head_commit, graph, tmp_path)
    result2 = tcs._find_trigger_commit(head_commit, graph, tmp_path)
    assert result1 == result2
    assert result1 is not None
    assert result1[0] == commit_b


def test_real_corpus_reports_oq11_not_required_and_reproduces_digest() -> None:
    """실코퍼스 HEAD — 상태 라인 NOT_REQUIRED 인쇄 + digest 재계산이 기지값을 재현."""
    result = subprocess.run(
        [sys.executable, str(_MODULE_PATH), "--check"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "oq11_raise_state=NOT_REQUIRED" in result.stdout

    digest = tcs._compute_bound_set_digest(tcs.U12_BOUND_PATHS, "HEAD", _REPO_ROOT)
    assert digest == "daaba47b1c4b2b31717c098c8d761d9fd2b0cd1eb7e0d55b48d46a4e059f1c3b"


# ---------------------------------------------------------------------------
# 17. U-13 — deferred_scope 스키마
# ---------------------------------------------------------------------------


def test_u13_resolved_with_deferred_scope_present_is_red(tmp_path: Path) -> None:
    write_corpus(
        tmp_path,
        oq11_text=_oq11_artifact_text(
            disposition="RESOLVED_MAPPING_APPROVED",
            deferred_scope={"kind": "GLOBAL"},
        ),
    )
    assert "U-13" in _ids(_run(tmp_path))


def test_u13_deferred_with_scope_missing_scope_is_red(tmp_path: Path) -> None:
    write_corpus(
        tmp_path,
        oq11_text=_oq11_artifact_text(disposition="DEFERRED_WITH_SCOPE"),
    )
    assert "U-13" in _ids(_run(tmp_path))


def test_u13_global_with_rows_is_red(tmp_path: Path) -> None:
    write_corpus(
        tmp_path,
        oq11_text=_oq11_artifact_text(
            disposition="DEFERRED_WITH_SCOPE",
            deferred_scope={"kind": "GLOBAL", "rows": ["MINI-EV-001"]},
        ),
    )
    assert "U-13" in _ids(_run(tmp_path))


def test_u13_row_subset_valid_is_green_and_prints_exclusions(tmp_path: Path) -> None:
    write_corpus(
        tmp_path,
        oq11_text=_oq11_artifact_text(
            disposition="DEFERRED_WITH_SCOPE",
            deferred_scope={
                "kind": "ROW_SUBSET",
                "rows": ["MINI-EV-001"],
                "remainder_mapping_approved": True,
            },
        ),
    )
    ctx, findings = _run_ctx(tmp_path)
    assert "U-13" not in _ids(findings)
    assert any(o.startswith("U-13 fwd_a_excluded_rows=") for o in ctx.observations)
    assert any(o.startswith("U-13 remainder_rows=") for o in ctx.observations)


def test_u13_row_subset_orphan_id_is_red(tmp_path: Path) -> None:
    write_corpus(
        tmp_path,
        oq11_text=_oq11_artifact_text(
            disposition="DEFERRED_WITH_SCOPE",
            deferred_scope={
                "kind": "ROW_SUBSET",
                "rows": ["MINI-EV-999"],
                "remainder_mapping_approved": True,
            },
        ),
    )
    assert "U-13" in _ids(_run(tmp_path))


def test_u13_row_subset_remainder_not_true_is_red(tmp_path: Path) -> None:
    write_corpus(
        tmp_path,
        oq11_text=_oq11_artifact_text(
            disposition="DEFERRED_WITH_SCOPE",
            deferred_scope={
                "kind": "ROW_SUBSET",
                "rows": ["MINI-EV-001"],
                "remainder_mapping_approved": False,
            },
        ),
    )
    assert "U-13" in _ids(_run(tmp_path))


def test_u13_register_id_outside_grammar_is_red(tmp_path: Path) -> None:
    bad_register = [
        REGISTER_ROW_1,
        REGISTER_ROW_2,
        _register_row(
            evidence_id="bad id!", minimum_evidence_level="Profile-dependent"
        ),
    ]
    write_corpus(
        tmp_path,
        register_rows=bad_register,
        oq11_text=_oq11_artifact_text(
            disposition="DEFERRED_WITH_SCOPE",
            deferred_scope={
                "kind": "ROW_SUBSET",
                "rows": ["MINI-EV-001"],
                "remainder_mapping_approved": True,
            },
        ),
    )
    assert "U-13" in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 18. U-1a · U-4 · U-5 — UNCHECKABLE 레지스터 규칙
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "Phase 5-2",
        "Phase 8",
        "Phase 0-7",
        "GOV-001 / Phase 1",
        "Phase 2 to 5",
        "언젠가",
    ],
)
def test_t62_owner_track_grammar_violations_are_red(tmp_path: Path, value: str) -> None:
    bad_row = dict(UNCHECKABLE_ROW_2_YES, id="MINI-UNCHK-BAD", owner_track=value)
    write_corpus(tmp_path, uncheckable_rows=[UNCHECKABLE_ROW_1, bad_row])
    assert "U-1a" in _ids(_run(tmp_path))


def test_t62_owner_track_range_within_width_is_valid_and_counted(
    tmp_path: Path,
) -> None:
    good_row = dict(
        UNCHECKABLE_ROW_2_YES, id="MINI-UNCHK-GOOD", owner_track="Phase 2-5"
    )
    write_corpus(tmp_path, uncheckable_rows=[UNCHECKABLE_ROW_1, good_row])
    ctx, findings = _run_ctx(tmp_path)
    assert "U-1a" not in _ids(findings)
    assert "imprecise_owner_track=1" in ctx.observations


def test_u1a_closable_yes_blank_owner_track_is_red(tmp_path: Path) -> None:
    bad_row = dict(UNCHECKABLE_ROW_2_YES, id="MINI-UNCHK-YB", owner_track="")
    write_corpus(tmp_path, uncheckable_rows=[UNCHECKABLE_ROW_1, bad_row])
    assert "U-1a" in _ids(_run(tmp_path))


def test_u1a_closable_yes_mibaejeong_literal_owner_track_is_red(tmp_path: Path) -> None:
    bad_row = dict(UNCHECKABLE_ROW_2_YES, id="MINI-UNCHK-YM", owner_track="미배정")
    write_corpus(tmp_path, uncheckable_rows=[UNCHECKABLE_ROW_1, bad_row])
    assert "U-1a" in _ids(_run(tmp_path))


def test_u1a_closable_no_nonblank_owner_track_is_red(tmp_path: Path) -> None:
    bad_row = dict(UNCHECKABLE_ROW_1, id="MINI-UNCHK-NB", owner_track="Phase 1")
    write_corpus(tmp_path, uncheckable_rows=[bad_row])
    assert "U-1a" in _ids(_run(tmp_path))


def test_u4_blocked_by_blank_is_red(tmp_path: Path) -> None:
    bad_row = dict(UNCHECKABLE_ROW_2_YES, id="MINI-UNCHK-BB", blocked_by="")
    write_corpus(tmp_path, uncheckable_rows=[UNCHECKABLE_ROW_1, bad_row])
    assert "U-4" in _ids(_run(tmp_path))


def test_u5_unassigned_owner_rows_metric_is_printed(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    ctx, findings = _run_ctx(tmp_path)
    assert any(o.startswith("unassigned_owner_rows=") for o in ctx.observations)


# ---------------------------------------------------------------------------
# 19. T-39 — CONTRACT_CHECKS 레지스트리 커버리지
# ---------------------------------------------------------------------------


def test_t39_all_registered_checks_are_invoked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_corpus(tmp_path)
    ctx = tcs.build_context(tmp_path)
    original = dict(tcs.CONTRACT_CHECKS)
    called: set[str] = set()

    def make_spy(check_id: str, fn):
        def spy(c):
            called.add(check_id)
            return fn(c)

        return spy

    monkeypatch.setattr(
        tcs, "CONTRACT_CHECKS", {cid: make_spy(cid, fn) for cid, fn in original.items()}
    )
    tcs.run_checks(ctx)
    assert called == set(original.keys())


def test_t39_deferred_contracts_disjoint_from_contract_checks() -> None:
    assert set(tcs.DEFERRED_CONTRACTS).isdisjoint(set(tcs.CONTRACT_CHECKS.keys()))
    for expected in ("U-12", "U-13", "U-1a", "U-4", "U-5"):
        assert expected in tcs.CONTRACT_CHECKS
    for expected in ("U-15", "U-16", "U-17", "T-71"):
        assert expected in tcs.DEFERRED_CONTRACTS
