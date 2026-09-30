"""
Unit tests validating Money-Safety Trading Invariants (A1-F3).
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from src.agents.runtime_guards import BoundedAIVeto, context_cache
from src.config import settings
from src.execution.kill_switch import KillSwitch
from src.execution.risk_gate import RiskGate
from src.models import TradeActionType, TradeDirection, TradeSignal


@pytest.fixture
def clean_kill_switch(tmp_path):
    state_file = tmp_path / "test_kill_switch.json"
    ks = KillSwitch(state_file=state_file)
    return ks


@pytest.fixture
def valid_signal():
    return TradeSignal(
        id="INV_SIG_01",
        timestamp=datetime.now(timezone.utc),
        master_address="0x1234567890abcdef1234567890abcdef12345678",
        coin="ETH",
        direction=TradeDirection.LONG,
        action=TradeActionType.OPEN,
        price=3500.0,
        size=1.0,
        usd_value=3500.0,
        leverage=5,
    )


def test_invariant_a4_kill_switch_lifecycle(clean_kill_switch):
    """Invariant A4: Kill switch halts new orders, persists across instances, and clears cleanly."""
    assert clean_kill_switch.is_active() is False

    # Activate
    clean_kill_switch.activate(reason="Test emergency stop")
    assert clean_kill_switch.is_active() is True

    # Check persistence in a new instance pointing to same file
    ks_reloaded = KillSwitch(state_file=clean_kill_switch.state_file)
    assert ks_reloaded.is_active() is True

    # Deactivate
    clean_kill_switch.deactivate()
    assert clean_kill_switch.is_active() is False
    assert ks_reloaded.is_active() is False


def test_invariant_a1_a2_risk_gate_blocks_when_kill_switch_active(valid_signal, monkeypatch):
    """Invariant A1 & A2: RiskGate is single chokepoint and fails closed when kill switch active."""
    gate = RiskGate()
    
    # Mock kill_switch active
    from src.execution.risk_gate import kill_switch
    monkeypatch.setattr(kill_switch, "is_active", lambda: True)

    res = gate.evaluate(valid_signal, current_market_price=3500.0, requested_usd_size=250.0, requested_leverage=5)
    assert res.allowed is False
    assert "Kill switch is active" in res.rejection_reason


def test_invariant_b1_staleness_guard(valid_signal):
    """Invariant B1: Signals older than TTL are rejected."""
    gate = RiskGate()
    # Age signal by 60 seconds (TTL is 45s)
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=60)
    stale_signal = valid_signal.model_copy(update={"timestamp": stale_time})

    res = gate.evaluate(stale_signal, current_market_price=3500.0, requested_usd_size=250.0, requested_leverage=5)
    assert res.allowed is False
    assert "stale" in res.rejection_reason.lower()


def test_invariant_c3_slippage_guard(valid_signal):
    """Invariant C3: Breaches beyond MAX_SLIPPAGE_PCT are rejected."""
    gate = RiskGate()
    # Master filled at 3500.0, current price jumped to 3530.0 (~0.85% slippage > 0.4% default)
    res = gate.evaluate(valid_signal, current_market_price=3530.0, requested_usd_size=250.0, requested_leverage=5)
    assert res.allowed is False
    assert "Slippage breached" in res.rejection_reason


def test_invariant_a6_decimal_precision(valid_signal):
    """Invariant A6: All money math in RiskGate uses Decimal without float loss."""
    gate = RiskGate()
    res = gate.evaluate(valid_signal, current_market_price=3500.0, requested_usd_size=250.0, requested_leverage=5)
    assert res.allowed is True
    assert isinstance(res.approved_notional_usd, Decimal)
    assert isinstance(res.approved_quantity, Decimal)
    assert isinstance(res.stop_loss_price, Decimal)


@pytest.mark.asyncio
async def test_invariant_f1_f2_ai_veto_bounded():
    """Invariant F1 & F2: AI Veto runs with hard timeout and can only veto."""
    veto_guard = BoundedAIVeto(timeout_ms=100)

    # When market regime is calm and leader eligible
    context_cache.blackout_active = False
    context_cache.update_regime("calm", 0.5)
    is_vetoed, reason = await veto_guard.evaluate_veto("0xabc", "ETH", "LONG")
    assert is_vetoed is False

    # When macro blackout is triggered in cold path cache
    context_cache.blackout_active = True
    is_vetoed, reason = await veto_guard.evaluate_veto("0xabc", "ETH", "LONG")
    assert is_vetoed is True
    assert "blackout" in reason.lower()
