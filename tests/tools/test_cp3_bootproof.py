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
_TEST_ALLOWLIST = ("tos-cp3-third-producer",)

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
        path, [_row(source_id=_TEST_ALLOWLIST[0] + "/0.1.0", instrument=instrument)]
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


def test_the_allowlist_holds_exactly_the_one_approved_producer() -> None:
    """The literal, pinned.

    Every "a real producer may genesis a designated set" test below
    monkeypatches this tuple, so without this assertion nothing would say what
    production's own copy actually is. It held ``()`` until ③'s PR-2, which
    added ``tos-cp3-live`` — the real-time field producer in
    :mod:`tools.tos_cp3.live_producer` — and nothing else. A second entry
    appearing here is a second producer approved to create a permanent corpus,
    which is a decision, so it changes this test too.
    """
    assert bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES == ("tos-cp3-live",)
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
    """``any()`` over no prefixes is False, which is what makes the empty
    allowlist fail closed with no second code path."""
    journal = _journal(
        tmp_path / "j.jsonl",
        [
            _row(source_id="anything-at-all"),
            _row(source_id=_TEST_ALLOWLIST[0] + "/0.1.0"),
        ],
    )
    assert bootproof_guard.unapproved_rows(journal) == (1, 2)


#: The allowlist entry the boundary tests match against. Deliberately WITHOUT a
#: trailing slash — the matcher appends the delimiter, and an entry that carries
#: one is refused outright (see the shape tests).
_BOUNDARY_PREFIX = "tos-cp3-live"


@pytest.mark.parametrize(
    ("source_id", "approved"),
    [
        # Accepted: the name itself, and the name + delimiter + anything. B1a's
        # own source_id already has this shape ("tos-cp3-b1a/0.1.0").
        ("tos-cp3-live", True),
        ("tos-cp3-live/1.0", True),
        ("tos-cp3-live/1.0/extra", True),
        # Refused: a bare `startswith` would approve every one of these.
        ("tos-cp3-live-EVIL", False),
        ("tos-cp3-liveX", False),
        ("tos-cp3-live.evil/1.0", False),
        ("tos-cp3-liv", False),
        ("evil/tos-cp3-live", False),
    ],
)
def test_red_the_allowlist_requires_a_delimiter(
    tmp_path: Path,
    state: types.SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    approved: bool,
) -> None:
    """**Re-review LOW.** A producer name is a NAMESPACE, not a string prefix.

    With a bare ``startswith``, an entry of ``tos-cp3-live`` approves
    ``tos-cp3-live-EVIL`` — anyone who can pick a ``source_id`` picks one that
    starts with an approved name and gets a permanent corpus. The separator is
    what makes the boundary real, so the matcher requires ``== p`` or
    ``p + "/"``.

    Red proofs are the ``False`` rows: every one of them passes a bare
    ``startswith``.
    """
    monkeypatch.setattr(
        bootproof_guard, "APPROVED_REAL_PRODUCER_PREFIXES", (_BOUNDARY_PREFIX,)
    )
    journal = _journal(tmp_path / "j.jsonl", [_row(source_id=source_id)])
    designated = state.designated / _FIXTURE_INSTRUMENT

    assert bootproof_guard.unapproved_rows(journal) == (() if approved else (1,))
    if approved:
        require_scratch_rule(journal, designated)
    else:
        with pytest.raises(BootProofGuardRefused):
            require_scratch_rule(journal, designated)


@pytest.mark.parametrize(
    ("bad_entry", "expected"),
    [("", "EMPTY entry"), ("tos-cp3-live/", "ends with '/'")],
)
def test_red_a_malformed_allowlist_entry_is_refused_at_call_time(
    tmp_path: Path,
    state: types.SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    bad_entry: str,
    expected: str,
) -> None:
    """An entry that cannot mean what it looks like is a refusal, not a silent
    no-match.

    ``""`` reads as "approve everything" and, under the delimiter rule, would in
    fact match almost nothing — permissive-looking, restrictive-behaving, and
    nobody finds out until a real genesis is refused for a reason the list does
    not state. A trailing ``/`` matches nothing at all, because the matcher
    appends the delimiter itself.
    """
    monkeypatch.setattr(
        bootproof_guard, "APPROVED_REAL_PRODUCER_PREFIXES", (bad_entry,)
    )
    journal = _journal(tmp_path / "j.jsonl", [_row(source_id="anything")])

    with pytest.raises(BootProofGuardRefused, match=expected):
        bootproof_guard.unapproved_rows(journal)
    with pytest.raises(BootProofGuardRefused, match=expected):
        require_scratch_rule(journal, state.designated / _FIXTURE_INSTRUMENT)


