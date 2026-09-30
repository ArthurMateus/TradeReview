# Multi-Agent Trading System & SDLC Guidelines

## Project Overview
- **Project**: Hyperliquid AI Copy-Trading & Dual SDLC System
- **Venue**: Hyperliquid Perpetual Futures (L1 DEX)
- **Stack**: Python 3.13, AsyncIO, WebSockets, Hyperliquid API/L1, Pydantic v2, aiogram 3, Decimal math
- **Default Mode**: `paper` / `testnet`

---

## 🛑 Strict Money-Safety Trading Invariants (Non-Negotiable)
Every code change, agent review, and trade execution must satisfy the invariants in `docs/trading-invariants.md`:
1. **A1 (Single Chokepoint)**: Every order must pass through `RiskGate`. No code path reaches exchange execution directly.
2. **A2 (Fail Closed)**: Stale data, missing config, unhandled exceptions, or failed checks strictly abort order placement.
3. **A3 (Hard Limits as Config)**: Leverage, notional caps, max positions, and daily loss are configurable and never hardcoded in logic.
4. **A4 (Kill Switch)**: A persistent kill switch halts trading immediately via CLI and Telegram `/kill`.
5. **A5 (Idempotency)**: Orders carry deterministic client IDs derived from signals to prevent double-execution.
6. **A6 (Decimal Money)**: Prices, quantities, notional, and fees use `decimal.Decimal` (never raw floats) to avoid rounding bugs.
7. **B1 (Staleness Guard)**: Reject any signal older than its configured TTL (default 45s).
8. **C3 (Slippage Guard)**: Discard copy trades if the market price has moved beyond tolerance from the master's fill price.
9. **F1-F3 (LLMs Off Hot Path)**: LLM analysis runs either out-of-band in cold-path caches, or inline with hard timeouts and fallback to deterministic veto only.

---

## 🏛️ Multi-Agent SDLC Architecture
Development adheres to the gated pipeline defined in `docs/protocol.md`:
`/brainstorm` $\to$ `/discovery` $\to$ `/research` $\to$ `/pm` $\to$ `/tests` $\to$ `/build` $\to$ `/review` $\to$ `/qa` $\to$ `/verify` $\to$ `/ship` $\to$ `/go-live`

### Specialized Reviewer Panel
All code reviews must evaluate:
- 🛡️ **reviewer-risk**: Sizing, leverage, liquidation buffer, margin ratio, fail-closed behavior.
- 🔒 **reviewer-security**: No leaked private keys, authenticated Telegram commands, non-root execution.
- ⚡ **reviewer-latency**: Hot path execution timing, non-blocking I/O, WebSocket heartbeat health.
- 🏛️ **reviewer-exchange**: Hyperliquid tick/step size rules, funding calculations, EIP-712 signing validity.
- ⚖️ **reviewer-compliance**: Invariant compliance (A1-F3) and regulatory guardrails.
