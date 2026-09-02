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
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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
# U-9(위생) 이 인용을 해석하는 대상이 U12_BOUND_DOC_A 자체다(§13.5 는 U-9
# 시드 행 UNCHECKABLE_ROW_1 의 기본 reason 인용과 맞춘 mini 헤딩).
U12_DEFAULT_BOUND_DOCS: dict[str, bytes] = {
    U12_BOUND_DOC_A: b"mini design doc placeholder\n\n### 13.5 mini heading\n\nbody\n",
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


# ---------------------------------------------------------------------------
# U-15 — §12.3.4-R d0a_entry_state / U-15-g d0a_entry_provenance_state fixture
# ---------------------------------------------------------------------------

U15_VERDICT_STAMP_DIR = "20260101-010101"


def _u15_verdict_body(
    *,
    adjudicator: str = "codex",
    verdict: str = "approve",
    reviewed_at_head: str,
    reviewed_plan_paths: list[str] | None = None,
) -> str:
    paths = (
        reviewed_plan_paths
        if reviewed_plan_paths is not None
        else [U12_BOUND_DOC_A, U12_BOUND_DOC_B]
    )
    data: dict[str, object] = {
        "adjudicator": adjudicator,
        "verdict": verdict,
        "reviewed_at_head": reviewed_at_head,
        "reviewed_plan_paths": paths,
    }
    body = yaml.safe_dump(data, sort_keys=False)
    return f"```yaml\n{body}```\n"


def _write_verdict_stamp(root: Path, stamp_dir: str, body: str) -> None:
    path = root / tcs.STAMPS_REL / stamp_dir / "verdict.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _transcript_text(r0_head: str, status: str) -> str:
    return f"R-0 head={r0_head}\nreason=synthetic\nd0a_entry_state={status}\n"


def _write_transcript(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commit_config_with_message(root: Path, message: str, when: str) -> str:
    """config 파일이 이미 워킹트리에 쓰여 있다고 가정 — 임의 커밋 메시지로 커밋."""
    git_date = when[:-1] + " +0000" if when.endswith("Z") else when
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = git_date
    env["GIT_COMMITTER_DATE"] = git_date
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message, env=env)
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _commit_config_with_trailers(
    root: Path,
    *,
    config_body: str,
    transcript_rel: str,
    run: int,
    sha256: str,
    when: str,
) -> str:
    config_path = root / tcs.CONFIG_REL
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_body, encoding="utf-8")
    message = (
        "feat(tos): D0A-FIRST synthetic — config/tos_completion.yaml 도입\n\n"
        f"Entry-Transcript: {transcript_rel}\n"
        f"Entry-Transcript-Run: {run}\n"
        f"Entry-Transcript-SHA256: {sha256}\n"
    )
    return _commit_config_with_message(root, message, when)


def _setup_u15_base_no_config(tmp_path: Path) -> str:
    """전체 코퍼스(config 제외)를 쓰고 커밋한다 — U-15-g 기준선 = ``NOT_STARTED``."""
    write_corpus(tmp_path, git_commit=False)
    (tmp_path / tcs.CONFIG_REL).unlink()
    _git_init(tmp_path)
    return _git_commit_all(tmp_path, "base corpus (no config)", "2026-01-01T00:00:00Z")


def _setup_u15_ok_repo(tmp_path: Path) -> tuple[str, str]:
    """R-0~R-7 전부 통과하는 최소 repo.  Returns (base_commit, head_commit)."""
    base = _setup_u15_base_no_config(tmp_path)
    body = _u15_verdict_body(reviewed_at_head=base)
    _write_verdict_stamp(tmp_path, U15_VERDICT_STAMP_DIR, body)
    head = _git_commit_all(tmp_path, "add verdict stamp", "2026-01-02T00:00:00Z")
    return base, head


def _setup_ok_head_with_transcript(
    tmp_path: Path, suffix: str, *, status: str = "ENTRY_OK"
) -> tuple[str, str, str, str]:
    """base -> verdict stamp(head1, 진짜 ENTRY_OK 성립)까지만 구성한다.

    transcript 내용·sha256 을 사전 계산해 반환한다 — 착지(T)는 호출자가
    d 커밋 뒤에 별도로 수행한다(H -> d -> T 흐름 순서 · G6).

    Returns (head1, transcript_rel, transcript_sha256, transcript_text).
    """
    base, head1 = _setup_u15_ok_repo(tmp_path)
    transcript_rel = (
        f"docs/reviews/phase0-completion-contract/synthetic-{suffix}/TRANSCRIPT.md"
    )
    transcript_text = _transcript_text(head1, status)
    transcript_sha = hashlib.sha256(transcript_text.encode("utf-8")).hexdigest()
    return head1, transcript_rel, transcript_sha, transcript_text


_HARNESS_PATH = _REPO_ROOT / "tools" / "tos_entry_harness.sh"
_HARNESS_STATE_RE = re.compile(r"^d0a_entry_state=(\S+)$", re.MULTILINE)


def _harness_entry_state(root: Path) -> tuple[int, str | None]:
    result = subprocess.run(
        ["bash", str(_HARNESS_PATH)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + result.stderr
    m = _HARNESS_STATE_RE.search(combined)
    return result.returncode, (m.group(1) if m else None)


def _assert_harness_parity(root: Path, expected_state: str) -> None:
    rc, state = _harness_entry_state(root)
    assert (
        state == expected_state
    ), f"harness state={state!r} rc={rc} != {expected_state!r}"
    if expected_state == "ENTRY_OK":
        assert rc == 0
    else:
        assert rc != 0


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


# ---------------------------------------------------------------------------
# U-16 — closable_no_provenance_state(12값) fixture (§13.6.5 · C2c)
# ---------------------------------------------------------------------------

U16_RATIONALE_DOC_REL = "docs/u16-mini-rationale.md"
U16_RATIONALE_REF = f"{U16_RATIONALE_DOC_REL} §5"
U16_RATIONALE_REF_ALT = f"{U16_RATIONALE_DOC_REL} §6"
U16_RATIONALE_DOC_TEXT = (
    "# Mini Rationale\n\n## 5. Section Five\n\nbody.\n\n## 6. Section Six\n\nbody.\n"
)


def _write_u16_rationale_doc(root: Path) -> None:
    path = root / U16_RATIONALE_DOC_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(U16_RATIONALE_DOC_TEXT, encoding="utf-8")


def _u16_row(row_id: str, closable: str, **overrides: str) -> dict[str, str]:
    row = {
        "id": row_id,
        "axis": "mini axis",
        "reason": "mini reason",
        "blocked_by": "mini blocker",
        "owner_track": "",
        "exposed_in": "TOS-COMPLETION-STATUS",
        "normative_ref": "",
        "closable": closable,
        "blocks_gate": "",
    }
    row.update(overrides)
    return row


def _u16_row_canonical_digest(row: dict[str, str]) -> str:
    """``tos_completion_status._row_canonical_digest`` 의 순수-파이썬 재현."""
    parts: list[bytes] = []
    for key in sorted(row.keys()):
        parts.append(f"{key}={row[key]}".encode() + b"\x00")
    return hashlib.sha256(b"".join(parts)).hexdigest()


def _write_u16_register(root: Path, rows: list[dict[str, str]]) -> None:
    _write_csv(root / tcs.UNCHECKABLE_REL, tcs.UNCHECKABLE_FIELDS, rows)


def _u16_ledger_text(
    rows: list[tuple[str, str, str, str, str, str]],
) -> str:
    lines = [
        "# Closable-NO Approval Ledger (synthetic)",
        "",
        "## 승인 행",
        "",
        "| row_id | transition | row_content_digest | approved_at_head "
        "| reviewer_ref | rationale_ref |",
        "|---|---|---|---|---|---|",
    ]
    for (
        row_id,
        transition,
        digest,
        approved_at_head,
        reviewer_ref,
        rationale_ref,
    ) in rows:
        lines.append(
            f"| {row_id} | {transition} | {digest} | {approved_at_head} "
            f"| {reviewer_ref} | {rationale_ref} |"
        )
    return "\n".join(lines) + "\n"


def _write_u16_ledger(
    root: Path, rows: list[tuple[str, str, str, str, str, str]]
) -> None:
    path = root / tcs.U16_LEDGER_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_u16_ledger_text(rows), encoding="utf-8")


def _write_u16_reviewer(root: Path, rel: str, digest: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Synthetic U-16 reviewer artifact\n\nrow_content_digest = {digest}\n",
        encoding="utf-8",
    )


def _u16_build_basic_chain(
    tmp_path: Path,
    row_id: str = "MINI-UNCHK-001",
    reviewer_rel: str = "docs/reviews/u16-synthetic/REVIEW.md",
) -> dict[str, Any]:
    """R(reviewer) -> L(ledger 승인 행) -> C(register born-NO) 3-커밋 양성 체인.

    실코퍼스(UNCHK-014)와 동형인 최소 happy-path — g1~g6·h 전부 충족.
    """
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)

    row = _u16_row(row_id, "NO")
    digest = _u16_row_canonical_digest(row)

    _write_u16_reviewer(tmp_path, reviewer_rel, digest)
    reviewer_commit = _git_commit_all(
        tmp_path, "u16 reviewer artifact", "2026-01-01T00:00:00Z"
    )

    _write_u16_ledger(
        tmp_path,
        [
            (
                row_id,
                "ABSENT->NO",
                digest,
                reviewer_commit,
                reviewer_rel,
                U16_RATIONALE_REF,
            )
        ],
    )
    ledger_commit = _git_commit_all(
        tmp_path, "u16 ledger approval row", "2026-01-02T00:00:00Z"
    )

    _write_u16_register(tmp_path, [row])
    edge_commit = _git_commit_all(
        tmp_path, "u16 register born-NO", "2026-01-03T00:00:00Z"
    )

    return {
        "reviewer_commit": reviewer_commit,
        "ledger_commit": ledger_commit,
        "edge_commit": edge_commit,
        "digest": digest,
        "row": row,
        "row_id": row_id,
        "reviewer_rel": reviewer_rel,
    }


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


def _git_merge_resolving(
    repo: Path,
    other_ref: str,
    message: str,
    when: str,
    resolved_paths: dict[str, bytes],
) -> str:
    """머지 시도; 충돌 시 ``resolved_paths``(경로 -> 최종 바이트열)로 수동 해결.

    T-82 ⑱/⑳ⓐ — 형제 브랜치가 같은 md 표에 행을 각각 추가하는 시나리오는
    git 이 충돌 없이 합칠 수도, 충돌로 멈출 수도 있다(내용 동일 여부에
    따라) — 어느 쪽이든 최종 트리는 ``resolved_paths`` 로 고정한다.
    """
    git_date = when[:-1] + " +0000" if when.endswith("Z") else when
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = git_date
    env["GIT_COMMITTER_DATE"] = git_date
    result = subprocess.run(
        ["git", "merge", "--no-ff", "-m", message, other_ref],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        for rel, content in resolved_paths.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", message, env=env)
    return str(_git(repo, "rev-parse", "HEAD").stdout.strip())


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
    # U-9(위생) — closable=NO 이므로 reason 의 §-인용이 실제 계약 문서
    # (U12_BOUND_PATHS[0])에서 해석 가능해야 한다.  §13.5 는 그 문서의 실재
    # 헤딩("### 13.5 U-2의 입력 우주...")이다.
    "reason": "mini reason (§13.5)",
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
    # T-71 — GATE_PREDICATES 는 corpus 무관 고정 11행(CHECKABLE 2/PARTIAL 3/
    # NMC 6) 이므로 이 세 앵커는 실코퍼스·합성 코퍼스 어디서나 이 값이어야
    # green 이다.
    "anchor_classification_checkable": 2,
    "anchor_classification_partial": 3,
    "anchor_classification_nmc": 6,
}

AUTHORITY_ROW_RESTRICTED_LIVE = {
    "axis": "restricted_live",
    "status": "NOT_AUTHORIZED",
    "governing_source": "mini governing source",
    "change_authority": "mini authority",
    "notes": "mini note",
}
AUTHORITY_ROW_PRODUCTION = {
    "axis": "production",
    "status": "NOT_AUTHORIZED",
    "governing_source": "mini governing source",
    "change_authority": "mini authority",
    "notes": "mini note",
}
AUTHORITY_FIELDS = (
    "axis",
    "status",
    "governing_source",
    "change_authority",
    "notes",
)

# A-2(§6.4) — CURRENT-STATUS.md/TOS-COMPLETION-STATUS.md 대조 표면 기본값.
# 기본 AUTHORITY_ROW_* (둘 다 NOT_AUTHORIZED) 와 결속돼 있어 write_corpus 의
# 기본 호출은 A-2 를 clean 으로 남긴다 — 불일치 뮤테이션은 이 텍스트를 직접
# override 한다.
DEFAULT_CURRENT_STATUS_MD = """# Mini Current Status

| Axis | Value | Notes |
|---|---|---|
| Restricted-live | `NOT_AUTHORIZED` | mini note |
| Production authorization | `NOT_AUTHORIZED` | mini note |
"""

