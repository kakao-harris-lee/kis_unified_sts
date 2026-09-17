"""``tos_runtime.marketfeed.policy`` — loader happy path + fail-closed refusals (TOS tick-source
wave, plan §2 decision 2; lane A).

Hermetic (D1.4): every case writes its own YAML under ``tmp_path``; no network, no ambient env.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos_runtime.marketfeed.policy import (
    CriticalInputPolicyConfigError,
    load_critical_input_policy,
)

from ._fixtures import (
    DEFAULT_FIELDS_BLOCK,
    SCHEME,
    VALID_POLICY_YAML,
    policy_yaml,
    write_policy,
)

# ===========================================================================
# Happy path
# ===========================================================================


def test_loads_valid_policy(tmp_path: Path) -> None:
    path = write_policy(tmp_path)
    loaded = load_critical_input_policy(path, scheme=SCHEME)

    assert loaded.policy_id == "cip-fixture-1"
    assert loaded.policy_version == "v1"
    assert loaded.policy_generation == 1
    assert loaded.issuer_principal_id == "iss-1"
    assert loaded.environment == "paper-test"
    assert loaded.decision_class == "entry"
    assert loaded.intended_use == "entry"
    assert [f.field_key for f in loaded.fields] == ["close", "session"]
    assert loaded.fields_by_key["close"].unit == "KRW"
    assert loaded.fields_by_key["close"].max_age_ms == 5000
    assert loaded.fields_by_key["session"].max_age_ms == 5000
    assert loaded.canonical_digest


def test_digest_is_deterministic_across_reloads(tmp_path: Path) -> None:
    path1 = write_policy(tmp_path, name="a.yaml")
    path2 = write_policy(tmp_path, name="b.yaml")
    loaded1 = load_critical_input_policy(path1, scheme=SCHEME)
    loaded2 = load_critical_input_policy(path2, scheme=SCHEME)
    assert loaded1.canonical_digest == loaded2.canonical_digest


def test_digest_is_sensitive_to_field_content(tmp_path: Path) -> None:
    path1 = write_policy(tmp_path, name="a.yaml")
    mutated = VALID_POLICY_YAML.replace("max_age_ms: 5000", "max_age_ms: 6000", 1)
    path2 = write_policy(tmp_path, mutated, name="b.yaml")
    loaded1 = load_critical_input_policy(path1, scheme=SCHEME)
    loaded2 = load_critical_input_policy(path2, scheme=SCHEME)
    assert loaded1.canonical_digest != loaded2.canonical_digest


# ===========================================================================
# Structural / YAML-shape refusals
# ===========================================================================


def test_missing_file_refuses(tmp_path: Path) -> None:
    with pytest.raises(CriticalInputPolicyConfigError, match="not found"):
        load_critical_input_policy(tmp_path / "does-not-exist.yaml", scheme=SCHEME)


def test_not_a_mapping_refuses(tmp_path: Path) -> None:
    path = write_policy(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(CriticalInputPolicyConfigError, match="top-level mapping"):
        load_critical_input_policy(path, scheme=SCHEME)


def test_not_valid_yaml_refuses(tmp_path: Path) -> None:
    path = write_policy(tmp_path, "key: [unterminated\n")
    with pytest.raises(CriticalInputPolicyConfigError, match="not valid YAML"):
        load_critical_input_policy(path, scheme=SCHEME)


# ===========================================================================
# Top-level header refusals — every required scalar
# ===========================================================================

_HEADER_KEYS = (
    "policy_id",
    "policy_version",
    "policy_generation",
    "issuer_principal_id",
    "environment",
    "decision_class",
    "intended_use",
)


@pytest.mark.parametrize("key", _HEADER_KEYS)
def test_missing_top_level_key_refuses(tmp_path: Path, key: str) -> None:
    path = write_policy(tmp_path, policy_yaml(omit=(key,)))
    with pytest.raises(CriticalInputPolicyConfigError, match=key):
        load_critical_input_policy(path, scheme=SCHEME)


@pytest.mark.parametrize("key", _HEADER_KEYS)
def test_null_top_level_key_refuses(tmp_path: Path, key: str) -> None:
    """Every leaf is named-TBD (``null``) in the shipped example — the loader must refuse each
    one individually, not just collectively (mutation M8's own "partially-filled file must
    refuse naming the offending leaf")."""
    path = write_policy(tmp_path, policy_yaml(overrides={key: f"{key}: null"}))
    with pytest.raises(CriticalInputPolicyConfigError, match=key):
        load_critical_input_policy(path, scheme=SCHEME)


def test_blank_string_refuses(tmp_path: Path) -> None:
    path = write_policy(tmp_path, policy_yaml(overrides={"policy_id": 'policy_id: ""'}))
    with pytest.raises(CriticalInputPolicyConfigError, match="policy_id"):
        load_critical_input_policy(path, scheme=SCHEME)


#: policy_generation is excluded -- it is an int leaf (module _require_int), not a
#: string one, so "TBD" fails its own type check rather than the named-TBD guard.
_HEADER_STR_KEYS = tuple(k for k in _HEADER_KEYS if k != "policy_generation")


@pytest.mark.parametrize("key", _HEADER_STR_KEYS)
def test_named_tbd_placeholder_top_level_key_refuses(tmp_path: Path, key: str) -> None:
    """W-A A-0 round 2: every top-level string leaf feeds ``canonical_digest`` directly
    (module docstring) — an operator-typed ``"TBD"`` must never be sealed into it."""
    path = write_policy(tmp_path, policy_yaml(overrides={key: f'{key}: "TBD"'}))
    with pytest.raises(CriticalInputPolicyConfigError, match="template placeholder"):
        load_critical_input_policy(path, scheme=SCHEME)


def test_example_file_all_null_refuses() -> None:
    """M8: the loader's null/missing rejection must still bite on the shipped example — a
    mutation removing it would let an all-null, no-real-identity document load."""
    example_path = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "critical_input_policy.example.yaml"
    )
    assert (
        example_path.is_file()
    ), "fixture assumption: the example file ships at this path"
    with pytest.raises(CriticalInputPolicyConfigError):
        load_critical_input_policy(example_path, scheme=SCHEME)


