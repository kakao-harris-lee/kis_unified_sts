"""Candidate-AST domain — the adversarial input surface (design §3.2)."""

from __future__ import annotations

from pydantic import model_validator

from tos.dsl._base import ArtifactIntegrityError, FrozenModel

KIND_IMPORT = "import"
KIND_DYNAMIC_EVAL = "dynamic_eval"
KIND_REFLECTION = "reflection"
KIND_FFI = "ffi"
KIND_AMBIENT_READ = "ambient_read"
KIND_WILDCARD_SCOPE = "wildcard_scope"
KIND_UNKNOWN = "unknown"
KIND_FOREIGN = "foreign"
KIND_EXTENSION = "extension"

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

WILDCARD_TOKENS: frozenset[str] = frozenset(
    {"*", "latest", "LATEST", "any", "ANY", "all", "ALL", "*/*", "?"}
)


class CandidateNode(FrozenModel):
    """One node of an untrusted candidate AST (design §3.2) — open by construction."""

    kind: str
    source: str | None = None
    symbol: str | None = None
    scope: str | None = None
    children: tuple[CandidateNode, ...] = ()


class CandidateProgram(FrozenModel):
    """A whole candidate submission: a non-empty forest of candidate nodes (design §3.2)."""

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
    """Return every node in ``program`` (pre-order), for a full-tree walk."""
    out: list[CandidateNode] = []
    stack: list[CandidateNode] = list(reversed(program.nodes))
    while stack:
        node = stack.pop()
        out.append(node)
        stack.extend(reversed(node.children))
    return out
