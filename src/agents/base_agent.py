"""
Base agent interface for the multi-agent review pipeline.
Supports both LLM-driven inference and deterministic fallback for offline/backtesting.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from src.models import TradeSignal


class BaseReviewAgent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def analyze(self, signal: TradeSignal, market_data: Dict[str, Any]) -> Any:
        """
        Executes analysis on the incoming signal with provided market data.
        Returns a strongly-typed Pydantic analysis model.
        """
        pass
