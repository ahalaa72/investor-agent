"""
Constants and configuration for the investor-agent system.

Reference: McMillan "Options as a Strategic Investment" + TastyTrade Research
"""

# Minimal HTTP Headers - only essential ones
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# =============================================================================
# INSTITUTIONAL OPTIONS TRADING PARAMETERS
# Reference: McMillan "Options as a Strategic Investment" + TastyTrade Research
# =============================================================================

INSTITUTIONAL_OPTIONS_PARAMS = {
    # Entry Criteria
    'min_iv_percentile': 50,           # Ideal > 70% for selling premium
    'target_dte': 45,                  # Optimal entry: 40-50 DTE
    'short_strike_delta': 16,          # 16-delta for credit strategies (15-20 range)
    'max_spread_pct': 5.0,             # Reject if bid-ask spread > 5%
    'preferred_spread_pct': 2.0,       # Prefer <= 2% spread
    'min_open_interest': 100,          # Minimum OI (prefer > 1,000)
    'preferred_open_interest': 1000,   # Preferred OI for full position
    'min_volume': 50,                  # Minimum daily volume
    'min_underlying_volume': 500000,   # Minimum underlying shares traded

    # Position Sizing
    'defined_risk_pct': 0.03,          # 3% of account per defined-risk trade
    'undefined_risk_pct': 0.02,        # 2% of account per undefined-risk trade
    'max_buying_power_usage': 0.60,    # 60% max BP usage
    'cash_reserve': 0.40,              # 40% cash reserve for adjustments
    'kelly_fraction': 0.50,            # Half-Kelly for conservative sizing

    # Exit Management (NO STOP LOSSES per TastyTrade research)
    'profit_target_pct': 0.50,         # Close at 50% of max profit
    'roll_dte_threshold': 21,          # Roll or close at 21 DTE
    'delta_adjustment_threshold': 0.35, # Adjust if position delta > 0.35
    'loss_review_threshold': 0.50,     # Review at 50% of max loss

    # Portfolio Limits (per $100K)
    'max_single_underlying': 0.10,     # 10% per ticker
    'max_sector_exposure': 0.20,       # 20% per sector
    'max_correlated_exposure': 0.40,   # 40% for correlated positions (r>0.7)
    'max_single_expiration': 0.35,     # 35% per expiration cycle
    'beta_weighted_delta_limit': 200,  # Per $100K

    # Risk Metrics
    'var_confidence': 0.95,            # 95% VaR confidence
    'stress_test_move': 0.20,          # 20% move + 50% IV spike
    'min_pop_for_entry': 0.65,         # 65% minimum probability of profit

    # Earnings Filter
    'min_days_to_earnings': 30,        # SKIP options if earnings < 30 days
}

# Liquidity Tier 1 - Penny-wide spreads, 10,000+ OI per strike (FULL SIZE)
TIER_1_UNDERLYINGS = frozenset([
    'SPY', 'QQQ', 'IWM',               # ETFs
    'AAPL', 'MSFT', 'NVDA', 'TSLA',    # Mega-cap tech
    'AMZN', 'GOOGL', 'GOOG', 'META',   # FAANG
    'AMD', 'NFLX', 'DIS', 'BA',        # High-volume stocks
    'JPM', 'BAC', 'WFC', 'GS',         # Financials
    'XOM', 'CVX',                       # Energy
])

# IV-Based Strategy Selection Matrix (from institutional document)
IV_STRATEGY_MATRIX = {
    'HIGH_IV_70_100': {
        'neutral': ['Straddle (Short)', 'Strangle (Short)', 'Iron Butterfly'],
        'long': ['Bull Put Spread (Credit)', 'Jade Lizard', 'Short Put'],
        'short': ['Bear Call Spread (Credit)', 'Short Call Spread', 'Covered Put'],
        'rationale': 'Aggressive premium selling - IV at extremes will crush'
    },
    'HIGH_IV_50_70': {
        'neutral': ['Iron Condor', 'Iron Butterfly', 'Credit Spread'],
        'long': ['Bull Put Spread (Credit)', 'Cash-Secured Put'],
        'short': ['Bear Call Spread (Credit)', 'Covered Call'],
        'rationale': 'Defined-risk selling - capture elevated premium with protection'
    },
    'NORMAL_IV_30_50': {
        'neutral': ['Iron Condor (Conservative)', 'Calendar Spread'],
        'long': ['Bull Call Spread (Debit)', 'Diagonal Spread'],
        'short': ['Bear Put Spread (Debit)', 'Put Calendar'],
        'rationale': 'Cautious - only conservative credit spreads or calendars'
    },
    'LOW_IV_0_30': {
        'neutral': ['Calendar Spread', 'Long Straddle', 'Long Strangle'],
        'long': ['Long Call', 'Bull Call Spread (Debit)', 'LEAPS'],
        'short': ['Long Put', 'Bear Put Spread (Debit)', 'Put Backspread'],
        'rationale': 'Premium buying - options are cheap, expect IV expansion'
    }
}

# Theta Decay Table (% of option value lost per day)
THETA_DECAY_TABLE = {
    (60, 45): 0.005,    # 60-45 DTE: ~0.5%/day - Optimal entry zone
    (45, 30): 0.010,    # 45-30 DTE: ~1%/day - Primary theta capture
    (30, 21): 0.015,    # 30-21 DTE: ~1.5%/day - Decision point (roll or close)
    (21, 7):  0.035,    # 21-7 DTE: ~3-4%/day - High gamma risk, exit zone
    (7, 0):   0.075,    # 7-0 DTE: ~5-10%/day - Binary zone, avoid
}

# Essential columns that should never be removed even if all zeros
ESSENTIAL_OPTIONS_COLUMNS = {'openInterest', 'bid', 'ask', 'volume', 'change', 'percentChange'}

# Google Trends timeframe mapping
TREND_TIMEFRAMES = {
    1: 'now 1-d', 7: 'now 7-d', 30: 'today 1-m',
    90: 'today 3-m', 365: 'today 12-m'
}

# Timeout configuration
DEFAULT_FUTURE_TIMEOUT = 30.0  # seconds

# Sector PE median lookup table (FIX BUG-11: replaces hardcoded 20)
SECTOR_PE_MEDIANS = {
    'Technology': 35,
    'Communication Services': 25,
    'Consumer Cyclical': 22,
    'Consumer Defensive': 23,
    'Healthcare': 28,
    'Financial Services': 14,
    'Industrials': 22,
    'Energy': 12,
    'Utilities': 18,
    'Real Estate': 35,
    'Basic Materials': 16,
}
SECTOR_PE_DEFAULT = 20  # Fallback if sector unknown
