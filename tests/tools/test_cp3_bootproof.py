"""CP-3 tenant boot-proof journal + run template (plan 2026-10-09 §2.5 / §2.6).

Every clause in :mod:`tools.tos_cp3.bootproof_guard` gets its OWN red proof, and
each is built so that exactly the clause it names is the one that refuses. The
discipline is the repo's repeated one (#838): a guard whose concrete failing
input nobody can write blocks nothing, and a clause that only ever fires behind
another clause is a *masked* clause.

**The first cut of this module failed open and these tests did not catch it.**
It keyed on a MARKER (``cp3-bootproof-synthetic``) and treated every other
journal as a real producer, so the resident render's own journal was waved
through to the designated tenant durable set. The test that pinned that hole —
"a real-producer journal is not subject to the scratch rule" — asserted the bug
as if it were the contract. It is gone; :func:`test_red_h1_an_unmarked_resident_style_journal_cannot_reach_a_designated_dir`
replaces it with the reviewer's measured input.

No test writes anything under the real ``~/.local/state/tos``: every one that
touches a root moves ``HOME`` into ``tmp_path`` first, which also means the
paths under test are the paths production uses — the guard takes no root
override.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import types
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

_RUNNER = _REPO_ROOT / "tools" / "tos_cp3" / "runners" / "run_tenant_session.sh"
_RUNNER_COMMON = _REPO_ROOT / "tools" / "broker_probes" / "runners" / "_common.sh"

#: The committed row ``tos/runtime/tests/marketfeed/test_journal_cp3_bootproof_row.py``
#: feeds to the REAL ``JsonLinesObservationJournal``. The firewall forbids
#: importing that reader from here, so the proof is split and the fixture is the
#: hinge; :func:`test_the_tool_reproduces_the_committed_fixture` is the other half.
_FIXTURE = (
    _REPO_ROOT / "tos" / "runtime" / "tests" / "fixtures" / "cp3-bootproof-row.jsonl"
)

_FIXTURE_RAW_EVENT_ID = "101S6000:1m:20251208T092000+0900"
_FIXTURE_SOURCE_INSTRUMENT = "101S6000"
_FIXTURE_INSTRUMENT = "A05611"

#: A stand-in for ③'s eventual prefix, used only where a test needs the allowlist
#: to be non-empty. Production's own tuple is empty and
#: :func:`test_the_allowlist_is_empty_until_the_real_producer_lands` pins that.
_TEST_ALLOWLIST = ("tos-cp3-third-producer/",)

#: The ``source_id`` values the RESIDENT deployment actually writes — measured
#: from ``~/.config/tos/paper-config/bootproof_journal.jsonl`` (5032 rows,
#: instrument A05610). This is the reviewer's H1 input, and neither carries the
#: synthetic marker: that is precisely why a marker-keyed rule failed open.
_RESIDENT_SOURCE_IDS = ("tos-paper-bootproof-render", "tos-paper-resident-session")

#: MIRRORS ``tos/runtime/src/tos_runtime/marketfeed/journal.py::_REQUIRED_KEYS``.
#: ``tests/`` is outside ``tos/``, so the five names are restated as a literal —
#: the same mirroring note ``tests/tools/test_cp3_produce_fields.py`` carries.
JOURNAL_REQUIRED_KEYS_MIRROR = frozenset(
    {"raw_event_id", "instrument", "as_of_ms", "fields", "source_id"}
)


# ---------------------------------------------------------------------------
# Fixtures
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


def _resident_journal(path: Path, instrument: str = _FIXTURE_INSTRUMENT) -> Path:
    """The reviewer's H1 input: the resident deployment's own source_ids."""
    return _journal(
        path,
        [_row(source_id=sid, instrument=instrument) for sid in _RESIDENT_SOURCE_IDS],
    )


def _allowlisted_journal(path: Path, instrument: str = _FIXTURE_INSTRUMENT) -> Path:
    return _journal(
        path, [_row(source_id=_TEST_ALLOWLIST[0] + "0.1.0", instrument=instrument)]
    )


@pytest.fixture
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    """``HOME`` in ``tmp_path``, with the §7.2-b directory names laid out under it.

    The names are the real ones so the tests read like the runbook; the location
    is throwaway. The guard takes no root override, so moving ``HOME`` is the
    only way in — which means these tests exercise the same lookup production
    does, rather than a test-only parameter.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    tos = tmp_path / ".local" / "state" / "tos"
    scratch = tos / "scratch"
    scratch.mkdir(parents=True)
    designated = tos / "cp3-setup-d-long-data"
    designated.mkdir(parents=True)
    resident = tos / "paper-data"
    resident.mkdir(parents=True)
    return types.SimpleNamespace(
        home=tmp_path,
        tos=tos,
        scratch=scratch,
        designated=designated,
        resident=resident,
    )


