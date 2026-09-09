"""Serialized strategy admission — pydantic validation only (design #31 §3.5/§9-4).

Design #31 §3.5 explicitly deferred the serialized authoring path ("직렬화/YAML/
builder-UI 데이터로 도착") to a later cycle and named its three-part contract: (i)
parsing into a typed :class:`~tos.dsl.strategy.AuthoredStrategy` (this module), (ii)
lowering + escape-checking (:mod:`tos.dsl.lowering` / :mod:`tos.dsl.admissibility`),
and (iii) strategy<->verdict binding (:mod:`tos.dsl.evidence`, G12). This module
realizes (i) only.

**No YAML in the kernel.** ``yaml.safe_load`` is a runtime-lane concern (design #31
§1.2 lane D-R, ``tos_runtime.strategy.load_strategies``); the kernel accepts an
already-decoded plain ``Mapping`` (``dict``, typically from ``yaml.safe_load`` or
JSON) and does pydantic validation only — no file I/O, no YAML parser import here
(the kernel firewall forbids third-party deps outside the design §3.2 allowlist,
which does not include a YAML library).

**Validation, not free-form construction.** :func:`parse_strategy` accepts only the
*authoring content* a strategy config supplies — ``dsl_version``,
``config_binding_version``, ``policy``, and an optional ``canonicalization_version``
— never a pre-computed ``canonical_digest`` / ``strategy_id`` / ``status``. Those
three are exactly :class:`~tos.dsl.strategy.AuthoredStrategy`'s own
``_REQUIRED_COVERED`` set, and they are *derived*, never author-supplied (design
§4.1 "mutate/forge is unconstructable" — a hand-written digest could otherwise
smuggle a stale or forged binding past the checks that assume ``id = f(digest)``).
A validated mapping is therefore fed straight into
:meth:`~tos.dsl.strategy.AuthoredStrategy.issue`, the same digest/id derivation an
in-process typed caller uses, so the parsed and the in-process paths converge on one
artifact shape before either ever reaches
:func:`tos.engine.admission.strategy_admissible` (design #31 §1.2 "두 경로 동형").

**Unknown keys are refused with their path.** Every :mod:`tos.dsl.vocabulary` model
inherits ``extra="forbid"`` from :class:`~tos.dsl._base.FrozenModel`, and the
wrapper model below does too, so an unrecognized key at *any* nesting level
(top-level, ``policy``, a rule's ``all_of``, an operand, a target, …) fails pydantic
validation with a ``loc`` path pydantic itself computes; :func:`parse_strategy`
re-raises that as a :class:`StrategyParseError` naming the dotted path.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design §firewall). No
``yaml``/``json`` parsing lives here — the input is already a decoded mapping.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl._base import ArtifactIntegrityError, FrozenModel
from tos.dsl.strategy import AuthoredStrategy
from tos.dsl.vocabulary import DecisionPolicy

__all__ = ["StrategyParseError", "parse_strategy"]


class StrategyParseError(ArtifactIntegrityError):
    """A serialized strategy mapping failed pydantic validation (design #31 §9-4).

    Subclasses :class:`~tos.dsl._base.ArtifactIntegrityError` (itself a
    ``ValueError``), so a malformed serialized strategy is a caught, actionable
    error — never an uncaught ``pydantic.ValidationError`` leaking out of the
    kernel's public surface. The message names every failing field's dotted path
    (pydantic's own ``loc``), so a config author is told exactly what to fix.
    """


class _StrategyAuthoringContent(FrozenModel):
    """The pydantic validation shape for a serialized strategy mapping (design #31 §9-4).

    Deliberately narrower than :class:`~tos.dsl.strategy.AuthoredStrategy` itself: a
    mapping supplies only authoring content, never the derived identity/digest/
    status triple (module docstring). ``extra="forbid"`` (inherited from
    :class:`~tos.dsl._base.FrozenModel`) rejects an unknown top-level key here, and
    every nested :mod:`tos.dsl.vocabulary` model rejects an unknown key at its own
    level the same way — so the rejection is not limited to the outermost mapping.
    """

    dsl_version: str
    config_binding_version: str
    policy: DecisionPolicy
    #: Optional: which :class:`~tos.canonical.CanonicalizationScheme` to issue
    #: under. Defaults to the package's provisional scheme (module docstring's
    #: honesty note; every digest in this package rides ``ev-l1-provisional-0``
    #: until a production scheme is ratified — design #31 §1.1 item 1) rather than
    #: requiring every config file to name a scheme that does not vary yet.
    canonicalization_version: str | None = None


def _format_validation_error(exc: ValidationError) -> str:
    """Render a pydantic :class:`ValidationError` as ``"path: message; path: message"``.

    Args:
        exc: The pydantic validation error to render.

    Returns:
        A semicolon-joined rendering; each entry names its dotted ``loc`` path (or
        ``<root>`` when the failure has none) and pydantic's own message.
    """
    parts: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error["loc"]) or "<root>"
        parts.append(f"{loc}: {error['msg']}")
    return "; ".join(parts)


def parse_strategy(mapping: Mapping[str, Any]) -> AuthoredStrategy:
    """Parse + issue an Authored Strategy from a plain mapping (design #31 §9-4).

    Pydantic validation only (module docstring) — ``mapping`` is already a decoded
    ``dict`` (from YAML/JSON; the runtime lane owns that decode step, design #31
    §1.2 lane D-R). An unknown key at any nesting level is refused, named by its
    dotted path. A validated mapping is then issued into a content-addressed
    :class:`~tos.dsl.strategy.AuthoredStrategy` — the identical digest/id derivation
    an in-process typed caller uses via
    :meth:`~tos.dsl.strategy.AuthoredStrategy.issue` — so both authoring paths
    converge on one artifact shape.

    Args:
        mapping: The raw (already YAML/JSON-decoded) strategy authoring content:
            ``dsl_version``, ``config_binding_version``, ``policy``, and an optional
            ``canonicalization_version``.

    Returns:
        The issued, digest-verified :class:`~tos.dsl.strategy.AuthoredStrategy`.

    Raises:
        StrategyParseError: If ``mapping`` fails pydantic validation — an unknown
            key at any level, a wrong type, or a nested construction-time integrity
            violation (e.g. an empty ``Rule.all_of`` guard, an ``Operand`` naming
            both/neither of ``const``/``ref``).
    """
    try:
        content = _StrategyAuthoringContent.model_validate(dict(mapping))
    except ValidationError as exc:
        raise StrategyParseError(_format_validation_error(exc)) from exc

    scheme = get_scheme(content.canonicalization_version or EV_L1_PROVISIONAL_VERSION)
    return AuthoredStrategy.issue(  # type: ignore[return-value]
        scheme=scheme,
        dsl_version=content.dsl_version,
        config_binding_version=content.config_binding_version,
        policy=content.policy,
    )
