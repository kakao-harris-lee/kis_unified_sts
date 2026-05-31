# 선물 전략 빌더 (Futures Strategy Builder) — 설계 스펙

- **작성일**: 2026-06-01
- **상태**: 설계 승인됨 (구현 계획 대기)
- **관련 문서**:
  - `docs/superpowers/specs/2026-05-12-dashboard-redesign-design.md` (대시보드/빌더 기반)
  - `docs/STRATEGY_BUILDER_UI.md` (빌더 UI 현황)
  - `CLAUDE.md` — 선물 합의사항, builder→paper 브릿지 정책

---

## 1. 배경 & 목표

프론트엔드(`strategy-builder-ui/`)에는 **주식 전용** 노코드 전략 빌더(`/builder`)가 구현되어 있다.
선물에는 빌더가 없고, 선물 전략(Setup A/C, williams_r_15m 등)은 손으로 작성한 YAML로만 운용된다.

본 작업의 목표는 **기존 주식 빌더를 멀티-자산으로 확장**하여, **지표 기반 long-only 선물 전략**을
빌더로 생성하고 **paper**로 등록·운용할 수 있게 하는 것이다. CLAUDE.md 로드맵
("향후 Williams %R / RSI / MACD 등 명시적 기술 지표 기반 신규 전략 추가 예정", 2026-05-15 운영 결정)과
정확히 일치한다.

### 검토에서 확인된 핵심 사실

1. **지표는 이미 자산군 중립이다.** 빌더 지표 카탈로그(프론트 `lib/builder/constants.ts` 80개,
   백엔드 `config/strategy_builder/indicators.yaml` 24개)는 둘 다 `asset_class` 필드가 없는 단일 공유
   목록이다. 평가기(`shared/strategy_builder/evaluator.py`)·스키마·지표 모듈 어디에도 자산군 필터가
   없다. 사용자가 "지표가 선물/주식으로 나뉜 듯"하다고 느낀 것은 *전략 레벨*(선물 전략이
   `config/strategies/futures/`에서 특정 지표 세트를 손으로 구성)이지 *카탈로그 레벨*이 아니다.
   → "지표 공유"는 사실상 현재 설계이며 추가 작업이 거의 없다.

2. **선물도 주식과 동일한 실행 경로를 탄다.** Setup A/C는 `shared/strategy/entry/setup_adapters.py`의
   어댑터로 레지스트리에 등록되어 **`TradingOrchestrator`에서 주식과 동일하게 실행**된다.
   `services/decision_engine/`·`risk_filter/`·`order_router/`(Phase 5 paradigm)는 **코드만 존재하고
   미배포**다. 따라서 `asset_class: futures`로 태깅된 builder_v1 전략은 이미 선물을 지원하는 동일
   오케스트레이터(H0IFCNT0 체결 피드, `KIS_FUTURES_*` 계좌, A05xxx 미니 근월물 자동감지)를 그대로
   탄다. **신규 런타임 배선이 필요 없다 — 본 작업의 가장 큰 강점.**

3. **선물 차단은 구조적 한계가 아니라 운영 게이트다.** 라이브 등록 경로는
   `services/dashboard/routes/kis_builder.py:681`에서 `asset_class != "stock"`이면 HTTP 400으로
   거부한다(주석: "stock-only in Phase 1"). 백엔드 스키마
   `shared/strategy_builder/schema.py:176`의 `BuilderState.asset_class`는 이미
   `Literal["stock", "futures"]`로 정의되어 있다.

### 라이브 등록 경로 (확정)

```
/builder (page.tsx)
  → BuilderState  (types/builder.ts — 현재 asset_class 필드 없음)
  → 지표: lib/builder/constants.ts (하드코딩 80개, 단일 목록)
  → 등록: CustomStrategyList.tsx → registerPaperStrategy()
          → POST /api/kis-builder/register-paper   (kis_builder.py:746)
  → 백엔드 검증: shared/strategy_builder/schema.py::BuilderState
  → ❌ 게이트: kis_builder.py:681  →  asset_class != "stock" 면 HTTP 400
  → 통과 시 _build_strategy_yaml() → config/strategies/built/<id>.yaml
          (entry.type=builder_v1, exit.type=builder_v1_exit, asset_class 태깅)
  → 런타임: ConfigLoader.load_all_strategies("futures") → TradingOrchestrator
```

