# MCP Client Configuration for Questrade Integration

## ⚠️ Current Issue

You're seeing this warning in the MCP server logs:
```
WARNING  questrade-api package not available. Install it with: pip install questrade-api
```

This means your MCP client is installing `investor-agent` **without** the optional `questrade-api` dependency.

---

## ✅ Solution

Update your MCP client configuration to install with the `[questrade]` extra.

### Step 1: Find Your Config File

The location depends on your operating system:

**Linux:**
```bash
~/.config/Claude/claude_desktop_config.json
```

**macOS:**
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

### Step 2: Update the Configuration

Open the config file and find the `investor-agent` or `investor` server entry.

**BEFORE (Incorrect - Missing questrade):**
```json
{
  "mcpServers": {
    "investor": {
      "command": "uvx",
      "args": ["investor-agent"]
    }
  }
}
```

**AFTER (Correct - With questrade support):**
```json
{
  "mcpServers": {
    "investor": {
      "command": "uvx",
      "args": ["--from", "investor-agent[questrade]", "investor-agent"],
      "env": {
        "QUESTRADE_REFRESH_TOKEN": "paste_your_actual_token_here"
      }
    }
  }
}
```

### Step 3: Add Your Questrade Token

1. Get your refresh token from: https://www.questrade.com/api/
2. Replace `paste_your_actual_token_here` with your actual token
3. Make sure there are NO extra quotes or spaces

Example with a fake token:
```json
{
  "mcpServers": {
    "investor": {
      "command": "uvx",
      "args": ["--from", "investor-agent[questrade]", "investor-agent"],
      "env": {
        "QUESTRADE_REFRESH_TOKEN": "KtXrC8PzW5BkfHqN2vLmYgDjS9RaE7U0"
      }
    }
  }
}
```

### Step 4: Restart Your MCP Client

- **Claude Desktop:** Quit and reopen the application
- **Other clients:** Follow their restart instructions

### Step 5: Verify It Works

After restart, check the logs again. You should see:

✅ **No warning** about questrade-api
✅ Server starts successfully
✅ Three new tools available:
   - `get_questrade_accounts`
   - `get_questrade_positions`
   - `get_questrade_balances`

---

## 🔍 What Changed?

The key change is in the `args` array:

```json
"args": ["--from", "investor-agent[questrade]", "investor-agent"]
```

This tells `uvx` to:
1. Install the package: `investor-agent[questrade]`
2. Run the command: `investor-agent`

The `[questrade]` part installs the optional `questrade-api` dependency.

---

## 🧪 Testing

Once configured, test the integration:

1. Open Claude Desktop (or your MCP client)
2. Ask: "List my Questrade accounts"
3. The AI should use the `get_questrade_accounts` tool
4. You should see your account information

---

## 🐛 Troubleshooting

### Still seeing the warning?

**Problem:** Config file not found
- **Solution:** Make sure you edited the correct file for your OS

**Problem:** Syntax error in JSON
- **Solution:** Validate your JSON at https://jsonlint.com/
- Common mistakes:
  - Missing commas between entries
  - Extra comma after last entry
  - Unbalanced brackets `{}` or `[]`

**Problem:** Token not working
- **Solution:** Verify:
  - Token is from Questrade API portal (not practice account)
  - No extra quotes or spaces around the token
  - Token hasn't expired (Questrade tokens expire after inactivity)

### Error: "Refresh token required"

This means the token isn't being passed to the server.

**Check:**
1. Token is in the `env` section of your config
2. Key name is exactly: `QUESTRADE_REFRESH_TOKEN`
3. No typos in the key or value

---

## 🔐 Security Note

**⚠️ Important:** Your Questrade refresh token provides full access to your account.

- Keep your config file secure
- Don't share your config file
- Don't commit it to git
- Consider using system environment variables instead

### Alternative: System Environment Variable

Instead of putting the token in the config file, you can set it as a system environment variable:

**Config (without token):**
```json
{
  "mcpServers": {
    "investor": {
      "command": "uvx",
      "args": ["--from", "investor-agent[questrade]", "investor-agent"]
    }
  }
}
```

**Then set in your shell:**

Linux/macOS:
```bash
export QUESTRADE_REFRESH_TOKEN="your_token_here"
```

Windows (PowerShell):
```powershell
$env:QUESTRADE_REFRESH_TOKEN="your_token_here"
```

Windows (CMD):
```cmd
set QUESTRADE_REFRESH_TOKEN=your_token_here
```

---

## 📚 Additional Resources

- **Questrade API Docs:** https://www.questrade.com/api/documentation
- **Getting Started:** https://www.questrade.com/api/documentation/getting-started
- **Setup Guide:** See `QUESTRADE_SETUP.md` in the repo
- **Environment Checker:** Run `python check_questrade_env.py` in the repo

---

## ✅ Quick Checklist

- [ ] Found my MCP config file
- [ ] Updated `args` to include `investor-agent[questrade]`
- [ ] Added `QUESTRADE_REFRESH_TOKEN` to config or environment
- [ ] Validated JSON syntax
- [ ] Restarted MCP client
- [ ] No warning in logs
- [ ] Questrade tools appear in tool list
- [ ] Successfully tested with "List my Questrade accounts"

---

**Need help?** Check the logs for specific error messages and refer to `QUESTRADE_SETUP.md` for detailed troubleshooting.
