"""
Runtime Guards: Cold Path Context Precomputation & Bounded Hot Path AI Veto.
Implements the Golden Rule from docs/RUNTIME-AGENTS.md and Invariants F1-F3:
- Keep LLMs off the hot path.
- LLMs run in the cold path to populate context cache.
- Hot path has a hard timeout and can ONLY veto (never bypass or raise size).
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, Literal, Optional, Tuple
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class RegimeContext(BaseModel):
    regime: Literal["calm", "normal", "stressed"]
    volatility_score: float
    funding_bias: str
    updated_at: datetime


class LeaderScore(BaseModel):
    address: str
    score: int  # 0 to 100
    is_eligible: bool
    verified_trades_count: int
    max_drawdown_pct: float


class RuntimeContextCache:
    """
    Cold-path cache read in microseconds by the hot execution path.
    Updated asynchronously by background workers (Macro Guard, Regime Detector, Leader Vetting).
    """
    def __init__(self):
        self.current_regime = RegimeContext(
            regime="normal",
            volatility_score=1.0,
            funding_bias="NEUTRAL",
            updated_at=datetime.now(timezone.utc)
        )
        self.blackout_active: bool = False
        self.leader_scores: Dict[str, LeaderScore] = {}

    def update_regime(self, regime: Literal["calm", "normal", "stressed"], vol_score: float):
        self.current_regime = RegimeContext(
            regime=regime,
            volatility_score=vol_score,
            funding_bias=self.current_regime.funding_bias,
            updated_at=datetime.now(timezone.utc)
        )
        logger.info(f"[COLD PATH] Market regime updated to: {regime}")

    def register_leader(self, address: str, score: int, is_eligible: bool, trades_count: int, max_dd: float):
        self.leader_scores[address.lower()] = LeaderScore(
            address=address.lower(),
            score=score,
            is_eligible=is_eligible,
            verified_trades_count=trades_count,
            max_drawdown_pct=max_dd,
        )

    def is_leader_eligible(self, address: str) -> bool:
        leader = self.leader_scores.get(address.lower())
        if not leader:
            # Default eligible if not evaluated, or require explicit vetting
            return True
        return leader.is_eligible


# Global cold-path context cache
context_cache = RuntimeContextCache()


class BoundedAIVeto:
    """
    Bounded Hot-Path AI Veto (Invariants F1, F2).
    Runs with a strict timeout (e.g. 500ms).
    Can ONLY veto or annotate. CANNOT raise size or bypass limits.
    """
    def __init__(self, timeout_ms: int = 500):
        self.timeout_ms = timeout_ms

    async def evaluate_veto(self, master_address: str, coin: str, direction: str) -> Tuple[bool, str]:
        """
        Returns (is_vetoed: bool, reason: str).
        """
        try:
            return await asyncio.wait_for(
                self._check_cached_rules(master_address, coin, direction),
                timeout=self.timeout_ms / 1000.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"[HOT PATH AI VETO] Timeout after {self.timeout_ms}ms. Fallback: NO VETO (deterministic).")
            return False, "Veto timed out; deferred to deterministic RiskGate"
        except Exception as e:
            logger.error(f"[HOT PATH AI VETO] Error in veto check: {e}. Fallback: NO VETO.")
            return False, f"Veto error: {e}"

    async def _check_cached_rules(self, master_address: str, coin: str, direction: str) -> Tuple[bool, str]:
        # Microsecond read from cold path context cache
        if context_cache.blackout_active:
            return True, "Veto: Macro blackout window active (high-impact economic release)"

        if context_cache.current_regime.regime == "stressed":
            return True, "Veto: Extreme market stress regime active"

        if not context_cache.is_leader_eligible(master_address):
            return True, f"Veto: Master address {master_address} is ineligible under leader vetting criteria"

        return False, "Pass: All cold-path guards clear"


ai_veto = BoundedAIVeto()
