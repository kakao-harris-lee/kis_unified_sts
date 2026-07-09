# CandleChart 배선 인계 — 데이터 있는 모의투자 서버에서 진행 (main 기록)

- 작성일: 2026-07-09
- 목적: UX Tier-3 PR-B에서 **테스트 완료된 재사용 primitive로 만든 `CandleChart`**를
  실제 화면에 배선하는 남은 작업을, **Parquet 시장데이터가 있는 모의투자 서버에서
  이어서** 실행하는 방법을 main에 기록.
- 선행: [2026-07-09-ux-improvement-research.md](2026-07-09-ux-improvement-research.md)(Tier-3 D 항목),
  [2026-07-09-ux-tier1-execution-plan.md](2026-07-09-ux-tier1-execution-plan.md)
- 관련 커밋: PR-B `2067cbda`(market-data 라우트 + CandleChart primitive), main `08477f0e`(Tier-3 완료 시점)
- 운영 원칙: 스케줄/데이터 종속 검증은 로컬이 아니라 모의투자 서버에서 수행
  (`mem: verify-on-paper-server-not-local-cron`와 정합).

## 현재 상태 (main에 머지 완료)

| 구성요소 | 상태 | 위치 |
|---|---|---|
| **market-data bars 라우트** | ✅ 배선·동작 (등록됨) | `services/dashboard/routes/market_data.py` — `GET /api/market-data/bars?symbol=&asset_class=&timeframe=&days=`, `app.py`에 include 완료 |
| **`ParquetMarketDataStore` 래핑** | ✅ (데이터 없으면 `status:"empty"`로 degrade, 500 안 남) | `create_market_data_store()` → `get_minute_bars`/`get_daily_bars` |
| **`marketDataApi` 클라이언트** | ✅ | `strategy-builder-ui/src/lib/dashboard/marketData.ts` (`getBars`) |
| **`CandleChart` primitive** | ✅ 구현·테스트 완료, **단 어느 페이지에도 mount 안 됨** | `strategy-builder-ui/src/components/dashboard/CandleChart.tsx` (+ `.test.tsx`) |

**즉 데이터 파이프(라우트+클라이언트+차트)는 완성돼 있고, 남은 것은 "마커를 채우는
심볼-스코프 뷰"를 만들어 세 조각을 잇는 것뿐이다.**

## 왜 서버에서 하는가 (로컬 차단 사유)

로컬 체크아웃에는 Parquet 시장데이터가 없다 — `config/storage.yaml::market_data.parquet.root`
= `data/market`, 로컬에선 **디렉토리 부재 / 0 files**(2026-07-09 실측). 따라서 `/api/market-data/bars`가
로컬에선 항상 `status:"empty"`를 반환해 캔들이 렌더되지 않는다. 실제 캔들 + 마커 정렬을
눈으로 검증하려면 Parquet가 채워진 모의투자 서버가 필요하다.

## 남은 작업 — 심볼-스코프 뷰 배선

`CandleChart`는 아래 계약으로 완성돼 있다 (변경 불필요, 그대로 소비):

```tsx
// src/components/dashboard/CandleChart.tsx
export interface PriceMarker { t: string; price: number; side: "BUY" | "SELL"; label?: string }
export default function CandleChart(props: {
  bars: OhlcvBar[];        // marketDataApi.getBars(...).data.bars
  markers?: PriceMarker[]; // signals + fills를 {t, price, side} 로 매핑
  title: string;
  subtitle?: string;
}): JSX.Element
```

마커는 이미 존재하는 두 API에서 조립한다 (신규 백엔드 불요):
- **체결 마커**: `GET /api/trades/fills` → 각 fill의 `filled_at`(→`t`), `filled_price`(→`price`),
  `side`. PR-B에서 `slippage_bps`도 함께 나오므로 `label`에 슬리피지 표기 가능.
- **시그널 마커**(선택): `signalsApi.getSignals({asset_class})` → `timestamp`(→`t`),
  `price`, `side`. `symbol`으로 필터.

### 권장 배선 지점 (택1)
1. **`/signals` DecisionTracePanel 안** — 트레이스를 연 신호의 심볼로 `getBars` +
   해당 심볼의 fills/signal을 마커로. "왜 이 시점에 진입" 직관에 가장 부합.
