"""AST-pin canaries for tos_runtime.venue (plan §5 mutation table M3/M9):

* ``VenueConstraintPolicy.issue`` may be called ONLY inside
  ``venue/_venue_policy_loader.py``.
* ``OrderConstructionPolicy.issue`` may be called ONLY inside
  ``venue/_order_construction_policy_loader.py``.
* ``VenueConstraintSnapshot.issue`` / ``OrderAdmissibilityDecision.issue``
  may be called ONLY inside ``venue/service.py``.
* No ``tos_runtime`` module ever passes an ``OrderAdmissibilityResult.<MEMBER>``
  attribute access as a call ARGUMENT or KEYWORD VALUE (comparisons via
  ``is``/``is not``/``in`` are fine — only construction-time use is forbidden,
  plan §2 decision 1's "런타임은 어느 판정도 저작하지 않는다").

``venue/config.py`` is a thin re-export shim over
``_venue_policy_loader.py``/``_order_construction_policy_loader.py``/
``_policy_primitives.py`` (split purely for module-size-budget reasons, see
``config.py``'s own module docstring) — it defines no ``.issue()`` call of
its own, so it never appears as an allowed home below.

An AST walk over each file's own statements — never a text grep — so a
multi-line, aliased, or nested call cannot slip past it (mirrors
``tos/runtime/tests/engine/test_no_transport_during_replay.py``'s own stated
idiom).
"""

from __future__ import annotations

import ast
from pathlib import Path

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]  # tos/runtime
_SRC = _RUNTIME_ROOT / "src" / "tos_runtime"
_VENUE_POLICY_LOADER = _SRC / "venue" / "_venue_policy_loader.py"
_OCP_LOADER = _SRC / "venue" / "_order_construction_policy_loader.py"
_VENUE_SERVICE = _SRC / "venue" / "service.py"

#: {method-owner-class-name: allowed file} for the four ``.issue()`` calls
#: this pin scopes (plan §5 mutation M9).
_ISSUE_METHOD_HOMES: dict[str, Path] = {
    "VenueConstraintPolicy": _VENUE_POLICY_LOADER,
    "OrderConstructionPolicy": _OCP_LOADER,
    "VenueConstraintSnapshot": _VENUE_SERVICE,
    "OrderAdmissibilityDecision": _VENUE_SERVICE,
}


def _all_py_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _issue_call_owner(node: ast.Call) -> str | None:
    """If ``node`` is a call of the shape ``<Name>.issue(...)``, return the
    ``<Name>`` — else ``None``."""
    func = node.func
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "issue"
        and isinstance(func.value, ast.Name)
    ):
        return func.value.id
    return None


def test_issue_calls_scoped_to_their_owning_module() -> None:
    offenders: list[str] = []
    for path in _all_py_files(_SRC):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            owner = _issue_call_owner(node)
            if owner is None or owner not in _ISSUE_METHOD_HOMES:
                continue
            allowed_file = _ISSUE_METHOD_HOMES[owner]
            if path != allowed_file:
                offenders.append(f"{path}:{node.lineno}: {owner}.issue(...)")
    assert offenders == [], (
        "VenueConstraintPolicy.issue (only in "
        f"{_VENUE_POLICY_LOADER}), OrderConstructionPolicy.issue (only in "
        f"{_OCP_LOADER}), and VenueConstraintSnapshot/"
        f"OrderAdmissibilityDecision.issue (only in {_VENUE_SERVICE}) must be "
        f"called from exactly its owning module (plan §5 M9): {offenders}"
    )


def _attribute_names_in_call_args_or_keywords(node: ast.Call) -> list[str]:
    """Every ``OrderAdmissibilityResult.<MEMBER>`` attribute-access dotted
    name that appears directly as a positional ARG or KEYWORD VALUE of
    ``node`` (not nested inside a tuple/list/comparison — those are membership
    checks, not construction)."""
    found = []
    for arg in node.args:
        if (
            isinstance(arg, ast.Attribute)
            and isinstance(arg.value, ast.Name)
            and arg.value.id == "OrderAdmissibilityResult"
        ):
            found.append(arg.attr)
    for kw in node.keywords:
        value = kw.value
        if (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and value.value.id == "OrderAdmissibilityResult"
        ):
            found.append(value.attr)
    return found


def test_order_admissibility_result_never_passed_as_a_call_argument() -> None:
    """Plan §5 mutation M3: ``VenueConstraintService.decide`` returning a
    hardcoded ``OrderAdmissibilityResult.ADMISSIBLE`` (or any other member)
    instead of the kernel fold's own value must turn this test red — the only
    way that mutation reads is by constructing/passing the enum member as a
    call argument (e.g. ``result=OrderAdmissibilityResult.ADMISSIBLE``), which
    this walk forbids everywhere in ``tos_runtime``. ``is``/``is not``/``in``
    comparisons (this suite's own assertions included) are unaffected — they
    are ``ast.Compare``/``ast.Tuple`` nodes, not call arguments."""
    offenders: list[str] = []
    for path in _all_py_files(_SRC):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for member in _attribute_names_in_call_args_or_keywords(node):
                offenders.append(
                    f"{path}:{node.lineno}: OrderAdmissibilityResult.{member}"
                )
    assert offenders == [], (
        "tos_runtime must never construct/pass an OrderAdmissibilityResult "
        f"member as a call argument (plan §2 decision 1 / §5 M3): {offenders}"
    )
