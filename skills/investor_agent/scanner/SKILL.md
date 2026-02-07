---
name: scanner
description: Market opportunity discovery. Use when finding new LONG/SHORT trading opportunities, scanning for setups, detecting catalysts, finding unusual options activity, or tracking smart money flow. Filters through institutional validation before presenting candidates.
---

# Scanner - Market Opportunity Discovery

Scan the market for LONG and SHORT opportunities using institutional filters and 4-gate validation.

---

## ⚠️ Questrade Token Protection

**NEVER write Python scripts to scan or get quotes** - This consumes the single-use refresh token.

**ALWAYS use MCP tools:**

- `scan_long_candidates()` for LONG opportunities
- `scan_short_candidates()` for SHORT opportunities
- `get_questrade_quotes()` for real-time prices

If you get HTTP 400 errors, the token is consumed. See main SKILL.md for recovery steps.

---

## Workflow (CACHE-FIRST - MANDATORY)

### ALWAYS CHECK CACHE FIRST - DO NOT SKIP THIS STEP

### Step 1: Get Cached Candidates (INSTANT RESULTS)

```python
FIRST: get_best_cached_trades(direction="LONG/SHORT", days=7, top_n=5, min_gates=3)
  → Show these results IMMEDIATELY
  → User sees opportunities within seconds
```

### Step 2: Scan for NEW Candidates (BATCHES OF 20 with LIVE PROGRESS)

```python
THEN: scan_long_candidates() or scan_short_candidates()
  → Scans in batches of 20 stocks
  → Shows progress after EACH batch
  → NO HANGING for minutes without updates
```

### Complete Workflow

1. **Check Cache FIRST:** `get_best_cached_trades()` → Show immediately
2. **Scan NEW:** `scan_long_candidates()` / `scan_short_candidates()` → Batches of 20
3. **Verify Catalysts:** `detect_catalyst_strength(ticker)` for each candidate
4. **Detect Smart Money:** `detect_unusual_options_activity()` + `detect_insider_cluster()`
5. **Present:** Combined cached + new results, ranked by setup quality

## Key Tools

| Tool | Purpose |
|------|---------|
| `scan_long_candidates()` | Find bullish setups |
| `scan_short_candidates()` | Find bearish setups |
| `scan_market_opportunities()` | Both directions |
| `detect_catalyst_strength()` | Verify catalyst quality |
| `detect_unusual_options_activity()` | Options flow analysis |
| `detect_insider_cluster()` | Insider buying/selling patterns |

## Candidate Filters

### LONG Requirements
- RSI < 50 (not overbought)
- Brooks Always-In: LONG or transitioning
- Price above key support
- Catalyst strength ≥ 60%
- F-Score ≥ 6

### SHORT Requirements
- RSI > 50 (not oversold)
- Brooks Always-In: SHORT or transitioning
- Price below key resistance
- Catalyst strength ≥ 60%
- F-Score ≤ 4

## Catalyst Verification

**Types:** Earnings, Insider Activity, Analyst Upgrades, Institutional Buying, News Events

**Institutional Strength:**
- ≥ 60%: Trade-worthy
- < 60%: Skip (weak signal)

**Freshness:** Must be < 7 days old

## Smart Money Detection

**Unusual Options Activity:**
- Volume > 2x daily average
- Large block trades (> 500 contracts)
- P/C ratio changes

**Insider Clusters:**
- Bullish: 3+ insiders buying within 30 days
- Bearish: 3+ insiders selling within 30 days

## 4-Gate Validation for Candidates

| Gate | Weight | Passing |
|------|--------|---------|
| Catalyst | 15% | ≥ 60% strength |
| Freshness | 15% | Recent action supports direction |
| Brooks | 19.6% | Always-In aligned |
| Quality | 10% | F-Score appropriate for direction |

**Score Interpretation:**
- ≥ 70%: High-quality (prioritize)
- 50-70%: Moderate (consider)
- < 50%: Skip

## Output Format

For each candidate:
1. Symbol, price, direction
2. 4-gate score and signal
3. Catalyst type and strength
4. Brooks Always-In direction
5. Entry / Stop / Target levels
6. R:R ratio (must be ≥ 2:1)
7. Options strategy (if applicable)

## Examples

```
"Scan the market for opportunities"
"Find LONG candidates"
"Scan for SHORT setups"
"Find stocks with unusual options activity"
"Show me insider buying clusters"
```

## Post-Entry Management

**After entering a position found by scanner:**

| Position Type | Use Skill |
|--------------|-----------|
| Stock | Portfolio (4-gate validation) |
| Options | Position (5-rule management) |

```
Scanner → find opportunity
Trading → analyze + trade plan
Entry → execute
Stock? → Portfolio skill
Options? → Position skill
```

## Important Notes

- Scanner finds NEW opportunities only
- Use portfolio skill for existing positions
- Only trade setups with ≥ 60% catalyst strength
- Brooks alignment is critical
- Quality filters prevent value traps
- Look for smart money confirmation
- All setups must have ≥ 2:1 R:R

## Scan Universe

- S&P 500, NASDAQ 100, Russell 2000
- Market cap > $1B
- Average volume > 500K shares
- Optionable stocks
