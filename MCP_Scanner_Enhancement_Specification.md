# MCP Scanner Enhancement Specification

> **Purpose:** Technical specification for enhancing the market opportunity scanner to find stocks at inflection points rather than confirmation points.
> **Methodology:** Al Brooks Price Action + McMillan Options Strategy
> **Created:** 2024-12-19

---

## Executive Summary

**Problem:** Current scanner produces candidates that are either exhausted (late-stage trends) or slow-moving (insufficient volatility for trading).

**Solution:** Implement momentum-timing filters that identify stocks at **inflection points** rather than confirmation points.

### Current vs Proposed Approach

| Current Approach | Better Approach |
|-----------------|-----------------|
| Find stocks IN trends | Find stocks ENTERING trends |
| Golden/Death Cross (lagging) | Consolidation breakout (leading) |
| Any momentum | Momentum + consolidation |
| RSI extremes | RSI middle range |

---

## Filter Architecture

### Priority Levels

```
TIER 1: MOMENTUM QUALITY FILTERS (Required - All must pass)
TIER 2: PATTERN QUALITY FILTERS (Required - Minimum 2 of 4)
TIER 3: CATALYST FILTERS (Preferred - Adds to score)
TIER 4: EXCLUSION FILTERS (Required - Rejects bad setups)
```

---

## TIER 1: Momentum Quality Filters

### 1.1 ADX (Average Directional Index) - NEW INDICATOR NEEDED

**Purpose:** Measure trend strength without indicating direction. Identifies "trending but not exhausted" sweet spot.

```python
ADX_FILTER = {
    "indicator": "ADX",
    "period": 14,
    "long_criteria": {
        "min": 20,      # Must be trending (not flat)
        "max": 40,      # Not exhausted
        "optimal": [25, 35]  # Sweet spot for scoring
    },
    "short_criteria": {
        "min": 20,
        "max": 40,
        "optimal": [25, 35]
    }
}
```

**Scoring:**
- ADX 25-35: +10 pts (optimal)
- ADX 20-25 or 35-40: +5 pts (acceptable)
- ADX < 20: REJECT (no trend)
- ADX > 40: REJECT (exhausted)

**Why Critical:** Current scanner has no exhaustion filter. ADX > 40 indicates trend is overextended.

---

### 1.2 RSI Position Filter - MODIFY EXISTING

**Purpose:** Find stocks with room to run, not already overbought/oversold.

```python
RSI_FILTER = {
    "indicator": "RSI",
    "period": 14,
    "long_criteria": {
        "min": 40,      # Not oversold (avoid catching knives)
        "max": 65,      # Not overbought (room to run)
        "optimal": [50, 60],  # Middle of range, momentum building
        "reject_above": 70    # Hard reject - exhausted
    },
    "short_criteria": {
        "min": 35,
        "max": 60,
        "optimal": [40, 50],
        "reject_below": 30    # Hard reject - oversold bounce risk
    }
}
```

**Scoring:**
- RSI in optimal range: +10 pts
- RSI in acceptable range: +5 pts
- RSI outside range: REJECT

**Current Problem:** Scanner likely accepts RSI extremes, producing exhausted candidates.

---

### 1.3 Distance from EMA20 - NEW FILTER

**Purpose:** Reject extended stocks. Best entries are near moving averages.

```python
EMA20_DISTANCE_FILTER = {
    "indicator": "EMA",
    "period": 20,
    "calculation": "(current_price - EMA20) / EMA20 * 100",
    "long_criteria": {
        "min_distance": -3.0,   # Can be slightly below (pullback)
        "max_distance": 5.0,    # Not too extended above
        "optimal": [-1.0, 3.0]  # Near the MA
    },
    "short_criteria": {
        "min_distance": -5.0,
        "max_distance": 3.0,
        "optimal": [-3.0, 1.0]
    }
}
```

**Scoring:**
- Within optimal range: +10 pts
- Within acceptable range: +5 pts
- Outside range: REJECT (too extended)

**Why Critical:** A stock 15% above EMA20 may trigger Golden Cross but has poor risk/reward for entry.

---

### 1.4 MACD Momentum Direction - MODIFY EXISTING

**Purpose:** Identify early momentum shifts, not late confirmations.

```python
MACD_MOMENTUM_FILTER = {
    "indicator": "MACD",
    "fast": 12,
    "slow": 26,
    "signal": 9,
    "long_criteria": {
        "histogram_direction": "rising",  # Histogram increasing
        "histogram_bars_rising": {"min": 1, "max": 5},  # Early, not late
        "macd_vs_signal": "any"  # Don't require crossover yet
    },
    "short_criteria": {
        "histogram_direction": "falling",
        "histogram_bars_falling": {"min": 1, "max": 5},
        "macd_vs_signal": "any"
    }
}
```

