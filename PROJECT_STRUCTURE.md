# Project Structure

This document provides a comprehensive overview of the `pump-short-scanner` repository layout, explaining the purpose and responsibility of every directory and file. It is maintained and updated whenever the project structure changes.

```
pump-short-scanner/
├── .env.example            # Environment variables template (API keys, bot tokens)
├── .gitignore              # Files and folders excluded from Git version control
├── CHANGELOG.md            # Running chronological log of all changes and rationale
├── PROJECT_STRUCTURE.md    # Overview of codebase layout and file responsibilities
├── README.md               # High-level project documentation, setup, and usage guide
├── config.py               # Central configuration constants, thresholds, and target lists
├── main.py                 # CLI entry point: executes scanner and displays results
├── requirements.txt        # Python package dependencies
├── data/
│   └── oi_log.csv          # Placeholder CSV for manual Open Interest / funding rate logging
└── scanner/
    ├── __init__.py         # Package initializer exporting client and filter utilities
    ├── coingecko_client.py # CoinGecko public API client for fetching & normalizing market data
    └── filters.py          # 4-criteria evaluation engine and candidate filter functions
```

---

## File & Directory Reference

### Root Directory
- **`README.md`**: Project mission, architecture overview, installation instructions, and current research roadmap.
- **`PROJECT_STRUCTURE.md`**: This document, outlining the structural blueprint of the project.
- **`CHANGELOG.md`**: Plain-language dated history of project features, updates, and fixes.
- **`config.py`**: Declares user-configurable thresholds:
  - `MIN_MARKET_CAP_USD`: Minimum market cap required ($500M default).
  - `MIN_FDV_USD`: Minimum fully diluted valuation required ($1B default).
  - `ATH_MULTIPLE_THRESHOLD`: Threshold for multiple from low/base ($10\times$ default).
  - `THIRTY_DAY_MULTIPLE_THRESHOLD`: Threshold for 30-day pump multiple ($5\times$ / +400% default).
  - `TEST_COIN_IDS`: Initial sample coin IDs scanned for verification.
- **`main.py`**: Orchestrates data fetching via `CoinGeckoClient`, evaluates each asset against `scanner.filters`, and renders a console summary table.
- **`requirements.txt`**: Minimal project dependencies (`requests`).
- **`.env.example`**: Template for secrets and environment variables (e.g. Telegram Bot tokens).
- **`.gitignore`**: Specifies untracked files (virtual environments, cache, sensitive configs).

### `scanner/` Directory
- **`__init__.py`**: Exposes core classes and functions (`CoinGeckoClient`, `evaluate_coin`, `filter_coins`).
- **`coingecko_client.py`**: Interfaces with the CoinGecko public free API (`/coins/markets`) without requiring an API key. Handles batch fetching, network retries, and data normalization (prices, market caps, FDVs, ATH, ATL, 30d change).
- **`filters.py`**: Pure logic module implementing the 4-criteria filter rule:
  $$\text{Match} = (\text{ATH Multiple} \ge T_{\text{ath}} \lor \text{30d Multiple} \ge T_{\text{30d}}) \land \text{Market Cap} \ge T_{\text{mcap}} \land \text{FDV} \ge T_{\text{fdv}}$$

### `data/` Directory
- **`oi_log.csv`**: Experimental data log for manually or programmatically recording Open Interest (OI), funding rates, and notes on detected pump candidates.
