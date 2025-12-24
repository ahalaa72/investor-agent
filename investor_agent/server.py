from dotenv import load_dotenv
load_dotenv()
import os
#print("KEY:", os.getenv("ALPACA_API_KEY"))
#print("SECRET:", os.getenv("ALPACA_API_SECRET"))
import datetime
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from io import StringIO
from pathlib import Path
from typing import Literal, Any

import hishel
import httpx
import numpy as np
import pandas as pd
import yfinance as yf
from mcp.server.fastmcp import FastMCP


def convert_numpy_types(obj):
    """Recursively convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        if np.isnan(obj):
            return None
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return convert_numpy_types(obj.tolist())
    elif hasattr(obj, 'item'):  # For other numpy scalar types
        return obj.item()
    return obj
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, after_log
from yfinance.exceptions import YFRateLimitError

mcp = FastMCP("Investor-Agent", dependencies=["yfinance", "pandas", "pytrends"])

# Configure pandas
pd.set_option('future.no_silent_downcasting', True)

# Check TA-Lib availability
try:
    import talib  # type: ignore
    _ta_available = True
except ImportError:
    _ta_available = False

# Import Questrade API (now mandatory)
from .questrade import get_questrade_client, QuestradeClient

# Import ML modules for institutional-grade analysis
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
from .backtesting import (
    SimilarityEngine,
    generate_similarity_report
)

# Import TradingView scanner with Finviz fallback (optional dependencies)
try:
    from .tradingview_scanner import (
        TradingViewScanner, get_scanner, SCREENER_AVAILABLE,
        FinvizFallbackScanner, get_fallback_scanner, get_scanner_with_fallback,
        FINVIZ_AVAILABLE
    )
except ImportError:
    SCREENER_AVAILABLE = False
    FINVIZ_AVAILABLE = False

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)

# Minimal HTTP Headers - only essential ones
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Unified retry decorator for API calls (yfinance and HTTP)
def api_retry(func):
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2.0, min=2.0, max=30.0),
        retry=retry_if_exception(lambda e:
            isinstance(e, YFRateLimitError) or
            (hasattr(e, 'status_code') and getattr(e, 'status_code', 0) >= 500) or
            any(term in str(e).lower() for term in [
                "rate limit", "too many requests", "temporarily blocked",
                "timeout", "connection", "network", "temporary", "5", "429", "502", "503", "504"
            ])
        ),
        after=after_log(logger, logging.WARNING)
    )(func)

# Timeout configuration
DEFAULT_FUTURE_TIMEOUT = 30.0  # seconds

def safe_future_result(future, timeout: float = DEFAULT_FUTURE_TIMEOUT, default=None, context: str = ""):
    """
    Safely get result from a future with timeout and exception handling.

    Prevents server crashes from hanging API calls by catching timeouts
    and exceptions, logging them, and returning a default value.

    Args:
        future: The Future object to get result from
        timeout: Maximum seconds to wait (default: 30)
        default: Value to return on failure (default: None)
        context: Description for logging (e.g., "fetching ticker info")

    Returns:
        The future result or default value on failure
    """
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError:
        logger.error(f"Timeout after {timeout}s: {context}")
        return default
    except Exception as e:
        logger.error(f"Exception in {context}: {type(e).__name__}: {e}")
        return default

# HTTP client utility
def create_async_client(headers: dict | None = None) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient with longer timeout, automatic redirect and custom headers."""
    return httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers=headers,
    )

