"""CoinGecko API client for fetching cryptocurrency market data."""

import logging
import time
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
        for a specific list of CoinGecko coin IDs.
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

        return [self._normalize_coin_data(item) for item in raw_coins]

    def fetch_top_market_coins(
        self,
        max_pages: int = 4,
        per_page: int = 250,
        delay_seconds: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """
        Fetch the top N coins by market cap (default 4 pages * 250 = Top 1000)
        using CoinGecko's free public /coins/markets endpoint with 30d price change.
        Includes polite delays and retry logic to avoid rate limits.
        """
        all_coins: List[Dict[str, Any]] = []
        url = f"{self.base_url}/coins/markets"

        for page in range(1, max_pages + 1):
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": per_page,
                "page": page,
                "price_change_percentage": "30d",
            }

            max_retries = 3
            success = False

            for attempt in range(1, max_retries + 1):
                try:
                    response = self.session.get(url, params=params, timeout=self.timeout)
                    if response.status_code == 429:
                        wait_time = 15 * attempt
                        logger.warning("CoinGecko rate limit (429) on page %d. Retrying in %ds...", page, wait_time)
                        time.sleep(wait_time)
                        continue

                    response.raise_for_status()
                    raw_data = response.json()
                    if isinstance(raw_data, list):
                        for item in raw_data:
                            all_coins.append(self._normalize_coin_data(item))
                    success = True
                    break
                except requests.exceptions.RequestException as err:
                    logger.warning("Attempt %d failed for page %d: %s", attempt, page, err)
                    time.sleep(3 * attempt)

            if not success:
                logger.error("Failed to fetch page %d after %d attempts.", page, max_retries)

            # Polite delay between paginated calls for free tier
            if page < max_pages:
                time.sleep(delay_seconds)

        return all_coins

    def _normalize_coin_data(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw CoinGecko market item into a clean dictionary."""
        current_price = float(item.get("current_price") or 0.0)
        market_cap = float(item.get("market_cap") or 0.0)
        fdv = item.get("fully_diluted_valuation")
        fdv = float(fdv) if fdv is not None else market_cap

        ath = float(item.get("ath") or 0.0)
        atl = float(item.get("atl") or 0.0)
        ath_change_pct = float(item.get("ath_change_percentage") or 0.0)
        pct_30d = item.get("price_change_percentage_30d_in_currency")
        pct_30d = float(pct_30d) if pct_30d is not None else 0.0

        # Multiples calculation
        # 30-day multiple: e.g. +400% change -> (1 + 400/100) = 5.0x
        if pct_30d > 0:
            thirty_day_multiple = round(1.0 + (pct_30d / 100.0), 2)
        else:
            thirty_day_multiple = round(1.0 / (1.0 + abs(pct_30d) / 100.0), 2) if pct_30d > -100 else 0.0

        # ATH multiple: multiple from base/ATL ONLY when the coin is currently near its ATH
        # (e.g. within 20% of ATH). If a coin is down 60-95% from an ATH set years ago,
        # its historical all-time gain does NOT constitute an active parabolic pump.
        is_near_ath = ath_change_pct >= -20.0
        if is_near_ath and atl > 0:
            ath_multiple = round(current_price / atl, 2)
        else:
            ath_multiple = 0.0

        return {
            "id": item.get("id", ""),
            "symbol": (item.get("symbol") or "").upper(),
            "name": item.get("name", ""),
            "current_price": current_price,
            "market_cap": market_cap,
            "fdv": fdv,
            "ath": ath,
            "atl": atl,
            "ath_change_pct": ath_change_pct,
            "is_near_ath": is_near_ath,
            "price_change_30d_pct": pct_30d,
            "ath_multiple": ath_multiple,
            "thirty_day_multiple": thirty_day_multiple,
        }
