"""``tos_runtime.compose.cli`` — argument parsing + operations-subcommand dispatch (slice plan §4"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.workload import RuntimeIdentity

from tos_runtime.authority.standing_cli import (
    COMMAND as _STANDING_COMMAND,
)
from tos_runtime.authority.standing_cli import (
    StandingApprovalArgs,
    add_standing_approval_subparser,
    dispatch_write_standing_approval,
    standing_approval_args,
)
from tos_runtime.compose._backup_dispatch import (
    ColdBackupArgs,
    add_cold_backup_subparser,
    cold_backup_args,
    dispatch_backup_set,
    dispatch_cold_backup,
)
from tos_runtime.compose._cli_ops import (
    marketfeed_policy_digest_lines,
    rearm_and_clear,
    risk_state_policy_digest_lines,
)
from tos_runtime.compose._migrate_paths import migrate_path_for
from tos_runtime.compose._run_dispatch import dispatch_run as _dispatch_run
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import KeyContinuityRefused, SqliteEvidenceStore
from tos_runtime.marketfeed.policy import CriticalInputPolicyConfigError
from tos_runtime.operations.backup_archive import DEFAULT_XZ_PRESET
from tos_runtime.operations.backup_set import DurableSetPaths, restore_set
from tos_runtime.operations.dependency_admission import (
    observe_runtime_artifact,
    print_digests_text,
)
from tos_runtime.operations.key_rotation import (
    KeyRotationRefused,
    RotationOutcome,
    rotate_evidence_key,
)
from tos_runtime.operations.schema_migrations import (
    STORE_MIGRATIONS,
    MigrationOutcome,
    apply_migrations,
)
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.safety.ack import acknowledge_alert
from tos_runtime.venue import (
    ORDER_CONSTRUCTION_POLICY_CONFIG_NAME,
    VENUE_POLICY_CONFIG_NAME,
    VenuePolicyConfigError,
    load_order_construction_policy,
    load_venue_constraint_policy,
)

__all__ = [
    "AckAlertArgs",
    "Args",
    "BackupSetArgs",
    "ColdBackupArgs",
    "MigrateArgs",
    "PrintDigestsArgs",
    "PrintPolicyDigestsArgs",
    "RearmArgs",
    "RestoreDrillArgs",
    "RotateKeyArgs",
    "build_parser",
    "main",
    "parse_args",
]

_SUBCOMMANDS = (
    "run",
    "backup-set",
    "cold-backup",
    "restore-drill",
    "migrate",
    "rotate-key",
    "print-digests",
    "print-policy-digests",
    "rearm",
    "ack-alert",
    _STANDING_COMMAND,
)

_LIVE_ENVIRONMENT_LABELS = frozenset({"paper", "restricted-live", "production"})


@dataclass(frozen=True)
class Args:
    """``run`` subcommand args — the original five fields, unchanged, plus two new optional TOS"""

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
    archive_dir: Path | None = None
    verify_dir: Path | None = None
    custody_root: Path | None = None
    xz_preset: int = DEFAULT_XZ_PRESET


@dataclass(frozen=True)
class RestoreDrillArgs:
    """``restore-drill`` subcommand args (module docstring — ``custody_root`` is an addition"""

    manifest: Path
    dest: Path
    environment_label: str
    custody_root: Path


@dataclass(frozen=True)
class MigrateArgs:
    """``migrate`` subcommand args. ``store=None`` means every registered store"""

    data_dir: Path
    store: str | None = None


@dataclass(frozen=True)
class RotateKeyArgs:
    """``rotate-key`` subcommand args — opens the evidence store + RCL log the same way"""

    data_dir: Path
    custody_root: Path
    new_generation: int


@dataclass(frozen=True)
class PrintDigestsArgs:
    """``print-digests`` subcommand args — none; the observation reads the CURRENT process's own"""


@dataclass(frozen=True)
class PrintPolicyDigestsArgs:
    """``print-policy-digests`` subcommand args (module docstring) — loads the two governed"""

    config_dir: Path


@dataclass(frozen=True)
class RearmArgs:
    """``rearm`` subcommand args (module docstring — opens the evidence store/inbox/time service"""

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


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    """The ``run`` subcommand's own flags — factored out so both :func:`build_parser`'s ``run``"""
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
    """Build the argument parser: ``run`` (default) plus the four operations subcommands"""
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
    backup_parser.add_argument(
        "--archive-dir",
        default=None,
        type=Path,
        help=(
            "Opt-in (evidence growth plan §2 A3): also write gen{N}.set.tar.xz here and "
            "verify it by reading it back. Requires --verify-dir and --custody-root."
        ),
    )
    backup_parser.add_argument("--verify-dir", default=None, type=Path)
    backup_parser.add_argument("--custody-root", default=None, type=Path)
    backup_parser.add_argument("--xz-preset", default=DEFAULT_XZ_PRESET, type=int)

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

    policy_digests_parser = subparsers.add_parser(
        "print-policy-digests",
        help=(
            "Print the governed Venue Constraint Policy / Order Construction Policy "
            "YAMLs' own id/generation/digest under --config-dir (stdout only; opens no "
            "store, reads no activation file)."
        ),
    )
    policy_digests_parser.add_argument("--config-dir", required=True, type=Path)

    add_cold_backup_subparser(subparsers)
    add_standing_approval_subparser(subparsers)
    _add_rearm_ack_subparsers(subparsers)

    return parser


def _add_rearm_ack_subparsers(
    subparsers: argparse._SubParsersAction,
) -> None:
    """The two runtime operations wiring plan (2026-09-13) subcommands — split out of"""
    rearm_parser = subparsers.add_parser(
        "rearm",
        help=(
            "Evaluate the operator re-arm approval for a latched new-risk halt "
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


def parse_args(
    argv: list[str] | None = None,
) -> (
    Args
    | BackupSetArgs
    | ColdBackupArgs
    | RestoreDrillArgs
    | MigrateArgs
    | RotateKeyArgs
    | PrintDigestsArgs
    | PrintPolicyDigestsArgs
    | RearmArgs
    | AckAlertArgs
    | StandingApprovalArgs
):
    """Parse ``argv`` (defaults to ``sys.argv[1:]``) into the args object for whichever"""
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
            archive_dir=namespace.archive_dir,
            verify_dir=namespace.verify_dir,
            custody_root=namespace.custody_root,
            xz_preset=namespace.xz_preset,
        )
    if command == "cold-backup":
        return cold_backup_args(namespace)
    if command == _STANDING_COMMAND:
        return standing_approval_args(namespace)
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
    if command == "print-policy-digests":
        return PrintPolicyDigestsArgs(config_dir=namespace.config_dir)
    return PrintDigestsArgs()


def _dispatch_rotate_key(args: RotateKeyArgs) -> int:
    """The ``rotate-key`` subcommand's own dispatch — split out of :func:`main` purely for"""
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
    return 0 if outcome == RotationOutcome.ROTATED else 1


_TIME_CONFIG_NAME = "time.yaml"


def _build_cli_identity(environment_label: str) -> RuntimeIdentity:
    """This process's own :class:`~tos.workload.RuntimeIdentity` for a directly-opened (not"""
    return RuntimeIdentity(
        cell_id=environment_label,
        runtime_generation=0,
        process_nonce=secrets.token_hex(8),
        code_digest=observe_runtime_artifact().source_tree_digest,
    )


def _dispatch_print_policy_digests(args: PrintPolicyDigestsArgs) -> int:
    """The ``print-policy-digests`` subcommand's own dispatch — loads the Venue/OCP policies"""
    scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)
    try:
        loaded_venue = load_venue_constraint_policy(
            args.config_dir / VENUE_POLICY_CONFIG_NAME, scheme=scheme
        )
        loaded_ocp = load_order_construction_policy(
            args.config_dir / ORDER_CONSTRUCTION_POLICY_CONFIG_NAME, scheme=scheme
        )
        risk_state_lines = risk_state_policy_digest_lines(
            args.config_dir, scheme=scheme
        ) + marketfeed_policy_digest_lines(args.config_dir, scheme=scheme)
    except (VenuePolicyConfigError, CriticalInputPolicyConfigError) as exc:
        print(f"print-policy-digests: refused — {exc}", file=sys.stderr)
        return 1
    print(
        "VENUE_CONSTRAINT_POLICY "
        f"{loaded_venue.policy.policy_id} {loaded_venue.policy.policy_generation} "
        f"{loaded_venue.policy.canonical_digest}"
    )
    print(
        "ORDER_CONSTRUCTION_POLICY "
        f"{loaded_ocp.policy.policy_id} {loaded_ocp.policy.policy_generation} "
        f"{loaded_ocp.policy.canonical_digest}"
    )
    for line in risk_state_lines:
        print(line)
    return 0


def _dispatch_rearm(args: RearmArgs) -> int:
    """The ``rearm`` subcommand's own dispatch — evaluates the operator approval and, only"""
    paths = DurableSetPaths.from_data_dir(args.data_dir)
    key_provider = FileKeyProvider(args.custody_root, expected_owner_uid=os.getuid())
    evidence_store = SqliteEvidenceStore(paths.evidence, key_provider=key_provider)
    try:
        inbox = SqliteEventInbox(
            paths.inbox, scheme=get_scheme(EV_L1_PROVISIONAL_VERSION)
        )
        try:
            result = rearm_and_clear(
                inbox=inbox,
                evidence_store=evidence_store,
                approvals_dir=args.approvals_dir,
                environment_label=args.environment_label,
                expected_owner_uid=os.getuid(),
                latched_evidence_seq=args.seq,
            )
        finally:
            inbox.close()
    finally:
        evidence_store.close()

    if not result.cleared:
        print(f"rearm: {result.reason}", file=sys.stderr)
        return 1
    print(f"rearm: cleared evidence_seq={args.seq} (operator approval APPROVED).")
    return 0


def _dispatch_ack_alert(args: AckAlertArgs) -> int:
    """The ``ack-alert`` subcommand's own dispatch — needs only the evidence store (module"""
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


def _migrate_report(outcome: MigrationOutcome) -> str:
    """One operator-facing line naming what ``migrate`` actually did."""
    if outcome.applied:
        parts = [
            f"applied v{outcome.from_version} -> v{outcome.to_version} "
            f"({', '.join(f'v{v}' for v in outcome.applied)})"
        ]
        unrecorded = tuple(v for v in outcome.applied if v not in outcome.ledgered)
        if unrecorded:
            parts.append(
                "ledger row(s) already present for "
                f"{', '.join(f'v{v}' for v in unrecorded)}, not re-recorded (append-only)"
            )
        if outcome.repaired:
            parts.append(f"rebuilt {', '.join(outcome.repaired)}")
        return "; ".join(parts)
    if outcome.repaired:
        return (
            f"already at v{outcome.to_version}, but REBUILT missing "
            f"{', '.join(outcome.repaired)} — the file was running without it"
        )
    return f"already at v{outcome.to_version}, nothing to do"


def main(argv: list[str] | None = None) -> int:
    """Parse ``argv`` and dispatch to the right subcommand (module docstring)."""
    args = parse_args(argv)

    if isinstance(args, Args):
        return _dispatch_run(args)

    if isinstance(args, BackupSetArgs):
        return dispatch_backup_set(args)

    if isinstance(args, ColdBackupArgs):
        return dispatch_cold_backup(args)

    if isinstance(args, StandingApprovalArgs):
        return dispatch_write_standing_approval(args)

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
        for store_name in store_names:
            store_path = migrate_path_for(
                store_name, paths=paths, data_dir=args.data_dir
            )
            outcome = apply_migrations(store_path, store_name)
            print(f"migrate: {store_name} at {store_path} — {_migrate_report(outcome)}")
        return 0

    if isinstance(args, RotateKeyArgs):
        return _dispatch_rotate_key(args)

    if isinstance(args, PrintPolicyDigestsArgs):
        return _dispatch_print_policy_digests(args)

    if isinstance(args, RearmArgs):
        return _dispatch_rearm(args)

    if isinstance(args, AckAlertArgs):
        return _dispatch_ack_alert(args)

    observation = observe_runtime_artifact()
    sys.stdout.write(print_digests_text(observation))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
