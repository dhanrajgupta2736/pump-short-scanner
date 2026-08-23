# Changelog

A running, plain-language history of all changes made to the Pump Short Scanner project, with the newest entries listed first.

---

## [2026-08-23] - Fix: Standardize OKX Open Interest Units to Base Currency (`oiCcy`)

### Fixed
- **OKX Open Interest Contract Multiplier / Unit Mismatch**:
  - Diagnosed why OKX Open Interest previously appeared ~1000x smaller than Binance/Bybit (e.g. OKX reported `3,384,522` for BOME while Binance reported `10,671,160,756` and Bybit reported `3,395,543,800`).
  - **Findings from OKX API Spec**:
    - OKX's `/api/v5/public/open-interest` returns `oi` in **contracts** (where 1 contract = `ctVal` base coins, e.g. 1 contract = 1,000 BOME).
    - OKX *also* returns `oiCcy`, which is the total Open Interest denominated in **underlying base-currency units** (e.g. `3,274,263,000` BOME coins), matching Binance and Bybit.
    - Previously, `OKXFuturesClient` read `oi` (contracts) for Open Interest and mistakenly read `oiCcy` as USD.
  - **Resolution (`scanner/auto_logger.py`)**:
    - Updated `OKXFuturesClient` to use `oiCcy` for base-currency `open_interest` and `oiUsd` for USD notional value.
    - Verified with a live Lambda invocation that OKX Open Interest now aligns across all venues (e.g. BOME: Binance 10.56B, Bybit 3.37B, OKX 3.27B).
    - Redeployed Lambda function `pump-short-scanner-auto-logger` on AWS in `ap-south-1`.

---

## [2026-08-23] - Infrastructure: Serverless 24/7 AWS Deployment (Lambda + S3 + EventBridge)

### Added
- **AWS Lambda Serverless Execution (`scanner/auto_logger.py`)**:
  - Implemented `lambda_handler(event, context)` and direct Amazon S3 snapshot uploading via `boto3`.
  - Maintains full backwards-compatibility for local execution (logs to local CSV when `LOG_BUCKET_NAME` is unset).
- **Private S3 Storage (`pump-short-scanner-logs-dhanraj-7938`)**:
  - Created a dedicated, private S3 bucket with full Block Public Access enabled in `ap-south-1`.
  - Snapshots are written as timestamped CSV objects (`snapshots/YYYY-MM-DD/snapshot_YYYYMMDD_HHMMSS.csv`) avoiding write collisions.
- **Automated EventBridge Scheduling (`rate(4 hours)`)**:
  - Created EventBridge rule `pump-short-scanner-auto-logger-schedule` triggering Lambda every 4 hours.
  - Granted least-privilege invocation permissions.
- **Least-Privilege IAM Role (`pump-short-scanner-lambda-role`)**:
  - Scoped strictly to `s3:PutObject` on the dedicated S3 bucket and CloudWatch Logs basic execution.
- **Verified 24/7 Pipeline**:
  - Manually invoked Lambda via AWS CLI and verified live derivative snapshot generation across Binance, Bybit, and OKX with zero errors.

---

## [2026-08-23] - Fix: Log "N/A" for Failed API Metrics Instead of Defaulting to 0.0 (`scanner/auto_logger.py`)

### Fixed
- **Distinguish API Failures from Zero Readings**:
  - Updated `BinanceFuturesClient`, `BybitFuturesClient`, and `OKXFuturesClient` to return `None` upon fetch errors.
  - Updated CSV logger and console output to write `"N/A"` for failed metrics so historical data analysis can reliably distinguish true zero values from missing API data.

---

## [2026-08-23] - Feature: Multi-Exchange Price, OI & Funding Rate Logger (Binance, Bybit, OKX)

### Added
- **Multi-Exchange Auto-Logger (`scanner/auto_logger.py`)**: Upgraded the automated logger to query direct public APIs across **Binance USDT-M Futures**, **Bybit Linear Futures (v5)**, and **OKX Perpetual Swaps (v5)** without requiring API keys or authentication.
- **Direct Exchange APIs Design Decision**: Deliberately chose direct exchange endpoints over Coinglass. Coinglass charges a monthly subscription (~$29/mo minimum) for API access, whereas Binance, Bybit, and OKX provide high-resolution raw OI and funding rate data for free.
- **Cross-Exchange Comparison in CSV (`data/oi_funding_manual_log.csv`)**: Updated CSV schema with an `exchange` column (`date,coin,exchange,price,open_interest,funding_rate,notes`) to record and compare OI and funding rate metrics across exchanges for the same asset.

---

## [2026-08-23] - Improvements: True ATH Multiples, Volume Floor on Gainers & API Rate-Limit Handling

### Fixed
- **Bitway (BTW) ATH Multiple Display**: Corrected `ath_multiple` computation so that coins with valid all-time low data display their genuine multiple (e.g. Bitway `BTW` now correctly displays `45.49x` rather than `0.0x`).
- **Safe Null/Missing ATH Handling (`scanner/coingecko_client.py` & `scanner/filters.py`)**:
  - Missing or null `ath`/`atl` values now explicitly return `None` (formatted as `N/A` in tables) rather than defaulting to `0.0`.

### Added
- **Liquidity Floor for 30-Day Gainers (`config.py` & `main.py`)**: Added `MIN_GAINERS_VOLUME_USD = 1_000_000` ($1M USD 24h trading volume floor).

---

## [2026-08-23] - Fix: Gate ATH Multiple on Active ATH Proximity to Exclude Legacy Large-Caps

### Fixed
- **Resolved False Positives in 4-Criteria Filter**: Diagnosed why stable large-caps like XRP, Chainlink, Cardano, and Zcash previously appeared in the "Meeting All 4 Criteria" table despite only having 1.35x–1.65x 30-day moves.
- **Gated ATH Multiple on Active ATH Proximity (`scanner/coingecko_client.py`)**: `ath_multiple` is now only calculated if the coin is actively trading near its All-Time High (`ath_change_percentage >= -20%`).

---

## [2026-08-23] - Scope Realignment: CoinGecko Top 1000 Scanner & Manual Forward-Testing

### Added
- **Manual Forward-Test Log (`data/oi_funding_manual_log.csv`)**: Created a clean CSV template for daily forward-test tracking.
- **CoinGecko Top 1000 Pagination (`scanner/coingecko_client.py`)**: Added `fetch_top_market_coins()` to paginate through CoinGecko's free public `/coins/markets` endpoint.

---

## [2026-08-23] - Initial Project Skeleton & 4-Criteria Filter Setup

### Added
- **Project Structure & Git Setup**: Initialized Git repository and connected to GitHub (`dhanrajgupta2736/pump-short-scanner`).
- **Configuration Module (`config.py`)**: Defined baseline thresholds for short scanning.
