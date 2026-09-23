#!/usr/bin/env python3
"""Render the committed TOS paper deployment values into an OFF-REPO config directory
with this host's deployment coordinates filled in.

Design: ``docs/plans/2026-09-23-tos-paper-coordinates-and-first-boot-design.md`` §2
(operator decision 1, 2026-09-23 — "이 장비가 운영 장비다. 여기 있는 `.env`·`.env.mock` 을
그대로 활용" → host render-script approach). Upper plan:
``docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md`` §7.8.

Why a script outside ``tos/`` at all
------------------------------------
``run`` cannot boot without deployment coordinates (the futures account and the current
front-month contract), and neither half of that can be solved inside ``tos/``:

* tos code may not read ``os.environ`` — the AST firewall rejects it
  (``tools/tos_firewall_check.py`` TOS-FW-C, both ``from os import environ/getenv`` and the
  ``os.environ`` attribute access), and rule scoping does not exempt the runtime shell.
* the coordinates may not be committed — every policy file's own header says so
  ("scope.accounts — the paper account number (**never committed here**)").

So a host script outside ``tos/`` byte-copies the committed values, fills ONLY the coordinate
slots, and writes the result somewhere outside the repository; ``run --config-dir <that dir>``
then boots. Zero tos-code and zero firewall changes.

Firewall note (this file is OUTSIDE ``tos/``): it therefore may NOT import ``tos`` or
``tos_runtime`` at all (``tools/tos_firewall_check.py`` rule (e)/TOS-FW-R,
``_REVERSE_SCAN_TARGET_NAMES = {"tos", "tos_runtime"}``). The two runtime operations this
script needs — ``print-policy-digests`` and the activation read-back — therefore run as
SUBPROCESSES, using the same ``python -c 'import sys;from tos_runtime.compose.cli import
main;sys.exit(main(sys.argv[1:]))'`` convention the boot command itself uses. The AST gate does
not read string arguments as imports.

Secrets discipline
------------------
The account number is read from a file literally named ``.env.mock`` and is NEVER printed,
logged, or written to ``RENDERED.json`` — only its ``account_fingerprint``
(``tools/broker_probes/common.py``, the same salt-free SHA-256 correlator every broker probe
artifact carries). ``.env`` / ``.env.real`` are REFUSED as a coordinate source: that file's
futures account is the REAL account, and this repo's non-negotiable rule is that the real
futures account is never funded and never on an order path.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:  # direct-script invocation
    sys.path.insert(0, str(_REPO_ROOT))

from shared.instruments.futures import get_front_month_code  # noqa: E402
from tools.broker_probes.common import account_fingerprint  # noqa: E402

__all__ = [
    "COORDINATE_RULE_KEYS",
    "MANDATORY_POLICY_KINDS",
    "RenderError",
    "RenderResult",
    "check",
    "main",
    "normalize_account",
    "parse_account_from_env_file",
    "render",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The committed source of truth this script copies (design §2 step 1).
DEFAULT_SOURCE = _REPO_ROOT / "config" / "tos_runtime" / "paper"

#: The default OFF-REPO output directory (design §2 — never inside the worktree: one missing
#: gitignore line would be a committed account number).
DEFAULT_OUT = Path("~/.config/tos/paper-config")

#: The ONLY env-file basename this CLI accepts (design §2 guard "계좌 원천이 모의 파일").
#: There is deliberately NO test-only override flag — tests call :func:`render` directly.
ENV_FILE_NAME = ".env.mock"

#: The one key parsed out of that file. Nothing else is read, and ``os.environ`` is never
#: touched (design §2 step 2).
ACCOUNT_ENV_KEY = "KIS_FUTURES_ACCOUNT_NO"

#: Total digits a KIS account number carries once the hyphen is stripped
#: (``shared/kis/client.py`` ``_normalize_account``: "Normalize account number to digits-only
#: 10-char format"; ``tools/broker_probes/common.py`` ``ProbeCredentials.cano``/``.acnt_prdt_cd``
#: slice the same 10 as ``[:8]`` / ``[8:10]``).
ACCOUNT_DIGITS = 10

#: The render-time-generated observation journal (never committed — its ``as_of_ms`` is fixed
#: at render time, so the runbook renders immediately before booting).
JOURNAL_NAME = "bootproof_journal.jsonl"

#: The render manifest written into the output directory.
RENDERED_NAME = "RENDERED.json"

#: Files the output directory may carry that the source does not (``--check`` allows exactly
#: these two, nothing else).
_GENERATED_NAMES = frozenset({JOURNAL_NAME, RENDERED_NAME})

#: The policy kinds ``print-policy-digests`` MUST print for this deployment — the four
#: ``compose`` itself calls ``require_member_activated`` for
#: (``compose/_venue_wiring.py:265-278`` VENUE/OCP, ``compose/_riskstate_wiring.py:236-250``
#: AGGREGATE_RISK/ACTION_FLOW). A fifth line (``CRITICAL_INPUT_POLICY``) is printed since this
#: deployment adopted ``critical_input_policy.yaml``; the design's rule is one ``members``
#: entry per PRINTED line, so it gets one too.
MANDATORY_POLICY_KINDS: tuple[str, ...] = (
    "VENUE_CONSTRAINT_POLICY",
    "ORDER_CONSTRUCTION_POLICY",
    "AGGREGATE_RISK_POLICY",
    "ACTION_FLOW_POLICY",
)

#: The direction-dependent tokens. Every value is copied from the deployed Order Construction
#: Policy's own machine-readable ``action_class_shape``
#: (``config/tos_runtime/paper/order_construction_policy.yaml:203-206``), which is itself the
#: machine-readable form of that document's prose rule "long/short symmetric:
#: NEW_LONG↔BUY/OPEN, NEW_SHORT↔SELL/OPEN" (same file, ``direction_side_and_position_effect_rules``).
_DIRECTION_TOKENS: dict[str, dict[str, str]] = {
    "LONG": {"action_class": "NEW_LONG", "side": "BUY"},
    "SHORT": {"action_class": "NEW_SHORT", "side": "SELL"},
}

#: The strategy file the boot-proof fixture ships (design §3 choice (가)).
_STRATEGY_FILE = "strategies/bootproof_band.strategy.yaml"

#: The synthetic band the render-time journal carries. Values copied from the compose e2e
#: fixture's own crossing constants (``tos/runtime/tests/compose/_fixtures.py:96-99``
#: ``LOWER_BAND``/``UPPER_BAND``/``CROSSING_CLOSE``) so the shipped strategy rule
#: ("close < lower_band") actually fires. Synthetic, not a quote.
_JOURNAL_CLOSE = 4_499_000
_JOURNAL_LOWER_BAND = 4_500_000
_JOURNAL_UPPER_BAND = 4_520_000

#: How far in the past the generated observation is stamped. The compose e2e journal helper
#: uses the same shape (``tos/runtime/tests/compose/test_marketfeed_wiring.py:54-59``
#: ``_as_of_ms`` — real-clock-relative, a moment before "now").
_JOURNAL_AGE_MS = 1_000

_KST = ZoneInfo("Asia/Seoul")

#: PYTHONPATH for the two runtime subprocesses — the SAME one the boot command uses.
_SUBPROCESS_PYTHONPATH = (
    f"{_REPO_ROOT / 'tos' / 'src'}:{_REPO_ROOT / 'tos' / 'runtime' / 'src'}"
)

#: The runtime CLI entry the design pins (design §2 step 6 / the boot command in §2).
_CLI_BOOTSTRAP = (
    "import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))"
)


class RenderError(RuntimeError):
    """Any refusal. Never carries the account number."""


# ---------------------------------------------------------------------------
# Substitution rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """One key-anchored, exact-line substitution.

    ``anchor`` is the EXACT source line (design §2 step 4: "규칙은 파일마다 키로 앵커된 정확한
    원문 줄") and must occur EXACTLY ONCE in that file — zero or two occurrences refuse. No YAML
    round-trip: re-serializing would drop every header comment and every provenance citation
    those files exist to carry.
    """

    #: Path relative to the config directory.
    file: str
    #: The leaf this rule fills — ``"<file>::<dotted.key>"``. Pinned by the unit tests.
    key: str
    #: The exact source line to replace.
    anchor: str
    #: The replacement text (may be several lines; no trailing newline).
    replacement: str


#: Every coordinate/host-fact slot this script is allowed to touch, by name. The unit test pins
#: this set: ADDING a rule (e.g. one that rewrites a value nobody approved) turns it RED, and a
#: rule whose anchor is not in the source refuses at render time.
COORDINATE_RULE_KEYS: tuple[str, ...] = (
    "venue_constraint_policy.yaml::scope.accounts",
    "venue_constraint_policy.yaml::scope.instruments",
    "order_construction_policy.yaml::scope.accounts",
    "order_construction_policy.yaml::scope.instruments",
    "order_construction_policy.yaml::_runtime.construction.axes.DIRECTION",
    "aggregate_risk_policy.yaml::account_scope",
    "aggregate_risk_policy.yaml::instrument_scope",
    "action_flow_policy.yaml::account_scope",
    "construction.yaml::account",
    "construction.yaml::instrument",
    "construction.yaml::action_class",
    "construction.yaml::outbound_side",
    f"{_STRATEGY_FILE}::policy.rules[0].decision.target.account",
    f"{_STRATEGY_FILE}::policy.rules[0].decision.target.instrument",
    f"{_STRATEGY_FILE}::policy.rules[0].decision.target.direction",
    "marketfeed.yaml::instruments",
    "marketfeed.yaml::account",
    "marketfeed.yaml::direction",
    "marketfeed.yaml::journal_path",
    "finality.yaml::source_revision",
    "safety_activation.yaml::members",
)


def _coordinate_rules(
    *,
    account: str,
    instrument: str,
    revision: str,
    direction: str,
    journal_path: Path,
) -> tuple[Rule, ...]:
    """Phase 1: the coordinate + host-fact substitutions (design §1 table, §2 steps 4-5).

    The DIRECTION-dependent rules are applied for BOTH directions, including ``LONG`` where the
    replacement equals the committed line: the anchor must still be found exactly once, so a
    fixture edit that drops or duplicates the slot refuses instead of silently rendering.
    """
    tokens = _DIRECTION_TOKENS[direction]
    return (
        Rule(
            "venue_constraint_policy.yaml",
            "venue_constraint_policy.yaml::scope.accounts",
            '  accounts: ["TBD"]',
            f'  accounts: ["{account}"]',
        ),
        Rule(
            "venue_constraint_policy.yaml",
            "venue_constraint_policy.yaml::scope.instruments",
            '  instruments: ["TBD"]',
            f'  instruments: ["{instrument}"]',
        ),
        Rule(
            "order_construction_policy.yaml",
            "order_construction_policy.yaml::scope.accounts",
            '  accounts: ["TBD"]',
            f'  accounts: ["{account}"]',
        ),
        Rule(
            "order_construction_policy.yaml",
            "order_construction_policy.yaml::scope.instruments",
            '  instruments: ["TBD"]',
            f'  instruments: ["{instrument}"]',
        ),
        Rule(
            "order_construction_policy.yaml",
            "order_construction_policy.yaml::_runtime.construction.axes.DIRECTION",
            '        value: "LONG"',
            f'        value: "{direction}"',
        ),
        Rule(
            "aggregate_risk_policy.yaml",
            "aggregate_risk_policy.yaml::account_scope",
            'account_scope: ["TBD"]',
            f'account_scope: ["{account}"]',
        ),
        Rule(
            "aggregate_risk_policy.yaml",
            "aggregate_risk_policy.yaml::instrument_scope",
            'instrument_scope: ["TBD"]',
            f'instrument_scope: ["{instrument}"]',
        ),
        Rule(
            "action_flow_policy.yaml",
            "action_flow_policy.yaml::account_scope",
            'account_scope: ["TBD"]',
            f'account_scope: ["{account}"]',
        ),
        Rule(
            "construction.yaml",
            "construction.yaml::account",
            'account: "TBD"',
            f'account: "{account}"',
        ),
        Rule(
            "construction.yaml",
            "construction.yaml::instrument",
            'instrument: "TBD"',
            f'instrument: "{instrument}"',
        ),
        Rule(
            "construction.yaml",
            "construction.yaml::action_class",
            'action_class: "NEW_LONG"',
            f'action_class: "{tokens["action_class"]}"',
        ),
        Rule(
            "construction.yaml",
            "construction.yaml::outbound_side",
            'outbound_side: "BUY"',
            f'outbound_side: "{tokens["side"]}"',
        ),
        Rule(
            _STRATEGY_FILE,
            f"{_STRATEGY_FILE}::policy.rules[0].decision.target.account",
            '          account: "TBD"',
            f'          account: "{account}"',
        ),
        Rule(
            _STRATEGY_FILE,
            f"{_STRATEGY_FILE}::policy.rules[0].decision.target.instrument",
            '          instrument: "TBD"',
            f'          instrument: "{instrument}"',
        ),
        Rule(
            _STRATEGY_FILE,
            f"{_STRATEGY_FILE}::policy.rules[0].decision.target.direction",
            '          direction: "LONG"',
            f'          direction: "{direction}"',
        ),
        Rule(
            "marketfeed.yaml",
            "marketfeed.yaml::instruments",
            "instruments: null",
            f'instruments: ["{instrument}"]',
        ),
        Rule(
            "marketfeed.yaml",
            "marketfeed.yaml::account",
            "account: null",
            f'account: "{account}"',
        ),
        Rule(
            "marketfeed.yaml",
            "marketfeed.yaml::direction",
            'direction: "LONG"',
            f'direction: "{direction}"',
        ),
        Rule(
            "marketfeed.yaml",
            "marketfeed.yaml::journal_path",
            "journal_path: null",
            f'journal_path: "{journal_path}"',
        ),
        Rule(
            "finality.yaml",
            "finality.yaml::source_revision",
            "source_revision: null",
            f'source_revision: "{revision}"',
        ),
    )


def _members_rule(members_block: str) -> Rule:
    """Phase 2: ``safety_activation.yaml::members`` (design §2 step 6).

    Derived from ``print-policy-digests`` against the ALREADY-coordinate-filled output
    directory, never hand-written (adoption plan §2 decision 3): the coordinates go into the
    canonical digest, so this value is host-specific and cannot be committed.
    """
    return Rule(
        "safety_activation.yaml",
        "safety_activation.yaml::members",
        "members: null",
        members_block,
    )


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def parse_account_from_env_file(env_path: Path) -> str:
    """Return ``KIS_FUTURES_ACCOUNT_NO``'s raw value from ``env_path``.

    Parses the file directly — ``os.environ`` is never read or written (design §2 step 2), so
    a stray ambient variable can neither supply nor override this coordinate. Only the one key
    is looked at; every other line is ignored.

    Raises:
        RenderError: the file is missing/unreadable, or the key is absent or empty. The value
            itself is never echoed in any message.
    """
    if not env_path.is_file():
        raise RenderError(f"env file not found: {env_path}")
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RenderError(f"env file could not be read: {env_path}") from exc
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        key, _, raw = stripped.partition("=")
        if key.strip() != ACCOUNT_ENV_KEY:
            continue
        value = raw.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if not value:
            raise RenderError(
                f"{env_path}: {ACCOUNT_ENV_KEY} is present but empty — the deployment "
                "coordinate cannot be rendered"
            )
        return value
    raise RenderError(f"{env_path}: {ACCOUNT_ENV_KEY} is not set")


def normalize_account(raw: str) -> str:
    """Normalize a KIS account number to the form the deployment files carry.

    **Measured (2026-09-23): no tos loader validates the account's FORMAT at all.** Every one
    accepts any non-empty, non-``"TBD"`` string —
    ``tos_runtime/venue/_policy_primitives.py::require_singleton_list_str`` (venue/OCP
    ``scope.accounts``), ``tos_runtime/riskstate/_action_flow_policy_loader.py:471-490``
    (``account_scope``), ``_aggregate_risk_policy_loader`` (same), and
    ``tos_runtime/compose/_construction_config.py::_require_str`` (``construction.yaml``).
    What IS enforced is cross-file EQUALITY (``compose/_venue_wiring.py:139-142``,
    ``compose/_riskstate_wiring.py:86-89``). So the hyphen question is settled here, once, and
    the same normalized string goes into every slot.

    The normalization is **digits only, all ten of them** — the one normalization this repo
    already performs on this value (``shared/kis/client.py`` ``_normalize_account``:
    "Normalize account number to digits-only 10-char format"), and the form
    ``tools/broker_probes/common.py`` splits into ``cano = [:8]`` / ``acnt_prdt_cd = [8:10]``.
    The trailing two digits are the product code (``03`` for 선물옵션), which is what makes
    this the FUTURES account rather than another product on the same 종합계좌 — dropping them
    would make the coordinate ambiguous.

    ⚠ **Open point for the KIS mock handover, deliberately not decided here.** The (still
    operator-unapproved) transport proposal maps this single coordinate onto the KIS wire field
    ``CANO`` alone, with ``ACNT_PRDT_CD`` as a separate static field
    (``docs/runbooks/tos-kis-mock-transport.md:97,101`` — that table's own header says the
    values await operator approval). If that mapping is adopted as-is, this coordinate becomes
    the 8-digit CANO. Under the adopted ``SYNTHETIC_FUTURES_ORDER`` scope nothing reaches a
    broker, so the choice is reversible by re-rendering; it is flagged rather than silently
    pre-empted.

    Raises:
        RenderError: the value does not carry exactly ten digits. The value is never echoed.
    """
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) != ACCOUNT_DIGITS:
        raise RenderError(
            f"account coordinate refused: expected exactly {ACCOUNT_DIGITS} digits after "
            f"stripping non-digits, got {len(digits)} (value withheld — account numbers are "
            "never printed)"
        )
    return digits


def _git_revision(source_checkout: Path) -> str:
    """The source checkout's ``git rev-parse HEAD`` (design §2 step 5 —
    ``finality.yaml::source_revision``; the 2026-09-12 value table calls this "배포 git SHA"
    but grades it M, and a commit cannot contain its own SHA, so it is a render-time fact).
    """
    try:
        completed = subprocess.run(
            ["git", "-C", str(source_checkout), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RenderError(f"git rev-parse failed: {exc}") from exc
    if completed.returncode != 0:
        raise RenderError(
            "git rev-parse HEAD refused in "
            f"{source_checkout}: {completed.stderr.strip() or completed.returncode}"
        )
    revision = completed.stdout.strip()
    if not revision:
        raise RenderError(f"git rev-parse HEAD produced no output in {source_checkout}")
    return revision


def _repo_root_of(path: Path) -> Path | None:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return Path(completed.stdout.strip()).resolve()


def _is_within(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


def _refuse_output_inside_repo(out: Path, source: Path) -> None:
    """Design §2 guard "출력이 저장소 밖": a config directory holding the account number must
    not live inside a git worktree — one missing ``.gitignore`` line would commit it."""
    roots = {_REPO_ROOT}
    for candidate in (_repo_root_of(source), _repo_root_of(out.parent)):
        if candidate is not None:
            roots.add(candidate)
    for root in roots:
        if _is_within(out, root):
            raise RenderError(
                f"output directory refused: {out} is inside the repository worktree {root} — "
                "the rendered config carries the account coordinate and must live outside it"
            )
    if _is_within(out, source.resolve()):
        raise RenderError(
            f"output directory refused: {out} is inside the source directory {source}"
        )


def _apply_rules(config_dir: Path, rules: Iterable[Rule]) -> None:
    """Apply each rule, requiring EXACTLY ONE anchor match per rule (design §2 guard
    "칸마다 정확히 1회 매칭")."""
    for rule in rules:
        path = config_dir / rule.file
        if not path.is_file():
            raise RenderError(f"substitution target missing: {path} (rule {rule.key})")
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")
        matches = [i for i, line in enumerate(lines) if line == rule.anchor]
        if len(matches) != 1:
            raise RenderError(
                f"rule {rule.key}: anchor line {rule.anchor!r} matched {len(matches)} times "
                f"in {rule.file} — exactly one is required"
            )
        lines[matches[0]] = rule.replacement
        path.write_text("\n".join(lines), encoding="utf-8")


def _subprocess_env() -> dict[str, str]:
    """The allowlisted environment for the two runtime subprocesses.

    ``PYTHONDONTWRITEBYTECODE`` (with ``python -B``) keeps ``__pycache__`` out of the source
    tree — a rendered run must leave the repository byte-identical, and ``__pycache__`` is
    gitignored, so ``git status --porcelain --ignored`` would otherwise show it.

    ``PYTHONHASHSEED`` is passed through when the CALLER set it, and only then. It exists in
    this allowlist because of a measured defect, not as a feature: see this module's
    ``NOT REPRODUCIBLE`` note on :func:`_policy_digest_lines`.
    """
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": _SUBPROCESS_PYTHONPATH,
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": str(Path.home()),
    }
    seed = os.environ.get("PYTHONHASHSEED")
    if seed:
        env["PYTHONHASHSEED"] = seed
    return env


def _run_runtime_cli(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run the ``tos_runtime`` CLI as a SUBPROCESS (this file may not import it — module
    docstring), with bytecode writing disabled so nothing lands next to the source tree.
    """
    return subprocess.run(
        [sys.executable, "-B", "-c", _CLI_BOOTSTRAP, *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
        env=_subprocess_env(),
    )


def _policy_digest_lines(config_dir: Path) -> tuple[tuple[str, str, int, str], ...]:
    """``print-policy-digests --config-dir <config_dir>`` → ``(kind, member_id, generation,
    digest)`` per printed line (design §2 step 6; the printer is
    ``compose/cli.py::_dispatch_print_policy_digests`` + ``compose/_cli_ops.py:91-145``).

    ⚠ **NOT REPRODUCIBLE across processes for VENUE_CONSTRAINT_POLICY (measured 2026-09-23).**
    ``VenueConstraintPolicy._COVERED_FIELDS`` (``tos/src/tos/venue/records.py:406-416``)
    includes ``required_constraint_classes: frozenset[ConstraintClass]`` (``:424``) and
    ``shape_constraints``, whose ``allowed_order_types``/``allowed_tifs``/``allowed_sides``/
    ``allowed_position_effects`` are frozensets too (``:165-168``).
    ``covered_content()`` is ``model_dump(mode="json", …)``
    (``tos/src/tos/canonical/_base.py:187``), which renders a frozenset as a LIST in
    set-iteration order, and ``_encode`` treats a sequence as ORDER-SIGNIFICANT
    ("sequence order is preserved (vectors are order-significant)",
    ``tos/src/tos/canonical/canonicalization.py:148-149,174-176``). ``ConstraintClass`` is a
    ``StrEnum`` (``tos/src/tos/venue/vocabulary.py:169``), so its iteration order follows
    Python's per-process string hash seed: the same file digests differently in every process.

    The other four printed kinds are stable — their covered fields carry no set.

    Consequence: the documented operator procedure (run ``print-policy-digests``, copy the
    digests into ``safety_activation.yaml::members``) cannot work for this one kind, because it
    is a CROSS-PROCESS transcription. :func:`_verify_activation` therefore re-derives in a
    fresh process and refuses here rather than letting the boot fail later.
    """
    completed = _run_runtime_cli(
        ["print-policy-digests", "--config-dir", str(config_dir)]
    )
    if completed.returncode != 0:
        raise RenderError(
            "print-policy-digests refused against the rendered directory "
            f"(exit {completed.returncode}):\n{completed.stderr.strip()}"
        )
    parsed: list[tuple[str, str, int, str]] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 4:
            raise RenderError(
                f"print-policy-digests line not understood: {line!r} (expected "
                "'<KIND> <policy_id> <generation> <digest>')"
            )
        kind, member_id, generation, digest = parts
        try:
            generation_int = int(generation)
        except ValueError as exc:
            raise RenderError(
                f"print-policy-digests line has a non-integer generation: {line!r}"
            ) from exc
        parsed.append((kind, member_id, generation_int, digest))
    printed_kinds = {kind for kind, _id, _gen, _digest in parsed}
    missing = [kind for kind in MANDATORY_POLICY_KINDS if kind not in printed_kinds]
    if missing:
        raise RenderError(
            "print-policy-digests did not print every policy kind this deployment "
            f"activates — missing {missing!r} (printed {sorted(printed_kinds)!r})"
        )
    if len(printed_kinds) != len(parsed):
        raise RenderError(
            f"print-policy-digests printed {len(parsed)} lines for "
            f"{len(printed_kinds)} distinct kinds — one line per kind is expected"
        )
    return tuple(parsed)


def _members_block(
    entries: Sequence[tuple[str, str, int, str]], *, rendered_at: str
) -> str:
    """The ``members:`` YAML block.

    Six fields per entry (``tos/src/tos/spg/records.py::BundleMemberRef`` via
    ``tos_runtime/venue/activation.py``): ``kind``/``member_id``/``generation``/``digest`` are
    transcribed from the printed line; ``resolved``/``immutable`` are NOT printed and are
    written as the constants every policy file's own header prescribes (e.g.
    ``venue_constraint_policy.yaml:36-37`` "resolved: true, immutable: true").
    """
    lines = [
        "members:",
        f"  # RENDERED {rendered_at} by scripts/tos/render_paper_config.py — derived from",
        "  # `print-policy-digests --config-dir <this dir>` against the coordinate-filled",
        "  # copy. Host-specific (the coordinates are inside each canonical digest): NEVER",
        "  # commit this block. `resolved`/`immutable` are the constants the policy files'",
        "  # own headers prescribe; they are not printed by the command.",
    ]
    for kind, member_id, generation, digest in entries:
        lines.extend(
            [
                f'  - kind: "{kind}"',
                f'    member_id: "{member_id}"',
                f"    generation: {generation}",
                f'    digest: "{digest}"',
                "    resolved: true",
                "    immutable: true",
            ]
        )
    return "\n".join(lines)


#: Design §2 step 6's end-check, run in a FRESH process.
#:
#: It deliberately RE-LOADS every policy through its own loader and activates against the
#: digest THAT load computes — it does not merely re-check the digests the printing process
#: already emitted. That distinction is the whole point: ``compose`` at boot is a third,
#: different process that recomputes each ``canonical_digest`` and calls
#: ``require_member_activated`` with ITS value (``compose/_venue_wiring.py:265-278``,
#: ``compose/_riskstate_wiring.py:236-250``). A read-back that trusted the printed digests
#: would pass while the boot refused — the documented operator procedure ("run
#: print-policy-digests, copy the digests into members") is a CROSS-PROCESS transcription, so
#: the check has to be cross-process too.
_VERIFY_ACTIVATION = """
import sys, json
from pathlib import Path
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.spg import BundleMemberKind
from tos_runtime.marketfeed.policy import load_critical_input_policy
from tos_runtime.riskstate.policies import (
    load_action_flow_policy,
    load_aggregate_risk_policy,
)
from tos_runtime.venue import (
    load_order_construction_policy,
    load_venue_constraint_policy,
)
from tos_runtime.venue.activation import (
    load_activation_members,
    require_member_activated,
)

config_dir = Path(sys.argv[1])
expected_count = int(sys.argv[2])
scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _venue():
    loaded = load_venue_constraint_policy(
        config_dir / "venue_constraint_policy.yaml", scheme=scheme
    )
    p = loaded.policy
    return (p.policy_id, p.policy_generation, p.canonical_digest)


def _ocp():
    loaded = load_order_construction_policy(
        config_dir / "order_construction_policy.yaml", scheme=scheme
    )
    p = loaded.policy
    return (p.policy_id, p.policy_generation, p.canonical_digest)


def _are():
    loaded = load_aggregate_risk_policy(
        config_dir / "aggregate_risk_policy.yaml", scheme=scheme
    )
    p = loaded.policy
    return (p.policy_id, p.policy_generation, p.canonical_digest)


def _afg():
    loaded = load_action_flow_policy(
        config_dir / "action_flow_policy.yaml", scheme=scheme
    )
    p = loaded.policy
    return (p.policy_id, p.policy_generation, p.canonical_digest)


def _cip():
    loaded = load_critical_input_policy(
        config_dir / "critical_input_policy.yaml", scheme=scheme
    )
    return (loaded.policy_id, loaded.policy_generation, loaded.canonical_digest)


RELOADERS = {
    "VENUE_CONSTRAINT_POLICY": _venue,
    "ORDER_CONSTRUCTION_POLICY": _ocp,
    "AGGREGATE_RISK_POLICY": _are,
    "ACTION_FLOW_POLICY": _afg,
    "CRITICAL_INPUT_POLICY": _cip,
}

members = load_activation_members(config_dir / "safety_activation.yaml")
if len(members) != expected_count:
    raise SystemExit(
        f"members has {len(members)} entries, expected {expected_count}"
    )
for kind, reload_policy in RELOADERS.items():
    member_id, generation, digest = reload_policy()
    require_member_activated(
        members,
        kind=BundleMemberKind(kind),
        member_id=member_id,
        generation=generation,
        digest=digest,
    )
print(f"ACTIVATED {len(members)} (re-derived in a fresh process)")
"""


def _verify_activation(
    config_dir: Path, entries: Sequence[tuple[str, str, int, str]]
) -> str:
    """Design §2 step 6 end-check, in a FRESH process: re-load every policy, recompute its
    ``canonical_digest``, and require that digest to be activated by the block just written.

    This is what ``compose`` itself does at boot. A render whose members block only matches the
    printing process's own digests is not a rendered deployment — it is one that will refuse at
    boot, later and further away. See :data:`_VERIFY_ACTIVATION`."""
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            _VERIFY_ACTIVATION,
            str(config_dir),
            str(len(entries)),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
        env=_subprocess_env(),
    )
    if completed.returncode != 0:
        raise RenderError(
            "activation read-back refused — the rendered members block is not activated "
            f"(exit {completed.returncode}):\n"
            f"{(completed.stderr or completed.stdout).strip()}"
        )
    return completed.stdout.strip()


