#!/usr/bin/env python3
"""``expected_code_digest`` re-derivation — one command, one source of truth.

**The failure this exists to prevent.** ``release.yaml::expected_code_digest`` pins the
sha256 of every ``*.py`` under the two installed package roots (``tos/src/tos`` and
``tos/runtime/src/tos_runtime``). Change one byte there and the pin is stale; merge it
stale and the resident paper session ABORTs at the next 08:45 and the CP-3 tenant trees
ABORT on their first boot, both with ``ReleaseAdmissionRefused``. That has happened
(PR #814 changed runtime source without re-deriving and left ``main`` stale).

The pin lives in every tree's ``release.yaml`` — DISCOVERED, not listed (below) — at
least the three byte-identical files
(``config/tos_runtime/{paper,cp3-setup-d-long,cp3-setup-d-short}/release.yaml``; the
copies are enforced by ``tos/runtime/tests/compose/test_tenant_tree_copies.py``). This
tool is the only place that writes them::

    python tools/tos_redigest.py --check    # exit 1 if any pin is stale
    python tools/tos_redigest.py --write    # rewrite the pin line in every tree

``--check`` runs as a CI step (``.github/workflows/tos-firewall.yml``) so a forgotten
re-derivation fails fast with the fix command in the message, and the equivalent
assertion runs inside the runtime suite
(``test_deploy_approved_values.py::test_release_code_digest_pin_equals_the_measured_source_tree``).

**The measurement is never reimplemented here.** It comes from the runtime's own
``print-digests`` CLI — the same ``observe_source_tree_digest()`` the boot-time
admission check calls. The import firewall forbids ``tools/`` importing ``tos`` or
``tos_runtime``, so the CLI runs as a subprocess pointed at this tree's two source
roots, the way ``~/.config/kis-probes/tos-paper-session.sh`` does — except that it is
pinned to those roots rather than merely preferring them, because an installed copy of
a different checkout answering the import would produce an honest-looking digest of the
wrong tree (see :data:`_PRINT_DIGESTS_PROGRAM`).

**Only ``expected_code_digest``.** The sibling ``expected_dependency_set_digest`` is a
property of the *deploy host's* interpreter and installed distribution set, not of the
commit, so it is deliberately out of scope: comparing it here would be red on every CI
run and on every developer machine. The resident session's wrapper checks that one
where it means something (on the deploy host, before boot).

Fail-closed everywhere: an unparseable pin, a missing pin, more than one pin, or a
``print-digests`` run that prints no 64-char lowercase hex digest is an error (exit 2),
never a silent pass. "Empty equals empty" is not a match — the 2026-10 lesson from the
wrapper's own digest guard.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

#: Repo root, derived from this file's location (``tools/`` is a top-level directory).
REPO_ROOT = Path(__file__).resolve().parents[1]

#: Where tree release files live: ``config/tos_runtime/<tree>/release.yaml``.
RELEASE_GLOB = "config/tos_runtime/*/release.yaml"

#: Trees that MUST be among the discovered ones — the resident tree and the first two
#: tenants. Discovery is what the tool writes to; this list only makes a vanished tree an
#: error instead of one fewer file quietly checked.
RELEASE_FILES: tuple[str, ...] = (
    "config/tos_runtime/paper/release.yaml",
    "config/tos_runtime/cp3-setup-d-long/release.yaml",
    "config/tos_runtime/cp3-setup-d-short/release.yaml",
)

_HEX64 = r"[0-9a-f]{64}"

#: The pin line in ``release.yaml``: ``expected_code_digest: "<64 hex>"`` at column 0.
#: The header's history comments mention the same key but start with ``#``, so the
#: ``^`` anchor excludes them.
_PIN_LINE = re.compile(
    rf'^(?P<prefix>expected_code_digest:[ \t]*")(?P<digest>{_HEX64})(?P<suffix>")',
    re.MULTILINE,
)

#: The same key in ``print-digests`` output, where the value is unquoted.
_MEASURED_LINE = re.compile(
    rf"^expected_code_digest:[ \t]*({_HEX64})[ \t]*$", re.MULTILINE
)

#: The program the measurement subprocess runs, with the two source roots as argv.
#:
#: Run under ``-I`` (isolated): ``PYTHONPATH`` and the user site directory are ignored,
#: so nothing the caller's environment happens to carry can steer the import. The two
#: roots are then put on ``sys.path`` explicitly.
#:
#: That alone is not enough. An editable install registers a finder in ``sys.meta_path``
#: (CI installs both distributions editable), and ``sys.meta_path`` is consulted BEFORE
#: ``sys.path`` — so an installed copy of a DIFFERENT checkout could answer the import
#: and the tool would measure that tree while writing this one's pin. So the program
#: checks where each module actually came from and refuses if it is not under the root
#: it was asked to measure. The digest is only honest if it is a digest OF THE TREE THE
#: PIN IS BEING WRITTEN INTO.
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
    """Run the runtime's own ``print-digests`` and return its ``expected_code_digest``.

    Args:
        repo_root: Tree to measure. Its ``tos/src`` and ``tos/runtime/src`` are the ONLY
            places the two packages may be imported from — see
            :data:`_PRINT_DIGESTS_PROGRAM` for how that is enforced.
        python_executable: Interpreter to run it with (default: the current one).

    Raises:
        RedigestError: Either source root is missing, the CLI failed, a package
            resolved outside ``repo_root``, or no 64-char lowercase hex digest was
            printed.
    """
    kernel_root = repo_root / "tos" / "src"
    runtime_root = repo_root / "tos" / "runtime" / "src"
    missing = [root for root in (kernel_root, runtime_root) if not root.is_dir()]
    if missing:
        # Without this, a --repo-root that is not a checkout of this repo would let the
        # import fall through to an INSTALLED tos/tos_runtime, and --write would put a
        # digest measured from some other tree into this tree's pin.
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
    """The one ``expected_code_digest`` pinned in ``path``.

    Raises:
        RedigestError: The file has no such line, or more than one.
    """
    # `findall` is typed `list[Any]`; the pattern's three groups are all strings,
    # so naming that here keeps the return genuinely `str` instead of `Any`.
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
    """Rewrite the pin line in ``path``; every other byte stays as it was.

    Returns:
        True if the file changed, False if it already held ``digest``.

    Raises:
        RedigestError: The file has no pin line, or more than one.
    """
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
    """Every ``config/tos_runtime/*/release.yaml`` — the stock tree (#926) is the incident.

    A hand-kept list of three silently skipped the fourth tree: its pin was left at the old
    digest while ``--check`` reported "all 3 pins match". Discovery closes that; every
    discovered file must then carry exactly one pin (:func:`read_pin`), so a tree whose
    release.yaml lost its pin is an error, never skipped.

    Raises:
        RedigestError: no release file at all, or one of :data:`RELEASE_FILES` is missing.
    """
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
        # OSError too: an unreadable/absent release.yaml must exit 2 ("cannot tell"),
        # not fall through to an uncaught traceback whose exit 1 reads as "stale pin".
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
