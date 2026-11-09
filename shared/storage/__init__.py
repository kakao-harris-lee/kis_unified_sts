"""Storage interfaces and implementations for runtime/research persistence.

스토어는 정의 모듈에서 바로 가져온다 —
`from shared.storage.market_data_store import ParquetMarketDataStore`.
부채꼴 re-export 는 레거시 제거 L7 에서 걷어냈다
(docs/plans/2026-11-07-legacy-removal-plan.md §3).
"""
