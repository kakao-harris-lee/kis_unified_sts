"""``intake_kind`` wiring-level tests (TOS tick-source wave, W2 lane review finding — HIGH)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.compose._marketfeed_wiring import (
    MarketFeedConfigError,
    load_marketfeed_config,
)
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.transport.kis_quote.adapter import KisQuoteObservationIntake
from tos_runtime.transport.kis_quote.config import KisQuoteTransportConfigError

from . import _fixtures as fx
from .example_integrity import assert_required_paths_present
from .example_integrity_registry import EXAMPLE_REQUIRED_PATHS
from .test_compose_root import _compose
from .test_marketfeed_wiring import (
    _write_critical_input_policy,
    _write_journal,
)
from .test_transport_wiring import _activate_mock_stock_order, _build_custody

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _write_marketfeed_config_raw(config_dir: Path, raw: dict[str, Any]) -> None:
    """Write ``marketfeed.yaml`` from a caller-supplied raw mapping, bypassing"""
    (config_dir / "marketfeed.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )


def _valid_marketfeed_raw(*, journal_path: Path) -> dict[str, Any]:
    """The same fields ``test_marketfeed_wiring.py``'s own ``_write_marketfeed_config`` writes,"""
    return {
        "instruments": [fx.INSTRUMENT],
        "instrument_class": fx.INSTRUMENT_CLASS,
        "account": fx.ACCOUNT,
        "direction": "LONG",
        "quantity_basis": "FIXED",
        "unit": "CONTRACT",
        "intake_kind": "journal",
        "journal_path": str(journal_path),
        "poll_interval_ms": 100,
        "journal_pass_allowance_ms": 100,
        "time_evaluate_closed_interval_ms": 60_000,
        "snapshot_age_bound": 60_000,
        "interval_width": 1_000,
    }


def _write_kis_quote_transport_config(config_dir: Path, **overrides: Any) -> Path:
    """Write a fully-valued ``kis_quote.yaml`` — mirrors"""
    raw: dict[str, Any] = {
        "endpoint_rest_base": fx.KIS_MOCK_REST_BASE,
        "allow_plaintext_for_tests": False,
        "quote_path": "/uapi/domestic-futureoption/v1/quotations/inquire-price",
        "tr_id": "FHMIF10000000",
        "market_div_code": "F",
        "instrument": fx.INSTRUMENT,
        "token_path": "/oauth2/tokenP",
        "token_reissue_min_interval_s": 60,
        "field_mapping": {"futs_prpr": "close"},
        "source_id": "kis_quote_wiring_test",
        "request_timeout_s": 2.0,
        "app_key_min_request_interval_ms": 1100,
        "app_key_request_wait_budget_ms": 2200,
    }
    raw.update(overrides)
    path = config_dir / "kis_quote.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def test_missing_intake_kind_refuses(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    del raw["intake_kind"]
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="intake_kind"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


@pytest.mark.parametrize("value", [None, 0, -60_000, "60000"])
def test_missing_or_non_positive_closed_evaluation_interval_refuses(
    tmp_path: Path, value: object
) -> None:
    """``time_evaluate_closed_interval_ms`` (plan 2026-09-26 periodic time eval, W1) never"""
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    raw = _valid_marketfeed_raw(journal_path=tmp_path / "journal.jsonl")
    if value is None:
        del raw["time_evaluate_closed_interval_ms"]
    else:
        raw["time_evaluate_closed_interval_ms"] = value
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="time_evaluate_closed_interval_ms"):
        load_marketfeed_config(config_dir / "marketfeed.yaml")


