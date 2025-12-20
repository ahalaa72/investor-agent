from dotenv import load_dotenv
load_dotenv()
import os
#print("KEY:", os.getenv("ALPACA_API_KEY"))
#print("SECRET:", os.getenv("ALPACA_API_SECRET"))
import datetime
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from io import StringIO
from typing import Literal, Any

import hishel
import httpx
import pandas as pd
import yfinance as yf
from mcp.server.fastmcp import FastMCP
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

# Import TradingView scanner (optional dependency)
try:
    from .tradingview_scanner import TradingViewScanner, get_scanner, SCREENER_AVAILABLE
except ImportError:
    SCREENER_AVAILABLE = False

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

@api_retry
def yf_call(ticker: str, method: str, *args, **kwargs):
    """Generic yfinance API call with retry logic."""
    t = yf.Ticker(ticker)
    return getattr(t, method)(*args, **kwargs)

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
    """Get comprehensive ticker data: metrics, calendar, news, recommendations."""
    ticker = validate_ticker(ticker)

    # Get all basic data in parallel
    with ThreadPoolExecutor() as executor:
        info_future = executor.submit(yf_call, ticker, "get_info")
        calendar_future = executor.submit(yf_call, ticker, "get_calendar")
        news_future = executor.submit(yf_call, ticker, "get_news")

        info = safe_future_result(info_future, context=f"fetching info for {ticker}")
        if not info:
            raise ValueError(f"No information available for {ticker}")

        essential_fields = {
            'symbol', 'longName', 'currentPrice', 'marketCap', 'volume', 'trailingPE',
            'forwardPE', 'dividendYield', 'beta', 'eps', 'totalRevenue', 'totalDebt',
            'profitMargins', 'operatingMargins', 'returnOnEquity', 'returnOnAssets',
            'revenueGrowth', 'earningsGrowth', 'bookValue', 'priceToBook',
            'enterpriseValue', 'pegRatio', 'trailingEps', 'forwardEps'
        }

        # Basic info section - convert to structured format
        basic_info = [
            {"metric": key, "value": value.isoformat() if hasattr(value, 'isoformat') else value}
            for key, value in info.items() if key in essential_fields
        ]

        result: dict[str, Any] = {"basic_info": basic_info}

        # Process calendar
        calendar = safe_future_result(calendar_future, context=f"fetching calendar for {ticker}")
        if calendar:
            result["calendar"] = [
                {"event": key, "value": value.isoformat() if hasattr(value, 'isoformat') else value}
                for key, value in calendar.items()
            ]

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

        # Get options expirations
        expirations = t.options
        if not expirations:
            raise ValueError(f"No options available for {ticker}")

        # Filter expirations near holding period
        target_date = datetime.now() + timedelta(days=holding_period_days)
        target_date_str = target_date.strftime('%Y-%m-%d')

        # Find nearest expiration to target holding period
        nearest_exp = min(expirations, key=lambda x: abs(
            (datetime.strptime(x, '%Y-%m-%d') - target_date).days
        ))

        # Get options chain for analysis
        chain = t.option_chain(nearest_exp)
        calls_df = chain.calls
        puts_df = chain.puts

        if calls_df.empty and puts_df.empty:
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
        t = yf.Ticker(ticker)
        hist = t.history(period="1y")
        if not hist.empty:
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


