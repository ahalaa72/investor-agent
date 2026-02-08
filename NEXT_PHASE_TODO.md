# Phase 2: Structural Refactors & Bug Fixes

**Created:** 2026-02-07
**Completed:** 2026-02-08
**Status:** DONE (all items except I3 which is deferred to Phase 4)
**Prerequisite:** Phase 1 complete (15 bug fixes, 68 tools verified, Docker rebuilt)

## Completion Summary

| Item | Status | Lines Changed |
|------|--------|---------------|
| BUG-NEW-3: Dalio dict extraction | DONE | signals.py:330-338 |
| BUG-NEW-4: Brooks import path | DONE | signals.py:704,1161 + position_mgmt.py:118 |
| R1: Remove JSON backup | DONE | prediction_tracker.py (-25 lines) |
| R2: scan_market_opportunities refactor | DONE | scanning.py (-190 lines) |
| R3: _fetch_yf_option_chain helper | DONE | options_analysis.py (11 sites) |
| R5: UOA threshold constants | DONE | catalysts.py:19-22,791,797,2002-2004 |
| I5: Error handling standardization | DONE | financial_data.py:179,183 + market_data.py:70 |
| I3: Return type standardization | DEFERRED | Breaking MCP API change → Phase 3 |

---

## Priority 1: Runtime Bugs (Fix First)

### BUG-NEW-3: Dalio Ratio Dict-vs-Float Comparison

**Error:** `'>=' not supported between instances of 'dict' and 'float'`
**Observed in:** `get_portfolio_summary` for stocks like FIG, LRCX
**Severity:** HIGH — crashes portfolio analysis for affected stocks

**Root Cause:**
The `dalio_ratio` field in `volume_analysis["dalio_metrics"]` is a **nested dict**, not a float:
```python
"dalio_ratio": {
    "current": 0.85,
    "5d_avg": 0.92,
    "20d_avg": 1.05,
    "interpretation": "Balanced"
}
```

Two extraction patterns exist — one correct, one broken:

| Location | Code | Returns |
|----------|------|---------|
| `signals.py:964` | `dalio_metrics.get("dalio_ratio", {}).get("20d_avg", 1.0)` | **float** (correct) |
| `signals.py:330` | `dalio.get("dalio_ratio", 1.0)` | **dict** (BUG) |

**Where it crashes:**
- `signals.py:337` — `dalio_ratio >= 1.0` (dict >= float)
- `signals.py:338` — `dalio_ratio < 1.0` (dict < float)

**Fix:**
```python
# Line 330: Change from:
dalio_ratio = dalio.get("dalio_ratio", 1.0)
# To:
dalio_ratio = dalio.get("dalio_ratio", {}).get("20d_avg", 1.0)
```

**Files:** `investor_agent/tools/signals.py` lines 330, 337-338
**Risk:** LOW — straightforward type fix, no API change
**Testing:** `get_portfolio_summary` with account `51673853` — verify no Dalio errors

---

### BUG-NEW-4: Brooks Analyzer Import Path Broken

**Error:** `No module named 'investor_agent.al_brooks_analyzer'`
**Observed in:** `generate_trading_signal` — Gate 3 (Brooks) returns ERROR
**Severity:** HIGH — Gate 3 always fails, degrading 5-gate validation

**Root Cause:**
The `AlBrooksAnalyzer` class lives in `investor_agent/scanner_analyzer.py` (line 71), but 3 files import from a non-existent path:

| File | Line | Import (BROKEN) |
|------|------|-----------------|
| `tools/signals.py` | 704 | `from ..al_brooks_analyzer import AlBrooksAnalyzer` |
| `tools/signals.py` | 1161 | `from ..al_brooks_analyzer import AlBrooksAnalyzer` |
| `tools/position_mgmt.py` | 118 | `from investor_agent.al_brooks_analyzer import AlBrooksAnalyzer` |

**Correct import** (already used in `tools/technical_analysis.py:60`):
```python
from investor_agent.scanner_analyzer import AlBrooksAnalyzer
```

**Fix:**
```python
# signals.py lines 704 and 1161: Change to:
from ..scanner_analyzer import AlBrooksAnalyzer

# position_mgmt.py line 118: Change to:
from investor_agent.scanner_analyzer import AlBrooksAnalyzer
```

