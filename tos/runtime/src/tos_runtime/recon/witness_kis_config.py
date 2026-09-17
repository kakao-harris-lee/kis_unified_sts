"""``KisWitnessConfig`` — fail-closed boot config for the real KIS 모의투자 ``BrokerWitness``
(W3 lane, ``docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`` §4 W3).

Mirrors :mod:`tos_runtime.transport.kis_mock.config`'s own fail-closed / host-seal shape
(same style, same rationale) over a **read-only, GET-only** surface — this module has no
``order_cash`` body to validate, so it is considerably smaller: two TR ids
(stock balance + stock daily execution inquiry), one host, no ``field_map``.

**Host seal (mirrors ``kis_mock/config.py:303-354``).** ``endpoint_rest_base`` must
byte-exact match the caller-supplied ``instance_mock_rest_base`` fact and must NOT equal
``instance_real_rest_base`` — exactly the same two-sided check ``kis_mock/config.py``
performs for the order transport. A config value cannot re-point this witness at a live
host, no matter what an operator (or an attacker with write access to the config file)
sets it to.

**TR id shape (mirrors ``kis_mock/config.py``'s ``_validate_tr_id``).** Both TR ids must
be the KIS mock (모의) shape ``^V[A-Z]{3}\\d{4}[A-Z]{1}$`` — measured against the two TR
ids this witness actually uses:

* stock balance inquiry — mock ``VTTC8434R`` (real ``TTTC8434R``) — measured
  ``docs/broker-profiles/evidence/2026-09-11-p02-t3-campaign/P-BAL-20260911T002427Z.json``
  ``measurements.target.tr_id``, and ``shared/kis/client.py:919`` (reference only, not
  imported — firewall-denied).
* stock daily execution inquiry (주식일별주문체결조회) — mock ``VTTC0081R`` (real
  ``TTTC0081R``) — measured
  ``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:1548-1575`` (§ "체결조회로
  독립 확인") and mirrored, with the exact wire params, at
  ``tools/broker_probes/probes_order.py:1079-1150``.

A config naming a ``T``/``S``/``C``-prefixed (real-order) TR id, or any other shape, is
refused at load time — this witness is 모의투자-only by construction (task scope: "A real
KIS 모의투자 witness"), never a live-broker read.

**Asset is structurally ``stock`` only.** The mock server serves no futures balance query
at all (``shared/kis/client.py:1026`` NOTE, reference only) and the real futures account is
never funded (root ``CLAUDE.md`` Non-Negotiable Rules) — there is no futures TR id field on
this config to even mis-populate. :func:`refuse_futures_asset` is the one, explicit,
testable refusal point a caller (or a config extension) must route a futures request
through; it is never bypassed by a per-call scope.

Firewall (RUNTIME scope, R1 — ``tools/tos_firewall_check.py`` SCOPE SPLIT): stdlib
(``dataclasses``, ``pathlib``, ``re``, ``urllib.parse``) + ``pyyaml`` only — no
``tos``/``tos_runtime`` sibling import (mirrors ``kis_mock/config.py``'s own firewall
note: this module has nothing to seal against yet). No ``os.environ``/``os.getenv``
anywhere (TOS-FW-C).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

__all__ = [
    "KisWitnessConfig",
    "KisWitnessConfigError",
    "FuturesAssetRefused",
    "load_kis_witness_config",
    "refuse_futures_asset",
]


class KisWitnessConfigError(Exception):
    """The KIS witness config is missing, malformed, still named-TBD, or names an
    unrecognized/forbidden value — fail-closed at load, never a silent default."""


class FuturesAssetRefused(Exception):
    """Raised by :func:`refuse_futures_asset` — futures is refused outright (module
    docstring): the mock server serves no futures balance query, and the real futures
    account is never funded (root ``CLAUDE.md`` Non-Negotiable Rules)."""


#: The KIS mock (모의) TR id shape (mirrors ``kis_mock/config.py``'s ``_TR_ID_PATTERN``,
#: review F7's citation): 'V' + 3 letters + 4 digits + 1 letter, e.g. ``VTTC8434R``.
#: Case-sensitive — KIS never lower-cases a TR id.
_TR_ID_PATTERN = re.compile(r"^V[A-Z]{3}\d{4}[A-Z]$")

#: Real-order/real-night TR id prefixes this witness must never carry (module docstring;
#: mirrors ``kis_mock/config.py``'s ``_FORBIDDEN_TR_PREFIXES``).
_FORBIDDEN_TR_PREFIXES = ("T", "STTN", "CTF")


def refuse_futures_asset(asset: str) -> None:
    """The one structural refusal point for a futures request (module docstring).

    Args:
        asset: The requested asset class. Only ``"stock"`` is accepted.

    Raises:
        FuturesAssetRefused: ``asset`` is ``"futures"`` (or anything other than
            ``"stock"``) — named reason, never a silent empty result.
    """
    if asset != "stock":
        raise FuturesAssetRefused(
            f"KisWitnessConfig: asset={asset!r} is refused — this witness is stock-only. "
            "The KIS mock server serves no futures balance query "
            "(shared/kis/client.py:1026 NOTE: '모의서버는 선물 잔고조회 미지원', reference "
            "only, not imported here — firewall-denied) and the real futures account is "
            "never funded (root CLAUDE.md Non-Negotiable Rules: real-money futures order "
            "paths are permanently blocked by policy). There is no code path in this "
            "witness that can answer a futures scope."
        )


@dataclass(frozen=True)
class KisWitnessConfig:
    """The fully-valued, fail-closed-loaded KIS 모의투자 witness config (module docstring).

    Every field names a GET-only surface: there is no order-mutation field anywhere on
    this dataclass (contrast ``KisMockTransportConfig``'s ``field_map``/
    ``static_body_fields``, which build an order body).
    """

    endpoint_rest_base: str
    balance_path: str
    balance_tr_id: str
    order_inquiry_path: str
    order_inquiry_tr_id: str
    request_timeout_s: float
    max_pages: int
    allow_plaintext_for_tests: bool


def _require_present(raw: Any, field: str, path: Path) -> Any:
    if not isinstance(raw, dict) or field not in raw:
        raise KisWitnessConfigError(
            f"{path}: KIS witness config missing entry {field!r} — refusing to start"
        )
    value = raw[field]
    if value is None:
        raise KisWitnessConfigError(
            f"{path}: {field!r} is still null (named-TBD) — refusing to start until an "
            "operator attests a concrete value"
        )
    return value


def _require_str(raw: Any, field: str, path: Path) -> str:
    value = _require_present(raw, field, path)
    if not isinstance(value, str) or not value:
        raise KisWitnessConfigError(
            f"{path}: {field!r} must be a non-empty string, got {value!r}"
        )
    return value


def _require_bool(raw: Any, field: str, path: Path) -> bool:
    value = _require_present(raw, field, path)
    if not isinstance(value, bool):
        raise KisWitnessConfigError(f"{path}: {field!r} must be a bool, got {value!r}")
    return value


def _require_positive_float(raw: Any, field: str, path: Path) -> float:
    value = _require_present(raw, field, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KisWitnessConfigError(
            f"{path}: {field!r} must be a number, got {value!r}"
        )
    if value <= 0:
        raise KisWitnessConfigError(f"{path}: {field} must be positive, got {value!r}")
    return float(value)


def _require_positive_int(raw: Any, field: str, path: Path) -> int:
    value = _require_present(raw, field, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise KisWitnessConfigError(f"{path}: {field!r} must be an int, got {value!r}")
    if value <= 0:
        raise KisWitnessConfigError(f"{path}: {field} must be positive, got {value!r}")
    return value


def _validate_tr_id(value: str, field: str, path: Path) -> str:
    for forbidden in _FORBIDDEN_TR_PREFIXES:
        if value.startswith(forbidden):
            raise KisWitnessConfigError(
                f"{path}: {field}={value!r} carries the {forbidden!r} prefix — that is a "
                "real-order (or real-night) TR id convention (module docstring); this "
                "모의투자-only witness admits only 'V'-prefixed TR ids"
            )
    if not _TR_ID_PATTERN.match(value):
        raise KisWitnessConfigError(
            f"{path}: {field}={value!r} does not match the KIS mock TR id shape "
            "('V' + 3 letters + 4 digits + 1 letter, e.g. VTTC8434R — module docstring) "
            "— refusing to start"
        )
    return value


def _validate_endpoint(
    endpoint_rest_base: str,
    *,
    instance_mock_rest_base: str,
    instance_real_rest_base: str,
    allow_plaintext_for_tests: bool,
    path: Path,
) -> None:
    """Mirrors ``kis_mock/config.py:303-354`` exactly (module docstring's "Host seal")."""
    if instance_real_rest_base is None:
        raise KisWitnessConfigError(
            "REAL rest_base must be known (instance_real_rest_base was None) to be "
            "excluded — a caller that cannot state the REAL_PROD host cannot honestly "
            "prove this config excludes it"
        )
    if instance_mock_rest_base == instance_real_rest_base:
        raise KisWitnessConfigError(
            f"instance_mock_rest_base and instance_real_rest_base must differ (both were "
            f"{instance_mock_rest_base!r}) — a caller that cannot distinguish the two "
            "instance facts cannot honestly exclude the real host"
        )
    if endpoint_rest_base == instance_real_rest_base:
        raise KisWitnessConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} equals the INSTANCE "
            "REAL_PROD document's own rest_base — this 모의투자-only witness refuses to "
            "boot against a real host under any config value"
        )
    if endpoint_rest_base != instance_mock_rest_base:
        raise KisWitnessConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} does not byte-exact match "
            f"the INSTANCE MOCK_VTS document's rest_base {instance_mock_rest_base!r} — a "
            "config value cannot invent its own broker host"
        )
    scheme = urlsplit(endpoint_rest_base).scheme
    if scheme == "http":
        if not allow_plaintext_for_tests:
            raise KisWitnessConfigError(
                f"{path}: endpoint_rest_base={endpoint_rest_base!r} uses http:// but "
                "allow_plaintext_for_tests is false — plaintext is a test-only escape "
                "hatch"
            )
    elif scheme != "https":
        raise KisWitnessConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} has unsupported scheme "
            f"{scheme!r} — only http (test-only) and https are supported"
        )


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise KisWitnessConfigError(f"KIS witness config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KisWitnessConfigError(
            f"KIS witness config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise KisWitnessConfigError(
            f"KIS witness config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise KisWitnessConfigError(
            f"KIS witness config file must be a top-level mapping: {path}"
        )
    return raw


