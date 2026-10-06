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
    report PASS unconditionally under that flag. The one remaining ``assert``
    narrows ``spec``/``spec.loader`` for type checkers immediately after
    :func:`require` has already decided the same condition, so stripping it
    changes no verdict.
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
# `--norc --noprofile`: this host's /etc/bash.bashrc runs even for a
# non-interactive `bash -c` and trips over `set -u` (`PS1: unbound
# variable`). A wiring gate must not depend on, or be polluted by, the
# host's shell startup files.
_BASH = ("bash", "--norc", "--noprofile")
_PRINT_PATH = '\nprintf "%s" "$PROJECTION_PATH"'


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


def _wrapper_abort(shell: str) -> str:
    """The wrapper's own ``abort()`` definition, or a loud failure."""
    match = _ABORT_DEFINITION.search(shell)
    require(
        match is not None,
        "tos-paper-session.sh defines no abort() — the absolute-path guard "
        "calls it, and under the wrapper's `set -u` (no `-e`) a missing "
        "abort would let a relative projection path through",
    )
    assert match is not None  # narrowing for type checkers; require decided it
    definition = match.group(0)
    require(
        "exit " in definition,
        f"abort() does not exit: {definition!r}",
    )
    return definition + "\n"


def check(source: Path) -> None:
    shell = (source / "tos-paper-session.sh").read_text()
    subprocess.run([*_BASH, "-n", str(source / "tos-paper-session.sh")], check=True)
    # Execute only the path-selection block, never the operational wrapper.
    block = _path_selection_block(shell)
    require(
        re.search(r"\babort\b", block) is not None,
        "the extracted path-selection block never calls abort — the "
        "absolute-path guard is gone or moved outside the slice",
    )
    preamble = _HELPER_STUBS + _wrapper_abort(shell)
    subprocess.run([*_BASH, "-n", "-c", preamble + block], check=True)
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

    spec = importlib.util.spec_from_file_location(
        "staged_paper_driver", source / "tos_paper_session.py"
    )
    require(spec and spec.loader, "could not load the staged driver module")
    assert spec is not None and spec.loader is not None  # narrowing for type checkers
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
        "own abort(); driver argv with/without projection; no runtime launched"
    )


if __name__ == "__main__":
    try:
        check(Path(sys.argv[1]).resolve())
    except CheckFailed as failure:
        print(f"FAIL: {failure}", file=sys.stderr)
        raise SystemExit(1) from failure
