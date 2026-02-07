# Scientific Entry/Exit Strategy - Implementation Plan

## Overview

This document provides the step-by-step implementation plan for integrating research-backed entry/exit strategies into the investor-agent MCP server. All methods are based on peer-reviewed research and institutional validation (see [ENTRY_EXIT_RESEARCH_FINDINGS.md](ENTRY_EXIT_RESEARCH_FINDINGS.md)).

---

## Architecture Decision

**ALL NEW CODE GOES INTO SEPARATE MODULE**: `investor_agent/entry_exit_strategy.py`

- `server.py` acts as **wrapper only** - imports and calls functions from the new module
- Keeps server.py clean and maintainable
- Sets foundation for future refactoring (breaking server.py into multiple scripts)

---

## Phase 1: Core Infrastructure (Week 1)

### 1.1 Create New Module: `investor_agent/entry_exit_strategy.py`

**New File**: `investor_agent/entry_exit_strategy.py`

**Purpose**: Contains all research-backed entry/exit strategy functions.

**Current Issue**: Existing `find_support_resistance()` in server.py returns empty lists, making all entry strategies default to current price.

**Research Backing**: K-means clustering on price extrema showed **65% profitability increase** across 8 currency pairs (2024-2025 research).

**Complete Module Structure**:

```python
from sklearn.cluster import KMeans
import numpy as np

def find_support_resistance_kmeans(
    ticker: str,
    lookback_days: int = 180,
    n_clusters: int = 12
) -> dict:
    """
    Detect support/resistance using K-means clustering on price extrema.

    Research: "Support and Resistance Detection Using K-Means Clustering"
    Result: 65% profitability increase when S/R features added to trading models
    Tested on: 8 currency pairs, 5 years of data

    Args:
        ticker: Stock symbol
        lookback_days: Historical period for analysis (default 180 days = 6 months)
        n_clusters: Number of clusters for K-means (default 12, validated in research)

    Returns:
        {
            'supports': [list of support prices],
            'resistances': [list of resistance prices],
            'current_price': float,
            'method': 'kmeans_clustering',
            'clusters_used': int,
            'validation': {
                'min_touches': 3,  # Minimum touches to validate level
                'significance_threshold': 0.01  # 1% price tolerance
            }
        }
    """
    try:
        # Get historical price data
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{lookback_days}d")

        if hist.empty:
            return {
                'supports': [],
                'resistances': [],
                'current_price': None,
                'error': 'No historical data available'
            }

        current_price = hist['Close'].iloc[-1]

        # Step 1: Identify swing highs and lows
        # Swing high: high > highs of 5 bars before and 5 bars after
        swing_highs = []
        swing_lows = []

        for i in range(5, len(hist) - 5):
            # Check if this is a swing high
            if hist['High'].iloc[i] == hist['High'].iloc[i-5:i+6].max():
                swing_highs.append(hist['High'].iloc[i])

            # Check if this is a swing low
            if hist['Low'].iloc[i] == hist['Low'].iloc[i-5:i+6].min():
                swing_lows.append(hist['Low'].iloc[i])

        # Combine all price extrema
        price_extrema = np.array(swing_highs + swing_lows)

        if len(price_extrema) < n_clusters:
            # Not enough data points, fall back to simple percentile method
            n_clusters = max(3, len(price_extrema) // 2)

        # Step 2: Apply K-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        price_extrema_reshaped = price_extrema.reshape(-1, 1)
        kmeans.fit(price_extrema_reshaped)

        # Get cluster centers (these are our S/R levels)
        sr_levels = sorted(kmeans.cluster_centers_.flatten())

        # Step 3: Validate levels by counting touches
        validated_levels = []
        for level in sr_levels:
            # Count how many times price came within 1% of this level
            tolerance = level * 0.01
            touches = 0

            for price in price_extrema:
                if abs(price - level) <= tolerance:
                    touches += 1

            # Keep levels with at least 3 touches
            if touches >= 3:
                validated_levels.append({
                    'price': float(level),
                    'touches': touches,
                    'strength': min(touches / 10.0, 1.0)  # Normalize to 0-1
                })

        # Step 4: Separate into supports and resistances
        supports = [
            level for level in validated_levels
            if level['price'] < current_price
        ]
        resistances = [
            level for level in validated_levels
            if level['price'] > current_price
        ]

        # Sort by proximity to current price
        supports = sorted(supports, key=lambda x: x['price'], reverse=True)
        resistances = sorted(resistances, key=lambda x: x['price'])

        return {
            'supports': supports[:5],  # Top 5 nearest supports
            'resistances': resistances[:5],  # Top 5 nearest resistances
            'current_price': float(current_price),
            'method': 'kmeans_clustering',
            'clusters_used': n_clusters,
            'total_swing_points': len(price_extrema),
            'validated_levels': len(validated_levels),
            'research_citation': '65% profitability increase (8 currency pairs, 2024-2025)'
        }

    except Exception as e:
        logger.error(f"K-means S/R detection failed for {ticker}: {str(e)}")
        return {
            'supports': [],
            'resistances': [],
            'current_price': None,
            'error': str(e)
        }
```

**Integration Point**: Replace calls to `find_support_resistance()` with `find_support_resistance_kmeans()` in:
- `generate_trading_signal()` (line ~17400)
- Any other functions using S/R detection

---

### 1.2 Implement ATR-Based Stop Loss Calculation

