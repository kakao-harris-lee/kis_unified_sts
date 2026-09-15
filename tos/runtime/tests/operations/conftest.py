"""``tos/runtime/tests/operations`` — hermetic fixtures for the schema-ledger and durable-set
backup/restore suites (TOS Phase 5 W4 plan §2 decisions 1-3).

Reuses :mod:`tos.runtime.tests.engine`'s own ``FixedKeyProvider`` test double rather than
re-typing it.
"""

from __future__ import annotations

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme

from ..engine.conftest import FixedKeyProvider  # noqa: F401

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
