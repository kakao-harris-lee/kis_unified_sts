"""``tos_runtime.compose._backup_dispatch`` — the two backup subcommands' parsers, args and"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, assert_never

from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.custody.ports import CustodyError
from tos_runtime.evidence.store import EvidenceCorruption
from tos_runtime.operations.backup_archive import (
    BackupArchiveRefused,
    archive_backup_set,
)
from tos_runtime.operations.backup_set import (
    BackupSetRefused,
    DurableSetPaths,
    backup_set,
    manifest_path_for,
)
from tos_runtime.operations.cold_backup import (
    COLD_BACKUP_CONFIG_NAME,
    ColdBackupFailed,
    ColdBackupRefused,
    cold_backup,
    load_cold_backup_config,
)
from tos_runtime.operations.key_rotation import KeyContinuityRefused
from tos_runtime.operations.schema_ledger import SchemaVersionRefused

if TYPE_CHECKING:
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
    """``cold-backup`` subcommand args — the live set to copy, the directory holding"""

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


def _schema_version_prefix(exc: SchemaVersionRefused) -> str:
    """``migrate refused`` for BEHIND, ``schema refused`` for AHEAD."""
    match exc.direction:
        case "BEHIND":
            return "migrate refused"
        case "AHEAD":
            return "schema refused"
        case _:
            assert_never(exc.direction)


#: re-run"; a re-run cannot change an on-disk ``PRAGMA user_version`` in either direction.
_PrefixRule = str | Callable[..., str]
_REFUSAL_PREFIXES: tuple[tuple[type[BaseException], _PrefixRule], ...] = (
    (ColdBackupRefused, "refused"),
    (BackupSetRefused, "snapshot refused"),
    (BackupArchiveRefused, "archive refused"),
    (EvidenceCorruption, "integrity refused"),
    (KeyContinuityRefused, "custody refused"),
    (CustodyError, "custody refused"),
    (SchemaVersionRefused, _schema_version_prefix),
)


_REFUSAL_TYPES: tuple[type[BaseException], ...] = tuple(
    exc_type for exc_type, _ in _REFUSAL_PREFIXES
)


def _refusal_line(exc: BaseException) -> str:
    """The stderr line body for ``exc`` — a named refusal, or the generic failure form."""
    for exc_type, rule in _REFUSAL_PREFIXES:
        if isinstance(exc, exc_type):
            prefix = rule(exc) if callable(rule) else rule
            return f"{prefix} — {exc}"
    return f"failed — {type(exc).__name__}: {exc}"


def dispatch_cold_backup(args: ColdBackupArgs) -> int:
    """Run one cold backup and report it; **nothing reaches the caller as a traceback.**"""
    config_path = args.config_dir / COLD_BACKUP_CONFIG_NAME
    try:
        config = load_cold_backup_config(config_path)
    except ColdBackupRefused as refusal:
        print(f"cold-backup: refused — {refusal}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - see docstring: no common base exists
        print(
            f"cold-backup: config failed — {type(exc).__name__}: {exc}", file=sys.stderr
        )
        return 1

    key_provider = FileKeyProvider(args.custody_root, expected_owner_uid=os.getuid())

    try:
        report = cold_backup(args.data_dir, config, key_provider=key_provider)
    except ColdBackupFailed as failure:
        print(f"cold-backup: {failure}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - see docstring: no common base exists
        print(f"cold-backup: {_refusal_line(exc)}", file=sys.stderr)
        return 1

    print(
        f"cold-backup: archived gen{report.generation} to {report.archive_path} "
        f"({report.source_bytes} -> {report.archive_bytes} bytes), read back and verified: "
        f"{len(report.files_verified)} file digest(s) + evidence chain; report at "
        f"{report.report_path}"
    )
    if report.free_bytes_below_minimum_after:
        low = "; ".join(
            f"{'+'.join(entry.roots)} at {entry.measured_path}: {entry.free_bytes} bytes free"
            for entry in report.free_space_after
            if entry.free_bytes < report.minimum_free_bytes
        )
        print(
            f"cold-backup: WARNING — {low} (configured floor {report.minimum_free_bytes}). "
            "This backup is verified; the NEXT run will refuse. Nothing here deletes a cold "
            "copy (that is Track B, ADR-002-016 §17) — add storage or move archives to "
            "another medium",
            file=sys.stderr,
        )
    return 0


def dispatch_backup_set(args: BackupSetArgs) -> int:
    """Take the durable-set snapshot, then — only when ``--archive-dir`` was given — compress"""
    paths = DurableSetPaths.from_data_dir(args.data_dir)
    manifest = backup_set(
        paths,
        args.dest,
        args.generation,
        readiness_verdict_at_backup=args.readiness_verdict,
    )
    manifest_path = manifest_path_for(args.dest, manifest.generation)
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
    except _REFUSAL_TYPES as refusal:
        print(f"backup-set: {_refusal_line(refusal)}", file=sys.stderr)
        return 1
    print(
        f"backup-set: archived gen{verification.generation} to "
        f"{verification.archive_path} ({verification.source_bytes} -> "
        f"{verification.archive_bytes} bytes), read back and verified: "
        f"{len(verification.files_verified)} file digest(s) + evidence chain"
    )
    return 0
