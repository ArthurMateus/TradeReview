"""
Active Position Monitor.
Tracks unrealized PnL, adjusts trailing stop loss, and coordinates copy-exits
when the master trader closes or trims a position.
"""

import asyncio
import logging
from typing import Dict
from src.models import TradeDirection

logger = logging.getLogger(__name__)


class PositionTracker:
    def __init__(self, coin: str, direction: TradeDirection, entry_price: float, size: float, stop_loss: float):
        self.coin = coin
        self.direction = direction
        self.entry_price = entry_price
        self.size = size
        self.stop_loss = stop_loss
        self.highest_price = entry_price
        self.lowest_price = entry_price

    def update_price(self, current_price: float) -> float:
        if self.direction == TradeDirection.LONG:
            if current_price > self.highest_price:
                self.highest_price = current_price
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100.0
        else:
            if current_price < self.lowest_price:
                self.lowest_price = current_price
            pnl_pct = ((self.entry_price - current_price) / self.entry_price) * 100.0
        return pnl_pct


class PositionMonitorDaemon:
    def __init__(self):
        self.active_positions: Dict[str, PositionTracker] = {}
        self._running = False

    def add_position(self, coin: str, direction: TradeDirection, entry_price: float, size: float, stop_loss: float):
        self.active_positions[coin] = PositionTracker(
            coin=coin,
            direction=direction,
            entry_price=entry_price,
            size=size,
            stop_loss=stop_loss,
        )
        logger.info(f"Monitoring active position for {coin}: {direction.value} @ ${entry_price:.2f}")

    def remove_position(self, coin: str):
        if coin in self.active_positions:
            del self.active_positions[coin]
            logger.info(f"Closed and removed {coin} from position monitor.")

    async def start(self):
        self._running = True
        while self._running:
            # Periodically poll or evaluate trailing stops
            await asyncio.sleep(5)

    def stop(self):
        self._running = False
