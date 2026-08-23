"""
Automated Snapshot Logger for Forward-Test Candidates (Price, Open Interest, Funding Rate).

IMPORTANT DATA RETENTION & BACKFILL LIMITATION:
Binance's free public Open Interest API only retains 30 days of historical data.
This tool captures CURRENT live snapshot values at runtime and appends them
to 'data/oi_funding_manual_log.csv' for forward-testing. It cannot backfill
historical OI data that does not exist in Binance's public window.
"""

import csv
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import requests

# Ensure UTF-8 output encoding if supported by stream
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Base URLs
BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com"
LOG_FILE_PATH = Path(__file__).resolve().parent.parent / "data" / "oi_funding_manual_log.csv"

# ==============================================================================
# FORWARD-TEST CANDIDATE COINS (Placeholder list)
# ==============================================================================
# Update or replace this list with active candidates identified by main.py.
# Format: {"symbol": "<Display Symbol>", "binance_symbol": "<USDT-M Perp Ticker>"}
FORWARD_TEST_CANDIDATES: List[Dict[str, str]] = [
    {"symbol": "BOME", "binance_symbol": "BOMEUSDT"},
    {"symbol": "DOGE", "binance_symbol": "DOGEUSDT"},
    {"symbol": "BTW", "binance_symbol": "BTWUSDT"},  # Example test candidate
]


class BinanceFuturesClient:
    """Client for fetching public Binance USDT-M Perpetual Futures market metrics."""

    def __init__(self, base_url: str = BINANCE_FUTURES_BASE_URL, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "pump-short-scanner/1.0",
        })

    def fetch_candidate_metrics(self, binance_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch Price, Funding Rate, and Open Interest for a specific Binance USDT-M perp symbol.
        Returns None if symbol is unlisted or API error occurs.
        """
        symbol = binance_symbol.upper()

        # 1. Fetch Current Price
        price_url = f"{self.base_url}/fapi/v1/ticker/price"
        try:
            r_price = self.session.get(price_url, params={"symbol": symbol}, timeout=self.timeout)
            if r_price.status_code == 400:
                print(f"[!] Warning: '{symbol}' is not listed on Binance USDT-M Futures. Skipping.")
                return None
            r_price.raise_for_status()
            price_data = r_price.json()
            current_price = float(price_data.get("price") or 0.0)
        except requests.exceptions.RequestException as err:
            print(f"[!] Network error fetching price for {symbol}: {err}")
            return None

        # 2. Fetch Funding Rate
        premium_url = f"{self.base_url}/fapi/v1/premiumIndex"
        try:
            r_prem = self.session.get(premium_url, params={"symbol": symbol}, timeout=self.timeout)
            r_prem.raise_for_status()
            prem_data = r_prem.json()
            funding_rate = float(prem_data.get("lastFundingRate") or 0.0)
        except requests.exceptions.RequestException as err:
            print(f"[!] Network error fetching funding rate for {symbol}: {err}")
            funding_rate = 0.0

        # 3. Fetch Open Interest
        oi_url = f"{self.base_url}/fapi/v1/openInterest"
        try:
            r_oi = self.session.get(oi_url, params={"symbol": symbol}, timeout=self.timeout)
            r_oi.raise_for_status()
            oi_data = r_oi.json()
            open_interest = float(oi_data.get("openInterest") or 0.0)
        except requests.exceptions.RequestException as err:
            print(f"[!] Network error fetching Open Interest for {symbol}: {err}")
            open_interest = 0.0

        # Compute USD Notional Open Interest
        oi_usd = open_interest * current_price

        return {
            "symbol": symbol,
            "price": current_price,
            "funding_rate": funding_rate,
            "open_interest": open_interest,
            "open_interest_usd": oi_usd,
        }


def ensure_csv_header(file_path: Path) -> None:
    """Ensure data directory and CSV header exist."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if not file_path.exists() or file_path.stat().st_size == 0:
        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "coin", "price", "open_interest", "funding_rate", "notes"])


def append_log_row(
    file_path: Path,
    timestamp: str,
    coin_symbol: str,
    price: float,
    open_interest: float,
    funding_rate: float,
    notes: str = "auto",
) -> None:
    """Append a single snapshot record to the forward-test CSV."""
    with open(file_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            timestamp,
            coin_symbol,
            f"{price:.8f}".rstrip("0").rstrip(".") if price < 1 else f"{price:.4f}",
            f"{open_interest:.2f}",
            f"{funding_rate:.8f}",
            notes,
        ])


def run_auto_logger(candidates: Optional[List[Dict[str, str]]] = None) -> None:
    """
    Fetch current live price, Open Interest, and funding rate for candidates,
    display a summary table, and append results to data/oi_funding_manual_log.csv.
    """
    target_candidates = candidates or FORWARD_TEST_CANDIDATES
    ensure_csv_header(LOG_FILE_PATH)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("=" * 85)
    print("        📊 FORWARD-TEST AUTO-LOGGER (Binance USDT-M Futures Snapshot)")
    print("=" * 85)
    print(f"Timestamp (UTC): {now_utc}")
    print(f"Target Log File : {LOG_FILE_PATH}")
    print(f"Candidates ({len(target_candidates)}) : {', '.join(c['symbol'] for c in target_candidates)}")
    print("=" * 85)

    client = BinanceFuturesClient()
    logged_count = 0

    header = f"{'Coin':<8} {'Binance Ticker':<16} {'Price':<14} {'Open Interest':<18} {'OI (USD)':<14} {'Funding Rate':<14}"
    print(header)
    print("-" * 85)

    for item in target_candidates:
        display_sym = item["symbol"]
        binance_sym = item.get("binance_symbol", f"{display_sym}USDT")

        metrics = client.fetch_candidate_metrics(binance_sym)
        if metrics is None:
            continue

        price = metrics["price"]
        oi = metrics["open_interest"]
        oi_usd = metrics["open_interest_usd"]
        fr = metrics["funding_rate"]
        fr_pct = fr * 100.0

        # Format display fields
        price_str = f"${price:,.4f}" if price >= 1.0 else f"${price:.6f}"
        oi_str = f"{oi:,.0f}"
        oi_usd_str = f"${oi_usd / 1e6:.2f}M" if oi_usd >= 1e6 else f"${oi_usd:,.0f}"
        fr_str = f"{fr_pct:+.4f}%"

        print(f"{display_sym:<8} {binance_sym:<16} {price_str:<14} {oi_str:<18} {oi_usd_str:<14} {fr_str:<14}")

        # Append to CSV
        append_log_row(
            file_path=LOG_FILE_PATH,
            timestamp=now_utc,
            coin_symbol=display_sym,
            price=price,
            open_interest=oi,
            funding_rate=fr,
            notes="auto",
        )
        logged_count += 1

    print("-" * 85)
    print(f"[+] Successfully logged {logged_count} record(s) to {LOG_FILE_PATH.name}.\n")


if __name__ == "__main__":
    run_auto_logger()
