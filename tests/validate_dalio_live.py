#!/usr/bin/env python3
"""
DALIO ECONOMIC MACHINE - LIVE TOOL VALIDATION

This script takes the ACTUAL tool output from investor-agent MCP 
and validates it against manually calculated values.

This is designed to be run from Claude with tool access, where you:
1. Call analyze_volume_tool(ticker) 
2. Call get_questrade_candles(symbol, interval="OneDay", window=60)
3. Pass the outputs to this validator

Usage (from Python):
    from tests.validate_dalio_live import validate_tool_output
    
    # Get tool outputs (from MCP)
    volume_result = analyze_volume_tool("AAPL")
    candles = get_questrade_candles("AAPL", "OneDay", window=60)
    
    # Validate
    report = validate_tool_output(volume_result, candles)
    print(report)

Reference: DALIO_IMPLEMENTATION_PLAN.md
"""

import json
from datetime import datetime
from typing import Dict, Any, List
import numpy as np
import pandas as pd


# =============================================================================
# TOLERANCE THRESHOLDS
# =============================================================================

TOLERANCE = {
    "dalio_ratio": 0.01,      # 1% tolerance
    "dollar_volume": 0.05,     # 5% tolerance (large numbers)
    "cdf": 0.10,               # 10% tolerance (can vary)
    "spending_efficiency": 0.2, # 20% tolerance (very volatile)
    "vwap": 0.005,             # 0.5% tolerance for VWAP
    "sustainability_score": 10,  # 10 points tolerance
}


# =============================================================================
# MANUAL CALCULATION FROM CANDLES
# =============================================================================