**Research Backing**: Institutional study on 500 stocks, 10 years showed **2x ATR reduces drawdown by 32%**, 3x ATR increases performance by 15% for position trading.

**New Function**:

```python
def calculate_atr_stop_loss(
    ticker: str,
    entry_price: float,
    position_type: str,
    time_frame: str = 'swing',
    atr_period: int = 14
) -> dict:
    """
    Calculate volatility-adjusted stop loss using ATR.

    Research: Institutional study (2024-2025)
    - 500 stocks, 10 years of data
    - 2x ATR: 32% reduction in max drawdown
    - 3x ATR: 15% performance increase for position trading

    Validated Multipliers:
    - Day trading: 1.5x - 2.0x ATR
    - Swing (1-2 weeks): 2.0x - 3.0x ATR
    - Position (1-3 months): 3.0x - 4.0x ATR

    Args:
        ticker: Stock symbol
        entry_price: Entry price for the position
        position_type: 'LONG' or 'SHORT'
        time_frame: 'day', 'swing', or 'position'
        atr_period: ATR calculation period (default 14)

    Returns:
        {
            'stop_price': float,
            'stop_percent': float,
            'atr_value': float,
            'atr_multiplier': float,
            'risk_per_share': float,
            'expected_benefit': str,
            'validation': {
                'stop_too_tight': bool,  # <2% is too tight
                'stop_too_wide': bool    # >15% is too wide
            }
        }
    """
    try:
        # Get ATR
        stock = yf.Ticker(ticker)
        hist = stock.history(period='90d')

        if len(hist) < atr_period + 1:
            raise ValueError(f"Insufficient data for ATR calculation (need {atr_period + 1} days)")

        # Calculate True Range
        hist['H-L'] = hist['High'] - hist['Low']
        hist['H-PC'] = abs(hist['High'] - hist['Close'].shift(1))
        hist['L-PC'] = abs(hist['Low'] - hist['Close'].shift(1))
        hist['TR'] = hist[['H-L', 'H-PC', 'L-PC']].max(axis=1)

        # Calculate ATR (simple moving average of TR)
        atr_value = hist['TR'].rolling(window=atr_period).mean().iloc[-1]

        # Select multiplier based on time frame
        multiplier_map = {
            'day': 1.5,
            'swing': 2.5,
            'position': 3.5
        }
        multiplier = multiplier_map.get(time_frame, 2.5)

        # Calculate stop loss
        if position_type == 'LONG':
            stop_price = entry_price - (atr_value * multiplier)
        elif position_type == 'SHORT':
            stop_price = entry_price + (atr_value * multiplier)
        else:
            raise ValueError(f"Invalid position_type: {position_type}")

        # Calculate metrics
        risk_per_share = abs(entry_price - stop_price)
        stop_percent = risk_per_share / entry_price

        # Validation checks
        stop_too_tight = stop_percent < 0.02  # Less than 2%
        stop_too_wide = stop_percent > 0.15   # More than 15%

        # Expected benefit based on research
        if multiplier >= 2.0:
            expected_benefit = "32% drawdown reduction (research-validated)"
        elif multiplier >= 3.0:
            expected_benefit = "15% performance increase for position trades"
        else:
            expected_benefit = "Tighter stop, may increase whipsaws"

        return {
            'stop_price': float(stop_price),
            'stop_percent': float(stop_percent),
            'atr_value': float(atr_value),
            'atr_multiplier': multiplier,
            'risk_per_share': float(risk_per_share),
            'time_frame': time_frame,
            'expected_benefit': expected_benefit,
            'validation': {
                'stop_too_tight': stop_too_tight,
                'stop_too_wide': stop_too_wide,
                'recommended': not stop_too_tight and not stop_too_wide
            },
            'research_citation': '500 stocks, 10 years: 32% drawdown reduction with 2x ATR'
        }

    except Exception as e:
        logger.error(f"ATR stop loss calculation failed for {ticker}: {str(e)}")
        return {'error': str(e)}
```

---

### 1.3 Enhanced Entry Price Logic with Multi-Factor Validation

**File**: `investor_agent/server.py`, function `generate_trading_signal()`

**Replace lines 17468-17530** (current broken entry logic) with:

