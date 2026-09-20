"""
Daily CoinGecko Top-200 Rank Movement Tracker for Pump Short Scanner.
Identifies newly-entered top-200 coins and screens them against the 4 pump-short filter criteria.
Updates active_watchlist.json in Amazon S3 for 4-hourly derivative logging by auto_logger.py.
"""

from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import requests

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None
    ClientError = Exception

# Local package imports
try:
    import config
    from scanner.filters import evaluate_coin
except ImportError:
    # Handle direct script execution from repo root
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import config
    from scanner.filters import evaluate_coin

# Ensure UTF-8 output encoding
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Constants
DEFAULT_BUCKET_NAME = "pump-short-scanner-logs-dhanraj-7938"
LOCAL_WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "data" / "active_watchlist.json"
RANK_HISTORY_PREFIX = "rank_history/"
WATCHLIST_KEY = "active_watchlist.json"


class Top200RankTracker:
    """Tracks daily CoinGecko top 200 rank movement and screens for pump short candidates."""

    COINGECKO_BASE_URL = getattr(config, "COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3")

    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or os.environ.get("LOG_BUCKET_NAME", DEFAULT_BUCKET_NAME)
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "pump-short-scanner/1.0",
        })
        self.s3_client = boto3.client("s3") if boto3 else None

    def fetch_current_top_200(self) -> List[Dict[str, Any]]:
        """
        Fetch CoinGecko's top 200 coins by market cap in a single request.
        Includes 30-day price change, ATH, ATL, FDV, and volume.
        """
        url = f"{self.COINGECKO_BASE_URL.rstrip('/')}/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 200,
            "page": 1,
            "price_change_percentage": "30d",
        }

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=20)
                if response.status_code == 429:
                    wait_seconds = 20 * attempt
                    logger.warning("CoinGecko 429 rate limit hit. Sleeping for %ds...", wait_seconds)
                    time.sleep(wait_seconds)
                    continue

                response.raise_for_status()
                raw_items = response.json()
                if not isinstance(raw_items, list):
                    raise ValueError(f"Expected list from CoinGecko, got: {type(raw_items)}")

                coins = []
                for rank, item in enumerate(raw_items, start=1):
                    coins.append(self._normalize_coin(item, rank))
                return coins

            except requests.exceptions.RequestException as e:
                logger.warning("Fetch top 200 attempt %d failed: %s", attempt, e)
                time.sleep(5 * attempt)

        raise RuntimeError(f"Failed to fetch CoinGecko top 200 after {max_retries} attempts.")

    def _normalize_coin(self, item: Dict[str, Any], rank: int) -> Dict[str, Any]:
        """Normalize raw CoinGecko item into a clean schema compatible with filters.py."""
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

        if pct_30d > 0:
            thirty_day_multiple = round(1.0 + (pct_30d / 100.0), 2)
        else:
            thirty_day_multiple = round(1.0 / (1.0 + abs(pct_30d) / 100.0), 2) if pct_30d > -100 else 0.0

        if atl is not None and atl > 0 and current_price > 0:
            ath_multiple = round(current_price / atl, 2)
        else:
            ath_multiple = None

        is_near_ath = ath_change_pct is not None and ath_change_pct >= -20.0

        return {
            "id": item.get("id", ""),
            "symbol": (item.get("symbol") or "").upper(),
            "name": item.get("name", ""),
            "rank": rank,
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

    def save_rank_snapshot(self, date_str: str, now_iso: str, coins: List[Dict[str, Any]]) -> str:
        """Store the top 200 rank snapshot to S3."""
        key = f"{RANK_HISTORY_PREFIX}{date_str}.json"
        payload = {
            "date": date_str,
            "timestamp": now_iso,
            "count": len(coins),
            "coins": [
                {
                    "id": c["id"],
                    "symbol": c["symbol"],
                    "name": c["name"],
                    "rank": c["rank"],
                    "market_cap": c["market_cap"],
                    "price": c["current_price"],
                    "ath_multiple": c["ath_multiple"],
                    "thirty_day_multiple": c["thirty_day_multiple"],
                }
                for c in coins
            ],
        }

        if self.s3_client and self.bucket_name:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(payload, indent=2),
                ContentType="application/json",
            )
            logger.info("Saved rank snapshot to s3://%s/%s", self.bucket_name, key)
        else:
            logger.info("Local run: skipping S3 rank history upload (no s3 client).")
        return key

    def load_prior_rank_snapshot(self, today_date_str: str) -> Tuple[Optional[str], Set[str]]:
        """
        Load prior rank snapshot (yesterday's or most recent prior date) from S3.
        Returns (prior_date_str, set_of_coin_ids).
        """
        if not self.s3_client or not self.bucket_name:
            return None, set()

        # 1. Attempt yesterday's exact date
        today_dt = datetime.strptime(today_date_str, "%Y-%m-%d")
        yesterday_str = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_key = f"{RANK_HISTORY_PREFIX}{yesterday_str}.json"

        try:
            resp = self.s3_client.get_object(Bucket=self.bucket_name, Key=yesterday_key)
            data = json.loads(resp["Body"].read().decode("utf-8"))
            coin_ids = {c["id"] for c in data.get("coins", []) if "id" in c}
            logger.info("Loaded yesterday's rank snapshot from s3://%s/%s (%d coins)", self.bucket_name, yesterday_key, len(coin_ids))
            return yesterday_str, coin_ids
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchKey":
                logger.warning("Error fetching %s: %s", yesterday_key, e)

        # 2. If yesterday's file does not exist, find the most recent prior snapshot in rank_history/
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=RANK_HISTORY_PREFIX)
            keys = []
            for page in pages:
                for obj in page.get("Contents", []):
                    k = obj["Key"]
                    if k.endswith(".json") and k != f"{RANK_HISTORY_PREFIX}{today_date_str}.json":
                        keys.append(k)

            keys.sort()
            if keys:
                latest_prior_key = keys[-1]
                resp = self.s3_client.get_object(Bucket=self.bucket_name, Key=latest_prior_key)
                data = json.loads(resp["Body"].read().decode("utf-8"))
                prior_date = data.get("date", latest_prior_key.replace(RANK_HISTORY_PREFIX, "").replace(".json", ""))
                coin_ids = {c["id"] for c in data.get("coins", []) if "id" in c}
                logger.info("Found prior snapshot s3://%s/%s from %s (%d coins)", self.bucket_name, latest_prior_key, prior_date, len(coin_ids))
                return prior_date, coin_ids
        except Exception as e:
            logger.warning("Could not search for prior rank snapshots: %s", e)

        logger.info("No prior rank snapshot found in S3 (first-ever run).")
        return None, set()

    def load_active_watchlist(self) -> Dict[str, Any]:
        """Load active watchlist from S3 or local file fallback."""
        if self.s3_client and self.bucket_name:
            try:
                resp = self.s3_client.get_object(Bucket=self.bucket_name, Key=WATCHLIST_KEY)
                data = json.loads(resp["Body"].read().decode("utf-8"))
                logger.info("Loaded active watchlist from s3://%s/%s (%d coins)", self.bucket_name, WATCHLIST_KEY, len(data.get("coins", [])))
                return data
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchKey":
                    logger.warning("Error loading watchlist from S3: %s", e)

        if LOCAL_WATCHLIST_PATH.exists():
            try:
                with open(LOCAL_WATCHLIST_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info("Loaded active watchlist from local file %s (%d coins)", LOCAL_WATCHLIST_PATH.name, len(data.get("coins", [])))
                    return data
            except Exception as e:
                logger.warning("Error reading local watchlist: %s", e)

        # Default initial watchlist
        return {
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "coins": [
                {"coin": "BOME", "binance_symbol": "BOMEUSDT", "bybit_symbol": "BOMEUSDT", "okx_symbol": "BOME-USDT-SWAP", "added_at": "2026-08-23T13:43:41Z", "source": "manual_seed"},
                {"coin": "BTW", "binance_symbol": "BTWUSDT", "bybit_symbol": "BTWUSDT", "okx_symbol": "BTW-USDT-SWAP", "added_at": "2026-08-23T13:43:41Z", "source": "manual_seed"},
                {"coin": "AKE", "binance_symbol": "AKEUSDT", "bybit_symbol": "AKEUSDT", "okx_symbol": "AKE-USDT-SWAP", "added_at": "2026-09-20T13:51:46Z", "source": "manual_trade"},
            ]
        }

    def save_active_watchlist(self, watchlist: Dict[str, Any]) -> None:
        """Save active watchlist to S3 and locally."""
        payload_bytes = json.dumps(watchlist, indent=2).encode("utf-8")

        if self.s3_client and self.bucket_name:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=WATCHLIST_KEY,
                Body=payload_bytes,
                ContentType="application/json",
            )
            logger.info("Successfully updated active watchlist in s3://%s/%s", self.bucket_name, WATCHLIST_KEY)

        try:
            LOCAL_WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LOCAL_WATCHLIST_PATH, "w", encoding="utf-8") as f:
                f.write(json.dumps(watchlist, indent=2))
        except Exception as e:
            logger.warning("Could not write local watchlist: %s", e)

    def run(self) -> Dict[str, Any]:
        """Execute the daily rank tracking and candidate screening cycle."""
        now_dt = datetime.now(timezone.utc)
        today_str = now_dt.strftime("%Y-%m-%d")
        now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        print("=" * 85)
        print("  🔍 DAILY COINGECKO TOP-200 RANK TRACKER & PUMP SHORT SCREENER")
        print("=" * 85)
        print(f"Timestamp (UTC) : {now_iso}")
        print(f"Date            : {today_str}")
        print(f"Target Bucket   : s3://{self.bucket_name}")
        print("=" * 85)

        # 1. Fetch current top 200
        print("[*] Fetching current Top 200 coins from CoinGecko...")
        today_coins = self.fetch_current_top_200()
        print(f"[+] Successfully fetched {len(today_coins)} coins in Top 200.")

        # 2. Save today's snapshot to S3
        snapshot_key = self.save_rank_snapshot(today_str, now_iso, today_coins)

        # 3. Load prior day's rank snapshot
        prior_date, prior_coin_ids = self.load_prior_rank_snapshot(today_str)

        new_entrants: List[Dict[str, Any]] = []
        if prior_coin_ids:
            print(f"[+] Comparing today's Top 200 with baseline from {prior_date} ({len(prior_coin_ids)} coins)...")
            for coin in today_coins:
                if coin["id"] not in prior_coin_ids:
                    new_entrants.append(coin)
            print(f"[+] Found {len(new_entrants)} newly entered coin(s) in Top 200.")
        else:
            print("[i] Baseline run: No prior snapshot available for delta comparison.")
            print("[i] Future daily runs will compare against today's snapshot.")

        # 4. Filter newly entered coins through 4 pump-short criteria
        passing_candidates: List[Dict[str, Any]] = []
        if new_entrants:
            print("\n" + "-" * 85)
            print("  EVALUATING NEW ENTRANTS AGAINST 4 PUMP-SHORT CRITERIA")
            print("-" * 85)
            for coin in new_entrants:
                is_match, criteria = evaluate_coin(coin)
                matched_reasons = []
                if criteria.get("market_cap_ok"):
                    matched_reasons.append(f"MCap: ${coin['market_cap'] / 1e6:.1f}M >= $500M")
                if criteria.get("fdv_ok"):
                    matched_reasons.append(f"FDV: ${coin['fdv'] / 1e6:.1f}M >= $1B")
                if criteria.get("ath_multiple_ok"):
                    matched_reasons.append(f"ATH Multiple: {coin['ath_multiple']}x >= 10x (Near ATH)")
                if criteria.get("thirty_day_multiple_ok"):
                    matched_reasons.append(f"30d Multiple: {coin['thirty_day_multiple']}x >= 5x")

                status_str = "PASSED" if is_match else "FAILED"
                print(f"[{status_str}] Rank #{coin['rank']:<3} {coin['symbol']:<8} ({coin['name']})")
                print(f"       Price: ${coin['current_price']:.6f} | MCap: ${coin['market_cap']/1e6:.1f}M | FDV: ${coin['fdv']/1e6:.1f}M")
                print(f"       ATH Multiple: {coin['ath_multiple']}x | 30d Multiple: {coin['thirty_day_multiple']}x")

                if is_match:
                    coin["matched_reasons"] = matched_reasons
                    passing_candidates.append(coin)
            print("-" * 85)
        else:
            print("[i] No newly entered coins in Top 200 today.")

        # 5. Append passing candidates to active watchlist
        watchlist = self.load_active_watchlist()
        existing_coins = watchlist.get("coins", [])
        existing_symbols = {c.get("coin", "").upper() for c in existing_coins}

        added_coins = []
        for cand in passing_candidates:
            sym = cand["symbol"].upper()
            if sym not in existing_symbols:
                new_entry = {
                    "coin": sym,
                    "binance_symbol": f"{sym}USDT",
                    "bybit_symbol": f"{sym}USDT",
                    "okx_symbol": f"{sym}-USDT-SWAP",
                    "coingecko_id": cand["id"],
                    "name": cand["name"],
                    "added_at": now_iso,
                    "source": "rank_tracker",
                    "matched_criteria": cand.get("matched_reasons", []),
                    "metrics": {
                        "rank": cand["rank"],
                        "market_cap": cand["market_cap"],
                        "fdv": cand["fdv"],
                        "price": cand["current_price"],
                        "ath_multiple": cand["ath_multiple"],
                        "thirty_day_multiple": cand["thirty_day_multiple"],
                    },
                }
                existing_coins.append(new_entry)
                existing_symbols.add(sym)
                added_coins.append(new_entry)
                print(f"[+] Added '{sym}' to active watchlist!")

        if added_coins:
            watchlist["updated_at"] = now_iso
            watchlist["coins"] = existing_coins
            self.save_active_watchlist(watchlist)
            print(f"[+] Watchlist updated. Total active candidates: {len(existing_coins)}")
        else:
            print(f"[i] Watchlist unchanged. Total active candidates: {len(existing_coins)}")

        print("=" * 85 + "\n")

        return {
            "date": today_str,
            "timestamp": now_iso,
            "top_200_count": len(today_coins),
            "prior_baseline_date": prior_date,
            "new_entrants_count": len(new_entrants),
            "passing_candidates_count": len(passing_candidates),
            "added_to_watchlist": [c["coin"] for c in added_coins],
            "total_watchlist_coins": len(existing_coins),
        }


def lambda_handler(event: Optional[Dict[str, Any]] = None, context: Any = None) -> Dict[str, Any]:
    """AWS Lambda entry point for scheduled daily execution."""
    logger.info("Rank Tracker Lambda started via EventBridge event: %s", json.dumps(event or {}))
    tracker = Top200RankTracker()
    results = tracker.run()
    return {
        "statusCode": 200,
        "body": json.dumps(results),
    }


if __name__ == "__main__":
    tracker = Top200RankTracker()
    tracker.run()
