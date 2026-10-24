#!/usr/bin/env python3
"""TOS 한 장 상태판 — «오늘 무엇이 돌았고 무엇이 막혔나» (읽기 전용).

계획 ``docs/plans/2026-10-22-tos-rescope-plan.md`` §2 문장 5 · §3 M4. 운영자가 한 명령
(``sts tos status``)으로 하루를 본다. 보여 주는 것:

* CP-3 tenant 세션(``cp3-sessions/<label>-YYYYMMDD``) 마다 부팅·종료·rc·ABORT 줄, 렌더
  digest(source_revision · activation) 와 런타임 ``code_digest`` 대 ``release.yaml``
  ``expected_code_digest``.
* 그 세션 날짜로 한정한 틱 수, 결정 종류, 보류(DECISION_WITHHELD 등) 사유와 흐름 정지 사유
  분포, M5 첫 수(값을 쥐고도 UNKNOWN 으로 거절된 post-boot 봉), ``MARKETFEED_FIELD_REFUSED``
  행, ``VENUE_BAND_OBSERVED`` 행, ``MARKETFEED_PASS_OVERRUN`` 행 수와 가장 긴 pass(#949).
* B3 대조 요약(``<session>/b3/report/summary.json`` 이 있으면) — unresolved · divergent.
* 생산자 지연(journal ``as_of_ms`` − 분 마감) p50/p90 과 생산자 카운터.
* 상주 paper 세션(``paper-sessions`` · ``paper-ops`` pid) 상태와 그 세션의
  ``MARKETFEED_PASS_OVERRUN`` 행.

**읽기 전용.** sqlite 는 :func:`tools.tos_cp3.session_inputs._connect_ro`
(``file:…?mode=ro`` + ``PRAGMA user_version`` 핀)로만 연다. 파일은 읽기만 하고, 프로세스
생존은 ``/proc/<pid>/cmdline`` 을 읽어 판단한다(신호를 보내지 않는다).

**tos import 없음.** 방화벽(TOS-FW-R)상 ``tools/`` 는 ``tos``/``tos_runtime`` 를 import
할 수 없다. 저장소 모양은 ``session_inputs`` 가 이미 미러링해 둔 상수·리더를 그대로 쓴다 —
틱↔봉 결합(capsule_id · evidence seq 괄호)과 M5 계수를 두 번 구현하지 않기 위해서다.

Usage::

    sts tos status                       # 오늘(KST)
    sts tos status --date 2026-10-22     # 특정 날짜
    sts tos status --json                # 기계용
    .venv/bin/python tools/tos_cp3/status_board.py --date 2026-10-22
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import re
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3 import session_inputs as si  # noqa: E402

DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "tos_status_board.yaml"
KST = ZoneInfo("Asia/Seoul")

BLOCK = "막힘"
WARN = "확인"

#: 러너가 정상 종료로 보는 rc — 0, 그리고 자기 정지 경로의 SIGTERM(143).
#: ``run_tenant_session.sh`` 말미의 case 문과 같은 집합이다.
NORMAL_END_RCS = frozenset({0, 143})

#: stale 거절로 읽는 보류 사유(#931 운영자 지시). 그 밖의 사유는 1건이라도 막힘.
STALE_HALT_REASON = "TIME_NOT_ADMITTED"

FIELD_REFUSED_KIND = "MARKETFEED_FIELD_REFUSED"
#: ``MARKETFEED_FIELD_REFUSED.refused_by_reason`` 의 stale 키(런타임 ``_derive_field_state``).
#: 그 밖의 사유는 1건이라도 막힘(#931).
STALE_FIELD_REASON = "stale"
BAND_OBSERVED_KIND = "VENUE_BAND_OBSERVED"
#: 런타임 ``marketfeed.scheduler._MARKETFEED_PASS_OVERRUN_KIND`` 의 거울(#949) — 한 pass(틱 +
#: post-pass hook)가 ``poll_interval_ms + journal_pass_allowance_ms`` 창을 넘을 때만 쓰이는
#: 진단 행. 날짜도 벽시계도 싣지 않으므로 band 행처럼 부팅 구간 seq 범위로만 세션에 묶인다.
PASS_OVERRUN_KIND = "MARKETFEED_PASS_OVERRUN"
#: 부팅마다 한 번 쓰이는 행 — 누적 잎을 «부팅 구간» seq 범위로 나누는 경계다.
#: band 행처럼 날짜를 싣지 않는 행(REFUSED 는 trading_date 가 없다)은 이 범위로만 세션에 묶인다.
BOOT_KIND = "TIME_SERVICE_STARTUP"
#: diff_decisions.py 가 쓰는 summary 모양 — 다른 값이면 키를 믿지 않고 막힘으로 보고한다.
B3_SUMMARY_SCHEMA_VERSIONS = frozenset({2})

_SESSION_DIR_RE = re.compile(r"^(?P<label>[a-z0-9][a-z0-9-]*?)-(?P<day>\d{8})$")
_PAPER_DIR_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<hms>\d{6})-(?P<direction>[A-Z]+)$"
)
#: 상주 paper 드라이버가 런타임 부팅을 확인했을 때 bootproof.txt 첫 줄에 쓰는 문구.
BOOTPROOF_OK = "boot proof: OK"
#: 상주 paper 드라이버의 bootproof.txt — 첫 줄 끝 « · <종목>», 셋째 줄 «baseline_seq=<n>».
_BOOTPROOF_INSTRUMENT_RE = re.compile(r"· (?P<instrument>[A-Z0-9]+)$")
_BOOTPROOF_BASELINE_RE = re.compile(r"baseline_seq=(?P<seq>-?\d+)")
_LOG_LINE_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<msg>.*)$")


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoardConfig:
    """``config/tos_status_board.yaml`` 의 값."""

    state_dir: Path
    tenant_sessions_subdir: str = "cp3-sessions"
    tenant_cron_log_glob: str = "cp3-*-tenant-daily.cron.log"
    paper_sessions_subdir: str = "paper-sessions"
    paper_ops_subdir: str = "paper-ops"
    paper_data_subdir: str = "paper-data"
    paper_runtime_cmdline_needle: str = "tos_runtime"
    paper_driver_cmdline_needle: str = "tos_paper_session"
    stale_refusal_ratio_max: float = 0.005
    latency_percentiles: tuple[int, ...] = (50, 90)
    history_days: int = 10


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> BoardConfig:
    """YAML 을 읽어 :class:`BoardConfig` 로. 빠진 키는 거부한다(조용한 기본값 없음)."""
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: 최상위가 매핑이 아니다")
    required = (
        "state_dir",
        "tenant_sessions_subdir",
        "tenant_cron_log_glob",
        "paper_sessions_subdir",
        "paper_ops_subdir",
        "paper_data_subdir",
        "paper_runtime_cmdline_needle",
        "paper_driver_cmdline_needle",
        "stale_refusal_ratio_max",
        "latency_percentiles",
        "history_days",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"{path}: 키가 없다 {missing}")
    # 빈 needle 은 모든 cmdline 에 들어 있어 pid 재사용 방지를 끈다(#941).
    blank = [
        key
        for key in ("paper_runtime_cmdline_needle", "paper_driver_cmdline_needle")
        if not str(raw[key] or "").strip()
    ]
    if blank:
        raise ValueError(f"{path}: 빈 값은 허용하지 않는다 {blank}")
    return BoardConfig(
        state_dir=expand_path(str(raw["state_dir"])),
        tenant_sessions_subdir=str(raw["tenant_sessions_subdir"]),
        tenant_cron_log_glob=str(raw["tenant_cron_log_glob"]),
        paper_sessions_subdir=str(raw["paper_sessions_subdir"]),
        paper_ops_subdir=str(raw["paper_ops_subdir"]),
        paper_data_subdir=str(raw["paper_data_subdir"]),
        paper_runtime_cmdline_needle=str(raw["paper_runtime_cmdline_needle"]),
        paper_driver_cmdline_needle=str(raw["paper_driver_cmdline_needle"]),
        stale_refusal_ratio_max=float(raw["stale_refusal_ratio_max"]),
        latency_percentiles=tuple(int(p) for p in raw["latency_percentiles"]),
        history_days=int(raw["history_days"]),
    )


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value)))


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def percentile(values: Sequence[int], p: int) -> int | None:
    """Nearest-rank 백분위. 빈 입력이면 ``None``."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def bar_close_ms(raw_event_id: str) -> int | None:
    """``A05611:1m:20261022T084500+0900`` → 그 1분봉 마감(시작 + 60s)의 epoch ms.

    id 문법은 ``session_inputs`` 의 것을 그대로 쓴다(두 문법이 갈라지지 않게).
    """
    try:
        stamp = raw_event_id.split(si._RAW_EVENT_ID_SEPARATOR, 1)[1]
        start = _dt.datetime.strptime(stamp, si._RAW_EVENT_ID_STAMP_FORMAT)
    except (IndexError, ValueError):
        return None
    return int(start.timestamp() * 1000) + 60_000


