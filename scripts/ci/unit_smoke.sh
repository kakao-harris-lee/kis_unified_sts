#!/usr/bin/env bash
# Unit smoke for the two clone-and-go entry points, shared by both jobs of
# .github/workflows/devcontainer.yml (the Docker test profile and the Dev
# Container) so the two cannot drift apart.
#
# Mirrors test.yml's shape — parallel (non-serial) pass, then serial pass — over
# tests/unit only. Full parity is test.yml's job, not this one's.
set -euo pipefail

PYTEST_FLAGS=(--timeout=180 --timeout-method=thread -q)

# Pass 1: everything NOT marked `serial`, under pytest-xdist.
pytest tests/unit -n auto -m 'not serial' "${PYTEST_FLAGS[@]}"

# Pass 2: the `serial`-marked tests, which pass 1 excluded. Keeping this pass is
# what makes the two-pass split a partition of tests/unit: without it a
# `serial`-marked test added under tests/unit would be excluded by pass 1 and
# run nowhere.
#
# tests/unit may legitimately hold NO serial test, and today it holds none: the
# marker is for timing-/shared-external-state-sensitive tests, and the last one
# under tests/unit (tests/unit/kis/test_rate_limiter.py) was deleted with
# shared/execution/rate_limiter.py in 714cdffd (S3, 2026-11-13). pytest then
# exits 5, "no tests collected", which turned BOTH jobs of this workflow red
# from the next weekly backstop run onwards (#1097, run 44000964731 — both jobs
# failed with exit code 5, neither with a test failure).
#
# So exit 5 here means the serial partition is empty, not broken. Every other
# non-zero exit still fails the job, including 1 (a real failure), 2 (a
# collection error) and 4 (a usage error).
rc=0
pytest tests/unit -m serial "${PYTEST_FLAGS[@]}" || rc=$?
if [ "$rc" -ne 0 ] && [ "$rc" -ne 5 ]; then
  exit "$rc"
fi
