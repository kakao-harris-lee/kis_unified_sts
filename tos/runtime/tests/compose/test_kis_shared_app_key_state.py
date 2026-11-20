"""A kis-mock boot takes its app key's shared token and shared queue from its own config.

The unit tests prove the cache and the gate behave; this proves the two config pairs
actually reach a composed runtime, and that every consumer of this app key takes the same
session — which is why the fill witness and the loop witness (built in
``_broker_posttrade_wiring``) cannot open a second token lifecycle of their own (#1125).
"""

from __future__ import annotations

from pathlib import Path

from tos_runtime.compose._transport_wiring import TransportKind

from . import _fixtures as fx
from .test_compose_root import _compose
from .test_transport_wiring import _activate_mock_stock_order, _build_custody


def _boot(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    *,
    shared_dir: Path | None,
):
    _activate_mock_stock_order(config_dir)
    fx.write_kis_mock_transport_config(config_dir, shared_app_key_state_dir=shared_dir)
    _build_custody(custody_root)
    return _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        transport_kind=TransportKind.KIS_MOCK,
    )


def test_a_boot_without_the_keys_shares_nothing(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root, shared_dir=None)
    try:
        sessions = runtime.kis_credential_sessions
        assert sessions is not None
        assert sessions._token_cache is None  # noqa: SLF001
        assert sessions._shared_gate is None  # noqa: SLF001
    finally:
        runtime.rcl_log.close()
        runtime.evidence_store.close()


def test_the_configured_files_reach_the_order_transports_own_session(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    shared_dir = tmp_path / "kis-mock-token"
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root, shared_dir=shared_dir)
    try:
        sessions = runtime.kis_credential_sessions
        assert sessions is not None
        cache = sessions._token_cache  # noqa: SLF001
        gate = sessions._shared_gate  # noqa: SLF001
        assert cache is not None and gate is not None
        assert cache.path == shared_dir / "stock-mock.json"
        assert gate.path == shared_dir / "stock-mock.pace"

        session = runtime.transport._credential_session  # noqa: SLF001
        assert session._lifecycle._cache is cache  # noqa: SLF001
        assert session._pacer._shared_gate is gate  # noqa: SLF001
    finally:
        runtime.rcl_log.close()
        runtime.evidence_store.close()
