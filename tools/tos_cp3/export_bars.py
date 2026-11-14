#!/usr/bin/env python3
"""Export one recorded session's per-bar inspection for the operator UI to read."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3 import inspect_session  # noqa: E402

__all__ = [
    "BARS_SCHEMA_VERSION",
    "BARS_SUBDIR",
    "DIR_MODE",
    "DOCUMENT_MODE",
    "PROJECTION_DIR_ENV",
    "ExportRefusal",
    "default_out_dir",
    "document_path",
    "export_bars",
    "main",
]

BARS_SUBDIR = "bars"

BARS_SCHEMA_VERSION = 1

PROJECTION_DIR_ENV = "TOS_OPERATOR_PROJECTION_DIR"

DIR_MODE = 0o700
DOCUMENT_MODE = 0o600

SESSION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class ExportRefusal(Exception):
    """An export refusal — a bad destination, or an inspection that refused."""


def default_out_dir() -> Path:
    """The projection directory from the environment."""
    raw = os.environ.get(PROJECTION_DIR_ENV, "").strip()
    if not raw:
        raise ExportRefusal(
            f"{PROJECTION_DIR_ENV} is not set — it names the HOST directory the "
            "dashboard has bind-mounted read-only, and a document written "
            "anywhere else would look exactly like no document at all on the "
            "page. Pass --out-dir to override deliberately."
        )
    return Path(os.path.expandvars(os.path.expanduser(raw)))


def document_path(out_dir: Path, session_name: str) -> Path:
    """Where ``session_name``'s document belongs under ``out_dir``."""
    return out_dir / BARS_SUBDIR / f"{session_name}.json"


def _inspect_document(
    session: str,
    *,
    state_dir: str | None,
    data_dir: str | None,
    runner: inspect_session.Runner | None = None,
) -> tuple[str, dict[str, object]]:
    """``(session name, the inspection document)`` for ``session``."""
    extra = {} if runner is None else {"runner": runner}
    outcome = inspect_session.run(
        session=session,
        state_dir=state_dir,
        data_dir=data_dir,
        as_json=True,
        **extra,  # type: ignore[arg-type]
    )
    if outcome.exit_code != 0:
        raise ExportRefusal(
            f"inspection of {session!r} refused (exit {outcome.exit_code}): "
            f"{outcome.stderr.strip() or '(no message)'}"
        )
    try:
        document = json.loads(outcome.stdout)
    except json.JSONDecodeError as exc:
        raise ExportRefusal(
            f"inspection of {session!r} emitted invalid JSON: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise ExportRefusal(
            f"inspection of {session!r} emitted a {type(document).__name__}, "
            "not a JSON object"
        )
    name = document.get("session")
    if not isinstance(name, str) or not name:
        raise ExportRefusal(
            f"inspection of {session!r} names no session, so the document has "
            "no filename the page could ask for"
        )
    if not SESSION_NAME_PATTERN.match(name):
        raise ExportRefusal(
            f"inspection of {session!r} names session {name!r}, which is outside "
            f"{SESSION_NAME_PATTERN.pattern} — that name is both this document's "
            "filename and the path segment GET /api/tos/sessions/{id}/bars is "
            "asked for, so a document written under it could never be served"
        )
    return name, document


def _narrow_directory(directory: Path) -> None:
    """Ensure ``directory`` exists and carries no bit outside :data:`DIR_MODE`."""
    directory.mkdir(parents=True, exist_ok=True)
    if stat.S_IMODE(directory.stat().st_mode) & ~DIR_MODE:
        os.chmod(directory, DIR_MODE)


def _write_atomically(path: Path, payload: str) -> None:
    """Write ``payload`` to ``path`` through a temp file in the same directory."""
    _narrow_directory(path.parent.parent)
    _narrow_directory(path.parent)
    handle, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, DOCUMENT_MODE)
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def export_bars(
    session: str,
    *,
    out_dir: Path | None = None,
    state_dir: str | None = None,
    data_dir: str | None = None,
    runner: inspect_session.Runner | None = None,
) -> Path:
    """Export ``session``'s inspection document and return where it landed."""
    destination_root = default_out_dir() if out_dir is None else out_dir
    name, document = _inspect_document(
        session, state_dir=state_dir, data_dir=data_dir, runner=runner
    )
    document["schema_version"] = BARS_SCHEMA_VERSION
    path = document_path(destination_root, name)
    try:
        _write_atomically(
            path, json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n"
        )
    except OSError as exc:
        raise ExportRefusal(f"{path}: cannot write the bars document: {exc}") from exc
    return path


def _parser() -> argparse.ArgumentParser:
    """The standalone CLI (``sts tos export-bars`` is a thin wrapper on :func:`export_bars`)."""
    parser = argparse.ArgumentParser(
        prog="tools.tos_cp3.export_bars",
        description=(
            "Export one recorded CP-3 session's per-bar inspection as JSON into "
            "the directory the dashboard has bind-mounted read-only."
        ),
    )
    parser.add_argument("session", help="session directory name, or a path to one")
    parser.add_argument(
        "--out-dir",
        default=None,
        help=f"destination root (default: ${PROJECTION_DIR_ENV})",
    )
    parser.add_argument("--state-dir", default=None)
    parser.add_argument("--data-dir", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Export one session. ``0`` on success, ``2`` on any refusal."""
    args = _parser().parse_args(argv)
    try:
        path = export_bars(
            args.session,
            out_dir=None if args.out_dir is None else Path(args.out_dir),
            state_dir=args.state_dir,
            data_dir=args.data_dir,
        )
    except ExportRefusal as exc:
        print(f"export-bars refused: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
