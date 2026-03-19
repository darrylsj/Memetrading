# Memetrading 🎰

Meme coin quick-flip trading system with auto-exit gates. Built for the [True Markets CLI](https://github.com/true-markets/cli) on Solana.

**Philosophy:** Easy to buy, hard to sell. This system solves the hard part.

## What It Does

1. **Scans** 50+ meme coins for pump signals (volume spikes, momentum, trending)
2. **Checks liquidity** before buying (won't enter pools under $2M)
3. **Buys** via True Markets CLI (Jupiter DEX routing, no gas)
4. **Monitors** positions with hybrid real-time price feeds
5. **Auto-exits** on take profit, stop loss, trailing stop, or time stop

## Price Feeds (Hybrid)

| Source | Speed | Coverage |
|--------|-------|----------|
| Binance WebSocket | <100ms | 15 listed coins |
| True Markets quote | 1-2s | All TM coins (actual Jupiter DEX exit price) |
| DexScreener | ~400ms | All Solana DEX tokens + 5m/1h candles |
| CoinGecko | 1-2 min | Fallback only |

## Exit Gates

| Gate | Trigger | Purpose |
|------|---------|---------|
| **Quick Flip** | +3% in first 2 min | Grab fast pops |
| **Take Profit** | +10% | Lock gains |
| **Trailing Stop** | -5% from high (after +7%) | Let winners run |
| **Stop Loss** | -20% first 20 min, -8% after | Don't panic on spread |
| **Time Stop** | 2 hours | No bagholding |
| **Liquidity Gate** | Pre-buy check | Block < $2M pools |

## Setup

```bash
# Install True Markets CLI
brew install true-markets/tap/tm

# Sign up
tm signup your@email.com

# Fund wallet (send USDC on Solana)
tm whoami  # Shows your Solana address

# Install Python deps (optional — only for Binance WS)
pip install websocket-client
```

## Usage

```bash
# Scan for pump candidates
python3 meme-scanner.py

# Buy a coin
python3 meme-trader.py buy FARTCOIN 20

# Monitor positions (auto-exits)
python3 meme-trader.py monitor

# Check positions + P&L
python3 meme-trader.py positions

# Manual sell
python3 meme-trader.py sell FARTCOIN
```

## Scanner Signals

The scanner scores coins 0-100 based on:

- **Volume/MCap ratio** — high ratio = unusual activity (pump in progress)
- **1h/24h price momentum** — catching moves already in motion
- **CoinGecko trending** — social attention driver
- **Market cap tier** — smaller = more explosive
- **Liquidity depth** — must be able to exit cleanly

Scores 70+ = BUY signal. Scores 55-69 = WATCH. Below 55 = SKIP.

## Lessons Learned (the hard way)

### The DADDY Trade ($0.46 lesson)
Bought $20 of DADDY Tate. $762K liquidity pool. Stop loss triggered instantly on the buy-sell spread (-6.7% phantom loss). Sell failed twice (500 errors). Eventually exited at -2.3%.

**Rule added:** Liquidity gate blocks anything under $2M.

### The FARTCOIN Round Trip ($0.03 cost)
Bought $2, sold $2 of FARTCOIN. $7.9M liquidity pool. In and out in seconds. Total cost: $0.03. This is what a clean trade looks like.

**The difference:** 10x more liquidity = 10x cleaner exit.

### Why "Easy to Buy, Hard to Sell"
Every DEX trade has spread. Thin pools have more spread. The buy always fills (you're adding to the pool). The sell sometimes fails (you're draining the pool). The system must account for this asymmetry.

## Architecture

```
meme-scanner.py          # Momentum scanner — finds pump candidates
    └── CoinGecko API    # Market data + trending
    └── DexScreener API  # 5m candles + liquidity check

meme-trader.py           # Position manager — buys, monitors, auto-exits
    └── tm CLI           # True Markets buy/sell execution
    └── Binance WS       # Real-time prices (15 coins)
    └── DexScreener      # Prices + liquidity (all others)
    └── tm dry-run quote # Actual exit price (Jupiter DEX)
```

## Disclaimer

This is experimental trading software. Meme coins are extremely volatile. You can lose your entire investment. This is not financial advice. Use at your own risk.

Built by [Aria](https://github.com/darmac) as part of the Polymarket trading bot saga.

## License

MIT
