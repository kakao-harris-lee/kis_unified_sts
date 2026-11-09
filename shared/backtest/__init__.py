"""백테스트 모듈

구성요소는 각자의 모듈에서 바로 가져온다 —
`from shared.backtest.market_context_replay import MarketContextReplay`.

부채꼴 re-export 는 레거시 제거 L7 에서 걷어냈다
(docs/plans/2026-11-07-legacy-removal-plan.md §3): `import shared.backtest` 하나로
optimizer → backend → vbt_runner · mlflow_tracker · adapter → regime 이 따라
들어왔고, 그 때문에 `import shared.backtest` 가 vectorbt 유무에 민감했다. 지금은
`__init__` 이 아무것도 import 하지 않고, 그 모듈들도 폐포 밖이라 같이 사라졌다 —
저장소에 vectorbt 를 import 하는 코드는 0 이다.
"""
