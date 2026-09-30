"""Cross-process determinism of the tos canonical digest (plan §3, first two rows).

``PYTHONHASHSEED`` decides the iteration order of a ``set`` of strings, and the
canonical encoder treats a sequence as order-significant, so before 2026-09-24 a
``frozenset`` covered field gave a **different digest in every process**. Design
#2 §3.4 must-pass (A)-1 ("determinism: same covered content => same digest") is
exactly what that broke, and PR #797 met it as a paper render that could not read
its own activation back in a fresh process.

This file is the guard, and it lives **outside** ``tos/`` for two reasons that
both matter:

* ``subprocess`` is firewall-forbidden under ``tos/`` (``tools/
  tos_firewall_check.py`` TOS-FW-B), and only a real child process can carry a
  different ``PYTHONHASHSEED``: the variable is read at interpreter start-up, so
  ``monkeypatch.setenv`` inside the test process changes nothing.
* nothing outside ``tos/`` may ``import tos`` (TOS-FW-R), so this orchestrator
  cannot accidentally become its own oracle. It runs
  ``tests.canonical._set_order_worker`` (a module inside ``tos/``) once per seed
  and compares the JSON it prints.

The worker's map carries a **negative control** alongside the artifact digests: a
raw ``frozenset`` iteration order digested without a model. That one MUST differ
between seeds — if it does not, the seed sweep is not varying anything and the
"every digest is stable" assertion below would be green for the wrong reason.
"""

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

#: Six seeds — the plan's floor is five. With six mixed-length elements per set,
#: two processes drawing the same iteration order is ~1/6! per pair, so a
#: reverted hook cannot pass this by luck (review-798 1차 MEDIUM-2(a)).
_SEEDS: tuple[str, ...] = ("0", "1", "2", "3", "7", "11")

#: The negative control key produced by the worker.
_CONTROL_KEY = "CONTROL.raw_frozenset_order"

#: The 19 ``covered_content()`` models plus the two non-``covered_content()``
#: call shapes the worker measures. Asserted as a floor so adding a model is not
#: a spurious RED, while a worker that measured nothing still fails.
_MIN_MEASURED_KEYS = 21


def _run_worker(seed: str) -> dict[str, str]:
    """Run the kernel worker once under ``seed`` and return its digest map.

    Args:
        seed: The ``PYTHONHASHSEED`` value for the child interpreter.

    Returns:
        The child's digest map, parsed from its stdout.
    """
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
    """Negative control: a raw frozenset order must NOT be stable across seeds.

    If this is stable, ``PYTHONHASHSEED`` is not reaching the children and every
    other assertion in this file is vacuous.
    """
    control = {digests[_CONTROL_KEY] for digests in digests_by_seed.values()}
    assert len(control) > 1, (
        "the raw frozenset order digest is identical under every PYTHONHASHSEED "
        "— the seed is not reaching the worker, so this file proves nothing"
    )


def test_every_measured_digest_is_identical_across_seeds(
    digests_by_seed: dict[str, dict[str, str]],
) -> None:
    """The plan's core pin: the same covered content gives the same digest.

    RED without the ``CanonicalJsonMixin`` hook: eleven covered models plus
    ``event_identity`` and the runtime driver's payload digest split per seed
    (measured on ``origin/main`` ``153c8fd0``: six seeds, six different maps).
    """
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
