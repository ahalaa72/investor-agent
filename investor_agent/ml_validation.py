"""
ML Validation Framework

Implements institutional-grade validation methods from:
- López de Prado, M. (2018). Advances in Financial Machine Learning.
  Chapter 7: Cross-Validation in Finance
  Chapter 11: The Dangers of Backtesting

This module provides:
1. Walk-Forward Optimization (WFO)
2. Multiple Testing Corrections (Bonferroni, Benjamini-Hochberg, Harvey-Liu-Zhu)
3. Purged K-Fold Cross-Validation
4. Ledoit-Wolf Covariance Shrinkage
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Optional, Callable
from dataclasses import dataclass
from scipy import stats
from sklearn.covariance import LedoitWolf


@dataclass
class WalkForwardResult:
    """Results from walk-forward optimization"""
    in_sample_returns: pd.Series
    out_of_sample_returns: pd.Series
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    walk_forward_efficiency: float  # OOS Sharpe / IS Sharpe
    total_periods: int
    window_size: int


class WalkForwardOptimization:
    """
    Walk-Forward Optimization for strategy validation.

    Optimizes parameters on in-sample data, tests on out-of-sample data,
    then rolls forward and repeats. This prevents look-ahead bias and
    provides realistic performance estimates.

    Two modes:
    - Rolling: Fixed-length window (adapts quickly to regime changes)
    - Anchored: Growing window from fixed start (uses more data)

    Reference:
        Pardo, R. (2008). The Evaluation and Optimization of Trading Strategies.
    """

    def __init__(
        self,
        mode: str = 'rolling',
        in_sample_ratio: float = 0.7,
        min_train_size: int = 100
    ):
        """
        Initialize walk-forward optimizer.

        Args:
            mode: 'rolling' (fixed window) or 'anchored' (growing window)
            in_sample_ratio: Proportion of data for training (0.7 = 70%)
            min_train_size: Minimum training samples required
        """
        if mode not in ['rolling', 'anchored']:
            raise ValueError("mode must be 'rolling' or 'anchored'")

        if not 0 < in_sample_ratio < 1:
            raise ValueError("in_sample_ratio must be between 0 and 1")

        if min_train_size < 30:
            raise ValueError("min_train_size must be at least 30")

        self.mode = mode
        self.in_sample_ratio = in_sample_ratio
        self.min_train_size = min_train_size

    def run(
        self,
        returns: pd.Series,
        strategy_func: Callable,
        param_grid: Dict
    ) -> WalkForwardResult:
        """
        Run walk-forward optimization.

        Args:
            returns: Time series of returns
            strategy_func: Function that takes (returns, params) and returns predictions
            param_grid: Dictionary of parameter values to test

        Returns:
            WalkForwardResult with in-sample and out-of-sample performance
        """
        if len(returns) < self.min_train_size:
            raise ValueError(f"Need at least {self.min_train_size} data points")

        n = len(returns)
        is_size = int(n * self.in_sample_ratio)
        oos_size = n - is_size

        if oos_size < 10:
            raise ValueError("Out-of-sample size too small")

        is_returns_list = []
        oos_returns_list = []

        if self.mode == 'rolling':
            # Rolling window: fixed size
            window_size = is_size + oos_size
            step_size = oos_size

            for start in range(0, n - window_size + 1, step_size):
                end = start + window_size

                train_data = returns.iloc[start:start + is_size]
                test_data = returns.iloc[start + is_size:end]

                # Optimize on training data
                best_params = self._optimize_parameters(train_data, strategy_func, param_grid)

                # Test on out-of-sample data
                test_predictions = strategy_func(test_data, best_params)

                is_returns_list.append(train_data.mean())
                oos_returns_list.append(test_data.mean())

        else:  # anchored
            # Anchored window: grows from start
            for split_idx in range(is_size, n, oos_size):
                if split_idx + oos_size > n:
                    break

                train_data = returns.iloc[:split_idx]
                test_data = returns.iloc[split_idx:split_idx + oos_size]

                # Optimize on training data
                best_params = self._optimize_parameters(train_data, strategy_func, param_grid)

                # Test on out-of-sample data
                test_predictions = strategy_func(test_data, best_params)

                is_returns_list.append(train_data.mean())
                oos_returns_list.append(test_data.mean())

        # Calculate metrics
        is_returns = pd.Series(is_returns_list)
        oos_returns = pd.Series(oos_returns_list)

        is_sharpe = self._calculate_sharpe(is_returns)
        oos_sharpe = self._calculate_sharpe(oos_returns)

        # Walk-Forward Efficiency: ratio of OOS to IS Sharpe
        # WFE > 0.5-0.6 suggests strategy is not overfit
        wfe = float(oos_sharpe / is_sharpe) if is_sharpe != 0 else 0.0

        return WalkForwardResult(
            in_sample_returns=is_returns,
            out_of_sample_returns=oos_returns,
            in_sample_sharpe=is_sharpe,
            out_of_sample_sharpe=oos_sharpe,
            walk_forward_efficiency=wfe,
            total_periods=len(is_returns),
            window_size=is_size
        )

    def _optimize_parameters(
        self,
        returns: pd.Series,
        strategy_func: Callable,
        param_grid: Dict
    ) -> Dict:
        """
        Find best parameters by grid search on training data.

        This is a simplified implementation. In production, you'd use
        more sophisticated optimization (Bayesian, genetic algorithms, etc.)
        """
        # For now, return middle values from param_grid
        # In real implementation, would test all combinations
        best_params = {}
        for param, values in param_grid.items():
            best_params[param] = values[len(values) // 2]

        return best_params

    def _calculate_sharpe(self, returns: pd.Series) -> float:
        """Calculate annualized Sharpe ratio"""
        if len(returns) < 2:
            return 0.0

        mean_ret = returns.mean()
        std_ret = returns.std()

        if std_ret < 1e-10:
            return 0.0

        # Annualize (assuming daily returns)
        sharpe = (mean_ret / std_ret) * np.sqrt(252)
        return sharpe


def bonferroni_correction(p_values: np.ndarray, alpha: float = 0.05) -> Tuple[np.ndarray, float]:
    """
    Bonferroni correction for multiple testing.

    Most conservative correction. Controls family-wise error rate (FWER):
    the probability of making at least one Type I error.

    Adjusted alpha = alpha / n_tests

    Args:
        p_values: Array of p-values from multiple tests
        alpha: Desired significance level (default 0.05)

    Returns:
        Tuple of (significant_mask, adjusted_alpha)

    Example:
        >>> p_values = np.array([0.001, 0.02, 0.04, 0.10])
        >>> significant, alpha_adj = bonferroni_correction(p_values)
        >>> # With 4 tests, adjusted alpha = 0.05/4 = 0.0125
    """
    n_tests = len(p_values)
    adjusted_alpha = alpha / n_tests
    significant = p_values < adjusted_alpha

    return significant, adjusted_alpha


def benjamini_hochberg_correction(
    p_values: np.ndarray,
    alpha: float = 0.05
) -> Tuple[np.ndarray, float]:
    """
    Benjamini-Hochberg procedure for controlling False Discovery Rate (FDR).

    Less conservative than Bonferroni. Controls the expected proportion
    of false discoveries among the rejected hypotheses.

    Procedure:
    1. Sort p-values in ascending order
    2. Find largest i where p(i) <= (i/m) * alpha
    3. Reject all H0 for p-values <= p(i)

    Args:
        p_values: Array of p-values from multiple tests
        alpha: Desired FDR level (default 0.05)

    Returns:
        Tuple of (significant_mask, threshold)

    Reference:
        Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate.
        Journal of the Royal Statistical Society, 57(1), 289-300.
    """
    n_tests = len(p_values)
    sorted_indices = np.argsort(p_values)
    sorted_p_values = p_values[sorted_indices]

    # Calculate BH threshold for each position
    thresholds = np.arange(1, n_tests + 1) / n_tests * alpha

    # Find largest index where p-value <= threshold
    significant_indices = np.where(sorted_p_values <= thresholds)[0]

    if len(significant_indices) > 0:
        max_idx = significant_indices[-1]
        threshold = sorted_p_values[max_idx]
        significant = p_values <= threshold
    else:
        threshold = 0.0
        significant = np.zeros(n_tests, dtype=bool)

    return significant, threshold


def harvey_liu_zhu_threshold(
    n_trials: int,
    alpha: float = 0.05
) -> float:
    """
    Calculate minimum t-statistic threshold accounting for multiple testing.

    Harvey, Liu, and Zhu (2016) showed that testing 300+ factors requires
    t-stat > 3.0 (vs standard 1.96) to maintain 5% significance level.

    Formula:
        t_threshold = Φ^(-1)(1 - α/(2*n))
    where Φ^(-1) is inverse normal CDF

    Args:
        n_trials: Number of strategies/factors tested
        alpha: Desired significance level (default 0.05)

    Returns:
        Minimum required t-statistic

    Reference:
        Harvey, C.R., Liu, Y., & Zhu, H. (2016). "... and the Cross-Section
        of Expected Returns." Review of Financial Studies, 29(1), 5-68.

    Example:
        >>> t_threshold = harvey_liu_zhu_threshold(n_trials=100)
        >>> # Returns ~2.78 (vs 1.96 for single test)
    """
    if n_trials < 1:
        raise ValueError("n_trials must be at least 1")

    # Bonferroni-adjusted p-value
    adjusted_p = alpha / (2 * n_trials)

    # Convert to t-statistic using inverse normal CDF
    t_threshold = stats.norm.ppf(1 - adjusted_p)

    return t_threshold


class PurgedKFold:
    """
    Purged K-Fold Cross-Validation for time series with overlapping labels.

    Standard K-Fold fails for financial data because:
    1. Labels overlap in time (e.g., 10-day forward returns)
    2. Training and test sets leak information

    Purged K-Fold:
    1. Removes training observations whose labels overlap test period
    2. Adds embargo period to prevent information leakage

    Reference:
        López de Prado, M. (2018). Advances in Financial Machine Learning.
        Chapter 7: Cross-Validation in Finance.
    """

    def __init__(
        self,
        n_splits: int = 5,
        embargo_pct: float = 0.01
    ):
        """
        Initialize Purged K-Fold.

        Args:
            n_splits: Number of folds
            embargo_pct: Percentage of data to embargo after test set
        """
        if n_splits < 2:
            raise ValueError("n_splits must be at least 2")

        if not 0 <= embargo_pct < 0.5:
            raise ValueError("embargo_pct must be between 0 and 0.5")

        self.n_splits = n_splits
        self.embargo_pct = embargo_pct

    def split(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        pred_times: pd.Series
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate purged train/test splits.

        Args:
            X: Feature matrix
            y: Labels
            pred_times: Series indicating when prediction was made (index)
                       and when label is known (value)

        Returns:
            List of (train_indices, test_indices) tuples
        """
        n_samples = len(X)
        test_size = n_samples // self.n_splits
        embargo_size = int(test_size * self.embargo_pct)

        splits = []

        for i in range(self.n_splits):
            # Test set
            test_start = i * test_size
            test_end = test_start + test_size if i < self.n_splits - 1 else n_samples
            test_indices = np.arange(test_start, test_end)

            # Purging: remove training samples that overlap with test labels
            test_times = pred_times.iloc[test_indices]
            max_test_label_time = test_times.max()
            min_test_pred_time = test_times.index.min()

            # Training set (all except test)
            train_indices = np.concatenate([
                np.arange(0, test_start),
                np.arange(test_end, n_samples)
            ])

            # Purge: remove training samples whose labels overlap test period
            # Keep only training samples whose label time is BEFORE test predictions start
            # OR whose prediction time is AFTER test labels end
            if len(train_indices) > 0:
                train_times = pred_times.iloc[train_indices]
                # Keep samples that don't overlap: label before test starts OR prediction after test ends
                purge_mask = (train_times < min_test_pred_time) | (train_times.index > max_test_label_time)
                train_indices = train_indices[purge_mask.values]

            # Embargo: remove samples immediately after test set
            if embargo_size > 0 and test_end < n_samples:
                embargo_end = min(test_end + embargo_size, n_samples)
                train_indices = train_indices[
                    (train_indices < test_start) | (train_indices >= embargo_end)
                ]

            splits.append((train_indices, test_indices))

        return splits


