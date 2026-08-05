"""§4 (design #38) — the admitted-snapshot injection port: its surface, its requirement, its seal.

Design #38 creates no runtime type. :class:`~tos.marketfeed.SnapshotStore` and
:class:`~tos.marketfeed.ValueCandidateSource` were shipped by design #32, a fake CIS already drives
the real resolver (``tos/tests/slice/_slice_fixtures.py:335-422``), and the exclusivity *behaviour*
is already committed (``test_slice_conformant_path.py:233-257``). None of that is re-authored here.
What was **not** locked is the port's own shape, and that is the whole of this file (design #38
§11-1 (ii)):

* **P1 — the Protocol surface itself.** Adding ``session_token=`` to ``SnapshotStore.__call__``
  breaks no committed canary today: the record-level fetch-surface seal reads pydantic
  ``model_fields``, the namespace sweep reads ``vars()``, and the import-closure canary reads
  imports — a Protocol parameter is the target of none of them. So the call-only shape, the exact
  parameter sets, the ambient-name exclusion, and the closure "exactly two CIS injections" are
  locked here. D-E4's ``test_brokeradapter_transport.py:69-96`` is the isomorph.
* **P2 / P5 — required injection.** Before this file the marketfeed suite used ``inspect`` nowhere,
  so "a resolver cannot be built without a CIS-issued source" was a structural fact that nothing
  read. One predicate reads it, and the three ways to bypass it — moved out of ``__init__``, made
  positional, given a default — are run against that same predicate and must all be caught.
* **P3 — the over-claim seal.** Nothing stopped a later edit from writing "this layer fully enforces
  distinctness" into a marketfeed docstring. The rule is **co-occurrence**, not bare substring: an
  over-claim stem is admitted only when its own sentence also carries an upstream/negation anchor.
  So the shipped honest sentence — "the environment-injection point does **not** re-verify it" —
  passes, and an unqualified planted claim does not.
* **P4 — the gates, restated at the port boundary.** The four publication gates are asserted
  through a fake CIS pair rather than against the gate function, which is the form of
  "the most a dishonest source achieves is a rejection record" (``resolver.py:89``).

**Where the P3 seal stops, stated rather than implied.** Two boundaries, both inherited from the
ratified contract rather than chosen here:

* **Scope.** The sweep reads module docstrings plus the public classes and functions each module
  *owns* — 31 surfaces — because that is the scope design #38 §4-P3 declares and its v1.2 Open
  Question ④ fixed. **Method docstrings are outside it**: 24 of them (callables carrying a
  docstring in those classes' own ``__dict__``), so an over-claim planted in
  ``MarketFeedContextResolver.resolve``'s docstring would pass this seal. Widening the sweep is a
  follow-on candidate, not a silent extension of a ratified scope.
* **Sensitivity.** The absence rule exempts a stem as soon as an anchor appears **anywhere in the
  same sentence**, and ``"not "`` is one of the anchors ratified §4-P3.2 names — so
  "this layer fully enforces distinctness, which is not obvious" would pass. P3 is therefore a
  **tripwire for an accidental over-claim edit**, not a proof that no over-claim can be written. A
  determined author can still write one; that residue belongs to review, not to this canary.

**What this file does not claim.** The port does not make the upstream producer honest (design #38
§3.3). A producer that stamps two bars with one as-of still collapses the chain, and the test below
asserts that collapse as a *limit* rather than pretending the gate catches it — complete enforcement
of per-bar distinctness is upstream, in the Context Integrity Service. A fabricated-but-plausible
lineage is not tested at all: from this layer's inputs a forged self-consistent lineage is
byte-indistinguishable from a true one, so no discriminator exists and inventing one would be the
over-claim this file seals against (design #38 §4.2 N2).

Regime tag: authoring evidence only; closes no EV (design #32 §1.1; design #38 provisional).
"""

from __future__ import annotations

import functools
import inspect
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol, get_args, get_type_hints

import pytest
import tos.marketfeed
import tos.marketfeed._base
import tos.marketfeed.records
import tos.marketfeed.resolver
import tos.marketfeed.value
import tos.marketfeed.vocabulary
from tos.capsule import CriticalInputSnapshot, DecisionContextCapsule
from tos.engine import InstrumentKey
from tos.marketfeed import (
    AdmittedValue,
    MarketFeedContextResolver,
    ResolvedTick,
    SnapshotStore,
    TimeCoordinateProjection,
    ValueCandidateSource,
    ValueRejectionReason,
    ValueViewDisposition,
)

