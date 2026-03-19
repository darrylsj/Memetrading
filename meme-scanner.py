#!/usr/bin/env python3
"""
meme-scanner.py — Scan True Markets coins for momentum signals.

Signals that move meme coins:
  1. Volume spike (24h vol vs 7d avg) — early pump detection
  2. Price momentum (1h, 4h, 24h changes)
  3. CoinGecko trending rank
  4. Market cap vs volume ratio (high vol/mcap = attention)
  5. Holder growth (on-chain, if available)

Outputs ranked buy candidates for quick flip trades.
"""

import json
import time
import urllib.request
import urllib.parse
import sys
from datetime import datetime

COINGECKO = "https://api.coingecko.com/api/v3"
UA = "MemeScannerBot/1.0"

# All meme/small coins on True Markets (Solana)
# Extracted from `tm assets`
TM_COINS = {
    # High-cap memes
    "BONK": "bonk", "WIF": "dogwifhat", "POPCAT": "popcat-sol",
    "PENGU": "pudgy-penguins", "FARTCOIN": "fartcoin",
    "TRUMP": "official-trump", "MELANIA": "official-melania-meme",
    "PNUT": "peanut-the-squirrel", "MOODENG": "moo-deng",
    "GOAT": "goatseus-maximus", "MEW": "cat-in-a-dogs-world",
    "GIGA": "gigachad-2", "PONKE": "ponke",
    "BOME": "book-of-meme", "SPX": "spx6900",
    "SLERF": "slerf", "MYRO": "myro",
    
    # Mid-cap memes/AI
    "JELLYJELLY": "jelly-my-jelly", "VINE": "vine-coin",
    "VIRTUAL": "virtual-protocol", "AI16Z": "ai16z",
    "GRIFFAIN": "griffain", "ZEREBRO": "zerebro",
    "SWARMS": "swarms", "RETARDIO": "retardio",
    "MICHI": "michi", "CHILLGUY": "just-a-chill-guy",
    "DADDY": "daddy-tate", "FWOG": "fwog",
    
    # Trending/new
    "LAUNCHCOIN": "launchcoin-on-believe", "HYPE": "hyperliquid",
    "MON": "monad", "USA": "american-coin",
    "HOUSE": "housecoin", "BAN": "comedian",
    "SIGMA": "sigma-2", "TITCOIN": "titcoin",
    
    # DeFi/infra on TM
    "SOL": "solana", "JUP": "jupiter-exchange-solana",
    "RAY": "raydium", "DRIFT": "drift-protocol",
    "ORCA": "orca", "PYTH": "pyth-network",
    "JTO": "jito-governance-token", "RENDER": "render-token",
    "GRASS": "grass", "HNT": "helium",
    "W": "wormhole", "IO": "io-net",
    
    # Base tokens
    "BRETT": "brett-based", "DEGEN": "degen-base",
    "AERO": "aerodrome-finance", "TOSHI": "toshi-base",
    "KAITO": "kaito-2",
}


def fetch(url, retries=2):
    """Fetch JSON with retry and rate limiting."""
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            time.sleep(1.5)  # CoinGecko rate limit
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
            else:
                return None
    return None


def scan_all_coins():
    """Fetch market data for all TM coins in batches."""
    ids = list(TM_COINS.values())
    all_data = []
    
    # CoinGecko allows up to 250 ids per request
    batch_size = 50
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i+batch_size]
        ids_str = ",".join(batch)
        url = (f"{COINGECKO}/coins/markets?vs_currency=usd&ids={ids_str}"
               f"&order=market_cap_desc&per_page={batch_size}&page=1"
               f"&sparkline=false&price_change_percentage=1h,24h,7d")
        
        data = fetch(url)
        if data:
            all_data.extend(data)
        print(f"  Fetched batch {i//batch_size + 1}: {len(data or [])} coins", file=sys.stderr)
    
    return all_data


def get_trending():
    """Get CoinGecko trending coins."""
    data = fetch(f"{COINGECKO}/search/trending")
    if not data:
        return set()
    trending = set()
    for coin in data.get("coins", []):
        item = coin.get("item", {})
        cg_id = item.get("id", "")
        trending.add(cg_id)
    return trending


