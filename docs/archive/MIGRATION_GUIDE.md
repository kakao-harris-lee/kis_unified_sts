> **ARCHIVED / HISTORICAL.** Initial project migration strategy. Current runtime
> and architecture rules live in [`../PROJECT_STATUS.md`](../PROJECT_STATUS.md),
> [`../ROADMAP.md`](../ROADMAP.md), and [`../../CLAUDE.md`](../../CLAUDE.md).

# 프로젝트 마이그레이션 전략

## ❌ 권장하지 않는 방식: 기존 프로젝트 하위 배치

```
kis-unified-trading/
├── quant_moment_sts/      # 기존 프로젝트 복사
├── kospi_mini_sts/        # 기존 프로젝트 복사
└── shared/                # 새로 작성?
```

**문제점:**
- 중복 코드가 그대로 남음 (KIS API, 지표 계산 등)
- 어떤 코드를 사용해야 할지 혼란
- 설정 기반 구조로 전환 어려움
- 의존성 충돌 가능

---

## ✅ 권장 방식: 코드 추출 마이그레이션

```
# 작업 디렉토리 구조
workspace/
├── quant_moment_sts/       # 기존 프로젝트 (참조용, 읽기 전용)
├── kospi_mini_sts/         # 기존 프로젝트 (참조용, 읽기 전용)
└── kis-unified-trading/    # 새 통합 프로젝트 (여기서 작업)
```

**장점:**
- 깔끔한 새 구조
- 중복 코드 완전 제거
- 설정 기반 아키텍처 적용
- 기존 코드 참조하면서 작업 가능

---

## 📋 마이그레이션 매핑 테이블

### Phase 1: 공통 인프라 추출

| 기존 위치 | 새 위치 | 작업 내용 |
|-----------|---------|-----------|
| `quant_moment_sts/core/auth.py` | `shared/kis/auth.py` | 토큰 관리 통합 |
| `kospi_mini_sts/src/common/kis_token.py` | `shared/kis/auth.py` | ↑ 병합 |
| `quant_moment_sts/core/websocket.py` | `shared/kis/websocket.py` | WebSocket 통합 |
| `kospi_mini_sts/src/collector/tick_collector.py` | `shared/kis/websocket.py` | ↑ 선물 기능 병합 |
| `quant_moment_sts/core/notifier.py` | `shared/notification/telegram.py` | 알림 통합 |
| `kospi_mini_sts/src/common/telegram.py` | `shared/notification/telegram.py` | ↑ 병합 |

### Phase 2: 지표 계산기 통합

| 기존 위치 | 새 위치 | 작업 내용 |
|-----------|---------|-----------|
| `quant_moment_sts/core/indicators.py` | `shared/indicators/` | BB, RSI, MA 등 분리 |
| `kospi_mini_sts/src/processor/feature_processor.py` | `shared/indicators/microstructure.py` | OFI, VPIN 추출 |

### Phase 3: 전략 마이그레이션

| 기존 위치 | 새 위치 | 작업 내용 |
|-----------|---------|-----------|
| `quant_moment_sts/core/signal_scanner.py` | `shared/strategy/entry/technical.py` | BB Entry 추출 |
| `quant_moment_sts/core/position_manager.py` | `shared/strategy/exit/three_stage.py` | 3-Stage Exit 추출 |
| `kospi_mini_sts/src/strategy/strategies/` | `shared/strategy/entry/microstructure.py` | OFI Entry 추출 |

### Phase 4: 서비스 계층

| 기존 위치 | 새 위치 | 작업 내용 |
|-----------|---------|-----------|
| `quant_moment_sts/core/orchestrator.py` | `services/trading/orchestrator.py` | 통합 오케스트레이터 |
| `quant_moment_sts/services/` (MLflow) | `services/backtest/mlflow_tracker.py` | MLflow 통합 |
| `kospi_mini_sts/src/backtest/` | `services/backtest/engine.py` | 백테스트 엔진 통합 |

---

## 🔧 Claude Code 작업 플로우

