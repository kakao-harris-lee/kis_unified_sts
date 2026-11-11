#!/usr/bin/env python3
"""`sts tos inspect` — the legacy-side driver for the per-bar inspection.

Roadmap ``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1. The operator
types one session name; this module turns it into the four paths the inspection
needs and runs the inspection.

**Why this is a driver and not the tool.** The inspection must reuse the DSL
evaluator (``tos.dsl.vocabulary.eval_compare`` / ``evaluate_policy``) and the
production strategy loader — re-implementing comparison semantics outside the
kernel would make the screen's answer a property of this file rather than of the
strategy, and ``EQ`` is type-strict in a way a hand-rolled comparison gets wrong.
But the import firewall is **bidirectional**: ``tools/`` is in its reverse scan
(``tools/tos_firewall_check.py`` TOS-FW-R), so this file may not import ``tos``
or ``tos_runtime`` at all — the same rule that makes
:mod:`tools.tos_cp3.session_inputs` read the runtime's sqlite stores as plain
files instead of importing their classes, and that makes
:mod:`tools.tos_cp3.produce_fields` drive the legacy Setup D class rather than
the kernel.

So the two sides meet the way every other CP-3 pair does — through a **process
boundary**, exactly as ``tools/tos_cp3/runners/cp3_tenant_daily.sh`` boots the
runtime (``PYTHONPATH=tos/runtime/src:tos/src python -c 'from
tos_runtime.compose.cli import main; …'``). The inspection core is
``tos/runtime/cp3/inspect_session.py`` (RUNTIME scope, so it imports the real
kernel evaluator, the real loader and the real store constants); this module
resolves paths, builds that process's argv, and hands its output back.

**Read-only.** Nothing here writes: the child process opens the journal, the
rendered tenant tree and the three sqlite stores for reading only.

Usage::

    sts tos inspect stock-r1-20261110
    sts tos inspect stock-r1-20261110 --from 09:00 --to 10:00
    sts tos inspect ~/.local/state/tos/cp3-sessions/stock-r1-20261110 --json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

#: Repo root of the checkout this file belongs to, at the FRONT of ``sys.path``
#: for the same reason B1a/B2/B3 do it: an editable install of another checkout
#: must not shadow this worktree's ``tools/``.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3 import status_board  # noqa: E402

__all__ = [
    "INSPECT_MODULE",
    "TENANT_DATA_PARENT_SUFFIX",
    "InspectRefusal",
    "SessionPaths",
    "build_argv",
    "child_pythonpath",
    "resolve_session",
    "run",
]

#: The child module the core lives in. ``cp3`` is importable only with
#: ``tos/runtime`` on ``PYTHONPATH`` (see :func:`child_pythonpath`) — the same
#: invocation ``tos/runtime/cp3/__init__.py`` documents for the B1b runner.
INSPECT_MODULE = "cp3.inspect_session"

#: The three source roots the child needs, repo-root-relative, in the order
#: ``cp3_tenant_daily.sh`` and ``run_tenant_session.sh`` already use.
CHILD_PYTHONPATH_PARTS: tuple[str, ...] = ("tos/src", "tos/runtime/src", "tos/runtime")

#: A tenant's durable-set parent is ``<state_dir>/<tree_id><suffix>`` and its
#: leaf is the instrument — the shape ``TENANT_DATA_PARENT`` /
#: ``TOS_STOCK_DATA_PARENT`` is set to for every tracked tenant session
#: (``tools/tos_cp3/runners/stock-mock-session.env.example``;
#: ``run_tenant_session.sh`` 499행 ``DATA_LEAF=$TENANT_DATA_PARENT/$INSTRUMENT``).
#: It is a derivation, not a declaration, which is why ``--data-dir`` overrides
#: it and a missing directory refuses by name instead of being inferred further.
TENANT_DATA_PARENT_SUFFIX = "-data"

#: The rendered tenant tree's strategy directory and bindings file, as the
#: production loader names them (``tos_runtime.strategy.resolve.STRATEGIES_DIRNAME``
#: / ``tos_runtime.strategy.bindings.STRATEGY_BINDINGS_FILE_NAME``). Restated
#: here because the firewall forbids importing them; the child re-checks both
#: names through the real constants and refuses a mismatch, so a drift in either
#: literal fails loudly in the child rather than silently here.
RENDER_DIRNAME = "render"
STRATEGIES_DIRNAME = "strategies"
STRATEGY_BINDINGS_FILE_NAME = "strategy_bindings.yaml"
RENDERED_MANIFEST_NAME = "RENDERED.json"
JOURNAL_NAME = "journal.jsonl"

#: ``(argv, env) -> (stdout+stderr, exit code)``. Injected so the resolution and
#: argv construction above can be tested without starting a process.
Runner = Callable[[Sequence[str], Mapping[str, str]], "tuple[str, int]"]


class InspectRefusal(Exception):
    """A path/resolution refusal raised before the child process is started."""


@dataclass(frozen=True)
class SessionPaths:
    """The four paths one inspection reads, plus the labels for the header."""

    session_name: str
    session_dir: Path
    journal_path: Path
    strategy_path: Path
    bindings_path: Path
    data_dir: Path | None
    instrument: str
    tree_id: str


def _read_manifest(render_dir: Path) -> tuple[str, str]:
    """``(instrument, tree_id)`` from the session's own render manifest.

    Raises:
        InspectRefusal: The manifest is absent, unreadable, or names neither.
    """
    manifest_path = render_dir / RENDERED_MANIFEST_NAME
    if not manifest_path.is_file():
        raise InspectRefusal(
            f"{manifest_path}: the session's render manifest is missing — the "
            "instrument and tenant tree are read from it, never guessed"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InspectRefusal(f"{manifest_path}: cannot read: {exc}") from exc
    if not isinstance(manifest, dict):
        raise InspectRefusal(f"{manifest_path}: not a JSON object")
    instrument = manifest.get("instrument")
    tree_id = manifest.get("tree_id")
    if not isinstance(instrument, str) or not instrument:
        raise InspectRefusal(f"{manifest_path}: names no 'instrument'")
    if not isinstance(tree_id, str) or not tree_id:
        raise InspectRefusal(f"{manifest_path}: names no 'tree_id'")
    return instrument, tree_id


def _sole_strategy_file(render_dir: Path) -> Path:
    """The one strategy file the rendered tree holds.

    Raises:
        InspectRefusal: The directory is absent, empty, or holds more than one
            file — which strategy a session ran is a fact of the render, so two
            candidates are refused rather than one of them picked.
    """
    strategies_dir = render_dir / STRATEGIES_DIRNAME
    if not strategies_dir.is_dir():
        raise InspectRefusal(
            f"{strategies_dir}: the rendered tenant tree has no "
            f"{STRATEGIES_DIRNAME}/ directory"
        )
    candidates = sorted(
        path
        for path in strategies_dir.iterdir()
        if path.is_file() and path.suffix in (".yaml", ".yml")
    )
    if len(candidates) != 1:
        raise InspectRefusal(
            f"{strategies_dir}: holds {len(candidates)} strategy file(s) "
            f"{[path.name for path in candidates]} — this inspection drives one "
            "policy, so the rendered tree must hold exactly one"
        )
    return candidates[0]


def resolve_session(
    session: str,
    *,
    state_dir: Path,
    sessions_subdir: str,
    data_dir: Path | None = None,
    with_evidence: bool = True,
) -> SessionPaths:
    """Resolve one session reference into the paths the inspection reads.

    Args:
        session: A session directory name (``stock-r1-20261110``) under
            ``state_dir / sessions_subdir``, or a path to such a directory.
        state_dir: The state root (``config/tos_status_board.yaml::state_dir``,
            or ``--state-dir``).
        sessions_subdir: The tenant-session parent's name under ``state_dir``.
        data_dir: An explicit durable-set leaf, or ``None`` to derive it from
            the manifest's ``tree_id`` and ``instrument``.
        with_evidence: ``False`` skips the durable set entirely (rule evaluation
            only) — for a session whose stores were archived or moved away.

    Returns:
        The resolved :class:`SessionPaths`.

    Raises:
        InspectRefusal: The session directory, its journal, its render tree, its
            manifest, its strategy file, its bindings file, or a derived data
            directory is absent or ambiguous.
    """
    candidate = Path(session).expanduser()
    session_dir = (
        candidate if candidate.is_dir() else state_dir / sessions_subdir / session
    )
    if not session_dir.is_dir():
        raise InspectRefusal(
            f"{session_dir}: no such session directory (looked for the name under "
            f"{state_dir / sessions_subdir})"
        )
    journal_path = session_dir / JOURNAL_NAME
    if not journal_path.is_file():
        raise InspectRefusal(f"{journal_path}: the session has no producer journal")
    render_dir = session_dir / RENDER_DIRNAME
    if not render_dir.is_dir():
        raise InspectRefusal(
            f"{render_dir}: the session kept no rendered tenant tree, so the "
            "policy it actually ran cannot be read"
        )
    instrument, tree_id = _read_manifest(render_dir)
    bindings_path = render_dir / STRATEGY_BINDINGS_FILE_NAME
    if not bindings_path.is_file():
        raise InspectRefusal(f"{bindings_path}: the rendered tree has no bindings file")
    resolved_data_dir: Path | None = None
    if with_evidence:
        resolved_data_dir = (
            data_dir
            if data_dir is not None
            else state_dir / f"{tree_id}{TENANT_DATA_PARENT_SUFFIX}" / instrument
        ).expanduser()
        if not resolved_data_dir.is_dir():
            raise InspectRefusal(
                f"{resolved_data_dir}: no such durable-set leaf — pass --data-dir "
                "to name it explicitly, or --no-evidence to inspect the rules alone"
            )
    return SessionPaths(
        session_name=session_dir.name,
        session_dir=session_dir,
        journal_path=journal_path,
        strategy_path=_sole_strategy_file(render_dir),
        bindings_path=bindings_path,
        data_dir=resolved_data_dir,
        instrument=instrument,
        tree_id=tree_id,
    )


def build_argv(
    paths: SessionPaths,
    *,
    window_from: str | None = None,
    window_to: str | None = None,
    as_json: bool = False,
    executable: str | None = None,
) -> list[str]:
    """The child process's argv for ``paths``.

    ``-P`` keeps the child's ``sys.path`` free of its own script directory, the
    same hardening every ``tools/tos_cp3`` runner invocation uses.
    """
    argv = [
        executable or sys.executable,
        "-P",
        "-m",
        INSPECT_MODULE,
        "--journal",
        str(paths.journal_path),
        "--strategy",
        str(paths.strategy_path),
        "--bindings",
        str(paths.bindings_path),
        "--session-name",
        paths.session_name,
    ]
    if paths.data_dir is not None:
        argv += ["--data-dir", str(paths.data_dir)]
    if window_from is not None:
        argv += ["--from", window_from]
    if window_to is not None:
        argv += ["--to", window_to]
    if as_json:
        argv.append("--json")
    return argv


def child_pythonpath(repo_root: Path = REPO_ROOT) -> str:
    """``PYTHONPATH`` for the child: the kernel, the runtime, and ``cp3``'s parent."""
    return os.pathsep.join(str(repo_root / part) for part in CHILD_PYTHONPATH_PARTS)


