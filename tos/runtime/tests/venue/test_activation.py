"""tos_runtime.venue.activation — unit tests (hermetic, tmp_path only)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.spg import BundleMemberKind, BundleMemberRef
from tos_runtime.venue.activation import (
    ActivationMembersConfigError,
    PolicyNotActivated,
    load_activation_members,
    require_member_activated,
)

_DIGEST = "a" * 64
_KIND = BundleMemberKind.VENUE_CONSTRAINT_POLICY
_MEMBER_ID = "vcp-fixture-1"
_GENERATION = 1


def _member_entry(
    *,
    kind: str,
    member_id: str,
    generation: int,
    digest: str,
    resolved: str,
    immutable: str,
) -> str:
    """One ``members:`` list-item block at the FINAL (2-space list-item /
    4-space field) indentation level — no ``textwrap.dedent`` involved, so
    concatenating several of these is never fragile to dedent's "common
    leading whitespace across ALL lines" computation."""
    return (
        f'  - kind: "{kind}"\n'
        f'    member_id: "{member_id}"\n'
        f"    generation: {generation}\n"
        f'    digest: "{digest}"\n'
        f"    resolved: {resolved}\n"
        f"    immutable: {immutable}\n"
    )


def _activation_yaml(
    *,
    digest: str = _DIGEST,
    resolved: str = "true",
    immutable: str = "true",
    kind: str = "VENUE_CONSTRAINT_POLICY",
    member_id: str = _MEMBER_ID,
    generation: int = _GENERATION,
    extra_entry: str = "",
) -> str:
    entry = _member_entry(
        kind=kind,
        member_id=member_id,
        generation=generation,
        digest=digest,
        resolved=resolved,
        immutable=immutable,
    )
    return f"members:\n{entry}{extra_entry}"


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "safety_activation.yaml"
    path.write_text(text, encoding="utf-8")
    return path


# ===========================================================================
# load_activation_members
# ===========================================================================


def test_load_activation_members_happy_path(tmp_path: Path) -> None:
    path = _write(tmp_path, _activation_yaml())
    members = load_activation_members(path)
    assert len(members) == 1
    assert isinstance(members[0], BundleMemberRef)
    assert members[0].kind is _KIND
    assert members[0].digest == _DIGEST


def test_load_activation_members_empty_list_is_accepted(tmp_path: Path) -> None:
    path = _write(tmp_path, "members: []\n")
    assert load_activation_members(path) == ()


def test_load_activation_members_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ActivationMembersConfigError, match="not found"):
        load_activation_members(tmp_path / "nope.yaml")


def test_load_activation_members_missing_key_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "some_other_key: 1\n")
    with pytest.raises(ActivationMembersConfigError, match="members"):
        load_activation_members(path)


def test_load_activation_members_null_key_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "members: null\n")
    with pytest.raises(ActivationMembersConfigError, match="members"):
        load_activation_members(path)


def test_load_activation_members_not_a_list_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "members: {}\n")
    with pytest.raises(ActivationMembersConfigError, match="explicit list"):
        load_activation_members(path)


def test_load_activation_members_entry_fails_model_validate(tmp_path: Path) -> None:
    path = _write(tmp_path, 'members:\n  - kind: "NOT_A_REAL_KIND"\n')
    with pytest.raises(ActivationMembersConfigError, match="does not validate"):
        load_activation_members(path)


def test_load_activation_members_never_reads_other_keys(tmp_path: Path) -> None:
    """The loader reads ONLY the ``members`` key — module docstring."""
    path = _write(
        tmp_path,
        _activation_yaml()
        + "\nbundle_digest: 'should-never-be-read'\napproval_ids: [1, 2]\n",
    )
    members = load_activation_members(path)
    assert len(members) == 1


# ===========================================================================
# require_member_activated — happy path
# ===========================================================================


def test_require_member_activated_exact_match(tmp_path: Path) -> None:
    path = _write(tmp_path, _activation_yaml())
    members = load_activation_members(path)
    ref = require_member_activated(
        members,
        kind=_KIND,
        member_id=_MEMBER_ID,
        generation=_GENERATION,
        digest=_DIGEST,
    )
    assert ref.digest == _DIGEST


# ===========================================================================
# require_member_activated — negatives (mutation M2's three cases + duplicates)
# ===========================================================================


def test_require_member_activated_digest_one_char_off_refused(tmp_path: Path) -> None:
    wrong_digest = "b" + _DIGEST[1:]
    path = _write(tmp_path, _activation_yaml(digest=wrong_digest))
    members = load_activation_members(path)
    with pytest.raises(PolicyNotActivated):
        require_member_activated(
            members,
            kind=_KIND,
            member_id=_MEMBER_ID,
            generation=_GENERATION,
            digest=_DIGEST,
        )


