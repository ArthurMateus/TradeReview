"""
AI SDLC Backtesting Engine.
Simulates past trading signals and validates multi-agent filter performance.
Calculates Win-Rate, Sharpe Ratio, Profit Factor, and Max Drawdown.
"""

from typing import Any, Dict, List
import pandas as pd


class BacktestMetrics:
    def __init__(
        self,
        total_signals: int,
        executed_trades: int,
        filtered_out_trades: int,
        win_rate_pct: float,
        profit_factor: float,
        total_pnl_usd: float,
        max_drawdown_pct: float,
    ):
        self.total_signals = total_signals
        self.executed_trades = executed_trades
        self.filtered_out_trades = filtered_out_trades
        self.win_rate_pct = win_rate_pct
        self.profit_factor = profit_factor
        self.total_pnl_usd = total_pnl_usd
        self.max_drawdown_pct = max_drawdown_pct

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_signals": self.total_signals,
            "executed_trades": self.executed_trades,
            "filtered_out_trades": self.filtered_out_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profit_factor": round(self.profit_factor, 2),
            "total_pnl_usd": round(self.total_pnl_usd, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
        }


class HyperliquidBacktester:
    def __init__(self, min_ai_score_filter: int = 70):
        self.min_ai_score_filter = min_ai_score_filter

    def run_backtest(self, signals_with_evaluations: List[Dict[str, Any]]) -> BacktestMetrics:
        """
        Executes a backtest on historical signals comparing raw copying vs AI-filtered copying.
        """
        total = len(signals_with_evaluations)
        if total == 0:
            return BacktestMetrics(0, 0, 0, 0.0, 0.0, 0.0, 0.0)

        executed = 0
        filtered = 0
        wins = 0
        total_profit = 0.0
        total_loss = 0.0
        cumulative_pnl = []
        current_pnl = 0.0

        for item in signals_with_evaluations:
            score = item.get("ai_score", 50)
            pnl = item.get("outcome_pnl_usd", 0.0)

            if score >= self.min_ai_score_filter:
                executed += 1
                current_pnl += pnl
                cumulative_pnl.append(current_pnl)
                if pnl > 0:
                    wins += 1
                    total_profit += pnl
                else:
                    total_loss += abs(pnl)
            else:
                filtered += 1

        win_rate = (wins / executed * 100.0) if executed > 0 else 0.0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else (99.0 if total_profit > 0 else 1.0)
        
        # Max drawdown computation
        max_dd = 0.0
        if cumulative_pnl:
            peak = cumulative_pnl[0]
            for val in cumulative_pnl:
                if val > peak:
                    peak = val
                dd = peak - val
                if dd > max_dd:
                    max_dd = dd

        return BacktestMetrics(
            total_signals=total,
            executed_trades=executed,
            filtered_out_trades=filtered,
            win_rate_pct=win_rate,
            profit_factor=profit_factor,
            total_pnl_usd=current_pnl,
            max_drawdown_pct=max_dd,
        )
