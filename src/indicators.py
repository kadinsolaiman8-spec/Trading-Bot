"""
Technical indicators: RSI, MACD, Bollinger Bands, SuperTrend, Stochastic, Williams %R, EMA.
Uses the ta library (pure Python, no TA-Lib C dependency).
"""

import pandas as pd
from ta.momentum import RSIIndicator, StochasticOscillator, WilliamsRIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI. Returns series; last value is most recent."""
    rsi = RSIIndicator(close=close, window=period)
    return rsi.rsi()


def compute_macd(
    close: pd.Series,
    window_slow: int = 26,
    window_fast: int = 12,
    window_sign: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Compute MACD line, signal line, and histogram.
    Returns (macd_line, signal_line, histogram).
    """
    macd = MACD(
        close=close,
        window_slow=window_slow,
        window_fast=window_fast,
        window_sign=window_sign,
    )
    return macd.macd(), macd.macd_signal(), macd.macd_diff()


def compute_bollinger(
    close: pd.Series,
    window: int = 20,
    window_dev: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Compute Bollinger Bands: upper, middle (SMA), lower.
    Returns (upper, middle, lower).
    """
    bb = BollingerBands(close=close, window=window, window_dev=window_dev)
    return bb.bollinger_hband(), bb.bollinger_mavg(), bb.bollinger_lband()


def compute_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14,
    smooth_window: int = 3,
) -> tuple[pd.Series, pd.Series]:
    """
    Compute Stochastic Oscillator.
    Returns (stoch_k, stoch_d) where stoch_k is %K and stoch_d is %D (signal).
    """
    stoch = StochasticOscillator(
        high=high, low=low, close=close, window=window, smooth_window=smooth_window
    )
    return stoch.stoch(), stoch.stoch_signal()


def compute_williams_r(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    lbp: int = 14,
) -> pd.Series:
    """
    Compute Williams %R. Oscillates from 0 to -100.
    Oversold < -80, overbought > -20.
    """
    willr = WilliamsRIndicator(high=high, low=low, close=close, lbp=lbp)
    return willr.williams_r()


def compute_ema_crossover(
    close: pd.Series,
    fast: int = 9,
    slow: int = 21,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Compute EMA crossover. Returns (ema_fast, ema_slow, ema_bullish).
    ema_bullish: 1 when fast > slow, -1 when fast < slow.
    """
    ema_fast_ind = EMAIndicator(close=close, window=fast)
    ema_slow_ind = EMAIndicator(close=close, window=slow)
    ema_fast = ema_fast_ind.ema_indicator()
    ema_slow = ema_slow_ind.ema_indicator()
    ema_bullish = pd.Series(0, index=close.index)
    ema_bullish[ema_fast > ema_slow] = 1
    ema_bullish[ema_fast < ema_slow] = -1
    return ema_fast, ema_slow, ema_bullish


def compute_supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 10,
    multiplier: float = 3.0,
) -> tuple[pd.Series, pd.Series]:
    """
    Compute SuperTrend indicator.
    Returns (supertrend_value, supertrend_direction) where direction is 1=bullish, -1=bearish.
    Bullish: close above SuperTrend line. Bearish: close below SuperTrend line.
    """
    atr_ind = AverageTrueRange(high=high, low=low, close=close, window=period)
    atr = atr_ind.average_true_range()

    hl2 = (high + low) / 2
    basic_ub = hl2 + multiplier * atr
    basic_lb = hl2 - multiplier * atr

    n = len(close)
    final_ub = [0.0] * n
    final_lb = [0.0] * n
    supertrend = [0.0] * n

    for i in range(n):
        if i < period:
            final_ub[i] = float(basic_ub.iloc[i]) if i < len(basic_ub) else 0.0
            final_lb[i] = float(basic_lb.iloc[i]) if i < len(basic_lb) else 0.0
            supertrend[i] = 0.0
        else:
            # Final Upper Band
            if basic_ub.iloc[i] < final_ub[i - 1] or close.iloc[i - 1] > final_ub[i - 1]:
                final_ub[i] = float(basic_ub.iloc[i])
            else:
                final_ub[i] = final_ub[i - 1]

            # Final Lower Band
            if basic_lb.iloc[i] > final_lb[i - 1] or close.iloc[i - 1] < final_lb[i - 1]:
                final_lb[i] = float(basic_lb.iloc[i])
            else:
                final_lb[i] = final_lb[i - 1]

            # SuperTrend value
            prev_st = supertrend[i - 1]
            prev_fub = final_ub[i - 1]
            prev_flb = final_lb[i - 1]
            curr_fub = final_ub[i]
            curr_flb = final_lb[i]
            curr_close = float(close.iloc[i])

            if prev_st == prev_fub and curr_close <= curr_fub:
                supertrend[i] = curr_fub
            elif prev_st == prev_fub and curr_close > curr_fub:
                supertrend[i] = curr_flb
            elif prev_st == prev_flb and curr_close >= curr_flb:
                supertrend[i] = curr_flb
            elif prev_st == prev_flb and curr_close < curr_flb:
                supertrend[i] = curr_fub
            else:
                supertrend[i] = curr_flb

    st_series = pd.Series(supertrend, index=close.index)
    direction = pd.Series(1, index=close.index)
    direction[close < st_series] = -1

    return st_series, direction