@pytest.mark.parametrize("bad_entry", ['""', '"tos-cp3-live/"'])
def test_red_a_malformed_allowlist_entry_fails_at_import(
    tmp_path: Path, bad_entry: str
) -> None:
    """The same shape check at IMPORT, which is where ③'s PR-2 was standing
    when it added ``tos-cp3-live``.

    A module that refuses to import is a louder failure than one that refuses at
    call time, and this is the one that fires on a bad commit rather than on a
    bad run. Exercised against a copy of the real source with the literal
    swapped, so it cannot drift from the module under test.
    """
    import importlib.util

    assignment = "APPROVED_REAL_PRODUCER_PREFIXES: tuple[str, ...] = "
    source = (_REPO_ROOT / "tools/tos_cp3/bootproof_guard.py").read_text("utf-8")
    # Replaced by LINE, not by the literal's text: the shipped tuple changes
    # whenever a producer is approved (③'s PR-2 added ``tos-cp3-live``), and a
    # test keyed on the old spelling would quietly stop patching anything.
    patched = "\n".join(
        f"{assignment}({bad_entry},)" if line.startswith(assignment) else line
        for line in source.splitlines()
    )
    assert patched != source, "the literal this test patches has moved"
    module_path = tmp_path / "patched_guard.py"
    module_path.write_text(patched, encoding="utf-8")

    spec = importlib.util.spec_from_file_location("patched_guard", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with pytest.raises(Exception, match="APPROVED_REAL_PRODUCER_PREFIXES"):
        spec.loader.exec_module(module)


def test_the_real_module_imports_with_its_own_literal() -> None:
    """The green side of the import check: the shipped tuple is well-formed, so
    the gate above is not simply refusing everything."""
    assert (
        bootproof_guard._validated_prefixes(
            bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES
        )
        == bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES
    )
    assert bootproof_guard._validated_prefixes(()) == ()
    assert bootproof_guard._validated_prefixes(("a", "b/c")) == ("a", "b/c")


def test_the_allowlist_attests_intent_not_provenance() -> None:
    """Said out loud, in the module, because the distinction is load-bearing:
    nothing authenticates ``source_id``. The list records which producer names
    the operator has decided may create a permanent corpus — a producer that
    lies about its name is outside what this guard can see."""
    assert "intent, not provenance" in bootproof_guard.__doc__
    assert "self-declared" in bootproof_guard.__doc__


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
            _row(source_id=_TEST_ALLOWLIST[0] + "/0.1.0"),
            _row(source_id=_TEST_ALLOWLIST[0] + "/0.1.0"),
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
    # Asserted as two facts rather than one long line: the launch now also goes
    # through `timeout` (re-review LOW), and the PYTHONPATH is still exactly the
    # driver's — the repo root deliberately NOT on it.
    assert 'PYTHONPATH="$REPO/tos/src:$REPO/tos/runtime/src"' in text
    assert '"$PY" -c "$CLI" run' in text
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


def test_runner_arms_the_traps_before_launching_either_child() -> None:
    """**Re-review LOW, and plan §3.5's M1.** A signal arriving between a
    ``… &`` and the ``trap`` statements would kill the runner with the default
    disposition and leave that child orphaned — the exact failure the traps
    exist to prevent, in the one moment nothing is watching for it.

    Both launches, and the EXIT trap as well as the signal ones: the producer
    starts before the guard, the render and the label check, so every ``die``
    between them has to stop it. ``die`` exits, and EXIT is the one handler an
    exit cannot skip.
    """
    text = _RUNNER.read_text("utf-8")
    lines = text.splitlines()
    first_trap = next(i for i, line in enumerate(lines) if line.startswith("trap "))
    for launch in ("PRODUCER_PID=$!", "RUN_PID=$!"):
        at = next(i for i, line in enumerate(lines) if line.startswith(launch))
        assert first_trap < at, (launch, first_trap, at)
    assert "trap 'on_exit' EXIT" in text
    # And the reason arming early is safe, stated as a property of the code:
    # both pids exist, empty, before any trap can read them.
    assert 'RUN_PID=""' in text
    assert 'PRODUCER_PID=""' in text
    assert lines.index('RUN_PID=""') < first_trap
    assert lines.index('PRODUCER_PID=""') < first_trap


def test_runner_gives_the_producer_a_ceiling_and_the_guards_order() -> None:
    """Source-level companion to the live tests: the producer runs under its
    own ``timeout``, and the boot order is producer → wait → guard → render →
    boot (plan §3.5)."""
    text = _RUNNER.read_text("utf-8")
    assert "PRODUCER_CEILING_S=$((RUN_S + PRODUCER_SIGKILL_AFTER_S))" in text
    assert (
        'timeout --kill-after="${PRODUCER_SIGKILL_AFTER_S}s" "${PRODUCER_CEILING_S}s"'
        in text
    )
    order = [
        "PRODUCER_PID=$!",
        "BOOT_SNAPSHOT=",
        "GUARD_OUT=",
        "RENDER_LOG=",
        "RUN_PID=$!",
    ]
    positions = [text.index(marker) for marker in order]
    assert positions == sorted(positions), list(zip(order, positions))


def test_the_kill_escalation_targets_the_process_group() -> None:
    """**#892 re-review L2, source level.** The pid the runner holds is
    ``timeout``'s, and GNU timeout runs the command in a new process group with
    itself as leader. A KILL to ``timeout`` alone is forwarded to nothing, so
    the real worker — a python process holding a store, or a REAL quotation
    session — would outlive its own supervisor."""
    helpers = _RUNNER_COMMON.read_text("utf-8")
    assert 'kill -KILL -- "-$_pid"' in helpers
    assert 'kill -TERM -- "-$_pid"' in helpers
    # the runner no longer carries its own copy of the escalation
    runner = _RUNNER.read_text("utf-8")
    assert "kill -KILL" not in runner
    assert "stop_supervised" in runner


def test_runner_gives_the_child_a_ceiling_of_its_own() -> None:
    """Source-level companion: the child runs under ``timeout``, whose duration
    is the stop window plus the same grace the runner's own stop path allows."""
    text = _RUNNER.read_text("utf-8")
    assert "CHILD_CEILING_S=$((RUN_S + SIGKILL_AFTER_S))" in text
    assert 'timeout --kill-after="${SIGKILL_AFTER_S}s" "${CHILD_CEILING_S}s"' in text


# ---------------------------------------------------------------------------
# The run template — against a real git checkout
# ---------------------------------------------------------------------------


_FRONT_MONTH = _FIXTURE_INSTRUMENT

#: Written by the stub `run` so a test can find the child process.
_RUN_PIDFILE_ENV = "STUB_RUN_PIDFILE"
#: Written by the stub `run`: its own environment, as JSON. The credential
#: separation claim (plan §3.4) is about what the RUNTIME holds, so it is
#: measured there rather than inferred from what the runner was given.
_RUN_ENVFILE_ENV = "STUB_RUN_ENVFILE"
#: Read by the stub renderer to decide the rendered tree's `environment`.
_TREE_ENV = "STUB_TREE_ENVIRONMENT"
#: Written by the stub producer so a test can find it and prove it was stopped.
_PRODUCER_PIDFILE_ENV = "STUB_PRODUCER_PIDFILE"
#: Written by the stub producer: its own environment, AFTER it has read the
#: query keys from its config's env_file the way the real one does. The
#: credential-separation claim is a comparison — these keys here, not there —
#: and a test that only looked at the runtime would pass with no keys anywhere.
_PRODUCER_ENVFILE_ENV = "STUB_PRODUCER_ENVFILE"
#: Comma-separated ``source_id`` values the stub producer writes into the
#: journal (default: one approved real-producer row).
_PRODUCER_SOURCE_IDS_ENV = "STUB_PRODUCER_SOURCE_IDS"
#: The instrument the stub producer labels its rows with (default: the
#: ``--instrument`` the runner gave it).
_PRODUCER_INSTRUMENT_ENV = "STUB_PRODUCER_INSTRUMENT"
#: "0" to write no journal at all, and exit — a producer that refused at boot.
_PRODUCER_ROWS_ENV = "STUB_PRODUCER_ROWS"
#: How the stub leaves, right after writing its journal and summary. A decimal
#: string is that exit code: "1" is every real refusal
#: (``LiveProducerRefused`` — the two §3.5 give-ups, the late boot, a seed or
#: journal refusal) and "0" is a producer that ENDED with the session
#: (``run_session`` walked past the last boundary and ``main`` returned 0).
#: ``"killed"`` SIGKILLs itself, which is rc 137 and no clean teardown.
#: Unset: stay alive until the runner stops it.
_PRODUCER_EXIT_ENV = "STUB_PRODUCER_EXIT_AFTER_WRITE"
#: The path the ``1+1`` mode watches before publishing its second row — the
#: rendered tree's own file, so "after the render, before the boot" is a fact
#: about the pipeline rather than a bet on how long a stub takes.
_PRODUCER_SECOND_ROW_WHEN_ENV = "STUB_PRODUCER_SECOND_ROW_WHEN"

#: What the producer's own ``source_id`` looks like, as the allowlist approves
#: it (``tools/tos_cp3/bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES``).
_APPROVED_SOURCE_ID = f"{bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES[0]}/0.1.0"

#: Stand-ins for the two real futures query keys. Distinctive strings so a
#: test can grep a whole captured stream for them — which is what the
#: xtrace-leak proofs do.
_PRODUCER_FAKE_KEY = "PSfake-app-key-0ac1dd"
_PRODUCER_FAKE_SECRET = "fake-app-secret-77b31e"


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
    (repo / "tools" / "tos_cp3" / "live_producer").mkdir(parents=True)
    (repo / "tools" / "broker_probes" / "runners").mkdir(parents=True)
    (repo / "shared" / "instruments").mkdir(parents=True)
    (repo / "config" / "tos_runtime" / "cp3-setup-d-long").mkdir(parents=True)
    (repo / "scripts" / "tos").mkdir(parents=True)

    # The stub ③. It stands in for tools/tos_cp3/live_producer/producer.py: it
    # writes the journal rows its environment asks for and then runs until it is
    # stopped, which is every property the runner's boot order depends on (the
    # real producer's own refusals are exercised in
    # tests/tools/test_cp3_live_producer.py).
    (repo / "tools/tos_cp3/live_producer/__init__.py").write_text("", encoding="utf-8")
    (repo / "tools/tos_cp3/live_producer/producer.py").write_text(
        "import json, os, signal, sys, time\n"
        "from pathlib import Path\n"
        "argv = sys.argv[1:]\n"
        "def opt(name):\n"
        "    return argv[argv.index(name) + 1]\n"
        "journal = Path(opt('--journal'))\n"
        "session = Path(opt('--session-dir'))\n"
        "session.mkdir(parents=True, exist_ok=True)\n"
        # The real producer reads the two query keys ITSELF, from the env_file
        # its own config names (live_producer/config.py::read_query_credentials).
        # The stub does the same one-line version of it, so a test can show the
        # keys reaching THIS process and not the runtime.
        "config = Path(opt('--config')).read_text(encoding='utf-8')\n"
        "env_file = [l.split(':', 1)[1].strip() for l in config.splitlines()\n"
        "            if l.startswith('env_file:')]\n"
        "if env_file and Path(env_file[0]).is_file():\n"
        "    for line in Path(env_file[0]).read_text(encoding='utf-8').splitlines():\n"
        "        if '=' in line:\n"
        "            key, _, value = line.partition('=')\n"
        "            os.environ[key.strip()] = value.strip()\n"
        f"envfile = os.environ.get({_PRODUCER_ENVFILE_ENV!r})\n"
        "if envfile:\n"
        "    Path(envfile).write_text(json.dumps(dict(os.environ)))\n"
        f"instrument = os.environ.get({_PRODUCER_INSTRUMENT_ENV!r}) or opt('--instrument')\n"
        f"source_ids = os.environ.get({_PRODUCER_SOURCE_IDS_ENV!r}, {_APPROVED_SOURCE_ID!r})\n"
        f"mode = os.environ.get({_PRODUCER_ROWS_ENV!r}, '1')\n"
        f"pidfile = os.environ.get({_PRODUCER_PIDFILE_ENV!r})\n"
        "if pidfile:\n"
        "    Path(pidfile).write_text(str(os.getpid()))\n"
        "if mode == '0':\n"
        "    print('stub producer: refused, writing nothing')\n"
        "    raise SystemExit(1)\n"
        "journal.parent.mkdir(parents=True, exist_ok=True)\n"
        "ids = source_ids.split(',')\n"
        "def publish(count):\n"
        "    # Whole-file replacement, like the real writer (sinks.py).\n"
        "    journal.write_text(''.join(json.dumps({\n"
        "        'raw_event_id': '%s:1m:2026101909%02d00+0900' % (instrument, index),\n"
        "        'source_id': ids[min(index, len(ids) - 1)],\n"
        "        'instrument': instrument,\n"
        "        'as_of_ms': 1791601200000 + index,\n"
        "        'fields': {'close_x100': 57950},\n"
        "    }) + '\\n' for index in range(count)))\n"
        "if mode == 'never':\n"
        "    pass  # alive, publishing nothing — the wait runs its bound\n"
        "elif mode == '1+1':\n"
        "    # One bar now, a second the moment the render lands: the window\n"
        "    # between the first-row wait and the boot, where a real producer\n"
        "    # keeps publishing. Keyed to the render rather than to a sleep so\n"
        "    # the test is not a race against stub timings.\n"
        "    publish(1)\n"
        f"    watch = Path(os.environ[{_PRODUCER_SECOND_ROW_WHEN_ENV!r}])\n"
        "    deadline = time.monotonic() + 60\n"
        "    while not watch.exists() and time.monotonic() < deadline:\n"
        "        time.sleep(0.02)\n"
        "    publish(2)\n"
        "else:\n"
        "    publish(max(len(ids), 1))\n"
        # The real `finish()` runs in `main`'s `finally`, so EVERY end writes
        # this — the halting ones too. That is why the runner's verdict cannot
        # be read off the summary (step 12b).
        "(session / 'producer-summary.json').write_text(\n"
        "    json.dumps({'stage': 'finish', 'counters': {'published': 1}}) + '\\n')\n"
        f"leave_with = os.environ.get({_PRODUCER_EXIT_ENV!r})\n"
        "if leave_with == 'killed':\n"
        "    print('stub producer: killing itself after writing')\n"
        "    os.kill(os.getpid(), signal.SIGKILL)\n"
        "if leave_with is not None:\n"
        "    print('stub producer: leaving with %s after writing' % leave_with)\n"
        "    raise SystemExit(int(leave_with))\n"
        "while True:\n"
        "    time.sleep(0.2)\n",
        encoding="utf-8",
    )

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
            "import json, os, time\n"
            "from pathlib import Path\n"
            "def main(argv):\n"
            f"    envfile = os.environ.get({_RUN_ENVFILE_ENV!r})\n"
            "    if envfile:\n"
            "        Path(envfile).write_text(json.dumps(dict(os.environ)))\n"
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
    # The producer's own credential file and the config that names it — the
    # arrangement plan §3.4 describes: the keys live in a file the PRODUCER's
    # config points at, never in the runner's environment.
    real_env = tmp_path / ".env.real"
    real_env.write_text(
        f"KIS_FUTURES_APP_KEY={_PRODUCER_FAKE_KEY}\n"
        f"KIS_FUTURES_APP_SECRET={_PRODUCER_FAKE_SECRET}\n",
        encoding="utf-8",
    )
    producer_config = tmp_path / "cp3-live-producer.yaml"
    producer_config.write_text(f"env_file: {real_env}\n", encoding="utf-8")

    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "TENANT_LOG": str(tmp_path / "session.log"),
        "TENANT_PYTHON": sys.executable,
        "TENANT_TREE": "cp3-setup-d-long",
        "TENANT_DIRECTION": "LONG",
        "TENANT_RENDER_OUT": str(tmp_path / "render-out"),
        "TENANT_DATA_PARENT": str(scratch / "data"),
        # The producer CREATES the journal (plan §3.5 boot order), so this path
        # does not exist yet — a pre-written one is what the real producer
        # refuses to start against (sinks.refuse_if_journal_exists).
        "TENANT_JOURNAL": str(tmp_path / "journal.jsonl"),
        "TENANT_STOP_AT": "+10 minutes",
        "TENANT_ENV_FILE": str(env_file),
        "TENANT_CUSTODY_ROOT": str(custody),
        "TENANT_ENVIRONMENT_LABEL": "paper",
        "TENANT_PRODUCER_CONFIG": str(producer_config),
        "TENANT_PRODUCER_SESSION_DIR": str(tmp_path / "producer-session"),
        _PRODUCER_PIDFILE_ENV: str(tmp_path / "producer.pid"),
    }
    for name, value in overrides.items():
        if value == "":
            env.pop(name, None)
        else:
            env[name] = value
    return env


