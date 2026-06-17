Next.js 프로젝트에서 개발 에이전트(Cursor, GPT Engineer 등)에게 바로 입력하여 작업을 수행할 수 있도록 작성된 컴포넌트 구현 및 연동 지시서(Agent Specification)입니다.

이 내용을 복사해서 에이전트에게 컨텍스트와 함께 프롬프트로 제공하시면 됩니다.

---

# 🤖 [Agent Instruction] Next.js기반 전략 빌더 파이프라인(Method A) 및 API 연동 구현 지시서

## 1. 개요 및 목적

본 작업의 목적은 한국 주식 시장 대상 LLM 및 시그널 기반 자동매매 시스템의 **[전략 빌더(Strategy Builder)]** 탭을 '수직 피드형 깔때기(Funnel) 파이프라인' 구조로 구현하는 것입니다. 유저가 화면에서 조립한 전략 조건은 JSON으로 직렬화되어 백엔드 CLI 엔진을 트리거하고, 실행 상태는 실시간으로 화면에 중계되어야 합니다.

### 기술 스택 환경

* **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, `shadcn/ui` (Card, Accordion, Slider, Switch, Button, Input)
* **Backend/Data:** Next.js Route Handlers (Node.js 환경), Redis (실시간 상태 관리 및 Pub/Sub 수신)
* **Core Engine:** JSON 파일을 아규먼트로 받아 실행되는 기존 Python CLI 백테스팅 엔진 (`backtest.py`)

---

## 2. 요구사항 및 UI/UX 컴포넌트 구조 (Method A)

`app/strategy-builder/page.tsx` (혹은 프로젝트 내 관련 경로)에 위에서 아래로 흐르는 3단계 카드 파이프라인을 구현하세요.

### Step 1: LLM Screener 카드 (`shadcn/ui` Card)

* **목적:** 1차 시장 유니버스 스크리닝 조건 설정
* **UI 요소:**
* LLM 모델 선택: `Select` 컴포넌트 (옵션: `custom-llm`, `gpt-4o`, `claude-3-5-sonnet`)
* 최소 신뢰도(Min Confidence): `Slider` 컴포넌트 (범위: 0.0 ~ 1.0, 기본값: 0.70, 스텝: 0.05)
* 프롬프트 프리셋: `Select` 또는 `RadioGroup` (옵션: `뉴스 감성 분석`, `공시 기반 스크리닝`, `종합 트렌드`)



### Step 2: Strategy Filter 카드 (`shadcn/ui` Card)

* **목적:** 2차 진입 시그널 조건 활성화 (AND 조건으로 결합)
* **UI 요소:**
* 퀀트 전략 토글 배지: `Switch` 또는 `Checkbox` 리스트
* `pattern_pullback` (눌림목 패턴 필터)
* `technical_consensus` (기술적 지표 컨센서스)
* `trend_continuation_vwap` (VWAP 추세 추종)
* `external` (외부 시그널)





### Step 3: Risk & MDD 카드 (`shadcn/ui` Card)

* **목적:** 리스크 관리 및 청산(Exit) 규칙 설정
* **UI 요소:**
* 허용 최대 낙폭(Target MDD): `Input (number)` 컴포넌트 (단위: %, 기본값: -5.0)
* 트레일링 스톱(Trailing Stop): `Input (number)` 컴포넌트 (단위: %, 기본값: 3.0)



### 하단 제어 바

* **전략 실행 버튼:** `Button` 컴포넌트 ("백테스트 실행" / "실전 매매 적용")
* 버튼 클릭 시 위 3개 카드의 상탯값(State)을 취합하여 지정된 JSON 스키마로 변환 후 API 요청을 보냅니다.

---

## 3. 데이터 직렬화 JSON 스키마 정의

에이전트는 API 요청 시 반드시 아래 구조의 데이터 규격을 생성하여 POST 바디로 전송하도록 상태 관리를 바인딩하세요.

```json
{
  "strategy_name": "USER_DEFINED_NAME_OR_TIMESTAMP",
  "screener": {
    "model": "custom-llm",
    "min_confidence": 0.75,
    "preset": "news_sentiment"
  },
  "filters": [
    "pattern_pullback",
    "technical_consensus"
  ],
  "risk": {
    "max_mdd": -5.0,
    "trailing_stop": 3.0
  }
}

```

---

## 4. 백엔드 연동 (Next.js Route Handler) 구현

`app/api/backtest/route.ts` 경로에 POST 핸들러를 작성하세요.

1. **CLI 엔진 트리거:** * 프론트엔드로부터 받은 JSON 설정을 임시 파일로 저장하거나 문자열 아규먼트로 변환합니다.
* Node.js의 `child_process.spawn`을 사용하여 파이썬 CLI 엔진을 비동기 실행합니다.
* 예시 명령어: `python3 backtest.py --config '{"screener":...}'`


2. **응답 처리:** * 프로세스가 성공적으로 시작되면 즉시 프론트엔드에 `{ "status": "started", "pid": 1234 }`를 반환하여 블로킹을 방지합니다.

---

## 5. 실시간 상태 동기화 및 모니터링 (Redis 연동)

1. **프로세스 인디케이터 연동:**
* CLI 엔진이 작동을 시작하면 콕핏 및 빌더 상단의 **`● Process`** 인디케이터 상태를 활성화(예: 녹색 점멸 또는 로딩 스피너)로 변경합니다.


2. **상태 스트리밍:**
* 파이썬 엔진이 실행되면서 진행 상황이나 실시간 MDD 도달 여부를 Redis 채널(`backtest:status`)에 `PUBLISH` 하도록 연동되어 있다고 가정합니다.
* Next.js 서버에서 해당 Redis 채널을 `SUBSCRIBE` 하고, 클라이언트와 **SSE(Server-Sent Events)** 연결을 수립하여 화면에 실시간 로그 및 진행률($0\% \rightarrow 100\%$)을 갱신하세요.



---

## 6. 에이전트 수행 가이드라인

* 모든 UI 컴포넌트는 기존 대시보드 테마(Dark/Light 모드 및 컬러 코드)와 이질감이 없도록 Tailwind 클래스를 세심하게 조정하세요.
* TypeScript 타입을 엄격하게 정의하세요 (`ScreenerConfig`, `FilterConfig`, `RiskConfig`, `BacktestRequestPayload`).
* 예외 처리: 입력값이 누락되었거나 MDD 수치가 양수로 입력되는 등 잘못된 퀀트 설정이 발생할 경우 클라이언트 단에서 1차 유효성 검사(Validation)를 수행하고 에러 토스트를 띄우세요.

---