def pid_alive(pid: int | None, needle: str, *, proc_root: Path = Path("/proc")) -> bool:
    """``pid`` 가 살아 있고 그 cmdline 에 ``needle`` 이 있으면 True(pid 재사용 방지)."""
    if pid is None:
        return False
    try:
        cmdline = (proc_root / str(pid) / "cmdline").read_bytes()
    except OSError:
        return False
    return needle in cmdline.replace(b"\0", b" ").decode("utf-8", "replace")


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _last_json_line(path: Path) -> dict[str, Any] | None:
    try:
        lines = [
            ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _hhmmss(ts: str | None) -> str:
    return ts[11:] if ts else "—"


# ---------------------------------------------------------------------------
# tenant session — the runner's own log
# ---------------------------------------------------------------------------


@dataclass
class RunnerLog:
    """``session.log`` (``run_tenant_session.sh`` 의 log() 흐름)에서 읽은 사실."""

    first_ts: str | None = None
    repo_commit: str | None = None
    instrument: str | None = None
    data_leaf: str | None = None
    tree_id: str | None = None
    direction: str | None = None
    source_revision: str | None = None
    activation: str | None = None
    #: 렌더가 band 원천 슬롯을 선언했나 — True/False, 줄이 없으면 None.
    #: SHORT 트리처럼 band 를 끈 트리는 False 이고, 그때 band 부재는 소견이 아니다.
    band_declared: bool | None = None
    band_line_ok: bool = False
    band_digest: str | None = None
    boot_at: str | None = None
    run_pid: int | None = None
    producer_pid: int | None = None
    stop_at: str | None = None
    end_at: str | None = None
    run_rc: int | None = None
    producer_rc: int | None = None
    aborts: list[str] = field(default_factory=list)


_RUNNER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("repo_commit", re.compile(r"checkout ok: .*repo_commit=(\w+)")),
    ("data_leaf", re.compile(r"instrument=(\S+) · data leaf (\S+)")),
    ("render", re.compile(r"=== RENDER tree=(\S+) direction=(\S+)")),
    ("band_ok", re.compile(r"band line ok · .*digest=(\w+)")),
    ("band_slot", re.compile(r"^render: \S+ declares a band_journal_path slot")),
    ("band_off", re.compile(r"^render: \S+ declares no band source")),
    ("boot", re.compile(r"=== BOOT ")),
    ("run_pid", re.compile(r"^run pid=(\d+)")),
    ("producer_pid", re.compile(r"^producer pid=(\d+)")),
    ("stop", re.compile(r"=== STOP ")),
    ("end_run", re.compile(r"=== END run rc=(\d+)")),
    ("end_producer", re.compile(r"=== END producer rc=(\d+)")),
    ("abort", re.compile(r"^ABORT: (.*)")),
)
_RENDER_FIELD_RE = re.compile(r"^\s+(source_revision|activation):\s+(.*)$")


def parse_runner_log(text: str) -> RunnerLog:
    out = RunnerLog()
    for line in text.splitlines():
        stamped = _LOG_LINE_RE.match(line)
        if stamped is None:
            # render 블록(타임스탬프 없는 들여쓴 줄)
            render = _RENDER_FIELD_RE.match(line)
            if render is not None:
                setattr(out, render.group(1), render.group(2).strip())
            continue
        ts, msg = stamped.group("ts"), stamped.group("msg")
        if out.first_ts is None:
            out.first_ts = ts
        for name, pattern in _RUNNER_PATTERNS:
            m = pattern.search(msg)
            if m is None:
                continue
            if name == "repo_commit":
                out.repo_commit = m.group(1)
            elif name == "data_leaf":
                out.instrument, out.data_leaf = m.group(1), m.group(2)
            elif name == "render":
                out.tree_id, out.direction = m.group(1), m.group(2)
            elif name == "band_ok":
                out.band_line_ok, out.band_digest = True, m.group(1)
            elif name == "band_slot":
                out.band_declared = True
            elif name == "band_off":
                out.band_declared = False
            elif name == "boot":
                out.boot_at = ts
            elif name == "run_pid":
                out.run_pid = int(m.group(1))
            elif name == "producer_pid":
                out.producer_pid = int(m.group(1))
            elif name == "stop":
                out.stop_at = ts
            elif name == "end_run":
                out.run_rc, out.end_at = int(m.group(1)), ts
            elif name == "end_producer":
                out.producer_rc = int(m.group(1))
            elif name == "abort":
                out.aborts.append(m.group(1))
            break
    return out


_EXPECTED_CODE_DIGEST_RE = re.compile(
    r"^expected_code_digest:\s*[\"']?([0-9a-f]{64})[\"']?\s*$", re.M
)


def expected_code_digest(config_dir: Path) -> str | None:
    """렌더된 트리 ``release.yaml`` 의 (주석이 아닌) ``expected_code_digest``."""
    try:
        text = (config_dir / "release.yaml").read_text(encoding="utf-8")
    except OSError:
        return None
    m = _EXPECTED_CODE_DIGEST_RE.search(text)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# producer
# ---------------------------------------------------------------------------


def producer_facts(session_dir: Path, percentiles: Sequence[int]) -> dict[str, Any]:
    """journal 지연 분포 + producer-summary 카운터 + band 줄."""
    latencies: list[int] = []
    rows = 0
    journal = session_dir / "journal.jsonl"
    try:
        lines = journal.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows += 1
        close = bar_close_ms(str(row.get("raw_event_id", "")))
        as_of = row.get("as_of_ms")
        if close is not None and isinstance(as_of, int):
            latencies.append(as_of - close)
    summary = _read_json(session_dir / "producer" / "producer-summary.json")
    counters = summary.get("counters") if isinstance(summary, dict) else None
    return {
        "journal_rows": rows,
        "latency_ms": {f"p{p}": percentile(latencies, p) for p in percentiles}
        | {"max": max(latencies) if latencies else None, "n": len(latencies)},
        "counters": counters,
        "band_line": _last_json_line(session_dir / "producer" / "band.jsonl"),
    }


# ---------------------------------------------------------------------------
# runtime stores (one accumulating leaf, many session days)
# ---------------------------------------------------------------------------


