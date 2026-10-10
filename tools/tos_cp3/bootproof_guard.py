#!/usr/bin/env python3
"""The refusals shared by the CP-3 tenant boot-proof entry points.

Plan ``docs/plans/2026-10-09-tos-cp3-tenant-render-and-boot-path-plan.md`` §2.5
(H2 disposition, v3) puts ONE rule in front of a tenant boot that is driven by a
*synthetic* observation journal:

    if ANY journal row's ``source_id`` carries the ``cp3-bootproof-synthetic``
    prefix, proceed only if the data dir's ``Path.resolve()`` lies strictly
    under the scratch root ``~/.local/state/tos/scratch/`` (also resolved), and
    that directory is newly created / still empty.

**Why it lives here and not in prose.** The renderer never reads the journal and
does not know the data dir; the run template takes the data parent from the
environment. The concrete failing input the plan names is
``run_tenant_session.sh`` pointed at the data parent ``~/.local/state/tos`` with
a boot-proof journal: that genesises the *designated* tenant durable set
(``~/.local/state/tos/cp3-setup-d-*-data``, runbook §7.2-b) with synthetic data,
and an append-only evidence corpus cannot be un-genesised. The first real
genesis must be ③'s real data.

**Why ONE module.** Both entry points — :mod:`tools.tos_cp3.bootproof_journal`
(which knows it is about to write a synthetic row) and the shell template
(which inspects a journal somebody else wrote) — call the functions below, so
the two cannot drift. The shell template reaches them through :func:`main`.

**Scope note (firewall).** ``tools/`` is in the reverse scan of
``tools/tos_firewall_check.py``: this module imports neither ``tos`` nor
``tos_runtime``. It is stdlib-only on purpose — the shell template runs it as a
guard, before anything heavier is imported.

Exit codes of :func:`main`: ``0`` ok, ``1`` refused, ``2`` bad arguments.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

#: Handshake string the shell template pins (``guard_checkout``'s sibling
#: ``guard_python_module`` in ``tools/broker_probes/runners/_common.sh``). A
#: template copied out of a different tree reports a different value and aborts,
#: which is the 2026-09-30 mistake #825 exists to prevent. Bump it whenever a
#: refusal below changes shape, so a stale template cannot drive a new guard.
POLICY_VERSION = "cp3-tenant-bootproof/1"

#: The scratch root, as the plan spells it. ``expanduser()`` is applied at use
#: time, so a test can move ``HOME`` and get a throwaway root — which is also
#: how the shell template is exercised without ever touching the real one.
DEFAULT_SCRATCH_ROOT = Path("~/.local/state/tos/scratch")

#: The marker :mod:`tools.tos_cp3.bootproof_journal` stamps on ``source_id``.
#: Plan §2.5 / L1: the full→mini relabel is explicit, so the whole stamp reads
#: ``cp3-bootproof-synthetic:<original contract>:<original raw_event_id>``.
SYNTHETIC_SOURCE_PREFIX = "cp3-bootproof-synthetic"


class BootProofGuardRefused(Exception):
    """One refusal class, many messages — the message names the concrete fact.

    Mirrors ``tos_runtime.marketfeed.journal.JournalError``'s own
    single-class-many-messages convention (that module's docstring).
    """


def _rows(journal_path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Every non-blank line of the journal, as ``(1-indexed line number, object)``.

    Fail-closed on anything it cannot read, exactly like the runtime reader this
    journal is written for: a line this cannot parse is a line whose
    ``source_id`` it cannot clear, and "unreadable" must never collapse into
    "no synthetic rows found".
    """
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
                f"{journal_path}:{line_no}: not a JSON object (got {type(payload).__name__})"
            )
        rows.append((line_no, payload))
    if not rows:
        raise BootProofGuardRefused(
            f"observation journal {journal_path} holds no rows — a boot driven by an "
            "empty journal proves nothing and its emptiness is not evidence of real data"
        )
    return rows


def synthetic_rows(journal_path: Path) -> tuple[int, ...]:
    """The 1-indexed line numbers whose ``source_id`` carries the synthetic marker.

    **Every** row is examined, not the first one (plan §2.5 v3, re-review). The
    concrete failing input the plan names: row 1 carries a real producer's
    ``source_id`` and row 3 carries the marker — a first-row-only check clears
    that journal and the synthetic data reaches the designated durable set.
    """
    hits: list[int] = []
    for line_no, payload in _rows(journal_path):
        source_id = payload.get("source_id")
        if isinstance(source_id, str) and source_id.startswith(SYNTHETIC_SOURCE_PREFIX):
            hits.append(line_no)
    return tuple(hits)


