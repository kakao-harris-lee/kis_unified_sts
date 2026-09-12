"""``tos_runtime.compose.cli`` — argument parsing + operations-subcommand dispatch (slice plan §4
item 2; TOS Phase 5 W4 §2 decision 10).

**``run`` is still parsing only — no daemon loop lives here for it.** This subcommand composes
the runtime once, from CLI-sourced paths only (never ``os.environ``/``os.getenv`` — design #40
D1.1 "파일 경로는 CLI 인자로만 주입"), and a real invocation still needs a caller-supplied
:class:`~tos_runtime.compose.root.ConstructionConfig` and the two risk input providers
(:func:`~tos_runtime.compose.root.compose_paper_runtime`'s own required keyword arguments) —
none of which are expressible as bare CLI flags (this module's long-standing constraint, unchanged
by this wave). :func:`main` therefore does not itself compose or drive anything for ``run``; a
real launcher parses :class:`Args` here and supplies the rest itself.

**The five operations subcommands DO real work directly from bare flags** (plan §2 decision 10),
because none of them need a ``ConstructionConfig``/risk-input-provider: ``backup-set``,
``restore-drill``, ``migrate``, ``rotate-key``, ``print-digests`` each call straight into
:mod:`tos_runtime.operations.backup_set` / :mod:`tos_runtime.operations.schema_migrations` /
:mod:`tos_runtime.operations.key_rotation` / :mod:`tos_runtime.operations.dependency_admission`.

**Three MORE operations subcommands, added by the runtime operations wiring plan
(2026-09-13) §2 decisions 4/5/7: ``rearm``, ``ack-alert``, ``nontrade-eval``.** All three follow
the SAME idiom as ``rotate-key`` above — open the evidence store / inbox / time service directly
(the ``rotate-key`` "no driver, no engine" pattern), never a full
:func:`~tos_runtime.compose.root.compose_paper_runtime` call, because none of the three need a
``ConstructionConfig`` or the risk-input providers either:

* ``rearm --data-dir --custody-root --approvals-dir --config-dir --environment-label --seq``
  evaluates the HAG two-person re-arm quorum
  (:func:`~tos_runtime.safety.rearm.prepare_new_risk_halt_clear`) against an operator-authored
  ``approvals_dir/rearm/<seq>.yaml`` decision file + ``approvals_dir/rearm/roster.yaml`` and
  durably evidences the verdict (``REARM_APPROVED``/``REARM_REFUSED``). **Scope decision (mirrors
  ``restore-drill``'s own documented narrowing above):** this subcommand does NOT itself perform
  the storage-layer clear. :meth:`~tos_runtime.engine.inbox.SqliteEventInbox.clear_new_risk_halt`
  is machine-pinned (``tests/engine/test_no_direct_latch_clear.py``) to ONE caller,
  :meth:`~tos_runtime.compose._types.ComposedRuntime.clear_new_risk_halt` — reaching it needs a
  live, fully-composed ``ComposedRuntime`` (the same ``ConstructionConfig``/risk-input-provider
  gap ``run`` has, see the blocker list below). ``rearm`` exits ``0`` when the quorum is
  ``APPROVED`` (the durable evidence a live runtime's own ``clear_new_risk_halt`` call will read
  and re-derive — ``ReArmWorkflow`` re-checks single-use/quorum against the SAME durable history
  every time, never a cached decision) and non-zero on any refusal; it prints which of the two
  outcomes occurred, never silently claims the halt was cleared.
* ``ack-alert --data-dir --custody-root --approvals-dir --environment-label --seq`` calls
  :func:`~tos_runtime.safety.ack.acknowledge_alert` against an operator-authored
  ``approvals_dir/alerts/<seq>.yaml`` file. Needs only the evidence store (no inbox, no time
  service) — see that module's own docstring for why an acknowledgement is not a resolution,
  containment, or re-arm.
* ``nontrade-eval --observation <path>`` is a pure, stateless dry run: it loads a
  :class:`~tos_runtime.nontrade.observations.NonTradeObservation` from a YAML file (a small,
  scalar-fields-only loader local to this module — the nested kernel records
  ``transition_envelope``/``split_spec``/``correction``/``prior_correction`` are refused rather
  than silently dropped if present, a future wave's own loader) and folds it through
  :meth:`~tos_runtime.nontrade.processor.NonTradeEventProcessor.evaluate` (that method's own
  docstring: "a DRY RUN: records no evidence and touches no durable state"), printing the
  disposition + per-predicate result table. Opens no store, no custody, no inbox — genuinely
  zero evidence reaches any real durable store.

**Canonical blocker list for why ``run`` still refuses (plan §2 decision 7; §7 of the plan
document is the other copy of this same list — keep both in sync).** Three independent gaps,
each requiring its own follow-up wave, and each gates the NEXT column's own follow-up (dashboards,
``shutdown``, live projection export all need a live composed runtime too, so they wait on ALL
three, not just one):

(a) **``ConstructionConfig``'s three issued/generation-numbered kernel artifacts**
    (``VenueConstraintPolicy``/``VenueConstraintSnapshot``/``OrderAdmissibilityDecision``) have no
    YAML loader anywhere — every existing caller is a test fixture hand-issuing them
    (``tests/compose/_fixtures.py``). Building one would let CONFIGURATION author a decision only
    a real venue-constraint SERVICE is supposed to issue (a stand-in fixed into governance,
    exactly the "판정 저작" this plan explicitly rejects — see §3 rejected alternatives). Needs: a
    real venue-constraint service, plus Order Construction Policy ratification (currently
    unratified — ``root.py``'s own docstring).
(b) **The two risk-input providers** (``aggregate_risk_inputs_provider`` /
    ``action_flow_inputs_provider``) have no production source — every caller hand-builds a
    synthetic ``AggregateRiskDecisionInputs``/``ActionFlowDecisionInputs`` per test request. Needs
    a real position/risk-state service.
(c) **No tick source.** Nothing in ``tos_runtime`` produces a ``DECISION_TICK`` from a live market
    feed or a clock — :class:`~tos_runtime.engine.driver.EngineDriver`'s three public entry points
    are all pull-based; every real caller is a test fixture. Needs a ``tos.marketfeed`` runtime
    adapter and a scheduler/poll loop.

Resolving order (a)/(b)/(c) is an operator decision (plan §6 confirmation point 5), not this
module's to make.

**No subcommand token given ⇒ ``run`` (backward compatibility).** :func:`parse_args` prepends
``"run"`` to ``argv`` when the first token is not one of :data:`_SUBCOMMANDS` — the OLD bare
``--config-dir ... --data-dir ... --custody-root ... --environment-label ...`` invocation (no
subcommand keyword at all) continues to parse exactly as before, now via the ``run`` subparser
rather than the top-level parser directly (module docstring's own backward-compatibility
requirement).

**Reported scope decision — ``restore-drill`` performs ``restore_set``, not the full
``operations.backup_set.restore_drill``.** The full drill (recompose + replay + readiness
verification) needs a :class:`~tos_runtime.operations.backup_set.ComposeForDrill` callable, which
in turn needs the SAME ``ConstructionConfig``/risk-input-providers ``run`` cannot synthesize from
bare flags either — there is no more CLI-expressible a path to a real ``EngineCore`` here than
there is for ``run``. This CLI subcommand therefore performs the fully self-contained, digest-
verified restore step (:func:`~tos_runtime.operations.backup_set.restore_set`) and reports that a
genuine drill needs a strategy-specific Python caller. It ALSO adds a ``--custody-root`` flag
beyond the plan's literal ``--manifest --dest --environment-label`` list — ``restore_set`` requires
a ``key_provider`` for its post-restore evidence-chain re-verification, and there is no way to
build one without a custody directory. Both of these are reported to the team lead as an explicit
Phase B scope decision, not a silent narrowing.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``argparse``, ``decimal``,
``os``, ``secrets``, ``sys``) + ``pyyaml`` (``nontrade-eval``'s own small observation loader) +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.nontrade import NonTradeEventClass
from tos.workload import RuntimeIdentity

from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import KeyContinuityRefused, SqliteEvidenceStore
from tos_runtime.nontrade.observations import NonTradeObservation
from tos_runtime.nontrade.processor import NonTradeEventProcessor
from tos_runtime.operations.backup_set import DurableSetPaths, backup_set, restore_set
from tos_runtime.operations.dependency_admission import (
    observe_runtime_artifact,
    print_digests_text,
)
from tos_runtime.operations.key_rotation import (
    KeyRotationRefused,
    RotationOutcome,
    rotate_evidence_key,
)
from tos_runtime.operations.schema_migrations import STORE_MIGRATIONS, apply_migrations
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.safety.ack import acknowledge_alert
from tos_runtime.safety.rearm import prepare_new_risk_halt_clear
from tos_runtime.time.config import load_time_config
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import LocalSystemClockReader, ProcessMonotonicSource

__all__ = [
    "AckAlertArgs",
    "Args",
    "BackupSetArgs",
    "MigrateArgs",
    "NontradeEvalArgs",
    "PrintDigestsArgs",
    "RearmArgs",
    "RestoreDrillArgs",
    "RotateKeyArgs",
    "build_parser",
    "main",
    "parse_args",
]

#: The recognized subcommand tokens (module docstring's own "no token given ⇒ run" rule).
_SUBCOMMANDS = (
    "run",
    "backup-set",
    "restore-drill",
    "migrate",
    "rotate-key",
    "print-digests",
    "rearm",
    "ack-alert",
    "nontrade-eval",
)

#: Duplicated from :mod:`tos_runtime.operations.backup_set`'s own private
#: ``_LIVE_ENVIRONMENT_LABELS`` (not exported) — the SAME "duplicate the literal, do not reach
#: into another module's private surface" discipline :mod:`tos_runtime.compose._operations_wiring`
#: already documents for its own duplicated constants. Refused here, in the CLI, BEFORE anything
#: else runs (plan §2 decision 10's own "refuse ... before doing anything").
_LIVE_ENVIRONMENT_LABELS = frozenset({"paper", "restricted-live", "production"})


@dataclass(frozen=True)
class Args:
    """``run`` subcommand args — the original five fields, unchanged, plus two new optional TOS
    Phase 5 W4 fields (``projection_path``/``backup_root``, both defaulting to ``None`` so any
    existing construction call keeps working)."""

    config_dir: Path
    data_dir: Path
    custody_root: Path
    environment_label: str
    transport: TransportKind
    projection_path: Path | None = None
    backup_root: Path | None = None


@dataclass(frozen=True)
class BackupSetArgs:
    """``backup-set`` subcommand args."""

    data_dir: Path
    dest: Path
    generation: int
    readiness_verdict: str | None = None


@dataclass(frozen=True)
class RestoreDrillArgs:
    """``restore-drill`` subcommand args (module docstring — ``custody_root`` is an addition
    beyond the plan's literal flag list, reported there)."""

    manifest: Path
    dest: Path
    environment_label: str
    custody_root: Path


@dataclass(frozen=True)
class MigrateArgs:
    """``migrate`` subcommand args. ``store=None`` means every registered store
    (:data:`~tos_runtime.operations.schema_migrations.STORE_MIGRATIONS`)."""

    data_dir: Path
    store: str | None = None


@dataclass(frozen=True)
class RotateKeyArgs:
    """``rotate-key`` subcommand args — opens the evidence store + RCL log the same way
    ``run`` does (no driver, no engine), then calls
    :func:`~tos_runtime.operations.key_rotation.rotate_evidence_key`."""

    data_dir: Path
    custody_root: Path
    new_generation: int


@dataclass(frozen=True)
class PrintDigestsArgs:
    """``print-digests`` subcommand args — none; the observation reads the CURRENT process's own
    installed source tree/dependency set (:mod:`tos_runtime.operations.dependency_admission`).
    """


@dataclass(frozen=True)
class RearmArgs:
    """``rearm`` subcommand args (module docstring — opens the evidence store/inbox/time service
    directly, the SAME ``rotate-key`` idiom; never a full ``compose_paper_runtime``)."""

    data_dir: Path
    custody_root: Path
    approvals_dir: Path
    config_dir: Path
    environment_label: str
    seq: int


@dataclass(frozen=True)
class AckAlertArgs:
    """``ack-alert`` subcommand args — needs only the evidence store (module docstring)."""

    data_dir: Path
    custody_root: Path
    approvals_dir: Path
    environment_label: str
    seq: int


@dataclass(frozen=True)
class NontradeEvalArgs:
    """``nontrade-eval`` subcommand args — a pure dry run, no store/custody at all."""

    observation: Path


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    """The ``run`` subcommand's own flags — factored out so both :func:`build_parser`'s ``run``
    subparser (used when a subcommand token IS given) and the implicit "no token ⇒ run" path
    (module docstring) parse the identical flag set."""
    parser.add_argument(
        "--config-dir",
        required=True,
        type=Path,
        help=(
            "Directory holding time.yaml/authority.yaml/risk.yaml/"
            "currentness.yaml/release.yaml (each shaped like its "
            "tos/runtime/config/*.example.yaml counterpart, every "
            "named-TBD value filled)."
        ),
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        type=Path,
        help="Directory the RCL log / evidence store / emergency log files are created under.",
    )
    parser.add_argument(
        "--custody-root",
        required=True,
        type=Path,
        help=(
            "The D4 custody directory (custody.manifest.yaml + scope files + "
            "evidence.key.<generation> files + an optional approvals/ directory)."
        ),
    )
    parser.add_argument(
        "--environment-label",
        required=True,
        type=str,
        help="This process's boot-argument environment label (e.g. 'non-live-test'/'paper').",
    )
    parser.add_argument(
        "--transport",
        choices=[kind.value for kind in TransportKind],
        default=TransportKind.SYNTHETIC.value,
        help=(
            "The transport this composition wires (TOS KIS MOCK transport plan T2 lane C): "
            "'synthetic' (default, non-broker-reaching) or 'kis-mock' (KIS 모의투자 stock "
            "order-verification transport — requires a broker-reaching active scope and "
            "provisioned kis_mock.* custody, see tos_runtime.compose._transport_wiring)."
        ),
    )
    parser.add_argument(
        "--projection-path",
        type=Path,
        default=None,
        help=(
            "TOS Phase 5 W4 — where the operator projection JSON is exported. Omitted "
            "(default) disables export entirely; never a fabricated default path."
        ),
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        default=None,
        help=(
            "TOS Phase 5 W4 — where to look for the latest durable-set backup manifest for "
            "boot-time observation. Omitted (default) skips backup observation entirely."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser: ``run`` (default) plus the four operations subcommands
    (module docstring)."""
    parser = argparse.ArgumentParser(
        prog="tos-runtime-compose",
        description=(
            "Compose the Phase 2 paper runtime service chain "
            "(tos_runtime.compose.root.compose_paper_runtime) or run one of the TOS Phase 5 "
            "W4 operations subcommands. `run` does not itself drive a daemon loop — see this "
            "module's own docstring."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run", help="Compose the runtime (default when no subcommand is given)."
    )
    _add_run_arguments(run_parser)

    backup_parser = subparsers.add_parser(
        "backup-set",
        help="Snapshot the durable set into dest/gen{generation}/ + a manifest.",
    )
    backup_parser.add_argument("--data-dir", required=True, type=Path)
    backup_parser.add_argument("--dest", required=True, type=Path)
    backup_parser.add_argument("--generation", required=True, type=int)
    backup_parser.add_argument("--readiness-verdict", default=None, type=str)

    restore_parser = subparsers.add_parser(
        "restore-drill",
        help=(
            "Restore a durable-set backup into a fresh, non-live directory "
            "(module docstring — the full recompose+replay drill needs a Python caller)."
        ),
    )
    restore_parser.add_argument("--manifest", required=True, type=Path)
    restore_parser.add_argument("--dest", required=True, type=Path)
    restore_parser.add_argument("--environment-label", required=True, type=str)
    restore_parser.add_argument("--custody-root", required=True, type=Path)

    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Bring a closed store file up to its latest known baseline migration.",
    )
    migrate_parser.add_argument("--data-dir", required=True, type=Path)
    migrate_parser.add_argument(
        "--store", choices=sorted(STORE_MIGRATIONS), default=None
    )

    rotate_parser = subparsers.add_parser(
        "rotate-key",
        help=(
            "Rotate the evidence-signing key to --new-generation (design #40 D4.1; the new "
            "generation's key file must already be staged, file-first, under --custody-root)."
        ),
    )
    rotate_parser.add_argument("--data-dir", required=True, type=Path)
    rotate_parser.add_argument("--custody-root", required=True, type=Path)
    rotate_parser.add_argument("--new-generation", required=True, type=int)

    subparsers.add_parser(
        "print-digests",
        help="Print this process's own source-tree/dependency-set digests (stdout only).",
    )

    _add_rearm_ack_nontrade_subparsers(subparsers)

    return parser


def _add_rearm_ack_nontrade_subparsers(
    subparsers: argparse._SubParsersAction,
) -> None:
    """The three runtime operations wiring plan (2026-09-13) subcommands — split out of
    :func:`build_parser` purely for the 100-line function budget (no behaviour difference from
    inlining it there)."""
    rearm_parser = subparsers.add_parser(
        "rearm",
        help=(
            "Evaluate the HAG two-person re-arm quorum for a latched new-risk halt "
            "(module docstring — durably evidences APPROVED/REFUSED; does not itself "
            "clear the halt)."
        ),
    )
    rearm_parser.add_argument("--data-dir", required=True, type=Path)
    rearm_parser.add_argument("--custody-root", required=True, type=Path)
    rearm_parser.add_argument("--approvals-dir", required=True, type=Path)
    rearm_parser.add_argument(
        "--config-dir",
        required=True,
        type=Path,
        help="Directory holding time.yaml — needed to construct the TrustworthyTimeService.",
    )
    rearm_parser.add_argument("--environment-label", required=True, type=str)
    rearm_parser.add_argument("--seq", required=True, type=int)

    ack_parser = subparsers.add_parser(
        "ack-alert",
        help=(
            "Acknowledge one STM_ALERT evidence row (module docstring — never a "
            "resolution/containment/re-arm; tos_runtime.safety.ack)."
        ),
    )
    ack_parser.add_argument("--data-dir", required=True, type=Path)
    ack_parser.add_argument("--custody-root", required=True, type=Path)
    ack_parser.add_argument("--approvals-dir", required=True, type=Path)
    ack_parser.add_argument("--environment-label", required=True, type=str)
    ack_parser.add_argument("--seq", required=True, type=int)

    nontrade_parser = subparsers.add_parser(
        "nontrade-eval",
        help=(
            "Dry-run a NonTradeObservation YAML file through NonTradeEventProcessor and "
            "print its disposition (module docstring — zero evidence, no store opened)."
        ),
    )
    nontrade_parser.add_argument("--observation", required=True, type=Path)


def parse_args(
    argv: list[str] | None = None,
) -> (
    Args
    | BackupSetArgs
    | RestoreDrillArgs
    | MigrateArgs
    | RotateKeyArgs
    | PrintDigestsArgs
    | RearmArgs
    | AckAlertArgs
    | NontradeEvalArgs
):
    """Parse ``argv`` (defaults to ``sys.argv[1:]``) into the args object for whichever
    subcommand was named (or ``run``, implicitly — module docstring).

    Args:
        argv: The argument vector (excluding the program name), or ``None`` to read
            ``sys.argv`` itself.

    Returns:
        The parsed args object for the resolved subcommand.
    """
    if argv is None:
        argv = sys.argv[1:]
    effective = list(argv)
    if not effective or effective[0] not in _SUBCOMMANDS:
        effective = ["run", *effective]

    parser = build_parser()
    namespace = parser.parse_args(effective)
    command = namespace.command

    if command == "run":
        return Args(
            config_dir=namespace.config_dir,
            data_dir=namespace.data_dir,
            custody_root=namespace.custody_root,
            environment_label=namespace.environment_label,
            transport=TransportKind(namespace.transport),
            projection_path=namespace.projection_path,
            backup_root=namespace.backup_root,
        )
    if command == "backup-set":
        return BackupSetArgs(
            data_dir=namespace.data_dir,
            dest=namespace.dest,
            generation=namespace.generation,
            readiness_verdict=namespace.readiness_verdict,
        )
    if command == "restore-drill":
        return RestoreDrillArgs(
            manifest=namespace.manifest,
            dest=namespace.dest,
            environment_label=namespace.environment_label,
            custody_root=namespace.custody_root,
        )
    if command == "migrate":
        return MigrateArgs(data_dir=namespace.data_dir, store=namespace.store)
    if command == "rotate-key":
        return RotateKeyArgs(
            data_dir=namespace.data_dir,
            custody_root=namespace.custody_root,
            new_generation=namespace.new_generation,
        )
    if command == "rearm":
        return RearmArgs(
            data_dir=namespace.data_dir,
            custody_root=namespace.custody_root,
            approvals_dir=namespace.approvals_dir,
            config_dir=namespace.config_dir,
            environment_label=namespace.environment_label,
            seq=namespace.seq,
        )
    if command == "ack-alert":
        return AckAlertArgs(
            data_dir=namespace.data_dir,
            custody_root=namespace.custody_root,
            approvals_dir=namespace.approvals_dir,
            environment_label=namespace.environment_label,
            seq=namespace.seq,
        )
    if command == "nontrade-eval":
        return NontradeEvalArgs(observation=namespace.observation)
    # command == "print-digests" — argparse itself refuses any token outside _SUBCOMMANDS,
    # so every other branch is exhaustive; this is the only remaining reachable case.
    return PrintDigestsArgs()


def _dispatch_rotate_key(args: RotateKeyArgs) -> int:
    """The ``rotate-key`` subcommand's own dispatch — split out of :func:`main` purely for
    the 100-line function budget (no behaviour difference from inlining it there).

    Opens the evidence store + RCL log the SAME way ``run`` does (no driver, no engine) —
    :attr:`~tos_runtime.evidence.store.SqliteEvidenceStore.__init__`'s
    ``permit_rotation_pending_for_generation`` is what lets this open at all when the new
    generation's key file is already staged (that parameter's own docstring). Never re-raises
    a refusal — every refusal is printed and reported via a non-zero exit code instead.
    """
    paths = DurableSetPaths.from_data_dir(args.data_dir)
    key_provider = FileKeyProvider(args.custody_root, expected_owner_uid=os.getuid())
    try:
        evidence_store = SqliteEvidenceStore(
            paths.evidence,
            key_provider=key_provider,
            permit_rotation_pending_for_generation=args.new_generation,
        )
    except KeyContinuityRefused as exc:
        print(f"rotate-key: refused — {exc}", file=sys.stderr)
        return 1
    try:
        rcl_log = SqliteCommitLog(paths.rcl, evidence_port=evidence_store)
        try:
            outcome = rotate_evidence_key(
                evidence_store, key_provider, rcl_log, args.new_generation
            )
        except KeyRotationRefused as exc:
            print(f"rotate-key: refused — {exc}", file=sys.stderr)
            return 1
        finally:
            rcl_log.close()
    finally:
        evidence_store.close()

    print(f"rotate-key: {outcome}")
    # ROTATED_RCL_UNRECORDED is still a rotation that DID happen (module docstring of
    # tos_runtime.operations.key_rotation's own M8 note) — reported on stdout above, but a
    # non-zero exit still flags it for an operator/script to notice and reconcile the RCL side.
    return 0 if outcome == RotationOutcome.ROTATED else 1


#: Duplicated from ``tos_runtime.compose._wiring._TIME_CONFIG_NAME`` (a private module constant
#: there, not exported) — the SAME "duplicate the literal" discipline this module already applies
#: to ``_LIVE_ENVIRONMENT_LABELS`` above.
_TIME_CONFIG_NAME = "time.yaml"

#: Duplicated from ``tos_runtime.compose._types.ComposedRuntime``'s own private
#: ``_NEW_RISK_HALT_CLEAR_REFUSED_KIND`` (not exported) — the exact same runtime-level evidence
#: kind string a live ``ComposedRuntime.clear_new_risk_halt`` call would use for the SAME
#: seq/latch pre-check refusals this subcommand's own ``prepare_new_risk_halt_clear`` call can
#: reach (``NO_LATCH``/``SEQ_MISMATCH``/``QUORUM_REFUSED``).
_NEW_RISK_HALT_CLEAR_REFUSED_KIND = "NEW_RISK_HALT_CLEAR_REFUSED"


def _build_cli_identity(environment_label: str) -> RuntimeIdentity:
    """This process's own :class:`~tos.workload.RuntimeIdentity` for a directly-opened (not
    fully composed) CLI subcommand — the SAME real source-tree digest
    :func:`~tos_runtime.operations.dependency_admission.observe_runtime_artifact` measures for
    ``print-digests``/``compose_paper_runtime``'s own identity, never the retired constant digest
    (``tos_runtime.compose._wiring``'s own M6 lesson)."""
    return RuntimeIdentity(
        cell_id=environment_label,
        runtime_generation=0,
        process_nonce=secrets.token_hex(8),
        code_digest=observe_runtime_artifact().source_tree_digest,
    )


def _dispatch_rearm(args: RearmArgs) -> int:
    """The ``rearm`` subcommand's own dispatch (module docstring's own scope decision — this
    evaluates the HAG quorum and durably evidences the verdict; it does NOT itself perform the
    storage-layer clear, which is machine-pinned to ``compose/_types.py`` alone).

    Opens the evidence store + inbox + a started :class:`~tos_runtime.time.service
    .TrustworthyTimeService` directly (the ``rotate-key`` idiom — no driver, no engine, no full
    ``compose_paper_runtime``); :class:`~tos_runtime.safety.rearm.ReArmWorkflow` never actually
    consults the time service (its own docstring — hag reads no clock), so it is carried here only
    for interface symmetry with :func:`~tos_runtime.safety.rearm.prepare_new_risk_halt_clear`'s
    signature.
    """
    paths = DurableSetPaths.from_data_dir(args.data_dir)
    key_provider = FileKeyProvider(args.custody_root, expected_owner_uid=os.getuid())
    evidence_store = SqliteEvidenceStore(paths.evidence, key_provider=key_provider)
    try:
        inbox = SqliteEventInbox(
            paths.inbox, scheme=get_scheme(EV_L1_PROVISIONAL_VERSION)
        )
        try:
            time_config = load_time_config(args.config_dir / _TIME_CONFIG_NAME)
            identity = _build_cli_identity(args.environment_label)
            time_service = TrustworthyTimeService(
                monotonic=ProcessMonotonicSource(),
                references=(LocalSystemClockReader(),),
                config=time_config,
                identity=identity,
                evidence=evidence_store,
            )
            time_service.start()
            time_service.evaluate()
            time_service.evaluate()

            current = inbox.new_risk_halt()
            decision = prepare_new_risk_halt_clear(
                current=current,
                latched_evidence_seq=args.seq,
                approvals_dir=args.approvals_dir,
                evidence_store=evidence_store,
                inbox=inbox,
                time_service=time_service,
                environment_label=args.environment_label,
                expected_owner_uid=os.getuid(),
                refused_kind=_NEW_RISK_HALT_CLEAR_REFUSED_KIND,
            )
        finally:
            inbox.close()
    finally:
        evidence_store.close()

    if decision.refusal is not None:
        print(f"rearm: refused — {decision.refusal.value}", file=sys.stderr)
        return 1
    print(
        f"rearm: APPROVED for evidence_seq={args.seq} — HAG two-person quorum durably "
        "evidenced (REARM_APPROVED). This subcommand does not itself clear the latch "
        "(tests/engine/test_no_direct_latch_clear.py restricts "
        "SqliteEventInbox.clear_new_risk_halt to compose/_types.py) — a live "
        "ComposedRuntime.clear_new_risk_halt(latched_evidence_seq=..., "
        "approvals_dir=...) call against this SAME approval file completes the clear."
    )
    return 0


def _dispatch_ack_alert(args: AckAlertArgs) -> int:
    """The ``ack-alert`` subcommand's own dispatch — needs only the evidence store (module
    docstring; :func:`~tos_runtime.safety.ack.acknowledge_alert`)."""
    paths = DurableSetPaths.from_data_dir(args.data_dir)
    key_provider = FileKeyProvider(args.custody_root, expected_owner_uid=os.getuid())
    evidence_store = SqliteEvidenceStore(paths.evidence, key_provider=key_provider)
    try:
        outcome = acknowledge_alert(
            evidence_store=evidence_store,
            approvals_dir=args.approvals_dir,
            alert_seq=args.seq,
            environment_label=args.environment_label,
            expected_owner_uid=os.getuid(),
        )
    finally:
        evidence_store.close()

    print(f"ack-alert: {outcome.reason}")
    return 0 if outcome.acknowledged else 1


#: ``NonTradeObservation`` fields this CLI's YAML loader accepts directly (scalar/simple types
#: only — module docstring). ``event_class`` is handled separately (enum conversion);
#: ``change_triggers``/``field_confidences`` are handled separately (frozenset conversion);
#: ``injected_worst_intermediate_risk`` is handled separately (Decimal conversion).
_NONTRADE_SCALAR_FIELDS = (
    "observation_id",
    "source_label",
    "event_subtype",
    "workflow_generation",
    "idempotency_key",
    "supersedes_ref",
    "announcement_time",
    "observation_time",
    "record_time",
    "ex_time",
    "effective_time",
    "payable_time",
    "settlement_time",
    "old_instrument_identity",
    "new_instrument_identity",
    "identity_transition_final",
    "original_retained",
    "event_is_material",
    "earliest_credible_boundary",
    "latest_completion_boundary",
    "source_disagreement_bounded",
    "protective_action_may_proceed",
    "injected_credible_space_bounded",
    "injected_union_capacity_known",
)

#: The three nested kernel records :class:`~tos_runtime.nontrade.observations.NonTradeObservation`
#: can carry (``transition_envelope``/``split_spec``/``correction``/``prior_correction``) have no
#: loader here yet — refused rather than silently dropped (module docstring's own "a future wave's
#: own loader" note).
_NONTRADE_UNSUPPORTED_NESTED_FIELDS = (
    "transition_envelope",
    "split_spec",
    "correction",
    "prior_correction",
)


class NontradeObservationLoadError(Exception):
    """Raised by :func:`_load_nontrade_observation` on any refusal."""


def _load_nontrade_observation(path: Path) -> NonTradeObservation:
    """Load a :class:`~tos_runtime.nontrade.observations.NonTradeObservation` from a YAML file
    (module docstring — scalar fields only)."""
    try:
        raw_text = path.read_text()
    except OSError as exc:
        raise NontradeObservationLoadError(f"cannot read {path}: {exc}") from exc
    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise NontradeObservationLoadError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise NontradeObservationLoadError(
            f"{path} must parse to a mapping (got {type(raw).__name__})"
        )
    unsupported = [
        name
        for name in _NONTRADE_UNSUPPORTED_NESTED_FIELDS
        if raw.get(name) is not None
    ]
    if unsupported:
        raise NontradeObservationLoadError(
            f"{path}: field(s) {unsupported} are not supported by this CLI's YAML loader "
            "yet (nested kernel records need a dedicated loader a future wave adds) — "
            "omit them or leave them null"
        )
    kwargs: dict[str, Any] = {
        name: raw[name] for name in _NONTRADE_SCALAR_FIELDS if name in raw
    }
    if raw.get("event_class") is not None:
        try:
            kwargs["event_class"] = NonTradeEventClass(raw["event_class"])
        except ValueError as exc:
            raise NontradeObservationLoadError(
                f"{path}: 'event_class'={raw['event_class']!r} is not a valid "
                f"NonTradeEventClass: {exc}"
            ) from exc
    for name in ("change_triggers", "field_confidences"):
        if raw.get(name) is not None:
            kwargs[name] = frozenset(raw[name])
    if raw.get("injected_worst_intermediate_risk") is not None:
        try:
            kwargs["injected_worst_intermediate_risk"] = Decimal(
                str(raw["injected_worst_intermediate_risk"])
            )
        except InvalidOperation as exc:
            raise NontradeObservationLoadError(
                f"{path}: 'injected_worst_intermediate_risk'="
                f"{raw['injected_worst_intermediate_risk']!r} is not a valid decimal: {exc}"
            ) from exc
    try:
        return NonTradeObservation(**kwargs)
    except TypeError as exc:
        raise NontradeObservationLoadError(
            f"{path}: missing or unexpected field(s): {exc}"
        ) from exc


def _dispatch_nontrade_eval(args: NontradeEvalArgs) -> int:
    """The ``nontrade-eval`` subcommand's own dispatch — a pure dry run (module docstring):
    opens no store, no custody, appends zero evidence anywhere real."""
    try:
        observation = _load_nontrade_observation(args.observation)
    except NontradeObservationLoadError as exc:
        print(f"nontrade-eval: refused — {exc}", file=sys.stderr)
        return 1

    processor = NonTradeEventProcessor(required_legs_by_class={})
    outcome = processor.evaluate(observation)

    disposition_str = (
        outcome.disposition.value if outcome.disposition is not None else None
    )
    print(
        f"nontrade-eval: disposition={disposition_str} "
        f"restrictive={outcome.restrictive} latch_reason={outcome.latch_reason}"
    )
    print("nontrade-eval: predicates:")
    for name, value in outcome.predicate_results.items():
        print(f"  {name}: {value}")
    if outcome.unevaluated:
        print(f"nontrade-eval: unevaluated: {list(outcome.unevaluated)}")
    print(
        "nontrade-eval: dry run only — no --data-dir/--custody-root was opened, so zero "
        "evidence was appended to any real store."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse ``argv`` and dispatch to the right subcommand (module docstring).

    ``run`` returns ``0`` without composing or driving anything itself (this module has never
    done that — see the module docstring's own long-standing constraint); every other
    subcommand performs its real action directly and prints a short human-readable report.

    Returns:
        ``0`` on success; ``1`` on a refusal this function itself decided (e.g.
        ``restore-drill`` against a live ``environment_label``) — an underlying operations
        function's own exception is NOT caught here and propagates to the caller.
    """
    args = parse_args(argv)

    if isinstance(args, Args):
        return 0

    if isinstance(args, BackupSetArgs):
        paths = DurableSetPaths.from_data_dir(args.data_dir)
        manifest = backup_set(
            paths,
            args.dest,
            args.generation,
            readiness_verdict_at_backup=args.readiness_verdict,
        )
        print(f"backup-set: wrote gen{manifest.generation} manifest under {args.dest}")
        return 0

    if isinstance(args, RestoreDrillArgs):
        if args.environment_label in _LIVE_ENVIRONMENT_LABELS:
            print(
                f"restore-drill: refused — environment_label={args.environment_label!r} is a "
                "live label; drills only ever run under a non-live label",
                file=sys.stderr,
            )
            return 1
        key_provider = FileKeyProvider(
            args.custody_root, expected_owner_uid=os.getuid()
        )
        restored = restore_set(args.manifest, args.dest, key_provider=key_provider)
        print(
            f"restore-drill: restored gen{restored.manifest.generation} into {args.dest} "
            "(digest-verified, non_live=True). A full replay+readiness drill needs a "
            "strategy-specific Python caller — see "
            "tos_runtime.operations.backup_set.restore_drill (module docstring)."
        )
        return 0

    if isinstance(args, MigrateArgs):
        store_names = (
            (args.store,) if args.store is not None else tuple(STORE_MIGRATIONS)
        )
        paths = DurableSetPaths.from_data_dir(args.data_dir)
        path_by_store = {
            "evidence": paths.evidence,
            "rcl": paths.rcl,
            "inbox": paths.inbox,
        }
        for store_name in store_names:
            apply_migrations(path_by_store[store_name], store_name)
            print(f"migrate: {store_name} at {path_by_store[store_name]} is current")
        return 0

    if isinstance(args, RotateKeyArgs):
        return _dispatch_rotate_key(args)

    if isinstance(args, RearmArgs):
        return _dispatch_rearm(args)

    if isinstance(args, AckAlertArgs):
        return _dispatch_ack_alert(args)

    if isinstance(args, NontradeEvalArgs):
        return _dispatch_nontrade_eval(args)

    # isinstance(args, PrintDigestsArgs) — the only remaining case.
    observation = observe_runtime_artifact()
    sys.stdout.write(print_digests_text(observation))
    return 0
