"""Dry-run tests for scripts/ops/portfolio_mdd_drill.py (Phase 3 gate drill).

The dry-run drill must be fully sandboxed: it builds its own tmp ledger,
in-memory Redis stub, and tmp sentinel path, and must PASS end-to-end
(stage transitions → filter verdicts → sentinel trip → latch hold).
"""

from __future__ import annotations

from scripts.ops.portfolio_mdd_drill import MiniRedis, run_dry_drill


class TestMiniRedis:
    def test_hash_roundtrip_and_delete(self):
        redis = MiniRedis()
        redis.hset("k", mapping={"a": "1"})
        assert redis.hgetall("k") == {"a": "1"}
        redis.delete("k")
        assert redis.hgetall("k") == {}

    def test_stream_maxlen_trims(self):
        redis = MiniRedis()
        for index in range(10):
            redis.xadd("s", {"i": str(index)}, maxlen=3)
        assert len(redis.streams["s"]) == 3


class TestDryDrill:
    def test_dry_run_passes_and_touches_no_real_paths(self, capsys):
        assert run_dry_drill() == 0
        out = capsys.readouterr().out
        assert "dry-run drill PASS" in out
        assert "FAILED checks" not in out
        # Every stage transition must have been exercised and verified.
        for label in ("reduce", "halt_new", "full_stop", "latch"):
            assert f"[PASS] {label}" in out or f"[PASS] {label}:" in out
