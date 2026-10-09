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

Since 2026-10-09 this file also pins the CP-3 **tenant** tree
(``config/tos_runtime/cp3-setup-d-long/venue_constraint_policy.yaml``), which is
where operator decision 9 (a)'s adopted ``max_quantity`` 10000 landed -- and the
matching fact that the resident ``paper/`` tree above deliberately did NOT adopt
it. The two halves are pinned next to each other on purpose: "the source exists
but this tree defers it" is a state that neither the resident ``null`` nor the
tenant ``10000`` records on its own.

Hermetic (D1.4): every write lands under ``tmp_path`` (the real files are
only READ and copied).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egressgw import EffectBasis, EffectDimensionSpec
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos.venue import OrderAdmissibilityResult, OrderShapeFields
from tos.venue.predicates import order_shape_admissible
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.marketfeed.policy import (
    CriticalInputPolicyConfigError,
    load_critical_input_policy,
)
from tos_runtime.marketfeed.time_projection import _DELAY_BOUND_FIELDS
from tos_runtime.time.config import _BOUND_FIELD_BY_KEY
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

#: The CP-3 first-tenant tree (Setup D / LONG) -- a SEPARATE deployment that boots under the
#: same ``paper`` environment label with its own off-repo render and data dir (CP-3 kickoff
#: ``docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md`` §4 decisions 3/4, approved
#: 2026-10-07). Its ``venue_constraint_policy.yaml`` is where decision 9's adopted
#: ``max_quantity`` landed; the resident ``paper/`` tree above deliberately did NOT adopt it.
_TENANT_DIR = _REPO_ROOT / "config" / "tos_runtime" / "cp3-setup-d-long"
_TENANT_VENUE_POLICY = _TENANT_DIR / "venue_constraint_policy.yaml"

#: Decision 9 (a), adopted by the operator 2026-10-08 -- KRX 파생상품시장 업무규정 시행세칙
#: 별표 17의2 제1호 미니코스피200선물거래 행 (정규거래 10,000 계약), grade R
#: (``docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md`` §2.1 / §3).
_ADOPTED_TENANT_MAX_QTY = 10000

#: The tenant venue policy's own identity. Renamed off the resident ``vcp-paper-krx-index-
#: futures`` on 2026-10-09 (PR #884 review L4): same id + same generation with DIFFERENT typed
#: content means a different ``canonical_digest`` under an identity an activation record cannot
#: disambiguate. Only the policies whose content actually differs were renamed -- the OCP, the
#: aggregate-risk and the action-flow policies keep the resident ids on purpose: there, "same id,
#: same digest" is a true statement that they ARE the same document.
#:
#: ⚠ The LONG tree's OCP is **digest-identical, not comment-only** (review L1). The 2026-10-09
#: tick correction rewrote its ``unit_multiplier_currency_and_numeric_rules`` line, which is
#: template DATA (DR-0002 §2.1 -- preserved, never interpreted by the runtime), not a comment.
#: The ``canonical_digest`` is unchanged regardless (``c90444b9...`` measured for the resident,
#: LONG and SHORT trees alike -- that digest tracks neither the DATA prose nor ``policy_id``),
#: which is why the id stays shared and the rename rule is unaffected. The earlier
#: "comment-only" wording was true when written and stopped being true in this PR's own first
#: commit.
_TENANT_VENUE_POLICY_ID = "vcp-paper-cp3-setup-d-long-krx-index-futures"

#: The provenance sentence design §8 step 5 requires next to that value. Pinned as a STRING so
#: the value cannot keep its number while losing the citation that makes it an approved value
#: (``config/tos_runtime/README.md``: "a value without a citation does not belong here").
_DECISION_9_PROVENANCE = (
    "결정 9 (a) · 운영자 채택 2026-10-08 · "
    "별표 17의2 제1호 미니코스피200선물거래 행 · 등급 R"
)

#: Design §2.2's **three** caveats, which that design requires to accompany the value WHEREVER
#: it is written -- as **four** string pins, because caveat (1) is two separate claims and
#: either can be dropped without the other: "a member may set a lower limit" (the rule) and
#: "the KIS limit is unconfirmed" (this broker's actual state, unobservable by GET per §4.3).
#: A caveat silently dropped turns 10000 from "a venue ceiling whose broker-side limit is
#: unconfirmed" into "the limit", which is the misreading §2.2 exists for.
_DECISION_9_CAVEATS = (
    "회원(증권사)은 이보다 낮게 정할 수 있다",  # §2.2 (1) -- 시행세칙 제61조제3항
    "KIS 측 한도는 미확인",  # §2.2 (1), second half -- GET 으로 관측 불가
    "거래소가 시장관리상 변경할 수 있다",  # §2.2 (2) -- 제61조제1항 단서
    "누적호가수량한도는 다른 한도다",  # §2.2 (3) -- 위탁계좌에는 적용되지 않는다
)

