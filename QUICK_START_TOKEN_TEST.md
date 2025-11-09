# Quick Start: Test Your Current Questrade Token

Your current token is **valid until November 13, 2025 at 12:37 PM**. Let's test it!

## Your Token Info

- **Token**: `Arl9WrBqPDynFj0IRsONs2ZWQdClN41a0`
- **Expires**: November 13, 2025 at 12:37 PM
- **Days remaining**: ~4 days
- **Status**: ✅ Valid and unused (as long as you haven't used it elsewhere)

## Step 1: Verify Token in .env File

```bash
# Check if token is in .env
grep QUESTRADE_REFRESH_TOKEN .env

# Expected output:
# QUESTRADE_REFRESH_TOKEN=Arl9WrBqPDynFj0IRsONs2ZWQdClN41a0
```

If not there or different:
```bash
# Edit .env
nano .env

# Add or update this line:
QUESTRADE_REFRESH_TOKEN=Arl9WrBqPDynFj0IRsONs2ZWQdClN41a0

# Save: Ctrl+X, Y, Enter
```

## Step 2: Clean Up Old Token Files (Fresh Start)

```bash
# Delete old token file on host (if exists)
rm -f ~/.questrade.json

# Delete old token file in Docker
docker compose exec investor-agent rm -f /root/.questrade.json

# Expected: File deleted (or "No such file" - both OK)
```

## Step 3: Restart Docker Container

**Important**: Must use `down` then `up` to reload `.env`

```bash
# Stop container
docker compose down

# Start with fresh environment
docker compose up -d

# Verify it's running
docker compose ps
# Should show: investor-agent  Up
```

## Step 4: Test in Docker (Multiple API Calls)

```bash
# Test 1: First API call (will use manual token, create ~/.questrade.json)
docker compose exec investor-agent python -c "
from investor_agent.questrade import get_questrade_client
import os

print('🧪 Test 1: First API Call')
print(f'Token: {os.getenv(\"QUESTRADE_REFRESH_TOKEN\", \"NOT SET\")[:10]}...')

client = get_questrade_client()
accounts = client.get_accounts()
print(f'✅ Retrieved {len(accounts[\"accounts\"])} accounts')
print()

# Check if token file was created
if os.path.exists('/root/.questrade.json'):
    print('✅ Token file created: /root/.questrade.json')
else:
    print('⚠️  Token file not created')
"
```

Expected output:
```
🧪 Test 1: First API Call
Token: Arl9WrBqPD...
✅ Retrieved 7 accounts
✅ Token file created: /root/.questrade.json
```

If you see errors:
- **400 Bad Request**: Token already used - need to generate new one
- **524 Timeout**: Network issue or invalid token
- **Other errors**: Check Docker logs

```bash
# Test 2: Second API call (should use tokens from ~/.questrade.json)
docker compose exec investor-agent python -c "
from investor_agent.questrade import get_questrade_client

print('🧪 Test 2: Second API Call (reusing tokens)')
client = get_questrade_client()
accounts = client.get_accounts()
print(f'✅ Retrieved {len(accounts[\"accounts\"])} accounts')
"
```

Expected output:
```
🧪 Test 2: Second API Call (reusing tokens)
✅ Retrieved 7 accounts
```

```bash
# Test 3: Third API call
docker compose exec investor-agent python -c "
from investor_agent.questrade import get_questrade_client

print('🧪 Test 3: Third API Call')
client = get_questrade_client()
accounts = client.get_accounts()
print(f'✅ Retrieved {len(accounts[\"accounts\"])} accounts')
"
```

```bash
# Test 4: Verify token file persists
docker compose exec investor-agent python -c "
import os
import json
from pathlib import Path
from datetime import datetime

token_file = Path('/root/.questrade.json')
if token_file.exists():
    print('✅ Token file exists')

    # Show file age
    import time
    file_age_sec = time.time() - token_file.stat().st_mtime
    file_age_min = file_age_sec / 60
    print(f'   Age: {file_age_min:.1f} minutes')

    if file_age_min > 5:
        print('   ⚠️  Access token likely expired (next call will auto-refresh)')
    else:
        print('   ✅ Access token likely still valid')

    # Show token info (first 20 chars only)
    with open(token_file) as f:
        data = json.load(f)
    print(f'   Access token: {data.get(\"access_token\", \"\")[:20]}...')
    print(f'   Refresh token: {data.get(\"refresh_token\", \"\")[:20]}...')
else:
    print('❌ Token file does not exist')
"
```

Expected output:
```
✅ Token file exists
   Age: 0.2 minutes
   ✅ Access token likely still valid
   Access token: C9mZxTHb8cRy5L3pN...
   Refresh token: Df8kW2vYtBn4M1qZ...
```

## Step 5: Comprehensive Token Test

Run the comprehensive test script:

```bash
# In Docker
docker compose exec investor-agent python test_token_refresh.py
```

This will:
1. Check `.env` token configuration
2. Check `~/.questrade.json` state
3. Make 3 API calls
4. Show token file details
5. Verify everything is working

Expected output:
```
======================================================================
QUESTRADE TOKEN REFRESH TEST
======================================================================

1. Checking QUESTRADE_REFRESH_TOKEN environment variable...
✅ Token loaded (first 10 chars): Arl9WrBqPD...
   Token length: 32 characters

======================================================================
INITIAL TOKEN FILE STATE
======================================================================
✅ Token file exists: /root/.questrade.json
   Access token (first 20 chars): C9mZxTHb8cRy5L3pN...
   Refresh token (first 20 chars): Df8kW2vYtBn4M1qZ...
   API server: https://api01.iq.questrade.com/
   File age: 0.50 minutes
   ✅ Access token likely still valid (<5 min old)

======================================================================
TEST 1: First API Call
======================================================================
...
✅ Success: Retrieved 7 accounts in 0.45s

======================================================================
TEST SUMMARY
======================================================================
✅ Token refresh mechanism is working correctly!
```

## Step 6: Restart Claude Desktop

**On macOS:**
```bash
# Quit Claude Desktop completely
# Cmd+Q (or File → Quit)

# Wait 5 seconds

# Relaunch Claude Desktop
```

**On Windows:**
```
Close Claude Desktop
Wait 5 seconds
Relaunch Claude Desktop
```

## Step 7: Test in Claude Desktop

Open Claude Desktop and ask multiple questions using Questrade tools:

```
1. "What are my Questrade accounts?"
2. "Show me my current positions"
3. "What are my account balances?"
4. "Get me a quote for AAPL"
5. "Show me recent orders"
6. "What's my account activity for the last week?"
```

**Expected**: All 6+ questions should work without errors.

## Step 8: Verify Token Persistence

```bash
# Restart Docker container
docker compose restart investor-agent

# Wait 10 seconds
sleep 10

# Verify token file still exists
docker compose exec investor-agent ls -la /root/.questrade.json

# Make API call (should work immediately without new token)
docker compose exec investor-agent python -c "
from investor_agent.questrade import get_questrade_client
client = get_questrade_client()
accounts = client.get_accounts()
print(f'✅ After restart: {len(accounts[\"accounts\"])} accounts')
"
```

Expected output:
```
-rw-r--r-- 1 root root 482 Nov  9 XX:XX /root/.questrade.json
✅ After restart: 7 accounts
```

## Troubleshooting

### If Test 1 Fails with "400 Bad Request"

Your manual token has already been used. Generate a new one:

1. Go to: https://login.questrade.com/APIAccess/UserApps.aspx
2. Click "Generate New Token"
3. Copy the new token
4. Update `.env`:
   ```bash
   nano .env
   # Update: QUESTRADE_REFRESH_TOKEN=new_token_here
   ```
5. Restart: `docker compose down && docker compose up -d`
6. Retry Test 1

### If Test 1 Fails with "524 Timeout"

Network connectivity issue:

1. Check internet connection
2. Try again in 1-2 minutes
3. Check Questrade service status
4. If persists, try new token

### If Tests 2-3 Fail But Test 1 Succeeds

Token file not persisting:

```bash
# Verify volume exists
docker volume ls | grep questrade

# Expected output:
# investor-agent_questrade-tokens

# If missing, check docker-compose.yml has:
# volumes:
#   - questrade-tokens:/root
```

### If Token File Doesn't Exist After Test 1

Permission issue:

```bash
# Check Docker logs
docker compose logs investor-agent | tail -20

# Look for errors like:
# "Permission denied: /root/.questrade.json"
```

## Success Criteria

✅ Test 1: API call succeeds, creates `/root/.questrade.json`
✅ Test 2-3: API calls succeed using stored tokens
✅ Test 4: Token file exists and shows valid structure
✅ Test 5: Comprehensive test passes all checks
✅ Test 6: Claude Desktop can ask 5+ questions without errors
✅ Test 7: Token file persists after container restart

## What Happens Behind the Scenes

### First API Call (Test 1)
```
1. Code checks: Does /root/.questrade.json exist?
2. No → Use manual token from .env: Arl9WrBqPD...
3. Call Questrade API:
   POST https://login.questrade.com/oauth2/token
   grant_type=refresh_token&refresh_token=Arl9WrBqPD...
4. Response:
   {
     "access_token": "C9mZxTHb...",  // 5 min validity
     "refresh_token": "Df8kW2vY...", // 7 day validity (NEW!)
     "api_server": "https://api01.iq.questrade.com/"
   }
5. Save to /root/.questrade.json
6. Manual token (Arl9WrBqPD...) now CONSUMED
7. Make actual API call (get accounts)
```

### Second API Call (Test 2)
```
1. Code checks: Does /root/.questrade.json exist?
2. Yes → Load tokens from file
3. Check: Is access token expired?
4. File age: 0.2 minutes < 5 minutes → Still valid
5. Skip refresh, use existing access token
6. Make API call
```

### Sixth API Call (After 5+ Minutes)
```
1. Code checks: Does /root/.questrade.json exist?
2. Yes → Load tokens from file
3. Check: Is access token expired?
4. File age: 5.5 minutes > 5 minutes → Expired!
5. Auto-refresh:
   POST https://login.questrade.com/oauth2/token
   grant_type=refresh_token&refresh_token=Df8kW2vY...
6. Get NEW access token + NEW refresh token
7. Update /root/.questrade.json with new tokens
8. Make API call with fresh access token
```

This cycle continues indefinitely!

## Next Steps After Success

Once all tests pass:

1. **Use normally in Claude Desktop** - tokens will auto-refresh every 5 minutes
2. **No manual intervention needed** - as long as you use API within 7 days
3. **If unused for 7+ days**:
   - Refresh token expires
   - Generate new manual token
   - Delete `/root/.questrade.json`
   - Repeat setup

4. **Monitor token health** (optional):
   ```bash
   # Check token file age
   docker compose exec investor-agent python -c "
   import time
   from pathlib import Path
   token_file = Path('/root/.questrade.json')
   age_min = (time.time() - token_file.stat().st_mtime) / 60
   print(f'Token file age: {age_min:.1f} minutes')
   "
   ```

## Summary

Your token **Arl9WrBqPDynFj0IRsONs2ZWQdClN41a0** is valid until Nov 13.

After running these tests:
- ✅ First call consumes manual token, creates auto-refresh chain
- ✅ Subsequent calls use auto-refreshed tokens from `/root/.questrade.json`
- ✅ Access tokens refresh every 5 minutes automatically
- ✅ Refresh tokens renew every 7 days automatically
- ✅ You should never see token errors again!

**Important**: The manual token can only be used ONCE. After Test 1 succeeds, it's consumed and replaced by the auto-refresh chain.
