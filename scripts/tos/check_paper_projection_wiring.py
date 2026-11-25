#!/usr/bin/env python3
"""Hermetic argv checks for a staged host wrapper/driver (never starts TOS).

Usage: python scripts/tos/check_paper_projection_wiring.py /path/to/staged/scripts
The caller must apply docs/runbooks/patches/tos-paper-projection.patch first.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


class CheckFailed(Exception):
    """A wiring check did not hold.

    A real exception, not ``assert``: this script is a gate, and ``python -O``
    strips every ``assert`` in it — the old bare asserts made the whole gate
    report PASS unconditionally under that flag. No ``assert`` remains: the
    four that narrowed a type for a checker (in :func:`_default_assignment`,
    :func:`_check_default_published_path`, :func:`_wrapper_abort` and
    :func:`check`) are now ``if ... raise CheckFailed`` instead, which both
    narrows and survives ``-O``. A new ``assert`` anywhere in this file would
    be a verdict that disappears under that flag, so checks belong in
    :func:`require` or in an explicit ``raise``.
    """


def require(condition: object, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


_BLOCK_START = "# Test/override sessions"
# The first line AFTER the path-selection block. The extraction must stop here:
# everything past it is the operational wrapper (it starts the runtime), and
# this script feeds the extracted text to `bash -eu -c`.
_BLOCK_END = "GENESIS=no"
# The wrapper's own abort() exits with this code. Pinned, not read from the
# wrapper: a silent change to the abort contract is itself a finding.
_WRAPPER_ABORT_EXIT = 2
# `--norc --noprofile`, plus a scrubbed `env=` on every invocation below:
# hermetic by construction. A gate's verdict must not depend on what the
# invoking environment arranges for new shells.
#
# Measured, so the reason here is not a guess:
#   $ env -i PATH=/usr/bin:/bin bash -eu -c 'printf ok'   # rc 0, stderr empty
#   /etc/bash.bashrc:7 is `[ -z "$PS1" ] && return`, and `bash -c` does not
#   source that file at all.
# So the earlier claim in this comment — that this host's bashrc runs for a
# non-interactive `bash -c` and trips `set -u` — was false. A gate run here
# did once print `PS1: unbound variable` seven times; it has not reproduced,
# and `BASH_ENV` (which bash *does* read for non-interactive shells) is unset
# in this environment, so that path is unconfirmed too. These flags close
# both without depending on either being the cause.
_BASH = ("bash", "--norc", "--noprofile")
_PRINT_PATH = '\nprintf "%s" "$PROJECTION_PATH"'
# The wrapper's own default for the published snapshot, as a single
# assignment line well above the selection block. Checked separately from
# the seven selection cases, which inject PROJECTION_PATH to isolate the
# selection logic and would therefore be overwritten by this assignment.
_DEFAULT_ASSIGNMENT = re.compile(
    r"^PROJECTION_PATH=\$\{TOS_PAPER_PROJECTION_PATH:-[^}\n]+\}$", re.MULTILINE
)
# Every assignment to PROJECTION_PATH in any syntax. The wrapper is allowed
# exactly two: this default, above the selection block, and the session-local
# override inside it. A third (or a second shape of the first) would mean the
# reassembled fragments below no longer model what the wrapper runs.
_ANY_PROJECTION_ASSIGNMENT = re.compile(r"^[ \t]*PROJECTION_PATH=", re.MULTILINE)
# The wrapper's per-session tree root, used to tell "published" from
# "session-local" by the wrapper's own value rather than an injected one.
_SESSIONS_ROOT = re.compile(r"^SESSIONS=(\S+)$", re.MULTILINE)
_PUBLISHED_BASENAME = "operator_projection.json"


def _path_selection_block(shell: str) -> str:
    """Slice out the path-selection block, or fail loudly.

    ``str.split`` is fail-open at both ends: a missing start sentinel yields
    the text unchanged and a missing end sentinel yields everything to EOF —
    either way the caller would hand the whole operational wrapper to ``bash``.
    So both sentinels are required to be present exactly once.
    """
    for sentinel in (_BLOCK_START, _BLOCK_END):
        found = shell.count(sentinel)
        require(
            found == 1,
            f"expected exactly one {sentinel!r} sentinel in tos-paper-session.sh, "
            f"found {found} — refusing to execute an unbounded slice of the wrapper",
        )
    after_start = shell.split(_BLOCK_START, 1)[1]
    require(
        _BLOCK_END in after_start,
        f"{_BLOCK_END!r} appears before {_BLOCK_START!r} — block boundaries "
        "are not in the expected order",
    )
    block = _BLOCK_START + after_start.split(_BLOCK_END, 1)[0]
    require(
        "--projection-path" not in block and "nohup" not in block,
        "extracted block reaches into the operational launch — refusing to run it",
    )
    return block


# `abort` is defined by the wrapper above the extracted slice. The harness
# takes the wrapper's REAL definition rather than substituting one: a stub
# would hide a wrapper that has no `abort` at all (the wrapper runs under
# `set -u` only, so a missing `abort` makes the guard's `case` arm stop
# nothing), and its exit code would be the harness's invention instead of the
# wrapper's contract.
_ABORT_DEFINITION = re.compile(r"^abort\(\)\s*\{.*?\}\s*$", re.DOTALL | re.MULTILINE)

# Only the wrapper's logging/notification helpers are substituted, never the
# guard or `abort` itself. `notify`'s argument is expanded before the call, so
# the variables the real `abort` interpolates must exist under `set -u`; a
# future `abort` that reaches for some other variable fails loudly here
# (unbound variable, exit 1) instead of silently.
_ABORT_CONTEXT = {"TAG": "[test] ", "TODAY": "2026-10-06", "LOG": "/dev/null"}
_HELPER_STUBS = "log() { printf '%s\\n' \"$*\" >&2; }\nnotify() { :; }\n"


def _default_assignment(shell: str, block: str) -> str:
    """The wrapper's own ``PROJECTION_PATH=...`` default, or a loud failure.

    This gate reassembles two fragments (this line plus the selection block)
    rather than running the wrapper's real prelude, so what makes that
    reassembly faithful has to be asserted, not assumed:

    * the default is **above** the selection block. Below it, the real
      wrapper would either die on an unbound variable or let a test session
      overwrite the published snapshot, and a reassembly would not notice.
    * no other line outside the block assigns ``PROJECTION_PATH`` in any
      syntax. Matching only the documented ``${VAR:-default}`` shape let a
      bare ``PROJECTION_PATH=/tmp/wrong.json`` sit beside it unseen.
    * the one line outside the block is that documented shape.
    """
    block_start = shell.index(_BLOCK_START)
    block_end = block_start + len(block)
    outside = [
        match
        for match in _ANY_PROJECTION_ASSIGNMENT.finditer(shell)
        if not block_start <= match.start() < block_end
    ]
    lines = [shell.count("\n", 0, match.start()) + 1 for match in outside]
    require(
        len(outside) == 1,
        f"expected exactly one PROJECTION_PATH assignment outside the selection "
        f"block, found {len(outside)} at lines {lines} — the published "
        f"snapshot's default must be the only one",
    )
    match = _DEFAULT_ASSIGNMENT.search(shell)
    if match is None:
        raise CheckFailed(
            "no PROJECTION_PATH=${TOS_PAPER_PROJECTION_PATH:-...} default found "
            "in tos-paper-session.sh — the published snapshot's default is what "
            "a session with no overrides writes to"
        )
    require(
        match.start() == outside[0].start(),
        f"the PROJECTION_PATH assignment outside the block is not the "
        f"documented ${{TOS_PAPER_PROJECTION_PATH:-...}} form: "
        f"{shell[outside[0].start():].splitlines()[0]!r}",
    )
    require(
        match.start() < block_start,
        f"the PROJECTION_PATH default is at offset {match.start()}, at or after "
        f"the selection block at {block_start} — a default below the block is "
        f"not what the wrapper runs, and this gate reassembles the two",
    )
    return match.group(0) + "\n"


def _check_default_published_path(shell: str, block: str, preamble: str) -> str:
    """The default the wrapper itself computes, with nothing injected.

    The seven selection cases all inject ``PROJECTION_PATH``, so none of them
    ever exercises the wrapper's own default constant — a default changed to a
    relative path, or to a session-local one, would pass every other case
    here. Properties are asserted, not the literal path: the deploy-host
    coordinate belongs to the runbook, and the gate's job is that the default
    is a usable published path and that the documented override still wins.
    """
    assignment = _default_assignment(shell, block)
    sessions_root = _SESSIONS_ROOT.search(shell)
    if sessions_root is None:
        raise CheckFailed(
            "no SESSIONS=<path> assignment found in tos-paper-session.sh — "
            "without the wrapper's own session root this check cannot tell a "
            "published default from a session-local one"
        )
    require(
        "$SESSION_DIR" not in assignment and "${SESSION_DIR" not in assignment,
        f"the PROJECTION_PATH default interpolates SESSION_DIR: {assignment!r}",
    )
    base_env = {"PATH": os.defpath, "SELFTEST": "0", "SESSION_DIR": "/scratch session"}
    script = preamble + assignment + block + _PRINT_PATH
    # `run`, not `check_output`: a non-absolute default makes the wrapper's own
    # guard abort, and a CalledProcessError traceback would report the gate as
    # broken instead of reporting the finding.
    completed = subprocess.run(
        [*_BASH, "-eu", "-c", script],
        env={**base_env, **_ABORT_CONTEXT},
        capture_output=True,
        text=True,
    )
    require(
        completed.returncode == 0,
        f"the wrapper's own default projection path does not survive its own "
        f"guard (exit {completed.returncode}"
        + (
            f" == abort; stderr {completed.stderr.strip()!r}"
            if completed.returncode == _WRAPPER_ABORT_EXIT
            else f"; stderr {completed.stderr.strip()!r}"
        )
        + ") — every unattended session would abort",
    )
    default = completed.stdout
    require(
        default.startswith("/"),
        f"the wrapper's default projection path is not absolute: {default!r} — "
        "the absolute-path guard would abort every unattended session",
    )
    require(
        default.endswith("/" + _PUBLISHED_BASENAME),
        f"the wrapper's default does not end in {_PUBLISHED_BASENAME!r}: {default!r}",
    )
    # Both roots: the one this harness injected, and — the one that matters —
    # the wrapper's own SESSIONS tree, so a default pointing at a literal
    # per-session path is caught too.
    for label, root in (
        ("the injected session dir", base_env["SESSION_DIR"]),
        ("the wrapper's SESSIONS tree", sessions_root.group(1)),
    ):
        require(
            not default.startswith(root.rstrip("/") + "/"),
            f"the wrapper's default is under {label} ({root}): {default!r} — an "
            "unattended session would never publish the operational snapshot",
        )

    override = "/scratch/override dir/" + _PUBLISHED_BASENAME
    overridden = subprocess.check_output(
        [*_BASH, "-eu", "-c", preamble + assignment + block + _PRINT_PATH],
        env={**base_env, "TOS_PAPER_PROJECTION_PATH": override},
        text=True,
    )
    require(
        overridden == override,
        f"TOS_PAPER_PROJECTION_PATH did not win: {overridden!r} != {override!r}",
    )
    return default


def _wrapper_abort(shell: str) -> str:
    """The wrapper's own ``abort()`` definition, or a loud failure."""
    match = _ABORT_DEFINITION.search(shell)
    if match is None:
        raise CheckFailed(
            "tos-paper-session.sh defines no abort() — the absolute-path guard "
            "calls it, and under the wrapper's `set -u` (no `-e`) a missing "
            "abort would let a relative projection path through"
        )
    definition = match.group(0)
    require(
        "exit " in definition,
        f"abort() does not exit: {definition!r}",
    )
    return definition + "\n"


