"""Shared harness for the KIS Broker Capability Profile measurement probes.

These probes exist to satisfy Phase-0 gate **P0-2** ("broker-specific bounds are
MEASURED, not guessed" — ``docs/plans/2026-07-29-tos-phase0-p02-execution-plan.md``
§1 T2). Every probe produces a JSON evidence artifact that is the *only*
admissible origin for

* a ``value_ms`` in ``tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml``
  (Bounds-Approver gate), and
* a field value + ``evidence_refs`` entry in
  ``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml``.

Nothing in this package writes to those files. Probes measure; humans approve.

Safety model (enforced in code, not by convention)
--------------------------------------------------
1. **Mock-only order emission.** Any probe that can cause an order mutation must
   pass ``assert_mock_host()`` *and* ``assert_mock_trading_tr()``. The real host
   ``openapi.koreainvestment.com`` and every non-``V``-prefixed trading TR are
   rejected with :class:`SafetyViolation` before a socket is opened.
2. **Read-only real-token probes.** N-16/N-18 need a REAL token. They go through
   :func:`assert_read_only_call`, a three-way allowlist (method **and** TR id
   **and** URL path). There is no POST code path in the real-token probe module.
3. **Dry-run by default.** Probes declared ``requires_confirm`` in
   :mod:`tools.broker_probes.registry` refuse to touch the broker without
   ``--confirm``; without it they print the exact request they *would* send.
4. **Secrets never leave env.** App key/secret are read from environment only
   (``KIS_APP_KEY``/``KIS_APP_SECRET`` and the asset-specific variants) and are
   redacted from every result artifact. Account numbers are masked and carried
   as a salt-free SHA-256 fingerprint so results stay correlatable.
5. **Private token cache.** Probes default to their own token-cache directory so
   an invalidate-and-reissue probe (N-15/P-15) can never delete the token file a
   running paper worker depends on (``shared/kis/auth.py:396-405`` unlinks it).

Statistical convention
----------------------
The Verification-Profile bound keys these probes feed carry
``semantics: hard_maximum`` (e.g. ``B_external_activity_detect``, VP-002:221-223)
or ``semantics: broker_specific`` (``B_broker_query_consistency`` VP-002:752-754,
``B_final_quantity_proof`` :716-718, ``B_late_fill_observation`` :725-727,
``B_protective_request_complete`` :743-745, ``B_rate_limit_recovery`` :761-763).
A hard maximum is **not** a percentile. :func:`summarize_latencies` therefore
reports the full distribution for diagnostics but derives its
``recommended_bound_ms`` candidate from ``max observed x (1 + margin)``. p95/p99
are recorded for shape only and must never be proposed as the bound.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Repo import bootstrap (probes are run as `python -m tools.broker_probes.run`
# from the repo root, but also tolerate direct script invocation).
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Environment constants — mirrored from shared/kis/auth.py:143-148 (KISAuthConfig
# .base_url). Duplicated as *assertions*, not as configuration: the harness must
# be able to reject a host even if config is wrong.
# ---------------------------------------------------------------------------
MOCK_HOST = "openapivts.koreainvestment.com"
REAL_HOST = "openapi.koreainvestment.com"
MOCK_BASE_URL = f"https://{MOCK_HOST}:29443"
REAL_BASE_URL = f"https://{REAL_HOST}:9443"

ENV_MOCK = "MOCK_VTS"
ENV_REAL = "REAL_PROD"
ENV_NONE = "NONE"

# Observed TR-id convention (config/kis/tr_ids.yaml + shared/execution/tr_ids.py:30-51):
#   mock trading TRs are V-prefixed (VTTC0802U, VTTO1101U, VTTO5201R ...)
#   real trading TRs are T/S/C-prefixed (TTTC0802U, STTN1101U, CTFO6118R ...)
# This is a *secondary* guard; the authoritative gate is the host check.
_MOCK_TRADING_TR_PREFIX = "V"
_REAL_TRADING_TR_PREFIXES = ("T", "S", "C")

# Keys redacted from every persisted artifact and every log line.
_SECRET_KEYS = {
    "appkey",
    "appsecret",
    "app_key",
    "app_secret",
    "secretkey",
    "authorization",
    "access_token",
    "token",
    "approval_key",
    "grant_type",
}
_ACCOUNT_KEYS = {"cano", "acnt_prdt_cd", "account_no", "kis_account_no"}


class ProbeError(RuntimeError):
    """A probe could not run (missing precondition, bad argument)."""


class SafetyViolation(ProbeError):
    """A probe attempted something the safety model forbids. Never caught."""


# ---------------------------------------------------------------------------
# Safety guards
# ---------------------------------------------------------------------------


def assert_mock_host(url: str) -> None:
    """Reject any URL that is not the KIS mock (모의투자) REST host.

    This is the primary structural guard for every order-emitting probe: a probe
    physically cannot reach ``openapi.koreainvestment.com`` through this harness.
    """
    host = urlparse(url).hostname or ""
    if host != MOCK_HOST:
        raise SafetyViolation(
            f"order-capable probe refused: host {host!r} is not the mock host "
            f"{MOCK_HOST!r} (url={url!r}). Probes that mutate orders are "
            "mock-only by construction (P0-2 execution plan §1 T2)."
        )


def assert_mock_trading_tr(tr_id: str) -> None:
    """Reject a trading TR id that is not a mock (``V``-prefixed) TR."""
    tr = (tr_id or "").strip().upper()
    if not tr:
        raise SafetyViolation("empty tr_id passed to a trading call")
    if tr.startswith(_MOCK_TRADING_TR_PREFIX):
        return
    hint = ""
    if tr.startswith(_REAL_TRADING_TR_PREFIXES):
        hint = (
            " This looks like a REAL-investment trading TR "
            "(config/kis/tr_ids.yaml: real = TTT*/STTN*, mock = VTT*)."
        )
    raise SafetyViolation(f"trading TR {tr!r} is not a mock TR.{hint}")


def assert_no_live_futures_config() -> None:
    """Refuse to run order probes while ``config/futures_live.yaml::enabled`` is true.

    Defence in depth: an order probe must never coexist with an armed live
    futures path (``shared/execution/live_mode_guard.py``).
    """
    path = _REPO_ROOT / "config" / "futures_live.yaml"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if re.fullmatch(r"enabled:\s*(true|True|yes|1)", line):
            raise SafetyViolation(
                "config/futures_live.yaml::enabled is true — refusing to run an "
                "order-capable probe while the live futures path is armed."
            )


@dataclass(frozen=True)
class ReadOnlyCall:
    """One entry of the real-token read-only allowlist."""

    tr_id: str
    path: str
    description: str


def assert_read_only_call(
    method: str, url: str, tr_id: str, allowlist: tuple[ReadOnlyCall, ...]
) -> None:
    """Three-way allowlist gate for REAL-token probes (N-16, N-18).

    A call is admitted only when the HTTP method is GET **and** the TR id is on
    the allowlist **and** the URL path matches that same allowlist entry. This
    makes an order mutation structurally unreachable from a real-token probe
    even if a URL or TR id is passed in from the command line.
    """
    if method.upper() != "GET":
        raise SafetyViolation(
            f"real-token probes are read-only; method {method!r} is refused"
        )
    path = urlparse(url).path
    for entry in allowlist:
        if entry.tr_id == tr_id and entry.path == path:
            return
    raise SafetyViolation(
        f"real-token call (tr_id={tr_id!r}, path={path!r}) is not on the "
        "read-only allowlist. Add it to the probe's ALLOWLIST with an explicit "
        "justification, or run the call under N-17 spec cross-check instead."
    )


# ---------------------------------------------------------------------------
# Redaction / masking
# ---------------------------------------------------------------------------


def mask_account(account_no: str) -> str:
    """Mask an account number for display: ``12******90``."""
    digits = "".join(ch for ch in (account_no or "") if ch.isdigit())
    if len(digits) < 6:
        return "*" * len(digits)
    return f"{digits[:2]}{'*' * (len(digits) - 4)}{digits[-2:]}"


def account_fingerprint(account_no: str) -> str:
    """Stable non-reversible correlator for an account across result files."""
    digits = "".join(ch for ch in (account_no or "") if ch.isdigit())
    if not digits:
        return ""
    return hashlib.sha256(digits.encode()).hexdigest()[:12]


def secret_fingerprint(secret: str) -> str:
    """Stable non-reversible correlator for an app key. NEVER the key itself.

    Design §4.2 makes "is this probe's app key the same one the resident paper
    session uses?" a PRECONDITION, because a shared key can hit the 1-minute
    token-reissue limit (N-15). PR #881 had to answer it from a host file and a
    line number, which a reviewer cannot verify and which the runbook warns
    against as an anchor style. Recording the fingerprint in the artifact makes
    the comparison re-checkable from the evidence alone.

    Twelve hex characters of SHA-256, the same width
    :func:`account_fingerprint` uses, so the two read alike in an artifact. An
    empty secret yields ``""`` rather than the digest of the empty string: a
    fingerprint for a key that does not exist would be a phantom.
    """
    if not secret:
        return ""
    return hashlib.sha256(secret.encode()).hexdigest()[:12]


def redact(obj: Any) -> Any:
    """Recursively redact secrets and mask account fields in a payload."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            lowered = str(key).lower()
            if lowered in _SECRET_KEYS:
                out[key] = "***REDACTED***"
            elif lowered in _ACCOUNT_KEYS:
                out[key] = mask_account(str(value))
            else:
                out[key] = redact(value)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact(item) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Credentials / configuration
