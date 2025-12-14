"""
ML Core Functions for Investor-Agent
Based on "Advances in Financial Machine Learning" by Marcos López de Prado

This module implements institutional-grade ML methods for financial analysis:
- Triple-Barrier Labeling (Chapter 3)
- Trend-Scanning Labels (Chapter 3)
- Meta-Labeling (Chapter 3)
- Fractional Differentiation (Chapter 5)
- Feature Importance (Chapter 5)
- Purged K-Fold CV (Chapter 7)
- Deflated Sharpe Ratio (Chapter 7)
- Kelly Criterion Position Sizing (Chapter 10)
"""

import numpy as np
import pandas as pd
from typing import Literal, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from datetime import timedelta
import warnings


@dataclass
class TripleBarrierResult:
    """Results from triple-barrier labeling"""
    labels: pd.Series  # +1 (profit), -1 (loss), 0 (timeout)
    barrier_hit: pd.Series  # 'profit', 'stop', 'time'
    holding_period: pd.Series  # days until barrier hit
    returns: pd.Series  # actual return achieved
    success_rate: float  # % of +1 labels
    avg_profit: float  # avg return when profitable
    avg_loss: float  # avg return when unprofitable
    risk_reward_ratio: float  # avg_profit / abs(avg_loss)
    avg_holding_days: float  # mean holding period


def apply_triple_barrier_labels(
    prices: pd.Series,
    profit_target: float = 0.05,
    stop_loss: float = 0.05,
    max_holding_days: int = 10,
    min_return: float = 0.0
) -> TripleBarrierResult:
    """
    Apply triple-barrier method to label price data.

    For each timestamp, we set three barriers:
    - Upper barrier: price * (1 + profit_target)
    - Lower barrier: price * (1 - stop_loss)
    - Time barrier: t + max_holding_days

    Label is determined by which barrier is hit first:
    - Upper hit first → +1 (profitable)
    - Lower hit first → -1 (unprofitable)
    - Time hit first → 0 (neutral) or sign of return if > min_return

    Args:
        prices: Series of closing prices with DatetimeIndex
        profit_target: Profit taking level (e.g., 0.05 = 5%)
        stop_loss: Stop loss level (e.g., 0.05 = 5%)
        max_holding_days: Maximum days to hold
        min_return: Minimum return to consider significant for timeout labels

    Returns:
        TripleBarrierResult with labels and statistics

    Example:
        >>> prices = pd.Series([100, 102, 105, 103, 98, 96, 101])
        >>> result = apply_triple_barrier_labels(prices, profit_target=0.05, stop_loss=0.05)
        >>> print(f"Success rate: {result.success_rate:.1%}")
    """
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("prices must have DatetimeIndex")

    if len(prices) < max_holding_days + 1:
        raise ValueError(f"Need at least {max_holding_days + 1} data points")

    labels = []
    barrier_hits = []
    holding_periods = []
    actual_returns = []

    # Iterate through each potential entry point
    # Stop before the last max_holding_days to ensure we have enough future data
    for i in range(len(prices) - max_holding_days):
        entry_price = prices.iloc[i]
        entry_date = prices.index[i]

        # Define barriers
        upper_barrier = entry_price * (1 + profit_target)
        lower_barrier = entry_price * (1 - stop_loss)

        # Look forward for barrier hits
        future_prices = prices.iloc[i+1:i+1+max_holding_days]

        # Find which barrier is hit first
        hit_upper = future_prices >= upper_barrier
        hit_lower = future_prices <= lower_barrier

        if hit_upper.any():
            # Profit barrier hit first
            hit_idx = hit_upper.idxmax()
            days_held = (hit_idx - entry_date).days
            if hit_lower.any() and hit_lower.idxmax() < hit_idx:
                # Stop hit before profit
                hit_idx = hit_lower.idxmax()
                days_held = (hit_idx - entry_date).days
                label = -1
                barrier = 'stop'
            else:
                label = 1
                barrier = 'profit'
        elif hit_lower.any():
            # Stop barrier hit
            hit_idx = hit_lower.idxmax()
            days_held = (hit_idx - entry_date).days
            label = -1
            barrier = 'stop'
        else:
            # Time barrier hit (no price barrier touched)
            hit_idx = future_prices.index[-1]
            days_held = max_holding_days
            final_return = (future_prices.iloc[-1] - entry_price) / entry_price

            # Label based on final return magnitude
            if abs(final_return) < min_return:
                label = 0  # Neutral if return too small
            else:
                label = 1 if final_return > 0 else -1
            barrier = 'time'

        exit_price = prices.loc[hit_idx]
        actual_return = (exit_price - entry_price) / entry_price

        labels.append(label)
        barrier_hits.append(barrier)
        holding_periods.append(days_held)
        actual_returns.append(actual_return)

    # Create result series with same index as input (truncated)
    result_index = prices.index[:len(labels)]
    labels_series = pd.Series(labels, index=result_index, name='label')
    barrier_series = pd.Series(barrier_hits, index=result_index, name='barrier_hit')
    holding_series = pd.Series(holding_periods, index=result_index, name='holding_period')
    returns_series = pd.Series(actual_returns, index=result_index, name='return')

    # Calculate statistics
    profitable = returns_series[labels_series == 1]
    unprofitable = returns_series[labels_series == -1]

    success_rate = (labels_series == 1).sum() / len(labels_series) if len(labels_series) > 0 else 0
    avg_profit = profitable.mean() if len(profitable) > 0 else 0
    avg_loss = unprofitable.mean() if len(unprofitable) > 0 else 0
    risk_reward = abs(avg_profit / avg_loss) if avg_loss != 0 else np.inf
    avg_holding = holding_series.mean()

    return TripleBarrierResult(
        labels=labels_series,
        barrier_hit=barrier_series,
        holding_period=holding_series,
        returns=returns_series,
        success_rate=success_rate,
        avg_profit=avg_profit,
        avg_loss=avg_loss,
        risk_reward_ratio=risk_reward,
        avg_holding_days=avg_holding
    )


