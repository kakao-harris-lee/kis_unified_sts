"""Unit tests for the Phase 5B Track A/B correlation filters.

Hermetic: ledger/positions providers injected — no Redis client is ever
built; the reloading provider runs against tmp_path ledgers with a fake
monotonic clock. Pins the contracts:

* empty ledger → both filters are exact no-ops;
* rule 1 rejects held symbols only (skip_reason ``track_a_overlap``);
* rule 2 rejects capped-sector entries at/above the cap
  (skip_reason ``sector_cap_semiconductor``), leniently skipping symbols the
  ledger cannot classify;
* loader/provider failures fail OPEN (pass + warning);
* the ledger YAML is re-parsed only when its mtime changes, at most once per
  reload interval.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared.portfolio.core_holdings import (
    CoreCandidate,
    CoreHolding,
    CoreHoldings,
)
from shared.risk.filters.core_correlation import (
    SKIP_TRACK_A_OVERLAP,
    CoreHoldingsProvider,
    CoreSectorCapFilter,
    TrackAOverlapFilter,
)

SEMI = "semiconductor_equipment"


def _signal(symbol: str = "005930") -> SimpleNamespace:
    # The correlation filters read only ``signal.symbol`` (M4-R duck-typing).
    return SimpleNamespace(symbol=symbol)


def _holding(symbol: str, sector: str = "defense") -> CoreHolding:
    return CoreHolding(symbol=symbol, sector=sector, kill_criteria=["k"])


def _candidate(symbol: str, sector: str = SEMI) -> CoreCandidate:
    return CoreCandidate(symbol=symbol, sector=sector, kill_criteria=["k"])


def _ledger(
    holdings: list[CoreHolding] | None = None,
    candidates: list[CoreCandidate] | None = None,
) -> CoreHoldings:
    return CoreHoldings(holdings=holdings or [], candidates=candidates or [])


# ---------------------------------------------------------------------------
# Rule 1 — TrackAOverlapFilter
# ---------------------------------------------------------------------------


class TestTrackAOverlapFilter:
    def _check(self, ledger: CoreHoldings | None, symbol: str = "005930"):
        filter_ = TrackAOverlapFilter(core_holdings_provider=lambda: ledger)
        return filter_.check(_signal(symbol), None)  # type: ignore[arg-type]

    def test_empty_ledger_is_noop(self):
        result = self._check(_ledger())
        assert result.passed
        assert result.skip_reason is None
        assert result.size_multiplier == 1.0

    def test_held_symbol_rejected(self):
        result = self._check(_ledger(holdings=[_holding("005930")]))
        assert not result.passed
        assert result.skip_reason == SKIP_TRACK_A_OVERLAP
        assert result.filter_name == "core_overlap"

    def test_other_symbol_passes(self):
        result = self._check(_ledger(holdings=[_holding("012450")]))
        assert result.passed

    def test_watchlist_candidate_does_not_block(self):
        """candidates: are not owned — only holdings: block (§7.2)."""
        result = self._check(_ledger(candidates=[_candidate("005930")]))
        assert result.passed

    def test_provider_none_fails_open(self):
        result = self._check(None)
        assert result.passed

    def test_provider_error_fails_open(self):
        def _boom() -> CoreHoldings:
            raise OSError("ledger unreadable")

        filter_ = TrackAOverlapFilter(core_holdings_provider=_boom)
        result = filter_.check(_signal(), None)  # type: ignore[arg-type]
        assert result.passed


# ---------------------------------------------------------------------------
# Rule 2 — CoreSectorCapFilter
# ---------------------------------------------------------------------------


def _cap_filter(
    ledger: CoreHoldings | None,
    positions: dict[str, float] | None,
    **kwargs,
) -> CoreSectorCapFilter:
    params = {
        "core_holdings_provider": lambda: ledger,
        "sector_key": SEMI,
        "cap": 0.40,
        "skip_reason": "sector_cap_semiconductor",
        "positions_provider": lambda: positions,
    }
    params.update(kwargs)
    return CoreSectorCapFilter(**params)


#: Ledger classifying two semiconductor symbols (one candidate, one holding).
def _semi_ledger() -> CoreHoldings:
    return _ledger(
        holdings=[_holding("042700", sector=SEMI), _holding("012450")],
        candidates=[_candidate("000660")],
    )


class TestCoreSectorCapFilter:
    def test_empty_ledger_is_noop(self):
        """Unclassifiable candidate (empty ledger) → cap never applies."""
        result = _cap_filter(_ledger(), {"000660": 100.0}).check(
            _signal("000660"), None  # type: ignore[arg-type]
        )
        assert result.passed

    def test_non_capped_sector_candidate_passes_without_position_read(self):
        calls = {"n": 0}

        def _positions() -> dict[str, float]:
            calls["n"] += 1
            return {}

        filter_ = _cap_filter(_semi_ledger(), None, positions_provider=_positions)
        result = filter_.check(_signal("012450"), None)  # type: ignore[arg-type]
        assert result.passed
        assert calls["n"] == 0  # hot path: no Redis round-trip for defense

    def test_share_at_cap_rejects(self):
        # semiconductor 40% of notional (>= cap 0.40) → reject.
        positions = {"000660": 40.0, "012450": 60.0}
        result = _cap_filter(_semi_ledger(), positions).check(
            _signal("042700"), None  # type: ignore[arg-type]
        )
        assert not result.passed
        assert result.skip_reason == "sector_cap_semiconductor"
        assert result.filter_name == "core_sector_cap"

    def test_share_below_cap_passes(self):
        positions = {"000660": 39.0, "012450": 61.0}
        result = _cap_filter(_semi_ledger(), positions).check(
            _signal("042700"), None  # type: ignore[arg-type]
        )
        assert result.passed

    def test_candidate_symbol_classifies_via_watchlist(self):
        """Ledger candidates (not just holdings) classify the entry symbol."""
        positions = {"042700": 100.0}
        result = _cap_filter(_semi_ledger(), positions).check(
            _signal("000660"), None  # type: ignore[arg-type]
        )
        assert not result.passed

    def test_unclassifiable_positions_dilute_share_leniently(self):
        # "999999" is unknown to the ledger: it stays in the denominator but
        # never counts as semiconductor — unknown sectors must not inflate
        # the measured share (lenient by design).
        positions = {"000660": 40.0, "999999": 80.0}
        result = _cap_filter(_semi_ledger(), positions).check(
            _signal("042700"), None  # type: ignore[arg-type]
        )
        assert result.passed  # 40 / 120 = 0.33 < 0.40

    def test_no_positions_passes(self):
        result = _cap_filter(_semi_ledger(), {}).check(
            _signal("042700"), None  # type: ignore[arg-type]
        )
        assert result.passed

    def test_zero_total_notional_passes(self):
        result = _cap_filter(_semi_ledger(), {"000660": 0.0}).check(
            _signal("042700"), None  # type: ignore[arg-type]
        )
        assert result.passed

    def test_positions_provider_none_fails_open(self):
        result = _cap_filter(_semi_ledger(), None).check(
            _signal("042700"), None  # type: ignore[arg-type]
        )
        assert result.passed

    def test_positions_provider_error_fails_open(self):
        def _boom() -> dict[str, float]:
            raise ConnectionError("redis down")

        filter_ = _cap_filter(_semi_ledger(), None, positions_provider=_boom)
        result = filter_.check(_signal("042700"), None)  # type: ignore[arg-type]
        assert result.passed

    def test_ledger_provider_none_fails_open(self):
        result = _cap_filter(None, {"000660": 100.0}).check(
            _signal("000660"), None  # type: ignore[arg-type]
        )
        assert result.passed

    def test_configured_cap_propagates(self):
        positions = {"000660": 50.0, "012450": 50.0}
        filter_ = _cap_filter(_semi_ledger(), positions, cap=0.60)
        result = filter_.check(_signal("042700"), None)  # type: ignore[arg-type]
        assert result.passed  # 0.5 < 0.6

    def test_invalid_construction_rejected(self):
        with pytest.raises(ValueError):
            _cap_filter(None, None, cap=0.0)
        with pytest.raises(ValueError):
            _cap_filter(None, None, cap=1.5)
        with pytest.raises(ValueError):
            _cap_filter(None, None, sector_key="")
        with pytest.raises(ValueError):
            _cap_filter(None, None, skip_reason="")


# ---------------------------------------------------------------------------
# CoreHoldingsProvider — mtime-gated reload
# ---------------------------------------------------------------------------


def _write_ledger(path: Path, symbols: list[str], *, mtime: float) -> None:
    if symbols:
        lines = ["holdings:"] + [
            f'  - {{symbol: "{s}", sector: defense, kill_criteria: ["k"]}}'
            for s in symbols
        ]
    else:
        lines = ["holdings: []"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.utime(path, (mtime, mtime))


class TestCoreHoldingsProvider:
    def _provider(
        self, path: Path, now: list[float], interval: int = 60
    ) -> CoreHoldingsProvider:
        return CoreHoldingsProvider(
            reload_interval_seconds=interval, path=path, clock=lambda: now[0]
        )

    def test_loads_ledger_on_first_call(self, tmp_path: Path):
        path = tmp_path / "core_holdings.yaml"
        _write_ledger(path, ["005930"], mtime=1000.0)
        provider = self._provider(path, now=[0.0])
        ledger = provider()
        assert ledger is not None
        assert ledger.symbols() == frozenset({"005930"})

    def test_within_interval_returns_cache_without_stat(self, tmp_path: Path):
        path = tmp_path / "core_holdings.yaml"
        _write_ledger(path, ["005930"], mtime=1000.0)
        now = [0.0]
        provider = self._provider(path, now)
        first = provider()
        _write_ledger(path, ["000660"], mtime=2000.0)  # changed on disk
        now[0] = 59.0  # still inside the 60s interval
        assert provider() is first  # cached — no stat, no re-parse

    def test_after_interval_mtime_change_reloads(self, tmp_path: Path):
        path = tmp_path / "core_holdings.yaml"
        _write_ledger(path, ["005930"], mtime=1000.0)
        now = [0.0]
        provider = self._provider(path, now)
        provider()
        _write_ledger(path, ["000660"], mtime=2000.0)
        now[0] = 61.0
        reloaded = provider()
        assert reloaded is not None
        assert reloaded.symbols() == frozenset({"000660"})

    def test_after_interval_unchanged_mtime_skips_reparse(self, tmp_path: Path):
        path = tmp_path / "core_holdings.yaml"
        _write_ledger(path, ["005930"], mtime=1000.0)
        now = [0.0]
        provider = self._provider(path, now)
        first = provider()
        now[0] = 61.0
        assert provider() is first  # same object — stat only, no YAML parse

    def test_missing_file_yields_empty_default_ledger(self, tmp_path: Path):
        provider = self._provider(tmp_path / "absent.yaml", now=[0.0])
        ledger = provider()
        assert ledger is not None  # defaults, NOT a failure
        assert ledger.symbols() == frozenset()

    def test_file_created_after_start_is_picked_up(self, tmp_path: Path):
        path = tmp_path / "core_holdings.yaml"
        now = [0.0]
        provider = self._provider(path, now)
        assert provider().symbols() == frozenset()  # type: ignore[union-attr]
        _write_ledger(path, ["005930"], mtime=1000.0)
        now[0] = 61.0
        assert provider().symbols() == frozenset({"005930"})  # type: ignore[union-attr]

    def test_malformed_yaml_fails_open_as_none(self, tmp_path: Path):
        path = tmp_path / "core_holdings.yaml"
        path.write_text("holdings: {not: [valid", encoding="utf-8")
        provider = self._provider(path, now=[0.0])
        assert provider() is None

    def test_invalid_ledger_schema_fails_open_as_none(self, tmp_path: Path):
        path = tmp_path / "core_holdings.yaml"
        # Sector weights not summing to 1.0 → pydantic validation error.
        path.write_text(
            "sectors:\n  defense: {label: d, target_weight: 0.5}\n",
            encoding="utf-8",
        )
        provider = self._provider(path, now=[0.0])
        assert provider() is None

    def test_recovers_after_failure_when_file_fixed(self, tmp_path: Path):
        path = tmp_path / "core_holdings.yaml"
        path.write_text("holdings: {not: [valid", encoding="utf-8")
        os.utime(path, (1000.0, 1000.0))
        now = [0.0]
        provider = self._provider(path, now)
        assert provider() is None
        _write_ledger(path, ["005930"], mtime=2000.0)
        now[0] = 61.0
        reloaded = provider()
        assert reloaded is not None
        assert reloaded.symbols() == frozenset({"005930"})

    def test_invalid_interval_rejected(self, tmp_path: Path):
        with pytest.raises(ValueError):
            CoreHoldingsProvider(reload_interval_seconds=0, path=tmp_path / "x.yaml")