```python
# ENHANCED ENTRY LOGIC - Research-backed methods
# Uses: K-means S/R (65% profit increase), MACD optimization (JFE 2025), sector rotation

def determine_entry_strategy(
    ticker: str,
    current_price: float,
    actual_direction: str,
    technical_data: dict,
    fundamental_data: dict,
    economic_context: dict = None
) -> dict:
    """
    Determine optimal entry strategy using multi-factor analysis.

    Research Integration:
    1. K-means S/R detection (65% profitability increase)
    2. MACD(17,21,15) + ADX(13) validation (JFE 2025)
    3. Sector rotation context (Fidelity/BlackRock)
    4. Volume confirmation (1.5x average)

    Returns strategic entry recommendation, not just "current price".
    """

    # Get K-means S/R levels
    sr_data = find_support_resistance_kmeans(ticker, lookback_days=180, n_clusters=12)

    if 'error' in sr_data:
        logger.warning(f"S/R detection failed for {ticker}: {sr_data['error']}")
        supports = []
        resistances = []
    else:
        supports = sr_data.get('supports', [])
        resistances = sr_data.get('resistances', [])

    # Initialize scores
    technical_score = 0.0
    entry_confidence = 0.5  # Base confidence

    # === TECHNICAL SCORING (40% weight) ===

    # Check MACD with optimized parameters (Research: JFE 2025)
    macd_data = technical_data.get('macd', {})
    if macd_data:
        # Optimized: Short=17, Long=21, Signal=15 (not traditional 12,26,9)
        # Note: Need to add optimized MACD calculation elsewhere
        macd_bullish = macd_data.get('signal') == 'bullish'
        if (actual_direction == 'LONG' and macd_bullish) or \
           (actual_direction == 'SHORT' and not macd_bullish):
            technical_score += 0.15

    # Check ADX for trend strength (ADX > 25 = trending)
    adx_value = technical_data.get('adx', {}).get('value', 0)
    if adx_value > 25:
        technical_score += 0.10  # Strong trend confirmation

    # Check volume confirmation (1.5x average)
    volume_ratio = technical_data.get('volume_ratio', 1.0)
    if volume_ratio > 1.5:
        technical_score += 0.15  # Above-average volume

    # === ENTRY PRICE DETERMINATION ===

    if actual_direction == "LONG":
        # Strategy 1: PULLBACK TO SUPPORT (preferred for LONG)
        if supports and len(supports) > 0:
            nearest_support = supports[0]  # Already sorted by proximity
            support_price = nearest_support['price']
            support_strength = nearest_support.get('strength', 0.5)
            pullback_distance = (current_price - support_price) / current_price

            # Strong support within 1-3% below current
            if 0.01 <= pullback_distance <= 0.03 and support_strength > 0.3:
                entry_price = support_price
                entry_strategy = "PULLBACK_TO_SUPPORT"
                entry_rationale = (
                    f"Wait for pullback to support at ${support_price:.2f} "
                    f"({pullback_distance*100:.1f}% below current). "
                    f"Strength: {support_strength:.0%} "
                    f"({nearest_support.get('touches', 0)} touches). "
                    f"Research: K-means S/R increases profitability by 65%."
                )
                entry_confidence += 0.2  # High confidence entry

            # Moderate support 3-5% below
            elif 0.03 < pullback_distance <= 0.05 and support_strength > 0.2:
                entry_price = support_price
                entry_strategy = "PULLBACK_TO_SUPPORT"
                entry_rationale = (
                    f"Aggressive entry: Wait for pullback to support at ${support_price:.2f} "
                    f"({pullback_distance*100:.1f}% below current). "
                    f"May require patience. Strength: {support_strength:.0%}."
                )
                entry_confidence += 0.1

            # Currently AT support (within 1%)
            elif pullback_distance < 0.01:
                entry_price = current_price
                entry_strategy = "AT_SUPPORT"
                entry_rationale = (
                    f"Enter at current price ${current_price:.2f} - "
                    f"already at validated support ${support_price:.2f}. "
                    f"Strength: {support_strength:.0%}."
                )
                entry_confidence += 0.25  # Very high confidence

            else:
                # Support too far away, check for resistance breakout
                entry_price = current_price
                entry_strategy = "CURRENT_PRICE"
                entry_rationale = (
                    f"Enter at current price ${current_price:.2f}. "
                    f"Nearest support ${support_price:.2f} is {pullback_distance*100:.1f}% away (too far for pullback entry)."
                )

        # Strategy 2: BREAKOUT ABOVE RESISTANCE
        elif resistances and len(resistances) > 0:
            nearest_resistance = resistances[0]
            resistance_price = nearest_resistance['price']
            resistance_strength = nearest_resistance.get('strength', 0.5)
            distance_to_resistance = (resistance_price - current_price) / current_price

            # Within 2% of resistance - wait for breakout
            if distance_to_resistance <= 0.02:
                entry_price = resistance_price * 1.001  # Just above resistance
                entry_strategy = "BREAKOUT_CONFIRMATION"
                entry_rationale = (
                    f"Buy on breakout above ${resistance_price:.2f} with volume confirmation. "
                    f"Current price ${current_price:.2f} is {distance_to_resistance*100:.1f}% below resistance. "
                    f"Require volume >1.5x average."
                )
                entry_confidence += 0.15

            else:
                entry_price = current_price
                entry_strategy = "CURRENT_PRICE"
                entry_rationale = (
                    f"Enter at current price ${current_price:.2f}. "
                    f"Next resistance ${resistance_price:.2f} is {distance_to_resistance*100:.1f}% away."
                )

        # Strategy 3: NO CLEAR LEVELS - use current with caution
        else:
            entry_price = current_price
            entry_strategy = "CURRENT_PRICE"
            entry_rationale = (
                f"Enter at current price ${current_price:.2f}. "
                f"No validated S/R levels identified in K-means analysis. "
                f"Consider waiting for clearer setup."
            )
            entry_confidence -= 0.1  # Lower confidence without S/R

    elif actual_direction == "SHORT":
        # Strategy 1: PULLBACK TO RESISTANCE (preferred for SHORT)
        if resistances and len(resistances) > 0:
            nearest_resistance = resistances[0]
            resistance_price = nearest_resistance['price']
            resistance_strength = nearest_resistance.get('strength', 0.5)
            pullback_distance = (resistance_price - current_price) / current_price

            # Strong resistance within 1-3% above current
            if 0.01 <= pullback_distance <= 0.03 and resistance_strength > 0.3:
                entry_price = resistance_price
                entry_strategy = "PULLBACK_TO_RESISTANCE"
                entry_rationale = (
                    f"Wait for pullback to resistance at ${resistance_price:.2f} "
                    f"({pullback_distance*100:.1f}% above current). "
                    f"Strength: {resistance_strength:.0%} "
                    f"({nearest_resistance.get('touches', 0)} touches)."
                )
                entry_confidence += 0.2

            # Currently AT resistance
            elif pullback_distance < 0.01:
                entry_price = current_price
                entry_strategy = "AT_RESISTANCE"
                entry_rationale = (
                    f"Enter short at current price ${current_price:.2f} - "
                    f"already at validated resistance ${resistance_price:.2f}. "
                    f"Strength: {resistance_strength:.0%}."
                )
                entry_confidence += 0.25

            else:
                entry_price = current_price
                entry_strategy = "CURRENT_PRICE"
                entry_rationale = (
                    f"Enter short at current price ${current_price:.2f}. "
                    f"Nearest resistance ${resistance_price:.2f} is {pullback_distance*100:.1f}% away."
                )

        # Strategy 2: BREAKDOWN BELOW SUPPORT
        elif supports and len(supports) > 0:
            nearest_support = supports[0]
            support_price = nearest_support['price']
            distance_to_support = (current_price - support_price) / current_price

            if distance_to_support <= 0.02:
                entry_price = support_price * 0.999  # Just below support
                entry_strategy = "BREAKDOWN_CONFIRMATION"
                entry_rationale = (
                    f"Short on breakdown below ${support_price:.2f} with volume confirmation. "
                    f"Current price ${current_price:.2f} is {distance_to_support*100:.1f}% above support."
                )
                entry_confidence += 0.15

            else:
                entry_price = current_price
                entry_strategy = "CURRENT_PRICE"
                entry_rationale = f"Enter short at current price ${current_price:.2f}."

        else:
            entry_price = current_price
            entry_strategy = "CURRENT_PRICE"
            entry_rationale = (
                f"Enter short at current price ${current_price:.2f}. "
                f"No validated S/R levels identified."
            )
            entry_confidence -= 0.1

    # === FUNDAMENTAL FILTER (30% weight) ===
    fundamental_score = 0.0

    pe_ratio = fundamental_data.get('pe_ratio')
    sector_pe = fundamental_data.get('sector_pe_median', 20)

    if pe_ratio and sector_pe:
        if actual_direction == "LONG":
            # LONG: prefer undervalued (P/E < sector median)
            if pe_ratio < sector_pe * 1.2:  # Within 20% of sector
                fundamental_score += 0.15
        else:
            # SHORT: prefer overvalued
            if pe_ratio > sector_pe * 1.5:  # 50% above sector
                fundamental_score += 0.15

    # Revenue growth check
    revenue_growth = fundamental_data.get('revenue_growth_yoy', 0)
    if actual_direction == "LONG" and revenue_growth > 0:
        fundamental_score += 0.10
    elif actual_direction == "SHORT" and revenue_growth < 0:
        fundamental_score += 0.10

    # FCF positive check
    fcf = fundamental_data.get('free_cash_flow', 0)
    if actual_direction == "LONG" and fcf > 0:
        fundamental_score += 0.05

    # === SECTOR/ECONOMIC CONTEXT (30% weight) ===
    macro_score = 0.0

    if economic_context:
        sector = fundamental_data.get('sector', 'Unknown')
        pmi = economic_context.get('pmi', 50)
        yield_curve = economic_context.get('yield_curve', 0)

        # Determine economic phase
        if pmi > 52 and yield_curve > 0.5:
            phase = 'early_expansion'
            favored_sectors = ['Technology', 'Financials', 'Consumer Discretionary']
        elif pmi > 50 and yield_curve > 0:
            phase = 'mid_expansion'
            favored_sectors = ['Industrials', 'Materials', 'Energy']
        else:
            phase = 'late_expansion_recession'
            favored_sectors = ['Utilities', 'Consumer Staples', 'Healthcare']

        if sector in favored_sectors:
            macro_score += 0.30
            macro_rationale = f"Sector {sector} favored in {phase} phase (PMI={pmi:.1f})"
        else:
            macro_rationale = f"Sector {sector} NOT favored in {phase} phase - reduce size"

    else:
        macro_rationale = "Economic context not available"

    # === FINAL CONFIDENCE CALCULATION ===
    total_score = technical_score + fundamental_score + macro_score
    entry_confidence = min(entry_confidence + total_score, 1.0)

    # Position size recommendation
    if entry_confidence > 0.8 and entry_strategy in ["AT_SUPPORT", "AT_RESISTANCE", "PULLBACK_TO_SUPPORT", "PULLBACK_TO_RESISTANCE"]:
        position_size_multiplier = 1.5  # Max 3% risk (vs 2% base)
    elif entry_confidence < 0.5 or entry_strategy == "CURRENT_PRICE":
        position_size_multiplier = 0.5  # Reduce to 1% risk
    else:
        position_size_multiplier = 1.0  # Normal 2% risk

    return {
        'entry_price': float(entry_price),
        'entry_strategy': entry_strategy,
        'entry_rationale': entry_rationale,
        'entry_confidence': float(entry_confidence),
        'position_size_multiplier': position_size_multiplier,
        'scores': {
            'technical': float(technical_score),
            'fundamental': float(fundamental_score),
            'macro': float(macro_score),
            'total': float(total_score)
        },
        'sr_data': {
            'supports_found': len(supports),
            'resistances_found': len(resistances),
            'method': 'kmeans_clustering'
        },
        'research_backing': [
            'K-means S/R: 65% profitability increase (2024-2025 research)',
            'MACD(17,21,15) + ADX(13): Journal of Financial Econometrics 2025',
            'Volume confirmation: 1.5x average (institutional standard)'
        ]
    }
```

