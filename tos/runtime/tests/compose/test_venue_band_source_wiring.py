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
D1.4) refuses any non-loopback socket, so the "a declared source does not read at boot"
assertion below is enforced by the harness and not just asserted: a boot that DID reach for the
band would fail loudly rather than quietly pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.brokercap.instance import load_instance_documents
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.transport.kis_quote.config import (
    KisQuoteTransportConfigError,
    read_declared_instrument,
)
from tos_runtime.venue import VenuePolicyConfigError, load_venue_constraint_policy

from ..venue._documents import band_source_runtime_extra, venue_policy_yaml
from . import _fixtures as fx
from .conftest import (
    _VENUE_POLICY_ACCOUNT,
    _VENUE_POLICY_ADMITTING_PHASE,
    _VENUE_POLICY_ENVIRONMENT,
    _VENUE_POLICY_INSTRUMENT,
    _VENUE_POLICY_INSTRUMENT_CLASS,
)
from .test_compose_root import _compose, _reach_trusted
from .test_marketfeed_intake_kind_wiring import _write_kis_quote_transport_config
from .test_transport_wiring import _activate_mock_stock_order, _build_custody
from .test_venue_wiring import _real_members, _rewrite_activation

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_ROOT = _REPO_ROOT / "config" / "tos_runtime"

#: Every tree this PR ships. Plan §5: all three keep the band source off — the resident one
#: forever-until-adopted (its observations are synthetic), the tenant ones until CP-3 §5 3 ③
#: produces real prices.
_SHIPPED_TREES = ("paper", "cp3-setup-d-long", "cp3-setup-d-short")

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


def _sync_venue_activation_digest(config_dir: Path) -> None:
    """``test_venue_wiring``'s own helper, re-declared here because that one loads the policy
    WITHOUT a ``band_transport_instrument`` — which is itself a boot refusal once the document
    declares a band source, so reusing it would mask the test under the fixture's own error.
    """
    loaded = load_venue_constraint_policy(
        config_dir / "venue_constraint_policy.yaml",
        scheme=_SCHEME,
        band_transport_instrument=read_declared_instrument(
            config_dir / "kis_quote.yaml"
        ),
    )
    members = _real_members(config_dir)
    for member in members:
        if member["kind"] == "VENUE_CONSTRAINT_POLICY":
            member["digest"] = loaded.policy.canonical_digest
    _rewrite_activation(config_dir, members)


class TestShippedTreesDeclareNoBandSource:
    """Plan §5 / §8 1 — the state this PR ships, read off the real files."""

    @pytest.mark.parametrize("tree", _SHIPPED_TREES)
    def test_the_runtime_block_carries_neither_key(self, tree: str) -> None:
        raw = yaml.safe_load(
            (_CONFIG_ROOT / tree / "venue_constraint_policy.yaml").read_text(
                encoding="utf-8"
            )
        )

        assert "band_source" not in raw["_runtime"]
        assert "price_scale" not in raw["_runtime"]

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
        ``build_venue_service`` is safe for every shipped tree."""
        assert read_declared_instrument(_CONFIG_ROOT / tree / "kis_quote.yaml") is None


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

    They cannot, structurally: both read
    :attr:`~tos_runtime.compose._venue_wiring.VenueServiceStage.shape_constraints`, which
    delegates to the service's own property. This test pins that delegation on a REAL composed
    runtime — if the stage ever cached a copy of the constraints at construction, a band
    arriving later would reach the decision and not item 11.
    """

    def test_the_stage_serves_the_services_own_effective_constraints_object(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        try:
            assert (
                runtime.venue_stage.shape_constraints is runtime.venue.shape_constraints
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

    def test_a_declared_source_boots_and_reads_nothing_at_boot(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """Plan §6 (A): the band GET is the paper runtime's FIRST external call. Boot itself
        must still make none — and the autouse network guard would raise if it did, so this
        assertion is harness-enforced rather than merely stated."""
        self._kis_mock_boot(config_dir, custody_root)
        _write_kis_quote_transport_config(
            config_dir, instrument=_VENUE_POLICY_INSTRUMENT
        )
        _declare_band_source(config_dir)

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
