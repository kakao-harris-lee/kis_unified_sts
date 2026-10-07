"""The per-bar Capsule + published value-view seam (how B1a's fields reach the DSL).

Part of the CP-3 B1b runner (``cp3`` package). The runner was one module until the
2026-10-08 review: at 1,820 lines it broke ``config/tos_size_budget.yaml``'s
1,000-line module cap and its 100-line function cap three times over, and
registering four day-one exceptions against a budget whose own header calls
registration "가시성, 면허가 아니라" would have been the wrong answer for NEW code.
So the module was decomposed along the seams it already had, and
``tos/runtime/cp3`` was added to that budget's ``scope`` so the caps are actually
enforced here (the review's fourth gate).

Firewall: ``tos.*`` + ``tos_runtime.*`` + stdlib + ``pyyaml`` only. No
``shared.*``, no clock, no RNG, no ``subprocess``, no network. Intra-package
imports are RELATIVE — the allowlist does not name ``cp3``, so an absolute
``import cp3.…`` from a file under ``tos/`` is a TOS-FW-A violation while a
relative import carries no absolute name for the gate to classify.
"""

from __future__ import annotations

from collections.abc import Mapping

from tos.backtest import Bar
from tos.canonical import EV_L1_PROVISIONAL_VERSION
from tos.capsule._base import PolicyRef
from tos.capsule.capsule import (
    CapsuleScope,
    DecisionContextCapsule,
    SafetyCriticalFacts,
    SnapshotRef,
)
from tos.dsl import ContextValue, ContextValueView
from tos.engine import InstrumentKey
from tos.engine.records import DecisionTickPayload
from tos.marketfeed.value import context_value_view_digest

from . import __version__ as CP3_VERSION
from ._base import SCHEME, Cp3RunnerRefusal
from .contract import FIELD_POLICY, REQUIRED_FIELD_KEYS, FieldRecord

__all__ = [
    "CAPSULE_DECISION_CLASS",
    "CAPSULE_ENVIRONMENT",
    "CRITICAL_INPUT_POLICY_ID",
    "Cp3CapsuleSource",
    "Cp3FieldResolver",
]

# ===========================================================================
# The per-bar Capsule + value-view seam
# ===========================================================================

#: The Capsule's declared environment. Not ``paper`` and not ``live``: this is
#: an out-of-tree clock-free replay, and labelling it ``paper`` would let a
#: paper-scoped consumer mistake the artifact for a paper session's.
CAPSULE_ENVIRONMENT = "non-live-backtest"

#: The Capsule's decision class. The policy gates on ``resolved_values`` only,
#: so this is scope metadata, never a guard operand here.
CAPSULE_DECISION_CLASS = "entry"

#: The Critical Input policy this replay's Capsules name. A ``PolicyRef`` is
#: required-covered content, and naming B1a's producer identity is the honest
#: answer to "which policy admitted these fields" — see the module docstring's
#: declared difference: B1a is the producer, and there is no policy *seam* in
#: the harness to enforce it through.
CRITICAL_INPUT_POLICY_ID = "cp3-b1b-field-policy"


class Cp3CapsuleSource:
    """The injected ``(Bar) -> DecisionContextCapsule`` slot — one Capsule per bar.

    Capsule issuance belongs to the Critical Input pipeline, never to the
    harness (``tos.backtest.converter`` ``CapsuleSource`` docstring). Here the
    "pipeline" is B1a's artifact, so the Capsule is minted from that artifact's
    own per-bar record and nothing else.
    """

    def __init__(
        self,
        *,
        instrument_key: InstrumentKey,
        direction: str,
        records_by_bar_index: Mapping[int, FieldRecord],
    ) -> None:
        """Wire the source.

        Args:
            instrument_key: The dispatch scope; the Capsule's own scope must
                agree with it or the pipeline refuses the tick
                (``pipeline.py`` 204-210행 cross-check).
            direction: The deployment's single direction (``LONG`` here —
                direction is a per-deployment fact, kickoff §2).
            records_by_bar_index: :func:`build_bars`' side table.
        """
        self._instrument_key = instrument_key
        self._direction = direction
        self._records = records_by_bar_index

    def __call__(self, bar: Bar) -> DecisionContextCapsule:
        """Issue the Capsule for ``bar``.

        Raises:
            Cp3RunnerRefusal: No record stands behind ``bar`` — a missing
                Decision Context is a fail-closed stop, never an implied empty
                one.
        """
        record = self._records.get(bar.bar_index)
        if record is None:
            raise Cp3RunnerRefusal(
                f"no field record stands behind bar_index={bar.bar_index} — a "
                "missing Decision Context forbids a decision"
            )
        return DecisionContextCapsule.issue(
            scheme=SCHEME,
            issuer_principal_id=CP3_VERSION,
            critical_input_policy=PolicyRef(
                policy_id=CRITICAL_INPUT_POLICY_ID,
                canonical_digest=SCHEME.compute_digest(
                    {"fields": {key: dict(FIELD_POLICY[key]) for key in FIELD_POLICY}}
                ),
            ),
            critical_input_snapshot=SnapshotRef(
                snapshot_id=record.snapshot_id,
                canonical_digest=record.snapshot_canonical_digest,
            ),
            scope=CapsuleScope(
                environment=CAPSULE_ENVIRONMENT,
                account=self._instrument_key.account,
                instrument=self._instrument_key.instrument,
                decision_class=CAPSULE_DECISION_CLASS,
            ),
            safety_critical_facts=SafetyCriticalFacts(
                account=self._instrument_key.account,
                instrument=self._instrument_key.instrument,
                direction=self._direction,
                quantity_basis="RISK",
                unit="contract",
                # session_and_tradability stays EMPTY on purpose: kickoff §2 ①
                # — `entry_window`/`eod` are strategy gates, not evidence of
                # tradability or session phase (RFC-008 §10; ADR-002-019).
            ),
        )


