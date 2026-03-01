# Claude Code Subprocess (`claude -p`) — Findings & Solution

## Summary

Running `claude -p` as a subprocess from a Python server on macOS required solving 3 layered auth/env issues. This document captures all findings for future reference.

## The 3-Layer Problem

| Layer | Symptom | Root Cause | Fix |
|-------|---------|------------|-----|
| 1 | Zero output, process hangs | `CLAUDECODE=1` env var inherited from VS Code | Whitelist env (`_build_clean_env()`) |
| 2 | 25 chars: "Credit balance is too low" | `ANTHROPIC_API_KEY` in env → API billing | Remove API key from clean env |
| 3 | "OAuth token has expired" / silent exit 1 | Keychain naming bug (Issue #9403) | `claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN` |

## Solution: `_build_clean_env()`

Build env from scratch (whitelist), never inherit from parent process:

```python
def _build_clean_env() -> dict:
    env = {
        "HOME": os.environ["HOME"],
        "USER": os.environ.get("USER", "AhmedE"),
        "SHELL": os.environ.get("SHELL", "/bin/zsh"),
        "PATH": f"{CLAUDE_PATH}:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "en_US.UTF-8",
        "TERM": "xterm-256color",
        "NVM_DIR": os.environ.get("NVM_DIR", ""),
        "NODE_PATH": os.environ.get("NODE_PATH", ""),
        "SSL_CERT_FILE": os.environ.get("SSL_CERT_FILE", ""),
        "REQUESTS_CA_BUNDLE": os.environ.get("REQUESTS_CA_BUNDLE", ""),
        "XDG_CONFIG_HOME": os.environ.get("XDG_CONFIG_HOME", ""),
        "XDG_DATA_HOME": os.environ.get("XDG_DATA_HOME", ""),
        "XDG_CACHE_HOME": os.environ.get("XDG_CACHE_HOME", ""),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
    }
    # Auth: persistent setup-token bypasses Keychain naming bug
    # Read from environment — set via: export CLAUDE_CODE_OAUTH_TOKEN=$(claude setup-token)
    oauth = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if oauth:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth
    env["CLAUDE_CODE_DONT_INHERIT_ENV"] = "1"
    return {k: v for k, v in env.items() if v}
```

## Key Flags for `claude -p`

```python
base_cmd = [
    CLAUDE_BIN, "-p",
    "--dangerously-skip-permissions",
    "--output-format", "stream-json",
    "--verbose",
    "--input-format", "stream-json",
    "--include-partial-messages",  # Required for streaming deltas
]
```

| Flag | Purpose |
|------|---------|
| `--input-format stream-json` | Pipe prompt via stdin (avoids ARG_MAX for large prompts) |
| `--output-format stream-json` | Structured JSON events on stdout |
| `--include-partial-messages` | Enables `content_block_delta` streaming events |
| `--no-session-persistence` | Don't save session to disk (for resolver/no-MCP path) |
| `--dangerously-skip-permissions` | Headless mode, no permission prompts |

## Stdin Format

```json
{"type":"user","message":{"role":"user","content":[{"type":"text","text":"Your prompt here"}]}}
```

Feed via stdin then close:

```python
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, ...)
user_msg = json.dumps({"type":"user","message":{"role":"user","content":[{"type":"text","text":prompt}]}})
proc.stdin.write(user_msg.encode() + b"\n")
proc.stdin.flush()
proc.stdin.close()
```

## Stream Event Types

With `--include-partial-messages`:

| Event Type | Contains | When |
|------------|----------|------|
| `system` (subtype `init`) | `session_id` | First event |
| `stream_event` → `content_block_delta` | `delta.text` | Incremental text chunks |
| `stream_event` → `tool_use` | Tool calls | When Claude uses tools |
| `assistant` | Complete message | After model finishes |
| `result` | Final result text | Last event |

## UI Streaming Bug: `stream_event` Wrapper Not Unwrapped

### Problem

With `--include-partial-messages`, text deltas arrive wrapped in a `stream_event` envelope:

```json
{"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello"}}}
```

The original code handled `content_block_delta` as a **top-level** event type (line 684), which only fires **without** `--include-partial-messages`. With the flag enabled, the top-level type is `stream_event` — which fell into the `else` branch and was silently logged as `Event: stream_event` with no text extraction or UI push.

**Result:** Pipeline completed successfully (13,799 chars saved to vault), but the UI showed zero streaming output — users saw nothing during generation.

### Fix

Added a `stream_event` handler that unwraps the inner event and processes it identically to the top-level `content_block_delta` handler:

```python
elif etype == "stream_event":
    inner = ev.get("event", {})
    inner_type = inner.get("type", "")
    if inner_type == "content_block_delta":
        delta = inner.get("delta", {})
        if delta.get("type") == "text_delta":
            txt = delta.get("text", "")
            if txt:
                text_parts.append(txt)
                push(pq, stage, "streaming", "", txt)  # → SSE → browser UI
```

### Event Flow (with fix)

```
claude -p stdout → JSON parse → type="stream_event"
                                 → unwrap inner event
                                 → type="content_block_delta"
                                 → extract delta.text
                                 → push to SSE queue → browser UI renders live
```

---

## SSE Streaming Through Cloudflare Quick Tunnel — SOLVED

**Status:** ✅ IMPLEMENTED & VERIFIED — WebSocket endpoint added alongside SSE. Client auto-detects HTTPS→WS, HTTP→SSE. Confirmed working: 2,161 events streamed through Cloudflare Quick Tunnel to phone via WebSocket (2026-03-01).

### Root Cause (Confirmed)

This is a **known, open bug in `cloudflared`** (Issue #1449, opened April 2025, still open as of March 2026):

> **SSE over GET is not streamed in real-time on Quick Tunnel — all data is flushed only after the server closes the connection.**

Key facts from the issue and Cloudflare docs:

- When using `cloudflared tunnel --url` (Quick Tunnels / trycloudflare.com), SSE responses over **GET requests are buffered entirely** at the Cloudflare edge and only flushed when the server closes the connection.
- This happens **regardless of headers** (`X-Accel-Buffering: no`, `Cache-Control: no-cache`, `Transfer-Encoding: chunked` — none of them work).
- Interestingly, **POST requests with `text/event-stream` DO stream in real-time** through quick tunnels. This is a GET-specific buffering behavior.
- The official Cloudflare Tunnel docs confirm: *"Proxied traffic through Cloudflare Tunnel is buffered by default unless the origin server includes `Content-Type: text/event-stream`."* We DO set this header, yet buffering still occurs on quick tunnels — meaning the fix in the docs applies to named/managed tunnels, NOT quick tunnels.
- Named/managed tunnels (requiring a Cloudflare account + DNS setup) may behave differently and could work with SSE.

### Why Our Headers Don't Work

All the headers we added (`X-Accel-Buffering: no`, `Cache-Control: no-cache`, `Connection: keep-alive`, keepalive comments every 5s) are the right approach for **Nginx/paid Cloudflare proxy**. They don't work for Quick Tunnels because the buffering happens deeper in the Quick Tunnel infrastructure at the Cloudflare edge, not in a component that respects these hints.

### Solution: Add WebSocket Endpoint (Cloudflare Supports WS Natively)

WebSockets use a different protocol upgrade (HTTP 101 → WS binary frames) that **Cloudflare explicitly supports end-to-end**, even through Quick Tunnels. The plan:

1. **Keep the existing SSE endpoint** (`GET /jobs/{id}/stream`) — it works perfectly on localhost
2. **Add a new WebSocket endpoint** (`GET /jobs/{id}/ws`) — used when connected through tunnel
3. **Client auto-detects**: if accessed via HTTPS (= tunnel), use WebSocket; if HTTP (= localhost), use SSE
4. Both endpoints pull from the **same `BroadcastQueue`** — no changes to the pipeline or event model

### Implementation

#### Step 1: Install `websockets` library

```bash
cd /Users/AhmedE/git/investor-agent
source .venv/bin/activate
pip install websockets
```

Or add to `pyproject.toml` dependencies.

#### Step 2: Add WebSocket handler to `analyst_server.py`

Add imports at the top of the file:

```python
import hashlib
```

Add the WebSocket handler method inside the `Handler` class (near the SSE handler, ~line 1310). This is a **raw WebSocket implementation** that reuses the existing `ThreadingHTTPServer` without adding asyncio — it integrates cleanly into the current threading model:

```python
def _ws_handshake(self):
    """Perform RFC 6455 WebSocket opening handshake."""
    key = self.headers.get("Sec-WebSocket-Key", "")
    accept = base64.b64encode(
        hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
    ).decode()
    self.send_response(101)
    self.send_header("Upgrade", "websocket")
    self.send_header("Connection", "Upgrade")
    self.send_header("Sec-WebSocket-Accept", accept)
    self.end_headers()

def _ws_send(self, data: str):
    """Send a text WebSocket frame."""
    payload = data.encode("utf-8")
    length = len(payload)
    if length <= 125:
        header = bytes([0x81, length])
    elif length <= 65535:
        header = bytes([0x81, 126]) + length.to_bytes(2, "big")
    else:
        header = bytes([0x81, 127]) + length.to_bytes(8, "big")
    self.wfile.write(header + payload)
    self.wfile.flush()

def _ws_recv(self, timeout=1.0):
    """Non-blocking read of incoming WS frame. Returns None on timeout/empty."""
    import select as _select
    ready, _, _ = _select.select([self.rfile], [], [], timeout)
    if not ready:
        return None
    b1 = self.rfile.read(1)
    if not b1:
        return None  # connection closed
    b1 = b1[0]
    b2 = self.rfile.read(1)[0]
    opcode = b1 & 0x0F
    if opcode == 0x8:  # close frame
        return "__CLOSE__"
    masked = (b2 & 0x80) != 0
    length = b2 & 0x7F
    if length == 126:
        length = int.from_bytes(self.rfile.read(2), "big")
    elif length == 127:
        length = int.from_bytes(self.rfile.read(8), "big")
    mask = self.rfile.read(4) if masked else None
    data = bytearray(self.rfile.read(length))
    if masked:
        for i in range(len(data)):
            data[i] ^= mask[i % 4]
    return data.decode("utf-8", errors="replace")
```

Then add the WebSocket route inside `do_GET`, alongside the existing SSE route:

```python
# WebSocket stream endpoint — works through Cloudflare Quick Tunnel
# Upgrade: websocket header triggers this branch
if path.startswith("/jobs/") and path.endswith("/ws"):
    if not self._check_auth():
        return
    # Check it's actually a WebSocket upgrade request
    if self.headers.get("Upgrade", "").lower() != "websocket":
        self._send_json(400, {"error": "Expected WebSocket upgrade"})
        return
    job_id = path.split("/")[2]
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        self.send_response(404)
        self.end_headers()
        return

    bq = job["pq"]
    self._ws_handshake()
    log(f"[WS] Client connected for job {job_id[:12]}")

    # Subscribe from beginning (WS clients don't have Last-Event-ID)
    sq = bq.subscribe(from_index=0)
    try:
        while True:
            # Check for client close frame (non-blocking)
            msg = self._ws_recv(timeout=0.05)
            if msg == "__CLOSE__":
                break
            # Send any pending events
            try:
                idx, ev = sq.get(timeout=0.1)
                self._ws_send(json.dumps(ev))
                if ev.get("stage") in ("complete", "error"):
                    break
            except queue.Empty:
                # Send a ping to keep connection alive (opcode 0x89)
                try:
                    self.wfile.write(bytes([0x89, 0x00]))  # ping frame
                    self.wfile.flush()
                except Exception:
                    break
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        bq.unsubscribe(sq)
        log(f"[WS] Client disconnected for job {job_id[:12]}")
    return
```

#### Step 3: Update the browser JavaScript (client-side auto-detection)

In the HTML/JS served by the server (the UI), replace the `EventSource` setup with a transport auto-detector. The logic: if we're on `https://` (= Cloudflare tunnel), use WebSocket; if `http://` (= localhost), use SSE.

Find the section in the server's HTML that creates the EventSource and replace with:

```javascript
function connectStream(jobId, onEvent, onDone) {
    const isHttps = window.location.protocol === 'https:';
    const base = window.location.host;

    if (isHttps) {
        // WebSocket path — works through Cloudflare Quick Tunnel
        const wsUrl = `wss://${base}/jobs/${jobId}/ws`;
        const ws = new WebSocket(wsUrl);
        ws.onmessage = (e) => {
            const ev = JSON.parse(e.data);
            onEvent(ev);
            if (ev.stage === 'complete' || ev.stage === 'error') {
                ws.close();
                onDone(ev);
            }
        };
        ws.onerror = (e) => console.error('[WS] error', e);
        ws.onclose = () => console.log('[WS] closed');
        return ws;
    } else {
        // SSE path — works on localhost (EventSource standard)
        const es = new EventSource(`/jobs/${jobId}/stream`);
        es.onmessage = (e) => {
            const ev = JSON.parse(e.data);
            onEvent(ev);
            if (ev.stage === 'complete' || ev.stage === 'error') {
                es.close();
                onDone(ev);
            }
        };
        es.onerror = (e) => console.error('[SSE] error', e);
        return es;
    }
}

