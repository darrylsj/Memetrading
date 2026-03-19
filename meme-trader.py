#!/usr/bin/env python3
"""
meme-trader.py — Meme coin quick-flip trader with auto-exit.

Monitors positions after buy. Auto-sells on:
  - Take profit: +10% (configurable)
  - Stop loss: -5% (configurable)
  - Trailing stop: locks in gains, exits on pullback
  - Time stop: sell after 2 hours regardless (don't baghold)

Usage:
  python3 meme-trader.py buy FARTCOIN 20       # Buy $20 worth
  python3 meme-trader.py monitor               # Watch all open positions
  python3 meme-trader.py scan                   # Run scanner + alert
  python3 meme-trader.py positions              # Show current holdings
  python3 meme-trader.py sell FARTCOIN          # Manual sell all
"""

import json
import os
import sys
import time
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────

TAKE_PROFIT_PCT = 0.10      # +10% = sell
STOP_LOSS_PCT = -0.08       # -8% = sell (wider to absorb 2-3% buy/sell spread)
TRAILING_STOP_PCT = 0.05    # After +7%, trail by 5% from high
TRAILING_ACTIVATE = 0.07    # Activate trailing stop after +7%
TIME_STOP_MINUTES = 120     # Sell after 2 hours no matter what
POLL_INTERVAL = 15          # Check prices every 15 seconds
GRACE_PERIOD_SECONDS = 60   # Don't trigger stop loss in first 60s (let spread settle)

import math

def log_return(entry_price, exit_price):
    """Honest P&L: log returns sum correctly, arithmetic returns lie."""
    if entry_price <= 0 or exit_price <= 0:
        return 0
    return math.log(exit_price / entry_price)

POSITIONS_FILE = Path.home() / ".config" / "truemarkets" / "positions.json"
TRADE_LOG = Path.home() / ".config" / "truemarkets" / "trade_log.json"

COINGECKO = "https://api.coingecko.com/api/v3"
DEXSCREENER = "https://api.dexscreener.com/tokens/v1/solana"

# Token mint addresses for DexScreener (Solana)
MINT_ADDRESSES = {
    "FARTCOIN": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
    "BAN": "9PR7nCP9DpcUotnDPVLUBUZKu5WAYkwrCUx9wDnSpump",
    "MOODENG": "ED5nyyWEzpPPiWimP8vYm7sD7TD3LAt3Q3gRTWHzPJBY",
    "JELLYJELLY": "FeR8VBqNRSUD5NtXAj2n3j1dAHkZHfyDktKuLXD4pump",
    "GOAT": "CzLSujWBLFsSjncfkh59rUFqvafWcY5tzedWJSuypump",
    "DADDY": "4Cnk9EPnW5ixfLZatCPJjDB1PUtcRpVVgTQukm9epump",
    "VINE": "6AJcP7wuLwmRYLBNbi825wgguaPsWzPBEHcHndpRpump",
    "POPCAT": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "PENGU": "2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv",
    "TRUMP": "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN",
    "PNUT": "2qEHjDLDLbuBgRYvsxhc5D6uDWAivNFZGan56P1tpump",
    "MEW": "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5",
    "SLERF": "7BgBvyjrZX1YKz4oh9mjb8ZScatkkwb8DzFx7LoiVkM3",
    "BOME": "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82",
    "CHILLGUY": "Df6yfrKC8kZE3KNkrHERKzAetSxbrWeniQfyJY4Jpump",
    "RETARDIO": "6ogzHhzdrQr9Pgv6hZ2MNze7UrzBMAFyBBWUYp1Fhitx",
    "SWARMS": "74SBV4zDXxTRgv1pEMoECskKBkZHc2yGPnc7GYVepump",
    "ZEREBRO": "8x5VqbHA8D7NkD52uNuS5nnt3PwA8pLD34ymskeSo2Wn",
    "VIRTUAL": "3iQL8BFS2vE7mww4ehAqQHAsbmRNCrPxizWAT2Zfyr9y",
    "GIGA": "63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9",
    "MICHI": "5mbK36SZ7J19An8jFochhQS4of8g6BwUjbeCSxBSoWdp",
    "SPX": "J3NKxxXZcnNiMjKw9hYb2K4LUxgwB6t1FtPtQVsv3KFr",
    "PONKE": "5z3EqYQo9HiCEs3R84RCDMu2n7anpDMxRhdK8PSWmrRC",
    "LAUNCHCOIN": "Ey59PH7Z4BFU4HjyKnyMdWt5GGN76KazTAwQihoUXRnk",
    "USA": "69kdRLyP5DTRkpHraaSZAQbWmAwzF9guKjZfzMXzcbAs",
    "GRIFFAIN": "KENJSUYLASHUMfHyy5o4Hp2FdNqZg1AsUPhfH2kYvEP",
    "FWOG": "A8C3xuqscfmyLrte3VmTqrAq8kgMASius9AFNANwpump",
    "HOUSE": "DitHyRMQiSDhn5cnKMJV2CDDt6sVct96YrECiM49pump",
    "TITCOIN": "FtUEW73K6vEYHfbkfpdBZfWpxgQar2HipGdbutEhpump",
}

