# Questrade Environment Setup Guide

## Quick Check Methods

### Method 1: Use the Checker Script (Recommended)
```bash
# With virtual environment
source .venv/bin/activate
python check_questrade_env.py
```

### Method 2: Check in Shell
```bash
# Check if variable is set
echo $QUESTRADE_REFRESH_TOKEN

# If it shows nothing, it's not set
# If it shows your token, it's set ✅
```

### Method 3: Check in Python
```python
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Check the variable
token = os.getenv("QUESTRADE_REFRESH_TOKEN")
if token:
    print(f"✅ Token is set (length: {len(token)})")
else:
    print("❌ Token is NOT set")
```

### Method 4: Check .env File
```bash
# Check if .env file exists
ls -la .env

# Check if token is in the file
grep QUESTRADE_REFRESH_TOKEN .env
```

### Method 5: Check Environment Variables
```bash
# List all environment variables containing "QUESTRADE"
env | grep -i questrade

# Or using printenv
printenv | grep -i questrade
```

---

## Setup Steps

### 1. Create .env File
```bash
cp .env.template .env
```

### 2. Get Your Questrade Refresh Token

1. Visit: https://www.questrade.com/api/
2. Log in to your Questrade account
3. Go to "Getting Started" section
4. Generate a **Manual Refresh Token** (not the Practice Account token!)
5. Copy the token (it will look like a long string of random characters)

### 3. Add Token to .env File
```bash
# Edit the .env file
nano .env   # or use your preferred editor

# Add this line (replace with your actual token):
QUESTRADE_REFRESH_TOKEN=YourActualTokenHere123456789abcdef
```

### 4. Verify Token is Loaded

**Option A: In Terminal**
```bash
# Source the .env file (if not using python-dotenv)
export $(grep -v '^#' .env | xargs)

# Check if loaded
echo $QUESTRADE_REFRESH_TOKEN
```

**Option B: Test with Python**
```bash
source .venv/bin/activate
python check_questrade_env.py
```

**Option C: Test with the MCP Server**
```bash
source .venv/bin/activate
python -c "from investor_agent.questrade import get_questrade_client; print('✅ Success!' if get_questrade_client() else '❌ Failed')"
```

---

## Common Issues

### Issue 1: Token Not Loading from .env File

**Symptom:** `echo $QUESTRADE_REFRESH_TOKEN` shows nothing

**Solutions:**
```bash
# Solution 1: Manually export the variable
export QUESTRADE_REFRESH_TOKEN="your_token_here"

# Solution 2: Source the .env file
set -a; source .env; set +a

# Solution 3: Use python-dotenv (automatic with investor-agent)
# Just make sure .env exists in the project root
```

### Issue 2: "questrade-api package not available"

**Solution:**
```bash
# Install with uv
uv sync --extra questrade

# Or with pip
pip install questrade-api
```

### Issue 3: Token Works in Shell but Not in Python

**Cause:** Python doesn't automatically read shell environment variables unless you export them

**Solution:**
```bash
# Make sure .env file exists
ls -la .env

# Run Python from the same directory as .env
cd /home/user/investor-agent
source .venv/bin/activate
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('Token loaded:', 'Yes' if os.getenv('QUESTRADE_REFRESH_TOKEN') else 'No')"
```

### Issue 4: "Refresh token required" Error

**This means the token is not being loaded. Check:**

1. .env file exists in project root
2. .env file contains `QUESTRADE_REFRESH_TOKEN=...`
3. Token value is not the template placeholder
4. No extra spaces around the `=` sign
5. No quotes around the token value (unless required by your shell)

**Correct format:**
```bash
QUESTRADE_REFRESH_TOKEN=abc123xyz456
```

**Incorrect formats:**
```bash
QUESTRADE_REFRESH_TOKEN = abc123xyz456    # ❌ spaces around =
QUESTRADE_REFRESH_TOKEN="abc123xyz456"    # ⚠️  might work but not recommended
QUESTRADE_REFRESH_TOKEN=your_questrade_refresh_token_here    # ❌ template value
```

---

## Testing the Tools

Once configured, test the Questrade tools:

```python
# In Python REPL with venv activated
from investor_agent.server import mcp

# List all tools (should include 3 Questrade tools)
tools = list(mcp._tool_manager._tools.keys())
questrade_tools = [t for t in tools if 'questrade' in t.lower()]
print(f"Questrade tools available: {questrade_tools}")

# Expected output:
# ['get_questrade_accounts', 'get_questrade_positions', 'get_questrade_balances']
```

---

## Security Notes

⚠️ **IMPORTANT SECURITY WARNINGS:**

1. **NEVER commit .env file to git**
   - .env is already in .gitignore
   - Always use .env.template for examples

2. **Keep your refresh token secret**
   - It provides full access to your Questrade account
   - Treat it like a password

3. **Rotate tokens regularly**
   - Generate new tokens periodically
   - Revoke old tokens when no longer needed

4. **Don't share logs containing tokens**
   - Sanitize logs before sharing
   - The checker script masks token values for security

---

## Quick Reference Commands

```bash
# Check if token is set
echo ${QUESTRADE_REFRESH_TOKEN:+SET} ${QUESTRADE_REFRESH_TOKEN:-NOT_SET}

# Set token temporarily (current session only)
export QUESTRADE_REFRESH_TOKEN="your_token"

# Check with investor-agent
source .venv/bin/activate
python check_questrade_env.py

# Test MCP server startup
python -m investor_agent.server
# Look for: "✅ questrade-api package is installed" in logs
```

---

## Additional Resources

- Questrade API Documentation: https://www.questrade.com/api/documentation
- Getting Started: https://www.questrade.com/api/documentation/getting-started
- Security: https://www.questrade.com/api/documentation/security
- Python dotenv docs: https://pypi.org/project/python-dotenv/
