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

**``V``-prefix + shape rule (decision 5, review disposition F7).** KIS's own TR-id convention
prefixes every 모의(paper) order TR with ``V`` (``VTTC0011U``/``VTTC0012U``, N-17 memo) and every
실전(real) one with ``T`` (``TTTC0011U``/``TTTC0012U``); futures 야간(night) real TRs use
``STTN``/``CTF*`` prefixes (``shared/execution/tr_ids.py``, cited by the N-17 collation memo).
Every one of these observed ids is exactly nine characters, shaped 1 letter + 3 letters + 4
digits + 1 letter (``VTTC0012U`` = ``V``+``TTC``+``0012``+``U``; ``STTN1101U`` =
``S``+``TTN``+``1101``+``U``; ``CTFO6118R`` = ``C``+``TFO``+``6118``+``R`` — verified against
the official SDK oracle, ``open-trading-api/examples_llm/domestic_stock/order_cash/
order_cash.py:103-118``, and the N-17 memo's further real-order/real-night observations).
``tr_id_buy``/``tr_id_sell`` must match ``^V[A-Z]{3}\\d{4}[A-Z]$`` exactly (case-sensitive, no
normalization) — refused outright (with a specific message) if they start with ``T``, ``STTN``,
or ``CTF``, and refused (generically, "TR id shape") for any other deviation from that nine-
character shape. A config cannot smuggle a real-order TR id, nor a malformed one, past this
loader by construction.

**``static_body_fields`` + the nine-field coverage check (review disposition F1).** KIS's
``order_cash`` body needs exactly nine fields (N-17 memo). Four are per-attempt kernel facts
named through ``field_map``; the other five (``ACNT_PRDT_CD``, ``ORD_DVSN``,
``EXCG_ID_DVSN_CD``, ``SLL_TYPE``, ``CNDT_PRIC``) are per-deployment constants with no sealed
source at all, named through ``static_body_fields`` (KIS wire field name -> literal value). The
union of ``field_map``'s values and ``static_body_fields``'s keys must equal exactly this
module's own copy of :data:`~tos_runtime.transport.kis_mock.codec.KIS_ORDER_CASH_WIRE_FIELDS`
(duplicated here, not imported, to keep this module stdlib-only — see the Firewall note below;
``test_config.py::test_a_fully_valued_config_loads`` is the drift canary) — a config missing or
adding a field refuses to load, before this transport ever reaches the network.

**``mode: live`` is refused unless the caller attests ``codec_bound=True`` (review disposition
F1/F6, T2 lane A follow-up).** By DEFAULT, the compose context resolver binds
``EgressRequestRecord.request_bytes_digest``/``SendBoundaryContext.capsule_egress_request_digest``
to :class:`~tos_runtime.compose._request_digest.CapsuleStandInDigest` — a documented STAND-IN
(:mod:`tos_runtime.compose._egress_coordinates` module docstring, :mod:`tos_runtime.compose.
_request_digest` module docstring), never a hash of real KIS wire bytes — so a live send's own
digest check (:mod:`tos_runtime.transport.kis_mock.adapter`) would deterministically mismatch
every attempt under that default wiring, regardless of how correct this transport is. T2 lane A
landed the seam that closes this gap (:class:`~tos_runtime.compose._request_digest.
KisWireCodecDigest`, built over :meth:`~tos_runtime.transport.kis_mock.codec.KisOrderWireCodec.
encode_fields` — see ``codec.py``'s own module docstring), but binding it into the DEFAULT
compose wiring is a later lane's job (compose ``--transport kis-mock``). So this loader still
refuses ``mode: live`` UNLESS the caller explicitly passes ``codec_bound=True`` to
:func:`load_kis_mock_transport_config` — an attestation that the compose root the caller is
about to run actually wired ``KisWireCodecDigest`` (never inferred, never a config-file field:
the config file cannot see its own compose wiring, so this is a caller-supplied fact, exactly
like ``instance_mock_rest_base``/``instance_real_rest_base`` below). The default,
``codec_bound=False``, preserves T1's unconditional refusal exactly.

Firewall: stdlib (``dataclasses``, ``pathlib``, ``re``, ``urllib.parse``) + ``pyyaml`` only — no
``tos``/``tos_runtime`` sibling import (this module has nothing to seal against yet; the seal
comparison lives in :mod:`tos_runtime.transport.kis_mock.adapter`, which does import ``tos``, and
the shared wire codec lives in :mod:`tos_runtime.transport.kis_mock.codec`). No
``os.environ``/``os.getenv`` anywhere (TOS-FW-C, D1.1 config row — every path/fact here is
caller-supplied or file-sourced, never ambient).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import yaml

__all__ = [
    "DYNAMIC_FIELD_SOURCES",
    "KIS_ORDER_CASH_WIRE_FIELDS",
    "KisMockTransportConfig",
    "KisMockTransportConfigError",
    "load_kis_mock_transport_config",
]

#: The only two boot modes the dataclass's type admits (decision 9); the loader below refuses
#: ``live`` unconditionally regardless (module docstring "mode: live is unconditionally
#: refused").
_VALID_MODES = ("dry_run", "live")

#: KIS's own TR-id prefix convention (module docstring). ``V`` is the ONLY admitted prefix for
#: this MOCK-only transport; the other three are explicitly real-order/real-night prefixes and
#: are named here so a rejection can say exactly which real-order convention was caught, rather
#: than a bare shape-mismatch message.
_FORBIDDEN_TR_PREFIXES = ("T", "STTN", "CTF")

#: The exact KIS mock order TR id shape (review F7 — module docstring's citation): 'V' + 3
#: letters + 4 digits + 1 letter, e.g. ``VTTC0012U``. Case-sensitive — KIS never lower-cases a
#: TR id, so this pattern does not either.
_TR_ID_PATTERN = re.compile(r"^V[A-Z]{3}\d{4}[A-Z]$")

#: The closed set of per-attempt kernel-side values ``field_map`` may name as a source (review
#: F2 — ``account`` reads the SEALED outbound coordinate ``SendSeal.account``, never a
#: custody-loaded value; see :mod:`tos_runtime.transport.kis_mock.codec`'s own module docstring
#: for the full account-sourcing rationale). A config that names any other source string is
#: refused at load time rather than failing later inside a send.
DYNAMIC_FIELD_SOURCES: frozenset[str] = frozenset(
    {"account", "instrument", "quantity", "price"}
)

#: This module's own copy of :data:`tos_runtime.transport.kis_mock.codec.KIS_ORDER_CASH_WIRE_FIELDS`
#: — duplicated, not imported, so this loader stays stdlib-only (module docstring). Keep the two
#: literals in sync; ``test_config.py::test_a_fully_valued_config_loads`` is the drift canary.
KIS_ORDER_CASH_WIRE_FIELDS: frozenset[str] = frozenset(
    {
        "CANO",
        "ACNT_PRDT_CD",
        "PDNO",
        "ORD_DVSN",
        "ORD_QTY",
        "ORD_UNPR",
        "EXCG_ID_DVSN_CD",
        "SLL_TYPE",
        "CNDT_PRIC",
    }
)


class KisMockTransportConfigError(Exception):
    """The KIS MOCK transport config is missing, malformed, still named-TBD, or names an
    unrecognized/forbidden value — fail-closed at load, never a silent default."""


@dataclass(frozen=True)
class KisMockTransportConfig:
    """The fully-valued, fail-closed-loaded KIS MOCK transport config (plan §2 결정 1; review
    disposition F1).

    ``field_map`` keys are per-attempt kernel-side value names drawn from
    :data:`DYNAMIC_FIELD_SOURCES`; values are the KIS wire body field names they populate
    (e.g. ``{"instrument": "PDNO", "quantity": "ORD_QTY"}``). ``static_body_fields`` covers the
    remaining KIS ``order_cash`` fields that have no per-attempt kernel source at all
    (``ACNT_PRDT_CD``, ``ORD_DVSN``, ``EXCG_ID_DVSN_CD``, ``SLL_TYPE``, ``CNDT_PRIC`` —
    per-deployment constants, KIS wire field name -> literal value). Together the two must cover
    exactly :data:`KIS_ORDER_CASH_WIRE_FIELDS` — see the module docstring's "nine-field coverage
    check".
    """

    mode: Literal["dry_run", "live"]
    endpoint_rest_base: str
    order_path: str
    token_path: str
    tr_id_buy: str
    tr_id_sell: str
    field_map: Mapping[str, str]
    static_body_fields: Mapping[str, str]
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


def _require_str_mapping(
    raw: Any, field: str, path: Path, *, allow_empty_value: bool = False
) -> dict[str, str]:
    """Require ``raw[field]`` to be a non-empty mapping of non-empty string keys to string
    values.

    Args:
        allow_empty_value: When ``False`` (``field_map`` — a KIS wire field name can never be
            empty), an empty-string value is refused exactly like ``null``. When ``True``
            (``static_body_fields`` — KIS's own ``SLL_TYPE``/``CNDT_PRIC`` are legitimately
            ``""`` per the official SDK's own default, ``order_cash.py``'s ``sll_type: str =
            ""``), only ``None`` (named-TBD) is refused; an explicit empty string is a
            concrete, attested value, not a placeholder.
    """
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
        if value is None or not isinstance(value, str):
            raise KisMockTransportConfigError(
                f"{path}: {field!r}[{key!r}] is still null (named-TBD) or not a string — "
                "refusing to start until an operator attests a concrete value"
            )
        if not value and not allow_empty_value:
            raise KisMockTransportConfigError(
                f"{path}: {field!r}[{key!r}] is empty — refusing to start until an operator "
                "attests a concrete value"
            )
        result[key] = value
    return result


def _validate_tr_id(value: str, field: str, path: Path) -> str:
    for forbidden in _FORBIDDEN_TR_PREFIXES:
        if value.startswith(forbidden):
            raise KisMockTransportConfigError(
                f"{path}: {field}={value!r} carries the {forbidden!r} prefix — that is a "
                "real-order (or real-night) TR id convention (module docstring); this MOCK-only "
                "transport admits only 'V'-prefixed TR ids"
            )
    if not _TR_ID_PATTERN.match(value):
        raise KisMockTransportConfigError(
            f"{path}: {field}={value!r} does not match the KIS mock order TR id shape "
            "('V' + 3 letters + 4 digits + 1 letter, e.g. VTTC0012U — module docstring, "
            "review F7) — refusing to start"
        )
    return value


def _validate_field_map_and_static_fields(
    field_map: dict[str, str], static_body_fields: dict[str, str], path: Path
) -> tuple[dict[str, str], dict[str, str]]:
    """(review F1) The two configs together must cover exactly the nine KIS wire fields."""
    unknown = sorted(set(field_map) - DYNAMIC_FIELD_SOURCES)
    if unknown:
        raise KisMockTransportConfigError(
            f"{path}: field_map names unrecognized dynamic source(s) {unknown!r} — only "
            f"{sorted(DYNAMIC_FIELD_SOURCES)!r} are recognized kernel-side values"
        )
    combined = list(field_map.values()) + list(static_body_fields.keys())
    if len(combined) != len(set(combined)):
        raise KisMockTransportConfigError(
            f"{path}: field_map and static_body_fields map two different sources onto the "
            f"same KIS wire field name (field_map={field_map!r}, "
            f"static_body_fields={static_body_fields!r}) — a body cannot carry the same key "
            "twice"
        )
    present = frozenset(combined)
    if present != KIS_ORDER_CASH_WIRE_FIELDS:
        missing = sorted(KIS_ORDER_CASH_WIRE_FIELDS - present)
        unexpected = sorted(present - KIS_ORDER_CASH_WIRE_FIELDS)
        raise KisMockTransportConfigError(
            f"{path}: field_map + static_body_fields do not cover exactly the nine KIS "
            f"order_cash fields (N-17 memo) — missing={missing!r} unexpected={unexpected!r}"
        )
    return field_map, static_body_fields


def _validate_endpoint(
    endpoint_rest_base: str,
    *,
    instance_mock_rest_base: str,
    instance_real_rest_base: str,
    allow_plaintext_for_tests: bool,
    path: Path,
) -> None:
    if (
        instance_real_rest_base is None
    ):  # runtime guard for a caller ignoring the type hint
        raise KisMockTransportConfigError(
            "REAL rest_base must be known (instance_real_rest_base was None) to be excluded — "
            "a caller that cannot state the REAL_PROD host cannot honestly prove this config "
            "excludes it (review F3)"
        )
    if instance_mock_rest_base == instance_real_rest_base:
        raise KisMockTransportConfigError(
            f"instance_mock_rest_base and instance_real_rest_base must differ (both were "
            f"{instance_mock_rest_base!r}) — a caller that cannot distinguish the two instance "
            "facts cannot honestly exclude the real host (review F3)"
        )
    # The REAL-match check runs BEFORE the mock-match check (review F3 fix): with
    # instance_mock_rest_base != instance_real_rest_base already established above, checking
    # "does not match mock" first would make this branch unreachable whenever endpoint DOES
    # match mock (the only way to reach a later check in this function at all) — an endpoint
    # cannot equal both when the two instance facts differ, so ordering real-match first is
    # what keeps this branch reachable in the first place.
    if endpoint_rest_base == instance_real_rest_base:
        raise KisMockTransportConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} equals the INSTANCE REAL_PROD "
            "document's own rest_base — this MOCK-only transport refuses to boot against a "
            "real host under any config value (decision 5)"
        )
    if endpoint_rest_base != instance_mock_rest_base:
        raise KisMockTransportConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} does not byte-exact match the "
            f"INSTANCE MOCK_VTS document's rest_base {instance_mock_rest_base!r} — a config "
            "value cannot invent its own broker host (decision 5, one source of truth)"
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
    instance_real_rest_base: str,
    codec_bound: bool = False,
) -> KisMockTransportConfig:
    """Load + fail-closed-validate the KIS MOCK transport config from ``path``.

    Args:
        path: The config file (shaped like
            ``tos/runtime/config/kis_mock_transport.example.yaml``).
        instance_mock_rest_base: The INSTANCE MOCK_VTS document's own
            ``_kis.endpoints.rest_base`` literal — the one value ``endpoint_rest_base`` is
            allowed to equal.
        instance_real_rest_base: The INSTANCE REAL_PROD document's own ``rest_base`` — REQUIRED
            (review F3: a caller that cannot state this cannot honestly exclude it), and must
            differ from ``instance_mock_rest_base``.
        codec_bound: The caller's own attestation that the compose root about to run this
            config actually wired :class:`~tos_runtime.compose._request_digest.KisWireCodecDigest`
            as its ``request_bytes_digest_source`` (T2 lane A — module docstring). ``False``
            (the default) preserves the unconditional ``mode: live`` refusal; only an explicit
            ``True`` admits ``mode: live`` past this check.

    Returns:
        The fully-valued config.

    Raises:
        KisMockTransportConfigError: The file is missing/unreadable/not valid YAML/not a
            mapping, an entry is absent or still ``null`` (named-TBD), ``mode`` is ``"live"``
            and ``codec_bound`` is not ``True`` (module docstring), a TR id carries a real-order
            prefix or does not match the mock TR id shape, ``endpoint_rest_base`` does not match
            the MOCK instance (or matches the REAL one), ``instance_real_rest_base`` is ``None``
            or equals ``instance_mock_rest_base``, or ``field_map``/``static_body_fields`` name
            an unrecognized source or do not cover exactly the nine KIS wire fields.
    """
    raw = _read_yaml_mapping(path)

    mode = _require_str(raw, "mode", path)
    if mode not in _VALID_MODES:
        raise KisMockTransportConfigError(
            f"{path}: mode={mode!r} must be one of {_VALID_MODES!r}"
        )
    if mode == "live" and codec_bound is not True:
        raise KisMockTransportConfigError(
            "live mode requires the T2 seal-codec binding (plan §4 T2) — the compose root "
            "must wire KisWireCodecDigest and pass codec_bound=True to attest it; dry_run "
            "only otherwise (review disposition F1/F6 — see this module's own docstring)"
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
    field_map, static_body_fields = _validate_field_map_and_static_fields(
        _require_str_mapping(raw, "field_map", path),
        _require_str_mapping(raw, "static_body_fields", path, allow_empty_value=True),
        path,
    )

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
        static_body_fields=static_body_fields,
        min_send_interval_ms=min_send_interval_ms,
        token_reissue_min_interval_s=token_reissue_min_interval_s,
        request_timeout_s=request_timeout_s,
        allow_plaintext_for_tests=allow_plaintext_for_tests,
    )
