#!/usr/bin/env python3
"""CP-3 tenant boot-proof journal — ONE row, the fifteen B1a fields, stamped now."""

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
    """Return the B1a row named by ``raw_event_id``, refusing anything ambiguous."""
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
    """The journal row: the borrowed values, this instrument, APPEND-TIME ``as_of_ms``."""
    return {
        "raw_event_id": f"cp3-bootproof:{instrument}:{as_of_ms}",
        "source_id": f"{SYNTHETIC_SOURCE_PREFIX}:{bar.instrument}:{bar.raw_event_id}",
        "instrument": instrument,
        "as_of_ms": as_of_ms,
        "fields": {name: bar.fields[name] for name in FIELD_ORDER},
    }


def write_journal(out_path: Path, row: dict[str, Any]) -> None:
    """Replace ``out_path`` with the single ``row``, atomically."""
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
        why = (
            f"this tool writes a {SYNTHETIC_SOURCE_PREFIX!r} row, which is not from an "
            "approved real producer"
        )
        require_scratch_data_dir(args.data_dir, why=why)
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
