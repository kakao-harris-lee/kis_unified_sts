"""Deterministic secret-field scrubbing before evidence serialization (design #40 D3-d).

Realizes the *kernel* (pure) half of design doc #40's D3.1 secret-scrubbing decision
(``docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-decisions.md`` §D3.1
line 95): "레코드 직렬화 전 ``scrub()`` 이 D4 의 «비밀 필드 목록» 을 결정론적으로
마스킹하고 그 사실 자체를 항목 메타에 남긴다" — cross-referencing ADR-002-016 §16
line 426 verbatim: "Usable broker secrets, signing material, session cookies, MFA
recovery material, private keys, unrestricted bearer tokens, and plaintext
credentials SHALL NOT be recorded. Secret scrubbing occurs before durable evidence
acceptance when possible, but the scrubbing result itself is deterministic and
evidenced."

:func:`scrub_secret_fields` supplies the "deterministic ... and evidenced" half:
same input twice -> byte-identical output, and the returned masked-key tuple is
exactly the "fact of scrubbing" the ADR requires to be recorded in the item's own
meta (the caller attaches that tuple to the evidence record; this module does not
itself write to any store).

This module does **not** decide *which* fields are secret (design #40 D4 owns the
"secret field list" — D4 custody knows what a credential looks like; design #40
§D4.1 line 110 states the kernel's own limit verbatim: "커널은 자격증명 개념을
모른다 — 커널은 principal 문자열과 route inventory 만 본다"). ``secret_keys`` is
always an injected caller argument, never a hard-coded literal set here.

Pure module: stdlib only (no ``pydantic`` needed — the function operates on plain
``Mapping``s, not a typed artifact); no ``shared.*``, no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping

__all__ = ["scrub_secret_fields"]

#: The deterministic replacement value for a masked field (ADR-002-016 §16 line
#: 426 "SHALL NOT be recorded" — the original value is never retained, not even
#: truncated or hashed, inside the scrubbed payload itself).
_REDACTED = "***REDACTED***"


def _scrub(
    node: Mapping[str, object], secret_keys: frozenset[str], prefix: str
) -> tuple[dict[str, object], list[str]]:
    """Recursively scrub one mapping level; return the scrubbed copy + masked paths."""
    out: dict[str, object] = {}
    masked: list[str] = []
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if key in secret_keys:
            out[key] = _REDACTED
            masked.append(path)
        elif isinstance(value, Mapping):
            nested_out, nested_masked = _scrub(value, secret_keys, path)
            out[key] = nested_out
            masked.extend(nested_masked)
        else:
            out[key] = value
    return out, masked


def scrub_secret_fields(
    payload: Mapping[str, object], secret_keys: frozenset[str]
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Deterministically mask every field whose key is in ``secret_keys`` (design #40 D3-d).

    Descends into nested mappings (e.g. a ``{"credentials": {"api_key": ...}}``
    payload masks ``credentials.api_key`` without touching sibling fields); a key
    matching ``secret_keys`` at ANY depth is masked, keyed by its own leaf name
    (not by the full dotted path) — matching how a "secret field list" is
    naturally authored (field names, not payload-shape-specific paths). Masking is
    total replacement, never partial/truncated redaction (ADR-002-016 §16 line 426
    "SHALL NOT be recorded" — no residual signal about the original value's
    length, prefix, or shape survives in the scrubbed payload).

    Deterministic: the same ``(payload, secret_keys)`` pair always produces the
    same scrubbed mapping and the same masked-key tuple, run twice or run a
    thousand times (ADR-002-016 §16 "the scrubbing result itself is
    deterministic"). No key present in ``secret_keys`` that also occurs in
    ``payload`` -> the payload is returned structurally unchanged (a fresh copy,
    not the same object) and the masked-key tuple is empty.

    Args:
        payload: The record fields to scrub, as (possibly nested) mappings.
        secret_keys: The closed set of field names to mask, wherever they occur.

    Returns:
        A ``(scrubbed_payload, masked_keys)`` pair: the scrubbed copy of
        ``payload`` (secret values replaced, structure otherwise identical), and
        the **sorted** tuple of dotted paths that were masked — the "fact of
        scrubbing" evidence the ADR requires the caller to attach to the record's
        meta.
    """
    out, masked = _scrub(payload, secret_keys, "")
    return out, tuple(sorted(masked))
