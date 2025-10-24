#!/usr/bin/env python3
"""Diagnostic script to check Alpaca API credentials and permissions."""

import os


def diagnose():
    """Run diagnostic checks on Alpaca API configuration."""
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    print("=" * 70)
    print("  Alpaca API Diagnostic Tool")
    print("=" * 70)

    # Check environment variables
    print("\n1. Environment Variables Check:")
    print("-" * 70)
    alpaca_key = os.getenv('ALPACA_API_KEY')
    alpaca_secret = os.getenv('ALPACA_API_SECRET')

    if alpaca_key:
        print(f"✓ ALPACA_API_KEY is set: {alpaca_key[:8]}...{alpaca_key[-4:]}")
    else:
        print("✗ ALPACA_API_KEY is NOT set")
        print("\n❌ ERROR: Cannot proceed without API credentials.")
        print("\nPlease set your Alpaca API credentials:")
        print("  export ALPACA_API_KEY='your-api-key-here'")
        print("  export ALPACA_API_SECRET='your-api-secret-here'")
        print("\nGet your credentials at: https://alpaca.markets/")
        print("(You need an account with market data access enabled)")
        return

    if alpaca_secret:
        print(f"✓ ALPACA_API_SECRET is set: {alpaca_secret[:8]}...{alpaca_secret[-4:]}")
    else:
        print("✗ ALPACA_API_SECRET is NOT set")
        print("\n❌ ERROR: Cannot proceed without API secret.")
        print("\nPlease set your Alpaca API credentials:")
        print("  export ALPACA_API_KEY='your-api-key-here'")
        print("  export ALPACA_API_SECRET='your-api-secret-here'")
        print("\nGet your credentials at: https://alpaca.markets/")
        print("(You need an account with market data access enabled)")
        return

    # Test Account API (to verify credentials work at all)
    print("\n2. Account API Test (Paper Trading):")
    print("-" * 70)
    try:
        trading_client = TradingClient(alpaca_key, alpaca_secret, paper=True)
        account = trading_client.get_account()
        print("✓ SUCCESS! Credentials are valid for trading API")
        print(f"  Account Status: {account.status}")
        print(f"  Account Number: {account.account_number}")
        print(f"  Buying Power: ${float(account.buying_power):,.2f}")
    except Exception as e:
        print(f"✗ FAILED! Error: {str(e)[:200]}")

    # Test Market Data API
    print("\n3. Market Data API Test:")
    print("-" * 70)
    try:
        data_client = StockHistoricalDataClient(alpaca_key, alpaca_secret)

        # Try to fetch recent intraday data for SPY
        request = StockBarsRequest(
            symbol_or_symbols="SPY",
            timeframe=TimeFrame(1, TimeFrameUnit.Hour),
            limit=5
        )

        bars = data_client.get_stock_bars(request)
        df = bars.df

        if not df.empty:
            print("✓ SUCCESS! Market data access is working!")
            print(f"  Retrieved {len(df)} bars for SPY")
            print(f"  Latest bar timestamp: {df.index[-1][1]}")
        else:
            print("✗ FAILED! No data returned (empty DataFrame)")
    except Exception as e:
        error_msg = str(e)
        print(f"✗ FAILED! Error: {error_msg[:300]}")

        if "forbidden" in error_msg.lower() or "403" in error_msg:
            print("\nThis means your account doesn't have market data access.")
        elif "unauthorized" in error_msg.lower() or "401" in error_msg:
            print("\nYour credentials are invalid for market data API")

    # Recommendations
    print("\n" + "=" * 70)
    print("  Recommendations")
    print("=" * 70)
    print("""
To fix market data access issues:

1. Verify environment variables are exported in your current shell:
   export ALPACA_API_KEY="your-key-here"
   export ALPACA_API_SECRET="your-secret-here"

2. Check your Alpaca account at https://app.alpaca.markets/
   - Go to Paper Trading Account
   - Check if market data is enabled
   - You may need to:
     a) Accept market data agreements
     b) Subscribe to market data plan (free tier includes IEX data)
     c) Request historical data access

3. For free accounts:
   - You get IEX feed access
   - This is sufficient for most use cases
   - SIP feed requires a paid subscription

4. Make sure you're using Paper Trading API keys if testing
   - Paper trading keys work for market data
   - Live trading keys work too

5. If issues persist, try regenerating your API keys in the Alpaca dashboard.
""")


if __name__ == "__main__":
    diagnose()
