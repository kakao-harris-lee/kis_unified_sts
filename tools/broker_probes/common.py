"""Shared harness for the KIS Broker Capability Profile measurement probes."""

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
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

MOCK_HOST = "openapivts.koreainvestment.com"
REAL_HOST = "openapi.koreainvestment.com"
MOCK_BASE_URL = f"https://{MOCK_HOST}:29443"
REAL_BASE_URL = f"https://{REAL_HOST}:9443"

ENV_MOCK = "MOCK_VTS"
ENV_REAL = "REAL_PROD"
ENV_NONE = "NONE"

_MOCK_TRADING_TR_PREFIX = "V"
_REAL_TRADING_TR_PREFIXES = ("T", "S", "C")

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


def assert_mock_host(url: str) -> None:
    """Reject any URL that is not the KIS mock (모의투자) REST host."""
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
    """Refuse to run order probes while ``config/futures_live.yaml::enabled`` is true."""
    path = _REPO_ROOT / "config" / "futures_live.yaml"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if re.fullmatch(r"enabled:\s*(true|yes|on|1)", line, re.IGNORECASE):
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
    """Three-way allowlist gate for REAL-token probes (N-16, N-18)."""
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
    """Stable non-reversible correlator for an app key. NEVER the key itself."""
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
    """Read credentials from env with asset-specific precedence."""
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
    """Return the token-cache directory a probe may safely write to."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    return results_dir() / ".token_cache"


def build_auth_config(creds: ProbeCredentials, token_cache_dir: Path) -> Any:
    """Build a ``KISAuthConfig`` bound to the probe-private token cache."""
    from shared.kis.auth import KISAuthConfig

    scoped_dir = token_cache_dir / creds.asset
    scoped_dir.mkdir(parents=True, exist_ok=True)
    return KISAuthConfig(
        app_key=creds.app_key,
        app_secret=creds.app_secret,
        is_real=creds.is_real,
        token_cache_dir=str(scoped_dir),
    )


def http_json_with_headers(
    session: Any,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> tuple[int, dict[str, Any], float, str, Mapping[str, str]]:
    """:func:`http_json`, plus the RESPONSE headers — the one request site."""
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
    return int(response.status_code), parsed, elapsed_ms, text, response.headers


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
    """Issue one request and return ``(status, parsed, elapsed_ms, raw_text)``."""
    status, parsed, elapsed_ms, text, _headers = http_json_with_headers(
        session,
        method,
        url,
        headers=headers,
        params=params,
        json_body=json_body,
        timeout=timeout,
    )
    return status, parsed, elapsed_ms, text


def is_rate_limited(status: int, parsed: dict[str, Any], text: str) -> bool:
    """Detect a broker-side rate-limit rejection."""
    if status == 429:
        return True
    blob = f"{parsed.get('msg_cd', '')} {parsed.get('msg1', '')} {text}"
    return "EGW00201" in blob


REFUSED_SECOND_CONSECUTIVE = "second_consecutive_transient"
REFUSED_WINDOW_CLOSED = "window_already_closed"
REFUSED_SINGLE_SHOT = "single_shot_call"

TRANSIENT_TRANSPORT = "transport"
TRANSIENT_LEDGER_THROTTLE = "ledger_throttle"

STATUS_TRANSIENT = "TRANSIENT"
STATUS_TRANSIENT_TRANSPORT = f"{STATUS_TRANSIENT}:{TRANSIENT_TRANSPORT}"
STATUS_TRANSIENT_LEDGER_THROTTLE = f"{STATUS_TRANSIENT}:{TRANSIENT_LEDGER_THROTTLE}"
STATUS_RATE_LIMITED = "RATE_LIMITED"

_TRANSIENT_KINDS: dict[str, str] = {
    STATUS_TRANSIENT_TRANSPORT: TRANSIENT_TRANSPORT,
    STATUS_TRANSIENT_LEDGER_THROTTLE: TRANSIENT_LEDGER_THROTTLE,
}

LEDGER_THROTTLE_MSG_CD = "EGW00215"


def is_ledger_throttled(parsed: dict[str, Any]) -> bool:
    """``msg_cd`` is exactly :data:`LEDGER_THROTTLE_MSG_CD`."""
    return str(parsed.get("msg_cd") or "").strip() == LEDGER_THROTTLE_MSG_CD


def transport_transient_types() -> tuple[type[BaseException], ...]:
    """The exception types the probe transports actually raise for a timeout or"""
    import requests

    return (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
        requests.exceptions.ContentDecodingError,
    )


_QUERY_STRING_IN_MESSAGE = re.compile(r"\?\S*")


def transport_excerpt(exc: BaseException) -> str:
    """One transport exception rendered for the artifact, query string removed."""
    return _QUERY_STRING_IN_MESSAGE.sub("?<redacted>", f"{type(exc).__name__}: {exc}")


def transient_kind(status: str | None) -> str | None:
    """``"transport"``/``"ledger_throttle"`` for a transient status, else ``None``."""
    return _TRANSIENT_KINDS.get(status or "")


def classify_answer(http_status: int, parsed: dict[str, Any], text: str) -> str | None:
    """The ONLY copy of the retry/no-retry precedence, for an answer that ARRIVED."""
    if is_rate_limited(http_status, parsed, text):
        return STATUS_RATE_LIMITED
    if is_ledger_throttled(parsed):
        return STATUS_TRANSIENT_LEDGER_THROTTLE
    return None


BODY_EXCERPT_MAX_CHARS = 300


def rt_cd_of(parsed: dict[str, Any]) -> str:
    """``rt_cd`` as a comparable string, or ``""`` when the body carries none."""
    raw = parsed.get("rt_cd")
    return "" if raw is None else str(raw).strip()


def call_evidence(
    *, status_kind: str, http_status: int, parsed: dict[str, Any], text: str
) -> dict[str, Any]:
    """Verbatim broker evidence for one failed call, for the artifact."""
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
    """The record written for EVERY transient, retried or not."""
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
    """One broker call, already run through the transient classification."""

    kind: str | None
    http_status: int
    parsed: dict[str, Any]
    text: str
    payload: Any = None


class Pacer:
    """Minimum-interval gate in front of a probe client's only socket."""

    def __init__(self, interval_s: float) -> None:
        self.interval_s = max(0.0, float(interval_s))
        self._next_allowed_at: float | None = None

    def wait(self) -> float:
        """Block out the remainder of the interval; return the release instant."""
        now = time.monotonic()
        if self._next_allowed_at is not None and now < self._next_allowed_at:
            time.sleep(self._next_allowed_at - now)
            now = time.monotonic()
        self._next_allowed_at = now + self.interval_s
        return now

    def defer(self, seconds: float) -> None:
        """Push the next allowed call ``seconds`` out from NOW."""
        target = time.monotonic() + max(0.0, float(seconds))
        if self._next_allowed_at is None or target > self._next_allowed_at:
            self._next_allowed_at = target


