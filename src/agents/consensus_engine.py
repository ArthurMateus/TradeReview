"""
Consensus Engine.
Executes Graph, Risk, Sentiment, and Trader Intent agents concurrently in parallel.
Computes composite AI score (0-100), outputs recommendation (APPROVE/SCALE_DOWN/REJECT),
and generates the rich formatted card for Human-in-the-Loop review.
"""

import asyncio
from typing import Any, Dict
from src.agents.graph_agent import GraphAgent
from src.agents.risk_guard_agent import RiskGuardAgent
from src.agents.sentiment_agent import SentimentAgent
from src.agents.trader_intent_agent import TraderIntentAgent
from src.models import (
    ConsensusDecision,
    GraphAnalysis,
    IntentClassification,
    RecommendationEnum,
    RiskAnalysis,
    SentimentAnalysis,
    TraderIntentAnalysis,
    TradeSignal,
)


class ConsensusEngine:
    def __init__(self):
        self.graph_agent = GraphAgent()
        self.risk_agent = RiskGuardAgent()
        self.sentiment_agent = SentimentAgent()
        self.intent_agent = TraderIntentAgent()

    async def evaluate_signal(self, signal: TradeSignal, market_data: Dict[str, Any]) -> ConsensusDecision:
        """
        Runs all 4 specialized review agents in parallel and synthesizes the decision.
        """
        graph_task = self.graph_agent.analyze(signal, market_data)
        risk_task = self.risk_agent.analyze(signal, market_data)
        sentiment_task = self.sentiment_agent.analyze(signal, market_data)
        intent_task = self.intent_agent.analyze(signal, market_data)

        # Run concurrently
        graph_res, risk_res, sent_res, intent_res = await asyncio.gather(
            graph_task, risk_task, sentiment_task, intent_task
        )
        graph: GraphAnalysis = graph_res
        risk: RiskAnalysis = risk_res
        sentiment: SentimentAnalysis = sent_res
        intent: TraderIntentAnalysis = intent_res

        # Calculate composite score (0 - 100)
        # Weights: Risk (35%), Graph (30%), Intent (20%), Sentiment (15%)
        sentiment_normalized = max(0, min(100, int((sentiment.sentiment_score + 100) / 2)))
        graph_score = 85 if graph.trend_1h != "SIDEWAYS" else 60
        intent_score = 20 if intent.is_revenge_risk else intent.confidence_score

        composite_score = int(
            (risk.risk_score * 0.35)
            + (graph_score * 0.30)
            + (intent_score * 0.20)
            + (sentiment_normalized * 0.15)
        )
        composite_score = max(0, min(100, composite_score))

        # Determine Recommendation
        if intent.is_revenge_risk or risk.risk_score < 40 or composite_score < 50:
            recommendation = RecommendationEnum.REJECT
            summary = "REJECT: High risk detected (suspected revenge trade or adverse market conditions)."
        elif composite_score >= 75:
            recommendation = RecommendationEnum.APPROVE
            summary = f"STRONG APPROVE: Favorable setup across technicals, risk parameters, and trader conviction."
        else:
            recommendation = RecommendationEnum.SCALE_DOWN
            summary = f"CAUTIOUS APPROVE: Moderate setup. Recommended 50% sizing or tight stop-loss."

        # Format Telegram/Discord Markdown Card
        direction_emoji = "🟢 LONG" if signal.direction.value == "LONG" else "🔴 SHORT"
        short_addr = f"{signal.master_address[:6]}...{signal.master_address[-4:]}"
        
        card_md = (
            f"🚨 *NEW HYPERLIQUID COPY SIGNAL*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Master Trader:* `{short_addr}`\n"
            f"📈 *Asset:* #{signal.coin}-PERP | {direction_emoji}\n"
            f"⚡ *Action:* {signal.action.value} @ *${signal.price:,.2f}* (Master: {signal.leverage}x)\n"
            f"\n"
            f"🤖 *AI SYNTHESIS SCORE: {composite_score}/100*\n"
            f"*{recommendation.value}* — _{summary}_\n"
            f"────────────────────────────\n"
            f"📊 *Graph:* {graph.summary}\n"
            f"🛡️ *Risk:* Size: `${risk.recommended_usd_size:,.2f}` | Max Lev: `{risk.recommended_leverage}x` | Hard SL: `${risk.suggested_stop_loss_price:,.2f}`\n"
            f"📰 *Sentiment:* {sentiment.market_phase} ({sentiment.funding_rate_bias})\n"
            f"🧠 *Trader Intent:* {intent.intent.value} — _{intent.reasoning}_\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

        return ConsensusDecision(
            signal_id=signal.id,
            overall_score=composite_score,
            recommendation=recommendation,
            recommended_usd_size=risk.recommended_usd_size,
            recommended_leverage=risk.recommended_leverage,
            stop_loss_price=risk.suggested_stop_loss_price,
            graph=graph,
            risk=risk,
            sentiment=sentiment,
            intent=intent,
            one_line_summary=summary,
            formatted_card_markdown=card_md,
        )
