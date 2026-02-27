"""
Build tutorial embed explaining how the bot works and reasons.
"""

import discord


def build_tutorial_embed() -> discord.Embed:
    """Build a Discord embed explaining the bot's functionality and signal logic."""
    embed = discord.Embed(
        title="How the Trading Bot Works",
        description="A quick guide to understanding this bot's data flow, signal logic, and output.",
        color=0x3498DB,
    )

    embed.add_field(
        name="What it does",
        value=(
            "Scans stocks for technical signals.\n"
            "• Use `/recap` for S&P 100 market recap (top 100 large-cap US stocks)\n"
            "• Use `/market` for other indices (e.g. S&P 500, DAX, FTSE 100) — enter index name or country\n"
            "• Auto-recap posts every 30 min when the market is open (9:30 AM - 4:00 PM ET, Mon-Fri), pinging @everyone"
        ),
        inline=False,
    )

    embed.add_field(
        name="How it works",
        value=(
            "1. Fetches ~60 days of daily OHLCV from Yahoo Finance\n"
            "2. Computes **RSI** (14), **MACD** (12/26/9), **Bollinger Bands** (20, 2 std), **SuperTrend** (10, 3), "
            "**Stochastic** (14, 3), **Williams %R** (14), **EMA crossover** (9/21)\n"
            "3. Evaluates each stock for Buy, Sell, or Hold"
        ),
        inline=False,
    )

    embed.add_field(
        name="Signal logic (how it reasons)",
        value=(
            "**Buy** (needs 2+ of 7 conditions):\n"
            "• RSI < 35 (oversold)\n"
            "• Price at or below lower Bollinger Band\n"
            "• MACD histogram > 0\n"
            "• SuperTrend bullish (price above line)\n"
            "• Stochastic %K < 20 (oversold)\n"
            "• Williams %R < -80 (oversold)\n"
            "• EMA fast > slow (bullish crossover)\n"
            "→ Confidence 1-100 combines condition alignment, RSI/Stochastic/Williams extremity, and MACD strength\n\n"
            "**Sell** (needs 2+ of 7 conditions):\n"
            "• RSI > 65 (overbought)\n"
            "• Price at or above upper Bollinger Band\n"
            "• MACD histogram < 0\n"
            "• SuperTrend bearish (price below line)\n"
            "• Stochastic %K > 80 (overbought)\n"
            "• Williams %R > -20 (overbought)\n"
            "• EMA fast < slow (bearish crossover)\n\n"
            "**Hold**: Otherwise (no strong signal)"
        ),
        inline=False,
    )

    embed.add_field(
        name="Interpreting results",
        value=(
            "• **Confidence 1-100**: Single score combining condition alignment, RSI/Stochastic/Williams extremity, and MACD strength\n"
            "• Auto-recap pings @everyone during market hours\n"
            "• Recap shows top 15 Buy and Sell signals by confidence"
        ),
        inline=False,
    )

    embed.set_footer(text="Tune indicator thresholds and recap interval in config.yaml")

    return embed