// Usage — replace existing EventSource call:
// OLD: const es = new EventSource(`/jobs/${jobId}/stream`);
// NEW:
const conn = connectStream(jobId,
    (ev) => handleStreamEvent(ev),   // your existing event handler
    (ev) => handleJobComplete(ev)    // your existing complete handler
);
```

Note: The Basic Auth header (`Authorization: Basic ...`) is sent automatically for the initial WebSocket HTTP upgrade handshake if you add it to the request. Since the existing JS already sends the auth cookie or header for the initial page load, the WS connection inherits the same origin context. If needed, pass the auth credentials in the WS URL: `wss://admin:admin@${base}/jobs/${jobId}/ws` — but test first without it since the tunnel + browser may handle auth transparently.

#### Step 4: Handle WS auth in the server

The `_ws_handshake()` method above performs the WS upgrade, but `_check_auth()` should be called before it (already shown in the route code above). The existing `_check_auth()` method reads `Authorization` header which is present in the WS upgrade request just like a normal HTTP request.

### Alternative: Long-Polling (Simpler, Lower Quality)

If WebSocket integration is too much effort, long-polling is a reliable fallback. The client already has a polling fallback that kicks in after 3 SSE drops — it just needs to be extended to retrieve **all events** since last poll, not just job status.

Add this endpoint to the server:

