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

Which slots, and in what mode, is NOT hard-coded here
-----------------------------------------------------
Each renderable tree commits its own ``RENDER.yaml`` manifest next to its values
(``docs/plans/2026-10-09-tos-cp3-tenant-render-and-boot-path-plan.md`` §2.1). It declares the
slot list, how DIRECTION is handled (``substitute`` — the resident behaviour, ``--direction``
rewrites the direction slots; ``declared`` — a tenant tree committed per direction, where
those slots are verified rather than rewritten, §2.3), and where the observation journal comes
from (``synthetic_bootproof`` — written here; ``external`` — produced elsewhere and named by
``--journal-path``, §2.4). A manifest may not carry a VALUE: each slot names a source out of a
closed set, and its ``replacement`` template is shape-checked so it cannot smuggle a literal in
(:func:`_validate_replacement_template`). ``safety_activation.yaml::members`` stays out of the
manifest entirely — it is always derived from ``print-policy-digests``.

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
(``tools/broker_probes/common.py:220-225``, the same correlator every broker probe artifact
carries).

⚠ **That fingerprint is a correlator, not a masking primitive** (review-797 LOW-3). It is an
UNSALTED SHA-256 truncated to 12 hex chars over a 10-digit input, so the input space is 10^10
and the value is trivially reversible by brute force. It is used here for the same reason the
probe harness uses it — so two artifacts about the same account can be tied together without
writing the number — and it is deliberately kept out of the repository: it appears only on
stdout and in ``RENDERED.json`` inside the 0700 off-repo output directory. Treat a leaked
fingerprint as a leaked account number. (The probe harness does record it in committed
evidence artifacts; that precedent is about correlating measurements, not about the value
being safe to publish.)

``.env`` / ``.env.real`` are REFUSED as a coordinate source: that file's futures account is
the REAL account, and this repo's non-negotiable rule is that the real futures account is
never funded and never on an order path.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:  # direct-script invocation
    sys.path.insert(0, str(_REPO_ROOT))

from shared.instruments.futures import get_front_month_code  # noqa: E402
from tools.broker_probes.common import account_fingerprint  # noqa: E402

__all__ = [
    "COORDINATE_RULE_KEYS",
    "MANDATORY_POLICY_KINDS",
    "RENDER_MANIFEST_NAME",
    "RenderError",
    "RenderManifest",
    "RenderResult",
    "Slot",
    "check",
    "load_manifest",
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

#: The per-tree RENDER manifest this script reads out of ``--source`` (design 2026-10-09
#: §2.1). It is COMMITTED next to the values it describes and is byte-copied into the output
#: directory like every other source file (§7) — no runtime reads it there.
RENDER_MANIFEST_NAME = "RENDER.yaml"

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


#: Every coordinate/host-fact slot the RESIDENT tree carries, by name.
#:
#: ⚠ **Transition reference** (design 2026-10-09 §4.1 item 1). Since the slot table moved into
#: the per-tree ``RENDER.yaml`` manifest, this tuple and :func:`_coordinate_rules` below are no
#: longer what :func:`render` executes — the manifest is. They are kept for exactly one job:
#: ``tests/unit/scripts/test_render_paper_config.py`` asserts the manifest-built ``Rule`` tuple
#: equals this one, which is how "the resident render did not change" is checkable rather than
#: claimed. The follow-up PR deletes both, and the per-tree expected-slot literal in that same
#: test file (full ``(file, key, anchor, replacement)`` tuples) takes over the pin.
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

    ⚠ **Transition reference only** — see :data:`COORDINATE_RULE_KEYS`. :func:`render` builds its
    rules from ``<source>/RENDER.yaml`` via :func:`_slot_rules`; this function is what the unit
    test compares that result against, and nothing else calls it.
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
            'instruments: ["TBD"]',
            f'instruments: ["{instrument}"]',
        ),
        Rule(
            "marketfeed.yaml",
            "marketfeed.yaml::account",
            'account: "TBD"',
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
            'journal_path: "TBD"',
            f'journal_path: "{journal_path}"',
        ),
        Rule(
            "finality.yaml",
            "finality.yaml::source_revision",
            "source_revision: null",
            f'source_revision: "{revision}"',
        ),
    )


# ---------------------------------------------------------------------------
# The per-tree render manifest (design 2026-10-09 §2.1)
# ---------------------------------------------------------------------------

#: The ONE placeholder a ``replacement`` template may carry.
_PLACEHOLDER = "{value}"