# ---------------------------------------------------------------------------


@dataclass
class ProbeCredentials:
    """KIS credentials resolved from the environment (never from a file)."""

    app_key: str
    app_secret: str
    account_no: str
    is_real: bool
    asset: str

    @property
    def base_url(self) -> str:
        return REAL_BASE_URL if self.is_real else MOCK_BASE_URL

    @property
    def cano(self) -> str:
        return self.account_no[:8]

    @property
    def acnt_prdt_cd(self) -> str:
        return self.account_no[8:10]

    def describe(self) -> dict[str, Any]:
        return {
            "environment": ENV_REAL if self.is_real else ENV_MOCK,
            "base_url": self.base_url,
            "asset": self.asset,
            "app_key_present": bool(self.app_key),
            "app_secret_present": bool(self.app_secret),
            "app_key_fingerprint": secret_fingerprint(self.app_key),
            "account_masked": mask_account(self.account_no),
            "account_fingerprint": account_fingerprint(self.account_no),
        }


def resolve_credentials(asset: str, *, is_real: bool) -> ProbeCredentials:
    """Read credentials from env with asset-specific precedence.

    Mirrors ``shared/kis/client.py:204-251`` (``_resolve_account_no``): the
    asset-specific variable wins; the legacy single-account variable is *not*
    consulted here at all (probes must never cross-route stock/futures).
    """
    asset = asset.lower()
    if asset not in {"stock", "futures"}:
        raise ProbeError(f"unknown asset {asset!r} (expected 'stock' or 'futures')")

    prefix = "KIS_STOCK" if asset == "stock" else "KIS_FUTURES"
    app_key = (
        os.getenv(f"{prefix}_APP_KEY", "").strip()
        or os.getenv("KIS_APP_KEY", "").strip()
    )
    app_secret = (
        os.getenv(f"{prefix}_APP_SECRET", "").strip()
        or os.getenv("KIS_APP_SECRET", "").strip()
    )
    account = "".join(
        ch for ch in os.getenv(f"{prefix}_ACCOUNT_NO", "").strip() if ch.isdigit()
    )

    if not app_key or not app_secret:
        raise ProbeError(
            f"{prefix}_APP_KEY / {prefix}_APP_SECRET (or KIS_APP_KEY / "
            "KIS_APP_SECRET) must be exported. Probes read secrets from the "
            "environment only — never pass them on the command line."
        )
    return ProbeCredentials(
        app_key=app_key,
        app_secret=app_secret,
        account_no=account,
        is_real=is_real,
        asset=asset,
    )


