# Changelog

A running, plain-language history of all changes made to the Pump Short Scanner project, with the newest entries listed first.

---

## [2026-08-23] - Initial Project Skeleton & 4-Criteria Filter Setup

### Added
- **Project Structure & Git Setup**: Initialized Git repository and connected it to the public GitHub remote repository (`dhanrajgupta2736/pump-short-scanner`). Created initial `.gitignore` and `README.md`.
- **Configuration Module (`config.py`)**: Defined baseline thresholds for short scanning:
  - Minimum Market Cap: $500,000,000
  - Minimum Fully Diluted Valuation (FDV): $1,000,000,000
  - ATH Multiple Threshold: 10x
  - 30-Day Multiple Threshold: 5x (+400% gain)
  - Hardcoded test list of top liquid crypto assets for initial verification.
- **CoinGecko Public Client (`scanner/coingecko_client.py`)**: Built client using the free CoinGecko public API (no API key required) to fetch real-time price, all-time highs/lows, 30-day percentage changes, market cap, and FDV.
- **Filtering Logic Engine (`scanner/filters.py`)**: Implemented evaluation function checking whether an asset passes the 4 criteria: `(ATH Multiple >= 10x OR 30d Multiple >= 5x) AND Market Cap >= $500M AND FDV >= $1B`.
- **CLI Runner (`main.py`)**: Built console scanner displaying a clean summary table of scanned assets, key metrics, and highlighted short candidates.
- **Data Placeholder (`data/oi_log.csv`)**: Added a CSV log structure for manual tracking of Open Interest, funding rates, and experimental notes.
- **Documentation**:
  - `README.md`: Explaining project purpose, installation, execution, and research status.
  - `PROJECT_STRUCTURE.md`: Documenting every file and folder's responsibility.
  - `requirements.txt` & `.env.example`: Listing dependencies and future Telegram bot configuration.