#: The CLOSED set of value sources a slot may name. A manifest cannot carry a literal value —
#: that is what preserved the property the hard-coded :data:`COORDINATE_RULE_KEYS` pin had
#: ("a rule that writes a value nobody approved cannot appear"), now that the table is data
#: (design §2.1).
_VALUE_SOURCES: frozenset[str] = frozenset(
    {
        "account",
        "instrument",
        "revision",
        "journal_path",
        "direction_action_class",
        "direction_side",
        "direction",
    }
)

#: The subset of :data:`_VALUE_SOURCES` whose value is a function of DIRECTION. In
#: ``declared`` mode these slots are VERIFY-ONLY (design §2.3): the renderer builds the line
#: from the manifest's declared direction and requires it to be present, unchanged, exactly
#: once. Without them a declared-mode tree would have no direction check at all — the review's
#: H1 finding.
_DIRECTION_VALUE_SOURCES: frozenset[str] = frozenset(
    {"direction_action_class", "direction_side", "direction"}
)

#: ``substitute`` = the resident behaviour (``--direction`` rewrites the direction slots).
#: ``declared`` = a tenant tree committed per direction; ``--direction`` is compared, not applied.
_DIRECTION_MODES: tuple[str, ...] = ("substitute", "declared")

#: ``synthetic_bootproof`` = the renderer writes the boot-proof journal itself (resident).
#: ``external`` = the journal comes from the ③ producer; ``--journal-path`` is REQUIRED and the
#: renderer writes no journal at all (design §2.4, fail-closed).
_JOURNAL_MODES: tuple[str, ...] = ("synthetic_bootproof", "external")

#: One YAML anchor token, the single exception rule ④ below allows inside a template.
_YAML_ANCHOR_TOKEN = re.compile(r"&[A-Za-z_][A-Za-z0-9_]*")

#: Everything rule ④ tolerates OUTSIDE the placeholder, the key prefix and the anchor token.
#: Deliberately not a superset: a comma, a letter or a digit here is a literal being smuggled
#: into a template, which is the one thing the closed value set exists to prevent.
_TEMPLATE_FILLER: frozenset[str] = frozenset("\"'[] \t")


@dataclass(frozen=True)
class Slot:
    """One manifest slot — the data form of a :class:`Rule`, with the VALUE left as a source
    name rather than a value."""

    #: Path relative to the tree.
    file: str
    #: ``"<file>::<dotted.key>"``'s dotted half; the full key is ``f"{file}::{key}"``.
    key: str
    #: The exact source line to replace (or, for a verify-only direction slot, to require).
    anchor: str
    #: The replacement TEMPLATE — exactly one ``{value}``, shape-checked by rules ①–④.
    replacement: str
    #: A member of :data:`_VALUE_SOURCES`.
    value: str

    @property
    def rule_key(self) -> str:
        return f"{self.file}::{self.key}"


@dataclass(frozen=True)
class RenderManifest:
    """``<tree>/RENDER.yaml``, validated."""

    tree_id: str
    direction_mode: str
    #: Only set (and only meaningful) in ``declared`` mode.
    direction_value: str | None
    journal_mode: str
    slots: tuple[Slot, ...]


def _generated_names(journal_mode: str) -> frozenset[str]:
    """Files the output directory carries that the source does not — i.e. what :func:`render`
    GENERATES, and therefore exactly what :func:`check` both requires and tolerates.

    Mode-dependent since design §7: ``external`` renders write no journal, so requiring
    ``bootproof_journal.jsonl`` would make ``--check`` report "render artifact missing" against
    every correct tenant render.
    """
    if journal_mode == "synthetic_bootproof":
        return frozenset({JOURNAL_NAME, RENDERED_NAME})
    return frozenset({RENDERED_NAME})


def _key_prefix(line: str) -> str | None:
    """``"  accounts:"`` for ``'  accounts: ["TBD"]'`` — up to and INCLUDING the first colon.

    ``None`` when the line carries no colon, which is not a YAML key line at all.
    """
    head, sep, _tail = line.partition(":")
    return head + sep if sep else None


def _anchor_token(tail: str) -> str | None:
    """The one YAML anchor token immediately after a key prefix, or ``None``.

    "Immediately after" means only whitespace separates it from the colon — an ``&name`` later
    in the line is not this exception and falls through to rule ④, which refuses it.
    """
    match = _YAML_ANCHOR_TOKEN.search(tail)
    if match is None or tail[: match.start()].strip() != "":
        return None
    return match.group()


