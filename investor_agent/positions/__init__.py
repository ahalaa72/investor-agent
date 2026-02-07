"""
Options Position Management Module

Handles lifecycle management for options positions:
- 50% profit target detection
- 21 DTE management (roll or close)
- Position health monitoring
- Exit signal detection

Based on TastyTrade research and McMillan methodology.
"""

from .manager import (
    evaluate_options_position,
    evaluate_portfolio_positions,
    get_position_greeks_summary
)

__all__ = [
    'evaluate_options_position',
    'evaluate_portfolio_positions',
    'get_position_greeks_summary'
]
