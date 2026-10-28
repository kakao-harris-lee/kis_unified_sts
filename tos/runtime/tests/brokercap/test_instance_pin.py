"""The render's pin on the INSTANCE profile file is checked at boot (#958).

The failing input from the issue: a rendered tree's ``instance_path`` points into a mutable source
checkout, and an edit there (MOCK_VTS ``rest_base``), made after the render, was booted as a host
fact. Each test builds a RENDERED tree in ``tmp_path`` the way ``render_paper_config.py`` lays it
out — the committed stock tree's ``broker_scopes.yaml`` with an ABSOLUTE ``instance_path`` and a
``RENDERED.json`` carrying ``broker_profile_instance`` — over a copy of the committed profile, then
drives the two boot-time reads: the active scope's bound document
(:func:`~tos_runtime.brokercap.derive.load_active_instance_document`) and the #932 host seal
(:func:`~tos_runtime.compose._transport_wiring.instance_rest_bases`).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml
from tos_runtime.brokercap import load_active_instance_document, load_broker_scopes
from tos_runtime.brokercap.instance import BrokerInstanceConfigError
from tos_runtime.brokercap.instance_pin import PIN_KEY, RENDERED_MANIFEST_NAME
from tos_runtime.compose._boot_integrity import _broker_scopes_coordinates
from tos_runtime.compose._transport_wiring import instance_rest_bases

_REPO_ROOT = Path(__file__).resolve().parents[4]
_STOCK_SCOPES = (
    _REPO_ROOT / "config/tos_runtime/cp3-setup-d-stock-005930/broker_scopes.yaml"
)
_PROFILE = _REPO_ROOT / "docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"


def _render(
    tmp_path: Path,
    *,
    pin: object = "auto",
    with_manifest: bool = True,
    relative: bool = False,
) -> tuple[Path, Path]:
    """A rendered tree over a private copy of the profile. Returns ``(scopes, profile)``.

    ``relative=True`` writes ``instance_path`` relative to the tree, the way every committed
    tree does (``../../../docs/…``) — the shape of an UNRENDERED tree."""
    profile = tmp_path / "source" / "docs" / _PROFILE.name
    profile.parent.mkdir(parents=True)
    profile.write_bytes(_PROFILE.read_bytes())
    tree = tmp_path / "render"
    tree.mkdir()
    raw = yaml.safe_load(_STOCK_SCOPES.read_text(encoding="utf-8"))
    raw["instance_path"] = (
        f"../source/docs/{profile.name}" if relative else str(profile)
    )
    scopes = tree / "broker_scopes.yaml"
    scopes.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    if with_manifest:
        manifest: dict[str, object] = {"tree_id": "cp3-setup-d-stock-005930"}
        if pin == "auto":
            pin = {
                "path": str(profile),
                "sha256": hashlib.sha256(profile.read_bytes()).hexdigest(),
            }
        if pin is not None:
            manifest[PIN_KEY] = pin
        (tree / RENDERED_MANIFEST_NAME).write_text(json.dumps(manifest), "utf-8")
    return scopes, profile


def _load(scopes: Path):  # noqa: ANN202 — the loader's own return type
    return load_broker_scopes(scopes, environment_label="paper")


def test_a_rendered_tree_carries_the_pin_and_boots_on_the_bound_bytes(
    tmp_path: Path,
) -> None:
    scopes, profile = _render(tmp_path)
    config = _load(scopes)
    assert config.instance_sha256 == hashlib.sha256(profile.read_bytes()).hexdigest()
    assert load_active_instance_document(config) is not None
    mock, real = instance_rest_bases(config)
    assert mock != real


def test_an_edit_to_the_profile_after_the_render_refuses_the_boot(
    tmp_path: Path,
) -> None:
    """The issue's failing input: MOCK_VTS ``rest_base`` changed in the source checkout between
    the render and the boot. Both boot-time reads refuse it."""
    scopes, profile = _render(tmp_path)
    config = _load(scopes)
    text = profile.read_text(encoding="utf-8")
    assert "openapivts" in text
    profile.write_text(text.replace("openapivts", "openapivtz", 1), encoding="utf-8")
    with pytest.raises(BrokerInstanceConfigError, match="changed since the render"):
        load_active_instance_document(config)
    with pytest.raises(BrokerInstanceConfigError, match="changed since the render"):
        instance_rest_bases(config)


def test_a_symlink_on_the_pinned_path_refuses_the_boot_even_with_the_same_bytes(
    tmp_path: Path,
) -> None:
    """The render pinned the RESOLVED file; a link appearing at that path later names some
    other file, so it is refused before its bytes are even compared."""
    scopes, profile = _render(tmp_path)
    elsewhere = tmp_path / "elsewhere.yaml"
    elsewhere.write_bytes(profile.read_bytes())
    profile.unlink()
    profile.symlink_to(elsewhere)
    with pytest.raises(BrokerInstanceConfigError, match="symlink"):
        load_active_instance_document(_load(scopes))


def test_a_render_with_an_absolute_instance_path_and_no_pin_is_refused(
    tmp_path: Path,
) -> None:
    """A render from before #958 (or one that skipped the pin) points into the source checkout
    with nothing binding it."""
    scopes, _ = _render(tmp_path, pin=None)
    with pytest.raises(
        BrokerInstanceConfigError, match="no 'broker_profile_instance' pin"
    ):
        _load(scopes)


@pytest.mark.parametrize(
    ("pin", "message"),
    [
        pytest.param(
            {"path": "/elsewhere.yaml", "sha256": "0" * 64},
            "is not the instance_path",
            id="other-path",
        ),
        pytest.param(
            {"path": "PROFILE", "sha256": "ABC"}, "64 lowercase hex", id="bad-sha"
        ),
        pytest.param("not-a-mapping", "64 lowercase hex", id="not-a-mapping"),
    ],
)
def test_a_malformed_pin_is_refused(tmp_path: Path, pin: object, message: str) -> None:
    profile_path = str(tmp_path / "source" / "docs" / _PROFILE.name)
    if isinstance(pin, dict) and pin["path"] == "PROFILE":
        pin = {**pin, "path": profile_path}
    scopes, _ = _render(tmp_path, pin=pin)
    with pytest.raises(BrokerInstanceConfigError, match=message):
        _load(scopes)


def test_a_rendered_tree_that_lost_its_manifest_is_refused(tmp_path: Path) -> None:
    """#988 review MEDIUM: render → ``RENDERED.json`` deleted → MOCK_VTS ``rest_base`` edited in
    the source → boot. Without the manifest there is no pin, and an ABSOLUTE ``instance_path`` is
    a render's reach into a source checkout — so it is refused, not booted unpinned."""
    scopes, profile = _render(tmp_path)
    (scopes.parent / RENDERED_MANIFEST_NAME).unlink()
    text = profile.read_text(encoding="utf-8")
    profile.write_text(text.replace("openapivts", "openapivtz", 1), encoding="utf-8")
    with pytest.raises(BrokerInstanceConfigError, match="no RENDERED.json"):
        _load(scopes)


