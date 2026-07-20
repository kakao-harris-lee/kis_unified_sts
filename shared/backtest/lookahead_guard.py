"""Backward-compatible re-export of the look-ahead guard.

The implementation now lives in the dependency-light commons
:mod:`shared.determinism` (see the 2026-07-20 tos boundary / import-firewall
design, §3.4). This thin module keeps the historical import path
``shared.backtest.lookahead_guard`` working for existing backtest consumers.
"""

from __future__ import annotations

from shared.determinism.lookahead_guard import LookaheadGuard, LookaheadGuardMode

__all__ = ["LookaheadGuard", "LookaheadGuardMode"]
