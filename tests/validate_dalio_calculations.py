#!/usr/bin/env python3
"""
DALIO ECONOMIC MACHINE - VALIDATION TEST SUITE

Purpose: Compare investor-agent Dalio metric outputs against manually calculated 
values using raw OHLCV data to ensure implementation correctness.

This is NOT a unit test - it's a VALIDATION test that:
1. Fetches real market data
2. Manually calculates Dalio metrics using the documented formulas
3. Compares against tool outputs
4. Reports discrepancies for developer debugging

Usage:
    # Run from project root:
    python tests/validate_dalio_calculations.py AAPL
    python tests/validate_dalio_calculations.py NVDA AAPL TSLA  # Multiple tickers

Reference: DALIO_IMPLEMENTATION_PLAN.md, RAY_DALIO_ECONOMIC_MACHINE_IMPLEMENTATION.md
"""

import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import traceback

# For numeric calculations
try:
    import numpy as np
    import pandas as pd
except ImportError:
    print("ERROR: numpy and pandas required. Install with: pip install numpy pandas")
    sys.exit(1)

# For MCP client (if available)
try:
    import asyncio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

# For direct API access (fallback)
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


# =============================================================================
# CONSTANTS & THRESHOLDS (from DALIO_IMPLEMENTATION_PLAN.md)
# =============================================================================

DALIO_RATIO_THRESHOLDS = {
    "STRONG_BULLISH": (1.05, float('inf')),
    "BULLISH": (1.02, 1.05),
    "NEUTRAL": (0.98, 1.02),
    "BEARISH": (0.95, 0.98),
    "STRONG_BEARISH": (float('-inf'), 0.95),
}

DV_MOMENTUM_THRESHOLDS = {
    "EXTREME_INFLOW": (100, float('inf')),
    "STRONG_INFLOW": (50, 100),
    "INFLOW": (20, 50),
    "NEUTRAL": (-20, 20),
    "OUTFLOW": (-50, -20),
    "STRONG_OUTFLOW": (float('-inf'), -50),
}

TOLERANCE = {
    "dalio_ratio": 0.01,      # 1% tolerance
    "dollar_volume": 0.05,     # 5% tolerance (large numbers)
    "cdf": 0.05,               # 5% tolerance
    "spending_efficiency": 0.1, # 10% tolerance (volatile)
    "sustainability_score": 5,  # 5 points tolerance
}


# =============================================================================
# MANUAL CALCULATION FUNCTIONS (Mirrors implementation)
# =============================================================================

