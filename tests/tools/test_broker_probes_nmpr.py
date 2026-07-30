"""Unit tests for the P-NMPR probe (``tools/broker_probes``).

P-NMPR is an order-emitting probe: a mistake here places real 모의투자 orders.
These tests therefore guard the two properties that cannot be checked by reading
the code at review time:

1. **The dry-run path opens no socket.** Both transports the probe could use
   (``MockTradingClient`` and ``common.http_json``) are replaced with sentinels
   that raise on contact, so a regression that moved the ``--confirm`` gate would
   fail loudly instead of quietly reaching the broker.
2. **The A/B arms differ in exactly the two fields under test.** If any other
   field drifted between the arms, an observed difference would no longer be
   attributable to the blank-vs-explicit question the probe exists to answer.

Registry metadata gets the same treatment, because a wrong ``instance_fields``
entry does not fail at runtime — it silently mis-files evidence against a
capability the probe never measured (runbook §4.1).
"""

from __future__ import annotations

import argparse

import pytest

from tools.broker_probes.common import ProbeCredentials, ProbeError, ProbeRun
from tools.broker_probes.probes_order import (
    MockTradingClient,
    TickPrice,
    _futures_tick,
    probe_nmpr_ab,
    snap_to_tick,
)
from tools.broker_probes.registry import PROBES, coverage_report, get

_ACCOUNT = "1234567890"


@pytest.fixture
def mock_creds() -> ProbeCredentials:
    """Credentials for a 모의투자 futures account (never real)."""
    return ProbeCredentials(
        app_key="test-key",
        app_secret="test-secret",
        account_no=_ACCOUNT,
        is_real=False,
        asset="futures",
    )


@pytest.fixture
def futures_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Export exactly the env vars ``resolve_credentials`` reads."""
    monkeypatch.setenv("KIS_FUTURES_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_FUTURES_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", _ACCOUNT)
    monkeypatch.delenv("KIS_TOKEN_CACHE_DIR", raising=False)


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "symbol": "101S6000",
        "asset": "futures",
        "confirm": False,
        "quantity": 1,
        "price_offset_pct": 10.0,
        "inter_trial_s": 1.0,
        "settle_seconds": 2.0,
        "token_cache_dir": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _tick_price(price: float) -> TickPrice:
    """A resting price snapped the way the probes snap one (tick from the YAML SoT)."""
    return snap_to_tick(price, _futures_tick("101S6000"), side="BUY", marketable=False)


def _client(creds: ProbeCredentials) -> MockTradingClient:
    """A client instance for body-shape tests only — it issues no request."""
    run = ProbeRun(probe_id="P-NMPR", title="t", mode="dry-run", environment="MOCK_VTS")
    return MockTradingClient(creds, auth_manager=object(), run=run)


# ---------------------------------------------------------------------------
# registry metadata
# ---------------------------------------------------------------------------


def test_registry_entry_is_order_emitting_and_confirm_gated() -> None:
    spec = get("P-NMPR")
    assert spec.kind == "ORDER"
    assert spec.environment == "MOCK_VTS"
    assert spec.emits_orders is True
    assert spec.requires_confirm is True
    assert spec.risk == "HIGH"
    assert spec.supported is True
    assert spec.entrypoint == "tools.broker_probes.probes_order:probe_nmpr_ab"


def test_registry_lookup_is_case_and_separator_insensitive() -> None:
    assert get("p-nmpr") is get("P-NMPR") is get("P_NMPR")


def test_probe_claims_no_verification_profile_bound() -> None:
    """P-NMPR is categorical; it produces no latency bound candidate."""
    assert get("P-NMPR").bounds_keys == ()


def test_instance_fields_are_the_command_construction_pair() -> None:
    """The probe must claim only what it can establish (runbook §4.1/§4.3)."""
    assert get("P-NMPR").instance_fields == (
        "capabilities.command_construction_and_wire_semantics.required_and_default_field_semantics",
        "capabilities.command_construction_and_wire_semantics.duplicate_unknown_and_omitted_field_behavior",
    )


def test_probe_does_not_claim_the_tif_value_set() -> None:
    """Neither arm sends IOC (3) or FOK (4), so the TIF set stays N-17's finding."""
    assert "live_scope.time_in_force_values" not in get("P-NMPR").instance_fields


