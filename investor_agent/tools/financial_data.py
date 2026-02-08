"""
Financial data tools: statements, institutional holders, earnings, insider trades.
"""
import logging
import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Any

import pandas as pd
import yfinance as yf

from ..core.validation import validate_ticker, validate_date
from ..core.price import yf_call, to_clean_csv, df_to_clean_dict
from ..core.http import fetch_json, api_retry, safe_future_result
from ..core.config import BROWSER_HEADERS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Implementation functions (module-level, importable by other modules)
# ---------------------------------------------------------------------------

def get_institutional_holders_impl(ticker: str, top_n: int = 20) -> dict:
    """Get major institutional and mutual fund holders."""
    ticker = validate_ticker(ticker)

    with ThreadPoolExecutor() as executor:
        inst_future = executor.submit(yf_call, ticker, "get_institutional_holders")
        fund_future = executor.submit(yf_call, ticker, "get_mutualfund_holders")

        inst_holders = safe_future_result(inst_future, context=f"institutional holders for {ticker}")
        fund_holders = safe_future_result(fund_future, context=f"mutual fund holders for {ticker}")

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


async def get_nasdaq_earnings_calendar_impl(
    date: str | None = None,
    limit: int = 100,
) -> str:
    """Get earnings calendar for a specific date using Nasdaq API."""
    NASDAQ_EARNINGS_URL = "https://api.nasdaq.com/api/calendar/earnings"
    NASDAQ_HEADERS = {**BROWSER_HEADERS, 'Referer': 'https://www.nasdaq.com/'}

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

                if isinstance(headers, dict):
                    column_names = list(headers.values())
                    column_keys = list(headers.keys())
                else:
                    column_names = [h.get('label', h) if isinstance(h, dict) else str(h) for h in headers]
                    column_keys = column_names

                processed_rows = []
                for row in rows:
                    if isinstance(row, dict):
                        processed_row = [row.get(key, '') for key in column_keys]
                        processed_rows.append(processed_row)

                if processed_rows:
                    df = pd.DataFrame(processed_rows, columns=column_names)
                    df.insert(0, 'Date', date_str)
                    if len(df) > limit:
                        df = df.head(limit)
                    logger.info(f"Retrieved {len(df)} earnings entries for {date_str}")
                    return to_clean_csv(df)

        return {"error": f"No earnings announcements found for {date_str}."}

    except Exception as e:
        logger.error(f"Error fetching earnings for {date_str}: {e}")
        return {"error": f"Error retrieving earnings data for {date_str}: {str(e)}"}


def register_tools(mcp):
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
        return get_institutional_holders_impl(ticker, top_n)

    @mcp.tool()
    def get_earnings_history(ticker: str, max_entries: int = 8) -> dict:
        ticker = validate_ticker(ticker)

        earnings_history = yf_call(ticker, "get_earnings_history")
        if earnings_history is None or (isinstance(earnings_history, pd.DataFrame) and earnings_history.empty):
            raise ValueError(f"No earnings history data found for {ticker}")

        if isinstance(earnings_history, pd.DataFrame):
            earnings_history = earnings_history.head(max_entries)

        return df_to_clean_dict(earnings_history)

    @mcp.tool()
    def get_insider_trades(ticker: str, max_trades: int = 20) -> dict:
        ticker = validate_ticker(ticker)

        trades = yf_call(ticker, "get_insider_transactions")
        if trades is None or (isinstance(trades, pd.DataFrame) and trades.empty):
            raise ValueError(f"No insider trading data found for {ticker}")

        if isinstance(trades, pd.DataFrame):
            trades = trades.head(max_trades)

        return df_to_clean_dict(trades)

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
        return await get_nasdaq_earnings_calendar_impl(date, limit)
