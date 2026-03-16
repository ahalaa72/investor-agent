"""Scanning tools - market opportunity detection.

5 MCP tools + ~14 helpers for scanning US/Canadian markets.
Uses TradingView/Finviz screeners with 4/5-gate validation.
"""
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime
from typing import Any, Literal

from ..core.price import convert_numpy_types

logger = logging.getLogger(__name__)


def _auto_track_picks(result: dict, scanner_source: str = "tradingview"):
    """Automatically track picks from scan results."""
    from .tracking import track_scanner_pick

    for direction in ["long_candidates", "short_candidates"]:
        candidates = result.get(direction, [])
        for c in candidates[:3]:  # Only track top 3
            try:
                brooks = c.get("brooks_analysis", {})
                track_scanner_pick(
                    ticker=c.get("symbol", "UNKNOWN"),
                    direction="LONG" if "long" in direction else "SHORT",
                    composite_score=c.get("composite_score", 0),
                    entry_price=brooks.get("entry", c.get("price", 0)),
                    stop_price=brooks.get("stop", 0),
                    target_price=brooks.get("target", 0),
                    signal=c.get("recommendation", {}).get("label", "UNKNOWN"),
                    scanner_source=scanner_source
                )
            except Exception as e:
                logger.warning(f"Failed to track pick: {e}")


def _get_ohlcv_for_ticker(ticker: str, period: str = "3mo") -> pd.DataFrame | None:
    """
    DEPRECATED: Use _get_ohlcv_cached() instead.
    Legacy helper kept for backward compatibility.
    """
    try:
        hist = yf.Ticker(ticker).history(period=period, interval="1d")
        if hist is not None and not hist.empty:
            return hist
    except Exception as e:
        logger.warning(f"Failed to get OHLCV for {ticker}: {e}")
    return None


# OHLCV Cache - Module level
_ohlcv_cache: dict[str, tuple[pd.DataFrame, datetime]] = {}
_ohlcv_mtf_cache: dict[str, tuple[pd.DataFrame, datetime]] = {}  # Multi-timeframe cache (weekly/monthly)
_cache_ttl_seconds = 300  # 5 minutes

# === PROPOSAL 5: Scan Result Caching ===
_scan_cache: dict[str, tuple[dict, datetime]] = {}
_scan_cache_ttl_seconds = 300  # 5 minutes


def _get_scan_cache(market: str, filters_hash: str) -> dict | None:
    """Get cached scan results if fresh."""
    from datetime import datetime
    key = f"{market}_{filters_hash}"
    if key in _scan_cache:
        result, timestamp = _scan_cache[key]
        age_seconds = (datetime.now() - timestamp).total_seconds()
        if age_seconds < _scan_cache_ttl_seconds:
            logger.info(f"💾 Scan Cache HIT for {market} (age: {age_seconds:.1f}s)")
            return result
    return None


def _set_scan_cache(market: str, filters_hash: str, results: dict) -> None:
    """Cache scan results."""
    from datetime import datetime
    key = f"{market}_{filters_hash}"
    _scan_cache[key] = (results, datetime.now())
    logger.debug(f"💾 Scan Cache SET for {market}")


# === PROPOSAL 3: Feature Availability Tracking ===
class FeatureAvailability:
    """Track which enhanced features are available for graceful degradation."""

    _instance = None
    _checked = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not FeatureAvailability._checked:
            self.features = {}
            self._check_features()
            FeatureAvailability._checked = True

    def _check_features(self):
        """Check which features are available at startup."""
        # CVD Analysis
        try:
            from investor_agent.realtime_order_flow import analyze_realtime_trade_flow
            self.features['cvd_analysis'] = True
            logger.info("✅ Feature available: CVD Analysis (realtime_order_flow)")
        except ImportError:
            self.features['cvd_analysis'] = False
            logger.warning("⚠️ Feature unavailable: CVD Analysis - scoring will be degraded by ~3 points")

        # Exhaustion Score
        try:
            from investor_agent.technical_analysis_bootstrap import calculate_exhaustion_score
            self.features['exhaustion_score'] = True
            logger.info("✅ Feature available: Exhaustion Score")
        except ImportError:
            self.features['exhaustion_score'] = False
            logger.warning("⚠️ Feature unavailable: Exhaustion Score - Tier 4 filtering degraded")

        # Al Brooks Analysis (always available in analyze_technical)
        self.features['al_brooks'] = True

        # Questrade API
        try:
            # Check if Questrade is configured
            import os
            if os.path.exists(os.path.expanduser("~/.questrade.json")):
                self.features['questrade'] = True
                logger.info("✅ Feature available: Questrade API (real-time data)")
            else:
                self.features['questrade'] = False
                logger.warning("⚠️ Feature unavailable: Questrade API - using Yahoo Finance (15-60 min lag)")
        except Exception:
            self.features['questrade'] = False

    def get_score_degradation(self) -> int:
        """Return expected score degradation if features missing."""
        degradation = 0
        if not self.features.get('cvd_analysis', False):
            degradation += 3  # CVD bonus unavailable
        if not self.features.get('exhaustion_score', False):
            degradation += 5  # Exhaustion filtering less accurate
        return degradation

    def get_status_report(self) -> dict:
        """Return feature availability status."""
        return {
            'features': self.features,
            'score_degradation': self.get_score_degradation(),
            'warnings': [f for f, v in self.features.items() if not v]
        }


# Initialize feature availability at module load
_feature_availability = None


def get_feature_availability() -> FeatureAvailability:
    """Get singleton feature availability tracker."""
    global _feature_availability
    if _feature_availability is None:
        _feature_availability = FeatureAvailability()
    return _feature_availability


def detect_market_regime() -> dict:
    """
    Detect current market regime for adaptive weight adjustment.

    Returns:
        dict with regime classification and adaptive weights

    Regimes:
        - BULL_TREND: Price > SMA20 > SMA50, low volatility
        - BEAR_TREND: Price < SMA20 < SMA50, low volatility
        - HIGH_VOL: Volatility > 30%
        - RANGE_BOUND: No clear trend
    """
    import numpy as np

    try:
        # Get SPY data for regime detection
        spy_df = _get_ohlcv_for_ticker_v2("SPY", period="3mo")

        if spy_df is None or len(spy_df) < 50:
            logger.warning("Could not get SPY data for regime detection, using default weights")
            return {
                'regime': 'UNKNOWN',
                'weights': _get_default_weights(),
                'spy_trend': 'UNKNOWN',
                'volatility': 0
            }

        closes = spy_df['Close']
        current_price = closes.iloc[-1]

        # Calculate SMAs
        sma20 = closes.rolling(20).mean().iloc[-1]
        sma50 = closes.rolling(50).mean().iloc[-1]

        # Calculate volatility (annualized)
        returns = closes.pct_change().dropna()
        vol_20d = returns.rolling(20).std().iloc[-1] * np.sqrt(252) * 100

        # Classify regime
        if current_price > sma20 > sma50 and vol_20d < 20:
            regime = "BULL_TREND"
        elif current_price < sma20 < sma50 and vol_20d < 20:
            regime = "BEAR_TREND"
        elif vol_20d > 30:
            regime = "HIGH_VOL"
        else:
            regime = "RANGE_BOUND"

        # Get adaptive weights
        weights = _get_adaptive_weights(regime)

        return {
            'regime': regime,
            'weights': weights,
            'spy_trend': 'BULLISH' if current_price > sma50 else 'BEARISH',
            'volatility': round(vol_20d, 2),
            'sma20': round(sma20, 2),
            'sma50': round(sma50, 2),
            'current_price': round(current_price, 2)
        }

    except Exception as e:
        logger.error(f"Market regime detection failed: {e}")
        return {
            'regime': 'UNKNOWN',
            'weights': _get_default_weights(),
            'spy_trend': 'UNKNOWN',
            'volatility': 0
        }


def _get_default_weights() -> dict:
    """Return default scoring weights."""
    return {
        'momentum': 30,
        'pattern': 28,
        'rs': 15,
        'catalyst': 20,
        'brooks': 10
    }


def _get_adaptive_weights(regime: str) -> dict:
    """Return scoring weights adapted to market regime."""
    if regime == "BULL_TREND":
        # In bull markets, momentum matters more
        return {
            'momentum': 35,  # +5
            'pattern': 23,   # -5
            'rs': 15,
            'catalyst': 20,
            'brooks': 10
        }
    elif regime == "BEAR_TREND":
        # In bear markets, catalyst/quality matters more
        return {
            'momentum': 25,  # -5
            'pattern': 28,
            'rs': 15,
            'catalyst': 25,  # +5
            'brooks': 10
        }
    elif regime == "HIGH_VOL":
        # In high volatility, Al Brooks patterns critical
        return {
            'momentum': 25,  # -5
            'pattern': 25,   # -3
            'rs': 12,        # -3
            'catalyst': 23,  # +3
            'brooks': 18     # +8
        }
    else:  # RANGE_BOUND or UNKNOWN
        return _get_default_weights()


