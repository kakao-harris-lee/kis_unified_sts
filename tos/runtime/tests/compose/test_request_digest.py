"""``tos_runtime.compose._request_digest`` unit tests (T2 lane A — codec digest binding, plan
``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md`` §8 "설계 정정 ①").
"""

from __future__ import annotations

from decimal import Decimal

from tos_runtime.compose._request_digest import (
    CapsuleStandInDigest,
    KisWireCodecDigest,
    RequestBytesDigestSource,
)
from tos_runtime.transport.kis_mock.codec import KisOrderWireCodec

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


def test_capsule_stand_in_digest_ignores_its_arguments_and_returns_the_constant() -> (
    None
):
    source = CapsuleStandInDigest(digest="stand-in-digest-value")
    first = source(
        account="acct-1",
        instrument="005930",
        quantity=Decimal("10"),
        price=Decimal("100"),
    )
    second = source(
        account="acct-2", instrument="000660", quantity=Decimal("5"), price=Decimal("1")
    )
    assert first == "stand-in-digest-value" == second


def test_capsule_stand_in_digest_is_a_request_bytes_digest_source() -> None:
    assert isinstance(CapsuleStandInDigest(digest="x"), RequestBytesDigestSource)


def test_kis_wire_codec_digest_matches_a_direct_codec_computation() -> None:
    """Pins that :class:`KisWireCodecDigest` computes EXACTLY what a caller would get calling
    ``KisOrderWireCodec.encode_fields``/``.digest`` directly over the same four values — the
    seam adds no divergence."""
    source = KisWireCodecDigest(field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS)
    account = "12345678"
    instrument = "005930"
    quantity = Decimal("10")
    price = Decimal("70000")

    via_source = source(
        account=account, instrument=instrument, quantity=quantity, price=price
    )
    via_direct = KisOrderWireCodec.digest(
        KisOrderWireCodec.encode_fields(
            account=account,
            instrument=instrument,
            quantity=quantity,
            price=price,
            field_map=FIELD_MAP,
            static_body_fields=STATIC_FIELDS,
        )
    )
    assert via_source == via_direct


def test_kis_wire_codec_digest_is_sensitive_to_every_one_of_its_four_inputs() -> None:
    """A mutation to ANY one of the four values must change the digest — proves the seam
    actually threads all four through, not a subset."""
    source = KisWireCodecDigest(field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS)
    base = source(
        account="acct-1",
        instrument="005930",
        quantity=Decimal("10"),
        price=Decimal("70000"),
    )
    assert base != source(
        account="acct-2",
        instrument="005930",
        quantity=Decimal("10"),
        price=Decimal("70000"),
    )
    assert base != source(
        account="acct-1",
        instrument="000660",
        quantity=Decimal("10"),
        price=Decimal("70000"),
    )
    assert base != source(
        account="acct-1",
        instrument="005930",
        quantity=Decimal("11"),
        price=Decimal("70000"),
    )
    assert base != source(
        account="acct-1",
        instrument="005930",
        quantity=Decimal("10"),
        price=Decimal("70001"),
    )


def test_kis_wire_codec_digest_is_a_request_bytes_digest_source() -> None:
    assert isinstance(
        KisWireCodecDigest(field_map=FIELD_MAP, static_body_fields=STATIC_FIELDS),
        RequestBytesDigestSource,
    )
