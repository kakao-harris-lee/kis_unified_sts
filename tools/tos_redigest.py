#!/usr/bin/env python3
"""``expected_code_digest`` re-derivation — one command, one source of truth."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

RELEASE_GLOB = "config/tos_runtime/*/release.yaml"

RELEASE_FILES: tuple[str, ...] = (
    "config/tos_runtime/paper/release.yaml",
    "config/tos_runtime/cp3-setup-d-long/release.yaml",
    "config/tos_runtime/cp3-setup-d-short/release.yaml",
)

_HEX64 = r"[0-9a-f]{64}"

_PIN_LINE = re.compile(
    rf'^(?P<prefix>expected_code_digest:[ \t]*")(?P<digest>{_HEX64})(?P<suffix>")',
    re.MULTILINE,
)

_MEASURED_LINE = re.compile(
    rf"^expected_code_digest:[ \t]*({_HEX64})[ \t]*$", re.MULTILINE
)

_PRINT_DIGESTS_PROGRAM = """\
import os
import sys

kernel_root, runtime_root = sys.argv[1], sys.argv[2]
sys.path[:0] = [kernel_root, runtime_root]

import tos
import tos_runtime

for module, root in ((tos, kernel_root), (tos_runtime, runtime_root)):
    resolved = os.path.realpath(module.__file__)
    expected = os.path.realpath(root)
    if os.path.commonpath([resolved, expected]) != expected:
        sys.exit(
            "refused: %s resolved to %s, outside the requested source root %s — an "
            "installed copy of another checkout would have been measured"
            % (module.__name__, resolved, expected)
        )

from tos_runtime.compose.cli import main

sys.exit(main(["print-digests"]))
"""

_FIX_COMMAND = "python tools/tos_redigest.py --write"


class RedigestError(RuntimeError):
    """Something the tool cannot measure or parse — fail closed, never pass."""


def measure_code_digest(
    repo_root: Path = REPO_ROOT, python_executable: str | None = None
) -> str:
    """Run the runtime's own ``print-digests`` and return its ``expected_code_digest``."""
    kernel_root = repo_root / "tos" / "src"
    runtime_root = repo_root / "tos" / "runtime" / "src"
    missing = [root for root in (kernel_root, runtime_root) if not root.is_dir()]
    if missing:
        raise RedigestError(
            "not a checkout of this repo — missing source root(s): "
            + ", ".join(str(root) for root in missing)
            + " (--repo-root must point at a tree containing tos/src and "
            "tos/runtime/src)"
        )
    proc = subprocess.run(
        [
            python_executable or sys.executable,
            "-I",
            "-c",
            _PRINT_DIGESTS_PROGRAM,
            str(kernel_root),
            str(runtime_root),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RedigestError(
            f"`print-digests` exited {proc.returncode} — cannot measure the source "
            f"tree.\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    match = _MEASURED_LINE.search(proc.stdout)
    if match is None:
        raise RedigestError(
            "`print-digests` printed no `expected_code_digest: <64-char lowercase "
            f"hex>` line — refusing to compare nothing.\nstdout:\n{proc.stdout}"
        )
    return match.group(1)


def read_pin(path: Path) -> str:
    """The one ``expected_code_digest`` pinned in ``path``."""
    matches: list[tuple[str, str, str]] = _PIN_LINE.findall(
        path.read_text(encoding="utf-8")
    )
    if len(matches) != 1:
        raise RedigestError(
            f'{path}: expected exactly one `expected_code_digest: "<64-char lowercase '
            f'hex>"` line, found {len(matches)}'
        )
    return matches[0][1]


def write_pin(path: Path, digest: str) -> bool:
    """Rewrite the pin line in ``path``; every other byte stays as it was."""
    text = path.read_text(encoding="utf-8")
    new_text, count = _PIN_LINE.subn(rf"\g<prefix>{digest}\g<suffix>", text)
    if count != 1:
        raise RedigestError(
            f'{path}: expected exactly one `expected_code_digest: "<64-char lowercase '
            f'hex>"` line to rewrite, found {count}'
        )
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def _pin_paths(repo_root: Path) -> list[Path]:
    """Every ``config/tos_runtime/*/release.yaml`` — the stock tree (#926) is the incident."""
    found = sorted(repo_root.glob(RELEASE_GLOB))
    if not found:
        raise RedigestError(
            f"no {RELEASE_GLOB} under {repo_root} — refusing to report on zero pins"
        )
    missing = [name for name in RELEASE_FILES if repo_root / name not in found]
    if missing:
        raise RedigestError(f"required release file(s) missing: {missing}")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tools/tos_redigest.py",
        description=(
            "Compare (or rewrite) release.yaml's expected_code_digest against the "
            "runtime's own print-digests measurement of this tree."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="exit 1 (and print measured vs pinned) if any discovered pin is stale",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="rewrite the pin line in every discovered release.yaml in place",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="tree to measure and to rewrite (default: this checkout)",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    try:
        measured = measure_code_digest(repo_root)
        pins = {path: read_pin(path) for path in _pin_paths(repo_root)}
    except (RedigestError, OSError) as error:
        print(f"tos_redigest: ERROR — {error}", file=sys.stderr)
        return 2

    if args.write:
        try:
            rewritten = [path for path in pins if write_pin(path, measured)]
        except RedigestError as error:
            print(f"tos_redigest: ERROR — {error}", file=sys.stderr)
            return 2
        if not rewritten:
            print(f"tos_redigest: already current — {measured}")
            return 0
        print(f"tos_redigest: wrote {measured} into {len(rewritten)} file(s):")
        for path in rewritten:
            print(f"  {path.relative_to(repo_root)}")
        return 0

    stale = {path: pinned for path, pinned in pins.items() if pinned != measured}
    if not stale:
        print(
            f"tos_redigest: OK — all {len(pins)} pins match the measured tree ({measured})"
        )
        return 0
    print(
        "tos_redigest: STALE — expected_code_digest does not match the measured "
        "source tree.",
        file=sys.stderr,
    )
    print(f"  measured (tos/src + tos/runtime/src): {measured}", file=sys.stderr)
    for path, pinned in stale.items():
        print(f"  pinned in {path.relative_to(repo_root)}: {pinned}", file=sys.stderr)
    print(f"  fix: {_FIX_COMMAND}  (then commit the rewritten files)", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
