"""RCL Safety Commit Log port + fault-contract predicates (design #40 D2.1).

Covers ``tos.rcl.commitlog``: Protocol conformance (via a test-only in-memory
double — never a src-level default implementation, per D1 not being ratified
yet), the D2.1 ①②⑤⑦ fault-contract predicates (positive/negative/None-polarity
cases), the derived legal-transition whitelist's exhaustiveness over the full
:class:`~tos.rcl.vocabulary.CapacityState` product, the closed refusal-reason
vocabulary's member count, and an import-closure/absence check isomorphic to
``test_rcl_import_closure.py`` but scoped to ``commitlog.py`` alone (verifying
the module's own "no I/O" claim: no ``sqlite3`` / ``os`` / ``socket`` / ``time`` /
``datetime``, and — per the epoch-conflict note in its docstring — no
``tos.authority``).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from tos.rcl import (
    AppendReceipt,
    AppendRefusal,
    AppendRefusalReason,
    CapacityReservationTransition,
    CapacityState,
    CommitEntry,
    CommitLog,
    LogView,
    TransitionCause,
    WriterEpoch,
    duplicate_command,
    release_admissible,
    replay_reproduces_state,
    reservation_transition_legal,
    stale_writer_epoch,
    transition_allowed,
)

_COMMITLOG_SRC = (
    Path(__file__).resolve().parent.parent.parent
    / "src"
    / "tos"
    / "rcl"
    / "commitlog.py"
)

CAPACITY_STATES = st.sampled_from(list(CapacityState))
TRANSITION_CAUSES = st.sampled_from(list(TransitionCause))


# ===========================================================================
# Protocol conformance — test-only in-memory double (never a src default impl;
# D1 / tos.runtime is not ratified — module docstring)
# ===========================================================================


class _InMemoryCommitLogDouble:
    """A minimal, test-only :class:`CommitLog` satisfier — no durability, no I/O.

    Exists solely to prove the Protocol's four-method shape is implementable and
    callable; it is not a candidate runtime implementation (that is
    ``tos_runtime.rcl.SqliteCommitLog``, D2.1, out of kernel scope).
    """

    def __init__(self) -> None:
        self._epoch: WriterEpoch = 1
        self._entries: list[CommitEntry] = []

    def current_epoch(self) -> WriterEpoch:
        return self._epoch

    def append_cas(
        self,
        entry: CommitEntry,
        *,
        expected_seq: int,
        writer_epoch: WriterEpoch,
    ) -> AppendReceipt | AppendRefusal:
        if writer_epoch != self._epoch:
            return AppendRefusal(reason=AppendRefusalReason.STALE_EPOCH)
        if expected_seq != len(self._entries):
            return AppendRefusal(reason=AppendRefusalReason.SEQ_MISMATCH)
        self._entries.append(entry)
        return AppendReceipt(seq=expected_seq, writer_epoch=writer_epoch)

    def read_linearizable(self, *, writer_epoch: WriterEpoch) -> LogView:
        if writer_epoch != self._epoch:
            # A read under a non-current epoch proves nothing linearizable — the
            # double reports no entries rather than the (possibly stale) state.
            return LogView(epoch=self._epoch, last_seq=None, entries=())
        return LogView(
            epoch=self._epoch,
            last_seq=len(self._entries) - 1 if self._entries else None,
            entries=tuple(self._entries),
        )

    def replay(self) -> Iterator[CommitEntry]:
        yield from self._entries


def test_double_satisfies_commitlog_protocol_structurally() -> None:
    """(conformance) The in-memory double is recognized by the runtime_checkable Protocol."""
    double = _InMemoryCommitLogDouble()
    assert isinstance(double, CommitLog)


def test_double_exercises_full_append_read_replay_cycle() -> None:
    """(conformance) Every Protocol method is callable with the documented signature."""
    double = _InMemoryCommitLogDouble()
    epoch = double.current_epoch()
    entry = CommitEntry(
        seq=0, writer_epoch=epoch, command_id="cmd-1", command_digest="d1"
    )
    receipt = double.append_cas(entry, expected_seq=0, writer_epoch=epoch)
    assert isinstance(receipt, AppendReceipt)
    assert receipt.durable is True

    view = double.read_linearizable(writer_epoch=epoch)
    assert view.entries == (entry,)

    replayed = list(double.replay())
    assert replayed == [entry]


def test_double_refuses_stale_epoch_and_seq_mismatch() -> None:
    """(conformance) The double actually refuses — proves the union type is exercised both ways."""
    double = _InMemoryCommitLogDouble()
    epoch = double.current_epoch()
    entry = CommitEntry(seq=0, writer_epoch=epoch, command_id="cmd-1")

    stale = double.append_cas(entry, expected_seq=0, writer_epoch=epoch + 1)
    assert isinstance(stale, AppendRefusal)
    assert stale.reason is AppendRefusalReason.STALE_EPOCH

    bad_seq = double.append_cas(entry, expected_seq=5, writer_epoch=epoch)
    assert isinstance(bad_seq, AppendRefusal)
    assert bad_seq.reason is AppendRefusalReason.SEQ_MISMATCH


# ===========================================================================
# D2.1 fault ① — stale_writer_epoch
# ===========================================================================


def test_stale_writer_epoch_matching_epoch_admits() -> None:
    assert stale_writer_epoch(5, 5) is None


def test_stale_writer_epoch_mismatch_refuses() -> None:
    assert stale_writer_epoch(5, 4) is AppendRefusalReason.STALE_EPOCH
    assert stale_writer_epoch(5, 6) is AppendRefusalReason.STALE_EPOCH


def test_stale_writer_epoch_none_current_refuses() -> None:
    """(canary) UNKNOWN current epoch fails closed, never admits (§2.A None-axis)."""
    assert stale_writer_epoch(None, 5) is AppendRefusalReason.STALE_EPOCH


def test_stale_writer_epoch_none_attempted_refuses() -> None:
    """(canary) UNKNOWN attempted epoch fails closed, never admits."""
    assert stale_writer_epoch(5, None) is AppendRefusalReason.STALE_EPOCH


def test_stale_writer_epoch_both_none_refuses() -> None:
    assert stale_writer_epoch(None, None) is AppendRefusalReason.STALE_EPOCH


@given(epoch=st.integers(min_value=0, max_value=1000))
def test_stale_writer_epoch_self_equal_always_admits(epoch: int) -> None:
    assert stale_writer_epoch(epoch, epoch) is None


# ===========================================================================
# D2.1 fault ② — duplicate_command
# ===========================================================================


def test_duplicate_command_no_prior_entry_admits() -> None:
    """No existing digest for this id => nothing to conflict with => admit."""
    assert duplicate_command(None, "any-digest") is None
    assert duplicate_command(None, None) is None


def test_duplicate_command_same_bytes_is_duplicate() -> None:
    assert (
        duplicate_command("digest-a", "digest-a")
        is AppendRefusalReason.DUPLICATE_COMMAND_ID
    )


def test_duplicate_command_different_bytes_is_mismatch() -> None:
    assert (
        duplicate_command("digest-a", "digest-b")
        is AppendRefusalReason.COMMAND_BYTES_MISMATCH
    )


def test_duplicate_command_attempted_none_with_existing_entry_fails_closed() -> None:
    """(canary) An UNKNOWN attempted digest against a real prior entry can never
    resolve to DUPLICATE_COMMAND_ID (that would assert an unproven sameness)."""
    assert (
        duplicate_command("digest-a", None)
        is AppendRefusalReason.COMMAND_BYTES_MISMATCH
    )


# ===========================================================================
# D2.1 fault ⑤ — replay_reproduces_state
# ===========================================================================


def test_replay_reproduces_state_matching_digests_admits() -> None:
    assert replay_reproduces_state("digest-x", "digest-x") is None


def test_replay_reproduces_state_mismatch_is_integrity_violation() -> None:
    assert (
        replay_reproduces_state("digest-x", "digest-y")
        is AppendRefusalReason.INTEGRITY_VIOLATION
    )


def test_replay_reproduces_state_none_replayed_fails_closed() -> None:
    assert (
        replay_reproduces_state(None, "digest-x")
        is AppendRefusalReason.INTEGRITY_VIOLATION
    )


def test_replay_reproduces_state_none_held_fails_closed() -> None:
    assert (
        replay_reproduces_state("digest-x", None)
        is AppendRefusalReason.INTEGRITY_VIOLATION
    )


def test_replay_reproduces_state_both_none_fails_closed() -> None:
    assert (
        replay_reproduces_state(None, None) is AppendRefusalReason.INTEGRITY_VIOLATION
    )


# ===========================================================================
# release_admissible
# ===========================================================================


def test_release_admissible_released_requires_true_witness() -> None:
    transition = CapacityReservationTransition(to_state=CapacityState.RELEASED)
    assert release_admissible(transition, True) is True
    assert release_admissible(transition, False) is False
    assert release_admissible(transition, None) is False


def test_release_admissible_confirmed_analog_requires_true_witness() -> None:
    """POSITION_CONSUMED is the documented CONFIRMED analog — same witness gate."""
    transition = CapacityReservationTransition(to_state=CapacityState.POSITION_CONSUMED)
    assert release_admissible(transition, True) is True
    assert release_admissible(transition, None) is False


def test_release_admissible_potentially_live_never_needs_witness() -> None:
    """POTENTIALLY_LIVE "never auto-releases" — it simply never reaches the gate."""
    transition = CapacityReservationTransition(to_state=CapacityState.POTENTIALLY_LIVE)
    assert release_admissible(transition, None) is True
    assert release_admissible(transition, False) is True


def test_release_admissible_unknown_destination_fails_closed() -> None:
    transition = CapacityReservationTransition(to_state=None)
    assert release_admissible(transition, True) is False


@given(state=CAPACITY_STATES)
def test_release_admissible_never_admits_finality_states_without_true_witness(
    state: CapacityState,
) -> None:
    """(canary, both-ways) Every finality state refuses False/None; non-finality states
    are unconditionally admissible — proves the gate is neither vacuously open nor
    vacuously closed (methodology §3.7)."""
    transition = CapacityReservationTransition(to_state=state)
    is_finality = state in (CapacityState.RELEASED, CapacityState.POSITION_CONSUMED)
    assert release_admissible(transition, None) is (not is_finality)
    assert release_admissible(transition, False) is (not is_finality)
    assert release_admissible(transition, True) is True


# ===========================================================================
# reservation_transition_legal — closed whitelist exhaustiveness
# ===========================================================================


def test_reservation_transition_legal_none_never_admits() -> None:
    assert reservation_transition_legal(None, CapacityState.POTENTIALLY_LIVE) is False
    assert reservation_transition_legal(CapacityState.POTENTIALLY_LIVE, None) is False
    assert reservation_transition_legal(None, None) is False


def test_reservation_transition_legal_from_released_is_always_illegal() -> None:
    """RELEASED is terminal (ADR-002-002 §10.1 line 562) — no transition may leave it."""
    for to_state in CapacityState:
        assert reservation_transition_legal(CapacityState.RELEASED, to_state) is False


def test_reservation_transition_legal_from_non_released_is_always_legal() -> None:
    """Every pair whose origin is not RELEASED is reachable under some cause."""
    for from_state in CapacityState:
        if from_state is CapacityState.RELEASED:
            continue
        for to_state in CapacityState:
            assert reservation_transition_legal(from_state, to_state) is True


@given(from_state=CAPACITY_STATES, to_state=CAPACITY_STATES)
def test_reservation_transition_legal_matches_any_cause_derivation(
    from_state: CapacityState, to_state: CapacityState
) -> None:
    """(exhaustiveness, hypothesis over the full enum product) The whitelist's
    membership for every pair equals "legal under at least one TransitionCause"
    per the already-ratified transition_allowed — proving the closed whitelist
    was not hand-drifted from its own derivation rule."""
    expected = any(
        transition_allowed(from_state, to_state, cause) for cause in TransitionCause
    )
    assert reservation_transition_legal(from_state, to_state) is expected


def test_reservation_transition_legal_whitelist_pair_count() -> None:
    """9 origins x 9 destinations, minus the 9 pairs whose origin is RELEASED."""
    n = len(list(CapacityState))
    legal_count = sum(
        1
        for from_state in CapacityState
        for to_state in CapacityState
        if reservation_transition_legal(from_state, to_state)
    )
    assert legal_count == n * n - n


# ===========================================================================
# closed refusal vocabulary — member count pin
# ===========================================================================


def test_append_refusal_reason_member_count_pin() -> None:
    """Pins the closed vocabulary at exactly the 7 D2.1 ①②⑦ reasons (regression
    anchor — an addition/removal here is a deliberate vocabulary change, not a
    silent drift)."""
    assert len(list(AppendRefusalReason)) == 7
    assert {member.value for member in AppendRefusalReason} == {
        "STALE_EPOCH",
        "SEQ_MISMATCH",
        "DUPLICATE_COMMAND_ID",
        "COMMAND_BYTES_MISMATCH",
        "STORE_UNAVAILABLE",
        "PARTIAL_COMMIT_SUSPECTED",
        "INTEGRITY_VIOLATION",
    }


# ===========================================================================
# import-closure / absence — commitlog.py's own "no I/O" claim (isomorphic to
# test_rcl_import_closure.py, scoped to this one file; no subprocess/os — both
# firewall-forbidden even in tests, so this stays a static AST scan)
# ===========================================================================

#: Root module names commitlog.py is allowed to import (module docstring's
#: closure claim). Anything else is a leak.
_ALLOWED_ROOTS = frozenset({"__future__", "collections", "enum", "typing", "tos"})

#: Specifically-forbidden imports the module docstring calls out by name — these
#: would indicate D1 (runtime I/O) landing prematurely, or the reported
#: tos.authority epoch-namespace conflict being silently resolved by force-reuse.
_FORBIDDEN_MODULES = frozenset(
    {
        "sqlite3",
        "os",
        "socket",
        "time",
        "datetime",
        "tos.authority",
        "tos.evidence",
        "tos.capsule",
    }
)


def _imported_module_roots(path: Path) -> set[str]:
    """Every module a file imports, both as written and as its root package."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_commitlog_source_exists() -> None:
    assert _COMMITLOG_SRC.is_file(), f"expected {_COMMITLOG_SRC} to exist"


