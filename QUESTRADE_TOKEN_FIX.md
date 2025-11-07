# Questrade Token "Worked Once, Now Bad Request" - Complete Fix Guide

## 🔴 The Problem You're Experiencing

**Symptom**: Token worked the first time, now getting `400 Bad Request` error

**Root Cause**: This is the **#1 most common Questrade API issue** and it's caused by Questrade's token refresh mechanism.

---

## 🎯 Why This Happens

### Questrade's Token System Works Like This:

1. **Manual Refresh Token** (from portal)
   - Generated at: https://login.questrade.com/APIAccess/UserApps.aspx
   - **Can only be used ONCE** ⚠️
   - Expires in 7 days if unused

2. **First API Call** (when it worked)
   - Your manual token → Questrade API
   - Response includes:
     - `access_token` (expires in 30 minutes)
     - `refresh_token` (NEW token, different from manual token)
     - `api_server` (specific endpoint like api01, api06, etc.)
   - Library stores these in `~/.questrade.json`

3. **Second API Call** (400 Bad Request)
   - You tried to reuse the original manual token
   - **That token is now invalid** (already consumed)
   - Questrade returns 400 Bad Request

### The Token Flow:

```
Manual Token (from portal)
    ↓ [use once]
Access Token (30 min) + Refresh Token (new)
    ↓ [after 30 min or new session]
Refresh Token
    ↓ [use once]
NEW Access Token (30 min) + NEW Refresh Token
    ↓ [repeat...]
```

**Key Point**: Each refresh token can **only be used once**. After using it, you get a NEW refresh token.

---

## ✅ The Solution

The `questrade-api` Python library **automatically handles this** by storing updated tokens in `~/.questrade.json`. However, there are scenarios where this fails:

### Scenario 1: Docker Environment (Most Likely Your Case)

**Problem**: In Docker, `~/.questrade.json` is inside the container and gets **deleted on container restart**.

**Fix Options**:

#### Option A: Use Environment Variable (Recommended for Docker)

The library will use your `QUESTRADE_REFRESH_TOKEN` env variable on each container restart:

```bash
# 1. Generate a NEW manual token from Questrade portal
# https://login.questrade.com/APIAccess/UserApps.aspx

# 2. Update your .env file with the NEW token
QUESTRADE_REFRESH_TOKEN=your_new_very_long_token_here

# 3. Rebuild and restart container
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**Important**: You'll need to generate a new manual token and update `.env` each time you restart the Docker container, because:
- Container restart → `~/.questrade.json` is lost
- Library tries to use env variable as manual token
- If that token was already used, you get 400 error

#### Option B: Persist Token File with Docker Volume (Better Solution)

Add a volume mount to preserve the token file across restarts:

```yaml
# In docker-compose.yml
services:
  investor-agent:
    volumes:
      - questrade-tokens:/root  # Persist ~/.questrade.json
    environment:
      - QUESTRADE_REFRESH_TOKEN=${QUESTRADE_REFRESH_TOKEN}

volumes:
  questrade-tokens:
```

This way:
1. First run: Uses `QUESTRADE_REFRESH_TOKEN` from env
2. Library saves updated tokens to `~/.questrade.json`
3. Container restart: Token file persists (no need for new manual token!)

### Scenario 2: Local Development (Non-Docker)

**Problem**: `~/.questrade.json` exists but contains expired tokens.

**Fix**:

```bash
# 1. Check the token file
cat ~/.questrade.json

# 2. Delete it
rm ~/.questrade.json

# 3. Generate a NEW manual token from Questrade portal

# 4. Set environment variable
export QUESTRADE_REFRESH_TOKEN='your_new_token'

# 5. Test
python test_questrade_auth.py
```

### Scenario 3: Token File Permissions Issue

**Problem**: Library can't write to `~/.questrade.json` to save updated tokens.

**Fix**:

```bash
# Check if file exists and permissions
ls -la ~/.questrade.json

# If it exists, make it writable
chmod 600 ~/.questrade.json

# Or delete and let library recreate it
rm ~/.questrade.json
```

---

## 🔧 Step-by-Step Fix (Docker Users)

### Quick Fix (Temporary - Works Until Next Restart)

```bash
# 1. Generate NEW token from Questrade
# https://login.questrade.com/APIAccess/UserApps.aspx

