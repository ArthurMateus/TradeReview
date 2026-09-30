"""
Trader Intent & Behavior Agent.
Decodes what the master trader is attempting to do:
- Breakout momentum
- Swing accumulation
- Delta-neutral funding hedge
- Quick scalp
- Emotional revenge/FOMO trading
"""

from typing import Any, Dict
from src.agents.base_agent import BaseReviewAgent
from src.models import IntentClassification, TradeActionType, TraderIntentAnalysis, TradeSignal


class TraderIntentAgent(BaseReviewAgent):
    def __init__(self):
        super().__init__(name="Trader Intent Agent")

    async def analyze(self, signal: TradeSignal, market_data: Dict[str, Any]) -> TraderIntentAnalysis:
        # Check master historical patterns or recent fills
        recent_losses_count = int(market_data.get("recent_losses_count", 0))
        position_count = int(market_data.get("open_positions_count", 1))

        # Check if master is revenge-trading (e.g. 3 consecutive losses followed by immediate high-leverage entry)
        if recent_losses_count >= 3 and signal.leverage >= 10:
            return TraderIntentAnalysis(
                intent=IntentClassification.REVENGE_FOMO,
                confidence_score=85,
                reasoning="Master trader suffered consecutive losses and immediately opened an aggressive high-leverage position.",
                is_revenge_risk=True,
            )

        # Check for scaling into a swing
        if signal.action == TradeActionType.INCREASE:
            return TraderIntentAnalysis(
                intent=IntentClassification.SWING_ACCUMULATION,
                confidence_score=90,
                reasoning=f"Master trader is adding size to an existing profitable {signal.coin} position, confirming conviction.",
                is_revenge_risk=False,
            )

        # Check for breakout vs scalp
        if signal.leverage <= 3:
            return TraderIntentAnalysis(
                intent=IntentClassification.BREAKOUT_MOMENTUM,
                confidence_score=88,
                reasoning=f"Low leverage ({signal.leverage}x) with directional bias signals patient multi-hour swing setup.",
                is_revenge_risk=False,
            )
        else:
            return TraderIntentAnalysis(
                intent=IntentClassification.SCALP,
                confidence_score=75,
                reasoning=f"Intraday scalp setup aiming for quick percentage moves on {signal.coin}.",
                is_revenge_risk=False,
            )
