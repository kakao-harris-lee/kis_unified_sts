"""scrub_secret_fields determinism + nesting tests (design #40 D3-d; ADR-002-016 §16 line 426)."""

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
