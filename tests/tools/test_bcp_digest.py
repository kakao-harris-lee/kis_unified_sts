"""Unit tests for the provisional BCP canonicalizer (``tools/bcp_digest.py``).

The tool implements ``ev-l1-provisional-0`` — the PROVISIONAL, non-production
canonicalizer adopted under operator decision D5 (2026-07-29). These tests pin
the properties the corpus actually requires of the two digest fields, so that a
future production canonicalizer (G2) cannot silently inherit a weaker one:

  * SPG-EV-003 (VER-002-001:1556) — "Canonical semantic digests agree only for
    identical meaning": invariance under comments / whitespace / key order,
    sensitivity to any value change, duplicate and aliased content fails closed.
  * IOC-EV-007 (VER-002-001:2112) — "byte and semantic digests cannot be used
    interchangeably": the two digests carry distinct KIND segments and react
    differently to a comment-only edit.
  * IOC-INV-002 (ADR-002-020:161) — determinism, or construction fails.
  * The tool's own P-5 / P-7 fixed points: recording a computed digest must
    change neither digest, while ANY other byte on a digest line must change the
    byte digest, and the approver set must be bound by both.

FROZEN GOLDEN VECTORS
    ``test_golden_vector_*`` hold two literal fixtures and their digests as
    hardcoded hex. They are the only tests that can detect canonicalizer DRIFT
    (separators, sort order, exclusion list, NFC→NFKC, JSON escaping): every
    other digest assertion is relative and would stay green while the algorithm
    silently changed under a fixed algorithm id. **If a golden literal or its
    expected hex has to change, ``ALGORITHM_ID`` must be bumped in the same
    commit** — every digest already recorded under the old id would otherwise
    become unreproducible.

The module under test lives at ``tools/bcp_digest.py`` (outside the package
tree); it is loaded directly from its file path, mirroring
``tests/tools/test_tos_firewall_check.py``.
"""

from __future__ import annotations

import importlib.util
import sys
import unicodedata
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "bcp_digest.py"


