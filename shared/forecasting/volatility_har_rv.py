"""HAR-RV (Heterogeneous Autoregressive on Realized Volatility), Corsi (2009).

Daily-level model with 1-day / 1-week / 1-month aggregates of past RV:

    RV_t = β_0 + β_d * RV_{t-1}
              + β_w * mean(RV_{t-1..t-5})
              + β_m * mean(RV_{t-1..t-22}) + ε
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import statsmodels.api as sm

from shared.forecasting.config import HARRVConfig
from shared.forecasting.models import VolForecast

logger = logging.getLogger(__name__)


@dataclass
class HARRVCoefficients:
    beta_0: float
    beta_d: float
    beta_w: float
    beta_m: float
    r2_in_sample: float
    r2_oos: float
    n_obs_used: int
    fit_date: str  # ISO date


def _build_har_regressors(rv: pd.Series) -> pd.DataFrame:
    """Construct daily/weekly/monthly RV regressors aligned with target."""
    df = pd.DataFrame({"rv": rv})
    df["rv_d"] = df["rv"].shift(1)  # t-1
    df["rv_w"] = df["rv"].shift(1).rolling(5).mean()  # mean(t-1..t-5)
    df["rv_m"] = df["rv"].shift(1).rolling(22).mean()  # mean(t-1..t-22)
    return df.dropna()


class VolatilityForecaster:
    """HAR-RV model — daily refit, multi-frequency RV regressors."""

    MODEL_VERSION = "har_rv_v1"

    def __init__(self, config: HARRVConfig):
        self.config = config
        self._coefficients: HARRVCoefficients | None = None
        self._last_fit_at: datetime | None = None
        self._rv_history: pd.Series | None = None
        self._latest_components: tuple[float, float, float] | None = (
            None  # (rv_d, rv_w, rv_m)
        )

    def fit(self, history: pd.Series) -> None:
        """Refit OLS on daily RV series.

        Args:
            history: indexed by date, values = daily realized variance.

        Raises:
            ValueError on insufficient data or OOS R² below threshold.
        """
        if len(history) < max(self.config.history_days, 22):
            raise ValueError(
                f"insufficient history: need >= {max(self.config.history_days, 22)} "
                f"days, got {len(history)}"
            )

        df = _build_har_regressors(history)
        holdout = self.config.holdout_days
        if len(df) <= holdout:
            raise ValueError(
                f"insufficient post-regressor rows for hold-out (have {len(df)}, "
                f"holdout {holdout})"
            )

        train = df.iloc[:-holdout]
        test = df.iloc[-holdout:]

        X_train = sm.add_constant(train[["rv_d", "rv_w", "rv_m"]])
        y_train = train["rv"]
        model = sm.OLS(y_train, X_train).fit()

        # OOS predictions
        X_test = sm.add_constant(test[["rv_d", "rv_w", "rv_m"]])
        y_test = test["rv"]
        y_pred = model.predict(X_test)
        ss_res = float(((y_test - y_pred) ** 2).sum())
        ss_tot = float(((y_test - y_test.mean()) ** 2).sum())
        r2_oos = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

        if not np.isfinite(r2_oos) or r2_oos < self.config.min_r2_oos:
            raise ValueError(
                f"R² OOS below threshold: {r2_oos:.3f} < {self.config.min_r2_oos:.3f}"
            )

        params = model.params
        self._coefficients = HARRVCoefficients(
            beta_0=float(params.iloc[0]),
            beta_d=float(params.iloc[1]),
            beta_w=float(params.iloc[2]),
            beta_m=float(params.iloc[3]),
            r2_in_sample=float(model.rsquared),
            r2_oos=float(r2_oos),
            n_obs_used=int(len(train)),
            fit_date=datetime.now(UTC).date().isoformat(),
        )
        self._last_fit_at = datetime.now(UTC)
        self._rv_history = history.copy()
        # Latest components for prediction
        last_d = float(history.iloc[-1])
        last_w = float(history.iloc[-5:].mean()) if len(history) >= 5 else last_d
        last_m = float(history.iloc[-22:].mean()) if len(history) >= 22 else last_w
        self._latest_components = (last_d, last_w, last_m)
        logger.info(
            "HAR-RV refit complete: beta_d=%.3f beta_w=%.3f beta_m=%.3f R2_oos=%.3f",
            self._coefficients.beta_d,
            self._coefficients.beta_w,
            self._coefficients.beta_m,
            self._coefficients.r2_oos,
        )

    def forecast(self, asof: datetime, current_close: float) -> VolForecast:
        """Predict next-15-min volatility.

        forecast_pct = sqrt(predicted_RV * 252) * 100  (annualized %)
        forecast_atr_equivalent = forecast_pct * close * sqrt(15/(252*390)) / 100
        """
        if self._coefficients is None or self._latest_components is None:
            raise RuntimeError("VolatilityForecaster.forecast called before fit()")

        rv_d, rv_w, rv_m = self._latest_components
        c = self._coefficients
        pred_rv = c.beta_0 + c.beta_d * rv_d + c.beta_w * rv_w + c.beta_m * rv_m
        pred_rv = max(pred_rv, 1e-10)
        # Annualized % vol = sqrt(daily variance * 252) * 100
        forecast_pct = float(np.sqrt(pred_rv * 252) * 100)
        # 15-min ATR-equivalent
        forecast_atr_equivalent = float(
            forecast_pct * current_close * np.sqrt(15 / (252 * 390)) / 100
        )
        # Regime percentile against historical RV distribution
        if self._rv_history is not None and len(self._rv_history) > 0:
            percentile = float((self._rv_history < pred_rv).mean() * 100)
        else:
            percentile = 50.0
        return VolForecast(
            asof=asof,
            horizon_minutes=15,
            forecast_pct=forecast_pct,
            forecast_atr_equivalent=forecast_atr_equivalent,
            regime_percentile=percentile,
            model_version=self.MODEL_VERSION,
            confidence=float(c.r2_oos),
        )

    def is_fit_stale(self, now: datetime) -> bool:
        if self._last_fit_at is None:
            return True
        return (now - self._last_fit_at) > timedelta(days=1, hours=12)

    def to_json(self) -> str:
        if self._coefficients is None or self._latest_components is None:
            raise RuntimeError("cannot serialize before fit()")
        payload = {
            "coefficients": asdict(self._coefficients),
            "latest_components": list(self._latest_components),
            "last_fit_at": (
                self._last_fit_at.isoformat() if self._last_fit_at else None
            ),
        }
        if self._rv_history is not None and len(self._rv_history) > 0:
            payload["rv_history"] = self._rv_history.astype(float).tolist()
        return json.dumps(payload)

    @classmethod
    def from_json(cls, blob: str | bytes, cfg: HARRVConfig) -> VolatilityForecaster:
        if isinstance(blob, bytes):
            blob = blob.decode()
        d = json.loads(blob)
        f = cls(cfg)
        f._coefficients = HARRVCoefficients(**d["coefficients"])
        f._latest_components = tuple(d["latest_components"])
        f._last_fit_at = (
            datetime.fromisoformat(d["last_fit_at"]) if d.get("last_fit_at") else None
        )
        if "rv_history" in d:
            f._rv_history = pd.Series(d["rv_history"], dtype=float, name="rv")
        return f