def _subprocess_runner(argv: Sequence[str], env: Mapping[str, str]) -> tuple[str, int]:
    """Run the child and return its merged output and exit code."""
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        list(argv),
        capture_output=True,
        text=True,
        env=dict(env),
        check=False,
    )
    return completed.stdout + completed.stderr, completed.returncode


def run(
    *,
    session: str,
    config_path: Path = status_board.DEFAULT_CONFIG_PATH,
    state_dir: str | None = None,
    data_dir: str | None = None,
    window_from: str | None = None,
    window_to: str | None = None,
    as_json: bool = False,
    with_evidence: bool = True,
    runner: Runner = _subprocess_runner,
) -> tuple[str, int]:
    """Resolve ``session`` and render its inspection.

    Args:
        session: The session directory name or path.
        config_path: The status-board config the state root is read from.
        state_dir: Overrides the config's ``state_dir``.
        data_dir: An explicit durable-set leaf.
        window_from: Inclusive KST ``HH:MM`` lower bound.
        window_to: Inclusive KST ``HH:MM`` upper bound.
        as_json: Render the machine document instead of the table.
        with_evidence: ``False`` inspects the rules without the durable set.
        runner: The process runner (injected for tests).

    Returns:
        ``(text, exit code)`` — ``2`` on any refusal, else the child's code.
    """
    try:
        config = status_board.load_config(config_path)
        root = (
            status_board.expand_path(state_dir)
            if state_dir is not None
            else config.state_dir
        )
        paths = resolve_session(
            session,
            state_dir=root,
            sessions_subdir=config.tenant_sessions_subdir,
            data_dir=None if data_dir is None else Path(data_dir),
            with_evidence=with_evidence,
        )
    except (InspectRefusal, ValueError, OSError) as exc:
        return f"inspect refused: {exc}\n", 2
    env = dict(os.environ)
    env["PYTHONPATH"] = child_pythonpath()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return runner(
        build_argv(
            paths,
            window_from=window_from,
            window_to=window_to,
            as_json=as_json,
        ),
        env,
    )


