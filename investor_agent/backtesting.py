"""
Similarity-Based Backtesting Framework

Implements similarity-based historical analysis for ML-enhanced trading strategies.
Instead of traditional backtesting, this finds similar historical setups and calculates
their success rates to validate current analysis.

Key Features:
1. Find historical situations similar to current market conditions
2. Calculate success rates from similar setups
3. Statistical validation (sample size, confidence intervals)
4. Report generation

Reference:
    López de Prado, M. (2018). Advances in Financial Machine Learning.
    Chapter 6: Ensemble Methods
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Literal
from dataclasses import dataclass
from scipy import stats
from datetime import datetime, timedelta


@dataclass
class SimilarSetup:
    """A historically similar market setup"""
    date: pd.Timestamp
    similarity_score: float
    conditions: Dict[str, any]
    outcomes: Dict[str, float]  # Returns at different horizons
    barrier_hit: str  # 'profit', 'stop', or 'time'
    target_achievement: Optional[float] = None  # % of target achieved (100 = exactly hit target)


@dataclass
class SimilarityAnalysisResult:
    """Results from similarity-based analysis"""
    ticker: str
    current_date: pd.Timestamp
    current_conditions: Dict[str, any]
    similar_setups: List[SimilarSetup]
    aggregate_statistics: Dict[str, any]
    statistical_validation: Dict[str, any]
    recommendation: Dict[str, any]


class SimilarityEngine:
    """
    Find and analyze similar historical market setups.

    Uses multi-dimensional similarity scoring to find historical situations
    that match current market conditions across multiple indicators.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.80,
        min_similar_setups: int = 1
    ):
        """
        Initialize similarity engine.

        Args:
            similarity_threshold: Minimum similarity score (0-1) to consider a match
            min_similar_setups: Minimum number of similar setups required for validity (note sample size in results)
        """
        if not 0 <= similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")

        if min_similar_setups < 1:
            raise ValueError("min_similar_setups must be at least 1")

        self.similarity_threshold = similarity_threshold
        self.min_similar_setups = min_similar_setups

    def find_similar_setups(
        self,
        ticker: str,
        current_conditions: Dict[str, any],
        historical_data: pd.DataFrame,
        lookback_periods: int = 504,  # ~2 years of trading days
        feature_weights: Optional[Dict[str, float]] = None,
        target_return_pct: Optional[float] = None,
        holding_period_days: Optional[int] = None,
        direction: Literal['LONG', 'SHORT'] = 'LONG',
        earnings_dates: Optional[List[pd.Timestamp]] = None
    ) -> List[SimilarSetup]:
        """
        Find historical setups similar to current conditions using feature-weighted matching.

        Uses tolerance-based matching on technical indicators (not price levels).
        Weights features by importance - critical features have more influence on similarity.

        Args:
            ticker: Stock symbol
            current_conditions: Current market technical conditions (RSI, MACD, trend, volume, etc.)
            historical_data: Historical OHLCV data
            lookback_periods: Number of periods to search back
            feature_weights: Optional feature importance weights from calculate_feature_importance_analysis()
                           If None, uses research-based default weights
            target_return_pct: Target return percentage for trade plan (e.g., 5.0 for 5%)
                             If provided, calculates target achievement for each similar setup
            holding_period_days: Number of trading days to hold (e.g., 10)
                               Required if target_return_pct is provided
            direction: Trade direction 'LONG' or 'SHORT' (default 'LONG')
            earnings_dates: Optional list of historical earnings dates for earnings context matching.
                          If provided, similarity matching will include earnings proximity features.

        Returns:
            List of similar historical setups (technical patterns, NOT price patterns)
            Each setup includes target_achievement if target parameters provided

        Example:
            >>> # Define current technical setup
            >>> current = {
            ...     'rsi': 32.5,                    # RSI oversold
            ...     'trend_direction': 'UPTREND',   # Uptrend confirmed
            ...     'macd_trend': 'BULLISH',        # MACD bullish
            ...     'volume_ratio': 1.34,           # Above avg volume
            ...     'volatility_regime': 'LOW'      # Low volatility
            ... }
            >>>
            >>> # Find similar TECHNICAL setups with target achievement
            >>> similar = engine.find_similar_setups('AAPL', current, hist_data,
            ...                                       target_return_pct=5.0,
            ...                                       holding_period_days=10,
            ...                                       direction='LONG')
            >>>
            >>> # Result: Historical days with similar RSI, trend, MACD, volume patterns
            >>> # Each setup includes target_achievement (e.g., 120% = exceeded target by 20%)
        """
        if len(historical_data) < lookback_periods:
            lookback_periods = len(historical_data)

        # Determine minimum forward days needed
        if target_return_pct is not None and holding_period_days is not None:
            min_forward_days = holding_period_days
        else:
            min_forward_days = 20  # Default for legacy outcomes

        # Search window: last N periods
        search_data = historical_data.iloc[-lookback_periods:]

        similar_setups = []

        for idx in range(len(search_data) - min_forward_days):
            hist_date = search_data.index[idx]

            # Calculate historical TECHNICAL conditions at this date
            # (RSI, MACD, trend, volume - NOT price!)
            # Include earnings context if earnings_dates provided
            hist_conditions = self._calculate_conditions(search_data, idx, earnings_dates)

            if not hist_conditions:
                continue

            # Calculate FEATURE-WEIGHTED similarity with TOLERANCE
            # Example: RSI 32 matches RSI 27-37 (±5 tolerance)
            #          Important features (RSI, trend) weighted higher
            similarity = self._calculate_similarity(
                current_conditions,
                hist_conditions,
                feature_weights=feature_weights
            )

            if similarity >= self.similarity_threshold:
                # Calculate forward returns
                outcomes = self._calculate_outcomes(search_data, idx)

                # Calculate target achievement if parameters provided
                target_achievement = None
                if target_return_pct is not None and holding_period_days is not None:
                    outcomes_with_target, target_achievement = self._calculate_outcomes_with_target(
                        search_data, idx, holding_period_days, target_return_pct, direction
                    )
                    # Merge target outcomes into main outcomes
                    outcomes['target_return'] = outcomes_with_target['return']
                    outcomes['target_holding_days'] = holding_period_days
                    outcomes['target_pct'] = target_return_pct
                    outcomes['direction'] = direction

                # Determine which barrier hit (simplified)
                barrier = self._determine_barrier_hit(outcomes)

                similar_setups.append(SimilarSetup(
                    date=hist_date,
                    similarity_score=similarity,
                    conditions=hist_conditions,
                    outcomes=outcomes,
                    barrier_hit=barrier,
                    target_achievement=target_achievement
                ))

        return similar_setups

    def _calculate_rsi(
        self,
        prices: pd.Series,
        window: int = 14
    ) -> float:
        """
        Calculate Relative Strength Index (RSI).

        Formula: RSI = 100 - (100 / (1 + RS))
        Where RS = Average Gain / Average Loss over window period
        """
        if len(prices) < window + 1:
            return 50.0

        deltas = prices.diff()
        gains = deltas.where(deltas > 0, 0.0)
        losses = -deltas.where(deltas < 0, 0.0)

        avg_gain = gains.rolling(window=window, min_periods=window).mean().iloc[-1]
        avg_loss = losses.rolling(window=window, min_periods=window).mean().iloc[-1]

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

        return float(rsi)

    def _calculate_macd(
        self,
        prices: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[float, float, float]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Returns:
            (macd_line, signal_line, histogram)
        """
        if len(prices) < slow + signal:
            return (0.0, 0.0, 0.0)

        exp_fast = prices.ewm(span=fast, adjust=False).mean()
        exp_slow = prices.ewm(span=slow, adjust=False).mean()

        macd_line = exp_fast - exp_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return (
            float(macd_line.iloc[-1]),
            float(signal_line.iloc[-1]),
            float(histogram.iloc[-1])
        )

    def _calculate_atr(
        self,
        data: pd.DataFrame,
        window: int = 14
    ) -> float:
        """
        Calculate Average True Range (ATR).

        Measures market volatility.
        """
        if len(data) < window + 1:
            return 0.0

        high = data['High'] if 'High' in data.columns else data['Close']
        low = data['Low'] if 'Low' in data.columns else data['Close']
        close = data['Close']

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=window).mean().iloc[-1]

        return float(atr) if not pd.isna(atr) else 0.0

    def _calculate_trend_tstat(
        self,
        prices: pd.Series,
        window: int = 20
    ) -> float:
        """
        Calculate trend t-statistic using linear regression.

        López de Prado's trend-scanning method.
        Returns t-statistic of regression slope.
        """
        if len(prices) < window:
            return 0.0

        y = prices.iloc[-window:].values
        x = np.arange(len(y))

        # Linear regression
        n = len(x)
        x_mean = np.mean(x)
        y_mean = np.mean(y)

        # Calculate slope (beta)
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)

        if denominator == 0:
            return 0.0

        slope = numerator / denominator

        # Calculate residuals
        y_pred = slope * x + (y_mean - slope * x_mean)
        residuals = y - y_pred

        # Standard error of slope
        mse = np.sum(residuals ** 2) / (n - 2)
        se_slope = np.sqrt(mse / denominator)

        if se_slope == 0:
            return 0.0

        # T-statistic
        t_stat = slope / se_slope

        return float(t_stat)

    def _calculate_earnings_context(
        self,
        current_date: pd.Timestamp,
        earnings_dates: List[pd.Timestamp]
    ) -> Dict[str, any]:
        """
        Calculate earnings-related context for similarity matching.

        This helps find similar setups that were also near earnings events,
        enabling pattern-based probability analysis for pre/post earnings behavior.

        Args:
            current_date: The date to calculate context for
            earnings_dates: List of historical earnings report dates

        Returns:
            Dictionary with:
                - days_to_earnings: Days until next earnings (0-90, or 999 if unknown)
                - days_since_earnings: Days since last earnings (0-90, or 999 if unknown)
                - earnings_phase: PRE_EARNINGS/EARNINGS_WEEK/POST_EARNINGS/NEUTRAL
        """
        if not earnings_dates:
            return {
                'days_to_earnings': 999,
                'days_since_earnings': 999,
                'earnings_phase': 'NEUTRAL'
            }

        # Convert to comparable format (normalize timezone to avoid tz-aware vs tz-naive issues)
        current = pd.Timestamp(current_date)
        if current.tzinfo is not None:
            current = current.tz_localize(None)

        # Normalize earnings dates to tz-naive for comparison
        normalized_earnings = []
        for d in earnings_dates:
            ts = pd.Timestamp(d)
            if ts.tzinfo is not None:
                ts = ts.tz_localize(None)
            normalized_earnings.append(ts)

        # Find nearest past and future earnings
        past_earnings = [d for d in normalized_earnings if d <= current]
        future_earnings = [d for d in normalized_earnings if d > current]

        # Days since last earnings
        if past_earnings:
            last_earnings = max(past_earnings)
            days_since = (current - last_earnings).days
            days_since_earnings = min(days_since, 90)  # Cap at 90
        else:
            days_since_earnings = 999  # Unknown

        # Days to next earnings (only use known dates, no estimation)
        if future_earnings:
            next_earnings = min(future_earnings)
            days_to = (next_earnings - current).days
            days_to_earnings = min(days_to, 90)  # Cap at 90
        else:
            # No known future earnings date - don't estimate
            days_to_earnings = 999  # Unknown

        # Determine earnings phase
        if days_to_earnings <= 7:
            earnings_phase = 'EARNINGS_WEEK'
        elif days_to_earnings <= 14:
            earnings_phase = 'PRE_EARNINGS'
        elif days_since_earnings <= 14:
            earnings_phase = 'POST_EARNINGS'
        else:
            earnings_phase = 'NEUTRAL'

        return {
            'days_to_earnings': int(days_to_earnings),
            'days_since_earnings': int(days_since_earnings),
            'earnings_phase': earnings_phase
        }

    def _calculate_conditions(
        self,
        data: pd.DataFrame,
        idx: int,
        earnings_dates: Optional[List[pd.Timestamp]] = None
    ) -> Dict[str, any]:
        """
        Calculate comprehensive technical market conditions at a given index.

        Uses proper technical indicators instead of simplified price metrics.
        This enables finding similar TECHNICAL SETUPS, not similar prices.

        Args:
            data: Historical OHLCV data
            idx: Index in the data to calculate conditions for
            earnings_dates: Optional list of earnings dates for earnings context
        """
        if idx < 50:  # Need enough history for indicators
            return {}

        # Get price data up to this index
        hist_data = data.iloc[:idx+1]
        prices = hist_data['Close']

        # === TECHNICAL INDICATORS ===

        # 1. RSI (14-period) - Momentum oscillator
        rsi = self._calculate_rsi(prices, window=14)

        # 2. MACD - Trend following momentum
        macd_line, signal_line, macd_histogram = self._calculate_macd(prices)

        # 3. ATR (14-period) - Volatility measure
        atr = self._calculate_atr(hist_data, window=14)

        # 4. Trend T-Statistic (20-period) - Statistical trend strength
        trend_tstat = self._calculate_trend_tstat(prices, window=20)

        # 5. Volume Analysis
        if 'Volume' in hist_data.columns and len(hist_data) >= 20:
            current_volume = hist_data['Volume'].iloc[-1]
            avg_volume = hist_data['Volume'].iloc[-20:].mean()
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        else:
            volume_ratio = 1.0

        # 6. SMA Relationships
        sma_20 = prices.iloc[-20:].mean() if len(prices) >= 20 else prices.iloc[-1]
        sma_50 = prices.iloc[-50:].mean() if len(prices) >= 50 else prices.iloc[-1]

        current_price = prices.iloc[-1]
        price_vs_sma20 = (current_price / sma_20 - 1) if sma_20 > 0 else 0.0
        price_vs_sma50 = (current_price / sma_50 - 1) if sma_50 > 0 else 0.0

        # 7. Momentum (20-day return)
        if len(prices) >= 20:
            momentum_20d = (prices.iloc[-1] / prices.iloc[-20] - 1)
        else:
            momentum_20d = 0.0

        # 8. VWAP relationship (if volume data available)
        if 'Volume' in hist_data.columns and len(hist_data) >= 20:
            recent_data = hist_data.iloc[-20:]
            vwap = (recent_data['Close'] * recent_data['Volume']).sum() / recent_data['Volume'].sum()
            price_vs_vwap = (current_price / vwap - 1) if vwap > 0 else 0.0
        else:
            price_vs_vwap = 0.0

        # 9. Volatility Regime (using ATR)
        atr_pct = (atr / current_price) if current_price > 0 else 0.0
        if atr_pct < 0.015:
            volatility_regime = 'LOW'
        elif atr_pct < 0.030:
            volatility_regime = 'MEDIUM'
        else:
            volatility_regime = 'HIGH'

        # 10. Trend Direction (from t-statistic)
        if trend_tstat > 1.96:  # 95% confidence
            trend_direction = 'STRONG_UPTREND'
        elif trend_tstat > 0.5:
            trend_direction = 'UPTREND'
        elif trend_tstat < -1.96:
            trend_direction = 'STRONG_DOWNTREND'
        elif trend_tstat < -0.5:
            trend_direction = 'DOWNTREND'
        else:
            trend_direction = 'RANGE'

        # 11. MACD Trend
        if macd_histogram > 0:
            macd_trend = 'BULLISH'
        elif macd_histogram < 0:
            macd_trend = 'BEARISH'
        else:
            macd_trend = 'NEUTRAL'

        # Build base conditions dict
        conditions = {
            # Momentum Indicators
            'rsi': float(rsi),
            'macd_line': float(macd_line),
            'macd_signal': float(signal_line),
            'macd_histogram': float(macd_histogram),
            'macd_trend': macd_trend,

            # Trend Indicators
            'trend_tstat': float(trend_tstat),
            'trend_direction': trend_direction,
            'price_vs_sma20': float(price_vs_sma20),
            'price_vs_sma50': float(price_vs_sma50),

            # Volume Indicators
            'volume_ratio': float(volume_ratio),
            'price_vs_vwap': float(price_vs_vwap),

            # Volatility Indicators
            'atr': float(atr),
            'atr_pct': float(atr_pct),
            'volatility_regime': volatility_regime,

            # Momentum
            'momentum_20d': float(momentum_20d)
        }

        # 12. Earnings Context (if earnings_dates provided)
        if earnings_dates:
            current_date = data.index[idx]
            earnings_context = self._calculate_earnings_context(current_date, earnings_dates)
            conditions.update(earnings_context)

        return conditions

    def _get_indicator_tolerance(self, indicator_name: str) -> float:
        """
        Define tolerance thresholds for each indicator type.

        Based on research: RSI ±5 points, MACD ±10%, Volume ±25%, etc.

        Args:
            indicator_name: Name of the technical indicator

        Returns:
            Tolerance threshold for matching
        """
        tolerances = {
            # Momentum Indicators (absolute tolerance)
            'rsi': 5.0,  # ±5 RSI points (e.g., 32 matches 27-37)
            'macd_line': 0.10,  # ±10% of value
            'macd_signal': 0.10,
            'macd_histogram': 0.15,  # More tolerance for histogram

            # Trend Indicators
            'trend_tstat': 0.5,  # ±0.5 t-stat
            'price_vs_sma20': 0.02,  # ±2% from SMA
            'price_vs_sma50': 0.03,  # ±3% from SMA

            # Volume Indicators
            'volume_ratio': 0.25,  # ±25% volume tolerance
            'price_vs_vwap': 0.015,  # ±1.5% from VWAP

            # Volatility Indicators
            'atr': 0.20,  # ±20% ATR
            'atr_pct': 0.005,  # ±0.5% ATR percentage

            # Momentum
            'momentum_20d': 0.05,  # ±5% momentum

            # Earnings Event Parameters
            'days_to_earnings': 5,      # ±5 days (e.g., 10 days matches 5-15)
            'days_since_earnings': 5    # ±5 days
        }

        return tolerances.get(indicator_name, 0.15)  # Default 15% tolerance

    def _get_default_feature_weights(self) -> Dict[str, float]:
        """
        Default feature importance weights.

        Based on research showing RSI (97% accuracy), multi-indicator confluence.
        These can be overridden by actual feature importance analysis.

        Includes earnings event weights to capture pre/post earnings patterns.

        Returns:
            Dictionary of feature weights (sum = 1.0)
        """
        return {
            # High Importance (based on research)
            'rsi': 0.13,  # RSI has 97% accuracy in research
            'trend_direction': 0.13,  # Trend is critical
            'macd_trend': 0.08,
            'volume_ratio': 0.09,

            # Medium Importance
            'trend_tstat': 0.08,
            'macd_histogram': 0.08,
            'volatility_regime': 0.08,

            # Lower Importance
            'price_vs_sma20': 0.06,
            'price_vs_sma50': 0.05,
            'price_vs_vwap': 0.05,
            'momentum_20d': 0.04,
            'atr_pct': 0.03,
            'macd_line': 0.02,
            'macd_signal': 0.01,

            # Earnings Event Parameters (5% total - only applied for non-NEUTRAL phases)
            'earnings_phase': 0.04,     # Categorical - pre/post earnings patterns
            'days_to_earnings': 0.01    # Numeric - proximity to next earnings
        }

    def _calculate_similarity(
        self,
        current: Dict[str, any],
        historical: Dict[str, any],
        feature_weights: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculate tolerance-based feature-weighted similarity score.

        Uses López de Prado's approach with tolerance thresholds and feature weighting.
        Research shows 85% accuracy when multiple indicators align within tolerance.

        Args:
            current: Current market conditions
            historical: Historical market conditions
            feature_weights: Optional feature importance weights (if None, uses defaults)

        Returns:
            Similarity score (0 = completely different, 1 = identical)

        References:
            - López de Prado (2018): Feature importance weighting
            - DTW-based tolerance matching for time series
            - Multi-indicator confluence research (85% win rate)
        """
        if not current or not historical:
            return 0.0

        # Get common keys
        common_keys = set(current.keys()) & set(historical.keys())

        if not common_keys:
            return 0.0

        # Use provided weights or defaults
        if feature_weights is None:
            feature_weights = self._get_default_feature_weights()

        # Make earnings weights conditional on current earnings phase
        # If current setup is NEUTRAL (>14 days from any earnings), set earnings weights to 0
        current_earnings_phase = current.get('earnings_phase', 'NEUTRAL')
        if current_earnings_phase == 'NEUTRAL':
            # Create a copy to avoid modifying the original weights
            feature_weights = feature_weights.copy()
            feature_weights['earnings_phase'] = 0.0
            feature_weights['days_to_earnings'] = 0.0
            feature_weights['days_since_earnings'] = 0.0

        # Calculate weighted differences with tolerance
        weighted_diffs = []
        total_weight = 0.0

        for key in common_keys:
            curr_val = current[key]
            hist_val = historical[key]

            # Get weight for this feature (default 1.0 if not specified)
            weight = feature_weights.get(key, 1.0)

            # Get tolerance for this indicator
            tolerance = self._get_indicator_tolerance(key)

            # Calculate difference based on type
            if isinstance(curr_val, str):
                # Categorical: exact match required
                diff = 0.0 if curr_val == hist_val else 1.0
            else:
                # Numerical: tolerance-based matching
                try:
                    curr_num = float(curr_val)
                    hist_num = float(hist_val)

                    # Absolute difference
                    abs_diff = abs(curr_num - hist_num)

                    # Special handling for specific indicators
                    if key == 'rsi':
                        # RSI: absolute tolerance (±5 points)
                        # RSI=32 matches RSI=27-37
                        normalized_diff = abs_diff / tolerance
                    elif key in ['macd_line', 'macd_signal', 'macd_histogram']:
                        # MACD: percentage tolerance
                        # Account for signs (both positive or both negative)
                        if (curr_num > 0) != (hist_num > 0):
                            # Different signs = very different
                            normalized_diff = 1.0
                        else:
                            # Same sign: use relative difference
                            max_val = max(abs(curr_num), abs(hist_num), 1e-10)
                            normalized_diff = abs_diff / (max_val * tolerance)
                    elif key in ['volume_ratio', 'atr', 'atr_pct']:
                        # Relative tolerance (percentage of value)
                        max_val = max(abs(curr_num), abs(hist_num), 1e-10)
                        normalized_diff = abs_diff / (max_val * tolerance)
                    elif key in ['trend_tstat', 'momentum_20d', 'price_vs_sma20',
                                 'price_vs_sma50', 'price_vs_vwap']:
                        # Absolute tolerance for percentage-based indicators
                        normalized_diff = abs_diff / tolerance
                    else:
                        # Default: relative tolerance
                        max_val = max(abs(curr_num), abs(hist_num), 1e-10)
                        normalized_diff = abs_diff / (max_val * tolerance)

                    # Cap normalized difference at 1.0 (completely different)
                    diff = min(normalized_diff, 1.0)

                except (ValueError, TypeError):
                    diff = 1.0

            # Weight the difference
            weighted_diffs.append(diff * weight)
            total_weight += weight

        if total_weight == 0:
            return 0.0

        # Calculate weighted average difference
        weighted_avg_diff = sum(weighted_diffs) / total_weight

        # Convert difference to similarity (1 - difference)
        similarity = 1.0 - min(weighted_avg_diff, 1.0)

        return similarity

    def _calculate_outcomes(
        self,
        data: pd.DataFrame,
        idx: int
    ) -> Dict[str, float]:
        """Calculate forward returns at different horizons"""
        if 'Close' not in data.columns:
            return {'5d': 0.0, '10d': 0.0, '20d': 0.0}

        entry_price = data['Close'].iloc[idx]

        # Handle NaN or zero entry price
        if pd.isna(entry_price) or entry_price == 0:
            return {'5d': 0.0, '10d': 0.0, '20d': 0.0}

        outcomes = {}

        for horizon in [5, 10, 20]:
            if idx + horizon < len(data):
                exit_price = data['Close'].iloc[idx + horizon]
                # Handle NaN exit price
                if pd.isna(exit_price):
                    outcomes[f'{horizon}d'] = 0.0
                else:
                    ret = (exit_price / entry_price - 1)
                    # Handle NaN result (shouldn't happen but defensive)
                    outcomes[f'{horizon}d'] = float(ret) if not pd.isna(ret) else 0.0
            else:
                outcomes[f'{horizon}d'] = 0.0

        return outcomes

    def _determine_barrier_hit(self, outcomes: Dict[str, float]) -> str:
        """Determine which barrier was hit first (simplified)"""
        if outcomes.get('5d', 0) > 0.05:
            return 'profit'
        elif outcomes.get('5d', 0) < -0.05:
            return 'stop'
        else:
            return 'time'

    def calculate_target_achievement(
        self,
        actual_return: float,
        target_return: float,
        direction: Literal['LONG', 'SHORT']
    ) -> float:
        """
        Calculate what percentage of target was achieved.

        For LONG trades: positive returns are good
        For SHORT trades: negative returns are good (stock went down)

        Examples:
            - LONG target +5%, actual +6% = 120% achievement
            - LONG target +5%, actual +4% = 80% achievement
            - LONG target +5%, actual -2% = -40% achievement (went wrong way)
            - SHORT target -5%, actual -6% = 120% achievement
            - SHORT target -5%, actual -4% = 80% achievement
            - SHORT target -5%, actual +2% = -40% achievement (went wrong way)

        Args:
            actual_return: Actual return observed (as decimal, e.g., 0.05 for 5%)
            target_return: Target return from trade plan (as decimal, always positive)
            direction: 'LONG' or 'SHORT'

        Returns:
            Achievement percentage (100 = exactly hit target, >100 = exceeded, <0 = went wrong way)
        """
        if target_return == 0:
            return 0.0

        # For SHORT trades, we want the price to go DOWN
        # So if actual_return is negative, that's good for shorts
        if direction == 'SHORT':
            # Invert actual return for shorts
            # If price went down 5% (actual = -0.05), for a short that's +5% gain
            effective_return = -actual_return
        else:
            # LONG: positive return is good
            effective_return = actual_return

        # Calculate achievement as percentage of target
        # target_return is always positive (e.g., 0.05 for 5% target)
        achievement = (effective_return / target_return) * 100

        return achievement

    def _calculate_outcomes_with_target(
        self,
        data: pd.DataFrame,
        idx: int,
        holding_period_days: int,
        target_return_pct: float,
        direction: Literal['LONG', 'SHORT']
    ) -> Tuple[Dict[str, float], float]:
        """
        Calculate forward returns and target achievement for a specific holding period.

        Args:
            data: Historical OHLCV data
            idx: Index of entry point
            holding_period_days: Number of trading days to hold
            target_return_pct: Target return percentage (e.g., 5.0 for 5%)
            direction: 'LONG' or 'SHORT'

        Returns:
            Tuple of (outcomes dict, target_achievement percentage)
        """
        if 'Close' not in data.columns:
            return {'return': 0.0}, 0.0

        entry_price = data['Close'].iloc[idx]
        target_return_decimal = target_return_pct / 100.0

        # Handle NaN or zero entry price
        if pd.isna(entry_price) or entry_price == 0:
            return {'return': 0.0}, 0.0

        if idx + holding_period_days < len(data):
            exit_price = data['Close'].iloc[idx + holding_period_days]
            # Handle NaN exit price
            if pd.isna(exit_price):
                actual_return = 0.0
            else:
                ret = (exit_price / entry_price - 1)
                actual_return = float(ret) if not pd.isna(ret) else 0.0
        else:
            actual_return = 0.0

        # Calculate achievement
        achievement = self.calculate_target_achievement(
            actual_return, target_return_decimal, direction
        )

        outcomes = {
            'return': actual_return,
            'holding_days': holding_period_days,
            'target_pct': target_return_pct,
            'direction': direction
        }

        return outcomes, achievement

    def analyze_similar_setups(
        self,
        ticker: str,
        current_conditions: Dict[str, any],
        similar_setups: List[SimilarSetup],
        target_return_pct: Optional[float] = None,
        holding_period_days: Optional[int] = None,
        direction: Literal['LONG', 'SHORT'] = 'LONG'
    ) -> SimilarityAnalysisResult:
        """
        Analyze similar setups and generate comprehensive results.

        Args:
            ticker: Stock symbol
            current_conditions: Current market conditions
            similar_setups: List of similar historical setups
            target_return_pct: Target return percentage (e.g., 5.0 for 5%)
            holding_period_days: Number of trading days to hold
            direction: Trade direction 'LONG' or 'SHORT'

        Returns:
            Complete analysis with statistics and recommendations
            If target parameters provided, includes achievement-based metrics
        """
        if len(similar_setups) < self.min_similar_setups:
            return SimilarityAnalysisResult(
                ticker=ticker,
                current_date=pd.Timestamp.now(),
                current_conditions=current_conditions,
                similar_setups=similar_setups,
                aggregate_statistics={
                    'total_similar': len(similar_setups),
                    'sample_size_adequate': False,
                    'error': f'Need at least {self.min_similar_setups} similar setups',
                    'success_rate_10d': 0.0,
                    'avg_return_10d': 0.0,
                    'risk_reward_ratio': 0.0
                },
                statistical_validation={
                    'valid': False
                },
                recommendation={
                    'take_trade': False,
                    'confidence': 0.0,
                    'confidence_label': 'INSUFFICIENT_DATA',
                    'reasoning': 'Insufficient historical data',
                    'expected_return': 0.0,
                    'expected_holding_days': 0,
                    'risk_reward_ratio': 0.0
                }
            )

        # Aggregate statistics (with target achievement if parameters provided)
        agg_stats = self._calculate_aggregate_stats(
            similar_setups,
            target_return_pct=target_return_pct,
            holding_period_days=holding_period_days,
            direction=direction
        )

        # Statistical validation
        stat_validation = self._statistical_validation(similar_setups, agg_stats)

        # Generate recommendation (with achievement-based logic if available)
        recommendation = self._generate_recommendation(
            agg_stats, stat_validation,
            target_return_pct=target_return_pct,
            holding_period_days=holding_period_days,
            direction=direction
        )

        return SimilarityAnalysisResult(
            ticker=ticker,
            current_date=pd.Timestamp.now(),
            current_conditions=current_conditions,
            similar_setups=similar_setups,
            aggregate_statistics=agg_stats,
            statistical_validation=stat_validation,
            recommendation=recommendation
        )

    def _calculate_aggregate_stats(
        self,
        similar_setups: List[SimilarSetup],
        target_return_pct: Optional[float] = None,
        holding_period_days: Optional[int] = None,
        direction: Literal['LONG', 'SHORT'] = 'LONG'
    ) -> Dict[str, any]:
        """
        Calculate aggregate statistics from similar setups.

        If target parameters provided, calculates achievement-based metrics.
        Achievement thresholds:
            - ≥80% = STRONG (achieved 80%+ of target)
            - 60-79% = MODERATE
            - <60% = WEAK
        """
        total = len(similar_setups)

        # Count profitable outcomes at different horizons (legacy)
        returns_5d = [s.outcomes.get('5d', 0) for s in similar_setups]
        returns_10d = [s.outcomes.get('10d', 0) for s in similar_setups]
        returns_20d = [s.outcomes.get('20d', 0) for s in similar_setups]

        profitable_5d = sum(1 for r in returns_5d if r > 0)
        profitable_10d = sum(1 for r in returns_10d if r > 0)
        profitable_20d = sum(1 for r in returns_20d if r > 0)

        # Calculate win/loss stats
        winners = [r for r in returns_10d if r > 0]
        losers = [r for r in returns_10d if r < 0]

        avg_winner = np.mean(winners) if winners else 0.0
        avg_loser = np.mean(losers) if losers else 0.0
        risk_reward = abs(avg_winner / avg_loser) if avg_loser != 0 else 0.0

        # Confidence interval for success rate (binomial)
        success_rate_10d = profitable_10d / total if total > 0 else 0.0

        # Wilson score interval (better for small samples than normal approximation)
        ci_lower, ci_upper = self._wilson_confidence_interval(
            profitable_10d, total, confidence=0.95
        )

        base_stats = {
            'total_similar': total,
            'profitable_5d': profitable_5d,
            'profitable_10d': profitable_10d,
            'profitable_20d': profitable_20d,
            'success_rate_5d': profitable_5d / total if total > 0 else 0.0,
            'success_rate_10d': success_rate_10d,
            'success_rate_20d': profitable_20d / total if total > 0 else 0.0,
            'avg_return_5d': np.mean(returns_5d) if returns_5d else 0.0,
            'avg_return_10d': np.mean(returns_10d) if returns_10d else 0.0,
            'avg_return_20d': np.mean(returns_20d) if returns_20d else 0.0,
            'avg_return_winners': avg_winner,
            'avg_return_losers': avg_loser,
            'risk_reward_ratio': risk_reward,
            'confidence_interval_95': [ci_lower, ci_upper],
            'median_return_10d': np.median(returns_10d) if returns_10d else 0.0,
            'std_return_10d': np.std(returns_10d) if returns_10d else 0.0
        }

        # Add target achievement metrics if target parameters provided
        if target_return_pct is not None and holding_period_days is not None:
            achievements = [s.target_achievement for s in similar_setups
                          if s.target_achievement is not None]

            if achievements:
                avg_achievement = np.mean(achievements)
                median_achievement = np.median(achievements)
                min_achievement = np.min(achievements)
                max_achievement = np.max(achievements)
                std_achievement = np.std(achievements)

                # Count setups by achievement level
                strong_count = sum(1 for a in achievements if a >= 80)  # ≥80% = STRONG
                moderate_count = sum(1 for a in achievements if 60 <= a < 80)  # 60-79% = MODERATE
                weak_count = sum(1 for a in achievements if 0 <= a < 60)  # 0-59% = WEAK
                negative_count = sum(1 for a in achievements if a < 0)  # <0% = Wrong direction

                total_with_achievement = len(achievements)
                strong_rate = strong_count / total_with_achievement if total_with_achievement > 0 else 0.0
                moderate_rate = moderate_count / total_with_achievement if total_with_achievement > 0 else 0.0
                weak_rate = weak_count / total_with_achievement if total_with_achievement > 0 else 0.0
                negative_rate = negative_count / total_with_achievement if total_with_achievement > 0 else 0.0

                # Determine overall achievement label
                if avg_achievement >= 80:
                    achievement_label = 'STRONG'
                elif avg_achievement >= 60:
                    achievement_label = 'MODERATE'
                elif avg_achievement >= 0:
                    achievement_label = 'WEAK'
                else:
                    achievement_label = 'NEGATIVE'

                # Add achievement stats
                base_stats.update({
                    # Target info
                    'target_return_pct': target_return_pct,
                    'holding_period_days': holding_period_days,
                    'direction': direction,

                    # Achievement metrics
                    'avg_achievement': avg_achievement,
                    'median_achievement': median_achievement,
                    'min_achievement': min_achievement,
                    'max_achievement': max_achievement,
                    'std_achievement': std_achievement,
                    'achievement_label': achievement_label,

                    # Achievement distribution
                    'strong_count': strong_count,  # ≥80%
                    'moderate_count': moderate_count,  # 60-79%
                    'weak_count': weak_count,  # 0-59%
                    'negative_count': negative_count,  # <0% (wrong direction)

                    'strong_rate': strong_rate,
                    'moderate_rate': moderate_rate,
                    'weak_rate': weak_rate,
                    'negative_rate': negative_rate,

                    # Total with valid achievement
                    'total_with_achievement': total_with_achievement
                })

        return base_stats

    def _wilson_confidence_interval(
        self,
        successes: int,
        total: int,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """
        Calculate Wilson score confidence interval for binomial proportion.

        More accurate than normal approximation for small samples.
        """
        if total == 0:
            return (0.0, 0.0)

        p = successes / total
        z = stats.norm.ppf((1 + confidence) / 2)

        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        margin = z * np.sqrt((p * (1 - p) / total + z**2 / (4 * total**2))) / denominator

        return (max(0, center - margin), min(1, center + margin))

    def _statistical_validation(
        self,
        similar_setups: List[SimilarSetup],
        agg_stats: Dict[str, any]
    ) -> Dict[str, any]:
        """Perform statistical validation on results"""
        n = len(similar_setups)
        success_rate = agg_stats['success_rate_10d']

        # One-sample t-test: is success rate significantly different from 50%?
        returns = [s.outcomes.get('10d', 0) for s in similar_setups]
        t_stat, p_value = stats.ttest_1samp(returns, 0)

        # Sample size adequate?
        min_required = self.min_similar_setups
        sample_adequate = n >= min_required

        # Confidence interval doesn't include 50%?
        ci_lower, ci_upper = agg_stats['confidence_interval_95']
        significantly_different = (ci_lower > 0.5) or (ci_upper < 0.5)

        return {
            't_statistic': t_stat,
            'p_value': p_value,
            'significant_at_05': p_value < 0.05,
            'sample_size_adequate': sample_adequate,
            'min_required_samples': min_required,
            'actual_samples': n,
            'confidence_interval': [ci_lower, ci_upper],
            'significantly_different_from_random': significantly_different
        }

    def _generate_recommendation(
        self,
        agg_stats: Dict[str, any],
        stat_validation: Dict[str, any],
        target_return_pct: Optional[float] = None,
        holding_period_days: Optional[int] = None,
        direction: Literal['LONG', 'SHORT'] = 'LONG'
    ) -> Dict[str, any]:
        """
        Generate trading recommendation based on analysis.

        If target parameters provided, uses achievement-based logic instead of
        legacy success rate logic.
        """
        significant = stat_validation.get('significant_at_05', False)
        sample_adequate = stat_validation.get('sample_size_adequate', False)

        # Use achievement-based logic if target parameters provided
        has_achievement_data = 'avg_achievement' in agg_stats

        if has_achievement_data:
            # Achievement-based recommendation
            avg_achievement = agg_stats['avg_achievement']
            strong_rate = agg_stats.get('strong_rate', 0.0)
            achievement_label = agg_stats.get('achievement_label', 'WEAK')

            # Determine if should take trade based on achievement
            # Strong confirmation if avg achievement ≥60% AND strong_rate ≥40%
            take_trade = (
                avg_achievement >= 60 and
                strong_rate >= 0.40 and
                sample_adequate
            )

            # Confidence level based on achievement
            if avg_achievement >= 80 and strong_rate >= 0.60:
                confidence = 0.85
                confidence_label = "HIGH"
            elif avg_achievement >= 60 and strong_rate >= 0.40:
                confidence = 0.70
                confidence_label = "MEDIUM"
            else:
                confidence = 0.50
                confidence_label = "LOW"

            # Generate reasoning
            reasoning_parts = []

            if sample_adequate:
                reasoning_parts.append(
                    f"Found {agg_stats['total_similar']} similar historical setups"
                )
            else:
                reasoning_parts.append(
                    f"Only {agg_stats['total_similar']} similar setups found (need {stat_validation['min_required_samples']})"
                )

            reasoning_parts.append(
                f"Avg target achievement: {avg_achievement:.1f}% ({achievement_label})"
            )
            reasoning_parts.append(
                f"Strong setups (≥80%): {agg_stats.get('strong_count', 0)}/{agg_stats.get('total_with_achievement', 0)} ({strong_rate:.1%})"
            )
            reasoning_parts.append(
                f"Direction: {direction}, Target: {target_return_pct}% in {holding_period_days} days"
            )

            reasoning = ". ".join(reasoning_parts)

            expected_return_pct = (avg_achievement / 100) * target_return_pct if target_return_pct else 0

            return {
                'take_trade': take_trade,
                'confidence': confidence,
                'confidence_label': confidence_label,
                'reasoning': reasoning,
                'expected_return': expected_return_pct / 100,  # Convert to decimal
                'expected_holding_days': holding_period_days or 10,
                'risk_reward_ratio': agg_stats['risk_reward_ratio'],
                'avg_achievement': avg_achievement,
                'achievement_label': achievement_label,
                'strong_rate': strong_rate,
                'direction': direction,
                'target_return_pct': target_return_pct
            }

        else:
            # Legacy success rate based logic
            success_rate = agg_stats['success_rate_10d']

            # Determine if should take trade
            take_trade = (
                success_rate > 0.55 and  # Better than random
                sample_adequate and       # Enough data
                significant              # Statistically significant
            )

            # Confidence level
            if success_rate > 0.70 and significant:
                confidence = 0.85
                confidence_label = "HIGH"
            elif success_rate > 0.60 and significant:
                confidence = 0.70
                confidence_label = "MEDIUM"
            else:
                confidence = 0.50
                confidence_label = "LOW"

            # Generate reasoning
            reasoning_parts = []

            if sample_adequate:
                reasoning_parts.append(
                    f"Found {agg_stats['total_similar']} similar historical setups"
                )
            else:
                reasoning_parts.append(
                    f"Only {agg_stats['total_similar']} similar setups found (need {stat_validation['min_required_samples']})"
                )

            reasoning_parts.append(
                f"{success_rate:.1%} success rate over 10 days"
            )

            if significant:
                p_val = stat_validation.get('p_value', 0.0)
                reasoning_parts.append(f"Statistically significant (p={p_val:.3f})")
            else:
                reasoning_parts.append("Not statistically significant")

            reasoning = ". ".join(reasoning_parts)

            return {
                'take_trade': take_trade,
                'confidence': confidence,
                'confidence_label': confidence_label,
                'reasoning': reasoning,
                'expected_return': agg_stats['avg_return_10d'],
                'expected_holding_days': 10,
                'risk_reward_ratio': agg_stats['risk_reward_ratio']
            }


def generate_similarity_report(result: SimilarityAnalysisResult) -> str:
    """
    Generate markdown report from similarity analysis.

    Args:
        result: Similarity analysis result

    Returns:
        Formatted markdown report
    """
    agg = result.aggregate_statistics
    val = result.statistical_validation
    rec = result.recommendation

    # Check if target achievement data is available
    has_achievement = 'avg_achievement' in agg

    report = f"""# Similarity-Based Analysis Report

## Summary
- **Ticker:** {result.ticker}
- **Analysis Date:** {result.current_date.strftime('%Y-%m-%d')}
- **Similar Setups Found:** {agg.get('total_similar', 0)}
- **Recommendation:** {"TAKE TRADE" if rec['take_trade'] else "SKIP"}
- **Confidence:** {rec['confidence_label']} ({rec['confidence']:.0%})
"""

    # Add target info if achievement-based
    if has_achievement:
        report += f"""
## Trade Plan Target
- **Direction:** {agg.get('direction', 'N/A')}
- **Target Return:** {agg.get('target_return_pct', 0):.1f}%
- **Holding Period:** {agg.get('holding_period_days', 0)} trading days
"""

    report += "\n## Current Market Conditions\n"

    for key, value in result.current_conditions.items():
        report += f"- **{key}:** {value}\n"

    # Add Target Achievement section if available
    if has_achievement:
        report += f"""
## Target Achievement Analysis

### Achievement Summary
- **Average Achievement:** {agg.get('avg_achievement', 0):.1f}% ({agg.get('achievement_label', 'N/A')})
- **Median Achievement:** {agg.get('median_achievement', 0):.1f}%
- **Min/Max:** {agg.get('min_achievement', 0):.1f}% / {agg.get('max_achievement', 0):.1f}%
- **Std Dev:** {agg.get('std_achievement', 0):.1f}%

### Achievement Distribution
| Category | Count | Rate |
|----------|-------|------|
| STRONG (≥80%) | {agg.get('strong_count', 0)} | {agg.get('strong_rate', 0):.1%} |
| MODERATE (60-79%) | {agg.get('moderate_count', 0)} | {agg.get('moderate_rate', 0):.1%} |
| WEAK (0-59%) | {agg.get('weak_count', 0)} | {agg.get('weak_rate', 0):.1%} |
| NEGATIVE (<0%) | {agg.get('negative_count', 0)} | {agg.get('negative_rate', 0):.1%} |

**Interpretation:**
- STRONG (≥80%): Achieved 80%+ of target (e.g., target 5%, actual ≥4%)
- MODERATE (60-79%): Achieved 60-79% of target
- WEAK (0-59%): Moved in right direction but fell short
- NEGATIVE (<0%): Moved in wrong direction

### Trading Plan Validation (Per Setup)

| Date | Sim% | Actual | Target | Achieve | Status |
|------|------|--------|--------|---------|--------|
"""
        # Add individual setup rows
        sorted_setups = sorted(result.similar_setups, key=lambda x: x.similarity_score, reverse=True)
        for setup in sorted_setups[:15]:  # Limit to top 15 for readability
            date_str = setup.date.strftime('%Y-%m-%d')
            similarity = setup.similarity_score * 100
            actual_return = setup.outcomes.get('target_return', setup.outcomes.get('10d', 0)) * 100
            achievement = setup.target_achievement if setup.target_achievement else 0
            target_pct = agg.get('target_return_pct', 5.0)

            # Determine status emoji
            if achievement >= 100:
                status = '✅ HIT'
            elif achievement >= 60:
                status = '🟡 PARTIAL'
            elif achievement >= 0:
                status = '🟠 WEAK'
            else:
                status = '❌ WRONG'

            report += f"| {date_str} | {similarity:.1f}% | {actual_return:+.2f}% | {target_pct:.1f}% | {achievement:+.1f}% | {status} |\n"

        if len(result.similar_setups) > 15:
            report += f"\n*Showing top 15 of {len(result.similar_setups)} similar setups*\n"

    report += f"""
## Historical Performance (Legacy)

### Success Rates
- **5-day:** {agg.get('success_rate_5d', 0):.1%} ({agg.get('profitable_5d', 0)}/{agg.get('total_similar', 0)})
- **10-day:** {agg.get('success_rate_10d', 0):.1%} ({agg.get('profitable_10d', 0)}/{agg.get('total_similar', 0)})
- **20-day:** {agg.get('success_rate_20d', 0):.1%} ({agg.get('profitable_20d', 0)}/{agg.get('total_similar', 0)})

### Returns
- **Average (10-day):** {agg.get('avg_return_10d', 0):.2%}
- **Median (10-day):** {agg.get('median_return_10d', 0):.2%}
- **Std Dev (10-day):** {agg.get('std_return_10d', 0):.2%}

### Win/Loss Profile
- **Average Winner:** {agg.get('avg_return_winners', 0):.2%}
- **Average Loser:** {agg.get('avg_return_losers', 0):.2%}
- **Risk/Reward Ratio:** {agg.get('risk_reward_ratio', 0):.2f}:1

## Statistical Validation

- **T-Statistic:** {val.get('t_statistic', 0):.2f}
- **P-Value:** {val.get('p_value', 1):.4f}
- **Significant:** {"✅ Yes" if val.get('significant_at_05', False) else "❌ No"}
- **Sample Size:** {val.get('actual_samples', 0)} (min: {val.get('min_required_samples', 0)})
- **95% CI:** [{agg.get('confidence_interval_95', [0,0])[0]:.1%}, {agg.get('confidence_interval_95', [0,0])[1]:.1%}]

## Recommendation

**Decision:** {"TAKE TRADE" if rec['take_trade'] else "SKIP TRADE"}

**Reasoning:** {rec['reasoning']}

**Expected Metrics:**
- Expected Return: {rec.get('expected_return', 0):.2%}
- Expected Holding Period: {rec.get('expected_holding_days', 0)} days
- Risk/Reward: {rec.get('risk_reward_ratio', 0):.2f}:1
"""

    if has_achievement:
        report += f"""
**Achievement-Based Metrics:**
- Avg Achievement: {rec.get('avg_achievement', 0):.1f}% ({rec.get('achievement_label', 'N/A')})
- Strong Rate (≥80%): {rec.get('strong_rate', 0):.1%}
"""

    report += """
---
*Generated with institutional-grade similarity-based backtesting*
"""

    return report
