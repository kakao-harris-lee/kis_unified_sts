"""``KisQuoteTransportConfig`` loader tests (TOS tick-source wave, W2 lane)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.transport.kis_quote.config import (
    KisQuoteTransportConfigError,
    load_kis_quote_transport_config,
)

MOCK_REST_BASE = "https://openapivts.koreainvestment.com:29443"
REAL_REST_BASE = "https://openapi.koreainvestment.com:9443"


def _valid_raw() -> dict[str, Any]:
    return {
        "endpoint_rest_base": MOCK_REST_BASE,
        "allow_plaintext_for_tests": False,
        "quote_path": "/uapi/domestic-stock/v1/quotations/inquire-price",
        "tr_id": "FHKST01010100",
        "market_div_code": "J",
        "instrument": "005930",
        "token_path": "/oauth2/tokenP",
        "token_reissue_min_interval_s": 60,
        "field_mapping": {"stck_prpr": "last_price", "acml_vol": "volume"},
        "source_id": "kis_quote_mock_stock",
        "request_timeout_s": 3.0,
    }


def _write(tmp_path: Path, raw: dict[str, Any]) -> Path:
    path = tmp_path / "kis_quote.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def _load(path: Path, **overrides: Any):
    kwargs: dict[str, Any] = {
        "instance_mock_rest_base": MOCK_REST_BASE,
        "instance_real_rest_base": REAL_REST_BASE,
    }
    kwargs.update(overrides)
    return load_kis_quote_transport_config(path, **kwargs)


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_a_fully_valued_config_loads(tmp_path: Path) -> None:
    path = _write(tmp_path, _valid_raw())
    config = _load(path)
    assert config.endpoint_rest_base == MOCK_REST_BASE
    assert config.tr_id == "FHKST01010100"
    assert config.instrument == "005930"
    assert config.market_div_code == "J"
    assert config.field_mapping == {"stck_prpr": "last_price", "acml_vol": "volume"}
    assert config.source_id == "kis_quote_mock_stock"
    assert config.token_reissue_min_interval_s == 60
    assert config.request_timeout_s == 3.0


def test_futures_tr_id_shape_also_accepted(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["tr_id"] = "FHMIF10000000"
    raw["market_div_code"] = "F"
    path = _write(tmp_path, raw)
    config = _load(path)
    assert config.tr_id == "FHMIF10000000"


# ---------------------------------------------------------------------------
# structural refusals
# ---------------------------------------------------------------------------


def test_missing_file_refuses(tmp_path: Path) -> None:
    with pytest.raises(KisQuoteTransportConfigError, match="not found"):
        _load(tmp_path / "absent.yaml")


def test_not_a_mapping_refuses(tmp_path: Path) -> None:
    path = tmp_path / "kis_quote.yaml"
    path.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(KisQuoteTransportConfigError, match="top-level mapping"):
        _load(path)


def test_not_valid_yaml_refuses(tmp_path: Path) -> None:
    path = tmp_path / "kis_quote.yaml"
    path.write_text("{unclosed: [1, 2\n", encoding="utf-8")
    with pytest.raises(KisQuoteTransportConfigError, match="not valid YAML"):
        _load(path)


@pytest.mark.parametrize(
    "field",
    [
        "endpoint_rest_base",
        "allow_plaintext_for_tests",
        "quote_path",
        "tr_id",
        "market_div_code",
        "instrument",
        "token_path",
        "token_reissue_min_interval_s",
        "field_mapping",
        "source_id",
        "request_timeout_s",
    ],
)
def test_still_null_field_refuses(tmp_path: Path, field: str) -> None:
    raw = _valid_raw()
    raw[field] = None
    path = _write(tmp_path, raw)
    with pytest.raises(KisQuoteTransportConfigError, match="named-TBD"):
        _load(path)


@pytest.mark.parametrize(
    "field",
    [
        "endpoint_rest_base",
        "allow_plaintext_for_tests",
        "quote_path",
        "tr_id",
        "market_div_code",
        "instrument",
        "token_path",
        "token_reissue_min_interval_s",
        "field_mapping",
        "source_id",
        "request_timeout_s",
    ],
)
def test_missing_field_refuses(tmp_path: Path, field: str) -> None:
    raw = _valid_raw()
    del raw[field]
    path = _write(tmp_path, raw)
    with pytest.raises(KisQuoteTransportConfigError, match="missing entry"):
        _load(path)


# ---------------------------------------------------------------------------
# host seal (module docstring — structural, not documentation)
# ---------------------------------------------------------------------------


def test_endpoint_matching_real_domain_refuses_even_though_field_is_present(
    tmp_path: Path,
) -> None:
    raw = _valid_raw()
    raw["endpoint_rest_base"] = REAL_REST_BASE
    path = _write(tmp_path, raw)
    with pytest.raises(KisQuoteTransportConfigError, match="REAL_PROD"):
        _load(path)


def test_endpoint_not_matching_mock_instance_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["endpoint_rest_base"] = "https://attacker.invalid"
    path = _write(tmp_path, raw)
    with pytest.raises(KisQuoteTransportConfigError, match="does not byte-exact match"):
        _load(path)


def test_instance_real_rest_base_none_refuses(tmp_path: Path) -> None:
    # A caller that cannot state the REAL host cannot honestly exclude it — this is a
    # programming-contract violation (the type says str), so exercised via a direct call that
    # bypasses the type checker, mirroring kis_mock/test_config.py's own equivalent test.
    path = _write(tmp_path, _valid_raw())
    with pytest.raises(
        KisQuoteTransportConfigError, match="REAL rest_base must be known"
    ):
        load_kis_quote_transport_config(
            path,
            instance_mock_rest_base=MOCK_REST_BASE,
            instance_real_rest_base=None,  # type: ignore[arg-type]
        )


def test_mock_and_real_instance_identical_refuses(tmp_path: Path) -> None:
    path = _write(tmp_path, _valid_raw())
    with pytest.raises(KisQuoteTransportConfigError, match="must differ"):
        _load(path, instance_real_rest_base=MOCK_REST_BASE)


def test_plaintext_scheme_without_the_test_flag_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["endpoint_rest_base"] = "http://127.0.0.1:1"
    path = _write(tmp_path, raw)
    with pytest.raises(KisQuoteTransportConfigError, match="allow_plaintext_for_tests"):
        _load(path, instance_mock_rest_base="http://127.0.0.1:1")


# ---------------------------------------------------------------------------
# TR id shape (module docstring — measured, not the order transport's V-prefix rule)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_tr_id",
    [
        "VTTC0012U",  # order transport's own shape — a different TR family entirely
        "TTTC0011U",  # real-order shape
        "FHKST0101010",  # one digit too many
        "fhkst01010100",  # lowercase — case-sensitive
        "FH0101010",  # missing the 3-letter segment
    ],
)
def test_non_conforming_tr_id_refuses(tmp_path: Path, bad_tr_id: str) -> None:
    raw = _valid_raw()
    raw["tr_id"] = bad_tr_id
    path = _write(tmp_path, raw)
    with pytest.raises(KisQuoteTransportConfigError, match="quotations TR id shape"):
        _load(path)


# ---------------------------------------------------------------------------
# field_mapping
# ---------------------------------------------------------------------------


def test_named_tbd_placeholder_instrument_refuses(tmp_path: Path) -> None:
    """W-A A-0 round 2 (kernel round #4 재심 BLOCKER): this file's own stdlib-only
    firewall discipline means it duplicates the ``"TBD"`` literal locally rather than
    importing ``tos_runtime._named_tbd`` — pin that the local check actually fires."""
    raw = _valid_raw()
    raw["instrument"] = "TBD"
    path = _write(tmp_path, raw)
    with pytest.raises(KisQuoteTransportConfigError, match="template placeholder"):
        _load(path)


def test_named_tbd_placeholder_field_mapping_value_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["field_mapping"] = {"stck_prpr": "TBD"}
    path = _write(tmp_path, raw)
    with pytest.raises(KisQuoteTransportConfigError, match="template placeholder"):
        _load(path)


def test_empty_field_mapping_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["field_mapping"] = {}
    path = _write(tmp_path, raw)
    with pytest.raises(KisQuoteTransportConfigError, match="non-empty mapping"):
        _load(path)


def test_field_mapping_with_non_string_value_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["field_mapping"] = {"stck_prpr": None}
    path = _write(tmp_path, raw)
    with pytest.raises(KisQuoteTransportConfigError, match="field_mapping"):
        _load(path)


def test_negative_or_zero_token_reissue_interval_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["token_reissue_min_interval_s"] = 0
    path = _write(tmp_path, raw)
    with pytest.raises(KisQuoteTransportConfigError, match="positive"):
        _load(path)


def test_negative_request_timeout_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["request_timeout_s"] = -1.0
    path = _write(tmp_path, raw)
    with pytest.raises(KisQuoteTransportConfigError, match="positive"):
        _load(path)


# ---------------------------------------------------------------------------
# shipped example (W2 lane review finding — LOW: no test ever loaded this file)
# ---------------------------------------------------------------------------


def test_shipped_example_file_is_all_null_and_therefore_refuses() -> None:
    """``kis_quote.example.yaml`` is a template, not an approved config — every leaf is
    ``null`` (named-TBD), so loading it as-shipped must refuse (module docstring's own "still-null
    or missing required leaf is a fail-closed refusal at load" note). Mirrors
    ``test_construction_config.py``'s ``test_shipped_example_file_is_all_null_and_therefore_refuses``.

    Nothing else in this suite ever reads the shipped example file itself — every other test
    here writes its own synthetic ``kis_quote.yaml`` via ``_write``/``_valid_raw``. This is the
    ONE test that would catch a required key added to the loader without the example being kept
    in sync (a missing key in ``marketfeed.example.yaml`` went unnoticed by hand for exactly this
    reason before this test existed)."""
    example_path = (
        Path(__file__).resolve().parents[3] / "config" / "kis_quote.example.yaml"
    )
    assert (
        example_path.is_file()
    ), "fixture assumption: the example file ships at this path"
    with pytest.raises(KisQuoteTransportConfigError):
        _load(example_path)
