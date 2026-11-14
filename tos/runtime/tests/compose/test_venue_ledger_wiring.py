"""The venue ledger's compose wiring: one config key, one transport kind (#1011 P2)."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
import yaml
from tos_runtime.compose._transport_wiring import (
    TransportKind,
    TransportWiringError,
    build_transport,
)
from tos_runtime.compose._venue_ledger_wiring import (
    FINALITY_CONFIG_NAME,
    VenueLedgerWiringError,
    build_synthetic_venue_ledger,
)
from tos_runtime.posttrade.config import FinalityConfigError
from tos_runtime.recon.ports import WitnessScope
from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness
from tos_runtime.recon.witness_synthetic_venue import (
    SYNTHETIC_VENUE_LEDGER_PROVENANCE,
    SyntheticVenueLedgerWitness,
)
from tos_runtime.venue import VenuePolicyConfigError
from tos_runtime.venue_ledger.synthetic import (
    VENUE_LEDGER_FILE_NAME,
    SyntheticVenueLedger,
)

from . import _fixtures as fx
from .test_compose_root import _compose

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_WITNESS_ON = {"witness": "synthetic_venue_ledger"}


def turn_the_venue_ledger_on(config_dir: Path) -> Path:
    """Write ``witness: synthetic_venue_ledger`` into this tree's ``finality.yaml``."""
    path = config_dir / FINALITY_CONFIG_NAME
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw.update(_WITNESS_ON)
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


def _ledger_path(data_dir: Path) -> Path:
    return data_dir / VENUE_LEDGER_FILE_NAME


