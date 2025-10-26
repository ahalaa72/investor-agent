# Simplified AI Agent Workflow - Setup Guide

This simplified workflow solves all the node reference and HTTP Request issues. It uses a single Code node with fetch() for reliability.

## Quick Setup (5 Minutes)

### Step 1: Import the Workflow

1. Open n8n at http://localhost:5678
2. Click **"Workflows"** → **"Import from File"**
3. Select: `n8n/workflows/ai-agent-simplified.json`
4. The workflow will appear with 3 nodes only

### Step 2: Configure OpenAI API Key

**IMPORTANT:** You must add your OpenAI API key to the workflow.

1. Click on the **"AI Agent (All-in-One)"** node
2. Find this line in the code (around line 8):
   ```javascript
   const OPENAI_API_KEY = 'YOUR_OPENAI_KEY_HERE';
   ```
3. Replace `YOUR_OPENAI_KEY_HERE` with your actual OpenAI API key:
   ```javascript
   const OPENAI_API_KEY = 'sk-proj-xxxxx...';
   ```
4. Click **"Save"** (or Ctrl+S)

### Step 3: Activate the Workflow

1. Toggle the **"Active"** switch in the top-right to ON
2. The workflow is now ready!

## Testing

### Get the Webhook URL

1. Click on the **"Webhook"** node
2. Copy the **"Production URL"** (should be something like):
   ```
   http://localhost:5678/webhook/ai-agent-report
   ```

### Test via cURL

```bash
curl -X POST http://localhost:5678/webhook/ai-agent-report \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the top 5 gainers today and should I invest in them?"}'
```

### Test via Browser

Save this as `test-webhook.html` and open in browser:

```html
<!DOCTYPE html>
<html>
<head>
    <title>AI Agent Tester</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
        }
        textarea {
            width: 100%;
            height: 100px;
            margin: 10px 0;
            padding: 10px;
            font-size: 14px;
        }
        button {
            background: #0066cc;
            color: white;
            padding: 10px 20px;
            border: none;
            cursor: pointer;
            font-size: 16px;
            margin: 5px;
        }
        button:hover {
            background: #0052a3;
        }
        #result {
            margin-top: 20px;
            padding: 15px;
            background: #f5f5f5;
            border-radius: 5px;
            white-space: pre-wrap;
            font-family: monospace;
        }
        .loading {
            color: #666;
            font-style: italic;
        }
    </style>
</head>
<body>
    <h1>🤖 AI Agent Tester</h1>

    <h3>Quick Examples:</h3>
    <button onclick="setQuery('What are the top 5 gainers today?')">Top Gainers</button>
    <button onclick="setQuery('Should I invest in AAPL? Give me a detailed analysis.')">Analyze AAPL</button>
    <button onclick="setQuery('What is the market sentiment right now?')">Market Sentiment</button>

    <h3>Your Query:</h3>
    <textarea id="query" placeholder="Enter your investment question...">What are the top 5 gainers today and should I invest in them?</textarea>

    <button onclick="sendQuery()">🚀 Send Query</button>

    <h3>Response:</h3>
    <div id="result">Results will appear here...</div>

    <script>
        const WEBHOOK_URL = 'http://localhost:5678/webhook/ai-agent-report';

        function setQuery(text) {
            document.getElementById('query').value = text;
        }

        async function sendQuery() {
            const query = document.getElementById('query').value;
            const resultDiv = document.getElementById('result');

            if (!query.trim()) {
                resultDiv.textContent = 'Please enter a query first!';
                return;
            }

            resultDiv.innerHTML = '<div class="loading">🔄 AI Agent is working... This may take 10-30 seconds...</div>';

            try {
                const response = await fetch(WEBHOOK_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ query: query })
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();

                if (data.error) {
                    resultDiv.innerHTML = `<div style="color: red;">❌ Error: ${data.message}</div>`;
                } else {
                    // Display the report nicely
                    let output = `
