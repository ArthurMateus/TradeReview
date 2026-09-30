"""
Risk Gate - Single Chokepoint (Invariants A1, A2, A3, A6, B1, C3).
No order can reach the exchange client without passing through this gate.
All calculations use Python's Decimal type to eliminate floating point rounding errors.
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
import logging
from typing import Optional, Tuple
from pydantic import BaseModel, ConfigDict

from src.config import settings
from src.execution.kill_switch import kill_switch
from src.models import TradeDirection, TradeSignal

logger = logging.getLogger(__name__)


class RiskGateResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    allowed: bool
    rejection_reason: Optional[str] = None
    approved_notional_usd: Decimal
    approved_quantity: Decimal
    approved_leverage: int
    stop_loss_price: Decimal
    current_price: Decimal


class RiskGate:
    def __init__(self):
        pass

    def evaluate(
        self,
        signal: TradeSignal,
        current_market_price: float,
        requested_usd_size: float,
        requested_leverage: int,
    ) -> RiskGateResult:
        """
        Single chokepoint evaluating all money safety invariants.
        Fails closed on any inconsistency or exception.
        """
        try:
            # 1. Kill switch check (Invariant A4)
            if kill_switch.is_active():
                return self._reject("Kill switch is active. All trading halted.")

            # 2. Staleness guard (Invariant B1)
            now_ts = datetime.now(timezone.utc).timestamp()
            signal_age_seconds = now_ts - signal.timestamp.timestamp()
            if signal_age_seconds > settings.signal_timeout_seconds:
                return self._reject(
                    f"Signal is stale ({signal_age_seconds:.1f}s old > {settings.signal_timeout_seconds}s limit)."
                )

            # 3. Decimal math conversions (Invariant A6)
            dec_signal_price = Decimal(str(signal.price))
            dec_market_price = Decimal(str(current_market_price))
            dec_requested_usd = Decimal(str(requested_usd_size))
            dec_max_usd = Decimal(str(settings.max_trade_usd_size))

            # 4. Slippage guard (Invariant C3)
            # |market_price - signal_price| / signal_price > max_slippage_pct
            price_delta = abs(dec_market_price - dec_signal_price)
            slippage_pct = (price_delta / dec_signal_price) * Decimal("100")
            dec_max_slippage = Decimal(str(settings.max_slippage_pct))

            if slippage_pct > dec_max_slippage:
                return self._reject(
                    f"Slippage breached: {slippage_pct:.2f}% exceeds tolerance of {dec_max_slippage}%."
                )

            # 5. Hard limit caps (Invariant A3)
            # Leverage cap
            approved_leverage = min(requested_leverage, settings.max_leverage)
            if approved_leverage < 1:
                approved_leverage = 1

            # Sizing cap
            approved_notional = min(dec_requested_usd, dec_max_usd)
            if approved_notional <= Decimal("0"):
                return self._reject("Approved notional is non-positive.")

            # Quantity computation with Decimal precision (Invariant A6)
            approved_qty = (approved_notional / dec_market_price).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)

            # 6. Stop-loss calculation with Decimal
            sl_pct = Decimal(str(settings.default_stop_loss_pct)) / Decimal("100")
            if signal.direction == TradeDirection.LONG:
                stop_loss = (dec_market_price * (Decimal("1") - sl_pct)).quantize(Decimal("0.0001"))
            else:
                stop_loss = (dec_market_price * (Decimal("1") + sl_pct)).quantize(Decimal("0.0001"))

            logger.info(
                f"[RISK GATE PASS] {signal.coin} {signal.direction.value}: Notional=${approved_notional} "
                f"Qty={approved_qty} Lev={approved_leverage}x SL=${stop_loss}"
            )

            return RiskGateResult(
                allowed=True,
                approved_notional_usd=approved_notional,
                approved_quantity=approved_qty,
                approved_leverage=approved_leverage,
                stop_loss_price=stop_loss,
                current_price=dec_market_price,
            )

        except Exception as e:
            # Fail closed (Invariant A2)
            logger.error(f"[RISK GATE CRITICAL] Exception inside gate: {e}. Failing closed.", exc_info=True)
            return self._reject(f"Internal gate error: {e}")

    def _reject(self, reason: str) -> RiskGateResult:
        logger.warning(f"[RISK GATE REJECT] {reason}")
        return RiskGateResult(
            allowed=False,
            rejection_reason=reason,
            approved_notional_usd=Decimal("0"),
            approved_quantity=Decimal("0"),
            approved_leverage=1,
            stop_loss_price=Decimal("0"),
            current_price=Decimal("0"),
        )


risk_gate = RiskGate()
