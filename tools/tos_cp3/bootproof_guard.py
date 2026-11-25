#!/usr/bin/env python3
"""The refusals shared by the CP-3 tenant boot-proof entry points."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path
from typing import Any

POLICY_VERSION = "cp3-tenant-bootproof/2"

APPROVED_REAL_PRODUCER_PREFIXES: tuple[str, ...] = ("tos-cp3-live",)

DEFAULT_SCRATCH_ROOT = Path("~/.local/state/tos/scratch")

RESIDENT_DATA_ROOT = Path("~/.local/state/tos/paper-data")

DESIGNATED_PARENT_GLOBS: tuple[str, ...] = ("cp3-setup-d-*-data", "paper-data")

SYNTHETIC_SOURCE_PREFIX = "cp3-bootproof-synthetic"


class BootProofGuardRefused(Exception):
    """One refusal class, many messages — the message names the concrete fact."""


def _rows(journal_path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Every non-blank line of the journal, as ``(1-indexed line number, object)``."""
    if not journal_path.is_file():
        raise BootProofGuardRefused(
            f"observation journal does not exist: {journal_path}"
        )
    try:
        text = journal_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BootProofGuardRefused(
            f"observation journal could not be read: {journal_path} ({exc})"
        ) from exc

    rows: list[tuple[int, dict[str, Any]]] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise BootProofGuardRefused(
                f"{journal_path}:{line_no}: not valid JSON ({exc}) — a line this guard "
                "cannot read is a line whose source_id it cannot clear"
            ) from exc
        if not isinstance(payload, dict):
            raise BootProofGuardRefused(
                f"{journal_path}:{line_no}: not a JSON object "
                f"(got {type(payload).__name__})"
            )
        rows.append((line_no, payload))
    if not rows:
        raise BootProofGuardRefused(
            f"observation journal {journal_path} holds no rows — a boot driven by an "
            "empty journal proves nothing and its emptiness is not evidence of real data"
        )
    return rows


def _validated_prefixes(prefixes: tuple[str, ...]) -> tuple[str, ...]:
    """Refuse an allowlist entry that cannot mean what it looks like."""
    for prefix in prefixes:
        if not prefix:
            raise BootProofGuardRefused(
                "APPROVED_REAL_PRODUCER_PREFIXES contains an EMPTY entry. An empty "
                "prefix reads as 'approve everything'; it is never a producer name"
            )
        if prefix.endswith("/"):
            raise BootProofGuardRefused(
                f"APPROVED_REAL_PRODUCER_PREFIXES entry {prefix!r} ends with '/'. The "
                "delimiter is appended by the matcher, so this entry would match "
                "nothing — write it without the trailing slash"
            )
    return tuple(prefixes)


_validated_prefixes(APPROVED_REAL_PRODUCER_PREFIXES)


def _matches_prefix(source_id: str, prefix: str) -> bool:
    """``source_id`` is ``prefix`` exactly, or ``prefix`` followed by ``/``."""
    return source_id == prefix or source_id.startswith(prefix + "/")


def unapproved_rows(journal_path: Path) -> tuple[int, ...]:
    """1-indexed line numbers whose ``source_id`` is **not** on the allowlist."""
    approved = _validated_prefixes(tuple(APPROVED_REAL_PRODUCER_PREFIXES))
    return tuple(
        line_no
        for line_no, payload in _rows(journal_path)
        if not isinstance(payload.get("source_id"), str)
        or not any(_matches_prefix(payload["source_id"], prefix) for prefix in approved)
    )


def synthetic_rows(journal_path: Path) -> tuple[int, ...]:
    """1-indexed line numbers carrying :data:`SYNTHETIC_SOURCE_PREFIX`."""
    return tuple(
        line_no
        for line_no, payload in _rows(journal_path)
        if isinstance(payload.get("source_id"), str)
        and payload["source_id"].startswith(SYNTHETIC_SOURCE_PREFIX)
    )


def _scratch_root() -> Path:
    """The resolved scratch root, refusing a symlinked one."""
    raw = DEFAULT_SCRATCH_ROOT.expanduser()
    absolute = raw.absolute()
    resolved = raw.resolve()
    if absolute != resolved:
        raise BootProofGuardRefused(
            f"the scratch root {raw} is not a real directory path: it resolves to "
            f"{resolved}. A symlinked scratch root (or a symlinked component of it) "
            "makes containment meaningless — a root pointing at an ancestor of the "
            "designated durable sets would make every one of them 'under scratch'"
        )
    return resolved


def _designated_component(resolved: Path) -> str | None:
    """The first path component named like a durable-set parent, if any."""
    for part in resolved.parts:
        for pattern in DESIGNATED_PARENT_GLOBS:
            if fnmatch.fnmatch(part, pattern):
                return part
    return None


def require_not_resident_store(data_dir: Path) -> None:
    """Refuse a data dir inside the resident paper durable set. **Unconditional.**"""
    root = RESIDENT_DATA_ROOT.expanduser().resolve()
    resolved = Path(data_dir).expanduser().resolve()
    if resolved == root or root in resolved.parents:
        raise BootProofGuardRefused(
            f"{data_dir} resolves to {resolved}, inside the RESIDENT paper durable set "
            f"{root}. A tenant session never writes there, with any journal: the store "
            "is append-only and activation records bind neither direction nor tree, so "
            "tenant rows mixed into the resident corpus could not be separated again"
        )


