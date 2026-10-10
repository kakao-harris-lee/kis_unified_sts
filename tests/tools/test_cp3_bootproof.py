"""CP-3 tenant boot-proof journal + run template (plan 2026-10-09 §2.5 / §2.6).

Every guard in :mod:`tools.tos_cp3.bootproof_guard` gets its OWN red proof here,
and the three the plan names by hand are marked as such. The discipline is the
repo's repeated one (#838): a guard whose concrete failing input nobody can
write is a guard that blocks nothing, and a clause that only ever fires behind
another clause is a *masked* clause — so each red proof below is built so that
exactly the clause it names is the one that refuses.

The run template's own tests follow ``tests/tools/test_broker_probes_ca.py``'s
shape: a throwaway git checkout holding a copy of the template, so the guards
run against a real ``git`` rather than a stubbed one.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from tools.tos_cp3 import bootproof_guard, bootproof_journal
from tools.tos_cp3.bootproof_guard import (
    SYNTHETIC_SOURCE_PREFIX,
    BootProofGuardRefused,
    require_scratch_rule,
)
from tools.tos_cp3.produce_fields import FIELD_ORDER

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: The template under test and the shared guard file it sources.
_RUNNER = _REPO_ROOT / "tools" / "tos_cp3" / "runners" / "run_tenant_session.sh"
_RUNNER_COMMON = _REPO_ROOT / "tools" / "broker_probes" / "runners" / "_common.sh"

#: The committed row ``tos/runtime/tests/marketfeed/test_journal_cp3_bootproof_row.py``
#: feeds to the REAL ``JsonLinesObservationJournal``. The firewall forbids
#: importing that reader from here, so the proof is split: that test shows the
#: reader accepts this file, and :func:`test_the_tool_reproduces_the_committed_fixture`
#: below shows this tool still produces it. Neither half can drift alone.
_FIXTURE = (
    _REPO_ROOT / "tos" / "runtime" / "tests" / "fixtures" / "cp3-bootproof-row.jsonl"
)

#: The bar the fixture borrows, and the B1a run it came from.
_FIXTURE_RAW_EVENT_ID = "101S6000:1m:20251208T092000+0900"
_FIXTURE_SOURCE_INSTRUMENT = "101S6000"
_FIXTURE_INSTRUMENT = "A05611"

#: MIRRORS ``tos/runtime/src/tos_runtime/marketfeed/journal.py::_REQUIRED_KEYS``.
#: ``tests/`` is outside ``tos/``, so the five names are restated as a literal —
#: the same mirroring note ``tests/tools/test_cp3_produce_fields.py`` carries.
JOURNAL_REQUIRED_KEYS_MIRROR = frozenset(
    {"raw_event_id", "instrument", "as_of_ms", "fields", "source_id"}
)


# ---------------------------------------------------------------------------
# Journal fixtures
# ---------------------------------------------------------------------------


def _row(*, source_id: str, instrument: str = _FIXTURE_INSTRUMENT) -> dict[str, Any]:
    return {
        "raw_event_id": f"row-{source_id}-{instrument}",
        "source_id": source_id,
        "instrument": instrument,
        "as_of_ms": 1791601200000,
        "fields": {"close_x100": 57950},
    }


def _journal(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _synthetic_journal(path: Path, instrument: str = _FIXTURE_INSTRUMENT) -> Path:
    return _journal(
        path,
        [
            _row(
                source_id=f"{SYNTHETIC_SOURCE_PREFIX}:{_FIXTURE_SOURCE_INSTRUMENT}:bar",
                instrument=instrument,
            )
        ],
    )


def _real_journal(path: Path, instrument: str = _FIXTURE_INSTRUMENT) -> Path:
    return _journal(
        path, [_row(source_id="tos-cp3-third-producer/0.1.0", instrument=instrument)]
    )


def _state(tmp_path: Path) -> tuple[Path, Path]:
    """``(scratch root, the designated tenant data parent)`` under ``tmp_path``.

    Named exactly like the real ones (runbook §7.2-b) but rooted in ``tmp_path``:
    nothing under the real ``~/.local/state/tos`` is ever created by these tests.
    """
    state = tmp_path / ".local" / "state" / "tos"
    scratch = state / "scratch"
    scratch.mkdir(parents=True)
    designated = state / "cp3-setup-d-long-data"
    designated.mkdir(parents=True)
    return scratch, designated


# ---------------------------------------------------------------------------
# The scratch rule — the three red proofs plan §2.5 names, plus the others
# ---------------------------------------------------------------------------


def test_the_default_scratch_root_is_the_one_the_plan_names() -> None:
    """The literal, pinned. Every red proof below moves the root to ``tmp_path``,
    so without this nothing would say WHICH directory production actually uses."""
    assert str(bootproof_guard.DEFAULT_SCRATCH_ROOT) == "~/.local/state/tos/scratch"
    assert bootproof_guard.SYNTHETIC_SOURCE_PREFIX == "cp3-bootproof-synthetic"


@pytest.mark.parametrize("leaf", ["", "A05611"])
def test_red_a_designated_data_dir_with_a_synthetic_journal_is_refused(
    tmp_path: Path, leaf: str
) -> None:
    """Plan §2.5 red proof (a) — the H2 input verbatim.

    ``run_tenant_session.sh`` pointed at the designated tenant durable set with a
    boot-proof journal would genesis ``cp3-setup-d-long-data`` from synthetic
    data, and an append-only evidence store cannot be un-genesised.

    Both shapes are checked: the designated parent itself, and the contract-month
    leaf under it (the path the template actually hands over). Both are EMPTY, so
    the emptiness clause has nothing to say and the refusal is the containment
    clause's alone.
    """
    scratch, designated = _state(tmp_path)
    data_dir = designated / leaf if leaf else designated
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(journal, data_dir, scratch_root=scratch)
    assert "scratch root" in str(excinfo.value)


def test_red_b_a_symlink_inside_scratch_pointing_at_a_designated_dir_is_refused(
    tmp_path: Path,
) -> None:
    """Plan §2.5 red proof (b) — this one fails without ``Path.resolve()``.

    The test asserts the property, not just the outcome: the path handed to the
    guard IS lexically under the scratch root, so a containment check written on
    strings would clear it. Only resolving both sides refuses it.
    """
    scratch, designated = _state(tmp_path)
    link = scratch / "looks-like-scratch"
    link.symlink_to(designated, target_is_directory=True)
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    # The property a string comparison would have been fooled by.
    assert str(link).startswith(str(scratch) + os.sep)
    assert link.resolve() == designated.resolve()

    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(journal, link, scratch_root=scratch)
    assert str(designated.resolve()) in str(excinfo.value)


def test_red_c_a_synthetic_marker_on_the_third_row_only_is_refused(
    tmp_path: Path,
) -> None:
    """Plan §2.5 red proof (c) — this one fails if only the first row is checked.

    The first two rows carry a real producer's ``source_id``; the third carries
    the marker. A first-row-only implementation clears this journal and the
    synthetic data reaches the designated durable set.
    """
    scratch, designated = _state(tmp_path)
    journal = _journal(
        tmp_path / "journal.jsonl",
        [
            _row(source_id="tos-cp3-third-producer/0.1.0"),
            _row(source_id="tos-cp3-third-producer/0.1.0"),
            _row(
                source_id=f"{SYNTHETIC_SOURCE_PREFIX}:{_FIXTURE_SOURCE_INSTRUMENT}:bar"
            ),
        ],
    )

    # The property a first-row-only check would have been fooled by.
    first = json.loads(journal.read_text(encoding="utf-8").splitlines()[0])
    assert not first["source_id"].startswith(SYNTHETIC_SOURCE_PREFIX)
    assert bootproof_guard.synthetic_rows(journal) == (3,)

    with pytest.raises(BootProofGuardRefused):
        require_scratch_rule(journal, designated / "A05611", scratch_root=scratch)


def test_a_non_empty_scratch_dir_is_refused(tmp_path: Path) -> None:
    """The emptiness clause, isolated: the directory IS under the scratch root,
    so containment has nothing to say. Genesis into a directory that already
    holds something appends synthetic evidence to whatever is there."""
    scratch, _designated = _state(tmp_path)
    data_dir = scratch / "bp" / "data" / "A05611"
    data_dir.mkdir(parents=True)
    (data_dir / "evidence.sqlite3").write_text("x", encoding="utf-8")
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(journal, data_dir, scratch_root=scratch)
    assert "newly created and empty" in str(excinfo.value)


def test_a_file_where_the_data_dir_should_be_is_refused(tmp_path: Path) -> None:
    """Same clause's other half — ``iterdir`` would raise instead of refusing."""
    scratch, _designated = _state(tmp_path)
    data_dir = scratch / "bp"
    data_dir.parent.mkdir(parents=True, exist_ok=True)
    data_dir.write_text("not a directory", encoding="utf-8")
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(journal, data_dir, scratch_root=scratch)
    assert "not a directory" in str(excinfo.value)


