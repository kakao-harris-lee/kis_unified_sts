"""``KisQuoteObservationIntake`` — the KIS 모의투자 quote HTTP
:class:`~tos_runtime.marketfeed.ports.ObservationIntake` (TOS tick-source wave, W2 lane, plan
``docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`` §4 W2).

Gives the tick source a REAL market-data intake — an HTTP GET against a KIS 모의투자 quotations
TR — so a deployment is no longer driven only by a file journal an upstream collector writes
(:mod:`tos_runtime.marketfeed.journal`, this wave's other, file-backed
:class:`~tos_runtime.marketfeed.ports.ObservationIntake`).

**Step 0 measurement 1 — this TR's OWN response body carries no genuine source event time (do not
skip this, and do not over-read it as a claim about KIS as a whole — see the explicit scope note
below).** The legacy KIS client stamps ``"timestamp": time.time()`` itself on every quote —
``shared/kis/client.py:648`` (stock) and ``:737`` (futures) — its own comment reads "Use local
time as approx". This is receipt time, not a broker-attested event time, by the legacy code's OWN
admission. Independent evidence confirms THIS RESPONSE BODY (the ``inquire-price`` quotations TR
this adapter polls) carries no genuine event-time field either: a live MOCK_VTS stock quote
capture (``docs/broker-profiles/evidence/2026-07-29-p02-t2-campaign/P-16-20260729T133539Z.json``,
005930, n=5, errors 0) lists ``body_timestamp_like_keys: [crdt_able_yn, ovtm_vi_cls_code,
rstc_wdth_prc]`` — and the broker profile itself
(``KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:2325-2331``) records that all three are FALSE
POSITIVES from a substring heuristic (신용가능여부/시간외VI구분코드/제한폭가격 — none is a
timestamp), leaving genuinely **zero** timestamp-like fields in the measured body. The futures
scope probe (``P-16-20260729T063005Z``) independently records ``body_timestamp_like_keys: []`` —
zero, not merely zero after the false-positive correction.

**Scope note — KIS DOES have a genuine execution-time field elsewhere; this adapter cannot reach
it.** ``shared/kis/stock_feed.py:67`` (``_F_TIME`` = ``STCK_CNTG_HOUR``, "체결시간") shows the KIS
real-time WebSocket trade feed (TR ``H0STCNT0``, subscription-based push, not an HTTP GET) DOES
carry a genuine broker execution time — the legacy WebSocket handler parses that field's position
and then DISCARDS it in favor of ``time.time()`` at ``stock_feed.py:120``, the same receipt-time
substitution as the REST client. No REST/HTTP TR carrying an equivalent field is measured,
referenced, or implemented anywhere in this repository, and this adapter's whole architecture
(:class:`~tos_runtime.marketfeed.ports.ObservationIntake`'s pull-based ``poll()``, this wave's own
stdlib-HTTP-only scope) is a REST poller, not a WebSocket subscriber — adopting the WebSocket feed
would be a different transport architecture, out of this lane's scope, not a code change here.
This paragraph exists so a future reader who wants genuine event time knows WHERE to look (a
WebSocket-subscribing intake, a lane this module does not attempt), rather than concluding KIS
never offers one.

**Conclusion, stated loudly rather than implied, and made unconditionally true rather than resting
on a measurement that does not cover every value this adapter's own config admits (independent
review MEDIUM, 2026-09-17 — see that note below).** This adapter uses RECEIPT time for
``RawObservation.as_of_ms`` — never a value read from the response body — as a STRUCTURAL fact
about this module's own code, not a claim earned by measuring any one TR: :meth:`poll`'s only
source for ``as_of_ms``/``received_ms`` is ``self._time_service.wall_clock_now()`` (below); nothing
in :meth:`_parse_output`/:meth:`_map_fields` ever extracts a timestamp candidate from the response
body, for ANY TR id :class:`~tos_runtime.transport.kis_quote.config.KisQuoteTransportConfig`'s
loader admits. This is deliberately the general, code-level statement, not the TR-specific one an
earlier revision of this paragraph made — that revision was true for the two TR ids this adapter
was actually measured against (``FHKST01010100``, ``FHMIF10000000`` — Step 0 measurement 1 above),
but ``_QUOTE_TR_ID_PATTERN`` (``config.py``) admits any ``^FH[A-Z]{3}\\d{8}$`` id, including the
other two the shape itself was derived from (``FHPPG04600001``/``FHKST03030200``) whose OWN
response bodies were never independently checked for a timestamp field. Resting the honesty
argument on a per-TR measurement would have been false for an operator who (harmlessly, from a
safety point of view — this code still never reads one) configured one of those. The Step 0
measurement above still stands as the motivating EVIDENCE for why this design was chosen in the
first place — it is just no longer the thing the conclusion's own truth depends on.

This is not a claim that no KIS TR anywhere carries a genuine event time (the scope note above is
the counter-evidence) — it is a claim about what this adapter's own code does with whatever body a
configured TR returns. A future change to poll a different REST TR that does carry a genuine event
time — or a future WebSocket-based intake — would need this module's own analysis, and its own new
code path, not a silent assumption inherited from this one.

**Receipt-time anchor.** ``as_of_ms``/``received_ms`` are both stamped from the SAME
:meth:`~tos_runtime.time.service.TrustworthyTimeService.wall_clock_now` reading, taken AFTER the
HTTP response is received (never before — the scheduler's own pre-poll ``now_ms``,
``scheduler.py``'s ``tick_once``, is a DIFFERENT, earlier instant and is not reused here, since
reusing it would understate every observation's own network latency). ``wall_clock_now()``
returns ``None`` when Trustworthy Time is not yet ``TRUSTED`` — this adapter RAISES
:class:`KisQuoteWallClockUntrusted` rather than fabricating a time or silently returning "nothing
new", because those are different facts: "the clock is not trusted yet" is an operational fault,
not "the market has not moved".

**Two clocks, two jobs (deliberate, do not merge).** This adapter is injected with BOTH a
:class:`~tos_runtime.time.sources.MonotonicSource` and a wall-clock reader, and they are never
substituted for each other. The shared :class:`~tos_runtime.transport.kis_mock.token
.KisTokenLifecycle` uses ONLY the monotonic source — a token's own age/cooldown bookkeeping is a
purely process-local, relative-elapsed-time concern that has nothing to do with whether
Trustworthy Time currently considers wall-clock readings ``TRUSTED``. An earlier revision of this
module derived the token lifecycle's clock FROM ``wall_clock_now()`` instead, which had two bugs:
it made a perfectly valid, still-live token suddenly unusable the instant wall-clock trust
degraded (for a reason unrelated to the token), and it moved the "untrusted" raise EARLIER than
this docstring's own "taken after the HTTP response" claim — ``ensure_token_string`` reads its
clock before ``_fetch_quote`` is ever called, on every poll, including ones whose token is still
perfectly fresh. Kept as a note against reintroducing that mistake.

**Step 0 measurement 2 — the token lifecycle is shared, not duplicated.** This adapter's token
handling is :class:`~tos_runtime.transport.kis_mock.token.KisTokenLifecycle` — the SAME class the
KIS MOCK order transport uses, against the SAME custody scopes (``kis_mock.app_key``/
``kis_mock.app_secret``): KIS's own environment separation is enforced per TR family, not per
credential (this module's own imports' docstrings cite the measurement), so a quote TR and an
order TR authenticate with the same mock app key and may share one cached token. See
``tos_runtime.transport.kis_mock.token``'s own module docstring for the extraction's
behavior-preservation proof.

**The phantom-churn problem (a real design decision, not a detail).** KIS's quote TR has no
"since" parameter — every GET returns the CURRENT price, full stop. Naively minting a
:class:`~tos_runtime.marketfeed.ports.RawObservation` on every poll, stamped with a fresh receipt
time, would make EVERY poll look like a new market event even when the market has not moved —
manufacturing ticks with no real change, and (per
:mod:`tos_runtime.marketfeed.ports`'s own "field state is derived, never declared" discipline)
silently inflating "freshness" with no matching cause. This adapter instead tracks its own
LAST-EMITTED content digest (over the mapped, admitted field tuple only — never the raw response,
so an unmapped, economically-insignificant KIS field changing does not, by itself, mint a tick) and
returns an EMPTY sequence — :attr:`~tos_runtime.marketfeed.ports.TickOutcome
.SKIPPED_NO_OBSERVATION`'s own "nothing new" contract — when the freshly polled content is
byte-identical to what was last emitted. Only a genuine content change mints a new observation, and
only then is ``raw_event_id`` derived as ``{source_id}:{instrument}:{as_of_ms}:{content_digest}`` —
combining the receipt instant with the content digest so two observations can never collide even if
a byte-identical body reappears at a LATER receipt time (a legitimate, distinct observation: the
market genuinely returned to a prior price at a new instant) or, in the pathological case of two
polls landing in the same millisecond, differ only in content (the digest disambiguates that too).
This adapter never emits two observations sharing a ``raw_event_id`` — the ambiguity
:mod:`tos_runtime.marketfeed.ports`'s own module docstring warns a producer must never create.

**Field mapping is configured, never hardcoded.** ``KisQuoteTransportConfig.field_mapping`` names
exactly which KIS wire field keys this adapter reads and which
``critical_input_policy.yaml``-admitted ``field_key`` each feeds. A KIS response field NOT named
in that mapping is dropped here, silently from this module's own point of view (the CIP's own
∅-floor already drops anything it does not itself admit — ``tos/src/tos/marketfeed/value.py``'s
``UNKNOWN`` floor — so a second, redundant drop-with-a-warning here would only duplicate that
floor, not add information). **No unit/scale/multiplier/sign interpretation happens in this
module** — the raw KIS scalar value (a numeral-as-string, per KIS's own JSON convention observed
in every cited evidence artifact) is carried through UNCHANGED; that interpretation is the
CIP-governed value-derivation layer's job (``policy.py``'s own ``unit``/``scale``/``multiplier``/
``sign`` fields), never something a collector invents for itself (``ports.py``'s own "field state
is derived, never declared" discipline).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``hashlib``, ``json``,
``typing``) + ``tos.*`` (``tos.dsl`` for :data:`~tos.dsl.ScalarValue`) +
``tos_runtime.custody``/``tos_runtime.time``/``tos_runtime.marketfeed``/this package's own sibling
``config``/``tos_runtime.transport.kis_mock`` (the shared token lifecycle + HTTP client) only. No
``shared.*``, no ``os.environ``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from tos.dsl import ScalarValue

from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.marketfeed.ports import ObservationIntake, RawObservation
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.client import KisMockHttpClient, RawResponse
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSession
from tos_runtime.transport.kis_mock.token import (
    EvidenceRecorder,
    TokenIssuingClient,
    TokenStale,
)
from tos_runtime.transport.kis_quote.config import KisQuoteTransportConfig

__all__ = [
    "KisQuoteAdapterError",
    "KisQuoteMalformedResponse",
    "KisQuoteObservationIntake",
    "KisQuoteRejected",
    "KisQuoteWallClockUntrusted",
    "TokenStale",
    "WallClockSource",
    "build_quote_client",
]

#: The two custody scope names a KIS quote poll authenticates with — deliberately the SAME
#: literal strings ``_transport_wiring.py``'s ``_KIS_MOCK_APP_KEY_SCOPE``/
#: ``_KIS_MOCK_APP_SECRET_SCOPE`` use for the order transport (module docstring's "shared, not
#: duplicated" credential note): one KIS mock app key/secret pair, one set of custody scopes,
#: regardless of which TR family is being called.
_KIS_MOCK_APP_KEY_SCOPE = "kis_mock.app_key"
_KIS_MOCK_APP_SECRET_SCOPE = "kis_mock.app_secret"

#: JSON-native scalar types this adapter ever carries into a ``RawObservation`` field — mirrors
#: ``tos_runtime.marketfeed.journal``'s own ``_SCALAR_FIELD_TYPES`` exactly (``bool`` checked
#: before ``int`` for the same reason: ``bool`` is an ``int`` subclass in Python, and this
#: adapter never silently narrows ``True`` to ``1``).
_SCALAR_FIELD_TYPES: tuple[type, ...] = (bool, int, float, str)


@runtime_checkable
class WallClockSource(Protocol):
    """The one method this module needs from a time service — mirrors
    :class:`tos_runtime.calendar.ports`'s own private ``_WallClockNowSource`` Protocol
    (identical shape, independently duplicated there for the same reason: match
    :meth:`~tos_runtime.time.service.TrustworthyTimeService.wall_clock_now` structurally without
    importing that module, keeping this module's own import surface — and a test's own fake —
    minimal)."""

    def wall_clock_now(self) -> int | None:
        """The current wall-clock reading, or ``None`` when not yet ``TRUSTED``. MUST NOT
        raise."""
        ...


class KisQuoteAdapterError(Exception):
    """A structural fault in this adapter's own configuration/wiring — e.g. ``poll`` was called
    for an ``instrument`` other than the one this config declares (module docstring: single-
    instrument scope, never silently served from the wrong config)."""


class KisQuoteRejected(Exception):
    """The broker's own response carried ``rt_cd != "0"`` — a business-layer rejection, not a
    transport fault. Refused rather than treated as "nothing new": a rejection is new information
    about this poll, not an absence of one."""


class KisQuoteMalformedResponse(Exception):
    """The response body did not parse as JSON, was not an object, or its ``output`` block was
    missing/not an object/missing a mapped field/carried a mapped field of an unsupported
    (non-scalar) type — refused rather than silently dropped (mirrors
    :mod:`tos_runtime.marketfeed.journal`'s own fail-closed-on-malformed-input discipline).
    """


class KisQuoteWallClockUntrusted(Exception):
    """:meth:`~tos_runtime.time.service.TrustworthyTimeService.wall_clock_now` returned ``None``
    — Trustworthy Time is not yet ``TRUSTED``. Raised rather than treated as "nothing new" (module
    docstring): those are different facts, and collapsing them would hide an operational fault
    behind an ordinary quiet poll."""


def build_quote_client(config: KisQuoteTransportConfig) -> KisMockHttpClient:
    """The one sanctioned way to build a client for a real KIS quote poll (mirrors
    :func:`tos_runtime.transport.kis_mock.client.build_client`'s own "one sanctioned
    construction path" discipline for the order transport) — every argument comes from
    ``config``, never a caller-supplied URL, so a client can never be pointed anywhere the
    config loader's own host-seal check did not already validate."""
    return KisMockHttpClient(
        rest_base=config.endpoint_rest_base,
        request_timeout_s=config.request_timeout_s,
        allow_plaintext_for_tests=config.allow_plaintext_for_tests,
    )


class KisQuoteObservationIntake:
    """The KIS 모의투자 quote :class:`~tos_runtime.marketfeed.ports.ObservationIntake` (module
    docstring for the full contract: receipt-time ``as_of_ms``, shared token lifecycle,
    content-dedup against phantom churn, configured field mapping)."""

    def __init__(
        self,
        *,
        config: KisQuoteTransportConfig,
        client: KisMockHttpClient,
        monotonic: MonotonicSource,
        time_service: WallClockSource,
        evidence_sink: EvidenceRecorder,
        custody: CredentialCustody | None = None,
        credential_session: KisCredentialSession | None = None,
    ) -> None:
        """Wire this intake's dependencies (all injected — no ambient state).

        Args:
            config: The fail-closed-loaded :class:`~tos_runtime.transport.kis_quote.config
                .KisQuoteTransportConfig`.
            client: The stdlib HTTP shim — build via :func:`build_quote_client` for real use.
            custody: The credential source — the two ``kis_mock.*`` scopes must already be
                provisioned (module-level constants above).
            monotonic: The injected monotonic clock — used ONLY for the shared token
                lifecycle's own pacing/expiry bookkeeping (module docstring's "two clocks, two
                jobs" note). Deliberately NOT derived from ``time_service``: a token's own
                validity is a purely process-local, RELATIVE-elapsed-time concern that has
                nothing to do with whether Trustworthy Time currently considers wall-clock
                readings ``TRUSTED`` — conflating the two would make a perfectly good, still-
                valid token suddenly unusable the moment wall-clock trust degrades, for a
                reason that has nothing to do with the token itself (an earlier revision of
                this module made exactly that mistake; kept here as a note against
                reintroducing it).
            time_service: This process's shared Trustworthy Time service — the ONE wall-clock
                reading this adapter takes for its OWN ``as_of_ms``/``received_ms`` stamp,
                taken once per emitted observation, after the HTTP response is received
                (module docstring).
            evidence_sink: Records this intake's own token-lifecycle evidence entries
                (``TRANSPORT_TOKEN_STALE`` — forwarded to :class:`~tos_runtime.transport.kis_mock
                .token.KisTokenLifecycle`, this module raises no evidence of its own).
            credential_session: The app key's single owner (C-2 decision (C)) — compose passes
                the one it shares with the order transport. ``None`` builds a private one from
                ``custody`` (then required) and the ``kis_mock.*`` scopes above.

        Raises:
            KisQuoteAdapterError: Neither ``credential_session`` nor ``custody`` was supplied.
        """
        self._config = config
        self._client = client
        self._time_service = time_service
        if credential_session is None:
            if custody is None:
                raise KisQuoteAdapterError(
                    "KisQuoteObservationIntake: supply credential_session, or custody to build "
                    "a private one"
                )
            credential_session = KisCredentialSession(
                client=_TokenIssuingClientAdapter(client),
                custody=custody,
                app_key_scope=_KIS_MOCK_APP_KEY_SCOPE,
                app_secret_scope=_KIS_MOCK_APP_SECRET_SCOPE,
                monotonic=monotonic,
                token_path=config.token_path,
                token_reissue_min_interval_s=config.token_reissue_min_interval_s,
                evidence_sink=evidence_sink,
            )
        # C-2 decision (C) — the token lifecycle and every custody load of the app key live in
        # the session; this class never touches custody itself.
        self._credential_session = credential_session
        #: The last-EMITTED content digest, or ``None`` before this process's first successful
        #: poll (module docstring's phantom-churn note). Process-local: a restart re-emits one
        #: confirmatory observation even if the market has not moved since the last emission
        #: before the restart — a legitimate, honest re-confirmation, not a bug (the durable
        #: snapshot store's own ``latest_as_of`` re-derivation in ``decide_tick`` still applies
        #: on top of this).
        self._last_content_digest: str | None = None

    def poll(
        self, *, instrument: str, after_as_of_ms: int | None
    ) -> Sequence[RawObservation]:
        """Return a single fresh observation for ``instrument``, or none (module docstring).

        Args:
            instrument: MUST equal ``config.instrument`` — this intake serves exactly one,
                configured instrument (FORWARD-OBLIGATION-MS1 is unratified).
            after_as_of_ms: Accepted for :class:`~tos_runtime.marketfeed.ports.ObservationIntake`
                conformance; NOT used to filter here — KIS's quote TR has no "since" parameter, so
                every poll fetches the CURRENT price and the phantom-churn content-dedup (module
                docstring) is what decides whether that counts as "new". ``decide_tick``'s own
                ``SKIPPED_NOT_NEWER`` re-derivation (``scheduler.py`` module docstring) still runs
                as a second, independent check downstream.

        Returns:
            Exactly one observation when the polled content differs from the last one this
            process emitted; an empty sequence otherwise ("nothing new" — a first-class answer,
            per :class:`~tos_runtime.marketfeed.ports.ObservationIntake`'s own docstring).

        Raises:
            KisQuoteAdapterError: ``instrument`` does not equal ``config.instrument``.
            KisQuoteWallClockUntrusted: Trustworthy Time is not yet ``TRUSTED``.
            TokenStale: The held token has expired and the reissue cooldown has not elapsed.
            KisMockConnectionError: The connection failed or was reset.
            KisMockTimeoutError: The request timed out.
            KisQuoteRejected: The broker's response carried ``rt_cd != "0"``.
            KisQuoteMalformedResponse: The response body was not usable (module docstring).
        """
        del after_as_of_ms  # module docstring — content-dedup decides "new", not this parameter
        if instrument != self._config.instrument:
            raise KisQuoteAdapterError(
                f"KisQuoteObservationIntake: poll() called for instrument {instrument!r} but "
                f"this config is scoped to {self._config.instrument!r} — refusing to serve the "
                "wrong instrument's quote"
            )

        access_token = (
            self._credential_session.ensure_token_string()
        )  # may raise TokenStale
        response = self._fetch_quote(access_token)
        output = self._parse_output(response)
        fields = self._map_fields(output)

        # The wall-clock reading is taken AFTER the response is fully received (module
        # docstring) — never reused from an earlier instant.
        wall_now_ms = self._time_service.wall_clock_now()
        if wall_now_ms is None:
            raise KisQuoteWallClockUntrusted(
                "KisQuoteObservationIntake: TrustworthyTimeService.wall_clock_now() returned "
                "None (not yet TRUSTED) — refusing to stamp an observation with no honest clock"
            )

        content_digest = self._content_digest(fields)
        if content_digest == self._last_content_digest:
            return ()  # nothing new — module docstring's phantom-churn discipline

        self._last_content_digest = content_digest
        raw_event_id = (
            f"{self._config.source_id}:{instrument}:{wall_now_ms}:{content_digest}"
        )
        observation = RawObservation(
            raw_event_id=raw_event_id,
            instrument=instrument,
            as_of_ms=wall_now_ms,
            fields=fields,
            source_id=self._config.source_id,
            received_ms=wall_now_ms,
        )
        return (observation,)

    def _fetch_quote(self, access_token: str) -> RawResponse:
        """(mirrors ``KisMockTransport._send_order_with_credentials``'s own discipline) The app
        key/secret are loaded inside the NARROWEST possible ``with`` block — wrapped directly
        around the one network call that needs them, so the credential handles are zeroed the
        instant this one GET returns."""
        query = (
            f"FID_COND_MRKT_DIV_CODE={self._config.market_div_code}"
            f"&FID_INPUT_ISCD={self._config.instrument}"
        )
        with self._credential_session.app_credentials() as credentials:
            return self._client.get_quote(
                self._config.tr_id,
                query,
                access_token=access_token,
                app_key=credentials.app_key(),
                app_secret=credentials.app_secret(),
                path=self._config.quote_path,
            )

    def _parse_output(self, response: RawResponse) -> dict[str, object]:
        if response.json is None:
            raise KisQuoteMalformedResponse(
                f"KisQuoteObservationIntake: response body did not parse as a JSON object "
                f"(status={response.status})"
            )
        rt_cd = response.json.get("rt_cd")
        if rt_cd != "0":
            msg = response.json.get("msg1", "unknown error")
            raise KisQuoteRejected(
                f"KisQuoteObservationIntake: broker rejected the quote poll "
                f"(rt_cd={rt_cd!r}, msg1={msg!r})"
            )
        output = response.json.get("output")
        if not isinstance(output, dict):
            raise KisQuoteMalformedResponse(
                f"KisQuoteObservationIntake: response 'output' is not a JSON object "
                f"(got {type(output).__name__})"
            )
        return output

    def _map_fields(
        self, output: dict[str, object]
    ) -> tuple[tuple[str, ScalarValue], ...]:
        # Typed `Any` for the value slot (mirrors tos_runtime.marketfeed.journal's own
        # _require_fields) — mypy cannot narrow a runtime tuple-of-types constant to a Union,
        # so the isinstance check below is the actual runtime guard; the static type is widened
        # here rather than re-litigating that narrowing gap with a cast.
        entries: list[tuple[str, Any]] = []
        for wire_key, field_key in self._config.field_mapping.items():
            if wire_key not in output:
                raise KisQuoteMalformedResponse(
                    f"KisQuoteObservationIntake: response 'output' is missing mapped field "
                    f"{wire_key!r} (-> {field_key!r})"
                )
            value = output[wire_key]
            if isinstance(value, _SCALAR_FIELD_TYPES):
                entries.append((field_key, value))
                continue
            raise KisQuoteMalformedResponse(
                f"KisQuoteObservationIntake: output[{wire_key!r}] has unsupported type "
                f"{type(value).__name__} (must be bool|int|float|str)"
            )
        return tuple(entries)

    @staticmethod
    def _content_digest(fields: tuple[tuple[str, ScalarValue], ...]) -> str:
        """A stable digest over the mapped field tuple — key-sorted so declaration order in
        ``field_mapping`` never changes the digest (mirrors
        :mod:`tos_runtime.marketfeed.journal`'s own order-independence discipline)."""
        canonical = json.dumps(sorted(fields), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class _TokenIssuingClientAdapter:
    """Adapts :class:`~tos_runtime.transport.kis_mock.client.KisMockHttpClient` onto
    :class:`~tos_runtime.transport.kis_mock.token.TokenIssuingClient` — trivial today (the two
    shapes already match exactly), kept as an explicit seam so a future quote-only client
    implementation does not need to also BE a full ``KisMockHttpClient``."""

    def __init__(self, client: KisMockHttpClient) -> None:
        self._client = client

    def issue_token(
        self, app_key: bytes, app_secret: bytes, *, path: str
    ) -> dict[str, object]:
        return self._client.issue_token(app_key, app_secret, path=path)


#: Static conformance checks — mypy fails this file if either class's shape ever drifts from the
#: Protocol it implements (mirrors ``tos_runtime.marketfeed.journal``'s own convention).
_conforms_to_observation_intake: type[ObservationIntake] = KisQuoteObservationIntake
_conforms_to_token_issuing_client: type[TokenIssuingClient] = _TokenIssuingClientAdapter
