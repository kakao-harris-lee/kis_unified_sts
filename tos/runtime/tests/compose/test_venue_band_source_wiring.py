"""Compose-level band-source wiring — CP-3 band 원천 웨이브 plan §8 items 1, 2, 6 (the compose
half) and 7 (``docs/plans/2026-10-08-tos-cp3-band-source-wave-plan.md`` §4.1/§4.3/§5).

**§8 1 — the resident deployment must be unchanged.** Plan §5 keeps ``band_source`` ``null``/
absent in the resident ``paper/`` tree and in both CP-3 tenant trees, so this wave must be a
no-op there. :class:`TestShippedTreesDeclareNoBandSource` reads the REAL files and
:class:`TestTodaysRowsAreUnchanged` pins that a full compose boot still writes the SAME evidence
payloads — same keys, same ORDER (which is what "byte-identical" means for a JSON payload row),
no new key, and no ``VENUE_BAND_OBSERVED`` row at all.

**§8 7 — the host seal is the ``kis_quote`` transport's own, reused.** A deployment that turns
the band source on against a REAL ``rest_base`` refuses AT BOOT, through that document's own
loader, with no band-source-specific host check anywhere.

**No GET ever happens here.** The autouse hermetic guard (``tos/runtime/tests/conftest.py``
D1.4) refuses any non-loopback socket, so the "a ``kis_quote_get`` source does not read at
boot" assertion below is enforced by the harness and not just asserted: a boot that DID reach
for the band would fail loudly rather than quietly pass.

**Rescope plan M1 (2026-10-22) moved the ``"boot"`` read instant to the end of
``VenueConstraintService.__init__``** so a band-declaring tenant lands a
``VENUE_BAND_OBSERVED`` row per boot whether or not any proposal ever reaches the venue stage
(the measured 2026-10-22 session reached it zero times —
``docs/broker-profiles/evidence/2026-10-22-cp3-band-first-session/README.md`` §2). Two
consequences live in this file: :class:`TestTheProducerJournalKindReadsAtBoot` is the new
acceptance on the kind the tenant trees declare — it opens a file, so it reads at boot through
the real wiring and still touches no socket — and the ``kis_quote_get`` kind, whose reader is
late-bound to the KIS credential cell ``_finalize`` fills AFTER the venue service is built,
now refuses the boot outright if it declares ``"boot"``
(:meth:`TestADeclaredSourceAtBoot.test_a_kis_source_that_declares_boot_refuses_the_boot`).
Every ``kis_quote_get`` fixture below therefore pins ``read_on: ["phase_change"]``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.brokercap.instance import load_instance_documents
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose._venue_wiring import VenueBandSourceUnwired
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.transport.kis_mock.credential_session import (
    KisCredentialSessionConflict,
)
from tos_runtime.transport.kis_quote.config import (
    KisQuoteTransportConfigError,
    read_declared_instrument,
)
from tos_runtime.venue import VenuePolicyConfigError, load_venue_constraint_policy

from ..venue._documents import (
    band_source_runtime_extra,
    producer_journal_band_source_runtime_extra,
    venue_policy_yaml,
)
from . import _fixtures as fx
from .conftest import (
    _VENUE_POLICY_ACCOUNT,
    _VENUE_POLICY_ADMITTING_PHASE,
    _VENUE_POLICY_ENVIRONMENT,
    _VENUE_POLICY_INSTRUMENT,
    _VENUE_POLICY_INSTRUMENT_CLASS,
)
from .test_compose_root import (
    _action_flow_inputs,
    _aggregate_inputs,
    _compose,
    _reach_trusted,
)
from .test_marketfeed_intake_kind_wiring import _write_kis_quote_transport_config
from .test_transport_wiring import _activate_mock_stock_order, _build_custody
from .test_venue_wiring import _real_members, _rewrite_activation

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_ROOT = _REPO_ROOT / "config" / "tos_runtime"

#: Every tree this repo ships.
_SHIPPED_TREES = ("paper", "cp3-setup-d-long", "cp3-setup-d-short")

#: The trees that keep the band source OFF. Band plan §5: the resident one
#: forever-until-adopted (its observations are synthetic, so a band would make every attempt
#: INADMISSIBLE) and the SHORT tenant one until the operator turns it on.
#:
#: ⚠ **This set used to be all three.** 2026-10-16 (CP-3 band 원천 경로 변경 PR-B,
#: ``docs/plans/2026-10-15-tos-cp3-band-via-producer-plan.md`` §4) turned the LONG tenant tree
#: on with ``kind: "producer_journal"``, so the "no shipped tree declares one" claim below
#: splits in two rather than being deleted: the OFF trees still have to be measured OFF, and
#: that is what keeps the resident 08:45 session's behaviour unchanged.
_TREES_WITH_NO_BAND_SOURCE = ("paper", "cp3-setup-d-short")

#: The one tree that declares a source, and the kind it declares.
_TREE_WITH_A_BAND_SOURCE = "cp3-setup-d-long"

#: The exact payload key SETS of the two rows this wave touches, as they are written for a
#: tree that declares no band source. A set, not an order: the evidence store canonicalizes a
#: payload with sorted keys (measured — the rows come back key-sorted), so insertion order
#: cannot change the stored bytes but a new key can, and the equality below is what refuses one.
_POLICY_BOUND_KEYS = (
    "policy_id",
    "policy_generation",
    "canonical_digest",
    "activated_member_digest",
    "null_shape_bounds",
)
_SNAPSHOT_KEYS = (
    "snapshot_id",
    "canonical_digest",
    "constraint_generation",
    "observed_session_phase",
    "policy_digest",
    "absent_fields",
)


def _real_prod_rest_base() -> str:
    """The REAL_PROD INSTANCE document's own ``rest_base``, read from the document rather than
    typed as a literal: a hardcoded copy would silently stop being the real host the day the
    document moved, and this test would then prove nothing."""
    documents = load_instance_documents(
        _REPO_ROOT
        / "docs"
        / "broker-profiles"
        / "KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
    )
    real = next(d for d in documents if d.environment == "REAL_PROD")
    assert real.rest_base is not None
    return real.rest_base


def _payloads(runtime: Any, kind: str) -> list[dict[str, Any]]:
    cursor = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
    )
    return [json.loads(row[0])["payload"] for row in cursor.fetchall()]


def _declare_band_source(
    config_dir: Path, *, sync_activation: bool = True, **overrides: Any
) -> None:
    """Rewrite the compose fixture's venue policy so it DECLARES a band source, and re-sync the
    activation digest the rewrite invalidates (the same two-step every scope-mutation test in
    ``test_venue_wiring.py`` performs)."""
    overrides.setdefault("instrument", _VENUE_POLICY_INSTRUMENT)
    (config_dir / "venue_constraint_policy.yaml").write_text(
        venue_policy_yaml(
            environment=_VENUE_POLICY_ENVIRONMENT,
            account=_VENUE_POLICY_ACCOUNT,
            instrument=_VENUE_POLICY_INSTRUMENT,
            instrument_class=_VENUE_POLICY_INSTRUMENT_CLASS,
            admitting_phases=f'["{_VENUE_POLICY_ADMITTING_PHASE}"]',
            price_min="null",
            price_max="null",
            tick_size="2",
            runtime_extra=band_source_runtime_extra(**overrides),
        ),
        encoding="utf-8",
    )
    # A test that expects the LOADER to refuse must skip this: the sync re-loads the same
    # document through the same loader, so it would raise first and the test would pass for
    # the fixture's reason instead of the boot's.
    if sync_activation:
        _sync_venue_activation_digest(config_dir)


def _declare_producer_journal_band_source(
    config_dir: Path, *, band_journal_path: Path
) -> None:
    """The LONG tenant tree's own ``kind`` (``producer_journal``), declared on the compose
    fixture's venue policy and activation-synced — the sibling of :func:`_declare_band_source`
    for the only kind a shipped tree carries."""
    (config_dir / "venue_constraint_policy.yaml").write_text(
        venue_policy_yaml(
            environment=_VENUE_POLICY_ENVIRONMENT,
            account=_VENUE_POLICY_ACCOUNT,
            instrument=_VENUE_POLICY_INSTRUMENT,
            instrument_class=_VENUE_POLICY_INSTRUMENT_CLASS,
            admitting_phases=f'["{_VENUE_POLICY_ADMITTING_PHASE}"]',
            price_min="null",
            price_max="null",
            tick_size="2",
            runtime_extra=producer_journal_band_source_runtime_extra(
                instrument=_VENUE_POLICY_INSTRUMENT,
                band_journal_path=str(band_journal_path),
            ),
        ),
        encoding="utf-8",
    )
    # No `band_transport_instrument_reader`: this kind's cross-checks never consult the
    # `kis_quote` document (`_cross_check_band_source` — the last two rules are
    # `kis_quote_get`-only), so the plain loader is the right one here.
    loaded = load_venue_constraint_policy(
        config_dir / "venue_constraint_policy.yaml", scheme=_SCHEME
    )
    members = _real_members(config_dir)
    for member in members:
        if member["kind"] == "VENUE_CONSTRAINT_POLICY":
            member["digest"] = loaded.policy.canonical_digest
    _rewrite_activation(config_dir, members)


def _sync_venue_activation_digest(config_dir: Path) -> None:
    """``test_venue_wiring``'s own helper, re-declared here because that one loads the policy
    WITHOUT a ``band_transport_instrument`` — which is itself a boot refusal once the document
    declares a band source, so reusing it would mask the test under the fixture's own error.
    """
    loaded = load_venue_constraint_policy(
        config_dir / "venue_constraint_policy.yaml",
        scheme=_SCHEME,
        band_transport_instrument_reader=lambda: read_declared_instrument(
            config_dir / "kis_quote.yaml"
        ),
    )
    members = _real_members(config_dir)
    for member in members:
        if member["kind"] == "VENUE_CONSTRAINT_POLICY":
            member["digest"] = loaded.policy.canonical_digest
    _rewrite_activation(config_dir, members)


def _tree_runtime_block(tree: str) -> dict[str, Any]:
    raw = yaml.safe_load(
        (_CONFIG_ROOT / tree / "venue_constraint_policy.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert isinstance(raw["_runtime"], dict)
    return raw["_runtime"]


class TestShippedTreesDeclareNoBandSource:
    """Band plan §5 / §8 1 — the trees that keep the source OFF, read off the real files.

    Split from the LONG tree's own class (:class:`TestTheLongTenantTreeDeclaresTheProducer
    Journal`) on 2026-10-16 rather than relaxed: "every tree is off" stopped being true, and
    the half that is still true is the half that keeps the resident 08:45 session's behaviour
    byte-identical.
    """

    @pytest.mark.parametrize("tree", _TREES_WITH_NO_BAND_SOURCE)
    def test_the_runtime_block_carries_neither_key(self, tree: str) -> None:
        runtime = _tree_runtime_block(tree)

        assert "band_source" not in runtime
        assert "price_scale" not in runtime

    def test_the_real_resident_policy_loads_with_no_band_source_and_no_price_scale(
        self, tmp_path: Path
    ) -> None:
        """The resident file, operator-filled exactly as ``test_deploy_policies.py`` fills it,
        loaded through the REAL loader with NO ``band_transport_instrument`` supplied — the
        default. This is the assertion plan §4.1's 재리뷰 MEDIUM asks for: if the loader
        demanded ``_runtime.price_scale`` unconditionally, the resident 08:45 session would
        ABORT on the first boot after this merge."""
        raw = yaml.safe_load(
            (_CONFIG_ROOT / "paper" / "venue_constraint_policy.yaml").read_text(
                encoding="utf-8"
            )
        )
        raw["scope"]["environments"] = [_VENUE_POLICY_ENVIRONMENT]
        raw["scope"]["accounts"] = [_VENUE_POLICY_ACCOUNT]
        raw["scope"]["instruments"] = [_VENUE_POLICY_INSTRUMENT]
        path = tmp_path / "venue_constraint_policy.yaml"
        path.write_text(
            yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

        loaded = load_venue_constraint_policy(path, scheme=_SCHEME)

        assert loaded.band_source is None
        assert loaded.band_source_digest is None
        assert loaded.price_scale is None
        # And the policy's own band bounds stay the honest nulls plan §5 relies on: turning
        # the source on later is a config edit, not a literal to delete first.
        assert loaded.policy.shape_constraints.price_min is None
        assert loaded.policy.shape_constraints.price_max is None

    @pytest.mark.parametrize("tree", _SHIPPED_TREES)
    def test_no_tree_carries_a_kis_quote_document_today(self, tree: str) -> None:
        """Reading an ABSENT transport document answers ``None`` rather than raising — which
        is the only reason the unconditional ``read_declared_instrument`` call in
        ``build_venue_service`` is safe for every shipped tree.

        ⚠ Still EVERY tree, the LONG one included: ``producer_journal`` reaches no broker, so
        it needs no host seal and no transport document (2026-10-15 plan §3.3). That is also
        why the loader applies the two ``kis_quote`` rules to ``kis_quote_get`` only — this
        assertion is what makes "we could not have required one" a measurement.
        """
        assert read_declared_instrument(_CONFIG_ROOT / tree / "kis_quote.yaml") is None


class TestTheLongTenantTreeDeclaresTheProducerJournal:
    """2026-10-15 plan §4 "켜는 배포: LONG tenant 만" — the one tree that is ON, read off the
    real file and loaded through the real loader."""

    def test_the_runtime_block_declares_the_producer_journal_kind(self) -> None:
        runtime = _tree_runtime_block(_TREE_WITH_A_BAND_SOURCE)

        assert runtime["price_scale"] == 100
        band_source = runtime["band_source"]
        assert band_source["kind"] == "producer_journal"
        assert band_source["price_scale"] == 100
        assert band_source["bound"] == "trading_date_kst"
        assert band_source["read_on"] == ["boot", "phase_change"]
        assert band_source["failure"] == "unknown"
        # The three render slots are still named-TBD in the COMMITTED tree — the coordinates
        # are filled by `scripts/tos/render_paper_config.py`, never committed here
        # (`config/tos_runtime/README.md`).
        assert band_source["instrument"] == "TBD"
        assert band_source["band_journal_path"] == "TBD"
        assert band_source["approved_source_prefixes"] == ["TBD"]

    def test_it_declares_no_leaf_of_the_other_kind(self) -> None:
        """The loader refuses one (``_refuse_keys_of_the_other_kind``); this says the shipped
        document does not need that refusal to be correct."""
        band_source = _tree_runtime_block(_TREE_WITH_A_BAND_SOURCE)["band_source"]

        assert set(band_source) == {
            "kind",
            "instrument",
            "price_scale",
            "bound",
            "read_on",
            "failure",
            "band_journal_path",
            "approved_source_prefixes",
        }

    def test_the_committed_tree_loads_once_its_coordinates_are_filled(
        self, tmp_path: Path
    ) -> None:
        """The REAL file, coordinate slots filled the way the renderer fills them, through the
        REAL loader with NO ``band_transport_instrument`` supplied — the default, and what a
        ``producer_journal`` deployment actually has (there is no ``kis_quote.yaml``).

        This is the assertion that would have caught the 2026-10-15 enabling attempt's first
        failure (plan §1 B1/B2): a document that declares a source the deployment cannot read
        refuses at BOOT, and the only way to know is to load it.
        """
        text = (
            _CONFIG_ROOT / _TREE_WITH_A_BAND_SOURCE / "venue_constraint_policy.yaml"
        ).read_text(encoding="utf-8")
        raw = yaml.safe_load(text)
        raw["scope"]["environments"] = [_VENUE_POLICY_ENVIRONMENT]
        raw["scope"]["accounts"] = [_VENUE_POLICY_ACCOUNT]
        raw["scope"]["instruments"] = [_VENUE_POLICY_INSTRUMENT]
        raw["_runtime"]["band_source"]["instrument"] = _VENUE_POLICY_INSTRUMENT
        raw["_runtime"]["band_source"]["band_journal_path"] = str(
            tmp_path / "producer" / "band.jsonl"
        )
        raw["_runtime"]["band_source"]["approved_source_prefixes"] = ["tos-cp3-live"]
        path = tmp_path / "venue_constraint_policy.yaml"
        path.write_text(
            yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

        loaded = load_venue_constraint_policy(path, scheme=_SCHEME)

        assert loaded.band_source is not None
        assert loaded.band_source.kind == "producer_journal"
        assert loaded.price_scale == 100
        assert loaded.band_source_digest is not None
        # The band fills these, so the policy must NOT carry literals (band plan §4.1).
        assert loaded.policy.shape_constraints.price_min is None
        assert loaded.policy.shape_constraints.price_max is None
        # And the tick correction the band depends on is in place: the measured 0.02-grid
        # band would be refused by a tree still carrying 5.
        assert loaded.policy.shape_constraints.tick_size == 2


class TestTodaysRowsAreUnchanged:
    """Plan §8 1 — a full compose boot plus one real attempt writes the same payloads it
    wrote before this wave.

    **The attempt is not decoration.** Boot alone writes ``VENUE_POLICY_BOUND`` and nothing
    else: ``VENUE_SNAPSHOT_ISSUED`` appears only once something calls ``snapshot()``. A version
    of this test that asserted over the snapshot rows WITHOUT driving an attempt iterated an
    empty list and passed no matter what the row looked like — caught by its own red proof
    (#838's "a clause that changes nothing when deleted was never judging"), which is why
    :func:`run_once` is here and why the count is asserted before the contents.

    **The byte-identical claim is MEASURED, not inferred.** 2026-10-09: this exact boot +
    attempt was run against this branch and against ``origin/main``'s own ``tos/`` tree
    (``git archive origin/main tos``), dumping all four kinds' payloads as sorted JSON. The two
    dumps compared equal byte for byte — sha256
    ``7b7ad4be04636ac674a10a00c151285cf6400310177b26d38a3d21b218009be7`` on both sides. The
    assertions below are what keeps that true from here on: the evidence store canonicalizes a
    payload with sorted keys, so order cannot drift, but a NEW key would, and the set
    equalities refuse one.
    """

    def test_the_rows_carry_exactly_the_pre_wave_keys(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        try:
            _reach_trusted(runtime)
            runtime.run_once((fx.crossing_event(),))

            (policy_row,) = _payloads(runtime, "VENUE_POLICY_BOUND")
            assert set(policy_row) == set(_POLICY_BOUND_KEYS)
            snapshot_rows = _payloads(runtime, "VENUE_SNAPSHOT_ISSUED")
            assert (
                snapshot_rows
            ), "no snapshot row — the assertions below would be vacuous"
            # L4 — an OBSERVATION of the null path's shape, deliberately NOT claimed as a
            # guard. One attempt at one phase writes exactly one snapshot row, at generation
            # 1. Three separate single-clause mutations were tried against it (forcing
            # `phase_changed`, bypassing the tick-generation cache early return, and dropping
            # the no-material-change early return) and all three stayed GREEN, because
            # `snapshot()` is only ever reached once per attempt here. So it pins the measured
            # shape — which a later extra issuance or a skipped generation would break — and
            # #838 says to say that rather than let it read like a clause-level guard.
            assert len(snapshot_rows) == 1
            assert [row["constraint_generation"] for row in snapshot_rows] == [1]
            for snapshot_row in snapshot_rows:
                assert set(snapshot_row) == set(_SNAPSHOT_KEYS)
                assert snapshot_row["absent_fields"] == [
                    "critical_input_snapshot_digest",
                    "source_continuity_id",
                    "max_age",
                ]
            decision_rows = _payloads(runtime, "ORDER_ADMISSIBILITY_DECISION_ISSUED")
            assert decision_rows, "no decision row — plan §8 1 covers both"
            for decision_row in decision_rows:
                assert set(decision_row) == {
                    "decision_id",
                    "canonical_digest",
                    "result",
                    "failed_predicates",
                    "unknown_predicates",
                    "candidate_command_digest",
                    "snapshot_id",
                }
            assert _payloads(runtime, "VENUE_BAND_OBSERVED") == []
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()

    def test_the_service_holds_no_band_reader(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """``build_venue_service`` builds a reader ONLY when the policy declares a source
        (plan §4) — the factory is constructed unconditionally in ``root.py``, so the thing
        that must be conditional is the CALL."""
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        try:
            assert runtime.venue._band_reader is None  # noqa: SLF001
            assert runtime.venue._trading_date_reader is None  # noqa: SLF001
            assert runtime.venue._band_source_declared is False  # noqa: SLF001
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()


class TestStepThreeAndItemElevenReadOneObject:
    """Plan §8 2 — the venue stage (step 3's folds) and the send-boundary context (item 11)
    must never disagree about the effective constraints.

    They cannot, structurally, and the chain is three links long:
    :meth:`~tos_runtime.compose.context.ComposeContextResolver.resolve` passes
    ``venue_shape_constraints=self.venue_stage.shape_constraints``
    (``compose/context.py:850``); that stage property returns
    ``self._service.shape_constraints``; and step 3's own two folds pass the same property into
    ``VenueConstraintStage``. This test pins the two links the compose root owns on a REAL
    composed runtime — if the stage ever cached a copy at construction, a band arriving later
    would reach the decision and NOT item 11, and nothing else in the suite would notice.

    The third link — that a band actually moves the value both of them then read — is unit-
    tested in ``tests/venue/test_service_band.py::TestEffectiveConstraints`` (including through
    the kernel predicate), because the band's own read instants are boot and a session-phase
    change: injecting one into an ALREADY-composed runtime would mean reaching past the public
    surface, which is weaker evidence than driving the same property directly.
    """

    def test_the_stage_serves_the_services_own_effective_constraints_object(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        try:
            assert (
                runtime.venue_stage.shape_constraints is runtime.venue.shape_constraints
            )
            # And the resolver really does read it off the stage, not off a snapshot of its
            # own taken at construction.
            assert (
                runtime.context_resolver.venue_stage.shape_constraints
                is runtime.venue.shape_constraints
            )
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()


class TestADeclaredSourceAtBoot:
    """Plan §4/§8 6/§8 7 — what a deployment that turns the source on actually gets."""

    def _kis_mock_boot(self, config_dir: Path, custody_root: Path) -> None:
        """The fixture setup a ``kis_quote``-document boot needs: the MOCK_STOCK_ORDER scope
        (the only one bound to the MOCK_VTS INSTANCE document) plus custody — exactly the
        shape ``test_marketfeed_intake_kind_wiring.py`` documents for its own kis_quote tests.
        """
        _activate_mock_stock_order(config_dir)
        fx.write_kis_mock_transport_config(config_dir)
        _build_custody(custody_root)

    def test_a_phase_change_only_kis_source_boots_and_reads_nothing_at_boot(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """Plan §6 (A): the band GET is the paper runtime's FIRST external call. A
        ``kis_quote_get`` deployment that does NOT declare the ``"boot"`` instant still makes
        none at boot — and the autouse network guard would raise if it did, so this assertion
        is harness-enforced rather than merely stated.

        ⚠ ``read_on`` is pinned to ``["phase_change"]`` here, which is no longer the default:
        since the rescope plan's M1 the ``"boot"`` instant is
        ``VenueConstraintService.__init__``, and for THIS kind that is before the credential
        registry exists — see
        :meth:`test_a_kis_source_that_declares_boot_refuses_the_boot`.
        """
        self._kis_mock_boot(config_dir, custody_root)
        _write_kis_quote_transport_config(
            config_dir, instrument=_VENUE_POLICY_INSTRUMENT
        )
        _declare_band_source(config_dir, read_on='["phase_change"]')

        runtime = _compose(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            transport_kind=TransportKind.KIS_MOCK,
        )
        try:
            assert runtime.venue._band_reader is not None  # noqa: SLF001
            assert runtime.venue._trading_date_reader is not None  # noqa: SLF001
            assert runtime.venue._band_source_declared is True  # noqa: SLF001
            assert runtime.venue._band is None  # noqa: SLF001
            assert _payloads(runtime, "VENUE_BAND_OBSERVED") == []
            (policy_row,) = _payloads(runtime, "VENUE_POLICY_BOUND")
            assert policy_row["band_source_digest"] is not None
            assert policy_row["price_scale"] == 100
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()

    def test_a_real_rest_base_refuses_at_boot_through_the_transports_own_seal(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """Plan §8 7. The refusal comes from
        :func:`~tos_runtime.transport.kis_quote.config.load_kis_quote_transport_config` — the
        band reader adds no host check of its own, which is the point: one seal, one place it
        can be wrong."""
        self._kis_mock_boot(config_dir, custody_root)
        _write_kis_quote_transport_config(
            config_dir,
            instrument=_VENUE_POLICY_INSTRUMENT,
            endpoint_rest_base=_real_prod_rest_base(),
        )
        _declare_band_source(config_dir)

        with pytest.raises(KisQuoteTransportConfigError) as excinfo:
            _compose(
                tmp_path,
                config_dir,
                data_dir,
                custody_root,
                transport_kind=TransportKind.KIS_MOCK,
            )

        assert "REAL_PROD" in str(excinfo.value)

    def test_the_order_transport_stays_the_shared_sessions_creator(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """Re-review LOW-2. ``KisCredentialSessions.session_for`` CREATES the one app-key
        session for its first caller, and that caller's client issues every later token —
        including the order transport's. The band reader must therefore take the session
        AFTER the order transport, not before.

        Dispatching the cell's callbacks inside ``fill`` (which runs before
        ``wire_engine_and_driver``) made the band reader the creator, so the order transport's
        token requests would have gone out through a client built from
        ``band_source.timeout_ms`` and ``kis_quote.yaml``'s own plaintext flag — neither of
        which the order transport ever declared. The assertion is object identity on the
        token lifecycle's client, because that is the thing that silently changes.
        """
        self._kis_mock_boot(config_dir, custody_root)
        # Token TERMS identical to the order transport's, so nothing refuses and the only
        # difference left is which client created the session.
        _write_kis_quote_transport_config(
            config_dir, instrument=_VENUE_POLICY_INSTRUMENT
        )
        # `["phase_change"]` for the same reason as the test above: this kind cannot be read
        # at the boot instant on this compose path.
        _declare_band_source(config_dir, read_on='["phase_change"]')

        runtime = _compose(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            transport_kind=TransportKind.KIS_MOCK,
        )
        try:
            transport = runtime.transport
            session = transport._credential_session  # noqa: SLF001
            # One app key, one session (C-2 decision (C)) — the band reader holds this very
            # object, so "whose client is inside it" is the whole question.
            assert (
                session._lifecycle._client  # noqa: SLF001
                is transport._client  # noqa: SLF001
            )
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()

    def test_a_session_terms_conflict_refuses_at_BOOT_not_at_the_first_decision(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """Independent review M1. One app key gets one token lifecycle (C-2 decision (C)), so
        two consumers declaring different token terms is a
        :class:`KisCredentialSessionConflict`. It must surface while compose is still running
        — a reader built on its FIRST READ instead would raise this hours later, inside a
        decision, which is exactly what the factory's docstring promised it would not do.

        The conflicting leaf is the reissue cooldown: the order transport's
        ``kis_mock_transport.yaml`` and this ``kis_quote.yaml`` disagree about it.
        """
        self._kis_mock_boot(config_dir, custody_root)
        _write_kis_quote_transport_config(
            config_dir,
            instrument=_VENUE_POLICY_INSTRUMENT,
            token_reissue_min_interval_s=61,
        )
        # `["phase_change"]`: with `"boot"` declared this kind refuses EARLIER, over the
        # registry not existing yet, and the conflict below would never be reached — the test
        # would pass for the wrong refusal.
        _declare_band_source(config_dir, read_on='["phase_change"]')

        with pytest.raises(KisCredentialSessionConflict):
            _compose(
                tmp_path,
                config_dir,
                data_dir,
                custody_root,
                transport_kind=TransportKind.KIS_MOCK,
            )

    def test_a_kis_source_that_declares_boot_refuses_the_boot(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """Rescope plan M1 — the one input that reaches :class:`VenueBandSourceUnwired`.

        The ``"boot"`` read instant is ``VenueConstraintService.__init__``, which
        :func:`~tos_runtime.compose._venue_wiring.build_venue_service` runs before
        ``_finalize`` fills the KIS credential cell. For ``kind: kis_quote_get`` that is too
        early by construction, so the deployment refuses LOUDLY at boot instead of running
        with a band source it can never read at the instant it declared. The sibling kind
        ``producer_journal`` — the only one any shipped tree declares — has no such
        dependency; :class:`TestTheProducerJournalKindReadsAtBoot` is its counterpart.
        """
        self._kis_mock_boot(config_dir, custody_root)
        _write_kis_quote_transport_config(
            config_dir, instrument=_VENUE_POLICY_INSTRUMENT
        )
        _declare_band_source(config_dir, read_on='["boot", "phase_change"]')

        with pytest.raises(VenueBandSourceUnwired) as excinfo:
            _compose(
                tmp_path,
                config_dir,
                data_dir,
                custody_root,
                transport_kind=TransportKind.KIS_MOCK,
            )

        assert "kis_quote_get" in str(excinfo.value)
        assert "producer_journal" in str(excinfo.value)

    def test_a_null_band_source_boots_beside_a_still_TBD_transport_document(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """Independent review L1. ``build_venue_service`` hands the loader a THUNK, which the
        loader calls only once it has parsed a non-null ``band_source``. Read eagerly instead,
        THIS boot would ABORT — a deployment with the band source off, refusing over a
        document nothing in its configuration consults. Every tree shipped today is in exactly
        this state (plan §5), so the refusal would have been the resident 08:45 session.
        """
        self._kis_mock_boot(config_dir, custody_root)
        _write_kis_quote_transport_config(
            config_dir, instrument="TBD", token_path="TBD"
        )
        # The venue policy is the fixture one: no `_runtime.band_source` at all.
        assert "band_source" not in (
            config_dir / "venue_constraint_policy.yaml"
        ).read_text(encoding="utf-8")

        runtime = _compose(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            transport_kind=TransportKind.KIS_MOCK,
        )
        try:
            assert runtime.venue._band_reader is None  # noqa: SLF001
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()

    def test_a_declared_source_without_a_transport_document_refuses_at_boot(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """Plan §4.1's "transport 설정 부재" refusal, reached through the real compose root —
        the loader's own rule, fed by ``build_venue_service``'s unconditional
        ``read_declared_instrument`` call."""
        self._kis_mock_boot(config_dir, custody_root)
        assert not (config_dir / "kis_quote.yaml").exists()
        _declare_band_source(config_dir, sync_activation=False)

        with pytest.raises(VenuePolicyConfigError) as excinfo:
            _compose(
                tmp_path,
                config_dir,
                data_dir,
                custody_root,
                transport_kind=TransportKind.KIS_MOCK,
            )

        assert "no kis_quote transport document" in str(excinfo.value)


class TestTheProducerJournalKindReadsAtBoot:
    """Rescope plan M1 (``docs/plans/2026-10-22-tos-rescope-plan.md``) — the band is
    OBSERVABLE at boot on the kind the CP-3 tenant trees actually declare.

    **The measured input** (``docs/broker-profiles/evidence/
    2026-10-22-cp3-band-first-session/README.md`` §2): on the first enabled session every
    proposal was denied at ``CANDIDATE_COMMAND_CONSTRUCTION``, which is upstream of every
    caller of ``snapshot()``, so the band was never read and acceptance 1c/2/3 were recorded
    NOT EXERCISED. This class is that day with the M1 change: a full compose boot, **no
    attempt driven at all**, and the row is there.

    The companion unit tests (``tests/venue/test_service_band.py::TestTheBandIsReadAtBoot``)
    pin the per-outcome shape; what only a compose boot can show is that the real wiring
    reaches the reader before anything calls ``snapshot()``.
    """

    #: The KST trading date the compose fixture's FIXED wall clock
    #: (``_fixtures.DEFAULT_WALL_CLOCK_UNIX_MS``) lands on — derived from that constant, never
    #: typed as a literal, so moving the fixture clock moves this with it.
    _TRADING_DATE = datetime.fromtimestamp(
        fx.DEFAULT_WALL_CLOCK_UNIX_MS / 1000, tz=timezone(timedelta(hours=9))
    ).strftime("%Y%m%d")

    def _band_line(self, **overrides: Any) -> dict[str, Any]:
        """One ``cp3-band/1`` line carrying the P-VL ``A05610`` measurement (987.46/1159.18
        about 1073.32), which sits on the policy's ``tick_size: 2`` grid at
        ``price_scale: 100`` — the same numbers ``tests/venue/test_band_journal.py``
        validates."""
        line: dict[str, Any] = {
            "kind": "cp3-band/1",
            "source_id": "tos-cp3-live/0.1.0",
            "instrument": _VENUE_POLICY_INSTRUMENT,
            "trading_date": self._TRADING_DATE,
            "tr_id": "FHMIF10000000",
            "upper": "1159.18",
            "lower": "987.46",
            "basis": "1073.32",
            "raw_payload_digest": "a" * 64,
            "producer_continuity_id": "band-probe/1",
            "as_of_ms": 1_760_577_960_000,
        }
        line.update(overrides)
        return line

    def _boot(
        self,
        tmp_path: Path,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        *,
        journal_bytes: bytes | None,
    ) -> Any:
        journal = tmp_path / "band.jsonl"
        if journal_bytes is not None:
            journal.write_bytes(journal_bytes)
        _declare_producer_journal_band_source(config_dir, band_journal_path=journal)
        return _compose(tmp_path, config_dir, data_dir, custody_root)

    def test_a_usable_journal_lands_one_observed_row_with_no_attempt_driven(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        line = self._band_line()
        runtime = self._boot(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            journal_bytes=json.dumps(line).encode("utf-8") + b"\n",
        )
        try:
            (row,) = _payloads(runtime, "VENUE_BAND_OBSERVED")

            assert row["outcome"] == "OBSERVED"
            assert row["raw_payload_digest"] == line["raw_payload_digest"]
            assert (row["price_min"], row["price_max"]) == (98_746, 115_918)
            assert row["raw_payload_digest_source"] == "producer"
            # The whole point: nothing called `snapshot()`, so pre-M1 this list was empty and
            # the band was unmeasurable.
            assert _payloads(runtime, "VENUE_SNAPSHOT_ISSUED") == []
            assert runtime.venue.shape_constraints.price_max == 115_918
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()

    def test_an_absent_journal_lands_one_refused_row_naming_the_reason(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """The other half of the operator's acceptance: ``REFUSED`` with a reason, not
        silence. A boot that cannot read the band still BOOTS — the runner may still be
        waiting for the probe's first line, and a band-less runtime is the conservative state
        (band plan §4.6: band ``None`` ⇒ kernel ``UNKNOWN`` ⇒ 송신 0)."""
        runtime = self._boot(
            tmp_path, config_dir, data_dir, custody_root, journal_bytes=None
        )
        try:
            (row,) = _payloads(runtime, "VENUE_BAND_OBSERVED")

            assert row["outcome"] == "REFUSED"
            assert row["reason"] == "journal_absent"
            assert runtime.venue.shape_constraints.price_max is None
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()

    def test_the_2026_10_22_shape_reproduced_an_upstream_halt_still_leaves_the_row(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """**The measured day, reproduced.** Driving a real event against this policy halts
        at ``CANDIDATE_COMMAND_CONSTRUCTION`` with ``STAGE_DENIED`` — the same halt step and
        reason all 25 proposals took on 2026-10-22 (evidence README §2) — so ``snapshot()``
        is never called and ``VENUE_SNAPSHOT_ISSUED`` stays empty. That is the day that
        produced zero band rows. It now produces exactly one.

        The halt is asserted, not merely allowed: if this fixture ever started reaching step
        3, this test would stop reproducing the shape it is named after and would have to be
        rewritten rather than silently measuring something else.
        """
        runtime = self._boot(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            journal_bytes=json.dumps(self._band_line()).encode("utf-8") + b"\n",
        )
        try:
            assert len(_payloads(runtime, "VENUE_BAND_OBSERVED")) == 1
            _reach_trusted(runtime)
            runtime.run_once((fx.crossing_event(),))

            (consumed,) = _payloads(runtime, "EVENT_CONSUMED")
            assert consumed["halt_reason"] == "STAGE_DENIED"
            assert (
                consumed["flow_fingerprint"]["halt_step"]
                == "CANDIDATE_COMMAND_CONSTRUCTION"
            )
            assert _payloads(runtime, "VENUE_SNAPSHOT_ISSUED") == []
            assert len(_payloads(runtime, "VENUE_BAND_OBSERVED")) == 1
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()

    def test_the_first_snapshot_adds_no_second_row_for_the_boot_instant(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """One instant, one row, on the REAL composed service. ``snapshot()`` is called
        directly because the fixture's own attempts halt upstream of it (the test above) —
        the object is the production one either way."""
        runtime = self._boot(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            journal_bytes=json.dumps(self._band_line()).encode("utf-8") + b"\n",
        )
        try:
            assert len(_payloads(runtime, "VENUE_BAND_OBSERVED")) == 1

            snapshot = runtime.venue.snapshot()

            assert len(_payloads(runtime, "VENUE_BAND_OBSERVED")) == 1
            assert (
                snapshot.critical_input_snapshot_digest
                == _payloads(runtime, "VENUE_BAND_OBSERVED")[0]["band_digest"]
            )
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()


class TestTheBootReadOnTheProductionClockPath:
    """The boot read against the clock reference PRODUCTION wires, not the suite's fixed one.

    ⚠ **Why this class exists** (independent review MEDIUM-1). Moving the ``"boot"`` read into
    ``VenueConstraintService.__init__`` put it outside the runner's per-cycle
    ``time_service.evaluate()``, and the first thing
    :meth:`~tos_runtime.venue.band_journal.ProducerJournalBandReader.read` does is ask
    ``trading_date_reader()`` — which on the real compose path is
    ``FreshTrustedWallClockReference(time_service, max_age_ms=1000)``
    (``_session_wiring.py:203-210``, from the shipped
    ``MAX_time_conservative_freshness_age_ms``), a reference that goes honestly absent once
    the last evaluated snapshot is older than that bound. Every other test in this file
    reaches compose through ``_compose``, which always passes ``wall_clock=``, and that
    REPLACES the reference this class is about (``test_compose_root._compose``'s own
    docstring says so). So the band boot read had no coverage on the production reference at
    all; the sibling that does cover it for the egress trading date is
    ``test_session_wiring.py::test_production_default_dates_egress_results_through_a_fresh_trusted_reference``.

    The OS clock underneath is PINNED with :func:`~._fixtures.pin_system_clock`, which shifts
    ``LocalSystemClockReader`` and leaves every other wire in place — so the assertion is
    about the wiring and not about the host clock (the same reasoning
    ``test_session_wiring.py`` records for its own pin).

    **The stale branch is pinned at unit level, deliberately**
    (``tests/venue/test_service_band.py::TestTheBandIsReadAtBoot
    ::test_a_clock_stale_boot_is_refused_and_then_retried_at_the_first_snapshot``). Staleness
    here is driven by ``TrustworthyTimeService.wall_clock_now_if_fresh``'s own
    ``self._monotonic.now_ms() - issued`` (``time/service.py:759``), so reproducing it through
    compose would mean injecting a monotonic source that jumps between compose's two boot
    ``evaluate()`` calls and the venue build — a test bound to compose's internal call
    ORDERING, which would go green on a reordering that still broke the band. The seam the
    behaviour actually lives at is ``trading_date_reader`` answering ``None``, and that is
    what the unit test drives.
    """

    def _boot_on_the_production_clock(
        self,
        tmp_path: Path,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        *,
        trading_date: str,
    ) -> Any:
        journal = tmp_path / "band.jsonl"
        # Same line builder the fixed-clock class uses, so the two differ ONLY in which
        # wall-clock reference compose wired.
        line = TestTheProducerJournalKindReadsAtBoot()._band_line(
            trading_date=trading_date
        )
        journal.write_bytes(json.dumps(line).encode("utf-8") + b"\n")
        _declare_producer_journal_band_source(config_dir, band_journal_path=journal)
        fx.write_band_strategy_file(config_dir)
        return compose_paper_runtime(
            config_dir,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=_aggregate_inputs,
            action_flow_inputs_provider=_action_flow_inputs,
            transport_kind=TransportKind.SYNTHETIC,
            # wall_clock intentionally omitted — the production default, which is the whole
            # point of this class. `_compose` would override it.
        )

    def test_the_boot_read_reaches_the_production_fresh_trusted_reference(
        self,
        tmp_path: Path,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A fresh production clock dates the boot read, so the band is in force before
        anything calls ``snapshot()`` — the M1 property, on the real reference.

        The journal line's ``trading_date`` is DERIVED from the pinned instant rather than
        typed, so this asserts "the date the production reference produced is the date the
        reader compared against", which is the actual wiring claim. A literal would make a
        pin-value change look like a band defect.
        """
        pinned = fx.LAST_MINUTE_OF_DAY_UNIX_MS
        fx.pin_system_clock(monkeypatch, pinned)
        trading_date = datetime.fromtimestamp(
            pinned / 1000, tz=timezone(timedelta(hours=9))
        ).strftime("%Y%m%d")

        runtime = self._boot_on_the_production_clock(
            tmp_path,
            config_dir,
            data_dir,
            custody_root,
            trading_date=trading_date,
        )
        try:
            _reach_trusted(runtime)
            (row,) = _payloads(runtime, "VENUE_BAND_OBSERVED")

            # Not REFUSED/trading_date_unavailable: the fresh-trusted reference answered.
            assert row["outcome"] == "OBSERVED"
            assert row["trading_date"] == trading_date
            assert (row["price_min"], row["price_max"]) == (98_746, 115_918)
            # And it happened at BOOT, with no snapshot issued.
            assert _payloads(runtime, "VENUE_SNAPSHOT_ISSUED") == []
            assert runtime.venue.shape_constraints.price_max == 115_918
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()
