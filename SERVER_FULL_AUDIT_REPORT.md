# server.py Full Audit Report

**Date:** February 7, 2026
**File:** `investor_agent/server.py` (19,281 lines)
**Scope:** Complete categorization of all 73 MCP tools, bug identification, redundancy analysis, inconsistency review
**Status:** AUDIT COMPLETE -- Implementation pending

---

## Table of Contents

1. [73 MCP Tools Categorized](#73-mcp-tools-categorized)
2. [Bugs](#bugs-verified-sorted-by-severity) (11 total: 3 CRITICAL, 4 HIGH, 4 MEDIUM)
3. [Redundancy Issues](#redundancy-overlapping-functionality) (5 total)
4. [Inconsistency Issues](#inconsistencies) (5 total)
5. [Implementation Checklist](#implementation-checklist)

---

## 73 MCP Tools Categorized

| # | Category | Tools | Count |
|---|----------|-------|-------|
| 1 | **Market Sentiment** | `get_market_movers`, `get_cnn_fear_greed_index`, `get_crypto_fear_greed_index`, `get_google_trends` | 4 |
| 2 | **Ticker Data** | `get_ticker_data`, `get_financial_statements`, `get_institutional_holders`, `get_earnings_history`, `get_insider_trades`, `get_nasdaq_earnings_calendar` | 6 |
| 3 | **Options Data** | `get_options`, `get_questrade_options_chain`, `get_questrade_option_quotes` | 3 |
| 4 | **Options Analysis** | `analyze_options_mcmillan`, `generate_options_trade_plan`, `analyze_iv_skew`, `analyze_iv_term_structure`, `calculate_vanna`, `analyze_expiration_charm`, `analyze_gamma_exposure` | 7 |
| 5 | **Questrade Account** | `get_questrade_accounts`, `get_questrade_positions`, `get_questrade_balances`, `get_questrade_quotes`, `get_questrade_candles`, `search_questrade_symbols`, `get_questrade_symbol_info`, `get_questrade_markets`, `get_questrade_orders`, `get_questrade_order`, `get_questrade_executions`, `get_questrade_activities` | 12 |
| 6 | **Position Management** | `evaluate_options_position_management`, `get_portfolio_greeks_dashboard` | 2 |
| 7 | **Order Flow** | `analyze_realtime_trade_flow`, `get_bid_ask_imbalance`, `analyze_spread_dynamics` | 3 |
| 8 | **Technical Analysis** | `calculate_technical_indicator`, `analyze_technical`, `find_support_resistance`, `compare_technical` | 4 |
| 9 | **Volume/Volatility/RS** | `analyze_volume_tool`, `analyze_volatility_tool`, `calculate_relative_strength_tool`, `calculate_fundamental_scores_tool` | 4 |
| 10 | **ML & Historical** | `find_similar_historical_setups`, `analyze_ml_enhanced`, `validate_strategy_robustness`, `calculate_feature_importance_analysis` | 4 |
| 11 | **Market Scanning** | `scan_long_candidates`, `scan_short_candidates`, `get_raw_scan_candidates`, `scan_market_opportunities`, `scan_stocks_by_setup` | 5 |
| 12 | **Fund/ETF/Portfolio** | `analyze_mutual_fund`, `compare_mutual_funds`, `analyze_etf`, `get_portfolio_summary` | 4 |
| 13 | **Catalyst & Quality** | `detect_catalyst_strength`, `detect_insider_cluster`, `detect_unusual_options_activity`, `calculate_quality_score`, `analyze_competitors` | 5 |
| 14 | **Signal Generation** | `generate_trading_signal` | 1 |
| 15 | **Prediction Tracking** | `get_ranking_validation_report`, `store_trading_prediction`, `get_cached_predictions`, `get_best_cached_trades`, `update_prediction_outcomes`, `generate_efficiency_report` | 6 |
| 16 | **Portfolio Risk** | `check_portfolio_concentration_limits`, `calculate_portfolio_beta_weighted_delta`, `calculate_portfolio_var` | 3 |

**Total: 73 tools across 16 categories**

---

## BUGS (Verified, sorted by severity)

### CRITICAL -- Affects real money decisions

#### BUG-1: Liquidity score missing 45% of its weight
- **Location:** Lines 2649, 2665
- **Function:** `_calculate_liquidity_score`
- **Problem:** `oi_score` (25% weight) and `vol_score` (20% weight) are computed but NEVER added to `score`. Only `spread_score` (35%), `under_score` (10%), and `size_score` (10%) are accumulated.
- **Impact:** Max achievable liquidity score is 55/100. Options with excellent OI and volume still get "C" or "F" grades. Valid options trades get rejected as illiquid.
- **Fix:** Add `score += oi_score` after line 2648 and `score += vol_score` after line 2665.
- **Effort:** 2 lines

#### BUG-2: `dir()` doesn't check local variables
- **Location:** Line 17248
- **Function:** `generate_trading_signal` (freshness analysis block)
- **Problem:** `if 'cdf_20d' in dir()` checks **module** scope, not function locals. The Dollar Flow block ($500M threshold) may silently never execute.
- **Impact:** The FSLR-type protection (blocking trades against massive institutional flows) might not work. This is the safety net that prevents LONG trades against billion-dollar distribution.
- **Fix:** Use `'cdf_20d' in locals()` or initialize `cdf_20d = 0` before the try block.
- **Effort:** 1 line

#### BUG-3: SHORT returns calculated as LONG returns
- **Location:** Lines 17988-17994
- **Function:** `validate_pick_outcomes`
- **Problem:** Always calculates returns as `(close - entry) / entry`, even for SHORT positions where it should be `(entry - close) / entry`.
- **Impact:** The `get_ranking_validation_report` shows inverted returns for SHORT picks. A successful SHORT that dropped 5% shows as -5% return instead of +5%. This makes the ranking validation report misleading for SHORT side analysis.
- **Fix:** Invert the formula when `direction == "SHORT"`.
- **Effort:** 3 lines

---

### HIGH -- Significant logic errors

#### BUG-4: Calendar spread uses wrong option's fallback price
- **Location:** Line 3651
- **Function:** Calendar spread strategy builder
- **Problem:** `back_premium = float(back_option.get('ask', 0) or front_option.get('lastPrice', 0))` -- falls back to `front_option` instead of `back_option`.
- **Impact:** Calendar spread debit calculation can be wrong, leading to incorrect risk/reward.
- **Fix:** Change `front_option` to `back_option` in the fallback.
- **Effort:** 1 character

#### BUG-5: EMA extension NORMAL counted as both bullish AND bearish
- **Location:** Lines 10619, 10650
- **Function:** `analyze_ml_enhanced`
- **Problem:** `ema_extension_20['signal'] == 'NORMAL'` adds +1 to BOTH `bullish_signals` and `bearish_signals`, canceling out and inflating both counts.
- **Impact:** Reduces discriminative power of ML analysis. Every stock with normal EMA extension gets polluted signals.
- **Fix:** Remove NORMAL from one or both signal categories, or don't count NORMAL at all.
- **Effort:** 2 lines

#### BUG-6: 10b5-1 discount sets key on non-existent dict
- **Location:** Line 15154
- **Function:** `detect_catalyst_strength`
- **Problem:** `result["details"]["insider"]["10b5_1_discount"]` tries to set a nested key, but `result["details"]["insider"]` isn't created until line 15189.
- **Impact:** When insider selling is detected with a 10b5-1 plan, the discount data is silently lost (caught by except). The bearish score still gets discounted in `insider_bearish_final`, but the tracking data is lost.
- **Fix:** Move the `result["details"]["insider"]` dict creation before line 15154, or initialize it earlier.
- **Effort:** 3 lines

#### BUG-7: Portfolio Greeks dashboard uses hardcoded placeholder values
- **Location:** Lines 9256-9261
- **Function:** `get_portfolio_greeks_dashboard`
- **Problem:** Every options position gets `delta=0.5, theta=-0.15, vega=1.0, gamma=0.01` regardless of actual option characteristics.
- **Impact:** Portfolio Greeks dashboard returns completely fictional data. Users relying on this for risk management are misled.
- **Fix:** Fetch actual Greeks from Questrade options quotes API, or clearly label values as estimates.
- **Effort:** 20+ lines (needs Questrade API integration)

---

### MEDIUM -- Could cause issues

#### BUG-8: Credit spread dict indentation error
- **Location:** Lines 5229-5237
- **Function:** Options trade plan credit spread builder
- **Problem:** `max_loss_per_contract`, `break_even`, `probability_of_profit`, `reward_risk_ratio` are at wrong indentation level inside the `risk_reward` dict. Python may interpret this as a syntax error or malformed dict depending on exact whitespace.
- **Fix:** Verify and correct indentation.
- **Effort:** 4 lines

#### BUG-9: `.iloc` used with label-based index from `.idxmin()`
- **Location:** Line 4365
- **Function:** IV term structure analysis
- **Problem:** `.idxmin()` returns a label-based index but `.iloc` expects integer position. Can return wrong row if DataFrame index isn't default RangeIndex.
- **Fix:** Use `.loc` instead of `.iloc`.
- **Effort:** 1 line

#### BUG-10: Position management uses stale yfinance price
- **Location:** Line 9112
- **Function:** `evaluate_options_position_management`
- **Problem:** Calls `yf.Ticker()` directly instead of using `get_current_price_questrade_first` helper, bypassing real-time Questrade data.
- **Fix:** Use `get_current_price_questrade_first(symbol)`.
- **Effort:** 1 line

#### BUG-11: Sector PE median hardcoded to 20
- **Location:** Line 17528
- **Function:** `generate_trading_signal` (entry strategy)
- **Problem:** Uses `sector_pe_median = 20` placeholder for all stocks. Tech stocks (median ~35) and utility stocks (median ~12) get systematically biased entry sizing.
- **Fix:** Fetch actual sector PE from ticker data or use a lookup table.
- **Effort:** 10+ lines

---

## REDUNDANCY (Overlapping functionality)

#### R-1: Two prediction tracking systems running simultaneously
- **JSON-based:** `_pick_history` list, `track_scanner_pick()`, `validate_pick_outcomes()`, `get_ranking_validation_report()` (lines 17850-18240)
- **DB-based:** `PredictionTracker`, `store_trading_prediction()`, `update_prediction_outcomes()`, `generate_efficiency_report()` (lines 18248-18656)
- Both track the same data (entry, stop, target, returns, outcomes). The JSON system is legacy. Both run in parallel doubling tracking work.
- **Recommendation:** Remove JSON-based system, consolidate to DB-only.

#### R-2: `scan_market_opportunities` duplicates `_scan_one_direction`
- `scan_long_candidates` and `scan_short_candidates` call `_scan_one_direction` (the reusable helper).
- `scan_market_opportunities` (line 12441) reinvents the same batch/validate/rank logic inline (~500 lines) instead of calling `_scan_one_direction` twice.
- **Recommendation:** Refactor `scan_market_opportunities` to call `_scan_one_direction("LONG")` and `_scan_one_direction("SHORT")`.

#### R-3: Options chain fetching copy-pasted across 6+ functions
- `_get_questrade_options_with_greeks` exists as the reusable helper (line 3130).
- But `analyze_options_mcmillan`, `analyze_iv_skew`, `analyze_iv_term_structure`, `analyze_expiration_charm`, `analyze_gamma_exposure`, and `get_questrade_options_chain` each copy-paste the Questrade->Yahoo fallback pattern with subtly different error handling.
- **Recommendation:** Consolidate all options chain fetching through `_get_questrade_options_with_greeks`.

#### R-4: Three functions to get current price with different failure modes
- `get_current_price_questrade_first` (line 399): Raises ValueError
- `_get_current_price` (line 2925): Returns $100.00 on failure (dangerous!)
- Direct `yf.Ticker().info` in `evaluate_options_position_management` (line 9112)
- **Recommendation:** Standardize on `get_current_price_questrade_first` everywhere. Remove `_get_current_price` or make it raise instead of returning $100.

#### R-5: `detect_catalyst_strength` duplicates `detect_unusual_options_activity`
- Both fetch options chains, check volume/OI ratios, classify activity. When `generate_trading_signal` calls `detect_catalyst_strength`, it performs its own options analysis internally instead of delegating to `detect_unusual_options_activity`.
- **Recommendation:** Have `detect_catalyst_strength` call `detect_unusual_options_activity` internally instead of duplicating the logic.

---

## INCONSISTENCIES

#### I-1: "4-gate" vs "5-gate" labeling mixed throughout
- Docstrings, comments, and log messages inconsistently reference "4-gate" and "5-gate".
- Example: `_scan_one_direction` says "4-gate system" in comment (line 11899) but `scan_long_candidates` docstring says "5-gate" (line 12235). Scan output shows `4/4 gates` format mixing with `5/5 gates`.
- **Recommendation:** Standardize to "5-gate" everywhere (the current system has 5 gates).

#### I-2: `gates_passed` means different things in different contexts
- In `generate_trading_signal`: counts all 5 gates (including options_tradability)
- In `_scan_one_direction`: counts 4 core gates only
- In `get_best_cached_trades` SQL query: uses `min_gates=3` default with no clarity on denominator
- **Recommendation:** Clearly distinguish `core_gates_passed` (out of 4) vs `total_gates_passed` (out of 5) in all outputs.

#### I-3: Return types vary unpredictably
- Some tools return `dict`: `get_ticker_data`, `get_questrade_quotes`, `analyze_technical`
- Some tools return `str` (CSV): `get_options`, `get_market_movers`, `get_earnings_history`, `get_insider_trades`
- `get_financial_statements` returns `dict[str, str]` (dict of CSVs)
- **Recommendation:** Standardize on dict returns with optional `format` parameter for CSV output.

#### I-4: Parameter naming inconsistent
- `ticker` (most tools) vs `ticker_symbol` (`get_options`) vs `symbol` (Questrade tools)
- **Recommendation:** Standardize on `ticker` for analysis tools and `symbol` for Questrade-specific tools, document the convention.

#### I-5: Error handling has 4 different patterns
- Raise ValueError
- Return `{"error": msg}`
- Return error string
- Silently return default value ($100 price)
- **Recommendation:** Standardize: raise for programming errors, return `{"error": msg}` for user-facing errors. Never silently return fake defaults.

---

## Implementation Checklist

Priority order for fixing. Check off each item as it's implemented.

### Phase 1: Critical Bugs (Do First)
- [ ] **BUG-1:** Add `score += oi_score` and `score += vol_score` to `_calculate_liquidity_score` (2 lines)
- [ ] **BUG-2:** Change `dir()` to `locals()` in Dollar Flow check (1 line)
- [ ] **BUG-3:** Fix SHORT return calculation in `validate_pick_outcomes` (3 lines)

### Phase 2: High Bugs
- [ ] **BUG-4:** Fix calendar spread fallback from `front_option` to `back_option` (1 char)
- [ ] **BUG-5:** Remove NORMAL EMA extension from bullish+bearish double-counting (2 lines)
- [ ] **BUG-6:** Move insider dict initialization before 10b5-1 discount assignment (3 lines)
- [ ] **BUG-7:** Replace hardcoded Greeks with actual Questrade option quotes (20+ lines)

### Phase 3: Medium Bugs
- [ ] **BUG-8:** Fix credit spread dict indentation (4 lines)
- [ ] **BUG-9:** Change `.iloc` to `.loc` for label-based index (1 line)
- [ ] **BUG-10:** Replace `yf.Ticker()` with `get_current_price_questrade_first` in position management (1 line)
- [ ] **BUG-11:** Replace hardcoded sector PE=20 with dynamic lookup (10+ lines)

### Phase 4: Redundancy Cleanup
- [ ] **R-1:** Remove legacy JSON prediction tracking, keep DB-only
- [ ] **R-2:** Refactor `scan_market_opportunities` to use `_scan_one_direction`
- [ ] **R-3:** Consolidate options chain fetching through single helper
- [ ] **R-4:** Standardize price fetching, remove `_get_current_price` $100 fallback
- [ ] **R-5:** Have `detect_catalyst_strength` delegate to `detect_unusual_options_activity`

### Phase 5: Consistency Standardization
- [ ] **I-1:** Standardize all references to "5-gate" system
- [ ] **I-2:** Clarify `gates_passed` denominator in all contexts
- [ ] **I-3:** Standardize return types (dict preferred)
- [ ] **I-4:** Standardize parameter naming convention
- [ ] **I-5:** Standardize error handling patterns

---

## Testing Protocol

After each fix:
1. Rebuild using `rebuild.sh`
2. Test ONLY via MCP tool calls (never use `python` command)
3. Verify fix with relevant tool (e.g., BUG-1 fix -> test `analyze_options_mcmillan` to check liquidity grades)
4. Run a scan to verify no regressions (`scan_long_candidates`, `scan_short_candidates`)

---

*Generated by Claude Opus 4.6 during comprehensive server.py audit session*