---

### 1.4 Integrate into server.py (Wrapper Only)

**File**: `investor_agent/server.py`

**Changes**:

1. **Add import at top of file**:
   ```python
   # Add after existing imports
   from investor_agent.entry_exit_strategy import (
       find_support_resistance_kmeans,
       calculate_atr_stop_loss,
       determine_entry_strategy,
       calculate_profit_target
   )
   ```

2. **Modify `generate_trading_signal()` function** (around line 17400):

   Replace the broken entry logic (lines 17468-17530) with wrapper calls:

   ```python
   # === ENTRY STRATEGY (Research-backed) ===
   # Call new entry_exit_strategy module
   entry_data = determine_entry_strategy(
       ticker=ticker,
       current_price=current_price,
       actual_direction=actual_direction,
       technical_data={
           'macd': macd_data if 'macd_data' in locals() else {},
           'adx': adx_data if 'adx_data' in locals() else {},
           'volume_ratio': volume_ratio if 'volume_ratio' in locals() else 1.0
       },
       fundamental_data={
           'sector': sector if 'sector' in locals() else 'Unknown',
           'pe_ratio': pe_ratio if 'pe_ratio' in locals() else None,
           'sector_pe_median': sector_pe_median if 'sector_pe_median' in locals() else 20,
           'revenue_growth_yoy': revenue_growth if 'revenue_growth' in locals() else 0,
           'free_cash_flow': fcf if 'fcf' in locals() else 0
       },
       economic_context=None  # Phase 2: Add economic indicators
   )

   # === STOP LOSS (ATR-based) ===
   stop_loss_data = calculate_atr_stop_loss(
       ticker=ticker,
       entry_price=entry_data['entry_price'],
       position_type=actual_direction,
       time_frame='swing',
       atr_period=14
   )

   # Validate and set stop loss
   if 'error' not in stop_loss_data and stop_loss_data['validation']['recommended']:
       stop_loss = stop_loss_data['stop_price']
       stop_rationale = (
           f"ATR-based stop: ${stop_loss:.2f} "
           f"({stop_loss_data['stop_percent']*100:.1f}% risk). "
           f"{stop_loss_data['atr_multiplier']}x ATR({stop_loss_data['atr_period']}). "
           f"{stop_loss_data['expected_benefit']}"
       )
   else:
       # Fallback to percentage-based stop
       stop_loss = entry_data['entry_price'] * (0.95 if actual_direction == 'LONG' else 1.05)
       stop_rationale = "Using 5% stop (ATR calculation unavailable or out of range)"

   # === PROFIT TARGET (R:R optimized) ===
   target_data = calculate_profit_target(
       entry_price=entry_data['entry_price'],
       stop_loss=stop_loss,
       direction=actual_direction,
       resistances=entry_data['sr_data'].get('resistances', []),
       supports=entry_data['sr_data'].get('supports', [])
   )

   # === BUILD SIGNAL OUTPUT ===
   signal['entry'] = {
       'price': entry_data['entry_price'],
       'strategy': entry_data['entry_strategy'],
       'rationale': entry_data['entry_rationale'],
       'confidence': entry_data['entry_confidence'],
       'position_size_multiplier': entry_data['position_size_multiplier'],
       'research_backing': entry_data['research_backing']
   }

   signal['stop_loss'] = {
       'price': stop_loss,
       'rationale': stop_rationale,
       'atr_data': stop_loss_data if 'error' not in stop_loss_data else None
   }

   signal['profit_target'] = {
       'price': target_data['target_price'],
       'rr_ratio': target_data['rr_ratio'],
       'required_win_rate': target_data['required_win_rate'],
       'rationale': target_data['rationale'],
       'partial_exits': target_data['partial_exits']
   }

   signal['multi_factor_scores'] = entry_data['scores']
   signal['macro_context'] = entry_data.get('macro_rationale', 'Not available')
   ```