def _producer_outlived_the_runner(tmp_path: Path) -> bool:
    """Is the stub producer still alive after the runner returned?

    The question every refusal below now has to answer (plan §3.5, v2 re-review
    M1): the producer starts BEFORE the guard, so a ``die`` that does not stop
    it leaves it calling the real quotation API all day. Polled rather than
    sampled once — SIGTERM, delivery and exit are not instantaneous — and
    whatever the answer, a survivor is killed so the suite leaks nothing.
    """
    pidfile = tmp_path / "producer.pid"
    if not pidfile.is_file():
        return False
    pid = int(pidfile.read_text().strip())
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and _pid_alive(pid):
        time.sleep(0.2)
    alive = _pid_alive(pid)
    if alive:
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGKILL)
    return alive


def _run_runner(repo: Path, tmp_path: Path, **overrides: str) -> Any:
    result = subprocess.run(
        ["bash", str(repo / "tools/tos_cp3/runners/run_tenant_session.sh")],
        capture_output=True,
        text=True,
        env=_runner_env(tmp_path, **overrides),
        cwd=str(tmp_path),
        timeout=180,
    )
    result.producer_outlived_the_runner = _producer_outlived_the_runner(tmp_path)
    return result


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
        "TENANT_PRODUCER_CONFIG",
        "TENANT_PRODUCER_SESSION_DIR",
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


def test_red_h1_the_runner_refuses_the_reviewers_resident_journal_rows(
    tmp_path: Path,
) -> None:
    """**The reviewer's HIGH input, end to end at the run template.**

    Unmarked resident-style ``source_id`` values plus
    ``TENANT_DATA_PARENT=<designated cp3-setup-d-long-data>``. The old guard
    accepted this and the runner would have genesised the designated store from
    synthetic rows.

    Since PR-3 the producer WRITES the journal, so the refusal arrives one step
    earlier — at the first-row wait, which asks the guard's own
    ``unapproved_rows`` rather than a second opinion. The guard still owns the
    rule and still refuses the same input directly
    (:func:`test_red_h1_an_unmarked_resident_style_journal_cannot_reach_a_designated_dir`);
    what changed is only which gate the runner reaches first.
    """
    designated = tmp_path / ".local" / "state" / "tos" / "cp3-setup-d-long-data"
    result = _run_runner(
        _runner_repo(tmp_path),
        tmp_path,
        TENANT_DATA_PARENT=str(designated),
        **{_PRODUCER_SOURCE_IDS_ENV: ",".join(_RESIDENT_SOURCE_IDS)},
    )
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "not an approved real producer" in output
    assert not (designated / _FRONT_MONTH).exists()
    assert not (tmp_path / "render-out").exists()
    assert not result.producer_outlived_the_runner


def test_red_h1_runner_refuses_the_resident_durable_set(tmp_path: Path) -> None:
    """The LIVE resident parent, with an APPROVED journal — the clause that
    holds unconditionally, and the only way to reach it now that an unapproved
    row is refused before the guard runs at all."""
    resident = tmp_path / ".local" / "state" / "tos" / "paper-data"
    resident.mkdir(parents=True)
    result = _run_runner(
        _runner_repo(tmp_path), tmp_path, TENANT_DATA_PARENT=str(resident)
    )
    assert result.returncode != 0
    assert "RESIDENT paper durable set" in result.stdout + result.stderr
    assert not (resident / _FRONT_MONTH).exists()
    assert not result.producer_outlived_the_runner


def test_an_approved_producer_row_opens_the_designated_tenant_set(
    tmp_path: Path,
) -> None:
    """The other half of the allowlist, and what ③ exists to unlock.

    Until PR-2 added ``tos-cp3-live`` the list was empty and EVERY boot outside
    scratch was refused; now the producer's own rows open the designated
    tenant set — the first real genesis. The run gets past the guard and dies
    at the stub renderer, which is as far as this fixture goes.

    ⚠ Which clauses the runner can still reach is now narrower than the
    guard's own set: the first-row wait refuses an unapproved journal before
    the guard sees it, so the scratch containment clause (rule 3) is reachable
    from ``tools/tos_cp3/bootproof_journal.py``, the other entry point, and
    from the direct tests above — not from here. Rules 1 and 2 are what this
    template exercises.
    """
    designated = tmp_path / ".local" / "state" / "tos" / "cp3-setup-d-long-data"
    result = _run_runner(
        _runner_repo(tmp_path), tmp_path, TENANT_DATA_PARENT=str(designated)
    )
    output = result.stdout + result.stderr
    assert "boot-proof guard refused" not in output
    assert (designated / _FRONT_MONTH).is_dir()
    # as far as the non-bootable fixture goes: the stub renderer refuses
    assert "render refused" in output
    assert not result.producer_outlived_the_runner


