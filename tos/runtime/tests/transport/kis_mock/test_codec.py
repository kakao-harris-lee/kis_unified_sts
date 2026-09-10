"""``KisOrderWireCodec`` tests (review disposition F1).

Written red-first: before ``codec.py`` existed, every test below failed on import. These pin
the codec's exact serialization recipe so a future T2 binding (the compose context resolver)
can reproduce it byte-for-byte (review instruction: "report the codec's exact serialization
recipe so T2 can bind to it")."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

import pytest
from tos_runtime.transport.kis_mock.codec import (
    KIS_ORDER_CASH_WIRE_FIELDS,
    KisOrderWireCodec,
    KisOrderWireCodecError,
)

from ._seal_fixtures import build_seal

FIELD_MAP = {
    "account": "CANO",
    "instrument": "PDNO",
    "quantity": "ORD_QTY",
    "price": "ORD_UNPR",
}
STATIC_FIELDS = {
    "ACNT_PRDT_CD": "01",
    "ORD_DVSN": "00",
    "EXCG_ID_DVSN_CD": "KRX",
    "SLL_TYPE": "",
    "CNDT_PRIC": "",
}


def test_kis_order_cash_wire_fields_is_exactly_the_nine_n17_fields() -> None:
    assert (
        frozenset(
            {
                "CANO",
                "ACNT_PRDT_CD",
                "PDNO",
                "ORD_DVSN",
                "ORD_QTY",
                "ORD_UNPR",
                "EXCG_ID_DVSN_CD",
                "SLL_TYPE",
                "CNDT_PRIC",
            }
        )
        == KIS_ORDER_CASH_WIRE_FIELDS
    )


def test_encode_produces_deterministic_sorted_no_whitespace_json() -> None:
    seal = build_seal(
        field_map=FIELD_MAP,
        static_body_fields=STATIC_FIELDS,
        account="12345678",
        instrument="005930",
        quantity=Decimal("10"),
        price=Decimal("70000"),
    )
    body = KisOrderWireCodec.encode(
        seal, field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS
    )
    expected = json.dumps(
        {
            "CANO": "12345678",
            "PDNO": "005930",
            "ORD_QTY": "10",
            "ORD_UNPR": "70000",
            "ACNT_PRDT_CD": "01",
            "ORD_DVSN": "00",
            "EXCG_ID_DVSN_CD": "KRX",
            "SLL_TYPE": "",
            "CNDT_PRIC": "",
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    assert body == expected
    # No incidental whitespace anywhere.
    assert b" " not in body


def test_encode_is_a_pure_function_of_its_inputs() -> None:
    seal = build_seal(field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS)
    first = KisOrderWireCodec.encode(
        seal, field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS
    )
    second = KisOrderWireCodec.encode(
        seal, field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS
    )
    assert first == second


def test_digest_is_sha256_hex() -> None:
    body = b'{"x":"y"}'
    assert KisOrderWireCodec.digest(body) == hashlib.sha256(body).hexdigest()


def test_account_is_read_from_the_sealed_account_coordinate() -> None:
    """(F2) The 'account' dynamic source is ``seal.account`` — the sealed outbound
    coordinate — never a custody-loaded value and never ``instrument_key.account``."""
    seal = build_seal(
        field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS, account="acct-from-seal"
    )
    body = KisOrderWireCodec.encode(
        seal, field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS
    )
    decoded = json.loads(body)
    assert decoded["CANO"] == "acct-from-seal" == seal.account


def test_missing_a_required_field_refuses() -> None:
    # Build a seal using a VALID field_map/static_body_fields (so seal construction itself
    # succeeds) — the broken map is exercised only against the encode() call under test.
    seal = build_seal(field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS)
    incomplete_static = dict(STATIC_FIELDS)
    del incomplete_static["CNDT_PRIC"]
    with pytest.raises(KisOrderWireCodecError, match="missing"):
        KisOrderWireCodec.encode(
            seal, field_map=FIELD_MAP, static_body_fields=incomplete_static
        )


def test_an_unexpected_extra_field_refuses() -> None:
    seal = build_seal(field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS)
    extra_static = dict(STATIC_FIELDS)
    extra_static["EXTRA_FIELD"] = "x"
    with pytest.raises(KisOrderWireCodecError, match="unexpected"):
        KisOrderWireCodec.encode(
            seal, field_map=FIELD_MAP, static_body_fields=extra_static
        )


def test_an_unrecognized_dynamic_source_refuses() -> None:
    seal = build_seal(field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS)
    bad_field_map = {"side": "SLL_BUY_DVSN_CD"}
    with pytest.raises(KisOrderWireCodecError, match="unrecognized"):
        KisOrderWireCodec.encode(
            seal, field_map=bad_field_map, static_body_fields=STATIC_FIELDS
        )


def test_quantity_and_price_are_plain_decimal_strings_never_scientific_notation() -> (
    None
):
    seal = build_seal(
        field_map=FIELD_MAP,
        static_body_fields=STATIC_FIELDS,
        quantity=Decimal("100"),
        price=Decimal("0.0001"),
    )
    body = KisOrderWireCodec.encode(
        seal, field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS
    )
    decoded = json.loads(body)
    assert decoded["ORD_QTY"] == "100"
    assert decoded["ORD_UNPR"] == "0.0001"
    assert "E" not in decoded["ORD_UNPR"] and "e" not in decoded["ORD_UNPR"]