def test_the_scratch_root_itself_is_refused(tmp_path: Path) -> None:
    """ "Under the scratch root" means strictly under it: the root is the parent
    of the one-off session directories, not a durable set of its own."""
    scratch, _designated = _state(tmp_path)
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    with pytest.raises(BootProofGuardRefused):
        require_scratch_rule(journal, scratch, scratch_root=scratch)


def test_a_fresh_scratch_dir_is_accepted(tmp_path: Path) -> None:
    """The green side: absent is fine — the caller creates it right after."""
    scratch, _designated = _state(tmp_path)
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    require_scratch_rule(
        journal, scratch / "bp" / "data" / "A05611", scratch_root=scratch
    )
    (scratch / "bp" / "data" / "A05611").mkdir(parents=True)
    require_scratch_rule(
        journal, scratch / "bp" / "data" / "A05611", scratch_root=scratch
    )


def test_a_real_producer_journal_is_not_subject_to_the_scratch_rule(
    tmp_path: Path,
) -> None:
    """③'s first real genesis goes into the DESIGNATED durable set — that is what
    those directories are for. Without this the rule would block the thing it
    exists to protect."""
    scratch, designated = _state(tmp_path)
    journal = _real_journal(tmp_path / "journal.jsonl")

    require_scratch_rule(journal, designated / "A05611", scratch_root=scratch)
    assert bootproof_guard.synthetic_rows(journal) == ()


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("{not json}\n", "not valid JSON"),
        ('["a list"]\n', "not a JSON object"),
        ("\n  \n", "holds no rows"),
    ],
)
def test_an_unreadable_journal_is_refused_not_cleared(
    tmp_path: Path, content: str, expected: str
) -> None:
    """Fail-closed: a line this guard cannot parse is a line whose ``source_id``
    it cannot clear, so "unreadable" must never collapse into "no synthetic rows
    found" — which would hand a corrupt journal the designated durable set."""
    scratch, designated = _state(tmp_path)
    journal = tmp_path / "journal.jsonl"
    journal.write_text(content, encoding="utf-8")

    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(journal, designated, scratch_root=scratch)
    assert expected in str(excinfo.value)