> 참고: `/api/strategy-builder/capabilities` + `config/strategy_builder/indicators.yaml`(24개)는
> 라이브 `/builder` 페이지가 소비하지 않는 **부분 배선된 병렬 경로**(upstream fork 잔재로 추정,
> `strategy-builder-ui/UPSTREAM.md` 참조)다. 본 작업은 **라이브 경로(constants.ts +
> kis-builder/register-paper)** 를 기준으로 한다.

### 발견된 선행조건: camelCase↔snake_case 직렬화 (PR 1)

검토 중 경험적으로 확인된 **기존 잠재 버그**: 프론트 `BuilderState`는 camelCase
(`indicatorId`/`displayName`/`indicatorAlias`/`stopLoss`)이고 `registerPaperStrategy`는 변환 없이
그대로 전송하지만(`apiPost` = `JSON.stringify`), Python 스키마(`shared/strategy_builder/schema.py`)는
**snake_case + `extra="forbid"` + alias 없음**이라 **실전 전략 등록 시 stock·futures 모두 HTTP 400**이
난다(`BuilderState.model_validate(camelCase)` → REJECTED 확인). register-paper는 #356/#357로 최근
추가되어 실제 상태로 미검증된 상태다.

→ 선물 빌더가 동작하려면(주식 포함) 이 정합이 **필수 선행 조건**이다. 운영 결정(2026-06-01)에 따라
**별도 선행 PR(PR 1)** 로 분리한다. 해법: 빌더 입력 모델에 `alias_generator=to_camel`
+ `populate_by_name=True`를 추가해 camel(프론트)·snake(테스트/YAML)을 모두 수용하고, `model_dump`는
snake로 유지하여 런타임/YAML은 불변. 상세 태스크: `docs/superpowers/plans/2026-06-01-futures-strategy-builder.md` PR 1.

---

## 2. 스코프 & 비목표

### 대상 (In Scope)

- 기존 `/builder`를 멀티-자산으로 확장 — 자산군 토글(주식/선물).
- **지표 기반 long-only 선물 전략**을 빌더로 생성 → **paper** 등록·운용.
- 선물 전략에 **EOD 청산 + 하드스톱 자동 강제** (사용자 비활성화 불가).
- 지표 카탈로그 공유 + 미니 선물 부적합 지표에 **자문 경고(차단 없음)**.

### 비목표 (Explicitly Out of Scope)

- ❌ **Setup A/C 빌더화** — macro overnight gap·이벤트 캘린더·regime gate·LLM veto 입력 블록이
  빌더에 없다. 백테스트 시 macro 데이터가 mock이라 정합성도 떨어진다. Setup A/C는 **계속 손으로
  작성하는 YAML로 유지**하며 빌더는 이를 건드리지 않는다.
- ❌ **숏(공매도) 진입/청산** — Phase 2. (아래 §3 제약 참조)
- ❌ **선물 live 자동 활성화** — 빌더 산출 전략은 **paper-only**. live는 기존
  `config/futures_live.yaml::enabled` + Redis `futures:live:suspended` 게이트 뒤에 그대로 둔다.
- ❌ UI 심볼 선택기, UI 백테스트 버튼 — 오케스트레이터 자동감지 + CLI 백테스트로 충분(Phase 2 옵션).
- ❌ 트레일링 스탑 — builder_v1_exit v1에서 미구현 상태 유지(기존과 동일).

---

## 3. 핵심 제약: 숏 셀링 (CLAUDE.md 합의사항과의 정합)

CLAUDE.md 선물 합의사항은 다음을 명시한다:

> "선물 paper/live 모두 숏 진입 및 숏 청산(BUY to cover)을 지원해야 한다."

Phase 1 빌더는 long-only 전략만 **생성**한다. 이는 합의사항과 충돌하지 않는다:

- **플랫폼의 숏 능력은 그대로 유지된다.** Setup A/C·오케스트레이터·KIS 실행 경로는 계속 숏을 지원한다.
- 제한되는 것은 **빌더 UI가 생성하는 전략의 방향**뿐이다(long만). 빌더는 선물 숏 능력을 *제거하지
  않으며*, 단지 아직 *노출하지 않는다*.
