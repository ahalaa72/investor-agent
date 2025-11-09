"""
Questrade API client for fetching account information, positions, and balances.

This module provides a wrapper around the questrade-api package with proper
error handling, logging, and retry logic consistent with the investor-agent patterns.
"""

import logging
import os
import sys
from typing import Any, Dict, List, Optional

from questrade_api import Questrade
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)


class QuestradeClient:
    """
    Client for interacting with the Questrade API.

    This client provides methods to:
    - Retrieve account information
    - Get account positions (assets)
    - Get account balances (cash)

    Authentication is handled via a refresh token stored in environment variables.
    """

    def __init__(self, refresh_token: Optional[str] = None):
        """
        Initialize the Questrade client.

        Args:
            refresh_token: Optional refresh token. If not provided, will attempt
                         to load from QUESTRADE_REFRESH_TOKEN environment variable.

        Raises:
            ValueError: If no refresh token is provided or found in environment.
        """
        self.refresh_token = refresh_token or os.getenv("QUESTRADE_REFRESH_TOKEN")
        if not self.refresh_token:
            raise ValueError(
                "Questrade refresh token required. Set QUESTRADE_REFRESH_TOKEN "
                "environment variable or pass refresh_token parameter."
            )

        logger.info("QuestradeClient initialized")

    def _get_client(self) -> Questrade:
        """
        Get or create the Questrade API client instance.

        Creates a fresh client for each request to ensure tokens are properly refreshed.
        The questrade-api library handles token refresh automatically when instantiating
        a new client - it checks ~/.questrade.json and refreshes expired access tokens.

        On first use, we pass the manual refresh token from the environment.
        On subsequent uses, the library reads from ~/.questrade.json and auto-refreshes.

        Returns:
            Questrade: The initialized Questrade API client.
        """
        try:
            # Check if token file already exists
            token_file = os.path.expanduser("~/.questrade.json")

            if os.path.exists(token_file):
                # Token file exists - create fresh client to handle token refresh
                # The library will check if access token expired and refresh if needed
                logger.info("Using stored Questrade tokens from ~/.questrade.json")
                client = Questrade()
                logger.info("Questrade API client connected")
                return client
            else:
                # First time - use manual refresh token from environment
                logger.info("No stored tokens found, using manual refresh token from environment")
                client = Questrade(refresh_token=self.refresh_token)
                logger.info("Questrade API client connected")
                return client

        except Exception as e:
            logger.error(f"Failed to initialize Questrade client: {e}")
            raise ValueError(f"Failed to connect to Questrade API: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_accounts(self) -> Dict[str, Any]:
        """
        Retrieve all accounts associated with the authenticated user.

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
            ValueError: If API call fails or returns invalid data.
        """
        try:
            client = self._get_client()
            logger.info("Fetching Questrade accounts")
            accounts = client.accounts

            # Debug: Log what we actually received
            logger.debug(f"API response type: {type(accounts)}")
            logger.debug(f"API response: {accounts}")

            if not accounts or 'accounts' not in accounts:
                logger.error(f"Invalid response format. Got: {accounts}")
                raise ValueError("No accounts data returned from Questrade API")

            logger.info(f"Retrieved {len(accounts.get('accounts', []))} accounts")
            return accounts

        except Exception as e:
            logger.error(f"Error fetching accounts: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve Questrade accounts: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_account_positions(self, account_number: str) -> Dict[str, Any]:
        """
        Retrieve positions (assets/holdings) for a specific account.

        Args:
            account_number: The account number to query.

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
        """
        if not account_number:
            raise ValueError("account_number is required")

        try:
            client = self._get_client()
            logger.info(f"Fetching positions for account {account_number}")
            positions = client.account_positions(account_number)

            if positions is None:
                raise ValueError(f"No positions data returned for account {account_number}")

            position_count = len(positions.get('positions', []))
            logger.info(f"Retrieved {position_count} positions for account {account_number}")
            return positions

        except Exception as e:
            logger.error(f"Error fetching positions for account {account_number}: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve positions for account {account_number}: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_account_balances(
        self,
        account_number: str,
        start_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve cash balances for a specific account.

        Args:
            account_number: The account number to query.
            start_time: Optional start time for historical balances (ISO format).

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
        """
        if not account_number:
            raise ValueError("account_number is required")

        try:
            client = self._get_client()
            logger.info(f"Fetching balances for account {account_number}")

            # Call with start_time if provided
            if start_time:
                balances = client.account_balances(account_number, start_time)
            else:
                balances = client.account_balances(account_number)

            if balances is None:
                raise ValueError(f"No balance data returned for account {account_number}")

            logger.info(f"Retrieved balances for account {account_number}")
            return balances

        except Exception as e:
            logger.error(f"Error fetching balances for account {account_number}: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve balances for account {account_number}: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get real-time Level 1 quote for a single symbol.

        Args:
            symbol: The symbol to get quote for (e.g., "AAPL", "TSLA").

        Returns:
            dict: Quote information including bid, ask, last price, volume, etc.

        Raises:
            ValueError: If symbol is invalid or API call fails.
        """
        if not symbol:
            raise ValueError("symbol is required")

        try:
            client = self._get_client()
            logger.info(f"Fetching quote for {symbol}")
            quote = client.markets_quote(symbol)

            if quote is None:
                raise ValueError(f"No quote data returned for {symbol}")

            logger.info(f"Retrieved quote for {symbol}")
            return quote

        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve quote for {symbol}: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Get real-time Level 1 quotes for multiple symbols.

        Args:
            symbols: List of symbols to get quotes for.

        Returns:
            dict: Quotes for all requested symbols.

        Raises:
            ValueError: If symbols are invalid or API call fails.
        """
        if not symbols:
            raise ValueError("symbols list is required")

        try:
            client = self._get_client()
            # Convert list to comma-separated string
            symbols_str = ",".join(symbols)
            logger.info(f"Fetching quotes for {len(symbols)} symbols")
            quotes = client.markets_quotes(symbols_str)

            if quotes is None:
                raise ValueError(f"No quotes data returned")

            logger.info(f"Retrieved quotes for {len(symbols)} symbols")
            return quotes

        except Exception as e:
            logger.error(f"Error fetching quotes: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve quotes: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_candles(
        self,
        symbol: str,
        interval: str,
        start_time: str,
        end_time: str
    ) -> Dict[str, Any]:
        """
        Get historical OHLCV candle data for a symbol.

        Args:
            symbol: The symbol to get candles for.
            interval: Candle interval (OneMinute, TwoMinutes, ThreeMinutes, FourMinutes,
                     FiveMinutes, TenMinutes, FifteenMinutes, TwentyMinutes, HalfHour,
                     OneHour, TwoHours, FourHours, OneDay, OneWeek, OneMonth, OneYear).
            start_time: Start time in ISO format (e.g., "2024-01-01T00:00:00-05:00").
            end_time: End time in ISO format.

        Returns:
            dict: Candle data with OHLCV values.

        Raises:
            ValueError: If parameters are invalid or API call fails.
        """
        if not symbol or not interval or not start_time or not end_time:
            raise ValueError("symbol, interval, start_time, and end_time are required")

        try:
            client = self._get_client()
            logger.info(f"Fetching candles for {symbol} ({interval})")
            candles = client.markets_candles(symbol, interval, start_time, end_time)

            if candles is None:
                raise ValueError(f"No candle data returned for {symbol}")

            logger.info(f"Retrieved candles for {symbol}")
            return candles

        except Exception as e:
            logger.error(f"Error fetching candles for {symbol}: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve candles for {symbol}: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def search_symbols(self, query: str, offset: int = 0) -> Dict[str, Any]:
        """
        Search for symbols by name or description.

        Args:
            query: Search query string.
            offset: Offset for pagination (default 0).

        Returns:
            dict: Search results with matching symbols.

        Raises:
            ValueError: If query is invalid or API call fails.
        """
        if not query:
            raise ValueError("query is required")

        try:
            client = self._get_client()
            logger.info(f"Searching symbols for: {query}")
            results = client.symbols_search(query, offset)

            if results is None:
                raise ValueError(f"No search results returned for {query}")

            logger.info(f"Found symbols matching: {query}")
            return results

        except Exception as e:
            logger.error(f"Error searching symbols for {query}: {e}", exc_info=True)
            raise ValueError(f"Failed to search symbols: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_symbol_info(self, symbols: str) -> Dict[str, Any]:
        """
        Get detailed information for one or more symbols.

        Args:
            symbols: Single symbol or comma-separated list of symbols.

        Returns:
            dict: Detailed symbol information.

        Raises:
            ValueError: If symbols are invalid or API call fails.
        """
        if not symbols:
            raise ValueError("symbols is required")

        try:
            client = self._get_client()
            logger.info(f"Fetching symbol info for: {symbols}")
            info = client.symbols(names=symbols)

            if info is None:
                raise ValueError(f"No symbol info returned for {symbols}")

            logger.info(f"Retrieved symbol info for: {symbols}")
            return info

        except Exception as e:
            logger.error(f"Error fetching symbol info for {symbols}: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve symbol info: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_markets(self) -> Dict[str, Any]:
        """
        Get information about available markets.

        Returns:
            dict: List of available markets and their details.

        Raises:
            ValueError: If API call fails.
        """
        try:
            client = self._get_client()
            logger.info("Fetching available markets")
            markets = client.markets()

            if markets is None:
                raise ValueError("No markets data returned")

            logger.info("Retrieved markets information")
            return markets

        except Exception as e:
            logger.error(f"Error fetching markets: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve markets: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_account_orders(
        self,
        account_number: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        state_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get orders for a specific account.

        Args:
            account_number: The account number.
            start_time: Optional start time filter (ISO format: YYYY-MM-DDTHH:MM:SS-05:00).
                       Defaults to 30 days ago if not provided.
            end_time: Optional end time filter (ISO format).
                     Defaults to current time if not provided.
            state_filter: Optional state filter (All, Open, Closed).

        Returns:
            dict: List of orders.

        Raises:
            ValueError: If account_number is invalid or API call fails.

        Note:
            If no date range is provided, defaults to last 30 days to avoid
            API response size limits. For older data, provide explicit date range.
        """
        if not account_number:
            raise ValueError("account_number is required")

        try:
            client = self._get_client()

            # Set default date range if not provided (to avoid "argument length exceeds limit" error)
            from datetime import datetime, timedelta, timezone

            if start_time is None:
                # Default to 30 days ago
                default_start = datetime.now(timezone.utc) - timedelta(days=30)
                start_time = default_start.strftime('%Y-%m-%dT%H:%M:%S-05:00')
                logger.info(f"No start_time provided, defaulting to 30 days ago: {start_time}")

            if end_time is None:
                # Default to current time
                default_end = datetime.now(timezone.utc)
                end_time = default_end.strftime('%Y-%m-%dT%H:%M:%S-05:00')
                logger.info(f"No end_time provided, defaulting to current time: {end_time}")

            logger.info(f"Fetching orders for account {account_number} from {start_time} to {end_time}")

            # Build kwargs dict
            kwargs = {
                'startTime': start_time,
                'endTime': end_time
            }
            if state_filter is not None:
                kwargs['stateFilter'] = state_filter

            orders = client.account_orders(account_number, **kwargs)

            if orders is None:
                raise ValueError(f"No orders data returned for account {account_number}")

            order_count = len(orders.get('orders', []))
            logger.info(f"Retrieved {order_count} orders for account {account_number}")
            return orders

        except Exception as e:
            logger.error(f"Error fetching orders for account {account_number}: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve orders: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_account_order(self, account_number: str, order_id: str) -> Dict[str, Any]:
        """
        Get details for a specific order.

        Args:
            account_number: The account number.
            order_id: The order ID.

        Returns:
            dict: Order details.

        Raises:
            ValueError: If parameters are invalid or API call fails.
        """
        if not account_number or not order_id:
            raise ValueError("account_number and order_id are required")

        try:
            client = self._get_client()
            logger.info(f"Fetching order {order_id} for account {account_number}")
            order = client.account_order(account_number, order_id)

            if order is None:
                raise ValueError(f"No order data returned for order {order_id}")

            logger.info(f"Retrieved order {order_id}")
            return order

        except Exception as e:
            logger.error(f"Error fetching order {order_id}: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve order: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_account_executions(
        self,
        account_number: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get trade executions for a specific account.

        Args:
            account_number: The account number.
            start_time: Optional start time filter (ISO format: YYYY-MM-DDTHH:MM:SS-05:00).
                       Defaults to 90 days ago if not provided.
            end_time: Optional end time filter (ISO format).
                     Defaults to current time if not provided.

        Returns:
            dict: List of trade executions.

        Raises:
            ValueError: If account_number is invalid or API call fails.

        Note:
            If no date range is provided, defaults to last 90 days to avoid
            API response size limits. For older data, provide explicit date range.
        """
        if not account_number:
            raise ValueError("account_number is required")

        try:
            client = self._get_client()

            # Set default date range if not provided (to avoid "argument length exceeds limit" error)
            from datetime import datetime, timedelta, timezone

            if start_time is None:
                # Default to 90 days ago
                default_start = datetime.now(timezone.utc) - timedelta(days=90)
                start_time = default_start.strftime('%Y-%m-%dT%H:%M:%S-05:00')
                logger.info(f"No start_time provided, defaulting to 90 days ago: {start_time}")

            if end_time is None:
                # Default to current time
                default_end = datetime.now(timezone.utc)
                end_time = default_end.strftime('%Y-%m-%dT%H:%M:%S-05:00')
                logger.info(f"No end_time provided, defaulting to current time: {end_time}")

            logger.info(f"Fetching executions for account {account_number} from {start_time} to {end_time}")

            # Build kwargs dict
            kwargs = {
                'startTime': start_time,
                'endTime': end_time
            }

            executions = client.account_executions(account_number, **kwargs)

            if executions is None:
                raise ValueError(f"No executions data returned for account {account_number}")

            execution_count = len(executions.get('executions', []))
            logger.info(f"Retrieved {execution_count} executions for account {account_number}")
            return executions

        except Exception as e:
            logger.error(f"Error fetching executions for account {account_number}: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve executions: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_account_activities(
        self,
        account_number: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get account activities (deposits, withdrawals, fees, etc.).

        Args:
            account_number: The account number.
            start_time: Optional start time filter (ISO format: YYYY-MM-DDTHH:MM:SS-05:00).
                       Defaults to 30 days ago if not provided.
            end_time: Optional end time filter (ISO format).
                     Defaults to current time if not provided.

        Returns:
            dict: List of account activities.

        Raises:
            ValueError: If account_number is invalid or API call fails.

        Note:
            If no date range is provided, defaults to last 30 days to avoid
            API response size limits (error 1003: "Argument length exceeds imposed limit").
            For older data, provide explicit date range in smaller chunks (e.g., 30-day periods).
        """
        if not account_number:
            raise ValueError("account_number is required")

        try:
            client = self._get_client()

            # Set default date range if not provided (to avoid "argument length exceeds limit" error)
            from datetime import datetime, timedelta, timezone

            if start_time is None:
                # Default to 30 days ago (activities can be more voluminous than executions)
                default_start = datetime.now(timezone.utc) - timedelta(days=30)
                start_time = default_start.strftime('%Y-%m-%dT%H:%M:%S-05:00')
                logger.info(f"No start_time provided, defaulting to 30 days ago: {start_time}")

            if end_time is None:
                # Default to current time
                default_end = datetime.now(timezone.utc)
                end_time = default_end.strftime('%Y-%m-%dT%H:%M:%S-05:00')
                logger.info(f"No end_time provided, defaulting to current time: {end_time}")

            logger.info(f"Fetching activities for account {account_number} from {start_time} to {end_time}")

            # Build kwargs dict
            kwargs = {
                'startTime': start_time,
                'endTime': end_time
            }

            activities = client.account_activities(account_number, **kwargs)

            if activities is None:
                raise ValueError(f"No activities data returned for account {account_number}")

            activity_count = len(activities.get('activities', []))
            logger.info(f"Retrieved {activity_count} activities for account {account_number}")
            return activities

        except Exception as e:
            logger.error(f"Error fetching activities for account {account_number}: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve activities: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_options_chain(self, symbol: str) -> Dict[str, Any]:
        """
        Get options chain for a symbol.

        Args:
            symbol: The underlying symbol.

        Returns:
            dict: Options chain data.

        Raises:
            ValueError: If symbol is invalid or API call fails.
        """
        if not symbol:
            raise ValueError("symbol is required")

        try:
            client = self._get_client()
            logger.info(f"Fetching options chain for {symbol}")
            options = client.symbol_options(symbol)

            if options is None:
                raise ValueError(f"No options data returned for {symbol}")

            logger.info(f"Retrieved options chain for {symbol}")
            return options

        except Exception as e:
            logger.error(f"Error fetching options for {symbol}: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve options chain: {str(e)}")

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def get_option_quotes(self, option_ids: List[int]) -> Dict[str, Any]:
        """
        Get quotes with Greeks for option symbols.

        Args:
            option_ids: List of option IDs.

        Returns:
            dict: Option quotes with Greeks data.

        Raises:
            ValueError: If option_ids are invalid or API call fails.
        """
        if not option_ids:
            raise ValueError("option_ids list is required")

        try:
            client = self._get_client()
            logger.info(f"Fetching option quotes for {len(option_ids)} options")
            quotes = client.markets_options(option_ids)

            if quotes is None:
                raise ValueError("No option quotes returned")

            logger.info(f"Retrieved option quotes for {len(option_ids)} options")
            return quotes

        except Exception as e:
            logger.error(f"Error fetching option quotes: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve option quotes: {str(e)}")


# Singleton instance
_questrade_client: Optional[QuestradeClient] = None


def get_questrade_client() -> QuestradeClient:
    """
    Get or create a singleton QuestradeClient instance.

    Returns:
        QuestradeClient: The initialized client instance.

    Raises:
        ValueError: If refresh token is not configured.
    """
    global _questrade_client
    if _questrade_client is None:
        _questrade_client = QuestradeClient()
    return _questrade_client