#: The tick correction, LANDED 2026-10-09 as the band-source wave plan's §3 first PR
#: (``docs/plans/2026-10-08-tos-cp3-band-source-wave-plan.md`` §3, operator-approved
#: 2026-10-08). Pinned as a STRING for the same reason ``_DECISION_9_PROVENANCE`` is: the
#: number 2 on its own does not say which regulation makes it the mini value, and
#: ``config/tos_runtime/README.md`` makes the citation part of what admits a value here.
#: Four separate pins because each can be dropped without the others -- the approval date, the
#: 조문 (which is what makes it grade R rather than the grade C local registry reading it
#: replaced), the grade itself, and the broker-side corroboration.
_TICK_PROVENANCE = (
    "운영자 승인 2026-10-08 · 시행세칙 제4조의9 제2호 · 등급 R · "
    "브로커 정황 = P-VL band 격자(PR #881)"
)

#: The other half of the correction, pinned next to the value for the same reason the
#: ``max_quantity`` deferral is: "the resident tree did NOT take this" is a state neither tree
#: records alone. Plan §3's table row: the resident tick stays 5 until paper adoption, because
#: moving it there buys a digest re-derivation plus the runbook §7.10 6 two-boot obligation for
#: zero behaviour change (the band is null there too).
_TICK_RESIDENT_DEFERRAL = "상주 `paper` 트리의 tick 은 5 그대로다"

#: B1a's published field policy, as ``tools/tos_cp3/produce_fields.py`` declares it: field_key
#: -> (unit, scale, multiplier, sign), in B1a's own ``FIELD_ORDER``. Literals, deliberately --
#: ``tools`` is legacy-side and the firewall forbids this tree from importing it, so the tie
#: between the two is this table plus the citation next to each group.
#:
#: Sources (``produce_fields._field_lineage``): the six price-like fields come from
#: ``_price_field`` (unit ``index_point`` / ``hundredths`` / ``100`` / ``unsigned``, PRICE_SCALE
#: 100); ``volume`` and ``session_token`` are that function's two inline entries; ``z_x1000``
#: is the one ``signed`` field (ATR thousandths, Z_SCALE 1000); the six gates come from
#: ``_bool_field`` (``bool`` / ``none`` / ``1`` / ``unsigned``).
_B1A_PRICE: tuple[str, str, str, str] = ("index_point", "hundredths", "100", "unsigned")
_B1A_BOOL: tuple[str, str, str, str] = ("bool", "none", "1", "unsigned")
_B1A_FIELD_POLICY: dict[str, tuple[str, str, str, str]] = {
    "open_x100": _B1A_PRICE,
    "high_x100": _B1A_PRICE,
    "low_x100": _B1A_PRICE,
    "close_x100": _B1A_PRICE,
    "volume": ("contract", "unit", "1", "unsigned"),
    "session_token": ("opaque_token", "none", "1", "unsigned"),
    "vwap_x100": _B1A_PRICE,
    "atr14_x100": _B1A_PRICE,
    "z_x1000": ("atr", "thousandths", "1000", "signed"),
    "hi_vol": _B1A_BOOL,
    "stall_ok": _B1A_BOOL,
    "reversal_ok": _B1A_BOOL,
    "entry_window": _B1A_BOOL,
    "vwap_reverted": _B1A_BOOL,
    "eod": _B1A_BOOL,
}

#: B1a's bar period, in milliseconds. NOT a free parameter: ``produce_fields`` writes the
#: timeframe into its own join key (``derive_raw_event_id``: ``<symbol>:1m:<stamp>``), so one
#: minute is what a "bar" means on this path.
_B1A_BAR_PERIOD_MS = 60_000

#: ``critical_input_policy.yaml::fields[].max_age_ms``, DECIDED by the operator 2026-10-09
#: ("max_age_ms : 800ms 로 정해") at grade **M** -- producible only from the operator, in the
#: ``docs/plans/2026-09-12-tos-operator-value-proposals.md:4`` vocabulary. Not A (VER-002 has no
#: APPROVED coordinate for this key, and the proposal table has no row for it: grade travels with
#: the KEY, not with the two grade-A terms the arithmetic consumes), not B (no measurement exists
#: -- ③, the live producer, has not been built), not C (the dev-side proposal WAS 180000, and the
#: same header recorded 800 as the order of magnitude that does not hold under the current ③
#: semantics; calling it a dev proposal would be a false statement).
#:
#: The number equals the kernel's own time-admission budget:
#: ``time.yaml::MAX_time_conservative_freshness_age_ms`` minus the sum of the delay bounds
#: ``RuntimeTimeProjection`` folds in. :func:`_tenant_kernel_time_budget_ms` RE-DERIVES that from
#: this tree's own ``time.yaml`` and
#: :func:`test_the_adopted_max_age_ms_is_the_kernel_budget_label_stamped_bars_cannot_meet`
#: asserts the equality, so a ``time.yaml`` edit turns this literal red rather than letting the
#: shipped number and its stated derivation drift apart.
_TENANT_MAX_AGE_MS = 800