@api_retry
async def fetch_json(url: str, headers: dict | None = None) -> dict:
    """Generic JSON fetcher with retry logic."""
    async with create_async_client(headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

@api_retry
async def fetch_text(url: str, headers: dict | None = None) -> str:
    """Generic text fetcher with retry logic."""
    async with create_async_client(headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text

# Utility functions
def validate_ticker(ticker: str) -> str:
    ticker = ticker.upper().strip()
    if not ticker:
        raise ValueError("Ticker symbol cannot be empty")
    return ticker

def validate_date(date_str: str) -> datetime.date:
    """Validate and parse a date string in YYYY-MM-DD format."""
    try:
        return datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")

def validate_date_range(start_str: str | None, end_str: str | None) -> None:
    start_date = None
    end_date = None

    if start_str:
        start_date = validate_date(start_str)
    if end_str:
        end_date = validate_date(end_str)

    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date must be before or equal to end_date")


def get_price_history_questrade_first(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """
    Get historical price data with Questrade as primary source, yfinance as fallback.

    This ensures we get accurate split-adjusted data for stocks that have had splits.

    Args:
        ticker: Stock symbol
        period: Period string (1mo, 3mo, 6mo, 1y, 2y, etc.)

    Returns:
        DataFrame with OHLCV data (columns: Open, High, Low, Close, Volume)
    """
    from datetime import datetime, timedelta

    # Map period to days
    period_days = {
        '1d': 1, '5d': 5, '1mo': 30, '3mo': 90, '6mo': 180,
        '1y': 365, '2y': 730, '5y': 1825, 'ytd': (datetime.now() - datetime(datetime.now().year, 1, 1)).days
    }
    days = period_days.get(period, 90)

    # Try Questrade first
    try:
        qt_client = get_questrade_client()

        # Get symbol info
        symbol_info = qt_client.get_symbol_info(ticker)
        if symbol_info and symbol_info.get('symbols'):
            symbol_id = symbol_info['symbols'][0]['symbolId']

            # Calculate date range
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days + 10)  # Add buffer

            # Determine interval based on period
            if days <= 5:
                interval = "FifteenMinutes"
            elif days <= 30:
                interval = "OneHour"
            else:
                interval = "OneDay"

            # Format for Questrade API
            start_str = start_time.strftime('%Y-%m-%dT%H:%M:%S-05:00')
            end_str = end_time.strftime('%Y-%m-%dT%H:%M:%S-05:00')

            candles = qt_client.get_candles(ticker, interval, start_str, end_str)

            if candles and candles.get('candles'):
                df = pd.DataFrame(candles['candles'])
                # Rename columns to match yfinance format
                df = df.rename(columns={
                    'start': 'Date',
                    'open': 'Open',
                    'high': 'High',
                    'low': 'Low',
                    'close': 'Close',
                    'volume': 'Volume'
                })
                # Convert with utc=True to handle timezone-aware strings properly
                df['Date'] = pd.to_datetime(df['Date'], utc=True)
                df.set_index('Date', inplace=True)
                # Remove timezone info for consistent downstream processing
                df.index = df.index.tz_convert(None)

                if len(df) >= 10:  # Require minimum data points
                    logger.info(f"Using Questrade price history for {ticker} ({len(df)} bars)")
                    return df

    except Exception as e:
        logger.warning(f"Questrade price history unavailable for {ticker}: {e}")

    # Fallback to yfinance
    logger.info(f"Using yfinance for {ticker} price history")
    t = yf.Ticker(ticker)
    df = t.history(period=period)

    if df.empty:
        raise ValueError(f"No price history available for {ticker}")

    # Normalize timezone-aware index to avoid pandas conversion issues
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    return df


def get_current_price_questrade_first(ticker: str) -> float:
    """
    Get current price with Questrade as primary source, yfinance as fallback.

    Args:
        ticker: Stock symbol

    Returns:
        Current price as float
    """
    # Try Questrade first
    try:
        qt_client = get_questrade_client()
        quote = qt_client.get_quote(ticker)

        if quote and quote.get('quotes'):
            q = quote['quotes'][0]
            price = q.get('lastTradePrice') or q.get('lastTradePriceTrHrs')
            if price and price > 0:
                logger.info(f"Using Questrade price for {ticker}: ${price}")
                return float(price)

    except Exception as e:
        logger.warning(f"Questrade quote unavailable for {ticker}: {e}")

    # Fallback to yfinance
    t = yf.Ticker(ticker)
    info = t.info
    price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')

    if not price:
        raise ValueError(f"Could not get price for {ticker}")

    logger.info(f"Using yfinance price for {ticker}: ${price}")
    return float(price)

@api_retry
def yf_call(ticker: str, method: str, *args, **kwargs):
    """Generic yfinance API call with retry logic.

    Handles both properties (info, calendar, news) and methods (history, get_info).
    """
    t = yf.Ticker(ticker)
    attr = getattr(t, method)
    # If it's callable (method), call it; otherwise return the property value
    if callable(attr):
        return attr(*args, **kwargs)
    return attr

def get_options_chain(ticker: str, expiry: str, option_type: Literal["C", "P"] | None = None) -> pd.DataFrame:
    """Get options chain with optional filtering by type."""
    chain = yf_call(ticker, "option_chain", expiry)

    if option_type == "C":
        return chain.calls
    elif option_type == "P":
        return chain.puts

    return pd.concat([chain.calls, chain.puts], ignore_index=True)



def to_clean_csv(df: pd.DataFrame) -> str:
    """Clean DataFrame by removing empty columns and convert to CSV string."""
    # Chain operations more efficiently
    mask = (df.notna().any() & (df != '').any() &
            ((df != 0).any() | (df.dtypes == 'object')))
    return df.loc[:, mask].fillna('').to_csv(index=False)

def format_date_string(date_str: str) -> str | None:
    """Parse and format date string to YYYY-MM-DD format."""
    try:
        return datetime.datetime.fromisoformat(date_str.replace("Z", "")).strftime("%Y-%m-%d")
    except Exception:
        return date_str[:10] if date_str else None


# =============================================================================
# QUESTRADE-FIRST DATA FETCHING (with Yahoo Finance fallback)
# =============================================================================

def get_ticker_info_questrade_first(ticker: str) -> dict[str, Any]:
    """
    Get ticker info using Questrade as primary source, Yahoo Finance as fallback.

    This function tries Questrade first because:
    1. Questrade often has data for stocks Yahoo Finance lacks (e.g., MNMD)
    2. Questrade data is more reliable for Canadian stocks
    3. Better real-time data when market is open

    Returns a unified dict with metrics from best available source.
    """
    result = {
        "source": "none",
        "questrade_data": {},
        "yfinance_data": {},
        "merged": {}
    }

    # Field mapping: Questrade field -> unified field name
    questrade_to_unified = {
        'symbol': 'symbol',
        'description': 'longName',
        'prevDayClosePrice': 'previousClose',
        'highPrice52': 'fiftyTwoWeekHigh',
        'lowPrice52': 'fiftyTwoWeekLow',
        'averageVol3Months': 'averageVolume',
        'averageVol20Days': 'averageVolume10days',
        'outstandingShares': 'sharesOutstanding',
        'eps': 'trailingEps',
        'pe': 'trailingPE',
        'dividend': 'dividendRate',
        'yield': 'dividendYield',
        'marketCap': 'marketCap',
        'currency': 'currency',
        'listingExchange': 'exchange',
    }

    # Try Questrade first
    questrade_success = False
    try:
        # Get Questrade client
        client = get_questrade_client()
        if client:
            # Questrade client uses synchronous methods
            symbol_info = client.get_symbol_info(ticker)
            quote = client.get_quote(ticker)

            if symbol_info and symbol_info.get('symbols'):
                sym = symbol_info['symbols'][0]
                result["questrade_data"] = sym

                # Map Questrade fields to unified format
                for q_field, u_field in questrade_to_unified.items():
                    if q_field in sym and sym[q_field] is not None:
                        result["merged"][u_field] = sym[q_field]

                # Add quote data
                if quote and quote.get('quotes'):
                    q = quote['quotes'][0]
                    if q.get('lastTradePrice'):
                        result["merged"]['currentPrice'] = q['lastTradePrice']
                    if q.get('volume'):
                        result["merged"]['volume'] = q['volume']
                    if q.get('openPrice'):
                        result["merged"]['open'] = q['openPrice']
                    if q.get('highPrice'):
                        result["merged"]['dayHigh'] = q['highPrice']
                    if q.get('lowPrice'):
                        result["merged"]['dayLow'] = q['lowPrice']

                result["source"] = "questrade"
                questrade_success = True
                logger.info(f"Got ticker info for {ticker} from Questrade")

    except Exception as e:
        logger.warning(f"Questrade failed for {ticker}: {e}")

    # Try Yahoo Finance (as fallback or to supplement)
    try:
        yf_info = yf_call(ticker, "get_info")
        if yf_info:
            result["yfinance_data"] = yf_info

            if not questrade_success:
                # Questrade failed, use yfinance as primary
                result["merged"] = yf_info.copy()
                result["source"] = "yfinance"
                logger.info(f"Got ticker info for {ticker} from Yahoo Finance (Questrade unavailable)")
            else:
                # Merge yfinance data for fields Questrade doesn't have
                yf_only_fields = {
                    'beta', 'forwardPE', 'forwardEps', 'pegRatio',
                    'profitMargins', 'operatingMargins', 'returnOnEquity', 'returnOnAssets',
                    'revenueGrowth', 'earningsGrowth', 'totalRevenue', 'totalDebt',
                    'bookValue', 'priceToBook', 'enterpriseValue', 'sector', 'industry'
                }
                for field in yf_only_fields:
                    if field in yf_info and yf_info[field] is not None and field not in result["merged"]:
                        result["merged"][field] = yf_info[field]

                result["source"] = "questrade+yfinance"
                logger.info(f"Merged Questrade + Yahoo Finance data for {ticker}")

    except Exception as e:
        logger.warning(f"Yahoo Finance failed for {ticker}: {e}")
        if not questrade_success:
            raise ValueError(f"No data available for {ticker} from any source")

    return result


# Google Trends timeframe mapping
TREND_TIMEFRAMES = {
    1: 'now 1-d', 7: 'now 7-d', 30: 'today 1-m',
    90: 'today 3-m', 365: 'today 12-m'
}

def get_trends_timeframe(days: int) -> str:
    """Get appropriate Google Trends timeframe for given days."""
    for max_days, timeframe in TREND_TIMEFRAMES.items():
        if days <= max_days:
            return timeframe
    return 'today 5-y'


# ============================================================================
# PRICE/EMA INTERACTION INDICATORS
# ============================================================================

def detect_ema_bounce(
    prices: pd.Series,
    volumes: pd.Series | None = None,
    ema_period: int = 20,
    bounce_tolerance_pct: float = 2.0
) -> dict[str, Any]:
    """
    Detect when price bounces off EMA as support/resistance.

    A bounce occurs when:
    1. Price approaches EMA (within tolerance %)
    2. Price touches or slightly penetrates EMA
    3. Price reverses and moves away from EMA
    4. Ideally with increased volume

    Args:
        prices: Price series
        volumes: Optional volume series for confirmation
        ema_period: EMA period (default 20)
        bounce_tolerance_pct: Distance tolerance from EMA (default 2%)

    Returns:
        {
            'signal': 'BULLISH_BOUNCE' | 'BEARISH_BOUNCE' | 'NONE',
            'ema_level': float,
            'distance_pct': float,
            'bounce_days_ago': int,
            'volume_confirmed': bool,
            'strength': 'STRONG' | 'MODERATE' | 'WEAK'
        }
    """
    if len(prices) < ema_period + 5:
        return {
            'signal': 'NONE',
            'ema_level': 0.0,
            'distance_pct': 0.0,
            'bounce_days_ago': 0,
            'volume_confirmed': False,
            'strength': 'NONE'
        }

    # Calculate EMA
    ema = prices.ewm(span=ema_period, adjust=False).mean()

    current_price = prices.iloc[-1]
    current_ema = ema.iloc[-1]

    # Current distance from EMA
    distance_pct = ((current_price / current_ema) - 1) * 100

    # Look back 5 days for bounce pattern
    bounce_signal = 'NONE'
    bounce_days_ago = 0
    volume_confirmed = False
    strength = 'NONE'

    # Check last 5 days for bounce pattern
    for i in range(1, min(6, len(prices))):
        past_price = prices.iloc[-i]
        past_ema = ema.iloc[-i]
        past_distance_pct = ((past_price / past_ema) - 1) * 100

        # BULLISH BOUNCE: Price was below/at EMA, now above
        if past_distance_pct <= bounce_tolerance_pct and past_distance_pct >= -bounce_tolerance_pct:
            if distance_pct > 1.0:  # Now clearly above
                bounce_signal = 'BULLISH_BOUNCE'
                bounce_days_ago = i

                # Check volume confirmation
                if volumes is not None and i < len(volumes):
                    avg_volume = volumes.iloc[-20:-i].mean() if len(volumes) >= 20 + i else volumes.mean()
                    bounce_volume = volumes.iloc[-i]
                    volume_confirmed = bounce_volume > avg_volume * 1.2  # 20% above average

                # Determine strength
                if distance_pct > 3.0:
                    strength = 'STRONG'
                elif distance_pct > 1.5:
                    strength = 'MODERATE'
                else:
                    strength = 'WEAK'

                break

        # BEARISH BOUNCE: Price was above/at EMA, now below
        if past_distance_pct <= bounce_tolerance_pct and past_distance_pct >= -bounce_tolerance_pct:
            if distance_pct < -1.0:  # Now clearly below
                bounce_signal = 'BEARISH_BOUNCE'
                bounce_days_ago = i

                # Check volume confirmation
                if volumes is not None and i < len(volumes):
                    avg_volume = volumes.iloc[-20:-i].mean() if len(volumes) >= 20 + i else volumes.mean()
                    bounce_volume = volumes.iloc[-i]
                    volume_confirmed = bounce_volume > avg_volume * 1.2

                # Determine strength
                if distance_pct < -3.0:
                    strength = 'STRONG'
                elif distance_pct < -1.5:
                    strength = 'MODERATE'
                else:
                    strength = 'WEAK'

                break

    return {
        'signal': bounce_signal,
        'ema_level': current_ema,
        'distance_pct': distance_pct,
        'bounce_days_ago': bounce_days_ago,
        'volume_confirmed': volume_confirmed,
        'strength': strength
    }


def detect_ema_cross(
    prices: pd.Series,
    ema_period: int = 20
) -> dict[str, Any]:
    """
    Detect when price crosses above or below EMA.

    Crossover = price moving from one side of EMA to the other
    This is a dynamic support/resistance breakout/breakdown signal.

    Args:
        prices: Price series
        ema_period: EMA period (default 20)

    Returns:
        {
            'signal': 'BULLISH_CROSS' | 'BEARISH_CROSS' | 'ABOVE' | 'BELOW',
            'ema_level': float,
            'distance_pct': float,
            'cross_days_ago': int
        }
    """
    if len(prices) < ema_period + 5:
        return {
            'signal': 'NONE',
            'ema_level': 0.0,
            'distance_pct': 0.0,
            'cross_days_ago': 0
        }

    # Calculate EMA
    ema = prices.ewm(span=ema_period, adjust=False).mean()

    current_price = prices.iloc[-1]
    current_ema = ema.iloc[-1]

    # Current distance from EMA
    distance_pct = ((current_price / current_ema) - 1) * 100

    # Look back 5 days for crossover
    cross_signal = 'NONE'
    cross_days_ago = 0

    for i in range(1, min(6, len(prices))):
        prev_price = prices.iloc[-i-1]
        prev_ema = ema.iloc[-i-1]
        curr_price = prices.iloc[-i]
        curr_ema = ema.iloc[-i]

        # BULLISH CROSS: Was below, now above
        if prev_price <= prev_ema and curr_price > curr_ema:
            cross_signal = 'BULLISH_CROSS'
            cross_days_ago = i
            break

        # BEARISH CROSS: Was above, now below
        if prev_price >= prev_ema and curr_price < curr_ema:
            cross_signal = 'BEARISH_CROSS'
            cross_days_ago = i
            break

    # If no recent cross, just indicate position
    if cross_signal == 'NONE':
        cross_signal = 'ABOVE' if current_price > current_ema else 'BELOW'

    return {
        'signal': cross_signal,
        'ema_level': current_ema,
        'distance_pct': distance_pct,
        'cross_days_ago': cross_days_ago
    }


def detect_ema_extension(
    prices: pd.Series,
    ema_period: int = 20,
    extension_threshold_pct: float = 5.0
) -> dict[str, Any]:
    """
    Detect when price is extended too far from EMA (reversal warning).

    When price moves >5% from EMA, it's often "overbought" or "oversold"
    relative to the moving average and may snap back (mean reversion).

    Args:
        prices: Price series
        ema_period: EMA period (default 20)
        extension_threshold_pct: Extension threshold (default 5%)

    Returns:
        {
            'signal': 'OVEREXTENDED_BULLISH' | 'OVEREXTENDED_BEARISH' | 'NORMAL',
            'ema_level': float,
            'distance_pct': float,
            'severity': 'EXTREME' | 'HIGH' | 'MODERATE' | 'NORMAL'
        }
    """
    if len(prices) < ema_period:
        return {
            'signal': 'NORMAL',
            'ema_level': 0.0,
            'distance_pct': 0.0,
            'severity': 'NORMAL'
        }

    # Calculate EMA
    ema = prices.ewm(span=ema_period, adjust=False).mean()

    current_price = prices.iloc[-1]
    current_ema = ema.iloc[-1]

    # Current distance from EMA
    distance_pct = ((current_price / current_ema) - 1) * 100

    # Determine signal and severity
    if distance_pct > extension_threshold_pct:
        signal = 'OVEREXTENDED_BULLISH'
        if distance_pct > 10.0:
            severity = 'EXTREME'
        elif distance_pct > 7.5:
            severity = 'HIGH'
        else:
            severity = 'MODERATE'
    elif distance_pct < -extension_threshold_pct:
        signal = 'OVEREXTENDED_BEARISH'
        if distance_pct < -10.0:
            severity = 'EXTREME'
        elif distance_pct < -7.5:
            severity = 'HIGH'
        else:
            severity = 'MODERATE'
    else:
        signal = 'NORMAL'
        severity = 'NORMAL'

    return {
        'signal': signal,
        'ema_level': current_ema,
        'distance_pct': distance_pct,
        'severity': severity
    }


# ============================================================================
# VWAP SUPPORT/RESISTANCE INDICATORS
# ============================================================================

def detect_vwap_bounce(
    prices: pd.Series,
    volumes: pd.Series,
    window: int = 20,
    bounce_tolerance_pct: float = 1.5
) -> dict[str, Any]:
    """
    Detect when price bounces off VWAP as support or resistance.

    VWAP (Volume Weighted Average Price) is considered institutional "fair value".
    When price bounces off VWAP, it often indicates strong support/resistance.

    A bounce occurs when:
    1. Price approaches VWAP (within tolerance %)
    2. Price touches or slightly penetrates VWAP
    3. Price reverses and moves away from VWAP
    4. Ideally with increased volume

    Args:
        prices: Price series
        volumes: Volume series
        window: VWAP calculation window (default 20 days)
        bounce_tolerance_pct: Distance tolerance from VWAP (default 1.5%)

    Returns:
        {
            'signal': 'VWAP_BOUNCE_SUPPORT' | 'VWAP_BOUNCE_RESISTANCE' | 'NONE',
            'vwap_level': float,
            'distance_pct': float,
            'bounce_days_ago': int,
            'volume_confirmed': bool,
            'strength': 'STRONG' | 'MODERATE' | 'WEAK' | 'NONE'
        }
    """
    if len(prices) < window + 5:
        return {
            'signal': 'NONE',
            'vwap_level': 0.0,
            'distance_pct': 0.0,
            'bounce_days_ago': 0,
            'volume_confirmed': False,
            'strength': 'NONE'
        }

    # Calculate VWAP (Volume Weighted Average Price)
    # VWAP = Σ(Price × Volume) / Σ(Volume)
    typical_price = prices  # Using close prices
    vwap = (typical_price * volumes).rolling(window=window).sum() / volumes.rolling(window=window).sum()

    current_price = prices.iloc[-1]
    current_vwap = vwap.iloc[-1]

    # Current distance from VWAP
    distance_pct = ((current_price / current_vwap) - 1) * 100

    # Look back 5 days for bounce pattern
    bounce_signal = 'NONE'
    bounce_days_ago = 0
    volume_confirmed = False
    strength = 'NONE'

    # Check last 5 days for bounce pattern
    for i in range(1, min(6, len(prices))):
        past_price = prices.iloc[-i]
        past_vwap = vwap.iloc[-i]
        past_distance_pct = ((past_price / past_vwap) - 1) * 100

        # SUPPORT BOUNCE: Price was at/below VWAP, now above
        if past_distance_pct <= bounce_tolerance_pct and past_distance_pct >= -bounce_tolerance_pct:
            if distance_pct > 0.5:  # Now clearly above
                bounce_signal = 'VWAP_BOUNCE_SUPPORT'
                bounce_days_ago = i

                # Check volume confirmation
                avg_volume = volumes.iloc[-20:-i].mean() if len(volumes) >= 20 + i else volumes.mean()
                bounce_volume = volumes.iloc[-i]
                volume_confirmed = bounce_volume > avg_volume * 1.2  # 20% above average

                # Determine strength
                if distance_pct > 2.0:
                    strength = 'STRONG'
                elif distance_pct > 1.0:
                    strength = 'MODERATE'
                else:
                    strength = 'WEAK'

                break

        # RESISTANCE BOUNCE: Price was at/above VWAP, now below
        if past_distance_pct <= bounce_tolerance_pct and past_distance_pct >= -bounce_tolerance_pct:
            if distance_pct < -0.5:  # Now clearly below
                bounce_signal = 'VWAP_BOUNCE_RESISTANCE'
                bounce_days_ago = i

                # Check volume confirmation
                avg_volume = volumes.iloc[-20:-i].mean() if len(volumes) >= 20 + i else volumes.mean()
                bounce_volume = volumes.iloc[-i]
                volume_confirmed = bounce_volume > avg_volume * 1.2

                # Determine strength
                if distance_pct < -2.0:
                    strength = 'STRONG'
                elif distance_pct < -1.0:
                    strength = 'MODERATE'
                else:
                    strength = 'WEAK'

                break

    return {
        'signal': bounce_signal,
        'vwap_level': current_vwap,
        'distance_pct': distance_pct,
        'bounce_days_ago': bounce_days_ago,
        'volume_confirmed': volume_confirmed,
        'strength': strength
    }


def detect_vwap_cross(
    prices: pd.Series,
    volumes: pd.Series,
    window: int = 20
) -> dict[str, Any]:
    """
    Detect when price crosses above or below VWAP (sentiment shift).

    VWAP crossovers indicate institutional sentiment shifts:
    - Cross above VWAP = Bullish sentiment (buyers in control)
    - Cross below VWAP = Bearish sentiment (sellers in control)

    Args:
        prices: Price series
        volumes: Volume series
        window: VWAP calculation window (default 20 days)

    Returns:
        {
            'signal': 'BULLISH_VWAP_CROSS' | 'BEARISH_VWAP_CROSS' | 'ABOVE_VWAP' | 'BELOW_VWAP',
            'vwap_level': float,
            'distance_pct': float,
            'cross_days_ago': int
        }
    """
    if len(prices) < window + 5:
        return {
            'signal': 'NONE',
            'vwap_level': 0.0,
            'distance_pct': 0.0,
            'cross_days_ago': 0
        }

    # Calculate VWAP
    typical_price = prices
    vwap = (typical_price * volumes).rolling(window=window).sum() / volumes.rolling(window=window).sum()

    current_price = prices.iloc[-1]
    current_vwap = vwap.iloc[-1]

    # Current distance from VWAP
    distance_pct = ((current_price / current_vwap) - 1) * 100

    # Look back 5 days for crossover
    cross_signal = 'NONE'
    cross_days_ago = 0

    for i in range(1, min(6, len(prices))):
        prev_price = prices.iloc[-i-1]
        prev_vwap = vwap.iloc[-i-1]
        curr_price = prices.iloc[-i]
        curr_vwap = vwap.iloc[-i]

        # BULLISH CROSS: Was below, now above
        if prev_price <= prev_vwap and curr_price > curr_vwap:
            cross_signal = 'BULLISH_VWAP_CROSS'
            cross_days_ago = i
            break

        # BEARISH CROSS: Was above, now below
        if prev_price >= prev_vwap and curr_price < curr_vwap:
            cross_signal = 'BEARISH_VWAP_CROSS'
            cross_days_ago = i
            break

    # If no recent cross, just indicate position
    if cross_signal == 'NONE':
        cross_signal = 'ABOVE_VWAP' if current_price > current_vwap else 'BELOW_VWAP'

    return {
        'signal': cross_signal,
        'vwap_level': current_vwap,
        'distance_pct': distance_pct,
        'cross_days_ago': cross_days_ago
    }


def interpret_vwap_position(
    price_vs_vwap_pct: float
) -> dict[str, Any]:
    """
    Interpret price position relative to VWAP.

    VWAP Position Interpretation:
    - Above VWAP: Bullish sentiment, buyers in control
    - Below VWAP: Bearish sentiment, sellers in control
    - Distance magnitude indicates strength

    Args:
        price_vs_vwap_pct: Price distance from VWAP as percentage

    Returns:
        {
            'position': 'STRONG_ABOVE' | 'ABOVE' | 'AT_VWAP' | 'BELOW' | 'STRONG_BELOW',
            'sentiment': 'STRONG_BULLISH' | 'BULLISH' | 'NEUTRAL' | 'BEARISH' | 'STRONG_BEARISH',
            'interpretation': str (human-readable explanation)
        }
    """
    if price_vs_vwap_pct > 3.0:
        return {
            'position': 'STRONG_ABOVE',
            'sentiment': 'STRONG_BULLISH',
            'interpretation': f'Price {price_vs_vwap_pct:+.2f}% above VWAP - Strong bullish sentiment, buyers firmly in control'
        }
    elif price_vs_vwap_pct > 1.0:
        return {
            'position': 'ABOVE',
            'sentiment': 'BULLISH',
            'interpretation': f'Price {price_vs_vwap_pct:+.2f}% above VWAP - Bullish sentiment, buyers in control'
        }
    elif price_vs_vwap_pct > -1.0:
        return {
            'position': 'AT_VWAP',
            'sentiment': 'NEUTRAL',
            'interpretation': f'Price {price_vs_vwap_pct:+.2f}% from VWAP - Neutral sentiment, balanced market'
        }
    elif price_vs_vwap_pct > -3.0:
        return {
            'position': 'BELOW',
            'sentiment': 'BEARISH',
            'interpretation': f'Price {price_vs_vwap_pct:+.2f}% below VWAP - Bearish sentiment, sellers in control'
        }
    else:
        return {
            'position': 'STRONG_BELOW',
            'sentiment': 'STRONG_BEARISH',
            'interpretation': f'Price {price_vs_vwap_pct:+.2f}% below VWAP - Strong bearish sentiment, sellers firmly in control'
        }


# ============================================================================
# VOLUME CONFIRMATION INDICATORS
# ============================================================================

def detect_volume_surge(
    volumes: pd.Series,
    window: int = 20,
    threshold_pct: float = 0.50
) -> dict[str, Any]:
    """
    Detect unusual volume spikes (>50% above average).

    Volume surges often precede or confirm significant price moves.
    Research shows volume should increase 50%+ on valid crossovers.

    Args:
        volumes: Volume series
        window: Rolling average window (default 20 days)
        threshold_pct: Surge threshold as decimal (default 0.50 = 50%)

    Returns:
        {
            'signal': 'VOLUME_SURGE' | 'NORMAL' | 'LOW_VOLUME',
            'current_volume': int,
            'avg_volume': float,
            'volume_ratio': float,
            'surge_strength': 'EXTREME' | 'STRONG' | 'MODERATE' | 'NORMAL' | 'LOW'
        }
    """
    if len(volumes) < window:
        return {
            'signal': 'NORMAL',
            'current_volume': 0,
            'avg_volume': 0.0,
            'volume_ratio': 0.0,
            'surge_strength': 'NORMAL'
        }

    # Calculate average volume
    avg_volume = volumes.iloc[-window:].mean()
    current_volume = volumes.iloc[-1]

    # Calculate volume ratio
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0.0

    # Determine signal and strength
    if volume_ratio > (1 + threshold_pct):
        signal = 'VOLUME_SURGE'

        # Classify surge strength
        if volume_ratio > 3.0:  # 3x average
            surge_strength = 'EXTREME'
        elif volume_ratio > 2.0:  # 2x average
            surge_strength = 'STRONG'
        elif volume_ratio > 1.5:  # 1.5x average
            surge_strength = 'MODERATE'
        else:
            surge_strength = 'NORMAL'
    elif volume_ratio < 0.5:  # Less than half average
        signal = 'LOW_VOLUME'
        surge_strength = 'LOW'
    else:
        signal = 'NORMAL'
        surge_strength = 'NORMAL'

    return {
        'signal': signal,
        'current_volume': int(current_volume),
        'avg_volume': float(avg_volume),
        'volume_ratio': float(volume_ratio),
        'surge_strength': surge_strength
    }


def calculate_obv_signal(
    prices: pd.Series,
    volumes: pd.Series
) -> dict[str, Any]:
    """
    Calculate On-Balance Volume (OBV) trend and divergence signals.

    OBV measures buying/selling pressure by adding volume on up days
    and subtracting volume on down days.

    Divergences:
    - Price up, OBV down = Warning (distribution)
    - Price down, OBV up = Bullish (accumulation)

    Args:
        prices: Price series
        volumes: Volume series

    Returns:
        {
            'obv': pd.Series,
            'obv_trend': 'UPTREND' | 'DOWNTREND' | 'NEUTRAL',
            'obv_strength': float (0-100),
            'divergence': 'BULLISH_DIVERGENCE' | 'BEARISH_DIVERGENCE' | 'NONE',
            'signal': 'BULLISH' | 'BEARISH' | 'NEUTRAL'
        }
    """
    if len(prices) < 20 or len(volumes) < 20:
        return {
            'obv': pd.Series(),
            'obv_trend': 'NEUTRAL',
            'obv_strength': 0.0,
            'divergence': 'NONE',
            'signal': 'NEUTRAL'
        }

    # Calculate OBV
    # OBV = Previous OBV + Volume (if price up) or - Volume (if price down)
    price_changes = prices.diff()
    obv = pd.Series(index=prices.index, dtype=float)
    obv.iloc[0] = volumes.iloc[0]

    for i in range(1, len(prices)):
        if price_changes.iloc[i] > 0:
            obv.iloc[i] = obv.iloc[i-1] + volumes.iloc[i]
        elif price_changes.iloc[i] < 0:
            obv.iloc[i] = obv.iloc[i-1] - volumes.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]

    # Determine OBV trend (last 10 days)
    if len(obv) >= 10:
        obv_recent = obv.iloc[-10:]
        obv_slope = (obv_recent.iloc[-1] - obv_recent.iloc[0]) / 10

        if obv_slope > 0:
            obv_trend = 'UPTREND'
            obv_strength = min(100, abs(obv_slope) / obv.iloc[-10:].std() * 50) if obv.iloc[-10:].std() > 0 else 50
        elif obv_slope < 0:
            obv_trend = 'DOWNTREND'
            obv_strength = min(100, abs(obv_slope) / obv.iloc[-10:].std() * 50) if obv.iloc[-10:].std() > 0 else 50
        else:
            obv_trend = 'NEUTRAL'
            obv_strength = 0.0
    else:
        obv_trend = 'NEUTRAL'
        obv_strength = 0.0

    # Detect divergences (last 20 days)
    divergence = 'NONE'
    if len(prices) >= 20 and len(obv) >= 20:
        price_trend = (prices.iloc[-1] - prices.iloc[-20]) / prices.iloc[-20]
        obv_trend_pct = (obv.iloc[-1] - obv.iloc[-20]) / abs(obv.iloc[-20]) if obv.iloc[-20] != 0 else 0

        # Bullish divergence: Price down, OBV up
        if price_trend < -0.05 and obv_trend_pct > 0.05:
            divergence = 'BULLISH_DIVERGENCE'
        # Bearish divergence: Price up, OBV down
        elif price_trend > 0.05 and obv_trend_pct < -0.05:
            divergence = 'BEARISH_DIVERGENCE'

    # Generate final signal
    if obv_trend == 'UPTREND' or divergence == 'BULLISH_DIVERGENCE':
        signal = 'BULLISH'
    elif obv_trend == 'DOWNTREND' or divergence == 'BEARISH_DIVERGENCE':
        signal = 'BEARISH'
    else:
        signal = 'NEUTRAL'

    return {
        'obv': obv,
        'obv_trend': obv_trend,
        'obv_strength': float(obv_strength),
        'divergence': divergence,
        'signal': signal
    }


def confirm_crossover_with_volume(
    cross_signal: str,
    volume_surge: dict[str, Any]
) -> dict[str, Any]:
    """
    Confirm if a crossover signal has volume support.

    Research shows valid crossovers have 50%+ volume increase.
    Volume confirmation significantly improves win rate (75% → 85%).

    Args:
        cross_signal: Crossover signal ('BULLISH_CROSS', 'BEARISH_CROSS', etc.)
        volume_surge: Result from detect_volume_surge()

    Returns:
        {
            'confirmed': bool,
            'confidence': 'HIGH' | 'MODERATE' | 'LOW',
            'explanation': str
        }
    """
    # Check if this is a crossover signal
    is_crossover = 'CROSS' in cross_signal

    if not is_crossover:
        return {
            'confirmed': False,
            'confidence': 'LOW',
            'explanation': 'Not a crossover signal - no volume confirmation needed'
        }

    # Check volume surge
    has_volume_surge = volume_surge['signal'] == 'VOLUME_SURGE'
    volume_ratio = volume_surge['volume_ratio']

    if has_volume_surge:
        # Determine confidence based on surge strength
        if volume_ratio > 2.0:  # 2x average or more
            confidence = 'HIGH'
            explanation = f'Strong volume confirmation: {volume_ratio:.1f}x average volume'
        elif volume_ratio > 1.5:
            confidence = 'MODERATE'
            explanation = f'Moderate volume confirmation: {volume_ratio:.1f}x average volume'
        else:
            confidence = 'MODERATE'
            explanation = f'Volume confirmation: {volume_ratio:.1f}x average volume'

        confirmed = True
    else:
        confirmed = False
        confidence = 'LOW'
        if volume_surge['signal'] == 'LOW_VOLUME':
            explanation = f'WARNING: Low volume ({volume_ratio:.1f}x avg) - weak crossover'
        else:
            explanation = f'No volume surge ({volume_ratio:.1f}x avg) - unconfirmed crossover'

    return {
        'confirmed': confirmed,
        'confidence': confidence,
        'explanation': explanation
    }


# ============================================================================
# EMA/VWAP CONFLUENCE INDICATORS
# ============================================================================

def detect_ema_vwap_confluence(
    price: float,
    ema_20: float,
    ema_50: float,
    vwap: float
) -> dict[str, Any]:
    """
    Detect confluence between EMAs and VWAP for high-probability setups.

    When multiple indicators align in the same direction, the signal
    strength increases significantly. Research shows confluence of 3+
    indicators improves win rate from 65% → 80%+.

    Args:
        price: Current price
        ema_20: EMA 20 value
        ema_50: EMA 50 value
        vwap: VWAP value

    Returns:
        {
            'signal': 'STRONG_BULLISH_CONFLUENCE' | 'BULLISH_CONFLUENCE' |
                     'STRONG_BEARISH_CONFLUENCE' | 'BEARISH_CONFLUENCE' |
                     'MIXED_SIGNALS',
            'alignment_count': int (0-4),
            'bullish_count': int,
            'bearish_count': int,
            'strength': 'MAXIMUM' | 'STRONG' | 'MODERATE' | 'WEAK' | 'NONE',
            'price_above_ema20': bool,
            'price_above_ema50': bool,
            'price_above_vwap': bool,
            'ema20_above_ema50': bool,
            'interpretation': str
        }
    """
    # Calculate price positions
    price_above_ema20 = price > ema_20
    price_above_ema50 = price > ema_50
    price_above_vwap = price > vwap
    ema20_above_ema50 = ema_20 > ema_50

    # Count bullish and bearish alignments
    bullish_count = sum([
        price_above_ema20,
        price_above_ema50,
        price_above_vwap,
        ema20_above_ema50
    ])

    bearish_count = sum([
        not price_above_ema20,
        not price_above_ema50,
        not price_above_vwap,
        not ema20_above_ema50
    ])

    # Determine alignment strength (all 4 indicators pointing same way)
    alignment_count = max(bullish_count, bearish_count)

    # Generate signal based on confluence
    if bullish_count == 4:
        signal = 'STRONG_BULLISH_CONFLUENCE'
        strength = 'MAXIMUM'
        interpretation = (
            'MAXIMUM bullish confluence: Price above EMA 20, EMA 50, and VWAP. '
            'EMA 20 above EMA 50. All indicators aligned bullish - HIGHEST probability setup.'
        )
    elif bullish_count == 3:
        signal = 'BULLISH_CONFLUENCE'
        strength = 'STRONG'
        interpretation = (
            'Strong bullish confluence: 3 of 4 indicators aligned bullish. '
            'High probability setup with multiple confirmations.'
        )
    elif bearish_count == 4:
        signal = 'STRONG_BEARISH_CONFLUENCE'
        strength = 'MAXIMUM'
        interpretation = (
            'MAXIMUM bearish confluence: Price below EMA 20, EMA 50, and VWAP. '
            'EMA 20 below EMA 50. All indicators aligned bearish - HIGHEST probability setup.'
        )
    elif bearish_count == 3:
        signal = 'BEARISH_CONFLUENCE'
        strength = 'STRONG'
        interpretation = (
            'Strong bearish confluence: 3 of 4 indicators aligned bearish. '
            'High probability setup with multiple confirmations.'
        )
    elif bullish_count == 2 and bearish_count == 2:
        signal = 'MIXED_SIGNALS'
        strength = 'WEAK'
        interpretation = (
            'Mixed signals: Equal bullish and bearish indicators. '
            'No clear confluence - wait for clearer alignment.'
        )
    else:
        signal = 'MIXED_SIGNALS'
        strength = 'MODERATE'
        if bullish_count > bearish_count:
            interpretation = f'Moderate bullish lean: {bullish_count} bullish vs {bearish_count} bearish indicators.'
        else:
            interpretation = f'Moderate bearish lean: {bearish_count} bearish vs {bullish_count} bullish indicators.'

    return {
        'signal': signal,
        'alignment_count': alignment_count,
        'bullish_count': bullish_count,
        'bearish_count': bearish_count,
        'strength': strength,
        'price_above_ema20': price_above_ema20,
        'price_above_ema50': price_above_ema50,
        'price_above_vwap': price_above_vwap,
        'ema20_above_ema50': ema20_above_ema50,
        'interpretation': interpretation
    }


# ============================================================================
# ORDER BLOCKS (Institutional Footprints)
# ============================================================================

def detect_order_blocks(
    prices: pd.Series,
    lookback: int = 50,
    impulse_threshold_pct: float = 3.0,
    proximity_pct: float = 2.0
) -> dict[str, Any]:
    """
    Detect Order Blocks - institutional supply/demand zones.

    Order Blocks are the last opposing candle before a strong price move.
    They represent zones where institutions executed large orders and often
    act as strong support/resistance when price returns.

    Bullish Order Block: Last down candle before strong up move (buying zone)
    Bearish Order Block: Last up candle before strong down move (selling zone)

    Args:
        prices: Price series (Close prices)
        lookback: How many candles to look back for order blocks
        impulse_threshold_pct: Minimum move % to qualify as impulse (default 3%)
        proximity_pct: How close price must be to order block (default 2%)

    Returns:
        {
            'signal': 'BULLISH_ORDER_BLOCK_TEST' | 'BEARISH_ORDER_BLOCK_TEST' | 'NONE',
            'bullish_blocks': list[dict],  # List of bullish order blocks
            'bearish_blocks': list[dict],  # List of bearish order blocks
            'closest_bullish_block': dict | None,
            'closest_bearish_block': dict | None,
            'distance_to_bullish_pct': float,
            'distance_to_bearish_pct': float,
            'interpretation': str
        }
    """
    if len(prices) < lookback + 5:
        return {
            'signal': 'NONE',
            'bullish_blocks': [],
            'bearish_blocks': [],
            'closest_bullish_block': None,
            'closest_bearish_block': None,
            'distance_to_bullish_pct': 100.0,
            'distance_to_bearish_pct': 100.0,
            'interpretation': 'Insufficient data for order block detection'
        }

    current_price = prices.iloc[-1]
    bullish_blocks = []
    bearish_blocks = []

    # Search for order blocks in lookback period
    for i in range(len(prices) - lookback, len(prices) - 5):
        # Calculate candle direction and size
        candle_change_pct = (prices.iloc[i] - prices.iloc[i-1]) / prices.iloc[i-1] * 100

        # Look ahead for impulse move (next 1-3 candles)
        future_max = prices.iloc[i:i+4].max()
        future_min = prices.iloc[i:i+4].min()

        # Check for bullish impulse (strong up move after down candle)
        if candle_change_pct < 0:  # Down candle
            impulse_up = (future_max - prices.iloc[i]) / prices.iloc[i] * 100
            if impulse_up >= impulse_threshold_pct:
                # This is a bullish order block
                bullish_blocks.append({
                    'candle_index': i,
                    'price_low': prices.iloc[i-1:i+1].min(),
                    'price_high': prices.iloc[i-1:i+1].max(),
                    'impulse_size': impulse_up,
                    'age_days': len(prices) - i - 1
                })

        # Check for bearish impulse (strong down move after up candle)
        elif candle_change_pct > 0:  # Up candle
            impulse_down = (prices.iloc[i] - future_min) / prices.iloc[i] * 100
            if impulse_down >= impulse_threshold_pct:
                # This is a bearish order block
                bearish_blocks.append({
                    'candle_index': i,
                    'price_low': prices.iloc[i-1:i+1].min(),
                    'price_high': prices.iloc[i-1:i+1].max(),
                    'impulse_size': impulse_down,
                    'age_days': len(prices) - i - 1
                })

    # Find closest order blocks to current price
    closest_bullish_block = None
    closest_bearish_block = None
    distance_to_bullish = 100.0
    distance_to_bearish = 100.0

    # Find closest bullish block (below current price)
    bullish_below = [b for b in bullish_blocks if b['price_high'] < current_price]
    if bullish_below:
        closest_bullish_block = min(bullish_below, key=lambda b: abs(current_price - b['price_high']))
        distance_to_bullish = (current_price - closest_bullish_block['price_high']) / current_price * 100

    # Find closest bearish block (above current price)
    bearish_above = [b for b in bearish_blocks if b['price_low'] > current_price]
    if bearish_above:
        closest_bearish_block = min(bearish_above, key=lambda b: abs(b['price_low'] - current_price))
        distance_to_bearish = (closest_bearish_block['price_low'] - current_price) / current_price * 100

    # Determine signal based on proximity
    signal = 'NONE'
    interpretation = ''

    if distance_to_bullish <= proximity_pct and closest_bullish_block is not None:
        signal = 'BULLISH_ORDER_BLOCK_TEST'
        interpretation = (
            f'Price testing bullish order block from {closest_bullish_block["age_days"]} days ago. '
            f'Distance: {distance_to_bullish:.2f}%. '
            f'Original impulse: +{closest_bullish_block["impulse_size"]:.1f}%. '
            f'Potential support zone - watch for bounce.'
        )
    elif distance_to_bearish <= proximity_pct and closest_bearish_block is not None:
        signal = 'BEARISH_ORDER_BLOCK_TEST'
        interpretation = (
            f'Price testing bearish order block from {closest_bearish_block["age_days"]} days ago. '
            f'Distance: {distance_to_bearish:.2f}%. '
            f'Original impulse: -{closest_bearish_block["impulse_size"]:.1f}%. '
            f'Potential resistance zone - watch for rejection.'
        )
    else:
        interpretation = (
            f'No order blocks in proximity. '
            f'Closest bullish block: {distance_to_bullish:.1f}% below. '
            f'Closest bearish block: {distance_to_bearish:.1f}% above.'
        )

    return {
        'signal': signal,
        'bullish_blocks': bullish_blocks,
        'bearish_blocks': bearish_blocks,
        'closest_bullish_block': closest_bullish_block,
        'closest_bearish_block': closest_bearish_block,
        'distance_to_bullish_pct': distance_to_bullish,
        'distance_to_bearish_pct': distance_to_bearish,
        'interpretation': interpretation
    }


# ============================================================================
# SUPPLY/DEMAND ZONES (Price Action Zones)
# ============================================================================

def detect_supply_demand_zones(
    prices: pd.Series,
    lookback: int = 50,
    consolidation_bars: int = 3,
    impulse_threshold_pct: float = 5.0,
    proximity_pct: float = 2.0
) -> dict[str, Any]:
    """
    Detect Supply/Demand Zones - price consolidation areas before strong moves.

    Unlike Order Blocks (single candles), Supply/Demand Zones are consolidation
    ranges where price moved sideways before a strong impulse. These zones
    represent areas of accumulated buying/selling pressure.

    Demand Zone: Consolidation followed by strong rally (buying pressure)
    Supply Zone: Consolidation followed by strong drop (selling pressure)

    Args:
        prices: Price series (Close prices)
        lookback: How many candles to look back for zones
        consolidation_bars: Minimum bars in consolidation (default 3)
        impulse_threshold_pct: Minimum move % to qualify as impulse (default 5%)
        proximity_pct: How close price must be to zone (default 2%)

    Returns:
        {
            'signal': 'DEMAND_ZONE_TEST' | 'SUPPLY_ZONE_TEST' | 'NONE',
            'demand_zones': list[dict],  # List of demand zones (support)
            'supply_zones': list[dict],  # List of supply zones (resistance)
            'closest_demand_zone': dict | None,
            'closest_supply_zone': dict | None,
            'distance_to_demand_pct': float,
            'distance_to_supply_pct': float,
            'interpretation': str
        }
    """
    if len(prices) < lookback + consolidation_bars + 5:
        return {
            'signal': 'NONE',
            'demand_zones': [],
            'supply_zones': [],
            'closest_demand_zone': None,
            'closest_supply_zone': None,
            'distance_to_demand_pct': 100.0,
            'distance_to_supply_pct': 100.0,
            'interpretation': 'Insufficient data for supply/demand zone detection'
        }

    current_price = prices.iloc[-1]
    demand_zones = []
    supply_zones = []

    # Search for consolidation zones followed by impulse moves
    i = len(prices) - lookback
    while i < len(prices) - consolidation_bars - 5:
        # Get consolidation window
        consolidation_window = prices.iloc[i:i+consolidation_bars]

        # Calculate consolidation range
        zone_high = consolidation_window.max()
        zone_low = consolidation_window.min()
        zone_range_pct = (zone_high - zone_low) / zone_low * 100

        # Only consider tight consolidations (range < 3%)
        if zone_range_pct < 3.0:
            # Look for impulse move after consolidation
            future_window_start = i + consolidation_bars
            future_window_end = min(i + consolidation_bars + 10, len(prices))
            future_prices = prices.iloc[future_window_start:future_window_end]

            if len(future_prices) > 0:
                future_high = future_prices.max()
                future_low = future_prices.min()

                # Check for bullish impulse (strong rally from zone)
                impulse_up = (future_high - zone_high) / zone_high * 100
                if impulse_up >= impulse_threshold_pct:
                    # This is a demand zone (support)
                    demand_zones.append({
                        'start_index': i,
                        'zone_low': zone_low,
                        'zone_high': zone_high,
                        'zone_range_pct': zone_range_pct,
                        'impulse_size': impulse_up,
                        'age_days': len(prices) - (i + consolidation_bars) - 1,
                        'consolidation_bars': consolidation_bars
                    })
                    # Skip past this zone
                    i += consolidation_bars + 5
                    continue

                # Check for bearish impulse (strong drop from zone)
                impulse_down = (zone_low - future_low) / zone_low * 100
                if impulse_down >= impulse_threshold_pct:
                    # This is a supply zone (resistance)
                    supply_zones.append({
                        'start_index': i,
                        'zone_low': zone_low,
                        'zone_high': zone_high,
                        'zone_range_pct': zone_range_pct,
                        'impulse_size': impulse_down,
                        'age_days': len(prices) - (i + consolidation_bars) - 1,
                        'consolidation_bars': consolidation_bars
                    })
                    # Skip past this zone
                    i += consolidation_bars + 5
                    continue

        i += 1

    # Find closest zones to current price
    closest_demand_zone = None
    closest_supply_zone = None
    distance_to_demand = 100.0
    distance_to_supply = 100.0

    # Find closest demand zone (below current price)
    demand_below = [z for z in demand_zones if z['zone_high'] < current_price]
    if demand_below:
        closest_demand_zone = min(demand_below, key=lambda z: abs(current_price - z['zone_high']))
        distance_to_demand = (current_price - closest_demand_zone['zone_high']) / current_price * 100

    # Find closest supply zone (above current price)
    supply_above = [z for z in supply_zones if z['zone_low'] > current_price]
    if supply_above:
        closest_supply_zone = min(supply_above, key=lambda z: abs(z['zone_low'] - current_price))
        distance_to_supply = (closest_supply_zone['zone_low'] - current_price) / current_price * 100

    # Determine signal based on proximity
    signal = 'NONE'
    interpretation = ''

    if distance_to_demand <= proximity_pct and closest_demand_zone is not None:
        signal = 'DEMAND_ZONE_TEST'
        interpretation = (
            f'Price testing demand zone from {closest_demand_zone["age_days"]} days ago. '
            f'Distance: {distance_to_demand:.2f}%. '
            f'Zone range: ${closest_demand_zone["zone_low"]:.2f} - ${closest_demand_zone["zone_high"]:.2f}. '
            f'Original impulse: +{closest_demand_zone["impulse_size"]:.1f}%. '
            f'Potential support - watch for bounce.'
        )
    elif distance_to_supply <= proximity_pct and closest_supply_zone is not None:
        signal = 'SUPPLY_ZONE_TEST'
        interpretation = (
            f'Price testing supply zone from {closest_supply_zone["age_days"]} days ago. '
            f'Distance: {distance_to_supply:.2f}%. '
            f'Zone range: ${closest_supply_zone["zone_low"]:.2f} - ${closest_supply_zone["zone_high"]:.2f}. '
            f'Original impulse: -{closest_supply_zone["impulse_size"]:.1f}%. '
            f'Potential resistance - watch for rejection.'
        )
    else:
        interpretation = (
            f'No supply/demand zones in proximity. '
            f'Closest demand zone: {distance_to_demand:.1f}% below. '
            f'Closest supply zone: {distance_to_supply:.1f}% above.'
        )

    return {
        'signal': signal,
        'demand_zones': demand_zones,
        'supply_zones': supply_zones,
        'closest_demand_zone': closest_demand_zone,
        'closest_supply_zone': closest_supply_zone,
        'distance_to_demand_pct': distance_to_demand,
        'distance_to_supply_pct': distance_to_supply,
        'interpretation': interpretation
    }


@mcp.tool()
async def get_market_movers(
    category: Literal["gainers", "losers", "most-active"] = "most-active",
    count: int = 25,
    market_session: Literal["regular", "pre-market", "after-hours"] = "regular"
) -> str:
    """Get market movers. market_session only applies to 'most-active'."""
    # URLs for different market movers categories
    YAHOO_MOST_ACTIVE_URL = "https://finance.yahoo.com/most-active"
    YAHOO_PRE_MARKET_URL = "https://finance.yahoo.com/markets/stocks/pre-market"
    YAHOO_AFTER_HOURS_URL = "https://finance.yahoo.com/markets/stocks/after-hours"
    YAHOO_GAINERS_URL = "https://finance.yahoo.com/gainers"
    YAHOO_LOSERS_URL = "https://finance.yahoo.com/losers"

    # Validate and constrain count
    count = min(max(count, 1), 100)

    # Build URLs with direct lookups to avoid dictionary recreation
    params = f"?count={count}&offset=0"

    if category == "most-active":
        if market_session == "regular":
            url = YAHOO_MOST_ACTIVE_URL + params
        elif market_session == "pre-market":
            url = YAHOO_PRE_MARKET_URL + params
        elif market_session == "after-hours":
            url = YAHOO_AFTER_HOURS_URL + params
        else:
            raise ValueError(f"Invalid market session: {market_session}")
    elif category == "gainers":
        url = YAHOO_GAINERS_URL + params
    elif category == "losers":
        url = YAHOO_LOSERS_URL + params
    else:
        raise ValueError(f"Invalid category: {category}")

    logger.info(f"Fetching {category} ({market_session} session) from: {url}")
    response_text = await fetch_text(url, BROWSER_HEADERS)
    tables = pd.read_html(StringIO(response_text))
    if not tables or tables[0].empty:
        return f"No data found for {category}"

    df = tables[0].loc[:, ~tables[0].columns.str.contains('^Unnamed')]
    return to_clean_csv(df.head(count))


@mcp.tool()
async def get_cnn_fear_greed_index(
    indicators: list[
        Literal[
            "fear_and_greed",
            "fear_and_greed_historical",
            "put_call_options",
            "market_volatility_vix",
            "market_volatility_vix_50",
            "junk_bond_demand",
            "safe_haven_demand"
        ]
    ] | None = None
) -> dict:
    CNN_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

    raw_data = await fetch_json(CNN_FEAR_GREED_URL, BROWSER_HEADERS)
    if not raw_data:
        raise ValueError("Empty response data")

    # Remove historical time series data arrays
    result = {
        k: {inner_k: inner_v for inner_k, inner_v in v.items() if inner_k != "data"}
        if isinstance(v, dict) else v
        for k, v in raw_data.items()
        if k != "fear_and_greed_historical"
    }

    # Filter by indicators if specified
    if indicators:
        if invalid := set(indicators) - set(result.keys()):
            raise ValueError(f"Invalid indicators: {list(invalid)}. Available: {list(result.keys())}")
        result = {k: v for k, v in result.items() if k in indicators}

    return result

@mcp.tool()
async def get_crypto_fear_greed_index() -> dict:
    CRYPTO_FEAR_GREED_URL = "https://api.alternative.me/fng/"

    data = await fetch_json(CRYPTO_FEAR_GREED_URL)
    if "data" not in data or not data["data"]:
        raise ValueError("Invalid response format from alternative.me API")

    current_data = data["data"][0]
    return {
        "value": current_data["value"],
        "classification": current_data["value_classification"],
        "timestamp": current_data["timestamp"]
    }

@mcp.tool()
def get_google_trends(
    keywords: list[str],
    period_days: int = 7
) -> str:
    """Get Google Trends relative search interest for specified keywords."""
    from pytrends.request import TrendReq

    logger.info(f"Fetching Google Trends data for {period_days} days")

    timeframe = get_trends_timeframe(period_days)
    pytrends = TrendReq(hl='en-US', tz=360)
    pytrends.build_payload(keywords, timeframe=timeframe)

    df = pytrends.interest_over_time()
    if df.empty:
        raise ValueError("No data returned from Google Trends")

    # Clean and format data
    if 'isPartial' in df.columns:
        df = df[~df['isPartial']].drop('isPartial', axis=1)

    df_reset = df.reset_index()

    return to_clean_csv(df_reset)

@mcp.tool()
def get_ticker_data(
    ticker: str,
    max_news: int = 5,
    max_recommendations: int = 5,
    max_upgrades: int = 5
) -> dict[str, Any]:
    """Get comprehensive ticker data: metrics, calendar, news, recommendations.

    Uses Questrade as primary data source with Yahoo Finance as fallback.
    This ensures better data availability for stocks where Yahoo Finance has gaps.
    """
    ticker = validate_ticker(ticker)

    # Get ticker info using Questrade-first approach
    ticker_info = get_ticker_info_questrade_first(ticker)
    info = ticker_info.get("merged", {})

    if not info:
        raise ValueError(f"No information available for {ticker}")

    essential_fields = {
        'symbol', 'longName', 'currentPrice', 'marketCap', 'volume', 'trailingPE',
        'forwardPE', 'dividendYield', 'beta', 'eps', 'totalRevenue', 'totalDebt',
        'profitMargins', 'operatingMargins', 'returnOnEquity', 'returnOnAssets',
        'revenueGrowth', 'earningsGrowth', 'bookValue', 'priceToBook',
        'enterpriseValue', 'pegRatio', 'trailingEps', 'forwardEps',
        # Additional fields from Questrade
        'previousClose', 'fiftyTwoWeekHigh', 'fiftyTwoWeekLow', 'averageVolume',
        'sharesOutstanding', 'exchange', 'currency', 'sector', 'industry'
    }

    # Basic info section - convert to structured format
    basic_info = [
        {"metric": key, "value": value.isoformat() if hasattr(value, 'isoformat') else value}
        for key, value in info.items() if key in essential_fields
    ]

    # Add data source indicator
    basic_info.append({"metric": "dataSource", "value": ticker_info.get("source", "unknown")})

    result: dict[str, Any] = {"basic_info": basic_info}

    # Get calendar, news, recommendations, upgrades from Yahoo Finance
    # (Questrade doesn't provide these)
    with ThreadPoolExecutor() as executor:
        calendar_future = executor.submit(yf_call, ticker, "get_calendar")
        news_future = executor.submit(yf_call, ticker, "get_news")

        # Process calendar
        calendar = safe_future_result(calendar_future, context=f"fetching calendar for {ticker}")
        if calendar:
            result["calendar"] = [
                {"event": key, "value": value.isoformat() if hasattr(value, 'isoformat') else value}
                for key, value in calendar.items()
            ]

        # Try to get next earnings date specifically (often missing from calendar)
        try:
            t_for_earnings = yf.Ticker(ticker)
            earnings_dates = t_for_earnings.earnings_dates
            if earnings_dates is not None and not earnings_dates.empty:
                from datetime import datetime
                today = datetime.now()
                # Find next earnings date (future dates only)
                future_dates = earnings_dates[earnings_dates.index > today]
                if not future_dates.empty:
                    next_earnings = future_dates.index[0]
                    days_to_earnings = (next_earnings - today).days
                    result["next_earnings"] = {
                        "date": next_earnings.strftime("%Y-%m-%d"),
                        "days_away": days_to_earnings
                    }
                else:
                    # No future dates, get most recent from calendar if available
                    past_dates = earnings_dates[earnings_dates.index <= today]
                    if not past_dates.empty:
                        last_earnings = past_dates.index[0]
                        result["last_earnings"] = {
                            "date": last_earnings.strftime("%Y-%m-%d"),
                            "note": "No future earnings date available"
                        }
        except Exception:
            pass  # Earnings dates not available

        # Process news
        news_items = safe_future_result(news_future, context=f"fetching news for {ticker}")
        if news_items:
            news_items = news_items[:max_news]  # Apply limit
            news_data = []
            for item in news_items:
                content = item.get("content", {})
                raw_date = content.get("pubDate") or content.get("displayTime") or ""

                news_data.append({
                    "date": format_date_string(raw_date),
                    "title": content.get("title") or "Untitled",
                    "source": content.get("provider", {}).get("displayName", "Unknown"),
                    "url": (content.get("canonicalUrl", {}).get("url") or
                            content.get("clickThroughUrl", {}).get("url") or "")
                })

            result["news"] = news_data

    # Get recommendations and upgrades in parallel
    with ThreadPoolExecutor() as executor:
        recommendations_future = executor.submit(yf_call, ticker, "get_recommendations")
        upgrades_future = executor.submit(yf_call, ticker, "get_upgrades_downgrades")

        recommendations = safe_future_result(recommendations_future, context=f"fetching recommendations for {ticker}")
        if isinstance(recommendations, pd.DataFrame) and not recommendations.empty:
            result["recommendations"] = to_clean_csv(recommendations.head(max_recommendations))

        upgrades = safe_future_result(upgrades_future, context=f"fetching upgrades for {ticker}")
        if isinstance(upgrades, pd.DataFrame) and not upgrades.empty:
            upgrades = upgrades.sort_index(ascending=False) if hasattr(upgrades, 'sort_index') else upgrades
            result["upgrades_downgrades"] = to_clean_csv(upgrades.head(max_upgrades))

    return result

@mcp.tool()
def get_options(
    ticker_symbol: str,
    num_options: int = 10,
    start_date: str | None = None,
    end_date: str | None = None,
    strike_lower: float | None = None,
    strike_upper: float | None = None,
    option_type: Literal["C", "P"] | None = None,
) -> str:
    """Get options data. Dates: YYYY-MM-DD. Type: C=calls, P=puts."""
    ticker_symbol = validate_ticker(ticker_symbol)

    try:
        # Validate dates
        validate_date_range(start_date, end_date)

        # Get options expirations - this is a property, not a method
        t = yf.Ticker(ticker_symbol)
        expirations = t.options
        if not expirations:
            raise ValueError(f"No options available for {ticker_symbol}")

        # Filter by date
        valid_expirations = [
            exp for exp in expirations
            if ((not start_date or exp >= start_date) and
                (not end_date or exp <= end_date))
        ]

        if not valid_expirations:
            raise ValueError(f"No options found for {ticker_symbol} within specified date range")

        # Parallel fetch with error handling and timeout
        with ThreadPoolExecutor() as executor:
            futures = [(executor.submit(get_options_chain, ticker_symbol, exp, option_type), exp)
                       for exp in valid_expirations]
            chains = []
            for future, expiry in futures:
                chain = safe_future_result(future, context=f"options chain {ticker_symbol} {expiry}")
                if chain is not None:
                    chains.append(chain.assign(expiryDate=expiry))

        if not chains:
            raise ValueError(f"No options found for {ticker_symbol} matching criteria")

        df = pd.concat(chains, ignore_index=True)

        # Apply strike filters
        if strike_lower is not None:
            df = df[df['strike'] >= strike_lower]
        if strike_upper is not None:
            df = df[df['strike'] <= strike_upper]

        df = df.sort_values(['openInterest', 'volume'], ascending=[False, False])
        df_subset = df.head(num_options)
        return to_clean_csv(df_subset)

    except Exception as e:
        raise ValueError(f"Failed to retrieve options data: {str(e)}")


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
    import numpy as np
    from datetime import datetime, timedelta

    ticker = validate_ticker(ticker)

    try:
        # Get current stock price
        t = yf.Ticker(ticker)
        info = t.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
        if not current_price:
            raise ValueError(f"Could not get current price for {ticker}")

        # Try Questrade first for options chain (more accurate, especially for split-adjusted stocks)
        calls_df = None
        puts_df = None
        nearest_exp = None
        expirations = []
        options_source = "yfinance"

        try:
            from investor_agent.questrade import get_questrade_client
            from questrade_api import Questrade

            qt_client = get_questrade_client()
            symbol_info = qt_client.get_symbol_info(ticker)

            if symbol_info and symbol_info.get('symbols') and symbol_info['symbols'][0].get('hasOptions'):
                symbol_id = symbol_info['symbols'][0]['symbolId']

                # Get Questrade client directly for options
                q = Questrade()
                qt_options = q.symbol_options(symbol_id)

                if qt_options and qt_options.get('optionChain'):
                    # Parse Questrade options chain into DataFrames
                    target_date = datetime.now() + timedelta(days=holding_period_days)

                    # Find nearest expiration
                    exp_dates = [exp['expiryDate'][:10] for exp in qt_options['optionChain']]
                    expirations = exp_dates

                    if exp_dates:
                        nearest_exp = min(exp_dates, key=lambda x: abs(
                            (datetime.strptime(x, '%Y-%m-%d') - target_date).days
                        ))

                        # Get the chain for nearest expiration
                        for exp in qt_options['optionChain']:
                            if exp['expiryDate'].startswith(nearest_exp):
                                # Build calls and puts DataFrames from Questrade data
                                calls_data = []
                                puts_data = []

                                for root in exp.get('chainPerRoot', []):
                                    for strike_info in root.get('chainPerStrikePrice', []):
                                        strike = strike_info['strikePrice']
                                        call_id = strike_info.get('callSymbolId')
                                        put_id = strike_info.get('putSymbolId')

                                        # Get quotes for these options using keyword argument
                                        try:
                                            if call_id:
                                                call_quotes = q.markets_options(optionIds=[call_id])
                                                if call_quotes and call_quotes.get('optionQuotes'):
                                                    cq = call_quotes['optionQuotes'][0]
                                                    calls_data.append({
                                                        'strike': strike,
                                                        'lastPrice': cq.get('lastTradePrice') or 0,
                                                        'bid': cq.get('bidPrice') or 0,
                                                        'ask': cq.get('askPrice') or 0,
                                                        'volume': cq.get('volume') or 0,
                                                        'openInterest': cq.get('openInterest') or 0,
                                                        'impliedVolatility': cq.get('volatility') or 0.3,
                                                        'delta': cq.get('delta') or 0,
                                                        'gamma': cq.get('gamma') or 0,
                                                        'theta': cq.get('theta') or 0,
                                                        'vega': cq.get('vega') or 0
                                                    })
                                            if put_id:
                                                put_quotes = q.markets_options(optionIds=[put_id])
                                                if put_quotes and put_quotes.get('optionQuotes'):
                                                    pq = put_quotes['optionQuotes'][0]
                                                    puts_data.append({
                                                        'strike': strike,
                                                        'lastPrice': pq.get('lastTradePrice') or 0,
                                                        'bid': pq.get('bidPrice') or 0,
                                                        'ask': pq.get('askPrice') or 0,
                                                        'volume': pq.get('volume') or 0,
                                                        'openInterest': pq.get('openInterest') or 0,
                                                        'impliedVolatility': pq.get('volatility') or 0.3,
                                                        'delta': pq.get('delta') or 0,
                                                        'gamma': pq.get('gamma') or 0,
                                                        'theta': pq.get('theta') or 0,
                                                        'vega': pq.get('vega') or 0
                                                    })
                                        except Exception:
                                            pass  # Skip individual option quote errors

                                if calls_data or puts_data:
                                    calls_df = pd.DataFrame(calls_data) if calls_data else pd.DataFrame()
                                    puts_df = pd.DataFrame(puts_data) if puts_data else pd.DataFrame()
                                    options_source = "questrade"
                                    logger.info(f"Using Questrade options data for {ticker}")
                                break
        except Exception as qt_err:
            logger.warning(f"Questrade options unavailable for {ticker}: {qt_err}")

        # Fall back to yfinance if Questrade didn't work
        if calls_df is None or (calls_df.empty if hasattr(calls_df, 'empty') else True):
            logger.info(f"Falling back to yfinance for {ticker} options")
            expirations = t.options
            if not expirations:
                raise ValueError(f"No options available for {ticker}")

            target_date = datetime.now() + timedelta(days=holding_period_days)
            nearest_exp = min(expirations, key=lambda x: abs(
                (datetime.strptime(x, '%Y-%m-%d') - target_date).days
            ))

            chain = t.option_chain(nearest_exp)
            calls_df = chain.calls
            puts_df = chain.puts
            options_source = "yfinance"

            # Validate yfinance data - check if strikes are reasonable vs price
            if not calls_df.empty:
                min_strike = calls_df['strike'].min()
                max_strike = calls_df['strike'].max()
                # If strikes are way off (like 3x+ away from price), data is bad
                if min_strike > current_price * 2 or max_strike < current_price * 0.5:
                    logger.warning(f"yfinance options data appears invalid for {ticker}: strikes {min_strike}-{max_strike} vs price {current_price}")
                    raise ValueError(f"Invalid options data for {ticker} (possible split adjustment issue)")

        if (calls_df is None or (hasattr(calls_df, 'empty') and calls_df.empty)) and \
           (puts_df is None or (hasattr(puts_df, 'empty') and puts_df.empty)):
            raise ValueError(f"No options data for {ticker} at {nearest_exp}")

        # ============================================================
        # 1. IV ANALYSIS (McMillan Ch. 28: Volatility Trading)
        # ============================================================
        iv_analysis = _calculate_iv_analysis(ticker, calls_df, puts_df, current_price)

        # ============================================================
        # 2. PUT/CALL RATIO ANALYSIS (McMillan Ch. 24: Stock Option Strategies)
        # ============================================================
        pc_ratio_analysis = _calculate_pc_ratio(calls_df, puts_df)

        # ============================================================
        # 3. OPEN INTEREST ANALYSIS (McMillan Ch. 25: Index Option Strategies)
        # ============================================================
        oi_analysis = _calculate_oi_analysis(calls_df, puts_df, current_price)

        # ============================================================
        # 4. UNUSUAL OPTIONS ACTIVITY (McMillan Ch. 36: Portfolio Management)
        # ============================================================
        uoa_analysis = _detect_unusual_activity(calls_df, puts_df, current_price)

        # ============================================================
        # 5. GREEKS ASSESSMENT (Try Questrade for accurate Greeks)
        # ============================================================
        greeks_analysis = None
        if use_questrade_greeks:
            try:
                greeks_analysis = _get_questrade_greeks(ticker, nearest_exp, current_price)
            except Exception as e:
                logger.warning(f"Questrade Greeks unavailable: {e}")

        if greeks_analysis is None:
            # Fallback to yfinance Greeks (less accurate but available)
            greeks_analysis = _estimate_greeks_from_chain(calls_df, puts_df, current_price)

        # ============================================================
        # 6. STRATEGY SELECTION MATRIX (McMillan Core Framework)
        # ============================================================
        strategy_recommendation = _select_mcmillan_strategy(
            direction=direction,
            iv_rank=iv_analysis['iv_rank'],
            iv_percentile=iv_analysis['iv_percentile'],
            current_price=current_price,
            holding_period_days=holding_period_days,
            calls_df=calls_df,
            puts_df=puts_df
        )

        # ============================================================
        # 7. COMPOSITE SCORE & RECOMMENDATION
        # ============================================================
        composite_score = _calculate_options_composite_score(
            iv_analysis=iv_analysis,
            pc_ratio_analysis=pc_ratio_analysis,
            oi_analysis=oi_analysis,
            uoa_analysis=uoa_analysis,
            direction=direction
        )

        return {
            "ticker": ticker,
            "current_price": current_price,
            "analysis_date": datetime.now().strftime('%Y-%m-%d %H:%M'),
            "direction": direction,
            "holding_period_days": holding_period_days,
            "nearest_expiration": nearest_exp,
            "available_expirations": expirations[:5],  # First 5 expirations

            # McMillan Analysis Components
            "iv_analysis": iv_analysis,
            "put_call_ratio": pc_ratio_analysis,
            "open_interest": oi_analysis,
            "unusual_activity": uoa_analysis,
            "greeks_assessment": greeks_analysis,

            # Strategy Recommendation
            "strategy_recommendation": strategy_recommendation,

            # Composite Score
            "composite_score": composite_score,

            # Quick Summary
            "summary": {
                "iv_environment": iv_analysis['iv_environment'],
                "sentiment": pc_ratio_analysis['sentiment'],
                "smart_money_signal": uoa_analysis['smart_money_signal'],
                "recommended_strategy": strategy_recommendation['primary_strategy'],
                "confidence": composite_score['confidence'],
                "score": composite_score['total_score']
            },

            "methodology": "McMillan - Options as a Strategic Investment (5th Ed.)"
        }

    except Exception as e:
        logger.error(f"Error in analyze_options_mcmillan for {ticker}: {e}")
        raise ValueError(f"McMillan options analysis failed: {str(e)}")


def _calculate_iv_analysis(ticker: str, calls_df: pd.DataFrame, puts_df: pd.DataFrame, current_price: float) -> dict:
    """Calculate IV Rank and IV Percentile per McMillan methodology."""
    import numpy as np

    # Get ATM options for IV
    atm_calls = calls_df[abs(calls_df['strike'] - current_price) == abs(calls_df['strike'] - current_price).min()]
    atm_puts = puts_df[abs(puts_df['strike'] - current_price) == abs(puts_df['strike'] - current_price).min()]

    # Current IV (average of ATM call and put)
    current_iv = None
    if 'impliedVolatility' in atm_calls.columns and not atm_calls.empty:
        call_iv = atm_calls['impliedVolatility'].iloc[0] if not atm_calls['impliedVolatility'].isna().all() else None
        put_iv = atm_puts['impliedVolatility'].iloc[0] if not atm_puts.empty and not atm_puts['impliedVolatility'].isna().all() else None

        # Normalize IV to decimal form (0.30 for 30%)
        # Questrade returns IV as percentage (30.0), yfinance as decimal (0.30)
        def normalize_to_decimal(iv_val):
            if iv_val is None or pd.isna(iv_val):
                return None
            iv_val = float(iv_val)
            if iv_val > 1.5:  # Likely already percentage form (e.g. 30.0 for 30%)
                return iv_val / 100
            return iv_val

        call_iv = normalize_to_decimal(call_iv)
        put_iv = normalize_to_decimal(put_iv)

        if call_iv and put_iv:
            current_iv = (call_iv + put_iv) / 2
        elif call_iv:
            current_iv = call_iv
        elif put_iv:
            current_iv = put_iv

    if current_iv is None:
        current_iv = 0.30  # Default 30% if unavailable

    # Get historical IV data (use price history to estimate)
    try:
        hist = _get_ohlcv_cached(ticker, period="1y")
        if hist is not None and not hist.empty:
            # Calculate historical volatility as proxy for IV range
            returns = np.log(hist['Close'] / hist['Close'].shift(1)).dropna()
            hv_20 = returns.rolling(20).std() * np.sqrt(252)
            hv_values = hv_20.dropna().values

            if len(hv_values) > 0:
                iv_52w_high = np.percentile(hv_values, 95)
                iv_52w_low = np.percentile(hv_values, 5)

                # IV Rank = (Current IV - 52w Low) / (52w High - 52w Low)
                iv_range = iv_52w_high - iv_52w_low
                iv_rank = ((current_iv - iv_52w_low) / iv_range * 100) if iv_range > 0 else 50

                # IV Percentile = % of days IV was lower than current
                iv_percentile = (hv_values < current_iv).sum() / len(hv_values) * 100
            else:
                iv_rank = 50
                iv_percentile = 50
                iv_52w_high = current_iv * 1.5
                iv_52w_low = current_iv * 0.5
        else:
            iv_rank = 50
            iv_percentile = 50
            iv_52w_high = current_iv * 1.5
            iv_52w_low = current_iv * 0.5
    except Exception:
        iv_rank = 50
        iv_percentile = 50
        iv_52w_high = current_iv * 1.5
        iv_52w_low = current_iv * 0.5

    # Determine IV environment
    if iv_rank >= 70:
        iv_environment = "HIGH_IV"
        iv_interpretation = "IV is elevated - favor selling premium strategies"
    elif iv_rank <= 30:
        iv_environment = "LOW_IV"
        iv_interpretation = "IV is low - favor buying premium strategies"
    else:
        iv_environment = "NORMAL_IV"
        iv_interpretation = "IV is normal - flexible strategy selection"

    return {
        "current_iv": round(current_iv * 100, 1),
        "iv_rank": round(max(0, min(100, iv_rank)), 1),
        "iv_percentile": round(max(0, min(100, iv_percentile)), 1),
        "iv_52w_high": round(iv_52w_high * 100, 1),
        "iv_52w_low": round(iv_52w_low * 100, 1),
        "iv_environment": iv_environment,
        "interpretation": iv_interpretation,
        "mcmillan_reference": "Chapter 28: Volatility Trading"
    }


def _calculate_pc_ratio(calls_df: pd.DataFrame, puts_df: pd.DataFrame) -> dict:
    """Calculate Put/Call ratio analysis per McMillan methodology."""
    # Volume-based P/C ratio
    call_volume = calls_df['volume'].sum() if 'volume' in calls_df.columns else 0
    put_volume = puts_df['volume'].sum() if 'volume' in puts_df.columns else 0
    volume_pc_ratio = put_volume / call_volume if call_volume > 0 else 1.0

    # Open Interest-based P/C ratio
    call_oi = calls_df['openInterest'].sum() if 'openInterest' in calls_df.columns else 0
    put_oi = puts_df['openInterest'].sum() if 'openInterest' in puts_df.columns else 0
    oi_pc_ratio = put_oi / call_oi if call_oi > 0 else 1.0

    # McMillan interpretation (contrarian indicator)
    # High P/C = Bearish sentiment = Contrarian Bullish
    # Low P/C = Bullish sentiment = Contrarian Bearish
    if volume_pc_ratio > 1.2:
        sentiment = "EXTREMELY_BEARISH"
        contrarian_signal = "BULLISH"
        interpretation = "Extreme put buying suggests fear - contrarian bullish signal"
    elif volume_pc_ratio > 0.9:
        sentiment = "BEARISH"
        contrarian_signal = "SLIGHTLY_BULLISH"
        interpretation = "Elevated put activity - moderate contrarian bullish"
    elif volume_pc_ratio < 0.5:
        sentiment = "EXTREMELY_BULLISH"
        contrarian_signal = "BEARISH"
        interpretation = "Extreme call buying suggests greed - contrarian bearish signal"
    elif volume_pc_ratio < 0.7:
        sentiment = "BULLISH"
        contrarian_signal = "SLIGHTLY_BEARISH"
        interpretation = "Elevated call activity - moderate contrarian bearish"
    else:
        sentiment = "NEUTRAL"
        contrarian_signal = "NEUTRAL"
        interpretation = "P/C ratio in neutral zone - no strong signal"

    return {
        "volume_pc_ratio": round(volume_pc_ratio, 3),
        "oi_pc_ratio": round(oi_pc_ratio, 3),
        "call_volume": int(call_volume),
        "put_volume": int(put_volume),
        "call_oi": int(call_oi),
        "put_oi": int(put_oi),
        "sentiment": sentiment,
        "contrarian_signal": contrarian_signal,
        "interpretation": interpretation,
        "mcmillan_reference": "Chapter 24: Stock Option Strategies"
    }


def _calculate_oi_analysis(calls_df: pd.DataFrame, puts_df: pd.DataFrame, current_price: float) -> dict:
    """Analyze Open Interest for max pain and positioning."""
    import numpy as np

    # Find max pain (strike where options sellers profit most)
    all_strikes = sorted(set(calls_df['strike'].tolist() + puts_df['strike'].tolist()))

    max_pain_strike = current_price
    min_pain_value = float('inf')

    for strike in all_strikes:
        # Calculate pain at this strike
        call_pain = 0
        put_pain = 0

        # Call pain: sum of (strike - exercise_strike) * OI for all ITM calls
        itm_calls = calls_df[calls_df['strike'] < strike]
        if not itm_calls.empty and 'openInterest' in itm_calls.columns:
            call_pain = ((strike - itm_calls['strike']) * itm_calls['openInterest']).sum()

        # Put pain: sum of (exercise_strike - strike) * OI for all ITM puts
        itm_puts = puts_df[puts_df['strike'] > strike]
        if not itm_puts.empty and 'openInterest' in itm_puts.columns:
            put_pain = ((itm_puts['strike'] - strike) * itm_puts['openInterest']).sum()

        total_pain = call_pain + put_pain
        if total_pain < min_pain_value:
            min_pain_value = total_pain
            max_pain_strike = strike

    # Find highest OI strikes (important levels)
    top_call_strikes = calls_df.nlargest(3, 'openInterest')[['strike', 'openInterest']].to_dict('records') if 'openInterest' in calls_df.columns else []
    top_put_strikes = puts_df.nlargest(3, 'openInterest')[['strike', 'openInterest']].to_dict('records') if 'openInterest' in puts_df.columns else []

    # Max pain interpretation
    distance_to_max_pain = (max_pain_strike - current_price) / current_price * 100
    if abs(distance_to_max_pain) < 2:
        oi_bias = "NEUTRAL"
        interpretation = "Price near max pain - likely to stay range-bound into expiration"
    elif distance_to_max_pain > 2:
        oi_bias = "BULLISH"
        interpretation = f"Max pain {distance_to_max_pain:.1f}% above price - gravitational pull higher"
    else:
        oi_bias = "BEARISH"
        interpretation = f"Max pain {abs(distance_to_max_pain):.1f}% below price - gravitational pull lower"

    return {
        "max_pain_strike": max_pain_strike,
        "distance_to_max_pain_pct": round(distance_to_max_pain, 2),
        "top_call_oi_strikes": top_call_strikes,
        "top_put_oi_strikes": top_put_strikes,
        "oi_bias": oi_bias,
        "interpretation": interpretation,
        "mcmillan_reference": "Chapter 25: Index Option Strategies"
    }


def _detect_unusual_activity(calls_df: pd.DataFrame, puts_df: pd.DataFrame, current_price: float) -> dict:
    """Detect unusual options activity (smart money signals)."""
    unusual_trades = []

    # Check for volume > OI (indicates new positions)
    for df, opt_type in [(calls_df, 'CALL'), (puts_df, 'PUT')]:
        if 'volume' in df.columns and 'openInterest' in df.columns:
            # Unusual: Volume > 2x OI
            unusual = df[(df['volume'] > df['openInterest'] * 2) & (df['volume'] > 100)]
            for _, row in unusual.iterrows():
                unusual_trades.append({
                    'type': opt_type,
                    'strike': row['strike'],
                    'volume': int(row['volume']),
                    'oi': int(row['openInterest']),
                    'volume_oi_ratio': round(row['volume'] / max(row['openInterest'], 1), 1),
                    'moneyness': 'ITM' if (opt_type == 'CALL' and row['strike'] < current_price) or
                                          (opt_type == 'PUT' and row['strike'] > current_price) else 'OTM'
                })

    # Sort by volume/OI ratio
    unusual_trades.sort(key=lambda x: x['volume_oi_ratio'], reverse=True)
    unusual_trades = unusual_trades[:5]  # Top 5

    # Determine smart money signal
    if not unusual_trades:
        smart_money_signal = "NO_SIGNAL"
        interpretation = "No unusual options activity detected"
    else:
        call_unusual = sum(1 for t in unusual_trades if t['type'] == 'CALL')
        put_unusual = sum(1 for t in unusual_trades if t['type'] == 'PUT')

        if call_unusual > put_unusual * 2:
            smart_money_signal = "BULLISH"
            interpretation = f"Unusual call activity ({call_unusual} trades) suggests smart money bullish positioning"
        elif put_unusual > call_unusual * 2:
            smart_money_signal = "BEARISH"
            interpretation = f"Unusual put activity ({put_unusual} trades) suggests smart money bearish positioning"
        else:
            smart_money_signal = "MIXED"
            interpretation = f"Mixed unusual activity ({call_unusual} calls, {put_unusual} puts)"

    return {
        "unusual_trades": unusual_trades,
        "unusual_trade_count": len(unusual_trades),
        "smart_money_signal": smart_money_signal,
        "interpretation": interpretation,
        "mcmillan_reference": "Chapter 36: Portfolio Management"
    }


def _get_questrade_greeks(ticker: str, expiration: str, current_price: float) -> dict | None:
    """Get Greeks from Questrade API for more accurate data."""
    try:
        client = get_questrade_client()
        options_chain = client.get_options_chain(ticker)

        if not options_chain or 'optionChain' not in options_chain:
            return None

        # Find ATM options and get their Greeks
        # This requires additional API calls to get option quotes with Greeks
        # For now, return a placeholder indicating Questrade is available
        return {
            "source": "questrade",
            "status": "available",
            "note": "Use get_questrade_option_quotes() with specific option IDs for detailed Greeks",
            "available_expirations": [exp.get('expiryDate') for exp in options_chain.get('optionChain', [])[:5]]
        }

    except Exception as e:
        logger.warning(f"Questrade Greeks unavailable: {e}")
        return None


def _calculate_black_scholes_greeks(
    S: float,  # Current stock price
    K: float,  # Strike price
    T: float,  # Time to expiration in years
    r: float,  # Risk-free rate (annual)
    sigma: float,  # Implied volatility (annual)
    option_type: str = "call"  # "call" or "put"
) -> dict:
    """
    Calculate option Greeks using Black-Scholes model.

    Reference: Hull, J.C. "Options, Futures, and Other Derivatives"

    Returns:
        dict with delta, gamma, theta (daily), vega (per 1% IV change)
    """
    import numpy as np
    from scipy.stats import norm

    # Handle edge cases
    if T <= 0 or sigma <= 0:
        return {"delta": 0.5 if option_type == "call" else -0.5,
                "gamma": 0, "theta": 0, "vega": 0}

    # Calculate d1 and d2
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    # Standard normal CDF and PDF
    N_d1 = norm.cdf(d1)
    N_d2 = norm.cdf(d2)
    n_d1 = norm.pdf(d1)  # Standard normal PDF

    # Greeks calculation
    if option_type == "call":
        delta = N_d1
        theta = (-(S * sigma * n_d1) / (2 * sqrt_T)
                 - r * K * np.exp(-r * T) * N_d2)
    else:  # put
        delta = N_d1 - 1
        theta = (-(S * sigma * n_d1) / (2 * sqrt_T)
                 + r * K * np.exp(-r * T) * norm.cdf(-d2))

    # Gamma and Vega are same for calls and puts
    gamma = n_d1 / (S * sigma * sqrt_T)
    vega = S * sqrt_T * n_d1 / 100  # Per 1% IV change

    # Convert theta to daily (divide by 365)
    theta_daily = theta / 365

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta_daily, 4),  # Daily theta
        "vega": round(vega, 4)  # Per 1% IV change
    }


