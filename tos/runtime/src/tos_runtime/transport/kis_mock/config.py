"""``KisMockTransportConfig`` — fail-closed boot config for the KIS MOCK stock transport
(plan ``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md`` §2 결정 1/4/5/9).

Mirrors :mod:`tos_runtime.compose._egress_coordinates`'s own boot-refusal mechanism (same
module's docstring: "every field is a named-TBD ``null``... a still-null field refuses
composition at startup, fail-closed, never a silent default") over a flatter YAML shape, the
same style :mod:`tos_runtime.custody.file_custody`'s manifest loader uses.

**Host seal (decision 5).** ``endpoint_rest_base`` must equal the INSTANCE MOCK_VTS document's
own ``_kis.endpoints.rest_base`` literal *exactly* — the loader takes the INSTANCE's mock and
real ``rest_base`` strings as caller-supplied facts (``instance_mock_rest_base`` /
``instance_real_rest_base``) rather than reading the broker-capability-profile YAML itself
(this package does not import ``docs/`` — that binding is the caller's job, kept out of this
firewalled distribution). A config whose ``endpoint_rest_base`` differs from the MOCK document,
or matches the REAL_PROD document, refuses to load — a config value cannot re-point this
transport at a live host, no matter what an operator (or an attacker with write access to the
config file) sets it to.

**``V``-prefix rule (decision 5, mirrors the runbook's own naming rule).** KIS's own TR-id
convention prefixes every 모의(paper) order TR with ``V`` (``VTTC0011U``/``VTTC0012U``, N-17
memo) and every 실전(real) one with ``T`` (``TTTC0011U``/``TTTC0012U``); futures 야간(night)
real TRs use ``STTN``/``CTF*`` prefixes (``shared/execution/tr_ids.py``, cited by the N-17
collation memo). ``tr_id_buy``/``tr_id_sell`` must start with ``V`` and are refused outright if
they start with ``T``, ``STTN``, or ``CTF`` — a config cannot smuggle a real-order TR id past this
loader by construction.

Firewall: stdlib (``dataclasses``, ``pathlib``, ``urllib.parse``) + ``pyyaml`` only — no
``tos``/``tos_runtime`` sibling import (this module has nothing to seal against yet; the seal
comparison lives in :mod:`tos_runtime.transport.kis_mock.adapter`, which does import ``tos``).
No ``os.environ``/``os.getenv`` anywhere (TOS-FW-C, D1.1 config row — every path/fact here is
caller-supplied or file-sourced, never ambient).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import yaml

__all__ = [
    "DYNAMIC_FIELD_SOURCES",
    "KisMockTransportConfig",
    "KisMockTransportConfigError",
    "load_kis_mock_transport_config",
]

#: The only two boot modes (decision 9). Anything else refuses to load.
_VALID_MODES = ("dry_run", "live")

#: KIS's own TR-id prefix convention (module docstring). ``V`` is the ONLY admitted prefix for
#: this MOCK-only transport; the other three are explicitly real-order/real-night prefixes and
#: are named here so a rejection can say exactly which real-order convention was caught, rather
#: than a bare "must start with V".
_FORBIDDEN_TR_PREFIXES = ("T", "STTN", "CTF")

#: The closed set of per-attempt kernel-side values ``field_map`` may name as a source (adapter
#: module docstring — ``account`` is deliberately ABSENT here: the real KIS account number is a
#: custody-loaded secret, never a sealed authorization coordinate, so it is not a "dynamic field
#: source" in this loader's sense; the adapter reads it from custody directly). A config that
#: names any other source string is refused at load time rather than failing later inside a
#: send.
DYNAMIC_FIELD_SOURCES: frozenset[str] = frozenset(
    {"account", "instrument", "quantity", "price"}
)


class KisMockTransportConfigError(Exception):
    """The KIS MOCK transport config is missing, malformed, still named-TBD, or names an
    unrecognized/forbidden value — fail-closed at load, never a silent default."""


@dataclass(frozen=True)
class KisMockTransportConfig:
    """The fully-valued, fail-closed-loaded KIS MOCK transport config (plan §2 결정 1).

    ``field_map`` keys are per-attempt kernel-side value names drawn from
    :data:`DYNAMIC_FIELD_SOURCES`; values are the KIS wire body field names they populate
    (e.g. ``{"instrument": "PDNO", "quantity": "ORD_QTY"}``). ⚠ **Known T1 gap** (flagged for
    the operator's proposal table, plan §6 확인 지점 2): KIS's ``order_cash`` body has nine
    required fields (N-17 memo); this config's ``field_map`` can only populate the ones with a
    genuine per-attempt kernel-side source (``account`` via custody, ``instrument``,
    ``quantity``, ``price``) — the remaining fields with no per-attempt source at all
    (``ACNT_PRDT_CD``, ``ORD_DVSN``, ``EXCG_ID_DVSN_CD``, ``SLL_TYPE``, ``CNDT_PRIC``) are simply
    not populated by this cut; see the runbook's proposal table for the recommended follow-up
    (widening this config with a small set of per-deployment static literals) rather than this
    loader inventing values that were never sourced from evidence.
    """

    mode: Literal["dry_run", "live"]
    endpoint_rest_base: str
    order_path: str
    token_path: str
    tr_id_buy: str
    tr_id_sell: str
    field_map: Mapping[str, str]
    min_send_interval_ms: int
    token_reissue_min_interval_s: int
    request_timeout_s: float
    allow_plaintext_for_tests: bool


def _require_present(raw: Any, field: str, path: Path) -> Any:
    if not isinstance(raw, dict) or field not in raw:
        raise KisMockTransportConfigError(
            f"{path}: KIS MOCK transport config missing entry {field!r} — refusing to start"
        )
    value = raw[field]
    if value is None:
        raise KisMockTransportConfigError(
            f"{path}: {field!r} is still null (named-TBD) — refusing to start until an "
            "operator attests a concrete value"
        )
    return value


def _require_str(raw: Any, field: str, path: Path) -> str:
    value = _require_present(raw, field, path)
    if not isinstance(value, str) or not value:
        raise KisMockTransportConfigError(
            f"{path}: {field!r} must be a non-empty string, got {value!r}"
        )
    return value


def _require_int(raw: Any, field: str, path: Path) -> int:
    value = _require_present(raw, field, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise KisMockTransportConfigError(
            f"{path}: {field!r} must be an int, got {value!r}"
        )
    return value


def _require_float(raw: Any, field: str, path: Path) -> float:
    value = _require_present(raw, field, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KisMockTransportConfigError(
            f"{path}: {field!r} must be a number, got {value!r}"
        )
    return float(value)


def _require_bool(raw: Any, field: str, path: Path) -> bool:
    value = _require_present(raw, field, path)
    if not isinstance(value, bool):
        raise KisMockTransportConfigError(
            f"{path}: {field!r} must be a bool, got {value!r}"
        )
    return value


def _require_str_mapping(raw: Any, field: str, path: Path) -> dict[str, str]:
    block = _require_present(raw, field, path)
    if not isinstance(block, dict) or not block:
        raise KisMockTransportConfigError(
            f"{path}: {field!r} must be a non-empty mapping, got {block!r}"
        )
    result: dict[str, str] = {}
    for key, value in block.items():
        if not isinstance(key, str) or not key:
            raise KisMockTransportConfigError(
                f"{path}: {field!r} has a non-string or empty key {key!r}"
            )
        if not isinstance(value, str) or not value:
            raise KisMockTransportConfigError(
                f"{path}: {field!r}[{key!r}] is still null (named-TBD), empty, or not a "
                "string — refusing to start until an operator attests a concrete value"
            )
        result[key] = value
    return result


def _validate_tr_id(value: str, field: str, path: Path) -> str:
    if value.startswith("V"):
        return value
    for forbidden in _FORBIDDEN_TR_PREFIXES:
        if value.startswith(forbidden):
            raise KisMockTransportConfigError(
                f"{path}: {field}={value!r} carries the {forbidden!r} prefix — that is a "
                "real-order (or real-night) TR id convention (module docstring); this MOCK-only "
                "transport admits only 'V'-prefixed TR ids"
            )
    raise KisMockTransportConfigError(
        f"{path}: {field}={value!r} must start with 'V' — KIS's own 모의(paper) order TR "
        "convention (N-17 memo); refusing to start"
    )


def _validate_field_map(field_map: dict[str, str], path: Path) -> dict[str, str]:
    unknown = sorted(set(field_map) - DYNAMIC_FIELD_SOURCES)
    if unknown:
        raise KisMockTransportConfigError(
            f"{path}: field_map names unrecognized dynamic source(s) {unknown!r} — only "
            f"{sorted(DYNAMIC_FIELD_SOURCES)!r} are recognized kernel-side values"
        )
    wire_names = list(field_map.values())
    if len(wire_names) != len(set(wire_names)):
        raise KisMockTransportConfigError(
            f"{path}: field_map maps two different sources onto the same KIS wire field name "
            f"{field_map!r} — a body cannot carry the same key twice"
        )
    return field_map


def _validate_endpoint(
    endpoint_rest_base: str,
    *,
    instance_mock_rest_base: str,
    instance_real_rest_base: str | None,
    allow_plaintext_for_tests: bool,
    path: Path,
) -> None:
    if endpoint_rest_base != instance_mock_rest_base:
        raise KisMockTransportConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} does not byte-exact match the "
            f"INSTANCE MOCK_VTS document's rest_base {instance_mock_rest_base!r} — a config "
            "value cannot invent its own broker host (decision 5, one source of truth)"
        )
    if (
        instance_real_rest_base is not None
        and endpoint_rest_base == instance_real_rest_base
    ):
        raise KisMockTransportConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} equals the INSTANCE REAL_PROD "
            "document's own rest_base — this MOCK-only transport refuses to boot against a "
            "real host under any config value (decision 5)"
        )
    scheme = urlsplit(endpoint_rest_base).scheme
    if scheme == "http":
        if not allow_plaintext_for_tests:
            raise KisMockTransportConfigError(
                f"{path}: endpoint_rest_base={endpoint_rest_base!r} uses http:// but "
                "allow_plaintext_for_tests is false — plaintext is a test-only escape hatch"
            )
    elif scheme != "https":
        raise KisMockTransportConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} has unsupported scheme "
            f"{scheme!r} — only http (test-only) and https are supported"
        )


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    """Read + parse ``path`` as a top-level YAML mapping — the first three fail-closed checks
    every loader in this codebase performs before touching any individual field (mirrors
    :mod:`tos_runtime.compose._egress_coordinates`'s own loader shape)."""
    if not path.is_file():
        raise KisMockTransportConfigError(
            f"KIS MOCK transport config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KisMockTransportConfigError(
            f"KIS MOCK transport config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise KisMockTransportConfigError(
            f"KIS MOCK transport config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise KisMockTransportConfigError(
            f"KIS MOCK transport config file must be a top-level mapping: {path}"
        )
    return raw


def _require_positive_int(raw: Any, field: str, path: Path) -> int:
    value = _require_int(raw, field, path)
    if value <= 0:
        raise KisMockTransportConfigError(
            f"{path}: {field} must be positive, got {value!r}"
        )
    return value


def _require_positive_float(raw: Any, field: str, path: Path) -> float:
    value = _require_float(raw, field, path)
    if value <= 0:
        raise KisMockTransportConfigError(
            f"{path}: {field} must be positive, got {value!r}"
        )
    return value


def load_kis_mock_transport_config(
    path: Path,
    *,
    instance_mock_rest_base: str,
    instance_real_rest_base: str | None,
) -> KisMockTransportConfig:
    """Load + fail-closed-validate the KIS MOCK transport config from ``path``.

    Args:
        path: The config file (shaped like
            ``tos/runtime/config/kis_mock_transport.example.yaml``).
        instance_mock_rest_base: The INSTANCE MOCK_VTS document's own
            ``_kis.endpoints.rest_base`` literal — the one value ``endpoint_rest_base`` is
            allowed to equal.
        instance_real_rest_base: The INSTANCE REAL_PROD document's own ``rest_base``, or
            ``None`` if unavailable — the one value ``endpoint_rest_base`` is never allowed to
            equal, when known.

    Returns:
        The fully-valued config.

    Raises:
        KisMockTransportConfigError: The file is missing/unreadable/not valid YAML/not a
            mapping, an entry is absent or still ``null`` (named-TBD), a TR id carries a
            real-order prefix, ``endpoint_rest_base`` does not match the MOCK instance (or
            matches the REAL one), or ``field_map`` names an unrecognized dynamic source.
    """
    raw = _read_yaml_mapping(path)

    mode = _require_str(raw, "mode", path)
    if mode not in _VALID_MODES:
        raise KisMockTransportConfigError(
            f"{path}: mode={mode!r} must be one of {_VALID_MODES!r}"
        )

    allow_plaintext_for_tests = _require_bool(raw, "allow_plaintext_for_tests", path)
    endpoint_rest_base = _require_str(raw, "endpoint_rest_base", path)
    _validate_endpoint(
        endpoint_rest_base,
        instance_mock_rest_base=instance_mock_rest_base,
        instance_real_rest_base=instance_real_rest_base,
        allow_plaintext_for_tests=allow_plaintext_for_tests,
        path=path,
    )

    order_path = _require_str(raw, "order_path", path)
    token_path = _require_str(raw, "token_path", path)
    tr_id_buy = _validate_tr_id(_require_str(raw, "tr_id_buy", path), "tr_id_buy", path)
    tr_id_sell = _validate_tr_id(
        _require_str(raw, "tr_id_sell", path), "tr_id_sell", path
    )
    field_map = _validate_field_map(_require_str_mapping(raw, "field_map", path), path)

    min_send_interval_ms = _require_positive_int(raw, "min_send_interval_ms", path)
    token_reissue_min_interval_s = _require_positive_int(
        raw, "token_reissue_min_interval_s", path
    )
    request_timeout_s = _require_positive_float(raw, "request_timeout_s", path)

    return KisMockTransportConfig(
        mode=mode,  # type: ignore[arg-type]  # narrowed by the membership check above
        endpoint_rest_base=endpoint_rest_base,
        order_path=order_path,
        token_path=token_path,
        tr_id_buy=tr_id_buy,
        tr_id_sell=tr_id_sell,
        field_map=field_map,
        min_send_interval_ms=min_send_interval_ms,
        token_reissue_min_interval_s=token_reissue_min_interval_s,
        request_timeout_s=request_timeout_s,
        allow_plaintext_for_tests=allow_plaintext_for_tests,
    )
