"""``fill_observer.yaml`` — the post-ACK fill observer's cadence, bounds, and sealed witness"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from tos_runtime._named_tbd import reject_named_tbd

__all__ = [
    "FILL_OBSERVER_CONFIG_NAME",
    "FillObserverConfig",
    "FillObserverConfigError",
    "load_fill_observer_config",
]

FILL_OBSERVER_CONFIG_NAME = "fill_observer.yaml"


class FillObserverConfigError(Exception):
    """``fill_observer.yaml`` is missing, malformed, or has a non-positive bound."""


@dataclass(frozen=True)
class FillObserverConfig:
    """The observer's cadence and bounds plus the witness fields it seals (module docstring)."""

    witness_fields: dict[str, Any]
    poll_interval_ms: int
    overdue_after_ms: int
    finality_retry_interval_ms: int
    prior_day_poll_interval_ms: int
    poll_deadline_ms: int
    witness_request_timeout_s: float
    release_snapshot_max_age_ms: int
    held_position_poll_interval_ms: int | None = None
    held_position_max_age_ms: int | None = None
    ack_date_recovery_lookback_trading_days: int | None = None
    broker_flat_release: bool = False
    broker_flat_release_settle_ms: int | None = None
    uncertain_send_reconcile: bool = False
    uncertain_send_settle_ms: int | None = None
    #: How far before our own send start a broker 주문시각 may still be this send's own order
    #: (issue #1127). Config, not a constant: it is a tolerance on two clocks we do not own.
    uncertain_send_ord_tmd_tolerance_s: int | None = None
    #: How much OLDER than our send start a row must be before it is somebody else's rather
    #: than clock error. Strictly greater than the tolerance; between the two, a row holds.
    uncertain_send_foreign_min_age_s: int | None = None
    #: ``outbound_side`` token -> the ``sll_buy_dvsn_cd`` the broker prints for it. Config, not
    #: a constant: a side is a policy-carried token in this runtime, never one it authors.
    uncertain_send_side_codes: dict[str, str] = field(default_factory=dict)
    loop_witness_request_timeout_s: float | None = None
    #: The loop-side walk deadline for a ONE-date scope; each further receipt date in the scope
    #: adds one app-key pacing interval, up to :attr:`loop_witness_deadline_max_ms` (#1115 N1).
    loop_witness_deadline_ms: int | None = None
    loop_witness_deadline_max_ms: int | None = None


_WITNESS_KEYS = (
    "balance_path",
    "balance_tr_id",
    "order_inquiry_path",
    "order_inquiry_tr_id",
    "max_pages",
)


def _positive_number(raw: dict[str, Any], key: str, path: Path) -> float:
    """A positive int or float (a timeout in seconds is not naturally an int)."""
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise FillObserverConfigError(
            f"{path}: {key!r} must be a positive number, got {value!r}"
        )
    return float(value)


def _positive_int(raw: dict[str, Any], key: str, path: Path) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise FillObserverConfigError(
            f"{path}: {key!r} must be a positive int, got {value!r}"
        )
    return value


