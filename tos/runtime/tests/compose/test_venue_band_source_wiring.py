"""Compose-level band-source wiring — CP-3 band 원천 웨이브 plan §8 items 1, 2, 6 (the compose"""

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
    _action_flow_inputs_for,
    _aggregate_inputs,
    _compose,
    _LiveRuntimeFacts,
    _reach_trusted,
)
from .test_marketfeed_intake_kind_wiring import _write_kis_quote_transport_config
from .test_transport_wiring import _activate_mock_stock_order, _build_custody

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_ROOT = _REPO_ROOT / "config" / "tos_runtime"

_SHIPPED_TREES = ("paper", "cp3-setup-d-long", "cp3-setup-d-short")

_TREES_WITH_NO_BAND_SOURCE = ("paper", "cp3-setup-d-short")

_TREE_WITH_A_BAND_SOURCE = "cp3-setup-d-long"

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
    """The REAL_PROD INSTANCE document's own ``rest_base``, read from the document rather than"""
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


def _declare_band_source(config_dir: Path, **overrides: Any) -> None:
    """Rewrite the compose fixture's venue policy so it DECLARES a band source."""
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


def _declare_producer_journal_band_source(
    config_dir: Path, *, band_journal_path: Path
) -> None:
    """The LONG tenant tree's own ``kind`` (``producer_journal``), declared on the compose"""
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
    loaded = load_venue_constraint_policy(
        config_dir / "venue_constraint_policy.yaml", scheme=_SCHEME
    )
    del loaded