- Phase 2에서 방향 선택기(long/short) + 평가기 양방향 방출 + entry/exit 숏 처리를 추가한다.

**스펙·코드·UI에 이 제약을 명시한다**: 선물 빌더 진입은 "long-only (Phase 1)"로 라벨링하고,
게이트 응답/로그에도 동일하게 표기한다.

### Phase 1에서 long-only가 안전한 기술적 이유

`builder_v1_exit`의 손익 수식(`builder_strategy_exit.py:93`)은
`pnl_pct = (current_price - entry_price) / entry_price * 100`으로 **long 기준**이다.
숏 포지션에서는 부호가 반대여야 하므로 잘못된다. long-only Phase 1에서는 이 수식이 그대로 유효하며,
숏 도입 시 방향 인지 수식으로 교체해야 한다(Phase 2).

---

## 4. 설계

### A. 프론트엔드 변경 (`strategy-builder-ui/`)

| # | 파일 | 변경 |
|---|------|------|
| A1 | `src/types/builder.ts` | `BuilderState`에 `asset_class: "stock" \| "futures"` 추가 (기본 `"stock"`). 현재 누락되어 백엔드 기본값에 암묵 의존 중 — 명시화. |
| A2 | `src/app/builder/page.tsx` (+ `hooks/useStrategyBuilder.ts`) | 자산군 토글 추가. `INITIAL_STATE`에 `asset_class` 반영. 앱 기존 `useAssetClass()` / 선물·주식 탭 패턴과 일관되게 배치. |
| A3 | `src/components/builder/MetadataEditor.tsx` 또는 빌더 헤더 | 자산군 선택 컨트롤(라디오/세그먼트). 선물 선택 시 "long-only (Phase 1)" 안내 표기. |
| A4 | `src/lib/builder/constants.ts` | `IndicatorDefinition`에 선택적 `futuresApplicability?: "ok" \| "degraded"` 메타 추가. 선물 모드에서 `degraded` 지표(orderbook depth, VWAP 등)에 "선물 권장 안 함" 배지 표시. **차단 없음.** |
| A5 | `src/components/builder/IndicatorSelector.tsx` | 선물 모드일 때 A4 배지 렌더링. 기본 선택은 막지 않음. |
| A6 | `src/lib/api/strategies.ts` (`registerPaperStrategy`) | `builder_state.asset_class`를 그대로 전송. 시그니처 변경 최소(이미 `builder_state` 전체를 보냄). |
| A7 | `src/lib/builder/presets.ts` (선택) | 선물용 시작 프리셋(williams_r, RSI, MACD/EMA, BB) 추가 — UX 편의, 인프라 무관. |

### B. 백엔드 변경

| # | 파일 | 변경 |
|---|------|------|
| B1 | `services/dashboard/routes/kis_builder.py:681` | 게이트 완화: `asset_class != "stock"` 거부 → `{"stock", "futures"}` 화이트리스트. 선물이면 long-only·paper-only임을 응답 메타/로그에 명시. 그 외 값은 400 유지. |
| B2 | `shared/strategy/entry/builder_strategy.py:111` | `asset_class != "stock"` no-op 가드 **제거** → 선물에서도 long 시그널 생성. `signal_direction:"long"`(line 165)은 Phase 1 유지(정합). docstring의 "stock-only" 문구 갱신. |
| B3 | `shared/strategy/exit/builder_strategy_exit.py` | **선물 안전 모드 추가** (아래 §B-detail). |
| B4 | `services/dashboard/routes/kis_builder.py::_build_strategy_yaml` | 이미 `asset_class` 태깅됨(line 711). 선물일 때 안전값(EOD/하드스톱)을 exit params에 주입 + 포지션 사이징 매핑(§F-1). |
| B5 | `shared/strategy_builder/schema.py` | `IndicatorDefinition`에 선택적 `asset_applicability` 메타 추가 검토(프론트 A4와 동기화 여부는 §F-3). |

#### B-detail: `builder_v1_exit` 선물 안전 모드

