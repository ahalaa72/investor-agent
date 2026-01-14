#!/usr/bin/env python3
"""Analyze predictions before/after fix."""
import sys
sys.path.insert(0, '/app')
from investor_agent.database import execute_query

# Get all predictions with outcomes
query = """
    SELECT
        ticker,
        direction,
        signal,
        confidence_score,
        gates_passed,
        entry_price,
        return_5d,
        return_10d,
        return_20d,
        outcome,
        catalyst_direction,
        cvd_trend,
        always_in,
        fresh_direction,
        dalio_interpretation,
        data_direction,
        vote_brooks,
        vote_catalyst,
        vote_cvd,
        created_at
    FROM predictions
    WHERE outcome IS NOT NULL
    ORDER BY created_at DESC
"""

rows = execute_query(query)
print(f"Total predictions with outcomes: {len(rows)}")

# Analyze each prediction
results = []
for row in rows:
    ticker = row['ticker']
    direction = row['direction']
    signal = row['signal']
    confidence = row['confidence_score']
    gates = row['gates_passed']
    r20 = row['return_20d']
    outcome = row['outcome']
    cat_dir = row['catalyst_direction']
    cvd = row['cvd_trend']
    brooks = row['always_in']  # Brooks direction is stored in always_in
    fresh = row['fresh_direction']
    dalio = row['dalio_interpretation']
    data_dir = row['data_direction']
    vote_brooks = row['vote_brooks']
    vote_catalyst = row['vote_catalyst']

    # NEW RULE: if Brooks=NEUTRAL and Catalyst=NEUTRAL -> NO_TRADE
    brooks_str = str(brooks).upper() if brooks else 'NONE'
    catalyst_str = str(cat_dir).upper() if cat_dir else 'NONE'
    vote_brooks_str = str(vote_brooks).upper() if vote_brooks else 'NONE'
    vote_catalyst_str = str(vote_catalyst).upper() if vote_catalyst else 'NONE'
    data_dir_str = str(data_dir).upper() if data_dir else 'NONE'

    brooks_neutral = vote_brooks_str in ['NONE', 'NEUTRAL', '']
    catalyst_neutral = vote_catalyst_str in ['NONE', 'NEUTRAL', '']

    would_be_no_trade = brooks_neutral and catalyst_neutral

    # Check for direction mismatch (trade went opposite to Brooks)
    direction_mismatch = False
    if direction == 'LONG' and brooks_str == 'SHORT':
        direction_mismatch = True
    elif direction == 'SHORT' and brooks_str == 'LONG':
        direction_mismatch = True

    # Check if data_direction disagreed with trade direction (NEW CHECK)
    data_direction_conflict = False
    if data_dir_str not in ['NONE', 'NO_CONSENSUS', '']:
        if direction == 'LONG' and data_dir_str == 'SHORT':
            data_direction_conflict = True
        elif direction == 'SHORT' and data_dir_str == 'LONG':
            data_direction_conflict = True

    results.append({
        'ticker': ticker,
        'direction': direction,
        'signal': signal,
        'confidence': confidence or 0,
        'gates': gates or 0,
        'outcome': outcome,
        'return_20d': float(r20) if r20 else 0,
        'brooks': brooks_str,
        'catalyst': catalyst_str,
        'cvd': cvd,
        'dalio': dalio,
        'vote_brooks': vote_brooks_str,
        'vote_catalyst': vote_catalyst_str,
        'data_direction': data_dir_str,
        'would_be_no_trade': would_be_no_trade,
        'direction_mismatch': direction_mismatch,
        'data_direction_conflict': data_direction_conflict
    })

# Calculate stats
total = len(results)
wins = sum(1 for r in results if r['outcome'] == 'WIN')
losses = sum(1 for r in results if r['outcome'] == 'LOSS')

# OLD SYSTEM stats
old_win_rate = (wins / total * 100) if total > 0 else 0
old_avg_return = sum(r['return_20d'] for r in results) / total if total > 0 else 0

print(f"\n{'='*60}")
print(f"OLD SYSTEM (ALL PREDICTIONS)")
print(f"{'='*60}")
print(f"Total Predictions: {total}")
print(f"Wins: {wins}")
print(f"Losses: {losses}")
print(f"Win Rate: {old_win_rate:.1f}%")
print(f"Avg 20d Return: {old_avg_return:+.2f}%")

# Count by direction
long_results = [r for r in results if r['direction'] == 'LONG']
short_results = [r for r in results if r['direction'] == 'SHORT']
long_wins = sum(1 for r in long_results if r['outcome'] == 'WIN')
short_wins = sum(1 for r in short_results if r['outcome'] == 'WIN')

