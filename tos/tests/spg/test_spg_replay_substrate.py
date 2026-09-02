"""Decision-replay substrate reconstruction (design #12 §5.7; SPG-EV-012 substrate).

The five digest-bound spg citizens (:class:`~tos.spg.HardSafetyEnvelope` /
:class:`~tos.spg.RuntimeSafetyProfile` / :class:`~tos.spg.SafetyConfigurationBundle` /
:class:`~tos.spg.ActivationRecord` / :class:`~tos.spg.ConsumerCompatibilityManifest`) are
frozen, append-only, digest-bound records (design #12 §2.3/§3.1). §21 line 522-533 requires
that durable evidence let independent replay reconstruct every artifact byte + canonical
digest, activation records, predecessor generations, and restrictive ordering, and every
consumer acceptance/denial by exact generation. This module exercises that reconstruction at
the substrate level: the scalar producers (``active_envelope_version`` /
``active_profile_version`` / ``active_envelope_generation`` / ``active_profile_generation`` /
``activation_digest``) that fill replay-evidence scalars (``activation_digest`` fills the
evidence ``safety_configuration_activation_record_digest``, ``evidence/replay.py:113``), the
value-equal / re-wrap-stable reconstruction of a frozen record set's replay coordinates
(versions, generations, digests, the predecessor link, restrictive ordering, and the consumer
compatibility decision), and the structural fact that this replay evidence carries no
authority-granting attribute (SPG-INV-014, §4.5 — evidence is not authority). The replay
ENGINE itself is ADR-002-016 (not-Phase-1); this module authors substrate only and closes no
SPG-EV row.

Regime tag: decision-replay substrate only; SPG-EV-012 substrate; EV-L1-complete claim
forbidden.
"""

from __future__ import annotations

import inspect

import pydantic
import pytest
import tos.spg as spg
from pydantic import ValidationError
from tos.spg import (
    ActivationRecord,
    ConsumerCompatibilityManifest,
    HardSafetyEnvelope,
    RuntimeSafetyProfile,
    SafetyConfigurationBundle,
)

from ._spg_strategies import (
    compat_query,
    issue_activation,
    issue_bundle,
    issue_envelope,
    issue_manifest,
    issue_profile,
)

# ---------------------------------------------------------------------------
# (a) scalar producers — both-ways: None when absent, exact record value otherwise
# ---------------------------------------------------------------------------


def test_active_envelope_version_absent_and_present() -> None:
    """(§5.7, SPG-EV-012) active_envelope_version replays the version string; None when absent."""
    assert spg.active_envelope_version(None) is None
    env = issue_envelope()
    assert spg.active_envelope_version(env) == env.envelope_version.version
    assert spg.active_envelope_version(env) == "e1"


def test_active_profile_version_absent_and_present() -> None:
    """(§5.7, SPG-EV-012) active_profile_version replays the version string; None when absent."""
    assert spg.active_profile_version(None) is None
    prof = issue_profile()
    assert spg.active_profile_version(prof) == prof.profile_version.version
    assert spg.active_profile_version(prof) == "p1"


def test_active_envelope_generation_absent_and_present() -> None:
    """(§5.7, SPG-EV-012) active_envelope_generation replays the integer generation; None when absent."""
    assert spg.active_envelope_generation(None) is None
    env = issue_envelope(envelope_generation=3)
    assert spg.active_envelope_generation(env) == 3


def test_active_profile_generation_absent_and_present() -> None:
    """(§5.7, SPG-EV-012) active_profile_generation replays the integer generation; None when absent."""
    assert spg.active_profile_generation(None) is None
    prof = issue_profile(profile_generation=4)
    assert spg.active_profile_generation(prof) == 4


def test_activation_digest_equals_record_canonical_digest() -> None:
    """(§5.7, SPG-EV-012) activation_digest reproduces the record's canonical digest; None when absent."""
    assert spg.activation_digest(None) is None
    act = issue_activation()
    digest = spg.activation_digest(act)
    assert digest is not None
    # This is the exact scalar that fills evidence
    # ``safety_configuration_activation_record_digest`` (evidence/replay.py:113).
    assert digest == act.canonical_digest


