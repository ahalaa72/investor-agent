# Questrade Refresh Token Guide

## The Problem

You're getting a **400 Bad Request** error because your refresh token is invalid or expired.

### Why Your Current Token Doesn't Work

```
Token used: 'IHlnNennUTolYZ5mnIIINx0kTlw3gZvh0'
Length: 33 characters ❌

Valid token length: 200-400+ characters ✅
```

**Questrade refresh tokens:**
- Are 300-400+ characters long
- Contain alphanumeric characters and special symbols
- Are Base64-encoded strings
- **Expire after being used once** (this is critical!)

## How to Get a Valid Refresh Token

### Step 1: Access Questrade API Portal

Go to: **https://login.questrade.com/APIAccess/UserApps.aspx**

### Step 2: Log In

Use your Questrade account credentials (same as your trading account).

### Step 3: Generate Token

1. Look for the **"My Apps"** section
2. Click **"Generate New Token"** or **"Manual Token Generation"**
3. You'll see a **Practice** vs **Production** option:
   - **Practice**: Use for testing (demo account, fake money)
   - **Production**: Use for real trading (real account, real money)

### Step 4: Copy the COMPLETE Token

⚠️ **CRITICAL**: You must copy the **ENTIRE** token string!

The token will look something like this (example):
```
hvW5FMJECbFG2cEi8GKQMJ0pZ6LhCDXvYPzYEVGy4p4t8CGWtqhCPqQVHMGJQPVMxCJVy...
[... continues for 300-400+ characters ...]
```

**Copy the FULL string** - don't truncate it!

### Step 5: Important Token Facts

🔴 **Tokens Expire After First Use**

When you first use a refresh token, Questrade API returns:
- A new access token (valid for ~30 minutes)
- A **new refresh token** (replaces the old one)

The `questrade-api` Python library **automatically handles this** by:
- Storing the new token in a config file: `~/.questrade.json`
- Using the new token for subsequent requests

### Step 6: Set Up Your Token

#### Option A: Environment Variable (Recommended for Development)

```bash
# In your terminal
export QUESTRADE_REFRESH_TOKEN='paste_your_very_long_token_here'
```

#### Option B: .env File (Recommended for Docker)

```bash
# Edit your .env file
nano .env

# Add this line:
QUESTRADE_REFRESH_TOKEN=paste_your_very_long_token_here

# Save and exit
```

#### Option C: Docker Compose (For Docker Deployment)

```yaml
# In docker-compose.yml
services:
  investor-agent:
    environment:
      - QUESTRADE_REFRESH_TOKEN=${QUESTRADE_REFRESH_TOKEN}
```

Then create `.env` file with the token.

## Testing Your Token

### Quick Test

Use the provided test script:

```bash
# Make it executable
chmod +x test_questrade_auth.py

# Run with environment variable
export QUESTRADE_REFRESH_TOKEN='your_token_here'
python test_questrade_auth.py

# Or pass token directly
python test_questrade_auth.py 'your_token_here'
```

### Expected Output (Success)

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
ACCOUNT INFORMATION
======================================================================

Account 1:
  Type: Margin
  Number: 12345678
  Status: Active
  Primary: True
  Billing: True

Account 2:
  Type: TFSA
  Number: 87654321
  Status: Active
  Primary: False
  Billing: False

======================================================================
✅ AUTHENTICATION TEST PASSED
======================================================================

Your Questrade integration is working correctly!
You can now use all 15 Questrade tools in investor-agent.
```

## Common Errors and Solutions

### Error: 400 Bad Request

**Cause**: Token is invalid or expired

**Solution**: Generate a **NEW** token from Questrade portal

```bash
# Get new token from: https://login.questrade.com/APIAccess/UserApps.aspx
export QUESTRADE_REFRESH_TOKEN='your_new_token_here'
python test_questrade_auth.py
```

### Error: Token Too Short

**Cause**: You copied an incomplete token

**Solution**:
1. Go back to Questrade portal
2. Generate a NEW token
3. **Select ALL** the text (it should be 300-400+ characters)
4. Copy and paste carefully

### Error: 401 Unauthorized

**Cause**: Invalid credentials or wrong token format

**Solution**:
- Verify you're using the **refresh token**, not access token
- Ensure no extra spaces or line breaks in the token
- Generate a fresh token

## Token Storage Locations

The `questrade-api` library stores updated tokens in:

```
~/.questrade.json
```

This file contains:
- The current access token
- The new refresh token (auto-updated)
- API server URL
- Token expiry time

**For Docker**: This file is inside the container, so it persists token updates between API calls but **resets when container restarts**. This is normal - the library will use your `QUESTRADE_REFRESH_TOKEN` env variable to get a new token on restart.

## Practice vs Production

### Practice Account (Testing)
- **Use this first!** Safe environment with fake money
- Test all tools without risk
- Same API interface as production
- Token URL: https://practicelogin.questrade.com/APIAccess/UserApps.aspx

### Production Account (Real Trading)
- Real money, real trades
- Only use after testing in practice
- Token URL: https://login.questrade.com/APIAccess/UserApps.aspx

## Security Best Practices

1. **Never commit tokens to git**
   ```bash
   # Add to .gitignore
   .env
   .questrade.json
   ```

2. **Use environment variables**
   - Keeps tokens out of code
   - Easy to rotate/update
   - Safe for Docker deployments

3. **Rotate tokens regularly**
   - Generate new tokens periodically
   - Revoke old tokens in Questrade portal

4. **Limit token permissions** (if available)
   - Only grant necessary API access
   - Use practice account for development

## Troubleshooting Checklist

- [ ] Token is 200-400+ characters long
- [ ] Token was copied completely (no truncation)
- [ ] No extra spaces or line breaks in token
- [ ] Token is the **refresh token**, not access token
- [ ] Token was generated from correct environment (practice vs production)
- [ ] Environment variable is set correctly
- [ ] `.env` file exists and is loaded
- [ ] Internet connection is working
- [ ] Questrade account is active and in good standing

## Need More Help?

1. **Test script output**: Run `python test_questrade_auth.py` and share the output
2. **Check token length**: `echo $QUESTRADE_REFRESH_TOKEN | wc -c` should show 300-400+
3. **Questrade API docs**: https://www.questrade.com/api/documentation
4. **Questrade support**: Contact them if account issues persist

## Quick Reference

| Task | Command |
|------|---------|
| Generate token | Visit https://login.questrade.com/APIAccess/UserApps.aspx |
| Set env variable | `export QUESTRADE_REFRESH_TOKEN='token'` |
| Test token | `python test_questrade_auth.py` |
| Check token length | `echo $QUESTRADE_REFRESH_TOKEN \| wc -c` |
| View stored config | `cat ~/.questrade.json` |

---

**Remember**: Questrade tokens expire after first use, but the `questrade-api` library handles this automatically by storing the updated token. Just make sure your initial token is valid!
