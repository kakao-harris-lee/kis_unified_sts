"""Front-month contract roll vs. boot-time engine replay (resident paper runtime).

The resident TOS paper session renders its config with
``shared.instruments.futures.get_front_month_code(product="mini")`` for the day, so the
instrument coordinate CHANGES by itself the first trading day after expiry — no edit, no
decision, nothing to review. For the 2026-10 contract that is ``A05610`` through
2026-10-08 (expiry) and ``A05611`` from 2026-10-09 on — a mapping pinned OUTSIDE this
kernel, not here; see ``FRONT_MONTH`` below for where.

Boot-time replay re-runs every durable inbox event against **today's** instrument-keyed
``StrategyRegistry`` (``tos/engine/registry.py`` keys on ``(account, instrument)``). Replaying
yesterday's receipt, which carries a real recorded ``outcome_digest``, against a registry keyed
on the NEW instrument resolves nothing, so the replayed outcome digest is ``None``, the compare
is ``INCONCLUSIVE``, and :class:`~tos_runtime.compose._boot_integrity.EngineReplayDiverged` is
raised. The damage is permanent: the ``REPLAY_DIVERGED`` evidence row is written durably before
the raise, so reverting the config does not clear it
(``tos_runtime.recovery.inputs``'s ``_replay_verdict_ok`` requires zero such rows;
``recovery/barrier.py`` only restates that rule when it checks the obligation).

Both halves are asserted here, because only the pair carries the decision:

* :func:`test_rolled_instrument_over_the_same_data_dir_diverges` — the hazard. One durable set
  shared across a roll is NOT bootable. This is the shape the flat
  ``~/.local/state/tos/paper-data`` layout would have hit on 2026-10-12, the first resident
  session after the 2026-10-08 expiry (2026-10-09 is 한글날, a listed holiday in both
  calendars).
* :func:`test_rolled_instrument_into_its_own_data_dir_boots_clean` — the fix (operator decision
  2026-10-04): one durable set PER CONTRACT MONTH, ``paper-data/<instrument>``. The rolled boot
  lands in a fresh leaf, which is an ordinary genesis boot, and the previous month's leaf stays
  bootable under its own instrument.

Hermetic: real sqlite files under ``tmp_path``, this suite's own ``_compose``/``_reach_trusted``
helpers, no network, no host state.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from tos_runtime.compose._boot_integrity import EngineReplayDiverged

from . import _fixtures as fx
from . import conftest as cf
from .conftest import call_wrapped_fixture, write_approval_file
from .test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: KOSPI200 mini, October 2026 — what ``get_front_month_code(product="mini")`` returns through
#: 2026-10-08 (that contract's second-Thursday expiry).
FRONT_MONTH = "A05610"
#: …and what it returns from 2026-10-09 on.
#:
#: Neither value is derived here, and nothing inside ``tos/`` could derive it: the import
#: firewall denies ``shared.instruments``. The mapping is pinned OUTSIDE the firewall — the
#: code strings by ``shared/instruments/futures.py::get_front_month_code``, and the 2026-10
#: boundary those strings turn on by the real-calendar tests named in
#: ``docs/runbooks/tos-paper-boot.md`` §7.10 7 「재도출」:
#: ``test_deploy_config.py::test_real_calendar_mini_october_expiry_day_before_and_after_close``
#: (2026-10-08 expiry) and ``::test_real_calendar_day_after_mini_october_expiry_rolls_to_november``
#: (the next day rolls to November). This suite needs neither fact: it uses the two values only
#: as two DISTINCT OPAQUE STRINGS, and would assert exactly the same thing under any other pair.
NEXT_MONTH = "A05611"


def _config_for(monkeypatch: pytest.MonkeyPatch, instrument: str, root: Path) -> Path:
    """A fresh compose config dir under ``root``, rendered for ``instrument``.

    Mirrors what ``scripts/tos/render_paper_config.py`` does on the host: the instrument is a
    coordinate written into the policy documents at render time, so a roll is a brand-new
    config dir, never an edit of yesterday's. ``fx.INSTRUMENT`` additionally governs the
    fixtures ``_compose`` itself reads (``fx.construction_config()``) and the crossing event, so
    both are repointed together — leaving one behind would compose a runtime whose config and
    whose events disagree, which is a different bug than the one under test.

    Assumption the monkeypatch rests on: every read of ``fx.INSTRUMENT`` and of
    ``cf._VENUE_POLICY_INSTRUMENT`` happens inside a function body, so rebinding the module
    attribute is what later calls see. A module-level constant in either module derived from
    them would be computed once at import, before this runs, and would silently defeat the
    repoint — day 2 would compose day 1's instrument and both tests would pass vacuously.
    """
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(fx, "INSTRUMENT", instrument)
    monkeypatch.setattr(cf, "_VENUE_POLICY_INSTRUMENT", instrument)
    return call_wrapped_fixture(cf.config_dir, root)


def _drive_one_real_hand_off(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """One crossing tick all the way to a real hand-off, leaving a real recorded
    ``outcome_digest`` in ``data_dir``'s inbox — the exact setup
    ``test_compose_root.py::TestRecomposeReplay::
    test_recompose_after_a_real_hand_off_does_not_diverge`` builds, which is what makes the
    replay on the NEXT boot non-trivial. A boot that never reached a hand-off has nothing for
    the roll to diverge on, so these tests would pass vacuously without it — hence the
    assertions here rather than in the callers.
    """
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    assert proposal_digest is not None
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=proposal_digest,
        environment_label="non-live-test",
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    results2 = runtime.run_once((event,))
    assert results2[0].flow is not None and results2[0].flow.handed_off is True
    assert len(runtime.transport.requests) == 1
    runtime.rcl_log.close()
    runtime.evidence_store.close()


def _recorded_outcome_digests(data_dir: Path) -> list[object]:
    """Every ``EVENT_CONSUMED`` receipt's recorded ``outcome_digest`` in ``data_dir``'s evidence
    store.

    Read through ``mode=ro`` and deliberately NOT ``immutable=1``: this file was written moments
    ago by a compose in this same test, so the newest rows may still live in its WAL.
    ``immutable=1`` promises sqlite that nobody is writing and lets it skip the WAL, which would
    read stale pages here; plain ``mode=ro`` re-reads the database correctly. The runbook's
    ``immutable=1`` idiom is for inspecting a finished corpus no process is writing.
    """
    connection = sqlite3.connect(
        f"file:{data_dir / 'evidence.sqlite3'}?mode=ro", uri=True
    )
    try:
        return [
            json.loads(row[0])["payload"].get("outcome_digest")
            for row in connection.execute(
                "SELECT payload_json FROM entries WHERE kind = 'EVENT_CONSUMED' ORDER BY seq"
            )
        ]
    finally:
        connection.close()


def _kind_count(data_dir: Path, kind: str) -> int:
    connection = sqlite3.connect(
        f"file:{data_dir / 'evidence.sqlite3'}?mode=ro", uri=True
    )
    try:
        (count,) = connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
        ).fetchone()
        return int(count)
    finally:
        connection.close()


def test_rolled_instrument_over_the_same_data_dir_diverges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ONE durable set carried across a front-month roll is not bootable (the hazard).

    Day 1 boots ``FRONT_MONTH`` and reaches a real hand-off. Day 2 renders ``NEXT_MONTH`` —
    which is what the resident wrapper's own ``get_front_month_code`` call produces, unattended
    — and composes over the SAME ``data_dir``. The control immediately below it (same data dir,
    same instrument) boots fine, so the instrument is the only moving part.
    """
    data_dir = call_wrapped_fixture(cf.data_dir, tmp_path)
    custody_root = call_wrapped_fixture(cf.custody_root, tmp_path)

    day1_config = _config_for(monkeypatch, FRONT_MONTH, tmp_path / "day1")
    _drive_one_real_hand_off(tmp_path, day1_config, data_dir, custody_root)
    digests = _recorded_outcome_digests(data_dir)
    assert (
        digests
    ), "day 1 recorded no EVENT_CONSUMED receipt — nothing for the roll to replay"
    assert any(
        digest for digest in digests
    ), "day 1 recorded no REAL outcome digest — the replay compare would be trivially clean"

    # Control: the same data dir re-composed under the SAME instrument still boots. Without
    # this the test below would also pass if ANY second boot over this data dir failed.
    control_config = _config_for(monkeypatch, FRONT_MONTH, tmp_path / "control")
    control = _compose(tmp_path, control_config, data_dir, custody_root)
    control.rcl_log.close()
    control.evidence_store.close()
    assert _kind_count(data_dir, "REPLAY_DIVERGED") == 0

    rolled_config = _config_for(monkeypatch, NEXT_MONTH, tmp_path / "rolled")
    with pytest.raises(EngineReplayDiverged):
        _compose(tmp_path, rolled_config, data_dir, custody_root)

    # Durable and permanent: the rows are written BEFORE the raise, so the recovery barrier
    # holds this durable set from here on even if the config is reverted. EVERY receipt
    # diverges, not just the one carrying the hand-off — the registry lookup fails for all of
    # them alike (measured here: 3 receipts, 3 rows).
    assert _kind_count(data_dir, "REPLAY_DIVERGED") == len(digests)


