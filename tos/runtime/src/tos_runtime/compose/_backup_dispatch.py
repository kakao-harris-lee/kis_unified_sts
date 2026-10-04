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


def _schema_version_prefix(exc: SchemaVersionRefused) -> str:
    """``migrate refused`` for BEHIND, ``schema refused`` for AHEAD.

    One exception type, two operator actions, so one prefix would have to lie about one of
    them. BEHIND is fixed by the ``migrate`` CLI on that ``--data-dir``
    (``docs/runbooks/tos-paper-boot.md`` §4-A). AHEAD is not: the store was written by NEWER
    code, ``apply_migrations`` refuses it as well
    (:func:`~tos_runtime.operations.schema_migrations.apply_migrations`'s AHEAD guard, which
    fires before it writes anything), and the resolution is to run the code version that
    wrote the file or to stop this lane until someone does.

    So ``schema refused`` names the SUBJECT where ``migrate refused`` names the action —
    because AHEAD has two admissible actions and this command cannot choose between them.
    The runbook's §5 table carries both; what the prefix must guarantee is that the operator
    does not land on the BEHIND row.

    Reads :attr:`~tos_runtime.operations.schema_ledger.SchemaVersionRefused.direction`, never
    the message: that wording is quoted verbatim in two runbooks and must stay free to change
    without silently re-routing a verdict.

    EXHAUSTIVE, not an ``if/else`` on one value. The earlier form returned ``schema refused``
    for everything that was not ``BEHIND``, so a third direction added to
    :data:`~tos_runtime.operations.schema_ledger.SchemaVersionDirection` would have been
    routed to the AHEAD row in silence — prescribing "run the newer code" for a case nobody
    had classified. Here mypy refuses the ``assert_never`` unless both members are handled, so
    that third member is a type error at the gate rather than a wrong runbook row at 18:00
    (review round 2 note i).
    """
    match exc.direction:
        case "BEHIND":
            return "migrate refused"
        case "AHEAD":
            return "schema refused"
        case _:
            assert_never(exc.direction)


#: ``(exception type, prefix)``, most specific first — where ``prefix`` is either the literal
#: or, for a type whose action depends on HOW it refused, a function of the exception. A
#: VERDICT gets a prefix of the form ``[<layer>|<action>|<subject> ]refused`` — naming the
#: LAYER that reached the verdict, or the ACTION the target needs (``migrate``), or the
#: SUBJECT that is wrong when no single action can be named (``schema``) — so the runbook's
#: §5 table can route the operator by that one word and the host wrapper's ``classify()``
#: legend can enumerate the same three forms. Counting the rows below: five literal prefixes
#: over six rows (``custody refused`` is shared by two types), of which FOUR name a layer —
#: ``snapshot`` / ``archive`` / ``integrity`` / ``custody``. The first row is the bare
#: ``refused``, which names NO layer on purpose: :class:`ColdBackupRefused` is this command's
#: own door saying no before any layer was entered, and there is no inner layer to name
#: (review round 2 note j — this comment said "the five literals" and called all of them
#: layers). The seventh row is the direction-dependent one and contributes no literal here.
#: Anything not listed is an
#: environment fault and falls through to ``failed``. ``integrity refused`` is the one that
#: matters most: a chain that does not re-verify means "do not trust this copy", and filing
#: it under "the host broke, re-run" was the wrong instruction in the single case where
#: re-running is not the answer (review round 2, F1).
#:
#: :class:`SchemaVersionRefused` is the one direction-dependent row — see
#: :func:`_schema_version_prefix`. It reached the host as ``archive failed`` (plan §7.1.27
#: A3-F1, runbook ``tos-evidence-cold-backup.md`` §4-5-2), which routed to "fix the host and
#: re-run"; a re-run cannot change an on-disk ``PRAGMA user_version`` in either direction.
#:
#: **Every type in** :data:`~tos_runtime.operations.cold_backup._PASSTHROUGH_REFUSALS` **must
#: appear here**, or that verdict ships as the generic ``failed —`` line. That is not a
#: convention to remember: ``tests/compose/test_cold_backup_cli.py`` asserts the two sets
#: agree, and derives its per-prefix cases from this table.
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


#: The table's types as a plain tuple, for ``except``. Derived, never re-listed, so a new
#: row is catchable by both doors the moment it is added.
_REFUSAL_TYPES: tuple[type[BaseException], ...] = tuple(
    exc_type for exc_type, _ in _REFUSAL_PREFIXES
)


