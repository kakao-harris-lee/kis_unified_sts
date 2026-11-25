"""``KisOrderWireCodec`` — the single, shared KIS ``order_cash`` wire-body codec (independent"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal

from tos.canonical import CanonicalDecimal
from tos.egressgw import SendSeal

from tos_runtime.transport.kis_mock.account import KisAccountError, split_kis_account

__all__ = [
    "KIS_ORDER_CASH_WIRE_FIELDS",
    "KisOrderWireCodec",
    "KisOrderWireCodecError",
]

KIS_ORDER_CASH_WIRE_FIELDS: frozenset[str] = frozenset(
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

DYNAMIC_FIELD_SOURCES: frozenset[str] = frozenset(
    {"account", "instrument", "quantity", "price"}
)


class KisOrderWireCodecError(Exception):
    """The combined ``field_map``/``static_body_fields`` do not encode exactly the nine KIS"""


def _decimal_to_kis_string(value: CanonicalDecimal) -> str:
    """KIS requires numeric body fields as plain (non-scientific) decimal strings."""
    return format(Decimal(value), "f")


def _price_to_kis_string(price: CanonicalDecimal, price_scale: int) -> str:
    """``price / price_scale`` as a whole-KRW string, or refuse."""
    if (
        isinstance(price_scale, bool)
        or not isinstance(price_scale, int)
        or price_scale < 1
    ):
        raise KisOrderWireCodecError(
            f"KisOrderWireCodec: price_scale must be a positive int, got {price_scale!r}"
        )
    exact = Decimal(price)
    if not exact.is_finite():
        raise KisOrderWireCodecError(
            f"KisOrderWireCodec: price {price} is not a finite number"
        )
    numerator, denominator = exact.as_integer_ratio()
    krw, remainder = divmod(numerator, denominator * price_scale)
    if remainder:
        raise KisOrderWireCodecError(
            f"KisOrderWireCodec: price {price} at scale {price_scale} is "
            f"{exact / price_scale} — not a whole-KRW ORD_UNPR; refusing rather than rounding"
        )
    return str(krw)


_ACCOUNT_PRODUCT_FIELD = "ACNT_PRDT_CD"


def _account_coordinate(seal: SendSeal) -> str:
    """The sealed outbound ``account`` coordinate (review F2) — :attr:`SendSeal.account`, the"""
    return seal.account


class KisOrderWireCodec:
    """Stateless — pure static methods, grouped under one name so a future caller (T2's"""

    @staticmethod
    def encode_fields(
        *,
        account: str,
        instrument: str,
        quantity: CanonicalDecimal,
        price: CanonicalDecimal,
        field_map: Mapping[str, str],
        static_body_fields: Mapping[str, str],
        price_scale: int,
    ) -> bytes:
        """Serialize the four dynamic VALUES + static config into the KIS ``order_cash`` wire"""
        try:
            kis_account = split_kis_account(account)
        except KisAccountError as exc:
            raise KisOrderWireCodecError(f"KisOrderWireCodec: {exc}") from exc
        dynamic_sources: dict[str, str] = {
            "account": kis_account.cano,
            "instrument": instrument,
            "quantity": _decimal_to_kis_string(quantity),
            "price": _price_to_kis_string(price, price_scale),
        }
        fields: dict[str, str] = {}
        for source_name, wire_name in field_map.items():
            if source_name not in dynamic_sources:
                raise KisOrderWireCodecError(
                    f"KisOrderWireCodec.encode_fields: unrecognized dynamic field_map source "
                    f"{source_name!r} — only {sorted(DYNAMIC_FIELD_SOURCES)!r} are recognized"
                )
            fields[wire_name] = dynamic_sources[source_name]
        for wire_name, literal in static_body_fields.items():
            fields[wire_name] = literal

        present = frozenset(fields)
        if present != KIS_ORDER_CASH_WIRE_FIELDS:
            missing = sorted(KIS_ORDER_CASH_WIRE_FIELDS - present)
            unexpected = sorted(present - KIS_ORDER_CASH_WIRE_FIELDS)
            raise KisOrderWireCodecError(
                "KisOrderWireCodec.encode_fields: the encoded body does not cover exactly the "
                f"nine KIS order_cash fields — missing={missing!r} unexpected={unexpected!r}"
            )
        if fields[_ACCOUNT_PRODUCT_FIELD] != kis_account.acnt_prdt_cd:
            raise KisOrderWireCodecError(
                "KisOrderWireCodec: static ACNT_PRDT_CD does not match the sealed account's "
                "product code (its last two digits)"
            )

        return json.dumps(
            fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")

    @staticmethod
    def encode(
        seal: SendSeal,
        *,
        field_map: Mapping[str, str],
        static_body_fields: Mapping[str, str],
        price_scale: int,
    ) -> bytes:
        """Serialize the sealed outbound + static config into the KIS ``order_cash`` wire body."""
        return KisOrderWireCodec.encode_fields(
            account=_account_coordinate(seal),
            instrument=seal.instrument_key.instrument,
            quantity=seal.outbound_quantity,
            price=seal.outbound_price,
            field_map=field_map,
            static_body_fields=static_body_fields,
            price_scale=price_scale,
        )

    @staticmethod
    def digest(body_bytes: bytes) -> str:
        """``sha256`` hex digest of already-encoded body bytes (recipe step 4 above)."""
        return hashlib.sha256(body_bytes).hexdigest()