**Files:** `investor_agent/tools/signals.py` (2 locations), `investor_agent/tools/position_mgmt.py` (1 location)
**Risk:** LOW — import path fix only, no logic change
**Testing:** `generate_trading_signal(ticker="AAPL")` — verify Gate 3 no longer shows ERROR

---

## Priority 2: Redundancy Removal

### R1: Dual Prediction Tracking (JSON + Database)

**Problem:** Predictions are stored in BOTH a JSON file and MSSQL database, creating sync issues.

**Current Architecture:**
```
store_trading_prediction()
    └─ PredictionTracker.store_prediction()
        ├─ Database INSERT (line 205) → MSSQL predictions table (50+ columns)
        └─ JSON backup (line 208) → investor_agent/predictions/{ticker}_{date}_{id}.json
```

Additionally, `tracking.py` has a separate JSON-based pick tracker:
- `pick_history.json` loaded at module import (line 249)
- `_load_pick_history()` / `_save_pick_history()` (lines 25-45)
- `track_scanner_pick()` appends to in-memory list + saves JSON (lines 104-105)

**Components:**

| System | Storage | Read | Write | Update |
|--------|---------|------|-------|--------|
| Prediction Tracker | MSSQL `predictions` table | `execute_query()` | `execute_insert()` | `execute_insert()` (UPDATE) |
| Prediction JSON Backup | `predictions/` dir | Never read back | `json.dump()` (line 257) | Never updated |
| Pick History | `pick_history.json` | `json.load()` (line 31) | `json.dump()` (line 42) | In-memory append |

**Recommended Approach:**
1. Remove JSON backup from `prediction_tracker.py` (line 208, `_save_json_backup` method)
2. Keep `pick_history.json` for now — it serves a different purpose (scanner validation, not signal tracking)
3. Add a `full_analysis_json` column query for when full signal data is needed (already stored in DB at line 200)

**Files:** `investor_agent/prediction_tracker.py` (lines 208, 240-257)
**Risk:** MEDIUM — must verify nothing reads from JSON backup files
**Testing:** `store_trading_prediction` → verify prediction stored in DB only

---

### R2: `scan_market_opportunities` Duplicates `_scan_one_direction`

**Problem:** ~400 lines of duplicated scanning logic.

**Current Structure:**
```
scan_market_opportunities() (lines 1213-1738, 525 lines)
  ├─ Scanner setup (lines 1298-1316) — DUPLICATED from _scan_one_direction (702-717)
  ├─ LONG candidate fetch (lines 1349-1356) — DUPLICATED
  ├─ SHORT candidate fetch (lines 1363-1370) — DUPLICATED
  ├─ LONG validation loop (lines 1378-1440) — DUPLICATED
  ├─ SHORT validation loop (lines 1446-1510) — DUPLICATED (again!)
  ├─ LONG results sorting (lines 1512-1540) — DUPLICATED
  └─ SHORT results sorting (lines 1542-1565) — DUPLICATED
```

**Optimal Structure:**
```
scan_market_opportunities()
  ├─ long_results = _scan_one_direction("LONG", ...)
  ├─ short_results = _scan_one_direction("SHORT", ...)
  └─ Combine + format final report (~50 lines)
```

**Refactor Steps:**
1. Ensure `_scan_one_direction` returns all fields that `scan_market_opportunities` needs
2. Add any missing return fields (e.g., `progress_log`, `rejection_reasons`)
3. Replace the 6 duplicated blocks with 2 calls to `_scan_one_direction`
4. Keep the combine/format section that merges LONG + SHORT results
5. **Expected reduction:** ~525 lines → ~100 lines

**Files:** `investor_agent/tools/scanning.py` (lines 1213-1738)
**Risk:** MEDIUM — must ensure identical behavior after refactor
**Testing:** `scan_market_opportunities` — compare output before/after

---

### R3: Options Chain Fetching Copy-Paste

**Problem:** `t.option_chain(expiry)` fetch pattern is copy-pasted across 8 functions with 11 total occurrences.

**Occurrences:**

