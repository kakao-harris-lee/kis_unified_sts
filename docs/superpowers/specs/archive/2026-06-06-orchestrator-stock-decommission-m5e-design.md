# Orchestrator Stock Decommission (M5e) — Design

- Date: 2026-06-06
- Status: Design (pending implementation plan)
- Parent effort: `docs/superpowers/specs/2026-06-04-stream-pipeline-decoupling-design.md` (M5 cutover)
- Predecessors merged: M5a (#419), M5b (#420), M5c (#421), M5d cutover runbook+verify+rollback (#422)
- Scope: **M5e — the FINAL M5 sub-project.** A flag-gated CLI guard + script/doc decommission that makes the decoupled M4 pipeline the permanent stock path and prevents the monolithic orchestrator from resurrecting stock trading (double-trade guard).

## 1. Goal & scope

After the M5d cutover moves stock paper trading to the decoupled M4 pipeline (M4-P/R/O/X + M5a/b/c), the monolithic `TradingOrchestrator` no longer runs stock — but it CAN still be started for stock (`sts trade start --asset stock`), which would double-trade against the decoupled pipeline. M5e adds a flag-gated guard that lets the operator permanently block the orchestrator's stock path, plus deprecation notes on the stock-orchestrator scripts and doc updates. The orchestrator class stays (futures, Phase-5-gated, still uses it); M5e removes/guards only the STOCK entry path.

**Critical framing — merge-safe, operator-activated.** The guard is flag-gated `STOCK_ORCHESTRATOR_ENABLED` (default `"true"` = current behavior). Merging M5e changes NOTHING (stock orchestrator still works); the operator sets the flag `false` as the final M5d cutover step, after which the orchestrator permanently refuses stock. This matches the whole M5 philosophy (default-off / operator-gated) and means M5e can merge anytime without risking a stock blackout (a hard guard merged before the cutover would refuse stock while the decoupled pipeline isn't live yet).

**Success criterion:** (a) a single CLI guard at the one chokepoint (`cli/main.py::trade_start`) that, when `STOCK_ORCHESTRATOR_ENABLED` is false, rejects `--asset stock` with a clear message pointing to the decoupled pipeline (futures unaffected, default-true preserves current behavior); (b) deprecation notes on `scripts/cron/stock_trading.sh` + `install_stock_trading_watchdog.sh`; (c) docs (CLAUDE.md + the M5d runbook gains the enable/rollback step). **No orchestrator class change, no shared strategy/indicator change, no screener/fusion change.**

비목표(out of scope): reducing/refactoring the `TradingOrchestrator` class (stays for futures); removing shared strategy/indicator code (M4-P uses it); touching the screener→fusion pipeline (M4-P consumes the same Redis keys); a second guard in the orchestrator `__init__` (the CLI is the only start path — defense-in-depth deferred, YAGNI); futures decommission (separate, Phase-5).

## 2. Locked decisions (브레인스토밍 2026-06-06)

| 결정 | 선택 | 근거 |
|---|---|---|
| M5e 형태 | **가드 + 스크립트 폐기 + 문서** (클래스 축소 아님) | orchestrator는 generic(asset_class)이라 futures가 계속 씀 → 클래스 유지, stock 경로만 차단 |
| 가드 활성화 | **flag-gated, default-allow** (`STOCK_ORCHESTRATOR_ENABLED` 기본 true) | 머지 무영향(stock orchestrator 계속 가능), 운영자가 컷오버 후 flip. 하드 가드를 컷오버 전 머지하면 stock dark |
| 가드 위치 | **CLI `trade_start` 단일 chokepoint** | 모든 stock orchestrator 진입(CLI·stock_trading.sh·cron)이 여기로 수렴. orchestrator `__init__` 가드는 intent 은닉 → 비채택 |
| 플래그 매체 | **env** (`.env`, 운영자 관리) | M4/M5 데몬 env-flag + `KIS_REAL_TRADING` 선례와 일관. 운영자 flip이 repo 밖 |

## 3. Current state (감사 2026-06-06)

- **orchestrator는 generic**: `TradingOrchestrator`(`services/trading/orchestrator.py`)는 `asset_class` 분기(stock/futures) 단일 클래스. stock 분기(data_provider stream/ws, screener universe, EOD guard, balance query 등) 존재하나 클래스 자체는 futures와 공유 → **클래스 유지 필수**.
- **stock orchestrator 진입점**: `sts trade start --asset stock`(`cli/main.py::trade_start`, 단일 chokepoint) ← `scripts/cron/stock_trading.sh start` ← crontab(08:55 start/16:00 stop/5분 watchdog). repo 밖 systemd 없음. **bypass 경로 없음**(직접 TradingOrchestrator 인스턴스화하는 코드 없음).
- **`trade_start` 시그니처**: `(strategy, asset, capital, paper, daemon, yes_live)` click 커맨드. 이미 `os.getenv("KIS_REAL_TRADING")` 패턴 사용(os 모듈 레벨 import 존재).
- **M4가 stock 책임 100% 커버**: entry(M4-P)·risk(M4-R)·order(M4-O)·exit(M4-X)·대시보드(M5a)·LLM(M5b)·daily reset(M5c). caveat(pre-market warmup 1분봉만·Telegram 축소·수동 shutdown)는 M5d 문서화, 비차단.
- **공유/외부(무변경)**: StrategyManager/ThreeStageExit/IndicatorEngine/PositionTracker(M4 데몬이 사용), screener→fusion(`system:stock:trade_targets:latest` 등 — M4-P가 같은 키 소비).
- **CLI 테스트**: `tests/unit/test_cli_commands.py`/`test_cli_paper.py`(`click.testing.CliRunner`).

## 4. Components

### 4.1 CLI 가드 (`cli/main.py`)
모듈 레벨 순수 헬퍼 2개 + `trade_start` 최상단 가드:
```python
def _stock_orchestrator_enabled() -> bool:
    """Orchestrator runs stock only when explicitly enabled (default true).

    The operator sets STOCK_ORCHESTRATOR_ENABLED=false as the final M5d cutover
    step so the orchestrator permanently refuses stock (the decoupled M4 pipeline
    owns it). Rollback: set it back to true.
    """
    return os.getenv("STOCK_ORCHESTRATOR_ENABLED", "true").strip().lower() == "true"


def _stock_orchestrator_blocked(asset: str) -> bool:
    """True when the orchestrator must refuse this asset (stock + flag disabled)."""
    return asset == "stock" and not _stock_orchestrator_enabled()
```
`trade_start` 본문 최상단(orchestrator 구성 전, fail-fast):
```python
    if _stock_orchestrator_blocked(asset):
        click.echo(
            "Error: the monolithic orchestrator no longer runs stock — stock trades "
            "via the decoupled M4 pipeline "
            "(kis-stock-{strategy-daemon,risk-filter,order-router,exit-daemon}).",
            err=True,
        )
        click.echo(
            "  Rollback to the orchestrator stock path: set STOCK_ORCHESTRATOR_ENABLED=true.",
            err=True,
        )
        raise SystemExit(1)
```
- 순수 함수 2개 분리 → 빠른 단위 테스트(env만). default true → stock+true·unset 비차단(현 동작 보존), futures 절대 비차단.

### 4.2 스크립트 폐기
- `scripts/cron/stock_trading.sh`: 헤더에 deprecation 주석(컷오버 후 orchestrator stock 미운용 → decoupled M4; enforcement는 CLI 가드). enforcement 로직은 추가 안 함(스크립트가 CLI를 호출 → 가드가 처리).
- `scripts/cron/install_stock_trading_watchdog.sh`: deprecation 주석.

### 4.3 문서
- `CLAUDE.md`: CLI 섹션 `sts trade start --asset stock` deprecated 표기(+ decoupled 안내) · 환경변수 표에 `STOCK_ORCHESTRATOR_ENABLED` 추가 · 주식 섹션에 "stock=decoupled M4, orchestrator=futures 전용, 롤백=플래그" 명시.
- `docs/runbooks/stock-pipeline-cutover-m5d.md`: 컷오버 시퀀스 **최종 단계 추가** — `.env`에 `STOCK_ORCHESTRATOR_ENABLED=false`(영구 차단); 롤백 섹션에 `STOCK_ORCHESTRATOR_ENABLED=true` 추가.

## 5. Sequencing safety

`STOCK_ORCHESTRATOR_ENABLED` 기본 `"true"` → M5e 머지는 **현 동작 무변경**(stock orchestrator 계속 가능). 운영자가 컷오버 완료(verify --mode live 통과 + 첫 세션 안정) 후 `.env`에 `=false` → orchestrator stock 영구 거부. decoupled 미기동 상태에서 M5e를 머지해도 stock dark 안 됨. 하드 가드(무조건 거부)는 stock 블랙아웃 리스크라 비채택.

## 6. Testing
- **단위**(`tests/unit/test_cli_stock_guard.py` 신규):
  - `_stock_orchestrator_enabled()`: env unset→True, `"false"`→False, `"true"`→True, `"FALSE"`/`" false "`(대소문자·공백)→False.
  - `_stock_orchestrator_blocked(asset)`: `("stock", flag off)`→True, `("stock", unset/true)`→False, `("futures", flag off)`→False.
  - **CliRunner**: `trade start --asset stock` + `STOCK_ORCHESTRATOR_ENABLED=false` → exit_code 1 + stderr에 decoupled 안내(orchestrator 구성 전 fail-fast — 실제 트레이딩 미기동).
- **회귀**: futures 경로·기존 `test_cli_commands.py` 무영향 → green. full gate.
- 가드는 env만 읽으므로 Redis/외부 불필요.

## 7. Acceptance criteria
- [ ] `cli/main.py`: `_stock_orchestrator_enabled`/`_stock_orchestrator_blocked` + `trade_start` 가드. stock+off→exit 1(decoupled 메시지); stock+true·unset→비차단(현 동작); futures→절대 비차단.
- [ ] `STOCK_ORCHESTRATOR_ENABLED` 기본 `"true"`(머지 안전, 무변경).
- [ ] `stock_trading.sh` + `install_stock_trading_watchdog.sh` deprecation 주석.
- [ ] `CLAUDE.md`(deprecation + 플래그) + M5d 런북(컷오버 enable 단계 + 롤백) 갱신.
- [ ] orchestrator 클래스 / 공유 전략·지표 코드 / screener-fusion **무변경**.
- [ ] 단위 테스트(헬퍼 + CliRunner exit-1) green; Redis/외부 호출 없음.

### 운영자 활성화 (컷오버 후)
M5d 컷오버 최종 단계: `verify --mode live` 통과 + 첫 세션 안정 → `.env` `STOCK_ORCHESTRATOR_ENABLED=false` → orchestrator stock 영구 거부. 롤백: `=true` + 크론 재활성(rollback.sh) + orchestrator 재기동.

## 8. Open questions (구현 계획에서 확정)
- 가드 메시지 문구(decoupled 데몬 이름 정확) — 위 §4.1 안 사용.
- CLI 테스트 위치: 신규 `tests/unit/test_cli_stock_guard.py` vs 기존 `test_cli_commands.py` 추가(신규 파일 권장 — 격리).
- orchestrator `__init__` defense-in-depth 2차 가드 포함 여부(CLI가 유일 경로 → YAGNI, 생략 권장).
- `stock_trading.sh`에 플래그 echo 경고 추가 여부(CLI 가드로 충분 → 주석만 권장).
