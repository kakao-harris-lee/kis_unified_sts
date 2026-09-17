"""``load_kis_witness_config`` tests — host seal, TR-id shape, named-TBD, futures refusal
(mirrors ``tos/runtime/tests/transport/kis_mock/test_config.py``'s own shape for the
sibling order-transport config)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from tos_runtime.recon.witness_kis_config import (
    FuturesAssetRefused,
    KisWitnessConfigError,
    load_kis_witness_config,
    refuse_futures_asset,
)

MOCK_BASE = "https://openapivts.koreainvestment.com:29443"
REAL_BASE = "https://openapi.koreainvestment.com:9443"


def _write(path: Path, **overrides: Any) -> Path:
    base = {
        "endpoint_rest_base": MOCK_BASE,
        "balance_path": "/uapi/domestic-stock/v1/trading/inquire-balance",
        "balance_tr_id": "VTTC8434R",
        "order_inquiry_path": "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
        "order_inquiry_tr_id": "VTTC0081R",
        "request_timeout_s": 5.0,
        "max_pages": 10,
        "allow_plaintext_for_tests": False,
    }
    base.update(overrides)
    lines = []
    for key, value in base.items():
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f'{key}: "{value}"')
    file_path = path / "kis_witness.yaml"
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return file_path


def _load(path: Path) -> Any:
    return load_kis_witness_config(
        path, instance_mock_rest_base=MOCK_BASE, instance_real_rest_base=REAL_BASE
    )


def test_a_fully_valued_config_loads(tmp_path: Path) -> None:
    cfg = _load(_write(tmp_path))
    assert cfg.endpoint_rest_base == MOCK_BASE
    assert cfg.balance_tr_id == "VTTC8434R"
    assert cfg.order_inquiry_tr_id == "VTTC0081R"
    assert cfg.max_pages == 10


def test_endpoint_must_match_the_mock_instance_exactly(tmp_path: Path) -> None:
    path = _write(tmp_path, endpoint_rest_base="https://not-the-mock-host:1234")
    with pytest.raises(KisWitnessConfigError, match="does not byte-exact match"):
        _load(path)


def test_endpoint_matching_the_real_instance_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, endpoint_rest_base=REAL_BASE)
    with pytest.raises(KisWitnessConfigError, match="REAL_PROD"):
        _load(path)


def test_a_config_cannot_smuggle_a_real_order_balance_tr_id(tmp_path: Path) -> None:
    path = _write(tmp_path, balance_tr_id="TTTC8434R")
    with pytest.raises(KisWitnessConfigError, match="real-order"):
        _load(path)


def test_a_config_cannot_smuggle_a_real_order_inquiry_tr_id(tmp_path: Path) -> None:
    path = _write(tmp_path, order_inquiry_tr_id="TTTC0081R")
    with pytest.raises(KisWitnessConfigError, match="real-order"):
        _load(path)


def test_a_malformed_tr_id_shape_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, balance_tr_id="NOTASHAPE")
    with pytest.raises(KisWitnessConfigError, match="TR id shape"):
        _load(path)


def test_a_named_tbd_null_field_refuses_to_load(tmp_path: Path) -> None:
    path = _write(tmp_path, request_timeout_s=None)
    with pytest.raises(KisWitnessConfigError, match="named-TBD"):
        _load(path)


def test_max_pages_must_be_positive(tmp_path: Path) -> None:
    path = _write(tmp_path, max_pages=0)
    with pytest.raises(KisWitnessConfigError, match="positive"):
        _load(path)


def test_plaintext_http_requires_the_test_only_flag(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        endpoint_rest_base="http://127.0.0.1:1",
        allow_plaintext_for_tests=False,
    )
    # http:// also fails the mock-host-match check first — assert on the actual error
    # this loader raises, not a guessed one.
    with pytest.raises(KisWitnessConfigError):
        _load(path)


def test_instance_real_rest_base_none_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path)
    with pytest.raises(KisWitnessConfigError, match="REAL rest_base must be known"):
        load_kis_witness_config(
            path, instance_mock_rest_base=MOCK_BASE, instance_real_rest_base=None
        )


def test_refuse_futures_asset_accepts_stock() -> None:
    refuse_futures_asset("stock")  # does not raise


def test_refuse_futures_asset_rejects_futures() -> None:
    with pytest.raises(FuturesAssetRefused, match="never funded"):
        refuse_futures_asset("futures")


def test_refuse_futures_asset_rejects_anything_else() -> None:
    with pytest.raises(FuturesAssetRefused):
        refuse_futures_asset("bond")
