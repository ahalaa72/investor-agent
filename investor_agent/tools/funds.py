"""Fund analysis tools: mutual fund analysis, comparison, and ETF analysis."""
import logging
from typing import Any

import yfinance as yf

from ..core.validation import validate_ticker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper functions (module-level)
# ---------------------------------------------------------------------------

def _calculate_fund_returns(ticker: str, periods: list[str] = None) -> dict:
    """Calculate returns for various periods."""
    import numpy as np
    from datetime import datetime, timedelta

    if periods is None:
        periods = ["1mo", "3mo", "6mo", "1y", "3y", "5y", "ytd"]

    t = yf.Ticker(ticker)
    returns = {}

    try:
        # Get max history for all calculations (Questrade primary, Yahoo fallback, cached)
        from .scanning import _get_ohlcv_cached
        hist = _get_ohlcv_cached(ticker, period="5y")
        if hist is None or hist.empty:
            return {"error": "No price history available"}

        current_price = hist['Close'].iloc[-1]

        # Calculate returns for each period
        period_mapping = {
            "1mo": 21,
            "3mo": 63,
            "6mo": 126,
            "1y": 252,
            "3y": 756,
            "5y": 1260
        }

        for period in periods:
            if period == "ytd":
                # Year to date
                year_start = datetime(datetime.now().year, 1, 1)
                ytd_data = hist[hist.index >= year_start.strftime('%Y-%m-%d')]
                if not ytd_data.empty:
                    start_price = ytd_data['Close'].iloc[0]
                    returns["ytd"] = round(((current_price - start_price) / start_price) * 100, 2)
            elif period in period_mapping:
                days = period_mapping[period]
                if len(hist) >= days:
                    start_price = hist['Close'].iloc[-days]
                    returns[period] = round(((current_price - start_price) / start_price) * 100, 2)

        return returns
    except Exception as e:
        return {"error": str(e)}


def _calculate_risk_metrics(ticker: str, benchmark: str = "SPY") -> dict:
    """Calculate comprehensive risk metrics."""
    import numpy as np

    try:
        # Get 3 years of data (Questrade primary, Yahoo fallback, cached)
        from .scanning import _get_ohlcv_cached
        fund_hist = _get_ohlcv_cached(ticker, period="3y")
        bench_hist = _get_ohlcv_cached(benchmark, period="3y")

        if fund_hist is None or fund_hist.empty:
            return {"error": "No price history available"}

        # Align dates
        common_dates = fund_hist.index.intersection(bench_hist.index)
        fund_prices = fund_hist.loc[common_dates, 'Close']
        bench_prices = bench_hist.loc[common_dates, 'Close']

        # Calculate daily returns
        fund_returns = np.log(fund_prices / fund_prices.shift(1)).dropna()
        bench_returns = np.log(bench_prices / bench_prices.shift(1)).dropna()

        # Risk-free rate (approximate)
        rf = 0.05 / 252  # ~5% annual, daily

        # Sharpe Ratio (annualized)
        excess_returns = fund_returns - rf
        sharpe = (excess_returns.mean() * 252) / (fund_returns.std() * np.sqrt(252))

        # Sortino Ratio (only penalize downside)
        downside_returns = fund_returns[fund_returns < 0]
        if len(downside_returns) > 0:
            downside_std = downside_returns.std() * np.sqrt(252)
            sortino = (fund_returns.mean() * 252 - 0.05) / downside_std
        else:
            sortino = None

        # Maximum Drawdown
        cumulative = (1 + fund_returns).cumprod()
        rolling_max = cumulative.expanding().max()
        drawdown = (cumulative - rolling_max) / rolling_max
        max_drawdown = drawdown.min() * 100

        # Beta
        covariance = np.cov(fund_returns, bench_returns)[0, 1]
        variance = np.var(bench_returns)
        beta = covariance / variance if variance > 0 else 1.0

        # Alpha (annualized)
        fund_annual_return = fund_returns.mean() * 252
        bench_annual_return = bench_returns.mean() * 252
        alpha = (fund_annual_return - 0.05) - beta * (bench_annual_return - 0.05)

        # Volatility (annualized)
        volatility = fund_returns.std() * np.sqrt(252) * 100

        # Tracking Error
        tracking_error = (fund_returns - bench_returns).std() * np.sqrt(252) * 100

        # Information Ratio
        active_return = (fund_returns - bench_returns).mean() * 252
        info_ratio = active_return / (tracking_error / 100) if tracking_error > 0 else 0

        return {
            "sharpe_ratio": round(sharpe, 2) if not np.isnan(sharpe) else None,
            "sortino_ratio": round(sortino, 2) if sortino and not np.isnan(sortino) else None,
            "max_drawdown_pct": round(max_drawdown, 2),
            "beta": round(beta, 2),
            "alpha_pct": round(alpha * 100, 2),
            "volatility_pct": round(volatility, 2),
            "tracking_error_pct": round(tracking_error, 2),
            "information_ratio": round(info_ratio, 2) if not np.isnan(info_ratio) else None,
            "benchmark": benchmark
        }
    except Exception as e:
        return {"error": str(e)}


