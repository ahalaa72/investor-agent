---
name: position
description: Options position lifecycle management (Phase 4). Use when checking existing options positions, deciding whether to close/hold/roll, daily position monitoring, managing tested positions, or checking portfolio Greeks. Implements TastyTrade 5-rule methodology.
---

# Position - Options Lifecycle Management

Manage existing options positions using TastyTrade research and McMillan methodology.

---

## ⚠️ Questrade Token Protection

**NEVER write Python scripts to check positions** - This consumes the single-use refresh token.

**ALWAYS use MCP tools:**

- `evaluate_options_position_management()` for position analysis
- `get_portfolio_greeks_dashboard()` for portfolio Greeks
- `get_questrade_positions()` for current holdings

If you get HTTP 400 errors, the token is consumed. See main SKILL.md for recovery steps.

---

## 5 Management Rules (Priority Order)

Rules are checked in order - **first trigger wins**.

### Rule 1: ✅ 50% Profit Target
**Trigger:** P&L ≥ 50% of max profit
**Action:** CLOSE (IMMEDIATE)
**Why:** 88% win rate at 50% vs 52% at expiration

### Rule 2: 📅 21 DTE Management
**Trigger:** DTE ≤ 21
**Action:** 
- Profitable → CLOSE (lock gains)
- Losing → ROLL to next monthly
**Why:** Gamma risk accelerates after 21 DTE

### Rule 3: 🔄 Direction Change
**Trigger:** Brooks Always-In flips from entry direction
**Action:** CLOSE (IMMEDIATE)
**Why:** Original thesis invalidated

### Rule 4: ⚠️ Tested Position
**Trigger:** Price breaches short strike + ITM > 5% + DTE ≤ 7
**Action:** CLOSE (IMMEDIATE)
**Why:** High assignment risk

### Rule 5: 📊 Earnings Proximity
**Trigger:** Earnings < 7 days away
**Action:** CLOSE (IMMEDIATE)
**Why:** Avoid IV crush

## Key Tools

| Tool | Purpose |
|------|---------|
| `evaluate_options_position_management()` | **Primary tool** - checks all 5 rules |
| `get_portfolio_greeks_dashboard()` | Portfolio-level risk |

## Using evaluate_options_position_management()

**Required Parameters:**
```python
evaluate_options_position_management(
    symbol="AAPL",
    strategy="IRON_CONDOR",  # or CREDIT_SPREAD, BULL_PUT_SPREAD, etc.
    entry_date="2026-01-15",
    expiration="2026-02-21",
    entry_credit=630.00,    # max profit for credit strategies
    current_value=315.00,   # current position value
    entry_direction="NEUTRAL",  # LONG, SHORT, or NEUTRAL
    legs=[
        {"type": "CALL", "strike": 252, "action": "SELL", "quantity": 2},
        {"type": "CALL", "strike": 257, "action": "BUY", "quantity": 2},
        {"type": "PUT", "strike": 204, "action": "SELL", "quantity": 2},
        {"type": "PUT", "strike": 199, "action": "BUY", "quantity": 2}
    ]
)
```

**Returns:**
- `action`: HOLD / CLOSE / ROLL
- `urgency`: IMMEDIATE / WITHIN_3_DAYS / MONITOR
- `reason`: Detailed explanation
- `profit_status`: Current P&L and percentage
- `dte_status`: Days to expiration info

## Portfolio Greeks Dashboard

```
📊 PORTFOLIO GREEKS:
   Delta: +35 (slight bullish)
   Theta: +134 (collecting $134/day)
   Vega: -430 (short vega)
   Gamma: -11 (short gamma)

💰 INCOME & RISK:
   Daily Theta: $134
   10pt IV Impact: -$4,300
```

**Risk Assessment:**
| Greek | NEUTRAL | BULLISH | BEARISH |
|-------|---------|---------|---------|
| Delta | -50 to +50 | > +50 | < -50 |

## Examples

```
"Check my AAPL iron condor"
"Should I close this position?"
"Show my portfolio Greeks"

"I have an AAPL iron condor:
Entry: $630 credit on Jan 15
Expiry: Feb 21
Current value: $315
Should I close it?"
```

## Action Codes

| Action | Meaning |
|--------|---------|
| HOLD | Position healthy, continue monitoring |
| CLOSE | Exit position (check urgency) |
| ROLL | Close current, open new in next expiration |

## Urgency Levels

| Level | Meaning |
|-------|---------|
| IMMEDIATE | Take action today |
| WITHIN_3_DAYS | Take action this week |
| MONITOR | No urgent action |

## Important Notes

- **Daily monitoring required** - Check positions every trading day
- **No stop losses on credit spreads** - Reduces profitability (TastyTrade)
- **Trust the 50% rule** - 88% win rate is proven
- **Brooks flip is critical** - Exit immediately
- **Roll, don't close, on 21 DTE losses** - Give trade more time

## Post-Entry Flow

```
Scanner → finds opportunity
Trading → analyzes + generates plan
Entry → execute trade
Position → daily monitoring starts
    ↓
Check 5 rules every day
    ↓
Rule triggered? → Take action
No trigger? → HOLD + check tomorrow
```
