# Ray Dalio Economic Machine - Implementation Plan

**Date:** January 4, 2026
**Status:** PLANNING
**Based On:** [RAY_DALIO_ECONOMIC_MACHINE_IMPLEMENTATION.md](RAY_DALIO_ECONOMIC_MACHINE_IMPLEMENTATION.md)

---

## Executive Summary

Implement Ray Dalio's "Price = Total Spending / Quantity Sold" principle into the investor-agent MCP tools. This adds institutional-grade dollar volume analysis to detect accumulation, distribution, and trend sustainability.

**Core Insight:** Track where CAPITAL is flowing, not just share volume.

---

## Implementation Approach

**DECISION:** Enhance existing `analyze_volume_tool()` instead of creating a new standalone tool.

**Rationale:**
- 80% of infrastructure already exists (VWAP, OBV, CVD calculations)
- Avoids tool sprawl
- Seamless integration with existing workflows
- Easier maintenance

---

## Phase 1: Core Metrics (analyze_volume_tool Enhancement)

### Task 1A: Dollar Volume Calculations
**File:** `investor_agent/server.py` → `analyze_volume_tool()`

```python
# Add to existing analyze_volume_tool()
df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
df['dollar_volume'] = df['typical_price'] * df['volume']

# Calculate aggregates
dv_today = df['dollar_volume'].iloc[-1]
dv_5d_avg = df['dollar_volume'].iloc[-5:].mean()
dv_20d_avg = df['dollar_volume'].iloc[-20:].mean()
dv_50d_avg = df['dollar_volume'].iloc[-50:].mean()
```

**Output Structure:**
```python
"dollar_volume": {
    "today": 15_200_000_000,
    "5d_avg": 12_800_000_000,
    "20d_avg": 11_500_000_000,
    "50d_avg": 10_200_000_000,
    "relative_to_20d": 1.32,
    "percentile_90d": 85
}
```

---

### Task 1B: Dalio Ratio
**Formula:** `Dalio Ratio = Current Session VWAP / Prior Period VWAP`

```python
# Session VWAP for each day
df['session_vwap'] = df['dollar_volume'] / df['volume']

# Dalio Ratio calculations
current_vwap = df['session_vwap'].iloc[-1]
prior_5d_vwap = df['session_vwap'].iloc[-6:-1].mean()
prior_20d_vwap = df['session_vwap'].iloc[-21:-1].mean()

dalio_ratio_5d = current_vwap / prior_5d_vwap
dalio_ratio_20d = current_vwap / prior_20d_vwap
```

**Interpretation Thresholds:**
| Dalio Ratio | Interpretation |
|-------------|----------------|
| > 1.05 | STRONG_BULLISH |
| 1.02 - 1.05 | BULLISH |
| 0.98 - 1.02 | NEUTRAL |
| 0.95 - 0.98 | BEARISH |
| < 0.95 | STRONG_BEARISH |

---

### Task 1C: Dollar Volume Momentum (DVM)
**Formula:** `DVM = (DV_today - DV_20d_avg) / DV_20d_avg * 100`

```python
dv_momentum = (dv_today - dv_20d_avg) / dv_20d_avg * 100

# Classification
def classify_dv_momentum(momentum_pct):
    if momentum_pct > 100: return "EXTREME_INFLOW"
    elif momentum_pct > 50: return "STRONG_INFLOW"
    elif momentum_pct > 20: return "INFLOW"
    elif momentum_pct > -20: return "NEUTRAL"
    elif momentum_pct > -50: return "OUTFLOW"
    else: return "STRONG_OUTFLOW"
```

---

### Task 1D: Spending Efficiency Ratio (SER)
**Formula:** `SER = Price_Change_% / Dollar_Volume_Change_%`

```python
price_change_pct = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100
dv_change_pct = (dv_today - df['dollar_volume'].iloc[-2]) / df['dollar_volume'].iloc[-2] * 100

spending_efficiency = price_change_pct / dv_change_pct if dv_change_pct != 0 else 0
```

**Interpretation:**
| Efficiency | Meaning | Implication |
|------------|---------|-------------|
| > 1.5 | LOW_LIQUIDITY | Small capital = big moves (avoid) |
| 0.8 - 1.5 | NORMAL | Standard market |
| 0.3 - 0.8 | HIGH_ABSORPTION | Big capital = small moves |
| < 0.3 | VERY_HIGH_ABSORPTION | Strong hands accumulating |

