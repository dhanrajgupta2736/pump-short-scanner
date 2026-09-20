# Changelog

A running, plain-language history of all changes made to the Pump Short Scanner project, with the newest entries listed first.

---

## [2026-09-20] - Feature: 6-Hourly Rank Tracker Schedule & Intra-Day Snapshot Diffing

### Changed
- **6-Hourly Execution Cadence (`pump-short-scanner-rank-tracker`)**:
  - Shifted Job 1 EventBridge trigger (`pump-short-scanner-rank-tracker-schedule`) from daily (`rate(1 day)`) to every 6 hours (`rate(6 hours)`).
  - Tightly hedges against rapid sub-24h flash pumps (e.g. `RAVE` and `CYS` historical pump windows) which could enter and exit the radar within a single day.
- **Dynamic Prior Snapshot Diffing (`scanner/rank_tracker.py`)**:
  - Replaced date-based snapshots (`rank_history/YYYY-MM-DD.json`) with run-timestamped snapshots (`rank_history/YYYY-MM-DD_HHMMSS.json`).
  - Updated snapshot comparison logic to diff against the **most recent prior snapshot** in S3 (whether 6 hours ago today or from yesterday evening), preventing false comparisons against stale baselines and capturing intra-day entrants.
- **Rate-Limit & Cost Analysis**:
  - Confirmed 4 runs/day = 16 CoinGecko calls/day (~480/month), well within CoinGecko's Demo API 10,000 monthly quota.
  - Confirmed Lambda compute consumes ~480 GB-seconds/month out of 400,000 free tier GB-seconds (0.12% utilization, $0.00/month).

### Added
- **Top 1000 Discovery Scope (`scanner/rank_tracker.py` - Job 1)**:
  - Widened daily rank tracking from Top 200 to Top 1000 by reusing `CoinGeckoClient` 4-page pagination (4 pages x 250 coins).
  - Informed by historical trade analysis (`DEXE`, `RAVE`, `LAB`, `BILL`, `BEAT`, `VELVET`, `CYS`) which showed that while all 8 historical coins reached Top 200 valuations during peak pump, 7 crashed by 85% to 99% into the Rank 350 to 800 zone post-pump.
  - Mitigates flash pump miss risks for fast moves (<24h to 48h) by tracking coins across the entire Top 1000.
  - Increased Lambda timeout on `pump-short-scanner-rank-tracker` from 120s to 300s (5 minutes) to comfortably accommodate CoinGecko 429 backoff retries.
  - Verified live AWS execution (1,000 coins fetched and stored to `rank_history/2026-09-20.json` in 31.5s).

---

## [2026-09-20] - Feature: Dynamic Top-200 Rank Tracker (Job 1) & S3 Watchlist Integration (Job 2)

### Added
- **Daily Top-200 Rank Tracker (`scanner/rank_tracker.py` - Job 1)**:
  - Fetches CoinGecko Top 200 coins daily and records dated snapshots in `s3://pump-short-scanner-logs-dhanraj-7938/rank_history/YYYY-MM-DD.json`.
  - Compares today's Top 200 against prior day's baseline to identify newly entered coins.
  - Automatically screens new entrants against the 4 pump-short filter criteria (`market_cap >= $500M`, `fdv >= $1B`, and `10x ATH` or `5x 30d`).
  - Automatically appends matching candidates to `s3://pump-short-scanner-logs-dhanraj-7938/active_watchlist.json`.
  - Deployed as AWS Lambda `pump-short-scanner-rank-tracker` triggered daily via EventBridge (`rate(1 day)`).
- **Dynamic Watchlist Loading & Safeguard (`scanner/auto_logger.py` - Job 2)**:
  - Upgraded derivative logger to pull candidates dynamically from `active_watchlist.json` in S3 with local fallback.
  - Seeded initial watchlist with `BOME`, `BTW`, and `AKE` (manually removed `DOGE`).
  - Added safe processing cap ($N = 15$) to prevent Lambda 60s timeout if the watchlist grows.
  - Updated IAM role permissions to include `s3:GetObject` and `s3:ListBucket`.

---

## [2026-09-20] - Feature & Analysis: Forward-Test Analysis & AKE Candidate Addition

### Added
- **New Forward-Test Candidate (`AKE`)**:
  - Added `AKE` (`AKEUSDT` on Binance/Bybit, `AKE-USDT-SWAP` on OKX) to `FORWARD_TEST_CANDIDATES` in `scanner/auto_logger.py`.
  - Packaged and redeployed updated function code to AWS Lambda (`pump-short-scanner-auto-logger`).
  - Verified live execution logging 11 records per run across Binance, Bybit, and OKX into Amazon S3.