@dataclass
class TrendScanningResult:
    """Results from trend-scanning labels"""
    labels: pd.Series  # +1 (uptrend), -1 (downtrend), 0 (neutral)
    t_statistics: pd.Series  # t-stat of regression slope
    p_values: pd.Series  # statistical significance
    confidence: pd.Series  # 1 - p_value
    slopes: pd.Series  # regression slopes


def get_trend_scanning_labels(
    prices: pd.Series,
    lookforward_window: int = 20,
    t_stat_threshold: float = 1.96
) -> TrendScanningResult:
    """
    Apply trend-scanning method using t-statistics.

    For each timestamp, fit linear regression on forward-looking window
    and calculate t-statistic of the slope. This determines if the trend
    is statistically significant, not just visually apparent.

    Args:
        prices: Series of closing prices with DatetimeIndex
        lookforward_window: Number of periods to look forward (default 20)
        t_stat_threshold: Threshold for significance (1.96 = 95% confidence)

    Returns:
        TrendScanningResult with labels and statistics

    Example:
        >>> prices = pd.Series([100, 102, 105, 108, 110, 113, 115])
        >>> result = get_trend_scanning_labels(prices, lookforward_window=5)
        >>> print(f"Trend confidence: {result.confidence.iloc[0]:.1%}")
    """
    from scipy import stats

    if not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("prices must have DatetimeIndex")

    if len(prices) < lookforward_window + 1:
        raise ValueError(f"Need at least {lookforward_window + 1} data points")

    labels = []
    t_stats = []
    p_vals = []
    slopes = []

    # Iterate through each potential entry point
    for i in range(len(prices) - lookforward_window):
        # Get forward-looking window
        forward_prices = prices.iloc[i:i+lookforward_window+1]

        # Fit linear regression: y = a + b*x
        x = np.arange(len(forward_prices))
        y = forward_prices.values

        # Calculate regression statistics
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

        # Calculate t-statistic for slope
        # t = slope / standard_error
        t_stat = slope / std_err if std_err > 0 else 0

        # Determine label based on t-statistic
        if t_stat > t_stat_threshold:
            label = 1  # Significant uptrend
        elif t_stat < -t_stat_threshold:
            label = -1  # Significant downtrend
        else:
            label = 0  # No significant trend

        labels.append(label)
        t_stats.append(t_stat)
        p_vals.append(p_value)
        slopes.append(slope)

    # Create result series
    result_index = prices.index[:len(labels)]
    labels_series = pd.Series(labels, index=result_index, name='trend_label')
    t_stat_series = pd.Series(t_stats, index=result_index, name='t_statistic')
    p_value_series = pd.Series(p_vals, index=result_index, name='p_value')
    confidence_series = pd.Series(1 - np.array(p_vals), index=result_index, name='confidence')
    slope_series = pd.Series(slopes, index=result_index, name='slope')

    return TrendScanningResult(
        labels=labels_series,
        t_statistics=t_stat_series,
        p_values=p_value_series,
        confidence=confidence_series,
        slopes=slope_series
    )