---

### Task 1E: Cumulative Dollar Flow (CDF)
**Formula:** `CDF = Sum(Dollar_Volume * Sign(Close - Open))`

```python
df['dv_direction'] = np.where(df['close'] >= df['open'], 1, -1)
df['directional_dv'] = df['dollar_volume'] * df['dv_direction']

cdf_5d = df['directional_dv'].iloc[-5:].sum()
cdf_20d = df['directional_dv'].iloc[-20:].sum()
```

**Output:**
```python
"cumulative_dollar_flow": {
    "5d": 2_500_000_000,
    "20d": 8_200_000_000,
    "direction": "ACCUMULATION",  # or "DISTRIBUTION"
    "acceleration": "INCREASING"   # or "DECREASING" / "FLAT"
}
```

---

### Task 1F: Dollar Volume Profile
**Purpose:** Find where most CAPITAL was deployed (not just shares).

```python
def calculate_dollar_volume_profile(df, bins=20):
    price_min, price_max = df['low'].min(), df['high'].max()
    bin_size = (price_max - price_min) / bins

    profile = {}
    for i in range(bins):
        price_low = price_min + (i * bin_size)
        price_high = price_low + bin_size
        price_mid = (price_low + price_high) / 2

        mask = (df['low'] <= price_mid) & (df['high'] >= price_mid)
        dv_at_level = df.loc[mask, 'dollar_volume'].sum() / mask.sum() if mask.sum() > 0 else 0
        profile[round(price_mid, 2)] = int(dv_at_level)

    # Point of Control = price with highest dollar volume
    poc = max(profile, key=profile.get)

    # Value Area (70% of dollar volume)
    # ... calculation ...

    return {
        "point_of_control": poc,
        "value_area_high": va_high,
        "value_area_low": va_low,
        "current_vs_poc": "ABOVE" if current_price > poc else "BELOW"
    }
```

---

### Task 1G: Institutional Activity Detection

```python
def detect_institutional_activity(df, dv_momentum, spending_efficiency, cdf_20d):
    signals = []
    confidence = 0

    # Check 1: Dollar volume significantly above average
    if dv_momentum > 50:
        signals.append(f"Dollar volume {dv_momentum:.0f}% above 20d avg")
        confidence += 30

    # Check 2: High absorption (big money, small moves)
    if spending_efficiency < 0.5:
        signals.append("Spending efficiency suggests absorption")
        confidence += 25

    # Check 3: Consistent directional flow
    if abs(cdf_20d) > df['dollar_volume'].iloc[-20:].sum() * 0.3:
        signals.append("Strong directional dollar commitment")
        confidence += 25

    # Check 4: Multiple high-dollar-volume days
    high_dv_days = (df['dollar_volume'].iloc[-20:] > df['dollar_volume'].iloc[-50:].mean() * 1.5).sum()
    if high_dv_days >= 5:
        signals.append(f"{high_dv_days} high-dollar-volume days in 20d")
        confidence += 20

    return {
        "detected": confidence >= 50,
        "confidence": "HIGH" if confidence >= 75 else "MEDIUM" if confidence >= 50 else "LOW",
        "signals": signals,
        "likely_direction": "ACCUMULATION" if cdf_20d > 0 else "DISTRIBUTION",
        "estimated_commitment": abs(cdf_20d)
    }
```

---

### Task 1H: Trend Sustainability Score

