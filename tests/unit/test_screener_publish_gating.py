"""End-to-end coverage for the screener's publish-and-mark callers.

PR #646 (commit 09b19de3) made ``_safe_set`` fail-open — the two publish
sites for the universe-latest and dip-latest caches only advance their
dedup state (signature / publish-time) when the cache write actually
succeeds, so a transient Redis outage causes a retry on the next loop
iteration instead of silently "succeeding" and never re-publishing.

``_safe_set`` itself already has direct unit coverage
(``test_screener_safe_set.py``). This file drives the two callers —
extracted from ``run_screener`` as ``_publish_universe_snapshot`` and
``_publish_dip_snapshot`` (2026-09-06 review follow-up, behavior-identical
to the inline blocks they replaced) — end to end across two simulated loop
iterations each, so the retry semantics are verified as a caller-visible
behavior rather than only by inspection.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import redis

from services.screener import _publish_dip_snapshot, _publish_universe_snapshot

UNIVERSE_KEY = "system:universe:latest"
DIP_KEY = "system:dip_candidates:latest"
HEARTBEAT = 60.0


def _payload(codes: list[str]) -> dict:
    return {"codes": codes, "scores": {}, "names": {}, "generated_at": "t0"}


class TestPublishUniverseSnapshot:
    def test_success_publishes_stream_then_cache_and_marks_state(self):
        redis_client = MagicMock()
        publisher = MagicMock()
        codes = ["005930", "000660"]
        payload = _payload(codes)
        call_order: list[str] = []
        publisher.publish.side_effect = lambda *_a, **_k: call_order.append("stream")
        redis_client.set.side_effect = lambda *_a, **_k: call_order.append("cache")

        signature, publish_time = _publish_universe_snapshot(
            redis_client=redis_client,
            publisher=publisher,
            universe_latest_key=UNIVERSE_KEY,
            codes=codes,
            payload=payload,
            now=100.0,
            last_signature=None,
            last_publish_time=0.0,
            heartbeat_seconds=HEARTBEAT,
        )

        publisher.publish.assert_called_once_with(payload)
        redis_client.set.assert_called_once_with(
            UNIVERSE_KEY, json.dumps(payload, ensure_ascii=False), ex=86400
        )
        assert call_order == [
            "stream",
            "cache",
        ], "stream publish must precede cache set"
        assert signature is not None
        assert publish_time == 100.0

    def test_same_codes_within_heartbeat_does_not_republish(self):
        redis_client = MagicMock()
        publisher = MagicMock()
        codes = ["005930"]
        payload = _payload(codes)

        signature, publish_time = _publish_universe_snapshot(
            redis_client=redis_client,
            publisher=publisher,
            universe_latest_key=UNIVERSE_KEY,
            codes=codes,
            payload=payload,
            now=100.0,
            last_signature=None,
            last_publish_time=0.0,
            heartbeat_seconds=HEARTBEAT,
        )
        publisher.reset_mock()
        redis_client.reset_mock()

        # Second iteration, same codes, well within the heartbeat window.
        signature2, publish_time2 = _publish_universe_snapshot(
            redis_client=redis_client,
            publisher=publisher,
            universe_latest_key=UNIVERSE_KEY,
            codes=codes,
            payload=payload,
            now=105.0,
            last_signature=signature,
            last_publish_time=publish_time,
            heartbeat_seconds=HEARTBEAT,
        )

        publisher.publish.assert_not_called()
        redis_client.set.assert_not_called()
        assert signature2 == signature
        assert publish_time2 == publish_time

    def test_redis_set_failure_does_not_advance_state_and_does_not_raise(self):
        redis_client = MagicMock()
        redis_client.set.side_effect = redis.exceptions.ConnectionError("down")
        publisher = MagicMock()
        codes = ["005930"]
        payload = _payload(codes)

        signature, publish_time = _publish_universe_snapshot(
            redis_client=redis_client,
            publisher=publisher,
            universe_latest_key=UNIVERSE_KEY,
            codes=codes,
            payload=payload,
            now=100.0,
            last_signature=None,
            last_publish_time=0.0,
            heartbeat_seconds=HEARTBEAT,
        )

        # Stream publish still happened (fire-and-forget), but dedup state
        # was NOT advanced because the cache write failed.
        publisher.publish.assert_called_once_with(payload)
        assert signature is None
        assert publish_time == 0.0

    def test_redis_failure_then_retry_republishes_same_codes(self):
        redis_client = MagicMock()
        publisher = MagicMock()
        codes = ["005930"]
        payload = _payload(codes)

        redis_client.set.side_effect = redis.exceptions.ConnectionError("down")
        signature1, publish_time1 = _publish_universe_snapshot(
            redis_client=redis_client,
            publisher=publisher,
            universe_latest_key=UNIVERSE_KEY,
            codes=codes,
            payload=payload,
            now=100.0,
            last_signature=None,
            last_publish_time=0.0,
            heartbeat_seconds=HEARTBEAT,
        )
        assert signature1 is None  # cache write failed, no state advance

        # Next iteration: Redis has recovered, same code set is retried
        # (not skipped) because the signature never advanced.
        redis_client.set.side_effect = None
        redis_client.reset_mock()
        publisher.reset_mock()

        signature2, publish_time2 = _publish_universe_snapshot(
            redis_client=redis_client,
            publisher=publisher,
            universe_latest_key=UNIVERSE_KEY,
            codes=codes,
            payload=payload,
            now=101.0,
            last_signature=signature1,
            last_publish_time=publish_time1,
            heartbeat_seconds=HEARTBEAT,
        )

        publisher.publish.assert_called_once_with(payload)
        redis_client.set.assert_called_once()
        assert signature2 is not None
        assert publish_time2 == 101.0


class TestPublishDipSnapshot:
    def test_success_publishes_cache_and_marks_state(self):
        redis_client = MagicMock()
        dip_codes = ["035720"]
        dip_payload = {"codes": dip_codes, "scores": {}, "names": {}, "info": {}}

        signature, publish_time = _publish_dip_snapshot(
            redis_client=redis_client,
            dip_latest_key=DIP_KEY,
            dip_codes=dip_codes,
            dip_payload=dip_payload,
            now=200.0,
            last_signature=None,
            last_publish_time=0.0,
            heartbeat_seconds=HEARTBEAT,
        )

        redis_client.set.assert_called_once_with(
            DIP_KEY,
            json.dumps(dip_payload, ensure_ascii=False),
            ex=86400,
        )
        assert signature is not None
        assert publish_time == 200.0

    def test_same_codes_within_heartbeat_does_not_republish(self):
        redis_client = MagicMock()
        dip_codes = ["035720"]
        dip_payload = {"codes": dip_codes, "scores": {}, "names": {}, "info": {}}

        signature, publish_time = _publish_dip_snapshot(
            redis_client=redis_client,
            dip_latest_key=DIP_KEY,
            dip_codes=dip_codes,
            dip_payload=dip_payload,
            now=200.0,
            last_signature=None,
            last_publish_time=0.0,
            heartbeat_seconds=HEARTBEAT,
        )
        redis_client.reset_mock()

        signature2, publish_time2 = _publish_dip_snapshot(
            redis_client=redis_client,
            dip_latest_key=DIP_KEY,
            dip_codes=dip_codes,
            dip_payload=dip_payload,
            now=205.0,
            last_signature=signature,
            last_publish_time=publish_time,
            heartbeat_seconds=HEARTBEAT,
        )

        redis_client.set.assert_not_called()
        assert signature2 == signature
        assert publish_time2 == publish_time

    def test_redis_set_failure_does_not_advance_state_and_does_not_raise(self):
        redis_client = MagicMock()
        redis_client.set.side_effect = redis.exceptions.ConnectionError("down")
        dip_codes = ["035720"]
        dip_payload = {"codes": dip_codes, "scores": {}, "names": {}, "info": {}}

        signature, publish_time = _publish_dip_snapshot(
            redis_client=redis_client,
            dip_latest_key=DIP_KEY,
            dip_codes=dip_codes,
            dip_payload=dip_payload,
            now=200.0,
            last_signature=None,
            last_publish_time=0.0,
            heartbeat_seconds=HEARTBEAT,
        )

        assert signature is None
        assert publish_time == 0.0

    def test_redis_failure_then_retry_republishes_same_codes(self):
        redis_client = MagicMock()
        dip_codes = ["035720"]
        dip_payload = {"codes": dip_codes, "scores": {}, "names": {}, "info": {}}

        redis_client.set.side_effect = redis.exceptions.ConnectionError("down")
        signature1, publish_time1 = _publish_dip_snapshot(
            redis_client=redis_client,
            dip_latest_key=DIP_KEY,
            dip_codes=dip_codes,
            dip_payload=dip_payload,
            now=200.0,
            last_signature=None,
            last_publish_time=0.0,
            heartbeat_seconds=HEARTBEAT,
        )
        assert signature1 is None

        redis_client.set.side_effect = None
        redis_client.reset_mock()

        signature2, publish_time2 = _publish_dip_snapshot(
            redis_client=redis_client,
            dip_latest_key=DIP_KEY,
            dip_codes=dip_codes,
            dip_payload=dip_payload,
            now=201.0,
            last_signature=signature1,
            last_publish_time=publish_time1,
            heartbeat_seconds=HEARTBEAT,
        )

        redis_client.set.assert_called_once()
        assert signature2 is not None
        assert publish_time2 == 201.0