def calculate_kelly_size(
    predicted_prob: float,
    predicted_return: float,
    volatility: float,
    kelly_fraction: float = 0.25
) -> float:
    """
    Calculate position size using Kelly Criterion adjusted for ML predictions.

    Kelly formula: f* = (p * b - q) / b
    where:
    - p = probability of win
    - q = probability of loss (1 - p)
    - b = win/loss ratio

    For continuous returns: f* = μ / σ² = Sharpe / σ

    Args:
        predicted_prob: Probability of positive return (0-1)
        predicted_return: Expected return (e.g., 0.05 for 5%)
        volatility: Expected volatility (standard deviation)
        kelly_fraction: Fraction of Kelly to use (0.25 = quarter-Kelly, safer)

    Returns:
        Position size as fraction of capital (0-1)

    Example:
        >>> size = calculate_kelly_size(0.68, 0.05, 0.15, kelly_fraction=0.25)
        >>> print(f"Position size: {size:.1%}")
    """
    if not 0 <= predicted_prob <= 1:
        raise ValueError("predicted_prob must be between 0 and 1")

    if volatility <= 0:
        raise ValueError("volatility must be positive")

    if not 0 < kelly_fraction <= 1:
        raise ValueError("kelly_fraction must be between 0 and 1")

    # Simplified Kelly for continuous returns
    # f* = (expected_return) / (variance)
    if volatility == 0:
        return 0

    # Adjust expected return by probability
    adjusted_return = predicted_return * predicted_prob

    # Kelly formula for continuous returns
    kelly_optimal = adjusted_return / (volatility ** 2)

    # Apply fractional Kelly for safety
    position_size = kelly_optimal * kelly_fraction

    # Constrain to reasonable bounds
    position_size = max(0, min(position_size, 1.0))

    return position_size


