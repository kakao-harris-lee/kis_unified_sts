"""LLM 분석 모듈

데이터 클래스·시장 컨텍스트는 정의 모듈에서 바로 가져온다 —
`from shared.llm.market_context import MarketContext`.
부채꼴 re-export 는 레거시 제거 L7 에서 걷어냈다
(docs/plans/2026-11-07-legacy-removal-plan.md §3): `shared.strategy.base` 가
`MarketContext` 를 타입 힌트로만 쓰는데도 `__init__` 이 수집기·분석기 37개를
통째로 끌고 왔다.
"""