from ._marketfeed_fixtures import (
    ACCOUNT,
    BAR_ONE_AS_OF,
    BAR_TWO_AS_OF,
    CLOSE_BAR_ONE,
    CLOSE_BAR_TWO,
    INSTRUMENT,
    SCHEME,
    candidate,
    evaluation,
    issue_capsule,
    issue_snapshot,
    lineage_node,
    observation,
    one_bar,
    preimage,
)

KEY = InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)

#: The band a derived-value bar exposes (the lineage suite's magnitude, reused as a plain number).
_BAND = 4_500_000


# ===========================================================================
# The fake CIS: the port's upstream, in this file's own shapes
# ===========================================================================


def _store_for(snapshot: CriticalInputSnapshot | None) -> SnapshotStore:
    """A plain-function :class:`~tos.marketfeed.SnapshotStore` answering with ``snapshot``."""

    def store(
        *, snapshot_id: str | None, canonical_digest: str | None
    ) -> CriticalInputSnapshot | None:
        del snapshot_id, canonical_digest
        return snapshot

    return store


def _source_for(candidates: Sequence[AdmittedValue]) -> ValueCandidateSource:
    """A plain-function :class:`~tos.marketfeed.ValueCandidateSource` supplying ``candidates``."""

    def source(
        snapshot: CriticalInputSnapshot, *, instrument_key: InstrumentKey
    ) -> Sequence[AdmittedValue]:
        del snapshot, instrument_key
        return candidates

    return source


def _resolve(
    *,
    capsule: DecisionContextCapsule,
    snapshot: CriticalInputSnapshot | None,
    candidates: Sequence[AdmittedValue],
) -> ResolvedTick:
    """Drive the **real** resolver over a fake CIS pair — the port boundary, not the gate."""
    resolver = MarketFeedContextResolver(
        snapshot_store=_store_for(snapshot),
        candidate_source=_source_for(candidates),
        scheme=SCHEME,
    )
    return resolver.resolve(capsule, instrument_key=KEY)


def _reasons(resolved: ResolvedTick) -> set[ValueRejectionReason]:
    """The named rejection reasons a resolution recorded."""
    return {entry.reason for entry in resolved.resolution.rejected}


# ===========================================================================
# P1 — the Protocol surface itself (design #38 §4-P1; D-E4 :69-96 isomorph)
# ===========================================================================

_PORT_PROTOCOLS = (SnapshotStore, ValueCandidateSource)


def _protocol_id(protocol: type) -> str:
    """Test id for a parametrized Protocol."""
    return protocol.__name__


def _public_names(protocol: type) -> list[str]:
    """The named (non-dunder) attributes a Protocol declares in its own body."""
    return sorted(name for name in vars(protocol) if not name.startswith("_"))


@pytest.mark.parametrize("protocol", _PORT_PROTOCOLS, ids=_protocol_id)
def test_each_port_protocol_is_call_only(protocol: type) -> None:
    """(§4-P1.1 ★) One anonymous call surface — a named ``fetch`` / ``subscribe`` has nowhere to go.

    D-E4 locks ``vars(Transport) == ["send_once"]``; the ingress form of the same lock is the empty
    list plus a ``__call__`` the Protocol really declares itself (design #34 §5.1 isomorph).
    """
    assert _public_names(protocol) == []
    assert "__call__" in vars(protocol), f"{protocol.__name__} declares no __call__ of its own"


def test_the_call_only_sweep_would_see_a_named_side_method() -> None:
    """(anti-phantom, both ways) The empty list above is a measurement, not a vacuous truth."""

    class _Smuggled(Protocol):
        """A Protocol that grew a side channel next to its call surface."""

        def __call__(self, *, snapshot_id: str | None) -> None: ...

        def subscribe(self, topic: str) -> None: ...

    assert _public_names(_Smuggled) == ["subscribe"]


def test_the_snapshot_store_call_takes_exactly_the_content_address() -> None:
    """(§4-P1.2 ★) ``(*, snapshot_id, canonical_digest)`` — a content address and nothing else."""
    assert set(inspect.signature(SnapshotStore.__call__).parameters) == {
        "self",
        "snapshot_id",
        "canonical_digest",
    }


def test_the_candidate_source_call_takes_exactly_the_snapshot_and_the_scope() -> None:
    """(§4-P1.2 ★) ``(snapshot, *, instrument_key)`` — the body it reads and the dispatch scope."""
    assert set(inspect.signature(ValueCandidateSource.__call__).parameters) == {
        "self",
        "snapshot",
        "instrument_key",
    }


