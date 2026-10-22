"""Tests for ``KisOrderWireCodec``.

These tests pin the exact serialization recipe so callers can reproduce the wire body
byte-for-byte."""

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
        seal, field_map=FIELD_MAP, price_scale=1, static_body_fields=STATIC_FIELDS
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
        seal, field_map=FIELD_MAP, price_scale=1, static_body_fields=STATIC_FIELDS
    )
    second = KisOrderWireCodec.encode(
        seal, field_map=FIELD_MAP, price_scale=1, static_body_fields=STATIC_FIELDS
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
        seal, field_map=FIELD_MAP, price_scale=1, static_body_fields=STATIC_FIELDS
    )
    decoded = json.loads(body)
    assert decoded["CANO"] == "acct-from-seal" == seal.account


def test_account_is_the_seal_field_never_instrument_key_account() -> None:
    """The codec must use ``seal.account`` even when
    ``instrument_key.account`` differs. Every OTHER fixture in this suite builds
    ``instrument_key.account`` equal to ``seal.account``, so a mutation swapping
    ``seal.account`` for ``seal.instrument_key.account`` inside the codec would silently
    survive every other test here."""
    seal = build_seal(
        field_map=FIELD_MAP,
        static_body_fields=STATIC_FIELDS,
        account="seal-account-value",
        instrument_key_account="different-instrument-key-account-value",
    )
    assert seal.account == "seal-account-value"
    assert seal.instrument_key.account == "different-instrument-key-account-value"
    body = KisOrderWireCodec.encode(
        seal, field_map=FIELD_MAP, price_scale=1, static_body_fields=STATIC_FIELDS
    )
    decoded = json.loads(body)
    assert decoded["CANO"] == "seal-account-value"
    assert decoded["CANO"] != "different-instrument-key-account-value"


def test_missing_a_required_field_refuses() -> None:
    # Build a seal using a VALID field_map/static_body_fields (so seal construction itself
    # succeeds) — the broken map is exercised only against the encode() call under test.
    seal = build_seal(field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS)
    incomplete_static = dict(STATIC_FIELDS)
    del incomplete_static["CNDT_PRIC"]
    with pytest.raises(KisOrderWireCodecError, match="missing"):
        KisOrderWireCodec.encode(
            seal,
            field_map=FIELD_MAP,
            price_scale=1,
            static_body_fields=incomplete_static,
        )


def test_an_unexpected_extra_field_refuses() -> None:
    seal = build_seal(field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS)
    extra_static = dict(STATIC_FIELDS)
    extra_static["EXTRA_FIELD"] = "x"
    with pytest.raises(KisOrderWireCodecError, match="unexpected"):
        KisOrderWireCodec.encode(
            seal, field_map=FIELD_MAP, price_scale=1, static_body_fields=extra_static
        )


def test_an_unrecognized_dynamic_source_refuses() -> None:
    seal = build_seal(field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS)
    bad_field_map = {"side": "SLL_BUY_DVSN_CD"}
    with pytest.raises(KisOrderWireCodecError, match="unrecognized"):
        KisOrderWireCodec.encode(
            seal,
            field_map=bad_field_map,
            price_scale=1,
            static_body_fields=STATIC_FIELDS,
        )


def test_encode_delegates_to_encode_fields_with_the_seals_own_four_values() -> None:
    """(T2 lane A) ``encode(seal, ...)`` must equal ``encode_fields`` called directly with the
    SAME four values a resolver reads before a seal exists — pinning that ``encode`` is a thin
    wrapper, never a diverging second implementation."""
    seal = build_seal(
        field_map=FIELD_MAP,
        static_body_fields=STATIC_FIELDS,
        account="12345678",
        instrument="005930",
        quantity=Decimal("10"),
        price=Decimal("70000"),
    )
    via_encode = KisOrderWireCodec.encode(
        seal, field_map=FIELD_MAP, price_scale=1, static_body_fields=STATIC_FIELDS
    )
    via_encode_fields = KisOrderWireCodec.encode_fields(
        account=seal.account,
        instrument=seal.instrument_key.instrument,
        quantity=seal.outbound_quantity,
        price=seal.outbound_price,
        field_map=FIELD_MAP,
        price_scale=1,
        static_body_fields=STATIC_FIELDS,
    )
    assert via_encode == via_encode_fields


def test_quantity_and_price_are_plain_decimal_strings_never_scientific_notation() -> (
    None
):
    seal = build_seal(
        field_map=FIELD_MAP,
        static_body_fields=STATIC_FIELDS,
        quantity=Decimal("100"),
        # A Decimal in exponent form (the shape the sealed payload carries, e.g. 4.499E+6):
        # the scaled quotient must still go out as plain digits.
        price=Decimal("1.5E+7"),
    )
    body = KisOrderWireCodec.encode(
        seal, field_map=FIELD_MAP, price_scale=100, static_body_fields=STATIC_FIELDS
    )
    decoded = json.loads(body)
    assert decoded["ORD_QTY"] == "100"
    assert decoded["ORD_UNPR"] == "150000"
    assert "E" not in decoded["ORD_UNPR"] and "e" not in decoded["ORD_UNPR"]


# ---------------------------------------------------------------------------
# price_scale — the 100× defect (rescope M2, 2026-10-22)
# ---------------------------------------------------------------------------


def test_a_x100_sealed_price_goes_out_as_whole_krw() -> None:
    """The defect this pins: every CP-3 tree prices off ``close_x100``, so a 270,000원 close
    is sealed as ``27000000``. Before ``price_scale`` the codec sent that integer verbatim as
    ``ORD_UNPR`` — a limit price 100× the market. Concrete failing input on the old codec:
    this seal → ``"ORD_UNPR":"27000000"``."""
    seal = build_seal(
        field_map=FIELD_MAP,
        static_body_fields=STATIC_FIELDS,
        instrument="005930",
        quantity=Decimal("1"),
        price=Decimal("27000000"),
    )
    body = json.loads(
        KisOrderWireCodec.encode(
            seal, field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS, price_scale=100
        )
    )
    assert body["ORD_UNPR"] == "270000"
    assert body["ORD_QTY"] == "1"


@pytest.mark.parametrize("price", ["27000050", "27000000.5"])
def test_a_price_that_is_not_whole_krw_is_refused_not_rounded(price: str) -> None:
    with pytest.raises(KisOrderWireCodecError, match="not a whole-KRW"):
        KisOrderWireCodec.encode_fields(
            account="12345678",
            instrument="005930",
            quantity=Decimal("1"),
            price=Decimal(price),
            field_map=FIELD_MAP,
            static_body_fields=STATIC_FIELDS,
            price_scale=100,
        )


@pytest.mark.parametrize("scale", [0, -100, True, 1.5, "100"])
def test_price_scale_must_be_a_positive_int(scale: object) -> None:
    with pytest.raises(KisOrderWireCodecError, match="positive int"):
        KisOrderWireCodec.encode_fields(
            account="12345678",
            instrument="005930",
            quantity=Decimal("1"),
            price=Decimal("27000000"),
            field_map=FIELD_MAP,
            static_body_fields=STATIC_FIELDS,
            price_scale=scale,  # type: ignore[arg-type]
        )