def load_fill_observer_config(path: Path) -> FillObserverConfig:
    """Load ``fill_observer.yaml``, fail-closed."""
    if not path.is_file():
        raise FillObserverConfigError(f"fill observer config not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise FillObserverConfigError(f"{path}: unreadable ({exc})") from exc
    if not isinstance(raw, dict):
        raise FillObserverConfigError(f"{path}: must be a top-level mapping")
    held_keys = ("held_position_poll_interval_ms", "held_position_max_age_ms")
    if any(key in raw for key in held_keys) and not all(
        key in raw for key in held_keys
    ):
        raise FillObserverConfigError(
            f"{path}: held position bounds must be supplied together"
        )
    broker_flat_release = raw.get("broker_flat_release", False)
    if not isinstance(broker_flat_release, bool):
        raise FillObserverConfigError(
            f"{path}: 'broker_flat_release' must be true or false, got {broker_flat_release!r}"
        )
    if broker_flat_release and not all(key in raw for key in held_keys):
        raise FillObserverConfigError(
            f"{path}: broker_flat_release rides the held-position double read and needs "
            "its bounds"
        )
    if broker_flat_release and "broker_flat_release_settle_ms" not in raw:
        raise FillObserverConfigError(
            f"{path}: broker_flat_release needs broker_flat_release_settle_ms (the "
            "fill-to-balance reflection lag it waits out)"
        )
    _loop_witness_deadlines(raw, path)
    uncertain_send_reconcile, side_codes = _uncertain_send(raw, path)
    missing = [key for key in _WITNESS_KEYS if key not in raw]
    if missing:
        raise FillObserverConfigError(f"{path}: missing {missing}")
    for key in _WITNESS_KEYS:
        reject_named_tbd(
            raw[key], field=key, context=str(path), error_cls=FillObserverConfigError
        )
    return FillObserverConfig(
        witness_fields={key: raw[key] for key in _WITNESS_KEYS},
        poll_interval_ms=_positive_int(raw, "poll_interval_ms", path),
        overdue_after_ms=_positive_int(raw, "overdue_after_ms", path),
        finality_retry_interval_ms=_positive_int(
            raw, "finality_retry_interval_ms", path
        ),
        prior_day_poll_interval_ms=_positive_int(
            raw, "prior_day_poll_interval_ms", path
        ),
        poll_deadline_ms=_positive_int(raw, "poll_deadline_ms", path),
        witness_request_timeout_s=_positive_number(
            raw, "witness_request_timeout_s", path
        ),
        release_snapshot_max_age_ms=_positive_int(
            raw, "release_snapshot_max_age_ms", path
        ),
        held_position_poll_interval_ms=(
            _positive_int(raw, "held_position_poll_interval_ms", path)
            if "held_position_poll_interval_ms" in raw
            else None
        ),
        held_position_max_age_ms=(
            _positive_int(raw, "held_position_max_age_ms", path)
            if "held_position_max_age_ms" in raw
            else None
        ),
        ack_date_recovery_lookback_trading_days=(
            _positive_int(raw, "ack_date_recovery_lookback_trading_days", path)
            if "ack_date_recovery_lookback_trading_days" in raw
            else None
        ),
        broker_flat_release=broker_flat_release,
        broker_flat_release_settle_ms=_optional_positive_int(
            raw, "broker_flat_release_settle_ms", path
        ),
        loop_witness_request_timeout_s=(
            _positive_number(raw, "loop_witness_request_timeout_s", path)
            if "loop_witness_request_timeout_s" in raw
            else None
        ),
        loop_witness_deadline_ms=_optional_positive_int(
            raw, "loop_witness_deadline_ms", path
        ),
        loop_witness_deadline_max_ms=_optional_positive_int(
            raw, "loop_witness_deadline_max_ms", path
        ),
        uncertain_send_reconcile=uncertain_send_reconcile,
        uncertain_send_settle_ms=_optional_positive_int(
            raw, "uncertain_send_settle_ms", path
        ),
        uncertain_send_ord_tmd_tolerance_s=_optional_positive_int(
            raw, "uncertain_send_ord_tmd_tolerance_s", path
        ),
        uncertain_send_foreign_min_age_s=_optional_positive_int(
            raw, "uncertain_send_foreign_min_age_s", path
        ),
        uncertain_send_side_codes=side_codes,
    )


def _loop_witness_deadlines(raw: dict[str, Any], path: Path) -> None:
    """The loop-side walk deadline and its cap (#1115 N1): a cap needs a base, and is not below it."""
    cap_key = "loop_witness_deadline_max_ms"
    if cap_key not in raw:
        return
    if "loop_witness_deadline_ms" not in raw:
        raise FillObserverConfigError(
            f"{path}: {cap_key} caps loop_witness_deadline_ms and needs it (without a base "
            "deadline the loop-side read is unbounded and nothing is capped)"
        )
    cap = _positive_int(raw, cap_key, path)
    base = _positive_int(raw, "loop_witness_deadline_ms", path)
    if cap < base:
        raise FillObserverConfigError(
            f"{path}: {cap_key} {cap} is below loop_witness_deadline_ms {base} — the cap would "
            "shorten the one-date deadline it exists to extend"
        )


def _uncertain_send(raw: dict[str, Any], path: Path) -> tuple[bool, dict[str, str]]:
    """The uncertain-send reconciliation's gate and its two companions (2026-11-20 d/e)."""
    enabled = raw.get("uncertain_send_reconcile", False)
    if not isinstance(enabled, bool):
        raise FillObserverConfigError(
            f"{path}: 'uncertain_send_reconcile' must be true or false, got {enabled!r}"
        )
    if enabled and "uncertain_send_settle_ms" not in raw:
        raise FillObserverConfigError(
            f"{path}: uncertain_send_reconcile needs uncertain_send_settle_ms (the window "
            "an empty broker order history must stay empty before it proves a non-send)"
        )
    if enabled and "uncertain_send_ord_tmd_tolerance_s" not in raw:
        raise FillObserverConfigError(
            f"{path}: uncertain_send_reconcile needs "
            "uncertain_send_ord_tmd_tolerance_s (how far before our own send start a broker "
            "주문시각 may still be ours — without it an EARLIER order of the same shape "
            "binds to this send, issue #1127)"
        )
    if enabled and "uncertain_send_foreign_min_age_s" not in raw:
        raise FillObserverConfigError(
            f"{path}: uncertain_send_reconcile needs "
            "uncertain_send_foreign_min_age_s (how much older than our send start a row must "
            "be before it is somebody else's rather than clock skew — without it a row our "
            "own send created under a drifted host clock is discarded and the reservation "
            "released, issue #1127 review r1)"
        )
    _refuse_overlapping_time_thresholds(raw, path)
    return enabled, _side_codes(raw, path, required=enabled)


def _refuse_overlapping_time_thresholds(raw: dict[str, Any], path: Path) -> None:
    """``foreign_min_age_s`` must be STRICTLY older than the tolerance (#1127 review r1).

    Equal or inverted leaves no unprovable band at all: every row the tolerance refuses is
    immediately "somebody else's", which is exactly the release-on-skew the band exists to
    prevent. Refusing at load is the only place this is visible before a send goes blind.
    """
    tolerance = raw.get("uncertain_send_ord_tmd_tolerance_s")
    foreign_min_age = raw.get("uncertain_send_foreign_min_age_s")
    if (
        isinstance(tolerance, bool)
        or isinstance(foreign_min_age, bool)
        or not isinstance(tolerance, int)
        or not isinstance(foreign_min_age, int)
    ):
        # A non-int (or absent) value is `_optional_positive_int`'s refusal to make, with its
        # own message; this check only compares two numbers that are already numbers.
        return
    if foreign_min_age <= tolerance:
        raise FillObserverConfigError(
            f"{path}: uncertain_send_foreign_min_age_s ({foreign_min_age}) must be greater "
            f"than uncertain_send_ord_tmd_tolerance_s ({tolerance}) — otherwise no row is "
            "ever held as unprovable and a clock skew releases our own order"
        )


def _side_codes(raw: dict[str, Any], path: Path, *, required: bool) -> dict[str, str]:
    """``uncertain_send_side_codes``: a non-empty mapping of side token -> broker code."""
    key = "uncertain_send_side_codes"
    value = raw.get(key)
    if value is None:
        if required:
            raise FillObserverConfigError(
                f"{path}: uncertain_send_reconcile needs {key} (the broker's own "
                "sll_buy_dvsn_cd for each side token — a side this runtime may not author)"
            )
        return {}
    if not isinstance(value, dict) or not value:
        raise FillObserverConfigError(
            f"{path}: {key!r} must be a non-empty mapping, got {value!r}"
        )
    for side, code in value.items():
        if (
            not isinstance(side, str)
            or not side
            or not isinstance(code, str)
            or not code
        ):
            raise FillObserverConfigError(
                f"{path}: {key!r} maps non-empty strings to non-empty strings, got "
                f"{side!r} -> {code!r}"
            )
    return dict(value)


def _optional_positive_int(raw: dict[str, Any], key: str, path: Path) -> int | None:
    return _positive_int(raw, key, path) if key in raw else None