#: Names that would turn an injection port into an ambient one: a live-transport surface, a
#: credential, or a clock. Matched **token-wise** (``split("_")`` plus the whole name) — the
#: ``_base.py:17-19`` discipline. An exact-name rule would miss ``session_token``; a bare substring
#: rule would over-reject, which is its own defect class (the #26 WDR MAJOR-1 lesson).
_AMBIENT_TOKENS = frozenset(
    {
        "clock",
        "credential",
        "fetch",
        "fetcher",
        "host",
        "now",
        "port",
        "session",
        "socket",
        "subscribe",
        "token",
        "url",
    }
)


def _ambient_offenders(names: Iterable[str]) -> tuple[str, ...]:
    """The parameter names that would give the port an ambient or transport surface."""
    offenders: list[str] = []
    for name in names:
        lowered = name.lower()
        parts = {part for part in lowered.split("_") if part}
        if lowered in _AMBIENT_TOKENS or parts & _AMBIENT_TOKENS:
            offenders.append(name)
    return tuple(offenders)


@pytest.mark.parametrize("protocol", _PORT_PROTOCOLS, ids=_protocol_id)
def test_no_port_call_admits_an_ambient_or_transport_parameter(protocol: type) -> None:
    """(§4-P1.3) The port receives a content address; it opens, authenticates and times nothing."""
    parameters = inspect.signature(protocol.__call__).parameters
    assert _ambient_offenders(parameters) == ()


def test_the_ambient_rule_is_token_wise_and_does_not_over_reject() -> None:
    """(§4-P1.3 both ways) Token-wise is why ``session_token`` is caught; whole-name is why
    ``canonical_digest`` is not."""
    assert _ambient_offenders(["session_token"]) == ("session_token",)
    assert _ambient_offenders(["fetch_url", "clock", "credential_ref"]) == (
        "fetch_url",
        "clock",
        "credential_ref",
    )
    assert (
        _ambient_offenders(
            ["self", "snapshot_id", "canonical_digest", "snapshot", "instrument_key"]
        )
        == ()
    )


def test_exactly_two_constructor_injections_are_cis_product_surfaces() -> None:
    """(§4-P1.4 ★) The port is a pair, and the time projection is not a third member of it.

    ``resolver.py:39`` carries ``from __future__ import annotations``, so the raw annotations are
    *strings* and an identity comparison against them would be meaningless — ``get_type_hints``
    resolves them first (design #38 §12 ③). The string-ness is asserted, so this reasoning cannot
    quietly become stale.
    """
    raw = MarketFeedContextResolver.__init__.__annotations__
    assert isinstance(raw["snapshot_store"], str), "PEP-563 assumption stale (design #38 §12 ③)"

    hints = get_type_hints(MarketFeedContextResolver.__init__)
    port = sorted(
        name
        for name, hint in hints.items()
        if hint is SnapshotStore or hint is ValueCandidateSource
    )
    assert port == ["candidate_source", "snapshot_store"]
    assert hints["snapshot_store"] is SnapshotStore
    assert hints["candidate_source"] is ValueCandidateSource

    # The time authority is a separate, optional injection — a "now" reading is not admitted
    # snapshot content, and absorbing it into the port would be scope creep (design #38 §2.3).
    assert hints["time_projection"] is not TimeCoordinateProjection
    assert get_args(hints["time_projection"]) == (TimeCoordinateProjection, type(None))


# ===========================================================================
# P2 / P5 — required injection, and the three ways to bypass it
# ===========================================================================

_PORT_INJECTIONS = ("snapshot_store", "candidate_source")


def _bypass_offenders(target: type) -> tuple[str, ...]:
    """Ways ``target`` would let a resolver be built without a CIS-issued source.

    Empty means both port halves are required, keyword-only constructor arguments — the structural
    form of "no snapshot body and no candidate value enters except through the port".

    Args:
        target: The class whose ``__init__`` is read.

    Returns:
        One complaint per bypass found, empty when the port is required.
    """
    parameters = inspect.signature(target.__init__).parameters  # type: ignore[misc]
    offenders: list[str] = []
    for name in _PORT_INJECTIONS:
        parameter = parameters.get(name)
        if parameter is None:
            offenders.append(f"{name}: not an __init__ parameter")
            continue
        if parameter.kind is not inspect.Parameter.KEYWORD_ONLY:
            offenders.append(f"{name}: {parameter.kind.name}, not KEYWORD_ONLY")
        if parameter.default is not inspect.Parameter.empty:
            offenders.append(f"{name}: default {parameter.default!r}")
    return tuple(offenders)


