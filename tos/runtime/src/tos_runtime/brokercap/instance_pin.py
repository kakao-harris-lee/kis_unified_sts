"""The render's pin on the Broker Capability Profile INSTANCE file (#958)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tos_runtime.brokercap.instance import BrokerInstanceConfigError

__all__ = ["PIN_KEY", "RENDERED_MANIFEST_NAME", "render_pin"]

RENDERED_MANIFEST_NAME = "RENDERED.json"

PIN_KEY = "broker_profile_instance"

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def render_pin(scopes_path: Path, raw_instance_path: object) -> str | None:
    """The sha256 the render bound for the instance file, or ``None`` for an unrendered tree."""
    manifest_path = scopes_path.parent / RENDERED_MANIFEST_NAME
    absolute = (
        isinstance(raw_instance_path, str) and Path(raw_instance_path).is_absolute()
    )
    if not manifest_path.is_file():
        if absolute:
            raise BrokerInstanceConfigError(
                f"{scopes_path}: instance_path {raw_instance_path!r} is absolute but there is "
                f"no {RENDERED_MANIFEST_NAME} beside it — an absolute path is a render's, and "
                "a render without its manifest carries no pin; refusing to boot (write a "
                "relative instance_path for an unrendered tree)"
            )
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BrokerInstanceConfigError(
            f"{manifest_path}: cannot read the render manifest: {exc}"
        ) from exc
    pin = manifest.get(PIN_KEY) if isinstance(manifest, dict) else None
    if pin is None:
        if absolute:
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
