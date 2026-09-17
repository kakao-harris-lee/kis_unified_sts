"""``KisQuoteTransportConfig`` — fail-closed boot config for the KIS 모의투자 QUOTE intake (TOS
tick-source wave, W2 lane, plan
``docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`` §4 W2).

Mirrors :mod:`tos_runtime.transport.kis_mock.config`'s own fail-closed idiom over a QUOTE-shaped
document: every field is named-TBD (``null``) in the shipped ``.example.yaml``, and a still-null
or missing required leaf refuses to load, naming the offending key.

**Host seal (same shape as the order transport, decision 5 there).** ``endpoint_rest_base`` must
equal the INSTANCE MOCK_VTS document's own ``rest_base`` literal exactly — this loader takes both
the MOCK and REAL facts as caller-supplied, never reads the broker-capability-profile YAML itself.
This is a STRUCTURAL guard, not documentation: the measured broker behavior
(``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:4348-4361``) is that KIS enforces
environment separation *per TR family*, not *per domain* — "모의 앱키로 실전 도메인 시세를 읽는
구성은 조용히 동작한다" ("a config reading REAL-domain quotes with a MOCK app key works silently").
A config value alone cannot be trusted to keep this transport pointed at MOCK.

**The actual defense is the ALLOWLIST check, not the explicit REAL-match check (independent
review LOW, 2026-09-17).** :func:`_validate_endpoint`'s LAST comparison —
``endpoint_rest_base != instance_mock_rest_base`` — is what refuses ANY non-MOCK value, a REAL
endpoint included: deleting the earlier, explicit ``endpoint_rest_base == instance_real_rest_base``
branch entirely still refuses a REAL endpoint, because it is not MOCK either, and the allowlist
check catches it regardless. That explicit REAL-match branch is kept ONLY for a clearer, more
specific error message when a config names the REAL host BY NAME (it says "equals REAL_PROD's own
rest_base", not the generic "does not match MOCK_VTS") — it is redundant for the refusal itself,
never the sole thing standing between this transport and a real host.

**Quote TR id shape (measured, NOT the order transport's ``V``-prefix rule).** Four independently
observed KIS quotations TR ids —
``FHKST01010100`` (stock current price, ``shared/kis/client.py:600``),
``FHMIF10000000`` (futures/index current price, ``shared/kis/client.py:661``),
``FHPPG04600001``/``FHKST03030200`` (quote TRs the broker profile records as answered for a MOCK
app key even against the REAL domain,
``KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:4351``) — share one shape: ``FH`` + 3 uppercase letters
+ 8 digits, 13 characters total. This is a DIFFERENT TR family from the order transport's
``V[A-Z]{3}\\d{4}[A-Z]`` shape (module docstring there) — applying that rule here would be wrong,
not merely stricter, since a quote TR id is never ``V``-prefixed at all. ``tr_id`` must match
``^FH[A-Z]{3}\\d{8}$`` exactly (case-sensitive) — refused otherwise, naming the measured shape and
its citations so a future reader can re-verify rather than trust this comment blindly.

**One source of truth for pacing (deliberate omission).** This config carries NO poll-interval /
min-request-spacing field of its own. :class:`~tos_runtime.marketfeed.scheduler.TickScheduler`'s
own ``poll_interval_ms`` (``marketfeed.yaml``) already governs how often ``ObservationIntake.poll``
is ever called at all — a second, independent pacing knob here could disagree with it (one config
saying "every 500ms", the other "every 2s"), and disagreement between two rate governors for the
SAME call site is worse than having only one. ``token_reissue_min_interval_s`` is the one
exception: it governs the TOKEN endpoint specifically, a different call site with its own
independent KIS-side rate limit (N-15's own finding, cited in
:mod:`tos_runtime.transport.kis_mock.token`'s module docstring), not a duplicate of the poll
pacing.

**No ``mode`` field (deliberate, unlike the order transport).** A quote poll is a GET-only read
with no dry-run/live distinction to make — there is no "would-be order" to hold back from the
network the way ``dry_run`` holds back a POST. Every quote poll always reaches the (host-sealed
MOCK) network; refusing to build this intake at all is the fail-closed lever, not a mode flag.

Firewall: stdlib (``dataclasses``, ``pathlib``, ``re``) + ``pyyaml`` only — no
``tos``/``tos_runtime`` sibling import (same reasoning as ``kis_mock/config.py``'s own firewall
note: this module has nothing to seal against yet). No ``os.environ``/``os.getenv`` anywhere
(TOS-FW-C) — every fact here is caller-supplied or file-sourced.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

__all__ = [
    "KisQuoteTransportConfig",
    "KisQuoteTransportConfigError",
    "load_kis_quote_transport_config",
]

#: The exact measured KIS quotations TR id shape (module docstring): ``FH`` + 3 uppercase
#: letters + 8 digits. Distinct from — and never confusable with — the order transport's
#: ``V``-prefixed shape (``kis_mock/config.py``'s ``_TR_ID_PATTERN``).
_QUOTE_TR_ID_PATTERN = re.compile(r"^FH[A-Z]{3}\d{8}$")


class KisQuoteTransportConfigError(Exception):
    """The KIS QUOTE transport config is missing, malformed, still named-TBD, or names an
    unrecognized/forbidden value — fail-closed at load, never a silent default."""


@dataclass(frozen=True)
class KisQuoteTransportConfig:
    """The fully-valued, fail-closed-loaded KIS QUOTE transport config (module docstring).

    Attributes:
        endpoint_rest_base: The host-sealed KIS MOCK REST base (module docstring).
        quote_path: The quotations endpoint's path (e.g.
            ``/uapi/domestic-stock/v1/quotations/inquire-price``).
        token_path: The token endpoint's path (e.g. ``/oauth2/tokenP``).
        tr_id: The KIS quotations TR id — ``FH`` + 3 letters + 8 digits (module docstring).
        instrument: The single instrument this config quotes — MUST equal the instrument string
            :meth:`~tos_runtime.transport.kis_quote.adapter.KisQuoteObservationIntake.poll` is
            called with (checked at poll time, not here — this loader has no independent access
            to what ``marketfeed.yaml`` will pass).
        market_div_code: KIS's own ``FID_COND_MRKT_DIV_CODE`` query value (``"J"`` for stock,
            ``"F"`` for futures/index — ``shared/kis/client.py:602``/``:665``, cited as an
            existing-code shape reference only).
        field_mapping: KIS wire field name -> the ``critical_input_policy.yaml``-admitted
            ``field_key`` it feeds (e.g. ``{"stck_prpr": "last_price"}``). A response field NOT
            named here is dropped by this adapter before it ever reaches
            :class:`~tos_runtime.marketfeed.ports.RawObservation` — never guessed, never passed
            through wholesale (module docstring's own "configured mapping, not hardcoded
            branches" discipline).
        source_id: The ``RawObservation.source_id`` this intake stamps on every observation it
            emits.
        token_reissue_min_interval_s: Forwarded to :class:`~tos_runtime.transport.kis_mock.token
            .KisTokenLifecycle` — the token endpoint's own reissue-rate pacing (module
            docstring's "one source of truth for pacing" note — this is the ONE exception).
        request_timeout_s: The per-request socket timeout, in seconds.
        allow_plaintext_for_tests: Whether an ``http://`` scheme is admitted (test-only escape
            hatch, same discipline as the order transport's own field).
    """

    endpoint_rest_base: str
    quote_path: str
    token_path: str
    tr_id: str
    instrument: str
    market_div_code: str
    field_mapping: Mapping[str, str]
    source_id: str
    token_reissue_min_interval_s: int
    request_timeout_s: float
    allow_plaintext_for_tests: bool


def _require_present(raw: Any, field: str, path: Path) -> Any:
    if not isinstance(raw, dict) or field not in raw:
        raise KisQuoteTransportConfigError(
            f"{path}: KIS QUOTE transport config missing entry {field!r} — refusing to start"
        )
    value = raw[field]
    if value is None:
        raise KisQuoteTransportConfigError(
            f"{path}: {field!r} is still null (named-TBD) — refusing to start until an "
            "operator attests a concrete value"
        )
    return value


def _require_str(raw: Any, field: str, path: Path) -> str:
    value = _require_present(raw, field, path)
    if not isinstance(value, str) or not value:
        raise KisQuoteTransportConfigError(
            f"{path}: {field!r} must be a non-empty string, got {value!r}"
        )
    return value


def _require_int(raw: Any, field: str, path: Path) -> int:
    value = _require_present(raw, field, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise KisQuoteTransportConfigError(
            f"{path}: {field!r} must be an int, got {value!r}"
        )
    return value


def _require_positive_int(raw: Any, field: str, path: Path) -> int:
    value = _require_int(raw, field, path)
    if value <= 0:
        raise KisQuoteTransportConfigError(
            f"{path}: {field} must be positive, got {value!r}"
        )
    return value


def _require_positive_float(raw: Any, field: str, path: Path) -> float:
    value = _require_present(raw, field, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KisQuoteTransportConfigError(
            f"{path}: {field!r} must be a number, got {value!r}"
        )
    result = float(value)
    if result <= 0:
        raise KisQuoteTransportConfigError(
            f"{path}: {field} must be positive, got {result!r}"
        )
    return result


def _require_bool(raw: Any, field: str, path: Path) -> bool:
    value = _require_present(raw, field, path)
    if not isinstance(value, bool):
        raise KisQuoteTransportConfigError(
            f"{path}: {field!r} must be a bool, got {value!r}"
        )
    return value


def _require_field_mapping(raw: Any, path: Path) -> dict[str, str]:
    block = _require_present(raw, "field_mapping", path)
    if not isinstance(block, dict) or not block:
        raise KisQuoteTransportConfigError(
            f"{path}: 'field_mapping' must be a non-empty mapping, got {block!r} — an empty "
            "mapping would admit no field at all, almost certainly a misfill (mirrors "
            "critical_input_policy.yaml's own empty-fields refusal)"
        )
    result: dict[str, str] = {}
    for key, value in block.items():
        if not isinstance(key, str) or not key:
            raise KisQuoteTransportConfigError(
                f"{path}: 'field_mapping' has a non-string or empty KIS wire field key {key!r}"
            )
        if not isinstance(value, str) or not value:
            raise KisQuoteTransportConfigError(
                f"{path}: field_mapping[{key!r}] is still null (named-TBD) or not a non-empty "
                "string — refusing to start until an operator attests a concrete CIP field_key"
            )
        result[key] = value
    return result


def _validate_tr_id(value: str, path: Path) -> str:
    if not _QUOTE_TR_ID_PATTERN.match(value):
        raise KisQuoteTransportConfigError(
            f"{path}: tr_id={value!r} does not match the measured KIS quotations TR id shape "
            "('FH' + 3 letters + 8 digits, e.g. FHKST01010100 — module docstring) — refusing "
            "to start"
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
    """Same host-seal shape as ``kis_mock.config._validate_endpoint`` (module docstring) —
    duplicated, not imported, so this loader stays free of a sibling-package import for a check
    this small; the two must be kept in sync by hand if the seal's shape ever changes.
    """
    if (
        instance_real_rest_base is None
    ):  # runtime guard for a caller ignoring the type hint
        raise KisQuoteTransportConfigError(
            "REAL rest_base must be known (instance_real_rest_base was None) to be excluded — "
            "a caller that cannot state the REAL_PROD host cannot honestly prove this config "
            "excludes it"
        )
    if instance_mock_rest_base == instance_real_rest_base:
        raise KisQuoteTransportConfigError(
            f"instance_mock_rest_base and instance_real_rest_base must differ (both were "
            f"{instance_mock_rest_base!r}) — a caller that cannot distinguish the two instance "
            "facts cannot honestly exclude the real host"
        )
    if endpoint_rest_base == instance_real_rest_base:
        raise KisQuoteTransportConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} equals the INSTANCE REAL_PROD "
            "document's own rest_base — this MOCK-only transport refuses to boot against a "
            "real host under any config value"
        )
    if endpoint_rest_base != instance_mock_rest_base:
        raise KisQuoteTransportConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} does not byte-exact match the "
            f"INSTANCE MOCK_VTS document's rest_base {instance_mock_rest_base!r} — a config "
            "value cannot invent its own broker host"
        )
    scheme = urlsplit(endpoint_rest_base).scheme
    if scheme == "http":
        if not allow_plaintext_for_tests:
            raise KisQuoteTransportConfigError(
                f"{path}: endpoint_rest_base={endpoint_rest_base!r} uses http:// but "
                "allow_plaintext_for_tests is false — plaintext is a test-only escape hatch"
            )
    elif scheme != "https":
        raise KisQuoteTransportConfigError(
            f"{path}: endpoint_rest_base={endpoint_rest_base!r} has unsupported scheme "
            f"{scheme!r} — only http (test-only) and https are supported"
        )


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise KisQuoteTransportConfigError(
            f"KIS QUOTE transport config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KisQuoteTransportConfigError(
            f"KIS QUOTE transport config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise KisQuoteTransportConfigError(
            f"KIS QUOTE transport config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise KisQuoteTransportConfigError(
            f"KIS QUOTE transport config file must be a top-level mapping: {path}"
        )
    return raw


def load_kis_quote_transport_config(
    path: Path,
    *,
    instance_mock_rest_base: str,
    instance_real_rest_base: str,
) -> KisQuoteTransportConfig:
    """Load + fail-closed-validate the KIS QUOTE transport config from ``path``.

    Args:
        path: The config file (shaped like
            ``tos/runtime/config/kis_quote.example.yaml``).
        instance_mock_rest_base: The INSTANCE MOCK_VTS document's own ``rest_base`` literal —
            the one value ``endpoint_rest_base`` is allowed to equal.
        instance_real_rest_base: The INSTANCE REAL_PROD document's own ``rest_base`` — REQUIRED,
            and must differ from ``instance_mock_rest_base`` (module docstring's host-seal note).

    Returns:
        The fully-valued config.

    Raises:
        KisQuoteTransportConfigError: The file is missing/unreadable/not valid YAML/not a
            mapping, an entry is absent or still ``null`` (named-TBD), ``tr_id`` does not match
            the measured quotations TR id shape, ``endpoint_rest_base`` does not match the MOCK
            instance (or matches the REAL one), or ``field_mapping`` is empty/malformed.
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

    quote_path = _require_str(raw, "quote_path", path)
    token_path = _require_str(raw, "token_path", path)
    tr_id = _validate_tr_id(_require_str(raw, "tr_id", path), path)
    instrument = _require_str(raw, "instrument", path)
    market_div_code = _require_str(raw, "market_div_code", path)
    field_mapping = _require_field_mapping(raw, path)
    source_id = _require_str(raw, "source_id", path)
    token_reissue_min_interval_s = _require_positive_int(
        raw, "token_reissue_min_interval_s", path
    )
    request_timeout_s = _require_positive_float(raw, "request_timeout_s", path)

    return KisQuoteTransportConfig(
        endpoint_rest_base=endpoint_rest_base,
        quote_path=quote_path,
        token_path=token_path,
        tr_id=tr_id,
        instrument=instrument,
        market_div_code=market_div_code,
        field_mapping=field_mapping,
        source_id=source_id,
        token_reissue_min_interval_s=token_reissue_min_interval_s,
        request_timeout_s=request_timeout_s,
        allow_plaintext_for_tests=allow_plaintext_for_tests,
    )
