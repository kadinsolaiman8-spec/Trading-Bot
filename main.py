"""
Discord Trading Alert Bot - main entry point.
Pycord bot with /recap slash command and auto-recap every 30 min when market is open.
"""

import asyncio
import logging
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import discord
import yaml
from dotenv import load_dotenv

from src.data import fetch_ohlcv
from src.indices import get_constituents, resolve_input
from src.market_hours import is_market_open
from src.recap import format_recap_embed
from src.signals import evaluate_all
from src.tutorial import build_tutorial_embed

load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = Path(__file__).parent / "config.yaml"
with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)


def _validate_config() -> None:
    """Validate config values at startup. Raises ValueError on invalid config."""
    ind = CONFIG.get("indicators", {})
    # Periods and windows: positive integers
    for key in ("rsi_period", "macd_fast", "macd_slow", "macd_signal", "bb_period",
                "supertrend_period", "stoch_window", "stoch_smooth", "willr_period",
                "ema_fast", "ema_slow"):
        v = ind.get(key)
        if v is not None and (not isinstance(v, (int, float)) or v < 1 or v > 200):
            raise ValueError(f"config indicators.{key} must be 1-200, got {v}")
    # bb_std and supertrend_multiplier: positive
    if ind.get("bb_std") is not None and (ind["bb_std"] <= 0 or ind["bb_std"] > 10):
        raise ValueError(f"config indicators.bb_std must be 0-10, got {ind.get('bb_std')}")
    if ind.get("supertrend_multiplier") is not None and (ind["supertrend_multiplier"] <= 0 or ind["supertrend_multiplier"] > 20):
        raise ValueError(f"config indicators.supertrend_multiplier must be 0-20, got {ind.get('supertrend_multiplier')}")
    # RSI: oversold < overbought
    rsi_os, rsi_ob = ind.get("rsi_oversold", 35), ind.get("rsi_overbought", 65)
    if rsi_os >= rsi_ob:
        raise ValueError(f"config indicators.rsi_oversold ({rsi_os}) must be < rsi_overbought ({rsi_ob})")
    # Stochastic: oversold < overbought
    so_os, so_ob = ind.get("stoch_oversold", 20), ind.get("stoch_overbought", 80)
    if so_os >= so_ob:
        raise ValueError(f"config indicators.stoch_oversold ({so_os}) must be < stoch_overbought ({so_ob})")
    # Williams %R: oversold < overbought (e.g. -80 < -20)
    wr_os, wr_ob = ind.get("willr_oversold", -80), ind.get("willr_overbought", -20)
    if wr_os >= wr_ob:
        raise ValueError(f"config indicators.willr_oversold ({wr_os}) must be < willr_overbought ({wr_ob})")
    # Top-level config
    min_conf = CONFIG.get("min_confidence", 60)
    if min_conf is not None and (not isinstance(min_conf, (int, float)) or min_conf < 1 or min_conf > 100):
        raise ValueError(f"config min_confidence must be 1-100, got {min_conf}")
    data_days = CONFIG.get("data_period_days", 60)
    if data_days is not None and (not isinstance(data_days, (int, float)) or data_days < 1 or data_days > 365):
        raise ValueError(f"config data_period_days must be 1-365, got {data_days}")
    recap_int = CONFIG.get("recap_interval_minutes", 30)
    if recap_int is not None and (not isinstance(recap_int, (int, float)) or recap_int < 1 or recap_int > 1440):
        raise ValueError(f"config recap_interval_minutes must be 1-1440, got {recap_int}")


_validate_config()

INDICATORS = CONFIG.get("indicators", {})
DATA_PERIOD_DAYS = CONFIG.get("data_period_days", 60)
RECAP_INTERVAL = CONFIG.get("recap_interval_minutes", 30)
MIN_CONFIDENCE = CONFIG.get("min_confidence", 60)
CHANNEL_ID = CONFIG.get("channel_id")
GUILD_ID = CONFIG.get("guild_id")

