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


class FieldError(RuntimeError):
    """Base class for every refusal of the declarative field layer."""


class FieldSpecError(FieldError):
    """A ``fields.yaml`` declaration is not loadable (refused at boot)."""


class FieldEvalError(FieldError):
    """A bar cannot be evaluated against an otherwise valid declaration."""


__all__ = ["FieldError", "FieldEvalError", "FieldSpecError"]