def require_scratch_data_dir(
    data_dir: Path, *, scratch_root: Path | None = None, why: str
) -> None:
    """Refuse unless ``data_dir`` is a scratch directory this boot may genesis.

    Two clauses, each with its own concrete failing input:

    * **containment** — ``~/.local/state/tos/cp3-setup-d-long-data`` (or a leaf
      under it) is not under the scratch root, so it is refused. The comparison
      is between ``Path.resolve()`` values on BOTH sides, which is what also
      refuses a symlink sitting inside the scratch root and pointing at the
      designated directory (plan §2.5: that case is the second red proof).
      Equality with the root is refused by the same clause and deliberately not
      spelled a second time — a path is never its own parent, so a separate
      ``==`` test would be a clause that can never fire on its own (#838).
    * **emptiness** — a directory that already holds something is somebody's
      durable set (or somebody's run), and genesis into it is not reversible.
      Absent is fine: the caller creates it immediately after this returns.

    Args:
        data_dir: The directory genesis will create its four stores in — the
            LEAF (``<parent>/<종목>``), not the parent, because that is where the
            append-only corpus actually lands.
        scratch_root: Override for tests; ``None`` means
            :data:`DEFAULT_SCRATCH_ROOT` with ``~`` expanded.
        why: What made this check apply, quoted in the refusal message.

    Raises:
        BootProofGuardRefused: Either clause.
    """
    raw_root = DEFAULT_SCRATCH_ROOT if scratch_root is None else Path(scratch_root)
    root = raw_root.expanduser().resolve()
    resolved = Path(data_dir).expanduser().resolve()

    if root not in resolved.parents:
        raise BootProofGuardRefused(
            f"{why}, so the data dir must be a fresh directory under the scratch root "
            f"{root}. {data_dir} resolves to {resolved}, which is not. The designated "
            "tenant durable sets (runbook tos-paper-boot.md §7.2-b) take their FIRST "
            "genesis from ③'s real data; an evidence store is append-only, so synthetic "
            "genesis there cannot be undone"
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
                f"already holds {len(existing)} entr{'y' if len(existing) == 1 else 'ies'} "
                f"({', '.join(existing[:5])}) — booting into it would append synthetic "
                "evidence to whatever is already there"
            )


def require_scratch_rule(
    journal_path: Path, data_dir: Path, *, scratch_root: Path | None = None
) -> None:
    """Apply :func:`require_scratch_data_dir` when the journal carries a synthetic row.

    A journal with no synthetic marker anywhere is a real-producer journal and is
    NOT subject to the scratch rule — ③'s first real genesis is the whole point
    of the designated durable sets.
    """
    hits = synthetic_rows(journal_path)
    if not hits:
        return
    require_scratch_data_dir(
        data_dir,
        scratch_root=scratch_root,
        why=(
            f"journal {journal_path} carries the {SYNTHETIC_SOURCE_PREFIX!r} marker on "
            f"line(s) {', '.join(str(n) for n in hits)}"
        ),
    )


def require_journal_instrument(journal_path: Path, instrument: str) -> None:
    """Refuse unless every journal row names ``instrument``.

    ``JsonLinesObservationJournal.poll`` filters by instrument, so a journal
    written for a different contract month is not an error anywhere downstream —
    it is **silence**: zero observations, zero snapshots, a session that boots
    cleanly and proves nothing. The contract month rolls on its own
    (``shared.instruments.futures.get_front_month_code``), so the journal written
    yesterday and the code derived today really can disagree.
    """
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
    """CLI entry point used by ``tools/tos_cp3/runners/run_tenant_session.sh``.

    Deliberately offers no ``--scratch-root`` flag: a run template that could be
    told where "scratch" is would be a guard the caller can switch off. The
    override exists only as a keyword argument, for tests (which move ``HOME``
    when they exercise this through the shell).
    """
    parser = argparse.ArgumentParser(
        prog="bootproof_guard.py",
        description=(
            "Refuse a CP-3 tenant boot whose observation journal is synthetic unless the "
            "data dir is a fresh scratch directory (plan 2026-10-09 §2.5)."
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
    except BootProofGuardRefused as exc:
        print(f"bootproof_guard: REFUSED — {exc}", file=sys.stderr)
        return 1

    hits = synthetic_rows(args.journal)
    kind = (
        f"SYNTHETIC (marker on line(s) {', '.join(str(n) for n in hits)})"
        if hits
        else "no synthetic marker — treated as a real-producer journal"
    )
    print(
        f"bootproof_guard: ok — journal {args.journal} is {kind}; "
        f"data dir {args.data_dir} accepted for instrument {args.instrument}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI tests
    raise SystemExit(main())
