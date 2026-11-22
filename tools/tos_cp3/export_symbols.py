#!/usr/bin/env python3
"""종목마다 오늘 한 줄 — 매수 · 매도 · 보유 · 마지막 차단 사유를 ``/tos`` 가 읽는 JSON 으로.

계획 ``docs/plans/2026-11-19-tos-usage-plan.md`` §5 «종목별 운영 화면»: 운영자가
한 화면에서 종목(= tenant)마다 그날의 체결과 무엇이 막았는지를 본다.

**한 줄도 새로 세지 않는다.** 체결·가격 기준·FIFO 보유는 ``tools/tos_cp3/perf.py``
(`sts tos perf`) 가, 세션 상태와 잎 읽기는 ``tools/tos_cp3/status_board.py``
(`sts tos status`) 가 이미 정의한 그대로를 호출해서 쓴다. 이 모듈이 더하는 것은
그 둘을 종목 하나의 줄로 모으고, 대시보드가 읽는 디렉터리에 원자적으로 쓰는 것뿐이다.

**호스트 측이다.** ``export_bars`` 와 같은 네 가지 벽 때문이다 — 대시보드 컨테이너는
``tools/`` 를 담지 않고(``Dockerfile.dashboard``), tenant 상태 디렉터리
(``~/.local/state/tos``, 0700)를 mount 하지 않으며, 방화벽(TOS-FW-R)상 커널을
import 할 수 없고, 그 virtualenv 에 ``tos_runtime`` 이 없다. 경계는 **파일**이다.

**읽기 전용.** sqlite 는 ``session_inputs._connect_ro`` (``file:…?mode=ro``) 로만 열고,
쓰는 것은 목적지 문서 하나뿐이다. 브로커(KIS)를 부르지 않는다 — 보유 수량은 계좌 조회가
아니라 **TOS 자신의 원장이 아는 값**(perf 의 FIFO 미청산 lot)이고, 문서와 화면 모두
그렇게 이름 붙인다.

**호스트 경로는 문서에 넣지 않는다.** 이 문서는 대시보드가 그대로 브라우저에 보내고,
그 브라우저는 번들에 대시보드 API 키를 쥐고 있다. 잎 경로 · 세션 경로는 어느 키에도
없고, 잎을 읽지 못한 사유조차 예외 **종류 이름**으로 줄여 적는다(:func:`_reduce_error`).

Usage::

    sts tos export-symbols
    sts tos export-symbols --date 2026-11-21 --out-dir /tmp/dry-run
    .venv/bin/python tools/tos_cp3/export_symbols.py --out-dir /tmp/dry-run
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3 import (  # noqa: E402
    export_bars,
    perf,
    status_board,
)
from tools.tos_cp3 import session_inputs as si  # noqa: E402
from tools.tos_cp3.inspect_session import (  # noqa: E402
    TENANT_DATA_PARENT_SUFFIX,
)

__all__ = [
    "DOCUMENT_NAME",
    "ExportRefusal",
    "HOLDING_BASIS",
    "ORDER_BAR_TIME_BASIS",
    "SYMBOLS_SCHEMA_VERSION",
    "SYMBOLS_SUBDIR",
    "Tenant",
    "build_document",
    "default_out_dir",
    "discover_tenants",
    "document_path",
    "export_symbols",
    "main",
    "symbol_row",
]

#: ``export_bars`` 가 정한 목적지 규약을 그대로 쓴다 — 같은 ``$TOS_OPERATOR_DIR`` 아래
#: 자기 하위 디렉터리 하나. 두 내보내기가 서로의 문서를 건드리지 않는다.
SYMBOLS_SUBDIR = "symbols"

#: 파일 이름은 고정이다. 호출자가 고르는 경로 조각이 없으므로 route 에 traversal
#: 표면이 아예 생기지 않는다(``tos_bars`` 는 세션 이름을 받아 패턴으로 막아야 했다).
#: 어느 날짜의 줄인지는 문서 안의 ``date`` 가 말한다.
DOCUMENT_NAME = "today.json"

SYMBOLS_SCHEMA_VERSION = 1

#: 트리마다 하나 있는 렌더 매니페스트. ``tree_id`` 와 ``instrument.pattern`` 이
#: 여기 선언돼 있다 — 종목 목록을 코드에 박지 않기 위해 이것을 읽는다(비협상 규칙
#: «Configuration-driven only»). ``scripts/tos/render_paper_config.py`` 의 입력과 같은 파일이다.
RENDER_MANIFEST_NAME = "RENDER.yaml"

#: 보유 수량이 어디서 온 값인지 — 브로커 잔고가 아니라 TOS 원장의 FIFO 미청산 lot.
#: 화면은 이 토큰을 «TOS 기준» 으로 읽는다.
HOLDING_BASIS = "TOS_LEDGER_FIFO_OPEN_LOTS"

#: 체결 시각의 기준. 증거에는 브로커 체결 **시각**이 없다(``FILL_OBSERVED`` 는
#: ``trading_date`` 만 적는다 — 실측 2026-11-22, 005930 잎 seq 435). 그래서 시각은
#: 지어내지 않고, 그 주문을 **낸 결정 봉**의 시각을 적고 기준 이름을 같이 적는다.
ORDER_BAR_TIME_BASIS = "ORDER_BAR"

ExportRefusal = export_bars.ExportRefusal

BUY, SELL = perf.BUY, perf.SELL

_EMPTY_SIDE: dict[str, Any] = {"fills": 0, "quantity": "0", "last": None}


@dataclass(frozen=True)
class Tenant:
    """한 tenant 트리가 선언한 자기 자신 — 트리 이름과 종목."""

    tree_id: str
    symbol: str


def default_out_dir() -> Path:
    """``export_bars`` 와 **같은** 목적지 규약 — 두 문서가 다른 mount 로 갈라지지 않게."""
    return export_bars.default_out_dir()


def document_path(out_dir: Path) -> Path:
    """문서가 놓일 자리."""
    return out_dir / SYMBOLS_SUBDIR / DOCUMENT_NAME


def discover_tenants(
    *, config_dir: Path, tree_glob: str = perf.TENANT_TREE_GLOB
) -> list[Tenant]:
    """주식 tenant 트리마다 ``(tree_id, 종목)``, 트리 이름 순.

    종목 목록은 설정에서 읽는다 — 코드에 박힌 종목표는 트리를 하나 더 붙인 날
    조용히 틀린다. 매니페스트를 읽지 못하거나 두 키 중 하나가 없으면 **거부**한다:
    이름 없는 종목은 줄을 만들 수 없고, 추측한 이름으로 만든 줄은 틀린 줄이다.
    """
    import yaml

    tenants: list[Tenant] = []
    for tree in sorted(config_dir.glob(tree_glob)):
        if not tree.is_dir():
            continue
        manifest = tree / RENDER_MANIFEST_NAME
        try:
            raw = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ExportRefusal(
                f"{manifest}: 렌더 매니페스트를 읽지 못했다 — {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise ExportRefusal(f"{manifest}: 최상위가 매핑이 아니다")
        tree_id = raw.get("tree_id")
        instrument = raw.get("instrument")
        symbol = instrument.get("pattern") if isinstance(instrument, dict) else None
        if not isinstance(tree_id, str) or not tree_id:
            raise ExportRefusal(f"{manifest}: 'tree_id' 가 없다")
        if not isinstance(symbol, str) or not symbol:
            raise ExportRefusal(f"{manifest}: 'instrument.pattern' 이 없다")
        tenants.append(Tenant(tree_id=tree_id, symbol=symbol))
    return tenants


def _leaf_path(state_dir: Path, tenant: Tenant) -> Path:
    """세션이 없는 날의 잎 자리 — ``inspect_session.resolve_session`` 과 같은 도출."""
    return state_dir / f"{tenant.tree_id}{TENANT_DATA_PARENT_SUFFIX}" / tenant.symbol


def _reduce_error(error: str) -> str:
    """잎을 읽지 못한 사유를, 호스트 경로 없이.

    ``perf.read_leaf`` 와 ``status_board.read_leaf`` 는 둘 다 사유를
    ``f"{type(exc).__name__}: {exc}"`` 로 적는다. 그 뒷부분에는 거의 항상 잎의 절대
    경로가 들어 있고, 이 문서는 대시보드가 그대로 브라우저에 보낸다. 그래서 **예외
    종류 이름만** 남긴다 — 운영자가 봐야 하는 것은 「무엇이 막혔나」(권한인지, 형식인지)
    이고, 경로는 호스트의 로그에 이미 있다.

    종류 이름처럼 보이지 않으면(공백 · 경로 구분자가 섞였으면) 통째로 버린다.
    """
    head = error.split(":", 1)[0].strip()
    if not head or not head.replace("_", "").isalnum():
        return "UNKNOWN"
    return head


def _kst_bar_time(raw_event_id: str | None) -> str | None:
    """봉 id 의 KST ``HH:MM``. 읽히지 않으면 ``None`` — 시각을 지어내지 않는다.

    ``session_inputs`` 가 이미 가진 분해 규약(구분자와 스탬프 형식)을 그대로 쓴다.
    ``status_board.bar_close_ms`` 가 같은 두 상수를 같은 방식으로 읽는다.
    """
    if raw_event_id is None:
        return None
    try:
        stamp = raw_event_id.split(si._RAW_EVENT_ID_SEPARATOR, 1)[1]
        start = _dt.datetime.strptime(stamp, si._RAW_EVENT_ID_STAMP_FORMAT)
    except (IndexError, ValueError):
        return None
    return start.astimezone(status_board.KST).strftime("%H:%M")


def _bar_at_or_before(records: Sequence[dict[str, Any]], seq: int | None) -> str | None:
    """``seq`` 직전에 마지막으로 평가된 봉의 id.

    주문(``SEND_SEALED``)은 그 주문을 낸 결정 블록 **뒤**의 evidence seq 로 적히므로,
    그 seq 이하의 마지막 결정 기록이 그 주문의 봉이다(실측 2026-11-22, 005930 잎:
    send 112 → 결정 79 = 14:36 봉, 다음 결정 144 = 14:37 봉).
    """
    if seq is None:
        return None
    before = [r for r in records if int(r["evidence_seq"]) <= seq]
    return str(before[-1]["raw_event_id"]) if before else None


def _last_fill_block(
    fill: perf.Fill, records: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """체결 한 건 — 가격 기준은 ``perf`` 의 것을 그대로, 시각은 주문 봉."""
    # perf._fill_document 가 가격·기준·수량 표기의 단일 정의다. 여기서 다시 쓰지 않는다.
    document = perf._fill_document(fill, fill.quantity)
    bar = _bar_at_or_before(records, fill.order_seq)
    time_kst = _kst_bar_time(bar)
    return {
        "quantity": document["quantity"],
        "order_price_krw": document["order_price_krw"],
        "execution_price_krw": document["execution_price_krw"],
        "price_basis": document["price_basis"],
        "broker_execution_id": document["broker_execution_id"],
        "time_kst": time_kst,
        # 기준 이름은 시각이 있을 때만 — 시각이 없는데 기준만 있으면 읽는 쪽이
        # 「시각은 있는데 못 읽었다」 와 「애초에 없다」 를 구분할 수 없다.
        "time_basis": None if time_kst is None else ORDER_BAR_TIME_BASIS,
    }


def _side_block(
    fills: Sequence[perf.Fill], side: str, records: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """한 방향의 오늘 체결 — 건수 · 수량 합 · 마지막 한 건."""
    mine = [fill for fill in fills if fill.side == side]
    if not mine:
        return dict(_EMPTY_SIDE)
    return {
        "fills": len(mine),
        "quantity": perf._num(sum((fill.quantity for fill in mine), Decimal(0))),
        "last": _last_fill_block(mine[-1], records),
    }


def _halt_block(
    records: Sequence[dict[str, Any]], day_key: str, error: str | None
) -> dict[str, Any]:
    """오늘 무엇이 막았나 — 마지막 흐름 정지와 마지막 보류, 그리고 사유 분포.

    둘을 **따로** 낸다. 보류(``TIME_NOT_ADMITTED`` 등)는 장 끝 무렵 매 봉 날 수 있어,
    하나로 합치면 정작 운영자가 봐야 하는 흐름 정지(승인 · 해제 · venue)를 덮는다.
    """
    if error is not None:
        return {
            "error": error,
            "last_flow": None,
            "last_withheld": None,
            "flow_counts": {},
        }
    today = [
        record
        for record in records
        if si.session_day_of(str(record["raw_event_id"])) == day_key
    ]
    flow = [r for r in today if r.get("flow_halt_reason") is not None]
    withheld = [
        r
        for r in today
        if r["outcome_kind"] == si.NO_OUTCOME_KIND
        and r.get("pipeline_halt_reason") is not None
    ]
    counts = Counter(str(r["flow_halt_reason"]) for r in flow)
    return {
        "error": None,
        "last_flow": (
            None
            if not flow
            else {
                "reason": str(flow[-1]["flow_halt_reason"]),
                "step": (
                    None
                    if flow[-1].get("flow_halt_step") is None
                    else str(flow[-1]["flow_halt_step"])
                ),
                "time_kst": _kst_bar_time(str(flow[-1]["raw_event_id"])),
            }
        ),
        "last_withheld": (
            None
            if not withheld
            else {
                "reason": str(withheld[-1]["pipeline_halt_reason"]),
                "step": str(withheld[-1]["evidence_kind"]),
                "time_kst": _kst_bar_time(str(withheld[-1]["raw_event_id"])),
            }
        ),
        "flow_counts": dict(sorted(counts.items())),
    }


def _session_block(session: status_board.TenantSession | None) -> dict[str, Any]:
    """오늘의 세션 — 없으면 ``status`` 가 ``None`` 이다(«오늘 시작 안 함»)."""
    if session is None:
        return {
            "name": None,
            "status": None,
            "boot_at": None,
            "end_at": None,
            "run_rc": None,
        }
    runner = session.runner
    return {
        "name": session.name,
        "status": session.status,
        # 로그의 스탬프는 `YYYY-MM-DD HH:MM:SS` 다. 화면은 시각만 쓰므로 시각만 준다 —
        # 날짜는 문서의 `date` 가 이미 말한다.
        "boot_at": status_board._hhmmss(runner.boot_at) if runner.boot_at else None,
        "end_at": status_board._hhmmss(runner.end_at) if runner.end_at else None,
        "run_rc": runner.run_rc,
    }


def symbol_row(
    tenant: Tenant,
    *,
    leaf_path: Path,
    session: status_board.TenantSession | None,
    day_key: str,
) -> dict[str, Any]:
    """한 종목의 줄. 잎을 읽지 못해도 줄은 난다 — 사유를 적고 나머지를 비운다."""
    row: dict[str, Any] = {
        "symbol": tenant.symbol,
        "tree_id": tenant.tree_id,
        "session": _session_block(session),
        "buy": dict(_EMPTY_SIDE),
        "sell": dict(_EMPTY_SIDE),
        "holding": {"quantity": None, "lots": None, "basis": HOLDING_BASIS},
        "halt": {
            "error": None,
            "last_flow": None,
            "last_withheld": None,
            "flow_counts": {},
        },
        "ticks": None,
        "error": None,
    }

    leaf = perf.read_leaf(leaf_path)
    if leaf.error is not None:
        row["error"] = _reduce_error(leaf.error)
        row["halt"]["error"] = row["error"]
        return row

    # 보유는 **누적**이다 — 오늘 산 것만이 아니라 아직 TOS 가 닫지 않은 전부.
    # perf.build_report 의 FIFO 가 그 단일 정의다.
    document = perf.build_report([leaf])
    symbols = document["symbols"]
    row["holding"]["quantity"] = (
        symbols[0]["totals"]["open_quantity"] if symbols else "0"
    )
    row["holding"]["lots"] = len(symbols[0]["open_lots"]) if symbols else 0

    # 결정 기록은 상태판의 잎 리더로 읽는다. 읽지 못하면 체결 줄은 그대로 내고
    # 차단 사유만 «모름» 이다 — 하나가 없다고 나머지를 버리지 않는다.
    facts = status_board.read_leaf(leaf_path)
    records: list[dict[str, Any]] = []
    halt_error: str | None = None
    if facts.error is not None or facts.records is None:
        halt_error = _reduce_error(facts.error or "UNKNOWN")
    else:
        records = facts.records
        row["ticks"] = sum(
            1
            for record in records
            if si.session_day_of(str(record["raw_event_id"])) == day_key
        )

    today_fills = [fill for fill in leaf.fills if fill.trading_date == day_key]
    row["buy"] = _side_block(today_fills, BUY, records)
    row["sell"] = _side_block(today_fills, SELL, records)
    row["halt"] = _halt_block(records, day_key, halt_error)
    return row


def _sessions_by_tree(
    cfg: status_board.BoardConfig, day_key: str, *, proc_root: Path | None
) -> dict[str, status_board.TenantSession]:
    """그날 돈 tenant 세션을 트리별로 하나씩 — 같은 날 여러 번 돌았으면 마지막 것.

    ``with_store=False``: 저장소 사실은 이 모듈이 종목 줄에 맞게 직접 읽으므로,
    상태판의 하루치 집계까지 다시 돌릴 이유가 없다. 여기서 쓰는 것은 러너 로그가
    말하는 트리 · 종목 · 부팅/종료와 :func:`status_board._session_status` 의 판정뿐이다.
    """
    root = cfg.state_dir / cfg.tenant_sessions_subdir
    sessions: dict[str, status_board.TenantSession] = {}
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return sessions
    for path in entries:
        if not path.is_dir():
            continue
        matched = status_board._SESSION_DIR_RE.match(path.name)
        if matched is None or matched.group("day") != day_key:
            continue
        session = status_board.read_tenant_session(
            path, leaves={}, cfg=cfg, proc_root=proc_root, with_store=False
        )
        tree_id = session.runner.tree_id
        if tree_id is None:
            continue
        prior = sessions.get(tree_id)
        # 가장 늦게 **시작한** 세션. 이름 순으로 고르면 r10 이 r2 보다 앞서므로
        # 재시작이 열 번을 넘는 날 조용히 틀린다.
        if prior is None or (session.runner.first_ts or "", session.name) > (
            prior.runner.first_ts or "",
            prior.name,
        ):
            sessions[tree_id] = session
    return sessions


def build_document(
    *,
    cfg: status_board.BoardConfig,
    day: _dt.date,
    today: _dt.date,
    config_dir: Path,
    proc_root: Path = Path("/proc"),
    tree_glob: str = perf.TENANT_TREE_GLOB,
) -> dict[str, Any]:
    """종목 줄 문서. pid 생존은 ``day == today`` 일 때만 본다(상태판과 같은 규칙)."""
    day_key = day.strftime("%Y%m%d")
    sessions = _sessions_by_tree(
        cfg, day_key, proc_root=proc_root if day == today else None
    )
    rows = []
    for tenant in discover_tenants(config_dir=config_dir, tree_glob=tree_glob):
        session = sessions.get(tenant.tree_id)
        # 그날 실제로 돈 세션이 말하는 잎을 먼저 쓴다 — 도출하지 않고 읽는다.
        leaf_path = (
            Path(session.runner.data_leaf)
            if session is not None and session.runner.data_leaf
            else _leaf_path(cfg.state_dir, tenant)
        )
        rows.append(
            symbol_row(tenant, leaf_path=leaf_path, session=session, day_key=day_key)
        )
    return {
        "schema_version": SYMBOLS_SCHEMA_VERSION,
        "date": day.isoformat(),
        "generated_kst": _dt.datetime.now(status_board.KST).isoformat(
            timespec="seconds"
        ),
        "holding_basis": HOLDING_BASIS,
        "symbols": rows,
    }


def export_symbols(
    *,
    config_path: Path = status_board.DEFAULT_CONFIG_PATH,
    out_dir: Path | None = None,
    state_dir: str | None = None,
    date: str | None = None,
    config_dir: Path | None = None,
    tree_glob: str = perf.TENANT_TREE_GLOB,
    proc_root: Path = Path("/proc"),
) -> Path:
    """문서를 만들어 쓰고, 어디에 놓였는지 돌려준다."""
    destination_root = default_out_dir() if out_dir is None else out_dir
    cfg = status_board.load_config(config_path)
    if state_dir is not None:
        cfg = status_board.BoardConfig(
            **{**cfg.__dict__, "state_dir": status_board.expand_path(state_dir)}
        )
    today = status_board.today_kst()
    day = _dt.date.fromisoformat(date) if date else today
    document = build_document(
        cfg=cfg,
        day=day,
        today=today,
        config_dir=config_dir or (REPO_ROOT / "config" / "tos_runtime"),
        proc_root=proc_root,
        tree_glob=tree_glob,
    )
    path = document_path(destination_root)
    try:
        export_bars._write_atomically(
            path, json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n"
        )
    except OSError as exc:
        raise ExportRefusal(f"{path}: 종목 문서를 쓰지 못했다: {exc}") from exc
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools.tos_cp3.export_symbols",
        description=(
            "종목마다 오늘의 매수 · 매도 · 보유 · 마지막 차단 사유를, 대시보드가 "
            "읽기 전용으로 bind-mount 한 디렉터리에 JSON 으로 내보낸다."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help=f"대상 루트 (기본: ${export_bars.PROJECTION_DIR_ENV})",
    )
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (기본: 오늘 KST)")
    parser.add_argument("--state-dir", default=None)
    parser.add_argument("--config", type=Path, default=status_board.DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """종목 문서를 내보낸다. 성공 ``0``, 거부 ``2``."""
    args = _parser().parse_args(argv)
    try:
        path = export_symbols(
            config_path=args.config,
            out_dir=None if args.out_dir is None else Path(args.out_dir),
            state_dir=args.state_dir,
            date=args.date,
        )
    except (ExportRefusal, ValueError, OSError) as exc:
        print(f"export-symbols refused: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