### Step 1: 프로젝트 초기화

```bash
# 작업 디렉토리 생성
mkdir -p workspace
cd workspace

# 기존 프로젝트 클론 (참조용)
git clone https://github.com/kakao-harris-lee/quant_moment_sts.git
git clone https://github.com/kakao-harris-lee/kospi_mini_sts.git

# 새 통합 프로젝트 생성
mkdir kis-unified-trading
cd kis-unified-trading
git init
```

### Step 2: 기본 구조 생성

```bash
# CLAUDE.md 복사
cp /path/to/CLAUDE.md .

# 디렉토리 구조 생성
mkdir -p config/strategies/{stock,futures}
mkdir -p config/{exit,risk}
mkdir -p shared/{config,strategy/{entry,exit,position},indicators,kis,models,notification}
mkdir -p domains/{stock,futures}/{strategies,universe}
mkdir -p services/{trading,backtest,monitoring}
mkdir -p cli/commands
mkdir -p tests/{unit,integration}
```

### Step 3: Claude Code로 마이그레이션

```bash
# Claude Code 시작
cd workspace
claude

# 예시 명령어들:
```

**명령어 1: KIS API 통합**
```
quant_moment_sts/core/auth.py와 kospi_mini_sts/src/common/kis_token.py를 분석해서
kis-unified-trading/shared/kis/auth.py로 통합해줘.
중복 코드 제거하고, 주식/선물 모두 지원하도록 해줘.
```

**명령어 2: 3-Stage Exit 추출**
```
quant_moment_sts/core/position_manager.py에서 3-Stage Exit 로직을 추출해서
kis-unified-trading/shared/strategy/exit/three_stage.py로 마이그레이션해줘.
모든 하드코딩된 값(2%, 5% 등)을 설정에서 받도록 리팩토링해줘.
```

**명령어 3: 설정 파일 생성**
```
quant_moment_sts의 BB Reversion 전략 파라미터를 분석해서
kis-unified-trading/config/strategies/stock/bb_reversion.yaml 파일을 생성해줘.
```

**명령어 4: OFI 전략 마이그레이션**
```
kospi_mini_sts/src/strategy/strategies/pure_micro.py를 분석해서
kis-unified-trading/shared/strategy/entry/microstructure.py로 마이그레이션해줘.
EntrySignalGenerator 인터페이스를 구현하도록 해줘.
```

---

## 📁 최종 디렉토리 구조

```
workspace/
│
├── quant_moment_sts/              # 🔒 참조용 (읽기 전용)
│   ├── core/
│   │   ├── auth.py               # → shared/kis/auth.py
│   │   ├── websocket.py          # → shared/kis/websocket.py
│   │   ├── indicators.py         # → shared/indicators/
│   │   ├── signal_scanner.py     # → shared/strategy/entry/
│   │   ├── position_manager.py   # → shared/strategy/exit/three_stage.py
│   │   └── ...
│   ├── services/                  # MLflow 관련
│   └── ...
│
├── kospi_mini_sts/                # 🔒 참조용 (읽기 전용)
│   ├── src/
│   │   ├── common/               # → shared/kis/, shared/notification/
│   │   ├── collector/            # → shared/kis/websocket.py
│   │   ├── processor/            # → shared/indicators/microstructure.py
│   │   ├── strategy/             # → shared/strategy/entry/
│   │   └── backtest/             # → services/backtest/
│   └── ...
│
└── kis-unified-trading/           # 🎯 새 통합 프로젝트
    ├── CLAUDE.md
    ├── pyproject.toml
    ├── config/
    │   ├── base.yaml
    │   ├── strategies/
    │   │   ├── stock/
    │   │   │   ├── bb_reversion.yaml
    │   │   │   └── volume_momentum.yaml
    │   │   └── futures/
    │   │       ├── pure_micro.yaml
    │   │       └── ofi_momentum.yaml
    │   ├── exit/
    │   └── risk/
    │
    ├── shared/                    # 통합된 공용 모듈
    │   ├── config/
    │   ├── strategy/
    │   │   ├── base.py
    │   │   ├── entry/
    │   │   │   ├── technical.py      # BB, Volume 등
    │   │   │   └── microstructure.py # OFI 등
    │   │   ├── exit/
    │   │   │   ├── three_stage.py    # 주식용
    │   │   │   └── scalping.py       # 선물용
    │   │   └── registry.py
    │   ├── indicators/
    │   ├── kis/
    │   └── notification/
    │
    ├── domains/
    │   ├── stock/
    │   └── futures/
    │
    ├── services/
    │   ├── trading/
    │   ├── backtest/
    │   │   ├── engine.py
    │   │   └── mlflow_tracker.py
    │   └── monitoring/
    │
    └── tests/
```

