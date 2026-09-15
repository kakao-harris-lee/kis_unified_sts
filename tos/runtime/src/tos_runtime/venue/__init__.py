"""tos_runtime.venue — the Venue Constraint Policy / Order Construction Policy
runtime package (TOS venue constraint service wave, plan §2 decisions 1-3,
7-8; ``docs/plans/2026-09-15-tos-venue-constraint-service-plan.md``).

Three modules, three owners (plan §2 decision 1 "소유 분리" — ownership
split):

* :mod:`tos_runtime.venue.config` — loads the two governance-authored policy
  YAML documents and issues ``VenueConstraintPolicy`` / ``OrderConstructionPolicy``
  through the kernel's own ``.issue()`` constructors. No admissibility
  judgement.
* :mod:`tos_runtime.venue.activation` — an exact-match check against
  ``safety_activation.yaml``'s own ``members:`` list (spg-owned activation
  authority — ADR-002-014 §3.5/§13, ADR-002-019 §5.1 line 111).
* :mod:`tos_runtime.venue.service` — issues ``VenueConstraintSnapshot`` (once
  per tick generation) and ``OrderAdmissibilityDecision`` (once per
  admissibility attempt), with every ``result`` coming exclusively from the
  kernel's own ``tos.egressgw.construction.fold_venue_admissibility``.

Referenced design: ADR-002-019 §5/§8/§14, ADR-002-020 §5.2/§9.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib +
``pyyaml`` + ``tos.*`` + ``tos_runtime.evidence.store`` only — no
``shared.*``, no ``os.environ``, no ``subprocess``, no
``importlib.import_module`` (the firewall scans tests too).
"""

from __future__ import annotations

from tos_runtime.venue.activation import (
    ActivationMembersConfigError,
    PolicyNotActivated,
    load_activation_members,
    require_member_activated,
)
from tos_runtime.venue.config import (
    ORDER_CONSTRUCTION_POLICY_CONFIG_NAME,
    VENUE_POLICY_CONFIG_NAME,
    LoadedOrderConstructionPolicy,
    LoadedVenuePolicy,
    VenuePolicyConfigError,
    VenuePolicyScope,
    load_order_construction_policy,
    load_venue_constraint_policy,
)
from tos_runtime.venue.service import (
    ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND,
    ORDER_CONSTRUCTION_POLICY_BOUND_KIND,
    VENUE_POLICY_BOUND_KIND,
    VENUE_SNAPSHOT_ISSUED_KIND,
    VenueConstraintService,
    record_order_construction_policy_bound,
)

__all__ = [
    # config
    "VENUE_POLICY_CONFIG_NAME",
    "ORDER_CONSTRUCTION_POLICY_CONFIG_NAME",
    "VenuePolicyConfigError",
    "VenuePolicyScope",
    "LoadedVenuePolicy",
    "load_venue_constraint_policy",
    "LoadedOrderConstructionPolicy",
    "load_order_construction_policy",
    # activation
    "ActivationMembersConfigError",
    "PolicyNotActivated",
    "load_activation_members",
    "require_member_activated",
    # service
    "VENUE_POLICY_BOUND_KIND",
    "ORDER_CONSTRUCTION_POLICY_BOUND_KIND",
    "VENUE_SNAPSHOT_ISSUED_KIND",
    "ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND",
    "VenueConstraintService",
    "record_order_construction_policy_bound",
]
