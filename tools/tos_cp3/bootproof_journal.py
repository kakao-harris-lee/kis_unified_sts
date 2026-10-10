#!/usr/bin/env python3
"""CP-3 tenant boot-proof journal — ONE row, the fifteen B1a fields, stamped now.

Plan ``docs/plans/2026-10-09-tos-cp3-tenant-render-and-boot-path-plan.md`` §2.5.
Until ③ (the real-time field producer) exists, the tenant tree has no
observation journal, and ``journal.mode: external`` makes the renderer refuse
without one. This writes the one row that lets the wiring be exercised:

    render → activation → strategy loader → fifteen declared fields → decision

**What this proves, and what it does NOT.** The row is stamped with the *write*
time, which is what the operator's 2026-10-09 decision requires of ③ as well:
the tenant tree's ``critical_input_policy.yaml`` declares ``max_age_ms: 800``
×15, and that key and the kernel's own time path measure the SAME quantity
(``now_ms - as_of_ms``). A bar-label stamp — B1a's own semantics, "the label,
not label+60s" — gives every observation a minimum age of 60,000 ms, i.e. 75×
the budget, and raising the limit cannot fix it because the kernel re-measures
the same quantity. So the stamp here is append time.

Even so, **800 ms is a narrow window**: if more than 800 ms passes between this
write and the boot's first marketfeed pass, ``_derive_field_state`` returns
``(UNKNOWN, "stale")`` for all fifteen, the kernel's UNKNOWN floor drops the
keys, R1's AND is false and the session ends at NO_ACTION. That is the same
shape the resident render's own boot-proof observation has had all along
(runbook ``tos-paper-boot.md``: "렌더가 만든 부팅 증명 관측은 부팅 시점에 이미
STALE 이다"). Plan §2.5 was downgraded by PR #887 for exactly this reason, so
say it plainly: this tool proves **wiring**, not **field consumption**. Which
way an actual run goes is recorded in the runbook when it is run.

**The values are borrowed, and the relabel is explicit (plan L1).** The fifteen
values come from one bar of a B1a ``fields.jsonl`` run — real measured values,
already driven through a decision by B1b, so a boot-proof outcome can be read
against that trace. But that run's lineage is the **full** contract
``101S6000`` (session 2025-12-08, ~583 price level), while a tenant boot has to
carry the rendered **mini** code or nothing consumes the row. That is a
full→mini relabel, the same shape as the 10-08 v1 misreading, so it is not
hidden: ``source_id`` is

    ``cp3-bootproof-synthetic:<original contract>:<original raw_event_id>``

which names the original contract and the original row, and the
``cp3-bootproof-synthetic`` prefix is what
:mod:`tools.tos_cp3.bootproof_guard` refuses to let near a designated durable
set. A result from this boot is NOT a market fact.

Firewall: legacy side. No ``tos`` / ``tos_runtime`` import — the journal row
shape mirrors ``tos_runtime.marketfeed.journal._REQUIRED_KEYS`` through
:data:`tools.tos_cp3.produce_fields.JOURNAL_REQUIRED_KEYS`, which is B1a's own
mirrored literal (``tools`` → ``tools`` is allowed), and
``tos/runtime/tests/marketfeed/test_journal_cp3_bootproof_row.py`` proves the
real reader accepts the committed fixture this tool reproduces.

Usage (every value explicit — this tool ships no instance defaults)::

    .venv/bin/python -m tools.tos_cp3.bootproof_journal \\
        --fields ~/.local/state/tos/measure/cp3-short-parity-run1/b1a/fields.jsonl \\
        --raw-event-id '101S6000:1m:20251208T084500+0900' \\
        --instrument A05611 \\
        --out ~/.local/state/tos/scratch/cp3-bootproof-20261010/journal.jsonl \\
        --data-dir ~/.local/state/tos/scratch/cp3-bootproof-20261010/data/A05611

Exit codes: ``0`` ok, ``1`` refusal, ``2`` bad arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3.bootproof_guard import (  # noqa: E402
    SYNTHETIC_SOURCE_PREFIX,
    BootProofGuardRefused,
    require_scratch_data_dir,
    require_scratch_output_path,
)
from tools.tos_cp3.produce_fields import (  # noqa: E402
    FIELD_ORDER,
    JOURNAL_REQUIRED_KEYS,
)

#: Scalar types a journal field value may have. MIRRORS
#: ``tos_runtime.marketfeed.journal._SCALAR_FIELD_TYPES`` (= ``tos.dsl
#: .ScalarValue``); the firewall forbids importing it, so it is restated. ``bool``
#: is listed first for the same reason that module lists it first — it is an
#: ``int`` subclass, and an unannounced ``True -> 1`` narrowing is the kind of
#: silent coercion both sides refuse.
SCALAR_FIELD_TYPES: tuple[type, ...] = (bool, int, float, str)


class BootProofJournalError(Exception):
    """The tool refused: a bad source row, a bad selection, or an unwritable out."""


@dataclass(frozen=True)
class BorrowedBar:
    """The one B1a row whose values this journal re-labels."""

    raw_event_id: str
    instrument: str
    fields: dict[str, Any]


def select_bar(fields_path: Path, raw_event_id: str) -> BorrowedBar:
    """Return the B1a row named by ``raw_event_id``, refusing anything ambiguous.

    There is no "pick a bar for me" mode on purpose: the chosen bar is the whole
    provenance of the boot-proof row, and a default would make one run's bar
    silently become the next run's — the same discipline the tracked probe
    runners keep for instance values (``tools/broker_probes/runners/run_p_ca.sh``).
    """
    if not fields_path.is_file():
        raise BootProofJournalError(f"B1a fields file does not exist: {fields_path}")

    matches: list[dict[str, Any]] = []
    with fields_path.open(encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise BootProofJournalError(
                    f"{fields_path}:{line_no}: not valid JSON ({exc})"
                ) from exc
            if not isinstance(payload, dict):
                raise BootProofJournalError(
                    f"{fields_path}:{line_no}: not a JSON object "
                    f"(got {type(payload).__name__})"
                )
            if payload.get("raw_event_id") == raw_event_id:
                matches.append(payload)

    if not matches:
        raise BootProofJournalError(
            f"{fields_path} has no row with raw_event_id {raw_event_id!r}"
        )
    if len(matches) > 1:
        raise BootProofJournalError(
            f"{fields_path} has {len(matches)} rows with raw_event_id {raw_event_id!r} — "
            "the borrowed bar must be unambiguous, it is this row's whole provenance"
        )

    payload = matches[0]
    missing = set(JOURNAL_REQUIRED_KEYS) - payload.keys()
    if missing:
        raise BootProofJournalError(
            f"{fields_path}: row {raw_event_id!r} is missing required key(s) "
            f"{sorted(missing)}"
        )
    source_instrument = payload["instrument"]
    if not isinstance(source_instrument, str) or not source_instrument.strip():
        raise BootProofJournalError(
            f"{fields_path}: row {raw_event_id!r} has a blank 'instrument'"
        )
    fields = payload["fields"]
    if not isinstance(fields, dict):
        raise BootProofJournalError(
            f"{fields_path}: row {raw_event_id!r} 'fields' is not an object "
            f"(got {type(fields).__name__})"
        )
    if sorted(fields) != sorted(FIELD_ORDER):
        raise BootProofJournalError(
            f"{fields_path}: row {raw_event_id!r} publishes {sorted(fields)}, not B1a's "
            f"fifteen FIELD_ORDER keys {sorted(FIELD_ORDER)} — the tenant tree's "
            "critical_input_policy.yaml declares exactly those fifteen"
        )
    for key, value in fields.items():
        if not isinstance(value, SCALAR_FIELD_TYPES):
            raise BootProofJournalError(
                f"{fields_path}: row {raw_event_id!r} field {key!r} is "
                f"{type(value).__name__}, which the runtime journal reader refuses "
                "(must be bool|int|float|str)"
            )
    return BorrowedBar(
        raw_event_id=raw_event_id, instrument=source_instrument, fields=dict(fields)
    )


def build_row(bar: BorrowedBar, instrument: str, as_of_ms: int) -> dict[str, Any]:
    """The journal row: the borrowed values, this instrument, APPEND-TIME ``as_of_ms``.

    Key order mirrors B1a's own ``FieldRecord.to_payload`` so a reader can diff
    the two files line for line; ``fields`` is emitted in ``FIELD_ORDER``.
    """
    return {
        "raw_event_id": f"cp3-bootproof:{instrument}:{as_of_ms}",
        "source_id": f"{SYNTHETIC_SOURCE_PREFIX}:{bar.instrument}:{bar.raw_event_id}",
        "instrument": instrument,
        "as_of_ms": as_of_ms,
        "fields": {name: bar.fields[name] for name in FIELD_ORDER},
    }


def write_journal(out_path: Path, row: dict[str, Any]) -> None:
    """Replace ``out_path`` with the single ``row``, atomically.

    Atomic whole-file replacement, not an append: the runtime reader deliberately
    has no trailing-partial-line special case, so a half-written final line
    refuses the WHOLE poll (``tos_runtime/marketfeed/journal.py`` docstring —
    "the fix belongs upstream, in the collector"). The temp file is a sibling so
    ``os.replace`` stays on one filesystem.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, separators=(",", ":"), ensure_ascii=True) + "\n"
    tmp = out_path.with_name(out_path.name + ".partial")
    tmp.write_text(line, encoding="utf-8")
    os.replace(tmp, out_path)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Exit codes: ``0`` ok, ``1`` refusal, ``2`` bad arguments."""
    parser = argparse.ArgumentParser(
        prog="bootproof_journal.py",
        description=(
            "Write ONE CP-3 tenant boot-proof observation: the fifteen B1a fields of a "
            "chosen bar, re-labelled onto the rendered mini contract and stamped with "
            "the write time (plan 2026-10-09 §2.5)."
        ),
    )
    parser.add_argument(
        "--fields",
        type=Path,
        required=True,
        help=(
            "a B1a fields.jsonl. No default: the suggested source is "
            "~/.local/state/tos/measure/cp3-short-parity-run1/b1a/fields.jsonl, and it is "
            "named here rather than defaulted so the borrowed run is always on the "
            "command line"
        ),
    )
    parser.add_argument(
        "--raw-event-id",
        required=True,
        help="which bar of --fields to borrow; it is recorded in source_id",
    )
    parser.add_argument(
        "--instrument",
        required=True,
        help="the RENDERED mini contract code this row is labelled with",
    )
    parser.add_argument("--out", type=Path, required=True, help="journal path to write")
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help=(
            "the durable-set LEAF the boot will genesis. Checked here with the same rule "
            "the run template applies, so a designated tenant data dir is refused at "
            "EITHER entry point (plan §2.5)"
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        # The scratch rule first: this tool is ABOUT to write a synthetic row, so
        # the rule applies by construction — there is no journal to inspect yet,
        # and no allowlisted producer wrote what is about to be written.
        why = (
            f"this tool writes a {SYNTHETIC_SOURCE_PREFIX!r} row, which is not from an "
            "approved real producer"
        )
        require_scratch_data_dir(args.data_dir, why=why)
        # And the OUTPUT itself (review LOW): this writes synthetic rows and
        # replaces the file whole, so an unconstrained --out can overwrite a live
        # journal — e.g. the resident session's own
        # ~/.config/tos/paper-config/bootproof_journal.jsonl.
        require_scratch_output_path(args.out)
        bar = select_bar(args.fields, args.raw_event_id)
        as_of_ms = time.time_ns() // 1_000_000
        row = build_row(bar, args.instrument, as_of_ms)
        write_journal(args.out, row)
    except (BootProofGuardRefused, BootProofJournalError) as exc:
        print(f"bootproof_journal: REFUSED — {exc}", file=sys.stderr)
        return 1

    print(
        f"bootproof_journal: wrote 1 row to {args.out}\n"
        f"  raw_event_id : {row['raw_event_id']}\n"
        f"  source_id    : {row['source_id']}\n"
        f"  instrument   : {row['instrument']} (relabelled from {bar.instrument})\n"
        f"  as_of_ms     : {row['as_of_ms']} (append time, NOT the bar label)\n"
        f"  fields       : {len(row['fields'])}\n"
        "  ⚠ max_age_ms is 800 in the tenant tree: if boot is more than 800 ms after "
        "this write, all fifteen read STALE. This proves WIRING, not field consumption."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI tests
    raise SystemExit(main())