@dataclass
class LeafFacts:
    """한 데이터 잎을 한 번 읽은 결과. 잎은 세션을 누적하므로 날짜로 자른다."""

    records: list[dict[str, Any]] | None = None
    snapshots: tuple[si.Snapshot, ...] | None = None
    extra_rows: list[tuple[int, str, dict[str, Any]]] = field(default_factory=list)
    code_digest_by_seq: dict[int, str | None] = field(default_factory=dict)
    #: 부팅 행(:data:`BOOT_KIND`)의 seq, 오름차순.
    boot_seqs: list[int] = field(default_factory=list)
    error: str | None = None


def _kind_rows(
    conn: Any, kinds: Sequence[str], *, after_seq: int = -1
) -> list[tuple[int, str, dict[str, Any]]]:
    """``(seq, kind, record)`` — 그 종류의 evidence 행, seq 오름차순(``(kind, seq)`` 인덱스)."""
    marks = ",".join("?" * len(kinds))
    return [
        (
            int(seq),
            str(kind),
            si._evidence_record(payload_json, seq=int(seq), kind=str(kind)),
        )
        for seq, kind, payload_json in conn.execute(
            f"SELECT seq, kind, payload_json FROM entries WHERE kind IN ({marks})"
            " AND seq > ? ORDER BY seq",
            (*kinds, after_seq),
        )
    ]


def pass_overrun_summary(
    rows: Iterable[tuple[int, Mapping[str, Any]]],
) -> dict[str, Any]:
    """``MARKETFEED_PASS_OVERRUN`` 행 수와 가장 긴 pass(``pass_ms`` 최대) 한 행.

    필드 이름은 런타임 ``TickScheduler._record_pass_overrun`` 이 쓰는 그대로다.
    ``pass_ms`` 가 정수가 아닌 행도 세지만 «최악» 후보에서는 뺀다.
    """
    rows = list(rows)
    timed = [
        (seq, p)
        for seq, p in rows
        if isinstance(p.get("pass_ms"), int) and not isinstance(p.get("pass_ms"), bool)
    ]
    worst = None
    if timed:
        seq, p = max(timed, key=lambda sp: sp[1]["pass_ms"])
        worst = {"seq": seq} | {
            key: p.get(key)
            for key in ("pass_ms", "budget_ms", "tick_ms", "after_pass_ms")
        }
    return {"rows": len(rows), "worst": worst}


def read_leaf(data_dir: Path) -> LeafFacts:
    """``session_inputs`` 의 리더로 잎을 읽는다. 거부는 문자열로 돌려준다(상태판은 죽지 않는다)."""
    facts = LeafFacts()
    try:
        facts.records = si.live_decision_records(data_dir)
        facts.snapshots = si.read_snapshots(data_dir)
        conn = si._connect_ro(
            data_dir / si.EVIDENCE_FILE_NAME,
            label="evidence",
            pinned_version=si.PINNED_EVIDENCE_SCHEMA_VERSION,
        )
        try:
            facts.extra_rows = _kind_rows(
                conn, (FIELD_REFUSED_KIND, BAND_OBSERVED_KIND, PASS_OVERRUN_KIND)
            )
            facts.boot_seqs = [
                int(seq)
                for (seq,) in conn.execute(
                    "SELECT seq FROM entries WHERE kind = ? ORDER BY seq", (BOOT_KIND,)
                )
            ]
            seqs = sorted({int(r["evidence_seq"]) for r in facts.records})
            for chunk_start in range(0, len(seqs), 500):
                chunk = seqs[chunk_start : chunk_start + 500]
                marks = ",".join("?" * len(chunk))
                for seq, identity in conn.execute(
                    f"SELECT seq, runtime_identity_json FROM entries WHERE seq IN ({marks})",
                    chunk,
                ):
                    digest = None
                    if identity:
                        try:
                            digest = json.loads(identity).get("code_digest")
                        except (json.JSONDecodeError, AttributeError):
                            digest = None
                    facts.code_digest_by_seq[int(seq)] = digest
        finally:
            conn.close()
    except (si.SessionInputsError, OSError, ValueError) as exc:
        facts.error = f"{type(exc).__name__}: {exc}"
    except (
        Exception
    ) as exc:  # noqa: BLE001 — sqlite3.Error 등, 상태판은 사유를 보여 준다
        facts.error = f"{type(exc).__name__}: {exc}"
    return facts


