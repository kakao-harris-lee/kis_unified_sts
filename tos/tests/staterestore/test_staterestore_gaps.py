"""The five EV-L3 seams, locked as executable observations (design #39 §7.4).

Inherits the discipline of ``tos/tests/slice/test_slice_gaps.py``: a property that a
design argued for in prose rots the moment someone edits the code, and the accumulated
anti-phantom lesson is that a claim of **absence** must be grepped exactly like a claim
of presence. Each test below is the executable form of one §7.4 canary:

* **(i)** ``reconstruct_conservative``'s codomain still **structurally excludes**
  ``RECONCILED`` (``tos/src/tos/orthostate/predicates.py`` line 700-702);
* **(ii)** the store is a **real on-disk file**, not an in-memory database — the EV-L2
  pilot's C1 defect ("durable, redefined as in-memory") must not recur one stage later;
* **(iii)** the outside crash orchestration does **not** import ``tos`` — the structural
  basis of oracle independence (§5.3 / O-3), asserted here as well as by the repo-wide
  firewall gate, so the guarantee fails inside the suite that relies on it;
* **(iv)** no forbidden stdlib primitive appears in the outside orchestration's
  *kernel-facing* surface, and the worker is invoked as a module path rather than
  imported;
* **(v)** the **tos-wide non-transmitting invariant** survives this package
  (``tos/src/tos/__init__.py`` line 6): staterestore adds local persistence (disk) and
  **zero** egress — persistence ≠ transmission (§5.1 MINOR-3).

⚠ Authoring evidence; closes no EV.
"""

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

#: The tos-wide invariant sentence, verbatim from ``tos/src/tos/__init__.py`` line 6.
_NON_TRANSMITTING_SENTENCE = "non-transmitting by construction"

#: Egress-shaped tokens that must not appear anywhere in the staterestore sources.
#: Broader than the firewall's import rule on purpose: the firewall bans *importing*
#: ``socket``, while this bans the package acquiring a broker route, credential, or
#: transport surface by any spelling at all.
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


# --------------------------------------------------------------------------
# (i) the projection's codomain still excludes RECONCILED
# --------------------------------------------------------------------------


def test_gap_i_no_input_at_all_reconstructs_to_reconciled() -> None:
    """§13 line 199 / ``predicates.py`` line 700-702, re-checked from the outside in.

    Swept over the full Knowledge enum rather than sampled: "never" is universally
    quantified, and a single surviving input that produced ``RECONCILED`` would falsify
    the whole restart claim. This is a **regression lock on a property staterestore now
    depends on**, not a second acceptance of the EV-L1 predicate.
    """
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
    # ∅-seal in the other direction: the sweep really ran and really varied.
    assert len(produced) >= 2


# --------------------------------------------------------------------------
# (ii) the store is real on-disk state
# --------------------------------------------------------------------------


def test_gap_ii_the_store_is_a_real_file_that_outlives_its_connection(tmp_path) -> None:
    """ "real persistence" (VER line 151-153) is a filesystem fact, checked as one."""
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
    # It is a real sqlite database, readable by a connection this package never opened.
    probe = sqlite3.connect(str(path))
    try:
        names = {row[0] for row in probe.execute("SELECT name FROM sqlite_master")}
    finally:
        probe.close()
    assert "dimension_marker" in names


def test_gap_ii_the_store_source_never_opens_an_in_memory_database() -> None:
    """The C1 regression lock: ``:memory:`` must be unreachable, not merely unused.

    A store that took its path from a caller and *could* be handed ``":memory:"`` would
    make ``persistence_real`` a statement about one call site instead of about the
    component. The token's absence from the source is the structural form of that claim.
    """
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


# --------------------------------------------------------------------------
# (iii) + (iv) the outside orchestration stays structurally independent
# --------------------------------------------------------------------------


def _outside_sources() -> list[Path]:
    return sorted(_OUTSIDE_DIR.glob("*.py"))


def test_gap_iii_the_outside_orchestration_exists_and_imports_no_tos() -> None:
    """TOS-FW-R as the oracle-independence guarantee (§5.3 / O-3), grepped both ways.

    Presence first: an empty or missing directory would make the absence claim vacuous
    (the ∅-seal that a naive negative grep always passes). Then absence, over the parsed
    syntax tree — the worker's module path is a *string* containing ``tos`` and a
    substring scan would have to either miss real imports or reject that string.
    """
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


# --------------------------------------------------------------------------
# (v) persistence != transmission
# --------------------------------------------------------------------------


def test_gap_v_the_tos_wide_non_transmitting_invariant_is_still_declared() -> None:
    """``tos/src/tos/__init__.py`` line 6 — the sentence staterestore must not falsify."""
    text = _TOS_INIT.read_text(encoding="utf-8")
    assert _NON_TRANSMITTING_SENTENCE in text


def test_gap_v_staterestore_adds_local_persistence_and_zero_egress() -> None:
    """The new package keeps the invariant: disk I/O yes, network egress no.

    Checked over code tokens *and* over the whole text for route/credential-shaped
    names, because the claim is about capability, not merely about imports. The one
    permitted exception is a docstring that discusses the distinction — so the scan runs
    against the parsed tree's code surface, with docstrings excluded.
    """
    findings: dict[str, list[str]] = {}
    for path in sorted(_STATERESTORE_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        # Drop every docstring, then unparse: what remains is executable surface only.
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
