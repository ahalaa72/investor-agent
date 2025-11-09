#!/usr/bin/env python3
"""
Diagnostic script to verify Questrade integration is working correctly.
This will test both the questrade-api library and our QuestradeClient wrapper.
"""

import os
import sys

def test_questrade_library():
    """Test that questrade-api library is installed and accessible."""
    print("="*70)
    print("Step 1: Testing questrade-api library installation")
    print("="*70)

    try:
        from questrade_api import Questrade
        print("✅ questrade-api library is installed")

        # Check what attributes/methods are available
        questrade_methods = [attr for attr in dir(Questrade) if not attr.startswith('_')]
        print(f"\n   Available public attributes/methods on Questrade class:")
        for method in sorted(questrade_methods):
            print(f"     - {method}")

        return True
    except ImportError as e:
        print(f"❌ questrade-api library is NOT installed: {e}")
        print("\n   Fix: pip install questrade-api")
        return False


def test_questrade_client_wrapper():
    """Test our QuestradeClient wrapper."""
    print("\n" + "="*70)
    print("Step 2: Testing QuestradeClient wrapper")
    print("="*70)

    try:
        from investor_agent.questrade import QuestradeClient, get_questrade_client
        print("✅ QuestradeClient wrapper can be imported")

        # Check what methods are available on our wrapper
        wrapper_methods = [attr for attr in dir(QuestradeClient) if not attr.startswith('_')]
        print(f"\n   Available public methods on QuestradeClient wrapper:")
        for method in sorted(wrapper_methods):
            print(f"     - {method}")

        return True
    except ImportError as e:
        print(f"❌ QuestradeClient wrapper import failed: {e}")
        return False


def test_token_configuration():
    """Test that refresh token is configured."""
    print("\n" + "="*70)
    print("Step 3: Testing token configuration")
    print("="*70)

    token = os.getenv("QUESTRADE_REFRESH_TOKEN")
    if not token:
        print("❌ QUESTRADE_REFRESH_TOKEN environment variable is NOT set")
        print("\n   Fix: export QUESTRADE_REFRESH_TOKEN='your_token_here'")
        return False

    token_len = len(token)
    print(f"✅ QUESTRADE_REFRESH_TOKEN is set")
    print(f"   Token length: {token_len} characters")

    # Note: Questrade tokens can vary in length (some are 30+ chars, others 300-400+)
    # Both short and long tokens can be valid depending on token generation method
    if token_len < 20:
        print(f"   ⚠️  WARNING: Token seems very short (< 20 chars)")
        print(f"   This is likely invalid - verify you copied the complete token")
        return False
    elif token_len < 100:
        print(f"   ℹ️  Note: Short token detected (valid for some Questrade token types)")
        print(f"   ✅ Token length is acceptable")
    else:
        print(f"   ✅ Token length looks good (standard long token)")

    return True


def test_client_instantiation():
    """Test that we can create a QuestradeClient instance."""
    print("\n" + "="*70)
    print("Step 4: Testing QuestradeClient instantiation")
    print("="*70)

    try:
        from investor_agent.questrade import QuestradeClient

        print("Creating QuestradeClient instance...")
        client = QuestradeClient()
        print("✅ QuestradeClient instance created successfully")

        # Check if it has the expected methods
        expected_methods = [
            'get_accounts',
            'get_account_positions',
            'get_account_balances',
            'get_quote',
            'get_quotes',
            'get_candles',
        ]

        print("\n   Checking for expected methods:")
        all_found = True
        for method in expected_methods:
            if hasattr(client, method):
                print(f"     ✅ {method}")
            else:
                print(f"     ❌ {method} NOT FOUND")
                all_found = False

        return all_found

    except Exception as e:
        print(f"❌ Failed to create QuestradeClient instance: {e}")
        return False


def test_api_connection():
    """Test actual API connection (requires valid token)."""
    print("\n" + "="*70)
    print("Step 5: Testing API connection")
    print("="*70)

    try:
        from investor_agent.questrade import QuestradeClient

        print("Attempting to connect to Questrade API...")
        client = QuestradeClient()

        print("Calling get_accounts()...")
        accounts = client.get_accounts()

        if accounts and 'accounts' in accounts:
            num_accounts = len(accounts['accounts'])
            print(f"✅ API connection successful!")
            print(f"   Retrieved {num_accounts} account(s)")

            # Show basic account info (without sensitive details)
            for i, account in enumerate(accounts['accounts'], 1):
                print(f"\n   Account {i}:")
                print(f"     Type: {account.get('type', 'N/A')}")
                print(f"     Status: {account.get('status', 'N/A')}")

            return True
        else:
            print(f"❌ API call succeeded but returned unexpected data: {accounts}")
            return False

    except Exception as e:
        print(f"❌ API connection failed: {e}")
        print(f"\n   Error type: {type(e).__name__}")
        print(f"   Error details: {str(e)}")

        # Provide specific guidance based on error
        error_str = str(e)
        if "400" in error_str or "Bad Request" in error_str:
            print("\n   💡 This is the 'token used once' issue!")
            print("   See QUESTRADE_TOKEN_FIX.md for the complete fix.")
            print("   Quick fix: Generate a NEW token from Questrade portal")
        elif "refresh_token" in error_str.lower():
            print("\n   💡 Token configuration issue")
            print("   Check that QUESTRADE_REFRESH_TOKEN is set correctly")
        elif "no attribute" in error_str.lower():
            print("\n   💡 Code version mismatch detected!")
            print("   Your Docker container may be running old code.")
            print("   Fix: docker-compose build --no-cache && docker-compose up -d")

        return False


def main():
    """Run all diagnostic tests."""
    print("\n" + "="*70)
    print("QUESTRADE INTEGRATION DIAGNOSTIC TOOL")
    print("="*70)
    print()

    results = []

    # Run all tests
    results.append(("Library Installation", test_questrade_library()))
    results.append(("Wrapper Import", test_questrade_client_wrapper()))
    results.append(("Token Configuration", test_token_configuration()))
    results.append(("Client Instantiation", test_client_instantiation()))
    results.append(("API Connection", test_api_connection()))

    # Summary
    print("\n" + "="*70)
    print("DIAGNOSTIC SUMMARY")
    print("="*70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:10} {test_name}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED!")
        print("="*70)
        print("\nYour Questrade integration is working correctly!")
        print("All 15 Questrade tools should be available in your MCP client.")
        return 0
    else:
        print("\n" + "="*70)
        print("⚠️  SOME TESTS FAILED")
        print("="*70)
        print("\nPlease review the error messages above and:")
        print("1. Read QUESTRADE_TOKEN_FIX.md for common issues")
        print("2. Ensure Docker container is rebuilt with latest code")
        print("3. Verify your refresh token is valid and current")
        print("4. Run: docker-compose build --no-cache && docker-compose up -d")
        return 1


if __name__ == "__main__":
    sys.exit(main())
