"""scrub_secret_fields determinism + nesting tests (design #40 D3-d; ADR-002-016 §16 line 426).

Includes list/tuple recursion coverage added 2026-09-08 after an independent
review found secrets nested inside list/tuple elements passed through unmasked
(the fix lives in ``tos/src/tos/evidence/scrub.py``'s module docstring "Container
recursion" note)."""

from __future__ import annotations

from tos.evidence import scrub_secret_fields

_SECRETS = frozenset({"api_key", "session_cookie"})


def test_no_matching_key_leaves_payload_unchanged_with_empty_masked_tuple() -> None:
    payload = {"symbol": "005930", "quantity": 10}
    scrubbed, masked = scrub_secret_fields(payload, _SECRETS)
    assert scrubbed == payload
    assert scrubbed is not payload  # a fresh copy, not the same object
    assert masked == ()


def test_top_level_secret_is_masked() -> None:
    payload = {"api_key": "sk-abc123", "symbol": "005930"}
    scrubbed, masked = scrub_secret_fields(payload, _SECRETS)
    assert scrubbed["api_key"] == "***REDACTED***"
    assert scrubbed["symbol"] == "005930"
    assert masked == ("api_key",)


def test_nested_secret_is_masked_with_dotted_path() -> None:
    payload = {"credentials": {"api_key": "sk-abc123", "region": "kr"}}
    scrubbed, masked = scrub_secret_fields(payload, _SECRETS)
    assert scrubbed["credentials"]["api_key"] == "***REDACTED***"
    assert scrubbed["credentials"]["region"] == "kr"
    assert masked == ("credentials.api_key",)


def test_deeply_nested_and_multiple_secrets_are_masked_sorted() -> None:
    payload = {
        "session_cookie": "sc-xyz",
        "auth": {"api_key": "sk-abc123", "nested": {"api_key": "sk-def456"}},
    }
    scrubbed, masked = scrub_secret_fields(payload, _SECRETS)
    assert scrubbed["session_cookie"] == "***REDACTED***"
    assert scrubbed["auth"]["api_key"] == "***REDACTED***"
    assert scrubbed["auth"]["nested"]["api_key"] == "***REDACTED***"
    assert masked == ("auth.api_key", "auth.nested.api_key", "session_cookie")


def test_empty_secret_keys_never_masks_anything() -> None:
    payload = {"api_key": "sk-abc123"}
    scrubbed, masked = scrub_secret_fields(payload, frozenset())
    assert scrubbed == payload
    assert masked == ()


def test_empty_payload_is_unchanged() -> None:
    scrubbed, masked = scrub_secret_fields({}, _SECRETS)
    assert scrubbed == {}
    assert masked == ()


def test_scrubbing_is_deterministic_across_repeated_calls() -> None:
    payload = {
        "session_cookie": "sc-xyz",
        "auth": {"api_key": "sk-abc123"},
        "symbol": "005930",
    }
    first_scrubbed, first_masked = scrub_secret_fields(payload, _SECRETS)
    second_scrubbed, second_masked = scrub_secret_fields(payload, _SECRETS)
    assert first_scrubbed == second_scrubbed
    assert first_masked == second_masked


def test_non_mapping_nested_value_is_left_untouched_when_not_secret() -> None:
    payload = {"tags": ["a", "b"], "count": 3, "ratio": 1.5}
    scrubbed, masked = scrub_secret_fields(payload, _SECRETS)
    assert scrubbed == payload
    assert masked == ()


# ===========================================================================
# list/tuple recursion (independent-review HIGH finding, fixed 2026-09-08:
# an earlier revision recursed only into Mapping, so a secret nested inside a
# list/tuple element passed through unmasked)
# ===========================================================================


def test_secret_inside_list_element_mapping_is_masked() -> None:
    """Repro of the reported gap: scrub_secret_fields({"accounts":
    [{"api_key": "SECRET"}]}, {"api_key"}) must mask it, not return masked=()."""
    payload = {"accounts": [{"api_key": "SECRET", "region": "kr"}]}
    scrubbed, masked = scrub_secret_fields(payload, _SECRETS)
    assert scrubbed["accounts"][0]["api_key"] == "***REDACTED***"
    assert scrubbed["accounts"][0]["region"] == "kr"
    assert masked == ("accounts[0].api_key",)


