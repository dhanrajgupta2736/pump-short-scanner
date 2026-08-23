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
        Fetch market metrics (price, ATH, ATL, 30d change, market cap, FDV, volume)
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
        delay_seconds: float = 2.5,
    ) -> List[Dict[str, Any]]:
        """
        Fetch the top N coins by market cap (default 4 pages * 250 = Top 1000)
        using CoinGecko's free public /coins/markets endpoint with 30d price change.
        Includes polite delays and exponential backoff retry logic for 429 rate limits.
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
                        wait_time = 20 * attempt
                        print(f"[*] CoinGecko rate limit (429) on page {page}. Retrying in {wait_time}s (attempt {attempt}/{max_retries})...")
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
                    time.sleep(4 * attempt)

            if not success:
                print(f"[!] Warning: Failed to fetch page {page} after {max_retries} attempts. Continuing with available pages.")

            # Polite delay between paginated calls for free tier
            if page < max_pages:
                time.sleep(delay_seconds)

        return all_coins

    def _normalize_coin_data(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw CoinGecko market item into a clean dictionary."""
        current_price = float(item.get("current_price") or 0.0)
        market_cap = float(item.get("market_cap") or 0.0)
        total_volume = float(item.get("total_volume") or 0.0)
        fdv = item.get("fully_diluted_valuation")
        fdv = float(fdv) if fdv is not None else market_cap

        raw_ath = item.get("ath")
        ath = float(raw_ath) if raw_ath is not None else None

        raw_atl = item.get("atl")
        atl = float(raw_atl) if raw_atl is not None else None

        raw_ath_change = item.get("ath_change_percentage")
        ath_change_pct = float(raw_ath_change) if raw_ath_change is not None else None

        pct_30d = item.get("price_change_percentage_30d_in_currency")
        pct_30d = float(pct_30d) if pct_30d is not None else 0.0

        # Multiples calculation
        # 30-day multiple: e.g. +400% change -> (1 + 400/100) = 5.0x
        if pct_30d > 0:
            thirty_day_multiple = round(1.0 + (pct_30d / 100.0), 2)
        else:
            thirty_day_multiple = round(1.0 / (1.0 + abs(pct_30d) / 100.0), 2) if pct_30d > -100 else 0.0

        # ATH multiple calculation
        # If ATL or ATH is missing/None/0, ath_multiple is None (data unavailable)
        # Otherwise, calculate multiple from ATL to current price (e.g. 45.49x for BTW)
        if atl is not None and atl > 0 and current_price > 0:
            ath_multiple = round(current_price / atl, 2)
        else:
            ath_multiple = None

        # ATH proximity flag (within 20% of ATH)
        is_near_ath = ath_change_pct is not None and ath_change_pct >= -20.0

        return {
            "id": item.get("id", ""),
            "symbol": (item.get("symbol") or "").upper(),
            "name": item.get("name", ""),
            "current_price": current_price,
            "market_cap": market_cap,
            "total_volume": total_volume,
            "fdv": fdv,
            "ath": ath,
            "atl": atl,
            "ath_change_pct": ath_change_pct,
            "is_near_ath": is_near_ath,
            "price_change_30d_pct": pct_30d,
            "ath_multiple": ath_multiple,
            "thirty_day_multiple": thirty_day_multiple,
        }