**Scoring:**
- Histogram turned in last 1-2 bars: +10 pts (early)
- Histogram turned 3-5 bars ago: +5 pts (acceptable)
- Histogram turned > 5 bars ago: +0 pts (late)

**Why Critical:** Waiting for MACD crossover is too late. Histogram direction change is earlier signal.

---

## TIER 2: Pattern Quality Filters

### 2.1 Consolidation Breakout Scanner - NEW

**Purpose:** Find stocks breaking out of ranges (Al Brooks "Breakout Mode").

```python
CONSOLIDATION_BREAKOUT_FILTER = {
    "lookback_period": 20,  # days
    "calculation": {
        "range_high": "max(high, 20 days)",
        "range_low": "min(low, 20 days)",
        "range_size": "(range_high - range_low) / range_low * 100",
        "breakout_threshold": 0.5  # % above/below range
    },
    "long_criteria": {
        "condition": "close > range_high * 1.005",
        "range_size_min": 5.0,   # Minimum 5% range (meaningful)
        "range_size_max": 25.0,  # Maximum 25% (not too volatile)
        "volume_confirmation": "today_vol > 1.3 * avg_vol_20"
    },
    "short_criteria": {
        "condition": "close < range_low * 0.995",
        "range_size_min": 5.0,
        "range_size_max": 25.0,
        "volume_confirmation": "today_vol > 1.3 * avg_vol_20"
    }
}
```

**Scoring:**
- Fresh breakout (today or yesterday): +15 pts
- Breakout within 3 days: +10 pts
- Pullback to breakout level: +12 pts (retest entry)

**Why Critical:** This finds stocks STARTING moves, not stocks mid-move.

---

### 2.2 Volume Surge Filter - ENHANCE EXISTING

**Purpose:** Confirm institutional interest at inflection points.

```python
VOLUME_SURGE_FILTER = {
    "calculation": "current_volume / SMA(volume, 20)",
    "criteria": {
        "min_ratio": 1.5,       # 50% above average minimum
        "optimal_ratio": [2.0, 4.0],  # 2-4x is ideal
        "max_ratio": 8.0        # > 8x may be blow-off/capitulation
    },
    "additional_checks": {
        "price_direction_match": True,  # Volume should confirm price direction
        "consecutive_surge_days": {"max": 3}  # Not after multi-day surge
    }
}
```

**Scoring:**
- Volume 2-4x with price confirmation: +10 pts
- Volume 1.5-2x with price confirmation: +5 pts
- Volume > 5x: Flag for review (could be climax)

---

### 2.3 Relative Strength Positioning - MODIFY EXISTING

**Purpose:** Find leaders that aren't crowded, laggards that aren't capitulated.

```python
RELATIVE_STRENGTH_FILTER = {
    "benchmark": "SPY",
    "period": 63,  # ~3 months
    "long_criteria": {
        "min_rs": 55,       # Outperforming
        "max_rs": 85,       # Not extremely crowded
        "optimal": [60, 75]
    },
    "short_criteria": {
        "min_rs": 15,       # Not completely capitulated
        "max_rs": 45,       # Underperforming
        "optimal": [25, 40]
    }
}
```

**Scoring:**
- RS in optimal range: +10 pts
- RS in acceptable range: +5 pts
- RS extreme (> 85 or < 15): REJECT or flag

**Why Critical:** RS 95 stocks are crowded longs prone to mean reversion. RS 5 stocks may have fundamental issues.

---

### 2.4 Trend Day Counter - NEW

**Purpose:** Count consecutive days moving in one direction to detect exhaustion.

```python
TREND_DAY_COUNTER = {
    "calculation": "count consecutive days where close > open (up) or close < open (down)",
    "long_criteria": {
        "max_consecutive_up_days": 5,    # > 5 = exhaustion risk
        "ideal_pattern": "pullback_after_trend",  # 2-3 up, 1 down, resuming
        "reject_if": "consecutive_up_days > 7"
    },
    "short_criteria": {
        "max_consecutive_down_days": 5,
        "ideal_pattern": "bounce_after_trend",
        "reject_if": "consecutive_down_days > 7"
    }
}
```

**Scoring:**
- 2-4 consecutive days in direction: +5 pts (trend intact)
- 5-6 consecutive days: +0 pts (caution)
- > 6 consecutive days: -5 pts or REJECT (exhaustion)

---

## TIER 3: Catalyst Filters

### 3.1 Earnings Proximity - ENHANCE EXISTING

