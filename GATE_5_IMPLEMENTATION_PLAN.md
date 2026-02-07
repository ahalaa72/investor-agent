# Gate 5: Options Tradability - Implementation Plan

**Date:** January 28, 2026
**Status:** Phase 1 - 75% Complete
**Estimated Completion:** 3 weeks (Feb 18, 2026)
**Last Updated:** January 28, 2026 15:30 EST

---

## Executive Summary

This plan adds **Gate 5 (Options Tradability)** to the existing 4-gate validation system, creating a comprehensive 5-gate framework that determines:
1. Whether to trade options vs stock
2. Which options strategy to use (based on IV environment)
3. How to manage options positions through their lifecycle

**Key Integration:** Gate 5 leverages existing institutional features implemented Jan 19, 2026:
- IV Skew Analysis (`analyze_iv_skew`)
- Term Structure (`analyze_iv_term_structure`)
- Advanced Greeks (Vanna, Charm, GEX)
- Portfolio Risk Management (beta-weighted delta, concentration limits, VaR)

---

## Current 4-Gate System

| Gate | Focus | Weight | Pass Criteria |
|------|-------|--------|---------------|
| 1. Catalyst | Earnings, insider, news | 25% | Active catalyst detected |
| 2. Freshness + Dalio | CVD, exhaustion, dollar flow | 20% | 5/6 checks pass |
| 3. Brooks | Price action, Always-In | 20% | Probability ≥55%, LOW trap risk |
| 4. Quality | F-Score, Z-Score, fundamentals | 15% | Quality score ≥40 |

**Signal Classification:**
- 4/4 gates = STRONG_BUY/SELL
- 3/4 gates = BUY/SELL
- 2/4 gates = WATCH
- <2/4 gates = NO_TRADE

---

## New 5-Gate System

| Gate | Focus | Weight | Pass Criteria |
|------|-------|--------|---------------|
| 1. Catalyst | Earnings, insider, news | 25% | Active catalyst detected |
| 2. Freshness + Dalio | CVD, exhaustion, dollar flow | 20% | 5/6 checks pass |
| 3. Brooks | Price action, Always-In | 20% | Probability ≥55%, LOW trap risk |
| 4. Quality | F-Score, Z-Score, fundamentals | 15% | Quality score ≥40 |
| **5. Options Tradability** | **Liquidity, IV, earnings, expected move** | **20%** | **Pass liquidity + IV checks** |

**Updated Signal Classification:**
- 5/5 gates = STRONG_BUY/SELL (options recommended)
- 4/4 gates (no Gate 5 run) = STRONG_BUY/SELL (stock only)
- 4/5 gates (Gate 5 failed) = BUY/SELL (stock only, options not viable)
- 3/4 gates = BUY/SELL
- <3/4 gates = WATCH or NO_TRADE

---

## Gate 5: Options Tradability Checks

### Check 1: Liquidity (MANDATORY)
| Metric | Threshold | Purpose |
|--------|-----------|---------|
| Bid/Ask Spread | ≤5% of mid-price | Execution cost control |
| Open Interest | ≥100 contracts (≥1000 preferred) | Market depth |
| Daily Volume | ≥50 contracts | Ability to enter/exit |
| Underlying Liquidity | Tier 1 or Tier 2 | Overall tradability |

**FAIL any one = Gate 5 FAIL → Trade stock only**

### Check 2: IV Environment Classification
| IV Rank | Environment | Optimal Strategy |
|---------|-------------|------------------|
| >50% (HIGH) | SELL PREMIUM | Credit spreads, Iron Condors |
| 30-50% (MEDIUM) | NEUTRAL | Debit spreads, Calendars |
| <30% (LOW) | BUY PREMIUM | Long calls/puts, Debit spreads |

**Uses:** `analyze_options_mcmillan()` for IV Rank

### Check 3: Earnings Proximity
| Scenario | Action |
|----------|--------|
| Earnings < 30 days + Buying premium | BLOCK (IV crush risk) |
| Earnings < 30 days + Selling premium | ALLOW (IV crush = profit) |
| Earnings ≥ 30 days | ALLOW |