def _refusal_line(exc: BaseException) -> str:
    """The stderr line body for ``exc`` — a named refusal, or the generic failure form.

    Data-driven rather than a stack of ``except`` branches so that "which prefix for which
    exception" is one table a test can read, and so this stays inside the 100-line budget as
    the list grows.
    """
    for exc_type, rule in _REFUSAL_PREFIXES:
        if isinstance(exc, exc_type):
            prefix = rule(exc) if callable(rule) else rule
            return f"{prefix} — {exc}"
    return f"failed — {type(exc).__name__}: {exc}"


def dispatch_cold_backup(args: ColdBackupArgs) -> int:
    """Run one cold backup and report it; **nothing reaches the caller as a traceback.**

    Two kinds of bad outcome, kept apart because the operator's next action differs:

    * **Refused** — a verdict. :data:`_REFUSAL_PREFIXES` gives each type its own prefix
      (``refused`` / ``snapshot refused`` / ``archive refused`` / ``integrity refused`` /
      ``custody refused`` / ``migrate refused`` / ``schema refused``) so the one line says
      which layer decided — or, for the last two, the ACTION the target needs (``migrate``)
      and the SUBJECT that is wrong where two actions are admissible and this command cannot
      choose (``schema``), the ``[<layer>|<action>|<subject> ]refused`` shape the runbook's
      §4-5-4 cell and the host wrapper's legend both spell out — and the runbook's
      §5 table routes by that word. **Three of them are NOT a re-run**:
      ``integrity refused`` (the archived evidence chain did not verify), ``migrate refused``
      (the target is BEHIND this code's schema: the operator runs the ``migrate`` CLI on that
      ``--data-dir``) and ``schema refused`` (the target is AHEAD: ``migrate`` refuses it too,
      so the fix is to run the code that wrote it, or to stop this lane).
      In the last two the snapshot stage already finished, so the uncompressed generation and
      its manifest stand complete and the per-generation verify directory is kept as the
      evidence of the refusal; what is missing is the compressed archive **and its report**.
      Each further night takes the NEXT generation, so an unattended lane left on a refusing
      target accumulates one full uncompressed copy per run until someone acts.
    * **Failed** — the run was admissible and the environment broke underneath it: the
      runtime still holding a sqlite handle (the precondition no code can check), a disk
      filling mid-copy, an unparseable manifest. Those arrive as
      :class:`~tos_runtime.operations.cold_backup.ColdBackupFailed` carrying the stage, and
      print as ``cold-backup: <stage> failed — <ExcType>: <message>``.

    Both exit ``1``. The catch-all at the end exists because ``cron`` is the primary caller
    and a Python traceback in a mail body is a worse report than one line — the same
    deliberate broad catch :func:`~tos_runtime.compose._run_dispatch.dispatch_run` documents
    for ``compose_paper_runtime``, and for the same stated reason: no common base class
    narrower than ``Exception`` exists across the loaders and adapters underneath.

    Exit ``0`` means the archive exists, was read back, every member digest matched the
    manifest and the evidence chain re-verified. A run that completes but leaves a filesystem
    below its configured floor still exits ``0`` — that backup IS verified — and prints the
    capacity alarm to stderr, which is what the NEXT run will refuse on.
    """
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

    # No try/except around the constructor: `FileKeyProvider.__init__` only stores fields, so
    # a branch here would name a case it cannot catch. Custody is actually exercised by
    # `cold_backup`'s preflight (`key_provider.current()`), before anything is copied.
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
    """Take the durable-set snapshot, then — only when ``--archive-dir`` was given — compress
    and verify it (evidence growth plan §2 A3).

    The snapshot itself is never conditional on the archive step: a failed or refused archive
    leaves the uncompressed generation exactly as ``backup_set`` wrote it, and is reported as a
    non-zero exit with the refusal on stderr rather than as a silent partial success.

    Scope note: the ``backup_set`` call below is deliberately NOT wrapped. This is the
    interactive door — an operator typed the generation — and a refusal there is about the
    arguments just typed. The archive step is the one an unattended caller reaches through
    :func:`dispatch_cold_backup` as well, which is why the two share
    :func:`_refusal_line` rather than spelling the prefixes twice.
    """
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
        # The SAME prefix table `cold-backup` routes by (review note). Before this, only
        # `BackupArchiveRefused` was caught here, so the other verdicts the archive step can
        # reach — a chain that does not re-verify, unreadable custody, a store at another
        # schema — came out of this door as tracebacks while the identical refusal came out
        # of `cold-backup` as one routed line. Same text, same §5 row, either door.
        print(f"backup-set: {_refusal_line(refusal)}", file=sys.stderr)
        return 1
    print(
        f"backup-set: archived gen{verification.generation} to "
        f"{verification.archive_path} ({verification.source_bytes} -> "
        f"{verification.archive_bytes} bytes), read back and verified: "
        f"{len(verification.files_verified)} file digest(s) + evidence chain"
    )
    return 0