print(f"\nBy Direction:")
if long_results:
    print(f"  LONG:  {len(long_results)} trades, {long_wins} wins ({long_wins/len(long_results)*100:.1f}% win rate)")
if short_results:
    print(f"  SHORT: {len(short_results)} trades, {short_wins} wins ({short_wins/len(short_results)*100:.1f}% win rate)")

# NEW SYSTEM - filter out would-be NO_TRADE
filtered_out = [r for r in results if r['would_be_no_trade']]
new_results = [r for r in results if not r['would_be_no_trade']]

print(f"\n{'='*60}")
print(f"FILTERED OUT (would be NO_TRADE under new rules)")
print(f"{'='*60}")
print(f"Total filtered: {len(filtered_out)}")
if filtered_out:
    filtered_wins = sum(1 for r in filtered_out if r['outcome'] == 'WIN')
    filtered_losses = sum(1 for r in filtered_out if r['outcome'] == 'LOSS')
    filtered_avg_return = sum(r['return_20d'] for r in filtered_out) / len(filtered_out)
    print(f"Wins in filtered: {filtered_wins}")
    print(f"Losses in filtered: {filtered_losses}")
    print(f"Win rate of filtered: {filtered_wins/len(filtered_out)*100:.1f}%")
    print(f"Avg return of filtered: {filtered_avg_return:+.2f}%")
    print(f"\n*** These bad trades would NOT have been taken under new rules ***")

# NEW SYSTEM stats
new_total = len(new_results)
new_wins = sum(1 for r in new_results if r['outcome'] == 'WIN')
new_losses = sum(1 for r in new_results if r['outcome'] == 'LOSS')
new_win_rate = (new_wins / new_total * 100) if new_total > 0 else 0
new_avg_return = sum(r['return_20d'] for r in new_results) / new_total if new_total > 0 else 0

print(f"\n{'='*60}")
print(f"NEW SYSTEM (after fix)")
print(f"{'='*60}")
print(f"Total Predictions: {new_total}")
print(f"Wins: {new_wins}")
print(f"Losses: {new_losses}")
print(f"Win Rate: {new_win_rate:.1f}%")
print(f"Avg 20d Return: {new_avg_return:+.2f}%")

print(f"\n{'='*60}")
print(f"IMPROVEMENT SUMMARY")
print(f"{'='*60}")
print(f"Win Rate: {old_win_rate:.1f}% -> {new_win_rate:.1f}% ({new_win_rate - old_win_rate:+.1f}%)")
print(f"Avg Return: {old_avg_return:+.2f}% -> {new_avg_return:+.2f}% ({new_avg_return - old_avg_return:+.2f}%)")
print(f"Bad Trades Avoided: {len(filtered_out)}")

# Show the worst losses that would have been filtered
if filtered_out:
    print(f"\n{'='*60}")
    print(f"TOP LOSSES THAT WOULD BE FILTERED (saved money)")
    print(f"{'='*60}")
    filtered_losses_list = sorted([r for r in filtered_out if r['outcome'] == 'LOSS'], key=lambda x: x['return_20d'])
    for r in filtered_losses_list[:15]:
        print(f"{r['ticker']:6} | {r['direction']:5} | Return: {r['return_20d']:+6.2f}% | Brooks:{r['brooks']:8} | Catalyst:{r['catalyst']:8}")

# Also check direction mismatch
mismatch_results = [r for r in results if r['direction_mismatch']]
print(f"\n{'='*60}")
print(f"DIRECTION MISMATCH (Trade direction vs Brooks signal)")
print(f"{'='*60}")
print(f"Total mismatches: {len(mismatch_results)}")
if mismatch_results:
    mismatch_wins = sum(1 for r in mismatch_results if r['outcome'] == 'WIN')
    mismatch_losses = sum(1 for r in mismatch_results if r['outcome'] == 'LOSS')
    mismatch_avg = sum(r['return_20d'] for r in mismatch_results) / len(mismatch_results)
    print(f"Wins: {mismatch_wins}, Losses: {mismatch_losses}")
    print(f"Win rate: {mismatch_wins/len(mismatch_results)*100:.1f}%")
    print(f"Avg return: {mismatch_avg:+.2f}%")
    print(f"\nThese trades went AGAINST the technical signal!")
    for r in sorted(mismatch_results, key=lambda x: x['return_20d'])[:10]:
        print(f"{r['ticker']:6} | Trade:{r['direction']:5} but Brooks:{r['brooks']:5} | {r['outcome']:4} | Return: {r['return_20d']:+6.2f}%")

