#!/usr/bin/env python3
"""Export one recorded session's per-bar inspection for the operator UI to read.

Two blocks are added here rather than in the kernel-side inspection
(``tos/runtime/cp3/inspect_session.py``), and the reason is the same for both:
that module's output feeds nothing but this export, while its *source* is folded
into the release pin the resident paper session aborts on. Growing it for a
page's benefit would move a digest for a reason that has nothing to do with what
the engine decides.

* ``explain`` — each rule's own ``rationale`` sentence and the definition of
  every field it reads, from the tenant content the session actually ran
  (:mod:`tools.tos_cp3.bars_explain`).
* ``hypothetical_pnl`` — for a decision-only (futures) tenant only, what the
  session's decisions would have earned if every one of them had filled at its
  bar's close (:mod:`tools.tos_cp3.hypothetical_pnl`). Never realized PnL; the
  block says so in every direction it can.

Neither block can fail the export. A tenant tree this exporter cannot read is a
document without an explanation, not a missing document: the bars are the thing
the page cannot do without, and refusing to write them because a comment could
not be found would be the wrong trade.
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
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3 import bars_explain, hypothetical_pnl, inspect_session  # noqa: E402

__all__ = [
    "BARS_SCHEMA_VERSION",
    "BARS_SUBDIR",
    "CONTRACT_SPEC_CONFIG",
    "DECISION_ONLY_MARKETS",
    "DIR_MODE",
    "DOCUMENT_MODE",
    "PROJECTION_DIR_ENV",
    "ExportRefusal",
    "attach_explanations",
    "default_out_dir",
    "document_path",
    "export_bars",
    "main",
    "resolve_contract",
]

BARS_SUBDIR = "bars"

BARS_SCHEMA_VERSION = 1

PROJECTION_DIR_ENV = "TOS_OPERATOR_PROJECTION_DIR"

DIR_MODE = 0o700
DOCUMENT_MODE = 0o600

SESSION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

#: The markets whose tenants decide but never order (operator decision
#: 2026-11-05). Only these get a hypothetical PnL: on a tenant that really
#: trades, a second "PnL" beside the realized one is an invitation to read the
#: wrong number.
DECISION_ONLY_MARKETS = frozenset({"futures"})

#: Where the contract multiplier comes from. Config, never a literal — the mini
#: and the full KOSPI200 contract differ by a factor of five, and a hardcoded
#: 50,000 would be silently wrong the day a tenant moves to the full contract.
CONTRACT_SPEC_CONFIG = REPO_ROOT / "config" / "execution.yaml"

#: Which published field carries the bar close, per tenant. Read from the
#: session's own rendered ``construction.yaml`` — the same key the order
#: construction uses, so the hypothetical fill price is the price the tenant
#: would actually have been priced at.
CONSTRUCTION_FILE_NAME = "construction.yaml"
PRICE_FIELD_CONFIG_KEY = "price_field_key"

#: Everything resolving the contract may raise, degraded into "no hypothetical
#: block" rather than allowed to kill the export. ``ContractSpecRegistry`` is a
#: plain ``**fields`` constructor over a YAML mapping, so a renamed or extra key
#: in ``config/execution.yaml`` surfaces as ``TypeError``; the file itself can
#: fail to parse (``yaml.YAMLError``) or to open (``OSError``);
#: ``resolve_contract_spec`` raises ``ValueError`` for an unknown symbol.
_CONTRACT_REFUSALS = (
    bars_explain.ExplainRefusal,
    OSError,
    UnicodeError,
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    yaml.YAMLError,
)


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


def resolve_contract(
    instrument: str,
    *,
    price_field: str,
    price_scale: int,
    config_path: Path | None = None,
) -> hypothetical_pnl.Contract:
    """The contract facts for ``instrument``, all read from config.

    ``shared.instruments.contract_spec`` is the repo's single definition of a
    futures contract's multiplier, and it is pure (stdlib + pyyaml). Reading it
    here rather than restating 50,000 is the "Configuration-driven only" rule:
    the mini and the full KOSPI200 contract differ by five times.

    ``config_path`` defaults to :data:`CONTRACT_SPEC_CONFIG` read at CALL time,
    not bound as a default argument: a default argument is evaluated at import,
    which would make the module constant unoverridable and the degrade path
    untestable.
    """
    from shared.instruments.contract_spec import (
        ContractSpecRegistry,
        resolve_contract_spec,
    )

    registry = ContractSpecRegistry.from_yaml(
        str(CONTRACT_SPEC_CONFIG if config_path is None else config_path)
    )
    spec = resolve_contract_spec(instrument, registry)
    return hypothetical_pnl.Contract(
        name=spec.name,
        multiplier_krw_per_point=spec.multiplier_krw_per_point,
        price_field=price_field,
        price_scale=price_scale,
    )


def _price_field(render_dir: Path, fields_doc: dict[str, Any]) -> tuple[str, int]:
    """``(close field's published name, its scale)`` for this tenant.

    Both come from the tenant's own rendered tree: the field name from
    ``construction.yaml``, the scale from the ``publish:`` entry that emits it.
    A scale read wrong by a factor of 100 would not look wrong — it would look
    like a very profitable day.
    """
    try:
        raw = yaml.safe_load((render_dir / CONSTRUCTION_FILE_NAME).read_text("utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        # Raised as a refusal, not let out: `attach_explanations` must never
        # fail the export over a block the page can do without, and a bare
        # YAMLError is not in the exception set it catches.
        raise bars_explain.ExplainRefusal(
            f"{CONSTRUCTION_FILE_NAME}: {type(exc).__name__}"
        ) from exc
    if not isinstance(raw, dict) or not isinstance(
        raw.get(PRICE_FIELD_CONFIG_KEY), str
    ):
        raise bars_explain.ExplainRefusal(
            f"{CONSTRUCTION_FILE_NAME}: '{PRICE_FIELD_CONFIG_KEY}' 가 없다"
        )
    field = str(raw[PRICE_FIELD_CONFIG_KEY])
    for entry in fields_doc.get("publish") or []:
        if not isinstance(entry, dict) or entry.get("as") != field:
            continue
        scale = entry.get("scale")
        # SAFETY: 배수를 모를 때 1 로 떨어지면 가격이 100배가 되고 가상 손익도 100배가 된다 — 틀려 보이지 않고 아주 좋은 날처럼 보인다
        if scale is None:
            return field, 1
        mult = scale.get("mult") if isinstance(scale, dict) else None
        if isinstance(mult, bool) or not isinstance(mult, int) or mult <= 0:
            raise bars_explain.ExplainRefusal(
                f"{field}: publish 배수가 양의 정수가 아니다"
            )
        return field, mult
    raise bars_explain.ExplainRefusal(f"{field}: publish 블록에 없다 — 배수를 모른다")


def attach_explanations(
    document: dict[str, Any],
    session: str,
    *,
    state_dir: str | None = None,
) -> dict[str, Any]:
    """Add ``explain`` and, for a decision-only tenant, ``hypothetical_pnl``.

    Returns the same document. Any refusal is recorded **in** the document, as
    ``explain_error``/``hypothetical_pnl_error``, and never raised: the bars are
    what the page cannot do without.
    """
    try:
        content = bars_explain.read_tenant_content(session, state_dir=state_dir)
        document["explain"] = bars_explain.build_explain(
            content.strategy,
            content.fields_doc,
            probe_rule_ids=bars_explain.load_probe_rule_ids(),
        )
    except bars_explain.ExplainRefusal as exc:
        document["explain"] = None
        document["explain_error"] = str(exc)
        return document

    document["market"] = content.market
    document["decision_only"] = content.market in DECISION_ONLY_MARKETS
    if not document["decision_only"]:
        return document

    instrument = document.get("instrument")
    if not isinstance(instrument, str) or content.direction not in (
        hypothetical_pnl.LONG,
        hypothetical_pnl.SHORT,
    ):
        # Direction is what makes a profit a profit here; a tenant whose
        # manifest does not declare one gets no number rather than a LONG
        # default, which would print every SHORT session exactly inverted.
        document["hypothetical_pnl"] = None
        document["hypothetical_pnl_error"] = "방향 또는 월물을 읽지 못했다"
        return document

    try:
        field, scale = _price_field(content.render_dir, content.fields_doc)
        contract = resolve_contract(instrument, price_field=field, price_scale=scale)
    except _CONTRACT_REFUSALS as exc:
        document["hypothetical_pnl"] = None
        document["hypothetical_pnl_error"] = type(exc).__name__
        return document

    document["hypothetical_pnl"] = hypothetical_pnl.build_hypothetical_pnl(
        document.get("bars") or [],
        direction=content.direction,
        contract=contract,
        instrument=instrument,
        # The page and the number must agree about what a probe is, so the
        # flags the explanation already published are the ones used here.
        probe_rule_ids=frozenset(
            rule["rule_id"]
            for rule in document["explain"]["rules"]
            if rule.get("probe") and rule.get("rule_id")
        ),
    )
    return document


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
    attach_explanations(document, session, state_dir=state_dir)
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