def require_scratch_data_dir(data_dir: Path, *, why: str) -> None:
    """Refuse unless ``data_dir`` is a scratch directory this boot may genesis."""
    root = _scratch_root()
    resolved = Path(data_dir).expanduser().resolve()

    if root not in resolved.parents:
        raise BootProofGuardRefused(
            f"{why}, so the data dir must be a fresh directory under the scratch root "
            f"{root}. {data_dir} resolves to {resolved}, which is not. The designated "
            "tenant durable sets (runbook tos-paper-boot.md §7.2-b) take their FIRST "
            "genesis from an APPROVED producer; an evidence store is append-only, so a "
            "genesis there cannot be undone"
        )

    designated = _designated_component(resolved)
    if designated is not None:
        raise BootProofGuardRefused(
            f"{why}, and {resolved} carries the durable-set parent name {designated!r}. "
            "Those names are how an operator tells corpora apart by path (runbook "
            "§7.2-b), so a scratch directory wearing one is a trap for whoever reads "
            "the evidence later — and it is what a symlinked scratch root would make "
            "look legitimate"
        )

    if resolved.exists():
        if not resolved.is_dir():
            raise BootProofGuardRefused(
                f"{why}, and {resolved} exists but is not a directory"
            )
        existing = sorted(entry.name for entry in resolved.iterdir())
        if existing:
            raise BootProofGuardRefused(
                f"{why}, so the data dir must be newly created and empty. {resolved} "
                f"already holds {len(existing)} "
                f"entr{'y' if len(existing) == 1 else 'ies'} "
                f"({', '.join(existing[:5])}) — booting into it would append synthetic "
                "evidence to whatever is already there"
            )


def require_scratch_output_path(out_path: Path) -> None:
    """Refuse a boot-proof journal written outside the scratch root."""
    root = _scratch_root()
    resolved = Path(out_path).expanduser().resolve()
    if root not in resolved.parents:
        raise BootProofGuardRefused(
            f"the boot-proof journal must be written under the scratch root {root}; "
            f"{out_path} resolves to {resolved}, which is not. This tool writes "
            "SYNTHETIC rows and replaces its output whole, so an unconstrained path "
            "can overwrite a live journal"
        )


def require_scratch_rule(journal_path: Path, data_dir: Path) -> None:
    """The rule (module docstring): resident never; allowlisted may; else scratch."""
    require_not_resident_store(data_dir)

    unapproved = unapproved_rows(journal_path)
    if not unapproved:
        return

    approved = ", ".join(repr(p) for p in APPROVED_REAL_PRODUCER_PREFIXES) or (
        "<empty — no real producer is approved>"
    )
    shown = ", ".join(str(n) for n in unapproved[:5])
    more = f" (+{len(unapproved) - 5} more)" if len(unapproved) > 5 else ""
    require_scratch_data_dir(
        data_dir,
        why=(
            f"journal {journal_path} has row(s) {shown}{more} whose source_id is not "
            f"from an approved real producer [allowlist: {approved}]"
        ),
    )


def require_journal_instrument(journal_path: Path, instrument: str) -> None:
    """Refuse unless every journal row names ``instrument``."""
    seen = sorted(
        {str(payload.get("instrument")) for _line_no, payload in _rows(journal_path)}
    )
    if seen != [instrument]:
        raise BootProofGuardRefused(
            f"journal {journal_path} names instrument(s) {seen} but this session boots "
            f"{instrument!r}. The runtime journal reader FILTERS by instrument, so a "
            "mismatch is not an error downstream — it is zero observations and a session "
            "that proves nothing"
        )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point used by ``tools/tos_cp3/runners/run_tenant_session.sh``."""
    parser = argparse.ArgumentParser(
        prog="bootproof_guard.py",
        description=(
            "Refuse a CP-3 tenant boot unless every journal row comes from an approved "
            "real producer, or the data dir is a fresh scratch directory (plan "
            "2026-10-09 §2.5, as corrected by the review of PR #892)."
        ),
    )
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="the durable-set LEAF this boot would genesis (<parent>/<종목>)",
    )
    parser.add_argument("--instrument", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        require_scratch_rule(args.journal, args.data_dir)
        require_journal_instrument(args.journal, args.instrument)
        unapproved = unapproved_rows(args.journal)
        synthetic = synthetic_rows(args.journal)
    except BootProofGuardRefused as exc:
        print(f"bootproof_guard: REFUSED — {exc}", file=sys.stderr)
        return 1

    branch = (
        f"SCRATCH ({len(unapproved)} row(s) not from an approved producer)"
        if unapproved
        else "APPROVED REAL PRODUCER (every row's source_id is allowlisted)"
    )
    marker = (
        f"; {len(synthetic)} row(s) carry the {SYNTHETIC_SOURCE_PREFIX!r} provenance "
        "marker"
        if synthetic
        else ""
    )
    print(
        f"bootproof_guard: ok — journal {args.journal} took the {branch} branch{marker}; "
        f"data dir {args.data_dir} accepted for instrument {args.instrument}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI tests
    raise SystemExit(main())
