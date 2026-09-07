"""RCL Safety Commit Log **port** + fault-contract predicates (design #40 D2.1).

Realizes the *kernel* (pure, non-transmitting) half of design doc #40's D2 decision
(``docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-decisions.md`` §D2.1,
lines 57-67), which resolves ADR-002-012 (Risk Capacity Ledger Persistence,
Consensus, and Writer Fencing) into a **single-node linearizable log +
replaceable ``CommitLog`` port**: "커널에 ``tos.rcl.CommitLog`` **Protocol** 을
신설(순수 시그니처: ``append_cas``·``read_linearizable``·``current_epoch``·
``replay``). 런타임 sqlite 구현과 미래의 복제 구현이 같은 포트를 만족한다.
커널은 포트만 알고 구현을 모른다" (design #40 D2.1 line 65).

**D1 (runtime composition boundary) is NOT yet ratified** (design #40 §0: "상태:
PROPOSED — 운영자 비준 대기... D1 비준 전에는 어떤 런타임 I/O 코드도 착지하지
않는다"). Consequently this module is **kernel PORT + PREDICATES only**: a
``typing.Protocol`` with no default implementation, plus pure fault-contract
predicates over injected observations. It performs **no I/O** — no ``sqlite3``,
``socket``, filesystem, or clock access — and does not live under ``tos/runtime``
(which does not exist yet; D1 creates it).

Realizes the D2.1 fault contract (design #40 D2.1 line 67, "장애 계약(각 서비스가
정상 API 보다 먼저 구현·테스트)"), items ①②⑤⑦ only (③④⑥ are runtime concerns —
partition-as-file-inaccessibility, crash-injection harnesses, and clock exclusion
— out of kernel scope):

* ① stale epoch writer → 거부+evidence : :func:`stale_writer_epoch`.
* ② 중복 command / 같은 ID 다른 바이트 → 두 번째는 거부, 바이트 불일치는
  ``INTEGRITY_VIOLATION`` 기록 : :func:`duplicate_command`.
* ⑤ 재기동 후 replay → 로그 전량 재생이 같은 상태를 재현하지 못하면
  ``CORRUPTION`` 표면화·비-live 고정 (ADR-002-012 line 491 "Independent replay
  SHALL reproduce the same deterministic state from the same committed prefix or
  identify corruption and remain non-live") : :func:`replay_reproduces_state`.
* ⑦ 저장소 불가/부분 커밋 → fail-closed(쓰기 실패 = 거부, 성공 보고 없음) — the
  ``AppendReceipt``/``AppendRefusal`` split below makes a "recorded" claim without
  a receipt structurally unconstructable (no third outcome).

Also realizes the reservation-lifecycle + release-admission piece of D2.1 line 64
("예약 생명주기 ... 해제(release)는 broker truth 또는 evidence 가 확정한 종결만이
트리거이며 자동 re-arm 없음") and ADR-002-012 line 37 ("Quorum restoration, leader
election, node restart, snapshot restore, or membership recovery SHALL NOT
automatically re-arm live operation or revive a prior capability") via
:func:`release_admissible` and :func:`reservation_transition_structurally_legal`.

**Anti-phantom greps recorded** (methodology playbook §2.C/§3.5 — negative-token
verification: existence AND absence claims below are both grepped, not asserted):

* ``git grep -n "class WriterEpoch\\|WriterEpoch =" tos/src/tos`` (before this
  module) -> empty. No existing ``WriterEpoch`` type. Every existing RCL epoch
  field is a bare ``int | None``
  (``tos.rcl.state.FenceCoordinates.expected_writer_epoch``,
  ``tos.rcl.state.WriterFenceState.writer_epoch_floor``). ``WriterEpoch`` below is
  a **type alias for ``int``**, matching that convention, not a new wrapper record.
* ``tos/src/tos/authority/records.py`` (read per the build instruction) defines
  ``AuthorityEpochTransitionRecord.old_epoch``/``.new_epoch`` — but that is the
  **Safety Authority epoch** (``safety_authority_epoch`` domain), a *different*
  governed namespace from the RCL Writer Epoch. ADR-002-012 §5.5 (line 129-131)
  is explicit: "Consensus term, process generation, and Writer Epoch MAY be
  related but SHALL NOT be treated as equivalent unless the implementation
  proves the mapping survives membership change, restore, and failover." Reusing
  ``AuthorityEpochTransitionRecord`` as ``WriterEpoch`` would silently assert that
  unproven equivalence. **Conflict reported, not resolved by force-reuse**: this
  module keeps ``WriterEpoch`` as the bare-``int`` RCL-local convention instead.
* ``git grep -n "RESERVED\\b\\|CONFIRMED\\b\\|QUARANTINED\\b" tos/src/tos/rcl
  tos/src/tos/engine`` -> no :class:`~tos.rcl.vocabulary.CapacityState` member is
  literally spelled ``RESERVED`` / ``CONFIRMED`` / ``QUARANTINED`` (design #40
  D2.1's own shorthand for the reservation lifecycle, line 64: "``RESERVED →
  POTENTIALLY_LIVE → (CONFIRMED|RELEASED|QUARANTINED)``"). The real
  reservation-state enum is :class:`~tos.rcl.vocabulary.CapacityState` (9
  members, ADR-002-002 §10.1 line 506-562) — already reused for exactly this
  purpose by ``tos.engine.state.ProvisionalReservationLedger``
  (``PROJECTION_ORDER``). **Conflict reported, not resolved by inventing a
  parallel enum**: D2.1's 5-name shorthand has no 1:1 literal match.
  ``POTENTIALLY_LIVE`` and ``RELEASED`` match verbatim. ``RESERVED`` has two
  structural analogs (``COMMITTED_UNBOUND`` / ``ATTEMPT_BOUND`` — both pre-live,
  un-consumed). ``CONFIRMED`` maps most closely to ``POSITION_CONSUMED`` (a full,
  broker-confirmed fill — see ``tos.engine.state._RESULT_TRANSITIONS[FULL_FILL]``).
  ``QUARANTINED`` maps to ``QUARANTINED_UNKNOWN``.
  :class:`CapacityReservationTransition` below types ``from_state``/``to_state``
  as the real 9-member :class:`~tos.rcl.vocabulary.CapacityState` — never a new
  enum — and :func:`release_admissible` documents its ``CONFIRMED``-analog choice
  explicitly rather than silently picking one.
* ``git grep -n "class CommitLog" tos/src/tos`` (before this module) -> empty: no
  prior port under this name.

Pure module: ``pydantic`` + stdlib (``enum``, ``typing``, ``collections.abc``) +
``tos.canonical`` + ``tos.rcl`` only — no ``shared.*``, no ``tos.evidence`` /
``tos.capsule`` / ``tos.authority`` (design #40 §0 kernel-PORT-only scope; the
``tos.authority`` non-reuse is the epoch conflict above), no ``sqlite3`` /
``socket`` / ``os`` / ``time`` / ``datetime`` (D1 not ratified — actively verified
by ``tos/tests/rcl/test_rcl_commitlog.py``'s import-closure/absence test).
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from tos.canonical import RecordPairKind, classify_record_pair
from tos.rcl._base import FrozenModel
from tos.rcl.predicates import transition_allowed
from tos.rcl.vocabulary import CapacityState, CommandType, TransitionCause

__all__ = [
    "AppendRefusalReason",
    "AppendReceipt",
    "AppendRefusal",
    "CapacityReservationTransition",
    "CommitEntry",
    "CommitLog",
    "LogView",
    "WriterEpoch",
    "duplicate_command",
    "release_admissible",
    "replay_reproduces_state",
    "reservation_transition_structurally_legal",
    "stale_writer_epoch",
]

#: A Writer Epoch is a bare, monotonically increasing integer (ADR-002-012 §5.5,
#: line 129: "A monotonically increasing RCL generation activated by a committed
#: command. It fences state-changing commands from every earlier writer
#: generation."). Kept as a plain ``int`` alias — matching every existing RCL
#: epoch field's convention — rather than a wrapper record (see the module
#: docstring's anti-phantom grep on ``AuthorityEpochTransitionRecord``: that type
#: models a *different* epoch namespace and reusing it would assert an unproven
#: equivalence ADR-002-012 §5.5 explicitly forbids).
WriterEpoch = int


# ===========================================================================
# closed refusal vocabulary
# ===========================================================================


class AppendRefusalReason(StrEnum):
    """Closed vocabulary of reasons ``CommitLog.append_cas`` may refuse (D2.1 ①②⑦).

    Every reason is a **structural** refusal — no free-text substitute is
    representable at the type level. ``STALE_EPOCH`` / ``SEQ_MISMATCH`` are the
    CAS-fencing pair (ADR-002-012 §9 line 259-260 "expected revision" /
    Writer-Epoch check); ``DUPLICATE_COMMAND_ID`` / ``COMMAND_BYTES_MISMATCH`` are
    the idempotency-vs-conflict pair (ADR-012 §9 line 270; RCLP-INV-006);
    ``STORE_UNAVAILABLE`` / ``PARTIAL_COMMIT_SUSPECTED`` are the D2.1 ⑦
    fail-closed storage-failure pair; ``INTEGRITY_VIOLATION`` is the D2.1 ⑤
    replay-corruption outcome.
    """

    STALE_EPOCH = "STALE_EPOCH"
    SEQ_MISMATCH = "SEQ_MISMATCH"
    DUPLICATE_COMMAND_ID = "DUPLICATE_COMMAND_ID"
    COMMAND_BYTES_MISMATCH = "COMMAND_BYTES_MISMATCH"
    STORE_UNAVAILABLE = "STORE_UNAVAILABLE"
    PARTIAL_COMMIT_SUSPECTED = "PARTIAL_COMMIT_SUSPECTED"
    INTEGRITY_VIOLATION = "INTEGRITY_VIOLATION"


# ===========================================================================
# pure data models (no digest-binding identity — port-level transport records,
# not IndependentIdArtifact ledger citizens; FrozenModel per RCL design §0.4a)
# ===========================================================================


class CommitEntry(FrozenModel):
    """One command as it is submitted for / held in the Safety Commit Log (§9).

    ``command_digest`` and ``payload_digest`` are **opaque strings** — no hashing
    happens in this module (digest computation is a canonicalization concern
    outside the port, ``tos.canonical`` / the future runtime). ``kind`` reuses the
    already-ratified :class:`~tos.rcl.vocabulary.CommandType` closed vocabulary
    (ADR-002-012 §10 / ADR-002-002 §27) rather than a free-text label.
    """

    seq: int | None = None
    writer_epoch: WriterEpoch | None = None
    command_id: str | None = None
    command_digest: str | None = None
    kind: CommandType | None = None
    payload_digest: str | None = None


class AppendReceipt(FrozenModel):
    """Proof of one durable commit (D2.1 ⑦: no "recorded" claim without one).

    ``durable`` is typed ``Literal[True]`` — there is no ``False`` variant to
    construct, so "an ``AppendReceipt`` exists" already **is** the durability
    claim; a failed / partial write returns :class:`AppendRefusal` instead, never
    an ``AppendReceipt`` with a false flag (ADR-002-012 line 482 "Projection lag,
    duplication, reordering, omission, or replay SHALL NOT... create permission").
    """

    seq: int | None = None
    writer_epoch: WriterEpoch | None = None
    durable: Literal[True] = True


class AppendRefusal(FrozenModel):
    """A structural, evidence-bearing refusal of ``append_cas`` (D2.1 ①②⑦)."""

    reason: AppendRefusalReason | None = None
    detail: str | None = None


class LogView(FrozenModel):
    """A linearizable read snapshot: current epoch + last seq + entries (§8.4).

    Produced only under a current-epoch check taken in the same transaction as
    the ``seq`` snapshot (ADR-002-012 line 243, §8.4 "Permissive reads SHALL use
    a quorum-confirmed read, read-index protocol, committed no-op barrier, or
    equivalent linearizable mechanism"). ``entries`` is position-ordered.
    """

    epoch: WriterEpoch | None = None
    last_seq: int | None = None
    entries: tuple[CommitEntry, ...] = ()


class CapacityReservationTransition(FrozenModel):
    """One committed reservation-lifecycle transition (design #40 D2.1 line 64).

    ``from_state``/``to_state`` are the real, already-ratified 9-member
    :class:`~tos.rcl.vocabulary.CapacityState` (ADR-002-002 §10.1) — reused
    verbatim per the module docstring's anti-phantom grep, never a parallel
    ``RESERVED``/``CONFIRMED``/``QUARANTINED`` enum. ``mark_potentially_live``'s
    authority transition (D2.1 line 64: "처음으로 RCL 소유가 된다") is represented
    here as a transition whose ``to_state`` is ``POTENTIALLY_LIVE``; the current
    ``tos.engine`` projection (``ProvisionalReservationLedger``) is a downstream,
    non-authoritative read projection of exactly this record (design §0 note:
    "현행 engine 투영은 이 로그의 읽기 투영으로 강등").
    """

    reservation_id: str | None = None
    seq: int | None = None
    writer_epoch: WriterEpoch | None = None
    from_state: CapacityState | None = None
    to_state: CapacityState | None = None


# ===========================================================================
# the port (D2.1 line 65: pure signatures, no default implementation)
# ===========================================================================


@runtime_checkable
class CommitLog(Protocol):
    """The Safety Commit Log port (design #40 D2.1 line 65; ADR-002-012 §1/§5-§9).

    "런타임 sqlite 구현과 미래의 복제 구현이 같은 포트를 만족한다. 커널은 포트만
    알고 구현을 모른다" (D2.1 line 65). This kernel module declares **only** the
    Protocol — no default implementation lives here (D1 not ratified, module
    docstring). ``tos_runtime.rcl.SqliteCommitLog`` (D2.1's chosen Phase 2
    implementation) satisfies this structurally once ``tos/runtime/`` lands.
    """

    def current_epoch(self) -> WriterEpoch:
        """Return the currently active Writer Epoch (ADR-002-012 §5.5, line 129)."""
        ...

    def append_cas(
        self,
        entry: CommitEntry,
        *,
        expected_seq: int,
        writer_epoch: WriterEpoch,
    ) -> AppendReceipt | AppendRefusal:
        """Compare-and-set append: admit ``entry`` iff ``expected_seq``/``writer_epoch``
        are current in the same transaction (ADR-002-012 §9 line 259-260 command
        envelope + §5.5 fencing); else return a structural
        :class:`AppendRefusal` — never a partial or silent failure (D2.1 ⑦).
        """
        ...

    def read_linearizable(self, *, writer_epoch: WriterEpoch) -> LogView:
        """Return a linearizable :class:`LogView` under a current-epoch read barrier
        (ADR-002-012 §8.4, line 243).
        """
        ...

    def replay(self) -> Iterator[CommitEntry]:
        """Replay the full committed log in commit order (ADR-002-012 §17.1, line
        425 "An authoritative snapshot SHALL bind..."; D2.1 ⑤ — the caller
        cross-checks the replayed state digest via
        :func:`replay_reproduces_state`).
        """
        ...


# ===========================================================================
# pure fault-contract predicates (D2.1 ①②⑤⑦; positive-admit, None never admits
# — methodology playbook §2.A/§3.6)
# ===========================================================================


def stale_writer_epoch(
    current: WriterEpoch | None,
    attempted: WriterEpoch | None,
) -> AppendRefusalReason | None:
    """D2.1 fault ① — reject a write whose Writer Epoch is not the current one.

    "모든 쓰기는 «내 epoch == 현재 epoch» 를 같은 트랜잭션에서 검사한다 → stale
    epoch writer 의 쓰기는 구조적으로 거부한다" (design #40 D2.1 line 62). The
    check is **equality**, not "at or above" — a single-node log has no concept
    of a legitimately higher unseen epoch arriving out of band (D2.1 line 62: "OS
    파일 잠금은 보조이지 정체성이 아니다"). Fail-closed: either coordinate being
    ``None`` (UNKNOWN currentness) refuses (methodology §2.A — a ``None``
    coordinate is never treated as a match).

    Args:
        current: The Writer Epoch the log currently holds (``current_epoch()``).
        attempted: The Writer Epoch the writer attached to this write.

    Returns:
        :data:`AppendRefusalReason.STALE_EPOCH` if not provably current, else
        ``None`` (admit).
    """
    if current is None or attempted is None:
        return AppendRefusalReason.STALE_EPOCH
    if attempted != current:
        return AppendRefusalReason.STALE_EPOCH
    return None


def duplicate_command(
    existing_digest_for_id: str | None,
    attempted_digest: str | None,
) -> AppendRefusalReason | None:
    """D2.1 fault ② — classify a command against any prior entry sharing its id.

    Reuses the already-ratified :func:`tos.canonical.classify_record_pair`
    (the same pairwise-conflict classifier ``tos.rcl.predicates.apply_committed``
    uses for command idempotency, RCLP-INV-006) rather than re-deriving digest
    comparison. Same id + same bytes => :data:`~AppendRefusalReason.DUPLICATE_COMMAND_ID`
    (the *second* commit of an already-applied command is refused — the first
    stands; ADR-012 §9 line 270). Same id + different bytes =>
    :data:`~AppendRefusalReason.COMMAND_BYTES_MISMATCH` (contain, no
    last-write-wins). Fail-closed: an attempted digest of ``None`` can never
    prove sameness, so it is conservatively classified as a bytes mismatch
    rather than silently admitted.

    Args:
        existing_digest_for_id: The canonical digest already committed under this
            command id, or ``None`` if no prior entry exists for this id (a fresh
            command — admits).
        attempted_digest: The canonical digest of the command now being appended.

    Returns:
        The :class:`AppendRefusalReason`, or ``None`` iff no prior entry exists
        for this command id (admit — nothing to conflict with).
    """
    if existing_digest_for_id is None:
        return None
    kind = classify_record_pair(
        "_same_command_id",
        existing_digest_for_id,
        "_same_command_id",
        attempted_digest,
    )
    if kind is RecordPairKind.IDEMPOTENT_DUP:
        return AppendRefusalReason.DUPLICATE_COMMAND_ID
    # CRITICAL_CONFLICT (differing bytes) or NOT_COMPARABLE (attempted_digest is
    # None, UNKNOWN) both fail closed to the same contained-conflict reason.
    return AppendRefusalReason.COMMAND_BYTES_MISMATCH


def replay_reproduces_state(
    replayed_digest: str | None,
    held_digest: str | None,
) -> AppendRefusalReason | None:
    """D2.1 fault ⑤ — cross-check a full replay against the authoritative state digest.

    ADR-002-012 line 491: "Independent replay SHALL reproduce the same
    deterministic state from the same committed prefix or identify corruption
    and remain non-live." Fail-closed: either digest being ``None`` (unprovable
    reproduction) is treated as corruption, not a pass.

    Args:
        replayed_digest: The state digest recomputed by folding
            :meth:`CommitLog.replay` (:func:`tos.rcl.predicates.fold_commands` or
            equivalent).
        held_digest: The authoritative state digest the log claims to hold.

    Returns:
        :data:`AppendRefusalReason.INTEGRITY_VIOLATION` if reproduction is not
        provably exact, else ``None``.
    """
    if replayed_digest is None or held_digest is None:
        return AppendRefusalReason.INTEGRITY_VIOLATION
    if replayed_digest != held_digest:
        return AppendRefusalReason.INTEGRITY_VIOLATION
    return None


#: The reservation-lifecycle destinations that require a finality witness before
#: admission (design #40 D2.1 line 64's ``CONFIRMED``/``RELEASED`` shorthand,
#: mapped onto the real :class:`~tos.rcl.vocabulary.CapacityState` per the module
#: docstring's anti-phantom grep: ``RELEASED`` matches verbatim; ``CONFIRMED``'s
#: closest analog is ``POSITION_CONSUMED``, a full broker-confirmed fill).
_WITNESS_REQUIRED_DESTINATIONS: frozenset[CapacityState] = frozenset(
    {CapacityState.RELEASED, CapacityState.POSITION_CONSUMED}
)


def release_admissible(
    transition: CapacityReservationTransition,
    finality_witness: bool | None,
) -> bool:
    """Whether a reservation transition to a finality state may be admitted.

    "해제(release)는 broker truth 또는 evidence 가 확정한 종결만이 트리거이며
    자동 re-arm 없음" (design #40 D2.1 line 64); ADR-002-012 line 37: "Quorum
    restoration, leader election, node restart, snapshot restore, or membership
    recovery SHALL NOT automatically re-arm live operation or revive a prior
    capability." A transition landing on :data:`~CapacityState.RELEASED` or its
    ``CONFIRMED``-analog :data:`~CapacityState.POSITION_CONSUMED` (see
    :data:`_WITNESS_REQUIRED_DESTINATIONS`) admits **only** when
    ``finality_witness is True`` — an explicit, positively-proven broker-truth /
    evidence witness (methodology §2.A: ``is True``, never a truthy coercion, so
    ``None``/UNKNOWN never admits). Every other destination — in particular
    ``POTENTIALLY_LIVE``, which "never auto-releases" by never reaching this gate
    at all — is unconditionally admissible here (cause-level legality is
    :func:`reservation_transition_structurally_legal`'s separate concern).

    Args:
        transition: The proposed reservation-lifecycle transition.
        finality_witness: The broker-truth / evidence witness, or ``None`` if
            none was supplied.

    Returns:
        ``False`` if the destination is unknown or requires an absent/unproven
        witness; ``True`` otherwise.
    """
    if transition.to_state is None:
        return False
    if transition.to_state not in _WITNESS_REQUIRED_DESTINATIONS:
        return True
    return finality_witness is True


#: The closed whitelist of structurally legal ``(from_state, to_state)`` pairs —
#: everything else is illegal (D2.1 line 64). Derived, not hand-authored: a pair
#: is legal iff :func:`tos.rcl.predicates.transition_allowed` (the already-ratified
#: ADR-002-002 §10.2 conservatism lattice) admits it under **some**
#: :class:`~tos.rcl.vocabulary.TransitionCause` — reusing the ratified predicate
#: instead of re-deriving the conservatism rank a second time (DRY; methodology
#: playbook §2.D). Because ``transition_allowed`` rejects only ``from_state is
#: RELEASED`` unconditionally (every other pair is reachable under at least one
#: cause — a decrease needs only a non-weak cause, and a move to ``RELEASED``
#: needs only ``FINAL_QUANTITY_PROOF``, both of which always exist), this
#: whitelist is exactly "every pair except a transition away from the terminal
#: ``RELEASED`` state" (ADR-002-002 §10.1 line 562: "RELEASED is terminal for the
#: reservation identity") — the one structural invariant this cause-agnostic,
#: log-layer gate is responsible for; cause-specific gating (weak-cause /
#: ``FINAL_QUANTITY_PROOF`` requirements) stays owned by
#: :func:`~tos.rcl.predicates.transition_allowed` at the authority layer, not
#: duplicated here.
_LEGAL_RESERVATION_TRANSITIONS: frozenset[tuple[CapacityState, CapacityState]] = (
    frozenset(
        (from_state, to_state)
        for from_state in CapacityState
        for to_state in CapacityState
        if any(
            transition_allowed(from_state, to_state, cause) for cause in TransitionCause
        )
    )
)


def reservation_transition_structurally_legal(
    from_state: CapacityState | None,
    to_state: CapacityState | None,
) -> bool:
    """Whether ``(from_state, to_state)`` is a structurally legal reservation transition.

    **Renamed from ``reservation_transition_legal`` (independent-review LOW
    finding, 2026-09-08) — no behaviour change, name-only.** The prior name read
    broader than the check: this predicate is cause-agnostic and admits 72 of the
    81 ``CapacityState`` pairs (every pair except a transition away from the
    terminal ``RELEASED`` state, per the ``_LEGAL_RESERVATION_TRANSITIONS``
    docstring above) — it does **not** enforce ADR-002-002 §10.2's "a weak cause
    cannot lower conservatism" requirement, which is a *cause-specific* check
    :func:`tos.rcl.predicates.transition_allowed` alone owns. ``_structurally_``
    makes that scope explicit in the name itself.

    A pure membership test against the closed, derived
    :data:`_LEGAL_RESERVATION_TRANSITIONS` whitelist — "everything else illegal"
    (fail-closed by construction: an unmapped or ``None`` state is never
    admitted).

    **This predicate alone never admits a transition.** A runtime MUST also
    evaluate :func:`tos.rcl.predicates.transition_allowed` with the concrete
    :class:`~tos.rcl.vocabulary.TransitionCause` in effect before applying a
    transition — this function only proves the pair is *reachable under some*
    cause (structural shape), never that the actual cause at hand justifies it
    (cause-level legality, the authority-layer concern this predicate explicitly
    does not duplicate).

    Args:
        from_state: The reservation's current capacity state.
        to_state: The proposed next capacity state.

    Returns:
        ``True`` iff the pair is in the closed whitelist.
    """
    if from_state is None or to_state is None:
        return False
    return (from_state, to_state) in _LEGAL_RESERVATION_TRANSITIONS
