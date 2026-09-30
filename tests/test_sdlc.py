"""
Unit tests for AI SDLC Backtester and Strategy Evaluator.
"""

from src.sdlc.backtester import HyperliquidBacktester
from src.sdlc.strategy_evaluator import StrategyEvaluator


def test_backtester_filters_low_score_trades():
    backtester = HyperliquidBacktester(min_ai_score_filter=70)
    
    historical_signals = [
        {"ai_score": 85, "outcome_pnl_usd": 150.0},
        {"ai_score": 40, "outcome_pnl_usd": -200.0},  # Should be filtered out
        {"ai_score": 75, "outcome_pnl_usd": 80.0},
        {"ai_score": 30, "outcome_pnl_usd": -300.0},  # Should be filtered out
    ]

    metrics = backtester.run_backtest(historical_signals)

    assert metrics.total_signals == 4
    assert metrics.executed_trades == 2
    assert metrics.filtered_out_trades == 2
    assert metrics.win_rate_pct == 100.0
    assert metrics.total_pnl_usd == 230.0


def test_strategy_evaluator_diagnoses_losing_trade():
    evaluator = StrategyEvaluator()
    post_mortem = evaluator.evaluate_closed_trade(
        trade_id="TR_100",
        coin="ETH",
        entry_price=3500.0,
        exit_price=3380.0,
        pnl_usd=-120.0,
        ai_score=85,
        entry_notes="High AI score false positive",
    )

    assert post_mortem.was_profitable is False
    assert len(post_mortem.suggested_parameter_tweaks) > 0
