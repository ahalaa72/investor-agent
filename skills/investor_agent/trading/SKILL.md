---
name: trading
description: Stock and options analysis for trading decisions. Use when analyzing a specific ticker, generating trading signals (LONG/SHORT/NEUTRAL), creating options trade plans, or checking current prices. Runs 4-gate validation and provides entry/stop/target levels.
---

# Trading - Stock & Options Analysis

Analyze stocks and generate trading signals using 4-gate validation, Al Brooks price action, and McMillan options methodology.

---

## ⚠️ Questrade Token Protection

**NEVER write Python scripts to test Questrade API** - This consumes the single-use refresh token before MCP tools can use it.

**ALWAYS use MCP tools:**

- `get_questrade_quotes()` for prices
- `get_questrade_positions()` for holdings
- `get_questrade_balances()` for account data

If you get HTTP 400 errors, the token is consumed. See main SKILL.md for recovery steps.

---

## Workflow

1. **Get Current Price:** `get_questrade_quotes(symbols)` for real-time bid/ask
2. **Generate Signal:** `generate_trading_signal(ticker)` runs full 4-gate analysis
3. **Options (if requested):** `analyze_options_mcmillan(ticker)` + `generate_options_trade_plan(ticker, direction)`

## Key Tools

| Tool | Purpose |
|------|---------|
| `get_questrade_quotes()` | Real-time prices (ALWAYS call first) |
| `get_ticker_data()` | Fundamentals, news, metrics |
| `generate_trading_signal()` | 4-gate validation (primary tool) |
| `analyze_technical()` | RSI, MACD, Bollinger, Al Brooks |
| `analyze_options_mcmillan()` | IV Rank, P/C ratio, max pain |
| `generate_options_trade_plan()` | Full trade setup with strikes |

## 4-Gate System

| Gate | Weight | Passing Criteria |
|------|--------|------------------|
| Catalyst | 15% | Institutional strength ≥ 60% |
| Freshness | 15% | Recent price action supports direction |
| Brooks | 19.6% | Always-In aligned with direction |
| Quality | 10% | F-Score ≥ 6 (LONG) or ≤ 4 (SHORT) |

**Signal Interpretation:**
- ≥ 70%: STRONG signal (high conviction)
- 50-70%: Moderate signal (trade with caution)
- < 50%: NO TRADE (insufficient conviction)

## Output Format

**Comprehensive Analysis:** Full 10-phase institutional report
**Concise Analysis:** Quick summary with signal, entry/stop/target

## Examples

```
"Analyze AAPL for trading"
"Quick analysis of TSLA"
"Generate options trade plan for NVDA LONG"
"What's the current price of MSFT?"
```

## Important Notes

- ALWAYS use `get_questrade_quotes()` first for current price
- `generate_trading_signal()` is the primary analysis tool
- For options, check IV environment before strategy selection
- Trust the 4-gate system - it has institutional validation built-in
- Brooks Always-In flip = thesis invalidation (don't fight it)