# Show breakdown of Brooks directions
print(f"\n{'='*60}")
print(f"BROOKS DIRECTION BREAKDOWN")
print(f"{'='*60}")
brooks_counts = {}
for r in results:
    b = r['brooks']
    if b not in brooks_counts:
        brooks_counts[b] = {'total': 0, 'wins': 0, 'losses': 0, 'return': 0}
    brooks_counts[b]['total'] += 1
    if r['outcome'] == 'WIN':
        brooks_counts[b]['wins'] += 1
    else:
        brooks_counts[b]['losses'] += 1
    brooks_counts[b]['return'] += r['return_20d']

for b, stats in sorted(brooks_counts.items(), key=lambda x: -x[1]['total']):
    wr = stats['wins']/stats['total']*100 if stats['total'] > 0 else 0
    avg_ret = stats['return']/stats['total'] if stats['total'] > 0 else 0
    print(f"Brooks={b:8} | {stats['total']:3} trades | {stats['wins']:2}W/{stats['losses']:2}L | WinRate: {wr:5.1f}% | AvgRet: {avg_ret:+.2f}%")

# DATA DIRECTION CONFLICT analysis
conflict_results = [r for r in results if r['data_direction_conflict']]
print(f"\n{'='*60}")
print(f"DATA DIRECTION CONFLICT (Trade vs Data Direction)")
print(f"{'='*60}")
print(f"Total conflicts: {len(conflict_results)}")
if conflict_results:
    conflict_wins = sum(1 for r in conflict_results if r['outcome'] == 'WIN')
    conflict_losses = sum(1 for r in conflict_results if r['outcome'] == 'LOSS')
    conflict_avg = sum(r['return_20d'] for r in conflict_results) / len(conflict_results)
    print(f"Wins: {conflict_wins}, Losses: {conflict_losses}")
    print(f"Win rate: {conflict_wins/len(conflict_results)*100:.1f}%")
    print(f"Avg return: {conflict_avg:+.2f}%")
    print(f"\n*** THE BUG: These trades went OPPOSITE to what data suggested! ***")
    for r in sorted(conflict_results, key=lambda x: x['return_20d'])[:15]:
        print(f"{r['ticker']:6} | Trade:{r['direction']:5} but Data:{r['data_direction']:10} | {r['outcome']:4} | Return: {r['return_20d']:+6.2f}%")

# COMBINED filter (would_be_no_trade OR data_direction_conflict)
combined_filter = [r for r in results if r['would_be_no_trade'] or r['data_direction_conflict']]
combined_new = [r for r in results if not r['would_be_no_trade'] and not r['data_direction_conflict']]

print(f"\n{'='*60}")
print(f"COMBINED FIX (NO_TRADE + Direction Conflict Filter)")
print(f"{'='*60}")
print(f"Total would be filtered: {len(combined_filter)}")
if combined_filter:
    comb_wins = sum(1 for r in combined_filter if r['outcome'] == 'WIN')
    comb_losses = sum(1 for r in combined_filter if r['outcome'] == 'LOSS')
    comb_avg = sum(r['return_20d'] for r in combined_filter) / len(combined_filter)
    print(f"Filtered trades - Wins: {comb_wins}, Losses: {comb_losses}")
    print(f"Filtered Win Rate: {comb_wins/len(combined_filter)*100:.1f}%")
    print(f"Filtered Avg Return: {comb_avg:+.2f}%")

if combined_new:
    new2_wins = sum(1 for r in combined_new if r['outcome'] == 'WIN')
    new2_losses = sum(1 for r in combined_new if r['outcome'] == 'LOSS')
    new2_rate = new2_wins / len(combined_new) * 100
    new2_avg = sum(r['return_20d'] for r in combined_new) / len(combined_new)

    print(f"\nAfter Combined Filter:")
    print(f"Remaining trades: {len(combined_new)}")
    print(f"Wins: {new2_wins}, Losses: {new2_losses}")
    print(f"Win Rate: {new2_rate:.1f}%")
    print(f"Avg Return: {new2_avg:+.2f}%")

print(f"\n{'='*60}")
print(f"FINAL COMPARISON")
print(f"{'='*60}")
print(f"OLD SYSTEM:      {total:3} trades | Win Rate: {old_win_rate:5.1f}% | Avg Return: {old_avg_return:+.2f}%")
print(f"NEW SYSTEM:      {new_total:3} trades | Win Rate: {new_win_rate:5.1f}% | Avg Return: {new_avg_return:+.2f}%")
if combined_new:
    print(f"COMBINED FIX:    {len(combined_new):3} trades | Win Rate: {new2_rate:5.1f}% | Avg Return: {new2_avg:+.2f}%")
