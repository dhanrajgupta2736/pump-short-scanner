# Changelog

A running, plain-language history of all changes made to the Pump Short Scanner project, with the newest entries listed first.

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
