"""Trading signal generation tools - portfolio summary and trading signals.

2 MCP tools + 1 helper for portfolio summary generation and
complete trading signal generation with 5-gate validation system.

MCP tools:
    - get_portfolio_summary: Portfolio analysis with asset type detection
    - generate_trading_signal: Actionable trading signal with 5-gate validation

Helpers:
    - fetch_analysis_data: Consolidates all API calls for a ticker (not an MCP tool)
"""
import logging
import yfinance as yf
from typing import Any, Literal

from ..core.validation import validate_ticker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level reference, populated by register_tools()
# ---------------------------------------------------------------------------
generate_trading_signal_impl = None


def fetch_analysis_data(ticker: str) -> dict[str, Any]:
    """
    Fetch all analysis data ONCE for a ticker.

    This function consolidates all 9 API calls needed for trading signal generation
    to avoid redundant calls. The returned dict can be passed to generate_trading_signal
    via the cached_data parameter.

    Returns:
        dict with keys:
        - quotes: Questrade quotes data
        - catalyst: Catalyst strength analysis
        - volume: Volume/CVD analysis with Dalio metrics
        - relative_strength: RS Score analysis
        - options: Options McMillan analysis (if available)
        - institutional: Institutional holders data
        - quality: Quality/F-Score analysis
        - exhaustion: Exhaustion/freshness analysis
        - technical: Technical analysis (RSI, MACD, Brooks, etc.)
        - ohlcv: OHLCV price data
    """
    from .questrade_api import get_questrade_quotes_impl as get_questrade_quotes
    from .scanning import _get_ohlcv_cached
    from .technical_analysis import (
        analyze_technical_impl as analyze_technical,
        analyze_volume_tool_impl as analyze_volume_tool,
        calculate_relative_strength_tool_impl as calculate_relative_strength_tool,
    )
    from .catalysts import (
        detect_catalyst_strength_impl as detect_catalyst_strength,
        calculate_quality_score_impl as calculate_quality_score,
    )
    from .options_analysis import analyze_options_mcmillan_impl as analyze_options_mcmillan
    from .financial_data import get_institutional_holders_impl as get_institutional_holders

    ticker = validate_ticker(ticker)
    cached = {}

    # 1. Quotes (Questrade or Yahoo fallback)
    try:
        cached['quotes'] = get_questrade_quotes([ticker])
    except Exception as e:
        logger.warning(f"Failed to fetch quotes for {ticker}: {e}")
        cached['quotes'] = None

    # 2. Catalyst analysis
    try:
        cached['catalyst'] = detect_catalyst_strength(ticker)
    except Exception as e:
        logger.warning(f"Failed to fetch catalyst for {ticker}: {e}")
        cached['catalyst'] = None

    # 3. Volume/CVD with Dalio metrics
    try:
        cached['volume'] = analyze_volume_tool(ticker, period="3mo")
    except Exception as e:
        logger.warning(f"Failed to fetch volume data for {ticker}: {e}")
        cached['volume'] = None

    # 4. Relative Strength Score
    try:
        cached['relative_strength'] = calculate_relative_strength_tool(ticker=ticker, benchmark="SPY", period="3mo")
    except Exception as e:
        logger.warning(f"Failed to fetch RS Score for {ticker}: {e}")
        cached['relative_strength'] = None

    # 5. Options analysis (if available)
    try:
        t_temp = yf.Ticker(ticker)
        has_options = len(t_temp.options) > 0 if hasattr(t_temp, 'options') else False
        if has_options:
            cached['options'] = analyze_options_mcmillan(ticker)
        else:
            cached['options'] = None
    except Exception as e:
        logger.warning(f"Failed to fetch options data for {ticker}: {e}")
        cached['options'] = None

    # 6. Institutional holders
    try:
        cached['institutional'] = get_institutional_holders(ticker=ticker)
    except Exception as e:
        logger.warning(f"Failed to fetch institutional data for {ticker}: {e}")
        cached['institutional'] = None

    # 7. Quality/F-Score
    try:
        cached['quality'] = calculate_quality_score(ticker=ticker)
    except Exception as e:
        logger.warning(f"Failed to fetch quality score for {ticker}: {e}")
        cached['quality'] = None

    # 8. Exhaustion/Freshness
    try:
        from ..technical_analysis_bootstrap import calculate_exhaustion_score
        cached['exhaustion'] = calculate_exhaustion_score(ticker, period="3mo")
    except Exception as e:
        logger.warning(f"Failed to fetch exhaustion data for {ticker}: {e}")
        cached['exhaustion'] = None

    # 9. Technical analysis + OHLCV
    try:
        cached['ohlcv'] = _get_ohlcv_cached(ticker, period="3mo")
        cached['technical'] = analyze_technical(ticker, period="3mo", include_ml_analysis=False, include_trend_score=False)
    except Exception as e:
        logger.warning(f"Failed to fetch technical data for {ticker}: {e}")
        cached['ohlcv'] = None
        cached['technical'] = None

    return cached


