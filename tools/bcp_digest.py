#!/usr/bin/env python3
"""Broker Capability Profile digest tool — PROVISIONAL canonicalizer.

==============================================================================
NON-PRODUCTION.  ALGORITHM ID = ``ev-l1-provisional-0``.
==============================================================================
This tool implements a **provisional** canonicalizer adopted under operator
decision **D5 (2026-07-29)** so that the KIS Broker Capability Profile INSTANCE
(``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml``) can carry a
reproducible ``canonical_semantic_digest`` / ``byte_digest`` pair at approval
time instead of two permanent ``TBD`` slots.

It is **not** the production canonicalization scheme. Production
canonicalization — versioned canonical form, signature binding, content
addressing, cross-artifact digest binding, canonicalization-version negotiation
— remains the open **G2** work item recorded at
``docs/plans/2026-07-29-tos-broker-capability-profile-kis-draft.md:284`` (U-1)
and ``docs/plans/2026-07-29-tos-phase0-p02-execution-plan.md:46`` (D5). Every
digest this tool emits is self-identifying (``ev-l1-provisional-0:...``) so a
future production digest can never be confused with, or silently substituted
for, one of these.

This tool NEVER writes to a profile. It computes and it verifies; filling the
digest fields is an approval-time authoring act performed by a human.

REVISION HISTORY
    attempt-1 (2026-07-29) — adversarial review returned REVISE with three
    blocking findings. attempt-2 (2026-07-30) implements all of them; the
    decisions they changed are marked **AMENDED** below and keep the superseded
    text as history, because a governance object must show what it used to
    claim. Any change to a digest VALUE produced by this file — not merely to
    the code — requires bumping ``ALGORITHM_ID``; the frozen golden vectors in
    ``tests/tools/test_bcp_digest.py`` exist to make that impossible to miss.

------------------------------------------------------------------------------
NORMATIVE ANCHORS (what the corpus actually requires of these two fields)
------------------------------------------------------------------------------
The corpus fixes the *properties*, not the algorithm. Each anchor below shaped
one design choice; where the corpus is silent, the choice is recorded in the
PROVISIONAL DECISION list and is explicitly provisional.

* ``tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md:1556``
  (SPG-EV-003 — Schema, Omission, and Canonicalization Safety):
  "Canonical semantic digests agree only for identical meaning; ambiguous,
  unresolved, omitted, unknown, incompatible, or parser-dependent content
  grants zero new-risk authority." Its injection list — "unknown, duplicate,
  deprecated, extension, aliased, reordered, Unicode-variant ... content; vary
  parsers and canonicalization versions" — is the direct source of P-3, P-4,
  P-8, P-12, P-15 and P-16 below.
* ``VER-002-001-...-Specification.md:2112`` (IOC-EV-007 — Canonicalization and
  Parser Differential): "byte and semantic digests cannot be used
  interchangeably without proof." Source of P-1 (the digest KIND segment).
* ``tos-spec/src/part-1-foundation/ADR-002-020-...-Fencing.md:161``
  (IOC-INV-002): "The same complete approved inputs ... produce the same
  canonical semantic command and digest, or construction fails." Determinism is
  mandatory; ambiguity must FAIL, not be repaired. Source of the fail-closed
  posture throughout (P-8, P-9, P-11, P-14, P-17).
* ``tos-spec/src/part-1-foundation/ADR-002-014-...-Governance.md:303-306`` (§11
  Semantic Validation, items 2-3): "schema completeness and canonical semantic
  reproducibility" plus explicit rejection of NaN / infinity / lossy numeric
  handling. Source of P-9.
* ``ADR-002-014-...-Governance.md:294``: content is only outside a digest when
  an approved artifact defines a finite closed interpretation for it; and
  ``ADR-002-019-...-Gate.md:343``: "The canonical digest SHALL cover all fields
  that can change the decision or economic effect." Source of P-5's rule that
  the exclusion list is minimal, enumerated, and justified per entry.
* ``tos-spec/src/part-1-foundation/ADR-002-004-...-Fallbacks.md:272-281`` (§7.3
  Activation) + ``verification/HUMAN-APPROVAL-ATTESTATION-template.yaml:7,20-38``
  (``request_digest`` and the reviewed/validated input-digest lists): an
  approval attests TO a digest of already-fixed content. Source of P-5's
  freeze-then-compute-then-record workflow.
* ``tos-spec/src/part-1-foundation/verification/BROKER-CAPABILITY-PROFILE-template.yaml:79-81``
  — the three slots this tool serves (``canonicalization_version``,
  ``canonical_semantic_digest``, ``byte_digest``) are bare ``TBD`` with no
  comment: the template states no byte scope, no hash, no canonical form. That
  silence is exactly the latitude D5 grants, and every gap it leaves is filled
  by a numbered PROVISIONAL DECISION below.
* ``BROKER-CAPABILITY-PROFILE-template.yaml:46-51`` — the fill convention.
  ``TBD`` means "a value is OWED", never a defined value. Source of P-7 (the
  blanking placeholder), P-14 (the recorded-value grammar), and of ``verify``
  treating ``TBD`` as a mismatch.

------------------------------------------------------------------------------
PROVISIONAL DECISIONS (every choice the corpus leaves open, enumerated)
------------------------------------------------------------------------------
P-1  Digest string shape is ``<algorithm-id>:<kind>:sha256:<lowercase-hex>``,
     e.g. ``ev-l1-provisional-0:semantic:sha256:ab12...``. The algorithm id
     makes the value self-identifying; the KIND segment (``semantic`` /
     ``byte``) makes an interchange of the two digests detectable by string
     inspection alone, which IOC-EV-007 (:2112) forbids without proof.

P-2  Hash = SHA-256. The canonical form is encoded UTF-8 before hashing.

P-3  Semantic canonical form = parse the YAML document, then serialize the
     resulting value tree as canonical JSON via
     ``json.dumps(obj, sort_keys=True, ensure_ascii=False,
     separators=(",", ":"), allow_nan=False)``. Comments, key order, indent
     style, quoting style and line endings therefore drop out of the semantic
     digest by construction — the invariance SPG-EV-003 (:1556) demands. YAML is
     a poor canonical form and JSON is a lossy one; this is a provisional
     convenience, not a claim of adequacy.

P-4  Strings AND mapping keys are Unicode NFC-normalized before serialization.
     Caveat recorded honestly: SPG-EV-003 lists "Unicode-variant" content as an
     ATTACK injection, and a production canonicalizer may well decide to
     *reject* non-NFC input instead of silently folding it. Folding is the
     weaker of the two behaviors and is provisional. Two distinct keys that
     collide after normalization are refused (ambiguity fails closed).

P-5  **AMENDED (attempt-2, review F2).** Semantic-digest exclusion list —
     exactly TWO fields, both top-level ``profile_identity`` members, and
     nothing else:
       * ``canonical_semantic_digest`` — a digest cannot cover itself.
       * ``byte_digest`` — same self-reference (see P-7 for its own fixed
         point).
     **``approvers`` is COVERED by both digests.** The approval workflow is
     therefore freeze-then-compute-then-record, in one act:
       1. freeze ``approvers[]`` with EVERY entry present (the AI-review entry
          and the operator countersign are recorded together — the D1
          single-operator + AI-review model has no sequential sign-off), and
          fix ``status``, ``canonicalization_version`` and all other content;
       2. compute both digests over that frozen artifact;
       3. record the two digest values, changing nothing else.
     Appending an approver afterwards invalidates BOTH digests and ``verify``
     says so. That is the intended behavior: an attestation must bind a fully
     frozen artifact (ADR-002-004 §7.3:272-281; HUMAN-APPROVAL-ATTESTATION
     ``request_digest``).
     *Superseded attempt-1 text, kept as history:* "``approvers`` is excluded
     because the approval act attests TO the digest, so covering the approver
     list would make the digest change at the moment of approval." Review F2
     showed that exclusion bought nothing — ``byte_digest`` covered
     ``approvers`` anyway, so the stated harm merely moved one field over —
     while combining with the F1 blanking defect to leave the approver set
     bound by NEITHER digest. Orchestrator ruling: drop the exclusion.
     Everything else IS covered — including the instance-local ``_``-prefixed
     annotations (``_kis``, ``_model_view``): excluding content is a claim that
     the content cannot change meaning, and no such claim has been approved
     (ADR-002-019:343). Recorded consequence: ``status``, ``effective_from``,
     ``expires_at`` and ``revocation_record`` are inside the digest, so
     recording a revocation changes ``canonical_semantic_digest`` and a consumer
     pinned to the approved value then fails closed. Denial is the safe
     direction, but a production canonicalizer must make that call deliberately.

P-6  ``byte_digest`` scope = the WHOLE FILE, recorded identically in every
     document of that file. The template states no per-document byte scope, and
     the artifact that is reviewed, transported and approved is the file. Both
     KIS documents therefore carry the same ``byte_digest``; this is file
     integrity, NOT capability inheritance, and does not touch ADR-002-004
     §13.14 / BC-INV-009 (which govern capability status across environments).
     The two documents remain distinguished by their differing
     ``canonical_semantic_digest``.

P-7  **AMENDED (attempt-2, review F1).** ``byte_digest`` fixed point, derived
     STRUCTURALLY. The byte digest is taken over the file bytes with the
     *values* of the two digest fields replaced by the fill convention's ``TBD``
     placeholder (template :46-51). Without that replacement the field is
     unsatisfiable: writing the digest into the file changes the file, so no
     recorded value could ever verify.
     The replaced span is taken from the parsed value node's
     ``start_mark.index``/``end_mark.index``, so **the text that is edited and
     the structural field that is excluded are the same object by
     construction** — they cannot disagree, silently or otherwise. Three hard
     refusals fence the remaining ambiguity:
       (i)   a digest key must be the SOLE key on its physical line — nothing
             but whitespace before it, nothing but whitespace and an optional
             ``#`` comment after its value;
       (ii)  the value must be a scalar node (no flow mapping, sequence, block
             scalar, or multi-line value);
       (iii) the raw text of the value span must equal the loaded value.
     Everything else — every comment, every space (including the exact padding
     between a digest value and a trailing comment), key order, encoding, line
     endings — stays inside the byte scope, which is what makes the byte digest
     strictly stronger than, and never a substitute for, the semantic one.
     *Superseded attempt-1 mechanism, kept as history:* a line regex
     ``^([ \\t]*(?:key)[ \\t]*:[ \\t]*)([^#\\n]*?)([ \\t]*(?:#.*)?)$``. Review F1
     showed its value group swallowed the whole remainder of a physical line, so
     a digest key sharing a line with other content (flow style) deleted those
     co-resident fields from the byte-digest input while the occurrence-count
     guard stayed balanced — including, in the reviewer's ADV-2, the
     ``approvers`` list, which was then bound by no digest at all.

P-8  Fail-closed parsing. ``yaml.SafeLoader`` only; strict UTF-8 decode;
     duplicate mapping keys are REJECTED (PyYAML's default last-wins is exactly
     the "duplicate ... content" ambiguity SPG-EV-003 injects); ``<<`` merge
     keys are rejected by an explicit constructor, not as a side effect of not
     calling ``flatten_mapping`` (review F13); any parse error is a nonzero
     exit, never a partial result.

P-9  Value-type closure. Only ``null``, ``bool``, ``int``, finite ``float``,
     ``str``, ``list``, and mappings with ``str`` keys may appear. NaN,
     ±Infinity, YAML timestamps/dates, binary, ``tuple`` (which is what PyYAML
     produces for ``!!omap``/``!!pairs`` — review F4), and non-string keys are
     REFUSED rather than coerced (ADR-002-014 §11:303-306). Practical
     consequence: a date in the instance must be quoted, so that its canonical
     form is the author's chosen text and not a parser's datetime rendering.

P-10 Document-count guard: the file must contain exactly 2 YAML documents
     unless ``--allow-any-doc-count`` is passed. The KIS instance is defined as
     a two-document file (draft header :132-140, one document per environment);
     a file that silently gained or lost a document is not the artifact that was
     reviewed.

P-11 Placement guard: ``canonical_semantic_digest`` / ``byte_digest`` may appear
     ONLY as top-level ``profile_identity`` members. A stray occurrence anywhere
     else is refused. The number of located text spans must equal the number of
     structurally present digest fields — a secondary cross-check now that P-7
     derives the two from one parse.

P-12 ``canonicalization_version`` must equal the algorithm id
     (``ev-l1-provisional-0``) for ``verify`` to pass. SPG-EV-003 injects
     "vary ... canonicalization versions" and expects a fail-closed result, so a
     profile that names a different canonicalizer must not verify against this
     one. ``TBD``/``null`` is a mismatch, not a pass. NOTE: this field is INSIDE
     the semantic digest, so it must be filled BEFORE the digests are computed
     (see the P-5 workflow). ``compute`` prints the value that has to be
     recorded.

P-13 Out of scope, deliberately: signing, content-addressed storage,
     cross-artifact digest binding, digest registry/publication, and
     canonicalization-version negotiation. Those belong to the G2 production
     work item.

P-14 **NEW (attempt-2, review F6).** Recorded digest-value grammar. Before any
     span is replaced, the raw text of each recorded digest value must match
     either ``TBD`` or
     ``ev-l1-provisional-0:(semantic|byte):sha256:[0-9a-f]{64}`` exactly.
     ``null``, an empty value, a quoted string, and anything else is REFUSED
     (write ``TBD`` to mean "owed"). This removes the class of values that could
     partially survive replacement — the reviewer's ``byte_digest: aaa#bbb``
     leaving ``TBD#bbb`` behind — and makes the fixed point checkable rather
     than assumed.

P-15 **NEW (attempt-2, review F9/F11).** Parser identity and the YAML 1.1
     hazard lint. The canonical form depends on the parser's scalar resolution.
     PyYAML implements YAML **1.1**, where ``yes``/``no``/``on``/``off`` are
     booleans, ``12:30`` is the integer 750, ``010`` is octal 8, and ``1_000``
     is 1000 — a YAML 1.2 parser reading the same bytes would compute a
     DIFFERENT digest under the same algorithm id. Two mitigations:
       (a) ``compute`` prints the parser and Unicode identity (PyYAML version,
           YAML 1.1, ``unicodedata.unidata_version``) so the environment that
           produced a value is recorded next to it; NFC folding (P-4) is
           Unicode-data-version dependent, and the frozen golden vectors are
           what would catch a drift;
       (b) every PLAIN (unquoted) scalar whose resolved TYPE differs between
           this parser and YAML 1.2 — in EITHER direction — is REFUSED with a
           "quote it" message, mirroring the P-9 date refusal. Most entries
           diverge one way (this parser resolves away from a string: ``yes``,
           ``12:30``, ``010``, ``0b101``, ``1_000``); ``0o17`` diverges the other
           way (this parser has no ``0o`` form and keeps the string, while YAML
           1.2 core reads 15). The list is drawn by MEASUREMENT, not by reading
           a spec: each entry's resolved type under this parser is pinned by a
           test, which is how the attempt-2 review caught two wrong premises
           (``09`` and ``0o17``).
     Recorded residual: the single letters ``y``/``n`` are booleans in the YAML
     1.1 *spec* but PyYAML resolves them to ``str``, exactly as YAML 1.2 does.
     They are therefore NOT refused — the live KIS draft uses ``n`` as a
     sample-size key — and the residual risk is that a third YAML 1.1
     implementation would read them as booleans and compute a different digest.
     That risk is covered by (a): the digest is defined by the recorded parser
     identity, not by "YAML" in the abstract.
     A production canonicalizer should pin the parser inside the algorithm id.

P-16 **NEW (attempt-2, review F8/F13).** Anchors and aliases are REFUSED.
     SPG-EV-003 lists "aliased" content among its injections; an alias makes one
     value reachable at two paths and a recursive anchor (``&x [*x]``) makes the
     value tree infinite. Both are refused while the node graph is composed,
     before any value is constructed.

P-17 **NEW (attempt-2, review F8).** Bounded work, and every failure arrives as
     a refusal. Nesting deeper than ``MAX_NESTING_DEPTH`` is refused instead of
     raising ``RecursionError``; a string that cannot be UTF-8 encoded (a lone
     surrogate) is refused at the point of normalization instead of raising
     ``UnicodeEncodeError`` out of the hashing step. The CLI contract is that
     every non-zero exit carries a ``REFUSED`` line naming the cause.

------------------------------------------------------------------------------
USAGE
------------------------------------------------------------------------------
    python tools/bcp_digest.py compute docs/broker-profiles/KIS-....yaml
    python tools/bcp_digest.py verify  docs/broker-profiles/KIS-....yaml

``compute`` prints, for every document, the identity, both digests, and the
EXACT replacement lines to paste into the file (byte-for-byte, including each
line's existing trailing comment and its padding — re-aligning that padding
changes the byte digest, see P-7).

``verify`` exits 0 only if every document's recorded ``canonicalization_version``
and both digests match a fresh recomputation; every other outcome — mismatch,
``TBD``, absent field, parse error, guard refusal — exits nonzero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# ============================================================================
# Provisional algorithm constants (P-1, P-2, P-12, P-14)
# ============================================================================

ALGORITHM_ID = "ev-l1-provisional-0"
SEMANTIC_KIND = "semantic"
BYTE_KIND = "byte"
HASH_NAME = "sha256"

#: The fill-convention placeholder (template :46-51). Never a value.
PLACEHOLDER = "TBD"

#: Top-level mapping that carries the profile key and the digest slots.
IDENTITY_KEY = "profile_identity"

#: The two digest fields, in template order (template :80-81).
DIGEST_KEYS = ("canonical_semantic_digest", "byte_digest")

#: P-5 (AMENDED) — the complete semantic-digest exclusion list. ``approvers``
#: is deliberately NOT here; see the P-5 freeze-then-compute workflow.
SEMANTIC_EXCLUDED_IDENTITY_KEYS = DIGEST_KEYS

#: P-17 — refuse rather than exhaust the interpreter stack.
MAX_NESTING_DEPTH = 64

#: Identity fields echoed by ``compute`` so a reader can tell the documents
#: apart without opening the file.
_IDENTITY_LABEL_KEYS = ("artifact_id", "environment", "broker_id", "profile_version")

#: P-14 — the only two shapes a recorded digest field may hold.
_RECORDED_VALUE_RE = re.compile(
    rf"\A(?:{re.escape(PLACEHOLDER)}"
    rf"|{re.escape(ALGORITHM_ID)}:(?:{SEMANTIC_KIND}|{BYTE_KIND})"
    rf":{HASH_NAME}:[0-9a-f]{{64}})\Z"
)

#: P-7 (i) — what may follow a digest value on its physical line.
_LINE_TRAIL_RE = re.compile(r"\A[ \t\r]*(?:#[^\n]*)?\Z")

#: P-15 (b) — plain scalars that THIS parser resolves away from a plain string
#: in a way YAML 1.2 does not. Each pattern's premise (PyYAML really does
#: resolve it to a non-str type) is pinned by a test, so the list cannot rot
#: into folklore. Deliberately NOT included: the single letters ``y``/``n``,
#: which the YAML 1.1 *spec* lists as booleans but which PyYAML resolves to
#: ``str`` exactly as YAML 1.2 does — see the P-15 residual note.
_YAML_11_HAZARDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\A(?:yes|Yes|YES|no|No|NO|on|On|ON|off|Off|OFF)\Z"),
        "YAML 1.1 boolean (this parser reads it as a bool; YAML 1.2 as a string)",
    ),
    (
        re.compile(r"\A[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+\Z"),
        "YAML 1.1 sexagesimal (12:30 resolves to the integer 750)",
    ),
    (
        # Only true octal digits: this parser leaves `09` a string (measured),
        # so refusing it would be an over-refusal.
        re.compile(r"\A[-+]?0[0-7_]+\Z"),
        "YAML 1.1 octal (010 resolves to 8, 0755 to 493)",
    ),
    (
        re.compile(r"\A[-+]?0[bB][01_]+\Z"),
        "YAML 1.1 binary (this parser resolves 0b101 to 5; YAML 1.2 core, which "
        "has no binary form, reads it as a string)",
    ),
    (
        # Divergence in the OPPOSITE direction from the rest of this list: this
        # parser has no `0o` form and keeps it a STRING, while YAML 1.2 core
        # reads it as an integer. Measured, not assumed — see the premise test.
        re.compile(r"\A[-+]?0[oO][0-7_]+\Z"),
        "YAML 1.2 octal spelling (this parser keeps '0o17' a string; YAML 1.2 "
        "core reads it as the integer 15)",
    ),
    (
        re.compile(r"\A[-+]?[0-9][0-9_]*_[0-9_]*(?:\.[0-9_]*)?\Z"),
        "underscored numeric (YAML 1.1 digit separator: 1_000 resolves to 1000)",
    ),
)

_NON_PRODUCTION_BANNER = (
    f"bcp-digest: canonicalizer {ALGORITHM_ID} — PROVISIONAL, NON-PRODUCTION "
    "(operator decision D5, 2026-07-29; production canonicalization = G2)"
)


def environment_line() -> str:
    """P-15 (a) — the parser/Unicode identity that produced a digest."""
    return (
        f"environment: PyYAML {yaml.__version__} (YAML 1.1 scalar resolution), "
        f"Unicode {unicodedata.unidata_version}, {HASH_NAME}"
    )


class ProfileDigestError(Exception):
    """Any condition under which a digest must NOT be produced (fail-closed)."""


# ============================================================================
# P-8 — fail-closed YAML loading
# ============================================================================


class _StrictSafeLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys and ``<<`` merge keys."""


