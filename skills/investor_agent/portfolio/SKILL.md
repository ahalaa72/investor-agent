---
name: portfolio
description: Portfolio validation and management. Use when reviewing portfolio holdings, validating existing stock positions with 4-gate continuous validation, checking concentration limits, monitoring portfolio Greeks, or getting HOLD/TRIM/ADD recommendations.
---

# Portfolio - Validation & Management

Validate and manage portfolio holdings using 4-gate continuous validation and institutional risk limits.

---

## ⚠️ Questrade Token Protection

**NEVER write Python scripts to access Questrade data** - This consumes the single-use refresh token.

**ALWAYS use MCP tools:**

- `get_questrade_accounts()` for account list
- `get_questrade_positions()` for holdings
- `get_questrade_balances()` for cash/buying power

If you get HTTP 400 errors, the token is consumed. See main SKILL.md for recovery steps.

---

## Workflow

1. **Get Positions:** `get_questrade_accounts()` → `get_questrade_positions(account)`
2. **Validate Each Stock:** `generate_trading_signal(ticker)` for 4-gate check
3. **Portfolio Risk:** `check_portfolio_concentration_limits()` + `get_portfolio_greeks_dashboard()`
4. **Provide Recommendations:** HOLD / TRIM / ADD with reasoning

## Key Tools

| Tool | Purpose |
|------|---------|
| `get_questrade_accounts()` | List all accounts |
| `get_questrade_positions()` | Holdings for an account |
| `get_questrade_balances()` | Cash and buying power |
| `generate_trading_signal()` | 4-gate validation per holding |
| `check_portfolio_concentration_limits()` | Diversification check |
| `get_portfolio_greeks_dashboard()` | Options risk (delta/theta/vega/gamma) |
| `calculate_portfolio_beta_weighted_delta()` | Market exposure |

## 4-Gate Continuous Validation

Run same 4 gates on existing positions:

| Gate | Question |
|------|----------|
| Catalyst | Still active catalysts? Original played out? |
| Freshness | Momentum still supportive? Volume profile? |
| Brooks | **CRITICAL:** Always-In still aligned? Flip = EXIT |
| Quality | Fundamentals still intact? |

**Decision Matrix:**
- Score ≥ 70%: **HOLD** (strong conviction)
- Score 50-70%: **HOLD** but monitor
- Score < 50%: **TRIM/EXIT** (thesis weakened)
- Brooks flip: **EXIT IMMEDIATELY** (thesis invalidated)

## Concentration Limits

| Metric | Limit | Action if Exceeded |
|--------|-------|-------------------|
| Single position | ≤ 15% | Reduce immediately |
| Sector | ≤ 30% | Rebalance |
| Options | ≤ 20% | Reduce exposure |
| Beta-weighted delta | ±25% | Hedge or reduce |

**Warning Levels:**
- 🔴 CRITICAL: > 20% single position
- 🟡 WARNING: 15-20% single position
- 🟢 HEALTHY: < 15% single position

## Portfolio Greeks

For portfolios with options:

| Greek | Positive | Negative |
|-------|----------|----------|
| Delta | Bullish bias | Bearish bias |
| Theta | Collecting decay | Paying decay |
| Vega | Want IV up | Want IV down |
| Gamma | Delta changes help | Delta changes hurt |

**Risk Levels:**
- Delta NEUTRAL: -50 to +50
- BULLISH: > +50
- BEARISH: < -50

## Combined Stock + Options

For positions with both components:

| Stock Says | Options Says | Action |
|------------|-------------|--------|
| EXIT | CLOSE | Exit both |
| HOLD | CLOSE | Close options, hold stock |
| EXIT | HOLD | Review thesis, likely exit both |

## Examples

```
"Review my portfolio"
"Should I hold my AAPL position?"
"Check my portfolio concentration"
"Show my portfolio Greeks"
"Am I delta neutral?"
```

## Important Notes

- Portfolio validation is NOT a scanner (use scanner skill for new opportunities)
- Brooks Always-In flip is a critical exit signal
- Concentration limits are hard stops
- For options, Phase 4 position management takes priority
- Trust the 4-gate system over emotional attachment
