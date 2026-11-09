"""Historical Data Collection Module

과거 1분봉 OHLCV 데이터를 다룬다. 파서·백필은 정의 모듈에서 바로 가져온다 —
`from shared.collector.historical.ohlcv_parser import parse_ohlcv_rows`.
부채꼴 re-export 는 레거시 제거 L7 에서 걷어냈다
(docs/plans/2026-11-07-legacy-removal-plan.md §3).
"""