def _estimate_greeks_from_chain(calls_df: pd.DataFrame, puts_df: pd.DataFrame, current_price: float) -> dict:
    """
    Estimate Greeks from yfinance chain data.

    If Greeks are not in the chain, calculates them using Black-Scholes model.
    Uses the ATM (At-The-Money) options for analysis.
    """
    import numpy as np
    from datetime import datetime

    greeks = {
        "source": "calculated_black_scholes",
        "note": "Greeks calculated using Black-Scholes model from IV and time to expiry"
    }

    try:
        # Get ATM options (closest strike to current price)
        if calls_df.empty or puts_df.empty:
            return {"source": "unavailable", "note": "No options data available"}

        atm_calls = calls_df.loc[calls_df['strike'].sub(current_price).abs().idxmin():calls_df['strike'].sub(current_price).abs().idxmin()]
        atm_puts = puts_df.loc[puts_df['strike'].sub(current_price).abs().idxmin():puts_df['strike'].sub(current_price).abs().idxmin()]

        if atm_calls.empty or atm_puts.empty:
            return {"source": "unavailable", "note": "Could not find ATM options"}

        # Get ATM strike and IV
        atm_call = atm_calls.iloc[0]
        atm_put = atm_puts.iloc[0]

        strike = atm_call['strike']
        call_iv = atm_call.get('impliedVolatility', 0.3)  # Default to 30% IV
        put_iv = atm_put.get('impliedVolatility', 0.3)

        # Handle NaN IV values and suspiciously low IVs
        # yfinance sometimes returns IV as decimal (0.30) but sometimes as percentage (30)
        # If IV < 0.05 (5%), it's likely in decimal form and we should use a default
        # If IV > 1.5 (150%), it's likely a data error
        def normalize_iv(iv_value, default=0.3):
            if pd.isna(iv_value) or iv_value is None or iv_value <= 0:
                return default
            if iv_value < 0.05:  # Less than 5% - likely bad data or needs conversion
                return default
            if iv_value > 1.5:  # More than 150% - likely bad data
                return default
            return float(iv_value)

        call_iv = normalize_iv(call_iv)
        put_iv = normalize_iv(put_iv)

        # Calculate time to expiration
        # Try to get expiration from dataframe index or assume 30 days
        T = 30 / 365  # Default: 30 days

        # Check if 'lastTradeDate' column exists to estimate time
        if 'lastTradeDate' in calls_df.columns:
            try:
                # Get contract name which often contains expiry
                contract = atm_call.get('contractSymbol', '')
                if contract:
                    # Extract date from contract symbol (format varies)
                    pass  # Use default T if we can't parse
            except Exception:
                pass

        # Risk-free rate (approximate from current Fed funds rate)
        r = 0.045  # 4.5% annual risk-free rate

        # First check if yfinance already provides Greeks
        greek_cols = ['delta', 'gamma', 'theta', 'vega']
        have_chain_greeks = all(col in atm_call.index and pd.notna(atm_call.get(col)) for col in greek_cols)

        # Helper to safely extract Greek value
        def safe_greek(row, col, default=0.0):
            val = row.get(col)
            if pd.isna(val) or val is None or val == 0:
                return None  # Return None to indicate need for calculation
            return float(val)

        # Check if we have valid chain Greeks (not NaN or zero)
        call_greeks_valid = all(safe_greek(atm_call, col) is not None for col in greek_cols)
        put_greeks_valid = all(safe_greek(atm_put, col) is not None for col in greek_cols)

        if have_chain_greeks and call_greeks_valid:
            # Use chain Greeks for calls if valid
            greeks["source"] = "yfinance_chain"
            greeks["atm_call_delta"] = round(float(atm_call['delta']), 4)
            greeks["atm_call_gamma"] = round(float(atm_call['gamma']), 6)
            greeks["atm_call_theta"] = round(float(atm_call['theta']), 4)
            greeks["atm_call_vega"] = round(float(atm_call['vega']), 4)
        else:
            # Calculate call Greeks using Black-Scholes
            call_bs = _calculate_black_scholes_greeks(
                S=current_price, K=strike, T=T, r=r, sigma=call_iv, option_type="call"
            )
            greeks["source"] = "calculated_black_scholes"
            greeks["atm_call_delta"] = call_bs["delta"]
            greeks["atm_call_gamma"] = call_bs["gamma"]
            greeks["atm_call_theta"] = call_bs["theta"]
            greeks["atm_call_vega"] = call_bs["vega"]

        if have_chain_greeks and put_greeks_valid:
            # Use chain Greeks for puts if valid
            greeks["atm_put_delta"] = round(float(atm_put['delta']), 4)
            greeks["atm_put_gamma"] = round(float(atm_put['gamma']), 6)
            greeks["atm_put_theta"] = round(float(atm_put['theta']), 4)
            greeks["atm_put_vega"] = round(float(atm_put['vega']), 4)
        else:
            # Calculate put Greeks using Black-Scholes (common case - yfinance often has 0 for puts)
            put_bs = _calculate_black_scholes_greeks(
                S=current_price, K=strike, T=T, r=r, sigma=put_iv, option_type="put"
            )
            greeks["atm_put_delta"] = put_bs["delta"]
            greeks["atm_put_gamma"] = put_bs["gamma"]
            greeks["atm_put_theta"] = put_bs["theta"]
            greeks["atm_put_vega"] = put_bs["vega"]
            if "source" not in greeks or greeks["source"] == "yfinance_chain":
                greeks["source"] = "mixed_chain_and_calculated"

        # Add IV for reference
        greeks["atm_call_impliedVolatility"] = round(float(call_iv), 4)
        greeks["atm_put_impliedVolatility"] = round(float(put_iv), 4)

        # Add interpretation
        greeks["interpretation"] = {
            "delta_exposure": f"Call: {greeks['atm_call_delta']:+.2f} = {abs(greeks['atm_call_delta'])*100:.0f}% ITM probability",
            "gamma_risk": "HIGH - near ATM, delta can change rapidly" if abs(greeks.get('atm_call_gamma', 0)) > 0.05 else "MODERATE - stable delta",
            "theta_burn": f"${abs(greeks.get('atm_call_theta', 0)):.2f}/day decay" if greeks.get('atm_call_theta') else "N/A",
            "vega_sensitivity": f"${abs(greeks.get('atm_call_vega', 0)):.2f} per 1% IV change"
        }

    except Exception as e:
        logger.warning(f"Error calculating Greeks: {e}")
        greeks = {
            "source": "error",
            "note": f"Could not calculate Greeks: {str(e)}"
        }

    return greeks


def _select_mcmillan_strategy(
    direction: str,
    iv_rank: float,
    iv_percentile: float,
    current_price: float,
    holding_period_days: int,
    calls_df: pd.DataFrame,
    puts_df: pd.DataFrame
) -> dict:
    """Select optimal strategy using McMillan's Strategy Selection Matrix."""

    # McMillan Strategy Selection Matrix
    # Based on IV environment + Directional bias

    strategies = []

    # HIGH IV (>70) - Favor selling premium
    if iv_rank >= 70:
        if direction == "LONG":
            strategies = [
                {"name": "Short Put", "type": "credit", "risk": "moderate", "max_profit": "premium", "max_loss": "strike - premium"},
                {"name": "Bull Put Spread", "type": "credit", "risk": "defined", "max_profit": "net credit", "max_loss": "spread width - credit"},
                {"name": "Covered Call", "type": "income", "risk": "stock ownership", "max_profit": "premium + (strike - stock price)", "max_loss": "stock price - premium"}
            ]
            primary = "Bull Put Spread (Credit)"
            rationale = "High IV favors selling premium. Bull put spread defines risk while collecting elevated premium."

        elif direction == "SHORT":
            strategies = [
                {"name": "Short Call", "type": "credit", "risk": "unlimited", "max_profit": "premium", "max_loss": "unlimited"},
                {"name": "Bear Call Spread", "type": "credit", "risk": "defined", "max_profit": "net credit", "max_loss": "spread width - credit"},
                {"name": "Protective Put + Short Stock", "type": "hedged", "risk": "defined", "max_profit": "stock decline - premium", "max_loss": "premium"}
            ]
            primary = "Bear Call Spread (Credit)"
            rationale = "High IV favors selling premium. Bear call spread defines risk while collecting elevated premium."

        else:  # NEUTRAL
            strategies = [
                {"name": "Iron Condor", "type": "credit", "risk": "defined", "max_profit": "net credit", "max_loss": "wing width - credit"},
                {"name": "Short Strangle", "type": "credit", "risk": "undefined", "max_profit": "premium", "max_loss": "unlimited"},
                {"name": "Short Straddle", "type": "credit", "risk": "undefined", "max_profit": "premium", "max_loss": "unlimited"}
            ]
            primary = "Iron Condor"
            rationale = "High IV + neutral outlook ideal for iron condor. Collect premium from both sides with defined risk."

    # LOW IV (<30) - Favor buying premium
    elif iv_rank <= 30:
        if direction == "LONG":
            strategies = [
                {"name": "Long Call", "type": "debit", "risk": "defined", "max_profit": "unlimited", "max_loss": "premium"},
                {"name": "Bull Call Spread", "type": "debit", "risk": "defined", "max_profit": "spread width - debit", "max_loss": "net debit"},
                {"name": "LEAPS Call", "type": "debit", "risk": "defined", "max_profit": "unlimited", "max_loss": "premium"}
            ]
            primary = "Long Call or Bull Call Spread"
            rationale = "Low IV makes buying options cheap. Long calls for conviction, spreads for cost reduction."

        elif direction == "SHORT":
            strategies = [
                {"name": "Long Put", "type": "debit", "risk": "defined", "max_profit": "strike - premium", "max_loss": "premium"},
                {"name": "Bear Put Spread", "type": "debit", "risk": "defined", "max_profit": "spread width - debit", "max_loss": "net debit"},
                {"name": "Put Backspread", "type": "debit/credit", "risk": "defined upside", "max_profit": "large on big move", "max_loss": "limited"}
            ]
            primary = "Long Put or Bear Put Spread"
            rationale = "Low IV makes buying options cheap. Long puts for conviction, spreads for cost reduction."

        else:  # NEUTRAL
            strategies = [
                {"name": "Long Straddle", "type": "debit", "risk": "defined", "max_profit": "unlimited", "max_loss": "premium"},
                {"name": "Long Strangle", "type": "debit", "risk": "defined", "max_profit": "unlimited", "max_loss": "premium"},
                {"name": "Calendar Spread", "type": "debit", "risk": "defined", "max_profit": "front month decay", "max_loss": "net debit"}
            ]
            primary = "Long Straddle or Calendar Spread"
            rationale = "Low IV with neutral outlook suggests volatility expansion expected. Long vol strategies benefit."

    # NORMAL IV (30-70) - Flexible
    else:
        if direction == "LONG":
            strategies = [
                {"name": "Bull Call Spread", "type": "debit", "risk": "defined", "max_profit": "spread width - debit", "max_loss": "net debit"},
                {"name": "Call Diagonal", "type": "debit", "risk": "defined", "max_profit": "variable", "max_loss": "net debit"},
                {"name": "Long Call", "type": "debit", "risk": "defined", "max_profit": "unlimited", "max_loss": "premium"}
            ]
            primary = "Bull Call Spread"
            rationale = "Normal IV allows flexibility. Bull call spread balances cost and reward."

        elif direction == "SHORT":
            strategies = [
                {"name": "Bear Put Spread", "type": "debit", "risk": "defined", "max_profit": "spread width - debit", "max_loss": "net debit"},
                {"name": "Put Diagonal", "type": "debit", "risk": "defined", "max_profit": "variable", "max_loss": "net debit"},
                {"name": "Long Put", "type": "debit", "risk": "defined", "max_profit": "strike - premium", "max_loss": "premium"}
            ]
            primary = "Bear Put Spread"
            rationale = "Normal IV allows flexibility. Bear put spread balances cost and reward."

        else:  # NEUTRAL
            strategies = [
                {"name": "Iron Butterfly", "type": "credit", "risk": "defined", "max_profit": "net credit", "max_loss": "wing width - credit"},
                {"name": "Calendar Spread", "type": "debit", "risk": "defined", "max_profit": "front month decay", "max_loss": "net debit"},
                {"name": "Double Diagonal", "type": "mixed", "risk": "defined", "max_profit": "time decay", "max_loss": "net debit"}
            ]
            primary = "Iron Butterfly or Calendar Spread"
            rationale = "Normal IV with neutral outlook. Iron butterfly for premium, calendar for time decay."

    # Calculate suggested strikes based on ATM
    atm_strike = round(current_price / 5) * 5  # Round to nearest $5

    return {
        "primary_strategy": primary,
        "rationale": rationale,
        "alternative_strategies": strategies,
        "suggested_strikes": {
            "atm": atm_strike,
            "otm_call": atm_strike + 5,
            "otm_put": atm_strike - 5,
            "deep_otm_call": atm_strike + 10,
            "deep_otm_put": atm_strike - 10
        },
        "iv_environment": "HIGH" if iv_rank >= 70 else "LOW" if iv_rank <= 30 else "NORMAL",
        "mcmillan_reference": "Chapter 1-10: Basic Option Strategies"
    }


def _calculate_options_composite_score(
    iv_analysis: dict,
    pc_ratio_analysis: dict,
    oi_analysis: dict,
    uoa_analysis: dict,
    direction: str
) -> dict:
    """Calculate composite options score for the given direction."""

    score = 50  # Start neutral
    factors = []

    # IV Factor (±15 points)
    iv_rank = iv_analysis['iv_rank']
    if direction in ["LONG", "SHORT"]:
        if iv_rank <= 30:
            score += 10
            factors.append(f"Low IV ({iv_rank:.0f}) favors buying premium: +10")
        elif iv_rank >= 70:
            score += 5
            factors.append(f"High IV ({iv_rank:.0f}) good for selling premium: +5")
    else:  # NEUTRAL
        if 30 <= iv_rank <= 70:
            score += 10
            factors.append(f"Normal IV ({iv_rank:.0f}) ideal for neutral strategies: +10")

    # P/C Ratio Factor (±15 points) - Contrarian
    if direction == "LONG":
        if pc_ratio_analysis['contrarian_signal'] in ["BULLISH", "SLIGHTLY_BULLISH"]:
            score += 15
            factors.append(f"P/C ratio contrarian bullish: +15")
        elif pc_ratio_analysis['contrarian_signal'] in ["BEARISH", "SLIGHTLY_BEARISH"]:
            score -= 10
            factors.append(f"P/C ratio contrarian bearish: -10")
    elif direction == "SHORT":
        if pc_ratio_analysis['contrarian_signal'] in ["BEARISH", "SLIGHTLY_BEARISH"]:
            score += 15
            factors.append(f"P/C ratio contrarian bearish: +15")
        elif pc_ratio_analysis['contrarian_signal'] in ["BULLISH", "SLIGHTLY_BULLISH"]:
            score -= 10
            factors.append(f"P/C ratio contrarian bullish: -10")

    # OI/Max Pain Factor (±10 points)
    if direction == "LONG" and oi_analysis['oi_bias'] == "BULLISH":
        score += 10
        factors.append(f"Max pain above price (gravitational pull higher): +10")
    elif direction == "SHORT" and oi_analysis['oi_bias'] == "BEARISH":
        score += 10
        factors.append(f"Max pain below price (gravitational pull lower): +10")
    elif oi_analysis['oi_bias'] == "NEUTRAL":
        score += 5
        factors.append(f"Price near max pain (range-bound): +5")

    # Unusual Activity Factor (±15 points)
    if direction == "LONG" and uoa_analysis['smart_money_signal'] == "BULLISH":
        score += 15
        factors.append(f"Smart money bullish positioning: +15")
    elif direction == "SHORT" and uoa_analysis['smart_money_signal'] == "BEARISH":
        score += 15
        factors.append(f"Smart money bearish positioning: +15")
    elif uoa_analysis['smart_money_signal'] == "MIXED":
        factors.append(f"Mixed smart money signals: +0")

    # Cap score
    score = max(0, min(100, score))

    # Determine confidence
    if score >= 80:
        confidence = "HIGH"
    elif score >= 65:
        confidence = "MODERATE"
    elif score >= 50:
        confidence = "LOW"
    else:
        confidence = "VERY_LOW"

    return {
        "total_score": score,
        "confidence": confidence,
        "factors": factors,
        "interpretation": f"Options analysis {'strongly supports' if score >= 80 else 'supports' if score >= 65 else 'is neutral on' if score >= 50 else 'does not support'} {direction} position"
    }


@mcp.tool()
def get_financial_statements(
    ticker: str,
    statement_types: list[Literal["income", "balance", "cash"]] = ["income"],
    frequency: Literal["quarterly", "annual"] = "quarterly",
    max_periods: int = 8
) -> dict[str, str]:
    """Get financial statements. Returns dict with statement type as key and CSV data as value."""
    ticker = validate_ticker(ticker)

    @api_retry
    def get_single_statement(stmt_type: str):
        t = yf.Ticker(ticker)
        if stmt_type == "income":
            return t.quarterly_income_stmt if frequency == "quarterly" else t.income_stmt
        elif stmt_type == "balance":
            return t.quarterly_balance_sheet if frequency == "quarterly" else t.balance_sheet
        else:  # cash
            return t.quarterly_cashflow if frequency == "quarterly" else t.cashflow

    # Fetch all requested statements in parallel
    with ThreadPoolExecutor() as executor:
        futures = {stmt_type: executor.submit(get_single_statement, stmt_type) for stmt_type in statement_types}

        results = {}
        for stmt_type, future in futures.items():
            df = safe_future_result(future, context=f"{stmt_type} statement for {ticker}")
            if df is None or df.empty:
                raise ValueError(f"No {stmt_type} statement data found for {ticker}")

            if len(df.columns) > max_periods:
                df = df.iloc[:, :max_periods]

            df_reset = df.reset_index()
            results[stmt_type] = to_clean_csv(df_reset)

    return results

@mcp.tool()
def get_institutional_holders(ticker: str, top_n: int = 20) -> dict[str, Any]:
    """Get major institutional and mutual fund holders."""
    ticker = validate_ticker(ticker)

    # Fetch both types in parallel
    with ThreadPoolExecutor() as executor:
        inst_future = executor.submit(yf_call, ticker, "get_institutional_holders")
        fund_future = executor.submit(yf_call, ticker, "get_mutualfund_holders")

        inst_holders = safe_future_result(inst_future, context=f"institutional holders for {ticker}")
        fund_holders = safe_future_result(fund_future, context=f"mutual fund holders for {ticker}")

    # Limit results
    inst_holders = inst_holders.head(top_n) if isinstance(inst_holders, pd.DataFrame) else None
    fund_holders = fund_holders.head(top_n) if isinstance(fund_holders, pd.DataFrame) else None

    if (inst_holders is None or inst_holders.empty) and (fund_holders is None or fund_holders.empty):
        raise ValueError(f"No institutional holder data found for {ticker}")

    result = {"ticker": ticker, "top_n": top_n}

    if inst_holders is not None and not inst_holders.empty:
        result["institutional_holders"] = to_clean_csv(inst_holders)

    if fund_holders is not None and not fund_holders.empty:
        result["mutual_fund_holders"] = to_clean_csv(fund_holders)

    return result

@mcp.tool()
def get_earnings_history(ticker: str, max_entries: int = 8) -> str:
    ticker = validate_ticker(ticker)

    earnings_history = yf_call(ticker, "get_earnings_history")
    if earnings_history is None or (isinstance(earnings_history, pd.DataFrame) and earnings_history.empty):
        raise ValueError(f"No earnings history data found for {ticker}")

    if isinstance(earnings_history, pd.DataFrame):
        earnings_history = earnings_history.head(max_entries)

    return to_clean_csv(earnings_history)

@mcp.tool()
def get_insider_trades(ticker: str, max_trades: int = 20) -> str:
    ticker = validate_ticker(ticker)

    trades = yf_call(ticker, "get_insider_transactions")
    if trades is None or (isinstance(trades, pd.DataFrame) and trades.empty):
        raise ValueError(f"No insider trading data found for {ticker}")

    if isinstance(trades, pd.DataFrame):
        trades = trades.head(max_trades)

    return to_clean_csv(trades)

@mcp.tool()
async def get_nasdaq_earnings_calendar(
    date: str | None = None,
    limit: int = 100
) -> str:
    """Get earnings calendar for a specific date using Nasdaq API.
    Date in YYYY-MM-DD format (defaults to today)
    Returns CSV with: Date, Symbol, Company Name, EPS, % Surprise, Market Cap, etc.
    Note: Single date only - call multiple times for date ranges.
    """
    # Constants
    NASDAQ_EARNINGS_URL = "https://api.nasdaq.com/api/calendar/earnings"
    NASDAQ_HEADERS = {
        **BROWSER_HEADERS,
        'Referer': 'https://www.nasdaq.com/'
    }

    # Set default date if not provided or validate provided date
    today = datetime.date.today()
    target_date = validate_date(date) if date else today

    date_str = target_date.strftime('%Y-%m-%d')
    url = f"{NASDAQ_EARNINGS_URL}?date={date_str}"

    try:
        logger.info(f"Fetching earnings for {date_str}")

        data = await fetch_json(url, NASDAQ_HEADERS)

        if 'data' in data and data['data']:
            earnings_data = data['data']

            if earnings_data.get('headers') and earnings_data.get('rows'):
                headers = earnings_data['headers']
                rows = earnings_data['rows']

                # Extract column names from headers dict
                if isinstance(headers, dict):
                    column_names = list(headers.values())
                    column_keys = list(headers.keys())
                else:
                    column_names = [h.get('label', h) if isinstance(h, dict) else str(h) for h in headers]
                    column_keys = column_names

                # Convert rows to DataFrame
                processed_rows = []
                for row in rows:
                    if isinstance(row, dict):
                        processed_row = [row.get(key, '') for key in column_keys]
                        processed_rows.append(processed_row)

                if processed_rows:
                    df = pd.DataFrame(processed_rows, columns=column_names)
                    # Add date column at the beginning
                    df.insert(0, 'Date', date_str)

                    # Apply limit
                    if len(df) > limit:
                        df = df.head(limit)

                    logger.info(f"Retrieved {len(df)} earnings entries for {date_str}")
                    return to_clean_csv(df)

        # No earnings data found
        return f"No earnings announcements found for {date_str}. This could be due to weekends, holidays, or no scheduled earnings on this date."

    except Exception as e:
        logger.error(f"Error fetching earnings for {date_str}: {e}")
        return f"Error retrieving earnings data for {date_str}: {str(e)}"


# ============================================================================
# Questrade Account Tools
# ============================================================================
# NOTE: fetch_intraday_15m and fetch_intraday_1h were removed as redundant.
# Use get_questrade_candles(symbol, interval, window=N) instead:
#   - For 15m bars: get_questrade_candles("AAPL", "FifteenMinutes", window=200)
#   - For 1h bars: get_questrade_candles("AAPL", "OneHour", window=200)

