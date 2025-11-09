# Questrade Token Mechanics - Complete Guide

## Token Types and Expiration

### 1. Access Token
- **Duration**: 300 seconds (5 minutes)
- **Purpose**: Used for actual API calls
- **Refresh**: Must be refreshed before expiration
- **How it works**:
  - Included in every API request header
  - Checked by Questrade servers for validity
  - Auto-refreshed by `questrade-api` library when expired

### 2. Manual Refresh Token
- **Duration**: 7 days from generation
- **Purpose**: Bootstrap the token chain on first use
- **One-time use**: Can only be used ONCE
- **Where to get**: https://login.questrade.com/APIAccess/UserApps.aspx
- **Format**: 32-33 character string (e.g., `Arl9WrBqPDynFj0IRsONs2ZWQdClN41a0`)
- **After first use**: Replaced by auto-refreshing tokens

### 3. Auto-Refresh Token
- **Duration**: 7 days from last refresh
- **Purpose**: Get new access tokens automatically
- **Stored in**: `~/.questrade.json`
- **How it works**:
  - Each refresh returns NEW access token + NEW refresh token
  - Forms a continuous chain of valid tokens
  - Old refresh token becomes invalid after use

## Token Lifecycle

```
Day 0: Generate manual refresh token
       ↓
       Copy token: Arl9WrBqPDynFj0IRsONs2ZWQdClN41a0
       Valid until: Day 7
       ↓
First API Call:
       ↓
       POST https://login.questrade.com/oauth2/token
       grant_type=refresh_token
       refresh_token=Arl9WrBqPDynFj0IRsONs2ZWQdClN41a0
       ↓
Response:
       {
         "access_token": "abc123...",     ← Valid for 5 minutes
         "refresh_token": "xyz789...",    ← Valid for 7 days (NEW!)
         "api_server": "https://api01.iq.questrade.com/",
         "expires_in": 300
       }
       ↓
       Save to ~/.questrade.json
       Manual token (Arl9WrB...) now INVALID
       ↓
5 Minutes Later:
       ↓
       Access token expired
       ↓
       Library auto-refreshes using xyz789...
       ↓
       Gets NEW access token + NEW refresh token
       ↓
       Updates ~/.questrade.json
       ↓
This continues indefinitely...
```

## How questrade-api Library Handles This

### First Call (No ~/.questrade.json exists)

```python
from questrade_api import Questrade

# Uses manual refresh token
client = Questrade(refresh_token="Arl9WrBqPDynFj0IRsONs2ZWQdClN41a0")

# Behind the scenes:
# 1. Calls token endpoint with manual token
# 2. Gets access token + new refresh token
# 3. Saves both to ~/.questrade.json
# 4. Manual token is now consumed (can't use again)
```

**~/.questrade.json contents:**
```json
{
  "access_token": "abc123_valid_for_5_min",
  "refresh_token": "xyz789_valid_for_7_days",
  "api_server": "https://api01.iq.questrade.com/",
  "expires_in": 300
}
```

### Subsequent Calls (with ~/.questrade.json)

```python
# No token parameter needed - loads from file
client = Questrade()

# Behind the scenes:
# 1. Loads tokens from ~/.questrade.json
# 2. Checks if access token expired (stored timestamp vs current time)
# 3. If expired (>5 min old):
#    - Calls token endpoint with refresh token
#    - Gets NEW access token + NEW refresh token
#    - Updates ~/.questrade.json
# 4. Makes API call with (possibly refreshed) access token
```

### Every 5 Minutes (Automatic)

The library transparently:
1. Detects access token expiration
2. Uses current refresh token to get new tokens
3. Updates `~/.questrade.json`
4. Continues with API call

**You never have to manually refresh!**

## Common Issues and Solutions

### Issue 1: "400 Bad Request" After Working Once

**Cause**: Trying to reuse manual refresh token that was already consumed

**Solution**:
- Delete `~/.questrade.json`
- Generate NEW manual token from Questrade portal
- Update `.env` with new token
- Restart application

### Issue 2: Tokens Expire After 2 Questions

**Cause**: Token file not persisting between calls

**Likely reasons**:
1. Docker container not using volume persistence
2. Token file being deleted between calls
3. Different containers/processes using different token files

**Solution**:
```yaml
# docker-compose.yml
volumes:
  - questrade-tokens:/root  # Persist /root/.questrade.json
```

### Issue 3: HTTP 524 Timeout

**Cause**: Network connectivity to Questrade servers, or invalid token causing 2-minute timeout

**Solution**:
- Check network connectivity
- Try generating fresh manual token
- Check Questrade service status

### Issue 4: Token File Permissions

**Cause**: Application can't write to `~/.questrade.json`

**Solution**:
```bash
chmod 644 ~/.questrade.json
chown $USER ~/.questrade.json
```

## Best Practices

### 1. For Development (Local)

