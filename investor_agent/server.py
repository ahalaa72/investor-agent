from dotenv import load_dotenv
load_dotenv()
import os
#print("KEY:", os.getenv("ALPACA_API_KEY"))
#print("SECRET:", os.getenv("ALPACA_API_SECRET"))
import datetime
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
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

        info = info_future.result()
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
        calendar = calendar_future.result()
        if calendar:
            result["calendar"] = [
                {"event": key, "value": value.isoformat() if hasattr(value, 'isoformat') else value}
                for key, value in calendar.items()
            ]

        # Process news
        news_items = news_future.result()
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

        recommendations = recommendations_future.result()
        if isinstance(recommendations, pd.DataFrame) and not recommendations.empty:
            result["recommendations"] = to_clean_csv(recommendations.head(max_recommendations))

        upgrades = upgrades_future.result()
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

        # Parallel fetch with error handling
        with ThreadPoolExecutor() as executor:
            chains = [
                chain.assign(expiryDate=expiry)
                for chain, expiry in zip(
                    executor.map(lambda exp: get_options_chain(ticker_symbol, exp, option_type), valid_expirations),
                    valid_expirations
                ) if chain is not None
            ]

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
            df = future.result()
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

        inst_holders = inst_future.result()
        fund_holders = fund_future.result()

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
    Fetch 15-minute historical stock bars using Alpaca API.

    Args:
        stock: Stock ticker symbol
        window: Number of 15-minute bars to fetch (default: 200)

    Returns:
        CSV string with timestamp and close price data in EST timezone
    """
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    import os

    try:
        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_API_SECRET')

        if not api_key or not api_secret:
            raise ValueError("ALPACA_API_KEY and ALPACA_API_SECRET environment variables must be set")

        timeframe = TimeFrame(15, TimeFrameUnit.Minute)
        client = StockHistoricalDataClient(api_key, api_secret)
        request = StockBarsRequest(
            symbol_or_symbols=stock,
            timeframe=timeframe,
            limit=window
        )

        df_raw = client.get_stock_bars(request).df

        if df_raw.empty or 'close' not in df_raw.columns:
            raise ValueError(f"'close' column missing or data empty for {stock}")

        df = df_raw['close']
        df.index = df_raw.index.get_level_values('timestamp').tz_convert("America/New_York")
        df = df.to_frame(name=f'{stock}')

        # Convert to CSV string
        df_reset = df.reset_index()
        df_reset['timestamp'] = df_reset['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S %Z')
        return df_reset.to_csv(index=False)

    except Exception as e:
        raise ValueError(f"Error fetching data for {stock}: {e}")


@mcp.tool()
def fetch_intraday_1h(stock: str, window: int = 200) -> str:
    """
    Fetch 1-Hour historical stock bars using Alpaca API.

    Args:
        stock: Stock ticker symbol
        window: Number of 15-minute bars to fetch (default: 200)

    Returns:
        CSV string with timestamp and close price data in EST timezone
    """
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    import os

    try:
        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_API_SECRET')

        if not api_key or not api_secret:
            raise ValueError("ALPACA_API_KEY and ALPACA_API_SECRET environment variables must be set")

        timeframe = TimeFrame(1, TimeFrameUnit.Hour)
        client = StockHistoricalDataClient(api_key, api_secret)
        request = StockBarsRequest(
            symbol_or_symbols=stock,
            timeframe=timeframe,
            limit=window
        )

        df_raw = client.get_stock_bars(request).df

        if df_raw.empty or 'close' not in df_raw.columns:
            raise ValueError(f"'close' column missing or data empty for {stock}")

        df = df_raw['close']
        df.index = df_raw.index.get_level_values('timestamp').tz_convert("America/New_York")
        df = df.to_frame(name=f'{stock}')

        # Convert to CSV string
        df_reset = df.reset_index()
        df_reset['timestamp'] = df_reset['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S %Z')
        return df_reset.to_csv(index=False)

    except Exception as e:
        raise ValueError(f"Error fetching data for {stock}: {e}")





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
        period: Literal["3mo", "6mo", "1y", "2y"] = "6mo"
    ) -> dict[str, Any]:
        """Perform comprehensive technical analysis with RSI, MACD, Bollinger Bands, Moving Averages, and Stochastic indicators.
        
        Returns detailed technical indicators including:
        - RSI (Relative Strength Index) with overbought/oversold signals
        - MACD (Moving Average Convergence Divergence) with trend analysis
        - Bollinger Bands with price position
        - Multiple Moving Averages (SMA 20/50/200, EMA 20)
        - Stochastic Oscillator
        """
        ticker = validate_ticker(ticker)
        
        history = yf_call(ticker, "history", period=period, interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data found for {ticker}")
        
        indicators = TechnicalAnalysis.calculate_comprehensive_indicators(history)
        
        return {
            "symbol": ticker,
            "period": period,
            "data_points": len(history),
            "analysis": indicators
        }
    
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
        period: Literal["3mo", "6mo", "1y"] = "6mo"
    ) -> dict[str, Any]:
        """Analyze trend strength and momentum for a stock.
        
        Calculates a comprehensive trend strength score (0-100) based on:
        - RSI momentum (25 points)
        - MACD trend direction (25 points)
        - Price vs moving averages (30 points)
        - Bollinger Bands position (20 points)
        
        Returns:
        - Trend strength score
        - Overall assessment (Strong Bullish, Moderate Bullish, Weak, Bearish)
        - Detailed analysis points
        - Full indicator breakdown
        """
        ticker = validate_ticker(ticker)
        
        history = yf_call(ticker, "history", period=period, interval="1d")
        if history is None or history.empty:
            raise ValueError(f"No historical data found for {ticker}")
        
        analysis = TechnicalAnalysis.calculate_trend_strength(history)
        
        return {
            "symbol": ticker,
            "period": period,
            **analysis
        }
    
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
        vwap_mode: Literal["session", "rolling", "anchored"] = "session"
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
        
        Returns:
        - VWAP (Volume Weighted Average Price) - calculated per selected mode
        - Volume Profile (POC - Point of Control)
        - Relative Volume (current vs 20-day average)
        - OBV trend (Accumulation/Distribution)
        - MFI (Money Flow Index)
        - Accumulation/Distribution Line
        
        Use before EVERY trade to confirm the move is real.
        """
        ticker = validate_ticker(ticker)
        return analyze_volume(ticker, period, vwap_mode)
    
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
# QUESTRADE API TOOLS
# ============================================================================

