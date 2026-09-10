"""``KisMockTransportConfig`` loader tests (plan §4 슬라이스 T1; review disposition F1/F3/F7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.transport.kis_mock.codec import KIS_ORDER_CASH_WIRE_FIELDS
from tos_runtime.transport.kis_mock.config import (
    KisMockTransportConfigError,
    load_kis_mock_transport_config,
)

MOCK_REST_BASE = "https://openapivts.koreainvestment.com:29443"
REAL_REST_BASE = "https://openapi.koreainvestment.com:9443"

STATIC_BODY_FIELDS = {
    "ACNT_PRDT_CD": "01",
    "ORD_DVSN": "00",
    "EXCG_ID_DVSN_CD": "KRX",
    "SLL_TYPE": "",
    "CNDT_PRIC": "",
}


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
        "static_body_fields": dict(STATIC_BODY_FIELDS),
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
    kwargs: dict[str, Any] = {
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
    assert config.static_body_fields == STATIC_BODY_FIELDS
    # The config's own combined coverage must equal the codec's own required field set — this
    # is the one test that would catch the two frozensets (config.py's local copy and codec.py's
    # own) drifting apart (config.py deliberately does not import codec.py — see config.py's
    # own module docstring on why it stays stdlib-only).
    combined = set(config.field_map.values()) | set(config.static_body_fields.keys())
    assert combined == KIS_ORDER_CASH_WIRE_FIELDS


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
        "static_body_fields",
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
        "static_body_fields",
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


def test_mode_live_always_refuses(tmp_path: Path) -> None:
    """(review F1/F6) ``live`` is unconditionally refused until T2 binds
    ``KisOrderWireCodec`` into the compose context resolver's ``capsule_egress_request_digest``
    — see ``codec.py``'s own module docstring for exactly why a real send would otherwise
    always hit a digest mismatch today."""
    raw = _valid_raw()
    raw["mode"] = "live"
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="seal-codec binding"):
        _load(path)


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
    # instance_mock_rest_base deliberately set to a THIRD host (not equal to instance_real_
    # rest_base — that combination is refused separately, see
    # test_instance_mock_and_real_rest_base_must_differ) to isolate the real-host refusal from
    # the "does not match mock" refusal.
    with pytest.raises(KisMockTransportConfigError, match="REAL_PROD"):
        _load(path, instance_mock_rest_base="https://a-third-host.example:1")


def test_instance_real_rest_base_none_refuses(tmp_path: Path) -> None:
    """(review F3) ``instance_real_rest_base`` is now REQUIRED — ``None`` must not vacuously
    admit a real-looking host by disabling the check."""
    path = _write(tmp_path, _valid_raw())
    with pytest.raises(
        KisMockTransportConfigError, match="REAL rest_base must be known"
    ):
        _load(path, instance_real_rest_base=None)


def test_instance_mock_and_real_rest_base_must_differ(tmp_path: Path) -> None:
    """(review F3) A caller passing the same value for both instance facts can never be
    honestly excluding the real host — refuse rather than silently accepting."""
    path = _write(tmp_path, _valid_raw())
    with pytest.raises(KisMockTransportConfigError, match="must differ"):
        _load(
            path,
            instance_mock_rest_base=MOCK_REST_BASE,
            instance_real_rest_base=MOCK_REST_BASE,
        )


def test_http_scheme_without_plaintext_flag_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["endpoint_rest_base"] = "http://127.0.0.1:8443"
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="allow_plaintext_for_tests"):
        _load(
            path,
            instance_mock_rest_base="http://127.0.0.1:8443",
            instance_real_rest_base=REAL_REST_BASE,
        )


def test_http_scheme_with_plaintext_flag_loads(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["endpoint_rest_base"] = "http://127.0.0.1:8443"
    raw["allow_plaintext_for_tests"] = True
    path = _write(tmp_path, raw)
    config = _load(
        path,
        instance_mock_rest_base="http://127.0.0.1:8443",
        instance_real_rest_base=REAL_REST_BASE,
    )
    assert config.allow_plaintext_for_tests is True


def test_unsupported_scheme_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["endpoint_rest_base"] = "ftp://127.0.0.1:21"
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="unsupported scheme"):
        _load(
            path,
            instance_mock_rest_base="ftp://127.0.0.1:21",
            instance_real_rest_base=REAL_REST_BASE,
        )


# ---------------------------------------------------------------------------
# TR id shape (review F7) — 'V' + 3 letters + 4 digits + 1 letter, e.g. VTTC0012U.
# Verified against the official SDK oracle: order_cash.py's own tr_id assignments
# (VTTC0011U/VTTC0012U mock, TTTC0011U/TTTC0012U real) plus the N-17 memo's further-observed
# real-order/real-night TR ids (STTN1101U, CTFO6118R) — all nine characters, 1+3+4+1 shape.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["tr_id_buy", "tr_id_sell"])
@pytest.mark.parametrize(
    ("value", "match"),
    [
        ("TTTC0012U", "real-order"),
        ("STTN1101U", "real-order"),
        ("CTFO6118R", "real-order"),
        ("XTTC0012U", "TR id shape"),
        ("VTTTC0012U", "TR id shape"),  # one extra letter -> 10 chars, shape violation
        ("VTC0012U", "TR id shape"),  # one too few letters -> 8 chars, shape violation
        ("VTTC00012U", "TR id shape"),  # one extra digit -> 10 chars, shape violation
        ("VTTC00121", "TR id shape"),  # trailing digit instead of a letter
        ("vttc0012u", "TR id shape"),  # lowercase — refused, not case-normalized
    ],
)
def test_a_malformed_tr_id_refuses(
    tmp_path: Path, field: str, value: str, match: str
) -> None:
    raw = _valid_raw()
    raw[field] = value
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match=match):
        _load(path)


def test_a_well_formed_v_prefixed_tr_id_loads(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["tr_id_buy"] = "VTTC0012U"
    raw["tr_id_sell"] = "VTTC0011U"
    path = _write(tmp_path, raw)
    config = _load(path)
    assert config.tr_id_buy == "VTTC0012U"
    assert config.tr_id_sell == "VTTC0011U"


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


def test_static_body_fields_with_a_null_value_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["static_body_fields"] = dict(STATIC_BODY_FIELDS)
    raw["static_body_fields"]["ORD_DVSN"] = None
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="named-TBD"):
        _load(path)


def test_static_body_fields_missing_a_required_kis_field_refuses(
    tmp_path: Path,
) -> None:
    """(review F1) The combined field_map + static_body_fields coverage must equal exactly the
    nine KIS order_cash fields — a missing field refuses at boot, before any network."""
    raw = _valid_raw()
    incomplete = dict(STATIC_BODY_FIELDS)
    del incomplete["CNDT_PRIC"]
    raw["static_body_fields"] = incomplete
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="missing"):
        _load(path)


def test_static_body_fields_with_an_unexpected_kis_field_refuses(
    tmp_path: Path,
) -> None:
    raw = _valid_raw()
    extra = dict(STATIC_BODY_FIELDS)
    extra["NOT_A_REAL_FIELD"] = "x"
    raw["static_body_fields"] = extra
    path = _write(tmp_path, raw)
    with pytest.raises(KisMockTransportConfigError, match="unexpected"):
        _load(path)


def test_static_body_fields_colliding_with_field_map_refuses(tmp_path: Path) -> None:
    raw = _valid_raw()
    collide = dict(STATIC_BODY_FIELDS)
    del collide["ACNT_PRDT_CD"]
    collide["CANO"] = "should-not-duplicate-field_map"
    raw["static_body_fields"] = collide
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
    named-TBD null (except mode/allow_plaintext_for_tests/field_map's and static_body_fields'
    keys) — this is the one test that would catch the example config and this loader drifting
    apart."""
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
    assert isinstance(raw["static_body_fields"], dict) and raw["static_body_fields"]
    assert all(value is None for value in raw["static_body_fields"].values())
    assert set(raw["field_map"]) == {"account", "instrument", "quantity", "price"}
    assert set(raw["static_body_fields"]) == {
        "ACNT_PRDT_CD",
        "ORD_DVSN",
        "EXCG_ID_DVSN_CD",
        "SLL_TYPE",
        "CNDT_PRIC",
    }
    with pytest.raises(KisMockTransportConfigError, match="named-TBD"):
        load_kis_mock_transport_config(
            example_path,
            instance_mock_rest_base=MOCK_REST_BASE,
            instance_real_rest_base=REAL_REST_BASE,
        )