def _get_fund_recommendation(returns: dict, risk: dict, expense_ratio: float) -> dict:
    """Generate KEEP/WATCH/REPLACE recommendation."""
    score = 0
    reasons = []

    # Performance scoring (40 points)
    if "3y" in returns:
        if returns["3y"] > 30:  # >10% annualized
            score += 40
            reasons.append("Strong 3-year performance")
        elif returns["3y"] > 15:  # >5% annualized
            score += 25
            reasons.append("Moderate 3-year performance")
        else:
            score += 10
            reasons.append("Weak 3-year performance")

    # Risk scoring (30 points)
    if "sharpe_ratio" in risk and risk["sharpe_ratio"]:
        if risk["sharpe_ratio"] > 1.0:
            score += 30
            reasons.append(f"Excellent Sharpe ratio ({risk['sharpe_ratio']})")
        elif risk["sharpe_ratio"] > 0.5:
            score += 20
            reasons.append(f"Good Sharpe ratio ({risk['sharpe_ratio']})")
        else:
            score += 10
            reasons.append(f"Poor Sharpe ratio ({risk['sharpe_ratio']})")

    # Cost scoring (30 points)
    if expense_ratio is not None:
        if expense_ratio < 0.20:
            score += 30
            reasons.append(f"Very low expense ratio ({expense_ratio:.2%})")
        elif expense_ratio < 0.50:
            score += 20
            reasons.append(f"Reasonable expense ratio ({expense_ratio:.2%})")
        elif expense_ratio < 1.0:
            score += 10
            reasons.append(f"High expense ratio ({expense_ratio:.2%})")
        else:
            score += 0
            reasons.append(f"Very high expense ratio ({expense_ratio:.2%})")

    # Determine recommendation
    if score >= 70:
        recommendation = "KEEP"
        action = "Continue holding - strong performance and value"
    elif score >= 50:
        recommendation = "WATCH"
        action = "Monitor closely - mixed signals"
    else:
        recommendation = "REPLACE"
        action = "Consider alternatives with lower costs or better performance"

    return {
        "recommendation": recommendation,
        "score": score,
        "action": action,
        "reasons": reasons
    }


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register_tools(mcp):
    from .scanning import _get_ohlcv_cached
    from .technical_analysis import (
        analyze_technical_impl as analyze_technical,
        analyze_volume_tool_impl as analyze_volume_tool,
        calculate_relative_strength_tool_impl as calculate_relative_strength_tool,
        analyze_volatility_tool_impl as analyze_volatility_tool,
        find_support_resistance_impl as find_support_resistance,
    )
    from .options_analysis import analyze_options_mcmillan_impl as analyze_options_mcmillan

    @mcp.tool()
    def analyze_mutual_fund(ticker: str, benchmark: str = "SPY") -> dict[str, Any]:
        """
        Comprehensive mutual fund analysis with KEEP/WATCH/REPLACE recommendation.

        Data Sources (in order):
        1. Questrade API (primary) - position data, symbol info
        2. yfinance (fallback) - additional fund data for US funds

        Analyzes:
        - Performance: Position return, 1yr, 3yr, 5yr, YTD returns
        - Risk: Sharpe, Sortino, Max Drawdown, Beta, Alpha
        - Cost: Expense ratio analysis
        - Benchmark comparison

        Decision Framework:
        - KEEP: Score >= 70 (Strong performance, good risk-adjusted returns, low cost)
        - WATCH: Score 50-69 (Mixed signals, monitor closely)
        - REPLACE: Score < 50 (Underperforming, high cost, consider alternatives)

        Args:
            ticker: Mutual fund ticker symbol
            benchmark: Benchmark for comparison (default SPY)

        Returns:
            Comprehensive analysis with recommendation
        """
        from datetime import datetime
        from ..questrade import get_questrade_client

        ticker = validate_ticker(ticker)

        # QUESTRADE FIRST for ALL mutual funds
        try:
            q = get_questrade_client()

            # Get symbol info from Questrade
            symbol_info = q.get_symbol_info(ticker)

            questrade_data = {}
            if symbol_info and symbol_info.get('symbols'):
                sym = symbol_info['symbols'][0]
                questrade_data = {
                    'name': sym.get('description', ticker),
                    'nav': sym.get('prevDayClosePrice'),
                    'security_type': sym.get('securityType', 'MutualFund'),
                    'currency': sym.get('currency', 'CAD')
                }

            # Get position data from all accounts
            position_data = None
            try:
                accounts = q.get_accounts()
                for acct in accounts.get('accounts', []):
                    positions = q.get_account_positions(acct['number'])
                    for pos in positions.get('positions', []):
                        if pos['symbol'] == ticker and pos.get('openQuantity', 0) > 0:
                            total_cost = pos.get('totalCost', 0)
                            open_pnl = pos.get('openPnl', 0)
                            position_data = {
                                'quantity': pos.get('openQuantity', 0),
                                'current_value': pos.get('currentMarketValue', 0),
                                'total_cost': total_cost,
                                'open_pnl': open_pnl,
                                'return_pct': round((open_pnl / total_cost) * 100, 2) if total_cost > 0 else None
                            }
                            break
                    if position_data:
                        break
            except Exception as e:
                logger.warning(f"Could not fetch Questrade position data for {ticker}: {e}")

            # Determine fund family from symbol prefix
            fund_families = {
                'MFC': 'Mackenzie Investments',
                'RBF': 'RBC Funds',
                'LWF': 'IG Wealth Management (Investors Group)',
                'TDB': 'TD Asset Management',
                'DYN': 'Dynamic Funds',
                'FID': 'Fidelity'
            }
            prefix = ticker[:3].upper()
            fund_family = fund_families.get(prefix, None)

            # Try yfinance for additional data (US funds)
            yf_data = {}
            try:
                t = yf.Ticker(ticker)
                info = t.info
                if info and info.get('quoteType'):
                    yf_data = {
                        'name': info.get('longName') or info.get('shortName'),
                        'quote_type': info.get('quoteType', 'Unknown'),
                        'expense_ratio': info.get('annualReportExpenseRatio') or info.get('expenseRatio'),
                        'category': info.get('category'),
                        'fund_family': info.get('fundFamily'),
                        'total_assets': info.get('totalAssets'),
                        'yield_pct': info.get('yield'),
                        'ytd_return': info.get('ytdReturn')
                    }
                    # Get historical returns if available
                    returns = _calculate_fund_returns(ticker)
                    if not returns.get('error'):
                        yf_data['returns'] = returns
                    # Get risk metrics if available
                    risk = _calculate_risk_metrics(ticker, benchmark)
                    if not risk.get('error'):
                        yf_data['risk'] = risk
            except Exception as e:
                logger.debug(f"yfinance data not available for {ticker}: {e}")

            # Combine data sources - Questrade first, yfinance as supplement
            fund_name = questrade_data.get('name') or yf_data.get('name') or ticker
            current_nav = questrade_data.get('nav') or yf_data.get('nav')
            quote_type = questrade_data.get('security_type') or yf_data.get('quote_type', 'MutualFund')
            expense_ratio = yf_data.get('expense_ratio')
            if not fund_family:
                fund_family = yf_data.get('fund_family')

            # Build analysis reasons and score
            reasons = []
            score = 50  # Start neutral

            # Score based on position performance (Questrade)
            if position_data and position_data.get('return_pct') is not None:
                ret = position_data['return_pct']
                if ret > 15:
                    score += 20
                    reasons.append(f"✓ Strong position return: +{ret:.1f}%")
                elif ret > 5:
                    score += 10
                    reasons.append(f"✓ Positive position return: +{ret:.1f}%")
                elif ret > 0:
                    score += 5
                    reasons.append(f"~ Modest position return: +{ret:.1f}%")
                elif ret > -5:
                    reasons.append(f"~ Small position loss: {ret:.1f}%")
                elif ret > -15:
                    score -= 10
                    reasons.append(f"✗ Moderate position loss: {ret:.1f}%")
                else:
                    score -= 20
                    reasons.append(f"✗ Significant position loss: {ret:.1f}%")

            # Score based on expense ratio (yfinance)
            if expense_ratio:
                if expense_ratio < 0.005:  # < 0.5%
                    score += 15
                    reasons.append(f"✓ Low expense ratio: {expense_ratio*100:.2f}%")
                elif expense_ratio < 0.01:  # < 1%
                    score += 5
                    reasons.append(f"~ Moderate expense ratio: {expense_ratio*100:.2f}%")
                elif expense_ratio < 0.02:  # < 2%
                    reasons.append(f"⚠ High expense ratio: {expense_ratio*100:.2f}%")
                else:
                    score -= 10
                    reasons.append(f"✗ Very high expense ratio: {expense_ratio*100:.2f}%")
            else:
                reasons.append("⚠ Expense ratio not available (Canadian MFs typically 1.5-2.5%)")

            # Score based on historical returns (yfinance)
            if yf_data.get('returns') and yf_data['returns'].get('1y'):
                ret_1y = yf_data['returns']['1y']
                if ret_1y > 15:
                    score += 10
                    reasons.append(f"✓ Strong 1Y return: +{ret_1y:.1f}%")
                elif ret_1y > 5:
                    score += 5
                    reasons.append(f"✓ Positive 1Y return: +{ret_1y:.1f}%")
                elif ret_1y < -10:
                    score -= 10
                    reasons.append(f"✗ Weak 1Y return: {ret_1y:.1f}%")

            # Add fund family info
            if fund_family:
                reasons.append(f"Fund Family: {fund_family}")

            # Determine recommendation
            if score >= 70:
                recommendation = "KEEP"
                action = "Fund is performing well - continue holding"
            elif score >= 50:
                recommendation = "WATCH"
                action = "Monitor performance and consider lower-cost ETF alternatives"
            else:
                recommendation = "REPLACE"
                action = "Consider replacing with lower-cost index ETF"

            # Get recommendation with full data if available
            if yf_data.get('returns') and yf_data.get('risk') and expense_ratio:
                full_rec = _get_fund_recommendation(
                    returns=yf_data['returns'],
                    risk=yf_data['risk'],
                    expense_ratio=expense_ratio
                )
                # Use the more detailed recommendation if available
                if full_rec.get('score', 0) > 0:
                    recommendation = full_rec['recommendation']
                    score = full_rec['score']
                    action = full_rec['action']
                    reasons = full_rec['reasons'] + reasons

            return {
                "ticker": ticker,
                "name": fund_name,
                "type": quote_type,
                "analysis_date": datetime.now().strftime('%Y-%m-%d %H:%M'),
                "current_nav": current_nav,
                "currency": questrade_data.get('currency', 'USD'),
                "data_source": "Questrade (primary) + yfinance (supplemental)",

                # Position info from Questrade
                "position": position_data,

                # Performance
                "performance": {
                    "position_return_pct": position_data.get('return_pct') if position_data else None,
                    "ytd_return_pct": yf_data.get('returns', {}).get("ytd"),
                    "1yr_return_pct": yf_data.get('returns', {}).get("1y"),
                    "3yr_return_pct": yf_data.get('returns', {}).get("3y"),
                    "5yr_return_pct": yf_data.get('returns', {}).get("5y")
                },

                # Risk Metrics
                "risk_metrics": yf_data.get('risk', {"note": "Risk metrics not available"}),

                # Cost
                "expense_ratio": expense_ratio,
                "expense_ratio_pct": f"{expense_ratio * 100:.2f}%" if expense_ratio else "N/A",

                # Recommendation
                "recommendation": recommendation,
                "score": score,
                "action": action,
                "analysis_reasons": reasons,

                # Fund info
                "fund_info": {
                    "category": yf_data.get('category'),
                    "fund_family": fund_family,
                    "total_assets": yf_data.get('total_assets'),
                    "yield_pct": yf_data.get('yield_pct'),
                    "ytd_return": yf_data.get('ytd_return')
                },

                "benchmark": benchmark,
                "methodology": "Questrade-first analysis with yfinance supplemental data"
            }

        except Exception as e:
            logger.error(f"Error in analyze_mutual_fund for {ticker}: {e}")
            raise ValueError(f"Mutual fund analysis failed: {str(e)}")

    @mcp.tool()
    def compare_mutual_funds(
        current_fund: str,
        candidates: list[str]
    ) -> dict[str, Any]:
        """
        Compare current fund against alternative candidates.

        Scoring System (100 points):
        - Performance Score (40%): Risk-adjusted returns
        - Cost Score (30%): Expense ratio comparison
        - Risk Score (30%): Volatility, max drawdown

        Args:
            current_fund: Current fund ticker
            candidates: List of alternative fund tickers to compare

        Returns:
            Ranked comparison with replacement recommendation
        """
        from datetime import datetime

        all_funds = [current_fund] + candidates
        analyses = []

        for fund in all_funds:
            try:
                analysis = analyze_mutual_fund(fund)
                analyses.append({
                    "ticker": fund,
                    "name": analysis.get("name", fund),
                    "score": analysis.get("score", 0),
                    "recommendation": analysis.get("recommendation"),
                    "expense_ratio": analysis.get("expense_ratio"),
                    "sharpe_ratio": analysis.get("risk_metrics", {}).get("sharpe_ratio"),
                    "3yr_return": analysis.get("performance", {}).get("3yr_return_pct"),
                    "max_drawdown": analysis.get("risk_metrics", {}).get("max_drawdown_pct")
                })
            except Exception as e:
                logger.warning(f"Could not analyze {fund}: {e}")
                analyses.append({
                    "ticker": fund,
                    "error": str(e)
                })

        # Rank by score
        valid_analyses = [a for a in analyses if "error" not in a]
        ranked = sorted(valid_analyses, key=lambda x: x.get("score", 0), reverse=True)

        # Add ranks
        for i, a in enumerate(ranked):
            a["rank"] = i + 1

        # Find current fund's rank
        current_analysis = next((a for a in ranked if a["ticker"] == current_fund), None)
        current_rank = current_analysis["rank"] if current_analysis else None

        # Determine action
        if current_rank == 1:
            action = "KEEP"
            rationale = "Current fund is the best option among alternatives"
            suggested_replacement = None
        elif current_rank and current_rank <= 2:
            action = "WATCH"
            rationale = f"Consider {ranked[0]['ticker']} - higher ranked alternative"
            suggested_replacement = ranked[0]["ticker"]
        else:
            action = "REPLACE"
            rationale = f"Switch to {ranked[0]['ticker']} for better performance/cost"
            suggested_replacement = ranked[0]["ticker"]

        return {
            "comparison_date": datetime.now().strftime('%Y-%m-%d %H:%M'),
            "current_fund": current_fund,
            "current_rank": current_rank,
            "total_compared": len(ranked),

            "action": action,
            "rationale": rationale,
            "suggested_replacement": suggested_replacement,

            "rankings": ranked,

            "comparison_summary": {
                "best_performer": ranked[0]["ticker"] if ranked else None,
                "lowest_cost": min(valid_analyses, key=lambda x: x.get("expense_ratio") or 999)["ticker"] if valid_analyses else None,
                "best_sharpe": max(valid_analyses, key=lambda x: x.get("sharpe_ratio") or -999)["ticker"] if valid_analyses else None
            },

            "methodology": "Ranking based on combined score (40% performance, 30% cost, 30% risk)"
        }

    @mcp.tool()
    def analyze_etf(ticker: str, include_options: bool = True) -> dict[str, Any]:
        """
        ETF-specific analysis (no fundamentals, focus on technicals and options).

        Includes:
        - Technical analysis (Al Brooks price action)
        - Options analysis with Greeks (if liquid)
        - Volume analysis (VWAP, OBV)
        - Relative strength vs SPY
        - ETF-specific metrics (tracking error, premium/discount)

        Skips: Fundamentals, earnings, insiders (not applicable to ETFs)

        Args:
            ticker: ETF ticker symbol
            include_options: Whether to include options analysis (default True)

        Returns:
            Comprehensive ETF analysis
        """
        from datetime import datetime

        ticker = validate_ticker(ticker)

        try:
            t = yf.Ticker(ticker)
            info = t.info

            # Basic info
            etf_name = info.get('longName') or info.get('shortName') or ticker
            current_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')

            result = {
                "ticker": ticker,
                "name": etf_name,
                "type": "ETF",
                "analysis_date": datetime.now().strftime('%Y-%m-%d %H:%M'),
                "current_price": current_price
            }

            # Technical Analysis
            try:
                technical = analyze_technical(ticker, period="3mo", include_ml_analysis=True)
                result["technical_analysis"] = technical
            except Exception as e:
                result["technical_analysis"] = {"error": str(e)}

            # Volume Analysis
            try:
                volume = analyze_volume_tool(ticker, period="3mo")
                result["volume_analysis"] = volume
            except Exception as e:
                result["volume_analysis"] = {"error": str(e)}

            # Relative Strength
            try:
                rs = calculate_relative_strength_tool(ticker, benchmark="SPY", period="3mo")
                result["relative_strength"] = rs
            except Exception as e:
                result["relative_strength"] = {"error": str(e)}

            # Volatility
            try:
                volatility = analyze_volatility_tool(ticker, period="3mo")
                result["volatility"] = volatility
            except Exception as e:
                result["volatility"] = {"error": str(e)}

            # Support/Resistance
            try:
                levels = find_support_resistance(ticker, lookback_period="1mo")
                result["support_resistance"] = levels
            except Exception as e:
                result["support_resistance"] = {"error": str(e)}

            # Options Analysis (if liquid and requested)
            if include_options:
                try:
                    # Check if options exist
                    options_exist = len(t.options) > 0 if hasattr(t, 'options') else False

                    if options_exist:
                        options = analyze_options_mcmillan(ticker)
                        result["options_analysis"] = options
                        result["options_available"] = True
                    else:
                        result["options_available"] = False
                        result["options_analysis"] = {"note": "No options available for this ETF"}
                except Exception as e:
                    result["options_available"] = False
                    result["options_analysis"] = {"error": str(e)}

            # ETF-specific metrics
            result["etf_metrics"] = {
                "expense_ratio": info.get('annualReportExpenseRatio') or info.get('expenseRatio'),
                "nav": info.get('navPrice'),
                "total_assets": info.get('totalAssets'),
                "volume": info.get('volume'),
                "avg_volume": info.get('averageVolume'),
                "52w_high": info.get('fiftyTwoWeekHigh'),
                "52w_low": info.get('fiftyTwoWeekLow'),
                "yield": info.get('yield')
            }

            # Generate verdict
            al_brooks_direction = "LONG"
            if "technical_analysis" in result and isinstance(result["technical_analysis"], dict):
                if "al_brooks" in result["technical_analysis"]:
                    al_brooks_direction = result["technical_analysis"]["al_brooks"].get("always_in_direction", "LONG")

            options_verdict = "N/A"
            if result.get("options_available") and "options_analysis" in result:
                if isinstance(result["options_analysis"], dict):
                    summary = result["options_analysis"].get("summary", {})
                    sentiment = summary.get("sentiment", "NEUTRAL")
                    smart_money = summary.get("smart_money_signal", "NEUTRAL")

                    if sentiment in ["BULLISH", "EXTREMELY_BULLISH"] or smart_money == "BULLISH":
                        options_verdict = "SUPPORTS_LONG"
                    elif sentiment in ["BEARISH", "EXTREMELY_BEARISH"] or smart_money == "BEARISH":
                        options_verdict = "OPPOSES_LONG"
                    else:
                        options_verdict = "NEUTRAL"

            result["verdict"] = {
                "al_brooks_direction": al_brooks_direction,
                "options_verdict": options_verdict,
                "combined": "ALIGNED" if (al_brooks_direction == "LONG" and options_verdict == "SUPPORTS_LONG") else
                            "OPPOSED" if (al_brooks_direction == "SHORT" and options_verdict == "OPPOSES_LONG") else "MIXED"
            }

            result["methodology"] = "Al Brooks (Price Action) + McMillan (Options) - No fundamentals for ETFs"

            return result

        except Exception as e:
            logger.error(f"Error in analyze_etf for {ticker}: {e}")
            raise ValueError(f"ETF analysis failed: {str(e)}")
