"""``tos_runtime.compose._cli_ops`` — the SECOND sanctioned door onto the storage-layer"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from tos.canonical import CanonicalizationScheme

from tos_runtime.engine.inbox import NewRiskHaltClearOutcome, SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.marketfeed.policy import (
    CRITICAL_INPUT_POLICY_CONFIG_NAME,
    load_critical_input_policy,
)
from tos_runtime.riskstate.policies import (
    ACTION_FLOW_POLICY_CONFIG_NAME,
    AGGREGATE_RISK_POLICY_CONFIG_NAME,
    load_action_flow_policy,
    load_aggregate_risk_policy,
)
from tos_runtime.safety.rearm import prepare_new_risk_halt_clear

__all__ = [
    "RearmCliOutcome",
    "marketfeed_policy_digest_lines",
    "rearm_and_clear",
    "risk_state_policy_digest_lines",
]


def risk_state_policy_digest_lines(
    config_dir: Path, *, scheme: CanonicalizationScheme
) -> tuple[str, ...]:
    """``print-policy-digests``'s own risk-state extension (TOS risk state service wave,"""
    lines: list[str] = []
    are_path = config_dir / AGGREGATE_RISK_POLICY_CONFIG_NAME
    if are_path.is_file():
        loaded_are = load_aggregate_risk_policy(are_path, scheme=scheme)
        lines.append(
            "AGGREGATE_RISK_POLICY "
            f"{loaded_are.policy.policy_id} {loaded_are.policy.policy_generation} "
            f"{loaded_are.policy.canonical_digest}"
        )
    afg_path = config_dir / ACTION_FLOW_POLICY_CONFIG_NAME
    if afg_path.is_file():
        loaded_afg = load_action_flow_policy(afg_path, scheme=scheme)
        lines.append(
            "ACTION_FLOW_POLICY "
            f"{loaded_afg.policy.policy_id} {loaded_afg.policy.policy_generation} "
            f"{loaded_afg.policy.canonical_digest}"
        )
    return tuple(lines)


def marketfeed_policy_digest_lines(
    config_dir: Path, *, scheme: CanonicalizationScheme
) -> tuple[str, ...]:
    """``print-policy-digests``'s own tick-source extension (TOS tick-source wave, lane D;"""
    cip_path = config_dir / CRITICAL_INPUT_POLICY_CONFIG_NAME
    if not cip_path.is_file():
        return ()
    loaded_cip = load_critical_input_policy(cip_path, scheme=scheme)
    return (
        "CRITICAL_INPUT_POLICY "
        f"{loaded_cip.policy_id} {loaded_cip.policy_generation} "
        f"{loaded_cip.canonical_digest}",
    )


_NEW_RISK_HALT_CLEARED_KIND = "NEW_RISK_HALT_CLEARED_BY_OPERATOR"
_NEW_RISK_HALT_CLEAR_REFUSED_KIND = "NEW_RISK_HALT_CLEAR_REFUSED"


@dataclass(frozen=True)
class RearmCliOutcome:
    """The result of one :func:`rearm_and_clear` call."""

    cleared: bool
    outcome: NewRiskHaltClearOutcome | None
    reason: str


def rearm_and_clear(
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    approvals_dir: Path,
    environment_label: str,
    expected_owner_uid: int,
    latched_evidence_seq: int,
) -> RearmCliOutcome:
    """Evaluate the operator re-arm approval for ``latched_evidence_seq`` and, only on"""
    current = inbox.new_risk_halt()
    decision = prepare_new_risk_halt_clear(
        current=current,
        latched_evidence_seq=latched_evidence_seq,
        approvals_dir=approvals_dir,
        evidence_store=evidence_store,
        inbox=inbox,
        environment_label=environment_label,
        expected_owner_uid=expected_owner_uid,
        refused_kind=_NEW_RISK_HALT_CLEAR_REFUSED_KIND,
    )
    if decision.refusal is not None:
        return RearmCliOutcome(
            cleared=False, outcome=None, reason=f"refused: {decision.refusal.value}"
        )

    assert current is not None
    attestation_text = decision.attestation_text
    assert attestation_text is not None
    attestation_sha256 = hashlib.sha256(attestation_text.encode("utf-8")).hexdigest()

    evidence_store.append(
        {
            "latched_evidence_seq": latched_evidence_seq,
            "latched_reason": current.get("reason"),
            "latched_event_id": current.get("event_id"),
            "operator_attestation_sha256": attestation_sha256,
        },
        kind=_NEW_RISK_HALT_CLEARED_KIND,
        record_class=_NEW_RISK_HALT_CLEARED_KIND,
    )
    storage_outcome = inbox.clear_new_risk_halt(
        latched_evidence_seq=latched_evidence_seq,
        operator_attestation=attestation_text,
    )
    if storage_outcome is not NewRiskHaltClearOutcome.CLEARED:
        evidence_store.append(
            {
                "outcome": NewRiskHaltClearOutcome.STORAGE_REFUSED.value,
                "requested_evidence_seq": latched_evidence_seq,
                "current_latched_evidence_seq": current.get("evidence_seq"),
            },
            kind=_NEW_RISK_HALT_CLEAR_REFUSED_KIND,
            record_class=_NEW_RISK_HALT_CLEAR_REFUSED_KIND,
        )
        return RearmCliOutcome(
            cleared=False,
            outcome=NewRiskHaltClearOutcome.STORAGE_REFUSED,
            reason="refused: STORAGE_REFUSED (concurrent relatch TOCTOU window)",
        )
    return RearmCliOutcome(
        cleared=True, outcome=NewRiskHaltClearOutcome.CLEARED, reason="cleared"
    )