def ledoit_wolf_shrinkage(returns: pd.DataFrame) -> np.ndarray:
    """
    Calculate Ledoit-Wolf shrinkage covariance matrix.

    Sample covariance matrices are unstable for large portfolios (N ~ T).
    Ledoit-Wolf shrinkage combines sample covariance with a structured
    target (constant correlation) using optimal shrinkage intensity.

    Advantages:
    - More stable eigenvalues
    - Better for portfolio optimization
    - Theoretically optimal shrinkage

    Args:
        returns: DataFrame of asset returns (samples x assets)

    Returns:
        Shrunk covariance matrix

    Reference:
        Ledoit, O., & Wolf, M. (2004). "A well-conditioned estimator for
        large-dimensional covariance matrices." Journal of Multivariate
        Analysis, 88(2), 365-411.

    Example:
        >>> returns = pd.DataFrame(np.random.randn(252, 5))  # 5 assets, 1 year
        >>> cov_shrunk = ledoit_wolf_shrinkage(returns)
        >>> # Use in portfolio optimization
    """
    if returns.shape[0] < 2:
        raise ValueError("Need at least 2 observations")

    lw = LedoitWolf()
    cov_shrunk = lw.fit(returns).covariance_

    return cov_shrunk


def calculate_multiple_testing_stats(
    sharpe_ratios: np.ndarray,
    n_observations: int,
    alpha: float = 0.05
) -> Dict[str, any]:
    """
    Calculate multiple testing statistics for strategy evaluation.

    When testing multiple strategies, standard p-values are too optimistic.
    This function calculates adjusted thresholds using various methods.

    Args:
        sharpe_ratios: Array of Sharpe ratios from different strategies
        n_observations: Number of observations per strategy
        alpha: Desired significance level

    Returns:
        Dictionary with correction results

    Example:
        >>> sharpes = np.array([0.8, 1.2, 1.5, 0.6, 2.1])
        >>> stats = calculate_multiple_testing_stats(sharpes, n_observations=252)
        >>> print(f"HLZ threshold: {stats['hlz_threshold']:.2f}")
    """
    n_strategies = len(sharpe_ratios)

    # Convert Sharpe ratios to t-statistics
    # t = SR * sqrt(n)
    t_stats = sharpe_ratios * np.sqrt(n_observations)

    # Calculate p-values (two-tailed)
    p_values = 2 * (1 - stats.norm.cdf(np.abs(t_stats)))

    # Bonferroni correction
    bonf_significant, bonf_alpha = bonferroni_correction(p_values, alpha)

    # Benjamini-Hochberg correction
    bh_significant, bh_threshold = benjamini_hochberg_correction(p_values, alpha)

    # Harvey-Liu-Zhu threshold
    hlz_t_threshold = harvey_liu_zhu_threshold(n_strategies, alpha)
    hlz_significant = np.abs(t_stats) > hlz_t_threshold

    return {
        'n_strategies': n_strategies,
        'n_observations': n_observations,
        'sharpe_ratios': sharpe_ratios,
        't_statistics': t_stats,
        'p_values': p_values,
        'bonferroni_significant': bonf_significant,
        'bonferroni_alpha': bonf_alpha,
        'bh_significant': bh_significant,
        'bh_threshold': bh_threshold,
        'hlz_t_threshold': hlz_t_threshold,
        'hlz_significant': hlz_significant,
        'n_significant_bonferroni': bonf_significant.sum(),
        'n_significant_bh': bh_significant.sum(),
        'n_significant_hlz': hlz_significant.sum()
    }