def _allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bootproof_guard, "APPROVED_REAL_PRODUCER_PREFIXES", _TEST_ALLOWLIST
    )


# ---------------------------------------------------------------------------
# The rule itself — H1
# ---------------------------------------------------------------------------


def test_the_allowlist_is_empty_until_the_real_producer_lands() -> None:
    """The literal, pinned.

    Every "a real producer may genesis a designated set" test below has to
    monkeypatch this tuple, so without this assertion nothing would say that
    production's own copy is empty — which is the whole fail-closed posture.
    ③'s PR adds its prefix here and changes this test in the same commit.
    """
    assert bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES == ()
    assert str(bootproof_guard.DEFAULT_SCRATCH_ROOT) == "~/.local/state/tos/scratch"
    assert str(bootproof_guard.RESIDENT_DATA_ROOT) == "~/.local/state/tos/paper-data"
    assert bootproof_guard.DESIGNATED_PARENT_GLOBS == (
        "cp3-setup-d-*-data",
        "paper-data",
    )
    assert bootproof_guard.POLICY_VERSION == "cp3-tenant-bootproof/2"


def test_an_empty_allowlist_marks_every_row_unapproved(
    tmp_path: Path, state: types.SimpleNamespace
) -> None:
    """``str.startswith(())`` is False for every string, which is what makes the
    empty allowlist fail closed with no second code path. Pinned here rather
    than left as a stdlib corner the next reader has to know."""
    journal = _journal(
        tmp_path / "j.jsonl",
        [_row(source_id="anything-at-all"), _row(source_id=_TEST_ALLOWLIST[0] + "x")],
    )
    assert bootproof_guard.unapproved_rows(journal) == (1, 2)


def test_red_h1_an_unmarked_resident_style_journal_cannot_reach_a_designated_dir(
    tmp_path: Path, state: types.SimpleNamespace
) -> None:
    """**The reviewer's measured input (HIGH).**

    ``~/.config/tos/paper-config/bootproof_journal.jsonl`` carries ``source_id``
    ``tos-paper-bootproof-render`` / ``tos-paper-resident-session`` — synthetic,
    but with no ``cp3-bootproof-synthetic`` marker anywhere. The first cut of
    this guard printed "ok — real-producer journal" for it and the runner would
    have genesised ``cp3-setup-d-long-data`` from synthetic rows, irreversibly.

    Goes red against a marker-keyed (denylist) implementation; that is the point.
    """
    journal = _resident_journal(tmp_path / "resident-style.jsonl")

    # The property the old rule was fooled by: nothing here says "synthetic".
    assert bootproof_guard.synthetic_rows(journal) == ()
    assert bootproof_guard.unapproved_rows(journal) == (1, 2)

    for data_dir in (state.designated, state.designated / _FIXTURE_INSTRUMENT):
        with pytest.raises(BootProofGuardRefused) as excinfo:
            require_scratch_rule(journal, data_dir)
        assert "not from an approved real producer" in str(excinfo.value)