def test_a_missing_journal_is_refused(tmp_path: Path) -> None:
    scratch, designated = _state(tmp_path)
    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(tmp_path / "nope.jsonl", designated, scratch_root=scratch)
    assert "does not exist" in str(excinfo.value)


def test_a_journal_for_another_contract_month_is_refused(tmp_path: Path) -> None:
    """Isolated from the scratch rule on purpose: a REAL journal, so only the
    instrument clause can fire. A mismatch is not an error downstream — the
    runtime reader filters by instrument, so it is zero observations and a
    session that boots cleanly and proves nothing."""
    journal = _real_journal(tmp_path / "journal.jsonl", instrument="A05612")

    bootproof_guard.require_journal_instrument(journal, "A05612")
    with pytest.raises(BootProofGuardRefused) as excinfo:
        bootproof_guard.require_journal_instrument(journal, "A05611")
    assert "A05612" in str(excinfo.value)


def test_the_guard_cli_refuses_and_says_why(
    tmp_path: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shell template reaches the rule through this entry point, so the exit
    codes are part of the contract.

    The CLI has no ``--scratch-root`` flag — a template that could be told where
    "scratch" is would be a guard its caller can switch off — so the throwaway
    root is installed by moving ``HOME``, which is also how the shell tests below
    keep away from the real ``~/.local/state/tos``.
    """
    scratch, designated = _state(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    assert (
        bootproof_guard.main(
            [
                "--journal",
                str(journal),
                "--data-dir",
                str(scratch / "bp" / "A05611"),
                "--instrument",
                _FIXTURE_INSTRUMENT,
            ]
        )
        == 0
    )
    assert (
        bootproof_guard.main(
            [
                "--journal",
                str(journal),
                "--data-dir",
                str(designated / "A05611"),
                "--instrument",
                _FIXTURE_INSTRUMENT,
            ]
        )
        == 1
    )
    assert "REFUSED" in capsys.readouterr().err


def test_the_cli_offers_no_scratch_root_flag() -> None:
    """Stated directly, because the absence is the point and an added flag would
    otherwise be an invisible widening."""
    with pytest.raises(SystemExit) as excinfo:
        bootproof_guard.main(
            [
                "--journal",
                "j",
                "--data-dir",
                "d",
                "--instrument",
                "A05611",
                "--scratch-root",
                "/tmp",
            ]
        )
    assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# The tool
# ---------------------------------------------------------------------------


def _b1a_source(tmp_path: Path, rows: list[dict[str, Any]] | None = None) -> Path:
    """A miniature B1a ``fields.jsonl`` — same wire shape, two bars."""
    if rows is None:
        fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        rows = [
            {
                "raw_event_id": _FIXTURE_RAW_EVENT_ID,
                "source_id": "tos-cp3-b1a/0.1.0",
                "instrument": _FIXTURE_SOURCE_INSTRUMENT,
                "as_of_ms": 1765153200000,
                "fields": dict(fixture["fields"]),
            },
            {
                "raw_event_id": "101S6000:1m:20251208T092100+0900",
                "source_id": "tos-cp3-b1a/0.1.0",
                "instrument": _FIXTURE_SOURCE_INSTRUMENT,
                "as_of_ms": 1765153260000,
                "fields": dict(fixture["fields"]),
            },
        ]
    return _journal(tmp_path / "b1a" / "fields.jsonl", rows)


def test_the_row_carries_the_fifteen_fields_in_b1a_order(tmp_path: Path) -> None:
    bar = bootproof_journal.select_bar(_b1a_source(tmp_path), _FIXTURE_RAW_EVENT_ID)
    row = bootproof_journal.build_row(bar, _FIXTURE_INSTRUMENT, 1791601200000)

    assert set(row) == JOURNAL_REQUIRED_KEYS_MIRROR
    assert tuple(row["fields"]) == FIELD_ORDER
    assert len(FIELD_ORDER) == 15


def test_the_relabel_is_explicit_in_source_id(tmp_path: Path) -> None:
    """Plan L1: the borrowed bar is the FULL contract ``101S6000`` and the row
    has to carry the rendered MINI code or nothing consumes it. The relabel is
    named rather than hidden, so a result from this boot is never read as a
    market fact."""
    bar = bootproof_journal.select_bar(_b1a_source(tmp_path), _FIXTURE_RAW_EVENT_ID)
    row = bootproof_journal.build_row(bar, _FIXTURE_INSTRUMENT, 1791601200000)

    assert row["instrument"] == _FIXTURE_INSTRUMENT
    assert row["source_id"] == (
        f"{SYNTHETIC_SOURCE_PREFIX}:{_FIXTURE_SOURCE_INSTRUMENT}:{_FIXTURE_RAW_EVENT_ID}"
    )
    # And the guard that keeps it out of a designated durable set actually sees it.
    journal = _journal(tmp_path / "j.jsonl", [row])
    assert bootproof_guard.synthetic_rows(journal) == (1,)


def test_as_of_ms_is_the_write_time_not_the_bar_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The operator's 2026-10-09 decision for ③, applied here: ``max_age_ms`` 800
    and the kernel's time path measure the SAME quantity, and B1a's own
    ``as_of_ms`` is the bar LABEL — a minimum age of 60,000 ms, 75× the budget.
    A label stamp can never be fresh, at any limit."""
    source = _b1a_source(tmp_path)
    label_as_of = json.loads(source.read_text(encoding="utf-8").splitlines()[0])[
        "as_of_ms"
    ]
    _state(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    before = time.time_ns() // 1_000_000
    assert (
        bootproof_journal.main(
            [
                "--fields",
                str(source),
                "--raw-event-id",
                _FIXTURE_RAW_EVENT_ID,
                "--instrument",
                _FIXTURE_INSTRUMENT,
                "--out",
                str(tmp_path / "out" / "journal.jsonl"),
                "--data-dir",
                str(tmp_path / ".local/state/tos/scratch/bp/A05611"),
            ]
        )
        == 0
    )
    after = time.time_ns() // 1_000_000

    written = json.loads(
        (tmp_path / "out" / "journal.jsonl").read_text(encoding="utf-8")
    )
    assert before <= written["as_of_ms"] <= after
    assert written["as_of_ms"] != label_as_of
    # 60 s is the bar period, so the label is at least that stale the moment it
    # is written — the number the tenant policy's 800 ms cannot accommodate.
    assert written["as_of_ms"] - label_as_of > 60_000


def test_the_tool_refuses_a_designated_data_dir(
    tmp_path: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same refusal as the run template, reached from the OTHER entry point —
    that is why it lives in one module (plan §2.5: "두 진입점 어느 쪽에서도
    막히게")."""
    source = _b1a_source(tmp_path)
    _scratch, designated = _state(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    rc = bootproof_journal.main(
        [
            "--fields",
            str(source),
            "--raw-event-id",
            _FIXTURE_RAW_EVENT_ID,
            "--instrument",
            _FIXTURE_INSTRUMENT,
            "--out",
            str(tmp_path / "out" / "journal.jsonl"),
            "--data-dir",
            str(designated / "A05611"),
        ]
    )
    assert rc == 1
    assert "REFUSED" in capsys.readouterr().err
    assert not (tmp_path / "out" / "journal.jsonl").exists()


def test_the_tool_refuses_an_unknown_or_ambiguous_bar(tmp_path: Path) -> None:
    """No "pick a bar for me" mode: the chosen bar is this row's whole provenance,
    and a default is how one run's bar silently becomes the next run's."""
    fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    duplicate = {
        "raw_event_id": _FIXTURE_RAW_EVENT_ID,
        "source_id": "tos-cp3-b1a/0.1.0",
        "instrument": _FIXTURE_SOURCE_INSTRUMENT,
        "as_of_ms": 1765153200000,
        "fields": dict(fixture["fields"]),
    }
    with pytest.raises(bootproof_journal.BootProofJournalError, match="no row with"):
        bootproof_journal.select_bar(_b1a_source(tmp_path), "nope")
    with pytest.raises(bootproof_journal.BootProofJournalError, match="2 rows"):
        bootproof_journal.select_bar(
            _b1a_source(tmp_path, [duplicate, dict(duplicate)]), _FIXTURE_RAW_EVENT_ID
        )


def test_the_tool_refuses_a_bar_that_is_not_the_fifteen_fields(tmp_path: Path) -> None:
    """The tenant tree declares exactly fifteen; a row short of them would boot
    and withhold, which looks like a freshness problem and is not one."""
    fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    short = dict(fixture["fields"])
    short.pop("eod")
    row = {
        "raw_event_id": _FIXTURE_RAW_EVENT_ID,
        "source_id": "tos-cp3-b1a/0.1.0",
        "instrument": _FIXTURE_SOURCE_INSTRUMENT,
        "as_of_ms": 1765153200000,
        "fields": short,
    }
    with pytest.raises(bootproof_journal.BootProofJournalError, match="FIELD_ORDER"):
        bootproof_journal.select_bar(
            _b1a_source(tmp_path, [row]), _FIXTURE_RAW_EVENT_ID
        )


def test_the_tool_refuses_a_non_scalar_field(tmp_path: Path) -> None:
    """``tos.dsl.ScalarValue`` is ``bool|int|float|str``; the runtime journal
    reader refuses the WHOLE poll on anything else, so catching it at write time
    is the difference between one bad row and no data at all."""
    fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    bad = dict(fixture["fields"])
    bad["close_x100"] = None
    row = {
        "raw_event_id": _FIXTURE_RAW_EVENT_ID,
        "source_id": "tos-cp3-b1a/0.1.0",
        "instrument": _FIXTURE_SOURCE_INSTRUMENT,
        "as_of_ms": 1765153200000,
        "fields": bad,
    }
    with pytest.raises(bootproof_journal.BootProofJournalError, match="NoneType"):
        bootproof_journal.select_bar(
            _b1a_source(tmp_path, [row]), _FIXTURE_RAW_EVENT_ID
        )


def test_the_tool_reproduces_the_committed_fixture(tmp_path: Path) -> None:
    """The other half of the reader proof.

    ``tos/runtime/tests/marketfeed/test_journal_cp3_bootproof_row.py`` feeds the
    committed fixture to the real ``JsonLinesObservationJournal``; this asserts
    the tool still produces exactly that file. The firewall forbids one test
    doing both (``tests/`` may not import ``tos``), so the fixture is the hinge —
    and a fixture nothing regenerates is a fixture that silently goes stale.
    """
    expected = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    bar = bootproof_journal.select_bar(_b1a_source(tmp_path), _FIXTURE_RAW_EVENT_ID)
    produced = bootproof_journal.build_row(
        bar, _FIXTURE_INSTRUMENT, expected["as_of_ms"]
    )
    assert produced == expected
    # Byte-for-byte, including key order and the separators the writer uses.
    bootproof_journal.write_journal(tmp_path / "again.jsonl", produced)
    assert (tmp_path / "again.jsonl").read_bytes() == _FIXTURE.read_bytes()


def test_the_journal_is_replaced_atomically(tmp_path: Path) -> None:
    """Whole-file replacement, not an append: the runtime reader deliberately has
    no trailing-partial-line special case, so a half-written final line refuses
    the whole poll."""
    out = tmp_path / "journal.jsonl"
    bar = bootproof_journal.select_bar(_b1a_source(tmp_path), _FIXTURE_RAW_EVENT_ID)
    bootproof_journal.write_journal(
        out, bootproof_journal.build_row(bar, _FIXTURE_INSTRUMENT, 1)
    )
    bootproof_journal.write_journal(
        out, bootproof_journal.build_row(bar, _FIXTURE_INSTRUMENT, 2)
    )
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["as_of_ms"] == 2
    # No ``.partial`` left behind — a reader that found one would be reading a
    # file this tool never finished writing.
    assert [p.name for p in out.parent.glob("*.partial")] == []


# ---------------------------------------------------------------------------
# The run template
# ---------------------------------------------------------------------------


def test_runner_template_is_tracked_and_executable() -> None:
    assert _RUNNER.is_file(), _RUNNER
    assert os.access(_RUNNER, os.X_OK), f"{_RUNNER} is not executable"


def test_runner_template_parses() -> None:
    result = subprocess.run(
        ["bash", "-n", str(_RUNNER)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_runner_template_passes_shellcheck() -> None:
    """On CI a missing shellcheck is a FAILURE, not a skip, and the file is
    checked ON ITS OWN as well as with the helpers it sources — the two lessons
    ``tests/tools/test_broker_probes_ca.py`` paid for (a gate whose verdict
    depends on how many files you hand it is not a gate)."""
    shellcheck = shutil.which("shellcheck")
    if shellcheck is None:
        if os.environ.get("CI"):
            pytest.fail(
                "shellcheck is missing on CI, where this gate is meant to run; "
                "add it to the workflow rather than letting the check vanish"
            )
        pytest.skip("shellcheck is not installed locally — CI runs this gate")
    for argv in ([_RUNNER], [_RUNNER, _RUNNER_COMMON]):
        result = subprocess.run(
            [shellcheck, "--severity=warning", *(str(f) for f in argv)],
            capture_output=True,
            text=True,
        )
        assert (
            result.returncode == 0
        ), f"{[f.name for f in argv]}: {result.stdout}{result.stderr}"


def test_runner_template_carries_no_instance_defaults() -> None:
    """Every ``TENANT_*`` value is read WITHOUT a non-empty ``:-`` default. The
    designated tenant paths (runbook §7.2-b) live in the runbook, never here: a
    default is how one session's data dir silently becomes the next session's —
    and the plan's whole H2 concern is a session writing to the wrong one."""
    pairs = set(
        re.findall(r"\$\{(TENANT_[A-Z_]+):-([^}]*)\}", _RUNNER.read_text("utf-8"))
    )
    assert {name for name, default in pairs if default not in ("", "0")} == set(), pairs
    assert {name for name, _default in pairs} <= {
        "TENANT_LOG",
        "TENANT_ALLOW_SHARED_CHECKOUT",
    }, pairs
    # The shared helpers stay prefix-free: a TENANT_ name creeping into
    # _common.sh is one runner reading another's environment. (Its own test
    # already pins PCA_/P8_; this is the same property for this caller.)
    helpers = _RUNNER_COMMON.read_text("utf-8")
    assert not re.findall(r"\bTENANT_[A-Z_]+\b", helpers), helpers


def test_runner_template_never_removes_itself() -> None:
    """2026-09-30: a runner that self-deleted after its first run left the review
    unable to say which script had run (#825)."""
    text = _RUNNER.read_text("utf-8")
    destructive = re.search(
        r"(?<![\w-])(rm|unlink|mv|shred|truncate)(?![\w-])|:\s*>[^>]", text
    )
    assert destructive is None, f"the runner runs a destructive command: {destructive}"
    self_references = [
        line for line in text.splitlines() if "$0" in line and "awk" not in line
    ]
    assert len(self_references) == 1, self_references
    assert "SCRIPT_DIR=" in self_references[0], self_references


def test_runner_template_touches_no_crontab() -> None:
    """The first real tenant session is an operator decision after ③ (plan §2.6:
    "cron 등록은 이 계획에 없다"). A template that could install itself would make
    that decision by accident."""
    code = [
        line
        for line in _RUNNER.read_text("utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    assert [line for line in code if "crontab" in line] == []


def test_runner_boots_the_way_the_resident_session_does() -> None:
    """The boot invocation is REUSED, not invented: the one-liner is the resident
    driver's ``CLI`` constant (``~/.config/kis-probes/tos_paper_session.py:38``,
    also runbook §3) and ``PYTHONPATH`` is that driver's own
    ``tos/src:tos/runtime/src`` — the repo root deliberately NOT on it."""
    text = _RUNNER.read_text("utf-8")
    assert (
        'CLI="import sys;from tos_runtime.compose.cli import main;'
        'sys.exit(main(sys.argv[1:]))"' in text
    )
    assert (
        'PYTHONPATH="$REPO/tos/src:$REPO/tos/runtime/src" "$PY" -c "$CLI" run' in text
    )
    for flag in ("--config-dir", "--data-dir", "--custody-root", "--environment-label"):
        assert flag in text, flag


# --- the guards, against a real git checkout -------------------------------


_FRONT_MONTH = "A05611"


def _runner_repo(
    tmp_path: Path, *, detached: bool = True, policy: str | None = None
) -> Path:
    """A throwaway checkout holding the template, the helpers it sources, the
    guard module it hands off to, and a stub front-month lookup."""
    repo = tmp_path / "repo"
    (repo / "tools" / "tos_cp3" / "runners").mkdir(parents=True)
    (repo / "tools" / "broker_probes" / "runners").mkdir(parents=True)
    (repo / "shared" / "instruments").mkdir(parents=True)
    (repo / "config" / "tos_runtime" / "cp3-setup-d-long").mkdir(parents=True)
    (repo / "scripts" / "tos").mkdir(parents=True)

    shutil.copy2(_RUNNER, repo / "tools/tos_cp3/runners/run_tenant_session.sh")
    shutil.copy2(_RUNNER_COMMON, repo / "tools/broker_probes/runners/_common.sh")
    shutil.copy2(
        _REPO_ROOT / "tools/tos_cp3/bootproof_guard.py",
        repo / "tools/tos_cp3/bootproof_guard.py",
    )
    (repo / "tools/tos_cp3/__init__.py").write_text("", encoding="utf-8")
    if policy is not None:
        text = (repo / "tools/tos_cp3/bootproof_guard.py").read_text("utf-8")
        (repo / "tools/tos_cp3/bootproof_guard.py").write_text(
            text.replace(
                f'POLICY_VERSION = "{bootproof_guard.POLICY_VERSION}"',
                f'POLICY_VERSION = "{policy}"',
            ),
            encoding="utf-8",
        )
    (repo / "shared/__init__.py").write_text("", encoding="utf-8")
    (repo / "shared/instruments/__init__.py").write_text("", encoding="utf-8")
    (repo / "shared/instruments/futures.py").write_text(
        "def get_front_month_code(product='kospi200', **_kw):\n"
        f"    return {_FRONT_MONTH!r}\n",
        encoding="utf-8",
    )
    (repo / "scripts/tos/render_paper_config.py").write_text(
        "raise SystemExit('the guard tests never reach the renderer')\n",
        encoding="utf-8",
    )

    def git(*argv: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *argv], check=True, capture_output=True, text=True
        )

    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)], check=True, capture_output=True
    )
    git("config", "user.email", "tenant@example.invalid")
    git("config", "user.name", "tenant")
    git("add", "-A")
    git("commit", "-q", "-m", "tenant runner")
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    git("update-ref", "refs/remotes/origin/main", sha)
    if detached:
        git("checkout", "-q", "--detach", "HEAD")
    return repo


def _run_runner(repo: Path, tmp_path: Path, **overrides: str) -> Any:
    """Run the template with a complete, valid environment unless overridden.

    ``HOME`` is ``tmp_path``, so ``bootproof_guard``'s default scratch root is a
    throwaway one — nothing under the real ``~/.local/state/tos`` is touched.
    ``""`` as an override value UNSETS the variable.
    """
    scratch = tmp_path / ".local" / "state" / "tos" / "scratch" / "bp"
    scratch.mkdir(parents=True, exist_ok=True)
    env_file = tmp_path / ".env.mock"
    env_file.write_text("KIS_FUTURES_ACCOUNT_NO=00000000-03\n", encoding="utf-8")
    custody = tmp_path / "custody"
    custody.mkdir(exist_ok=True)
    journal = _synthetic_journal(tmp_path / "journal.jsonl", instrument=_FRONT_MONTH)

    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "TENANT_LOG": str(tmp_path / "session.log"),
        "TENANT_PYTHON": sys.executable,
        "TENANT_TREE": "cp3-setup-d-long",
        "TENANT_DIRECTION": "LONG",
        "TENANT_RENDER_OUT": str(tmp_path / "render-out"),
        "TENANT_DATA_PARENT": str(scratch / "data"),
        "TENANT_JOURNAL": str(journal),
        "TENANT_STOP_AT": "+10 minutes",
        "TENANT_ENV_FILE": str(env_file),
        "TENANT_CUSTODY_ROOT": str(custody),
        "TENANT_ENVIRONMENT_LABEL": "paper",
    }
    for name, value in overrides.items():
        if value == "":
            env.pop(name, None)
        else:
            env[name] = value
    return subprocess.run(
        ["bash", str(repo / "tools/tos_cp3/runners/run_tenant_session.sh")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )


def test_runner_aborts_on_a_checkout_that_is_not_detached(tmp_path: Path) -> None:
    """#793 — a shared checkout lets a parallel lane move the branch under a
    running session. The guard is wired, not merely named in the header."""
    result = _run_runner(_runner_repo(tmp_path, detached=False), tmp_path)
    assert result.returncode != 0
    assert "not a detached worktree" in result.stdout + result.stderr


def test_runner_aborts_on_a_dirty_checkout(tmp_path: Path) -> None:
    repo = _runner_repo(tmp_path)
    (repo / "untracked.txt").write_text("x", encoding="utf-8")
    result = _run_runner(repo, tmp_path)
    assert result.returncode != 0
    assert "is dirty" in result.stdout + result.stderr


def test_runner_aborts_when_head_is_not_an_ancestor_of_origin_main(
    tmp_path: Path,
) -> None:
    repo = _runner_repo(tmp_path)
    # origin/main stays where _runner_repo left it; the detached HEAD moves one
    # commit ahead of it, which is what a lane running unmerged code looks like.
    (repo / "extra.txt").write_text("x", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "ahead"],
        check=True,
        capture_output=True,
    )
    result = _run_runner(repo, tmp_path)
    assert result.returncode != 0
    assert "not an ancestor of origin/main" in result.stdout + result.stderr


@pytest.mark.parametrize(
    "name",
    [
        "TENANT_PYTHON",
        "TENANT_TREE",
        "TENANT_DIRECTION",
        "TENANT_RENDER_OUT",
        "TENANT_DATA_PARENT",
        "TENANT_JOURNAL",
        "TENANT_STOP_AT",
        "TENANT_ENV_FILE",
        "TENANT_CUSTODY_ROOT",
        "TENANT_ENVIRONMENT_LABEL",
    ],
)
def test_runner_aborts_when_any_instance_value_is_unset(
    tmp_path: Path, name: str
) -> None:
    """Each name separately: "this template ships no instance defaults" is only
    worth the words if removing any one of them stops the run."""
    result = _run_runner(_runner_repo(tmp_path), tmp_path, **{name: ""})
    assert result.returncode != 0
    assert f"required env {name} is unset" in result.stdout + result.stderr


def test_runner_refuses_an_env_file_that_is_not_env_mock(tmp_path: Path) -> None:
    """Mirrors ``render_paper_config.py``'s ENV_FILE_NAME guard, one step
    earlier: refusing here means a real-money credential file cannot even reach
    the renderer, and nothing has been created yet when it fires."""
    other = tmp_path / ".env.real"
    other.write_text("KIS_FUTURES_ACCOUNT_NO=11111111-03\n", encoding="utf-8")
    result = _run_runner(_runner_repo(tmp_path), tmp_path, TENANT_ENV_FILE=str(other))
    assert result.returncode != 0
    assert ".env.mock" in result.stdout + result.stderr


def test_runner_refuses_an_unknown_direction(tmp_path: Path) -> None:
    result = _run_runner(_runner_repo(tmp_path), tmp_path, TENANT_DIRECTION="BOTH")
    assert result.returncode != 0
    assert "TENANT_DIRECTION must be" in result.stdout + result.stderr


def test_runner_refuses_an_unknown_tree(tmp_path: Path) -> None:
    result = _run_runner(_runner_repo(tmp_path), tmp_path, TENANT_TREE="no-such-tree")
    assert result.returncode != 0
    assert "names no config tree" in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("stop_at", "expected"),
    [
        ("not a time at all", "is not a time this shell can parse"),
        ("-10 minutes", "already past"),
        ("+20 hours", "ceiling"),
    ],
)
def test_runner_refuses_a_stop_time_it_cannot_honour(
    tmp_path: Path, stop_at: str, expected: str
) -> None:
    """Three separate failing inputs, because "the stop time is checked" covers
    three different ways to lose a session: an unparseable value, a deadline that
    has already gone by (the session would stop before it started), and a typo
    like "2027" that never ends."""
    result = _run_runner(_runner_repo(tmp_path), tmp_path, TENANT_STOP_AT=stop_at)
    assert result.returncode != 0
    assert expected in result.stdout + result.stderr


def test_runner_refuses_a_guard_module_of_a_different_generation(
    tmp_path: Path,
) -> None:
    """The POLICY_VERSION handshake: a template copied out of another tree drives
    refusals that are not the ones its header describes."""
    repo = _runner_repo(tmp_path, policy="cp3-tenant-bootproof/99")
    result = _run_runner(repo, tmp_path)
    assert result.returncode != 0
    assert "policy version mismatch" in result.stdout + result.stderr


def test_runner_refuses_a_synthetic_journal_outside_the_scratch_root(
    tmp_path: Path,
) -> None:
    """Plan §2.5's H2 input, at the RUN TEMPLATE: data parent
    ``~/.local/state/tos`` plus a boot-proof journal would genesis the designated
    tenant durable set with synthetic data. Nothing is created and nothing is
    rendered — the refusal lands before the data dir exists."""
    designated = tmp_path / ".local" / "state" / "tos" / "cp3-setup-d-long-data"
    result = _run_runner(
        _runner_repo(tmp_path), tmp_path, TENANT_DATA_PARENT=str(designated)
    )
    assert result.returncode != 0
    assert "boot-proof guard refused" in result.stdout + result.stderr
    assert not (designated / _FRONT_MONTH).exists()
    assert not (tmp_path / "render-out").exists()


def test_runner_refuses_a_journal_for_another_contract_month(tmp_path: Path) -> None:
    """The contract month is derived ONCE and given to both the leaf and the
    render (runbook §7.3 5-a). A journal written for last month's code is not an
    error downstream — it is zero observations."""
    other = _synthetic_journal(tmp_path / "other.jsonl", instrument="A05612")
    result = _run_runner(_runner_repo(tmp_path), tmp_path, TENANT_JOURNAL=str(other))
    assert result.returncode != 0
    assert "A05612" in result.stdout + result.stderr


def test_runner_refuses_a_missing_journal(tmp_path: Path) -> None:
    result = _run_runner(
        _runner_repo(tmp_path), tmp_path, TENANT_JOURNAL=str(tmp_path / "nope.jsonl")
    )
    assert result.returncode != 0
    assert "does not exist" in result.stdout + result.stderr