def test_require_member_activated_digest_last_char_off_refused(tmp_path: Path) -> None:
    """Team-lead review HIGH, 2026-09-15: the pre-existing negative only ever
    flipped the FIRST character, so a bug that compared just an 8-char
    prefix would still pass all tests. Flip only the LAST character
    instead — an exact-match comparator must still refuse."""
    wrong_digest = _DIGEST[:-1] + "b"
    assert wrong_digest[:32] == _DIGEST[:32]  # same long leading prefix
    path = _write(tmp_path, _activation_yaml(digest=wrong_digest))
    members = load_activation_members(path)
    with pytest.raises(PolicyNotActivated):
        require_member_activated(
            members,
            kind=_KIND,
            member_id=_MEMBER_ID,
            generation=_GENERATION,
            digest=_DIGEST,
        )


def test_require_member_activated_digest_shared_long_prefix_refused(
    tmp_path: Path,
) -> None:
    """A digest sharing the SAME 32 leading characters as the real one but
    differing entirely in the trailing 32 — pins that the comparator checks
    the whole string, not just a leading prefix (team-lead review HIGH)."""
    wrong_digest = ("a" * 32) + ("b" * 32)
    assert len(wrong_digest) == len(_DIGEST)
    assert wrong_digest[:32] == _DIGEST[:32]
    assert wrong_digest != _DIGEST
    path = _write(tmp_path, _activation_yaml(digest=wrong_digest))
    members = load_activation_members(path)
    with pytest.raises(PolicyNotActivated):
        require_member_activated(
            members,
            kind=_KIND,
            member_id=_MEMBER_ID,
            generation=_GENERATION,
            digest=_DIGEST,
        )


def test_require_member_activated_digest_strict_prefix_of_real_refused(
    tmp_path: Path,
) -> None:
    """A digest that is a STRICT PREFIX of the real one (shorter, every
    character matching) — pins that the comparator is exact-length equality,
    never a ``startswith``/prefix check (team-lead review HIGH)."""
    wrong_digest = _DIGEST[:32]
    assert _DIGEST.startswith(wrong_digest)
    assert wrong_digest != _DIGEST
    path = _write(tmp_path, _activation_yaml(digest=wrong_digest))
    members = load_activation_members(path)
    with pytest.raises(PolicyNotActivated):
        require_member_activated(
            members,
            kind=_KIND,
            member_id=_MEMBER_ID,
            generation=_GENERATION,
            digest=_DIGEST,
        )


def test_require_member_activated_resolved_false_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, _activation_yaml(resolved="false"))
    members = load_activation_members(path)
    with pytest.raises(PolicyNotActivated, match="resolved"):
        require_member_activated(
            members,
            kind=_KIND,
            member_id=_MEMBER_ID,
            generation=_GENERATION,
            digest=_DIGEST,
        )


def test_require_member_activated_immutable_false_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, _activation_yaml(immutable="false"))
    members = load_activation_members(path)
    with pytest.raises(PolicyNotActivated, match="immutable"):
        require_member_activated(
            members,
            kind=_KIND,
            member_id=_MEMBER_ID,
            generation=_GENERATION,
            digest=_DIGEST,
        )


def test_require_member_activated_empty_members_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "members: []\n")
    members = load_activation_members(path)
    with pytest.raises(PolicyNotActivated):
        require_member_activated(
            members,
            kind=_KIND,
            member_id=_MEMBER_ID,
            generation=_GENERATION,
            digest=_DIGEST,
        )


def test_require_member_activated_two_identical_matches_refused(tmp_path: Path) -> None:
    extra = _member_entry(
        kind="VENUE_CONSTRAINT_POLICY",
        member_id=_MEMBER_ID,
        generation=_GENERATION,
        digest=_DIGEST,
        resolved="true",
        immutable="true",
    )
    path = _write(tmp_path, _activation_yaml(extra_entry=extra))
    members = load_activation_members(path)
    assert len(members) == 2
    with pytest.raises(PolicyNotActivated, match="2 distinct members"):
        require_member_activated(
            members,
            kind=_KIND,
            member_id=_MEMBER_ID,
            generation=_GENERATION,
            digest=_DIGEST,
        )


def test_require_member_activated_kind_mismatch_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, _activation_yaml(kind="ORDER_CONSTRUCTION_POLICY"))
    members = load_activation_members(path)
    with pytest.raises(PolicyNotActivated):
        require_member_activated(
            members,
            kind=_KIND,
            member_id=_MEMBER_ID,
            generation=_GENERATION,
            digest=_DIGEST,
        )


def test_require_member_activated_generation_mismatch_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, _activation_yaml(generation=2))
    members = load_activation_members(path)
    with pytest.raises(PolicyNotActivated):
        require_member_activated(
            members,
            kind=_KIND,
            member_id=_MEMBER_ID,
            generation=_GENERATION,
            digest=_DIGEST,
        )
