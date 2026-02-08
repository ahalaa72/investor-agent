# Server.py Refactoring Status

**Date:** 2026-02-07
**Branch:** `questrade`
**Goal:** Break monolithic `server.py` (19,465 lines, 65+ @mcp.tool() functions) into modular subpackages.

---

## Architecture

```
investor_agent/
├── server.py              # Monolith (still 19,465 lines - not yet trimmed)
├── core/                  # Shared infrastructure (Phase 1 - DONE)
│   ├── __init__.py        # Re-exports all core utilities
│   ├── config.py          # Constants: BROWSER_HEADERS, INSTITUTIONAL_OPTIONS_PARAMS, etc.
│   ├── http.py            # api_retry, fetch_json, create_async_client, safe_future_result
│   ├── validation.py      # validate_ticker, validate_date, validate_date_range
│   └── price.py           # get_price_history_questrade_first, yf_call, get_options_chain, etc.
├── technical/             # Technical indicators (Phase 2 - DONE)
│   ├── __init__.py
│   └── indicators.py      # 13 detection functions (EMA, VWAP, volume, order blocks, etc.)
└── tools/                 # Tool modules with register_tools(mcp) pattern
    ├── __init__.py
    ├── market_data.py     # ✅ 6 tools (movers, fear/greed, trends, ticker_data, options)
    ├── questrade_api.py   # ✅ 14 tools (accounts, positions, quotes, candles, orders, etc.)
    ├── financial_data.py  # ✅ 5 tools (statements, holders, earnings, insiders, calendar)
    ├── position_mgmt.py   # ✅ 5 tools (position management, Greeks dashboard, trade flow)
    ├── technical_analysis.py # ✅ 4 tools (analyze_technical, support/resistance, compare, + bootstrap wrappers)
    ├── funds.py           # ✅ 3 tools (analyze_mutual_fund, compare_mutual_funds, analyze_etf)
    ├── risk.py            # ✅ 3 tools (concentration_limits, beta_weighted_delta, portfolio_var)
    ├── tracking.py        # ✅ 6 tools (ranking_validation, predictions CRUD, efficiency_report)
    ├── options_analysis.py # ❌ MISSING - 7 tools + ~25 helpers (lines 2156-7961)
    ├── ml_tools.py        # ❌ MISSING - 4 tools (lines 10163-11264)
    ├── scanning.py        # ❌ MISSING - 5 tools + ~12 helpers (lines 11265-13128)
    ├── catalysts.py       # ❌ MISSING - 5 tools + ~5 helpers (lines 14035-16693)
    └── signals.py         # ❌ MISSING - 2 tools (lines 13805-14034, 16594-18037)
```

## Completed Modules: 46 tools extracted

| Module | Tools | Lines | Status |
|--------|-------|-------|--------|
| market_data.py | 6 | 332 | ✅ Complete |
| questrade_api.py | 14 | 830 | ✅ Complete |
| financial_data.py | 5 | 183 | ✅ Complete |
| position_mgmt.py | 5 | 526 | ✅ Complete |
| technical_analysis.py | 4 | 456 | ✅ Complete |
| funds.py | 3 | 706 | ✅ Complete |
| risk.py | 3 | 872 | ✅ Complete |
| tracking.py | 6 | 822 | ✅ Complete |
| **Total extracted** | **46** | **4,727** | |

## Missing Modules: 23 tools remaining

### 1. options_analysis.py (Phase 4) - LARGEST MODULE
**7 tools, ~25 helper functions, ~5,800 lines of code**

