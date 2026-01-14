#!/usr/bin/env python3
"""Proper analysis with live Questrade prices."""
import sys
sys.path.insert(0, '/app')
from investor_agent.database import execute_query
from investor_agent.questrade import QuestradeClient

# Get all unique predictions (deduplicated by ticker+direction)
query = """
    SELECT
        ticker, direction, entry_price, signal, confidence_score,
        gates_passed, always_in, data_direction, dalio_interpretation,
        cvd_trend, created_at
    FROM predictions
    ORDER BY created_at DESC
"""
rows = execute_query(query)

# Deduplicate - keep first (most recent) per ticker+direction
seen = set()
predictions = []
for r in rows:
    key = f"{r['ticker']}_{r['direction']}"
    if key not in seen:
        seen.add(key)
        predictions.append(r)

print(f"Unique predictions: {len(predictions)}")

# Get unique tickers
tickers = list(set(p['ticker'] for p in predictions))
print(f"Unique tickers: {len(tickers)}")

# Fetch live prices from Questrade in batches
print("\nFetching live prices from Questrade...")
client = QuestradeClient()
price_map = {}

batch_size = 50
for i in range(0, len(tickers), batch_size):
    batch = tickers[i:i+batch_size]
    try:
        quotes = client.get_quotes(batch)
        for q in quotes.get('quotes', []):
            symbol = q.get('symbol')
            price = q.get('lastTradePrice') or q.get('bidPrice') or 0
            price_map[symbol] = price
        print(f"  Batch {i//batch_size + 1}: got {len(quotes.get('quotes', []))} prices")
    except Exception as e:
        print(f"  Error fetching batch {i}: {e}")

print(f"Total prices fetched: {len(price_map)}")

# Calculate returns
results = []
missing_prices = []
for p in predictions:
    ticker = p['ticker']
    direction = p['direction']
    entry = float(p['entry_price'])
    current = price_map.get(ticker, 0)

    if current == 0:
        missing_prices.append(ticker)
        continue
    if entry == 0:
        continue

    # Calculate profit (positive = made money)
    if direction == "LONG":
        profit_pct = ((current - entry) / entry) * 100
    else:  # SHORT
        profit_pct = ((entry - current) / entry) * 100

    results.append({
        'ticker': ticker,
        'direction': direction,
        'entry': entry,
        'current': current,
        'profit': profit_pct,
        'signal': p['signal'],
        'confidence': p['confidence_score'],
        'gates': p['gates_passed'],
        'brooks': p['always_in'],
        'data_dir': p['data_direction'],
        'dalio': p['dalio_interpretation']
    })

if missing_prices:
    print(f"\nMissing prices for: {missing_prices[:10]}...")

print(f"\n{'='*70}")
print(f"LIVE QUESTRADE ANALYSIS - {len(results)} predictions")
print(f"{'='*70}")

# Overall stats
total = len(results)
if total == 0:
    print("No results to analyze!")
    sys.exit(1)

winners = [r for r in results if r['profit'] > 0]
losers = [r for r in results if r['profit'] < 0]
total_profit = sum(r['profit'] for r in results)

print(f"\nOVERALL PERFORMANCE")
print("-"*70)
print(f"Total trades:    {total}")
print(f"Winners:         {len(winners)} ({len(winners)/total*100:.1f}%)")
print(f"Losers:          {len(losers)} ({len(losers)/total*100:.1f}%)")
print(f"Total P&L:       {total_profit:+.2f}%")
print(f"Avg per trade:   {total_profit/total:+.2f}%")

# By direction
long_results = [r for r in results if r['direction'] == 'LONG']
short_results = [r for r in results if r['direction'] == 'SHORT']

print(f"\nBY DIRECTION")
print("-"*70)
if long_results:
    long_profit = sum(r['profit'] for r in long_results)
    long_winners = sum(1 for r in long_results if r['profit'] > 0)
    print(f"LONG:  {len(long_results):3} trades | Win: {long_winners:3} ({long_winners/len(long_results)*100:5.1f}%) | P&L: {long_profit:+8.2f}% | Avg: {long_profit/len(long_results):+.2f}%")
if short_results:
    short_profit = sum(r['profit'] for r in short_results)
    short_winners = sum(1 for r in short_results if r['profit'] > 0)
    print(f"SHORT: {len(short_results):3} trades | Win: {short_winners:3} ({short_winners/len(short_results)*100:5.1f}%) | P&L: {short_profit:+8.2f}% | Avg: {short_profit/len(short_results):+.2f}%")

# TOP 15 WINNERS
print(f"\nTOP 15 WINNERS")
print("-"*70)
for r in sorted(results, key=lambda x: x['profit'], reverse=True)[:15]:
    print(f"{r['ticker']:6} | {r['direction']:5} | ${r['entry']:7.2f} -> ${r['current']:7.2f} | {r['profit']:+6.2f}% | {r['signal']:12} | G:{r['gates']}")

# TOP 15 LOSERS
print(f"\nTOP 15 LOSERS")
print("-"*70)
for r in sorted(results, key=lambda x: x['profit'])[:15]:
    print(f"{r['ticker']:6} | {r['direction']:5} | ${r['entry']:7.2f} -> ${r['current']:7.2f} | {r['profit']:+6.2f}% | {r['signal']:12} | G:{r['gates']}")

# By Gates Passed
print(f"\nBY GATES PASSED")
print("-"*70)
for gates in [4, 3, 2, 1, 0, None]:
    gate_results = [r for r in results if r['gates'] == gates]
    if gate_results:
        gate_profit = sum(r['profit'] for r in gate_results)
        gate_winners = sum(1 for r in gate_results if r['profit'] > 0)
        g = gates if gates is not None else "None"
        print(f"Gates={g}: {len(gate_results):3} trades | Win: {gate_winners:3} ({gate_winners/len(gate_results)*100:5.1f}%) | Avg: {gate_profit/len(gate_results):+.2f}%")

# By Signal Type
print(f"\nBY SIGNAL TYPE")
print("-"*70)
signals = set(r['signal'] for r in results)
for sig in sorted(signals, key=lambda x: str(x)):
    sig_results = [r for r in results if r['signal'] == sig]
    if sig_results:
        sig_profit = sum(r['profit'] for r in sig_results)
        sig_winners = sum(1 for r in sig_results if r['profit'] > 0)
        s = sig if sig else "None"
        print(f"{s:12}: {len(sig_results):3} trades | Win: {sig_winners:3} ({sig_winners/len(sig_results)*100:5.1f}%) | Avg: {sig_profit/len(sig_results):+.2f}%")
