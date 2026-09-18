"""Pin what ``recover_missing_consumer_group`` claims in the log.

The helper is called on *every* stream a caller reads, not just the one that
vanished (PR #739 made both monitor daemons recover both of their streams on
any vanished-stream error). It used to log ``consumer group missing;
recreated`` whenever the group ended up usable, so the healthy stream — which
takes the BUSYGROUP path — produced the same line as the broken one. The paper
stack's 2026-09-18 13:31:54 NOGROUP injection printed exactly that pair, and an
operator reading it concludes both streams broke.

The message is also the alerting surface for the monitor daemons going blind
(2026-09-17 00:00 → 2026-09-18 12:34 passed unnoticed), so it has to be
``format_audit_kv`` ``event=`` form like the rest of the monitor path, not
free-form prose.
"""

from __future__ import annotations

import logging

import pytest

from shared.streaming.stage import (
    ConsumerGroupEnsure,
    recover_missing_consumer_group,
)

_STREAM = "signal.final.futures.shadow"
_GROUP = "futures_monitor"


class _StubRedis:
    """XGROUP CREATE double: creates, reports BUSYGROUP, or fails outright."""

    def __init__(self, *, existing: bool = False, error: str | None = None) -> None:
        self.existing = existing
        self.error = error
        self.created: list[tuple[str, str]] = []

    async def xgroup_create(self, stream, group, *, id="0", mkstream=False):
        self.created.append((stream, group))
        if self.error is not None:
            raise RuntimeError(self.error)
        if self.existing:
            raise RuntimeError("BUSYGROUP Consumer Group name already exists")


def _events(caplog, name: str) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if f"event={name}" in record.getMessage()
    ]


def test_outcome_truthiness_matches_usability() -> None:
    """``__bool__`` must answer the question a caller means by ``if not ...``.

    Every member is a non-empty string, so the inherited truthiness would make
    ``FAILED`` truthy and a ``not`` test silently always false.
    """
    assert bool(ConsumerGroupEnsure.CREATED) is True
    assert bool(ConsumerGroupEnsure.EXISTED) is True
    assert bool(ConsumerGroupEnsure.FAILED) is False


@pytest.mark.asyncio
async def test_busygroup_recovery_reports_existed_without_claiming_a_recreate(
    caplog,
) -> None:
    """The healthy sibling stream must not be reported as broken.

    The outcome — not a bool — is what the monitor daemons branch on: EXISTED
    on every stream means nothing was missing, so the read error had another
    cause and retrying immediately would spin.
    """
    redis = _StubRedis(existing=True)
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")

    assert (
        await recover_missing_consumer_group(redis, _STREAM, _GROUP)
        is ConsumerGroupEnsure.EXISTED
    )

    assert _events(caplog, "consumer_group_recovered") == []
    assert not any(
        "recreated" in record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.WARNING
    )
    assert _events(caplog, "consumer_group_already_present") == [
        f"event=consumer_group_already_present stream={_STREAM} consumer_group={_GROUP}"
    ]
    assert [
        r.levelno for r in caplog.records if "already_present" in r.getMessage()
    ] == [logging.DEBUG]


@pytest.mark.asyncio
async def test_genuine_recreate_warns_once_in_audit_kv_form(caplog) -> None:
    redis = _StubRedis()
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")

    assert (
        await recover_missing_consumer_group(redis, _STREAM, _GROUP)
        is ConsumerGroupEnsure.CREATED
    )

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert [r.getMessage() for r in warnings] == [
        f"event=consumer_group_recovered stream={_STREAM} consumer_group={_GROUP}"
    ]
    assert redis.created == [(_STREAM, _GROUP)]


@pytest.mark.asyncio
async def test_failed_ensure_reports_failed_and_keeps_the_traceback(caplog) -> None:
    redis = _StubRedis(error="NOPERM this user has no permissions to run 'xgroup'")
    caplog.set_level(logging.DEBUG, logger="shared.streaming.stage")

    outcome = await recover_missing_consumer_group(redis, _STREAM, _GROUP)
    assert outcome is ConsumerGroupEnsure.FAILED
    assert not outcome

    failures = [
        record
        for record in caplog.records
        if "event=consumer_group_ensure_failed" in record.getMessage()
    ]
    assert len(failures) == 1
    assert failures[0].levelno == logging.WARNING
    assert failures[0].exc_info is not None
    assert (
        failures[0].getMessage()
        == f"event=consumer_group_ensure_failed stream={_STREAM} consumer_group={_GROUP}"
    )
    # a failed recreate never claims to have recovered anything
    assert _events(caplog, "consumer_group_recovered") == []


@pytest.mark.asyncio
async def test_bytes_stream_name_is_decoded_into_the_event(caplog) -> None:
    """XREADGROUP hands byte keys back; the alert must still name the stream."""
    caplog.set_level(logging.WARNING, logger="shared.streaming.stage")

    assert await recover_missing_consumer_group(_StubRedis(), _STREAM.encode(), _GROUP)

    assert _events(caplog, "consumer_group_recovered") == [
        f"event=consumer_group_recovered stream={_STREAM} consumer_group={_GROUP}"
    ]