# Guild-specific commands sync instantly; omit for global (can take up to 1 hour)
def _slash_kwargs():
    return {"guild_ids": [GUILD_ID]} if GUILD_ID else {}

# Map days to yfinance period
PERIOD_MAP = {30: "1mo", 60: "2mo", 90: "3mo"}
PERIOD = PERIOD_MAP.get(DATA_PERIOD_DAYS, "2mo")

bot = discord.Bot()
_executor = ThreadPoolExecutor(max_workers=2)


def sanitize_for_discord(text: str, max_len: int = 100) -> str:
    """
    Sanitize user-supplied text before echoing to Discord.
    Prevents @everyone/@here/role pings and markdown injection.
    """
    if not text:
        return ""
    # Truncate first to limit processing
    text = str(text)[:max_len]
    # Break mentions: @everyone, @here, <@user_id>, <@&role_id>
    text = text.replace("@", "@\u200b")  # Zero-width space breaks mentions
    return text


def run_recap() -> discord.Embed:
    """Fetch data, compute signals, return Discord Embed."""
    logger.info("Running market recap...")
    ohlcv = fetch_ohlcv(period=PERIOD, interval="1d")
    if not ohlcv:
        return discord.Embed(
            title="Market Recap - Error",
            description="Could not fetch market data. Please try again later.",
            color=0x808080,
        )

    signals = evaluate_all(
        ohlcv,
        rsi_oversold=INDICATORS.get("rsi_oversold", 35),
        rsi_overbought=INDICATORS.get("rsi_overbought", 65),
        rsi_period=INDICATORS.get("rsi_period", 14),
        macd_fast=INDICATORS.get("macd_fast", 12),
        macd_slow=INDICATORS.get("macd_slow", 26),
        macd_signal=INDICATORS.get("macd_signal", 9),
        bb_period=INDICATORS.get("bb_period", 20),
        bb_std=INDICATORS.get("bb_std", 2),
        supertrend_period=INDICATORS.get("supertrend_period", 10),
        supertrend_multiplier=INDICATORS.get("supertrend_multiplier", 3),
        stoch_window=INDICATORS.get("stoch_window", 14),
        stoch_smooth=INDICATORS.get("stoch_smooth", 3),
        stoch_oversold=INDICATORS.get("stoch_oversold", 20),
        stoch_overbought=INDICATORS.get("stoch_overbought", 80),
        willr_period=INDICATORS.get("willr_period", 14),
        willr_oversold=INDICATORS.get("willr_oversold", -80),
        willr_overbought=INDICATORS.get("willr_overbought", -20),
        ema_fast=INDICATORS.get("ema_fast", 9),
        ema_slow=INDICATORS.get("ema_slow", 21),
    )

    embed_dict = format_recap_embed(signals, include_hold=False, min_confidence=MIN_CONFIDENCE)
    embed = discord.Embed(
        title=embed_dict["title"],
        description=embed_dict["description"],
        color=embed_dict["color"],
    )
    embed.set_footer(text=embed_dict.get("footer", {}).get("text", "S&P 100 | RSI, MACD, BB, SuperTrend, Stochastic, Williams %R, EMA"))
    return embed