def _write_journal(path: Path, *, instrument: str, now_ms: int) -> int:
    """Write the one-observation boot-proof journal (design §4 5항 — a render-time GENERATED
    tick source, never a network one; the intake is
    ``tos_runtime/marketfeed/journal.py::JsonLinesObservationJournal``, which opens no socket).

    The line shape is the one the compose e2e suite's own journal helper writes
    (``tos/runtime/tests/compose/test_marketfeed_wiring.py:130-155``).
    """
    as_of_ms = now_ms - _JOURNAL_AGE_MS
    line = json.dumps(
        {
            "raw_event_id": "bootproof-1",
            "instrument": instrument,
            "as_of_ms": as_of_ms,
            "fields": {
                "close": _JOURNAL_CLOSE,
                "lower_band": _JOURNAL_LOWER_BAND,
                "upper_band": _JOURNAL_UPPER_BAND,
            },
            "source_id": "tos-paper-bootproof-render",
            "received_ms": as_of_ms,
        },
        sort_keys=True,
    )
    path.write_text(line + "\n", encoding="utf-8")
    return as_of_ms


# ---------------------------------------------------------------------------
# render / check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RenderResult:
    """What one render produced. Carries NO account number — only its fingerprint."""

    out: Path
    source: Path
    revision: str
    direction: str
    instrument: str
    account_fingerprint: str
    rendered_keys: tuple[str, ...]
    policy_digests: tuple[tuple[str, str, int, str], ...]
    activation_check: str
    journal_path: Path
    journal_as_of_ms: int
    rendered_at_kst: str