def test_runner_refuses_a_journal_for_another_contract_month(tmp_path: Path) -> None:
    """The contract month is derived ONCE and given to the leaf, the render and
    the producer (runbook §7.3 5-a). A journal written for last month's code is
    not an error downstream — it is zero observations."""
    result = _run_runner(
        _runner_repo(tmp_path),
        tmp_path,
        **{_PRODUCER_INSTRUMENT_ENV: "A05612"},
    )
    assert result.returncode != 0
    assert "A05612" in result.stdout + result.stderr
    assert not result.producer_outlived_the_runner


def test_runner_aborts_at_once_when_the_producer_writes_no_row(
    tmp_path: Path,
) -> None:
    """**Plan §3.5's bounded wait.** A producer that refused at boot (a seed
    that cannot fill ``vol_window``, an env pin mismatch, an existing session
    directory) writes nothing and exits.

    The session must not then sit out the whole ceiling: the wait watches the
    producer's own liveness and gives up as soon as it is gone. Timed here, so
    "at once" is a measurement rather than a hope — the ceiling it must beat is
    ``FIRST_LINE_TIMEOUT_S`` (600 s).
    """
    started = time.monotonic()
    result = _run_runner(_runner_repo(tmp_path), tmp_path, **{_PRODUCER_ROWS_ENV: "0"})
    elapsed = time.monotonic() - started
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "producer never produced a usable first row" in output
    assert "exited before writing a usable journal row" in output
    assert elapsed < 120, elapsed
    assert not (tmp_path / "render-out").exists()


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
        # BOTH children (PR-3): the producer is the one holding a real
        # quotation session, so a signal that stops only the runtime leaves
        # the expensive half running.
        assert not _producer_outlived_the_runner(tmp_path)
    finally:
        if runner.poll() is None:
            runner.kill()
        if child_pid > 0 and _pid_alive(child_pid):
            os.kill(child_pid, signal.SIGKILL)