def run_market(index_id: str, index_name: str) -> discord.Embed:
    """Fetch data for index constituents, compute signals, return Discord Embed."""
    logger.info("Running market recap for %s...", index_name)
    constituents = get_constituents(index_id)
    if not constituents:
        return discord.Embed(
            title=f"Market Recap - {index_name}",
            description="No constituent data for this index. It may not be supported yet.",
            color=0x808080,
        )

    ohlcv = fetch_ohlcv(symbols=constituents, period=PERIOD, interval="1d")
    if not ohlcv:
        return discord.Embed(
            title=f"Market Recap - {index_name}",
            description="Could not fetch market data. Please try again later.",
            color=0x808080,
        )

    signals = evaluate_all(
        ohlcv,
        rsi_oversold=INDICATORS.get("rsi_oversold", 35),
        rsi_overbought=INDICATORS.get("rsi_overbought", 65),
        rsi_period=INDICATORS.get("rsi_period", 14),
        macd_fast=INDICATORS.get("macd_fast", 12),
        macd_slow=INDICATORS.get("macd_slow", 26),
        macd_signal=INDICATORS.get("macd_signal", 9),
        bb_period=INDICATORS.get("bb_period", 20),
        bb_std=INDICATORS.get("bb_std", 2),
        supertrend_period=INDICATORS.get("supertrend_period", 10),
        supertrend_multiplier=INDICATORS.get("supertrend_multiplier", 3),
        stoch_window=INDICATORS.get("stoch_window", 14),
        stoch_smooth=INDICATORS.get("stoch_smooth", 3),
        stoch_oversold=INDICATORS.get("stoch_oversold", 20),
        stoch_overbought=INDICATORS.get("stoch_overbought", 80),
        willr_period=INDICATORS.get("willr_period", 14),
        willr_oversold=INDICATORS.get("willr_oversold", -80),
        willr_overbought=INDICATORS.get("willr_overbought", -20),
        ema_fast=INDICATORS.get("ema_fast", 9),
        ema_slow=INDICATORS.get("ema_slow", 21),
    )

    embed_dict = format_recap_embed(
        signals, include_hold=False, min_confidence=MIN_CONFIDENCE, index_name=index_name
    )
    embed = discord.Embed(
        title=embed_dict["title"],
        description=embed_dict["description"],
        color=embed_dict["color"],
    )
    embed.set_footer(text=embed_dict.get("footer", {}).get("text", f"{index_name} | RSI, MACD, BB, SuperTrend, Stochastic, Williams %R, EMA"))
    return embed