def render(
    source: Path,
    out: Path,
    *,
    account: str,
    instrument: str,
    revision: str,
    direction: str = "LONG",
    now_ms: int | None = None,
) -> RenderResult:
    """Byte-copy ``source`` to ``out`` and fill exactly the coordinate slots.

    This function reads NO env file and touches NO ``os.environ`` (design §2 guard "계좌
    원천이 모의 파일" — the env-file rule lives in :func:`main`, and the tests drive this
    function with a fake account so no real value ever reaches a test).

    Args:
        source: The committed values directory (``config/tos_runtime/paper``).
        out: The OFF-REPO output directory.
        account: The already-normalized account coordinate.
        instrument: The contract code coordinate.
        revision: ``finality.yaml::source_revision``.
        direction: ``LONG`` or ``SHORT`` (design §3 choice (가) — both are booted).
        now_ms: Wall-clock milliseconds for the generated journal; defaults to now.

    Raises:
        RenderError: any refusal — bad direction, an output path inside the repo, an anchor
            that did not match exactly once, a refused ``print-policy-digests``, or an
            activation read-back that does not see every member.
    """
    if direction not in _DIRECTION_TOKENS:
        raise RenderError(
            f"direction refused: {direction!r} — expected one of "
            f"{sorted(_DIRECTION_TOKENS)!r}"
        )
    if not account or not account.strip():
        raise RenderError("account coordinate refused: empty")
    if not instrument or not instrument.strip():
        raise RenderError("instrument coordinate refused: empty")
    source = source.resolve()
    if not source.is_dir():
        raise RenderError(f"source directory not found: {source}")
    out = out.expanduser()
    out = (out if out.is_absolute() else Path.cwd() / out).resolve()
    _refuse_output_inside_repo(out, source)

    if out.exists():
        if any(out.iterdir()) and not (out / RENDERED_NAME).is_file():
            raise RenderError(
                f"output directory refused: {out} is not empty and carries no "
                f"{RENDERED_NAME} — refusing to overwrite a directory this script did not "
                "render"
            )
        shutil.rmtree(out)
    shutil.copytree(source, out)
    out.chmod(0o700)

    now = (
        datetime.now(tz=_KST)
        if now_ms is None
        else datetime.fromtimestamp(now_ms / 1000, tz=_KST)
    )
    effective_now_ms = int(now.timestamp() * 1000)
    journal_path = out / JOURNAL_NAME
    journal_as_of_ms = _write_journal(
        journal_path, instrument=instrument, now_ms=effective_now_ms
    )

    rules = _coordinate_rules(
        account=account,
        instrument=instrument,
        revision=revision,
        direction=direction,
        journal_path=journal_path,
    )
    _apply_rules(out, rules)

    digests = _policy_digest_lines(out)
    rendered_at = now.isoformat()
    members = _members_rule(_members_block(digests, rendered_at=rendered_at))
    _apply_rules(out, (members,))
    activation_check = _verify_activation(out, digests)

    rendered_keys = tuple(rule.key for rule in rules) + (members.key,)
    if set(rendered_keys) != set(COORDINATE_RULE_KEYS):
        raise RenderError(
            "rendered key set does not match COORDINATE_RULE_KEYS — "
            f"{sorted(set(rendered_keys) ^ set(COORDINATE_RULE_KEYS))!r}"
        )
    fingerprint = account_fingerprint(account)
    result = RenderResult(
        out=out,
        source=source,
        revision=revision,
        direction=direction,
        instrument=instrument,
        account_fingerprint=fingerprint,
        rendered_keys=rendered_keys,
        policy_digests=digests,
        activation_check=activation_check,
        journal_path=journal_path,
        journal_as_of_ms=journal_as_of_ms,
        rendered_at_kst=rendered_at,
    )
    (out / RENDERED_NAME).write_text(
        json.dumps(
            {
                "rendered_at_kst": rendered_at,
                "source_dir": str(source),
                "source_revision": revision,
                "direction": direction,
                "instrument": instrument,
                "account_fingerprint": fingerprint,
                "rendered_keys": list(rendered_keys),
                "policy_digests": [
                    {
                        "kind": kind,
                        "member_id": member_id,
                        "generation": generation,
                        "digest": digest,
                    }
                    for kind, member_id, generation, digest in digests
                ],
                "activation_check": activation_check,
                "journal_path": str(journal_path),
                "journal_as_of_ms": journal_as_of_ms,
                "note": (
                    "boot-proof fixture render — 거래 전략 아님. The account number itself is "
                    "never recorded here, only its fingerprint."
                ),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return result


def _relative_files(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}


def check(source: Path, out: Path) -> list[str]:
    """Design §2 step 8: return the list of problems — empty means "the rendered directory
    differs from the committed source ONLY at the registered coordinate slots".

    Line-level: every non-equal diff hunk must be a ``replace`` whose SOURCE lines are all
    registered rule anchors (adjacent anchors — e.g. ``construction.yaml``'s ``account`` and
    ``instrument`` — merge into one hunk, which is why the check is per-line-within-the-hunk
    rather than one-line-per-hunk). A hand edit anywhere else, a pure insertion or deletion, an
    extra file, or a missing file is reported by name.
    """
    source = source.resolve()
    out = out.expanduser().resolve()
    problems: list[str] = []
    if not out.is_dir():
        return [f"output directory not found: {out}"]

    source_files = _relative_files(source)
    out_files = _relative_files(out)
    for extra in sorted(out_files - source_files - _GENERATED_NAMES):
        problems.append(f"unexpected file in the rendered directory: {extra}")
    for missing in sorted(source_files - out_files):
        problems.append(f"file missing from the rendered directory: {missing}")
    for required in sorted(_GENERATED_NAMES):
        if required not in out_files:
            problems.append(f"render artifact missing: {required}")

    anchors_by_file: dict[str, set[str]] = {}
    for key in COORDINATE_RULE_KEYS:
        file_name = key.split("::", 1)[0]
        anchors_by_file.setdefault(file_name, set())
    for rule in _coordinate_rules(
        account="RENDERED",
        instrument="RENDERED",
        revision="RENDERED",
        direction="LONG",
        journal_path=Path("RENDERED"),
    ) + (_members_rule("members: RENDERED"),):
        anchors_by_file.setdefault(rule.file, set()).add(rule.anchor)

    for name in sorted(source_files & out_files):
        source_lines = (source / name).read_text(encoding="utf-8").split("\n")
        out_lines = (out / name).read_text(encoding="utf-8").split("\n")
        anchors = anchors_by_file.get(name, set())
        matcher = difflib.SequenceMatcher(a=source_lines, b=out_lines, autojunk=False)
        for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            if tag != "replace":
                problems.append(
                    f"{name}: line(s) {i1 + 1}-{i2} changed outside any coordinate slot "
                    f"({tag})"
                )
                continue
            for index in range(i1, i2):
                if source_lines[index] not in anchors:
                    problems.append(
                        f"{name}:{index + 1}: changed line is not a registered coordinate "
                        f"slot ({source_lines[index]!r})"
                    )
    return problems


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="render_paper_config.py",
        description=(
            "Render config/tos_runtime/paper into an OFF-REPO directory with this host's "
            "deployment coordinates filled in (design 2026-09-23 §2)."
        ),
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="committed values directory (default: %(default)s)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="output directory, OUTSIDE the repository (default: %(default)s)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=_REPO_ROOT / ENV_FILE_NAME,
        help=(
            f"the mock env file supplying {ACCOUNT_ENV_KEY}; its basename must be exactly "
            f"{ENV_FILE_NAME!r} (default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--instrument",
        default=None,
        help=(
            "override the contract code (default: "
            "shared.instruments.futures.get_front_month_code(product='mini') for today)"
        ),
    )
    parser.add_argument(
        "--direction",
        choices=sorted(_DIRECTION_TOKENS),
        default="LONG",
        help="boot-proof fixture direction (default: %(default)s)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "do not render; verify an existing --out differs from --source only at the "
            "registered coordinate slots (exit 0 clean, 1 otherwise)"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Exit codes: ``0`` ok, ``1`` refusal, ``2`` bad arguments."""
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.check:
        problems = check(args.source, args.out)
        for problem in problems:
            print(f"render_paper_config --check: {problem}", file=sys.stderr)
        if problems:
            return 1
        print(f"render_paper_config --check: {args.out} matches {args.source}")
        return 0

    env_file = Path(args.env_file)
    if env_file.name != ENV_FILE_NAME:
        parser.error(
            f"--env-file must name a file called {ENV_FILE_NAME!r} (got {env_file.name!r}). "
            "The real .env carries the REAL futures account, which this repo's non-negotiable "
            "rules keep off every order path — it is never a coordinate source."
        )

    try:
        account = normalize_account(parse_account_from_env_file(env_file))
        instrument = args.instrument or get_front_month_code(product="mini")
        revision = _git_revision(Path(args.source).resolve())
        result = render(
            Path(args.source),
            Path(args.out),
            account=account,
            instrument=instrument,
            revision=revision,
            direction=args.direction,
        )
    except RenderError as exc:
        print(f"render_paper_config: refused — {exc}", file=sys.stderr)
        return 1

    print(f"rendered: {result.out}")
    print(f"  source_revision: {result.revision}")
    print(f"  direction:       {result.direction}")
    print(f"  instrument:      {result.instrument}")
    print(f"  account:         <withheld> fingerprint={result.account_fingerprint}")
    print(
        f"  journal:         {result.journal_path} (as_of_ms={result.journal_as_of_ms})"
    )
    print(f"  activation:      {result.activation_check}")
    for kind, member_id, generation, digest in result.policy_digests:
        print(f"  digest:          {kind} {member_id} {generation} {digest}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