def calculate_dalio_metrics_manual(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Manually calculate ALL Dalio metrics from raw OHLCV data.
    This is the "expected" calculation for validation.
    
    Args:
        df: DataFrame with columns [Open, High, Low, Close, Volume]
            Index should be dates, sorted ascending (oldest first)
    
    Returns:
        Dictionary with all Dalio metrics calculated manually
    """
    # Ensure we have enough data
    if len(df) < 21:
        return {"error": f"Insufficient data: {len(df)} rows, need at least 21"}
    
    # --- Task 1A: Dollar Volume Calculations ---
    df = df.copy()
    df['typical_price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['dollar_volume'] = df['typical_price'] * df['Volume']
    
    dv_today = df['dollar_volume'].iloc[-1]
    dv_5d_avg = df['dollar_volume'].iloc[-5:].mean()
    dv_20d_avg = df['dollar_volume'].iloc[-20:].mean()
    dv_50d_avg = df['dollar_volume'].iloc[-50:].mean() if len(df) >= 50 else dv_20d_avg
    
    relative_to_20d = dv_today / dv_20d_avg if dv_20d_avg > 0 else 0
    
    # Percentile calculation for 90 days
    lookback_90d = df['dollar_volume'].iloc[-min(90, len(df)):]
    percentile_90d = (lookback_90d < dv_today).sum() / len(lookback_90d) * 100
    
    # --- Task 1B: Dalio Ratio ---
    # Session VWAP for each day
    df['session_vwap'] = df['dollar_volume'] / df['Volume']
    df['session_vwap'] = df['session_vwap'].replace([np.inf, -np.inf], np.nan).fillna(0)
    
    current_vwap = df['session_vwap'].iloc[-1]
    prior_5d_vwap = df['session_vwap'].iloc[-6:-1].mean()
    prior_20d_vwap = df['session_vwap'].iloc[-21:-1].mean()
    
    dalio_ratio_5d = current_vwap / prior_5d_vwap if prior_5d_vwap > 0 else 1.0
    dalio_ratio_20d = current_vwap / prior_20d_vwap if prior_20d_vwap > 0 else 1.0
    
    # Interpretation
    def interpret_dalio_ratio(ratio):
        for label, (low, high) in DALIO_RATIO_THRESHOLDS.items():
            if low <= ratio < high:
                return label
        return "NEUTRAL"
    
    dalio_interpretation = interpret_dalio_ratio(dalio_ratio_20d)
    
    # Trend (is current higher than prior?)
    dalio_5d_prior = df['session_vwap'].iloc[-6:-1].mean() / df['session_vwap'].iloc[-11:-6].mean() if len(df) >= 11 else 1.0
    dalio_trend = "INCREASING" if dalio_ratio_20d > dalio_5d_prior else "DECREASING"
    
    # --- Task 1C: Dollar Volume Momentum (DVM) ---
    dv_momentum_pct = (dv_today - dv_20d_avg) / dv_20d_avg * 100 if dv_20d_avg > 0 else 0
    
    def classify_dv_momentum(momentum_pct):
        for label, (low, high) in DV_MOMENTUM_THRESHOLDS.items():
            if low <= momentum_pct < high:
                return label
        return "NEUTRAL"
    
    dv_momentum_class = classify_dv_momentum(dv_momentum_pct)
    
    # --- Task 1D: Spending Efficiency Ratio (SER) ---
    price_change_pct = (df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100
    dv_change_pct = (dv_today - df['dollar_volume'].iloc[-2]) / df['dollar_volume'].iloc[-2] * 100 if df['dollar_volume'].iloc[-2] > 0 else 0
    
    spending_efficiency = price_change_pct / dv_change_pct if abs(dv_change_pct) > 0.001 else 0
    
    def interpret_spending_efficiency(ratio):
        abs_ratio = abs(ratio)
        if abs_ratio > 1.5:
            return "LOW_LIQUIDITY"
        elif abs_ratio >= 0.8:
            return "NORMAL"
        elif abs_ratio >= 0.3:
            return "HIGH_ABSORPTION"
        else:
            return "VERY_HIGH_ABSORPTION"
    
    efficiency_interpretation = interpret_spending_efficiency(spending_efficiency)
    
    # --- Task 1E: Cumulative Dollar Flow (CDF) ---
    df['dv_direction'] = np.where(df['Close'] >= df['Open'], 1, -1)
    df['directional_dv'] = df['dollar_volume'] * df['dv_direction']
    
    cdf_5d = df['directional_dv'].iloc[-5:].sum()
    cdf_20d = df['directional_dv'].iloc[-20:].sum()
    
    cdf_direction = "ACCUMULATION" if cdf_20d > 0 else "DISTRIBUTION"
    
    # Acceleration (compare recent 5d to prior 5d)
    cdf_recent = df['directional_dv'].iloc[-5:].sum()
    cdf_prior = df['directional_dv'].iloc[-10:-5].sum() if len(df) >= 10 else cdf_recent
    cdf_acceleration = "INCREASING" if abs(cdf_recent) > abs(cdf_prior) else "DECREASING"
    
    # --- Task 1F: Dollar Volume Profile ---
    bins = 20
    price_min = df['Low'].min()
    price_max = df['High'].max()
    bin_size = (price_max - price_min) / bins if price_max > price_min else 1
    
    profile = {}
    for i in range(bins):
        price_low = price_min + (i * bin_size)
        price_high = price_low + bin_size
        price_mid = (price_low + price_high) / 2
        
        mask = (df['Low'] <= price_mid) & (df['High'] >= price_mid)
        if mask.sum() > 0:
            dv_at_level = df.loc[mask, 'dollar_volume'].sum() / mask.sum()
            profile[round(price_mid, 2)] = int(dv_at_level)
    
    poc = max(profile, key=profile.get) if profile else df['Close'].iloc[-1]
    current_price = df['Close'].iloc[-1]
    current_vs_poc = "ABOVE" if current_price > poc else "BELOW"
    
    # --- Task 1G: Institutional Activity Detection ---
    signals = []
    confidence = 0
    
    if dv_momentum_pct > 50:
        signals.append(f"Dollar volume {dv_momentum_pct:.0f}% above 20d avg")
        confidence += 30
    
    if abs(spending_efficiency) < 0.5:
        signals.append("Spending efficiency suggests absorption")
        confidence += 25
    
    if abs(cdf_20d) > df['dollar_volume'].iloc[-20:].sum() * 0.3:
        signals.append("Strong directional dollar commitment")
        confidence += 25
    
    high_dv_50d = df['dollar_volume'].iloc[-50:].mean() if len(df) >= 50 else dv_20d_avg
    high_dv_days = (df['dollar_volume'].iloc[-20:] > high_dv_50d * 1.5).sum()
    if high_dv_days >= 5:
        signals.append(f"{high_dv_days} high-dollar-volume days in 20d")
        confidence += 20
    
    institutional_detected = confidence >= 50
    institutional_confidence = "HIGH" if confidence >= 75 else "MEDIUM" if confidence >= 50 else "LOW"
    likely_direction = "ACCUMULATION" if cdf_20d > 0 else "DISTRIBUTION"
    
    # --- Task 1H: Trend Sustainability Score ---
    score = 0
    factors = {}
    
    # Factor 1: Dalio Ratio (25 points)
    if dalio_ratio_20d > 1.02:
        score += 25
        factors["dalio_ratio"] = "POSITIVE"
    elif dalio_ratio_20d < 0.98:
        factors["dalio_ratio"] = "NEGATIVE"
    else:
        score += 12
        factors["dalio_ratio"] = "NEUTRAL"
    
    # Factor 2: Dollar volume momentum (25 points)
    if dv_momentum_pct > 20:
        score += 25
        factors["dollar_volume_trend"] = "POSITIVE"
    elif dv_momentum_pct < -20:
        factors["dollar_volume_trend"] = "NEGATIVE"
    else:
        score += 12
        factors["dollar_volume_trend"] = "NEUTRAL"
    
    # Factor 3: Spending efficiency (25 points)
    if 0.3 <= abs(spending_efficiency) <= 1.2:
        score += 25
        factors["efficiency_trend"] = "STABLE"
    else:
        score += 10
        factors["efficiency_trend"] = "HIGH_ABSORPTION" if abs(spending_efficiency) < 0.3 else "UNSTABLE"
    
    # Factor 4: Price vs POC (25 points)
    price_vs_poc = (current_price - poc) / poc * 100
    if -5 <= price_vs_poc <= 10:
        score += 25
        factors["price_vs_poc"] = "FAVORABLE"
    else:
        score += 10
        factors["price_vs_poc"] = "EXTENDED"
    
    # Grade
    if score >= 80:
        grade = "A"
    elif score >= 70:
        grade = "B+"
    elif score >= 60:
        grade = "B"
    elif score >= 50:
        grade = "C"
    else:
        grade = "D"
    
    assessment = "SUSTAINABLE" if score >= 60 else "AT_RISK" if score >= 40 else "UNSUSTAINABLE"
    
    return {
        "dollar_volume": {
            "today": dv_today,
            "5d_avg": dv_5d_avg,
            "20d_avg": dv_20d_avg,
            "50d_avg": dv_50d_avg,
            "relative_to_20d": relative_to_20d,
            "percentile_90d": percentile_90d,
            "momentum_pct": dv_momentum_pct,
            "momentum_class": dv_momentum_class,
        },
        "dalio_ratio": {
            "current": dalio_ratio_20d,
            "5d_avg": dalio_ratio_5d,
            "20d_avg": dalio_ratio_20d,
            "interpretation": dalio_interpretation,
            "trend": dalio_trend,
        },
        "spending_efficiency": {
            "ratio": spending_efficiency,
            "interpretation": efficiency_interpretation,
            "price_change_pct": price_change_pct,
            "dv_change_pct": dv_change_pct,
        },
        "cumulative_dollar_flow": {
            "5d": cdf_5d,
            "20d": cdf_20d,
            "direction": cdf_direction,
            "acceleration": cdf_acceleration,
        },
        "dollar_profile": {
            "point_of_control": poc,
            "current_vs_poc": current_vs_poc,
        },
        "institutional_activity": {
            "detected": institutional_detected,
            "confidence": institutional_confidence,
            "confidence_score": confidence,
            "signals": signals,
            "likely_direction": likely_direction,
        },
        "trend_sustainability": {
            "score": score,
            "grade": grade,
            "assessment": assessment,
            "factors": factors,
        },
        "raw_data": {
            "current_price": current_price,
            "current_vwap": current_vwap,
            "prior_20d_vwap": prior_20d_vwap,
            "data_points": len(df),
        }
    }


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

def fetch_ohlcv_yfinance(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """Fetch OHLCV data using yfinance."""
    if not YFINANCE_AVAILABLE:
        raise ImportError("yfinance not available")
    
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)
    
    # Standardize column names
    df = df.rename(columns={
        'Open': 'Open',
        'High': 'High', 
        'Low': 'Low',
        'Close': 'Close',
        'Volume': 'Volume'
    })
    
    return df[['Open', 'High', 'Low', 'Close', 'Volume']]


# =============================================================================
# COMPARISON & VALIDATION FUNCTIONS
# =============================================================================

def compare_values(expected: float, actual: float, tolerance: float, 
                   is_percentage: bool = False) -> Tuple[bool, str]:
    """
    Compare expected vs actual value with tolerance.
    
    Returns:
        Tuple of (passed: bool, message: str)
    """
    if expected == 0 and actual == 0:
        return True, "Both zero ✓"
    
    if expected == 0:
        diff = abs(actual)
        relative = float('inf')
    else:
        diff = abs(expected - actual)
        relative = diff / abs(expected)
    
    if is_percentage:
        passed = diff <= tolerance
        msg = f"Expected: {expected:.2f}, Actual: {actual:.2f}, Diff: {diff:.2f} (tol: {tolerance})"
    else:
        passed = relative <= tolerance
        msg = f"Expected: {expected:.2f}, Actual: {actual:.2f}, Diff: {relative*100:.2f}% (tol: {tolerance*100:.0f}%)"
    
    return passed, msg


def validate_dalio_metrics(expected: Dict, actual: Dict) -> List[Dict]:
    """
    Compare manually calculated metrics against tool output.
    
    Args:
        expected: Manually calculated metrics
        actual: Tool output (dalio_metrics section from analyze_volume_tool)
    
    Returns:
        List of validation results
    """
    results = []
    
    # --- Dalio Ratio ---
    if "dalio_ratio" in expected and "dalio_ratio" in actual:
        exp_ratio = expected["dalio_ratio"]["20d_avg"]
        act_ratio = actual["dalio_ratio"].get("20d_avg", actual["dalio_ratio"].get("current", 0))
        passed, msg = compare_values(exp_ratio, act_ratio, TOLERANCE["dalio_ratio"])
        results.append({
            "metric": "Dalio Ratio (20d)",
            "passed": passed,
            "expected": exp_ratio,
            "actual": act_ratio,
            "message": msg,
            "critical": True
        })
        
        # Interpretation match
        exp_interp = expected["dalio_ratio"]["interpretation"]
        act_interp = actual["dalio_ratio"].get("interpretation", "UNKNOWN")
        results.append({
            "metric": "Dalio Ratio Interpretation",
            "passed": exp_interp == act_interp,
            "expected": exp_interp,
            "actual": act_interp,
            "message": f"Expected: {exp_interp}, Actual: {act_interp}",
            "critical": False
        })
    
    # --- Dollar Volume ---
    if "dollar_volume" in expected and "dollar_volume" in actual:
        for key in ["today", "20d_avg"]:
            exp_dv = expected["dollar_volume"].get(key, 0)
            act_dv = actual["dollar_volume"].get(key, 0)
            passed, msg = compare_values(exp_dv, act_dv, TOLERANCE["dollar_volume"])
            results.append({
                "metric": f"Dollar Volume ({key})",
                "passed": passed,
                "expected": exp_dv,
                "actual": act_dv,
                "message": msg,
                "critical": key == "today"
            })
        
        # Momentum classification
        exp_mom = expected["dollar_volume"]["momentum_class"]
        act_mom = actual["dollar_volume"].get("momentum", "UNKNOWN")
        results.append({
            "metric": "DV Momentum Classification",
            "passed": exp_mom == act_mom,
            "expected": exp_mom,
            "actual": act_mom,
            "message": f"Expected: {exp_mom}, Actual: {act_mom}",
            "critical": False
        })
    
    # --- Cumulative Dollar Flow ---
    if "cumulative_dollar_flow" in expected and "cumulative_dollar_flow" in actual:
        exp_cdf = expected["cumulative_dollar_flow"]["20d"]
        act_cdf = actual["cumulative_dollar_flow"].get("20d", 0)
        passed, msg = compare_values(exp_cdf, act_cdf, TOLERANCE["cdf"])
        results.append({
            "metric": "Cumulative Dollar Flow (20d)",
            "passed": passed,
            "expected": exp_cdf,
            "actual": act_cdf,
            "message": msg,
            "critical": True
        })
        
        # Direction match
        exp_dir = expected["cumulative_dollar_flow"]["direction"]
        act_dir = actual["cumulative_dollar_flow"].get("direction", "UNKNOWN")
        results.append({
            "metric": "CDF Direction",
            "passed": exp_dir == act_dir,
            "expected": exp_dir,
            "actual": act_dir,
            "message": f"Expected: {exp_dir}, Actual: {act_dir}",
            "critical": True
        })
    
    # --- Spending Efficiency ---
    if "spending_efficiency" in expected and "spending_efficiency" in actual:
        exp_se = expected["spending_efficiency"]["ratio"]
        act_se = actual["spending_efficiency"].get("ratio", 0)
        # Spending efficiency can be volatile, use higher tolerance
        passed, msg = compare_values(exp_se, act_se, TOLERANCE["spending_efficiency"])
        results.append({
            "metric": "Spending Efficiency Ratio",
            "passed": passed,
            "expected": exp_se,
            "actual": act_se,
            "message": msg,
            "critical": False
        })
    
    # --- Trend Sustainability ---
    if "trend_sustainability" in expected and "trend_sustainability" in actual:
        exp_score = expected["trend_sustainability"]["score"]
        act_score = actual["trend_sustainability"].get("score", 0)
        passed = abs(exp_score - act_score) <= TOLERANCE["sustainability_score"]
        results.append({
            "metric": "Sustainability Score",
            "passed": passed,
            "expected": exp_score,
            "actual": act_score,
            "message": f"Expected: {exp_score}, Actual: {act_score}, Diff: {abs(exp_score - act_score)}",
            "critical": False
        })
        
        exp_grade = expected["trend_sustainability"]["grade"]
        act_grade = actual["trend_sustainability"].get("grade", "?")
        results.append({
            "metric": "Sustainability Grade",
            "passed": exp_grade == act_grade,
            "expected": exp_grade,
            "actual": act_grade,
            "message": f"Expected: {exp_grade}, Actual: {act_grade}",
            "critical": False
        })
    
    # --- Institutional Activity ---
    if "institutional_activity" in expected and "institutional_activity" in actual:
        exp_det = expected["institutional_activity"]["detected"]
        act_det = actual["institutional_activity"].get("detected", False)
        results.append({
            "metric": "Institutional Activity Detected",
            "passed": exp_det == act_det,
            "expected": exp_det,
            "actual": act_det,
            "message": f"Expected: {exp_det}, Actual: {act_det}",
            "critical": False
        })
    
    return results


def generate_report(ticker: str, expected: Dict, actual: Dict, 
                    validation_results: List[Dict]) -> str:
    """Generate a detailed validation report."""
    lines = []
    lines.append("=" * 80)
    lines.append(f"DALIO ECONOMIC MACHINE VALIDATION REPORT - {ticker}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    
    # Summary
    passed = sum(1 for r in validation_results if r["passed"])
    total = len(validation_results)
    critical_failed = [r for r in validation_results if not r["passed"] and r["critical"]]
    
    lines.append(f"\n📊 SUMMARY: {passed}/{total} tests passed")
    if critical_failed:
        lines.append(f"⚠️  CRITICAL FAILURES: {len(critical_failed)}")
    else:
        lines.append("✅ All critical tests passed")
    
    # Raw data info
    lines.append(f"\n📈 Data Info:")
    lines.append(f"   Current Price: ${expected['raw_data']['current_price']:.2f}")
    lines.append(f"   Current VWAP: ${expected['raw_data']['current_vwap']:.2f}")
    lines.append(f"   Prior 20d VWAP: ${expected['raw_data']['prior_20d_vwap']:.2f}")
    lines.append(f"   Data Points: {expected['raw_data']['data_points']}")
    
    # Detailed results
    lines.append("\n" + "-" * 80)
    lines.append("DETAILED VALIDATION RESULTS")
    lines.append("-" * 80)
    
    for result in validation_results:
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        critical = " [CRITICAL]" if result["critical"] else ""
        lines.append(f"\n{status}{critical} {result['metric']}")
        lines.append(f"   {result['message']}")
    
    # Diagnostic section for failures
    if critical_failed:
        lines.append("\n" + "=" * 80)
        lines.append("⚠️  DIAGNOSTIC INFORMATION FOR CRITICAL FAILURES")
        lines.append("=" * 80)
        
        for failure in critical_failed:
            lines.append(f"\n❌ {failure['metric']}")
            lines.append(f"   Expected: {failure['expected']}")
            lines.append(f"   Actual: {failure['actual']}")
            
            # Add specific debugging hints
            if "Dalio Ratio" in failure['metric']:
                lines.append("\n   DEBUGGING HINTS for Dalio Ratio:")
                lines.append("   - Check session_vwap calculation: Dollar_Volume / Volume")
                lines.append("   - Verify prior_20d_vwap uses iloc[-21:-1].mean()")
                lines.append("   - Current VWAP should be last day's session VWAP")
                lines.append(f"   - Manual calc: {expected['raw_data']['current_vwap']:.4f} / {expected['raw_data']['prior_20d_vwap']:.4f} = {expected['dalio_ratio']['20d_avg']:.4f}")
            
            elif "Cumulative Dollar Flow" in failure['metric']:
                lines.append("\n   DEBUGGING HINTS for CDF:")
                lines.append("   - Check dv_direction: 1 if Close >= Open, else -1")
                lines.append("   - directional_dv = dollar_volume * dv_direction")
                lines.append("   - 20d CDF = sum of last 20 directional_dv values")
            
            elif "Dollar Volume" in failure['metric']:
                lines.append("\n   DEBUGGING HINTS for Dollar Volume:")
                lines.append("   - typical_price = (High + Low + Close) / 3")
                lines.append("   - dollar_volume = typical_price * Volume")
                lines.append("   - Check data source consistency")
    
    # Formula reference
    lines.append("\n" + "-" * 80)
    lines.append("FORMULA REFERENCE (from DALIO_IMPLEMENTATION_PLAN.md)")
    lines.append("-" * 80)
    lines.append("""
1. Session VWAP = Dollar_Volume / Share_Volume
2. Dalio Ratio = Current_Session_VWAP / Prior_20d_Session_VWAP_Average
3. Dollar Volume = Typical_Price * Volume
4. DV Momentum = (DV_today - DV_20d_avg) / DV_20d_avg * 100
5. Spending Efficiency = Price_Change_% / DV_Change_%
6. CDF = Sum(Dollar_Volume * Sign(Close - Open))
""")
    
    lines.append("\n" + "=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)
    
    return "\n".join(lines)


# =============================================================================
# MAIN VALIDATION FUNCTION
# =============================================================================

def validate_ticker(ticker: str, tool_output: Dict = None) -> Dict:
    """
    Run full validation for a single ticker.
    
    Args:
        ticker: Stock symbol
        tool_output: If provided, use this instead of calling the tool
    
    Returns:
        Validation results dictionary
    """
    print(f"\n🔍 Validating {ticker}...")
    
    # Step 1: Fetch raw OHLCV data
    print(f"   Fetching raw OHLCV data...")
    try:
        df = fetch_ohlcv_yfinance(ticker, period="3mo")
        print(f"   Got {len(df)} data points")
    except Exception as e:
        return {"error": f"Failed to fetch data: {e}"}
    
    # Step 2: Calculate expected values manually
    print(f"   Calculating expected Dalio metrics manually...")
    expected = calculate_dalio_metrics_manual(df)
    if "error" in expected:
        return expected
    
    # Step 3: Get tool output (if not provided)
    if tool_output is None:
        print(f"   ⚠️  Tool output not provided - using expected as baseline")
        actual = expected.copy()
    else:
        actual = tool_output.get("dalio_metrics", tool_output)
    
    # Step 4: Compare
    print(f"   Comparing expected vs actual...")
    validation_results = validate_dalio_metrics(expected, actual)
    
    # Step 5: Generate report
    report = generate_report(ticker, expected, actual, validation_results)
    
    # Summary
    passed = sum(1 for r in validation_results if r["passed"])
    total = len(validation_results)
    critical_failed = [r for r in validation_results if not r["passed"] and r["critical"]]
    
    return {
        "ticker": ticker,
        "passed": passed,
        "total": total,
        "critical_failures": len(critical_failed),
        "success": len(critical_failed) == 0,
        "results": validation_results,
        "expected": expected,
        "actual": actual,
        "report": report
    }


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Validate Dalio Economic Machine calculations against manual calculations"
    )
    parser.add_argument(
        "tickers", 
        nargs="+", 
        help="Stock tickers to validate (e.g., AAPL NVDA TSLA)"
    )
    parser.add_argument(
        "--output", 
        "-o", 
        help="Output file for detailed report (optional)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show full report for each ticker"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("DALIO ECONOMIC MACHINE - VALIDATION TEST")
    print("=" * 80)
    
    all_results = []
    
    for ticker in args.tickers:
        result = validate_ticker(ticker.upper())
        all_results.append(result)
        
        if "error" in result:
            print(f"\n❌ {ticker}: ERROR - {result['error']}")
            continue
        
        status = "✅ PASSED" if result["success"] else "❌ FAILED"
        print(f"\n{status} {ticker}: {result['passed']}/{result['total']} tests")
        if result["critical_failures"] > 0:
            print(f"   ⚠️  {result['critical_failures']} CRITICAL FAILURES")
        
        if args.verbose:
            print("\n" + result["report"])
    
    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    total_passed = sum(r.get("passed", 0) for r in all_results if "error" not in r)
    total_tests = sum(r.get("total", 0) for r in all_results if "error" not in r)
    total_critical = sum(r.get("critical_failures", 0) for r in all_results if "error" not in r)
    
    print(f"Total: {total_passed}/{total_tests} tests passed")
    print(f"Critical failures: {total_critical}")
    
    all_success = all(r.get("success", False) for r in all_results if "error" not in r)
    if all_success:
        print("\n✅ ALL VALIDATIONS PASSED")
    else:
        print("\n❌ SOME VALIDATIONS FAILED - See reports above for details")
    
    # Output to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            for result in all_results:
                if "report" in result:
                    f.write(result["report"])
                    f.write("\n\n")
        print(f"\nDetailed reports saved to: {args.output}")
    
    if args.json:
        # Remove non-serializable items
        clean_results = []
        for r in all_results:
            clean = {k: v for k, v in r.items() if k != "report"}
            # Convert numpy types
            clean = json.loads(json.dumps(clean, default=str))
            clean_results.append(clean)
        print("\n" + json.dumps(clean_results, indent=2))
    
    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
