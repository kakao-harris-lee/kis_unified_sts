"""Cross-process determinism of the tos canonical digest (plan §3, first two rows)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOS_DIR = _REPO_ROOT / "tos"
_KERNEL_SRC = _TOS_DIR / "src"
_WORKER_MODULE = "tests.canonical._set_order_worker"

_SEEDS: tuple[str, ...] = ("0", "1", "2", "3", "7", "11")

_CONTROL_KEY = "CONTROL.raw_frozenset_order"

_MIN_MEASURED_KEYS = 7


def _run_worker(seed: str) -> dict[str, str]:
    """Run the kernel worker once under ``seed`` and return its digest map."""
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONPATH": str(_KERNEL_SRC),
        "PYTHONHASHSEED": seed,
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
    }
    proc = subprocess.run(
        [sys.executable, "-m", _WORKER_MODULE],
        cwd=str(_TOS_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"worker failed (seed={seed}): {proc.stderr}"
    parsed = json.loads(proc.stdout)
    assert isinstance(parsed, dict)
    return parsed


@pytest.fixture(scope="module")
def digests_by_seed() -> dict[str, dict[str, str]]:
    """One digest map per seed, measured once for the whole module."""
    return {seed: _run_worker(seed) for seed in _SEEDS}


def test_the_seed_sweep_actually_varies_the_hash_seed(
    digests_by_seed: dict[str, dict[str, str]],
) -> None:
    """Negative control: a raw frozenset order must NOT be stable across seeds."""
    control = {digests[_CONTROL_KEY] for digests in digests_by_seed.values()}
    assert len(control) > 1, (
        "the raw frozenset order digest is identical under every PYTHONHASHSEED "
        "— the seed is not reaching the worker, so this file proves nothing"
    )


def test_every_measured_digest_is_identical_across_seeds(
    digests_by_seed: dict[str, dict[str, str]],
) -> None:
    """The plan's core pin: the same covered content gives the same digest."""
    reference_seed = _SEEDS[0]
    reference = digests_by_seed[reference_seed]
    for seed, digests in digests_by_seed.items():
        if seed == reference_seed:
            continue
        differing = sorted(
            key
            for key in reference
            if key != _CONTROL_KEY and digests.get(key) != reference[key]
        )
        assert differing == [], (
            f"PYTHONHASHSEED={seed} produced different digests than "
            f"PYTHONHASHSEED={reference_seed} for: {differing}"
        )


def test_the_worker_measured_the_whole_surface(
    digests_by_seed: dict[str, dict[str, str]],
) -> None:
    """A worker that silently measured nothing must not read as determinism."""
    digests = digests_by_seed[_SEEDS[0]]
    measured = set(digests) - {_CONTROL_KEY}
    assert len(measured) >= _MIN_MEASURED_KEYS
    assert "EngineEvent.event_identity" in measured
    assert "EngineEvent.payload_digest" in measured
    assert "VenueConstraintPolicy" in measured
    for key, digest in digests.items():
        body = digest.split("-", 1)[1] if digest.startswith("event-") else digest
        assert len(body) == 64, f"{key} is not a sha256 digest: {digest!r}"
        assert set(body) <= set("0123456789abcdef"), key
