"""``CurrentnessAssembler`` — Phase 2 currentness vector production seam."""

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

from tos_runtime.time.service import TimeServiceNotStarted, TimeSnapshotReader

__all__ = [
    "CurrentnessAssembler",
    "DimensionReport",
    "Item3Fields",
    "SingleNodeCommitCertificate",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_EMPTY_DIMENSION_READERS: Mapping[
    DimensionKey, tuple[str, Callable[[], DimensionReport | None]]
] = {}

_RCL_COMMITMENT_EPOCH_DOMAIN = "RCL_COMMITMENT_EPOCH"


@dataclass(frozen=True)
class DimensionReport:
    """One owner's injected currentness verdict for a single §9 dimension"""

    bound_generation: int | None
    positively_established: bool
    restrictive_floor: int


@dataclass(frozen=True)
class SingleNodeCommitCertificate:
    """A single-node commit certificate — explicitly **NOT** a quorum certificate."""

    writer_epoch: WriterEpoch
    seq: int | None
    digest: str | None


@dataclass(frozen=True)
class Item3Fields:
    """``SendBoundaryContext`` item 3 (provisional; ``egressgw/records.py``"""

    commitment_epoch_current: bool | None


class CurrentnessAssembler:
    """Derives a :class:`~tos.cur.SafetyCurrentnessVector` from each owner's"""

    def __init__(
        self,
        log: CommitLog,
        time_service: TimeSnapshotReader,
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
        self._last_assemble_complete: bool | None = None

    @property
    def last_assemble_complete(self) -> bool | None:
        """Whether the MOST RECENT :meth:`assemble` call issued a vector AND that vector"""
        return self._last_assemble_complete

    def commit_certificate(self) -> SingleNodeCommitCertificate | None:
        """The current :class:`SingleNodeCommitCertificate`, or ``None`` if no"""
        view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        if not view.epoch:
            return None
        digest = self._scheme.compute_digest(
            {"epoch": view.epoch, "last_seq": view.last_seq}
        )
        return SingleNodeCommitCertificate(
            writer_epoch=view.epoch, seq=view.last_seq, digest=digest
        )

    def item3_fields(self) -> Item3Fields:
        """``SendBoundaryContext`` item 3 — ``commitment_epoch_current``,"""
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
        """The two dimensions this process can always structurally observe"""
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
        """Copy an injected owner :class:`DimensionReport` into a"""
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
        """Every dimension in :attr:`_dimension_readers`, present only when"""
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
        """Issue a :class:`~tos.cur.SafetyCurrentnessVector` from the owners"""
        try:
            snapshot = self._time.current_snapshot()
        except TimeServiceNotStarted:
            self._last_assemble_complete = None
            return None
        if not state_permits_new_normal_risk(snapshot.health_state):
            self._last_assemble_complete = None
            return None
        assert snapshot.health_state is HealthState.TRUSTED

        view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        if not view.epoch:
            self._last_assemble_complete = None
            return None
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
        self._last_assemble_complete = self.is_complete(issued)
        return issued

    def is_complete(self, vector: SafetyCurrentnessVector) -> bool:
        """Whether ``vector`` is complete under this assembler's policy +"""
        return vector_complete(vector, self._policy, self._mandated)
