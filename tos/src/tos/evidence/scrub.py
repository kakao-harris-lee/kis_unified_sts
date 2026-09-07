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

**Container recursion (fixed 2026-09-08, independent-review HIGH finding).** An
earlier revision recursed only into nested ``Mapping``s, so a secret nested inside
a ``list``/``tuple`` element (e.g. ``{"accounts": [{"api_key": "..."}]}``) passed
through unmasked while the docstring claimed "any depth" — a real gap, not a
phantom one (repro: ``scrub_secret_fields({"accounts": [{"api_key": "SECRET"}]},
frozenset({"api_key"}))`` returned ``masked=()`` with the secret intact). This
module now recurses into ``list`` and ``tuple`` **only** — not the general
``collections.abc.Sequence`` (which would wrongly capture ``str``/``bytes`` and
iterate their characters/bytes as "elements", and would also reach exotic sequence
types like ``range`` that never carry payload data) and not ``set``/``frozenset``
(unordered, so a stable positional path notation is not meaningful for them; a
secret inside a set is out of scope for this fix — payloads scrubbed here are
JSON/YAML-shaped, and neither format has a set literal). List/tuple elements are
addressed by position: ``key[i]`` for a direct list/tuple field, ``key[i].leaf``
when the element is itself a mapping. The container type is preserved on output
(``list`` in -> ``list`` out, ``tuple`` in -> ``tuple`` out) so a caller round-tripping
a scrubbed payload does not silently see its tuples become lists.

Pure module: stdlib only (no ``pydantic`` needed — the function operates on plain
``Mapping``/``list``/``tuple`` structures, not a typed artifact); no ``shared.*``,
no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping

__all__ = ["scrub_secret_fields"]

#: The deterministic replacement value for a masked field (ADR-002-016 §16 line
#: 426 "SHALL NOT be recorded" — the original value is never retained, not even
#: truncated or hashed, inside the scrubbed payload itself).
_REDACTED = "***REDACTED***"


def _scrub_value(
    value: object, secret_keys: frozenset[str], path: str
) -> tuple[object, list[str]]:
    """Scrub one already-addressed value: mapping and list/tuple recurse, else a leaf.

    Dispatch order matters for correctness, not just style: ``str``/``bytes`` are
    checked nowhere here because neither is a ``Mapping`` nor a ``list``/``tuple``,
    so they always fall through to the leaf branch unchanged — exactly the "not the
    general Sequence" carve-out the module docstring documents.
    """
    if isinstance(value, Mapping):
        return _scrub_mapping(value, secret_keys, path)
    if isinstance(value, (list, tuple)):
        scrubbed_elements: list[object] = []
        masked: list[str] = []
        for index, element in enumerate(value):
            element_path = f"{path}[{index}]"
            scrubbed_element, nested_masked = _scrub_value(
                element, secret_keys, element_path
            )
            scrubbed_elements.append(scrubbed_element)
            masked.extend(nested_masked)
        preserved: object = (
            tuple(scrubbed_elements) if isinstance(value, tuple) else scrubbed_elements
        )
        return preserved, masked
    return value, []


def _scrub_mapping(
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
        else:
            scrubbed_value, nested_masked = _scrub_value(value, secret_keys, path)
            out[key] = scrubbed_value
            masked.extend(nested_masked)
    return out, masked


def scrub_secret_fields(
    payload: Mapping[str, object], secret_keys: frozenset[str]
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Deterministically mask every field whose key is in ``secret_keys`` (design #40 D3-d).

    Descends into nested mappings (e.g. a ``{"credentials": {"api_key": ...}}``
    payload masks ``credentials.api_key`` without touching sibling fields) AND into
    ``list``/``tuple`` elements (e.g. ``{"accounts": [{"api_key": ...}]}`` masks
    ``accounts[0].api_key``) — a key matching ``secret_keys`` at ANY depth, through
    any mixture of mapping and list/tuple nesting, is masked, keyed by its own leaf
    name (not by the full path) — matching how a "secret field list" is naturally
    authored (field names, not payload-shape-specific paths). Masking is total
    replacement, never partial/truncated redaction (ADR-002-016 §16 line 426 "SHALL
    NOT be recorded" — no residual signal about the original value's length,
    prefix, or shape survives in the scrubbed payload).

    Deterministic: the same ``(payload, secret_keys)`` pair always produces the
    same scrubbed structure and the same masked-key tuple, run twice or run a
    thousand times (ADR-002-016 §16 "the scrubbing result itself is
    deterministic"). No key present in ``secret_keys`` that also occurs in
    ``payload`` -> the payload is returned structurally unchanged (a fresh copy,
    not the same object; list/tuple containers are also freshly built, container
    type preserved) and the masked-key tuple is empty.

    Args:
        payload: The record fields to scrub, as (possibly nested) mappings whose
            values may themselves be mappings, lists, or tuples to any depth.
        secret_keys: The closed set of field names to mask, wherever they occur.

    Returns:
        A ``(scrubbed_payload, masked_keys)`` pair: the scrubbed copy of
        ``payload`` (secret values replaced, structure otherwise identical,
        list/tuple container type preserved), and the **sorted** tuple of paths
        that were masked (``key.nested``, ``key[i]``, ``key[i].leaf`` per depth
        and container mix) — the "fact of scrubbing" evidence the ADR requires
        the caller to attach to the record's meta.
    """
    out, masked = _scrub_mapping(payload, secret_keys, "")
    return out, tuple(sorted(masked))