class Cp3FieldResolver:
    """The injected ``DecisionContextResolver`` that publishes the per-bar value view.

    Replaces :class:`~tos.backtest.ProvisionalContextResolver` at the slot the
    converter already has, which is the forward seam the design named
    ("when D-E2's typed resolver lands it is injected in place of the
    provisional one — the converter's call site does not change",
    ``tos.backtest.resolver`` module docstring).

    The binding round trip is the production one: resolve the Capsule's
    ``SnapshotRef`` through a snapshot store and publish a view **only** when
    ``snapshot_id`` *and* ``canonical_digest`` match exactly
    (``tos.marketfeed.resolver`` 170-192행; ADR-002-018 §15:386 — a silent
    substitution of a more-permissive snapshot is refused). Here the store is
    B1a's artifact, keyed by the snapshot id the capsule source derived.
    """

    #: Mirrors the shipped provisional resolver's own honesty label: nothing on
    #: this path is authoritative and nothing here closes an EV.
    authority_label = "NON_AUTHORITATIVE_PROVISIONAL"

    def __init__(self, *, records_by_snapshot_id: Mapping[str, FieldRecord]) -> None:
        """Wire the resolver with its snapshot store."""
        self._records = records_by_snapshot_id

    def __call__(
        self, capsule: DecisionContextCapsule, *, instrument_key: InstrumentKey
    ) -> DecisionTickPayload:
        """Resolve one Capsule into a value-carrying tick payload.

        Raises:
            Cp3RunnerRefusal: The Capsule's ``SnapshotRef`` names an id this
                store does not hold, or names an id whose digest disagrees.
                Both are fail-closed: publishing no view would silently
                degrade every operand to ``UNKNOWN`` (restrictive, but
                *indistinguishable* from "the policy legitimately saw false"),
                which is exactly the silent-inertness defect
                ``tos_runtime.strategy.resolve`` refuses one layer up.
        """
        ref = capsule.critical_input_snapshot
        record = self._records.get(ref.snapshot_id or "")
        if record is None:
            raise Cp3RunnerRefusal(
                f"capsule {capsule.capsule_id!r} binds snapshot_id "
                f"{ref.snapshot_id!r}, which this replay's snapshot store does "
                "not hold"
            )
        if ref.canonical_digest != record.snapshot_canonical_digest:
            raise Cp3RunnerRefusal(
                f"capsule {capsule.capsule_id!r} binds snapshot_id "
                f"{ref.snapshot_id!r} with canonical_digest "
                f"{ref.canonical_digest!r}, but the stored record digests to "
                f"{record.snapshot_canonical_digest!r} — a view is published "
                "only on an exact binding match"
            )
        # Sorted by ``field_key``, matching the kernel's own preimage ordering
        # (``context_value_view_digest``: "values are ordered by field_key so the
        # digest depends on the value *set*, not on the order a producer happened
        # to emit them in"). Emission order here is B1a's field order, which is a
        # producer accident.
        values = tuple(
            ContextValue(
                field_key=key,
                value=record.fields[key],
                as_of=record.as_of_ms,
                payload_digest=record.snapshot_canonical_digest,
                observation_ref=record.raw_event_id,
            )
            for key in sorted(REQUIRED_FIELD_KEYS)
        )
        view = ContextValueView(
            snapshot_id=record.snapshot_id,
            snapshot_canonical_digest=record.snapshot_canonical_digest,
            values=values,
            # **The kernel's digest, not a local one** (2026-10-08 review item 1).
            # The previous revision hashed ``{"values": [...]}`` in emission
            # order, which left out ``snapshot_id`` / ``snapshot_canonical_digest``
            # and did not sort — so ``view_digest_matches`` was False on EVERY bar
            # (measured: recorded ``a82270de…`` vs canonical ``41faf4ac…``).
            # Nothing rejects a mismatched digest, which is exactly why it
            # mattered: the value flows into
            # ``RecordedInputSignature.captured_external_value_refs`` -> every
            # ``outcome_digest`` -> ``trace_digest``, and ``tos.marketfeed.value``
            # calls a signature built on a non-matching digest "a fiction". The
            # module claimed to "re-author nothing" and to perform "the same round
            # trip tos.marketfeed.resolver performs"; for this one value it did
            # neither. Importing the kernel function makes the claim true.
            canonical_digest=context_value_view_digest(
                snapshot_id=record.snapshot_id,
                snapshot_canonical_digest=record.snapshot_canonical_digest,
                values=values,
                scheme=SCHEME,
            ),
            canonicalization_version=EV_L1_PROVISIONAL_VERSION,
        )
        return DecisionTickPayload(
            instrument_key=instrument_key, capsule=capsule, value_view=view
        )
