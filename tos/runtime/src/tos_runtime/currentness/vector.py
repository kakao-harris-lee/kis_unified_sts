"""``CurrentnessAssembler`` — Phase 2 currentness vector production seam.

Design #40 (`docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-
decisions.md`) §5 order 6, lane R item 1
(`docs/plans/2026-09-08-tos-phase2-runtime-slice3-authority-risk-currentness-
compose-plan.md` §3 item 1). Consumes the kernel's ``tos.cur`` (ADR-002-024)
pure aggregator: this module never decides currentness itself, it only
**assembles the inputs** — each owner's own currently-committed revision —
into a :class:`~tos.cur.SafetyCurrentnessVector` and hands the result to the
kernel's own :func:`~tos.cur.predicates.vector_complete` for judgement.

**判定은 커널 술어만 한다** (slice plan §0): this module contains no
``>=``/``==`` comparison standing in for a kernel predicate. The one
epoch-currency check it performs (:meth:`CurrentnessAssembler.item3_fields`)
is realized entirely through the kernel's own
:func:`~tos.authority.predicates.authority_epoch_current` fence shape,
never a locally-authored comparison.

**R-RCL-F0 (single-node, not quorum).** ``tos-spec/src/part-1-foundation/
verification/RESIDUAL-RISK-REGISTER-002.yaml`` registers, at design #40 D2.2
(operator-ratified 2026-09-08), that Phase 2's RCL substrate is f=0 (no
replication) — "a Phase 2 design choice registered at authoring time", not a
waived requirement, and it keeps the restricted-live/production gate ``NO``
for this substrate on its own (ADR-002-009 §10.1 item 6) independently of
every other residual risk in that register (the file's own NON-UNION RULE).
:class:`SingleNodeCommitCertificate` names this honestly in its own docstring
and is never confused with ``tos.cur``'s reserved
``QuorumCommitCertificate`` name (``cur/__init__.py:35`` "egress owns
QuorumCommitCertificate").

**Domain-label honesty (item 3).** :meth:`CurrentnessAssembler.item3_fields`
feeds the RCL Writer Epoch through ``authority_epoch_current`` under a
locally-reported domain label, ``RCL_COMMITMENT_EPOCH`` — this is
*structurally* the same "is this epoch still the current floor for its
domain" fence shape the Safety Authority epoch uses, reused because the
kernel predicate is domain-agnostic (any injected ``authority_domain`` string
works), but it is emphatically **not** the Safety Authority epoch itself
(ADR-002-012 §5.5 line 129-131: "Consensus term, process generation, and
Writer Epoch MAY be related but SHALL NOT be treated as equivalent unless the
implementation proves the mapping survives membership change, restore, and
failover" — the same non-collapse discipline
``tos_runtime.rcl.log``'s own module docstring already applies to
``WriterEpoch`` vs. ``AuthorityEpochTransitionRecord``). Reported here, not
silently resolved by force-reuse.

Fault contract (design #3 §3 "장애 계약"): a non-``TRUSTED`` time snapshot
refuses vector assembly outright (``state_permits_new_normal_risk``); an
unacquired Writer Epoch (``read_linearizable`` reports no epoch) also
refuses. An empty (acquired-but-nothing-committed) log yields a COMMIT_LOG
dimension that is honestly **not** established (independent review of
39dd3993, MEDIUM-B: "nothing committed yet ⇒ nothing current" — no ``-1``
placeholder standing in for a real generation).

**Owner verdicts are copied, never authored (independent review of 39dd3993,
MEDIUM-A).** ``tos.cur.CurrentnessDimension.positively_established``'s own
docstring calls this field "the owner's injected verdict" — the Safety
Authority and Action Flow Permit dimensions are owned by lanes P/Q, not by
this assembler, so it must not decide ``positively_established``/
``restrictive_floor`` for them itself. :class:`DimensionReport` is the exact
shape those lanes' injected readers return; the assembler only copies its
fields into a :class:`~tos.cur.CurrentnessDimension` at the shared vector
revision. A reader returning ``None`` means it could not observe the
dimension at all — the dimension is omitted from the assembled vector, never
defaulted to established.

**Reader map (Phase 5 W3-b, plan
``docs/plans/2026-09-11-tos-phase5-w3-safety-mesh-plan.md`` §2 decision 3).**
``CurrentnessAssembler`` no longer hardcodes two owner-reader kwargs. Every
injected dimension — Safety Authority / Action Flow Permit (this Phase 2
slice) and every later Phase 5 owner (RECOVERY, TRADING_APPROVAL,
CURRENTNESS_POLICY, ENVIRONMENT_SCOPE, the four safety-mesh dimensions, …) —
is one entry in :attr:`dimension_readers`: ``DimensionKey -> (owner_identity,
reader)``. This is a pure generalization of the same "``None`` in, ``None``
out, owner decides every field" contract :meth:`_dimension_from_report`
already enforced for the two hardcoded readers — no behavioural change for
SAFETY_AUTHORITY/ACTION_FLOW, which are simply two more map entries now
(:mod:`tos_runtime.compose._currentness_wiring`'s own construction call).
A caller registering the SAME key twice is a caller bug the ``dict`` literal
itself would silently last-write-wins on; this class does not additionally
guard against it (compose-time key-collision refusal, if ever needed, is
:mod:`tos_runtime.compose._pending_dimensions`'s job — see its own
"owned/pending-duplicated key" boot refusal).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from tos.authority import AuthorityEpochState, authority_epoch_current
from tos.canonical import (
    EV_L1_PROVISIONAL_VERSION,
    CanonicalizationScheme,
    get_scheme,
)
from tos.cur import (
    CurrentnessDimension,
    CurrentnessPolicy,
    CurrentnessRevision,
    DimensionKey,
    SafetyCurrentnessVector,
    vector_complete,
)
from tos.rcl.commitlog import CommitLog, LogView, WriterEpoch
from tos.time import HealthState, TimeHealthSnapshot, state_permits_new_normal_risk

from tos_runtime.time.service import TimeServiceNotStarted, TrustworthyTimeService

__all__ = [
    "CurrentnessAssembler",
    "DimensionReport",
    "Item3Fields",
    "SingleNodeCommitCertificate",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: The default ``dimension_readers`` value — no injected dimension at all.
#: A plain ``{}`` default would be a mutable-default-argument hazard; this
#: named module-level constant is the shared empty instance every caller
#: that supplies none of its own readers gets.
_EMPTY_DIMENSION_READERS: Mapping[
    DimensionKey, tuple[str, Callable[[], DimensionReport | None]]
] = {}

#: The locally-reported domain label for the RCL commitment-epoch currency
#: check (module docstring "Domain-label honesty") — never the Safety
#: Authority epoch's own domain string.
_RCL_COMMITMENT_EPOCH_DOMAIN = "RCL_COMMITMENT_EPOCH"


@dataclass(frozen=True)
class DimensionReport:
    """One owner's injected currentness verdict for a single §9 dimension
    (module docstring, MEDIUM-A). The owner decides every field here —
    ``CurrentnessAssembler`` only copies them into a
    :class:`~tos.cur.CurrentnessDimension` at the shared vector revision; it
    never authors ``positively_established``/``restrictive_floor`` for a
    dimension it does not itself own.

    For the Safety Authority dimension, the natural owner-side construction
    is ``positively_established=tos.authority.predicates.currentness_admissible
    (witness)`` over that service's own :class:`~tos.authority.CurrentnessWitness`
    — never a bare "state exists" check. ``restrictive_floor`` is the
    owner's own explicit choice (Phase 2 has no floor-governance runtime
    yet, so an owner reporting ``0`` is that owner's deliberate statement,
    never one this assembler invents on the owner's behalf).
    """

    bound_generation: int | None
    positively_established: bool
    restrictive_floor: int


@dataclass(frozen=True)
class SingleNodeCommitCertificate:
    """A single-node commit certificate — explicitly **NOT** a quorum certificate.

    R-RCL-F0 (``tos-spec/.../RESIDUAL-RISK-REGISTER-002.yaml``, design #40
    D2.2): Phase 2's RCL substrate is a single node (f=0). "single node +
    writer epoch" is the entirety of what this process can honestly attest —
    there is no replica set to reach quorum with. ``tos.cur.__init__``
    reserves the name ``QuorumCommitCertificate`` for egress's own
    quorum-commitment axis; this type is deliberately a different name and
    never claims quorum. A consumer that needs an actual quorum-backed
    certificate cannot get one from Phase 2's RCL substrate — that is
    exactly what R-RCL-F0 records as the residual risk.
    """

    writer_epoch: WriterEpoch
    seq: int | None
    digest: str | None


@dataclass(frozen=True)
class Item3Fields:
    """``SendBoundaryContext`` item 3 (provisional; ``egressgw/records.py``
    line 559-561: "⚠ provisional RCL stand-in — real epoch fencing is
    deferred")."""

    commitment_epoch_current: bool | None


class CurrentnessAssembler:
    """Derives a :class:`~tos.cur.SafetyCurrentnessVector` from each owner's
    own currently-committed revision (design #40 §5 order 6, lane R item 1).

    Args:
        log: The injected RCL ``CommitLog`` port (the Protocol type only —
            never the concrete ``tos_runtime.rcl.SqliteCommitLog``, per the
            slice plan §5 "레인 간 계약" cross-lane isolation rule).
        time_service: The injected ``TrustworthyTimeService`` (lane K) this
            process already runs.
        writer_epoch: The Writer Epoch this process holds (acquired once at
            composition-root startup, design #40 D2.1).
        policy: The governing ``CurrentnessPolicy`` content (injected;
            activation is spg-governed, out of this lane's scope).
        mandated: The caller's mandated dimension floor (floored to at least
            ``MANDATED_DIMENSION_FLOOR`` by the kernel's own
            :func:`~tos.cur.predicates.vector_complete` — this class does not
            re-floor it).
        dimension_readers: ``DimensionKey -> (owner_identity, reader)`` — one
            entry per injected dimension this process can observe (module
            docstring, "Reader map"). Each reader returns the owning lane's
            own :class:`DimensionReport`, or ``None`` when unavailable —
            **never** an import of the owning lane's package (cross-lane
            inputs are injected callables only, per the coordinator's task
            brief). The reader, not this assembler, decides
            ``positively_established``/``restrictive_floor`` (MEDIUM-A).
            Defaults to an empty mapping (no injected dimension at all —
            only ``_owned_dimensions`` is assembled).
        scheme: The canonicalization scheme digests are computed under.
    """

    def __init__(
        self,
        log: CommitLog,
        time_service: TrustworthyTimeService,
        *,
        writer_epoch: WriterEpoch,
        policy: CurrentnessPolicy,
        mandated: frozenset[DimensionKey],
        dimension_readers: Mapping[
            DimensionKey, tuple[str, Callable[[], DimensionReport | None]]
        ] = _EMPTY_DIMENSION_READERS,
        scheme: CanonicalizationScheme = _SCHEME,
    ) -> None:
        self._log = log
        self._time = time_service
        self._writer_epoch = writer_epoch
        self._policy = policy
        self._mandated = mandated
        self._dimension_readers = dict(dimension_readers)
        self._scheme = scheme

    def commit_certificate(self) -> SingleNodeCommitCertificate | None:
        """The current :class:`SingleNodeCommitCertificate`, or ``None`` if no
        Writer Epoch has ever been acquired on this log."""
        view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        if (
            not view.epoch
        ):  # None or 0 (unacquired sentinel, tos_runtime.rcl.log.SqliteCommitLog.current_epoch)
            return None
        digest = self._scheme.compute_digest(
            {"epoch": view.epoch, "last_seq": view.last_seq}
        )
        return SingleNodeCommitCertificate(
            writer_epoch=view.epoch, seq=view.last_seq, digest=digest
        )

    def item3_fields(self) -> Item3Fields:
        """``SendBoundaryContext`` item 3 — ``commitment_epoch_current``,
        derived via the kernel's own ``authority_epoch_current`` fence shape
        (module docstring "Domain-label honesty"), never a self-comparison.
        """
        current = self._log.current_epoch()
        state = AuthorityEpochState(
            authority_domain=_RCL_COMMITMENT_EPOCH_DOMAIN,
            current_epoch_floor=current,
        )
        current_ok = authority_epoch_current(
            self._writer_epoch, _RCL_COMMITMENT_EPOCH_DOMAIN, state
        )
        return Item3Fields(commitment_epoch_current=current_ok)

    def _owned_dimensions(
        self,
        *,
        view: LogView,
        revision: CurrentnessRevision,
        snapshot: TimeHealthSnapshot,
    ) -> list[CurrentnessDimension]:
        """The two dimensions this process can always structurally observe
        (RCL, Trustworthy Time) — split out of :meth:`assemble` to stay
        under the module size budget.

        COMMIT_LOG's ``positively_established`` is ``view.last_seq is not
        None`` — an empty (acquired-but-nothing-committed) log has nothing
        current to report (MEDIUM-B), never a ``-1`` placeholder standing in
        for a real generation. TRUSTWORTHY_TIME's ``positively_established``
        is unconditionally ``True`` here because :meth:`assemble` already
        refused to reach this point unless ``snapshot.health_state`` is
        genuinely ``TRUSTED`` — a structural derivation from the real
        TrustworthyTimeService state, not an invented default.
        """
        return [
            CurrentnessDimension(
                dimension_key=DimensionKey.COMMIT_LOG,
                owner_identity="tos_runtime.rcl",
                bound_generation=view.last_seq,
                bound_digest=self._scheme.compute_digest(
                    {"epoch": view.epoch, "last_seq": view.last_seq}
                ),
                restrictive_floor=0,
                positively_established=view.last_seq is not None,
                at_revision=revision,
            ),
            CurrentnessDimension(
                dimension_key=DimensionKey.TRUSTWORTHY_TIME,
                owner_identity="tos_runtime.time",
                bound_generation=snapshot.generation,
                bound_digest=snapshot.canonical_digest,
                restrictive_floor=0,
                positively_established=True,
                at_revision=revision,
            ),
        ]

    @staticmethod
    def _dimension_from_report(
        report: DimensionReport | None,
        *,
        dimension_key: DimensionKey,
        owner_identity: str,
        revision: CurrentnessRevision,
        scheme: CanonicalizationScheme,
    ) -> CurrentnessDimension | None:
        """Copy an injected owner :class:`DimensionReport` into a
        :class:`~tos.cur.CurrentnessDimension` verbatim — this assembler
        authors none of ``positively_established``/``restrictive_floor``
        itself (MEDIUM-A). ``None`` in, ``None`` out: an owner that could
        not observe its own dimension contributes nothing, never a
        defaulted-established placeholder."""
        if report is None:
            return None
        return CurrentnessDimension(
            dimension_key=dimension_key,
            owner_identity=owner_identity,
            bound_generation=report.bound_generation,
            bound_digest=scheme.compute_digest(
                {
                    "dimension_key": dimension_key.value,
                    "bound_generation": report.bound_generation,
                }
            ),
            restrictive_floor=report.restrictive_floor,
            positively_established=report.positively_established,
            at_revision=revision,
        )

    def _injected_dimensions(
        self, *, revision: CurrentnessRevision
    ) -> list[CurrentnessDimension]:
        """Every dimension in :attr:`_dimension_readers`, present only when
        its own reader returns a :class:`DimensionReport` (module docstring,
        "Reader map") — split out of :meth:`assemble` to stay under the
        module size budget. Iteration order follows ``dict`` insertion order
        (the caller's own construction call), which is immaterial: dimension
        identity, not position, is what ``tos.cur`` compares on.
        """
        dimensions: list[CurrentnessDimension] = []
        for dimension_key, (owner_identity, reader) in self._dimension_readers.items():
            dimension = self._dimension_from_report(
                reader(),
                dimension_key=dimension_key,
                owner_identity=owner_identity,
                revision=revision,
                scheme=self._scheme,
            )
            if dimension is not None:
                dimensions.append(dimension)
        return dimensions

    def assemble(
        self, *, extra_dimensions: Sequence[CurrentnessDimension] = ()
    ) -> SafetyCurrentnessVector | None:
        """Issue a :class:`~tos.cur.SafetyCurrentnessVector` from the owners
        this process can structurally observe (RCL, Trustworthy Time, plus
        the injected Safety Authority / Action Flow Permit readers).

        Every other §9 dimension (spg profile, deviation, incident,
        monitoring, release, post-trade, critical input, context, constraint,
        construction, trading approval, aggregate risk, egress identity) is
        owned by a lane this slice does not wire directly — their absence is
        why :func:`~tos.cur.predicates.vector_complete` legitimately returns
        ``False`` on the assembled vector until those lanes are composed in
        (composition root S, or a later Phase); that is the honest L1
        substrate-only posture the whole ``tos.cur`` package documents for
        itself, not a defect of this assembler. ``extra_dimensions`` lets a
        caller (composition root, or a test) inject additional
        :class:`~tos.cur.CurrentnessDimension` coordinates from lanes that
        *are* wired.

        Returns:
            The issued vector, or ``None`` when the time snapshot is not
            ``TRUSTED`` (``state_permits_new_normal_risk``) or no Writer
            Epoch has been acquired — both are refusals, never a partial
            vector.
        """
        try:
            snapshot = self._time.current_snapshot()
        except TimeServiceNotStarted:
            return None
        if not state_permits_new_normal_risk(snapshot.health_state):
            return None
        assert snapshot.health_state is HealthState.TRUSTED  # narrowed above

        view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        if (
            not view.epoch
        ):  # None or 0 (unacquired sentinel, tos_runtime.rcl.log.SqliteCommitLog.current_epoch)
            return None
        # The revision identity carries whatever last_seq IS (including
        # None for an empty log) — it is a shared ORDERING label every
        # dimension must sit at (single_revision_consistent), not itself a
        # claim of establishment; COMMIT_LOG's own establishment is decided
        # separately in _owned_dimensions (MEDIUM-B — no -1 placeholder).
        revision = CurrentnessRevision(
            revision_id=f"rev-{view.epoch}-{view.last_seq}", commit_index=view.last_seq
        )

        dimensions = self._owned_dimensions(
            view=view, revision=revision, snapshot=snapshot
        )
        dimensions.extend(self._injected_dimensions(revision=revision))
        dimensions.extend(extra_dimensions)
        dims_tuple = tuple(dimensions)

        vector_digest = self._scheme.compute_digest(
            {
                "epoch": view.epoch,
                "last_seq": view.last_seq,
                "dimension_count": len(dims_tuple),
            }
        )
        issued = SafetyCurrentnessVector.issue(
            scheme=self._scheme,
            vector_id=f"vec-{view.epoch}-{view.last_seq}",
            currentness_revision=revision,
            vector_digest=vector_digest,
            policy_id=self._policy.policy_id,
            policy_generation=self._policy.policy_generation,
            policy_digest=self._policy.canonical_digest,
            dimensions=dims_tuple,
        )
        assert isinstance(issued, SafetyCurrentnessVector)
        return issued

    def is_complete(self, vector: SafetyCurrentnessVector) -> bool:
        """Whether ``vector`` is complete under this assembler's policy +
        mandated floor — a thin call-through to the kernel's own
        :func:`~tos.cur.predicates.vector_complete` (this class judges
        nothing itself)."""
        return vector_complete(vector, self._policy, self._mandated)