`builder_state.asset_class == "futures"`일 때, 사용자 설정과 **무관하게** 다음을 강제한다
(모든 값은 config에서 로드 — 하드코딩 금지):

1. **하드스톱 상한(cap)**: 선물은 허용 손실의 절대 상한(예: -3%)을 강제한다.
   `stop_loss_pct`는 양수이고 `pnl_pct <= -stop_loss_pct`에서 청산되므로, **더 타이트한(작은)
   임계값**이 안전하다. 따라서:
   - 사용자가 더 느슨하게 설정(예: 10%)하면 → config 하드스톱(3%)으로 좁힌다.
   - 사용자가 더 타이트하게 설정(예: 1%)하면 → 사용자 값(1%)을 유지한다.
   - 사용자가 0(비활성)으로 설정해도 → 선물은 **비활성 불가**, 하드스톱(3%)을 적용한다.
   - 의미: `effective_stop = futures_hard_stop if user_stop <= 0 else min(user_stop, futures_hard_stop)`.
2. **EOD 시간 청산**: config 기본 **15:15 KST** 도달 시 강제 청산. 기존 KST 변환 패턴(CLAUDE.md §5,
   `_KST = ZoneInfo("Asia/Seoul")`, `builder_strategy_exit.py:26`에 이미 존재) 사용.

> **왜 오케스트레이터 일반 EOD 청산에 의존하지 않는가:** 오케스트레이터
> `_close_intraday_positions`(`orchestrator.py:3992`)는 비-swing·비-rl 선물 포지션을 닫지만,
> 동작 시점이 **선물 장마감 15:45**(`futures_close`, `orchestrator.py:307`)다. CLAUDE.md 선물 EOD
> 기준인 **15:15**과 다르다. 따라서 안전장치를 builder_v1_exit에 직접 두어 시점을 명확히 통제한다.

### C. 런타임/데이터 흐름 (변경 없음 — 확인용)

```
built/<id>.yaml (asset_class: futures, enabled 토글)
  → ConfigLoader.load_all_strategies("futures")  # built/ 에서 asset_class 필터로 픽업
  → StrategyFactory.create_from_file("futures", <id>)
  → TradingOrchestrator(asset_class=futures)
       ├─ 피드: KISFuturesPriceFeed (H0IFCNT0 체결 + H0IFASP0 호가)
       ├─ 계좌: KIS_FUTURES_APP_KEY / SECRET / ACCOUNT_NO
       ├─ 심볼: A05xxx 미니 근월물 자동감지 (_get_futures_default_symbols)
       └─ live 게이트: futures_live.yaml + Redis suspended (paper 에서는 무관)
```

신규 런타임 배선 없음. 빌더 산출물은 손작성 선물 YAML과 동일한 적재 경로를 탄다.

---

## 5. 테스트 전략

| 영역 | 테스트 |
|------|--------|
| 게이트 | `register-paper`에 stock/futures 통과, 그 외 asset_class 400 |
| 진입 | `builder_v1` 선물 long 진입 시그널 생성(no-op 가드 제거 검증), `signal_direction == "long"` |
| 청산 안전모드 | 선물 하드스톱 상한 강제(사용자가 10% 설정해도 3%에서 청산), 사용자 0(비활성) 설정해도 3% 적용, EOD 15:15 KST 강제 청산, config 값 로드 |
| 스키마 | `BuilderState.asset_class` round-trip: 프론트 직렬화 → schema 검증 → YAML 머티리얼라이즈 |
| 통합 | 선물 register-paper → `built/<id>.yaml` → `ConfigLoader.load_all_strategies("futures")` 픽업 |
| 회귀 | 주식 빌더 기존 동작 불변(기본 asset_class="stock", three_stage 미사용 경로 영향 없음) |
| 프론트 | 자산군 토글 상태, 선물 모드 지표 배지, asset_class 전송 |

`.venv/bin/pytest tests/ -v` (venv 필수). 신규 테스트는 `tests/unit/dashboard/`,
`tests/unit/strategy/` 등 기존 위치 컨벤션을 따른다.

---

## 6. 열린 설계 항목 (구현 계획 단계에서 확정)

### F-1. 선물 포지션 사이징 (가장 중요)

