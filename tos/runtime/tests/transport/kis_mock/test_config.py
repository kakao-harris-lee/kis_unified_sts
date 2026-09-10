"""``KisMockTransportConfig`` loader tests (plan §4 슬라이스 T1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.transport.kis_mock.config import (
    KisMockTransportConfigError,
    load_kis_mock_transport_config,
)

MOCK_REST_BASE = "https://openapivts.koreainvestment.com:29443"
REAL_REST_BASE = "https://openapi.koreainvestment.com:9443"


def _valid_raw() -> dict[str, Any]:
    return {
        "mode": "dry_run",
        "endpoint_rest_base": MOCK_REST_BASE,
        "order_path": "/uapi/domestic-stock/v1/trading/order-cash",
        "token_path": "/oauth2/tokenP",
        "tr_id_buy": "VTTC0012U",
        "tr_id_sell": "VTTC0011U",
        "field_map": {
            "account": "CANO",
            "instrument": "PDNO",
            "quantity": "ORD_QTY",
            "price": "ORD_UNPR",
        },
        "min_send_interval_ms": 1100,
        "token_reissue_min_interval_s": 60,
        "request_timeout_s": 5.0,
        "allow_plaintext_for_tests": False,
    }


def _write(tmp_path: Path, raw: dict[str, Any]) -> Path:
    path = tmp_path / "kis_mock_transport.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def _load(path: Path, **overrides: Any):
    kwargs = {
        "instance_mock_rest_base": MOCK_REST_BASE,
        "instance_real_rest_base": REAL_REST_BASE,
    }
    kwargs.update(overrides)
    return load_kis_mock_transport_config(path, **kwargs)


def test_a_fully_valued_config_loads(tmp_path: Path) -> None:
    path = _write(tmp_path, _valid_raw())
    config = _load(path)
    assert config.mode == "dry_run"
    assert config.endpoint_rest_base == MOCK_REST_BASE
    assert config.tr_id_buy == "VTTC0012U"
    assert config.field_map == _valid_raw()["field_map"]


def test_missing_file_refuses(tmp_path: Path) -> None:
    with pytest.raises(KisMockTransportConfigError, match="not found"):
        _load(tmp_path / "absent.yaml")


def test_not_a_mapping_refuses(tmp_path: Path) -> None:
    path = tmp_path / "kis_mock_transport.yaml"
    path.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(KisMockTransportConfigError, match="top-level mapping"):
        _load(path)


@pytest.mark.parametrize(
    "field",
    [
        "mode",
        "endpoint_rest_base",
        "order_path",
        "token_path",
        "tr_id_buy",
        "tr_id_sell",
        "field_map",
        "min_send_interval_ms",
        "token_reissue_min_interval_s",
        "request_timeout_s",
        "allow_plaintext_for_tests",
    ],
)
def test_a_null_named_tbd_field_refuses(tmp_path: Path, field: str) -> None:
    raw = _valid_raw()
    raw[field] = None
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="named-TBD"):
        _load(path)


@pytest.mark.parametrize(
    "field",
    [
        "mode",
        "endpoint_rest_base",
        "order_path",
        "token_path",
        "tr_id_buy",
        "tr_id_sell",
        "min_send_interval_ms",
        "token_reissue_min_interval_s",
        "request_timeout_s",
        "allow_plaintext_for_tests",
        "field_map",
    ],
)
def test_an_absent_field_refuses(tmp_path: Path, field: str) -> None:
    raw = _valid_raw()
    del raw[field]
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="missing entry"):
        _load(path)


def test_mode_outside_the_two_valid_values_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["mode"] = "live_fire"
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="mode"):
        _load(path)


def test_mode_live_loads(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["mode"] = "live"
    path = _write(tmp_path, raw)
    config = _load(path)
    assert config.mode == "live"


def test_endpoint_not_matching_the_mock_instance_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["endpoint_rest_base"] = "https://not-the-mock-host.example:1234"
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="does not byte-exact match"):
        _load(path)


def test_endpoint_matching_the_real_instance_refuses_even_if_named_mock(
    tmp_path: Path,
) -> None:
    raw = _valid_raw()
    raw["endpoint_rest_base"] = REAL_REST_BASE
    path = _write(tmp_path, raw)
    # instance_mock_rest_base deliberately set to the real host too, to isolate the
    # real-host refusal from the "does not match mock" refusal.
    with pytest.raises(KisMockTransportConfigError, match="REAL_PROD"):
        _load(path, instance_mock_rest_base=REAL_REST_BASE)


def test_endpoint_matching_real_refuses_even_with_no_real_base_known(
    tmp_path: Path,
) -> None:
    """instance_real_rest_base=None must not vacuously admit a real-looking host — this test
    just proves the mock-mismatch check alone (not the real-equality check) already refuses,
    since None disables only the second, additional guard."""
    raw = _valid_raw()
    raw["endpoint_rest_base"] = REAL_REST_BASE
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="does not byte-exact match"):
        _load(path, instance_real_rest_base=None)


def test_http_scheme_without_plaintext_flag_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["endpoint_rest_base"] = "http://127.0.0.1:8443"
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="allow_plaintext_for_tests"):
        _load(path, instance_mock_rest_base="http://127.0.0.1:8443")


def test_http_scheme_with_plaintext_flag_loads(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["endpoint_rest_base"] = "http://127.0.0.1:8443"
    raw["allow_plaintext_for_tests"] = True
    path = _write(tmp_path, raw)
    config = _load(path, instance_mock_rest_base="http://127.0.0.1:8443")
    assert config.allow_plaintext_for_tests is True


def test_unsupported_scheme_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["endpoint_rest_base"] = "ftp://127.0.0.1:21"
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="unsupported scheme"):
        _load(path, instance_mock_rest_base="ftp://127.0.0.1:21")


@pytest.mark.parametrize("field", ["tr_id_buy", "tr_id_sell"])
@pytest.mark.parametrize(
    ("value", "match"),
    [
        ("TTTC0012U", "real-order"),
        ("STTN1101U", "real-order"),
        ("CTFO6118R", "real-order"),
        ("XTTC0012U", "must start with 'V'"),
    ],
)
def test_a_non_v_prefixed_tr_id_refuses(
    tmp_path: Path, field: str, value: str, match: str
) -> None:
    raw = _valid_raw()
    raw[field] = value
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match=match):
        _load(path)


def test_field_map_naming_an_unrecognized_source_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["field_map"] = {"side": "SLL_BUY_DVSN_CD"}
    path = _write(tmp_path, raw)
    with pytest.raises(
        KisMockTransportConfigError, match="unrecognized dynamic source"
    ):
        _load(path)


def test_field_map_with_a_null_value_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["field_map"] = {"account": None}
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="named-TBD"):
        _load(path)


def test_field_map_colliding_wire_names_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["field_map"] = {"account": "CANO", "instrument": "CANO"}
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="same KIS wire field name"):
        _load(path)


@pytest.mark.parametrize(
    "field",
    ["min_send_interval_ms", "token_reissue_min_interval_s", "request_timeout_s"],
)
def test_a_non_positive_numeric_field_refuses(tmp_path: Path, field: str) -> None:
    raw = _valid_raw()
    raw[field] = 0
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="positive"):
        _load(path)


def test_a_non_int_min_send_interval_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["min_send_interval_ms"] = 1100.5
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="must be an int"):
        _load(path)


def test_a_non_bool_allow_plaintext_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["allow_plaintext_for_tests"] = "false"
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="must be a bool"):
        _load(path)


def test_the_example_config_file_matches_this_loaders_shape() -> None:
    """The shipped example config (deliverable B) must parse with every field present and
    named-TBD null (except mode/allow_plaintext_for_tests/field_map's keys) — this is the one
    test that would catch the example config and this loader drifting apart."""
    example_path = (
        Path(__file__).resolve().parents[3]
        / "config"
        / "kis_mock_transport.example.yaml"
    )
    raw = yaml.safe_load(example_path.read_text(encoding="utf-8"))
    assert raw["mode"] == "dry_run"
    assert raw["allow_plaintext_for_tests"] is False
    assert raw["endpoint_rest_base"] is None
    assert raw["order_path"] is None
    assert raw["token_path"] is None
    assert raw["tr_id_buy"] is None
    assert raw["tr_id_sell"] is None
    assert raw["min_send_interval_ms"] is None
    assert raw["token_reissue_min_interval_s"] is None
    assert raw["request_timeout_s"] is None
    assert isinstance(raw["field_map"], dict) and raw["field_map"]
    assert all(value is None for value in raw["field_map"].values())
    with pytest.raises(KisMockTransportConfigError, match="named-TBD"):
        load_kis_mock_transport_config(
            example_path,
            instance_mock_rest_base=MOCK_REST_BASE,
            instance_real_rest_base=REAL_REST_BASE,
        )