def _start_bootable_runner(
    tmp_path: Path, pidfile: Path, *, stop_at: str
) -> tuple[Any, int]:
    """Start the template against the stubs and return ``(runner, child pid)``."""
    repo = _runner_repo(tmp_path, bootable=True)
    env = _runner_env(tmp_path, TENANT_STOP_AT=stop_at)
    env[_RUN_PIDFILE_ENV] = str(pidfile)
    runner = subprocess.Popen(
        ["bash", str(repo / "tools/tos_cp3/runners/run_tenant_session.sh")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and not pidfile.is_file():
        assert runner.poll() is None, runner.communicate()[0]
        time.sleep(0.2)
    assert pidfile.is_file(), (
        "the stub `run` never started; session log:\n"
        + (tmp_path / "session.log").read_text("utf-8", errors="replace")[-3000:]
    )
    return runner, int(pidfile.read_text().strip())


def test_red_a_sigkilled_runner_still_leaves_the_child_a_deadline(
    tmp_path: Path,
) -> None:
    """**Re-review LOW.** The traps only cover signals the runner lives to see.

    SIGKILL delivers nothing to a handler, so with traps alone a ``kill -9`` on
    the runner (or the host dying under it) leaves ``run`` orphaned with no
    deadline at all, writing into a durable set nobody is watching. The child
    therefore runs under ``timeout``, a separate supervising process with its
    own alarm.

    This test is **slow on purpose** (~2.5 min): the ceiling is the stop window
    plus ``SIGKILL_AFTER_S`` = 120 s, and that 120 s is real — it exists so the
    external alarm never pre-empts a graceful stop already under way. Faking it
    would prove nothing, so the test waits for the actual deadline.
    """
    pidfile = tmp_path / "run.pid"
    stop_window_s = 15
    runner, child_pid = _start_bootable_runner(
        tmp_path, pidfile, stop_at=f"+{stop_window_s} seconds"
    )
    ceiling_s = stop_window_s + 120
    try:
        assert _pid_alive(child_pid)
        runner.kill()
        runner.wait(timeout=30)
        assert runner.returncode == -signal.SIGKILL

        # The orphan condition really is reached: nothing stopped the child when
        # the runner died. Without this the test could pass on a child that had
        # already exited for some other reason.
        time.sleep(2)
        assert _pid_alive(child_pid), (
            "the child was already gone right after the runner was SIGKILLed, so "
            "this test is not exercising the external ceiling"
        )

        gone_by = time.monotonic() + ceiling_s + 60
        while time.monotonic() < gone_by and _pid_alive(child_pid):
            time.sleep(1)
        assert not _pid_alive(child_pid), (
            f"the stub `run` (pid {child_pid}) outlived its {ceiling_s}s ceiling after "
            "the runner was SIGKILLed — it is an orphan with no deadline"
        )
    finally:
        if runner.poll() is None:
            runner.kill()
        if _pid_alive(child_pid):
            os.kill(child_pid, signal.SIGKILL)


# ---------------------------------------------------------------------------
# PR-3: credential separation, the boot order, and the stop path
# ---------------------------------------------------------------------------


def test_red_the_runner_refuses_a_real_query_key_in_its_own_environment(
    tmp_path: Path,
) -> None:
    """**Plan §3.4.** The concrete input: a shell that exported
    ``KIS_FUTURES_APP_KEY`` before calling the template — the natural thing to
    do when the producer is the thing that needs it.

    Every child inherits this environment, so that key would reach the RUNTIME
    too, silently, because nothing downstream looks for it. The producer reads
    the real keys itself from the file its own config names; the runner never
    carries them. Nothing is launched and nothing is rendered.
    """
    result = _run_runner(
        _runner_repo(tmp_path), tmp_path, KIS_FUTURES_APP_KEY="PS-not-a-real-key"
    )
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "KIS_FUTURES_APP_KEY is set in this shell" in output
    # and the value itself is never echoed back into the log
    assert "PS-not-a-real-key" not in output
    assert not (tmp_path / "producer.pid").exists()
    assert not (tmp_path / "render-out").exists()


def test_red_the_same_refusal_for_the_secret(tmp_path: Path) -> None:
    """The second key, separately: a guard that only names the first one lets
    the pair through whenever the secret is the one that was exported."""
    result = _run_runner(
        _runner_repo(tmp_path), tmp_path, KIS_FUTURES_APP_SECRET="not-a-real-secret"
    )
    assert result.returncode != 0
    assert "KIS_FUTURES_APP_SECRET is set in this shell" in result.stdout + (
        result.stderr
    )
    assert "not-a-real-secret" not in result.stdout + result.stderr


def test_a_die_after_the_producer_starts_does_not_leave_it_running(
    tmp_path: Path,
) -> None:
    """**Plan §3.5, v2 re-review M1 — the EXIT trap's red proof.**

    #892 armed its traps after the render, which was enough while nothing ran
    before the boot. The producer now starts BEFORE the guard, the render and
    the label check, so a refusal in any of them used to leave it running —
    calling the REAL quotation API all day, with the runner gone and nobody
    watching.

    The refusal used here is the label check, the LAST one before the boot, so
    the whole span between the launch and the boot is covered by one case.
    """
    repo = _runner_repo(tmp_path, bootable=True)
    result = _run_runner(
        repo,
        tmp_path,
        TENANT_STOP_AT="+2 minutes",
        **{_TREE_ENV: "non-live-test", _RUN_PIDFILE_ENV: str(tmp_path / "run.pid")},
    )
    assert result.returncode != 0
    assert "the rendered tree declares environment 'non-live-test'" in (
        result.stdout + result.stderr
    )
    # the producer really did start (otherwise this proves nothing)...
    assert (tmp_path / "producer.pid").is_file()
    # ...and the refusal stopped it
    assert not result.producer_outlived_the_runner
    # the boot never happened
    assert not (tmp_path / "run.pid").exists()


def test_the_boot_order_is_producer_then_first_row_then_guard_then_boot(
    tmp_path: Path,
) -> None:
    """**Plan §3.5 end to end**, in one short session.

    What this pins, in the order the log must carry it: the producer starts
    first and CREATES the journal (the #892 guard refuses an empty one); the
    session waits for its first approved row and records how many rows are
    there at boot as ``consumed_stale_at_boot``; the snapshot file the §3.6
    extractor reads names those ids; the RUNTIME's environment holds neither
    real query key (plan §3.4); and the producer is stopped when the session
    ends rather than left behind.
    """
    repo = _runner_repo(tmp_path, bootable=True)
    envfile = tmp_path / "runtime-env.json"
    result = _run_runner(
        repo,
        tmp_path,
        TENANT_STOP_AT="+15 seconds",
        **{
            _RUN_PIDFILE_ENV: str(tmp_path / "run.pid"),
            _RUN_ENVFILE_ENV: str(envfile),
        },
    )
    output = result.stdout + result.stderr

    # ① the producer, before anything else, and it is what wrote the journal
    journal = tmp_path / "journal.jsonl"
    assert journal.is_file()
    rows = [json.loads(line) for line in journal.read_text("utf-8").splitlines()]
    assert [row["source_id"] for row in rows] == [_APPROVED_SOURCE_ID]
    # ② the bounded wait, and what it counted
    assert "first real row seen · consumed_stale_at_boot=1" in output
    snapshot = json.loads(
        (tmp_path / "producer-session" / "boot-journal-snapshot.json").read_text(
            "utf-8"
        )
    )
    assert snapshot["consumed_stale_at_boot"] == 1
    assert snapshot["pre_boot_raw_event_ids"] == [rows[0]["raw_event_id"]]
    # ③ guard → render → boot, in that order, after the wait
    for earlier, later in zip(
        ["=== PRODUCER", "first real row seen", "=== RENDER", "=== BOOT"],
        ["first real row seen", "=== RENDER", "=== BOOT", "=== END run"],
    ):
        assert output.index(earlier) < output.index(later), (earlier, later)
    # the runtime's own environment carries neither real key (plan §3.4)
    runtime_env = json.loads(envfile.read_text("utf-8"))
    assert "KIS_FUTURES_APP_KEY" not in runtime_env
    assert "KIS_FUTURES_APP_SECRET" not in runtime_env
    # and the producer is stopped with the session, not left behind
    assert "=== END producer" in output
    assert not result.producer_outlived_the_runner


@pytest.mark.parametrize(
    ("exit_code", "expected_rc"),
    [
        # Every real refusal: `LiveProducerRefused` -> `main` returns 1. That
        # is the two §3.5 give-ups (a `produce_error` run and, since PR #904's
        # review, a run of minutes in which NO poll came back), a boot already
        # past the session close, and the seed/journal/lock refusals.
        pytest.param("1", "1", id="refused-rc1"),
        # Killed outright: no clean teardown, no summary, rc 137. Here so the
        # clause cannot be narrowed from "non-zero" to "equals 1".
        pytest.param("killed", "137", id="sigkilled-rc137"),
    ],
)
def test_a_producer_that_stops_mid_session_is_reported_as_an_abort(
    tmp_path: Path, exit_code: str, expected_rc: str
) -> None:
    """**Plan §3.5's last sentence: 「멈춘 생산자는 러너가 ABORT 로 보고한다」.**

    The producer halts after writing. From that minute the journal stops
    growing and every remaining pass reads a frozen one — a session that looks
    clean and measured nothing.

    The runtime is NOT killed for it: truncating a durable set loses the
    evidence the session exists to leave. The report is the exit code, and it
    is its own (5), because "the boot failed" and "the boot was fine and the
    feed behind it stopped" are different findings.

    ⚠ The stub writes its ``stage: finish`` summary on BOTH shapes below,
    because the real ``finish()`` runs in ``main``'s ``finally`` and so does
    the same. That is the whole reason the runner's verdict is the exit code
    and not anything in the summary (PR #904 review round 1 item A). The
    companion is
    :func:`test_a_producer_that_ends_with_the_session_is_not_an_abort`, the
    input both of these must NOT also match.
    """
    repo = _runner_repo(tmp_path, bootable=True)
    result = _run_runner(
        repo,
        tmp_path,
        TENANT_STOP_AT="+15 seconds",
        **{
            _PRODUCER_EXIT_ENV: exit_code,
            _RUN_PIDFILE_ENV: str(tmp_path / "run.pid"),
        },
    )
    output = result.stdout + result.stderr
    # the boot itself was fine and ran to its stop time — this is not a refusal
    assert "=== BOOT" in output
    assert "=== END run rc=143" in output  # SIGTERM from our own stop path
    assert f"producer end: rc={expected_rc} (self-stopped=1" in output
    # ...and the session is still not reported as clean
    assert result.returncode == 5, output[-2000:]
    assert "ABORT: the producer halted in the session" in output


def test_nothing_the_session_creates_is_readable_by_another_user(
    tmp_path: Path,
) -> None:
    """**0600 inside 0700, for every path this template brings into being.**

    Measured on the 2026-10-15 LONG genesis session: the four tenant stores
    and the session artifacts were ``0644`` inside ``0700`` directories. The
    runtime and the renderer pass no mode to their own ``mkdir``/sqlite calls
    (runbook §7.2-a 「왜 umask 인가」), so the modes are the inherited umask's —
    and the template only wrapped its three ``mkdir``s, which narrowed the
    directories and left every file inside them wide. Decision records carry
    the account number in plaintext, and a 0700 parent is traversal
    protection, not file protection.

    The caller's umask is forced PERMISSIVE here (022, the host default the
    09-27/28 corpus was born under was 002), so this fails the moment the
    template's own ``umask 077`` is removed — the directories alone would
    still pass, which is exactly the half-fix being closed.
    """
    repo = _runner_repo(tmp_path, bootable=True)
    runner = repo / "tools/tos_cp3/runners/run_tenant_session.sh"
    result = subprocess.run(
        ["bash", "-c", 'umask 022; exec bash "$1"', "_", str(runner)],
        capture_output=True,
        text=True,
        env=_runner_env(
            tmp_path,
            TENANT_STOP_AT="+10 seconds",
            **{
                _PRODUCER_EXIT_ENV: "0",
                _RUN_PIDFILE_ENV: str(tmp_path / "run.pid"),
            },
        ),
        cwd=str(tmp_path),
        timeout=180,
    )
    output = result.stdout + result.stderr
    assert "=== BOOT" in output, output[-2000:]
    _producer_outlived_the_runner(tmp_path)

    producer_session = tmp_path / "producer-session"
    data_leaf = tmp_path / ".local/state/tos/scratch/bp/data" / _FRONT_MONTH
    directories = [producer_session, data_leaf, tmp_path / "render-out"]
    files = [
        tmp_path / "session.log",  # the operator's own log
        tmp_path / "journal.jsonl",  # the fifteen fields
        producer_session / "boot-journal-snapshot.json",
        producer_session / "first-row-wait.log",
        producer_session / "producer-summary.json",
        tmp_path / "render-out/critical_input_policy.yaml",
    ]
    modes = {
        str(path): oct(path.stat().st_mode & 0o777)
        for path in (*directories, *files)
        if path.exists()
    }
    assert len(modes) == len(directories) + len(files), (modes, output[-2000:])
    assert all(
        mode == oct(0o700) for path, mode in modes.items() if Path(path).is_dir()
    ), modes
    assert all(
        mode == oct(0o600) for path, mode in modes.items() if Path(path).is_file()
    ), modes


@pytest.mark.parametrize("which", ["TENANT_PRODUCER_SESSION_DIR", "TENANT_DATA_PARENT"])
def test_red_a_session_path_that_is_a_symlink_is_refused(
    tmp_path: Path, which: str
) -> None:
    """**PR #904 review round 1 item B — the repair must not reach outside.**

    Step 12c narrows modes on the data leaf and the producer session dir, and
    ``chmod`` FOLLOWS a symlink: the 0700 would land on whatever the link
    points at. Refused at step 6b instead, before any child exists — by stop
    time the stores have already been written through the link, so a late
    refusal is worth much less than an early one.

    Concrete input: the named path IS a symlink to a directory outside the
    session. The refusal must fire for either of the two trees, so neither can
    be dropped from the guard's argument list.
    """
    repo = _runner_repo(tmp_path)
    outside = tmp_path / "somewhere-else"
    outside.mkdir()
    scratch = tmp_path / ".local/state/tos/scratch/bp"
    scratch.mkdir(parents=True, exist_ok=True)
    linked = scratch / "linked"
    linked.symlink_to(outside, target_is_directory=True)

    result = _run_runner(repo, tmp_path, **{which: str(linked)})

    output = result.stdout + result.stderr
    assert "is a symlink" in output, output[-2000:]
    assert "a session path is not the path it names" in output
    assert result.returncode == 3, output[-2000:]
    assert not result.producer_outlived_the_runner


def test_red_a_session_path_under_a_symlinked_ancestor_is_refused(
    tmp_path: Path,
) -> None:
    """**The same hole one level up — the clause a leaf-only check would miss.**

    Concrete input: the leaf itself does not exist yet (it never does at step
    6b — the guard requires a fresh one), and an ANCESTOR of it is a symlink.
    ``find`` would descend it and ``chmod`` would follow it, so the resolved
    path, not just the final component, has to equal the path given.
    """
    repo = _runner_repo(tmp_path)
    real = tmp_path / ".local/state/tos/scratch/bp/real"
    real.mkdir(parents=True)
    scratch = tmp_path / ".local/state/tos/scratch/bp"
    (scratch / "via").symlink_to(real, target_is_directory=True)

    result = _run_runner(
        repo, tmp_path, TENANT_DATA_PARENT=str(scratch / "via" / "data")
    )

    output = result.stdout + result.stderr
    assert "a session path is not the path it names" in output, output[-2000:]
    assert result.returncode == 3, output[-2000:]


def test_the_runner_runs_no_mode_repair_sweep_after_the_stop(tmp_path: Path) -> None:
    """**Codex re-review MEDIUM at ``ccf1f0d0``: the repair is REFUSED.**

    A post-stop ``chmod`` sweep cannot be made race-free in this script. ``-P``
    and ``-links 1`` close the shapes a test can build up front, but they are
    checks made before the ``chmod`` that acts on their result: an ancestor
    swapped after step 6b redirects the walk, and an entry replaced or given a
    second name between ``find``'s test and the syscall is chmodded through the
    name ``find`` approved. The disposition was to drop the sweep, not to keep
    narrowing it.

    So this pins the ABSENCE, which is the only way an absence stays: a future
    reader who re-adds a sweep makes this red. Modes now come from one
    mechanism with no window — the process-wide ``umask 077``
    (:func:`test_nothing_the_session_creates_is_readable_by_another_user` is
    what proves it covers everything this session creates).
    """
    text = _RUNNER.read_text("utf-8")
    assert "repair_modes" not in text
    # CODE only — step 12c's comment quotes the command it refuses to run, and
    # a check that cannot tell prose from an instruction would be satisfied by
    # deleting the explanation.
    code = "\n".join(
        line
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    # From step 12b to the end — the window the sweep lived in. Anchored on a
    # variable that occurs once, not on `stop_producer`, whose first occurrence
    # is its definition back in step 7. The `chmod` beside step 9's data-parent
    # `mkdir` is BEFORE this window and predates this PR.
    after_stop = code[code.index("PRODUCER_ENDED_THE_SESSION=0") :]
    assert "chmod" not in after_stop, after_stop[:1500]
    assert "find " not in after_stop, after_stop[:1500]
    # and the refusal is recorded where the sweep used to be, so it is not
    # merely missing
    assert "there is NO mode repair here, deliberately" in text


def test_session_paths_with_spaces_still_work(tmp_path: Path) -> None:
    """**Item B's last requirement: quoting survives the hardening.**

    The step-6b guard takes the four session paths as arguments, and an
    unquoted expansion would split each of these into two words — a refusal on
    a path that is perfectly fine. The mode assertions below come from
    ``umask 077`` plus the ``(umask 077; mkdir)`` subshells, not from any
    repair step (there is none — see
    :func:`test_the_runner_runs_no_mode_repair_sweep_after_the_stop`).
    """
    repo = _runner_repo(tmp_path, bootable=True)
    scratch = tmp_path / ".local/state/tos/scratch/bp"
    scratch.mkdir(parents=True, exist_ok=True)
    result = _run_runner(
        repo,
        tmp_path,
        TENANT_STOP_AT="+10 seconds",
        TENANT_DATA_PARENT=str(scratch / "a data dir"),
        TENANT_PRODUCER_SESSION_DIR=str(tmp_path / "a producer session"),
        TENANT_RENDER_OUT=str(tmp_path / "a render out"),
        **{_RUN_PIDFILE_ENV: str(tmp_path / "run.pid")},
    )
    output = result.stdout + result.stderr
    assert "session paths are literal" in output, output[-2000:]
    assert "=== BOOT" in output, output[-2000:]
    assert result.returncode == 143, output[-2000:]
    _producer_outlived_the_runner(tmp_path)

    leaf = scratch / "a data dir" / _FRONT_MONTH
    assert oct(leaf.stat().st_mode & 0o777) == oct(0o700)
    assert oct((tmp_path / "a producer session").stat().st_mode & 0o777) == oct(0o700)
    assert oct(
        (tmp_path / "a producer session/producer-summary.json").stat().st_mode & 0o777
    ) == oct(0o600)


def test_a_producer_that_ends_with_the_session_is_not_an_abort(
    tmp_path: Path,
) -> None:
    """**The 2026-10-15 false ABORT: every full-day session exited 5.**

    The producer ends BY DESIGN once the session's last bar is published:
    ``run_session`` walks boundaries to ``window.end_boundary(target)`` — one
    minute past the 15:45 close — and returns, and ``main`` returns 0. The
    runner's stop time is necessarily later than that (15:50 on the LONG
    genesis session), so the producer is ALWAYS gone by the time step 12 looks.
    Asking only "was it still alive?" therefore reported the clean shape as the
    defect: measured 2026-10-15 15:50:02, ``producer rc=0, run rc=0`` → exit 5.

    The stub here reproduces exactly that: it leaves with 0 well before
    ``TENANT_STOP_AT``. Nothing about this session is unclean, so the runner
    must hand back the runtime's own code.
    """
    repo = _runner_repo(tmp_path, bootable=True)
    result = _run_runner(
        repo,
        tmp_path,
        TENANT_STOP_AT="+15 seconds",
        **{
            _PRODUCER_EXIT_ENV: "0",
            _RUN_PIDFILE_ENV: str(tmp_path / "run.pid"),
        },
    )
    output = result.stdout + result.stderr
    assert "=== BOOT" in output
    assert "=== END producer rc=0" in output
    # it WAS gone before the stop — the old condition's whole test — and that
    # is now recorded without being a verdict
    assert "producer end: rc=0 (self-stopped=1" in output
    assert "ended-the-session=1" in output
    assert "ABORT" not in output, output[-2000:]
    assert result.returncode == 143, output[-2000:]  # the runtime's own code


# ---------------------------------------------------------------------------
# The stop helper, and the waiter, exercised directly
# ---------------------------------------------------------------------------


def test_red_stop_supervised_reaps_the_worker_behind_its_supervisor(
    tmp_path: Path,
) -> None:
    """**#892 re-review L2 — the group kill's red proof.**

    The pid a caller holds is ``timeout``'s. GNU timeout runs the command in a
    NEW process group with itself as leader, forwards a TERM, and forwards
    nothing at all when it is itself KILLed. So a worker that ignores SIGTERM
    — in production: a python process mid-``os.replace``, or holding a REAL
    quotation session — survives its own supervisor unless the escalation goes
    to the GROUP.

    The grace is two seconds here so the proof is cheap, and the supervisor's
    OWN ``--kill-after`` is five minutes so it cannot be the thing that cleans
    up inside the test window — otherwise this passes either way, which is
    what the first cut of it did (measured: the worker died at ``timeout``'s
    2 s kill-after, and the escalation never ran).
    """
    marker = tmp_path / "worker.pid"
    script = tmp_path / "ignore-term.py"
    script.write_text(
        "import os, signal, time\n"
        "from pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"Path({str(marker)!r}).write_text(str(os.getpid()))\n"
        "while True:\n"
        "    time.sleep(0.2)\n",
        encoding="utf-8",
    )
    driver = tmp_path / "drive.sh"
    driver.write_text(
        "set -u\n" f". {_RUNNER_COMMON}\n" 'set_log_file ""\n'
        # Output to a FILE, not to this script's stdout: when the escalation
        # fails to reach the group the worker is orphaned, and an orphan
        # holding the captured pipe makes `subprocess.run` block forever on
        # EOF — the mutation experiment would then HANG instead of failing,
        # which is the shape this suite has paid for before (the §7.2-c label
        # test's own "measured: it did, before these were added").
        f"timeout --kill-after=300s 600s {sys.executable} {script} "
        f">{tmp_path / 'worker.out'} 2>&1 &\n"
        "PID=$!\n"
        "while [ ! -s %s ]; do sleep 0.1; done\n" % marker
        + 'stop_supervised "$PID" 2 worker\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", str(driver)], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stdout + result.stderr
    worker_pid = int(marker.read_text().strip())
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and _pid_alive(worker_pid):
        time.sleep(0.2)
    try:
        assert not _pid_alive(worker_pid), (
            f"the worker (pid {worker_pid}) outlived the SIGKILL its supervisor "
            "received — the escalation did not reach the process group"
        )
    finally:
        if _pid_alive(worker_pid):
            os.kill(worker_pid, signal.SIGKILL)
    assert "SIGKILL to the process group" in result.stdout


def test_stop_supervised_returns_at_once_for_a_child_that_already_exited(
    tmp_path: Path,
) -> None:
    """A producer that reached its own session end is already gone.

    The stop path must not TERM a pid that is not there and then sit out its
    whole grace — at the end of a trading day that is the difference between
    "stopped" and "the runner hung". Measured, not asserted from the code:
    the call returns in well under the grace it was given.
    """
    driver = tmp_path / "already-gone.sh"
    driver.write_text(
        "set -u\n"
        f". {_RUNNER_COMMON}\n"
        'set_log_file ""\n'
        "bash -c 'exit 0' &\n"
        "PID=$!\n"
        'wait "$PID"\n'
        'stop_supervised "$PID" 30 worker\n'
        "echo returned\n",
        encoding="utf-8",
    )
    started = time.monotonic()
    result = subprocess.run(
        ["bash", str(driver)], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "returned" in result.stdout
    assert "STOP SIGTERM" not in result.stdout
    assert time.monotonic() - started < 10


def _extract_waiter(tmp_path: Path) -> Path:
    """The shipped first-row waiter, lifted out of the template verbatim.

    The template runs it as a heredoc, so this is the only way to exercise it
    with a small timeout — and lifting it means the tests below run the code
    that ships, not a copy of it.
    """
    lines = _RUNNER.read_text("utf-8").splitlines()
    # The waiter is the one heredoc launched in the BACKGROUND (Claude lane
    # MEDIUM M2) — step 13's evidence summary is the foreground one, so the
    # trailing `&` is what tells them apart.
    body_start = next(i for i, line in enumerate(lines) if line.endswith("<<'PY' &"))
    end = next(i for i in range(body_start + 1, len(lines)) if lines[i] == "PY")
    path = tmp_path / "waiter.py"
    path.write_text("\n".join(lines[body_start + 1 : end]) + "\n", encoding="utf-8")
    return path


def _run_waiter(
    tmp_path: Path, journal: Path, timeout_s: str, pid: int
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(_extract_waiter(tmp_path)),
            str(journal),
            timeout_s,
            str(pid),
            str(tmp_path / "snapshot.json"),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)},
    )


def test_red_the_waiter_gives_up_at_its_bound(tmp_path: Path) -> None:
    """**Plan §3.5's bounded wait, with the bound exercised.**

    A producer that is alive and simply never publishes (its seed walked a
    month of empty responses, or the market is shut) must not hold the session
    forever: the template's ``FIRST_LINE_TIMEOUT_S`` is the ceiling and this is
    the same code under a two-second one. Without the deadline branch this
    test hangs instead of failing, which is the defect.
    """
    alive = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        result = _run_waiter(tmp_path, tmp_path / "never.jsonl", "2", alive.pid)
    finally:
        alive.kill()
    assert result.returncode != 0
    assert "within 2s" in result.stderr
    assert not (tmp_path / "snapshot.json").exists()


def test_red_the_waiter_stops_as_soon_as_the_producer_is_gone(
    tmp_path: Path,
) -> None:
    """A producer that refused at boot has already exited. Waiting out the
    ceiling for it would turn a clear refusal into a ten-minute silence."""
    dead = subprocess.Popen([sys.executable, "-c", ""])
    dead.wait()
    started = time.monotonic()
    result = _run_waiter(tmp_path, tmp_path / "never.jsonl", "600", dead.pid)
    assert result.returncode != 0
    assert "exited before writing a usable journal row" in result.stderr
    assert time.monotonic() - started < 30


def test_red_the_waiter_refuses_an_unapproved_row_rather_than_waiting(
    tmp_path: Path,
) -> None:
    """The producer wrote, but not as an approved producer. The guard would
    refuse that journal, and no amount of waiting unwrites it — so the wait
    says so at once, with the guard's own predicate (``unapproved_rows``, the
    allowlist and its delimiter rule) rather than a second opinion."""
    journal = _journal(
        tmp_path / "journal.jsonl", [_row(source_id="tos-cp3-live-EVIL/0.1.0")]
    )
    alive = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        result = _run_waiter(tmp_path, journal, "600", alive.pid)
    finally:
        alive.kill()
    assert result.returncode != 0
    assert "not an approved real producer" in result.stderr
    assert not (tmp_path / "snapshot.json").exists()


def test_the_waiter_records_every_row_present_at_boot(tmp_path: Path) -> None:
    """``consumed_stale_at_boot`` is the rows present when the boot begins —
    not "the first one". A seed that published two bars before the guard ran
    leaves two structurally-unconsumable lines (plan §5 M5's own exclusion),
    and the §3.6 extractor reads exactly this file to tell them from a line
    the runtime failed to consume."""
    journal = _journal(
        tmp_path / "journal.jsonl",
        [_row(source_id=_APPROVED_SOURCE_ID) for _ in range(2)],
    )
    alive = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        result = _run_waiter(tmp_path, journal, "600", alive.pid)
    finally:
        alive.kill()
    assert result.returncode == 0, result.stderr
    snapshot = json.loads((tmp_path / "snapshot.json").read_text("utf-8"))
    assert snapshot["consumed_stale_at_boot"] == 2
    assert len(snapshot["pre_boot_raw_event_ids"]) == 2
    assert "consumed_stale_at_boot=2" in result.stdout


# ---------------------------------------------------------------------------
# 2026-10-14 review round: xtrace leaks, group liveness, deferred signals
# ---------------------------------------------------------------------------


def _run_runner_traced(repo: Path, tmp_path: Path, **overrides: str) -> Any:
    """The runner under a TRACE, the way an operator debugging it would."""
    env = _runner_env(tmp_path, **overrides)
    result = subprocess.run(
        ["bash", "-x", str(repo / "tools/tos_cp3/runners/run_tenant_session.sh")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
        timeout=180,
    )
    result.producer_outlived_the_runner = _producer_outlived_the_runner(tmp_path)
    return result


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("KIS_FUTURES_APP_KEY", _PRODUCER_FAKE_KEY),
        ("KIS_FUTURES_APP_SECRET", _PRODUCER_FAKE_SECRET),
    ],
)
def test_red_codex_high_no_credential_value_survives_bash_x(
    tmp_path: Path, variable: str, value: str
) -> None:
    """**Codex review HIGH.** The guard against the key reaching the runtime
    must not itself print the key.

    Concrete input: the operator exports the key and runs the template with
    ``bash -x`` — a debugging habit, not a mistake. ``set -x`` prints every
    word AFTER expansion, so the first cut's ``[ -z "$(printenv "$_real_key")" ]``
    wrote the value to stderr and into TENANT_LOG on its way to refusing it.

    Both halves of the fix are exercised at once: tracing is off before any
    environment is read, and the test is on the NAME (``${!name+x}``) so there
    is no expansion to print. Restore either half and the value appears in the
    captured stream.
    """
    repo = _runner_repo(tmp_path)
    result = _run_runner_traced(repo, tmp_path, **{variable: value})
    stream = (
        result.stdout
        + result.stderr
        + (tmp_path / "session.log").read_text("utf-8", errors="replace")
    )
    assert result.returncode != 0
    assert f"{variable} is set in this shell" in stream
    assert value not in stream, "the credential value reached the trace"


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("KIS_FUTURES_APP_KEY", _PRODUCER_FAKE_KEY),
        ("KIS_FUTURES_APP_SECRET", _PRODUCER_FAKE_SECRET),
    ],
)
def test_red_codex_high_no_credential_value_survives_inherited_shellopts(
    tmp_path: Path, variable: str, value: str
) -> None:
    """The same leak through the other door: ``SHELLOPTS=xtrace`` exported by
    the CALLING shell turns tracing on before this script's first line, with
    nothing in the invocation to show for it. ``set +x`` at the top is what
    closes it, and this is the input that proves the top is early enough."""
    repo = _runner_repo(tmp_path)
    result = _run_runner(repo, tmp_path, SHELLOPTS="xtrace", **{variable: value})
    stream = (
        result.stdout
        + result.stderr
        + (tmp_path / "session.log").read_text("utf-8", errors="replace")
    )
    assert result.returncode != 0
    assert value not in stream, "the credential value reached the inherited trace"


