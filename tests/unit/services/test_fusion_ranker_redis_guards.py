"""Redis-failure guards for FusionRanker (operator review 2026-09-06).

With Redis connect_retries=0 (fail-fast connect, shared/streaming/client.py),
redis-py's built-in 3 retries no longer absorb a transient ConnectionError —
a single blip now raises immediately. These tests pin the minimal guards
added at the two unprotected call sites: the sequential GET fallback in
``_mget`` and the cache-key SET in ``_publish_payload``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import redis

from services.fusion_ranker import FusionRanker, FusionRankerConfig


@pytest.fixture
def ranker():
    with (
        patch(
            "services.fusion_ranker.RedisClient.get_client", return_value=MagicMock()
        ),
        patch("services.fusion_ranker.StreamPublisher", return_value=MagicMock()),
    ):
        return FusionRanker(FusionRankerConfig())


class TestMgetSequentialFallbackGuard:
    def test_mget_unavailable_and_get_raises_treated_as_missing(self, ranker):
        """No .mget on the client (falls back to sequential GET); one GET
        raises ConnectionError — must return None for that key, not raise.
        """
        fake_redis = MagicMock(spec=["get"])  # no mget attribute at all
        fake_redis.get.side_effect = [
            "value-a",
            redis.exceptions.ConnectionError("down"),
            "value-c",
        ]
        ranker.redis = fake_redis

        result = ranker._mget("key-a", "key-b", "key-c")

        assert result == ["value-a", None, "value-c"]

    def test_mget_raises_and_sequential_get_also_raises_for_one_key(self, ranker):
        """MGET itself fails (existing fallback path); the sequential GET
        fallback then hits a Redis error on one key — still no raise.
        """
        fake_redis = MagicMock()
        fake_redis.mget.side_effect = redis.exceptions.ConnectionError("down")
        fake_redis.get.side_effect = [
            redis.exceptions.ConnectionError("down"),
            "value-b",
        ]
        ranker.redis = fake_redis

        result = ranker._mget("key-a", "key-b")

        assert result == [None, "value-b"]

    def test_mget_success_path_unaffected(self, ranker):
        fake_redis = MagicMock()
        fake_redis.mget.return_value = ["v1", "v2"]
        ranker.redis = fake_redis

        result = ranker._mget("key-a", "key-b")

        assert result == ["v1", "v2"]
        fake_redis.get.assert_not_called()


class TestPublishPayloadCacheSetGuard:
    def test_redis_set_failure_logs_warning_and_returns_false(self, ranker, caplog):
        """output_key IS the published/latest-value contract for GET-based
        consumers, so a failed cache SET must not raise out of the cycle
        (Redis connect_retries=0 — a blip raises once instead of the old
        absorbed retries) but also must not be reported as a successful
        publish (reviewer guidance 2026-09-06): return False and do not mark
        the fingerprint as delivered, so the next cycle retries this exact
        payload instead of skipping it as an already-published duplicate.
        """
        fake_publisher = MagicMock()
        fake_redis = MagicMock()
        fake_redis.set.side_effect = redis.exceptions.ConnectionError("down")
        ranker.publisher = fake_publisher
        ranker.redis = fake_redis

        payload = {"codes": ["005930"], "names": {"005930": "Samsung"}}

        with caplog.at_level("WARNING"):
            result = ranker._publish_payload(payload)

        assert result is False
        fake_publisher.publish.assert_called_once_with(payload)
        fake_redis.set.assert_called_once()
        assert any(
            "Failed to publish fused trade targets to Redis (key=" in rec.message
            for rec in caplog.records
        )
        # Fingerprint must NOT update on failure, so an unchanged payload is
        # retried next cycle instead of being treated as an already-published
        # duplicate.
        assert ranker._last_payload_fingerprint == ""

    def test_redis_set_failure_then_success_retries_and_delivers(self, ranker):
        """A failed cycle must not poison future cycles: the same payload
        retried after Redis recovers should publish normally.
        """
        fake_publisher = MagicMock()
        fake_redis = MagicMock()
        fake_redis.set.side_effect = [redis.exceptions.ConnectionError("down"), None]
        ranker.publisher = fake_publisher
        ranker.redis = fake_redis

        payload = {"codes": ["005930"], "names": {"005930": "Samsung"}}

        assert ranker._publish_payload(payload) is False
        assert ranker._publish_payload(dict(payload)) is True

        assert fake_publisher.publish.call_count == 2
        assert fake_redis.set.call_count == 2

    def test_redis_set_success_path_unaffected(self, ranker):
        fake_publisher = MagicMock()
        fake_redis = MagicMock()
        ranker.publisher = fake_publisher
        ranker.redis = fake_redis

        payload = {"codes": ["005930"], "names": {"005930": "Samsung"}}

        result = ranker._publish_payload(payload)

        assert result is True
        fake_redis.set.assert_called_once()

    def test_duplicate_payload_still_skips_without_touching_redis(self, ranker):
        fake_publisher = MagicMock()
        fake_redis = MagicMock()
        ranker.publisher = fake_publisher
        ranker.redis = fake_redis

        payload = {"codes": ["005930"], "names": {"005930": "Samsung"}}
        assert ranker._publish_payload(payload) is True
        fake_redis.reset_mock()
        fake_publisher.reset_mock()

        assert ranker._publish_payload(dict(payload)) is False
        fake_publisher.publish.assert_not_called()
        fake_redis.set.assert_not_called()
