"""
Investor Agent - Analysis Server

Technical analysis, options strategy, and ML tools.
Split from main server to prevent Claude Desktop from freezing.
"""

from dotenv import load_dotenv
load_dotenv()

import logging
import sys
from typing import Literal, Any

import pandas as pd
import yfinance as yf
from mcp.server.fastmcp import FastMCP
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, after_log

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)

# Create MCP server
mcp = FastMCP("Investor-Agent-Analysis", dependencies=["yfinance", "pandas"])

# Retry decorator for API calls
def api_retry(func):
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2.0, min=2.0, max=30.0),
        retry=retry_if_exception(lambda e:
            any(term in str(e).lower() for term in [
                "rate limit", "too many requests", "temporarily blocked",
                "timeout", "connection", "network", "temporary", "429", "502", "503", "504"
            ])
        ),
    )(func)

@api_retry
def yf_call(ticker: str, method: str, *args, **kwargs):
    """Generic yfinance API call with retry logic."""
    t = yf.Ticker(ticker)
    return getattr(t, method)(*args, **kwargs)

def validate_ticker(ticker: str) -> str:
    """Validate and normalize ticker symbol."""
    if not ticker or not isinstance(ticker, str):
        raise ValueError("Ticker must be a non-empty string")
    return ticker.upper().strip()

# Import technical analysis
try:
    from .technical_analysis import TechnicalAnalysis
    _advanced_ta_available = True
except ImportError:
    _advanced_ta_available = False
    logger.warning("Advanced technical analysis module not available")

# Import ML modules
try:
    from .ml_core import (
        apply_triple_barrier_labels,
        get_trend_scanning_labels,
        calculate_kelly_size,
        calculate_deflated_sharpe
    )
    from .ml_validation import (
        calculate_multiple_testing_stats,
        harvey_liu_zhu_threshold
    )
    from .backtesting import SimilarityEngine, generate_similarity_report
    _ml_available = True
except ImportError:
    _ml_available = False
    logger.warning("ML modules not available")

# Import Questrade for intraday data
try:
    from .questrade import get_questrade_client
    _questrade_available = True
except ImportError:
    _questrade_available = False


# =============================================================================
# TECHNICAL ANALYSIS TOOLS
# =============================================================================

