"""Statistical Validation & Risk Analytics — Phase 6 MCP Tools.

Institutional-grade statistical validation for trading strategies:
- Brooks pattern win rate backtesting via historical detection + triple-barrier
- Portfolio correlation matrix & risk attribution (MCR/CCR)
- Monte Carlo stress testing with scenario analysis
- Kelly criterion edge quantification
- Prediction model decay detection

MCP tools (7):
    validate_brooks_pattern_win_rate   — Backtest a Brooks pattern on historical data
    calculate_portfolio_correlation    — Correlation matrix + risk attribution
    run_monte_carlo_stress_test        — Monte Carlo VaR + scenario analysis
    recommend_kelly_position_size      — Kelly criterion position sizing
    quantify_pattern_edge              — Edge calculation per pattern
    detect_model_decay                 — Rolling accuracy drop detection
    calculate_drawdown_analysis        — Max drawdown, Calmar ratio, recovery time

Reference:
    López de Prado — "Advances in Financial Machine Learning" (Chapters 3, 5, 7, 10)
    Hull — "Options, Futures, and Other Derivatives" (Chapter 19)
    McMillan — "Options as a Strategic Investment" (Chapter 36-41)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================================
# Helper: convert numpy types to JSON-safe Python types
# ============================================================================
def _safe(val):
    """Convert numpy/pandas types to native Python for JSON serialization."""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, (np.ndarray,)):
        return val.tolist()
    if isinstance(val, (pd.Timestamp,)):
        return val.isoformat()
    if pd.isna(val):
        return None
    return val


def _round_dict(d: dict, decimals: int = 4) -> dict:
    """Round all float values in a dict."""
    return {k: round(v, decimals) if isinstance(v, float) else v for k, v in d.items()}


# ============================================================================
# 1. Brooks Pattern Win Rate Backtesting
# ============================================================================

def _validate_brooks_pattern_impl(
    ticker: str,
    pattern_id: str = "auto",
    lookback_days: int = 504,
    holding_period: int = 10,
    profit_target_pct: float = 5.0,
    stop_loss_pct: float = 5.0,
) -> dict[str, Any]:
    """
    Backtest a specific Brooks pattern on historical data using triple-barrier labeling.

    1. Fetch 2+ years of price history
    2. Run AlBrooksAnalyzer.detect_pattern() on each bar
    3. When pattern_id matches, apply triple-barrier to measure outcome
    4. Calculate win rate, risk/reward, confidence interval
    """
    from ..scanner_analyzer import AlBrooksAnalyzer
    from ..core.price import get_price_history_questrade_first
    from ..ml_core import apply_triple_barrier_labels

    try:
        # Fetch historical data
        period = f"{max(lookback_days // 252, 2)}y"
        df = get_price_history_questrade_first(ticker, period=period)

        if df is None or len(df) < 100:
            return {"error": f"Insufficient data for {ticker} ({len(df) if df is not None else 0} bars)"}

        # Flatten MultiIndex if needed
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Ensure DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        analyzer = AlBrooksAnalyzer()

        # Pattern detection — scan each bar window
        all_patterns = analyzer.LONG_PATTERNS.copy()
        all_patterns.update(analyzer.SHORT_PATTERNS)

        pattern_occurrences = []
        min_window = 20  # Need 20 bars for pattern detection

        closes = df['Close']
        highs = df['High']
        lows = df['Low']

        # Scan through history detecting patterns
        for i in range(min_window, len(df) - holding_period):
            window = df.iloc[max(0, i - 50):i + 1]

            if len(window) < min_window:
                continue

            # Simplified pattern detection using price action characteristics
            detected = _detect_pattern_at_bar(window, closes, highs, lows, i)

            if detected and (pattern_id == "auto" or detected == pattern_id):
                # Record this occurrence
                entry_price = float(closes.iloc[i])
                future_prices = closes.iloc[i:i + holding_period + 1]

                if len(future_prices) < holding_period:
                    continue

                # Apply triple-barrier
                upper = entry_price * (1 + profit_target_pct / 100)
                lower = entry_price * (1 - stop_loss_pct / 100)

                outcome = "time"
                exit_price = float(future_prices.iloc[-1])
                exit_day = holding_period

                for j in range(1, len(future_prices)):
                    p = float(future_prices.iloc[j])
                    if p >= upper:
                        outcome = "profit"
                        exit_price = p
                        exit_day = j
                        break
                    elif p <= lower:
                        outcome = "stop"
                        exit_price = p
                        exit_day = j
                        break

                ret = (exit_price - entry_price) / entry_price
                pattern_occurrences.append({
                    "date": df.index[i].isoformat(),
                    "pattern": detected,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "return_pct": round(ret * 100, 2),
                    "outcome": outcome,
                    "days_held": exit_day,
                })

        if not pattern_occurrences:
            return {
                "ticker": ticker,
                "pattern_id": pattern_id,
                "error": f"No occurrences of pattern '{pattern_id}' found in {lookback_days} days",
                "suggestion": "Try pattern_id='auto' to detect all patterns",
            }

        # Aggregate statistics
        returns = [o["return_pct"] for o in pattern_occurrences]
        outcomes = [o["outcome"] for o in pattern_occurrences]
        n = len(pattern_occurrences)

        wins = sum(1 for o in outcomes if o == "profit")
        losses = sum(1 for o in outcomes if o == "stop")
        timeouts = sum(1 for o in outcomes if o == "time")

        win_rate = wins / n if n > 0 else 0
        avg_return = np.mean(returns)
        avg_win = np.mean([r for r in returns if r > 0]) if any(r > 0 for r in returns) else 0
        avg_loss = np.mean([r for r in returns if r < 0]) if any(r < 0 for r in returns) else 0
        risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        # 95% confidence interval for win rate (Wilson score)
        from scipy import stats as scipy_stats
        z = 1.96
        denominator = 1 + z**2 / n
        center = (win_rate + z**2 / (2 * n)) / denominator
        margin = z * np.sqrt((win_rate * (1 - win_rate) + z**2 / (4 * n)) / n) / denominator
        ci_low = max(0, center - margin)
        ci_high = min(1, center + margin)

        # Pattern breakdown
        pattern_counts = {}
        for o in pattern_occurrences:
            p = o["pattern"]
            if p not in pattern_counts:
                pattern_counts[p] = {"total": 0, "wins": 0, "returns": []}
            pattern_counts[p]["total"] += 1
            if o["outcome"] == "profit":
                pattern_counts[p]["wins"] += 1
            pattern_counts[p]["returns"].append(o["return_pct"])

        pattern_breakdown = {}
        for p, data in pattern_counts.items():
            pattern_breakdown[p] = {
                "occurrences": data["total"],
                "win_rate": round(data["wins"] / data["total"], 4) if data["total"] > 0 else 0,
                "avg_return_pct": round(np.mean(data["returns"]), 2),
                "expected_win_rate": AlBrooksAnalyzer.PATTERN_LESSONS.get(p, {}).get("win_rate", "unknown"),
            }

        # Get expected win rate from PATTERN_LESSONS for comparison
        expected = AlBrooksAnalyzer.PATTERN_LESSONS.get(pattern_id, {}).get("win_rate", "unknown")

        return {
            "ticker": ticker,
            "pattern_id": pattern_id,
            "lookback_days": lookback_days,
            "holding_period": holding_period,
            "profit_target_pct": profit_target_pct,
            "stop_loss_pct": stop_loss_pct,

            "results": {
                "total_occurrences": n,
                "wins": wins,
                "losses": losses,
                "timeouts": timeouts,
                "win_rate": round(win_rate, 4),
                "avg_return_pct": round(avg_return, 2),
                "avg_win_pct": round(avg_win, 2),
                "avg_loss_pct": round(avg_loss, 2),
                "risk_reward_ratio": round(risk_reward, 2) if risk_reward != float('inf') else "inf",
                "confidence_interval_95": {
                    "lower": round(ci_low, 4),
                    "upper": round(ci_high, 4),
                },
                "expected_win_rate": expected,
            },

            "pattern_breakdown": pattern_breakdown,

            "sample_trades": pattern_occurrences[-10:],  # Last 10

            "statistical_validity": {
                "sample_size": n,
                "sufficient": n >= 30,
                "note": f"{'Sufficient' if n >= 30 else 'Insufficient'} sample size (n={n}, need 30+)",
            },

            "methodology": "Triple-barrier labeling on historical Brooks pattern detections",
        }

    except Exception as e:
        logger.error(f"Brooks pattern validation failed: {e}", exc_info=True)
        return {"error": str(e), "ticker": ticker, "pattern_id": pattern_id}


def _detect_pattern_at_bar(window, closes, highs, lows, idx):
    """Simplified pattern detection at a specific bar index."""
    if len(window) < 15:
        return None

    c = window['Close'].values
    h = window['High'].values
    l = window['Low'].values

    # Use last 10-15 bars for pattern detection
    recent = c[-10:]

    # Simple trend detection
    sma_10 = np.mean(c[-10:])
    sma_20 = np.mean(c[-20:]) if len(c) >= 20 else sma_10
    current = c[-1]
    prev = c[-2] if len(c) >= 2 else current

    uptrend = sma_10 > sma_20
    downtrend = sma_10 < sma_20

    # Pullback detection
    if len(c) >= 5:
        recent_high = max(h[-5:])
        recent_low = min(l[-5:])
        pullback_from_high = (recent_high - current) / recent_high if recent_high > 0 else 0
        pullback_from_low = (current - recent_low) / recent_low if recent_low > 0 else 0
    else:
        return None

    # Count consecutive down bars in uptrend (pullback depth)
    down_bars = 0
    for k in range(len(c) - 1, max(len(c) - 6, 0), -1):
        if c[k] < c[k-1]:
            down_bars += 1
        else:
            break

    up_bars = 0
    for k in range(len(c) - 1, max(len(c) - 6, 0), -1):
        if c[k] > c[k-1]:
            up_bars += 1
        else:
            break

    # Detect patterns
    if uptrend:
        if down_bars == 1 and current > prev:
            return 'high_1'
        elif down_bars == 2 and current > prev:
            return 'high_2'
        elif down_bars >= 3 and current > prev:
            return 'high_3'
        elif pullback_from_high > 0.02 and current > prev and current > sma_10:
            return 'ema_bounce'
        elif len(c) >= 10:
            # Double bottom check
            low1 = min(l[-10:-5])
            low2 = min(l[-5:])
            if abs(low1 - low2) / low1 < 0.01 and current > prev:
                return 'double_bottom'
            # Higher low
            if low2 > low1 and current > prev:
                return 'higher_low'

    elif downtrend:
        if up_bars == 1 and current < prev:
            return 'low_1'
        elif up_bars == 2 and current < prev:
            return 'low_2'
        elif up_bars >= 3 and current < prev:
            return 'low_3'
        elif pullback_from_low > 0.02 and current < prev and current < sma_10:
            return 'ema_rejection'
        elif len(c) >= 10:
            high1 = max(h[-10:-5])
            high2 = max(h[-5:])
            if abs(high1 - high2) / high1 < 0.01 and current < prev:
                return 'double_top'
            if high2 < high1 and current < prev:
                return 'lower_high'

    # Breakout/breakdown patterns (trend-neutral)
    if len(c) >= 15:
        range_5 = max(h[-5:]) - min(l[-5:])
        range_15 = max(h[-15:]) - min(l[-15:])
        if range_15 > 0 and range_5 / range_15 < 0.3:
            # Tight range detected
            if current > max(h[-10:-1]):
                return 'tight_trading_range_breakout'

    return None


# ============================================================================
# 2. Portfolio Correlation Matrix & Risk Attribution
# ============================================================================

def _calculate_correlation_impl(
    account_number: str,
    method: str = "pearson",
    lookback_days: int = 252,
) -> dict[str, Any]:
    """
    Calculate portfolio correlation matrix and risk attribution.

    Returns:
    - Correlation matrix between all positions
    - Marginal Contribution to Risk (MCR) per position
    - Component Contribution to Risk (CCR) per position
    - Cluster analysis (highly correlated groups)
    """
    from .questrade_api import get_questrade_positions_impl as get_positions
    from ..core.price import get_price_history_questrade_first

    try:
        positions_data = get_positions(account_number)
        if not positions_data or 'positions' not in positions_data:
            return {"error": "Could not fetch positions"}

        positions = [p for p in positions_data['positions'] if p.get('openQuantity', 0) > 0]
        if len(positions) < 2:
            return {"error": "Need at least 2 positions for correlation analysis"}

        # Fetch price history for each position
        import re
        returns_dict = {}
        weights = {}
        total_value = sum(p.get('currentMarketValue', 0) for p in positions)

        if total_value <= 0:
            return {"error": "Portfolio has no value"}

        for pos in positions:
            symbol = pos.get('symbol', '')
            if not symbol:
                continue

            # Extract underlying for options
            ticker = symbol
            match = re.match(r'^([A-Z]+)', symbol)
            if match and ('.' in symbol or len(symbol) > 6):
                ticker = match.group(1)

            market_value = pos.get('currentMarketValue', 0)
            weights[symbol] = market_value / total_value

            try:
                period = "12mo" if lookback_days > 180 else "6mo"
                hist = get_price_history_questrade_first(ticker, period=period)
                if hist is not None and len(hist) >= 30:
                    if isinstance(hist.columns, pd.MultiIndex):
                        hist.columns = hist.columns.get_level_values(0)
                    returns_dict[symbol] = hist['Close'].pct_change().dropna()
            except Exception as e:
                logger.warning(f"Skipping {symbol}: {e}")
                continue

        if len(returns_dict) < 2:
            return {"error": "Could not fetch returns for enough positions"}

        # Align dates
        returns_df = pd.DataFrame(returns_dict).dropna()

        if len(returns_df) < 30:
            return {"error": f"Insufficient overlapping data ({len(returns_df)} days, need 30+)"}

        # Correlation matrix
        if method == "spearman":
            corr_matrix = returns_df.corr(method='spearman')
        else:
            corr_matrix = returns_df.corr(method='pearson')

        # Covariance matrix (annualized)
        cov_matrix = returns_df.cov() * 252

        # Weight vector (aligned with returns_df columns)
        w = np.array([weights.get(col, 0) for col in returns_df.columns])
        w_sum = w.sum()
        if w_sum > 0:
            w = w / w_sum  # Normalize

        # Portfolio variance
        portfolio_var = float(w @ cov_matrix.values @ w)
        portfolio_vol = np.sqrt(portfolio_var) if portfolio_var > 0 else 0

        # Marginal Contribution to Risk (MCR)
        # MCR_i = (Σ * w)_i / σ_p
        sigma_w = cov_matrix.values @ w
        mcr = sigma_w / portfolio_vol if portfolio_vol > 0 else sigma_w

        # Component Contribution to Risk (CCR)
        # CCR_i = w_i * MCR_i
        ccr = w * mcr

        # Risk attribution dict
        risk_attribution = {}
        for i, col in enumerate(returns_df.columns):
            risk_attribution[col] = {
                "weight_pct": round(float(w[i]) * 100, 2),
                "marginal_contribution": round(float(mcr[i]), 6),
                "component_contribution": round(float(ccr[i]), 6),
                "pct_of_portfolio_risk": round(float(ccr[i] / portfolio_var * 100), 2) if portfolio_var > 0 else 0,
                "annualized_vol": round(float(np.sqrt(cov_matrix.iloc[i, i])), 4),
            }

        # Cluster analysis — find highly correlated pairs (r > 0.7)
        high_corr_pairs = []
        cols = corr_matrix.columns.tolist()
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                r = float(corr_matrix.iloc[i, j])
                if abs(r) > 0.7:
                    high_corr_pairs.append({
                        "pair": f"{cols[i]} / {cols[j]}",
                        "correlation": round(r, 4),
                        "risk": "HIGH" if abs(r) > 0.85 else "MODERATE",
                        "combined_weight_pct": round((float(w[i]) + float(w[j])) * 100, 2),
                    })

        # Format correlation matrix for output
        corr_output = {}
        for col in corr_matrix.columns:
            corr_output[col] = {c: round(float(corr_matrix.loc[col, c]), 4) for c in corr_matrix.columns}

        diversification_ratio = (sum(float(w[i]) * float(np.sqrt(cov_matrix.iloc[i, i])) for i in range(len(w))) / portfolio_vol) if portfolio_vol > 0 else 1.0

        return {
            "account_number": account_number,
            "positions_analyzed": len(returns_df.columns),
            "data_points": len(returns_df),
            "method": method,

            "correlation_matrix": corr_output,

            "risk_attribution": risk_attribution,

            "portfolio_metrics": {
                "annualized_volatility": round(portfolio_vol, 4),
                "annualized_variance": round(portfolio_var, 6),
                "diversification_ratio": round(float(diversification_ratio), 4),
                "diversification_benefit": round((1 - 1 / float(diversification_ratio)) * 100, 2) if diversification_ratio > 1 else 0,
            },

            "high_correlation_pairs": high_corr_pairs,

            "warnings": [
                f"High correlation detected: {p['pair']} (r={p['correlation']}, combined {p['combined_weight_pct']}%)"
                for p in high_corr_pairs if p['risk'] == 'HIGH'
            ],

            "methodology": f"{method.title()} correlation with annualized covariance, MCR/CCR decomposition",
        }

    except Exception as e:
        logger.error(f"Correlation analysis failed: {e}", exc_info=True)
        return {"error": str(e), "account_number": account_number}


# ============================================================================
# 3. Monte Carlo Stress Testing
# ============================================================================

def _monte_carlo_stress_test_impl(
    account_number: str,
    n_simulations: int = 5000,
    time_horizon_days: int = 21,
    lookback_days: int = 252,
) -> dict[str, Any]:
    """
    Run Monte Carlo simulation + stress test scenarios on portfolio.

    Uses Geometric Brownian Motion calibrated from historical returns.
    Includes historical crash replays and hypothetical scenarios.
    """
    from .questrade_api import (
        get_questrade_positions_impl as get_positions,
        get_questrade_balances_impl as get_balances,
    )
    from ..core.price import get_price_history_questrade_first

    try:
        # Get portfolio value
        balances = get_balances(account_number)
        portfolio_value = balances.get('perCurrencyBalances', [{}])[0].get('totalEquity', 0)

        positions_data = get_positions(account_number)
        if not positions_data or 'positions' not in positions_data:
            return {"error": "Could not fetch positions"}

        positions = [p for p in positions_data['positions'] if p.get('openQuantity', 0) > 0]
        if not positions:
            return {"error": "No open positions"}

        if portfolio_value <= 0:
            portfolio_value = sum(p.get('currentMarketValue', 0) for p in positions)

        # Collect returns for portfolio
        import re
        all_returns = []
        total_value = sum(p.get('currentMarketValue', 0) for p in positions)

        for pos in positions:
            symbol = pos.get('symbol', '')
            if not symbol:
                continue

            ticker = symbol
            match = re.match(r'^([A-Z]+)', symbol)
            if match and ('.' in symbol or len(symbol) > 6):
                ticker = match.group(1)

            weight = pos.get('currentMarketValue', 0) / total_value if total_value > 0 else 0

            try:
                hist = get_price_history_questrade_first(ticker, period="12mo")
                if hist is not None and len(hist) >= 30:
                    if isinstance(hist.columns, pd.MultiIndex):
                        hist.columns = hist.columns.get_level_values(0)
                    rets = hist['Close'].pct_change().dropna() * weight
                    all_returns.append(rets)
            except Exception:
                continue

        if not all_returns:
            return {"error": "Could not fetch returns for any position"}

        portfolio_returns = pd.concat(all_returns, axis=1).sum(axis=1).dropna()

        if len(portfolio_returns) < 30:
            return {"error": f"Insufficient return data ({len(portfolio_returns)} days)"}

        # Calibrate GBM parameters
        mu = float(portfolio_returns.mean())
        sigma = float(portfolio_returns.std())

        # Monte Carlo simulation
        np.random.seed(42)
        dt = 1  # Daily
        final_values = np.zeros(n_simulations)

        for sim in range(n_simulations):
            path_value = portfolio_value
            for day in range(time_horizon_days):
                z = np.random.standard_normal()
                daily_return = mu + sigma * z
                path_value *= (1 + daily_return)
            final_values[sim] = path_value

        # P&L distribution
        pnl = final_values - portfolio_value
        pnl_pct = (final_values / portfolio_value - 1) * 100

        # Percentiles
        percentiles = {
            "p1": round(float(np.percentile(pnl, 1)), 2),
            "p5": round(float(np.percentile(pnl, 5)), 2),
            "p10": round(float(np.percentile(pnl, 10)), 2),
            "p25": round(float(np.percentile(pnl, 25)), 2),
            "p50_median": round(float(np.percentile(pnl, 50)), 2),
            "p75": round(float(np.percentile(pnl, 75)), 2),
            "p90": round(float(np.percentile(pnl, 90)), 2),
            "p95": round(float(np.percentile(pnl, 95)), 2),
            "p99": round(float(np.percentile(pnl, 99)), 2),
        }

        # VaR and CVaR from simulation
        var_95 = abs(float(np.percentile(pnl, 5)))
        var_99 = abs(float(np.percentile(pnl, 1)))
        cvar_95 = abs(float(np.mean(pnl[pnl <= np.percentile(pnl, 5)])))
        cvar_99 = abs(float(np.mean(pnl[pnl <= np.percentile(pnl, 1)])))

        # Stress test scenarios
        stress_scenarios = {
            "market_crash_10pct": {
                "description": "Market drops 10%",
                "portfolio_loss": round(-portfolio_value * 0.10, 2),
                "portfolio_loss_pct": -10.0,
            },
            "market_crash_20pct": {
                "description": "2008-style 20% drop",
                "portfolio_loss": round(-portfolio_value * 0.20, 2),
                "portfolio_loss_pct": -20.0,
            },
            "covid_crash_35pct": {
                "description": "COVID-style 35% crash",
                "portfolio_loss": round(-portfolio_value * 0.35, 2),
                "portfolio_loss_pct": -35.0,
            },
            "vol_spike_50pct": {
                "description": "VIX doubles, volatility +50%",
                "portfolio_loss": round(-portfolio_value * sigma * np.sqrt(time_horizon_days) * 1.5, 2),
                "portfolio_loss_pct": round(-sigma * np.sqrt(time_horizon_days) * 1.5 * 100, 2),
            },
            "flash_crash_5pct_1day": {
                "description": "Flash crash: 5% single-day drop",
                "portfolio_loss": round(-portfolio_value * 0.05, 2),
                "portfolio_loss_pct": -5.0,
            },
            "rate_shock_3pct": {
                "description": "Rate shock: yields +100bp, equities -3%",
                "portfolio_loss": round(-portfolio_value * 0.03, 2),
                "portfolio_loss_pct": -3.0,
            },
        }

        # Probability of loss
        prob_loss = float(np.mean(pnl < 0))
        prob_loss_5pct = float(np.mean(pnl_pct < -5))
        prob_loss_10pct = float(np.mean(pnl_pct < -10))
        prob_gain_5pct = float(np.mean(pnl_pct > 5))

        return {
            "account_number": account_number,
            "portfolio_value": round(portfolio_value, 2),
            "n_simulations": n_simulations,
            "time_horizon_days": time_horizon_days,

            "calibration": {
                "daily_mean_return": round(mu, 6),
                "daily_volatility": round(sigma, 6),
                "annualized_return": round(mu * 252 * 100, 2),
                "annualized_volatility": round(sigma * np.sqrt(252) * 100, 2),
                "data_points": len(portfolio_returns),
            },

            "monte_carlo_results": {
                "var_95": round(var_95, 2),
                "var_99": round(var_99, 2),
                "cvar_95_expected_shortfall": round(cvar_95, 2),
                "cvar_99_expected_shortfall": round(cvar_99, 2),
                "var_95_pct": round(var_95 / portfolio_value * 100, 2),
                "var_99_pct": round(var_99 / portfolio_value * 100, 2),
                "expected_pnl": round(float(np.mean(pnl)), 2),
                "pnl_std": round(float(np.std(pnl)), 2),
            },

            "pnl_percentiles": percentiles,

            "probability_analysis": {
                "prob_any_loss": round(prob_loss, 4),
                "prob_loss_gt_5pct": round(prob_loss_5pct, 4),
                "prob_loss_gt_10pct": round(prob_loss_10pct, 4),
                "prob_gain_gt_5pct": round(prob_gain_5pct, 4),
            },

            "stress_scenarios": stress_scenarios,

            "risk_level": (
                "LOW" if var_95 / portfolio_value < 0.02
                else "MODERATE" if var_95 / portfolio_value < 0.05
                else "HIGH" if var_95 / portfolio_value < 0.10
                else "EXTREME"
            ),

            "interpretation": {
                "var_statement": f"With 95% confidence, max {time_horizon_days}-day loss is ${var_95:,.0f} ({var_95/portfolio_value*100:.1f}%)",
                "cvar_statement": f"If VaR breached, average loss is ${cvar_95:,.0f} ({cvar_95/portfolio_value*100:.1f}%)",
                "median_outcome": f"Median outcome over {time_horizon_days} days: ${percentiles['p50_median']:+,.0f}",
            },

            "methodology": f"GBM Monte Carlo ({n_simulations} paths, {time_horizon_days}-day horizon) calibrated on {len(portfolio_returns)} days of history",
        }

    except Exception as e:
        logger.error(f"Monte Carlo stress test failed: {e}", exc_info=True)
        return {"error": str(e), "account_number": account_number}


# ============================================================================
# 4. Kelly Criterion Position Sizing
# ============================================================================

def _kelly_position_size_impl(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    account_value: float = 100000,
    kelly_fraction: float = 0.25,
    max_position_pct: float = 10.0,
) -> dict[str, Any]:
    """
    Calculate optimal position size using Kelly Criterion.

    Kelly formula: f* = (p * b - q) / b
    where p = win probability, q = 1-p, b = win/loss ratio
    """
    try:
        if not 0 < win_rate < 1:
            return {"error": "win_rate must be between 0 and 1 (exclusive)"}
        if avg_win_pct <= 0:
            return {"error": "avg_win_pct must be positive"}
        if avg_loss_pct >= 0:
            return {"error": "avg_loss_pct must be negative"}

        p = win_rate
        q = 1 - p
        b = abs(avg_win_pct / avg_loss_pct)  # Win/loss ratio

        # Kelly formula
        kelly_full = (p * b - q) / b
        kelly_half = kelly_full * 0.5
        kelly_quarter = kelly_full * 0.25
        kelly_user = kelly_full * kelly_fraction

        # Edge calculation
        edge = p * avg_win_pct + q * avg_loss_pct  # Expected return per trade
        edge_per_dollar = edge / 100

        # Position sizing
        position_pct = min(kelly_user * 100, max_position_pct)
        position_dollars = account_value * position_pct / 100

        # Expected value per trade
        ev_per_trade = position_dollars * edge_per_dollar

        # Risk of ruin (simplified)
        if edge > 0 and abs(avg_loss_pct) > 0:
            # Approximate risk of ruin using Kelly
            ror = ((1 - kelly_full) / (1 + kelly_full)) ** 100 if kelly_full > 0 else 1.0
            ror = min(ror, 1.0)
        else:
            ror = 1.0

        return {
            "inputs": {
                "win_rate": win_rate,
                "avg_win_pct": avg_win_pct,
                "avg_loss_pct": avg_loss_pct,
                "account_value": account_value,
                "kelly_fraction": kelly_fraction,
                "max_position_pct": max_position_pct,
            },

            "kelly_sizing": {
                "full_kelly_pct": round(kelly_full * 100, 2),
                "half_kelly_pct": round(kelly_half * 100, 2),
                "quarter_kelly_pct": round(kelly_quarter * 100, 2),
                "recommended_pct": round(position_pct, 2),
                "recommended_dollars": round(position_dollars, 2),
            },

            "edge_analysis": {
                "edge_per_trade_pct": round(edge, 4),
                "win_loss_ratio": round(b, 4),
                "expected_value_per_trade": round(ev_per_trade, 2),
                "has_positive_edge": edge > 0,
            },

            "risk_metrics": {
                "risk_of_ruin_pct": round(ror * 100, 4),
                "max_drawdown_kelly": round(kelly_full * abs(avg_loss_pct), 2) if kelly_full > 0 else 0,
                "trades_to_double": int(np.ceil(np.log(2) / np.log(1 + edge_per_dollar * kelly_user))) if edge_per_dollar > 0 and kelly_user > 0 else 0,
            },

            "recommendation": (
                f"Position {round(position_pct, 1)}% of account (${position_dollars:,.0f}). "
                f"Edge: {edge:+.2f}% per trade. "
                f"{'TRADE' if edge > 0.5 else 'MARGINAL EDGE' if edge > 0 else 'NO EDGE - DO NOT TRADE'}."
            ),

            "methodology": f"Kelly Criterion at {kelly_fraction:.0%} fraction, capped at {max_position_pct}%",
        }

    except Exception as e:
        logger.error(f"Kelly sizing failed: {e}", exc_info=True)
        return {"error": str(e)}


# ============================================================================
# 5. Pattern Edge Quantification
# ============================================================================

def _quantify_edge_impl(
    ticker: str,
    pattern_id: str = "auto",
    lookback_days: int = 504,
    holding_period: int = 10,
) -> dict[str, Any]:
    """
    Quantify the statistical edge for a specific Brooks pattern.

    Combines win rate backtesting with Kelly criterion to produce
    actionable edge metrics and position sizing.
    """
    try:
        # Run pattern validation first
        validation = _validate_brooks_pattern_impl(
            ticker=ticker,
            pattern_id=pattern_id,
            lookback_days=lookback_days,
            holding_period=holding_period,
        )

        if "error" in validation:
            return validation

        results = validation["results"]
        win_rate = results["win_rate"]
        avg_win = results["avg_win_pct"]
        avg_loss = results["avg_loss_pct"]

        if avg_loss == 0:
            avg_loss = -0.01  # Avoid division by zero

        # Calculate edge
        edge = win_rate * avg_win + (1 - win_rate) * avg_loss

        # Kelly sizing
        b = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        kelly = ((win_rate * b - (1 - win_rate)) / b) if b > 0 else 0

        # Sharpe-like metric: edge / volatility of outcomes
        all_returns = [t["return_pct"] for t in validation.get("sample_trades", [])]
        outcome_vol = float(np.std(all_returns)) if len(all_returns) > 1 else 1.0
        sharpe_like = edge / outcome_vol if outcome_vol > 0 else 0

        # Classify edge quality
        if edge > 2.0:
            edge_quality = "STRONG"
        elif edge > 0.5:
            edge_quality = "MODERATE"
        elif edge > 0:
            edge_quality = "MARGINAL"
        else:
            edge_quality = "NO_EDGE"

        return {
            "ticker": ticker,
            "pattern_id": pattern_id,
            "lookback_days": lookback_days,
            "holding_period": holding_period,

            "edge_metrics": {
                "expected_return_per_trade_pct": round(edge, 4),
                "win_rate": round(win_rate, 4),
                "avg_win_pct": round(avg_win, 2),
                "avg_loss_pct": round(avg_loss, 2),
                "risk_reward_ratio": results["risk_reward_ratio"],
                "edge_quality": edge_quality,
                "sharpe_like_ratio": round(sharpe_like, 4),
            },

            "kelly_sizing": {
                "full_kelly_pct": round(kelly * 100, 2),
                "half_kelly_pct": round(kelly * 50, 2),
                "quarter_kelly_pct": round(kelly * 25, 2),
            },

            "statistical_validity": validation["statistical_validity"],

            "pattern_breakdown": validation.get("pattern_breakdown", {}),

            "recommendation": (
                f"{'TRADE with {:.0f}% of account (quarter-Kelly)'.format(kelly * 25) if edge_quality in ('STRONG', 'MODERATE') and validation['statistical_validity']['sufficient'] else 'SKIP — ' + ('insufficient edge' if edge_quality in ('MARGINAL', 'NO_EDGE') else 'insufficient samples')}"
            ),

            "methodology": "Brooks pattern detection + triple-barrier + Kelly criterion",
        }

    except Exception as e:
        logger.error(f"Edge quantification failed: {e}", exc_info=True)
        return {"error": str(e), "ticker": ticker}


# ============================================================================
# 6. Prediction Model Decay Detection
# ============================================================================

def _detect_decay_impl(
    days: int = 60,
    threshold: float = 0.55,
) -> dict[str, Any]:
    """
    Detect prediction model decay by analyzing rolling accuracy from prediction_tracker.

    Checks if win rates have dropped below threshold in recent windows.
    """
    from ..prediction_tracker import ComponentAnalyzer

    try:
        analyzer = ComponentAnalyzer()

        # Get gate accuracy over different windows
        windows = [30, 60, 90]
        gate_trends = {}
        decay_detected = False
        decay_alerts = []

        for window in windows:
            if window > days:
                continue
            try:
                gate_accuracy = analyzer.analyze_gate_accuracy(days=window)
                if gate_accuracy and "gate_accuracy" in gate_accuracy:
                    for gate_name, gate_data in gate_accuracy["gate_accuracy"].items():
                        if gate_name not in gate_trends:
                            gate_trends[gate_name] = {}

                        pass_rate = gate_data.get("pass_rate", 0)
                        gate_trends[gate_name][f"{window}d"] = round(pass_rate, 4)

                        # Check for decay (recent < threshold)
                        if window == min(windows) and pass_rate < threshold:
                            decay_detected = True
                            decay_alerts.append(
                                f"Gate '{gate_name}' pass rate ({pass_rate:.1%}) below threshold ({threshold:.1%}) in last {window} days"
                            )
            except Exception as e:
                logger.warning(f"Could not analyze {window}d window: {e}")

        # Sub-component analysis
        component_accuracy = {}
        try:
            sub = analyzer.analyze_sub_components(days=days)
            if sub and "categorical_components" in sub:
                for comp_name, comp_data in sub["categorical_components"].items():
                    if isinstance(comp_data, dict):
                        component_accuracy[comp_name] = {
                            k: {
                                "count": v.get("count", 0),
                                "accuracy": round(v.get("accuracy", 0), 4),
                            }
                            for k, v in comp_data.items()
                            if isinstance(v, dict) and "accuracy" in v
                        }
        except Exception as e:
            logger.warning(f"Sub-component analysis failed: {e}")

        # Best/worst predictors
        best_predictors = []
        improvement_areas = []
        try:
            best = analyzer.find_best_predictors(days=days)
            if best:
                best_predictors = best[:5] if isinstance(best, list) else []

            worst = analyzer.find_improvement_areas(days=days, threshold=threshold)
            if worst:
                improvement_areas = worst[:5] if isinstance(worst, list) else []
        except Exception:
            pass

        # Trend analysis: compare 30d vs 60d accuracy
        trend_analysis = {}
        for gate_name, windows_data in gate_trends.items():
            if "30d" in windows_data and "60d" in windows_data:
                delta = windows_data["30d"] - windows_data["60d"]
                trend = "IMPROVING" if delta > 0.05 else "DECLINING" if delta < -0.05 else "STABLE"
                trend_analysis[gate_name] = {
                    "30d_accuracy": windows_data["30d"],
                    "60d_accuracy": windows_data["60d"],
                    "delta": round(delta, 4),
                    "trend": trend,
                }
                if trend == "DECLINING":
                    decay_alerts.append(
                        f"Gate '{gate_name}' declining: {windows_data['60d']:.1%} → {windows_data['30d']:.1%} ({delta:+.1%})"
                    )

        return {
            "analysis_period_days": days,
            "decay_threshold": threshold,
            "decay_detected": decay_detected,

            "gate_trends": gate_trends,
            "trend_analysis": trend_analysis,

            "decay_alerts": decay_alerts,

            "component_accuracy": component_accuracy,

            "best_predictors": best_predictors,
            "improvement_areas": improvement_areas,

            "recommendation": (
                "MODEL DECAY DETECTED — Review strategy parameters and re-calibrate"
                if decay_detected
                else "Model performing within acceptable parameters"
            ),

            "methodology": "Rolling window accuracy analysis from prediction_tracker database",
        }

    except Exception as e:
        logger.error(f"Model decay detection failed: {e}", exc_info=True)
        return {"error": str(e), "days": days}


# ============================================================================
# 7. Drawdown Analysis
# ============================================================================

def _drawdown_analysis_impl(
    account_number: str,
    lookback_days: int = 252,
) -> dict[str, Any]:
    """
    Calculate comprehensive drawdown analysis for portfolio.

    Metrics: max drawdown, drawdown duration, Calmar ratio, recovery time,
    current drawdown state, underwater equity curve.
    """
    from .questrade_api import (
        get_questrade_positions_impl as get_positions,
        get_questrade_balances_impl as get_balances,
    )
    from ..core.price import get_price_history_questrade_first

    try:
        balances = get_balances(account_number)
        portfolio_value = balances.get('perCurrencyBalances', [{}])[0].get('totalEquity', 0)

        positions_data = get_positions(account_number)
        if not positions_data or 'positions' not in positions_data:
            return {"error": "Could not fetch positions"}

        positions = [p for p in positions_data['positions'] if p.get('openQuantity', 0) > 0]
        if not positions:
            return {"error": "No open positions"}

        if portfolio_value <= 0:
            portfolio_value = sum(p.get('currentMarketValue', 0) for p in positions)

        # Build portfolio returns
        import re
        all_returns = []
        total_value = sum(p.get('currentMarketValue', 0) for p in positions)

        for pos in positions:
            symbol = pos.get('symbol', '')
            if not symbol:
                continue

            ticker = symbol
            match = re.match(r'^([A-Z]+)', symbol)
            if match and ('.' in symbol or len(symbol) > 6):
                ticker = match.group(1)

            weight = pos.get('currentMarketValue', 0) / total_value if total_value > 0 else 0

            try:
                hist = get_price_history_questrade_first(ticker, period="12mo")
                if hist is not None and len(hist) >= 30:
                    if isinstance(hist.columns, pd.MultiIndex):
                        hist.columns = hist.columns.get_level_values(0)
                    rets = hist['Close'].pct_change().dropna() * weight
                    all_returns.append(rets)
            except Exception:
                continue

        if not all_returns:
            return {"error": "Could not fetch returns for any position"}

        portfolio_returns = pd.concat(all_returns, axis=1).sum(axis=1).dropna()

        if len(portfolio_returns) < 20:
            return {"error": f"Insufficient data ({len(portfolio_returns)} days)"}

        # Build equity curve
        equity = (1 + portfolio_returns).cumprod() * portfolio_value
        running_max = equity.cummax()
        drawdown = (equity - running_max) / running_max
        drawdown_dollars = equity - running_max

        # Max drawdown
        max_dd_pct = float(drawdown.min())
        max_dd_idx = drawdown.idxmin()
        max_dd_dollars = float(drawdown_dollars.min())

        # Find peak before max drawdown
        peak_idx = running_max[:max_dd_idx].idxmax() if max_dd_idx is not None else None
        peak_value = float(running_max[peak_idx]) if peak_idx is not None else portfolio_value

        # Drawdown duration (days from peak to trough)
        dd_duration = (max_dd_idx - peak_idx).days if peak_idx is not None and max_dd_idx is not None else 0

        # Recovery time (days from trough back to peak, if recovered)
        recovery_idx = None
        if max_dd_idx is not None:
            post_trough = equity[max_dd_idx:]
            recovered = post_trough[post_trough >= peak_value]
            if len(recovered) > 0:
                recovery_idx = recovered.index[0]

        recovery_days = (recovery_idx - max_dd_idx).days if recovery_idx is not None else None

        # Current drawdown state
        current_dd_pct = float(drawdown.iloc[-1])
        current_dd_dollars = float(drawdown_dollars.iloc[-1])
        is_in_drawdown = current_dd_pct < -0.001  # More than 0.1%

        # Calmar ratio (annualized return / max drawdown)
        annualized_return = float(portfolio_returns.mean() * 252)
        calmar = annualized_return / abs(max_dd_pct) if max_dd_pct != 0 else 0

        # Ulcer Index (RMS of drawdowns)
        ulcer_index = float(np.sqrt(np.mean(drawdown ** 2)))

        # All drawdown events > 5%
        dd_events = []
        in_dd = False
        dd_start = None
        for i in range(len(drawdown)):
            if drawdown.iloc[i] < -0.05 and not in_dd:
                in_dd = True
                dd_start = drawdown.index[i]
            elif drawdown.iloc[i] >= -0.01 and in_dd:
                in_dd = False
                dd_events.append({
                    "start": dd_start.isoformat() if dd_start else None,
                    "end": drawdown.index[i].isoformat(),
                    "max_drawdown_pct": round(float(drawdown[dd_start:drawdown.index[i]].min()) * 100, 2),
                    "duration_days": (drawdown.index[i] - dd_start).days if dd_start else 0,
                })

        return {
            "account_number": account_number,
            "portfolio_value": round(portfolio_value, 2),
            "data_points": len(portfolio_returns),

            "max_drawdown": {
                "pct": round(max_dd_pct * 100, 2),
                "dollars": round(max_dd_dollars, 2),
                "peak_date": peak_idx.isoformat() if peak_idx is not None else None,
                "trough_date": max_dd_idx.isoformat() if max_dd_idx is not None else None,
                "peak_value": round(peak_value, 2),
                "duration_days": dd_duration,
                "recovery_days": recovery_days,
                "recovered": recovery_idx is not None,
            },

            "current_state": {
                "in_drawdown": is_in_drawdown,
                "current_drawdown_pct": round(current_dd_pct * 100, 2),
                "current_drawdown_dollars": round(current_dd_dollars, 2),
                "distance_from_peak_pct": round(abs(current_dd_pct) * 100, 2),
            },

            "risk_ratios": {
                "calmar_ratio": round(calmar, 4),
                "calmar_interpretation": (
                    "EXCELLENT" if calmar > 3 else
                    "GOOD" if calmar > 1 else
                    "FAIR" if calmar > 0.5 else
                    "POOR"
                ),
                "ulcer_index": round(ulcer_index, 6),
                "annualized_return_pct": round(annualized_return * 100, 2),
            },

            "drawdown_events_gt_5pct": dd_events,

            "interpretation": {
                "max_dd_statement": f"Worst drawdown: {max_dd_pct*100:.1f}% (${abs(max_dd_dollars):,.0f}) lasting {dd_duration} days",
                "current_state": (
                    f"Currently in drawdown: {current_dd_pct*100:.1f}% from peak"
                    if is_in_drawdown
                    else "At or near equity highs"
                ),
                "recovery": (
                    f"Recovered in {recovery_days} days"
                    if recovery_days is not None
                    else "Not yet recovered" if is_in_drawdown else "N/A"
                ),
            },

            "methodology": "Historical simulation drawdown analysis with Calmar ratio and Ulcer Index",
        }

    except Exception as e:
        logger.error(f"Drawdown analysis failed: {e}", exc_info=True)
        return {"error": str(e), "account_number": account_number}


# ============================================================================
# MCP Tool Registration
# ============================================================================

def register_tools(mcp):
    """Register Phase 6 statistical validation tools with MCP server."""

    @mcp.tool()
    def validate_brooks_pattern_win_rate(
        ticker: str,
        pattern_id: str = "auto",
        lookback_days: int = 504,
        holding_period: int = 10,
        profit_target_pct: float = 5.0,
        stop_loss_pct: float = 5.0,
    ) -> dict[str, Any]:
        """
        Backtest a Brooks pattern on historical data using triple-barrier labeling.

        Finds all historical occurrences of a pattern, applies profit/stop barriers,
        and calculates actual win rate with confidence intervals.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            pattern_id: Brooks pattern to test ("high_2", "double_bottom", etc.) or "auto" for all
            lookback_days: Historical data to scan (default 504 = ~2 years)
            holding_period: Days to hold each trade (default 10)
            profit_target_pct: Profit target percentage (default 5.0%)
            stop_loss_pct: Stop loss percentage (default 5.0%)

        Returns:
            Win rate, risk/reward, confidence interval, pattern breakdown, sample trades
        """
        return _validate_brooks_pattern_impl(
            ticker, pattern_id, lookback_days, holding_period,
            profit_target_pct, stop_loss_pct,
        )

    @mcp.tool()
    def calculate_portfolio_correlation(
        account_number: str,
        method: str = "pearson",
        lookback_days: int = 252,
    ) -> dict[str, Any]:
        """
        Calculate portfolio correlation matrix and risk attribution (MCR/CCR).

        Analyzes how correlated positions are, identifies concentration risk,
        and decomposes which positions drive portfolio volatility.

        Args:
            account_number: Questrade account number
            method: Correlation method - "pearson" or "spearman"
            lookback_days: Historical lookback (default 252 = 1 year)

        Returns:
            Correlation matrix, risk attribution per position, high-correlation warnings,
            diversification ratio, portfolio volatility
        """
        return _calculate_correlation_impl(account_number, method, lookback_days)

    @mcp.tool()
    def run_monte_carlo_stress_test(
        account_number: str,
        n_simulations: int = 5000,
        time_horizon_days: int = 21,
        lookback_days: int = 252,
    ) -> dict[str, Any]:
        """
        Run Monte Carlo simulation and stress test scenarios on portfolio.

        Simulates thousands of possible portfolio paths using GBM calibrated
        on historical returns. Includes crash scenarios (COVID, 2008, flash crash).

        Args:
            account_number: Questrade account number
            n_simulations: Number of simulated paths (default 5000)
            time_horizon_days: Forecast horizon in days (default 21 = 1 month)
            lookback_days: Historical calibration period (default 252)

        Returns:
            VaR/CVaR from simulation, P&L percentiles, loss probabilities,
            stress scenario impacts, risk level
        """
        return _monte_carlo_stress_test_impl(
            account_number, n_simulations, time_horizon_days, lookback_days,
        )

    @mcp.tool()
    def recommend_kelly_position_size(
        win_rate: float,
        avg_win_pct: float,
        avg_loss_pct: float,
        account_value: float = 100000,
        kelly_fraction: float = 0.25,
        max_position_pct: float = 10.0,
    ) -> dict[str, Any]:
        """
        Calculate optimal position size using Kelly Criterion.

        Given win rate and average win/loss, calculates the mathematically
        optimal bet size that maximizes long-term capital growth.

        Args:
            win_rate: Win probability (0-1, e.g., 0.65 for 65%)
            avg_win_pct: Average winning trade return (positive, e.g., 5.0 for 5%)
            avg_loss_pct: Average losing trade return (negative, e.g., -3.0 for -3%)
            account_value: Total account value in dollars (default $100K)
            kelly_fraction: Fraction of Kelly to use (default 0.25 = quarter-Kelly)
            max_position_pct: Maximum position as % of account (default 10%)

        Returns:
            Kelly sizing (full/half/quarter), edge analysis, risk of ruin,
            position size recommendation
        """
        return _kelly_position_size_impl(
            win_rate, avg_win_pct, avg_loss_pct,
            account_value, kelly_fraction, max_position_pct,
        )

    @mcp.tool()
    def quantify_pattern_edge(
        ticker: str,
        pattern_id: str = "auto",
        lookback_days: int = 504,
        holding_period: int = 10,
    ) -> dict[str, Any]:
        """
        Quantify the statistical edge for a Brooks pattern on a specific ticker.

        Combines pattern win rate backtesting with Kelly criterion to produce
        actionable edge metrics and position sizing recommendations.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            pattern_id: Brooks pattern or "auto" for all
            lookback_days: Historical scan period (default 504 = ~2 years)
            holding_period: Trade holding period in days (default 10)

        Returns:
            Edge per trade, edge quality (STRONG/MODERATE/MARGINAL/NO_EDGE),
            Kelly sizing, Sharpe-like ratio, trade/skip recommendation
        """
        return _quantify_edge_impl(ticker, pattern_id, lookback_days, holding_period)

    @mcp.tool()
    def detect_model_decay(
        days: int = 60,
        threshold: float = 0.55,
    ) -> dict[str, Any]:
        """
        Detect prediction model decay by analyzing rolling accuracy trends.

        Checks if trading signal accuracy (gate pass rates, component scores)
        has declined below threshold in recent windows. Early warning for
        strategy degradation.

        Args:
            days: Analysis period in days (default 60)
            threshold: Minimum acceptable accuracy (default 0.55 = 55%)

        Returns:
            Gate accuracy trends (30d/60d/90d), trend direction (IMPROVING/STABLE/DECLINING),
            decay alerts, best/worst predictors, recommendations
        """
        return _detect_decay_impl(days, threshold)

    @mcp.tool()
    def calculate_drawdown_analysis(
        account_number: str,
        lookback_days: int = 252,
    ) -> dict[str, Any]:
        """
        Calculate comprehensive drawdown analysis for portfolio.

        Measures maximum drawdown, drawdown duration, recovery time,
        Calmar ratio, Ulcer Index, and current drawdown state.

        Args:
            account_number: Questrade account number
            lookback_days: Historical period (default 252 = 1 year)

        Returns:
            Max drawdown (%, $), duration, recovery time, Calmar ratio,
            Ulcer Index, current state, historical drawdown events > 5%
        """
        return _drawdown_analysis_impl(account_number, lookback_days)
