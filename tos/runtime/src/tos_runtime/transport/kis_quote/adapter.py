"""KIS quote intake implementing the runtime observation port.

The adapter performs one configured HTTP request per poll, for the one
instrument its config declares, and maps only the configured response fields
into a market observation. It never extracts an event timestamp from the
response body; this statement is about this adapter's code path and does not
claim that other KIS feeds lack execution times.

Observations are anchored on the request, on the MONOTONIC clock, and the
scheduler finalizes them. This adapter reads no wall clock at all: it takes a
:meth:`~tos_runtime.time.sources.MonotonicSource.now_ms` reading immediately
before the request goes out and another immediately after the response
arrives, and returns a
:class:`~tos_runtime.marketfeed.ports.MonotonicAnchoredObservation` carrying
both. :meth:`~tos_runtime.marketfeed.scheduler.TickScheduler.tick_once` maps
them onto that pass's own freshly evaluated reading
(:meth:`~tos_runtime.time.service.TrustworthyTimeService
.wall_clock_at_monotonic`) — ``as_of_ms`` from the request instant,
``received_ms`` from the response one — so this request's own round trip lands
in ``source_age``. Stamping
:meth:`~tos_runtime.time.service.TrustworthyTimeService.wall_clock_now` here
instead would reuse whatever reading the last ``evaluate()`` cached, which
runs after the pass's intake read and so carries the previous pass's time.

What the anchor still does NOT know, stated rather than implied: the response
body carries no event time, so how stale the data already was on the broker's
side remains unknown. Anchoring on the request start raises the age's LOWER
BOUND from zero to the HTTP round trip; it does not produce the true age. A
genuine source event time would need the KIS real-time WebSocket trade feed —
a different transport architecture this module does not attempt — not a
different stamp here.

The deferred-digest note: an unconsumed quote is re-emitted, not dropped.
``poll`` cannot filter on ``after_as_of_ms`` (the quote TR has no "since"
parameter), but it does READ it: that argument is the durable store's own
high-water mark, so it advances exactly when the previous pass's observation
was consumed. This adapter therefore holds a freshly emitted content digest as
pending and promotes it to the last-consumed digest only on a later poll whose
``after_as_of_ms`` has advanced. An observation the scheduler declined to
consume (``TickOutcome.SKIPPED_TIME_NOT_EVALUATED`` /
``SKIPPED_TIME_UNANCHORED`` — no ``store.put``, ``latest_as_of`` unmoved) is
re-emitted on the next pass rather than dropped until the price changes.

The phantom-churn note: every GET returns the CURRENT price, so minting an
observation on every poll would make each one look like a market event even
when the market has not moved. This adapter dedups on its last-consumed
content digest — taken over the mapped, admitted field tuple only, never the
raw response, so an unmapped KIS field changing does not by itself mint a tick
— and returns an EMPTY sequence, the ``SKIPPED_NO_OBSERVATION`` "nothing new"
contract, when the polled content is byte-identical to it. Only a genuine
content change, or an emission that was never consumed, mints an observation,
and only then does :func:`~tos_runtime.marketfeed.ports.anchor_observation`
derive ``raw_event_id`` as
``{source_id}:{instrument}:{as_of_ms}:{content_digest}``. Combining the anchor
instant with the content digest keeps a byte-identical body reappearing at a
LATER instant a distinct observation, and separates two polls anchored in the
same millisecond by content; this adapter never emits two observations sharing
a ``raw_event_id``.

One clock, two jobs — and it must be THE process's monotonic source. A single
injected :class:`~tos_runtime.time.sources.MonotonicSource` serves both the
shared :class:`~tos_runtime.transport.kis_mock.token.KisTokenLifecycle`'s
age/cooldown bookkeeping and the two request-anchor readings, and the stricter
requirement governs. Token pacing needs only relative elapsed time from any
consistent source, while the anchor readings are mapped by
``wall_clock_at_monotonic``, which compares them against the time service's
own readings — and the :class:`~tos_runtime.time.sources.MonotonicSource` port
guarantees readings are comparable only WITHIN one instance. The injected
source must therefore be the very object this process's
:class:`~tos_runtime.time.service.TrustworthyTimeService` was built with;
compose passes exactly that, and ``tests/compose/
test_marketfeed_intake_kind_wiring.py`` pins the object identity. A source
with an origin of its own would put every mapping outside the domain and every
pass would answer ``SKIPPED_TIME_UNANCHORED``.

The note against reintroducing a wall clock here: token validity, observation
anchoring, and wall-clock TRUST are three different facts. The first two live
on the monotonic clock in this module; the third is the scheduler's to apply
after its own evaluation. Deriving token pacing from wall-clock trust makes a
live token unusable for a reason unrelated to the token, and stamping
``as_of_ms`` from a cached wall-clock reading is the defect the request anchor
above removed.

Credential access stays inside the shared session seam, and field mapping is
configured, never hardcoded. ``KisQuoteTransportConfig.field_mapping`` names
exactly which KIS wire field keys this adapter reads and which
``critical_input_policy.yaml``-admitted ``field_key`` each feeds; a response
field not named there is dropped here, since the CIP's own ∅-floor already
drops anything it does not itself admit. No unit/scale/multiplier/sign
interpretation happens in this module — the raw KIS scalar value is carried
through UNCHANGED, because that interpretation belongs to the CIP-governed
value-derivation layer, never to a collector.
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
