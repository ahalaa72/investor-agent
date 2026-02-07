# Questrade API Setup Guide

## Critical Issue: Cloudflare User-Agent Blocking

**IMPORTANT:** As of January 2026, Questrade's API is protected by Cloudflare, which blocks requests without a `User-Agent` header (Cloudflare error 1010: Access Denied). The standard `questrade-api` Python library does NOT send User-Agent headers and will fail with `HTTP Error 403: Forbidden`.

### The Fix

A monkey-patch has been implemented in `investor_agent/questrade.py` that wraps `urllib.request.urlopen` to automatically add a User-Agent header to all requests:

```python
# Lines 38-61 in investor_agent/questrade.py
import urllib.request

_original_urlopen = urllib.request.urlopen

def _urlopen_with_user_agent(url, data=None, timeout=None, **kwargs):
    """Wrapper for urlopen that adds User-Agent header to prevent Cloudflare blocking."""
    if isinstance(url, str):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        req = urllib.request.Request(url, data=data, headers=headers)
        if timeout is not None:
            return _original_urlopen(req, timeout=timeout, **kwargs)
        return _original_urlopen(req, **kwargs)
    else:
        if not url.has_header('User-Agent'):
            url.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        if timeout is not None:
            return _original_urlopen(url, timeout=timeout, **kwargs)
        return _original_urlopen(url, **kwargs)

urllib.request.urlopen = _urlopen_with_user_agent
```

**This fix is MANDATORY** - without it, all Questrade API calls will fail with 403.

---

## Setup Instructions

### 1. Initial Setup

```bash
# Build the Docker image
docker build -t investor-agent-mcp .

# Create persistent volume for tokens
docker volume create questrade-tokens

# Get a fresh token from Questrade
# Go to: https://login.questrade.com/APIAccess/UserApps.aspx
# Click "Generate new token" and copy it

# Update .env file with your token
echo "QUESTRADE_REFRESH_TOKEN=YOUR_TOKEN_HERE" >> .env

# Start container with persistent volume
docker run -d --name investor-agent-mcp \
  -v questrade-tokens:/root \
  --env-file .env \
  investor-agent-mcp
```

### 2. Quick Setup with rebuild.sh

The project includes `rebuild.sh` which automates the setup:

```bash
# Ensure .env has your token
cat .env  # Should show QUESTRADE_REFRESH_TOKEN=...

# Run rebuild script
bash rebuild.sh

# The script will:
# 1. Build Docker image
# 2. Create persistent volume
# 3. Stop/remove old container
# 4. Start new container with volume
# 5. Run Gate 5 tests
```

### 3. Verify Setup

After starting the container, verify Questrade connectivity:

```bash
# Check token file exists in volume
docker exec investor-agent-mcp cat /root/.questrade.json

# Should show JSON with refresh_token
```

Then in Claude Code, test with:
```
get_questrade_accounts()
```

Should return 7 accounts with no errors.

---

## How Token Persistence Works

### Docker Volume Storage

The token is stored in a Docker volume mounted to `/root`:

```bash
docker run -d --name investor-agent-mcp \
  -v questrade-tokens:/root \  # <-- Volume mount
  --env-file .env \
  investor-agent-mcp
```

### Token Refresh Flow

1. **First API call:** Uses token from `.env` file
2. **Questrade response:** Returns new access_token + new refresh_token
3. **Library saves:** Writes to `/root/.questrade.json` (in Docker volume)
4. **Subsequent calls:** Use the refreshed token from file
5. **Auto-refresh:** Every ~4 minutes, token refreshes automatically
6. **Persistence:** Docker volume persists across container rebuilds

### Token File Structure

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJI...",
  "api_server": "https://api05.iq.questrade.com/",
  "expires_in": 1800,
  "refresh_token": "NEW_REFRESH_TOKEN_HERE",
  "token_type": "Bearer",
  "expires_at": "1738073594"
}
```

---

## Troubleshooting

### Error: HTTP Error 403: Forbidden

**Symptom:**
```
Failed to connect to Questrade API: HTTP Error 403: Forbidden
```

**Root Cause:** Cloudflare blocking requests without User-Agent header.

**Solution:** Verify the User-Agent monkey-patch is present in `investor_agent/questrade.py` (lines 38-61). If missing, the fix needs to be re-applied.

**Debug Steps:**
```bash
# Test raw API call without User-Agent (should fail)
docker exec investor-agent-mcp python -c "
import urllib.request
url = 'https://login.questrade.com/oauth2/token?grant_type=refresh_token&refresh_token=TEST'
try:
    urllib.request.urlopen(url)
except urllib.error.HTTPError as e:
    print(f'Error {e.code}: {e.read().decode()}')
"
# Output: Error 403: error code: 1010

