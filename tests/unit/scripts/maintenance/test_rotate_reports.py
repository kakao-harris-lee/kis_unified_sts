"""Unit tests for scripts/maintenance/rotate_reports.py.

Test coverage
-------------
1. ``_apply_policy`` is a no-op on missing directory.
2. Files newer than ``gzip_after_days`` are untouched.
3. Files older than ``gzip_after_days`` are gzipped (apply mode).
4. Dry-run mode records intent but does not mutate disk.
5. Already-gzipped files older than ``delete_after_days`` are deleted
   (when policy has a delete cutoff).
6. Policy with ``delete_after_days=None`` never deletes.
7. Existing target ``.gz`` is handled (original removed; no overwrite).
8. Glob honours ``file_pattern`` (drills uses ``*``, others ``*.json``).
"""

from __future__ import annotations

import gzip
import time
from pathlib import Path

import scripts.maintenance.rotate_reports as _mod
from scripts.maintenance.rotate_reports import (
    RotationPolicy,
    _apply_policy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _touch(path: Path, age_days: float, content: bytes = b'{"x":1}') -> None:
    """Create a file and backdate its mtime."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    mtime = time.time() - age_days * 86_400
    import os as _os

    _os.utime(path, (mtime, mtime))


def _policy(
    dir_path: Path,
    *,
    gzip_after: int = 30,
    delete_after: int | None = 730,
    pattern: str = "*.json",
) -> RotationPolicy:
    return RotationPolicy(
        name="test",
        directory=dir_path,
        gzip_after_days=gzip_after,
        delete_after_days=delete_after,
        file_pattern=pattern,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestApplyPolicy:
    def test_missing_directory_is_noop(self, tmp_path: Path):
        policy = _policy(tmp_path / "does_not_exist")
        stats = _apply_policy(policy, apply=True, now=time.time())
        assert stats.gzipped == 0
        assert stats.deleted == 0
        assert stats.errors == 0

    def test_recent_file_untouched(self, tmp_path: Path):
        f = tmp_path / "report.json"
        _touch(f, age_days=5)
        policy = _policy(tmp_path)
        stats = _apply_policy(policy, apply=True, now=time.time())
        assert stats.gzipped == 0
        assert f.exists()
        assert not f.with_suffix(".json.gz").exists()

    def test_old_file_gzipped(self, tmp_path: Path):
        f = tmp_path / "report.json"
        _touch(f, age_days=60, content=b'{"hello":"world"}' * 100)
        policy = _policy(tmp_path, gzip_after=30)
        stats = _apply_policy(policy, apply=True, now=time.time())
        assert stats.gzipped == 1
        assert not f.exists()
        gz = f.with_suffix(".json.gz")
        assert gz.exists()
        # Round-trip the content
        with gzip.open(gz, "rb") as g:
            assert g.read() == b'{"hello":"world"}' * 100

    def test_dry_run_records_intent_no_mutation(self, tmp_path: Path):
        f = tmp_path / "report.json"
        _touch(f, age_days=60)
        policy = _policy(tmp_path, gzip_after=30)
        stats = _apply_policy(policy, apply=False, now=time.time())
        assert stats.gzipped == 1  # would-have count
        assert f.exists()  # still on disk
        assert not f.with_suffix(".json.gz").exists()

    def test_old_gzipped_file_deleted_after_retention(self, tmp_path: Path):
        gz = tmp_path / "report.json.gz"
        _touch(gz, age_days=800)
        policy = _policy(tmp_path, gzip_after=30, delete_after=730)
        stats = _apply_policy(policy, apply=True, now=time.time())
        assert stats.deleted == 1
        assert not gz.exists()

    def test_old_gzipped_file_kept_when_delete_after_is_none(self, tmp_path: Path):
        gz = tmp_path / "drill.txt.gz"
        _touch(gz, age_days=2000)
        policy = _policy(
            tmp_path, gzip_after=90, delete_after=None, pattern="*"
        )
        stats = _apply_policy(policy, apply=True, now=time.time())
        assert stats.deleted == 0
        assert gz.exists()

    def test_existing_target_gz_does_not_overwrite(self, tmp_path: Path):
        original = tmp_path / "report.json"
        _touch(original, age_days=60, content=b'{"new":1}')
        existing_gz = tmp_path / "report.json.gz"
        # Pre-write a gz with different content
        with gzip.open(existing_gz, "wb") as g:
            g.write(b'{"old":1}')
        policy = _policy(tmp_path, gzip_after=30)
        stats = _apply_policy(policy, apply=True, now=time.time())
        # Original should be removed (we didn't double-gzip)
        assert not original.exists()
        # Existing gz preserved (NOT overwritten with the new payload)
        with gzip.open(existing_gz, "rb") as g:
            assert g.read() == b'{"old":1}'
        # Counter still incremented
        assert stats.gzipped == 1

    def test_pattern_glob_filters_files(self, tmp_path: Path):
        json_file = tmp_path / "report.json"
        txt_file = tmp_path / "log.txt"
        _touch(json_file, age_days=60)
        _touch(txt_file, age_days=60)
        # Default pattern is *.json — only json should be touched
        policy = _policy(tmp_path, gzip_after=30, pattern="*.json")
        stats = _apply_policy(policy, apply=True, now=time.time())
        assert stats.gzipped == 1
        assert not json_file.exists()
        assert txt_file.exists()  # txt untouched


class TestPolicyBuilder:
    def test_build_three_policies(self):
        import argparse

        args = argparse.Namespace(
            daily_verification_gzip_days=30,
            daily_verification_delete_days=730,
            counterfactual_gzip_days=365,
            counterfactual_delete_days=1825,
            drills_gzip_days=90,
        )
        policies = _mod._build_policies(args)
        names = [p.name for p in policies]
        assert names == ["daily_verification", "counterfactual", "drills"]

        drills = next(p for p in policies if p.name == "drills")
        assert drills.delete_after_days is None
        assert drills.file_pattern == "*"

        counterfactual = next(p for p in policies if p.name == "counterfactual")
        assert counterfactual.delete_after_days == 1825
        assert counterfactual.gzip_after_days == 365