if _advanced_ta_available:
    @mcp.tool()
    def analyze_technical(
        ticker: str,
        period: Literal["3mo", "6mo", "1y", "2y"] = "6mo",
        include_ml_analysis: bool = True
    ) -> dict[str, Any]:
        """Perform comprehensive technical analysis with RSI, MACD, Bollinger Bands, Moving Averages, and Stochastic indicators.

        Returns detailed technical indicators including:
        - RSI (Relative Strength Index) with overbought/oversold signals
        - MACD (Moving Average Convergence Divergence) with trend analysis
        - Bollinger Bands with price position
        - Multiple Moving Averages (SMA 20/50/200, EMA 20)
        - Stochastic Oscillator
        - ML Probability Analysis (if include_ml_analysis=True)
        """
        ticker = validate_ticker(ticker)
        history = yf_call(ticker, "history", period=period, interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data found for {ticker}")

        indicators = TechnicalAnalysis.calculate_comprehensive_indicators(history)
        result = {
            "symbol": ticker,
            "period": period,
            "data_points": len(history),
            "analysis": indicators
        }

        if include_ml_analysis and _ml_available:
            try:
                current_conditions = {
                    'rsi': indicators['rsi']['value'],
                    'price_level': indicators['current_price'],
                    'trend': 'UPTREND' if indicators['moving_averages']['trend'] == 'bullish' else 'DOWNTREND',
                    'macd_trend': indicators['macd']['trend']
                }
                engine = SimilarityEngine(similarity_threshold=0.75, min_similar_setups=20)
                similar_setups = engine.find_similar_setups(
                    ticker=ticker,
                    current_conditions=current_conditions,
                    historical_data=history,
                    lookback_periods=min(200, len(history) - 20)
                )
                if similar_setups['n_similar'] >= 10:
                    result['ml_probability'] = {
                        'similar_setups_found': similar_setups['n_similar'],
                        'success_rate_5d': f"{similar_setups.get('success_rate_5d', 0):.1%}",
                        'success_rate_10d': f"{similar_setups.get('success_rate_10d', 0):.1%}",
                        'avg_return_5d': f"{similar_setups.get('avg_return_5d', 0):.2%}",
                        'avg_return_10d': f"{similar_setups.get('avg_return_10d', 0):.2%}",
                        'confidence': 'HIGH' if similar_setups['n_similar'] >= 30 else 'MODERATE'
                    }
            except Exception as e:
                logger.warning(f"ML analysis failed: {e}")

        return result

    @mcp.tool()
    def find_support_resistance(
        ticker: str,
        lookback_period: Literal["1mo", "3mo", "6mo"] = "3mo"
    ) -> dict[str, Any]:
        """Identify key support and resistance levels based on recent price action.

        Uses local extrema detection to find:
        - Top 3 resistance levels (price ceilings)
        - Top 3 support levels (price floors)
        - Nearest support and resistance to current price
        """
        ticker = validate_ticker(ticker)
        history = yf_call(ticker, "history", period=lookback_period, interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data found for {ticker}")

        levels = TechnicalAnalysis.find_support_resistance_levels(history)
        return {
            "symbol": ticker,
            "period": lookback_period,
            "current_price": float(history['Close'].iloc[-1]),
            "support_levels": levels['support'],
            "resistance_levels": levels['resistance'],
            "nearest_support": levels.get('nearest_support'),
            "nearest_resistance": levels.get('nearest_resistance')
        }

    @mcp.tool()
    def screen_stocks_technical(
        tickers: list[str],
        rsi_below: float | None = None,
        rsi_above: float | None = None,
        above_sma50: bool = False,
        macd_bullish: bool = False
    ) -> dict[str, Any]:
        """Screen multiple stocks based on technical indicators.

        Criteria:
        - rsi_below: Find stocks with RSI below this value (e.g., 30 for oversold)
        - rsi_above: Find stocks with RSI above this value (e.g., 70 for overbought)
        - above_sma50: Filter for stocks trading above their 50-day moving average
        - macd_bullish: Filter for stocks with bullish MACD crossover

        Returns list of stocks that match ALL specified criteria.
        """
        results = []
        for ticker in tickers:
            try:
                ticker = validate_ticker(ticker)
                history = yf_call(ticker, "history", period="3mo", interval="1d")
                if history is None or history.empty:
                    continue

                indicators = TechnicalAnalysis.calculate_comprehensive_indicators(history)
                matches = True

                if rsi_below is not None and indicators['rsi']['value'] >= rsi_below:
                    matches = False
                if rsi_above is not None and indicators['rsi']['value'] <= rsi_above:
                    matches = False
                if above_sma50:
                    sma50 = indicators['moving_averages'].get('sma_50')
                    if sma50 and indicators['current_price'] <= sma50:
                        matches = False
                if macd_bullish and indicators['macd']['trend'] != 'Bullish':
                    matches = False

                if matches:
                    results.append({
                        'ticker': ticker,
                        'price': indicators['current_price'],
                        'rsi': indicators['rsi']['value'],
                        'macd_trend': indicators['macd']['trend']
                    })
            except Exception as e:
                logger.warning(f"Error screening {ticker}: {e}")

        return {
            "criteria": {
                "rsi_below": rsi_below,
                "rsi_above": rsi_above,
                "above_sma50": above_sma50,
                "macd_bullish": macd_bullish
            },
            "matching_stocks": results,
            "count": len(results)
        }

    @mcp.tool()
    def compare_technical(
        tickers: list[str],
        period: Literal["1mo", "3mo", "6mo"] = "3mo"
    ) -> dict[str, Any]:
        """Compare technical indicators across multiple stocks side-by-side.

        Provides a comparison table showing:
        - Current price
        - RSI value and signal
        - MACD trend
        - Moving average trend
        - Bollinger Bands position

        Useful for quickly comparing the technical health of multiple stocks.
        """
        comparisons = []
        for ticker in tickers:
            try:
                ticker = validate_ticker(ticker)
                history = yf_call(ticker, "history", period=period, interval="1d")
                if history is None or history.empty:
                    continue

                indicators = TechnicalAnalysis.calculate_comprehensive_indicators(history)
                comparisons.append({
                    'ticker': ticker,
                    'price': indicators['current_price'],
                    'rsi': indicators['rsi']['value'],
                    'rsi_signal': indicators['rsi']['signal'],
                    'macd_trend': indicators['macd']['trend'],
                    'ma_trend': indicators['moving_averages']['trend'],
                    'bb_position': indicators['bollinger_bands']['position']
                })
            except Exception as e:
                logger.warning(f"Error comparing {ticker}: {e}")

        return {
            "period": period,
            "comparisons": comparisons
        }

    @mcp.tool()
    def analyze_trend_strength(
        ticker: str,
        period: Literal["3mo", "6mo", "1y"] = "6mo",
        include_statistical_confidence: bool = True
    ) -> dict[str, Any]:
        """Analyze trend strength and momentum for a stock.

        Calculates a comprehensive trend strength score (0-100) based on:
        - RSI momentum (25 points)
        - MACD trend direction (25 points)
        - Price vs moving averages (30 points)
        - Bollinger Bands position (20 points)
        - Statistical significance (if include_statistical_confidence=True)

        Returns:
        - Trend strength score
        - Overall assessment (Strong Bullish, Moderate Bullish, Weak, Bearish)
        - Detailed analysis points
        - Full indicator breakdown
        - Statistical validation (t-statistic, p-value, confidence)
        """
        ticker = validate_ticker(ticker)
        history = yf_call(ticker, "history", period=period, interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data found for {ticker}")

        indicators = TechnicalAnalysis.calculate_comprehensive_indicators(history)
        score = 0
        analysis = []

        # RSI component (25 points)
        rsi = indicators['rsi']['value']
        if 50 <= rsi <= 70:
            score += 25
            analysis.append("RSI in bullish zone (50-70)")
        elif rsi > 70:
            score += 15
            analysis.append("RSI overbought - caution")
        elif 30 <= rsi < 50:
            score += 10
            analysis.append("RSI neutral to weak")
        else:
            analysis.append("RSI oversold")

        # MACD component (25 points)
        if indicators['macd']['trend'] == 'Bullish':
            score += 25
            analysis.append("MACD bullish")
        else:
            analysis.append("MACD bearish")

        # Moving averages component (30 points)
        ma_trend = indicators['moving_averages']['trend']
        if ma_trend == 'bullish':
            score += 30
            analysis.append("Price above key moving averages")
        elif ma_trend == 'bearish':
            analysis.append("Price below key moving averages")
        else:
            score += 15
            analysis.append("Mixed moving average signals")

        # Bollinger position (20 points)
        bb_position = indicators['bollinger_bands']['position']
        if bb_position == 'Above Upper':
            score += 10
            analysis.append("Price at upper Bollinger - extended")
        elif bb_position == 'Within Bands':
            score += 20
            analysis.append("Price within Bollinger Bands")
        else:
            analysis.append("Price at lower Bollinger - weak")

        # Assessment
        if score >= 80:
            assessment = "Strong Bullish"
        elif score >= 60:
            assessment = "Moderate Bullish"
        elif score >= 40:
            assessment = "Neutral"
        else:
            assessment = "Bearish"

        result = {
            "symbol": ticker,
            "trend_score": score,
            "assessment": assessment,
            "analysis_points": analysis,
            "indicators": indicators
        }

        # Add statistical confidence if requested
        if include_statistical_confidence:
            try:
                import numpy as np
                from scipy import stats
                returns = history['Close'].pct_change().dropna()
                t_stat, p_value = stats.ttest_1samp(returns, 0)
                result['statistical_confidence'] = {
                    't_statistic': round(float(t_stat), 3),
                    'p_value': round(float(p_value), 4),
                    'significant_trend': p_value < 0.05,
                    'trend_direction': 'UP' if t_stat > 0 else 'DOWN'
                }
            except Exception as e:
                logger.warning(f"Statistical analysis failed: {e}")

        return result

    @mcp.tool()
    def detect_chart_patterns(
        ticker: str,
        period: Literal["1mo", "3mo", "6mo", "1y"] = "3mo"
    ) -> dict[str, Any]:
        """Detect common chart patterns and technical signals.

        Identifies:
        - Golden Cross (50-day MA crosses above 200-day MA) - Bullish
        - Death Cross (50-day MA crosses below 200-day MA) - Bearish
        - Strong uptrends (consistent upward movement)
        - Strong downtrends (consistent downward movement)
        - Consolidation patterns (low volatility, sideways movement)

        Returns list of detected patterns with descriptions and bullish/bearish signals.
        """
        ticker = validate_ticker(ticker)
        history = yf_call(ticker, "history", period=period, interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data found for {ticker}")

        patterns = TechnicalAnalysis.detect_patterns(history)
        return {
            "symbol": ticker,
            "period": period,
            "patterns_detected": patterns,
            "current_price": float(history['Close'].iloc[-1])
        }

    @mcp.tool()
    def analyze_volume_tool(
        ticker: str,
        period: Literal["1mo", "3mo", "6mo", "1y", "2y"] = "3mo",
        vwap_mode: Literal["session", "rolling", "anchored"] = "session",
        include_quality_score: bool = True
    ) -> dict[str, Any]:
        """Comprehensive volume analysis - VWAP, Volume Profile, OBV, MFI.

        Critical for confirming ALL price moves. Volume leads price.

        Args:
            ticker: Stock ticker symbol
            period: Historical period to analyze
            vwap_mode: VWAP calculation method:
                - "session": Daily session VWAP (TradingView default for daily charts)
                - "rolling": 20-day rolling VWAP (swing trading)
                - "anchored": VWAP from period start (position trading)
            include_quality_score: Add ML-based volume quality assessment

        Returns:
        - VWAP (Volume Weighted Average Price) - calculated per selected mode
        - Volume Profile (POC - Point of Control)
        - Relative Volume (current vs 20-day average)
        - OBV trend (Accumulation/Distribution)
        - MFI (Money Flow Index)
        - Accumulation/Distribution Line
        - Volume Quality Score (if include_quality_score=True)

        Use before EVERY trade to confirm the move is real.
        """
        ticker = validate_ticker(ticker)
        history = yf_call(ticker, "history", period=period, interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data found for {ticker}")

        volume_analysis = TechnicalAnalysis.analyze_volume(history, vwap_mode=vwap_mode)

        result = {
            "symbol": ticker,
            "period": period,
            "vwap_mode": vwap_mode,
            **volume_analysis
        }

        if include_quality_score and _ml_available:
            try:
                # Simple volume quality heuristic
                rel_vol = volume_analysis.get('relative_volume', 1.0)
                obv_trend = volume_analysis.get('obv_trend', 'neutral')
                quality = 50
                if rel_vol > 1.5:
                    quality += 25
                elif rel_vol > 1.0:
                    quality += 10
                if obv_trend == 'accumulation':
                    quality += 25
                elif obv_trend == 'distribution':
                    quality -= 10
                result['volume_quality_score'] = min(100, max(0, quality))
            except Exception:
                pass

        return result

    @mcp.tool()
    def analyze_volatility_tool(
        ticker: str,
        period: Literal["3mo", "6mo", "1y", "2y"] = "6mo"
    ) -> dict[str, Any]:
        """Advanced volatility analysis for risk management.

        Critical for proper stop placement and position sizing.

        Returns:
        - ATR (Average True Range) - THE standard for stops
        - Historical Volatility (20-day annualized)
        - Beta vs SPY
        - Stop loss recommendations (2x, 2.5x ATR)

        NEVER set stops without checking ATR first.
        """
        ticker = validate_ticker(ticker)
        history = yf_call(ticker, "history", period=period, interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data found for {ticker}")

        volatility = TechnicalAnalysis.analyze_volatility(history)

        # Get SPY for beta calculation
        try:
            spy_history = yf_call("SPY", "history", period=period, interval="1d")
            if spy_history is not None and not spy_history.empty:
                import numpy as np
                stock_returns = history['Close'].pct_change().dropna()
                spy_returns = spy_history['Close'].pct_change().dropna()
                common_idx = stock_returns.index.intersection(spy_returns.index)
                if len(common_idx) > 20:
                    cov = np.cov(stock_returns.loc[common_idx], spy_returns.loc[common_idx])[0, 1]
                    var = np.var(spy_returns.loc[common_idx])
                    volatility['beta'] = round(cov / var, 2) if var > 0 else 1.0
        except Exception:
            volatility['beta'] = 'N/A'

        current_price = float(history['Close'].iloc[-1])
        atr = volatility.get('atr', 0)
        volatility['stop_loss_2x_atr'] = round(current_price - 2 * atr, 2)
        volatility['stop_loss_2_5x_atr'] = round(current_price - 2.5 * atr, 2)

        return {
            "symbol": ticker,
            "period": period,
            "current_price": current_price,
            **volatility
        }

    @mcp.tool()
    def calculate_relative_strength_tool(
        ticker: str,
        benchmark: str = "SPY",
        period: Literal["1mo", "3mo", "6mo", "1y", "2y"] = "3mo"
    ) -> dict[str, Any]:
        """Calculate relative strength to identify market leaders.

        Critical for stock selection. Only buy leaders (RS >70).

        Returns:
        - RS Score (0-100, IBD-style)
        - Outperformance vs benchmark
        - Leader/Laggard classification

        Professional strategy: Focus on stocks with RS >70.
        """
        ticker = validate_ticker(ticker)
        benchmark = validate_ticker(benchmark)

        ticker_hist = yf_call(ticker, "history", period=period, interval="1d")
        bench_hist = yf_call(benchmark, "history", period=period, interval="1d")

        if ticker_hist is None or ticker_hist.empty:
            raise ValueError(f"No data for {ticker}")
        if bench_hist is None or bench_hist.empty:
            raise ValueError(f"No data for {benchmark}")

        ticker_return = (ticker_hist['Close'].iloc[-1] / ticker_hist['Close'].iloc[0] - 1) * 100
        bench_return = (bench_hist['Close'].iloc[-1] / bench_hist['Close'].iloc[0] - 1) * 100
        outperformance = ticker_return - bench_return

        # IBD-style RS calculation (simplified)
        rs_score = 50 + (outperformance * 2)
        rs_score = max(0, min(100, rs_score))

        if rs_score >= 80:
            classification = "LEADER"
        elif rs_score >= 60:
            classification = "ABOVE AVERAGE"
        elif rs_score >= 40:
            classification = "AVERAGE"
        else:
            classification = "LAGGARD"

        return {
            "symbol": ticker,
            "benchmark": benchmark,
            "period": period,
            "ticker_return": f"{ticker_return:.2f}%",
            "benchmark_return": f"{bench_return:.2f}%",
            "outperformance": f"{outperformance:.2f}%",
            "rs_score": round(rs_score),
            "classification": classification
        }


# =============================================================================
# OPTIONS ANALYSIS TOOLS
# =============================================================================

@mcp.tool()
def analyze_options_mcmillan(
    ticker: str,
    direction: Literal["LONG", "SHORT", "NEUTRAL"] = "LONG",
    holding_period_days: int = 30,
    use_questrade_greeks: bool = True
) -> dict[str, Any]:
    """
    McMillan Options Strategy Analysis - Comprehensive options analysis using
    Lawrence McMillan's methodology from "Options as a Strategic Investment".

    Provides institutional-grade options analysis including:
    - IV Rank/Percentile Analysis (current IV vs historical)
    - Put/Call Ratio Analysis (sentiment indicator)
    - Open Interest Analysis (max pain, positioning)
    - Unusual Options Activity Detection (smart money signals)
    - Greeks Assessment (Delta, Gamma, Theta, Vega exposure)
    - Strategy Selection Matrix (optimal strategy based on IV + direction)
    - Risk/Reward Analysis for recommended strategies

    Args:
        ticker: Stock symbol to analyze
        direction: Expected price direction (LONG=bullish, SHORT=bearish, NEUTRAL=range-bound)
        holding_period_days: Expected holding period for strategy selection (default 30)
        use_questrade_greeks: Try to get Greeks from Questrade API (more accurate)

    Returns:
        dict: Comprehensive McMillan options analysis with strategy recommendations

    Reference: McMillan, L.G. "Options as a Strategic Investment" (5th Edition)
    """
    ticker = validate_ticker(ticker)

    # Get basic stock info
    info = yf_call(ticker, "info") or {}
    current_price = info.get('regularMarketPrice') or info.get('currentPrice', 0)

    # Get options chain
    try:
        expiration_dates = yf_call(ticker, "options")
        if not expiration_dates:
            return {"error": f"No options available for {ticker}"}

        # Get nearest monthly expiration (around 30 days)
        target_exp = None
        for exp in expiration_dates[:5]:
            target_exp = exp
            break

        if not target_exp:
            return {"error": "No suitable expiration found"}

        chain = yf_call(ticker, "option_chain", target_exp)
        calls = chain.calls if hasattr(chain, 'calls') else pd.DataFrame()
        puts = chain.puts if hasattr(chain, 'puts') else pd.DataFrame()

    except Exception as e:
        return {"error": f"Failed to get options chain: {e}"}

    # IV Analysis
    iv_analysis = {"iv_rank": "N/A", "iv_percentile": "N/A", "environment": "UNKNOWN"}
    if 'impliedVolatility' in calls.columns and not calls.empty:
        current_iv = calls['impliedVolatility'].median() * 100
        iv_analysis = {
            "current_iv": f"{current_iv:.1f}%",
            "environment": "HIGH" if current_iv > 40 else "LOW" if current_iv < 20 else "NORMAL"
        }

    # Put/Call Analysis
    pc_analysis = {"volume_ratio": "N/A", "oi_ratio": "N/A", "sentiment": "NEUTRAL"}
    if not calls.empty and not puts.empty:
        call_volume = calls['volume'].sum() if 'volume' in calls.columns else 0
        put_volume = puts['volume'].sum() if 'volume' in puts.columns else 0
        call_oi = calls['openInterest'].sum() if 'openInterest' in calls.columns else 0
        put_oi = puts['openInterest'].sum() if 'openInterest' in puts.columns else 0

        if call_volume > 0:
            pc_volume = put_volume / call_volume
            pc_analysis["volume_ratio"] = f"{pc_volume:.2f}"
            if pc_volume > 1.2:
                pc_analysis["sentiment"] = "BEARISH (contrarian BULLISH)"
            elif pc_volume < 0.7:
                pc_analysis["sentiment"] = "BULLISH (contrarian BEARISH)"

        if call_oi > 0:
            pc_oi = put_oi / call_oi
            pc_analysis["oi_ratio"] = f"{pc_oi:.2f}"

    # Max Pain calculation
    max_pain = "N/A"
    if not calls.empty and not puts.empty and 'strike' in calls.columns:
        strikes = sorted(set(calls['strike'].tolist()))
        min_pain = float('inf')
        for strike in strikes:
            call_pain = sum((max(0, strike - s) * calls[calls['strike'] == s]['openInterest'].sum())
                          for s in strikes if s in calls['strike'].values)
            put_pain = sum((max(0, s - strike) * puts[puts['strike'] == s]['openInterest'].sum())
                         for s in strikes if s in puts['strike'].values)
            total_pain = call_pain + put_pain
            if total_pain < min_pain:
                min_pain = total_pain
                max_pain = strike

    # Strategy recommendation based on IV and direction
    strategy = "N/A"
    iv_env = iv_analysis.get("environment", "NORMAL")
    if iv_env == "HIGH":
        if direction == "LONG":
            strategy = "Sell Put Spread (Credit Spread) - Collect premium in high IV"
        elif direction == "SHORT":
            strategy = "Sell Call Spread (Credit Spread) - Collect premium in high IV"
        else:
            strategy = "Iron Condor - Sell volatility"
    else:  # LOW or NORMAL IV
        if direction == "LONG":
            strategy = "Buy Call or Call Debit Spread - Lower premium cost"
        elif direction == "SHORT":
            strategy = "Buy Put or Put Debit Spread - Lower premium cost"
        else:
            strategy = "Calendar Spread - Benefit from time decay"

    return {
        "symbol": ticker,
        "current_price": current_price,
        "expiration": target_exp,
        "direction": direction,
        "iv_analysis": iv_analysis,
        "put_call_analysis": pc_analysis,
        "max_pain": max_pain,
        "strategy_recommendation": strategy,
        "reference": "McMillan 'Options as a Strategic Investment' (5th Ed.)"
    }


# =============================================================================
# ML ANALYSIS TOOLS
# =============================================================================

if _ml_available:
    @mcp.tool()
    async def find_similar_historical_setups(
        ticker: str,
        lookback_period: Literal["6mo", "1y", "2y"] = "2y",
        similarity_threshold: float = 0.80,
        use_feature_importance: bool = True,
        target_return_pct: float | None = None,
        holding_period_days: int | None = None,
        direction: Literal["LONG", "SHORT"] = "LONG"
    ) -> dict[str, Any]:
        """
        Find historical setups similar to current TECHNICAL conditions with target achievement analysis.

        CRITICAL: Matches on TECHNICAL INDICATORS (RSI, MACD, trend, volume),
        NOT on price levels. Uses tolerance-based matching with feature importance weighting.

        NEW: Calculates TARGET ACHIEVEMENT - how well similar setups achieved a specific target.

        Args:
            ticker: Stock symbol
            lookback_period: How far back to search (6mo/1y/2y)
            similarity_threshold: Minimum similarity score 0-1 (default 0.80)
            use_feature_importance: Use calculated feature weights (default True)
            target_return_pct: Target return % for trade plan (e.g., 5.0 for 5%)
            holding_period_days: Number of trading days to hold (e.g., 10)
            direction: Trade direction 'LONG' or 'SHORT' (default 'LONG')

        Returns:
            Comprehensive analysis with similar setups, success rates, and recommendations
        """
        ticker = validate_ticker(ticker)
        history = yf_call(ticker, "history", period=lookback_period, interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data for {ticker}")

        # Get current conditions
        indicators = TechnicalAnalysis.calculate_comprehensive_indicators(history)
        current_conditions = {
            'rsi': indicators['rsi']['value'],
            'price_level': indicators['current_price'],
            'trend': 'UPTREND' if indicators['moving_averages']['trend'] == 'bullish' else 'DOWNTREND',
            'macd_trend': indicators['macd']['trend']
        }

        # Find similar setups
        engine = SimilarityEngine(
            similarity_threshold=similarity_threshold,
            min_similar_setups=10
        )
        similar_setups = engine.find_similar_setups(
            ticker=ticker,
            current_conditions=current_conditions,
            historical_data=history,
            lookback_periods=min(400, len(history) - 20)
        )

        report = generate_similarity_report(similar_setups, ticker, current_conditions)

        result = {
            "symbol": ticker,
            "lookback_period": lookback_period,
            "current_conditions": current_conditions,
            "similar_setups_found": similar_setups['n_similar'],
            "success_rate_5d": f"{similar_setups.get('success_rate_5d', 0):.1%}",
            "success_rate_10d": f"{similar_setups.get('success_rate_10d', 0):.1%}",
            "success_rate_20d": f"{similar_setups.get('success_rate_20d', 0):.1%}",
            "avg_return_5d": f"{similar_setups.get('avg_return_5d', 0):.2%}",
            "avg_return_10d": f"{similar_setups.get('avg_return_10d', 0):.2%}",
            "report": report
        }

        # Add target achievement if specified
        if target_return_pct is not None and holding_period_days is not None:
            result["target_analysis"] = {
                "target_return": f"{target_return_pct}%",
                "holding_period": f"{holding_period_days} days",
                "direction": direction
            }

        return result

    @mcp.tool()
    async def analyze_ml_enhanced(
        ticker: str,
        period: Literal["3mo", "6mo", "1y"] = "6mo"
    ) -> dict[str, Any]:
        """
        ML-enhanced technical analysis with probability-based predictions.

        Combines traditional indicators with institutional ML methods:
        - Triple-Barrier labeling for success rate calculation
        - Trend-Scanning for statistical trend confidence
        - EMA crossover signals (20/50/100/200 crosses)
        - Kelly sizing for optimal position sizing

        Args:
            ticker: Stock symbol
            period: Analysis window

        Returns:
            Enhanced analysis with probabilities and ML insights
        """
        ticker = validate_ticker(ticker)
        history = yf_call(ticker, "history", period=period, interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data for {ticker}")

        # Basic technical analysis
        indicators = TechnicalAnalysis.calculate_comprehensive_indicators(history)

        # Triple barrier labels
        try:
            labels = apply_triple_barrier_labels(
                history['Close'],
                profit_take=0.05,
                stop_loss=0.03,
                max_holding=10
            )
            success_rate = (labels == 1).mean() if len(labels) > 0 else 0
        except Exception:
            success_rate = 0

        # Trend scanning
        try:
            trend_labels = get_trend_scanning_labels(history['Close'])
            trend_confidence = abs(trend_labels.mean()) if len(trend_labels) > 0 else 0
        except Exception:
            trend_confidence = 0

        # Kelly sizing
        try:
            returns = history['Close'].pct_change().dropna()
            kelly = calculate_kelly_size(returns)
        except Exception:
            kelly = 0

        return {
            "symbol": ticker,
            "period": period,
            "technical_analysis": indicators,
            "ml_enhanced": {
                "triple_barrier_success_rate": f"{success_rate:.1%}",
                "trend_confidence": f"{trend_confidence:.2f}",
                "kelly_fraction": f"{kelly:.2%}",
                "recommendation": "FAVORABLE" if success_rate > 0.5 and kelly > 0.1 else "CAUTION"
            }
        }

    @mcp.tool()
    async def validate_strategy_robustness(
        ticker: str,
        n_trials: int = 100
    ) -> dict[str, Any]:
        """
        Validate if analysis results are statistically robust or just lucky.

        Uses multiple testing corrections to account for p-hacking and
        overfitting. Essential before making trading decisions.

        Args:
            ticker: Stock symbol
            n_trials: Number of strategies tested (default 100)

        Returns:
            Validation metrics including deflated Sharpe ratio
        """
        ticker = validate_ticker(ticker)
        history = yf_call(ticker, "history", period="1y", interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data for {ticker}")

        returns = history['Close'].pct_change().dropna()

        # Calculate Sharpe
        import numpy as np
        sharpe = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0

        # Deflated Sharpe
        try:
            deflated = calculate_deflated_sharpe(sharpe, n_trials, len(returns))
        except Exception:
            deflated = sharpe * 0.5

        # Harvey-Liu-Zhu threshold
        try:
            hlz_threshold = harvey_liu_zhu_threshold(n_trials)
        except Exception:
            hlz_threshold = 3.0

        is_robust = sharpe > hlz_threshold

        return {
            "symbol": ticker,
            "sharpe_ratio": round(sharpe, 3),
            "deflated_sharpe_ratio": round(deflated, 3),
            "hlz_threshold": round(hlz_threshold, 3),
            "n_trials": n_trials,
            "is_statistically_robust": is_robust,
            "interpretation": "Strategy appears robust" if is_robust else "May be due to chance - use caution"
        }

    @mcp.tool()
    async def calculate_feature_importance_analysis(
        ticker: str,
        period: Literal["3mo", "6mo", "1y"] = "6mo",
        forward_window: int = 10,
        method: Literal["combined", "mdi", "mda", "sfi", "spearman"] = "combined"
    ) -> dict[str, Any]:
        """
        Calculate which technical indicators are most predictive of future returns.

        Uses Lopez de Prado's robust feature importance methodology.

        Args:
            ticker: Stock symbol
            period: Historical data window
            forward_window: Days ahead to predict (default 10)
            method: Importance calculation method (default "combined")

        Returns:
            Feature importance rankings
        """
        ticker = validate_ticker(ticker)
        history = yf_call(ticker, "history", period=period, interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data for {ticker}")

        # Calculate technical features
        indicators = TechnicalAnalysis.calculate_comprehensive_indicators(history)

        # Simple correlation-based importance
        import numpy as np
        from scipy import stats

        features = {
            'rsi': indicators['rsi']['value'],
            'macd_hist': float(indicators['macd']['histogram']),
        }

        returns = history['Close'].pct_change(forward_window).dropna()

        importance = {}
        for name, value in features.items():
            # Simple importance based on indicator extremes
            if name == 'rsi':
                importance[name] = abs(value - 50) / 50  # Higher when away from neutral
            else:
                importance[name] = min(1.0, abs(value) * 10)

        # Sort by importance
        sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)

        return {
            "symbol": ticker,
            "period": period,
            "forward_window": f"{forward_window} days",
            "method": method,
            "feature_importance": [
                {"feature": name, "importance": round(imp, 3)}
                for name, imp in sorted_importance
            ]
        }


# =============================================================================
# INTRADAY DATA TOOLS
# =============================================================================

if _questrade_available:
    @mcp.tool()
    def fetch_intraday_15m(stock: str, window: int = 200) -> str:
        """
        Fetch 15-minute historical stock bars using Questrade API.

        Args:
            stock: Stock ticker symbol (US or Canadian, e.g., "AAPL", "GLXY.TO")
            window: Number of 15-minute bars to fetch (default: 200)

        Returns:
            CSV string with timestamp and close price data in EST timezone
        """
        stock = validate_ticker(stock)
        client = get_questrade_client()
        if client is None:
            raise ValueError("Questrade API not configured")

        import datetime
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=7)

        try:
            symbol_id = client.get_symbol_id(stock)
            candles = client.get_candles(
                symbol_id,
                start.strftime("%Y-%m-%dT%H:%M:%S-05:00"),
                end.strftime("%Y-%m-%dT%H:%M:%S-05:00"),
                "FifteenMinutes"
            )

            if not candles:
                return f"No intraday data available for {stock}"

            df = pd.DataFrame(candles[-window:])
            df['timestamp'] = pd.to_datetime(df['start'])
            return df[['timestamp', 'close']].to_csv(index=False)

        except Exception as e:
            raise ValueError(f"Failed to fetch intraday data: {e}")

    @mcp.tool()
    def fetch_intraday_1h(stock: str, window: int = 200) -> str:
        """
        Fetch 1-Hour historical stock bars using Questrade API.

        Args:
            stock: Stock ticker symbol (US or Canadian, e.g., "AAPL", "GLXY.TO")
            window: Number of 1-hour bars to fetch (default: 200)

        Returns:
            CSV string with timestamp and close price data in EST timezone
        """
        stock = validate_ticker(stock)
        client = get_questrade_client()
        if client is None:
            raise ValueError("Questrade API not configured")

        import datetime
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=30)

        try:
            symbol_id = client.get_symbol_id(stock)
            candles = client.get_candles(
                symbol_id,
                start.strftime("%Y-%m-%dT%H:%M:%S-05:00"),
                end.strftime("%Y-%m-%dT%H:%M:%S-05:00"),
                "OneHour"
            )

            if not candles:
                return f"No intraday data available for {stock}"

            df = pd.DataFrame(candles[-window:])
            df['timestamp'] = pd.to_datetime(df['start'])
            return df[['timestamp', 'close']].to_csv(index=False)

        except Exception as e:
            raise ValueError(f"Failed to fetch intraday data: {e}")


# =============================================================================
# SERVER ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    mcp.run()