def _construct_mapping_no_duplicates(
    loader: _StrictSafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            mark = key_node.start_mark
            raise ProfileDigestError(
                f"duplicate mapping key {key!r} at line {mark.line + 1}, "
                f"column {mark.column + 1}: duplicate content is ambiguous and "
                "fails closed (P-8, SPG-EV-003)"
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


def _refuse_merge_key(loader: _StrictSafeLoader, node: yaml.Node) -> Any:
    """P-8 / review F13 — refuse ``<<`` explicitly, not by omission."""
    del loader
    mark = node.start_mark
    raise ProfileDigestError(
        f"YAML merge key '<<' at line {mark.line + 1}: a merged mapping is content "
        "that is not written where it is read; it fails closed (P-8)"
    )


_StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_no_duplicates,
)
_StrictSafeLoader.add_constructor("tag:yaml.org,2002:merge", _refuse_merge_key)


def read_text(path: Path) -> str:
    """Read the file as strict UTF-8 text, preserving line endings exactly."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ProfileDigestError(f"cannot read {path}: {exc}") from exc
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProfileDigestError(f"{path} is not valid UTF-8: {exc}") from exc


def load_documents(text: str, *, source: str = "<text>") -> list[Any]:
    """Parse every YAML document in ``text`` into values (fail-closed)."""
    try:
        return list(yaml.load_all(text, Loader=_StrictSafeLoader))
    except ProfileDigestError:
        raise
    except yaml.YAMLError as exc:
        raise ProfileDigestError(f"{source}: YAML parse error: {exc}") from exc


def compose_documents(text: str, *, source: str = "<text>") -> list[yaml.Node]:
    """Compose every YAML document into a node graph (marks and styles)."""
    try:
        return list(yaml.compose_all(text, Loader=_StrictSafeLoader))
    except ProfileDigestError:
        raise
    except yaml.YAMLError as exc:
        raise ProfileDigestError(f"{source}: YAML parse error: {exc}") from exc


# ============================================================================
# P-3, P-4, P-9, P-17 — canonical semantic form
# ============================================================================


def _nfc(text: str, path: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    try:
        normalized.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ProfileDigestError(
            f"{path}: string is not UTF-8 encodable (lone surrogate?): {exc} (P-17)"
        ) from exc
    return normalized


def _canonicalize(value: Any, path: str, depth: int = 0) -> Any:
    """Return the canonical form of ``value`` or raise (P-4, P-9, P-17)."""
    if depth > MAX_NESTING_DEPTH:
        raise ProfileDigestError(
            f"{path}: nesting deeper than {MAX_NESTING_DEPTH} levels — refusing "
            "rather than exhausting the stack (P-17)"
        )
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ProfileDigestError(
                f"{path}: NaN/Infinity is not a canonicalizable value "
                "(ADR-002-014 §11:303-306)"
            )
        return value
    if isinstance(value, str):
        return _nfc(value, path)
    if isinstance(value, list):
        return [
            _canonicalize(item, f"{path}[{i}]", depth + 1)
            for i, item in enumerate(value)
        ]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProfileDigestError(
                    f"{path}: mapping key {key!r} is {type(key).__name__}, not str; "
                    "quote it so its canonical form is the author's text (P-9)"
                )
            norm_key = _nfc(key, f"{path}/<key>")
            if norm_key in out:
                raise ProfileDigestError(
                    f"{path}: keys {key!r} and its NFC-equivalent collide after "
                    "Unicode normalization; ambiguity fails closed (P-4)"
                )
            out[norm_key] = _canonicalize(item, f"{path}/{norm_key}", depth + 1)
        return out
    raise ProfileDigestError(
        f"{path}: value of type {type(value).__name__} is outside the canonical "
        "type closure (null/bool/int/finite float/str/list/str-keyed map); quote "
        "it in the YAML instead of letting the parser render it (P-9)"
    )


def canonical_json(value: Any, *, path: str = "$") -> str:
    """Canonical JSON text for ``value`` (P-3)."""
    return json.dumps(
        _canonicalize(value, path),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_hex(text: str, *, what: str) -> str:
    try:
        payload = text.encode("utf-8")
    except UnicodeEncodeError as exc:  # pragma: no cover - _nfc refuses first
        raise ProfileDigestError(
            f"{what} is not UTF-8 encodable: {exc} (P-17)"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def format_digest(kind: str, hex_digest: str) -> str:
    """Render a self-identifying digest string (P-1)."""
    return f"{ALGORITHM_ID}:{kind}:{HASH_NAME}:{hex_digest}"


def semantic_view(document: Any, *, index: int) -> dict[str, Any]:
    """Return ``document`` with the P-5 exclusion list removed."""
    if not isinstance(document, dict):
        raise ProfileDigestError(
            f"document {index}: top level is {type(document).__name__}, not a "
            "mapping; a Broker Capability Profile is a mapping"
        )
    identity = document.get(IDENTITY_KEY)
    if not isinstance(identity, dict):
        raise ProfileDigestError(
            f"document {index}: {IDENTITY_KEY!r} is missing or is not a mapping "
            "(template :76-97); refusing to digest an unidentifiable artifact"
        )
    view = dict(document)
    view[IDENTITY_KEY] = {
        key: item
        for key, item in identity.items()
        if key not in SEMANTIC_EXCLUDED_IDENTITY_KEYS
    }
    return view


def semantic_digest(document: Any, *, index: int = 0) -> str:
    """``canonical_semantic_digest`` for one parsed document (P-1..P-5, P-9)."""
    payload = canonical_json(semantic_view(document, index=index))
    return format_digest(
        SEMANTIC_KIND, _sha256_hex(payload, what=f"document {index} canonical JSON")
    )


# ============================================================================
# P-7, P-11, P-14, P-15, P-16 — node-level scan and structural blanking
# ============================================================================


@dataclass(frozen=True)
class DigestSlot:
    """One recorded digest field, located structurally in the source text."""

    doc_index: int
    key: str
    value_start: int
    value_end: int
    line_number: int
    line_prefix: str
    line_trail: str
    raw_value: str

    def replacement_line(self, digest: str) -> str:
        """The exact physical line to write for ``digest`` (P-7, review F7)."""
        return f"{self.line_prefix}{digest}{self.line_trail}"


def _line_span(text: str, index: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    return start, len(text) if end == -1 else end


def scan_nodes(nodes: list[yaml.Node]) -> None:
    """Refuse aliases, stray digest keys and YAML 1.1 hazards (P-11/15/16/17)."""
    stray: list[str] = []
    seen: set[int] = set()

    def check_scalar(node: yaml.ScalarNode, path: tuple[str, ...]) -> None:
        if node.style is not None:
            return
        for pattern, reason in _YAML_11_HAZARDS:
            if pattern.match(node.value):
                raise ProfileDigestError(
                    f"/{'/'.join(path)} (line {node.start_mark.line + 1}): unquoted "
                    f"{node.value!r} is a {reason}; quote it so its canonical form "
                    "is the author's text (P-15)"
                )

    def walk(node: yaml.Node, path: tuple[str, ...], index: int, depth: int) -> None:
        if depth > MAX_NESTING_DEPTH:
            raise ProfileDigestError(
                f"document {index}: nesting deeper than {MAX_NESTING_DEPTH} levels "
                "— refusing (P-17)"
            )
        if id(node) in seen:
            raise ProfileDigestError(
                f"/{'/'.join(path)} (line {node.start_mark.line + 1}): YAML "
                "anchor/alias reuse makes one value reachable at two paths; it "
                "fails closed (P-16)"
            )
        seen.add(id(node))

        if isinstance(node, yaml.ScalarNode):
            check_scalar(node, path)
        elif isinstance(node, yaml.SequenceNode):
            for i, child in enumerate(node.value):
                walk(child, (*path, f"[{i}]"), index, depth + 1)
        elif isinstance(node, yaml.MappingNode):
            for key_node, value_node in node.value:
                key_name = (
                    key_node.value if isinstance(key_node, yaml.ScalarNode) else "?"
                )
                walk(key_node, (*path, f"<key {key_name}>"), index, depth + 1)
                if key_name in DIGEST_KEYS and path != (IDENTITY_KEY,):
                    stray.append(
                        f"document {index}: /{'/'.join((*path, str(key_name)))} "
                        f"(line {key_node.start_mark.line + 1})"
                    )
                walk(value_node, (*path, str(key_name)), index, depth + 1)

    for index, node in enumerate(nodes):
        walk(node, (), index, 0)

    if stray:
        raise ProfileDigestError(
            f"digest field(s) found outside {IDENTITY_KEY!r} — refusing (P-11):\n  "
            + "\n  ".join(stray)
        )


def _build_slot(
    text: str, index: int, key_node: yaml.ScalarNode, value_node: yaml.Node
) -> DigestSlot:
    key = str(key_node.value)
    where = (
        f"document {index} {IDENTITY_KEY}.{key} "
        f"(line {key_node.start_mark.line + 1})"
    )

    if not isinstance(value_node, yaml.ScalarNode):
        raise ProfileDigestError(
            f"{where}: value is a {type(value_node).__name__}, not a scalar; a "
            "digest field must be a lone scalar on its own line (P-7 ii)"
        )
    if key_node.start_mark.line != value_node.end_mark.line:
        raise ProfileDigestError(
            f"{where}: key and value do not share one physical line; a digest "
            "field must be a lone scalar on its own line (P-7 i)"
        )

    line_start, line_end = _line_span(text, key_node.start_mark.index)
    value_start = value_node.start_mark.index
    value_end = value_node.end_mark.index

    if text[line_start : key_node.start_mark.index].strip(" \t"):
        raise ProfileDigestError(
            f"{where}: content precedes the key on its physical line; a digest key "
            "must be the sole key on its line (P-7 i)"
        )
    trail = text[value_end:line_end]
    if not _LINE_TRAIL_RE.match(trail):
        raise ProfileDigestError(
            f"{where}: content follows the value on its physical line "
            f"({trail.strip()!r}); a digest key must be the sole key on its line "
            "(P-7 i)"
        )

    raw = text[value_start:value_end]
    if not _RECORDED_VALUE_RE.match(raw):
        raise ProfileDigestError(
            f"{where}: recorded value {raw!r} is neither {PLACEHOLDER!r} nor a "
            f"well-formed {ALGORITHM_ID} digest; write {PLACEHOLDER} to mean "
            '"a value is OWED" (P-14)'
        )
    if raw != value_node.value:  # pragma: no cover - P-14 admits only plain text
        raise ProfileDigestError(
            f"{where}: value text {raw!r} differs from the parsed value "
            f"{value_node.value!r}; text and structure must be the same object "
            "(P-7 iii)"
        )
    return DigestSlot(
        doc_index=index,
        key=key,
        value_start=value_start,
        value_end=value_end,
        line_number=key_node.start_mark.line + 1,
        line_prefix=text[line_start:value_start],
        line_trail=trail,
        raw_value=raw,
    )


def locate_digest_slots(text: str, nodes: list[yaml.Node]) -> list[DigestSlot]:
    """Locate both digest fields structurally, enforcing P-7 (i)-(iii) and P-14."""
    slots: list[DigestSlot] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, yaml.MappingNode):
            continue
        for key_node, value_node in node.value:
            if not isinstance(key_node, yaml.ScalarNode):
                continue
            if key_node.value != IDENTITY_KEY:
                continue
            if not isinstance(value_node, yaml.MappingNode):
                continue
            for id_key, id_value in value_node.value:
                if isinstance(id_key, yaml.ScalarNode) and id_key.value in DIGEST_KEYS:
                    slots.append(_build_slot(text, index, id_key, id_value))
    return slots


def _apply_blanking(text: str, slots: list[DigestSlot]) -> str:
    out: list[str] = []
    cursor = 0
    for slot in sorted(slots, key=lambda s: s.value_start):
        if slot.value_start < cursor:  # pragma: no cover - P-7 (i) prevents it
            raise ProfileDigestError("overlapping digest spans — refusing (P-7)")
        out.append(text[cursor : slot.value_start])
        out.append(PLACEHOLDER)
        cursor = slot.value_end
    out.append(text[cursor:])
    return "".join(out)


def blank_digest_values(
    text: str, *, source: str = "<text>"
) -> tuple[str, list[DigestSlot]]:
    """Structurally replace both digest values with ``TBD`` (P-7, P-14)."""
    nodes = compose_documents(text, source=source)
    slots = locate_digest_slots(text, nodes)
    return _apply_blanking(text, slots), slots


def recorded_digest_fields(document: Any) -> dict[str, Any]:
    """The digest fields structurally present in ``profile_identity``."""
    if not isinstance(document, dict):
        return {}
    identity = document.get(IDENTITY_KEY)
    if not isinstance(identity, dict):
        return {}
    return {key: identity[key] for key in DIGEST_KEYS if key in identity}


# ============================================================================
# Public results
# ============================================================================


@dataclass(frozen=True)
class DocumentDigests:
    """Computed digests plus the identity labels for one document."""

    index: int
    identity: dict[str, Any]
    canonical_semantic_digest: str
    byte_digest: str
    recorded_canonicalization_version: Any
    recorded_canonical_semantic_digest: Any
    recorded_byte_digest: Any
    slots: tuple[DigestSlot, ...]

    def label(self) -> str:
        parts = [
            f"{key}={self.identity[key]!r}"
            for key in _IDENTITY_LABEL_KEYS
            if key in self.identity
        ]
        return ", ".join(parts) if parts else "<no identity labels>"

    def replacement_lines(self) -> list[str]:
        """Exact physical lines to record, in file order (review F7)."""
        digests = {
            "canonical_semantic_digest": self.canonical_semantic_digest,
            "byte_digest": self.byte_digest,
        }
        return [
            f"line {slot.line_number}: {slot.replacement_line(digests[slot.key])}"
            for slot in sorted(self.slots, key=lambda s: s.line_number)
        ]


_MISSING = object()


def compute_digests(
    path: Path, *, allow_any_doc_count: bool = False
) -> list[DocumentDigests]:
    """Compute both digests for every document in ``path`` (fail-closed)."""
    source = str(path)
    text = read_text(path)
    nodes = compose_documents(text, source=source)
    documents = load_documents(text, source=source)

    if not documents:
        raise ProfileDigestError(f"{path}: contains no YAML document")
    if len(documents) != len(nodes):  # pragma: no cover - same parser, same bytes
        raise ProfileDigestError(f"{path}: parse disagreement — refusing")
    if len(documents) != 2 and not allow_any_doc_count:
        raise ProfileDigestError(
            f"{path}: expected exactly 2 YAML documents, found {len(documents)}; "
            "pass --allow-any-doc-count to override (P-10)"
        )

    scan_nodes(nodes)
    slots = locate_digest_slots(text, nodes)

    expected = sum(len(recorded_digest_fields(doc)) for doc in documents)
    if len(slots) != expected:  # pragma: no cover - one parse feeds both views
        raise ProfileDigestError(
            f"{path}: located {len(slots)} digest span(s) but {expected} field(s) "
            "are structurally present — refusing (P-11)"
        )

    file_byte_digest = format_digest(
        BYTE_KIND, _sha256_hex(_apply_blanking(text, slots), what=f"{path} bytes")
    )

    results: list[DocumentDigests] = []
    for index, document in enumerate(documents):
        semantic = semantic_digest(document, index=index)
        identity = document[IDENTITY_KEY]
        results.append(
            DocumentDigests(
                index=index,
                identity={
                    key: identity[key]
                    for key in _IDENTITY_LABEL_KEYS
                    if key in identity
                },
                canonical_semantic_digest=semantic,
                byte_digest=file_byte_digest,
                recorded_canonicalization_version=identity.get(
                    "canonicalization_version", _MISSING
                ),
                recorded_canonical_semantic_digest=identity.get(
                    "canonical_semantic_digest", _MISSING
                ),
                recorded_byte_digest=identity.get("byte_digest", _MISSING),
                slots=tuple(slot for slot in slots if slot.doc_index == index),
            )
        )
    return results


def _describe_recorded(value: Any) -> str:
    if value is _MISSING:
        return "<field absent>"
    if value is None:  # pragma: no cover - P-14 refuses a `null` digest earlier
        return "null (explicitly absent)"
    if value == PLACEHOLDER:
        return f"{PLACEHOLDER} (placeholder — a value is OWED, template :46-51)"
    return repr(value)


def verify_digests(path: Path, *, allow_any_doc_count: bool = False) -> list[str]:
    """Return a list of mismatch descriptions; empty means verified."""
    problems: list[str] = []
    for result in compute_digests(path, allow_any_doc_count=allow_any_doc_count):
        prefix = f"document {result.index} [{result.label()}]"
        checks = (
            (
                "canonicalization_version",
                result.recorded_canonicalization_version,
                ALGORITHM_ID,
            ),
            (
                "canonical_semantic_digest",
                result.recorded_canonical_semantic_digest,
                result.canonical_semantic_digest,
            ),
            ("byte_digest", result.recorded_byte_digest, result.byte_digest),
        )
        failed: set[str] = set()
        for field, recorded, expected in checks:
            if recorded != expected:
                failed.add(field)
                problems.append(
                    f"{prefix} {field}: recorded {_describe_recorded(recorded)}, "
                    f"expected {expected!r}"
                )
        if failed == {"byte_digest"}:
            problems.append(
                f"{prefix} diagnostic: the semantic digest matches, so the CONTENT "
                "is intact and the difference is bytes only — most often the "
                "whitespace between a digest value and its trailing comment, or a "
                "line ending. Record the exact lines `compute` prints (P-7)."
            )
    return problems


# ============================================================================
# CLI
# ============================================================================


def _cmd_compute(args: argparse.Namespace) -> int:
    results = compute_digests(args.path, allow_any_doc_count=args.allow_any_doc_count)
    print(_NON_PRODUCTION_BANNER)
    print(environment_line())
    print(f"file: {args.path} ({len(results)} document(s))")
    for result in results:
        print()
        print(f"document {result.index}")
        for key in _IDENTITY_LABEL_KEYS:
            if key in result.identity:
                print(f"  {key + ':':<28}{result.identity[key]}")
        print(f"  {'canonicalization_version:':<28}{ALGORITHM_ID}")
        print(f"  {'canonical_semantic_digest:':<28}{result.canonical_semantic_digest}")
        print(f"  {'byte_digest:':<28}{result.byte_digest}")
        lines = result.replacement_lines()
        if lines:
            print("  record these physical lines VERBATIM (padding included):")
            for line in lines:
                print(f"    {line}")
    print()
    print(
        "These values are computed from the file AS IT STANDS. Record them only at "
        "approval time, after the content — approvers[] included — is frozen (P-5)."
    )
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    problems = verify_digests(args.path, allow_any_doc_count=args.allow_any_doc_count)
    print(_NON_PRODUCTION_BANNER)
    print(environment_line())
    if problems:
        print(f"bcp-digest verify: FAIL — {len(problems)} finding(s) in {args.path}")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"bcp-digest verify: PASS — {args.path} matches {ALGORITHM_ID}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bcp_digest",
        description=(
            f"Broker Capability Profile digests under the PROVISIONAL, "
            f"NON-PRODUCTION canonicalizer {ALGORITHM_ID} (operator decision D5, "
            "2026-07-29). Production canonicalization is the open G2 item."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text, handler in (
        ("compute", "compute both digests for every document", _cmd_compute),
        ("verify", "recompute and compare against the recorded fields", _cmd_verify),
    ):
        child = sub.add_parser(name, help=help_text)
        child.add_argument("path", type=Path, help="path to the profile YAML file")
        child.add_argument(
            "--allow-any-doc-count",
            action="store_true",
            help="permit a document count other than 2 (P-10)",
        )
        child.set_defaults(handler=handler)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except ProfileDigestError as exc:
        print(f"bcp-digest: REFUSED — {exc}", file=sys.stderr)
        return 1
    except RecursionError:  # pragma: no cover - P-16/P-17 refuse first
        print("bcp-digest: REFUSED — input too deeply nested", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