```python
EARNINGS_PROXIMITY_FILTER = {
    "source": "nasdaq_earnings_calendar",
    "long_criteria": {
        "days_to_earnings": {
            "ideal": [7, 30],      # 1-4 weeks out
            "acceptable": [5, 45],
            "reject": [0, 3]       # Too close (binary risk)
        },
        "historical_beat_rate": {"min": 60}  # > 60% beat rate
    },
    "short_criteria": {
        "days_to_earnings": {
            "ideal": [7, 30],
            "acceptable": [5, 45],
            "reject": [0, 3]
        },
        "historical_beat_rate": {"max": 50}  # < 50% beat rate
    }
}
```

**Scoring:**
- Earnings 7-30 days + good beat rate: +10 pts
- Earnings 30-45 days: +5 pts
- No earnings soon: +0 pts (neutral)
- Earnings < 5 days: Flag for binary risk warning

---

### 3.2 IV Rank Filter - NEW (For Options Strategy)

```python
IV_RANK_FILTER = {
    "calculation": "(current_IV - 52wk_low_IV) / (52wk_high_IV - 52wk_low_IV) * 100",
    "directional_plays": {
        "ideal_iv_rank": [20, 50],   # Cheap options
        "max_iv_rank": 60            # Above 60 = expensive
    },
    "premium_selling": {
        "ideal_iv_rank": [60, 90]    # High IV for selling
    }
}
```

**Scoring:**
- IV Rank 20-40 (cheap options): +10 pts for directional
- IV Rank 40-60: +5 pts
- IV Rank > 70: Flag - suggest premium selling strategies instead

---

### 3.3 Insider Activity Filter - ENHANCE EXISTING

```python
INSIDER_ACTIVITY_FILTER = {
    "lookback_days": 90,
    "long_criteria": {
        "net_activity": "buying",
        "cluster_buying": {  # Multiple insiders buying together
            "min_insiders": 2,
            "within_days": 14,
            "bonus_points": 10
        },
        "ceo_cfo_activity": {  # Weight C-suite higher
            "buying": "+5 pts",
            "selling": "flag for review"
        }
    },
    "short_criteria": {
        "net_activity": "selling",
        "cluster_selling": {
            "min_insiders": 2,
            "within_days": 14,
            "points": 10
        }
    }
}
```

**Scoring:**
- Cluster buying by C-suite: +15 pts
- Any insider buying: +5 pts
- No activity: +0 pts
- Heavy insider selling (for longs): Flag warning

---

## TIER 4: Exclusion Filters (Hard Rejects)

### 4.1 Extended Move Filter - NEW CRITICAL

```python
EXTENDED_MOVE_EXCLUSION = {
    "purpose": "Reject stocks that already made their move",
    "long_exclusions": {
        "3_month_return_max": 50,   # Reject if > +50% in 3mo
        "1_month_return_max": 30,   # Reject if > +30% in 1mo
        "distance_from_52wk_high": 5  # Reject if within 5% of 52wk high
    },
    "short_exclusions": {
        "3_month_return_min": -40,  # Reject if < -40% in 3mo
        "1_month_return_min": -25,  # Reject if < -25% in 1mo
        "distance_from_52wk_low": 5  # Reject if within 5% of 52wk low
    }
}
```

> **This is the most critical missing filter.** Prevents exhausted candidates.

---

### 4.2 Gap Exclusion Filter - NEW

```python
GAP_EXCLUSION = {
    "purpose": "Reject choppy/gappy stocks",
    "criteria": {
        "max_gap_size": 8,          # % gap in single day
        "lookback_days": 10,
        "max_gaps_in_period": 2     # No more than 2 big gaps in 10 days
    }
}
```

---

### 4.3 Volatility Minimum - NEW

```python
VOLATILITY_MINIMUM = {
    "purpose": "Reject slow-moving stocks",
    "criteria": {
        "min_atr_percent": 2.0,     # ATR as % of price must be > 2%
        "min_20day_range": 8.0      # 20-day high-low range > 8%
    }
}
```

**Calculation:**
- `ATR_percent = ATR(14) / current_price * 100`
- `range_20d = (max_20d - min_20d) / min_20d * 100`

> **This prevents slow-moving candidates** that don't offer trading opportunity.

---

## Composite Scoring System

### Revised Score Weights