머티리얼라이즈된 YAML은 `position.type=fixed, params.order_amount_per_stock`(KRW 금액)을 쓴다.
선물은 **계약 수 단위**로 거래하므로 KRW 금액 매핑이 부적절하다.

- **권장안**: 선물 빌더는 사이징 입력을 "계약 수(quantity)"로 받아, `fixed` 사이저에 계약 수량을
  직접 전달하거나 선물 전용 사이저 키로 매핑한다. KOSPI200 미니 계약 명세는
  `config/execution.yaml::futures_contract_spec`(multiplier 50,000 KRW/pt).
- 계획 단계에서 기존 `position/sizers.py`의 `fixed` 사이저가 선물 quantity를 어떻게 해석하는지
  확인 후 확정.

### F-2. 선물 안전값 config 위치

- 옵션 A: 신규 `config/strategy_builder/futures_safety.yaml` (`hard_stop_pct`, `eod_close_time`).
- 옵션 B: 기존 `config/execution.yaml`에 `futures_builder_safety` 섹션 추가.
- **권장**: 빌더 전용 안전값이므로 옵션 A(빌더 도메인 응집). 계획 단계에서 결정.

### F-3. 지표 적합성 메타 출처

- 프론트 `constants.ts`에만 `futuresApplicability`를 둘지, 백엔드 카탈로그
  (`indicators.yaml` / `schema.py`)와 동기화할지.
- **권장**: Phase 1은 프론트 단독(표시 전용이므로). 백엔드 동기화는 카탈로그 통합 시점에 함께.

---

## 7. 단계 (Phasing)

- **Phase 1 (본 스펙)**: 게이트 완화 + asset_class UI 토글 + builder_v1 선물 long 진입 + builder_v1_exit
  선물 안전모드(EOD/하드스톱) + 지표 자문 경고 + 테스트. 산출물은 **paper-only**.
- **Phase 2 (후속, 별도 스펙)**: 숏 방향 선택기 + 평가기 양방향 방출 + 방향 인지 손익/청산, UI 심볼/계약
  선택기, UI 백테스트, 지표 적합성 백엔드 동기화.

---

## 8. 수용 기준 (Acceptance Criteria)

- [ ] `/builder`에서 자산군을 선물로 전환할 수 있고, 상태에 `asset_class: "futures"`가 반영된다.
- [ ] 선물 모드에서 미니 부적합 지표에 자문 배지가 뜨되, 선택은 차단되지 않는다.
- [ ] 선물 전략을 register-paper로 등록하면 HTTP 400 없이 `built/<id>.yaml (asset_class: futures)`가
      생성된다.
- [ ] 등록된 선물 빌더 전략이 `ConfigLoader.load_all_strategies("futures")`로 픽업되어 오케스트레이터
      선물 경로에서 paper 실행된다.
- [ ] 선물 빌더 전략은 사용자 설정과 무관하게 하드스톱 상한(예: -3%)과 EOD 15:15 청산이 강제된다(테스트로 증명).
- [ ] 선물 진입은 long-only이며, UI·응답·로그에 그렇게 표기된다.
- [ ] 주식 빌더의 기존 동작이 회귀하지 않는다.
- [ ] 선물 live는 본 작업으로 활성화되지 않는다(기존 게이트 불변).
- [ ] `.venv/bin/pytest tests/ -v` 그린.

---

## 9. 리스크

| 리스크 | 완화 |
|--------|------|
| 선물 포지션 사이징 매핑 오류(KRW vs 계약 수) | F-1을 계획 단계 1순위로 확정, 테스트로 검증 |
| 숏 미지원이 CLAUDE.md 합의와 충돌로 보일 우려 | §3에서 "플랫폼 능력 유지, 빌더 UI만 long 한정" 명시 |
| 미니 유동성 낮은 지표로 만든 전략의 품질 | 자문 경고 + paper-only 운용 + 후속 평가(model-evaluator) |
| 두 빌더 lineage 혼동(constants.ts vs capabilities) | §1에서 라이브 경로 확정, 본 작업은 라이브 경로만 변경 |
| EOD 시점 불일치(15:15 vs 15:45) | builder_v1_exit에 안전장치 직접 구현(§B-detail) |