| Function | Lines | Calls | Notes |
|----------|-------|-------|-------|
| `_get_oi_with_yf_fallback` | 412 | 1 | Single expiry |
| `analyze_options_mcmillan` | 2985, 3131 | 2 | Primary + nested fallback |
| `generate_options_trade_plan` | 3567, 3794-3795 | 3 | Single + dual for calendar |
| `analyze_iv_skew` | 4269 | 1 | Single expiry |
| `analyze_iv_term_structure` | 4652 | N | **Loop** — multiple expiries |
| `calculate_vanna` | 4844 | 1 | Single strike extraction |
| `analyze_expiration_charm` | 5182 | 1 | Single expiry |
| `analyze_gamma_exposure` | 5552 | 1 | Single expiry |

**Proposed Helper:**
```python
def _fetch_yf_chain(ticker: str, expiry: str, option_type: str | None = None) -> dict:
    """Fetch options chain from yfinance with error handling.

    Returns:
        {"calls": DataFrame, "puts": DataFrame} or
        {"options": DataFrame} if option_type specified
    """
    t = yfinance.Ticker(ticker)
    chain = t.option_chain(expiry)
    if option_type == "call":
        return {"options": chain.calls}
    elif option_type == "put":
        return {"options": chain.puts}
    return {"calls": chain.calls, "puts": chain.puts}
```

**Files:** `investor_agent/tools/options_analysis.py` (11 locations across 8 functions)
**Risk:** LOW — extract method refactor, no behavior change
**Testing:** Run each of the 8 affected tools once to verify

---

### R5: Catalyst Duplicates UOA Thresholds

**Problem:** "Unusual options activity" thresholds are defined independently in two places.

**Threshold Definitions:**

| Location | Threshold | Value |
|----------|-----------|-------|
| `detect_unusual_options_activity` (line 2001) | Vol/OI ratio | `vol > 2 * oi` (2.0x) |
| `detect_unusual_options_activity` (line 2003) | Premium filter | `premium > 50000` ($50k) |
| `_verify_catalyst` (line 785) | Vol/OI HIGH | `vol_oi_ratio >= 2.0` |
| `_verify_catalyst` (line 790) | Vol/OI MEDIUM | `vol_oi_ratio >= 1.5` |

**Fix:** Extract thresholds into module-level constants:
```python
UOA_VOL_OI_HIGH = 2.0
UOA_VOL_OI_MEDIUM = 1.5
UOA_PREMIUM_MIN = 50_000
```

**Files:** `investor_agent/tools/catalysts.py` (lines 785-800, 2001-2013)
**Risk:** LOW — constant extraction only
**Testing:** `detect_catalyst_strength(ticker="AAPL")` and `detect_unusual_options_activity(ticker="AAPL")`

---

## Priority 3: Inconsistency Fixes

### I3: Return Type Standardization

**Problem:** MCP tools return 3 different types across modules.

**Current Distribution (49 tools sampled):**

| Return Type | Count | Modules |
|-------------|-------|---------|
| `dict` | 41 (84%) | catalysts, funds, options, position_mgmt, questrade, risk, scanning, signals, technical, tracking |
| `string` (markdown) | 4 (8%) | ml_tools (all 4 tools) |
| `csv` | 3 (6%) | financial_data, market_data (get_options, get_google_trends) |
| `mixed` | 1 (2%) | market_data (varies by tool) |

**Recommendation:** This is a **breaking MCP API change**. Defer to Phase 3 unless clients are under your control.

**If proceeding:**
1. Convert `ml_tools.py` string returns → `{"report": "...", "summary": {...}}` dict
2. Convert CSV returns in `market_data.py` and `financial_data.py` → `{"data": [...], "columns": [...]}` dict
3. Update all MCP clients consuming these tools

**Files:** `investor_agent/tools/ml_tools.py`, `investor_agent/tools/market_data.py`, `investor_agent/tools/financial_data.py`
**Risk:** HIGH — breaks existing MCP client integrations
**Testing:** All affected tools + MCP client compatibility

---

### I5: Error Handling Pattern Standardization

**Problem:** 4 different error handling patterns coexist.

**Current Patterns:**