```python
# GET /jobs/{id}/events?after=N  — returns batch of events since index N
if path.startswith("/jobs/") and path.endswith("/events"):
    job_id = path.split("/")[2]
    after = int(qs.get("after", ["0"])[0])
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        self._send_json(404, {"error": "job not found"})
        return
    bq = job["pq"]
    with bq._lock:
        batch = [(i, ev) for i, ev in enumerate(bq._events) if i >= after]
    self._send_json(200, {"events": batch, "next_after": len(bq._events)})
    return
```

Client-side long-polling (JS):

```javascript
async function pollStream(jobId, onEvent, onDone) {
    let after = 0;
    while (true) {
        const res = await fetch(`/jobs/${jobId}/events?after=${after}`, {
            headers: {Authorization: 'Basic ' + btoa('admin:admin')}
        });
        const data = await res.json();
        for (const [idx, ev] of data.events) {
            onEvent(ev);
            if (ev.stage === 'complete' || ev.stage === 'error') {
                onDone(ev);
                return;
            }
        }
        after = data.next_after;
        await new Promise(r => setTimeout(r, 2000));  // poll every 2s
    }
}
```

### Comparison of Solutions

| Option | Effort | Real-time feel | Works through any tunnel | Recommended |
|--------|--------|---------------|--------------------------|-------------|
| **WebSocket** | Medium (1-2h) | ✅ Excellent | ✅ Yes (CF supports WS) | **YES — do this** |
| **Long-polling** | Low (30min) | ⚠️ Batched updates every 2s | ✅ Yes | Fallback if WS fails |
| **Named CF tunnel** | Low (30min) | ✅ Excellent (SSE works) | Requires CF account | Good alternative |
| **ngrok free tier** | Low (15min) | ✅ Excellent (SSE works) | ✅ Yes | Quick test option |
| **Header tweaks** | ❌ Already tried | ❌ Doesn't work | ❌ Quick tunnel bug | Skip |