def test_the_producer_holds_the_keys_and_the_runtime_does_not(
    tmp_path: Path,
) -> None:
    """**Codex review LOW — the separation stated as a comparison.**

    The first cut asserted only that the runtime's environment lacked the two
    keys, in a run where nothing had them: true, and true of any run at all.
    This asserts the difference that is the actual claim — the PRODUCER reads
    them (from the file its own config names) and the RUNTIME never sees them
    — so a change that handed the keys to every child turns it red.
    """
    repo = _runner_repo(tmp_path, bootable=True)
    runtime_env = tmp_path / "runtime-env.json"
    producer_env = tmp_path / "producer-env.json"
    result = _run_runner(
        repo,
        tmp_path,
        TENANT_STOP_AT="+15 seconds",
        **{
            _RUN_PIDFILE_ENV: str(tmp_path / "run.pid"),
            _RUN_ENVFILE_ENV: str(runtime_env),
            _PRODUCER_ENVFILE_ENV: str(producer_env),
        },
    )
    assert "=== BOOT" in result.stdout + result.stderr
    producer = json.loads(producer_env.read_text("utf-8"))
    runtime = json.loads(runtime_env.read_text("utf-8"))
    # the premise: the producer really does hold both keys...
    assert producer["KIS_FUTURES_APP_KEY"] == _PRODUCER_FAKE_KEY
    assert producer["KIS_FUTURES_APP_SECRET"] == _PRODUCER_FAKE_SECRET
    # ...and the runtime holds neither
    assert "KIS_FUTURES_APP_KEY" not in runtime
    assert "KIS_FUTURES_APP_SECRET" not in runtime
    # nor did either value pass through the runner's own log
    assert _PRODUCER_FAKE_KEY not in (tmp_path / "session.log").read_text("utf-8")


