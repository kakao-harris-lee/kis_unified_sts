"""Shared hypothesis strategies + valid-artifact builders for the property tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.capsule.*`` (design §0.3).

The ``*_required_kwargs`` / ``issue_*`` builders populate the safety-load-bearing
covered fields the issuance guard now demands (design §3.2). Tests MUST build
artifacts through these so a "valid" fixture is genuinely valid — issuing with
all-null covered content is exactly the coverage illusion the review flagged.
"""

from __future__ import annotations

from typing import Any

import hypothesis.strategies as st
from tos.capsule import CriticalInputSnapshot, DecisionContextCapsule, get_scheme
from tos.capsule._base import PolicyRef
from tos.capsule.canonicalization import EV_L1_PROVISIONAL_VERSION
from tos.capsule.capsule import CapsuleScope, SafetyCriticalFacts, SnapshotRef
from tos.capsule.consistency_cut import ConsistencyCut, SourceContinuityVectorEntry
from tos.capsule.field_state import FieldState
from tos.capsule.lineage import ParentRef, Stochastic, TransformationLineage
from tos.capsule.snapshot import CorroborationPath, SnapshotScope

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: A consistency cut that passes ``cut_compatible`` (atomic, VALID, no gap).
COMPATIBLE_CUT = ConsistencyCut(
    cut_id="cut-ok",
    source_continuity_vector=(SourceContinuityVectorEntry(source_continuity_id="s1"),),
    atomicity_proven=True,
    uncertainty=FieldState.VALID,
)

# ---------------------------------------------------------------------------
# Primitive strategies
# ---------------------------------------------------------------------------

ASCII = st.characters(min_codepoint=32, max_codepoint=126)
TEXT = st.text(alphabet=ASCII, max_size=6)
OPT_TEXT = st.none() | TEXT
FIELD_STATES = st.sampled_from(list(FieldState))

# Canon-safe (no numbers) value tree: exercises determinism / key-order /
# injectivity without the intended magnitude fold (design §3.4 (A) vs (B)).
_canon_scalars = st.none() | st.booleans() | TEXT
CANON_VALUES = st.recursive(
    _canon_scalars,
    lambda children: (
        st.lists(children, max_size=4)
        | st.dictionaries(
            st.text(alphabet=ASCII, min_size=1, max_size=4), children, max_size=4
        )
    ),
    max_leaves=12,
)
CANON_DICTS = st.dictionaries(
    st.text(alphabet=ASCII, min_size=1, max_size=5), CANON_VALUES, max_size=5
)

# Mixed string + integer (no bool/float/None) domain for injectivity (MINOR-5):
# on this domain Python equality coincides with canonical equality — no magnitude
# fold (no floats) and no ``True == 1`` / ``1.0 == 1`` cross-type quirk.
_mixed_scalars = st.integers(min_value=-1000, max_value=1000) | TEXT
MIXED_VALUES = st.recursive(
    _mixed_scalars,
    lambda children: (
        st.lists(children, max_size=4)
        | st.dictionaries(
            st.text(alphabet=ASCII, min_size=1, max_size=4), children, max_size=4
        )
    ),
    max_leaves=12,
)
MIXED_DICTS = st.dictionaries(
    st.text(alphabet=ASCII, min_size=1, max_size=5), MIXED_VALUES, max_size=5
)


# ---------------------------------------------------------------------------
# Model strategies
# ---------------------------------------------------------------------------


@st.composite
def lineages(draw: st.DrawFn) -> TransformationLineage:
    """A varied :class:`TransformationLineage` for reproducibility properties."""
    n_parents = draw(st.integers(min_value=0, max_value=3))
    parents = tuple(
        ParentRef(parent_id=draw(OPT_TEXT), digest=draw(OPT_TEXT))
        for _ in range(n_parents)
    )
    return TransformationLineage(
        output_id=draw(OPT_TEXT),
        parents=parents,
        stochastic=Stochastic(
            is_stochastic=draw(st.booleans()),
            random_seed=draw(OPT_TEXT),
            nondeterminism_declaration=draw(OPT_TEXT),
        ),
        reproducible=draw(st.booleans()),
        field_state=draw(FIELD_STATES),
    )


def corroboration_path(path_id: str, tags: tuple[str, ...]) -> CorroborationPath:
    """Build a :class:`CorroborationPath` with explicit tags (common-mode tests)."""
    return CorroborationPath(path_id=path_id, tags=tags)


# ---------------------------------------------------------------------------
# Valid-artifact builders (populate the required safety-load-bearing covered set)
# ---------------------------------------------------------------------------


def capsule_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Return capsule issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "issuer_principal_id": "iss-1",
        "critical_input_policy": PolicyRef(policy_id="pol-1", canonical_digest="pd-1"),
        "critical_input_snapshot": SnapshotRef(
            snapshot_id="cis-ref", canonical_digest="sd-1"
        ),
        "scope": CapsuleScope(
            environment="paper",
            account="acct-1",
            instrument="ES",
            decision_class="entry",
        ),
        "safety_critical_facts": SafetyCriticalFacts(
            account="acct-1",
            instrument="ES",
            direction="long",
            quantity_basis="contracts",
            unit="contract",
        ),
    }
    base.update(overrides)
    return base


def snapshot_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Return snapshot issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "issuer_principal_id": "iss-1",
        "critical_input_policy": PolicyRef(policy_id="pol-1", canonical_digest="pd-1"),
        "scope": SnapshotScope(environment="paper", decision_class="entry"),
        "intended_use": "decide-entry",
        "consistency_cut": ConsistencyCut(cut_id="cut-1"),
    }
    base.update(overrides)
    return base


def issue_capsule(**overrides: Any) -> DecisionContextCapsule:
    """Issue a valid :class:`DecisionContextCapsule` (required fields populated)."""
    return DecisionContextCapsule.issue(
        scheme=SCHEME, **capsule_required_kwargs(**overrides)
    )


def issue_snapshot(**overrides: Any) -> CriticalInputSnapshot:
    """Issue a valid :class:`CriticalInputSnapshot` (required fields populated)."""
    return CriticalInputSnapshot.issue(
        scheme=SCHEME, **snapshot_required_kwargs(**overrides)
    )