def store_facts(leaf: LeafFacts, day: str, pre_boot: frozenset[str]) -> dict[str, Any]:
    """한 세션 날짜(KST ``YYYYMMDD``)로 자른 런타임 사실."""
    if leaf.error is not None or leaf.records is None or leaf.snapshots is None:
        return {"error": leaf.error or "store not read"}
    # 날짜 한정은 session_inputs.scope_to_session_day 에 맡긴다 — 날짜를 읽을 수 없는 id 와
    # 부팅 스냅샷·저장소의 날짜 불일치를 거부하는 것이 그 함수다. 다만 그 함수는 «넘겨받은
    # 스냅샷 중 가장 새 날짜» 를 세션으로 보므로, 지난 날짜를 볼 때는 그 날 이후 스냅샷을 빼고
    # 넘긴다(날짜를 읽을 수 없는 id 는 빼지 않는다 — 그래야 거부된다).
    passed = [
        snap
        for snap in leaf.snapshots
        if (d := si.session_day_of(snap.raw_event_id)) is None or d <= day
    ]
    has_day = any(si.session_day_of(snap.raw_event_id) == day for snap in passed)
    has_unreadable = any(
        si.session_day_of(snap.raw_event_id) is None for snap in passed
    )
    if has_day or has_unreadable:
        try:
            day_snaps, scope = si.scope_to_session_day(passed, pre_boot)
        except si.SessionInputsError as exc:
            return {"error": f"세션 범위 거부 — {exc}"}
        if scope.session_day != day:
            return {
                "error": f"세션 범위 거부 — 저장소가 말하는 세션 날짜 {scope.session_day} ≠ {day}"
            }
    else:
        # 아직 한 봉도 소비하지 않은 세션(부팅 직후) — 거부가 아니라 «틱 0» 이다.
        day_snaps = []
        scope = si.SessionScope(
            session_day=day,
            days_present=tuple(
                sorted(
                    {
                        d
                        for d in (si.session_day_of(x.raw_event_id) for x in passed)
                        if d
                    }
                )
            ),
            all_days_total=len(leaf.snapshots),
        )
    day_ids = {snap.snapshot_id for snap in day_snaps}
    ticks = [r for r in leaf.records if r["snapshot_id"] in day_ids]
    post_boot = [r for r in ticks if r["raw_event_id"] not in pre_boot]
    outcomes = Counter(r["outcome_kind"] for r in ticks)
    withheld = Counter(
        f"{r['evidence_kind']}/{r['pipeline_halt_reason']}"
        for r in ticks
        if r["outcome_kind"] == si.NO_OUTCOME_KIND
    )
    flow_halts = Counter(
        r["flow_halt_reason"] for r in ticks if r.get("flow_halt_reason") is not None
    )
    withheld_post_boot = [
        r for r in post_boot if r["outcome_kind"] == si.NO_OUTCOME_KIND
    ]
    stale = sum(
        1 for r in withheld_post_boot if r["pipeline_halt_reason"] == STALE_HALT_REASON
    )
    other = [
        f"{r['raw_event_id']} {r['evidence_kind']}/{r['pipeline_halt_reason']}"
        for r in withheld_post_boot
        if r["pipeline_halt_reason"] != STALE_HALT_REASON
    ]

    m5_block = si.consumed_field_states(
        snapshots=day_snaps, pre_boot=pre_boot, scope=scope
    )

    refused_rows = [
        p
        for _seq, kind, p in leaf.extra_rows
        if kind == FIELD_REFUSED_KIND
        and si.session_day_of(str(p.get("raw_event_id", ""))) == day
    ]
    refused_by_reason: Counter[str] = Counter()
    for p in refused_rows:
        for reason in p.get("refused_by_reason") or {}:
            refused_by_reason[reason] += 1
    ages = [p["age_ms"] for p in refused_rows if isinstance(p.get("age_ms"), int)]
    non_stale_refused = [
        f"{p.get('raw_event_id')} {reason}"
        for p in refused_rows
        for reason in (p.get("refused_by_reason") or {})
        if reason != STALE_FIELD_REASON
    ]
    seq_range = session_seq_range(leaf, ticks)
    band_rows: list[dict[str, Any]] | None
    pass_overrun: dict[str, Any] | None
    if seq_range is None:
        band_rows = None  # 틱이 없어 이 세션의 부팅 구간을 정할 수 없다
        pass_overrun = None
    else:
        lo, hi = seq_range
        pass_overrun = pass_overrun_summary(
            (seq, p)
            for seq, kind, p in leaf.extra_rows
            if kind == PASS_OVERRUN_KIND and lo <= seq and (hi is None or seq < hi)
        )
        band_rows = [
            {
                key: p.get(key)
                for key in (
                    "outcome",
                    "reason",
                    "detail",
                    "trading_date",
                    "basis",
                    "price_min",
                    "price_max",
                    "narrowed_intraday",
                )
            }
            | {"seq": seq}
            for seq, kind, p in leaf.extra_rows
            if kind == BAND_OBSERVED_KIND and lo <= seq and (hi is None or seq < hi)
        ]
    code_digests = sorted(
        {
            d
            for d in (
                leaf.code_digest_by_seq.get(int(r["evidence_seq"])) for r in ticks
            )
            if d
        }
    )
    post_boot_consumed = int(m5_block["counts"]["post_boot_consumed_ids"])
    m5 = int(
        m5_block["m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown"]
    )
    return {
        "ticks": len(ticks),
        "post_boot_ticks": len(post_boot),
        "outcomes": dict(sorted(outcomes.items())),
        "withheld_by_reason": dict(sorted(withheld.items())),
        "flow_halts": dict(sorted(flow_halts.items())),
        "capacity_denied": sum(1 for r in ticks if r.get("capacity_denied")),
        "handed_off": sum(1 for r in ticks if r.get("handed_off")),
        "stale_withheld_post_boot": stale,
        "other_withheld_post_boot": other,
        # #931 운영자 판정: M5 ① / post_boot_consumed_ids ≤ stale_refusal_ratio_max
        "post_boot_consumed_ids": post_boot_consumed,
        "m5_present_value_refused_as_unknown": m5,
        "m5_ratio": (m5 / post_boot_consumed) if post_boot_consumed else None,
        "m5_unknown_field_causes": m5_block["unknown_field_causes"],
        "consumed_snapshots": len(day_snaps),
        "field_refused_rows": len(refused_rows),
        "field_refused_by_reason": dict(sorted(refused_by_reason.items())),
        "field_refused_max_age_ms": max(ages) if ages else None,
        "field_refused_non_stale": non_stale_refused,
        "band_observed": band_rows,
        "pass_overrun": pass_overrun,
        "seq_range": list(seq_range) if seq_range else None,
        "code_digests": code_digests,
    }


def session_seq_range(
    leaf: LeafFacts, ticks: Sequence[Mapping[str, Any]]
) -> tuple[int, int | None] | None:
    """이 세션의 부팅 구간 ``[boot, 다음 boot)`` evidence seq 범위.

    세션의 첫 틱보다 앞선 마지막 부팅 행이 시작이다. 틱이 없으면 잎의 마지막 부팅 구간에
    어느 날의 틱도 없을 때만 그 구간을 쓴다(부팅 직후 아직 틱이 없는 세션). 그 밖에는 ``None``
    — 추측해서 다른 세션의 행을 붙이지 않는다.
    """
    if not leaf.boot_seqs:
        return None
    if ticks:
        first = min(int(r["evidence_seq"]) for r in ticks)
        starts = [b for b in leaf.boot_seqs if b <= first]
        if not starts:
            return None
        start = starts[-1]
    else:
        start = leaf.boot_seqs[-1]
        if any(int(r["evidence_seq"]) > start for r in leaf.records or ()):
            return None
    later = [b for b in leaf.boot_seqs if b > start]
    return start, (later[0] if later else None)


# ---------------------------------------------------------------------------
# B3
# ---------------------------------------------------------------------------


def b3_facts(session_dir: Path) -> dict[str, Any] | None:
    """B3 summary 요약. 파일이 없으면 ``None``, 모양이 다르면 ``{"error": …}``."""
    path = session_dir / "b3" / "report" / "summary.json"
    if not path.exists():
        return None
    summary = _read_json(path)
    if not isinstance(summary, dict):
        return {"error": f"{path.name} 이 JSON 객체가 아니다"}
    version = summary.get("summary_schema_version")
    if version not in B3_SUMMARY_SCHEMA_VERSIONS:
        return {
            "error": f"summary_schema_version={version!r} — 이 상태판은"
            f" {sorted(B3_SUMMARY_SCHEMA_VERSIONS)} 모양만 읽는다"
        }
    unresolved = summary.get("unresolved")
    live = summary.get("live_comparison")
    window = summary.get("window_identity")
    count = unresolved.get("count") if isinstance(unresolved, dict) else None
    if not isinstance(count, int) or isinstance(count, bool):
        return {"error": f"unresolved.count 가 정수가 아니다: {unresolved!r}"}
    if not isinstance(live, dict) or not all(
        isinstance(live.get(k), int)
        for k in ("compared_bars", "identical", "divergent")
    ):
        return {
            "error": "live_comparison 의 compared_bars/identical/divergent 가 정수가 아니다"
        }
    window = window if isinstance(window, dict) else {}
    return {
        "unresolved": count,
        "compared_bars": live["compared_bars"],
        "identical": live["identical"],
        "divergent": live["divergent"],
        "window": f"{window.get('window_start')}..{window.get('window_end')}",
    }


# ---------------------------------------------------------------------------
# one tenant session
# ---------------------------------------------------------------------------


@dataclass
class TenantSession:
    name: str
    label: str
    day: str
    path: Path
    runner: RunnerLog
    status: str
    run_alive: bool
    producer_alive: bool
    expected_code_digest: str | None
    producer: dict[str, Any]
    store: dict[str, Any] | None
    b3: dict[str, Any] | None
    boot_snapshot_error: str | None = None
    issues: list[tuple[str, str]] = field(default_factory=list)


def _session_status(runner: RunnerLog, run_alive: bool, producer_alive: bool) -> str:
    if runner.aborts:
        return "ABORT"
    if runner.end_at is not None:
        return "ENDED" if runner.run_rc in NORMAL_END_RCS else "FAILED"
    if runner.boot_at is not None:
        return "RUNNING" if run_alive else "LOST"
    return "PRE-BOOT" if producer_alive else "NOT-BOOTED"