def test_dimension_reuses_an_existing_taxonomy_member() -> None:
    """No 18th CapabilityDimension: the enum has 17 members and
    ``command_construction_and_wire_semantics`` has no dimension of its own."""
    ratified = {
        spec.dimension
        for spec in PROBES.values()
        if spec.source.startswith(("draft", "plan"))
    }
    assert get("P-NMPR").dimension in ratified
    assert get("P-NMPR").dimension == get("N-17").dimension


def test_followup_probe_does_not_inflate_the_ratified_counts() -> None:
    """P-NMPR sits outside the ratified 12+4; ``--coverage`` must still say 12/4."""
    report = coverage_report()
    assert report["canonical_count"] == 12
    assert report["census_count"] == 4
    assert "P-NMPR" not in report["canonical_12"]
    assert "P-NMPR" not in report["census_4"]
    assert "P-NMPR" in report["order_emitting"]


# ---------------------------------------------------------------------------
# request-body shapes
# ---------------------------------------------------------------------------


def test_explicit_arm_matches_the_official_enumeration(
    mock_creds: ProbeCredentials,
) -> None:
    """01=지정가 / 0=없음 per the official ``order.py`` docstring (v1_국내선물-001)."""
    body = _client(mock_creds).futures_order_body(
        "101S6000", 1, _tick_price(340.0), "BUY"
    )
    assert body["NMPR_TYPE_CD"] == "01"
    assert body["KRX_NMPR_CNDT_CD"] == "0"
    assert body["ORD_DVSN_CD"] == "01"


def test_legacy_blank_arm_reproduces_the_pre_fix_body(
    mock_creds: ProbeCredentials,
) -> None:
    body = _client(mock_creds).futures_order_body(
        "101S6000", 1, _tick_price(340.0), "BUY", required_fields="legacy_blank"
    )
    assert body["NMPR_TYPE_CD"] == ""
    assert body["KRX_NMPR_CNDT_CD"] == ""


def test_arms_differ_in_exactly_the_two_fields_under_test(
    mock_creds: ProbeCredentials,
) -> None:
    """The attributability invariant the probe asserts at runtime."""
    client = _client(mock_creds)
    body_a = client.futures_order_body("101S6000", 1, _tick_price(340.0), "BUY")
    body_b = client.futures_order_body(
        "101S6000", 1, _tick_price(340.0), "BUY", required_fields="legacy_blank"
    )
    assert body_a.keys() == body_b.keys()
    differing = sorted(k for k in body_a if body_a[k] != body_b[k])
    assert differing == ["KRX_NMPR_CNDT_CD", "NMPR_TYPE_CD"]


def test_unknown_required_fields_mode_is_refused(
    mock_creds: ProbeCredentials,
) -> None:
    """Fail-closed: an unrecognised mode must not fall back to a blank body."""
    with pytest.raises(ProbeError, match="unknown required_fields mode"):
        _client(mock_creds).futures_order_body(
            "101S6000", 1, _tick_price(340.0), "BUY", required_fields="typo"
        )


# ---------------------------------------------------------------------------
# dry-run safety
# ---------------------------------------------------------------------------


def test_dry_run_contacts_no_broker(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """Without ``--confirm`` the probe must not construct a client or transport."""

    def _explode(*args: object, **kwargs: object) -> object:
        raise AssertionError("dry-run attempted broker contact")

    monkeypatch.setattr("tools.broker_probes.probes_order.MockTradingClient", _explode)
    monkeypatch.setattr("tools.broker_probes.common.http_json", _explode)

    run = probe_nmpr_ab(_args())

    assert run.mode == "dry-run"
    assert run.errors == []
    assert run.measurements == {}
    assert any("would_send" in obs for obs in run.observations)


def test_dry_run_reports_both_arms(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    monkeypatch.setattr(
        "tools.broker_probes.probes_order.MockTradingClient",
        lambda *a, **k: pytest.fail("dry-run built a client"),
    )
    run = probe_nmpr_ab(_args())
    said = " ".join(str(obs.get("would_send", "")) for obs in run.observations)
    assert "explicit" in said and "blank" in said


def test_non_futures_asset_is_refused(futures_env: None) -> None:
    """Stock has no NMPR fields at all; the probe is futures-only."""
    with pytest.raises(ProbeError, match="futures-only"):
        probe_nmpr_ab(_args(asset="stock"))


def test_missing_symbol_is_refused(futures_env: None) -> None:
    with pytest.raises(ProbeError, match="--symbol is required"):
        probe_nmpr_ab(_args(symbol=""))
