"""Candidate-AST domain — the adversarial input surface (design §3.2).

The closed typed algebra of :mod:`tos.dsl.vocabulary` cannot *express* an escape
attempt, so it cannot be used to test that escapes are rejected. This module
supplies the separate **candidate-AST** representation the static admissibility
predicate consumes (design §3.2): a permissive, open tree that CAN carry an
escape marker, an ambient read, a wildcard scope, or an entirely unknown node —
precisely the adversarial inputs DCE-EV-004/006 require.

**Firewall-critical (design §3.2):** a candidate is **data**, never code. This
module and the checker walk the pydantic tree only; they never ``import``,
``compile``, ``exec``, or ``eval`` it. If a candidate ever arrives as Python
source, it is analyzed with stdlib :mod:`ast` static parsing (no execution) — the
exact technique of ``tools/tos_firewall_check.py`` (design §5.2, structural twin).

The node-kind constants below are the escape/ambient families used to *generate*
adversarial candidates and to produce readable inadmissibility reasons. They are
**not** the enforcement mechanism: admissibility is decided by default-deny
membership in :data:`tos.dsl.vocabulary.ADMISSIBLE_KINDS` (an allowlist), so a
novel/unknown kind not enumerated here is still inadmissible (DCE-INV-006).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design §firewall).
"""

from __future__ import annotations

from pydantic import model_validator

from tos.dsl._base import ArtifactIntegrityError, FrozenModel

# --- Escape / ambient / defect kind names (adversarial generation + reasons) ---
# These are illustrative members of the inadmissible space, used by tests to plant
# concrete escapes. Enforcement does NOT consult this set (default-deny is by the
# ADMISSIBLE_KINDS allowlist); it exists for adversarial coverage and messaging.

KIND_IMPORT = "import"
KIND_DYNAMIC_EVAL = "dynamic_eval"
KIND_REFLECTION = "reflection"
KIND_FFI = "ffi"
KIND_AMBIENT_READ = "ambient_read"
KIND_WILDCARD_SCOPE = "wildcard_scope"
KIND_UNKNOWN = "unknown"
KIND_FOREIGN = "foreign"
KIND_EXTENSION = "extension"

#: Illustrative escape/ambient/extension families (RFC-008 §11 items 12/17;
#: ADR-DEV-001 DCE-INV-004 adds reflection). Generation/messaging only.
ESCAPE_KINDS: frozenset[str] = frozenset(
    {
        KIND_IMPORT,
        KIND_DYNAMIC_EVAL,
        KIND_REFLECTION,
        KIND_FFI,
        KIND_AMBIENT_READ,
        KIND_WILDCARD_SCOPE,
        KIND_UNKNOWN,
        KIND_FOREIGN,
        KIND_EXTENSION,
    }
)

#: Named ambient symbols a candidate might reference (clock/rand/net/fs/global/
#: builtin — RFC-008 §11 item 12). Referencing any is an inadmissible ambient reach
#: even inside an otherwise-admissible-kind node (DCE-INV-003 static naming facet).
AMBIENT_SYMBOLS: frozenset[str] = frozenset(
    {
        "clock",
        "time",
        "now",
        "wall_time",
        "random",
        "rand",
        "urandom",
        "socket",
        "network",
        "http",
        "url",
        "filesystem",
        "file",
        "open",
        "path",
        "os",
        "environ",
        "getenv",
        "env",
        "globals",
        "locals",
        "global",
        "builtin",
        "builtins",
        "__builtins__",
        "import",
        "importlib",
        "__import__",
        "eval",
        "exec",
        "compile",
        "getattr",
        "setattr",
        "reflection",
    }
)

#: Wildcard / "latest policy" scope tokens (RFC-008 §11 item 13; ADR-002-020 §8).
WILDCARD_TOKENS: frozenset[str] = frozenset(
    {"*", "latest", "LATEST", "any", "ANY", "all", "ALL", "*/*", "?"}
)


class CandidateNode(FrozenModel):
    """One node of an untrusted candidate AST (design §3.2) — open by construction.

    A candidate node carries an **open** ``kind`` string (not a closed enum), so it
    can represent both an admissible construct and an escape/ambient/unknown node.
    Optional fields let adversarial inputs name an ambient ``source``/``symbol`` or
    a wildcard ``scope``. ``children`` makes it a tree. This is pure data: the
    checker walks it, it is never executed.
    """

    kind: str
    #: For an admissible ``context_ref``: the read source ("capsule"/"config"). An
    #: ambient value (clock/network/...) is an inadmissible reach (DCE-INV-003).
    source: str | None = None
    #: A referenced symbol name — checked against ambient names (DCE-INV-003).
    symbol: str | None = None
    #: A scope token — checked against wildcard/"latest" (RFC-008 §11 item 13).
    scope: str | None = None
    children: tuple[CandidateNode, ...] = ()


class CandidateProgram(FrozenModel):
    """A whole candidate submission: a non-empty forest of candidate nodes (design §3.2).

    An **empty** program (no nodes) is not a benign no-op: with nothing proven
    inside the surface it is inadmissible (fail-closed, DCE-INV-006 / ★ vacuous-True
    prohibition). Construction therefore rejects an empty node tuple so a
    degenerate candidate can never be mistaken for an admissible one.
    """

    nodes: tuple[CandidateNode, ...]

    @model_validator(mode="after")
    def _non_empty(self) -> CandidateProgram:
        """Reject an empty candidate so emptiness never reads as admissible (★3)."""
        if not self.nodes:
            raise ArtifactIntegrityError(
                "CandidateProgram.nodes must be non-empty — an empty candidate "
                "proves nothing inside the surface and is inadmissible (DCE-INV-006)"
            )
        return self


def iter_nodes(program: CandidateProgram) -> list[CandidateNode]:
    """Return every node in ``program`` (pre-order), for a full-tree walk.

    Args:
        program: The candidate program.

    Returns:
        Every :class:`CandidateNode` in the program, roots first.
    """
    out: list[CandidateNode] = []
    stack: list[CandidateNode] = list(reversed(program.nodes))
    while stack:
        node = stack.pop()
        out.append(node)
        stack.extend(reversed(node.children))
    return out