def test_secret_inside_tuple_element_mapping_is_masked() -> None:
    payload = {"accounts": ({"api_key": "SECRET"},)}
    scrubbed, masked = scrub_secret_fields(payload, _SECRETS)
    assert scrubbed["accounts"][0]["api_key"] == "***REDACTED***"
    assert masked == ("accounts[0].api_key",)


def test_list_container_type_is_preserved_on_output() -> None:
    payload = {"accounts": [{"api_key": "SECRET"}]}
    scrubbed, _ = scrub_secret_fields(payload, _SECRETS)
    assert isinstance(scrubbed["accounts"], list)


def test_tuple_container_type_is_preserved_on_output() -> None:
    payload = {"accounts": ({"api_key": "SECRET"},)}
    scrubbed, _ = scrub_secret_fields(payload, _SECRETS)
    assert isinstance(scrubbed["accounts"], tuple)


def test_multiple_list_elements_masked_with_correct_index_in_path() -> None:
    payload = {
        "accounts": [
            {"api_key": "SECRET-0", "id": "a"},
            {"api_key": "SECRET-1", "id": "b"},
        ]
    }
    scrubbed, masked = scrub_secret_fields(payload, _SECRETS)
    assert scrubbed["accounts"][0]["api_key"] == "***REDACTED***"
    assert scrubbed["accounts"][1]["api_key"] == "***REDACTED***"
    assert scrubbed["accounts"][0]["id"] == "a"
    assert scrubbed["accounts"][1]["id"] == "b"
    assert masked == ("accounts[0].api_key", "accounts[1].api_key")


def test_mixed_depth_list_inside_mapping_inside_list_is_masked() -> None:
    """Mixed nesting: mapping -> list -> mapping -> list -> mapping, secret at
    the bottom, plus a top-level secret and an untouched sibling at every level."""
    payload = {
        "session_cookie": "top-secret",
        "groups": [
            {
                "label": "g0",
                "members": [
                    {"name": "m0", "api_key": "SECRET-DEEP"},
                    {"name": "m1"},
                ],
            }
        ],
    }
    scrubbed, masked = scrub_secret_fields(payload, _SECRETS)
    assert scrubbed["session_cookie"] == "***REDACTED***"
    assert scrubbed["groups"][0]["label"] == "g0"
    assert scrubbed["groups"][0]["members"][0]["api_key"] == "***REDACTED***"
    assert scrubbed["groups"][0]["members"][0]["name"] == "m0"
    assert scrubbed["groups"][0]["members"][1] == {"name": "m1"}
    assert masked == ("groups[0].members[0].api_key", "session_cookie")


def test_non_secret_inside_list_is_left_untouched() -> None:
    """Negative control: a list containing non-secret mappings/scalars is
    returned structurally unchanged with an empty masked tuple."""
    payload = {"accounts": [{"region": "kr"}, {"region": "us"}], "tags": ["a", "b"]}
    scrubbed, masked = scrub_secret_fields(payload, _SECRETS)
    assert scrubbed == payload
    assert masked == ()


def test_scrubbing_list_and_tuple_nesting_is_deterministic_across_repeated_calls() -> (
    None
):
    payload = {
        "accounts": [{"api_key": "SECRET-0"}, {"api_key": "SECRET-1"}],
        "sessions": ({"session_cookie": "sc-xyz"},),
    }
    first_scrubbed, first_masked = scrub_secret_fields(payload, _SECRETS)
    second_scrubbed, second_masked = scrub_secret_fields(payload, _SECRETS)
    assert first_scrubbed == second_scrubbed
    assert first_masked == second_masked
    assert first_masked == (
        "accounts[0].api_key",
        "accounts[1].api_key",
        "sessions[0].session_cookie",
    )