def register_tools(mcp):
    from .questrade_api import (
        get_questrade_positions_impl as get_questrade_positions,
        get_questrade_quotes_impl as get_questrade_quotes,
    )
    from .scanning import _get_ohlcv_cached
    from .technical_analysis import (
        analyze_technical_impl as analyze_technical,
        analyze_volume_tool_impl as analyze_volume_tool,
        calculate_relative_strength_tool_impl as calculate_relative_strength_tool,
    )
    from .catalysts import (
        detect_catalyst_strength_impl as detect_catalyst_strength,
        calculate_quality_score_impl as calculate_quality_score,
    )
    from .options_analysis import (
        analyze_options_mcmillan_impl as analyze_options_mcmillan,
        analyze_iv_skew_impl as analyze_iv_skew,
        analyze_iv_term_structure_impl as analyze_iv_term_structure,
    )
    from .financial_data import get_institutional_holders_impl as get_institutional_holders
    from .ml_tools import find_similar_historical_setups_impl as find_similar_historical_setups

    # Import research-backed entry/exit strategies
    from ..entry_exit_strategy import (
        calculate_atr_stop_loss,
        determine_entry_strategy,
        calculate_profit_target,
        calculate_optimized_macd,
        calculate_adx,
        get_economic_context,
    )

    @mcp.tool()
    def get_portfolio_summary(account_number: str) -> dict[str, Any]:
        """
        Generate portfolio summary with asset type detection and appropriate analysis.

        For each position:
        - Detects type: STOCK / ETF / MUTUAL_FUND
        - Routes to appropriate analysis
        - Aggregates results by type

        Args:
            account_number: Questrade account number

        Returns:
            Portfolio summary grouped by asset type
        """
        from datetime import datetime

        try:
            # Get positions from Questrade
            positions = get_questrade_positions(account_number)

            if not positions or 'positions' not in positions:
                return {"error": "Could not fetch positions"}

            result = {
                "account_number": account_number,
                "analysis_date": datetime.now().strftime('%Y-%m-%d %H:%M'),
                "stocks": [],
                "etfs": [],
                "mutual_funds": [],
                "summary": {
                    "total_positions": 0,
                    "stock_count": 0,
                    "etf_count": 0,
                    "mutual_fund_count": 0
                }
            }

            for position in positions['positions']:
                if position.get('openQuantity', 0) <= 0:
                    continue

                symbol = position.get('symbol', '')
                if not symbol:
                    continue

                result["summary"]["total_positions"] += 1

                # Detect asset type - Use PREFIX first (Canadian mutual funds), then Questrade symbolId lookup
                mf_prefixes = ['MFC', 'RBF', 'LWF', 'TDB', 'DYN', 'FID', 'CIG']

                position_info = {
                    "symbol": symbol,
                    "quantity": position.get('openQuantity'),
                    "current_price": position.get('currentPrice'),
                    "current_value": position.get('currentMarketValue'),
                    "open_pnl": position.get('openPnl'),
                    "open_pnl_pct": round((position.get('openPnl', 0) / position.get('totalCost', 1)) * 100, 2)
                        if position.get('totalCost') else 0
                }

                # Mutual fund detection by prefix (Canadian funds not in stock APIs)
                if any(symbol.startswith(p) for p in mf_prefixes):
                    result["summary"]["mutual_fund_count"] += 1
                    position_info["type"] = "MUTUAL_FUND"
                    position_info["analysis_note"] = "Full analysis available: 'analyze my mutual funds'"
                    result["mutual_funds"].append(position_info)

                # ETF detection - check symbol suffix, known ETF tickers, or yfinance fallback
                elif symbol.endswith('.TO') or symbol in ['VIXY', 'TSLQ', 'SPY', 'QQQ', 'VTI', 'SQQQ', 'SPXL']:
                    result["summary"]["etf_count"] += 1
                    position_info["type"] = "ETF"
                    # Light analysis for ETF
                    try:
                        rs = calculate_relative_strength_tool(symbol, benchmark="SPY", period="1mo")
                        position_info["rs_vs_spy"] = rs.get("rs_score") if isinstance(rs, dict) else None
                    except:
                        position_info["rs_vs_spy"] = None
                    result["etfs"].append(position_info)

                else:
                    # Fallback: Use yfinance to detect ETF vs STOCK
                    try:
                        t = yf.Ticker(symbol)
                        info = t.info
                        quote_type = info.get('quoteType', 'EQUITY')
                    except:
                        quote_type = 'EQUITY'  # Default to stock on error

                    if quote_type == 'ETF':
                        result["summary"]["etf_count"] += 1
                        position_info["type"] = "ETF"
                        try:
                            rs = calculate_relative_strength_tool(symbol, benchmark="SPY", period="1mo")
                            position_info["rs_vs_spy"] = rs.get("rs_score") if isinstance(rs, dict) else None
                        except:
                            position_info["rs_vs_spy"] = None
                        result["etfs"].append(position_info)

                    else:  # Stock
                        result["summary"]["stock_count"] += 1
                        position_info["type"] = "STOCK"
                        # Enhanced analysis for stock with Al Brooks price action
                        try:
                            rs = calculate_relative_strength_tool(symbol, benchmark="SPY", period="1mo")
                            position_info["rs_vs_spy"] = rs.get("rs_score") if isinstance(rs, dict) else None
                        except:
                            position_info["rs_vs_spy"] = None

                        # Add Al Brooks price action analysis for education
                        try:
                            tech_analysis = analyze_technical(symbol, period="3mo", include_ml_analysis=True)
                            if isinstance(tech_analysis, dict) and "al_brooks" in tech_analysis:
                                brooks = tech_analysis["al_brooks"]

                                # Build comprehensive educational paragraph
                                always_in = brooks.get("always_in_direction", "UNKNOWN")
                                pattern = brooks.get("pattern", "none")
                                pattern_desc = brooks.get("pattern_description", "")
                                probability = brooks.get("adjusted_probability", 50)
                                trap_risk = brooks.get("trap_risk", "UNKNOWN")
                                bar_reading = brooks.get("bar_reading", "")
                                commentary = brooks.get("commentary", "")

                                # Educational explanation paragraph
                                educational_paragraph = (
                                    f"📚 AL BROOKS PRICE ACTION LESSON:\n\n"
                                    f"WHAT THE MARKET IS DOING: The market is currently 'Always-In {always_in}', which means "
                                    f"{'bulls are in control and you should look for opportunities to buy dips' if always_in == 'LONG' else 'bears are in control and you should look for opportunities to sell rallies' if always_in == 'SHORT' else 'the market is in balance with no clear directional bias'}. "
                                    f"\n\n"
                                    f"THE PATTERN: {pattern_desc}. "
                                    f"{'This is a continuation pattern, meaning the trend is likely to continue in the same direction. ' if 'continuation' in pattern_desc.lower() else ''}"
                                    f"{'This is a reversal pattern, meaning the trend may be changing direction. Be cautious. ' if 'reversal' in pattern_desc.lower() else ''}"
                                    f"\n\n"
                                    f"RECENT PRICE ACTION: {bar_reading}. "
                                    f"\n\n"
                                    f"WHY THIS MATTERS: {commentary} "
                                    f"The probability of success for this setup is {probability}%, which is "
                                    f"{'strong - this is a high-probability trade setup' if probability >= 60 else 'moderate - proceed with caution and wait for confirmation' if probability >= 50 else 'weak - avoid trading until a clearer setup develops'}. "
                                    f"\n\n"
                                    f"TRAP WARNING: Trap risk is {trap_risk}. "
                                    f"{'This means there is significant risk of a false breakout or reversal - wait for strong confirmation before entering.' if trap_risk == 'HIGH' else 'This setup looks clean with minimal trap risk.' if trap_risk == 'LOW' else 'Exercise normal caution.'}"
                                    f"\n\n"
                                    f"TRADING IMPLICATION: "
                                    f"{'Since we are Always-In LONG, look for pullbacks to buy. Avoid shorting against the trend.' if always_in == 'LONG' else 'Since we are Always-In SHORT, look for rallies to sell. Avoid buying against the trend.' if always_in == 'SHORT' else 'In a neutral market, wait for a breakout and trade in the direction of the breakout.'}"
                                )

                                position_info["al_brooks_price_action"] = {
                                    "always_in_direction": always_in,
                                    "pattern": pattern,
                                    "pattern_description": pattern_desc,
                                    "probability": probability,
                                    "trap_risk": trap_risk,
                                    "bar_reading": bar_reading,
                                    "commentary": commentary,
                                    "educational_paragraph": educational_paragraph
                                }
                            else:
                                position_info["al_brooks_price_action"] = {"error": "Al Brooks analysis unavailable"}
                        except Exception as e:
                            position_info["al_brooks_price_action"] = {"error": f"Analysis failed: {str(e)}"}

                        # Add Dalio Economic Machine analysis for education (NEW - January 2026)
                        try:
                            volume_analysis = analyze_volume_tool(symbol, period="3mo", include_quality_score=True)
                            if isinstance(volume_analysis, dict) and "dalio_metrics" in volume_analysis:
                                dalio = volume_analysis["dalio_metrics"]

                                # Extract from nested dicts (dalio_metrics uses nested structure)
                                _dr = dalio.get("dalio_ratio", {})
                                dalio_ratio = _dr.get("20d_avg", 1.0) if isinstance(_dr, dict) else (_dr if isinstance(_dr, (int, float)) else 1.0)
                                _cdf = dalio.get("cumulative_dollar_flow", {})
                                dollar_flow = _cdf.get("20d", 0) if isinstance(_cdf, dict) else (_cdf if isinstance(_cdf, (int, float)) else 0)
                                flow_direction = _cdf.get("direction", "NEUTRAL") if isinstance(_cdf, dict) else dalio.get("dollar_flow_direction", "NEUTRAL")
                                _ts = dalio.get("trend_sustainability", {})
                                sustainability = _ts.get("score", 50) if isinstance(_ts, dict) else (_ts if isinstance(_ts, (int, float)) else 50)
                                sustainability_grade = _ts.get("grade", "C") if isinstance(_ts, dict) else dalio.get("sustainability_grade", "C")

                                # Determine Dalio signal
                                dalio_bullish = dalio_ratio >= 1.0 and dollar_flow > 0 and sustainability >= 50
                                dalio_bearish = dalio_ratio < 1.0 and dollar_flow < 0 and sustainability >= 50

                                if dalio_bullish:
                                    dalio_signal = "BULLISH"
                                    dalio_action = "Money flow supports holding LONG positions. Consider adding on pullbacks."
                                elif dalio_bearish:
                                    dalio_signal = "BEARISH"
                                    dalio_action = "Money flow supports SHORT positions or exiting LONGs. Consider reducing exposure."
                                else:
                                    dalio_signal = "MIXED"
                                    dalio_action = "Money flow is not aligned. Wait for clarity before adding to positions."

                                # Educational paragraph
                                dalio_paragraph = (
                                    f"📚 DALIO ECONOMIC MACHINE LESSON:\n\n"
                                    f"WHAT THE MONEY IS DOING: The Dalio Ratio is {dalio_ratio:.4f}, which means "
                                    f"{'buyers are paying MORE than yesterday - bullish demand' if dalio_ratio > 1.0 else 'buyers are paying LESS than yesterday - weakening demand' if dalio_ratio < 1.0 else 'buyers are paying the same as yesterday - neutral'}. "
                                    f"Ray Dalio teaches: 'Price = Total Spending / Quantity Sold.' When the ratio is above 1.0, spending is outpacing volume - bullish.\n\n"
                                    f"DOLLAR FLOW ANALYSIS: Cumulative Dollar Flow is ${dollar_flow/1e6:.2f}M ({flow_direction}). "
                                    f"{'This shows NET ACCUMULATION - institutions are building positions.' if flow_direction == 'ACCUMULATION' else 'This shows NET DISTRIBUTION - institutions may be exiting.'}\n\n"
                                    f"TREND SUSTAINABILITY: Score is {sustainability}/100, Grade {sustainability_grade}. "
                                    f"{'This trend is SUSTAINABLE - money flow, volume, and momentum are aligned.' if sustainability >= 60 else 'This trend is MODERATING - some components are weakening.' if sustainability >= 40 else 'This trend is UNSUSTAINABLE - reversal risk is elevated.'}\n\n"
                                    f"TRADING IMPLICATION: {dalio_action}"
                                )

                                position_info["dalio_economic_machine"] = {
                                    "dalio_ratio": dalio_ratio,
                                    "dollar_flow": dollar_flow,
                                    "flow_direction": flow_direction,
                                    "sustainability_score": sustainability,
                                    "sustainability_grade": sustainability_grade,
                                    "signal": dalio_signal,
                                    "action": dalio_action,
                                    "educational_paragraph": dalio_paragraph
                                }
                            else:
                                position_info["dalio_economic_machine"] = {"error": "Dalio analysis unavailable"}
                        except Exception as e:
                            position_info["dalio_economic_machine"] = {"error": f"Dalio analysis failed: {str(e)}"}

                        result["stocks"].append(position_info)

            return result

        except Exception as e:
            logger.error(f"Error in get_portfolio_summary: {e}")
            raise ValueError(f"Portfolio summary failed: {str(e)}")

    @mcp.tool()
    def generate_trading_signal(
        ticker: str,
        direction: Literal["LONG", "SHORT"] | None = None,
        account_size: float = 10000.0,
        auto_store: bool = True,
        report_type: str = "comprehensive",
        cached_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Generate actionable trading signal with complete trading plan.

        NOW DATA-DRIVEN: Collects independent direction findings from each tool,
        determines consensus direction, then evaluates gates for that direction.

        5-GATE VALIDATION SYSTEM:
            GATE 1 (CATALYST): Earnings, Insider, UOA, News - with verification
            GATE 2 (FRESHNESS): Enhanced with Dalio Economic Machine (6 checks, need 5/6):
                - CVD alignment
                - Exhaustion < 50
                - Fresh direction
                - Dalio Ratio aligned (>1.0 for LONG, <1.0 for SHORT)
                - Dollar Flow aligned (positive for LONG, negative for SHORT)
                - Sustainability >= 50
            GATE 3 (BROOKS): Al Brooks price action analysis
            GATE 4 (QUALITY): Fundamental quality scores
            GATE 5 (OPTIONS TRADABILITY): Liquidity, IV environment, earnings proximity, expected moves

        Combines all analysis tools to produce:
        - data_direction: Direction determined by data (LONG/SHORT/NO_CONSENSUS)
        - direction_votes: How each tool voted on direction
        - Signal: STRONG_BUY / BUY / WATCH / NO_TRADE / SELL / STRONG_SELL
        - Complete trading plan with entry, stop, targets
        - Proof of validity from historical analysis
        - Gate status for all requirements
        - freshness_analysis: Includes Dalio metrics (dalio_ratio, dollar_flow, sustainability)
        - prediction_id: UUID of stored prediction (if auto_store=True)

        Args:
            ticker: Stock symbol
            direction: Optional expected direction. If None, uses data_direction.
                       If specified but conflicts with data, warning is issued.
            account_size: Account size for position sizing
            auto_store: Automatically store prediction for tracking (default: True)
            report_type: Report type for storage: "comprehensive", "concise", "scanner", "portfolio"

        Returns:
            Complete trading signal with plan and validation
        """
        from datetime import datetime

        ticker = validate_ticker(ticker)

        result = {
            "ticker": ticker,
            "direction": None,  # Will be set after data analysis
            "data_direction": "NO_CONSENSUS",  # NEW: What the data says
            "direction_votes": {},  # NEW: How each tool voted
            "signal": "NO_TRADE",
            "confidence": 0,
            "generated_at": datetime.now().isoformat(),
            "signal_version": "v2",  # NEW: Weighted voting with hard overrides
            "signal_algorithm": "weighted_voting_with_overrides",
            "trading_plan": None,
            "proof_of_validity": None,
            "gate_status": {
                "catalyst": "PENDING",
                "freshness": "PENDING",
                "brooks": "PENDING",
                "quality": "PENDING",
                "options_tradability": "PENDING"
            },
            "warnings": [],
            "summary": ""
        }

        score = 0
        max_score = 100

        # Track direction votes from each tool
        direction_votes = {
            "catalyst": "NEUTRAL",
            "cvd": "NEUTRAL",
            "exhaustion": "NEUTRAL",
            "brooks": "NEUTRAL",
            "dollar_flow": "NEUTRAL",  # NEW: Dollar Flow as primary signal (80% accurate)
            "rs_score": "NEUTRAL",  # CRITICAL: Long-term market position (40% weight)
            "pc_contrarian": "NEUTRAL",  # Contrarian: Put/Call ratio sentiment
            "institutional": "NEUTRAL",  # Institutional accumulation/distribution
            "f_score": "NEUTRAL"  # Quality/earnings quality score
        }

        try:
            # Get current price - TRY QUESTRADE FIRST (real-time), fallback to Yahoo Finance
            current_price = 0
            data_source = "UNKNOWN"
            quotes_response = None

            # Check cache first
            if cached_data and 'quotes' in cached_data and cached_data['quotes']:
                quotes_response = cached_data['quotes']
                logger.info(f"✓ Using CACHED quotes for {ticker}")
            else:
                # Fetch if not cached
                try:
                    # PRIORITY 1: Questrade (real-time)
                    quotes_response = get_questrade_quotes([ticker])
                except Exception as e:
                    logger.warning(f"Questrade quotes failed for {ticker}, falling back to Yahoo Finance: {e}")

            # Extract price from quotes_response
            try:
                if quotes_response and 'quotes' in quotes_response and len(quotes_response['quotes']) > 0:
                    quote = quotes_response['quotes'][0]
                    current_price = quote.get('lastTradePrice', 0)
                    data_source = quotes_response.get('data_source', 'QUESTRADE')
                    if not (cached_data and 'quotes' in cached_data):
                        logger.info(f"✓ Using {data_source} price for {ticker}: ${current_price}")
            except Exception as e:
                logger.warning(f"Failed to extract price from quotes: {e}")

            # FALLBACK: Yahoo Finance if Questrade failed
            if not current_price:
                t = yf.Ticker(ticker)
                info = t.info
                current_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
                data_source = "YAHOO_FINANCE"
                logger.warning(f"⚠️ Using {data_source} price for {ticker}: ${current_price} (may be delayed)")
                result["warnings"].append(f"Using delayed Yahoo Finance data - Questrade unavailable")

            if not current_price:
                result["warnings"].append("Could not get current price from any source")
                return result

            # Store data source in result for transparency
            result["price_data_source"] = data_source
            result["current_price"] = current_price

            # ========== STEP 1: COLLECT INDEPENDENT DIRECTION FINDINGS ==========

            # Get catalyst data (now returns catalyst_direction)
            catalyst_data = None
            if cached_data and 'catalyst' in cached_data:
                catalyst_data = cached_data['catalyst']
            else:
                try:
                    catalyst_data = detect_catalyst_strength(ticker)
                except Exception as e:
                    result["warnings"].append(f"Catalyst check failed: {e}")

            if catalyst_data:
                catalyst_dir = catalyst_data.get("catalyst_direction", "NEUTRAL")
                direction_votes["catalyst"] = catalyst_dir

            # Get volume/CVD data
            volume_data = None
            if cached_data and 'volume' in cached_data:
                volume_data = cached_data['volume']
            else:
                try:
                    volume_data = analyze_volume_tool(ticker, period="3mo")
                except Exception as e:
                    result["warnings"].append(f"Volume analysis failed: {e}")

            if isinstance(volume_data, dict):
                cvd_assessment = volume_data.get("cvd_analysis", {}).get("assessment", "")
                if "BULLISH" in cvd_assessment.upper():
                    direction_votes["cvd"] = "BULLISH"
                elif "BEARISH" in cvd_assessment.upper():
                    direction_votes["cvd"] = "BEARISH"

                # NEW: Dollar Flow as PRIMARY signal (80% accurate in backtest)
                # Dollar Flow follows the money - most reliable indicator
                dalio_metrics = volume_data.get("dalio_metrics", {})
                cdf_20d = dalio_metrics.get("cumulative_dollar_flow", {}).get("20d", 0)
                # Threshold: $10M to avoid noise
                if cdf_20d > 10_000_000:
                    direction_votes["dollar_flow"] = "BULLISH"
                elif cdf_20d < -10_000_000:
                    direction_votes["dollar_flow"] = "BEARISH"
                # else stays NEUTRAL

            # Get RS Score (MOST IMPORTANT long-term indicator - 40% weight)
            relative_strength = None
            if cached_data and 'relative_strength' in cached_data:
                relative_strength = cached_data['relative_strength']
            else:
                try:
                    relative_strength = calculate_relative_strength_tool(ticker=ticker, benchmark="SPY", period="3mo")
                except Exception as e:
                    result["warnings"].append(f"RS Score analysis failed: {e}")
                    direction_votes["rs_score"] = "NEUTRAL"

            if relative_strength and relative_strength.get("rs_score") is not None:
                rs_score = relative_strength["rs_score"]

                # Strong thresholds - RS Score is critical for direction
                if rs_score >= 80:  # Market leader
                    direction_votes["rs_score"] = "LONG"
                elif rs_score >= 60:  # Above average strength
                    direction_votes["rs_score"] = "LONG"
                elif rs_score <= 20:  # Market laggard
                    direction_votes["rs_score"] = "SHORT"
                elif rs_score <= 40:  # Below average strength
                    direction_votes["rs_score"] = "SHORT"
                # else stays NEUTRAL (41-59 range is neutral)

            # Get P/C Contrarian vote (from options analysis)
            options_analysis = None
            if cached_data and 'options' in cached_data:
                options_analysis = cached_data['options']
            else:
                try:
                    # Check if ticker has options
                    t_temp = yf.Ticker(ticker)
                    has_options = len(t_temp.options) > 0 if hasattr(t_temp, 'options') else False

                    if has_options:
                        options_analysis = analyze_options_mcmillan(ticker)
                except Exception as e:
                    result["warnings"].append(f"P/C contrarian analysis failed: {e}")

            if options_analysis and "put_call_ratio" in options_analysis:
                pc_data = options_analysis["put_call_ratio"]
                volume_pc = pc_data.get("volume_pc_ratio")

                if volume_pc is not None:
                    # Contrarian interpretation (opposite of market sentiment)
                    if volume_pc < 0.5:  # Extreme call buying = greed
                        direction_votes["pc_contrarian"] = "SHORT"  # Contrarian bearish
                    elif volume_pc > 1.5:  # Extreme put buying = fear
                        direction_votes["pc_contrarian"] = "LONG"   # Contrarian bullish
                    # else stays NEUTRAL

            # Get Institutional Flow vote
            institutional = None
            if cached_data and 'institutional' in cached_data:
                institutional = cached_data['institutional']
            else:
                try:
                    institutional = get_institutional_holders(ticker=ticker)
                except Exception as e:
                    result["warnings"].append(f"Institutional flow analysis failed: {e}")

            if institutional and "holders" in institutional:
                holders = institutional["holders"]

                # Count accumulation vs distribution among top holders
                accumulating = 0
                distributing = 0

                for holder in holders[:10]:  # Top 10 institutions
                    change_pct = holder.get("pct_change", 0)
                    if change_pct > 10:  # Meaningful accumulation (>10% increase)
                        accumulating += 1
                    elif change_pct < -10:  # Meaningful distribution (>10% decrease)
                        distributing += 1

                # Require strong imbalance (2:1 ratio)
                if accumulating > distributing * 2:
                    direction_votes["institutional"] = "LONG"
                elif distributing > accumulating * 2:
                    direction_votes["institutional"] = "SHORT"
                # else stays NEUTRAL

            # Get F-Score vote (quality indicator)
            quality_analysis = None
            if cached_data and 'quality' in cached_data:
                quality_analysis = cached_data['quality']
            else:
                try:
                    quality_analysis = calculate_quality_score(ticker=ticker)
                except Exception as e:
                    result["warnings"].append(f"F-Score analysis failed: {e}")

            if quality_analysis and "f_score" in quality_analysis:
                f_score = quality_analysis.get("f_score")

                if f_score is not None:
                    if f_score >= 7:  # High quality (strong fundamentals)
                        direction_votes["f_score"] = "LONG"
                    elif f_score <= 3:  # Low quality (weak fundamentals)
                        direction_votes["f_score"] = "SHORT"
                    # else stays NEUTRAL (4-6 range)

            # Get exhaustion data (now returns fresh_direction)
            exhaustion_data = None
            if cached_data and 'exhaustion' in cached_data:
                exhaustion_data = cached_data['exhaustion']
            else:
                try:
                    from ..technical_analysis_bootstrap import calculate_exhaustion_score
                    exhaustion_data = calculate_exhaustion_score(ticker, period="3mo")  # No direction!
                except Exception as e:
                    result["warnings"].append(f"Exhaustion check failed: {e}")

            if exhaustion_data:
                fresh_dir = exhaustion_data.get("fresh_direction", "NEUTRAL")
                direction_votes["exhaustion"] = fresh_dir

            # Get Brooks Always-In direction
            ohlcv = None
            technical_data = None
            brooks_always_in = "NEUTRAL"

            # Check cache for OHLCV and technical data
            if cached_data and 'ohlcv' in cached_data and 'technical' in cached_data:
                ohlcv = cached_data['ohlcv']
                technical_data = cached_data['technical']
            else:
                try:
                    ohlcv = _get_ohlcv_cached(ticker, period="3mo")
                    technical_data = analyze_technical(ticker, period="3mo", include_ml_analysis=False, include_trend_score=False)
                except Exception as e:
                    result["warnings"].append(f"Failed to fetch technical data: {e}")

            if ohlcv is not None and technical_data is not None:
                try:
                    from ..scanner_analyzer import AlBrooksAnalyzer
                    # Get Always-In direction independently (not for a specific trade)
                    brooks_analyzer = AlBrooksAnalyzer()
                    # Call with a neutral analysis first to get Always-In
                    temp_brooks = brooks_analyzer.analyze(
                        ticker=ticker,
                        direction="long",  # Doesn't matter - we just want always_in
                        ohlcv_data=ohlcv,
                        technical_data=technical_data or {}
                    )
                    if isinstance(temp_brooks, dict):
                        brooks_always_in = temp_brooks.get("always_in", "NEUTRAL")
                        direction_votes["brooks"] = brooks_always_in
                except Exception as e:
                    result["warnings"].append(f"Brooks analysis failed: {e}")

            # ========== STEP 2: WEIGHTED VOTING SYSTEM (v2) ==========
            # Long-term indicators (40%): RS Score (most important)
            # Short-term indicators (30%): Brooks, CVD, Dollar Flow
            # Catalyst indicators (20%): Catalyst, F-Score
            # Contrarian indicators (10%): P/C Ratio, Institutional

            vote_weights = {
                # Long-term (40% total)
                "rs_score": 40,           # Most important - long-term market position

                # Short-term (30% total)
                "brooks": 10,             # Al Brooks price action probability
                "cvd": 10,                # Cumulative volume delta
                "dollar_flow": 10,        # Smart money flow

                # Catalyst (20% total)
                "catalyst": 15,           # Combined catalyst score
                "f_score": 5,             # Quality/earnings quality

                # Contrarian (10% total)
                "pc_contrarian": 5,       # Put/Call contrarian signal
                "institutional": 5,       # Institutional accumulation/distribution

                # Legacy (keep for backward compatibility)
                "exhaustion": 0,          # Deprecated - now captured in CVD
            }

            long_score = 0
            short_score = 0
            neutral_score = 0

            for tool, vote in direction_votes.items():
                weight = vote_weights.get(tool, 0)

                if vote in ["BULLISH", "LONG"]:
                    long_score += weight
                elif vote in ["BEARISH", "SHORT"]:
                    short_score += weight
                else:
                    neutral_score += weight

            total_votes = long_score + short_score + neutral_score
            long_pct = (long_score / total_votes * 100) if total_votes > 0 else 0
            short_pct = (short_score / total_votes * 100) if total_votes > 0 else 0

            # Determine direction with 60% threshold
            if long_pct >= 60:
                data_direction = "LONG"
            elif short_pct >= 60:
                data_direction = "SHORT"
            else:
                data_direction = "NO_CONSENSUS"

            # Store voting breakdown for transparency
            voting_breakdown = {
                "long_score": long_score,
                "short_score": short_score,
                "neutral_score": neutral_score,
                "long_pct": round(long_pct, 1),
                "short_pct": round(short_pct, 1),
                "weights_used": {k: v for k, v in vote_weights.items() if k in direction_votes}
            }

            result["data_direction"] = data_direction
            result["direction_votes"] = direction_votes
            result["voting_breakdown"] = voting_breakdown  # NEW: Transparency

            # ========== STEP 3: DETERMINE ACTUAL DIRECTION TO USE ==========
            # CRITICAL: Always run all 5 gates - never exit early
            # The 5-gate system must independently validate and show pass/fail for each gate
            # TradingView uses technicals, so we use Brooks (price action) as primary direction

            if direction is not None:
                # User/scanner specified direction
                actual_direction = direction
                if data_direction != "NO_CONSENSUS" and direction != data_direction:
                    result["warnings"].append(
                        f"DIRECTION CONFLICT: Requested {direction} but votes suggest {data_direction}. "
                        f"Votes: {direction_votes}"
                    )
            else:
                # No direction specified - determine from votes
                if data_direction != "NO_CONSENSUS":
                    actual_direction = data_direction
                else:
                    # NO_CONSENSUS: Use Brooks (technical/price action) as primary
                    # This aligns with TradingView which also uses technicals
                    brooks_vote = direction_votes.get("brooks", "NEUTRAL")
                    if brooks_vote == "SHORT":
                        actual_direction = "SHORT"
                    elif brooks_vote == "LONG":
                        actual_direction = "LONG"
                    else:
                        # Brooks neutral - use catalyst as secondary
                        catalyst_vote = direction_votes.get("catalyst", "NEUTRAL")
                        if catalyst_vote == "BEARISH":
                            actual_direction = "SHORT"
                        elif catalyst_vote == "BULLISH":
                            actual_direction = "LONG"
                        else:
                            # NO TRADE when all indicators neutral - don't force direction
                            actual_direction = None
                            result["signal"] = "NO_TRADE"
                            result["warnings"].append(
                                "NO_TRADE: All indicators neutral (Brooks=NEUTRAL, Catalyst=NEUTRAL). No clear direction signal."
                            )

                    if actual_direction is not None:
                        result["warnings"].append(
                            f"NO_CONSENSUS: {direction_votes}. Using Brooks ({brooks_vote}) -> {actual_direction}"
                        )

            # ========== TIMEFRAME CONFLICT DETECTION ==========
            timeframe_conflicts = []

            # Long-term vs Short-term conflict
            long_term_votes = ["rs_score", "f_score", "institutional"]
            short_term_votes = ["brooks", "cvd", "dollar_flow"]

            long_term_long = sum(1 for v in long_term_votes if direction_votes.get(v) == "LONG")
            long_term_short = sum(1 for v in long_term_votes if direction_votes.get(v) == "SHORT")
            short_term_long = sum(1 for v in short_term_votes if direction_votes.get(v) == "LONG")
            short_term_short = sum(1 for v in short_term_votes if direction_votes.get(v) == "SHORT")

            if long_term_long > long_term_short and short_term_short > short_term_long:
                conflict_msg = "⚠️ TIMEFRAME CONFLICT: Long-term bullish but short-term bearish - may be pullback in uptrend"
                timeframe_conflicts.append(conflict_msg)
            elif long_term_short > long_term_long and short_term_long > short_term_short:
                conflict_msg = "⚠️ TIMEFRAME CONFLICT: Long-term bearish but short-term bullish - may be bounce in downtrend"
                timeframe_conflicts.append(conflict_msg)

            # Add conflicts to warnings
            if timeframe_conflicts:
                result["warnings"].extend(timeframe_conflicts)

            # ========== HARD OVERRIDE RULES ==========
            # These override ALL other votes to prevent dangerous trades
            override_reason = None

            # Rule 1: NEVER SHORT MARKET LEADERS (RS ≥ 80)
            if relative_strength and relative_strength.get("rs_score", 0) >= 80:
                if actual_direction in ["SHORT", "BEARISH"]:
                    override_reason = f"⚠️ OVERRIDE: RS Score {relative_strength['rs_score']} (market leader) - changed SHORT to LONG"
                    actual_direction = "LONG"

            # Rule 2: NEVER LONG MARKET LAGGARDS (RS ≤ 20)
            elif relative_strength and relative_strength.get("rs_score", 100) <= 20:
                if actual_direction in ["LONG", "BULLISH"]:
                    override_reason = f"⚠️ OVERRIDE: RS Score {relative_strength['rs_score']} (market laggard) - changed LONG to SHORT"
                    actual_direction = "SHORT"

            # Add override to warnings and summary
            if override_reason:
                result["warnings"].append(override_reason)

            result["direction"] = actual_direction

            # Early return if NO_TRADE (all indicators neutral)
            if actual_direction is None:
                result["confidence"] = 0
                result["gates_passed"] = 0
                result["recommendation"] = "NO_TRADE: All indicators neutral. Wait for clearer signal."
                return result

            # ========== GATE 1: CATALYST CHECK (direction-aware now) ==========
            try:
                if catalyst_data is None:
                    catalyst_data = detect_catalyst_strength(ticker)

                result["catalyst_analysis"] = {
                    "strength": catalyst_data.get("catalyst_strength"),
                    "score": catalyst_data.get("catalyst_score"),
                    "direction": catalyst_data.get("catalyst_direction"),
                    "bullish_score": catalyst_data.get("bullish_score"),
                    "bearish_score": catalyst_data.get("bearish_score"),
                    "catalysts": catalyst_data.get("catalysts_detected", []),
                    "trade_allowed": catalyst_data.get("trade_allowed")
                }

                # Check if catalyst direction aligns with actual_direction
                cat_dir = catalyst_data.get("catalyst_direction", "NEUTRAL")
                direction_aligned = (
                    (actual_direction == "LONG" and cat_dir in ["BULLISH", "NEUTRAL"]) or
                    (actual_direction == "SHORT" and cat_dir in ["BEARISH", "NEUTRAL"])
                )

                # NEW: Strong catalyst conflict = BLOCK TRADE (not just fail gate)
                # This fixed CRNX which went SHORT despite BULLISH catalyst -> -16% loss
                catalyst_conflict = (
                    (actual_direction == "LONG" and cat_dir == "BEARISH") or
                    (actual_direction == "SHORT" and cat_dir == "BULLISH")
                )

                if catalyst_data.get("trade_allowed") and direction_aligned:
                    result["gate_status"]["catalyst"] = "PASS"
                    score += 25 if catalyst_data.get("catalyst_strength") == "STRONG" else 15
                elif catalyst_conflict:
                    # CRITICAL FIX: Block trade entirely when catalyst strongly contradicts
                    result["gate_status"]["catalyst"] = "BLOCKED"
                    result["signal"] = "NO_TRADE"
                    result["warnings"].append(
                        f"BLOCKED: Catalyst ({cat_dir}) strongly opposes trade direction ({actual_direction}). "
                        f"Trading against catalyst has 30% win rate."
                    )
                    result["confidence"] = 0
                    result["gates_passed"] = 0
                    result["recommendation"] = f"NO_TRADE: Catalyst direction ({cat_dir}) conflicts with {actual_direction}. Wait for alignment."
                    return result
                elif catalyst_data.get("trade_allowed") and not direction_aligned:
                    result["gate_status"]["catalyst"] = "FAIL"
                    result["warnings"].append(f"Catalyst direction ({cat_dir}) conflicts with trade direction ({actual_direction})")
                else:
                    result["gate_status"]["catalyst"] = "FAIL"
                    result["warnings"].append("No catalyst present - trade not recommended")

            except Exception as e:
                result["gate_status"]["catalyst"] = "ERROR"
                result["warnings"].append(f"Catalyst check failed: {e}")

            # ========== GATE 2: FRESHNESS CHECK (Enhanced with Dalio Economic Machine) ==========
            # Now includes 6 checks: CVD, Exhaustion, Fresh Direction + 3 Dalio metrics
            # Requires 5/6 checks to PASS
            try:
                if exhaustion_data is None:
                    from ..technical_analysis_bootstrap import calculate_exhaustion_score
                    exhaustion_data = calculate_exhaustion_score(ticker, period="3mo")

                # Get exhaustion for actual direction
                if actual_direction == "LONG":
                    exhaustion = exhaustion_data.get("long_exhaustion", {}).get("score", 50)
                    exhaustion_level = exhaustion_data.get("long_exhaustion", {}).get("level", "UNKNOWN")
                else:
                    exhaustion = exhaustion_data.get("short_exhaustion", {}).get("score", 50)
                    exhaustion_level = exhaustion_data.get("short_exhaustion", {}).get("level", "UNKNOWN")

                cvd_trend = "FLAT"
                if volume_data and isinstance(volume_data, dict):
                    cvd_trend = volume_data.get("cvd_analysis", {}).get("cvd_trend", "FLAT")

                # ========== NEW: Extract Dalio Metrics ==========
                dalio_metrics = {}
                if volume_data and isinstance(volume_data, dict):
                    dalio_metrics = volume_data.get("dalio_metrics", {})

                dalio_ratio = dalio_metrics.get("dalio_ratio", {}).get("20d_avg", 1.0)
                cdf_20d = dalio_metrics.get("cumulative_dollar_flow", {}).get("20d", 0)
                sustainability_score = dalio_metrics.get("trend_sustainability", {}).get("score", 50)
                dv_momentum = dalio_metrics.get("dollar_volume", {}).get("momentum", "NEUTRAL")

                result["freshness_analysis"] = {
                    "cvd_trend": cvd_trend,
                    "fresh_direction": exhaustion_data.get("fresh_direction", "NEUTRAL"),
                    "long_exhaustion": exhaustion_data.get("long_exhaustion", {}).get("score", 0),
                    "short_exhaustion": exhaustion_data.get("short_exhaustion", {}).get("score", 0),
                    "exhaustion_score": exhaustion,
                    "exhaustion_level": exhaustion_level,
                    # NEW: Dalio metrics in freshness analysis
                    "dalio_ratio": round(dalio_ratio, 4),
                    "dalio_interpretation": dalio_metrics.get("dalio_ratio", {}).get("interpretation", "UNKNOWN"),
                    "cumulative_dollar_flow_20d": cdf_20d,
                    "dollar_flow_direction": dalio_metrics.get("cumulative_dollar_flow", {}).get("direction", "UNKNOWN"),
                    "sustainability_score": sustainability_score,
                    "sustainability_grade": dalio_metrics.get("trend_sustainability", {}).get("grade", "?"),
                    "dollar_volume_momentum": dv_momentum
                }

                # ========== 6 FRESHNESS CHECKS ==========
                # Original 3 checks
                # Check 1: CVD alignment
                cvd_aligned = (actual_direction == "LONG" and cvd_trend in ["RISING", "FLAT"]) or \
                              (actual_direction == "SHORT" and cvd_trend in ["FALLING", "FLAT"])

                # Check 2: Exhaustion < 50
                not_exhausted = exhaustion < 50

                # Check 3: Fresh direction
                is_fresh_direction = exhaustion_data.get("fresh_direction") == actual_direction

                # NEW: Dalio checks (3 additional)
                # Check 4: Dalio Ratio aligned
                dalio_ratio_aligned = (actual_direction == "LONG" and dalio_ratio >= 1.0) or \
                                      (actual_direction == "SHORT" and dalio_ratio <= 1.0)

                # Check 5: Dollar Flow aligned
                dollar_flow_aligned = (actual_direction == "LONG" and cdf_20d > 0) or \
                                      (actual_direction == "SHORT" and cdf_20d < 0)

                # Check 6: Sustainability OK
                sustainability_ok = sustainability_score >= 50

                # Count passed checks
                checks = {
                    "cvd_aligned": cvd_aligned,
                    "not_exhausted": not_exhausted,
                    "fresh_direction": is_fresh_direction,
                    "dalio_ratio_aligned": dalio_ratio_aligned,
                    "dollar_flow_aligned": dollar_flow_aligned,
                    "sustainability_ok": sustainability_ok
                }
                checks_passed = sum(checks.values())

                # Store check details in result
                result["freshness_analysis"]["checks"] = checks
                result["freshness_analysis"]["checks_passed"] = checks_passed
                result["freshness_analysis"]["checks_total"] = 6

                # Gate 2 passes if 5/6 checks pass (allows 1 failure)
                if checks_passed >= 5:
                    result["gate_status"]["freshness"] = "PASS"
                    score += 20
                elif checks_passed >= 4:
                    result["gate_status"]["freshness"] = "PASS"
                    score += 15  # Marginal pass with 4/6
                else:
                    result["gate_status"]["freshness"] = "FAIL"
                    # Add specific warnings for failed checks
                    if not cvd_aligned:
                        result["warnings"].append(f"CVD not aligned: {cvd_trend}")
                    if not not_exhausted:
                        result["warnings"].append(f"High exhaustion for {actual_direction}: {exhaustion}")
                    if not dalio_ratio_aligned:
                        result["warnings"].append(f"Dalio ratio not aligned: {dalio_ratio:.4f} (need {'≥1.0' if actual_direction == 'LONG' else '≤1.0'})")
                    if not dollar_flow_aligned:
                        flow_dir = "positive" if actual_direction == "LONG" else "negative"
                        result["warnings"].append(f"Dollar flow not aligned: ${cdf_20d:,.0f} (need {flow_dir})")
                    if not sustainability_ok:
                        result["warnings"].append(f"Low sustainability score: {sustainability_score}/100")

                # ========== DALIO ECONOMIC MACHINE SUMMARY ==========
                # Dedicated section for Ray Dalio's principle: Price = Total Spending / Quantity Sold
                institutional_activity = dalio_metrics.get("institutional_activity", {})
                spending_efficiency = dalio_metrics.get("spending_efficiency", {})

                # CRITICAL FIX: Dalio verdict MUST require Dollar Flow alignment
                # This fixed FSLR which showed BULLISH Dalio with -$549M distribution -> -10% loss
                # Dollar Flow is the PRIMARY indicator - cannot override it
                dalio_verdict = "NEUTRAL"
                if not dollar_flow_aligned:
                    # Dollar flow disagrees - CANNOT be bullish/bearish regardless of other metrics
                    dalio_verdict = "CONFLICTED"
                    result["warnings"].append(
                        f"DALIO CONFLICT: Direction {actual_direction} but Dollar Flow ${cdf_20d:,.0f} "
                        f"({('negative' if cdf_20d < 0 else 'positive')}) contradicts. Follow the money."
                    )
                elif checks_passed >= 5 and sustainability_score >= 70 and dollar_flow_aligned:
                    dalio_verdict = "STRONG_BULLISH" if actual_direction == "LONG" else "STRONG_BEARISH"
                elif checks_passed >= 4 and sustainability_score >= 50 and dollar_flow_aligned:
                    dalio_verdict = "BULLISH" if actual_direction == "LONG" else "BEARISH"
                elif checks_passed <= 2:
                    dalio_verdict = "WEAK"

                result["dalio_economic_machine"] = {
                    "principle": "Price = Total Spending / Quantity Sold (Ray Dalio)",
                    "verdict": dalio_verdict,
                    "key_metrics": {
                        "dalio_ratio": {
                            "value": round(dalio_ratio, 4),
                            "interpretation": dalio_metrics.get("dalio_ratio", {}).get("interpretation", "UNKNOWN"),
                            "aligned_for_trade": dalio_ratio_aligned
                        },
                        "cumulative_dollar_flow": {
                            "20d_value": cdf_20d,
                            "20d_formatted": f"${cdf_20d:,.0f}" if abs(cdf_20d) >= 1000 else f"${cdf_20d:.2f}",
                            "direction": dalio_metrics.get("cumulative_dollar_flow", {}).get("direction", "UNKNOWN"),
                            "aligned_for_trade": dollar_flow_aligned
                        },
                        "trend_sustainability": {
                            "score": sustainability_score,
                            "grade": dalio_metrics.get("trend_sustainability", {}).get("grade", "?"),
                            "description": dalio_metrics.get("trend_sustainability", {}).get("description", "Unknown"),
                            "is_sustainable": sustainability_ok
                        },
                        "dollar_volume_momentum": {
                            "classification": dv_momentum,
                            "percentage": dalio_metrics.get("dollar_volume", {}).get("dv_momentum_pct", 0)
                        },
                        "institutional_activity": {
                            "detected": institutional_activity.get("detected", False),
                            "type": institutional_activity.get("type", "NONE"),
                            "confidence": institutional_activity.get("confidence", 0),
                            "signals": institutional_activity.get("signals", [])
                        },
                        "spending_efficiency": {
                            "ratio": spending_efficiency.get("ratio", 1.0),
                            "interpretation": spending_efficiency.get("interpretation", "UNKNOWN"),
                            "implication": spending_efficiency.get("implication", "Unknown")
                        }
                    },
                    "gate_2_contribution": {
                        "checks_passed": checks_passed,
                        "checks_total": 6,
                        "dalio_checks_passed": sum([dalio_ratio_aligned, dollar_flow_aligned, sustainability_ok]),
                        "dalio_checks_total": 3
                    },
                    "trade_recommendation": {
                        "direction_supported": checks_passed >= 4,
                        "confidence_level": "HIGH" if checks_passed >= 5 else ("MODERATE" if checks_passed >= 4 else "LOW"),
                        "key_insight": f"Dalio Ratio {dalio_ratio:.4f} with ${cdf_20d:,.0f} dollar flow suggests {'accumulation' if cdf_20d > 0 else 'distribution'}"
                    }
                }

            except Exception as e:
                result["gate_status"]["freshness"] = "ERROR"
                result["warnings"].append(f"Freshness check failed: {e}")

            # ========== DOLLAR FLOW BLOCK CHECK (after Gate 2) ==========
            # CRITICAL: Block trades with large opposing Dollar Flow (> $500M)
            # This fixed FSLR which lost -10% trading LONG against -$1.6B distribution
            try:
                if 'cdf_20d' in locals():
                    df_threshold = 500_000_000  # $500M threshold for blocking
                    if actual_direction == "LONG" and cdf_20d < -df_threshold:
                        result["signal"] = "NO_TRADE"
                        result["warnings"].append(
                            f"BLOCKED: Massive distribution ${cdf_20d:,.0f} opposes LONG. "
                            f"Institutions are selling. Follow the money!"
                        )
                        result["confidence"] = 0
                        result["gates_passed"] = sum(1 for g in result["gate_status"].values() if g == "PASS")
                        result["recommendation"] = f"NO_TRADE: ${abs(cdf_20d):,.0f} flowing OUT while trying to go LONG."
                        return result
                    elif actual_direction == "SHORT" and cdf_20d > df_threshold:
                        result["signal"] = "NO_TRADE"
                        result["warnings"].append(
                            f"BLOCKED: Massive accumulation ${cdf_20d:,.0f} opposes SHORT. "
                            f"Institutions are buying. Follow the money!"
                        )
                        result["confidence"] = 0
                        result["gates_passed"] = sum(1 for g in result["gate_status"].values() if g == "PASS")
                        result["recommendation"] = f"NO_TRADE: ${cdf_20d:,.0f} flowing IN while trying to go SHORT."
                        return result
            except Exception:
                pass  # Continue if cdf_20d not available

            # ========== GATE 3: AL BROOKS ANALYSIS ==========
            try:
                if ohlcv is None:
                    ohlcv = _get_ohlcv_cached(ticker, period="3mo")
                if technical_data is None:
                    technical_data = analyze_technical(ticker, period="3mo", include_ml_analysis=False, include_trend_score=False)

                from ..scanner_analyzer import AlBrooksAnalyzer
                brooks_analyzer = AlBrooksAnalyzer()
                brooks = brooks_analyzer.analyze(
                    ticker=ticker,
                    direction=actual_direction.lower(),
                    ohlcv_data=ohlcv,
                    technical_data=technical_data or {}
                )

                if isinstance(brooks, dict):
                    always_in = brooks.get("always_in", "NEUTRAL")
                    trap_risk = brooks.get("trap_risk", "MEDIUM")
                    probability = brooks.get("adjusted_probability", brooks.get("base_probability", 50))
                    pattern = brooks.get("pattern", "Unknown")

                    result["brooks_analysis"] = {
                        "always_in": always_in,
                        "trap_risk": trap_risk,
                        "probability": probability,
                        "pattern": pattern
                    }

                    # Check Al Brooks gates
                    direction_ok = (actual_direction == "LONG" and always_in in ["LONG", "NEUTRAL"]) or \
                                   (actual_direction == "SHORT" and always_in in ["SHORT", "NEUTRAL"])
                    trap_ok = trap_risk != "HIGH"
                    prob_ok = probability >= 55

                    if direction_ok and trap_ok and prob_ok:
                        result["gate_status"]["brooks"] = "PASS"
                        score += 25
                    else:
                        result["gate_status"]["brooks"] = "FAIL"
                        if not direction_ok:
                            result["warnings"].append(f"Always-In is {always_in}, not aligned with {actual_direction}")
                        if not trap_ok:
                            result["warnings"].append("HIGH trap risk detected")
                        if not prob_ok:
                            result["warnings"].append(f"Low probability: {probability}%")

            except Exception as e:
                result["gate_status"]["brooks"] = "ERROR"
                result["warnings"].append(f"Brooks analysis failed: {e}")

            # ========== GATE 4: QUALITY CHECK (direction-aware) ==========
            # LONG: Want HIGH quality (score >= 50, no major red flags)
            # SHORT: Want LOW quality / defects (score <= 40 OR red_flags OR distressed)
            try:
                # Use cached quality_analysis if available
                quality_data = quality_analysis if quality_analysis else calculate_quality_score(ticker)

                if isinstance(quality_data, dict):
                    quality_score = quality_data.get("quality_score", 0)
                    quality_grade = quality_data.get("quality_grade", "N/A")
                    red_flags = quality_data.get("red_flags", [])

                    # Extract f_score and z_score from components
                    components = quality_data.get("components", {})

                    result["quality_analysis"] = {
                        "score": quality_score,
                        "grade": quality_grade,
                        "red_flags": red_flags,
                        "f_score": components.get("f_score"),
                        "z_score": components.get("z_score")
                    }

                    if actual_direction == "LONG":
                        # LONG: High quality = PASS
                        if quality_score >= 50:
                            result["gate_status"]["quality"] = "PASS"
                            score += 15
                        else:
                            result["gate_status"]["quality"] = "FAIL"
                            result["warnings"].append(f"Low quality for LONG: {quality_score}")
                    else:
                        # SHORT: Low quality OR red flags = PASS (want weak companies)
                        has_defects = len(red_flags) >= 1
                        is_weak = quality_score <= 40
                        is_distressed = quality_grade in ["D", "F"]

                        if is_weak or has_defects or is_distressed:
                            result["gate_status"]["quality"] = "PASS"
                            score += 15
                            if has_defects:
                                result["quality_analysis"]["short_reason"] = f"Red flags: {red_flags}"
                            elif is_weak:
                                result["quality_analysis"]["short_reason"] = f"Weak fundamentals: {quality_score}"
                            else:
                                result["quality_analysis"]["short_reason"] = f"Distressed: {quality_grade}"
                        else:
                            result["gate_status"]["quality"] = "FAIL"
                            result["warnings"].append(f"Too strong for SHORT: score {quality_score}, grade {quality_grade}, no defects")

            except Exception as e:
                result["gate_status"]["quality"] = "ERROR"

            # ========== GATE 5: OPTIONS TRADABILITY (NEW) ==========
            # Determines if options are suitable vs stock
            # Validates: liquidity, IV environment, earnings proximity, expected moves
            gate_5_result = None
            try:
                from ..gates.options_tradability_gate import validate_options_tradability
                from ..options.decision_framework import should_use_options

                # Get options data for Gate 5 validation
                # Use cached options_analysis if available
                options_data = options_analysis if options_analysis else None
                iv_skew_data = None
                term_structure_data = None

                if options_data is None:
                    try:
                        # Use existing analyze_options_mcmillan (already has liquidity + IV)
                        options_data = analyze_options_mcmillan(ticker, holding_period_days=45)
                    except Exception as e:
                        logger.debug(f"Options data fetch failed: {e}")

                try:
                    # Get IV skew for strategy selection
                    iv_skew_data = analyze_iv_skew(ticker, holding_period_days=45)
                except Exception as e:
                    logger.debug(f"IV skew fetch failed: {e}")

                try:
                    # Get term structure for calendar spread signals
                    term_structure_data = analyze_iv_term_structure(ticker)
                except Exception as e:
                    logger.debug(f"Term structure fetch failed: {e}")

                # Run Gate 5 validation
                if options_data:
                    gate_5_result = validate_options_tradability(
                        ticker=ticker,
                        direction=actual_direction,
                        current_price=current_price,
                        options_data=options_data,
                        iv_skew_data=iv_skew_data,
                        term_structure=term_structure_data,
                        earnings_days=catalyst_data.get("days_to_earnings") if catalyst_data else None,
                        account_size=account_size
                    )

                    # Store Gate 5 result for later use
                    result["gate_5_analysis"] = gate_5_result

                    # Check Gate 5 pass/fail
                    if gate_5_result.get("gate_status") == "PASS":
                        result["gate_status"]["options_tradability"] = "PASS"
                        score += 20  # Gate 5 weight
                    else:
                        result["gate_status"]["options_tradability"] = "FAIL"
                        result["warnings"].append(
                            f"Options Gate 5 failed: {gate_5_result.get('skip_reason', 'Unknown')}"
                        )
                else:
                    result["gate_status"]["options_tradability"] = "SKIP"
                    result["warnings"].append("Gate 5 skipped: Options data unavailable")

            except Exception as e:
                result["gate_status"]["options_tradability"] = "ERROR"
                result["warnings"].append(f"Gate 5 (Options Tradability) error: {e}")
                logger.error(f"Gate 5 error for {ticker}: {e}", exc_info=True)

            # ========== PROOF OF VALIDITY ==========
            try:
                similar = find_similar_historical_setups(
                    ticker=ticker,
                    direction=actual_direction,
                    target_return_pct=5.0,
                    holding_period_days=10
                )

                if isinstance(similar, dict):
                    if 'error' in similar:
                        result["proof_of_validity"] = {
                            "similar_setups": 0,
                            "success_rate": 0,
                            "confidence": "N/A",
                            "avg_return": 0,
                            "error": similar.get("error")
                        }
                    else:
                        setups_found = similar.get("similar_setups_found", 0)
                        success_rate = similar.get("success_rate_5d", 0)

                        result["proof_of_validity"] = {
                            "similar_setups": setups_found,
                            "success_rate": success_rate,
                            "confidence": similar.get("statistical_confidence", "N/A"),
                            "avg_return": similar.get("average_return_5d", 0)
                        }

                        if setups_found >= 10 and success_rate >= 55:
                            score += 15
                else:
                    result["proof_of_validity"] = {
                        "similar_setups": 0,
                        "success_rate": 0,
                        "confidence": "N/A",
                        "avg_return": 0,
                        "note": "Historical analysis unavailable"
                    }

            except Exception as e:
                result["proof_of_validity"] = {
                    "similar_setups": 0,
                    "success_rate": 0,
                    "confidence": "N/A",
                    "avg_return": 0,
                    "error": str(e)
                }

            # ========== GENERATE TRADING PLAN (Research-Backed) ==========
            try:
                # === PHASE 2: Calculate optimized technical indicators ===
                macd_data = calculate_optimized_macd(ticker)
                adx_data = calculate_adx(ticker)
                economic_context = get_economic_context()

                # Calculate volume ratio (current volume vs 20-day average)
                try:
                    stock_data = yf.Ticker(ticker)
                    hist = stock_data.history(period='30d')
                    if len(hist) > 20:
                        current_volume = hist['Volume'].iloc[-1]
                        avg_volume_20 = hist['Volume'].iloc[-20:].mean()
                        volume_ratio = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0
                    else:
                        volume_ratio = 1.0
                except:
                    volume_ratio = 1.0

                # Extract fundamental data from ticker
                # Sector PE medians (S&P 500 historical medians, updated periodically)
                SECTOR_PE_MEDIANS = {
                    'Technology': 32,
                    'Communication Services': 22,
                    'Consumer Cyclical': 25,
                    'Consumer Defensive': 23,
                    'Financial Services': 15,
                    'Healthcare': 28,
                    'Industrials': 22,
                    'Energy': 12,
                    'Utilities': 18,
                    'Real Estate': 35,
                    'Basic Materials': 16,
                }

                try:
                    info = stock_data.info if 'stock_data' in locals() else yf.Ticker(ticker).info
                    sector = info.get('sector', 'Unknown')
                    pe_ratio = info.get('trailingPE') or info.get('forwardPE')
                    sector_pe_median = SECTOR_PE_MEDIANS.get(sector, 20)

                    # Revenue growth (if available)
                    revenue_growth = 0  # Placeholder - would need financial statements

                    # Free cash flow
                    fcf = info.get('freeCashflow', 0)
                except:
                    sector = 'Unknown'
                    pe_ratio = None
                    sector_pe_median = 20
                    revenue_growth = 0
                    fcf = 0

                # === ENTRY STRATEGY ===
                # Call new entry_exit_strategy module with research-backed methods
                entry_data = determine_entry_strategy(
                    ticker=ticker,
                    current_price=current_price,
                    actual_direction=actual_direction,
                    technical_data={
                        'macd': macd_data if 'error' not in macd_data else {},
                        'adx': adx_data if 'error' not in adx_data else {},
                        'volume_ratio': volume_ratio
                    },
                    fundamental_data={
                        'sector': sector,
                        'pe_ratio': pe_ratio,
                        'sector_pe_median': sector_pe_median,
                        'revenue_growth_yoy': revenue_growth,
                        'free_cash_flow': fcf
                    },
                    economic_context=economic_context
                )

                entry_price = entry_data['entry_price']
                entry_strategy = entry_data['entry_strategy']
                entry_rationale = entry_data['entry_rationale']
                entry_confidence = entry_data['entry_confidence']
                entry_status = entry_data.get('entry_status', 'ACTIONABLE')

                # === CHASE WARNING DETECTION ===
                # Upgrade entry_status to CHASE_WARNING if overbought + no clear entry
                rsi_value = None
                if technical_data and isinstance(technical_data, dict):
                    rsi_raw = technical_data.get('rsi')
                    if isinstance(rsi_raw, dict):
                        rsi_value = rsi_raw.get('value')
                    elif isinstance(rsi_raw, (int, float)):
                        rsi_value = rsi_raw

                exhaustion_val = locals().get('exhaustion', 50)

                if entry_strategy in ("NO_CLEAR_ENTRY", "WAIT_FOR_PULLBACK"):
                    is_overbought = rsi_value is not None and rsi_value > 70
                    is_exhausted = exhaustion_val > 70
                    if is_overbought or is_exhausted:
                        entry_status = "CHASE_WARNING"
                        result["warnings"].append(
                            f"CHASE WARNING: entry_strategy={entry_strategy}, "
                            f"RSI={rsi_value}, exhaustion={exhaustion_val}. "
                            f"Do NOT enter at current price ${current_price:.2f}. "
                            f"Wait for pullback to ${entry_price:.2f}."
                        )

                # === STOP LOSS (ATR-based) ===
                stop_loss_data = calculate_atr_stop_loss(
                    ticker=ticker,
                    entry_price=entry_price,
                    position_type=actual_direction,
                    time_frame='swing',
                    atr_period=14
                )

                # Validate and set stop loss
                if 'error' not in stop_loss_data and stop_loss_data['validation']['recommended']:
                    stop_price = stop_loss_data['stop_price']
                    stop_rationale = (
                        f"ATR-based stop: ${stop_price:.2f} "
                        f"({stop_loss_data['stop_percent']*100:.1f}% risk). "
                        f"{stop_loss_data['atr_multiplier']}x ATR({stop_loss_data['atr_period']}). "
                        f"{stop_loss_data['expected_benefit']}"
                    )
                else:
                    # Fallback to percentage-based stop
                    stop_price = entry_price * (0.95 if actual_direction == 'LONG' else 1.05)
                    stop_rationale = "Using 5% stop (ATR calculation unavailable or out of range)"
                    logger.warning(f"ATR stop fallback for {ticker}: {stop_loss_data.get('error', 'validation failed')}")

                # === PROFIT TARGET (R:R optimized) ===
                target_data = calculate_profit_target(
                    entry_price=entry_price,
                    stop_loss=stop_price,
                    direction=actual_direction,
                    resistances=entry_data['sr_data'].get('resistances', []),
                    supports=entry_data['sr_data'].get('supports', [])
                )

                target_1 = target_data['partial_exits']['1R']
                target_2 = target_data['target_price']

                risk_per_share = abs(entry_price - stop_price)
                risk_reward = target_data['rr_ratio']

                # Position sizing (1% risk, adjusted by confidence)
                base_risk_pct = 0.01  # 1% base risk
                adjusted_risk_pct = base_risk_pct * entry_data['position_size_multiplier']
                risk_amount = account_size * adjusted_risk_pct
                shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0

                result["trading_plan"] = {
                    "entry_price": round(entry_price, 2),
                    "entry_type": "LIMIT",
                    "entry_strategy": entry_strategy,
                    "entry_status": entry_status,
                    "entry_zone": entry_data.get('entry_zone', {}),
                    "entry_rationale": entry_rationale,
                    "current_price": round(current_price, 2),
                    "entry_confidence": round(entry_confidence, 2),
                    "stop_loss": {
                        "price": round(stop_price, 2),
                        "risk_pct": round((abs(entry_price - stop_price) / entry_price) * 100, 2),
                        "rationale": stop_rationale
                    },
                    "target_1": {
                        "price": round(target_1, 2),
                        "reward_pct": round((abs(target_1 - entry_price) / entry_price) * 100, 2),
                        "exit_strategy": "Take 50% profit at 1R"
                    },
                    "target_2": {
                        "price": round(target_2, 2),
                        "reward_pct": round((abs(target_2 - entry_price) / entry_price) * 100, 2),
                        "exit_strategy": "Final target (remaining 50%)"
                    },
                    "risk_reward_ratio": round(risk_reward, 2),
                    "required_win_rate": round(target_data['required_win_rate'] * 100, 1),
                    "position_size": {
                        "shares": shares,
                        "dollar_risk": round(risk_amount, 2),
                        "position_value": round(shares * entry_price, 2),
                        "risk_pct_adjusted": round(adjusted_risk_pct * 100, 2)
                    },
                    "time_frame": "5-15 trading days",
                    "research_backing": entry_data['research_backing'],
                    "multi_factor_scores": entry_data['scores'],
                    "sr_analysis": {
                        "supports_found": entry_data['sr_data']['supports_found'],
                        "resistances_found": entry_data['sr_data']['resistances_found'],
                        "method": entry_data['sr_data']['method']
                    }
                }

            except Exception as e:
                logger.error(f"Trading plan generation failed for {ticker}: {str(e)}")
                result["trading_plan"] = {"error": str(e)}

            # ========== OPTIONS ANALYSIS (McMillan) ==========
            try:
                # Use cached options_analysis if available
                if options_analysis is None and options_data is None:
                    options_data = analyze_options_mcmillan(ticker)
                else:
                    # Reuse already fetched data
                    options_data = options_analysis if options_analysis else options_data

                if isinstance(options_data, dict) and "error" not in options_data:
                    iv_analysis = options_data.get("iv_analysis", {})
                    pc_analysis = options_data.get("put_call_ratio", {})
                    summary = options_data.get("summary", {})

                    result["options_analysis"] = {
                        "iv_rank": iv_analysis.get("iv_rank"),
                        "iv_percentile": iv_analysis.get("iv_percentile"),
                        "iv_environment": iv_analysis.get("iv_environment"),
                        "put_call_ratio": pc_analysis.get("volume_pc_ratio"),
                        "pc_sentiment": pc_analysis.get("sentiment"),
                        "recommended_strategy": summary.get("primary_suggestion")
                    }
            except Exception as e:
                result["options_analysis"] = {"error": str(e)}

            # ========== DETERMINE FINAL SIGNAL ==========
            result["confidence"] = score

            # NEW: Confidence penalty for NO_CONSENSUS - but only when PRIMARY signals disagree
            # Primary signals: Brooks (80% accurate) and Dollar Flow (80% accurate)
            # APO had NO_CONSENSUS but got 80% confidence -> lost 6.2%
            # TRMD had NO_CONSENSUS but Brooks+Dollar_Flow agreed -> won 14.4%
            brooks_vote = direction_votes.get("brooks", "NEUTRAL")
            df_vote = direction_votes.get("dollar_flow", "NEUTRAL")

            # Check if primary signals (Brooks + Dollar Flow) agree with direction
            primary_signals_agree = (
                (actual_direction == "LONG" and brooks_vote == "LONG" and df_vote == "BULLISH") or
                (actual_direction == "SHORT" and brooks_vote == "SHORT" and df_vote == "BEARISH")
            )

            if data_direction == "NO_CONSENSUS" and not primary_signals_agree:
                # Apply 15% confidence penalty only when primary signals also disagree
                original_score = score
                score = max(0, score - 15)
                result["confidence"] = score
                result["warnings"].append(
                    f"NO_CONSENSUS penalty: Confidence reduced from {original_score}% to {score}% "
                    f"(primary signals don't align). Votes: {direction_votes}"
                )
            elif data_direction == "NO_CONSENSUS":
                # NO_CONSENSUS but primary signals agree - no penalty, just note
                result["warnings"].append(
                    f"NO_CONSENSUS but Brooks+Dollar_Flow agree on {actual_direction}. "
                    f"Votes: {direction_votes}"
                )

            # Count passed gates
            # Note: Gate 5 (OPTIONS) is optional - stock is always available as fallback
            core_gates = ["catalyst", "freshness", "brooks", "quality"]
            core_gates_passed = sum(1 for g in core_gates if result["gate_status"].get(g) == "PASS")
            all_gates_passed = sum(1 for g in result["gate_status"].values() if g == "PASS")
            gate_5_passed = result["gate_status"].get("options_tradability") == "PASS"

            # Calculate composite score (weighted: confidence 60% + gates 40%)
            # Use all 5 gates for scoring (Gate 5 = options tradability)
            gate_score = (all_gates_passed / 5) * 100
            result["composite_score"] = round(score * 0.6 + gate_score * 0.4, 1)
            result["gates_passed"] = all_gates_passed
            result["core_gates_passed"] = core_gates_passed

            # NEW: 5-gate signal classification
            # 5/5 gates (including options) = STRONG signal with OPTIONS recommended
            # 4/4 core gates (no options) = STRONG signal with STOCK only
            # Gate 5 determines OPTIONS vs STOCK, not signal strength
            if all_gates_passed == 5 and score >= 80 and data_direction != "NO_CONSENSUS":
                result["signal"] = f"STRONG_{'BUY' if actual_direction == 'LONG' else 'SELL'}"
                result["vehicle"] = "OPTIONS"  # 5/5 gates -> use options
            elif core_gates_passed == 4 and score >= 80 and data_direction != "NO_CONSENSUS":
                result["signal"] = f"STRONG_{'BUY' if actual_direction == 'LONG' else 'SELL'}"
                result["vehicle"] = "STOCK"  # 4/4 core gates but Gate 5 failed -> use stock
            elif all_gates_passed == 5 and score >= 70:
                # 5/5 gates but lower confidence or NO_CONSENSUS -> regular BUY/SELL with options
                result["signal"] = "BUY" if actual_direction == "LONG" else "SELL"
                result["vehicle"] = "OPTIONS"
            elif core_gates_passed == 4 and score >= 70:
                # 4/4 core gates but lower confidence -> regular BUY/SELL with stock
                result["signal"] = "BUY" if actual_direction == "LONG" else "SELL"
                result["vehicle"] = "STOCK"
            elif core_gates_passed >= 3 and score >= 55:
                result["signal"] = "BUY" if actual_direction == "LONG" else "SELL"
                result["vehicle"] = "STOCK"  # 3/4 gates -> stock only (lower conviction)
            elif core_gates_passed >= 2 and score >= 40:
                result["signal"] = "WATCH"
                result["vehicle"] = "NONE"
            else:
                result["signal"] = "NO_TRADE"
                result["vehicle"] = "NONE"

            # Generate summary
            gates_str = f"{all_gates_passed}/5"
            result["summary"] = f"{ticker}: {result['signal']} | Confidence: {score}% | Gates: {gates_str} | Vehicle: {result.get('vehicle', 'STOCK')}"

            # ========== GATE 5 DECISION FRAMEWORK: OPTIONS vs STOCK ==========
            # Use Gate 5 results to decide between options and stock
            actionable_signals = ["STRONG_BUY", "BUY", "STRONG_SELL", "SELL"]
            if result.get("signal") in actionable_signals and gate_5_result:
                try:
                    from ..options.decision_framework import should_use_options, build_options_plan, build_stock_plan

                    # Get conviction level from signal
                    conviction = "STRONG" if result["signal"] in ["STRONG_BUY", "STRONG_SELL"] else "MODERATE"

                    # Decide: OPTIONS vs STOCK
                    decision = should_use_options(
                        gate_5_result=gate_5_result,
                        stock_liquidity={"tier": options_data.get("institutional", {}).get("liquidity_tier", {}).get("tier", "TIER_2") if options_data else "TIER_2"},
                        conviction_level=conviction,
                        account_size=account_size
                    )

                    # Store decision
                    result["options_vs_stock_decision"] = decision

                    # Build appropriate plan
                    if decision.get("use_options"):
                        # OPTIONS: Use Gate 5 options plan
                        result["vehicle"] = "OPTIONS"
                        result["options_trade_plan"] = decision.get("options_plan")
                        result["stock_trade_plan"] = None  # No stock plan needed
                        result["summary"] = f"{ticker}: {result['signal']} via OPTIONS | {decision.get('reason', '')}"
                    else:
                        # STOCK: Build stock plan with Al Brooks stops
                        result["vehicle"] = "STOCK"
                        result["options_trade_plan"] = None
                        result["stock_trade_plan"] = decision.get("stock_plan") or result.get("trading_plan")
                        result["summary"] = f"{ticker}: {result['signal']} via STOCK | {decision.get('reason', '')}"

                except Exception as e:
                    # Fallback to stock if Gate 5 decision framework fails
                    result["vehicle"] = "STOCK"
                    result["options_trade_plan"] = None
                    result["warnings"].append(f"Gate 5 decision error: {e}. Defaulting to STOCK.")
                    logger.error(f"Gate 5 decision framework error for {ticker}: {e}", exc_info=True)

            elif result.get("signal") in actionable_signals:
                # Gate 5 not available - default to STOCK
                result["vehicle"] = "STOCK"
                result["options_trade_plan"] = None
                result["warnings"].append("Gate 5 unavailable - using STOCK only")

            else:
                # Signal not actionable - no plans needed
                result["vehicle"] = "NONE"
                result["options_trade_plan"] = None
                result["stock_trade_plan"] = None

        except Exception as e:
            result["error"] = str(e)
            result["signal"] = "ERROR"

        # ========== AUTO-STORE PREDICTION ==========
        # Store prediction automatically for tracking (unless disabled)
        # Only store actionable signals: STRONG_BUY, BUY, STRONG_SELL, SELL
        # Skip: WATCH, NO_TRADE, ERROR (not actionable predictions)
        actionable_signals = ["STRONG_BUY", "BUY", "STRONG_SELL", "SELL"]
        if auto_store and result.get("signal") in actionable_signals:
            try:
                from ..prediction_tracker import PredictionTracker
                tracker = PredictionTracker()
                final_direction = result.get("direction") or result.get("data_direction", "LONG")
                if final_direction == "NO_CONSENSUS":
                    final_direction = "LONG"  # Default to LONG if no consensus

                store_result = tracker.store_prediction(
                    trading_signal=result,
                    report_type=report_type,
                    ticker=ticker,
                    direction=final_direction
                )
                result["prediction_stored"] = True
                result["prediction_id"] = store_result.get("prediction_id")
                result["prediction_status"] = store_result.get("status")
            except Exception as e:
                result["prediction_stored"] = False
                result["prediction_error"] = str(e)
        elif auto_store:
            # Signal was not actionable (WATCH, NO_TRADE, ERROR) - skip storage
            result["prediction_stored"] = False
            result["prediction_skipped_reason"] = f"Signal '{result.get('signal')}' not actionable"

        return result

    # Expose closure function via module-level _impl reference
    global generate_trading_signal_impl
    generate_trading_signal_impl = generate_trading_signal
