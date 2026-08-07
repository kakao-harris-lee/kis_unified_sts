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
