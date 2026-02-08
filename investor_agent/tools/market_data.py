"""
Market data tools: market movers, fear/greed, Google Trends, ticker data, options chains.
"""
import logging
import datetime
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from typing import Literal, Any

import pandas as pd
import yfinance as yf

from ..core.config import BROWSER_HEADERS, ESSENTIAL_OPTIONS_COLUMNS, TREND_TIMEFRAMES
from ..core.http import api_retry, fetch_text, fetch_json, fetch_json_sync, safe_future_result
from ..core.validation import validate_ticker, validate_date_range
from ..core.price import yf_call, to_clean_csv, df_to_clean_dict, get_options_chain, get_ticker_info_questrade_first, convert_numpy_types, format_date_string

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Implementation functions (module-level, importable by other modules)
# ---------------------------------------------------------------------------

def get_options_impl(
    ticker: str,
    num_options: int = 10,
    start_date: str | None = None,
    end_date: str | None = None,
    strike_lower: float | None = None,
    strike_upper: float | None = None,
    option_type: str | None = None,
) -> dict:
    """Get options data for a ticker."""
    ticker = validate_ticker(ticker)
    try:
        validate_date_range(start_date, end_date)

        t = yf.Ticker(ticker)
        expirations = t.options
        if not expirations:
            raise ValueError(f"No options available for {ticker}")

        valid_expirations = [
            exp for exp in expirations
            if ((not start_date or exp >= start_date) and
                (not end_date or exp <= end_date))
        ]
        if not valid_expirations:
            raise ValueError(f"No options found for {ticker} within specified date range")

        with ThreadPoolExecutor() as executor:
            futures = [(executor.submit(get_options_chain, ticker, exp, option_type), exp)
                       for exp in valid_expirations]
            chains = []
            for future, expiry in futures:
                chain = safe_future_result(future, context=f"options chain {ticker} {expiry}")
                if chain is not None:
                    chains.append(chain.assign(expiryDate=expiry))

        if not chains:
            raise ValueError(f"No options found for {ticker} matching criteria")

        df = pd.concat(chains, ignore_index=True)
        if strike_lower is not None:
            df = df[df['strike'] >= strike_lower]
        if strike_upper is not None:
            df = df[df['strike'] <= strike_upper]

        df = df.sort_values(['openInterest', 'volume'], ascending=[False, False])
        df_subset = df.head(num_options)
        return df_to_clean_dict(df_subset, preserve_columns=ESSENTIAL_OPTIONS_COLUMNS)

    except Exception as e:
        raise ValueError(f"Failed to retrieve options data: {str(e)}")


def get_trends_timeframe(days: int) -> str:
    """Get appropriate Google Trends timeframe for given days."""
    for max_days, timeframe in TREND_TIMEFRAMES.items():
        if days <= max_days:
            return timeframe
    return 'today 5-y'


def register_tools(mcp):
    @mcp.tool()
    async def get_market_movers(
        category: Literal["gainers", "losers", "most-active"] = "most-active",
        count: int = 25,
        market_session: Literal["regular", "pre-market", "after-hours"] = "regular"
    ) -> dict:
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
            return {"error": f"No data found for {category}"}

        df = tables[0].loc[:, ~tables[0].columns.str.contains('^Unnamed')]
        return df_to_clean_dict(df.head(count))


    @mcp.tool()
    def get_cnn_fear_greed_index(
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

        raw_data = fetch_json_sync(CNN_FEAR_GREED_URL, BROWSER_HEADERS)
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
    ) -> dict:
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

        return df_to_clean_dict(df_reset)

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
        ticker: str,
        num_options: int = 10,
        start_date: str | None = None,
        end_date: str | None = None,
        strike_lower: float | None = None,
        strike_upper: float | None = None,
        option_type: Literal["C", "P"] | None = None,
    ) -> dict:
        """Get options data. Dates: YYYY-MM-DD. Type: C=calls, P=puts."""
        return get_options_impl(ticker, num_options, start_date, end_date, strike_lower, strike_upper, option_type)