def test_red_codex_medium_the_worker_dies_when_its_supervisor_was_reaped_first(
    tmp_path: Path,
) -> None:
    """**Codex review MEDIUM.** Liveness is a question about the GROUP.

    Concrete input: the supervising ``timeout`` is SIGKILLed and reaped before
    the stop path runs — a host OOM killer, an operator's ``kill -9``, a
    crashed supervisor. Its worker keeps running in the same process group. A
    leader-only ``kill -0`` then answers "already gone" and ``stop_supervised``
    returns success over a process still holding a REAL quotation session.

    Here the worker also ignores SIGTERM, so only the group KILL can end it —
    and the supervisor's own ``--kill-after`` is five minutes, far outside the
    window, so it cannot be the thing that cleans up.
    """
    marker = tmp_path / "worker.pid"
    script = tmp_path / "ignore-term.py"
    script.write_text(
        "import os, signal, time\n"
        "from pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"Path({str(marker)!r}).write_text(str(os.getpid()))\n"
        "while True:\n"
        "    time.sleep(0.2)\n",
        encoding="utf-8",
    )
    driver = tmp_path / "reaped-leader.sh"
    driver.write_text(
        "set -u\n"
        f". {_RUNNER_COMMON}\n"
        'set_log_file ""\n'
        f"timeout --kill-after=300s 600s {sys.executable} {script} "
        f">{tmp_path / 'worker.out'} 2>&1 &\n"
        "PID=$!\n"
        "while [ ! -s %s ]; do sleep 0.1; done\n" % marker
        # the supervisor dies and is reaped, leaving the worker in its group
        + 'kill -KILL "$PID"\n'
        'wait "$PID" 2>/dev/null || true\n'
        'stop_supervised "$PID" 2 worker\n'
        "echo returned\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", str(driver)], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "returned" in result.stdout
    worker_pid = int(marker.read_text().strip())
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and _pid_alive(worker_pid):
        time.sleep(0.2)
    try:
        assert not _pid_alive(worker_pid), (
            f"the worker (pid {worker_pid}) outlived a stop whose supervisor had "
            "already been reaped — the liveness test asked about the leader, not "
            "the group"
        )
    finally:
        if _pid_alive(worker_pid):
            os.kill(worker_pid, signal.SIGKILL)
    # it really did go through the stop path (not "nothing to do")
    assert "STOP SIGTERM" in result.stdout


