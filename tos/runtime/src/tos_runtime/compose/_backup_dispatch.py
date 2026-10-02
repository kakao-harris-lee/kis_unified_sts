"""``tos_runtime.compose._backup_dispatch`` — the two backup subcommands' parsers, args and
dispatch (``backup-set``, ``cold-backup``), split out of ``cli.py`` purely for that module's own
size budget
(``tools/tos_size_budget.py`` — module ceiling 1000 lines; ``cli.py`` stood at 972/1000 before
this wave, and ``cold-backup``'s own wiring alone took it to 995 — one ordinary edit from a red
gate, the exact condition the evidence growth plan's §7.1.7 deviation 1 already named for
``backup_set.py``). ``backup-set``'s dispatch moved here UNCHANGED, with it, because the two
belong together and the move is what buys the headroom. No behavioural difference from having
them inline there — the SAME "split purely for size budget" discipline :mod:`~tos_runtime.compose._nontrade_eval_dispatch` and
:mod:`~tos_runtime.compose._run_dispatch` already document for themselves.

``cold-backup --data-dir --config-dir --custody-root`` is the unattended operator entry point
for the evidence growth plan's §2 A3 (``docs/plans/2026-09-29-tos-evidence-growth-and-purge-
plan.md``): snapshot the next generation, compress it, verify it by reading it back, record the
result. It is the same two halves ``backup-set --archive-dir`` already performs, with the
destinations read from ``evidence_cold_backup.yaml`` instead of typed on the command line and
the generation counted from the backup root instead of by hand — which is what makes it
callable from a cron line (no state in the invocation, so the Nth run is spelled exactly like
the first). ``backup-set`` is unchanged and remains the interactive, one-off door.

**Scheduling is a cron line, not a daemon** (``docs/runbooks/tos-evidence-cold-backup.md``).
This subcommand opens no store in the live data directory, holds nothing, and exits.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.*`` only.
No ``shared.*``.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.operations.backup_archive import (
    BackupArchiveRefused,
    archive_backup_set,
)
from tos_runtime.operations.backup_set import (
    BackupSetRefused,
    DurableSetPaths,
    backup_set,
)
from tos_runtime.operations.cold_backup import (
    COLD_BACKUP_CONFIG_NAME,
    ColdBackupRefused,
    cold_backup,
    load_cold_backup_config,
)

if TYPE_CHECKING:
    # TYPE_CHECKING-only: `cli.py` imports THIS module, so a top-level import of its
    # `BackupSetArgs` would be circular — the SAME pattern `_nontrade_eval_dispatch.py`
    # already uses for `NontradeEvalArgs`.
    from tos_runtime.compose.cli import BackupSetArgs

__all__ = [
    "ColdBackupArgs",
    "add_cold_backup_subparser",
    "cold_backup_args",
    "dispatch_backup_set",
    "dispatch_cold_backup",
]


@dataclass(frozen=True)
class ColdBackupArgs:
    """``cold-backup`` subcommand args — the live set to copy, the directory holding
    ``evidence_cold_backup.yaml``, and the custody root the archive's chain re-verification
    reads its keys from. Every destination is in the config file (module docstring)."""

    data_dir: Path
    config_dir: Path
    custody_root: Path


def add_cold_backup_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``cold-backup`` subparser on ``subparsers``."""
    parser = subparsers.add_parser(
        "cold-backup",
        help=(
            "Snapshot the next generation, compress it to xz, verify it by reading it back, "
            "and write a JSON report (evidence growth plan §2 A3; destinations come from "
            f"{COLD_BACKUP_CONFIG_NAME} under --config-dir). Deletes nothing."
        ),
    )
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument(
        "--config-dir",
        required=True,
        type=Path,
        help=(
            f"Directory holding {COLD_BACKUP_CONFIG_NAME} (shaped like "
            "tos/runtime/config/evidence_cold_backup.example.yaml, every value filled)."
        ),
    )
    parser.add_argument("--custody-root", required=True, type=Path)


def cold_backup_args(namespace: argparse.Namespace) -> ColdBackupArgs:
    """The parsed namespace as a :class:`ColdBackupArgs`."""
    return ColdBackupArgs(
        data_dir=namespace.data_dir,
        config_dir=namespace.config_dir,
        custody_root=namespace.custody_root,
    )