def _validate_replacement_template(*, key: str, anchor: str, template: str) -> None:
    """Rules ①–④ of design §2.1 — the shape check that keeps a template from carrying a value.

    The point is NOT formatting hygiene. ``COORDINATE_RULE_KEYS`` used to be a code constant,
    so "this table may only write approved coordinates" was true because a human reviewed the
    code. With the table as data, that property has to be mechanical, and these four rules are
    it: a template may re-shape the line around the value (quotes, a list bracket, a YAML
    anchor) and may do nothing else.

    ① exactly one ``{value}``; ② no other brace; ③ the template's key prefix is byte-identical
    to the anchor's, and the placeholder lies after it; ④ what is left, once the key prefix, the
    placeholder and at most one YAML anchor token are removed, is quotes/brackets/whitespace
    only — and that anchor token must be BYTE-IDENTICAL to the anchor line's.

    Concrete inputs this refuses:

    * ``replacement: '  instruments: ["{value}", "A05610"]'`` — a literal instrument rides along
      with the coordinate (rule ④);
    * ``replacement: '          account: &acct "{value}"'`` against anchor
      ``'          account: &account "TBD"'`` — the rendered line would define an anchor nobody
      aliases, so every ``*account`` alias in the file dangles (rule ④'s byte-identity half);
    * ``replacement: '  tick_size: {value}'`` against anchor ``'  accounts: ["TBD"]'`` — the
      slot has been re-aimed at a different leaf (rule ③).
    """
    occurrences = template.count(_PLACEHOLDER)
    if occurrences != 1:
        raise RenderError(
            f"slot {key}: replacement template must carry exactly one {_PLACEHOLDER} "
            f"placeholder, found {occurrences} — {template!r}"
        )
    without_placeholder = template.replace(_PLACEHOLDER, "", 1)
    if "{" in without_placeholder or "}" in without_placeholder:
        raise RenderError(
            f"slot {key}: replacement template carries a brace outside the "
            f"{_PLACEHOLDER} placeholder — {template!r}"
        )

    anchor_prefix = _key_prefix(anchor)
    template_prefix = _key_prefix(template)
    if anchor_prefix is None:
        raise RenderError(f"slot {key}: anchor line carries no key — {anchor!r}")
    if template_prefix is None or template_prefix != anchor_prefix:
        raise RenderError(
            f"slot {key}: replacement template's key prefix {template_prefix!r} does not match "
            f"the anchor's {anchor_prefix!r} — the slot has been re-aimed at a different leaf"
        )
    if template.index(_PLACEHOLDER) < len(template_prefix):
        raise RenderError(
            f"slot {key}: the {_PLACEHOLDER} placeholder sits inside the key prefix — "
            f"{template!r}"
        )

    template_tail = template[len(template_prefix) :]
    anchor_tail = anchor[len(anchor_prefix) :]
    template_token = _anchor_token(template_tail)
    anchor_token = _anchor_token(anchor_tail)
    if template_token != anchor_token:
        raise RenderError(
            f"slot {key}: the YAML anchor token differs between the anchor line "
            f"({anchor_token!r}) and the replacement template ({template_token!r}) — the one "
            "token rule ④ allows must be byte-identical in both"
        )
    residue = template_tail.replace(_PLACEHOLDER, "", 1)
    if template_token is not None:
        residue = residue.replace(template_token, "", 1)
    stray = sorted({char for char in residue if char not in _TEMPLATE_FILLER})
    if stray:
        raise RenderError(
            f"slot {key}: replacement template carries literal characters {stray!r} outside the "
            f"{_PLACEHOLDER} placeholder — a template may re-shape the line around the value, "
            f"never supply one ({template!r})"
        )