```python
COMPOSITE_SCORE = {
    "total_points": 100,
    "components": {
        "momentum_quality": {
            "weight": 30,
            "factors": {
                "ADX_position": 10,
                "RSI_position": 10,
                "EMA20_distance": 5,
                "MACD_momentum": 5
            }
        },
        "pattern_quality": {
            "weight": 25,
            "factors": {
                "consolidation_breakout": 15,
                "volume_surge": 5,
                "trend_day_count": 5
            }
        },
        "relative_strength": {
            "weight": 15,
            "factors": {
                "RS_vs_SPY": 10,
                "sector_RS": 5
            }
        },
        "catalyst_quality": {
            "weight": 20,
            "factors": {
                "earnings_proximity": 8,
                "insider_activity": 7,
                "IV_rank": 5
            }
        },
        "al_brooks_pattern": {
            "weight": 10,
            "factors": {
                "pattern_type": 5,   # H2/L2 > H1/L1 > H3/L3
                "pattern_completion": 5
            }
        }
    }
}
```

---

### Score Thresholds

| Score | Label | Action |
|-------|-------|--------|
| 75-100 | STRONG CANDIDATE | High conviction trade |
| 60-74 | GOOD CANDIDATE | BUY/SHORT |
| 50-59 | WATCHLIST | WATCH |
| 0-49 | REJECT | SKIP |

---

## API Specification

### Scan Request Structure

```python
scan_market_opportunities(
    market="america",
    min_price=2.0,
    min_market_cap=1_000_000_000,
    top_n=3,
    
    # NEW PARAMETERS
    filters={
        "tier1_momentum": {
            "adx_range": [20, 40],
            "rsi_range_long": [40, 65],
            "rsi_range_short": [35, 60],
            "ema20_distance_max": 5.0,
            "macd_histogram_direction": True
        },
        "tier2_pattern": {
            "require_consolidation_breakout": True,
            "min_volume_ratio": 1.5,
            "max_consecutive_trend_days": 6
        },
        "tier3_catalyst": {
            "earnings_days_range": [7, 45],
            "iv_rank_max": 60,
            "require_insider_activity": False
        },
        "tier4_exclusions": {
            "max_3month_return_long": 50,
            "min_3month_return_short": -40,
            "max_gap_percent": 8,
            "min_atr_percent": 2.0
        }
    },
    
    scoring_weights={
        "momentum_quality": 30,
        "pattern_quality": 25,
        "relative_strength": 15,
        "catalyst_quality": 20,
        "brooks_pattern": 10
    }
)
```

### Scan Response Structure

```python
{
    "scan_metadata": {
        "timestamp": "2024-01-15T10:30:00Z",
        "stocks_scanned": 4521,
        "passed_tier1": 342,
        "passed_tier2": 87,
        "passed_tier4_exclusions": 64,
        "final_candidates": 6
    },
    "long_candidates": [
        {
            "ticker": "XXXX",
            "score": 82,
            "score_breakdown": {
                "momentum_quality": 28,
                "pattern_quality": 22,
                "relative_strength": 12,
                "catalyst_quality": 15,
                "brooks_pattern": 5
            },
            "key_signals": [
                "Consolidation breakout (Day 1)",
                "ADX 28 (trending, not exhausted)",
                "RSI 55 (room to run)",
                "Volume 2.3x average",
                "Earnings in 18 days"
            ],
            "warnings": [],
            "entry_proximity": "AT_ENTRY",
            "brooks_pattern": "HIGH_2"
        }
    ],
    "short_candidates": [...],
    "rejected_summary": {
        "exhausted_moves": 45,
        "low_volatility": 23,
        "rsi_extreme": 18,
        "extended_from_ma": 31
    }
}
```

---

## Implementation Priority

### Phase 1 (Critical - Immediate)

| Filter | Priority | Impact |
|--------|----------|--------|
| Extended Move Exclusion | P0 | Eliminates exhausted candidates |
| ADX Range Filter | P0 | Identifies trending but not exhausted |
| RSI Position Filter (modified) | P0 | Rejects overbought/oversold |
| Volatility Minimum | P0 | Eliminates slow movers |

### Phase 2 (Important - Next Sprint)

| Filter | Priority | Impact |
|--------|----------|--------|
| Consolidation Breakout | P1 | Finds inflection points |
| EMA20 Distance | P1 | Rejects extended entries |
| Trend Day Counter | P1 | Flags exhaustion risk |

### Phase 3 (Enhancement)

| Filter | Priority | Impact |
|--------|----------|--------|
| IV Rank Integration | P2 | Better options strategy matching |
| Cluster Insider Detection | P2 | Smart money confirmation |
| Earnings Proximity Scoring | P2 | Catalyst timing |

---

## Validation Test Cases

### Test Case 1: Should REJECT (Exhausted Long)
```
Stock: UP +45% in 3 months, RSI 78, ADX 52, 8 consecutive up days
Expected: REJECT (exhausted)
Reason: Fails extended move filter, RSI filter, ADX filter, trend day filter
```

