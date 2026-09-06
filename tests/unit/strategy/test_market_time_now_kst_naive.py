"""Tests for now_kst_naive (O11-④ shared KST-now helper)."""

from __future__ import annotations

from datetime import timedelta

from shared.strategy.market_time import now_kst, now_kst_naive


def test_now_kst_naive_strips_tzinfo():
    assert now_kst_naive().tzinfo is None


def test_now_kst_naive_matches_now_kst_within_tolerance():
    aware = now_kst()
    naive = now_kst_naive()
    assert naive == aware.replace(tzinfo=None) or abs(
        naive - aware.replace(tzinfo=None)
    ) < timedelta(seconds=1)
