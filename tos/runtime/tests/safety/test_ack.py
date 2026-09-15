"""``tos_runtime.safety.ack`` tests (TOS runtime operations wiring plan
``docs/plans/2026-09-13-tos-runtime-operations-wiring-plan.md`` §2 decision 4).
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import yaml
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.safety.ack import (
    EVIDENCE_KIND_STM_ALERT_ACKNOWLEDGED,
    acknowledge_alert,
)

_ENV_LABEL = "non-live-test"


def _write_ack_file(
    approvals_dir: Path,
    *,
    alert_seq: int,
    principal_id: str = "alice",
    acknowledged_at_label: str = "2026-09-13T10:00 operator shift handover",
    environment_label: str = _ENV_LABEL,
    mode: int = 0o600,
) -> Path:
    path = approvals_dir / "alerts" / f"{alert_seq}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "environment_label": environment_label,
                "principal_id": principal_id,
                "acknowledged_at_label": acknowledged_at_label,
            },
            sort_keys=False,
        )
    )
    os.chmod(path, mode)
    return path


def _append_stm_alert(evidence_store: SqliteEvidenceStore) -> int:
    receipt = evidence_store.append(
        {"identity": "stm", "clear": False, "reasons": ["x"]},
        kind="STM_ALERT",
        record_class="STM_ALERT",
    )
    assert receipt.seq is not None
    return receipt.seq


def _evidence_kinds(evidence_store: SqliteEvidenceStore) -> list[str]:
    rows = evidence_store.connection.execute(
        "SELECT kind FROM entries ORDER BY seq"
    ).fetchall()
    return [row[0] for row in rows]


def _payload_for_kind(evidence_store: SqliteEvidenceStore, kind: str) -> dict:
    row = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq DESC LIMIT 1",
        (kind,),
    ).fetchone()
    assert row is not None
    return json.loads(row[0])["payload"]


# ============================================================================
# Happy path
# ============================================================================


def test_happy_path_acknowledges_a_real_alert_seq(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, expected_owner_uid: int
) -> None:
    seq = _append_stm_alert(evidence_store)
    _write_ack_file(tmp_path / "approvals", alert_seq=seq)

    outcome = acknowledge_alert(
        evidence_store=evidence_store,
        approvals_dir=tmp_path / "approvals",
        alert_seq=seq,
        environment_label=_ENV_LABEL,
        expected_owner_uid=expected_owner_uid,
    )

    assert outcome.acknowledged is True
    assert outcome.evidence_seq is not None
    assert outcome.reason == "ACKNOWLEDGED"
    assert _evidence_kinds(evidence_store) == ["STM_ALERT", "STM_ALERT_ACKNOWLEDGED"]
    payload = _payload_for_kind(evidence_store, EVIDENCE_KIND_STM_ALERT_ACKNOWLEDGED)
    assert payload["alert_seq"] == seq
    assert payload["principal_id"] == "alice"
    assert payload["acknowledged_at_label"]


# ============================================================================
# Missing file
# ============================================================================


def test_missing_ack_file_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, expected_owner_uid: int
) -> None:
    seq = _append_stm_alert(evidence_store)

    outcome = acknowledge_alert(
        evidence_store=evidence_store,
        approvals_dir=tmp_path / "approvals",
        alert_seq=seq,
        environment_label=_ENV_LABEL,
        expected_owner_uid=expected_owner_uid,
    )

    assert outcome.acknowledged is False
    assert outcome.evidence_seq is None
    assert "not found" in outcome.reason
    assert _evidence_kinds(evidence_store) == ["STM_ALERT"]


# ============================================================================
# Wrong mode (0644 instead of 0600)
# ============================================================================


def test_wrong_mode_0644_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, expected_owner_uid: int
) -> None:
    seq = _append_stm_alert(evidence_store)
    _write_ack_file(tmp_path / "approvals", alert_seq=seq, mode=0o644)

    outcome = acknowledge_alert(
        evidence_store=evidence_store,
        approvals_dir=tmp_path / "approvals",
        alert_seq=seq,
        environment_label=_ENV_LABEL,
        expected_owner_uid=expected_owner_uid,
    )

    assert outcome.acknowledged is False
    assert "custody mode/owner gate" in outcome.reason
    assert _evidence_kinds(evidence_store) == ["STM_ALERT"]


# ============================================================================
# Wrong owner uid
# ============================================================================


def test_wrong_owner_uid_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, expected_owner_uid: int
) -> None:
    seq = _append_stm_alert(evidence_store)
    _write_ack_file(tmp_path / "approvals", alert_seq=seq)

    outcome = acknowledge_alert(
        evidence_store=evidence_store,
        approvals_dir=tmp_path / "approvals",
        alert_seq=seq,
        environment_label=_ENV_LABEL,
        expected_owner_uid=expected_owner_uid,
        getuid=lambda: expected_owner_uid + 1,
    )

    assert outcome.acknowledged is False
    assert "custody mode/owner gate" in outcome.reason
    assert _evidence_kinds(evidence_store) == ["STM_ALERT"]


# ============================================================================
# Environment-label mismatch
# ============================================================================


def test_environment_label_mismatch_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, expected_owner_uid: int
) -> None:
    seq = _append_stm_alert(evidence_store)
    _write_ack_file(tmp_path / "approvals", alert_seq=seq, environment_label="paper")

    outcome = acknowledge_alert(
        evidence_store=evidence_store,
        approvals_dir=tmp_path / "approvals",
        alert_seq=seq,
        environment_label=_ENV_LABEL,
        expected_owner_uid=expected_owner_uid,
    )

    assert outcome.acknowledged is False
    assert "environment_label" in outcome.reason
    assert _evidence_kinds(evidence_store) == ["STM_ALERT"]


# ============================================================================
# Target seq is not a real STM_ALERT row (mutation M9's positive-direction pin)
# ============================================================================


def test_seq_not_an_stm_alert_row_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, expected_owner_uid: int
) -> None:
    bogus_seq = 999
    _write_ack_file(tmp_path / "approvals", alert_seq=bogus_seq)

    outcome = acknowledge_alert(
        evidence_store=evidence_store,
        approvals_dir=tmp_path / "approvals",
        alert_seq=bogus_seq,
        environment_label=_ENV_LABEL,
        expected_owner_uid=expected_owner_uid,
    )

    assert outcome.acknowledged is False
    assert "ALERT_SEQ_NOT_FOUND" in outcome.reason
    assert _evidence_kinds(evidence_store) == []


# ============================================================================
# Double-ack is idempotent refusal, never a second row
# ============================================================================


def test_double_acknowledgement_is_idempotent_refusal(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, expected_owner_uid: int
) -> None:
    seq = _append_stm_alert(evidence_store)
    _write_ack_file(tmp_path / "approvals", alert_seq=seq)

    first = acknowledge_alert(
        evidence_store=evidence_store,
        approvals_dir=tmp_path / "approvals",
        alert_seq=seq,
        environment_label=_ENV_LABEL,
        expected_owner_uid=expected_owner_uid,
    )
    second = acknowledge_alert(
        evidence_store=evidence_store,
        approvals_dir=tmp_path / "approvals",
        alert_seq=seq,
        environment_label=_ENV_LABEL,
        expected_owner_uid=expected_owner_uid,
    )

    assert first.acknowledged is True
    assert second.acknowledged is False
    assert "ALREADY_ACKNOWLEDGED" in second.reason
    assert _evidence_kinds(evidence_store) == ["STM_ALERT", "STM_ALERT_ACKNOWLEDGED"]


# ============================================================================
# Mutation M9 — removing the seq-existence check would let a bogus seq
# "succeed". This test proves the current code refuses it (see
# test_seq_not_an_stm_alert_row_is_refused above); this second assertion
# pins that no evidence at all is appended for that refusal, so a mutant
# that deletes _alert_row_exists's call site and falls through to a
# successful append is caught even if the reason-string assertion above is
# weakened.
# ============================================================================


def test_mutation_m9_bogus_seq_never_appends_acknowledged_evidence(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, expected_owner_uid: int
) -> None:
    _append_stm_alert(evidence_store)  # a real STM_ALERT exists, but at a different seq
    bogus_seq = 4242
    _write_ack_file(tmp_path / "approvals", alert_seq=bogus_seq)

    outcome = acknowledge_alert(
        evidence_store=evidence_store,
        approvals_dir=tmp_path / "approvals",
        alert_seq=bogus_seq,
        environment_label=_ENV_LABEL,
        expected_owner_uid=expected_owner_uid,
    )

    assert outcome.acknowledged is False
    assert EVIDENCE_KIND_STM_ALERT_ACKNOWLEDGED not in _evidence_kinds(evidence_store)


# ============================================================================
# Structural pin (mutation M4) — ack.py must never import monitoring/latch/
# rearm/inbox, so an acknowledgement can never reach the mesh clear()/latch/
# re-arm decision through this module.
# ============================================================================

_ACK_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "tos_runtime" / "safety" / "ack.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "tos_runtime.safety.monitoring",
    "tos_runtime.safety.latch",
    "tos_runtime.safety.rearm",
    "tos_runtime.engine.inbox",
)


def _imported_module_names(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
    return names


def test_structural_pin_ack_imports_nothing_from_monitoring_latch_rearm_or_inbox() -> (
    None
):
    """Mutation M4: inserting ``import tos_runtime.safety.monitoring`` (or any of the
    other three forbidden modules) into ``ack.py`` must turn this test red."""
    tree = ast.parse(_ACK_MODULE_PATH.read_text(encoding="utf-8"))
    imported = _imported_module_names(tree)
    offenders = [
        name
        for name in imported
        if any(
            name == forbidden or name.startswith(forbidden + ".")
            for forbidden in _FORBIDDEN_IMPORT_PREFIXES
        )
    ]
    assert offenders == [], (
        "tos_runtime.safety.ack must not import any of "
        f"{_FORBIDDEN_IMPORT_PREFIXES} (ADR-002-028 :159/:187/:388 structural pin) — "
        f"found: {offenders}"
    )


def test_the_import_scan_itself_would_catch_a_real_offending_import(
    tmp_path: Path,
) -> None:
    """Proves the AST scan is not vacuous: a scratch module containing exactly the
    forbidden import IS caught by the same detection logic the pin above uses."""
    scratch = tmp_path / "scratch_offender.py"
    scratch.write_text("import tos_runtime.safety.monitoring\n")
    tree = ast.parse(scratch.read_text(encoding="utf-8"))
    imported = _imported_module_names(tree)
    offenders = [
        name
        for name in imported
        if any(
            name == forbidden or name.startswith(forbidden + ".")
            for forbidden in _FORBIDDEN_IMPORT_PREFIXES
        )
    ]
    assert offenders == ["tos_runtime.safety.monitoring"]


# ============================================================================
# File-not-a-mapping / not-YAML shapes (round out the custody-load path)
# ============================================================================


def test_ack_file_not_a_mapping_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, expected_owner_uid: int
) -> None:
    seq = _append_stm_alert(evidence_store)
    path = tmp_path / "approvals" / "alerts" / f"{seq}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("- just\n- a\n- list\n")
    os.chmod(path, 0o600)

    outcome = acknowledge_alert(
        evidence_store=evidence_store,
        approvals_dir=tmp_path / "approvals",
        alert_seq=seq,
        environment_label=_ENV_LABEL,
        expected_owner_uid=expected_owner_uid,
    )

    assert outcome.acknowledged is False
    assert "must parse to a mapping" in outcome.reason


def test_missing_principal_id_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, expected_owner_uid: int
) -> None:
    seq = _append_stm_alert(evidence_store)
    path = tmp_path / "approvals" / "alerts" / f"{seq}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "environment_label": _ENV_LABEL,
                "acknowledged_at_label": "shift handover",
            }
        )
    )
    os.chmod(path, 0o600)

    outcome = acknowledge_alert(
        evidence_store=evidence_store,
        approvals_dir=tmp_path / "approvals",
        alert_seq=seq,
        environment_label=_ENV_LABEL,
        expected_owner_uid=expected_owner_uid,
    )

    assert outcome.acknowledged is False
    assert "principal_id" in outcome.reason


def test_missing_acknowledged_at_label_is_refused(
    tmp_path: Path, evidence_store: SqliteEvidenceStore, expected_owner_uid: int
) -> None:
    seq = _append_stm_alert(evidence_store)
    path = tmp_path / "approvals" / "alerts" / f"{seq}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "environment_label": _ENV_LABEL,
                "principal_id": "alice",
            }
        )
    )
    os.chmod(path, 0o600)

    outcome = acknowledge_alert(
        evidence_store=evidence_store,
        approvals_dir=tmp_path / "approvals",
        alert_seq=seq,
        environment_label=_ENV_LABEL,
        expected_owner_uid=expected_owner_uid,
    )

    assert outcome.acknowledged is False
    assert "acknowledged_at_label" in outcome.reason
