"""Dashboard asset-class selector helpers."""

from fastapi import HTTPException

VALID_ASSET = {"stock", "futures", "all"}
ASSET_CLASSES = ("futures", "stock")


def normalize_asset_class(value: str | None) -> str:
    """Validate and normalize the ``asset_class`` selector."""
    if value is None:
        return "futures"
    normalized = value.strip().lower()
    if normalized not in VALID_ASSET:
        raise HTTPException(
            status_code=400,
            detail="asset_class must be stock, futures, or all",
        )
    return normalized


def target_assets(asset_class: str) -> tuple[str, ...]:
    """Return concrete asset classes for a normalized selector."""
    return ASSET_CLASSES if asset_class == "all" else (asset_class,)
