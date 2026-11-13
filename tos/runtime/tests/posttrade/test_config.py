"""Hermetic tests for :mod:`tos_runtime.posttrade.config` (TOS Phase 5 W2-R independent-review"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos_runtime.posttrade.config import (
    FinalityConfigError,
    PostTradeWitnessKind,
    load_finality_config,
)

_VALID_RAW: dict[str, object] = {
    "currency": "KRW",
    "value_date": "2026-09-09",
    "source_revision": "config-test-rev-1",
    "proof_recipe_id": "config-test-recipe-1",
    "release_proof_wait_ms": 60_000,
}


def _write(path: Path, raw: dict[str, object]) -> Path:
    file_path = path / "finality.yaml"
    file_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return file_path


def test_a_fully_valued_file_loads(tmp_path: Path) -> None:
    config = load_finality_config(_write(tmp_path, _VALID_RAW))
    assert config.release_proof_wait_ms == 60_000


def test_release_proof_wait_ms_null_is_named_tbd_refused(tmp_path: Path) -> None:
    raw = dict(_VALID_RAW, release_proof_wait_ms=None)
    with pytest.raises(FinalityConfigError, match="release_proof_wait_ms"):
        load_finality_config(_write(tmp_path, raw))


def test_currency_named_tbd_placeholder_is_refused(tmp_path: Path) -> None:
    """W-A A-0: the literal placeholder string ``"TBD"`` in place of a real"""
    raw = dict(_VALID_RAW, currency="TBD")
    with pytest.raises(FinalityConfigError, match="template placeholder"):
        load_finality_config(_write(tmp_path, raw))


def test_release_proof_wait_ms_zero_is_refused(tmp_path: Path) -> None:
    """Zero is not a smaller bound, it is a silently-disabled one — same discipline as every"""
    raw = dict(_VALID_RAW, release_proof_wait_ms=0)
    with pytest.raises(FinalityConfigError, match="release_proof_wait_ms"):
        load_finality_config(_write(tmp_path, raw))


def test_release_proof_wait_ms_negative_is_refused(tmp_path: Path) -> None:
    raw = dict(_VALID_RAW, release_proof_wait_ms=-1)
    with pytest.raises(FinalityConfigError, match="release_proof_wait_ms"):
        load_finality_config(_write(tmp_path, raw))


def test_release_proof_wait_ms_bool_is_refused(tmp_path: Path) -> None:
    """``bool`` is an ``int`` subclass in Python -- ``True``/``False`` must not silently pass"""
    raw = dict(_VALID_RAW, release_proof_wait_ms=True)
    with pytest.raises(FinalityConfigError, match="release_proof_wait_ms"):
        load_finality_config(_write(tmp_path, raw))


def test_release_proof_wait_ms_missing_key_is_refused(tmp_path: Path) -> None:
    raw = dict(_VALID_RAW)
    del raw["release_proof_wait_ms"]
    with pytest.raises(FinalityConfigError, match="release_proof_wait_ms"):
        load_finality_config(_write(tmp_path, raw))


@pytest.mark.parametrize(
    "field",
    ["currency", "value_date", "source_revision", "proof_recipe_id"],
)
def test_string_field_null_is_named_tbd_refused(tmp_path: Path, field: str) -> None:
    raw = dict(_VALID_RAW, **{field: None})
    with pytest.raises(FinalityConfigError, match=field):
        load_finality_config(_write(tmp_path, raw))


@pytest.mark.parametrize(
    "field",
    ["currency", "value_date", "source_revision", "proof_recipe_id"],
)
def test_string_field_wrong_type_is_refused(tmp_path: Path, field: str) -> None:
    """An int where a string is required -- ``_require_str``'s own ``isinstance`` guard."""
    raw = dict(_VALID_RAW, **{field: 42})
    with pytest.raises(FinalityConfigError, match=field):
        load_finality_config(_write(tmp_path, raw))


@pytest.mark.parametrize(
    "field",
    ["currency", "value_date", "source_revision", "proof_recipe_id"],
)
def test_string_field_blank_is_refused(tmp_path: Path, field: str) -> None:
    """A blank/whitespace-only string is not a concrete value either."""
    raw = dict(_VALID_RAW, **{field: "   "})
    with pytest.raises(FinalityConfigError, match=field):
        load_finality_config(_write(tmp_path, raw))


def test_an_absent_witness_key_is_the_store_derived_default(tmp_path: Path) -> None:
    """No key at all ⇒ ``witness is None`` — today's behaviour, not a missing value."""
    config = load_finality_config(_write(tmp_path, _VALID_RAW))
    assert config.witness is None


def test_the_venue_ledger_token_selects_that_witness(tmp_path: Path) -> None:
    """The ONE recognized value decodes to the ONE enum member."""
    raw = dict(_VALID_RAW, witness="synthetic_venue_ledger")
    config = load_finality_config(_write(tmp_path, raw))
    assert config.witness is PostTradeWitnessKind.SYNTHETIC_VENUE_LEDGER


@pytest.mark.parametrize(
    "value",
    [
        "synthetic-venue-ledger",
        "synthetic_ledger",
        "SYNTHETIC_VENUE_LEDGER",
        "",
        None,
        7,
        True,
    ],
)
def test_an_unrecognized_witness_value_refuses_the_load(
    tmp_path: Path, value: object
) -> None:
    """A misspelling must refuse, never fall back to the store-derived witness."""
    raw = dict(_VALID_RAW, witness=value)
    with pytest.raises(FinalityConfigError, match="witness"):
        load_finality_config(_write(tmp_path, raw))


def test_the_shipped_example_file_carries_no_witness_key() -> None:
    """``finality.example.yaml`` ships the key COMMENTED OUT (plan §4 P2: "shipped trees OFF")."""
    example = Path(__file__).resolve().parents[2] / "config" / "finality.example.yaml"
    raw = yaml.safe_load(example.read_text(encoding="utf-8"))
    assert "witness" not in raw
    assert "witness: synthetic_venue_ledger" in example.read_text(encoding="utf-8")