| Pattern | Example | Used In |
|---------|---------|---------|
| `raise ValueError(msg)` | `risk.py _get_current_price` | Internal helpers |
| `return {"error": msg}` | `scanning.py scan_long_candidates` | MCP tools (most common) |
| `return f"Error: {msg}"` | `ml_tools.py analyze_ml_enhanced` | ML tools |
| Silent fallback | `catalysts.py` try/except pass | Background operations |

**Recommended Standard:**
```python
# For MCP-exposed tools: Always return dict with "error" key
try:
    result = do_work()
    return {"status": "success", **result}
except Exception as e:
    logger.error(f"tool_name failed: {e}")
    return {"status": "error", "error": str(e)}

# For internal helpers: raise exceptions (let caller handle)
def _helper():
    if bad:
        raise ValueError("reason")
```

**Scope:** All 13 tool modules
**Risk:** MEDIUM — must audit every try/except and return path
**Testing:** Trigger error conditions in each tool to verify consistent format

---

## Priority 4: Previously Untested Tools — NOW TESTED

**Tested:** 2026-02-08
**Status:** ALL PASS

### Heavy Scanners

| Tool | Status | Runtime | Result |
|------|--------|---------|--------|
| `scan_long_candidates` | PASS | 80s | 5 scanned, 1 returned (AAPL from DB cache). Batch processing, progress log, DB dedup all working. |
| `scan_short_candidates` | PASS | 69s | 5 scanned, 1 returned (INTC 3/5 relaxed). Direction conflict detection working. |
| `scan_market_opportunities` | PASS | (tested via R2 refactor) | Delegates to `_scan_one_direction` x2. data_driven + timeout params working. |

### Write Operations

| Tool | Status | Result |
|------|--------|--------|
| `store_trading_prediction` | PASS | Stored via `generate_trading_signal(AAPL, auto_store=true)`, prediction ID `f57015c4-2961-4fba-a58a-2daca215f599` |
| `update_prediction_outcomes` | PASS | Updated 218/225 open predictions, validated 216 |

---

## Implementation Order

```
Phase 2a (Quick Wins — 30 min):
  1. BUG-NEW-3: Fix Dalio dict extraction (1 line)
  2. BUG-NEW-4: Fix Brooks import path (3 lines across 2 files)
  3. R5: Extract UOA threshold constants (5 lines)
  4. Docker rebuild + test

Phase 2b (Medium Refactors — 2 hrs):
  5. R3: Extract _fetch_yf_chain helper, update 8 functions
  6. R1: Remove JSON backup, verify DB-only storage
  7. Docker rebuild + test

Phase 2c (Large Refactor — 3 hrs):
  8. R2: Refactor scan_market_opportunities to use _scan_one_direction
  9. I5: Standardize error handling across all modules
  10. Docker rebuild + full regression test

Phase 3 (Testing — 2026-02-08): ✅ DONE
  11. store_trading_prediction: PASS (auto_store via generate_trading_signal)
  12. update_prediction_outcomes: PASS (218/225 updated, 216 validated)
  13. scan_long_candidates: PASS (80s, 5 scanned, batch/dedup working)
  14. scan_short_candidates: PASS (69s, 5 scanned, direction conflict detection working)

Phase 4 (Breaking Changes — Separate PR):
  15. I3: Return type standardization (breaking MCP API change)
```

---

## Files Reference

| File | Changes | Priority |
|------|---------|----------|
| `investor_agent/tools/signals.py` | BUG-NEW-3 (line 330), BUG-NEW-4 (lines 704, 1161) | P1 |
| `investor_agent/tools/position_mgmt.py` | BUG-NEW-4 (line 118) | P1 |
| `investor_agent/prediction_tracker.py` | R1 (line 208, lines 240-257) | P2 |
| `investor_agent/tools/scanning.py` | R2 (lines 1213-1738) | P2 |
| `investor_agent/tools/options_analysis.py` | R3 (11 locations) | P2 |
| `investor_agent/tools/catalysts.py` | R5 (lines 785-800, 2001-2013) | P2 |
| `investor_agent/tools/ml_tools.py` | I3 (4 tools), I5 | P3 |
| `investor_agent/tools/market_data.py` | I3 (2 tools) | P3 |
| `investor_agent/tools/financial_data.py` | I3 (1 tool) | P3 |
| All 13 tool modules | I5 error handling audit | P3 |