Server.py line ranges:
- Helpers: 2156-4037 (`_get_earnings_proximity`, `_calculate_liquidity_tier`, `_get_tradier_option_bidask`, `_get_oi_with_yf_fallback`, `_calculate_liquidity_score`, `_find_target_expiry`, `_find_delta_strike`, `_get_questrade_options_with_greeks`, `_construct_iron_condor`, `_calculate_expected_move`, `_construct_calendar_spread`, `_construct_jade_lizard`, `_calculate_options_position_size`)
- More helpers: 6015-6636 (`_calculate_iv_analysis`, `_calculate_pc_ratio`, `_calculate_oi_analysis`, `_detect_unusual_activity`, `_get_questrade_greeks`, `_calculate_black_scholes_greeks`, `_calculate_vanna`, `_calculate_charm`)
- More helpers: 7570-7961 (`_estimate_greeks_from_chain`, `_get_iv_based_strategies`, `_calculate_options_quality_score`, `_select_mcmillan_strategy`, `_calculate_options_composite_score`)
- Tools: `analyze_options_mcmillan` (4037), `generate_options_trade_plan` (4614), `analyze_iv_skew` (5320), `analyze_iv_term_structure` (5742), `calculate_vanna` (6638), `analyze_expiration_charm` (6779), `analyze_gamma_exposure` (7171)

Cross-module deps (need late imports in register_tools):
- `from ..server import get_nasdaq_earnings_calendar, _get_ohlcv_cached`
- `from ..questrade import get_questrade_client`
- `INSTITUTIONAL_OPTIONS_PARAMS` from config

### 2. ml_tools.py (Phase 5)
**4 tools, lines 10163-11264**

Tools: `find_similar_historical_setups` (async), `analyze_ml_enhanced`, `validate_strategy_robustness` (async), `calculate_feature_importance_analysis` (async)

Cross-module deps:
- `from ..technical_analysis import TechnicalAnalysis`
- `from ..ml_core import get_trend_scanning_labels, apply_triple_barrier_labels, calculate_kelly_size, calculate_deflated_sharpe, calculate_feature_importance`
- `from ..ml_validation import harvey_liu_zhu_threshold`
- `from ..backtesting import SimilarityEngine, generate_similarity_report`
- `from ..technical.indicators import detect_ema_bounce, detect_ema_cross, ...` (all 13 indicator functions)
- `from ..technical_analysis_bootstrap import calculate_exhaustion_score, analyze_volume, ...`
- Bootstrap imports wrapped in try/except (`_bootstrap_available` flag)
- Volume/volatility tools at lines 9550-10163 are **inside** technical_analysis.py (already extracted)

### 3. scanning.py (Phase 6)
**5 tools, ~12 helpers, lines 11265-13128**

Helpers: `_get_ohlcv_for_ticker`, `_get_scan_cache`, `_set_scan_cache`, `get_feature_availability` (uses FeatureAvailability class), `detect_market_regime`, `_get_default_weights`, `_get_adaptive_weights`, `_get_ohlcv_for_ticker_v2`, `_get_ohlcv_cached`, `_create_options_summary`, `_get_recent_predictions`, `_scan_one_direction`

Tools: `scan_long_candidates`, `scan_short_candidates`, `get_raw_scan_candidates`, `scan_market_opportunities`, `scan_stocks_by_setup`

**CRITICAL:** `_get_ohlcv_cached` (line 11719) is used by many other modules (funds.py, catalysts.py, signals.py all import it via `from ..server import _get_ohlcv_cached`). This needs careful handling in Phase 8.

### 4. catalysts.py (Phase 6b)
**5 tools, ~5 helpers, lines 14035-16693**

Helpers: `_fetch_google_news`, `_web_search_news`, `_check_insider_selling_context`, `_analyze_news_sentiment`, `_verify_catalyst`

Tools: `detect_catalyst_strength`, `detect_insider_cluster`, `detect_unusual_options_activity`, `calculate_quality_score`, `analyze_competitors`

### 5. signals.py (Phase 7a)
**2 tools, 1 helper, lines 13805-14034 + 16594-18037**

Helper: `fetch_analysis_data` (line 16596)
Tools: `get_portfolio_summary` (13805), `generate_trading_signal` (16694 - MASSIVE ~1,340 lines, orchestrates 5-gate system)

