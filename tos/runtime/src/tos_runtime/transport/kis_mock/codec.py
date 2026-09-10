"""``KisOrderWireCodec`` — the single, shared KIS ``order_cash`` wire-body codec (independent
review disposition F1, `dc6b47ba`).

**Why this module exists.** The adapter's own digest check (compare a freshly-serialized KIS
body's digest against ``SendSeal.request_bytes_digest``) is only meaningful if something
upstream computes ``request_bytes_digest`` the SAME way. Today it does not: the compose context
resolver sets ``EgressRequestRecord.request_bytes_digest`` literally EQUAL to
``capsule_egress_request_digest`` (``tos_runtime/compose/context.py:368``,
``self._egress_request_for_command`` — ``request_bytes_digest=self.capsule_egress_request_digest``),
and the gateway's own ``exact_binding_holds`` enforces exactly that equality as a structural
invariant (``tos/src/tos/egress/predicates.py:386-390``:
``request.request_bytes_digest != capsule_egress_request_digest`` ⇒ ``False``).
``capsule_egress_request_digest`` is itself a documented STAND-IN
(:mod:`tos_runtime.compose._egress_coordinates` module docstring: "a STAND-IN, not the real
thing") — a digest over ``capsule_terminus_fields`` (``account``/``instrument`` only), never a
hash of the real KIS wire bytes. So a ``sha256`` of THIS codec's own KIS-body JSON can never
equal a real, gateway-produced seal's ``request_bytes_digest`` today, no matter how correct this
codec is.

**The fix is out of this slice's (T1's) scope, but this module is the shared seam for it.** T2
(the compose-wiring slice) binds this SAME ``KisOrderWireCodec`` into the compose context
resolver so ``capsule_egress_request_digest`` (and therefore ``request_bytes_digest``) becomes
genuinely this codec's own digest of the sealed outbound — closing the semantic gap. Until that
binding lands, :mod:`tos_runtime.transport.kis_mock.config` refuses ``mode: live`` unconditionally
at load time (see that module's own docstring) — a real send would deterministically hit
:class:`~tos_runtime.transport.kis_mock.adapter.SendRefused` today, which is honest but useless,
so the config loader now says so up front instead.

**Serialization recipe (FROZEN — a future T2 binding must reproduce this EXACTLY, byte for
byte):**

1. Resolve the KIS ``order_cash`` body's nine required fields (N-17 collation memo,
   ``docs/plans/2026-07-29-tos-p02-n17-spec-collation.md``), from two disjoint sources:

   * **Four dynamic fields** (``field_map``, keyed by kernel-side source name): ``account``
     (:attr:`tos.egressgw.SendSeal.account` — the sealed **outbound coordinate**, review F2; NOT
     ``instrument_key.account``, a different, dispatch-key-only fact, and NOT a custody-loaded
     value), ``instrument`` (:attr:`~tos.egressgw.SendSeal.instrument_key`
     ``.instrument``), ``quantity`` (:attr:`~tos.egressgw.SendSeal.outbound_quantity`), ``price``
     (:attr:`~tos.egressgw.SendSeal.outbound_price`). The two numeric values are formatted as
     plain, non-scientific decimal strings via ``format(Decimal(value), "f")`` (KIS's own
     ``order_cash`` docstring: "ORD_QTY(주문수량), ORD_UNPR(주문단가) 등을 String으로 전달해야
     함").
   * **Five static fields** (``static_body_fields``, a per-deployment config constant, copied
     verbatim): ``ACNT_PRDT_CD``, ``ORD_DVSN``, ``EXCG_ID_DVSN_CD``, ``SLL_TYPE``, ``CNDT_PRIC``
     — none of these varies per attempt, so none has (or needs) a sealed source.

2. The combined field set (from both sources' target wire names) MUST equal
   :data:`KIS_ORDER_CASH_WIRE_FIELDS` **exactly** — not a subset, not a superset. A missing or
   an unexpected field raises :class:`KisOrderWireCodecError` before any byte is serialized
   (fail-closed; a partial order is never sent).
3. ``json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode
   ("utf-8")`` — deterministic: alphabetically sorted keys, no incidental whitespace, UTF-8.
4. ``digest(body_bytes) = hashlib.sha256(body_bytes).hexdigest()``.

**Construction note (reviewer F3).** This module has nothing to do with HTTP construction, but
the same discipline applies one layer over: :func:`tos_runtime.transport.kis_mock.client.
build_client` (``config`` in, a wired :class:`~tos_runtime.transport.kis_mock.client.
KisMockHttpClient` out) is the only sanctioned PRODUCTION construction path. An adapter
constructed with a directly-injected, hand-rolled client is a TEST seam, not a pattern T2 should
carry into the compose root.

Firewall: stdlib (``hashlib``, ``json``, ``decimal``) + ``tos.canonical``/``tos.egressgw`` only
— no ``tos_runtime`` sibling import needed (this module has no config/custody/network
dependency of its own; the adapter is the only in-package caller).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal

from tos.canonical import CanonicalDecimal
from tos.egressgw import SendSeal

__all__ = [
    "KIS_ORDER_CASH_WIRE_FIELDS",
    "KisOrderWireCodec",
    "KisOrderWireCodecError",
]

#: The nine KIS ``order_cash`` body fields this codec's output must cover EXACTLY (N-17 memo).
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

#: The closed set of per-attempt kernel-side sources ``field_map`` may name (review F2 — deliberately
#: excludes any custody-sourced value; the account number is itself a sealed outbound coordinate).
DYNAMIC_FIELD_SOURCES: frozenset[str] = frozenset(
    {"account", "instrument", "quantity", "price"}
)


class KisOrderWireCodecError(Exception):
    """The combined ``field_map``/``static_body_fields`` do not encode exactly the nine KIS
    ``order_cash`` wire fields, or ``field_map`` names an unrecognized dynamic source.
    """


def _decimal_to_kis_string(value: CanonicalDecimal) -> str:
    """KIS requires numeric body fields as plain (non-scientific) decimal strings."""
    return format(Decimal(value), "f")


def _account_coordinate(seal: SendSeal) -> str:
    """The sealed outbound ``account`` coordinate (review F2) — :attr:`SendSeal.account`, the
    same value :meth:`SendSeal._outbound_coordinates_match_sealed_fields` already validates
    against the seal's own ``outbound_coordinates`` ``("account", ...)`` entry. Never
    ``seal.instrument_key.account`` (a distinct, dispatch-key-only fact) and never a
    custody-loaded value — the real KIS account number reaches this codec exclusively through
    the seal, exactly like every other outbound fact (module docstring, decision 3)."""
    return seal.account


class KisOrderWireCodec:
    """Stateless — two pure static methods, grouped under one name so a future caller (T2's
    compose context resolver) imports and calls ``KisOrderWireCodec.encode``/``.digest`` without
    ever needing an instance."""

    @staticmethod
    def encode(
        seal: SendSeal,
        *,
        field_map: Mapping[str, str],
        static_body_fields: Mapping[str, str],
    ) -> bytes:
        """Serialize the sealed outbound + static config into the KIS ``order_cash`` wire body.

        Args:
            seal: The sealed outbound (the sole source for every dynamic field).
            field_map: Kernel-side source name -> KIS wire field name (closed vocabulary:
                :data:`DYNAMIC_FIELD_SOURCES`).
            static_body_fields: KIS wire field name -> per-deployment literal constant.

        Returns:
            The deterministic, canonical body bytes (recipe step 3 above).

        Raises:
            KisOrderWireCodecError: ``field_map`` names an unrecognized source, or the combined
                field set does not equal :data:`KIS_ORDER_CASH_WIRE_FIELDS` exactly.
        """
        dynamic_sources: dict[str, str] = {
            "account": _account_coordinate(seal),
            "instrument": seal.instrument_key.instrument,
            "quantity": _decimal_to_kis_string(seal.outbound_quantity),
            "price": _decimal_to_kis_string(seal.outbound_price),
        }
        fields: dict[str, str] = {}
        for source_name, wire_name in field_map.items():
            if source_name not in dynamic_sources:
                raise KisOrderWireCodecError(
                    f"KisOrderWireCodec.encode: unrecognized dynamic field_map source "
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
                "KisOrderWireCodec.encode: the encoded body does not cover exactly the nine "
                f"KIS order_cash fields — missing={missing!r} unexpected={unexpected!r}"
            )

        return json.dumps(
            fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")

    @staticmethod
    def digest(body_bytes: bytes) -> str:
        """``sha256`` hex digest of already-encoded body bytes (recipe step 4 above)."""
        return hashlib.sha256(body_bytes).hexdigest()