# Check Questrade API availability
try:
    from questrade_api import Questrade
    _questrade_available = True
except ImportError:
    _questrade_available = False
    logger.warning("Questrade API not available - install with: pip install questrade-api")


def get_questrade_client() -> Questrade:
    """Initialize Questrade client with refresh token from environment."""
    refresh_token = os.getenv('QUESTRADE_REFRESH_TOKEN')
    if not refresh_token:
        raise ValueError(
            "QUESTRADE_REFRESH_TOKEN environment variable not set. "
            "Get your token from: https://login.questrade.com/APIAccess/UserApps.aspx"
        )
    return Questrade(refresh_token=refresh_token)


def resolve_symbol_to_id(qt: Questrade, symbol: str) -> dict:
    """Resolve a symbol string to its ID and info."""
    symbol = symbol.upper().strip()
    result = qt.symbols_search(prefix=symbol)

    if not result.get('symbols'):
        raise ValueError(f"Symbol '{symbol}' not found")

    # Find exact match or first result
    for sym in result['symbols']:
        if sym.get('symbol') == symbol:
            return sym

    # Return first result if no exact match
    first_result = result['symbols'][0]
    logger.warning(f"Exact match not found for '{symbol}', using '{first_result.get('symbol')}'")
    return first_result


if _questrade_available:

    @mcp.tool()
    def questrade_get_quote(symbol: str) -> dict:
        """Get real-time quote for a single symbol from Questrade.

        Returns:
        - Current bid/ask prices
        - Last trade price and volume
        - Day high/low
        - Open/close prices
        - Market data timestamp
        """
        qt = get_questrade_client()
        sym_info = resolve_symbol_to_id(qt, symbol)
        symbol_id = sym_info['symbolId']

        result = qt.markets_quotes(ids=str(symbol_id))

        if not result.get('quotes'):
            raise ValueError(f"No quote data available for {symbol}")

        quote = result['quotes'][0]

        return {
            "symbol": quote.get('symbol'),
            "symbolId": quote.get('symbolId'),
            "lastTradePrice": quote.get('lastTradePrice'),
            "lastTradeSize": quote.get('lastTradeSize'),
            "lastTradeTime": quote.get('lastTradeTime'),
            "bidPrice": quote.get('bidPrice'),
            "bidSize": quote.get('bidSize'),
            "askPrice": quote.get('askPrice'),
            "askSize": quote.get('askSize'),
            "openPrice": quote.get('openPrice'),
            "highPrice": quote.get('highPrice'),
            "lowPrice": quote.get('lowPrice'),
            "closePrice": quote.get('previousClose'),
            "volume": quote.get('volume'),
            "delay": quote.get('delay', 0),
            "timestamp": quote.get('lastTradeTick')
        }

    @mcp.tool()
    def questrade_get_quotes(symbols: list[str]) -> list[dict]:
        """Get real-time quotes for multiple symbols from Questrade.

        Args:
            symbols: List of ticker symbols (e.g., ['AAPL', 'MSFT', 'TSLA'])

        Returns list of quote dictionaries with pricing and volume data.
        """
        qt = get_questrade_client()

        # Resolve all symbols to IDs
        symbol_ids = []
        symbol_map = {}
        for symbol in symbols:
            try:
                sym_info = resolve_symbol_to_id(qt, symbol)
                symbol_id = sym_info['symbolId']
                symbol_ids.append(str(symbol_id))
                symbol_map[symbol_id] = symbol
            except Exception as e:
                logger.warning(f"Failed to resolve {symbol}: {e}")
                continue

        if not symbol_ids:
            raise ValueError("No valid symbols could be resolved")

        # Get quotes for all symbols
        ids_str = ','.join(symbol_ids)
        result = qt.markets_quotes(ids=ids_str)

        quotes = []
        for quote in result.get('quotes', []):
            quotes.append({
                "symbol": quote.get('symbol'),
                "symbolId": quote.get('symbolId'),
                "lastTradePrice": quote.get('lastTradePrice'),
                "bidPrice": quote.get('bidPrice'),
                "askPrice": quote.get('askPrice'),
                "volume": quote.get('volume'),
                "highPrice": quote.get('highPrice'),
                "lowPrice": quote.get('lowPrice'),
                "openPrice": quote.get('openPrice'),
                "lastTradeTime": quote.get('lastTradeTime')
            })

        return quotes

    @mcp.tool()
    def questrade_get_candles(
        symbol: str,
        interval: Literal["OneMinute", "TwoMinutes", "ThreeMinutes", "FourMinutes", "FiveMinutes",
                          "TenMinutes", "FifteenMinutes", "TwentyMinutes", "HalfHour",
                          "OneHour", "TwoHours", "FourHours", "OneDay", "OneWeek", "OneMonth", "OneYear"] = "OneDay",
        start_date: str | None = None,
        end_date: str | None = None,
        max_candles: int = 100
    ) -> str:
        """Get OHLCV candlestick data from Questrade.

        Args:
            symbol: Stock ticker symbol
            interval: Candle interval (OneMinute to OneYear)
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)
            max_candles: Maximum number of candles to return (default 100)

        Returns CSV with: Date, Open, High, Low, Close, Volume
        """
        qt = get_questrade_client()
        sym_info = resolve_symbol_to_id(qt, symbol)
        symbol_id = sym_info['symbolId']

        # Prepare time parameters
        kwargs = {'interval': interval}

        if start_date:
            validate_date(start_date)
            kwargs['startTime'] = f"{start_date}T00:00:00-05:00"

        if end_date:
            validate_date(end_date)
            kwargs['endTime'] = f"{end_date}T23:59:59-05:00"

        if start_date and end_date:
            validate_date_range(start_date, end_date)

        result = qt.markets_candles(symbol_id, **kwargs)

        if not result.get('candles'):
            raise ValueError(f"No candle data available for {symbol}")

        # Convert to DataFrame
        candles = result['candles']
        df = pd.DataFrame(candles)

        # Rename columns to standard names
        df = df.rename(columns={
            'start': 'Date',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })

        # Convert date format
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d %H:%M:%S')

        # Select relevant columns
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]

        # Limit number of candles
        if len(df) > max_candles:
            df = df.tail(max_candles)

        return to_clean_csv(df)

    @mcp.tool()
    def questrade_search_symbols(query: str, max_results: int = 10) -> list[dict]:
        """Search for symbols on Questrade by name or ticker prefix.

        Args:
            query: Symbol prefix or name to search for (e.g., 'AAPL', 'Apple')
            max_results: Maximum number of results to return

        Returns list of matching symbols with details.
        """
        qt = get_questrade_client()
        query = query.upper().strip()

        result = qt.symbols_search(prefix=query)

        if not result.get('symbols'):
            return []

        symbols = []
        for sym in result['symbols'][:max_results]:
            symbols.append({
                "symbol": sym.get('symbol'),
                "symbolId": sym.get('symbolId'),
                "description": sym.get('description'),
                "securityType": sym.get('securityType'),
                "listingExchange": sym.get('listingExchange'),
                "currency": sym.get('currency'),
                "isTradable": sym.get('isTradable', False),
                "isQuotable": sym.get('isQuotable', False)
            })

        return symbols

    @mcp.tool()
    def questrade_get_symbol_info(symbol: str) -> dict:
        """Get detailed information about a specific symbol from Questrade.

        Returns:
        - Symbol ID and name
        - Security type (Stock, Option, etc.)
        - Exchange and currency
        - Trading status
        - Description
        """
        qt = get_questrade_client()
        sym_info = resolve_symbol_to_id(qt, symbol)

        return {
            "symbol": sym_info.get('symbol'),
            "symbolId": sym_info.get('symbolId'),
            "description": sym_info.get('description'),
            "securityType": sym_info.get('securityType'),
            "listingExchange": sym_info.get('listingExchange'),
            "currency": sym_info.get('currency'),
            "isTradable": sym_info.get('isTradable', False),
            "isQuotable": sym_info.get('isQuotable', False),
            "hasOptions": sym_info.get('hasOptions', False)
        }

    @mcp.tool()
    def questrade_get_markets() -> list[dict]:
        """Get list of available markets from Questrade.

        Returns information about all trading markets and venues.
        """
        qt = get_questrade_client()
        result = qt.markets

        markets = []
        for market in result.get('markets', []):
            markets.append({
                "name": market.get('name'),
                "tradingVenues": market.get('tradingVenues', []),
                "defaultTradingVenue": market.get('defaultTradingVenue'),
                "primaryOrderRoutes": market.get('primaryOrderRoutes', []),
                "secondaryOrderRoutes": market.get('secondaryOrderRoutes', [])
            })

        return markets

    @mcp.tool()
    def questrade_get_orders(
        account_number: str,
        status_filter: Literal["All", "Open", "Closed"] = "Open",
        start_date: str | None = None,
        end_date: str | None = None
    ) -> list[dict]:
        """Get orders for a Questrade account.

        Args:
            account_number: Questrade account number
            status_filter: Filter by order status (All, Open, Closed)
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)

        Returns list of orders with details.
        """
        qt = get_questrade_client()

        kwargs = {}
        if start_date:
            validate_date(start_date)
            kwargs['startTime'] = f"{start_date}T00:00:00-05:00"

        if end_date:
            validate_date(end_date)
            kwargs['endTime'] = f"{end_date}T23:59:59-05:00"

        if start_date and end_date:
            validate_date_range(start_date, end_date)

        if status_filter != "All":
            kwargs['stateFilter'] = status_filter

        result = qt.account_orders(account_number, **kwargs)

        orders = []
        for order in result.get('orders', []):
            orders.append({
                "orderId": order.get('id'),
                "symbol": order.get('symbol'),
                "symbolId": order.get('symbolId'),
                "totalQuantity": order.get('totalQuantity'),
                "filledQuantity": order.get('filledQuantity'),
                "orderType": order.get('orderType'),
                "side": order.get('side'),
                "price": order.get('limitPrice'),
                "state": order.get('state'),
                "creationTime": order.get('creationTime'),
                "updateTime": order.get('updateTime'),
                "timeInForce": order.get('timeInForce')
            })

        return orders

    @mcp.tool()
    def questrade_get_order(account_number: str, order_id: int) -> dict:
        """Get details of a specific order from Questrade.

        Args:
            account_number: Questrade account number
            order_id: Order ID to retrieve

        Returns detailed order information.
        """
        qt = get_questrade_client()
        result = qt.account_order(account_number, order_id)

        if not result.get('orders'):
            raise ValueError(f"Order {order_id} not found")

        order = result['orders'][0]

        return {
            "orderId": order.get('id'),
            "symbol": order.get('symbol'),
            "symbolId": order.get('symbolId'),
            "totalQuantity": order.get('totalQuantity'),
            "filledQuantity": order.get('filledQuantity'),
            "openQuantity": order.get('openQuantity'),
            "canceledQuantity": order.get('canceledQuantity'),
            "orderType": order.get('orderType'),
            "side": order.get('side'),
            "limitPrice": order.get('limitPrice'),
            "stopPrice": order.get('stopPrice'),
            "state": order.get('state'),
            "rejectionReason": order.get('rejectionReason'),
            "creationTime": order.get('creationTime'),
            "updateTime": order.get('updateTime'),
            "timeInForce": order.get('timeInForce'),
            "legs": order.get('orderLegs', []),
            "strategyType": order.get('strategyType'),
            "commissionCharged": order.get('commissionCharged')
        }

    @mcp.tool()
    def questrade_get_executions(
        account_number: str,
        start_date: str,
        end_date: str | None = None
    ) -> list[dict]:
        """Get trade execution history from Questrade.

        Args:
            account_number: Questrade account number
            start_date: Start date in YYYY-MM-DD format (required)
            end_date: End date in YYYY-MM-DD format (optional, defaults to today)

        Returns list of executed trades with details.
        """
        qt = get_questrade_client()

        validate_date(start_date)
        kwargs = {'startTime': f"{start_date}T00:00:00-05:00"}

        if end_date:
            validate_date(end_date)
            kwargs['endTime'] = f"{end_date}T23:59:59-05:00"
            validate_date_range(start_date, end_date)
        else:
            kwargs['endTime'] = datetime.datetime.now().strftime('%Y-%m-%dT23:59:59-05:00')

        result = qt.account_executions(account_number, **kwargs)

        executions = []
        for execution in result.get('executions', []):
            executions.append({
                "executionId": execution.get('id'),
                "orderId": execution.get('orderId'),
                "symbol": execution.get('symbol'),
                "symbolId": execution.get('symbolId'),
                "quantity": execution.get('quantity'),
                "side": execution.get('side'),
                "price": execution.get('price'),
                "timestamp": execution.get('timestamp'),
                "notes": execution.get('notes'),
                "venue": execution.get('venue'),
                "totalCost": execution.get('totalCost'),
                "orderPlacementCommission": execution.get('orderPlacementCommission'),
                "commission": execution.get('commission'),
                "executionFee": execution.get('executionFee'),
                "secFee": execution.get('secFee'),
                "netCost": execution.get('netCost')
            })

        return executions

    @mcp.tool()
    def questrade_get_activities(
        account_number: str,
        start_date: str,
        end_date: str | None = None,
        activity_type: Literal["All", "Trades", "NonTrades", "Dividends", "Deposits", "Withdrawals"] = "All"
    ) -> list[dict]:
        """Get account activity history from Questrade.

        Args:
            account_number: Questrade account number
            start_date: Start date in YYYY-MM-DD format (required)
            end_date: End date in YYYY-MM-DD format (optional, defaults to today)
            activity_type: Filter by activity type

        Returns list of account activities.
        """
        qt = get_questrade_client()

        validate_date(start_date)
        kwargs = {'startTime': f"{start_date}T00:00:00-05:00"}

        if end_date:
            validate_date(end_date)
            kwargs['endTime'] = f"{end_date}T23:59:59-05:00"
            validate_date_range(start_date, end_date)
        else:
            kwargs['endTime'] = datetime.datetime.now().strftime('%Y-%m-%dT23:59:59-05:00')

        result = qt.account_activities(account_number, **kwargs)

        activities = result.get('activities', [])

        # Filter by activity type if specified
        if activity_type != "All":
            type_filter = activity_type.lower()
            activities = [a for a in activities if type_filter in a.get('type', '').lower()]

        formatted_activities = []
        for activity in activities:
            formatted_activities.append({
                "type": activity.get('type'),
                "tradeDate": activity.get('tradeDate'),
                "transactionDate": activity.get('transactionDate'),
                "settlementDate": activity.get('settlementDate'),
                "action": activity.get('action'),
                "symbol": activity.get('symbol'),
                "symbolId": activity.get('symbolId'),
                "description": activity.get('description'),
                "currency": activity.get('currency'),
                "quantity": activity.get('quantity'),
                "price": activity.get('price'),
                "grossAmount": activity.get('grossAmount'),
                "commission": activity.get('commission'),
                "netAmount": activity.get('netAmount')
            })

        return formatted_activities

    @mcp.tool()
    def questrade_get_options_chain(symbol: str) -> list[dict]:
        """Get options chain for a symbol from Questrade.

        Returns list of option expiry dates and details for the underlying symbol.
        """
        qt = get_questrade_client()
        sym_info = resolve_symbol_to_id(qt, symbol)
        symbol_id = sym_info['symbolId']

        result = qt.symbol_options(symbol_id)

        if not result.get('optionChain'):
            raise ValueError(f"No options chain available for {symbol}")

        chain = []
        for option in result['optionChain']:
            chain.append({
                "expiryDate": option.get('expiryDate'),
                "description": option.get('description'),
                "listingExchange": option.get('listingExchange'),
                "optionExerciseType": option.get('optionExerciseType'),
                "chainPerRoot": option.get('chainPerRoot', [])
            })

        return chain

    @mcp.tool()
    def questrade_get_option_quotes(
        option_ids: list[int] | None = None,
        underlying_symbol: str | None = None
    ) -> list[dict]:
        """Get option quotes with Greeks from Questrade.

        Args:
            option_ids: List of specific option IDs to retrieve (optional)
            underlying_symbol: Get all options for underlying symbol (optional)

        Note: Must provide either option_ids OR underlying_symbol.

        Returns list of option quotes with Greeks (delta, gamma, theta, vega, rho).
        """
        qt = get_questrade_client()

        if option_ids:
            result = qt.markets_options(optionIds=option_ids)
        elif underlying_symbol:
            # Get symbol ID first
            sym_info = resolve_symbol_to_id(qt, underlying_symbol)
            symbol_id = sym_info['symbolId']

            # Get options chain to find option IDs
            chain_result = qt.symbol_options(symbol_id)
            if not chain_result.get('optionChain'):
                raise ValueError(f"No options available for {underlying_symbol}")

            # Extract option IDs from chain (limited to first 20 to avoid overload)
            option_ids = []
            for option in chain_result['optionChain'][:5]:  # Limit to first 5 expiry dates
                for root in option.get('chainPerRoot', []):
                    for strike in root.get('chainPerStrikePrice', [])[:10]:  # Limit strikes per expiry
                        option_ids.extend([opt.get('symbolId') for opt in strike.get('callSymbolId', [])])
                        option_ids.extend([opt.get('symbolId') for opt in strike.get('putSymbolId', [])])

            if not option_ids:
                raise ValueError(f"No option IDs found for {underlying_symbol}")

            result = qt.markets_options(optionIds=option_ids[:50])  # Limit to 50 options
        else:
            raise ValueError("Must provide either option_ids or underlying_symbol")

        quotes = []
        for quote in result.get('optionQuotes', []):
            quotes.append({
                "underlying": quote.get('underlying'),
                "underlyingId": quote.get('underlyingId'),
                "symbol": quote.get('symbol'),
                "symbolId": quote.get('symbolId'),
                "bidPrice": quote.get('bidPrice'),
                "askPrice": quote.get('askPrice'),
                "lastTradePrice": quote.get('lastTradePrice'),
                "openPrice": quote.get('openPrice'),
                "highPrice": quote.get('highPrice'),
                "lowPrice": quote.get('lowPrice'),
                "volume": quote.get('volume'),
                "openInterest": quote.get('openInterest'),
                "delta": quote.get('delta'),
                "gamma": quote.get('gamma'),
                "theta": quote.get('theta'),
                "vega": quote.get('vega'),
                "rho": quote.get('rho'),
                "volatility": quote.get('volatility'),
                "expiryDate": quote.get('expiryDate')
            })

        return quotes


if __name__ == "__main__":
    mcp.run()
