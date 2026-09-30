"""Hermetic unit tests for the two pure surfaces ``tos_runtime.marketfeed.ports`` gained with
#810 — :class:`~tos_runtime.marketfeed.ports.MonotonicAnchoredObservation` and
:func:`~tos_runtime.marketfeed.ports.anchor_observation` (plan
``docs/plans/2026-09-28-tos-kis-quote-request-anchor-plan.md`` §2.1).

The load-bearing claim here is a NON-change: moving ``raw_event_id``'s derivation out of the
kis_quote adapter must leave the id itself byte-identical, because that string is the
``observation_ref`` every candidate value points at and the key a durable preimage is stored
under (``ports.py``'s own ``RawObservation.raw_event_id`` docstring). A silently reshaped id
would not fail any existing test — it would simply stop matching ids already on disk.

Pure: no clock, no I/O, no ``tmp_path``.
"""

from __future__ import annotations

from typing import Any

from tos_runtime.marketfeed.ports import (
    MonotonicAnchoredObservation,
    RawObservation,
    anchor_observation,
)

#: A realistic sha256-shaped content digest — the shape
#: ``KisQuoteObservationIntake._content_digest`` produces (hexdigest, 64 chars).
_DIGEST = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

_SOURCE_ID = "kis_quote_mock_stock"
_INSTRUMENT = "005930"
_AS_OF_MS = 1_790_557_200_123
_RECEIVED_MS = 1_790_557_200_456


def _pending(**overrides: Any) -> MonotonicAnchoredObservation:
    base: dict[str, Any] = {
        "instrument": _INSTRUMENT,
        "fields": (("last_price", "71300"), ("volume", 12345)),
        "source_id": _SOURCE_ID,
        "content_digest": _DIGEST,
        "requested_monotonic_ms": 1_000,
        "received_monotonic_ms": 1_180,
    }
    base.update(overrides)
    return MonotonicAnchoredObservation(**base)


def test_raw_event_id_is_byte_identical_to_the_pre_810_adapter_format() -> None:
    """The format transcribed from ``transport/kis_quote/adapter.py:400-402`` as it stood at
    main ``ac2efb0f`` (the commit this plan is written against)::

        raw_event_id = (
            f"{self._config.source_id}:{instrument}:{wall_now_ms}:{content_digest}"
        )

    Written out as a literal rather than re-composed with an f-string of the same shape: an
    f-string here would pass whatever the function does, which is the "guard that reads a
    second copy of what it guards" shape this repo records as a repeated defect. Mutation:
    reorder any two components, or change the separator -> red.
    """
    observation = anchor_observation(
        _pending(), as_of_ms=_AS_OF_MS, received_ms=_RECEIVED_MS
    )

    assert observation.raw_event_id == (
        "kis_quote_mock_stock:005930:1790557200123:"
        "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )


def test_the_anchor_instant_is_the_as_of_never_the_receipt() -> None:
    """``as_of_ms`` and ``received_ms`` fill DIFFERENT slots, and the id folds in the former.
    Mutation: derive the id from ``received_ms`` -> red (and the whole point of #810 — the
    request instant is what puts the round trip inside ``source_age``)."""
    observation = anchor_observation(
        _pending(), as_of_ms=_AS_OF_MS, received_ms=_RECEIVED_MS
    )

    assert observation.as_of_ms == _AS_OF_MS
    assert observation.received_ms == _RECEIVED_MS
    assert f":{_AS_OF_MS}:" in observation.raw_event_id
    assert str(_RECEIVED_MS) not in observation.raw_event_id


def test_every_other_field_is_carried_through_unchanged() -> None:
    pending = _pending()
    observation = anchor_observation(
        pending, as_of_ms=_AS_OF_MS, received_ms=_RECEIVED_MS
    )

    assert isinstance(observation, RawObservation)
    assert observation.instrument == pending.instrument
    assert observation.source_id == pending.source_id
    assert observation.fields == pending.fields


def test_two_anchor_instants_over_one_digest_never_collide() -> None:
    """The distinctness the adapter's own phantom-churn note claims: the SAME content at a
    LATER instant is a legitimate, distinct observation, and the id says so."""
    pending = _pending()
    first = anchor_observation(pending, as_of_ms=_AS_OF_MS, received_ms=_RECEIVED_MS)
    second = anchor_observation(
        pending, as_of_ms=_AS_OF_MS + 1, received_ms=_RECEIVED_MS + 1
    )

    assert first.raw_event_id != second.raw_event_id


def test_pending_observations_are_immutable() -> None:
    """Frozen by construction — a pending observation travels from the intake to the
    scheduler across a pass boundary, and nothing downstream may re-stamp it in place.
    """
    # Typed ``Any`` on purpose: the assignment below is the thing under test, and mypy
    # (correctly) rejects it statically on the real type.
    pending: Any = _pending()
    try:
        pending.requested_monotonic_ms = 0
    except AttributeError:
        return
    raise AssertionError("MonotonicAnchoredObservation must be frozen")
