"""
Investor Agent - Scanner Server (Minimal)

A focused MCP server with only the tools needed for Market Opportunity Scanner.
Reduced from 47 tools to ~12 tools to prevent Claude Desktop from freezing.
"""

import logging
from typing import Any, Literal

import pandas as pd
import yfinance as yf
from mcp.server.fastmcp import FastMCP
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, after_log

# Import technical analysis
from investor_agent.technical_analysis import TechnicalAnalysis

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

# Check if scanner is available
try:
    from investor_agent.tradingview_scanner import get_scanner
    SCREENER_AVAILABLE = True
except ImportError:
    SCREENER_AVAILABLE = False

try:
    from investor_agent.scanner_analyzer import ScannerAnalyzer
    ANALYZER_AVAILABLE = True
except ImportError:
    ANALYZER_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("investor-agent-scanner")

# Create MCP server
mcp = FastMCP("Investor-Agent-Scanner", dependencies=["yfinance", "pandas"])


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_ohlcv_for_ticker(ticker: str, period: str = "3mo") -> pd.DataFrame | None:
    """Get OHLCV data for a ticker."""
    try:
        hist = yf_call(ticker, "history", period=period, interval="1d")
        if hist is not None and not hist.empty:
            return hist
    except Exception as e:
        logger.warning(f"Failed to get OHLCV for {ticker}: {e}")
    return None


# =============================================================================
# SCANNER TOOLS
# =============================================================================

@mcp.tool()
def scan_market_opportunities(
    market: Literal["america", "canada", "both"] = "america",
    min_price: float = 2.0,
    min_market_cap: int = 1_000_000_000,
    top_n: int = 5,
    include_deep_analysis: bool = False
) -> dict[str, Any]:
    """
    Scan US/Canadian markets for INFLECTION POINT trading opportunities.
    Returns top LONG and SHORT candidates with composite scores.

    Args:
        market: "america", "canada", or "both"
        min_price: Minimum stock price (default: $2)
        min_market_cap: Minimum market cap (default: $1B)
        top_n: Number of candidates per direction (default: 5)
        include_deep_analysis: Run full analysis pipeline (default: False)
    """
    if not SCREENER_AVAILABLE:
        raise ValueError("TradingView scanner not available")

    from datetime import datetime
    import pytz

    try:
        scanner = get_scanner()
        et = pytz.timezone("America/New_York")

        # Scan for candidates
        long_candidates = scanner.scan_long_setups(
            setup_type="all", market=market, min_price=min_price,
            min_market_cap=min_market_cap, limit=top_n * 5
        )
        short_candidates = scanner.scan_short_setups(
            setup_type="all", market=market, min_price=min_price,
            min_market_cap=min_market_cap, limit=top_n * 5
        )

        analyzed_long = []
        analyzed_short = []

        if include_deep_analysis and ANALYZER_AVAILABLE:
            analyzer = ScannerAnalyzer()
            # Analyze LONG
            for c in long_candidates[:top_n * 2]:
                try:
                    ohlcv = _get_ohlcv_for_ticker(c['symbol'])
                    analysis = analyzer.analyze_candidate(
                        ticker=c['symbol'], direction='long', tv_data=c,
                        get_ohlcv_fn=lambda t=c['symbol']: _get_ohlcv_for_ticker(t)
                    )
                    analyzed_long.append(analysis)
                except Exception as e:
                    logger.warning(f"Analysis failed for {c['symbol']}: {e}")
                    analyzed_long.append({
                        'symbol': c['symbol'], 'direction': 'LONG', 'price': c['price'],
                        'composite_score': c['signal_strength'], 'tv_data': c,
                        'recommendation': {'label': c['recommendation']},
                        'brooks_analysis': {'pattern': 'N/A'}
                    })
            # Analyze SHORT
            for c in short_candidates[:top_n * 2]:
                try:
                    analysis = analyzer.analyze_candidate(
                        ticker=c['symbol'], direction='short', tv_data=c,
                        get_ohlcv_fn=lambda t=c['symbol']: _get_ohlcv_for_ticker(t)
                    )
                    analyzed_short.append(analysis)
                except Exception as e:
                    logger.warning(f"Analysis failed for {c['symbol']}: {e}")
                    analyzed_short.append({
                        'symbol': c['symbol'], 'direction': 'SHORT', 'price': c['price'],
                        'composite_score': c['signal_strength'], 'tv_data': c,
                        'recommendation': {'label': c['recommendation']},
                        'brooks_analysis': {'pattern': 'N/A'}
                    })
            # Sort and limit
            analyzed_long.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
            analyzed_short.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
            final_long = analyzed_long[:top_n]
            final_short = analyzed_short[:top_n]
        else:
            # Simple format without deep analysis
            final_long = [{
                'rank': i+1, 'symbol': c['symbol'], 'direction': 'LONG',
                'price': c['price'], 'composite_score': c['signal_strength'],
                'tv_data': c, 'recommendation': {'label': c['recommendation']},
                'brooks_analysis': {'note': 'Deep analysis disabled'}
            } for i, c in enumerate(long_candidates[:top_n])]
            final_short = [{
                'rank': i+1, 'symbol': c['symbol'], 'direction': 'SHORT',
                'price': c['price'], 'composite_score': c['signal_strength'],
                'tv_data': c, 'recommendation': {'label': c['recommendation']},
                'brooks_analysis': {'note': 'Deep analysis disabled'}
            } for i, c in enumerate(short_candidates[:top_n])]

        # Generate report
        report = f"""=================================================================
    MARKET OPPORTUNITIES SCAN - {datetime.now(et).strftime('%Y-%m-%d %H:%M')} EST
=================================================================
Markets: {market.upper()} | Filters: Price>${min_price}, MCap>${min_market_cap:,}

TOP LONG CANDIDATES:
"""
        for c in final_long:
            report += f"  {c.get('rank', '?')}. {c['symbol']} - ${c['price']:.2f} | Score: {c['composite_score']}/100\n"
        report += "\nTOP SHORT CANDIDATES:\n"
        for c in final_short:
            report += f"  {c.get('rank', '?')}. {c['symbol']} - ${c['price']:.2f} | Score: {c['composite_score']}/100\n"

        return {
            'scan_time': datetime.now(et).strftime('%Y-%m-%d %H:%M:%S EST'),
            'filters': {'market': market, 'min_price': min_price, 'min_market_cap': f"${min_market_cap:,}"},
            'long_candidates': final_long,
            'short_candidates': final_short,
            'total_long_found': len(long_candidates),
            'total_short_found': len(short_candidates),
            'report': report
        }
    except Exception as e:
        logger.error(f"Market scan failed: {e}")
        raise ValueError(f"Market scan failed: {str(e)}")