@mcp.tool()
def get_questrade_accounts() -> dict[str, Any]:
    """
    Get list of all Questrade accounts for the authenticated user.

    Returns account information including:
    - Account type (Margin, TFSA, RRSP, RESP, etc.)
    - Account number
    - Account status (Active, Suspended, etc.)
    - Primary account flag
    - Client account type (Individual, Joint, etc.)

    Returns:
        dict: Account information with structure:
            {
                'accounts': [
                    {
                        'type': 'Margin',
                        'number': '123456',
                        'status': 'Active',
                        'isPrimary': True,
                        'isBilling': True,
                        'clientAccountType': 'Individual'
                    },
                    ...
                ]
            }

    Raises:
        ValueError: If API call fails or authentication is invalid.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    try:
        client = get_questrade_client()
        accounts = client.get_accounts()

        logger.info(f"Retrieved {len(accounts.get('accounts', []))} Questrade accounts")
        return accounts

    except Exception as e:
        logger.error(f"Error in get_questrade_accounts: {e}")
        raise ValueError(f"Failed to retrieve Questrade accounts: {str(e)}")

@mcp.tool()
def get_questrade_positions(account_number: str) -> dict[str, Any]:
    """
    Get all positions (holdings/assets) for a specific Questrade account.

    Retrieves detailed information about all open positions including:
    - Symbol and symbol ID
    - Open quantity
    - Current market value and price
    - Average entry price
    - Profit/Loss (realized and unrealized)
    - Total cost basis

    Args:
        account_number: The Questrade account number (e.g., "26598145")

    Returns:
        dict: Position information with structure:
            {
                'positions': [
                    {
                        'symbol': 'AAPL',
                        'symbolId': 8049,
                        'openQuantity': 100,
                        'currentMarketValue': 15000.00,
                        'currentPrice': 150.00,
                        'averageEntryPrice': 140.00,
                        'closedPnl': 0.0,
                        'openPnl': 1000.00,
                        'totalCost': 14000.00,
                        'isRealTime': True,
                        'isUnderReorg': False
                    },
                    ...
                ]
            }

    Raises:
        ValueError: If account_number is invalid or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not account_number:
        raise ValueError("account_number parameter is required")

    try:
        client = get_questrade_client()
        positions = client.get_account_positions(account_number)

        position_count = len(positions.get('positions', []))
        logger.info(f"Retrieved {position_count} positions for account {account_number}")
        return positions

    except Exception as e:
        logger.error(f"Error in get_questrade_positions for account {account_number}: {e}")
        raise ValueError(f"Failed to retrieve positions for account {account_number}: {str(e)}")

@mcp.tool()
def get_questrade_balances(
    account_number: str,
    start_time: str | None = None
) -> dict[str, Any]:
    """
    Get cash balances and account equity for a specific Questrade account.

    Retrieves detailed balance information including:
    - Cash available per currency (CAD, USD, etc.)
    - Market value of holdings
    - Total equity
    - Buying power
    - Maintenance excess
    - Start-of-day balances (if available)

    Args:
        account_number: The Questrade account number (e.g., "26598145")
        start_time: Optional start time for historical balances (ISO format: "2024-01-01T00:00:00-05:00")

    Returns:
        dict: Balance information with structure:
            {
                'perCurrencyBalances': [
                    {
                        'currency': 'CAD',
                        'cash': 10000.00,
                        'marketValue': 50000.00,
                        'totalEquity': 60000.00,
                        'buyingPower': 120000.00,
                        'maintenanceExcess': 30000.00,
                        'isRealTime': True
                    },
                    ...
                ],
                'combinedBalances': [
                    {
                        'currency': 'CAD',
                        'cash': 10000.00,
                        'marketValue': 50000.00,
                        'totalEquity': 60000.00,
                        'buyingPower': 120000.00,
                        'maintenanceExcess': 30000.00,
                        'isRealTime': True
                    }
                ],
                'sodPerCurrencyBalances': [...],
                'sodCombinedBalances': [...]
            }

    Raises:
        ValueError: If account_number is invalid or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not account_number:
        raise ValueError("account_number parameter is required")

    try:
        client = get_questrade_client()
        balances = client.get_account_balances(account_number, start_time)

        logger.info(f"Retrieved balances for account {account_number}")
        return balances

    except Exception as e:
        logger.error(f"Error in get_questrade_balances for account {account_number}: {e}")
        raise ValueError(f"Failed to retrieve balances for account {account_number}: {str(e)}")

# NOTE: get_questrade_quote was removed as redundant.
# Use get_questrade_quotes(symbols=["AAPL"]) for single quotes.

@mcp.tool()
def get_questrade_quotes(symbols: list[str]) -> dict[str, Any]:
    """
    Get real-time Level 1 quotes for multiple symbols.

    Efficiently retrieves quotes for multiple symbols in a single API call.
    Falls back to Yahoo Finance if Questrade is unavailable.

    Args:
        symbols: List of symbols to get quotes for (e.g., ["AAPL", "TSLA", "NVDA"])

    Returns:
        dict: Quotes for all requested symbols

    Raises:
        ValueError: If symbols list is empty or both APIs fail.

    Note:
        Prefers Questrade for real-time data, falls back to Yahoo Finance.
    """
    if not symbols:
        raise ValueError("symbols list parameter is required")

    # Try Questrade first
    try:
        client = get_questrade_client()
        quotes = client.get_quotes(symbols)
        quotes['data_source'] = 'QUESTRADE'
        logger.info(f"Retrieved quotes for {len(symbols)} symbols from Questrade")
        return quotes

    except Exception as questrade_error:
        logger.warning(f"Questrade failed, falling back to Yahoo Finance: {questrade_error}")

        # Fallback to Yahoo Finance
        try:
            import yfinance as yf

            yf_quotes = []
            for symbol in symbols:
                ticker = yf.Ticker(symbol)
                info = ticker.info

                # Map Yahoo Finance fields to Questrade-like structure
                quote = {
                    'symbol': symbol,
                    'lastTradePrice': info.get('regularMarketPrice') or info.get('currentPrice'),
                    'bidPrice': info.get('bid'),
                    'askPrice': info.get('ask'),
                    'bidSize': info.get('bidSize'),
                    'askSize': info.get('askSize'),
                    'volume': info.get('regularMarketVolume') or info.get('volume'),
                    'openPrice': info.get('regularMarketOpen') or info.get('open'),
                    'highPrice': info.get('regularMarketDayHigh') or info.get('dayHigh'),
                    'lowPrice': info.get('regularMarketDayLow') or info.get('dayLow'),
                    'prevDayClosePrice': info.get('regularMarketPreviousClose') or info.get('previousClose'),
                    'VWAP': None,  # Not available in YF
                    'delay': 0,  # YF is delayed
                    'isHalted': False,
                }
                yf_quotes.append(quote)

            result = {
                'quotes': yf_quotes,
                'data_source': 'YAHOO_FINANCE',
                'note': 'Questrade unavailable, using Yahoo Finance (may be delayed 15-20 min)'
            }
            logger.info(f"Retrieved quotes for {len(symbols)} symbols from Yahoo Finance (fallback)")
            return result

        except Exception as yf_error:
            logger.error(f"Both Questrade and Yahoo Finance failed: {yf_error}")
            raise ValueError(f"Failed to retrieve quotes from both sources. Questrade: {questrade_error}, Yahoo Finance: {yf_error}")

@mcp.tool()
def get_questrade_candles(
    symbol: str,
    interval: str,
    start_time: str | None = None,
    end_time: str | None = None,
    window: int | None = None
) -> dict[str, Any]:
    """
    Get historical OHLCV candle data for a symbol.

    Perfect for charting and technical analysis.
    Falls back to Yahoo Finance if Questrade is unavailable.

    Args:
        symbol: The symbol to get candles for (e.g., "AAPL")
        interval: Candle interval - one of:
            OneMinute, TwoMinutes, ThreeMinutes, FourMinutes, FiveMinutes,
            TenMinutes, FifteenMinutes, TwentyMinutes, HalfHour, OneHour,
            TwoHours, FourHours, OneDay, OneWeek, OneMonth, OneYear
        start_time: Start time in ISO format (e.g., "2024-01-01T00:00:00-05:00").
            Optional if window is provided.
        end_time: End time in ISO format (e.g., "2024-12-31T23:59:59-05:00").
            Optional if window is provided.
        window: Number of bars to fetch (e.g., 200). When provided, auto-calculates
            start_time and end_time based on the interval. This is a convenience
            alternative to specifying explicit timestamps.

    Returns:
        dict: Candle data with Open, High, Low, Close, Volume

    Raises:
        ValueError: If parameters are invalid or both APIs fail.

    Note:
        Prefers Questrade for real-time data, falls back to Yahoo Finance.

    Examples:
        # Using explicit timestamps:
        get_questrade_candles("AAPL", "OneDay", "2024-01-01T00:00:00-05:00", "2024-12-31T23:59:59-05:00")

        # Using window (convenience mode - fetches last N bars):
        get_questrade_candles("AAPL", "FifteenMinutes", window=200)
        get_questrade_candles("AAPL", "OneHour", window=200)
    """
    from datetime import datetime, timedelta
    import pytz

    if not symbol or not interval:
        raise ValueError("symbol and interval are required")

    # Calculate time range from window if provided
    if window is not None:
        et = pytz.timezone("America/New_York")
        end_dt = datetime.now(et)

        # Map interval to minutes for time calculation
        interval_minutes = {
            "OneMinute": 1,
            "TwoMinutes": 2,
            "ThreeMinutes": 3,
            "FourMinutes": 4,
            "FiveMinutes": 5,
            "TenMinutes": 10,
            "FifteenMinutes": 15,
            "TwentyMinutes": 20,
            "HalfHour": 30,
            "OneHour": 60,
            "TwoHours": 120,
            "FourHours": 240,
            "OneDay": 1440,
            "OneWeek": 10080,
            "OneMonth": 43200,
            "OneYear": 525600,
        }
        minutes = interval_minutes.get(interval, 60)
        # Add buffer multiplier (3x) to account for market hours only
        start_dt = end_dt - timedelta(minutes=minutes * window * 3)

        start_time = start_dt.isoformat()
        end_time = end_dt.isoformat()

    elif start_time is None or end_time is None:
        raise ValueError("Either provide window OR both start_time and end_time")

    # Try Questrade first
    try:
        client = get_questrade_client()
        candles = client.get_candles(symbol, interval, start_time, end_time)
        candles['data_source'] = 'QUESTRADE'
        logger.info(f"Retrieved candles for {symbol} from Questrade")
        return candles

    except Exception as questrade_error:
        logger.warning(f"Questrade failed, falling back to Yahoo Finance: {questrade_error}")

        # Fallback to Yahoo Finance
        try:
            import yfinance as yf

            # Map Questrade intervals to Yahoo Finance intervals
            interval_map = {
                "OneMinute": "1m",
                "TwoMinutes": "2m",
                "FiveMinutes": "5m",
                "FifteenMinutes": "15m",
                "HalfHour": "30m",
                "OneHour": "1h",
                "OneDay": "1d",
                "OneWeek": "1wk",
                "OneMonth": "1mo",
            }
            yf_interval = interval_map.get(interval, "1d")

            # Calculate period for yfinance based on window or dates
            if window is not None:
                # Map window to period string
                if yf_interval in ["1m", "2m", "5m", "15m", "30m"]:
                    period = "7d"  # YF intraday limit
                elif yf_interval == "1h":
                    period = "1mo"
                elif yf_interval == "1d":
                    period = f"{min(window, 365)}d"
                elif yf_interval == "1wk":
                    period = f"{min(window * 7, 730)}d"
                else:
                    period = "max"

                df = yf.download(symbol, period=period, interval=yf_interval, progress=False)
            else:
                # Use explicit dates
                start_date = start_time[:10] if start_time else None
                end_date = end_time[:10] if end_time else None
                df = yf.download(symbol, start=start_date, end=end_date, interval=yf_interval, progress=False)

            if df.empty:
                raise ValueError(f"No data returned from Yahoo Finance for {symbol}")

            # Flatten MultiIndex columns if present (yfinance returns ('Open', 'AAPL'))
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Convert to Questrade-like format
            candles_list = []
            for idx, row in df.iterrows():
                try:
                    open_val = float(row['Open']) if pd.notna(row['Open']) else None
                    high_val = float(row['High']) if pd.notna(row['High']) else None
                    low_val = float(row['Low']) if pd.notna(row['Low']) else None
                    close_val = float(row['Close']) if pd.notna(row['Close']) else None
                    volume_val = int(row['Volume']) if pd.notna(row['Volume']) else 0
                except (TypeError, ValueError):
                    continue

                candle = {
                    'start': idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                    'open': open_val,
                    'high': high_val,
                    'low': low_val,
                    'close': close_val,
                    'volume': volume_val,
                }
                candles_list.append(candle)

            # Limit to requested window if specified
            if window is not None and len(candles_list) > window:
                candles_list = candles_list[-window:]

            result = {
                'candles': candles_list,
                'data_source': 'YAHOO_FINANCE',
                'note': f'Questrade unavailable, using Yahoo Finance. Interval mapped: {interval} -> {yf_interval}'
            }
            logger.info(f"Retrieved {len(candles_list)} candles for {symbol} from Yahoo Finance (fallback)")
            return result

        except Exception as yf_error:
            logger.error(f"Both Questrade and Yahoo Finance failed: {yf_error}")
            raise ValueError(f"Failed to retrieve candles from both sources. Questrade: {questrade_error}, Yahoo Finance: {yf_error}")

@mcp.tool()
def search_questrade_symbols(query: str, offset: int = 0) -> dict[str, Any]:
    """
    Search for symbols by name or description.

    Useful for discovering symbols before trading or analyzing.

    Args:
        query: Search query string (e.g., "Apple", "tech", "bank")
        offset: Pagination offset (default: 0)

    Returns:
        dict: Search results with matching symbols

    Raises:
        ValueError: If query is empty or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not query:
        raise ValueError("query parameter is required")

    try:
        client = get_questrade_client()
        results = client.search_symbols(query, offset)
        logger.info(f"Searched symbols for: {query}")
        return results

    except Exception as e:
        logger.error(f"Error in search_questrade_symbols for '{query}': {e}")
        raise ValueError(f"Failed to search symbols: {str(e)}")

@mcp.tool()
def get_questrade_symbol_info(symbols: str) -> dict[str, Any]:
    """
    Get detailed information for one or more symbols.

    Retrieves comprehensive symbol data including exchange, currency,
    trading status, and more.

    Args:
        symbols: Single symbol or comma-separated list (e.g., "AAPL" or "AAPL,TSLA,NVDA")

    Returns:
        dict: Detailed symbol information

    Raises:
        ValueError: If symbols parameter is empty or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not symbols:
        raise ValueError("symbols parameter is required")

    try:
        client = get_questrade_client()
        info = client.get_symbol_info(symbols)
        logger.info(f"Retrieved symbol info for: {symbols}")
        return info

    except Exception as e:
        logger.error(f"Error in get_questrade_symbol_info for {symbols}: {e}")
        raise ValueError(f"Failed to retrieve symbol info: {str(e)}")

@mcp.tool()
def get_questrade_markets() -> dict[str, Any]:
    """
    Get information about available markets.

    Returns details about all markets available through Questrade.

    Returns:
        dict: List of available markets and their details

    Raises:
        ValueError: If API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    try:
        client = get_questrade_client()
        markets = client.get_markets()
        logger.info("Retrieved markets information")
        return markets

    except Exception as e:
        logger.error(f"Error in get_questrade_markets: {e}")
        raise ValueError(f"Failed to retrieve markets: {str(e)}")

@mcp.tool()
def get_questrade_orders(
    account_number: str,
    start_time: str | None = None,
    end_time: str | None = None,
    state_filter: str | None = None
) -> dict[str, Any]:
    """
    Get orders for a specific account.

    Lists all orders (open, filled, cancelled) for monitoring trading activity.

    Args:
        account_number: The account number
        start_time: Optional start time filter (ISO format: "2024-01-01T00:00:00-05:00")
        end_time: Optional end time filter (ISO format)
        state_filter: Optional state filter ("All", "Open", "Closed")

    Returns:
        dict: List of orders with details

    Raises:
        ValueError: If account_number is invalid or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not account_number:
        raise ValueError("account_number parameter is required")

    try:
        client = get_questrade_client()
        orders = client.get_account_orders(account_number, start_time, end_time, state_filter)
        order_count = len(orders.get('orders', []))
        logger.info(f"Retrieved {order_count} orders for account {account_number}")
        return orders

    except Exception as e:
        logger.error(f"Error in get_questrade_orders for account {account_number}: {e}")
        raise ValueError(f"Failed to retrieve orders: {str(e)}")

@mcp.tool()
def get_questrade_order(account_number: str, order_id: str) -> dict[str, Any]:
    """
    Get details for a specific order.

    Retrieves complete information about a single order including status,
    fill details, and timestamps.

    Args:
        account_number: The account number
        order_id: The order ID

    Returns:
        dict: Complete order details

    Raises:
        ValueError: If parameters are invalid or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not account_number or not order_id:
        raise ValueError("account_number and order_id parameters are required")

    try:
        client = get_questrade_client()
        order = client.get_account_order(account_number, order_id)
        logger.info(f"Retrieved order {order_id} for account {account_number}")
        return order

    except Exception as e:
        logger.error(f"Error in get_questrade_order for order {order_id}: {e}")
        raise ValueError(f"Failed to retrieve order details: {str(e)}")

@mcp.tool()
def get_questrade_executions(
    account_number: str,
    start_time: str | None = None,
    end_time: str | None = None
) -> dict[str, Any]:
    """
    Get trade executions (trade history) for a specific account.

    Essential for analyzing trading performance and tracking executed trades.

    Args:
        account_number: The account number
        start_time: Optional start time filter (ISO format: "2024-01-01T00:00:00-05:00")
        end_time: Optional end time filter (ISO format)

    Returns:
        dict: List of trade executions with prices, quantities, and timestamps

    Raises:
        ValueError: If account_number is invalid or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not account_number:
        raise ValueError("account_number parameter is required")

    try:
        client = get_questrade_client()
        executions = client.get_account_executions(account_number, start_time, end_time)
        execution_count = len(executions.get('executions', []))
        logger.info(f"Retrieved {execution_count} executions for account {account_number}")
        return executions

    except Exception as e:
        logger.error(f"Error in get_questrade_executions for account {account_number}: {e}")
        raise ValueError(f"Failed to retrieve executions: {str(e)}")

@mcp.tool()
def get_questrade_activities(
    account_number: str,
    start_time: str | None = None,
    end_time: str | None = None
) -> dict[str, Any]:
    """
    Get account activities (deposits, withdrawals, fees, dividends, etc.).

    Track all account activity beyond just trades.

    Args:
        account_number: The account number
        start_time: Optional start time filter (ISO format: "2024-01-01T00:00:00-05:00")
        end_time: Optional end time filter (ISO format)

    Returns:
        dict: List of account activities

    Raises:
        ValueError: If account_number is invalid or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not account_number:
        raise ValueError("account_number parameter is required")

    try:
        client = get_questrade_client()
        activities = client.get_account_activities(account_number, start_time, end_time)
        activity_count = len(activities.get('activities', []))
        logger.info(f"Retrieved {activity_count} activities for account {account_number}")
        return activities

    except Exception as e:
        logger.error(f"Error in get_questrade_activities for account {account_number}: {e}")
        raise ValueError(f"Failed to retrieve activities: {str(e)}")

@mcp.tool()
def get_questrade_options_chain(symbol: str) -> dict[str, Any]:
    """
    Get options chain for a symbol.

    Retrieves all available option contracts for an underlying symbol.
    Falls back to Yahoo Finance if Questrade is unavailable.

    Args:
        symbol: The underlying symbol (e.g., "AAPL")

    Returns:
        dict: Options chain data with available strikes and expirations

    Raises:
        ValueError: If symbol is invalid or both APIs fail.

    Note:
        Prefers Questrade for options data, falls back to Yahoo Finance.
    """
    if not symbol:
        raise ValueError("symbol parameter is required")

    # Try Questrade first
    try:
        client = get_questrade_client()
        options = client.get_options_chain(symbol)
        options['data_source'] = 'QUESTRADE'
        logger.info(f"Retrieved options chain for {symbol} from Questrade")
        return options

    except Exception as questrade_error:
        logger.warning(f"Questrade failed, falling back to Yahoo Finance: {questrade_error}")

        # Fallback to Yahoo Finance
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            expiry_dates = ticker.options  # List of expiry dates

            if not expiry_dates:
                raise ValueError(f"No options available for {symbol}")

            # Build options chain in Questrade-like format
            option_chain = []
            for expiry in expiry_dates[:5]:  # Limit to first 5 expiries for performance
                try:
                    chain = ticker.option_chain(expiry)
                    calls = chain.calls
                    puts = chain.puts

                    chain_per_strike = []
                    # Get unique strikes from both calls and puts
                    all_strikes = sorted(set(calls['strike'].tolist() + puts['strike'].tolist()))

                    for strike in all_strikes:
                        call_row = calls[calls['strike'] == strike]
                        put_row = puts[puts['strike'] == strike]

                        strike_data = {
                            'strikePrice': strike,
                            'callSymbolId': call_row['contractSymbol'].iloc[0] if not call_row.empty else None,
                            'putSymbolId': put_row['contractSymbol'].iloc[0] if not put_row.empty else None,
                        }
                        chain_per_strike.append(strike_data)

                    option_chain.append({
                        'expiryDate': expiry,
                        'description': symbol,
                        'listingExchange': 'OPRA',
                        'optionExerciseType': 'American',
                        'chainPerRoot': [{
                            'optionRoot': symbol,
                            'chainPerStrikePrice': chain_per_strike,
                            'multiplier': 100
                        }]
                    })
                except Exception as chain_error:
                    logger.warning(f"Failed to get chain for {symbol} {expiry}: {chain_error}")
                    continue

            if not option_chain:
                raise ValueError(f"Failed to build options chain for {symbol}")

            result = {
                'optionChain': option_chain,
                'data_source': 'YAHOO_FINANCE',
                'note': f'Questrade unavailable, using Yahoo Finance. Limited to {len(option_chain)} expiries.'
            }
            logger.info(f"Retrieved options chain for {symbol} from Yahoo Finance (fallback)")
            return result

        except Exception as yf_error:
            logger.error(f"Both Questrade and Yahoo Finance failed: {yf_error}")
            raise ValueError(f"Failed to retrieve options chain from both sources. Questrade: {questrade_error}, Yahoo Finance: {yf_error}")