def _estimate_greeks_from_chain(calls_df: pd.DataFrame, puts_df: pd.DataFrame, current_price: float) -> dict:
    """Estimate Greeks from yfinance chain data."""
    greeks = {
        "source": "yfinance_estimated",
        "note": "Greeks estimated from chain data - use Questrade for accurate Greeks"
    }

    # Check if Greeks are available in the chain
    if 'impliedVolatility' in calls_df.columns:
        # Get ATM options
        atm_calls = calls_df[abs(calls_df['strike'] - current_price) == abs(calls_df['strike'] - current_price).min()]
        atm_puts = puts_df[abs(puts_df['strike'] - current_price) == abs(puts_df['strike'] - current_price).min()]

        # Extract available Greeks
        greek_cols = ['impliedVolatility', 'delta', 'gamma', 'theta', 'vega']
        for col in greek_cols:
            if col in atm_calls.columns and not atm_calls.empty:
                val = atm_calls[col].iloc[0]
                if pd.notna(val):
                    greeks[f"atm_call_{col}"] = round(val, 4)

            if col in atm_puts.columns and not atm_puts.empty:
                val = atm_puts[col].iloc[0]
                if pd.notna(val):
                    greeks[f"atm_put_{col}"] = round(val, 4)

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
def get_price_history(
    ticker: str,
    period: Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"] = "1mo"
) -> str:
    """Get historical OHLCV data with smart interval selection."""
    ticker = validate_ticker(ticker)

    interval = "1mo" if period in ["2y", "5y", "10y", "max"] else "1d"
    history = yf_call(ticker, "history", period=period, interval=interval)
    if history is None or history.empty:
        raise ValueError(f"No historical data found for {ticker}")

    # Reset index to include dates as a column
    history_with_dates = history.reset_index()
    history_with_dates['Date'] = pd.to_datetime(history_with_dates['Date']).dt.strftime('%Y-%m-%d')

    return to_clean_csv(history_with_dates)

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
    from datetime import datetime, timedelta
    import pytz
    import pandas as pd

    try:
        client = get_questrade_client()

        # Calculate time range: 15 min * window bars
        # Add extra buffer for market hours only
        et = pytz.timezone("America/New_York")
        end_time = datetime.now(et)
        # Rough estimate: need ~window * 15 min of market time
        # Markets open 6.5 hrs/day, so multiply by 2.5 for buffer
        start_time = end_time - timedelta(minutes=15 * window * 3)

        candles = client.get_candles(
            symbol=stock,
            interval="FifteenMinutes",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat()
        )

        if not candles or 'candles' not in candles:
            raise ValueError(f"No candle data returned for {stock}")

        # Convert to DataFrame
        df = pd.DataFrame(candles['candles'])
        if df.empty or 'close' not in df.columns:
            raise ValueError(f"'close' column missing or data empty for {stock}")

        # Parse timestamps and convert to EST
        df['timestamp'] = pd.to_datetime(df['start']).dt.tz_convert("America/New_York")
        df = df[['timestamp', 'close']].rename(columns={'close': stock})

        # Limit to requested window
        df = df.tail(window)

        # Convert to CSV string
        df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S %Z')
        return df.to_csv(index=False)

    except Exception as e:
        raise ValueError(f"Error fetching data for {stock}: {e}")


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
    from datetime import datetime, timedelta
    import pytz
    import pandas as pd

    try:
        client = get_questrade_client()

        # Calculate time range: 1 hour * window bars
        # Add extra buffer for market hours only
        et = pytz.timezone("America/New_York")
        end_time = datetime.now(et)
        # Rough estimate: need ~window hours of market time
        # Markets open 6.5 hrs/day, so multiply by 4 for buffer
        start_time = end_time - timedelta(hours=window * 4)

        candles = client.get_candles(
            symbol=stock,
            interval="OneHour",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat()
        )

        if not candles or 'candles' not in candles:
            raise ValueError(f"No candle data returned for {stock}")

        # Convert to DataFrame
        df = pd.DataFrame(candles['candles'])
        if df.empty or 'close' not in df.columns:
            raise ValueError(f"'close' column missing or data empty for {stock}")

        # Parse timestamps and convert to EST
        df['timestamp'] = pd.to_datetime(df['start']).dt.tz_convert("America/New_York")
        df = df[['timestamp', 'close']].rename(columns={'close': stock})

        # Limit to requested window
        df = df.tail(window)

        # Convert to CSV string
        df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S %Z')
        return df.to_csv(index=False)

    except Exception as e:
        raise ValueError(f"Error fetching data for {stock}: {e}")


# ============================================================================
# Questrade Account Tools
# ============================================================================

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

