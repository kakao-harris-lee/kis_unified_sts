"""tos.marketfeed — market data → admitted Critical Input value surface (design #32, D-E2).

Realizes the ratified project-side design contract
``docs/plans/2026-07-29-tos-marketfeed-design.md`` (#32, D-E2, v1.1, operator-delegated
auto-ratification 2026-07-29) — the vertical slice's **data supply layer**. It owns the contract by
which a market number reaches a strategy: as an *admitted, attributed Critical Input* (RFC-004 §9;
RFC-008 §9/§10; ADR-002-018 §9/§10/§11/§14/§15), never relabelled as configuration.

⚠ **The name is narrower than it sounds.** ``feed`` here does **not** mean a network transport. This
package opens no socket, subscribes to nothing, and holds no credential: it *receives* already
admitted observations by injection and produces a verified value surface from them. That is the
structural form of RFC-004 §9:242-244 — "never by unattributed fetch or side channel" — and it is
enforced two ways: the import-closure canary (no ``socket`` / ``urllib`` / ``os.environ`` /
``importlib`` anywhere in the sources) and the record-level fetch-surface seal in
:mod:`tos.marketfeed._base`. Real transport is D-E4's, upstream of this package's inputs.

**The problem it solves.** ``tos.capsule``'s ``Observation`` is a provenance record with **no**
numeric leaf: ADR-002-018 §9:249-261 binds raw event identity, payload digest, and
unit/scale/multiplier/sign metadata — never the observed magnitude itself. The value lives behind
the covered ``raw.payload_digest``. Before this package the only channel that actually reached a
policy was ``config.bindings``, and routing a market value through it is precisely the relabelling
RFC-008 §10:327-331 and RFC-004 §9:251-252 prohibit. D-E2 replaces that channel with one whose every
value is bound to a covered digest.

**Ownership split** (design #32 §2.2 F1). The env-value **shape** — :class:`~tos.dsl.ContextValue` /
:class:`~tos.dsl.ContextValueView` — lives in ``tos.dsl``, because ``tos.dsl`` owns the environment
the interpreter walks and because a ``tos.marketfeed`` type on
``tos.engine.DecisionTickPayload.value_view`` would breach the committed engine import-closure
allowlist and create an ``engine -> marketfeed -> engine`` cycle. ``tos.marketfeed`` owns
**production and verification**. Edges run one way only: marketfeed → {dsl, capsule, canonical,
engine}; nothing imports marketfeed.

**What the gates seal.**

* *side channel* — a value must digest back to the observation's covered ``payload_digest``
  (§2.3), so it cannot be conjured;
* *per-bar distinctness* — a value carries the observation's covered ``source_event_time``, and
  observations are a covered snapshot field, so distinct bars yield distinct snapshot digests →
  distinct Capsule digests → distinct outcome identities (§4, the D-E1 Gap-1 residue);
* *vacuous validity* — the VALID gate takes ``worst`` over three sources with an explicit
  ``UNKNOWN`` floor when no field evaluation names the key, so an unevaluated field cannot pass
  (§2.2);
* *silent numeric coercion* — integer minor/tick units are the exposed numeric form; a ``Decimal``
  is refused outright and the fractional path is fail-closed until the deterministic-float rule is
  ratified (§2.5);
* *disagreement* — a repeated ``field_key`` is refused wholesale, never averaged or majority-voted
  (§6);
* *reproducibility of the signature* — the view's canonical digest joins
  ``RecordedInputSignature.captured_external_value_refs``, so two runs differing only in their
  values differ in their recorded signature (§3.2 (3b)).

⚠ **Provisional; closes no EV** (design #32 §1.1). Three independent reasons: (a) production
canonicalization is unresolved — every digest here rides ``ev-l1-provisional-0``; (b) this
package carries **no VERIFICATION-PROFILE-002 bound of its own** — grep of ``tos/src/tos/marketfeed``
finds no ``MAX_``/``MIN_``/``B_`` profile-key reference at all; the time coordinates it forwards
come from an externally injected ``TimeCoordinateProjection`` (``resolver.py``) wired by its
D-E3/D-E4 caller, not held here. Independent-reviewer designation (P0-3) is a register concern
(``EVIDENCE-REGISTER-DEV.csv``), not a profile key, and no evidence-register row is scoped to
``tos.marketfeed`` to check it against; (c) this is a *model plus
properties*, not the Context Integrity Service runtime that collects, assembles, and issues
snapshots — that runtime is explicitly out of scope (design #2 §0.2), and this package only
**consumes** its output — **through the admitted-snapshot injection port** (``SnapshotStore`` +
``ValueCandidateSource``), the D-E2 consumption boundary of that upstream output (design #38). The
property tests are authoring evidence, not acceptance.

⚠ **Trust seams, named** (design #32 §2.3/§4.3/§5.4). The value ⟺ digest check runs at publication;
the environment-injection point does not repeat it. Look-ahead is checked against what the lineage
*records*. Distinctness assumes a producer that stamps distinct bars with distinct as-of times.
Each of those is a producer-honesty boundary this layer detects rather than enforces, and none of
them is claimed as closed.

Public surface groups by module:

* :mod:`tos.marketfeed.vocabulary` — the closed disposition / rejection-reason vocabulary.
* :mod:`tos.marketfeed.records` — the producer-side candidate records + the resolution report.
* :mod:`tos.marketfeed.value` — the pure gates and the ``ContextValueView`` producer (no engine).
* :mod:`tos.marketfeed.resolver` — the concrete ``DecisionContextResolver`` (the engine edge).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #1 §3.2). No ``shared.*`` operational
package, no ``os.environ``, no network stdlib, no ``importlib`` / ``exec`` / ``eval`` / ``compile``,
no ``numpy`` / ``pandas``, no clock, no RNG.
"""

