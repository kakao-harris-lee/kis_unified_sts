"""Operator-attested step 6/7 admission witnesses with no Phase 2 producer
(re-review finding F4, 2026-09-08).

``AggregateRiskDecisionInputs``/``ActionFlowDecisionInputs`` (steps 6/7)
each carry several fields their own module docstrings already name as
"Phase-0 / broker-capability-profile concerns this slice does not own":

* ``numerically_safe`` / ``valuation_ok`` — real kernel predicates exist
  (``tos.are.numerical_safety`` / ``valuation_conservative``), but BOTH
  consume their own injected classification witnesses (raw magnitudes/units,
  price-class distinctions, staleness flags, ...) that Phase 2 has no
  producer for either — one level deeper, same gap, not resolved by calling
  the kernel function.
* ``all_fields_attributed`` — a data-lineage/attribution witness
  (``tos.are.predicates.snapshot_scope_complete``'s own docstring: "every
  field carries its source / continuity / observation-time / unit /
  mapping / confidence / lineage") — no Phase 2 service tracks field-level
  data lineage.
* ``limit_source_is_injected_envelope`` — a PROVENANCE claim ("did this
  specific limit value come from the injected envelope, vs. a runtime /
  strategy / human / broker / model source", ``tos.are.predicates.
  envelope_bound_not_enlarged`` / ``tos.afg.predicates.envelope_not_enlarged``).
  Checked and rejected as "derivable via equality": the two occurrences are
  NOT required to be numerically equal to their governing envelope (a
  strategy legitimately requests LESS than the full envelope while still
  sourcing it from the envelope — confirmed against
  ``tos/runtime/tests/compose/_fixtures.py``'s own
  ``action_flow_requested_limit`` (1) vs ``action_flow_envelope_max`` (10),
  a genuine subset, not an equal value) — so a bare equality check would be
  a WRONG derivation (false-negative on every legitimate scaled request),
  not merely an incomplete one. No Phase 2 sizing/allocation service
  exists to attest the real provenance instead.
* ``economic_commitment_exclusive`` / ``flow_commitment_exclusive`` — an
  exclusivity/non-double-booking claim (``tos.afg.predicates.
  atomic_economic_flow_coverage``'s own docstring: "the atomic transaction
  itself is rcl runtime"). A real check would need a durable, agreed
  convention for what an economic/flow commitment's own RCL entry looks
  like so a query could prove no OTHER entry already claims it — no such
  convention exists yet in this Phase 2 slice (unlike IAP's
  ``_consumption_command_id`` prefix, which lane P already built for a
  DIFFERENT artifact). Inventing one here would be a new safety mechanism,
  not a derivation from what already exists, and a half-built one would be
  worse than an honest attestation.

Per team-lead's explicit instruction, these six are supplied from
**composition config as explicit, named operator attestations** — never a
bare Python literal a caller's test-only inputs-provider function invents,
mirroring :mod:`tos_runtime.compose._egress_attestations`'s own mechanism
exactly. ``compose_paper_runtime``'s own ``aggregate_risk_inputs_provider``/
``action_flow_inputs_provider`` callables stay in its signature (the
genuinely scenario-specific fields — cells, cause, snapshot, applicable
scopes, ...) still need a caller — but this module's
``wrap_aggregate_risk_inputs_provider``/``wrap_action_flow_inputs_provider``
ALWAYS override these six fields on whatever the caller's own function
returns, so a caller literal for them is never actually consulted.

**One of the seven fields IS genuinely derivable and is NOT here:**
``generation_current`` (``ActionFlowDecisionInputs`` only). Unlike the six
above, ``tos.afg.state.generation_fenced(artifact_generation,
current_generation)`` is a real, already-shipped structural EQUALITY check
over two concrete generation integers — not a data-provenance/quality
judgement needing domain knowledge this composition lacks. The caller's
own ``decision_generation`` (part of the returned inputs, a genuinely
scenario-specific claim) is the ``artifact_generation`` side;
``current_generation`` is the SAME RCL-log-tip value
:func:`~tos_runtime.compose._wiring._rcl_tip_generation_provider` already
derives for steps 6/9 — so ``wrap_action_flow_inputs_provider`` derives
``generation_current`` structurally, exactly like lane P's
``IntentRegistry.decision_current`` derives IAP decision currency.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml
from tos.afg import generation_fenced
from tos.engine import StageRequest

from tos_runtime.rcl.log import StaleEpochRead
from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs
from tos_runtime.risk.flow import ActionFlowDecisionInputs

__all__ = [
    "RiskAttestationConfigError",
    "RiskAttestations",
    "load_risk_attestations",
    "wrap_aggregate_risk_inputs_provider",
    "wrap_action_flow_inputs_provider",
]

_FIELDS: tuple[str, ...] = (
    "numerically_safe",
    "valuation_ok",
    "all_fields_attributed",
    "limit_source_is_injected_envelope",
    "economic_commitment_exclusive",
    "flow_commitment_exclusive",
)


class RiskAttestationConfigError(Exception):
    """Raised when the risk-attestations config is missing, malformed, or
    carries an unfilled (named-TBD) field — fail-closed at load, never a
    silent default."""


@dataclass(frozen=True)
class RiskAttestations:
    """The six operator-attested step 6/7 admission witnesses (module
    docstring). ``generation_current`` is NOT here — it is derived."""

    numerically_safe: bool
    valuation_ok: bool
    all_fields_attributed: bool
    limit_source_is_injected_envelope: bool
    economic_commitment_exclusive: bool
    flow_commitment_exclusive: bool


def _require_bool(raw: Any, field: str, path: Path) -> bool:
    block = raw.get(field) if isinstance(raw, dict) else None
    if not isinstance(block, dict):
        raise RiskAttestationConfigError(
            f"{path}: risk-attestations config missing a mapping entry "
            f"for {field!r} — refusing to start"
        )
    value = block.get("attested")
    if not isinstance(value, bool):
        raise RiskAttestationConfigError(
            f"{path}: {field!r}.attested is still null (named-TBD) or not a "
            "bool — refusing to start until an operator attests a concrete "
            "value"
        )
    return value


def load_risk_attestations(path: Path) -> RiskAttestations:
    """Load + fail-closed-validate the six operator-attested step 6/7
    admission witnesses from ``path`` (shaped like
    ``tos/runtime/config/risk_attestations.example.yaml``).

    Raises:
        RiskAttestationConfigError: The file is missing/unreadable/not
            valid YAML/not a mapping, an entry is absent, or any field is
            still ``null`` (named-TBD).
    """
    if not path.is_file():
        raise RiskAttestationConfigError(
            f"risk-attestations config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RiskAttestationConfigError(
            f"risk-attestations config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RiskAttestationConfigError(
            f"risk-attestations config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise RiskAttestationConfigError(
            f"risk-attestations config file must be a top-level mapping: {path}"
        )
    values = {field: _require_bool(raw, field, path) for field in _FIELDS}
    return RiskAttestations(**values)


def wrap_aggregate_risk_inputs_provider(
    provider: Callable[[StageRequest], AggregateRiskDecisionInputs | None],
    attestations: RiskAttestations,
) -> Callable[[StageRequest], AggregateRiskDecisionInputs | None]:
    """Wrap a caller-supplied step 6 inputs provider so the four attested
    fields it might return are ALWAYS overridden by ``attestations`` — a
    caller's own literal for them is never actually consulted (module
    docstring)."""

    def _wrapped(request: StageRequest) -> AggregateRiskDecisionInputs | None:
        inputs = provider(request)
        if inputs is None:
            return None
        return replace(
            inputs,
            numerically_safe=attestations.numerically_safe,
            valuation_ok=attestations.valuation_ok,
            all_fields_attributed=attestations.all_fields_attributed,
            limit_source_is_injected_envelope=(
                attestations.limit_source_is_injected_envelope
            ),
        )

    return _wrapped


def wrap_action_flow_inputs_provider(
    provider: Callable[[StageRequest], ActionFlowDecisionInputs | None],
    attestations: RiskAttestations,
    current_generation_provider: Callable[[StageRequest], int],
) -> Callable[[StageRequest], ActionFlowDecisionInputs | None]:
    """Wrap a caller-supplied step 7 inputs provider: three fields are
    ALWAYS overridden by ``attestations`` (module docstring), and
    ``generation_current`` is ALWAYS derived (never attested, never a
    caller literal) via ``tos.afg.generation_fenced`` over the caller's own
    ``decision_generation`` claim and ``current_generation_provider``'s
    real RCL-log-tip value (the SAME provider steps 6/9 use).

    ``current_generation_provider`` is an RCL log read and can raise
    ``StaleEpochRead``/``sqlite3.Error``/``OSError`` — caught here and
    mapped to ``None`` (no inputs available -> UNKNOWN), matching
    :func:`~tos_runtime.compose.context.make_permit_provider`'s own
    treatment of the identical fault (re-review finding F2):
    ``ActionFlowDecisionStage.__call__`` calls this ``inputs_provider`` with
    NO enclosing ``try/except``, unlike step 6's own Stage.
    """

    def _wrapped(request: StageRequest) -> ActionFlowDecisionInputs | None:
        inputs = provider(request)
        if inputs is None:
            return None
        try:
            current_generation = current_generation_provider(request)
        except (StaleEpochRead, sqlite3.Error, OSError):
            return None
        return replace(
            inputs,
            limit_source_is_injected_envelope=(
                attestations.limit_source_is_injected_envelope
            ),
            economic_commitment_exclusive=attestations.economic_commitment_exclusive,
            flow_commitment_exclusive=attestations.flow_commitment_exclusive,
            generation_current=generation_fenced(
                inputs.decision_generation, current_generation
            ),
        )

    return _wrapped