# =============================================================================
# COMPANY OVERVIEW TOOLS (Section A)
# =============================================================================

@mcp.tool()
def get_ticker_data(
    ticker: str,
    max_news: int = 5,
    max_recommendations: int = 5,
    max_upgrades: int = 5
) -> dict[str, Any]:
    """Get comprehensive ticker data: metrics, calendar, news, recommendations."""
    try:
        info = yf_call(ticker, "info") or {}
        calendar = yf_call(ticker, "calendar") or {}
        news = yf_call(ticker, "news") or []
        recommendations = yf_call(ticker, "recommendations") or []
        upgrades = yf_call(ticker, "upgrades_downgrades") or []

        return {
            'ticker': ticker,
            'info': {
                'name': info.get('shortName', ticker),
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'market_cap': info.get('marketCap', 0),
                'price': info.get('currentPrice', info.get('regularMarketPrice', 0)),
                'pe_ratio': info.get('trailingPE', 'N/A'),
                'forward_pe': info.get('forwardPE', 'N/A'),
                'eps': info.get('trailingEps', 'N/A'),
                'revenue': info.get('totalRevenue', 0),
                'profit_margin': info.get('profitMargins', 'N/A'),
                'beta': info.get('beta', 'N/A'),
            },
            'calendar': calendar,
            'news': news[:max_news] if isinstance(news, list) else [],
            'recommendations_count': len(recommendations) if hasattr(recommendations, '__len__') else 0,
            'recent_upgrades': upgrades[:max_upgrades] if hasattr(upgrades, '__iter__') else []
        }
    except Exception as e:
        return {'ticker': ticker, 'error': str(e)}


