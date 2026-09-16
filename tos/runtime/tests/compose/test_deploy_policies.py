"""Compose e2e tests for the REAL deployed policy INSTANCE files
(``config/tos_runtime/paper/venue_constraint_policy.yaml`` /
``order_construction_policy.yaml`` -- TOS venue constraint service plan §6 ②,
adopted by the operator 2026-09-16; placement per DR-0002 §2.1).

Two facts this file pins, in the same spirit as ``test_deploy_config.py``
pins the real calendar:

1. The files are OPERATOR-FILL gated: as committed, ``scope.accounts`` and
   ``scope.instruments`` are ``"TBD"`` (the paper account number is never
   committed; the front-month contract code is a per-generation fill), and
   the loader REFUSES them as-is -- a policy that boots with a literal
   ``"TBD"`` account would be a phantom scope.
2. With those two coordinates (and the environment label) filled, the files
   boot the real compose root against the REAL calendar and the attempt stops
   fail-closed BEFORE any send: the adopted values carry a ``null``
   ``max_quantity`` (no broker limit source), which makes the venue quantity
   constraint step 2 derives from the policy incomplete -- the kernel's
   ``OrderConstructionStage`` DENIES ("the venue / broker quantity constraint
   is incomplete") and step 3 is never reached. Independently, the ``null``
   price band (no price-band source -- P0-2 ``UNKNOWN``) makes the kernel's
   ``order_shape_admissible`` return ``UNKNOWN`` for the adopted shape
   constraints, so even a sized attempt could not be admitted. Both are the
   intended fail-closed state the plan's §5 정직 상태 records -- not a
   test-only shortcut.

Hermetic (D1.4): every write lands under ``tmp_path`` (the real files are
only READ and copied).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos.venue import OrderAdmissibilityResult, OrderShapeFields
from tos.venue.predicates import order_shape_admissible
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.venue import (
    VenuePolicyConfigError,
    load_order_construction_policy,
    load_venue_constraint_policy,
)

from . import _fixtures as fx
from .conftest import (
    _VENUE_POLICY_ACCOUNT,
    _VENUE_POLICY_ENVIRONMENT,
    _VENUE_POLICY_INSTRUMENT,
)
from .test_compose_root import _compose, _reach_trusted
from .test_deploy_config import _install_real_calendar, _kst_unix_ms
from .test_venue_wiring import _kind_count, _rewrite_activation, _rows

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEPLOY_DIR = _REPO_ROOT / "config" / "tos_runtime" / "paper"
_REAL_VENUE_POLICY = _DEPLOY_DIR / "venue_constraint_policy.yaml"
_REAL_OCP = _DEPLOY_DIR / "order_construction_policy.yaml"

#: The values the operator adopted (plan §6 ② table) -- pinned here so a
#: silent edit of the deploy file cannot pass as "still the approved value".
_ADOPTED_TICK = 5
_ADOPTED_LOT = 1
_ADOPTED_MIN_QTY = 1
_ADOPTED_ADMITTING_PHASE = "CONTINUOUS"
_ADOPTED_OCP_VERSION = "1.0.0"


#: The (a′) wave's OCP fixture-fill for ``_runtime.construction.sizing.admitted_quantity_bases``
#: -- the SAME token the OCP sizing values proposal (§3) names as "the basis the fixtures
#: already use" and ``tos_runtime/tests/venue/_documents.py``'s own ``ocp_yaml()`` default uses.
#: Not a real strategy-file value (the shipped deploy file stays ``["TBD"]`` -- see
#: ``test_real_paper_ocp_refuses_on_admitted_quantity_bases_tbd_even_when_scope_is_filled`` in
#: ``tests/venue/test_config.py``); this is only what THIS test's "filled" copy uses to prove the
#: rest of the document boots, the same role ``account``/``instrument`` already play here.
_OCP_FIXTURE_QUANTITY_BASIS = "RISK"

#: The (a′) wave's OCP fixture-fill for ``_runtime.construction.axes``' ``DIRECTION`` entry
#: (review round 2026-09-16, PR #719 -- the shipped file left it ``"TBD"``: no operator decision
#: has bound this static, proposal-path-less composition to one trading direction yet). Not a
#: real strategy-file value (the shipped deploy file stays ``"TBD"`` -- see
#: ``test_real_paper_ocp_refuses_on_direction_tbd_even_when_scope_and_bases_are_filled`` in
#: ``tests/venue/test_config.py``); fixture data only, the same role
#: ``_OCP_FIXTURE_QUANTITY_BASIS`` already plays here.
_OCP_FIXTURE_DIRECTION = "LONG"


def _filled(path: Path, *, environment: str, account: str, instrument: str) -> dict:
    """The real document with ONLY the operator-fill coordinates filled -- exactly what the
    operator fills by hand before ``print-policy-digests``. For the Order Construction Policy
    this now ALSO fills ``_runtime.construction.sizing.admitted_quantity_bases`` and
    ``_runtime.construction.axes``' ``DIRECTION`` entry (the (a′) wave's OCP loader changes,
    ``tos_runtime/venue/_order_construction_policy_loader.py``): both leaves joined the
    operator-fill gate scope.accounts/scope.instruments were already in, so this helper --
    whose whole job is "fill every operator-fill leaf, then prove the rest boots" -- fills them
    too, the same way and for the same reason."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["scope"]["accounts"] == ["TBD"]
    assert raw["scope"]["instruments"] == ["TBD"]
    raw["scope"]["environments"] = [environment]
    raw["scope"]["accounts"] = [account]
    raw["scope"]["instruments"] = [instrument]
    construction = raw.get("_runtime", {}).get("construction")
    if construction is not None:
        sizing = construction["sizing"]
        assert sizing["admitted_quantity_bases"] == ["TBD"]
        sizing["admitted_quantity_bases"] = [_OCP_FIXTURE_QUANTITY_BASIS]
        direction_entries = [
            entry for entry in construction["axes"] if entry["axis"] == "DIRECTION"
        ]
        assert len(direction_entries) == 1
        assert direction_entries[0]["value"] == "TBD"
        direction_entries[0]["value"] = _OCP_FIXTURE_DIRECTION
    return raw