```bash
# .env file
QUESTRADE_REFRESH_TOKEN=Arl9WrBqPDynFj0IRsONs2ZWQdClN41a0

# First run
python -m investor_agent  # Creates ~/.questrade.json

# Subsequent runs
python -m investor_agent  # Uses ~/.questrade.json
```

**Token files**:
- Mac: `/Users/yourname/.questrade.json`
- Linux: `/home/yourname/.questrade.json`

### 2. For Docker Deployment

```yaml
# docker-compose.yml
services:
  investor-agent:
    volumes:
      - questrade-tokens:/root  # ← Critical for persistence
    env_file:
      - .env

volumes:
  questrade-tokens:  # Named volume
```

**Token files**:
- Container: `/root/.questrade.json`
- Volume: Persists across container restarts

**Important**: After updating `.env`:
```bash
docker-compose down  # Stop and remove container
docker-compose up -d  # Start with new .env
```

Using `docker-compose restart` will NOT reload `.env`!

### 3. Token Rotation Schedule

Since tokens auto-refresh, you don't need to do anything after initial setup!

The token chain continues indefinitely as long as:
- ✅ API calls happen at least once every 7 days (keeps refresh token valid)
- ✅ `~/.questrade.json` file persists
- ✅ Application can write to token file

If you don't use the API for 7+ days:
- Refresh token expires
- Generate new manual token from portal
- Delete old `~/.questrade.json`
- Restart application

## Testing Token Refresh

### Test Script

```bash
# Run comprehensive test
python test_token_refresh.py
```

This will:
1. Check manual token in `.env`
2. Check existing `~/.questrade.json`
3. Make 3 API calls
4. Show token file state
5. Verify auto-refresh works

### Manual Testing

```python
from investor_agent.questrade import get_questrade_client
import time

# Call 1
client = get_questrade_client()
accounts = client.get_accounts()
print(f"Call 1: {len(accounts['accounts'])} accounts")

# Call 2 (immediate - should use same access token)
accounts = client.get_accounts()
print(f"Call 2: {len(accounts['accounts'])} accounts")

# Wait 6 minutes, then call again
time.sleep(360)
accounts = client.get_accounts()
print(f"Call 3: {len(accounts['accounts'])} accounts")
# ↑ Should auto-refresh access token (was >5 min old)
```

### Docker Testing

```bash
# Test multiple calls in Docker
docker compose exec investor-agent python -c "
from investor_agent.questrade import get_questrade_client
client = get_questrade_client()
for i in range(5):
    accounts = client.get_accounts()
    print(f'Call {i+1}: {len(accounts[\"accounts\"])} accounts')
"

# Check token file exists and persists
docker compose exec investor-agent ls -la /root/.questrade.json

# Restart container and verify tokens persist
docker compose restart investor-agent
docker compose exec investor-agent ls -la /root/.questrade.json
# Should still exist (volume persistence)
```

## Security Considerations

### Token Storage

**Never commit tokens to git:**
```bash
# .gitignore
.env
.env.*
.questrade.json
```

**File permissions:**
```bash
chmod 600 ~/.questrade.json  # Read/write for owner only
```

### Token Exposure

If your manual refresh token is exposed:
1. Go to Questrade API portal
2. Generate NEW token (invalidates old one)
3. Update `.env`
4. Delete `~/.questrade.json`
5. Restart application

### Production Secrets

For production deployments:
```bash
# Use secret management (not .env files)
docker secret create questrade_token -
# Paste token, Ctrl+D

# docker-compose.yml
services:
  investor-agent:
    secrets:
      - questrade_token
```

## Monitoring Token Health

### Check Token File Age

```bash
# Mac/Linux
stat -f "%Sm" ~/.questrade.json

# Check if >5 minutes old (next call will refresh)
find ~/.questrade.json -mmin +5
```

### Check Token Expiration

```python
import json
import time
from pathlib import Path

token_file = Path.home() / ".questrade.json"
with open(token_file) as f:
    data = json.load(f)

file_age_seconds = time.time() - token_file.stat().st_mtime
file_age_minutes = file_age_seconds / 60

if file_age_minutes > 5:
    print("⚠️  Access token likely expired - will auto-refresh on next call")
else:
    print(f"✅ Access token likely valid ({file_age_minutes:.1f} min old)")
```

## Summary

| Token Type | Duration | Purpose | Can Reuse? |
|------------|----------|---------|------------|
| Access Token | 5 minutes | API calls | Auto-refreshed |
| Manual Refresh | 7 days | Bootstrap | ❌ One-time only |
| Auto Refresh | 7 days | Get new access tokens | ✅ Until expiry |

**Key Takeaway**: After initial setup with manual token, the `questrade-api` library handles everything automatically. You should never see token errors in normal operation as long as:
1. `~/.questrade.json` persists between calls
2. API is used at least once every 7 days
3. Application has write permissions to token file
