"""``tos/runtime/tests/operations`` — hermetic fixtures for the schema-ledger and durable-set"""

from __future__ import annotations

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme

from ..engine.conftest import FixedKeyProvider  # noqa: F401

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
