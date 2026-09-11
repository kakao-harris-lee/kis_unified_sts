"""``tos_runtime.compose._egress_attestations`` tests (re-review finding F3,
2026-09-08). Hermetic — real config files under ``tmp_path`` / ``config_dir``,
a real composed runtime for the e2e refusal assertions (never a mock of the
gateway's own verify list).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos.egressgw.vocabulary import SendVerifyItem, VerifyOutcome
from tos_runtime.compose._egress_attestations import (
    EgressAttestationConfigError,
    EgressAttestations,
    load_egress_attestations,
)

from . import _fixtures as fx
from .conftest import write_approval_file
from .test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _valid_egress_attestations() -> dict:
    return {
        "venue_session_account_facts_current": {"attested": True},
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
    ],
    ids=[
        "venue_session_account_facts_current",
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
    [
        "account_instrument_action_allowed",
        "broker_constraint_generation_current",
        "restrictive_latch_state",
        "worst_credible_capacity",
    ],
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
# (i) restrictive_latch_state / worst_credible_capacity are no longer loaded
# from THIS config (TOS Phase 5 W3 plan §2 decision 6 — tos_runtime.safety.latch
# owns both now); the item-16 DENY_LATCHED-denies-send and
# worst-credible-capacity-is-descriptive-not-gating behaviors are unchanged at
# the kernel/gateway level, but exercising them end-to-end now requires a
# composed ``safety_mesh`` (or a fake RestrictiveLatchOwner/CapacityOwner pair)
# wired through ``compose/context.py`` (lane b's ``_safety_wiring.py`` —
# not yet landed as of this lane's own commit). ``tos_runtime.safety.latch``'s
# own unit tests (``tos/runtime/tests/safety/test_latch.py``) cover
# ``RestrictiveLatchOwner``/``CapacityOwner`` directly; a full compose e2e
# re-exercise of item 16 belongs with that wiring landing, not here.
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
# kernel round #2 K-4 (§2 decision 4) — link the kernel-side recount to the
# actual runtime attestation set (independent review round #1 LOW-3: the
# kernel's own test_the_package_recounts_the_actual_remaining_attestations
# (tos/tests/egressgw/test_egressgw_package.py) can only go red when the
# package docstring changes, not when this module's own attested field set
# does. This test closes that gap from the runtime side, so a field added
# to EgressAttestations without a matching kernel docstring update is caught
# somewhere.
#
# TOS Phase 5 W3 plan §2 decision 6 (this lane): the runtime attested set
# shrank from 3 fields to 1 (restrictive_latch_state / worst_credible_capacity
# moved to tos_runtime.safety.latch), but the KERNEL docstring recount stays at
# 3 this wave (kernel diff 0 — carried over to a future kernel round). The
# assertion below is therefore now a ONE-DIRECTION containment check (every
# runtime-attested field must be named in the kernel docstring), never exact
# set equality — the kernel docstring is allowed to still name more than the
# runtime actually attests, since it also still describes item 12/16 as a
# 3-field non-authoritative group pending that future kernel recount.
# ============================================================================


def test_the_attested_field_set_matches_the_kernel_docstrings_recount() -> None:
    """Every ``EgressAttestations`` field name must appear in the kernel's
    ``tos.egressgw`` package docstring recount (module docstring — a
    containment check, not exact equality, since the kernel docstring's own
    recount (3) has not yet been brought down to this runtime's shrunk
    attested set (1); TOS Phase 5 W3 plan §2 decision 6, kernel round #3
    carryover)."""
    import dataclasses

    import tos.egressgw

    attested_fields = {f.name for f in dataclasses.fields(EgressAttestations)}
    assert attested_fields == {"venue_session_account_facts_current"}
    doc = " ".join((tos.egressgw.__doc__ or "").split())
    for name in attested_fields:
        assert name in doc, (
            f"{name!r} is an EgressAttestations field but the kernel package docstring's "
            "recount does not name it — the two pins have drifted apart"
        )