**That's it!** server.py now just imports and calls the new module. All logic is in `entry_exit_strategy.py`.

---

## Phase 2: MACD Optimization & Sector Rotation (Week 2)

### 2.1 Implement Optimized MACD Calculation

**Research**: Journal of Financial Econometrics (2025) - optimized parameters: Short=17, Long=21, Signal=15, ADX=13

**New Function**:

```python
def calculate_optimized_macd(ticker: str, period_days: int = 90) -> dict:
    """
    Calculate MACD with research-optimized parameters.

    Research: Journal of Financial Econometrics (2025)
    Traditional MACD (12,26,9) replaced with grid-search optimized:
    - Short: 17 (not 12)
    - Long: 21 (not 26)
    - Signal: 15 (not 9)
    - ADX: 13 for trend filter

    Validation: 95% confidence interval, walk-forward testing
    """
    stock = yf.Ticker(ticker)
    hist = stock.history(period=f"{period_days}d")

    if len(hist) < 50:
        return {'error': 'Insufficient data for MACD calculation'}

    # Calculate optimized MACD
    exp1 = hist['Close'].ewm(span=17, adjust=False).mean()  # Short = 17
    exp2 = hist['Close'].ewm(span=21, adjust=False).mean()  # Long = 21
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=15, adjust=False).mean()  # Signal = 15
    histogram = macd_line - signal_line

    # Calculate ADX for trend filter
    # ... (ADX calculation code)

    current_macd = macd_line.iloc[-1]
    current_signal = signal_line.iloc[-1]
    current_histogram = histogram.iloc[-1]

    # Determine signal
    if current_macd > current_signal and current_histogram > 0:
        signal_type = 'bullish'
    elif current_macd < current_signal and current_histogram < 0:
        signal_type = 'bearish'
    else:
        signal_type = 'neutral'

    return {
        'macd': float(current_macd),
        'signal': signal_type,
        'histogram': float(current_histogram),
        'parameters': {
            'short': 17,
            'long': 21,
            'signal': 15,
            'adx': 13
        },
        'research_citation': 'JFE 2025 - Grid search optimization with 95% CI'
    }
```

