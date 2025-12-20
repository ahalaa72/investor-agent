"""
TradingView Stock Scanner Module

Provides market scanning functionality using the tradingview-screener package.
Identifies potential LONG and SHORT candidates based on technical setups.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

import pandas as pd
import pytz

logger = logging.getLogger(__name__)

# Try to import tradingview-screener
try:
    from tradingview_screener import Query, col
    SCREENER_AVAILABLE = True
except ImportError:
    SCREENER_AVAILABLE = False
    logger.warning("tradingview-screener not installed. Install with: pip install tradingview-screener")


# Setup type definitions - Updated for inflection point detection
LONG_SETUPS = {
    "momentum_long": "Momentum Long",          # ADX/RSI aligned for uptrend entry
    "consolidation_breakout": "Consolidation Breakout",  # NEW: Breaking 20-day range
    "golden_cross": "Golden Cross",
    "macd_bullish": "MACD Bullish",
    "volume_breakout": "Volume Breakout",
    "support_bounce": "Support Bounce",
}

SHORT_SETUPS = {
    "momentum_short": "Momentum Short",        # ADX/RSI aligned for downtrend entry
    "consolidation_breakdown": "Consolidation Breakdown",  # NEW: Breaking 20-day range down
    "death_cross": "Death Cross",
    "macd_bearish": "MACD Bearish",
    "breakdown": "Breakdown",
    "resistance_rejection": "Resistance Rejection",
}


class TradingViewScanner:
    """
    Scanner for finding trading opportunities using TradingView's screener API.

    Supports US and Canadian markets with customizable filters.
    """

    # Common fields to select in all queries
    BASE_FIELDS = [
        'name', 'close', 'volume', 'market_cap_basic',
        'change', 'change_abs', 'Recommend.All'
    ]

    TECHNICAL_FIELDS = [
        'RSI', 'RSI[1]',  # Current and previous RSI
        'MACD.macd', 'MACD.signal',
        'SMA20', 'SMA50', 'SMA200',
        'EMA20', 'EMA50',
        'relative_volume_10d_calc',
        'price_52_week_high', 'price_52_week_low',
        'BB.upper', 'BB.lower',
        'ADX', 'ATR',
        # Performance fields for extended move exclusion
        'Perf.3M', 'Perf.1M',
        # 20-day high/low calculated from recent prices (via High.1M, Low.1M as proxy)
        'High.1M', 'Low.1M',
    ]

    def __init__(self):
        if not SCREENER_AVAILABLE:
            raise ImportError("tradingview-screener package is required. Install with: pip install tradingview-screener")

    def _get_market_filter(self, market: Literal["america", "canada", "both"]) -> Optional[str]:
        """Get the market filter string for TradingView query."""
        if market == "america":
            return "america"
        elif market == "canada":
            return "canada"
        return None  # 'both' returns None to scan all markets

    def _base_query(self, market: str = "america") -> "Query":
        """Create a base query with common fields."""
        query = Query().select(*(self.BASE_FIELDS + self.TECHNICAL_FIELDS))
        if market and market != "both":
            query = query.set_markets(market)
        return query

    def _get_base_filter_conditions(
        self,
        min_price: float,
        min_market_cap: int,
        direction: str = "LONG",
        apply_tier1: bool = True
    ) -> list:
        """Get base filter conditions as a list (to be combined with setup-specific filters).

        IMPORTANT: tradingview-screener's .where() calls OVERRIDE each other,
        so all conditions must be passed in a single .where() call.

        Tier 1 Momentum Filters (Required for inflection points):
        - ADX 20-40: Trending but not exhausted
        - RSI 40-65 (long) / 35-60 (short): Room to run
        - EMA20 Distance < 5%: Price near trend

        Tier 4 Exclusion Filters (Hard Rejects):
        - Extended Move: >+50% 3mo (long), <-40% 3mo (short)
        - Volatility Minimum: ATR > 2% of price (validated post-processing)
        - 52-Week Proximity: Within 5% of high (long) or low (short)
        """
        conditions = [
            col('close') >= min_price,
            col('market_cap_basic') >= min_market_cap,
            col('volume') >= 100000,  # Minimum daily volume
            col('type') == 'stock',   # Only common stocks
        ]

        # TIER 1: Momentum Quality Filters (find stocks ENTERING trends)
        if apply_tier1:
            # ADX 20-40: Trending but not exhausted
            conditions.extend([
                col('ADX') >= 20,  # Must be trending
                col('ADX') <= 40,  # Not exhausted
            ])

            if direction == "LONG":
                # RSI 40-65: Room to run up (not oversold extremes)
                conditions.extend([
                    col('RSI') >= 40,  # Not falling knife
                    col('RSI') <= 65,  # Room to run
                ])
            else:  # SHORT
                # RSI 35-60: Room to fall (not overbought extremes)
                conditions.extend([
                    col('RSI') >= 35,  # Not capitulation
                    col('RSI') <= 60,  # Room to fall
                ])

        # TIER 4: Extended Move Exclusion (query-level)
        if direction == "LONG":
            # Reject stocks up >50% in 3 months (already extended)
            conditions.append(col('Perf.3M') < 50)
            # Reject stocks up >30% in 1 month (recent surge)
            conditions.append(col('Perf.1M') < 30)
            # Note: 52-week proximity check done in post-processing (Column*float not supported)
        else:  # SHORT
            # Reject stocks down >40% in 3 months (already crashed)
            conditions.append(col('Perf.3M') > -40)
            # Reject stocks down >25% in 1 month (recent crash)
            conditions.append(col('Perf.1M') > -25)
            # Note: 52-week proximity check done in post-processing (Column*float not supported)

        return conditions

    def scan_long_setups(
        self,
        setup_type: str = "all",
        market: Literal["america", "canada", "both"] = "both",
        min_price: float = 2.0,
        min_market_cap: int = 1_000_000_000,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Scan for LONG setup candidates.

        Args:
            setup_type: Specific setup or "all" for combined scan
            market: Market to scan ("america", "canada", "both")
            min_price: Minimum stock price
            min_market_cap: Minimum market cap
            limit: Maximum results to return

        Returns:
            List of candidate dictionaries with technical data
        """
        results = []

        if market == "both":
            # Scan both markets
            for mkt in ["america", "canada"]:
                results.extend(self._scan_long_market(
                    setup_type, mkt, min_price, min_market_cap, limit // 2
                ))
        else:
            results = self._scan_long_market(
                setup_type, market, min_price, min_market_cap, limit
            )

        # Sort by signal strength and limit
        results.sort(key=lambda x: x.get('signal_strength', 0), reverse=True)
        return results[:limit]

    def _scan_long_market(
        self,
        setup_type: str,
        market: str,
        min_price: float,
        min_market_cap: int,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Scan a single market for LONG setups."""
        try:
            query = self._base_query(market)

            # Get base filters with LONG direction for Tier 4 exclusions
            conditions = self._get_base_filter_conditions(min_price, min_market_cap, direction="LONG")

            # Add setup-specific filters
            if setup_type == "all":
                # For "all", use Tier 1 momentum + positive recommendation
                conditions.append(col('Recommend.All') > 0)
            elif setup_type == "momentum_long":
                # Tier 1 filters already applied via base conditions
                # Add MACD confirmation
                conditions.append(col('MACD.macd') > col('MACD.signal'))
            elif setup_type == "consolidation_breakout":
                # Breaking 20-day high with volume confirmation
                conditions.extend([
                    col('close') > col('High.1M'),        # Breaking 1-month high (proxy for 20-day)
                    col('relative_volume_10d_calc') >= 1.5,  # Volume surge
                    col('relative_volume_10d_calc') <= 4.0,  # Not panic buying
                ])
            elif setup_type == "golden_cross":
                conditions.extend([
                    col('SMA20') > col('SMA50'),
                    col('close') > col('SMA20'),
                ])
            elif setup_type == "macd_bullish":
                conditions.append(col('MACD.macd') > col('MACD.signal'))
            elif setup_type == "volume_breakout":
                conditions.extend([
                    col('relative_volume_10d_calc') >= 1.5,
                    col('relative_volume_10d_calc') <= 4.0,  # Cap at 4x
                    col('change') > 0,
                ])
            elif setup_type == "support_bounce":
                conditions.append(col('RSI') > col('RSI[1]'))

            # Apply all conditions in single where call (CRITICAL!)
            query = query.where(*conditions)

            # Order by recommendation score
            query = query.order_by('Recommend.All', ascending=False).limit(limit)

            count, df = query.get_scanner_data()

            if df.empty:
                return []

            return self._format_results(df, "LONG", setup_type, market, min_price, min_market_cap)

        except Exception as e:
            logger.error(f"Error scanning {market} for LONG setups: {e}")
            return []

    def scan_short_setups(
        self,
        setup_type: str = "all",
        market: Literal["america", "canada", "both"] = "both",
        min_price: float = 2.0,
        min_market_cap: int = 1_000_000_000,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Scan for SHORT setup candidates.

        Args:
            setup_type: Specific setup or "all" for combined scan
            market: Market to scan ("america", "canada", "both")
            min_price: Minimum stock price
            min_market_cap: Minimum market cap
            limit: Maximum results to return

        Returns:
            List of candidate dictionaries with technical data
        """
        results = []

        if market == "both":
            for mkt in ["america", "canada"]:
                results.extend(self._scan_short_market(
                    setup_type, mkt, min_price, min_market_cap, limit // 2
                ))
        else:
            results = self._scan_short_market(
                setup_type, market, min_price, min_market_cap, limit
            )

        results.sort(key=lambda x: x.get('signal_strength', 0), reverse=True)
        return results[:limit]

    def _scan_short_market(
        self,
        setup_type: str,
        market: str,
        min_price: float,
        min_market_cap: int,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Scan a single market for SHORT setups."""
        try:
            query = self._base_query(market)

            # Get base filters with SHORT direction for Tier 4 exclusions
            conditions = self._get_base_filter_conditions(min_price, min_market_cap, direction="SHORT")

            # Add setup-specific filters
            if setup_type == "all":
                # For "all", use Tier 1 momentum + negative recommendation
                conditions.append(col('Recommend.All') < 0)
            elif setup_type == "momentum_short":
                # Tier 1 filters already applied via base conditions
                # Add MACD confirmation
                conditions.append(col('MACD.macd') < col('MACD.signal'))
            elif setup_type == "consolidation_breakdown":
                # Breaking 20-day low with volume confirmation
                conditions.extend([
                    col('close') < col('Low.1M'),         # Breaking 1-month low (proxy for 20-day)
                    col('relative_volume_10d_calc') >= 1.5,  # Volume surge
                    col('relative_volume_10d_calc') <= 4.0,  # Not panic selling
                ])
            elif setup_type == "death_cross":
                conditions.extend([
                    col('SMA20') < col('SMA50'),
                    col('close') < col('SMA20'),
                ])
            elif setup_type == "macd_bearish":
                conditions.append(col('MACD.macd') < col('MACD.signal'))
            elif setup_type == "breakdown":
                conditions.extend([
                    col('close') < col('SMA50'),
                    col('relative_volume_10d_calc') >= 1.5,
                    col('relative_volume_10d_calc') <= 4.0,  # Cap at 4x
                    col('change') < 0,
                ])
            elif setup_type == "resistance_rejection":
                conditions.append(col('change') < 0)

            # Apply all conditions in single where call (CRITICAL!)
            query = query.where(*conditions)

            # Order by recommendation (ascending = most bearish first)
            query = query.order_by('Recommend.All', ascending=True).limit(limit)

            count, df = query.get_scanner_data()

            if df.empty:
                return []

            return self._format_results(df, "SHORT", setup_type, market, min_price, min_market_cap)

        except Exception as e:
            logger.error(f"Error scanning {market} for SHORT setups: {e}")
            return []

    def _format_results(
        self,
        df,
        direction: str,
        setup_type: str,
        market: str,
        min_price: float = 2.0,
        min_market_cap: int = 1_000_000_000
    ) -> List[Dict[str, Any]]:
        """Format DataFrame results into structured dictionaries with validation."""
        results = []

        def safe_val(val, default=0):
            """Safely get a numeric value, handling None and NaN."""
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return default
            return val

        def safe_round(val, decimals, default=0):
            """Safely round a value."""
            val = safe_val(val, default)
            return round(val, decimals)

        def safe_int(val, default=0):
            """Safely convert to int."""
            val = safe_val(val, default)
            return int(val)

        for _, row in df.iterrows():
            # POST-PROCESSING VALIDATION: Double-check filters
            price = safe_val(row.get('close'), 0)
            mcap = safe_val(row.get('market_cap_basic'), 0)
            vol = safe_val(row.get('volume'), 0)
            atr = safe_val(row.get('ATR'), 0)
            perf_3m = safe_val(row.get('Perf.3M'), 0)
            perf_1m = safe_val(row.get('Perf.1M'), 0)

            # Skip if doesn't meet minimum criteria
            if price < min_price:
                logger.debug(f"Skipping {row.get('name')}: price ${price:.2f} < ${min_price}")
                continue
            if mcap < min_market_cap:
                logger.debug(f"Skipping {row.get('name')}: mcap ${mcap:,.0f} < ${min_market_cap:,.0f}")
                continue
            if vol < 100000:
                logger.debug(f"Skipping {row.get('name')}: volume {vol:,.0f} < 100,000")
                continue

            # TIER 4: ATR Volatility Minimum - Reject slow-moving stocks
            # ATR must be > 2% of price for sufficient volatility
            if price > 0 and atr > 0:
                atr_pct = (atr / price) * 100
                if atr_pct < 2.0:
                    logger.debug(f"Skipping {row.get('name')}: ATR {atr_pct:.1f}% < 2.0% (too slow)")
                    continue

            # TIER 1: EMA20 Distance Filter - Price must be within 5% of EMA20
            ema20 = safe_val(row.get('EMA20'), 0)
            if ema20 > 0 and price > 0:
                ema20_distance = abs((price - ema20) / ema20) * 100
                if ema20_distance > 5.0:
                    logger.debug(f"Skipping {row.get('name')}: EMA20 distance {ema20_distance:.1f}% > 5% (too far)")
                    continue

            # TIER 4: Extended Move Exclusion (double-check query filters)
            high_52w = safe_val(row.get('price_52_week_high'), 0)
            low_52w = safe_val(row.get('price_52_week_low'), 0)

            if direction == "LONG":
                if perf_3m >= 50:
                    logger.debug(f"Skipping {row.get('name')}: 3mo perf {perf_3m:.1f}% >= 50% (extended)")
                    continue
                if perf_1m >= 30:
                    logger.debug(f"Skipping {row.get('name')}: 1mo perf {perf_1m:.1f}% >= 30% (recent surge)")
                    continue
                # 52-week proximity check: Reject if within 5% of 52w high (limited upside)
                if high_52w > 0 and price >= high_52w * 0.95:
                    logger.debug(f"Skipping {row.get('name')}: price ${price:.2f} within 5% of 52w high ${high_52w:.2f}")
                    continue
            else:  # SHORT
                if perf_3m <= -40:
                    logger.debug(f"Skipping {row.get('name')}: 3mo perf {perf_3m:.1f}% <= -40% (crashed)")
                    continue
                if perf_1m <= -25:
                    logger.debug(f"Skipping {row.get('name')}: 1mo perf {perf_1m:.1f}% <= -25% (recent crash)")
                    continue
                # 52-week proximity check: Reject if within 5% of 52w low (limited downside)
                if low_52w > 0 and price <= low_52w * 1.05:
                    logger.debug(f"Skipping {row.get('name')}: price ${price:.2f} within 5% of 52w low ${low_52w:.2f}")
                    continue
            try:
                # Calculate signal strength (0-100)
                signal_strength = self._calculate_signal_strength(row, direction)

                # Determine setup type label
                if setup_type == "all":
                    detected_setup = self._detect_setup_type(row, direction)
                else:
                    detected_setup = LONG_SETUPS.get(setup_type) or SHORT_SETUPS.get(setup_type) or setup_type

                result = {
                    'symbol': row.get('name', 'UNKNOWN'),
                    'price': safe_round(row.get('close'), 2),
                    'change_pct': safe_round(row.get('change'), 2),
                    'volume': safe_int(row.get('volume')),
                    'market_cap': safe_int(row.get('market_cap_basic')),
                    'market': market,
                    'direction': direction,
                    'signal_strength': signal_strength,
                    'setup_type': detected_setup,
                    'recommendation': self._get_recommendation_label(signal_strength),
                    'metrics': {
                        'rsi': safe_round(row.get('RSI'), 1, 50),
                        'macd': safe_round(row.get('MACD.macd'), 4),
                        'macd_signal': safe_round(row.get('MACD.signal'), 4),
                        'sma20': safe_round(row.get('SMA20'), 2),
                        'sma50': safe_round(row.get('SMA50'), 2),
                        'ema20': safe_round(row.get('EMA20'), 2),
                        'rel_volume': safe_round(row.get('relative_volume_10d_calc'), 2, 1),
                        'vs_sma20': self._calc_vs_sma(safe_val(row.get('close')), safe_val(row.get('SMA20'))),
                        'vs_52w_high': self._calc_vs_52w(safe_val(row.get('close')), safe_val(row.get('price_52_week_high'))),
                        'recommend_all': safe_round(row.get('Recommend.All'), 2),
                        # Tier 4 metrics for transparency
                        'adx': safe_round(row.get('ADX'), 1),
                        'atr': safe_round(row.get('ATR'), 2),
                        'atr_pct': safe_round((atr / price * 100) if price > 0 else 0, 1),
                        'perf_3m': safe_round(row.get('Perf.3M'), 1),
                        'perf_1m': safe_round(row.get('Perf.1M'), 1),
                    }
                }
                results.append(result)

            except Exception as e:
                logger.warning(f"Error formatting row: {e}")
                continue

        return results

    def _calculate_signal_strength(self, row, direction: str) -> int:
        """
        Calculate signal strength score (0-100) based on technical indicators.

        Components:
        - RSI alignment: 25 pts
        - MACD alignment: 20 pts
        - Price vs SMA: 20 pts
        - Volume: 15 pts
        - TradingView recommendation: 20 pts
        """
        score = 0

        # Helper to safely get numeric values, handling None and NaN
        def safe_get(key, default):
            val = row.get(key)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return default
            return val

        rsi = safe_get('RSI', 50)
        macd = safe_get('MACD.macd', 0)
        macd_signal = safe_get('MACD.signal', 0)
        close = safe_get('close', 0)
        sma20 = safe_get('SMA20', 0)
        sma50 = safe_get('SMA50', 0)
        rel_vol = safe_get('relative_volume_10d_calc', 1)
        recommend = safe_get('Recommend.All', 0)

        if direction == "LONG":
            # RSI: Oversold is bullish (25 pts)
            if rsi < 30:
                score += 25
            elif rsi < 40:
                score += 20
            elif rsi < 50:
                score += 15
            elif rsi < 60:
                score += 10

            # MACD above signal (20 pts)
            if macd > macd_signal:
                score += 20
            elif macd > macd_signal * 0.95:
                score += 10

            # Price above SMAs (20 pts)
            if close > sma20 and close > sma50:
                score += 20
            elif close > sma20:
                score += 15
            elif close > sma50:
                score += 10

            # Volume surge (15 pts)
            if rel_vol > 2.0:
                score += 15
            elif rel_vol > 1.5:
                score += 10
            elif rel_vol > 1.2:
                score += 5

            # TradingView recommendation (20 pts)
            # recommend ranges from -1 (strong sell) to 1 (strong buy)
            if recommend > 0.5:
                score += 20
            elif recommend > 0.2:
                score += 15
            elif recommend > 0:
                score += 10
            elif recommend > -0.2:
                score += 5

        else:  # SHORT
            # RSI: Overbought is bearish (25 pts)
            if rsi > 75:
                score += 25
            elif rsi > 65:
                score += 20
            elif rsi > 55:
                score += 15
            elif rsi > 50:
                score += 10

            # MACD below signal (20 pts)
            if macd < macd_signal:
                score += 20
            elif macd < macd_signal * 1.05:
                score += 10

            # Price below SMAs (20 pts)
            if close < sma20 and close < sma50:
                score += 20
            elif close < sma20:
                score += 15
            elif close < sma50:
                score += 10

            # Volume surge (15 pts)
            if rel_vol > 2.0:
                score += 15
            elif rel_vol > 1.5:
                score += 10
            elif rel_vol > 1.2:
                score += 5

            # TradingView recommendation (20 pts) - inverted for shorts
            if recommend < -0.5:
                score += 20
            elif recommend < -0.2:
                score += 15
            elif recommend < 0:
                score += 10
            elif recommend < 0.2:
                score += 5

        return min(100, max(0, score))

    def _detect_setup_type(self, row, direction: str) -> str:
        """Auto-detect the most relevant setup type based on indicators."""
        def safe_get(key, default):
            val = row.get(key)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return default
            return val

        rsi = safe_get('RSI', 50)
        adx = safe_get('ADX', 25)
        macd = safe_get('MACD.macd', 0)
        macd_signal = safe_get('MACD.signal', 0)
        close = safe_get('close', 0)
        sma20 = safe_get('SMA20', 0)
        sma50 = safe_get('SMA50', 0) or 1  # Avoid division by zero
        ema20 = safe_get('EMA20', 0) or 1
        rel_vol = safe_get('relative_volume_10d_calc', 1)
        high_20d = safe_get('High.1M', 0)  # Using 1-month high as proxy for 20-day
        low_20d = safe_get('Low.1M', 0)    # Using 1-month low as proxy for 20-day
        high_52w = safe_get('price_52_week_high', 0) or 1  # Avoid division by zero

        if direction == "LONG":
            # Consolidation Breakout - highest priority (inflection point)
            if high_20d > 0 and close > high_20d and rel_vol >= 1.5:
                return "Consolidation Breakout"
            # Momentum Long - ADX/RSI aligned for trend entry
            elif 20 <= adx <= 40 and 40 <= rsi <= 65 and macd > macd_signal:
                return "Momentum Long"
            elif sma20 > sma50 and close > sma20:
                return "Golden Cross"
            elif macd > macd_signal and macd > 0:
                return "MACD Bullish"
            elif rel_vol >= 1.5 and safe_get('change', 0) > 0:
                return "Volume Breakout"
            elif sma50 > 0 and abs(close - sma50) / sma50 < 0.02:
                return "Support Bounce"
            else:
                return "Bullish Setup"
        else:  # SHORT
            # Consolidation Breakdown - highest priority (inflection point)
            if low_20d > 0 and close < low_20d and rel_vol >= 1.5:
                return "Consolidation Breakdown"
            # Momentum Short - ADX/RSI aligned for downtrend entry
            elif 20 <= adx <= 40 and 35 <= rsi <= 60 and macd < macd_signal:
                return "Momentum Short"
            elif sma20 < sma50 and close < sma20:
                return "Death Cross"
            elif macd < macd_signal and macd < 0:
                return "MACD Bearish"
            elif rel_vol >= 1.5 and close < sma50:
                return "Breakdown"
            elif close > high_52w * 0.95 and safe_get('change', 0) < 0:
                return "Resistance Rejection"
            else:
                return "Bearish Setup"

    def _get_recommendation_label(self, signal_strength: int) -> str:
        """Convert signal strength to recommendation label."""
        if signal_strength >= 80:
            return "STRONG"
        elif signal_strength >= 65:
            return "BUY/SHORT"
        elif signal_strength >= 50:
            return "WATCH"
        else:
            return "WEAK"

    def _calc_vs_sma(self, price: float, sma: float) -> str:
        """Calculate percentage vs SMA."""
        if not sma or sma == 0:
            return "N/A"
        pct = ((price - sma) / sma) * 100
        return f"{pct:+.1f}%"

    def _calc_vs_52w(self, price: float, high_52w: float) -> str:
        """Calculate percentage vs 52-week high."""
        if not high_52w or high_52w == 0:
            return "N/A"
        pct = ((price - high_52w) / high_52w) * 100
        return f"{pct:+.1f}%"


def get_scanner() -> TradingViewScanner:
    """Get a TradingViewScanner instance."""
    return TradingViewScanner()