def _get_ohlcv_for_ticker_v2(ticker: str, period: str = "3mo") -> pd.DataFrame | None:
    """
    Fetch OHLCV data with 3-source fallback chain.
    Returns pd.DataFrame for compatibility with existing code.

    Data Sources (priority order) - PROPOSAL 1:
    1. Questrade API (real-time, 0 min lag)
    2. Alpaca API (fallback 1, ~15 min lag) - requires ALPACA_API_KEY/ALPACA_API_SECRET
    3. Yahoo Finance (fallback 2, 15-60 min lag)

    Args:
        ticker: Stock symbol (e.g., "AAPL")
        period: Time period ("3mo", "6mo", "1y", "2y")

    Returns:
        pd.DataFrame with OHLCV data (Date index, OHLC columns)
        or None if all sources fail
    """
    from datetime import datetime, timedelta
    import pytz

    # Calculate time range from period
    period_map = {
        "1mo": 30,
        "3mo": 90,
        "6mo": 180,
        "1y": 365,
        "2y": 730,
        "3y": 1095,
        "5y": 1825
    }
    days = period_map.get(period, 90)

    # Try Questrade first (real-time data)
    try:
        et = pytz.timezone("America/New_York")
        end_dt = datetime.now(et)
        start_dt = end_dt - timedelta(days=days)

        start_time = start_dt.isoformat()
        end_time = end_dt.isoformat()

        from .questrade_api import get_questrade_candles_impl as get_questrade_candles
        candles_dict = get_questrade_candles(
            symbol=ticker,
            interval="OneDay",
            start_time=start_time,
            end_time=end_time
        )

        # Convert dict format to DataFrame
        candles = candles_dict['candles']
        data_source = candles_dict.get('data_source', 'questrade')  # Get actual source used

        if not candles:
            raise ValueError(f"No candle data returned for {ticker}")

        df = pd.DataFrame(candles)

        # Rename columns to match yfinance format
        df = df.rename(columns={
            'start': 'Date',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })

        # Set Date as index and ensure proper DatetimeIndex
        df['Date'] = pd.to_datetime(df['Date'], utc=True)
        df = df.set_index('Date')

        # CRITICAL FIX: Ensure index is DatetimeIndex (not object Index)
        # This fixes AMZN backtesting data issue where index was dtype='object'
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.DatetimeIndex(df.index)

        # Ensure columns are in correct order and type
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        df = df.astype({
            'Open': 'float64',
            'High': 'float64',
            'Low': 'float64',
            'Close': 'float64',
            'Volume': 'int64'
        })

        # === PROPOSAL 2: Timestamp Validation ===
        # Check if data is stale (missing today's bar when market is closed)
        last_bar_date = df.index[-1].date() if hasattr(df.index[-1], 'date') else df.index[-1]
        today = datetime.now(et).date()

        # During market hours (9:30-16:00 ET), expect yesterday's bar
        # After market close, expect today's bar
        market_open = datetime.now(et).replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = datetime.now(et).replace(hour=16, minute=0, second=0, microsecond=0)
        now = datetime.now(et)

        # Check for weekends
        is_weekend = today.weekday() >= 5

        if is_weekend:
            # On weekends, expect Friday's bar
            days_since_friday = (today.weekday() - 4) % 7
            expected_date = today - timedelta(days=days_since_friday)
        elif now < market_open:
            # Before market open, expect yesterday (or Friday if Monday)
            expected_date = today - timedelta(days=1)
            if expected_date.weekday() >= 5:  # Weekend
                expected_date = expected_date - timedelta(days=expected_date.weekday() - 4)
        elif now >= market_close:
            # After market close, expect today's bar
            expected_date = today
        else:
            # During market hours, yesterday's bar is acceptable
            expected_date = today - timedelta(days=1)
            if expected_date.weekday() >= 5:
                expected_date = expected_date - timedelta(days=expected_date.weekday() - 4)

        # Convert last_bar_date if it's a Timestamp
        if hasattr(last_bar_date, 'date'):
            last_bar_date = last_bar_date.date()

        days_stale = (expected_date - last_bar_date).days if isinstance(last_bar_date, type(expected_date)) else 0

        if days_stale > 2:
            logger.warning(f"⚠️ STALE DATA for {ticker}: Last bar {last_bar_date}, expected {expected_date} ({days_stale} days stale)")

        # Log with actual data source
        if data_source.lower() == 'questrade':
            logger.info(f"✅ Retrieved {len(df)} bars for {ticker} from Questrade (real-time, 0 min lag)")
        else:
            logger.info(f"✅ Retrieved {len(df)} bars for {ticker} from Yahoo Finance via get_questrade_candles() (fallback, 15-60 min lag)")

        return df

    except Exception as questrade_error:
        logger.warning(f"⚠️ Questrade failed for {ticker}: {questrade_error} - trying Alpaca fallback")

        # === PROPOSAL 1: Alpaca Fallback (15-min delay, better than Yahoo) ===
        try:
            import os
            from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest

            api_key = os.getenv('ALPACA_API_KEY')
            api_secret = os.getenv('ALPACA_API_SECRET')

            if api_key and api_secret:
                client = StockHistoricalDataClient(api_key, api_secret)

                # For daily bars, use TimeFrame.Day
                request = StockBarsRequest(
                    symbol_or_symbols=ticker,
                    timeframe=TimeFrame.Day,
                    limit=days  # Use same period as Questrade
                )

                df_raw = client.get_stock_bars(request).df

                if not df_raw.empty:
                    # Convert multi-index to simple Date index
                    if isinstance(df_raw.index, pd.MultiIndex):
                        df_raw = df_raw.reset_index(level='symbol', drop=True)

                    # Rename columns to match yfinance format
                    df = df_raw.rename(columns={
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low',
                        'close': 'Close',
                        'volume': 'Volume'
                    })

                    # Ensure columns are in correct order
                    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
                    df = df.astype({
                        'Open': 'float64',
                        'High': 'float64',
                        'Low': 'float64',
                        'Close': 'float64',
                        'Volume': 'int64'
                    })

                    logger.info(f"✅ Retrieved {len(df)} bars for {ticker} from Alpaca (fallback 1, ~15 min lag)")
                    return df
                else:
                    logger.warning(f"⚠️ Alpaca returned empty data for {ticker}")
            else:
                logger.debug(f"Alpaca credentials not set, skipping to Yahoo Finance")

        except Exception as alpaca_error:
            logger.warning(f"⚠️ Alpaca failed for {ticker}: {alpaca_error} - falling back to Yahoo Finance")

        # Fallback to Yahoo Finance (existing behavior)
        try:
            hist = yf.Ticker(ticker).history(period=period, interval="1d")
            if hist is not None and not hist.empty:
                # Ensure consistent format
                hist = hist[['Open', 'High', 'Low', 'Close', 'Volume']]
                logger.info(f"✅ Retrieved {len(hist)} bars for {ticker} from Yahoo Finance (fallback 2, 15-60 min lag)")
                return hist
        except Exception as yf_error:
            logger.error(f"❌ All sources failed for {ticker}. Questrade: {questrade_error}, Yahoo: {yf_error}")

    return None


def _get_ohlcv_cached(ticker: str, period: str = "3mo") -> pd.DataFrame | None:
    """
    Cached version of _get_ohlcv_for_ticker_v2().
    Prevents redundant fetches for same ticker in same scan.

    Cache TTL: 5 minutes

    Args:
        ticker: Stock symbol (e.g., "AAPL")
        period: Time period ("3mo", "6mo", "1y", "2y")

    Returns:
        pd.DataFrame with OHLCV data or None if failed
    """
    from datetime import datetime

    # Check cache
    cache_key = f"{ticker}_{period}"
    if cache_key in _ohlcv_cache:
        df, timestamp = _ohlcv_cache[cache_key]
        age_seconds = (datetime.now() - timestamp).total_seconds()

        if age_seconds < _cache_ttl_seconds:
            logger.debug(f"💾 Cache HIT for {ticker} (age: {age_seconds:.1f}s, TTL: {_cache_ttl_seconds}s)")
            return df.copy()  # Return copy to prevent cache corruption
        else:
            logger.debug(f"⏰ Cache EXPIRED for {ticker} (age: {age_seconds:.1f}s > TTL: {_cache_ttl_seconds}s)")

    # Fetch fresh data
    logger.debug(f"🔄 Cache MISS for {ticker} - fetching from Questrade/Yahoo")
    df = _get_ohlcv_for_ticker_v2(ticker, period)

    # Cache result (only if successful)
    if df is not None and not df.empty:
        _ohlcv_cache[cache_key] = (df.copy(), datetime.now())
        logger.debug(f"💾 Cached OHLCV for {ticker} ({len(df)} bars)")

    return df