def load_kis_witness_config(
    path: Path,
    *,
    instance_mock_rest_base: str,
    instance_real_rest_base: str,
) -> KisWitnessConfig:
    """Load + fail-closed-validate the KIS 모의투자 witness config from ``path``.

    Args:
        path: The config file (shaped like
            ``tos/runtime/config/kis_witness.example.yaml``).
        instance_mock_rest_base: The INSTANCE MOCK_VTS document's own
            ``_kis.endpoints.rest_base`` literal — the one value
            ``endpoint_rest_base`` is allowed to equal.
        instance_real_rest_base: The INSTANCE REAL_PROD document's own ``rest_base`` —
            REQUIRED, and must differ from ``instance_mock_rest_base`` (module
            docstring's "Host seal").

    Returns:
        The fully-valued config.

    Raises:
        KisWitnessConfigError: Any fail-closed check fails — see the module docstring.
    """
    raw = _read_yaml_mapping(path)

    allow_plaintext_for_tests = _require_bool(raw, "allow_plaintext_for_tests", path)
    endpoint_rest_base = _require_str(raw, "endpoint_rest_base", path)
    _validate_endpoint(
        endpoint_rest_base,
        instance_mock_rest_base=instance_mock_rest_base,
        instance_real_rest_base=instance_real_rest_base,
        allow_plaintext_for_tests=allow_plaintext_for_tests,
        path=path,
    )

    balance_path = _require_str(raw, "balance_path", path)
    order_inquiry_path = _require_str(raw, "order_inquiry_path", path)
    balance_tr_id = _validate_tr_id(
        _require_str(raw, "balance_tr_id", path), "balance_tr_id", path
    )
    order_inquiry_tr_id = _validate_tr_id(
        _require_str(raw, "order_inquiry_tr_id", path), "order_inquiry_tr_id", path
    )
    request_timeout_s = _require_positive_float(raw, "request_timeout_s", path)
    max_pages = _require_positive_int(raw, "max_pages", path)

    return KisWitnessConfig(
        endpoint_rest_base=endpoint_rest_base,
        balance_path=balance_path,
        order_inquiry_path=order_inquiry_path,
        balance_tr_id=balance_tr_id,
        order_inquiry_tr_id=order_inquiry_tr_id,
        request_timeout_s=request_timeout_s,
        max_pages=max_pages,
        allow_plaintext_for_tests=allow_plaintext_for_tests,
    )