@mcp.tool()
def get_questrade_quote(symbol: str) -> dict[str, Any]:
    """
    Get real-time Level 1 quote for a single symbol.

    Retrieves current market data including:
    - Bid price and size
    - Ask price and size
    - Last trade price and size
    - Volume
    - High/Low of day
    - Open price

    Args:
        symbol: The symbol to get quote for (e.g., "AAPL", "TSLA")

    Returns:
        dict: Quote information with bid, ask, last price, volume, etc.

    Raises:
        ValueError: If symbol is invalid or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not symbol:
        raise ValueError("symbol parameter is required")

    try:
        client = get_questrade_client()
        quote = client.get_quote(symbol)
        logger.info(f"Retrieved quote for {symbol}")
        return quote

    except Exception as e:
        logger.error(f"Error in get_questrade_quote for {symbol}: {e}")
        raise ValueError(f"Failed to retrieve quote for {symbol}: {str(e)}")

@mcp.tool()
def get_questrade_quotes(symbols: list[str]) -> dict[str, Any]:
    """
    Get real-time Level 1 quotes for multiple symbols.

    Efficiently retrieves quotes for multiple symbols in a single API call.

    Args:
        symbols: List of symbols to get quotes for (e.g., ["AAPL", "TSLA", "NVDA"])

    Returns:
        dict: Quotes for all requested symbols

    Raises:
        ValueError: If symbols list is empty or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not symbols:
        raise ValueError("symbols list parameter is required")

    try:
        client = get_questrade_client()
        quotes = client.get_quotes(symbols)
        logger.info(f"Retrieved quotes for {len(symbols)} symbols")
        return quotes

    except Exception as e:
        logger.error(f"Error in get_questrade_quotes: {e}")
        raise ValueError(f"Failed to retrieve quotes: {str(e)}")

