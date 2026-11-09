# LLM 시장 분석 모듈 (대부분 퇴역)

이 패키지는 KRX Open API 와 OpenAI GPT 로 시장 분석을 돌리던 곳이다. 수집기 ·
분석기 · 설정 로더 35개 모듈은 레거시 제거 **L7** 에서 사라졌다 — TOS 뿌리의
import 폐포 밖이었다(`docs/plans/2026-11-07-legacy-removal-plan.md` §3).
사라진 코드와 그것이 적어 두었던 KRX 전략·엔드포인트 설명은 태그
`legacy-final`(`6fc17c0f8d25`) 이후의 git 이력에 남아 있다.

## 지금 남은 것

| 파일 | 왜 남았나 |
|------|-----------|
| `data_classes.py` | 데이터 클래스·Enum. `market_context.py` 가 쓴다 |
| `market_context.py` | `MarketContext`. `shared/strategy/base.py` 가 `TYPE_CHECKING` 타입 힌트로만 참조한다 |

둘 다 **타입 표면**으로만 남아 있다. 이 패키지를 실행하는 경로는 없고,
`config/llm.yaml` · `LLMConfig` · `KRX_API_KEY` · `OPENAI_API_KEY` 도 함께
사라졌다. `shared/llm/__init__.py` 는 아무것도 re-export 하지 않으므로 이름은
정의 모듈에서 바로 가져온다 —
`from shared.llm.market_context import MarketContext`.

새 시장 분석이 필요하면 여기를 되살리지 말고 TOS 쪽에서 설계한다.
