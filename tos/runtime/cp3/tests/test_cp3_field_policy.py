"""The two literal mirrors are checked against their sources, not cited.

`FIELD_POLICY` and `JOURNAL_REQUIRED_KEYS` both restate content another module
owns. The 2026-10-08 review's finding was not that restating is wrong — the two
sides meet through a FILE and a cross-distribution import is not available for
one of them — but that a restatement with no equality assertion is drift waiting
to happen, and that citing a digest in a comment cannot detect it.

So both are asserted here:

* ``JOURNAL_REQUIRED_KEYS`` against ``tos_runtime.marketfeed.journal``'s own
  ``_REQUIRED_KEYS`` — a plain import, available because this package is RUNTIME
  scope (the same assertion B1a shipped for its mirror, #875 item 1).
* ``FIELD_POLICY`` against **B1a's own source**, by parsing
  ``tools/tos_cp3/produce_fields.py`` with stdlib ``ast``. Not an import: the
  firewall's allowlist does not name ``tools`` (TOS-FW-A), and dynamic import is
  forbidden outright (TOS-FW-D). A parse is a read of committed bytes — stricter
  than the yaml/json fallback the review offered, because it reads the producer's
  actual literals rather than a copy of them, so a one-sided edit on either side
  fails this test.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from tos_runtime.marketfeed.journal import _REQUIRED_KEYS as JOURNAL_SOURCE_KEYS

from .. import runner
from ..contract import FIELD_POLICY, FIELD_POLICY_GOVERNED_KEYS

#: B1a's producer, whose field specs this package's FIELD_POLICY mirrors.
_B1A_RELATIVE = Path("tools") / "tos_cp3" / "produce_fields.py"

#: The function in that module that assembles the per-field lineage block.
_B1A_SPEC_FUNCTION = "_field_lineage"


def _repo_root() -> Path:
    """The repo root, found by the two directories that mark it."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tos").is_dir() and (candidate / "tools").is_dir():
            return candidate
    pytest.fail(
        "cannot locate the repo root from this test file — the B1a drift check "
        "cannot be skipped silently"
    )


def _literal_dict(node: ast.AST) -> dict[str, Any] | None:
    """The LITERAL key/value pairs of a dict node, or ``None`` if not a dict.

    Per-key rather than whole-node, deliberately: B1a's family helpers return a
    dict mixing literal governed values with parameter names (``formula_id`` is a
    ``str`` parameter, ``parents`` a ``list`` parameter), so
    ``ast.literal_eval`` on the whole node raises. The governed keys this test
    compares are all literal strings, so skipping the non-literal entries reads
    exactly what is being asserted and nothing it cannot see.
    """
    if not isinstance(node, ast.Dict):
        return None
    literal: dict[str, Any] = {}
    for key_node, value_node in zip(node.keys, node.values):
        if not isinstance(key_node, ast.Constant) or not isinstance(
            key_node.value, str
        ):
            continue
        try:
            literal[key_node.value] = ast.literal_eval(value_node)
        except (ValueError, TypeError, SyntaxError):
            continue  # a parameter / f-string: not a governed value
    return literal


def _helper_returns(module: ast.Module) -> dict[str, dict[str, Any]]:
    """Every module-level helper whose body is a single literal-dict ``return``.

    B1a declares each field FAMILY once (``_price_field``, ``_bool_field``) and
    calls it per field, so the governed values for a family live in the helper's
    own return literal. Only the literal keys are recoverable — the formula /
    parents / source arguments are f-strings and parameters, which is fine: this
    test compares the five GOVERNED keys, not the prose.
    """
    found: dict[str, dict[str, Any]] = {}
    for node in module.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        returns = [n for n in node.body if isinstance(n, ast.Return) and n.value]
        if len(returns) != 1:
            continue
        literal = _literal_dict(returns[0].value)  # type: ignore[arg-type]
        if literal:
            found[node.name] = literal
    return found


