"""``tos_runtime.backtest`` — the runtime half of the paper/backtest calibration gate
(Phase 3 wave 3 §3.1 slice E, runtime half; plan §3.1/§5).

Pairs a paper ``EGRESS_RESULT_CONSUMED`` evidence row against a backtest
:class:`~tos.backtest.records.LocalFillRecord` for the same attempt, and reports the deviation
through the kernel's pure calibration gate (:mod:`tos.backtest.calibration`, imported by
submodule path). See :mod:`tos_runtime.backtest.calibration_report` for the full docstring —
including the pairing-key limitation and the always-``None`` ``price_bps``/``latency_bars``
dimensions this runtime slice produces.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): re-exports only; no imports of its
own beyond the two submodules.
"""

from __future__ import annotations

from tos_runtime.backtest.calibration_report import (
    CalibrationReport,
    build_calibration_report,
    read_egress_result_consumed_records,
)
from tos_runtime.backtest.config import (
    BACKTEST_CALIBRATION_CONFIG_FILENAME,
    BacktestCalibrationConfigError,
    load_backtest_calibration_config,
)

__all__ = [
    "BACKTEST_CALIBRATION_CONFIG_FILENAME",
    "BacktestCalibrationConfigError",
    "CalibrationReport",
    "build_calibration_report",
    "load_backtest_calibration_config",
    "read_egress_result_consumed_records",
]
