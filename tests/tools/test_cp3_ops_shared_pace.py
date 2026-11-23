"""tools/tos_cp3/ops — the mock app key's shared pace file, as tos_runtime keeps it (#1161)."""

from __future__ import annotations

import fcntl
import os
import stat
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.tos_cp3.ops import mock_flat_check as flat
from tools.tos_cp3.ops import mock_flatten as flatten
from tools.tos_cp3.ops.shared_pace import (
    DEFAULT_WINDOW_MARGIN_S,
    TRANSPORT_YAML_ENV,
    SharedAppKeyPace,
    SharedPacedCallPacer,
    SharedPaceTerms,
    SharedPaceUnavailable,
    attach_shared_pace,
    load_shared_pace_terms,
    resolve_transport_yaml,
)

_PACE_FILE = "/var/lib/tos/kis-mock-token/stock-mock.pace"
_FP = "ee1bdb5f1ca2"


class _StubCreds:
    cano = "50000000"
    acnt_prdt_cd = "01"
    account_no = "5000000001"


class _Clock:
    """A wall clock the test moves (mirrors the runtime gate's own test clock)."""

    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.now = start
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _pace(
    path: Path,
    clock: _Clock,
    *,
    max_rps: float = 2.0,
    margin: float = 0.25,
    slot_budget_s: float = 4.0,
) -> SharedAppKeyPace:
    return SharedAppKeyPace(
        SharedPaceTerms(
            path=path,
            max_rps=max_rps,
            window_margin_s=margin,
            slot_wait_budget_s=slot_budget_s,
        ),
        now_epoch_s=clock,
        sleep=clock.sleep,
    )


def _yaml(tmp_path: Path, **overrides: Any) -> Path:
    raw = {
        "mode": "live",
        "shared_pacer_path": _PACE_FILE,
        "shared_max_rps": 2.0,
        "app_key_request_wait_budget_ms": 4000,
    }
    raw.update(overrides)
    path = tmp_path / "kis_mock_transport.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


# ── the terms come off the tenant's own transport yaml ─────────────────────


def test_the_terms_come_off_the_tenants_transport_yaml(tmp_path: Path) -> None:
    terms = load_shared_pace_terms(_yaml(tmp_path, shared_window_margin_s=0.4))
    assert terms.path == Path(_PACE_FILE)
    assert terms.max_rps == 2.0
    assert terms.window_margin_s == 0.4
    assert terms.slot_wait_budget_s == 4.0


def test_a_home_relative_pace_file_is_expanded_not_refused(tmp_path: Path) -> None:
    """The runtime's loader expands `~` before the absolute check; so must this one."""
    terms = load_shared_pace_terms(
        _yaml(tmp_path, shared_pacer_path="~/.local/state/tos/stock-mock.pace")
    )
    assert terms.path == Path.home() / ".local/state/tos/stock-mock.pace"
    assert terms.path.is_absolute()


def test_an_undeclared_margin_is_the_same_default_the_runtime_uses(
    tmp_path: Path,
) -> None:
    assert load_shared_pace_terms(_yaml(tmp_path)).window_margin_s == 0.25
    assert DEFAULT_WINDOW_MARGIN_S == 0.25


@pytest.mark.parametrize(
    ("overrides", "why"),
    [
        ({"shared_pacer_path": None}, "shared_pacer_path is missing"),
        ({"shared_pacer_path": "state/stock-mock.pace"}, "is relative"),
        ({"shared_max_rps": None}, "must be a number"),
        ({"shared_max_rps": 0}, "must be positive"),
        ({"shared_max_rps": -1.0}, "must be positive"),
        ({"shared_window_margin_s": -0.1}, "must be zero or positive"),
        ({"shared_window_margin_s": None}, "must be a number"),
        ({"app_key_request_wait_budget_ms": None}, "must be a number"),
        ({"app_key_request_wait_budget_ms": 0}, "must be positive"),
    ],
)
def test_terms_that_cannot_be_honoured_are_refused(
    tmp_path: Path, overrides: dict[str, Any], why: str
) -> None:
    with pytest.raises(SharedPaceUnavailable, match=why):
        load_shared_pace_terms(_yaml(tmp_path, **overrides))


