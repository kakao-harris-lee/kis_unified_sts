#!/usr/bin/env python3
"""Export one recorded session's per-bar inspection for the operator UI to read.

Roadmap ``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1, second item (the
``/tos`` bar panel and its Control Plane read model). This is the **host side**
of that boundary: it runs :mod:`tools.tos_cp3.inspect_session` and drops the
``--json`` document into the directory the dashboard container already has
bind-mounted read-only.

**Why a file and not an API call into the core.** The dashboard cannot reach the
inspection as a child process, and that is not a configuration oversight —
four independent walls, all measured 2026-11-11:

1. ``docker-compose.yml``'s ``dashboard`` service mounts ``./config``,
   ``./logs``, ``./reports``, ``./data/runtime``, ``./data/market`` and
   ``${TOS_OPERATOR_PROJECTION_DIR}`` — nothing under ``~/.local/state/tos``;
2. ``Dockerfile.dashboard`` copies ``shared/``, ``services/``, ``cli/``,
   ``config/`` only, so neither ``tos/`` nor ``tools/`` exists in that image;
3. every tenant state directory is ``0700 deploy:deploy`` (the runner logs
   "data parent mode 700" and ``bootproof_guard`` enforces the containment), so
   a bind mount alone would not make them readable;
4. ``tos_runtime`` is not installed in that virtualenv at all
   (``services/dashboard/routes/tos_projection.py`` module docstring).

So this follows the boundary that service already uses for
``GET /api/tos/projection``: a producer on the host writes a JSON document, the
container opens it **by path only**, imports no ``tos``/``tos_runtime``, and
writes nothing back.

**The mount pairing.** ``TOS_OPERATOR_PROJECTION_DIR`` is the HOST directory
(``.env.paper``: ``/home/deploy/.local/state/tos/paper-projection``);
``TOS_OPERATOR_PROJECTION_PATH`` is the file path INSIDE the container. The
compose comment calls them a pair that must be set together, and this exporter
joins the same pair rather than inventing a third variable: it writes
``<TOS_OPERATOR_PROJECTION_DIR>/bars/<session>.json`` and the route reads
``<dirname(TOS_OPERATOR_PROJECTION_PATH)>/bars/<session>.json``.

**Permissions, measured rather than hoped.** The directory is created ``0700``
and the document written ``0600``, owned by whoever runs this (``deploy``,
uid 1000). The container's ``appuser`` is also **uid 1000**
(``Dockerfile.dashboard``: ``useradd -m -u 1000 appuser``) and a bind mount
preserves numeric uids, which is exactly why the existing ``0600``
``operator_projection.json`` is readable there today. This exporter therefore
adds no new exposure: same owner, same mode class, same mount.

**Atomic.** The document is written to a temporary file in the same directory
and ``os.replace``-d into place, so a reader never sees a half-written
document — the invariant ``tos_projection.py``'s reader already relies on
("The exporter atomically replaces the file").

Usage::

    # one session (backfill, or any past session)
    python -m tools.tos_cp3.export_bars stock-r1-20261110
    # explicit destination, e.g. a dry run outside the mounted dir
    python -m tools.tos_cp3.export_bars stock-r1-20261110 --out-dir /tmp/x

``sts tos export-bars <session>`` is the same thing through the operator CLI.
"""

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

#: Repo root of the checkout this file belongs to, at the FRONT of ``sys.path``
#: for the same reason B1a/B2/B3 do it: an editable install of another checkout
#: must not shadow this worktree's ``tools/``.
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

#: The subdirectory under the projection dir that holds one document per
#: session. A subdirectory rather than a filename prefix so the existing
#: ``operator_projection.json`` reader is untouched and a listing is cheap.
BARS_SUBDIR = "bars"

#: This document's own schema version, checked by the route. Bump on any change
#: that moves or re-means a key, so a dashboard reading an older document says
#: "unsupported schema_version" instead of rendering it as if it understood it.
BARS_SCHEMA_VERSION = 1

#: The host env var naming the directory the container has bind-mounted.
PROJECTION_DIR_ENV = "TOS_OPERATOR_PROJECTION_DIR"

#: ``0700``/``0600``: the same owner and mode class as the
#: ``operator_projection.json`` the container already reads through this mount
#: (measured 2026-11-11). Readable there only because ``appuser`` is uid 1000,
#: the same numeric uid as ``deploy`` — see the module docstring.
DIR_MODE = 0o700
DOCUMENT_MODE = 0o600

#: The session names this exporter will write a document under. MIRRORS
#: ``services/dashboard/routes/tos_bars.py``'s ``_SESSION_ID_PATTERN``, and the
#: two are asserted equal by
#: ``tests/tools/test_cp3_export_bars.py::test_the_exported_name_is_one_the_route_will_accept``
#: — restated rather than imported because this is a stdlib-only host tool and
#: importing the route would pull FastAPI into a cron step.
#:
#: Checked BEFORE the write (not only by the route on the way out): the name is
#: this document's filename, so a name outside the pattern would either escape
#: the directory this module chose or produce a file the route refuses to serve.
SESSION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class ExportRefusal(Exception):
    """An export refusal — a bad destination, or an inspection that refused."""


