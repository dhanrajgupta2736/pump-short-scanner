"""Configuration settings and filter thresholds for Pump Short Scanner."""

# 4 Filter Criteria Constants
MIN_MARKET_CAP_USD = 500_000_000      # $500 Million USD minimum market cap
MIN_FDV_USD = 1_000_000_000          # $1 Billion USD minimum fully diluted valuation
ATH_MULTIPLE_THRESHOLD = 10          # 10x multiple from base/ATL to ATH or current price
THIRTY_DAY_MULTIPLE_THRESHOLD = 5    # 5x multiple over the last 30 days (+400% or more)

# Liquidity sanity filter for Top 30-Day Gainers list
MIN_GAINERS_VOLUME_USD = 1_000_000   # $1 Million USD minimum 24h volume floor

# CoinGecko API Configuration
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
REQUEST_TIMEOUT_SECONDS = 15

# Initial test list of coins for scanner validation
TEST_COIN_IDS = [
    "bitcoin",
    "ethereum",
    "solana",
    "dogecoin",
    "pepe",
    "bittensor",
    "sui",
    "worldcoin-wld",
]