#: ``time.yaml``'s four delay-bound KEYS -- **derived from the runtime, never re-listed**.
#:
#: ``_DELAY_BOUND_FIELDS`` is the tuple ``RuntimeTimeProjection`` actually sums into
#: ``delay_bounds``, and ``_BOUND_FIELD_BY_KEY`` is the loader's own YAML-key -> config-field
#: map; inverting the second over the first yields the YAML keys with **no literal in this
#: file**. ``compose/_marketfeed_wiring.py`` imports the same private tuple for the same reason
#: its docstring gives: "a guard that reads a second copy of the numbers it guards is exactly
#: the failure this repo has already hit". Both imports are RUNTIME-scope -> RUNTIME-scope, which
#: the firewall permits (it only forbids ``shared.*`` from here, and ``tos`` importing
#: ``tos_runtime``).
#:
#: ⚠ The first cut DID re-list them, and got one wrong: it named
#: ``MAX_time_source_disagreement_ms``, which is NOT a delay bound -- the runtime's fourth entry
#: is ``MAX_time_source_sequence_gap_ms``. The ``budget == 800`` assertion passed anyway because
#: both values happen to be 50 in every shipped ``time.yaml``. That is precisely the class of
#: guard this repo's project memory calls "a guard that admits what it names": it would have
#: stayed green while measuring the wrong four numbers.
_TIME_DELAY_BOUND_KEYS: tuple[str, ...] = tuple(
    key
    for field in _DELAY_BOUND_FIELDS
    for key, mapped in _BOUND_FIELD_BY_KEY.items()
    if mapped == field
)

#: The sentences the adopted ``max_age_ms`` may not be read without -- the operator's decision
#: with its arithmetic, the grade **and the reasons the other three grades would be false**, the
#: two measured premises behind the consequence, the consequence itself, the obligation that
#: consequence places on ③, the superseded 180000 kept as history, and the conservative
#: direction. A value with no source and no derivation written next to it is an invented number,
#: which is the state the fifteen ``null``s existed to avoid.
_MAX_AGE_PROVENANCE = (
    "운영자 결정 2026-10-09: 800 ms (= 커널 시간 예산 1000 − Σ지연 200)",
    "등급 M",
    "키를 따라가지 산술의 입력을 따라가지 않는다",  # why not A
    "개발 측 제안은 180000 이었고",  # why not C
    "The label, not label+60s",  # premise -- as_of is the bar OPEN
    "now_ms - as_of_ms",  # premise -- what the runtime measures
    "현행 B1a 의미론에서는 열다섯 전부 STALE 이다",  # the binding consequence
    "저널에 append 하는 시각을 `as_of_ms` 로 찍어야 한다",  # what it binds ③ to
    "180000 은 폐기됐다",  # the superseded value, as history
    "보수 방향 = 작게",
)

#: The price-like subset, by name -- asserted to be exactly the ×100 group, so a field cannot
#: join or leave that scale silently.
_B1A_PRICE_FIELDS = frozenset(
    {"open_x100", "high_x100", "low_x100", "close_x100", "vwap_x100", "atr14_x100"}
)

#: The resident tree's own one-line record of the same decision (design §8 step 5's last
#: sentence). Comment-only: measured 2026-10-09 that adding it leaves that file's
#: ``canonical_digest`` byte-identical, so the resident session's daily re-derivation is
#: untouched.
_PAPER_DEFERRAL_NOTE = (
    "source exists (10-08 결정 9); paper adoption deferred by operator"
)


def _tenant_kernel_time_budget_ms() -> int:
    """The conservative freshness budget THIS TREE's own ``time.yaml`` leaves, derived the way
    ``RuntimeTimeProjection`` derives it: the conservative freshness age bound minus the sum of
    the delay bounds it actually folds into ``delay_bounds``.

    Derived, never written as ``800``: the point of the 2026-10-09 decision is that
    ``max_age_ms`` IS this budget, so a literal here would let ``time.yaml`` move while the
    fifteen stayed -- exactly the drift the pacing guard
    (``compose/_marketfeed_wiring.py::_load_config_within_freshness_budget``, and its own suite
    ``test_marketfeed_pacing_budget.py``) exists to prevent on the other two terms. Same
    machinery as that suite: the runtime's ``_DELAY_BOUND_FIELDS`` mapped through the loader's
    ``_BOUND_FIELD_BY_KEY`` to YAML keys (:data:`_TIME_DELAY_BOUND_KEYS`), with no second copy
    of the numbers.
    """
    time_cfg = yaml.safe_load((_TENANT_DIR / "time.yaml").read_text(encoding="utf-8"))

    # The inverted-map derivation must have produced the runtime's FULL set -- a lookup that
    # silently found nothing would make the sum below too small and the budget too large (i.e.
    # permissive), so an empty or short result is never an acceptable outcome here.
    assert len(_TIME_DELAY_BOUND_KEYS) == len(_DELAY_BOUND_FIELDS)
    assert set(_TIME_DELAY_BOUND_KEYS) <= set(time_cfg)

    return int(time_cfg["MAX_time_conservative_freshness_age_ms"]) - sum(
        int(time_cfg[name]) for name in _TIME_DELAY_BOUND_KEYS
    )


