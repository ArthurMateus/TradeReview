"""
Unit tests for the Multi-Agent Review Pipeline.
"""

import pytest
from src.agents.consensus_engine import ConsensusEngine
from src.agents.graph_agent import GraphAgent
from src.agents.risk_guard_agent import RiskGuardAgent
from src.agents.sentiment_agent import SentimentAgent
from src.agents.trader_intent_agent import TraderIntentAgent
from src.models import IntentClassification, RecommendationEnum, TradeActionType, TradeDirection, TradeSignal


@pytest.fixture
def sample_signal():
    return TradeSignal(
        id="TEST_001",
        master_address="0x1111111111111111111111111111111111111111",
        coin="BTC",
        direction=TradeDirection.LONG,
        action=TradeActionType.OPEN,
        price=65000.0,
        size=1.0,
        usd_value=65000.0,
        leverage=10,
    )


@pytest.mark.asyncio
async def test_risk_guard_scales_leverage(sample_signal):
    risk_agent = RiskGuardAgent()
    market_data = {"account_equity": 5000.0}
    result = await risk_agent.analyze(sample_signal, market_data)

    # Master used 10x, but config max_leverage is 5
    assert result.recommended_leverage <= 5
    assert result.suggested_stop_loss_price < sample_signal.price
    assert len(result.risk_flags) > 0


@pytest.mark.asyncio
async def test_trader_intent_detects_revenge(sample_signal):
    intent_agent = TraderIntentAgent()
    # 3 consecutive losses + 10x leverage = REVENGE_FOMO
    market_data = {"recent_losses_count": 3}
    result = await intent_agent.analyze(sample_signal, market_data)

    assert result.intent == IntentClassification.REVENGE_FOMO
    assert result.is_revenge_risk is True


@pytest.mark.asyncio
async def test_consensus_engine_rejects_revenge_trade(sample_signal):
    engine = ConsensusEngine()
    market_data = {
        "recent_losses_count": 3,
        "rsi_14": 50.0,
        "funding_rate": 0.0001,
        "sentiment_score": 10,
    }
    decision = await engine.evaluate_signal(sample_signal, market_data)

    assert decision.recommendation == RecommendationEnum.REJECT
    assert "REJECT" in decision.formatted_card_markdown
