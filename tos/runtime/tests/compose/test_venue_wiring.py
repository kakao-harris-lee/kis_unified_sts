"""Compose e2e tests for :mod:`tos_runtime.compose._venue_wiring` (TOS venue constraint
service wave, ``docs/plans/2026-09-15-tos-venue-constraint-service-plan.md`` §5).

Hermetic (D1.4): real sqlite files under ``tmp_path``, real custody files this suite's own
``conftest.py``/``_fixtures.py`` create with 0600 + uid. Every negative-path test here builds
its OWN fresh ``(config_dir, data_dir, custody_root)`` triple (mirroring
``test_symmetry.py``'s own ``_fresh_compose_dirs``) so it can mutate the governed policy /
activation files without disturbing the happy-path ``config_dir`` fixture every other compose
e2e test relies on.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egressgw import fold_venue_admissibility
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose._venue_wiring import VenuePolicyScopeMismatch
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.venue import PolicyNotActivated

from ..venue._documents import ocp_yaml, venue_policy_yaml
from . import _fixtures as fx
from .conftest import (
    _VENUE_POLICY_ACCOUNT,
    _VENUE_POLICY_ADMITTING_PHASE,
    _VENUE_POLICY_ENVIRONMENT,
    _VENUE_POLICY_INSTRUMENT,
    _VENUE_POLICY_INSTRUMENT_CLASS,
)
from .conftest import config_dir as _config_dir_fixture
from .conftest import custody_root as _custody_root_fixture
from .conftest import data_dir as _data_dir_fixture
from .test_compose_root import (
    _action_flow_inputs,
    _aggregate_inputs,
    _compose,
    _reach_trusted,
)
from .test_transport_wiring import _activate_mock_stock_order

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _fresh_compose_dirs(root: Path) -> tuple[Path, Path, Path]:
    """Mirrors ``test_symmetry.py``'s own helper — one independent
    ``(config_dir, data_dir, custody_root)`` triple, built via the SAME fixture-writing logic
    every other compose e2e test uses (called through ``__wrapped__`` since pytest refuses a
    fixture function called directly)."""
    root.mkdir(parents=True, exist_ok=True)
    config_dir = _config_dir_fixture.__wrapped__(root)
    data_dir = _data_dir_fixture.__wrapped__(root)
    custody_root = _custody_root_fixture.__wrapped__(root)
    return config_dir, data_dir, custody_root


def _rewrite_activation(config_dir: Path, members: list[dict[str, object]]) -> None:
    """Overwrite ``safety_activation.yaml``'s own ``members:`` list, keeping every other key
    (the ``activation:``/``not_expired:`` blocks) exactly as ``conftest.py`` wrote them.
    """
    path = config_dir / "safety_activation.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["members"] = members
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _real_members(config_dir: Path) -> list[dict[str, object]]:
    """The two REAL member rows ``conftest.py`` wrote — read back rather than re-derived, so a
    mutation test changes exactly one field of a genuinely-activating pair."""
    raw = yaml.safe_load(
        (config_dir / "safety_activation.yaml").read_text(encoding="utf-8")
    )
    members = raw["members"]
    assert isinstance(members, list) and len(members) == 2
    return [dict(m) for m in members]


def _sync_venue_activation_digest(config_dir: Path) -> None:
    """Re-load ``venue_constraint_policy.yaml`` (as it stands NOW, after a test's own
    mutation) and rewrite ``safety_activation.yaml``'s ``VENUE_CONSTRAINT_POLICY`` member
    digest to match — a scope/admitting-phase mutation test wants to reach the scope/calendar
    cross-check itself, not an (unrelated) activation-digest refusal, since changing the
    policy's own content also changes its freshly-computed digest."""
    from tos_runtime.venue import load_venue_constraint_policy

    loaded = load_venue_constraint_policy(
        config_dir / "venue_constraint_policy.yaml", scheme=_SCHEME
    )
    members = _real_members(config_dir)
    for member in members:
        if member["kind"] == "VENUE_CONSTRAINT_POLICY":
            member["digest"] = loaded.policy.canonical_digest
    _rewrite_activation(config_dir, members)


def _compose_with_construction(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    construction,
):
    """Mirrors ``test_compose_root.py``'s own ``_compose`` but takes a caller-supplied
    ``construction`` (that helper hardcodes ``fx.construction_config()``) — used by the (a′)
    wave's order-shape sourcing tests below to mutate the injected literal shape / envelope
    independently of the shared happy-path fixture every other e2e test in this file relies
    on."""
    fx.write_band_strategy_file(config_dir)
    return compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=construction,
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs,
        transport_kind=TransportKind.SYNTHETIC,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )


def _kind_count(runtime, kind: str) -> int:
    return runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
    ).fetchone()[0]


def _rows(runtime, kind: str) -> list[dict]:
    cursor = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
    )
    return [json.loads(row[0])["payload"] for row in cursor.fetchall()]


# ===========================================================================
# e2e (1)-(5) — plan §5 실증
# ===========================================================================


