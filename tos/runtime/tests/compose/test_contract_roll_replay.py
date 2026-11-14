"""Front-month contract roll vs. boot-time engine replay (resident paper runtime)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from tos_runtime.compose._boot_integrity import EngineReplayDiverged

from . import _fixtures as fx
from . import conftest as cf
from .conftest import (
    approve_constructed_intent,
    call_wrapped_fixture,
)
from .test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

FRONT_MONTH = "A05610"
NEXT_MONTH = "A05611"


def _config_for(monkeypatch: pytest.MonkeyPatch, instrument: str, root: Path) -> Path:
    """A fresh compose config dir under ``root``, rendered for ``instrument``."""
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(fx, "INSTRUMENT", instrument)
    monkeypatch.setattr(cf, "_VENUE_POLICY_INSTRUMENT", instrument)
    return call_wrapped_fixture(cf.config_dir, root)


def _drive_one_real_hand_off(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """One crossing tick all the way to a real hand-off, leaving a real recorded"""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    assert proposal_digest is not None
    approve_constructed_intent(
        runtime,
        custody_root,
        proposal_digest=proposal_digest,
    )
    results2 = runtime.run_once((event,))
    assert results2[0].flow is not None and results2[0].flow.handed_off is True
    assert len(runtime.transport.requests) == 1
    runtime.rcl_log.close()
    runtime.evidence_store.close()


def _recorded_outcome_digests(data_dir: Path) -> list[object]:
    """Every ``EVENT_CONSUMED`` receipt's recorded ``outcome_digest`` in ``data_dir``'s evidence"""
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
    """ONE durable set carried across a front-month roll is not bootable (the hazard)."""
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

    control_config = _config_for(monkeypatch, FRONT_MONTH, tmp_path / "control")
    control = _compose(tmp_path, control_config, data_dir, custody_root)
    control.rcl_log.close()
    control.evidence_store.close()
    assert _kind_count(data_dir, "REPLAY_DIVERGED") == 0

    rolled_config = _config_for(monkeypatch, NEXT_MONTH, tmp_path / "rolled")
    with pytest.raises(EngineReplayDiverged):
        _compose(tmp_path, rolled_config, data_dir, custody_root)

    assert _kind_count(data_dir, "REPLAY_DIVERGED") == len(digests)


def test_rolled_instrument_into_its_own_data_dir_boots_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One durable set PER CONTRACT MONTH makes the roll an ordinary genesis boot (the fix)."""
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

    back_config = _config_for(monkeypatch, FRONT_MONTH, tmp_path / "back")
    back = _compose(tmp_path, back_config, data_dir, custody_root)
    back.rcl_log.close()
    back.evidence_store.close()
    assert _kind_count(data_dir, "REPLAY_DIVERGED") == 0