```python
def assess_trend_sustainability(dalio_ratio, dv_momentum, spending_efficiency, cdf_20d, current_price, poc):
    score = 0
    factors = {}

    # Factor 1: Dalio Ratio trend (25 points)
    if dalio_ratio > 1.02:
        score += 25
        factors["dalio_ratio"] = "POSITIVE"
    elif dalio_ratio < 0.98:
        factors["dalio_ratio"] = "NEGATIVE"
    else:
        score += 12
        factors["dalio_ratio"] = "NEUTRAL"

    # Factor 2: Dollar volume momentum (25 points)
    if dv_momentum > 20:
        score += 25
        factors["dollar_volume_trend"] = "POSITIVE"
    elif dv_momentum < -20:
        factors["dollar_volume_trend"] = "NEGATIVE"
    else:
        score += 12
        factors["dollar_volume_trend"] = "NEUTRAL"

    # Factor 3: Spending efficiency (25 points)
    if 0.3 <= spending_efficiency <= 1.2:
        score += 25
        factors["efficiency_trend"] = "STABLE"
    else:
        score += 10
        factors["efficiency_trend"] = "UNSTABLE"

    # Factor 4: Price vs POC (25 points)
    price_vs_poc = (current_price - poc) / poc * 100
    if -5 <= price_vs_poc <= 10:
        score += 25
        factors["price_vs_poc"] = "FAVORABLE"
    else:
        score += 10
        factors["price_vs_poc"] = "EXTENDED"

    # Grade
    if score >= 80: grade = "A"
    elif score >= 70: grade = "B+"
    elif score >= 60: grade = "B"
    elif score >= 50: grade = "C"
    else: grade = "D"

    return {
        "score": score,
        "grade": grade,
        "assessment": "SUSTAINABLE" if score >= 60 else "AT_RISK" if score >= 40 else "UNSUSTAINABLE",
        "factors": factors
    }
```

---

## Phase 2: Integration

### Task 2A: Gate 2 (Freshness) Enhancement

**Current Gate 2 Checks:**
1. Trend Days <= 3
2. Exhaustion Score < 50
3. CVD Alignment

**Add Dalio Checks:**
4. Dalio Ratio Aligned (>1.0 for LONG, <1.0 for SHORT)
5. Dollar Flow Aligned (CDF_20d positive for LONG, negative for SHORT)
6. Sustainability Score >= 50

**New Gate 2 Logic:**
```python
gate_2_checks = {
    # Original
    "trend_days_ok": trend_days <= 3,
    "exhaustion_ok": exhaustion_score < 50,
    "cvd_aligned": cvd_direction == trade_direction,

    # NEW: Dalio checks
    "dalio_ratio_aligned": (
        (direction == "LONG" and dalio_ratio > 1.0) or
        (direction == "SHORT" and dalio_ratio < 1.0)
    ),
    "dollar_flow_aligned": (
        (direction == "LONG" and cdf_20d > 0) or
        (direction == "SHORT" and cdf_20d < 0)
    ),
    "sustainability_ok": sustainability_score >= 50
}

# Gate 2 passes if 5/6 checks pass
gate_2_pass = sum(gate_2_checks.values()) >= 5
```

---

### Task 2B: Scanner Tier 1 Filters

**Add to Tier 1 (Momentum Quality):**
```python
tier_1_dalio_filters = {
    # For LONG setups
    "dalio_ratio_min": 1.00,           # Buyers paying same or more
    "dollar_volume_vs_20d_min": 1.20,  # At least 20% above average
    "cdf_direction": "POSITIVE",       # Net inflow

    # For SHORT setups
    "dalio_ratio_max": 1.00,           # Buyers paying same or less
    "dollar_volume_vs_20d_min": 1.20,  # Still need volume
    "cdf_direction": "NEGATIVE"        # Net outflow
}
```

---

### Task 2C: Report Template Update

Add new section to scanner reports after Volume Analysis:

```markdown
#### DALIO ECONOMIC MACHINE ANALYSIS [analyze_volume_tool.dalio_metrics]

**Core Principle:** Price = Total Spending / Quantity Sold

DALIO RATIO:        X.XX [BULLISH / NEUTRAL / BEARISH]
├─ Current:         X.XX (vs prior 5d VWAP)
├─ 20d Average:     X.XX
└─ Trend:           [INCREASING / FLAT / DECREASING]

**Dollar Volume Analysis:**
| Metric | Value | vs 20d Avg | Signal |
|--------|-------|------------|--------|
| Today DV | $XXB | +XX% | [STRONG_INFLOW / NEUTRAL / OUTFLOW] |

**Cumulative Dollar Flow:**
- 20d: $+/-XXB [ACCUMULATION / DISTRIBUTION]

**Trend Sustainability:** XX/100 (Grade: X)

**Gate 2 Dalio Contribution:** [PASS / FAIL]
```

---

## Phase 3: Automated Testing

### Test File: `tests/test_dalio_economic_machine.py`

