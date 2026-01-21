# Expected Moves Integration - Deep Dive Analysis

**Date:** January 19, 2026
**Analysis Type:** Implementation Gap Analysis
**Files Analyzed:** SCANNER_REPORT_GENERATOR.md, PORTFOLIO_INSTRUCTIONS.md

---

## ✅ WHAT'S BEEN DONE

Successfully added 1 SD expected move **TEMPLATES** to:
1. ✅ SCANNER_REPORT_GENERATOR.md (lines 372-388)
2. ✅ PORTFOLIO_INSTRUCTIONS.md (lines 476-529)
3. ✅ SCANNER_INSTRUCTIONS.md (lines 822-883)
4. ✅ COMPREHENSIVE_REPORT_GENERATOR.md
5. ✅ CONCISE_REPORT_GENERATOR.md
6. ✅ instructions.md

**Content Added:**
- Formula: `Expected Move = Current Price × IV × √(DTE / 365)`
- Standard deviation ranges tables (1 SD, 2 SD)
- Probability-based strike selection (16Δ optimal)
- Why 16Δ works vs why 2 SD fails
- Example calculations

---

## ❌ CRITICAL GAP IDENTIFIED

### Problem: Template But No Calculation Instructions

**SCANNER_REPORT_GENERATOR.md:**
```markdown
#### Expected Moves & Standard Deviation ⭐ NEW
**📊 PROBABILITY-BASED STRIKE SELECTION:**

| Timeframe | DTE | 1 SD Move (68%) | 2 SD Move (95%) | 16Δ Strike (84% OTM) |
|-----------|-----|-----------------|-----------------|----------------------|
| Weekly | 7 | ±$X.XX | ±$X.XX | $XXX |           <-- PLACEHOLDERS!
| Monthly | 30 | ±$X.XX | ±$X.XX | $XXX |          <-- PLACEHOLDERS!
| 45 DTE | 45 | ±$X.XX | ±$X.XX | $XXX ⭐ |        <-- PLACEHOLDERS!
```

**Where It Says:**
- Line 359: `**Options Analysis:** [analyze_options_mcmillan]`
- Line 1309: `analyze_options_mcmillan(ticker)  # Full McMillan analysis`

**What's Missing:**
- ❌ No instruction to extract `current_price` from analyze_options_mcmillan
- ❌ No instruction to extract `iv` (current options IV) from analyze_options_mcmillan
- ❌ No instruction to **calculate** expected moves using the formula
- ❌ No instruction to **populate** the table with calculated values
- ❌ No instruction on how to find 16Δ strike prices from options chain

---

## 🔍 DETAILED ANALYSIS

### File 1: SCANNER_REPORT_GENERATOR.md

**Location:** Lines 372-388

**What Exists:**
```markdown
#### Expected Moves & Standard Deviation ⭐ NEW
**📊 PROBABILITY-BASED STRIKE SELECTION:**

| Timeframe | DTE | 1 SD Move (68%) | 2 SD Move (95%) | 16Δ Strike (84% OTM) |
|-----------|-----|-----------------|-----------------|----------------------|
| Weekly | 7 | ±$X.XX | ±$X.XX | $XXX |
| Monthly | 30 | ±$X.XX | ±$X.XX | $XXX |
| 45 DTE | 45 | ±$X.XX | ±$X.XX | $XXX ⭐ |

**Formula:** Expected Move = Price × IV × √(DTE/365)
```

**Data Source Available:**
- Line 1309: `analyze_options_mcmillan(ticker)` returns:
  - `current_price`: Stock price
  - `iv_analysis.current_iv`: Current implied volatility (as decimal, e.g., 0.30)
  - Options chain data with strikes and deltas