def calculate_feature_importance(
    features: pd.DataFrame,
    target: pd.Series,
    method: str = 'combined'
) -> Dict[str, float]:
    """
    Calculate feature importance using López de Prado's robust methodology.

    Implements three complementary methods from Chapter 5 of "Advances in Financial
    Machine Learning" and averages them for robustness:

    1. **MDI (Mean Decrease Impurity)**: Sklearn's built-in Random Forest importance
       - Fast, but biased toward continuous and high-cardinality features
       - Based on node impurity reduction

    2. **MDA (Mean Decrease Accuracy)**: Permutation importance
       - Shuffle each feature and measure accuracy drop
       - More robust, accounts for feature interactions
       - Unbiased, but slower

    3. **SFI (Single Feature Importance)**: Individual feature performance
       - Train model with each feature alone
       - Measures standalone predictive power
       - No interaction effects captured

    The three methods are averaged to provide a robust, balanced importance score.

    Args:
        features: DataFrame of feature values (samples x features)
        target: Series of target values (e.g., forward returns or labels)
        method: Importance calculation method:
                - 'combined': Average of MDI, MDA, SFI (DEFAULT, recommended)
                - 'mdi': Mean Decrease Impurity only
                - 'mda': Mean Decrease Accuracy only
                - 'sfi': Single Feature Importance only
                - 'spearman': Simple correlation (fast, for backward compatibility)

    Returns:
        Dictionary mapping feature names to importance scores (0-1 normalized)

    Example:
        >>> features_df = pd.DataFrame({
        ...     'rsi': [...],
        ...     'macd': [...],
        ...     'volume': [...]
        ... })
        >>> returns = pd.Series([...])  # Forward returns
        >>> importances = calculate_feature_importance(features_df, returns, method='combined')
        >>> # Returns: {'rsi': 0.45, 'volume': 0.32, 'macd': 0.23}
        >>> # Higher score = more important for prediction

    Reference:
        López de Prado, M. (2018). Advances in Financial Machine Learning.
        Chapter 5: Feature Importance

    Note:
        - Requires scikit-learn for 'combined', 'mdi', 'mda', 'sfi'
        - 'spearman' is faster but less robust
        - For real money trading, use 'combined' (default)
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import r2_score
    from scipy.stats import spearmanr

    if len(features) != len(target):
        raise ValueError("features and target must have same length")

    if len(features) < 30:
        raise ValueError("Need at least 30 samples for robust feature importance")

    # Remove rows with any NaN
    valid_mask = ~(features.isna().any(axis=1) | target.isna())
    features_clean = features[valid_mask].copy()
    target_clean = target[valid_mask].copy()

    if len(features_clean) < 30:
        raise ValueError(f"Only {len(features_clean)} valid samples after removing NaN (need 30+)")

    # === SPEARMAN CORRELATION (FAST, BACKWARD COMPATIBLE) ===
    if method == 'spearman':
        importances = {}
        for column in features_clean.columns:
            try:
                corr, _ = spearmanr(features_clean[column], target_clean)
                importances[column] = abs(corr) if not np.isnan(corr) else 0.0
            except Exception as e:
                warnings.warn(f"Could not calculate correlation for {column}: {e}")
                importances[column] = 0.0
        return importances

    # === LÓPEZ DE PRADO METHODS (MDI, MDA, SFI) ===

    feature_names = features_clean.columns.tolist()
    X = features_clean.values
    y = target_clean.values

    # Initialize importance dictionaries
    mdi_importance = {}
    mda_importance = {}
    sfi_importance = {}

    # === 1. MDI (Mean Decrease Impurity) ===
    if method in ['mdi', 'combined']:
        try:
            # Train Random Forest
            rf = RandomForestRegressor(
                n_estimators=100,
                max_depth=5,
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1
            )
            rf.fit(X, y)

            # Get built-in feature importances
            mdi_scores = rf.feature_importances_

            for i, name in enumerate(feature_names):
                mdi_importance[name] = float(mdi_scores[i])

        except Exception as e:
            warnings.warn(f"MDI calculation failed: {e}")
            mdi_importance = {name: 0.0 for name in feature_names}

    # === 2. MDA (Mean Decrease Accuracy) - Permutation Importance ===
    if method in ['mda', 'combined']:
        try:
            # Train Random Forest
            rf = RandomForestRegressor(
                n_estimators=100,
                max_depth=5,
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1
            )
            rf.fit(X, y)

            # Baseline R² score
            baseline_score = r2_score(y, rf.predict(X))

            # Permutation importance: shuffle each feature and measure accuracy drop
            for i, name in enumerate(feature_names):
                X_permuted = X.copy()
                # Shuffle this feature
                np.random.seed(42)
                X_permuted[:, i] = np.random.permutation(X_permuted[:, i])

                # Calculate R² with shuffled feature
                permuted_score = r2_score(y, rf.predict(X_permuted))

                # Importance = drop in accuracy
                importance = max(0, baseline_score - permuted_score)
                mda_importance[name] = float(importance)

        except Exception as e:
            warnings.warn(f"MDA calculation failed: {e}")
            mda_importance = {name: 0.0 for name in feature_names}

    # === 3. SFI (Single Feature Importance) ===
    if method in ['sfi', 'combined']:
        try:
            for i, name in enumerate(feature_names):
                # Train model with ONLY this feature
                X_single = X[:, [i]]

                rf = RandomForestRegressor(
                    n_estimators=50,
                    max_depth=3,
                    min_samples_split=10,
                    min_samples_leaf=5,
                    random_state=42,
                    n_jobs=-1
                )
                rf.fit(X_single, y)

                # R² score for this single feature
                score = r2_score(y, rf.predict(X_single))
                sfi_importance[name] = max(0.0, float(score))

        except Exception as e:
            warnings.warn(f"SFI calculation failed: {e}")
            sfi_importance = {name: 0.0 for name in feature_names}

    # === COMBINE RESULTS ===
    if method == 'mdi':
        result = mdi_importance
    elif method == 'mda':
        result = mda_importance
    elif method == 'sfi':
        result = sfi_importance
    elif method == 'combined':
        # Average the three methods (López de Prado's recommendation)
        result = {}
        for name in feature_names:
            mdi_score = mdi_importance.get(name, 0.0)
            mda_score = mda_importance.get(name, 0.0)
            sfi_score = sfi_importance.get(name, 0.0)

            # Average of three methods
            avg_score = (mdi_score + mda_score + sfi_score) / 3.0
            result[name] = float(avg_score)
    else:
        raise ValueError(f"Unknown method: {method}")

    # Normalize to sum to 1
    total = sum(result.values())
    if total > 0:
        result = {k: v / total for k, v in result.items()}

    return result


def calculate_deflated_sharpe(
    returns: pd.Series,
    n_trials: int,
    skewness: Optional[float] = None,
    kurtosis: Optional[float] = None,
    annual_factor: int = 252
) -> Dict[str, float]:
    """
    Calculate Deflated Sharpe Ratio accounting for multiple testing.

    The DSR adjusts the Sharpe ratio for:
    1. Multiple trials (testing many strategies)
    2. Non-normal returns (skewness, kurtosis)

    Based on Bailey & López de Prado (2014)

    Args:
        returns: Series of returns
        n_trials: Number of strategies tested
        skewness: Return skewness (calculated if None)
        kurtosis: Return kurtosis (calculated if None)
        annual_factor: Annualization factor (252 for daily, 12 for monthly)

    Returns:
        Dictionary with raw_sharpe, deflated_sharpe, probability_significant

    Example:
        >>> returns = pd.Series(np.random.randn(252) * 0.01 + 0.001)
        >>> result = calculate_deflated_sharpe(returns, n_trials=100)
        >>> print(f"Deflated Sharpe: {result['deflated_sharpe']:.2f}")
    """
    from scipy.stats import norm

    if len(returns) < 2:
        raise ValueError("Need at least 2 returns")

    # Calculate raw Sharpe ratio
    mean_return = returns.mean()
    std_return = returns.std()

    # Check for zero or near-zero volatility (using small epsilon for floating-point comparison)
    if std_return < 1e-10:
        return {
            'raw_sharpe': 0.0,
            'deflated_sharpe': 0.0,
            'probability_significant': 0.0,
            'expected_max_sharpe': 0.0
        }

    sharpe = mean_return / std_return
    annual_sharpe = sharpe * np.sqrt(annual_factor)

    # Calculate skewness and kurtosis if not provided
    if skewness is None:
        skewness = returns.skew()
    if kurtosis is None:
        kurtosis = returns.kurtosis()  # Excess kurtosis

    # Expected maximum Sharpe from n_trials random strategies
    # E[max SR] ≈ √(2 log n_trials)
    expected_max_sharpe = np.sqrt(2 * np.log(n_trials))

    # Adjustment for non-normality
    # Adjusted SR = SR * √(1 - γ₁*SR + (γ₂ - 1)/4 * SR²)
    # where γ₁ = skewness, γ₂ = kurtosis + 3
    excess_kurt = kurtosis + 3

    adjustment = np.sqrt(1 - skewness * sharpe + (excess_kurt - 1) / 4 * sharpe ** 2)
    adjusted_sharpe = sharpe * adjustment if adjustment > 0 else 0

    # Deflated Sharpe Ratio
    # DSR = (SR - E[max SR]) / σ_SR
    # where σ_SR ≈ 1/√T
    T = len(returns)
    sigma_sharpe = 1 / np.sqrt(T)

    deflated_sharpe = (annual_sharpe - expected_max_sharpe) / (sigma_sharpe * np.sqrt(annual_factor))

    # Probability that strategy is truly significant
    # P(SR > 0 | observed SR, n_trials)
    prob_significant = norm.cdf(deflated_sharpe)

    return {
        'raw_sharpe': annual_sharpe,
        'deflated_sharpe': deflated_sharpe,
        'probability_significant': prob_significant,
        'expected_max_sharpe': expected_max_sharpe,
        'skewness': skewness,
        'kurtosis': kurtosis
    }


if __name__ == "__main__":
    # Example usage
    print("ML Core Module - Example Usage")
    print("=" * 50)

    # Create sample price data
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    prices = pd.Series(100 * (1 + np.cumsum(np.random.randn(100) * 0.02)), index=dates)

    # Test triple-barrier labeling
    print("\n1. Triple-Barrier Labeling")
    print("-" * 50)
    tb_result = apply_triple_barrier_labels(prices, profit_target=0.05, stop_loss=0.05, max_holding_days=10)
    print(f"Success rate: {tb_result.success_rate:.1%}")
    print(f"Avg profit when winning: {tb_result.avg_profit:.2%}")
    print(f"Avg loss when losing: {tb_result.avg_loss:.2%}")
    print(f"Risk/Reward ratio: {tb_result.risk_reward_ratio:.2f}")
    print(f"Avg holding days: {tb_result.avg_holding_days:.1f}")

    # Test trend-scanning
    print("\n2. Trend-Scanning Labels")
    print("-" * 50)
    ts_result = get_trend_scanning_labels(prices, lookforward_window=20)
    print(f"Uptrends detected: {(ts_result.labels == 1).sum()}")
    print(f"Downtrends detected: {(ts_result.labels == -1).sum()}")
    print(f"No significant trend: {(ts_result.labels == 0).sum()}")
    print(f"Avg confidence for uptrends: {ts_result.confidence[ts_result.labels == 1].mean():.1%}")

    # Test Kelly sizing
    print("\n3. Kelly Position Sizing")
    print("-" * 50)
    kelly_size = calculate_kelly_size(predicted_prob=0.68, predicted_return=0.05, volatility=0.15, kelly_fraction=0.25)
    print(f"Position size (quarter-Kelly): {kelly_size:.1%}")

    # Test Deflated Sharpe
    print("\n4. Deflated Sharpe Ratio")
    print("-" * 50)
    returns = prices.pct_change().dropna()
    ds_result = calculate_deflated_sharpe(returns, n_trials=100)
    print(f"Raw Sharpe: {ds_result['raw_sharpe']:.2f}")
    print(f"Deflated Sharpe: {ds_result['deflated_sharpe']:.2f}")
    print(f"Probability significant: {ds_result['probability_significant']:.1%}")