```python
"""
Automated tests for Ray Dalio Economic Machine implementation.

Tests cover:
1. Dollar Volume calculations
2. Dalio Ratio accuracy
3. Dollar Volume Momentum classification
4. Spending Efficiency interpretation
5. Cumulative Dollar Flow direction
6. Dollar Volume Profile POC/VAH/VAL
7. Institutional Activity detection
8. Trend Sustainability scoring
9. Gate 2 integration
10. Scanner filter integration

Run with: pytest tests/test_dalio_economic_machine.py -v
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Import functions to test (after implementation)
# from investor_agent.server import analyze_volume_tool


class TestDollarVolumeCalculations:
    """Test Task 1A: Dollar Volume Calculations"""

    @pytest.fixture
    def sample_ohlcv_data(self):
        """Create sample OHLCV data for testing"""
        dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
        np.random.seed(42)

        data = {
            'open': 100 + np.random.randn(60).cumsum(),
            'high': 0,
            'low': 0,
            'close': 0,
            'volume': np.random.randint(1_000_000, 10_000_000, 60)
        }
        data['high'] = data['open'] + abs(np.random.randn(60)) * 2
        data['low'] = data['open'] - abs(np.random.randn(60)) * 2
        data['close'] = data['open'] + np.random.randn(60)

        df = pd.DataFrame(data, index=dates)
        return df

    def test_dollar_volume_calculation(self, sample_ohlcv_data):
        """Dollar volume = typical_price * volume"""
        df = sample_ohlcv_data
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['dollar_volume'] = df['typical_price'] * df['volume']

        # Verify calculation
        expected = df['typical_price'].iloc[0] * df['volume'].iloc[0]
        assert df['dollar_volume'].iloc[0] == pytest.approx(expected)

    def test_dollar_volume_averages(self, sample_ohlcv_data):
        """Test 5d, 20d, 50d averages"""
        df = sample_ohlcv_data
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['dollar_volume'] = df['typical_price'] * df['volume']

        dv_5d = df['dollar_volume'].iloc[-5:].mean()
        dv_20d = df['dollar_volume'].iloc[-20:].mean()
        dv_50d = df['dollar_volume'].iloc[-50:].mean()

        assert dv_5d > 0
        assert dv_20d > 0
        assert dv_50d > 0

    def test_relative_dollar_volume(self, sample_ohlcv_data):
        """Test relative DV calculation"""
        df = sample_ohlcv_data
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['dollar_volume'] = df['typical_price'] * df['volume']

        dv_today = df['dollar_volume'].iloc[-1]
        dv_20d = df['dollar_volume'].iloc[-20:].mean()

        relative = dv_today / dv_20d
        assert relative > 0


class TestDalioRatio:
    """Test Task 1B: Dalio Ratio"""

    @pytest.fixture
    def sample_vwap_data(self):
        """Create sample VWAP data"""
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        # Uptrending VWAP
        vwaps = 100 + np.arange(30) * 0.5 + np.random.randn(30) * 0.2
        return pd.DataFrame({'session_vwap': vwaps}, index=dates)

    def test_dalio_ratio_bullish(self, sample_vwap_data):
        """Dalio Ratio > 1.0 = BULLISH"""
        df = sample_vwap_data
        current_vwap = df['session_vwap'].iloc[-1]
        prior_vwap = df['session_vwap'].iloc[-6:-1].mean()

        dalio_ratio = current_vwap / prior_vwap
        assert dalio_ratio > 1.0  # Uptrending = bullish

    def test_dalio_ratio_bearish(self):
        """Dalio Ratio < 1.0 = BEARISH"""
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        # Downtrending VWAP
        vwaps = 100 - np.arange(30) * 0.5 + np.random.randn(30) * 0.2
        df = pd.DataFrame({'session_vwap': vwaps}, index=dates)

        current_vwap = df['session_vwap'].iloc[-1]
        prior_vwap = df['session_vwap'].iloc[-6:-1].mean()

        dalio_ratio = current_vwap / prior_vwap
        assert dalio_ratio < 1.0  # Downtrending = bearish

    def test_dalio_ratio_interpretation(self):
        """Test interpretation thresholds"""
        def interpret(ratio):
            if ratio > 1.05: return "STRONG_BULLISH"
            elif ratio > 1.02: return "BULLISH"
            elif ratio > 0.98: return "NEUTRAL"
            elif ratio > 0.95: return "BEARISH"
            else: return "STRONG_BEARISH"

        assert interpret(1.10) == "STRONG_BULLISH"
        assert interpret(1.03) == "BULLISH"
        assert interpret(1.00) == "NEUTRAL"
        assert interpret(0.96) == "BEARISH"
        assert interpret(0.90) == "STRONG_BEARISH"


class TestDollarVolumeMomentum:
    """Test Task 1C: Dollar Volume Momentum"""

    def test_extreme_inflow(self):
        """DVM > 100% = EXTREME_INFLOW"""
        dv_today = 250_000_000
        dv_20d_avg = 100_000_000
        momentum = (dv_today - dv_20d_avg) / dv_20d_avg * 100

        assert momentum == 150
        assert momentum > 100  # EXTREME_INFLOW

    def test_strong_inflow(self):
        """DVM 50-100% = STRONG_INFLOW"""
        dv_today = 160_000_000
        dv_20d_avg = 100_000_000
        momentum = (dv_today - dv_20d_avg) / dv_20d_avg * 100

        assert 50 < momentum < 100

    def test_classification(self):
        """Test all DVM classifications"""
        def classify(momentum):
            if momentum > 100: return "EXTREME_INFLOW"
            elif momentum > 50: return "STRONG_INFLOW"
            elif momentum > 20: return "INFLOW"
            elif momentum > -20: return "NEUTRAL"
            elif momentum > -50: return "OUTFLOW"
            else: return "STRONG_OUTFLOW"

        assert classify(150) == "EXTREME_INFLOW"
        assert classify(75) == "STRONG_INFLOW"
        assert classify(30) == "INFLOW"
        assert classify(0) == "NEUTRAL"
        assert classify(-30) == "OUTFLOW"
        assert classify(-60) == "STRONG_OUTFLOW"


class TestSpendingEfficiency:
    """Test Task 1D: Spending Efficiency Ratio"""

    def test_high_absorption(self):
        """SER < 0.3 = HIGH_ABSORPTION (accumulation)"""
        price_change = 0.5  # 0.5% price change
        dv_change = 50      # 50% volume change
        efficiency = price_change / dv_change

        assert efficiency < 0.3  # HIGH_ABSORPTION

    def test_low_liquidity(self):
        """SER > 1.5 = LOW_LIQUIDITY (avoid)"""
        price_change = 5    # 5% price change
        dv_change = 2       # 2% volume change
        efficiency = price_change / dv_change

        assert efficiency > 1.5  # LOW_LIQUIDITY

    def test_normal_efficiency(self):
        """SER 0.8-1.5 = NORMAL"""
        price_change = 2    # 2% price change
        dv_change = 2       # 2% volume change
        efficiency = price_change / dv_change

        assert 0.8 <= efficiency <= 1.5  # NORMAL


class TestCumulativeDollarFlow:
    """Test Task 1E: Cumulative Dollar Flow"""

    @pytest.fixture
    def sample_directional_data(self):
        """Create data with known direction"""
        dates = pd.date_range(end=datetime.now(), periods=20, freq='D')
        data = {
            'open': [100] * 20,
            'close': [101] * 15 + [99] * 5,  # 15 up days, 5 down days
            'dollar_volume': [1_000_000] * 20
        }
        return pd.DataFrame(data, index=dates)

    def test_accumulation_detection(self, sample_directional_data):
        """Net positive CDF = ACCUMULATION"""
        df = sample_directional_data
        df['direction'] = np.where(df['close'] >= df['open'], 1, -1)
        df['directional_dv'] = df['dollar_volume'] * df['direction']

        cdf = df['directional_dv'].sum()
        assert cdf > 0  # 15 up - 5 down = net positive

    def test_distribution_detection(self):
        """Net negative CDF = DISTRIBUTION"""
        dates = pd.date_range(end=datetime.now(), periods=20, freq='D')
        data = {
            'open': [100] * 20,
            'close': [99] * 15 + [101] * 5,  # 15 down days, 5 up days
            'dollar_volume': [1_000_000] * 20
        }
        df = pd.DataFrame(data, index=dates)
        df['direction'] = np.where(df['close'] >= df['open'], 1, -1)
        df['directional_dv'] = df['dollar_volume'] * df['direction']

        cdf = df['directional_dv'].sum()
        assert cdf < 0  # Net negative = DISTRIBUTION


class TestDollarVolumeProfile:
    """Test Task 1F: Dollar Volume Profile"""

    def test_poc_calculation(self):
        """Point of Control = price with highest dollar volume"""
        profile = {
            180.0: 1_000_000,
            185.0: 5_000_000,  # Highest
            190.0: 2_000_000,
            195.0: 1_500_000
        }

        poc = max(profile, key=profile.get)
        assert poc == 185.0

    def test_value_area(self):
        """Value Area contains 70% of dollar volume"""
        profile = {
            180.0: 1_000_000,
            185.0: 5_000_000,
            190.0: 3_000_000,
            195.0: 1_000_000
        }
        total = sum(profile.values())  # 10M

        # Sort by DV descending
        sorted_levels = sorted(profile.items(), key=lambda x: x[1], reverse=True)

        cumulative = 0
        value_area_prices = []
        for price, dv in sorted_levels:
            cumulative += dv
            value_area_prices.append(price)
            if cumulative >= total * 0.70:
                break

        # 185 + 190 = 8M = 80% > 70%
        assert 185.0 in value_area_prices
        assert 190.0 in value_area_prices


class TestInstitutionalDetection:
    """Test Task 1G: Institutional Activity Detection"""

    def test_high_confidence_detection(self):
        """Multiple signals = HIGH confidence"""
        dv_momentum = 60      # > 50
        spending_efficiency = 0.4  # < 0.5
        cdf_20d = 5_000_000_000
        avg_dv_20d = 10_000_000_000

        confidence = 0
        if dv_momentum > 50:
            confidence += 30
        if spending_efficiency < 0.5:
            confidence += 25
        if abs(cdf_20d) > avg_dv_20d * 0.3:
            confidence += 25

        assert confidence >= 50  # HIGH confidence threshold

    def test_low_confidence(self):
        """Few signals = LOW confidence"""
        dv_momentum = 10      # < 50
        spending_efficiency = 1.0  # > 0.5
        cdf_20d = 100_000
        avg_dv_20d = 10_000_000_000

        confidence = 0
        if dv_momentum > 50:
            confidence += 30
        if spending_efficiency < 0.5:
            confidence += 25
        if abs(cdf_20d) > avg_dv_20d * 0.3:
            confidence += 25

        assert confidence < 50  # LOW confidence


class TestTrendSustainability:
    """Test Task 1H: Trend Sustainability Score"""

    def test_high_sustainability(self):
        """All positive factors = high score"""
        score = 0

        # Dalio ratio bullish
        dalio_ratio = 1.05
        if dalio_ratio > 1.02:
            score += 25

        # DV momentum positive
        dv_momentum = 30
        if dv_momentum > 20:
            score += 25

        # Efficiency stable
        efficiency = 1.0
        if 0.3 <= efficiency <= 1.2:
            score += 25

        # Price near POC
        price_vs_poc_pct = 3
        if -5 <= price_vs_poc_pct <= 10:
            score += 25

        assert score >= 80  # Grade A

    def test_grade_assignment(self):
        """Test grade thresholds"""
        def get_grade(score):
            if score >= 80: return "A"
            elif score >= 70: return "B+"
            elif score >= 60: return "B"
            elif score >= 50: return "C"
            else: return "D"

        assert get_grade(85) == "A"
        assert get_grade(75) == "B+"
        assert get_grade(65) == "B"
        assert get_grade(55) == "C"
        assert get_grade(40) == "D"


class TestGate2Integration:
    """Test Task 2A: Gate 2 Dalio Integration"""

    def test_gate_2_pass_with_dalio(self):
        """Gate 2 passes with 5/6 checks"""
        checks = {
            "trend_days_ok": True,
            "exhaustion_ok": True,
            "cvd_aligned": True,
            "dalio_ratio_aligned": True,
            "dollar_flow_aligned": True,
            "sustainability_ok": False  # 1 failure
        }

        passed = sum(checks.values())
        assert passed >= 5  # PASS

    def test_gate_2_fail(self):
        """Gate 2 fails with <5 checks"""
        checks = {
            "trend_days_ok": True,
            "exhaustion_ok": True,
            "cvd_aligned": False,
            "dalio_ratio_aligned": False,
            "dollar_flow_aligned": False,
            "sustainability_ok": False  # 4 failures
        }

        passed = sum(checks.values())
        assert passed < 5  # FAIL

    def test_dalio_ratio_alignment_long(self):
        """Dalio ratio > 1.0 for LONG"""
        direction = "LONG"
        dalio_ratio = 1.03

        aligned = (direction == "LONG" and dalio_ratio > 1.0)
        assert aligned is True

    def test_dalio_ratio_alignment_short(self):
        """Dalio ratio < 1.0 for SHORT"""
        direction = "SHORT"
        dalio_ratio = 0.97

        aligned = (direction == "SHORT" and dalio_ratio < 1.0)
        assert aligned is True


class TestScannerIntegration:
    """Test Task 2B: Scanner Filter Integration"""

    def test_tier1_long_filters(self):
        """LONG setup passes Dalio filters"""
        candidate = {
            "dalio_ratio": 1.05,
            "dv_vs_20d": 1.35,
            "cdf_direction": "POSITIVE"
        }

        filters = {
            "dalio_ratio_min": 1.00,
            "dv_vs_20d_min": 1.20,
            "cdf_direction": "POSITIVE"
        }

        passes = (
            candidate["dalio_ratio"] >= filters["dalio_ratio_min"] and
            candidate["dv_vs_20d"] >= filters["dv_vs_20d_min"] and
            candidate["cdf_direction"] == filters["cdf_direction"]
        )
        assert passes is True

    def test_tier1_short_filters(self):
        """SHORT setup passes Dalio filters"""
        candidate = {
            "dalio_ratio": 0.95,
            "dv_vs_20d": 1.40,
            "cdf_direction": "NEGATIVE"
        }

        filters = {
            "dalio_ratio_max": 1.00,
            "dv_vs_20d_min": 1.20,
            "cdf_direction": "NEGATIVE"
        }

        passes = (
            candidate["dalio_ratio"] <= filters["dalio_ratio_max"] and
            candidate["dv_vs_20d"] >= filters["dv_vs_20d_min"] and
            candidate["cdf_direction"] == filters["cdf_direction"]
        )
        assert passes is True


# ============================================================================
# INTEGRATION TESTS (require MCP server running)
# ============================================================================

@pytest.mark.integration
class TestLiveIntegration:
    """
    Live integration tests against MCP server.

    Prerequisites:
    1. Docker container running: docker ps | grep investor-agent-mcp
    2. Questrade token valid (not expired)

    Run with: pytest tests/test_dalio_economic_machine.py -v -m integration
    """

    @pytest.fixture
    def mcp_client(self):
        """Create MCP client for testing"""
        # This would be implemented based on your MCP client setup
        # For now, return a mock or skip if not available
        pytest.skip("MCP client not configured for integration tests")

    def test_analyze_volume_has_dalio_metrics(self, mcp_client):
        """analyze_volume_tool returns dalio_metrics section"""
        result = mcp_client.call("analyze_volume_tool", ticker="AAPL")

        assert "dalio_metrics" in result
        assert "dalio_ratio" in result["dalio_metrics"]
        assert "dollar_volume" in result["dalio_metrics"]
        assert "cumulative_dollar_flow" in result["dalio_metrics"]

    def test_dalio_ratio_reasonable(self, mcp_client):
        """Dalio ratio is within reasonable bounds (0.8 - 1.2)"""
        result = mcp_client.call("analyze_volume_tool", ticker="AAPL")

        ratio = result["dalio_metrics"]["dalio_ratio"]["current"]
        assert 0.8 <= ratio <= 1.2

    def test_gate_2_includes_dalio(self, mcp_client):
        """Gate 2 validation includes Dalio checks"""
        result = mcp_client.call("generate_trading_signal", ticker="AAPL")

        gate_2 = result.get("gates", {}).get("gate_2", {})
        assert "dalio_ratio_aligned" in gate_2.get("details", {})
        assert "dollar_flow_aligned" in gate_2.get("details", {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Development Workflow

### Before Making Code Changes

```bash
# 1. Check Docker container is running
docker ps | grep investor-agent-mcp