- **Consolidated Forward-Test Dataset & Visualization**:
  - Downloaded and consolidated 173 continuous 4-hour snapshots (Aug 23 - Sep 20, 2026) into `data/consolidated_forward_test_log.csv`.
  - Generated visual trajectory charts for `BTW`, `BOME`, and `DOGE` in `data/`.

---

## [2026-08-25] - Analysis: Binance Funding Rate Mechanism & Audit Verification

### Investigated
- **Binance Constant Funding Rate Audit (`scanner/auto_logger.py`)**:
  - Investigated why Binance funding rate appeared constant for `BOME` (`+0.0050%`) and `DOGE` (`+0.0100%`) across 48 hours while Bybit and OKX showed floating values.
  - **Technical Findings**:
    1. **Endpoint Called**: The client queries `GET /fapi/v1/premiumIndex?symbol=SYMBOL` and reads `lastFundingRate`.
    2. **Binance Clamp Mechanism**: Binance applies a baseline interest rate of `0.0100%` per 8 hours (or `0.0050%` for 4-hour contracts like BOME). Under Binance's funding formula, whenever the basis spread between the perpetual contract and spot index is within $\pm 0.05\%$, the funding rate mathematically defaults exactly to the baseline interest rate (`0.0100%` for DOGE, `0.0050%` for BOME).
    3. **Historical Verification**: Historical settlements from `GET /fapi/v1/fundingRate` confirm Binance officially settled at `0.00010000` (+0.0100%) for all consecutive intervals for DOGE.
    4. **Pumped Assets Divergence**: For high-volatility/pumped assets like `BTWUSDT`, Binance's funding rate actively fluctuated (`+0.0187%` $\rightarrow$ `+0.0250%` $\rightarrow$ `+0.0397%` $\rightarrow$ `+0.0374%`), proving the parser and live API updates are fully functional.

---

## [2026-08-23] - Fix: Standardize OKX Open Interest Units to Base Currency (`oiCcy`)

### Fixed
- **OKX Open Interest Contract Multiplier / Unit Mismatch**:
  - Updated `OKXFuturesClient` to use `oiCcy` for base-currency `open_interest` and `oiUsd` for USD notional value.
  - Verified with a live Lambda invocation that OKX Open Interest now aligns across all venues (e.g. BOME: Binance 10.56B, Bybit 3.37B, OKX 3.27B).

---

## [2026-08-23] - Infrastructure: Serverless 24/7 AWS Deployment (Lambda + S3 + EventBridge)

### Added
- **AWS Lambda Serverless Execution (`scanner/auto_logger.py`)**:
  - Implemented `lambda_handler(event, context)` and direct Amazon S3 snapshot uploading via `boto3`.
- **Private S3 Storage (`pump-short-scanner-logs-dhanraj-7938`)**:
  - Created a dedicated, private S3 bucket with full Block Public Access enabled in `ap-south-1`.
- **Automated EventBridge Scheduling (`rate(4 hours)`)**:
  - Created EventBridge rule `pump-short-scanner-auto-logger-schedule` triggering Lambda every 4 hours.

---

## [2026-08-23] - Fix: Log "N/A" for Failed API Metrics Instead of Defaulting to 0.0 (`scanner/auto_logger.py`)

### Fixed
- **Distinguish API Failures from Zero Readings**:
  - Updated `BinanceFuturesClient`, `BybitFuturesClient`, and `OKXFuturesClient` to return `None` upon fetch errors and write `"N/A"` in CSV.

---

## [2026-08-23] - Feature: Multi-Exchange Price, OI & Funding Rate Logger (Binance, Bybit, OKX)

### Added
- **Multi-Exchange Auto-Logger (`scanner/auto_logger.py`)**: Upgraded the automated logger to query direct public APIs across **Binance USDT-M Futures**, **Bybit Linear Futures (v5)**, and **OKX Perpetual Swaps (v5)** without requiring API keys.

---

## [2026-08-23] - Scope Realignment: CoinGecko Top 1000 Scanner & Manual Forward-Testing

### Added
- **Manual Forward-Test Log (`data/oi_funding_manual_log.csv`)**: Created a clean CSV template for daily forward-test tracking.
- **CoinGecko Top 1000 Pagination (`scanner/coingecko_client.py`)**: Added `fetch_top_market_coins()` to paginate through CoinGecko's free public `/coins/markets` endpoint.
