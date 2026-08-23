# Project Structure

This document provides a comprehensive overview of the `pump-short-scanner` repository layout, explaining the purpose and responsibility of every directory and file. It is updated whenever the project structure changes.

```
pump-short-scanner/
├── .env.example                  # Environment variables template (future Telegram bot token)
├── .gitignore                    # Files and folders excluded from Git version control
├── CHANGELOG.md                  # Running chronological log of all changes and rationale
├── PROJECT_STRUCTURE.md          # Overview of codebase layout and file responsibilities
├── README.md                     # High-level project documentation, setup, and forward-test guide
├── config.py                     # Central configuration constants, thresholds, and target lists
├── main.py                       # CLI entry point: scans Top 1000 coins and displays filtered candidates
├── requirements.txt              # Python package dependencies (requests)
├── data/
│   ├── oi_funding_manual_log.csv # Forward-test log for daily price/OI/funding tracking
│   └── oi_log.csv                # Legacy placeholder CSV
└── scanner/
    ├── __init__.py               # Package initializer exporting client, filter, and logger utilities
    ├── auto_logger.py            # Automated snapshot logger for Binance USDT-M Futures Price/OI/Funding
    ├── coingecko_client.py       # CoinGecko client with Top 1000 pagination & rate-limit handling
    └── filters.py                # 4-criteria evaluation engine and candidate filter functions
```

---

## File & Directory Reference

### Root Directory
- **`README.md`**: Project mission, 4-criteria rules, scanner execution, and auto-logger guide.
- **`PROJECT_STRUCTURE.md`**: This document, outlining the structural blueprint of the project.
- **`CHANGELOG.md`**: Plain-language dated history of project features, updates, and fixes.
- **`config.py`**: Declares user-configurable thresholds:
  - `MIN_MARKET_CAP_USD`: Minimum market cap required ($500M default).
  - `MIN_FDV_USD`: Minimum fully diluted valuation required ($1B default).
  - `ATH_MULTIPLE_THRESHOLD`: Threshold for multiple from low/base ($10\times$ default).
  - `THIRTY_DAY_MULTIPLE_THRESHOLD`: Threshold for 30-day pump multiple ($5\times$ / +400% default).
  - `MIN_GAINERS_VOLUME_USD`: 24h trading volume floor for Top Gainers list ($1M default).
  - `COINGECKO_BASE_URL` & `REQUEST_TIMEOUT_SECONDS`: Connection settings.
- **`main.py`**: Orchestrates data fetching across CoinGecko's Top 1000 universe, evaluates each asset against `scanner.filters`, and renders a console summary table of matching coins and liquid top 30-day gainers.
- **`requirements.txt`**: Minimal project dependencies (`requests`).
- **`.env.example`**: Template for future secrets (Telegram Bot token placeholder).
- **`.gitignore`**: Specifies untracked files (virtual environments, cache, sensitive configs).

### `scanner/` Directory
- **`__init__.py`**: Exposes core classes and functions (`BinanceFuturesClient`, `CoinGeckoClient`, `evaluate_coin`, `filter_coins`, `run_auto_logger`).
- **`auto_logger.py`**: Standalone tool that queries public Binance USDT-M Perpetual Futures REST endpoints for Price, Funding Rate, and Open Interest, displaying a summary table and appending snapshot rows to `data/oi_funding_manual_log.csv`.
- **`coingecko_client.py`**: Interfaces with the CoinGecko public free API (`/coins/markets`) without requiring an API key. Handles paginated fetching (4 pages $\times$ 250 coins = Top 1000), polite rate-limiting pauses, retry logic, and data normalization (prices, market caps, FDVs, ATH, ATL, 30d change, 24h volume). Safely returns `None` for missing data.
- **`filters.py`**: Pure logic module implementing the 4-criteria filter rule:
  $$\text{Match} = (\text{ATH Multiple} \ge T_{\text{ath}} \lor \text{30d Multiple} \ge T_{\text{30d}}) \land \text{Market Cap} \ge T_{\text{mcap}} \land \text{FDV} \ge T_{\text{fdv}}$$

### `data/` Directory
- **`oi_funding_manual_log.csv`**: Forward-testing CSV log with header `date,coin,price,open_interest,funding_rate,notes`. Populated by both `scanner/auto_logger.py` and manual entries during the validation phase.
- **`oi_log.csv`**: Legacy data placeholder.
