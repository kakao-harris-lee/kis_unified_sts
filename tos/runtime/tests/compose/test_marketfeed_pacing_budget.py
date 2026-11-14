"""The ``intake_kind: journal`` pacing guard — ``poll_interval_ms +"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.compose._marketfeed_wiring import (
    MarketFeedConfigError,
    _load_config_within_freshness_budget,
)
from tos_runtime.marketfeed.time_projection import _DELAY_BOUND_FIELDS
from tos_runtime.time.config import _BOUND_FIELD_BY_KEY, load_time_config

from . import _fixtures as fx
from .test_compose_root import _compose
from .test_marketfeed_intake_kind_wiring import (
    _valid_marketfeed_raw,
    _write_kis_quote_transport_config,
    _write_marketfeed_config_raw,
)
from .test_marketfeed_wiring import _write_critical_input_policy, _write_journal

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_PAPER_MAX_AGE_MS = 1000
_PAPER_DELAY_BOUND_MS = 50

_PAPER_BUDGET_MS = _PAPER_MAX_AGE_MS - _PAPER_DELAY_BOUND_MS * len(_DELAY_BOUND_FIELDS)

_DELAY_KEY_BY_FIELD = {field: key for key, field in _BOUND_FIELD_BY_KEY.items()}

_MISSING = object()


def _write_paper_shaped_time_yaml(config_dir: Path, **overrides: int) -> None:
    """Re-shape the ``config_dir`` fixture's own ``time.yaml`` to the APPROVED paper bounds."""
    path = config_dir / "time.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["MAX_time_conservative_freshness_age_ms"] = _PAPER_MAX_AGE_MS
    for field in _DELAY_BOUND_FIELDS:
        raw[_DELAY_KEY_BY_FIELD[field]] = _PAPER_DELAY_BOUND_MS
    raw.update(overrides)
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _write_journal_marketfeed(
    config_dir: Path, tmp_path: Path, **overrides: Any
) -> Path:
    """Write a valid ``intake_kind: journal`` ``marketfeed.yaml``, with ``overrides``"""
    raw = _valid_marketfeed_raw(journal_path=tmp_path / "journal.jsonl")
    for key, value in overrides.items():
        if value is _MISSING:
            del raw[key]
        else:
            raw[key] = value
    _write_marketfeed_config_raw(config_dir, raw)
    return config_dir / "marketfeed.yaml"


@pytest.mark.parametrize(
    ("poll_ms", "allowance_ms", "admitted"),
    [
        (1000, 100, False),
        (700, 100, True),
        (701, 100, False),
        (400, 100, True),
    ],
)
def test_journal_pacing_against_the_paper_shaped_budget(
    tmp_path: Path, config_dir: Path, poll_ms: int, allowance_ms: int, admitted: bool
) -> None:
    _write_paper_shaped_time_yaml(config_dir)
    time_config = load_time_config(config_dir / "time.yaml")
    assert (
        time_config.max_time_conservative_freshness_age_ms
        - sum(getattr(time_config, field) for field in _DELAY_BOUND_FIELDS)
        == _PAPER_BUDGET_MS
    ), "fixture assumption: the paper-shaped budget is 800 ms"
    path = _write_journal_marketfeed(
        config_dir,
        tmp_path,
        poll_interval_ms=poll_ms,
        journal_pass_allowance_ms=allowance_ms,
    )

    if admitted:
        config = _load_config_within_freshness_budget(path, time_config)
        assert config.poll_interval_ms == poll_ms
        assert config.journal_pass_allowance_ms == allowance_ms
        return
    with pytest.raises(MarketFeedConfigError, match="paces outside the conservative"):
        _load_config_within_freshness_budget(path, time_config)


@pytest.mark.parametrize("raised_field", _DELAY_BOUND_FIELDS)
@pytest.mark.parametrize(("poll_ms", "admitted"), [(400, True), (650, False)])
def test_raising_any_one_delay_bound_narrows_the_budget(
    tmp_path: Path, config_dir: Path, raised_field: str, poll_ms: int, admitted: bool
) -> None:
    """Plan §2.3's Σ pin, widened to all four terms. With ONE delay bound at 150 instead of"""
    _write_paper_shaped_time_yaml(
        config_dir, **{_DELAY_KEY_BY_FIELD[raised_field]: 150}
    )
    time_config = load_time_config(config_dir / "time.yaml")
    path = _write_journal_marketfeed(
        config_dir, tmp_path, poll_interval_ms=poll_ms, journal_pass_allowance_ms=100
    )

    if admitted:
        assert (
            _load_config_within_freshness_budget(path, time_config).poll_interval_ms
            == poll_ms
        )
        return
    with pytest.raises(MarketFeedConfigError, match="paces outside the conservative"):
        _load_config_within_freshness_budget(path, time_config)


