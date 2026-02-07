"""
Options trading modules for investor-agent.

Modules:
- decision_framework: Options vs stock decision logic
- strategy_selector: Strategy selection based on IV environment
- expected_moves: Expected move calculations for strike selection
"""

from .decision_framework import (
    should_use_options,
    build_options_plan,
    build_stock_plan
)

__all__ = [
    'should_use_options',
    'build_options_plan',
    'build_stock_plan'
]
