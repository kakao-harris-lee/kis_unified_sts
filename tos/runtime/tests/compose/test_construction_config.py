"""``tos_runtime.compose._construction_config`` tests (TOS ``run`` 구동 아크 plan
``docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`` §4 W1 lane A).

Hermetic — real config files under ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos.venue import ActionClass
from tos_runtime.compose._construction_config import (
    ConstructionConfigError,
    load_construction_config,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _valid_content() -> dict:
    return {
        "account": "acct-1",
        "instrument": "ES",
        "action_class": "NEW_LONG",
        "instrument_class": "krx-index-futures",
        "outbound_side": "BUY",
        "price_field_key": "close",
        "shape_price_field_key": "close",
    }


def _write(path: Path, content: dict) -> None:
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


def test_a_valid_file_loads_with_price_always_none(tmp_path: Path) -> None:
    path = tmp_path / "construction.yaml"
    _write(path, _valid_content())

    config = load_construction_config(path)

    assert config.account == "acct-1"
    assert config.instrument == "ES"
    assert config.action_class is ActionClass.NEW_LONG
    assert config.instrument_class == "krx-index-futures"
    assert config.outbound_side == "BUY"
    assert config.price_field_key == "close"
    assert config.shape_price_field_key == "close"
    # Plan §2 decision 2, binding: the loader never expresses `price`.
    assert config.price is None


def test_missing_file_refuses_to_load(tmp_path: Path) -> None:
    with pytest.raises(ConstructionConfigError):
        load_construction_config(tmp_path / "does-not-exist.yaml")


def test_not_a_mapping_refuses_to_load(tmp_path: Path) -> None:
    path = tmp_path / "construction.yaml"
    path.write_text(yaml.safe_dump(["not", "a", "mapping"]), encoding="utf-8")
    with pytest.raises(ConstructionConfigError):
        load_construction_config(path)


def test_not_valid_yaml_refuses_to_load(tmp_path: Path) -> None:
    path = tmp_path / "construction.yaml"
    path.write_text("{unbalanced: [", encoding="utf-8")
    with pytest.raises(ConstructionConfigError):
        load_construction_config(path)


@pytest.mark.parametrize(
    "key",
    [
        "account",
        "instrument",
        "action_class",
        "instrument_class",
        "outbound_side",
        "price_field_key",
        "shape_price_field_key",
    ],
)
def test_missing_key_refuses_to_load(tmp_path: Path, key: str) -> None:
    content = _valid_content()
    del content[key]
    path = tmp_path / "construction.yaml"
    _write(path, content)
    with pytest.raises(ConstructionConfigError):
        load_construction_config(path)


@pytest.mark.parametrize(
    "key",
    [
        "account",
        "instrument",
        "action_class",
        "instrument_class",
        "outbound_side",
        "price_field_key",
        "shape_price_field_key",
    ],
)
def test_null_value_refuses_to_load_named_tbd(tmp_path: Path, key: str) -> None:
    content = _valid_content()
    content[key] = None
    path = tmp_path / "construction.yaml"
    _write(path, content)
    with pytest.raises(ConstructionConfigError):
        load_construction_config(path)


@pytest.mark.parametrize(
    "key",
    [
        "account",
        "instrument",
        "action_class",
        "instrument_class",
        "outbound_side",
        "price_field_key",
        "shape_price_field_key",
    ],
)
def test_literal_tbd_string_refuses_to_load(tmp_path: Path, key: str) -> None:
    content = _valid_content()
    content[key] = "TBD"
    path = tmp_path / "construction.yaml"
    _write(path, content)
    with pytest.raises(ConstructionConfigError):
        load_construction_config(path)


def test_invalid_action_class_refuses_to_load(tmp_path: Path) -> None:
    content = _valid_content()
    content["action_class"] = "NOT_A_REAL_ACTION_CLASS"
    path = tmp_path / "construction.yaml"
    _write(path, content)
    with pytest.raises(ConstructionConfigError):
        load_construction_config(path)


def test_unrecognized_top_level_key_refuses_to_load(tmp_path: Path) -> None:
    content = _valid_content()
    content["some_typo_field"] = "value"
    path = tmp_path / "construction.yaml"
    _write(path, content)
    with pytest.raises(ConstructionConfigError):
        load_construction_config(path)


def test_wrong_type_refuses_to_load(tmp_path: Path) -> None:
    content = _valid_content()
    content["account"] = 12345
    path = tmp_path / "construction.yaml"
    _write(path, content)
    with pytest.raises(ConstructionConfigError):
        load_construction_config(path)


def test_shipped_example_file_is_all_null_and_therefore_refuses(
    tmp_path: Path,
) -> None:
    """The shipped ``construction.example.yaml`` is a template, not an approved config — every
    leaf ``null`` means it must refuse to load as-is (module docstring)."""
    example_path = (
        Path(__file__).resolve().parents[2] / "config" / "construction.example.yaml"
    )
    with pytest.raises(ConstructionConfigError):
        load_construction_config(example_path)
