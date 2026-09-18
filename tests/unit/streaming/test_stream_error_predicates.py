"""Pin the vanished-stream predicates to real redis-py error objects.

The monitor recovery hinges on a substring match against messages redis-py
hands through unstripped: ``BaseParser.parse_error`` only removes the leading
code for codes listed in ``EXCEPTION_CLASSES``, and neither ``NOGROUP`` nor
``UNBLOCKED`` is listed. A redis-py upgrade that adds either one would strip
the prefix and silently disarm the recovery while every stubbed
``RuntimeError("NOGROUP ...")`` test in the repo stayed green. These tests
assert the predicates against the verbatim production strings and against
redis-py's own parser, so that upgrade fails loudly here instead.
"""

from __future__ import annotations

import pytest

# Private module path on purpose: this is the code that decides whether the
# error code survives into the message. If redis-py moves it, this import
# fails loudly — which is the point, the contract needs re-checking then.
from redis._parsers.base import BaseParser
from redis.exceptions import ResponseError

from shared.streaming.stage import (
    is_missing_consumer_group_error,
    is_vanished_stream_read_error,
)

# Verbatim from the paper stack's retained stock_monitor traceback.
NOGROUP_MESSAGE = (
    "NOGROUP No such key 'signal.final.stock' or consumer group "
    "'stock_monitor' in XREADGROUP with GROUP option"
)
# Verbatim from the first monitor_stream_read_error of each production episode:
# Redis sends this to a client already blocked in XREADGROUP when the key goes.
UNBLOCKED_MESSAGE = "UNBLOCKED the stream key no longer exists"


def test_production_nogroup_response_error_matches_both_predicates() -> None:
    exc = ResponseError(NOGROUP_MESSAGE)

    assert is_missing_consumer_group_error(exc)
    assert is_vanished_stream_read_error(exc)


def test_production_unblocked_response_error_matches_only_the_wider_predicate() -> None:
    exc = ResponseError(UNBLOCKED_MESSAGE)

    assert is_vanished_stream_read_error(exc)
    # the narrow predicate keeps its NOGROUP-only meaning for StreamStage
    assert not is_missing_consumer_group_error(exc)


@pytest.mark.parametrize(
    "message",
    [
        "WRONGTYPE Operation against a key holding the wrong kind of value",
        "ERR The XGROUP subcommand requires the key to exist",
        # an operator running CLIENT UNBLOCK is not a vanished key
        "UNBLOCKED client unblocked via CLIENT UNBLOCK",
    ],
)
def test_unrelated_response_error_matches_neither_predicate(message: str) -> None:
    exc = ResponseError(message)

    assert not is_missing_consumer_group_error(exc)
    assert not is_vanished_stream_read_error(exc)


@pytest.mark.parametrize("message", [NOGROUP_MESSAGE, UNBLOCKED_MESSAGE])
def test_redis_parser_leaves_the_error_code_in_the_message(message: str) -> None:
    """Tripwire: redis-py must keep passing these codes through unstripped."""
    exc = BaseParser.parse_error(message)

    assert isinstance(exc, ResponseError)
    assert str(exc) == message
    assert is_vanished_stream_read_error(exc)
