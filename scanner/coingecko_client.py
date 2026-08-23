"""CoinGecko API client for fetching cryptocurrency market data."""

import logging
from typing import Any, Dict, List, Optional
import requests

import config

logger = logging.getLogger(__name__)


class CoinGeckoClient:
    """Client for CoinGecko free public API."""

    def __init__(self, base_url: str = config.COINGECKO_BASE_URL, timeout: int = config.REQUEST_TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "pump-short-scanner/1.0",
        })

    def fetch_markets_data(self, coin_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch market metrics (price, ATH, ATL, 30d change, market cap, FDV)
        for a given list of CoinGecko coin IDs.
        """
        if not coin_ids:
            return []

        url = f"{self.base_url}/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": ",".join(coin_ids),
            "price_change_percentage": "30d",
        }

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            raw_coins = response.json()
        except requests.exceptions.HTTPError as err:
            logger.error("HTTP error while fetching CoinGecko data: %s", err)
            raise
        except requests.exceptions.RequestException as err:
            logger.error("Network error while connecting to CoinGecko: %s", err)
            raise

        normalized_coins = []
        for item in raw_coins:
            normalized_coins.append(self._normalize_coin_data(item))

        return normalized_coins

    def _normalize_coin_data(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw CoinGecko market item into a clean dictionary."""
        current_price = float(item.get("current_price") or 0.0)
        market_cap = float(item.get("market_cap") or 0.0)
        fdv = item.get("fully_diluted_valuation")
        fdv = float(fdv) if fdv is not None else market_cap

        ath = float(item.get("ath") or 0.0)
        atl = float(item.get("atl") or 0.0)
        pct_30d = item.get("price_change_percentage_30d_in_currency")
        pct_30d = float(pct_30d) if pct_30d is not None else 0.0

        # Multiples calculation
        # 30-day multiple: e.g. +400% change -> (1 + 400/100) = 5.0x
        if pct_30d > 0:
            thirty_day_multiple = round(1.0 + (pct_30d / 100.0), 2)
        else:
            thirty_day_multiple = round(1.0 / (1.0 + abs(pct_30d) / 100.0), 2) if pct_30d > -100 else 0.0

        # ATH multiple: multiple from all-time low to current price
        # (or ATH to ATL if measuring full cycle expansion)
        ath_multiple = round(current_price / atl, 2) if atl > 0 else 0.0

        return {
            "id": item.get("id", ""),
            "symbol": (item.get("symbol") or "").upper(),
            "name": item.get("name", ""),
            "current_price": current_price,
            "market_cap": market_cap,
            "fdv": fdv,
            "ath": ath,
            "atl": atl,
            "price_change_30d_pct": pct_30d,
            "ath_multiple": ath_multiple,
            "thirty_day_multiple": thirty_day_multiple,
        }