def test_an_unrendered_tree_is_unpinned_and_unchanged(tmp_path: Path) -> None:
    """No ``RENDERED.json`` and a RELATIVE ``instance_path``: the committed trees. Nothing to
    pin, behaviour unchanged."""
    scopes, profile = _render(tmp_path, with_manifest=False, relative=True)
    config = _load(scopes)
    assert config.instance_sha256 is None
    profile.write_text(profile.read_text("utf-8") + "\n# edited\n", encoding="utf-8")
    assert load_active_instance_document(config) is not None


def test_the_attested_inputs_row_records_the_pin_not_a_second_read(
    tmp_path: Path,
) -> None:
    """#988 review LOW: the boot's attested-inputs evidence row for the INSTANCE file must carry
    the digest the boot actually verified. Re-hashing the file there is a second read outside the
    pin — an edit landing after the pinned load would be recorded as if it had been booted.
    """
    scopes, profile = _render(tmp_path)
    config = _load(scopes)
    document = load_active_instance_document(config)
    profile.write_text(profile.read_text("utf-8") + "\n# edited\n", encoding="utf-8")
    rows = _broker_scopes_coordinates(scopes.parent, config, document)
    (instance_row,) = [r for r in rows if r["source_file"] == profile.name]
    assert instance_row["source_file_digest"] == config.instance_sha256