def get_latest_indicators(
    df: pd.DataFrame,
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
    willr_period: int = 14,
    ema_fast: int = 9,
    ema_slow: int = 21,
) -> dict[str, float] | None:
    """
    Compute all indicators and return latest values for the most recent bar.
    df must have 'High', 'Low', 'Close' columns.

    Returns dict with keys: rsi, macd_hist, bb_upper, bb_middle, bb_lower, close,
    supertrend_value, supertrend_direction, stoch_k, stoch_d, williams_r,
    ema_fast, ema_slow, ema_bullish (1=bullish, -1=bearish).
    Returns None if insufficient data.
    """
    if df is None or df.empty or "Close" not in df.columns:
        return None
    if "High" not in df.columns or "Low" not in df.columns:
        return None

    close = df["Close"].dropna()
    high = df["High"].reindex(close.index).ffill().bfill()
    low = df["Low"].reindex(close.index).ffill().bfill()

    min_len = max(
        rsi_period, macd_slow, bb_period, supertrend_period,
        stoch_window, willr_period, ema_slow
    ) + 15
    if len(close) < min_len:
        return None

    rsi_series = compute_rsi(close, period=rsi_period)
    _, _, macd_hist = compute_macd(close, macd_slow, macd_fast, macd_signal)
    bb_upper, bb_mid, bb_lower = compute_bollinger(close, bb_period, bb_std)
    st_series, st_direction = compute_supertrend(
        high, low, close, period=supertrend_period, multiplier=supertrend_multiplier
    )
    stoch_k, stoch_d = compute_stochastic(
        high, low, close, window=stoch_window, smooth_window=stoch_smooth
    )
    willr_series = compute_williams_r(high, low, close, lbp=willr_period)
    ema_fast_series, ema_slow_series, ema_bullish_series = compute_ema_crossover(
        close, fast=ema_fast, slow=ema_slow
    )

    last = close.index[-1]
    rsi_val = rsi_series.loc[last] if last in rsi_series.index else rsi_series.iloc[-1]
    hist_val = macd_hist.loc[last] if last in macd_hist.index else macd_hist.iloc[-1]
    upper_val = bb_upper.loc[last] if last in bb_upper.index else bb_upper.iloc[-1]
    mid_val = bb_mid.loc[last] if last in bb_mid.index else bb_mid.iloc[-1]
    lower_val = bb_lower.loc[last] if last in bb_lower.index else bb_lower.iloc[-1]
    close_val = float(close.iloc[-1])
    st_val = st_series.loc[last] if last in st_series.index else st_series.iloc[-1]
    st_dir = int(st_direction.loc[last]) if last in st_direction.index else int(st_direction.iloc[-1])
    stoch_k_val = stoch_k.loc[last] if last in stoch_k.index else stoch_k.iloc[-1]
    stoch_d_val = stoch_d.loc[last] if last in stoch_d.index else stoch_d.iloc[-1]
    willr_val = willr_series.loc[last] if last in willr_series.index else willr_series.iloc[-1]
    ema_fast_val = ema_fast_series.loc[last] if last in ema_fast_series.index else ema_fast_series.iloc[-1]
    ema_slow_val = ema_slow_series.loc[last] if last in ema_slow_series.index else ema_slow_series.iloc[-1]
    ema_bullish_val = ema_bullish_series.loc[last] if last in ema_bullish_series.index else ema_bullish_series.iloc[-1]

    return {
        "rsi": float(rsi_val),
        "macd_hist": float(hist_val),
        "bb_upper": float(upper_val),
        "bb_middle": float(mid_val),
        "bb_lower": float(lower_val),
        "close": close_val,
        "supertrend_value": float(st_val),
        "supertrend_direction": st_dir,
        "stoch_k": float(stoch_k_val),
        "stoch_d": float(stoch_d_val),
        "williams_r": float(willr_val),
        "ema_fast": float(ema_fast_val),
        "ema_slow": float(ema_slow_val),
        "ema_bullish": int(ema_bullish_val),
    }
