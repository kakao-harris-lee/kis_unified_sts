"""``tos_runtime.compose._egress_coordinates`` tests (TOS Phase 4 작업 6 §2.1,
plan doc ``docs/plans/2026-09-08-tos-phase4-send-seal-plan.md``). Hermetic —
real config files under ``tmp_path`` / ``config_dir``, a real composed
runtime for the "single source of truth" assertions (never a mock of the
gateway's own coordinate set).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egress import EgressCoordinateSet
from tos_runtime.brokercap import BrokerScopeConfigError
from tos_runtime.compose._egress_coordinates import (
    EgressCoordinateConfigError,
    load_egress_coordinates,
)
from tos_runtime.compose._request_digest import CapsuleStandInDigest

from . import _fixtures as fx
from .conftest import write_approval_file
from .test_compose_root import _compose, _reach_trusted

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _valid_egress_coordinates() -> dict:
    return {
        "endpoint": {"value": "synthetic://paper/order"},
        "action": {"value": "NEW_ORDER"},
        "method": {"value": "SUBMIT"},
        "route_identity": {"value": "synthetic-route"},
        "credential_generation": {"value": 0},
        "broker_session_generation": {"value": 0},
        "egress_generation": {"value": 1},
        "active_principal": {"value": "egressgw-{environment_label}"},
        "capsule_terminus_fields": {"value": ["account", "instrument"]},
    }


def _write(path: Path, content: dict) -> None:
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


# ============================================================================
# Loader happy path
# ============================================================================


def test_loader_happy_path_and_environment_label_substitution(tmp_path: Path) -> None:
    path = tmp_path / "egress_coordinates.yaml"
    _write(path, _valid_egress_coordinates())

    loaded = load_egress_coordinates(path, environment_label="paper-env-7")

    assert loaded.endpoint == "synthetic://paper/order"
    assert loaded.action == "NEW_ORDER"
    assert loaded.method == "SUBMIT"
    assert loaded.route_identity == "synthetic-route"
    assert loaded.credential_generation == 0
    assert loaded.broker_session_generation == 0
    assert loaded.egress_generation == 1
    # {environment_label} substitution is the ONLY templating the loader
    # performs.
    assert loaded.active_principal == "egressgw-paper-env-7"
    assert loaded.capsule_terminus_fields == ("account", "instrument")


def test_active_principal_without_the_token_passes_through_unchanged(
    tmp_path: Path,
) -> None:
    raw = _valid_egress_coordinates()
    raw["active_principal"] = {"value": "fixed-principal-no-templating"}
    path = tmp_path / "egress_coordinates.yaml"
    _write(path, raw)

    loaded = load_egress_coordinates(path, environment_label="paper-env-7")

    assert loaded.active_principal == "fixed-principal-no-templating"


# ============================================================================
# Each key null (named-TBD) refuses to load, naming the key
# ============================================================================


@pytest.mark.parametrize(
    "field",
    [
        "endpoint",
        "action",
        "method",
        "route_identity",
        "credential_generation",
        "broker_session_generation",
        "egress_generation",
        "active_principal",
        "capsule_terminus_fields",
    ],
)
def test_a_still_null_field_refuses_to_load(tmp_path: Path, field: str) -> None:
    raw = _valid_egress_coordinates()
    raw[field] = {"value": None}
    path = tmp_path / "egress_coordinates.yaml"
    _write(path, raw)

    with pytest.raises(EgressCoordinateConfigError, match=field):
        load_egress_coordinates(path, environment_label="paper-env-7")


def test_missing_file_refuses_to_load(tmp_path: Path) -> None:
    with pytest.raises(EgressCoordinateConfigError):
        load_egress_coordinates(
            tmp_path / "does-not-exist.yaml", environment_label="paper-env-7"
        )


def test_not_a_mapping_refuses_to_load(tmp_path: Path) -> None:
    path = tmp_path / "egress_coordinates.yaml"
    path.write_text(yaml.safe_dump(["not", "a", "mapping"]), encoding="utf-8")
    with pytest.raises(EgressCoordinateConfigError):
        load_egress_coordinates(path, environment_label="paper-env-7")


# ============================================================================
# capsule_terminus_fields validation
# ============================================================================


def test_unknown_capsule_terminus_field_refuses_to_load(tmp_path: Path) -> None:
    raw = _valid_egress_coordinates()
    raw["capsule_terminus_fields"] = {"value": ["account", "not_a_real_field"]}
    path = tmp_path / "egress_coordinates.yaml"
    _write(path, raw)

    with pytest.raises(EgressCoordinateConfigError, match="not_a_real_field"):
        load_egress_coordinates(path, environment_label="paper-env-7")


def test_empty_capsule_terminus_fields_refuses_to_load(tmp_path: Path) -> None:
    raw = _valid_egress_coordinates()
    raw["capsule_terminus_fields"] = {"value": []}
    path = tmp_path / "egress_coordinates.yaml"
    _write(path, raw)

    with pytest.raises(EgressCoordinateConfigError):
        load_egress_coordinates(path, environment_label="paper-env-7")


def test_non_list_capsule_terminus_fields_refuses_to_load(tmp_path: Path) -> None:
    raw = _valid_egress_coordinates()
    raw["capsule_terminus_fields"] = {"value": "account"}
    path = tmp_path / "egress_coordinates.yaml"
    _write(path, raw)

    with pytest.raises(EgressCoordinateConfigError):
        load_egress_coordinates(path, environment_label="paper-env-7")


# ============================================================================
# Single source of truth — the wired EgressCoordinateSet/digest equal the
# loader output built from THIS SAME config file (mutation M-R1 catcher):
# if a caller ever reverts to a hardcoded literal that diverges from a
# custom config value, this test goes red.
# ============================================================================


def test_wired_coordinates_equal_the_configured_non_default_values(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    custom = {
        "endpoint": {"value": "synthetic://custom/endpoint"},
        "action": {"value": "CUSTOM_ACTION"},
        "method": {"value": "CUSTOM_METHOD"},
        "route_identity": {"value": "custom-route"},
        "credential_generation": {"value": 7},
        "broker_session_generation": {"value": 3},
        "egress_generation": {"value": 9},
        "active_principal": {"value": "custom-{environment_label}"},
        "capsule_terminus_fields": {"value": ["account", "instrument"]},
    }
    _write(config_dir / "egress_coordinates.yaml", custom)

    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    resolved = runtime.context_resolver

    assert resolved.authorized_coordinates == EgressCoordinateSet(
        endpoint="synthetic://custom/endpoint",
        account=runtime.context_resolver.instrument_key.account,
        environment="non-live-test",
        action="CUSTOM_ACTION",
        method="CUSTOM_METHOD",
        route_identity="custom-route",
        credential_generation=7,
        broker_session_generation=3,
        egress_generation=9,
        active_principal="custom-non-live-test",
    )

    # Review follow-up finding #1b (2026-09-09): credential_route_inventory's
    # gateway-principal entry was ALSO hardcoded to
    # ``f"egressgw-{environment_label}"`` in ``_wiring.py`` — the same
    # identity finding #1 already single-sourced for ``context.principal``
    # above. A caller reverting either line back to its own literal would
    # silently leave the inventory keyed to a DIFFERENT principal than the
    # one that actually appears as ``context.principal`` / ``seal.
    # claim_principal``, defeating ``credential_route_authority_disjoint``'s
    # ability to corroborate the gateway's own transport. Assert the
    # inventory carries an entry for the SAME principal as
    # ``resolved.principal`` (not a second, independently-templated
    # literal that merely happens to match the fixture default).
    matching_inventory_principals = [
        entry.principal
        for entry in resolved.credential_route_inventory
        if entry.principal == resolved.principal
    ]
    assert matching_inventory_principals == [resolved.principal]

    # T2 lane A: the DEFAULT ``request_bytes_digest_source`` is still the unchanged
    # capsule-terminus stand-in — same constant, same computation, now wrapped in
    # ``CapsuleStandInDigest`` rather than assigned to a bare field.
    assert isinstance(resolved.request_bytes_digest_source, CapsuleStandInDigest)
    assert resolved.request_bytes_digest_source.digest == _SCHEME.compute_digest(
        {
            "account": runtime.context_resolver.instrument_key.account,
            "instrument": runtime.context_resolver.instrument_key.instrument,
        }
    )

    # Review finding #1 (2026-09-09): the M-R1 catcher above proved the
    # *static* coordinate set matches this non-default config, but stopped
    # at ``_compose(...)`` and never reached a send — which is exactly why
    # it missed that ``_wiring.py`` still hardcoded ``context.principal`` to
    # ``f"egressgw-{environment_label}"`` while ``active_principal`` (here,
    # ``"custom-non-live-test"``) came from this same config. The kernel's
    # ``_claim_principal_matches_active_principal`` validator requires
    # ``seal.claim_principal`` (sourced from ``context.principal``) to equal
    # ``seal.active_principal`` (sourced from ``authorized_coordinates.
    # active_principal``); with the literal, this diverging config used to
    # refuse EVERY send at the seal (reviewer probe:
    # ``halt_reasons == ["SEND_SEAL_UNCONSTRUCTABLE"]``,
    # ``transport requests == 0``). Run to the real synthetic hand-off and
    # assert the opposite.
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

    rows = runtime.evidence_store.connection.execute(
        "SELECT kind, payload_json FROM entries ORDER BY seq ASC"
    ).fetchall()
    halt_reasons = [
        json.loads(payload_json)["payload"].get("halt_reason")
        for kind, payload_json in rows
        if kind == "SEND_REFUSED"
    ]
    assert "SEND_SEAL_UNCONSTRUCTABLE" not in halt_reasons, halt_reasons
    assert len(runtime.transport.requests) == 1

    # Review finding #5 (2026-09-09): the QCC G-3 stand-in used to hardcode
    # ``egress_generation=1`` regardless of config (`context.py`'s
    # ``_quorum_certificate_for_command``), while `authorized_coordinates.
    # egress_generation` (this config's ``9``) came from the same loader.
    # Nothing compared the two, so the issued
    # ``QuorumCommitCertificate.egress_generation`` silently drifted from
    # what the operator configured. Assert both read the SAME config value.
    issued_contexts = [c for c in runtime.context_resolver.contexts if c is not None]
    assert issued_contexts, "expected at least one resolved SendBoundaryContext"
    qcc = issued_contexts[-1].quorum_commit_certificate
    assert qcc is not None
    assert qcc.egress_generation == 9

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_active_principal_matching_the_transport_identity_refuses_to_compose(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """(re-review residual R2, 2026-09-09) Finding #1's fix made the gateway
    principal (``context.principal`` / ``authorized_coordinates.
    active_principal``) config-driven, which opened a new degenerate-config
    surface with no guard: an operator can set ``active_principal`` to the
    exact string the transport's OWN identity is templated to
    (``TransportNature.principal``, then the literal
    ``f"synthetic-paper-{environment_label}"`` in ``_wiring.py``). Before
    finding #1's fix this collision was unreachable (the gateway principal
    was a different hardcoded literal); now it is one config edit away.

    **G-4 CLOSED (TOS Phase 4 plan §2 decision 2,
    docs/plans/2026-09-09-tos-phase4-scopes-and-verify-realization-plan.md):**
    the transport's own identity is no longer a ``_wiring.py`` literal — it
    is the ``SYNTHETIC_FUTURES_ORDER`` scope's own configured ``principal``
    (``tos_runtime.brokercap.scopes.BrokerScope``), and the refusal below is
    now :func:`~tos_runtime.brokercap.refuse_principal_collision` (raising
    :class:`~tos_runtime.brokercap.BrokerScopeConfigError`), generalized
    from ONE hardcoded comparison to every configured scope's principal —
    the fixture's ``broker_scopes.yaml`` (conftest.py) still templates that
    scope's principal to ``f"synthetic-paper-{environment_label}"``, so the
    degenerate config below still collides exactly as before.

    Conflating the gateway's workload identity with the transport's own
    identity is exactly what ADR-002-013 §8's "non-transferable workload
    identity" exists to forbid, so composition refuses fail-closed rather
    than silently letting the two collide.
    """
    degenerate = _valid_egress_coordinates()
    degenerate["active_principal"] = {"value": "synthetic-paper-{environment_label}"}
    _write(config_dir / "egress_coordinates.yaml", degenerate)

    with pytest.raises(BrokerScopeConfigError, match="synthetic-paper-non-live-test"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


def test_no_authorized_coordinate_literal_remains_in_wiring_source() -> None:
    """ "No literal" grep test (Part 1 test list) — the eight authorized-
    coordinate values (review finding #2, 2026-09-09: ``endpoint`` joined
    the other seven) must come from config only, never a bare literal in
    ``_wiring.py``."""
    import tos_runtime.compose._wiring as wiring_module

    source = Path(wiring_module.__file__).read_text(encoding="utf-8")
    for literal in (
        '"synthetic://paper/order"',
        '"synthetic-route"',
        "NEW_ORDER",
        "SUBMIT",
        "credential_generation=0",
        "egress_generation=1",
    ):
        assert literal not in source, f"literal {literal!r} still present in _wiring.py"
