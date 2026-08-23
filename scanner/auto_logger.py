"""
Multi-Exchange Automated Snapshot Logger for Forward-Test Candidates (Price, Open Interest, Funding Rate).
Supports both local CSV logging and AWS Lambda serverless execution with Amazon S3 snapshot storage.

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
import io
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import requests

# Conditional boto3 import (available by default in AWS Lambda runtime)
try:
    import boto3
except ImportError:
    boto3 = None

# Ensure UTF-8 output encoding if supported by stream
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# File & S3 Paths
LOG_FILE_PATH = Path(__file__).resolve().parent.parent / "data" / "oi_funding_manual_log.csv"
LOG_BUCKET_NAME = os.environ.get("LOG_BUCKET_NAME")

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
            raw_price = r_p.json().get("price")
            price = float(raw_price) if raw_price is not None else None
        except Exception as e:
            print(f"[!] Binance price error for '{symbol}': {e}")
            return None

        # 2. Funding Rate
        try:
            r_f = self.session.get(f"{self.BASE_URL}/fapi/v1/premiumIndex", params={"symbol": symbol}, timeout=self.timeout)
            r_f.raise_for_status()
            raw_fr = r_f.json().get("lastFundingRate")
            funding_rate = float(raw_fr) if raw_fr is not None else None
        except Exception:
            funding_rate = None

        # 3. Open Interest (returned in base-currency coin units)
        try:
            r_oi = self.session.get(f"{self.BASE_URL}/fapi/v1/openInterest", params={"symbol": symbol}, timeout=self.timeout)
            r_oi.raise_for_status()
            raw_oi = r_oi.json().get("openInterest")
            open_interest = float(raw_oi) if raw_oi is not None else None
        except Exception:
            open_interest = None

        oi_usd = (open_interest * price) if (open_interest is not None and price is not None) else None

        return {
            "exchange": "Binance",
            "symbol": symbol,
            "price": price,
            "open_interest": open_interest,
            "open_interest_usd": oi_usd,
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
            raw_price = item.get("lastPrice")
            price = float(raw_price) if (raw_price is not None and raw_price != "") else None

            raw_fr = item.get("fundingRate")
            funding_rate = float(raw_fr) if (raw_fr is not None and raw_fr != "") else None

            # Open interest is reported in base-currency coin units
            raw_oi = item.get("openInterest")
            open_interest = float(raw_oi) if (raw_oi is not None and raw_oi != "") else None

            raw_oi_usd = item.get("openInterestValue")
            if raw_oi_usd is not None and raw_oi_usd != "":
                oi_usd = float(raw_oi_usd)
            elif open_interest is not None and price is not None:
                oi_usd = open_interest * price
            else:
                oi_usd = None

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

    def __init__(self, timeout: int = 4):
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
            raw_price = t_data[0].get("last")
            price = float(raw_price) if (raw_price is not None and raw_price != "") else None
        except requests.exceptions.ConnectTimeout:
            print(f"[!] OKX: Connection timed out for '{inst_id}' (regional restriction). Skipping.")
            return None
        except Exception as e:
            print(f"[!] OKX price error for '{inst_id}': {e}")
            return None

        # 2. Open Interest
        # Note on OKX OI Unit Standardisation:
        # OKX returns:
        # - 'oi': Number of contracts (e.g. 3.27M contracts)
        # - 'oiCcy': Open Interest in Base Currency units (e.g. 3.27B BOME coins), matching Binance & Bybit
        # - 'oiUsd': Open Interest USD notional value
        try:
            r_oi = self.session.get(
                f"{self.BASE_URL}/api/v5/public/open-interest",
                params={"instType": "SWAP", "instId": inst_id},
                timeout=self.timeout,
            )
            r_oi.raise_for_status()
            oi_data = r_oi.json().get("data", [])
            if oi_data:
                item = oi_data[0]
                raw_oi_ccy = item.get("oiCcy")
                raw_oi_contracts = item.get("oi")
                raw_oi_usd = item.get("oiUsd")

                # Use base-currency open interest (oiCcy) for direct comparability with Binance/Bybit
                if raw_oi_ccy is not None and raw_oi_ccy != "":
                    open_interest = float(raw_oi_ccy)
                elif raw_oi_contracts is not None and raw_oi_contracts != "":
                    open_interest = float(raw_oi_contracts)
                else:
                    open_interest = None

                if raw_oi_usd is not None and raw_oi_usd != "":
                    oi_usd = float(raw_oi_usd)
                elif open_interest is not None and price is not None:
                    oi_usd = open_interest * price
                else:
                    oi_usd = None
            else:
                open_interest = None
                oi_usd = None
        except Exception:
            open_interest = None
            oi_usd = None

        # 3. Funding Rate
        try:
            r_f = self.session.get(
                f"{self.BASE_URL}/api/v5/public/funding-rate",
                params={"instId": inst_id},
                timeout=self.timeout,
            )
            r_f.raise_for_status()
            f_data = r_f.json().get("data", [])
            if f_data and f_data[0].get("fundingRate") is not None and f_data[0].get("fundingRate") != "":
                funding_rate = float(f_data[0]["fundingRate"])
            else:
                funding_rate = None
        except Exception:
            funding_rate = None

        return {
            "exchange": "OKX",
            "symbol": inst_id,
            "price": price,
            "open_interest": open_interest,
            "open_interest_usd": oi_usd,
            "funding_rate": funding_rate,
        }


def ensure_csv_structure(file_path: Path) -> None:
    """Ensure data directory and updated 7-column CSV header exist for local mode."""
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
    price: Optional[float],
    open_interest: Optional[float],
    funding_rate: Optional[float],
    notes: str = "auto",
) -> None:
    """Append a single snapshot record to the local forward-test CSV."""
    price_val = "N/A"
    if price is not None:
        price_val = f"{price:.8f}".rstrip("0").rstrip(".") if price < 1 else f"{price:.4f}"

    oi_val = f"{open_interest:.2f}" if open_interest is not None else "N/A"
    fr_val = f"{funding_rate:.8f}" if funding_rate is not None else "N/A"

    with open(file_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            timestamp,
            coin_symbol,
            exchange,
            price_val,
            oi_val,
            fr_val,
            notes,
        ])


def upload_snapshot_to_s3(bucket_name: str, timestamp_utc: str, records: List[Dict[str, Any]]) -> str:
    """
    Upload run snapshot to S3 as a timestamped CSV object (Option b).
    Key format: snapshots/YYYY-MM-DD/snapshot_YYYYMMDD_HHMMSS.csv
    """
    if boto3 is None:
        raise RuntimeError("boto3 is not installed or available for S3 upload.")

    dt = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%Y%m%d_%H%M%S")
    object_key = f"snapshots/{date_str}/snapshot_{time_str}.csv"

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "coin", "exchange", "price", "open_interest", "funding_rate", "notes"])

    for r in records:
        price = r.get("price")
        price_val = (f"{price:.8f}".rstrip("0").rstrip(".") if price < 1 else f"{price:.4f}") if price is not None else "N/A"
        oi = r.get("open_interest")
        oi_val = f"{oi:.2f}" if oi is not None else "N/A"
        fr = r.get("funding_rate")
        fr_val = f"{fr:.8f}" if fr is not None else "N/A"

        writer.writerow([
            r.get("date"),
            r.get("coin"),
            r.get("exchange"),
            price_val,
            oi_val,
            fr_val,
            r.get("notes", "auto"),
        ])

    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=output.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )
    return object_key


def run_auto_logger(
    candidates: Optional[List[Dict[str, Any]]] = None,
    bucket_name: Optional[str] = None,
) -> int:
    """
    Fetch current live Price, Open Interest, and Funding Rate across Binance, Bybit, and OKX.
    If bucket_name (or LOG_BUCKET_NAME env var) is provided, uploads snapshot to S3.
    Otherwise, appends to local data/oi_funding_manual_log.csv.
    """
    target_candidates = candidates or FORWARD_TEST_CANDIDATES
    target_bucket = bucket_name or os.environ.get("LOG_BUCKET_NAME")

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("=" * 105)
    print("      📊 MULTI-EXCHANGE FORWARD-TEST AUTO-LOGGER (Binance / Bybit / OKX Public APIs)")
    print("=" * 105)
    print(f"Timestamp (UTC) : {now_utc}")
    if target_bucket:
        print(f"Destination     : Amazon S3 (Bucket: {target_bucket})")
    else:
        print(f"Destination     : Local File ({LOG_FILE_PATH})")
    print(f"Candidates ({len(target_candidates)}) : {', '.join(c['coin'] for c in target_candidates)}")
    print("=" * 105)

    binance_client = BinanceFuturesClient()
    bybit_client = BybitFuturesClient()
    okx_client = OKXFuturesClient()

    records: List[Dict[str, Any]] = []

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

            price = metrics.get("price")
            oi = metrics.get("open_interest")
            oi_usd = metrics.get("open_interest_usd")
            fr = metrics.get("funding_rate")

            # Formatting for console display
            if price is not None:
                price_str = f"${price:,.4f}" if price >= 1.0 else f"${price:.6f}"
            else:
                price_str = "N/A"

            oi_str = f"{oi:,.0f}" if oi is not None else "N/A"
            if oi_usd is not None:
                oi_usd_str = f"${oi_usd / 1e6:.2f}M" if oi_usd >= 1e6 else f"${oi_usd:,.0f}"
            else:
                oi_usd_str = "N/A"

            fr_str = f"{fr * 100.0:+.4f}%" if fr is not None else "N/A"

            print(f"{coin:<8} {ex_name:<10} {sym:<18} {price_str:<14} {oi_str:<18} {oi_usd_str:<14} {fr_str:<14}")

            record = {
                "date": now_utc,
                "coin": coin,
                "exchange": ex_name,
                "price": price,
                "open_interest": oi,
                "funding_rate": fr,
                "notes": "auto",
            }
            records.append(record)

    print("-" * 105)

    if target_bucket:
        try:
            s3_key = upload_snapshot_to_s3(target_bucket, now_utc, records)
            print(f"[+] Successfully uploaded {len(records)} record(s) to s3://{target_bucket}/{s3_key}\n")
        except Exception as e:
            print(f"[!] Error uploading snapshot to S3: {e}")
            raise
    else:
        ensure_csv_structure(LOG_FILE_PATH)
        for r in records:
            append_log_row(
                file_path=LOG_FILE_PATH,
                timestamp=r["date"],
                coin_symbol=r["coin"],
                exchange=r["exchange"],
                price=r["price"],
                open_interest=r["open_interest"],
                funding_rate=r["funding_rate"],
                notes="auto",
            )
        print(f"[+] Successfully logged {len(records)} snapshot record(s) to {LOG_FILE_PATH.name}.\n")

    return len(records)


def lambda_handler(event: Optional[Dict[str, Any]] = None, context: Any = None) -> Dict[str, Any]:
    """
    AWS Lambda entry point for scheduled EventBridge execution.
    """
    logger.info("Lambda invocation started via EventBridge event: %s", json.dumps(event or {}))
    logged_count = run_auto_logger()
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"Successfully logged {logged_count} derivative snapshot records to S3.",
            "records_count": logged_count,
        }),
    }


if __name__ == "__main__":
    run_auto_logger()