def _resample_to_timeframe(daily_df: pd.DataFrame, timeframe: str = "W") -> pd.DataFrame | None:
    """
    Resample daily OHLCV data to weekly or monthly.
    Last resort fallback when both Questrade and yfinance fail for weekly/monthly candles.

    Args:
        daily_df: Daily OHLCV DataFrame (DatetimeIndex, OHLCV columns)
        timeframe: 'W' for weekly, 'ME' for monthly

    Returns:
        Resampled DataFrame or None if input is invalid
    """
    if daily_df is None or daily_df.empty:
        return None
    try:
        resampled = daily_df.resample(timeframe).agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        if resampled.empty:
            return None
        return resampled
    except Exception as e:
        logger.warning(f"Failed to resample to {timeframe}: {e}")
        return None


def _get_ohlcv_multitimeframe(
    ticker: str,
    interval: str = "OneWeek",
    window: int = 104
) -> pd.DataFrame | None:
    """
    Fetch weekly or monthly OHLCV data.
    Source priority: Questrade (OneWeek/OneMonth) → yfinance → resample daily.

    Args:
        ticker: Stock symbol
        interval: "OneWeek" or "OneMonth"
        window: Number of candles to fetch (104 weekly ≈ 2 years, 60 monthly ≈ 5 years)

    Returns:
        pd.DataFrame with OHLCV data or None
    """
    from datetime import datetime as dt, timedelta
    import pytz

    interval_yf_map = {"OneWeek": "1wk", "OneMonth": "1mo"}
    yf_interval = interval_yf_map.get(interval)
    if not yf_interval:
        logger.error(f"Unsupported multi-timeframe interval: {interval}")
        return None

    # Source 1: Questrade (via get_questrade_candles_impl which has yfinance fallback built in)
    try:
        from .questrade_api import get_questrade_candles_impl as get_questrade_candles
        candles_dict = get_questrade_candles(
            symbol=ticker,
            interval=interval,
            window=window
        )

        candles = candles_dict.get('candles', [])
        if not candles:
            raise ValueError(f"No {interval} candle data for {ticker}")

        df = pd.DataFrame(candles)
        df = df.rename(columns={
            'start': 'Date', 'open': 'Open', 'high': 'High',
            'low': 'Low', 'close': 'Close', 'volume': 'Volume'
        })
        df['Date'] = pd.to_datetime(df['Date'], utc=True)
        df = df.set_index('Date')
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.DatetimeIndex(df.index)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        df = df.astype({
            'Open': 'float64', 'High': 'float64',
            'Low': 'float64', 'Close': 'float64', 'Volume': 'int64'
        })

        source = candles_dict.get('data_source', 'questrade')
        logger.info(f"✅ Retrieved {len(df)} {interval} bars for {ticker} from {source}")
        return df

    except Exception as e:
        logger.warning(f"⚠️ {interval} fetch failed for {ticker}: {e}")

    # Source 2: Direct yfinance (if Questrade wrapper failed entirely)
    try:
        period = "2y" if interval == "OneWeek" else "5y"
        hist = yf.Ticker(ticker).history(period=period, interval=yf_interval)
        if hist is not None and not hist.empty:
            hist = hist[['Open', 'High', 'Low', 'Close', 'Volume']]
            logger.info(f"✅ Retrieved {len(hist)} {yf_interval} bars for {ticker} from yfinance")
            return hist
    except Exception as yf_err:
        logger.warning(f"⚠️ yfinance {yf_interval} failed for {ticker}: {yf_err}")

    # Source 3: Resample daily data
    daily = _get_ohlcv_cached(ticker, period="2y" if interval == "OneWeek" else "5y")
    if daily is not None:
        tf = "W" if interval == "OneWeek" else "ME"
        resampled = _resample_to_timeframe(daily, tf)
        if resampled is not None:
            logger.info(f"✅ Resampled {len(resampled)} {interval} bars for {ticker} from daily data")
            return resampled

    logger.error(f"❌ All sources failed for {ticker} {interval}")
    return None


def _get_ohlcv_cached_multitimeframe(
    ticker: str,
    interval: str = "OneWeek",
    window: int = 104
) -> pd.DataFrame | None:
    """
    Cached version of _get_ohlcv_multitimeframe().
    Uses separate cache from daily data to prevent key collisions.

    Args:
        ticker: Stock symbol
        interval: "OneWeek" or "OneMonth"
        window: Number of candles

    Returns:
        pd.DataFrame with OHLCV data or None
    """
    from datetime import datetime as dt

    cache_key = f"{ticker}_{interval}_{window}"
    if cache_key in _ohlcv_mtf_cache:
        df, timestamp = _ohlcv_mtf_cache[cache_key]
        age = (dt.now() - timestamp).total_seconds()
        if age < _cache_ttl_seconds:
            logger.debug(f"💾 MTF Cache HIT for {ticker} {interval} (age: {age:.1f}s)")
            return df.copy()

    df = _get_ohlcv_multitimeframe(ticker, interval, window)
    if df is not None and not df.empty:
        _ohlcv_mtf_cache[cache_key] = (df.copy(), dt.now())

    return df


def get_all_timeframe_data(ticker: str) -> dict[str, pd.DataFrame | None]:
    """
    Fetch data for all three timeframes in top-down order (monthly → weekly → daily).
    The higher timeframe establishes the trend; the lower provides the entry.

    Args:
        ticker: Stock symbol

    Returns:
        dict with 'monthly', 'weekly', 'daily' DataFrames (any can be None)
    """
    monthly = _get_ohlcv_cached_multitimeframe(ticker, "OneMonth", 60)
    weekly = _get_ohlcv_cached_multitimeframe(ticker, "OneWeek", 104)
    daily = _get_ohlcv_cached(ticker, period="6mo")
    return {"monthly": monthly, "weekly": weekly, "daily": daily}


def _create_options_summary(gate_5_result: dict | None, options_decision: dict | None, vehicle: str) -> str:
    """
    Create quick options summary for scanner display.

    Returns strings like:
    - "IC@68IV" - Iron Condor at 68% IV Rank
    - "LC@17IV" - Long Call at 17% IV Rank
    - "STOCK" - Stock recommended (Gate 5 failed or low conviction)
    - "BLOCKED" - Gate 5 blocked (earnings/liquidity issues)
    - "N/A" - Options data unavailable
    """
    if not gate_5_result:
        return "N/A"

    gate_status = gate_5_result.get('gate_status')
    if gate_status == 'SKIP':
        return "N/A"
    elif gate_status == 'FAIL':
        return "BLOCKED"

    # Gate 5 passed - check if OPTIONS chosen
    if vehicle == "OPTIONS" and options_decision and options_decision.get('use_options'):
        # Get IV Rank and strategy
        iv_check = gate_5_result.get('checks', {}).get('iv_environment', {})
        iv_rank = iv_check.get('iv_rank', 0)
        strategy = gate_5_result.get('recommended_strategy', 'UNKNOWN')

        # Map strategy to short code
        strategy_codes = {
            'IRON_CONDOR': 'IC',
            'CREDIT_SPREAD': 'CS',
            'DEBIT_SPREAD': 'DS',
            'BULL_PUT_SPREAD': 'BPS',
            'BEAR_CALL_SPREAD': 'BCS',
            'LONG_CALL': 'LC',
            'LONG_PUT': 'LP',
            'CALENDAR_SPREAD': 'CAL',
            'DIAGONAL_SPREAD': 'DIA',
            'STRADDLE': 'STD',
            'STRANGLE': 'STG'
        }
        code = strategy_codes.get(strategy, 'OPT')

        return f"{code}@{iv_rank:.0f}IV"
    else:
        # STOCK chosen (Gate 5 passed but decision framework chose stock)
        if options_decision:
            reason = options_decision.get('reason', '')
            if 'MODERATE' in reason:
                return "STOCK (MOD)"  # Moderate conviction
            elif 'account' in reason.lower():
                return "STOCK (<$5K)"  # Account too small
            else:
                return "STOCK"
        return "STOCK"