def calculate_dalio_from_candles(candles: List[Dict]) -> Dict[str, Any]:
    """
    Calculate Dalio metrics from Questrade candles data.
    
    Args:
        candles: List of candle dictionaries with keys:
                 start, end, open, high, low, close, volume, VWAP
    
    Returns:
        Manually calculated Dalio metrics
    """
    # Convert to DataFrame
    df = pd.DataFrame(candles)
    
    # Standardize column names
    df = df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume',
        'VWAP': 'VWAP'
    })
    
    if len(df) < 21:
        return {"error": f"Insufficient data: {len(df)} candles, need 21+"}
    
    # Sort by date (ensure chronological order)
    if 'start' in df.columns:
        df['Date'] = pd.to_datetime(df['start'])
        df = df.sort_values('Date')
    
    # Calculate metrics
    df['typical_price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['dollar_volume'] = df['typical_price'] * df['Volume']
    df['session_vwap'] = df['dollar_volume'] / df['Volume']
    df['session_vwap'] = df['session_vwap'].replace([np.inf, -np.inf], np.nan).fillna(df['Close'])
    
    # Use Questrade VWAP if available (more accurate)
    if 'VWAP' in df.columns and df['VWAP'].notna().any():
        df['session_vwap'] = df['VWAP']
    
    # Dollar Volume calculations
    dv_today = df['dollar_volume'].iloc[-1]
    dv_5d_avg = df['dollar_volume'].iloc[-5:].mean()
    dv_20d_avg = df['dollar_volume'].iloc[-20:].mean()
    relative_to_20d = dv_today / dv_20d_avg if dv_20d_avg > 0 else 0
    
    # Dalio Ratio: Current VWAP / Prior 20d Average VWAP
    current_vwap = df['session_vwap'].iloc[-1]
    prior_20d_vwap = df['session_vwap'].iloc[-21:-1].mean()
    dalio_ratio = current_vwap / prior_20d_vwap if prior_20d_vwap > 0 else 1.0
    
    # DV Momentum
    dv_momentum_pct = (dv_today - dv_20d_avg) / dv_20d_avg * 100 if dv_20d_avg > 0 else 0
    
    # Spending Efficiency
    price_change_pct = (df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100
    dv_change_pct = (dv_today - df['dollar_volume'].iloc[-2]) / df['dollar_volume'].iloc[-2] * 100
    spending_efficiency = price_change_pct / dv_change_pct if abs(dv_change_pct) > 0.001 else 0
    
    # Cumulative Dollar Flow
    df['dv_direction'] = np.where(df['Close'] >= df['Open'], 1, -1)
    df['directional_dv'] = df['dollar_volume'] * df['dv_direction']
    cdf_5d = df['directional_dv'].iloc[-5:].sum()
    cdf_20d = df['directional_dv'].iloc[-20:].sum()
    cdf_direction = "ACCUMULATION" if cdf_20d > 0 else "DISTRIBUTION"
    
    return {
        "data_source": "questrade_candles",
        "data_points": len(df),
        "current_price": df['Close'].iloc[-1],
        "current_vwap": current_vwap,
        "prior_20d_vwap": prior_20d_vwap,
        "dalio_ratio": {
            "value": dalio_ratio,
            "formula": f"{current_vwap:.4f} / {prior_20d_vwap:.4f}"
        },
        "dollar_volume": {
            "today": dv_today,
            "20d_avg": dv_20d_avg,
            "relative_to_20d": relative_to_20d,
            "momentum_pct": dv_momentum_pct
        },
        "spending_efficiency": {
            "ratio": spending_efficiency,
            "price_change_pct": price_change_pct,
            "dv_change_pct": dv_change_pct
        },
        "cumulative_dollar_flow": {
            "5d": cdf_5d,
            "20d": cdf_20d,
            "direction": cdf_direction
        }
    }


# =============================================================================
# VALIDATION AGAINST TOOL OUTPUT
# =============================================================================

def compare_value(name: str, expected: float, actual: float, 
                  tolerance: float, format_str: str = ".4f") -> Dict:
    """Compare a single value with tolerance."""
    if expected == 0 and actual == 0:
        return {"name": name, "passed": True, "diff": 0, "msg": "Both zero"}
    
    if expected == 0:
        diff = abs(actual)
        relative = float('inf')
    else:
        diff = abs(expected - actual)
        relative = diff / abs(expected)
    
    passed = relative <= tolerance
    
    return {
        "name": name,
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "diff": diff,
        "relative": relative,
        "tolerance": tolerance,
        "msg": f"Expected: {expected:{format_str}}, Actual: {actual:{format_str}}, Diff: {relative*100:.2f}%"
    }


def validate_tool_output(volume_result: Dict, candles: List[Dict]) -> str:
    """
    Validate analyze_volume_tool output against manual calculations.
    
    Args:
        volume_result: Output from analyze_volume_tool(ticker)
        candles: Output from get_questrade_candles(symbol, interval, window)
    
    Returns:
        Formatted validation report string
    """
    # Calculate expected values
    expected = calculate_dalio_from_candles(candles)
    
    if "error" in expected:
        return f"ERROR: {expected['error']}"
    
    # Extract actual values from tool output
    actual_dalio = volume_result.get("dalio_metrics", {})
    
    # Run comparisons
    comparisons = []
    
    # 1. Dalio Ratio
    exp_ratio = expected["dalio_ratio"]["value"]
    act_ratio = actual_dalio.get("dalio_ratio", {}).get("20d_avg", 
                actual_dalio.get("dalio_ratio", {}).get("current", 0))
    comparisons.append(compare_value(
        "Dalio Ratio (20d)",
        exp_ratio, act_ratio, TOLERANCE["dalio_ratio"]
    ))
    
    # 2. Dollar Volume Today
    exp_dv = expected["dollar_volume"]["today"]
    act_dv = actual_dalio.get("dollar_volume", {}).get("today", 0)
    comparisons.append(compare_value(
        "Dollar Volume (Today)",
        exp_dv, act_dv, TOLERANCE["dollar_volume"], ".0f"
    ))
    
    # 3. Dollar Volume 20d Avg
    exp_dv20 = expected["dollar_volume"]["20d_avg"]
    act_dv20 = actual_dalio.get("dollar_volume", {}).get("20d_avg", 0)
    comparisons.append(compare_value(
        "Dollar Volume (20d Avg)",
        exp_dv20, act_dv20, TOLERANCE["dollar_volume"], ".0f"
    ))
    
    # 4. Relative DV
    exp_rel = expected["dollar_volume"]["relative_to_20d"]
    act_rel = actual_dalio.get("dollar_volume", {}).get("relative_to_20d", 0)
    comparisons.append(compare_value(
        "Relative DV (vs 20d)",
        exp_rel, act_rel, 0.05
    ))
    
    # 5. CDF 20d
    exp_cdf = expected["cumulative_dollar_flow"]["20d"]
    act_cdf = actual_dalio.get("cumulative_dollar_flow", {}).get("20d", 0)
    comparisons.append(compare_value(
        "CDF (20d)",
        exp_cdf, act_cdf, TOLERANCE["cdf"], ".0f"
    ))
    
    # 6. CDF Direction
    exp_dir = expected["cumulative_dollar_flow"]["direction"]
    act_dir = actual_dalio.get("cumulative_dollar_flow", {}).get("direction", "UNKNOWN")
    comparisons.append({
        "name": "CDF Direction",
        "passed": exp_dir == act_dir,
        "expected": exp_dir,
        "actual": act_dir,
        "msg": f"Expected: {exp_dir}, Actual: {act_dir}"
    })
    
    # 7. Spending Efficiency
    exp_se = expected["spending_efficiency"]["ratio"]
    act_se = actual_dalio.get("spending_efficiency", {}).get("ratio", 0)
    comparisons.append(compare_value(
        "Spending Efficiency",
        exp_se, act_se, TOLERANCE["spending_efficiency"]
    ))
    
    # Generate report
    lines = []
    lines.append("=" * 70)
    lines.append("DALIO ECONOMIC MACHINE - LIVE VALIDATION REPORT")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    
    # Data info
    lines.append(f"\n📊 SOURCE DATA:")
    lines.append(f"   Data Points: {expected['data_points']} candles")
    lines.append(f"   Current Price: ${expected['current_price']:.2f}")
    lines.append(f"   Current VWAP: ${expected['current_vwap']:.4f}")
    lines.append(f"   Prior 20d VWAP: ${expected['prior_20d_vwap']:.4f}")
    lines.append(f"   Dalio Ratio Formula: {expected['dalio_ratio']['formula']}")
    
    # Results
    passed = sum(1 for c in comparisons if c["passed"])
    total = len(comparisons)
    
    lines.append(f"\n📈 VALIDATION RESULTS: {passed}/{total} passed")
    lines.append("-" * 70)
    
    for c in comparisons:
        status = "✅" if c["passed"] else "❌"
        lines.append(f"{status} {c['name']}")
        lines.append(f"   {c['msg']}")
    
    # Summary
    lines.append("\n" + "=" * 70)
    if passed == total:
        lines.append("✅ ALL VALIDATIONS PASSED - Tool calculations are correct!")
    else:
        lines.append(f"⚠️  {total - passed} VALIDATION(S) FAILED - Review calculations")
        lines.append("\n📝 DEBUGGING HINTS:")
        for c in comparisons:
            if not c["passed"]:
                lines.append(f"\n   {c['name']}:")
                if "Dalio Ratio" in c["name"]:
                    lines.append(f"   - Check: current_vwap / prior_20d_vwap_mean")
                    lines.append(f"   - Expected: {expected['dalio_ratio']['formula']} = {exp_ratio:.4f}")
                elif "CDF" in c["name"] and "Direction" not in c["name"]:
                    lines.append(f"   - Check: Sum of (dollar_volume * sign(close - open)) for last 20 days")
                elif "Dollar Volume" in c["name"]:
                    lines.append(f"   - Check: typical_price * volume")
                    lines.append(f"   - typical_price = (high + low + close) / 3")
    
    lines.append("=" * 70)
    
    return "\n".join(lines)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

def example_validation():
    """
    Example showing how to use this validator with sample data.
    In real usage, you'd pass actual tool outputs.
    """
    # Sample candles data (would come from get_questrade_candles)
    sample_candles = [
        {"start": "2024-01-01", "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000000, "VWAP": 102.5},
        {"start": "2024-01-02", "open": 103, "high": 106, "low": 102, "close": 105, "volume": 1200000, "VWAP": 104.2},
        # ... would need 60+ days of data
    ]
    
    # Sample tool output (would come from analyze_volume_tool)
    sample_tool_output = {
        "dalio_metrics": {
            "dalio_ratio": {"20d_avg": 1.02, "interpretation": "NEUTRAL"},
            "dollar_volume": {"today": 10000000, "20d_avg": 9500000, "relative_to_20d": 1.05},
            "cumulative_dollar_flow": {"20d": 50000000, "direction": "ACCUMULATION"},
            "spending_efficiency": {"ratio": 0.8}
        }
    }
    
    print("To run validation, call from MCP context:")
    print("  1. Get volume_result = analyze_volume_tool(ticker)")
    print("  2. Get candles = get_questrade_candles(symbol, 'OneDay', window=60)")
    print("  3. Call validate_tool_output(volume_result, candles['candles'])")


if __name__ == "__main__":
    example_validation()
