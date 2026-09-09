"""``tos_runtime.compose._egress_attestations`` tests (re-review finding F3,
2026-09-08). Hermetic — real config files under ``tmp_path`` / ``config_dir``,
a real composed runtime for the e2e refusal assertions (never a mock of the
gateway's own verify list).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos.egress import RestrictiveLatchState
from tos.egressgw.vocabulary import SendVerifyItem, VerifyOutcome
from tos_runtime.compose._egress_attestations import (
    EgressAttestationConfigError,
    load_egress_attestations,
)

from . import _fixtures as fx
from .conftest import write_approval_file
from .test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _valid_egress_attestations() -> dict:
    return {
        "venue_session_account_facts_current": {"attested": True},
        "restrictive_latch_state": {"clear": True},
        "worst_credible_capacity": {"value": 1},
    }


def _write(path: Path, content: dict) -> None:
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


# ============================================================================
# (iii) loader refuses a still-null (named-TBD) field, for every field
# ============================================================================


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw["venue_session_account_facts_current"].__setitem__(
            "attested", None
        ),
        lambda raw: raw["restrictive_latch_state"].__setitem__("clear", None),
        lambda raw: raw["worst_credible_capacity"].__setitem__("value", None),
    ],
    ids=[
        "venue_session_account_facts_current",
        "restrictive_latch_state.clear",
        "worst_credible_capacity.value",
    ],
)
def test_a_still_null_field_refuses_to_load(tmp_path: Path, mutate) -> None:
    raw = _valid_egress_attestations()
    mutate(raw)
    path = tmp_path / "egress_attestations.yaml"
    _write(path, raw)
    with pytest.raises(EgressAttestationConfigError):
        load_egress_attestations(path)


def test_missing_file_refuses_to_load(tmp_path: Path) -> None:
    with pytest.raises(EgressAttestationConfigError):
        load_egress_attestations(tmp_path / "does-not-exist.yaml")


# ============================================================================
# Retired items 6/12 keys — a config still carrying either refuses to load
# (TOS Phase 4 plan §2 decision 4: these are derived now, never attested)
# ============================================================================


@pytest.mark.parametrize(
    "stale_key",
    ["account_instrument_action_allowed", "broker_constraint_generation_current"],
)
def test_a_retired_derived_key_still_present_refuses_to_load(
    tmp_path: Path, stale_key: str
) -> None:
    raw = _valid_egress_attestations()
    raw[stale_key] = {"attested": True}
    path = tmp_path / "egress_attestations.yaml"
    _write(path, raw)
    with pytest.raises(EgressAttestationConfigError, match="no longer attestations"):
        load_egress_attestations(path)


# ============================================================================
# (i) restrictive_latch_state: clear: false -> the composed SendBoundaryContext
# carries the non-CLEAR latch, item 16 denies, zero transport calls.
# ============================================================================


def _run_to_send_boundary(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
):
    """Compose + run once + write the matching approval file + re-run —
    the same two-pass pattern ``test_one_synthetic_transport_handoff`` uses,
    shared here so each refusal test reaches the SAME send-boundary point
    a healthy attestation set would reach a real hand-off from."""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=proposal_digest,
        environment_label="non-live-test",
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    runtime.run_once((event,))
    return runtime


def test_refusing_latch_yields_zero_transport_calls_attributed_to_item_16(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    raw = _valid_egress_attestations()
    raw["restrictive_latch_state"] = {"clear": False}
    _write(config_dir / "egress_attestations.yaml", raw)

    runtime = _run_to_send_boundary(config_dir, data_dir, custody_root, tmp_path)
    assert runtime.transport.requests == ()
    assert len(runtime.gateway.verifications) >= 1
    verification = runtime.gateway.verifications[-1]
    assert verification.admitted is not True
    item16 = next(
        v for v in verification.verdicts if v.item is SendVerifyItem.CURRENTNESS
    )
    assert item16.outcome is VerifyOutcome.DENIED
    assert item16.native_verdict_value == RestrictiveLatchState.DENY_LATCHED.value


# ============================================================================
# (ii) each of the other individually-gating attested booleans, set to its
# refusing value -> zero transport calls, attributed to the correct item.
# ============================================================================


@pytest.mark.parametrize(
    "field,item",
    [
        (
            "venue_session_account_facts_current",
            SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION,
        ),
    ],
)
def test_refusing_boolean_attestation_yields_zero_transport_calls(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    field: str,
    item: SendVerifyItem,
) -> None:
    raw = _valid_egress_attestations()
    raw[field] = {"attested": False}
    _write(config_dir / "egress_attestations.yaml", raw)

    runtime = _run_to_send_boundary(config_dir, data_dir, custody_root, tmp_path)
    assert runtime.transport.requests == ()
    assert len(runtime.gateway.verifications) >= 1
    verification = runtime.gateway.verifications[-1]
    assert verification.admitted is not True
    matching = next(v for v in verification.verdicts if v.item is item)
    assert matching.outcome is not VerifyOutcome.SATISFIED


# ============================================================================
# worst_credible_capacity: NOT an independent gate (gateway.py's own
# _check_currentness only folds it into the DENIAL REASON TEXT when
# currentness already denies for another reason) -- proven here by showing
# an extreme value does NOT by itself block an otherwise-healthy hand-off.
# ============================================================================


def test_worst_credible_capacity_is_descriptive_not_gating(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    raw = _valid_egress_attestations()
    raw["worst_credible_capacity"] = {"value": 0}
    _write(config_dir / "egress_attestations.yaml", raw)

    runtime = _run_to_send_boundary(config_dir, data_dir, custody_root, tmp_path)
    assert len(runtime.transport.requests) == 1