<strong>📊 Investment Report</strong>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Query: ${data.query}
Time: ${new Date(data.timestamp).toLocaleString()}
Tools Used: ${data.tools_used.join(', ')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
${data.report}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Model: ${data.model}
Tokens Used: ${data.usage?.total_tokens || 'N/A'}
                    `;
                    resultDiv.innerHTML = output;
                }

            } catch (error) {
                resultDiv.innerHTML = `<div style="color: red;">❌ Error: ${error.message}</div>`;
            }
        }
    </script>
</body>
</html>
```

## How It Works

This workflow has **3 simple nodes**:

1. **Webhook** - Receives your query via POST request
2. **AI Agent (All-in-One)** - Does everything:
   - Fetches available MCP tools from bridge
   - Asks OpenAI GPT-4 which tools to use
   - Executes the selected tools
   - Asks OpenAI to synthesize a comprehensive report
   - Returns structured result
3. **Respond to Webhook** - Sends the report back to you

## Example Queries

Try these queries to test different tools:

```bash
# Market movers
curl -X POST http://localhost:5678/webhook/ai-agent-report \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the top gainers and losers today?"}'

# Stock analysis
curl -X POST http://localhost:5678/webhook/ai-agent-report \
  -H "Content-Type: application/json" \
  -d '{"query": "Should I invest in Tesla? Give me a detailed analysis."}'

# Market sentiment
curl -X POST http://localhost:5678/webhook/ai-agent-report \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the current market sentiment?"}'

# Insider trading
curl -X POST http://localhost:5678/webhook/ai-agent-report \
  -H "Content-Type: application/json" \
  -d '{"query": "Are there any significant insider trades in NVDA?"}'

# Multi-stock comparison
curl -X POST http://localhost:5678/webhook/ai-agent-report \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare AAPL, MSFT, and GOOGL. Which should I buy?"}'
```

## Expected Response Format

```json
{
  "query": "Your question here",
  "report": "# Investment Report\n\n## Executive Summary\n...",
  "timestamp": "2025-10-26T10:30:00.000Z",
  "tools_used": ["get_market_movers", "get_ticker_data"],
  "model": "gpt-4o",
  "usage": {
    "prompt_tokens": 1500,
    "completion_tokens": 800,
    "total_tokens": 2300
  }
}
```

## Troubleshooting

### Error: "OpenAI API error: 401"
- **Problem:** Invalid or missing API key
- **Solution:** Check you replaced `YOUR_OPENAI_KEY_HERE` with your actual OpenAI API key

### Error: "Failed to fetch tools"
- **Problem:** Bridge is not running or not accessible
- **Solution:**
  ```bash
  # Check if bridge is running
  docker ps | grep investor-agent-bridge

  # Test bridge directly
  curl http://localhost:8000/health

  # If not running, start it
  docker-compose -f docker-compose.n8n.yml up -d investor-agent-bridge
  ```

### Error: "Tool call failed: 422"
- **Problem:** Invalid tool arguments
- **Solution:** This is usually caught by the AI. Check the n8n execution logs for details.

### Workflow Takes Too Long
- **Normal:** First run can take 20-30 seconds (fetching tools, calling OpenAI twice, executing tools)
- **If > 60 seconds:** Check if specific tools are timing out in the bridge logs

## Viewing Execution Logs

To see what's happening:

1. In n8n, click **"Executions"** in the left sidebar
2. Click on the most recent execution
3. Click on the **"AI Agent (All-in-One)"** node
4. You'll see console.log outputs showing:
   - Which tools were fetched
   - What the AI decided to call
   - Tool execution results
   - Report generation

## Advantages of This Workflow

✅ **No HTTP Request Node Issues** - Uses fetch() instead
✅ **No Node Reference Errors** - All logic in one place
✅ **No Execution Order Problems** - Linear flow
✅ **Full Error Handling** - Try/catch throughout
✅ **Real AI Agent** - Autonomous tool selection and report synthesis
✅ **Comprehensive Reports** - Not just raw data, actual analysis
✅ **Easy to Debug** - All code visible in one node

## Next Steps

Once this is working:

1. **Customize the System Prompt** - Edit the financial analyst instructions
2. **Add RAG Integration** - Include investment books/documents in the context
3. **Schedule Reports** - Replace Webhook with Schedule trigger for daily reports
4. **Send to Slack/Email** - Add notification nodes after report generation
5. **Save to Database** - Store reports for historical tracking

---

**Need Help?** Check the console logs in the execution view, or test the bridge directly with `curl http://localhost:8000/tools`
