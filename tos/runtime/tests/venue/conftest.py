"""Hermetic fixtures for tos_runtime.venue tests (tmp_path only, no external
network, no ambient env — same discipline as tos/runtime/tests/calendar
/conftest.py and tos/runtime/tests/compose/conftest.py).

The venue/OCP YAML VALUES below are FIXTURE DATA authored for this test
suite only — they are NOT the operator-signed production policy (plan §6
②, still an open operator decision).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, CanonicalizationScheme, get_scheme
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore

#: The one registered kernel canonicalization scheme (mirrors
#: tos_runtime.compose._wiring's own ``_SCHEME`` constant).
SCHEME: CanonicalizationScheme = get_scheme(EV_L1_PROVISIONAL_VERSION)

FIXTURE_POLICY_ID = "vcp-fixture-1"
FIXTURE_POLICY_GENERATION = 1
FIXTURE_OCP_POLICY_ID = "ocp-fixture-1"
FIXTURE_OCP_POLICY_GENERATION = 1
FIXTURE_OCP_POLICY_VERSION = "1.0.0"


def venue_policy_yaml(
    *,
    policy_id: str = FIXTURE_POLICY_ID,
    policy_generation: int = FIXTURE_POLICY_GENERATION,
    max_quantity: str = "null",
    admitting_phases: str = '["REGULAR"]',
) -> str:
    """The standard fixture ``venue_constraint_policy.yaml`` body — every
    numeric bound present EXCEPT ``max_quantity`` (left ``null`` by default,
    the module docstring's "honestly nullable" discipline), one
    ``NEW_LONG``/``NEW_SHORT`` admitting-phase rule each, no dependency
    edges."""
    return textwrap.dedent(f"""\
        policy_id: "{policy_id}"
        policy_generation: {policy_generation}
        scope:
          environment: "paper"
          broker: "kis"
          account: "acct-1"
          venue: "krx"
          market_segment: "futures"
          product_type: "index-futures"
          instrument: "K200F"
          instrument_class: "krx-futures"
          currency: "KRW"
          quantity_unit: "CONTRACTS"
        admitting_phase_rules:
          - action: "NEW_LONG"
            admitting_phases: {admitting_phases}
          - action: "NEW_SHORT"
            admitting_phases: {admitting_phases}
        required_constraint_classes: []
        shape_constraints:
          price_min: 100
          price_max: 500
          tick_size: 5
          lot_size: 1
          min_quantity: 1
          max_quantity: {max_quantity}
          allowed_order_types: ["LIMIT"]
          allowed_tifs: ["DAY"]
          allowed_sides: ["BUY", "SELL"]
          allowed_position_effects: ["OPEN", "CLOSE"]
        dependency_closure:
          edges: []
        """)


def ocp_yaml(
    *,
    policy_id: str = FIXTURE_OCP_POLICY_ID,
    policy_generation: int = FIXTURE_OCP_POLICY_GENERATION,
    policy_version: str = FIXTURE_OCP_POLICY_VERSION,
    canonicalization_version: str | None = None,
    wire_codec: str = "null",
) -> str:
    version = (
        SCHEME.version if canonicalization_version is None else canonicalization_version
    )
    return textwrap.dedent(f"""\
        policy_id: "{policy_id}"
        policy_generation: {policy_generation}
        policy_version: "{policy_version}"
        canonicalization_version: "{version}"
        wire_codec: {wire_codec}
        """)


def write_fixture_venue_policy(tmp_path: Path, text: str | None = None) -> Path:
    path = tmp_path / "venue_constraint_policy.yaml"
    path.write_text(venue_policy_yaml() if text is None else text, encoding="utf-8")
    return path


def write_fixture_ocp(tmp_path: Path, text: str | None = None) -> Path:
    path = tmp_path / "order_construction_policy.yaml"
    path.write_text(ocp_yaml() if text is None else text, encoding="utf-8")
    return path


class FixedKeyProvider:
    """A :class:`~tos_runtime.evidence.store.KeyProvider` test double — fixed
    bytes (mirrors ``tos/runtime/tests/calendar/test_owner.py``'s own
    re-declared double; cross-suite imports are forbidden per that module's
    convention)."""

    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-venue-suite")

    def generations(self) -> tuple[int, ...]:
        return (1,)

    def key_for(self, generation: int) -> bytes:
        del generation
        return b"test-fixed-key-bytes-venue-suite"


@pytest.fixture
def key_provider() -> KeyProvider:
    return FixedKeyProvider()


@pytest.fixture
def evidence_store(tmp_path: Path, key_provider: KeyProvider):
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    yield instance
    instance.close()


def kind_count(evidence_store: SqliteEvidenceStore, kind: str) -> int:
    return sum(1 for entry in evidence_store.iter_entry_meta() if entry.kind == kind)