# ---------------------------------------------------------------------------
# (b) frozen-record-set reconstruction — value-equal + re-wrap-stable
# ---------------------------------------------------------------------------


def _replay_coordinates(
    envelope: HardSafetyEnvelope,
    profile: RuntimeSafetyProfile,
    bundle: SafetyConfigurationBundle,
    activation: ActivationRecord,
    manifest: ConsumerCompatibilityManifest,
    query: spg.CompatibilityQuery,
) -> dict[str, object]:
    """Assemble the §21 replay coordinates from a frozen record set (test-local helper).

    Not a spg API — this mirrors, at the test level, the scalar/field reads an independent
    ADR-002-016 replay engine would perform against the substrate this module tests.
    """
    return {
        "envelope_version": spg.active_envelope_version(envelope),
        "profile_version": spg.active_profile_version(profile),
        "envelope_generation": spg.active_envelope_generation(envelope),
        "profile_generation": spg.active_profile_generation(profile),
        "envelope_digest": envelope.canonical_digest,
        "profile_digest": profile.canonical_digest,
        "bundle_digest": bundle.canonical_digest,
        "activation_digest": spg.activation_digest(activation),
        "predecessor_generation": activation.predecessor_generation,
        "restrictive_generation_effects": activation.restrictive_generation_effects,
        "predecessor_link_serializes": spg.activation_serializable(
            activation, activation.predecessor_generation
        ),
        "consumer_decision": spg.compatibility_manifest_matches(manifest, query),
    }


def _frozen_replay_fixture() -> tuple[
    HardSafetyEnvelope,
    RuntimeSafetyProfile,
    SafetyConfigurationBundle,
    ActivationRecord,
    ConsumerCompatibilityManifest,
    spg.CompatibilityQuery,
]:
    env = issue_envelope()
    prof = issue_profile()
    bundle = issue_bundle(envelope=env, profile=prof)
    act = issue_activation(
        envelope_digest=env.canonical_digest,
        profile_digest=prof.canonical_digest,
        bundle_digest=bundle.canonical_digest,
        predecessor_generation=0,
        restrictive_generation_effects=("acct-1:qty:narrowed",),
    )
    manifest = issue_manifest()
    query = compat_query()
    return env, prof, bundle, act, manifest, query


def test_replay_coordinates_reconstruct_value_equal() -> None:
    """(§5.7, SPG-EV-012) Every replay coordinate reconstructs value-equal from the frozen set."""
    env, prof, bundle, act, manifest, query = _frozen_replay_fixture()

    first = _replay_coordinates(env, prof, bundle, act, manifest, query)
    second = _replay_coordinates(env, prof, bundle, act, manifest, query)
    assert first == second

    assert first["envelope_version"] == "e1"
    assert first["profile_version"] == "p1"
    assert first["envelope_generation"] == 1
    assert first["profile_generation"] == 1
    assert first["envelope_digest"] == env.canonical_digest
    assert first["profile_digest"] == prof.canonical_digest
    assert first["bundle_digest"] == bundle.canonical_digest
    assert first["activation_digest"] == act.canonical_digest
    assert first["predecessor_generation"] == 0
    assert first["restrictive_generation_effects"] == ("acct-1:qty:narrowed",)
    # The predecessor-generation link (§15) reconstructs: gen-1 activation serializes
    # against its exact predecessor (gen 0).
    assert first["predecessor_link_serializes"] is True
    # The consumer-compatibility decision (§16) reconstructs: the issued manifest covers
    # the issued query's required schema/field surface.
    assert first["consumer_decision"] is True


