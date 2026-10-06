#!/usr/bin/env python3
"""Hermetic argv checks for a staged host wrapper/driver (never starts TOS).

Usage: python scripts/tos/check_paper_projection_wiring.py /path/to/staged/scripts
The caller must apply docs/runbooks/patches/tos-paper-projection.patch first.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


class CheckFailed(Exception):
    """A wiring check did not hold.

    A real exception, never ``assert``: this script is a gate, and ``python -O``
    strips every ``assert`` in it — the old bare asserts made the whole gate
    report PASS unconditionally under that flag.
    """


def require(condition: object, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


_BLOCK_START = "# Test/override sessions"
# The first line AFTER the path-selection block. The extraction must stop here:
# everything past it is the operational wrapper (it starts the runtime), and
# this script feeds the extracted text to `bash -eu -c`.
_BLOCK_END = "GENESIS=no"


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


# `abort` is defined by the wrapper itself; the extracted slice does not carry
# that definition, so the harness supplies a stub. Without it the guard's own
# `case` arm would die with "abort: command not found" (exit 127) and the
# check could not tell a working guard from a broken one.
_ABORT_STUB = 'abort() { printf "ABORT: %s\n" "$*" >&2; exit 9; }\n'


def check(source: Path) -> None:
    shell = (source / "tos-paper-session.sh").read_text()
    subprocess.run(["bash", "-n", str(source / "tos-paper-session.sh")], check=True)
    # Execute only the path-selection block, never the operational wrapper.
    block = _path_selection_block(shell)
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
            [
                "bash",
                "-eu",
                "-c",
                _ABORT_STUB + block + '\nprintf "%s" "$PROJECTION_PATH"',
            ],
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
    # PROJECTION_PATH with no override left to rewrite it must abort.
    relative = subprocess.run(
        [
            "bash",
            "-eu",
            "-c",
            _ABORT_STUB + block + '\nprintf "%s" "$PROJECTION_PATH"',
        ],
        env={
            "PATH": os.defpath,
            "SELFTEST": "0",
            "SESSION_DIR": "/scratch session",
            "PROJECTION_PATH": "relative/operator_projection.json",
        },
        capture_output=True,
        text=True,
    )
    require(
        relative.returncode == 9,
        f"relative projection path was accepted (exit {relative.returncode}, "
        f"stdout {relative.stdout!r})",
    )
    require(
        "projection path must be absolute" in relative.stderr,
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
        "PASS: 7 wrapper path cases + relative-path abort; "
        "driver argv with/without projection; no runtime launched"
    )


if __name__ == "__main__":
    try:
        check(Path(sys.argv[1]).resolve())
    except CheckFailed as failure:
        print(f"FAIL: {failure}", file=sys.stderr)
        raise SystemExit(1) from failure