### 2.2 Add Sector Rotation Context

**New Function**:

```python
def get_economic_context() -> dict:
    """
    Fetch economic indicators for sector rotation.

    Indicators:
    - PMI (Purchasing Managers Index) - leading indicator
    - Yield Curve (10yr - 2yr) - recession predictor
    - Unemployment Rate - cycle position

    Data sources: FRED API, Yahoo Finance economic data
    """
    # Implementation would fetch real-time economic data
    # Placeholder for now
    return {
        'pmi': 52.3,  # > 50 = expansion
        'yield_curve': 0.8,  # Positive = normal
        'unemployment': 3.7,
        'phase': 'early_expansion',
        'favored_sectors': ['Technology', 'Financials', 'Consumer Discretionary'],
        'update_frequency': 'monthly'
    }
```

---

## Phase 3: Profit Target Optimization (Week 3)

### 3.1 Calculate R:R with S/R Levels

```python
def calculate_profit_target(
    entry_price: float,
    stop_loss: float,
    direction: str,
    resistances: list,
    supports: list
) -> dict:
    """
    Calculate profit target based on R:R optimization.

    Research: Risk/Reward must align with win rate for positive expectancy.
    - Minimum R:R of 1.5:1 to account for commission/slippage
    - Target 2:1 to 3:1 for optimal expectancy with 40-50% win rate
    """
    risk = abs(entry_price - stop_loss)

    if direction == "LONG":
        # Use nearest resistance as target
        if resistances and len(resistances) > 0:
            target_price = resistances[0]['price'] * 0.99  # Slightly below resistance
        else:
            # No resistance, use 2x risk minimum
            target_price = entry_price + (risk * 2.0)

    else:  # SHORT
        if supports and len(supports) > 0:
            target_price = supports[0]['price'] * 1.01  # Slightly above support
        else:
            target_price = entry_price - (risk * 2.0)

    reward = abs(target_price - entry_price)
    rr_ratio = reward / risk

    # Validate R:R
    if rr_ratio < 1.5:
        # Adjust target to minimum 2:1
        if direction == "LONG":
            target_price = entry_price + (risk * 2.0)
        else:
            target_price = entry_price - (risk * 2.0)
        rr_ratio = 2.0
        rationale = "Adjusted to minimum 2:1 R:R (original target too close)"
    else:
        rationale = f"Target at next S/R level, {rr_ratio:.1f}:1 R:R"

    # Calculate required win rate for breakeven
    required_win_rate = 1 / (1 + rr_ratio)

    return {
        'target_price': float(target_price),
        'rr_ratio': float(rr_ratio),
        'required_win_rate': float(required_win_rate),
        'rationale': rationale,
        'partial_exits': {
            '1R': entry_price + risk if direction == 'LONG' else entry_price - risk,
            '2R': entry_price + (risk * 2) if direction == 'LONG' else entry_price - (risk * 2),
            'final': target_price
        }
    }
```

---

## Testing & Validation

**CRITICAL TESTING RULES:**

1. **MCP TOOLS ONLY** - NEVER test with manual Python scripts or direct API calls
   - ❌ **WRONG**: `docker exec investor-agent-mcp python -c "..."`
   - ❌ **WRONG**: Writing test Python files that call Questrade API
   - ✅ **CORRECT**: Use MCP tools via Claude Code: `generate_trading_signal()`, `get_questrade_quotes()`, etc.
   - **Reason**: Manual testing consumes single-use Questrade tokens and invalidates the MCP server state

2. **Claude Code Restart Required** - After rebuilding Docker container:
   - Stop Claude Code completely (quit the application)
   - Restart Claude Code
   - Wait for MCP server reconnection
   - **Reason**: MCP connection needs to reconnect to the rebuilt container

3. **Test Strategy**: Two-phase validation
   - **Phase A**: Functionality testing (via MCP tools)
   - **Phase B**: Strategy backtesting (on historical data)

---

### Phase A: Functionality Testing (MCP Tools Only)

**After implementing Phase 1 and rebuilding container:**

1. **Rebuild container**:
   ```bash
   bash rebuild.sh
   ```

2. **STOP and RESTART Claude Code**:
   - Quit Claude Code application completely
   - Restart Claude Code
   - Wait 10-20 seconds for MCP server reconnection
   - Verify investor-agent MCP tools are available

3. **Test with MCP tools** (in Claude Code conversation):

   **Test 1: K-means S/R Detection**
   ```
   Test generate_trading_signal for AAPL with LONG direction.
   Verify the output includes:
   - entry_strategy (should NOT always be "CURRENT_PRICE")
   - supports and resistances found
   - research citations in the output
   ```

   **Test 2: ATR Stop Loss**
   ```
   Test generate_trading_signal for TSLA with SHORT direction.
   Verify stop_loss includes:
   - ATR-based calculation
   - Multiplier (2.5x for swing)
   - Expected benefit ("32% drawdown reduction")
   ```

   **Test 3: Multi-Stock Validation**
   ```
   Test generate_trading_signal for each: AAPL, SNDK, AMD, SPOT
   Direction: LONG for all
   Expected: Different entry strategies (not all CURRENT_PRICE)
   Verify confidence scores vary based on setup quality
   ```

