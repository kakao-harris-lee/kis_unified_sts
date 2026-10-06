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


def check(source: Path) -> None:
    shell = (source / "tos-paper-session.sh").read_text()
    subprocess.run(["bash", "-n", str(source / "tos-paper-session.sh")], check=True)
    # Execute only the path-selection block, never the operational wrapper.
    block = shell.split("# Test/override sessions", 1)[1].split("GENESIS=no", 1)[0]
    block = "# Test/override sessions" + block
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
            ["bash", "-eu", "-c", block + '\nprintf "%s" "$PROJECTION_PATH"'],
            env=env,
            text=True,
        )
        expected = (
            "/scratch session/operator_projection.json"
            if override
            else "/published/operator_projection.json"
        )
        assert result == expected, (override, result)

    spec = importlib.util.spec_from_file_location(
        "staged_paper_driver", source / "tos_paper_session.py"
    )
    assert spec and spec.loader
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
                    assert command[-2:] == ["--projection-path", expected_projection]
                else:
                    assert "--projection-path" not in command
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
                    raise AssertionError("driver never reached the captured launch")
    print(
        "PASS: 7 wrapper path cases; driver argv with/without projection; no runtime launched"
    )


if __name__ == "__main__":
    check(Path(sys.argv[1]).resolve())