def _b1a_field_specs() -> dict[str, dict[str, Any]]:
    """Extract B1a's per-field governed values from its committed source."""
    path = _repo_root() / _B1A_RELATIVE
    assert path.is_file(), f"{path} is missing — the mirrored source must exist"
    module = ast.parse(path.read_text(encoding="utf-8"))
    helpers = _helper_returns(module)

    spec_node: ast.AST | None = None
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == _B1A_SPEC_FUNCTION:
            for statement in ast.walk(node):
                if (
                    isinstance(statement, ast.AnnAssign)
                    and isinstance(statement.target, ast.Name)
                    and statement.target.id == "spec"
                ):
                    spec_node = statement.value
    assert spec_node is not None, (
        f"{path}::{_B1A_SPEC_FUNCTION} no longer assigns a `spec` dict — the "
        "drift check cannot read B1a's field specs, which is itself a failure"
    )
    assert isinstance(spec_node, ast.Dict)

    specs: dict[str, dict[str, Any]] = {}
    for key_node, value_node in zip(spec_node.keys, spec_node.values):
        assert isinstance(key_node, ast.Constant)
        field_key = str(key_node.value)
        literal = _literal_dict(value_node)
        if literal is not None:  # an inline literal entry
            specs[field_key] = literal
            continue
        # a helper CALL: the governed values are the helper's own literal return
        assert isinstance(value_node, ast.Call) and isinstance(
            value_node.func, ast.Name
        ), f"{field_key}: unexpected spec shape {type(value_node).__name__}"
        helper = value_node.func.id
        assert helper in helpers, (
            f"{field_key}: B1a builds it with {helper}(), whose return is no "
            "longer a single literal dict — the drift check cannot read it"
        )
        specs[field_key] = helpers[helper]
    return specs


def test_journal_required_keys_equal_the_shipped_reader_contract() -> None:
    """The five-key mirror equals ``journal._REQUIRED_KEYS`` exactly.

    An import, not a copy: the only shipped reader of this wire shape lives in
    the same distribution, so there is no excuse for a literal that can drift.
    """
    assert set(runner.JOURNAL_REQUIRED_KEYS) == set(JOURNAL_SOURCE_KEYS)
    assert len(runner.JOURNAL_REQUIRED_KEYS) == len(JOURNAL_SOURCE_KEYS)


def test_field_policy_covers_exactly_the_published_fields() -> None:
    """One policy entry per published field, no more and no fewer."""
    assert set(FIELD_POLICY) == set(runner.REQUIRED_FIELD_KEYS)
    assert len(FIELD_POLICY) == 15


def test_field_policy_matches_b1a_field_specs_on_every_governed_key() -> None:
    """``FIELD_POLICY`` equals B1a's lineage ``fields`` block where they overlap.

    The real drift detector. B1a is the producer and therefore the source of
    truth for unit / scale / multiplier / sign / quantization; this asserts the
    mirror against B1a's parsed source for all 15 fields, so an edit to either
    side alone fails here.
    """
    b1a = _b1a_field_specs()
    assert set(b1a) == set(FIELD_POLICY), (
        "B1a publishes a different field set than this policy covers: "
        f"only-B1a={sorted(set(b1a) - set(FIELD_POLICY))}, "
        f"only-cp3={sorted(set(FIELD_POLICY) - set(b1a))}"
    )
    for field_key in sorted(FIELD_POLICY):
        for governed in FIELD_POLICY_GOVERNED_KEYS:
            assert FIELD_POLICY[field_key][governed] == b1a[field_key][governed], (
                f"{field_key}.{governed}: cp3 says "
                f"{FIELD_POLICY[field_key][governed]!r}, B1a's source says "
                f"{b1a[field_key][governed]!r}"
            )


def test_governed_values_are_strings_as_the_policy_loader_demands() -> None:
    """``multiplier`` et al. are STRING tokens, not ints.

    The shipped policy loader lists ``unit``/``scale``/``multiplier``/``sign`` in
    ``tos_runtime.marketfeed.policy._FIELD_STR_KEYS`` and refuses an
    "absent/blank/non-string" value, so an int ``100`` here would publish a block
    a paper deployment could not load — the review's measured defect.
    """
    from tos_runtime.marketfeed.policy import _FIELD_STR_KEYS

    str_keys = [key for key in _FIELD_STR_KEYS if key != "field_key"]
    assert str_keys, "the loader's string-key set lost its members"
    for field_key, policy in FIELD_POLICY.items():
        for governed in str_keys:
            value = policy[governed]
            assert isinstance(value, str) and value.strip(), (
                f"{field_key}.{governed} is {value!r} ({type(value).__name__}) — "
                "the shipped policy loader refuses a non-string here"
            )
        # max_age_ms is the declared difference (B1b-D3): absent on this path.
        assert policy["max_age_ms"] is None


def test_quantization_is_published_for_every_field() -> None:
    """``quantization`` is present — it was dropped in the first revision.

    It is not decoration: ``truncate_toward_zero`` on ``z_x1000`` is exactly why
    the LONG entry threshold ``-1800`` is the conservative edge, and a consumer
    that cannot see the rounding rule cannot reproduce the integer.
    """
    for field_key, policy in FIELD_POLICY.items():
        assert policy["quantization"], f"{field_key} publishes no quantization"
    assert FIELD_POLICY["z_x1000"]["quantization"] == "truncate_toward_zero"
    assert FIELD_POLICY["close_x100"]["quantization"] == "half_up"
