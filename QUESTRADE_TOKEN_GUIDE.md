# Questrade Token Management Guide

## Token Lifecycle Overview

Questrade uses **OAuth 2.0** with **single-use refresh tokens**. Understanding this is critical to avoid authentication errors.

### Key Facts

| Property | Value |
|----------|-------|
| **Access Token Lifetime** | 30 minutes (but refresh at 5 min for safety) |
| **Refresh Token** | **SINGLE-USE** - consumed on first API call |
| **Token Expiry** | 7 days if not used |
| **API Rate Limit** | 30,000 calls/day |

---

## Why Tokens "Expire" During Sessions

### The Single-Use Refresh Token Problem

```
Initial State:
┌─────────────────────────────────────┐
│ You get token from Questrade:       │
│ "C7O_hympinvpkEuYAjASKdzHs98IJlUr0" │
└─────────────────────────────────────┘
                 │
                 ▼
First API Call (e.g., get_questrade_accounts()):
┌─────────────────────────────────────┐
│ 1. Send refresh_token to Questrade  │
│ 2. Questrade INVALIDATES old token  │
│ 3. Returns: new access_token +      │
│    NEW refresh_token                │
│ 4. Library saves to ~/.questrade.json│
└─────────────────────────────────────┘
                 │
                 ▼
Original Token Status:
┌─────────────────────────────────────┐
│ "C7O_hympinvpkEuYAjASKdzHs98IJlUr0" │
│ Status: **DEAD** (consumed forever) │
└─────────────────────────────────────┘
```

### What Causes "Token Expired" Errors

1. **Container Restart Without Volume**: Token file lost, original env token is dead
2. **Multiple Container Instances**: First instance consumes token, others fail
3. **Manual Testing Outside Docker**: Consumes token, Docker instance fails
4. **Generating New Token in UI**: Invalidates all previous tokens

---

## Token File Location

The `questrade-api` library stores tokens at:

| Environment | Path |
|-------------|------|
| Docker Container | `/root/.questrade.json` |
| Local macOS | `~/.questrade.json` |
| Local Linux | `~/.questrade.json` |

### Token File Structure

```json
{
  "access_token": "eyJ0eXAiOiJKV1...",
  "api_server": "https://api05.iq.questrade.com/",
  "expires_in": 1800,
  "refresh_token": "NEW_REFRESH_TOKEN_HERE",
  "token_type": "Bearer"
}
```

---

## Best Practices for Token Management

### 1. Use Persistent Volume for Docker

**Recommended Setup:**

```bash
# Create a persistent volume for tokens
docker volume create questrade-tokens

# Run container with volume mounted
docker run -d \
  --name investor-agent-mcp \
  -v questrade-tokens:/root \
  -e QUESTRADE_REFRESH_TOKEN="YOUR_TOKEN" \
  investor-agent-mcp:latest
```

This ensures:
- Token file persists across container restarts
- New refresh tokens are saved and reused
- Only need to provide initial token once

### 2. Keep Container Running

The current setup uses `tail -f /dev/null` to keep the container alive. This is intentional:
- Container stays running continuously
- Token file is preserved in memory
- Claude Desktop can `docker exec` into it anytime

**DO NOT:**
- Stop/remove the container unnecessarily
- Create multiple containers with the same token

### 3. Use Token Security Module (Encryption)

For added security, use the encrypted token feature:

```bash
# Encrypt your token (inside container)
docker exec -it investor-agent-mcp python -m investor_agent.token_security encrypt

# Container will prompt for password
# Encrypted file: /root/.questrade.enc
# Token file deleted after encryption
```

When container starts with encrypted token:
1. Prompts for password (or uses `QUESTRADE_TOKEN_PASSWORD` env var)
2. Decrypts token to memory
3. Re-encrypts on shutdown

### 4. Single Instance Only

**NEVER run multiple containers** with the same Questrade token:
- First container consumes the refresh token
- Other containers get "HTTP 400 Bad Request"

---

## Getting a New Refresh Token

When you need a fresh token:

1. Go to: https://login.questrade.com/APIAccess/UserApps.aspx
2. Click **"Generate new token"** for your app
3. **IMPORTANT:** This invalidates ALL previous tokens immediately
4. Copy the new token and update your Docker container

```bash
# Stop old container
docker stop investor-agent-mcp
docker rm investor-agent-mcp

# Start with new token (use volume to persist)
docker run -d \
  --name investor-agent-mcp \
  -v questrade-tokens:/root \
  -e QUESTRADE_REFRESH_TOKEN="NEW_TOKEN_HERE" \
  investor-agent-mcp:latest
```

---

## Token Refresh Flow in Code

The `questrade.py` module handles token refresh automatically:

```python
def _get_client(self) -> Questrade:
    token_file_path = Path.home() / ".questrade.json"

    if token_file_path.exists():
        # Check if access token is about to expire (>4 min old)
        file_age_minutes = (time.time() - token_file_path.stat().st_mtime) / 60

        if file_age_minutes > 4:
            # Read stored refresh token and get new tokens
            with open(token_file_path, 'r') as f:
                token_data = json.load(f)
            client = Questrade(refresh_token=token_data['refresh_token'])
            # Library automatically saves new tokens
        else:
            # Use existing tokens (still fresh)
            client = Questrade()  # Reads from ~/.questrade.json
    else:
        # First time - use env var token
        client = Questrade(refresh_token=self.refresh_token)
        # Library saves tokens to ~/.questrade.json

    return client
```

---

## Troubleshooting

### Error: "HTTP Error 400: Bad Request"

**Cause:** Refresh token has been consumed

**Solution:**
1. Generate new token from Questrade website
2. Restart container with new token

### Error: "Questrade refresh token required"

**Cause:** No token in environment or file

**Solution:**
1. Set `QUESTRADE_REFRESH_TOKEN` environment variable
2. Or ensure `~/.questrade.json` exists with valid token

### Error: "argument length exceeds limit"

**Cause:** API response too large (happens with orders/activities)

**Solution:** Already handled in code with default date ranges

---

## Docker Volume Commands

```bash
# List volumes
docker volume ls

# Inspect token volume
docker volume inspect questrade-tokens

# Backup token file (if needed)
docker cp investor-agent-mcp:/root/.questrade.json ./questrade_backup.json

# Restore token file
docker cp ./questrade_backup.json investor-agent-mcp:/root/.questrade.json
```

---

## Current Container Setup

The `.mcp.json` file configures Claude Desktop to use:

```json
{
  "mcpServers": {
    "investor-agent": {
      "command": "docker",
      "args": [
        "exec", "-i", "investor-agent-mcp",
        "python", "-m", "investor_agent.server"
      ]
    }
  }
}
```

This requires the container to be running. Start it with:

```bash
# One-time setup with persistent volume
docker run -d \
  --name investor-agent-mcp \
  -v questrade-tokens:/root \
  -e QUESTRADE_REFRESH_TOKEN="YOUR_TOKEN" \
  investor-agent-mcp:latest
```

---

## Summary: Token Best Practices

| Do | Don't |
|----|-------|
| Use Docker volume for token persistence | Stop container unnecessarily |
| Keep single container running | Run multiple containers with same token |
| Use encrypted token for security | Share token files |
| Generate new token only when needed | Test manually while container is running |
| Check container logs for token issues | Ignore "400 Bad Request" errors |

---

**Last Updated:** 2025-12-20
