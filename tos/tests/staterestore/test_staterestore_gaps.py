"""The five EV-L3 seams, locked as executable observations (design #39 §7.4)."""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
    reconstruct_conservative,
)
from tos.rcl import CapacityState
from tos.staterestore import CompositeStateStore

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STATERESTORE_SRC = _REPO_ROOT / "tos" / "src" / "tos" / "staterestore"
_TOS_INIT = _REPO_ROOT / "tos" / "src" / "tos" / "__init__.py"
_OUTSIDE_DIR = _REPO_ROOT / "tests" / "tos_l3"

_NON_TRANSMITTING_SENTENCE = "non-transmitting by construction"

_EGRESS_TOKENS = (
    "socket",
    "urlopen",
    "http",
    "requests",
    "broker_credential",
    "order_construction",
    "send_order",
    "transmit",
)


def test_gap_i_no_input_at_all_reconstructs_to_reconciled() -> None:
    """§13 line 199 / ``predicates.py`` line 700-702, re-checked from the outside in."""
    produced = set()
    for knowledge in KnowledgeState:
        for attempt in TransmissionAttemptState:
            for broker in BrokerOrderState:
                post = reconstruct_conservative(
                    CompositeState(
                        intent_identity="GAP-I",
                        intent_state=IntentState.ACTIVE,
                        transmission_attempt_state=attempt,
                        broker_order_state=broker,
                        knowledge_state=knowledge,
                        capacity_state=CapacityState.POTENTIALLY_LIVE,
                    )
                )
                produced.add(post.knowledge_state)
    assert KnowledgeState.RECONCILED not in produced, (
        "a restart reconstruction produced RECONCILED — the codomain no longer "
        "structurally excludes it"
    )
    assert len(produced) >= 2


def test_gap_ii_the_store_is_a_real_file_that_outlives_its_connection(tmp_path) -> None:
    '"real persistence" (VER line 151-153) is a filesystem fact, checked as one.'
    path = tmp_path / "durable" / "store.sqlite3"
    with CompositeStateStore(path) as store:
        store.commit_composite(
            CompositeState(
                intent_identity="GAP-II",
                intent_state=IntentState.ACTIVE,
                transmission_attempt_state=TransmissionAttemptState.SEND_STARTED,
                broker_order_state=BrokerOrderState.UNKNOWN,
                knowledge_state=KnowledgeState.UNOBSERVED,
                capacity_state=CapacityState.POTENTIALLY_LIVE,
            )
        )
    assert path.is_file(), "the store is not a file on disk"
    assert path.stat().st_size > 0, "the store file is empty"
    probe = sqlite3.connect(str(path))
    try:
        names = {row[0] for row in probe.execute("SELECT name FROM sqlite_master")}
    finally:
        probe.close()
    assert "dimension_marker" in names


def test_gap_ii_the_store_source_never_opens_an_in_memory_database() -> None:
    """The C1 regression lock: ``:memory:`` must be unreachable, not merely unused."""
    source = (_STATERESTORE_SRC / "store.py").read_text(encoding="utf-8")
    assert ":memory:" not in source
    assert "mode=memory" not in source
    tree = ast.parse(source)
    connects = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "connect"
    ]
    assert len(connects) == 1, "expected exactly one sqlite3.connect call site"
    literal_args = [
        arg.value
        for arg in connects[0].args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    ]
    assert literal_args == [], f"the connection target is a literal: {literal_args}"


def _outside_sources() -> list[Path]:
    return sorted(_OUTSIDE_DIR.glob("*.py"))


def test_gap_iii_the_outside_orchestration_exists_and_imports_no_tos() -> None:
    """TOS-FW-R as the oracle-independence guarantee (§5.3 / O-3), grepped both ways."""
    sources = _outside_sources()
    assert sources, f"no outside orchestration found under {_OUTSIDE_DIR}"
    assert {p.name for p in sources} >= {
        "conftest.py",
        "test_state_ev_004_crash_restart.py",
    }

    offenders: list[str] = []
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [
                    f"{path.name}:{node.lineno} import {alias.name}"
                    for alias in node.names
                    if alias.name == "tos" or alias.name.startswith("tos.")
                ]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if not node.level and (module == "tos" or module.startswith("tos.")):
                    offenders.append(f"{path.name}:{node.lineno} from {module}")
    assert offenders == [], (
        "the outside crash orchestration imports the kernel it measures — its Expecteds "
        f"would no longer be independent anchors: {offenders}"
    )


def test_gap_iv_the_outside_orchestration_reaches_the_worker_as_a_module_path() -> None:
    """The only channel is spawn + on-disk store, so the worker is named, not imported."""
    source = (_OUTSIDE_DIR / "test_state_ev_004_crash_restart.py").read_text(
        encoding="utf-8"
    )
    assert "tos.staterestore._l3_worker" in source, (
        "the outside suite no longer names the worker module — it may have started "
        "reaching the kernel some other way"
    )


def test_gap_v_staterestore_adds_local_persistence_and_zero_egress() -> None:
    """The new package keeps the invariant: disk I/O yes, network egress no."""
    findings: dict[str, list[str]] = {}
    for path in sorted(_STATERESTORE_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                body = getattr(node, "body", [])
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    node.body = body[1:] or [ast.Pass()]
        code = ast.unparse(tree)
        hits = [token for token in _EGRESS_TOKENS if token in code]
        if hits:
            findings[path.name] = hits
    assert findings == {}, (
        "an egress-shaped surface appeared in tos.staterestore — the package may add "
        f"local persistence only, never transmission: {findings}"
    )
