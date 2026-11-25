"""전략 프레임워크

진입/청산/포지션 사이징 전략 추상화 계층.

Usage:
    from shared.strategy.base import EntrySignalGenerator, TradingStrategy

부채꼴 re-export 는 레거시 제거 L7 에서 걷어냈다
(docs/plans/2026-11-07-legacy-removal-plan.md §3): `shared.strategy` 를
import 하는 것만으로 registry → factory → strategy_builder → strategy_lab 가
따라 들어와 폐포가 부풀었고, 그 넷은 폐포 밖이라 같이 사라졌다. 남은 이름은
정의 모듈에서 바로 가져온다.
"""
