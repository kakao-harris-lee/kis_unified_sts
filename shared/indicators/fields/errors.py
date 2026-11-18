"""Refusals of the declarative field layer.

Two kinds, because they fail at two different times and a reader has to be able
to tell them apart:

* :class:`FieldSpecError` — the *declaration* is wrong. Raised while parsing
  ``fields.yaml`` (boot / producer start), before a single bar is read. Every
  refusal listed in ``docs/plans/2026-11-11-tos-p2-declarative-fields.md`` §2.2
  is one of these.
* :class:`FieldEvalError` — the declaration parsed, but a *bar* cannot be
  evaluated against it (a missing value reached an op that refuses to read it
  as ``False``, a zero divisor, a non-finite input).

Both derive from :class:`FieldError` so a caller that only wants "the field
layer refused" can catch one class.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class FieldError(RuntimeError):
    """Base class for every refusal of the declarative field layer."""


class FieldSpecError(FieldError):
    """A ``fields.yaml`` declaration is not loadable (refused at boot)."""


class FieldEvalError(FieldError):
    """A bar cannot be evaluated against an otherwise valid declaration.

    Attributes:
        values: The fields that WERE evaluated, in declaration order, before
            the refusal — empty when the refusal happened before any field had
            a value, or when it was raised somewhere that has no bar context.

            This exists because a caller has to be able to tell two refusals
            apart without matching on the message. ``tools/tos_cp3
            /produce_fields.py::produce_bars_declarative`` asks its own
            omission gate (``_inputs_unusable``) about the already-evaluated
            ``close``/``vwap``/``atr``: if the gate names the bar
            unpublishable, the bar is OMITTED with the gate's wording — the
            same bytes the legacy loop wrote into the lineage — and if the gate
            does not, the refusal is a declaration defect and must surface
            rather than be counted as a quiet bar.
    """

    def __init__(
        self, message: str, *, values: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.values: Mapping[str, Any] = dict(values) if values else {}


__all__ = ["FieldError", "FieldEvalError", "FieldSpecError"]
