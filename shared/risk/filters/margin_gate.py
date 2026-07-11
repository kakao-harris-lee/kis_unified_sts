"""MarginGateFilter — futures margin-risk new-entry gate (Phase 4-f).

Wires the futures margin-risk read-model (``shared/risk/futures_margin.py``,
published to ``futures:risk:latest`` by ``services/futures_margin_risk``) into
the surviving decoupled World-B ``RiskFilterLayer`` as a **new-entry gate**.
Before this filter the decoupled futures chain had no margin awareness at all —
account margin usage / liquidation buffer / stress loss existed only as an
advisory read-model consumed by the dashboard and the hedge lane.

This filter does NOT re-derive any margin math. It reads the already-classified
``risk_level`` the publisher put in the snapshot and only *branches* on it — the
thresholds live entirely in ``config/futures_margin.yaml`` on the publish side,
so nothing here is hardcoded (설계 2.7 / plan §6(d)).

Snapshot contract (``futures:risk:latest`` hash, produced by
:func:`shared.risk.futures_margin.margin_state_to_fields`)
------------------------------------------------------------------------------
Only three fields are consumed here; the rest are dashboard/hedge advisory:

* ``risk_level``  — string, one of :data:`shared.risk.futures_margin.RISK_LEVELS`
  (``ok`` < ``watch`` < ``reduce_only`` < ``block_new_entries`` < ``critical``).
  An unknown/absent value fails OPEN (pass) rather than guessing severity.
* ``asof_ts``     — KST-naive ISO-8601 timestamp (``state.asof_ts.isoformat()``);
  drives the staleness gate. Missing/unparseable → treated as stale → pass.
* ``degraded``    — advisory only; NOT gated on (a degraded-but-fresh snapshot
  still carries a usable ``risk_level``; live fail-closed already folds a bad
  account snapshot into ``critical`` on the publish side).

Fail-OPEN design (shadow-first rollout — mirrors :class:`PortfolioMddFilter` and
:class:`ConcurrentPositionsFilter`)
------------------------------------------------------------------------------
The filter is *inert* unless an operator both enables it AND flips it to
``enforce`` AND the publisher is live. Every one of these passes the signal
unchanged (``size_multiplier`` = 1.0):

* snapshot absent — the ``services/futures_margin_risk`` publisher is dormant
  (no compose profile) so ``futures:risk:latest`` never exists → pass;
* Redis read error / provider raises → pass;
* snapshot ``asof_ts`` missing / unparseable / older than
  ``stale_max_age_seconds`` → pass (positive-form staleness, memory #458);
* corrupt / non-mapping snapshot (deserialization failure) → pass, resolved
  entirely inside the read guard so a poison snapshot can never raise out of
  :meth:`check` into the guardless ``RiskFilterLayer.evaluate`` → daemon path
  (an unhandled raise there fails *closed* — the message never XACKs and the
  pipeline stalls, the opposite of this filter's intent);
* ``mode`` != ``enforce`` (the default is ``shadow``) → pass;
* ``risk_level`` not in :data:`_BLOCKING_RISK_LEVELS` → pass.

Only ``risk_level`` ∈ {``block_new_entries``, ``critical``} in ``enforce`` mode
rejects a new entry. ``reduce_only`` is **passed** in this landing: mapping it to
a soft ``size_multiplier`` would require a new (hardcoded) size factor the
publisher does not mandate, so a soft-reduce policy is deferred to P5 / operator
rather than invented here (task: "발행된 risk_level을 그대로 소비"). The
dashboard already surfaces ``reduce_only`` as an advisory ``warn``.

Because the publisher ships dormant, this filter is **structurally inert** at
landing — effective activation needs P5 (start the publisher) + an operator flip
of ``mode`` to ``enforce``. It is a new-entry gate for *futures only*; the
``RiskFilterLayer.from_config`` wiring builds it solely when the config's
``_asset_class`` is ``"futures"`` (see that method), so the stock chain never
grows it even though ``StockRiskConfig`` inherits the ``margin_gate`` block.

Configuration: ``config/risk.yaml`` ``risk.margin_gate`` (``enabled`` default
``false`` + ``mode`` default ``shadow`` + ``latest_key`` + ``stale_max_age_seconds``).
No thresholds are hardcoded — the ``risk_level`` decision is made on the publish
side and merely consumed here.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.futures_margin import RISK_LEVELS
from shared.risk.state import RiskStateSnapshot

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

#: The filter-config mode value that arms enforcement. Anything else (default
#: ``shadow``) fails open — the margin publisher itself carries no ``mode``
#: field, so enforcement is a deliberate filter-side config decision.
_ENFORCE_MODE = "enforce"

#: Published risk levels that reject a NEW entry when armed. ``reduce_only`` is
#: intentionally excluded (passed as observation-only; see module docstring).
_BLOCKING_RISK_LEVELS: frozenset[str] = frozenset({"block_new_entries", "critical"})

#: Canonical set of publisher-known levels (from the publish-side SoT). Any
#: value outside this set is unknown → fail open rather than guess severity.
_KNOWN_RISK_LEVELS: frozenset[str] = frozenset(RISK_LEVELS)


def _validate_blocking_subset() -> None:
    """Fail loudly at import if a blocking level is no longer a published level.

    ``_BLOCKING_RISK_LEVELS`` is a hand-picked subset of the publish-side SoT
    (:data:`shared.risk.futures_margin.RISK_LEVELS`), while ``_KNOWN_RISK_LEVELS``
    auto-tracks that SoT. If the publisher ever renames a blocking level (e.g.
    ``critical`` → ``catastrophic``), the renamed string still lands in KNOWN but
    the stale literal here would fall out of the SoT — a NEW entry carrying the
    renamed severity would then be *unknown* and fail OPEN, silently killing the
    gate (the recurring SoT-drift failure mode, memory #601/#533/#537).

    A plain ``assert`` would be stripped under ``python -O``, so this raises
    explicitly at module load. The regression test ``test_blocking_levels_
    subset_of_sot`` pins the same invariant.
    """
    orphaned = _BLOCKING_RISK_LEVELS - _KNOWN_RISK_LEVELS
    if orphaned:
        raise RuntimeError(
            "margin_gate blocking levels not in publisher SoT RISK_LEVELS: "
            f"{sorted(orphaned)} (RISK_LEVELS={list(RISK_LEVELS)}). A publish-side "
            "risk_level rename dropped a blocking level — update "
            "_BLOCKING_RISK_LEVELS to match shared.risk.futures_margin.RISK_LEVELS."
        )


_validate_blocking_subset()


def _default_snapshot_provider(
    latest_key: str,
) -> Callable[[], Mapping[str, str] | None]:
    """Lazy sync-Redis reader for the ``futures:risk:latest`` hash.

    ``RiskFilterLayer.evaluate`` is synchronous, so the filter keeps its own
    sync client (identical pattern to :class:`PortfolioMddFilter`). The client
    is created on first use and reused afterwards. This is the *production*
    wiring; the read is against an EXISTING key (created by the publisher) —
    the filter never writes any Redis key of its own.
    """
    client: Any = None

    def _read() -> Mapping[str, str] | None:
        nonlocal client
        if client is None:
            import redis as redis_lib

            from shared.config.runtime_defaults import redis_url_from_env

            client = redis_lib.Redis.from_url(
                redis_url_from_env(), decode_responses=True
            )
        raw = client.hgetall(latest_key)
        if not raw:
            return None
        return {str(key): str(value) for key, value in dict(raw).items()}

    return _read


class MarginGateFilter(RiskFilter):
    """Gate new futures entries on the published margin ``risk_level``.

    Args:
        mode: Filter enforcement mode. Only ``"enforce"`` arms rejection; any
            other value (default ``"shadow"``) fails open on every signal. The
            margin publisher carries no ``mode`` field of its own, so this is a
            filter-side config decision (operator flip in P5).
        latest_key: Redis hash key published by ``services/futures_margin_risk``.
        stale_max_age_seconds: Fail-open when the snapshot ``asof_ts`` is older
            than this (KST-naive comparison, positive-form).
        snapshot_provider: Zero-arg callable returning the decoded hash (or
            ``None``). Defaults to a lazy sync-Redis reader; inject in tests.
        now_provider: KST-naive clock override for staleness tests.
    """

    name = "margin_gate"

    def __init__(
        self,
        *,
        mode: str,
        latest_key: str,
        stale_max_age_seconds: int,
        snapshot_provider: Callable[[], Mapping[str, str] | None] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.mode: str = str(mode or "").strip().lower()
        self.latest_key: str = latest_key
        self.stale_max_age_seconds: int = stale_max_age_seconds
        self._snapshot_provider = snapshot_provider or _default_snapshot_provider(
            latest_key
        )
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
        # Not armed → observation-only, never touches the snapshot.
        if self.mode != _ENFORCE_MODE:
            return self._pass()

        snapshot = self._read_snapshot()
        if snapshot is None:
            # Dormant publisher / Redis error / corrupt snapshot → fail open.
            return self._pass()

        if self._is_stale(snapshot.get("asof_ts")):
            return self._pass()

        risk_level = str(snapshot.get("risk_level", "")).strip().lower()
        if risk_level not in _KNOWN_RISK_LEVELS:
            # Unknown/absent level — fail open rather than guess severity.
            logger.warning(
                "margin_gate: unknown risk_level %r; failing open", risk_level
            )
            return self._pass()

        if risk_level in _BLOCKING_RISK_LEVELS:
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason=f"margin_gate_{risk_level}",
            )

        # ok / watch / reduce_only → pass (reduce_only is observation-only here).
        return self._pass()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _pass(self) -> FilterResult:
        return FilterResult(passed=True, filter_name=self.name)

    def _read_snapshot(self) -> dict[str, str] | None:
        """Read + normalize the snapshot, failing OPEN on any error.

        The entire provider contact surface — the call, the ``Mapping`` type
        check, and every key/value ``str`` coercion — lives inside one fail-open
        guard. A corrupt return therefore can never raise out of :meth:`check`
        into the guardless ``RiskFilterLayer.evaluate`` → daemon path (which
        would fail *closed*: the poison message is never XACK'd and the pipeline
        stalls) — the opposite of this filter's fail-open intent.

        Returns a plain ``{str: str}`` dict, or ``None`` (⇒ pass) when the
        provider raises, returns ``None``, or returns a non-``Mapping``.

        Byte-string values are NOT decoded: the production reader uses
        ``decode_responses=True`` so the hash is always ``{str: str}``. A raw
        ``bytes`` client is unsupported — its keys/values ``str()``-coerce to
        ``"b'...'"`` reprs, so ``asof_ts``/``risk_level`` miss their lookups and
        the signal fails OPEN (stale/unknown path), never a spurious block. Pinned
        by ``test_bytes_snapshot_fails_open``.
        """
        try:
            raw = self._snapshot_provider()
            if raw is None:
                return None
            if not isinstance(raw, Mapping):
                logger.warning(
                    "margin_gate provider returned %s, not a mapping; failing open",
                    type(raw).__name__,
                )
                return None
            return {str(key): str(value) for key, value in raw.items()}
        except Exception as exc:  # noqa: BLE001 — fail-open on any read/coerce error
            logger.warning("margin_gate snapshot read failed: %s", exc)
            return None

    def _is_stale(self, asof_raw: str | None) -> bool:
        """True when asof_ts is missing/unparseable/too old (→ fail open).

        Positive-form staleness (memory #458): a missing or malformed timestamp
        is treated as stale (→ pass), never as fresh, so a "NaN-clean" snapshot
        can't be mistaken for a live block signal.
        """
        if not asof_raw:
            return True
        try:
            asof = datetime.fromisoformat(str(asof_raw))
        except ValueError:
            logger.warning("margin_gate: unparseable asof_ts %r", asof_raw)
            return True
        if asof.tzinfo is not None:
            asof = asof.astimezone(KST).replace(tzinfo=None)
        age = (self._now_provider() - asof).total_seconds()
        return age > self.stale_max_age_seconds
