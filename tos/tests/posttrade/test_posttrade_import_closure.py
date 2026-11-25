"""§8.0 broker-agnostic / no-hardcoded-bound canaries for ``tos.posttrade``."""

from __future__ import annotations

import ast

from .._closure_policy import SRC_ROOT

_POSTTRADE_SRC = SRC_ROOT / "posttrade"


def test_no_hardcoded_numeric_bound_in_posttrade_source() -> None:
    """(§8.0 / CLAUDE.md) No source hardcodes an amount / ratio / haircut / threshold."""
    offenders: list[str] = []
    for path in sorted(_POSTTRADE_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                if isinstance(node.value, bool):
                    continue
                if node.value in (0, 1):
                    continue
                offenders.append(
                    f"{path.name}:{node.lineno} numeric literal {node.value!r}"
                )
    assert offenders == [], f"hardcoded numeric bound in posttrade source: {offenders}"


def test_no_broker_is_named_in_the_posttrade_source() -> None:
    """(broker-agnostic) No concrete broker / clearing house / custodian / bank is named."""
    forbidden_tokens = ("kis", "korea investment", "koreainvestment", "ebest", "kiwoom")
    offenders: list[str] = []
    for path in sorted(_POSTTRADE_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden_tokens:
            if token in text:
                offenders.append(f"{path.name}: {token!r}")
    assert offenders == [], f"a concrete broker is named in the source: {offenders}"
