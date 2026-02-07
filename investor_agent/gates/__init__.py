"""
Gate validation system for investor-agent.

5-Gate Validation Framework:
1. Catalyst Gate - Earnings, insider activity, news catalysts
2. Freshness + Dalio Gate - CVD, exhaustion, dollar flow
3. Brooks Gate - Price action, Always-In direction
4. Quality Gate - F-Score, Z-Score, fundamentals
5. Options Tradability Gate - Liquidity, IV environment, strategy selection
"""

from .options_tradability_gate import (
    validate_options_tradability,
    calculate_expected_moves,
    classify_iv_environment,
    check_liquidity_requirements,
    integrate_iv_skew,
    integrate_term_structure
)

__all__ = [
    'validate_options_tradability',
    'calculate_expected_moves',
    'classify_iv_environment',
    'check_liquidity_requirements',
    'integrate_iv_skew',
    'integrate_term_structure'
]
