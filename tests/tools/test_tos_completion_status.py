"""Tests for tools/tos_completion_status.py — Phase-0 D0-A 검사기 증분 C1.

합성 미니 코퍼스는 tmp_path 아래 실제 코퍼스와 동일한 상대 경로 구조로
써지고, ``build_context()`` 가 그 트리를 직접 읽는다 — 모듈 상수를
monkeypatch 하지 않는다(``build_context`` 가 이미 ``repo_root`` 를
인자로 받으므로 필요 없다).
"""

from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

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
    "blocked_by": "",
    "owner_track": "Phase 2-5",
    "exposed_in": "TOS-COMPLETION-STATUS",
    "normative_ref": "",
    "closable": "NO",
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
) -> None:
    """합성 미니 코퍼스를 ``root`` 아래 실제 코퍼스와 같은 상대 경로로 쓴다."""
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
        oq11_text = OQ11_TABLE
    if doc_text is None:
        doc_text = DOC_MD

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

    doc_path = root / "tos-spec" / "src" / "part-1-foundation" / f"{DOC_ID}-Spec.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(doc_text, encoding="utf-8")


def _run(root: Path) -> list:
    ctx = tcs.build_context(root)
    return tcs.run_checks(ctx)


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
