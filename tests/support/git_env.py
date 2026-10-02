"""One answer, for the whole suite, to "can a test use git here?".

Two different questions used to be answered in two different places with two different
shapes (``shutil.which("git")`` in the firewall tests, an ad-hoc ``rev-parse`` probe in the
render-guard test). They are kept separate here on purpose, because they are genuinely
different questions, but each has exactly one implementation:

* :func:`git_cli_available` — is the ``git`` binary on PATH at all?
* :func:`repo_checkout_state` — is *this directory* the toplevel of a git work tree, i.e.
  something ``git clone <dir>`` can actually clone?

**The dangerous case is the third one.** A git probe can fail for reasons that are NOT
"there is no repository here" — dubious ownership (``safe.directory``), a leaked ``GIT_DIR``
or ``GIT_CEILING_DIRECTORIES``, a corrupt object store. Reporting those as "no repository"
would silently skip the guards that depend on a repository, which is the failure mode the
guard was written to prevent. So :func:`classify_git_probe` **raises** on anything it does
not positively recognise. This mirrors ``tools/tos_firewall_check.py::_git_toplevel_or_none``,
which made the same distinction for the same reason.
"""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
from pathlib import Path

#: Set by ``Dockerfile.test`` (and only there). It is a POSITIVE marker: "this environment
#: deliberately ships without git metadata, because `.dockerignore` excludes `.git`".
#:
#: A skip is allowed only where something declares the absence intentional. Without this
#: marker a missing work tree stays a loud failure — on the host `test` job, in the Dev
#: Container, on a developer's machine. That is the point: before #835 the clone failure was
#: loud everywhere, and a blanket "no repo -> skip" would have made it quiet everywhere.
NO_GIT_METADATA_ENV = "KIS_TEST_IMAGE_NO_GIT_METADATA"

#: ``_REPO_ROOT`` is the toplevel of a git work tree — ``git clone`` it.
CHECKOUT = "checkout"
#: There is genuinely no work tree here. Either no ``.git`` at all, or this directory is
#: merely NESTED inside some other repository (``--show-toplevel`` points elsewhere), which
#: ``git clone <dir>`` cannot clone either.
NO_WORK_TREE = "no-work-tree"
#: The ``git`` binary is not installed.
NO_GIT_CLI = "no-git-cli"


@functools.lru_cache(maxsize=1)
def git_cli_available() -> bool:
    """Is the ``git`` binary on PATH?

    Decorator-time safe: this is a plain cached function, so a module-level
    ``@pytest.mark.skipif(not git_cli_available(), ...)`` can call it. A pytest fixture
    could not be used there, which is why this stays a function and not a fixture.
    """
    return shutil.which("git") is not None


def classify_git_probe(
    root: Path, returncode: int, stdout: bytes, stderr: bytes
) -> str:
    """Turn one ``git rev-parse --show-toplevel`` result into a state. Pure.

    Split out from :func:`repo_checkout_state` so every branch — including the one that
    must RAISE — is reachable from a unit test without staging a broken git installation.

    Raises:
        RuntimeError: the probe failed for a reason other than "not a git repository".
            Dubious ownership lands here, deliberately: treating it as "no repository"
            would convert a misconfigured checkout into a silent skip.
    """
    if returncode == 0:
        toplevel = Path(os.fsdecode(stdout.strip())).resolve()
        # Not `!= root` but "is root itself the toplevel": a directory nested inside another
        # repository answers rc 0 while `git clone <that directory>` still fails.
        return CHECKOUT if toplevel == root.resolve() else NO_WORK_TREE
    text = stderr.decode("utf-8", errors="replace")
    if "not a git repository" in text:
        return NO_WORK_TREE
    raise RuntimeError(
        f"git rev-parse --show-toplevel failed unexpectedly in {root} (exit {returncode}). "
        "This is NOT a plain 'no repository here' answer — dubious ownership, a leaked "
        "GIT_DIR, or a corrupt repository look like this, and silently reading them as "
        f"'no repository' would skip guards that need one: {text.strip()}"
    )


@functools.cache
def repo_checkout_state(root: Path) -> str:
    """:data:`CHECKOUT`, :data:`NO_WORK_TREE` or :data:`NO_GIT_CLI` for ``root``.

    Cached per root and evaluated lazily — never at import time, so collecting an unrelated
    test does not fork a ``git`` process in the controller and in every xdist worker.
    """
    try:
        probe = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=False,
        )
    except OSError:  # FileNotFoundError, and a PATH entry that cannot be executed
        return NO_GIT_CLI
    return classify_git_probe(root, probe.returncode, probe.stdout, probe.stderr)


def repo_checkout_skip_reason(state: str, marker: str | None) -> str | None:
    """Why a clone-the-repo test must skip, or ``None`` if it must run. Pure.

    The marker is what keeps this from becoming a hole on the real gates. The three rows
    that matter:

    ===================  ========  ========================================================
    state                marker    result
    ===================  ========  ========================================================
    ``CHECKOUT``         any       ``None`` — a repository is right there; run it.
    not ``CHECKOUT``     unset     ``None`` — run it and let the clone fail LOUDLY. This is
                                   the host ``test`` job, the Dev Container, a laptop.
    not ``CHECKOUT``     set       a reason — only ``Dockerfile.test`` sets the marker.
    ===================  ========  ========================================================
    """
    if state == CHECKOUT:
        return None
    if not marker:
        return None
    detail = (
        "the git CLI is not installed"
        if state == NO_GIT_CLI
        else "the repository root is not a git work tree"
    )
    return (
        f"{detail}, and {NO_GIT_METADATA_ENV} declares that intentional. Only "
        "Dockerfile.test sets it: `.dockerignore` excludes `.git`, so /app is a plain "
        "directory and `git clone /app` exits 128 (#835). Everywhere else — the host "
        "`test` job above all — this test runs."
    )
