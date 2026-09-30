"""
Main Application Entry Point.
Orchestrates the Hyperliquid Ingestion, Multi-Agent Review Pipeline,
Telegram Human-in-the-Loop Bot, and Hyperliquid Execution Trader.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 console output on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console

from src.agents.consensus_engine import ConsensusEngine
from src.agents.runtime_guards import ai_veto
from src.config import settings
from src.execution.hyperliquid_trader import HyperliquidTrader
from src.execution.position_monitor import PositionMonitorDaemon
from src.execution.risk_gate import risk_gate
from src.hitl.approval_queue import ApprovalQueue
from src.hitl.telegram_bot import TelegramHITLManager
from src.ingestion.hyperliquid_ws import HyperliquidWebSocketListener
from src.models import TradeActionType, TradeDirection, TradeSignal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("HyperliquidApp")
console = Console()


class HyperliquidAICopySystem:
    def __init__(self):
        self.consensus_engine = ConsensusEngine()
        self.approval_queue = ApprovalQueue()
        self.trader = HyperliquidTrader()
        self.position_monitor = PositionMonitorDaemon()

        self.hitl_manager = TelegramHITLManager(
            approval_queue=self.approval_queue,
            execution_handler=self.execute_trade,
        )

        self.ws_listener = HyperliquidWebSocketListener(
            on_signal_callback=self.on_trade_signal_received
        )

    async def execute_trade(self, signal: TradeSignal, usd_size: float, leverage: int, stop_loss_price: float):
        """
        Callback triggered when trade is approved via HITL Telegram or CLI.
        Enforces:
        1. Bounded AI Veto (Invariants F1-F3)
        2. Single RiskGate Chokepoint (Invariants A1, A2, A3, A6, B1, C3)
        3. Exchange Execution
        """
        # 1. Bounded AI Veto Check
        is_vetoed, veto_reason = await ai_veto.evaluate_veto(
            master_address=signal.master_address,
            coin=signal.coin,
            direction=signal.direction.value
        )
        if is_vetoed:
            logger.warning(f"Order aborted by AI VETO: {veto_reason}")
            return OrderExecutionResult(
                success=False,
                signal_id=signal.id,
                coin=signal.coin,
                direction=signal.direction,
                executed_size=0.0,
                executed_price=0.0,
                executed_usd_value=0.0,
                leverage=leverage,
                error_message=f"AI VETO: {veto_reason}",
            )

        # 2. Single RiskGate Chokepoint (Invariants A1-A6)
        gate_res = risk_gate.evaluate(
            signal=signal,
            current_market_price=signal.price,
            requested_usd_size=usd_size,
            requested_leverage=leverage,
        )
        if not gate_res.allowed:
            logger.warning(f"Order rejected at RiskGate: {gate_res.rejection_reason}")
            return OrderExecutionResult(
                success=False,
                signal_id=signal.id,
                coin=signal.coin,
                direction=signal.direction,
                executed_size=0.0,
                executed_price=0.0,
                executed_usd_value=0.0,
                leverage=leverage,
                error_message=f"RiskGate: {gate_res.rejection_reason}",
            )

        # 3. Execution on Hyperliquid
        result = await self.trader.execute_copy_order(
            signal=signal,
            usd_size=float(gate_res.approved_notional_usd),
            leverage=gate_res.approved_leverage,
            stop_loss_price=float(gate_res.stop_loss_price),
        )
        if result.success:
            self.position_monitor.add_position(
                coin=signal.coin,
                direction=signal.direction,
                entry_price=result.executed_price,
                size=result.executed_size,
                stop_loss=float(gate_res.stop_loss_price),
            )
        return result

    async def on_trade_signal_received(self, signal: TradeSignal):
        """Pipeline entry point when a master trader fill is captured from Hyperliquid."""
        logger.info(f"Signal received: {signal.direction.value} {signal.coin} from {signal.master_address}")

        # Gather market context (e.g. from Hyperliquid REST or cache)
        market_data = {
            "rsi_14": 56.4,
            "support": signal.price * 0.95,
            "resistance": signal.price * 1.08,
            "liquidity_score": 88,
            "account_equity": 3000.0,
            "funding_rate": 0.00012,
            "sentiment_score": 52,
            "recent_losses_count": 0,
        }

        # Multi-Agent Consensus Review
        decision = await self.consensus_engine.evaluate_signal(signal, market_data)

        # Dispatch to Human-in-the-Loop Bot (Telegram/CLI)
        await self.hitl_manager.dispatch_signal(signal, decision)

    async def run_live(self):
        """Runs the live listener and bot concurrently."""
        console.print("[bold green]Starting Hyperliquid AI Copy-Trading Pipeline...[/bold green]")
        tasks = [
            asyncio.create_task(self.ws_listener.start()),
            asyncio.create_task(self.position_monitor.start()),
        ]
        if self.hitl_manager.dp and self.hitl_manager.bot:
            tasks.append(asyncio.create_task(self.hitl_manager.dp.start_polling(self.hitl_manager.bot)))

        await asyncio.gather(*tasks)

    async def run_demo(self):
        """Simulates an incoming signal from a tracked master whale and runs full pipeline."""
        console.print("\n[bold yellow]═══ RUNNING HYPERLIQUID AI COPY-TRADING DEMO SIMULATION ═══[/bold yellow]\n")

        demo_signal = TradeSignal(
            id="DEMO_SIGNAL_001",
            master_address="0x5244E6886eD6c7b9F59D1D5f7823f990924eA383",
            coin="SOL",
            direction=TradeDirection.LONG,
            action=TradeActionType.OPEN,
            price=152.40,
            size=100.0,
            usd_value=15240.0,
            leverage=10,
        )

        await self.on_trade_signal_received(demo_signal)

        # Simulate Human approving the signal
        console.print("\n[cyan]Simulating User Human-in-the-Loop decision: [bold]APPROVE FULL[/bold]...[/cyan]")
        item = await self.approval_queue.get(demo_signal.id)
        if item:
            exec_res = await self.execute_trade(
                demo_signal,
                usd_size=item.decision.recommended_usd_size,
                leverage=item.decision.recommended_leverage,
                stop_loss_price=item.decision.stop_loss_price,
            )
            console.print(f"[bold green]Execution Complete:[/bold green] {exec_res.model_dump_json(indent=2)}")


def main():
    parser = argparse.ArgumentParser(description="Hyperliquid AI Copy-Trading & SDLC System")
    parser.add_argument("--demo", action="store_true", help="Run a demo trade signal through the multi-agent pipeline")
    args = parser.parse_args()

    app = HyperliquidAICopySystem()

    if args.demo:
        asyncio.run(app.run_demo())
    else:
        try:
            asyncio.run(app.run_live())
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutdown requested. Exiting cleanly.[/yellow]")
            sys.exit(0)


if __name__ == "__main__":
    main()
