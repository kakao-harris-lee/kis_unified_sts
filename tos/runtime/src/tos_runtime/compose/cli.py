"""``tos_runtime.compose.cli`` — argument parsing only (slice plan §4 item 2).

**No daemon loop lives here.** This module composes the runtime once, from
CLI-sourced paths only (never ``os.environ``/``os.getenv`` — design #40 D1.1
"파일 경로는 CLI 인자로만 주입"), and drives it over whatever the caller's own
:class:`~tos_runtime.compose.root.ComposedRuntime.run_once` receives — a
single synthetic tick, a short replay. An always-on event loop, a broker
feed subscription, and process supervision are all Phase 5 (slice plan §4
item 2: "실행은 run_once(events) 수준 — 데몬 루프는 Phase 5").

This module does not itself decide what strategies run or what events arrive
— it only resolves the four composition-root paths + the environment label
from argv and returns the parsed :class:`Args`. A real invocation still needs
a caller-supplied :class:`~tos_runtime.compose.root.ConstructionConfig` and
the two risk input providers (:func:`~tos_runtime.compose.root.compose_paper_runtime`'s
own required keyword arguments) — those are strategy-specific and are not,
and should not be, expressible as bare CLI flags.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Args", "build_parser", "parse_args"]


@dataclass(frozen=True)
class Args:
    """The four :func:`~tos_runtime.compose.root.compose_paper_runtime`
    positional arguments, parsed from argv only."""

    config_dir: Path
    data_dir: Path
    custody_root: Path
    environment_label: str


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (argparse only — no ``os.environ`` read)."""
    parser = argparse.ArgumentParser(
        prog="tos-runtime-compose",
        description=(
            "Compose the Phase 2 paper runtime service chain "
            "(tos_runtime.compose.root.compose_paper_runtime). Does not run "
            "a daemon loop — see this module's own docstring."
        ),
    )
    parser.add_argument(
        "--config-dir",
        required=True,
        type=Path,
        help=(
            "Directory holding time.yaml/authority.yaml/risk.yaml/"
            "currentness.yaml/release.yaml (each shaped like its "
            "tos/runtime/config/*.example.yaml counterpart, every "
            "named-TBD value filled)."
        ),
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        type=Path,
        help="Directory the RCL log / evidence store / emergency log files are created under.",
    )
    parser.add_argument(
        "--custody-root",
        required=True,
        type=Path,
        help=(
            "The D4 custody directory (custody.manifest.yaml + scope files + "
            "evidence.key.<generation> files + an optional approvals/ directory)."
        ),
    )
    parser.add_argument(
        "--environment-label",
        required=True,
        type=str,
        help="This process's boot-argument environment label (e.g. 'non-live-test'/'paper').",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> Args:
    """Parse ``argv`` (defaults to ``sys.argv[1:]``) into an :class:`Args`.

    Args:
        argv: The argument vector (excluding the program name), or ``None``
            to let ``argparse`` read ``sys.argv`` itself.

    Returns:
        The parsed, path-typed :class:`Args`.
    """
    parser = build_parser()
    namespace = parser.parse_args(argv)
    return Args(
        config_dir=namespace.config_dir,
        data_dir=namespace.data_dir,
        custody_root=namespace.custody_root,
        environment_label=namespace.environment_label,
    )