def default_out_dir() -> Path:
    """The projection directory from the environment.

    Raises:
        ExportRefusal: :data:`PROJECTION_DIR_ENV` is unset or blank. Guessing a
            destination is the one thing this must not do: a document written
            somewhere the container does not mount is indistinguishable, from
            the page, from no document at all.
    """
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
    """``(session name, the inspection document)`` for ``session``.

    ``runner`` is injected for the same reason the driver injects it: a test can
    then pin what this module does with a document without starting a process.

    Raises:
        ExportRefusal: The inspection refused (its stderr is carried through),
            or its stdout is not a JSON object.
    """
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
        # Loudly, before anything is written. This name becomes a FILENAME here
        # and a path segment the route is asked for later; a name outside the
        # pattern would either land somewhere this function did not choose or
        # produce a document the route refuses to serve — a file that exists and
        # can never be read. Refusing beats both.
        raise ExportRefusal(
            f"inspection of {session!r} names session {name!r}, which is outside "
            f"{SESSION_NAME_PATTERN.pattern} — that name is both this document's "
            "filename and the path segment GET /api/tos/sessions/{id}/bars is "
            "asked for, so a document written under it could never be served"
        )
    return name, document


def _narrow_directory(directory: Path) -> None:
    """Ensure ``directory`` exists and carries no bit outside :data:`DIR_MODE`.

    ``mkdir(mode=…)`` is not enough, twice over:

    * it applies the mode only to the leaf it creates, so a parent created on
      the same call (the projection directory, on a first run) gets the default;
    * the mode is masked by ``umask``, and it does nothing at all for a
      directory that already exists — a ``bars/`` left at ``0755`` by an earlier
      run, a restore, or a hand-made ``mkdir`` would stay world-readable and
      nothing here would say so.

    So the mode is checked after the fact, every run, for the projection
    directory AND for ``bars/``.

    **It only ever narrows.** The chmod fires exactly when a bit outside
    ``0700`` is set; a directory the operator left NARROWER (``0500``, say) is
    left alone, and the write then fails with the caller's named refusal. A
    mode-tightening fix that quietly granted itself write access to a
    deliberately read-only directory would be doing the opposite of its job.
    A chmod that fails refuses too, through the caller's ``OSError`` handler.

    Raises:
        OSError: ``mkdir``, ``stat`` or ``chmod`` failed (the caller turns it
            into an :class:`ExportRefusal` naming the path).
    """
    directory.mkdir(parents=True, exist_ok=True)
    if stat.S_IMODE(directory.stat().st_mode) & ~DIR_MODE:
        os.chmod(directory, DIR_MODE)


def _write_atomically(path: Path, payload: str) -> None:
    """Write ``payload`` to ``path`` through a temp file in the same directory.

    ``os.replace`` is atomic within one filesystem, so a reader holding the old
    inode keeps reading a whole document and the next open gets the whole new
    one — never a truncated mix. The temp file is created in the destination
    directory (not ``/tmp``) precisely so the rename cannot cross a filesystem.

    ⚠ A ``SIGKILL`` between ``mkstemp`` and ``os.replace`` leaves one
    ``.<name>.<rand>.tmp`` behind. Deliberately not swept: the route lists only
    ``*.json`` (``Path.suffix`` of such a file is ``.tmp``), so a leftover is
    invisible to the page and to ``latest``, and it cannot be mistaken for a
    document. One dotfile per kill in a ``0700`` directory does not earn a
    sweeper (CLAUDE.md R5 — a new guard needs a real incident beside it).
    """
    # Both levels, not just the leaf — see `_narrow_directory`.
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
    """Export ``session``'s inspection document and return where it landed.

    Args:
        session: The session directory name (or a path to one).
        out_dir: The projection directory to write under, or ``None`` to read
            :data:`PROJECTION_DIR_ENV`.
        state_dir: Overrides the status-board config's state root.
        data_dir: An explicit tenant durable-set leaf.
        runner: The process runner the inspection uses (injected for tests).

    Returns:
        The written document's path.

    Raises:
        ExportRefusal: No destination, the inspection refused, or the write
            failed.
    """
    destination_root = default_out_dir() if out_dir is None else out_dir
    name, document = _inspect_document(
        session, state_dir=state_dir, data_dir=data_dir, runner=runner
    )
    # The version goes on the OUTSIDE of the inspection's own document: the
    # route checks it before validating anything else, exactly as the sibling
    # projection reader does, so an older document is reported as unsupported
    # rather than parsed optimistically.
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