from __future__ import annotations

from tos.marketfeed._base import (
    FETCH_SURFACE_TOKENS,
    CanonicalizationScheme,
    FrozenModel,
    MarketFeedIntegrityError,
    fetch_surface_offenders,
    get_scheme,
    seal_fetch_surface,
)
from tos.marketfeed.records import (
    AdmittedValue,
    PreimageEntry,
    RawPayloadPreimage,
    RejectedValue,
    ValueResolution,
)
from tos.marketfeed.resolver import (
    MarketFeedContextResolver,
    ResolvedTick,
    SnapshotStore,
    TimeCoordinateProjection,
    ValueCandidateSource,
)
from tos.marketfeed.value import (
    capsule_top_level_keys,
    context_value_view_digest,
    index_observations,
    lineage_state_for_output,
    project_scalar,
    publish_context_value_view,
    snapshot_binds_capsule_reference,
    value_field_state,
    value_namespace_is_disjoint,
    view_digest_matches,
)
from tos.marketfeed.vocabulary import (
    ADMITTING_DISPOSITIONS,
    ValueRejectionReason,
    ValueViewDisposition,
)

__all__ = [
    # base
    "FETCH_SURFACE_TOKENS",
    "CanonicalizationScheme",
    "FrozenModel",
    "MarketFeedIntegrityError",
    "fetch_surface_offenders",
    "get_scheme",
    "seal_fetch_surface",
    # vocabulary
    "ADMITTING_DISPOSITIONS",
    "ValueRejectionReason",
    "ValueViewDisposition",
    # records
    "AdmittedValue",
    "PreimageEntry",
    "RawPayloadPreimage",
    "RejectedValue",
    "ValueResolution",
    # value production / verification
    "capsule_top_level_keys",
    "context_value_view_digest",
    "index_observations",
    "lineage_state_for_output",
    "project_scalar",
    "publish_context_value_view",
    "snapshot_binds_capsule_reference",
    "value_field_state",
    "value_namespace_is_disjoint",
    "view_digest_matches",
    # resolver (the tos.engine edge)
    "MarketFeedContextResolver",
    "ResolvedTick",
    "SnapshotStore",
    "TimeCoordinateProjection",
    "ValueCandidateSource",
]