# 2. Update .env file
nano .env
# Change QUESTRADE_REFRESH_TOKEN to your NEW token

# 3. Restart container
docker-compose restart investor-agent

# 4. Test
docker-compose logs investor-agent | grep -i questrade
```

### Permanent Fix (Recommended - Persists Across Restarts)

```bash
# 1. Stop container
docker-compose down

# 2. Edit docker-compose.yml to add volume
nano docker-compose.yml
```

Add this to your `investor-agent` service:

```yaml
services:
  investor-agent:
    # ... existing config ...
    volumes:
      - questrade-tokens:/root
    environment:
      - QUESTRADE_REFRESH_TOKEN=${QUESTRADE_REFRESH_TOKEN}

# Add at bottom of file
volumes:
  questrade-tokens:
```

```bash
# 3. Generate NEW manual token from Questrade portal

# 4. Update .env with NEW token
nano .env

# 5. Rebuild and start
docker-compose build --no-cache
docker-compose up -d

# 6. Verify tokens are working
docker-compose exec investor-agent ls -la /root/.questrade.json

# 7. Test API call
docker-compose logs investor-agent
```

Now when you restart the container, the token file persists and you **don't need a new manual token**!

---

## 🧪 Testing Your Fix

### Test Script

```bash
# Inside container
docker-compose exec investor-agent python test_questrade_auth.py

# Or with your local Python
python test_questrade_auth.py
```

### Expected Success Output:

```
======================================================================
QUESTRADE API AUTHENTICATION TEST
======================================================================

Step 1: Validating token format...
📏 Token length: 345 characters
✅ Token length looks reasonable

Step 2: Testing authentication with Questrade API...
✅ Successfully created Questrade client

Step 3: Testing API call (get accounts)...
✅ Successfully retrieved accounts: 2 account(s) found

======================================================================
✅ AUTHENTICATION TEST PASSED
======================================================================
```

### If You Still Get 400 Error:

```bash
# 1. Check what token is being used
echo $QUESTRADE_REFRESH_TOKEN | wc -c
# Should be 300-400+ characters

# 2. Check if token file exists
docker-compose exec investor-agent cat /root/.questrade.json
# or locally: cat ~/.questrade.json

# 3. Delete token file and try with fresh manual token
docker-compose exec investor-agent rm -f /root/.questrade.json
# or locally: rm ~/.questrade.json

# 4. Generate BRAND NEW manual token from Questrade

# 5. Update .env with NEW token

# 6. Restart
docker-compose restart investor-agent
```

---

## 📊 Understanding ~/.questrade.json

When working correctly, the file looks like this:

```json
{
  "access_token": "vxcj7h3fh47fh47fh4...",
  "api_server": "https://api06.iq.questrade.com/",
  "expires_in": 1800,
  "refresh_token": "xj4h7fh4fh4fh4f...",
  "token_type": "Bearer"
}
```

**Key Fields**:
- `access_token`: Valid for 30 minutes, used for API calls
- `refresh_token`: Used to get next access token (changes every time!)
- `api_server`: Specific endpoint (api01, api06, etc.) - changes!
- `expires_in`: 1800 seconds (30 minutes)

**How the library uses it**:
1. Check if access_token is expired
2. If expired, use refresh_token to get new tokens
3. Save NEW tokens back to this file
4. Make API call with access_token

---

## 🚨 Common Mistakes

### ❌ Mistake 1: Reusing the Original Manual Token

```python
# DON'T DO THIS
token = "manual_token_from_portal"
q = Questrade(refresh_token=token)  # Works first time
# Later...
q = Questrade(refresh_token=token)  # 400 ERROR - token already used!
```

### ✅ Correct Approach:

```python
# First time only - provide manual token
q = Questrade(refresh_token="manual_token_from_portal")
# Library saves tokens to ~/.questrade.json

# All subsequent calls - no token needed!
q = Questrade()  # Reads from ~/.questrade.json
```

### ❌ Mistake 2: Hardcoding API Server

```python
# DON'T DO THIS
url = "https://api01.iq.questrade.com/v1/accounts"  # Wrong!
```

The API server changes (api01, api06, api12, etc.) and is included in the token response. Always use the `api_server` from the auth response.

### ❌ Mistake 3: Not Handling Token Storage in Docker

Without volume persistence, Docker containers lose `~/.questrade.json` on restart, forcing you to use a new manual token each time.

---

## 🔍 Debugging Commands

```bash
# Check env variable is set
echo $QUESTRADE_REFRESH_TOKEN