def test_the_resolver_cannot_be_built_without_a_cis_issued_source() -> None:
    """(§4-P2 ★) Both port halves are required, keyword-only constructor arguments."""
    assert _bypass_offenders(MarketFeedContextResolver) == ()


def test_the_constructor_takes_exactly_the_declared_injections() -> None:
    """(§4-P2) An exact set, so a later ambient collaborator cannot arrive unremarked."""
    parameters = inspect.signature(MarketFeedContextResolver.__init__).parameters
    assert set(parameters) == {
        "self",
        "snapshot_store",
        "candidate_source",
        "scheme",
        "time_projection",
    }
    assert parameters["time_projection"].default is None
    assert _ambient_offenders(parameters) == ()


def test_omitting_a_port_half_is_a_construction_error_not_a_default() -> None:
    """(§4-P2 behavioural mirror) The signature lock and the runtime agree with each other."""
    _, snapshot, candidates = one_bar()
    with pytest.raises(TypeError):
        MarketFeedContextResolver(snapshot_store=_store_for(snapshot), scheme=SCHEME)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        MarketFeedContextResolver(candidate_source=_source_for(candidates), scheme=SCHEME)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        MarketFeedContextResolver(_store_for(snapshot), _source_for(candidates), SCHEME)  # type: ignore[call-arg]


def _ambient_store(*, snapshot_id: str | None, canonical_digest: str | None) -> None:
    """The no-op store a default would silently supply — a resolver with no CIS behind it."""
    del snapshot_id, canonical_digest
    return None


def _ambient_source(snapshot: Any, *, instrument_key: Any) -> tuple[()]:
    """The no-op candidate source a default would silently supply."""
    del snapshot, instrument_key
    return ()


class _PortMovedOutOfInit:
    """(§4-P5 a) The injections became class attributes — nothing is required at construction."""

    snapshot_store = staticmethod(_ambient_store)
    candidate_source = staticmethod(_ambient_source)

    def __init__(self, *, scheme: Any) -> None:
        """Wire only the scheme; the port halves are ambient class state."""
        self._scheme = scheme


class _PortMadePositional:
    """(§4-P5 b) Keyword-only became positional — two call sites away from a silent swap."""

    def __init__(self, snapshot_store: Any, candidate_source: Any, *, scheme: Any = None) -> None:
        """Wire the port positionally."""
        self._snapshot_store = snapshot_store
        self._candidate_source = candidate_source
        self._scheme = scheme


class _PortGivenDefaults:
    """(§4-P5 c) A default source — the resolver builds with no CIS product at all."""

    def __init__(
        self,
        *,
        snapshot_store: Any = _ambient_store,
        candidate_source: Any = _ambient_source,
        scheme: Any = None,
    ) -> None:
        """Wire the port, or accept the ambient no-op."""
        self._snapshot_store = snapshot_store
        self._candidate_source = candidate_source
        self._scheme = scheme


@pytest.mark.parametrize(
    ("mutant", "complaint"),
    [
        (_PortMovedOutOfInit, "not an __init__ parameter"),
        (_PortMadePositional, "not KEYWORD_ONLY"),
        (_PortGivenDefaults, "default "),
    ],
    ids=("moved-out-of-init", "made-positional", "given-a-default"),
)
def test_every_port_bypass_mutation_is_killed(mutant: type, complaint: str) -> None:
    """(§4-P5 ★ mutation) The three ways to make the port optional are all caught, and named."""
    offenders = _bypass_offenders(mutant)
    assert offenders != (), f"{mutant.__name__} bypassed the port and was NOT detected"
    assert all(complaint in offender for offender in offenders), offenders


# ===========================================================================
# P3 — the over-claim seal (design #38 §4-P3; existence + absence)
# ===========================================================================

_MARKETFEED_SRC = Path(tos.marketfeed.__file__).resolve().parent

#: The shipped submodules whose authored prose is in scope. Compared against disk below, so a
#: seventh module cannot land un-swept (``test_marketfeed_import_closure.py:627-641`` discipline).
_SWEPT_MODULES = {
    "tos.marketfeed": tos.marketfeed,
    "tos.marketfeed._base": tos.marketfeed._base,
    "tos.marketfeed.records": tos.marketfeed.records,
    "tos.marketfeed.resolver": tos.marketfeed.resolver,
    "tos.marketfeed.value": tos.marketfeed.value,
    "tos.marketfeed.vocabulary": tos.marketfeed.vocabulary,
}