# 2. Check current Questrade token is valid
# (Run in Claude Code)
get_questrade_accounts()
```

### After Making Code Changes

```bash
# CRITICAL: Code changes require Docker rebuild!

# Step 1: Rebuild Docker image
cd /Users/AhmedE/git/investor-agent
docker build -t investor-agent-mcp .

# Step 2: Restart container with token
docker stop investor-agent-mcp && docker rm investor-agent-mcp
docker run -d --name investor-agent-mcp \
  -v ~/.questrade.json:/root/.questrade.json \
  investor-agent-mcp

# Step 3: Verify new code is in container
docker exec investor-agent-mcp grep "dalio_metrics" /app/investor_agent/server.py
# Should return matches if code was added
```

### Quick Rebuild Script

Create `rebuild.sh`:
```bash
#!/bin/bash
echo "=== Rebuilding investor-agent-mcp ==="

echo "1. Building Docker image..."
docker build -t investor-agent-mcp . || exit 1

echo "2. Stopping old container..."
docker stop investor-agent-mcp 2>/dev/null
docker rm investor-agent-mcp 2>/dev/null

echo "3. Starting new container..."
docker run -d --name investor-agent-mcp \
  -v ~/.questrade.json:/root/.questrade.json \
  investor-agent-mcp || exit 1