### Test Case 2: Should REJECT (Slow Mover)
```
Stock: ATR 0.8% of price, 20-day range 4%, Volume ratio 0.7x
Expected: REJECT (low volatility)
Reason: Fails volatility minimum filter
```

### Test Case 3: Should ACCEPT (Ideal Long)
```
Stock: Breaking 20-day consolidation, RSI 54, ADX 31, 
       Volume 2.5x, up +12% in 3mo, earnings in 22 days
Expected: ACCEPT (score ~75-85)
Reason: Passes all filters, early-stage breakout
```

### Test Case 4: Should ACCEPT (Ideal Short)
```
Stock: Breaking below support, RSI 48, ADX 27,
       Volume 2.1x, down -8% in 3mo, insider selling
Expected: ACCEPT (score ~70-80)
Reason: Passes all filters, early breakdown
```

---

## Summary for Developers

### Core Problem
Scanner finds stocks mid-trend (late) instead of at inflection points (early).

### Critical Additions Needed

1. **ADX Indicator** - Trend strength filter (20-40 range)
2. **Extended Move Exclusion** - Reject > +50% 3mo return (longs)
3. **Volatility Minimum** - Reject ATR < 2% of price
4. **Consolidation Breakout Scanner** - Find range breakouts
5. **RSI Positioning** - Accept 40-65 (longs), reject extremes
6. **EMA20 Distance** - Reject > 5% extended
7. **Trend Day Counter** - Flag > 5 consecutive days

### Expected Outcome
Candidates with:
- Room to run (not exhausted)
- Sufficient volatility (tradeable)
- Early-stage moves (better R/R)
- Clear entry levels (near MAs or breakout zones)

---

## Quick Reference Tables

### Momentum Quality Summary

| Filter | Long Criteria | Short Criteria | Reject If |
|--------|--------------|----------------|-----------|
| ADX | 20-40 | 20-40 | < 20 or > 40 |
| RSI | 40-65 | 35-60 | > 70 or < 30 |
| EMA20 Distance | -3% to +5% | -5% to +3% | > 5% extended |
| MACD Histogram | Rising 1-5 bars | Falling 1-5 bars | > 5 bars |

### Pattern Quality Summary

| Filter | Criteria | Scoring |
|--------|----------|---------|
| Consolidation Breakout | Breaking 20-day range | +15 pts fresh |
| Volume Surge | > 1.5x average | +10 pts at 2-4x |
| RS Position | 55-85 (L) / 15-45 (S) | +10 pts optimal |
| Trend Days | < 6 consecutive | -5 pts if > 6 |

### Exclusion Filters Summary

| Filter | Long Reject | Short Reject |
|--------|-------------|--------------|
| 3-Month Return | > +50% | < -40% |
| 1-Month Return | > +30% | < -25% |
| 52-Week Proximity | Within 5% of high | Within 5% of low |
| Gap Size | > 8% in 10 days | > 8% in 10 days |
| ATR % | < 2% | < 2% |

---

## Al Brooks Pattern Reference

### LONG Patterns

| Pattern | Description | Base Prob |
|---------|-------------|-----------|
| High 1 | First pullback in uptrend | 50% |
| High 2 | Second entry long (most reliable) | 60% |
| High 3 | Third push (exhaustion risk) | 45% |
| Breakout Pullback | Test of breakout level | 55% |
| Double Bottom | Two tests of support | 55% |
| Failed Low 2 | Bear trap becomes bull signal | 65% |

### SHORT Patterns

| Pattern | Description | Base Prob |
|---------|-------------|-----------|
| Low 1 | First pullback in downtrend | 50% |
| Low 2 | Second entry short (most reliable) | 60% |
| Low 3 | Third push (exhaustion risk) | 45% |
| Failed Breakout | Bull trap becomes bear signal | 65% |
| Double Top | Two tests of resistance | 55% |
| Failed High 2 | Bull trap becomes bear signal | 65% |

### Probability Adjustments

| Factor | Adjustment |
|--------|------------|
| RSI aligned | +5% |
| ML prediction aligned | +5% |
| RS Leader/Laggard | +3% |
| Volume confirmation | +3% |
| Catalyst within 30 days | +5% |
| Conflicting signals | -5% |
| Low volume | -3% |
| Near major S/R | -5% |

---

#trading #scanner #mcp #al-brooks #mcmillan #development

*Document created for MCP development team. Based on Al Brooks Price Action Trading methodology and Lawrence McMillan's Options as a Strategic Investment.*
