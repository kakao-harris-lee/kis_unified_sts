"""Shared builders for ``tos_runtime.marketfeed`` tests (TOS tick-source wave, lane A)."""

from __future__ import annotations

from pathlib import Path

from tos.canonical import EV_L1_PROVISIONAL_VERSION, CanonicalizationScheme, get_scheme
from tos.dsl import ScalarValue
from tos_runtime.marketfeed.policy import (
    LoadedCriticalInputPolicy,
    load_critical_input_policy,
)
from tos_runtime.marketfeed.ports import RawObservation

SCHEME: CanonicalizationScheme = get_scheme(EV_L1_PROVISIONAL_VERSION)

ACCOUNT = "acct-1"
INSTRUMENT = "ES"
ENVIRONMENT = "paper-test"
DECISION_CLASS = "entry"

BAR_ONE_AS_OF = 1_700_000_060_000
BAR_TWO_AS_OF = 1_700_000_120_000

CLOSE_BAR_ONE = 4_512_500
CLOSE_BAR_TWO = 4_513_000

_HEADER_LINES: dict[str, str] = {
    "policy_id": 'policy_id: "cip-fixture-1"',
    "policy_version": 'policy_version: "v1"',
    "policy_generation": "policy_generation: 1",
    "issuer_principal_id": 'issuer_principal_id: "iss-1"',
    "environment": f'environment: "{ENVIRONMENT}"',
    "decision_class": f'decision_class: "{DECISION_CLASS}"',
    "intended_use": f'intended_use: "{DECISION_CLASS}"',
}

DEFAULT_FIELDS_BLOCK = (
    "fields:\n"
    "  - field_key: close\n"
    "    unit: KRW\n"
    "    scale: minor\n"
    '    multiplier: "1"\n'
    '    sign: "1"\n'
    "    max_age_ms: 5000\n"
    "  - field_key: session\n"
    "    unit: token\n"
    "    scale: none\n"
    '    multiplier: "1"\n'
    '    sign: "1"\n'
    "    max_age_ms: 5000\n"
)


def policy_yaml(
    *,
    omit: tuple[str, ...] = (),
    overrides: dict[str, str] | None = None,
    fields_block: str = DEFAULT_FIELDS_BLOCK,
) -> str:
    """Compose a Critical Input Policy YAML document from the header line table + a fields block."""
    overrides = overrides or {}
    lines = [
        overrides.get(key, default_line)
        for key, default_line in _HEADER_LINES.items()
        if key not in omit
    ]
    return "\n".join(lines) + "\n" + fields_block


VALID_POLICY_YAML = policy_yaml()


def write_policy(
    tmp_path: Path,
    text: str = VALID_POLICY_YAML,
    *,
    name: str = "critical_input_policy.yaml",
) -> Path:
    """Write ``text`` under ``tmp_path`` and return the path (hermetic — no writes elsewhere)."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def loaded_policy(
    tmp_path: Path, text: str = VALID_POLICY_YAML
) -> LoadedCriticalInputPolicy:
    """Write ``text`` and load it — the common "give me a real loaded policy" fixture step."""
    return load_critical_input_policy(write_policy(tmp_path, text), scheme=SCHEME)


def observation(
    *,
    raw_event_id: str = "raw-1",
    instrument: str = INSTRUMENT,
    as_of_ms: int = BAR_ONE_AS_OF,
    fields: tuple[tuple[str, ScalarValue], ...] = (
        ("close", CLOSE_BAR_ONE),
        ("session", "REGULAR"),
    ),
    source_id: str = "journal-1",
    received_ms: int | None = None,
) -> RawObservation:
    """A raw observation matching :data:`VALID_POLICY_YAML`'s two declared fields by default."""
    return RawObservation(
        raw_event_id=raw_event_id,
        instrument=instrument,
        as_of_ms=as_of_ms,
        fields=fields,
        source_id=source_id,
        received_ms=received_ms,
    )
