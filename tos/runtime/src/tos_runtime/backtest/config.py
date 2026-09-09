"""``tos_runtime.backtest.config`` — the paper/backtest calibration-budget config loader
(Phase 3 wave 3 §3.1 slice E, runtime half; plan §3.1).

Loads ``config_dir/backtest_calibration.yaml`` (or an operator-approved copy shaped like
``tos/runtime/config/backtest_calibration.example.yaml``) into the kernel's
:class:`~tos.backtest.calibration.DeviationBudget` — the injected tolerance
:func:`~tos.backtest.calibration.calibration_within_budget` measures a set of
:class:`~tos.backtest.calibration.FillDeviation` observations against
(:mod:`tos_runtime.backtest.calibration_report` produces those observations).

Every value in the file is an OPERATOR-APPROVED policy value, never computed here — mirroring
every other runtime config loader's own "null = named-TBD ⇒ refuse to start" discipline
(:mod:`tos_runtime.posttrade.config`, :mod:`tos_runtime.release.config`). Two fail-closed layers,
per the assigning brief:

* ``extra="forbid"`` on the intake model — an unknown key is refused, never silently ignored.
* Every leaf defaults to ``None`` on intake so a ``null``/missing value can be refused BY NAME
  (which key is unfilled), rather than merely "the file was invalid somehow".

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``pydantic`` + ``pyyaml``
(``yaml``) + ``tos.backtest.calibration`` only.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError
from tos.backtest.calibration import DeviationBudget

__all__ = [
    "BACKTEST_CALIBRATION_CONFIG_FILENAME",
    "BacktestCalibrationConfigError",
    "load_backtest_calibration_config",
]

#: The one place this filename is spelled — every caller (compose root, docs, tests) imports
#: this constant rather than repeating the literal.
BACKTEST_CALIBRATION_CONFIG_FILENAME = "backtest_calibration.yaml"


class BacktestCalibrationConfigError(Exception):
    """Raised when the calibration-budget config is missing, malformed, carries an unfilled
    (named-TBD) required key, or an unknown key — fail-closed at load."""


class _RawDeviationBudget(BaseModel):
    """Permissive intake shape: every leaf optional so a ``null``/absent value can be refused
    BY NAME below, and ``extra="forbid"`` so an unrecognized key is refused rather than
    silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    max_price_bps: Decimal | None = None
    max_fill_ratio_shortfall: Decimal | None = None
    max_latency_bars: int | None = None
    min_observations: int | None = None


def _load_mapping(path: Path) -> dict[str, Any]:
    """Read + YAML-parse ``path`` into a top-level mapping, fail-closed."""
    if not path.is_file():
        raise BacktestCalibrationConfigError(
            f"backtest calibration config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BacktestCalibrationConfigError(
            f"backtest calibration config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise BacktestCalibrationConfigError(
            f"backtest calibration config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise BacktestCalibrationConfigError(
            "backtest calibration config file must be a top-level mapping: "
            f"{path} (got {type(raw)!r})"
        )
    return raw


def _parse_raw(raw: dict[str, Any], *, path: Path) -> _RawDeviationBudget:
    """Validate ``raw`` against the permissive intake shape, refusing an unknown key."""
    try:
        return _RawDeviationBudget.model_validate(raw)
    except ValidationError as exc:
        raise BacktestCalibrationConfigError(
            f"backtest calibration config has an unknown or malformed key: {path} ({exc})"
        ) from exc


def _require_decimal(parsed: _RawDeviationBudget, field_name: str) -> Decimal:
    value = getattr(parsed, field_name)
    if value is None:
        raise BacktestCalibrationConfigError(
            "backtest calibration config has an unfilled (named-TBD) key — fail-closed at "
            f"startup until an operator fills it: {field_name!r}"
        )
    assert isinstance(value, Decimal)
    return value


def _require_int(parsed: _RawDeviationBudget, field_name: str) -> int:
    value = getattr(parsed, field_name)
    if value is None:
        raise BacktestCalibrationConfigError(
            "backtest calibration config has an unfilled (named-TBD) key — fail-closed at "
            f"startup until an operator fills it: {field_name!r}"
        )
    assert isinstance(value, int)
    return value


def load_backtest_calibration_config(path: Path) -> DeviationBudget:
    """Load + validate ``path`` into a fully-valued :class:`DeviationBudget`, fail-closed.

    Args:
        path: Path to a YAML file shaped like
            ``tos/runtime/config/backtest_calibration.example.yaml``.

    Returns:
        A fully-valued :class:`~tos.backtest.calibration.DeviationBudget`.

    Raises:
        BacktestCalibrationConfigError: The file is missing/unreadable/not valid YAML/not a
            mapping, carries an unrecognized key, or a required key is missing or still
            ``null`` (named-TBD).
    """
    raw = _load_mapping(path)
    parsed = _parse_raw(raw, path=path)
    return DeviationBudget(
        max_price_bps=_require_decimal(parsed, "max_price_bps"),
        max_fill_ratio_shortfall=_require_decimal(parsed, "max_fill_ratio_shortfall"),
        max_latency_bars=_require_int(parsed, "max_latency_bars"),
        min_observations=_require_int(parsed, "min_observations"),
    )