### Testing the WebSocket Fix

After implementing, test from the tunnel:

```bash
# Test WS directly with wscat (npm install -g wscat)
wscat -c "wss://xxx.trycloudflare.com/jobs/JOBID/ws" \
  --header "Authorization: Basic YWRtaW46YWRtaW4="
# Should see streaming JSON events immediately

# Or test from browser console:
const ws = new WebSocket('wss://xxx.trycloudflare.com/jobs/JOBID/ws');
ws.onmessage = e => console.log(JSON.parse(e.data));
```

### Files to Modify

- `analyst_server.py`: Add `_ws_handshake()`, `_ws_send()`, `_ws_recv()` methods to `Handler` class; add `/jobs/{id}/ws` route in `do_GET`
- HTML/JS in server response (~`_html_page()` method): Replace `new EventSource(...)` with `connectStream()` auto-detector
- `pyproject.toml`: Add `websockets` dependency (though the implementation above uses raw socket framing with no external lib — zero deps)

> **Note:** The raw WS implementation above requires NO external library. It implements RFC 6455 framing directly using `hashlib` (stdlib) and raw socket writes, which is already the pattern used by the existing `ThreadingHTTPServer`. This keeps the deployment simple — no `pip install` needed.

### Issue 2 (Resolved): Generic prompt classified as `general`