@mcp.tool()
def get_questrade_option_quotes(option_ids: list[int]) -> dict[str, Any]:
    """
    Get quotes with Greeks for option symbols.

    Retrieves real-time option quotes including Greeks (Delta, Gamma, Theta, Vega).

    Args:
        option_ids: List of option IDs (obtained from options chain)

    Returns:
        dict: Option quotes with Greeks data

    Raises:
        ValueError: If option_ids list is empty or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not option_ids:
        raise ValueError("option_ids list parameter is required")

    try:
        client = get_questrade_client()
        quotes = client.get_option_quotes(option_ids)
        logger.info(f"Retrieved option quotes for {len(option_ids)} options")
        return quotes

    except Exception as e:
        logger.error(f"Error in get_questrade_option_quotes: {e}")
        raise ValueError(f"Failed to retrieve option quotes: {str(e)}")


# ============================================================================
# Real-Time Order Flow Tools
# ============================================================================

@mcp.tool()
def analyze_realtime_trade_flow(
    ticker: str,
    duration_minutes: int = 30
) -> dict[str, Any]:
    """
    Analyze real-time trade flow using Questrade Level 1 data.

    Uses lastTradeTick to classify trades as buyer or seller initiated.
    This is TRUE order flow classification, not OHLCV approximation.

    Tick meanings:
    - "Up" = Trade at higher price = Buyer hitting ask (BULLISH)
    - "Down" = Trade at lower price = Seller hitting bid (BEARISH)
    - "Equal" = Trade at same price = Neutral

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        duration_minutes: How many minutes of data to analyze (default 30)

    Returns:
        Trade flow analysis with:
        - buy_volume / sell_volume / neutral_volume
        - tick_ratio: buy_vol / (buy_vol + sell_vol)
        - aggression_bias: BULLISH (>55%), BEARISH (<45%), NEUTRAL
        - large_trade_details: Trades > 2x average size
    """
    from .realtime_order_flow import analyze_trade_flow_snapshot

    try:
        # For single call, use snapshot function
        result = analyze_trade_flow_snapshot(ticker)
        logger.info(f"Retrieved trade flow snapshot for {ticker}")
        return result

    except Exception as e:
        logger.error(f"Error in analyze_realtime_trade_flow for {ticker}: {e}")
        raise ValueError(f"Failed to analyze trade flow for {ticker}: {str(e)}")


@mcp.tool()
def get_bid_ask_imbalance(ticker: str) -> dict[str, Any]:
    """
    Get current bid/ask size imbalance for a ticker.

    Monitors passive order flow to detect institutional positioning.

    Interpretation:
    - High bid/ask ratio (>2.0) = STRONG_BID = Buyers have size advantage
    - Low bid/ask ratio (<0.5) = STRONG_ASK = Sellers have size advantage
    - Ratio 0.8-1.2 = BALANCED

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Bid/ask imbalance analysis with:
        - imbalance_ratio: bidSize / askSize
        - imbalance_pct: (bid - ask) / total * 100
        - signal: STRONG_BID / WEAK_BID / BALANCED / WEAK_ASK / STRONG_ASK
        - spread_bps: Spread in basis points
        - liquidity_wall: Side with larger size
    """
    try:
        client = get_questrade_client()
        quotes = client.get_quote(ticker)

        if not quotes.get('quotes'):
            return {"error": f"No quote data for {ticker}"}

        q = quotes['quotes'][0]

        bid_size = q.get('bidSize', 0)
        ask_size = q.get('askSize', 0)
        bid_price = q.get('bidPrice', 0)
        ask_price = q.get('askPrice', 0)

        # Calculate imbalance
        if ask_size > 0:
            imbalance = bid_size / ask_size
        else:
            imbalance = 1.0

        total = bid_size + ask_size
        if total > 0:
            imbalance_pct = (bid_size - ask_size) / total * 100
        else:
            imbalance_pct = 0

        # Determine signal
        if imbalance > 2.0:
            signal = "STRONG_BID"
        elif imbalance > 1.2:
            signal = "WEAK_BID"
        elif imbalance < 0.5:
            signal = "STRONG_ASK"
        elif imbalance < 0.8:
            signal = "WEAK_ASK"
        else:
            signal = "BALANCED"

        # Calculate spread in basis points
        mid_price = (bid_price + ask_price) / 2 if (bid_price + ask_price) > 0 else 1
        spread = ask_price - bid_price
        spread_bps = (spread / mid_price) * 10000 if mid_price > 0 else 0

        result = {
            "ticker": ticker.upper(),
            "bid_size": bid_size,
            "ask_size": ask_size,
            "bid_price": bid_price,
            "ask_price": ask_price,
            "imbalance_ratio": round(imbalance, 2),
            "imbalance_pct": round(imbalance_pct, 1),
            "signal": signal,
            "spread": round(spread, 4),
            "spread_bps": round(spread_bps, 1),
            "liquidity_wall": {
                "side": "BID" if bid_size > ask_size else "ASK",
                "size": max(bid_size, ask_size),
                "price": bid_price if bid_size > ask_size else ask_price
            },
            "interpretation": f"{'Buyers' if imbalance > 1 else 'Sellers'} have size advantage ({signal})"
        }

        logger.info(f"Retrieved bid-ask imbalance for {ticker}: {signal}")
        return result

    except Exception as e:
        logger.error(f"Error in get_bid_ask_imbalance for {ticker}: {e}")
        raise ValueError(f"Failed to retrieve bid-ask imbalance for {ticker}: {str(e)}")


@mcp.tool()
def analyze_spread_dynamics(ticker: str) -> dict[str, Any]:
    """
    Analyze spread dynamics for liquidity assessment.

    Spread is a key indicator of market liquidity and potential volatility:
    - Tight spread = High liquidity, lower transaction costs
    - Wide spread = Lower liquidity, higher volatility expected

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Spread analysis with:
        - current_spread: Ask - Bid in dollars
        - spread_bps: Spread in basis points
        - liquidity_grade: A (excellent) to F (very poor)
        - total_depth: Combined bid + ask size
    """
    try:
        client = get_questrade_client()
        quotes = client.get_quote(ticker)

        if not quotes.get('quotes'):
            return {"error": f"No quote data for {ticker}"}

        q = quotes['quotes'][0]

        bid_price = q.get('bidPrice', 0)
        ask_price = q.get('askPrice', 0)
        bid_size = q.get('bidSize', 0)
        ask_size = q.get('askSize', 0)

        # Current spread
        spread = ask_price - bid_price
        mid_price = (bid_price + ask_price) / 2 if (bid_price + ask_price) > 0 else 1
        spread_bps = (spread / mid_price) * 10000 if mid_price > 0 else 0

        # Liquidity grade based on spread and size
        total_size = bid_size + ask_size
        if spread_bps < 5 and total_size > 1000:
            grade = "A"  # Excellent
        elif spread_bps < 10 and total_size > 500:
            grade = "B"  # Good
        elif spread_bps < 20 and total_size > 100:
            grade = "C"  # Average
        elif spread_bps < 50:
            grade = "D"  # Poor
        else:
            grade = "F"  # Very poor

        result = {
            "ticker": ticker.upper(),
            "bid_price": bid_price,
            "ask_price": ask_price,
            "current_spread": round(spread, 4),
            "spread_bps": round(spread_bps, 1),
            "bid_size": bid_size,
            "ask_size": ask_size,
            "total_depth": total_size,
            "liquidity_grade": grade,
            "interpretation": f"Liquidity Grade {grade} - Spread {round(spread_bps, 1)} bps"
        }

        logger.info(f"Analyzed spread dynamics for {ticker}: Grade {grade}")
        return result

    except Exception as e:
        logger.error(f"Error in analyze_spread_dynamics for {ticker}: {e}")
        raise ValueError(f"Failed to analyze spread dynamics for {ticker}: {str(e)}")


# NOTE: calculate_true_cvd was removed as redundant.
# CVD analysis (trend, divergence, delta bars) is already included in
# analyze_volume_tool() with comprehensive OHLCV-based calculation.
# The Questrade lastTradeTick enhancement added minimal value.


# Only register the technical indicator tool if TA-Lib is available
if _ta_available:
    @mcp.tool()
    def calculate_technical_indicator(
        ticker: str,
        indicator: Literal["SMA", "EMA", "RSI", "MACD", "BBANDS"],
        period: Literal["1mo", "3mo", "6mo", "1y", "2y", "5y"] = "1y",
        timeperiod: int = 14,  # Default timeperiod for SMA, EMA, RSI
        fastperiod: int = 12,  # Default for MACD fast EMA
        slowperiod: int = 26,  # Default for MACD slow EMA
        signalperiod: int = 9,   # Default for MACD signal line
        nbdev: int = 2,        # Default standard deviation for BBANDS
        matype: int = 0,       # MA type: 0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA, 5=TRIMA, 6=KAMA, 7=MAMA, 8=T3
        num_results: int = 100  # Number of recent results to return
    ) -> dict[str, Any]:
        """Calculate technical indicators for stock analysis.

        matype values: 0=SMA, 1=EMA, 2=WMA, 3=DEMA, 4=TEMA, 5=TRIMA, 6=KAMA, 7=MAMA, 8=T3

        Returns dictionary with indicator-specific keys:
        - SMA/EMA: {"sma"/"ema": Series}
        - RSI: {"rsi": Series}
        - MACD: {"macd": Series, "signal": Series, "histogram": Series}
        - BBANDS: {"upper_band": Series, "middle_band": Series, "lower_band": Series}
        """
        import numpy as np
        from talib import MA_Type  # type: ignore

        ticker = validate_ticker(ticker)

        history = yf_call(ticker, "history", period=period, interval="1d")
        if history is None or history.empty or 'Close' not in history.columns:
            raise ValueError(f"No valid historical data found for {ticker}")

        close_prices = history['Close'].values
        min_required = {
            "SMA": timeperiod, "EMA": timeperiod * 2, "RSI": timeperiod + 1,
            "MACD": slowperiod + signalperiod, "BBANDS": timeperiod
        }.get(indicator, timeperiod)

        if len(close_prices) < min_required:
            raise ValueError(f"Insufficient data for {indicator} ({len(close_prices)} points, need {min_required})")

        # Calculate indicators using mapping
        indicator_funcs = {
            "SMA": lambda: {"sma": talib.SMA(close_prices, timeperiod=timeperiod)},
            "EMA": lambda: {"ema": talib.EMA(close_prices, timeperiod=timeperiod)},
            "RSI": lambda: {"rsi": talib.RSI(close_prices, timeperiod=timeperiod)},
            "MACD": lambda: dict(zip(["macd", "signal", "histogram"],
                talib.MACD(close_prices, fastperiod=fastperiod,
                          slowperiod=slowperiod, signalperiod=signalperiod))),
            "BBANDS": lambda: dict(zip(["upper_band", "middle_band", "lower_band"],
                talib.BBANDS(close_prices, timeperiod=timeperiod,
                           nbdevup=nbdev, nbdevdn=nbdev, matype=MA_Type(matype))))
        }
        indicator_values = indicator_funcs[indicator]()

        # Limit results to num_results
        if num_results > 0:
            history = history.tail(num_results)

        # Reset index to show dates as a column
        price_df = history.reset_index()
        price_df['Date'] = pd.to_datetime(price_df['Date']).dt.strftime('%Y-%m-%d')

        # Create indicator DataFrame with same date range
        indicator_rows = []
        for i, date in enumerate(price_df['Date']):
            row = {'Date': date}
            for name, values in indicator_values.items():
                # Get the corresponding value for this date
                slice_values = values[-num_results:] if num_results > 0 else values

                if i < len(slice_values):
                    val = slice_values[i]
                    row[name] = f"{val:.4f}" if not np.isnan(val) else "N/A"
                else:
                    row[name] = "N/A"
            indicator_rows.append(row)

        indicator_df = pd.DataFrame(indicator_rows)

        return {
            "price_data": to_clean_csv(price_df),
            "indicator_data": to_clean_csv(indicator_df)
        }

# Import advanced technical analysis module
try:
    from .technical_analysis import TechnicalAnalysis
    _advanced_ta_available = True
except ImportError:
    _advanced_ta_available = False
    logger.warning("Advanced technical analysis module not available")


# Advanced Technical Analysis Tools
if _advanced_ta_available:
    @mcp.tool()
    def analyze_technical(
        ticker: str,
        period: Literal["3mo", "6mo", "1y", "2y"] = "6mo",
        include_ml_analysis: bool = True,
        include_trend_score: bool = True
    ) -> dict[str, Any]:
        """Perform comprehensive technical analysis with RSI, MACD, Bollinger Bands, Moving Averages, and Stochastic indicators.

        Returns detailed technical indicators including:
        - RSI (Relative Strength Index) with overbought/oversold signals
        - MACD (Moving Average Convergence Divergence) with trend analysis
        - Bollinger Bands with price position
        - Multiple Moving Averages (SMA 20/50/200, EMA 20)
        - Stochastic Oscillator
        - ML Probability Analysis (if include_ml_analysis=True)
        - Al Brooks Price Action Analysis (pattern, probability, bar reading, trap risk)
        - Trend Strength Score 0-100 with statistical validation (if include_trend_score=True)

        Note: Trend strength scoring with statistical validation (t-statistic, p-value,
        confidence levels) is now included here. This replaces the standalone
        analyze_trend_strength tool. Output appears in result['trend_strength'].
        """
        ticker = validate_ticker(ticker)

        # Use Questrade-first approach with caching
        history = _get_ohlcv_cached(ticker, period=period)
        if history is None or history.empty:
            raise ValueError(f"No historical data found for {ticker}")

        indicators = TechnicalAnalysis.calculate_comprehensive_indicators(history)

        result = {
            "symbol": ticker,
            "period": period,
            "data_points": len(history),
            "analysis": indicators
        }

        # Add ML probability layer if requested
        if include_ml_analysis:
            try:
                # Calculate current conditions from indicators
                current_conditions = {
                    'rsi': indicators['rsi']['value'],
                    'price_level': indicators['current_price'],
                    'trend': 'UPTREND' if indicators['moving_averages']['trend'] == 'bullish' else 'DOWNTREND',
                    'macd_trend': indicators['macd']['trend']
                }

                # Find similar historical setups (lowered from 20 to 10 for better results)
                engine = SimilarityEngine(similarity_threshold=0.75, min_similar_setups=10)
                similar_setups = engine.find_similar_setups(
                    ticker=ticker,
                    current_conditions=current_conditions,
                    historical_data=history,
                    lookback_periods=min(200, len(history) - 20)
                )

                if len(similar_setups) >= 1:  # Calculate with any available data
                    # Analyze similar setups
                    analysis_result = engine.analyze_similar_setups(
                        ticker=ticker,
                        current_conditions=current_conditions,
                        similar_setups=similar_setups
                    )

                    # Add ML layer to result
                    result['ml_probability_layer'] = {
                        'similar_setups_found': len(similar_setups),
                        'historical_success_rate_10d': analysis_result.aggregate_statistics.get('success_rate_10d', 0.0),
                        'avg_return_10d': analysis_result.aggregate_statistics.get('avg_return_10d', 0.0),
                        'confidence': analysis_result.recommendation.get('confidence', 0.0),
                        'recommendation': analysis_result.recommendation.get('take_trade', False),
                        'expected_return': analysis_result.recommendation.get('expected_return', 0.0),
                        'risk_reward_ratio': analysis_result.aggregate_statistics.get('risk_reward_ratio', 0.0),
                        'confidence_interval_95': analysis_result.aggregate_statistics.get('confidence_interval_95', [0.0, 0.0]),
                        'interpretation': (
                            f"Based on {len(similar_setups)} similar historical setups, "
                            f"{analysis_result.aggregate_statistics.get('success_rate_10d', 0.0):.1%} success rate. "
                            f"{'HIGH PROBABILITY' if analysis_result.recommendation.get('confidence', 0) > 0.7 else 'MODERATE' if analysis_result.recommendation.get('confidence', 0) > 0.5 else 'LOW'} setup."
                        )
                    }
                else:
                    # Check data availability
                    data_days = len(history) if history is not None and not history.empty else 0
                    if data_days < 60:
                        reason = f'Insufficient historical data ({data_days} days). New stock or limited trading history.'
                    else:
                        reason = 'No similar historical setups found matching current conditions (very unique setup).'

                    result['ml_probability_layer'] = {
                        'similar_setups_found': 0,
                        'data_availability': f'{data_days} days',
                        'note': reason,
                        'interpretation': 'ML probability analysis unavailable. Rely on technical indicators and price action instead.',
                        'recommendation': 'Use Al Brooks price action analysis and traditional technical indicators for this setup.'
                    }

            except Exception as e:
                result['ml_probability_layer'] = {
                    'error': f'ML analysis failed: {str(e)}',
                    'interpretation': 'ML analysis unavailable'
                }

        # Add Al Brooks Price Action Analysis
        try:
            if ANALYZER_AVAILABLE:
                brooks = AlBrooksAnalyzer()
                # Determine direction from technical indicators
                ma_trend = indicators.get('moving_averages', {}).get('trend', 'neutral')
                macd_trend = indicators.get('macd', {}).get('trend', 'neutral')
                direction = 'long' if ma_trend == 'bullish' or macd_trend == 'bullish' else 'short'

                brooks_result = brooks.analyze(
                    ticker=ticker,
                    direction=direction,
                    ohlcv_data=history,
                    technical_data=result
                )

                result['al_brooks'] = {
                    'always_in_direction': brooks_result.get('always_in', 'UNKNOWN'),
                    'pattern': brooks_result.get('pattern', 'none'),
                    'pattern_description': brooks_result.get('pattern_description', ''),
                    'base_probability': brooks_result.get('base_probability', 50),
                    'adjusted_probability': brooks_result.get('adjusted_probability', 50),
                    'probability_adjustments': brooks_result.get('probability_adjustments', []),
                    'bar_reading': brooks_result.get('bar_reading', []),
                    'trap_risk': brooks_result.get('trap_risk', 'UNKNOWN'),
                    'trap_explanation': brooks_result.get('trap_explanation', ''),
                    'entry': brooks_result.get('entry'),
                    'stop': brooks_result.get('stop'),
                    'target': brooks_result.get('target'),
                    'risk_reward_ratio': brooks_result.get('risk_reward_ratio'),
                    'commentary': brooks_result.get('commentary', '')
                }
            else:
                result['al_brooks'] = {
                    'error': 'AlBrooksAnalyzer not available',
                    'note': 'Scanner analyzer module not loaded'
                }
        except Exception as e:
            result['al_brooks'] = {
                'error': f'Al Brooks analysis failed: {str(e)}',
                'interpretation': 'Al Brooks analysis unavailable'
            }

        # Add Trend Strength Score (0-100) with statistical validation
        if include_trend_score:
            try:
                trend_analysis = TechnicalAnalysis.calculate_trend_strength(history)
                result['trend_strength'] = trend_analysis

                # Add statistical confidence layer
                try:
                    # Ensure prices have DatetimeIndex (required by get_trend_scanning_labels)
                    prices = history['Close']
                    if not isinstance(prices.index, pd.DatetimeIndex):
                        prices = prices.copy()
                        prices.index = pd.to_datetime(prices.index)

                    # Use trend-scanning labels to get statistical significance
                    trend_result = get_trend_scanning_labels(
                        prices=prices,
                        lookforward_window=20,
                        t_stat_threshold=1.96  # 95% confidence
                    )

                    # TrendScanningResult is a dataclass, check if its labels Series has data
                    if trend_result is not None and len(trend_result.labels) > 0:
                        # Get the latest values from each Series attribute
                        t_stat = float(trend_result.t_statistics.iloc[-1])
                        p_value = float(trend_result.p_values.iloc[-1])
                        trend_label = int(trend_result.labels.iloc[-1])
                        confidence = 1 - p_value

                        # Determine significance
                        if abs(t_stat) > 2.58:
                            significance = "HIGHLY SIGNIFICANT (99%)"
                        elif abs(t_stat) > 1.96:
                            significance = "STATISTICALLY SIGNIFICANT (95%)"
                        elif abs(t_stat) > 1.645:
                            significance = "MODERATELY SIGNIFICANT (90%)"
                        else:
                            significance = "NOT SIGNIFICANT"

                        # Trend direction
                        if trend_label == 1:
                            trend_direction = "UPTREND"
                        elif trend_label == -1:
                            trend_direction = "DOWNTREND"
                        else:
                            trend_direction = "NEUTRAL"

                        result['trend_strength']['statistical_validation'] = {
                            't_statistic': float(t_stat),
                            'p_value': float(p_value),
                            'confidence': float(confidence),
                            'significance': significance,
                            'trend_direction': trend_direction,
                            'interpretation': (
                                f"{trend_direction} with {confidence:.1%} confidence. "
                                f"{'Trend is statistically robust' if abs(t_stat) > 1.96 else 'Trend may be noise - use caution'}."
                            )
                        }
                    else:
                        result['trend_strength']['statistical_validation'] = {
                            'note': 'Insufficient data for statistical validation'
                        }
                except Exception as stat_e:
                    result['trend_strength']['statistical_validation'] = {
                        'error': f'Statistical validation failed: {str(stat_e)}'
                    }

            except Exception as e:
                result['trend_strength'] = {
                    'error': f'Trend strength analysis failed: {str(e)}'
                }

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

        # Use Questrade-first approach with caching
        history = _get_ohlcv_cached(ticker, period=lookback_period)
        if history is None or history.empty:
            raise ValueError(f"No historical data found for {ticker}")

        levels = TechnicalAnalysis.find_support_resistance(history)
        
        return {
            "symbol": ticker,
            "lookback_period": lookback_period,
            **levels
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
        tickers = [validate_ticker(t) for t in tickers[:10]]  # Limit to 10 stocks
        
        comparisons = []
        for ticker in tickers:
            try:
                # Use Questrade-first approach with caching
                history = _get_ohlcv_cached(ticker, period=period)
                if history is None or history.empty:
                    comparisons.append({"symbol": ticker, "error": "No data available"})
                    continue
                
                indicators = TechnicalAnalysis.calculate_comprehensive_indicators(history)
                
                comparisons.append({
                    "symbol": ticker,
                    "price": indicators['current_price'],
                    "rsi": indicators['rsi']['value'],
                    "rsi_signal": indicators['rsi']['signal'],
                    "macd_trend": indicators['macd']['trend'],
                    "ma_trend": indicators['moving_averages']['trend'],
                    "bb_position": indicators['bollinger_bands']['position']
                })
            except Exception as e:
                comparisons.append({"symbol": ticker, "error": str(e)})
        
        return {
            "period": period,
            "comparison": comparisons
        }
    
    # NOTE: analyze_trend_strength was removed as redundant.
    # Trend strength scoring (0-100) with statistical validation is now
    # included in analyze_technical() with include_trend_score=True parameter.
    # The output appears in result['trend_strength'] with full statistical validation.

    # NOTE: detect_chart_patterns was removed as redundant.
    # These patterns (Golden Cross, Death Cross, trends) are already detected
    # in analyze_technical() with more context.


# ============================================================================
# BOOTSTRAP TOOLS - 4 Critical Analysis Tools ($0 cost, 50%+ improvement)
# ============================================================================

# Import bootstrap functions
try:
    from .technical_analysis_bootstrap import (
        analyze_volume,
        analyze_volatility,
        calculate_relative_strength,
        calculate_fundamental_scores,
        calculate_exhaustion_score,
        detect_cvd_divergence,
        count_trend_days,
        enhance_brooks_with_cvd,
        analyze_cvd
    )
    _bootstrap_available = True
except ImportError:
    _bootstrap_available = False
    logger.warning("Bootstrap analysis tools not available")


if _bootstrap_available:
    @mcp.tool()
    def analyze_volume_tool(
        ticker: str,
        period: Literal["1mo", "3mo", "6mo", "1y", "2y"] = "3mo",
        vwap_mode: Literal["session", "rolling", "anchored"] = "session",
        include_quality_score: bool = True
    ) -> dict[str, Any]:
        """Comprehensive volume analysis - VWAP, CVD, Volume Profile, OBV, MFI.

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
        - CVD (Cumulative Volume Delta) - buy vs sell pressure with divergence detection
        - Volume Profile (POC - Point of Control)
        - Relative Volume (current vs 20-day average)
        - OBV trend (Accumulation/Distribution)
        - MFI (Money Flow Index)
        - Accumulation/Distribution Line
        - Volume Quality Score (if include_quality_score=True)

        Note: CVD analysis includes trend direction and divergence signals for
        detecting exhaustion. This replaces the standalone calculate_true_cvd tool.

        Use before EVERY trade to confirm the move is real.
        """
        ticker = validate_ticker(ticker)
        result = analyze_volume(ticker, period, vwap_mode)

        # Add volume quality score if requested
        if include_quality_score:
            try:
                # Get historical data using Questrade-first approach with caching
                history = _get_ohlcv_cached(ticker, period=period)

                if history is not None and not history.empty:
                    # Calculate volume metrics
                    volume = history['Volume']
                    close = history['Close']

                    # Average volume (exclude current day - use previous 20 days)
                    avg_volume_20 = volume.shift(1).rolling(window=20).mean()
                    relative_volume = volume / avg_volume_20

                    # Volume trend
                    volume_slope = (volume.iloc[-5:].mean() - volume.iloc[-20:-5].mean()) / volume.iloc[-20:-5].mean()

                    # Price-volume relationship
                    price_change = close.pct_change()
                    price_up = price_change > 0
                    volume_up = relative_volume > 1.0

                    # Smart money indicator: Volume increases on up days (accumulation)
                    # vs volume increases on down days (distribution)
                    accumulation_days = (price_up & volume_up).sum()
                    distribution_days = (~price_up & volume_up).sum()

                    if (accumulation_days + distribution_days) > 0:
                        accumulation_ratio = accumulation_days / (accumulation_days + distribution_days)
                    else:
                        accumulation_ratio = 0.5

                    # Volume confirmation strength
                    latest_relative_volume = relative_volume.iloc[-1] if not relative_volume.empty else 1.0

                    if latest_relative_volume > 1.5:
                        volume_confirmation = "STRONG"
                    elif latest_relative_volume > 1.2:
                        volume_confirmation = "MODERATE"
                    elif latest_relative_volume > 0.8:
                        volume_confirmation = "NORMAL"
                    else:
                        volume_confirmation = "WEAK"

                    # Smart money probability (higher when accumulation on up days)
                    smart_money_probability = min(accumulation_ratio, 1.0)

                    # Accumulation detection
                    accumulation_detected = (
                        accumulation_ratio > 0.6 and
                        volume_slope > 0 and
                        latest_relative_volume > 1.0
                    )

                    result['volume_quality_score'] = {
                        'smart_money_probability': float(smart_money_probability),
                        'accumulation_detected': bool(accumulation_detected),
                        'distribution_detected': bool(accumulation_ratio < 0.4 and volume_slope > 0),
                        'volume_confirmation': volume_confirmation,
                        'accumulation_days': int(accumulation_days),
                        'distribution_days': int(distribution_days),
                        'volume_trend': 'INCREASING' if volume_slope > 0.1 else 'DECREASING' if volume_slope < -0.1 else 'STABLE',
                        'interpretation': (
                            f"{'ACCUMULATION' if accumulation_detected else 'DISTRIBUTION' if accumulation_ratio < 0.4 else 'NEUTRAL'} pattern detected. "
                            f"Smart money probability: {smart_money_probability:.1%}. "
                            f"Volume confirmation: {volume_confirmation}."
                        )
                    }
                else:
                    result['volume_quality_score'] = {
                        'note': 'Insufficient data for quality score',
                        'interpretation': 'Volume quality analysis unavailable'
                    }

            except Exception as e:
                result['volume_quality_score'] = {
                    'error': f'Quality score calculation failed: {str(e)}',
                    'interpretation': 'Volume quality analysis unavailable'
                }

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
        return analyze_volatility(ticker, period)
    
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
        return calculate_relative_strength(ticker, benchmark, period)
    
    @mcp.tool()
    def calculate_fundamental_scores_tool(
        ticker: str,
        max_periods: int = 8
    ) -> dict[str, Any]:
        """Calculate comprehensive fundamental quality scores.
        
        Critical for avoiding value traps and identifying quality.
        
        Returns:
        - Piotroski F-Score (0-9, >7 = excellent)
        - Altman Z-Score (>2.99 = safe, <1.81 = distress)
        - Bankruptcy risk assessment
        
        Always check F-Score before buying. <3 = value trap.
        """
        ticker = validate_ticker(ticker)
        return calculate_fundamental_scores(ticker, max_periods)



# ============================================================================
# ML-Enhanced Analysis Tools
# Institutional-grade analysis using López de Prado methods
# ============================================================================

@mcp.tool()
async def find_similar_historical_setups(
    ticker: str,
    lookback_period: Literal["6mo", "1y", "2y"] = "2y",
    similarity_threshold: float = 0.80,
    use_feature_importance: bool = True,
    target_return_pct: float | None = None,
    holding_period_days: int | None = None,
    direction: Literal["LONG", "SHORT"] = "LONG"
) -> str:
    """
    Find historical setups similar to current TECHNICAL conditions with target achievement analysis.

    **CRITICAL:** Matches on TECHNICAL INDICATORS (RSI, MACD, trend, volume),
    NOT on price levels. Uses tolerance-based matching with feature importance weighting.

    **NEW:** Calculates TARGET ACHIEVEMENT - how well similar setups achieved a specific target.
    This is NOT binary win/loss, but a percentage of target achieved.
    - Example: Target +5% in 10 days, actual +6% = 120% achievement
    - Example: Target +5% in 10 days, actual +4% = 80% achievement

    Args:
        ticker: Stock symbol
        lookback_period: How far back to search (6mo/1y/2y)
        similarity_threshold: Minimum similarity score 0-1 (default 0.80)
        use_feature_importance: Use calculated feature weights (default True)
        target_return_pct: Target return % for trade plan (e.g., 5.0 for 5%)
                          If provided with holding_period_days, calculates achievement
        holding_period_days: Number of trading days to hold (e.g., 10)
                            Required if target_return_pct is provided
        direction: Trade direction 'LONG' or 'SHORT' (default 'LONG')
                  LONG: positive returns are good
                  SHORT: negative returns are good (price going down)

    Returns:
        Comprehensive analysis with:
        - Number of similar TECHNICAL setups found
        - Success rates at 5d, 10d, 20d horizons
        - **Target Achievement Analysis** (if target params provided):
          - Average achievement % (e.g., 85% = achieved 85% of target)
          - Achievement distribution: STRONG (≥80%), MODERATE (60-79%), WEAK (<60%)
        - Statistical validation (t-test, confidence intervals)
        - Trade recommendation with confidence level

    Achievement Thresholds:
        - STRONG (≥80%): Achieved 80%+ of target (excellent confirmation)
        - MODERATE (60-79%): Partial target achievement
        - WEAK (0-59%): Moved in right direction but fell short
        - NEGATIVE (<0%): Moved in wrong direction

    Example:
        Trade Plan: LONG 5% in 10 days
        find_similar_historical_setups("NVDA", target_return_pct=5.0, holding_period_days=10, direction="LONG")
        Result: "Found 25 similar setups. Avg achievement: 92% (STRONG).
                12 setups achieved ≥80% of target. HIGH CONFIRMATION."

    References:
        - López de Prado (2018): Feature-weighted similarity
        - Multi-indicator confluence research (85% accuracy)
    """
    ticker = validate_ticker(ticker)

    # Map period to number of days
    period_map = {"6mo": 126, "1y": 252, "2y": 504}
    lookback_days = period_map[lookback_period]

    # Get historical data (Questrade primary, Yahoo fallback, cached)
    hist = _get_ohlcv_cached(ticker, period=lookback_period)

    if hist.empty or len(hist) < 50:
        return f"Error: Insufficient historical data for {ticker}"

    # Get earnings dates for earnings context matching
    earnings_dates = None
    try:
        earnings_history = yf_call(ticker, "get_earnings_history")
        if earnings_history is not None and isinstance(earnings_history, pd.DataFrame) and not earnings_history.empty:
            # Extract dates from index or column
            if hasattr(earnings_history.index, 'to_list'):
                earnings_dates = [pd.Timestamp(d) for d in earnings_history.index.to_list()]
            logger.info(f"Found {len(earnings_dates) if earnings_dates else 0} earnings dates for {ticker}")
    except Exception as e:
        logger.warning(f"Could not fetch earnings history for {ticker}: {e}")
        earnings_dates = None

    # Calculate current TECHNICAL conditions (NOT price-based!)
    # Uses enhanced technical indicators: RSI, MACD, ATR, trend t-stat, volume, etc.
    engine = SimilarityEngine(
        similarity_threshold=similarity_threshold,
        min_similar_setups=10  # Lowered from 20 for better results with default threshold
    )

    # Calculate current technical conditions from most recent data
    # Include earnings context if earnings dates available
    current_idx = len(hist) - 1
    current_conditions = engine._calculate_conditions(hist, current_idx, earnings_dates)

    if not current_conditions:
        return f"Error: Insufficient data to calculate current technical conditions for {ticker}"

    # Get feature importance weights if requested
    feature_weights = None
    if use_feature_importance:
        try:
            # Calculate feature importance from historical data
            from .ml_core import calculate_feature_importance

            prices = hist['Close']

            # Calculate forward returns for feature importance
            forward_returns = prices.shift(-10) / prices - 1

            # Get all technical features for each day
            feature_matrix = []
            valid_indices = []

            for idx in range(50, len(hist) - 10):  # Need history for indicators and forward returns
                conditions = engine._calculate_conditions(hist, idx)
                if conditions and not pd.isna(forward_returns.iloc[idx]):
                    # Extract numerical features only (exclude categorical)
                    numerical_features = {
                        k: v for k, v in conditions.items()
                        if not isinstance(v, str)
                    }
                    feature_matrix.append(numerical_features)
                    valid_indices.append(idx)

            if len(feature_matrix) > 30:  # Need enough samples
                # Convert to DataFrame
                features_df = pd.DataFrame(feature_matrix)
                returns = forward_returns.iloc[valid_indices]

                # Calculate importance using Spearman correlation
                importances = calculate_feature_importance(
                    features_df,
                    returns,
                    method='spearman'
                )

                # Convert to weights (normalize to sum to 1)
                total_importance = sum(abs(imp) for imp in importances.values())
                if total_importance > 0:
                    feature_weights = {
                        k: abs(v) / total_importance
                        for k, v in importances.items()
                    }

                logger.info(f"Calculated feature importance for {ticker}: {feature_weights}")
            else:
                logger.warning(f"Insufficient samples for feature importance ({len(feature_matrix)} < 30), using defaults")

        except Exception as e:
            logger.warning(f"Could not calculate feature importance: {e}, using defaults")
            feature_weights = None

    # Find similar TECHNICAL setups (not similar prices!)
    # Include earnings context for matching similar earnings proximity patterns
    similar_setups = engine.find_similar_setups(
        ticker=ticker,
        current_conditions=current_conditions,
        historical_data=hist,
        lookback_periods=min(lookback_days, len(hist) - 20),
        feature_weights=feature_weights,  # Pass feature weights for weighted matching
        target_return_pct=target_return_pct,
        holding_period_days=holding_period_days,
        direction=direction,
        earnings_dates=earnings_dates  # Pass earnings dates for earnings context matching
    )

    # Analyze results (with target achievement if parameters provided)
    result = engine.analyze_similar_setups(
        ticker=ticker,
        current_conditions=current_conditions,
        similar_setups=similar_setups,
        target_return_pct=target_return_pct,
        holding_period_days=holding_period_days,
        direction=direction
    )

    # Generate report
    report = generate_similarity_report(result)

    # Add feature importance section if weights were used
    if feature_weights:
        # Sort by weight
        sorted_features = sorted(feature_weights.items(), key=lambda x: x[1], reverse=True)

        feature_section = "\n## Feature Importance Weights Used\n\n"
        feature_section += "**Top Features in Similarity Matching:**\n"

        for feature, weight in sorted_features[:5]:  # Top 5
            feature_section += f"- **{feature}:** {weight:.1%} weight\n"

        feature_section += "\n*Similarity matching weighted by feature importance - " \
                          "important features (RSI, trend) have more influence than less predictive features.*\n"

        # Insert before the final line
        report = report.replace(
            "---\n*Generated with institutional-grade similarity-based backtesting*",
            f"{feature_section}\n---\n*Generated with feature-weighted institutional-grade similarity-based backtesting*"
        )

    return report


@mcp.tool()
async def analyze_ml_enhanced(
    ticker: str,
    period: Literal["3mo", "6mo", "1y"] = "6mo"
) -> str:
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
        Enhanced analysis with:
        - Historical success rate from triple-barrier method
        - Trend confidence (95% or 99% statistical significance)
        - EMA crossover signals (golden/death crosses)
        - Expected returns and holding periods
        - Kelly-optimal position size
    """
    ticker = validate_ticker(ticker)

    # Get historical data (Questrade primary, Yahoo fallback, cached)
    hist = _get_ohlcv_cached(ticker, period=period)

    if hist is None or hist.empty or len(hist) < 50:
        return f"Error: Insufficient data for {ticker}"

    prices = hist['Close']

    # 1. Triple-Barrier Analysis
    tb_result = apply_triple_barrier_labels(
        prices,
        profit_target=0.05,
        stop_loss=0.05,
        max_holding_days=10
    )

    # 2. Trend-Scanning Analysis
    ts_result = get_trend_scanning_labels(
        prices,
        lookforward_window=20,
        t_stat_threshold=1.96
    )

    # 3. EMA Crossover Analysis (CRITICAL TRADING SIGNALS)
    ema_20 = prices.ewm(span=20, adjust=False).mean().iloc[-1]
    ema_50 = prices.ewm(span=50, adjust=False).mean().iloc[-1] if len(prices) >= 50 else ema_20
    ema_100 = prices.ewm(span=100, adjust=False).mean().iloc[-1] if len(prices) >= 100 else ema_50
    ema_200 = prices.ewm(span=200, adjust=False).mean().iloc[-1] if len(prices) >= 200 else ema_100

    current_price = prices.iloc[-1]

    # Detect crossovers (looking back 5 days for recent crosses)
    ema_20_series = prices.ewm(span=20, adjust=False).mean()
    ema_50_series = prices.ewm(span=50, adjust=False).mean() if len(prices) >= 50 else ema_20_series
    ema_100_series = prices.ewm(span=100, adjust=False).mean() if len(prices) >= 100 else ema_50_series
    ema_200_series = prices.ewm(span=200, adjust=False).mean() if len(prices) >= 200 else ema_100_series

    # Detect 20/50 cross
    cross_20_50 = "NONE"
    if len(prices) >= 50:
        for i in range(1, min(6, len(ema_20_series))):
            prev_20 = ema_20_series.iloc[-i-1]
            prev_50 = ema_50_series.iloc[-i-1]
            curr_20 = ema_20_series.iloc[-1]
            curr_50 = ema_50_series.iloc[-1]

            if prev_20 <= prev_50 and curr_20 > curr_50:
                cross_20_50 = "BULLISH_CROSS"
                break
            elif prev_20 >= prev_50 and curr_20 < curr_50:
                cross_20_50 = "BEARISH_CROSS"
                break

        if cross_20_50 == "NONE":
            cross_20_50 = "BULLISH" if curr_20 > curr_50 else "BEARISH"

    # Detect 20/100 cross
    cross_20_100 = "NONE"
    if len(prices) >= 100:
        for i in range(1, min(6, len(ema_20_series))):
            prev_20 = ema_20_series.iloc[-i-1]
            prev_100 = ema_100_series.iloc[-i-1]
            curr_20 = ema_20_series.iloc[-1]
            curr_100 = ema_100_series.iloc[-1]

            if prev_20 <= prev_100 and curr_20 > curr_100:
                cross_20_100 = "BULLISH_CROSS"
                break
            elif prev_20 >= prev_100 and curr_20 < curr_100:
                cross_20_100 = "BEARISH_CROSS"
                break

        if cross_20_100 == "NONE":
            cross_20_100 = "BULLISH" if curr_20 > curr_100 else "BEARISH"

    # Detect 20/200 cross (GOLDEN CROSS / DEATH CROSS)
    cross_20_200 = "NONE"
    golden_cross = False
    death_cross = False
    if len(prices) >= 200:
        for i in range(1, min(6, len(ema_20_series))):
            prev_20 = ema_20_series.iloc[-i-1]
            prev_200 = ema_200_series.iloc[-i-1]
            curr_20 = ema_20_series.iloc[-1]
            curr_200 = ema_200_series.iloc[-1]

            if prev_20 <= prev_200 and curr_20 > curr_200:
                cross_20_200 = "GOLDEN_CROSS"
                golden_cross = True
                break
            elif prev_20 >= prev_200 and curr_20 < curr_200:
                cross_20_200 = "DEATH_CROSS"
                death_cross = True
                break

        if cross_20_200 == "NONE":
            cross_20_200 = "BULLISH" if curr_20 > curr_200 else "BEARISH"

    # EMA alignment (all EMAs in order = strong trend)
    bullish_alignment = (ema_20 > ema_50 > ema_100 > ema_200) if len(prices) >= 200 else False
    bearish_alignment = (ema_20 < ema_50 < ema_100 < ema_200) if len(prices) >= 200 else False

    # 4. Price/EMA Interaction Signals (NEW - Dynamic Support/Resistance)
    volumes = hist['Volume'] if 'Volume' in hist.columns else None

    # Detect EMA bounce (price bouncing off EMA as support/resistance)
    ema_bounce_20 = detect_ema_bounce(prices, volumes, ema_period=20)
    ema_bounce_50 = detect_ema_bounce(prices, volumes, ema_period=50)

    # Detect price crossing EMA (breakout/breakdown)
    price_ema_cross_20 = detect_ema_cross(prices, ema_period=20)
    price_ema_cross_50 = detect_ema_cross(prices, ema_period=50)

    # Detect EMA extension (overextended price - reversal warning)
    ema_extension_20 = detect_ema_extension(prices, ema_period=20)

    # 5. VWAP Support/Resistance Signals (NEW - Institutional Fair Value)
    if volumes is not None:
        # Detect VWAP bounce (institutional support/resistance)
        vwap_bounce = detect_vwap_bounce(prices, volumes, window=20)

        # Detect price crossing VWAP (sentiment shift)
        vwap_cross = detect_vwap_cross(prices, volumes, window=20)

        # Interpret VWAP position
        vwap_position = interpret_vwap_position(vwap_cross['distance_pct'])
    else:
        # No volume data - set defaults
        vwap_bounce = {'signal': 'NONE', 'vwap_level': 0.0, 'distance_pct': 0.0, 'bounce_days_ago': 0, 'volume_confirmed': False, 'strength': 'NONE'}
        vwap_cross = {'signal': 'NONE', 'vwap_level': 0.0, 'distance_pct': 0.0, 'cross_days_ago': 0}
        vwap_position = {'position': 'UNKNOWN', 'sentiment': 'NEUTRAL', 'interpretation': 'No volume data available'}

    # 6. Volume Confirmation Signals (NEW - Smart Money Detection)
    if volumes is not None:
        # Detect volume surge
        volume_surge = detect_volume_surge(volumes, window=20, threshold_pct=0.50)

        # Calculate OBV signals
        obv_result = calculate_obv_signal(prices, volumes)

        # Confirm EMA 20/50 crossover with volume
        ema_cross_volume_conf = confirm_crossover_with_volume(cross_20_50, volume_surge)

        # Confirm VWAP crossover with volume
        vwap_cross_volume_conf = confirm_crossover_with_volume(vwap_cross['signal'], volume_surge)
    else:
        # No volume data - set defaults
        volume_surge = {'signal': 'NORMAL', 'current_volume': 0, 'avg_volume': 0.0, 'volume_ratio': 0.0, 'surge_strength': 'NORMAL'}
        obv_result = {'obv': pd.Series(), 'obv_trend': 'NEUTRAL', 'obv_strength': 0.0, 'divergence': 'NONE', 'signal': 'NEUTRAL'}
        ema_cross_volume_conf = {'confirmed': False, 'confidence': 'LOW', 'explanation': 'No volume data'}
        vwap_cross_volume_conf = {'confirmed': False, 'confidence': 'LOW', 'explanation': 'No volume data'}

    # 7. EMA/VWAP Confluence Detection (NEW - Multi-Indicator Alignment)
    current_price = prices.iloc[-1]
    # Note: ema_20, ema_50 are already single float values (calculated earlier with .iloc[-1])
    # VWAP is calculated in vwap_cross and returned as 'vwap_level'
    vwap_current = vwap_cross['vwap_level'] if vwap_cross['vwap_level'] > 0 else current_price

    confluence_result = detect_ema_vwap_confluence(
        price=current_price,
        ema_20=ema_20,
        ema_50=ema_50,
        vwap=vwap_current
    )

    # 8. Order Blocks Detection (Institutional Footprints)
    order_blocks_result = detect_order_blocks(
        prices=prices,
        lookback=50,
        impulse_threshold_pct=3.0,
        proximity_pct=2.0
    )

    # 9. Supply/Demand Zones Detection (NEW - Price Action Zones)
    supply_demand_result = detect_supply_demand_zones(
        prices=prices,
        lookback=50,
        consolidation_bars=3,
        impulse_threshold_pct=5.0,
        proximity_pct=2.0
    )

    # 10. Exhaustion Score Analysis (NEW - Volumetric Liquidity Enhancement)
    # Calculate exhaustion for both LONG and SHORT directions
    exhaustion_long = calculate_exhaustion_score(ticker, direction="LONG", period=period) if _bootstrap_available else {"score": 0, "level": "UNKNOWN"}
    exhaustion_short = calculate_exhaustion_score(ticker, direction="SHORT", period=period) if _bootstrap_available else {"score": 0, "level": "UNKNOWN"}

    # Determine which direction is more relevant based on current trend
    current_trend_direction = "LONG" if ts_result.labels.iloc[-1] >= 0 else "SHORT"
    primary_exhaustion = exhaustion_long if current_trend_direction == "LONG" else exhaustion_short

    # 11. Calculate Kelly size (using triple-barrier success rate)
    if tb_result.success_rate > 0.5:
        expected_return = tb_result.avg_profit if tb_result.avg_profit > 0 else 0.03
        volatility = prices.pct_change().std()
        kelly_size = calculate_kelly_size(
            predicted_prob=tb_result.success_rate,
            predicted_return=expected_return,
            volatility=volatility,
            kelly_fraction=0.25
        )
    else:
        kelly_size = 0.0

    # Build comprehensive recommendation (now 19 signals - added Exhaustion)
    bullish_signals = sum([
        # ML Signals (2)
        tb_result.success_rate > 0.55,
        ts_result.confidence.iloc[-1] > 0.90 and ts_result.labels.iloc[-1] == 1,
        # EMA/EMA Crossovers (4)
        cross_20_50 in ["BULLISH_CROSS", "BULLISH"],
        cross_20_100 in ["BULLISH_CROSS", "BULLISH"],
        cross_20_200 in ["GOLDEN_CROSS", "BULLISH"],
        bullish_alignment,
        # Price/EMA Interactions (3)
        ema_bounce_20['signal'] == 'BULLISH_BOUNCE' or ema_bounce_50['signal'] == 'BULLISH_BOUNCE',
        price_ema_cross_20['signal'] in ['BULLISH_CROSS', 'ABOVE'],
        ema_extension_20['signal'] == 'NORMAL',  # Not overextended = healthy
        # VWAP Signals (3)
        vwap_bounce['signal'] == 'VWAP_BOUNCE_SUPPORT',
        vwap_cross['signal'] in ['BULLISH_VWAP_CROSS', 'ABOVE_VWAP'],
        vwap_position['sentiment'] in ['STRONG_BULLISH', 'BULLISH'],
        # Volume Confirmation Signals (3)
        volume_surge['signal'] == 'VOLUME_SURGE',
        obv_result['signal'] == 'BULLISH',
        obv_result['divergence'] == 'BULLISH_DIVERGENCE' or ema_cross_volume_conf['confirmed'] or vwap_cross_volume_conf['confirmed'],
        # EMA/VWAP Confluence (1)
        confluence_result['signal'] in ['STRONG_BULLISH_CONFLUENCE', 'BULLISH_CONFLUENCE'],
        # Order Blocks (1)
        order_blocks_result['signal'] == 'BULLISH_ORDER_BLOCK_TEST',
        # Supply/Demand Zones (1)
        supply_demand_result['signal'] == 'DEMAND_ZONE_TEST',
        # Exhaustion (1) - NEW: Low exhaustion for LONG = bullish
        exhaustion_long.get('level', '') in ['NO_EXHAUSTION', 'LOW_EXHAUSTION']
    ])

    bearish_signals = sum([
        # ML Signals (2)
        tb_result.success_rate < 0.45,
        ts_result.confidence.iloc[-1] > 0.90 and ts_result.labels.iloc[-1] == -1,
        # EMA/EMA Crossovers (4)
        cross_20_50 in ["BEARISH_CROSS", "BEARISH"],
        cross_20_100 in ["BEARISH_CROSS", "BEARISH"],
        cross_20_200 in ["DEATH_CROSS", "BEARISH"],
        bearish_alignment,
        # Price/EMA Interactions (3)
        ema_bounce_20['signal'] == 'BEARISH_BOUNCE' or ema_bounce_50['signal'] == 'BEARISH_BOUNCE',
        price_ema_cross_20['signal'] in ['BEARISH_CROSS', 'BELOW'],
        ema_extension_20['signal'] == 'NORMAL',  # Not overextended = healthy
        # VWAP Signals (3)
        vwap_bounce['signal'] == 'VWAP_BOUNCE_RESISTANCE',
        vwap_cross['signal'] in ['BEARISH_VWAP_CROSS', 'BELOW_VWAP'],
        vwap_position['sentiment'] in ['STRONG_BEARISH', 'BEARISH'],
        # Volume Confirmation Signals (3)
        volume_surge['signal'] == 'LOW_VOLUME',  # Low volume on moves = weak
        obv_result['signal'] == 'BEARISH',
        obv_result['divergence'] == 'BEARISH_DIVERGENCE' or (ema_cross_volume_conf['confirmed'] == False and 'CROSS' in cross_20_50),
        # EMA/VWAP Confluence (1)
        confluence_result['signal'] in ['STRONG_BEARISH_CONFLUENCE', 'BEARISH_CONFLUENCE'],
        # Order Blocks (1)
        order_blocks_result['signal'] == 'BEARISH_ORDER_BLOCK_TEST',
        # Supply/Demand Zones (1)
        supply_demand_result['signal'] == 'SUPPLY_ZONE_TEST',
        # Exhaustion (1) - NEW: High exhaustion for LONG = bearish
        exhaustion_long.get('level', '') in ['HIGH_EXHAUSTION', 'MODERATE_EXHAUSTION']
    ])

    # Generate recommendation (adjusted thresholds for 19 total signals)
    if bullish_signals >= 10:
        recommendation = "🟢 STRONG BUY - Multiple bullish confirmations"
    elif bullish_signals >= 9:
        recommendation = "🟢 BUY - Bullish signals dominant"
    elif bearish_signals >= 10:
        recommendation = "🔴 STRONG SELL - Multiple bearish confirmations"
    elif bearish_signals >= 9:
        recommendation = "🔴 SELL - Bearish signals dominant"
    else:
        recommendation = "⚪ NEUTRAL - Mixed signals, wait for clearer setup"

    # Calculate total setups from labels
    total_setups = len(tb_result.labels)

    # Build report
    report = f"""# ML-Enhanced Analysis: {ticker}

**Current Price:** ${current_price:.2f}

## EMA Crossover Signals (CRITICAL) 🎯

### Current EMA Levels:
- **EMA 20:** ${ema_20:.2f} ({'+' if current_price > ema_20 else ''}{((current_price/ema_20-1)*100):.1f}%)
- **EMA 50:** ${ema_50:.2f} ({'+' if current_price > ema_50 else ''}{((current_price/ema_50-1)*100):.1f}%)
- **EMA 100:** ${ema_100:.2f} ({'+' if current_price > ema_100 else ''}{((current_price/ema_100-1)*100):.1f}%)
- **EMA 200:** ${ema_200:.2f} ({'+' if current_price > ema_200 else ''}{((current_price/ema_200-1)*100):.1f}%)

### Crossover Status:
- **EMA 20/50:** {cross_20_50}{'  🚀' if cross_20_50 == 'BULLISH_CROSS' else ' 💥' if cross_20_50 == 'BEARISH_CROSS' else ''}
- **EMA 20/100:** {cross_20_100}{'  🚀' if cross_20_100 == 'BULLISH_CROSS' else ' 💥' if cross_20_100 == 'BEARISH_CROSS' else ''}
- **EMA 20/200:** {cross_20_200}{'  🌟 GOLDEN CROSS!' if golden_cross else ' ☠️  DEATH CROSS!' if death_cross else ''}

### EMA Alignment:
{'✅ **BULLISH ALIGNMENT** - All EMAs in bullish order (20>50>100>200)' if bullish_alignment else '❌ **BEARISH ALIGNMENT** - All EMAs in bearish order (20<50<100<200)' if bearish_alignment else '⚪ Mixed alignment - no clear trend from EMAs'}

## Price/EMA Interaction Signals (NEW) 📊

### EMA Bounce Detection:
- **EMA 20 Bounce:** {ema_bounce_20['signal']}{' (' + ema_bounce_20['strength'] + ')' if ema_bounce_20['signal'] != 'NONE' else ''}{' 🔊 Volume Confirmed' if ema_bounce_20.get('volume_confirmed', False) else ''}
  - Distance from EMA 20: {ema_bounce_20['distance_pct']:+.2f}%
  - {ema_bounce_20['bounce_days_ago']} days ago{'⚡' if ema_bounce_20['signal'] in ['BULLISH_BOUNCE', 'BEARISH_BOUNCE'] else ''}

- **EMA 50 Bounce:** {ema_bounce_50['signal']}{' (' + ema_bounce_50['strength'] + ')' if ema_bounce_50['signal'] != 'NONE' else ''}{' 🔊 Volume Confirmed' if ema_bounce_50.get('volume_confirmed', False) else ''}
  - Distance from EMA 50: {ema_bounce_50['distance_pct']:+.2f}%
  - {ema_bounce_50['bounce_days_ago']} days ago{'⚡' if ema_bounce_50['signal'] in ['BULLISH_BOUNCE', 'BEARISH_BOUNCE'] else ''}

### Price Crossing EMA:
- **Price vs EMA 20:** {price_ema_cross_20['signal']}{' (' + str(price_ema_cross_20['cross_days_ago']) + ' days ago)' if price_ema_cross_20['signal'] in ['BULLISH_CROSS', 'BEARISH_CROSS'] else ''}
  - Distance: {price_ema_cross_20['distance_pct']:+.2f}%

- **Price vs EMA 50:** {price_ema_cross_50['signal']}{' (' + str(price_ema_cross_50['cross_days_ago']) + ' days ago)' if price_ema_cross_50['signal'] in ['BULLISH_CROSS', 'BEARISH_CROSS'] else ''}
  - Distance: {price_ema_cross_50['distance_pct']:+.2f}%

### Price Extension Analysis:
- **EMA 20 Extension:** {ema_extension_20['signal']} - {ema_extension_20['severity']}
  - {'⚠️  Price extended ' + f"{ema_extension_20['distance_pct']:+.2f}%" + ' from EMA 20 - potential mean reversion' if ema_extension_20['signal'] != 'NORMAL' else '✅ Price within normal range of EMA 20'}

## VWAP Signals (Institutional Fair Value) 💎

### VWAP Bounce Detection:
- **VWAP Bounce:** {vwap_bounce['signal']}{' (' + vwap_bounce['strength'] + ')' if vwap_bounce['signal'] != 'NONE' else ''}{' 🔊 Volume Confirmed' if vwap_bounce.get('volume_confirmed', False) else ''}
  - VWAP Level: ${vwap_bounce['vwap_level']:.2f}
  - Distance from VWAP: {vwap_bounce['distance_pct']:+.2f}%
  - {vwap_bounce['bounce_days_ago']} days ago{'⚡' if vwap_bounce['signal'] in ['VWAP_BOUNCE_SUPPORT', 'VWAP_BOUNCE_RESISTANCE'] else ''}

### VWAP Crossing:
- **Price vs VWAP:** {vwap_cross['signal']}{' (' + str(vwap_cross['cross_days_ago']) + ' days ago)' if vwap_cross['signal'] in ['BULLISH_VWAP_CROSS', 'BEARISH_VWAP_CROSS'] else ''}
  - Distance: {vwap_cross['distance_pct']:+.2f}%

### VWAP Position Interpretation:
- **{vwap_position['position']}** - {vwap_position['sentiment']}
  - {vwap_position['interpretation']}

## Volume Confirmation (Smart Money) 📈

### Volume Surge Detection:
- **Current Volume:** {volume_surge['current_volume']:,} shares
- **20-Day Average:** {volume_surge['avg_volume']:,.0f} shares
- **Volume Ratio:** {volume_surge['volume_ratio']:.2f}x average
- **Signal:** {volume_surge['signal']} - {volume_surge['surge_strength']}
  - {'⚡ VOLUME SURGE detected!' if volume_surge['signal'] == 'VOLUME_SURGE' else '⚠️ Low volume warning' if volume_surge['signal'] == 'LOW_VOLUME' else '✅ Normal volume'}

### On-Balance Volume (OBV):
- **OBV Trend:** {obv_result['obv_trend']}
- **Trend Strength:** {obv_result['obv_strength']:.1f}/100
- **Divergence:** {obv_result['divergence']}
  - {'⚡ BULLISH DIVERGENCE - Price down but volume accumulating!' if obv_result['divergence'] == 'BULLISH_DIVERGENCE' else '⚠️ BEARISH DIVERGENCE - Price up but volume distributing!' if obv_result['divergence'] == 'BEARISH_DIVERGENCE' else '✅ No divergence detected'}
- **Signal:** {obv_result['signal']}

### Crossover Volume Confirmation:
- **EMA 20/50 Cross:** {ema_cross_volume_conf['explanation']}
  - Confidence: {ema_cross_volume_conf['confidence']}
  - {'✅ Volume confirmed' if ema_cross_volume_conf['confirmed'] else '⚠️ Unconfirmed'}

- **VWAP Cross:** {vwap_cross_volume_conf['explanation']}
  - Confidence: {vwap_cross_volume_conf['confidence']}
  - {'✅ Volume confirmed' if vwap_cross_volume_conf['confirmed'] else '⚠️ Unconfirmed'}

## EMA/VWAP Confluence (Multi-Indicator Alignment) 🎯

### Alignment Analysis:
- **Signal:** {confluence_result['signal']}
- **Strength:** {confluence_result['strength']}
- **Alignment Count:** {confluence_result['alignment_count']}/4 indicators aligned
  - Bullish: {confluence_result['bullish_count']}/4
  - Bearish: {confluence_result['bearish_count']}/4

### Indicator Positions:
- **Price above EMA 20:** {'✅ YES' if confluence_result['price_above_ema20'] else '❌ NO'}
- **Price above EMA 50:** {'✅ YES' if confluence_result['price_above_ema50'] else '❌ NO'}
- **Price above VWAP:** {'✅ YES' if confluence_result['price_above_vwap'] else '❌ NO'}
- **EMA 20 above EMA 50:** {'✅ YES' if confluence_result['ema20_above_ema50'] else '❌ NO'}

### Interpretation:
{confluence_result['interpretation']}

## Order Blocks (Institutional Footprints) 📍

### Order Block Analysis:
- **Signal:** {order_blocks_result['signal']}
- **Bullish Blocks Found:** {len(order_blocks_result['bullish_blocks'])}
- **Bearish Blocks Found:** {len(order_blocks_result['bearish_blocks'])}

### Closest Order Blocks:
- **Bullish Block Distance:** {order_blocks_result['distance_to_bullish_pct']:.2f}% below
  {f"  - Price Range: ${order_blocks_result['closest_bullish_block']['price_low']:.2f} - ${order_blocks_result['closest_bullish_block']['price_high']:.2f}" if order_blocks_result['closest_bullish_block'] else "  - None detected"}
  {f"  - Age: {order_blocks_result['closest_bullish_block']['age_days']} days" if order_blocks_result['closest_bullish_block'] else ""}
  {f"  - Original Impulse: +{order_blocks_result['closest_bullish_block']['impulse_size']:.1f}%" if order_blocks_result['closest_bullish_block'] else ""}

- **Bearish Block Distance:** {order_blocks_result['distance_to_bearish_pct']:.2f}% above
  {f"  - Price Range: ${order_blocks_result['closest_bearish_block']['price_low']:.2f} - ${order_blocks_result['closest_bearish_block']['price_high']:.2f}" if order_blocks_result['closest_bearish_block'] else "  - None detected"}
  {f"  - Age: {order_blocks_result['closest_bearish_block']['age_days']} days" if order_blocks_result['closest_bearish_block'] else ""}
  {f"  - Original Impulse: -{order_blocks_result['closest_bearish_block']['impulse_size']:.1f}%" if order_blocks_result['closest_bearish_block'] else ""}

### Interpretation:
{order_blocks_result['interpretation']}

## Supply/Demand Zones (Price Action Zones) 🏛️

### Zone Analysis:
- **Signal:** {supply_demand_result['signal']}
- **Demand Zones Found:** {len(supply_demand_result['demand_zones'])}
- **Supply Zones Found:** {len(supply_demand_result['supply_zones'])}

### Closest Zones:
- **Demand Zone Distance:** {supply_demand_result['distance_to_demand_pct']:.2f}% below
  {f"  - Zone Range: ${supply_demand_result['closest_demand_zone']['zone_low']:.2f} - ${supply_demand_result['closest_demand_zone']['zone_high']:.2f}" if supply_demand_result['closest_demand_zone'] else "  - None detected"}
  {f"  - Age: {supply_demand_result['closest_demand_zone']['age_days']} days" if supply_demand_result['closest_demand_zone'] else ""}
  {f"  - Original Impulse: +{supply_demand_result['closest_demand_zone']['impulse_size']:.1f}%" if supply_demand_result['closest_demand_zone'] else ""}
  {f"  - Consolidation: {supply_demand_result['closest_demand_zone']['consolidation_bars']} bars" if supply_demand_result['closest_demand_zone'] else ""}

- **Supply Zone Distance:** {supply_demand_result['distance_to_supply_pct']:.2f}% above
  {f"  - Zone Range: ${supply_demand_result['closest_supply_zone']['zone_low']:.2f} - ${supply_demand_result['closest_supply_zone']['zone_high']:.2f}" if supply_demand_result['closest_supply_zone'] else "  - None detected"}
  {f"  - Age: {supply_demand_result['closest_supply_zone']['age_days']} days" if supply_demand_result['closest_supply_zone'] else ""}
  {f"  - Original Impulse: -{supply_demand_result['closest_supply_zone']['impulse_size']:.1f}%" if supply_demand_result['closest_supply_zone'] else ""}
  {f"  - Consolidation: {supply_demand_result['closest_supply_zone']['consolidation_bars']} bars" if supply_demand_result['closest_supply_zone'] else ""}

### Interpretation:
{supply_demand_result['interpretation']}

## Exhaustion Analysis (Volumetric Liquidity) 🔋 NEW

### LONG Position Exhaustion:
- **Score:** {exhaustion_long.get('score', 0)}/100
- **Level:** {exhaustion_long.get('level', 'UNKNOWN')}
- **Suggested Action:** {exhaustion_long.get('suggested_action', 'N/A')}

### Component Breakdown (LONG):
{f"- CVD Divergence: {exhaustion_long.get('components', {}).get('cvd_divergence', {}).get('points', 0)}/20 pts" if exhaustion_long.get('components') else "- CVD Divergence: N/A"}
{f"- RSI Divergence: {exhaustion_long.get('components', {}).get('rsi_divergence', {}).get('points', 0)}/20 pts" if exhaustion_long.get('components') else "- RSI Divergence: N/A"}
{f"- Trend Days: {exhaustion_long.get('components', {}).get('trend_days', {}).get('points', 0)}/25 pts ({exhaustion_long.get('components', {}).get('trend_days', {}).get('count', 0)} consecutive)" if exhaustion_long.get('components') else "- Trend Days: N/A"}
{f"- VWAP Extension: {exhaustion_long.get('components', {}).get('vwap_extension', {}).get('points', 0)}/15 pts (σ={exhaustion_long.get('components', {}).get('vwap_extension', {}).get('sigma_distance', 0)})" if exhaustion_long.get('components') else "- VWAP Extension: N/A"}
{f"- Volume Decline: {exhaustion_long.get('components', {}).get('volume_decline', {}).get('points', 0)}/20 pts" if exhaustion_long.get('components') else "- Volume Decline: N/A"}

### Interpretation:
{exhaustion_long.get('interpretation', 'No exhaustion data available')}

{'⚠️ **WARNING:** ' + exhaustion_long.get('action_detail', '') if exhaustion_long.get('level', '') in ['HIGH_EXHAUSTION', 'MODERATE_EXHAUSTION'] else '✅ No significant exhaustion detected for LONG positions'}

## Triple-Barrier Analysis
- **Success Rate:** {tb_result.success_rate:.1%} ({total_setups} historical setups)
- **Average Profit:** {tb_result.avg_profit:.2%} when winning
- **Average Loss:** {tb_result.avg_loss:.2%} when losing
- **Risk/Reward Ratio:** {tb_result.risk_reward_ratio:.2f}:1
- **Average Holding:** {tb_result.avg_holding_days:.1f} days

## Trend Analysis (Statistical)
- **Current Trend:** {'UPTREND' if ts_result.labels.iloc[-1] == 1 else 'DOWNTREND' if ts_result.labels.iloc[-1] == -1 else 'NEUTRAL'}
- **Statistical Confidence:** {ts_result.confidence.iloc[-1]:.1%}
- **T-Statistic:** {ts_result.t_statistics.iloc[-1]:.2f}

## Position Sizing
- **Kelly-Optimal Size:** {kelly_size:.1%} of capital

## Final Recommendation
**{recommendation}**

**Signal Confluence:**
- Bullish Signals: {bullish_signals}/19
- Bearish Signals: {bearish_signals}/19

**Signal Breakdown:**
- ML Signals: 2 (Triple-Barrier + Trend-Scanning)
- EMA/EMA Crosses: 4 (20/50, 20/100, 20/200, Alignment)
- Price/EMA Interactions: 3 (Bounce, Cross, Extension)
- VWAP Signals: 3 (Bounce, Cross, Position)
- Volume Confirmation: 3 (Surge, OBV, Crossover Confirmation)
- EMA/VWAP Confluence: 1 (Multi-Indicator Alignment)
- Order Blocks: 1 (Institutional Footprints)
- Supply/Demand Zones: 1 (Price Action Zones)
- Exhaustion Analysis: 1 (Volumetric Liquidity) ⭐ NEW

---
*Based on {len(prices)} days of historical data with Price/EMA + VWAP + Volume + Confluence + Order Blocks + Supply/Demand + Exhaustion analysis*
"""

    return report


