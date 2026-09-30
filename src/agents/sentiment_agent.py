"""
Sentiment & Macro Context Agent.
Evaluates market sentiment, funding rate bias on Hyperliquid, and macro liquidity conditions.
"""

from typing import Any, Dict
from src.agents.base_agent import BaseReviewAgent
from src.models import SentimentAnalysis, TradeSignal


class SentimentAgent(BaseReviewAgent):
    def __init__(self):
        super().__init__(name="Sentiment & Macro Agent")

    async def analyze(self, signal: TradeSignal, market_data: Dict[str, Any]) -> SentimentAnalysis:
        funding_rate = float(market_data.get("funding_rate", 0.0001))
        
        # Analyze funding rate bias
        if funding_rate > 0.0003:
            funding_bias = "HEAVY_LONGS"
            bias_note = "High positive funding: Longs paying shorts (crowded long trade)."
        elif funding_rate < -0.0002:
            funding_bias = "HEAVY_SHORTS"
            bias_note = "Negative funding: Shorts paying longs (potential short squeeze fuel)."
        else:
            funding_bias = "NEUTRAL"
            bias_note = "Balanced funding rates with healthy open interest."

        # Sentiment score from -100 to +100
        sentiment_score = int(market_data.get("sentiment_score", 45))
        
        if sentiment_score >= 60:
            market_phase = "GREED"
        elif sentiment_score >= 20:
            market_phase = "NEUTRAL"
        elif sentiment_score >= -20:
            market_phase = "FEAR"
        else:
            market_phase = "EXTREME_FEAR"

        key_drivers = [
            f"Hyperliquid Funding: {funding_rate * 100:.4f}%/8h ({bias_note})",
            f"Ecosystem narrative: Inflows steady on {signal.coin} perps",
        ]

        return SentimentAnalysis(
            sentiment_score=sentiment_score,
            market_phase=market_phase,
            funding_rate_bias=funding_bias,
            key_drivers=key_drivers,
        )