**Uses:** `detect_catalyst_strength()` for earnings date

### Check 4: Expected Move Calculation
Formula: `Expected Move = Price × IV × √(DTE/365)`

| DTE | 1 SD Factor | Use Case |
|-----|-------------|----------|
| 7 | 0.139 | Weekly expirations |
| 30 | 0.287 | Monthly cycle |
| **45** | **0.352** | **Optimal entry (institutional standard)** |
| 90 | 0.498 | Quarterly |

**16-Delta Strike Selection (1 SD):**
- Call spread short strike: Current price + Expected Move
- Put spread short strike: Current price - Expected Move
- 84% probability OTM (TastyTrade research optimal)

### Check 5: IV Skew Integration
**Uses:** `analyze_iv_skew()` for put/call edge detection

| Skew Type | Implication | Strategy Adjustment |
|-----------|-------------|---------------------|
| STEEP_PUT_SKEW (>10 pts) | Puts expensive, calls cheap | Favor call spreads over put spreads |
| NORMAL_PUT_SKEW (3-10 pts) | Standard fear premium | Balanced approach |
| FLAT_SKEW (0-3 pts) | Neutral sentiment | Standard strategies |
| INVERTED_SKEW (<0 pts) | Calls expensive (bullish mania) | Favor put spreads over call spreads |

### Check 6: Term Structure Integration
**Uses:** `analyze_iv_term_structure()` for calendar signal

| Structure | Signal | Strategy Impact |
|-----------|--------|-----------------|
| CONTANGO (slope >0) | FAVORABLE | Calendar spreads profitable |
| FLAT (slope ~0) | NEUTRAL | Standard strategies |
| BACKWARDATION (slope <0) | UNFAVORABLE | Avoid calendars, reduce premium selling |

---

## Implementation Architecture

### Phase 1: Foundation (Week 1)

#### File Structure
```
investor_agent/
├── gates/
│   ├── __init__.py
│   ├── options_tradability_gate.py  # NEW - Gate 5 implementation
│   └── gate_validator.py            # NEW - Unified gate runner
├── options/
│   ├── decision_framework.py        # NEW - Options vs stock logic
│   ├── strategy_selector.py         # NEW - Strategy selection by IV
│   └── expected_moves.py            # NEW - 1SD/2SD calculations
└── server.py                        # MODIFY - integrate Gate 5
```

#### Core Functions

**1. `validate_options_tradability()` - Gate 5 Entry Point**
```python
def validate_options_tradability(
    ticker: str,
    direction: str,
    current_price: float,
    options_data: dict,  # from analyze_options_mcmillan
    iv_skew_data: dict,  # from analyze_iv_skew
    term_structure: dict,  # from analyze_iv_term_structure
    earnings_days: int,
    account_size: float,
    vanna_data: dict = None  # Optional: if earnings < 45 days
) -> dict:
    """
    Gate 5: Validates options tradability and recommends strategy.

    Returns:
        {
            "gate_status": "PASS" | "FAIL",
            "score": 0-100,
            "checks": {
                "liquidity": {
                    "status": "PASS" | "FAIL",
                    "spread_pct": 2.3,
                    "open_interest": 1523,
                    "volume": 342,
                    "liquidity_tier": "TIER_1"
                },
                "iv_environment": {
                    "status": "PASS",
                    "iv_rank": 68.2,
                    "classification": "HIGH",
                    "interpretation": "SELL_PREMIUM"
                },
                "earnings_filter": {
                    "status": "PASS" | "WARN" | "FAIL",
                    "days_to_earnings": 45,
                    "buying_blocked": False
                },
                "expected_move": {
                    "1sd_move": 24.09,
                    "2sd_move": 48.18,
                    "1sd_upper": 252.09,
                    "1sd_lower": 203.91,
                    "optimal_call_strike": 252,
                    "optimal_put_strike": 204
                },
                "skew_integration": {
                    "skew_type": "NORMAL_PUT_SKEW",
                    "skew_absolute": 6.2,
                    "put_spread_edge": "Rich",
                    "call_spread_edge": "Fair",
                    "recommended_adjustment": "Standard iron condor, slight bias to put side"
                },
                "term_structure_integration": {
                    "structure": "CONTANGO",
                    "slope": 0.042,
                    "calendar_signal": "FAVORABLE",
                    "diagonal_signal": "FAVORABLE"
                },
                "vanna_protection": {  # Only if earnings < 45 days
                    "vanna_exposure": -0.12,
                    "iv_crush_delta_change": -2.4,
                    "hedging_required": "YES"
                }
            },
            "recommended_strategy": "IRON_CONDOR" | "CREDIT_SPREAD" | "DEBIT_SPREAD" | "LONG_OPTIONS" | "CALENDAR_SPREAD" | "STOCK_ONLY",
            "strategy_rationale": str,
            "alternatives": [
                {"strategy": "BULL_PUT_SPREAD", "reason": "If prefer single side"},
                ...
            ],
            "warnings": [
                "Earnings in 12 days - IV crush expected",
                ...
            ],
            "options_plan": {
                # Full 4-leg construction if Gate 5 passes
                "legs": [...],
                "max_profit": 630,
                "max_loss": 370,
                # ... (existing structure from generate_options_trade_plan)
            } | None
        }
    """
```

