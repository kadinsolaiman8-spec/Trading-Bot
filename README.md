# Discord Trading Alert Bot

A Python Discord bot that provides market recaps for large-cap US stocks (S&P 100). Uses RSI, MACD, Bollinger Bands, SuperTrend, Stochastic, Williams %R, and EMA crossover to generate Buy/Sell signals with confidence ratings.

## Features

- **Slash command** `/recap` - Get a market recap on demand
- **Auto recap** - Posts every 30 minutes when the US market is open (9:30 AM - 4:00 PM ET, Mon-Fri)
- **Stocks only** - Large-cap S&P 100 constituents
- **Free** - Uses Yahoo Finance (yfinance) and Discord; no paid APIs

## Setup

### 1. Discord Bot

1. Create an application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Go to **Bot** tab, create a bot, and copy the token
3. Go to **OAuth2** → **URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: Send Messages, Embed Links
4. Use the generated URL to invite the bot to your server

### 2. Configuration

```bash
# Copy example env and add your token
cp .env.example .env
# Edit .env and set DISCORD_BOT_TOKEN=your_token_here
```

**Important:** Never commit `.env` to version control. If your token was ever exposed, rotate it immediately in the Discord Developer Portal (Bot tab → Reset Token).

Edit `config.yaml`:

- `channel_id` - Discord channel ID for auto-recap posts (right-click channel → Copy ID). Required for auto recap.
- `recap_interval_minutes` - Default 30
- `indicators` - Tune RSI/MACD/BB/Stochastic/Williams %R/EMA thresholds if desired

### 3. Install and Run

```bash
pip install -r requirements.txt
python main.py
```

## Usage

- **On demand**: Use `/recap` in any channel where the bot is present
- **Auto recap**: When the market is open, the bot posts to the configured channel every 30 minutes

## Output Format

Each recap shows Buy and Sell signals with:

- **Symbol** - Stock ticker
- **Confidence (1-100)** - Combined score from condition alignment and indicator extremity
- **Price** - Current price

## Tech Stack

- **py-cord** - Discord bot with slash commands
- **yfinance** - Free stock data from Yahoo Finance
- **ta** - Technical indicators (RSI, MACD, Bollinger Bands, SuperTrend, Stochastic, Williams %R, EMA)

## Disclaimer

This bot is for educational and informational purposes only. It does not constitute financial advice. Always do your own research before making investment decisions.
