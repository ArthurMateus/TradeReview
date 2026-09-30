"""
Hyperliquid REST API client.
Provides endpoints for asset context, candles, funding rates, and user state.
"""

from typing import Any, Dict, List, Optional
import aiohttp
from src.config import settings


class HyperliquidRestClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.hl_rest_url

    async def _post(self, payload: Dict[str, Any]) -> Any:
        url = f"{self.base_url}/info"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers={"Content-Type": "application/json"}) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    raise RuntimeError(f"Hyperliquid API Error {resp.status}: {text}")

    async def get_meta_and_asset_ctxs(self) -> List[Any]:
        """Returns meta information and active asset contexts (prices, funding, open interest)."""
        return await self._post({"type": "metaAndAssetCtxs"})

    async def get_clearinghouse_state(self, user_address: str) -> Dict[str, Any]:
        """Returns account equity, margins, and active open positions for a user."""
        return await self._post({"type": "clearinghouseState", "user": user_address})

    async def get_user_fills(self, user_address: str) -> List[Dict[str, Any]]:
        """Returns recent fills/trades executed by a specific user address."""
        return await self._post({"type": "userFills", "user": user_address})

    async def get_candle_snapshot(self, coin: str, interval: str = "1h", start_time: int = 0) -> List[Dict[str, Any]]:
        """Returns OHLCV candle snapshots for a given coin on Hyperliquid."""
        return await self._post({
            "type": "candleSnapshot",
            "req": {
                "coin": coin,
                "interval": interval,
                "startTime": start_time
            }
        })
