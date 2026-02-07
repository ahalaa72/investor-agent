---
name: investor-agent
description: Comprehensive stock analysis and options trading toolkit. Use when analyzing stocks, generating trading signals, managing options positions, reviewing portfolios, or scanning for market opportunities. Integrates Al Brooks price action, McMillan options strategy, Ray Dalio's Economic Machine, and 4-gate validation (Catalyst, Freshness, Brooks, Quality). Supports Questrade API for real-time data.
---

# Investor Agent - Stock Analysis & Options Trading

Professional-grade stock analysis, options trading, portfolio management, and position monitoring using institutional methodologies.

---

## 🚨 CRITICAL: DO NOT SCREW UP THE QUESTRADE TOKEN 🚨

**Questrade tokens are SINGLE-USE and easily destroyed. Follow these rules exactly:**

### What BREAKS the Token (DO NOT DO)
❌ **Running Python scripts manually** - Consumes the single-use token before MCP can use it
❌ **Restarting Docker without volume** - Token file is lost, env token is dead
❌ **Multiple container instances** - First consumes token, others fail
❌ **Testing outside Docker** - Consumes token, Docker instance fails
❌ **Creating incomplete token file** - Missing any of 6 required fields causes repeated token consumption

### What PRESERVES the Token (ALWAYS DO)
✅ **Use MCP tools ONLY** - Never write Python scripts for Questrade API
✅ **Keep container running** - Stop/remove only during planned rebuilds
✅ **Use Docker volume** - Token persists across rebuilds: `-v questrade-tokens:/root`
✅ **Let auto-refresh work** - Token file must have all 6 fields (access_token, api_server, expires_in, refresh_token, token_type, expires_at)
✅ **One container only** - Never run multiple containers with same token

### When Token Breaks (HTTP 400 Error)

**Step 1: Get New Token**
- Go to: https://login.questrade.com/APIAccess/UserApps.aspx
- Click "Generate new token"
- Copy the new token

**Step 2: Update Files**
```bash
# Update .env
echo "QUESTRADE_REFRESH_TOKEN=NEW_TOKEN_HERE" > /Users/AhmedE/git/investor-agent/.env

# Update running container
docker exec investor-agent-mcp bash -c 'cat > /root/.questrade.json << "EOF"
{
  "refresh_token": "NEW_TOKEN_HERE",
  "token_type": "Bearer"
}
EOF'
```

**Step 3: Verify**
```bash
docker exec investor-agent-mcp cat /root/.questrade.json
```

**Step 4: Test**
Use `get_questrade_accounts()` to verify connection. First successful API call will auto-populate all 6 required fields in token file.

---

## Sub-Skills

This skill contains 4 specialized sub-skills:

| Sub-Skill | Use When |
|-----------|----------|
| **trading** | Analyzing a specific stock, generating trading signals, creating options trade plans |
| **portfolio** | Reviewing portfolio holdings, validating positions, checking concentration limits |
| **position** | Managing existing options positions (50% profit, 21 DTE, direction changes) |
| **scanner** | Finding new LONG/SHORT opportunities, detecting catalysts, smart money flow |

Read the appropriate sub-skill SKILL.md before executing tasks.

## Core Methodologies

**Al Brooks Price Action:** Always-In direction, trading ranges vs trends, order blocks
**McMillan Options:** IV environment analysis, 16-delta strikes, defined risk strategies
**Ray Dalio Economic Machine:** Volume-price relationships, regime detection (risk-on/off)
**4-Gate Validation:** Catalyst (15%), Freshness (15%), Brooks (19.6%), Quality (10%)

## Key MCP Tools

### Real-Time Data
- `get_questrade_quotes(symbols)` - Live bid/ask, pre-market
- `get_ticker_data(ticker)` - Comprehensive fundamentals

### Analysis
- `generate_trading_signal(ticker)` - 4-gate validation (primary analysis tool)
- `analyze_technical(ticker)` - RSI, MACD, Bollinger, Al Brooks patterns
- `analyze_options_mcmillan(ticker)` - IV Rank, P/C Ratio, Max Pain

### Portfolio
- `get_questrade_positions(account)` - Current holdings
- `get_portfolio_greeks_dashboard()` - Delta, theta, vega, gamma
- `check_portfolio_concentration_limits()` - Diversification check

### Position Management
- `evaluate_options_position_management()` - 5-rule position lifecycle
- `calculate_portfolio_beta_weighted_delta()` - Market exposure

### Scanning
- `scan_long_candidates()` - Bullish opportunities
- `scan_short_candidates()` - Bearish opportunities
- `detect_catalyst_strength(ticker)` - Catalyst verification
- `detect_unusual_options_activity(ticker)` - Smart money flow

## Quick Reference

**Trading Signal Interpretation:**
- Score ≥ 70%: Strong conviction (BUY/SELL)
- Score 50-70%: Moderate (WATCH)
- Score < 50%: No trade (SKIP)

**Position Management Rules (Priority Order):**
1. 50% profit → CLOSE (88% win rate)
2. 21 DTE → CLOSE if profitable, ROLL if losing
3. Brooks flip → EXIT (thesis invalidated)
4. Tested + DTE ≤ 7 → CLOSE (assignment risk)
5. Earnings < 7 days → EXIT (IV crush)

**Concentration Limits:**
- Single position: ≤ 15%
- Sector: ≤ 30%
- Options: ≤ 20%

## Workflow

```
SCANNER → find opportunities
    ↓
TRADING → analyze + generate trade plan
    ↓
ENTRY → execute trade
    ↓
Stock? → PORTFOLIO skill (4-gate validation)
Options? → POSITION skill (5-rule management)
```

## Configuration

```json
{
  "mcpServers": {
    "investor-agent": {
      "command": "docker",
      "args": ["exec", "-i", "investor-agent-mcp", "python", "-m", "investor_agent.server"]
    }
  }
}
```

## References

- TastyTrade: 50% profit target, 45 DTE entry, 21 DTE exit
- McMillan: "Options as a Strategic Investment" (5th Ed)
- Al Brooks: "Trading Price Action" series
- Ray Dalio: Economic Machine principles
- Hull: "Options, Futures, and Other Derivatives"
