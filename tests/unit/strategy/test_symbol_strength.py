from shared.strategy.symbol_strength import (
    StrengthCriteria, compute_strong_symbols, is_strong,
)

_STRONG = {  # SK하이닉스-like
    "daily_close": 100.0, "daily_sma_20": 90.0,
    "daily_rsi_14": 74.0, "daily_prev_rsi_14": 70.0, "daily_macd_hist": 120.0,
}

def test_all_conditions_met_is_strong():
    assert is_strong(_STRONG, StrengthCriteria()) is True

def test_below_sma20_not_strong():
    assert is_strong({**_STRONG, "daily_close": 80.0}, StrengthCriteria()) is False

def test_rsi_below_min_not_strong():
    assert is_strong({**_STRONG, "daily_rsi_14": 50.0}, StrengthCriteria()) is False

def test_rsi_not_rising_not_strong():
    assert is_strong({**_STRONG, "daily_rsi_14": 60.0, "daily_prev_rsi_14": 65.0}, StrengthCriteria()) is False

def test_macd_not_positive_not_strong():
    assert is_strong({**_STRONG, "daily_macd_hist": -1.0}, StrengthCriteria()) is False

def test_missing_field_not_strong():
    assert is_strong({"daily_close": 100.0}, StrengthCriteria()) is False

def test_nan_field_not_strong():
    assert is_strong({**_STRONG, "daily_rsi_14": float("nan")}, StrengthCriteria()) is False

def test_compute_strong_symbols_filters():
    weak = {**_STRONG, "daily_close": 80.0}
    out = compute_strong_symbols({"AAA": _STRONG, "BBB": weak}, StrengthCriteria())
    assert out == {"AAA"}

def test_criteria_toggles_relax():
    # disabling RSI-rising lets a non-rising-but-otherwise-strong symbol pass
    c = StrengthCriteria(require_rsi_rising=False)
    s = {**_STRONG, "daily_rsi_14": 60.0, "daily_prev_rsi_14": 65.0}
    assert is_strong(s, c) is True