def _tree_runtime_block(tree: str) -> dict[str, Any]:
    raw = yaml.safe_load(
        (_CONFIG_ROOT / tree / "venue_constraint_policy.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert isinstance(raw["_runtime"], dict)
    return raw["_runtime"]


class TestShippedTreesDeclareNoBandSource:
    """Band plan §5 / §8 1 — the trees that keep the source OFF, read off the real files."""

    @pytest.mark.parametrize("tree", _TREES_WITH_NO_BAND_SOURCE)
    def test_the_runtime_block_carries_neither_key(self, tree: str) -> None:
        runtime = _tree_runtime_block(tree)

        assert "band_source" not in runtime
        assert "price_scale" not in runtime

    def test_the_real_resident_policy_loads_with_no_band_source_and_no_price_scale(
        self, tmp_path: Path
    ) -> None:
        """The resident file, operator-filled exactly as ``test_deploy_policies.py`` fills it,"""
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
        assert loaded.policy.shape_constraints.price_min is None
        assert loaded.policy.shape_constraints.price_max is None

    @pytest.mark.parametrize("tree", _SHIPPED_TREES)
    def test_no_tree_carries_a_kis_quote_document_today(self, tree: str) -> None:
        """Reading an ABSENT transport document answers ``None`` rather than raising — which"""
        assert read_declared_instrument(_CONFIG_ROOT / tree / "kis_quote.yaml") is None


class TestTheLongTenantTreeDeclaresTheProducerJournal:
    """2026-10-15 plan §4 "켜는 배포: LONG tenant 만" — the one tree that is ON, read off the"""

    def test_the_runtime_block_declares_the_producer_journal_kind(self) -> None:
        runtime = _tree_runtime_block(_TREE_WITH_A_BAND_SOURCE)

        assert runtime["price_scale"] == 100
        band_source = runtime["band_source"]
        assert band_source["kind"] == "producer_journal"
        assert band_source["price_scale"] == 100
        assert band_source["bound"] == "trading_date_kst"
        assert band_source["read_on"] == ["boot", "phase_change"]
        assert band_source["failure"] == "unknown"
        assert band_source["instrument"] == "TBD"
        assert band_source["band_journal_path"] == "TBD"
        assert band_source["approved_source_prefixes"] == ["TBD"]

    def test_it_declares_no_leaf_of_the_other_kind(self) -> None:
        """The loader refuses one (``_refuse_keys_of_the_other_kind``); this says the shipped"""
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
        """The REAL file, coordinate slots filled the way the renderer fills them, through the"""
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
        assert loaded.policy.shape_constraints.price_min is None
        assert loaded.policy.shape_constraints.price_max is None
        assert loaded.policy.shape_constraints.tick_size == 2


class TestTodaysRowsAreUnchanged:
    """Plan §8 1 — a full compose boot plus one real attempt writes the same payloads it"""

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
        """``build_venue_service`` builds a reader ONLY when the policy declares a source"""
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        try:
            assert runtime.venue._band_reader is None  # noqa: SLF001
            assert runtime.venue._trading_date_reader is None  # noqa: SLF001
            assert runtime.venue._band_source_declared is False  # noqa: SLF001
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()


class TestStepThreeAndItemElevenReadOneObject:
    """Plan §8 2 — the venue stage (step 3's folds) and the send-boundary context (item 11)"""

    def test_the_stage_serves_the_services_own_effective_constraints_object(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        try:
            assert (
                runtime.venue_stage.shape_constraints is runtime.venue.shape_constraints
            )
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
        """The fixture setup a ``kis_quote``-document boot needs: the MOCK_STOCK_ORDER scope"""
        _activate_mock_stock_order(config_dir)
        fx.write_kis_mock_transport_config(config_dir)
        _build_custody(custody_root)

    def test_a_phase_change_only_kis_source_boots_and_reads_nothing_at_boot(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """Plan §6 (A): the band GET is the paper runtime's FIRST external call. A"""
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
        """Plan §8 7. The refusal comes from"""
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
        """Re-review LOW-2. ``KisCredentialSessions.session_for`` CREATES the one app-key"""
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
            transport = runtime.transport
            session = transport._credential_session  # noqa: SLF001
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
        """Independent review M1. One app key gets one token lifecycle (C-2 decision (C)), so"""
        self._kis_mock_boot(config_dir, custody_root)
        _write_kis_quote_transport_config(
            config_dir,
            instrument=_VENUE_POLICY_INSTRUMENT,
            token_reissue_min_interval_s=61,
        )
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
        """Rescope plan M1 — the one input that reaches :class:`VenueBandSourceUnwired`."""
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
        """Independent review L1. ``build_venue_service`` hands the loader a THUNK, which the"""
        self._kis_mock_boot(config_dir, custody_root)
        _write_kis_quote_transport_config(
            config_dir, instrument="TBD", token_path="TBD"
        )
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
        """Plan §4.1's "transport 설정 부재" refusal, reached through the real compose root —"""
        self._kis_mock_boot(config_dir, custody_root)
        assert not (config_dir / "kis_quote.yaml").exists()
        _declare_band_source(config_dir)

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
    """Rescope plan M1 (``docs/plans/2026-10-22-tos-rescope-plan.md``) — the band is"""

    _TRADING_DATE = datetime.fromtimestamp(
        fx.DEFAULT_WALL_CLOCK_UNIX_MS / 1000, tz=timezone(timedelta(hours=9))
    ).strftime("%Y%m%d")

    def _band_line(self, **overrides: Any) -> dict[str, Any]:
        """One ``cp3-band/1`` line carrying the P-VL ``A05610`` measurement (987.46/1159.18"""
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
            assert _payloads(runtime, "VENUE_SNAPSHOT_ISSUED") == []
            assert runtime.venue.shape_constraints.price_max == 115_918
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()

    def test_an_absent_journal_lands_one_refused_row_naming_the_reason(
        self, tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """The other half of the operator's acceptance: ``REFUSED`` with a reason, not"""
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
        """**The measured day, reproduced.** Driving a real event against this policy halts"""
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
        """One instant, one row, on the REAL composed service. ``snapshot()`` is called"""
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
    """The boot read against the clock reference PRODUCTION wires, not the suite's fixed one."""

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
        line = TestTheProducerJournalKindReadsAtBoot()._band_line(
            trading_date=trading_date
        )
        journal.write_bytes(json.dumps(line).encode("utf-8") + b"\n")
        _declare_producer_journal_band_source(config_dir, band_journal_path=journal)
        fx.write_band_strategy_file(config_dir)
        facts = _LiveRuntimeFacts()
        runtime = compose_paper_runtime(
            config_dir,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=_aggregate_inputs,
            action_flow_inputs_provider=_action_flow_inputs_for(facts),
            transport_kind=TransportKind.SYNTHETIC,
        )
        facts.runtime = runtime
        return runtime

    def test_the_boot_read_reaches_the_production_fresh_trusted_reference(
        self,
        tmp_path: Path,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A fresh production clock dates the boot read, so the band is in force before"""
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

            assert row["outcome"] == "OBSERVED"
            assert row["trading_date"] == trading_date
            assert (row["price_min"], row["price_max"]) == (98_746, 115_918)
            assert _payloads(runtime, "VENUE_SNAPSHOT_ISSUED") == []
            assert runtime.venue.shape_constraints.price_max == 115_918
        finally:
            runtime.rcl_log.close()
            runtime.evidence_store.close()