def test_replay_coordinates_are_re_wrap_stable() -> None:
    """(§5.7, SPG-EV-012) Re-wrapping/re-instantiating the frozen records does not change the replay coordinates."""
    env, prof, bundle, act, manifest, query = _frozen_replay_fixture()
    before = _replay_coordinates(env, prof, bundle, act, manifest, query)

    # "Re-wrapping/re-serialising" — round-trip each record through model_dump() and
    # rebuild it. A frozen, digest-bound, append-only artifact must reconstruct to the
    # exact same content: the digest-identity validator recomputes and re-checks the
    # digest on every construction (design §4.1), so a silent drift would raise instead
    # of silently reconstructing something different.
    reloaded_env = HardSafetyEnvelope(**env.model_dump())
    reloaded_prof = RuntimeSafetyProfile(**prof.model_dump())
    reloaded_bundle = SafetyConfigurationBundle(**bundle.model_dump())
    reloaded_act = ActivationRecord(**act.model_dump())
    reloaded_manifest = ConsumerCompatibilityManifest(**manifest.model_dump())

    after = _replay_coordinates(
        reloaded_env,
        reloaded_prof,
        reloaded_bundle,
        reloaded_act,
        reloaded_manifest,
        query,
    )
    assert after == before


def test_replay_coordinates_reconstruct_denial_too() -> None:
    """(§5.7, SPG-EV-012) The replay substrate reconstructs a consumer denial exactly as it reconstructs a match."""
    env, prof, bundle, act, manifest, _query = _frozen_replay_fixture()
    # A query asking for a field the manifest never declared — the recorded outcome
    # (deny) must reconstruct identically to how the match outcome reconstructs above.
    unmet_query = compat_query(required_fields=("f1", "f-never-declared"))

    denial = _replay_coordinates(env, prof, bundle, act, manifest, unmet_query)
    assert denial["consumer_decision"] is False

    # A stale-base predecessor (does not equal the candidate's recorded predecessor)
    # reconstructs a non-serializing link, not a silently-permissive one.
    stale_predecessor_link = spg.activation_serializable(
        act, act.predecessor_generation + 1
    )
    assert stale_predecessor_link is False


# ---------------------------------------------------------------------------
# (b, cont.) frozen / append-only — mutation attempts raise
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("predecessor_generation", 99),
        ("restrictive_generation_effects", ("tampered",)),
        ("envelope_digest", "forged-digest"),
        ("activation_id", "act-forged"),
    ],
)
def test_activation_record_replay_fields_reject_mutation(
    field: str, value: object
) -> None:
    """(§5.7, SPG-EV-012) ActivationRecord replay fields (predecessor link, restrictive ordering, digests) are frozen."""
    act = issue_activation()
    with pytest.raises(ValidationError):
        setattr(act, field, value)


# ---------------------------------------------------------------------------
# (c) evidence is not authority (SPG-INV-014, §4.5)
# ---------------------------------------------------------------------------

#: Attribute-name tokens that would betray this replay evidence granting authority.
_AUTHORITY_GRANTING_TOKENS = (
    "authorize",
    "activate",
    "grant",
    "capacity",
    "live_authorization",
    "transmit",
    "commit",
    "arm",
)


def test_activation_record_grants_no_authority() -> None:
    """(§5.7, SPG-EV-012) ActivationRecord, the decision-replay substrate, exposes no authority-granting attribute (SPG-INV-014)."""
    inherited = set(dir(pydantic.BaseModel))
    authored = [
        n for n in dir(ActivationRecord) if not n.startswith("_") and n not in inherited
    ]
    for name in authored:
        for token in _AUTHORITY_GRANTING_TOKENS:
            assert (
                token not in name.lower()
            ), f"ActivationRecord.{name} looks authority-granting"

    # The class's own docstring states the SPG-INV-014 fact this test enforces
    # structurally: replay evidence "grants no Live Authorization by itself" (§5.7 line
    # 135). If that sentence ever moves or is deleted, this assertion fails loudly rather
    # than the check silently passing on an un-anchored token scan.
    doc = inspect.getdoc(ActivationRecord) or ""
    assert "grants no Live Authorization by itself" in doc


def test_activation_digest_is_a_plain_scalar_not_an_authority_object() -> None:
    """(§5.7, SPG-EV-012) activation_digest returns a plain str scalar — never a verdict/authority-bearing object."""
    act = issue_activation()
    digest = spg.activation_digest(act)
    assert type(digest) is str
    assert spg.activation_digest(None) is None