@mcp.tool()
async def validate_strategy_robustness(
    ticker: str,
    n_trials: int = 100
) -> str:
    """
    Validate if analysis results are statistically robust or just lucky.

    Uses multiple testing corrections to account for p-hacking and
    overfitting. Essential before making trading decisions.

    Args:
        ticker: Stock symbol
        n_trials: Number of strategies tested (default 100)

    Returns:
        Validation metrics:
        - Deflated Sharpe Ratio
        - Harvey-Liu-Zhu t-stat threshold
        - Probability results are not due to luck
    """
    ticker = validate_ticker(ticker)

    # Get returns (Questrade primary, Yahoo fallback, cached)
    hist = _get_ohlcv_cached(ticker, period="1y")
    if hist is None or hist.empty:
        return f"Error: No data for {ticker}"

    returns = hist['Close'].pct_change().dropna()

    # Calculate Deflated Sharpe
    ds_result = calculate_deflated_sharpe(
        returns,
        n_trials=n_trials,
        annual_factor=252
    )

    # Calculate HLZ threshold
    hlz_threshold = harvey_liu_zhu_threshold(n_trials=n_trials)

    # Determine if robust
    is_robust = (
        ds_result['deflated_sharpe'] > 1.0 and
        ds_result['probability_significant'] > 0.95
    )

    report = f"""# Strategy Robustness Validation: {ticker}

## Deflated Sharpe Ratio
- **Raw Sharpe:** {ds_result['raw_sharpe']:.2f}
- **Deflated Sharpe:** {ds_result['deflated_sharpe']:.2f}
- **Probability Significant:** {ds_result['probability_significant']:.1%}

## Multiple Testing Correction
- **Trials Tested:** {n_trials}
- **HLZ T-Stat Threshold:** {hlz_threshold:.2f} (vs standard 1.96)
- **Expected Max Sharpe:** {ds_result['expected_max_sharpe']:.2f}

## Assessment
**Result:** {'✅ ROBUST - Strategy passes validation' if is_robust else '❌ NOT ROBUST - Results may be due to luck'}

**Interpretation:**
- Deflated Sharpe > 1.0: {'✅ Pass' if ds_result['deflated_sharpe'] > 1.0 else '❌ Fail'}
- Probability > 95%: {'✅ Pass' if ds_result['probability_significant'] > 0.95 else '❌ Fail'}

---
*Validation accounts for {n_trials} tested strategies*
"""

    return report


@mcp.tool()
async def calculate_feature_importance_analysis(
    ticker: str,
    period: Literal["3mo", "6mo", "1y"] = "6mo",
    forward_window: int = 10,
    method: Literal["combined", "mdi", "mda", "sfi", "spearman"] = "combined"
) -> str:
    """
    Calculate which technical indicators are most predictive of future returns.

    **METHODOLOGY:** Uses López de Prado's robust feature importance methodology from
    "Advances in Financial Machine Learning" Chapter 5.

    **DEFAULT (method='combined'):**
    - MDI (Mean Decrease Impurity): Fast, from Random Forest node splits
    - MDA (Mean Decrease Accuracy): Permutation importance, robust
    - SFI (Single Feature Importance): Individual feature performance
    - **Averages all three for maximum robustness**

    This is institutional-grade analysis - more reliable than simple correlation.

    Args:
        ticker: Stock symbol (e.g., "AAPL")
        period: Historical data window ("3mo", "6mo", "1y")
        forward_window: Days ahead to predict (default 10)
        method: Importance calculation method (default "combined"):
                - 'combined': MDI + MDA + SFI averaged (RECOMMENDED for real money)
                - 'mdi': Mean Decrease Impurity only (fast)
                - 'mda': Mean Decrease Accuracy only (permutation)
                - 'sfi': Single Feature Importance only
                - 'spearman': Simple correlation (fastest, for quick checks)

    Returns:
        Markdown formatted report with feature importance rankings

    Example:
        >>> # Robust analysis (recommended)
        >>> result = await calculate_feature_importance_analysis("AAPL", "6mo")
        >>>
        >>> # Fast analysis (for quick checks)
        >>> result = await calculate_feature_importance_analysis("AAPL", "6mo", method="spearman")

    References:
        López de Prado, M. (2018). Advances in Financial Machine Learning. Chapter 5.
    """
    import pandas as pd
    import numpy as np
    from .ml_core import calculate_feature_importance

    try:
        # Get historical data (Questrade primary, Yahoo fallback, cached)
        hist = _get_ohlcv_cached(ticker, period=period)

        if hist is None or hist.empty or len(hist) < forward_window + 20:
            return f"Error: Insufficient data for {ticker} with period {period}"

        # Calculate future returns (target variable)
        hist['Forward_Return'] = hist['Close'].pct_change(forward_window).shift(-forward_window)

        # Calculate technical indicators
        close = hist['Close']
        high = hist['High']
        low = hist['Low']
        volume = hist['Volume']

        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs))

        # MACD
        ema_12 = close.ewm(span=12).mean()
        ema_26 = close.ewm(span=26).mean()
        hist['MACD'] = ema_12 - ema_26
        hist['MACD_Signal'] = hist['MACD'].ewm(span=9).mean()
        hist['MACD_Hist'] = hist['MACD'] - hist['MACD_Signal']

        # Moving Averages
        hist['SMA_20'] = close.rolling(window=20).mean()
        hist['SMA_50'] = close.rolling(window=50).mean()
        hist['Price_vs_SMA20'] = (close - hist['SMA_20']) / hist['SMA_20']
        hist['Price_vs_SMA50'] = (close - hist['SMA_50']) / hist['SMA_50']

        # Bollinger Bands
        bb_period = 20
        bb_std = 2
        hist['BB_Middle'] = close.rolling(window=bb_period).mean()
        bb_std_val = close.rolling(window=bb_period).std()
        hist['BB_Upper'] = hist['BB_Middle'] + (bb_std_val * bb_std)
        hist['BB_Lower'] = hist['BB_Middle'] - (bb_std_val * bb_std)
        hist['BB_Position'] = (close - hist['BB_Lower']) / (hist['BB_Upper'] - hist['BB_Lower'])

        # Volume indicators (exclude current day from average)
        hist['Volume_SMA'] = volume.shift(1).rolling(window=20).mean()
        hist['Relative_Volume'] = volume / hist['Volume_SMA']

        # Volatility
        hist['ATR'] = hist[['High', 'Low', 'Close']].apply(
            lambda x: max(x['High'] - x['Low'],
                         abs(x['High'] - x['Close']),
                         abs(x['Low'] - x['Close'])),
            axis=1
        ).rolling(window=14).mean()
        hist['Volatility'] = close.pct_change().rolling(window=20).std()

        # Momentum
        hist['ROC_10'] = close.pct_change(10)
        hist['ROC_20'] = close.pct_change(20)

        # Feature list with descriptions
        feature_descriptions = {
            'RSI': 'RSI (Relative Strength Index)',
            'MACD_Hist': 'MACD Histogram',
            'Price_vs_SMA20': 'Price vs 20-day MA',
            'Price_vs_SMA50': 'Price vs 50-day MA',
            'BB_Position': 'Bollinger Band Position',
            'Relative_Volume': 'Relative Volume',
            'Volatility': 'Price Volatility (20-day)',
            'ROC_10': '10-day Rate of Change',
            'ROC_20': '20-day Rate of Change'
        }

        # Prepare features DataFrame (only existing columns)
        feature_cols = [f for f in feature_descriptions.keys() if f in hist.columns]
        features_df = hist[feature_cols].copy()
        target = hist['Forward_Return'].copy()

        # Remove rows with NaN in features or target
        valid_mask = ~(features_df.isna().any(axis=1) | target.isna())
        features_clean = features_df[valid_mask]
        target_clean = target[valid_mask]

        if len(features_clean) < 30:
            return f"Error: Insufficient valid data for {ticker} (need 30+ samples, got {len(features_clean)})"

        # Calculate feature importance using López de Prado methodology
        importances = calculate_feature_importance(
            features_clean,
            target_clean,
            method=method  # 'combined', 'mdi', 'mda', 'sfi', or 'spearman'
        )

        # Build results dictionary with descriptions
        correlations = {}
        for feature, importance in importances.items():
            correlations[feature] = {
                'description': feature_descriptions.get(feature, feature),
                'importance': importance,
                'sample_size': len(features_clean)
            }

        # Sort by importance (already normalized 0-1)
        sorted_features = sorted(
            correlations.items(),
            key=lambda x: x[1]['importance'],
            reverse=True
        )

        # Generate report
        method_name = {
            'combined': 'Combined (MDI + MDA + SFI)',
            'mdi': 'MDI (Mean Decrease Impurity)',
            'mda': 'MDA (Mean Decrease Accuracy)',
            'sfi': 'SFI (Single Feature Importance)',
            'spearman': 'Spearman Correlation'
        }.get(method, method)

        report = f"""# Feature Importance Analysis: {ticker}

**Methodology:** {method_name}
**Analysis Period:** {period}
**Forward Window:** {forward_window} days
**Valid Samples:** {len(features_clean)} (after removing NaN)

## Feature Rankings

Features ranked by predictive importance for {forward_window}-day forward returns:

*Importance scores are normalized (sum to 1.0) - higher = more predictive*

"""

        for rank, (feature, stats) in enumerate(sorted_features, 1):
            importance = stats['importance']

            # Interpret strength (importance is 0-1, normalized across all features)
            # With 9 features, average would be ~0.11
            avg_importance = 1.0 / len(sorted_features)
            relative = importance / avg_importance if avg_importance > 0 else 0

            if relative > 1.5:
                strength = "CRITICAL"
            elif relative > 1.0:
                strength = "HIGH"
            elif relative > 0.5:
                strength = "MODERATE"
            else:
                strength = "LOW"

            report += f"""### {rank}. {stats['description']}
- **Importance Score:** {importance:.4f} ({importance*100:.2f}%)
- **Strength:** {strength} ({relative:.1f}x average)
- **Interpretation:** {"Critical predictor - prioritize in analysis" if relative > 1.5 else "Important predictor" if relative > 1.0 else "Moderate predictor" if relative > 0.5 else "Minor predictor"}

"""

        # Summary insights
        report += f"""## Summary Insights

### Top Predictive Features:
"""

        for rank, (feature, stats) in enumerate(sorted_features[:3], 1):
            report += f"{rank}. **{stats['description']}** - {stats['importance']:.4f} importance ({stats['importance']*100:.1f}%)\n"

        # Concentration analysis
        top3_importance = sum(stats['importance'] for _, stats in sorted_features[:3])
        total_count = len(correlations)

        # Determine predictability based on importance concentration
        if top3_importance > 0.6:
            predictability = "HIGH"
            pred_desc = "Top 3 features dominate (>60%) - clear strong predictors"
        elif top3_importance > 0.45:
            predictability = "MODERATE"
            pred_desc = "Top 3 features moderately important (45-60%)"
        else:
            predictability = "LOW"
            pred_desc = "Importance widely distributed - no clear dominant predictors"

        report += f"""
### Statistical Summary:
- **Total Features:** {total_count}
- **Top 3 Concentration:** {top3_importance:.1%} of importance
- **Predictability:** {predictability} - {pred_desc}
- **Methodology:** {method_name}

### Recommendations:
"""

        if predictability == "HIGH":
            report += f"- ✅ **Strong predictive power found** - focus on top {min(3, total_count)} features\n"
            report += "- ML models likely to perform well with these features\n"
            report += "- Top features account for majority of predictive power\n"
        elif predictability == "MODERATE":
            report += "- ⚠️ **Moderate predictive power** - use top 3-5 features together\n"
            report += "- Combining multiple indicators recommended\n"
            report += "- Consider feature interactions (not just individual features)\n"
        else:
            report += "- ⚠️ **Limited predictive power in individual features**\n"
            report += "- May need non-linear models to capture relationships\n"
            report += "- Consider regime-based or ensemble approaches\n"

        # Methodology note
        if method == 'combined':
            report += """
**Methodology Note:** This analysis uses López de Prado's robust combined approach (MDI + MDA + SFI averaged).
More reliable than simple correlation for real money trading.
"""
        elif method == 'spearman':
            report += """
**Methodology Note:** Fast Spearman correlation used. For production trading, consider using method='combined'
for more robust results (MDI + MDA + SFI).
"""
        else:
            report += """
**Note:** Feature importance quantifies predictive power, not causation. Use top features together
for more robust predictions. Results may vary across different market regimes.
"""

        return report

    except Exception as e:
        return f"Error analyzing feature importance for {ticker}: {str(e)}"


# ============================================================================
# TradingView Scanner Tools
# ============================================================================

# Import the scanner analyzer for deep analysis
try:
    from investor_agent.scanner_analyzer import ScannerAnalyzer, format_analysis_report, AlBrooksAnalyzer
    ANALYZER_AVAILABLE = True
except ImportError:
    ANALYZER_AVAILABLE = False


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


# === PROPOSAL 6: Market Regime Detection ===
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

        # Set Date as index
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date')

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