echo "4. Waiting for container to start..."
sleep 2

echo "5. Verifying container is running..."
docker ps | grep investor-agent-mcp

echo "=== Rebuild complete ==="
echo "Restart Claude Code to reconnect MCP"
```

---

## Questrade Token Refresh (For Testing)

### When Token Expires (HTTP 400 Error)

1. **Get new token from Questrade:**
   - Go to: https://login.questrade.com/APIAccess/UserApps.aspx
   - Click "Generate new token"
   - Copy the new token

2. **Test token locally first:**
   ```bash
   python3 -c "
   from questrade_api import Questrade
   q = Questrade(refresh_token='YOUR_NEW_TOKEN')
   print('Token works!')
   print(f'Accounts: {q.accounts}')
   "
   ```

3. **Restart Docker with updated token:**
   ```bash
   # Token is auto-saved to ~/.questrade.json after local test
   docker stop investor-agent-mcp && docker rm investor-agent-mcp
   docker run -d --name investor-agent-mcp \
     -v ~/.questrade.json:/root/.questrade.json \
     investor-agent-mcp
   ```

4. **Test MCP connection:**
   ```
   # In Claude Code
   get_questrade_accounts()
   ```

### Token Best Practices

| Do | Don't |
|----|-------|
| Keep single container running | Run multiple containers with same token |
| Use volume for token persistence | Restart container without volume |
| Test locally first, then Docker | Test in parallel (consumes token) |
| Generate new token only when needed | Share token between instances |

---

## Running Tests

### Unit Tests (No MCP Required)
```bash
cd /Users/AhmedE/git/investor-agent
pytest tests/test_dalio_economic_machine.py -v
```

### Integration Tests (MCP Required)
```bash
# Ensure Docker container is running first
pytest tests/test_dalio_economic_machine.py -v -m integration
```

### All Tests
```bash
pytest tests/ -v
```

### Test Coverage
```bash
pytest tests/test_dalio_economic_machine.py --cov=investor_agent --cov-report=html
```

---

## Validation Checklist

After implementation, verify each component:

- [ ] `analyze_volume_tool()` returns `dalio_metrics` section
- [ ] Dalio Ratio calculated correctly (current VWAP / prior VWAP)
- [ ] Dollar Volume Momentum classification works
- [ ] Spending Efficiency interpretation correct
- [ ] Cumulative Dollar Flow shows ACCUMULATION/DISTRIBUTION
- [ ] Dollar Volume Profile calculates POC/VAH/VAL
- [ ] Institutional Activity detection triggers on high DV + low efficiency
- [ ] Trend Sustainability Score grades correctly
- [ ] Gate 2 includes 3 new Dalio checks (5/6 to pass)
- [ ] Scanner Tier 1 filters include Dalio criteria
- [ ] Report templates show Dalio section
- [ ] All unit tests pass
- [ ] Integration tests pass with live MCP

---

## Timeline

| Phase | Tasks | Status |
|-------|-------|--------|
| **Phase 1** | Core Metrics (1A-1H) | PENDING |
| **Phase 2** | Integration (2A-2C) | PENDING |
| **Phase 3** | Testing | PENDING |

---

**Document Version:** 1.0
**Last Updated:** January 4, 2026