def _comment_prose(path: Path) -> str:
    """Every comment line's text with ``#`` and indentation removed, joined by single spaces.

    A header sentence is pinned against THIS, not against the raw bytes, so re-wrapping a
    long Korean comment line does not break the pin while deleting or altering the sentence
    still does."""
    words: list[str] = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            words.extend(stripped.lstrip("#").split())
    return " ".join(words)


#: The values the operator adopted (plan §6 ② table) -- pinned here so a
#: silent edit of the deploy file cannot pass as "still the approved value".
#:
#: ``_RESIDENT_TICK`` and ``_TENANT_TICK`` are two constants on purpose, not one shared by both
#: trees: since 2026-10-09 they genuinely differ, and a single constant would have made the
#: tenant correction look like a resident change (or forced the resident assertion to follow the
#: tenant silently). 5 is the FULL-contract value kept in the resident tree while the band is
#: null (band-source wave plan §3's table: deferred with paper adoption); 2 is the mini
#: regulation value (시행세칙 제4조의9 제2호, grade R) in the tenant tree, where the leaf is a
#: mini ``A056xx``.
_RESIDENT_TICK = 5
_TENANT_TICK = 2
_ADOPTED_LOT = 1
_ADOPTED_MIN_QTY = 1
_ADOPTED_ADMITTING_PHASE = "CONTINUOUS"
_ADOPTED_OCP_VERSION = "1.0.0"


#: ``_runtime.construction.sizing.admitted_quantity_bases`` as SHIPPED since W-A / A-5
#: (2026-09-23, operator choice (가)): the deployed boot-proof strategy file
#: ``config/tos_runtime/paper/strategies/bootproof_band.strategy.yaml`` declares
#: ``quantity_basis: "RISK"``, which is the condition OCP sizing proposal §4 ② was waiting for.
#: No longer a test-local fixture value -- it is in the committed document, and
#: ``tests/compose/test_deploy_approved_values.py`` pins the two against each other.
_OCP_ADMITTED_QUANTITY_BASIS = "RISK"

#: ``_runtime.construction.axes``' ``DIRECTION`` entry as SHIPPED since W-A / A-5. One
#: direction per composition is all the current (proposal-path-less) design can express; the
#: SHORT arm is produced by ``scripts/tos/render_paper_config.py --direction SHORT``, never by
#: a second committed copy, and ``scope.action_classes`` still authorizes both.
_OCP_DIRECTION = "LONG"


