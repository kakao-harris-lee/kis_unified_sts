"""``tos_runtime.authority`` — Safety Authority epoch service + Independent
Approval / Intent Registry runtime (design #40 §5 order 4; slice plan §1).

The runtime never judges: every service here collects inputs (RCL log state,
Trustworthy Time snapshots, operator-authored approval files) and calls the
kernel's own conservative, fail-closed predicates
(``tos.authority``/``tos.iap``). See each module's own docstring for its
specific contract and the two reported ``CommandType`` vocabulary gaps
(:mod:`tos_runtime.authority.epoch`, :mod:`tos_runtime.authority.iap`).

Cross-lane isolation (slice plan §5): this package imports nothing from
``tos_runtime.currentness`` / ``tos_runtime.risk`` / ``tos_runtime.release``
(the sibling lanes of this same design #40 §5 sequence) — any cross-input a
future composition root needs is received here as an injected callable/
Protocol argument, never an import edge onto those packages.
"""

from __future__ import annotations

from tos_runtime.authority.capability import capability_valid
from tos_runtime.authority.epoch import (
    AuthorityEpochTransitionRefused,
    AuthorityRuntimeConfig,
    SafetyAuthorityEpochService,
    load_authority_config,
)
from tos_runtime.authority.iap import (
    ConsumeResult,
    IntentRegistry,
    OperatorApprovalFileError,
    load_operator_approval_file,
)
from tos_runtime.authority.stages import IndependentApprovalStage, item14_fields

__all__ = [
    "AuthorityEpochTransitionRefused",
    "AuthorityRuntimeConfig",
    "ConsumeResult",
    "IndependentApprovalStage",
    "IntentRegistry",
    "OperatorApprovalFileError",
    "SafetyAuthorityEpochService",
    "capability_valid",
    "item14_fields",
    "load_authority_config",
    "load_operator_approval_file",
]