def score_coin(coin, trending_ids):
    """
    Score a coin for meme momentum (0-100).
    
    Signals:
    - Volume spike: 24h volume relative to market cap
    - Price momentum: 1h and 24h price changes
    - Trending: CoinGecko trending bonus
    - Volume/MCap ratio: High ratio = unusual activity
    """
    score = 50  # Baseline
    reasons = []
    
    mcap = coin.get("market_cap", 0) or 0
    volume = coin.get("total_volume", 0) or 0
    price = coin.get("current_price", 0) or 0
    change_1h = coin.get("price_change_percentage_1h_in_currency", 0) or 0
    change_24h = coin.get("price_change_percentage_24h", 0) or 0
    change_7d = coin.get("price_change_percentage_7d_in_currency", 0) or 0
    cg_id = coin.get("id", "")
    
    # Volume/MCap ratio (normal is 0.05-0.15, spike is 0.3+)
    vol_mcap = volume / mcap if mcap > 0 else 0
    if vol_mcap > 0.5:
        score += 20
        reasons.append(f"vol/mcap={vol_mcap:.2f} EXTREME")
    elif vol_mcap > 0.3:
        score += 12
        reasons.append(f"vol/mcap={vol_mcap:.2f} HIGH")
    elif vol_mcap > 0.15:
        score += 5
        reasons.append(f"vol/mcap={vol_mcap:.2f}")
    
    # 1h momentum
    if change_1h > 10:
        score += 15
        reasons.append(f"1h +{change_1h:.1f}% PUMPING")
    elif change_1h > 5:
        score += 10
        reasons.append(f"1h +{change_1h:.1f}%")
    elif change_1h > 2:
        score += 5
        reasons.append(f"1h +{change_1h:.1f}%")
    elif change_1h < -10:
        score -= 10
        reasons.append(f"1h {change_1h:.1f}% DUMPING")
    elif change_1h < -5:
        score -= 5
        reasons.append(f"1h {change_1h:.1f}%")
    
    # 24h momentum
    if change_24h > 20:
        score += 15
        reasons.append(f"24h +{change_24h:.1f}% SURGING")
    elif change_24h > 10:
        score += 10
        reasons.append(f"24h +{change_24h:.1f}%")
    elif change_24h > 5:
        score += 5
        reasons.append(f"24h +{change_24h:.1f}%")
    elif change_24h < -15:
        # Big dump could mean bounce opportunity
        score += 3
        reasons.append(f"24h {change_24h:.1f}% OVERSOLD?")
    elif change_24h < -5:
        score -= 5
        reasons.append(f"24h {change_24h:.1f}%")
    
    # 7d trend (context)
    if change_7d and change_7d > 30:
        score += 5
        reasons.append(f"7d +{change_7d:.0f}% HOT")
    elif change_7d and change_7d < -30:
        reasons.append(f"7d {change_7d:.0f}% COLD")
    
    # Trending bonus
    if cg_id in trending_ids:
        score += 15
        reasons.append("TRENDING on CoinGecko")
    
    # Absolute volume (liquidity check)
    if volume > 100_000_000:
        score += 5
        reasons.append(f"vol=${volume/1e6:.0f}M deep")
    elif volume < 1_000_000:
        score -= 10
        reasons.append(f"vol=${volume/1e3:.0f}K thin")
    elif volume < 5_000_000:
        score -= 3
        reasons.append(f"vol=${volume/1e6:.1f}M low")
    
    # MCap tier (smaller = more explosive)
    if mcap < 50_000_000:
        score += 5
        reasons.append("micro-cap")
    elif mcap < 200_000_000:
        score += 3
        reasons.append("small-cap")
    
    # Liquidity penalty — can't exit if pool is too thin
    # (liquidity data from CoinGecko is limited, DexScreener is better)
    # Flag for manual check
    if mcap < 10_000_000 and volume < 2_000_000:
        score -= 10
        reasons.append("LOW LIQ WARNING")
    
    # Clamp
    score = max(0, min(100, score))
    
    return {
        "symbol": coin.get("symbol", "?").upper(),
        "name": coin.get("name", "?"),
        "price": price,
        "mcap": mcap,
        "volume_24h": volume,
        "vol_mcap_ratio": round(vol_mcap, 3),
        "change_1h": round(change_1h, 2),
        "change_24h": round(change_24h, 2),
        "change_7d": round(change_7d or 0, 2),
        "trending": cg_id in trending_ids,
        "score": score,
        "signals": reasons,
        "action": "BUY" if score >= 70 else ("WATCH" if score >= 55 else "SKIP"),
    }


