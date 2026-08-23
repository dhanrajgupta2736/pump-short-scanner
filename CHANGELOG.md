# Changelog

A running, plain-language history of all changes made to the Pump Short Scanner project, with the newest entries listed first.

---

## [2026-08-23] - Fix: Log "N/A" for Failed API Metrics Instead of Defaulting to 0.0 (`scanner/auto_logger.py`)

### Fixed
- **Distinguish API Failures from Zero Readings**:
  - Previously, if an exchange API call failed for `funding_rate` or `open_interest`, the clients silently defaulted to `0.0`. This made network/API errors indistinguishable from legitimate market readings of 0% funding rate or zero open interest.
  - Updated `BinanceFuturesClient`, `BybitFuturesClient`, and `OKXFuturesClient` to return `None` upon fetch errors.
  - Updated CSV logger and console output to write `"N/A"` for failed metrics so historical data analysis can reliably distinguish true zero values from missing API data.

---

## [2026-08-23] - Feature: Multi-Exchange Price, OI & Funding Rate Logger (Binance, Bybit, OKX)

### Added
- **Multi-Exchange Auto-Logger (`scanner/auto_logger.py`)**: Upgraded the automated logger to query direct public APIs across **Binance USDT-M Futures**, **Bybit Linear Futures (v5)**, and **OKX Perpetual Swaps (v5)** without requiring API keys or authentication.
- **Direct Exchange APIs Design Decision**: Deliberately chose direct exchange endpoints over Coinglass. Coinglass charges a monthly subscription (~$29/mo minimum) for API access, whereas Binance, Bybit, and OKX provide high-resolution raw OI and funding rate data for free. Coinglass's primary value-add is derived analytics (e.g. liquidation heatmaps), which is not needed for raw forward-testing data collection.
- **Cross-Exchange Comparison in CSV (`data/oi_funding_manual_log.csv`)**: Updated CSV schema with an `exchange` column (`date,coin,exchange,price,open_interest,funding_rate,notes`) to record and compare OI and funding rate metrics across exchanges for the same asset.
- **Resilient Per-Exchange Error Handling**: If an asset is unlisted or an exchange API is regionally restricted / times out, the logger logs a warning and skips that specific exchange without crashing the run.

---

## [2026-08-23] - Improvements: True ATH Multiples, Volume Floor on Gainers & API Rate-Limit Handling

### Fixed
- **Bitway (BTW) ATH Multiple Display**: Corrected `ath_multiple` computation so that coins with valid all-time low data display their genuine multiple (e.g. Bitway `BTW` now correctly displays `45.49x` rather than `0.0x`).
- **Safe Null/Missing ATH Handling (`scanner/coingecko_client.py` & `scanner/filters.py`)**:
  - Missing or null `ath`/`atl` values now explicitly return `None` (formatted as `N/A` in tables) rather than defaulting to `0.0`.
  - In `filters.py`, missing ATH data safely evaluates to `ath_multiple_ok = False`, preventing false positives while allowing the coin to qualify on the 30-day multiple alone if eligible.

### Added
- **Liquidity Floor for 30-Day Gainers (`config.py` & `main.py`)**:
  - Added `MIN_GAINERS_VOLUME_USD = 1_000_000` ($1M USD 24h trading volume floor).
  - Excludes thin/illiquid micro-caps with artificial percentage spikes (e.g. `$ONION`, `SFTMX`) from the Top 15 Gainers list.
  - Added a `24h Volume` column to the Top Gainers table for instant liquidity assessment.
- **Enhanced Rate-Limit Backoff (`scanner/coingecko_client.py`)**:
  - Increased base inter-page delay to 2.5s and configured exponential retry backoff (20s/40s/60s) for CoinGecko free tier HTTP 429 responses.

---

## [2026-08-23] - Fix: Gate ATH Multiple on Active ATH Proximity to Exclude Legacy Large-Caps

### Fixed
- **Resolved False Positives in 4-Criteria Filter**: Diagnosed why stable large-caps like XRP, Chainlink, Cardano, and Zcash previously appeared in the "Meeting All 4 Criteria" table despite only having 1.35x–1.65x 30-day moves.
- **Gated ATH Multiple on Active ATH Proximity (`scanner/coingecko_client.py`)**: `ath_multiple` is now only calculated if the coin is actively trading near its All-Time High (`ath_change_percentage >= -20%`).

---

## [2026-08-23] - Scope Realignment: CoinGecko Top 1000 Scanner & Manual Forward-Testing

### Added
- **Manual Forward-Test Log (`data/oi_funding_manual_log.csv`)**: Created a clean CSV template (`date,coin,price,open_interest,funding_rate,notes`) for daily forward-test tracking.
- **CoinGecko Top 1000 Pagination (`scanner/coingecko_client.py`)**: Added `fetch_top_market_coins()` to paginate through CoinGecko's free public `/coins/markets` endpoint.

---

## [2026-08-23] - Initial Project Skeleton & 4-Criteria Filter Setup

### Added
- **Project Structure & Git Setup**: Initialized Git repository and connected to GitHub (`dhanrajgupta2736/pump-short-scanner`).
- **Configuration Module (`config.py`)**: Defined baseline thresholds for short scanning.
- **CoinGecko Public Client & Filter Engine (`scanner/coingecko_client.py`, `scanner/filters.py`)**: Implemented 4-criteria filter.