def test_without_the_key_the_boot_has_no_ledger_and_the_old_witness(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """No key ⇒ no ledger file, no venue witness, and the store-derived one still wired."""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    try:
        assert runtime.venue_ledger.enabled is False
        assert runtime.venue_ledger.witness is None
        assert not _ledger_path(data_dir).exists()
        assert runtime.broker_witness_provenance == "synthetic-ledger"
        assert isinstance(
            runtime.driver._release_consumer.recon_service._witness,  # noqa: SLF001
            SyntheticLedgerWitness,
        )
    finally:
        runtime.rcl_log.close()
        runtime.evidence_store.close()


def test_the_key_on_wires_the_venue_witness_everywhere_the_old_one_was(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
) -> None:
    """One key ⇒ the recording transport, the ledger file at 0600, and the venue witness."""
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    runtime = _compose(tmp_path, config_dir_with_risk_state, data_dir, custody_root)
    try:
        assert runtime.venue_ledger.enabled is True
        assert isinstance(runtime.venue_ledger.witness, SyntheticVenueLedgerWitness)
        assert runtime.broker_witness_provenance == (SYNTHETIC_VENUE_LEDGER_PROVENANCE)

        path = _ledger_path(data_dir)
        assert path.is_file()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

        witness = (
            runtime.driver._release_consumer.recon_service._witness
        )  # noqa: SLF001
        assert isinstance(witness, SyntheticVenueLedgerWitness)
        assert witness is runtime.venue_ledger.witness

        assert type(runtime.transport).__name__ == "RecordingSyntheticTransport"
    finally:
        runtime.venue_ledger.close()
        runtime.rcl_log.close()
        runtime.evidence_store.close()


def test_the_venue_witness_declares_itself_independent_of_the_evidence_store(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
) -> None:
    """The one field the whole release path turns on, read off the COMPOSED witness."""
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    runtime = _compose(tmp_path, config_dir_with_risk_state, data_dir, custody_root)
    try:
        witness = runtime.venue_ledger.witness
        assert witness is not None
        instrument_key = runtime.context_resolver.instrument_key
        snapshot = witness.observe(
            WitnessScope(
                account=instrument_key.account, instrument_keys=(instrument_key,)
            )
        )
        assert snapshot.independent_of_evidence_store is True
        assert snapshot.provenance == SYNTHETIC_VENUE_LEDGER_PROVENANCE
        assert (snapshot.orders, snapshot.positions) == ((), ())
        assert snapshot.positions_complete is True
    finally:
        runtime.venue_ledger.close()
        runtime.rcl_log.close()
        runtime.evidence_store.close()


def test_the_key_on_with_a_kis_mock_transport_refuses_the_boot(
    config_dir_with_risk_state: Path, data_dir: Path
) -> None:
    """The ledger is the SYNTHETIC venue's own record — a broker-reaching boot must not hold it."""
    turn_the_venue_ledger_on(config_dir_with_risk_state)

    with pytest.raises(VenueLedgerWiringError, match="kis-mock"):
        build_synthetic_venue_ledger(
            config_dir=config_dir_with_risk_state,
            data_dir=data_dir,
            transport_kind=TransportKind.KIS_MOCK,
            scheme=fx.SCHEME,
            trading_date_now=lambda: "20261031",
        )

    assert not _ledger_path(data_dir).exists()


def test_build_transport_also_refuses_to_wrap_a_broker_reaching_transport(
    tmp_path: Path,
) -> None:
    """The same refusal restated where the wrapping would happen (defence in depth)."""
    ledger = SyntheticVenueLedger(tmp_path / VENUE_LEDGER_FILE_NAME)
    try:
        with pytest.raises(TransportWiringError, match="SYNTHETIC venue's own record"):
            build_transport(
                TransportKind.KIS_MOCK,
                transport_config=None,
                custody=None,  # type: ignore[arg-type]
                monotonic=None,  # type: ignore[arg-type]
                seal_lookup=None,  # type: ignore[arg-type]
                evidence_store=None,  # type: ignore[arg-type]
                runtime_identity=None,  # type: ignore[arg-type]
                credential_sessions=None,  # type: ignore[arg-type]
                venue_ledger=ledger,
            )
    finally:
        ledger.close()


def test_a_venue_ledger_without_a_trusted_trading_date_refuses_the_boot(
    tmp_path: Path,
) -> None:
    """A ledger with no date source is refused, not silently written undated."""
    ledger = SyntheticVenueLedger(tmp_path / VENUE_LEDGER_FILE_NAME)
    try:
        with pytest.raises(TransportWiringError, match="trading-date"):
            build_transport(
                TransportKind.SYNTHETIC,
                transport_config=None,
                custody=None,  # type: ignore[arg-type]
                monotonic=None,  # type: ignore[arg-type]
                seal_lookup=None,  # type: ignore[arg-type]
                evidence_store=None,  # type: ignore[arg-type]
                runtime_identity=None,  # type: ignore[arg-type]
                credential_sessions=None,  # type: ignore[arg-type]
                venue_ledger=ledger,
                trading_date_now=None,
            )
    finally:
        ledger.close()


def test_the_key_on_without_the_governed_side_tokens_refuses_the_boot(
    config_dir: Path, data_dir: Path
) -> None:
    """A witness that cannot sign a fill cannot net a position — so it is not built at all."""
    turn_the_venue_ledger_on(config_dir)
    assert not (config_dir / "action_flow_policy.yaml").exists()

    with pytest.raises(VenuePolicyConfigError):
        build_synthetic_venue_ledger(
            config_dir=config_dir,
            data_dir=data_dir,
            transport_kind=TransportKind.SYNTHETIC,
            scheme=fx.SCHEME,
            trading_date_now=lambda: "20261031",
        )

    assert not _ledger_path(data_dir).exists()


def test_a_misspelled_witness_key_refuses_the_boot(
    config_dir: Path, data_dir: Path
) -> None:
    """``witness: synthetic-venue-ledger`` (hyphens) is refused, never read as "absent"."""
    path = config_dir / FINALITY_CONFIG_NAME
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["witness"] = "synthetic-venue-ledger"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(FinalityConfigError, match="witness"):
        build_synthetic_venue_ledger(
            config_dir=config_dir,
            data_dir=data_dir,
            transport_kind=TransportKind.SYNTHETIC,
            scheme=fx.SCHEME,
            trading_date_now=lambda: "20261031",
        )

    assert not _ledger_path(data_dir).exists()


@pytest.mark.parametrize(
    "tree",
    ["paper", "cp3-setup-d-long", "cp3-setup-d-short", "cp3-setup-d-stock-005930"],
)
def test_no_shipped_tree_carries_the_witness_key(tree: str) -> None:
    """The deploy guard for this PR."""
    path = (
        Path(__file__).resolve().parents[4]
        / "config"
        / "tos_runtime"
        / tree
        / FINALITY_CONFIG_NAME
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "witness" not in raw, (
        f"{tree}/{FINALITY_CONFIG_NAME} carries the venue-ledger key — the switch-on day is "
        "the operator's, in its own PR (plan §4 P2)"
    )