4. **Success Criteria**:
   - At least 2 out of 4 stocks show entry strategy OTHER than "CURRENT_PRICE"
   - All stocks show ATR-based stop loss with research citations
   - Confidence scores range between 0.4 - 0.9 (not all the same)
   - S/R data shows method: "kmeans_clustering"

---

### Phase B: Strategy Backtesting

**Purpose**: Validate that research-backed methods produce statistically significant improvements on historical data.

**Backtesting Framework** (to be implemented in Phase 4):

#### B1. New MCP Tool: `backtest_entry_strategy`

```python
@mcp.tool()
async def backtest_entry_strategy(
    ticker: str,
    direction: str,
    start_date: str,  # Format: "2024-01-01"
    end_date: str,    # Format: "2024-12-31"
    strategy_type: str = "kmeans_sr",  # "kmeans_sr", "atr_stop", "combined"
    min_trades: int = 20
) -> dict:
    """
    Backtest entry/exit strategy on historical data.

    Tests the effectiveness of research-backed methods by:
    1. Generating trading signals on historical dates
    2. Simulating trades with entry, stop, and target prices
    3. Calculating win rate, R:R, expectancy, Sharpe ratio
    4. Comparing to baseline (enter at current price, 5% stop)

    Returns statistical validation of strategy performance.

    Args:
        ticker: Stock symbol to backtest
        direction: "LONG" or "SHORT"
        start_date: Backtest start date (YYYY-MM-DD)
        end_date: Backtest end date (YYYY-MM-DD)
        strategy_type: Which strategy to test
        min_trades: Minimum trades required for statistical significance

    Returns:
        {
            'ticker': str,
            'period': {'start': str, 'end': str},
            'total_trades': int,
            'win_rate': float,  # Percentage
            'avg_rr_ratio': float,
            'expectancy': float,  # Expected value per trade
            'sharpe_ratio': float,
            'max_drawdown': float,  # Percentage
            'total_return': float,  # Percentage
            'comparison_to_baseline': {
                'baseline_win_rate': float,
                'baseline_expectancy': float,
                'improvement': float  # Percentage improvement
            },
            'trade_sample': [  # First 5 trades as examples
                {
                    'date': str,
                    'entry': float,
                    'entry_strategy': str,
                    'stop': float,
                    'target': float,
                    'exit': float,
                    'pnl_percent': float,
                    'outcome': 'WIN' | 'LOSS'
                }
            ],
            'statistical_significance': {
                't_statistic': float,
                'p_value': float,
                'significant': bool  # p < 0.05
            },
            'validation': {
                'sufficient_trades': bool,  # >= min_trades
                'meets_research_claims': bool,  # Win rate improvement matches research
                'recommendation': str
            }
        }
    """
    # Implementation:
    # 1. Fetch historical data for ticker
    # 2. For each trading day, generate signal using research methods
    # 3. Simulate trade: entry, stop loss hit or target hit
    # 4. Calculate metrics
    # 5. Run t-test vs baseline
    # 6. Return comprehensive results
```

#### B2. Backtesting Test Cases

**Test Case 1: K-means S/R Entry (LONG)**
```
backtest_entry_strategy(
    ticker="AAPL",
    direction="LONG",
    start_date="2023-01-01",
    end_date="2024-12-31",
    strategy_type="kmeans_sr"
)

Expected Results (based on research):
- Win rate: 45-55% (vs 40% baseline)
- Expectancy: >0.5R per trade
- Improvement vs baseline: >20%
- Statistical significance: p < 0.05
```

**Test Case 2: ATR Stop Loss Effectiveness**
```
backtest_entry_strategy(
    ticker="TSLA",
    direction="LONG",
    start_date="2023-01-01",
    end_date="2024-12-31",
    strategy_type="atr_stop"
)

Expected Results (based on research):
- Max drawdown: 20-30% lower than baseline
- Win rate: Similar or slightly higher
- Total return: Higher due to reduced catastrophic losses
```

**Test Case 3: Combined Strategy (Entry + Stop + Target)**
```
backtest_entry_strategy(
    ticker="AMD",
    direction="LONG",
    start_date="2023-01-01",
    end_date="2024-12-31",
    strategy_type="combined"
)

Expected Results:
- Win rate: 50-60%
- R:R ratio: 2:1 to 3:1 average
- Sharpe ratio: >1.5
- Expectancy: >0.6R per trade
```

#### B3. Random Historical Date Testing

**Random Sample Validation**:
- Select 10 random historical dates within last 2 years
- Generate trading signal for AAPL, MSFT, NVDA on each date
- Track actual outcome (did entry strategy work? did stop get hit?)
- Calculate realized win rate vs predicted

**Example**:
```
Random dates: 2024-03-15, 2024-07-22, 2023-11-08, ...

For each date:
1. Generate signal with K-means S/R entry
2. Track if actual price reached entry point
3. Track if stop was hit or target was reached
4. Calculate P&L

Aggregate:
- Realized win rate: X%
- Predicted win rate: Y%
- Delta: Should be <10% for valid strategy
```