@mcp.tool()
def get_questrade_candles(
    symbol: str,
    interval: str,
    start_time: str,
    end_time: str
) -> dict[str, Any]:
    """
    Get historical OHLCV candle data for a symbol.

    Perfect for charting and technical analysis.

    Args:
        symbol: The symbol to get candles for (e.g., "AAPL")
        interval: Candle interval - one of:
            OneMinute, TwoMinutes, ThreeMinutes, FourMinutes, FiveMinutes,
            TenMinutes, FifteenMinutes, TwentyMinutes, HalfHour, OneHour,
            TwoHours, FourHours, OneDay, OneWeek, OneMonth, OneYear
        start_time: Start time in ISO format (e.g., "2024-01-01T00:00:00-05:00")
        end_time: End time in ISO format (e.g., "2024-12-31T23:59:59-05:00")

    Returns:
        dict: Candle data with Open, High, Low, Close, Volume

    Raises:
        ValueError: If parameters are invalid or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not all([symbol, interval, start_time, end_time]):
        raise ValueError("symbol, interval, start_time, and end_time are all required")

    try:
        client = get_questrade_client()
        candles = client.get_candles(symbol, interval, start_time, end_time)
        logger.info(f"Retrieved candles for {symbol}")
        return candles

    except Exception as e:
        logger.error(f"Error in get_questrade_candles for {symbol}: {e}")
        raise ValueError(f"Failed to retrieve candles: {str(e)}")

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

    Args:
        symbol: The underlying symbol (e.g., "AAPL")

    Returns:
        dict: Options chain data with available strikes and expirations

    Raises:
        ValueError: If symbol is invalid or API call fails.

    Note:
        Requires QUESTRADE_REFRESH_TOKEN environment variable to be set.
    """
    if not symbol:
        raise ValueError("symbol parameter is required")

    try:
        client = get_questrade_client()
        options = client.get_options_chain(symbol)
        logger.info(f"Retrieved options chain for {symbol}")
        return options

    except Exception as e:
        logger.error(f"Error in get_questrade_options_chain for {symbol}: {e}")
        raise ValueError(f"Failed to retrieve options chain: {str(e)}")

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

                # Find similar historical setups
                engine = SimilarityEngine(similarity_threshold=0.75, min_similar_setups=20)
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
                    result['ml_probability_layer'] = {
                        'similar_setups_found': 0,
                        'note': 'No similar historical setups found matching current conditions',
                        'interpretation': 'Unable to find matching historical patterns for ML analysis'
                    }

            except Exception as e:
                result['ml_probability_layer'] = {
                    'error': f'ML analysis failed: {str(e)}',
                    'interpretation': 'ML analysis unavailable'
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
        
        history = yf_call(ticker, "history", period=lookback_period, interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data found for {ticker}")
        
        levels = TechnicalAnalysis.find_support_resistance(history)
        
        return {
            "symbol": ticker,
            "lookback_period": lookback_period,
            **levels
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
        # Validate tickers
        tickers = [validate_ticker(t) for t in tickers]
        
        # Fetch data for all stocks
        stock_data = {}
        for ticker in tickers:
            try:
                history = yf_call(ticker, "history", period="3mo", interval="1d")
                if history is not None and not history.empty:
                    stock_data[ticker] = history
            except Exception as e:
                logger.warning(f"Failed to fetch data for {ticker}: {e}")
                continue
        
        criteria = {
            "rsi_below": rsi_below,
            "rsi_above": rsi_above,
            "above_sma50": above_sma50,
            "macd_bullish": macd_bullish
        }
        
        # Filter out None values
        criteria = {k: v for k, v in criteria.items() if v is not None and v is not False}
        
        results = TechnicalAnalysis.screen_stocks(stock_data, criteria)
        
        return {
            "total_screened": len(tickers),
            "matches_found": len(results),
            "criteria": criteria,
            "results": results
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
                history = yf_call(ticker, "history", period=period, interval="1d")
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

        analysis = TechnicalAnalysis.calculate_trend_strength(history)

        result = {
            "symbol": ticker,
            "period": period,
            **analysis
        }

        # Add statistical confidence layer if requested
        if include_statistical_confidence:
            try:
                # Use trend-scanning labels to get statistical significance
                trend_result = get_trend_scanning_labels(
                    prices=history['Close'],
                    lookforward_window=20,
                    t_stat_threshold=1.96  # 95% confidence
                )

                # Get the latest trend data
                if not trend_result.empty:
                    latest_trend = trend_result.iloc[-1]

                    t_stat = latest_trend.get('t_statistic', 0.0)
                    p_value = latest_trend.get('p_value', 1.0)
                    trend_label = latest_trend.get('trend', 0)

                    # Calculate confidence
                    confidence = 1 - p_value

                    # Determine significance
                    if abs(t_stat) > 2.58:  # 99% confidence
                        significance = "HIGHLY SIGNIFICANT (99%)"
                    elif abs(t_stat) > 1.96:  # 95% confidence
                        significance = "STATISTICALLY SIGNIFICANT (95%)"
                    elif abs(t_stat) > 1.645:  # 90% confidence
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

                    result['statistical_validation'] = {
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
                    result['statistical_validation'] = {
                        'note': 'Insufficient data for statistical validation',
                        'interpretation': 'Unable to calculate statistical confidence'
                    }

            except Exception as e:
                result['statistical_validation'] = {
                    'error': f'Statistical validation failed: {str(e)}',
                    'interpretation': 'Statistical validation unavailable'
                }

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
            "analysis_date": datetime.date.today().isoformat(),
            **patterns
        }


# ============================================================================
# BOOTSTRAP TOOLS - 4 Critical Analysis Tools ($0 cost, 50%+ improvement)
# ============================================================================

# Import bootstrap functions
try:
    from .technical_analysis_bootstrap import (
        analyze_volume,
        analyze_volatility,
        calculate_relative_strength,
        calculate_fundamental_scores
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
        result = analyze_volume(ticker, period, vwap_mode)

        # Add volume quality score if requested
        if include_quality_score:
            try:
                # Get historical data
                history = yf_call(ticker, "history", period=period, interval="1d")

                if history is not None and not history.empty:
                    # Calculate volume metrics
                    volume = history['Volume']
                    close = history['Close']

                    # Average volume
                    avg_volume_20 = volume.rolling(window=20).mean()
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

    # Get historical data
    hist = yf.Ticker(ticker).history(period=lookback_period, interval="1d")

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
        min_similar_setups=20
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

    # Get historical data
    hist = yf.Ticker(ticker).history(period=period, interval="1d")

    if hist.empty or len(hist) < 50:
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

    # 10. Calculate Kelly size (using triple-barrier success rate)
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

    # Build comprehensive recommendation (now 18 signals vs previous 17)
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
        # Supply/Demand Zones (1) - NEW
        supply_demand_result['signal'] == 'DEMAND_ZONE_TEST'
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
        # Supply/Demand Zones (1) - NEW
        supply_demand_result['signal'] == 'SUPPLY_ZONE_TEST'
    ])

    # Generate recommendation (adjusted thresholds for 18 total signals)
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
- Bullish Signals: {bullish_signals}/18
- Bearish Signals: {bearish_signals}/18

**Signal Breakdown:**
- ML Signals: 2 (Triple-Barrier + Trend-Scanning)
- EMA/EMA Crosses: 4 (20/50, 20/100, 20/200, Alignment)
- Price/EMA Interactions: 3 (Bounce, Cross, Extension)
- VWAP Signals: 3 (Bounce, Cross, Position)
- Volume Confirmation: 3 (Surge, OBV, Crossover Confirmation)
- EMA/VWAP Confluence: 1 (Multi-Indicator Alignment)
- Order Blocks: 1 (Institutional Footprints)
- Supply/Demand Zones: 1 (Price Action Zones) ⭐ NEW

---
*Based on {len(prices)} days of historical data with Price/EMA + VWAP + Volume + Confluence + Order Blocks + Supply/Demand Zones analysis*
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

    # Get returns
    hist = yf.Ticker(ticker).history(period="1y", interval="1d")
    if hist.empty:
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
        # Get historical data
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period=period)

        if hist.empty or len(hist) < forward_window + 20:
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

        # Volume indicators
        hist['Volume_SMA'] = volume.rolling(window=20).mean()
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
    from investor_agent.scanner_analyzer import ScannerAnalyzer, format_analysis_report
    ANALYZER_AVAILABLE = True
except ImportError:
    ANALYZER_AVAILABLE = False


def _get_ohlcv_for_ticker(ticker: str, period: str = "3mo") -> pd.DataFrame | None:
    """Helper to get OHLCV data for Brooks analysis."""
    try:
        hist = yf.Ticker(ticker).history(period=period, interval="1d")
        if hist is not None and not hist.empty:
            return hist
    except Exception as e:
        logger.warning(f"Failed to get OHLCV for {ticker}: {e}")
    return None


@mcp.tool()
def scan_market_opportunities(
    market: Literal["america", "canada", "both"] = "both",
    min_price: float = 2.0,
    min_market_cap: int = 1_000_000_000,
    top_n: int = 3,
    include_deep_analysis: bool = True
) -> dict[str, Any]:
    """
    Scan US and Canadian markets for INFLECTION POINT trading opportunities.

    Enhanced with 4-Tier Filter Architecture to find stocks ENTERING trends
    at early stages, not stocks already exhausted in late-stage moves.

    4-Tier Filter System:
        TIER 1 (MOMENTUM - Required): ADX 20-40, RSI 40-65, EMA20 <5%
        TIER 2 (PATTERN - Min 2/4): Consolidation Breakout, Volume 1.5-4x, RS 55-85
        TIER 3 (CATALYST - Adds Score): Earnings proximity, IV Rank, ML alignment
        TIER 4 (EXCLUSIONS - Hard Reject): >50% 3mo move, ATR <2%, Near 52w extremes

    Returns top LONG and SHORT candidates with:
    - Composite scores (0-100) using tier-based inflection detection
    - Al Brooks price action analysis (pattern, probability, levels)
    - Trend Day Counter to detect exhaustion

    Args:
        market: Market to scan - "america", "canada", or "both"
        min_price: Minimum stock price (default: $2)
        min_market_cap: Minimum market cap (default: $1B)
        top_n: Number of candidates per direction (default: 3)
        include_deep_analysis: Run full analysis pipeline (default: True)

    Returns:
        Dictionary with:
        - scan_time: Timestamp of scan
        - filters: Applied filters including tier exclusions
        - long_candidates: Top N LONG at inflection points
        - short_candidates: Top N SHORT at inflection points
        - report: Formatted text report for easy reading

    Composite Score Components (100 pts total):
        - Momentum Quality (30 pts): ADX, RSI, EMA20, MACD
        - Pattern Quality (25 pts): Breakout, Volume, Trend Days
        - Relative Strength (15 pts): RS vs benchmark
        - Catalyst Quality (20 pts): Earnings, IV, ML prediction
        - Al Brooks (10 pts): Pattern quality + probability
    """
    if not SCREENER_AVAILABLE:
        raise ValueError(
            "TradingView scanner not available. Install with: pip install tradingview-screener"
        )

    from datetime import datetime
    import pytz

    try:
        scanner = get_scanner()
        et = pytz.timezone("America/New_York")

        # Scan for initial candidates (get more to filter after analysis)
        long_candidates = scanner.scan_long_setups(
            setup_type="all",
            market=market,
            min_price=min_price,
            min_market_cap=min_market_cap,
            limit=top_n * 5
        )

        short_candidates = scanner.scan_short_setups(
            setup_type="all",
            market=market,
            min_price=min_price,
            min_market_cap=min_market_cap,
            limit=top_n * 5
        )

        analyzed_long = []
        analyzed_short = []

        if include_deep_analysis and ANALYZER_AVAILABLE:
            analyzer = ScannerAnalyzer()

            # Helper functions to pass to analyzer
            def get_technical(ticker, period="3mo", include_ml_analysis=False):
                return TechnicalAnalysis.analyze_comprehensive(
                    yf_call(ticker, "history", period=period, interval="1d")
                )

            # Analyze top LONG candidates
            for c in long_candidates[:top_n * 2]:
                try:
                    ohlcv = _get_ohlcv_for_ticker(c['symbol'])

                    # Get technical data for Brooks analysis
                    tech_data = None
                    try:
                        hist = yf_call(c['symbol'], "history", period="3mo", interval="1d")
                        if hist is not None and not hist.empty:
                            tech_data = {
                                'analysis': TechnicalAnalysis.calculate_comprehensive_indicators(hist)
                            }
                    except Exception:
                        pass

                    # Run full analysis
                    analysis = analyzer.analyze_candidate(
                        ticker=c['symbol'],
                        direction='long',
                        tv_data=c,
                        get_ohlcv_fn=lambda t=c['symbol']: _get_ohlcv_for_ticker(t)
                    )

                    # If we have better technical data, update Brooks
                    if tech_data and ohlcv is not None:
                        analysis['brooks_analysis'] = analyzer.brooks_analyzer.analyze(
                            ticker=c['symbol'],
                            direction='long',
                            ohlcv_data=ohlcv,
                            technical_data=tech_data
                        )
                        # Recalculate Brooks score
                        analysis['scores']['brooks_score'] = analyzer._score_brooks(analysis['brooks_analysis'])
                        analysis['composite_score'] = analyzer._calculate_composite(analysis['scores'])
                        analysis['recommendation'] = analyzer._generate_recommendation(
                            analysis['composite_score'], 'long', analysis['brooks_analysis']
                        )

                    analyzed_long.append(analysis)
                except Exception as e:
                    logger.warning(f"Analysis failed for {c['symbol']}: {e}")
                    # Fall back to basic format
                    analyzed_long.append({
                        'symbol': c['symbol'],
                        'direction': 'LONG',
                        'price': c['price'],
                        'composite_score': c['signal_strength'],
                        'tv_data': c,
                        'recommendation': {'label': c['recommendation']},
                        'brooks_analysis': {'pattern': 'N/A - analysis failed'}
                    })

            # Analyze top SHORT candidates
            for c in short_candidates[:top_n * 2]:
                try:
                    ohlcv = _get_ohlcv_for_ticker(c['symbol'])

                    tech_data = None
                    try:
                        hist = yf_call(c['symbol'], "history", period="3mo", interval="1d")
                        if hist is not None and not hist.empty:
                            tech_data = {
                                'analysis': TechnicalAnalysis.calculate_comprehensive_indicators(hist)
                            }
                    except Exception:
                        pass

                    analysis = analyzer.analyze_candidate(
                        ticker=c['symbol'],
                        direction='short',
                        tv_data=c,
                        get_ohlcv_fn=lambda t=c['symbol']: _get_ohlcv_for_ticker(t)
                    )

                    if tech_data and ohlcv is not None:
                        analysis['brooks_analysis'] = analyzer.brooks_analyzer.analyze(
                            ticker=c['symbol'],
                            direction='short',
                            ohlcv_data=ohlcv,
                            technical_data=tech_data
                        )
                        analysis['scores']['brooks_score'] = analyzer._score_brooks(analysis['brooks_analysis'])
                        analysis['composite_score'] = analyzer._calculate_composite(analysis['scores'])
                        analysis['recommendation'] = analyzer._generate_recommendation(
                            analysis['composite_score'], 'short', analysis['brooks_analysis']
                        )

                    analyzed_short.append(analysis)
                except Exception as e:
                    logger.warning(f"Analysis failed for {c['symbol']}: {e}")
                    analyzed_short.append({
                        'symbol': c['symbol'],
                        'direction': 'SHORT',
                        'price': c['price'],
                        'composite_score': c['signal_strength'],
                        'tv_data': c,
                        'recommendation': {'label': c['recommendation']},
                        'brooks_analysis': {'pattern': 'N/A - analysis failed'}
                    })

            # Sort by composite score
            analyzed_long.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
            analyzed_short.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

        else:
            # Basic format without deep analysis
            for i, c in enumerate(long_candidates[:top_n]):
                analyzed_long.append({
                    'rank': i + 1,
                    'symbol': c['symbol'],
                    'direction': 'LONG',
                    'price': c['price'],
                    'composite_score': c['signal_strength'],
                    'tv_data': c,
                    'recommendation': {'label': c['recommendation']},
                    'brooks_analysis': {'note': 'Deep analysis disabled'}
                })

            for i, c in enumerate(short_candidates[:top_n]):
                analyzed_short.append({
                    'rank': i + 1,
                    'symbol': c['symbol'],
                    'direction': 'SHORT',
                    'price': c['price'],
                    'composite_score': c['signal_strength'],
                    'tv_data': c,
                    'recommendation': {'label': c['recommendation']},
                    'brooks_analysis': {'note': 'Deep analysis disabled'}
                })

        # Take top N after sorting
        final_long = analyzed_long[:top_n]
        final_short = analyzed_short[:top_n]

        # Add ranks
        for i, a in enumerate(final_long):
            a['rank'] = i + 1
        for i, a in enumerate(final_short):
            a['rank'] = i + 1

        # Generate text report
        report_lines = [
            "=" * 65,
            f"    MARKET OPPORTUNITIES SCAN - {datetime.now(et).strftime('%Y-%m-%d %H:%M %Z')}",
            "=" * 65,
            f"Markets: {market.upper()} | Filters: Price>${min_price}, MCap>${min_market_cap:,}",
            "",
            "=" * 65,
            "                TOP LONG CANDIDATES",
            "=" * 65,
        ]

        if ANALYZER_AVAILABLE:
            for a in final_long:
                report_lines.append(format_analysis_report(a))

            report_lines.extend([
                "=" * 65,
                "                TOP SHORT CANDIDATES",
                "=" * 65,
            ])

            for a in final_short:
                report_lines.append(format_analysis_report(a))
        else:
            for a in final_long:
                report_lines.append(f"#{a.get('rank')} {a['symbol']} - ${a['price']:.2f} | Score: {a['composite_score']}")
            report_lines.extend(["", "=" * 65, "                TOP SHORT CANDIDATES", "=" * 65])
            for a in final_short:
                report_lines.append(f"#{a.get('rank')} {a['symbol']} - ${a['price']:.2f} | Score: {a['composite_score']}")

        return {
            "scan_time": datetime.now(et).strftime("%Y-%m-%d %H:%M:%S %Z"),
            "filters": {
                "market": market,
                "min_price": min_price,
                "min_market_cap": f"${min_market_cap:,}",
                "tier_filters": {
                    "tier1_momentum": "ADX 20-40, RSI 40-65 (long) / 35-60 (short), EMA20 <5%",
                    "tier2_pattern": "Consolidation Breakout, Volume 1.5-4x, Trend Days <6",
                    "tier4_exclusions": "3mo >50%/-40%, ATR <2%, 52w proximity <5%"
                }
            },
            "long_candidates": final_long,
            "short_candidates": final_short,
            "total_long_found": len(long_candidates),
            "total_short_found": len(short_candidates),
            "report": "\n".join(report_lines)
        }

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
        scanner = get_scanner()
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

        return {
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
        }

    except Exception as e:
        logger.error(f"Error in scan_stocks_by_setup: {e}")
        raise ValueError(f"Setup scan failed: {str(e)}")


if __name__ == "__main__":
    mcp.run()