#: Claims the port cannot back (design #38 §3.3). Stems, not whole phrases, so a conjugation does
#: not walk past the rule.
_OVER_CLAIM_STEMS = (
    "complete enforcement",
    "fully enforc",
    "completely enforc",
    "re-verif",
    "guarantees producer",
    "guarantee producer honesty",
)

#: The qualification that turns a stem into an honest statement — the claim is placed upstream or
#: negated. "Complete enforcement is upstream" is honest; "this layer fully enforces" is not.
_HONEST_ANCHORS = ("upstream", "cannot", "does not", "not ")

#: Sentence split on terminal punctuation **followed by whitespace**, trailing closers consumed. A
#: bare ``"."`` split would cut ``value.py:44`` in half and orphan an anchor from its stem — an
#: over-rejection this rule must not commit (design #38 §12 NIT-3).
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]*\s+")


def _normalized(text: str) -> str:
    """One-line form — every pin below must survive a line wrap (design #38 §12 ①).

    ``__init__.py:64-65`` wraps "none of / them is claimed as closed" across two source lines, so a
    raw substring check would fail on landing. The precedent is ``test_egressgw_package.py:43``.
    """
    return " ".join(text.split())


def _sentences(text: str) -> list[str]:
    """``text`` split into sentences, dotted tokens such as ``value.py:44`` kept whole."""
    return [part for part in _SENTENCE_END.split(_normalized(text)) if part]


def _over_claim_offenders(text: str) -> tuple[str, ...]:
    """Sentences claiming enforcement the port does not have (design #38 §3.3).

    Co-occurrence, not substring: a stem is an offence only when its own sentence carries no
    upstream/negation anchor. The honest uses already shipped — "the environment-injection point
    does not re-verify it" — must pass, or the rule would be an over-rejection.

    Args:
        text: The docstring under inspection.

    Returns:
        The offending sentences, empty when every stem is qualified.
    """
    offenders: list[str] = []
    for sentence in _sentences(text):
        lowered = sentence.lower()
        if not any(stem in lowered for stem in _OVER_CLAIM_STEMS):
            continue
        if any(anchor in lowered for anchor in _HONEST_ANCHORS):
            continue
        offenders.append(sentence)
    return tuple(offenders)


def _documented_surfaces() -> list[tuple[str, str]]:
    """``(name, normalized docstring)`` for every swept module and the surfaces it owns.

    Scope is design #38 §4-P3: the six modules plus the public classes and functions each module
    **owns**. A name re-exported from ``tos.canonical`` is that package's prose, not marketfeed's,
    and is filtered out by its ``__module__``.
    """
    surfaces: list[tuple[str, str]] = []
    for module_name, module in sorted(_SWEPT_MODULES.items()):
        surfaces.append((module_name, _normalized(module.__doc__ or "")))
        for attr_name, obj in sorted(vars(module).items()):
            if attr_name.startswith("_"):
                continue
            if not (inspect.isclass(obj) or inspect.isfunction(obj)):
                continue
            if getattr(obj, "__module__", None) != module_name:
                continue
            surfaces.append((f"{module_name}.{attr_name}", _normalized(obj.__doc__ or "")))
    return surfaces


def test_the_over_claim_sweep_covers_every_shipped_submodule() -> None:
    """(anti-phantom) The swept set is the on-disk set — a new module cannot land un-swept."""
    on_disk = {
        f"tos.marketfeed.{path.stem}" if path.stem != "__init__" else "tos.marketfeed"
        for path in _MARKETFEED_SRC.glob("*.py")
    }
    assert on_disk == set(_SWEPT_MODULES), (
        f"the shipped submodule set drifted: on-disk={sorted(on_disk)}, "
        f"swept={sorted(_SWEPT_MODULES)}"
    )


def test_the_sweep_reaches_the_port_docstrings_this_contract_edits() -> None:
    """(§4-P3 scope) The §5.2 edits land inside the swept set, not outside it."""
    names = {name for name, _ in _documented_surfaces()}
    for expected in (
        "tos.marketfeed",
        "tos.marketfeed.resolver",
        "tos.marketfeed.resolver.SnapshotStore",
        "tos.marketfeed.resolver.ValueCandidateSource",
        "tos.marketfeed.resolver.MarketFeedContextResolver",
        "tos.marketfeed.value.publish_context_value_view",
    ):
        assert expected in names, f"{expected} is outside the over-claim sweep"


