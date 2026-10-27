"""``fill_observer.yaml`` — the post-ACK fill observer's cadence, bounds, and sealed witness
fields (split out of :mod:`tos_runtime.posttrade.fill_observer` for the module size budget when
issue #950 added the FETCH/APPLY split; unchanged content, re-exported there).

Firewall: stdlib + ``pyyaml`` + ``tos_runtime._named_tbd`` only.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    """The observer's cadence and bounds plus the witness fields it seals (module docstring).

    Attributes:
        witness_fields: The GET-only witness fields (TR ids, paths, ``max_pages``) — validated
            by :func:`~tos_runtime.recon.witness_kis_config.kis_witness_config_from_mapping`
            together with the order transport's own sealed host.
        poll_interval_ms: Minimum spacing between two order-inquiry polls
            (:meth:`KisMockFillObserver.poll_if_due`), on the injected monotonic clock.
        overdue_after_ms: How long an ACKed attempt may show no terminal row before one
            ``FILL_OBSERVER_OVERDUE`` row is recorded (record only — nothing is guessed).
        finality_retry_interval_ms: Minimum spacing between two finality re-runs for one
            attempt whose terminal result is recorded but whose release has not committed.
        prior_day_poll_interval_ms: Minimum spacing between two reads of an unresolved ACK from
            an EARLIER trading day (Codex r2 MEDIUM): it is re-read under its own date until a
            terminal broker result shows — slower than today's cadence, never abandoned.
        poll_deadline_ms: The whole poll's bound, across every date and page it reads (#949
            review HIGH). Once it is past, the observer starts no further read and the witness
            fetches no further page: the read in question is ``WitnessUnavailable`` — recorded,
            fail-closed, retried at the next due poll — never a partial row list. Worst case
            for one poll is therefore this deadline plus the one request already in flight
            (bounded by ``witness_request_timeout_s``), instead of that timeout times every
            page times every date.
        witness_request_timeout_s: Per-GET timeout for the witness this config seals — the
            observer's own bound, deliberately NOT the order path's
            ``kis_mock_transport.yaml::request_timeout_s`` (10 s). #949 review HIGH: the
            observer's read happens inside the session loop's tick-to-tick window, so its worst
            case has to be a number this file states, not one inherited from a path whose
            latency nobody is waiting on. It bounds every GET this witness makes — the
            observer's order inquiry AND the release/recovery reconciliation's balance read,
            which run on the same witness. Since issue #950 the observer's reads run on its
            FETCH thread, not the loop's; this bound still caps how long one FETCH — and a
            shutdown waiting on one — can take.
    """

    witness_fields: dict[str, Any]
    poll_interval_ms: int
    overdue_after_ms: int
    finality_retry_interval_ms: int
    prior_day_poll_interval_ms: int
    poll_deadline_ms: int
    witness_request_timeout_s: float


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
    """Load ``fill_observer.yaml``, fail-closed.

    Raises:
        FillObserverConfigError: The file is absent, not a mapping, misses a key, or carries a
            non-positive bound.
    """
    if not path.is_file():
        raise FillObserverConfigError(f"fill observer config not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise FillObserverConfigError(f"{path}: unreadable ({exc})") from exc
    if not isinstance(raw, dict):
        raise FillObserverConfigError(f"{path}: must be a top-level mapping")
    missing = [key for key in _WITNESS_KEYS if key not in raw]
    if missing:
        raise FillObserverConfigError(f"{path}: missing {missing}")
    for key in _WITNESS_KEYS:
        # The witness config loader re-checks every one of these; refusing the placeholder here
        # names THIS file in the error rather than the witness's.
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
    )