def _get_recent_predictions(direction: str, days: int = 7) -> dict[str, dict]:
    """
    Get predictions from DB for the last N days.

    Used by scanner to skip re-analysis of recently validated tickers.

    Args:
        direction: "LONG" or "SHORT"
        days: Number of days to look back (default 7)

    Returns:
        Dict mapping ticker -> prediction data (most recent per ticker)
    """
    from ..database import execute_query
    from datetime import datetime, timedelta

    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    query = """
        SELECT
            ticker, direction, signal, confidence_score, gates_passed,
            gate_catalyst, gate_freshness, gate_brooks, gate_quality,
            entry_price, stop_price, target_1_price, target_2_price,
            catalyst_direction, catalyst_strength,
            dalio_ratio, dalio_interpretation,
            brooks_probability, brooks_pattern, trap_risk,
            quality_score, quality_grade, f_score, z_score,
            data_direction, created_at
        FROM predictions
        WHERE direction = :direction
          AND prediction_date >= :cutoff_date
          AND report_type = 'scanner'
        ORDER BY created_at DESC
    """

    try:
        rows = execute_query(query, {"direction": direction, "cutoff_date": cutoff_date})

        # Build lookup dict - use most recent prediction per ticker
        result = {}
        for row in rows:
            ticker = row['ticker']
            if ticker not in result:  # Only keep most recent
                result[ticker] = {
                    'signal': row['signal'],
                    'confidence': row['confidence_score'],
                    'gates_passed': row['gates_passed'],
                    'gate_status': {
                        'catalyst': row['gate_catalyst'],
                        'freshness': row['gate_freshness'],
                        'brooks': row['gate_brooks'],
                        'quality': row['gate_quality']
                    },
                    'entry_price': float(row['entry_price']) if row['entry_price'] else None,
                    'stop_price': float(row['stop_price']) if row['stop_price'] else None,
                    'target_1': float(row['target_1_price']) if row['target_1_price'] else None,
                    'target_2': float(row['target_2_price']) if row['target_2_price'] else None,
                    'catalyst_direction': row['catalyst_direction'],
                    'catalyst_strength': row['catalyst_strength'],
                    'dalio_ratio': float(row['dalio_ratio']) if row['dalio_ratio'] else None,
                    'dalio_interpretation': row['dalio_interpretation'],
                    'brooks_probability': float(row['brooks_probability']) if row['brooks_probability'] else None,
                    'brooks_pattern': row['brooks_pattern'],
                    'trap_risk': row['trap_risk'],
                    'quality_score': float(row['quality_score']) if row['quality_score'] else None,
                    'quality_grade': row['quality_grade'],
                    'f_score': row['f_score'],
                    'z_score': float(row['z_score']) if row['z_score'] else None,
                    'data_direction': row['data_direction'],
                    'stored_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'is_repeated': True
                }

        logger.info(f"📦 DB Cache: Found {len(result)} {direction} predictions from last {days} days")
        return result

    except Exception as e:
        logger.warning(f"Failed to fetch recent predictions from DB: {e}")
        return {}


