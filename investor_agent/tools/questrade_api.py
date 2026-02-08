"""
Questrade API tools: accounts, positions, balances, quotes, candles, options, orders.
"""
import logging
import datetime

from ..questrade import get_questrade_client
from ..core.price import convert_numpy_types

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Implementation functions (module-level, importable by other modules)
# ---------------------------------------------------------------------------

def get_questrade_accounts_impl() -> dict:
    """Retrieve all Questrade accounts."""
    try:
        client = get_questrade_client()
        accounts = client.get_accounts()
        logger.info(f"Retrieved {len(accounts.get('accounts', []))} Questrade accounts")
        return accounts
    except Exception as e:
        logger.error(f"Error in get_questrade_accounts: {e}")
        raise ValueError(f"Failed to retrieve Questrade accounts: {str(e)}")


def get_questrade_positions_impl(account_number: str) -> dict:
    """Retrieve positions for a Questrade account."""
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


def get_questrade_balances_impl(account_number: str, start_time: str | None = None) -> dict:
    """Retrieve balances for a Questrade account."""
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


def get_questrade_quotes_impl(symbols: list[str]) -> dict:
    """Retrieve real-time quotes, falling back to Yahoo Finance."""
    if not symbols:
        raise ValueError("symbols list parameter is required")

    # Try Questrade first
    try:
        client = get_questrade_client()
        quotes = client.get_quotes(symbols)
        quotes['data_source'] = 'QUESTRADE'
        quotes['data_quality'] = 'REAL-TIME (0 delay)'
        quotes['note'] = 'Real-time data from Questrade API'
        logger.info(f"✓ Retrieved quotes for {len(symbols)} symbols from Questrade (real-time)")
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
                    'VWAP': None,
                    'delay': 0,
                    'isHalted': False,
                }
                yf_quotes.append(quote)

            result = {
                'quotes': yf_quotes,
                'data_source': 'YAHOO_FINANCE',
                'WARNING': '⚠️ USING DELAYED DATA - Questrade unavailable, falling back to Yahoo Finance',
                'data_quality': 'DELAYED (15-20 min old)',
                'note': 'This is NOT real-time data. Verify current price with your broker before trading.',
                'questrade_error': str(questrade_error),
                'recommendation': 'Fix Questrade token to get real-time data. See CLAUDE.md troubleshooting section.'
            }
            logger.warning(f"Retrieved quotes for {len(symbols)} symbols from Yahoo Finance (FALLBACK - data may be stale)")
            return result

        except Exception as yf_error:
            logger.error(f"Both Questrade and Yahoo Finance failed: {yf_error}")
            raise ValueError(f"Failed to retrieve quotes from both sources. Questrade: {questrade_error}, Yahoo Finance: {yf_error}")