def test_commitlog_imports_no_forbidden_module() -> None:
    """(absence, negative-token) None of sqlite3/os/socket/time/datetime/tos.authority
    /tos.evidence/tos.capsule is imported by commitlog.py — verifies both the
    "no I/O" and the reported epoch-namespace-conflict claims in its docstring."""
    imported = _imported_module_roots(_COMMITLOG_SRC)
    leaked = imported & _FORBIDDEN_MODULES
    assert leaked == set(), f"forbidden import(s) found in commitlog.py: {leaked}"


def test_commitlog_imports_only_allowed_roots() -> None:
    """(existence + closure) Every import's root package is in the allowed set."""
    imported = _imported_module_roots(_COMMITLOG_SRC)
    offenders = {name for name in imported if name.split(".")[0] not in _ALLOWED_ROOTS}
    assert offenders == set(), f"unexpected import root(s) in commitlog.py: {offenders}"


def test_forbidden_module_scan_detects_planted_leak(tmp_path: Path) -> None:
    """(both-ways canary) The scan actually catches a planted forbidden import —
    proves "green" above is evidence the checker works, not that it is neutered."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import sqlite3\nimport os\nfrom tos.authority import records\n",
        encoding="utf-8",
    )
    imported = _imported_module_roots(planted)
    leaked = imported & _FORBIDDEN_MODULES
    assert "sqlite3" in leaked
    assert "os" in leaked
    assert "tos.authority" in leaked