def test_the_package_still_declares_what_it_is_not() -> None:
    """(§4-P3.1 / §5.1 ★ positive pin) The honesty phrases the port naming must not retire."""
    doc = _normalized(tos.marketfeed.__doc__ or "")
    for phrase in (
        "not the Context Integrity Service runtime",
        "detects rather than enforces",
        "none of them is claimed as closed",
    ):
        assert phrase in doc, f"the package docstring lost its honesty phrase: {phrase!r}"


def test_the_publication_layer_still_names_the_limit_it_cannot_close() -> None:
    """(§4-P3.1 ★ positive pin) ``value.py`` states the as-of limit as a limit, not a guarantee."""
    assert "cannot close" in _normalized(tos.marketfeed.value.__doc__ or "")


def test_no_marketfeed_docstring_claims_enforcement_the_port_does_not_have() -> None:
    """(§4-P3.2 ★ the seal) Over-claim stems are admitted only alongside their qualification."""
    offenders = [
        (name, sentence)
        for name, doc in _documented_surfaces()
        for sentence in _over_claim_offenders(doc)
    ]
    assert offenders == [], f"unqualified enforcement claim in marketfeed prose: {offenders}"


def test_the_over_claim_rule_is_co_occurrence_not_substring() -> None:
    """(§4-P3.3 both ways) The honest sentence passes; the planted unqualified claim fails."""
    assert _over_claim_offenders("Complete enforcement is upstream (the CIS).") == ()
    assert _over_claim_offenders("This layer fully enforces distinctness.") == (
        "This layer fully enforces distinctness.",
    )


def test_a_planted_over_claim_is_caught_where_it_would_actually_land() -> None:
    """(§4-P3.3 ★ mutation) The rule catches the claim inside real shipped prose."""
    planted = _normalized(tos.marketfeed.__doc__ or "") + " This layer fully enforces distinctness."
    assert _over_claim_offenders(planted) == ("This layer fully enforces distinctness.",)


def test_the_sentence_split_keeps_a_dotted_source_reference_whole() -> None:
    """(§4-P3.2 / §12 NIT-3) A bare ``"."`` split would orphan the anchor and over-reject."""
    qualified = "Nothing here fully enforces value.py:44's limit; it is upstream."
    assert _sentences(qualified) == [qualified]
    assert _over_claim_offenders(qualified) == ()

    naive = [part for part in qualified.split(".") if part]
    assert any("fully enforces" in part and "upstream" not in part for part in naive), (
        "the naive split no longer demonstrates the over-rejection this protection prevents"
    )


def test_the_shipped_trust_seam_sentence_is_what_the_rule_admits() -> None:
    """(§4-P3.3 in-scope example) The rule has bite on shipped prose, not only on synthetic text.

    ``value.py:35-37`` says the environment-injection point "does **not** re-verify it" — a stem and
    its anchor in one sentence. If that sentence ever disappears the rule would still be green, so
    its presence is asserted rather than assumed.
    """
    doc = _normalized(tos.marketfeed.value.__doc__ or "")
    stemmed = [
        sentence
        for sentence in _sentences(doc)
        if any(stem in sentence.lower() for stem in _OVER_CLAIM_STEMS)
    ]
    assert stemmed, "value.py carries no over-claim stem any more — the rule is vacuous here"
    assert all("not" in sentence.lower() for sentence in stemmed), stemmed
    assert _over_claim_offenders(doc) == ()


# ===========================================================================
# P4 — the four gates, restated at the port boundary (design #38 §4-P4)
# ===========================================================================


def test_a_body_that_is_not_the_referenced_one_is_refused_at_the_port() -> None:
    """(§4-P4 a / G1) A store answering with another snapshot publishes nothing.

    The gate-level form of this is committed at ``test_marketfeed_resolver.py:93-102`` (K11); this
    restates it as the port's own obligation, which is the framing the other three reuse.
    """
    capsule, _, candidates = one_bar()
    impostor = issue_snapshot(intended_use="something-else")
    resolved = _resolve(capsule=capsule, snapshot=impostor, candidates=candidates)
    assert resolved.resolution.disposition is ValueViewDisposition.BINDING_MISMATCH
    assert resolved.payload.value_view is None
    assert resolved.value_surface_published is False


