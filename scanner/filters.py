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
    3. (ATH Multiple >= ath_multiple_threshold with active ATH proximity OR 30d Multiple >= thirty_day_multiple_threshold)

    Formula:
        (ATH multiple >= threshold OR 30d multiple >= threshold) AND market_cap >= min AND fdv >= min
    """
    is_match, _ = evaluate_coin(
        coin,
        min_market_cap=min_market_cap,
        min_fdv=min_fdv,
        ath_multiple_threshold=ath_multiple_threshold,
        thirty_day_multiple_threshold=thirty_day_multiple_threshold,
    )
    return is_match


def evaluate_coin(
    coin: Dict[str, Any],
    min_market_cap: float = config.MIN_MARKET_CAP_USD,
    min_fdv: float = config.MIN_FDV_USD,
    ath_multiple_threshold: float = config.ATH_MULTIPLE_THRESHOLD,
    thirty_day_multiple_threshold: float = config.THIRTY_DAY_MULTIPLE_THRESHOLD,
) -> Tuple[bool, Dict[str, bool]]:
    """
    Detailed evaluation returning overall match status and per-criteria boolean breakdown.
    Handles None/missing values safely without producing false positives.
    """
    market_cap = coin.get("market_cap") or 0.0
    fdv = coin.get("fdv") or 0.0
    ath_multiple = coin.get("ath_multiple")
    thirty_day_multiple = coin.get("thirty_day_multiple")
    is_near_ath = coin.get("is_near_ath", False)

    # 30-day multiple check: must be valid number and >= 5.0 (+400%)
    thirty_day_multiple_ok = (
        thirty_day_multiple is not None
        and thirty_day_multiple >= thirty_day_multiple_threshold
    )

    # ATH multiple check: must have valid ATH data, >= 10.0, and be actively near ATH
    # (Coins deeply below ATH cannot qualify via historical launch-date multiples)
    ath_multiple_ok = (
        ath_multiple is not None
        and ath_multiple >= ath_multiple_threshold
        and is_near_ath
    )

    criteria = {
        "market_cap_ok": market_cap >= min_market_cap,
        "fdv_ok": fdv >= min_fdv,
        "ath_multiple_ok": ath_multiple_ok,
        "thirty_day_multiple_ok": thirty_day_multiple_ok,
        "pump_multiple_ok": thirty_day_multiple_ok or ath_multiple_ok,
    }

    matched = criteria["market_cap_ok"] and criteria["fdv_ok"] and criteria["pump_multiple_ok"]
    return matched, criteria


def filter_coins(coins: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter a list of coins and return only those matching all 4 criteria."""
    return [coin for coin in coins if matches_filter(coin)]
