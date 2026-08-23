"""Main entry point for Pump Short Scanner."""

import sys
import config
from scanner.coingecko_client import CoinGeckoClient
from scanner.filters import evaluate_coin

# Ensure UTF-8 output encoding if supported by stream
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def format_currency(value: float) -> str:
    """Format large numbers into human-readable currency strings ($M, $B)."""
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value / 1_000:.2f}K"
    elif value > 0:
        return f"${value:.4f}"
    return "$0.00"


def print_banner():
    """Print scanner startup banner with active criteria."""
    print("=" * 80)
    print("                 PUMP SHORT SCANNER (v0.1.0 - Research Mode)")
    print("=" * 80)
    print("Criteria:")
    print(f"  * Min Market Cap   : {format_currency(config.MIN_MARKET_CAP_USD)}")
    print(f"  * Min FDV          : {format_currency(config.MIN_FDV_USD)}")
    print(f"  * ATH Multiple     : >= {config.ATH_MULTIPLE_THRESHOLD}x (or)")
    print(f"  * 30d Multiple     : >= {config.THIRTY_DAY_MULTIPLE_THRESHOLD}x (+400%)")
    print("=" * 80)


def run_scanner():
    """Fetch test coins, apply criteria filters, and display results."""
    print_banner()

    client = CoinGeckoClient()
    test_coins = config.TEST_COIN_IDS
    print(f"[*] Scanning {len(test_coins)} target coins from CoinGecko public API...")
    print(f"    Target IDs: {', '.join(test_coins)}\n")

    try:
        coins_data = client.fetch_markets_data(test_coins)
    except Exception as err:
        print(f"[!] Error fetching market data from CoinGecko: {err}", file=sys.stderr)
        return

    if not coins_data:
        print("[!] No coin data returned.")
        return

    # Header for table
    header = f"{'Symbol':<8} {'Price':<12} {'Market Cap':<14} {'FDV':<14} {'30d Mult':<10} {'ATH Mult':<10} {'Match?'}"
    print(header)
    print("-" * 80)

    matched_coins = []

    for coin in coins_data:
        is_match, criteria = evaluate_coin(coin)
        symbol = coin["symbol"]
        price = f"${coin['current_price']:,.4f}" if coin['current_price'] < 1 else f"${coin['current_price']:,.2f}"
        mcap = format_currency(coin["market_cap"])
        fdv = format_currency(coin["fdv"])
        m_30d = f"{coin['thirty_day_multiple']}x"
        m_ath = f"{coin['ath_multiple']}x"
        match_str = "[MATCH] YES" if is_match else "[ ] No"

        print(f"{symbol:<8} {price:<12} {mcap:<14} {fdv:<14} {m_30d:<10} {m_ath:<10} {match_str}")

        if is_match:
            matched_coins.append((coin, criteria))

    print("-" * 80)
    print(f"\nSummary: {len(matched_coins)} of {len(coins_data)} coins matched short-scanner criteria.")

    if matched_coins:
        print("\nMatching Short Candidates:")
        for coin, criteria in matched_coins:
            print(f"  * {coin['name']} ({coin['symbol']}):")
            print(f"      Price: ${coin['current_price']:,} | Market Cap: {format_currency(coin['market_cap'])} | FDV: {format_currency(coin['fdv'])}")
            print(f"      30d Change: {coin['price_change_30d_pct']:+.2f}% ({coin['thirty_day_multiple']}x) | All-Time Multiple: {coin['ath_multiple']}x")
    else:
        print("  (No coins currently meet all thresholds simultaneously with the test sample)")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    run_scanner()

