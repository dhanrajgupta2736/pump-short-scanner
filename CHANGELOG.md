# Changelog

A running, plain-language history of all changes made to the Pump Short Scanner project, with the newest entries listed first.

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