**2. `should_use_options()` - Decision Framework**
```python
def should_use_options(
    gate_5_result: dict,
    stock_liquidity: dict,
    conviction_level: str  # "STRONG" (4/4 gates) vs "MODERATE" (3/4 gates)
) -> dict:
    """
    Decides: Options vs Stock

    Logic:
    1. If Gate 5 FAIL → Stock only
    2. If Gate 5 PASS + HIGH IV + Excellent liquidity → Options (credit spreads)
    3. If Gate 5 PASS + LOW IV + Excellent liquidity → Options (debit spreads)
    4. If Gate 5 PASS + Moderate liquidity → Stock (safer)
    5. If conviction MODERATE (3/4 gates) → Stock (reduce complexity)

    Returns:
        {
            "use_options": bool,
            "primary_vehicle": "OPTIONS" | "STOCK",
            "reason": str,
            "stock_plan": {...},
            "options_plan": {...} | None
        }
    """
```

**3. `calculate_expected_moves()` - Strike Selection Helper**
```python
def calculate_expected_moves(
    current_price: float,
    iv: float,  # Decimal (0.30 for 30%)
    dte: int = 45
) -> dict:
    """
    Calculates 1 SD and 2 SD expected moves for strike selection.

    Returns:
        {
            "dte": 45,
            "1sd_move": 24.09,
            "1sd_range": {"low": 203.91, "high": 252.09},
            "2sd_move": 48.18,
            "2sd_range": {"low": 179.82, "high": 276.08},
            "optimal_strikes": {
                "call_16delta": 252,  # 1 SD above
                "call_5delta": 276,   # 2 SD above
                "put_16delta": 204,   # 1 SD below
                "put_5delta": 180     # 2 SD below
            }
        }
    """
```

### Phase 2: Scanner Integration (Week 2)

#### Caching Strategy
```python
# investor_agent/cache/options_cache.py

class OptionsCache:
    """
    Redis-based caching for options data during scans.

    Cache TTLs:
    - Options chains: 15 min (market hours) / 1 hour (after hours)
    - IV Rank: 1 hour
    - Liquidity scores: 30 minutes
    """

    def get_cached_iv_rank(self, ticker: str) -> float | None:
        """Fast lookup of IV Rank without full analysis"""

    def get_cached_liquidity_tier(self, ticker: str) -> str | None:
        """Pre-computed liquidity tier (TIER_1, TIER_2, TIER_3)"""
```