#### B4. Backtesting as Standard Measure

**NEW REQUIREMENT**: Every recommendation must include backtesting validation.

**Modified MCP Tool Output Format**:
```json
{
  "recommendation": {
    "entry_price": 147.50,
    "entry_strategy": "PULLBACK_TO_SUPPORT",
    "stop_loss": 145.20,
    "profit_target": 152.00
  },
  "research_backing": [
    "K-means S/R: 65% profitability increase"
  ],
  "backtesting_validation": {
    "ticker": "AAPL",
    "backtest_period": "2023-01-01 to 2024-12-31",
    "historical_trades": 47,
    "win_rate": 53.2,
    "expectancy": 0.62,
    "sharpe_ratio": 1.8,
    "improvement_vs_baseline": "28% better expectancy",
    "statistically_significant": true,
    "p_value": 0.023
  },
  "confidence": {
    "score": 0.78,
    "rationale": "High confidence - backtesting validates research claims"
  }
}
```

---

### Unit Tests (Optional - For Development Only)

Create `tests/test_entry_exit.py` for local development testing:

```python
import pytest
from investor_agent.server import (
    find_support_resistance_kmeans,
    calculate_atr_stop_loss,
    determine_entry_strategy
)

def test_kmeans_sr_detection():
    """Test K-means S/R detection returns valid levels."""
    result = find_support_resistance_kmeans('AAPL', lookback_days=180)

    assert 'supports' in result
    assert 'resistances' in result
    assert 'current_price' in result
    assert result['method'] == 'kmeans_clustering'

    # Should have at least some levels for liquid stock
    assert len(result['supports']) + len(result['resistances']) > 0

def test_atr_stop_loss():
    """Test ATR stop loss calculation with different time frames."""
    result_swing = calculate_atr_stop_loss('AAPL', 150.0, 'LONG', 'swing')

    assert 'stop_price' in result
    assert result['stop_price'] < 150.0  # LONG stop should be below entry
    assert result['atr_multiplier'] == 2.5  # Swing default

    # Validate stop isn't too tight or wide
    assert 0.02 <= result['stop_percent'] <= 0.15

def test_entry_strategy_with_sr():
    """Test entry strategy uses S/R levels, not just current price."""
    # Mock data
    technical_data = {
        'macd': {'signal': 'bullish'},
        'adx': {'value': 30},
        'volume_ratio': 1.8
    }
    fundamental_data = {
        'sector': 'Technology',
        'pe_ratio': 25,
        'sector_pe_median': 30
    }

    result = determine_entry_strategy(
        ticker='AAPL',
        current_price=150.0,
        actual_direction='LONG',
        technical_data=technical_data,
        fundamental_data=fundamental_data
    )

    assert 'entry_strategy' in result
    assert result['entry_strategy'] != 'CURRENT_PRICE' or 'no clear' in result['entry_rationale'].lower()
    assert 'research_backing' in result
```

**NOTE**: These unit tests are for development only. DO NOT run pytest inside Docker container during normal operations as it may consume Questrade tokens.

---

## Deployment Checklist

- [ ] Phase 1 functions implemented and tested
- [ ] K-means S/R returns non-empty levels for liquid stocks
- [ ] ATR stop loss calculates correctly for all time frames
- [ ] Entry strategy shows varied strategies (not all CURRENT_PRICE)
- [ ] Unit tests passing
- [ ] Integration test shows research citations
- [ ] Docker container rebuilt with changes
- [ ] User validation on AAPL, SNDK, AMD, SPOT

---

## Success Criteria

**After implementation, a trading signal should show**:

1. **Entry Strategy**: One of PULLBACK_TO_SUPPORT, AT_SUPPORT, BREAKOUT_CONFIRMATION, PULLBACK_TO_RESISTANCE, AT_RESISTANCE, BREAKDOWN_CONFIRMATION, or CURRENT_PRICE (with rationale if no clear levels)

2. **Stop Loss**: ATR-based with multiplier and expected benefit ("32% drawdown reduction")

3. **Profit Target**: R:R ratio between 1.5:1 and 4:1, with required win rate

4. **Confidence Score**: Multi-factor (technical + fundamental + macro) between 0-1

5. **Research Citations**: Every component cites the research backing it

**Example Output**:
```json
{
  "entry": {
    "entry_price": 147.50,
    "entry_strategy": "PULLBACK_TO_SUPPORT",
    "entry_rationale": "Wait for pullback to support at $147.50 (1.7% below current). Strength: 60% (5 touches). Research: K-means S/R increases profitability by 65%.",
    "entry_confidence": 0.78,
    "position_size_multiplier": 1.5,
    "research_backing": [
      "K-means S/R: 65% profitability increase",
      "MACD(17,21,15) + ADX(13): JFE 2025"
    ]
  },
  "stop_loss": {
    "price": 145.20,
    "rationale": "ATR-based stop: $145.20 (1.6% risk). 2.5x ATR(14). Expected benefit: 32% drawdown reduction (research-validated)",
    "atr_data": {
      "atr_multiplier": 2.5,
      "expected_benefit": "32% drawdown reduction"
    }
  },
  "profit_target": {
    "target_price": 152.00,
    "rr_ratio": 2.0,
    "required_win_rate": 0.33
  }
}
```

---

## References

All implementation details based on research documented in:
- [ENTRY_EXIT_RESEARCH_FINDINGS.md](ENTRY_EXIT_RESEARCH_FINDINGS.md)

Research citations available for verification.