Cross-module deps: `TechnicalAnalysis`, `detect_catalyst_strength`, `analyze_options_mcmillan`, `_get_ohlcv_cached`, `detect_market_regime`, `_create_options_summary`, `get_questrade_client`, and many more.

---

## Pattern for All Modules

```python
"""Module docstring."""
import logging
from ..core.config import ...
from ..core.price import ...
logger = logging.getLogger(__name__)

# Module-level helpers (no cross-module deps)
def _helper_function():
    ...

def register_tools(mcp):
    # Late imports to avoid circular dependencies
    from ..server import _get_ohlcv_cached, other_function

    @mcp.tool()
    def tool_name(...):
        ...
```

## Key Dependencies (Circular Import Risk)

| Function | Defined in server.py line | Used by modules |
|----------|--------------------------|-----------------|
| `_get_ohlcv_cached` | 11719 | funds.py, catalysts.py, signals.py, scanning.py |
| `get_nasdaq_earnings_calendar` | 8140 | options_analysis.py |
| `analyze_technical` | 9550 (inside conditional) | funds.py (analyze_etf) |
| `analyze_options_mcmillan` | 4037 | funds.py (analyze_etf), signals.py |
| `detect_market_regime` | 11394 | scanning.py, signals.py |
| `_create_options_summary` | 11759 | signals.py |
| `get_questrade_positions` | 8264 | risk.py |
| `get_questrade_balances` | 8322 | risk.py |

All resolved via late imports inside `register_tools()`.

## Phase 8 Plan (Wire Everything)

Once all 5 missing modules are created:
1. Add `from .tools.X import register_tools as register_X_tools` for each module
2. Call all `register_X_tools(mcp)` after `mcp = FastMCP(...)` in server.py
3. Remove the duplicated tool functions and helpers from server.py
4. Keep only: imports, mcp creation, shared helpers that are imported by other modules
5. Gradually move shared helpers (`_get_ohlcv_cached`, etc.) to appropriate modules

## server.py Tool Line Map (for extraction reference)

```
Lines 1847-2090:    market_data tools (already in market_data.py)
Lines 2156-7961:    options helpers + tools (→ options_analysis.py)
Lines 8045-8139:    financial_data tools (already in financial_data.py)
Lines 8140-8218:    get_nasdaq_earnings_calendar (financial_data.py)
Lines 8218-9039:    questrade_api tools (already in questrade_api.py)
Lines 9040-9470:    position_mgmt tools (already in position_mgmt.py)
Lines 9550-10162:   technical_analysis tools (already in technical_analysis.py)
Lines 10163-11264:  ML tools (→ ml_tools.py)
Lines 11265-13128:  scanning helpers + tools (→ scanning.py)
Lines 13129-13802:  fund helpers + tools (already in funds.py)
Lines 13805-14034:  get_portfolio_summary (→ signals.py)
Lines 14035-16693:  catalyst helpers + tools (→ catalysts.py)
Lines 16694-18037:  generate_trading_signal + helper (→ signals.py)
Lines 18038-18842:  tracking helpers + tools (already in tracking.py)
Lines 18843-19465:  risk helpers + tools (already in risk.py)
```

## Bug Fixes in Plan (Not Yet Applied)

- BUG-1: Options position sizing
- BUG-2,3: Signal generation issues
- BUG-4: Position management
- BUG-5: ML tools
- BUG-6: Scanning
- BUG-7,8,9,10: Various
- BUG-11: Tracking
- R-2: Scanning fix
- R-4: Already fixed in core/price.py (removed `_get_current_price` $100 fallback)

## Next Steps

1. Create 5 missing modules (options_analysis.py, ml_tools.py, scanning.py, catalysts.py, signals.py)
2. Phase 8: Wire all modules into server.py
3. Rebuild Docker container
4. Test all 65+ tools via MCP