@mcp.tool()
def calculate_fundamental_scores(ticker: str, max_periods: int = 8) -> dict[str, Any]:
    """Calculate Piotroski F-Score (0-9) and Altman Z-Score for bankruptcy risk."""
    try:
        info = yf_call(ticker, "info") or {}
        financials = yf_call(ticker, "quarterly_financials")
        balance = yf_call(ticker, "quarterly_balance_sheet")
        cashflow = yf_call(ticker, "quarterly_cashflow")

        # Simplified F-Score calculation
        f_score = 0
        # Positive net income
        if info.get('netIncomeToCommon', 0) > 0:
            f_score += 1
        # Positive operating cash flow
        if info.get('operatingCashflow', 0) > 0:
            f_score += 1
        # Positive ROA
        if info.get('returnOnAssets', 0) > 0:
            f_score += 1
        # Operating cash flow > net income (quality)
        if info.get('operatingCashflow', 0) > info.get('netIncomeToCommon', 0):
            f_score += 1
        # Current ratio > 1
        if info.get('currentRatio', 0) > 1:
            f_score += 1
        # Positive gross margin
        if info.get('grossMargins', 0) > 0:
            f_score += 1
        # Positive operating margin
        if info.get('operatingMargins', 0) > 0:
            f_score += 1

        # Simplified Z-Score
        total_assets = info.get('totalAssets', 1)
        current_assets = info.get('totalCurrentAssets', 0)
        current_liabilities = info.get('totalCurrentLiabilities', 0)
        retained_earnings = info.get('retainedEarnings', 0)
        ebit = info.get('ebitda', 0)
        market_cap = info.get('marketCap', 0)
        total_liabilities = info.get('totalLiab', 1)
        revenue = info.get('totalRevenue', 0)

        working_capital = current_assets - current_liabilities
        z_score = (
            1.2 * (working_capital / max(total_assets, 1)) +
            1.4 * (retained_earnings / max(total_assets, 1)) +
            3.3 * (ebit / max(total_assets, 1)) +
            0.6 * (market_cap / max(total_liabilities, 1)) +
            1.0 * (revenue / max(total_assets, 1))
        )

        return {
            'ticker': ticker,
            'piotroski_f_score': f_score,
            'f_score_interpretation': 'Strong' if f_score >= 7 else 'Moderate' if f_score >= 4 else 'Weak',
            'altman_z_score': round(z_score, 2),
            'z_score_interpretation': 'Safe' if z_score > 2.99 else 'Grey Zone' if z_score > 1.81 else 'Distress'
        }
    except Exception as e:
        return {'ticker': ticker, 'error': str(e)}


# =============================================================================
# CATALYST TOOLS (Section B)
# =============================================================================

@mcp.tool()
def get_earnings_history(ticker: str, max_entries: int = 8) -> str:
    """Get historical earnings with beat/miss rate for last N quarters."""
    try:
        earnings = yf_call(ticker, "earnings_history")
        if earnings is None or earnings.empty:
            return f"No earnings history available for {ticker}"
        return earnings.head(max_entries).to_csv()
    except Exception as e:
        return f"Error getting earnings history: {e}"


@mcp.tool()
def get_insider_trades(ticker: str, max_trades: int = 20) -> str:
    """Get recent insider trading activity."""
    try:
        insider = yf_call(ticker, "insider_transactions")
        if insider is None or insider.empty:
            return f"No insider trades available for {ticker}"
        return insider.head(max_trades).to_csv()
    except Exception as e:
        return f"Error getting insider trades: {e}"


@mcp.tool()
def get_institutional_holders(ticker: str, top_n: int = 20) -> dict[str, Any]:
    """Get major institutional holders."""
    try:
        holders = yf_call(ticker, "institutional_holders")
        mutualfund = yf_call(ticker, "mutualfund_holders")
        return {
            'ticker': ticker,
            'institutional_holders': holders.head(top_n).to_dict() if holders is not None and not holders.empty else {},
            'mutualfund_holders': mutualfund.head(top_n).to_dict() if mutualfund is not None and not mutualfund.empty else {}
        }
    except Exception as e:
        return {'ticker': ticker, 'error': str(e)}