**What's Missing:**
```markdown
**HOW TO POPULATE THIS TABLE:**

1. Extract data from `analyze_options_mcmillan()`:
   - current_price = mcmillan["current_price"]
   - iv = mcmillan["iv_analysis"]["current_iv"]  # e.g., 0.30

2. Calculate expected moves for each timeframe:
   - Weekly (7 DTE): price × iv × √(7/365) = price × iv × 0.1387
   - Monthly (30 DTE): price × iv × √(30/365) = price × iv × 0.2867
   - 45 DTE: price × iv × √(45/365) = price × iv × 0.3514
   - Quarterly (90 DTE): price × iv × √(90/365) = price × iv × 0.4965

3. Calculate 1 SD and 2 SD ranges:
   - 1 SD Move = expected_move
   - 1 SD Range = [price - expected_move, price + expected_move]
   - 2 SD Move = 2 × expected_move
   - 2 SD Range = [price - 2×expected_move, price + 2×expected_move]

4. Find 16Δ strikes:
   - From mcmillan options chain, find the strike closest to:
     - 16Δ call: price + 1SD_move
     - 16Δ put: price - 1SD_move
   - Alternatively, look for strikes with ~16 delta in the chain

**Example (AAPL @ $228, IV = 30%):**
- Weekly 1 SD: $228 × 0.30 × 0.1387 = ±$9.49
- Monthly 1 SD: $228 × 0.30 × 0.2867 = ±$19.61
- 45 DTE 1 SD: $228 × 0.30 × 0.3514 = ±$24.04
```

---

### File 2: PORTFOLIO_INSTRUCTIONS.md

**Location:** Lines 476-529

**What Exists:**
```markdown
#### 📊 EXPECTED MOVES & STANDARD DEVIATION FOR POSITION ⭐ NEW

**Formula:** Expected Move = Current Price × IV × √(DTE / 365)

**STANDARD DEVIATION RANGES:**

| Timeframe | DTE | 1 SD Move (68% prob) | 1 SD Range | 2 SD Move (95% prob) | 2 SD Range |
|-----------|-----|---------------------|------------|---------------------|------------|
| **Weekly** | 7 | ±$X.XX | $XXX.XX - $XXX.XX | ±$X.XX | $XXX.XX - $XXX.XX |
| **Monthly** | 30 | ±$X.XX | $XXX.XX - $XXX.XX | ±$X.XX | $XXX.XX - $XXX.XX |
| **45 DTE** | 45 | ±$X.XX | $XXX.XX - $XXX.XX | ±$X.XX | $XXX.XX - $XXX.XX |
| **Quarterly** | 90 | ±$X.XX | $XXX.XX - $XXX.XX | ±$X.XX | $XXX.XX - $XXX.XX |
```

**Data Source Available:**
- Line 186: `options = analyze_options_mcmillan(symbol)` returns same data as scanner

**Same Gap:** No calculation/population instructions

---

## 💡 SOLUTION: ADD CALCULATION INSTRUCTIONS

### Option A: Add to Each File (Recommended)

Add a new section after line 388 in SCANNER_REPORT_GENERATOR.md:

```markdown
#### 📋 HOW TO CALCULATE EXPECTED MOVES

**Step 1: Extract Data from analyze_options_mcmillan()**
```python
mcmillan = analyze_options_mcmillan(ticker)
current_price = mcmillan["current_price"]
iv = mcmillan["iv_analysis"]["current_iv"]  # Decimal (e.g., 0.30)
```

**Step 2: Calculate Expected Moves**
```python
import math

# Pre-calculated square root factors
sqrt_factors = {
    7: 0.1387,    # √(7/365)
    30: 0.2867,   # √(30/365)
    45: 0.3514,   # √(45/365)
    90: 0.4965    # √(90/365)
}

# Calculate 1 SD moves for each timeframe
expected_moves = {}
for dte, factor in sqrt_factors.items():
    move_1sd = current_price * iv * factor
    expected_moves[dte] = {
        "1sd_move": round(move_1sd, 2),
        "1sd_low": round(current_price - move_1sd, 2),
        "1sd_high": round(current_price + move_1sd, 2),
        "2sd_move": round(2 * move_1sd, 2),
        "2sd_low": round(current_price - 2 * move_1sd, 2),
        "2sd_high": round(current_price + 2 * move_1sd, 2)
    }
```

**Step 3: Find 16Δ Strikes**
```python
# For covered calls (LONG position), find 16Δ call strike
# Approximate: 16Δ call ≈ current_price + 1SD_move (45 DTE)
target_16delta_call = expected_moves[45]["1sd_high"]

