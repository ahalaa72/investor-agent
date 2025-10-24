#!/usr/bin/env python3
"""Diagnostic script to check Alpaca API credentials and permissions."""

import os
import httpx
import asyncio


async def diagnose():
    """Run diagnostic checks on Alpaca API configuration."""

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
        alpaca_key = 'PKLPZ2H7Y5CK0JO6QNOI'  # Default from code
        print(f"  Using default: {alpaca_key[:8]}...{alpaca_key[-4:]}")

    if alpaca_secret:
        print(f"✓ ALPACA_API_SECRET is set: {alpaca_secret[:8]}...{alpaca_secret[-4:]}")
    else:
        print("✗ ALPACA_API_SECRET is NOT set")
        alpaca_secret = 'JvyvcgEPPELqgZb1QOPk7CYnf5IUJRdIuR2nBeYa'  # Default from code
        print(f"  Using default: {alpaca_secret[:8]}...{alpaca_secret[-4:]}")

    # Test Account API (to verify credentials work at all)
    print("\n2. Account API Test (Paper Trading):")
    print("-" * 70)
    headers = {
        'APCA-API-KEY-ID': alpaca_key,
        'APCA-API-SECRET-KEY': alpaca_secret
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                'https://paper-api.alpaca.markets/v2/account',
                headers=headers
            )
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                print("✓ SUCCESS! Credentials are valid for trading API")
                data = response.json()
                print(f"  Account Status: {data.get('status', 'unknown')}")
                print(f"  Account Number: {data.get('account_number', 'unknown')}")
            else:
                print(f"✗ FAILED! Response: {response.text[:200]}")
    except Exception as e:
        print(f"✗ ERROR: {e}")

    # Test Market Data API (IEX feed)
    print("\n3. Market Data API Test (IEX Feed):")
    print("-" * 70)
    try:
        url = "https://data.alpaca.markets/v2/stocks/SPY/bars?timeframe=1Hour&limit=5&feed=iex"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                print("✓ SUCCESS! Market data access is working!")
                data = response.json()
                if 'bars' in data:
                    print(f"  Received {len(data['bars'])} bars")
            elif response.status_code == 403:
                print("✗ FAILED! 403 Forbidden")
                print("\nThis means your account doesn't have market data access.")
                print("Response:", response.text[:300])
            elif response.status_code == 401:
                print("✗ FAILED! 401 Unauthorized")
                print("Your credentials are invalid for market data API")
                print("Response:", response.text[:300])
            else:
                print(f"✗ FAILED! Status {response.status_code}")
                print("Response:", response.text[:300])
    except Exception as e:
        print(f"✗ ERROR: {e}")

    # Test Market Data API (SIP feed - requires subscription)
    print("\n4. Market Data API Test (SIP Feed - Premium):")
    print("-" * 70)
    try:
        url = "https://data.alpaca.markets/v2/stocks/SPY/bars?timeframe=1Hour&limit=5&feed=sip"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                print("✓ SUCCESS! Premium SIP feed access is enabled!")
            elif response.status_code == 403:
                print("✗ 403 Forbidden - SIP feed requires paid subscription")
                print("  (This is expected for free accounts)")
            else:
                print(f"Status {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"✗ ERROR: {e}")

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
     b) Subscribe to market data plan
     c) Request historical data access

3. For free accounts:
   - You get IEX feed access
   - SIP feed requires a paid subscription
   - Some accounts have restrictions

4. Alternative: Use a different set of API credentials that have
   market data permissions enabled.

5. If using paper trading credentials, make sure they have market
   data access (not all paper accounts have this by default).
""")


if __name__ == "__main__":
    asyncio.run(diagnose())
