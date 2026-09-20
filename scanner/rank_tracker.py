"""
Daily CoinGecko Top-1000 Rank Movement Tracker for Pump Short Scanner.
Fetches Top 1000 coins (4 pages x 250), tracks rank snapshots, identifies newly entered coins,
and screens them against the 4 pump-short filter criteria.
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
    from scanner.coingecko_client import CoinGeckoClient
    from scanner.filters import evaluate_coin
except ImportError:
    # Handle direct script execution from repo root
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import config
    from scanner.coingecko_client import CoinGeckoClient
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


class Top1000RankTracker:
    """Tracks daily CoinGecko top 1000 rank movement and screens for pump short candidates."""

    COINGECKO_BASE_URL = getattr(config, "COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3")

    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or os.environ.get("LOG_BUCKET_NAME", DEFAULT_BUCKET_NAME)
        self.s3_client = boto3.client("s3") if boto3 else None
        self.cg_client = CoinGeckoClient(base_url=self.COINGECKO_BASE_URL, timeout=20)

    def fetch_current_top_1000(self) -> List[Dict[str, Any]]:
        """
        Fetch CoinGecko's top 1000 coins by market cap using paginated queries
        (4 pages * 250 coins/page) with built-in rate-limit backoff.
        """
        logger.info("Fetching CoinGecko Top 1000 coins (4 pages x 250)...")
        raw_coins = self.cg_client.fetch_top_market_coins(max_pages=4, per_page=250, delay_seconds=2.0)

        for rank, coin in enumerate(raw_coins, start=1):
            coin["rank"] = rank

        return raw_coins

    def save_rank_snapshot(self, now_dt: datetime, coins: List[Dict[str, Any]]) -> str:
        """Store the top 1000 rank snapshot to S3 with a timestamped key."""
        date_str = now_dt.strftime("%Y-%m-%d")
        time_str = now_dt.strftime("%H%M%S")
        now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        key = f"{RANK_HISTORY_PREFIX}{date_str}_{time_str}.json"
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
                    "ath_multiple": c.get("ath_multiple"),
                    "thirty_day_multiple": c.get("thirty_day_multiple"),
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
            logger.info("Saved rank snapshot to s3://%s/%s (%d coins)", self.bucket_name, key, len(coins))
        else:
            logger.info("Local run: skipping S3 rank history upload (no s3 client).")
        return key

    def load_prior_rank_snapshot(self, exclude_key: Optional[str] = None) -> Tuple[Optional[str], Set[str]]:
        """
        Load the most recent prior rank snapshot from S3.
        Finds the newest snapshot in rank_history/ (excluding exclude_key).
        Returns (prior_timestamp_or_date, set_of_coin_ids).
        """
        if not self.s3_client or not self.bucket_name:
            return None, set()

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=RANK_HISTORY_PREFIX)
            candidates = []
            for page in pages:
                for obj in page.get("Contents", []):
                    k = obj["Key"]
                    if k.endswith(".json") and k != exclude_key:
                        candidates.append((k, obj.get("LastModified")))

            if candidates:
                # Sort by Key and LastModified to find the most recent prior snapshot
                # Standard YYYY-MM-DD_HHMMSS sorts chronologically.
                candidates.sort(key=lambda item: (item[0], item[1]))
                latest_prior_key = candidates[-1][0]
                resp = self.s3_client.get_object(Bucket=self.bucket_name, Key=latest_prior_key)
                data = json.loads(resp["Body"].read().decode("utf-8"))
                prior_label = data.get("timestamp") or data.get("date") or latest_prior_key.replace(RANK_HISTORY_PREFIX, "").replace(".json", "")
                coin_ids = {c["id"] for c in data.get("coins", []) if "id" in c}
                logger.info("Loaded most recent prior snapshot s3://%s/%s from %s (%d coins)", self.bucket_name, latest_prior_key, prior_label, len(coin_ids))
                return prior_label, coin_ids
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
        """Execute the 6-hourly rank tracking and candidate screening cycle across Top 1000."""
        now_dt = datetime.now(timezone.utc)
        today_str = now_dt.strftime("%Y-%m-%d")
        now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        print("=" * 85)
        print("  🔍 6-HOURLY COINGECKO TOP-1000 RANK TRACKER & PUMP SHORT SCREENER")
        print("=" * 85)
        print(f"Timestamp (UTC) : {now_iso}")
        print(f"Date            : {today_str}")
        print(f"Target Bucket   : s3://{self.bucket_name}")
        print("=" * 85)

        # 1. Fetch current top 1000
        print("[*] Fetching current Top 1000 coins from CoinGecko (4 pages x 250)...")
        today_coins = self.fetch_current_top_1000()
        print(f"[+] Successfully fetched {len(today_coins)} coins in Top 1000.")

        # 2. Save current snapshot to S3
        snapshot_key = self.save_rank_snapshot(now_dt, today_coins)

        # 3. Load most recent prior rank snapshot (excluding current snapshot)
        prior_baseline, prior_coin_ids = self.load_prior_rank_snapshot(exclude_key=snapshot_key)

        new_entrants: List[Dict[str, Any]] = []
        if prior_coin_ids:
            print(f"[+] Comparing current Top 1000 with most recent prior baseline from {prior_baseline} ({len(prior_coin_ids)} coins)...")
            for coin in today_coins:
                if coin["id"] not in prior_coin_ids:
                    new_entrants.append(coin)
            print(f"[+] Found {len(new_entrants)} newly entered coin(s) in Top 1000.")
        else:
            print("[i] Baseline run: No prior snapshot available for delta comparison.")
            print("[i] Future 6-hour runs will compare against today's snapshot.")

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
                    matched_reasons.append(f"ATH Multiple: {coin.get('ath_multiple')}x >= 10x (Near ATH)")
                if criteria.get("thirty_day_multiple_ok"):
                    matched_reasons.append(f"30d Multiple: {coin.get('thirty_day_multiple')}x >= 5x")

                status_str = "PASSED" if is_match else "FAILED"
                print(f"[{status_str}] Rank #{coin['rank']:<4} {coin['symbol']:<8} ({coin['name']})")
                print(f"       Price: ${coin['current_price']:.6f} | MCap: ${coin['market_cap']/1e6:.1f}M | FDV: ${coin['fdv']/1e6:.1f}M")
                print(f"       ATH Multiple: {coin.get('ath_multiple')}x | 30d Multiple: {coin.get('thirty_day_multiple')}x")

                if is_match:
                    coin["matched_reasons"] = matched_reasons
                    passing_candidates.append(coin)
            print("-" * 85)
        else:
            print("[i] No newly entered coins in Top 1000 today.")

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
                    "source": "rank_tracker_top1000",
                    "matched_criteria": cand.get("matched_reasons", []),
                    "metrics": {
                        "rank": cand["rank"],
                        "market_cap": cand["market_cap"],
                        "fdv": cand["fdv"],
                        "price": cand["current_price"],
                        "ath_multiple": cand.get("ath_multiple"),
                        "thirty_day_multiple": cand.get("thirty_day_multiple"),
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
            "top_1000_count": len(today_coins),
            "prior_baseline": prior_baseline,
            "prior_baseline_date": prior_baseline,
            "new_entrants_count": len(new_entrants),
            "passing_candidates_count": len(passing_candidates),
            "added_to_watchlist": [c["coin"] for c in added_coins],
            "total_watchlist_coins": len(existing_coins),
            "snapshot_key": snapshot_key,
        }


# Backwards compatibility alias
Top200RankTracker = Top1000RankTracker


def lambda_handler(event: Optional[Dict[str, Any]] = None, context: Any = None) -> Dict[str, Any]:
    """AWS Lambda entry point for scheduled 6-hourly execution across Top 1000."""
    logger.info("Rank Tracker Lambda started via EventBridge event: %s", json.dumps(event or {}))
    tracker = Top1000RankTracker()
    results = tracker.run()
    return {
        "statusCode": 200,
        "body": json.dumps(results),
    }


if __name__ == "__main__":
    tracker = Top1000RankTracker()
    tracker.run()