def read_tenant_session(
    path: Path,
    *,
    leaves: dict[str, LeafFacts],
    cfg: BoardConfig,
    proc_root: Path | None,
    with_store: bool = True,
) -> TenantSession:
    """한 세션 디렉터리. ``proc_root=None`` 이면 생존 확인을 하지 않는다(지난 날짜)."""
    m = _SESSION_DIR_RE.match(path.name)
    assert m is not None
    try:
        runner = parse_runner_log((path / "session.log").read_text(encoding="utf-8"))
    except OSError:
        runner = RunnerLog()
    needle = str(path)
    run_alive = proc_root is not None and pid_alive(
        runner.run_pid, needle, proc_root=proc_root
    )
    producer_alive = proc_root is not None and pid_alive(
        runner.producer_pid, needle, proc_root=proc_root
    )
    status = _session_status(runner, run_alive, producer_alive)

    store: dict[str, Any] | None = None
    boot_snapshot_error: str | None = None
    if with_store and runner.boot_at and not runner.data_leaf:
        # 부팅은 했는데 잎 경로를 모른다 — «부팅 전» 이 아니라 «상태 모름» 이다.
        store = {
            "error": "session.log 에 'instrument=… · data leaf …' 줄이 없어 저장소를 열 수 없다"
        }
    elif with_store and runner.data_leaf and runner.boot_at:
        leaf = leaves.get(runner.data_leaf)
        if leaf is None:
            leaf = leaves[runner.data_leaf] = read_leaf(Path(runner.data_leaf))
        boot_snapshot = path / "producer" / "boot-journal-snapshot.json"
        try:
            pre_boot = si.read_boot_snapshot(boot_snapshot)
        except (OSError, si.SessionInputsError, json.JSONDecodeError) as exc:
            pre_boot = frozenset()
            boot_snapshot_error = f"{type(exc).__name__}: {exc}"
        store = store_facts(leaf, m.group("day"), pre_boot)

    session = TenantSession(
        name=path.name,
        label=m.group("label"),
        day=m.group("day"),
        path=path,
        runner=runner,
        status=status,
        run_alive=run_alive,
        producer_alive=producer_alive,
        expected_code_digest=expected_code_digest(path / "config"),
        producer=producer_facts(path, cfg.latency_percentiles),
        store=store,
        b3=b3_facts(path),
        boot_snapshot_error=boot_snapshot_error,
    )
    session.issues = tenant_issues(session, cfg)
    return session


def _overrun_issues(overrun: Mapping[str, Any] | None) -> list[tuple[str, str]]:
    """진단 행이라 막힘이 아니라 확인이다 — 런타임은 이 행으로 아무것도 결정하지 않는다(#949)."""
    if not overrun or not overrun.get("rows"):
        return []
    return [
        (
            WARN,
            f"{PASS_OVERRUN_KIND} {overrun['rows']}행 — {_fmt_overrun_worst(overrun)}",
        )
    ]


def _fmt_overrun_worst(overrun: Mapping[str, Any]) -> str:
    w = overrun.get("worst")
    if not w:
        return "pass_ms 없음"
    return (
        f"최악 pass {w['pass_ms']}ms > 창 {w['budget_ms']}ms"
        f" (tick {w['tick_ms']}ms + post-pass {w['after_pass_ms']}ms, seq {w['seq']})"
    )


def _fmt_overrun(overrun: Mapping[str, Any] | None) -> str:
    if overrun is None:
        return f"{PASS_OVERRUN_KIND}: 부팅 구간을 정할 수 없어 보지 못함"
    if not overrun["rows"]:
        return f"{PASS_OVERRUN_KIND} 0행"
    return f"{PASS_OVERRUN_KIND} {overrun['rows']}행 · {_fmt_overrun_worst(overrun)}"


def tenant_issues(s: TenantSession, cfg: BoardConfig) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    r = s.runner
    for line in r.aborts:
        issues.append((BLOCK, f"ABORT: {line}"))
    if s.status == "NOT-BOOTED":
        issues.append(
            (
                BLOCK,
                "런타임이 부팅하지 않았고 러너 프로세스도 없다(session.log 끝 확인)",
            )
        )
    elif s.status == "PRE-BOOT":
        issues.append((WARN, "생산자는 돌고 있으나 런타임 부팅 전"))
    elif s.status == "LOST":
        issues.append((BLOCK, f"런타임 pid {r.run_pid} 가 END 기록 없이 사라졌다"))
    elif s.status == "FAILED":
        issues.append((BLOCK, f"런타임 종료 rc={r.run_rc} (정상은 0/143)"))
    if r.producer_rc is not None and r.producer_rc not in NORMAL_END_RCS:
        issues.append((BLOCK, f"생산자 종료 rc={r.producer_rc}"))
    if r.boot_at and r.band_declared is not False and not r.band_line_ok:
        issues.append((WARN, "부팅 전 band 줄 없음(band plan §4 수용 1)"))
    counters = s.producer.get("counters") or {}
    for key in ("fetch_error", "produce_error"):
        if counters.get(key):
            issues.append((WARN, f"생산자 {key}={counters[key]}"))
    if s.boot_snapshot_error is not None:
        issues.append(
            (
                WARN,
                "부팅 스냅샷을 읽지 못해 pre-boot 봉을 빼지 않고 셌다 — "
                f"{s.boot_snapshot_error}",
            )
        )
    if r.boot_at and s.expected_code_digest is None:
        issues.append(
            (
                WARN,
                "release.yaml 의 expected_code_digest 를 찾지 못해 code_digest 를 대조하지 않았다",
            )
        )
    st = s.store
    if st is not None:
        if "error" in st:
            issues.append((BLOCK, f"런타임 저장소 상태 모름 — {st['error']}"))
        else:
            if st["ticks"] == 0:
                if s.status in ("RUNNING", "PRE-BOOT"):
                    issues.append((WARN, "부팅했지만 아직 소비한 틱이 없다"))
                else:
                    issues.append((BLOCK, "부팅한 세션이 틱을 하나도 소비하지 않았다"))
            for line in st["other_withheld_post_boot"]:
                issues.append((BLOCK, f"stale 이 아닌 보류: {line}"))
            for line in st["field_refused_non_stale"]:
                issues.append((BLOCK, f"stale 이 아닌 필드 거절: {line}"))
            ratio = st["m5_ratio"]
            if ratio is not None and ratio > cfg.stale_refusal_ratio_max:
                # 판정은 세션 전체 분모로 한다 — 진행 중에는 분모가 작아 확인으로만 올린다.
                level = WARN if s.status in ("RUNNING", "PRE-BOOT") else BLOCK
                suffix = " (진행 중 — 판정은 종료 뒤)" if level == WARN else ""
                issues.append(
                    (
                        level,
                        f"stale 거절(M5 ①) {st['m5_present_value_refused_as_unknown']}"
                        f"/{st['post_boot_consumed_ids']} = {ratio:.3%}"
                        f" > {cfg.stale_refusal_ratio_max:.1%}{suffix}",
                    )
                )
            bands = st["band_observed"]
            if bands is None:
                if r.band_declared:
                    issues.append(
                        (
                            WARN,
                            "부팅 구간을 정할 수 없어 VENUE_BAND_OBSERVED 를 보지 못했다",
                        )
                    )
            else:
                for b in bands:
                    if b["outcome"] != "OBSERVED":
                        issues.append(
                            (
                                BLOCK,
                                f"VENUE_BAND_OBSERVED {b['outcome']} seq {b['seq']}"
                                f" reason={b['reason']} detail={b['detail']}",
                            )
                        )
                    elif str(b["trading_date"]) != s.day:
                        issues.append(
                            (
                                WARN,
                                f"VENUE_BAND_OBSERVED trading_date {b['trading_date']}"
                                f" ≠ 세션 날짜 {s.day} (seq {b['seq']})",
                            )
                        )
                if r.band_declared and not bands:
                    issues.append(
                        (
                            WARN,
                            "band 를 선언한 트리인데 이 부팅 구간에 VENUE_BAND_OBSERVED 행 없음",
                        )
                    )
            issues.extend(_overrun_issues(st["pass_overrun"]))
            if (
                s.expected_code_digest
                and st["code_digests"]
                and st["code_digests"] != [s.expected_code_digest]
            ):
                issues.append(
                    (
                        BLOCK,
                        f"런타임 code_digest {','.join(d[:12] for d in st['code_digests'])}"
                        f" ≠ release.yaml {s.expected_code_digest[:12]}",
                    )
                )
    if s.b3 is not None:
        if "error" in s.b3:
            issues.append((BLOCK, f"B3 summary 를 읽을 수 없다 — {s.b3['error']}"))
        else:
            if s.b3["unresolved"]:
                issues.append((BLOCK, f"B3 unresolved={s.b3['unresolved']}"))
            # §2-1 판정은 unresolved(설명 안 된 차이) 다. live divergent 는 귀속 규칙으로
            # 설명된 차이를 포함하므로 막힘이 아니라 확인으로 올린다 — 숫자를 숨기지 않기 위해.
            if s.b3["divergent"]:
                issues.append(
                    (
                        WARN,
                        f"B3 live divergent {s.b3['divergent']}/{s.b3['compared_bars']}"
                        " — 귀속은 B3 리포트에서 확인",
                    )
                )
    elif s.status in ("ENDED", "ABORT", "FAILED"):
        issues.append(
            (WARN, "B3 결과 없음(세션 디렉터리에 b3/report/summary.json 이 없다)")
        )
    return issues


