import pytest


class FakeVerifier:
    def __init__(self):
        self.kwargs = None

    async def verify(self, **kwargs):
        self.kwargs = kwargs


@pytest.mark.asyncio
async def test_verify_positions_with_broker_hands_dependencies_to_verifier():
    from services.trading.orchestrator import TradingOrchestrator

    orchestrator = TradingOrchestrator.__new__(TradingOrchestrator)
    verifier = FakeVerifier()
    config = object()
    kis_client = object()
    position_tracker = object()

    async def notify(message):
        return None

    orchestrator.config = config
    orchestrator._kis_client = kis_client
    orchestrator._position_tracker = position_tracker
    orchestrator._notify = notify
    orchestrator._broker_position_verifier = verifier

    await TradingOrchestrator._verify_positions_with_broker(orchestrator)

    assert verifier.kwargs == {
        "config": config,
        "kis_client": kis_client,
        "position_tracker": position_tracker,
        "notify": notify,
    }
