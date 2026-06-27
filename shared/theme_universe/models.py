"""JSON-friendly theme candidate payload contracts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

THEME_CANDIDATE_STATES = ("active", "watch", "quarantine")
_STATE_SET = set(THEME_CANDIDATE_STATES)


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value if item is not None)
    return (str(value),)


def _coerce_state(value: Any) -> str:
    state = str(value or "watch")
    return state if state in _STATE_SET else "watch"


@dataclass(frozen=True)
class ThemeCandidate:
    """Serializable theme-screening candidate for downstream paper-only consumers."""

    code: str
    name: str = ""
    theme: str = ""
    state: str = "watch"
    leader_score: float = 0.0
    risk_flags: tuple[str, ...] = ()
    market_signal_count: int = 0
    catalyst_signal_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ThemeCandidate:
        """Parse a candidate from a JSON-like mapping."""
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        return cls(
            code=str(payload.get("code", "") or ""),
            name=str(payload.get("name", "") or ""),
            theme=str(payload.get("theme", "") or ""),
            state=_coerce_state(payload.get("state")),
            leader_score=round(_as_float(payload.get("leader_score")), 6),
            risk_flags=_as_str_tuple(payload.get("risk_flags")),
            market_signal_count=_as_int(payload.get("market_signal_count")),
            catalyst_signal_count=_as_int(payload.get("catalyst_signal_count")),
            metadata=dict(metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary with stable field names."""
        return {
            "code": str(self.code),
            "name": str(self.name),
            "theme": str(self.theme),
            "state": _coerce_state(self.state),
            "leader_score": round(_as_float(self.leader_score), 6),
            "risk_flags": list(self.risk_flags),
            "market_signal_count": int(self.market_signal_count),
            "catalyst_signal_count": int(self.catalyst_signal_count),
            "metadata": dict(self.metadata),
        }


def parse_theme_candidates(
    payload: Mapping[str, Any] | Iterable[Mapping[str, Any] | ThemeCandidate],
) -> list[ThemeCandidate]:
    """Parse theme candidates from a full payload or an iterable of candidate maps."""
    if isinstance(payload, Mapping):
        raw_candidates = payload.get("candidates")
        if raw_candidates is None and "code" in payload:
            raw_candidates = [payload]
        elif raw_candidates is None:
            raw_candidates = []
    else:
        raw_candidates = payload

    candidates: list[ThemeCandidate] = []
    for item in raw_candidates:
        if isinstance(item, ThemeCandidate):
            candidates.append(item)
        elif isinstance(item, Mapping):
            candidates.append(ThemeCandidate.from_mapping(item))
        else:
            raise TypeError(f"unsupported theme candidate payload: {type(item)!r}")
    return candidates


def build_theme_targets_payload(
    candidates: Iterable[ThemeCandidate | Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the shared latest-payload shape for theme target publication."""
    parsed = parse_theme_candidates(candidates)
    candidate_payloads = [candidate.to_dict() for candidate in parsed]
    state_counts = dict.fromkeys(THEME_CANDIDATE_STATES, 0)
    for candidate in candidate_payloads:
        state_counts[_coerce_state(candidate["state"])] += 1

    active_codes = [
        candidate["code"]
        for candidate in candidate_payloads
        if candidate["state"] == "active" and candidate["code"]
    ]
    themes = sorted(
        {candidate["theme"] for candidate in candidate_payloads if candidate["theme"]}
    )
    return {
        "codes": active_codes,
        "candidates": candidate_payloads,
        "themes": themes,
        "state_counts": state_counts,
        "metadata": {
            "candidate_count": len(candidate_payloads),
            "active_count": state_counts["active"],
        },
    }
