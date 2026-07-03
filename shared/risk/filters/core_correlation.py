"""Track A/B correlation filters (Phase 5B, roadmap §5.1 / 설계서 §7.2).

Two stock-only RiskFilterLayer filters gate Track B (stock swing) entries
against the Track A core-holdings manual ledger
(``config/portfolio/core_holdings.yaml``):

* :class:`TrackAOverlapFilter` — rule 1: reject candidates whose symbol is
  already HELD in Track A (``skip_reason="track_a_overlap"``). Candidates on
  the ledger watchlist (``candidates:``) are not owned and do not block.
* :class:`CoreSectorCapFilter` — rule 2: reject NEW entries into the capped
  sector (default ``semiconductor_equipment``) while that sector's share of
  the current Track B open-position notional is at or above the configured
  cap (``skip_reason="sector_cap_semiconductor"``).

Sector classification (rule 2) — conservative reduced scope
-----------------------------------------------------------
No repo data source classifies arbitrary KOSPI/KOSDAQ codes by sector (the
screener universe, theme targets, and market-structure stores carry no
per-symbol sector field; ``config/trade_trend_priority.yaml::symbol_sectors``
is a small screener-priority whitelist, not a risk-grade classification).
The only operator-vetted mapping is the Track A ledger itself, so rule 2
classifies via :meth:`CoreHoldings.sector_of` (holdings + candidates) and
therefore only fires when the candidate is a symbol the operator explicitly
listed under the capped sector. Symbols the ledger cannot classify are
treated leniently: an unclassifiable candidate passes, and unclassifiable
open positions count toward the total (denominator) but never toward the
capped-sector notional (numerator) — unknown sectors must not inflate the
measured share.

Fail-open contract (mirrors :class:`PortfolioMddFilter`): ledger stat/parse
failures and position-store read failures pass the signal unchanged with a
warning. With the ledger empty (current repo state) both filters are exact
no-ops.

Wired by ``RiskFilterLayer.from_config`` only when the config object carries
a ``core_correlation`` block — i.e. for ``StockRiskConfig``; the futures
``FuturesRiskConfig`` has no such attribute, keeping the futures chain
untouched.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from shared.decision.signal import Signal
from shared.portfolio.core_holdings import CORE_HOLDINGS_FILE, CoreHoldings
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.state import RiskStateSnapshot
from shared.streaming.stock_keys import stock_daemon_positions_key

logger = logging.getLogger(__name__)

#: Rule 1 rejection tag (fixed contract — persisted for observability).
SKIP_TRACK_A_OVERLAP = "track_a_overlap"


class CoreHoldingsProvider:
    """mtime-gated reloading loader for the Track A core-holdings ledger.

    ``RiskFilterLayer.evaluate`` runs on the candidate hot path, so the YAML
    must never be re-parsed per signal. The provider:

    1. loads the ledger on first use;
    2. re-``stat``s the file at most once per ``reload_interval_seconds``
       (monotonic clock);
    3. re-parses only when the mtime actually changed.

    The ledger is read through :meth:`CoreHoldings.load_or_default` with an
    ABSOLUTE path — the absolute-path branch of ``ServiceConfigBase.from_yaml``
    reads the file directly, bypassing the ``ConfigLoader`` cache, so an mtime
    change is guaranteed to be observed. The valuations sidecar only affects
    prices (never symbols/sectors), so its mtime is deliberately not tracked.

    Fail-open: any stat/parse/validation failure logs a warning and yields
    ``None`` until the next reload check; consumers must pass on ``None``.

    Args:
        reload_interval_seconds: Minimum seconds between mtime checks.
        path: Absolute ledger path override (tests). ``None`` resolves the
            standard config-dir location on every reload check, honouring
            ``KIS_CONFIG_DIR`` the same way ``ServiceConfigBase.from_yaml``
            does.
        clock: Monotonic-clock override for hermetic reload tests.
    """

    def __init__(
        self,
        *,
        reload_interval_seconds: int,
        path: str | Path | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if reload_interval_seconds <= 0:
            raise ValueError(
                "reload_interval_seconds must be > 0, "
                f"got {reload_interval_seconds!r}"
            )
        self._interval: float = float(reload_interval_seconds)
        self._explicit_path: Path | None = Path(path) if path is not None else None
        self._clock: Callable[[], float] = clock or time.monotonic
        self._checked_at: float | None = None
        self._mtime: float | None = None
        self._cached: CoreHoldings | None = None

    def __call__(self) -> CoreHoldings | None:
        """Return the (possibly cached) ledger, or ``None`` on failure."""
        now = self._clock()
        if self._checked_at is not None and (now - self._checked_at) < self._interval:
            return self._cached
        first_load = self._checked_at is None
        self._checked_at = now

        try:
            ledger_path = self._resolve_path()
            mtime = ledger_path.stat().st_mtime if ledger_path.exists() else None
        except Exception:  # noqa: BLE001 — fail-open on any stat error
            logger.warning(
                "core-holdings ledger stat failed; failing open", exc_info=True
            )
            self._mtime = None
            self._cached = None
            return None

        if not first_load and mtime == self._mtime:
            return self._cached

        try:
            # Missing file → CoreHoldings defaults (empty ledger → no-op).
            self._cached = CoreHoldings.load_or_default(str(ledger_path))
        except Exception:  # noqa: BLE001 — fail-open on any parse error
            logger.warning(
                "core-holdings ledger load failed (%s); failing open",
                ledger_path,
                exc_info=True,
            )
            self._cached = None
        self._mtime = mtime
        return self._cached

    def _resolve_path(self) -> Path:
        """Resolve the ledger path (explicit override or config dir)."""
        if self._explicit_path is not None:
            return self._explicit_path
        from shared.config.loader import ConfigLoader

        # Mirror ServiceConfigBase.from_yaml: honour a (possibly monkeypatched)
        # KIS_CONFIG_DIR that differs from the loader's current config dir.
        env_config_dir = os.environ.get("KIS_CONFIG_DIR")
        if env_config_dir and Path(env_config_dir) != ConfigLoader.get_config_dir():
            ConfigLoader.set_config_dir(env_config_dir)
        return Path(ConfigLoader.get_config_dir()) / CORE_HOLDINGS_FILE


def _default_positions_provider() -> Callable[[], Mapping[str, float] | None]:
    """Lazy sync-Redis reader for Track B open-position notionals.

    Reads the M4 stock daemon positions hash (written by
    ``services/stock_order_router``: one JSON record per code carrying
    ``entry_price`` and ``quantity``) and returns ``{code: notional KRW}``.
    ``RiskFilterLayer.evaluate`` is synchronous, so the filter keeps its own
    sync client — same pattern as ``PortfolioMddFilter``'s default snapshot
    provider. The client is created on first use and reused afterwards.
    """
    client: Any = None

    def _read() -> Mapping[str, float] | None:
        nonlocal client
        if client is None:
            import redis as redis_lib

            from shared.config.runtime_defaults import redis_url_from_env

            client = redis_lib.Redis.from_url(
                redis_url_from_env(), decode_responses=True
            )
        raw = client.hgetall(stock_daemon_positions_key())
        positions: dict[str, float] = {}
        for code, record_json in dict(raw).items():
            try:
                record = json.loads(record_json)
                notional = float(record["entry_price"]) * float(record["quantity"])
            except (KeyError, TypeError, ValueError) as exc:
                # Lenient: a malformed record drops out of the share math
                # entirely rather than poisoning the whole read.
                logger.warning(
                    "unparseable position record for %s; "
                    "excluded from sector-cap notional: %s",
                    code,
                    exc,
                )
                continue
            positions[str(code)] = notional
        return positions

    return _read


class TrackAOverlapFilter(RiskFilter):
    """Rule 1 — reject Track B entries into symbols already held in Track A.

    설계서 §7.2: "트랙 B는 트랙 A 보유 종목과 동일 종목 중복 진입 금지".
    Only HELD symbols block (:meth:`CoreHoldings.symbols` is holdings-only);
    ledger watchlist candidates are not owned and pass.

    Args:
        core_holdings_provider: Zero-arg callable returning the current
            :class:`CoreHoldings` ledger or ``None`` (→ fail-open pass).
            Production wiring uses a shared :class:`CoreHoldingsProvider`;
            tests inject a lambda.
    """

    name = "core_overlap"

    def __init__(
        self,
        *,
        core_holdings_provider: Callable[[], CoreHoldings | None],
    ) -> None:
        self._core_holdings_provider = core_holdings_provider

    def check(
        self,
        signal: Signal,
        state_snapshot: RiskStateSnapshot,  # noqa: ARG002
    ) -> FilterResult:
        """Reject when ``signal.symbol`` is currently held in Track A."""
        core = _read_ledger(self._core_holdings_provider, self.name)
        if core is None:
            return FilterResult(passed=True, filter_name=self.name)
        if signal.symbol in core.symbols():
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason=SKIP_TRACK_A_OVERLAP,
            )
        return FilterResult(passed=True, filter_name=self.name)


class CoreSectorCapFilter(RiskFilter):
    """Rule 2 — cap the capped sector's share of Track B position notional.

    설계서 §7.2: "트랙 B 진입 종목 중 반도체 섹터 비중 상한: 트랙 B 포지션의
    40%". When the candidate classifies into ``sector_key`` and the sector's
    share of current Track B open-position notional is already ``>= cap``,
    the entry is rejected with the configured ``skip_reason``.

    Classification uses :meth:`CoreHoldings.sector_of` (see module docstring:
    conservative reduced scope — no full-coverage sector source exists).
    Lenient treatment of unclassifiable symbols is deliberate: candidates the
    ledger does not know pass unfiltered, and unknown-sector open positions
    contribute to the denominator only.

    Args:
        core_holdings_provider: Zero-arg callable returning the current
            :class:`CoreHoldings` ledger or ``None`` (→ fail-open pass).
        sector_key: Ledger sector key being capped
            (``config/portfolio/core_holdings.yaml`` ``sectors`` key).
        cap: Share threshold in ``(0.0, 1.0]``; entries are rejected when the
            pre-entry sector share is ``>= cap``.
        skip_reason: Rejection tag emitted on cap breach (fixed contract:
            ``sector_cap_semiconductor``).
        positions_provider: Zero-arg callable returning ``{code: notional
            KRW}`` for current Track B open positions, or ``None`` (→
            fail-open pass). Defaults to a lazy sync-Redis reader of the
            stock daemon positions hash; inject in tests.
    """

    name = "core_sector_cap"

    def __init__(
        self,
        *,
        core_holdings_provider: Callable[[], CoreHoldings | None],
        sector_key: str,
        cap: float,
        skip_reason: str,
        positions_provider: Callable[[], Mapping[str, float] | None] | None = None,
    ) -> None:
        if not (0.0 < cap <= 1.0):
            raise ValueError(f"cap must be in (0.0, 1.0], got {cap!r}")
        if not sector_key:
            raise ValueError("sector_key must be a non-empty string")
        if not skip_reason:
            raise ValueError("skip_reason must be a non-empty string")
        self._core_holdings_provider = core_holdings_provider
        self.sector_key: str = sector_key
        self.cap: float = cap
        self.skip_reason: str = skip_reason
        self._positions_provider = positions_provider or _default_positions_provider()

    def check(
        self,
        signal: Signal,
        state_snapshot: RiskStateSnapshot,  # noqa: ARG002
    ) -> FilterResult:
        """Reject capped-sector entries while the sector share is at the cap."""
        core = _read_ledger(self._core_holdings_provider, self.name)
        if core is None:
            return self._pass()

        # Classify the candidate FIRST: non-capped (or unclassifiable —
        # lenient) candidates pass without touching the position store, so
        # the common path costs one in-memory lookup and no Redis round-trip.
        if core.sector_of(signal.symbol) != self.sector_key:
            return self._pass()

        positions = self._read_positions()
        if positions is None:
            return self._pass()

        total_notional = sum(positions.values())
        if total_notional <= 0:
            # No (or zero-notional) Track B positions → share is 0 < cap.
            return self._pass()

        capped_notional = sum(
            notional
            for code, notional in positions.items()
            if core.sector_of(code) == self.sector_key
        )
        share = capped_notional / total_notional
        if share >= self.cap:
            logger.info(
                "core_sector_cap: %s share %.4f >= cap %.4f — rejecting %s",
                self.sector_key,
                share,
                self.cap,
                signal.symbol,
            )
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason=self.skip_reason,
            )
        return self._pass()

    def _pass(self) -> FilterResult:
        return FilterResult(passed=True, filter_name=self.name)

    def _read_positions(self) -> Mapping[str, float] | None:
        try:
            return self._positions_provider()
        except Exception as exc:  # noqa: BLE001 — fail-open on any read error
            logger.warning("core_sector_cap positions read failed: %s", exc)
            return None


def _read_ledger(
    provider: Callable[[], CoreHoldings | None], filter_name: str
) -> CoreHoldings | None:
    """Fail-open ledger read shared by both correlation filters."""
    try:
        return provider()
    except Exception as exc:  # noqa: BLE001 — fail-open on any read error
        logger.warning("%s: core-holdings read failed: %s", filter_name, exc)
        return None
