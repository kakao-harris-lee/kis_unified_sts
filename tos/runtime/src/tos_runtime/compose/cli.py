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

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``argparse``, ``os``,
``sys``) + ``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.evidence.store import KeyContinuityRefused, SqliteEvidenceStore
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

__all__ = [
    "Args",
    "BackupSetArgs",
    "MigrateArgs",
    "PrintDigestsArgs",
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

    return parser


def parse_args(
    argv: list[str] | None = None,
) -> (
    Args
    | BackupSetArgs
    | RestoreDrillArgs
    | MigrateArgs
    | RotateKeyArgs
    | PrintDigestsArgs
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

    # isinstance(args, PrintDigestsArgs) — the only remaining case.
    observation = observe_runtime_artifact()
    sys.stdout.write(print_digests_text(observation))
    return 0