When phone submits a prompt without a ticker (e.g., just "hello"), classifier returns `general` → Claude gives a greeting instead of analysis. **Fixed by updating placeholder text** to show example prompts: `scan AAPL · scan the market · portfolio review`.

---

## Known Bugs to Handle

### 1. Process hangs after result (Issue #25629)

After emitting `result` event, the CLI hangs indefinitely. Kill it:

```python
elif etype == "result":
    result_text = ev.get("result", "")
    try:
        proc.kill()
    except Exception:
        pass
    break
```

### 2. Missing result event (Issue #1920)

Sometimes `result` never arrives. Use an idle timeout as safety net:

```python
IDLE_TIMEOUT = 300  # 5 minutes
```

### 3. OAuth token race condition (Issues #24317, #27933)

Refresh tokens are single-use. Multiple `claude -p` processes refreshing simultaneously = only one wins, others get HTTP 400.

**Solution:** `claude setup-token` provides a long-lived access token that doesn't need refreshing. Eliminates the race entirely.

### 4. macOS Keychain naming bug (Issue #9403)

`claude auth login` writes to Keychain service `"Claude Code-credentials"` but reads from `"Claude Code"`. On macOS, failed Keychain lookup preempts file fallback (Issue #25069).

**Solution:** Use `CLAUDE_CODE_OAUTH_TOKEN` env var to bypass Keychain entirely.

### 5. 60-second startup latency (Issue #20527)

On macOS with OAuth/Max subscription, every `claude -p` takes 60s to start. Likely Keychain timeout before falling back to file.

**Solution:** Same — `CLAUDE_CODE_OAUTH_TOKEN` skips Keychain lookup.

## Env Vars to NEVER Pass

| Variable | Why |
|----------|-----|
| `CLAUDECODE` | Set to `1` by VS Code — causes `claude -p` to detect "nested session" and hang |
| `CLAUDE_CODE_ENTRYPOINT` | Values: `cli`, `sdk-py`, `claude-vscode` — signals parent session |
| `ANTHROPIC_API_KEY` | Causes API billing instead of subscription auth |
| `TERM_PROGRAM` | VS Code sets to `"vscode"` — Claude checks this (Issue #9642) |
| `VSCODE_*` | VS Code injection vars |

## Env Vars to ADD

| Variable | Value | Why |
|----------|-------|-----|
| `CLAUDE_CODE_OAUTH_TOKEN` | `sk-ant-oat01-...` from `claude setup-token` | Bypasses Keychain, eliminates race condition |
| `CLAUDE_CODE_DONT_INHERIT_ENV` | `1` | Prevents nested Claude invocations from inheriting session vars |

## Auth Resolution Order (No API Key)

1. macOS Keychain → 2. `CLAUDE_CODE_OAUTH_TOKEN` env var → 3. `~/.claude/.credentials.json` → 4. `ANTHROPIC_API_KEY` → 5. `apiKeyHelper` setting

By setting `CLAUDE_CODE_OAUTH_TOKEN`, we hit #2 and skip Keychain entirely.

## Auth: `claude setup-token` (Free, Auto-refreshing)

The only reliable free method for `claude -p` subprocess auth:

1. Run from Terminal.app: `claude setup-token`
2. Export as env variable: `export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...`
3. Start server: `bash scripts/start-analyst.sh` (passes token through `env -i`)

- **Free** — uses Max subscription, zero API credits consumed
- Token lasts ~15 hours, CLI auto-refreshes automatically
- No manual refresh needed as long as subscription is active
- Bypasses macOS Keychain entirely (avoids naming bug Issue #9403)
- **Never hardcoded** — always read from `CLAUDE_CODE_OAUTH_TOKEN` env var
- If token refresh ever fails, re-run `claude setup-token` and re-export

**Do NOT use `claude auth login`** for subprocess — Keychain naming bug causes silent failures.
**Do NOT pass `ANTHROPIC_API_KEY`** — causes API billing ("Credit balance is too low").

## Start Script (`start-analyst.sh`)

One command starts everything — token, server, tunnel, email:

```bash
bash scripts/start-analyst.sh
```

The script automatically:
1. Runs `claude setup-token` to get an OAuth token (or reuses `CLAUDE_CODE_OAUTH_TOKEN` if already set)
2. Starts the server with `env -i` (clean env, no VS Code leaks)
3. Starts Cloudflare Quick Tunnel
4. Emails the tunnel URL to your phone
5. Prints summary with PIDs and log paths

Uses `env -i` to prevent VS Code env contamination, passes only whitelisted vars including the OAuth token.

## E2E Pipeline Result

Verified working on 2026-03-01 (latest: OKTA through Cloudflare Quick Tunnel via WebSocket):

```
Stage 1 (Generator): 16/16 MCP tools → Claude produced 2,592 chars
Stage 2 (Auditor):   Gemini produced 4,749 chars audit
Stage 3 (Resolver):  Claude merged → 13,003 chars final report
Vault:               Saved OKTA_CONCISE_2026-03-01.md (13,220 bytes)
WebSocket:           2,161 events streamed through Cloudflare Quick Tunnel
```

Previous run (2 concurrent pipelines):
```
AAPL: 41KB final report — completed simultaneously
NVDA: 28KB final report — completed simultaneously
```

## Long-Term: Claude Agent SDK

Anthropic ships `claude-agent-sdk` (Python) which wraps `claude -p` with proper lifecycle management. It handles pipe management, JSON parsing, process cleanup, and typed errors. Migration recommended once current approach is stable.

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="Generate the report",
    options=ClaudeAgentOptions(
        permission_mode="bypassPermissions",
    )
):
    if message.type == "assistant":
        print(message.message.content)
```
