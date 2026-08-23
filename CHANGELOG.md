# Changelog

A running, plain-language history of all changes made to the Pump Short Scanner project, with the newest entries listed first.

---

## [2026-08-23] - Feature: Automated Binance Futures Price, OI & Funding Rate Logger (`scanner/auto_logger.py`)

### Added
- **Automated Snapshot Logger (`scanner/auto_logger.py`)**: Built a standalone script to fetch live Price, Funding Rate, and Open Interest directly from Binance USDT-M Perpetual Futures public endpoints (no API key required) and append records to `data/oi_funding_manual_log.csv`.
- **Graceful Unlisted Symbol Handling**: Automatically detects and skips coins not listed on Binance Futures with a clear warning without crashing.
- **Unified CSV Logging**: Appends rows matching the existing CSV header (`date,coin,price,open_interest,funding_rate,notes`), using `"auto"` in the notes column to distinguish automated runs from manual entries.
- **Data Retention Limitation Notice**: Documented that Binance's free public Open Interest API only retains 30 days of historical data, meaning the script records live forward snapshots going forward and cannot backfill older historical OI.

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
  - *Note*: Under heavy public API congestion, the scanner gracefully continues with partial data (e.g. 750 or 1000 coins) without crashing.

---

## [2026-08-23] - Fix: Gate ATH Multiple on Active ATH Proximity to Exclude Legacy Large-Caps

### Fixed
- **Resolved False Positives in 4-Criteria Filter**: Diagnosed why stable large-caps like XRP, Chainlink, Cardano, and Zcash previously appeared in the "Meeting All 4 Criteria" table despite only having 1.35x–1.65x 30-day moves:
  - The 30-day percentage math was correct (e.g. XRP +35.2% $\rightarrow$ 1.35x, evaluating to `thirty_day_multiple_ok = False`).
  - However, the second branch of the `OR` logic (`ath_multiple >= 10`) was previously calculated as `current_price / atl` against ancient historical all-time lows from 2014–2020.
  - Because mature coins like XRP (554x from 2014 ATL), Zcash (50x), Chainlink (76x), and Cardano (11.6x) are historically above their launch lows, `ath_multiple_ok` returned `True`, allowing them to bypass the 30-day 5x pump requirement via the `OR` expression.
- **Gated ATH Multiple on Active ATH Proximity (`scanner/coingecko_client.py`)**:
  - `ath_multiple` is now only calculated if the coin is actively trading near its All-Time High (`ath_change_percentage >= -20%`).
  - For coins trading well below their historical ATH (e.g. XRP down -59%, ADA down -93%, ZEC down -80%, LINK down -78%), `ath_multiple` is set to `0.0`, ensuring they cannot qualify as active parabolic pump candidates.

---

## [2026-08-23] - Scope Realignment: CoinGecko Top 1000 Scanner & Manual Forward-Testing

### Added
- **Manual Forward-Test Log (`data/oi_funding_manual_log.csv`)**: Created a clean CSV template (`date,coin,price,open_interest,funding_rate,notes`) for manual daily recording of price, Open Interest, and funding rates on 2–3 selected candidates over a 1–2 week validation window.
- **CoinGecko Top 1000 Pagination (`scanner/coingecko_client.py`)**: Added `fetch_top_market_coins()` to paginate through CoinGecko's free public `/coins/markets` endpoint (4 pages of 250 coins = Top 1000 by market cap) with built-in rate-limit delays and retry handling.

### Changed
- **Scanner Entry Point (`main.py`)**: Upgraded `main.py` from scanning a small hardcoded list to scanning the full Top 1000 coin universe, applying the 4-criteria filter, and outputting both matching short candidates and top 30-day gainers for forward-test selection.
- **Blueprint Plan Status (`implementation_plan.md`)**: Marked the automated architecture blueprint as **PAUSED** to prevent premature engineering. Documented the rationale: the OI/funding crash hypothesis is unvalidated and must be tested manually via forward-testing before building automated alert bots or derivatives ingestion engines.
- **Documentation (`README.md`, `PROJECT_STRUCTURE.md`)**: Updated documentation to reflect the manual forward-testing phase and codebase structure.

---

## [2026-08-23] - Initial Project Skeleton & 4-Criteria Filter Setup

### Added
- **Project Structure & Git Setup**: Initialized Git repository and connected it to the public GitHub remote repository (`dhanrajgupta2736/pump-short-scanner`). Created initial `.gitignore` and `README.md`.
- **Configuration Module (`config.py`)**: Defined baseline thresholds for short scanning:
  - Minimum Market Cap: $500,000,000
  - Minimum Fully Diluted Valuation (FDV): $1,000,000,000
  - ATH Multiple Threshold: 10x
  - 30-Day Multiple Threshold: 5x (+400% gain)
- **CoinGecko Public Client (`scanner/coingecko_client.py`)**: Built client using the free CoinGecko public API (no API key required) to fetch real-time price, all-time highs/lows, 30-day percentage changes, market cap, and FDV.
- **Filtering Logic Engine (`scanner/filters.py`)**: Implemented evaluation function checking whether an asset passes the 4 criteria: `(ATH Multiple >= 10x OR 30d Multiple >= 5x) AND Market Cap >= $500M AND FDV >= $1B`.
- **CLI Runner (`main.py`)**: Built initial console scanner displaying a clean summary table of scanned assets, key metrics, and highlighted short candidates.
- **Data Placeholder (`data/oi_log.csv`)**: Added a CSV log structure for manual tracking of Open Interest, funding rates, and experimental notes.
