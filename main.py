"""Main entry point for Pump Short Scanner."""

import sys
import config
from scanner.coingecko_client import CoinGeckoClient
from scanner.filters import evaluate_coin, filter_coins

# Ensure UTF-8 output encoding if supported by stream
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def format_currency(value: float) -> str:
    """Format large numbers into human-readable currency strings ($M, $B)."""
    if value is None:
        return "N/A"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value / 1_000:.2f}K"
    elif value > 0:
        return f"${value:.4f}"
    return "$0.00"


def format_price(price: float) -> str:
    """Format price with appropriate decimal places."""
    if price is None:
        return "N/A"
    if price >= 1.0:
        return f"${price:,.2f}"
    elif price >= 0.0001:
        return f"${price:,.4f}"
    else:
        return f"${price:.8f}"


def format_multiple(multiple: float) -> str:
    """Format multiple with x suffix or N/A."""
    if multiple is None:
        return "N/A"
    return f"{multiple:.2f}x" if multiple < 100 else f"{multiple:.1f}x"


def print_banner():
    """Print scanner startup banner with active criteria."""
    print("=" * 95)
    print("                 PUMP SHORT SCANNER (v0.1.0 - Research & Forward-Test)")
    print("=" * 95)
    print("4 Core Filter Criteria:")
    print(f"  [1] Min Market Cap : {format_currency(config.MIN_MARKET_CAP_USD)}")
    print(f"  [2] Min FDV        : {format_currency(config.MIN_FDV_USD)}")
    print(f"  [3] ATH Multiple   : >= {config.ATH_MULTIPLE_THRESHOLD}x (OR)")
    print(f"  [4] 30d Multiple   : >= {config.THIRTY_DAY_MULTIPLE_THRESHOLD}x (+400%)")
    print(f"  [+] Gainers Vol Min: {format_currency(config.MIN_GAINERS_VOLUME_USD)} (24h Volume Floor for Gainers List)")
    print("=" * 95)


def run_scanner(max_pages: int = 4):
    """
    Fetch CoinGecko Top 1000 coins by market cap, apply 4-criteria filter,
    and display matching coins alongside liquid top 30d gainers for manual forward-test selection.
    """
    print_banner()

    client = CoinGeckoClient()
    total_target = max_pages * 250
    print(f"[*] Fetching CoinGecko Top {total_target} coins ({max_pages} pages of 250)...")
    print("    (Applying rate-limit delay between paginated requests)\n")

    try:
        coins_data = client.fetch_top_market_coins(max_pages=max_pages, per_page=250, delay_seconds=2.5)
    except Exception as err:
        print(f"[!] Error fetching market data from CoinGecko: {err}", file=sys.stderr)
        return

    if not coins_data:
        print("[!] No coin data returned from CoinGecko.")
        return

    print(f"[+] Successfully retrieved {len(coins_data)} coins.\n")

    # Evaluate 4-criteria filter
    matched_coins = []
    for coin in coins_data:
        is_match, criteria = evaluate_coin(coin)
        if is_match:
            matched_coins.append((coin, criteria))

    # Sort matching coins by 30-day multiple descending, then market cap descending
    matched_coins.sort(
        key=lambda x: (x[0]["thirty_day_multiple"] or 0, x[0]["market_cap"] or 0),
        reverse=True,
    )

    # 1. Display Matching Coins
    print("=" * 95)
    print(f"🎯 COINS MEETING ALL 4 FILTER CRITERIA ({len(matched_coins)} found):")
    print("=" * 95)

    if matched_coins:
        header = f"{'Symbol':<8} {'Name':<18} {'Price':<14} {'Market Cap':<14} {'FDV':<14} {'30d Mult':<10} {'ATH Mult':<10}"
        print(header)
        print("-" * 95)
        for coin, _ in matched_coins:
            sym = coin["symbol"][:7]
            name = coin["name"][:17]
            price = format_price(coin["current_price"])
            mcap = format_currency(coin["market_cap"])
            fdv = format_currency(coin["fdv"])
            m_30d = format_multiple(coin["thirty_day_multiple"])
            m_ath = format_multiple(coin["ath_multiple"])
            print(f"{sym:<8} {name:<18} {price:<14} {mcap:<14} {fdv:<14} {m_30d:<10} {m_ath:<10}")
        print("-" * 95)
    else:
        print("  No coins in the retrieved universe currently meet all 4 thresholds simultaneously.")

    # 2. Top 30-Day Gainers (filtered by minimum $1M 24h volume floor for tradeable liquidity)
    gainers_30d = [
        c for c in coins_data
        if (c.get("price_change_30d_pct") or 0) > 0
        and (c.get("total_volume") or 0) >= config.MIN_GAINERS_VOLUME_USD
    ]
    gainers_30d.sort(key=lambda c: c["price_change_30d_pct"], reverse=True)
    top_gainers = gainers_30d[:15]

    print("\n" + "=" * 95)
    print(f"🚀 TOP 15 LIQUID 30-DAY GAINERS (24h Vol >= {format_currency(config.MIN_GAINERS_VOLUME_USD)} - Forward-Test Candidates):")
    print("=" * 95)
    header_g = f"{'Symbol':<8} {'Name':<18} {'Price':<14} {'Market Cap':<14} {'24h Volume':<14} {'30d Change':<12} {'30d Mult':<10}"
    print(header_g)
    print("-" * 95)
    for coin in top_gainers:
        sym = coin["symbol"][:7]
        name = coin["name"][:17]
        price = format_price(coin["current_price"])
        mcap = format_currency(coin["market_cap"])
        vol = format_currency(coin["total_volume"])
        pct_30d = f"{coin['price_change_30d_pct']:+.1f}%"
        m_30d = format_multiple(coin["thirty_day_multiple"])
        print(f"{sym:<8} {name:<18} {price:<14} {mcap:<14} {vol:<14} {pct_30d:<12} {m_30d:<10}")

    print("=" * 95)
    print("\n📝 Forward-Test Reminder:")
    print("  Log candidate daily OI & funding rate in 'data/oi_funding_manual_log.csv' for validation.\n")


if __name__ == "__main__":
    run_scanner()
