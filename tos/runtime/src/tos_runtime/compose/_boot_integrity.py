"""``tos_runtime.compose`` boot-time integrity helpers — split out of
``_wiring.py`` purely for the size budget (tools/tos_size_budget.py file-
level limit); no behavioural difference from having them inline there.
:func:`~tos_runtime.compose._wiring._boot_services` calls both, right after
the RCL log / risk-and-currentness phases build (design #40 §5 order 3-6).
"""

from __future__ import annotations

import hashlib
from dataclasses import fields
from pathlib import Path

from tos.workload import RuntimeIdentity

from tos_runtime.compose._egress_attestations import EgressAttestations
from tos_runtime.compose._egress_coordinates import EgressCoordinatesConfig
from tos_runtime.compose._risk_attestations import RiskAttestations
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import CommitLogCorruption, SqliteCommitLog

__all__ = [
    "EGRESS_ATTESTATIONS_CONFIG_NAME",
    "RISK_ATTESTATIONS_CONFIG_NAME",
    "EGRESS_COORDINATES_CONFIG_NAME",
    "verify_rcl_log_or_halt",
    "record_operator_attested_inputs",
]

EGRESS_ATTESTATIONS_CONFIG_NAME = "egress_attestations.yaml"
RISK_ATTESTATIONS_CONFIG_NAME = "risk_attestations.yaml"
#: Same config file name ``_wiring.py``/``_egress_coordinates.py`` use for
#: the egress-coordinates config (TOS Phase 4 작업 6 §2.1).
EGRESS_COORDINATES_CONFIG_NAME = "egress_coordinates.yaml"

#: The evidence kind/record class for the operator-attested-inputs
#: provenance record (re-review finding F4, 2026-09-08).
_ATTESTED_INPUTS_EVIDENCE_KIND = "OPERATOR_ATTESTED_INPUTS"


def verify_rcl_log_or_halt(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    identity: RuntimeIdentity,
) -> None:
    """Independently re-verify the RCL log's own replay at boot, before any
    Stage is wired (re-review finding F1, 2026-09-08): compose must never
    hand back a runtime over a corrupt log. On
    :class:`~tos_runtime.rcl.log.CommitLogCorruption`, durably records one
    ``RCL_CORRUPTION_ALERT`` (both evidence paths, via
    :func:`~tos_runtime.evidence.emergency.record_halt`) before re-raising
    — never a silent halt, never a swallowed exception."""
    try:
        rcl_log.verify_replay()
    except CommitLogCorruption as exc:
        record_halt(
            evidence_store,
            emergency_log,
            payload={"detail": str(exc)},
            kind="RCL_CORRUPTION_ALERT",
            record_class="RCL_CORRUPTION_ALERT",
            runtime_identity=identity,
        )
        raise


def record_operator_attested_inputs(
    config_dir: Path,
    evidence_store: SqliteEvidenceStore,
    identity: RuntimeIdentity,
    egress_attestations: EgressAttestations,
    risk_attestations: RiskAttestations,
    egress_coordinates: EgressCoordinatesConfig,
) -> None:
    """Durably record ONE evidence entry enumerating every config-attested
    coordinate name (items 6/12/16 + the step 6/7 admission witnesses + the
    egress-coordinate/capsule-terminus-stand-in inputs, TOS Phase 4 작업 6
    §2.1) and its source config file's own digest — re-review reviewer Q3,
    F4 (2026-09-08): "the five egress attestations enter SendBoundaryContext
    as bare kernel-typed fields, identical in shape to derived verdicts".
    This record is what lets an auditor tell attested from derived
    downstream — the field VALUES themselves carry no marker of their own
    origin, so the origin is instead evidenced once, here, at boot.

    Never re-derives ``config_dir``'s file names independently elsewhere —
    this is the ONE place that reads all three attestation/coordinate config
    files' raw bytes for digesting, kept next to where the rest of boot
    already reads them (``_wiring._boot_services``).
    """
    coordinates: list[dict[str, str]] = []
    for path, prefix, dataclass_type in (
        (
            config_dir / EGRESS_ATTESTATIONS_CONFIG_NAME,
            EGRESS_ATTESTATIONS_CONFIG_NAME,
            type(egress_attestations),
        ),
        (
            config_dir / RISK_ATTESTATIONS_CONFIG_NAME,
            RISK_ATTESTATIONS_CONFIG_NAME,
            type(risk_attestations),
        ),
        (
            config_dir / EGRESS_COORDINATES_CONFIG_NAME,
            EGRESS_COORDINATES_CONFIG_NAME,
            type(egress_coordinates),
        ),
    ):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        for field in fields(dataclass_type):
            coordinates.append(
                {
                    "name": field.name,
                    "source_file": prefix,
                    "source_file_digest": digest,
                }
            )
    evidence_store.append(
        {"attested_coordinates": coordinates},
        kind=_ATTESTED_INPUTS_EVIDENCE_KIND,
        record_class=_ATTESTED_INPUTS_EVIDENCE_KIND,
        runtime_identity=identity,
    )
