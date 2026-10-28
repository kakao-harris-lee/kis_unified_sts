"""The render's pin on the Broker Capability Profile INSTANCE file (#958).

A rendered tree's ``broker_scopes.yaml::instance_path`` is an ABSOLUTE path back into the source
checkout the render ran from (``scripts/tos/render_paper_config.py``
``resolve_broker_profile_instance_path``) — a mutable place. Without a pin, an uncommitted edit
there (say, MOCK_VTS ``rest_base``), or any change between the 08:45 render and the 08:55 boot,
is booted as a host fact.

So the renderer records ``{"path", "sha256"}`` of the file it bound under
:data:`PIN_KEY` in the tree's own :data:`RENDERED_MANIFEST_NAME`, and :func:`render_pin` hands
that sha256 to :func:`~tos_runtime.brokercap.scopes.load_broker_scopes`; every instance read then
checks it (:func:`tos_runtime.brokercap.instance._read_instance_text`).

Which trees are pinned:

* no ``RENDERED.json`` beside ``broker_scopes.yaml`` — an unrendered tree (the committed trees,
  the hermetic test fixtures). Its ``instance_path`` is the committed relative path into this
  same repo; nothing to pin, behaviour unchanged.
* ``RENDERED.json`` present — a render. The pin, when recorded, must name the very path the
  rendered ``broker_scopes.yaml`` carries. A render whose ``instance_path`` is ABSOLUTE but which
  recorded NO pin is refused: that is exactly the source-checkout reach the pin exists for (a
  render from before #958, or one that skipped it). A render that kept the committed RELATIVE
  value (the futures trees, whose manifests declare no instance slot) needs none.

The manifest's name and key are the renderer's (``RENDERED_NAME`` /
``broker_profile_instance``); the runtime may not import ``scripts``, so both sides carry the
literal and ``tests/unit/scripts/test_render_stock_tenant_mock_boot.py`` boots a real render
through this reader.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tos_runtime.brokercap.instance import BrokerInstanceConfigError

__all__ = ["PIN_KEY", "RENDERED_MANIFEST_NAME", "render_pin"]

#: The renderer's output manifest, written into the rendered config directory.
RENDERED_MANIFEST_NAME = "RENDERED.json"

#: Its key holding ``{"path": <absolute instance path>, "sha256": <hex>}``.
PIN_KEY = "broker_profile_instance"

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def render_pin(scopes_path: Path, raw_instance_path: object) -> str | None:
    """The sha256 the render bound for the instance file, or ``None`` for an unrendered tree.

    Args:
        scopes_path: The ``broker_scopes.yaml`` being loaded; its directory is the tree.
        raw_instance_path: That file's ``instance_path`` value AS WRITTEN (before relative
            resolution), so an absolute rendered value can be told from a committed relative one.

    Raises:
        BrokerInstanceConfigError: ``RENDERED.json`` is unreadable or malformed, its pin is
            malformed or names another path, or it carries no pin for an absolute
            ``instance_path`` (module docstring).
    """
    manifest_path = scopes_path.parent / RENDERED_MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BrokerInstanceConfigError(
            f"{manifest_path}: cannot read the render manifest: {exc}"
        ) from exc
    pin = manifest.get(PIN_KEY) if isinstance(manifest, dict) else None
    if pin is None:
        if isinstance(raw_instance_path, str) and Path(raw_instance_path).is_absolute():
            raise BrokerInstanceConfigError(
                f"{manifest_path}: no {PIN_KEY!r} pin, but {scopes_path.name} names the "
                f"absolute instance_path {raw_instance_path!r} — a render must bind the "
                "profile it points at (re-render with a current renderer); refusing to boot"
            )
        return None
    path = pin.get("path") if isinstance(pin, dict) else None
    sha256 = pin.get("sha256") if isinstance(pin, dict) else None
    if not isinstance(sha256, str) or not _SHA256_HEX.fullmatch(sha256):
        raise BrokerInstanceConfigError(
            f"{manifest_path}: {PIN_KEY}.sha256 must be 64 lowercase hex digits, got {sha256!r}"
        )
    if path != raw_instance_path:
        raise BrokerInstanceConfigError(
            f"{manifest_path}: {PIN_KEY}.path {path!r} is not the instance_path "
            f"{raw_instance_path!r} {scopes_path.name} carries — refusing to boot"
        )
    return sha256