# ===========================================================================
# ``fields:`` refusals
# ===========================================================================


def test_missing_fields_key_refuses(tmp_path: Path) -> None:
    path = write_policy(tmp_path, policy_yaml(fields_block=""))
    with pytest.raises(CriticalInputPolicyConfigError, match="fields"):
        load_critical_input_policy(path, scheme=SCHEME)


def test_null_fields_refuses(tmp_path: Path) -> None:
    path = write_policy(tmp_path, policy_yaml(fields_block="fields: null\n"))
    with pytest.raises(CriticalInputPolicyConfigError, match="fields"):
        load_critical_input_policy(path, scheme=SCHEME)


def test_fields_not_a_list_refuses(tmp_path: Path) -> None:
    """``fields:`` present and non-null but not a list at all (a mapping here) — distinct from
    ``test_missing_fields_key_refuses``/``test_null_fields_refuses`` (key absent/null) and from
    ``test_fields_entry_not_a_mapping_refuses`` below (a list whose *entry* is malformed).
    """
    path = write_policy(
        tmp_path, policy_yaml(fields_block="fields:\n  close: not-a-list\n")
    )
    with pytest.raises(CriticalInputPolicyConfigError, match="must be a list"):
        load_critical_input_policy(path, scheme=SCHEME)


def test_empty_fields_list_refuses(tmp_path: Path) -> None:
    """A policy admitting no field is almost certainly a misfill (module docstring), not a
    deliberate deny-all — refused outright rather than silently admitting nothing forever.
    """
    path = write_policy(tmp_path, policy_yaml(fields_block="fields: []\n"))
    with pytest.raises(CriticalInputPolicyConfigError, match="fields"):
        load_critical_input_policy(path, scheme=SCHEME)


def test_fields_entry_not_a_mapping_refuses(tmp_path: Path) -> None:
    path = write_policy(
        tmp_path, policy_yaml(fields_block="fields:\n  - just-a-string\n")
    )
    with pytest.raises(CriticalInputPolicyConfigError, match="mapping"):
        load_critical_input_policy(path, scheme=SCHEME)


@pytest.mark.parametrize(
    "key,sample",
    [("unit", "KRW"), ("scale", "minor"), ("multiplier", '"1"'), ("sign", '"1"')],
)
def test_field_entry_missing_str_key_refuses(
    tmp_path: Path, key: str, sample: str
) -> None:
    mutated = DEFAULT_FIELDS_BLOCK.replace(f"    {key}: {sample}\n", "", 1)
    path = write_policy(tmp_path, policy_yaml(fields_block=mutated))
    with pytest.raises(CriticalInputPolicyConfigError, match=key):
        load_critical_input_policy(path, scheme=SCHEME)


def test_field_entry_missing_field_key_refuses(tmp_path: Path) -> None:
    """Removing the list-item marker line while keeping the rest of the entry's keys still
    leaves a mapping the loader must reject for lacking ``field_key`` — the list marker itself
    (``  - ``) is preserved so the entry stays one list item, not two."""
    mutated = DEFAULT_FIELDS_BLOCK.replace("  - field_key: close\n", "  - \n", 1)
    path = write_policy(tmp_path, policy_yaml(fields_block=mutated))
    with pytest.raises(CriticalInputPolicyConfigError, match="field_key"):
        load_critical_input_policy(path, scheme=SCHEME)


def test_field_entry_missing_max_age_ms_refuses(tmp_path: Path) -> None:
    mutated = DEFAULT_FIELDS_BLOCK.replace("    max_age_ms: 5000\n", "", 1)
    path = write_policy(tmp_path, policy_yaml(fields_block=mutated))
    with pytest.raises(CriticalInputPolicyConfigError, match="max_age_ms"):
        load_critical_input_policy(path, scheme=SCHEME)


def test_non_positive_max_age_ms_refuses(tmp_path: Path) -> None:
    mutated = DEFAULT_FIELDS_BLOCK.replace("max_age_ms: 5000", "max_age_ms: 0", 1)
    path = write_policy(tmp_path, policy_yaml(fields_block=mutated))
    with pytest.raises(CriticalInputPolicyConfigError, match="max_age_ms"):
        load_critical_input_policy(path, scheme=SCHEME)


def test_negative_max_age_ms_refuses(tmp_path: Path) -> None:
    mutated = DEFAULT_FIELDS_BLOCK.replace("max_age_ms: 5000", "max_age_ms: -1", 1)
    path = write_policy(tmp_path, policy_yaml(fields_block=mutated))
    with pytest.raises(CriticalInputPolicyConfigError, match="max_age_ms"):
        load_critical_input_policy(path, scheme=SCHEME)


def test_duplicate_field_key_refuses(tmp_path: Path) -> None:
    duplicated = DEFAULT_FIELDS_BLOCK + (
        "  - field_key: close\n"
        "    unit: KRW\n"
        "    scale: minor\n"
        '    multiplier: "1"\n'
        '    sign: "1"\n'
        "    max_age_ms: 1000\n"
    )
    path = write_policy(tmp_path, policy_yaml(fields_block=duplicated))
    with pytest.raises(CriticalInputPolicyConfigError, match="duplicate"):
        load_critical_input_policy(path, scheme=SCHEME)