---

## 🔄 마이그레이션 체크리스트

### Week 1-2: 공통 인프라

- [ ] `kis-unified-trading/` 프로젝트 초기화
- [ ] `pyproject.toml` 작성
- [ ] `shared/config/` 구현 (설정 로더)
- [ ] `shared/kis/auth.py` 통합 (두 프로젝트 병합)
- [ ] `shared/kis/websocket.py` 통합
- [ ] `shared/kis/client.py` 통합 (REST API)
- [ ] `shared/notification/telegram.py` 통합
- [ ] `shared/models/` 공통 데이터 모델

### Week 3-4: 전략 프레임워크

- [ ] `shared/strategy/base.py` 인터페이스
- [ ] `shared/strategy/registry.py` 레지스트리
- [ ] `shared/strategy/entry/technical.py` (BB, Volume)
- [ ] `shared/strategy/entry/microstructure.py` (OFI)
- [ ] `shared/strategy/exit/three_stage.py` (주식)
- [ ] `shared/strategy/exit/scalping.py` (선물)
- [ ] `shared/indicators/` 지표 계산기 통합
- [ ] 설정 파일 작성 (YAML)

### Week 5: 백테스트 & MLflow

- [ ] `services/backtest/engine.py` 통합
- [ ] `services/backtest/mlflow_tracker.py` 마이그레이션
- [ ] CLI 명령어 구현

### Week 6: 서비스 통합

- [ ] `services/trading/orchestrator.py`
- [ ] `domains/stock/service.py`
- [ ] `domains/futures/service.py`
- [ ] 통합 테스트

### Week 7: 배포

- [ ] Docker 설정
- [ ] 모의투자 검증
- [ ] 문서화 완료

---

## ⚠️ 주의사항

### 기존 프로젝트 변경 금지
```bash
# 기존 프로젝트는 참조만!
cd quant_moment_sts
# 여기서 코드 수정 ❌

cd ../kis-unified-trading
# 여기서만 작업 ✅
```

### 점진적 마이그레이션
```
1. 새 프로젝트에서 기능 구현
2. 테스트 통과 확인
3. 기존 프로젝트와 결과 비교
4. 검증 후 다음 단계 진행
```

### 기존 프로젝트 아카이브 시점
```
# 통합 프로젝트가 안정화되면:
1. 기존 프로젝트 README에 deprecation 공지
2. 통합 프로젝트로 리다이렉트 안내
3. 6개월 후 아카이브 처리
```

---

## 🚀 시작하기

```bash
# 1. 작업 디렉토리 설정
mkdir -p ~/workspace/trading
cd ~/workspace/trading

# 2. 기존 프로젝트 클론
git clone https://github.com/kakao-harris-lee/quant_moment_sts.git
git clone https://github.com/kakao-harris-lee/kospi_mini_sts.git

# 3. 통합 프로젝트 생성
mkdir kis-unified-trading
cd kis-unified-trading

# 4. CLAUDE.md 배치 후 Claude Code 시작
# (CLAUDE.md, unified_implementation.py, config_examples.yaml 복사)

# 5. Claude Code 실행
claude
```

**첫 번째 명령어:**
```
CLAUDE.md를 읽고 프로젝트 구조를 파악한 뒤,
shared/config/loader.py와 shared/config/schema.py를 먼저 구현해줘.
```