def test_red_m2_a_signal_during_the_first_row_wait_is_not_deferred(
    tmp_path: Path,
) -> None:
    """**Claude-lane MEDIUM M2.** Bash runs a trap only BETWEEN commands.

    Concrete input: the producer never publishes (so the wait runs its full
    bound) and the operator sends TERM. As a foreground ``$(…)`` the handler
    waited for the substitution to finish — up to ``FIRST_LINE_TIMEOUT_S``,
    ten minutes, with the producer calling the real quotation API throughout.
    In the background with ``wait``, the handler runs when the signal lands.

    Measured, not asserted from the shape: the runner must be gone, and the
    producer with it, in seconds rather than at the bound.
    """
    repo = _runner_repo(tmp_path)
    env = _runner_env(tmp_path, **{_PRODUCER_ROWS_ENV: "never"})
    runner = subprocess.Popen(
        ["bash", str(repo / "tools/tos_cp3/runners/run_tenant_session.sh")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )
    try:
        pidfile = tmp_path / "producer.pid"
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not pidfile.is_file():
            assert runner.poll() is None, runner.communicate()[0]
            time.sleep(0.2)
        assert pidfile.is_file(), "the stub producer never started"
        # it is waiting now: the journal exists but holds nothing approved
        time.sleep(1.0)

        sent_at = time.monotonic()
        runner.send_signal(signal.SIGTERM)
        out = runner.communicate(timeout=60)[0]
        elapsed = time.monotonic() - sent_at
    finally:
        if runner.poll() is None:
            runner.kill()
    assert runner.returncode == 143, out
    assert "SIGNAL TERM received by the runner" in out
    assert elapsed < 30, f"the signal was deferred for {elapsed:.1f}s"
    assert not _producer_outlived_the_runner(tmp_path)


def test_l2_the_boot_snapshot_is_taken_at_the_boot_not_at_the_first_row(
    tmp_path: Path,
) -> None:
    """**Claude-lane LOW L2.** A bar published during guard/render/boot is
    pre-boot too.

    Concrete input: the producer writes its second row AFTER the first-row
    wait returns — the guard, the render and the label check take real time
    and the market does not pause for them. Snapshotted at first-row time the
    second id is missing, and §3.6 then reports it as a line the runtime
    failed to consume: the defect shape, manufactured by the runner's own
    bookkeeping.
    """
    repo = _runner_repo(tmp_path, bootable=True)
    result = _run_runner(
        repo,
        tmp_path,
        TENANT_STOP_AT="+15 seconds",
        **{
            _RUN_PIDFILE_ENV: str(tmp_path / "run.pid"),
            # one row at once, a second when the render lands — after the
            # first-row wait returned, before the boot
            _PRODUCER_ROWS_ENV: "1+1",
            _PRODUCER_SECOND_ROW_WHEN_ENV: str(
                tmp_path / "render-out" / "critical_input_policy.yaml"
            ),
        },
    )
    assert "=== BOOT" in result.stdout + result.stderr
    journal_ids = [
        json.loads(line)["raw_event_id"]
        for line in (tmp_path / "journal.jsonl").read_text("utf-8").splitlines()
        if line.strip()
    ]
    snapshot = json.loads(
        (tmp_path / "producer-session" / "boot-journal-snapshot.json").read_text(
            "utf-8"
        )
    )
    assert len(journal_ids) == 2, journal_ids
    assert snapshot["consumed_stale_at_boot"] == 2
    assert snapshot["pre_boot_raw_event_ids"] == journal_ids


def test_red_codex_high_no_credential_value_reaches_a_redirected_trace(
    tmp_path: Path,
) -> None:
    """**Codex review HIGH, the third door: ``BASH_XTRACEFD``.**

    A trace need not go to the terminal. ``BASH_XTRACEFD`` points it at an
    arbitrary open descriptor — a shared operator log, a file someone later
    pastes into an issue — and ``SHELLOPTS=xtrace`` turns it on without
    appearing in the command line. The two together are the quietest version
    of this leak: nothing in the invocation shows it, and the output lands
    somewhere the runner never looks.

    The descriptor is real (``pass_fds``), so this is the mechanism and not a
    mock of it; the assertion is that the file it points at never contains the
    credential.
    """
    repo = _runner_repo(tmp_path)
    trace = tmp_path / "trace.log"
    with trace.open("w", encoding="utf-8") as handle:
        env = _runner_env(tmp_path, KIS_FUTURES_APP_KEY=_PRODUCER_FAKE_KEY)
        env["SHELLOPTS"] = "xtrace"
        env["BASH_XTRACEFD"] = str(handle.fileno())
        result = subprocess.run(
            ["bash", str(repo / "tools/tos_cp3/runners/run_tenant_session.sh")],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
            timeout=180,
            pass_fds=(handle.fileno(),),
        )
    assert result.returncode != 0
    assert "KIS_FUTURES_APP_KEY is set in this shell" in result.stdout + result.stderr
    written = trace.read_text("utf-8", errors="replace")
    assert _PRODUCER_FAKE_KEY not in written, "the value reached the redirected trace"
    assert _PRODUCER_FAKE_KEY not in (tmp_path / "session.log").read_text(
        "utf-8", errors="replace"
    )