def _scan_one_direction(
    direction: Literal["LONG", "SHORT"],
    market: str,
    min_price: float,
    min_market_cap: int,
    max_scan: int,
    top_n: int,
    batch_size: int = 20,
    candidates: list = None,
    data_driven: bool = False,
    timeout_seconds: int = 0,
    scan_start_override: float = None,
) -> dict[str, Any]:
    """
    Internal helper to scan one direction (LONG or SHORT).

    Process:
    1. Use provided candidates list, or fetch from TradingView if not provided
    2. Process in batches of batch_size (default 50)
    3. Validate each batch through 5-gate system
    4. Compile all validated results across batches
    5. Return top N from combined pool

    Args:
        candidates: Optional list from get_raw_scan_candidates(). If provided,
                   skips TradingView fetch and validates this list directly.
        data_driven: If True, pass direction=None to generate_trading_signal and
                    only keep stocks where data confirms expected direction.
        timeout_seconds: Max seconds for scan (0 = no timeout).
        scan_start_override: Shared start time for timeout (e.g. from parent scan).

    Returns candidates with 3+ gates, progress log, and stats.
    """
    from ..tradingview_scanner import SCREENER_AVAILABLE, get_scanner, get_fallback_scanner
    from .signals import fetch_analysis_data, generate_trading_signal_impl as generate_trading_signal
    import time
    from datetime import datetime
    import pytz

    et = pytz.timezone("America/New_York")
    scan_start = scan_start_override if scan_start_override else time.time()
    timeout_hit = False
    progress_log = []
    progress_file = "/tmp/claude-scan-live-progress.txt"

    def log_progress(msg: str):
        logger.info(msg)
        progress_log.append(f"[{time.time() - scan_start:.0f}s] {msg}")
        # Write to file for live Telegram updates
        try:
            with open(progress_file, "w") as f:
                f.write(f"[{time.time() - scan_start:.0f}s] {msg}\n")
        except:
            pass

    # Step 1: Use provided candidates OR fetch from TradingView
    if candidates is not None and len(candidates) > 0:
        all_candidates = candidates
        scanner_source = "provided"
        raw_candidates_count = len(all_candidates)
        log_progress(f"📋 Using {raw_candidates_count} provided {direction} candidates (no fetch needed)")
    else:
        # Fetch from TradingView
        if not SCREENER_AVAILABLE:
            return {"error": "TradingView scanner not available"}

        try:
            scanner = get_scanner()
            scanner_source = "tradingview"
        except Exception as e:
            try:
                scanner = get_fallback_scanner()
                scanner_source = "finviz" if scanner else "none"
            except:
                return {"error": f"Scanner failed: {e}", "progress_log": progress_log}

        if not scanner:
            return {"error": "No scanner available", "progress_log": progress_log}

        log_progress(f"🔍 Fetching ALL {direction} candidates from {scanner_source}...")

        try:
            if direction == "LONG":
                all_candidates = scanner.scan_long_setups(
                    setup_type="all", market=market,
                    min_price=min_price, min_market_cap=min_market_cap, limit=max_scan
                )
            else:
                all_candidates = scanner.scan_short_setups(
                    setup_type="all", market=market,
                    min_price=min_price, min_market_cap=min_market_cap, limit=max_scan
                )
            raw_candidates_count = len(all_candidates)
            log_progress(f"   📋 Got {raw_candidates_count} raw {direction} candidates")
        except Exception as e:
            return {"error": f"Fetch failed: {e}", "progress_log": progress_log}

    if not all_candidates:
        return {
            "direction": direction,
            "scan_time": datetime.now(et).strftime("%Y-%m-%d %H:%M:%S %Z"),
            "scanner_source": scanner_source,
            "raw_candidates": 0,
            "db_matches": 0,
            "repeated": 0,
            "new_analyzed": 0,
            "scanned": 0,
            "five_gate_passed": 0,
            "three_of_five_gate_passed": 0,
            "returned": 0,
            "relaxed": False,
            "candidates": [],
            "rejection_reasons": {},
            "errors": [],
            "elapsed_seconds": round(time.time() - scan_start, 1),
            "progress_log": progress_log
        }

    # Step 2: Process in batches
    validated = []
    all_results = []  # Compact one-liner for EVERY company tested
    stocks_seen = set()
    rejection_reasons = {}
    errors = []

    num_batches = (len(all_candidates) + batch_size - 1) // batch_size
    log_progress(f"📦 Processing {raw_candidates_count} candidates in {num_batches} batches of {batch_size}...")

    # Step 2.5: Get recent predictions from DB to skip repeated tickers
    recent_predictions = _get_recent_predictions(direction, days=7)
    recent_tickers = set(recent_predictions.keys())
    if recent_tickers:
        log_progress(f"📦 Found {len(recent_tickers)} {direction} predictions in DB from last 7 days - will skip re-analysis")

    # Track repeated vs new
    repeated_count = 0

    for batch_num in range(num_batches):
        batch_start = batch_num * batch_size
        batch_end = min(batch_start + batch_size, len(all_candidates))
        batch = all_candidates[batch_start:batch_end]

        log_progress(f"")
        log_progress(f"━━━ BATCH {batch_num + 1}/{num_batches} ({batch_start + 1}-{batch_end} of {raw_candidates_count}) ━━━")

        for i, candidate in enumerate(batch):
            # Timeout check
            if timeout_seconds > 0 and (time.time() - scan_start) > timeout_seconds:
                log_progress(f"⏱️ {direction} scan timeout after {time.time() - scan_start:.0f}s. Returning partial results.")
                timeout_hit = True
                break

            # Accept both formats: {"symbol": "AAPL"} or just "AAPL"
            if isinstance(candidate, str):
                symbol = candidate
            else:
                symbol = candidate.get('symbol')
            if not symbol or symbol in stocks_seen:
                continue
            stocks_seen.add(symbol)

            global_idx = batch_start + i + 1

            # CHECK IF TICKER IS IN RECENT DB PREDICTIONS
            if symbol in recent_tickers:
                # REPEATED: Skip full analysis, use stored data
                stored = recent_predictions[symbol]
                repeated_count += 1
                log_progress(f"[{direction} {global_idx}/{raw_candidates_count}] ♻️ REPEATED: {symbol} (from DB)")

                gates_passed = stored['gates_passed'] or 0
                if gates_passed >= 3:
                    validated.append({
                        'symbol': symbol,
                        'direction': direction,
                        'is_repeated': True,
                        'stored_at': stored['stored_at'],
                        'price': stored['entry_price'],
                        'signal': stored['signal'],
                        'confidence': stored['confidence'],
                        'gates_passed': gates_passed,
                        'gate_status': stored['gate_status'],
                        'trading_plan': {
                            'entry_price': stored['entry_price'],
                            'stop_price': stored['stop_price'],
                            'target_1': stored['target_1'],
                            'target_2': stored['target_2'],
                        },
                        'catalyst_analysis': {
                            'catalyst_direction': stored['catalyst_direction'],
                            'catalyst_strength': stored['catalyst_strength'],
                        },
                        'freshness_analysis': {
                            'dalio_ratio': stored['dalio_ratio'],
                            'dalio_interpretation': stored['dalio_interpretation'],
                        },
                        'brooks_analysis': {
                            'probability': stored['brooks_probability'],
                            'pattern': stored['brooks_pattern'],
                            'trap_risk': stored['trap_risk'],
                        },
                        'quality_analysis': {
                            'quality_score': stored['quality_score'],
                            'quality_grade': stored['quality_grade'],
                            'f_score': stored['f_score'],
                            'z_score': stored['z_score'],
                        },
                    })

                # Add to results with REPEATED marker
                gs = stored['gate_status']
                c = (gs.get('catalyst', '?') or '?')[0]
                f = (gs.get('freshness', '?') or '?')[0]
                b = (gs.get('brooks', '?') or '?')[0]
                q = (gs.get('quality', '?') or '?')[0]
                o = (gs.get('options_tradability', 'S') or 'S')[0]  # Stored predictions may not have Gate 5
                gates_str = f"{gates_passed}/5" if o != 'S' else f"{gates_passed}/4"
                all_results.append(f"♻️ {symbol}: {gates_str} [C:{c} F:{f} B:{b} Q:{q} O:{o}] (REPEATED)")

                continue  # Skip to next candidate - no need to re-analyze

            # NEW TICKER: Run full analysis
            log_progress(f"[{direction} {global_idx}/{raw_candidates_count}] 🔍 Checking {symbol}...")

            try:
                # Fetch all analysis data ONCE
                cached_data = fetch_analysis_data(symbol)

                # Pass cached_data to avoid redundant API calls
                sig_direction = None if data_driven else direction
                signal = generate_trading_signal(ticker=symbol, direction=sig_direction, report_type="scanner", cached_data=cached_data)
                gate_status = signal.get('gate_status', {})
                core_gates_passed = sum(1 for g in ['catalyst', 'freshness', 'brooks', 'quality'] if gate_status.get(g) == "PASS")
                all_gates_passed = sum(1 for g in gate_status.values() if g == "PASS")
                signal_direction = signal.get('direction')

                # In data-driven mode, filter by confirmed direction
                if data_driven:
                    if signal_direction is None:
                        log_progress(f"   ⏸️ {symbol}: NO_TRADE - indicators neutral, no clear direction")
                        continue
                    opposite = "SHORT" if direction == "LONG" else "LONG"
                    if signal_direction == opposite:
                        log_progress(f"   🔄 {symbol}: Data indicates {opposite}, not {direction} | skipping")
                        continue

                # Compact one-liner for this company (now with Gate 5)
                price = signal.get('current_price') or (candidate.get('price') if isinstance(candidate, dict) else None)
                c = gate_status.get('catalyst', '?')[0]  # P or F
                f = gate_status.get('freshness', '?')[0]
                b = gate_status.get('brooks', '?')[0]
                q = gate_status.get('quality', '?')[0]
                o = gate_status.get('options_tradability', 'S')[0]  # P=PASS, F=FAIL, S=SKIP, E=ERROR
                gates_str = f"{all_gates_passed}/5" if o != 'S' else f"{core_gates_passed}/4"
                result_line = f"{symbol}: {gates_str} [C:{c} F:{f} B:{b} Q:{q} O:{o}]"
                all_results.append(result_line)

                # Extract Gate 5 + options info for display
                gate_5_result = signal.get('gate_5_analysis')
                options_decision = signal.get('options_vs_stock_decision')
                gates_passed = all_gates_passed if gate_5_result else core_gates_passed

                if gates_passed >= 3:
                    # Check for direction conflict
                    data_dir = signal.get('data_direction', 'NO_CONSENSUS')
                    direction_conflict = data_dir != "NO_CONSENSUS" and data_dir != direction

                    # Create options summary for display
                    options_summary = _create_options_summary(gate_5_result, options_decision, signal.get('vehicle'))

                    validated.append({
                        'symbol': symbol,
                        'direction': direction,
                        'data_direction': data_dir,  # NEW: What the data actually says
                        'direction_conflict': direction_conflict,  # NEW: True if scanner direction != data direction
                        'direction_votes': signal.get('direction_votes', {}),  # NEW: How each tool voted
                        'price': price,
                        'signal': signal.get('signal'),
                        'confidence': signal.get('confidence', 0),
                        'gates_passed': gates_passed,
                        'core_gates_passed': core_gates_passed,
                        'gate_status': gate_status,
                        'vehicle': signal.get('vehicle', 'STOCK'),  # NEW: OPTIONS or STOCK
                        'options_summary': options_summary,  # NEW: Quick options display
                        'gate_5_analysis': gate_5_result,  # NEW: Full Gate 5 data
                        'options_vs_stock_decision': options_decision,  # NEW: Decision framework result
                        'trading_plan': signal.get('trading_plan'),
                        'catalyst_analysis': signal.get('catalyst_analysis'),
                        'freshness_analysis': signal.get('freshness_analysis'),
                        'brooks_analysis': signal.get('brooks_analysis'),
                        'quality_analysis': signal.get('quality_analysis'),
                    })
                    conflict_warning = " ⚠️ DIRECTION CONFLICT" if direction_conflict else ""
                    log_progress(f"   ✅ {symbol}: {gates_passed}/5 gates | {gate_status}{conflict_warning}")
                else:
                    log_progress(f"   ❌ {symbol}: {gates_passed}/5 gates | {gate_status}")
                    for gate, val in gate_status.items():
                        if val != "PASS":
                            rejection_reasons[gate] = rejection_reasons.get(gate, 0) + 1

            except Exception as e:
                errors.append(f"{symbol}: {str(e)[:50]}")
                log_progress(f"   ⚠️ {symbol} error: {str(e)[:50]}")

        # After each batch, show running totals
        four_so_far = len([x for x in validated if x['gates_passed'] == 4])
        three_so_far = len([x for x in validated if x['gates_passed'] == 3])
        log_progress(f"   📊 Batch {batch_num + 1} complete: {four_so_far} @5/5, {three_so_far} @3/5 so far")

        if timeout_hit:
            break

    # Step 3: Compile results from all batches
    five_gates = [x for x in validated if x['gates_passed'] >= 4]
    three_gates = [x for x in validated if x['gates_passed'] == 3]

    five_gates.sort(key=lambda x: x.get('confidence', 0), reverse=True)
    three_gates.sort(key=lambda x: x.get('confidence', 0), reverse=True)

    # Return ALL 5/5 gate passers, fill with 3/5 if less than min_results (5)
    min_results = 5
    final = five_gates[:]  # ALL 5/5 gate passers
    relaxed = False
    if len(final) < min_results and three_gates:
        remaining = min_results - len(final)
        final.extend(three_gates[:remaining])
        relaxed = True

    for i, a in enumerate(final):
        a['rank'] = i + 1

    elapsed = time.time() - scan_start
    log_progress(f"")
    log_progress(f"═══════════════════════════════════════════════════════════")
    log_progress(f"📊 {direction} SCAN COMPLETE")
    log_progress(f"   Raw candidates:  {raw_candidates_count}")
    log_progress(f"   Scanned:         {len(stocks_seen)}")
    log_progress(f"   5/5 gates:       {len(five_gates)}")
    log_progress(f"   3/5 gates:       {len(three_gates)}")
    log_progress(f"   Returned:        {len(final)}")
    log_progress(f"   Time:            {elapsed:.0f}s")
    log_progress(f"═══════════════════════════════════════════════════════════")

    return {
        "direction": direction,
        "scan_time": datetime.now(et).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "scanner_source": scanner_source,
        "raw_candidates": raw_candidates_count,
        "db_matches": len(recent_tickers),
        "repeated": repeated_count,
        "new_analyzed": len(stocks_seen) - repeated_count,
        "scanned": len(stocks_seen),
        "five_gate_passed": len(five_gates),
        "three_of_five_gate_passed": len(three_gates),
        "returned": len(final),
        "relaxed": relaxed,
        "all_results": all_results,
        "candidates": final,
        "rejection_reasons": rejection_reasons,
        "errors": errors[:10],
        "elapsed_seconds": round(elapsed, 1),
        "timeout_hit": timeout_hit,
        "progress_log": progress_log
    }