def main():
    print(f"=== MEME COIN MOMENTUM SCANNER ===")
    print(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Scanning {len(TM_COINS)} True Markets coins...")
    print()
    
    # Get trending
    trending = get_trending()
    print(f"CoinGecko trending: {len(trending)} coins")
    
    # Scan all coins
    market_data = scan_all_coins()
    print(f"Got data for {len(market_data)} coins")
    print()
    
    # Score everything
    scored = []
    tm_ids = set(TM_COINS.values())
    for coin in market_data:
        if coin.get("id") in tm_ids:
            result = score_coin(coin, trending)
            scored.append(result)
    
    # Sort by score
    scored.sort(key=lambda x: -x["score"])
    
    # Output
    print("=" * 90)
    print(f"{'Rank':>4} {'Symbol':<12} {'Price':>10} {'1h':>7} {'24h':>7} {'Vol/MCap':>8} {'Score':>5} {'Action':<6} Signals")
    print("-" * 90)
    
    for i, coin in enumerate(scored[:30], 1):
        sym = coin["symbol"]
        price_str = f"${coin['price']:.4f}" if coin["price"] < 0.01 else f"${coin['price']:.2f}"
        signals = ", ".join(coin["signals"][:3])
        print(f"{i:>4} {sym:<12} {price_str:>10} {coin['change_1h']:>+6.1f}% {coin['change_24h']:>+6.1f}% "
              f"{coin['vol_mcap_ratio']:>7.3f} {coin['score']:>5} {coin['action']:<6} {signals}")
    
    # BUY recommendations
    buys = [c for c in scored if c["action"] == "BUY"]
    if buys:
        print(f"\n{'='*60}")
        print(f"BUY CANDIDATES ({len(buys)} coins scoring 70+):")
        print(f"{'='*60}")
        for c in buys:
            print(f"\n  {c['symbol']} @ ${c['price']:.4f}" if c['price'] < 0.01 else f"\n  {c['symbol']} @ ${c['price']:.2f}")
            print(f"    Score: {c['score']}/100 | MCap: ${c['mcap']/1e6:.0f}M | Vol: ${c['volume_24h']/1e6:.0f}M")
            print(f"    1h: {c['change_1h']:+.1f}% | 24h: {c['change_24h']:+.1f}% | 7d: {c['change_7d']:+.1f}%")
            print(f"    Signals: {', '.join(c['signals'])}")
    else:
        print("\nNo strong BUY signals right now. Market may be cooling.")
    
    # Bounce candidates (big dump = potential reversal)
    bounces = [c for c in scored if c["change_24h"] < -10 and c["volume_24h"] > 5_000_000]
    if bounces:
        print(f"\nBOUNCE CANDIDATES (oversold with volume):")
        for c in bounces[:5]:
            print(f"  {c['symbol']} {c['change_24h']:+.1f}% 24h | vol=${c['volume_24h']/1e6:.0f}M")
    
    # Save results
    output = {
        "timestamp": datetime.utcnow().isoformat(),
        "coins_scanned": len(scored),
        "buy_candidates": [c for c in scored if c["action"] == "BUY"],
        "watch_list": [c for c in scored if c["action"] == "WATCH"],
        "top_10": scored[:10],
        "bounce_candidates": bounces[:5] if bounces else [],
    }
    
    with open("/tmp/meme-scan-latest.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nFull results saved to /tmp/meme-scan-latest.json")


if __name__ == "__main__":
    main()
