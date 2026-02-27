"""
Signal logic: Buy/Sell/Hold with unified confidence (1-100).
Based on RSI, MACD, Bollinger Bands, SuperTrend, Stochastic, Williams %R, EMA crossover.
"""

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from src.indicators import get_latest_indicators


@dataclass
class Signal:
    symbol: str
    signal_type: Literal["Buy", "Sell", "Hold"]
    confidence: int  # 1-100
    rsi: float
    macd_hist: float
    price: float


def _compute_confidence(
    signal_type: str,
    num_conditions: int,
    rsi: float,
    macd_hist: float,
    stoch_k: float,
    williams_r: float,
    rsi_oversold: float,
    rsi_overbought: float,
    stoch_oversold: float,
    stoch_overbought: float,
    willr_oversold: float,
    willr_overbought: float,
) -> int:
    """
    Unified confidence 1-100 from condition count and extremity bonuses.
    Base: 2 cond -> 40, 3 -> 52, 4 -> 64, 5 -> 76, 6 -> 88, 7 -> 100.
    Bonuses: RSI (0-15), MACD (0-15), Stochastic (0-5), Williams %R (0-5).
    """
    if signal_type == "Hold":
        return 0

    # Base: 2 conditions -> 40, scaling to 100 for 7 conditions
    base = 40 + 12 * (num_conditions - 2)

    # RSI extremity bonus (0-15): how far beyond threshold
    if signal_type == "Buy":
        rsi_bonus = max(0, rsi_oversold - rsi) / max(1, rsi_oversold) * 15
    else:
        rsi_bonus = max(0, rsi - rsi_overbought) / max(1, 100 - rsi_overbought) * 15

    # MACD strength bonus (0-15): histogram magnitude
    macd_bonus = min(15.0, abs(macd_hist) / 0.15)  # scale ~2.25 MACD to 15 pts

    # Stochastic extremity bonus (0-5): how far beyond oversold/overbought
    if signal_type == "Buy":
        stoch_bonus = max(0, stoch_oversold - stoch_k) / max(1, stoch_oversold) * 5
    else:
        stoch_bonus = max(0, stoch_k - stoch_overbought) / max(1, 100 - stoch_overbought) * 5

    # Williams %R extremity bonus (0-5): williams_r is -100 to 0
    if signal_type == "Buy":
        willr_bonus = max(0, willr_oversold - williams_r) / max(1, abs(willr_oversold)) * 5
    else:
        willr_bonus = max(0, williams_r - willr_overbought) / max(1, abs(willr_overbought)) * 5

    confidence = base + rsi_bonus + macd_bonus + stoch_bonus + willr_bonus
    return max(1, min(100, int(round(confidence))))


def evaluate_signal(
    df,
    symbol: str,
    rsi_oversold: float = 35,
    rsi_overbought: float = 65,
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    bb_period: int = 20,
    bb_std: float = 2.0,
    supertrend_period: int = 10,
    supertrend_multiplier: float = 3.0,
    stoch_window: int = 14,
    stoch_smooth: int = 3,
    stoch_oversold: float = 20,
    stoch_overbought: float = 80,
    willr_period: int = 14,
    willr_oversold: float = -80,
    willr_overbought: float = -20,
    ema_fast: int = 9,
    ema_slow: int = 21,
) -> Signal | None:
    """
    Evaluate Buy/Sell/Hold for a single symbol from OHLCV DataFrame.
    Returns Signal or None if insufficient data.
    """
    ind = get_latest_indicators(
        df,
        rsi_period=rsi_period,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal,
        bb_period=bb_period,
        bb_std=bb_std,
        supertrend_period=supertrend_period,
        supertrend_multiplier=supertrend_multiplier,
        stoch_window=stoch_window,
        stoch_smooth=stoch_smooth,
        willr_period=willr_period,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
    )
    if ind is None:
        return None

    rsi = ind["rsi"]
    macd_hist = ind["macd_hist"]
    close = ind["close"]
    bb_lower = ind["bb_lower"]
    bb_upper = ind["bb_upper"]
    st_direction = ind.get("supertrend_direction", 0)  # 1=bullish, -1=bearish, 0=neutral
    stoch_k = ind.get("stoch_k", 50)
    williams_r = ind.get("williams_r", -50)
    ema_bullish = ind.get("ema_bullish", 0)  # 1=bullish, -1=bearish

    buy_score = 0
    sell_score = 0

    # Buy conditions (7 total)
    if rsi < rsi_oversold:
        buy_score += 1
    if close <= bb_lower * 1.002:  # At or below lower band
        buy_score += 1
    if macd_hist > 0:
        buy_score += 1
    if st_direction == 1:  # SuperTrend bullish (price above line)
        buy_score += 1
    if stoch_k < stoch_oversold:
        buy_score += 1
    if williams_r < willr_oversold:
        buy_score += 1
    if ema_bullish == 1:  # EMA fast > slow
        buy_score += 1

    # Sell conditions (7 total)
    if rsi > rsi_overbought:
        sell_score += 1
    if close >= bb_upper * 0.998:  # At or above upper band
        sell_score += 1
    if macd_hist < 0:
        sell_score += 1
    if st_direction == -1:  # SuperTrend bearish (price below line)
        sell_score += 1
    if stoch_k > stoch_overbought:
        sell_score += 1
    if williams_r > willr_overbought:
        sell_score += 1
    if ema_bullish == -1:  # EMA fast < slow
        sell_score += 1

    if buy_score >= 2 and buy_score > sell_score:
        signal_type = "Buy"
        confidence = _compute_confidence(
            signal_type, buy_score, rsi, macd_hist, stoch_k, williams_r,
            rsi_oversold, rsi_overbought, stoch_oversold, stoch_overbought,
            willr_oversold, willr_overbought,
        )
    elif sell_score >= 2 and sell_score > buy_score:
        signal_type = "Sell"
        confidence = _compute_confidence(
            signal_type, sell_score, rsi, macd_hist, stoch_k, williams_r,
            rsi_oversold, rsi_overbought, stoch_oversold, stoch_overbought,
            willr_oversold, willr_overbought,
        )
    else:
        signal_type = "Hold"
        confidence = 0

    return Signal(
        symbol=symbol,
        signal_type=signal_type,
        confidence=confidence,
        rsi=rsi,
        macd_hist=macd_hist,
        price=close,
    )


def evaluate_all(
    ohlcv_data: dict[str, pd.DataFrame],
    rsi_oversold: float = 35,
    rsi_overbought: float = 65,
    **indicator_params,
) -> list[Signal]:
    """
    Evaluate signals for all symbols in ohlcv_data.
    Returns list of Signal objects (includes Hold; filter in recap if desired).
    """
    signals = []
    for symbol, df in ohlcv_data.items():
        sig = evaluate_signal(
            df,
            symbol,
            rsi_oversold=rsi_oversold,
            rsi_overbought=rsi_overbought,
            **indicator_params,
        )
        if sig:
            signals.append(sig)
    return signals