#### Lightweight Scoring
```python
# investor_agent/scanner/options_scoring.py

def quick_options_score(ticker: str, direction: str) -> dict:
    """
    Fast options viability check for scanner (target: <2 sec per ticker).

    Only fetches:
    - IV Rank (cached)
    - Liquidity tier (cached)
    - Basic strategy classification

    Skips:
    - IV skew (heavy)
    - Term structure (multiple expirations)
    - Greeks calculations (Vanna, Charm, GEX)

    Returns:
        {
            "options_viable": bool,
            "iv_rank": 65.2,
            "liquidity_tier": "TIER_1",
            "quick_strategy": "IC",  # Iron Condor
            "display_string": "IC@65IV"
        }
    """
```

#### Scanner Output Format
```
Current:
AAPL: 4/4 [C:P F:P B:P Q:P] | STRONG_BUY | 85%

New:
AAPL: 4/4 [C:P F:P B:P Q:P] | STRONG_BUY | 85% | OPT: IC@65IV
                                                    └─ Options viable: Iron Condor at 65% IV Rank

Legend:
- IC@XXiv = Iron Condor at XX% IV Rank
- BS@XXiv = Debit Spread at XX% IV Rank
- LC@XXiv = Long Call/Put at XX% IV Rank
- STOCK = Stock only (poor liquidity or Gate 5 fail)
- N/A = No options data available
```

### Phase 3: Position Management (Week 3)

#### Position State Machine
```python
# investor_agent/positions/management.py

class OptionsPositionManager:
    """
    Manages options position lifecycle based on McMillan + TastyTrade rules.

    Rules:
    1. 50% Profit Target (credit spreads) - 88% win rate
    2. 21 DTE Management - Close or roll
    3. Direction Change - Exit if Brooks flips
    4. Tested Position - Roll or take assignment
    5. Earnings <7 days - Close (IV crush)
    """

    def evaluate_position(
        self,
        position: dict,
        current_market: dict,
        brooks_signal: dict
    ) -> dict:
        """
        Returns:
            {
                "action": "HOLD" | "CLOSE" | "ROLL" | "ADJUST",
                "reason": str,
                "urgency": "IMMEDIATE" | "WITHIN_3_DAYS" | "MONITOR",
                "roll_details": {...} | None,
                "expected_pnl_if_hold": float,
                "expected_pnl_if_close": float
            }
        """
```

#### Portfolio Greeks Dashboard
```python
def calculate_aggregate_portfolio_greeks(positions: list[dict]) -> dict:
    """
    Calculates portfolio-level Greeks across all options positions.

    Integrates with:
    - calculate_portfolio_beta_weighted_delta() (existing)
    - check_portfolio_concentration_limits() (existing)

    Returns:
        {
            "beta_weighted_delta": 142.3,  # SPY-equivalent delta
            "delta_per_100k": 142,
            "delta_limit": 200,
            "delta_status": "OK" | "WARNING" | "VIOLATION",

            "net_theta": 12.45,  # Daily time decay (positive = profit)
            "theta_target": ">0 (time decay in your favor)",

            "net_vega": -156.8,  # IV sensitivity
            "vega_10pt_impact": -1568,  # P&L change per 10-point IV move

            "net_gamma": -2.34,
            "gamma_regime": "SHORT_GAMMA",  # "LONG_GAMMA" | "SHORT_GAMMA" | "NEUTRAL"

            "concentration_warnings": [
                "62% of options exposure in Technology sector (limit: 20%)",
                ...
            ]
        }
    """
```

### Phase 4: Documentation & Reporting (Week 4)

#### Report Template Addition
Add to `COMPREHENSIVE_REPORT_GENERATOR.md`:

