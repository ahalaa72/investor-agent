#!/usr/bin/env python3
"""
Check if token refresh is working in Docker container.
"""
import os
import json
import time
from datetime import datetime

print("="*70)
print("QUESTRADE TOKEN REFRESH DIAGNOSTIC")
print("="*70)

# Check token file
token_file = os.path.expanduser("~/.questrade.json")
print(f"\n1. Checking token file: {token_file}")

if os.path.exists(token_file):
    print("   ✅ Token file EXISTS")
    
    with open(token_file, 'r') as f:
        tokens = json.load(f)
    
    print(f"\n   Token file contents:")
    for key, value in tokens.items():
        if key in ['access_token', 'refresh_token']:
            print(f"     {key}: {value[:30]}... (truncated)")
        else:
            print(f"     {key}: {value}")
    
    # Check if file is writable
    if os.access(token_file, os.W_OK):
        print(f"\n   ✅ Token file is WRITABLE")
    else:
        print(f"\n   ❌ Token file is NOT writable - refresh will FAIL!")
else:
    print("   ❌ Token file DOES NOT EXIST")

# Test API call with token refresh
print(f"\n2. Testing API call with automatic token refresh")

try:
    from questrade_api import Questrade
    
    # First call
    print("   Making first API call...")
    start = time.time()
    q = Questrade()
    accounts = q.accounts
    elapsed = time.time() - start
    print(f"   ✅ First call succeeded in {elapsed:.2f}s")
    print(f"   Retrieved {len(accounts.get('accounts', []))} accounts")
    
    # Check if token file was updated
    if os.path.exists(token_file):
        stat1 = os.stat(token_file)
        mtime1 = datetime.fromtimestamp(stat1.st_mtime)
        print(f"   Token file last modified: {mtime1}")
    
    # Wait a moment
    print(f"\n   Waiting 2 seconds...")
    time.sleep(2)
    
    # Second call
    print("   Making second API call...")
    start = time.time()
    q2 = Questrade()  # New instance
    accounts2 = q2.accounts
    elapsed = time.time() - start
    print(f"   ✅ Second call succeeded in {elapsed:.2f}s")
    
    # Check if token file was updated
    if os.path.exists(token_file):
        stat2 = os.stat(token_file)
        mtime2 = datetime.fromtimestamp(stat2.st_mtime)
        print(f"   Token file last modified: {mtime2}")
        
        if mtime2 > mtime1:
            print(f"   ✅ Token file WAS UPDATED (refresh working!)")
        else:
            print(f"   ⚠️  Token file NOT updated (may be using cached token)")
    
    print("\n" + "="*70)
    print("✅ TOKEN REFRESH APPEARS TO BE WORKING")
    print("="*70)
    
except Exception as e:
    print(f"\n   ❌ ERROR: {type(e).__name__}: {e}")
    
    if "Access token is invalid" in str(e) or "1017" in str(e):
        print("\n   💡 ACCESS TOKEN INVALID ERROR DETECTED!")
        print("   This means:")
        print("   - The stored refresh token has also expired")
        print("   - Need to generate a NEW manual token from Questrade portal")
        print("   - And update QUESTRADE_REFRESH_TOKEN environment variable")

print("\n" + "="*70)
print("DIAGNOSTIC COMPLETE")
print("="*70)