# ---------------------------------------------------------------------------
# resident paper
# ---------------------------------------------------------------------------


def _read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def paper_pass_overrun(
    cfg: BoardConfig, bootproof: Sequence[str], report: Mapping[str, Any] | None
) -> dict[str, Any] | None:
    """상주 paper 세션의 ``MARKETFEED_PASS_OVERRUN`` 요약. 잎이나 기준 seq 를 모르면 ``None``.

    범위는 드라이버가 부팅 전에 잡은 ``baseline_evidence_seq``(= 그때의 ``MAX(seq)``) 다음부터,
    이 세션 부팅 행 다음의 부팅 행 전까지다 — 다음 날 세션의 행을 붙이지 않는다. 잎은
    report.json 의 ``data_dir``, 진행 중(report 없음)이면 bootproof 의 종목으로
    ``<state_dir>/<paper_data_subdir>/<종목>`` (래퍼가 잎을 고르는 규칙).
    """
    # 부팅 증명이 OK 가 아니면 이 세션의 부팅 행이 없을 수 있다 — 그때 «기준 뒤 두 번째 부팅»
    # 은 다음 세션의 끝이라, 다음 세션의 행을 이 날짜에 붙이게 된다(#951 리뷰 LOW-1). 보지 않는다.
    if not bootproof or BOOTPROOF_OK not in bootproof[0]:
        return None
    report = report if isinstance(report, Mapping) else {}
    baseline = report.get("baseline_evidence_seq")
    if not isinstance(baseline, int) and len(bootproof) > 2:
        m = _BOOTPROOF_BASELINE_RE.search(bootproof[2])
        baseline = int(m.group("seq")) if m else None
    data_dir = report.get("data_dir")
    if not data_dir and bootproof:
        m = _BOOTPROOF_INSTRUMENT_RE.search(bootproof[0].strip())
        if m:
            data_dir = str(
                cfg.state_dir / cfg.paper_data_subdir / m.group("instrument")
            )
    if not isinstance(baseline, int) or not data_dir:
        return None
    try:
        conn = si._connect_ro(
            Path(data_dir) / si.EVIDENCE_FILE_NAME,
            label="evidence",
            pinned_version=si.PINNED_EVIDENCE_SCHEMA_VERSION,
        )
        try:
            rows = _kind_rows(conn, (BOOT_KIND, PASS_OVERRUN_KIND), after_seq=baseline)
        finally:
            conn.close()
    except (
        Exception
    ) as exc:  # noqa: BLE001 — sqlite3.Error 등, 상태판은 사유를 보여 준다
        return {"error": f"{type(exc).__name__}: {exc}"}
    boots = [seq for seq, kind, _ in rows if kind == BOOT_KIND]
    hi = boots[1] if len(boots) > 1 else None
    return pass_overrun_summary(
        (seq, p)
        for seq, kind, p in rows
        if kind == PASS_OVERRUN_KIND and (hi is None or seq < hi)
    )


def paper_facts(
    cfg: BoardConfig, date_iso: str, *, proc_root: Path | None
) -> dict[str, Any]:
    """그 날짜의 상주 paper 세션. ``proc_root=None`` 이면 pid 생존을 보지 않는다(지난 날짜)."""
    root = cfg.state_dir / cfg.paper_sessions_subdir
    try:
        candidates = sorted(
            p
            for p in root.iterdir()
            if p.is_dir()
            and (m := _PAPER_DIR_RE.match(p.name))
            and m.group("date") == date_iso
        )
    except OSError:
        candidates = []
    ops = cfg.state_dir / cfg.paper_ops_subdir
    runtime_pid = _read_pid(ops / "paper-session.pid")
    driver_pid = _read_pid(ops / "paper-session.driver.pid")
    facts: dict[str, Any] = {
        "session": None,
        "live_check": proc_root is not None,
        "runtime_alive": proc_root is not None
        and pid_alive(
            runtime_pid, cfg.paper_runtime_cmdline_needle, proc_root=proc_root
        ),
        "driver_alive": proc_root is not None
        and pid_alive(driver_pid, cfg.paper_driver_cmdline_needle, proc_root=proc_root),
        "issues": [],
    }
    if not candidates:
        facts["issues"].append((WARN, f"{date_iso} 상주 paper 세션 디렉터리 없음"))
        return facts
    session = candidates[-1]
    try:
        bootproof = (session / "bootproof.txt").read_text(encoding="utf-8").splitlines()
    except OSError:
        bootproof = []
    report = _read_json(session / "report.json")
    facts["session"] = session.name
    facts["bootproof"] = bootproof[0] if bootproof else None
    if isinstance(report, dict):
        facts["report"] = {
            key: report.get(key)
            for key in (
                "verdict",
                "exit_code",
                "stop_reason",
                "started_kst",
                "ended_kst",
                "events_consumed",
                "stale_withheld",
                "stale_ratio",
                "worktree_commit",
            )
        }
        breakdown = report.get("decision_breakdown_delta") or {}
        facts["report"]["outcomes"] = breakdown.get("outcomes")
        facts["report"]["withheld"] = breakdown.get("withheld")
        facts["report"]["flow_halted"] = breakdown.get("flow_halted")
    else:
        facts["report"] = None
    facts["pass_overrun"] = paper_pass_overrun(cfg, bootproof, report)
    if facts["pass_overrun"] is not None and "error" in facts["pass_overrun"]:
        facts["issues"].append(
            (
                WARN,
                f"{PASS_OVERRUN_KIND} 를 읽지 못했다 — {facts['pass_overrun']['error']}",
            )
        )
    else:
        facts["issues"].extend(_overrun_issues(facts["pass_overrun"]))
    if not facts["bootproof"] or BOOTPROOF_OK not in facts["bootproof"]:
        facts["issues"].append(
            (BLOCK, f"boot proof 가 OK 가 아니다: {facts['bootproof']!r}")
        )
    if facts["report"] is not None:
        if facts["report"].get("verdict") != "ok":
            facts["issues"].append(
                (
                    BLOCK,
                    f"paper verdict={facts['report'].get('verdict')} rc={facts['report'].get('exit_code')}",
                )
            )
    elif not facts["live_check"]:
        facts["issues"].append(
            (BLOCK, "지난 날짜인데 report.json 이 없다(세션이 정상 종료되지 않음)")
        )
    elif not (facts["runtime_alive"] and facts["driver_alive"]):
        facts["issues"].append(
            (BLOCK, "report.json 없이 상주 런타임/드라이버가 멈춰 있다")
        )
    return facts


