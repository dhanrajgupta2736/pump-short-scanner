"""4-criteria filtering logic for detecting short-candidate crypto pumps."""

from typing import Any, Dict, List, Tuple
import config


def matches_filter(
    coin: Dict[str, Any],
    min_market_cap: float = config.MIN_MARKET_CAP_USD,
    min_fdv: float = config.MIN_FDV_USD,
    ath_multiple_threshold: float = config.ATH_MULTIPLE_THRESHOLD,
    thirty_day_multiple_threshold: float = config.THIRTY_DAY_MULTIPLE_THRESHOLD,
) -> bool:
    """
    Evaluates whether a coin meets the 4 pump-short criteria:
    1. Market Cap >= min_market_cap
    2. FDV >= min_fdv
    3. (ATH Multiple >= ath_multiple_threshold OR 30d Multiple >= thirty_day_multiple_threshold)

    Formula:
        (ATH multiple >= threshold OR 30d multiple >= threshold) AND market_cap >= min AND fdv >= min
    """
    market_cap = coin.get("market_cap", 0.0)
    fdv = coin.get("fdv", 0.0)
    ath_multiple = coin.get("ath_multiple", 0.0)
    thirty_day_multiple = coin.get("thirty_day_multiple", 0.0)

    passes_market_cap = market_cap >= min_market_cap
    passes_fdv = fdv >= min_fdv
    passes_pump_multiple = (
        ath_multiple >= ath_multiple_threshold
        or thirty_day_multiple >= thirty_day_multiple_threshold
    )

    return passes_market_cap and passes_fdv and passes_pump_multiple


def evaluate_coin(
    coin: Dict[str, Any],
    min_market_cap: float = config.MIN_MARKET_CAP_USD,
    min_fdv: float = config.MIN_FDV_USD,
    ath_multiple_threshold: float = config.ATH_MULTIPLE_THRESHOLD,
    thirty_day_multiple_threshold: float = config.THIRTY_DAY_MULTIPLE_THRESHOLD,
) -> Tuple[bool, Dict[str, bool]]:
    """
    Detailed evaluation returning overall match status and per-criteria boolean breakdown.
    """
    market_cap = coin.get("market_cap", 0.0)
    fdv = coin.get("fdv", 0.0)
    ath_multiple = coin.get("ath_multiple", 0.0)
    thirty_day_multiple = coin.get("thirty_day_multiple", 0.0)

    criteria = {
        "market_cap_ok": market_cap >= min_market_cap,
        "fdv_ok": fdv >= min_fdv,
        "ath_multiple_ok": ath_multiple >= ath_multiple_threshold,
        "thirty_day_multiple_ok": thirty_day_multiple >= thirty_day_multiple_threshold,
        "pump_multiple_ok": (
            ath_multiple >= ath_multiple_threshold
            or thirty_day_multiple >= thirty_day_multiple_threshold
        ),
    }

    matched = criteria["market_cap_ok"] and criteria["fdv_ok"] and criteria["pump_multiple_ok"]
    return matched, criteria


def filter_coins(coins: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter a list of coins and return only those matching all 4 criteria."""
    return [coin for coin in coins if matches_filter(coin)]