def test_the_refusal_message_names_the_three_terms_and_the_collector_headroom(
    tmp_path: Path, config_dir: Path
) -> None:
    """An operator reading only the message must be able to pick a value. Plan §2.3: the"""
    _write_paper_shaped_time_yaml(config_dir)
    time_config = load_time_config(config_dir / "time.yaml")
    path = _write_journal_marketfeed(
        config_dir, tmp_path, poll_interval_ms=1000, journal_pass_allowance_ms=100
    )

    with pytest.raises(MarketFeedConfigError) as excinfo:
        _load_config_within_freshness_budget(path, time_config)
    message = str(excinfo.value)
    assert "poll_interval_ms=1000" in message
    assert "journal_pass_allowance_ms=100" in message
    assert "MAX_time_conservative_freshness_age_ms=1000" in message
    assert "sum(delay_bounds)=200" in message
    assert "800 ms" in message
    assert "-300 ms of headroom" in message


@pytest.mark.parametrize("value", [_MISSING, None, "TBD", "", 0, -1, True])
def test_journal_pass_allowance_is_required_and_positive_for_journal(
    tmp_path: Path, config_dir: Path, value: Any
) -> None:
    """Plan §2.3's last refusal row. ``"TBD"``/``""``/``True`` are refused by"""
    _write_paper_shaped_time_yaml(config_dir)
    time_config = load_time_config(config_dir / "time.yaml")
    path = _write_journal_marketfeed(
        config_dir, tmp_path, journal_pass_allowance_ms=value
    )

    with pytest.raises(MarketFeedConfigError, match="journal_pass_allowance_ms"):
        _load_config_within_freshness_budget(path, time_config)


def test_kis_quote_is_not_subject_to_the_pacing_guard(
    tmp_path: Path, config_dir: Path
) -> None:
    """Plan §0-3 / §2.3's last row: ``kis_quote`` + ``poll_interval_ms: 1000`` is ADMITTED"""
    _write_paper_shaped_time_yaml(config_dir)
    time_config = load_time_config(config_dir / "time.yaml")
    path = _write_journal_marketfeed(
        config_dir,
        tmp_path,
        intake_kind="kis_quote",
        journal_path=_MISSING,
        journal_pass_allowance_ms=_MISSING,
        poll_interval_ms=1000,
    )

    config = _load_config_within_freshness_budget(path, time_config)
    assert config.intake_kind == "kis_quote"
    assert config.poll_interval_ms == 1000
    assert config.journal_pass_allowance_ms is None


def test_journal_pass_allowance_present_with_kis_quote_refuses(
    tmp_path: Path, config_dir: Path
) -> None:
    """The required-XOR-forbidden half, mirroring ``journal_path``'s own cross-check: a"""
    _write_paper_shaped_time_yaml(config_dir)
    time_config = load_time_config(config_dir / "time.yaml")
    path = _write_journal_marketfeed(
        config_dir,
        tmp_path,
        intake_kind="kis_quote",
        journal_path=_MISSING,
        journal_pass_allowance_ms=100,
    )

    with pytest.raises(MarketFeedConfigError, match="journal_pass_allowance_ms"):
        _load_config_within_freshness_budget(path, time_config)


def test_boot_refuses_a_journal_pacing_outside_the_budget(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Through the REAL composition root: the 2026-09-27 paper combination (1000 + 100"""
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    _write_paper_shaped_time_yaml(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    raw["poll_interval_ms"] = 1000
    raw["journal_pass_allowance_ms"] = 100
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="paces outside the conservative"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_boot_admits_the_disposition_pacing_against_the_same_budget(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """The twin of the test above with ONLY ``poll_interval_ms`` changed to the operator's"""
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    _write_paper_shaped_time_yaml(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    raw["poll_interval_ms"] = 400
    raw["journal_pass_allowance_ms"] = 100
    _write_marketfeed_config_raw(config_dir, raw)

    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    try:
        assert runtime.marketfeed is not None
    finally:
        runtime.rcl_log.close()
        runtime.evidence_store.close()


def test_kis_quote_boot_is_not_budgeted(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """``kis_quote`` + 1000 reaches a REAL ``build_tick_scheduler`` call under the same"""
    _write_critical_input_policy(config_dir)
    _write_kis_quote_transport_config(config_dir)
    _write_paper_shaped_time_yaml(config_dir)
    raw = _valid_marketfeed_raw(journal_path=tmp_path / "unused.jsonl")
    raw["intake_kind"] = "kis_quote"
    raw["poll_interval_ms"] = 1000
    del raw["journal_path"]
    del raw["journal_pass_allowance_ms"]
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="instance") as excinfo:
        _compose(tmp_path, config_dir, data_dir, custody_root)
    assert "paces outside" not in str(excinfo.value)


def test_fixture_instrument_is_the_one_the_journal_tests_share() -> None:
    """Guards the import above: ``_valid_marketfeed_raw`` is the sibling module's helper,"""
    raw = _valid_marketfeed_raw(journal_path=Path("/tmp/unused.jsonl"))
    assert raw["instruments"] == [fx.INSTRUMENT]
    assert raw["intake_kind"] == "journal"
    assert raw["journal_pass_allowance_ms"] == 100