class Retries:
    """Counts the retries a run spent, and keeps ``measurements.retries``"""

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
    """The standard ``on_transient``: observe EVERY transient, count the RETRIES."""

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
    """Run ``call``; on a transient outcome wait one whole interval and run it"""
    attempts = 0
    while True:
        attempts += 1
        outcome = call()
        kind = transient_kind(outcome.kind)
        if kind is None:
            return outcome, attempts, attempts > 1
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
    """Summarise a latency sample and derive a *candidate* hard-maximum bound."""
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
    """Collects observations and writes one JSON evidence artifact."""

    probe_id: str
    title: str
    mode: str
    environment: str
    args: dict[str, Any] = field(default_factory=dict)
    credentials: dict[str, Any] = field(default_factory=dict)
    measurements: dict[str, Any] = field(default_factory=dict)
    observations: list[dict[str, Any]] = field(default_factory=list)
    skips: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    _t0: float = field(default_factory=time.monotonic, repr=False)

    _last: ClassVar[ProbeRun | None] = None

    def __post_init__(self) -> None:
        type(self)._last = self

    @classmethod
    def reset_salvage(cls) -> None:
        """Forget any earlier run, so only one built after this call is salvageable."""
        cls._last = None

    @classmethod
    def salvage(cls, probe_id: str) -> ProbeRun | None:
        """The partially populated run for ``probe_id``, if one was built."""
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
