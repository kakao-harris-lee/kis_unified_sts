"""shared.determinism — dependency-light determinism commons.

Pure mechanisms that guarantee deterministic, look-ahead-safe replay of
historical data. Extracted from ``shared.backtest`` so that any deterministic
harness (backtest, replay, verification) can reuse them without pulling in
execution/storage/streaming/LLM/backtest-orchestration dependencies.

Public API:
    - :class:`LookaheadGuard`, :class:`LookaheadGuardMode` — look-ahead-bias
      enforcement.
    - :func:`ensure_kst`, :func:`session_date`, :func:`build_session_index`,
      :func:`build_prev_session_close`, :class:`SessionIndex`, ``KST``,
      ``DEFAULT_WARMUP_BARS`` — deterministic replay primitives.
"""

from __future__ import annotations

from shared.determinism.lookahead_guard import (
    LookaheadGuard,
    LookaheadGuardMode,
)
from shared.determinism.replay import (
    DEFAULT_WARMUP_BARS,
    KST,
    SessionIndex,
    build_prev_session_close,
    build_session_index,
    ensure_kst,
    session_date,
)

__all__ = [
    # Look-ahead guard
    "LookaheadGuard",
    "LookaheadGuardMode",
    # Replay primitives
    "DEFAULT_WARMUP_BARS",
    "KST",
    "SessionIndex",
    "build_prev_session_close",
    "build_session_index",
    "ensure_kst",
    "session_date",
]
