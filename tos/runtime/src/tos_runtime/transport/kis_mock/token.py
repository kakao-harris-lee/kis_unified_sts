"""``KisTokenLifecycle`` — the shared KIS OAuth token issuance/expiry/reissue-cooldown state
machine (extracted for the TOS tick-source wave, W2 lane, plan
``docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`` §4 W2 step 0 measurement 2).

**Why this was extracted.** :class:`~tos_runtime.transport.kis_mock.adapter.KisMockTransport`
(T1, plan ``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md`` §2 결정 4) already carried this
exact state machine, entangled with order-only concerns (pacing, the wire codec, the seal lookup).
Measurement: the token-lifecycle slice (state fields + ``_ensure_token_string``/``_issue_token``)
touches none of those order-only collaborators — it reads only ``client.issue_token``, ``custody``,
the two custody scope names, ``monotonic``, ``token_path``, ``token_reissue_min_interval_s``, and
``evidence_sink``. That made it a clean, behavior-preserving extraction rather than a "not safe to
split" case. The KIS 모의투자 quote intake (:mod:`tos_runtime.transport.kis_quote`) needs the
IDENTICAL state machine against the IDENTICAL credential: KIS enforces environment separation per
TR family, not per credential
(``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:4351-4356`` —
"환경 분리는 도메인 단위가 아니라 TR 계열 단위로 강제된다"), so a quote TR and an order TR issued
against the same mock app key share one authenticated session, not two separate credential
universes each needing its own token cache. Duplicating this state machine a second time would be
exactly the "registry with an unpinned satellite" failure this repo has hit before — two independent
copies of one stateful lifecycle that silently drift.

**Behavior-preservation.** This is a pure extraction, not a rewrite: every field name, every
branch, every evidence-kind string, and :class:`TokenStale`'s own raise site are unchanged from
``KisMockTransport``'s former inline methods.
:class:`~tos_runtime.transport.kis_mock.adapter.KisMockTransport` now holds one
:class:`KisTokenLifecycle` instance and delegates to it; the ONE deliberate, non-breaking change is
that a malformed token response now raises this module's own :class:`TokenResponseError` instead of
the client module's :class:`~tos_runtime.transport.kis_mock.client.KisMockClientError` — a change
made so this module needs no import of ``client.py`` at all (:class:`TokenIssuingClient` is a
structural Protocol, satisfied by :class:`~tos_runtime.transport.kis_mock.client.KisMockHttpClient`
without a hard import edge). No existing test asserts on that exception type (verified by grep over
``tests/transport/kis_mock/test_adapter.py`` before this change), so this is not a behavior change
any test suite observes — the adapter's full pre-existing test suite, INCLUDING every token-lifecycle
assertion, passes unchanged against the refactored adapter (see the W2 report for the exact
``passed`` count before and after).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``typing``,
``collections.abc``) + ``tos_runtime.custody``/``tos_runtime.time`` only. No ``tos.*`` kernel
import (nothing here is kernel-typed), no third-party import, no ``os.environ``, no network (the
one network call this module drives is made by the injected ``client``, never by this module
itself).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "EvidenceRecorder",
    "KisTokenLifecycle",
    "TokenIssuingClient",
    "TokenResponseError",
    "TokenStale",
]


class TokenStale(Exception):
    """The held token has expired and the reissue cooldown has not yet elapsed — this attempt
    does not reissue (decision 4). A later attempt, once the cooldown has elapsed, may.
    """


class TokenResponseError(Exception):
    """The token endpoint's response body did not carry a usable ``access_token``/``expires_in``
    pair. Distinct from any HTTP-client-level exception (module docstring) so a caller can catch
    a token-SHAPE fault without also catching an unrelated client fault."""


@runtime_checkable
class TokenIssuingClient(Protocol):
    """The one client capability this lifecycle needs — satisfied structurally by
    :class:`~tos_runtime.transport.kis_mock.client.KisMockHttpClient` (and by any quote-side
    client exposing the same method) with no import edge to that module required."""

    def issue_token(
        self, app_key: bytes, app_secret: bytes, *, path: str
    ) -> dict[str, Any]:
        """POST the token endpoint exactly once; return the raw parsed body.

        Raises:
            Whatever connection/timeout exception the concrete client raises — this Protocol
            makes no promise about that hierarchy; :meth:`KisTokenLifecycle.ensure_token_string`
            propagates it unchanged.
        """
        ...


@runtime_checkable
class EvidenceRecorder(Protocol):
    """Records one evidence entry. The compose root adapts this to the real evidence store — this
    package only depends on the shape (``record(kind, fields)``)."""

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        """Durably (from the caller's perspective) record one evidence entry.

        Args:
            kind: The caller's own evidence-kind vocabulary (this module itself emits only
                ``TRANSPORT_TOKEN_STALE``, unchanged from the pre-extraction inline behavior).
            fields: The record's own fields — never the secret bytes of any loaded credential,
                and never a bearer access token.
        """
        ...


class KisTokenLifecycle:
    """The KIS OAuth token issuance/expiry/reissue-cooldown state machine (module docstring).

    One instance is scoped to one custody-loaded app key/secret pair and one token endpoint —
    a caller that talks to two distinct KIS environments (e.g. MOCK and REAL, were that ever
    permitted) needs two separate instances, never one shared instance re-pointed mid-life.
    """

    def __init__(
        self,
        *,
        client: TokenIssuingClient,
        custody: CredentialCustody,
        app_key_scope: str,
        app_secret_scope: str,
        monotonic: MonotonicSource,
        token_path: str,
        token_reissue_min_interval_s: int,
        evidence_sink: EvidenceRecorder,
    ) -> None:
        """Wire this lifecycle's dependencies (all injected — no ambient state).

        Args:
            client: The token-issuing HTTP client.
            custody: The credential source — ``app_key_scope``/``app_secret_scope`` must both be
                scopes ``custody`` actually provisions.
            app_key_scope: The custody scope name for the KIS app key.
            app_secret_scope: The custody scope name for the KIS app secret.
            monotonic: The injected monotonic clock (never ``time.time()``).
            token_path: The token endpoint's path.
            token_reissue_min_interval_s: The minimum spacing between two ``issue_token`` calls
                (module docstring — a reissue-RATE limit, not a token lifetime).
            evidence_sink: Records this lifecycle's own evidence entries
                (``TRANSPORT_TOKEN_STALE``).
        """
        self._client = client
        self._custody = custody
        self._app_key_scope = app_key_scope
        self._app_secret_scope = app_secret_scope
        self._monotonic = monotonic
        self._token_path = token_path
        self._token_reissue_min_interval_s = token_reissue_min_interval_s
        self._evidence = evidence_sink

        self._access_token: str | None = None
        self._token_issued_at_ms: int | None = None
        self._token_expires_in_s: int | None = None
        self._last_token_issue_attempt_ms: int | None = None

    def ensure_token_string(self) -> str:
        """Return the bearer access token string for the call about to happen.

        Raises:
            TokenStale: The held token (or the absence of one) is stale and the reissue cooldown
                has not elapsed since the last issuance attempt.
        """
        now = self._monotonic.now_ms()
        needs_fresh = self._access_token is None or (
            self._token_issued_at_ms is not None
            and self._token_expires_in_s is not None
            and (now - self._token_issued_at_ms) >= self._token_expires_in_s * 1000
        )
        if not needs_fresh:
            assert self._access_token is not None
            return self._access_token

        if self._last_token_issue_attempt_ms is not None:
            elapsed_since_last_attempt_ms = now - self._last_token_issue_attempt_ms
            cooldown_ms = self._token_reissue_min_interval_s * 1000
            if elapsed_since_last_attempt_ms < cooldown_ms:
                # (review F8, preserved verbatim) the burned attempt's evidence explains exactly
                # how much cooldown remained, so a reader of the evidence store understands why
                # this attempt was refused rather than reissued.
                self._evidence(
                    "TRANSPORT_TOKEN_STALE",
                    {
                        "reissue_cooldown_s": self._token_reissue_min_interval_s,
                        "elapsed_ms": elapsed_since_last_attempt_ms,
                        "cooldown_remaining_ms": cooldown_ms
                        - elapsed_since_last_attempt_ms,
                    },
                )
                raise TokenStale(
                    "KisTokenLifecycle: token is stale/absent and the reissue cooldown "
                    f"({self._token_reissue_min_interval_s}s) has not elapsed since the last "
                    "issuance attempt — refusing to reissue within this attempt (decision 4)"
                )

        self._last_token_issue_attempt_ms = now
        self._issue_token()
        assert self._access_token is not None
        return self._access_token

    def _issue_token(self) -> None:
        """(review F5, preserved verbatim) The app key/secret are loaded inside the narrowest
        possible ``with`` block — wrapped directly around the one ``issue_token`` network call.
        """
        with (
            self._custody.load(self._app_key_scope) as key_handle,
            self._custody.load(self._app_secret_scope) as secret_handle,
        ):
            body = self._client.issue_token(
                key_handle.value(), secret_handle.value(), path=self._token_path
            )
        access_token = body.get("access_token")
        expires_in = body.get("expires_in")
        if not isinstance(access_token, str) or not access_token:
            raise TokenResponseError(
                "KisTokenLifecycle: token response missing a usable access_token"
            )
        if (
            not isinstance(expires_in, int)
            or isinstance(expires_in, bool)
            or expires_in <= 0
        ):
            raise TokenResponseError(
                "KisTokenLifecycle: token response missing a usable expires_in"
            )
        self._access_token = access_token
        self._token_expires_in_s = expires_in
        self._token_issued_at_ms = self._monotonic.now_ms()