# CoinGecko IDs for TM coins (subset — add as needed)
COIN_IDS = {
    "FARTCOIN": "fartcoin", "BAN": "comedian", "MOODENG": "moo-deng",
    "PNUT": "peanut-the-squirrel", "BOME": "book-of-meme",
    "ZEREBRO": "zerebro", "BONK": "bonk", "WIF": "dogwifhat",
    "PENGU": "pudgy-penguins", "POPCAT": "popcat-sol",
    "TRUMP": "official-trump", "JELLYJELLY": "jelly-my-jelly",
    "DADDY": "daddy-tate", "VINE": "vine-coin",
    "MICHI": "michi", "CHILLGUY": "just-a-chill-guy",
    "GOAT": "goatseus-maximus", "PONKE": "ponke",
    "SPX": "spx6900", "RETARDIO": "retardio",
    "MEW": "cat-in-a-dogs-world", "SWARMS": "swarms",
    "GRIFFAIN": "griffain", "SIGMA": "sigma-2",
    "VIRTUAL": "virtual-protocol", "DRIFT": "drift-protocol",
    "W": "wormhole", "LAUNCHCOIN": "launchcoin-on-believe",
    "HYPE": "hyperliquid", "MON": "monad",
    "DEGEN": "degen-base", "BRETT": "brett-based",
    "KAITO": "kaito-2", "USA": "american-coin",
    "SLERF": "slerf", "MYRO": "myro",
    "GIGA": "gigachad-2", "FWOG": "fwog",
    "TITCOIN": "titcoin", "HOUSE": "housecoin",
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def tm_cmd(args):
    """Run a tm CLI command and return output."""
    result = subprocess.run(
        ["tm"] + args, capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def tm_buy(symbol, amount_usd):
    """Buy via tm CLI with auto-confirm."""
    result = subprocess.run(
        ["tm", "buy", symbol, str(amount_usd)],
        input="y\n", capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip(), result.returncode


def tm_sell(symbol, amount=None):
    """Sell via tm CLI with auto-confirm and retry."""
    if not amount:
        balances = get_balances()
        bal = balances.get(symbol, 0)
        if bal <= 0:
            return "No balance to sell", 1
        # Leave tiny dust to avoid rounding issues
        amount = int(bal) if bal > 10 else bal * 0.99
    
    for attempt in range(3):
        result = subprocess.run(
            ["tm", "sell", symbol, str(amount)],
            input="y\n", capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and "Trade submitted" in result.stdout:
            return result.stdout.strip(), 0
        if "500" in result.stdout or "could not submit" in result.stdout:
            time.sleep(2)  # Retry on 500
            continue
        break
    
    return result.stdout.strip(), result.returncode


def get_balances():
    """Get current TM balances."""
    out, err, code = tm_cmd(["balances", "-o", "json"])
    if code != 0:
        return {}
    try:
        data = json.loads(out)
        return {item["symbol"]: float(item["balance"]) for item in data if float(item["balance"]) > 0}
    except:
        return {}


# Coins available on Binance for real-time WebSocket prices
BINANCE_PAIRS = {
    "BOME": "bomeusdt", "BONK": "bonkusdt", "JTO": "jtousdt",
    "JUP": "jupusdt", "KAITO": "kaitousdt", "ORCA": "orcausdt",
    "PENGU": "penguusdt", "PNUT": "pnutusdt", "PYTH": "pythusdt",
    "RAY": "rayusdt", "RENDER": "renderusdt", "SOL": "solusdt",
    "TRUMP": "trumpusdt", "VIRTUAL": "virtualusdt", "WIF": "wifusdt",
}

# Binance price cache (updated by WS thread)
_binance_prices = {}
_binance_ws_running = False


def start_binance_ws():
    """Start Binance WebSocket for real-time prices on supported coins."""
    global _binance_ws_running
    if _binance_ws_running:
        return
    _binance_ws_running = True
    
    import threading
    try:
        import websocket as ws_lib
    except ImportError:
        log("websocket-client not installed — Binance WS disabled")
        _binance_ws_running = False
        return
    
    streams = "/".join(f"{pair}@ticker" for pair in BINANCE_PAIRS.values())
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    
    # Reverse map
    pair_to_sym = {v: k for k, v in BINANCE_PAIRS.items()}
    
    def on_msg(ws, msg):
        try:
            data = json.loads(msg)
            stream = data.get("stream", "")
            ticker = data.get("data", {})
            pair = stream.split("@")[0]
            sym = pair_to_sym.get(pair)
            if sym and ticker.get("c"):
                _binance_prices[sym] = {
                    "price": float(ticker["c"]),  # Last price
                    "change_24h": float(ticker.get("P", 0)),  # 24h change %
                    "ts": time.time(),
                }
        except:
            pass
    
    def on_err(ws, err):
        pass  # Silent reconnect
    
    def on_close(ws, *args):
        global _binance_ws_running
        _binance_ws_running = False
    
    def run_ws():
        while True:
            try:
                w = ws_lib.WebSocketApp(url, on_message=on_msg, on_error=on_err, on_close=on_close)
                w.run_forever(ping_interval=30, ping_timeout=10)
            except:
                pass
            time.sleep(3)
    
    t = threading.Thread(target=run_ws, daemon=True)
    t.start()
    log(f"Binance WS started — {len(BINANCE_PAIRS)} pairs real-time")


def get_price_tm(symbol, amount=0.001):
    """Get real execution price from tm CLI dry-run quote.
    
    This is the ACTUAL price we'd get on Jupiter/Raydium DEX,
    including slippage and fees. Most accurate for exit decisions.
    """
    try:
        # Use a tiny sell quote to get current price
        result = subprocess.run(
            ["tm", "sell", symbol, str(amount)],
            input="n\n",  # Don't execute, just quote
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout
        # Parse "You receive:  0.000212 USDC"
        for line in output.split("\n"):
            if "You receive:" in line:
                parts = line.split()
                usdc_amount = float(parts[-2])
                return usdc_amount / amount  # Price per token
    except:
        pass
    return None


def get_price(symbol):
    """Get current price — best available source.
    
    Priority:
    1. Binance WS (sub-second, if available)
    2. tm CLI quote (1-2s, actual DEX price)
    3. CoinGecko (1-2 min delayed, last resort)
    """
    # 1. Binance (sub-second)
    if symbol in _binance_prices:
        bp = _binance_prices[symbol]
        if time.time() - bp.get("ts", 0) < 30:  # Fresh within 30s
            return bp["price"]
    
    # 2. tm CLI quote (actual DEX execution price)
    tm_price = get_price_tm(symbol)
    if tm_price and tm_price > 0:
        return tm_price
    
    # 3. DexScreener (fast, covers all DEX memes)
    mint = MINT_ADDRESSES.get(symbol)
    if mint:
        try:
            import urllib.request as _ur
            url = f"{DEXSCREENER}/{mint}"
            req = _ur.Request(url, headers={"User-Agent": "MemeTrader/1.0"})
            with _ur.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, list) and data:
                    return float(data[0].get("priceUsd", 0))
        except:
            pass
    
    # 4. CoinGecko fallback (slowest)
    cg_id = COIN_IDS.get(symbol)
    if not cg_id:
        return None
    import urllib.request
    url = f"{COINGECKO}/simple/price?ids={cg_id}&vs_currencies=usd"
    req = urllib.request.Request(url, headers={"User-Agent": "MemeTrader/1.0"})
    try:
        time.sleep(1.5)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get(cg_id, {}).get("usd")
    except:
        return None


def get_prices_batch(symbols):
    """Get prices for multiple symbols — hybrid Binance WS + tm + CoinGecko."""
    result = {}
    need_cg = []
    
    for sym in symbols:
        # 1. Try Binance cache first
        if sym in _binance_prices:
            bp = _binance_prices[sym]
            if time.time() - bp.get("ts", 0) < 30:
                result[sym] = {
                    "price": bp["price"],
                    "change_24h": bp.get("change_24h", 0),
                    "source": "binance_ws",
                }
                continue
        
        # 2. Try tm quote for non-Binance coins
        if sym not in BINANCE_PAIRS:
            tm_price = get_price_tm(sym)
            if tm_price and tm_price > 0:
                result[sym] = {
                    "price": tm_price,
                    "change_24h": 0,  # tm doesn't give 24h change
                    "source": "tm_quote",
                }
                continue
        
        # 3. Fall back to DexScreener / CoinGecko
        need_cg.append(sym)
    
    # Batch DexScreener for Solana tokens
    dex_batch = [s for s in need_cg if s in MINT_ADDRESSES]
    if dex_batch:
        try:
            import urllib.request as _ur
            addrs = ",".join(MINT_ADDRESSES[s] for s in dex_batch)
            url = f"{DEXSCREENER}/{addrs}"
            req = _ur.Request(url, headers={"User-Agent": "MemeTrader/1.0"})
            with _ur.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                addr_to_sym = {v: k for k, v in MINT_ADDRESSES.items()}
                seen = set()
                if isinstance(data, list):
                    for pair in data:
                        addr = pair.get("baseToken", {}).get("address", "")
                        sym_match = addr_to_sym.get(addr)
                        if sym_match and sym_match not in seen:
                            seen.add(sym_match)
                            result[sym_match] = {
                                "price": float(pair.get("priceUsd", 0)),
                                "change_24h": pair.get("priceChange", {}).get("h24", 0),
                                "change_5m": pair.get("priceChange", {}).get("m5", 0),
                                "change_1h": pair.get("priceChange", {}).get("h1", 0),
                                "liquidity": pair.get("liquidity", {}).get("usd", 0),
                                "source": "dexscreener",
                            }
                            need_cg = [s for s in need_cg if s != sym_match]
        except:
            pass
    
    # Remaining: CoinGecko
    if need_cg:
        ids = [COIN_IDS[s] for s in need_cg if s in COIN_IDS]
        if ids:
            import urllib.request
            ids_str = ",".join(ids)
            url = f"{COINGECKO}/simple/price?ids={ids_str}&vs_currencies=usd&include_24hr_change=true"
            req = urllib.request.Request(url, headers={"User-Agent": "MemeTrader/1.0"})
            try:
                time.sleep(1.5)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    id_to_sym = {v: k for k, v in COIN_IDS.items()}
                    for cg_id, price_data in data.items():
                        sym = id_to_sym.get(cg_id)
                        if sym:
                            result[sym] = {
                                "price": price_data.get("usd", 0),
                                "change_24h": price_data.get("usd_24h_change", 0),
                                "source": "coingecko",
                            }
            except:
                pass
    
    return result


# ── Position Management ────────────────────────────────────────────────────

def load_positions():
    """Load open positions."""
    if POSITIONS_FILE.exists():
        try:
            return json.loads(POSITIONS_FILE.read_text())
        except:
            pass
    return {}


def save_positions(positions):
    """Save open positions."""
    POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    POSITIONS_FILE.write_text(json.dumps(positions, indent=2))


def log_trade(trade):
    """Append to trade log."""
    TRADE_LOG.parent.mkdir(parents=True, exist_ok=True)
    trades = []
    if TRADE_LOG.exists():
        try:
            trades = json.loads(TRADE_LOG.read_text())
        except:
            pass
    trades.append(trade)
    TRADE_LOG.write_text(json.dumps(trades, indent=2))


def send_alert(msg):
    """Send alert to Telegram via OpenClaw."""
    try:
        subprocess.run(
            ["openclaw", "message", "send", "--channel", "telegram", "--message", msg],
            capture_output=True, timeout=10
        )
    except:
        pass  # Best effort


# ── Commands ────────────────────────────────────────────────────────────────

def cmd_buy(symbol, amount_usd):
    """Buy a coin and register the position for monitoring."""
    symbol = symbol.upper()
    
    # Get current price before buying
    price_before = get_price(symbol)
    if not price_before:
        log(f"Cannot get price for {symbol}")
        return
    
    # LIQUIDITY CHECK — don't buy illiquid tokens
    mint = MINT_ADDRESSES.get(symbol)
    if mint:
        try:
            import urllib.request as _lr
            liq_url = f"{DEXSCREENER}/{mint}"
            liq_req = _lr.Request(liq_url, headers={"User-Agent": "MemeTrader/1.0"})
            with _lr.urlopen(liq_req, timeout=10) as liq_resp:
                liq_data = json.loads(liq_resp.read().decode())
                if isinstance(liq_data, list) and liq_data:
                    liquidity = liq_data[0].get("liquidity", {}).get("usd", 0)
                    if liquidity < 2_000_000:
                        log(f"BLOCKED: {symbol} liquidity ${liquidity/1e3:.0f}K < $2M minimum. Hard to exit.")
                        return
                    log(f"Liquidity check: ${liquidity/1e6:.1f}M ✅")
        except Exception as e:
            log(f"Liquidity check failed: {e} — proceeding with caution")
    
    log(f"BUYING {symbol} for ${amount_usd}...")
    
    out, code = tm_buy(symbol, amount_usd)
    print(out)
    
    if code != 0 or "Trade submitted" not in out:
        log(f"BUY FAILED: {out}")
        return
    
    # Parse actual tokens received from tm output: "You receive:  2073.271084 DADDY"
    tokens_received = 0
    actual_cost = float(amount_usd)
    for line in out.split("\n"):
        if "You receive:" in line:
            try:
                tokens_received = float(line.split()[-2])
            except:
                pass
        if "Fee:" in line:
            try:
                fee_amt = float(line.split()[-2])
                actual_cost = float(amount_usd) + fee_amt
            except:
                pass
    
    # Wait and verify balance
    time.sleep(3)
    balances = get_balances()
    tokens = balances.get(symbol, tokens_received)
    
    if tokens <= 0:
        log(f"BUY may have failed — no {symbol} balance found")
        return
    
    # Calculate TRUE entry price from what we actually paid and received
    true_entry_price = actual_cost / tokens if tokens > 0 else 0
    
    # Register position
    positions = load_positions()
    positions[symbol] = {
        "entry_price": true_entry_price,
        "tokens": tokens,
        "cost_usd": float(amount_usd),
        "entry_time": datetime.now(timezone.utc).isoformat(),
        "high_price": price_before,
        "trailing_active": False,
    }
    save_positions(positions)
    
    log(f"POSITION OPENED: {tokens:.4f} {symbol} @ ${price_before:.6f} (${amount_usd})")
    log(f"  Take profit: ${price_before * (1 + TAKE_PROFIT_PCT):.6f} (+{TAKE_PROFIT_PCT*100:.0f}%)")
    log(f"  Stop loss:   ${price_before * (1 + STOP_LOSS_PCT):.6f} ({STOP_LOSS_PCT*100:.0f}%)")
    log(f"  Time stop:   {TIME_STOP_MINUTES} minutes")
    
    log_trade({
        "action": "BUY", "symbol": symbol, "price": price_before,
        "tokens": tokens, "cost": float(amount_usd),
        "time": datetime.now(timezone.utc).isoformat(),
    })


def cmd_sell(symbol):
    """Manually sell all of a coin."""
    symbol = symbol.upper()
    
    price = get_price(symbol)
    out, code = tm_sell(symbol)
    print(out)
    
    # Remove from positions
    positions = load_positions()
    pos = positions.pop(symbol, None)
    save_positions(positions)
    
    if pos and price:
        pnl = (price - pos["entry_price"]) / pos["entry_price"] * 100
        log(f"SOLD {symbol} @ ${price:.6f} | P&L: {pnl:+.1f}%")
        log_trade({
            "action": "SELL", "symbol": symbol, "price": price,
            "entry_price": pos["entry_price"], "pnl_pct": round(pnl, 2),
            "reason": "manual",
            "time": datetime.now(timezone.utc).isoformat(),
        })


def cmd_positions():
    """Show current positions with P&L."""
    positions = load_positions()
    balances = get_balances()
    
    if not positions and not balances:
        print("No open positions")
        return
    
    symbols = list(set(list(positions.keys()) + [s for s in balances if s != "USDC"]))
    if not symbols:
        print("No open positions (USDC only)")
        return
    
    prices = get_prices_batch(symbols)
    
    print(f"\n{'Symbol':<10} {'Tokens':>10} {'Entry':>10} {'Current':>10} {'P&L':>8} {'Time':>8}")
    print("-" * 60)
    
    total_cost = 0
    total_value = 0
    
    for sym in symbols:
        pos = positions.get(sym, {})
        bal = balances.get(sym, 0)
        price_info = prices.get(sym, {})
        cur_price = price_info.get("price", 0)
        entry = pos.get("entry_price", cur_price)
        tokens = pos.get("tokens", bal)
        cost = pos.get("cost_usd", 0)
        
        if entry and cur_price:
            pnl_pct = (cur_price - entry) / entry * 100
            value = tokens * cur_price
            total_cost += cost
            total_value += value
            
            entry_time = pos.get("entry_time", "")
            if entry_time:
                try:
                    dt = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                    mins = (datetime.now(timezone.utc) - dt).total_seconds() / 60
                    time_str = f"{mins:.0f}m"
                except:
                    time_str = "?"
            else:
                time_str = "?"
            
            src = price_info.get("source", "cg")[:5]
            print(f"{sym:<10} {tokens:>10.2f} ${entry:>8.4f} ${cur_price:>8.4f} {pnl_pct:>+7.1f}% {time_str:>8} [{src}]")
    
    if total_cost > 0:
        total_pnl = total_value - total_cost
        print(f"\nTotal invested: ${total_cost:.2f} | Current value: ${total_value:.2f} | P&L: ${total_pnl:+.2f}")


def cmd_monitor():
    """Monitor positions and auto-exit on triggers."""
    # Start Binance WS for real-time prices
    start_binance_ws()
    time.sleep(2)  # Let WS connect
    
    log("MONITOR started — watching positions for exit signals")
    log(f"  Take profit: +{TAKE_PROFIT_PCT*100:.0f}% | Stop loss: {STOP_LOSS_PCT*100:.0f}% | Trail: {TRAILING_STOP_PCT*100:.0f}% (after +{TRAILING_ACTIVATE*100:.0f}%)")
    log(f"  Time stop: {TIME_STOP_MINUTES} min | Poll: {POLL_INTERVAL}s")
    log(f"  Price feeds: Binance WS ({len(BINANCE_PAIRS)} coins) + tm quotes (all others)")
    
    while True:
        positions = load_positions()
        
        if not positions:
            log("No positions to monitor. Waiting...")
            time.sleep(30)
            continue
        
        symbols = list(positions.keys())
        prices = get_prices_batch(symbols)
        
        for sym in symbols:
            pos = positions[sym]
            price_info = prices.get(sym, {})
            cur_price = price_info.get("price", 0)
            
            if not cur_price:
                continue
            
            entry = pos["entry_price"]
            pnl_pct = (cur_price - entry) / entry
            
            # Update high water mark
            if cur_price > pos.get("high_price", 0):
                pos["high_price"] = cur_price
            
            # Check time stop
            entry_time = pos.get("entry_time", "")
            mins_held = 0
            if entry_time:
                try:
                    dt = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                    mins_held = (datetime.now(timezone.utc) - dt).total_seconds() / 60
                except:
                    pass
            
            sell_reason = None
            
            # 0. Quick flip — even a small gain in first 2 min = take it
            if pnl_pct >= 0.03 and mins_held < 2:
                sell_reason = f"QUICK FLIP +{pnl_pct*100:.1f}% in {mins_held:.0f}m"
            
            # 1. Take profit
            elif pnl_pct >= TAKE_PROFIT_PCT:
                sell_reason = f"TAKE PROFIT +{pnl_pct*100:.1f}%"
            
            # 2. Stop loss — wide at first (let it breathe), tighten over time
            #    First 20 min: -20% (absorb spread + volatility)
            #    After 20 min: -8% (real stop)
            if mins_held < 20:
                active_stop = -0.20  # Wide stop — don't panic sell on spread
            else:
                active_stop = STOP_LOSS_PCT  # -8% tightened stop
            
            if pnl_pct <= active_stop and mins_held >= (GRACE_PERIOD_SECONDS / 60):
                sell_reason = f"STOP LOSS {pnl_pct*100:.1f}% (limit was {active_stop*100:.0f}%)"
            
            # 3. Trailing stop
            elif pnl_pct >= TRAILING_ACTIVATE:
                pos["trailing_active"] = True
                drop_from_high = (cur_price - pos["high_price"]) / pos["high_price"]
                if drop_from_high <= -TRAILING_STOP_PCT:
                    sell_reason = f"TRAILING STOP (high ${pos['high_price']:.6f}, dropped {drop_from_high*100:.1f}%)"
            
            # 4. Time stop
            elif mins_held >= TIME_STOP_MINUTES:
                sell_reason = f"TIME STOP ({mins_held:.0f}m held)"
            
            if sell_reason:
                log(f"EXIT {sym}: {sell_reason}")
                log(f"  Entry: ${entry:.6f} | Current: ${cur_price:.6f} | P&L: {pnl_pct*100:+.1f}%")
                
                # Execute sell
                out, code = tm_sell(sym)
                if code == 0:
                    log(f"  SOLD: {out[:80]}")
                    
                    # Alert
                    pnl_usd = pos.get("cost_usd", 0) * pnl_pct
                    alert = f"{'🟢' if pnl_pct > 0 else '🔴'} {sym} {sell_reason}\nEntry ${entry:.4f} → ${cur_price:.4f}\nP&L: {pnl_pct*100:+.1f}% (${pnl_usd:+.2f})"
                    send_alert(alert)
                    
                    lr = log_return(entry, cur_price)
                    log_trade({
                        "action": "SELL", "symbol": sym, "price": cur_price,
                        "entry_price": entry, "pnl_pct": round(pnl_pct * 100, 2),
                        "pnl_usd": round(pnl_usd, 2),
                        "log_return": round(lr, 6),
                        "reason": sell_reason, "mins_held": round(mins_held, 1),
                        "time": datetime.now(timezone.utc).isoformat(),
                    })
                else:
                    log(f"  SELL FAILED: {out}")
                
                # Remove position
                positions.pop(sym, None)
            else:
                # Status update
                trail = " [TRAILING]" if pos.get("trailing_active") else ""
                src = price_info.get("source", "?")[:6]
                log(f"  {sym}: ${cur_price:.6f} | {pnl_pct*100:+.1f}% | {mins_held:.0f}m{trail} [{src}]")
        
        save_positions(positions)
        time.sleep(POLL_INTERVAL)


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  meme-trader.py buy SYMBOL AMOUNT    # Buy $AMOUNT of SYMBOL")
        print("  meme-trader.py sell SYMBOL           # Sell all SYMBOL")
        print("  meme-trader.py monitor               # Auto-exit monitor")
        print("  meme-trader.py positions             # Show positions + P&L")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "buy" and len(sys.argv) >= 4:
        cmd_buy(sys.argv[2], sys.argv[3])
    elif cmd == "sell" and len(sys.argv) >= 3:
        cmd_sell(sys.argv[2])
    elif cmd == "monitor":
        cmd_monitor()
    elif cmd == "positions":
        cmd_positions()
    else:
        print(f"Unknown command: {cmd}")
