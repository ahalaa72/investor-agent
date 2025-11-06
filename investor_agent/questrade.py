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

        self._client: Optional[Questrade] = None
        logger.info("QuestradeClient initialized")

    def _get_client(self) -> Questrade:
        """
        Get or create the Questrade API client instance.

        Returns:
            Questrade: The initialized Questrade API client.
        """
        if self._client is None:
            try:
                self._client = Questrade(refresh_token=self.refresh_token)
                logger.info("Questrade API client connected")
            except Exception as e:
                logger.error(f"Failed to initialize Questrade client: {e}")
                raise ValueError(f"Failed to connect to Questrade API: {str(e)}")
        return self._client

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

            if not accounts or 'accounts' not in accounts:
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
