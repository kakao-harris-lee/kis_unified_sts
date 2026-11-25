"""Shared builders for the declarative-field tests."""

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
    """Build a raw ``fields.yaml`` mapping."""
    if publish is None:
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
    """Three bars whose ATR and VWAP are exact binary values."""
    return [
        bar(0, high=10.0, low=8.0, close=9.0, volume=100.0, open=9.0),
        bar(1, high=11.0, low=10.0, close=9.0, volume=300.0, open=10.0),
        bar(2, high=12.0, low=8.0, close=10.0, volume=600.0, open=9.0),
    ]