def _filled(
    path: Path,
    *,
    environment: str,
    account: str,
    instrument: str,
    direction: str = _OCP_DIRECTION,
) -> dict:
    """The real document with ONLY the operator-fill coordinates filled -- exactly what
    ``scripts/tos/render_paper_config.py`` fills off-repo before ``print-policy-digests``.

    Since W-A / A-5 that is just the scope coordinates (+ the environment this suite boots
    under): ``admitted_quantity_bases`` and the ``DIRECTION`` axis are no longer operator-fill
    -- they are committed values now, asserted here rather than written, so a silent edit of
    either shows up as a failure in this file too.

    ``direction`` is the EXPECTED axis value, not a value written into the document: the
    assertion below still reads the file. It defaults to ``LONG`` -- the resident and LONG-tenant
    deployments -- and the CP-3 SHORT tenant tree passes ``"SHORT"``. A single hard-coded
    ``LONG`` here would have forced the SHORT tree's callers to skip this helper, and with it
    the ``admitted_quantity_bases`` check.

    ⚠ What the axis block below does and does not check: it asserts there is exactly ONE
    ``DIRECTION`` entry and that its value is the expected one. It does **not** check the length
    of ``axes`` or anything about the other axes -- a TIF axis edited, added or dropped passes
    straight through. (This docstring used to claim an "axis-count" check; review M2 found there
    was none.) The axes list as a whole is compared between the two tenant trees by
    ``test_tenant_tree_short.py::test_the_axes_list_differs_only_in_its_DIRECTION_entry``, and
    the resident tree's own axes are pinned in ``test_deploy_approved_values.py``.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), f"policy document loaded as {type(raw).__name__}"
    assert raw["scope"]["accounts"] == ["TBD"]
    assert raw["scope"]["instruments"] == ["TBD"]
    raw["scope"]["environments"] = [environment]
    raw["scope"]["accounts"] = [account]
    raw["scope"]["instruments"] = [instrument]
    construction = raw.get("_runtime", {}).get("construction")
    if construction is not None:
        assert construction["sizing"]["admitted_quantity_bases"] == [
            _OCP_ADMITTED_QUANTITY_BASIS
        ]
        direction_entries = [
            entry for entry in construction["axes"] if entry["axis"] == "DIRECTION"
        ]
        assert len(direction_entries) == 1
        assert direction_entries[0]["value"] == direction
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
    # The resident tree's tick is still the FULL-contract 5: the 5 → 2 correction is approved
    # but deferred HERE (band-source wave plan §3) -- pinned so the tenant correction cannot
    # drift into this tree without a deliberate edit plus the runbook §7.10 6 obligations.
    assert shape.tick_size == _RESIDENT_TICK
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
    # policy_generation 3 -- generation 2 was the (a′) wave's _runtime.construction block
    # ((a′) plan §2 decision 1: a new generation, not a field bolted onto generation 1);
    # generation 3 is the effect_dimensions proposal (2026-09-16), same discipline.
    assert ocp.policy.policy_generation == 3
    assert ocp.construction_generation == 1
    assert ocp.wire_codec_kind is None  # synthetic paper default
    assert ocp.construction_rules.effect_dimensions == (
        EffectDimensionSpec(
            dimension_id="INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL",
            basis=EffectBasis.QUANTITY,
            unit="CONTRACTS",
            scale="1",
        ),
    )
    assert ocp.construction_rules.sizing_bound.admitted_quantity_bases == frozenset(
        {_OCP_ADMITTED_QUANTITY_BASIS}
    )


# ---------------------------------------------------------------------------
# CP-3 tenant tree (Setup D / LONG) -- decision 9 (a)'s landing site
# ---------------------------------------------------------------------------


def test_tenant_venue_policy_carries_the_decision_9_provenance_and_its_three_caveats() -> (
    None
):
    """Design §8 step 5: the adopted value lands WITH its citation and §2.2's three caveats.

    The number alone is not the approved value -- ``config/tos_runtime/README.md`` makes the
    citation part of what admits a value into this directory, and design §2.2 makes the three
    caveats part of what the value MEANS (10,000 is the venue ceiling, the member limit is
    unconfirmed, the exchange may change it, and the cumulative limit is a different limit
    that does not apply to this 위탁계좌)."""
    prose = _comment_prose(_TENANT_VENUE_POLICY)
    assert _DECISION_9_PROVENANCE in prose
    for caveat in _DECISION_9_CAVEATS:
        assert caveat in prose, caveat
    # The tick correction's own provenance, landed 2026-10-09 (band-source wave plan §3), and
    # the fact that the resident tree deliberately kept 5. Both in this header, because this is
    # the file that carries the value.
    assert _TICK_PROVENANCE in prose
    assert _TICK_RESIDENT_DEFERRAL in prose

    # And the identity this tree's differing CONTENT requires: a policy whose typed content
    # differs from the resident one's may not share its (member_id, generation) -- an
    # activation record keyed on those could not tell the two documents apart. Renamed while
    # it was still free to rename (never booted, no activation record, no evidence); the
    # generation stays 1 because this is a DIFFERENT deployment's policy, not a next
    # generation of the resident one.
    tenant_raw = yaml.safe_load(_TENANT_VENUE_POLICY.read_text(encoding="utf-8"))
    resident_raw = yaml.safe_load(_REAL_VENUE_POLICY.read_text(encoding="utf-8"))
    assert tenant_raw["policy_id"] == _TENANT_VENUE_POLICY_ID
    assert tenant_raw["policy_id"] != resident_raw["policy_id"]
    assert tenant_raw["policy_generation"] == resident_raw["policy_generation"] == 1


def test_resident_paper_tree_records_the_deferral_rather_than_the_value() -> None:
    """The other half of design §8 step 5: the resident tree says a source now EXISTS and that
    adoption there is deferred, instead of silently looking like "no source was ever found".

    Paired with ``test_filled_real_policies_carry_exactly_the_adopted_values``' assertion that
    the resident ``max_quantity`` is still ``None``: together they pin "deferred", which
    neither assertion pins alone (a note without the null would permit a quiet adoption; the
    null without the note would keep claiming NO SOURCE)."""
    assert _PAPER_DEFERRAL_NOTE in _comment_prose(_REAL_VENUE_POLICY)
    assert "cp3-setup-d-long" in _comment_prose(_REAL_VENUE_POLICY)


def test_tenant_venue_policy_refuses_to_load_until_the_operator_fills_the_scope() -> (
    None
):
    """The tenant tree inherits the SAME operator-fill gate: accounts/instruments are
    ``"TBD"`` as committed and the loader refuses them, so landing a quantity ceiling did not
    turn this tree into something that boots on its own."""
    with pytest.raises(VenuePolicyConfigError):
        load_venue_constraint_policy(_TENANT_VENUE_POLICY, scheme=_SCHEME)


def test_filled_tenant_venue_policy_carries_10000_with_the_band_still_null(
    tmp_path: Path,
) -> None:
    """Decision 9 (a) is a NECESSARY, not sufficient, condition (design §3): the quantity
    ceiling is adopted, so step 2's "venue quantity constraint is incomplete" DENY is gone --
    but the price band is still ``null``, so ``order_shape_admissible`` stays ``UNKNOWN`` and
    nothing can be transmitted. Pinned together so a later edit cannot quietly land the band
    (a per-day dynamic value, design §6) alongside it and open a send path."""
    raw = _filled(
        _TENANT_VENUE_POLICY,
        environment="paper",
        account="acct-x",
        instrument="inst-x",
    )
    path = tmp_path / "venue_constraint_policy.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True))
    venue = load_venue_constraint_policy(path, scheme=_SCHEME)

    shape = venue.policy.shape_constraints
    assert shape.max_quantity == _ADOPTED_TENANT_MAX_QTY
    assert shape.price_min is None and shape.price_max is None
    # Only the band is unsourced now -- the quantity axis left this set.
    assert set(venue.null_shape_bounds) == {"price_min", "price_max"}
    # Two bounds differ from the resident tree now: decision 9's quantity ceiling and the
    # 2026-10-09 tick correction. ``tick_size`` is asserted as the MINI regulation value, which
    # is also the one value here that is inert today -- ``order_shape_admissible`` below returns
    # UNKNOWN on the null band BEFORE it examines the tick, so this assertion is the only thing
    # that can catch a wrong tick until a band source lands.
    assert shape.tick_size == _TENANT_TICK
    assert shape.tick_size != _RESIDENT_TICK
    assert shape.lot_size == _ADOPTED_LOT
    assert shape.min_quantity == _ADOPTED_MIN_QTY
    assert venue.scope.instrument_class == "krx-index-futures"

    # And the kernel's own shape predicate still refuses to admit an on-grid shape, for the
    # band's sake alone -- the same UNKNOWN the resident tree gets, reached for ONE reason
    # instead of two.
    on_grid = OrderShapeFields(
        price=5 * 100_000,
        quantity=1,
        order_type="LIMIT",
        tif="DAY",
        side="BUY",
        position_effect="OPEN",
        silently_rounded=False,
    )
    assert order_shape_admissible(on_grid, shape) is OrderAdmissibilityResult.UNKNOWN


def test_tenant_critical_input_policy_declares_fifteen_fields_with_the_adopted_max_age_ms() -> (
    None
):
    """CP-3 kickoff §5 1 / §5 3 ②: the tenant tree declares B1a's fifteen upstream fields with
    their unit/scale/multiplier/sign from B1a's own field lineage, plus the fifth value
    ``max_age_ms``, DECIDED by the operator 2026-10-09 ("max_age_ms : 800ms 로 정해") at grade
    **M** -- the kernel's own time-admission budget, with the reasons A/B/C would each be a false
    label written next to it.

    Until 2026-10-09 the fifteen were ``null`` and the loader refused the whole document. This
    test replaced that refusal pin; the "``null`` would still be refused" half now lives in
    ``test_tenant_critical_input_policy_still_refuses_a_null_max_age_ms``, so filling the key
    did not retire the guard that kept an unsourced value out. The first fill wrote 180000 (3
    bar periods, grade C); the operator superseded it the same day, and the header keeps that
    derivation as history rather than deleting it.

    The value is pinned as ONE number for all fifteen on purpose: B1a publishes the whole
    ``FIELD_ORDER`` as a single per-bar record under one label ``as_of_ms``, so there is no
    per-field lifetime to differentiate and a split would be an unexplained asymmetry.
    """
    path = _TENANT_DIR / "critical_input_policy.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    # Field set, ORDER, and the four sourced values per field -- all against
    # _B1A_FIELD_POLICY, whose literals come from B1a's own lineage. Pinning the exact
    # 4-tuple (not "some non-empty string") is the point: a wrong unit or multiplier is a
    # silently wrong SCALE on the number an order is priced and sized against, and
    # "non-empty" accepts every one of those.
    assert [entry["field_key"] for entry in raw["fields"]] == list(_B1A_FIELD_POLICY)

    # Two properties of the SHIPPED FILE, asserted as properties rather than as rows -- and
    # deliberately BEFORE the per-field loop below. Both read ``raw``, never the table: an
    # assert between two test constants would pass no matter what the tenant tree ships (PR
    # #884 re-check, LOW). Ordering is part of the design: the loop pins every field's whole
    # 4-tuple, so if it ran first it would catch any field-level mutation and leave these two
    # unable to fail -- a clause that cannot fail is not a guard. Running them first makes each
    # one the clause a scale/sign mutation actually trips.
    #
    # Their own contribution, beyond what the loop covers: ``_B1A_PRICE_FIELDS`` is what
    # ``test_tenant_construction_price_field_keys_are_declared_critical_inputs`` consults to
    # decide "is this key a price?". These bind that constant to the shipped file, so it cannot
    # drift into naming a field the file does not publish at the ×100 price scale.
    multipliers = {entry["field_key"]: entry["multiplier"] for entry in raw["fields"]}
    signs = {entry["field_key"]: entry["sign"] for entry in raw["fields"]}
    # The price-like fields are the ONLY ones at the ×100 scale the venue policy's tick_size
    # lives on (tick 2 = 0.02 index points at that scale, since the 2026-10-09 correction).
    assert {
        key for key, multiplier in multipliers.items() if multiplier == "100"
    } == _B1A_PRICE_FIELDS
    # z is the ONE signed field -- the LONG entry threshold -1800 is bound to that sign.
    assert {key for key, sign in signs.items() if sign == "signed"} == {"z_x1000"}

    for entry in raw["fields"]:
        key = entry["field_key"]
        assert (
            entry["unit"],
            entry["scale"],
            entry["multiplier"],
            entry["sign"],
        ) == _B1A_FIELD_POLICY[key], key
        # The fifth value -- the one with no source, set by the operator's decision.
        assert entry["max_age_ms"] == _TENANT_MAX_AGE_MS, key

    # And the document LOADS -- which is all this key buys on its own (see the 구속 결과 section
    # in its header and
    # ``test_the_adopted_max_age_ms_is_the_kernel_budget_label_stamped_bars_cannot_meet`` below:
    # a label-stamped bar's floor age is 75x this bound, so every field reads STALE).
    policy = load_critical_input_policy(path, scheme=_SCHEME)
    assert [field.field_key for field in policy.fields] == list(_B1A_FIELD_POLICY)
    assert {field.max_age_ms for field in policy.fields} == {_TENANT_MAX_AGE_MS}

    # The provenance the value cannot be read without: the operator's direction verbatim, the
    # grade, the derivation's three measured premises, the conservative direction, and the
    # re-derivation obligation. Pinned as strings for the same reason the decision-9 caveats
    # are -- a number whose derivation has been deleted is an invented number again.
    prose = _comment_prose(path)
    for sentence in _MAX_AGE_PROVENANCE:
        assert sentence in prose, sentence


def test_tenant_critical_input_policy_still_refuses_a_null_max_age_ms(
    tmp_path: Path,
) -> None:
    """Filling the fifteen did not retire the loader's refusal -- pinned BY KEY NAME against a
    tmp copy with ONE value nulled.

    This is the half that the old "refuses as committed" test carried for free and that the fill
    would otherwise have silently removed. Without it, a later edit that drops a ``max_age_ms``
    back to ``null`` (or omits it) would be caught by nothing in this file, and the whole reason
    the fifteen were ``null`` for two days was that this refusal is what keeps an unsourced
    freshness bound out of a booting deployment.

    ONE field, not all fifteen: a mutation that nulls every entry would also be caught by a
    loader that only checked the first, so nulling the LAST one proves the loader walks them
    all."""
    raw = yaml.safe_load(
        (_TENANT_DIR / "critical_input_policy.yaml").read_text(encoding="utf-8")
    )
    assert raw["fields"][-1]["field_key"] == "eod"  # B1a's FIELD_ORDER ends here
    raw["fields"][-1]["max_age_ms"] = None
    path = tmp_path / "critical_input_policy.yaml"
    path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    with pytest.raises(CriticalInputPolicyConfigError) as excinfo:
        load_critical_input_policy(path, scheme=_SCHEME)
    assert "max_age_ms" in str(excinfo.value)


def test_the_adopted_max_age_ms_is_the_kernel_budget_label_stamped_bars_cannot_meet() -> (
    None
):
    """The operator's 2026-10-09 decision, as arithmetic rather than a comment -- and its honest
    consequence in the same place.

    ``max_age_ms`` and the kernel's time-admission bound measure the SAME quantity --
    ``now_ms - as_of_ms`` (``marketfeed/snapshot.py::_derive_field_state``) and ``source_age =
    wall_clock_now() - as_of`` (``marketfeed/time_projection.py``'s own docstring). The decision
    binds the first to the budget the second leaves, so the two bounds are now one number.

    That makes the consequence sharper than it was at 180000, not softer. B1a stamps ``as_of_ms``
    at the bar's LABEL, i.e. its OPEN (``produce_fields.derive_as_of_ms``: "The label, not
    label+60s"), on 1-minute bars (``derive_raw_event_id``'s ``:1m:`` token), so the SMALLEST age
    such an observation can have is one bar period. At 180000 those fields read VALID here and
    were rejected one layer up by the time path; at 800 ``_derive_field_state`` itself returns
    ``(UNKNOWN, "stale")`` for **every one of the fifteen**. The fix is ③, the live producer
    (kickoff §5 3), and the decision is what makes append-time stamping a REQUIREMENT on it
    rather than a preference: a label-stamping ③ cannot be rescued by raising this bound,
    because the kernel would then refuse the same observation on the same quantity.

    ⚠ **Clause inventory, and one clause deliberately NOT asserted** (the masked-clause rule --
    host memory ``guards-that-admit-what-they-name.md``, #838):

    * ``budget == _TENANT_MAX_AGE_MS`` -- red when this tree's ``time.yaml`` moves either term
      (measured: raising ``MAX_time_conservative_freshness_age_ms`` 1000 -> 1200 across all three
      trees, which is what the byte-identity drift guards require, turns ONLY this test and
      ``test_approved_value_is_unchanged`` red). ⚠ It compares the derived budget against the
      CONSTANT, so it does **not** fire when the shipped fifteen move: that direction is
      ``test_tenant_critical_input_policy_...with_the_adopted_max_age_ms``'s per-field pin, which
      is what binds the constant to the file (measured: reverting the fifteen to 180000 turns
      that test red and leaves this one green). The two together are what stops the shipped
      number and its stated derivation from drifting apart; neither does it alone.
    * ``_TENANT_MAX_AGE_MS < _B1A_BAR_PERIOD_MS`` -- red if the bar period changes (measured:
      60_000 -> 600 turns ONLY this test red, with the clause above still green). This is the
      form ``_derive_field_state`` actually compares, which is why it is the one kept.
    * ``budget < _B1A_BAR_PERIOD_MS`` -- **not asserted**. Given the first clause it is the same
      statement as the second, so it could not fail on its own: a clause that cannot fail is not
      a guard, it is a decoration that makes the test look stronger than it is. (It WAS a
      separate fact at 180000, where the two numbers differed by 225x.)

    ⚠ **What this test does and does not guard.** It reads ``time.yaml`` and the runtime's own
    ``_DELAY_BOUND_FIELDS``, so it tracks those two. Everything else -- the bar period, the label
    semantics, the quantity the runtime compares -- is asserted as VALUES against the constants
    above, which carry the code citations in their own comments; this test does not re-derive
    them from ``produce_fields`` or ``snapshot.py`` (``tools`` is legacy-side and firewall-denied
    from here, and the comparison in ``snapshot.py`` is an expression, not a readable constant).
    So: a changed ``time.yaml`` or a changed delay-bound set fails here; a ③ that starts stamping
    at append time would NOT turn anything red -- it would simply stop reproducing the second
    clause's consequence at runtime. That asymmetry is the ③ obligation, not something this test
    closes."""
    budget = _tenant_kernel_time_budget_ms()

    # The decision: the fifteen ARE the kernel's conservative freshness budget.
    assert budget == _TENANT_MAX_AGE_MS

    # Its consequence under the current producer: one bar period is the FLOOR on a label-stamped
    # observation's age, and that floor is already past the adopted bound -- so every field reads
    # ``(UNKNOWN, "stale")`` and the kernel's UNKNOWN floor drops the key.
    assert _TENANT_MAX_AGE_MS < _B1A_BAR_PERIOD_MS


def test_tenant_construction_price_field_keys_are_declared_critical_inputs() -> None:
    """``construction.yaml``'s two price field keys must name fields the SAME tree's
    ``critical_input_policy.yaml`` declares -- the cross-check neither loader can perform.

    ``compose/_construction_config.py``'s own module docstring names this gap: "the only way a
    REAL deployment reaches the value-free branch is a tick whose critical-input policy does
    not cover ``price_field_key`` for this instrument -- a governance gap this loader cannot
    see or refuse from inside ``construction.yaml`` alone". The resident tree's value is
    ``"close"`` (its boot-proof policy declares ``close``/``lower_band``/``upper_band``); this
    tree declares B1a's fifteen, where the price-like field is ``close_x100`` and there is no
    ``close``. Copying the resident value here therefore named a field that does not exist.

    What that costs if it is wrong, measured rather than assumed: ``price_field_key`` is
    non-``None``, so ``OrderConstructionStage._price_for`` projects from the value view via
    ``admitted_price_from_view``, whose docstring states that a populated view LACKING the key
    yields an observation carrying the capsule source and snapshot lineage but **no value**,
    and that ``derive_order_size`` then denies with "no positive finite value". So it is a
    no-send, never a fabricated price -- but the denial reason does not name the
    misconfiguration, which is why it needs a test and not a comment.

    Also pinned: the keys sit at the ×100 scale the venue policy's ``tick_size`` lives on, so
    price and tick are on one grid."""
    construction = yaml.safe_load(
        (_TENANT_DIR / "construction.yaml").read_text(encoding="utf-8")
    )
    critical_input = yaml.safe_load(
        (_TENANT_DIR / "critical_input_policy.yaml").read_text(encoding="utf-8")
    )
    declared = {entry["field_key"] for entry in critical_input["fields"]}

    for key_name in ("price_field_key", "shape_price_field_key"):
        key = construction[key_name]
        assert key in declared, (
            f"construction.yaml::{key_name} = {key!r} is not declared by this tree's "
            f"critical_input_policy.yaml (declared: {sorted(declared)})"
        )
        # ... and it is a price, at the tick's own ×100 scale -- not a boolean gate, not z.
        assert key in _B1A_PRICE_FIELDS, (key_name, key)


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
