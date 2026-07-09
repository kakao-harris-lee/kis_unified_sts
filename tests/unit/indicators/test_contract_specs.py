"""IndicatorContract.from_specs — typed builder-style requirements (P2-b).

Additive API: a strategy can declare ``IndicatorSpec`` requests (indicator id
+ params) and get back a contract whose required keys come from the shared
``flat_key`` catalog — no magic strings. Legacy string contracts must behave
exactly as before.
"""

from __future__ import annotations

from shared.indicators.contracts import IndicatorContract, IndicatorKind
from shared.indicators.engine.spec import IndicatorSpec
from shared.indicators.resolver import StreamingIndicatorResolver


class _FakeEngine:
    """Minimal engine double for resolver payload assembly."""

    def __init__(self, base: dict[str, float]) -> None:
        self._base = base

    def get_indicators(self, symbol: str) -> dict[str, float]:
        return dict(self._base)


def test_single_output_spec_maps_to_bare_flat_key() -> None:
    contract = IndicatorContract.from_specs(
        [IndicatorSpec.create("rsi", {"period": 14})]
    )
    assert contract.required_keys == ("rsi",)
    (request,) = contract.requests
    assert request.kind == IndicatorKind.BASE
    assert request.spec == IndicatorSpec.create("rsi", {"period": 14})
    assert request.source_key == "5m:rsi(period=14)"


def test_multi_output_spec_pair_maps_through_flat_key_overrides() -> None:
    bollinger = IndicatorSpec.create("bollinger", {"period": 20, "std": 2})
    contract = IndicatorContract.from_specs(
        [(bollinger, "upper"), (bollinger, "lower")]
    )
    assert contract.required_keys == ("bb_upper", "bb_lower")


def test_period_keyed_spec_embeds_period_in_key() -> None:
    contract = IndicatorContract.from_specs(
        [IndicatorSpec.create("ema", {"period": 20})]
    )
    assert contract.required_keys == ("ema_20",)


def test_extra_keys_go_through_legacy_string_parsing() -> None:
    contract = IndicatorContract.from_specs(
        [IndicatorSpec.create("rsi", {"period": 14})],
        extra_keys=["ohlcv", "momentum_5m", "mtf_base_15m"],
    )
    assert contract.required_keys == ("rsi", "ohlcv", "momentum_5m", "mtf_base_15m")
    assert contract.needs_ohlcv
    assert len(contract.momentum_requests) == 1
    assert len(contract.mtf_base_requests) == 1
    # Only the typed request carries a spec.
    typed = [req for req in contract.requests if req.spec is not None]
    assert len(typed) == 1
    assert typed[0].name == "rsi"


def test_legacy_string_contract_is_unchanged() -> None:
    contract = IndicatorContract.from_required_keys(["rsi", "bb_upper", "ohlcv"])
    assert contract.required_keys == ("rsi", "bb_upper", "ohlcv")
    assert all(req.spec is None for req in contract.requests)


def test_resolver_fulfils_spec_derived_keys_as_base_payload() -> None:
    """A specs-built contract needs zero resolver changes: its flat keys are
    the very names the live base payload publishes."""
    contract = IndicatorContract.from_specs(
        [
            IndicatorSpec.create("rsi", {"period": 14}),
            (IndicatorSpec.create("bollinger", {"period": 20, "std": 2}), "upper"),
        ]
    )
    engine = _FakeEngine({"rsi": 47.1, "bb_upper": 71000.0, "bb_lower": 69000.0})
    resolver = StreamingIndicatorResolver(
        engine=engine, required_keys=list(contract.required_keys)
    )
    payload = resolver.collect_entry_indicators("005930")
    assert payload["rsi"] == 47.1
    assert payload["bb_upper"] == 71000.0
