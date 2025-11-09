#!/usr/bin/env python3
"""
Debug script to check what's in ~/.questrade.json and what the API returns.
"""

import os
import json
from questrade_api import Questrade

print("="*70)
print("QUESTRADE TOKEN DEBUG SCRIPT")
print("="*70)

# Check if token file exists
token_file = os.path.expanduser("~/.questrade.json")
print(f"\n1. Checking for token file: {token_file}")

if os.path.exists(token_file):
    print("   ✅ Token file EXISTS")

    # Read and display contents
    try:
        with open(token_file, 'r') as f:
            token_data = json.load(f)

        print("\n   Token file contents:")
        for key, value in token_data.items():
            if key in ['access_token', 'refresh_token']:
                # Show only first 20 chars for security
                print(f"     {key}: {value[:20]}... (truncated)")
            else:
                print(f"     {key}: {value}")
    except Exception as e:
        print(f"   ❌ Error reading token file: {e}")
else:
    print("   ❌ Token file DOES NOT EXIST")

# Try to create Questrade client
print("\n2. Testing Questrade client initialization")

try:
    # Try without refresh token (should use stored tokens)
    print("   Attempting: Questrade() - using stored tokens")
    q = Questrade()
    print("   ✅ Client created successfully")

    # Try to get accounts
    print("\n3. Testing accounts API call")
    print("   Calling: q.accounts")

    accounts = q.accounts

    print(f"   Response type: {type(accounts)}")
    print(f"   Response value: {accounts}")

    if isinstance(accounts, dict):
        print(f"\n   Response keys: {list(accounts.keys())}")

        if 'accounts' in accounts:
            print(f"   ✅ 'accounts' key found!")
            print(f"   Number of accounts: {len(accounts['accounts'])}")
        else:
            print(f"   ❌ 'accounts' key NOT found")
            print(f"   Available keys: {list(accounts.keys())}")
    else:
        print(f"   ❌ Response is not a dict, it's: {type(accounts)}")

except Exception as e:
    print(f"   ❌ Error: {type(e).__name__}: {e}")

    import traceback
    print("\n   Full traceback:")
    traceback.print_exc()

print("\n" + "="*70)
print("DEBUG COMPLETE")
print("="*70)
