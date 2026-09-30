"""
Configuration module using Pydantic Settings.
Loads environment variables and sets defaults for Hyperliquid, Telegram, AI agents, and Risk Guard.
"""

from typing import List, Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Hyperliquid
    hyperliquid_network: Literal["mainnet", "testnet"] = "testnet"
    hyperliquid_account_address: str = "0x0000000000000000000000000000000000000000"
    hyperliquid_agent_private_key: str = "0x0000000000000000000000000000000000000000000000000000000000000000"
    tracked_master_addresses: str = ""

    @property
    def master_address_list(self) -> List[str]:
        if not self.tracked_master_addresses:
            return []
        return [addr.strip().lower() for addr in self.tracked_master_addresses.split(",") if addr.strip()]

    @property
    def hl_ws_url(self) -> str:
        if self.hyperliquid_network == "mainnet":
            return "wss://api.hyperliquid.xyz/ws"
        return "wss://api.hyperliquid-testnet.xyz/ws"

    @property
    def hl_rest_url(self) -> str:
        if self.hyperliquid_network == "mainnet":
            return "https://api.hyperliquid.xyz"
        return "https://api.hyperliquid-testnet.xyz"

    # Telegram HITL
    telegram_bot_token: Optional[str] = None
    telegram_authorized_chat_id: Optional[int] = None
    signal_timeout_seconds: int = 45

    # AI Multi-Agent Engine
    ai_provider: Literal["mock", "gemini", "openai", "anthropic"] = "mock"
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    auto_execute_enabled: bool = False
    auto_execute_min_score: int = Field(default=90, ge=0, le=100)

    # Risk Management Rules
    max_leverage: int = Field(default=5, ge=1, le=50)
    max_trade_usd_size: float = Field(default=500.0, gt=0.0)
    default_trade_usd_size: float = Field(default=250.0, gt=0.0)
    default_stop_loss_pct: float = Field(default=3.5, gt=0.0)
    max_slippage_pct: float = Field(default=0.4, gt=0.0)


# Global singleton instance
settings = Settings()
