"""The guard that keeps ``requires_repo_checkout`` from becoming a silent hole.

#835 fixed a red CI job by letting one test skip where the repository is absent. A skip is
cheap to add and expensive to notice, so the decision itself is pinned here: every row of
:func:`tests.support.git_env.repo_checkout_skip_reason`, and in particular the row that
must NOT skip — no repository, no marker — which is what a real gate looks like when its
checkout is broken.

These tests never touch git. They drive the pure functions directly, which is the only way
to reach the "git failed for some OTHER reason" branch without staging a broken git.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support import git_env

# ---------------------------------------------------------------------------
# repo_checkout_skip_reason — the skip decision itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("state", [git_env.NO_WORK_TREE, git_env.NO_GIT_CLI])
def test_no_repository_without_the_marker_does_not_skip(state: str) -> None:
    """THE regression test for #835's fix.

    The host ``test`` job, the Dev Container and a developer's laptop never set the marker.
    If git goes wrong there, the clone must fail loudly — a green skip would mean the
    byte-identical guard stopped guarding and nobody heard.
    """
    assert git_env.repo_checkout_skip_reason(state, None) is None
    assert git_env.repo_checkout_skip_reason(state, "") is None


@pytest.mark.parametrize("state", [git_env.NO_WORK_TREE, git_env.NO_GIT_CLI])
def test_no_repository_with_the_marker_skips_and_says_why(state: str) -> None:
    reason = git_env.repo_checkout_skip_reason(state, "1")
    assert reason is not None
    assert git_env.NO_GIT_METADATA_ENV in reason
    assert "#835" in reason


@pytest.mark.parametrize("marker", [None, "", "1"])
def test_a_real_checkout_never_skips_even_with_the_marker_set(
    marker: str | None,
) -> None:
    """The marker declares an INTENT, not an override: if a work tree is actually there —
    say someone bind-mounts the source over /app — the guard runs."""
    assert git_env.repo_checkout_skip_reason(git_env.CHECKOUT, marker) is None


# ---------------------------------------------------------------------------
# classify_git_probe — what each git answer means
# ---------------------------------------------------------------------------


def test_toplevel_equal_to_the_root_is_a_checkout(tmp_path: Path) -> None:
    state = git_env.classify_git_probe(tmp_path, 0, f"{tmp_path}\n".encode(), b"")
    assert state == git_env.CHECKOUT


def test_a_root_merely_nested_in_another_repository_is_not_a_checkout(
    tmp_path: Path,
) -> None:
    """``git rev-parse`` answers 0 for any directory under a work tree, but
    ``git clone <that directory>`` still fails — the exact rc 128 of #835. A probe that only
    looked at the exit status (``--is-inside-work-tree``) would call this a checkout."""
    nested = tmp_path / "nested"
    nested.mkdir()
    state = git_env.classify_git_probe(nested, 0, f"{tmp_path}\n".encode(), b"")
    assert state == git_env.NO_WORK_TREE


def test_not_a_git_repository_is_the_only_recognised_failure(tmp_path: Path) -> None:
    state = git_env.classify_git_probe(
        tmp_path,
        128,
        b"",
        b"fatal: not a git repository (or any of the parent directories): .git\n",
    )
    assert state == git_env.NO_WORK_TREE


def test_dubious_ownership_raises_instead_of_reading_as_no_repository(
    tmp_path: Path,
) -> None:
    """safe.directory was the hypothesis #835 disproved, but it is a real way for a probe to
    fail on a machine that HAS the repository. Reporting it as "no repository" would skip
    the guard on a real gate, so it raises."""
    with pytest.raises(RuntimeError, match="dubious ownership"):
        git_env.classify_git_probe(
            tmp_path,
            128,
            b"",
            b"fatal: detected dubious ownership in repository at '/app'\n",
        )


def test_an_unrecognised_failure_raises(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="exit 129"):
        git_env.classify_git_probe(tmp_path, 129, b"", b"usage: git rev-parse\n")


# ---------------------------------------------------------------------------
# The probe is lazy — it must not run at import time
# ---------------------------------------------------------------------------


def test_the_state_probe_is_cached_so_collection_forks_no_git(tmp_path: Path) -> None:
    git_env.repo_checkout_state.cache_clear()
    assert git_env.repo_checkout_state.cache_info().currsize == 0
    first = git_env.repo_checkout_state(tmp_path)
    second = git_env.repo_checkout_state(tmp_path)
    # tmp_path is never a work tree; without a git binary the probe says so differently.
    assert first == second
    assert first in {git_env.NO_WORK_TREE, git_env.NO_GIT_CLI}
    assert git_env.repo_checkout_state.cache_info().hits == 1