# ---------------------------------------------------------------------------
# the board
# ---------------------------------------------------------------------------


def _session_dirs(cfg: BoardConfig) -> list[Path]:
    root = cfg.state_dir / cfg.tenant_sessions_subdir
    try:
        return sorted(
            p for p in root.iterdir() if p.is_dir() and _SESSION_DIR_RE.match(p.name)
        )
    except OSError:
        return []


def cron_lines(cfg: BoardConfig, date_iso: str) -> dict[str, str]:
    """크론 래퍼 로그마다 그 날짜의 마지막 줄."""
    out: dict[str, str] = {}
    for path in sorted(cfg.state_dir.glob(cfg.tenant_cron_log_glob)):
        try:
            lines = [
                ln
                for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.startswith(date_iso)
            ]
        except OSError:
            continue
        if lines:
            out[path.name] = lines[-1]
    return out


def build_board(
    cfg: BoardConfig,
    *,
    day: _dt.date,
    today: _dt.date,
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """상태판 문서. pid 생존은 ``day == today`` 일 때만 본다 — 지난 날짜의 pid 는 의미가 없다."""
    live_root: Path | None = proc_root if day == today else None
    day_key = day.strftime("%Y%m%d")
    date_iso = day.isoformat()
    leaves: dict[str, LeafFacts] = {}
    dirs = _session_dirs(cfg)
    on_day = [
        read_tenant_session(p, leaves=leaves, cfg=cfg, proc_root=live_root)
        for p in dirs
        if _SESSION_DIR_RE.match(p.name).group("day") == day_key  # type: ignore[union-attr]
    ]
    history_days = sorted(
        {
            _SESSION_DIR_RE.match(p.name).group("day")  # type: ignore[union-attr]
            for p in dirs
        }
        - {day_key},
    )
    # 이력은 그 날짜를 포함해 history_days 개 날짜다. 앞선 날짜는 history_days - 1 개 —
    # 0 이면 [-0:] 가 전부를 남기므로 따로 비운다.
    earlier = [d for d in history_days if d < day_key]
    keep = cfg.history_days - 1
    history_days = earlier[-keep:] if keep > 0 else []
    history = [
        read_tenant_session(p, leaves=leaves, cfg=cfg, proc_root=None)
        for p in dirs
        if _SESSION_DIR_RE.match(p.name).group("day") in history_days  # type: ignore[union-attr]
    ]
    paper = paper_facts(cfg, date_iso, proc_root=live_root)
    issues: list[tuple[str, str, str]] = []
    if not on_day:
        issues.append((WARN, "tenant", f"{date_iso} CP-3 tenant 세션 디렉터리 없음"))
    for s in on_day:
        issues.extend((level, s.name, text) for level, text in s.issues)
    issues.extend((level, "paper", text) for level, text in paper["issues"])
    return {
        "date": date_iso,
        "state_dir": str(cfg.state_dir),
        "generated_kst": _dt.datetime.now(KST).isoformat(timespec="seconds"),
        "tenant_sessions": [_session_json(s) for s in on_day],
        "cron": cron_lines(cfg, date_iso),
        "paper": paper,
        "history": [
            _history_row(s)
            for s in sorted(history + on_day, key=lambda s: (s.day, s.label))
        ],
        "issues": [
            {"level": lv, "where": where, "text": text} for lv, where, text in issues
        ],
    }


def _session_json(s: TenantSession) -> dict[str, Any]:
    r = s.runner
    return {
        "name": s.name,
        "label": s.label,
        "day": s.day,
        "status": s.status,
        "run_alive": s.run_alive,
        "producer_alive": s.producer_alive,
        "instrument": r.instrument,
        "tree_id": r.tree_id,
        "direction": r.direction,
        "repo_commit": r.repo_commit,
        "activation": r.activation,
        "expected_code_digest": s.expected_code_digest,
        "band_declared": r.band_declared,
        "band_line_ok": r.band_line_ok,
        "band_digest": r.band_digest,
        "started": r.first_ts,
        "boot_at": r.boot_at,
        "stop_at": r.stop_at,
        "end_at": r.end_at,
        "run_rc": r.run_rc,
        "producer_rc": r.producer_rc,
        "aborts": r.aborts,
        "producer": s.producer,
        "store": s.store,
        "b3": s.b3,
        "issues": [{"level": lv, "text": t} for lv, t in s.issues],
    }


def _history_row(s: TenantSession) -> dict[str, Any]:
    st = s.store or {}
    return {
        "day": s.day,
        "label": s.label,
        "status": s.status,
        "run_rc": s.runner.run_rc,
        "ticks": st.get("ticks"),
        "stale": st.get("m5_present_value_refused_as_unknown"),
        "other_withheld": len(st.get("other_withheld_post_boot") or []),
        "band": None if st.get("band_observed") is None else len(st["band_observed"]),
        "overrun": (st.get("pass_overrun") or {}).get("rows"),
        "b3_unresolved": (s.b3 or {}).get("unresolved"),
        "store_error": st.get("error"),
        "blocks": sum(1 for lv, _ in s.issues if lv == BLOCK),
    }


# ---------------------------------------------------------------------------
# text rendering
# ---------------------------------------------------------------------------


def _fmt_counts(counts: Mapping[str, Any] | None) -> str:
    if not counts:
        return "없음"
    return " · ".join(f"{k} {v}" for k, v in counts.items())


def _short(value: str | None, n: int = 12) -> str:
    return value[:n] if value else "—"


def render_text(board: Mapping[str, Any]) -> str:
    out: list[str] = []
    add = out.append
    blocks = [i for i in board["issues"] if i["level"] == BLOCK]
    warns = [i for i in board["issues"] if i["level"] == WARN]
    add(f"TOS 상태판 — {board['date']} (KST) · 읽기 전용 · {board['state_dir']}")
    verdict = "막힘 있음" if blocks else ("확인 필요" if warns else "이상 없음")
    add(
        f"판정: {verdict} (막힘 {len(blocks)} · 확인 {len(warns)}) · 생성 {board['generated_kst']}"
    )
    add("")
    add("■ CP-3 tenant 세션")
    if not board["tenant_sessions"]:
        add("  (없음)")
    for s in board["tenant_sessions"]:
        alive = " · 런타임 살아 있음" if s["run_alive"] else ""
        add(
            f"  {s['name']}  {s['direction'] or '?'} {s['instrument'] or '?'}  [{s['status']}]{alive}"
        )
        add(
            f"    시작 {_hhmmss(s['started'])} · 부팅 {_hhmmss(s['boot_at'])} · 정지 {_hhmmss(s['stop_at'])}"
            f" · 종료 {_hhmmss(s['end_at'])} (run rc={s['run_rc']}, producer rc={s['producer_rc']})"
        )
        st = s["store"] or {}
        code = ",".join(_short(d) for d in st.get("code_digests") or []) or "—"
        match = ""
        if st.get("code_digests") and s["expected_code_digest"]:
            match = (
                " = release.yaml"
                if st["code_digests"] == [s["expected_code_digest"]]
                else " ≠ release.yaml"
            )
        add(
            f"    rev {_short(s['repo_commit'])} · tree {s['tree_id'] or '—'} · {s['activation'] or 'activation —'}"
            f" · code_digest {code}{match}"
        )
        if "error" in st:
            add(f"    저장소: 상태 모름 — {st['error']}")
        elif st:
            add(
                f"    틱 {st['ticks']} (post-boot {st['post_boot_ticks']}) · 결정 {_fmt_counts(st['outcomes'])}"
            )
            add(f"    보류 사유: {_fmt_counts(st['withheld_by_reason'])}")
            add(
                f"    흐름 정지: {_fmt_counts(st['flow_halts'])} · capacity_denied {st['capacity_denied']} · handed_off {st['handed_off']}"
            )
            ratio = st["m5_ratio"]
            add(
                f"    stale 거절(M5 ①: 값 있는 UNKNOWN) {st['m5_present_value_refused_as_unknown']}"
                f"/{st['post_boot_consumed_ids']} ({'—' if ratio is None else f'{ratio:.3%}'})"
                f" · TIME_NOT_ADMITTED 보류(post-boot) {st['stale_withheld_post_boot']}"
                f" · 그 밖의 보류 {len(st['other_withheld_post_boot'])}"
                f" · UNKNOWN 원인 {_fmt_counts({k: v.get('post_boot') for k, v in st['m5_unknown_field_causes'].items()})}"
            )
            age = st["field_refused_max_age_ms"]
            add(
                f"    MARKETFEED_FIELD_REFUSED {st['field_refused_rows']}행"
                f" ({_fmt_counts(st['field_refused_by_reason'])}{'' if age is None else f' · 최대 age {age}ms'})"
            )
            if st["band_observed"] is None:
                add("    VENUE_BAND_OBSERVED: 부팅 구간을 정할 수 없어 보지 못함")
            elif st["band_observed"]:
                for b in st["band_observed"]:
                    if b["outcome"] == "OBSERVED":
                        add(
                            f"    VENUE_BAND_OBSERVED OBSERVED {b['trading_date']} basis {b['basis']}"
                            f" [{b['price_min']}, {b['price_max']}] narrowed={b['narrowed_intraday']}"
                        )
                    else:
                        add(
                            f"    VENUE_BAND_OBSERVED {b['outcome']} reason={b['reason']}"
                            f" detail={b['detail']} (seq {b['seq']})"
                        )
            elif s["band_declared"] is False:
                add("    VENUE_BAND_OBSERVED 0행 (이 트리는 band 를 끔)")
            else:
                add("    VENUE_BAND_OBSERVED 0행")
            add(f"    {_fmt_overrun(st['pass_overrun'])}")
        else:
            add("    저장소: 부팅 전이라 읽지 않음")
        band = "있음 " + _short(s["band_digest"]) if s["band_line_ok"] else "없음"
        p = s["producer"]
        lat = p["latency_ms"]
        lat_txt = " · ".join(
            f"{k} {v}ms" for k, v in lat.items() if k.startswith("p") and v is not None
        )
        c = p.get("counters") or {}
        counters = (
            f"published {c.get('published')} · fetch_error {c.get('fetch_error')} · produce_error {c.get('produce_error')}"
            f" · skipped_behind {c.get('skipped_behind')} · late_completed {c.get('late_completed')}"
            if c
            else "summary 아직 없음"
        )
        add(
            f"    생산자: journal {p['journal_rows']}줄 · 지연(as_of−분마감) {lat_txt or '—'} · 최대 {lat['max']}ms · band 줄 {band}"
        )
        add(f"    생산자 카운터: {counters}")
        b3 = s["b3"]
        if b3 is None:
            add("    B3 대조: 결과 없음(세션 디렉터리 b3/report/summary.json)")
        elif "error" in b3:
            add(f"    B3 대조: summary 를 읽을 수 없음 — {b3['error']}")
        else:
            add(
                f"    B3 대조: unresolved {b3['unresolved']} · divergent {b3['divergent']}/{b3['compared_bars']}"
                f" (identical {b3['identical']}) · 창 {b3['window']}"
            )
    if board["cron"]:
        add("  크론 마지막 줄:")
        for name, line in board["cron"].items():
            add(f"    {name}: {line}")
    add("")
    add("■ 상주 paper")
    paper = board["paper"]
    alive = (
        f"런타임 {'살아 있음' if paper['runtime_alive'] else '없음'}"
        f" · 드라이버 {'살아 있음' if paper['driver_alive'] else '없음'}"
        if paper["live_check"]
        else "지난 날짜 — 프로세스 생존은 보지 않음"
    )
    add(f"  {paper['session'] or '(오늘 세션 없음)'} · {alive}")
    if paper.get("session"):
        add(f"    {paper.get('bootproof') or 'bootproof 없음'}")
        rep = paper.get("report")
        if rep:
            add(
                f"    verdict {rep['verdict']} rc={rep['exit_code']} stop={rep['stop_reason']}"
                f" · 소비 {rep['events_consumed']} · stale 보류 {rep['stale_withheld']} ({rep['stale_ratio']})"
            )
            add(
                f"    결정 {_fmt_counts(rep.get('outcomes'))} · 보류 {_fmt_counts(rep.get('withheld'))}"
            )
            add(f"    흐름 정지 {_fmt_counts(rep.get('flow_halted'))}")
        else:
            add("    report.json 아직 없음(세션 진행 중이면 정상)")
        po = paper.get("pass_overrun")
        if po is None:
            add(f"    {PASS_OVERRUN_KIND}: 잎·기준 seq 를 몰라 보지 못함")
        elif "error" in po:
            add(f"    {PASS_OVERRUN_KIND}: 읽지 못함 — {po['error']}")
        else:
            add(f"    {_fmt_overrun(po)}")
    add("")
    if board["history"]:
        add("■ 최근 세션(날짜별)")
        add(
            "  날짜      세션      상태        rc   틱   stale 기타 band 초과 B3unres 막힘"
        )
        for h in board["history"]:
            err = " 저장소모름" if h["store_error"] else ""
            add(
                f"  {h['day']}  {h['label']:<8}  {h['status']:<10}  {str(h['run_rc']):>3}"
                f"  {str(h['ticks']):>4}  {str(h['stale']):>4}  {h['other_withheld']:>3}  {str(h['band']):>3}  {str(h['overrun']):>3}"
                f"  {str(h['b3_unresolved']):>6}  {h['blocks']:>3}{err}"
            )
        add("")
    add("■ 막힌 것 / 확인할 것")
    if not board["issues"]:
        add("  없음")
    for i in board["issues"]:
        add(f"  [{i['level']}] {i['where']}: {i['text']}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def today_kst() -> _dt.date:
    return _dt.datetime.now(KST).date()


def run(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    state_dir: str | None = None,
    date: str | None = None,
    as_json: bool = False,
    proc_root: Path = Path("/proc"),
) -> tuple[str, int]:
    """(출력, 종료코드). 막힘이 있으면 1, 없으면 0."""
    cfg = load_config(config_path)
    if state_dir is not None:
        cfg = BoardConfig(**{**cfg.__dict__, "state_dir": expand_path(state_dir)})
    day = _dt.date.fromisoformat(date) if date else today_kst()
    board = build_board(cfg, day=day, today=today_kst(), proc_root=proc_root)
    text = (
        json.dumps(board, ensure_ascii=False, indent=2, default=str) + "\n"
        if as_json
        else render_text(board)
    )
    blocked = any(i["level"] == BLOCK for i in board["issues"])
    return text, (1 if blocked else 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--state-dir", default=None)
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (기본: 오늘 KST)")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    text, code = run(
        config_path=args.config,
        state_dir=args.state_dir,
        date=args.date,
        as_json=args.json,
    )
    sys.stdout.write(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
