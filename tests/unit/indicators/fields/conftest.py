"""Shared builders for the declarative-field tests.

Every document here is written out in full in the test that uses it — these
helpers only remove the two version lines and the publish boilerplate, so a
reader of a refusal test sees exactly the declaration under test.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from shared.indicators.fields import (
    CATALOG_VERSION,
    SCHEMA_VERSION,
    FieldBar,
    FieldsDocument,
    parse_fields_document,
)


def document(
    fields: list[dict[str, Any]],
    publish: list[dict[str, Any]] | None = None,
    *,
    schema: str = SCHEMA_VERSION,
    catalog: str = CATALOG_VERSION,
) -> dict[str, Any]:
    """Build a raw ``fields.yaml`` mapping.

    When *publish* is omitted the LAST declared field is published — enough for
    a document to be well formed when the test is about ``fields``.
    """
    if publish is None:
        # ``<unnamed>`` keeps the helper usable for a malformed field entry —
        # the field-list refusal fires long before publish is looked at.
        publish = [{"field": fields[-1].get("name", "<unnamed>")}]
    return {
        "schema": schema,
        "catalog": catalog,
        "fields": fields,
        "publish": publish,
    }


def parsed(
    fields: list[dict[str, Any]], publish: list[dict[str, Any]] | None = None
) -> FieldsDocument:
    """Parse :func:`document` and return the validated form."""
    return parse_fields_document(document(fields, publish))


def bar(
    minute: int = 0,
    *,
    open: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.5,
    volume: float = 1000.0,
    day: int = 11,
    hour: int = 9,
) -> FieldBar:
    """One bar on 2026-11-*day* at *hour*:00 + *minute* minutes, KST."""
    stamp = datetime(2026, 11, day, hour, 0) + timedelta(minutes=minute)
    return FieldBar.create(
        stamp, open=open, high=high, low=low, close=close, volume=volume
    )


@pytest.fixture
def hand_bars() -> list[FieldBar]:
    """Three bars whose ATR and VWAP are exact binary values.

    ===  ====  ====  =====  ======  ================  ====================
    bar  high  low   close  volume  true range        typical price
    ===  ====  ====  =====  ======  ================  ====================
    0    10     8    9        100   10-8 = 2          (10+8+9)/3  = 9.0
    1    11    10    9        300   |11-9| = 2        (11+10+9)/3 = 10.0
    2    12     8    10       600   12-8 = 4          (12+8+10)/3 = 10.0
    ===  ====  ====  =====  ======  ================  ====================

    So ``atr(period=2)`` is ``2.0``, ``(2+2)/2 = 2.0``, ``(2+4)/2 = 3.0`` and
    ``session.vwap_typical`` is ``9.0``, ``3900/400 = 9.75``,
    ``9900/1000 = 9.9``.
    """
    return [
        bar(0, high=10.0, low=8.0, close=9.0, volume=100.0, open=9.0),
        bar(1, high=11.0, low=10.0, close=9.0, volume=300.0, open=10.0),
        bar(2, high=12.0, low=8.0, close=10.0, volume=600.0, open=9.0),
    ]
