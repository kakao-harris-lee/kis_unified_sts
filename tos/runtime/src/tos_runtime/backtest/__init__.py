"""``tos_runtime.backtest`` — the runtime half of the paper/backtest calibration gate"""

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