def dispatch_cold_backup(args: ColdBackupArgs) -> int:
    """Run one cold backup and report it; never raises a refusal at an operator.

    Every refusal — config, destination, free space, snapshot, archive — is printed to stderr
    and reported as exit 1, because the caller is usually ``cron`` and a traceback in a mail
    body is a worse report than one line naming what was refused. The three refusal types stay
    distinct in the message prefix rather than being flattened into one.

    Exit ``0`` means the archive exists, was read back, every member digest matched the
    manifest and the evidence chain re-verified. A run that completes but leaves cold storage
    below its configured floor still exits ``0`` — that backup IS verified — and prints the
    capacity alarm to stderr, which is what the NEXT run will refuse on.
    """
    config_path = args.config_dir / COLD_BACKUP_CONFIG_NAME
    try:
        config = load_cold_backup_config(config_path)
        report = cold_backup(
            args.data_dir,
            config,
            key_provider=FileKeyProvider(
                args.custody_root, expected_owner_uid=os.getuid()
            ),
        )
    except ColdBackupRefused as refusal:
        print(f"cold-backup: refused — {refusal}", file=sys.stderr)
        return 1
    except BackupSetRefused as refusal:
        print(f"cold-backup: snapshot refused — {refusal}", file=sys.stderr)
        return 1
    except BackupArchiveRefused as refusal:
        print(f"cold-backup: archive refused — {refusal}", file=sys.stderr)
        return 1

    print(
        f"cold-backup: archived gen{report.generation} to {report.archive_path} "
        f"({report.source_bytes} -> {report.archive_bytes} bytes), read back and verified: "
        f"{len(report.files_verified)} file digest(s) + evidence chain; report at "
        f"{report.report_path}"
    )
    if report.free_bytes_below_minimum_after:
        print(
            f"cold-backup: WARNING — cold storage now has {report.free_bytes_after} bytes "
            f"free, below the configured floor of {report.minimum_free_bytes}. This backup is "
            "verified; the NEXT run will refuse. Nothing here deletes a cold copy (that is "
            "Track B, ADR-002-016 §17) — add storage or move archives to another medium",
            file=sys.stderr,
        )
    return 0


def dispatch_backup_set(args: BackupSetArgs) -> int:
    """Take the durable-set snapshot, then — only when ``--archive-dir`` was given — compress
    and verify it (evidence growth plan §2 A3).

    The snapshot itself is never conditional on the archive step: a failed or refused archive
    leaves the uncompressed generation exactly as ``backup_set`` wrote it, and is reported as a
    non-zero exit with the refusal on stderr rather than as a silent partial success.
    """
    paths = DurableSetPaths.from_data_dir(args.data_dir)
    manifest = backup_set(
        paths,
        args.dest,
        args.generation,
        readiness_verdict_at_backup=args.readiness_verdict,
    )
    manifest_path = args.dest / f"gen{manifest.generation}.set.manifest.json"
    print(f"backup-set: wrote gen{manifest.generation} manifest under {args.dest}")
    if args.archive_dir is None:
        return 0
    if args.verify_dir is None or args.custody_root is None:
        print(
            "backup-set: --archive-dir requires --verify-dir and --custody-root (the archive "
            "is verified by reading it back, which needs a scratch directory and the evidence "
            "chain keys) — the uncompressed snapshot above is complete and untouched",
            file=sys.stderr,
        )
        return 1
    try:
        verification = archive_backup_set(
            manifest_path,
            args.archive_dir,
            args.verify_dir,
            key_provider=FileKeyProvider(
                args.custody_root, expected_owner_uid=os.getuid()
            ),
            preset=args.xz_preset,
        )
    except BackupArchiveRefused as refusal:
        print(f"backup-set: archive refused — {refusal}", file=sys.stderr)
        return 1
    print(
        f"backup-set: archived gen{verification.generation} to "
        f"{verification.archive_path} ({verification.source_bytes} -> "
        f"{verification.archive_bytes} bytes), read back and verified: "
        f"{len(verification.files_verified)} file digest(s) + evidence chain"
    )
    return 0
