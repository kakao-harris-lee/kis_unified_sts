"""Operator-attested egress-gate stand-ins (design #40 §5 order 6 items 6/12/16;
team-lead follow-up guidance on the slice #3 review, 2026-09-08).

**Landed (TOS Phase 4 plan §2 decision 4,
docs/plans/2026-09-09-tos-phase4-scopes-and-verify-realization-plan.md):**
``account_instrument_action_allowed`` / ``broker_constraint_generation_current``
(items 6/12) are **no longer attestations** — they are now STRUCTURALLY
DERIVED from the active Broker Scope + (for a broker-reaching scope) the
bound Broker Capability Profile INSTANCE document, via
:func:`~tos_runtime.brokercap.derive.derive_item6_item12` and wired in
:mod:`tos_runtime.compose.context`. This module refuses to load a config that
still carries either key (below) — a stale operator config must never
silently pretend to attest a value this runtime now derives on its own.

Three ``SendBoundaryContext`` fields remain genuine operator attestations —
each still has **no Phase 2 (or Phase 4) runtime producer**, exactly like the
17 pending currentness dimensions (:mod:`tos_runtime.compose._pending_dimensions`):

* ``venue_session_account_facts_current`` (item 12) — no runtime owns a real
  venue/session/account-facts-currency service yet. **Phase 5** replaces this
  operator attestation.
* ``restrictive_latch_state`` / ``worst_credible_capacity`` (item 16) — no
  runtime owns a real local-restrictive-latch service or a real
  worst-credible-capacity computation. **Phase 5** (a real latch/capacity
  -owning runtime service) replaces these operator attestations.

Per team-lead's explicit instruction, this module supplies these three from
**composition config as explicit, named operator attestations** — never a
kernel-derived judgement and never a bare Python literal standing in for one.
Every field is a named-TBD ``null`` in the example config, and a still-null
field refuses composition at startup (the same fail-closed discipline
:mod:`tos_runtime.compose._pending_dimensions` and every other
``tos_runtime.*.config`` loader in this codebase applies).

This mirrors, deliberately, how ``tos/tests/slice/_slice_fixtures.py`` — the
KERNEL's own end-to-end test — supplies these same fields as literal
``True``/``CLEAR``/``1`` constants: that is a legitimate, hand-authored TEST
fixture describing "what a fully-current attempt looks like", never claiming
to be a real runtime derivation. This compose root's PRODUCTION wiring must
not silently reuse a test fixture's literal — an explicit, config-sourced,
named operator attestation makes the same "no runtime producer" gap visible
and inspectable at deploy time instead of buried in source code.

``max_quantity_within_allowance`` (also an item-6 field) is NOT part of this
module: it DOES have a genuine Phase 2 producer — step 2's own
``CandidateConstruction.no_silent_widening_ok`` — and stays wired directly
from that in :mod:`tos_runtime.compose.context` (never routed through an
operator attestation when a real derivation exists).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.egress import RestrictiveLatchState

__all__ = [
    "EgressAttestationConfigError",
    "EgressAttestations",
    "load_egress_attestations",
]


class EgressAttestationConfigError(Exception):
    """Raised when the egress-attestations config is missing, malformed,
    carries an unfilled (named-TBD) field, or still carries a key that is no
    longer an attestation (module docstring, items 6/12) — fail-closed at
    load, never a silent default."""


#: Item 6/12 keys retired by TOS Phase 4 plan §2 decision 4 — now derived by
#: :func:`~tos_runtime.brokercap.derive.derive_item6_item12`, never attested.
#: A config that still carries either is refused (module docstring): it
#: could otherwise silently pretend to attest a value this runtime derives.
_RETIRED_DERIVED_KEYS = (
    "account_instrument_action_allowed",
    "broker_constraint_generation_current",
)


@dataclass(frozen=True)
class EgressAttestations:
    """The three remaining operator-attested egress-gate stand-ins (module
    docstring) — items 6/12's other two fields are derived, not attested,
    since TOS Phase 4 plan §2 decision 4."""

    #: Item 12 — no runtime owns venue/session/account-facts currency yet (Phase 5).
    venue_session_account_facts_current: bool
    #: Item 16 — the local restrictive deny-latch (``tos.egress.RestrictiveLatchState``,
    #: Phase 5).
    restrictive_latch_state: RestrictiveLatchState
    #: Item 16 — the worst-credible-capacity bound (Phase 5).
    worst_credible_capacity: int


def _require_bool(raw: Any, field: str, path: Path) -> bool:
    block = raw.get(field) if isinstance(raw, dict) else None
    if not isinstance(block, dict):
        raise EgressAttestationConfigError(
            f"{path}: egress-attestations config missing a mapping entry "
            f"for {field!r} — refusing to start"
        )
    value = block.get("attested")
    if not isinstance(value, bool):
        raise EgressAttestationConfigError(
            f"{path}: {field!r}.attested is still null (named-TBD) or not a "
            "bool — refusing to start until an operator attests a concrete "
            "value"
        )
    return value


def load_egress_attestations(path: Path) -> EgressAttestations:
    """Load + fail-closed-validate the five operator-attested egress-gate
    stand-ins from ``path`` (shaped like
    ``tos/runtime/config/egress_attestations.example.yaml``).

    Raises:
        EgressAttestationConfigError: The file is missing/unreadable/not
            valid YAML/not a mapping, an entry is absent, or any field is
            still ``null`` (named-TBD).
    """
    if not path.is_file():
        raise EgressAttestationConfigError(
            f"egress-attestations config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EgressAttestationConfigError(
            f"egress-attestations config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise EgressAttestationConfigError(
            f"egress-attestations config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise EgressAttestationConfigError(
            f"egress-attestations config file must be a top-level mapping: {path}"
        )
    stale = [key for key in _RETIRED_DERIVED_KEYS if key in raw]
    if stale:
        raise EgressAttestationConfigError(
            f"{path}: {stale!r} are no longer attestations — items 6/12 are "
            "structurally derived from the active Broker Scope + INSTANCE "
            "document since TOS Phase 4 plan §2 decision 4 "
            "(tos_runtime.brokercap.derive.derive_item6_item12); remove them "
            "from this config"
        )

    venue_session_account_facts_current = _require_bool(
        raw, "venue_session_account_facts_current", path
    )

    latch_block = raw.get("restrictive_latch_state")
    if not isinstance(latch_block, dict) or not isinstance(
        latch_block.get("clear"), bool
    ):
        raise EgressAttestationConfigError(
            f"{path}: 'restrictive_latch_state.clear' is still null "
            "(named-TBD) or not a bool — refusing to start"
        )
    restrictive_latch_state = (
        RestrictiveLatchState.CLEAR
        if latch_block["clear"]
        else RestrictiveLatchState.DENY_LATCHED
    )

    capacity_block = raw.get("worst_credible_capacity")
    capacity_value = (
        capacity_block.get("value") if isinstance(capacity_block, dict) else None
    )
    if isinstance(capacity_value, bool) or not isinstance(capacity_value, int):
        raise EgressAttestationConfigError(
            f"{path}: 'worst_credible_capacity.value' is still null "
            "(named-TBD) or not an int — refusing to start"
        )

    return EgressAttestations(
        venue_session_account_facts_current=venue_session_account_facts_current,
        restrictive_latch_state=restrictive_latch_state,
        worst_credible_capacity=capacity_value,
    )