def _load_bcp_digest():
    spec = importlib.util.spec_from_file_location("bcp_digest", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: ``@dataclass`` resolves ``from __future__ import
    # annotations`` string annotations through ``sys.modules[cls.__module__]``.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bcp = _load_bcp_digest()


# --------------------------------------------------------------------------
# fixtures / helpers
# --------------------------------------------------------------------------

_HEADER = """\
# =============================================================================
# fixture profile — two documents, one per environment
# =============================================================================
"""

_BODY = """\
live_scope:
  conformance_class: CLASS_D_NON_LIVE
  accounts: []
  maximum_concurrency: 0
  maximum_quantity: null
capabilities:
  order_identity:
    status: UNKNOWN
    assurance_level: LEVEL_0_UNKNOWN
    restriction_approved: false
"""


def _document(
    artifact_id: str,
    *,
    environment: str = "MOCK_VTS",
    account_type: str = "모의투자_위탁",
    canonicalization_version: str = "TBD",
    semantic_token: str = "TBD",
    byte_token: str = "TBD",
    digest_comment: str = "",
    approvers: str = "[]",
    status: str = "DRAFT",
    body: str = _BODY,
    lead_comment: str = "",
) -> str:
    """One YAML document in template key order (template :76-97)."""
    return (
        f"{lead_comment}"
        "profile_identity:\n"
        f"  artifact_id: {artifact_id}\n"
        "  schema_version: BROKER-CAPABILITY-PROFILE-template@part-1-foundation\n"
        f"  canonicalization_version: {canonicalization_version}\n"
        f"  canonical_semantic_digest: {semantic_token}{digest_comment}\n"
        f"  byte_digest: {byte_token}{digest_comment}\n"
        "  broker_id: BROKER_X\n"
        f"  environment: {environment}\n"
        f"  account_type: {account_type}\n"
        "  profile_version: 0.1.0-draft\n"
        f"  status: {status}\n"
        f"  approvers: {approvers}\n"
        f"{body}"
    )


def _profile(*documents: str, header: str = _HEADER) -> str:
    return header + "".join(f"---\n{doc}" for doc in documents)


def _default_profile(**kwargs: str) -> str:
    """A conventional two-document profile, one document per environment."""
    doc_a = _document("FIXTURE-A", environment="MOCK_VTS", **kwargs)
    doc_b = _document("FIXTURE-B", environment="REAL_PROD", **kwargs)
    return _profile(doc_a, doc_b)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def _record_digests(path: Path) -> Path:
    """Record the computed digests exactly where ``compute`` says they go."""
    text = path.read_text(encoding="utf-8")
    values: dict[object, str] = {}
    for result in bcp.compute_digests(path):
        for slot in result.slots:
            values[slot] = (
                result.canonical_semantic_digest
                if slot.key == "canonical_semantic_digest"
                else result.byte_digest
            )
    for slot in sorted(values, key=lambda s: s.value_start, reverse=True):
        text = text[: slot.value_start] + values[slot] + text[slot.value_end :]
    return _write(path, text)


def _approved_profile(
    tmp_path: Path, name: str = "approved.yaml", **kwargs: str
) -> Path:
    """A profile filled the way an approver would: freeze, compute, record."""
    kwargs.setdefault("canonicalization_version", bcp.ALGORITHM_ID)
    kwargs.setdefault("approvers", "[ai-review-2026-07-30, operator-countersign]")
    path = _write(tmp_path / name, _default_profile(**kwargs))
    return _record_digests(path)


def _digests(path: Path) -> list[tuple[str, str]]:
    return [
        (r.canonical_semantic_digest, r.byte_digest) for r in bcp.compute_digests(path)
    ]


def _hex(digest: str) -> str:
    return digest.rsplit(":", 1)[1]


# ==========================================================================
# F3 — FROZEN GOLDEN VECTORS
# Changing any literal below requires bumping ALGORITHM_ID in the same commit.
# ==========================================================================

_GOLDEN_ASCII = """\
# golden vector A — frozen; read the module docstring before touching this
---
profile_identity:
  artifact_id: GOLDEN-A0
  canonicalization_version: ev-l1-provisional-0
  canonical_semantic_digest: TBD
  byte_digest: TBD
  environment: MOCK
  status: DRAFT
  approvers: []
live_scope:
  maximum_concurrency: 0
  maximum_quantity: null
  flags:
    - alpha
    - beta
---
profile_identity:
  artifact_id: GOLDEN-A1
  canonicalization_version: ev-l1-provisional-0
  canonical_semantic_digest: TBD
  byte_digest: TBD
  environment: REAL
  status: DRAFT
  approvers: []
live_scope:
  maximum_concurrency: 0
  maximum_quantity: null
  flags: []
"""

_GOLDEN_ASCII_SEMANTIC_0 = (
    "72eb2397d0a5d79701ddb4cc3775fa848e1e4941169d0876215fa6dbe3c1377a"
)
_GOLDEN_ASCII_SEMANTIC_1 = (
    "9a0bd3ab5aceabd0383a2b50321b968ce64496324f86181f2d7a3ba2d3e1a709"
)
_GOLDEN_ASCII_BYTE = "7eaaf5a64ba02cd600f2adc92c422092ee460a6f79abceca110e2d71bc30c3bb"

#: Vector B pins ``ensure_ascii=False`` + NFC + UTF-8 together: the Korean text
#: is serialized literally (never as \\uXXXX escapes) and hashed as UTF-8 bytes.
_GOLDEN_NON_ASCII = """\
---
profile_identity:
  artifact_id: GOLDEN-B0
  canonicalization_version: ev-l1-provisional-0
  canonical_semantic_digest: TBD
  byte_digest: TBD
  environment: MOCK_VTS
  account_type: 모의투자_위탁
  status: DRAFT
  approvers: []
  _kis:
    비고: 값
    ratio: 1.5
    truthy: true
    nothing: null
    # NFC-vs-NFKC discriminator: Hangul is NFKC-invariant, so without a
    # compatibility character an NFC->NFKC swap would leave every digest
    # unchanged. U+FF21 folds to 'A' and U+2460 to '1' under NFKC only.
    nfkc_discriminator: Ａ①
---
profile_identity:
  artifact_id: GOLDEN-B1
  canonicalization_version: ev-l1-provisional-0
  canonical_semantic_digest: TBD
  byte_digest: TBD
  environment: REAL_PROD
  account_type: 실전_위탁
  status: APPROVED
  approvers:
    - ai-review-2026-07-30
    - operator-countersign
"""

_GOLDEN_NON_ASCII_SEMANTIC_0 = (
    "b8951f5882a40269e98293c3e5150a3f115ac125ca2f73c8028f0d173e2d3b63"
)
_GOLDEN_NON_ASCII_SEMANTIC_1 = (
    "ea21ccd6f026591b2448bdd6181d3ea7c6ecff3b6cd6d85c99d617454dacba6d"
)
_GOLDEN_NON_ASCII_BYTE = (
    "d38e843a25c67debb5773602a1dbf3ba67bc827cb0a32348516e932b1a34bb7b"
)


def test_golden_vector_ascii(tmp_path: Path) -> None:
    """FROZEN. A change here means the canonicalizer changed — bump the id."""
    (sem0, byte0), (sem1, byte1) = _digests(_write(tmp_path / "a.yaml", _GOLDEN_ASCII))

    assert _hex(sem0) == _GOLDEN_ASCII_SEMANTIC_0
    assert _hex(sem1) == _GOLDEN_ASCII_SEMANTIC_1
    assert _hex(byte0) == _GOLDEN_ASCII_BYTE
    assert byte0 == byte1


def test_golden_vector_non_ascii(tmp_path: Path) -> None:
    """FROZEN. Pins ensure_ascii=False + NFC + UTF-8 on 모의투자_위탁."""
    (sem0, byte0), (sem1, byte1) = _digests(
        _write(tmp_path / "b.yaml", _GOLDEN_NON_ASCII)
    )

    assert _hex(sem0) == _GOLDEN_NON_ASCII_SEMANTIC_0
    assert _hex(sem1) == _GOLDEN_NON_ASCII_SEMANTIC_1
    assert _hex(byte0) == _GOLDEN_NON_ASCII_BYTE
    assert byte0 == byte1


def test_golden_canonical_json_is_literal_utf8() -> None:
    """The canonical form carries Korean literally, never \\uXXXX escapes."""
    payload = bcp.canonical_json({"account_type": "모의투자_위탁", "n": 1})
    assert payload == '{"account_type":"모의투자_위탁","n":1}'
    assert "\\u" not in payload


def test_normalization_is_nfc_and_not_nfkc() -> None:
    """P-4 is NFC. NFKC would fold compatibility variants and lose meaning.

    Hangul is NFKC-invariant, so the Korean fixtures alone cannot tell the two
    normal forms apart — golden vector B carries U+FF21/U+2460 for that, and
    this is the direct canary.
    """
    assert unicodedata.normalize("NFKC", "Ａ") == "A"
    assert unicodedata.normalize("NFC", "Ａ") == "Ａ"

    assert bcp.canonical_json({"k": "Ａ"}) != bcp.canonical_json({"k": "A"})
    assert bcp.canonical_json({"k": "①"}) != bcp.canonical_json({"k": "1"})
    assert bcp.canonical_json({"Ａ": 1}) != bcp.canonical_json({"A": 1})


def test_golden_vector_survives_recording_its_own_digests(tmp_path: Path) -> None:
    """The frozen values are also what a filled file verifies against."""
    path = _write(tmp_path / "b.yaml", _GOLDEN_NON_ASCII)
    _record_digests(path)

    (sem0, byte0), (sem1, _) = _digests(path)
    assert _hex(sem0) == _GOLDEN_NON_ASCII_SEMANTIC_0
    assert _hex(sem1) == _GOLDEN_NON_ASCII_SEMANTIC_1
    assert _hex(byte0) == _GOLDEN_NON_ASCII_BYTE
    assert bcp.verify_digests(path) == []


def test_cli_output_matches_the_golden_vector(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI is checked against frozen values, not against the tool itself."""
    path = _write(tmp_path / "b.yaml", _GOLDEN_NON_ASCII)
    assert bcp.main(["compute", str(path)]) == 0

    out = capsys.readouterr().out
    assert _GOLDEN_NON_ASCII_SEMANTIC_0 in out
    assert _GOLDEN_NON_ASCII_SEMANTIC_1 in out
    assert _GOLDEN_NON_ASCII_BYTE in out


# --------------------------------------------------------------------------
# determinism and digest shape
# --------------------------------------------------------------------------


def test_compute_is_deterministic(tmp_path: Path) -> None:
    path = _write(tmp_path / "p.yaml", _default_profile())
    assert _digests(path) == _digests(path)


def test_digest_string_is_self_identifying_and_kind_tagged(tmp_path: Path) -> None:
    """P-1: algorithm id + KIND, so the two digests can never be interchanged."""
    path = _write(tmp_path / "p.yaml", _default_profile())
    result = bcp.compute_digests(path)[0]

    assert result.canonical_semantic_digest.startswith(
        f"{bcp.ALGORITHM_ID}:{bcp.SEMANTIC_KIND}:sha256:"
    )
    assert result.byte_digest.startswith(f"{bcp.ALGORITHM_ID}:{bcp.BYTE_KIND}:sha256:")
    assert result.canonical_semantic_digest != result.byte_digest
    for value in (result.canonical_semantic_digest, result.byte_digest):
        hex_part = _hex(value)
        assert len(hex_part) == 64
        assert hex_part == hex_part.lower()
        int(hex_part, 16)


def test_two_documents_share_a_byte_digest_but_not_a_semantic_one(
    tmp_path: Path,
) -> None:
    """P-6: byte scope is the whole file; semantic scope is the document."""
    path = _write(tmp_path / "p.yaml", _default_profile())
    first, second = bcp.compute_digests(path)

    assert first.byte_digest == second.byte_digest
    assert first.canonical_semantic_digest != second.canonical_semantic_digest


def test_semantic_digest_helper_is_the_live_implementation(tmp_path: Path) -> None:
    """F10: one implementation, and the named function is it."""
    path = _write(tmp_path / "p.yaml", _default_profile())
    documents = bcp.load_documents(path.read_text(encoding="utf-8"))

    for index, result in enumerate(bcp.compute_digests(path)):
        assert result.canonical_semantic_digest == bcp.semantic_digest(
            documents[index], index=index
        )


# --------------------------------------------------------------------------
# SPG-EV-003 — semantic invariance and sensitivity
# --------------------------------------------------------------------------


def test_semantic_digest_ignores_comments(tmp_path: Path) -> None:
    plain = _write(tmp_path / "plain.yaml", _default_profile())
    commented = _write(
        tmp_path / "commented.yaml",
        _default_profile(lead_comment="# a comment that carries no meaning\n"),
    )
    assert _digests(plain)[0][0] == _digests(commented)[0][0]


def test_semantic_digest_ignores_whitespace_and_quoting(tmp_path: Path) -> None:
    base = _default_profile()
    varied = base.replace("  broker_id: BROKER_X\n", '  broker_id:    "BROKER_X"   \n')
    assert varied != base
    plain = _write(tmp_path / "plain.yaml", base)
    other = _write(tmp_path / "varied.yaml", varied)
    assert _digests(plain)[0][0] == _digests(other)[0][0]


def test_semantic_digest_ignores_key_order(tmp_path: Path) -> None:
    base = _default_profile()
    reordered = base.replace(
        "  broker_id: BROKER_X\n  environment: MOCK_VTS\n",
        "  environment: MOCK_VTS\n  broker_id: BROKER_X\n",
    )
    assert reordered != base
    plain = _write(tmp_path / "plain.yaml", base)
    other = _write(tmp_path / "reordered.yaml", reordered)
    assert _digests(plain)[0][0] == _digests(other)[0][0]


def test_semantic_digest_is_sensitive_to_a_value_change(tmp_path: Path) -> None:
    base = _default_profile()
    changed = base.replace("  maximum_concurrency: 0\n", "  maximum_concurrency: 1\n")
    assert changed != base
    plain = _write(tmp_path / "plain.yaml", base)
    other = _write(tmp_path / "changed.yaml", changed)
    assert _digests(plain)[0][0] != _digests(other)[0][0]


def test_semantic_digest_distinguishes_null_from_the_string_null(
    tmp_path: Path,
) -> None:
    base = _default_profile()
    quoted = base.replace("  maximum_quantity: null\n", '  maximum_quantity: "null"\n')
    plain = _write(tmp_path / "plain.yaml", base)
    other = _write(tmp_path / "quoted.yaml", quoted)
    assert _digests(plain)[0][0] != _digests(other)[0][0]


def test_semantic_digest_distinguishes_bool_from_the_string(tmp_path: Path) -> None:
    base = _default_profile()
    quoted = base.replace(
        "    restriction_approved: false\n", '    restriction_approved: "false"\n'
    )
    plain = _write(tmp_path / "plain.yaml", base)
    other = _write(tmp_path / "quoted.yaml", quoted)
    assert _digests(plain)[0][0] != _digests(other)[0][0]


def test_byte_digest_sees_the_comment_the_semantic_digest_ignores(
    tmp_path: Path,
) -> None:
    """IOC-EV-007: the two digests are not interchangeable."""
    plain = _write(tmp_path / "plain.yaml", _default_profile())
    commented = _write(
        tmp_path / "commented.yaml",
        _default_profile(lead_comment="# comment-only edit\n"),
    )
    sem_a, byte_a = _digests(plain)[0]
    sem_b, byte_b = _digests(commented)[0]

    assert sem_a == sem_b
    assert byte_a != byte_b


# --------------------------------------------------------------------------
# F1 — the byte digest must see EVERY non-digest byte on a digest line
# --------------------------------------------------------------------------


def test_byte_digest_sees_a_comment_change_on_a_digest_line(tmp_path: Path) -> None:
    """Mandatory canary: attempt-1's regex deleted this content from the input."""
    a = _write(tmp_path / "a.yaml", _default_profile(digest_comment="  # note one"))
    b = _write(tmp_path / "b.yaml", _default_profile(digest_comment="  # note two"))
    assert _digests(a)[0][0] == _digests(b)[0][0]  # semantics unchanged
    assert _digests(a)[0][1] != _digests(b)[0][1]  # bytes changed


def test_byte_digest_sees_padding_before_a_trailing_comment(tmp_path: Path) -> None:
    """P-7: the padding between value and comment is inside the byte scope."""
    a = _write(tmp_path / "a.yaml", _default_profile(digest_comment="  # note"))
    b = _write(tmp_path / "b.yaml", _default_profile(digest_comment="      # note"))
    assert _digests(a)[0][1] != _digests(b)[0][1]


def test_digest_key_nested_under_another_key_is_refused(tmp_path: Path) -> None:
    """F1 ADV-1: flow style must never reach the blanking step."""
    text = _default_profile().replace(
        "  canonical_semantic_digest: TBD\n  byte_digest: TBD\n",
        "  digests: {canonical_semantic_digest: TBD, byte_digest: TBD}\n",
        1,
    )
    path = _write(tmp_path / "flow.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="outside 'profile_identity'"):
        bcp.compute_digests(path)


def test_flow_style_identity_block_is_refused(tmp_path: Path) -> None:
    """F1 ADV-2 reproduction: the approver-swap path must be unreachable."""
    doc = (
        "profile_identity: {artifact_id: X, canonicalization_version: TBD, "
        "canonical_semantic_digest: TBD, byte_digest: TBD, approvers: [alice]}\n"
        "live_scope: {}\n"
    )
    path = _write(tmp_path / "flow.yaml", _profile(doc, doc))
    with pytest.raises(bcp.ProfileDigestError, match="sole key on its line"):
        bcp.compute_digests(path)


def test_trailing_content_guard_fires_on_its_own(tmp_path: Path) -> None:
    """P-7 (i), trailing half ISOLATED: the key starts its line, but a
    co-resident field follows the value — exactly the shape that let attempt-1
    delete `secret` from the byte-digest input."""
    doc = (
        "profile_identity: {\n"
        "  artifact_id: X,\n"
        "  canonical_semantic_digest: TBD, secret: 1,\n"
        "  byte_digest: TBD,\n"
        "  approvers: []}\n"
        "live_scope: {}\n"
    )
    path = _write(tmp_path / "trailing.yaml", _profile(doc, doc))
    with pytest.raises(
        bcp.ProfileDigestError, match="content follows the value on its physical line"
    ):
        bcp.compute_digests(path)


def test_preceding_content_guard_fires_on_its_own(tmp_path: Path) -> None:
    """P-7 (i), preceding half ISOLATED: the key sits mid-line, yet nothing
    follows its value (the separator is carried to the next line)."""
    doc = (
        "profile_identity: {artifact_id: X, canonical_semantic_digest: TBD\n"
        "  , byte_digest: TBD\n"
        "  , approvers: []}\n"
        "live_scope: {}\n"
    )
    path = _write(tmp_path / "preceding.yaml", _profile(doc, doc))
    with pytest.raises(
        bcp.ProfileDigestError, match="content precedes the key on its physical line"
    ):
        bcp.compute_digests(path)


def test_digest_value_on_a_following_line_is_refused(tmp_path: Path) -> None:
    text = _default_profile().replace(
        "  canonical_semantic_digest: TBD\n", "  canonical_semantic_digest:\n    TBD\n"
    )
    path = _write(tmp_path / "wrapped.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="one physical line"):
        bcp.compute_digests(path)


def test_block_scalar_digest_value_is_refused(tmp_path: Path) -> None:
    text = _default_profile().replace(
        "  byte_digest: TBD\n", "  byte_digest: >-\n    TBD\n"
    )
    path = _write(tmp_path / "block.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="P-7"):
        bcp.compute_digests(path)


def test_sequence_digest_value_is_refused(tmp_path: Path) -> None:
    text = _default_profile().replace("  byte_digest: TBD\n", "  byte_digest: [TBD]\n")
    path = _write(tmp_path / "seq.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="not a scalar"):
        bcp.compute_digests(path)


def test_blanking_replaces_only_the_value_span(tmp_path: Path) -> None:
    """The replaced span is the parsed value node; the line survives intact."""
    path = _write(
        tmp_path / "p.yaml",
        _default_profile(
            canonicalization_version=bcp.ALGORITHM_ID, digest_comment="   # keep me"
        ),
    )
    _record_digests(path)

    blanked, slots = bcp.blank_digest_values(path.read_text(encoding="utf-8"))
    assert len(slots) == 4
    assert blanked.count("canonical_semantic_digest: TBD   # keep me") == 2
    assert blanked.count("byte_digest: TBD   # keep me") == 2
    assert f":{bcp.SEMANTIC_KIND}:" not in blanked
    assert f":{bcp.BYTE_KIND}:" not in blanked


# --------------------------------------------------------------------------
# F5 — line endings live inside the byte scope
# --------------------------------------------------------------------------


def test_crlf_on_a_digest_line_is_preserved_in_the_byte_digest(
    tmp_path: Path,
) -> None:
    base = _default_profile()
    crlf = base.replace("  byte_digest: TBD\n", "  byte_digest: TBD\r\n")
    assert crlf != base
    a = _write(tmp_path / "lf.yaml", base)
    b = _write(tmp_path / "crlf.yaml", crlf)

    assert _digests(a)[0][0] == _digests(b)[0][0]
    assert _digests(a)[0][1] != _digests(b)[0][1]


def test_a_fully_crlf_file_still_computes(tmp_path: Path) -> None:
    path = _write(tmp_path / "crlf.yaml", _default_profile().replace("\n", "\r\n"))
    assert len(bcp.compute_digests(path)) == 2


# --------------------------------------------------------------------------
# F4 / F13 / P-16 / P-17 — parse-level fail-closed guards
# --------------------------------------------------------------------------


def test_omap_is_refused(tmp_path: Path) -> None:
    """F4: !!omap yields tuples, which must not collide with a list of pairs."""
    text = _default_profile().replace(
        "  accounts: []\n", "  accounts: !!omap\n    - a: 1\n    - b: 2\n"
    )
    path = _write(tmp_path / "omap.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="outside the canonical"):
        bcp.compute_digests(path)


def test_pairs_is_refused(tmp_path: Path) -> None:
    text = _default_profile().replace(
        "  accounts: []\n", "  accounts: !!pairs\n    - a: 1\n    - a: 2\n"
    )
    path = _write(tmp_path / "pairs.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="outside the canonical"):
        bcp.compute_digests(path)


def test_merge_key_is_refused(tmp_path: Path) -> None:
    """F13: the refusal is deliberate, not a side effect of skipping flatten."""
    text = _default_profile().replace(
        "capabilities:\n", "defaults:\n  x: 1\ncapabilities:\n  <<: {y: 2}\n", 1
    )
    path = _write(tmp_path / "merge.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="merge key"):
        bcp.compute_digests(path)


def test_alias_is_refused(tmp_path: Path) -> None:
    """P-16: an alias makes one value reachable at two paths."""
    text = _default_profile().replace(
        "  accounts: []\n", "  accounts: &acc []\n  venues: *acc\n", 1
    )
    path = _write(tmp_path / "alias.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="anchor/alias"):
        bcp.compute_digests(path)


def test_recursive_anchor_is_refused(tmp_path: Path) -> None:
    """F8: `&x [*x]` must produce a REFUSED line, not a RecursionError."""
    text = _default_profile().replace("  accounts: []\n", "  accounts: &x [*x]\n", 1)
    path = _write(tmp_path / "recursive.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="anchor/alias"):
        bcp.compute_digests(path)
    assert bcp.main(["compute", str(path)]) == 1


def test_deeply_nested_input_is_refused(tmp_path: Path) -> None:
    """P-17: bounded work; a refusal, never a RecursionError."""
    deep = "".join(f"{'  ' * i}k{i}:\n" for i in range(1, bcp.MAX_NESTING_DEPTH + 10))
    text = _default_profile().replace("  accounts: []\n", "  accounts:\n" + deep, 1)
    path = _write(tmp_path / "deep.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="nesting deeper"):
        bcp.compute_digests(path)
    assert bcp.main(["compute", str(path)]) == 1


def test_lone_surrogate_is_refused(tmp_path: Path) -> None:
    """F8: an unencodable string is a refusal, not a UnicodeEncodeError."""
    text = _default_profile().replace(
        "  broker_id: BROKER_X\n", '  broker_id: "\\ud800"\n', 1
    )
    path = _write(tmp_path / "surrogate.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="not UTF-8 encodable"):
        bcp.compute_digests(path)
    assert bcp.main(["compute", str(path)]) == 1


# --------------------------------------------------------------------------
# F6 / P-14 — recorded digest-value grammar
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "aaa#bbb",
        "null",
        '"TBD"',
        "tbd",
        "TBD extra",
        "ev-l1-provisional-0:semantic:sha256:tooshort",
        "ev-l1-provisional-0:other:sha256:" + "a" * 64,
        "ev-l1-provisional-0:semantic:sha256:" + "A" * 64,
        "ev-l1-provisional-1:semantic:sha256:" + "a" * 64,
        "sha256:" + "a" * 64,
    ],
)
def test_malformed_recorded_digest_value_is_refused(tmp_path: Path, value: str) -> None:
    text = _default_profile().replace(
        "  byte_digest: TBD\n", f"  byte_digest: {value}\n"
    )
    path = _write(tmp_path / "grammar.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="P-14"):
        bcp.compute_digests(path)


def test_empty_recorded_digest_value_is_refused(tmp_path: Path) -> None:
    text = _default_profile().replace("  byte_digest: TBD\n", "  byte_digest:\n")
    path = _write(tmp_path / "empty.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="P-14"):
        bcp.compute_digests(path)


def test_a_digest_of_the_wrong_kind_parses_but_verify_rejects_it(
    tmp_path: Path,
) -> None:
    """IOC-EV-007: the KIND swap is caught, and caught as a digest mismatch."""
    path = _approved_profile(tmp_path)
    result = bcp.compute_digests(path)[0]
    text = path.read_text(encoding="utf-8")
    _write(
        path,
        text.replace(
            f"  byte_digest: {result.byte_digest}\n",
            f"  byte_digest: {result.canonical_semantic_digest}\n",
        ),
    )
    assert any("byte_digest" in p for p in bcp.verify_digests(path))


# --------------------------------------------------------------------------
# F9 / F11 / P-15 — parser identity and the YAML 1.1 hazard lint
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # (raw plain scalar, the type THIS parser resolves it to)
        # Divergence direction is noted per row; both directions are refused.
        ("yes", bool),  # YAML 1.2 core: str
        ("no", bool),  # YAML 1.2 core: str
        ("On", bool),  # YAML 1.2 core: str
        ("OFF", bool),  # YAML 1.2 core: str
        ("12:30", int),  # YAML 1.2 core: str
        ("010", int),  # YAML 1.2 core: int 10 or str, never 8
        ("0755", int),  # YAML 1.2 core: int 755 or str, never 493
        ("0b101", int),  # YAML 1.2 core: str (no binary form)
        ("1_000", int),  # YAML 1.2 core: str (no digit separator)
        ("0o17", str),  # OPPOSITE: YAML 1.2 core reads int 15, this parser str
        ("0O17", str),  # same, uppercase spelling
    ],
)
def test_hazard_premise_is_measured(raw: str, expected: type) -> None:
    """Each lint entry is pinned by the type THIS parser actually produces.

    ``type(...) is`` rather than ``isinstance``: bool is a subclass of int, and
    the ``0o17`` row diverges in the opposite direction from every other row —
    two premises the attempt-2 review caught precisely because they are measured
    here rather than assumed from a spec.
    """
    assert type(yaml.safe_load(f"k: {raw}\n")["k"]) is expected


@pytest.mark.parametrize("raw", ["y", "Y", "n", "N", "09:00", "09", "08"])
def test_non_hazard_premise_is_measured(raw: str) -> None:
    """Recorded residual (P-15): this parser agrees with YAML 1.2 on these, so
    refusing them would be an over-refusal. `09` is the case that caught an
    over-broad octal pattern during attempt-2."""
    assert isinstance(yaml.safe_load(f"k: {raw}\n")["k"], str)


@pytest.mark.parametrize(
    "raw",
    ["yes", "no", "On", "12:30", "010", "0755", "0b101", "0o17", "0O17", "1_000"],
)
def test_yaml_11_hazard_is_refused(tmp_path: Path, raw: str) -> None:
    text = _default_profile().replace(
        "  broker_id: BROKER_X\n", f"  broker_id: {raw}\n", 1
    )
    path = _write(tmp_path / "hazard.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="P-15"):
        bcp.compute_digests(path)


@pytest.mark.parametrize(
    # `0x1f` is the boundary case: BOTH readings are the integer 31, so there is
    # no divergence to refuse and the lint must leave it alone.
    "raw",
    ["y", "n", "N", "09:00", "09", "0x1f", "1.0", "true", "0"],
)
def test_yaml_11_non_hazard_is_accepted(tmp_path: Path, raw: str) -> None:
    """`n` is a sample-size key in the live KIS draft; refusing it would be wrong."""
    text = _default_profile().replace(
        "  broker_id: BROKER_X\n", f"  broker_id: {raw}\n", 1
    )
    path = _write(tmp_path / "ok.yaml", text)
    assert len(bcp.compute_digests(path)) == 2


def test_quoting_a_hazard_makes_it_acceptable_and_distinct(tmp_path: Path) -> None:
    quoted = _write(
        tmp_path / "quoted.yaml",
        _default_profile().replace(
            "  broker_id: BROKER_X\n", '  broker_id: "yes"\n', 1
        ),
    )
    boolean = _write(
        tmp_path / "bool.yaml",
        _default_profile().replace("  broker_id: BROKER_X\n", "  broker_id: true\n", 1),
    )
    assert _digests(quoted)[0][0] != _digests(boolean)[0][0]


def test_environment_line_records_parser_and_unicode_identity() -> None:
    """F11: the Unicode data version NFC depends on is recorded next to a value."""
    line = bcp.environment_line()
    assert yaml.__version__ in line
    assert unicodedata.unidata_version in line
    assert "YAML 1.1" in line


# --------------------------------------------------------------------------
# P-4 — Unicode NFC normalization
# --------------------------------------------------------------------------


def test_nfc_normalization_folds_decomposed_strings(tmp_path: Path) -> None:
    composed = unicodedata.normalize("NFC", "모의투자_위탁")
    decomposed = unicodedata.normalize("NFD", "모의투자_위탁")
    assert composed != decomposed  # the fixture is meaningful

    nfc = _write(tmp_path / "nfc.yaml", _default_profile(account_type=composed))
    nfd = _write(tmp_path / "nfd.yaml", _default_profile(account_type=decomposed))

    sem_nfc, byte_nfc = _digests(nfc)[0]
    sem_nfd, byte_nfd = _digests(nfd)[0]

    assert sem_nfc == sem_nfd  # same meaning -> same semantic digest
    assert byte_nfc != byte_nfd  # different bytes -> different byte digest


def test_canonical_json_normalizes_mapping_keys() -> None:
    composed = unicodedata.normalize("NFC", "종목")
    decomposed = unicodedata.normalize("NFD", "종목")
    assert bcp.canonical_json({composed: 1}) == bcp.canonical_json({decomposed: 1})


def test_canonical_json_refuses_keys_that_collide_after_normalization() -> None:
    composed = unicodedata.normalize("NFC", "종목")
    decomposed = unicodedata.normalize("NFD", "종목")
    with pytest.raises(bcp.ProfileDigestError, match="collide after"):
        bcp.canonical_json({composed: 1, decomposed: 2})


# --------------------------------------------------------------------------
# P-5 / P-7 — self-exclusion, approver binding, and the byte fixed point
# --------------------------------------------------------------------------


def test_recording_the_computed_digests_changes_neither_digest(
    tmp_path: Path,
) -> None:
    """P-7 fixed point, exercised WITH a trailing comment and padding present."""
    path = _write(
        tmp_path / "p.yaml",
        _default_profile(
            canonicalization_version=bcp.ALGORITHM_ID,
            digest_comment="        # 승인 전 필수",
        ),
    )
    before = _digests(path)
    _record_digests(path)

    assert _digests(path) == before
    assert bcp.verify_digests(path) == []


def test_following_the_printed_replacement_lines_verifies(tmp_path: Path) -> None:
    """The workflow ``compute`` prescribes must actually produce a PASS."""
    path = _write(
        tmp_path / "p.yaml",
        _default_profile(
            canonicalization_version=bcp.ALGORITHM_ID, digest_comment="   # note"
        ),
    )
    prescribed = [
        line.split(": ", 1)[1]
        for line in bcp.compute_digests(path)[0].replacement_lines()
    ]
    assert len(prescribed) == 2
    assert all(line.endswith("   # note") for line in prescribed)

    _record_digests(path)
    written = path.read_text(encoding="utf-8").splitlines()
    for line in prescribed:
        assert line in written
    assert bcp.verify_digests(path) == []


def test_approvers_are_bound_by_both_digests(tmp_path: Path) -> None:
    """F2(a) mandatory canary: the approver set is inside BOTH digests."""
    empty = _write(tmp_path / "empty.yaml", _default_profile())
    signed = _write(
        tmp_path / "signed.yaml", _default_profile(approvers="[operator-alice]")
    )
    assert _digests(empty)[0][0] != _digests(signed)[0][0]
    assert _digests(empty)[0][1] != _digests(signed)[0][1]


def test_swapping_an_approver_is_detected_by_verify(tmp_path: Path) -> None:
    """F1 ADV-2 end to end: alice's approval cannot be rewritten to mallory's."""
    path = _approved_profile(tmp_path, approvers="[operator-alice]")
    assert bcp.verify_digests(path) == []

    text = path.read_text(encoding="utf-8")
    _write(path, text.replace("[operator-alice]", "[operator-mallory, operator-eve]"))

    problems = bcp.verify_digests(path)
    assert any("canonical_semantic_digest" in p for p in problems)
    assert any("byte_digest" in p for p in problems)
    assert bcp.main(["verify", str(path)]) == 1


def test_appending_an_approver_after_recording_invalidates_the_digests(
    tmp_path: Path,
) -> None:
    """P-5 freeze-then-compute: sequential sign-off is deliberately unsupported."""
    path = _approved_profile(tmp_path, approvers="[ai-review-2026-07-30]")
    text = path.read_text(encoding="utf-8")
    _write(
        path,
        text.replace(
            "[ai-review-2026-07-30]", "[ai-review-2026-07-30, operator-countersign]"
        ),
    )
    assert any("canonical_semantic_digest" in p for p in bcp.verify_digests(path))


def test_digest_fields_are_the_only_semantic_exclusions() -> None:
    assert bcp.SEMANTIC_EXCLUDED_IDENTITY_KEYS == bcp.DIGEST_KEYS
    assert "approvers" not in bcp.SEMANTIC_EXCLUDED_IDENTITY_KEYS


def test_status_is_inside_the_semantic_digest(tmp_path: Path) -> None:
    draft = _write(tmp_path / "draft.yaml", _default_profile())
    approved = _write(tmp_path / "approved.yaml", _default_profile(status="APPROVED"))
    assert _digests(draft)[0][0] != _digests(approved)[0][0]


def test_instance_local_annotations_are_inside_the_semantic_digest(
    tmp_path: Path,
) -> None:
    """`_`-prefixed annotations are covered: excluding them is a claim."""
    base = _default_profile()
    annotated = base.replace(
        "    restriction_approved: false\n",
        "    restriction_approved: false\n    _kis:\n      note: measured\n",
        1,
    )
    plain = _write(tmp_path / "plain.yaml", base)
    other = _write(tmp_path / "annotated.yaml", annotated)
    assert _digests(plain)[0][0] != _digests(other)[0][0]


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------


def test_verify_passes_on_a_correctly_filled_profile(tmp_path: Path) -> None:
    path = _approved_profile(tmp_path)
    assert bcp.verify_digests(path) == []
    assert bcp.main(["verify", str(path)]) == 0


def test_verify_fails_when_a_value_is_tampered_with(tmp_path: Path) -> None:
    path = _approved_profile(tmp_path)
    text = path.read_text(encoding="utf-8")
    _write(path, text.replace("maximum_concurrency: 0", "maximum_concurrency: 9", 1))

    assert any("canonical_semantic_digest" in p for p in bcp.verify_digests(path))
    assert bcp.main(["verify", str(path)]) == 1


def test_verify_fails_when_only_a_comment_is_tampered_with(tmp_path: Path) -> None:
    """The semantic digest still matches; the byte digest catches it."""
    path = _approved_profile(tmp_path)
    text = path.read_text(encoding="utf-8")
    _write(path, "# injected comment\n" + text)

    problems = bcp.verify_digests(path)
    assert [p for p in problems if "byte_digest: recorded" in p]
    assert not [p for p in problems if "canonical_semantic_digest: recorded" in p]


def test_verify_emits_a_bytes_only_diagnostic(tmp_path: Path) -> None:
    """F7: a byte-only mismatch must not be an opaque failure."""
    path = _approved_profile(tmp_path)
    text = path.read_text(encoding="utf-8")
    _write(path, text + "\n# a trailing comment added after approval\n")

    assert any(
        "diagnostic" in p and "bytes only" in p for p in bcp.verify_digests(path)
    )


def test_verify_reports_tbd_as_a_mismatch(tmp_path: Path) -> None:
    path = _write(tmp_path / "p.yaml", _default_profile())
    problems = bcp.verify_digests(path)

    assert len(problems) == 6  # 2 documents x (version + 2 digests)
    assert all("TBD (placeholder" in p for p in problems)
    assert bcp.main(["verify", str(path)]) == 1


def test_verify_reports_an_absent_field_as_a_mismatch(tmp_path: Path) -> None:
    text = _default_profile().replace("  byte_digest: TBD\n", "")
    path = _write(tmp_path / "p.yaml", text)
    assert any(
        "byte_digest: recorded <field absent>" in p for p in bcp.verify_digests(path)
    )


def test_verify_fails_on_a_different_canonicalization_version(tmp_path: Path) -> None:
    """P-12 / SPG-EV-003 'vary ... canonicalization versions' fails closed."""
    path = _approved_profile(tmp_path)
    text = path.read_text(encoding="utf-8")
    _write(
        path,
        text.replace(
            f"canonicalization_version: {bcp.ALGORITHM_ID}",
            "canonicalization_version: some-other-canonicalizer-1",
            1,
        ),
    )
    assert any("canonicalization_version" in p for p in bcp.verify_digests(path))


# --------------------------------------------------------------------------
# fail-closed guards
# --------------------------------------------------------------------------


def test_document_count_guard(tmp_path: Path) -> None:
    path = _write(tmp_path / "one.yaml", _profile(_document("ONLY")))
    with pytest.raises(bcp.ProfileDigestError, match="expected exactly 2"):
        bcp.compute_digests(path)
    assert bcp.main(["compute", str(path)]) == 1

    assert len(bcp.compute_digests(path, allow_any_doc_count=True)) == 1
    assert bcp.main(["compute", str(path), "--allow-any-doc-count"]) == 0


def test_duplicate_mapping_key_is_refused(tmp_path: Path) -> None:
    text = _default_profile().replace(
        "  broker_id: BROKER_X\n", "  broker_id: BROKER_X\n  broker_id: BROKER_Y\n", 1
    )
    path = _write(tmp_path / "dup.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="duplicate mapping key"):
        bcp.compute_digests(path)


def test_stray_digest_field_is_refused(tmp_path: Path) -> None:
    text = _default_profile().replace(
        "live_scope:\n", "live_scope:\n  byte_digest: TBD\n", 1
    )
    path = _write(tmp_path / "stray.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="outside 'profile_identity'"):
        bcp.compute_digests(path)


def test_unquoted_date_is_refused(tmp_path: Path) -> None:
    """P-9: no parser-rendered datetime may reach the canonical form."""
    text = _default_profile().replace(
        "  status: DRAFT\n", "  status: DRAFT\n  effective_from: 2026-07-29\n"
    )
    path = _write(tmp_path / "date.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="outside the canonical"):
        bcp.compute_digests(path)


def test_nan_is_refused(tmp_path: Path) -> None:
    text = _default_profile().replace(
        "  maximum_concurrency: 0\n", "  maximum_concurrency: .nan\n"
    )
    path = _write(tmp_path / "nan.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="NaN/Infinity"):
        bcp.compute_digests(path)


def test_infinity_is_refused(tmp_path: Path) -> None:
    text = _default_profile().replace(
        "  maximum_concurrency: 0\n", "  maximum_concurrency: .inf\n"
    )
    path = _write(tmp_path / "inf.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="NaN/Infinity"):
        bcp.compute_digests(path)


def test_non_string_key_is_refused(tmp_path: Path) -> None:
    text = _default_profile().replace(
        "  accounts: []\n", "  accounts:\n    1: one\n", 1
    )
    path = _write(tmp_path / "intkey.yaml", text)
    with pytest.raises(bcp.ProfileDigestError, match="not str"):
        bcp.compute_digests(path)


def test_missing_profile_identity_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path / "bare.yaml", _profile("live_scope: {}\n", "a: 1\n"))
    with pytest.raises(bcp.ProfileDigestError, match="is missing or is not a mapping"):
        bcp.compute_digests(path)


def test_malformed_yaml_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path / "bad.yaml", "profile_identity:\n  a: [1, 2\n")
    with pytest.raises(bcp.ProfileDigestError, match="YAML parse error"):
        bcp.compute_digests(path)
    assert bcp.main(["compute", str(path)]) == 1


def test_non_utf8_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "latin1.yaml"
    path.write_bytes(b"profile_identity:\n  artifact_id: \xff\xfe\n")
    with pytest.raises(bcp.ProfileDigestError, match="not valid UTF-8"):
        bcp.compute_digests(path)


def test_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(bcp.ProfileDigestError, match="cannot read"):
        bcp.compute_digests(tmp_path / "nope.yaml")


def test_numeric_forms_do_not_collide() -> None:
    assert bcp.canonical_json({"a": 1}) != bcp.canonical_json({"a": 1.0})
    assert bcp.canonical_json({"a": 0.0}) != bcp.canonical_json({"a": -0.0})
    assert bcp.canonical_json({"a": True}) != bcp.canonical_json({"a": 1})


# --------------------------------------------------------------------------
# CLI surface
# --------------------------------------------------------------------------


def test_compute_prints_identity_banner_and_replacement_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path / "p.yaml", _default_profile(digest_comment="  # owed"))
    assert bcp.main(["compute", str(path)]) == 0

    out = capsys.readouterr().out
    assert "PROVISIONAL, NON-PRODUCTION" in out
    assert "operator decision D5" in out
    assert "document 0" in out and "document 1" in out
    assert "FIXTURE-A" in out and "FIXTURE-B" in out
    assert "record these physical lines VERBATIM" in out
    assert "  # owed" in out  # the trail is preserved in the prescribed line
    assert "approvers[] included" in out


def test_refusal_goes_to_stderr_with_a_nonzero_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path / "one.yaml", _profile(_document("ONLY")))
    assert bcp.main(["compute", str(path)]) == 1

    captured = capsys.readouterr()
    assert "REFUSED" in captured.err
    assert captured.out == ""


def test_tool_never_writes_to_the_profile(tmp_path: Path) -> None:
    path = _write(tmp_path / "p.yaml", _default_profile())
    before = path.read_bytes()
    bcp.main(["compute", str(path)])
    bcp.main(["verify", str(path)])
    assert path.read_bytes() == before
