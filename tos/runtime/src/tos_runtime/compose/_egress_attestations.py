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

**Landed (TOS Phase 5 W3 plan §2 decision 6,
docs/plans/2026-09-11-tos-phase5-w3-safety-mesh-plan.md):**
``restrictive_latch_state`` / ``worst_credible_capacity`` (item 16) are **no
longer attestations** either — they are now supplied by the real runtime
owners :class:`~tos_runtime.safety.latch.RestrictiveLatchOwner` and
:class:`~tos_runtime.safety.latch.CapacityOwner`
(:mod:`tos_runtime.safety.latch`), wired in :mod:`tos_runtime.compose.context`
via :func:`~tos_runtime.safety.latch.egress_owner_fields`. This module refuses
to load a config that still carries either key (below) — a stale operator
config must never silently pretend to attest a value this runtime now derives
on its own, the same discipline the item-6/12 ``_RETIRED_DERIVED_KEYS`` check
already applied.

One ``SendBoundaryContext`` field remains a genuine operator attestation — it
still has **no runtime producer**, exactly like the 17 pending currentness
dimensions (:mod:`tos_runtime.compose._pending_dimensions`):

* ``venue_session_account_facts_current`` (item 12) — no runtime owns a real
  venue/session/account-facts-currency service yet (W5 — Phase 5's venue/
  session calendar owner replaces this operator attestation).

Per team-lead's explicit instruction, this module supplies this field from
**composition config as an explicit, named operator attestation** — never a
kernel-derived judgement and never a bare Python literal standing in for one.
The field is a named-TBD ``null`` in the example config, and a still-null
field refuses composition at startup (the same fail-closed discipline
:mod:`tos_runtime.compose._pending_dimensions` and every other
``tos_runtime.*.config`` loader in this codebase applies).

This mirrors, deliberately, how ``tos/tests/slice/_slice_fixtures.py`` — the
KERNEL's own end-to-end test — supplies this same field as a literal ``True``
constant: that is a legitimate, hand-authored TEST fixture describing "what a
fully-current attempt looks like", never claiming to be a real runtime
derivation. This compose root's PRODUCTION wiring must not silently reuse a
test fixture's literal — an explicit, config-sourced, named operator
attestation makes the same "no runtime producer" gap visible and inspectable
at deploy time instead of buried in source code.

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

__all__ = [
    "EgressAttestationConfigError",
    "EgressAttestations",
    "load_egress_attestations",
]


class EgressAttestationConfigError(Exception):
    """Raised when the egress-attestations config is missing, malformed,
    carries an unfilled (named-TBD) field, or still carries a key that is no
    longer an attestation (module docstring, items 6/12/16) — fail-closed at
    load, never a silent default."""


#: Keys retired from this config across two waves — a config that still
#: carries any of these is refused (module docstring): it could otherwise
#: silently pretend to attest a value this runtime now derives/owns.
#:
#: * ``account_instrument_action_allowed`` / ``broker_constraint_generation_current``
#:   (items 6/12) — TOS Phase 4 plan §2 decision 4 — now STRUCTURALLY DERIVED by
#:   :func:`~tos_runtime.brokercap.derive.derive_item6_item12`.
#: * ``restrictive_latch_state`` / ``worst_credible_capacity`` (item 16) — TOS
#:   Phase 5 W3 plan §2 decision 6 — now supplied by the real runtime owners
#:   :mod:`tos_runtime.safety.latch`.
_RETIRED_DERIVED_KEYS = (
    "account_instrument_action_allowed",
    "broker_constraint_generation_current",
    "restrictive_latch_state",
    "worst_credible_capacity",
)


@dataclass(frozen=True)
class EgressAttestations:
    """The one remaining operator-attested egress-gate stand-in (module
    docstring) — items 6/12/16's other four fields are derived/owned, not
    attested, since TOS Phase 4 plan §2 decision 4 and TOS Phase 5 W3 plan §2
    decision 6."""

    #: Item 12 — no runtime owns venue/session/account-facts currency yet (W5).
    venue_session_account_facts_current: bool


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
    """Load + fail-closed-validate the one remaining operator-attested
    egress-gate stand-in from ``path`` (shaped like
    ``tos/runtime/config/egress_attestations.example.yaml``).

    Raises:
        EgressAttestationConfigError: The file is missing/unreadable/not
            valid YAML/not a mapping, the entry is absent, the field is still
            ``null`` (named-TBD), or the config still carries a retired key
            (module docstring).
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
            "document (TOS Phase 4 plan §2 decision 4,"
            " tos_runtime.brokercap.derive.derive_item6_item12) and item 16's"
            " restrictive_latch_state/worst_credible_capacity are now owned by"
            " tos_runtime.safety.latch (TOS Phase 5 W3 plan §2 decision 6);"
            " remove them from this config"
        )

    venue_session_account_facts_current = _require_bool(
        raw, "venue_session_account_facts_current", path
    )

    return EgressAttestations(
        venue_session_account_facts_current=venue_session_account_facts_current,
    )