def test_null_intake_kind_refuses(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    raw["intake_kind"] = None
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="intake_kind"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_unknown_intake_kind_refuses(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """``journal_path`` is deliberately OMITTED from ``raw`` (not merely left at its valid"""
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    del raw["journal_path"]
    raw["intake_kind"] = "websocket"
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="is not one of"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_journal_path_present_with_kis_quote_intake_refuses(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """``journal_path`` set while ``intake_kind: kis_quote`` — refused BEFORE ever reaching"""
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    raw["intake_kind"] = "kis_quote"
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="journal_path"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_journal_path_absent_with_journal_intake_refuses(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """``match`` is narrowed to ``"required when intake_kind"`` — the fragment unique to"""
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    raw = _valid_marketfeed_raw(journal_path=journal_path)
    del raw["journal_path"]
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="required when intake_kind"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_kis_quote_intake_builds_through_the_full_compose_stack(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir)
    _build_custody(custody_root)
    _write_critical_input_policy(config_dir)
    _write_kis_quote_transport_config(config_dir)
    raw = _valid_marketfeed_raw(journal_path=tmp_path / "unused.jsonl")
    raw["intake_kind"] = "kis_quote"
    del raw["journal_path"]
    del raw["journal_pass_allowance_ms"]
    _write_marketfeed_config_raw(config_dir, raw)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    try:
        assert runtime.marketfeed is not None
        assert isinstance(runtime.marketfeed._intake, KisQuoteObservationIntake)
        intake_session = runtime.marketfeed._intake._credential_session  # noqa: SLF001
        transport_session = runtime.transport._credential_session  # noqa: SLF001
        assert intake_session is transport_session
    finally:
        runtime.rcl_log.close()
        runtime.evidence_store.close()


def test_kis_quote_intake_and_the_time_service_share_one_monotonic_source(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """#810 (plan ``docs/plans/2026-09-28-tos-kis-quote-request-anchor-plan.md`` §4 T-5): the"""
    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir)
    _build_custody(custody_root)
    _write_critical_input_policy(config_dir)
    _write_kis_quote_transport_config(config_dir)
    raw = _valid_marketfeed_raw(journal_path=tmp_path / "unused.jsonl")
    raw["intake_kind"] = "kis_quote"
    del raw["journal_path"]
    del raw["journal_pass_allowance_ms"]
    _write_marketfeed_config_raw(config_dir, raw)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )
    try:
        assert runtime.marketfeed is not None
        intake = runtime.marketfeed._intake  # noqa: SLF001
        assert isinstance(intake, KisQuoteObservationIntake)
        assert intake._monotonic is runtime.time_service._monotonic  # noqa: SLF001
    finally:
        runtime.rcl_log.close()
        runtime.evidence_store.close()


def test_kis_quote_intake_missing_config_file_refuses_at_wiring_level(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Same setup as the happy path, MINUS ``kis_quote.yaml`` itself — proves"""
    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir)
    _build_custody(custody_root)
    _write_critical_input_policy(config_dir)
    assert not (config_dir / "kis_quote.yaml").exists()
    raw = _valid_marketfeed_raw(journal_path=tmp_path / "unused.jsonl")
    raw["intake_kind"] = "kis_quote"
    del raw["journal_path"]
    del raw["journal_pass_allowance_ms"]
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(KisQuoteTransportConfigError, match="not found"):
        _compose(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            transport_kind=TransportKind.KIS_MOCK,
        )


def test_kis_quote_intake_no_instance_binding_refuses_at_wiring_level(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """The DEFAULT ``config_dir`` fixture's ``broker_scopes.yaml`` (``SYNTHETIC_FUTURES_ORDER``,"""
    _write_critical_input_policy(config_dir)
    _write_kis_quote_transport_config(config_dir)
    raw = _valid_marketfeed_raw(journal_path=tmp_path / "unused.jsonl")
    raw["intake_kind"] = "kis_quote"
    del raw["journal_path"]
    del raw["journal_pass_allowance_ms"]
    _write_marketfeed_config_raw(config_dir, raw)

    with pytest.raises(MarketFeedConfigError, match="instance"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_shipped_example_file_is_all_null_and_therefore_refuses() -> None:
    """``marketfeed.example.yaml`` is a template, not an approved config — every leaf is ``null``"""
    example_path = (
        Path(__file__).resolve().parents[2] / "config" / "marketfeed.example.yaml"
    )
    assert (
        example_path.is_file()
    ), "fixture assumption: the example file ships at this path"
    with pytest.raises(MarketFeedConfigError):
        load_marketfeed_config(example_path)
    assert_required_paths_present("marketfeed", EXAMPLE_REQUIRED_PATHS["marketfeed"])
