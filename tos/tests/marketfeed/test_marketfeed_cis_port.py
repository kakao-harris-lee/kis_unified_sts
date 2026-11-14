"""§4 (design #38) — the admitted-snapshot injection port: its surface, its requirement, its seal."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Iterable, Sequence
from typing import Any, Protocol, get_args, get_type_hints

import pytest
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

_BAND = 4_500_000


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


_PORT_PROTOCOLS = (SnapshotStore, ValueCandidateSource)


def _protocol_id(protocol: type) -> str:
    """Test id for a parametrized Protocol."""
    return protocol.__name__


def _public_names(protocol: type) -> list[str]:
    """The named (non-dunder) attributes a Protocol declares in its own body."""
    return sorted(name for name in vars(protocol) if not name.startswith("_"))


@pytest.mark.parametrize("protocol", _PORT_PROTOCOLS, ids=_protocol_id)
def test_each_port_protocol_is_call_only(protocol: type) -> None:
    """(§4-P1.1 ★) One anonymous call surface — a named ``fetch`` / ``subscribe`` has nowhere to go."""
    assert _public_names(protocol) == []
    assert "__call__" in vars(
        protocol
    ), f"{protocol.__name__} declares no __call__ of its own"


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
    """(§4-P1.3 both ways) Token-wise is why ``session_token`` is caught; whole-name is why"""
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
    """(§4-P1.4 ★) The port is a pair, and the time projection is not a third member of it."""
    raw = MarketFeedContextResolver.__init__.__annotations__
    assert isinstance(
        raw["snapshot_store"], str
    ), "PEP-563 assumption stale (design #38 §12 ③)"

    hints = get_type_hints(MarketFeedContextResolver.__init__)
    port = sorted(
        name
        for name, hint in hints.items()
        if hint is SnapshotStore or hint is ValueCandidateSource
    )
    assert port == ["candidate_source", "snapshot_store"]
    assert hints["snapshot_store"] is SnapshotStore
    assert hints["candidate_source"] is ValueCandidateSource

    assert hints["time_projection"] is not TimeCoordinateProjection
    assert get_args(hints["time_projection"]) == (TimeCoordinateProjection, type(None))


_PORT_INJECTIONS = ("snapshot_store", "candidate_source")


def _bypass_offenders(target: type) -> tuple[str, ...]:
    """Ways ``target`` would let a resolver be built without a CIS-issued source."""
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

    def __init__(
        self, snapshot_store: Any, candidate_source: Any, *, scheme: Any = None
    ) -> None:
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


def test_a_body_that_is_not_the_referenced_one_is_refused_at_the_port() -> None:
    """(§4-P4 a / G1) A store answering with another snapshot publishes nothing."""
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
    snapshot = issue_snapshot(
        observations=(obs,), field_evaluations=(evaluation("close"),)
    )
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
            observation(
                raw_event_id="raw-close", payload=close_payload, as_of=BAR_TWO_AS_OF
            ),
            observation(
                raw_event_id="raw-band", payload=band_payload, as_of=BAR_ONE_AS_OF
            ),
        ),
        field_evaluations=(evaluation("close"), evaluation("lower_band")),
        transformation_lineage=(
            lineage_node(output_id="raw-band", parents=("raw-close",)),
        ),
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
        capsule=capsule,
        snapshot=snapshot,
        candidates=(candidate("close", "raw-1", payload),),
    )
    assert _reasons(resolved) == {ValueRejectionReason.FIELD_STATE_NOT_VALID}
    assert resolved.payload.value_view is not None
    assert resolved.payload.value_view.values == ()


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
    """(§4.2 parity ★) Function, bound method, callable object / partial — one digest."""
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


def test_the_port_does_not_make_the_producer_honest_about_as_of() -> None:
    """(§3.3 N1 ★ limit, not a guarantee) Two bars stamped with one as-of collapse the chain."""
    capsule_one, snapshot_one, candidates_one = one_bar(
        as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE
    )
    capsule_two, snapshot_two, candidates_two = one_bar(
        as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE
    )

    first = _resolve(
        capsule=capsule_one, snapshot=snapshot_one, candidates=candidates_one
    )
    second = _resolve(
        capsule=capsule_two, snapshot=snapshot_two, candidates=candidates_two
    )

    assert first.resolution.disposition is ValueViewDisposition.RESOLVED
    assert second.resolution.disposition is ValueViewDisposition.RESOLVED
    assert (
        first.payload.value_view is not None and second.payload.value_view is not None
    )
    assert (
        first.payload.value_view.canonical_digest
        == second.payload.value_view.canonical_digest
    )
    assert snapshot_one.canonical_digest == snapshot_two.canonical_digest