def _install_real_policies(config_dir: Path) -> tuple[str, str]:
    """Install the filled real policies over the fixture ones and rewrite the
    activation ``members:`` with their freshly computed digests (the
    ``print-policy-digests`` step, done in-process). Returns both digests."""
    for source, target in (
        (_REAL_VENUE_POLICY, "venue_constraint_policy.yaml"),
        (_REAL_OCP, "order_construction_policy.yaml"),
    ):
        raw = _filled(
            source,
            environment=_VENUE_POLICY_ENVIRONMENT,
            account=_VENUE_POLICY_ACCOUNT,
            instrument=_VENUE_POLICY_INSTRUMENT,
        )
        (config_dir / target).write_text(
            yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    venue = load_venue_constraint_policy(
        config_dir / "venue_constraint_policy.yaml", scheme=_SCHEME
    )
    ocp = load_order_construction_policy(
        config_dir / "order_construction_policy.yaml", scheme=_SCHEME
    )
    assert venue.policy.canonical_digest is not None
    assert ocp.policy.canonical_digest is not None
    _rewrite_activation(
        config_dir,
        [
            {
                "kind": "VENUE_CONSTRAINT_POLICY",
                "member_id": venue.policy.policy_id,
                "generation": venue.policy.policy_generation,
                "digest": venue.policy.canonical_digest,
                "resolved": True,
                "immutable": True,
            },
            {
                "kind": "ORDER_CONSTRUCTION_POLICY",
                "member_id": ocp.policy.policy_id,
                "generation": ocp.policy.policy_generation,
                "digest": ocp.policy.canonical_digest,
                "resolved": True,
                "immutable": True,
            },
        ],
    )
    return venue.policy.canonical_digest, ocp.policy.canonical_digest


def test_real_policy_files_carry_their_approval_provenance() -> None:
    for path in (_REAL_VENUE_POLICY, _REAL_OCP):
        text = path.read_text(encoding="utf-8")
        assert "§6 ②" in text
        assert "DR-0002" in text
        assert "2026-09-16" in text


@pytest.mark.parametrize(
    "path, loader",
    [
        (_REAL_VENUE_POLICY, load_venue_constraint_policy),
        (_REAL_OCP, load_order_construction_policy),
    ],
)
def test_real_policy_files_refuse_to_load_until_the_operator_fills_the_scope(
    path: Path, loader
) -> None:
    """As committed, accounts/instruments are ``"TBD"`` -- the loader's
    named-TBD refusal is the operator-fill gate, never a silent default."""
    with pytest.raises(VenuePolicyConfigError):
        loader(path, scheme=_SCHEME)


def test_filled_real_policies_carry_exactly_the_adopted_values(tmp_path: Path) -> None:
    venue_raw = _filled(
        _REAL_VENUE_POLICY, environment="paper", account="acct-x", instrument="inst-x"
    )
    venue_path = tmp_path / "venue_constraint_policy.yaml"
    venue_path.write_text(
        yaml.safe_dump(venue_raw, sort_keys=False, allow_unicode=True)
    )
    venue = load_venue_constraint_policy(venue_path, scheme=_SCHEME)

    shape = venue.policy.shape_constraints
    assert shape.tick_size == _ADOPTED_TICK
    assert shape.lot_size == _ADOPTED_LOT
    assert shape.min_quantity == _ADOPTED_MIN_QTY
    # No source → null → kernel UNKNOWN (plan §6 ② 보류 rows), never invented.
    assert shape.price_min is None and shape.price_max is None
    assert shape.max_quantity is None
    assert set(venue.null_shape_bounds) == {"price_min", "price_max", "max_quantity"}
    assert shape.allowed_order_types == frozenset({"LIMIT"})
    assert shape.allowed_tifs == frozenset({"DAY"})
    assert shape.allowed_sides == frozenset({"BUY", "SELL"})
    assert shape.allowed_position_effects == frozenset({"OPEN", "CLOSE"})
    for action in (
        fx.ActionClass.NEW_LONG,
        fx.ActionClass.NEW_SHORT,
        fx.ActionClass.CLOSE,
    ):
        assert venue.policy.admitting_phases_for(action) == frozenset(
            {_ADOPTED_ADMITTING_PHASE}
        )
    assert venue.scope.instrument_class == "krx-index-futures"

    ocp_raw = _filled(
        _REAL_OCP, environment="paper", account="acct-x", instrument="inst-x"
    )
    ocp_path = tmp_path / "order_construction_policy.yaml"
    ocp_path.write_text(yaml.safe_dump(ocp_raw, sort_keys=False, allow_unicode=True))
    ocp = load_order_construction_policy(ocp_path, scheme=_SCHEME)
    assert ocp.policy.policy_version == _ADOPTED_OCP_VERSION
    # policy_generation 2 -- the (a′) wave's _runtime.construction block ((a′) plan §2
    # decision 1: a new generation, not a field bolted onto generation 1).
    assert ocp.policy.policy_generation == 2
    assert ocp.construction_generation == 1
    assert ocp.wire_codec_kind is None  # synthetic paper default
    assert ocp.construction_rules.sizing_bound.admitted_quantity_bases == frozenset(
        {_OCP_FIXTURE_QUANTITY_BASIS}
    )


def test_real_policies_boot_the_compose_root_and_the_attempt_denies_fail_closed(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Real calendar + filled real policies, Monday 2026-09-07 10:00 KST
    (futures ``CONTINUOUS``): boot binds both policies, the session phase
    would admit, but step 2 DENIES on the incomplete quantity constraint
    (``max_quantity`` null) before step 3 runs -- nothing is sent. This is
    the adopted deploy state, pinned so it cannot silently become a send."""
    _install_real_calendar(config_dir)
    venue_digest, ocp_digest = _install_real_policies(config_dir)

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_kst_unix_ms(2026, 9, 7, 10, 0)),
    )
    _reach_trusted(runtime)

    bound = _rows(runtime, "VENUE_POLICY_BOUND")
    assert len(bound) == 1
    assert bound[0]["canonical_digest"] == venue_digest
    assert set(bound[0]["null_shape_bounds"]) == {
        "price_min",
        "price_max",
        "max_quantity",
    }
    assert _kind_count(runtime, "ORDER_CONSTRUCTION_POLICY_BOUND") == 1
    # The real futures calendar declares CONTINUOUS at this instant — the phase the
    # policy admits — so the refusal below is the quantity constraint's, not the phase's.
    assert runtime.session_facts.phase_for_step3("krx-index-futures") == (
        _ADOPTED_ADMITTING_PHASE
    )

    results = runtime.run_once((fx.crossing_event(),))
    assert results[0].flow is not None
    verdicts = {v.step: v for v in results[0].flow.verdicts}
    step2 = verdicts[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION]
    assert step2.outcome is StageOutcome.DENY
    assert "quantity constraint is incomplete" in (step2.reason or "")
    assert CommitmentStep.VENUE_ADMISSIBILITY_DECISION not in verdicts
    assert runtime.venue.last_decision is None
    assert _kind_count(runtime, "ORDER_ADMISSIBILITY_DECISION_ISSUED") == 0
    assert runtime.venue.quantity_constraint.max_quantity is None

    # And independently of step 2: the adopted shape constraints (null band) make the
    # kernel's own shape predicate UNKNOWN for a shape that is otherwise on-grid.
    on_grid = OrderShapeFields(
        price=5 * 100_000,
        quantity=1,
        order_type="LIMIT",
        tif="DAY",
        side="BUY",
        position_effect="OPEN",
        silently_rounded=False,
    )
    assert (
        order_shape_admissible(on_grid, runtime.venue.shape_constraints)
        is OrderAdmissibilityResult.UNKNOWN
    )

    construction = runtime.construction_stage.construction
    assert construction is not None
    assert construction.command is None  # denied before a candidate command existed
    assert runtime.venue.policy.canonical_digest == venue_digest
    assert (
        construction.policy is None
        or construction.policy.canonical_digest == ocp_digest
    )

    runtime.rcl_log.close()
    runtime.evidence_store.close()
