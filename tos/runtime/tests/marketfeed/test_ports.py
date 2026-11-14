"""Hermetic unit tests for the two pure surfaces ``tos_runtime.marketfeed.ports`` gained with"""

from __future__ import annotations

from typing import Any

from tos_runtime.marketfeed.ports import (
    MonotonicAnchoredObservation,
    RawObservation,
    anchor_observation,
)

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
    """The format transcribed from ``transport/kis_quote/adapter.py:400-402`` as it stood at"""
    observation = anchor_observation(
        _pending(), as_of_ms=_AS_OF_MS, received_ms=_RECEIVED_MS
    )

    assert observation.raw_event_id == (
        "kis_quote_mock_stock:005930:1790557200123:"
        "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )


def test_the_anchor_instant_is_the_as_of_never_the_receipt() -> None:
    """``as_of_ms`` and ``received_ms`` fill DIFFERENT slots, and the id folds in the former."""
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
    """The distinctness the adapter's own phantom-churn note claims: the SAME content at a"""
    pending = _pending()
    first = anchor_observation(pending, as_of_ms=_AS_OF_MS, received_ms=_RECEIVED_MS)
    second = anchor_observation(
        pending, as_of_ms=_AS_OF_MS + 1, received_ms=_RECEIVED_MS + 1
    )

    assert first.raw_event_id != second.raw_event_id


def test_pending_observations_are_immutable() -> None:
    """Frozen by construction — a pending observation travels from the intake to the"""
    pending: Any = _pending()
    try:
        pending.requested_monotonic_ms = 0
    except AttributeError:
        return
    raise AssertionError("MonotonicAnchoredObservation must be frozen")