```markdown
## SECTION X: OPTIONS GATE (GATE 5 VALIDATION)

**Purpose:** Determine if options are suitable and which strategy to use.

### Gate 5 Checks

| Check | Threshold | Current | Status | Impact |
|-------|-----------|---------|--------|--------|
| **Liquidity** |
| - Bid/Ask Spread | ≤5% | 2.1% | ✅ PASS | Tight spreads = low slippage |
| - Open Interest | ≥100 | 1,523 | ✅ PASS | Excellent market depth |
| - Daily Volume | ≥50 | 342 | ✅ PASS | Active trading |
| - Liquidity Tier | 1 or 2 | TIER_1 | ✅ PASS | Highly liquid |
| **IV Environment** |
| - IV Rank | - | 68.2% | HIGH | SELL PREMIUM strategies favored |
| - Classification | - | HIGH | - | Credit spreads, Iron Condors |
| **Earnings Filter** |
| - Days to Earnings | >30 (buyers) | 45 days | ✅ PASS | Safe for premium buying |
| **Expected Move (1 SD)** |
| - 45 DTE Move | - | ±$24.09 | - | 68% probability range |
| - Optimal Call Strike | - | $252 (16Δ) | - | 84% OTM probability |
| - Optimal Put Strike | - | $204 (16Δ) | - | 84% OTM probability |
| **IV Skew** |
| - Skew Type | - | NORMAL_PUT | - | Standard fear premium |
| - Put vs Call IV | - | +6.2 pts | - | Puts slightly expensive |
| - Edge Detection | - | Put Rich | - | Slight bias to call spreads |
| **Term Structure** |
| - Structure | - | CONTANGO | ✅ | Calendar spreads favorable |
| - Slope | >0 | 0.042 | ✅ | Far-term IV > near-term |
| - Calendar Signal | - | FAVORABLE | - | Time spreads profitable |

**Gate 5 Overall:** ✅ PASS (Score: 92/100)

### Recommended Strategy: IRON CONDOR

**Why Iron Condor:**
1. High IV (68%) → Sell premium
2. Excellent liquidity (Tier 1) → Tight execution
3. Contango term structure → Favorable decay
4. Earnings 45 days away → Safe window
5. Normal put skew → Balanced condor structure

**Strategy Details:**

| Leg | Action | Type | Strike | Delta | IV | Premium | Contracts |
|-----|--------|------|--------|-------|----|---------|-----------|
| 1 | SELL | CALL | $252 | 0.16 | 28.3% | $2.45 | 2 |
| 2 | BUY | CALL | $257 | 0.05 | 26.1% | $0.85 | 2 |
| 3 | SELL | PUT | $204 | -0.16 | 32.6% | $2.30 | 2 |
| 4 | BUY | PUT | $199 | -0.05 | 34.9% | $0.75 | 2 |

**Risk/Reward:**
- Net Credit: $6.30 ($630 total)
- Max Profit: $630 (at expiration, price $204-$252)
- Max Loss: $370 (if price >$257 or <$199)
- Breakeven Upper: $258.30
- Breakeven Lower: $197.70
- Probability of Profit: 68% (based on 16Δ short strikes)

**Position Greeks:**
- Delta: +0.02 (near delta-neutral)
- Theta: +$3.70/day (time decay profit)
- Vega: -24.6 (short IV, profit from IV crush)
- Gamma: -0.008 (short gamma near expiration)

**Management Plan:**
1. **50% Profit Target:** Close when credit reaches $3.15 (50% of max profit)
2. **21 DTE Check:** At 21 days to expiration, evaluate close vs roll
3. **Direction Change:** Exit immediately if Brooks Always-In flips
4. **Earnings <7 days:** Close to avoid IV crush volatility

**Alternative Strategies:**

| Strategy | When to Use | Reason |
|----------|-------------|--------|
| Bull Put Credit Spread | If bullish bias stronger | Single-side position, higher credit |
| Bear Call Credit Spread | If bearish bias stronger | Single-side position, less capital |
| Calendar Spread | If neutral + want long vega | Profit from contango term structure |
| Stock Only | If prefer simplicity | Avoid options complexity |

### Options vs Stock Decision: OPTIONS RECOMMENDED

**Decision Rationale:**
- ✅ Gate 5 passed all checks (92/100 score)
- ✅ High IV environment (68%) favors premium selling
- ✅ Tier 1 liquidity ensures tight execution
- ✅ Risk-defined structure (max loss $370 vs stock $22,800)
- ✅ Time decay working in your favor (+$3.70/day)

**If Stock Instead:**
- Entry: $228.00
- Stop: $219.30 (2.5x ATR)
- Target: $245.70
- Position: 100 shares ($22,800)
- Max Risk: $870 (vs $370 with options)

**Verdict:** Options provide better risk/reward (1.7:1 vs 1.5:1) with defined risk and positive theta decay.
```