def get_questrade_candles_impl(
    symbol: str,
    interval: str,
    start_time: str | None = None,
    end_time: str | None = None,
    window: int | None = None
) -> dict:
    """Retrieve historical OHLCV candles, falling back to Yahoo Finance."""
    import pytz

    if not symbol or not interval:
        raise ValueError("symbol and interval are required")

    # Calculate time range from window if provided
    if window is not None:
        et = pytz.timezone("America/New_York")
        end_dt = datetime.datetime.now(et)

        interval_minutes = {
            "OneMinute": 1, "TwoMinutes": 2, "ThreeMinutes": 3,
            "FourMinutes": 4, "FiveMinutes": 5, "TenMinutes": 10,
            "FifteenMinutes": 15, "TwentyMinutes": 20, "HalfHour": 30,
            "OneHour": 60, "TwoHours": 120, "FourHours": 240,
            "OneDay": 1440, "OneWeek": 10080, "OneMonth": 43200,
            "OneYear": 525600,
        }
        minutes = interval_minutes.get(interval, 60)
        start_dt = end_dt - datetime.timedelta(minutes=minutes * window * 3)

        start_time = start_dt.isoformat()
        end_time = end_dt.isoformat()

    elif start_time is None or end_time is None:
        raise ValueError("Either provide window OR both start_time and end_time")

    # Try Questrade first
    try:
        client = get_questrade_client()
        candles = client.get_candles(symbol, interval, start_time, end_time)
        candles['data_source'] = 'QUESTRADE'
        candles['data_quality'] = 'REAL-TIME (0 delay)'
        candles['note'] = 'Real-time historical data from Questrade API'
        logger.info(f"✓ Retrieved candles for {symbol} from Questrade (real-time)")
        return candles

    except Exception as questrade_error:
        logger.warning(f"Questrade failed, falling back to Yahoo Finance: {questrade_error}")

        # Fallback to Yahoo Finance
        try:
            import yfinance as yf
            import pandas as pd

            interval_map = {
                "OneMinute": "1m", "TwoMinutes": "2m", "FiveMinutes": "5m",
                "FifteenMinutes": "15m", "HalfHour": "30m", "OneHour": "1h",
                "OneDay": "1d", "OneWeek": "1wk", "OneMonth": "1mo",
            }
            yf_interval = interval_map.get(interval, "1d")

            if window is not None:
                if yf_interval in ["1m", "2m", "5m", "15m", "30m"]:
                    period = "7d"
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
                start_date = start_time[:10] if start_time else None
                end_date = end_time[:10] if end_time else None
                df = yf.download(symbol, start=start_date, end=end_date, interval=yf_interval, progress=False)

            if df.empty:
                raise ValueError(f"No data returned from Yahoo Finance for {symbol}")

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

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

            if window is not None and len(candles_list) > window:
                candles_list = candles_list[-window:]

            result = {
                'candles': candles_list,
                'data_source': 'YAHOO_FINANCE',
                'WARNING': '⚠️ USING DELAYED DATA - Questrade unavailable, falling back to Yahoo Finance',
                'data_quality': 'DELAYED (15-20 min old)',
                'note': f'Interval mapped: {interval} -> {yf_interval}. This is NOT real-time data.',
                'questrade_error': str(questrade_error),
                'recommendation': 'Fix Questrade token to get real-time data. See CLAUDE.md troubleshooting section.'
            }
            logger.warning(f"Retrieved {len(candles_list)} candles for {symbol} from Yahoo Finance (FALLBACK - data may be stale)")
            return result

        except Exception as yf_error:
            logger.error(f"Both Questrade and Yahoo Finance failed: {yf_error}")
            raise ValueError(f"Failed to retrieve candles from both sources. Questrade: {questrade_error}, Yahoo Finance: {yf_error}")


def register_tools(mcp):

    @mcp.tool()
    def get_questrade_accounts() -> dict:
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
        return get_questrade_accounts_impl()

    @mcp.tool()
    def get_questrade_positions(account_number: str) -> dict:
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
        return get_questrade_positions_impl(account_number)

    @mcp.tool()
    def get_questrade_balances(
        account_number: str,
        start_time: str | None = None
    ) -> dict:
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
        return get_questrade_balances_impl(account_number, start_time)

    # NOTE: get_questrade_quote was removed as redundant.
    # Use get_questrade_quotes(symbols=["AAPL"]) for single quotes.

    @mcp.tool()
    def get_questrade_quotes(symbols: list[str]) -> dict:
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
        return get_questrade_quotes_impl(symbols)

    @mcp.tool()
    def get_questrade_candles(
        symbol: str,
        interval: str,
        start_time: str | None = None,
        end_time: str | None = None,
        window: int | None = None
    ) -> dict:
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
        return get_questrade_candles_impl(symbol, interval, start_time, end_time, window)

    @mcp.tool()
    def search_questrade_symbols(query: str, offset: int = 0) -> dict:
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
    def get_questrade_symbol_info(symbols: str) -> dict:
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
    def get_questrade_markets() -> dict:
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
    ) -> dict:
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
    def get_questrade_order(account_number: str, order_id: str) -> dict:
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
    ) -> dict:
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
    ) -> dict:
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
    def get_questrade_options_chain(symbol: str) -> dict:
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
    def get_questrade_option_quotes(option_ids: list[int]) -> dict:
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