def require_account(creds: ProbeCredentials) -> None:
    if len(creds.account_no) != 10:
        raise ProbeError(
            f"a 10-digit {creds.asset} account number is required for this probe "
            f"(got {len(creds.account_no)} digits). Export "
            f"KIS_{creds.asset.upper()}_ACCOUNT_NO."
        )


def probe_token_cache_dir(explicit: str | None) -> Path:
    """Return the token-cache directory a probe may safely write to.

    Default is ``tools/broker_probes/results/.token_cache`` — *not* the runtime
    ``.cache`` directory. ``KISAuthManager.invalidate()`` unlinks the cache file
    (``shared/kis/auth.py:396-405``); pointing a probe at the shared cache would
    yank the token out from under running paper workers.
    """
    if explicit:
        return Path(explicit).expanduser().resolve()
    return results_dir() / ".token_cache"


def build_auth_config(creds: ProbeCredentials, token_cache_dir: Path) -> Any:
    """Build a ``KISAuthConfig`` bound to the probe-private token cache.

    REUSE: ``shared.kis.auth.KISAuthConfig`` owns the real/mock base-URL split
    and the token cache file naming, so probes inherit the exact runtime
    semantics they are supposed to be measuring.

    The directory is ASSET-scoped before handing it to ``KISAuthConfig``:
    the runtime names the token file ``.kis_token_{real|mock}`` with no
    app-key discrimination (``shared/kis/auth.py::token_cache_path``), so
    stock and futures credentials given the same directory would share one
    bearer-token file. The 2026-07-31 session ran a stock and a futures mock
    probe in parallel and escaped only by timing (latent-risk register,
    campaign README). Scoping here covers every probe module because this is
    the single construction site for probe auth configs.
    """
    from shared.kis.auth import KISAuthConfig

    scoped_dir = token_cache_dir / creds.asset
    scoped_dir.mkdir(parents=True, exist_ok=True)
    return KISAuthConfig(
        app_key=creds.app_key,
        app_secret=creds.app_secret,
        is_real=creds.is_real,
        token_cache_dir=str(scoped_dir),
    )


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def http_json(
    session: Any,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> tuple[int, dict[str, Any], float, str]:
    """Issue one request and return ``(status, parsed, elapsed_ms, raw_text)``.

    Deliberately **not** routed through ``retry_once_on_token_expiry``
    (``shared/kis/auth.py:64-104``) or the executor's rate limiter. Those wrappers
    are part of what the probes measure (Q-IDEMP-2, Q-RATE-1 in the KIS draft
    §5); wrapping the measurement in them would confound the observation.
    """
    started = time.monotonic()
    response = session.request(
        method.upper(),
        url,
        headers=headers,
        params=params,
        json=json_body,
        timeout=timeout,
    )
    elapsed_ms = (time.monotonic() - started) * 1000.0
    text = response.text
    try:
        parsed = response.json()
    except ValueError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {"output": parsed}
    return int(response.status_code), parsed, elapsed_ms, text


def is_rate_limited(status: int, parsed: dict[str, Any], text: str) -> bool:
    """Detect a broker-side rate-limit rejection.

    ``EGW00201`` is the code the runtime already treats as throttling
    (``shared/kis/client.py:333``, ``:461``, ``:982`` apply a backoff penalty on
    it); HTTP 429 is the transport-level signal.
    """
    if status == 429:
        return True
    blob = f"{parsed.get('msg_cd', '')} {parsed.get('msg1', '')} {text}"
    return "EGW00201" in blob


# ---------------------------------------------------------------------------
# Transient-error policy — ONE copy, shared by every probe that polls
# ---------------------------------------------------------------------------
#
# A broker call can fail for a reason that is NOT attributable to this harness's
# own call rate, and such a failure is worth exactly ONE retry one interval
# later. Two campaigns measured the cost of not having that rule:
#
# * 2026-09-30 P-CA (000660 cash dividend): four attempts, four stops, zero
#   cash-leg observations — two transport read timeouts, one ``EGW00215``
#   ledger throttle, one runner guard defect. Fixed for P-CA in #825.
# * 2026-09-28 P-8 (new 모의 futures account): trial 2 of 5 died mid-poll on a
#   ``ConnectionError`` that escaped the probe entirely (``run.py`` rc 5), and
#   the runner's STOP rule counted it as a broker rejection — "오류 1건(브로커
#   거부 포함)" — so trials 3, 4 and 5 never ran. The transport recovered
#   within seconds; the cleanup cancel issued right afterwards succeeded.
#
# The "stop at once, never retry" rule those fell under was written for
# 2026-09-17, whose cause WAS our own pacing (``EGW00201``). That rule is an
# account-protection device and stays exactly as it is
# (:func:`is_rate_limited`); only the two kinds below buy a retry.
#
# This block lives in ``common.py`` rather than in each probe module because
# the policy had already drifted once while there were two copies of it: an
# answer carrying BOTH a 429 and ``EGW00215`` bought a retry on one path and
# stopped the run at once on the other (#825 independent review F4).

#: ``retry_evidence.not_retried_because`` — why a transient bought no retry.
#: Two different facts: the broker failed twice, or it failed once after the
#: caller's window had already closed. The second says nothing about the
#: link's health, and a reader counting "unhealthy" transients must not add
#: them together.
REFUSED_SECOND_CONSECUTIVE = "second_consecutive_transient"
REFUSED_WINDOW_CLOSED = "window_already_closed"
#: A call that is never retried at all, whatever it answers — an order POST,
#: or a one-off lookup whose repeat would only move the clock. It does not go
#: through :func:`retry_once`, so without a third value its record would carry
#: a bare ``retried: false`` and a harvester separating the two above would
#: meet a kind it cannot classify and lump it with the unhealthy ones.
REFUSED_SINGLE_SHOT = "single_shot_call"

#: The two transient sub-kinds, as they appear in ``measurements.retries`` and
#: in every ``retry_evidence`` record.
TRANSIENT_TRANSPORT = "transport"
TRANSIENT_LEDGER_THROTTLE = "ledger_throttle"

#: Status strings :func:`classify_answer` returns. Prefixed so a caller can test
#: for "transient" without enumerating the kinds, and carried as plain strings
#: rather than as an extra tuple element so that existing call signatures and
#: the tests pinned to them keep their arity.
STATUS_TRANSIENT = "TRANSIENT"
STATUS_TRANSIENT_TRANSPORT = f"{STATUS_TRANSIENT}:{TRANSIENT_TRANSPORT}"
STATUS_TRANSIENT_LEDGER_THROTTLE = f"{STATUS_TRANSIENT}:{TRANSIENT_LEDGER_THROTTLE}"
STATUS_RATE_LIMITED = "RATE_LIMITED"

_TRANSIENT_KINDS: dict[str, str] = {
    STATUS_TRANSIENT_TRANSPORT: TRANSIENT_TRANSPORT,
    STATUS_TRANSIENT_LEDGER_THROTTLE: TRANSIENT_LEDGER_THROTTLE,
}

#: 원장에서 허용 가능한 초당 거래건수를 초과하였습니다 — the LEDGER-side throttle,
#: which the mock server answers with HTTP 500 and ``rt_cd='1'``
#: (``P-CA-20260930T015946Z.json`` poll #14, verbatim). It is NOT ``EGW00201``:
#: :func:`is_rate_limited` never sees it, so before #825 it fell through to the
#: caller's rejection arm and stopped the run on the spot.
LEDGER_THROTTLE_MSG_CD = "EGW00215"


def is_ledger_throttled(parsed: dict[str, Any]) -> bool:
    """``msg_cd`` is exactly :data:`LEDGER_THROTTLE_MSG_CD`.

    Field-exact, deliberately not the substring sweep over
    ``msg_cd``/``msg1``/raw body that :func:`is_rate_limited` does for
    ``EGW00201``: the ledger throttle is worth a retry, so a body that merely
    MENTIONS the code (an operator note echoed back, a future envelope that
    quotes it) must not buy one.
    """
    return str(parsed.get("msg_cd") or "").strip() == LEDGER_THROTTLE_MSG_CD


def transport_transient_types() -> tuple[type[BaseException], ...]:
    """The exception types the probe transports actually raise for a timeout or
    a failed connection — and ONLY those.

    The line is "no intact answer arrived, and our call rate is not why". Both
    :func:`http_json` and ``probes_ca._get`` raise from TWO places, and both are
    in the set:

    * ``session.request`` — ``Timeout`` (covers ``ReadTimeout``, which the
      2026-09-30 P-CA trials 3 and 4 died on, and ``ConnectTimeout``) and
      ``ConnectionError`` (covers ``SSLError``, ``ProxyError``, and the
      ``RemoteDisconnected`` form the 2026-09-28 P-8 trial 2 died on).
    * ``response.text`` — the body is streamed, so a connection cut or a corrupt
      encoding surfaces only when the body is READ, as ``ChunkedEncodingError``
      (a chunked body cut before its terminating chunk) or
      ``ContentDecodingError`` (a gzip body that will not decode). Both mean a
      truncated transfer, which is the same failure as a read timeout arriving a
      few bytes later; neither is a misconfiguration.

    Everything else ``requests`` can raise — ``TooManyRedirects``,
    ``InvalidURL``, ``MissingSchema``, ``URLRequired`` — is a defect in the
    probe or its configuration. Retrying one produces the identical failure
    twice and hides it behind a doubled stop reason, so those still surface as a
    failed run.

    Imported lazily for the same reason the probe modules import ``requests``
    lazily: ``--list``/``--dry-run`` and the registry import them and must not
    pay for (or require) the HTTP stack.
    """
    import requests

    return (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
        requests.exceptions.ContentDecodingError,
    )


#: Anything from ``?`` to the next whitespace in a transport exception message.
#: ``requests``' ``ConnectionError`` renders the URL it failed on IN FULL —
#: "Max retries exceeded with url: /uapi/...?CANO=12345678&ACNT_PRDT_CD=01..." —
#: and these artifacts are committed under ``docs/broker-profiles/evidence/``.
#: :func:`redact` keys on field NAMES and cannot reach inside a raw string leaf,
#: and :func:`call_evidence`'s excerpt cap only bounds the length, so without
#: this the account number would reach the corpus through the one field that
#: carries a broker string verbatim. Over-redaction is the safe direction: the
#: diagnosis a reader needs is the exception CLASS and the timeout value, both
#: of which sit before the ``?``.
_QUERY_STRING_IN_MESSAGE = re.compile(r"\?\S*")


def transport_excerpt(exc: BaseException) -> str:
    """One transport exception rendered for the artifact, query string removed."""
    return _QUERY_STRING_IN_MESSAGE.sub("?<redacted>", f"{type(exc).__name__}: {exc}")


def transient_kind(status: str | None) -> str | None:
    """``"transport"``/``"ledger_throttle"`` for a transient status, else ``None``."""
    return _TRANSIENT_KINDS.get(status or "")


def classify_answer(http_status: int, parsed: dict[str, Any], text: str) -> str | None:
    """The ONLY copy of the retry/no-retry precedence, for an answer that ARRIVED.

    Returns :data:`STATUS_RATE_LIMITED`, :data:`STATUS_TRANSIENT_LEDGER_THROTTLE`,
    or ``None`` when the answer came back intact and the CALLER has to interpret
    it (``rt_cd``, pagination, rows). A call that raised instead of answering is
    :data:`STATUS_TRANSIENT_TRANSPORT`, which the caller assigns around its own
    transport (the two transports differ; the precedence does not).

    The ORDER is the policy:

    1. no answer at all ⇒ transient (retry once) — the caller's ``except``;
    2. :func:`is_rate_limited` — HTTP 429 or ``EGW00201`` ⇒ WE called too fast,
       the 2026-09-17 cause; stop, never retry;
    3. ``EGW00215`` ⇒ the LEDGER-side throttle, not our rate ⇒ transient.

    2 before 3 is load-bearing: a body can carry both signals, and the
    account-protection rule has to win.
    """
    if is_rate_limited(http_status, parsed, text):
        return STATUS_RATE_LIMITED
    if is_ledger_throttled(parsed):
        return STATUS_TRANSIENT_LEDGER_THROTTLE
    return None


#: Cap on the verbatim broker body carried by a FAILED call's evidence record.
#: The excerpt is GATED first (:func:`call_evidence`), and the gate is PAYLOAD-
#: BASED and FAIL-CLOSED: the body is recorded only when the call both failed
#: (``rt_cd != '0'``) AND carries no ``output1``/``output2``. Asking only "did
#: the broker say success?" recorded the body on every OTHER answer, so a body
#: the probe MISCLASSIFIES still reached the artifact — ``rt_cd`` absent or
#: ``null``, or ``rt_cd`` as the JSON number ``0`` (``str(0 or '')`` is ``''``,
#: not ``'0'``, because ``0`` is falsy), each wrote holdings plus the raw
#: ``ctx_area_*`` cursors into a committed artifact. Keying on the payload
#: instead is safe in BOTH directions: a body carrying rows is never diagnostic
#: (it is the success page, not the signal that stopped the run), and the
#: failures worth recording — HTTP 429, ``EGW00201``, ``APBK0919``, an HTML
#: gateway page — carry no ``output1``/``output2`` at all. Verified against the
#: committed corpus: EVERY non-empty ``raw_excerpt`` under
#: ``docs/broker-profiles/evidence/`` is a bare ``rt_cd``/``msg_cd``/``msg1`` or
#: ``error_code`` envelope, none with a non-empty ``output1``/``output2``.
#: 300 chars is the cap the sibling probes already use
#: (``probes_balance.py:749``, ``probes_real.py:232,315,389,490``).
BODY_EXCERPT_MAX_CHARS = 300


def rt_cd_of(parsed: dict[str, Any]) -> str:
    """``rt_cd`` as a comparable string, or ``""`` when the body carries none.

    The ONE reader, because the obvious spelling is wrong in a way that only
    shows up on one input: ``str(parsed.get("rt_cd") or "")`` turns the JSON
    NUMBER ``0`` into ``""`` — ``0`` is falsy — so a successful body reads as
    a failed one. ``call_evidence``'s payload gate was written around that
    trap; every other ``rt_cd`` comparison has to use the same reader or the
    trap simply moves.
    """
    raw = parsed.get("rt_cd")
    return "" if raw is None else str(raw).strip()


def call_evidence(
    *, status_kind: str, http_status: int, parsed: dict[str, Any], text: str
) -> dict[str, Any]:
    """Verbatim broker evidence for one failed call, for the artifact.

    :func:`is_rate_limited` fires on EITHER HTTP 429 OR ``EGW00201`` in the body,
    so a bare "rate-limited" string cannot be diagnosed after the fact; this
    record carries both signals plus the rejection envelope (2026-09-17
    incident).

    The gate is the point: a SUCCESSFUL body carries rows, and on the balance
    surface that means holdings (``pdno``, ``pchs_avg_pric``, ``evlu_amt``), the
    account cash total (``dnca_tot_amt``) and the raw
    ``ctx_area_fk100``/``ctx_area_nk100`` cursors — and these artifacts are
    committed under ``docs/broker-profiles/evidence/``. It fails closed on the
    PAYLOAD rather than trusting ``rt_cd`` alone, because a body the probe
    MISCLASSIFIES (``rt_cd`` absent/``null``, or the JSON number ``0``) is
    exactly the body an ``rt_cd``-only gate lets through
    (:data:`BODY_EXCERPT_MAX_CHARS`).
    """
    rt_cd = rt_cd_of(parsed)
    carries_payload = any(bool(parsed.get(k)) for k in ("output1", "output2"))
    return {
        "status_kind": status_kind,
        "http_status": http_status,
        "rt_cd": parsed.get("rt_cd"),
        "msg_cd": parsed.get("msg_cd"),
        "msg1": parsed.get("msg1"),
        "body_excerpt": (
            ""
            if rt_cd == "0" or carries_payload
            else (text or "")[:BODY_EXCERPT_MAX_CHARS]
        ),
    }


def retry_evidence(
    *,
    phase: str,
    kind: str,
    status: str,
    http_status: int,
    parsed: dict[str, Any],
    text: str,
    poll_index: int | None,
    retried: bool,
    not_retried_because: str | None = None,
) -> dict[str, Any]:
    """The record written for EVERY transient, retried or not.

    Same shape and the same payload gate as :func:`call_evidence`, plus which
    phase it happened in, which poll (when there was one), and whether a retry
    followed. A run must be reconstructible down to "when, and how many times",
    which is the whole reason the retry is capped at one — and ``retried: false``
    is how a refusal is told apart from a retry — and ``not_retried_because``
    says WHICH refusal it was. The two are different facts and were
    indistinguishable while both only carried ``retried: false``: the second
    consecutive transient means the broker failed twice, while
    :data:`REFUSED_WINDOW_CLOSED` means it failed once and the window had
    already run out, so the trial spent its whole window and this transient is
    not evidence of an unhealthy link.

    The key this lands under is ``retry_evidence``, never a phase-specific one:
    several phases can write one, and a harvester filtering on a poll-shaped key
    would have miscounted the others (#825 independent review F8).
    """
    record: dict[str, Any] = {
        "phase": phase,
        "transient_kind": kind,
        "retried": retried,
    }
    if not retried and not_retried_because is not None:
        record["not_retried_because"] = not_retried_because
    if poll_index is not None:
        record["poll_index"] = poll_index
    record.update(
        call_evidence(
            status_kind=status, http_status=http_status, parsed=parsed, text=text
        )
    )
    return record


@dataclass(frozen=True)
class Outcome:
    """One broker call, already run through the transient classification.

    ``kind`` is the status the retry policy reads: ``None`` means "the caller
    interprets this" (a walk's own OK/REJECTED/CAPPED verdicts reuse the field,
    since they are equally "not transient"). ``payload`` carries whatever the
    phase needs beyond the envelope — ``(qty, cash)`` for a balance read, the
    parsed rows for an open-order listing, nothing for a bare lookup.
    """

    kind: str | None
    http_status: int
    parsed: dict[str, Any]
    text: str
    payload: Any = None


class Pacer:
    """Minimum-interval gate in front of a probe client's only socket.

    Contract: :meth:`wait` blocks until the next call is permitted and returns
    the instant it was released. The first call is never delayed — an empty
    pacer has no previous call to be too close to.

    The released instant is the *only* honest t0 for a latency measurement. A
    timestamp taken before the gate would include the pacing sleep and charge it
    to the broker; on a 1.1 s pace that inflates every accept-to-visible sample
    by roughly 1100 ms, which for a ``hard_maximum`` bound propagates straight
    into an over-wide approved value.
    """

    def __init__(self, interval_s: float) -> None:
        self.interval_s = max(0.0, float(interval_s))
        self._next_allowed_at: float | None = None

    def wait(self) -> float:
        """Block out the remainder of the interval; return the release instant."""
        now = time.monotonic()
        if self._next_allowed_at is not None and now < self._next_allowed_at:
            # Sleep the REMAINDER only. A fixed per-call sleep would also charge
            # the probe for time already spent in the previous request.
            time.sleep(self._next_allowed_at - now)
            now = time.monotonic()
        self._next_allowed_at = now + self.interval_s
        return now

    def defer(self, seconds: float) -> None:
        """Push the next allowed call ``seconds`` out from NOW.

        The transient-error retry (:func:`retry_once`) has to wait a WHOLE
        interval before trying again, and ``wait()`` alone does not give that:
        the failed attempt already armed the gap before it went out, so by the
        time a 20 s read timeout surfaces, ``wait()`` owes only the remainder
        (10 s of a 30 s interval — the 2026-09-30 P-CA trial-3 shape). Deferring
        from NOW makes the following ``wait()`` sleep the full interval, which is
        where the wait lives — this method never sleeps itself, so there is
        exactly one sleep site per call.

        It never SHORTENS an outstanding gap: a longer pending interval wins.
        """
        target = time.monotonic() + max(0.0, float(seconds))
        if self._next_allowed_at is None or target > self._next_allowed_at:
            self._next_allowed_at = target


class Retries:
    """Counts the retries a run spent, and keeps ``measurements.retries``
    current at EVERY exit path.

    A run that retried is labelled exactly as before — the retry changes no
    verdict. What it changes is the timing a reader reconstructs from the
    artifact, by up to one interval per retry, so the count has to be in the
    artifact whatever happens: it is published on construction (all zeros, so
    "no retries" is stated rather than inferred from a missing key) and
    republished on every increment, because a phase can stop the run long before
    the probe's own finalisation would get to write anything.
    """

    def __init__(self, run: ProbeRun) -> None:
        self._run = run
        self._counts: dict[str, int] = {
            TRANSIENT_TRANSPORT: 0,
            TRANSIENT_LEDGER_THROTTLE: 0,
        }
        self._publish()

    def bump(self, kind: str) -> None:
        self._counts[kind] = self._counts.get(kind, 0) + 1
        self._publish()

    def as_dict(self) -> dict[str, int]:
        return dict(self._counts)

    def _publish(self) -> None:
        self._run.measure("retries", self.as_dict())


def record_retry(
    run: ProbeRun, retries: Retries
) -> Callable[[dict[str, Any], str], None]:
    """The standard ``on_transient``: observe EVERY transient, count the RETRIES.

    The two differ, and conflating them is how a counter stops meaning anything:
    ``measurements.retries`` answers "how much extra waiting did this run
    spend", which a transient that bought no retry did not.
    """

    def _record(evidence: dict[str, Any], kind: str) -> None:
        run.observe(retry_evidence=evidence)
        if evidence.get("retried"):
            retries.bump(kind)

    return _record


def retry_once(
    call: Callable[[], Outcome],
    on_transient: Callable[[dict[str, Any], str], None],
    pacer: Pacer,
    *,
    wait_s: float,
    phase: str,
    poll_index_base: int | None = None,
    can_retry: Callable[[], bool] | None = None,
) -> tuple[Outcome, int, bool]:
    """Run ``call``; on a transient outcome wait one whole interval and run it
    exactly once more. Returns ``(outcome, attempts, retried)`` — ``attempts`` is
    1 or 2, and ``retried`` says whether a second attempt was actually made.

    ``can_retry`` lets a caller REFUSE the retry for a reason of its own. A poll
    loop passes its window deadline: a transient surfacing after the window has
    elapsed must not buy another interval of waiting plus another call, or a
    verdict ends up resting on a poll made outside the window it claims to cover
    (#825 independent review F5 — window 60 s, poll at 58 s, 20 s timeout, 30 s
    defer, retry at 108 s).

    The caller sees a transient ``kind`` back only when BOTH attempts were
    transient — the "second consecutive transient" stop.

    Exactly one retry, exactly one interval apart (:meth:`Pacer.defer`). No
    backoff, no tunable attempt count: each of the 2026-09-30 P-CA stops and the
    2026-09-28 P-8 stop was a SINGLE failure, so one retry would have carried all
    of them, and every extra knob blurs the "when, and how many times" the
    artifact has to answer.

    ``on_transient`` receives ``(evidence, kind)`` for EVERY transient — the
    retried one and the one that ends the phase — so the phase decides where that
    goes. Recording both is the point: a transient that bought no retry is
    exactly the case a reader needs to see.

    ``call`` must be safe to run twice. Every site that uses this is a GET; an
    order POST is not retried here, because a resent submit is the duplicate-order
    hazard P-2 exists to measure.
    """
    attempts = 0
    while True:
        attempts += 1
        outcome = call()
        kind = transient_kind(outcome.kind)
        if kind is None:
            return outcome, attempts, attempts > 1
        # Asked BEFORE the attempt count is consulted, so the reason recorded
        # is the one that actually applied: a window that has closed is not a
        # "second consecutive" refusal even on the second attempt.
        window_open = can_retry is None or can_retry()
        retrying = attempts < 2 and window_open
        refusal = None
        if not retrying:
            refusal = (
                REFUSED_WINDOW_CLOSED if not window_open else REFUSED_SECOND_CONSECUTIVE
            )
        on_transient(
            retry_evidence(
                phase=phase,
                kind=kind,
                status=outcome.kind or "",
                http_status=outcome.http_status,
                parsed=outcome.parsed,
                text=outcome.text,
                poll_index=(
                    None if poll_index_base is None else poll_index_base + attempts
                ),
                retried=retrying,
                not_retried_because=refusal,
            ),
            kind,
        )
        if not retrying:
            return outcome, attempts, attempts > 1
        pacer.defer(wait_s)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return math.nan
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * (pct / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[int(rank)]
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (
        rank - low
    )


def summarize_latencies(
    values_ms: list[float], *, margin_pct: float, label: str
) -> dict[str, Any]:
    """Summarise a latency sample and derive a *candidate* hard-maximum bound.

    ``recommended_bound_ms = ceil(max x (1 + margin_pct/100))`` because the
    Verification-Profile keys these feed are ``hard_maximum`` /
    ``broker_specific`` maxima, not percentiles. ``p95``/``p99`` are reported for
    distribution shape only — proposing a percentile as the bound would convert a
    "no event can exceed this" contract into "most events do not exceed this".

    The returned value is explicitly a *candidate*: only a Bounds-Approver may
    write it into VERIFICATION-PROFILE-002.yaml.
    """
    clean = sorted(float(v) for v in values_ms if v is not None and not math.isnan(v))
    if not clean:
        return {
            "label": label,
            "n": 0,
            "insufficient_sample": True,
            "recommended_bound_ms": None,
            "statistic": "max x (1 + margin); no samples collected",
        }
    observed_max = clean[-1]
    return {
        "label": label,
        "n": len(clean),
        "min_ms": round(clean[0], 3),
        "p50_ms": round(_percentile(clean, 50), 3),
        "p90_ms": round(_percentile(clean, 90), 3),
        "p95_ms": round(_percentile(clean, 95), 3),
        "p99_ms": round(_percentile(clean, 99), 3),
        "max_ms": round(observed_max, 3),
        "stdev_ms": round(statistics.pstdev(clean), 3) if len(clean) > 1 else 0.0,
        "margin_pct": margin_pct,
        "recommended_bound_ms": int(
            math.ceil(observed_max * (1.0 + margin_pct / 100.0))
        ),
        "statistic": (
            "hard maximum: ceil(max_observed x (1 + margin_pct/100)). "
            "p95/p99 are shape diagnostics and MUST NOT be proposed as the bound."
        ),
        "sample_adequacy_note": (
            "A maximum estimated from a small sample understates the true "
            "maximum. Record n and the observation window with the value; the "
            "Bounds-Approver decides whether n is adequate."
        ),
        "candidate_only": True,
    }


# ---------------------------------------------------------------------------
# Result artifacts
# ---------------------------------------------------------------------------


def results_dir() -> Path:
    return Path(__file__).resolve().parent / "results"


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001 - provenance is best-effort
        return ""


@dataclass
class ProbeRun:
    """Collects observations and writes one JSON evidence artifact.

    The artifact is the object the runbook's "결과 기입 절차" consumes: its
    ``artifact_id`` becomes an INSTANCE ``evidence_refs`` entry and its
    ``measurements`` become the ``_kis.measurement`` provenance for the affected
    capability declaration.
    """

    probe_id: str
    title: str
    mode: str  # "dry-run" | "live"
    environment: str
    args: dict[str, Any] = field(default_factory=dict)
    credentials: dict[str, Any] = field(default_factory=dict)
    measurements: dict[str, Any] = field(default_factory=dict)
    observations: list[dict[str, Any]] = field(default_factory=list)
    skips: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    _t0: float = field(default_factory=time.monotonic, repr=False)

    #: The most recently constructed run, so ``run.py`` can salvage one whose probe
    #: raised before returning it.
    #:
    #: ``run.py:136-137`` states the intent — "a probe that could not complete must
    #: leave a trace, otherwise a silent failure looks like 'not yet run'" — but it
    #: implemented that by building a BLANK ProbeRun, which drops the credentials,
    #: observations and measurements the probe had already collected. The four
    #: ``N-15-20260729T06*`` artifacts are what that costs: ``credentials: {}``,
    #: ``observations: []``, ``measurements: {}``, and one exception string
    #: standing in for a session that had already recorded which token cache it was
    #: using and why. A trace that keeps nothing is barely better than none.
    _last: ClassVar[ProbeRun | None] = None

    def __post_init__(self) -> None:
        type(self)._last = self

    @classmethod
    def reset_salvage(cls) -> None:
        """Forget any earlier run, so only one built after this call is salvageable.

        ``run.py`` calls this immediately before invoking the probe. Without it
        ``_last`` is "the most recent run anywhere in the process", and a run built
        by an earlier probe — or, in the test suite, by an earlier test — could be
        written out as this probe's evidence. Scoping the window to the probe call
        makes a salvaged run provably one this invocation created.
        """
        cls._last = None

    @classmethod
    def salvage(cls, probe_id: str) -> ProbeRun | None:
        """The partially populated run for ``probe_id``, if one was built.

        Matched on ``probe_id`` as well, so even within the window a run for a
        different probe can never be written out under this probe's name.
        """
        last = cls._last
        return last if last is not None and last.probe_id == probe_id else None

    def observe(self, **fields: Any) -> None:
        self.observations.append(redact(fields))

    def measure(self, key: str, value: Any) -> None:
        self.measurements[key] = value

    def skip(self, what: str, reason: str) -> None:
        """Record an explicit, reasoned skip (never a silent omission)."""
        self.skips.append({"what": what, "reason": reason})
        print(f"  SKIP  {what}: {reason}")

    def error(self, message: str) -> None:
        self.errors.append(message)
        print(f"  ERROR {message}")

    def to_dict(self, spec: Any | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "probe_id": self.probe_id,
            "title": self.title,
            "mode": self.mode,
            "environment": self.environment,
            "started_at_utc": self.started_at,
            "finished_at_utc": datetime.now(UTC).isoformat(),
            "duration_s": round(time.monotonic() - self._t0, 3),
            "repo_commit": _git_commit(),
            "harness": "tools/broker_probes",
            "args": redact(self.args),
            "credentials": self.credentials,
            "measurements": redact(self.measurements),
            "observations": self.observations,
            "skips": self.skips,
            "errors": self.errors,
            "provenance_class": (
                "MEASURED"
                if self.mode == "live" and not self.errors
                else "NOT_MEASURED"
            ),
            "approval_status": "UNAPPROVED_CANDIDATE",
            "approval_note": (
                "This artifact records observations only. Writing any value into "
                "VERIFICATION-PROFILE-002.yaml requires a Bounds-Approver; writing "
                "any capability status into the Broker Capability Profile INSTANCE "
                "requires the P0-2 approval chain (draft memo §8)."
            ),
        }
        if spec is not None:
            payload["targets"] = {
                "verification_profile_bound_keys": list(spec.bounds_keys),
                "instance_fields": list(spec.instance_fields),
                "capability_dimension": spec.dimension,
            }
        return payload

    @property
    def artifact_id(self) -> str:
        stamp = self.started_at.replace(":", "").replace("-", "").split(".")[0]
        return f"{self.probe_id}-{stamp}Z"

    def write(self, spec: Any | None = None, out_dir: Path | None = None) -> Path:
        target_dir = out_dir or results_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{self.artifact_id}.json"
        path.write_text(
            json.dumps(self.to_dict(spec), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"\n  artifact: {path}")
        return path


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--confirm",
        action="store_true",
        help=(
            "Actually contact the broker. Without it, probes declared "
            "requires_confirm run as dry-run and print the request they would send."
        ),
    )
    parser.add_argument(
        "--asset",
        choices=("stock", "futures"),
        default="futures",
        help="Which credential/account family to use (default: futures).",
    )
    parser.add_argument(
        "--symbol",
        default="",
        help="Instrument code (e.g. 101S6000 futures, 005930 stock). Required for order probes.",
    )
    parser.add_argument(
        "--quantity", type=int, default=1, help="Order quantity (default: 1 = minimum)."
    )
    parser.add_argument(
        "--price-offset-pct",
        type=float,
        default=10.0,
        help=(
            "Place limit orders this far AWAY from the touch so they rest without "
            "filling (default 10%%). Order probes rely on a non-marketable resting "
            "order; lowering this risks an unintended fill."
        ),
    )
    parser.add_argument(
        "--samples", type=int, default=30, help="Sample count for latency probes."
    )
    parser.add_argument(
        "--margin-pct",
        type=float,
        default=50.0,
        help=(
            "Safety margin added to the observed maximum when proposing a bound "
            "candidate (default 50%%). The Bounds-Approver may override."
        ),
    )
    parser.add_argument(
        "--token-cache-dir",
        default=None,
        help=(
            "Token cache directory. Defaults to a probe-private directory under "
            "results/ so probes cannot delete the runtime token cache."
        ),
    )
    parser.add_argument("--out-dir", default=None, help="Result artifact directory.")
    parser.add_argument(
        "--note", default="", help="Free-text operator note for the artifact."
    )


def resolve_out_dir(args: argparse.Namespace) -> Path:
    return Path(args.out_dir).expanduser().resolve() if args.out_dir else results_dir()


def dry_run_banner(spec: Any) -> None:
    print(
        f"\n  DRY-RUN — {spec.probe_id} is declared requires_confirm "
        f"(risk={spec.risk}). Nothing was sent to the broker.\n"
        "  Re-run with --confirm once the runbook preconditions are satisfied:\n"
        "  docs/runbooks/kis-capability-probes.md"
    )


def warn_shared_token_cache() -> None:
    """Warn loudly if the operator pointed the probe at the runtime token cache."""
    shared = os.getenv("KIS_TOKEN_CACHE_DIR", "").strip()
    if shared:
        print(
            f"  WARNING: KIS_TOKEN_CACHE_DIR={shared!r} is set in the environment. "
            "The probe harness ignores it and uses a private cache; unset it only "
            "if you deliberately want probes to share the runtime token."
        )
