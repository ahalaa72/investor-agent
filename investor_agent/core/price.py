"""
Price fetching with Questrade-first strategy, yfinance fallback.

FIX R-4: Removed _get_current_price ($100 fallback). Use get_current_price_questrade_first everywhere.
"""
import logging
from typing import Literal, Any

import numpy as np
import pandas as pd
import yfinance as yf

from .http import api_retry
from .config import ESSENTIAL_OPTIONS_COLUMNS

logger = logging.getLogger(__name__)


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


def get_price_history_questrade_first(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """
    Get historical price data with Questrade as primary source, yfinance as fallback.

    This ensures we get accurate split-adjusted data for stocks that have had splits.
    """
    from datetime import datetime, timedelta
    from ..questrade import get_questrade_client

    # Map period to days
    period_days = {
        '1d': 1, '5d': 5, '1mo': 30, '3mo': 90, '6mo': 180,
        '1y': 365, '2y': 730, '5y': 1825, 'ytd': (datetime.now() - datetime(datetime.now().year, 1, 1)).days
    }
    days = period_days.get(period, 90)

    # Try Questrade first
    try:
        qt_client = get_questrade_client()

        symbol_info = qt_client.get_symbol_info(ticker)
        if symbol_info and symbol_info.get('symbols'):
            symbol_id = symbol_info['symbols'][0]['symbolId']

            end_time = datetime.now()
            start_time = end_time - timedelta(days=days + 10)

            if days <= 5:
                interval = "FifteenMinutes"
            elif days <= 30:
                interval = "OneHour"
            else:
                interval = "OneDay"

            start_str = start_time.strftime('%Y-%m-%dT%H:%M:%S-05:00')
            end_str = end_time.strftime('%Y-%m-%dT%H:%M:%S-05:00')

            candles = qt_client.get_candles(ticker, interval, start_str, end_str)

            if candles and candles.get('candles'):
                df = pd.DataFrame(candles['candles'])
                df = df.rename(columns={
                    'start': 'Date', 'open': 'Open', 'high': 'High',
                    'low': 'Low', 'close': 'Close', 'volume': 'Volume'
                })
                df['Date'] = pd.to_datetime(df['Date'], utc=True)
                df.set_index('Date', inplace=True)
                df.index = df.index.tz_convert(None)

                if len(df) >= 10:
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

    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    return df


def get_current_price_questrade_first(ticker: str) -> float:
    """
    Get current price with Questrade as primary source, yfinance as fallback.

    Raises ValueError if no price is available (never returns fake defaults).
    """
    from ..questrade import get_questrade_client

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


def to_clean_csv(df: pd.DataFrame, preserve_columns: set | None = None) -> str:
    """Clean DataFrame by removing empty columns and convert to CSV string."""
    preserve = preserve_columns or set()

    mask = (
        (df.notna().any() & (df != '').any() & ((df != 0).any() | (df.dtypes == 'object'))) |
        df.columns.isin(preserve)
    )
    return df.loc[:, mask].fillna('').to_csv(index=False)


def df_to_clean_dict(df: pd.DataFrame, preserve_columns: set | None = None) -> dict:
    """Clean DataFrame and convert to list of record dicts."""
    preserve = preserve_columns or set()

    mask = (
        (df.notna().any() & (df != '').any() & ((df != 0).any() | (df.dtypes == 'object')))
        | df.columns.isin(preserve)
    )
    cleaned = df.loc[:, mask].copy()
    for col in cleaned.columns:
        if pd.api.types.is_datetime64_any_dtype(cleaned[col]):
            cleaned[col] = cleaned[col].apply(
                lambda x: x.isoformat() if pd.notna(x) else None
            )
    records = cleaned.where(cleaned.notna(), None).to_dict('records')
    return convert_numpy_types({"data": records, "count": len(records)})


def format_date_string(date_str: str) -> str | None:
    """Parse and format date string to YYYY-MM-DD format."""
    import datetime
    try:
        return datetime.datetime.fromisoformat(date_str.replace("Z", "")).strftime("%Y-%m-%d")
    except Exception:
        return date_str[:10] if date_str else None


def get_ticker_info_questrade_first(ticker: str) -> dict[str, Any]:
    """
    Get ticker info using Questrade as primary source, Yahoo Finance as fallback.
    Returns a unified dict with metrics from best available source.
    """
    from ..questrade import get_questrade_client

    result = {
        "source": "none",
        "questrade_data": {},
        "yfinance_data": {},
        "merged": {}
    }

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
        client = get_questrade_client()
        if client:
            symbol_info = client.get_symbol_info(ticker)
            quote = client.get_quote(ticker)

            if symbol_info and symbol_info.get('symbols'):
                sym = symbol_info['symbols'][0]
                result["questrade_data"] = sym

                for q_field, u_field in questrade_to_unified.items():
                    if q_field in sym and sym[q_field] is not None:
                        result["merged"][u_field] = sym[q_field]

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
                result["merged"] = yf_info.copy()
                result["source"] = "yfinance"
                logger.info(f"Got ticker info for {ticker} from Yahoo Finance (Questrade unavailable)")
            else:
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