def test_an_absent_transport_yaml_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SharedPaceUnavailable, match="cannot be read"):
        load_shared_pace_terms(tmp_path / "nope.yaml")


def test_the_transport_yaml_comes_from_the_flag_or_the_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(TRANSPORT_YAML_ENV, raising=False)
    assert resolve_transport_yaml(None) is None
    assert resolve_transport_yaml("  ") is None
    monkeypatch.setenv(TRANSPORT_YAML_ENV, " /tmp/from-env.yaml ")
    assert resolve_transport_yaml(None) == Path("/tmp/from-env.yaml")
    assert resolve_transport_yaml("/tmp/from-flag.yaml") == Path("/tmp/from-flag.yaml")


# ── the window rule, identical to tos_runtime's SharedAppKeyGate ───────────


def test_the_second_call_waits_out_the_first_calls_slot(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "pace" / "stock-mock.pace"
    _pace(path, clock).acquire()
    assert clock.slept == []
    _pace(path, clock).acquire()
    assert clock.slept == [pytest.approx(0.5)]


def test_no_second_ever_holds_more_than_max_rps_grants(tmp_path: Path) -> None:
    """The failing input: a backlog of calls the interval alone lets into one second."""
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    grants: list[float] = []
    for _ in range(12):
        _pace(path, clock).acquire()
        grants.append(clock.now)
    worst = max(
        sum(1 for other in grants if start <= other < start + 1.0) for start in grants
    )
    assert worst <= 2


def test_the_configured_margin_is_the_one_that_is_applied(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    first = clock.now
    for _ in range(3):
        _pace(path, clock, margin=0.25).acquire()
    assert clock.now == pytest.approx(first + 1.25)


def test_a_slot_further_away_than_the_app_keys_budget_refuses(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    _pace(path, clock, slot_budget_s=0.1).acquire()
    with pytest.raises(SharedPaceUnavailable, match="nothing was sent"):
        _pace(path, clock, slot_budget_s=0.1).acquire()


def test_a_margin_past_the_app_keys_budget_refuses_instead_of_sleeping(
    tmp_path: Path,
) -> None:
    """The failing input: a 9 s margin would sleep ~10 s while holding the lock.

    The runtime refuses such a slot rather than parking every other tenant process
    behind the lock, and `app_key_request_wait_budget_ms` is the bound it uses.
    """
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    for _ in range(2):
        _pace(path, clock, margin=9.0, slot_budget_s=4.0).acquire()
    assert clock.slept == [pytest.approx(0.5)]

    with pytest.raises(SharedPaceUnavailable, match="past the 4.000s wait budget"):
        _pace(path, clock, margin=9.0, slot_budget_s=4.0).acquire()
    assert clock.slept == [pytest.approx(0.5)]


def test_the_lock_budget_is_separate_from_the_slot_budget(tmp_path: Path) -> None:
    """A tight slot budget must not shorten how long we wait for the flock itself."""
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    pace = _pace(path, clock, slot_budget_s=0.05)
    assert pace.slot_wait_budget_s == 0.05
    pace.acquire(lock_wait_s=30.0)
    assert clock.slept == []


def test_a_corrupted_grant_file_grants_rather_than_stalling(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not-a-number\n", encoding="utf-8")
    _pace(path, clock).acquire()
    assert clock.slept == []


def test_a_grant_dated_in_the_future_is_not_trusted(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{clock.now + 3600:.6f}\n", encoding="utf-8")
    _pace(path, clock).acquire()
    assert clock.slept == []


# ── the cross-implementation pin (issue #1161) ────────────────────────────
#
# SAFETY: 이 픽스처는 tos_runtime 의 SharedAppKeyGate 와 공유하는 유일한 계약이다 — 방화벽 때문에 이 파일은 그 코드를 import 할 수 없으므로, 한쪽 형식만 바꾸면 여기와 tos/runtime/tests/transport/kis_mock/test_shared_pacer.py 중 하나가 깨져야 한다 (#1166 리뷰 LOW 3)

_GRANTS_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "tests/fixtures/kis_mock_shared_pace_grants.txt"
)
_FIXTURE_MAX_RPS = 2.0
_FIXTURE_MARGIN_S = 0.25
_FIXTURE_FIRST_GRANT = 1_700_000_000.0


def _fixture_text() -> str:
    return _GRANTS_FIXTURE.read_text(encoding="utf-8")


def test_this_tool_writes_the_shared_grant_fixture_byte_for_byte(
    tmp_path: Path,
) -> None:
    """Seeded with the fixture's first line, a grant at its second must reproduce it."""
    expected = _fixture_text()
    seed, second = expected.splitlines()
    path = tmp_path / "stock-mock.pace"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(seed + "\n", encoding="utf-8")
    clock = _Clock(start=float(second))

    _pace(path, clock, max_rps=_FIXTURE_MAX_RPS, margin=_FIXTURE_MARGIN_S).acquire()

    assert clock.slept == []
    assert path.read_text(encoding="utf-8") == expected


def test_this_tool_reads_the_shared_grant_fixture(tmp_path: Path) -> None:
    """The fixture's two grants make the next slot 0.25 s away at +1.0 s."""
    path = tmp_path / "stock-mock.pace"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_fixture_text(), encoding="utf-8")
    clock = _Clock(start=_FIXTURE_FIRST_GRANT + 1.0)

    _pace(path, clock, max_rps=_FIXTURE_MAX_RPS, margin=_FIXTURE_MARGIN_S).acquire()

    assert clock.slept == [pytest.approx(0.25)]


# ── the file and lock contract the tenant processes read ───────────────────


def test_the_grant_file_is_the_format_the_runtime_writes(tmp_path: Path) -> None:
    """One `%.6f` epoch second per line, oldest first, at most `int(max_rps)` lines."""
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    for _ in range(3):
        _pace(path, clock).acquire()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [line == f"{float(line):.6f}" for line in lines] == [True, True]
    assert [float(line) for line in lines] == sorted(float(line) for line in lines)


def test_a_grant_file_the_runtime_wrote_is_honoured(tmp_path: Path) -> None:
    """The interop direction: a file written by the tenant processes paces this tool."""
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{clock.now - 0.6:.6f}\n{clock.now - 0.1:.6f}\n", encoding="utf-8")
    _pace(path, clock).acquire()
    assert clock.slept == [pytest.approx(0.65)]


def test_the_grant_file_and_its_directory_are_private(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "pace" / "stock-mock.pace"
    _pace(path, clock).acquire()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert not list(path.parent.glob("*.tmp"))


def test_the_lock_is_the_flock_the_runtime_takes(tmp_path: Path) -> None:
    """A holder of `<path>.lock` — which is what tos_runtime's file_lock takes — blocks us."""
    clock, path = _Clock(), tmp_path / "pace" / "stock-mock.pace"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(SharedPaceUnavailable, match="held"):
            _pace(path, clock).acquire(lock_wait_s=0.05)
    finally:
        os.close(fd)
    assert not path.exists()


# ── what the probe client's call path does with it ─────────────────────────


class _InnerPacer:
    def __init__(self) -> None:
        self.interval_s = 2.5
        self.waits = 0
        self.deferred: list[float] = []

    def wait(self) -> float:
        self.waits += 1
        return 0.0

    def defer(self, seconds: float) -> None:
        self.deferred.append(seconds)


class _FakeClient:
    def __init__(self) -> None:
        self.pacer: Any = _InnerPacer()
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


def test_the_tools_own_floor_runs_first_then_the_shared_slot(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.pace"
    inner = _InnerPacer()
    paced = SharedPacedCallPacer(inner, _pace(path, clock))
    paced.wait()
    paced.wait()
    assert inner.waits == 2
    assert clock.slept == [pytest.approx(0.5)]
    assert paced.interval_s == 2.5
    paced.defer(3.0)
    assert inner.deferred == [3.0]


def test_a_transport_yaml_puts_the_shared_window_in_front_of_the_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(TRANSPORT_YAML_ENV, raising=False)
    pace_file = tmp_path / "state" / "stock-mock.pace"
    yaml_path = _yaml(tmp_path, shared_pacer_path=str(pace_file))
    client = _FakeClient()
    assert attach_shared_pace(client, str(yaml_path)) == pace_file
    assert isinstance(client.pacer, SharedPacedCallPacer)


def test_without_a_transport_yaml_the_run_says_it_is_not_sharing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(TRANSPORT_YAML_ENV, raising=False)
    client = _FakeClient()
    assert attach_shared_pace(client, None) is None
    assert isinstance(client.pacer, _InnerPacer)
    assert TRANSPORT_YAML_ENV in capsys.readouterr().err


def test_both_tools_take_the_transport_yaml_flag() -> None:
    argv = [
        "005930",
        "--expect-account-fingerprint",
        "ee1bdb5f1ca2",
        "--transport-yaml",
        "/tmp/kis_mock_transport.yaml",
    ]
    for parser in (
        flat.build_parser("flat", "d"),
        flatten.build_parser("flatten", "d"),
    ):
        assert parser.parse_args(argv).transport_yaml == "/tmp/kis_mock_transport.yaml"


def test_a_mid_run_shared_refusal_is_read_as_no_answer_not_as_flat() -> None:
    """A slot this tool never got is 'the broker did not answer', not a traceback."""
    assert SharedPaceUnavailable in flat.broker_transport_errors()


def test_a_transport_yaml_that_cannot_be_honoured_leaves_the_client_unpaced(
    tmp_path: Path,
) -> None:
    client = _FakeClient()
    bad = tmp_path / "kis_mock_transport.yaml"
    bad.write_text("mode: live\n", encoding="utf-8")
    with pytest.raises(SharedPaceUnavailable, match="shared_pacer_path is missing"):
        attach_shared_pace(client, str(bad))
    assert isinstance(client.pacer, _InnerPacer)


def test_terms_that_cannot_be_honoured_are_a_refusal_with_nothing_sent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The ops tool refuses before its first GET, and closes the client it built."""
    import shared.kis.auth as kis_auth
    import tools.broker_probes.common as common
    import tools.broker_probes.probes_order as probes_order

    client = _FakeClient()
    monkeypatch.setattr(common, "assert_no_live_futures_config", lambda: None)
    monkeypatch.setattr(
        common, "resolve_credentials", lambda asset, is_real: _StubCreds()
    )
    monkeypatch.setattr(common, "require_account", lambda creds: None)
    monkeypatch.setattr(common, "account_fingerprint", lambda account_no: _FP)
    monkeypatch.setattr(common, "build_auth_config", lambda creds, cache_dir: None)
    monkeypatch.setattr(common, "probe_token_cache_dir", lambda directory: tmp_path)
    monkeypatch.setattr(
        kis_auth, "KISAuthManager", lambda config, use_singleton: object()
    )
    monkeypatch.setattr(
        probes_order, "MockTradingClient", lambda *args, **kwargs: client
    )
    bad = tmp_path / "kis_mock_transport.yaml"
    bad.write_text("mode: live\nshared_max_rps: 2.0\n", encoding="utf-8")

    with pytest.raises(flat.OpsRefusal, match="shared_pacer_path is missing"):
        flat.build_client(
            expected_fingerprint=_FP,
            probe_id="cp3-ops-flat-check",
            title="t",
            transport_yaml=str(bad),
        )
    assert client.closed == 1
