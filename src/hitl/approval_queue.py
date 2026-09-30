"""
Signal Approval Queue with TTL (Time-To-Live).
Guarantees that trades aren't executed after high latency/slippage.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional
from src.config import settings
from src.models import ConsensusDecision, TradeSignal


class PendingSignalItem:
    def __init__(self, signal: TradeSignal, decision: ConsensusDecision, ttl_seconds: int):
        self.signal = signal
        self.decision = decision
        self.created_at = datetime.now(timezone.utc)
        self.expires_at = self.created_at.timestamp() + ttl_seconds
        self.status: str = "PENDING"  # PENDING, APPROVED, REJECTED, EXPIRED

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc).timestamp() > self.expires_at


class ApprovalQueue:
    def __init__(self):
        self._pending: Dict[str, PendingSignalItem] = {}
        self._lock = asyncio.Lock()

    async def add(self, signal: TradeSignal, decision: ConsensusDecision) -> PendingSignalItem:
        async with self._lock:
            item = PendingSignalItem(
                signal=signal,
                decision=decision,
                ttl_seconds=settings.signal_timeout_seconds,
            )
            self._pending[signal.id] = item
            return item

    async def get(self, signal_id: str) -> Optional[PendingSignalItem]:
        async with self._lock:
            item = self._pending.get(signal_id)
            if item and item.is_expired and item.status == "PENDING":
                item.status = "EXPIRED"
            return item

    async def resolve(self, signal_id: str, new_status: str) -> Optional[PendingSignalItem]:
        async with self._lock:
            item = self._pending.get(signal_id)
            if item:
                item.status = new_status
            return item