def test_an_allowlisted_journal_may_genesis_a_designated_dir(
    tmp_path: Path, state: types.SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """③'s path still works once its prefix is added — the inversion is
    fail-closed, not a wall. Without this, a guard that refused everything would
    look just as green."""
    _allowlist(monkeypatch)
    journal = _allowlisted_journal(tmp_path / "third.jsonl")

    assert bootproof_guard.unapproved_rows(journal) == ()
    require_scratch_rule(journal, state.designated / _FIXTURE_INSTRUMENT)


def test_red_h1_the_resident_store_is_refused_even_with_an_allowlisted_journal(
    tmp_path: Path, state: types.SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unconditional clause, isolated: the journal is allowlisted, so the
    scratch branch is not taken at all and only the resident check can fire.

    The resident leaf is live. Its rows are attributed to the resident
    deployment and activation records bind neither direction nor tree (runbook
    §5 ⑤), so tenant rows appended there could never be separated again.
    """
    _allowlist(monkeypatch)
    journal = _allowlisted_journal(tmp_path / "third.jsonl")
    assert bootproof_guard.unapproved_rows(journal) == ()

    for data_dir in (state.resident, state.resident / _FIXTURE_INSTRUMENT):
        with pytest.raises(BootProofGuardRefused) as excinfo:
            require_scratch_rule(journal, data_dir)
        assert "RESIDENT paper durable set" in str(excinfo.value)


def test_red_c_one_unapproved_row_among_approved_ones_is_refused(
    tmp_path: Path, state: types.SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plan §2.5's third red proof, carried across the inversion: **every** row
    is examined, not the first.

    Rows 1-2 are allowlisted and row 3 is not. A first-row-only check clears
    this journal and lets the unapproved rows into a permanent corpus.
    """
    _allowlist(monkeypatch)
    journal = _journal(
        tmp_path / "mixed.jsonl",
        [
            _row(source_id=_TEST_ALLOWLIST[0] + "0.1.0"),
            _row(source_id=_TEST_ALLOWLIST[0] + "0.1.0"),
            _row(source_id="tos-paper-resident-session"),
        ],
    )

    # The property a first-row-only check would have been fooled by.
    assert bootproof_guard.unapproved_rows(journal) == (3,)

    with pytest.raises(BootProofGuardRefused):
        require_scratch_rule(journal, state.designated / _FIXTURE_INSTRUMENT)


# ---------------------------------------------------------------------------
# The scratch branch — one isolated red proof per clause
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("leaf", ["", _FIXTURE_INSTRUMENT])
def test_red_a_designated_data_dir_with_a_synthetic_journal_is_refused(
    tmp_path: Path, state: types.SimpleNamespace, leaf: str
) -> None:
    """Plan §2.5 red proof (a) — the H2 input verbatim, now refused because the
    allowlist is empty rather than because of a marker."""
    data_dir = state.designated / leaf if leaf else state.designated
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(journal, data_dir)
    assert "scratch root" in str(excinfo.value)


def test_red_containment_a_plain_dir_outside_scratch_is_refused(
    tmp_path: Path, state: types.SimpleNamespace
) -> None:
    """Containment, isolated.

    The dir is outside scratch but carries NO durable-set name and is NOT under
    the resident root, so the name clause and the resident clause have nothing
    to say — only containment can refuse it. Without this, containment's only
    red proofs would be inputs the name clause also catches.
    """
    data_dir = state.tos / "somewhere-else" / _FIXTURE_INSTRUMENT
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    assert bootproof_guard._designated_component(data_dir.resolve()) is None
    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(journal, data_dir)
    assert "which is not" in str(excinfo.value)


def test_red_b_a_symlink_inside_scratch_pointing_at_a_designated_dir_is_refused(
    tmp_path: Path, state: types.SimpleNamespace
) -> None:
    """Plan §2.5 red proof (b) — this one fails without ``Path.resolve()``.

    The test asserts the property, not just the outcome: the path handed to the
    guard IS lexically under the scratch root, so a containment check written on
    strings would clear it.
    """
    link = state.scratch / "looks-like-scratch"
    link.symlink_to(state.designated, target_is_directory=True)
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    assert str(link).startswith(str(state.scratch) + os.sep)
    assert link.resolve() == state.designated.resolve()

    with pytest.raises(BootProofGuardRefused):
        require_scratch_rule(journal, link)


def test_red_m1_a_symlinked_scratch_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Review MEDIUM, isolated.**

    ``~/.local/state/tos/scratch`` is a symlink. The data dir here is genuinely
    under the RESOLVED root, is empty, carries no durable-set name and is not
    under the resident root — so every other clause is satisfied and only the
    symlink check can refuse it. Delete that check and this goes green.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    tos = tmp_path / ".local" / "state" / "tos"
    (tos / "real-scratch").mkdir(parents=True)
    (tos / "scratch").symlink_to(tos / "real-scratch", target_is_directory=True)
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(journal, tos / "scratch" / "bp" / _FIXTURE_INSTRUMENT)
    assert "symlinked scratch root" in str(excinfo.value)


def test_red_m1_the_reviewers_symlinked_root_input_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reviewer's own framing of the same finding: the root points at an
    ANCESTOR of the designated sets, so every one of them resolves "under
    scratch".

    Two clauses cover this input — the symlinked root fires first, and the
    durable-set name would catch it anyway. That redundancy is stated rather
    than hidden; the two preceding tests are what prove each clause can fire on
    its own.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    tos = tmp_path / ".local" / "state" / "tos"
    designated = tos / "cp3-setup-d-long-data"
    designated.mkdir(parents=True)
    (tos / "scratch").symlink_to(tos, target_is_directory=True)
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    candidate = tos / "scratch" / "cp3-setup-d-long-data" / _FIXTURE_INSTRUMENT
    assert candidate.resolve() == (designated / _FIXTURE_INSTRUMENT).resolve()
    with pytest.raises(BootProofGuardRefused):
        require_scratch_rule(journal, candidate)


@pytest.mark.parametrize(
    "name", ["cp3-setup-d-long-data", "cp3-setup-d-short-data", "paper-data"]
)
def test_red_m1_a_durable_set_name_under_scratch_is_refused(
    tmp_path: Path, state: types.SimpleNamespace, name: str
) -> None:
    """The durable-set-name clause, isolated.

    The dir is genuinely under a genuinely non-symlinked scratch root and is
    empty, so containment, the symlink check and emptiness all pass. ``paper-data``
    here is NOT under the real resident root either, so the resident clause
    cannot fire — which is why that name is checked in both places rather than
    once: each placement has its own live failing input.
    """
    data_dir = state.scratch / name / _FIXTURE_INSTRUMENT
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(journal, data_dir)
    assert "durable-set parent name" in str(excinfo.value)


def test_a_non_empty_scratch_dir_is_refused(
    tmp_path: Path, state: types.SimpleNamespace
) -> None:
    """Emptiness, isolated: under scratch, no durable-set name, real root."""
    data_dir = state.scratch / "bp" / "data" / _FIXTURE_INSTRUMENT
    data_dir.mkdir(parents=True)
    (data_dir / "evidence.sqlite3").write_text("x", encoding="utf-8")
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(journal, data_dir)
    assert "newly created and empty" in str(excinfo.value)


def test_a_file_where_the_data_dir_should_be_is_refused(
    tmp_path: Path, state: types.SimpleNamespace
) -> None:
    """Same clause's other half — ``iterdir`` would raise instead of refusing."""
    data_dir = state.scratch / "bp"
    data_dir.write_text("not a directory", encoding="utf-8")
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(journal, data_dir)
    assert "not a directory" in str(excinfo.value)


def test_the_scratch_root_itself_is_refused(
    tmp_path: Path, state: types.SimpleNamespace
) -> None:
    """ "Under the scratch root" means strictly under it: the root is the parent
    of the one-off session directories, not a durable set of its own."""
    journal = _synthetic_journal(tmp_path / "journal.jsonl")
    with pytest.raises(BootProofGuardRefused):
        require_scratch_rule(journal, state.scratch)


def test_a_fresh_scratch_dir_is_accepted(
    tmp_path: Path, state: types.SimpleNamespace
) -> None:
    """The green side: absent is fine — the caller creates it right after — and
    so is an existing empty one."""
    journal = _synthetic_journal(tmp_path / "journal.jsonl")
    data_dir = state.scratch / "cp3-bootproof-20261010" / "data" / _FIXTURE_INSTRUMENT

    require_scratch_rule(journal, data_dir)
    data_dir.mkdir(parents=True)
    require_scratch_rule(journal, data_dir)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("{not json}\n", "not valid JSON"),
        ('["a list"]\n', "not a JSON object"),
        ("\n  \n", "holds no rows"),
    ],
)
def test_an_unreadable_journal_is_refused_not_cleared(
    tmp_path: Path, state: types.SimpleNamespace, content: str, expected: str
) -> None:
    """Fail-closed: a line this guard cannot parse is a line whose ``source_id``
    it cannot clear, so "unreadable" must never collapse into "every row is from
    an approved producer"."""
    journal = tmp_path / "journal.jsonl"
    journal.write_text(content, encoding="utf-8")

    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(journal, state.designated)
    assert expected in str(excinfo.value)