def check(source: Path) -> None:
    shell = (source / "tos-paper-session.sh").read_text()
    # Scrubbed `env=` like every other invocation: a parse check that
    # inherits the parent's `BASH_ENV` is not hermetic either.
    subprocess.run(
        [*_BASH, "-n", str(source / "tos-paper-session.sh")],
        check=True,
        env={"PATH": os.defpath},
    )
    # Execute only the path-selection block, never the operational wrapper.
    block = _path_selection_block(shell)
    require(
        re.search(r"\babort\b", block) is not None,
        "the extracted path-selection block never calls abort — the "
        "absolute-path guard is gone or moved outside the slice",
    )
    preamble = _HELPER_STUBS + _wrapper_abort(shell)
    subprocess.run(
        [*_BASH, "-n", "-c", preamble + block],
        check=True,
        env={"PATH": os.defpath},
    )
    for override in (
        {},
        {"SELFTEST": "1"},
        {"TOS_PAPER_DATA_DIR": "/scratch"},
        {"TOS_PAPER_INSTRUMENT_OVERRIDE": "A05611"},
        {"TOS_PAPER_FAKE_DATE": "2026-10-09"},
        {"TOS_PAPER_WT": "/scratch-worktree"},
        {"TOS_PAPER_IGNORE_CALENDAR": "1"},
    ):
        env = {
            "PATH": os.defpath,
            "SELFTEST": "0",
            "SESSION_DIR": "/scratch session",
            "PROJECTION_PATH": "/published/operator_projection.json",
            **override,
        }
        result = subprocess.check_output(
            [*_BASH, "-eu", "-c", preamble + block + _PRINT_PATH],
            env=env,
            text=True,
        )
        expected = (
            "/scratch session/operator_projection.json"
            if override
            else "/published/operator_projection.json"
        )
        require(result == expected, f"path case {override}: {result!r} != {expected!r}")

    # The absolute-path guard: none of the seven cases above reaches it (each
    # ends on an absolute path), so it gets its own case. A relative
    # PROJECTION_PATH with no override left to rewrite it must abort, through
    # the wrapper's OWN abort — exit code and message are the wrapper's.
    relative = subprocess.run(
        [*_BASH, "-eu", "-c", preamble + block + _PRINT_PATH],
        env={
            "PATH": os.defpath,
            "SELFTEST": "0",
            "SESSION_DIR": "/scratch session",
            "PROJECTION_PATH": "relative/operator_projection.json",
            **_ABORT_CONTEXT,
        },
        capture_output=True,
        text=True,
    )
    require(
        relative.returncode == _WRAPPER_ABORT_EXIT,
        f"relative projection path did not reach the wrapper's abort "
        f"(exit {relative.returncode}, expected {_WRAPPER_ABORT_EXIT}, "
        f"stdout {relative.stdout!r}, stderr {relative.stderr!r})",
    )
    require(
        "ABORT" in relative.stderr
        and "projection path must be absolute" in relative.stderr,
        f"abort guard did not run: stderr {relative.stderr!r}",
    )

    # 노트 h: the wrapper's own default for the published snapshot.
    default_path = _check_default_published_path(shell, block, preamble)

    spec = importlib.util.spec_from_file_location(
        "staged_paper_driver", source / "tos_paper_session.py"
    )
    if spec is None or spec.loader is None:
        raise CheckFailed("could not load the staged driver module")
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)

    class CapturedLaunch(Exception):
        pass

    with tempfile.TemporaryDirectory(prefix="projection-wiring-") as temporary:
        root = Path(temporary)
        config = root / "config"
        config.mkdir()
        (config / "RENDERED.json").write_text(
            json.dumps({"instrument": "A05610", "journal_path": str(root / "journal")})
        )
        for projection in (None, str(root / "projection with spaces.json")):
            argv = ["driver"]
            for name, value in {
                "worktree": root,
                "main-repo": root,
                "config-dir": config,
                "data-dir": root / "data",
                "custody-root": root / "custody",
                "env-file": root / "unused.env",
                "session-dir": root / "session",
                "instrument": "A05610",
                "max-minutes": "1",
                "pidfile": root / "unused.pid",
            }.items():
                argv.extend(["--" + name, str(value)])
            if projection:
                argv.extend(["--projection-path", projection])

            def capture(command, expected_projection=projection, **kwargs):
                kwargs["stdout"].close()
                if expected_projection:
                    require(
                        command[-2:] == ["--projection-path", expected_projection],
                        f"driver argv tail {command[-2:]!r} lacks the projection path",
                    )
                else:
                    require(
                        "--projection-path" not in command,
                        "driver passed --projection-path when none was requested",
                    )
                raise CapturedLaunch

            with (
                patch.object(sys, "argv", argv),
                patch.object(driver.signal, "signal"),
                patch.object(
                    driver.subprocess, "check_output", return_value="test-sha"
                ),
                patch.object(
                    driver.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 0, "", ""),
                ),
                patch.object(driver.subprocess, "Popen", side_effect=capture),
            ):
                try:
                    driver.main()
                except CapturedLaunch:
                    pass
                else:
                    raise CheckFailed("driver never reached the captured launch")
    print(
        "PASS: 7 wrapper path cases + relative-path abort through the wrapper's "
        "own abort() + default published path "
        f"({default_path!r}, overridable); "
        "driver argv with/without projection; no runtime launched"
    )


if __name__ == "__main__":
    try:
        check(Path(sys.argv[1]).resolve())
    except CheckFailed as failure:
        print(f"FAIL: {failure}", file=sys.stderr)
        raise SystemExit(1) from failure
