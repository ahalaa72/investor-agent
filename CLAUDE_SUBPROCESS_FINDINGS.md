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
    env["CLAUDE_CODE_OAUTH_TOKEN"] = "sk-ant-oat01-..."  # from `claude setup-token`
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
2. Copy the `sk-ant-oat01-...` token
3. Pass via `CLAUDE_CODE_OAUTH_TOKEN` env var in `_build_clean_env()`

- **Free** — uses Max subscription, zero API credits consumed
- Token lasts ~15 hours, CLI auto-refreshes automatically
- No manual refresh needed as long as subscription is active
- Bypasses macOS Keychain entirely (avoids naming bug Issue #9403)
- If token refresh ever fails, re-run `claude setup-token` and update the code

**Do NOT use `claude auth login`** for subprocess — Keychain naming bug causes silent failures.
**Do NOT pass `ANTHROPIC_API_KEY`** — causes API billing ("Credit balance is too low").

## Start Script (`start-analyst.sh`)

Must use `env -i` to prevent VS Code env contamination:

```bash
env -i \
  HOME="$HOME" \
  USER="${USER:-AhmedE}" \
  SHELL="${SHELL:-/bin/zsh}" \
  PATH="/Users/AhmedE/.nvm/versions/node/v22.20.0/bin:/usr/local/bin:/usr/bin:/bin" \
  LANG="en_US.UTF-8" \
  TERM="xterm-256color" \
  PYTHONUNBUFFERED=1 \
  TMPDIR="${TMPDIR:-/tmp}" \
  NVM_DIR="${NVM_DIR:-$HOME/.nvm}" \
  nohup python3 -u analyst_server.py >> logs/analyst-server.log 2>&1 &
```

## E2E Pipeline Result

Verified working on 2026-03-01:

```
Stage 1 (Generator): 16/16 MCP tools → Claude produced 5,951 chars
Stage 2 (Auditor):   Gemini produced 4,318 chars audit
Stage 3 (Resolver):  Claude merged → 13,799 chars final report
Vault:               Saved AAPL_CONCISE_2026-03-01_1628.md (14,040 bytes)
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