def test_a_candidate_the_observation_does_not_attest_is_refused_at_the_port() -> None:
    """(§4-P4 b / G2 ★) A source that supplies a different number reaches a rejection record."""
    payload = preimage(close=CLOSE_BAR_ONE)
    obs = observation(raw_event_id="raw-1", payload=payload, as_of=BAR_ONE_AS_OF)
    snapshot = issue_snapshot(observations=(obs,), field_evaluations=(evaluation("close"),))
    capsule = issue_capsule(snapshot)
    forged = candidate("close", "raw-1", preimage(close=CLOSE_BAR_TWO))

    resolved = _resolve(capsule=capsule, snapshot=snapshot, candidates=(forged,))
    assert _reasons(resolved) == {ValueRejectionReason.DIGEST_MISMATCH}
    assert resolved.resolution.disposition is ValueViewDisposition.EXPLICIT_EMPTY
    assert resolved.payload.value_view is not None
    assert resolved.payload.value_view.values == ()


def test_a_derived_value_whose_parent_is_later_is_refused_at_the_port() -> None:
    """(§4-P4 c / G4 ★) Recorded look-ahead is refused through the port, not merely at the gate."""
    close_payload = preimage(close=CLOSE_BAR_ONE)
    band_payload = preimage(lower_band=_BAND)
    snapshot = issue_snapshot(
        observations=(
            observation(raw_event_id="raw-close", payload=close_payload, as_of=BAR_TWO_AS_OF),
            observation(raw_event_id="raw-band", payload=band_payload, as_of=BAR_ONE_AS_OF),
        ),
        field_evaluations=(evaluation("close"), evaluation("lower_band")),
        transformation_lineage=(lineage_node(output_id="raw-band", parents=("raw-close",)),),
    )
    capsule = issue_capsule(snapshot)

    resolved = _resolve(
        capsule=capsule,
        snapshot=snapshot,
        candidates=(candidate("lower_band", "raw-band", band_payload),),
    )
    assert _reasons(resolved) == {ValueRejectionReason.LINEAGE_LOOKAHEAD}
    assert resolved.payload.value_view is not None
    assert resolved.payload.value_view.values == ()


def test_an_unevaluated_field_is_refused_at_the_port() -> None:
    """(§4-P4 d / G3 ★) The ∅ floor holds through the port: silence is not validity."""
    payload = preimage(close=CLOSE_BAR_ONE)
    obs = observation(raw_event_id="raw-1", payload=payload, as_of=BAR_ONE_AS_OF)
    snapshot = issue_snapshot(observations=(obs,), field_evaluations=())
    capsule = issue_capsule(snapshot)

    resolved = _resolve(
        capsule=capsule, snapshot=snapshot, candidates=(candidate("close", "raw-1", payload),)
    )
    assert _reasons(resolved) == {ValueRejectionReason.FIELD_STATE_NOT_VALID}
    assert resolved.payload.value_view is not None
    assert resolved.payload.value_view.values == ()


# ===========================================================================
# §4.2 — source parity in three structural shapes, and its KILL mutation
# ===========================================================================


class _MethodBook:
    """A fake CIS playing both port halves as **bound methods** (the ``BandBarBook`` shape)."""

    def __init__(
        self, snapshot: CriticalInputSnapshot, candidates: Sequence[AdmittedValue]
    ) -> None:
        """Hold the one body and the one candidate set this book answers with."""
        self._snapshot = snapshot
        self._candidates = candidates

    def snapshot_store(
        self, *, snapshot_id: str | None, canonical_digest: str | None
    ) -> CriticalInputSnapshot:
        """The content-addressed lookup, as a bound method."""
        del snapshot_id, canonical_digest
        return self._snapshot

    def candidate_source(
        self, snapshot: CriticalInputSnapshot, *, instrument_key: InstrumentKey
    ) -> Sequence[AdmittedValue]:
        """The candidate supplier, as a bound method."""
        del snapshot, instrument_key
        return self._candidates


class _CallableStore:
    """A fake CIS store as a **callable object** rather than a function."""

    def __init__(self, snapshot: CriticalInputSnapshot) -> None:
        """Hold the one body this store answers with."""
        self._snapshot = snapshot

    def __call__(
        self, *, snapshot_id: str | None, canonical_digest: str | None
    ) -> CriticalInputSnapshot | None:
        """The content-addressed lookup, as ``__call__``."""
        del snapshot_id, canonical_digest
        return self._snapshot