class TestVenueServiceE2E:
    def test_boot_binds_the_policies_once_and_step3_admits_with_the_real_decision(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        assert _kind_count(runtime, "VENUE_POLICY_BOUND") == 1
        assert _kind_count(runtime, "ORDER_CONSTRUCTION_POLICY_BOUND") == 1

        results = runtime.run_once((fx.crossing_event(),))
        assert results[0].flow is not None
        verdicts = {v.step: v for v in results[0].flow.verdicts}
        step3 = verdicts[CommitmentStep.VENUE_ADMISSIBILITY_DECISION]
        assert step3.outcome is StageOutcome.ADMIT

        decision = runtime.venue.last_decision
        assert decision is not None
        snapshot = runtime.venue.last_snapshot
        assert snapshot is not None
        fold = fold_venue_admissibility(
            observed_session_phase=snapshot.observed_session_phase,
            action_class=fx.ActionClass.NEW_LONG,
            snapshot=snapshot,
            policy=runtime.venue.policy,
            shape=runtime.venue_stage.resolved_shape,
            constraints=runtime.venue.shape_constraints,
        )
        assert decision.result is fold

        # HIGH-2 (team-lead review, 2026-09-15): the returned StageVerdict must bind the REAL
        # issued decision's own digest/identity — a mutation that returns stage0's verdict
        # (built with decision=None, before the real decision was issued) would leave
        # bound_digest/bound_identity None here (tos.engine.adapters.venue_admissibility_verdict
        # sets both from `decision`, `tos/src/tos/engine/adapters.py:105-106`).
        assert step3.bound_digest is not None
        assert step3.bound_digest == decision.canonical_digest
        assert step3.bound_identity == decision.decision_id

        # HIGH-1 (team-lead review, 2026-09-15): this scope (SYNTHETIC_FUTURES_ORDER) declares
        # no `instance:` block at all (config/broker_scopes.example.yaml) — pin that premise so
        # this test fails loudly if the fixture ever binds one — and the decision's own
        # broker-capability fields must stay honestly None, never an invented "draft" digest.
        assert runtime.context_resolver.instance_document is None
        assert decision.broker_capability_profile_version is None
        assert decision.broker_capability_profile_digest is None

        construction = runtime.construction_stage.construction
        assert construction is not None and construction.command is not None
        assert (
            decision.candidate_command_digest == construction.command.canonical_digest
        )

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_two_attempts_same_tick_issue_one_snapshot_and_two_decisions(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        event = fx.crossing_event()
        runtime.run_once((event,))
        runtime.run_once((event,))

        assert _kind_count(runtime, "VENUE_SNAPSHOT_ISSUED") == 1
        assert _kind_count(runtime, "ORDER_ADMISSIBILITY_DECISION_ISSUED") == 2
        # Both decisions reference the SAME (one) issued snapshot — same constraint generation.
        snapshot_ids = {
            row["snapshot_id"]
            for row in _rows(runtime, "ORDER_ADMISSIBILITY_DECISION_ISSUED")
        }
        assert len(snapshot_ids) == 1

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_closed_phase_instant_denies_step3(
        self, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        # A Saturday: the conftest.py calendar is open 24/7 (every weekday incl. SAT/SUN), so
        # narrow it here to a weekday-only window (mirrors test_session_wiring.py's own
        # `_write_narrow_calendar`) — the SAME "CONTINUOUS" phase token stays declared (the
        # venue policy's own admitting_phases cross-check must still pass at boot), only the
        # window during which it is OBSERVED narrows.
        (config_dir / "calendar.yaml").write_text(
            yaml.safe_dump(
                {
                    "calendar_version": "cal-compose-0",
                    "tz_id": "Asia/Seoul",
                    "holidays": [],
                    "sessions": {
                        fx.INSTRUMENT_CLASS: [
                            {
                                "phase": _VENUE_POLICY_ADMITTING_PHASE,
                                "start": "09:00",
                                "end": "15:30",
                                "days": ["MON", "TUE", "WED", "THU", "FRI"],
                                "crosses_midnight": False,
                            }
                        ]
                    },
                    "closed_phase": "CLOSED",
                    "futures_expiry": {},
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        saturday_kst = 1_789_779_600_000  # 2026-09-19 10:00 KST
        fx.write_band_strategy_file(config_dir)
        runtime = compose_paper_runtime(
            config_dir,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=_aggregate_inputs,
            action_flow_inputs_provider=_action_flow_inputs,
            transport_kind=TransportKind.SYNTHETIC,
            wall_clock=FixedWallClockReference(saturday_kst),
        )
        _reach_trusted(runtime)

        results = runtime.run_once((fx.crossing_event(),))
        assert results[0].flow is not None
        verdicts = {v.step: v for v in results[0].flow.verdicts}
        step3 = verdicts[CommitmentStep.VENUE_ADMISSIBILITY_DECISION]
        assert step3.outcome is not StageOutcome.ADMIT
        assert runtime.venue.last_snapshot is not None
        assert runtime.venue.last_snapshot.observed_session_phase == "CLOSED"

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_recompose_over_the_same_data_dir_strictly_increases_constraint_generation(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        runtime.run_once((fx.crossing_event(),))
        first_generation = runtime.venue.last_snapshot.constraint_generation  # type: ignore[union-attr]
        runtime.rcl_log.close()
        runtime.evidence_store.close()

        runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime2)
        runtime2.run_once((fx.crossing_event(),))
        second_generation = runtime2.venue.last_snapshot.constraint_generation  # type: ignore[union-attr]
        assert second_generation > first_generation

        runtime2.rcl_log.close()
        runtime2.evidence_store.close()

    def test_print_policy_digests_matches_the_venue_policy_bound_payload_digest(
        self,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from tos_runtime.compose import cli

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        bound_digest = _rows(runtime, "VENUE_POLICY_BOUND")[0]["canonical_digest"]
        runtime.rcl_log.close()
        runtime.evidence_store.close()

        args = cli.parse_args(["print-policy-digests", "--config-dir", str(config_dir)])
        assert isinstance(args, cli.PrintPolicyDigestsArgs)
        exit_code = cli._dispatch_print_policy_digests(args)
        assert exit_code == 0
        out = capsys.readouterr().out
        match = re.search(r"VENUE_CONSTRAINT_POLICY \S+ \S+ (\S+)", out)
        assert match is not None
        assert match.group(1) == bound_digest


# ===========================================================================
# Structural pins (mutations M4, M9)
# ===========================================================================


def test_the_retired_ocp_literals_do_not_appear_under_tos_runtime_src() -> None:
    """M4: the old ``policy_id="compose-ocp"``/``policy_version="ocp-v1"`` literals must never
    reappear anywhere in the runtime source tree — step 2's OCP coordinates come exclusively
    from the governed, loaded Order Construction Policy now."""
    src_root = Path(__file__).resolve().parents[2] / "src" / "tos_runtime"
    offenders = []
    for path in src_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "compose-ocp" in text or '"ocp-v1"' in text:
            offenders.append(str(path))
    assert offenders == []


def test_compose_context_resolver_has_no_venue_decision_field() -> None:
    """M9: ``ComposeContextResolver`` must carry no ``venue_decision``/``venue_policy``/
    ``venue_snapshot`` dataclass FIELD (they are attempt-fresh reads off ``venue_stage`` now,
    never a boot-time-fixed constant) — an AST check over the dataclass body, not a runtime
    probe, so a reintroduced field is caught even if nothing currently reads it."""
    context_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "tos_runtime"
        / "compose"
        / "context.py"
    )
    tree = ast.parse(context_path.read_text(encoding="utf-8"))
    resolver = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "ComposeContextResolver"
    )
    field_names = {
        stmt.target.id
        for stmt in resolver.body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
    }
    assert "venue_decision" not in field_names
    assert "venue_policy" not in field_names
    assert "venue_snapshot" not in field_names


# ===========================================================================
# HIGH-1 (team-lead review, 2026-09-15): brokercap digest stays None for a genuinely DRAFT
# INSTANCE document — never an invented "draft" string (mutation M7).
# ===========================================================================


def test_broker_capability_profile_facts_stay_none_for_a_real_draft_instance_document() -> (
    None
):
    """Loads the REAL, repo-tracked KIS draft INSTANCE document (the same file
    ``test_transport_wiring.py`` loads for its own kis-mock e2e tests) and pins
    :func:`~tos_runtime.compose._venue_wiring._broker_capability_profile_facts` against it
    directly — the happy-path e2e boot (``SYNTHETIC_FUTURES_ORDER``) never binds an INSTANCE
    document at all, so it alone cannot prove the DRAFT-specific "digest stays None" claim this
    test exists to pin."""
    from tos_runtime.brokercap.instance import load_instance_document
    from tos_runtime.compose._venue_wiring import _broker_capability_profile_facts

    path = (
        Path(__file__).resolve().parents[4]
        / "docs"
        / "broker-profiles"
        / "KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
    )
    document = load_instance_document(path, environment="MOCK_VTS")
    # The premise this test's own name asserts — fails loudly if this fixture file is ever
    # finalized to ISSUED (at which point a real digest would become the honest value).
    assert document.status == "DRAFT"
    assert document.profile.canonical_digest is None

    version, digest = _broker_capability_profile_facts(document)
    assert digest is None
    profile_version = document.profile.profile_version
    assert profile_version is not None
    assert version == profile_version.profile_version
    assert version is not None  # the version string itself IS real, unlike the digest


# ===========================================================================
# Negative boot tests (mutations M2, M10, M11; scope mismatch)
# ===========================================================================


class TestVenueBootRefusals:
    def test_activation_digest_mismatch_refuses_to_boot(self, tmp_path: Path) -> None:
        config_dir, data_dir, custody_root = _fresh_compose_dirs(tmp_path / "case")
        members = _real_members(config_dir)
        members[0]["digest"] = "deliberately-wrong-digest"  # type: ignore[index]
        _rewrite_activation(config_dir, members)
        fx.write_band_strategy_file(config_dir)
        with pytest.raises(PolicyNotActivated):
            compose_paper_runtime(
                config_dir,
                data_dir,
                custody_root,
                "non-live-test",
                construction=fx.construction_config(),
                aggregate_risk_inputs_provider=_aggregate_inputs,
                action_flow_inputs_provider=_action_flow_inputs,
                transport_kind=TransportKind.SYNTHETIC,
            )

    def test_activation_resolved_false_refuses_to_boot(self, tmp_path: Path) -> None:
        config_dir, data_dir, custody_root = _fresh_compose_dirs(tmp_path / "case")
        members = _real_members(config_dir)
        members[0]["resolved"] = False  # type: ignore[index]
        _rewrite_activation(config_dir, members)
        fx.write_band_strategy_file(config_dir)
        with pytest.raises(PolicyNotActivated):
            compose_paper_runtime(
                config_dir,
                data_dir,
                custody_root,
                "non-live-test",
                construction=fx.construction_config(),
                aggregate_risk_inputs_provider=_aggregate_inputs,
                action_flow_inputs_provider=_action_flow_inputs,
                transport_kind=TransportKind.SYNTHETIC,
            )

    def test_activation_empty_members_refuses_to_boot(self, tmp_path: Path) -> None:
        config_dir, data_dir, custody_root = _fresh_compose_dirs(tmp_path / "case")
        _rewrite_activation(config_dir, [])
        fx.write_band_strategy_file(config_dir)
        with pytest.raises(PolicyNotActivated):
            compose_paper_runtime(
                config_dir,
                data_dir,
                custody_root,
                "non-live-test",
                construction=fx.construction_config(),
                aggregate_risk_inputs_provider=_aggregate_inputs,
                action_flow_inputs_provider=_action_flow_inputs,
                transport_kind=TransportKind.SYNTHETIC,
            )

    def test_admitting_phase_token_not_in_calendar_refuses_to_boot(
        self, tmp_path: Path
    ) -> None:
        config_dir, data_dir, custody_root = _fresh_compose_dirs(tmp_path / "case")
        # A phase token the shared conftest.py calendar never declares for this instrument
        # class (it only ever declares "CONTINUOUS"/"CLOSED").
        (config_dir / "venue_constraint_policy.yaml").write_text(
            venue_policy_yaml(
                environment=_VENUE_POLICY_ENVIRONMENT,
                account=_VENUE_POLICY_ACCOUNT,
                instrument=_VENUE_POLICY_INSTRUMENT,
                instrument_class=_VENUE_POLICY_INSTRUMENT_CLASS,
                price_min="1000",
                price_max="9000000",
                tick_size="500",
                lot_size="2",
                min_quantity="2",
                max_quantity="100",
                admitting_phases='["OPEN_X"]',
                admitting_phases_short='["OPEN_X"]',
            ),
            encoding="utf-8",
        )
        _sync_venue_activation_digest(config_dir)
        fx.write_band_strategy_file(config_dir)
        with pytest.raises(VenuePolicyScopeMismatch):
            compose_paper_runtime(
                config_dir,
                data_dir,
                custody_root,
                "non-live-test",
                construction=fx.construction_config(),
                aggregate_risk_inputs_provider=_aggregate_inputs,
                action_flow_inputs_provider=_action_flow_inputs,
                transport_kind=TransportKind.SYNTHETIC,
            )

    def test_kis_mock_wire_codec_null_refuses_at_compose_level(
        self, tmp_path: Path
    ) -> None:
        """MEDIUM (team-lead review, 2026-09-15): ``write_kis_mock_transport_config`` used to
        unconditionally rewrite ``order_construction_policy.yaml``'s ``wire_codec`` into the
        exact KIS codec block, so no compose-level test ever proved a ``kis-mock`` boot with
        ``wire_codec: null`` is actually refused. Reuses the SAME MOCK_STOCK_ORDER scope +
        custody + transport-config recipe ``test_transport_wiring.py``'s own
        ``test_e2e_boot_wires_a_kis_mock_transport_and_codec_digest_source`` already proves
        boots successfully — the ONE difference is the deliberate ``wire_codec=None`` override
        here."""
        config_dir, data_dir, custody_root = _fresh_compose_dirs(tmp_path / "case")
        _activate_mock_stock_order(config_dir)
        fx.write_kis_mock_transport_config(config_dir, wire_codec=None)
        fx.provision_kis_mock_custody(custody_root)
        fx.write_band_strategy_file(config_dir)
        with pytest.raises(VenuePolicyScopeMismatch):
            compose_paper_runtime(
                config_dir,
                data_dir,
                custody_root,
                "non-live-test",
                construction=fx.construction_config(),
                aggregate_risk_inputs_provider=_aggregate_inputs,
                action_flow_inputs_provider=_action_flow_inputs,
                transport_kind=TransportKind.KIS_MOCK,
            )

    def test_synthetic_wire_codec_non_null_refuses_at_compose_level(
        self, tmp_path: Path
    ) -> None:
        """MEDIUM inverse (team-lead review, 2026-09-15): a ``synthetic`` transport boot with a
        non-null ``wire_codec`` declared must also refuse at the compose level — the shared
        ``config_dir`` fixture already writes ``wire_codec: null``, so this only needs to
        overwrite the OCP file with a non-null codec before composing (no kis-mock
        scope/custody dance needed — the active scope stays the default SYNTHETIC one).
        """
        config_dir, data_dir, custody_root = _fresh_compose_dirs(tmp_path / "case")
        (config_dir / "order_construction_policy.yaml").write_text(
            ocp_yaml(
                environment=_VENUE_POLICY_ENVIRONMENT,
                account=_VENUE_POLICY_ACCOUNT,
                instrument=_VENUE_POLICY_INSTRUMENT,
                wire_codec='{kind: kis-order-cash-v1, wire_fields: ["CANO"]}',
            ),
            encoding="utf-8",
        )
        fx.write_band_strategy_file(config_dir)
        with pytest.raises(VenuePolicyScopeMismatch):
            compose_paper_runtime(
                config_dir,
                data_dir,
                custody_root,
                "non-live-test",
                construction=fx.construction_config(),
                aggregate_risk_inputs_provider=_aggregate_inputs,
                action_flow_inputs_provider=_action_flow_inputs,
                transport_kind=TransportKind.SYNTHETIC,
            )

    def test_instrument_scope_mismatch_refuses_to_boot(self, tmp_path: Path) -> None:
        config_dir, data_dir, custody_root = _fresh_compose_dirs(tmp_path / "case")
        (config_dir / "venue_constraint_policy.yaml").write_text(
            venue_policy_yaml(
                environment=_VENUE_POLICY_ENVIRONMENT,
                account=_VENUE_POLICY_ACCOUNT,
                instrument="NOT-" + _VENUE_POLICY_INSTRUMENT,
                instrument_class=_VENUE_POLICY_INSTRUMENT_CLASS,
                price_min="1000",
                price_max="9000000",
                tick_size="500",
                lot_size="2",
                min_quantity="2",
                max_quantity="100",
                admitting_phases=f'["{_VENUE_POLICY_ADMITTING_PHASE}"]',
                admitting_phases_short=f'["{_VENUE_POLICY_ADMITTING_PHASE}"]',
            ),
            encoding="utf-8",
        )
        _sync_venue_activation_digest(config_dir)
        fx.write_band_strategy_file(config_dir)
        with pytest.raises(VenuePolicyScopeMismatch):
            compose_paper_runtime(
                config_dir,
                data_dir,
                custody_root,
                "non-live-test",
                construction=fx.construction_config(),
                aggregate_risk_inputs_provider=_aggregate_inputs,
                action_flow_inputs_provider=_action_flow_inputs,
                transport_kind=TransportKind.SYNTHETIC,
            )


class TestWireCodecCrossCheck:
    """M11, at the unit level: a full kis-mock e2e boot needs a whole scope/custody dance
    (``test_transport_wiring.py``'s own ``_activate_mock_stock_order`` +
    ``provision_kis_mock_custody``) unrelated to what this cross-check itself decides, so this
    pins :func:`~tos_runtime.compose._venue_wiring._cross_check_wire_codec` directly against a
    REAL loaded ``LoadedOrderConstructionPolicy`` (never a hand-built stand-in)."""

    def test_null_wire_codec_with_kis_mock_transport_refuses(
        self, tmp_path: Path
    ) -> None:
        from tos_runtime.compose import _venue_wiring
        from tos_runtime.venue import load_order_construction_policy

        path = tmp_path / "order_construction_policy.yaml"
        path.write_text(ocp_yaml(wire_codec="null"), encoding="utf-8")
        loaded = load_order_construction_policy(path, scheme=_SCHEME)
        with pytest.raises(VenuePolicyScopeMismatch):
            _venue_wiring._cross_check_wire_codec(
                loaded, transport_kind=TransportKind.KIS_MOCK
            )

    def test_non_null_wire_codec_with_synthetic_transport_refuses(
        self, tmp_path: Path
    ) -> None:
        from tos_runtime.compose import _venue_wiring
        from tos_runtime.venue import load_order_construction_policy

        path = tmp_path / "order_construction_policy.yaml"
        path.write_text(
            ocp_yaml(wire_codec='{kind: kis-order-cash-v1, wire_fields: ["CANO"]}'),
            encoding="utf-8",
        )
        loaded = load_order_construction_policy(path, scheme=_SCHEME)
        with pytest.raises(VenuePolicyScopeMismatch):
            _venue_wiring._cross_check_wire_codec(
                loaded, transport_kind=TransportKind.SYNTHETIC
            )

    def test_exact_kis_order_cash_wire_codec_with_kis_mock_transport_admits(
        self, tmp_path: Path
    ) -> None:
        from tos_runtime.compose import _venue_wiring
        from tos_runtime.transport.kis_mock.codec import KIS_ORDER_CASH_WIRE_FIELDS
        from tos_runtime.venue import load_order_construction_policy

        path = tmp_path / "order_construction_policy.yaml"
        path.write_text(
            ocp_yaml(
                wire_codec=(
                    "{kind: kis-order-cash-v1, wire_fields: "
                    f"{sorted(KIS_ORDER_CASH_WIRE_FIELDS)!r}}}"
                )
            ),
            encoding="utf-8",
        )
        loaded = load_order_construction_policy(path, scheme=_SCHEME)
        _venue_wiring._cross_check_wire_codec(
            loaded, transport_kind=TransportKind.KIS_MOCK
        )

    def test_null_wire_codec_with_synthetic_transport_admits(
        self, tmp_path: Path
    ) -> None:
        from tos_runtime.compose import _venue_wiring
        from tos_runtime.venue import load_order_construction_policy

        path = tmp_path / "order_construction_policy.yaml"
        path.write_text(ocp_yaml(wire_codec="null"), encoding="utf-8")
        loaded = load_order_construction_policy(path, scheme=_SCHEME)
        _venue_wiring._cross_check_wire_codec(
            loaded, transport_kind=TransportKind.SYNTHETIC
        )


# ===========================================================================
# (a′) wave lane C — order_shape field sourcing
# (docs/plans/2026-09-16-tos-aprime-envelope-order-shape-plan.md §2 decisions 2/3/4)
# ===========================================================================


class TestDerivedQuantityReachesVenueGate:
    """decision 2: ``order_shape.quantity`` is judged from the derivation
    (``construction.command.axis_value(QUANTITY)``), never the caller-declared literal on
    ``ConstructionConfig.order_shape``."""

    def test_derived_quantity_reaches_the_fold_not_the_literal(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        # fx.sizing_bound() derives risk_budget/per_unit_risk = 1000/50 = 20 (already an
        # exact lot_size=2 multiple, within [min_quantity=2, max_quantity=100]) —
        # deliberately different from the literal quantity below (4, itself on-grid /
        # admissible on its own) so an ADMIT here cannot be explained by the literal
        # happening to match, only by the derived value being the one actually judged.
        construction = fx.construction_config(order_shape=fx.order_shape(quantity=4))
        runtime = _compose_with_construction(
            tmp_path, config_dir, data_dir, custody_root, construction
        )
        _reach_trusted(runtime)

        results = runtime.run_once((fx.crossing_event(),))
        verdicts = {v.step: v for v in results[0].flow.verdicts}
        step3 = verdicts[CommitmentStep.VENUE_ADMISSIBILITY_DECISION]

        construction_result = runtime.construction_stage.construction
        assert (
            construction_result is not None and construction_result.command is not None
        )
        # the bound axis value is a canonicalized Decimal string (e.g. "2E+1", not "20") —
        # assert the parsed *value*, not its literal spelling.
        from decimal import Decimal

        bound_quantity = construction_result.command.axis_value(
            fx.ConformanceAxis.QUANTITY
        )
        assert bound_quantity is not None and Decimal(bound_quantity) == 20

        assert runtime.venue_stage.resolved_shape is not None
        assert runtime.venue_stage.resolved_shape.quantity == 20
        assert step3.outcome is StageOutcome.ADMIT

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_literal_derived_quantity_mismatch_no_longer_passes_on_the_literal(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """The defect, as a test (team-lead brief): a literal quantity (999) the venue policy
        would refuse on its own (exceeds ``max_quantity=100`` — ``conftest.py``'s own venue
        policy fixture) must not veto the attempt when the DERIVED quantity (20, on-grid,
        in-bounds) is the one actually judged. Pre-fix, ``order_shape_admissible`` judged the
        caller's literal directly and this attempt would have been INADMISSIBLE."""
        construction = fx.construction_config(order_shape=fx.order_shape(quantity=999))
        runtime = _compose_with_construction(
            tmp_path, config_dir, data_dir, custody_root, construction
        )
        _reach_trusted(runtime)

        results = runtime.run_once((fx.crossing_event(),))
        verdicts = {v.step: v for v in results[0].flow.verdicts}
        step3 = verdicts[CommitmentStep.VENUE_ADMISSIBILITY_DECISION]

        assert runtime.venue_stage.resolved_shape is not None
        assert runtime.venue_stage.resolved_shape.quantity == 20
        assert step3.outcome is StageOutcome.ADMIT

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    # No e2e "denied derivation ⇒ step3 sees quantity=None" test: ``tos.engine.sequencer
    # .run_commitment_flow``'s "positive-admit gate" halts the flow entirely at the FIRST
    # non-ADMIT verdict ("Only an explicit ADMIT advances") — a denied step 2
    # (``candidate_command_verdict`` DENYs whenever ``construction.command is None``) means
    # step 3's stage never runs at all, so there is no ``StageVerdict`` to read here. The
    # ``candidate_command is None ⇒ quantity is None`` fail-closed behaviour is instead
    # covered directly at the unit level: ``TestDerivedShapeQuantityUnit
    # .test_absent_candidate_command_is_none`` below.


class TestSourcedShapeNonIntegralQuantityNeverFallsBackToTheLiteral:
    """MEDIUM (team-lead review, PR #718): pins ``VenueServiceStage._sourced_shape`` ITSELF —
    the reviewer made it silently fall back to the injected literal quantity when the
    derivation yields ``None`` and all 2225 other tests still passed, because nothing
    exercised ``_sourced_shape`` with a ``candidate_command`` that IS present
    (``candidate_command is not None``, i.e. step 2 admitted) but bound to a non-integral
    QUANTITY value — ``_derived_shape_quantity``'s own fail-closed branch, distinct from the
    "no command at all" case ``TestDerivedQuantityReachesVenueGate`` already covers (that one
    halts the sequencer before step 3 ever runs, so it cannot reach this branch either).

    Exercises the REAL ``_sourced_shape`` method against a hand-built
    ``CanonicalBrokerCommand`` — not a reimplementation of its logic — rather than forcing a
    genuinely-DERIVED non-integral quantity through the full compose stack: that path is
    structurally closed, since ``VenueShapeConstraints.lot_size`` is ``int``-typed, so any
    quantity that clears the venue policy's own lot check is necessarily integer-valued
    (verified while writing this test — an all-``Decimal("0.5")`` lot/sizing-bound override
    hits ``VenuePolicyConfigError: ... lot_size must be an int or null`` at the venue-policy
    loader, before derivation is even reached)."""

    @staticmethod
    def _stage(shape) -> object:
        from tos.venue import ActionClass
        from tos_runtime.compose._venue_wiring import VenueServiceStage

        class _StubService:
            shape_constraints = None

        class _StubConstructionStage:
            construction = None

        return VenueServiceStage(
            _StubService(),
            _StubConstructionStage(),
            ActionClass.NEW_LONG,
            shape,
            None,
        )

    def test_non_integral_axis_value_leaves_quantity_none_not_the_literal(self) -> None:
        from tos.ioc import AxisBinding, CanonicalBrokerCommand, ConformanceAxis
        from tos.venue import OrderShapeFields

        literal_quantity = 20
        resolved = OrderShapeFields(
            price=4500,
            quantity=literal_quantity,  # must NOT survive into the sourced shape
            order_type="LIMIT",
            tif="DAY",
            side="BUY",
            position_effect="OPEN",
            silently_rounded=False,
        )
        command = CanonicalBrokerCommand(
            command_id="cmd-test",
            command_generation=1,
            axis_bindings=(AxisBinding(axis=ConformanceAxis.QUANTITY, value="10.5"),),
        )

        sourced = self._stage(resolved)._sourced_shape(resolved, command)

        assert sourced is not None
        assert sourced.quantity is None
        assert sourced.quantity != literal_quantity


class TestSilentlyRoundedObservedEndToEnd:
    """decision 4: ``silently_rounded`` is an OBSERVED tick/lot-grid fact, never the injected
    attestation."""

    def test_on_grid_shape_observes_silently_rounded_false(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        runtime.run_once((fx.crossing_event(),))

        assert runtime.venue_stage.resolved_shape is not None
        assert runtime.venue_stage.resolved_shape.silently_rounded is False

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_off_grid_price_observes_not_false_and_denies(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Disabling step 3's value-surface price projection (``shape_price_field_key=None``)
        leaves the literal price (4200) standing — off the venue policy's own tick grid
        (``conftest.py``: ``price_min=1000``, ``tick_size=500`` — ``(4200-1000) % 500 ==
        200``). The injected ``silently_rounded=False`` attestation is IGNORED; the observed
        fact (off-grid) denies the attempt through ``order_shape_admissible``'s own early
        gate ("anything other than a positive ``False`` fails closed")."""
        construction = fx.construction_config(shape_price_field_key=None)
        runtime = _compose_with_construction(
            tmp_path, config_dir, data_dir, custody_root, construction
        )
        _reach_trusted(runtime)

        results = runtime.run_once((fx.crossing_event(),))
        verdicts = {v.step: v for v in results[0].flow.verdicts}
        step3 = verdicts[CommitmentStep.VENUE_ADMISSIBILITY_DECISION]

        assert runtime.venue_stage.resolved_shape is not None
        assert runtime.venue_stage.resolved_shape.price == 4200
        # LOW (team-lead review, PR #718): `is not False` admits both `True` and `None` —
        # `_observed_silently_rounded` returns a plain `bool` now, so the precise value is
        # `True` (this shape IS fully gradeable and IS off-grid), not merely "not False".
        assert runtime.venue_stage.resolved_shape.silently_rounded is True
        assert step3.outcome is not StageOutcome.ADMIT

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_unprojectable_price_yields_structural_unknown_not_inadmissible(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """HIGH (team-lead review, PR #718): a structurally-unprojectable step-3 price —
        ``_shape_for``'s own documented "projection impossible ⇒ structural UNKNOWN" path
        (``egressgw/construction.py:1074-1098``, ``admitted_shape_price_from_view`` returning
        ``None`` because the governed field key is not on the value surface) — must reach
        ``order_shape_admissible``'s OWN missing-field ``UNKNOWN`` classification. Before the
        fix, ``_observed_silently_rounded`` returned ``None`` here, which
        ``order_shape_admissible`` treats the same as ``True`` (``is not False`` gates BEFORE
        the missing-field check) — silently turning the kernel's own ``UNKNOWN`` into a
        ``DENY`` this function has no authority to make. This is the exact classification a
        unit test on the helper's return value alone cannot pin — it only shows up once the
        kernel's real predicate ordering runs, hence e2e."""
        construction = fx.construction_config(
            shape_price_field_key="not-a-real-field-key"
        )
        runtime = _compose_with_construction(
            tmp_path, config_dir, data_dir, custody_root, construction
        )
        _reach_trusted(runtime)

        results = runtime.run_once((fx.crossing_event(),))
        verdicts = {v.step: v for v in results[0].flow.verdicts}
        step3 = verdicts[CommitmentStep.VENUE_ADMISSIBILITY_DECISION]

        assert runtime.venue_stage.resolved_shape is not None
        assert runtime.venue_stage.resolved_shape.price is None
        assert runtime.venue_stage.resolved_shape.silently_rounded is False
        assert step3.outcome is StageOutcome.UNKNOWN

        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestDerivedShapeQuantityUnit:
    """decision 2: pure unit coverage for :func:`_derived_shape_quantity`'s fail-closed
    parsing — the case an e2e path cannot cheaply exercise (a bound axis value that is not an
    exact whole number)."""

    def test_absent_candidate_command_is_none(self) -> None:
        from tos_runtime.compose._venue_wiring import _derived_shape_quantity

        assert _derived_shape_quantity(None) is None

    def test_absent_quantity_axis_is_none(self) -> None:
        from tos.ioc import CanonicalBrokerCommand
        from tos_runtime.compose._venue_wiring import _derived_shape_quantity

        command = CanonicalBrokerCommand(command_id="cmd-test", command_generation=1)
        assert _derived_shape_quantity(command) is None

    def test_fractional_axis_value_is_none_not_a_guess(self) -> None:
        from tos.ioc import AxisBinding, CanonicalBrokerCommand, ConformanceAxis
        from tos_runtime.compose._venue_wiring import _derived_shape_quantity

        command = CanonicalBrokerCommand(
            command_id="cmd-test",
            command_generation=1,
            axis_bindings=(AxisBinding(axis=ConformanceAxis.QUANTITY, value="1.5"),),
        )
        assert _derived_shape_quantity(command) is None

    def test_whole_number_axis_value_parses_to_int(self) -> None:
        from tos.ioc import AxisBinding, CanonicalBrokerCommand, ConformanceAxis
        from tos_runtime.compose._venue_wiring import _derived_shape_quantity

        command = CanonicalBrokerCommand(
            command_id="cmd-test",
            command_generation=1,
            axis_bindings=(AxisBinding(axis=ConformanceAxis.QUANTITY, value="20"),),
        )
        assert _derived_shape_quantity(command) == 20


class TestConstructionRulesShapeSourcingUnit:
    """decisions 2/3: pure unit coverage for the ``ConstructionRules``-driven sourcing
    helpers. Not yet reachable end-to-end — ``compose/_wiring.py``'s own
    ``_build_construction_stages`` does not pass a loaded ``ConstructionRules`` into
    ``VenueServiceStage`` yet (that wiring reaches into ``compose/root.py``, outside this
    wave's lane-C scope; see the lane-C report) — so the capability is exercised directly.

    ``action_class_shape`` is keyed by ``(ActionClass, direction)`` (contract amended
    2026-09-16, commit ``7e79f00c``) — a single ``ActionClass.CLOSE`` member cannot otherwise
    express both a long-close and a short-close arm. ``direction`` is a per-composition fact
    read off ``authorized_axes``' own ``DIRECTION`` binding (today's discipline, pending a
    runtime proposal path — see ``_shape_side_and_position_effect``'s own docstring), so each
    test below builds ONE ``ConstructionRules`` per direction rather than one shared instance
    covering both.
    """

    def test_side_and_position_effect_come_from_the_mapping(self) -> None:
        from tos.ioc import AxisBinding, ConformanceAxis
        from tos.venue import ActionClass
        from tos_runtime.compose._venue_wiring import _shape_side_and_position_effect
        from tos_runtime.venue.construction_rules import (
            ActionClassShape,
            ConstructionRules,
        )

        long_rules = ConstructionRules(
            sizing_bound=fx.sizing_bound(),
            admitted_quantity_bases=frozenset({"RISK"}),
            authorized_axes=(
                AxisBinding(axis=ConformanceAxis.DIRECTION, value="LONG"),
            ),
            action_class_shape={
                (ActionClass.NEW_LONG, "LONG"): ActionClassShape(
                    side="BUY", position_effect="OPEN"
                ),
                (ActionClass.CLOSE, "LONG"): ActionClassShape(
                    side="SELL", position_effect="CLOSE"
                ),
            },
            effect_dimensions=(),
        )
        assert _shape_side_and_position_effect(long_rules, ActionClass.NEW_LONG) == (
            "BUY",
            "OPEN",
        )
        assert _shape_side_and_position_effect(long_rules, ActionClass.CLOSE) == (
            "SELL",
            "CLOSE",
        )

        # NEW_SHORT / short-close mirror — a SEPARATE ConstructionRules whose
        # authorized_axes DIRECTION is SHORT, with its OWN CLOSE arm distinct from the
        # long-close arm above (the exact ambiguity the (ActionClass, direction) key
        # exists to resolve) — symmetric, not a narrower/omitted case (CLAUDE.md
        # non-negotiable: "Futures must preserve long/short symmetry").
        short_rules = ConstructionRules(
            sizing_bound=fx.sizing_bound(),
            admitted_quantity_bases=frozenset({"RISK"}),
            authorized_axes=(
                AxisBinding(axis=ConformanceAxis.DIRECTION, value="SHORT"),
            ),
            action_class_shape={
                (ActionClass.NEW_SHORT, "SHORT"): ActionClassShape(
                    side="SELL", position_effect="OPEN"
                ),
                (ActionClass.CLOSE, "SHORT"): ActionClassShape(
                    side="BUY", position_effect="CLOSE"
                ),
            },
            effect_dimensions=(),
        )
        assert _shape_side_and_position_effect(short_rules, ActionClass.NEW_SHORT) == (
            "SELL",
            "OPEN",
        )
        assert _shape_side_and_position_effect(short_rules, ActionClass.CLOSE) == (
            "BUY",
            "CLOSE",
        )

    def test_action_class_absent_from_the_mapping_is_a_refusal(self) -> None:
        from tos.ioc import AxisBinding, ConformanceAxis
        from tos.venue import ActionClass
        from tos_runtime.compose._venue_wiring import _shape_side_and_position_effect
        from tos_runtime.venue.construction_rules import (
            ActionClassShape,
            ConstructionRules,
        )

        rules = ConstructionRules(
            sizing_bound=fx.sizing_bound(),
            admitted_quantity_bases=frozenset({"RISK"}),
            authorized_axes=(
                AxisBinding(axis=ConformanceAxis.DIRECTION, value="LONG"),
            ),
            action_class_shape={
                (ActionClass.NEW_LONG, "LONG"): ActionClassShape(
                    side="BUY", position_effect="OPEN"
                ),
            },
            effect_dimensions=(),
        )

        # NEW_SHORT is absent for direction LONG (there is no (NEW_SHORT, "LONG") entry,
        # and there is no CLOSE entry at all) — both refuse.
        assert _shape_side_and_position_effect(rules, ActionClass.NEW_SHORT) == (
            None,
            None,
        )
        assert _shape_side_and_position_effect(rules, ActionClass.CLOSE) == (None, None)
        assert _shape_side_and_position_effect(rules, None) == (None, None)

    def test_no_direction_binding_is_a_refusal(self) -> None:
        """No ``DIRECTION`` axis binding at all is the SAME refusal as an absent mapping
        entry — never a fallback to some default direction (team-lead brief, 2026-09-16:
        "no direction" gets the same discipline already applied to "no derivation")."""
        from tos.venue import ActionClass
        from tos_runtime.compose._venue_wiring import _shape_side_and_position_effect
        from tos_runtime.venue.construction_rules import (
            ActionClassShape,
            ConstructionRules,
        )

        rules = ConstructionRules(
            sizing_bound=fx.sizing_bound(),
            admitted_quantity_bases=frozenset({"RISK"}),
            authorized_axes=(),  # no DIRECTION binding
            action_class_shape={
                (ActionClass.NEW_LONG, "LONG"): ActionClassShape(
                    side="BUY", position_effect="OPEN"
                ),
            },
            effect_dimensions=(),
        )

        assert _shape_side_and_position_effect(rules, ActionClass.NEW_LONG) == (
            None,
            None,
        )

    def test_order_type_and_tif_come_from_authorized_axes(self) -> None:
        from tos.ioc import AxisBinding, ConformanceAxis
        from tos_runtime.compose._venue_wiring import _shape_order_type_and_tif
        from tos_runtime.venue.construction_rules import ConstructionRules

        rules = ConstructionRules(
            sizing_bound=fx.sizing_bound(),
            admitted_quantity_bases=frozenset({"RISK"}),
            authorized_axes=(
                AxisBinding(axis=ConformanceAxis.ORDER_TYPE, value="LIMIT"),
                AxisBinding(axis=ConformanceAxis.TIF, value="DAY"),
                AxisBinding(axis=ConformanceAxis.ACCOUNT, value=fx.ACCOUNT),
            ),
            action_class_shape={},
            effect_dimensions=(),
        )

        assert _shape_order_type_and_tif(rules) == ("LIMIT", "DAY")

    def test_order_type_and_tif_absent_from_authorized_axes_is_none(self) -> None:
        from tos_runtime.compose._venue_wiring import _shape_order_type_and_tif
        from tos_runtime.venue.construction_rules import ConstructionRules

        rules = ConstructionRules(
            sizing_bound=fx.sizing_bound(),
            admitted_quantity_bases=frozenset({"RISK"}),
            authorized_axes=(),
            action_class_shape={},
            effect_dimensions=(),
        )

        assert _shape_order_type_and_tif(rules) == (None, None)


class TestObservedSilentlyRoundedUnit:
    """decision 4 + HIGH (team-lead review, PR #718): pure unit coverage for
    :func:`_observed_silently_rounded` — every branch. This is NOT a three-state observation:
    ``order_shape_admissible`` checks ``silently_rounded is not False`` BEFORE its own
    missing-field check, so anything other than ``False`` on missing/invalid grid data would
    force ``INADMISSIBLE`` in place of the kernel's own ``UNKNOWN`` — a classification this
    function has no authority to make. ``False`` is therefore the answer for every
    "ungradeable" case, not just the on-grid one; only an AFFIRMATIVELY off-grid shape (every
    fact present, positive tick/lot, and a genuine misalignment) returns ``True``. The
    classification-preserving property itself — that ``False`` here reaches the kernel's own
    missing-field ``UNKNOWN`` rather than a forced ``INADMISSIBLE`` — is pinned at the e2e
    level below (``TestSilentlyRoundedObservedEndToEnd
    .test_unprojectable_price_yields_structural_unknown_not_inadmissible``), since a unit
    assertion on this function's return value alone cannot see the kernel's predicate
    ordering."""

    @staticmethod
    def _constraints(**overrides: object):
        from tos.venue import VenueShapeConstraints

        base: dict[str, object] = {
            "price_min": 1000,
            "price_max": 9000000,
            "tick_size": 500,
            "lot_size": 2,
            "min_quantity": 2,
            "max_quantity": 100,
            "allowed_order_types": frozenset({"LIMIT"}),
            "allowed_tifs": frozenset({"DAY"}),
            "allowed_sides": frozenset({"BUY", "SELL"}),
            "allowed_position_effects": frozenset({"OPEN", "CLOSE"}),
        }
        base.update(overrides)
        return VenueShapeConstraints(**base)

    def test_on_grid_price_and_quantity_observe_false(self) -> None:
        from tos_runtime.compose._venue_wiring import _observed_silently_rounded

        assert (
            _observed_silently_rounded(
                price=4500, quantity=20, constraints=self._constraints()
            )
            is False
        )

    def test_off_grid_price_observes_true(self) -> None:
        from tos_runtime.compose._venue_wiring import _observed_silently_rounded

        assert (
            _observed_silently_rounded(
                price=4200, quantity=20, constraints=self._constraints()
            )
            is True
        )

    def test_off_grid_quantity_observes_true(self) -> None:
        from tos_runtime.compose._venue_wiring import _observed_silently_rounded

        assert (
            _observed_silently_rounded(
                price=4500, quantity=21, constraints=self._constraints()
            )
            is True
        )

    def test_missing_constraints_observes_false_not_a_forced_denial(self) -> None:
        from tos_runtime.compose._venue_wiring import _observed_silently_rounded

        assert (
            _observed_silently_rounded(price=4500, quantity=20, constraints=None)
            is False
        )

    def test_missing_price_or_quantity_observes_false_not_a_forced_denial(self) -> None:
        from tos_runtime.compose._venue_wiring import _observed_silently_rounded

        constraints = self._constraints()
        assert (
            _observed_silently_rounded(price=None, quantity=20, constraints=constraints)
            is False
        )
        assert (
            _observed_silently_rounded(
                price=4500, quantity=None, constraints=constraints
            )
            is False
        )

    def test_zero_tick_or_lot_observes_false_not_a_forced_denial(self) -> None:
        from tos_runtime.compose._venue_wiring import _observed_silently_rounded

        assert (
            _observed_silently_rounded(
                price=4500, quantity=20, constraints=self._constraints(tick_size=0)
            )
            is False
        )
        assert (
            _observed_silently_rounded(
                price=4500, quantity=20, constraints=self._constraints(lot_size=0)
            )
            is False
        )