---

## Testing Strategy

### Unit Tests (Phase 1)
```python
# tests/test_gate_5_validation.py

def test_gate_5_liquidity_check():
    """Test liquidity validation passes with good data"""

def test_gate_5_liquidity_fail():
    """Test liquidity validation fails with poor spread/OI"""

def test_iv_environment_classification():
    """Test HIGH/MEDIUM/LOW IV classification"""

def test_earnings_filter_blocks_buyers():
    """Test earnings <30 days blocks premium buyers"""

def test_earnings_filter_allows_sellers():
    """Test earnings <30 days allows premium sellers"""

def test_expected_moves_calculation():
    """Test 1SD/2SD calculations are accurate"""

def test_skew_integration():
    """Test IV skew affects strategy selection"""

def test_term_structure_integration():
    """Test contango favors calendars"""
```

### Integration Tests (Phase 2)
```python
# tests/test_gate_5_integration.py

def test_5_gate_system_strong_buy():
    """Test 5/5 gates = STRONG_BUY with options"""

def test_4_gate_stock_only():
    """Test 4/4 gates (no Gate 5) = stock only"""

def test_gate_5_fail_falls_back_to_stock():
    """Test Gate 5 fail → stock recommendation"""

def test_scanner_with_options_column():
    """Test scanner outputs options recommendations"""

def test_scanner_performance_with_cache():
    """Test scanner completes in <5 min with caching"""
```

### End-to-End Tests (Phase 3)
```python
# tests/test_gate_5_e2e.py

def test_full_report_with_gate_5():
    """Test comprehensive report includes Gate 5 section"""

def test_position_management_50pct_profit():
    """Test position closes at 50% profit"""

def test_position_management_21_dte():
    """Test position evaluated at 21 DTE"""

def test_portfolio_greeks_monitoring():
    """Test portfolio Greeks calculated correctly"""
```

---

## Success Metrics

✅ **Gate 5 Validation:** 95%+ pass rate on valid options trades
✅ **Scanner Performance:** <5 minutes for 200 candidates with options
✅ **Position Management:** 88% win rate on credit spreads (TastyTrade benchmark)
✅ **Portfolio Greeks:** All positions within institutional limits
✅ **Documentation:** 100% coverage of new features
✅ **Test Coverage:** 95%+ code coverage for Gate 5 modules

---

## Timeline

| Week | Phase | Deliverables | Status |
|------|-------|--------------|--------|
| 1 | Foundation | Gate 5 validation, decision framework | 🟢 75% Complete |
| 2 | Integration | Integrate into `generate_trading_signal()` | 🟡 Next |
| 3 | Scanner | Cache, lightweight scoring, output format | ⚪ Pending |
| 4 | Position Mgmt | State machine, Greeks dashboard | ⚪ Pending |

**Target Completion:** February 18, 2026

---

## Phase 1 Progress (75% Complete)

### ✅ Completed (Jan 28, 2026)

1. **Gate 5 Core Implementation**
   - ✅ Created `investor_agent/gates/options_tradability_gate.py` (25KB, 600+ lines)
   - ✅ Implemented `validate_options_tradability()` - main orchestrator
   - ✅ Implemented `calculate_expected_moves()` - 1SD/2SD strike selection
   - ✅ Implemented `classify_iv_environment()` - HIGH/MEDIUM/LOW
   - ✅ Implemented `check_liquidity_requirements()` - spread/OI/volume checks
   - ✅ Implemented `integrate_iv_skew()` - connects to MCP tool
   - ✅ Implemented `integrate_term_structure()` - connects to MCP tool