def test_rolled_instrument_into_its_own_data_dir_boots_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One durable set PER CONTRACT MONTH makes the roll an ordinary genesis boot (the fix).

    Same day 1 as the test above. Day 2 renders ``NEXT_MONTH`` and composes over its OWN data
    dir — what ``paper-data/<instrument>`` gives the resident wrapper for free, since a fresh
    leaf is genesis v2. Then day 1's leaf is re-booted under its own instrument to show the
    roll left it bootable: per-contract dirs must not cost the previous month's recoverability.

    Red proof: point ``rolled_data_dir`` at ``data_dir`` (the flat layout) AND drop the
    ``rolled_data_dir != data_dir`` guard assert below — on equal paths that assert trips first,
    so leaving it in proves only that the two paths are equal. Without it the failure lands
    where the fix lives: the rolled ``_compose`` raises ``EngineReplayDiverged``, uncaught (the
    hazard the test above catches on purpose). The guard itself stays in the green test: it is
    what makes "its own data dir" a checked fact rather than a naming convention.
    """
    data_dir = call_wrapped_fixture(cf.data_dir, tmp_path)
    custody_root = call_wrapped_fixture(cf.custody_root, tmp_path)

    day1_config = _config_for(monkeypatch, FRONT_MONTH, tmp_path / "day1")
    _drive_one_real_hand_off(tmp_path, day1_config, data_dir, custody_root)
    assert any(_recorded_outcome_digests(data_dir))

    rolled_root = tmp_path / "rolled"
    rolled_config = _config_for(monkeypatch, NEXT_MONTH, rolled_root)
    rolled_data_dir = call_wrapped_fixture(cf.data_dir, rolled_root)
    assert rolled_data_dir != data_dir

    rolled = _compose(tmp_path, rolled_config, rolled_data_dir, custody_root)
    _reach_trusted(rolled)
    rolled.rcl_log.close()
    rolled.evidence_store.close()
    assert _kind_count(rolled_data_dir, "REPLAY_DIVERGED") == 0

    # The previous month's leaf is untouched and still boots under its own instrument.
    back_config = _config_for(monkeypatch, FRONT_MONTH, tmp_path / "back")
    back = _compose(tmp_path, back_config, data_dir, custody_root)
    back.rcl_log.close()
    back.evidence_store.close()
    assert _kind_count(data_dir, "REPLAY_DIVERGED") == 0
