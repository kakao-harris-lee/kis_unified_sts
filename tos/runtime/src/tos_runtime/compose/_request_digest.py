"""Per-attempt request-bytes digest sources (T2 lane A — codec digest binding, plan
``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md`` §8 "설계 정정 ①").

**The gap this module closes.** :class:`~tos_runtime.compose.context.ComposeContextResolver`
used to carry ``capsule_egress_request_digest`` as a single boot-time constant field
(``tos_runtime/compose/_wiring.py::_build_context_resolver``,
``_SCHEME.compute_digest({name: getattr(construction, name) for name in
egress_coordinates.capsule_terminus_fields})`` — a digest over
:data:`~tos_runtime.compose._egress_coordinates.EgressCoordinatesConfig.capsule_terminus_fields`,
currently ``("account", "instrument")`` only), and set
``EgressRequestRecord.request_bytes_digest`` (:meth:`~tos_runtime.compose.context.
ComposeContextResolver._egress_request_for_command`) literally EQUAL to that same constant. The
kernel's ``exact_binding_holds`` (``tos/src/tos/egress/predicates.py``) enforces exactly that
equality as a structural invariant, so it always trivially held — never a real check that a
transport's own wire bytes match anything.

:mod:`tos_runtime.transport.kis_mock.codec`'s own module docstring names this exact gap and the
shared seam that closes it: :class:`~tos_runtime.transport.kis_mock.codec.KisOrderWireCodec`.
This module supplies the resolver-side half — a small seam so ``ComposeContextResolver`` can be
wired with EITHER the unchanged stand-in behaviour (:class:`CapsuleStandInDigest`, the default —
identical to today's constant) OR a genuine KIS-wire-codec digest
(:class:`KisWireCodecDigest`, injected by a later lane's ``compose --transport kis-mock`` wiring)
without ``ComposeContextResolver`` itself needing to know which.

**Why a ``Protocol``, not a subclass hierarchy.** Both implementations are pure, stateless(-ish)
callables over the same four per-attempt values every downstream consumer already reads off
``SendSeal``/``SendBoundaryContext`` — a ``Callable``-shaped seam keeps
:mod:`tos_runtime.compose.context` and :mod:`tos_runtime.compose._wiring` from needing to import
either concrete implementation's own dependencies (:class:`KisWireCodecDigest` imports
:mod:`tos_runtime.transport.kis_mock.codec`; :class:`CapsuleStandInDigest` imports nothing beyond
this module).

Firewall: stdlib + ``tos.canonical`` (:class:`RequestBytesDigestSource` and
:class:`CapsuleStandInDigest`) — no ``tos_runtime`` sibling import needed for those two.
:class:`KisWireCodecDigest` additionally imports :mod:`tos_runtime.transport.kis_mock.codec`
(runtime -> runtime, allowed by firewall rule (g); no cycle — that module imports only ``tos.*``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from tos.canonical import EV_L1_PROVISIONAL_VERSION, CanonicalDecimal, get_scheme

from tos_runtime.transport.kis_mock.codec import KisOrderWireCodec

if TYPE_CHECKING:
    # Independent review LOW-3: a TYPE_CHECKING-only import — a genuine runtime import of
    # tos_runtime.compose._types here would be a cycle (_types -> context -> this module); see
    # default_request_bytes_digest_source's own docstring for the full explanation.
    from tos_runtime.compose._types import ConstructionConfig

__all__ = [
    "CapsuleStandInDigest",
    "KisWireCodecDigest",
    "RequestBytesDigestSource",
    "default_request_bytes_digest_source",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


@runtime_checkable
class RequestBytesDigestSource(Protocol):
    """The ONE per-attempt digest :class:`~tos_runtime.compose.context.ComposeContextResolver`
    computes and shares between ``EgressRequestRecord.request_bytes_digest`` (item 17) and
    ``SendBoundaryContext.capsule_egress_request_digest`` — the exact two fields the kernel's
    ``exact_binding_holds`` requires to agree (module docstring).

    Every argument is a value the resolver already holds before a seal exists — never a
    ``SendSeal`` or ``SendBoundaryContext`` object itself, so an implementation cannot reach past
    these four values into anything else the seal will later carry.
    """

    def __call__(
        self,
        *,
        account: str,
        instrument: str,
        quantity: CanonicalDecimal,
        price: CanonicalDecimal,
    ) -> str:
        """Compute this attempt's request-bytes digest.

        Args:
            account: The authorized outbound account coordinate (-> ``SendSeal.account``).
            instrument: The instrument key's instrument (-> ``SendSeal.instrument_key.instrument``).
            quantity: The derived outbound quantity (-> ``SendSeal.outbound_quantity``).
            price: The derived outbound price (-> ``SendSeal.outbound_price``).

        Returns:
            The digest string.
        """
        ...


@dataclass(frozen=True)
class CapsuleStandInDigest:
    """The unchanged capsule-terminus stand-in (module docstring) — returns the SAME boot-time
    constant :mod:`tos_runtime.compose._wiring` computed before this lane, regardless of the four
    per-attempt values. This is the DEFAULT ``ComposeContextResolver.request_bytes_digest_source``
    today; behaviourally identical to the prior constant field, just recomputed (cheaply) once per
    attempt through this seam instead of once at boot.
    """

    #: The precomputed stand-in digest (``_SCHEME.compute_digest`` over
    #: ``capsule_terminus_fields`` — unchanged from the prior boot-time computation).
    digest: str

    def __call__(
        self,
        *,
        account: str,  # noqa: ARG002 - stand-in: deliberately ignores every argument
        instrument: str,  # noqa: ARG002
        quantity: CanonicalDecimal,  # noqa: ARG002
        price: CanonicalDecimal,  # noqa: ARG002
    ) -> str:
        return self.digest


@dataclass(frozen=True)
class KisWireCodecDigest:
    """The genuine KIS-wire-codec digest (module docstring) — a ``sha256`` of
    :meth:`~tos_runtime.transport.kis_mock.codec.KisOrderWireCodec.encode_fields`'s own output
    over the same four values, using this per-deployment ``field_map``/``static_body_fields``.

    Binding this into ``ComposeContextResolver.request_bytes_digest_source`` is what makes
    :mod:`tos_runtime.transport.kis_mock.adapter`'s own digest check
    (``KisOrderWireCodec.digest(KisOrderWireCodec.encode(seal, ...)) ==
    seal.request_bytes_digest``) genuinely meaningful — see
    :mod:`tos_runtime.transport.kis_mock.codec`'s own module docstring for the full picture.
    """

    field_map: Mapping[str, str]
    static_body_fields: Mapping[str, str]

    def __call__(
        self,
        *,
        account: str,
        instrument: str,
        quantity: CanonicalDecimal,
        price: CanonicalDecimal,
    ) -> str:
        body = KisOrderWireCodec.encode_fields(
            account=account,
            instrument=instrument,
            quantity=quantity,
            price=price,
            field_map=self.field_map,
            static_body_fields=self.static_body_fields,
        )
        return KisOrderWireCodec.digest(body)


def default_request_bytes_digest_source(
    construction: ConstructionConfig, capsule_terminus_fields: Iterable[str]
) -> CapsuleStandInDigest:
    """Build the DEFAULT :class:`CapsuleStandInDigest` (T2 lane C — moved out of
    ``tos_runtime.compose._wiring`` to keep that module's own size budget net-negative; no
    behavioural change from the T2 lane A version this replaces).

    ``construction`` is typed as :class:`~tos_runtime.compose._types.ConstructionConfig` under
    ``TYPE_CHECKING`` only (independent review LOW-3) — a genuine RUNTIME import of
    :mod:`tos_runtime.compose._types` here would be a cycle (it imports
    :mod:`tos_runtime.compose.context`, which imports THIS module), but a ``TYPE_CHECKING``-guarded
    import plus the ``from __future__ import annotations`` string-annotation deferral this module
    already carries costs nothing at runtime and gives full static typing at the one real call
    site — strictly better than the bare ``object`` this signature carried before, which discarded
    typing entirely rather than avoiding the cycle. This function still only ever reads named
    attributes off ``construction`` via ``getattr``, never anything ``ConstructionConfig``-specific
    beyond that.

    Args:
        construction: The per-strategy Order Construction facts object (every caller today:
            :class:`~tos_runtime.compose._types.ConstructionConfig`) — only attributes named in
            ``capsule_terminus_fields`` are read, via ``getattr``.
        capsule_terminus_fields: Which of ``construction``'s own attribute names feed the digest
            (:data:`~tos_runtime.compose._egress_coordinates.EgressCoordinatesConfig.capsule_terminus_fields`
            at the one real call site).

    Returns:
        The stand-in digest source, wrapping the SAME boot-time computation the prior inline
        helper performed.
    """
    return CapsuleStandInDigest(
        digest=_SCHEME.compute_digest(
            {name: getattr(construction, name) for name in capsule_terminus_fields}
        )
    )
