"""
Fetch OHLCV data from Yahoo Finance via yfinance.
"""

import logging
import pandas as pd
import yfinance as yf

from src.stocks import get_sp100_tickers

logger = logging.getLogger(__name__)

BATCH_SIZE = 25  # Avoid rate limits


def fetch_ohlcv(
    symbols: list[str] | None = None,
    period: str = "2mo",
    interval: str = "1d",
) -> dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for given symbols.

    Args:
        symbols: List of ticker symbols. If None, uses S&P 100.
        period: yfinance period (e.g. "2mo", "3mo").
        interval: Candle interval ("1d" for daily).

    Returns:
        Dict mapping symbol -> DataFrame with columns Open, High, Low, Close, Volume.
        Failed symbols are omitted.
    """
    if symbols is None:
        symbols = get_sp100_tickers()

    result: dict[str, pd.DataFrame] = {}

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i : i + BATCH_SIZE]
        try:
            df = yf.download(
                batch,
                period=period,
                interval=interval,
                group_by="ticker",
                progress=False,
                threads=False,
                auto_adjust=True,
            )
        except Exception as e:
            logger.warning("yfinance batch download failed: %s", e)
            continue

        if df.empty:
            continue

        # With group_by="ticker", columns are (Ticker, OHLCV) for any batch size
        for ticker in batch:
            if ticker not in df.columns.get_level_values(0):
                continue
            try:
                sub = df[ticker].copy()
                if sub is None or sub.empty:
                    continue
                required = ["Open", "High", "Low", "Close", "Volume"]
                if all(c in sub.columns for c in required):
                    result[ticker] = sub[required]
            except (KeyError, TypeError):
                continue

    return result


def fetch_single(symbol: str, period: str = "2mo", interval: str = "1d") -> pd.DataFrame | None:
    """Fetch OHLCV for a single symbol. Returns None on failure."""
    data = fetch_ohlcv([symbol], period=period, interval=interval)
    return data.get(symbol)
