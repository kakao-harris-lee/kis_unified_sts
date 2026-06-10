"""Contract-spec registry for Korean index futures."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ContractSpec:
    name: str
    multiplier_krw_per_point: int
    tick_size_points: float
    tick_value_krw: int
    commission_rate: float
    symbol_prefix: str


@dataclass
class ContractSpecRegistry:
    specs: dict[str, ContractSpec] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> ContractSpecRegistry:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        raw = data.get("futures_contract_spec", {})
        return cls(
            specs={
                name: ContractSpec(name=name, **fields) for name, fields in raw.items()
            }
        )


def resolve_contract_spec(symbol: str, registry: ContractSpecRegistry) -> ContractSpec:
    for spec in registry.specs.values():
        # symbol_prefix may list several comma-separated prefixes — e.g. the full
        # KOSPI200 future is the continuous "101…" code (backtest) AND the live
        # "A01…" front-month. str.startswith accepts a tuple of prefixes.
        prefixes = tuple(p.strip() for p in spec.symbol_prefix.split(",") if p.strip())
        if symbol.startswith(prefixes):
            return spec
    raise ValueError(f"no contract spec for symbol={symbol}")
