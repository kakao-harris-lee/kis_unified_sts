"""Release-admission runtime config loader (design #40 §5 order 6, lane R item 4).

Loads ``tos/runtime/config/release.example.yaml`` (or an operator-approved
copy). Phase 2 has no live SCI (ADR-002-029) admission-decision runtime —
no real source/build/dependency/signer/registry scanning exists yet — so
every fact :func:`~tos_runtime.release.admission.release_admission` needs
beyond the runtime's own :class:`~tos.workload.RuntimeIdentity` is an
**operator-approved static snapshot**, not a computed one. A ``null`` value
here is named-TBD and refuses service construction (fail-closed), matching
the slice plan §3 item 4's own instruction: "config YAML with
null=named-TBD ⇒ refuse to start".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.sci import AdmissionResult, ReleaseRestriction, SupplyChainScope

__all__ = [
    "ReleaseAdmissionConfig",
    "ReleaseAdmissionConfigError",
    "load_release_config",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_ADMISSION_RESULT_BY_NAME: dict[str, AdmissionResult] = {
    member.value: member for member in AdmissionResult
}


class ReleaseAdmissionConfigError(Exception):
    """Raised when the release-admission config is missing, malformed, or
    carries an unfilled (missing/null) required key — fail-closed at load."""


@dataclass(frozen=True)
class ReleaseAdmissionConfig:
    """Fully-valued release-admission runtime configuration.

    ``restriction`` is populated only when ``restriction_present`` is
    ``True``; ``restriction_present``/``restriction_state_resolved`` feed
    :func:`~tos.sci.predicates.software_deployment_ok_verdict`'s own
    negative/positive-polarity gates directly.
    """

    expected_code_digest: str
    admission_result: AdmissionResult
    restriction_state_resolved: bool
    restriction_present: bool
    restriction: ReleaseRestriction | None


def _require_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ReleaseAdmissionConfigError(
            f"release-admission config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleaseAdmissionConfigError(
            f"release-admission config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ReleaseAdmissionConfigError(
            f"release-admission config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise ReleaseAdmissionConfigError(
            f"release-admission config file must be a top-level mapping: {path} "
            f"(got {type(raw)!r})"
        )
    return raw


def _require_str(raw: dict[str, Any], key: str) -> str:
    if key not in raw:
        raise ReleaseAdmissionConfigError(
            f"release-admission config missing required key: {key!r}"
        )
    value = raw[key]
    if value is None:
        raise ReleaseAdmissionConfigError(
            "release-admission config has an unfilled (named-TBD) key — "
            f"fail-closed at startup until an operator fills it: {key!r}"
        )
    if not isinstance(value, str) or not value.strip():
        raise ReleaseAdmissionConfigError(
            f"release-admission config key {key!r} must be a non-blank string "
            f"(got {value!r})"
        )
    return value


def _require_bool(raw: dict[str, Any], key: str) -> bool:
    if key not in raw:
        raise ReleaseAdmissionConfigError(
            f"release-admission config missing required key: {key!r}"
        )
    value = raw[key]
    if value is None:
        raise ReleaseAdmissionConfigError(
            "release-admission config has an unfilled (named-TBD) key — "
            f"fail-closed at startup until an operator fills it: {key!r}"
        )
    if not isinstance(value, bool):
        raise ReleaseAdmissionConfigError(
            f"release-admission config key {key!r} must be a bool (got {value!r})"
        )
    return value


def _resolve_admission_result(raw: dict[str, Any]) -> AdmissionResult:
    value = _require_str(raw, "admission_result")
    resolved = _ADMISSION_RESULT_BY_NAME.get(value)
    if resolved is None:
        raise ReleaseAdmissionConfigError(
            "release-admission config key 'admission_result' must be one of "
            f"{sorted(_ADMISSION_RESULT_BY_NAME)} (got {value!r})"
        )
    return resolved


def _resolve_restriction(
    raw: dict[str, Any], *, present: bool
) -> ReleaseRestriction | None:
    if not present:
        return None
    section = raw.get("restriction")
    if not isinstance(section, dict):
        raise ReleaseAdmissionConfigError(
            "release-admission config: 'restriction_present' is true but "
            "'restriction' is not a mapping — fail-closed"
        )
    restriction_id = section.get("restriction_id")
    restriction_generation = section.get("restriction_generation")
    trigger_class = section.get("trigger_class")
    if restriction_id is None or restriction_generation is None:
        raise ReleaseAdmissionConfigError(
            "release-admission config: 'restriction_present' is true but "
            "'restriction.restriction_id'/'restriction_generation' is "
            "unfilled (named-TBD) — fail-closed"
        )
    issued = ReleaseRestriction.issue(
        scheme=_SCHEME,
        restriction_id=restriction_id,
        restriction_generation=restriction_generation,
        restricted_scope=SupplyChainScope(),
        trigger_class=trigger_class,
    )
    assert isinstance(issued, ReleaseRestriction)
    return issued


def load_release_config(path: Path) -> ReleaseAdmissionConfig:
    """Load + validate the release-admission config file, fail-closed.

    Args:
        path: Path to a YAML file shaped like
            ``tos/runtime/config/release.example.yaml``.

    Returns:
        A fully-valued :class:`ReleaseAdmissionConfig`.

    Raises:
        ReleaseAdmissionConfigError: The file is missing/unreadable/not
            valid YAML/not a mapping, a required key is missing or still
            ``null`` (named-TBD), or a value fails its type/enum check.
    """
    raw = _require_mapping(path)
    expected_code_digest = _require_str(raw, "expected_code_digest")
    admission_result = _resolve_admission_result(raw)
    restriction_state_resolved = _require_bool(raw, "restriction_state_resolved")
    restriction_present = _require_bool(raw, "restriction_present")
    restriction = _resolve_restriction(raw, present=restriction_present)
    return ReleaseAdmissionConfig(
        expected_code_digest=expected_code_digest,
        admission_result=admission_result,
        restriction_state_resolved=restriction_state_resolved,
        restriction_present=restriction_present,
        restriction=restriction,
    )