# Check token length (should be 300-400+)
echo $QUESTRADE_REFRESH_TOKEN | wc -c

# Check if token file exists (Docker)
docker-compose exec investor-agent ls -la /root/.questrade.json

# View token file contents (Docker)
docker-compose exec investor-agent cat /root/.questrade.json

# Delete token file and force refresh (Docker)
docker-compose exec investor-agent rm /root/.questrade.json

# View container logs
docker-compose logs investor-agent | grep -i questrade

# Check volume exists
docker volume ls | grep questrade

# Inspect volume
docker volume inspect investor-agent_questrade-tokens
```

---

## 📝 Best Practices

### 1. Use Practice Account First

Test with Questrade Practice environment:
- Portal: https://practicelogin.questrade.com/APIAccess/UserApps.aspx
- Same API, fake money
- Safe for testing

### 2. Implement Volume Persistence (Docker)

Always persist `~/.questrade.json` in Docker:

```yaml
volumes:
  - questrade-tokens:/root
```

### 3. Monitor Token Expiry

The library handles this, but be aware:
- Access tokens: 30 minutes
- Refresh tokens: 3 days (auto-updated)
- Manual tokens: 7 days (if unused)

### 4. Error Handling in Code

```python
from questrade_api import Questrade

try:
    q = Questrade()  # Try using stored tokens
except Exception as e:
    if "400" in str(e):
        # Token invalid - need new manual token
        logger.error("Refresh token invalid. Generate new token from Questrade portal.")
        raise
```

### 5. Keep Manual Token Handy

Store your current manual token securely in case you need to regenerate the session after container restart (if not using volume persistence).

---

## 🎯 Quick Troubleshooting Checklist

- [ ] Generated a **BRAND NEW** token from Questrade portal (last 5 minutes)
- [ ] Token is 300-400+ characters long
- [ ] Copied the **complete** token (no truncation)
- [ ] Updated `.env` file with new token
- [ ] Restarted Docker container: `docker-compose restart`
- [ ] Or rebuilt container: `docker-compose build --no-cache && docker-compose up -d`
- [ ] Checked container logs: `docker-compose logs investor-agent`
- [ ] Verified `~/.questrade.json` exists inside container
- [ ] Added volume persistence to `docker-compose.yml` (for permanent fix)
- [ ] Using Practice account for testing (recommended)
- [ ] Internet connection is working
- [ ] Questrade account is active

---

## 🆘 Still Not Working?

### Generate Fresh Token Right Now:

1. Go to: https://login.questrade.com/APIAccess/UserApps.aspx
2. Click "Generate New Token"
3. Select "Manual Token Generation"
4. Choose "Practice" or "Production"
5. **Copy the ENTIRE token** (300-400+ characters)
6. Update `.env` file immediately
7. Restart container within 5 minutes
8. Run test script

### Check These Common Issues:

1. **Old token in .env**: Make sure you updated the file
2. **Container not restarted**: Run `docker-compose restart investor-agent`
3. **Typo in token**: Regenerate and copy carefully
4. **Wrong environment**: Practice tokens only work with practice API
5. **Concurrent usage**: Only one process should use the token at a time

---

## 📚 Additional Resources

- **Questrade API Docs**: https://www.questrade.com/api/documentation
- **Authorization Guide**: https://www.questrade.com/api/documentation/authorization
- **Security Guide**: https://www.questrade.com/api/documentation/security
- **Test Script**: `test_questrade_auth.py` (in this repo)
- **Token Guide**: `QUESTRADE_TOKEN_GUIDE.md` (in this repo)

---

## 💡 Summary

The "worked once, now 400 error" issue happens because:

1. ✅ **First call**: Manual token → get access_token + new refresh_token
2. ❌ **Second call**: Try to reuse manual token → 400 error (already consumed)

**The Fix**:
- Let the library handle token refresh by storing `~/.questrade.json`
- In Docker, persist this file with a volume mount
- Only provide manual token once (first time or after file is deleted)

**Remember**: Each token can only be used once. The library manages this automatically if you let it persist the token file!
