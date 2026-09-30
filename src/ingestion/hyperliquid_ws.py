"""
Hyperliquid WebSocket Listener.
Subscribes to real-time `userFills` events for all tracked master trader addresses.
Emits parsed `TradeSignal` objects to downstream listeners.
"""

import asyncio
import json
import logging
from typing import Callable, List, Optional
import websockets
from src.config import settings
from src.models import TradeActionType, TradeDirection, TradeSignal

logger = logging.getLogger(__name__)


class HyperliquidWebSocketListener:
    def __init__(
        self,
        master_addresses: Optional[List[str]] = None,
        ws_url: Optional[str] = None,
        on_signal_callback: Optional[Callable[[TradeSignal], None]] = None,
    ):
        self.master_addresses = master_addresses or settings.master_address_list
        self.ws_url = ws_url or settings.hl_ws_url
        self.on_signal = on_signal_callback
        self._running = False

    async def start(self):
        """Starts the persistent WebSocket connection with auto-reconnect."""
        self._running = True
        logger.info(f"Connecting to Hyperliquid WebSocket: {self.ws_url}")

        while self._running:
            try:
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("Connected to Hyperliquid WS. Subscribing to master traders...")
                    # Subscribe to each master trader's userFills
                    for addr in self.master_addresses:
                        sub_msg = {
                            "method": "subscribe",
                            "subscription": {"type": "userFills", "user": addr}
                        }
                        await ws.send(json.dumps(sub_msg))
                        logger.info(f"Subscribed to fills for master: {addr}")

                    # Listen for messages
                    async for raw_message in ws:
                        if not self._running:
                            break
                        await self._handle_message(raw_message)

            except (websockets.ConnectionClosedError, websockets.ConnectionClosedOK) as e:
                logger.warning(f"Hyperliquid WS connection closed: {e}. Reconnecting in 3s...")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Unexpected error in Hyperliquid WS loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def stop(self):
        """Stops the WebSocket listener gracefully."""
        self._running = False

    async def _handle_message(self, raw_message: str):
        try:
            data = json.loads(raw_message)
            channel = data.get("channel")

            if channel == "userFills":
                fills_data = data.get("data", {})
                is_snapshot = fills_data.get("isSnapshot", False)
                # Ignore initial connection snapshot to avoid copying old trades
                if is_snapshot:
                    return

                user = fills_data.get("user", "")
                fills = fills_data.get("fills", [])
                for fill in fills:
                    signal = self._parse_fill_to_signal(user, fill)
                    if signal and self.on_signal:
                        if asyncio.iscoroutinefunction(self.on_signal):
                            await self.on_signal(signal)
                        else:
                            self.on_signal(signal)
        except Exception as e:
            logger.error(f"Failed to handle WS message: {e}")

    def _parse_fill_to_signal(self, user: str, fill: dict) -> Optional[TradeSignal]:
        try:
            coin = fill.get("coin", "UNKNOWN")
            side = fill.get("side", "B")  # 'B' for Buy, 'A' for Sell/Ask
            price = float(fill.get("px", 0.0))
            sz = float(fill.get("sz", 0.0))
            usd_value = price * sz
            trade_id = str(fill.get("tid", "")) or f"{coin}_{fill.get('time', '')}"

            direction = TradeDirection.LONG if side == "B" else TradeDirection.SHORT

            return TradeSignal(
                id=trade_id,
                master_address=user,
                coin=coin,
                direction=direction,
                action=TradeActionType.OPEN,
                price=price,
                size=sz,
                usd_value=usd_value,
                leverage=5,  # Default or dynamically fetched from clearinghouse
            )
        except Exception as e:
            logger.error(f"Error parsing fill into TradeSignal: {e}")
            return None
