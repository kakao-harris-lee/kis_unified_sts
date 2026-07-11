"""LeverageFilter — gross notional / equity leverage cap (Phase 4-g).

Introduces the **first leverage constraint anywhere in the repo** (before this
PR only a single World-A YAML comment mentioned leverage; no code enforced it).
It ports the missing "레버리지 제한" bullet of plan §6(d) into the surviving
decoupled World-B ``RiskFilterLayer`` as a new-entry gate.

Definition
----------
::

    gross_leverage = Σ|quantity · price · multiplier| / equity

The numerator sums the **absolute** notional of every already-open position, so
a long and a short of the same size contribute identically — long/short
symmetry (the non-negotiable futures rule) is preserved *for free* by the
``abs`` (the filter never inspects ``side``). A new entry is rejected only when
``gross_leverage > max_gross_leverage`` AND ``mode == "enforce"``.

Multiplier (DRY, no hardcoded contract constants)
-------------------------------------------------
The per-contract multiplier is resolved through
:func:`shared.risk.futures_margin.spec_for_symbol` against the same
``MarginProductSpec`` map the margin read-model uses — no contract multiplier is
hardcoded here. A symbol that resolves no spec (and every symbol when
``product_specs`` is ``None``, e.g. the stock chain — cash equities have
multiplier 1) uses a multiplier of ``1.0``. Understating a futures multiplier
(unresolved spec) only *understates* leverage, so it can never cause a spurious
reject — it is fail-open-safe.

When ``product_specs`` *is* supplied (a futures wiring) but a held position's
``code`` resolves no spec — e.g. the code prefix has drifted from the configured
product prefixes — the ``1.0`` fallback is retained (still fail-open-safe) but a
throttled *one-warning-per-symbol* ``logger.warning`` fires so the under-counting
is observable, mirroring the margin read-model's ``missing_components`` /
``degraded`` convention (:func:`futures_margin.compute_margin_risk` records
``margin_product:{symbol}``). Memory #601: a symbol-prefix mismatch must never
fail *silently*. The provider's position ``code`` MUST therefore align with the
futures product-spec prefixes or leverage is understated.

Fail-OPEN design (shadow-first rollout — mirrors :class:`MarginGateFilter` and
:class:`ConcurrentPositionsFilter`)
-----------------------------------------------------------------------------
The filter is *inert* unless an operator both enables it, flips it to
``enforce``, AND a snapshot provider is wired. Every one of these passes the
signal unchanged (``size_multiplier`` = 1.0):

* ``mode`` != ``enforce`` (default ``shadow``) → pass (provider never consulted);
* ``max_gross_leverage`` is ``None`` (no cap) → pass (provider never consulted);
* no ``snapshot_provider`` injected → pass (structurally inert; no daemon wires
  a provider in this landing, so the two shadow daemons are unaffected);
* provider raises / returns ``None`` / a non-mapping / malformed positions or
  values → pass (resolved entirely inside :meth:`_read_gross_leverage`'s single
  fail-open guard so a corrupt snapshot can NEVER raise out of :meth:`check`
  into the guardless ``RiskFilterLayer.evaluate`` → daemon path, which would
  fail *closed*: the poison message never XACKs and the pipeline stalls);
* ``equity`` missing / non-positive (``<= 0``) → pass (also the 0-division
  guard — a zero/negative denominator can never produce a block);
* (when ``stale_max_age_seconds`` is configured) snapshot ``asof_ts`` missing /
  unparseable / older than the bound → pass (positive-form staleness, memory
  #458: a missing timestamp is treated as *stale*, never as fresh).

Because no daemon wires a provider today, this filter is **structurally inert**
at landing — effective activation needs a follow-up (P4-h2 / P5) that wires a
position+equity snapshot provider (and, for the futures chain, the real
``product_specs``) PLUS an operator flip of ``mode`` to ``enforce``.

Provider contract
-----------------
``snapshot_provider`` is a zero-arg callable returning a mapping with:

* ``positions`` — a sequence of already-open position mappings, each carrying
  ``code`` (symbol), ``quantity`` (magnitude; may be signed — ``abs`` is taken
  either way), and ``current_price``. It MUST **exclude the pending candidate**
  being evaluated (leverage is measured on the current book, not the hypothetical
  post-entry book) and cover every asset the equity denominator spans. For the
  futures chain the ``code`` MUST match a configured product-spec prefix (see
  **Multiplier**); a mismatch defaults the per-contract multiplier to ``1.0`` and
  understates leverage (fail-open-safe, but a throttled warning fires). A single
  snapshot may carry BOTH a long (+N) and a short (−N) of the same symbol (a
  hedge book) — each contributes ``|N|`` to the gross sum, so gross is a SUM of
  absolute notionals, never a NET that would cancel to zero.
* ``equity_krw`` — account equity in KRW (broker snapshot or the config/env
  fallback the margin/kill lanes use). The leverage *denominator* is equity, not
  cash. The **canonical** futures margin read-model publishes account equity
  under ``account_equity_krw`` (:func:`futures_margin.margin_state_to_fields`);
  this filter reads ``equity_krw`` first and falls back to
  ``account_equity_krw``, so a follow-up that reuses the margin snapshot as the
  provider is not silently inert (review F1). ``KIS_FUTURES_EQUITY_KRW`` is the
  usual env fallback source.
* ``asof_ts`` — optional KST-naive ISO-8601 timestamp; only consulted when
  ``stale_max_age_seconds`` is set.

Boundary semantics
------------------
The reject boundary is strict ``>``: ``gross_leverage > max_gross_leverage``
rejects, exactly ``== max_gross_leverage`` passes (leverage *at* the cap is
still allowed; only exceeding it blocks a new entry).

Configuration: ``config/risk.yaml`` ``risk.leverage`` / ``risk_stock.leverage``
(``enabled`` default ``false`` + ``mode`` default ``shadow`` +
``max_gross_leverage`` [asset-specific — e.g. futures 3.0, cash stock 1.0] +
optional ``stale_max_age_seconds``). No threshold is hardcoded — the cap lives
entirely in config.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.futures_margin import MarginProductSpec, spec_for_symbol
from shared.risk.state import RiskStateSnapshot
from shared.utils.coercion import to_float

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

#: Rejection tag emitted when the gross-leverage cap blocks a new entry.
SKIP_LEVERAGE = "max_gross_leverage"

#: The filter-config mode value that arms enforcement. Anything else (default
#: ``shadow``) fails open — leverage is measured but never blocks.
_ENFORCE_MODE = "enforce"


class LeverageFilter(RiskFilter):
    """Reject new entries once gross notional / equity leverage exceeds the cap.

    Args:
        mode: Filter enforcement mode. Only ``"enforce"`` arms rejection; any
            other value (default ``"shadow"``) passes every signal without ever
            consulting the provider. No leverage publisher carries a ``mode``
            field, so this is a deliberate filter-side config decision.
        max_gross_leverage: Cap on ``Σ|notional| / equity``. ``None`` disables
            the check (fail-open — the provider is never consulted).
        snapshot_provider: Zero-arg callable returning the position+equity
            snapshot mapping (or ``None``). ``None`` (not injected), a ``None``
            return, a non-mapping, malformed positions/values, or any raised
            exception all fail OPEN. See **Provider contract** in the module
            docstring.
        product_specs: Symbol→:class:`MarginProductSpec` map used to resolve the
            per-contract multiplier via :func:`spec_for_symbol` (DRY reuse of
            the margin read-model's contract constants). ``None`` (the stock
            chain, and any wiring without specs) → multiplier ``1.0`` for every
            symbol. A futures wiring MUST inject the real specs alongside the
            provider or leverage is understated (fail-open-safe but inaccurate);
            that wiring is a follow-up (P4-h2 / P5).
        stale_max_age_seconds: When set, fail-open on a snapshot whose
            ``asof_ts`` is missing / unparseable / older than this (KST-naive,
            positive-form, memory #458). ``None`` (default) disables the
            staleness gate — the snapshot is trusted to be current.
        now_provider: KST-naive clock override for staleness tests.
    """

    name = "leverage"

    def __init__(
        self,
        *,
        mode: str,
        max_gross_leverage: float | None,
        snapshot_provider: Callable[[], Mapping[str, Any] | None] | None = None,
        product_specs: Mapping[str, MarginProductSpec] | None = None,
        stale_max_age_seconds: int | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.mode: str = str(mode or "").strip().lower()
        self.max_gross_leverage: float | None = max_gross_leverage
        self._snapshot_provider = snapshot_provider
        self._product_specs = product_specs
        #: Symbols already warned about (unresolved spec → 1.0 fallback). Throttles
        #: the F2 observability warning to once per symbol — :meth:`check` runs per
        #: signal on the hot path, so an un-deduped warning would flood the log.
        self._warned_unresolved_symbols: set[str] = set()
        self.stale_max_age_seconds: int | None = stale_max_age_seconds
        self._now_provider = now_provider or (
            lambda: datetime.now(KST).replace(tzinfo=None)
        )

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,  # noqa: ARG002 — account-level gate; signal content unused
        state_snapshot: RiskStateSnapshot,  # noqa: ARG002
    ) -> FilterResult:
        # Not armed → observation-only, never touches the provider.
        if self.mode != _ENFORCE_MODE:
            return self._pass()
        # No cap configured → nothing to enforce (provider never consulted).
        if self.max_gross_leverage is None:
            return self._pass()

        # _read_gross_leverage normalizes to a float inside one fail-open guard
        # (or returns None ⇒ pass), so the comparison below is on already-valid
        # data — nothing here can raise into the guardless layer/daemon path.
        gross_leverage = self._read_gross_leverage()
        if gross_leverage is None:
            return self._pass()

        # Strict boundary: leverage AT the cap passes; only exceeding it blocks.
        if gross_leverage > self.max_gross_leverage:
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason=SKIP_LEVERAGE,
            )
        return self._pass()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _pass(self) -> FilterResult:
        return FilterResult(passed=True, filter_name=self.name)

    def _read_gross_leverage(self) -> float | None:
        """Compute ``Σ|notional| / equity``, failing OPEN on any error.

        The *entire* provider contact surface — the call, the ``Mapping`` type
        check, staleness, equity/position coercion, spec resolution, and the
        division — lives inside one fail-open guard. A corrupt return therefore
        can never raise out of :meth:`check` into the guardless
        ``RiskFilterLayer.evaluate`` → daemon path (which would fail *closed*),
        the opposite of this filter's fail-open intent.

        Returns the gross leverage ratio, or ``None`` (⇒ pass) when there is no
        provider, the snapshot is corrupt/stale, equity is missing/non-positive,
        or any position value cannot be coerced.
        """
        if self._snapshot_provider is None:
            return None
        try:
            raw = self._snapshot_provider()
            if not isinstance(raw, Mapping):
                if raw is not None:
                    logger.warning(
                        "leverage provider returned %s, not a mapping; failing open",
                        type(raw).__name__,
                    )
                return None

            # Positive-form staleness (only when configured): a missing/unparseable
            # timestamp is treated as stale → pass, never as a live block (#458).
            if self.stale_max_age_seconds is not None and self._is_stale(
                raw.get("asof_ts")
            ):
                return None

            # Equity denominator. ``equity_krw`` is this filter's own key; the
            # canonical futures margin read-model publishes account equity under
            # ``account_equity_krw`` (futures_margin.margin_state_to_fields), so
            # accept it as an alias (review F1) — a follow-up that reuses the
            # margin snapshot as the provider would otherwise read None here and
            # go silently inert. Both reads stay inside this one fail-open guard.
            equity = to_float(raw.get("equity_krw"))
            if equity is None:
                equity = to_float(raw.get("account_equity_krw"))
            if equity is None or equity <= 0:
                # Missing / non-positive equity → fail open (also the 0-division
                # guard: a bad denominator can never manufacture a block).
                return None

            gross_notional = self._gross_notional(raw.get("positions"))
            if gross_notional is None:
                return None
            return gross_notional / equity
        except Exception as exc:  # noqa: BLE001 — fail-open on any read/coerce error
            logger.warning("leverage read failed: %s", exc)
            return None

    def _gross_notional(self, positions: Any) -> float | None:
        """Sum ``|quantity · price · multiplier|`` over open positions.

        Returns ``0.0`` for an empty/absent book (no leverage), the summed gross
        notional for a well-formed position sequence, or ``None`` when the
        container or any leg is malformed (⇒ fail open). Taking ``abs`` makes the
        sum side-independent, so a long and an equal short net to the same gross
        notional (long/short symmetry).
        """
        if positions is None:
            return 0.0
        # A mapping / string / non-sequence container is malformed → fail open.
        if isinstance(positions, (Mapping, str, bytes)) or not isinstance(
            positions, Sequence
        ):
            logger.warning(
                "leverage positions is %s, not a sequence; failing open",
                type(positions).__name__,
            )
            return None

        total = 0.0
        for position in positions:
            if not isinstance(position, Mapping):
                return None
            quantity = to_float(position.get("quantity"))
            price = to_float(position.get("current_price"))
            if quantity is None or price is None:
                # A malformed leg would silently under-count notional and
                # under-state leverage; fail open on the whole snapshot instead.
                return None
            symbol = str(position.get("code", "")).strip()
            multiplier = self._multiplier_for(symbol)
            total += abs(quantity * price * multiplier)
        return total

    def _multiplier_for(self, symbol: str) -> float:
        """Resolve the per-contract multiplier via the margin SoT (DRY).

        ``None`` product_specs (stock chain / unwired) → ``1.0`` for every symbol
        (cash equities: the *correct* value, not a degraded fallback — no
        warning). A resolved spec contributes its ``multiplier_krw_per_point``.

        When product_specs *are* supplied (a futures wiring) but ``symbol``
        resolves no spec, the multiplier still falls back to ``1.0`` (understates
        leverage, fail-open-safe) but a throttled ``logger.warning`` fires once
        per symbol so the under-counting is observable — mirroring the margin
        read-model recording ``margin_product:{symbol}`` as a missing/degraded
        component (memory #601: a prefix mismatch must never fail silently). The
        provider's position ``code`` must align with the futures product-spec
        prefixes; a drift both understates leverage and surfaces via this warning.
        """
        if not self._product_specs:
            return 1.0
        spec = spec_for_symbol(symbol, self._product_specs)
        if spec is not None:
            return spec.multiplier_krw_per_point
        # product_specs given but this symbol matched no prefix → 1.0 (understated,
        # fail-open-safe). Warn once per symbol (throttled — hot path).
        if symbol not in self._warned_unresolved_symbols:
            self._warned_unresolved_symbols.add(symbol)
            logger.warning(
                "leverage: no futures product spec for symbol %r; multiplier "
                "defaults to 1.0 (leverage understated, fail-open-safe) — check "
                "position code aligns with configured product prefixes",
                symbol or "unknown",
            )
        return 1.0

    def _is_stale(self, asof_raw: Any) -> bool:
        """True when asof_ts is missing/unparseable/too old (→ fail open).

        Positive-form staleness (memory #458): a missing or malformed timestamp
        is treated as stale (→ pass), never as fresh, so a "NaN-clean" snapshot
        can't be mistaken for a live leverage reading. Only reached when
        ``stale_max_age_seconds`` is configured.
        """
        assert self.stale_max_age_seconds is not None  # guarded by caller
        if not asof_raw:
            return True
        try:
            asof = datetime.fromisoformat(str(asof_raw))
        except ValueError:
            logger.warning("leverage: unparseable asof_ts %r", asof_raw)
            return True
        if asof.tzinfo is not None:
            asof = asof.astimezone(KST).replace(tzinfo=None)
        age = (self._now_provider() - asof).total_seconds()
        return age > self.stale_max_age_seconds