# Test with User-Agent (should succeed or fail with different error)
docker exec investor-agent-mcp python -c "
import urllib.request
url = 'https://login.questrade.com/oauth2/token?grant_type=refresh_token&refresh_token=TEST'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    print(f'Error {e.code}: {e.read().decode()}')
"
# Output: Error 400: (different error, means Cloudflare allowed it through)
```

### Error: Token Already Consumed

**Symptom:**
```
Failed to connect to Questrade API: HTTP Error 400: Bad Request
```

**Root Cause:** Questrade refresh tokens are SINGLE-USE. Once consumed, they're dead forever.

**Solution:** Generate a fresh token from Questrade and update:

```bash
# Get new token from https://login.questrade.com/APIAccess/UserApps.aspx

# Update .env file
vim .env  # Set QUESTRADE_REFRESH_TOKEN=NEW_TOKEN

# Update token file in Docker volume
docker exec investor-agent-mcp bash -c 'cat > /root/.questrade.json << "EOF"
{
  "refresh_token": "NEW_TOKEN_HERE",
  "token_type": "Bearer"
}
EOF'

# Test
docker exec investor-agent-mcp python -m investor_agent.server
# Or in Claude Code: get_questrade_accounts()
```

### Token Not Persisting After Rebuild

**Symptom:** After `bash rebuild.sh`, token file is missing or empty.

**Diagnosis:**
```bash
# Check if volume exists
docker volume ls | grep questrade-tokens

# Check volume contents
docker run --rm -v questrade-tokens:/data alpine ls -la /data/

# Should show .questrade.json file
```

**Solution:** Ensure `rebuild.sh` uses the volume mount:

```bash
# Line 35 in rebuild.sh should be:
-v questrade-tokens:/root \
```

### Container Won't Start

**Symptom:** Container exits immediately after starting.

**Diagnosis:**
```bash
# Check logs
docker logs investor-agent-mcp

# Check entrypoint script
docker exec investor-agent-mcp cat /docker-entrypoint.sh
```

**Common Causes:**
1. Missing `.env` file
2. Entrypoint script has syntax errors
3. Python dependencies not installed

---

## Testing Checklist

After setup or rebuild, verify:

- [ ] Container is running: `docker ps | grep investor-agent-mcp`
- [ ] Token file exists: `docker exec investor-agent-mcp cat /root/.questrade.json`
- [ ] Token has all fields: `access_token`, `api_server`, `refresh_token`, `expires_in`, `expires_at`
- [ ] API call succeeds: `get_questrade_accounts()` returns 7 accounts
- [ ] Token persists after rebuild: Run `bash rebuild.sh`, then check token file still exists
- [ ] No need for new token: After successful setup, you should NEVER need to manually provide tokens again

---

## DO NOT Do These Things

❌ **DO NOT manually test tokens with Python scripts** - This consumes the single-use token before the MCP tool can use it.

❌ **DO NOT bind-mount the token file directly** - Docker on Mac has issues with atomic file replacement on bind mounts. Use a volume instead.

❌ **DO NOT run multiple containers** with the same token - First container consumes it, others fail.

❌ **DO NOT delete the Docker volume** - This destroys the persisted token.

❌ **DO NOT ignore Cloudflare 1010 errors** - This means User-Agent header is missing.

---

## Maintenance

### Backing Up Token

```bash
# Backup token from volume
docker cp investor-agent-mcp:/root/.questrade.json ./questrade_backup.json

# Restore token to volume
docker cp ./questrade_backup.json investor-agent-mcp:/root/.questrade.json
```

### Viewing Token Without Consuming

```bash
# Safe - just reads the file
docker exec investor-agent-mcp cat /root/.questrade.json | python3 -m json.tool

# UNSAFE - makes API call, consumes token
docker exec investor-agent-mcp python -c "from questrade_api import Questrade; q = Questrade(...)"
```

### Updating to New Token (if needed)

```bash
# Only do this if absolutely necessary (e.g., old token expired after 7 days of no use)

# Get new token from Questrade website
# Update .env
vim .env

# Update volume
docker exec investor-agent-mcp bash -c 'cat > /root/.questrade.json << "EOF"
{
  "refresh_token": "NEW_TOKEN_HERE",
  "token_type": "Bearer"
}
EOF'

# Restart container (optional)
docker restart investor-agent-mcp
```

---

## Technical Details

### Why Monkey-Patch?

The `questrade-api` library uses Python's built-in `urllib.request.urlopen()` which doesn't send User-Agent headers by default. Rather than forking the library or using a different HTTP client, we monkey-patch `urlopen` at import time to inject the header for all requests.

### Why Docker Volume?

Docker volumes provide:
1. Persistence across container rebuilds
2. Atomic file operations (no "Device or resource busy" errors)
3. Automatic mounting without host filesystem dependencies
4. Backup/restore capabilities

### Token Security

For production use, consider encrypting the token:

```bash
docker exec -it investor-agent-mcp python -m investor_agent.token_security encrypt
```

This creates an encrypted `.questrade.enc` file and deletes the plaintext `.questrade.json`. On container startup, you'll be prompted for the encryption password.

---

**Last Updated:** 2026-01-28 (after User-Agent fix)