def register_tools(mcp):
    """Register scanning tools with MCP server."""
    from ..tradingview_scanner import SCREENER_AVAILABLE, get_scanner, get_fallback_scanner
    from .signals import fetch_analysis_data, generate_trading_signal_impl as generate_trading_signal

    @mcp.tool()
    def scan_long_candidates(
        candidates: list = None,
        market: Literal["america", "canada", "both"] = "both",
        min_price: float = 2.0,
        min_market_cap: int = 1_000_000_000,
        max_scan: int = 500,
        batch_size: int = 20,
        top_n: int = 5
    ) -> dict[str, Any]:
        """
        Scan for LONG candidates only. Call this first, then scan_short_candidates.

        RECOMMENDED WORKFLOW:
            1. get_raw_scan_candidates(direction="LONG") - Get raw TradingView list
            2. scan_long_candidates(candidates=<output from step 1>) - Validate with 5-gate system
            3. get_raw_scan_candidates(direction="SHORT") - Get raw TradingView list
            4. scan_short_candidates(candidates=<output from step 3>) - Validate SHORT direction

        Process:
            1. Fetch ALL raw candidates from TradingView (up to max_scan, default 500)
            2. Process in batches of batch_size (default 50)
            3. Validate each batch through 5-gate system
            4. Compile all validated results across all batches
            5. Return top N from combined pool

        Returns top N LONG candidates that pass 3+/4 core gates.
        Includes full progress log showing each stock checked.

        Args:
            candidates: Optional list from get_raw_scan_candidates(direction="LONG").
                       If provided, validates this list directly (no fetch needed).
                       If not provided, fetches from TradingView automatically.
                       Accepts: ["AAPL", "TSLA"] or [{"symbol": "AAPL"}, ...] - only symbol is used.

        5-Gate Validation:
            GATE 1 (CATALYST): Earnings proximity, insider buying, analyst upgrades
            GATE 2 (FRESHNESS): Enhanced with Dalio Economic Machine (6 checks, need 5/6):
                - CVD alignment, Exhaustion < 50, Fresh direction
                - Dalio Ratio >= 1.0, Dollar Flow positive, Sustainability >= 50
            GATE 3 (BROOKS): Probability >= 55%, no HIGH trap risk
            GATE 4 (QUALITY): Quality score >= 50
            GATE 5 (OPTIONS TRADABILITY): Liquidity, IV environment, earnings, expected moves
                - Determines OPTIONS vs STOCK vehicle

        Returns:
            - raw_candidates: Total fetched from TradingView
            - scanned: Unique stocks validated
            - five_gate_passed: Stocks passing 5/5 core gates
            - three_of_five_gate_passed: Stocks passing 3/5 core gates
            - returned: Top N candidates returned
            - candidates: List of validated candidates with full analysis + options recommendations
            - progress_log: Detailed batch-by-batch progress
        """
        return _scan_one_direction("LONG", market, min_price, min_market_cap, max_scan, top_n, batch_size, candidates)


    @mcp.tool()
    def scan_short_candidates(
        candidates: list = None,
        market: Literal["america", "canada", "both"] = "both",
        min_price: float = 2.0,
        min_market_cap: int = 1_000_000_000,
        max_scan: int = 500,
        batch_size: int = 20,
        top_n: int = 5
    ) -> dict[str, Any]:
        """
        Scan for SHORT candidates only. Call after scan_long_candidates.

        RECOMMENDED WORKFLOW:
            1. get_raw_scan_candidates(direction="LONG") - Get raw TradingView list
            2. scan_long_candidates(candidates=<output from step 1>) - Validate with 5-gate system
            3. get_raw_scan_candidates(direction="SHORT") - Get raw TradingView list
            4. scan_short_candidates(candidates=<output from step 3>) - Validate SHORT direction

        Process:
            1. Use provided candidates OR fetch from TradingView (up to max_scan, default 500)
            2. Process in batches of batch_size (default 50)
            3. Validate each batch through 5-gate system
            4. Compile all validated results across all batches
            5. Return top N from combined pool

        Returns top N SHORT candidates that pass 3+/4 core gates.
        Includes full progress log showing each stock checked.

        Args:
            candidates: Optional list from get_raw_scan_candidates(direction="SHORT").
                       If provided, validates this list directly (no fetch needed).
                       If not provided, fetches from TradingView automatically.
                       Accepts: ["AAPL", "TSLA"] or [{"symbol": "AAPL"}, ...] - only symbol is used.

        5-Gate Validation:
            GATE 1 (CATALYST): Earnings proximity, insider buying, analyst upgrades
            GATE 2 (FRESHNESS): Enhanced with Dalio Economic Machine (6 checks, need 5/6):
                - CVD alignment, Exhaustion < 50, Fresh direction
                - Dalio Ratio <= 1.0, Dollar Flow negative, Sustainability >= 50
            GATE 3 (BROOKS): Probability >= 55%, no HIGH trap risk
            GATE 4 (QUALITY): Quality score >= 50
            GATE 5 (OPTIONS TRADABILITY): Liquidity, IV environment, earnings, expected moves
                - Determines OPTIONS vs STOCK vehicle

        Returns:
            - raw_candidates: Total fetched from TradingView
            - scanned: Unique stocks validated
            - five_gate_passed: Stocks passing 5/5 core gates
            - three_of_five_gate_passed: Stocks passing 3/5 core gates
            - returned: Top N candidates returned
            - candidates: List of validated candidates with full analysis + options recommendations
            - progress_log: Detailed batch-by-batch progress
        """
        return _scan_one_direction("SHORT", market, min_price, min_market_cap, max_scan, top_n, batch_size, candidates)


    @mcp.tool()
    def get_raw_scan_candidates(
        direction: Literal["LONG", "SHORT"] = "LONG",
        market: Literal["america", "canada", "both"] = "both",
        min_price: float = 2.0,
        min_market_cap: int = 1_000_000_000,
        limit: int = 500
    ) -> dict[str, Any]:
        """
        Fetch RAW candidates from TradingView WITHOUT any validation.

        Use this to verify the scanner is returning candidates before running validation.
        Returns the full list of candidates as-is from TradingView's screener API.

        NO validation is performed - this just shows what TradingView returns.

        Args:
            direction: LONG or SHORT setups to scan for
            market: "america", "canada", or "both"
            min_price: Minimum stock price (default: $2)
            min_market_cap: Minimum market cap (default: $1B)
            limit: Maximum candidates to fetch (default: 500)

        Returns:
            Dictionary with:
            - direction: LONG or SHORT
            - scanner_source: "tradingview" or "finviz"
            - total_candidates: Number of candidates fetched
            - candidates: List of raw candidate data (symbol, price, change%, volume, market_cap, RSI, ADX, etc.)
        """
        import time
        from datetime import datetime
        import pytz

        if not SCREENER_AVAILABLE:
            return {"error": "TradingView scanner not available. Install: pip install tradingview-screener"}

        et = pytz.timezone("America/New_York")
        scan_start = time.time()

        # Get scanner
        try:
            scanner = get_scanner()
            scanner_source = "tradingview"
        except Exception as e:
            try:
                scanner = get_fallback_scanner()
                scanner_source = "finviz" if scanner else "none"
            except:
                return {"error": f"Scanner failed: {e}"}

        if not scanner:
            return {"error": "No scanner available"}

        # Fetch raw candidates
        try:
            if direction == "LONG":
                raw_candidates = scanner.scan_long_setups(
                    setup_type="all", market=market,
                    min_price=min_price, min_market_cap=min_market_cap, limit=limit
                )
            else:
                raw_candidates = scanner.scan_short_setups(
                    setup_type="all", market=market,
                    min_price=min_price, min_market_cap=min_market_cap, limit=limit
                )
        except Exception as e:
            return {"error": f"Scan failed: {e}"}

        elapsed = time.time() - scan_start

        # Format candidates for output (show key metrics)
        formatted = []
        for c in raw_candidates:
            formatted.append({
                "symbol": c.get("symbol"),
                "price": c.get("price"),
                "change_pct": c.get("change_pct"),
                "volume": c.get("volume"),
                "market_cap": c.get("market_cap"),
                "rsi": c.get("rsi"),
                "adx": c.get("adx"),
                "macd": c.get("macd"),
                "macd_signal": c.get("macd_signal"),
                "setup_type": c.get("setup_type"),
                "rel_volume": c.get("rel_volume"),
                "perf_3m": c.get("perf_3m"),
                "perf_1m": c.get("perf_1m"),
            })

        return {
            "direction": direction,
            "scan_time": datetime.now(et).strftime("%Y-%m-%d %H:%M:%S %Z"),
            "scanner_source": scanner_source,
            "market": market,
            "filters": {
                "min_price": min_price,
                "min_market_cap": min_market_cap,
                "limit": limit
            },
            "total_candidates": len(formatted),
            "elapsed_seconds": round(elapsed, 2),
            "candidates": formatted,
            "note": "This is RAW data from TradingView. NO validation performed. Use scan_long_candidates/scan_short_candidates for validated results."
        }


    @mcp.tool()
    def scan_market_opportunities(
        market: Literal["america", "canada", "both"] = "both",
        min_price: float = 2.0,
        min_market_cap: int = 1_000_000_000,
        top_n: int = 5,
        include_deep_analysis: bool = True,
        require_5_gates: bool = True,
        batch_size: int = 20,
        max_scan: int = 500
    ) -> dict[str, Any]:
        """
        Scan US and Canadian markets for HIGH-QUALITY trading opportunities.

        NEW: Scans in batches of 20 stocks and runs FULL 5-gate validation
        on each candidate. Only returns stocks that pass ALL 4 gates.

        AVAILABLE SCANNER TOOLS (use in this order):
            1. get_raw_scan_candidates() - Raw TradingView list (NO validation, fast)
               Use to verify scanner is returning candidates before validation.
            2. scan_long_candidates() - LONG only with 5-gate validation
            3. scan_short_candidates() - SHORT only with 5-gate validation
            4. scan_market_opportunities() - Full scan (LONG + SHORT) with validation

        4-Gate Validation System:
            GATE 1 (CATALYST): Earnings proximity, insider buying, analyst upgrades
            GATE 2 (FRESHNESS): Enhanced with Dalio Economic Machine (6 checks, need 5/6):
                - CVD alignment
                - Exhaustion < 50
                - Fresh direction
                - Dalio Ratio aligned (>1.0 for LONG, <1.0 for SHORT)
                - Dollar Flow aligned (positive for LONG, negative for SHORT)
                - Sustainability >= 50
            GATE 3 (BROOKS): Probability >= 55%, no HIGH trap risk, direction aligned
            GATE 4 (QUALITY): Quality score >= 50

        Scan Process:
            1. Fetch 200 stocks per batch from TradingView
            2. Run generate_trading_signal() on each for FULL 5-gate validation
            3. Keep only stocks passing 5/5 gates
            4. Continue until we have 5 LONG + 5 SHORT or hit 1000 scanned
            5. Rank by confidence score

        Args:
            market: Market to scan - "america", "canada", or "both"
            min_price: Minimum stock price (default: $2)
            min_market_cap: Minimum market cap (default: $1B)
            top_n: Number of candidates per direction (default: 5)
            include_deep_analysis: Run full analysis pipeline (default: True)
            require_5_gates: Only return 5/5 gate passers (default: True)
            batch_size: Stocks to scan per batch (default: 200)
            max_scan: Maximum stocks to scan before giving up (default: 1000)

        Returns:
            Dictionary with:
            - scan_time: Timestamp of scan
            - long_candidates: Top N LONG with 5/5 gates passed
            - short_candidates: Top N SHORT with 5/5 gates passed
            - stats: Scanning statistics (total scanned, pass rates)
            - report: Formatted text report
        """
        if not SCREENER_AVAILABLE:
            raise ValueError(
                "TradingView scanner not available. Install with: pip install tradingview-screener"
            )

        from datetime import datetime
        import pytz
        import hashlib

        # === Check Scan Cache ===
        filters_hash = hashlib.md5(
            f"{min_price}_{min_market_cap}_{top_n}_{require_5_gates}_{batch_size}".encode()
        ).hexdigest()[:8]

        cached_result = _get_scan_cache(market, filters_hash)
        if cached_result is not None:
            logger.info(f"Returning cached scan results for {market}")
            return cached_result

        # === Detect Market Regime ===
        market_regime = detect_market_regime()
        logger.info(f"📊 Market Regime: {market_regime['regime']} | SPY Vol: {market_regime['volatility']}%")

        try:
            import time

            et = pytz.timezone("America/New_York")
            scan_start_time = time.time()
            MAX_SCAN_SECONDS = 900  # 15 minute timeout for entire scan

            # === Delegate to _scan_one_direction for both LONG and SHORT ===
            long_result = _scan_one_direction(
                direction="LONG", market=market, min_price=min_price,
                min_market_cap=min_market_cap, max_scan=max_scan, top_n=top_n,
                batch_size=batch_size, data_driven=True,
                timeout_seconds=MAX_SCAN_SECONDS, scan_start_override=scan_start_time,
            )

            short_result = _scan_one_direction(
                direction="SHORT", market=market, min_price=min_price,
                min_market_cap=min_market_cap, max_scan=max_scan, top_n=top_n,
                batch_size=batch_size, data_driven=True,
                timeout_seconds=MAX_SCAN_SECONDS, scan_start_override=scan_start_time,
            )

            # Extract results
            final_long = long_result.get("candidates", [])
            final_short = short_result.get("candidates", [])
            scanner_source = long_result.get("scanner_source", "unknown")
            timeout_occurred = long_result.get("timeout_hit", False) or short_result.get("timeout_hit", False)

            total_scanned_long = long_result.get("scanned", 0)
            total_scanned_short = short_result.get("scanned", 0)
            stats_5gate_long = long_result.get("five_gate_passed", 0)
            stats_3gate_long = long_result.get("three_of_five_gate_passed", 0)
            stats_5gate_short = short_result.get("five_gate_passed", 0)
            stats_3gate_short = short_result.get("three_of_five_gate_passed", 0)
            gate_relaxed_long = long_result.get("relaxed", False)
            gate_relaxed_short = short_result.get("relaxed", False)

            rejection_reasons = {
                "LONG": long_result.get("rejection_reasons", {}),
                "SHORT": short_result.get("rejection_reasons", {}),
            }
            scan_errors = long_result.get("errors", []) + short_result.get("errors", [])
            progress_log = long_result.get("progress_log", []) + short_result.get("progress_log", [])

            total_elapsed = time.time() - scan_start_time

            # Generate text report for validated results
            report_lines = [
                "=" * 65,
                f"    SMART SCAN RESULTS - {datetime.now(et).strftime('%Y-%m-%d %H:%M %Z')}",
                "=" * 65,
                f"Markets: {market.upper()} | Filters: Price>${min_price}, MCap>${min_market_cap:,}",
                f"Max Scan: {max_scan} | Elapsed: {total_elapsed:.0f}s",
                "",
                "📡 SCANNER TOOLS:",
                "   • get_raw_scan_candidates() - Raw list (no validation)",
                "   • scan_long_candidates()    - LONG with 5-gate validation",
                "   • scan_short_candidates()   - SHORT with 5-gate validation",
                "",
                "=" * 65,
                "                    📊 SCAN STATISTICS",
                "=" * 65,
                f"   LONG:  Scanned {total_scanned_long} stocks",
                f"          → {stats_5gate_long} passed 5/5 gates ({stats_5gate_long/max(total_scanned_long,1)*100:.1f}%)",
                f"          → {stats_3gate_long} passed 3/5 gates ({stats_3gate_long/max(total_scanned_long,1)*100:.1f}%)",
                f"          → Returning {len(final_long)} candidates" + (" (relaxed to 3/5)" if gate_relaxed_long else ""),
                "",
                f"   SHORT: Scanned {total_scanned_short} stocks",
                f"          → {stats_5gate_short} passed 5/5 gates ({stats_5gate_short/max(total_scanned_short,1)*100:.1f}%)",
                f"          → {stats_3gate_short} passed 3/5 gates ({stats_3gate_short/max(total_scanned_short,1)*100:.1f}%)",
                f"          → Returning {len(final_short)} candidates" + (" (relaxed to 3/5)" if gate_relaxed_short else ""),
                "",
                "   Gate 1: CATALYST (earnings/insider/upgrades/unusual options)",
                "   Gate 2: FRESHNESS (CVD aligned, exhaustion < 50)",
                "   Gate 3: BROOKS (probability >= 55%, no HIGH trap)",
                "   Gate 4: QUALITY (score >= 50)",
                "",
                "=" * 65,
                "              TOP LONG CANDIDATES",
                "=" * 65,
            ]

            for a in final_long:
                brooks = a.get('brooks_analysis', {})
                trading_plan = a.get('trading_plan', {})
                gates = a.get('gates_passed', 0)
                gate_emoji = "✅" if gates == 4 else "⚠️"
                report_lines.extend([
                    "",
                    f"#{a.get('rank')} {a['symbol']} - ${a.get('price', 0):.2f} [{gates}/4 {gate_emoji}]",
                    f"   Signal: {a.get('signal')} | Confidence: {a.get('confidence')}%",
                    f"   Gate Status: {a.get('gate_status', {})}",
                    f"   Brooks: {brooks.get('pattern', 'N/A')} | Prob: {brooks.get('probability', 0)}% | Trap: {brooks.get('trap_risk', 'N/A')}",
                    f"   Entry: ${trading_plan.get('entry_price', 0):.2f} | Stop: ${trading_plan.get('stop_loss', {}).get('price', 0):.2f} | Target: ${trading_plan.get('target_1', {}).get('price', 0):.2f}",
                ])

            if not final_long:
                report_lines.append("\n   ❌ No LONG candidates passed 3+/4 gates in this scan.")

            report_lines.extend([
                "",
                "=" * 65,
                "              TOP SHORT CANDIDATES",
                "=" * 65,
            ])

            for a in final_short:
                brooks = a.get('brooks_analysis', {})
                trading_plan = a.get('trading_plan', {})
                gates = a.get('gates_passed', 0)
                gate_emoji = "✅" if gates == 4 else "⚠️"
                report_lines.extend([
                    "",
                    f"#{a.get('rank')} {a['symbol']} - ${a.get('price', 0):.2f} [{gates}/4 {gate_emoji}]",
                    f"   Signal: {a.get('signal')} | Confidence: {a.get('confidence')}%",
                    f"   Gate Status: {a.get('gate_status', {})}",
                    f"   Brooks: {brooks.get('pattern', 'N/A')} | Prob: {brooks.get('probability', 0)}% | Trap: {brooks.get('trap_risk', 'N/A')}",
                    f"   Entry: ${trading_plan.get('entry_price', 0):.2f} | Stop: ${trading_plan.get('stop_loss', {}).get('price', 0):.2f} | Target: ${trading_plan.get('target_1', {}).get('price', 0):.2f}",
                ])

            if not final_short:
                report_lines.append("\n   ❌ No SHORT candidates passed 3+/4 gates in this scan.")

            # Add rejection stats to report
            report_lines.extend([
                "",
                "=" * 65,
                "                     SCAN DIAGNOSTICS",
                "=" * 65,
                f"⏱️  Total Time: {total_elapsed:.0f}s | Timeout: {'YES' if timeout_occurred else 'NO'}",
                f"📡 Scanner: {scanner_source.upper()}",
                "",
            ])

            # Show why stocks are failing gates
            if rejection_reasons["LONG"]:
                report_lines.append("❌ LONG Rejection Reasons:")
                for gate, count in sorted(rejection_reasons["LONG"].items(), key=lambda x: x[1], reverse=True):
                    report_lines.append(f"   {gate}: {count} stocks failed")

            if rejection_reasons["SHORT"]:
                report_lines.append("❌ SHORT Rejection Reasons:")
                for gate, count in sorted(rejection_reasons["SHORT"].items(), key=lambda x: x[1], reverse=True):
                    report_lines.append(f"   {gate}: {count} stocks failed")

            if scan_errors:
                report_lines.append(f"\n⚠️  Errors ({len(scan_errors)}):")
                for err in scan_errors[:5]:  # Show first 5 errors
                    report_lines.append(f"   {err}")
                if len(scan_errors) > 5:
                    report_lines.append(f"   ... and {len(scan_errors) - 5} more")

            report_lines.append("")

            # Add progress log to report
            report_lines.extend([
                "=" * 65,
                "                     SCAN PROGRESS LOG",
                "=" * 65,
            ])
            for log_entry in progress_log:
                report_lines.append(log_entry)
            report_lines.append("")

            # Convert numpy types to native Python types for JSON serialization
            result = convert_numpy_types({
                "scan_time": datetime.now(et).strftime("%Y-%m-%d %H:%M:%S %Z"),
                "market_regime": market_regime,
                "scanner_source": scanner_source,
                "filters": {
                    "market": market,
                    "min_price": min_price,
                    "min_market_cap": f"${min_market_cap:,}",
                    "max_scan": max_scan
                },
                "stats": {
                    "long_scanned": total_scanned_long,
                    "long_4gate_passed": stats_5gate_long,
                    "long_3gate_passed": stats_3gate_long,
                    "long_returned": len(final_long),
                    "long_relaxed": gate_relaxed_long,
                    "short_scanned": total_scanned_short,
                    "short_4gate_passed": stats_5gate_short,
                    "short_3gate_passed": stats_3gate_short,
                    "short_returned": len(final_short),
                    "short_relaxed": gate_relaxed_short,
                    "elapsed_seconds": round(total_elapsed, 1),
                    "timeout_occurred": timeout_occurred,
                    "rejection_reasons": rejection_reasons,
                    "errors_count": len(scan_errors)
                },
                "long_candidates": final_long,
                "short_candidates": final_short,
                "errors": scan_errors[:10] if scan_errors else [],
                "progress_log": progress_log,
                "report": "\n".join(report_lines)
            })

            # === PROPOSAL 5: Cache the result ===
            _set_scan_cache(market, filters_hash, result)

            # === AUTO-TRACK PICKS FOR VALIDATION ===
            try:
                _auto_track_picks(result, scanner_source)
            except Exception as track_error:
                logger.warning(f"Auto-tracking failed: {track_error}")

            return result

        except Exception as e:
            logger.error(f"Error in scan_market_opportunities: {e}")
            import traceback
            traceback.print_exc()
            raise ValueError(f"Market scan failed: {str(e)}")


    @mcp.tool()
    def scan_stocks_by_setup(
        setup_type: Literal[
            # Long setups
            "momentum_long", "consolidation_breakout", "golden_cross", "macd_bullish", "volume_breakout", "support_bounce",
            # Short setups
            "momentum_short", "consolidation_breakdown", "death_cross", "macd_bearish", "breakdown", "resistance_rejection"
        ],
        market: Literal["america", "canada", "both"] = "both",
        min_price: float = 2.0,
        min_market_cap: int = 1_000_000_000,
        limit: int = 10
    ) -> dict[str, Any]:
        """
        Scan for stocks matching a specific technical setup pattern.

        LONG Setups (Inflection Point Detection):
            - momentum_long: ADX 20-40, RSI 40-65, MACD bullish (RECOMMENDED)
            - consolidation_breakout: Breaking 20-day high with volume 1.5-4x (RECOMMENDED)
            - golden_cross: SMA20 > SMA50, price above both
            - macd_bullish: MACD above signal line
            - volume_breakout: High volume 1.5-4x, positive momentum
            - support_bounce: Price near SMA50, RSI rising

        SHORT Setups (Inflection Point Detection):
            - momentum_short: ADX 20-40, RSI 35-60, MACD bearish (RECOMMENDED)
            - consolidation_breakdown: Breaking 20-day low with volume 1.5-4x (RECOMMENDED)
            - death_cross: SMA20 < SMA50, price below both
            - macd_bearish: MACD below signal line
            - breakdown: Price below SMA50, high volume 1.5-4x, negative
            - resistance_rejection: Near 52w high, negative change

        Note: All setups now include Tier 1/4 filters by default:
            - Tier 1: ADX 20-40, RSI positioning, EMA20 <5%
            - Tier 4: Rejects >50% 3mo moves, ATR <2%, 52w proximity

        Args:
            setup_type: The technical setup pattern to scan for
            market: Market to scan ("america", "canada", "both")
            min_price: Minimum stock price
            min_market_cap: Minimum market capitalization
            limit: Maximum results to return

        Returns:
            Dictionary with matching candidates and their metrics
        """
        if not SCREENER_AVAILABLE:
            raise ValueError(
                "TradingView scanner not available. Install with: pip install tradingview-screener"
            )

        from datetime import datetime
        import pytz

        # Determine direction from setup type
        long_setups = ["momentum_long", "consolidation_breakout", "golden_cross", "macd_bullish", "volume_breakout", "support_bounce"]
        direction = "LONG" if setup_type in long_setups else "SHORT"

        try:
            # === PROPOSAL 1: TradingView → Finviz Fallback Chain ===
            scanner = None
            scanner_source = "unknown"

            try:
                scanner = get_scanner()
                scanner_source = "tradingview"
            except Exception as tv_error:
                logger.warning(f"TradingView failed: {tv_error}, trying Finviz fallback")
                scanner = get_fallback_scanner()
                if scanner:
                    scanner_source = "finviz"
                else:
                    raise ValueError("No scanner available")

            et = pytz.timezone("America/New_York")

            if direction == "LONG":
                candidates = scanner.scan_long_setups(
                    setup_type=setup_type,
                    market=market,
                    min_price=min_price,
                    min_market_cap=min_market_cap,
                    limit=limit
                )
            else:
                candidates = scanner.scan_short_setups(
                    setup_type=setup_type,
                    market=market,
                    min_price=min_price,
                    min_market_cap=min_market_cap,
                    limit=limit
                )

            logger.info(f"Found {len(candidates)} candidates for {setup_type} from {scanner_source}")

            # Setup type display names
            setup_names = {
                # Long setups - Inflection Point Detection
                "momentum_long": "Momentum Long (Inflection)",
                "consolidation_breakout": "Consolidation Breakout",
                "golden_cross": "Golden Cross",
                "macd_bullish": "MACD Bullish",
                "volume_breakout": "Volume Breakout",
                "support_bounce": "Support Bounce",
                # Short setups - Inflection Point Detection
                "momentum_short": "Momentum Short (Inflection)",
                "consolidation_breakdown": "Consolidation Breakdown",
                "death_cross": "Death Cross",
                "macd_bearish": "MACD Bearish",
                "breakdown": "Breakdown",
                "resistance_rejection": "Resistance Rejection"
            }

            # Convert numpy types to native Python types for JSON serialization
            return convert_numpy_types({
                "scan_time": datetime.now(et).strftime("%Y-%m-%d %H:%M:%S %Z"),
                "setup_type": setup_names.get(setup_type, setup_type),
                "direction": direction,
                "filters": {
                    "market": market,
                    "min_price": min_price,
                    "min_market_cap": f"${min_market_cap:,}"
                },
                "candidates": [
                    {
                        "rank": i + 1,
                        "symbol": c['symbol'],
                        "price": c['price'],
                        "change_pct": c['change_pct'],
                        "signal_strength": c['signal_strength'],
                        "recommendation": c['recommendation'],
                        "market": c['market'],
                        "metrics": c['metrics']
                    }
                    for i, c in enumerate(candidates)
                ],
                "total_found": len(candidates)
            })

        except Exception as e:
            logger.error(f"Error in scan_stocks_by_setup: {e}")
            raise ValueError(f"Setup scan failed: {str(e)}")



