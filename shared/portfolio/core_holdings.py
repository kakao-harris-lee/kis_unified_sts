"""Track A core-holdings manual ledger loader (Phase 5A).

Loads ``config/portfolio/core_holdings.yaml`` — the operator-maintained manual
ledger for the Track A core portfolio (design doc §2: 35/35/15/15 sector
frame, inclusion rules, Kill Criteria). This is the FIXED contract consumed
by the 5E UI lane (``GET /api/portfolio/core``) and the 5B stock-filter lane
(:meth:`CoreHoldings.symbols` / :meth:`CoreHoldings.sector_of`).

Track A is a MANUAL track: nothing in this module (or its consumers) places
orders. The loader reads, validates, and values — recording happens through
``sts portfolio`` CLI commands and display through the dashboard.

Valuations sidecar
------------------

``sts portfolio value`` never rewrites the operator-authored YAML (rewriting
would destroy its comments — the schema documentation and per-holding thesis
context live there). Manual valuations are stored in a machine-managed
sidecar next to the main file (``core_holdings_valuations.yaml``, symbol →
``{date, price}``) and merged over the inline ``last_valuation`` fields at
load time. Sidecar values win over inline values.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from datetime import date as _date  # field-name-safe alias for annotations
from pathlib import Path
from typing import Any, ClassVar

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError
from shared.portfolio.config import TRACK_CORE
from shared.portfolio.equity import TrackEquity, track_label

logger = logging.getLogger(__name__)

#: Default config path (relative to the config directory).
CORE_HOLDINGS_FILE = "portfolio/core_holdings.yaml"
#: Machine-managed valuations sidecar, sibling of the main YAML.
VALUATIONS_FILENAME = "core_holdings_valuations.yaml"

_WEIGHT_SUM_TOLERANCE = 1e-6


class SectorSpec(BaseModel):
    """One sector of the core allocation frame (design doc §2.1)."""

    label: str = Field(min_length=1)
    target_weight: float = Field(ge=0.0, le=1.0)


class RebalancingRules(BaseModel):
    """Rebalancing triggers (design doc §2.3) — declarative, manual execution."""

    drift_threshold_pct: float = Field(default=0.10, gt=0.0, lt=1.0)
    single_holding_max: float = Field(default=0.25, gt=0.0, lt=1.0)


class Valuation(BaseModel):
    """One manual valuation point (updated via ``sts portfolio value``)."""

    # The field is named ``date`` (fixed YAML schema), which would shadow the
    # ``datetime.date`` type during annotation evaluation — use the alias.
    date: _date | None = None
    price: float | None = Field(default=None, gt=0.0)

    @field_validator("date", mode="before")
    @classmethod
    def _coerce_date(cls, value: Any) -> Any:
        if isinstance(value, str) and value:
            return date.fromisoformat(value[:10])
        if isinstance(value, datetime):
            return value.date()
        return value


class CoreInstrument(BaseModel):
    """Shared holding/candidate schema (design doc §2.2 inclusion rules)."""

    symbol: str = Field(min_length=1)
    name: str = ""
    sector: str = Field(min_length=1)
    thesis: str = ""
    kill_criteria: list[str] = Field(default_factory=list)

    @field_validator("symbol", mode="before")
    @classmethod
    def _coerce_symbol(cls, value: Any) -> Any:
        # Keep leading zeros: YAML integers like 012450 would be lossy, but a
        # quoted string stays intact; coerce whatever arrives to str.
        return str(value).strip() if value is not None else value


class CoreHolding(CoreInstrument):
    """One held core position (manual shares/valuation bookkeeping)."""

    shares: int = Field(default=0, ge=0)
    avg_price: float = Field(default=0.0, ge=0.0)
    last_valuation: Valuation = Field(default_factory=Valuation)

    @property
    def value(self) -> float | None:
        """Position value ``shares × last_valuation.price`` (None unvalued)."""
        if self.shares <= 0:
            return 0.0
        if self.last_valuation.price is None:
            return None
        return float(self.shares) * float(self.last_valuation.price)


class CoreCandidate(CoreInstrument):
    """One candidate under watch (same schema, no shares/valuation)."""


def _default_sectors() -> dict[str, SectorSpec]:
    return {
        "defense": SectorSpec(label="방산", target_weight=0.35),
        "semiconductor_equipment": SectorSpec(label="반도체 장비", target_weight=0.35),
        "robotics": SectorSpec(label="로보틱스", target_weight=0.15),
        "cash": SectorSpec(label="현금 버퍼", target_weight=0.15),
    }


#: Sector key whose weight is carried by ``cash_krw`` (not by holdings).
CASH_SECTOR = "cash"


class CoreHoldings(ServiceConfigBase):
    """Track A manual core ledger loaded from the core-holdings YAML."""

    _default_config_file: ClassVar[str] = CORE_HOLDINGS_FILE

    sectors: dict[str, SectorSpec] = Field(default_factory=_default_sectors)
    rebalancing: RebalancingRules = Field(default_factory=RebalancingRules)
    cash_krw: float = Field(default=0.0, ge=0.0)
    holdings: list[CoreHolding] = Field(default_factory=list)
    candidates: list[CoreCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> CoreHoldings:
        if not self.sectors:
            raise ValueError("core_holdings.sectors must not be empty")
        total = sum(spec.target_weight for spec in self.sectors.values())
        if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError(
                f"core_holdings sector target_weights must sum to 1.0, got {total:.6f}"
            )

        seen: set[str] = set()
        for holding in self.holdings:
            if holding.symbol in seen:
                raise ValueError(f"duplicate core holding symbol: {holding.symbol!r}")
            seen.add(holding.symbol)

        for instrument in [*self.holdings, *self.candidates]:
            if instrument.sector not in self.sectors:
                raise ValueError(
                    f"{instrument.symbol!r} references unknown sector"
                    f" {instrument.sector!r}; configured: {sorted(self.sectors)}"
                )
            # Inclusion rule §2.2-2: Kill Criteria must be pre-declared.
            # Warn (not fail) so a hurried registration is visible, not fatal.
            if not instrument.kill_criteria:
                logger.warning(
                    "core holding %s (%s) has no kill_criteria — 설계서 §2.2"
                    " 편입 기준 위반 (논거 무효화 조건을 명시하세요)",
                    instrument.symbol,
                    instrument.name or instrument.sector,
                )
        return self

    # -- loading ------------------------------------------------------------

    @classmethod
    def load_or_default(
        cls,
        path: str | None = None,
        *,
        valuations_path: str | Path | None = None,
    ) -> CoreHoldings:
        """Load from YAML (+ valuations sidecar); missing file → defaults.

        The sidecar (``core_holdings_valuations.yaml`` next to the main file,
        or ``valuations_path`` when given) overrides the inline
        ``last_valuation`` of matching holdings.
        """
        try:
            core = cls.from_yaml(path)
        except ConfigNotFoundError:
            core = cls()
        sidecar = (
            Path(valuations_path)
            if valuations_path is not None
            else valuations_sidecar_path(path)
        )
        core.apply_valuations(load_valuations(sidecar))
        return core

    def apply_valuations(self, valuations: dict[str, Valuation]) -> None:
        """Merge sidecar valuations over the inline ``last_valuation`` fields."""
        for holding in self.holdings:
            valuation = valuations.get(holding.symbol)
            if valuation is not None:
                holding.last_valuation = valuation

    # -- contract accessors (5B filter lane / 5E UI lane) ---------------------

    def symbols(self) -> frozenset[str]:
        """Held symbols (holdings only — candidates are not owned)."""
        return frozenset(holding.symbol for holding in self.holdings)

    def sector_of(self, symbol: str) -> str | None:
        """Sector key of a held/candidate symbol, or None when unknown."""
        for instrument in [*self.holdings, *self.candidates]:
            if instrument.symbol == symbol:
                return instrument.sector
        return None

    @property
    def provisioned(self) -> bool:
        """True once the manual ledger carries any value (holdings or cash)."""
        return self.cash_krw > 0 or any(h.shares > 0 for h in self.holdings)

    def total_value(self) -> float | None:
        """Σ(shares × valuation price) + cash, or None when not computable.

        Returns None when the ledger is not provisioned, or when any held
        position (shares > 0) lacks a manual valuation — a partial sum would
        understate equity and silently skew the unified MDD math.
        """
        if not self.provisioned:
            return None
        total = float(self.cash_krw)
        for holding in self.holdings:
            value = holding.value
            if value is None:
                return None
            total += value
        return total

    def sector_weights(self) -> dict[str, float]:
        """Actual sector weights from valuations (empty when not computable).

        Cash weight comes from ``cash_krw``; every configured sector appears
        in the result (0.0 when unheld) so consumers can render actual-vs-
        target without key juggling.
        """
        total = self.total_value()
        if total is None or total <= 0:
            return {}
        values: dict[str, float] = dict.fromkeys(self.sectors, 0.0)
        values[CASH_SECTOR] = values.get(CASH_SECTOR, 0.0) + float(self.cash_krw)
        for holding in self.holdings:
            value = holding.value
            if value:
                values[holding.sector] = values.get(holding.sector, 0.0) + value
        return {key: value / total for key, value in values.items()}

    def oldest_valuation_date(self) -> date | None:
        """Oldest valuation date across held positions (freshness anchor).

        A held position whose valuation has a price but no date reads as
        None-date → the caller must treat the ledger as stale (unverifiable).
        Returns None when there are no held positions.
        """
        held = [h for h in self.holdings if h.shares > 0]
        if not held:
            return None
        dates = [h.last_valuation.date for h in held]
        if any(d is None for d in dates):
            return date.min  # unverifiable → maximally stale
        return min(d for d in dates if d is not None)


# ---------------------------------------------------------------------------
# Valuations sidecar I/O (machine-managed; the main YAML is never rewritten)
# ---------------------------------------------------------------------------


def valuations_sidecar_path(config_path: str | None = None) -> Path:
    """Resolve the sidecar path next to the main core-holdings YAML."""
    if config_path is not None and Path(config_path).is_absolute():
        return Path(config_path).parent / VALUATIONS_FILENAME
    from shared.config.loader import ConfigLoader

    relative = Path(config_path or CORE_HOLDINGS_FILE).parent / VALUATIONS_FILENAME
    return Path(ConfigLoader.get_config_dir()) / relative


def load_valuations(path: str | Path) -> dict[str, Valuation]:
    """Read the sidecar into ``{symbol: Valuation}`` (missing file → empty)."""
    sidecar = Path(path)
    if not sidecar.exists():
        return {}
    try:
        raw = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning("unreadable valuations sidecar %s: %s", sidecar, exc)
        return {}
    if not isinstance(raw, dict):
        logger.warning("valuations sidecar %s is not a mapping; ignored", sidecar)
        return {}
    valuations: dict[str, Valuation] = {}
    for symbol, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        try:
            valuations[str(symbol)] = Valuation(**entry)
        except ValueError as exc:
            logger.warning("invalid valuation for %s in %s: %s", symbol, sidecar, exc)
    return valuations


def save_valuation(
    path: str | Path, symbol: str, price: float, valuation_date: date
) -> None:
    """Upsert one symbol's valuation into the sidecar (atomic-ish rewrite)."""
    sidecar = Path(path)
    existing = {
        key: {"date": val.date.isoformat() if val.date else None, "price": val.price}
        for key, val in load_valuations(sidecar).items()
    }
    existing[str(symbol)] = {
        "date": valuation_date.isoformat(),
        "price": float(price),
    }
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Track A manual valuations sidecar — MACHINE MANAGED.\n"
        "# Written by `sts portfolio value <symbol> <price>`; merged over\n"
        "# config/portfolio/core_holdings.yaml last_valuation at load time.\n"
        "# Do not hand-edit while the CLI is in use (comments are rewritten).\n"
    )
    body = yaml.safe_dump(
        dict(sorted(existing.items())),
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    sidecar.write_text(header + body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Track A equity (consumed by services/portfolio_monitor)
# ---------------------------------------------------------------------------

#: missing_components marker for stale manual valuations (fixed contract).
TRACK_A_STALE_COMPONENT = "track_a_valuation_stale"


def compute_track_a_equity(
    core: CoreHoldings,
    *,
    as_of: date,
    stale_after_days: int,
) -> TrackEquity:
    """Track A equity from the manual ledger (never from orders/positions).

    * Not provisioned (empty ledger) or unvalued held positions → equity
      ``None`` with the ``track_a`` coverage marker — same publication shape
      the monitor used pre-Phase 5 ("" in the Redis hash).
    * Valued → ``Σ(shares × last_valuation.price) + cash_krw``. When the
      oldest valuation is older than ``stale_after_days`` the value is still
      published, flagged via :data:`TRACK_A_STALE_COMPONENT`.
    """
    label = track_label(TRACK_CORE)
    total = core.total_value()
    if total is None:
        return TrackEquity(
            track_id=TRACK_CORE,
            equity=None,
            capital_base=None,
            realized_pnl=None,
            unrealized_pnl=0.0,
            missing_components=(label,),
            degraded=False,
        )

    missing: list[str] = []
    oldest = core.oldest_valuation_date()
    if oldest is not None and (as_of - oldest).days > stale_after_days:
        missing.append(TRACK_A_STALE_COMPONENT)
        logger.warning(
            "track A valuations stale: oldest %s is > %d days before %s",
            "unknown" if oldest == date.min else oldest.isoformat(),
            stale_after_days,
            as_of.isoformat(),
        )

    return TrackEquity(
        track_id=TRACK_CORE,
        equity=float(total),
        capital_base=None,
        realized_pnl=None,
        unrealized_pnl=0.0,
        missing_components=tuple(missing),
        degraded=False,
    )
