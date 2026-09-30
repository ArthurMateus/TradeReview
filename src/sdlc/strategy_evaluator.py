"""
AI Strategy Evaluator & Self-Improvement Loop.
Conducts post-mortem analysis on executed trades and suggests rule / prompt adjustments.
"""

from typing import Any, Dict, List
from pydantic import BaseModel, Field


class TradePostMortem(BaseModel):
    trade_id: str
    coin: str
    realized_pnl_usd: float
    was_profitable: bool
    ai_score_at_entry: int
    lessons_learned: str
    suggested_parameter_tweaks: List[str] = Field(default_factory=list)


class StrategyEvaluator:
    def __init__(self):
        pass

    def evaluate_closed_trade(
        self,
        trade_id: str,
        coin: str,
        entry_price: float,
        exit_price: float,
        pnl_usd: float,
        ai_score: int,
        entry_notes: str,
    ) -> TradePostMortem:
        """
        Synthesizes trade outcome with entry conditions to generate lessons and parameter tweaks.
        """
        was_profitable = pnl_usd > 0
        tweaks = []

        if not was_profitable:
            if ai_score >= 80:
                lessons = (
                    f"False positive alert: High AI score ({ai_score}) failed to protect capital on {coin}. "
                    f"Possible macro reversal or excessive slippage on entry."
                )
                tweaks.append("Increase weight of Funding Rate bias in Sentiment Agent.")
                tweaks.append("Tighten maximum leverage allowance when 1h RSI is above 65.")
            else:
                lessons = f"Marginal trade ({ai_score} score) resulted in loss as expected. Hard stop-loss prevented liquidation."
                tweaks.append("Raise auto-approval threshold to 80.")
        else:
            lessons = f"Thesis validated: {coin} trade followed predicted trend structure yielding +${pnl_usd:,.2f} profit."

        return TradePostMortem(
            trade_id=trade_id,
            coin=coin,
            realized_pnl_usd=pnl_usd,
            was_profitable=was_profitable,
            ai_score_at_entry=ai_score,
            lessons_learned=lessons,
            suggested_parameter_tweaks=tweaks,
        )
