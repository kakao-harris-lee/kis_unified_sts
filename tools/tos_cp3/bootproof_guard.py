#!/usr/bin/env python3
"""The refusals shared by the CP-3 tenant boot-proof entry points.

Plan ``docs/plans/2026-10-09-tos-cp3-tenant-render-and-boot-path-plan.md`` §2.5
(H2 disposition) puts one rule in front of a tenant boot driven by a journal no
real producer wrote. **That rule is an allowlist, and this module's first cut got
it backwards** — see "The inversion" below; the plan's own wording was the hole,
and §2.5 now records the correction.

**The question the rule answers.** A tenant boot genesises a durable set, and an
evidence store is append-only: synthetic rows written into the designated tenant
sets (``~/.local/state/tos/cp3-setup-d-*-data``, runbook §7.2-b) or into the
resident leaf (``~/.local/state/tos/paper-data/<종목>``) **cannot be undone**. So
the question is not "does this journal look synthetic" but "has this journal's
producer been approved to create a permanent corpus".

**The rule.**

1. The resident durable set is **never** a tenant target, whatever the journal
   says. Unconditional, both branches below.
2. If **every** row's ``source_id`` starts with a prefix in
   :data:`APPROVED_REAL_PRODUCER_PREFIXES`, the designated tenant sets are
   allowed — that is what they exist for.
3. Otherwise the data dir must be a fresh, empty directory strictly under the
   scratch root ``~/.local/state/tos/scratch/``, whose own path contains no
   symlink and no component named like a durable set.

:data:`APPROVED_REAL_PRODUCER_PREFIXES` **is empty today**, so rule 2 never fires
and every non-scratch boot is refused. ③'s PR adds its prefix there, and that
addition is the moment the first real genesis becomes possible. ⚠ ``source_id``
is self-declared and nothing authenticates it, so the allowlist attests
**intent, not provenance** — it records which producer names the operator has
decided may create a permanent corpus.

**The inversion (implementation-time correction, independent review of PR #892,
HIGH).** The first cut keyed on a *marker*: a journal carrying
``cp3-bootproof-synthetic`` was confined to scratch, and anything else was
"a real producer" and allowed anywhere. That is a denylist, and it **fails
open** — the only journals that exist today are synthetic, and most are not
marked. The reviewer's measured input: the resident render's own journal
``~/.config/tos/paper-config/bootproof_journal.jsonl``
(``source_id`` ``tos-paper-bootproof-render`` / ``tos-paper-resident-session``)
re-labelled to the mini front month, with
``TENANT_DATA_PARENT=~/.local/state/tos/cp3-setup-d-long-data``. The old guard
printed "ok — real-producer journal" and the runner would have genesised the
designated store from synthetic data; pointed at ``paper-data`` it would have
appended tenant evidence into the **live resident leaf**. Both irreversible.

**Why ONE module.** Both entry points — :mod:`tools.tos_cp3.bootproof_journal`
(which knows it is about to write a synthetic row) and the shell template
(which inspects a journal somebody else wrote) — call the functions below, so
the two cannot drift. The shell template reaches them through :func:`main`.

**No overrides.** Neither the scratch root nor the allowlist can be supplied by
a caller: a template that could be told where "scratch" is, or which producers
count, is a guard its caller can switch off. Tests move ``HOME`` and
monkeypatch the module constant instead, so the paths production uses are the
paths under test.

**Scope note (firewall).** ``tools/`` is in the reverse scan of
``tools/tos_firewall_check.py``: this module imports neither ``tos`` nor
``tos_runtime``. It is stdlib-only on purpose — the shell template runs it as a
guard, before anything heavier is imported.

Exit codes of :func:`main`: ``0`` ok, ``1`` refused, ``2`` bad arguments.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path
from typing import Any

#: Handshake string the shell template pins (``guard_checkout``'s sibling
#: ``guard_python_module`` in ``tools/broker_probes/runners/_common.sh``). A
#: template copied out of a different tree reports a different value and aborts,
#: which is the 2026-09-30 mistake #825 exists to prevent. Bump it whenever a
#: refusal below changes shape, so a stale template cannot drive a new guard.
#: ``/2`` = the allowlist inversion (review of PR #892, HIGH).
POLICY_VERSION = "cp3-tenant-bootproof/2"

#: Producers whose rows may create a PERMANENT corpus — the ONLY way a boot
#: reaches a designated tenant durable set.
#:
#: ⛔ **EMPTY ON PURPOSE.** No real producer exists yet: ③ (the real-time
#: fifteen-field producer, kickoff §5 3 ③) is unbuilt, so every journal on this
#: host today is synthetic — the resident render's
#: ``tos-paper-bootproof-render``, the resident collector's
#: ``tos-paper-resident-session``, B1a's ``tos-cp3-b1a/…`` batch output, and
#: this package's own ``cp3-bootproof-synthetic:…``. While this tuple is empty
#: every non-scratch boot is refused, which is the intended state.
#:
#: ③'s PR adds its prefix here, in the same PR that makes the producer real, and
#: says in its own comment which producer it is approving. Adding a prefix is a
#: decision to let that producer write an append-only corpus; it is not a
#: formatting change.
#:
#: ⚠ **``source_id`` is self-declared.** Nothing authenticates it, so this list
#: attests INTENT, not provenance: it records which producer names the operator
#: has decided may create a permanent corpus, and a producer that lies about its
#: name is outside what this guard can see.
#:
#: Matching requires a DELIMITER (:func:`_matches_prefix`): an entry ``p``
#: matches ``p`` exactly or ``p + "/"`` + anything. A bare ``startswith`` would
#: let ``tos-cp3-live-EVIL`` through on an entry of ``tos-cp3-live``, and an
#: entry of ``""`` would approve every row. Entries are validated at import and
#: at every call (:func:`_validated_prefixes`).
APPROVED_REAL_PRODUCER_PREFIXES: tuple[str, ...] = ()

#: The scratch root, as the plan spells it. ``expanduser()`` is applied at use
#: time, so a test can move ``HOME`` and get a throwaway root — which is also
#: how the shell template is exercised without ever touching the real one.
DEFAULT_SCRATCH_ROOT = Path("~/.local/state/tos/scratch")

#: The resident paper durable set's parent (runbook §7.2-b). Its leaves hold the
#: live resident corpus; a tenant session writing there would append tenant
#: evidence to a store whose every row is attributed to the resident deployment,
#: and activation records do not bind direction or tree (runbook §5 ⑤), so the
#: two could not be told apart afterwards.
RESIDENT_DATA_ROOT = Path("~/.local/state/tos/paper-data")

#: Names a durable-set PARENT is allowed to have (runbook §7.2-b's table). A
#: scratch path carrying one of these as a component is refused: the names are
#: how an operator tells corpora apart by path, so a scratch directory wearing
#: one is a trap for whoever reads the evidence later. Checked on the SCRATCH
#: branch only — on the allowlist branch the designated set is the intended
#: target.
DESIGNATED_PARENT_GLOBS: tuple[str, ...] = ("cp3-setup-d-*-data", "paper-data")

#: The marker :mod:`tools.tos_cp3.bootproof_journal` stamps on ``source_id``.
#: Plan §2.5 / L1: the full→mini relabel is explicit, so the whole stamp reads
#: ``cp3-bootproof-synthetic:<original contract>:<original raw_event_id>``.
#: ⚠ This is **provenance, not the rule** — it is reported, never branched on.
#: Keying the rule on it is exactly the fail-open the inversion above replaced.
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
    "every row is from an approved producer".
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
    """Refuse an allowlist entry that cannot mean what it looks like.

    Two shapes, each with its own concrete failure:

    * **empty** — ``""`` reads as "any producer". Under the delimiter rule it
      would in fact match almost nothing, which is arguably worse: the entry
      looks permissive, behaves restrictively, and nobody finds out until a real
      genesis is refused for a reason the list does not state.
    * **trailing ``/``** — ``"tos-cp3-live/"`` would require ``tos-cp3-live//…``
      because the delimiter is appended here. The entry would silently match
      nothing at all.

    Called at import (so a bad edit to the literal fails loudly, at the point
    ③'s PR touches it) and on every call (so a list substituted at runtime —
    a test, a patched deployment — is held to the same shape).
    """
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


#: Import-time shape check on the literal above. A bad edit to
#: :data:`APPROVED_REAL_PRODUCER_PREFIXES` fails at import — the loudest place,
#: and the one ③'s PR will be standing in when it adds its prefix.
_validated_prefixes(APPROVED_REAL_PRODUCER_PREFIXES)


def _matches_prefix(source_id: str, prefix: str) -> bool:
    """``source_id`` is ``prefix`` exactly, or ``prefix`` followed by ``/``.

    The delimiter is the whole point. A bare ``startswith`` approves
    ``tos-cp3-live-EVIL`` on an entry of ``tos-cp3-live`` — a producer name is a
    namespace, not a string prefix, and the separator is what makes the boundary
    real. B1a's own ``source_id`` already has this shape
    (``tos-cp3-b1a/0.1.0``: name, slash, version).
    """
    return source_id == prefix or source_id.startswith(prefix + "/")


def unapproved_rows(journal_path: Path) -> tuple[int, ...]:
    """1-indexed line numbers whose ``source_id`` is **not** on the allowlist.

    **Every** row is examined, not the first one. The concrete failing input:
    rows 1-2 carry an approved producer's ``source_id`` and row 3 carries
    something else — a first-row-only check would clear that journal and let the
    unapproved rows into a permanent corpus. (This is the same "all rows, not
    the first" property the plan's third red proof names; the inversion moved it
    from the marker to the allowlist, and it survives the move.)

    An EMPTY allowlist marks every row unapproved: ``any()`` over no prefixes is
    False, with no second code path to get wrong.
    """
    approved = _validated_prefixes(tuple(APPROVED_REAL_PRODUCER_PREFIXES))
    return tuple(
        line_no
        for line_no, payload in _rows(journal_path)
        if not isinstance(payload.get("source_id"), str)
        or not any(_matches_prefix(payload["source_id"], prefix) for prefix in approved)
    )


def synthetic_rows(journal_path: Path) -> tuple[int, ...]:
    """1-indexed line numbers carrying :data:`SYNTHETIC_SOURCE_PREFIX`.

    Reporting only — :func:`main` names them so an operator can see what the
    journal says about itself. **Nothing branches on this.**
    """
    return tuple(
        line_no
        for line_no, payload in _rows(journal_path)
        if isinstance(payload.get("source_id"), str)
        and payload["source_id"].startswith(SYNTHETIC_SOURCE_PREFIX)
    )


def _scratch_root() -> Path:
    """The resolved scratch root, refusing a symlinked one.

    **The concrete failing input** (review MEDIUM): ``~/.local/state/tos/scratch``
    is a symlink to ``~/.local/state/tos``. Every designated set then resolves
    *under* the resolved root, so containment accepts
    ``scratch/cp3-setup-d-long-data/A05611`` — the exact directory the rule
    exists to protect. Comparing ``absolute()`` with ``resolve()`` catches a
    symlink at ANY component of the root, not just its last one.
    """
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
    """Refuse a data dir inside the resident paper durable set. **Unconditional.**

    Applies on BOTH branches — an approved real producer does not make the
    resident corpus a legitimate tenant target. The resident leaf is live: its
    rows are attributed to the resident deployment, activation records bind
    neither direction nor tree (runbook §5 ⑤), and the store is append-only, so
    tenant rows mixed in could never be separated again.
    """
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
    """Refuse unless ``data_dir`` is a scratch directory this boot may genesis.

    Four clauses, each with its own concrete failing input and its own red proof
    (``tests/tools/test_cp3_bootproof.py``); none of them can fire only behind
    another (#838):

    * **symlinked root** — :func:`_scratch_root`.
    * **containment** — the resolved dir must lie strictly under the resolved
      root. Equality with the root is refused by the same comparison and
      deliberately not spelled twice: a path is never its own parent, so a
      separate ``==`` test would be a clause that can never fire alone.
      Resolving BOTH sides is also what refuses a symlink sitting *inside* the
      scratch root and pointing at a designated dir.
    * **durable-set name** — no component may be named like a durable-set parent
      (:data:`DESIGNATED_PARENT_GLOBS`). Its own failing input, reachable with
      every other clause satisfied: ``scratch/cp3-setup-d-long-data/A05611`` —
      genuinely under scratch, genuinely empty, and a path that any later reader
      of the evidence would misfile.
    * **emptiness** — a directory that already holds something is somebody's
      durable set (or somebody's run), and genesis into it is not reversible.
      Absent is fine: the caller creates it immediately after this returns.

    Args:
        data_dir: The directory genesis will create its four stores in — the
            LEAF (``<parent>/<종목>``), not the parent, because that is where the
            append-only corpus actually lands.
        why: What made this check apply, quoted in the refusal message.

    Raises:
        BootProofGuardRefused: Any clause.
    """
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
    """Refuse a boot-proof journal written outside the scratch root.

    :mod:`tools.tos_cp3.bootproof_journal` writes **synthetic** rows and replaces
    its output file atomically and in whole. Without this, ``--out
    ~/.config/tos/paper-config/bootproof_journal.jsonl`` would silently replace
    the LIVE resident journal with one synthetic row — the resident session's
    only observation source (review LOW). The file's parent is what is checked:
    the file itself need not exist yet.
    """
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
    """The rule (module docstring): resident never; allowlisted may; else scratch.

    Fail-closed. With :data:`APPROVED_REAL_PRODUCER_PREFIXES` empty — its state
    until ③ lands — the middle branch never fires and every non-scratch boot is
    refused.
    """
    require_not_resident_store(data_dir)

    unapproved = unapproved_rows(journal_path)
    if not unapproved:
        return

    approved = ", ".join(repr(p) for p in APPROVED_REAL_PRODUCER_PREFIXES) or (
        "<empty — no real producer is approved yet; ③ is unbuilt>"
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

    Deliberately offers no ``--scratch-root`` and no allowlist flag (module
    docstring, "No overrides").
    """
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
