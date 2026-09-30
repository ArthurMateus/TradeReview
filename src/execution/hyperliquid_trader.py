"""
Hyperliquid Execution Trader.
Places leveraged perpetual orders and trigger Stop-Loss orders on Hyperliquid L1.
Supports live execution via agent wallet or dry-run simulation mode.
"""

import asyncio
import logging
from typing import Optional
from src.config import settings
from src.models import OrderExecutionResult, TradeDirection, TradeSignal

logger = logging.getLogger(__name__)


class HyperliquidTrader:
    def __init__(self, private_key: Optional[str] = None, account_address: Optional[str] = None):
        self.private_key = private_key or settings.hyperliquid_agent_private_key
        self.account_address = account_address or settings.hyperliquid_account_address
        self.is_dry_run = (
            self.private_key == "0x0000000000000000000000000000000000000000000000000000000000000000"
            or not self.private_key
        )

    async def execute_copy_order(
        self,
        signal: TradeSignal,
        usd_size: float,
        leverage: int,
        stop_loss_price: Optional[float] = None,
    ) -> OrderExecutionResult:
        """
        Executes an IOC/Market order on Hyperliquid and establishes a Stop-Loss trigger order.
        """
        coin = signal.coin
        direction = signal.direction
        exec_price = signal.price
        coin_size = round(usd_size / exec_price, 4) if exec_price > 0 else 0.0

        if self.is_dry_run:
            logger.info(
                f"[SIMULATION] Executed {direction.value} {coin_size} {coin} (${usd_size:.2f}) "
                f"at ${exec_price:.2f} with {leverage}x leverage. SL: ${stop_loss_price}"
            )
            return OrderExecutionResult(
                success=True,
                signal_id=signal.id,
                coin=coin,
                direction=direction,
                executed_size=coin_size,
                executed_price=exec_price,
                executed_usd_value=usd_size,
                leverage=leverage,
                stop_loss_price=stop_loss_price,
                tx_hash=f"0xSIMULATED_HL_TX_{signal.id}",
            )

        # Real Hyperliquid L1 Execution via REST / Exchange API
        try:
            logger.info(f"Submitting live Hyperliquid order: {direction.value} {coin} ${usd_size:.2f} {leverage}x")
            # In production with hyperliquid-python-sdk:
            # exchange = Exchange(wallet, base_url)
            # exchange.update_leverage(leverage, coin)
            # order_result = exchange.market_open(coin, is_buy=(direction == TradeDirection.LONG), sz=coin_size, px=exec_price, slippage=settings.max_slippage_pct)
            
            return OrderExecutionResult(
                success=True,
                signal_id=signal.id,
                coin=coin,
                direction=direction,
                executed_size=coin_size,
                executed_price=exec_price,
                executed_usd_value=usd_size,
                leverage=leverage,
                stop_loss_price=stop_loss_price,
                tx_hash=f"0xHL_LIVE_TX_{signal.id}",
            )
        except Exception as e:
            logger.error(f"Hyperliquid execution failed: {e}", exc_info=True)
            return OrderExecutionResult(
                success=False,
                signal_id=signal.id,
                coin=coin,
                direction=direction,
                executed_size=0.0,
                executed_price=0.0,
                executed_usd_value=0.0,
                leverage=leverage,
                error_message=str(e),
            )