def _parser() -> argparse.ArgumentParser:
    """The standalone CLI (``sts tos inspect`` is a thin click wrapper on :func:`run`)."""
    parser = argparse.ArgumentParser(
        prog="tools.tos_cp3.inspect_session",
        description=(
            "Read-only per-bar inspection of a recorded CP-3 tenant session: "
            "field values, every rule's comparison pass/fail, the first-match "
            "decision, and the engine's own recorded outcome/halt."
        ),
    )
    parser.add_argument("session", help="session directory name, or a path to one")
    parser.add_argument("--config", type=Path, default=status_board.DEFAULT_CONFIG_PATH)
    parser.add_argument("--state-dir", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument(
        "--no-evidence",
        dest="with_evidence",
        action="store_false",
        help="inspect the rules only; do not open the tenant durable set",
    )
    parser.add_argument("--from", dest="window_from", default=None, metavar="HH:MM")
    parser.add_argument("--to", dest="window_to", default=None, metavar="HH:MM")
    parser.add_argument("--json", dest="as_json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Render one inspection to stdout."""
    args = _parser().parse_args(argv)
    text, code = run(
        session=args.session,
        config_path=args.config,
        state_dir=args.state_dir,
        data_dir=args.data_dir,
        window_from=args.window_from,
        window_to=args.window_to,
        as_json=args.as_json,
        with_evidence=args.with_evidence,
    )
    sys.stdout.write(text)
    return code


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
