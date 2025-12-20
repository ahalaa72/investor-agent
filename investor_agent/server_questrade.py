"""
Investor Agent - Questrade Server

Questrade account and trading tools.
Split from main server to prevent Claude Desktop from freezing.
"""

from dotenv import load_dotenv
load_dotenv()

import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)

# Create MCP server
mcp = FastMCP("Investor-Agent-Questrade", dependencies=["questrade-api"])

# Import Questrade client
try:
    from .questrade import get_questrade_client
    _questrade_available = True
except ImportError:
    _questrade_available = False
    logger.warning("Questrade module not available")


# =============================================================================
# QUESTRADE ACCOUNT TOOLS
# =============================================================================

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
                'combinedBalances': [...],
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


# =============================================================================
# SERVER ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    mcp.run()