DEFAULT_COMPLETION_STATUS_MD = """# Mini Completion Status

| Gate | Kind | Verdict | Reasons (blocks_gate) |
|---|---|---|---|
| G4 | `AUTHORITY` | `NOT_AUTHORIZED` | - |
"""


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
    include_u15_verdict_stamp: bool = True,
    authority_rows: list[dict[str, str]] | None = None,
    current_status_text: str | None = None,
    completion_status_text: str | None = None,
) -> None:
    """합성 미니 코퍼스를 ``root`` 아래 실제 코퍼스와 같은 상대 경로로 쓴다.

    ``git_commit=True``(기본)면 전체를 한 커밋으로 묶는다 — U-12 의 권위
    판정 입력(OQ-11 아티팩트·bound 문서 2종·원장)이 HEAD blob 소비이므로,
    기본 fixture 값들은 서로 결속(digest 일치)해 ``oq11_raise_state
    =NOT_REQUIRED`` 가 되도록 맞춰져 있다.  U-12 전용 다중-커밋 이력
    시나리오는 ``git_commit=False`` 로 받아 호출자가 직접 커밋을 쌓는다.

    ``git_commit=True`` 면 U-15 ``d0a_entry_state`` 도 기본으로 ``ENTRY_OK``
    가 되도록 두 번째 커밋으로 codex-approve verdict 스탬프를 얹는다
    (``include_u15_verdict_stamp=False`` 로 끌 수 있다).  ``config`` 파일은
    두 커밋 모두의 **밖**(워킹트리 전용)에 남겨 U-15-g
    ``d0a_entry_provenance_state`` 기본값을 ``NOT_STARTED``(비차단)로 지킨다
    — U-12/U-13 은 ``config`` 를 git 이 아니라 디스크로 읽으므로 영향받지
    않는다.

    ``git_commit=True`` 면 ``uncheckable_rows`` 에 ``UNCHECKABLE_ROW_1``
    (``closable=NO``)가 포함돼 있는 한 U-16 도 기본으로
    ``NO_ROWS_CLEAR`` 가 되도록 그 행 앞에 reviewer(R)·ledger(L) 승인
    커밋 2개를 얹고, 레지스터 CSV(그 NO 행을 포함) 커밋(C)을 그 뒤에
    둔다 — c_APP(L) 이 edge 커밋(C) 의 **진 조상**이어야 하므로
    (U-16-c g1 SAME_COMMIT 회피) 셋을 한 커밋으로 묶을 수 없다.
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
    if authority_rows is None:
        authority_rows = [AUTHORITY_ROW_RESTRICTED_LIVE, AUTHORITY_ROW_PRODUCTION]
    if current_status_text is None:
        current_status_text = DEFAULT_CURRENT_STATUS_MD
    if completion_status_text is None:
        completion_status_text = DEFAULT_COMPLETION_STATUS_MD
    _write_csv(root / tcs.AUTHORITY_CSV_REL, AUTHORITY_FIELDS, authority_rows)
    current_status_path = root / tcs.CURRENT_STATUS_REL
    current_status_path.parent.mkdir(parents=True, exist_ok=True)
    current_status_path.write_text(current_status_text, encoding="utf-8")
    completion_status_path = root / tcs.GENERATED_MD_REL
    completion_status_path.parent.mkdir(parents=True, exist_ok=True)
    completion_status_path.write_text(completion_status_text, encoding="utf-8")
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

    _write_u16_rationale_doc(root)

    if git_commit:
        _git_init(root)

        # U-16 기본 배선 — UNCHECKABLE_ROW_1(closable=NO)이 살아있는 한
        # R(reviewer) -> L(ledger 승인) 커밋을 레지스터 CSV 커밋(C) 앞에 둔다.
        default_no_row = next(
            (
                r
                for r in uncheckable_rows
                if r.get("id") == UNCHECKABLE_ROW_1["id"] and r.get("closable") == "NO"
            ),
            None,
        )
        if default_no_row is not None:
            digest = _u16_row_canonical_digest(default_no_row)
            reviewer_rel = (
                "docs/reviews/phase0-completion-contract/synthetic-u16/REVIEW.md"
            )
            _write_u16_reviewer(root, reviewer_rel, digest)
            reviewer_commit = _git_commit_all(
                root, "synthetic corpus: u16 reviewer artifact", commit_when
            )
            _write_u16_ledger(
                root,
                [
                    (
                        default_no_row["id"],
                        "ABSENT->NO",
                        digest,
                        reviewer_commit,
                        reviewer_rel,
                        U16_RATIONALE_REF,
                    )
                ],
            )
            _git_commit_all(
                root, "synthetic corpus: u16 ledger approval row", commit_when
            )

        _write_csv(root / tcs.UNCHECKABLE_REL, tcs.UNCHECKABLE_FIELDS, uncheckable_rows)
        base_commit = _git_commit_all(root, "synthetic corpus", commit_when)
        if include_u15_verdict_stamp:
            _write_verdict_stamp(
                root,
                U15_VERDICT_STAMP_DIR,
                _u15_verdict_body(reviewed_at_head=base_commit),
            )
            _git_commit_all(root, "synthetic corpus: U-15 verdict stamp", commit_when)
    else:
        _write_csv(root / tcs.UNCHECKABLE_REL, tcs.UNCHECKABLE_FIELDS, uncheckable_rows)

    # config 는 U-15-g 기준선을 NOT_STARTED 로 지키려 커밋 밖(워킹트리 전용)에
    # 둔다 — git_commit=False 호출자는 자신의 커밋에서 원하면 포함시킨다.
    config_path = root / tcs.CONFIG_REL
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


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


def test_real_corpus_map_never_mixes_marker_and_real_binding_for_same_pair() -> None:
    """FWD-a 매핑 아크 1차 — (evidence_id, surface_kind) 쌍마다 마커 행과 실결속
    행이 병존해서는 안 된다(``planned_unassigned_pairs`` 는 "마커만 있는 쌍" 계수
    이므로 병존은 그 지표를 조용히 왜곡한다). 결속이 생기면 마커 행은 제거된다."""
    with open(_REPO_ROOT / tcs.SURFACE_MAP_REL, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    marker_pairs = {
        (r["evidence_id"], r["surface_kind"])
        for r in rows
        if r["surface_ref"] == "PLANNED_UNASSIGNED"
    }
    real_pairs = {
        (r["evidence_id"], r["surface_kind"])
        for r in rows
        if r["surface_ref"] != "PLANNED_UNASSIGNED"
    }
    coexisting = marker_pairs & real_pairs
    assert coexisting == set(), coexisting


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
# 6b. K-4 — MAP.binding_basis 신규 <repo 경로>:<행> 형식 (FWD-a 매핑 아크 1차)
# ---------------------------------------------------------------------------


def test_k4_path_line_basis_literal_present_is_not_flagged(tmp_path: Path) -> None:
    sample_path = tmp_path / "shared" / "pkg" / "sample.py"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(
        "placeholder\nMINI-EV-001 substrate\nunrelated\n", encoding="utf-8"
    )
    map_rows = [
        dict(
            MAP_ROW_1,
            surface_ref="shared/pkg/sample.py",
            existence="PRESENT",
            binding_basis="shared/pkg/sample.py:2",
        ),
        MAP_ROW_2,
        MAP_ROW_3,
    ]
    write_corpus(tmp_path, map_rows=map_rows)
    assert "K-4" not in _ids(_run(tmp_path))


def test_k4_path_line_basis_literal_absent_is_red(tmp_path: Path) -> None:
    sample_path = tmp_path / "shared" / "pkg" / "sample.py"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(
        "placeholder\nMINI-EV-001 substrate\nunrelated\n", encoding="utf-8"
    )
    map_rows = [
        dict(
            MAP_ROW_1,
            surface_ref="shared/pkg/sample.py",
            existence="PRESENT",
            # 행 3 에는 evidence_id 리터럴이 없다 — 행이 이동/오기입되면 red.
            binding_basis="shared/pkg/sample.py:3",
        ),
        MAP_ROW_2,
        MAP_ROW_3,
    ]
    write_corpus(tmp_path, map_rows=map_rows)
    assert "K-4" in _ids(_run(tmp_path))


# ---------------------------------------------------------------------------
# 6c. K-3 — TEST 배치 수집 (단일 pytest --collect-only 호출, ref 별 개별 실행 아님)
# ---------------------------------------------------------------------------


def test_k3_test_batch_collection_positive_and_negative(tmp_path: Path) -> None:
    test_pkg = tmp_path / "tos" / "tests"
    test_pkg.mkdir(parents=True, exist_ok=True)
    (test_pkg / "test_mini.py").write_text(
        "def test_something() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    map_rows = [
        dict(MAP_ROW_1, surface_ref="shared/pkg/does_not_matter.py"),
        # 양성 — 실제로 수집되는 노드 ID.
        dict(
            MAP_ROW_2,
            # 합성 코퍼스에는 tos/pyproject.toml(ini_options)이 없어 pytest
            # rootdir 이 tmp_path 자체로 잡힌다 — 노드 ID 에 "tos/" 접두가
            # 남는다(실코퍼스는 tos/ 를 rootdir 로 앵커해 접두가 없다).
            surface_ref="tos/tests/test_mini.py::test_something",
            existence="PRESENT",
        ),
        MAP_ROW_3,
    ]
    write_corpus(tmp_path, map_rows=map_rows)
    findings = _ids(_run(tmp_path))
    assert "K-3" not in findings


def test_k3_test_batch_collection_uncollected_ref_is_red(tmp_path: Path) -> None:
    test_pkg = tmp_path / "tos" / "tests"
    test_pkg.mkdir(parents=True, exist_ok=True)
    (test_pkg / "test_mini.py").write_text(
        "def test_something() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    map_rows = [
        MAP_ROW_1,
        # 음성 — 구문은 정상이지만 실제로 수집되지 않는 노드 ID.
        dict(
            MAP_ROW_2,
            surface_ref="tests/test_mini.py::test_does_not_exist",
            existence="PRESENT",
        ),
        MAP_ROW_3,
    ]
    write_corpus(tmp_path, map_rows=map_rows)
    assert "K-3" in _ids(_run(tmp_path))


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
    for expected in (
        "U-12",
        "U-13",
        "U-15",
        "U-16",
        "U-1a",
        "U-4",
        "U-5",
        "U-8",
        "U-9",
        "D0-1",
        "A-1",
        "A-2",
        "A-3",
        "D-1",
    ):
        assert expected in tcs.CONTRACT_CHECKS
    # C3 승격 — T-71 은 이제 U-14 확장으로 CONTRACT_CHECKS 에 강제된다.
    assert tcs.DEFERRED_CONTRACTS == ()
    assert "U-16" not in tcs.DEFERRED_CONTRACTS
    assert "U-17" not in tcs.DEFERRED_CONTRACTS
    assert "U-17" not in tcs.CONTRACT_CHECKS


# ---------------------------------------------------------------------------
# 20. U-15 — d0a_entry_state(9값) 승계 실코퍼스 패리티
# ---------------------------------------------------------------------------


def test_real_corpus_u15_entry_state_matches_harness() -> None:
    """실코퍼스 --check 의 U-15 상태 라인 2종 + 실제 하니스와의 패리티(rc·값)."""
    result = subprocess.run(
        [sys.executable, str(_MODULE_PATH), "--check"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "d0a_entry_state=ENTRY_OK" in result.stdout
    assert "d0a_entry_provenance_state=ENTRY_PROVENANCE_CLEAR" in result.stdout

    harness_rc, harness_state = _harness_entry_state(_REPO_ROOT)
    assert harness_rc == 0
    assert harness_state == "ENTRY_OK"


# ---------------------------------------------------------------------------
# 21. T-81 배터리 ①~⑩ — d0a_entry_state(9값) 변이
# ---------------------------------------------------------------------------


def test_u15_battery_1_bound_doc_edit_after_approval_is_rebinding_required(
    tmp_path: Path,
) -> None:
    _setup_u15_ok_repo(tmp_path)
    (tmp_path / U12_BOUND_DOC_A).write_bytes(b"edited content (no digest update)\n")
    _git_commit_all(
        tmp_path, "edit BP1 without rebinding digest", "2026-01-03T00:00:00Z"
    )

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_state=REBINDING_REQUIRED" in ctx.state_lines
    assert "U-15" in _ids(findings)
    _assert_harness_parity(tmp_path, "REBINDING_REQUIRED")


def test_u15_battery_1e_rebinding_with_digest_update_is_approval_stale(
    tmp_path: Path,
) -> None:
    _setup_u15_ok_repo(tmp_path)
    new_bp1 = b"edited content (with digest rebind)\n"
    (tmp_path / U12_BOUND_DOC_A).write_bytes(new_bp1)
    new_digest = _bound_set_digest(
        {
            U12_BOUND_DOC_A: new_bp1,
            U12_BOUND_DOC_B: U12_DEFAULT_BOUND_DOCS[U12_BOUND_DOC_B],
        }
    )
    (tmp_path / tcs.OQ11_REL).write_text(
        _oq11_artifact_text(digest=new_digest), encoding="utf-8"
    )
    _git_commit_all(tmp_path, "edit BP1 + rebind digest", "2026-01-03T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_state=APPROVAL_STALE" in ctx.state_lines
    assert "U-15" in _ids(findings)
    _assert_harness_parity(tmp_path, "APPROVAL_STALE")


def test_u15_battery_2_digest_mismatch_is_rebinding_required(tmp_path: Path) -> None:
    _setup_u15_ok_repo(tmp_path)
    (tmp_path / tcs.OQ11_REL).write_text(
        _oq11_artifact_text(digest=U12_BROKEN_DIGEST), encoding="utf-8"
    )
    _git_commit_all(tmp_path, "corrupt digest", "2026-01-03T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_state=REBINDING_REQUIRED" in ctx.state_lines
    assert "U-15" in _ids(findings)
    _assert_harness_parity(tmp_path, "REBINDING_REQUIRED")


def test_u15_battery_3_reviewed_plan_paths_missing_one_is_scope_mismatch(
    tmp_path: Path,
) -> None:
    base, _head = _setup_u15_ok_repo(tmp_path)
    body = _u15_verdict_body(
        reviewed_at_head=base, reviewed_plan_paths=[U12_BOUND_DOC_A]
    )
    _write_verdict_stamp(tmp_path, U15_VERDICT_STAMP_DIR, body)
    _git_commit_all(tmp_path, "narrow reviewed_plan_paths", "2026-01-03T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_state=APPROVAL_SCOPE_MISMATCH" in ctx.state_lines
    assert "U-15" in _ids(findings)
    _assert_harness_parity(tmp_path, "APPROVAL_SCOPE_MISMATCH")


def test_u15_battery_4_needs_attention_verdict_is_not_approve(tmp_path: Path) -> None:
    base, _head = _setup_u15_ok_repo(tmp_path)
    body = _u15_verdict_body(reviewed_at_head=base, verdict="needs-attention")
    _write_verdict_stamp(tmp_path, U15_VERDICT_STAMP_DIR, body)
    _git_commit_all(tmp_path, "downgrade verdict", "2026-01-03T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_state=APPROVAL_NOT_APPROVE" in ctx.state_lines
    assert "U-15" in _ids(findings)
    _assert_harness_parity(tmp_path, "APPROVAL_NOT_APPROVE")


def test_u15_battery_4_non_codex_adjudicator_is_not_approve(tmp_path: Path) -> None:
    base, _head = _setup_u15_ok_repo(tmp_path)
    body = _u15_verdict_body(reviewed_at_head=base, adjudicator="claude")
    _write_verdict_stamp(tmp_path, U15_VERDICT_STAMP_DIR, body)
    _git_commit_all(tmp_path, "non-codex adjudicator", "2026-01-03T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_state=APPROVAL_NOT_APPROVE" in ctx.state_lines
    assert "U-15" in _ids(findings)
    _assert_harness_parity(tmp_path, "APPROVAL_NOT_APPROVE")


def test_u15_battery_5_shallow_clone_is_provenance_unverifiable(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    _setup_u15_ok_repo(src)
    clone_dir = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{src}", str(clone_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    ctx, findings = _run_ctx(clone_dir)
    assert "d0a_entry_state=APPROVAL_PROVENANCE_UNVERIFIABLE" in ctx.state_lines
    assert "U-15" in _ids(findings)
    _assert_harness_parity(clone_dir, "APPROVAL_PROVENANCE_UNVERIFIABLE")


def test_u15_battery_6_no_verdict_stamp_is_approval_absent(tmp_path: Path) -> None:
    _setup_u15_base_no_config(tmp_path)  # verdict 스탬프 없이 HEAD 확정

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_state=APPROVAL_ABSENT" in ctx.state_lines
    assert "U-15" in _ids(findings)
    _assert_harness_parity(tmp_path, "APPROVAL_ABSENT")


def test_u15_battery_7_uncommitted_bp_edit_is_freeze_violated(tmp_path: Path) -> None:
    _setup_u15_ok_repo(tmp_path)
    (tmp_path / U12_BOUND_DOC_A).write_bytes(b"dirty uncommitted edit\n")

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_state=FREEZE_VIOLATED" in ctx.state_lines
    assert "U-15" in _ids(findings)
    _assert_harness_parity(tmp_path, "FREEZE_VIOLATED")


def test_u15_battery_8_committed_bp_deletion_is_harness_aborted(tmp_path: Path) -> None:
    _setup_u15_ok_repo(tmp_path)
    (tmp_path / U12_BOUND_DOC_A).unlink()
    _git_commit_all(tmp_path, "delete BP1", "2026-01-03T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_state=HARNESS_ABORTED" in ctx.state_lines
    assert "U-15" in _ids(findings)
    _assert_harness_parity(tmp_path, "HARNESS_ABORTED")


def test_u15_battery_9_git_tool_failure_is_aborted_not_rebinding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup_u15_ok_repo(tmp_path)
    ctx = tcs.build_context(tmp_path)

    def _boom(*_args: object, **_kwargs: object) -> str:
        raise OSError("git not found (simulated)")

    monkeypatch.setattr(tcs, "_resolve_commit", _boom)
    findings = tcs.check_u15(ctx)

    assert "d0a_entry_state=HARNESS_ABORTED" in ctx.state_lines
    assert "d0a_entry_state=REBINDING_REQUIRED" not in ctx.state_lines
    assert "U-15" in _ids(findings)


def test_u15_battery_10_uncommitted_authority_forgery_is_red_not_ok(
    tmp_path: Path,
) -> None:
    _base, head = _setup_u15_ok_repo(tmp_path)
    # 워킹트리에서만 아티팩트 digest 갱신(미커밋).
    (tmp_path / tcs.OQ11_REL).write_text(
        _oq11_artifact_text(digest=U12_BROKEN_DIGEST), encoding="utf-8"
    )
    # 가짜 스탬프도 미커밋으로 신설.
    _write_verdict_stamp(
        tmp_path, "99999999-999999", _u15_verdict_body(reviewed_at_head=head)
    )

    ctx, findings = _run_ctx(tmp_path)
    entry_state = next(
        s.split("=", 1)[1] for s in ctx.state_lines if s.startswith("d0a_entry_state=")
    )
    assert entry_state in ("FREEZE_VIOLATED", "REBINDING_REQUIRED")
    assert "U-15" in _ids(findings)
    _assert_harness_parity(tmp_path, entry_state)


# ---------------------------------------------------------------------------
# 22. T-81 배터리 ⑪~⑫ — U-15-f-1 가드 3단 실측(차단 vs ENTRY_OK)
# ---------------------------------------------------------------------------


def _run_guard(tmp_path: Path, config_yaml_text: str) -> int:
    """U-15-f-1 3단 가드의 최소 재현: 하니스 && config 생성 && commit."""
    script = (
        "set -e\n"
        f"bash {_HARNESS_PATH}\n"
        "cat > config/tos_completion.yaml <<'EOF_CFG'\n"
        f"{config_yaml_text}"
        "EOF_CFG\n"
        "git add config/tos_completion.yaml\n"
        'git commit -q -m "feat(tos): D0A-FIRST guarded intro"\n'
    )
    result = subprocess.run(
        ["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True
    )
    return result.returncode


def test_u15_battery_11_blocked_guard_leaves_config_and_intro_absent(
    tmp_path: Path,
) -> None:
    _setup_u15_base_no_config(tmp_path)  # verdict 스탬프 없음 -> APPROVAL_ABSENT(차단)

    rc = _run_guard(tmp_path, yaml.safe_dump(dict(CONFIG_BASE)))

    assert rc != 0
    assert not (tmp_path / tcs.CONFIG_REL).exists()
    d = tcs._find_config_introduction_commits(tcs.CONFIG_REL, tmp_path)
    assert d == []


def test_u15_battery_12_entry_ok_guard_produces_single_introduction_commit(
    tmp_path: Path,
) -> None:
    base = _setup_u15_base_no_config(tmp_path)
    body = _u15_verdict_body(reviewed_at_head=base)
    _write_verdict_stamp(tmp_path, U15_VERDICT_STAMP_DIR, body)
    _git_commit_all(tmp_path, "add verdict stamp", "2026-01-02T00:00:00Z")

    rc = _run_guard(tmp_path, yaml.safe_dump(dict(CONFIG_BASE)))

    assert rc == 0
    assert (tmp_path / tcs.CONFIG_REL).exists()
    d = tcs._find_config_introduction_commits(tcs.CONFIG_REL, tmp_path)
    assert d is not None
    assert len(d) == 1


# ---------------------------------------------------------------------------
# 23. T-81 배터리 ⑬~⑲ — d0a_entry_provenance_state(8값) 변이
# ---------------------------------------------------------------------------


def test_u15_battery_13_parent_mismatch(tmp_path: Path) -> None:
    head1, transcript_rel, transcript_sha, transcript_text = (
        _setup_ok_head_with_transcript(tmp_path, "13")
    )
    (tmp_path / "unrelated.txt").write_text("noop\n", encoding="utf-8")
    _git_commit_all(tmp_path, "unrelated no-op commit", "2026-01-025T00:00:00Z")
    _commit_config_with_trailers(
        tmp_path,
        config_body=yaml.safe_dump(dict(CONFIG_BASE)),
        transcript_rel=transcript_rel,
        run=1,
        sha256=transcript_sha,
        when="2026-01-03T00:00:00Z",
    )
    _write_transcript(tmp_path, transcript_rel, transcript_text)
    _git_commit_all(tmp_path, "land transcript (T)", "2026-01-04T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert head1  # R-0 head 가 실제 재파생 가능함(어긋난 값과의 비교 대상)
    assert "d0a_entry_provenance_state=PARENT_MISMATCH" in ctx.state_lines
    assert "U-15" in _ids(findings)


def test_u15_battery_14_config_commit_without_trailers_is_malformed(
    tmp_path: Path,
) -> None:
    _setup_u15_base_no_config(tmp_path)
    config_path = tmp_path / tcs.CONFIG_REL
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(dict(CONFIG_BASE)), encoding="utf-8")
    _commit_config_with_message(
        tmp_path, "feat(tos): config intro without trailers", "2026-01-02T00:00:00Z"
    )

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED" in ctx.state_lines
    assert "U-15" in _ids(findings)


def test_u15_battery_15_forward_merge_without_trailers_is_red(tmp_path: Path) -> None:
    _setup_u15_base_no_config(tmp_path)
    main_branch = _git_current_branch(tmp_path)

    _git_checkout_new_branch(tmp_path, "feature")
    config_path = tmp_path / tcs.CONFIG_REL
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(dict(CONFIG_BASE)), encoding="utf-8")
    _commit_config_with_message(
        tmp_path, "d: config intro (no trailers)", "2026-01-02T00:00:00Z"
    )

    _git_checkout(tmp_path, main_branch)
    _git_merge(
        tmp_path, "feature", "merge feature forward (no-ff)", "2026-01-03T00:00:00Z"
    )

    ctx, findings = _run_ctx(tmp_path)
    prov_line = next(
        s for s in ctx.state_lines if s.startswith("d0a_entry_provenance_state=")
    )
    assert prov_line not in (
        "d0a_entry_provenance_state=ENTRY_PROVENANCE_CLEAR",
        "d0a_entry_provenance_state=NOT_STARTED",
    )
    assert "U-15" in _ids(findings)


def test_u15_battery_16_trailerless_d_then_later_transcript_still_malformed(
    tmp_path: Path,
) -> None:
    _setup_u15_base_no_config(tmp_path)
    config_path = tmp_path / tcs.CONFIG_REL
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(dict(CONFIG_BASE)), encoding="utf-8")
    _commit_config_with_message(
        tmp_path, "d: config intro (no trailers)", "2026-01-02T00:00:00Z"
    )
    # 사후 t'/d' 별도 착지 — 파일 «재도입» 이 아니라 무관 후속 커밋일 뿐이다.
    _write_transcript(
        tmp_path,
        "docs/reviews/phase0-completion-contract/synthetic-16/TRANSCRIPT.md",
        "R-0 head=deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\nd0a_entry_state=ENTRY_OK\n",
    )
    _git_commit_all(
        tmp_path, "t': transcript landing (post-hoc)", "2026-01-03T00:00:00Z"
    )

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED" in ctx.state_lines
    assert "U-15" in _ids(findings)


def test_u15_battery_17a_trailer_missing_one_line_is_malformed(tmp_path: Path) -> None:
    _head1, transcript_rel, transcript_sha, transcript_text = (
        _setup_ok_head_with_transcript(tmp_path, "17a")
    )
    config_path = tmp_path / tcs.CONFIG_REL
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(dict(CONFIG_BASE)), encoding="utf-8")
    message = (
        "feat(tos): D0A-FIRST synthetic 17a\n\n"
        f"Entry-Transcript: {transcript_rel}\n"
        f"Entry-Transcript-SHA256: {transcript_sha}\n"  # Run 트레일러 누락(ⓐ)
    )
    _commit_config_with_message(tmp_path, message, "2026-01-03T00:00:00Z")
    _write_transcript(tmp_path, transcript_rel, transcript_text)
    _git_commit_all(tmp_path, "land transcript (T)", "2026-01-04T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED" in ctx.state_lines
    assert "U-15" in _ids(findings)


def test_u15_battery_17b_trailer_duplicate_line_is_malformed(tmp_path: Path) -> None:
    _head1, transcript_rel, transcript_sha, transcript_text = (
        _setup_ok_head_with_transcript(tmp_path, "17b")
    )
    config_path = tmp_path / tcs.CONFIG_REL
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(dict(CONFIG_BASE)), encoding="utf-8")
    message = (
        "feat(tos): D0A-FIRST synthetic 17b\n\n"
        f"Entry-Transcript: {transcript_rel}\n"
        "Entry-Transcript-Run: 1\n"
        "Entry-Transcript-Run: 1\n"  # 같은 줄 2회(ⓑ)
        f"Entry-Transcript-SHA256: {transcript_sha}\n"
    )
    _commit_config_with_message(tmp_path, message, "2026-01-03T00:00:00Z")
    _write_transcript(tmp_path, transcript_rel, transcript_text)
    _git_commit_all(tmp_path, "land transcript (T)", "2026-01-04T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED" in ctx.state_lines
    assert "U-15" in _ids(findings)


def test_u15_battery_17c_trailer_sha_mismatch_is_malformed(tmp_path: Path) -> None:
    _head1, transcript_rel, _transcript_sha, transcript_text = (
        _setup_ok_head_with_transcript(tmp_path, "17c")
    )
    config_path = tmp_path / tcs.CONFIG_REL
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(dict(CONFIG_BASE)), encoding="utf-8")
    message = (
        "feat(tos): D0A-FIRST synthetic 17c\n\n"
        f"Entry-Transcript: {transcript_rel}\n"
        "Entry-Transcript-Run: 1\n"
        f"Entry-Transcript-SHA256: {'0' * 64}\n"  # SHA 불일치(ⓒ)
    )
    _commit_config_with_message(tmp_path, message, "2026-01-03T00:00:00Z")
    _write_transcript(tmp_path, transcript_rel, transcript_text)
    _git_commit_all(tmp_path, "land transcript (T)", "2026-01-04T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_provenance_state=ENTRY_TRAILER_MALFORMED" in ctx.state_lines
    assert "U-15" in _ids(findings)


def test_u15_battery_18_run_status_not_entry_ok_is_transcript_not_entry_ok(
    tmp_path: Path,
) -> None:
    _head1, transcript_rel, transcript_sha, transcript_text = (
        _setup_ok_head_with_transcript(tmp_path, "18", status="REBINDING_REQUIRED")
    )
    _commit_config_with_trailers(
        tmp_path,
        config_body=yaml.safe_dump(dict(CONFIG_BASE)),
        transcript_rel=transcript_rel,
        run=1,
        sha256=transcript_sha,
        when="2026-01-03T00:00:00Z",
    )
    _write_transcript(tmp_path, transcript_rel, transcript_text)
    _git_commit_all(tmp_path, "land transcript (T)", "2026-01-04T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_provenance_state=TRANSCRIPT_NOT_ENTRY_OK" in ctx.state_lines
    assert "U-15" in _ids(findings)


def test_u15_battery_18_transcript_missing_run_is_transcript_missing(
    tmp_path: Path,
) -> None:
    """run 부재/형식 미충족 — 경로/run 부재 시 SHA 계산 불가라 3 이 아니라 6."""
    _head1, transcript_rel, _transcript_sha, _transcript_text = (
        _setup_ok_head_with_transcript(tmp_path, "18b")
    )
    # transcript 내용에 「R-0 head=」 여는 라인 자체가 없다 — run 자체가 미발견.
    malformed_transcript = "이 파일에는 run 여는 라인이 없다.\n"
    malformed_sha = hashlib.sha256(malformed_transcript.encode("utf-8")).hexdigest()
    _commit_config_with_trailers(
        tmp_path,
        config_body=yaml.safe_dump(dict(CONFIG_BASE)),
        transcript_rel=transcript_rel,
        run=1,
        sha256=malformed_sha,
        when="2026-01-03T00:00:00Z",
    )
    _write_transcript(tmp_path, transcript_rel, malformed_transcript)
    _git_commit_all(tmp_path, "land malformed transcript (T)", "2026-01-04T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_provenance_state=TRANSCRIPT_MISSING" in ctx.state_lines
    assert "U-15" in _ids(findings)


def _parallel_introduction_merge(
    tmp_path: Path, *, content_a: bytes, content_b: bytes, resolve_with: bytes
) -> tuple[str, str]:
    """두 브랜치가 독립적으로 config 를 도입 → 머지(충돌 시 ``resolve_with`` 로 해소)."""
    _setup_u15_base_no_config(tmp_path)
    main_branch = _git_current_branch(tmp_path)
    cfg = tmp_path / tcs.CONFIG_REL

    _git_checkout_new_branch(tmp_path, "branch-a")
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_bytes(content_a)
    commit_a = _git_commit_all(
        tmp_path, "branch-a: introduce config", "2026-01-02T00:00:00Z"
    )

    _git_checkout(tmp_path, main_branch)
    _git_checkout_new_branch(tmp_path, "branch-b")
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_bytes(content_b)
    commit_b = _git_commit_all(
        tmp_path, "branch-b: introduce config", "2026-01-02T00:00:01Z"
    )

    _git_checkout(tmp_path, main_branch)
    _git_merge(tmp_path, "branch-a", "merge branch-a", "2026-01-03T00:00:00Z")

    merge_env = dict(os.environ)
    merge_env["GIT_AUTHOR_DATE"] = "2026-01-04T00:00:00 +0000"
    merge_env["GIT_COMMITTER_DATE"] = "2026-01-04T00:00:00 +0000"
    merge_result = subprocess.run(
        ["git", "merge", "--no-ff", "-m", "merge branch-b", "branch-b"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=merge_env,
    )
    if merge_result.returncode != 0:
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_bytes(resolve_with)
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", "resolve add/add conflict", env=merge_env)

    return commit_a, commit_b


def test_u15_battery_19_gu_parallel_introduction_conflict_pick_one_is_multiple(
    tmp_path: Path,
) -> None:
    _parallel_introduction_merge(
        tmp_path, content_a=b"a: 1\n", content_b=b"b: 2\n", resolve_with=b"a: 1\n"
    )
    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_provenance_state=MULTIPLE_INTRODUCTIONS" in ctx.state_lines
    assert "U-15" in _ids(findings)


def test_u15_battery_19_uu_parallel_introduction_conflict_blend_is_multiple(
    tmp_path: Path,
) -> None:
    _parallel_introduction_merge(
        tmp_path,
        content_a=b"a: 1\n",
        content_b=b"b: 2\n",
        resolve_with=b"a: 1\nb: 2\n",
    )
    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_provenance_state=MULTIPLE_INTRODUCTIONS" in ctx.state_lines
    assert "U-15" in _ids(findings)


def test_u15_battery_19_gg_parallel_introduction_identical_content_is_multiple(
    tmp_path: Path,
) -> None:
    """byte-동일 병렬 도입 — ``--diff-filter=A`` 류 구현이면 |D|=1 로 오판한다."""
    same = b"identical: content\n"
    commit_a, commit_b = _parallel_introduction_merge(
        tmp_path, content_a=same, content_b=same, resolve_with=same
    )
    d = tcs._find_config_introduction_commits(tcs.CONFIG_REL, tmp_path)
    assert d is not None
    assert set(d) == {commit_a, commit_b}

    ctx, findings = _run_ctx(tmp_path)
    assert "d0a_entry_provenance_state=MULTIPLE_INTRODUCTIONS" in ctx.state_lines
    assert "U-15" in _ids(findings)


# ---------------------------------------------------------------------------
# 22. U-16 — closable_no_provenance_state(12값) 실코퍼스 패리티
# ---------------------------------------------------------------------------


def test_real_corpus_u16_state_is_no_rows_clear() -> None:
    result = subprocess.run(
        [sys.executable, str(_MODULE_PATH), "--check"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "closable_no_provenance_state=NO_ROWS_CLEAR" in result.stdout


def test_t39_u16_registered_and_not_deferred() -> None:
    assert "U-16" in tcs.CONTRACT_CHECKS
    assert "U-16" not in tcs.DEFERRED_CONTRACTS


# ---------------------------------------------------------------------------
# 23. T-82 배터리 — closable_no_provenance_state(12값) 변이 (§13.6.5)
# ---------------------------------------------------------------------------


def test_u16_battery_0_basic_chain_is_green(tmp_path: Path) -> None:
    """양성 기준선 — R -> L -> C(ABSENT->NO) happy-path, g1~g6·h 전부 충족."""
    _u16_build_basic_chain(tmp_path)
    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=NO_ROWS_CLEAR" in ctx.state_lines
    assert "U-16" not in _ids(findings)


def test_u16_battery_1_same_commit_is_red(tmp_path: Path) -> None:
    """① 단일 커밋 우회 — 승인 행이 edge 커밋과 같은 커밋 -> APPROVAL_SAME_COMMIT."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row = _u16_row("MINI-UNCHK-001-1", "NO")
    digest = _u16_row_canonical_digest(row)
    reviewer_rel = "docs/reviews/u16/REVIEW-1.md"
    _write_u16_reviewer(tmp_path, reviewer_rel, digest)
    reviewer_commit = _git_commit_all(tmp_path, "reviewer", "2026-01-01T00:00:00Z")
    _write_u16_ledger(
        tmp_path,
        [
            (
                row["id"],
                "ABSENT->NO",
                digest,
                reviewer_commit,
                reviewer_rel,
                U16_RATIONALE_REF,
            )
        ],
    )
    _write_u16_register(tmp_path, [row])
    _git_commit_all(
        tmp_path, "ledger + register in the same commit", "2026-01-02T00:00:00Z"
    )

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_SAME_COMMIT" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_2_transition_without_approval_is_missing(tmp_path: Path) -> None:
    """② YES->NO 전이에 승인 없음 -> APPROVAL_MISSING."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row_yes = _u16_row("MINI-UNCHK-002", "YES")
    _write_u16_register(tmp_path, [row_yes])
    _write_u16_ledger(tmp_path, [])
    _git_commit_all(tmp_path, "born YES, empty ledger", "2026-01-01T00:00:00Z")

    row_no = dict(row_yes, closable="NO")
    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "flip to NO without approval", "2026-01-02T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_MISSING" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_3_approval_after_transition_is_red(tmp_path: Path) -> None:
    """③ 전이 뒤에 승인(원장이 edge 커밋의 조상이 아님) -> APPROVAL_AFTER."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row = _u16_row("MINI-UNCHK-003", "NO")
    digest = _u16_row_canonical_digest(row)
    _write_u16_register(tmp_path, [row])
    _git_commit_all(tmp_path, "born NO (no approval yet)", "2026-01-01T00:00:00Z")

    reviewer_rel = "docs/reviews/u16/REVIEW-3.md"
    _write_u16_reviewer(tmp_path, reviewer_rel, digest)
    reviewer_commit = _git_commit_all(
        tmp_path, "reviewer after the fact", "2026-01-02T00:00:00Z"
    )
    _write_u16_ledger(
        tmp_path,
        [
            (
                row["id"],
                "ABSENT->NO",
                digest,
                reviewer_commit,
                reviewer_rel,
                U16_RATIONALE_REF,
            )
        ],
    )
    _git_commit_all(tmp_path, "ledger after the fact", "2026-01-03T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_AFTER" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_4_born_no_without_approval_is_blocked(tmp_path: Path) -> None:
    """④ 출생-NO 무승인 -> 차단 (ABSENT->NO 간선 포섭 증명)."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row = _u16_row("MINI-UNCHK-004", "NO")
    _write_u16_ledger(tmp_path, [])
    _write_u16_register(tmp_path, [row])
    _git_commit_all(tmp_path, "born NO directly, no approval", "2026-01-01T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_MISSING" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_5_delete_then_reintroduce_as_no_is_blocked(tmp_path: Path) -> None:
    """⑤ YES 행 삭제 후 다른 id 로 NO 재도입 -> ABSENT->NO 포섭·차단."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row_yes = _u16_row("MINI-UNCHK-005", "YES")
    _write_u16_register(tmp_path, [row_yes])
    _write_u16_ledger(tmp_path, [])
    _git_commit_all(tmp_path, "born YES", "2026-01-01T00:00:00Z")

    _write_u16_register(tmp_path, [])
    _git_commit_all(tmp_path, "delete row entirely", "2026-01-02T00:00:00Z")

    row_no = _u16_row("MINI-UNCHK-005B", "NO")
    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "reintroduce under new id as NO", "2026-01-03T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert ctx.state_lines[-1] != "closable_no_provenance_state=NO_ROWS_CLEAR"
    assert "U-16" in _ids(findings)


def test_u16_battery_6_orphan_approval_row_is_malformed(tmp_path: Path) -> None:
    """⑥ 레지스터에 없는 row_id 를 가리키는 승인 행 -> APPROVAL_MALFORMED(고아)."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row = _u16_row("MINI-UNCHK-006", "NO")
    digest = _u16_row_canonical_digest(row)
    reviewer_rel = "docs/reviews/u16/REVIEW-6.md"
    _write_u16_reviewer(tmp_path, reviewer_rel, digest)
    reviewer_commit = _git_commit_all(tmp_path, "reviewer", "2026-01-01T00:00:00Z")
    _write_u16_ledger(
        tmp_path,
        [
            (
                "MINI-UNCHK-DOES-NOT-EXIST",
                "ABSENT->NO",
                digest,
                reviewer_commit,
                reviewer_rel,
                U16_RATIONALE_REF,
            )
        ],
    )
    _git_commit_all(
        tmp_path, "orphan ledger row (unrelated id)", "2026-01-02T00:00:00Z"
    )
    _write_u16_register(tmp_path, [row])
    _git_commit_all(tmp_path, "register born-NO (different id)", "2026-01-03T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_MALFORMED" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_7_shallow_clone_is_provenance_unverifiable(tmp_path: Path) -> None:
    """⑦ 얕은 클론(--depth 1) -> PROVENANCE_UNVERIFIABLE (green 이면 실패)."""
    src = tmp_path / "src"
    src.mkdir()
    _u16_build_basic_chain(src, row_id="MINI-UNCHK-007")
    clone_dir = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{src}", str(clone_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    ctx, findings = _run_ctx(clone_dir)
    assert "closable_no_provenance_state=PROVENANCE_UNVERIFIABLE" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_8_unbound_digest_is_red(tmp_path: Path) -> None:
    """⑧ 무관한 기존 리뷰(digest 미포함)를 가리키는 승인 -> APPROVAL_UNBOUND."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row = _u16_row("MINI-UNCHK-008", "NO")
    digest = _u16_row_canonical_digest(row)
    reviewer_rel = "docs/reviews/u16/REVIEW-8.md"
    (tmp_path / reviewer_rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / reviewer_rel).write_text(
        "# unrelated review, digest not present here\n", encoding="utf-8"
    )
    reviewer_commit = _git_commit_all(
        tmp_path, "unrelated reviewer artifact", "2026-01-01T00:00:00Z"
    )
    _write_u16_ledger(
        tmp_path,
        [
            (
                row["id"],
                "ABSENT->NO",
                digest,
                reviewer_commit,
                reviewer_rel,
                U16_RATIONALE_REF,
            )
        ],
    )
    _git_commit_all(
        tmp_path, "ledger points at unbound reviewer", "2026-01-02T00:00:00Z"
    )
    _write_u16_register(tmp_path, [row])
    _git_commit_all(tmp_path, "register born-NO", "2026-01-03T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_UNBOUND" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_9a_head_invalid_non_ancestor(tmp_path: Path) -> None:
    """⑨(a) approved_at_head 가 edge 커밋의 비조상(형제 브랜치) -> APPROVAL_HEAD_INVALID."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row = _u16_row("MINI-UNCHK-009A", "NO")
    digest = _u16_row_canonical_digest(row)
    _git_commit_all(tmp_path, "base", "2026-01-01T00:00:00Z")
    main_branch = _git_current_branch(tmp_path)

    _git_checkout_new_branch(tmp_path, "side")
    reviewer_rel = "docs/reviews/u16/REVIEW-9a.md"
    _write_u16_reviewer(tmp_path, reviewer_rel, digest)
    side_commit = _git_commit_all(
        tmp_path, "reviewer on side branch (never merged)", "2026-01-02T00:00:00Z"
    )

    _git_checkout(tmp_path, main_branch)
    _write_u16_ledger(
        tmp_path,
        [
            (
                row["id"],
                "ABSENT->NO",
                digest,
                side_commit,
                reviewer_rel,
                U16_RATIONALE_REF,
            )
        ],
    )
    _git_commit_all(tmp_path, "ledger references side commit", "2026-01-03T00:00:00Z")
    _write_u16_register(tmp_path, [row])
    _git_commit_all(tmp_path, "register born-NO on main", "2026-01-04T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_HEAD_INVALID" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_9b_head_invalid_missing_reviewer_at_head(tmp_path: Path) -> None:
    """⑨(b) approved_at_head 는 조상이나 그 시점 reviewer_ref 부재 -> APPROVAL_HEAD_INVALID."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row = _u16_row("MINI-UNCHK-009B", "NO")
    digest = _u16_row_canonical_digest(row)
    base_commit = _git_commit_all(
        tmp_path, "base (no reviewer file yet)", "2026-01-01T00:00:00Z"
    )

    reviewer_rel = "docs/reviews/u16/REVIEW-9b.md"  # 어느 커밋에도 실재하지 않는다.
    _write_u16_ledger(
        tmp_path,
        [
            (
                row["id"],
                "ABSENT->NO",
                digest,
                base_commit,
                reviewer_rel,
                U16_RATIONALE_REF,
            )
        ],
    )
    _git_commit_all(
        tmp_path,
        "ledger references base (reviewer absent there)",
        "2026-01-02T00:00:00Z",
    )
    _write_u16_register(tmp_path, [row])
    _git_commit_all(tmp_path, "register born-NO", "2026-01-03T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_HEAD_INVALID" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_10_content_drift_is_red(tmp_path: Path) -> None:
    """⑩ 승인·전이 후 레지스터 행 내용 변경 -> APPROVAL_CONTENT_DRIFT."""
    chain = _u16_build_basic_chain(tmp_path, row_id="MINI-UNCHK-010")
    mutated_row = dict(chain["row"], reason="mutated reason text (post-approval)")
    _write_u16_register(tmp_path, [mutated_row])
    _git_commit_all(
        tmp_path, "mutate NO row content post-approval", "2026-01-04T00:00:00Z"
    )

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_CONTENT_DRIFT" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_11_transition_mismatch_is_malformed(tmp_path: Path) -> None:
    """⑪ 원장 transition=YES->NO 기재·실간선=ABSENT->NO -> MALFORMED."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row = _u16_row("MINI-UNCHK-011", "NO")
    digest = _u16_row_canonical_digest(row)
    reviewer_rel = "docs/reviews/u16/REVIEW-11.md"
    _write_u16_reviewer(tmp_path, reviewer_rel, digest)
    reviewer_commit = _git_commit_all(tmp_path, "reviewer", "2026-01-01T00:00:00Z")
    _write_u16_ledger(
        tmp_path,
        [
            (
                row["id"],
                "YES->NO",
                digest,
                reviewer_commit,
                reviewer_rel,
                U16_RATIONALE_REF,
            )
        ],
    )
    _git_commit_all(
        tmp_path, "ledger declares wrong transition", "2026-01-02T00:00:00Z"
    )
    _write_u16_register(tmp_path, [row])
    _git_commit_all(
        tmp_path, "register born-NO (ABSENT->NO in reality)", "2026-01-03T00:00:00Z"
    )

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_MALFORMED" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_12_late_digest_insertion_still_unbound(tmp_path: Path) -> None:
    """⑫ H0(무관 리뷰)->H1(승인)->H2(전이)->H3(리뷰에 digest 사후 삽입) -> APPROVAL_UNBOUND."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row = _u16_row("MINI-UNCHK-012", "NO")
    digest = _u16_row_canonical_digest(row)
    reviewer_rel = "docs/reviews/u16/REVIEW-12.md"
    _write_u16_reviewer(tmp_path, reviewer_rel, "0" * 64)
    h0 = _git_commit_all(tmp_path, "H0 unrelated review", "2026-01-01T00:00:00Z")

    _write_u16_ledger(
        tmp_path,
        [(row["id"], "ABSENT->NO", digest, h0, reviewer_rel, U16_RATIONALE_REF)],
    )
    _git_commit_all(tmp_path, "H1 approval referencing H0", "2026-01-02T00:00:00Z")

    _write_u16_register(tmp_path, [row])
    _git_commit_all(tmp_path, "H2 transition", "2026-01-03T00:00:00Z")

    _write_u16_reviewer(tmp_path, reviewer_rel, digest)
    _git_commit_all(tmp_path, "H3 late digest insertion", "2026-01-04T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_UNBOUND" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_13_row_mutated_is_red(tmp_path: Path) -> None:
    """⑬ 원장 행 도입 후 편집(구조 키는 그대로) -> APPROVAL_ROW_MUTATED."""
    chain = _u16_build_basic_chain(tmp_path, row_id="MINI-UNCHK-013")
    _write_u16_ledger(
        tmp_path,
        [
            (
                chain["row_id"],
                "ABSENT->NO",
                chain["digest"],
                chain["reviewer_commit"],
                chain["reviewer_rel"],
                U16_RATIONALE_REF_ALT,  # rationale_ref 만 편집 — 구조 키(row_id/transition/digest) 불변.
            )
        ],
    )
    _git_commit_all(
        tmp_path, "edit ledger row after introduction", "2026-01-04T00:00:00Z"
    )

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_ROW_MUTATED" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_14_merge_unapproved_side_edge_breaks_universal(
    tmp_path: Path,
) -> None:
    """⑭ 2-parent 위상 — X 브랜치 무승인 NO 가 merge 를 거쳐도 전칭을 깬다."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row_id = "MINI-UNCHK-014"
    row_yes = _u16_row(row_id, "YES")
    _write_u16_ledger(tmp_path, [])
    _write_u16_register(tmp_path, [row_yes])
    _git_commit_all(tmp_path, "G: YES", "2026-01-01T00:00:00Z")
    main_branch = _git_current_branch(tmp_path)

    _git_checkout_new_branch(tmp_path, "x-branch")
    row_no = dict(row_yes, closable="NO")
    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "X: unapproved NO", "2026-01-02T00:00:00Z")

    _git_checkout(tmp_path, main_branch)
    _git_checkout_new_branch(tmp_path, "a-branch")
    digest = _u16_row_canonical_digest(row_no)
    reviewer_rel = "docs/reviews/u16/REVIEW-14.md"
    _write_u16_reviewer(tmp_path, reviewer_rel, digest)
    reviewer_commit = _git_commit_all(
        tmp_path, "reviewer on A branch", "2026-01-03T00:00:00Z"
    )
    _write_u16_ledger(
        tmp_path,
        [
            (
                row_id,
                "ABSENT->NO",
                digest,
                reviewer_commit,
                reviewer_rel,
                U16_RATIONALE_REF,
            )
        ],
    )
    _git_commit_all(tmp_path, "A: unrelated approval row added", "2026-01-04T00:00:00Z")

    _git_checkout(tmp_path, main_branch)
    _git_merge(tmp_path, "x-branch", "merge X into main", "2026-01-05T00:00:00Z")
    _git_merge(tmp_path, "a-branch", "merge A into main", "2026-01-06T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert ctx.state_lines[-1] != "closable_no_provenance_state=NO_ROWS_CLEAR"
    assert "U-16" in _ids(findings)


def test_u16_battery_15_r_parallel_a_merge_is_order_invalid(tmp_path: Path) -> None:
    """⑮ R∥A 병렬 머지 — g3 은 통과(둘 다 조상)하지만 R⋠A -> APPROVAL_ORDER_INVALID."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row_id = "MINI-UNCHK-015"
    row_yes = _u16_row(row_id, "YES")
    row_no = dict(row_yes, closable="NO")
    digest = _u16_row_canonical_digest(row_no)
    reviewer_rel = "docs/reviews/u16/REVIEW-15.md"

    _write_u16_register(tmp_path, [row_yes])
    _write_u16_ledger(tmp_path, [])
    _git_commit_all(tmp_path, "H0: YES, empty ledger", "2026-01-01T00:00:00Z")
    main_branch = _git_current_branch(tmp_path)

    _git_checkout_new_branch(tmp_path, "r-branch")
    _write_u16_reviewer(tmp_path, reviewer_rel, digest)
    r_commit = _git_commit_all(tmp_path, "R: reviewer artifact", "2026-01-02T00:00:00Z")

    _git_checkout(tmp_path, main_branch)
    _git_checkout_new_branch(tmp_path, "a-branch")
    _write_u16_ledger(
        tmp_path,
        [(row_id, "YES->NO", digest, r_commit, reviewer_rel, U16_RATIONALE_REF)],
    )
    _git_commit_all(
        tmp_path,
        "A: approval row referencing R (parallel branch)",
        "2026-01-03T00:00:00Z",
    )

    _git_checkout(tmp_path, main_branch)
    _git_merge(tmp_path, "r-branch", "merge R into main", "2026-01-04T00:00:00Z")
    _git_merge(tmp_path, "a-branch", "merge A into main", "2026-01-05T00:00:00Z")

    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "transition to NO", "2026-01-06T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_ORDER_INVALID" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_17a_existing_path_parallel_order_invalid(tmp_path: Path) -> None:
    """⑰ⓐ 기존 경로 B∥A — C_R={B}(blob 동일성)·B⋠A -> APPROVAL_ORDER_INVALID."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row_id = "MINI-UNCHK-017A"
    row_yes = _u16_row(row_id, "YES")
    row_no = dict(row_yes, closable="NO")
    digest = _u16_row_canonical_digest(row_no)
    reviewer_rel = "docs/reviews/u16/REVIEW-17A.md"

    _write_u16_register(tmp_path, [row_yes])
    _write_u16_ledger(tmp_path, [])
    (tmp_path / reviewer_rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / reviewer_rel).write_text(
        "# unrelated placeholder, no digest\n", encoding="utf-8"
    )
    _git_commit_all(
        tmp_path,
        "H0: YES, empty ledger, unrelated reviewer path",
        "2026-01-01T00:00:00Z",
    )
    main_branch = _git_current_branch(tmp_path)

    _git_checkout_new_branch(tmp_path, "b-branch")
    _write_u16_reviewer(
        tmp_path, reviewer_rel, digest
    )  # B: 같은 경로를 실제 내용으로 덮어쓴다.
    b_commit = _git_commit_all(
        tmp_path, "B: insert digest into existing path", "2026-01-02T00:00:00Z"
    )

    _git_checkout(tmp_path, main_branch)
    _git_checkout_new_branch(tmp_path, "a-branch")
    _write_u16_ledger(
        tmp_path,
        [(row_id, "YES->NO", digest, b_commit, reviewer_rel, U16_RATIONALE_REF)],
    )
    _git_commit_all(
        tmp_path,
        "A: approval row referencing B (parallel branch)",
        "2026-01-03T00:00:00Z",
    )

    _git_checkout(tmp_path, main_branch)
    _git_merge(tmp_path, "b-branch", "merge B into main", "2026-01-04T00:00:00Z")
    _git_merge(tmp_path, "a-branch", "merge A into main", "2026-01-05T00:00:00Z")

    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "transition to NO", "2026-01-06T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_ORDER_INVALID" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_17b_digest_introduced_after_approved_at_head_is_unbound(
    tmp_path: Path,
) -> None:
    """⑰ⓑ digest 는 approved_at_head(B) 이후 별도 브랜치에서 도입 -> h 선발화 -> APPROVAL_UNBOUND."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row_id = "MINI-UNCHK-017B"
    row_yes = _u16_row(row_id, "YES")
    row_no = dict(row_yes, closable="NO")
    digest = _u16_row_canonical_digest(row_no)
    reviewer_rel = "docs/reviews/u16/REVIEW-17B.md"

    _write_u16_register(tmp_path, [row_yes])
    _write_u16_ledger(tmp_path, [])
    (tmp_path / reviewer_rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / reviewer_rel).write_text(
        "# unrelated placeholder, no digest\n", encoding="utf-8"
    )
    _git_commit_all(
        tmp_path,
        "H0: YES, empty ledger, unrelated reviewer path",
        "2026-01-01T00:00:00Z",
    )
    main_branch = _git_current_branch(tmp_path)

    _git_checkout_new_branch(tmp_path, "b-branch")
    # B 는 승인 대상 커밋이지만 reviewer 파일은 그대로(digest 없음) — approved_at_head 로 쓰인다.
    b_commit = _git_commit_all(
        tmp_path, "B: approved_at_head marker (no digest yet)", "2026-01-02T00:00:00Z"
    )

    _git_checkout(tmp_path, main_branch)
    _git_checkout_new_branch(tmp_path, "digest-branch")
    _write_u16_reviewer(
        tmp_path, reviewer_rel, digest
    )  # digest 는 별도 브랜치에서 도입.
    _git_commit_all(
        tmp_path, "D: insert digest on a separate branch", "2026-01-02T30:00:00Z"
    )

    _git_checkout(tmp_path, main_branch)
    _git_checkout_new_branch(tmp_path, "a-branch")
    _write_u16_ledger(
        tmp_path,
        [(row_id, "YES->NO", digest, b_commit, reviewer_rel, U16_RATIONALE_REF)],
    )
    _git_commit_all(tmp_path, "A: approval row referencing B", "2026-01-03T00:00:00Z")

    _git_checkout(tmp_path, main_branch)
    _git_merge(
        tmp_path,
        "digest-branch",
        "merge digest-branch into main",
        "2026-01-04T00:00:00Z",
    )
    _git_merge(tmp_path, "b-branch", "merge B into main", "2026-01-05T00:00:00Z")
    _git_merge(tmp_path, "a-branch", "merge A into main", "2026-01-06T00:00:00Z")

    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "transition to NO", "2026-01-07T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_UNBOUND" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_17c_shared_reviewer_blob_witness_exists_is_green(
    tmp_path: Path,
) -> None:
    """⑰ⓒ 양성 — B1·B2 가 동일 blob 을 독립 삽입, A 는 B1 자손 -> B1⊰A 증인 존재 -> green."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row_id = "MINI-UNCHK-017C"
    row_yes = _u16_row(row_id, "YES")
    row_no = dict(row_yes, closable="NO")
    digest = _u16_row_canonical_digest(row_no)
    reviewer_rel = "docs/reviews/u16/REVIEW-17C.md"

    _write_u16_register(tmp_path, [row_yes])
    _write_u16_ledger(tmp_path, [])
    h0 = _git_commit_all(
        tmp_path, "H0: YES, empty ledger, no reviewer file", "2026-01-01T00:00:00Z"
    )
    main_branch = _git_current_branch(tmp_path)

    _git_checkout_new_branch(tmp_path, "b1-branch")
    _write_u16_reviewer(tmp_path, reviewer_rel, digest)
    b1_commit = _git_commit_all(
        tmp_path, "B1: reviewer content", "2026-01-02T00:00:00Z"
    )
    _write_u16_ledger(
        tmp_path,
        [(row_id, "YES->NO", digest, b1_commit, reviewer_rel, U16_RATIONALE_REF)],
    )
    _git_commit_all(
        tmp_path, "A: approval row descending from B1", "2026-01-03T00:00:00Z"
    )

    _git_checkout(tmp_path, main_branch)
    _git_checkout_new_branch(tmp_path, "b2-branch")
    _write_u16_reviewer(tmp_path, reviewer_rel, digest)  # 바이트-동일 독립 삽입.
    _git_commit_all(
        tmp_path,
        "B2: identical reviewer content, independent branch",
        "2026-01-02T30:00:00Z",
    )

    _git_checkout(tmp_path, main_branch)
    _git_merge(tmp_path, "b1-branch", "merge B1+A into main", "2026-01-04T00:00:00Z")
    _git_merge(tmp_path, "b2-branch", "merge B2 into main", "2026-01-05T00:00:00Z")

    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "transition to NO", "2026-01-06T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=NO_ROWS_CLEAR" in ctx.state_lines
    assert "U-16" not in _ids(findings)
    assert h0  # H0 는 대조군 증거일 뿐 assert 대상 아님 — 참조로 lint 무시 방지.


def test_u16_battery_18_sibling_branches_each_approve_one_edge_is_green(
    tmp_path: Path,
) -> None:
    """⑱ 병렬 반복 이력 양성 — 두 →NO 간선을 형제 브랜치가 각각 승인 -> NO_ROWS_CLEAR."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row_id = "MINI-UNCHK-018"
    row_no = _u16_row(row_id, "NO")
    row_yes = dict(row_no, closable="YES")
    digest = _u16_row_canonical_digest(row_no)
    reviewer_rel1 = "docs/reviews/u16/REVIEW-18-1.md"
    reviewer_rel2 = "docs/reviews/u16/REVIEW-18-2.md"

    _write_u16_reviewer(tmp_path, reviewer_rel1, digest)
    _write_u16_reviewer(tmp_path, reviewer_rel2, digest)
    _write_u16_ledger(tmp_path, [])
    h0 = _git_commit_all(
        tmp_path,
        "H0: reviewers ready, no register yet, empty ledger",
        "2026-01-01T00:00:00Z",
    )
    main_branch = _git_current_branch(tmp_path)

    row1 = (row_id, "ABSENT->NO", digest, h0, reviewer_rel1, U16_RATIONALE_REF)
    row2 = (row_id, "YES->NO", digest, h0, reviewer_rel2, U16_RATIONALE_REF_ALT)

    _git_checkout_new_branch(tmp_path, "ledger1-branch")
    _write_u16_ledger(tmp_path, [row1])
    _git_commit_all(tmp_path, "L1: approve edge 1 (ABSENT->NO)", "2026-01-02T00:00:00Z")

    _git_checkout(tmp_path, main_branch)
    _git_checkout_new_branch(tmp_path, "ledger2-branch")
    _write_u16_ledger(tmp_path, [row2])
    _git_commit_all(tmp_path, "L2: approve edge 2 (YES->NO)", "2026-01-02T30:00:00Z")

    _git_checkout(tmp_path, main_branch)
    _git_merge_resolving(
        tmp_path,
        "ledger1-branch",
        "merge L1 into main",
        "2026-01-03T00:00:00Z",
        {str(tcs.U16_LEDGER_REL): _u16_ledger_text([row1]).encode("utf-8")},
    )
    _git_merge_resolving(
        tmp_path,
        "ledger2-branch",
        "merge L2 into main",
        "2026-01-04T00:00:00Z",
        {str(tcs.U16_LEDGER_REL): _u16_ledger_text([row1, row2]).encode("utf-8")},
    )

    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "C1: born NO (edge 1)", "2026-01-05T00:00:00Z")
    _write_u16_register(tmp_path, [row_yes])
    _git_commit_all(tmp_path, "C2: flip to YES", "2026-01-06T00:00:00Z")
    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "C3: back to NO (edge 2)", "2026-01-07T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=NO_ROWS_CLEAR" in ctx.state_lines
    assert "U-16" not in _ids(findings)


def test_u16_battery_19_preplaced_digest_carrier_is_order_invalid(
    tmp_path: Path,
) -> None:
    """⑲ digest 선배치 — 빈 운반자(H0) != 실내용 blob(B) -> C_R={B}·B⋠A -> APPROVAL_ORDER_INVALID."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row_id = "MINI-UNCHK-019"
    row_yes = _u16_row(row_id, "YES")
    row_no = dict(row_yes, closable="NO")
    digest = _u16_row_canonical_digest(row_no)
    reviewer_rel = "docs/reviews/u16/REVIEW-19.md"

    _write_u16_register(tmp_path, [row_yes])
    _write_u16_ledger(tmp_path, [])
    (tmp_path / reviewer_rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / reviewer_rel).write_text(
        f"row_content_digest = {digest}\n", encoding="utf-8"
    )  # H0: digest 만 담은 빈 운반자.
    _git_commit_all(tmp_path, "H0: bare digest carrier", "2026-01-01T00:00:00Z")
    main_branch = _git_current_branch(tmp_path)

    _git_checkout_new_branch(tmp_path, "b-branch")
    (tmp_path / reviewer_rel).write_text(
        "# Full review write-up\n\n"
        f"row_content_digest = {digest}\n\n"
        "(실제 심사 서술 — H0 운반자와 바이트가 다르다.)\n",
        encoding="utf-8",
    )
    b_commit = _git_commit_all(
        tmp_path,
        "B: full review content (still contains digest)",
        "2026-01-02T00:00:00Z",
    )

    _git_checkout(tmp_path, main_branch)
    _git_checkout_new_branch(tmp_path, "a-branch")
    _write_u16_ledger(
        tmp_path,
        [(row_id, "YES->NO", digest, b_commit, reviewer_rel, U16_RATIONALE_REF)],
    )
    _git_commit_all(
        tmp_path,
        "A: approval row referencing B (parallel branch)",
        "2026-01-03T00:00:00Z",
    )

    _git_checkout(tmp_path, main_branch)
    _git_merge(tmp_path, "b-branch", "merge B into main", "2026-01-04T00:00:00Z")
    _git_merge(tmp_path, "a-branch", "merge A into main", "2026-01-05T00:00:00Z")

    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "transition to NO", "2026-01-06T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_ORDER_INVALID" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_20a_identical_sibling_ledger_rows_is_malformed(
    tmp_path: Path,
) -> None:
    """⑳ⓐ 동일 승인 행을 형제 둘이 독립 도입 후 merge -> |c_APP|=2 -> APPROVAL_MALFORMED."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row_id = "MINI-UNCHK-020A"
    row_yes = _u16_row(row_id, "YES")
    row_no = dict(row_yes, closable="NO")
    digest = _u16_row_canonical_digest(row_no)
    reviewer_rel = "docs/reviews/u16/REVIEW-20A.md"

    _write_u16_reviewer(tmp_path, reviewer_rel, digest)
    _write_u16_register(tmp_path, [row_yes])
    _write_u16_ledger(tmp_path, [])
    h0 = _git_commit_all(
        tmp_path, "H0: YES, reviewer ready, empty ledger", "2026-01-01T00:00:00Z"
    )
    main_branch = _git_current_branch(tmp_path)

    shared_row = (row_id, "YES->NO", digest, h0, reviewer_rel, U16_RATIONALE_REF)

    _git_checkout_new_branch(tmp_path, "s1-branch")
    _write_u16_ledger(tmp_path, [shared_row])
    _git_commit_all(tmp_path, "S1: introduce approval row", "2026-01-02T00:00:00Z")

    _git_checkout(tmp_path, main_branch)
    _git_checkout_new_branch(tmp_path, "s2-branch")
    _write_u16_ledger(tmp_path, [shared_row])  # byte-동일 독립 도입.
    _git_commit_all(
        tmp_path, "S2: introduce identical approval row", "2026-01-02T30:00:00Z"
    )

    _git_checkout(tmp_path, main_branch)
    _git_merge_resolving(
        tmp_path,
        "s1-branch",
        "merge S1 into main",
        "2026-01-03T00:00:00Z",
        {str(tcs.U16_LEDGER_REL): _u16_ledger_text([shared_row]).encode("utf-8")},
    )
    _git_merge_resolving(
        tmp_path,
        "s2-branch",
        "merge S2 into main",
        "2026-01-04T00:00:00Z",
        {str(tcs.U16_LEDGER_REL): _u16_ledger_text([shared_row]).encode("utf-8")},
    )

    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "transition to NO", "2026-01-05T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=APPROVAL_MALFORMED" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_20b_shallow_clone_of_20a_is_provenance_unverifiable(
    tmp_path: Path,
) -> None:
    """⑳ⓑ ⑳ⓐ 를 얕은 클론에서 — 선-검사 전순서(2 < 3) -> PROVENANCE_UNVERIFIABLE."""
    src = tmp_path / "src"
    src.mkdir()
    _git_init(src)
    _write_u16_rationale_doc(src)
    row_id = "MINI-UNCHK-020B"
    row_yes = _u16_row(row_id, "YES")
    row_no = dict(row_yes, closable="NO")
    digest = _u16_row_canonical_digest(row_no)
    reviewer_rel = "docs/reviews/u16/REVIEW-20B.md"

    _write_u16_reviewer(src, reviewer_rel, digest)
    _write_u16_register(src, [row_yes])
    _write_u16_ledger(src, [])
    h0 = _git_commit_all(
        src, "H0: YES, reviewer ready, empty ledger", "2026-01-01T00:00:00Z"
    )
    main_branch = _git_current_branch(src)

    shared_row = (row_id, "YES->NO", digest, h0, reviewer_rel, U16_RATIONALE_REF)

    _git_checkout_new_branch(src, "s1-branch")
    _write_u16_ledger(src, [shared_row])
    _git_commit_all(src, "S1: introduce approval row", "2026-01-02T00:00:00Z")

    _git_checkout(src, main_branch)
    _git_checkout_new_branch(src, "s2-branch")
    _write_u16_ledger(src, [shared_row])
    _git_commit_all(src, "S2: introduce identical approval row", "2026-01-02T30:00:00Z")

    _git_checkout(src, main_branch)
    _git_merge_resolving(
        src,
        "s1-branch",
        "merge S1 into main",
        "2026-01-03T00:00:00Z",
        {str(tcs.U16_LEDGER_REL): _u16_ledger_text([shared_row]).encode("utf-8")},
    )
    _git_merge_resolving(
        src,
        "s2-branch",
        "merge S2 into main",
        "2026-01-04T00:00:00Z",
        {str(tcs.U16_LEDGER_REL): _u16_ledger_text([shared_row]).encode("utf-8")},
    )

    _write_u16_register(src, [row_no])
    _git_commit_all(src, "transition to NO", "2026-01-05T00:00:00Z")

    clone_dir = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{src}", str(clone_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    ctx, findings = _run_ctx(clone_dir)
    assert "closable_no_provenance_state=PROVENANCE_UNVERIFIABLE" in ctx.state_lines
    assert "U-16" in _ids(findings)


def test_u16_battery_16_repeated_no_transitions_each_approved_is_green(
    tmp_path: Path,
) -> None:
    """⑯ 양성 — ABSENT->NO->YES->NO 선형 반복, 두 간선 각각 승인 -> NO_ROWS_CLEAR."""
    _git_init(tmp_path)
    _write_u16_rationale_doc(tmp_path)
    row_id = "MINI-UNCHK-016"
    row_no = _u16_row(row_id, "NO")
    digest_no = _u16_row_canonical_digest(row_no)

    reviewer_rel1 = "docs/reviews/u16/REVIEW-16-1.md"
    _write_u16_reviewer(tmp_path, reviewer_rel1, digest_no)
    r1 = _git_commit_all(tmp_path, "reviewer 1", "2026-01-01T00:00:00Z")
    _write_u16_ledger(
        tmp_path,
        [(row_id, "ABSENT->NO", digest_no, r1, reviewer_rel1, U16_RATIONALE_REF)],
    )
    _git_commit_all(tmp_path, "approve edge 1 (ABSENT->NO)", "2026-01-02T00:00:00Z")
    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "C1: born NO", "2026-01-03T00:00:00Z")

    row_yes = dict(row_no, closable="YES")
    _write_u16_register(tmp_path, [row_yes])
    _git_commit_all(tmp_path, "C2: flip to YES", "2026-01-04T00:00:00Z")

    reviewer_rel2 = "docs/reviews/u16/REVIEW-16-2.md"
    _write_u16_reviewer(tmp_path, reviewer_rel2, digest_no)
    r2 = _git_commit_all(tmp_path, "reviewer 2", "2026-01-05T00:00:00Z")
    _write_u16_ledger(
        tmp_path,
        [
            (row_id, "ABSENT->NO", digest_no, r1, reviewer_rel1, U16_RATIONALE_REF),
            (row_id, "YES->NO", digest_no, r2, reviewer_rel2, U16_RATIONALE_REF),
        ],
    )
    _git_commit_all(tmp_path, "approve edge 2 (YES->NO)", "2026-01-06T00:00:00Z")
    _write_u16_register(tmp_path, [row_no])
    _git_commit_all(tmp_path, "C3: back to NO (2nd time)", "2026-01-07T00:00:00Z")

    ctx, findings = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=NO_ROWS_CLEAR" in ctx.state_lines
    assert "U-16" not in _ids(findings)


def test_u16_battery_20c_graft_on_origin_does_not_affect_snapshot_judgment(
    tmp_path: Path,
) -> None:
    """⑳ⓒ 격리 검증 — 원본에 graft 를 심어도 스냅샷 소비 구현은 판정 불변."""
    _u16_build_basic_chain(tmp_path, row_id="MINI-UNCHK-020C")
    ctx_before, findings_before = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=NO_ROWS_CLEAR" in ctx_before.state_lines
    assert "U-16" not in _ids(findings_before)

    head = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    root_commit = (
        _git(tmp_path, "rev-list", "--max-parents=0", "HEAD")
        .stdout.strip()
        .splitlines()[0]
    )
    # 후보 밖 graft — HEAD 를 자기 자신의 조상(가짜 root)에 접붙인다.  U-16
    # 판정과 무관한 커밋에만 영향을 주므로 판정 자체는 불변이어야 한다.
    _git(tmp_path, "replace", "--graft", root_commit, root_commit)

    ctx_after, findings_after = _run_ctx(tmp_path)
    assert "closable_no_provenance_state=NO_ROWS_CLEAR" in ctx_after.state_lines
    assert "U-16" not in _ids(findings_after)
    assert head == _git(tmp_path, "rev-parse", "HEAD").stdout.strip()


# ---------------------------------------------------------------------------
# 21. C3 — TOS-COMPLETION-STATUS 생성기 (구 D0-1)
# ---------------------------------------------------------------------------


def test_real_corpus_gate_verdicts_match_expectations() -> None:
    """§4.2 예상: 실코퍼스에서 G1~G3 = NOT_MET · G4 = NOT_AUTHORIZED."""
    ctx = tcs.build_context(_REPO_ROOT)
    tcs.run_checks(ctx)
    verdicts, reasons, _contributions = tcs.evaluate_gates(
        ctx.uncheckable_rows, tcs.GATE_PREDICATES, tcs._real_checkable_results(ctx)
    )
    assert verdicts == {"G1": "NOT_MET", "G2": "NOT_MET", "G3": "NOT_MET"}
    assert tcs.derive_g4_authority(_REPO_ROOT) == "NOT_AUTHORIZED"
    # 현행: UNCHK-016·017·018 → G2 reasons(§13.6.2 U-8a 주).
    assert reasons["G2"] == frozenset({"UNCHK-016", "UNCHK-017", "UNCHK-018"})
    assert reasons["G1"] == frozenset()
    assert reasons["G3"] == frozenset()


def test_real_corpus_generator_write_check_cycle() -> None:
    result = subprocess.run(
        [sys.executable, str(_MODULE_PATH), "--write"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    result2 = subprocess.run(
        [sys.executable, str(_MODULE_PATH), "--check"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result2.returncode == 0, result2.stdout + result2.stderr
    assert "RESULT: GREEN (violations=0)" in result2.stdout


def test_generator_write_then_check_is_green(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    assert tcs.main(["--write", "--root", str(tmp_path)]) == 0
    assert tcs.main(["--check", "--root", str(tmp_path)]) == 0


def test_generator_missing_file_is_red(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    assert tcs.main(["--check", "--root", str(tmp_path)]) == 1


def test_generator_currency_one_byte_mutation_is_red(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    assert tcs.main(["--write", "--root", str(tmp_path)]) == 0
    md_path = tmp_path / tcs.GENERATED_MD_REL
    md_path.write_bytes(md_path.read_bytes() + b"x")
    assert tcs.main(["--check", "--root", str(tmp_path)]) == 1


def test_missing_write_and_check_flags_is_usage_error() -> None:
    result = subprocess.run(
        [sys.executable, str(_MODULE_PATH), "--write", "--check"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2


def test_t73_removing_a_u10_metric_line_from_generated_file_is_red(
    tmp_path: Path,
) -> None:
    write_corpus(tmp_path)
    assert tcs.main(["--write", "--root", str(tmp_path)]) == 0
    md_path = tmp_path / tcs.GENERATED_MD_REL
    text = md_path.read_text(encoding="utf-8")
    mutated = "\n".join(
        line for line in text.splitlines() if "closable_no_rows=" not in line
    )
    md_path.write_text(mutated, encoding="utf-8")
    assert tcs.main(["--check", "--root", str(tmp_path)]) == 1


def test_t23_truncating_register_table_row_in_generated_file_is_red(
    tmp_path: Path,
) -> None:
    write_corpus(tmp_path)
    assert tcs.main(["--write", "--root", str(tmp_path)]) == 0
    md_path = tmp_path / tcs.GENERATED_MD_REL
    lines = md_path.read_text(encoding="utf-8").splitlines()
    for idx in range(len(lines) - 1, -1, -1):
        if lines[idx].startswith("| MINI-UNCHK-001"):
            del lines[idx]
            break
    else:
        raise AssertionError("MINI-UNCHK-001 행을 찾지 못함")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert tcs.main(["--check", "--root", str(tmp_path)]) == 1


def test_t21_predicate_table_below_11_rows_is_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_corpus(tmp_path)
    monkeypatch.setattr(tcs, "GATE_PREDICATES", tcs.GATE_PREDICATES[:10])
    assert "D0-1" in _ids(_run(tmp_path))


def test_t21_predicate_table_is_exactly_11_rows_with_2_3_6_distribution() -> None:
    assert len(tcs.GATE_PREDICATES) == 11
    checkable = sum(1 for p in tcs.GATE_PREDICATES if p.classification == "CHECKABLE")
    partial = sum(1 for p in tcs.GATE_PREDICATES if p.classification == "PARTIAL")
    nmc = sum(1 for p in tcs.GATE_PREDICATES if p.classification == "NMC")
    assert (checkable, partial, nmc) == (2, 3, 6)


def test_t80_t71_forward_mismatch_is_red(tmp_path: Path) -> None:
    bad_config = dict(CONFIG_BASE, anchor_classification_checkable=99)
    write_corpus(tmp_path, config=bad_config)
    assert "U-14" in _ids(_run(tmp_path))


def test_t80_t71_reverse_mismatch_is_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_corpus(tmp_path)
    all_checkable = tuple(
        tcs.GatePredicate(p.predicate_id, p.gate, p.condition, "CHECKABLE", None)
        for p in tcs.GATE_PREDICATES
    )
    monkeypatch.setattr(tcs, "GATE_PREDICATES", all_checkable)
    assert "U-14" in _ids(_run(tmp_path))


def test_t80_t71_key_missing_is_red(tmp_path: Path) -> None:
    bad_config = dict(CONFIG_BASE)
    del bad_config["anchor_classification_partial"]
    write_corpus(tmp_path, config=bad_config)
    assert "U-14" in _ids(_run(tmp_path))


def test_t80_t71_type_error_is_red(tmp_path: Path) -> None:
    bad_config = dict(CONFIG_BASE, anchor_classification_nmc="6")
    write_corpus(tmp_path, config=bad_config)
    assert "U-14" in _ids(_run(tmp_path))


def test_t75_all_met_reachability() -> None:
    """T-75 — 계약이 all-MET 을 표현할 수 있음을 합성 벡터로 양성 증명한다."""
    synthetic = tuple(
        tcs.GatePredicate(f"SYN-{i}", gate, "synthetic", "CHECKABLE", None)
        for i, gate in enumerate(["G1"] * 5 + ["G2"] * 3 + ["G3"] * 3)
    )
    results = {p.predicate_id: True for p in synthetic}
    verdicts, _reasons, contributions = tcs.evaluate_gates([], synthetic, results)
    assert verdicts == {"G1": "MET", "G2": "MET", "G3": "MET"}
    assert set(contributions) == {p.predicate_id for p in synthetic}
    assert all(v == "MET" for v in contributions.values())


def test_t69_gate_predicate_fold_is_isolated_per_predicate() -> None:
    """T-69 — 한 술어의 분류 변형이 다른 술어의 기여 항을 건드리지 않는다."""
    _verdicts, _reasons, baseline = tcs.evaluate_gates([], tcs.GATE_PREDICATES, {})
    assert set(baseline.values()) == {"NOT_MET"}
    for target in tcs.GATE_PREDICATES:
        forced = tuple(
            (
                tcs.GatePredicate(
                    p.predicate_id, p.gate, p.condition, "CHECKABLE", None
                )
                if p.predicate_id == target.predicate_id
                else p
            )
            for p in tcs.GATE_PREDICATES
        )
        _v, _r, contrib = tcs.evaluate_gates([], forced, {target.predicate_id: True})
        for p in tcs.GATE_PREDICATES:
            expected = "MET" if p.predicate_id == target.predicate_id else "NOT_MET"
            assert contrib[p.predicate_id] == expected, (
                target.predicate_id,
                p.predicate_id,
            )


def test_t2_authority_mutation_does_not_affect_g1_g3(tmp_path: Path) -> None:
    """T-2(INV-C1 회귀) — AUTHORITY-STATUS.csv 뮤테이션은 G1~G3 verdict·reasons
    를 바꾸지 않고 G4 만 바꾼다."""
    write_corpus(tmp_path)
    ctx1 = tcs.build_context(tmp_path)
    verdicts1, reasons1, _c1 = tcs.evaluate_gates(
        ctx1.uncheckable_rows, tcs.GATE_PREDICATES, tcs._real_checkable_results(ctx1)
    )
    g4_before = tcs.derive_g4_authority(tmp_path)
    assert g4_before == "NOT_AUTHORIZED"

    write_corpus(
        tmp_path,
        authority_rows=[
            dict(AUTHORITY_ROW_RESTRICTED_LIVE, status="AUTHORIZED"),
            dict(AUTHORITY_ROW_PRODUCTION, status="AUTHORIZED"),
        ],
    )
    ctx2 = tcs.build_context(tmp_path)
    verdicts2, reasons2, _c2 = tcs.evaluate_gates(
        ctx2.uncheckable_rows, tcs.GATE_PREDICATES, tcs._real_checkable_results(ctx2)
    )
    g4_after = tcs.derive_g4_authority(tmp_path)

    assert verdicts1 == verdicts2
    assert reasons1 == reasons2
    assert g4_after == "AUTHORIZED"
    assert g4_before != g4_after


def test_t11_g4_unaffected_by_non_authority_sources(tmp_path: Path) -> None:
    """T-11(INV-C2) — G4 는 AUTHORITY-STATUS.csv 외 어떤 소스 뮤테이션에도
    불변이다."""
    write_corpus(tmp_path)
    g4_before = tcs.derive_g4_authority(tmp_path)

    mutated_row = dict(
        UNCHECKABLE_ROW_2_YES, id="MINI-UNCHK-999", blocks_gate="", normative_ref=""
    )
    write_corpus(
        tmp_path,
        uncheckable_rows=[UNCHECKABLE_ROW_1, UNCHECKABLE_ROW_2_YES, mutated_row],
    )
    g4_after = tcs.derive_g4_authority(tmp_path)

    assert g4_before == g4_after == "NOT_AUTHORIZED"


def test_t58_u8_blank_blocks_gate_on_nonblank_normative_ref_is_red(
    tmp_path: Path,
) -> None:
    bad_row = dict(
        UNCHECKABLE_ROW_2_YES,
        id="MINI-UNCHK-058",
        normative_ref="VER-002-001 §5 Composite Notation (:168)",
        blocks_gate="",
    )
    write_corpus(tmp_path, uncheckable_rows=[UNCHECKABLE_ROW_1, bad_row])
    assert "U-8" in _ids(_run(tmp_path))


def test_t68_u8b_allowed_set_derives_from_gate_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_row = dict(
        UNCHECKABLE_ROW_2_YES, id="MINI-UNCHK-068", normative_ref="x", blocks_gate="G7"
    )
    write_corpus(tmp_path, uncheckable_rows=[UNCHECKABLE_ROW_1, bad_row])

    assert "U-8b" in _ids(_run(tmp_path))

    monkeypatch.setattr(tcs, "GATE_REGISTRY", {**tcs.GATE_REGISTRY, "G7": "AUTHORITY"})
    assert "U-8b" in _ids(_run(tmp_path))

    monkeypatch.setattr(tcs, "GATE_REGISTRY", {**tcs.GATE_REGISTRY, "G7": "COMPLETION"})
    assert "U-8b" not in _ids(_run(tmp_path))


def test_t61_moving_blocks_gate_moves_reason_membership() -> None:
    allowed = frozenset({"G1", "G2", "G3"})
    row = dict(UNCHECKABLE_ROW_2_YES, id="X", normative_ref="ref", blocks_gate="G2")
    reasons = tcs.compute_gate_reasons([row], allowed)
    assert "X" in reasons["G2"]
    assert "X" not in reasons["G3"]

    row2 = dict(row, blocks_gate="G3")
    reasons2 = tcs.compute_gate_reasons([row2], allowed)
    assert "X" not in reasons2["G2"]
    assert "X" in reasons2["G3"]


def test_t70_two_nonempty_gate_reason_sets_are_not_identical() -> None:
    allowed = frozenset({"G1", "G2", "G3"})
    rows = [
        dict(UNCHECKABLE_ROW_2_YES, id="A", normative_ref="ref", blocks_gate="G2"),
        dict(UNCHECKABLE_ROW_2_YES, id="B", normative_ref="ref", blocks_gate="G3"),
    ]
    reasons = tcs.compute_gate_reasons(rows, allowed)
    nonempty_values = [ids for ids in reasons.values() if ids]
    assert len(nonempty_values) >= 2
    assert len({frozenset(v) for v in nonempty_values}) == len(nonempty_values)
    # 공집합 위양성 회피(v2.2) — 사유가 아직 없는 게이트끼리는 ∅==∅ 이어도 정상.
    assert reasons["G1"] == frozenset()


def test_t63_u9_unresolvable_citation_is_red(tmp_path: Path) -> None:
    bad_row = dict(UNCHECKABLE_ROW_1, reason="mini reason (§99.9)")
    write_corpus(tmp_path, uncheckable_rows=[bad_row])
    assert "U-9" in _ids(_run(tmp_path))


def test_t63_u9_freeform_prose_without_citation_is_red(tmp_path: Path) -> None:
    bad_row = dict(UNCHECKABLE_ROW_1, reason="나중에 봄")
    write_corpus(tmp_path, uncheckable_rows=[bad_row])
    assert "U-9" in _ids(_run(tmp_path))


def test_t74_closable_yes_to_no_transition_without_anchor_update_is_red(
    tmp_path: Path,
) -> None:
    transitioned = dict(
        UNCHECKABLE_ROW_2_YES,
        closable="NO",
        owner_track="",
        reason="mini reason (§13.5)",
    )
    write_corpus(tmp_path, uncheckable_rows=[UNCHECKABLE_ROW_1, transitioned])
    assert "U-14" in _ids(_run(tmp_path))


def test_scrub_removes_not_authorized_before_forbidden_vocab_scan() -> None:
    assert tcs._scan_forbidden_vocabulary("state=NOT_AUTHORIZED") == []
    assert tcs._scan_forbidden_vocabulary("this was already done") == []
    assert tcs._scan_forbidden_vocabulary("this gate is ready") == ["ready"]
    assert tcs._scan_forbidden_vocabulary("plan approved") == ["approved"]


def test_inv_c5_forbidden_vocabulary_in_static_prose_is_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_corpus(tmp_path)
    monkeypatch.setattr(
        tcs, "_STATIC_PROSE", tcs._STATIC_PROSE + "\nThis gate is ready.\n"
    )
    assert "D0-1" in _ids(_run(tmp_path))


def test_inv_c5_real_static_prose_is_clean() -> None:
    assert tcs._scan_forbidden_vocabulary(tcs._STATIC_PROSE) == []


# ---------------------------------------------------------------------------
# 21. D0-4b — A-1/A-2/A-3 authority 축 (§6.4)
# ---------------------------------------------------------------------------


def test_a1_real_corpus_source_vocabulary_is_clean() -> None:
    ctx = tcs.build_context(_REPO_ROOT)
    assert tcs.check_a1(ctx) == []


def test_a1_synthetic_default_is_clean(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    assert "A-1" not in _ids(_run(tmp_path))


def test_a1_bad_status_vocabulary_is_red(tmp_path: Path) -> None:
    write_corpus(
        tmp_path,
        authority_rows=[
            dict(AUTHORITY_ROW_RESTRICTED_LIVE, status="MAYBE"),
            AUTHORITY_ROW_PRODUCTION,
        ],
    )
    assert "A-1" in _ids(_run(tmp_path))


def test_a1_missing_axis_is_red(tmp_path: Path) -> None:
    write_corpus(tmp_path, authority_rows=[AUTHORITY_ROW_RESTRICTED_LIVE])
    assert "A-1" in _ids(_run(tmp_path))


def test_a1_missing_file_is_red(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    (tmp_path / tcs.AUTHORITY_CSV_REL).unlink()
    assert "A-1" in _ids(_run(tmp_path))


def test_a2_real_corpus_three_surfaces_agree() -> None:
    ctx = tcs.build_context(_REPO_ROOT)
    assert tcs.check_a2(ctx) == []


MISMATCHED_CURRENT_STATUS_MD = """# Mini Current Status

| Axis | Value | Notes |
|---|---|---|
| Restricted-live | `AUTHORIZED` | mini note |
| Production authorization | `NOT_AUTHORIZED` | mini note |
"""


def test_a2_current_status_value_mismatch_is_red(tmp_path: Path) -> None:
    """A-2 — tmp 사본 값 불일치 뮤테이션(CURRENT-STATUS.md 만 AUTHORIZED 로 드리프트)."""
    write_corpus(tmp_path, current_status_text=MISMATCHED_CURRENT_STATUS_MD)
    assert "A-2" in _ids(_run(tmp_path))


def test_a2_current_status_missing_axis_is_red(tmp_path: Path) -> None:
    text = "# Mini Current Status\n\n| Restricted-live | `NOT_AUTHORIZED` | note |\n"
    write_corpus(tmp_path, current_status_text=text)
    assert "A-2" in _ids(_run(tmp_path))


def test_a2_current_status_file_missing_is_red(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    (tmp_path / tcs.CURRENT_STATUS_REL).unlink()
    assert "A-2" in _ids(_run(tmp_path))


def test_a2_completion_status_g4_mismatch_is_red(tmp_path: Path) -> None:
    text = "| G4 | `AUTHORITY` | `AUTHORIZED` | - |\n"
    write_corpus(tmp_path, completion_status_text=text)
    assert "A-2" in _ids(_run(tmp_path))


def test_a2_completion_status_g4_row_missing_is_red(tmp_path: Path) -> None:
    write_corpus(tmp_path, completion_status_text="# nothing here\n")
    assert "A-2" in _ids(_run(tmp_path))


def test_a2_architecture_gate_status_prose_only_is_not_flagged(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    arch_path = tmp_path / tcs.ARCH_GATE_STATUS_REL
    arch_path.parent.mkdir(parents=True, exist_ok=True)
    arch_path.write_text(
        "restricted-live and production authorization (both `NOT_AUTHORIZED`)\n",
        encoding="utf-8",
    )
    assert "A-2" not in _ids(_run(tmp_path))


def test_a2_architecture_gate_status_parseable_mismatch_is_red(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    arch_path = tmp_path / tcs.ARCH_GATE_STATUS_REL
    arch_path.parent.mkdir(parents=True, exist_ok=True)
    arch_path.write_text(
        "| Restricted-live | `AUTHORIZED` | note |\n", encoding="utf-8"
    )
    assert "A-2" in _ids(_run(tmp_path))


def test_a3_real_derive_g4_authority_is_clean() -> None:
    ctx = tcs.build_context(_REPO_ROOT)
    assert tcs.check_a3(ctx) == []


def test_a3_synthetic_default_is_clean(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    assert "A-3" not in _ids(_run(tmp_path))


def test_a3_evidence_symbol_injection_is_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A-3 — evidence 심볼 주입 뮤테이션: derive_g4_authority 를 GATE_PREDICATES
    (게이트 술어 evidence 표면)를 참조하는 함수로 바꿔치기하면 검출돼야 한다."""

    def mutated_derive_g4_authority(_repo_root: Path) -> str:
        if tcs.GATE_PREDICATES:
            pass
        return "NOT_AUTHORIZED"

    write_corpus(tmp_path)
    monkeypatch.setattr(tcs, "derive_g4_authority", mutated_derive_g4_authority)
    ctx = tcs.build_context(tmp_path)
    assert "A-3" in _ids(tcs.check_a3(ctx))


def _d1_probe_leaf_referencing_evidence_symbol() -> None:
    """모듈 최상위 함수 — ``__globals__`` 를 통해 호출 그래프가 실제로 펼쳐
    보이는 대상이 되려면 이 함수가 (닫힘 지역변수가 아니라) 이 테스트 모듈의
    전역 이름으로 존재해야 한다."""
    _ = tcs.REGISTER_FIELDS  # evidence 심볼 (register 파싱)


def _mutated_derive_g4_authority_calls_leaf(_repo_root: Path) -> str:
    _d1_probe_leaf_referencing_evidence_symbol()
    return "NOT_AUTHORIZED"


def test_a3_call_graph_closure_follows_module_level_callees(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-3 의 호출 그래프 순회가 entry 함수 자신뿐 아니라, 그 함수가 호출하는
    같은 모듈의 다른 함수까지 펼쳐 evidence 심볼을 잡아낸다."""
    monkeypatch.setattr(
        tcs, "derive_g4_authority", _mutated_derive_g4_authority_calls_leaf
    )
    consumed = tcs._call_graph_closure(tcs.derive_g4_authority)
    assert "REGISTER_FIELDS" in consumed


# ---------------------------------------------------------------------------
# 22. D0-5b — D-1 처분 검사기 + U-6 (§7.4/§13.6.6)
# ---------------------------------------------------------------------------

D1_TEST_SITE_REL = Path("d1_test_pkg/probe_module.py")
D1_TEST_SITES = (("d1probe", D1_TEST_SITE_REL, "module", ""),)


def _write_d1_test_site(root: Path, docstring_body: str) -> None:
    path = root / D1_TEST_SITE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'"""{docstring_body}"""\n', encoding="utf-8")


def _write_mini_profile(
    root: Path, *, bounds: dict[str, dict[str, object]], limits: dict[str, object]
) -> None:
    path = root / tcs.VERIFICATION_PROFILE_002_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"bounds": bounds, "limits": limits}, sort_keys=False),
        encoding="utf-8",
    )


def test_d1_real_corpus_dispositions_match_expected() -> None:
    """§7.4 실측 기대: 7곳 전부 UNBOUND (UNCHK-024 부분 해소 — resolver 도 UNBOUND)."""
    dispositions, _profile_blocked = tcs.compute_d1_dispositions(_REPO_ROOT)
    for name in (
        "backtest__init__",
        "resolver",
        "results",
        "construction",
        "records",
        "engine",
        "marketfeed",
    ):
        assert dispositions[name][0] == "UNBOUND", (name, dispositions[name])


def test_d1_real_corpus_u6_registered_is_clean() -> None:
    ctx = tcs.build_context(_REPO_ROOT)
    assert tcs.check_d1(ctx) == []


def test_d1_unbound_declaration_phrase_is_derived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tcs, "D1_SITES", D1_TEST_SITES)
    _write_d1_test_site(
        tmp_path,
        "some_field is not a VERIFICATION-PROFILE-002 key at all, absent from census.",
    )
    dispositions, _profile_blocked = tcs.compute_d1_dispositions(tmp_path)
    assert dispositions["d1probe"][0] == "UNBOUND"


def test_d1_valued_nonnull_backtick_key_is_derived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tcs, "D1_SITES", D1_TEST_SITES)
    _write_mini_profile(
        tmp_path,
        bounds={"B_probe_bound": {"value_ms": 500}},
        limits={"MAX_probe_ceiling": 1},
    )
    _write_d1_test_site(tmp_path, "This module consumes ``B_probe_bound``.")
    dispositions, _profile_blocked = tcs.compute_d1_dispositions(tmp_path)
    assert dispositions["d1probe"] == ("VALUED", "B_probe_bound")


def test_d1_blocked_null_backtick_key_is_derived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tcs, "D1_SITES", D1_TEST_SITES)
    _write_mini_profile(
        tmp_path,
        bounds={"B_probe_bound": {"value_ms": None}},
        limits={"MAX_probe_ceiling": 1},
    )
    _write_d1_test_site(tmp_path, "This module consumes ``B_probe_bound``.")
    dispositions, _profile_blocked = tcs.compute_d1_dispositions(tmp_path)
    assert dispositions["d1probe"] == ("BLOCKED", "B_probe_bound")


def test_d1_unbound_declaration_wins_over_incidental_profile_key_mention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """engine/__init__.py 재현 — 대조용으로 실재 프로파일 키를 인용해도
    UNBOUND 선언 문언이 우선한다(§7.4 — 저작자 결론이 우선)."""
    monkeypatch.setattr(tcs, "D1_SITES", D1_TEST_SITES)
    _write_mini_profile(
        tmp_path,
        bounds={"B_probe_bound": {"value_ms": 500}},
        limits={"MAX_probe_ceiling": 1},
    )
    _write_d1_test_site(
        tmp_path,
        "The real dependency is not a VERIFICATION-PROFILE-002 key at all; "
        "for contrast the profile does carry ``B_probe_bound`` (non-null) but that "
        "bounds something else entirely.",
    )
    dispositions, _profile_blocked = tcs.compute_d1_dispositions(tmp_path)
    assert dispositions["d1probe"][0] == "UNBOUND"


def test_d1_key_not_supplied_is_undecided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tcs, "D1_SITES", D1_TEST_SITES)
    # 우주는 정상 로드되지만(genuine 케이스와 profile-load-failure 케이스를
    # 구별하려면 프로파일이 유효해야 한다) 이 docstring 은 어떤 키도 인용하지
    # 않는다.
    _write_mini_profile(
        tmp_path,
        bounds={"B_probe_bound": {"value_ms": 1}},
        limits={"MAX_probe_ceiling": 1},
    )
    _write_d1_test_site(tmp_path, "No bound is named or cited here at all.")
    dispositions, profile_blocked = tcs.compute_d1_dispositions(tmp_path)
    assert dispositions["d1probe"][0] == "UNDECIDED"
    assert profile_blocked == ()


def test_d1_missing_site_file_is_excluded_from_dispositions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tcs, "D1_SITES", D1_TEST_SITES)
    dispositions, _profile_blocked = tcs.compute_d1_dispositions(tmp_path)
    assert "d1probe" not in dispositions


def test_u6_undecided_site_without_register_row_is_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tcs, "D1_SITES", D1_TEST_SITES)
    write_corpus(tmp_path)
    # 유효한 프로파일을 둬야 이 UNDECIDED 가 genuine("키 미공급")임을
    # 확인할 수 있다 — 프로파일이 아예 없으면 profile-load-failure 축으로
    # 새는 별도 D-1 violation(과 이 테스트가 검증하려는 U-6 이 아니게 된다).
    _write_mini_profile(
        tmp_path,
        bounds={"B_probe_bound": {"value_ms": 1}},
        limits={"MAX_probe_ceiling": 1},
    )
    _write_d1_test_site(tmp_path, "No bound is named or cited here at all.")
    findings = _run(tmp_path)
    assert "U-6" in _ids(findings)
    assert "D-1" not in _ids(findings)


def test_u6_undecided_site_with_register_row_is_green(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tcs, "D1_SITES", D1_TEST_SITES)
    registered_row = dict(
        UNCHECKABLE_ROW_2_YES,
        id="MINI-UNCHK-D1PROBE",
        axis="d1probe 사이트의 결속 축",
        reason="d1probe 는 UNDECIDED 로 §7.4 D-1 이 파생했다",
    )
    write_corpus(tmp_path, uncheckable_rows=[UNCHECKABLE_ROW_1, registered_row])
    _write_mini_profile(
        tmp_path,
        bounds={"B_probe_bound": {"value_ms": 1}},
        limits={"MAX_probe_ceiling": 1},
    )
    _write_d1_test_site(tmp_path, "No bound is named or cited here at all.")
    findings = _run(tmp_path)
    assert "U-6" not in _ids(findings)
    assert "D-1" not in _ids(findings)


def test_d1_profile_universe_load_failure_is_fail_closed_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """profile_key_universe 가 None(형상 불인식)을 반환하면, 프로파일 대조가
    필요했던 사이트는 (제대로 판정했다면 VALUED/BLOCKED 였을 수도 있으므로)
    조용히 UNDECIDED 로 접히지 않고 D-1 자체의 fail-closed violation 이
    돼야 한다 — U-6(§13 등재)로는 구제되지 않는다."""
    monkeypatch.setattr(tcs, "D1_SITES", D1_TEST_SITES)
    write_corpus(tmp_path)
    # bounds 섹션이 없는 프로파일 — profile_key_universe 의 형상 검증에
    # 걸려 None 을 반환해야 한다(fail-closed).
    profile_path = tmp_path / tcs.VERIFICATION_PROFILE_002_REL
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        yaml.safe_dump({"limits": {"MAX_probe": 1}}), encoding="utf-8"
    )
    _write_d1_test_site(tmp_path, "This module consumes ``B_probe_bound``.")

    dispositions, profile_blocked = tcs.compute_d1_dispositions(tmp_path)
    assert dispositions["d1probe"][0] == "UNDECIDED"
    assert "d1probe" in profile_blocked

    findings = _run(tmp_path)
    assert "D-1" in _ids(findings)
    # U-6 은 이 사이트에 대해 별도로 발화하지 않는다 — 실패 사유가 다르다.
    assert not any(f.check_id == "U-6" and "d1probe" in f.message for f in findings)


def test_d1_profile_universe_not_needed_when_unbound_resolves_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UNBOUND 선언으로 즉시 해소되는 사이트는 프로파일이 깨져 있어도
    영향받지 않는다(우주가 애초에 필요 없다)."""
    monkeypatch.setattr(tcs, "D1_SITES", D1_TEST_SITES)
    write_corpus(tmp_path)
    profile_path = tmp_path / tcs.VERIFICATION_PROFILE_002_REL
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(yaml.safe_dump({"limits": {}}), encoding="utf-8")
    _write_d1_test_site(
        tmp_path, "some_field is not a VERIFICATION-PROFILE-002 key at all."
    )

    dispositions, profile_blocked = tcs.compute_d1_dispositions(tmp_path)
    assert dispositions["d1probe"][0] == "UNBOUND"
    assert profile_blocked == ()
    assert "D-1" not in _ids(_run(tmp_path))