# From options chain, find closest strike to this price
# Or find strike with delta ≈ 0.16
```

**Step 4: Populate Table**
```markdown
| Timeframe | DTE | 1 SD Move (68%) | 2 SD Move (95%) | 16Δ Strike (84% OTM) |
|-----------|-----|-----------------|-----------------|----------------------|
| Weekly | 7 | ±${expected_moves[7]["1sd_move"]} | ±${expected_moves[7]["2sd_move"]} | ${strike_7d} |
| Monthly | 30 | ±${expected_moves[30]["1sd_move"]} | ±${expected_moves[30]["2sd_move"]} | ${strike_30d} |
| 45 DTE | 45 | ±${expected_moves[45]["1sd_move"]} | ±${expected_moves[45]["2sd_move"]} | ${strike_45d} ⭐ |
```
```

---

### Option B: Create Shared Calculation Helper (Alternative)

Create a new file: `EXPECTED_MOVES_CALCULATION_GUIDE.md` and reference it from both files.

**Pros:**
- Single source of truth
- Easier to maintain

**Cons:**
- Agent needs to reference another file
- Less self-contained

---

## 🎯 RECOMMENDATION

**Add calculation instructions to BOTH files:**

1. **SCANNER_REPORT_GENERATOR.md** - Add after line 388
2. **PORTFOLIO_INSTRUCTIONS.md** - Add after line 529

**Reasoning:**
- Self-contained (no cross-file references needed)
- Agent sees calculation immediately after template
- Reduces chance of agent skipping the calculation

---

## 📊 IMPACT ASSESSMENT

### Current State (With Template Only):
- ❌ Agent sees placeholders: `±$X.XX`, `$XXX`
- ❌ Agent doesn't know how to calculate values
- ❌ Agent might skip the section or leave placeholders
- ❌ Reports will have incomplete expected moves data

### After Adding Calculation Instructions:
- ✅ Agent knows to extract IV from analyze_options_mcmillan
- ✅ Agent knows formula application for each timeframe
- ✅ Agent can populate table with real values
- ✅ Reports will have actionable strike recommendations

---

## 🚀 NEXT STEPS

1. Add calculation instructions to SCANNER_REPORT_GENERATOR.md (after line 388)
2. Add calculation instructions to PORTFOLIO_INSTRUCTIONS.md (after line 529)
3. Test with real report generation
4. Verify calculated values match formula

---

## 📝 VERIFICATION CHECKLIST

After implementation, verify:
- [ ] Agent extracts `current_price` from analyze_options_mcmillan
- [ ] Agent extracts `current_iv` from analyze_options_mcmillan
- [ ] Agent calculates 1 SD moves for 7d, 30d, 45d, 90d
- [ ] Agent calculates 2 SD moves (2× 1 SD)
- [ ] Agent populates table with calculated values (no placeholders)
- [ ] Agent identifies 16Δ strikes approximately at 1 SD levels
- [ ] Final report shows expected moves like "±$24.09" not "±$X.XX"

---

## ✅ GAP CLOSED - IMPLEMENTATION COMPLETE

**Date Completed:** January 19, 2026

### What Was Added:

1. **SCANNER_REPORT_GENERATOR.md (lines 390-460):**
   - Complete Python calculation code
   - Step-by-step data extraction from analyze_options_mcmillan()
   - Pre-calculated square root factors for all timeframes
   - 16Δ strike approximation for LONG/SHORT candidates
   - Example output with real values (AAPL @ $228, 30% IV)

2. **PORTFOLIO_INSTRUCTIONS.md (lines 531-624):**
   - Same comprehensive calculation instructions
   - Portfolio-specific context (covered calls, protective puts)
   - Enhanced example showing 100 shares position
   - Complete covered call trade plan with profit calculations
   - Both standard deviation ranges AND optimal strike selection tables

### Verification:

- ✅ Both files now have templates AND calculation instructions
- ✅ Agent can extract current_price and IV from analyze_options_mcmillan()
- ✅ Agent can calculate 1 SD and 2 SD moves for all timeframes (7d, 30d, 45d, 90d)
- ✅ Agent can populate tables with real values (no more placeholders)
- ✅ Agent can identify approximate 16Δ strikes
- ✅ Examples show expected output format with actual numbers

---

**Status:** ✅ COMPLETE
**Priority:** HIGH - Gap successfully closed
**Actual Effort:** ~20 minutes to add instructions to both files