def _require_str(raw: Any, *, where: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise RenderError(f"{where}: expected a non-empty string, got {raw!r}")
    return raw


def load_manifest(tree: Path) -> RenderManifest:
    """Read and validate ``<tree>/RENDER.yaml`` (design §2.1).

    Every refusal here is a refusal to render — the manifest is the whole rule table, so an
    unvalidated one is an unvalidated render.

    Raises:
        RenderError: the file is missing/unparseable, a mode is not one of the two declared
            ones, a slot names a value source outside the closed set, two slots share a key, a
            slot's target file is absent from the tree, or a replacement template fails rules
            ①–④.
    """
    path = tree / RENDER_MANIFEST_NAME
    if not path.is_file():
        raise RenderError(
            f"render manifest not found: {path} — every tree this script renders must commit "
            f"its own {RENDER_MANIFEST_NAME} (design 2026-10-09 §2.1)"
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RenderError(f"render manifest could not be read: {path} ({exc})") from exc
    if not isinstance(raw, dict):
        raise RenderError(
            f"{path}: expected a mapping at the top level, got {type(raw)}"
        )

    tree_id = _require_str(raw.get("tree_id"), where=f"{path}: tree_id")

    direction_raw = raw.get("direction")
    if not isinstance(direction_raw, dict):
        raise RenderError(f"{path}: direction must be a mapping")
    direction_mode = direction_raw.get("mode")
    if direction_mode not in _DIRECTION_MODES:
        raise RenderError(
            f"{path}: direction.mode refused: {direction_mode!r} — expected one of "
            f"{list(_DIRECTION_MODES)!r}"
        )
    direction_value = direction_raw.get("value")
    if direction_mode == "declared":
        if direction_value not in _DIRECTION_TOKENS:
            raise RenderError(
                f"{path}: direction.value refused: {direction_value!r} — a declared-mode tree "
                f"must name one of {sorted(_DIRECTION_TOKENS)!r}"
            )
    elif direction_value is not None:
        # Two sources for one fact. In substitute mode the direction comes from `--direction`,
        # so a manifest value could only ever agree or lie.
        raise RenderError(
            f"{path}: direction.value is set in substitute mode — the direction comes from "
            "--direction there, and a manifest value would be a second source"
        )

    journal_raw = raw.get("journal")
    if not isinstance(journal_raw, dict):
        raise RenderError(f"{path}: journal must be a mapping")
    journal_mode = journal_raw.get("mode")
    if journal_mode not in _JOURNAL_MODES:
        raise RenderError(
            f"{path}: journal.mode refused: {journal_mode!r} — expected one of "
            f"{list(_JOURNAL_MODES)!r}"
        )

    slots_raw = raw.get("slots")
    if not isinstance(slots_raw, list) or not slots_raw:
        raise RenderError(f"{path}: slots must be a non-empty list")
    slots: list[Slot] = []
    seen: set[str] = set()
    for index, entry in enumerate(slots_raw):
        where = f"{path}: slots[{index}]"
        if not isinstance(entry, dict):
            raise RenderError(f"{where}: expected a mapping, got {entry!r}")
        slot = Slot(
            file=_require_str(entry.get("file"), where=f"{where}.file"),
            key=_require_str(entry.get("key"), where=f"{where}.key"),
            anchor=_require_str(entry.get("anchor"), where=f"{where}.anchor"),
            replacement=_require_str(
                entry.get("replacement"), where=f"{where}.replacement"
            ),
            value=_require_str(entry.get("value"), where=f"{where}.value"),
        )
        if slot.value not in _VALUE_SOURCES:
            raise RenderError(
                f"{where}: value source refused: {slot.value!r} — the set is closed to "
                f"{sorted(_VALUE_SOURCES)!r}, so a manifest cannot carry a literal value"
            )
        if slot.rule_key in seen:
            raise RenderError(f"{where}: duplicate slot key {slot.rule_key!r}")
        seen.add(slot.rule_key)
        if not (tree / slot.file).is_file():
            raise RenderError(
                f"{where}: slot target missing from the tree: {tree / slot.file}"
            )
        _validate_replacement_template(
            key=slot.rule_key, anchor=slot.anchor, template=slot.replacement
        )
        slots.append(slot)

    return RenderManifest(
        tree_id=tree_id,
        direction_mode=direction_mode,
        direction_value=direction_value if direction_mode == "declared" else None,
        journal_mode=journal_mode,
        slots=tuple(slots),
    )


def _slot_rules(
    manifest: RenderManifest,
    *,
    account: str,
    instrument: str,
    revision: str,
    direction: str,
    journal_path: Path,
) -> tuple[Rule, ...]:
    """Turn the manifest's slots into the :class:`Rule` tuple :func:`_apply_rules` executes.

    ``substitute`` mode reproduces :func:`_coordinate_rules` exactly (the unit test pins that).

    ``declared`` mode adds exactly ONE clause, for the direction-bound slots: the line the
    declared direction makes must BE the committed anchor. Everything else about those slots is
    unchanged, and deliberately so (design §2.3) — the substitution is then a no-op and
    ``_apply_rules``' existing "exactly one anchor match" invariant does the direction check by
    itself. A ``cp3-setup-d-short`` tree rendered against a manifest declaring ``LONG``, or a
    tree whose ``construction.yaml`` still says ``NEW_LONG`` under a ``SHORT`` manifest, refuses
    with "matched 0 times"; without the direction slots in the manifest at all, nothing would
    (review H1).

    ⚠ The clause is written as a bare check rather than as a separate anchor/replacement path,
    because the two are provably the same once it holds — a second formulation would be a
    clause that can never fire on its own (#838).
    """
    tokens = _DIRECTION_TOKENS[direction]
    values: dict[str, str] = {
        "account": account,
        "instrument": instrument,
        "revision": revision,
        "journal_path": str(journal_path),
        "direction_action_class": tokens["action_class"],
        "direction_side": tokens["side"],
        "direction": direction,
    }
    rules: list[Rule] = []
    for slot in manifest.slots:
        line = slot.replacement.replace(_PLACEHOLDER, values[slot.value])
        if (
            manifest.direction_mode == "declared"
            and slot.value in _DIRECTION_VALUE_SOURCES
            and line != slot.anchor
        ):
            raise RenderError(
                f"slot {slot.rule_key}: this tree declares direction "
                f"{manifest.direction_value!r}, which makes the verify-only line {line!r} — "
                f"but the manifest's committed anchor is {slot.anchor!r}. The manifest "
                "disagrees with itself about its own direction"
            )
        rules.append(Rule(slot.file, slot.rule_key, slot.anchor, line))
    return tuple(rules)


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
        # Inline comments (review-797 LOW-4). Without this, a trailing `# opened 2026`
        # reaches :func:`normalize_account`, which deletes every non-digit — so the comment's
        # digits silently JOIN the account number. When the total still lands on ten digits
        # that is an accepted, well-formed, WRONG account; otherwise it is a refusal whose
        # digit count makes no sense to the reader.
        #
        # A quoted value is taken up to its closing quote, so a `#` INSIDE the quotes is part
        # of the value and only what follows the quote is a comment. An unquoted value is cut
        # at the first `#`.
        if value[:1] in {"'", '"'}:
            quote = value[0]
            closing = value.find(quote, 1)
            if closing != -1:
                value = value[1:closing]
            else:
                raise RenderError(
                    f"{env_path}: {ACCOUNT_ENV_KEY} has an unterminated {quote} quote"
                )
        else:
            value = value.split("#", 1)[0].strip()
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

    ``PYTHONHASHSEED`` is deliberately NOT in this allowlist. It was passed through between
    2026-09-23 and 2026-09-24 to work around the canonical set-ordering defect; with that
    defect fixed (``docs/plans/2026-09-24-tos-canonical-set-order-plan.md``) a digest no
    longer depends on the seed, and re-introducing the pass-through would hide a regression
    rather than surface it.
    """
    return {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": _SUBPROCESS_PYTHONPATH,
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": str(Path.home()),
    }


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

    Reproducible across processes since 2026-09-24. It was not before: ``covered_content()``
    is ``model_dump(mode="json", …)`` (``tos/src/tos/canonical/_base.py:187``), which renders a
    ``set``/``frozenset`` as a LIST in set-iteration order, and ``_encode`` treats a sequence
    as ORDER-SIGNIFICANT ("sequence order is preserved (vectors are order-significant)",
    ``tos/src/tos/canonical/canonicalization.py``). Set iteration order follows Python's
    per-process string hash seed, so any canonical model with a set in its covered content
    digested differently in every process — and the documented operator procedure (run
    ``print-policy-digests``, copy the digests into ``safety_activation.yaml::members``, boot)
    is a CROSS-PROCESS transcription, so it could not work for such a kind.

    The fix is one JSON-mode serialization hook on :class:`~tos.canonical.FrozenModel`
    (``tos/src/tos/canonical/_canonical_json.py``;
    ``docs/plans/2026-09-24-tos-canonical-set-order-plan.md``): every set is emitted in
    ``sorted()`` order, so all 19 set-carrying canonical models — ``VenueConstraintPolicy``
    among them — digest identically in every process.
    ``tests/tools/test_tos_canonical_set_order.py`` measures that over six ``PYTHONHASHSEED``
    values, and ``_verify_activation`` still re-derives in a fresh process: the cross-process
    transcription is the property that must hold, and re-measuring it here is cheaper than
    discovering a regression at boot.

    ⚠ **Separately: the activation record does not bind DIRECTION** (review-797 LOW-6).
    ``_runtime.construction.axes``' ``DIRECTION`` and ``admitted_quantity_bases`` sit OUTSIDE
    the OCP's canonical covered content (DR-0002 §2.3 binds the digest to
    ``policy_id``/``policy_generation``/``policy_version`` only), so a LONG render and a SHORT
    render produce BYTE-IDENTICAL digests for all five kinds. The symmetry argument for this
    deployment rests on the render rewriting four slots together and on the tests pinning
    that — **the digests do not prove it.**
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


#: The two sibling working directories :func:`render` creates next to ``out``. Both can hold
#: an account coordinate, so both are named by the same scheme and both are covered by
#: :func:`_refuse_stale_working_dirs`.
_STAGING_KIND = "partial"
_REPLACED_KIND = "replaced"


def _working_dir(out: Path, kind: str) -> Path:
    """``.<out name>.<kind>-<pid>``, a sibling of ``out`` (same filesystem, so the swap in
    :func:`_publish` is a rename and never a copy)."""
    return out.parent / f".{out.name}.{kind}-{os.getpid()}"


def _refuse_stale_working_dirs(out: Path) -> None:
    """Refuse loudly when a working directory from an earlier run is still lying next to
    ``out``, naming it so the operator can remove it.

    **Why refuse instead of auto-deleting** (review-797 round 2): a working directory holds an
    account coordinate, and the two candidate rules for deleting one automatically are both
    wrong here.

    * "delete any stale one" would destroy a CONCURRENT render's in-flight tree.
    * "delete the ones whose pid is not alive" relies on pid liveness, which pid reuse makes
      unreliable — and it would silently delete account-bearing data on a heuristic, which is
      exactly the quiet behaviour this guard exists to make impossible.

    Refusing is also what restores the observability the first cut lost: a leftover used to be
    invisible (hidden name, wrong pid, next run succeeded anyway). Now the next run stops and
    points at it.
    """
    stale = sorted(
        path
        for kind in (_STAGING_KIND, _REPLACED_KIND)
        for path in out.parent.glob(f".{out.name}.{kind}-*")
    )
    if stale:
        listed = " ".join(str(path) for path in stale)
        raise RenderError(
            "refusing to start: a working directory from an earlier render is still present "
            f"next to {out} — {listed}. It holds an account coordinate. If no other render is "
            f"running, remove it: rm -rf {listed}"
        )


def _write_rendered_manifest(staging: Path, payload: dict[str, Any]) -> None:
    """Write ``RENDERED.json`` into ``staging`` (its own function so a test can inject a
    failure exactly here — see the parametrized failure-point test)."""
    (staging / RENDERED_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _publish(staging: Path, out: Path) -> None:
    """Swap ``staging`` into place at ``out``.

    The ordering matters, and the obvious ``rmtree(out); move(staging, out)`` is what this
    deliberately does NOT do: between those two statements ``out`` is gone while ``staging``
    still exists, so an interruption there destroys the previous render AND leaves an
    account-bearing directory behind.

    Instead, three renames, each atomic on a single filesystem (both paths are siblings of
    ``out``, which is what :func:`_working_dir` guarantees):

    1. the previous render, if any, is renamed ASIDE (not deleted) — so it can be put back;
    2. ``staging`` is renamed ONTO the now-free ``out`` (``os.replace`` onto a non-existent
       path; renaming onto an existing non-empty directory would fail with ``ENOTEMPTY``,
       which is the whole reason for step 1);
    3. only once ``out`` holds the new render is the old one removed.

    If step 2 fails, step 1 is rolled back and the caller's ``except`` removes ``staging``. If
    step 3 fails, the render itself succeeded but a directory holding the PREVIOUS account
    coordinate survived, so that is raised rather than swallowed.
    """
    replaced = _working_dir(out, _REPLACED_KIND)
    if out.exists():
        os.replace(out, replaced)
    try:
        os.replace(staging, out)
    except BaseException:
        if replaced.exists():
            os.replace(replaced, out)
        raise
    if replaced.exists():
        try:
            shutil.rmtree(replaced)
        except OSError as exc:
            raise RenderError(
                f"the render completed and {out} is correct, but the PREVIOUS render could "
                f"not be removed: {replaced} ({exc}). It holds an account coordinate — "
                f"remove it: rm -rf {replaced}"
            ) from exc


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
    #: ``None`` in ``external`` journal mode — the renderer does not read the journal there,
    #: so it has no observation timestamp to report (design §2.4).
    journal_as_of_ms: int | None
    rendered_at_kst: str
    #: The manifest's ``tree_id`` — which committed tree this render came from. No default:
    #: a fallback of ``"paper"`` would label a tenant render as the resident one.
    tree_id: str


def render(
    source: Path,
    out: Path,
    *,
    account: str,
    instrument: str,
    revision: str,
    direction: str = "LONG",
    now_ms: int | None = None,
    journal_path: Path | None = None,
) -> RenderResult:
    """Byte-copy ``source`` to ``out`` and fill exactly the slots ``source``'s manifest declares.

    The rule table is NOT in this file: it is ``<source>/RENDER.yaml``, validated by
    :func:`load_manifest` (design 2026-10-09 §2.1). ``_apply_rules`` is unchanged, so the
    "exactly one anchor match" invariant holds for every tree.

    This function reads NO env file and touches NO ``os.environ`` (design §2 guard "계좌
    원천이 모의 파일" — the env-file rule lives in :func:`main`, and the tests drive this
    function with a fake account so no real value ever reaches a test).

    Args:
        source: The committed values directory (``config/tos_runtime/paper``).
        out: The OFF-REPO output directory.
        account: The already-normalized account coordinate.
        instrument: The contract code coordinate.
        revision: ``finality.yaml::source_revision``.
        direction: ``LONG`` or ``SHORT``. In ``substitute`` mode (design §3 choice (가)) it is
            APPLIED to the direction slots; in ``declared`` mode it must equal the manifest's
            own ``direction.value`` and the direction slots are verified, not rewritten.
        now_ms: Wall-clock milliseconds for the generated journal; defaults to now.
        journal_path: REQUIRED in ``external`` journal mode (the ③ producer's output, which
            must already exist); REFUSED in ``synthetic_bootproof`` mode, where the renderer
            writes the journal itself.

    Raises:
        RenderError: any refusal — a bad direction, a manifest that refuses to load, a
            direction or journal argument that contradicts the manifest's mode, an output path
            inside the repo, an anchor that did not match exactly once, a refused
            ``print-policy-digests``, or an activation read-back that does not see every member.
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
    manifest = load_manifest(source)
    if manifest.direction_mode == "declared" and direction != manifest.direction_value:
        raise RenderError(
            f"direction refused: {source.name} is a declared-direction tree committed as "
            f"{manifest.direction_value!r}, but --direction says {direction!r}. A declared tree "
            "is not re-pointed by a flag — render the tree for the direction you want"
        )
    if manifest.journal_mode == "external":
        if journal_path is None:
            raise RenderError(
                f"journal path required: {source.name} declares journal.mode 'external', so "
                "the observation journal comes from its producer and --journal-path is "
                "mandatory (design §2.4 — fail-closed, the renderer invents no observations)"
            )
        journal_path = journal_path.expanduser()
        journal_path = (
            journal_path if journal_path.is_absolute() else Path.cwd() / journal_path
        ).resolve()
        if not journal_path.is_file():
            raise RenderError(f"journal file not found: {journal_path}")
    elif journal_path is not None:
        raise RenderError(
            f"journal path refused: {source.name} declares journal.mode "
            "'synthetic_bootproof', so the renderer writes the journal itself — passing one "
            "would be a second source"
        )
    out = out.expanduser()
    out = (out if out.is_absolute() else Path.cwd() / out).resolve()
    _refuse_output_inside_repo(out, source)

    if out.exists():
        if any(out.iterdir()) and not (out / RENDERED_NAME).is_file():
            raise RenderError(
                f"output directory refused: {out} is not empty and carries no "
                f"{RENDERED_NAME} — refusing to overwrite a directory this script did not "
                f"render. If it IS a leftover you recognize, remove it first: rm -rf {out}"
            )
    _refuse_stale_working_dirs(out)

    # Build in a sibling staging directory and swap it into place only on success
    # (review-797 MEDIUM-2, scope corrected in round 2). A failure AFTER the first account
    # byte reaches the disk — which is what every operator on this host hits today, because
    # the activation read-back refuses on the canonical-digest defect — must not leave an
    # account-bearing directory behind.
    #
    # ⚠ The first cut of this closed only PART of that: the `try` ended before the fingerprint,
    # the RENDERED.json write and the move, so a failure in those left a HIDDEN
    # `.<name>.partial-<pid>` holding seven account-bearing files, which the next run neither
    # cleaned (the name carries THIS pid) nor noticed (it is not `out`). The window is now the
    # whole body, the swap included, and both working directories are named by
    # :func:`_working_dir` so a leftover from any run is visible to
    # :func:`_refuse_stale_working_dirs`.
    staging = _working_dir(out, _STAGING_KIND)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copytree(source, staging)
        staging.chmod(0o700)

        now = (
            datetime.now(tz=_KST)
            if now_ms is None
            else datetime.fromtimestamp(now_ms / 1000, tz=_KST)
        )
        effective_now_ms = int(now.timestamp() * 1000)
        journal_as_of_ms: int | None
        # `journal_path is not None` is exactly `journal_mode == "external"` here: the
        # pre-flight above REQUIRES a path in external mode and REFUSES one in synthetic mode,
        # so branching on the value keeps the two facts from drifting apart.
        if journal_path is not None:
            # The ③ producer's output. The renderer neither writes nor reads it — the content
            # contract belongs to the producer (design §2.4).
            effective_journal_path = journal_path
            journal_as_of_ms = None
        else:
            # The journal FILE is written into staging, but the path baked into marketfeed.yaml
            # is the FINAL one — the rendered config must be correct after the swap, not during.
            effective_journal_path = out / JOURNAL_NAME
            journal_as_of_ms = _write_journal(
                staging / JOURNAL_NAME, instrument=instrument, now_ms=effective_now_ms
            )

        rules = _slot_rules(
            manifest,
            account=account,
            instrument=instrument,
            revision=revision,
            direction=direction,
            journal_path=effective_journal_path,
        )
        # ---- the first account byte reaches the disk here ----
        _apply_rules(staging, rules)

        digests = _policy_digest_lines(staging)
        rendered_at = now.isoformat()
        members = _members_rule(_members_block(digests, rendered_at=rendered_at))
        _apply_rules(staging, (members,))
        activation_check = _verify_activation(staging, digests)

        # ⚠ No self-check against :data:`COORDINATE_RULE_KEYS` here any more, and deliberately
        # not a self-check against the manifest either. With the slot table as DATA, comparing
        # the rendered keys to the manifest would compare the manifest to itself — adding a
        # slot would turn nothing red (design §2.1, review M1). The pin that keeps its force is
        # the per-tree expected-slot literal in the unit tests, which carries the full
        # ``(file, key, anchor, replacement)`` tuple, not just the key name.
        rendered_keys = tuple(rule.key for rule in rules) + (members.key,)

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
            journal_path=effective_journal_path,
            journal_as_of_ms=journal_as_of_ms,
            rendered_at_kst=rendered_at,
            tree_id=manifest.tree_id,
        )
        # RENDERED.json is written LAST inside staging, so the directory that lands at `out`
        # can never be the "non-empty, no RENDERED.json" shape the guard above permanently
        # refuses.
        _write_rendered_manifest(
            staging,
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
                "journal_path": str(effective_journal_path),
                "journal_as_of_ms": journal_as_of_ms,
                # ADDED 2026-10-09 (design §2.3): which committed tree this render came from.
                # The five keys the host driver reads are untouched
                # (`~/.config/kis-probes/tos_paper_session.py:331-333,366-370`).
                "tree_id": manifest.tree_id,
                "note": (
                    "boot-proof fixture render — 거래 전략 아님. The account number itself is "
                    "never recorded here, only its fingerprint."
                ),
            },
        )
        _publish(staging, out)
    except BaseException:
        # EVERY failure path from the first byte written into staging through the swap,
        # `KeyboardInterrupt` included. BOTH working directories can hold an account
        # coordinate, so neither outlives the failure.
        #
        # `out` itself is never removed here: :func:`_publish` either left the previous render
        # in place (it rolls back) or already swapped the new one in.
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(_working_dir(out, _REPLACED_KIND), ignore_errors=True)
        raise
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

    The registered slots come from ``<source>/RENDER.yaml`` — the SAME manifest :func:`render`
    executed, so the two cannot drift. ``RENDER.yaml`` itself is byte-copied into the output
    (design §7) and is therefore compared like any other file: an edit to the output's copy is
    reported, because no slot is anchored in it.
    """
    source = source.resolve()
    out = out.expanduser().resolve()
    problems: list[str] = []
    if not out.is_dir():
        return [f"output directory not found: {out}"]
    try:
        manifest = load_manifest(source)
    except RenderError as exc:
        return [str(exc)]

    generated = _generated_names(manifest.journal_mode)
    source_files = _relative_files(source)
    out_files = _relative_files(out)
    for extra in sorted(out_files - source_files - generated):
        problems.append(f"unexpected file in the rendered directory: {extra}")
    for missing in sorted(source_files - out_files):
        problems.append(f"file missing from the rendered directory: {missing}")
    for required in sorted(generated):
        if required not in out_files:
            problems.append(f"render artifact missing: {required}")

    anchors_by_file: dict[str, set[str]] = {}
    for slot in manifest.slots:
        anchors_by_file.setdefault(slot.file, set()).add(slot.anchor)
    members = _members_rule("members: RENDERED")
    anchors_by_file.setdefault(members.file, set()).add(members.anchor)

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
        help=(
            "direction. Applied to the direction slots when --source declares "
            "direction.mode 'substitute'; compared against the tree's own declared value "
            "when it declares 'declared' (default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--journal-path",
        type=Path,
        default=None,
        help=(
            "the observation journal the rendered marketfeed points at. REQUIRED when "
            "--source declares journal.mode 'external' (the file must already exist and is "
            "never read here); REFUSED when it declares 'synthetic_bootproof', where this "
            "script writes the journal itself"
        ),
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
            journal_path=args.journal_path,
        )
    except RenderError as exc:
        print(f"render_paper_config: refused — {exc}", file=sys.stderr)
        return 1

    print(f"rendered: {result.out}")
    print(f"  tree_id:         {result.tree_id}")
    print(f"  source_revision: {result.revision}")
    print(f"  direction:       {result.direction}")
    print(f"  instrument:      {result.instrument}")
    print(f"  account:         <withheld> fingerprint={result.account_fingerprint}")
    journal_note = (
        "external"
        if result.journal_as_of_ms is None
        else f"as_of_ms={result.journal_as_of_ms}"
    )
    print(f"  journal:         {result.journal_path} ({journal_note})")
    print(f"  activation:      {result.activation_check}")
    for kind, member_id, generation, digest in result.policy_digests:
        print(f"  digest:          {kind} {member_id} {generation} {digest}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