class IndexSelectView(discord.ui.View):
    """View with buttons for selecting an index when multiple match."""

    def __init__(self, matches: list, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        for m in matches[:5]:  # Max 5 buttons
            self.add_item(IndexSelectButton(m))
        self.add_item(IndexCancelButton())

    def disable_all(self):
        """Disable all buttons (grey out) while loading."""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    async def on_timeout(self):
        """Disable buttons when view times out."""
        self.disable_all()
        try:
            await self.message.edit(view=self)
        except discord.NotFound:
            pass


class IndexCancelButton(discord.ui.Button):
    """Cancel button - must have explicit custom_id to avoid conflicts."""

    def __init__(self):
        super().__init__(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id="index_select_cancel",
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Cancelled.", view=None)


async def _animate_loading_dots(interaction: discord.Interaction, base_text: str, view: discord.ui.View):
    """Cycle loading dots (., .., ...) until cancelled."""
    dots = [".", "..", "..."]
    i = 0
    try:
        while True:
            await interaction.edit_original_response(
                content=f"{base_text}{dots[i % 3]}",
                view=view,
            )
            i += 1
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass


class IndexSelectButton(discord.ui.Button):
    """Button that runs market recap for the selected index."""

    def __init__(self, match):
        super().__init__(
            label=match.name[:80],
            custom_id=match.id,
            style=discord.ButtonStyle.primary,
        )
        self._match = match

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        # Grey out all buttons immediately while loading
        if isinstance(self.view, IndexSelectView):
            self.view.disable_all()
            base = f"Loading {self._match.name}"
            await interaction.edit_original_response(
                content=f"{base}.",
                view=self.view,
            )
        anim_task = asyncio.create_task(
            _animate_loading_dots(interaction, base, self.view)
        )
        embed = None
        try:
            loop = asyncio.get_event_loop()
            embed = await loop.run_in_executor(
                _executor,
                lambda: run_market(self._match.id, self._match.name),
            )
        except Exception:
            logger.exception("Market button callback failed")
        finally:
            anim_task.cancel()
            try:
                await anim_task
            except asyncio.CancelledError:
                pass
        if embed is not None:
            await interaction.edit_original_response(embed=embed, view=None)
        else:
            await interaction.edit_original_response(
                content="An error occurred while generating the recap. Please try again later.",
                embed=None,
                view=None,
            )


@bot.slash_command(description="Learn how the bot works and reasons", **_slash_kwargs())
async def tutorial(ctx):
    """Slash command: tutorial on bot functionality."""
    await ctx.respond(embed=build_tutorial_embed())


@bot.slash_command(description="Get a market recap of large-cap stocks", **_slash_kwargs())
async def recap(ctx):
    """Slash command: on-demand market recap (S&P 100 only)."""
    await ctx.defer()
    try:
        loop = asyncio.get_event_loop()
        embed = await loop.run_in_executor(_executor, run_recap)
        await ctx.respond(embed=embed)
    except Exception as e:
        logger.exception("Recap command failed")
        await ctx.respond("An error occurred while generating the recap. Please try again later.", ephemeral=True)


@bot.slash_command(
    description="Get market recap for an index (by name or country)",
    **_slash_kwargs(),
)
async def market(ctx, query: discord.Option(str, "Index name or country (e.g. S&P 500, USA, Germany)")):
    """Slash command: market recap for a specific index."""
    await ctx.defer()
    try:
        # Validate and sanitize input
        query = (query or "")[:100].strip()
        if not query:
            await ctx.respond("Please enter an index name or country (e.g. S&P 500, USA, Germany).", ephemeral=True)
            return

        matches = resolve_input(query)
        safe_query = sanitize_for_discord(query)
        if not matches:
            await ctx.respond(f"No index found for '{safe_query}'. Try an index name (e.g. S&P 500, DAX) or country (e.g. USA, Germany).", ephemeral=True)
            return

        if len(matches) == 1:
            m = matches[0]
            constituents = get_constituents(m.id)
            if not constituents:
                await ctx.respond(f"No constituent data for {m.name}. This index is not supported yet.", ephemeral=True)
                return
            loop = asyncio.get_event_loop()
            embed = await loop.run_in_executor(
                _executor,
                lambda m=m: run_market(m.id, m.name),
            )
            await ctx.respond(embed=embed)
        else:
            view = IndexSelectView(matches)
            await ctx.respond(
                f"Multiple indices found for '{safe_query}'. Choose one:",
                view=view,
                ephemeral=True,
            )
    except Exception as e:
        logger.exception("Market command failed")
        await ctx.respond("An error occurred. Please try again later.", ephemeral=True)


async def auto_recap_loop():
    """Background task: run recap every N minutes when market is open."""
    await bot.wait_until_ready()
    interval_seconds = RECAP_INTERVAL * 60

    while not bot.is_closed():
        try:
            if is_market_open() and CHANNEL_ID:
                channel = bot.get_channel(CHANNEL_ID)
                if channel:
                    loop = asyncio.get_event_loop()
                    embed = await loop.run_in_executor(_executor, run_recap)
                    await channel.send(content="@everyone", embed=embed)
                    logger.info("Auto recap posted to channel %s", CHANNEL_ID)
                else:
                    logger.warning("Channel %s not found", CHANNEL_ID)
        except Exception as e:
            logger.exception("Auto recap failed: %s", e)

        await asyncio.sleep(interval_seconds)


@bot.event
async def on_ready():
    logger.info("Bot ready: %s", bot.user)
    bot.loop.create_task(auto_recap_loop())


def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN not set. Create a .env file with your bot token.")
        return

    if not CHANNEL_ID:
        logger.warning("channel_id not set in config.yaml. Auto recap will not post. Set it to your channel ID.")
    if not GUILD_ID:
        logger.info("guild_id not set. Slash commands sync globally and may take up to 1 hour to appear. For instant sync, add your server ID to config.yaml.")

    bot.run(token)


if __name__ == "__main__":
    main()