# =============================================================================
# TECHNICAL TOOLS (Section D)
# =============================================================================

@mcp.tool()
def analyze_technical(
    ticker: str,
    period: Literal["3mo", "6mo", "1y", "2y"] = "6mo",
    include_ml_analysis: bool = False
) -> dict[str, Any]:
    """Comprehensive technical analysis: RSI, MACD, Bollinger Bands, Moving Averages."""
    try:
        hist = yf_call(ticker, "history", period=period, interval="1d")
        if hist is None or hist.empty:
            return {'ticker': ticker, 'error': 'No price data available'}

        analysis = TechnicalAnalysis.calculate_comprehensive_indicators(hist)
        analysis['ticker'] = ticker
        analysis['period'] = period
        return analysis
    except Exception as e:
        return {'ticker': ticker, 'error': str(e)}


@mcp.tool()
def calculate_relative_strength(
    ticker: str,
    benchmark: str = "SPY",
    period: Literal["1mo", "3mo", "6mo", "1y"] = "3mo"
) -> dict[str, Any]:
    """Calculate relative strength vs benchmark (IBD-style 0-100 score)."""
    try:
        ticker_hist = yf_call(ticker, "history", period=period, interval="1d")
        bench_hist = yf_call(benchmark, "history", period=period, interval="1d")

        if ticker_hist is None or ticker_hist.empty or bench_hist is None or bench_hist.empty:
            return {'ticker': ticker, 'error': 'Price data unavailable'}

        ticker_return = (ticker_hist['Close'].iloc[-1] / ticker_hist['Close'].iloc[0] - 1) * 100
        bench_return = (bench_hist['Close'].iloc[-1] / bench_hist['Close'].iloc[0] - 1) * 100
        outperformance = ticker_return - bench_return

        # Simple RS score (0-100)
        rs_score = min(100, max(0, 50 + outperformance * 2))

        return {
            'ticker': ticker,
            'benchmark': benchmark,
            'period': period,
            'ticker_return': round(ticker_return, 2),
            'benchmark_return': round(bench_return, 2),
            'outperformance': round(outperformance, 2),
            'rs_score': round(rs_score, 0),
            'classification': 'Leader' if rs_score >= 70 else 'Average' if rs_score >= 40 else 'Laggard'
        }
    except Exception as e:
        return {'ticker': ticker, 'error': str(e)}


@mcp.tool()
def analyze_volume(
    ticker: str,
    period: Literal["1mo", "3mo", "6mo"] = "3mo"
) -> dict[str, Any]:
    """Volume analysis: OBV trend, relative volume, accumulation/distribution."""
    try:
        hist = yf_call(ticker, "history", period=period, interval="1d")
        if hist is None or hist.empty:
            return {'ticker': ticker, 'error': 'No price data'}

        # OBV calculation
        obv = [0]
        for i in range(1, len(hist)):
            if hist['Close'].iloc[i] > hist['Close'].iloc[i-1]:
                obv.append(obv[-1] + hist['Volume'].iloc[i])
            elif hist['Close'].iloc[i] < hist['Close'].iloc[i-1]:
                obv.append(obv[-1] - hist['Volume'].iloc[i])
            else:
                obv.append(obv[-1])

        avg_vol = hist['Volume'].mean()
        recent_vol = hist['Volume'].iloc[-5:].mean()
        rel_volume = recent_vol / avg_vol if avg_vol > 0 else 1

        obv_trend = 'Bullish' if obv[-1] > obv[-10] else 'Bearish' if obv[-1] < obv[-10] else 'Neutral'

        return {
            'ticker': ticker,
            'period': period,
            'avg_volume': int(avg_vol),
            'recent_volume': int(recent_vol),
            'relative_volume': round(rel_volume, 2),
            'obv_current': obv[-1],
            'obv_trend': obv_trend,
            'volume_signal': 'Strong' if rel_volume > 1.5 else 'Normal' if rel_volume > 0.8 else 'Weak'
        }
    except Exception as e:
        return {'ticker': ticker, 'error': str(e)}


# =============================================================================
# SERVER ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    mcp.run()