2. **`/trades` 행 클릭 → 심볼 캔들 드로어** — 트레이드의 심볼·진입/청산 시각 전후 윈도우.
3. **`/positions` 심볼 상세** — 보유 포지션의 진입가 마커.

권장: **(1) DecisionTracePanel** — 이미 trade_id 딥링크(PR#2)가 있어 lineage 흐름과 일관.

### 구현 스케치 (서버에서)
```tsx
// 예: 심볼 s, 기간 days 로
const { data: bars } = useQuery({
  queryKey: ["market-bars", s, tf],
  queryFn: () => marketDataApi.getBars({ symbol: s, asset_class, timeframe: tf, days }).then(r => r.data),
});
const { data: fills } = useQuery({ queryKey: ["fills", asset_class], queryFn: ... });
const markers: PriceMarker[] = (fills?.fills ?? [])
  .filter(f => f.symbol === s)
  .map(f => ({ t: f.filled_at, price: f.filled_price, side: f.side,
               label: f.slippage_bps != null ? `${f.slippage_bps}bp` : undefined }));
return <CandleChart bars={bars?.bars ?? []} markers={markers} title={`${s} 진입 컨텍스트`} />;
```

**마커 시각(`t`)은 캔들 `t`와 정확히 일치해야 렌더된다** (`CandleSvg`의 `indexByT` 조회).
minute 타임프레임은 KIS/Parquet의 분봉 timestamp 포맷과 fill의 `filled_at` 포맷이
같은 해상도(분)로 정렬되는지 서버에서 확인 필요 — 불일치 시 분 단위로 반올림/버킷팅.

## 서버에서 이어서 할 일 (체크리스트)

### 사전조건
- Parquet 시장데이터 store(`data/market` 또는 `config/storage.yaml` 오버라이드) 채워짐.
- 대시보드 API 기동 (`services/dashboard`), Caddy `DASHBOARD_HOST_PORT` 뒤.
- 프론트: `cd strategy-builder-ui && npm run dev` (port 3100) 또는 빌드 배포.

### 1. 라우트 실증 (배선 전 데이터 확인)
```bash
# 실제 유니버스의 심볼로 — 분봉/일봉 둘 다
curl "http://<host>:<port>/api/market-data/bars?symbol=005930&asset_class=stock&timeframe=daily&days=30"
curl "http://<host>:<port>/api/market-data/bars?symbol=005930&asset_class=stock&timeframe=minute&days=2"
```
`status:"ok"` + `bars[]` 비어있지 않음을 확인. `empty`면 Parquet에 해당 심볼/기간 데이터가
없는 것 → 백필 상태부터 점검(`shared/collector/historical`, `/coverage` 페이지).

### 2. 뷰 배선 + 마커 정렬
- 위 스케치대로 선택 지점에 `CandleChart` mount.
- fill/signal 마커의 `t`가 캔들 `t`와 정렬돼 실제로 삼각형이 찍히는지 확인
  (안 찍히면 timestamp 해상도 불일치 → 분 버킷팅).
- KR 색상 관례 유지: 상승 캔들 빨강 / 하락 파랑 (이미 컴포넌트에 반영).

### 3. 검증 게이트
- `cd strategy-builder-ui && npm run lint && npm run build` green.
- 신규 뷰 컴포넌트 smoke 테스트 추가(빈 bars → empty state, 마커 매핑 단위).
- 데스크톱/모바일 렌더 확인 (paper-safe: 주문 컨트롤 미추가).
- 모의투자 서버에서 실 심볼로 캔들+마커 육안 확인 후 커밋.

## 비목표 / 주의
- **실시간 스트리밍 캔들 아님**: 사후 진단용 제한 윈도우 (Tier-3 결정: config-driven 알고
  시스템이라 차트-매매 아님). 대용량 실시간 최적화 불필요.
- `CandleChart`/`market_data.py`/`marketData.ts`는 **변경 불필요** — 소비만 하면 된다.
  변경이 필요하다고 느끼면 계약을 먼저 재검토.
- Parquet 백필이 비어 있으면 이 작업은 진행 불가 — 데이터부터.
