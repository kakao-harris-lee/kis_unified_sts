"""Standing session approval — one operator artifact that approves a bounded set of step-4
proposals for ONE KIS MOCK stock session (operator decision 2026-10-24).

Why it exists. A per-proposal approval file (``approvals/<proposal_digest>.yaml``,
:mod:`tos_runtime.authority.iap`) binds a proposal digest, and every proposal binds its own
decision context capsule, so no operator can author that file before the proposal exists — and
nothing re-drives a proposal halted ``UNKNOWN`` at step 4. The first MOCK stock session would
send zero orders. The operator therefore writes ONE artifact before the open
(``approvals/standing-session.yaml``, ``tos-runtime write-standing-approval``) and this module
turns it into a per-proposal :class:`~tos.iap.IndependentApprovalDecision` only for a proposal
that falls inside every bound it names.

What bounds a use (all must hold; anything else is "not covered" and step 4 stays ``UNKNOWN``,
exactly as with no artifact at all):

* **MOCK only, by construction** — the active broker scope is the kernel's
  :func:`~tos.brokercap.mock_order_without_position_or_cash` class AND its bound INSTANCE profile
  is a host-bound ``BROKER_SIMULATION`` profile
  (:func:`~tos_runtime.brokercap.derive.is_mock_order_class`, the facts the gateway's item-6 skip
  reads). The artifact has no field that names an environment class, so no file, config or env
  value can extend this to a REAL, POSITION_OR_CASH or SYNTHETIC scope.
* the runtime's ``environment_label`` and admitted ``code_digest`` (the tenant tree release);
* the KST trading date (``trading_date_now`` through the trusted, fresh wall clock — ``None``
  outside every calendar session window, so the artifact expires at session close);
* the proposal's ``strategy_id`` (a content digest of the strategy) and instrument;
* the action — the proposal's ``position_effect`` and ``direction`` plus the command's ``SIDE``
  — must match one declared action exactly; the command's quantity must not exceed
  ``max_quantity``;
* per-action use caps.

Uses are durable. Each use is the ordinary IAP consumption commit — one content-addressed RCL
``CONSUME_APPROVAL_DECISION`` entry — under a slot id ``standing-approval:<date>:<action>:<n>``.
The free slot is chosen from the committed log, so a use that committed is counted after any
crash or restart, a use whose append did not commit (refused / rolled back) is not, and a slot is
never reused: a restart re-proposes with a new capsule, and that new command takes the NEXT slot.
Slots are keyed by trading date, not by artifact digest, so rewriting the artifact mid-day cannot
reset the count.

Integrity. Per-proposal approval files carry no signature; they are custody-gated (0600, owner
uid) and environment-label checked. This artifact gets the same gate, plus its canonical digest
(``tos.canonical``) is recorded once as ``APPROVAL_STANDING_BOUND`` and pinned for the life of the
process: a later read with a different digest is refused (``APPROVAL_STANDING_REFUSED``) until a
restart re-binds. Every committed use records ``APPROVAL_STANDING_CONSUMED`` linking the artifact
digest, the proposal digest and the RCL command id.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import StageRequest, StageVerdict
from tos.engine.vocabulary import StageOutcome
from tos.iap import ApprovalResult, IndependentApprovalDecision
from tos.ioc.vocabulary import ConformanceAxis
from tos.rcl import CommandType

from tos_runtime.authority.iap import LoadedApproval, _consumption_command_id
from tos_runtime.custody.file_custody import verify_file_mode_and_owner
from tos_runtime.rcl.log import SqliteCommitLog

__all__ = [
    "STANDING_APPROVAL_RELPATH",
    "STANDING_APPROVAL_SCHEMA",
    "StandingAction",
    "StandingApproval",
    "StandingApprovalError",
    "StandingApprovalSource",
    "load_standing_approval",
    "standing_approval_digest",
]

#: Where the artifact lives, relative to the custody root (next to the per-proposal files).
STANDING_APPROVAL_RELPATH = Path("approvals") / "standing-session.yaml"
STANDING_APPROVAL_SCHEMA = "tos-standing-session-approval/1"

#: Slot ids start with this token (inside the IAP ``iap-consumption:`` command id).
_SLOT_PREFIX = "standing-approval"
_CONSUMPTION_PREFIX = "iap-consumption"

_EVIDENCE_BOUND = "APPROVAL_STANDING_BOUND"
_EVIDENCE_REFUSED = "APPROVAL_STANDING_REFUSED"
_EVIDENCE_CONSUMED = "APPROVAL_STANDING_CONSUMED"
_EVIDENCE_NOT_COVERED = "APPROVAL_STANDING_NOT_COVERED"

_TOP_KEYS = frozenset(
    {
        "schema",
        "environment_label",
        "code_digest",
        "trading_date",
        "strategy_id",
        "instrument",
        "max_quantity",
        "actions",
        "trading_approval_policy_id",
        "trading_approval_policy_generation",
        "trading_approval_policy_digest",
    }
)
_ACTION_KEYS = frozenset({"position_effect", "direction", "side", "max_uses"})

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


class StandingApprovalError(RuntimeError):
    """The artifact is unreadable, fails custody, or is malformed — never an approval."""


@dataclass(frozen=True)
class StandingAction:
    """One declared action: the proposal's position effect and direction, the command's side,
    and how many times it may be used this session."""

    position_effect: str
    direction: str
    side: str
    max_uses: int

    @property
    def key(self) -> str:
        """The slot-id token for this action (``OPEN-LONG-<side>``)."""
        return f"{self.position_effect}-{self.direction}-{self.side}"


@dataclass(frozen=True)
class StandingApproval:
    """A parsed, digest-bound standing session approval."""

    digest: str
    environment_label: str
    code_digest: str
    trading_date: str
    strategy_id: str
    instrument: str
    max_quantity: int
    actions: tuple[StandingAction, ...]
    trading_approval_policy_id: str
    trading_approval_policy_generation: int
    trading_approval_policy_digest: str | None


def standing_approval_digest(raw: Mapping[str, Any]) -> str:
    """The artifact's canonical digest (the kernel's registered scheme, never a new one)."""
    return _SCHEME.compute_digest(raw)


def _require_str(raw: Mapping[str, Any], key: str, path: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value or value == "TBD":
        raise StandingApprovalError(f"{path}: {key!r} must be a non-empty string")
    return value


def _require_positive_int(raw: Mapping[str, Any], key: str, path: Path) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise StandingApprovalError(f"{path}: {key!r} must be a positive integer")
    return value


def _parse_actions(raw: Any, path: Path) -> tuple[StandingAction, ...]:
    if not isinstance(raw, list) or not raw:
        raise StandingApprovalError(f"{path}: 'actions' must be a non-empty list")
    actions: list[StandingAction] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != _ACTION_KEYS:
            raise StandingApprovalError(
                f"{path}: every action must carry exactly {sorted(_ACTION_KEYS)}"
            )
        actions.append(
            StandingAction(
                position_effect=_require_str(item, "position_effect", path),
                direction=_require_str(item, "direction", path),
                side=_require_str(item, "side", path),
                max_uses=_require_positive_int(item, "max_uses", path),
            )
        )
    keys = [a.key for a in actions]
    if len(set(keys)) != len(keys):
        raise StandingApprovalError(f"{path}: duplicate action {keys}")
    return tuple(actions)


def parse_standing_approval(raw: Any, path: Path) -> StandingApproval:
    """Parse ``raw`` strictly: exact key set, no defaults, no unknown field.

    Raises:
        StandingApprovalError: Any deviation.
    """
    if not isinstance(raw, dict) or set(raw) != _TOP_KEYS:
        got = sorted(raw) if isinstance(raw, dict) else type(raw).__name__
        raise StandingApprovalError(
            f"{path}: must be a mapping with exactly {sorted(_TOP_KEYS)} (got {got})"
        )
    if raw["schema"] != STANDING_APPROVAL_SCHEMA:
        raise StandingApprovalError(
            f"{path}: schema must be {STANDING_APPROVAL_SCHEMA!r}"
        )
    trading_date = _require_str(raw, "trading_date", path)
    if len(trading_date) != 8 or not trading_date.isdigit():
        raise StandingApprovalError(f"{path}: 'trading_date' must be YYYYMMDD")
    policy_digest = raw["trading_approval_policy_digest"]
    if policy_digest is not None and not isinstance(policy_digest, str):
        raise StandingApprovalError(
            f"{path}: 'trading_approval_policy_digest' must be a string or null"
        )
    return StandingApproval(
        digest=standing_approval_digest(raw),
        environment_label=_require_str(raw, "environment_label", path),
        code_digest=_require_str(raw, "code_digest", path),
        trading_date=trading_date,
        strategy_id=_require_str(raw, "strategy_id", path),
        instrument=_require_str(raw, "instrument", path),
        max_quantity=_require_positive_int(raw, "max_quantity", path),
        actions=_parse_actions(raw["actions"], path),
        trading_approval_policy_id=_require_str(
            raw, "trading_approval_policy_id", path
        ),
        trading_approval_policy_generation=_require_positive_int(
            raw, "trading_approval_policy_generation", path
        ),
        trading_approval_policy_digest=policy_digest,
    )


def load_standing_approval(
    path: Path, *, expected_owner_uid: int, getuid: Callable[[], int] = os.getuid
) -> StandingApproval:
    """Custody gate (0600, owner) BEFORE parsing, then a strict parse.

    Raises:
        StandingApprovalError: Custody, read, YAML or schema failure.
    """
    try:
        verify_file_mode_and_owner(
            path, expected_owner_uid=expected_owner_uid, getuid=getuid
        )
    except Exception as exc:  # noqa: BLE001 - re-raised under this module's own type
        raise StandingApprovalError(
            f"{path}: failed the custody mode/owner gate: {exc}"
        ) from exc
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise StandingApprovalError(f"{path}: unreadable or not YAML: {exc}") from exc
    return parse_standing_approval(raw, path)


@dataclass(frozen=True)
class _Covered:
    """A proposal the artifact covers, with the slot it will consume."""

    action: StandingAction
    slot: int
    command_digest: str


@dataclass(frozen=True)
class _PendingUse:
    decision_id: str
    rcl_command_id: str
    proposal_digest: str
    action_key: str
    slot: int
    command_id: str
    command_digest: str


class StandingApprovalSource:
    """Resolves step-4 decisions from the standing artifact (module docstring)."""

    def __init__(
        self,
        custody_root: Path,
        *,
        environment_label: str,
        code_digest: str,
        uid: int,
        mock_class: Callable[[], bool],
        trading_date_reader: Callable[[], str | None],
        construction_reader: Callable[[], Any],
        rcl_log: SqliteCommitLog,
        writer_epoch: int,
        evidence: Any,
        getuid: Callable[[], int] = os.getuid,
    ) -> None:
        """Wire the source over facts the composition root already owns.

        Args:
            custody_root: The custody root (artifact at :data:`STANDING_APPROVAL_RELPATH`).
            environment_label: This runtime's boot environment label.
            code_digest: This runtime's admitted source-tree digest (``RuntimeIdentity``).
            uid: Expected owner uid of the artifact (custody rule).
            mock_class: Whether the active scope + bound profile is the MOCK class
                (:func:`~tos_runtime.brokercap.derive.is_mock_order_class`) — re-read per call.
            trading_date_reader: The KST trading date (``YYYYMMDD``) now, or ``None``.
            construction_reader: Step 2's current ``CandidateConstruction`` (or ``None``).
            rcl_log: The RCL log uses are committed to and counted from.
            writer_epoch: The RCL writer epoch for linearizable reads.
            evidence: The durable evidence append port.
            getuid: Injectable ``os.getuid``.
        """
        self._path = custody_root / STANDING_APPROVAL_RELPATH
        self._environment_label = environment_label
        self._code_digest = code_digest
        self._uid = uid
        self._mock_class = mock_class
        self._trading_date_reader = trading_date_reader
        self._construction_reader = construction_reader
        self._rcl_log = rcl_log
        self._writer_epoch = writer_epoch
        self._evidence = evidence
        self._getuid = getuid
        self._bound_digest: str | None = None
        self._refused_digests: set[str] = set()
        self._not_covered_reasons: set[str] = set()
        self._pending: _PendingUse | None = None

    # ------------------------------------------------------------------ binding

    def bind_at_boot(self) -> None:
        """Bind (and evidence) the artifact if it is already present at boot — never on a
        non-MOCK runtime, where the artifact is not read at all."""
        if self._mock_class() is True and self._path.is_file():
            self._load_bound()

    def _load_bound(self) -> StandingApproval | None:
        """Load the artifact, binding its digest on first sight and refusing any other digest
        for the rest of this process."""
        try:
            approval = load_standing_approval(
                self._path, expected_owner_uid=self._uid, getuid=self._getuid
            )
        except StandingApprovalError as exc:
            self._refuse("unloadable", str(exc))
            return None
        if approval.environment_label != self._environment_label:
            self._refuse("environment_label_mismatch", approval.digest)
            return None
        if self._bound_digest is None:
            self._bound_digest = approval.digest
            self._evidence.append(
                {
                    "path": str(self._path),
                    "artifact_digest": approval.digest,
                    "trading_date": approval.trading_date,
                    "strategy_id": approval.strategy_id,
                    "instrument": approval.instrument,
                    "max_quantity": approval.max_quantity,
                    "actions": [
                        {"action": a.key, "max_uses": a.max_uses}
                        for a in approval.actions
                    ],
                },
                kind=_EVIDENCE_BOUND,
                record_class=_EVIDENCE_BOUND,
            )
        elif approval.digest != self._bound_digest:
            self._refuse("digest_changed_since_bound", approval.digest)
            return None
        return approval

    def _refuse(self, reason: str, detail: str) -> None:
        key = f"{reason}:{detail}"
        if key in self._refused_digests:
            return
        self._refused_digests.add(key)
        self._evidence.append(
            {"path": str(self._path), "reason": reason, "detail": detail},
            kind=_EVIDENCE_REFUSED,
            record_class=_EVIDENCE_REFUSED,
        )

    def _not_covered(self, reason: str) -> None:
        if reason in self._not_covered_reasons:
            return
        self._not_covered_reasons.add(reason)
        self._evidence.append(
            {"artifact_digest": self._bound_digest, "reason": reason},
            kind=_EVIDENCE_NOT_COVERED,
            record_class=_EVIDENCE_NOT_COVERED,
        )

    # ------------------------------------------------------------------ provider

    def provide(self, request: StageRequest) -> LoadedApproval | None:
        """The decision for ``request`` if the artifact covers it, else ``None``."""
        self._pending = None
        if self._mock_class() is not True:
            # Never MOCK: the artifact is not even read (stock MOCK only, by construction).
            return None
        if not self._path.is_file():
            return None
        approval = self._load_bound()
        if approval is None:
            return None
        covered = self._covered(approval, request)
        if covered is None:
            return None
        try:
            return self._issue(approval, request, covered)
        except (
            Exception
        ) as exc:  # noqa: BLE001 - a decision that cannot be issued grants nothing
            self._not_covered(f"decision_issue_failed:{type(exc).__name__}")
            return None

    def _covered(
        self, approval: StandingApproval, request: StageRequest
    ) -> _Covered | None:
        reason, action, command_digest = _bounds_verdict(
            approval,
            request,
            self._construction_reader(),
            code_digest=self._code_digest,
            trading_date=self._trading_date_reader(),
        )
        if reason is not None or action is None or command_digest is None:
            self._not_covered(reason or "unbounded")
            return None
        slot = self.free_slot(approval.trading_date, action)
        if slot is None:
            self._not_covered(f"uses_exhausted:{action.key}")
            return None
        return _Covered(action=action, slot=slot, command_digest=command_digest)

    def free_slot(self, trading_date: str, action: StandingAction) -> int | None:
        """The lowest uncommitted slot for ``action`` today, read from the committed log;
        ``None`` when every slot is used or the log cannot be read (fail closed)."""
        prefix = f"{_CONSUMPTION_PREFIX}:{_SLOT_PREFIX}:{trading_date}:{action.key}:"
        try:
            view = self._rcl_log.read_linearizable(writer_epoch=self._writer_epoch)
        except (
            Exception
        ):  # noqa: BLE001 - an unreadable log grants no use (fail closed)
            return None
        used: set[int] = set()
        for entry in view.entries:
            if entry.command_id is None or not entry.command_id.startswith(prefix):
                continue
            if entry.kind is not CommandType.CONSUME_APPROVAL_DECISION:
                return None  # a foreign kind under our prefix is corruption: no use
            token = entry.command_id[len(prefix) :].split(":", 1)[0]
            if not token.isdigit():
                return None
            used.add(int(token))
        for slot in range(1, action.max_uses + 1):
            if slot not in used:
                return slot
        return None

    def _issue(
        self, approval: StandingApproval, request: StageRequest, covered: _Covered
    ) -> LoadedApproval:
        action, slot = covered.action, covered.slot
        construction = self._construction_reader()
        intent = construction.intent
        command = construction.command
        proposal_digest = request.proposal.canonical_digest
        decision = IndependentApprovalDecision.issue(
            scheme=_SCHEME,
            decision_id=f"{_SLOT_PREFIX}:{approval.digest}:{action.key}:{slot}",
            decision_generation=1,
            request_id=f"{_SLOT_PREFIX}:{approval.trading_date}:{action.key}:{slot}",
            request_digest=proposal_digest,
            trading_approval_policy_id=approval.trading_approval_policy_id,
            trading_approval_policy_generation=approval.trading_approval_policy_generation,
            trading_approval_policy_digest=approval.trading_approval_policy_digest,
            result=ApprovalResult.APPROVE,
            reason_codes=("STANDING_SESSION_APPROVAL",),
            approved_intent_envelope_id=intent.intent_id,
            approved_intent_envelope_digest=intent.canonical_digest,
            max_decision_age_ms=None,
            invalidation_generation=None,
            supersedes_decision_id=None,
        )
        assert isinstance(decision, IndependentApprovalDecision)
        self._pending = _PendingUse(
            decision_id=decision.decision_id or "",
            rcl_command_id=_consumption_command_id(decision),
            proposal_digest=proposal_digest or "",
            action_key=action.key,
            slot=slot,
            command_id=command.command_id or "",
            command_digest=covered.command_digest,
        )
        return LoadedApproval(
            decision=decision,
            issued_at_unix_ms=None,
            receipt_continuity=None,
            receipt_anchor=None,
            issuer_signed_age_ms=None,
            issuer_age_uncertainty_ms=None,
        )

    def record_verdict(self, verdict: StageVerdict) -> None:
        """Evidence one committed use (step 4 ADMIT on a standing decision)."""
        pending, self._pending = self._pending, None
        if pending is None or verdict.bound_identity != pending.decision_id:
            return
        if verdict.outcome is not StageOutcome.ADMIT:
            return
        self._evidence.append(
            {
                "artifact_digest": self._bound_digest,
                "proposal_digest": pending.proposal_digest,
                "rcl_command_id": pending.rcl_command_id,
                "action": pending.action_key,
                "slot": pending.slot,
                "command_id": pending.command_id,
                "command_digest": pending.command_digest,
                "consumption_outcome": verdict.native_verdict_value,
            },
            kind=_EVIDENCE_CONSUMED,
            record_class=_EVIDENCE_CONSUMED,
        )


def _axis(command: Any, axis: ConformanceAxis) -> str | None:
    value = command.axis_value(axis)
    return value if isinstance(value, str) else None


def _quantity_within(command: Any, max_quantity: int) -> bool:
    raw = _axis(command, ConformanceAxis.QUANTITY)
    if raw is None:
        return False
    try:
        quantity = Decimal(raw)
    except InvalidOperation:
        return False
    if (
        not quantity.is_finite()
        or quantity <= 0
        or quantity != quantity.to_integral_value()
    ):
        return False
    return quantity <= max_quantity


def _bounds_verdict(
    approval: StandingApproval,
    request: StageRequest,
    construction: Any,
    *,
    code_digest: str,
    trading_date: str | None,
) -> tuple[str | None, StandingAction | None, str | None]:
    """``(None, action, command_digest)`` when every bound holds, else ``(reason, None, None)``.

    Reads only the proposal the sequencer handed step 4 and step 2's command for THAT proposal.
    """
    proposal = request.proposal
    if approval.code_digest != code_digest:
        return "code_digest_mismatch", None, None
    if trading_date is None or trading_date != approval.trading_date:
        return "trading_date_mismatch_or_session_closed", None, None
    command = None if construction is None else construction.command
    if command is None or construction.intent is None:
        return "no_step2_command", None, None
    if (
        not proposal.canonical_digest
        or command.proposal_digest != proposal.canonical_digest
    ):
        return "step2_command_not_for_this_proposal", None, None
    if not command.canonical_digest:
        return "command_digest_missing", None, None
    strategy_id = None if proposal.proposer is None else proposal.proposer.strategy_id
    if strategy_id != approval.strategy_id:
        return "strategy_mismatch", None, None
    if (
        proposal.instrument != approval.instrument
        or _axis(command, ConformanceAxis.INSTRUMENT) != approval.instrument
    ):
        return "instrument_mismatch", None, None
    side = _axis(command, ConformanceAxis.SIDE)
    action = next(
        (
            a
            for a in approval.actions
            if a.position_effect == proposal.position_effect
            and a.direction == proposal.direction
            and a.side == side
        ),
        None,
    )
    if action is None:
        return "action_not_declared", None, None
    if not _quantity_within(command, approval.max_quantity):
        return "quantity_exceeds_max", None, None
    return None, action, command.canonical_digest


def chain_decision_providers(
    primary: Callable[[StageRequest], LoadedApproval | None],
    standing: StandingApprovalSource,
) -> Callable[[StageRequest], LoadedApproval | None]:
    """Per-proposal file first (unchanged path); the standing artifact only when no
    per-proposal file resolved a decision."""

    def _provider(request: StageRequest) -> LoadedApproval | None:
        loaded = primary(request)
        if loaded is not None:
            return loaded
        return standing.provide(request)

    return _provider


class StandingRecordingStage:
    """Step 4 wrapped so a committed standing use is evidenced after the stage judged it.
    Delegates unchanged; never alters the verdict."""

    def __init__(
        self,
        inner: Callable[[StageRequest], StageVerdict],
        standing: StandingApprovalSource,
    ) -> None:
        self._inner = inner
        self._standing = standing

    def __call__(self, request: StageRequest) -> StageVerdict:
        verdict = self._inner(request)
        self._standing.record_verdict(verdict)
        return verdict
