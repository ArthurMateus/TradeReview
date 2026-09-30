"""
Risk Guard Agent.
Calculates safe position sizing, enforces leverage caps, sets mandatory stop-loss prices,
and computes liquidation distance.
"""

from typing import Any, Dict
from src.agents.base_agent import BaseReviewAgent
from src.config import settings
from src.models import RiskAnalysis, TradeDirection, TradeSignal


class RiskGuardAgent(BaseReviewAgent):
    def __init__(self):
        super().__init__(name="Risk Guard Agent")

    async def analyze(self, signal: TradeSignal, market_data: Dict[str, Any]) -> RiskAnalysis:
        risk_flags = []
        master_leverage = signal.leverage

        # 1. Enforce leverage cap
        if master_leverage > settings.max_leverage:
            recommended_leverage = settings.max_leverage
            risk_flags.append(
                f"Master leverage {master_leverage}x exceeds max cap {settings.max_leverage}x; scaled down."
            )
        else:
            recommended_leverage = max(1, master_leverage)

        # 2. Position sizing calculation
        account_balance = float(market_data.get("account_equity", 2500.0))
        # Default trade size or cap by max_trade_usd_size
        recommended_usd_size = min(settings.default_trade_usd_size, settings.max_trade_usd_size)
        
        # If user account is smaller, scale position down so it doesn't exceed 20% of account
        max_allowed_from_equity = account_balance * 0.20
        if recommended_usd_size > max_allowed_from_equity:
            recommended_usd_size = round(max_allowed_from_equity, 2)
            risk_flags.append(f"Position size scaled to ${recommended_usd_size} (20% of equity limit).")

        # 3. Stop loss calculation
        sl_pct = settings.default_stop_loss_pct
        if signal.direction == TradeDirection.LONG:
            suggested_sl = signal.price * (1.0 - sl_pct / 100.0)
            # Liquidation buffer approx: (1 / leverage) * 100%
            liq_buffer_pct = (1.0 / recommended_leverage) * 100.0 * 0.90
        else:
            suggested_sl = signal.price * (1.0 + sl_pct / 100.0)
            liq_buffer_pct = (1.0 / recommended_leverage) * 100.0 * 0.90

        # 4. Composite Risk Score (1-100, 100 is safest)
        risk_deductions = 0
        if master_leverage >= 10:
            risk_deductions += 20
        elif master_leverage >= 5:
            risk_deductions += 10

        if signal.usd_value > 50000:
            risk_flags.append("High whale notional size on master account.")

        base_risk_score = max(20, min(100, 95 - risk_deductions))

        return RiskAnalysis(
            recommended_leverage=recommended_leverage,
            recommended_usd_size=recommended_usd_size,
            suggested_stop_loss_price=round(suggested_sl, 4),
            stop_loss_pct=sl_pct,
            liquidation_buffer_pct=round(liq_buffer_pct, 1),
            risk_score=base_risk_score,
            risk_flags=risk_flags,
        )
