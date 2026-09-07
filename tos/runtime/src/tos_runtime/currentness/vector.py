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
refuses. Both return ``None`` rather than a partial/placeholder vector.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
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
    "Item3Fields",
    "SingleNodeCommitCertificate",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: The locally-reported domain label for the RCL commitment-epoch currency
#: check (module docstring "Domain-label honesty") — never the Safety
#: Authority epoch's own domain string.
_RCL_COMMITMENT_EPOCH_DOMAIN = "RCL_COMMITMENT_EPOCH"


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
        authority_epoch_reader: Injected callable returning the Safety
            Authority epoch state, or ``None`` when unavailable — **never**
            an import of ``tos_runtime.authority`` (lane P's own package;
            cross-lane inputs are injected callables only, per the
            coordinator's task brief).
        permit_seq_reader: Injected callable returning the current Action
            Flow Permit RCL seq, or ``None`` when unavailable — never an
            import of ``tos_runtime.risk`` (lane Q's own package).
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
        authority_epoch_reader: Callable[[], AuthorityEpochState | None],
        permit_seq_reader: Callable[[], int | None],
        scheme: CanonicalizationScheme = _SCHEME,
    ) -> None:
        self._log = log
        self._time = time_service
        self._writer_epoch = writer_epoch
        self._policy = policy
        self._mandated = mandated
        self._authority_epoch_reader = authority_epoch_reader
        self._permit_seq_reader = permit_seq_reader
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
        effective_seq: int,
        revision: CurrentnessRevision,
        snapshot: TimeHealthSnapshot,
    ) -> list[CurrentnessDimension]:
        """The two dimensions this process can always structurally observe
        (RCL, Trustworthy Time) — split out of :meth:`assemble` to stay
        under the module size budget."""
        return [
            CurrentnessDimension(
                dimension_key=DimensionKey.COMMIT_LOG,
                owner_identity="tos_runtime.rcl",
                bound_generation=effective_seq,
                bound_digest=self._scheme.compute_digest(
                    {"epoch": view.epoch, "last_seq": view.last_seq}
                ),
                restrictive_floor=0,
                positively_established=True,
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

    def _injected_dimensions(
        self, *, revision: CurrentnessRevision
    ) -> list[CurrentnessDimension]:
        """The Safety Authority / Action Flow Permit dimensions, present only
        when their injected readers return a concrete value — split out of
        :meth:`assemble` to stay under the module size budget."""
        dimensions: list[CurrentnessDimension] = []

        authority_state = self._authority_epoch_reader()
        if (
            authority_state is not None
            and authority_state.current_epoch_floor is not None
        ):
            dimensions.append(
                CurrentnessDimension(
                    dimension_key=DimensionKey.SAFETY_AUTHORITY,
                    owner_identity="tos_runtime.authority",
                    bound_generation=authority_state.current_epoch_floor,
                    bound_digest=self._scheme.compute_digest(
                        {
                            "domain": authority_state.authority_domain,
                            "floor": authority_state.current_epoch_floor,
                        }
                    ),
                    restrictive_floor=0,
                    positively_established=True,
                    at_revision=revision,
                )
            )

        permit_seq = self._permit_seq_reader()
        if permit_seq is not None:
            dimensions.append(
                CurrentnessDimension(
                    dimension_key=DimensionKey.ACTION_FLOW,
                    owner_identity="tos_runtime.risk",
                    bound_generation=permit_seq,
                    bound_digest=self._scheme.compute_digest(
                        {"permit_seq": permit_seq}
                    ),
                    restrictive_floor=0,
                    positively_established=True,
                    at_revision=revision,
                )
            )
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
        last_seq = view.last_seq
        # -1 is the log's own "empty" sentinel (SqliteCommitLog.append_cas's
        # own `expected_seq=-1` convention for an empty log) — a concrete,
        # ORDERED value rather than None, so an empty-but-acquired log is
        # honestly "established at seq -1", not "unestablished" (a None
        # bound_generation would make dimension_positively_established fail
        # closed even though the log's state IS positively known: empty).
        effective_seq = -1 if last_seq is None else last_seq
        revision = CurrentnessRevision(
            revision_id=f"rev-{view.epoch}-{effective_seq}", commit_index=effective_seq
        )

        dimensions = self._owned_dimensions(
            view=view, effective_seq=effective_seq, revision=revision, snapshot=snapshot
        )
        dimensions.extend(self._injected_dimensions(revision=revision))
        dimensions.extend(extra_dimensions)
        dims_tuple = tuple(dimensions)

        vector_digest = self._scheme.compute_digest(
            {
                "epoch": view.epoch,
                "last_seq": last_seq,
                "dimension_count": len(dims_tuple),
            }
        )
        issued = SafetyCurrentnessVector.issue(
            scheme=self._scheme,
            vector_id=f"vec-{view.epoch}-{last_seq}",
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
