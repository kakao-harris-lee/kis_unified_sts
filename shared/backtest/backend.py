"""Backtest backend resolution and dispatch — ``config/backtest.yaml``.

Extracted from ``experiment_runner.py``'s per-symbol backend seam (plan
2026-09-07 §1-B/C, ``docs/plans/2026-09-07-vectorbt-default-flip.md``) so
``experiment_runner`` and ``optimizer`` share one resolution + fallback
implementation instead of the optimizer bypassing the seam entirely (it used
to construct :class:`~shared.backtest.engine.BacktestEngine` directly).

Two independent concerns live here:

1. ``load_default_engine`` — reads the *process-wide* default engine from
   ``config/backtest.yaml`` (env-overridable via ``BACKTEST_DEFAULT_ENGINE``).
   A missing file, a parse failure, or an unrecognized value all fall back to
   ``"legacy"`` WITH a warning — config absence must never silently flip the
   default to vectorbt.
2. ``resolve_backend`` / ``run_with_backend`` — the per-strategy resolution
   (engine key + ``legacy_exit`` escape hatch) and the actual dispatch
   (attempt vectorbt, fall back to legacy on refusal), moved verbatim from
   ``experiment_runner._run_registry_strategy``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

from shared.backtest.config import BacktestConfig
from shared.backtest.result import BacktestResult
from shared.utils.coercion import to_bool

logger = logging.getLogger(__name__)

EngineName = Literal["legacy", "vectorbt"]
# Report-label vocabulary — distinct from EngineName ("legacy" only ever
# appears as a *resolution* value; a completed legacy-engine run is reported
# as "backtest_engine", matching the pre-existing experiment_runner schema
# (coverage[symbol]["engine"], summary["engine"], dashboard consumers) that
# this module must not relabel.
RanEngine = Literal["backtest_engine", "vectorbt"]

_CONFIG_FILE = "backtest.yaml"
_CONFIG_SECTION = "backtest"
_SAFE_DEFAULT: EngineName = "legacy"
_VALID_ENGINES = ("legacy", "vectorbt")

# In-process dedup state for run_with_backend's fallback logging (review
# fix, 2026-09-07): a statically-refused strategy (NotImplementedError from
# VectorbtRunner._ensure_supported — e.g. a daily strategy, or an exit not on
# the allowlist) refuses identically for every symbol/trial. Logging that at
# WARNING per symbol buries genuine ImportError/VectorbtParityError signal.
# `_refusal_seen` dedupes NotImplementedError INFO logs per (experiment,
# strategy) pair (never per symbol/trial); `_import_error_warned` dedupes the
# "vectorbt not importable" WARNING once per process (a process-wide
# condition, not a per-strategy one). Best-effort, not lock-guarded — a race
# can double-log at most once, which is harmless.
_refusal_seen: set[str] = set()
_import_error_warned: bool = False


def reset_dedupe_state_for_tests() -> None:
    """Clear the in-process fallback-log dedup state.

    Test-only: the dedup sets are module-level (correct for a long-running
    process — logging once per experiment, not once per pytest session), so
    tests asserting first-occurrence-vs-repeat behavior must reset between
    cases.
    """
    global _import_error_warned
    _refusal_seen.clear()
    _import_error_warned = False


class BacktestBackendConfig(BaseModel):
    """``config/backtest.yaml::backtest`` — 실험/최적화 경로의 기본 엔진."""

    default_engine: str = Field(default=_SAFE_DEFAULT)


def load_default_engine() -> EngineName:
    """``config/backtest.yaml`` 에서 기본 백테스트 엔진을 읽는다.

    파일 부재/파싱 실패/스키마 위반/미지원 값은 전부 ``"legacy"`` 로 안전
    폴백하되 반드시 경고한다 — 설정 부재가 조용히 vectorbt 로 뒤집히면
    안 된다는 것이 운영자 지침이다. 롤백은 ``BACKTEST_DEFAULT_ENGINE=legacy``
    (YAML 의 ``${VAR:default}`` 치환이 처리한다).

    ``use_cache=False`` — 의도적. 이 YAML 은 한 줄짜리라 매 호출 재파싱
    비용이 무시할 만하고, 캐시를 켜면 ``ConfigLoader`` 의 프로세스 전역 캐시가
    프로세스 수명 동안 최초 읽은 env 값에 값을 고정해버려 테스트마다
    ``BACKTEST_DEFAULT_ENGINE`` 을 바꿔도 반영되지 않는다(호출자가
    ``ConfigLoader.clear_cache()`` 를 기억해야 하는 함정을 없앤다).
    """
    from shared.config.loader import ConfigError, ConfigLoader

    try:
        raw = ConfigLoader.load(_CONFIG_FILE, use_cache=False)
    except ConfigError as exc:
        logger.warning(
            "%s not found/invalid (%s) — defaulting backtest engine to %r",
            _CONFIG_FILE,
            exc,
            _SAFE_DEFAULT,
        )
        return _SAFE_DEFAULT

    section = raw.get(_CONFIG_SECTION, {}) if isinstance(raw, dict) else {}
    try:
        cfg = BacktestBackendConfig.model_validate(section or {})
    except Exception as exc:  # noqa: BLE001 - defensive, mirrors ConfigError path
        logger.warning(
            "%s::%s invalid (%s) — defaulting backtest engine to %r",
            _CONFIG_FILE,
            _CONFIG_SECTION,
            exc,
            _SAFE_DEFAULT,
        )
        return _SAFE_DEFAULT

    value = cfg.default_engine.strip().lower()
    if value not in _VALID_ENGINES:
        logger.warning(
            "%s::%s.default_engine unknown value %r — defaulting to %r "
            "(valid: legacy | vectorbt)",
            _CONFIG_FILE,
            _CONFIG_SECTION,
            cfg.default_engine,
            _SAFE_DEFAULT,
        )
        return _SAFE_DEFAULT
    return value  # type: ignore[return-value]


def resolve_backend(
    bt_cfg: Mapping[str, Any] | None,
    default: EngineName,
    *,
    context: str = "backtest",
) -> EngineName:
    """전략 ``backtest`` 블록 + 공정 기본값으로 엔진을 결정한다.

    ``experiment_runner._run_registry_strategy`` 의 구 인라인 로직(옛
    ``bt.get("engine", "") or "legacy"``)을 그대로 옮기되, 리터럴 ``"legacy"``
    자리를 호출자가 넘기는 ``default`` (보통 :func:`load_default_engine`)로
    대체했다 — 이것이 이번 flip 의 본질이다.

    Args:
        bt_cfg: 전략 YAML 의 ``strategy.backtest`` 블록 (없으면 빈 매핑 취급).
        default: 엔진 키가 비어 있을 때 쓸 기본값.
        context: 로그 메시지 접두사 (예: ``"experiment bb_reversion"``,
            ``"optimizer trial 3"``).

    Returns:
        ``"legacy"`` 또는 ``"vectorbt"``.
    """
    bt = bt_cfg or {}

    # 미지원 값은 typo("vbt" 등)가 조용히 legacy 로 굳어지지 않도록 경고 후
    # legacy 로 접는다 — unknown-engine 정책과 동일.
    engine_backend = str(bt.get("engine", "") or default).lower()
    if engine_backend not in _VALID_ENGINES:
        logger.warning(
            "%s: unknown backtest engine %r — using legacy "
            "(valid: legacy | vectorbt)",
            context,
            engine_backend,
        )
        engine_backend = "legacy"

    # Explicit legacy-exit escape hatch (plan 2026-07-08 §5 P3-c): a strategy
    # whose exit is a state machine the vectorbt runner cannot express (e.g.
    # three_stage's staged partial exits) sets `backtest.legacy_exit: true` to
    # force the legacy engine WITHOUT even attempting the runner. Coerced as a
    # tri-state; an unrecognized value is NOT silently honored.
    raw_legacy_exit = bt.get("legacy_exit", False)
    # 빈 키(`legacy_exit:` → None)는 "미설정"이다 — 경고 없이 False 취급.
    legacy_exit = False if raw_legacy_exit is None else to_bool(raw_legacy_exit)
    if legacy_exit is None:
        logger.warning(
            "%s: unrecognized backtest.legacy_exit %r — ignoring "
            "(expected true/false)",
            context,
            raw_legacy_exit,
        )
        legacy_exit = False
    if legacy_exit and engine_backend != "legacy":
        logger.info(
            "%s: backtest.legacy_exit=true — forcing legacy engine "
            "(state-machine exit); vectorbt runner not attempted",
            context,
        )
        engine_backend = "legacy"

    return engine_backend  # type: ignore[return-value]


@dataclass
class BackendRun:
    """One dispatch outcome — the result plus which engine actually ran.

    ``engine`` may differ from the requested backend (a vectorbt attempt that
    fell back to legacy) — callers must label reports with this field, not the
    requested backend, so a fallback is never mislabeled as intended.
    """

    result: BacktestResult
    engine: RanEngine


def run_with_backend(
    make_strategy: Callable[[], Any],
    config: BacktestConfig,
    data: pd.DataFrame,
    backend: EngineName,
    *,
    experiment_id: str = "",
    dedupe_key: str | None = None,
) -> BackendRun:
    """Run one backtest through ``backend``, falling back to legacy on refusal.

    ``make_strategy`` is called fresh for every attempt (zero-arg factory) —
    a mid-run vectorbt refusal leaves the previous adapter warm/dirty, so the
    legacy fallback must never reuse it (mirrors the moved-from code's
    ``_build_adapter`` contract).

    Fallback logging is split by cause (review fix, 2026-09-07): a
    ``NotImplementedError`` is an expected *static* refusal (the strategy/
    exit is structurally outside the runner's expressible range — e.g. a
    daily adapter or a non-allowlisted exit) that refuses identically for
    every symbol/trial of the same strategy, so it logs at INFO and only
    once per ``dedupe_key`` (never per symbol) — see
    :data:`_refusal_seen`. An ``ImportError`` (vectorbt not installed) is a
    process-wide condition and warns once per process. A
    ``VectorbtParityError`` is a real runner-defect signal and always warns,
    every occurrence — see the module docstring.

    Args:
        make_strategy: zero-arg factory returning a fresh strategy/adapter
            conforming to ``StrategyProtocol`` (``on_bar`` required).
        config: backtest config (capital, position sizing, risk, ...).
        data: OHLCV frame for a single symbol.
        backend: resolved backend, from :func:`resolve_backend`.
        experiment_id: log-message context (e.g. ``"experiment sid/symbol"``).
        dedupe_key: identifies the (experiment, strategy) pair for the
            NotImplementedError INFO dedup — must NOT vary per symbol/trial
            (e.g. ``f"{spec.id}:{sid}"``, not ``f"{sid}/{symbol}"``).
            Defaults to ``experiment_id`` when omitted, which only dedupes
            calls that pass an identical ``experiment_id`` verbatim.

    Returns:
        :class:`BackendRun` — result plus the engine that actually ran.
    """
    global _import_error_warned
    from shared.backtest.engine import BacktestEngine

    result: BacktestResult | None = None
    engine_used: RanEngine = "backtest_engine"

    if backend == "vectorbt":
        from shared.backtest.vbt_runner import VectorbtParityError, VectorbtRunner

        try:
            result = VectorbtRunner(make_strategy(), config).run(data)
            engine_used = "vectorbt"
        except NotImplementedError as unsupported:
            # 러너 표현범위 밖 — 정적으로 항상 같은 이유로 거부되는 정상
            # 폴백 경로(계약이 지원하는 유일한 "거부"). 심볼/시도마다 반복
            # 발화하면(예: daily 전략은 매 심볼 거부) WARNING 이 진짜 이상
            # 징후(ImportError/VectorbtParityError)를 파묻는다 — INFO 로
            # 낮추고 (experiment, strategy) 쌍마다 최초 1회만 찍는다.
            key = dedupe_key if dedupe_key is not None else experiment_id
            if key not in _refusal_seen:
                _refusal_seen.add(key)
                logger.info(
                    "%s: vectorbt runner refused (static, expected) — %s; "
                    "falling back to legacy engine (further refusals for "
                    "this strategy are logged at DEBUG)",
                    experiment_id,
                    unsupported,
                )
            else:
                logger.debug(
                    "%s: vectorbt runner refused (static, expected) — %s; "
                    "falling back to legacy engine",
                    experiment_id,
                    unsupported,
                )
        except ImportError as unsupported:
            # vectorbt 자체가 없는 환경 — 러너의 사전 가드(find_spec)가
            # 대부분 잡지만, 깨진 설치 등 늦게 터지는 케이스도 legacy 로
            # 폴백해야 한다. 전략/심볼과 무관한 프로세스 전역 조건이므로
            # 프로세스당 1회만 경고한다.
            if not _import_error_warned:
                _import_error_warned = True
                logger.warning(
                    "%s: vectorbt not installed/importable (%s); falling "
                    "back to legacy engine (further occurrences in this "
                    "process are logged at DEBUG)",
                    experiment_id,
                    unsupported,
                )
            else:
                logger.debug(
                    "%s: vectorbt not installed/importable (%s); falling "
                    "back to legacy engine",
                    experiment_id,
                    unsupported,
                )
        except VectorbtParityError as parity_err:
            # 러너 내부 cross-check(resolver 원장 ↔ vbt 원장) 불일치 — 러너
            # 결함 신호다. 결과를 버리면 등가중 집계가 조용히 왜곡되므로,
            # legacy 로 폴백해 결과를 보존하고 조사용 경고를 **매 발생마다**
            # 남긴다(디듀프하지 않는다 — 진짜 이상 징후이므로).
            logger.warning(
                "%s: vectorbt parity cross-check FAILED (%s); falling back "
                "to legacy engine — investigate vbt_runner",
                experiment_id,
                parity_err,
            )

    if result is None:
        result = BacktestEngine(make_strategy(), config).run(data)
        engine_used = "backtest_engine"

    return BackendRun(result=result, engine=engine_used)


__all__ = [
    "BacktestBackendConfig",
    "BackendRun",
    "EngineName",
    "RanEngine",
    "load_default_engine",
    "reset_dedupe_state_for_tests",
    "resolve_backend",
    "run_with_backend",
]