class _PeekingStore(_CallableStore):
    """(§4.2 KILL) A store that branches on **its own kind** — what parity must be able to catch."""

    def __call__(
        self, *, snapshot_id: str | None, canonical_digest: str | None
    ) -> CriticalInputSnapshot | None:
        """Answer differently depending on what shape the store itself is."""
        del snapshot_id, canonical_digest
        return None if type(self) is _PeekingStore else self._snapshot


def _partial_source(
    snapshot: CriticalInputSnapshot,
    *,
    instrument_key: InstrumentKey,
    candidates: Sequence[AdmittedValue],
) -> Sequence[AdmittedValue]:
    """A candidate source completed by :func:`functools.partial`."""
    del snapshot, instrument_key
    return candidates


def _port_shapes(
    snapshot: CriticalInputSnapshot, candidates: Sequence[AdmittedValue]
) -> dict[str, tuple[SnapshotStore, ValueCandidateSource]]:
    """The same body and candidates injected in three structurally different shapes."""
    book = _MethodBook(snapshot, candidates)
    return {
        "plain-function": (_store_for(snapshot), _source_for(candidates)),
        "bound-method": (book.snapshot_store, book.candidate_source),
        "callable-object-and-partial": (
            _CallableStore(snapshot),
            functools.partial(_partial_source, candidates=candidates),
        ),
    }


def _view_digest(
    store: SnapshotStore, source: ValueCandidateSource, capsule: DecisionContextCapsule
) -> str:
    """The published view digest for one injected pair."""
    resolved = MarketFeedContextResolver(
        snapshot_store=store, candidate_source=source, scheme=SCHEME
    ).resolve(capsule, instrument_key=KEY)
    assert resolved.payload.value_view is not None
    return resolved.payload.value_view.canonical_digest


def test_the_port_does_not_discriminate_between_upstream_shapes() -> None:
    """(§4.2 parity ★) Function, bound method, callable object / partial — one digest.

    This is the structural form of ``resolver.py:16-18`` "the resolver cannot tell them apart": the
    three shapes are different *kinds of Python object*, not three names for one function.
    """
    capsule, snapshot, candidates = one_bar()
    digests = {
        shape: _view_digest(store, source, capsule)
        for shape, (store, source) in _port_shapes(snapshot, candidates).items()
    }
    assert len(digests) == 3
    assert len(set(digests.values())) == 1, digests


def test_a_store_that_branches_on_its_own_kind_breaks_the_parity_claim() -> None:
    """(§4.2 KILL mutation) The parity assertion is falsifiable — a self-peeking store fails it."""
    capsule, snapshot, candidates = one_bar()
    honest = _view_digest(_store_for(snapshot), _source_for(candidates), capsule)
    assert honest

    peeking = MarketFeedContextResolver(
        snapshot_store=_PeekingStore(snapshot),
        candidate_source=_source_for(candidates),
        scheme=SCHEME,
    ).resolve(capsule, instrument_key=KEY)
    assert peeking.resolution.disposition is ValueViewDisposition.SNAPSHOT_UNRESOLVED
    assert peeking.payload.value_view is None


# ===========================================================================
# The non-guarantee, stated as a non-guarantee (design #38 §3.3 N1 / §4.2)
# ===========================================================================


def test_the_port_does_not_make_the_producer_honest_about_as_of() -> None:
    """(§3.3 N1 ★ limit, not a guarantee) Two bars stamped with one as-of collapse the chain.

    Nothing here is asserted to be *caught*. The port admits both, their digests coincide, and
    complete enforcement of per-bar distinctness stays upstream, in the Context Integrity Service —
    which is what K1 (``test_marketfeed_distinctness.py:236-247``) says at the gate and what this
    says at the port. Adding an as-of reuse rejection would be deferral ②(b) work and the invention
    design #38 §0.4 (f) forbids, so it is not done.
    """
    capsule_one, snapshot_one, candidates_one = one_bar(as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE)
    capsule_two, snapshot_two, candidates_two = one_bar(as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE)

    first = _resolve(capsule=capsule_one, snapshot=snapshot_one, candidates=candidates_one)
    second = _resolve(capsule=capsule_two, snapshot=snapshot_two, candidates=candidates_two)

    assert first.resolution.disposition is ValueViewDisposition.RESOLVED
    assert second.resolution.disposition is ValueViewDisposition.RESOLVED
    assert first.payload.value_view is not None and second.payload.value_view is not None
    assert first.payload.value_view.canonical_digest == second.payload.value_view.canonical_digest
    assert snapshot_one.canonical_digest == snapshot_two.canonical_digest
