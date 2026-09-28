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
review MEDIUM, 2026-09-17 — see that note below).** This adapter anchors an observation on the
LOCAL instants of its own request — never a value read from the response body — as a STRUCTURAL
fact about this module's own code, not a claim earned by measuring any one TR: the only times
:meth:`poll` supplies are two ``monotonic.now_ms()`` readings taken around the request (below);
nothing in :meth:`_parse_output`/:meth:`_map_fields` ever extracts a timestamp candidate from the
response body, for ANY TR id
:class:`~tos_runtime.transport.kis_quote.config.KisQuoteTransportConfig`'s loader admits. This is deliberately the general, code-level statement, not the TR-specific one an
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

**Request-start anchor, on the MONOTONIC clock — the scheduler stamps it after the evaluation**
(plan ``docs/plans/2026-09-28-tos-kis-quote-request-anchor-plan.md`` §2.4; issue #810). This
adapter reads NO wall clock at all. It takes a
:meth:`~tos_runtime.time.sources.MonotonicSource.now_ms` reading immediately before the request
goes out and another immediately after the response arrives, and returns a
:class:`~tos_runtime.marketfeed.ports.MonotonicAnchoredObservation` carrying both.
:meth:`~tos_runtime.marketfeed.scheduler.TickScheduler.tick_once` maps them onto that pass's own
freshly evaluated reading (:meth:`~tos_runtime.time.service.TrustworthyTimeService
.wall_clock_at_monotonic`) — ``as_of_ms`` from the REQUEST instant, ``received_ms`` from the
response one.

*Why not stamp a wall-clock reading here.*
:meth:`~tos_runtime.time.service.TrustworthyTimeService.wall_clock_now` hands back the reading
the last ``evaluate()`` cached, never a fresh one, and since 2026-09-27 that evaluation runs
AFTER the pass's intake read (plan
``docs/plans/2026-09-27-tos-freshness-read-order-plan.md`` §2.4; issue #809). So a stamp taken
here — before or after the response, it makes no difference — is the PREVIOUS pass's reading, and
``source_age`` came out ≈ the pass spacing: at the ≥ 1000 ms spacings the 모의 quote rate limit
admits (1.0 rps clean, probe P-13) every observation read STALE against the 800 ms paper budget.
Anchoring on the request instead puts THIS request's own round trip into ``source_age``, which is
the quantity that was actually measured.

⚠ **What this still does NOT know, stated rather than implied** (plan §2.5). The response body
carries no event time (the measurements above), so how stale the data was on the BROKER's side
remains unknown. Anchoring on the request start raises the age's LOWER BOUND from 0 to the HTTP
round trip; it does not produce the true age. Stricter than the pre-#809 "age 0" fail-open,
still not a source event time — a genuine one needs the WebSocket feed named in the scope note
above, not a different stamp here.

**The deferred digest: an unconsumed quote is re-emitted, not dropped** (plan §2.4). ``poll``
cannot filter on ``after_as_of_ms`` (KIS's quote TR has no "since" parameter), but it does READ
it: that argument is the durable store's own high-water mark, so it advances exactly when the
previous pass's observation was consumed. This adapter therefore holds a freshly emitted content
digest as *pending* and promotes it to ``_last_content_digest`` only on a later poll whose
``after_as_of_ms`` has advanced. An observation the scheduler declined to consume
(``TickOutcome.SKIPPED_TIME_NOT_EVALUATED``/``SKIPPED_TIME_UNANCHORED`` — no ``store.put``,
``latest_as_of`` unmoved) is re-emitted on the next pass instead of being dropped until the price
changes. The phantom-churn guarantee below is unaffected: once an emission IS consumed, an
unchanged quote goes back to returning ``()``.

**One clock, two jobs — and it must be THE process's monotonic source.** Since #810 this adapter
is injected with a single clock, a :class:`~tos_runtime.time.sources.MonotonicSource`, serving
both the shared :class:`~tos_runtime.transport.kis_mock.token.KisTokenLifecycle`'s own
age/cooldown bookkeeping and the two request-anchor readings. Those two uses have DIFFERENT
requirements and the stricter one governs: token pacing needs only relative elapsed time from any
consistent source, while the anchor readings are mapped by
:meth:`~tos_runtime.time.service.TrustworthyTimeService.wall_clock_at_monotonic`, which compares
them against the time service's own readings — so this must be the very
:class:`~tos_runtime.time.sources.MonotonicSource` INSTANCE that service was built with, not a
second one. Compose passes exactly that (``compose/_wiring.py``'s ``_Infra.monotonic_source``),
and ``tests/compose/test_marketfeed_intake_kind_wiring.py`` pins the object identity; a private
second source would make every mapping fall outside the domain and every pass answer
``SKIPPED_TIME_UNANCHORED``.

⚠ **Against reintroducing a wall clock here.** An earlier revision derived the token lifecycle's
clock from ``wall_clock_now()``, which made a perfectly valid, still-live token unusable the
instant wall-clock trust degraded, for a reason unrelated to the token. A later one stamped
``as_of_ms`` from that same reading, which is the #810 defect this module has now removed. Token
validity, observation anchoring, and wall-clock TRUST are three different facts; the first two
live on the monotonic clock here, and the third is the scheduler's to apply after its own
evaluation.

**Step 0 measurement 2 — the token lifecycle is shared, not duplicated.** This adapter's token
handling is :class:`~tos_runtime.transport.kis_mock.token.KisTokenLifecycle` — the SAME class the
KIS MOCK order transport uses, against the SAME custody scopes (``kis_mock.app_key``/
``kis_mock.app_secret``): KIS's own environment separation is enforced per TR family, not per
credential (this module's own imports' docstrings cite the measurement), so a quote TR and an
order TR authenticate with the same mock app key and may share one cached token. See
``tos_runtime.transport.kis_mock.token``'s own module docstring for the extraction's
behavior-preservation proof.

**The phantom-churn problem (a real design decision, not a detail).** KIS's quote TR has no
"since" parameter — every GET returns the CURRENT price, full stop. Naively minting an
observation on every poll, anchored at a fresh instant, would make EVERY poll look like a new
market event even when the market has not moved — manufacturing ticks with no real change, and
(per :mod:`tos_runtime.marketfeed.ports`'s own "field state is derived, never declared"
discipline) silently inflating "freshness" with no matching cause. This adapter instead tracks its
own LAST-CONSUMED content digest (over the mapped, admitted field tuple only — never the raw
response, so an unmapped, economically-insignificant KIS field changing does not, by itself, mint
a tick) and returns an EMPTY sequence — :attr:`~tos_runtime.marketfeed.ports.TickOutcome
.SKIPPED_NO_OBSERVATION`'s own "nothing new" contract — when the freshly polled content is
byte-identical to it. Only a genuine content change (or an emission that was never consumed — the
deferred-digest note above) mints an observation, and only then does
:func:`~tos_runtime.marketfeed.ports.anchor_observation` derive ``raw_event_id`` as
``{source_id}:{instrument}:{as_of_ms}:{content_digest}`` — combining the anchor instant with the
content digest so two observations can never collide even if a byte-identical body reappears at a
LATER instant (a legitimate, distinct observation: the market genuinely returned to a prior price
at a new instant) or, in the pathological case of two polls anchored in the same millisecond,
differ only in content (the digest disambiguates that too). This adapter never emits two
observations sharing a ``raw_event_id`` — the ambiguity :mod:`tos_runtime.marketfeed.ports`'s own
module docstring warns a producer must never create.

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
from typing import Any

from tos.dsl import ScalarValue

from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.marketfeed.ports import MonotonicAnchoredObservation, ObservationIntake
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
    "TokenStale",
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
    docstring for the full contract: monotonic request anchor finalized by the scheduler, shared
    token lifecycle, content-dedup against phantom churn with a deferred digest, configured field
    mapping)."""

    def __init__(
        self,
        *,
        config: KisQuoteTransportConfig,
        client: KisMockHttpClient,
        monotonic: MonotonicSource,
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
            monotonic: The injected monotonic clock, used for BOTH jobs this adapter has
                (module docstring's "one clock, two jobs" note): the shared token lifecycle's
                pacing/expiry bookkeeping, and the two request-anchor readings each poll
                takes. MUST be the same :class:`~tos_runtime.time.sources.MonotonicSource`
                INSTANCE this process's :class:`~tos_runtime.time.service
                .TrustworthyTimeService` was built with — the scheduler maps those readings
                through that service, and readings from a second source are not comparable
                against its own.
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
        self._monotonic = monotonic
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
        #: The last CONSUMED content digest, or ``None`` before this process's first consumed
        #: emission (module docstring's phantom-churn note). Process-local: a restart re-emits
        #: one confirmatory observation even if the market has not moved since the last
        #: emission before the restart — a legitimate, honest re-confirmation, not a bug (the
        #: durable snapshot store's own ``latest_as_of`` re-derivation in ``decide_tick`` still
        #: applies on top of this).
        self._last_content_digest: str | None = None
        #: The digest of the most recent EMITTED-but-not-yet-known-consumed observation
        #: (module docstring's deferred-digest note), or ``None`` when there is none
        #: outstanding. Promoted into :attr:`_last_content_digest` by
        #: :meth:`_commit_pending_if_consumed`.
        self._pending_digest: str | None = None
        #: The ``after_as_of_ms`` the PREVIOUS poll was asked from, and whether there was one.
        #: A plain ``None`` cannot carry both facts — ``None`` is also a legitimate mark (no
        #: snapshot issued yet) — so the flag is separate rather than overloaded.
        self._polled_once = False
        self._previous_after_as_of_ms: int | None = None

    def _commit_pending_if_consumed(self, after_as_of_ms: int | None) -> None:
        """Promote a pending digest to :attr:`_last_content_digest` iff the store's high-water
        mark has ADVANCED since the previous poll (module docstring's deferred-digest note).

        ``after_as_of_ms`` is ``DurableSnapshotStore.latest_as_of`` for this instrument, read
        by the scheduler immediately before this poll, and this scheduler is the only consumer
        of this instrument's snapshots — so an advance is exactly "the observation this intake
        emitted last pass was durably consumed". An unmoved mark means it was not (a failed
        time evaluation, an unanchorable pass, a refusal downstream), and the pending digest
        stays pending so the same quote is emitted again rather than dropped until the price
        moves.
        """
        advanced = (
            self._polled_once
            and after_as_of_ms is not None
            and (
                self._previous_after_as_of_ms is None
                or after_as_of_ms > self._previous_after_as_of_ms
            )
        )
        if advanced and self._pending_digest is not None:
            self._last_content_digest = self._pending_digest
            self._pending_digest = None
        self._polled_once = True
        self._previous_after_as_of_ms = after_as_of_ms

    def poll(
        self, *, instrument: str, after_as_of_ms: int | None
    ) -> Sequence[MonotonicAnchoredObservation]:
        """Return a single fresh, not-yet-anchored observation for ``instrument``, or none
        (module docstring).

        Args:
            instrument: MUST equal ``config.instrument`` — this intake serves exactly one,
                configured instrument (FORWARD-OBLIGATION-MS1 is unratified).
            after_as_of_ms: NOT used to filter — KIS's quote TR has no "since" parameter, so
                every poll fetches the CURRENT price and the phantom-churn content-dedup
                (module docstring) is what decides whether that counts as "new". It IS read,
                as the consumption signal :meth:`_commit_pending_if_consumed` needs.
                ``decide_tick``'s own ``SKIPPED_NOT_NEWER`` re-derivation (``scheduler.py``
                module docstring) still runs as a second, independent check downstream.

        Returns:
            Exactly one :class:`~tos_runtime.marketfeed.ports.MonotonicAnchoredObservation`
            when the polled content differs from the last CONSUMED one; an empty sequence
            otherwise ("nothing new" — a first-class answer, per
            :class:`~tos_runtime.marketfeed.ports.ObservationIntake`'s own docstring). The
            wall-clock anchor is the scheduler's to stamp (module docstring).

        Raises:
            KisQuoteAdapterError: ``instrument`` does not equal ``config.instrument``.
            TokenStale: The held token has expired and the reissue cooldown has not elapsed.
            KisMockConnectionError: The connection failed or was reset.
            KisMockTimeoutError: The request timed out.
            KisQuoteRejected: The broker's response carried ``rt_cd != "0"``.
            KisQuoteMalformedResponse: The response body was not usable (module docstring).
        """
        if instrument != self._config.instrument:
            raise KisQuoteAdapterError(
                f"KisQuoteObservationIntake: poll() called for instrument {instrument!r} but "
                f"this config is scoped to {self._config.instrument!r} — refusing to serve the "
                "wrong instrument's quote"
            )
        self._commit_pending_if_consumed(after_as_of_ms)

        access_token = (
            self._credential_session.ensure_token_string()
        )  # may raise TokenStale
        # The two anchor readings bracket the request as tightly as this module can: nothing
        # but the HTTP call itself lies between them (parsing happens after the second one).
        requested_monotonic_ms = self._monotonic.now_ms()
        response = self._fetch_quote(access_token)
        received_monotonic_ms = self._monotonic.now_ms()
        output = self._parse_output(response)
        fields = self._map_fields(output)

        content_digest = self._content_digest(fields)
        if content_digest == self._last_content_digest:
            return ()  # nothing new — module docstring's phantom-churn discipline

        self._pending_digest = content_digest
        return (
            MonotonicAnchoredObservation(
                instrument=instrument,
                fields=fields,
                source_id=self._config.source_id,
                content_digest=content_digest,
                requested_monotonic_ms=requested_monotonic_ms,
                received_monotonic_ms=received_monotonic_ms,
            ),
        )

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
