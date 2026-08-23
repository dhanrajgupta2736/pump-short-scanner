"""
Multi-Exchange Automated Snapshot Logger for Forward-Test Candidates (Price, Open Interest, Funding Rate).

DESIGN DECISION - DIRECT EXCHANGE APIS VS COINGLASS:
We deliberately chose direct public exchange APIs (Binance, Bybit, OKX) over aggregators
like Coinglass. Coinglass API is a paid subscription product (~$29/month minimum), whereas
Binance, Bybit, and OKX expose raw, high-resolution Open Interest and Funding Rate data
via free public endpoints without authentication. Coinglass's primary value-add is derived
analytics (e.g. liquidation heatmaps), which is not needed for this raw forward-testing log.

DATA RETENTION & BACKFILL LIMITATION:
Exchange free public APIs only report CURRENT real-time values (Binance historical OI is
capped at 30 days). This tool records live forward snapshots on each run and cannot backfill
older historical OI.
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

# File Paths
LOG_FILE_PATH = Path(__file__).resolve().parent.parent / "data" / "oi_funding_manual_log.csv"

# ==============================================================================
# FORWARD-TEST CANDIDATE COINS (Placeholder list)
# ==============================================================================
# Update or expand this list as candidates are discovered from main.py scanner.
# By default, exchange symbols are generated automatically, or specified explicitly.
FORWARD_TEST_CANDIDATES: List[Dict[str, Any]] = [
    {
        "coin": "BOME",
        "binance_symbol": "BOMEUSDT",
        "bybit_symbol": "BOMEUSDT",
        "okx_symbol": "BOME-USDT-SWAP",
    },
    {
        "coin": "DOGE",
        "binance_symbol": "DOGEUSDT",
        "bybit_symbol": "DOGEUSDT",
        "okx_symbol": "DOGE-USDT-SWAP",
    },
    {
        "coin": "BTW",
        "binance_symbol": "BTWUSDT",
        "bybit_symbol": "BTWUSDT",
        "okx_symbol": "BTW-USDT-SWAP",
    },
]


class BinanceFuturesClient:
    """Fetches Binance USDT-M Perpetual Futures public data."""

    BASE_URL = "https://fapi.binance.com"

    def __init__(self, timeout: int = 8):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "pump-short-scanner/1.0", "Accept": "application/json"})

    def fetch(self, symbol: str) -> Optional[Dict[str, Any]]:
        # 1. Price
        try:
            r_p = self.session.get(f"{self.BASE_URL}/fapi/v1/ticker/price", params={"symbol": symbol}, timeout=self.timeout)
            if r_p.status_code == 400:
                print(f"[!] Binance: '{symbol}' is not listed on USDT-M Futures. Skipping.")
                return None
            r_p.raise_for_status()
            price = float(r_p.json().get("price") or 0.0)
        except Exception as e:
            print(f"[!] Binance error for '{symbol}': {e}")
            return None

        # 2. Funding Rate
        try:
            r_f = self.session.get(f"{self.BASE_URL}/fapi/v1/premiumIndex", params={"symbol": symbol}, timeout=self.timeout)
            r_f.raise_for_status()
            funding_rate = float(r_f.json().get("lastFundingRate") or 0.0)
        except Exception:
            funding_rate = 0.0

        # 3. Open Interest
        try:
            r_oi = self.session.get(f"{self.BASE_URL}/fapi/v1/openInterest", params={"symbol": symbol}, timeout=self.timeout)
            r_oi.raise_for_status()
            open_interest = float(r_oi.json().get("openInterest") or 0.0)
        except Exception:
            open_interest = 0.0

        return {
            "exchange": "Binance",
            "symbol": symbol,
            "price": price,
            "open_interest": open_interest,
            "open_interest_usd": open_interest * price,
            "funding_rate": funding_rate,
        }


class BybitFuturesClient:
    """Fetches Bybit Linear (USDT) Perpetual Futures public data via v5 API."""

    BASE_URL = "https://api.bybit.com"

    def __init__(self, timeout: int = 8):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "pump-short-scanner/1.0", "Accept": "application/json"})

    def fetch(self, symbol: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/v5/market/tickers"
        params = {"category": "linear", "symbol": symbol}

        try:
            res = self.session.get(url, params=params, timeout=self.timeout)
            res.raise_for_status()
            data = res.json()
            items = data.get("result", {}).get("list", [])
            if not items:
                print(f"[!] Bybit: '{symbol}' not found on Linear Futures. Skipping.")
                return None

            item = items[0]
            price = float(item.get("lastPrice") or 0.0)
            funding_rate = float(item.get("fundingRate") or 0.0)
            open_interest = float(item.get("openInterest") or 0.0)
            oi_usd = float(item.get("openInterestValue") or (open_interest * price))

            return {
                "exchange": "Bybit",
                "symbol": symbol,
                "price": price,
                "open_interest": open_interest,
                "open_interest_usd": oi_usd,
                "funding_rate": funding_rate,
            }
        except Exception as e:
            print(f"[!] Bybit error for '{symbol}': {e}")
            return None


class OKXFuturesClient:
    """Fetches OKX Perpetual Swap public data via v5 API."""

    BASE_URL = "https://www.okx.com"

    def __init__(self, timeout: int = 3):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "pump-short-scanner/1.0", "Accept": "application/json"})

    def fetch(self, inst_id: str) -> Optional[Dict[str, Any]]:
        # 1. Price Ticker
        try:
            r_t = self.session.get(f"{self.BASE_URL}/api/v5/market/ticker", params={"instId": inst_id}, timeout=self.timeout)
            r_t.raise_for_status()
            t_data = r_t.json().get("data", [])
            if not t_data:
                print(f"[!] OKX: '{inst_id}' not found on Perpetual Swap. Skipping.")
                return None
            price = float(t_data[0].get("last") or 0.0)
        except requests.exceptions.ConnectTimeout:
            print(f"[!] OKX: Connection timed out for '{inst_id}' (regional restriction). Skipping.")
            return None
        except Exception as e:
            print(f"[!] OKX price error for '{inst_id}': {e}")
            return None

        # 2. Open Interest
        try:
            r_oi = self.session.get(
                f"{self.BASE_URL}/api/v5/public/open-interest",
                params={"instType": "SWAP", "instId": inst_id},
                timeout=self.timeout,
            )
            r_oi.raise_for_status()
            oi_data = r_oi.json().get("data", [])
            open_interest = float(oi_data[0].get("oi") or 0.0) if oi_data else 0.0
            oi_usd = float(oi_data[0].get("oiCcy") or (open_interest * price)) if oi_data else (open_interest * price)
        except Exception:
            open_interest = 0.0
            oi_usd = 0.0

        # 3. Funding Rate
        try:
            r_f = self.session.get(
                f"{self.BASE_URL}/api/v5/public/funding-rate",
                params={"instId": inst_id},
                timeout=self.timeout,
            )
            r_f.raise_for_status()
            f_data = r_f.json().get("data", [])
            funding_rate = float(f_data[0].get("fundingRate") or 0.0) if f_data else 0.0
        except Exception:
            funding_rate = 0.0

        return {
            "exchange": "OKX",
            "symbol": inst_id,
            "price": price,
            "open_interest": open_interest,
            "open_interest_usd": oi_usd,
            "funding_rate": funding_rate,
        }


def ensure_csv_structure(file_path: Path) -> None:
    """Ensure data directory and updated 7-column CSV header exist."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    expected_header = ["date", "coin", "exchange", "price", "open_interest", "funding_rate", "notes"]

    if not file_path.exists() or file_path.stat().st_size == 0:
        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(expected_header)
        return

    # Check existing header format; migrate if needed
    with open(file_path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        first_row = next(reader, None)

    if first_row and "exchange" not in first_row:
        # Migrate old 6-column format to new 7-column format with default exchange='Binance'
        rows = []
        with open(file_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            _ = next(reader, None)
            for row in reader:
                if len(row) == 6:
                    rows.append([row[0], row[1], "Binance", row[2], row[3], row[4], row[5]])
                else:
                    rows.append(row)

        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(expected_header)
            writer.writerows(rows)


def append_log_row(
    file_path: Path,
    timestamp: str,
    coin_symbol: str,
    exchange: str,
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
            exchange,
            f"{price:.8f}".rstrip("0").rstrip(".") if price < 1 else f"{price:.4f}",
            f"{open_interest:.2f}",
            f"{funding_rate:.8f}",
            notes,
        ])


def run_auto_logger(candidates: Optional[List[Dict[str, Any]]] = None) -> None:
    """
    Fetch current live Price, Open Interest, and Funding Rate across Binance, Bybit, and OKX,
    display a comparison table, and append results to data/oi_funding_manual_log.csv.
    """
    target_candidates = candidates or FORWARD_TEST_CANDIDATES
    ensure_csv_structure(LOG_FILE_PATH)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("=" * 105)
    print("      📊 MULTI-EXCHANGE FORWARD-TEST AUTO-LOGGER (Binance / Bybit / OKX Public APIs)")
    print("=" * 105)
    print(f"Timestamp (UTC) : {now_utc}")
    print(f"Target Log File : {LOG_FILE_PATH}")
    print(f"Candidates ({len(target_candidates)}) : {', '.join(c['coin'] for c in target_candidates)}")
    print("=" * 105)

    binance_client = BinanceFuturesClient()
    bybit_client = BybitFuturesClient()
    okx_client = OKXFuturesClient()

    logged_count = 0

    header = f"{'Coin':<8} {'Exchange':<10} {'Symbol / Ticker':<18} {'Price':<14} {'Open Interest':<18} {'OI (USD)':<14} {'Funding Rate':<14}"
    print(header)
    print("-" * 105)

    for item in target_candidates:
        coin = item["coin"]
        binance_sym = item.get("binance_symbol", f"{coin}USDT")
        bybit_sym = item.get("bybit_symbol", f"{coin}USDT")
        okx_sym = item.get("okx_symbol", f"{coin}-USDT-SWAP")

        exchange_tasks = [
            ("Binance", binance_client, binance_sym),
            ("Bybit", bybit_client, bybit_sym),
            ("OKX", okx_client, okx_sym),
        ]

        for ex_name, client, sym in exchange_tasks:
            metrics = client.fetch(sym)
            if metrics is None:
                continue

            price = metrics["price"]
            oi = metrics["open_interest"]
            oi_usd = metrics["open_interest_usd"]
            fr = metrics["funding_rate"]
            fr_pct = fr * 100.0

            # Formatting
            price_str = f"${price:,.4f}" if price >= 1.0 else f"${price:.6f}"
            oi_str = f"{oi:,.0f}"
            oi_usd_str = f"${oi_usd / 1e6:.2f}M" if oi_usd >= 1e6 else f"${oi_usd:,.0f}"
            fr_str = f"{fr_pct:+.4f}%"

            print(f"{coin:<8} {ex_name:<10} {sym:<18} {price_str:<14} {oi_str:<18} {oi_usd_str:<14} {fr_str:<14}")

            # Append row to CSV
            append_log_row(
                file_path=LOG_FILE_PATH,
                timestamp=now_utc,
                coin_symbol=coin,
                exchange=ex_name,
                price=price,
                open_interest=oi,
                funding_rate=fr,
                notes="auto",
            )
            logged_count += 1

    print("-" * 105)
    print(f"[+] Successfully logged {logged_count} snapshot record(s) across exchanges to {LOG_FILE_PATH.name}.\n")


if __name__ == "__main__":
    run_auto_logger()