2. **Decision Framework**
   - ✅ Created `investor_agent/options/decision_framework.py` (14KB)
   - ✅ Implemented `should_use_options()` - OPTIONS vs STOCK decision
   - ✅ Implemented `build_options_plan()` - format Gate 5 output
   - ✅ Implemented `build_stock_plan()` - fallback stock plan with Al Brooks stops

3. **Testing**
   - ✅ Created `tests/test_gate_5_basic.py` - 17 unit tests
   - ✅ Created `tests/test_gate_5_mcp_integration.py` - MCP tool integration tests
   - ✅ All 17 tests passing
   - ✅ Fixed floating-point tolerance issue in 2SD calculation

4. **Bug Fixes**
   - ✅ **SPY Liquidity Bug Fixed** - SPY was incorrectly rejected (spread defaulted to 5.0%)
   - ✅ **Tiered Spread Proxies** - Added realistic proxies for TIER_1/2/3:
     - TIER_1 (SPY, QQQ, AAPL): 0.1% (penny-wide spreads)
     - TIER_2 (high-volume S&P 500): 0.3% (tight but not penny-wide)
     - TIER_3 (mid-caps): 1.0% (moderate spreads)
     - NON_LIQUID: 5.0% (correctly rejected)
   - ✅ **Real-time Questrade Bid/Ask Fetch** - Added fallback to fetch fresh quotes
   - ✅ **Tradier API Research** - Investigated as alternative data source (requires US residency, not implemented)

5. **Documentation**
   - ✅ Created `GATE_5_IMPLEMENTATION_PLAN.md` (this document)
   - ✅ Updated `QUESTRADE_SETUP.md` - Cloudflare fix
   - ✅ Updated `QUESTRADE_TOKEN_GUIDE.md` - 403 troubleshooting
   - ✅ Updated `CLAUDE.md` - Added Questrade setup warnings
   - ✅ Updated `.env.template` - Added Tradier API placeholders

### 🟡 In Progress

**CRITICAL BLOCKER:** Gate 5 is NOT yet integrated into `generate_trading_signal()`

The Gate 5 code exists and works, but it's not being called by the main trading signal generator. This means:
- ❌ Scanner doesn't use Gate 5
- ❌ Trading signals don't include options recommendations
- ❌ Users can't get options vs stock decisions

### ⚪ Not Started (25% Remaining)

1. **Integrate Gate 5 into `generate_trading_signal()`** - NEXT CRITICAL TASK
   - Location: `investor_agent/server.py` around line 9000+
   - Add Gate 5 as 5th gate check
   - Wire up `should_use_options()` decision framework
   - Update signal classification (5/5 gates = STRONG_BUY with options)

---

## Next Steps (Priority Order)

### 🚨 IMMEDIATE (This Week)

1. **Integrate Gate 5 into `generate_trading_signal()`**
   - File: `investor_agent/server.py`
   - Add after existing 4 gates
   - Wire decision framework
   - Test with SPY, AAPL, PLTR

2. **Test Full Signal Generation**
   - Run `generate_trading_signal()` with Gate 5
   - Verify OPTIONS vs STOCK routing works
   - Confirm strategy selection matches IV environment

### 📋 Phase 2 (Next Week)

3. **Scanner Integration**
   - Add lightweight options scoring
   - Add "OPT: IC@65IV" column to scanner output
   - Implement caching for performance

4. **Documentation Updates**
   - Update `COMPREHENSIVE_REPORT_GENERATOR.md` with Gate 5 section
   - Update `CLAUDE.md` with Gate 5 usage examples

### 📊 Phase 3 (Week 3)

5. **Position Management**
   - Build state machine for 50% profit target
   - Add 21 DTE management
   - Portfolio Greeks dashboard

### 📈 Phase 4 (Week 4)

6. **Final Testing & Polish**
   - End-to-end tests
   - Performance optimization
   - Final documentation