def test_a_missing_journal_is_refused(
    tmp_path: Path, state: types.SimpleNamespace
) -> None:
    with pytest.raises(BootProofGuardRefused) as excinfo:
        require_scratch_rule(tmp_path / "nope.jsonl", state.designated)
    assert "does not exist" in str(excinfo.value)


def test_a_journal_for_another_contract_month_is_refused(tmp_path: Path) -> None:
    """Isolated from the data-dir rule on purpose. A mismatch is not an error
    downstream — the runtime reader FILTERS by instrument, so it is zero
    observations and a session that boots cleanly and proves nothing."""
    journal = _synthetic_journal(tmp_path / "journal.jsonl", instrument="A05612")

    bootproof_guard.require_journal_instrument(journal, "A05612")
    with pytest.raises(BootProofGuardRefused) as excinfo:
        bootproof_guard.require_journal_instrument(journal, _FIXTURE_INSTRUMENT)
    assert "A05612" in str(excinfo.value)


def test_the_guard_cli_refuses_and_says_why(
    tmp_path: Path, state: types.SimpleNamespace, capsys: Any
) -> None:
    """The shell template reaches the rule through this entry point, so the exit
    codes and the branch it reports are part of the contract."""
    journal = _synthetic_journal(tmp_path / "journal.jsonl")

    assert (
        bootproof_guard.main(
            [
                "--journal",
                str(journal),
                "--data-dir",
                str(state.scratch / "bp" / _FIXTURE_INSTRUMENT),
                "--instrument",
                _FIXTURE_INSTRUMENT,
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "SCRATCH" in out and SYNTHETIC_SOURCE_PREFIX in out

    assert (
        bootproof_guard.main(
            [
                "--journal",
                str(journal),
                "--data-dir",
                str(state.designated / _FIXTURE_INSTRUMENT),
                "--instrument",
                _FIXTURE_INSTRUMENT,
            ]
        )
        == 1
    )
    assert "REFUSED" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["--scratch-root", "--allow-producer"])
def test_the_cli_offers_no_root_or_allowlist_override(flag: str) -> None:
    """Stated directly, because the absence is the point: a template that could
    be told where "scratch" is, or which producers count, is a guard its caller
    can switch off."""
    with pytest.raises(SystemExit) as excinfo:
        bootproof_guard.main(
            ["--journal", "j", "--data-dir", "d", "--instrument", "A05611", flag, "x"]
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
    market fact.

    ⚠ The marker is PROVENANCE, not the rule — the guard reports it and does not
    branch on it. Keying the rule on it is what failed open (review HIGH).
    """
    bar = bootproof_journal.select_bar(_b1a_source(tmp_path), _FIXTURE_RAW_EVENT_ID)
    row = bootproof_journal.build_row(bar, _FIXTURE_INSTRUMENT, 1791601200000)

    assert row["instrument"] == _FIXTURE_INSTRUMENT
    assert row["source_id"] == (
        f"{SYNTHETIC_SOURCE_PREFIX}:{_FIXTURE_SOURCE_INSTRUMENT}:{_FIXTURE_RAW_EVENT_ID}"
    )
    journal = _journal(tmp_path / "j.jsonl", [row])
    assert bootproof_guard.synthetic_rows(journal) == (1,)
    assert bootproof_guard.unapproved_rows(journal) == (1,)


def test_as_of_ms_is_the_write_time_not_the_bar_label(
    tmp_path: Path, state: types.SimpleNamespace
) -> None:
    """The operator's 2026-10-09 decision for ③, applied here: ``max_age_ms`` 800
    and the kernel's time path measure the SAME quantity, and B1a's own
    ``as_of_ms`` is the bar LABEL — a minimum age of 60,000 ms, 75x the budget.
    A label stamp can never be fresh, at any limit."""
    source = _b1a_source(tmp_path)
    label_as_of = json.loads(source.read_text(encoding="utf-8").splitlines()[0])[
        "as_of_ms"
    ]
    out = state.scratch / "bp" / "journal.jsonl"

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
                str(out),
                "--data-dir",
                str(state.scratch / "bp" / "data" / _FIXTURE_INSTRUMENT),
            ]
        )
        == 0
    )
    after = time.time_ns() // 1_000_000

    written = json.loads(out.read_text(encoding="utf-8"))
    assert before <= written["as_of_ms"] <= after
    assert written["as_of_ms"] != label_as_of
    # 60 s is the bar period, so the label is at least that stale the moment it
    # is written — the number the tenant policy's 800 ms cannot accommodate.
    assert written["as_of_ms"] - label_as_of > 60_000


def test_the_tool_refuses_a_designated_data_dir(
    tmp_path: Path, state: types.SimpleNamespace, capsys: Any
) -> None:
    """The same refusal as the run template, reached from the OTHER entry point —
    that is why it lives in one module (plan §2.5: "두 진입점 어느 쪽에서도
    막히게")."""
    source = _b1a_source(tmp_path)
    out = state.scratch / "bp" / "journal.jsonl"

    rc = bootproof_journal.main(
        [
            "--fields",
            str(source),
            "--raw-event-id",
            _FIXTURE_RAW_EVENT_ID,
            "--instrument",
            _FIXTURE_INSTRUMENT,
            "--out",
            str(out),
            "--data-dir",
            str(state.designated / _FIXTURE_INSTRUMENT),
        ]
    )
    assert rc == 1
    assert "REFUSED" in capsys.readouterr().err
    assert not out.exists()


def test_red_l1_the_tool_refuses_an_out_path_outside_scratch(
    tmp_path: Path, state: types.SimpleNamespace, capsys: Any
) -> None:
    """**Review LOW.** ``--out`` was unconstrained, and this tool replaces its
    output file WHOLE and atomically — so

        --out ~/.config/tos/paper-config/bootproof_journal.jsonl

    would have silently replaced the live resident journal (the resident
    session's only observation source, 5032 rows) with one synthetic row.

    The data dir here is a perfectly good scratch dir, so only the output clause
    can refuse this.
    """
    source = _b1a_source(tmp_path)
    live = state.home / ".config" / "tos" / "paper-config" / "bootproof_journal.jsonl"
    live.parent.mkdir(parents=True)
    live.write_text('{"the": "live resident journal"}\n', encoding="utf-8")

    rc = bootproof_journal.main(
        [
            "--fields",
            str(source),
            "--raw-event-id",
            _FIXTURE_RAW_EVENT_ID,
            "--instrument",
            _FIXTURE_INSTRUMENT,
            "--out",
            str(live),
            "--data-dir",
            str(state.scratch / "bp" / "data" / _FIXTURE_INSTRUMENT),
        ]
    )
    assert rc == 1
    assert "REFUSED" in capsys.readouterr().err
    assert live.read_text(encoding="utf-8") == '{"the": "live resident journal"}\n'


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
    assert [p.name for p in out.parent.glob("*.partial")] == []


# ---------------------------------------------------------------------------
# The run template — source properties
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
    default is how one session's data dir silently becomes the next session's."""
    pairs = set(
        re.findall(r"\$\{(TENANT_[A-Z_]+):-([^}]*)\}", _RUNNER.read_text("utf-8"))
    )
    assert {name for name, default in pairs if default not in ("", "0")} == set(), pairs
    assert {name for name, _default in pairs} <= {
        "TENANT_LOG",
        "TENANT_ALLOW_SHARED_CHECKOUT",
    }, pairs
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


def test_runner_pins_the_guard_generation_it_was_written_for() -> None:
    """A template copied out of another tree drives refusals that are not the
    ones its header describes. The inversion bumped the guard to ``/2``; without
    this the template could still be pinned to ``/1``."""
    assert (
        f"EXPECT_POLICY_VERSION={bootproof_guard.POLICY_VERSION}"
        in _RUNNER.read_text("utf-8")
    )


def test_runner_forwards_signals_to_the_child() -> None:
    """Source-level companion to the live test below: the traps exist and all
    three route through the one stop path."""
    text = _RUNNER.read_text("utf-8")
    for sig in ("TERM", "INT", "HUP"):
        assert f"trap 'on_signal {sig}" in text, sig
    assert "stop_run()" in text


# ---------------------------------------------------------------------------
# The run template — against a real git checkout
# ---------------------------------------------------------------------------


_FRONT_MONTH = _FIXTURE_INSTRUMENT

#: Written by the stub `run` so a test can find the child process.
_RUN_PIDFILE_ENV = "STUB_RUN_PIDFILE"
#: Read by the stub renderer to decide the rendered tree's `environment`.
_TREE_ENV = "STUB_TREE_ENVIRONMENT"


def _runner_repo(
    tmp_path: Path,
    *,
    detached: bool = True,
    policy: str | None = None,
    bootable: bool = False,
) -> Path:
    """A throwaway checkout holding the template, the helpers it sources, the
    guard module it hands off to, and a stub front-month lookup.

    ``bootable=True`` additionally installs a stub renderer and a stub
    ``tos_runtime.compose.cli`` that runs until it is killed, so the tests that
    need the template to reach step 8b and step 9 can get there without the real
    renderer, a custody root or a kernel.
    """
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
        guard = repo / "tools/tos_cp3/bootproof_guard.py"
        guard.write_text(
            guard.read_text("utf-8").replace(
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

    if bootable:
        (repo / "scripts/tos/render_paper_config.py").write_text(
            "import os, sys\n"
            "from pathlib import Path\n"
            "argv = sys.argv[1:]\n"
            "out = Path(argv[argv.index('--out') + 1])\n"
            "out.mkdir(parents=True, exist_ok=True)\n"
            f"env = os.environ.get({_TREE_ENV!r}, 'paper')\n"
            "if env != '__omit__':\n"
            "    (out / 'critical_input_policy.yaml').write_text(\n"
            "        'environment: \"%s\"\\n' % env, encoding='utf-8')\n"
            "print('stub render ok')\n",
            encoding="utf-8",
        )
        cli_dir = repo / "tos/runtime/src/tos_runtime/compose"
        cli_dir.mkdir(parents=True)
        (repo / "tos/runtime/src/tos_runtime/__init__.py").write_text(
            "", encoding="utf-8"
        )
        (cli_dir / "__init__.py").write_text("", encoding="utf-8")
        (cli_dir / "cli.py").write_text(
            "import os, time\n"
            "from pathlib import Path\n"
            "def main(argv):\n"
            f"    Path(os.environ[{_RUN_PIDFILE_ENV!r}]).write_text(str(os.getpid()))\n"
            "    while True:\n"
            "        time.sleep(0.2)\n",
            encoding="utf-8",
        )
    else:
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


def _runner_env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    """A complete, valid environment for the template.

    ``HOME`` is ``tmp_path``, so the guard's default scratch root is a throwaway
    one — nothing under the real ``~/.local/state/tos`` is touched. ``""`` as an
    override value UNSETS the variable.
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
    return env


def _run_runner(repo: Path, tmp_path: Path, **overrides: str) -> Any:
    return subprocess.run(
        ["bash", str(repo / "tools/tos_cp3/runners/run_tenant_session.sh")],
        capture_output=True,
        text=True,
        env=_runner_env(tmp_path, **overrides),
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
        # TENANT_LOG included: without it every log() line is silently dropped,
        # which is the "the attempt vanished" shape these runners exist to
        # prevent (#825 round-3 F1).
        "TENANT_LOG",
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
    has already gone by, and a typo like "2027" that never ends."""
    result = _run_runner(_runner_repo(tmp_path), tmp_path, TENANT_STOP_AT=stop_at)
    assert result.returncode != 0
    assert expected in result.stdout + result.stderr


def test_runner_refuses_a_guard_module_of_a_different_generation(
    tmp_path: Path,
) -> None:
    repo = _runner_repo(tmp_path, policy="cp3-tenant-bootproof/99")
    result = _run_runner(repo, tmp_path)
    assert result.returncode != 0
    assert "policy version mismatch" in result.stdout + result.stderr


def test_red_h1_runner_refuses_the_reviewers_resident_journal_input(
    tmp_path: Path,
) -> None:
    """**The reviewer's HIGH input, end to end at the run template.**

    An unmarked resident-style journal plus
    ``TENANT_DATA_PARENT=<designated cp3-setup-d-long-data>``. The old guard
    accepted this and the runner would have genesised the designated store from
    synthetic rows. Nothing is created and nothing is rendered now.
    """
    designated = tmp_path / ".local" / "state" / "tos" / "cp3-setup-d-long-data"
    journal = _resident_journal(tmp_path / "resident-style.jsonl", _FRONT_MONTH)
    result = _run_runner(
        _runner_repo(tmp_path),
        tmp_path,
        TENANT_DATA_PARENT=str(designated),
        TENANT_JOURNAL=str(journal),
    )
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "boot-proof guard refused" in output
    assert "not from an approved real producer" in output
    assert not (designated / _FRONT_MONTH).exists()
    assert not (tmp_path / "render-out").exists()


def test_red_h1_runner_refuses_the_resident_durable_set(tmp_path: Path) -> None:
    """The same journal pointed at the LIVE resident parent — the second half of
    the reviewer's input. Refused by the unconditional clause."""
    resident = tmp_path / ".local" / "state" / "tos" / "paper-data"
    resident.mkdir(parents=True)
    journal = _resident_journal(tmp_path / "resident-style.jsonl", _FRONT_MONTH)
    result = _run_runner(
        _runner_repo(tmp_path),
        tmp_path,
        TENANT_DATA_PARENT=str(resident),
        TENANT_JOURNAL=str(journal),
    )
    assert result.returncode != 0
    assert "RESIDENT paper durable set" in result.stdout + result.stderr
    assert not (resident / _FRONT_MONTH).exists()


def test_runner_refuses_a_synthetic_journal_outside_the_scratch_root(
    tmp_path: Path,
) -> None:
    """Plan §2.5's H2 input at the run template: data parent
    ``~/.local/state/tos`` plus a boot-proof journal."""
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


# --- the bootable fixture: label check and signal forwarding ---------------


@pytest.mark.parametrize(
    ("tree_env", "expected"),
    [
        ("non-live-test", "the rendered tree declares environment 'non-live-test'"),
        ("__omit__", "cannot read environment"),
    ],
)
def test_red_l3_runner_refuses_a_label_the_rendered_tree_does_not_declare(
    tmp_path: Path, tree_env: str, expected: str
) -> None:
    """**Review LOW.** ``--environment-label`` is free-form and the critical-input
    loader does not compare its own ``environment`` against it, so a mismatch
    boots quietly and every capsule this session issues carries the wrong
    environment inside its covered content — wrong evidence, not missing
    evidence, in an append-only store.

    Two failing inputs: the tree declares something else, and the tree declares
    nothing this can read.
    """
    repo = _runner_repo(tmp_path, bootable=True)
    env = _runner_env(tmp_path)
    env[_TREE_ENV] = tree_env
    env[_RUN_PIDFILE_ENV] = str(tmp_path / "run.pid")
    # A short window and a hard timeout: when this guard is REMOVED the runner
    # does not fail, it BOOTS — so without these the mutation experiment that
    # proves the guard load-bearing would hang the suite for the whole session
    # window instead of failing. (Measured: it did, before these were added.)
    env["TENANT_STOP_AT"] = "+1 minutes"
    try:
        result = subprocess.run(
            ["bash", str(repo / "tools/tos_cp3/runners/run_tenant_session.sh")],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
            timeout=120,
        )
    finally:
        pidfile = tmp_path / "run.pid"
        if pidfile.is_file():
            with contextlib.suppress(OSError, ValueError):
                os.kill(int(pidfile.read_text().strip()), signal.SIGKILL)
    assert result.returncode != 0
    assert expected in result.stdout + result.stderr
    # The boot never started.
    assert not (tmp_path / "run.pid").exists()


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_red_m2_a_signal_to_the_runner_stops_the_child(tmp_path: Path) -> None:
    """**Review MEDIUM.** Without a trap, SIGTERM to the runner leaves ``run``
    ORPHANED with no deadline — writing into a durable set nobody is watching,
    which is the opposite of what a one-off boot proof is for. The resident
    driver forwards signals the same way
    (``~/.config/kis-probes/tos_paper_session.py:264, 439-441, 525-529``).

    A stub ``run`` stands in for the kernel; the assertion is about the child's
    lifetime, not about what it does.
    """
    repo = _runner_repo(tmp_path, bootable=True)
    pidfile = tmp_path / "run.pid"
    env = _runner_env(tmp_path, TENANT_STOP_AT="+2 hours")
    env[_RUN_PIDFILE_ENV] = str(pidfile)

    runner = subprocess.Popen(
        ["bash", str(repo / "tools/tos_cp3/runners/run_tenant_session.sh")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    child_pid = -1
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not pidfile.is_file():
            assert runner.poll() is None, runner.communicate()[0]
            time.sleep(0.2)
        assert pidfile.is_file(), (
            "the stub `run` never started; runner output:\n"
            + (tmp_path / "session.log").read_text("utf-8", errors="replace")[-3000:]
        )
        child_pid = int(pidfile.read_text().strip())
        assert _pid_alive(child_pid)

        runner.send_signal(signal.SIGTERM)
        out = runner.communicate(timeout=60)[0]

        gone = time.monotonic() + 30
        while time.monotonic() < gone and _pid_alive(child_pid):
            time.sleep(0.2)
        assert not _pid_alive(child_pid), (
            f"the stub `run` (pid {child_pid}) survived a SIGTERM to the runner — "
            "it is orphaned with no deadline"
        )
        assert runner.returncode == 143, out
        assert "SIGNAL TERM received by the runner" in out
    finally:
        if runner.poll() is None:
            runner.kill()
        if child_pid > 0 and _pid_alive(child_pid):
            os.kill(child_pid, signal.SIGKILL)
