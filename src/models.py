"""
Domain models for the Hyperliquid AI Copy-Trading system.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class TradeDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TradeActionType(str, Enum):
    OPEN = "OPEN"
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    CLOSE = "CLOSE"


class RecommendationEnum(str, Enum):
    APPROVE = "APPROVE"
    SCALE_DOWN = "SCALE_DOWN"
    REJECT = "REJECT"


class IntentClassification(str, Enum):
    BREAKOUT_MOMENTUM = "BREAKOUT_MOMENTUM"
    SWING_ACCUMULATION = "SWING_ACCUMULATION"
    DELTA_NEUTRAL_HEDGE = "DELTA_NEUTRAL_HEDGE"
    SCALP = "SCALP"
    REVENGE_FOMO = "REVENGE_FOMO"
    UNKNOWN = "UNKNOWN"


class TradeSignal(BaseModel):
    id: str = Field(description="Unique signal ID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    master_address: str = Field(description="Ethereum address of master trader or vault")
    coin: str = Field(description="Hyperliquid perp asset, e.g. BTC, ETH, SOL")
    direction: TradeDirection
    action: TradeActionType
    price: float = Field(description="Execution or trigger price")
    size: float = Field(description="Size in coin units")
    usd_value: float = Field(description="Notional USD value")
    leverage: int = Field(default=1, description="Leverage used by master trader")
    is_cross: bool = True
    master_pnl_usd: Optional[float] = None
    master_winrate_pct: Optional[float] = None


class GraphAnalysis(BaseModel):
    trend_1h: Literal["BULLISH", "BEARISH", "SIDEWAYS"]
    trend_4h: Literal["BULLISH", "BEARISH", "SIDEWAYS"]
    rsi_14: float
    nearest_support: float
    nearest_resistance: float
    liquidity_score: int = Field(description="0 to 100 liquidity score from orderbook", ge=0, le=100)
    summary: str


class RiskAnalysis(BaseModel):
    recommended_leverage: int
    recommended_usd_size: float
    suggested_stop_loss_price: float
    stop_loss_pct: float
    liquidation_buffer_pct: float
    risk_score: int = Field(description="0 to 100 risk score (higher is safer)", ge=0, le=100)
    risk_flags: List[str] = Field(default_factory=list)


class SentimentAnalysis(BaseModel):
    sentiment_score: int = Field(description="-100 to +100 market sentiment", ge=-100, le=100)
    market_phase: Literal["EXTREME_FEAR", "FEAR", "NEUTRAL", "GREED", "EXTREME_GREED"]
    funding_rate_bias: Literal["HEAVY_LONGS", "NEUTRAL", "HEAVY_SHORTS"]
    key_drivers: List[str] = Field(default_factory=list)


class TraderIntentAnalysis(BaseModel):
    intent: IntentClassification
    confidence_score: int = Field(ge=0, le=100)
    reasoning: str
    is_revenge_risk: bool = False


class ConsensusDecision(BaseModel):
    signal_id: str
    overall_score: int = Field(description="0 to 100 composite confidence score", ge=0, le=100)
    recommendation: RecommendationEnum
    recommended_usd_size: float
    recommended_leverage: int
    stop_loss_price: float
    graph: GraphAnalysis
    risk: RiskAnalysis
    sentiment: SentimentAnalysis
    intent: TraderIntentAnalysis
    one_line_summary: str
    formatted_card_markdown: str


class OrderExecutionResult(BaseModel):
    success: bool
    signal_id: str
    coin: str
    direction: TradeDirection
    executed_size: float
    executed_price: float
    executed_usd_value: float
    leverage: int
    stop_loss_price: Optional[float] = None
    tx_hash: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
