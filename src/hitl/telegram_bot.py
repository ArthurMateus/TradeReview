"""
Human-in-the-Loop Telegram Bot interface using aiogram 3.
Provides 1-click interactive Inline Buttons:
- [✅ Copy Full ($X)]
- [⚡ Copy Half ($Y)]
- [❌ Reject / Skip]
Gracefully falls back to rich terminal display when TELEGRAM_BOT_TOKEN is not configured.
"""

import asyncio
import logging
import sys
from typing import Any, Callable, Optional
from rich.console import Console
from rich.panel import Panel

from src.config import settings
from src.hitl.approval_queue import ApprovalQueue
from src.models import ConsensusDecision, OrderExecutionResult, TradeSignal

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)
console = Console(legacy_windows=False)

# Optional aiogram imports
try:
    from aiogram import Bot, Dispatcher, F
    from aiogram.enums import ParseMode
    from aiogram.filters import CommandStart
    from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
    HAS_AIOGRAM = True
except ImportError:
    HAS_AIOGRAM = False


class TelegramHITLManager:
    def __init__(
        self,
        approval_queue: ApprovalQueue,
        execution_handler: Optional[Callable[[TradeSignal, float, int, float], OrderExecutionResult]] = None,
    ):
        self.approval_queue = approval_queue
        self.execution_handler = execution_handler
        self.bot: Optional[Any] = None
        self.dp: Optional[Any] = None

        if HAS_AIOGRAM and settings.telegram_bot_token:
            self.bot = Bot(token=settings.telegram_bot_token)
            self.dp = Dispatcher()
            self._register_handlers()
        else:
            logger.info("Telegram Bot token not provided or aiogram absent. Running in CLI Simulation mode.")

    def _register_handlers(self):
        if not self.dp:
            return

        @self.dp.message(CommandStart())
        async def handle_start(message: Message):
            await message.answer(
                "🚀 *Hyperliquid AI Copy-Trading Bot Active*\n"
                "You will receive trade review cards with 1-click execution buttons here.",
                parse_mode=ParseMode.MARKDOWN,
            )

        @self.dp.callback_query(F.data.startswith("copy_full:"))
        async def on_copy_full(query: CallbackQuery):
            signal_id = query.data.split(":")[1]
            await self._process_user_decision(query, signal_id, scale_factor=1.0)

        @self.dp.callback_query(F.data.startswith("copy_half:"))
        async def on_copy_half(query: CallbackQuery):
            signal_id = query.data.split(":")[1]
            await self._process_user_decision(query, signal_id, scale_factor=0.5)

        @self.dp.callback_query(F.data.startswith("reject:"))
        async def on_reject(query: CallbackQuery):
            signal_id = query.data.split(":")[1]
            item = await self.approval_queue.resolve(signal_id, "REJECTED")
            await query.answer("❌ Trade Rejected.")
            if query.message:
                await query.message.edit_text(
                    f"{query.message.text}\n\n🛑 *STATUS: REJECTED BY USER*",
                    parse_mode=ParseMode.MARKDOWN,
                )

    async def _process_user_decision(self, query: CallbackQuery, signal_id: str, scale_factor: float):
        item = await self.approval_queue.get(signal_id)
        if not item:
            await query.answer("⚠️ Signal not found.", show_alert=True)
            return

        if item.is_expired:
            await self.approval_queue.resolve(signal_id, "EXPIRED")
            await query.answer("⏱️ Signal Expired! Market price has moved.", show_alert=True)
            if query.message:
                await query.message.edit_text(f"{query.message.text}\n\n⏱️ *STATUS: EXPIRED*", parse_mode=ParseMode.MARKDOWN)
            return

        # Execute
        await self.approval_queue.resolve(signal_id, "APPROVED")
        target_size = item.decision.recommended_usd_size * scale_factor
        leverage = item.decision.recommended_leverage
        sl_price = item.decision.stop_loss_price

        await query.answer("⚡ Executing order on Hyperliquid...")

        if self.execution_handler:
            result = await self.execution_handler(item.signal, target_size, leverage, sl_price)
            if result.success:
                receipt = (
                    f"\n\n✅ *EXECUTED ON HYPERLIQUID*\n"
                    f"• Size: `${result.executed_usd_value:,.2f}` @ `${result.executed_price:,.2f}`\n"
                    f"• Leverage: `{result.leverage}x`\n"
                    f"• Hard SL: `${result.stop_loss_price:,.2f}`\n"
                    f"• Tx: `{result.tx_hash or '0xMOCK_TX'}`"
                )
            else:
                receipt = f"\n\n❌ *EXECUTION FAILED:* {result.error_message}"
        else:
            receipt = f"\n\n✅ *SIMULATED EXECUTION:* ${target_size:,.2f} order filled."

        if query.message:
            await query.message.edit_text(f"{query.message.text}{receipt}", parse_mode=ParseMode.MARKDOWN)

    async def dispatch_signal(self, signal: TradeSignal, decision: ConsensusDecision):
        """Sends signal card to Telegram or logs to CLI console if in mock mode."""
        item = await self.approval_queue.add(signal, decision)

        # 1. Telegram Dispatch
        if self.bot and settings.telegram_authorized_chat_id:
            full_usd = decision.recommended_usd_size
            half_usd = decision.recommended_usd_size * 0.5
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"✅ Copy Full (${full_usd:,.0f})",
                            callback_data=f"copy_full:{signal.id}",
                        ),
                        InlineKeyboardButton(
                            text=f"⚡ Copy Half (${half_usd:,.0f})",
                            callback_data=f"copy_half:{signal.id}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="❌ Skip / Reject",
                            callback_data=f"reject:{signal.id}",
                        ),
                    ],
                ]
            )
            try:
                await self.bot.send_message(
                    chat_id=settings.telegram_authorized_chat_id,
                    text=decision.formatted_card_markdown,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                )
                logger.info(f"Dispatched signal card {signal.id} to Telegram chat.")
            except Exception as e:
                logger.error(f"Failed to send Telegram message: {e}")

        # 2. Rich Terminal Console Output (always available for local observation)
        console.print(
            Panel(
                decision.formatted_card_markdown,
                title=f"[bold cyan]AI SDLC HITL SIGNAL REVIEW ({signal.coin})[/bold cyan]",
                border_style="green" if decision.overall_score >= 70 else "yellow",
            )
        )