@mcp.tool()
def scan_market_opportunities(
    market: Literal["america", "canada", "both"] = "both",
    min_price: float = 2.0,
    min_market_cap: int = 1_000_000_000,
    top_n: int = 5,
    include_deep_analysis: bool = True,
    require_4_gates: bool = True,
    batch_size: int = 50,
    max_scan: int = 500
) -> dict[str, Any]:
    """
    Scan US and Canadian markets for HIGH-QUALITY trading opportunities.

    NEW: Scans in batches of 200 stocks and runs FULL 4-gate validation
    on each candidate. Only returns stocks that pass ALL 4 gates.

    4-Gate Validation System:
        GATE 1 (CATALYST): Earnings proximity, insider buying, analyst upgrades
        GATE 2 (FRESHNESS): CVD alignment, exhaustion < 50
        GATE 3 (BROOKS): Probability >= 55%, no HIGH trap risk, direction aligned
        GATE 4 (QUALITY): Quality score >= 50

    Scan Process:
        1. Fetch 200 stocks per batch from TradingView
        2. Run generate_trading_signal() on each for FULL 4-gate validation
        3. Keep only stocks passing 4/4 gates
        4. Continue until we have 5 LONG + 5 SHORT or hit 1000 scanned
        5. Rank by confidence score

    Args:
        market: Market to scan - "america", "canada", or "both"
        min_price: Minimum stock price (default: $2)
        min_market_cap: Minimum market cap (default: $1B)
        top_n: Number of candidates per direction (default: 5)
        include_deep_analysis: Run full analysis pipeline (default: True)
        require_4_gates: Only return 4/4 gate passers (default: True)
        batch_size: Stocks to scan per batch (default: 200)
        max_scan: Maximum stocks to scan before giving up (default: 1000)

    Returns:
        Dictionary with:
        - scan_time: Timestamp of scan
        - long_candidates: Top N LONG with 4/4 gates passed
        - short_candidates: Top N SHORT with 4/4 gates passed
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
        f"{min_price}_{min_market_cap}_{top_n}_{require_4_gates}_{batch_size}".encode()
    ).hexdigest()[:8]

    cached_result = _get_scan_cache(market, filters_hash)
    if cached_result is not None:
        logger.info(f"Returning cached scan results for {market}")
        return cached_result

    # === Detect Market Regime ===
    market_regime = detect_market_regime()
    logger.info(f"📊 Market Regime: {market_regime['regime']} | SPY Vol: {market_regime['volatility']}%")

    try:
        # === Get Scanner (TradingView → Finviz fallback) ===
        scanner = None
        scanner_source = "unknown"

        try:
            scanner = get_scanner()
            scanner_source = "tradingview"
            logger.info("📡 Using TradingView scanner (primary)")
        except Exception as tv_error:
            logger.warning(f"⚠️ TradingView scanner failed: {tv_error}")
            try:
                scanner = get_fallback_scanner()
                if scanner:
                    scanner_source = "finviz"
                    logger.info("📡 Using Finviz scanner (fallback)")
                else:
                    raise ValueError("Finviz scanner not available")
            except Exception as finviz_error:
                logger.error(f"❌ Both scanners failed. TV: {tv_error}, Finviz: {finviz_error}")
                raise ValueError("No stock scanner available - all sources failed")

        et = pytz.timezone("America/New_York")
        import time
        scan_start_time = time.time()
        MAX_SCAN_SECONDS = 600  # 10 minute timeout for entire scan

        # === NEW: BATCH SCANNING WITH 4-GATE VALIDATION ===
        logger.info(f"🔍 Starting batch scan: {batch_size} stocks/batch, max {max_scan}, require 4/4 gates: {require_4_gates}")

        # Collect 4/4 gate passers
        validated_long = []
        validated_short = []
        total_scanned_long = 0
        total_scanned_short = 0
        stocks_seen = set()  # Avoid duplicates

        # Track rejections for debugging
        rejection_reasons = {"LONG": {}, "SHORT": {}}  # gate_name -> count
        scan_errors = []
        timeout_occurred = False

        # Fetch ALL candidates upfront (TradingView doesn't support pagination)
        logger.info(f"📡 Fetching all candidates from scanner (limit={max_scan})...")

        try:
            all_long_candidates = scanner.scan_long_setups(
                setup_type="all",
                market=market,
                min_price=min_price,
                min_market_cap=min_market_cap,
                limit=max_scan
            )
            logger.info(f"   Got {len(all_long_candidates)} LONG candidates from TradingView")
        except Exception as e:
            scan_errors.append(f"LONG scan error: {str(e)}")
            logger.error(f"❌ LONG scanner failed: {e}")
            all_long_candidates = []

        try:
            all_short_candidates = scanner.scan_short_setups(
                setup_type="all",
                market=market,
                min_price=min_price,
                min_market_cap=min_market_cap,
                limit=max_scan
            )
            logger.info(f"   Got {len(all_short_candidates)} SHORT candidates from TradingView")
        except Exception as e:
            scan_errors.append(f"SHORT scan error: {str(e)}")
            logger.error(f"❌ SHORT scanner failed: {e}")
            all_short_candidates = []

        # Validate LONG candidates
        logger.info(f"📊 Validating LONG candidates (have {len(all_long_candidates)} to check)...")
        for candidate in all_long_candidates:
            # Check timeout
            elapsed = time.time() - scan_start_time
            if elapsed > MAX_SCAN_SECONDS:
                logger.warning(f"⏱️ LONG scan timeout after {elapsed:.0f}s. Returning partial results.")
                timeout_occurred = True
                break

            symbol = candidate['symbol']
            if symbol in stocks_seen:
                continue
            stocks_seen.add(symbol)
            total_scanned_long += 1

            # Progress every 10 stocks
            if total_scanned_long % 10 == 0:
                logger.info(f"   Progress: {total_scanned_long}/{len(all_long_candidates)} scanned, {len(validated_long)} validated ({time.time() - scan_start_time:.0f}s)")

            try:
                # Run FULL 4-gate validation
                signal = generate_trading_signal(ticker=symbol, direction="LONG")

                gate_status = signal.get('gate_status', {})
                gates_passed = sum(1 for g in gate_status.values() if g == "PASS")

                if require_4_gates and gates_passed == 4:
                    validated_long.append({
                        'symbol': symbol,
                        'direction': 'LONG',
                        'price': candidate.get('price', signal.get('current_price')),
                        'signal': signal.get('signal'),
                        'confidence': signal.get('confidence', 0),
                        'gates_passed': gates_passed,
                        'gate_status': gate_status,
                        'trading_plan': signal.get('trading_plan'),
                        'catalyst_analysis': signal.get('catalyst_analysis'),
                        'freshness_analysis': signal.get('freshness_analysis'),
                        'brooks_analysis': signal.get('brooks_analysis'),
                        'quality_analysis': signal.get('quality_analysis'),
                        'tv_data': candidate
                    })
                    logger.info(f"✅ {symbol}: 4/4 gates PASSED | Confidence: {signal.get('confidence')}% [{len(validated_long)}/{top_n} found]")
                    if len(validated_long) >= top_n:
                        logger.info(f"🎯 Found {top_n} LONG candidates - moving to SHORT scan")
                        break

                elif not require_4_gates and gates_passed >= 3:
                    validated_long.append({
                        'symbol': symbol,
                        'direction': 'LONG',
                        'price': candidate.get('price', signal.get('current_price')),
                        'signal': signal.get('signal'),
                        'confidence': signal.get('confidence', 0),
                        'gates_passed': gates_passed,
                        'gate_status': gate_status,
                        'trading_plan': signal.get('trading_plan'),
                        'tv_data': candidate
                    })
                    if len(validated_long) >= top_n:
                        logger.info(f"🎯 Found {top_n} LONG candidates - moving to SHORT scan")
                        break

                else:
                    # Track rejection reasons
                    for gate_name, gate_val in gate_status.items():
                        if gate_val != "PASS":
                            rejection_reasons["LONG"][gate_name] = rejection_reasons["LONG"].get(gate_name, 0) + 1
                    logger.debug(f"❌ {symbol}: {gates_passed}/4 gates - {gate_status}")

            except Exception as e:
                scan_errors.append(f"{symbol}: {str(e)[:50]}")
                logger.warning(f"Validation failed for {symbol}: {e}")

        # Validate SHORT candidates (only if LONG didn't timeout)
        stocks_seen_short = set()
        if not timeout_occurred:
            logger.info(f"📊 Validating SHORT candidates (have {len(all_short_candidates)} to check)...")

        for candidate in all_short_candidates:
            # Check timeout
            elapsed = time.time() - scan_start_time
            if elapsed > MAX_SCAN_SECONDS:
                logger.warning(f"⏱️ SHORT scan timeout after {elapsed:.0f}s. Returning partial results.")
                timeout_occurred = True
                break

            if len(validated_short) >= top_n:
                break
            if total_scanned_short >= max_scan:
                break

            symbol = candidate['symbol']
            if symbol in stocks_seen_short:
                continue
            stocks_seen_short.add(symbol)
            total_scanned_short += 1

            # Progress every 10 stocks
            if total_scanned_short % 10 == 0:
                logger.info(f"   Progress: {total_scanned_short}/{len(all_short_candidates)} scanned, {len(validated_short)} validated ({time.time() - scan_start_time:.0f}s)")

            try:
                signal = generate_trading_signal(ticker=symbol, direction="SHORT")

                gate_status = signal.get('gate_status', {})
                gates_passed = sum(1 for g in gate_status.values() if g == "PASS")

                if require_4_gates and gates_passed == 4:
                    validated_short.append({
                        'symbol': symbol,
                        'direction': 'SHORT',
                        'price': candidate.get('price', signal.get('current_price')),
                        'signal': signal.get('signal'),
                        'confidence': signal.get('confidence', 0),
                        'gates_passed': gates_passed,
                        'gate_status': gate_status,
                        'trading_plan': signal.get('trading_plan'),
                        'catalyst_analysis': signal.get('catalyst_analysis'),
                        'freshness_analysis': signal.get('freshness_analysis'),
                        'brooks_analysis': signal.get('brooks_analysis'),
                        'quality_analysis': signal.get('quality_analysis'),
                        'tv_data': candidate
                    })
                    logger.info(f"✅ {symbol}: 4/4 gates PASSED | Confidence: {signal.get('confidence')}% [{len(validated_short)}/{top_n} found]")
                    if len(validated_short) >= top_n:
                        logger.info(f"🎯 Found {top_n} SHORT candidates - scan complete!")
                        break

                elif not require_4_gates and gates_passed >= 3:
                    validated_short.append({
                        'symbol': symbol,
                        'direction': 'SHORT',
                        'price': candidate.get('price', signal.get('current_price')),
                        'signal': signal.get('signal'),
                        'confidence': signal.get('confidence', 0),
                        'gates_passed': gates_passed,
                        'gate_status': gate_status,
                        'trading_plan': signal.get('trading_plan'),
                        'tv_data': candidate
                    })
                    if len(validated_short) >= top_n:
                        logger.info(f"🎯 Found {top_n} SHORT candidates - scan complete!")
                        break

                else:
                    # Track rejection reasons
                    for gate_name, gate_val in gate_status.items():
                        if gate_val != "PASS":
                            rejection_reasons["SHORT"][gate_name] = rejection_reasons["SHORT"].get(gate_name, 0) + 1
                    logger.debug(f"❌ {symbol}: {gates_passed}/4 gates - {gate_status}")

            except Exception as e:
                scan_errors.append(f"{symbol}: {str(e)[:50]}")
                logger.warning(f"Validation failed for {symbol}: {e}")

        # Sort by confidence score (descending)
        validated_long.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        validated_short.sort(key=lambda x: x.get('confidence', 0), reverse=True)

        # Take top N
        final_long = validated_long[:top_n]
        final_short = validated_short[:top_n]

        # Add ranks
        for i, a in enumerate(final_long):
            a['rank'] = i + 1
        for i, a in enumerate(final_short):
            a['rank'] = i + 1

        logger.info(f"📊 Scan complete: {len(final_long)} LONG, {len(final_short)} SHORT with 4/4 gates")

        # Generate text report for 4/4 gate validated results
        report_lines = [
            "=" * 65,
            f"    HIGH-QUALITY SCAN - {datetime.now(et).strftime('%Y-%m-%d %H:%M %Z')}",
            "=" * 65,
            f"Markets: {market.upper()} | Filters: Price>${min_price}, MCap>${min_market_cap:,}",
            f"Batch Size: {batch_size} | Max Scan: {max_scan} | Require 4/4 Gates: {require_4_gates}",
            "",
            f"📊 SCAN STATISTICS:",
            f"   LONG:  Scanned {total_scanned_long} → Found {len(final_long)} with 4/4 gates ({len(final_long)/max(total_scanned_long,1)*100:.1f}% pass rate)",
            f"   SHORT: Scanned {total_scanned_short} → Found {len(final_short)} with 4/4 gates ({len(final_short)/max(total_scanned_short,1)*100:.1f}% pass rate)",
            "",
            "✅ ALL candidates below have passed FULL 4-gate validation:",
            "   Gate 1: CATALYST (earnings/insider/upgrades)",
            "   Gate 2: FRESHNESS (CVD aligned, exhaustion < 50)",
            "   Gate 3: BROOKS (probability >= 55%, no HIGH trap)",
            "   Gate 4: QUALITY (score >= 50)",
            "",
            "=" * 65,
            "                TOP LONG CANDIDATES (4/4 GATES)",
            "=" * 65,
        ]

        for a in final_long:
            brooks = a.get('brooks_analysis', {})
            trading_plan = a.get('trading_plan', {})
            report_lines.extend([
                "",
                f"#{a.get('rank')} {a['symbol']} - ${a.get('price', 0):.2f}",
                f"   Signal: {a.get('signal')} | Confidence: {a.get('confidence')}%",
                f"   Gates: {a.get('gates_passed')}/4 ✅",
                f"   Brooks: {brooks.get('pattern', 'N/A')} | Prob: {brooks.get('probability', 0)}% | Trap: {brooks.get('trap_risk', 'N/A')}",
                f"   Entry: ${trading_plan.get('entry_price', 0):.2f} | Stop: ${trading_plan.get('stop_loss', {}).get('price', 0):.2f} | Target: ${trading_plan.get('target_1', {}).get('price', 0):.2f}",
            ])

        if not final_long:
            report_lines.append("\n   ❌ No LONG candidates passed 4/4 gates in this scan.")

        report_lines.extend([
            "",
            "=" * 65,
            "                TOP SHORT CANDIDATES (4/4 GATES)",
            "=" * 65,
        ])

        for a in final_short:
            brooks = a.get('brooks_analysis', {})
            trading_plan = a.get('trading_plan', {})
            report_lines.extend([
                "",
                f"#{a.get('rank')} {a['symbol']} - ${a.get('price', 0):.2f}",
                f"   Signal: {a.get('signal')} | Confidence: {a.get('confidence')}%",
                f"   Gates: {a.get('gates_passed')}/4 ✅",
                f"   Brooks: {brooks.get('pattern', 'N/A')} | Prob: {brooks.get('probability', 0)}% | Trap: {brooks.get('trap_risk', 'N/A')}",
                f"   Entry: ${trading_plan.get('entry_price', 0):.2f} | Stop: ${trading_plan.get('stop_loss', {}).get('price', 0):.2f} | Target: ${trading_plan.get('target_1', {}).get('price', 0):.2f}",
            ])

        if not final_short:
            report_lines.append("\n   ❌ No SHORT candidates passed 4/4 gates in this scan.")

        # Add rejection stats to report
        total_elapsed = time.time() - scan_start_time
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

        # Convert numpy types to native Python types for JSON serialization
        result = convert_numpy_types({
            "scan_time": datetime.now(et).strftime("%Y-%m-%d %H:%M:%S %Z"),
            "market_regime": market_regime,
            "scanner_source": scanner_source,
            "filters": {
                "market": market,
                "min_price": min_price,
                "min_market_cap": f"${min_market_cap:,}",
                "batch_size": batch_size,
                "max_scan": max_scan,
                "require_4_gates": require_4_gates
            },
            "stats": {
                "long_scanned": total_scanned_long,
                "long_passed": len(final_long),
                "long_pass_rate": f"{len(final_long)/max(total_scanned_long,1)*100:.1f}%",
                "short_scanned": total_scanned_short,
                "short_passed": len(final_short),
                "short_pass_rate": f"{len(final_short)/max(total_scanned_short,1)*100:.1f}%",
                "elapsed_seconds": round(total_elapsed, 1),
                "timeout_occurred": timeout_occurred,
                "rejection_reasons": rejection_reasons,
                "errors_count": len(scan_errors)
            },
            "long_candidates": final_long,
            "short_candidates": final_short,
            "errors": scan_errors[:10] if scan_errors else [],  # Include first 10 errors
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


# ============================================================
# MUTUAL FUND & ETF ANALYSIS TOOLS
# ============================================================

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
    from .questrade import get_questrade_client

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
                    options = analyze_options_mcmillan(ticker, direction="LONG")
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

                    result["stocks"].append(position_info)

        return result

    except Exception as e:
        logger.error(f"Error in get_portfolio_summary: {e}")
        raise ValueError(f"Portfolio summary failed: {str(e)}")


# =============================================================================
# NEW SCANNER ENHANCEMENT TOOLS (December 2025)
# =============================================================================

@mcp.tool()
def detect_catalyst_strength(ticker: str) -> dict[str, Any]:
    """
    Aggregate ALL catalyst signals into one actionable strength assessment.

    Combines multiple data sources:
    - Earnings Calendar: Days to earnings, beat rate (25 pts max)
    - Insider Trades: Buy clusters in 30 days (25 pts max)
    - Options IV Rank: 30-60% = active interest (20 pts max)
    - Institutional: Recent 13F accumulation (15 pts max)
    - News/Upgrades: Recent analyst upgrades (15 pts max)
    - Unusual Options Activity: Smart money detection (20 pts max)
    - CNN Fear/Greed Index: Market sentiment context (10 pts max)

    Returns:
    - catalyst_strength: STRONG / MODERATE / WEAK / NONE
    - catalysts_detected: List of active catalysts
    - primary_catalyst: Most significant driver
    - catalyst_score: 0-100
    - trade_allowed: bool (NONE = False)
    """
    from datetime import datetime, timedelta
    import pandas as pd

    ticker = validate_ticker(ticker)

    result = {
        "ticker": ticker,
        "catalyst_strength": "NONE",
        "catalyst_score": 0,
        "catalysts_detected": [],
        "primary_catalyst": None,
        "trade_allowed": False,
        "details": {}
    }

    score = 0
    catalysts = []

    # 1. EARNINGS ANALYSIS (25 pts max)
    try:
        t = yf.Ticker(ticker)
        calendar = t.calendar
        earnings_date = None
        all_earnings_dates = []

        if calendar is not None:
            if isinstance(calendar, dict):
                earnings_date = calendar.get('Earnings Date')
                # Collect all dates if it's a list
                if isinstance(earnings_date, list):
                    all_earnings_dates = earnings_date
                    earnings_date = earnings_date[0] if len(earnings_date) > 0 else None
            elif isinstance(calendar, pd.DataFrame) and not calendar.empty:
                if 'Earnings Date' in calendar.columns:
                    all_earnings_dates = calendar['Earnings Date'].tolist()
                    earnings_date = calendar['Earnings Date'].iloc[0]

        # Convert to date object
        def to_date(d):
            if d is None:
                return None
            if hasattr(d, 'date'):
                return d.date()
            elif isinstance(d, str):
                try:
                    return datetime.strptime(d[:10], '%Y-%m-%d').date()
                except:
                    return None
            return d

        earnings_date = to_date(earnings_date)
        today = datetime.now().date()

        # If the primary earnings date is too far in the past (>10 days), try to find next upcoming
        if earnings_date and (earnings_date - today).days < -10:
            # Look for future dates in the list
            future_dates = []
            for d in all_earnings_dates:
                d_converted = to_date(d)
                if d_converted and d_converted > today:
                    future_dates.append(d_converted)

            if future_dates:
                # Use the nearest future earnings date
                earnings_date = min(future_dates)
            else:
                # No future dates found, mark as past and unknown next
                result["details"]["earnings"] = {
                    "last_earnings": str(to_date(all_earnings_dates[0])) if all_earnings_dates else "unknown",
                    "next_earnings": "unknown",
                    "note": "No upcoming earnings date available"
                }
                earnings_date = None

        if earnings_date:
            days_to_earnings = (earnings_date - today).days

            result["details"]["earnings"] = {
                "date": str(earnings_date),
                "days_away": days_to_earnings
            }

            # Pre-earnings (5-30 days) = STRONG catalyst
            if 5 <= days_to_earnings <= 30:
                score += 25
                catalysts.append(f"Pre-Earnings in {days_to_earnings} days")
            # Post-earnings (1-10 days ago) = MODERATE catalyst
            elif -10 <= days_to_earnings < 0:
                score += 20
                catalysts.append(f"Post-Earnings {abs(days_to_earnings)} days ago")
            # Earnings further out (30-45 days)
            elif 30 < days_to_earnings <= 45:
                score += 10
                catalysts.append(f"Earnings in {days_to_earnings} days")

        # Check earnings beat rate
        try:
            earnings_hist = t.earnings_history
            if earnings_hist is not None and not earnings_hist.empty:
                if 'Surprise(%)' in earnings_hist.columns:
                    beats = (earnings_hist['Surprise(%)'] > 0).sum()
                    total = len(earnings_hist)
                    beat_rate = beats / total if total > 0 else 0
                    result["details"]["earnings"]["beat_rate"] = round(beat_rate * 100, 1)

                    if beat_rate >= 0.7:
                        score += 5  # Bonus for consistent beater
                        catalysts.append(f"Earnings Beat Rate: {round(beat_rate*100)}%")
        except:
            pass

    except Exception as e:
        result["details"]["earnings_error"] = str(e)

    # 2. INSIDER TRADES (25 pts max)
    try:
        insider_data = yf_call(ticker, "get_insider_transactions")

        if insider_data is not None and isinstance(insider_data, pd.DataFrame) and not insider_data.empty:
            # Count buys in last 30 days
            thirty_days_ago = datetime.now() - timedelta(days=30)

            recent_trades = insider_data.copy()
            if 'Start Date' in recent_trades.columns:
                recent_trades['date'] = pd.to_datetime(recent_trades['Start Date'], errors='coerce')
                recent_trades = recent_trades[recent_trades['date'] >= thirty_days_ago]

            # Column is named 'Text' in yfinance, not 'Transaction'
            trans_col = 'Text' if 'Text' in recent_trades.columns else 'Transaction'
            if trans_col in recent_trades.columns:
                buys = recent_trades[recent_trades[trans_col].str.contains('Purchase|Buy', case=False, na=False)]
                sells = recent_trades[recent_trades[trans_col].str.contains('Sale|Sell', case=False, na=False)]

                buy_count = len(buys)
                sell_count = len(sells)

                result["details"]["insider"] = {
                    "buys_30d": buy_count,
                    "sells_30d": sell_count
                }

                # 3+ buys = STRONG (25 pts)
                if buy_count >= 3:
                    score += 25
                    catalysts.append(f"Insider Cluster: {buy_count} buys in 30 days")
                # 2 buys = MODERATE (15 pts)
                elif buy_count >= 2:
                    score += 15
                    catalysts.append(f"Insider Buying: {buy_count} buys in 30 days")
                # 1 buy = WEAK (8 pts)
                elif buy_count >= 1:
                    score += 8
                    catalysts.append(f"Insider Buy detected")

                # Check for C-suite buys (bonus)
                if not buys.empty and 'Insider' in buys.columns:
                    c_suite = buys[buys['Insider'].str.contains('CEO|CFO|COO|President|Chairman', case=False, na=False)]
                    if len(c_suite) > 0:
                        score += 5
                        catalysts.append("C-Suite buying detected")

    except Exception as e:
        result["details"]["insider_error"] = str(e)

    # 3. OPTIONS IV RANK (20 pts max)
    try:
        # Quick IV rank check using yfinance options
        t = yf.Ticker(ticker)
        if t.options and len(t.options) > 0:
            nearest_exp = t.options[0]
            chain = t.option_chain(nearest_exp)

            if chain.calls is not None and not chain.calls.empty:
                atm_calls = chain.calls[
                    (chain.calls['strike'] >= t.info.get('currentPrice', 0) * 0.95) &
                    (chain.calls['strike'] <= t.info.get('currentPrice', 0) * 1.05)
                ]

                if not atm_calls.empty and 'impliedVolatility' in atm_calls.columns:
                    current_iv = atm_calls['impliedVolatility'].mean()
                    iv_rank = min(100, current_iv * 100)  # Simplified IV rank

                    result["details"]["options"] = {
                        "iv_rank": round(iv_rank, 1),
                        "current_iv": round(current_iv * 100, 1)
                    }

                    # IV Rank 40-60% = sweet spot (20 pts)
                    if 40 <= iv_rank <= 60:
                        score += 20
                        catalysts.append(f"IV Rank {round(iv_rank)}% (Options active)")
                    # IV Rank 30-40% = moderate (10 pts)
                    elif 30 <= iv_rank < 40:
                        score += 10
                        catalysts.append(f"IV Rank {round(iv_rank)}%")
                    # IV Rank 60-80% = high expectation (15 pts)
                    elif 60 < iv_rank <= 80:
                        score += 15
                        catalysts.append(f"High IV Rank {round(iv_rank)}%")

    except Exception as e:
        result["details"]["options_error"] = str(e)

    # 4. INSTITUTIONAL HOLDERS (15 pts max)
    try:
        inst_holders = yf_call(ticker, "get_institutional_holders")

        if inst_holders is not None and isinstance(inst_holders, pd.DataFrame) and not inst_holders.empty:
            # Check if major institutions are present
            major_holders = len(inst_holders)
            result["details"]["institutional"] = {
                "holder_count": major_holders
            }

            if major_holders >= 10:
                score += 15
                catalysts.append(f"{major_holders} institutional holders")
            elif major_holders >= 5:
                score += 8
                catalysts.append(f"{major_holders} institutional holders")

    except Exception as e:
        result["details"]["institutional_error"] = str(e)

    # 5. NEWS & UPGRADES (15 pts max)
    try:
        t = yf.Ticker(ticker)

        # Check for recent upgrades
        upgrades = t.upgrades_downgrades
        if upgrades is not None and not upgrades.empty:
            # Recent upgrades (last 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)

            if hasattr(upgrades.index, 'to_pydatetime'):
                recent_upgrades = upgrades[upgrades.index >= thirty_days_ago]
            else:
                recent_upgrades = upgrades.head(5)  # Fallback to most recent

            if not recent_upgrades.empty:
                if 'ToGrade' in recent_upgrades.columns:
                    bullish = recent_upgrades[recent_upgrades['ToGrade'].str.contains(
                        'Buy|Outperform|Overweight|Strong Buy', case=False, na=False
                    )]

                    if len(bullish) > 0:
                        score += 15
                        catalysts.append(f"{len(bullish)} analyst upgrades")
                        result["details"]["upgrades"] = {
                            "bullish_count": len(bullish),
                            "recent": recent_upgrades.head(3).to_dict('records') if len(recent_upgrades) > 0 else []
                        }

        # Check for recent news
        news = t.news
        if news and len(news) > 0:
            result["details"]["news_count"] = len(news)

    except Exception as e:
        result["details"]["news_error"] = str(e)

    # 6. UNUSUAL OPTIONS ACTIVITY (20 pts max) - Smart Money Detection
    try:
        options_activity = detect_unusual_options_activity(ticker)

        if options_activity.get("unusual_activity"):
            activity_type = options_activity.get("activity_type", "NEUTRAL")
            signals = options_activity.get("signals", [])

            result["details"]["unusual_options"] = {
                "detected": True,
                "type": activity_type,
                "signal_count": len(signals),
                "largest_bet": options_activity.get("largest_bet"),
                "implied_move": options_activity.get("implied_move")
            }

            # BULLISH unusual activity = STRONG catalyst
            if activity_type == "BULLISH":
                score += 20
                catalysts.append(f"Unusual Options: BULLISH ({len(signals)} signals)")
            # BEARISH unusual activity = useful for shorts
            elif activity_type == "BEARISH":
                score += 10  # Still a catalyst, but for SHORT direction
                catalysts.append(f"Unusual Options: BEARISH ({len(signals)} signals)")
            # MIXED unusual activity = something brewing
            elif activity_type == "MIXED" and len(signals) >= 2:
                score += 8
                catalysts.append(f"Unusual Options: MIXED ({len(signals)} signals)")
        else:
            result["details"]["unusual_options"] = {"detected": False}

    except Exception as e:
        result["details"]["unusual_options_error"] = str(e)

    # 7. MARKET SENTIMENT - CNN Fear/Greed Index (10 pts max)
    try:
        # Sync fetch of CNN Fear/Greed
        import httpx
        CNN_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

        with httpx.Client(timeout=10.0) as client:
            response = client.get(CNN_FEAR_GREED_URL, headers=BROWSER_HEADERS)
            if response.status_code == 200:
                fg_data = response.json()
                fg_score = fg_data.get("fear_and_greed", {}).get("score", 50)
                fg_rating = fg_data.get("fear_and_greed", {}).get("rating", "Neutral")

                result["details"]["market_sentiment"] = {
                    "fear_greed_score": round(fg_score, 1),
                    "rating": fg_rating
                }

                # Extreme Fear (<25) = LONG catalyst boost (buy the fear)
                if fg_score < 25:
                    score += 10
                    catalysts.append(f"Extreme Fear ({round(fg_score)}) - Contrarian LONG")
                # Fear (25-45) = Moderate LONG boost
                elif fg_score < 45:
                    score += 5
                    catalysts.append(f"Fear ({round(fg_score)}) - LONG opportunity")
                # Extreme Greed (>75) = SHORT catalyst or caution
                elif fg_score > 75:
                    score += 5  # Catalyst for SHORT trades
                    catalysts.append(f"Extreme Greed ({round(fg_score)}) - SHORT catalyst")
                # Greed (55-75) = Slight caution
                elif fg_score > 55:
                    # No points, just informational
                    result["details"]["market_sentiment"]["note"] = "Elevated greed - be cautious"

    except Exception as e:
        result["details"]["market_sentiment_error"] = str(e)

    # CALCULATE FINAL STRENGTH
    result["catalyst_score"] = min(100, score)

    if score >= 60:
        result["catalyst_strength"] = "STRONG"
        result["trade_allowed"] = True
    elif score >= 35:
        result["catalyst_strength"] = "MODERATE"
        result["trade_allowed"] = True
    elif score >= 15:
        result["catalyst_strength"] = "WEAK"
        result["trade_allowed"] = False  # Weak catalyst = no trade
    else:
        result["catalyst_strength"] = "NONE"
        result["trade_allowed"] = False

    result["catalysts_detected"] = catalysts
    result["primary_catalyst"] = catalysts[0] if catalysts else None

    return result


@mcp.tool()
def detect_insider_cluster(ticker: str, days: int = 60) -> dict[str, Any]:
    """
    Detect clustered insider buying patterns - stronger signal than single buy.

    Returns:
    - cluster_detected: bool
    - cluster_type: BUYING / SELLING / MIXED
    - cluster_strength: STRONG (3+) / MODERATE (2) / WEAK (1) / NONE
    - insiders: List of insider transactions
    - total_value: Sum of insider transactions
    - notable: CEO/CFO buys flagged specially
    """
    from datetime import datetime, timedelta

    ticker = validate_ticker(ticker)

    result = {
        "ticker": ticker,
        "cluster_detected": False,
        "cluster_type": "NONE",
        "cluster_strength": "NONE",
        "insiders": [],
        "total_buy_value": 0,
        "total_sell_value": 0,
        "notable_trades": [],
        "days_analyzed": days
    }

    try:
        insider_data = yf_call(ticker, "get_insider_transactions")

        if insider_data is None or (isinstance(insider_data, pd.DataFrame) and insider_data.empty):
            return result

        df = insider_data.copy()

        # Parse dates
        cutoff_date = datetime.now() - timedelta(days=days)
        if 'Start Date' in df.columns:
            df['date'] = pd.to_datetime(df['Start Date'], errors='coerce')
            df = df[df['date'] >= cutoff_date]

        if df.empty:
            return result

        # Categorize transactions
        # Column is named 'Text' in yfinance, not 'Transaction'
        buys = []
        sells = []

        for _, row in df.iterrows():
            # Try 'Text' first (yfinance column name), then 'Transaction'
            transaction = row.get('Text', row.get('Transaction', ''))
            insider = row.get('Insider', '')
            shares = row.get('Shares', 0)
            value = row.get('Value', 0)

            trade_info = {
                "insider": insider,
                "transaction": transaction,
                "shares": shares,
                "value": value,
                "date": str(row.get('date', ''))[:10]
            }

            if 'Purchase' in str(transaction) or 'Buy' in str(transaction):
                buys.append(trade_info)

                # Flag C-suite
                if any(title in str(insider).upper() for title in ['CEO', 'CFO', 'COO', 'PRESIDENT', 'CHAIRMAN']):
                    trade_info["notable"] = True
                    result["notable_trades"].append(trade_info)

            elif 'Sale' in str(transaction) or 'Sell' in str(transaction):
                sells.append(trade_info)

        # Calculate totals
        result["total_buy_value"] = sum(b.get('value', 0) or 0 for b in buys)
        result["total_sell_value"] = sum(s.get('value', 0) or 0 for s in sells)
        result["insiders"] = buys + sells

        # Determine cluster type and strength
        buy_count = len(buys)
        sell_count = len(sells)

        if buy_count >= 3:
            result["cluster_detected"] = True
            result["cluster_type"] = "BUYING"
            result["cluster_strength"] = "STRONG"
        elif buy_count >= 2:
            result["cluster_detected"] = True
            result["cluster_type"] = "BUYING"
            result["cluster_strength"] = "MODERATE"
        elif buy_count >= 1:
            result["cluster_detected"] = False
            result["cluster_type"] = "BUYING"
            result["cluster_strength"] = "WEAK"
        elif sell_count >= 3:
            result["cluster_detected"] = True
            result["cluster_type"] = "SELLING"
            result["cluster_strength"] = "STRONG"
        elif sell_count >= 2:
            result["cluster_detected"] = True
            result["cluster_type"] = "SELLING"
            result["cluster_strength"] = "MODERATE"

        # Mixed if both significant
        if buy_count >= 2 and sell_count >= 2:
            result["cluster_type"] = "MIXED"

    except Exception as e:
        result["error"] = str(e)

    return result


@mcp.tool()
def detect_unusual_options_activity(ticker: str) -> dict[str, Any]:
    """
    Detect unusual options activity signaling smart money.

    Detection Criteria:
    - Volume/OI > 2x = Unusual interest
    - Large premium concentrations
    - Near-term options focus (2-4 weeks)

    Returns:
    - unusual_activity: bool
    - activity_type: BULLISH / BEARISH / MIXED
    - signals: List of unusual activity detected
    - largest_bet: Description of biggest position
    - implied_move: Expected move from options pricing
    """
    from datetime import datetime, timedelta

    ticker = validate_ticker(ticker)

    result = {
        "ticker": ticker,
        "unusual_activity": False,
        "activity_type": "NEUTRAL",
        "signals": [],
        "largest_bet": None,
        "implied_move": None,
        "call_volume": 0,
        "put_volume": 0,
        "put_call_ratio": None
    }

    try:
        t = yf.Ticker(ticker)
        current_price = t.info.get('currentPrice') or t.info.get('regularMarketPrice', 0)

        if not t.options or len(t.options) == 0:
            result["error"] = "No options available"
            return result

        total_call_vol = 0
        total_put_vol = 0
        total_call_oi = 0
        total_put_oi = 0
        unusual_signals = []
        largest_premium = 0
        largest_bet_info = None

        # Analyze first 2 expirations (near-term focus)
        for exp in t.options[:2]:
            try:
                chain = t.option_chain(exp)

                # Analyze calls
                if chain.calls is not None and not chain.calls.empty:
                    calls = chain.calls

                    for _, row in calls.iterrows():
                        # Handle NaN values properly (NaN or 0 = NaN, not 0)
                        vol = row.get('volume', 0)
                        vol = 0 if pd.isna(vol) else int(vol)
                        oi = row.get('openInterest', 0)
                        oi = 0 if pd.isna(oi) else int(oi)
                        strike = row.get('strike', 0)
                        last_price = row.get('lastPrice', 0)
                        last_price = 0 if pd.isna(last_price) else float(last_price)

                        total_call_vol += vol
                        total_call_oi += oi

                        # Unusual: Volume > 2x OI
                        if oi > 0 and vol > 2 * oi:
                            premium = vol * last_price * 100
                            if premium > 50000:  # > $50k premium
                                unusual_signals.append({
                                    "type": "CALL",
                                    "strike": strike,
                                    "expiry": exp,
                                    "volume": vol,
                                    "oi": oi,
                                    "vol_oi_ratio": round(vol/oi, 1),
                                    "premium": premium
                                })

                                if premium > largest_premium:
                                    largest_premium = premium
                                    largest_bet_info = {
                                        "type": "CALL",
                                        "strike": strike,
                                        "expiry": exp,
                                        "premium": f"${premium:,.0f}"
                                    }

                # Analyze puts
                if chain.puts is not None and not chain.puts.empty:
                    puts = chain.puts

                    for _, row in puts.iterrows():
                        # Handle NaN values properly (NaN or 0 = NaN, not 0)
                        vol = row.get('volume', 0)
                        vol = 0 if pd.isna(vol) else int(vol)
                        oi = row.get('openInterest', 0)
                        oi = 0 if pd.isna(oi) else int(oi)
                        strike = row.get('strike', 0)
                        last_price = row.get('lastPrice', 0)
                        last_price = 0 if pd.isna(last_price) else float(last_price)

                        total_put_vol += vol
                        total_put_oi += oi

                        # Unusual: Volume > 2x OI
                        if oi > 0 and vol > 2 * oi:
                            premium = vol * last_price * 100
                            if premium > 50000:  # > $50k premium
                                unusual_signals.append({
                                    "type": "PUT",
                                    "strike": strike,
                                    "expiry": exp,
                                    "volume": vol,
                                    "oi": oi,
                                    "vol_oi_ratio": round(vol/oi, 1),
                                    "premium": premium
                                })

                                if premium > largest_premium:
                                    largest_premium = premium
                                    largest_bet_info = {
                                        "type": "PUT",
                                        "strike": strike,
                                        "expiry": exp,
                                        "premium": f"${premium:,.0f}"
                                    }

            except Exception:
                continue

        result["call_volume"] = total_call_vol
        result["put_volume"] = total_put_vol
        result["signals"] = unusual_signals[:10]  # Top 10 signals
        result["largest_bet"] = largest_bet_info

        # Put/Call ratio
        if total_call_vol > 0:
            pc_ratio = total_put_vol / total_call_vol
            result["put_call_ratio"] = round(pc_ratio, 2)

        # Determine activity type
        call_signals = len([s for s in unusual_signals if s["type"] == "CALL"])
        put_signals = len([s for s in unusual_signals if s["type"] == "PUT"])

        if len(unusual_signals) > 0:
            result["unusual_activity"] = True

            if call_signals > put_signals * 1.5:
                result["activity_type"] = "BULLISH"
            elif put_signals > call_signals * 1.5:
                result["activity_type"] = "BEARISH"
            else:
                result["activity_type"] = "MIXED"

        # Implied move from ATM straddle
        try:
            if t.options and len(t.options) > 0:
                chain = t.option_chain(t.options[0])
                atm_strike = min(chain.calls['strike'], key=lambda x: abs(x - current_price))

                atm_call = chain.calls[chain.calls['strike'] == atm_strike]['lastPrice'].iloc[0]
                atm_put = chain.puts[chain.puts['strike'] == atm_strike]['lastPrice'].iloc[0]

                straddle_cost = atm_call + atm_put
                implied_move_pct = (straddle_cost / current_price) * 100

                result["implied_move"] = {
                    "straddle_cost": round(straddle_cost, 2),
                    "implied_move_pct": round(implied_move_pct, 1),
                    "range": f"${current_price - straddle_cost:.2f} - ${current_price + straddle_cost:.2f}"
                }
        except:
            pass

    except Exception as e:
        result["error"] = str(e)

    return result


@mcp.tool()
def calculate_quality_score(ticker: str) -> dict[str, Any]:
    """
    Unified quality score combining financial health metrics.

    Components:
    - F-Score (30%): 7+ = good, <3 = bad
    - Z-Score (20%): >2.99 = safe, <1.81 = distress
    - ROE (20%): >15% = good
    - Debt/Equity (15%): <1.0 = good
    - Net Margin (15%): >10% = good

    Returns:
    - quality_score: 0-100
    - quality_grade: A / B / C / D / F
    - components: Individual metric values
    - red_flags: List of concerns
    - green_flags: List of positives
    """
    ticker = validate_ticker(ticker)

    result = {
        "ticker": ticker,
        "quality_score": 0,
        "quality_grade": "N/A",
        "components": {},
        "red_flags": [],
        "green_flags": []
    }

    score = 0
    max_score = 100

    try:
        # Get fundamental scores (F-Score, Z-Score)
        try:
            fund_scores = calculate_fundamental_scores_tool(ticker)

            if isinstance(fund_scores, dict):
                f_score = fund_scores.get("piotroski_f_score", {}).get("score", 0)
                z_score = fund_scores.get("altman_z_score", {}).get("score", 0)

                result["components"]["f_score"] = f_score
                result["components"]["z_score"] = round(z_score, 2) if z_score else None

                # F-Score scoring (30 pts max)
                if f_score >= 7:
                    score += 30
                    result["green_flags"].append(f"Strong F-Score: {f_score}/9")
                elif f_score >= 5:
                    score += 20
                elif f_score >= 3:
                    score += 10
                else:
                    result["red_flags"].append(f"Weak F-Score: {f_score}/9 (value trap risk)")

                # Z-Score scoring (20 pts max)
                if z_score:
                    if z_score > 2.99:
                        score += 20
                        result["green_flags"].append(f"Safe Z-Score: {z_score:.2f}")
                    elif z_score > 1.81:
                        score += 10
                    else:
                        result["red_flags"].append(f"Distress Z-Score: {z_score:.2f}")

        except Exception as e:
            result["components"]["fundamental_error"] = str(e)

        # Get financial metrics from ticker info
        try:
            t = yf.Ticker(ticker)
            info = t.info

            # ROE (20 pts max)
            roe = info.get('returnOnEquity')
            if roe is not None:
                roe_pct = roe * 100
                result["components"]["roe"] = round(roe_pct, 1)

                if roe_pct >= 20:
                    score += 20
                    result["green_flags"].append(f"Excellent ROE: {roe_pct:.1f}%")
                elif roe_pct >= 15:
                    score += 15
                    result["green_flags"].append(f"Good ROE: {roe_pct:.1f}%")
                elif roe_pct >= 10:
                    score += 10
                elif roe_pct < 5:
                    result["red_flags"].append(f"Low ROE: {roe_pct:.1f}%")

            # Debt/Equity (15 pts max)
            total_debt = info.get('totalDebt', 0)
            total_equity = info.get('totalStockholderEquity', 0)

            if total_equity and total_equity > 0:
                de_ratio = total_debt / total_equity
                result["components"]["debt_to_equity"] = round(de_ratio, 2)

                if de_ratio < 0.5:
                    score += 15
                    result["green_flags"].append(f"Low Debt/Equity: {de_ratio:.2f}")
                elif de_ratio < 1.0:
                    score += 10
                elif de_ratio > 2.0:
                    result["red_flags"].append(f"High Debt/Equity: {de_ratio:.2f}")

            # Net Margin (15 pts max)
            profit_margin = info.get('profitMargins')
            if profit_margin is not None:
                margin_pct = profit_margin * 100
                result["components"]["net_margin"] = round(margin_pct, 1)

                if margin_pct >= 15:
                    score += 15
                    result["green_flags"].append(f"High Margin: {margin_pct:.1f}%")
                elif margin_pct >= 10:
                    score += 10
                elif margin_pct >= 5:
                    score += 5
                elif margin_pct < 0:
                    result["red_flags"].append(f"Negative Margin: {margin_pct:.1f}%")

            # Additional metrics
            result["components"]["gross_margin"] = round(info.get('grossMargins', 0) * 100, 1) if info.get('grossMargins') else None
            result["components"]["operating_margin"] = round(info.get('operatingMargins', 0) * 100, 1) if info.get('operatingMargins') else None

        except Exception as e:
            result["components"]["info_error"] = str(e)

        # Calculate final score and grade
        result["quality_score"] = min(100, score)

        if score >= 80:
            result["quality_grade"] = "A"
        elif score >= 65:
            result["quality_grade"] = "B"
        elif score >= 50:
            result["quality_grade"] = "C"
        elif score >= 35:
            result["quality_grade"] = "D"
        else:
            result["quality_grade"] = "F"

    except Exception as e:
        result["error"] = str(e)

    return result


@mcp.tool()
def analyze_competitors(ticker: str, top_n: int = 5) -> dict[str, Any]:
    """
    Compare stock vs sector peers to identify true leaders.

    Returns:
    - sector: Sector name
    - sector_rank: 1 = best, N = worst
    - is_leader: bool (rank <= 3)
    - competitors: List of competitor performance data
    - relative_advantage: What makes this stock better/worse
    """
    ticker = validate_ticker(ticker)

    result = {
        "ticker": ticker,
        "sector": None,
        "industry": None,
        "sector_rank": None,
        "is_leader": False,
        "competitors": [],
        "relative_advantage": []
    }

    try:
        t = yf.Ticker(ticker)
        info = t.info

        sector = info.get('sector')
        industry = info.get('industry')

        result["sector"] = sector
        result["industry"] = industry

        if not sector:
            result["error"] = "Could not determine sector"
            return result

        # Get sector ETF for comparison
        sector_etfs = {
            "Technology": ["XLK", "QQQ"],
            "Healthcare": ["XLV", "VHT"],
            "Financial Services": ["XLF", "VFH"],
            "Consumer Cyclical": ["XLY", "VCR"],
            "Consumer Defensive": ["XLP", "VDC"],
            "Energy": ["XLE", "VDE"],
            "Industrials": ["XLI", "VIS"],
            "Basic Materials": ["XLB", "VAW"],
            "Real Estate": ["XLRE", "VNQ"],
            "Utilities": ["XLU", "VPU"],
            "Communication Services": ["XLC", "VOX"]
        }

        # Get target ticker performance (Questrade primary, Yahoo fallback, cached)
        target_hist = _get_ohlcv_cached(ticker, period="3mo")
        if target_hist is None or target_hist.empty:
            result["error"] = "Could not get price history"
            return result

        target_return_30d = (target_hist['Close'].iloc[-1] / target_hist['Close'].iloc[-22] - 1) * 100 if len(target_hist) >= 22 else 0
        target_return_90d = (target_hist['Close'].iloc[-1] / target_hist['Close'].iloc[0] - 1) * 100

        result["performance"] = {
            "return_30d": round(target_return_30d, 2),
            "return_90d": round(target_return_90d, 2)
        }

        # Compare to sector ETF
        sector_etf = sector_etfs.get(sector, ["SPY"])[0]
        try:
            # Get ETF history (Questrade primary, Yahoo fallback, cached)
            etf_hist = _get_ohlcv_cached(sector_etf, period="3mo")

            if etf_hist is not None and not etf_hist.empty:
                etf_return_30d = (etf_hist['Close'].iloc[-1] / etf_hist['Close'].iloc[-22] - 1) * 100 if len(etf_hist) >= 22 else 0
                etf_return_90d = (etf_hist['Close'].iloc[-1] / etf_hist['Close'].iloc[0] - 1) * 100

                result["vs_sector"] = {
                    "sector_etf": sector_etf,
                    "sector_return_30d": round(etf_return_30d, 2),
                    "sector_return_90d": round(etf_return_90d, 2),
                    "outperformance_30d": round(target_return_30d - etf_return_30d, 2),
                    "outperformance_90d": round(target_return_90d - etf_return_90d, 2)
                }

                if target_return_30d > etf_return_30d:
                    result["relative_advantage"].append(f"Outperforming {sector_etf} by {target_return_30d - etf_return_30d:.1f}% (30d)")
                    result["is_leader"] = True
                else:
                    result["relative_advantage"].append(f"Underperforming {sector_etf} by {etf_return_30d - target_return_30d:.1f}% (30d)")

        except:
            pass

        # Find industry peers using comprehensive mapping with fuzzy matching + sector fallback
        try:
            # Comprehensive industry peer mapping (60+ industries)
            industry_peers = {
                # Technology - Software
                "Software - Infrastructure": ["MSFT", "ORCL", "CRM", "NOW", "ADBE", "INTU", "PANW", "CRWD", "SNOW", "DDOG"],
                "Software - Application": ["CRM", "ADBE", "NOW", "WDAY", "ZM", "TEAM", "HUBS", "DOCU", "ZS", "OKTA"],
                "Software—Infrastructure": ["MSFT", "ORCL", "CRM", "NOW", "ADBE", "INTU", "PANW", "CRWD", "SNOW", "DDOG"],
                "Software—Application": ["CRM", "ADBE", "NOW", "WDAY", "ZM", "TEAM", "HUBS", "DOCU", "ZS", "OKTA"],
                "Information Technology Services": ["ACN", "IBM", "INFY", "WIT", "CTSH", "EPAM", "LDOS", "DXC"],
                "Electronic Components": ["TEL", "APH", "GLW", "JBL", "FLEX", "SANM", "ARW", "AVT"],
                "Computer Hardware": ["AAPL", "HPQ", "DELL", "NTAP", "WDC", "STX", "PSTG"],
                # Technology - Semiconductors & Electronics
                "Semiconductors": ["NVDA", "AMD", "INTC", "AVGO", "QCOM", "TSM", "TXN", "MU", "MRVL", "AMAT"],
                "Semiconductor Equipment & Materials": ["AMAT", "LRCX", "KLAC", "ASML", "ENTG", "TER", "MKSI"],
                "Consumer Electronics": ["AAPL", "SONY", "SONO", "GPRO", "KOSS", "VZIO"],
                # Technology - Internet & Digital
                "Internet Content & Information": ["GOOGL", "META", "SNAP", "PINS", "NFLX", "SPOT", "RBLX", "RDDT"],
                "Internet Retail": ["AMZN", "BABA", "JD", "MELI", "SHOP", "EBAY", "ETSY", "W", "CHWY"],
                "Entertainment": ["DIS", "NFLX", "WBD", "PARA", "LYV", "MSG", "IMAX"],
                "Electronic Gaming & Multimedia": ["EA", "TTWO", "ATVI", "U", "RBLX", "PLTK"],
                # Financial - Banking
                "Banks - Diversified": ["JPM", "BAC", "WFC", "C", "USB", "PNC", "TFC", "COF", "SCHW"],
                "Banks - Regional": ["USB", "PNC", "TFC", "FRC", "MTB", "FITB", "HBAN", "RF", "KEY", "CFG"],
                "Banks—Diversified": ["JPM", "BAC", "WFC", "C", "USB", "PNC", "TFC", "COF", "SCHW"],
                "Banks—Regional": ["USB", "PNC", "TFC", "MTB", "FITB", "HBAN", "RF", "KEY", "CFG"],
                # Financial - Investment & Insurance
                "Asset Management": ["BLK", "BX", "KKR", "APO", "ARES", "TROW", "IVZ", "BEN"],
                "Insurance - Diversified": ["BRK-B", "AIG", "MET", "PRU", "ALL", "TRV", "CB", "AFL"],
                "Insurance - Life": ["MET", "PRU", "LNC", "AFL", "GL", "PFG"],
                "Insurance - Property & Casualty": ["PGR", "ALL", "TRV", "CB", "AIG", "CNA", "HIG"],
                "Capital Markets": ["GS", "MS", "SCHW", "IBKR", "SF", "LAZ", "EVR", "MC"],
                "Credit Services": ["V", "MA", "AXP", "DFS", "COF", "SYF", "PYPL", "SQ"],
                # Healthcare - Pharma & Biotech
                "Drug Manufacturers - General": ["JNJ", "PFE", "MRK", "LLY", "ABBV", "BMY", "NVO", "AZN", "GSK"],
                "Drug Manufacturers—General": ["JNJ", "PFE", "MRK", "LLY", "ABBV", "BMY", "NVO", "AZN", "GSK"],
                "Biotechnology": ["AMGN", "GILD", "REGN", "VRTX", "BIIB", "MRNA", "BNTX", "SGEN", "ALNY", "INCY"],
                "Pharmaceutical Retailers": ["WBA", "CVS", "CI", "AMGN"],
                # Healthcare - Medical
                "Medical Devices": ["ABT", "MDT", "SYK", "BSX", "EW", "ISRG", "DXCM", "ALGN", "ZBH", "BAX"],
                "Medical Instruments & Supplies": ["ABT", "MDT", "SYK", "BSX", "EW", "ISRG", "DXCM", "ALGN"],
                "Health Care Plans": ["UNH", "CVS", "CI", "ELV", "HUM", "CNC", "MOH"],
                "Healthcare Plans": ["UNH", "CVS", "CI", "ELV", "HUM", "CNC", "MOH"],
                "Medical Distribution": ["MCK", "CAH", "ABC", "CI"],
                "Diagnostics & Research": ["TMO", "DHR", "ILMN", "A", "IQV", "LH", "DGX"],
                # Consumer - Retail
                "Specialty Retail": ["HD", "LOW", "TJX", "ROST", "ULTA", "BBY", "TSCO", "WSM", "AZO", "ORLY"],
                "Discount Stores": ["WMT", "TGT", "COST", "DG", "DLTR"],
                "Apparel Retail": ["TJX", "ROST", "GPS", "ANF", "AEO", "URBN", "LULU"],
                "Luxury Goods": ["LVMUY", "TPR", "RL", "CPRI", "TPCO"],
                "Department Stores": ["M", "KSS", "JWN", "DDS"],
                # Consumer - Food & Beverage
                "Restaurants": ["MCD", "SBUX", "CMG", "YUM", "DPZ", "QSR", "DRI", "WING", "TXRH", "BLMN"],
                "Beverages - Wineries & Distilleries": ["STZ", "BF-B", "TAP", "SAM", "BUD"],
                "Beverages - Non-Alcoholic": ["KO", "PEP", "MNST", "KDP", "CELH"],
                "Packaged Foods": ["GIS", "K", "CAG", "CPB", "MKC", "HSY", "MDLZ"],
                "Food Distribution": ["SYY", "USFD", "PFGC"],
                # Consumer - Other
                "Auto Manufacturers": ["TSLA", "F", "GM", "TM", "HMC", "RIVN", "LCID", "NIO", "STLA"],
                "Auto Parts": ["APTV", "LEA", "ADNT", "BWA", "ALV", "MOD", "VC"],
                "Leisure": ["CCL", "RCL", "NCLH", "MAR", "HLT", "H", "IHG"],
                "Travel Services": ["BKNG", "EXPE", "TRIP", "ABNB", "TCOM"],
                "Furnishings, Fixtures & Appliances": ["WHR", "LEG", "ETD", "SNBR"],
                # Energy
                "Oil & Gas Integrated": ["XOM", "CVX", "COP", "TTE", "BP", "SHEL"],
                "Oil & Gas E&P": ["EOG", "PXD", "DVN", "COP", "OXY", "FANG", "MRO", "APA", "HES"],
                "Oil & Gas Midstream": ["EPD", "ET", "WMB", "OKE", "MPLX", "PAA", "KMI"],
                "Oil & Gas Refining & Marketing": ["PSX", "VLO", "MPC", "HFC", "DINO"],
                "Oil & Gas Equipment & Services": ["SLB", "HAL", "BKR", "FTI", "NOV", "HP", "PTEN"],
                # Industrial
                "Aerospace & Defense": ["BA", "RTX", "LMT", "NOC", "GD", "LHX", "HWM", "TDG", "TXT"],
                "Railroads": ["UNP", "CSX", "NSC", "CP", "CNI"],
                "Airlines": ["DAL", "UAL", "AAL", "LUV", "JBLU", "SAVE", "ALK"],
                "Trucking": ["ODFL", "XPO", "JBHT", "KNX", "CHRW", "LSTR"],
                "Marine Shipping": ["EGLE", "SBLK", "STNG", "FRO", "INSW"],
                "Industrial Distribution": ["GWW", "FAST", "WST", "DCI"],
                "Building Products & Equipment": ["JCI", "CARR", "BLD", "OC", "MAS", "BLDR"],
                "Engineering & Construction": ["FLR", "STRL", "PWR", "EME", "MTZ", "ACM"],
                "Machinery": ["CAT", "DE", "CMI", "EMR", "ETN", "ITW", "PH", "ROK"],
                # Materials
                "Chemicals": ["LIN", "APD", "ECL", "SHW", "DD", "DOW", "PPG", "NEM"],
                "Steel": ["NUE", "STLD", "X", "CLF", "RS", "MT"],
                "Copper": ["FCX", "SCCO", "TGB", "CMCL"],
                "Gold": ["NEM", "GOLD", "AEM", "KGC", "FNV"],
                "Agricultural Inputs": ["NTR", "MOS", "CF", "ICL", "SMG"],
                # Communication & Utilities
                "Telecom Services": ["T", "VZ", "TMUS", "LUMN"],
                "Telecommunications Services": ["T", "VZ", "TMUS", "LUMN"],
                "Wireless Telecommunication Services": ["T", "VZ", "TMUS"],
                "Utilities - Regulated Electric": ["NEE", "DUK", "SO", "D", "AEP", "XEL", "SRE", "ED"],
                "Utilities - Renewable": ["NEE", "AES", "BEP", "CWEN", "RUN"],
                "Utilities - Independent Power Producers": ["NEE", "AES", "NRG", "VST", "CEG", "OKLO"],
                "Specialty Industrial Machinery": ["ITW", "ROK", "EMR", "ETN", "PH", "IR", "DOV", "XYL", "FLS", "NDSN"],
                "Utilities—Regulated Electric": ["NEE", "DUK", "SO", "D", "AEP", "XEL", "SRE", "ED"],
                # Real Estate
                "REIT - Residential": ["EQR", "AVB", "ESS", "MAA", "UDR", "CPT"],
                "REIT - Retail": ["SPG", "REG", "KIM", "BRX", "SKT"],
                "REIT - Office": ["BXP", "VNO", "SLG", "DEI", "CUZ"],
                "REIT - Industrial": ["PLD", "DRE", "FR", "REXR", "STAG"],
                "REIT - Healthcare Facilities": ["WELL", "VTR", "PEAK", "DOC", "HR"],
            }

            # Sector-based fallback mapping when industry not found
            sector_peers = {
                "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AVGO", "ORCL", "AMD"],
                "Financial Services": ["JPM", "BAC", "WFC", "GS", "MS", "BLK", "SCHW", "AXP", "C", "USB"],
                "Healthcare": ["UNH", "JNJ", "LLY", "ABBV", "MRK", "TMO", "ABT", "PFE", "DHR", "BMY"],
                "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG"],
                "Consumer Defensive": ["WMT", "PG", "COST", "KO", "PEP", "PM", "MDLZ", "CL", "KMB", "GIS"],
                "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "WMB"],
                "Industrials": ["CAT", "HON", "UNP", "RTX", "BA", "GE", "LMT", "DE", "MMM", "UPS"],
                "Basic Materials": ["LIN", "APD", "SHW", "ECL", "NEM", "FCX", "NUE", "DD", "DOW", "PPG"],
                "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "WBD"],
                "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "XEL", "EXC", "ED", "WEC"],
                "Real Estate": ["PLD", "AMT", "EQIX", "PSA", "CCI", "SPG", "WELL", "DLR", "O", "AVB"],
            }

            industry = info.get('industry')
            sector = info.get('sector')

            # Try exact match first
            peers = None
            if industry and industry in industry_peers:
                peers = industry_peers[industry]

            # Try fuzzy match (normalize dashes/em-dashes, case)
            if not peers and industry:
                normalized_industry = industry.replace('—', ' - ').replace('  ', ' ')
                for key in industry_peers:
                    if key.replace('—', ' - ').replace('  ', ' ').lower() == normalized_industry.lower():
                        peers = industry_peers[key]
                        break

            # Fallback to sector-based peers
            if not peers and sector and sector in sector_peers:
                peers = sector_peers[sector]
                result["note"] = f"Industry '{industry}' not found. Using sector '{sector}' peers."

            if peers:
                # Remove target ticker from peers list
                peers = [p for p in peers if p.upper() != ticker.upper()][:top_n]

                competitors = []
                for peer in peers:
                    try:
                        # Get peer history (Questrade primary, Yahoo fallback, cached)
                        peer_hist = _get_ohlcv_cached(peer, period="3mo")
                        if peer_hist is not None and not peer_hist.empty and len(peer_hist) >= 22:
                            peer_30d = (peer_hist['Close'].iloc[-1] / peer_hist['Close'].iloc[-22] - 1) * 100
                            peer_90d = (peer_hist['Close'].iloc[-1] / peer_hist['Close'].iloc[0] - 1) * 100

                            # Calculate RS score for peer
                            peer_rs = calculate_relative_strength_tool(peer, benchmark="SPY", period="3mo")
                            peer_rs_score = peer_rs.get("rs_score", 50) if isinstance(peer_rs, dict) else 50

                            competitors.append({
                                "ticker": peer,
                                "return_30d": round(peer_30d, 2),
                                "return_90d": round(peer_90d, 2),
                                "rs_score": peer_rs_score
                            })
                    except Exception:
                        continue

                if competitors:
                    # Sort by 30d return and add ranking
                    competitors.sort(key=lambda x: x['return_30d'], reverse=True)
                    all_returns = [c['return_30d'] for c in competitors] + [target_return_30d]
                    all_returns.sort(reverse=True)
                    target_rank = all_returns.index(target_return_30d) + 1

                    result["competitors"] = competitors
                    result["sector_rank"] = target_rank
                    result["total_peers"] = len(competitors) + 1
                    result["is_leader"] = target_rank <= 3

                    if target_rank == 1:
                        result["relative_advantage"].append(f"#1 in industry (30d performance)")
                    elif target_rank <= 3:
                        result["relative_advantage"].append(f"Top 3 in industry (rank #{target_rank})")
                    else:
                        result["relative_advantage"].append(f"Rank #{target_rank} of {len(competitors) + 1} in industry")
            else:
                result["note"] = f"No peers found for industry '{industry}' or sector '{sector}'. Compared against {sector_etf} sector ETF."

        except Exception as peer_err:
            result["note"] = f"Peer comparison unavailable: {str(peer_err)[:50]}. Compared against {sector_etf} sector ETF."

        # Calculate RS vs SPY
        try:
            rs_data = calculate_relative_strength_tool(ticker, benchmark="SPY", period="3mo")
            if isinstance(rs_data, dict):
                rs_score = rs_data.get("rs_score", 0)
                result["rs_vs_spy"] = rs_score

                if rs_score >= 70:
                    result["relative_advantage"].append(f"Strong RS Score: {rs_score}")
                    result["is_leader"] = True
                elif rs_score <= 30:
                    result["relative_advantage"].append(f"Weak RS Score: {rs_score}")

        except:
            pass

    except Exception as e:
        result["error"] = str(e)

    return result


@mcp.tool()
def generate_trading_signal(
    ticker: str,
    direction: Literal["LONG", "SHORT"] = "LONG",
    account_size: float = 10000.0
) -> dict[str, Any]:
    """
    Generate actionable trading signal with complete trading plan.

    Combines all analysis tools to produce:
    - Signal: STRONG_BUY / BUY / WATCH / NO_TRADE / SELL / STRONG_SELL
    - Complete trading plan with entry, stop, targets
    - Proof of validity from historical analysis
    - Gate status for all requirements

    Args:
        ticker: Stock symbol
        direction: Expected direction (LONG or SHORT)
        account_size: Account size for position sizing

    Returns:
        Complete trading signal with plan and validation
    """
    from datetime import datetime

    ticker = validate_ticker(ticker)

    result = {
        "ticker": ticker,
        "direction": direction,
        "signal": "NO_TRADE",
        "confidence": 0,
        "generated_at": datetime.now().isoformat(),
        "trading_plan": None,
        "proof_of_validity": None,
        "gate_status": {
            "catalyst": "PENDING",
            "freshness": "PENDING",
            "brooks": "PENDING",
            "quality": "PENDING"
        },
        "warnings": [],
        "summary": ""
    }

    score = 0
    max_score = 100

    try:
        # Get current price
        t = yf.Ticker(ticker)
        info = t.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)

        if not current_price:
            result["warnings"].append("Could not get current price")
            return result

        result["current_price"] = current_price

        # ========== GATE 1: CATALYST CHECK ==========
        try:
            catalyst_data = detect_catalyst_strength(ticker)

            result["catalyst_analysis"] = {
                "strength": catalyst_data.get("catalyst_strength"),
                "score": catalyst_data.get("catalyst_score"),
                "catalysts": catalyst_data.get("catalysts_detected", [])
            }

            if catalyst_data.get("trade_allowed"):
                result["gate_status"]["catalyst"] = "PASS"
                score += 25 if catalyst_data.get("catalyst_strength") == "STRONG" else 15
            else:
                result["gate_status"]["catalyst"] = "FAIL"
                result["warnings"].append("No catalyst present - trade not recommended")

        except Exception as e:
            result["gate_status"]["catalyst"] = "ERROR"
            result["warnings"].append(f"Catalyst check failed: {e}")

        # ========== GATE 2: FRESHNESS CHECK (CVD, Exhaustion) ==========
        try:
            # Get volume analysis for CVD
            volume_data = analyze_volume_tool(ticker, period="3mo")

            # Get exhaustion score directly (FIXED: was using missing field from volume_data)
            from investor_agent.technical_analysis_bootstrap import calculate_exhaustion_score
            exhaustion_data = calculate_exhaustion_score(ticker, direction, period="3mo")
            exhaustion = exhaustion_data.get("score", 50) if isinstance(exhaustion_data, dict) else 50

            if isinstance(volume_data, dict):
                cvd_trend = volume_data.get("cvd_analysis", {}).get("cvd_trend", "FLAT")

                result["freshness_analysis"] = {
                    "cvd_trend": cvd_trend,
                    "exhaustion_score": exhaustion,
                    "exhaustion_level": exhaustion_data.get("level", "UNKNOWN") if isinstance(exhaustion_data, dict) else "UNKNOWN"
                }

                # Check CVD alignment
                cvd_aligned = (direction == "LONG" and cvd_trend in ["RISING", "FLAT"]) or \
                              (direction == "SHORT" and cvd_trend in ["FALLING", "FLAT"])

                # Check exhaustion
                not_exhausted = exhaustion < 50

                if cvd_aligned and not_exhausted:
                    result["gate_status"]["freshness"] = "PASS"
                    score += 20
                else:
                    result["gate_status"]["freshness"] = "FAIL"
                    if not cvd_aligned:
                        result["warnings"].append(f"CVD not aligned: {cvd_trend}")
                    if not not_exhausted:
                        result["warnings"].append(f"High exhaustion: {exhaustion}")

        except Exception as e:
            result["gate_status"]["freshness"] = "ERROR"
            result["warnings"].append(f"Freshness check failed: {e}")

        # ========== GATE 3: AL BROOKS ANALYSIS ==========
        # FIXED: Call AlBrooksAnalyzer directly with user-specified direction
        # (same as scanner does) instead of using analyze_technical() which
        # determines its own direction based on MA/MACD trends
        try:
            # Get OHLCV data for Brooks analysis
            ohlcv = _get_ohlcv_cached(ticker, period="3mo")

            # Get technical data for context (but NOT for Brooks direction)
            technical_data = analyze_technical(ticker, period="3mo", include_ml_analysis=False, include_trend_score=False)

            # Call AlBrooksAnalyzer directly with the USER-SPECIFIED direction
            brooks_analyzer = AlBrooksAnalyzer()
            brooks = brooks_analyzer.analyze(
                ticker=ticker,
                direction=direction.lower(),  # AlBrooks expects lowercase
                ohlcv_data=ohlcv,
                technical_data=technical_data or {}
            )

            if isinstance(brooks, dict):
                always_in = brooks.get("always_in", "NEUTRAL")
                trap_risk = brooks.get("trap_risk", "MEDIUM")
                # Use adjusted_probability (same as scanner)
                probability = brooks.get("adjusted_probability", brooks.get("base_probability", 50))
                pattern = brooks.get("pattern", "Unknown")

                result["brooks_analysis"] = {
                    "always_in": always_in,
                    "trap_risk": trap_risk,
                    "probability": probability,
                    "pattern": pattern
                }

                # Check Al Brooks gates
                direction_ok = (direction == "LONG" and always_in in ["LONG", "NEUTRAL"]) or \
                               (direction == "SHORT" and always_in in ["SHORT", "NEUTRAL"])
                trap_ok = trap_risk != "HIGH"
                prob_ok = probability >= 55

                if direction_ok and trap_ok and prob_ok:
                    result["gate_status"]["brooks"] = "PASS"
                    score += 25
                else:
                    result["gate_status"]["brooks"] = "FAIL"
                    if not direction_ok:
                        result["warnings"].append(f"Always-In is {always_in}, not aligned with {direction}")
                    if not trap_ok:
                        result["warnings"].append("HIGH trap risk detected")
                    if not prob_ok:
                        result["warnings"].append(f"Low probability: {probability}%")

        except Exception as e:
            result["gate_status"]["brooks"] = "ERROR"
            result["warnings"].append(f"Brooks analysis failed: {e}")

        # ========== GATE 4: QUALITY CHECK ==========
        try:
            quality_data = calculate_quality_score(ticker)

            if isinstance(quality_data, dict):
                quality_score = quality_data.get("quality_score", 0)
                quality_grade = quality_data.get("quality_grade", "N/A")

                result["quality_analysis"] = {
                    "score": quality_score,
                    "grade": quality_grade,
                    "red_flags": quality_data.get("red_flags", [])
                }

                if quality_score >= 50:
                    result["gate_status"]["quality"] = "PASS"
                    score += 15
                else:
                    result["gate_status"]["quality"] = "FAIL"
                    result["warnings"].append(f"Low quality score: {quality_score}")

        except Exception as e:
            result["gate_status"]["quality"] = "ERROR"

        # ========== PROOF OF VALIDITY ==========
        try:
            similar = find_similar_historical_setups(
                ticker=ticker,
                direction=direction,
                target_return_pct=5.0,
                holding_period_days=10
            )

            if isinstance(similar, dict) and 'error' not in similar:
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

        except Exception as e:
            result["proof_of_validity"] = {"error": str(e)}

        # ========== GENERATE TRADING PLAN ==========
        try:
            # Get support/resistance for stop/target
            sr_data = find_support_resistance(ticker)
            volatility_data = analyze_volatility_tool(ticker)

            atr = volatility_data.get("atr", {}).get("value", current_price * 0.02) if isinstance(volatility_data, dict) else current_price * 0.02

            if direction == "LONG":
                # Entry at current price or pullback
                entry_price = current_price

                # Stop below nearest support or 2x ATR
                supports = sr_data.get("supports", []) if isinstance(sr_data, dict) else []
                if supports:
                    stop_price = min(supports[0].get("price", entry_price - 2*atr), entry_price - 2*atr)
                else:
                    stop_price = entry_price - 2*atr

                # Targets
                resistances = sr_data.get("resistances", []) if isinstance(sr_data, dict) else []
                target_1 = resistances[0].get("price", entry_price + 1.5*(entry_price - stop_price)) if resistances else entry_price + 1.5*(entry_price - stop_price)
                target_2 = resistances[1].get("price", entry_price + 2.5*(entry_price - stop_price)) if len(resistances) > 1 else entry_price + 2.5*(entry_price - stop_price)

            else:  # SHORT
                entry_price = current_price
                resistances = sr_data.get("resistances", []) if isinstance(sr_data, dict) else []
                if resistances:
                    stop_price = max(resistances[0].get("price", entry_price + 2*atr), entry_price + 2*atr)
                else:
                    stop_price = entry_price + 2*atr

                supports = sr_data.get("supports", []) if isinstance(sr_data, dict) else []
                target_1 = supports[0].get("price", entry_price - 1.5*(stop_price - entry_price)) if supports else entry_price - 1.5*(stop_price - entry_price)
                target_2 = supports[1].get("price", entry_price - 2.5*(stop_price - entry_price)) if len(supports) > 1 else entry_price - 2.5*(stop_price - entry_price)

            risk_per_share = abs(entry_price - stop_price)
            reward_1 = abs(target_1 - entry_price)
            risk_reward = reward_1 / risk_per_share if risk_per_share > 0 else 0

            # Position sizing (1% risk)
            risk_amount = account_size * 0.01
            shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0

            result["trading_plan"] = {
                "entry_price": round(entry_price, 2),
                "entry_type": "LIMIT",
                "stop_loss": {
                    "price": round(stop_price, 2),
                    "risk_pct": round((abs(entry_price - stop_price) / entry_price) * 100, 2)
                },
                "target_1": {
                    "price": round(target_1, 2),
                    "reward_pct": round((abs(target_1 - entry_price) / entry_price) * 100, 2)
                },
                "target_2": {
                    "price": round(target_2, 2),
                    "reward_pct": round((abs(target_2 - entry_price) / entry_price) * 100, 2)
                },
                "risk_reward_ratio": round(risk_reward, 2),
                "position_size": {
                    "shares": shares,
                    "dollar_risk": round(risk_amount, 2),
                    "position_value": round(shares * entry_price, 2)
                },
                "time_frame": "5-15 trading days"
            }

        except Exception as e:
            result["trading_plan"] = {"error": str(e)}

        # ========== DETERMINE FINAL SIGNAL ==========
        result["confidence"] = score

        # Count passed gates
        passed_gates = sum(1 for g in result["gate_status"].values() if g == "PASS")

        if passed_gates == 4 and score >= 70:
            result["signal"] = f"STRONG_{'BUY' if direction == 'LONG' else 'SELL'}"
        elif passed_gates >= 3 and score >= 55:
            result["signal"] = "BUY" if direction == "LONG" else "SELL"
        elif passed_gates >= 2 and score >= 40:
            result["signal"] = "WATCH"
        else:
            result["signal"] = "NO_TRADE"

        # Generate summary
        result["summary"] = f"{ticker}: {result['signal']} | Confidence: {score}% | Gates: {passed_gates}/4 passed"

    except Exception as e:
        result["error"] = str(e)
        result["signal"] = "ERROR"

    return result


# =============================================================================
# RANKING VALIDATION SYSTEM
# =============================================================================

# Performance tracking storage (in-memory, persisted to JSON)
_pick_history: list[dict] = []
_pick_history_file = Path(__file__).parent / "pick_history.json"


def _load_pick_history():
    """Load pick history from JSON file."""
    global _pick_history
    if _pick_history_file.exists():
        try:
            with open(_pick_history_file, 'r') as f:
                _pick_history = json.load(f)
            logger.info(f"Loaded {len(_pick_history)} picks from history")
        except Exception as e:
            logger.warning(f"Failed to load pick history: {e}")
            _pick_history = []


def _save_pick_history():
    """Save pick history to JSON file."""
    try:
        with open(_pick_history_file, 'w') as f:
            json.dump(_pick_history, f, indent=2, default=str)
        logger.debug(f"Saved {len(_pick_history)} picks to history")
    except Exception as e:
        logger.warning(f"Failed to save pick history: {e}")


def track_scanner_pick(
    ticker: str,
    direction: str,
    composite_score: float,
    entry_price: float,
    stop_price: float,
    target_price: float,
    signal: str,
    scanner_source: str = "tradingview"
) -> dict:
    """
    Track a scanner pick for future performance validation.

    Args:
        ticker: Stock symbol
        direction: LONG or SHORT
        composite_score: Composite score from scanner (0-100)
        entry_price: Recommended entry price
        stop_price: Stop loss price
        target_price: Target price
        signal: Signal type (BUY, WATCH, SKIP, etc.)
        scanner_source: Data source (tradingview, finviz)

    Returns:
        dict: Pick record
    """
    from datetime import datetime
    import pytz

    et = pytz.timezone("America/New_York")
    now = datetime.now(et)

    pick = {
        "id": f"{ticker}_{now.strftime('%Y%m%d_%H%M%S')}",
        "ticker": ticker,
        "direction": direction,
        "composite_score": composite_score,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price,
        "signal": signal,
        "scanner_source": scanner_source,
        "picked_at": now.isoformat(),
        "picked_date": now.strftime("%Y-%m-%d"),
        # Forward returns (updated later)
        "return_5d": None,
        "return_10d": None,
        "return_20d": None,
        "hit_target": None,
        "hit_stop": None,
        "days_to_target": None,
        "days_to_stop": None,
        "outcome": None,  # WIN / LOSS / OPEN
        "validated": False
    }

    _pick_history.append(pick)
    _save_pick_history()

    return pick


def validate_pick_outcomes():
    """
    Validate outcomes for all tracked picks by fetching current prices.

    Updates forward returns and outcome status for each pick.
    """
    from datetime import datetime, timedelta
    import pytz

    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    today = now.date()

    validated_count = 0

    for pick in _pick_history:
        if pick.get("validated"):
            continue

        pick_date = datetime.fromisoformat(pick["picked_at"]).date()
        days_since_pick = (today - pick_date).days

        if days_since_pick < 1:
            continue  # Need at least 1 day of data

        ticker = pick["ticker"]
        direction = pick["direction"]
        entry_price = pick["entry_price"]
        stop_price = pick["stop_price"]
        target_price = pick["target_price"]

        try:
            # Fetch price history since pick
            ohlcv = _get_ohlcv_for_ticker_v2(ticker, period="1mo")

            if ohlcv is None or ohlcv.empty:
                continue

            # Filter to dates after pick
            pick_datetime = datetime.fromisoformat(pick["picked_at"])
            ohlcv_after = ohlcv[ohlcv.index > pick_datetime]

            if ohlcv_after.empty:
                continue

            # Calculate forward returns
            closes = ohlcv_after['Close'].values
            current_price = closes[-1] if len(closes) > 0 else entry_price

            # 5d, 10d, 20d returns
            if len(closes) >= 5:
                pick["return_5d"] = round((closes[4] - entry_price) / entry_price * 100, 2)
            if len(closes) >= 10:
                pick["return_10d"] = round((closes[9] - entry_price) / entry_price * 100, 2)
            if len(closes) >= 20:
                pick["return_20d"] = round((closes[19] - entry_price) / entry_price * 100, 2)
                pick["validated"] = True

            # Check if hit target or stop
            if direction == "LONG":
                highs = ohlcv_after['High'].values
                lows = ohlcv_after['Low'].values

                for i, (high, low) in enumerate(zip(highs, lows)):
                    if high >= target_price and pick["hit_target"] is None:
                        pick["hit_target"] = True
                        pick["days_to_target"] = i + 1
                    if low <= stop_price and pick["hit_stop"] is None:
                        pick["hit_stop"] = True
                        pick["days_to_stop"] = i + 1

            else:  # SHORT
                highs = ohlcv_after['High'].values
                lows = ohlcv_after['Low'].values

                for i, (high, low) in enumerate(zip(highs, lows)):
                    if low <= target_price and pick["hit_target"] is None:
                        pick["hit_target"] = True
                        pick["days_to_target"] = i + 1
                    if high >= stop_price and pick["hit_stop"] is None:
                        pick["hit_stop"] = True
                        pick["days_to_stop"] = i + 1

            # Determine outcome
            if pick["hit_target"] and not pick.get("hit_stop"):
                pick["outcome"] = "WIN"
            elif pick["hit_stop"] and not pick.get("hit_target"):
                pick["outcome"] = "LOSS"
            elif pick["hit_target"] and pick["hit_stop"]:
                # Both hit - check which came first
                if (pick.get("days_to_target") or 999) <= (pick.get("days_to_stop") or 999):
                    pick["outcome"] = "WIN"
                else:
                    pick["outcome"] = "LOSS"
            elif days_since_pick >= 20:
                # 20 days passed without hitting target or stop
                if direction == "LONG":
                    pick["outcome"] = "WIN" if current_price > entry_price else "LOSS"
                else:
                    pick["outcome"] = "WIN" if current_price < entry_price else "LOSS"
            else:
                pick["outcome"] = "OPEN"

            validated_count += 1

        except Exception as e:
            logger.warning(f"Failed to validate {ticker}: {e}")
            continue

    _save_pick_history()
    return validated_count


@mcp.tool()
def get_ranking_validation_report() -> dict:
    """
    Generate a comprehensive ranking validation report.

    Analyzes all tracked picks to show:
    - Overall win rate
    - Win rate by score bucket (60-70, 70-80, 80+)
    - Win rate by signal type (BUY, WATCH, SKIP)
    - Average returns by score bucket
    - Score-return correlation

    Returns:
        dict: Comprehensive validation report proving (or disproving) ranking quality
    """
    _load_pick_history()

    # Validate any unvalidated picks
    validated_count = validate_pick_outcomes()

    if not _pick_history:
        return {
            "status": "NO_DATA",
            "message": "No picks tracked yet. Scanner picks will be tracked automatically.",
            "how_to_track": "Run scan_market_opportunities() - picks are tracked automatically."
        }

    # Filter to picks with outcomes
    picks_with_outcome = [p for p in _pick_history if p.get("outcome") in ["WIN", "LOSS"]]

    if not picks_with_outcome:
        open_picks = [p for p in _pick_history if p.get("outcome") == "OPEN"]
        return {
            "status": "PENDING",
            "message": f"{len(open_picks)} picks tracked, waiting for 20-day validation period",
            "tracked_picks": len(_pick_history),
            "open_picks": len(open_picks)
        }

    # Calculate metrics
    total_picks = len(picks_with_outcome)
    wins = sum(1 for p in picks_with_outcome if p["outcome"] == "WIN")
    losses = total_picks - wins
    overall_win_rate = round(wins / total_picks * 100, 1) if total_picks > 0 else 0

    # Win rate by score bucket
    score_buckets = {
        "40-50": {"wins": 0, "total": 0, "returns": []},
        "50-60": {"wins": 0, "total": 0, "returns": []},
        "60-70": {"wins": 0, "total": 0, "returns": []},
        "70-80": {"wins": 0, "total": 0, "returns": []},
        "80+": {"wins": 0, "total": 0, "returns": []},
    }

    for p in picks_with_outcome:
        score = p.get("composite_score", 0)
        ret_20d = p.get("return_20d")

        if score >= 80:
            bucket = "80+"
        elif score >= 70:
            bucket = "70-80"
        elif score >= 60:
            bucket = "60-70"
        elif score >= 50:
            bucket = "50-60"
        else:
            bucket = "40-50"

        score_buckets[bucket]["total"] += 1
        if p["outcome"] == "WIN":
            score_buckets[bucket]["wins"] += 1
        if ret_20d is not None:
            score_buckets[bucket]["returns"].append(ret_20d)

    # Calculate bucket stats
    bucket_stats = {}
    for bucket, data in score_buckets.items():
        if data["total"] > 0:
            bucket_stats[bucket] = {
                "total_picks": data["total"],
                "wins": data["wins"],
                "losses": data["total"] - data["wins"],
                "win_rate": round(data["wins"] / data["total"] * 100, 1),
                "avg_return": round(sum(data["returns"]) / len(data["returns"]), 2) if data["returns"] else None
            }

    # Win rate by signal type
    signal_stats = {}
    for signal_type in ["BUY", "WATCH", "SKIP", "NO_TRADE"]:
        signal_picks = [p for p in picks_with_outcome if p.get("signal") == signal_type]
        if signal_picks:
            signal_wins = sum(1 for p in signal_picks if p["outcome"] == "WIN")
            signal_stats[signal_type] = {
                "total_picks": len(signal_picks),
                "wins": signal_wins,
                "win_rate": round(signal_wins / len(signal_picks) * 100, 1)
            }

    # Calculate correlation (simple linear)
    scores = [p.get("composite_score", 0) for p in picks_with_outcome if p.get("return_20d") is not None]
    returns = [p.get("return_20d") for p in picks_with_outcome if p.get("return_20d") is not None]

    correlation = None
    if len(scores) >= 5:
        try:
            import numpy as np
            correlation = round(np.corrcoef(scores, returns)[0, 1], 3)
        except:
            pass

    # Build report
    report = {
        "status": "OK",
        "summary": {
            "total_picks_tracked": len(_pick_history),
            "picks_with_outcome": total_picks,
            "open_picks": len([p for p in _pick_history if p.get("outcome") == "OPEN"]),
            "overall_win_rate": overall_win_rate,
            "total_wins": wins,
            "total_losses": losses
        },
        "score_bucket_analysis": bucket_stats,
        "signal_type_analysis": signal_stats,
        "score_return_correlation": correlation,
        "interpretation": {
            "ranking_quality": "GOOD" if overall_win_rate >= 55 else "NEEDS_IMPROVEMENT" if overall_win_rate >= 45 else "POOR",
            "correlation_strength": "STRONG" if correlation and correlation > 0.3 else "MODERATE" if correlation and correlation > 0.1 else "WEAK" if correlation else "UNKNOWN",
            "recommendation": "Higher scores DO correlate with better returns" if correlation and correlation > 0.1 else "Score correlation unclear - more data needed"
        },
        "validation_date": datetime.now().isoformat()
    }

    # Add markdown report
    md = f"""
## 📊 Scanner Ranking Validation Report

### Overall Performance
- **Total Picks**: {total_picks}
- **Win Rate**: {overall_win_rate}%
- **Wins**: {wins} | **Losses**: {losses}

### Win Rate by Score Bucket
"""
    for bucket, stats in bucket_stats.items():
        md += f"- **{bucket}**: {stats['win_rate']}% ({stats['wins']}/{stats['total_picks']} wins)"
        if stats['avg_return'] is not None:
            md += f" | Avg Return: {stats['avg_return']:+.1f}%"
        md += "\n"

    md += f"""
### Score-Return Correlation
- **Correlation**: {correlation if correlation else 'N/A'}
- **Interpretation**: {report['interpretation']['correlation_strength']}

### Conclusion
**Ranking Quality**: {report['interpretation']['ranking_quality']}
{report['interpretation']['recommendation']}
"""

    report["markdown_report"] = md

    return report


# Auto-track picks when scanner runs (hook into scan_market_opportunities result)
def _auto_track_picks(result: dict, scanner_source: str = "tradingview"):
    """Automatically track picks from scan results."""
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


# Load history on module import
_load_pick_history()


if __name__ == "__main__":
    mcp.run()
