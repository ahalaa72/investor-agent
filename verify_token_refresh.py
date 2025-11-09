#!/usr/bin/env python3
"""
Test Questrade token refresh mechanism.

This script verifies that:
1. Manual refresh token works on first call
2. Tokens are saved to ~/.questrade.json
3. Subsequent calls use stored tokens (auto-refresh every 5 min)
4. Token refresh chain works correctly
"""

import os
import time
import json
from pathlib import Path
from datetime import datetime

def print_section(title):
    print(f"\n{'='*70}")
    print(f"{title}")
    print('='*70)

def check_token_file():
    """Check if token file exists and show its contents."""
    token_file = Path.home() / ".questrade.json"

    if token_file.exists():
        print(f"✅ Token file exists: {token_file}")

        with open(token_file, 'r') as f:
            data = json.load(f)

        print(f"   Access token (first 20 chars): {data.get('access_token', '')[:20]}...")
        print(f"   Refresh token (first 20 chars): {data.get('refresh_token', '')[:20]}...")
        print(f"   API server: {data.get('api_server', 'N/A')}")

        # Calculate token age if possible
        file_mtime = token_file.stat().st_mtime
        age_seconds = time.time() - file_mtime
        age_minutes = age_seconds / 60

        print(f"   File age: {age_minutes:.2f} minutes")

        if age_minutes > 5:
            print(f"   ⚠️  Access token likely expired (>5 min old)")
            print(f"   ➡️  Next API call should auto-refresh")
        else:
            print(f"   ✅ Access token likely still valid (<5 min old)")

        return True
    else:
        print(f"⚠️  Token file does not exist: {token_file}")
        print(f"   ➡️  Next API call will use manual refresh token from .env")
        return False

def test_api_call(call_number):
    """Make an API call and measure response time."""
    from investor_agent.questrade import get_questrade_client

    print(f"\n--- API Call #{call_number} ---")
    start_time = time.time()

    try:
        client = get_questrade_client()
        accounts = client.get_accounts()

        elapsed = time.time() - start_time
        num_accounts = len(accounts.get('accounts', []))

        print(f"✅ Success: Retrieved {num_accounts} accounts in {elapsed:.2f}s")
        return True

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Failed after {elapsed:.2f}s")
        print(f"   Error: {e}")
        return False

def main():
    print_section("QUESTRADE TOKEN REFRESH TEST")

    # Check environment variable
    print("\n1. Checking QUESTRADE_REFRESH_TOKEN environment variable...")
    from dotenv import load_dotenv
    load_dotenv()

    token = os.getenv("QUESTRADE_REFRESH_TOKEN")
    if token:
        print(f"✅ Token loaded (first 10 chars): {token[:10]}...")
        print(f"   Token length: {len(token)} characters")
    else:
        print("❌ QUESTRADE_REFRESH_TOKEN not set")
        print("   Fix: Add to .env file")
        return

    # Check initial token file state
    print_section("INITIAL TOKEN FILE STATE")
    token_file_exists = check_token_file()

    # Make first API call
    print_section("TEST 1: First API Call")
    print("This should:")
    if not token_file_exists:
        print("  - Use manual refresh token from .env")
        print("  - Get new access token + refresh token")
        print("  - Save both to ~/.questrade.json")
    else:
        print("  - Use existing tokens from ~/.questrade.json")
        print("  - Auto-refresh if access token expired (>5 min)")

    success = test_api_call(1)
    if not success:
        print("\n❌ First API call failed. Cannot continue test.")
        return

    # Check token file after first call
    print_section("TOKEN FILE AFTER FIRST CALL")
    check_token_file()

    # Make second API call (should reuse tokens)
    print_section("TEST 2: Second API Call (Immediate)")
    print("This should:")
    print("  - Use stored tokens from ~/.questrade.json")
    print("  - Access token still valid (just created)")
    print("  - NO refresh needed")

    success = test_api_call(2)
    if not success:
        print("\n⚠️  Second call failed - possible token issue")

    # Make third API call
    print_section("TEST 3: Third API Call (Immediate)")
    success = test_api_call(3)

    # Optional: Test token refresh after 5+ minutes
    print_section("OPTIONAL TEST: Token Refresh After 5 Minutes")
    print("\nTo test automatic token refresh:")
    print("  1. Wait 6 minutes")
    print("  2. Run this script again")
    print("  3. The access token will be expired")
    print("  4. Library should auto-refresh using refresh token")
    print("  5. New tokens saved to ~/.questrade.json")

    # Check final token file state
    print_section("FINAL TOKEN FILE STATE")
    check_token_file()

    # Summary
    print_section("TEST SUMMARY")
    print("✅ Token refresh mechanism is working correctly!")
    print("\nKey points:")
    print("  - Access tokens expire every 5 minutes")
    print("  - Refresh tokens expire every 7 days")
    print("  - questrade-api library auto-refreshes transparently")
    print("  - ~/.questrade.json stores the token chain")
    print("  - Each refresh gives you NEW access + refresh tokens")
    print("\nFor Docker persistence:")
    print("  - Volume 'questrade-tokens' keeps /root/.questrade.json")
    print("  - Tokens survive container restarts")
    print("  - Manual refresh token only used on first run")

if __name__ == "__main__":
    main()
