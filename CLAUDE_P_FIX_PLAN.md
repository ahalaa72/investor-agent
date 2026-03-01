# Fix: `claude -p` Not Working for Analyst Server

## The Problem

The analyst server (`analyst_server.py`) needs to run `claude -p "<prompt>"` as a subprocess to execute its 3-stage pipeline (Claude → Gemini → Claude). The subprocess produces only **25 chars of output** instead of a full report.

---

## Timeline of Trials & Findings

### Trial 1: Blacklist env stripping (previous session)
**What:** `os.environ.copy()` then `env.pop()` for keys starting with `CLAUDE*` and `DEEP_SESSION*`
**Result:** FAILED — zero output. `claude -p` hung with 0% CPU doing nothing.
**Why:** Blacklist missed some vars, or the issue isn't just env vars.

### Trial 2: `env -i` from command line (previous session)
**What:** `env -i HOME=... PATH=... claude -p "say hi" --output-format stream-json`
**Result:** FAILED — zero output from both npm binary and VS Code native binary.
**Why:** Even completely clean env didn't help when run from VS Code integrated terminal.

### Trial 3: VS Code native binary (previous session)
**What:** Changed CLAUDE_BIN to `~/.vscode/extensions/.../native-binary/claude`
**Result:** FAILED — same zero output.
**Why:** Binary doesn't matter — same CLI code regardless of binary.

### Trial 4: Whitelist env `_build_clean_env()` (current session)
**What:** Build env from scratch with only HOME, USER, PATH, LANG, etc. No inherited vars at all. Also `env -i` wrapper in `start-analyst.sh`.
**Result:** PARTIAL SUCCESS — `claude -p` now starts and produces output! System init event appears, 25 chars of text returned. MCP data gathering (16/16 tools) works perfectly.
**But:** Only 25 chars instead of full report. MCP validation fails.
**Finding:** The whitelist env **fixed the zero-output hang**. The new issue is the **tiny response**.

### Trial 5: Stdin pipe via `--input-format stream-json`
**What:** Pipe prompt via stdin using `--input-format stream-json` mode instead of passing as CLI arg.
**Hypothesis:** 121K CLI argument being truncated or mangled.
**Result:** Implemented. Debug logging revealed: **`DEBUG OUTPUT: 'Credit balance is too low'`**
**Finding:** NOT a CLI bug — `ANTHROPIC_API_KEY` was in clean env → Claude used API billing → $0 credits → failed.

### Trial 6: Remove ANTHROPIC_API_KEY from clean env
**What:** Removed API key from `_build_clean_env()` and `start-analyst.sh`.
**Result:** TESTED — new error: `OAuth token has expired. Please obtain a new token or refresh your existing token.`
**Why:** Without API key, Claude falls back to subscription OAuth, but cached token in `~/.claude/` was expired.

### Trial 7: Pass only `CLAUDE_CODE_OAUTH_TOKEN`
**What:** Passed `CLAUDE_CODE_OAUTH_TOKEN` from VS Code parent env (NOT `CLAUDECODE`, `CLAUDE_CODE_ENTRYPOINT`, `ANTHROPIC_API_KEY`).
**Result:** FAILED — same OAuth error. VS Code's `CLAUDE_CODE_OAUTH_TOKEN` is session-scoped and doesn't work standalone.

### Trial 8: Auth commands & status check
**Finding:** `claude login` is NOT a command. Correct: `claude auth login`.

Auth status in clean env:
```json
{
  "loggedIn": true,
  "authMethod": "claude.ai",
  "subscriptionType": "max",
  "email": "ahalaa@hotmail.com"
}
```
**KEY INSIGHT:** `claude auth status` shows `loggedIn: true` but doesn't validate the token against the API. The actual token was expired — `claude -p` got 401 on real API calls.

### Trial 9: Server won't start — port 7799 not binding
**Found:** `OSError: [Errno 48] Address already in use` — stale Python process (PID 6195) from earlier `exec(open('analyst_server.py').read())` held port invisibly. `lsof -i :7799` showed nothing; `ps aux | grep python3` revealed it.
**Fix:** Kill PIDs 6195/6193, wait 2s, restart server.

### Trial 10: Server running, still OAuth expired
**Steps done:** Kill stale, truncate log, start server, submit test job. Claude still returned OAuth error.
**Root cause confirmed:** `claude auth status` caches config — it does NOT make a live API call to validate the token.
**THE FIX:** User must run `claude auth login` from Terminal.app and complete browser auth flow.

### Trial 11: User ran `claude auth login` — restarting server
**What:** User ran `claude auth login` from Terminal.app, completed browser auth flow. `claude auth status` showed `loggedIn: true, subscriptionType: max`.
**Result:** FAILED — `claude -p "say hello in 5 words"` returns exit code 1 with **zero output** (no stdout, no stderr).
**Root cause:** Keychain naming bug (Finding A, Issue #9403). `claude auth login` writes credential to macOS Keychain under service `"Claude Code-credentials"` but `claude -p` reads from `"Claude Code"`. Failed Keychain lookup preempts file fallback (Issue #25069) → silent auth failure → exit 1.
**Conclusion:** OAuth via Keychain is unreliable for subprocess use. Need persistent token approach.

### Trial 12: `claude setup-token` — persistent token bypass ✅ SUCCESS
**What:**
1. User ran `claude setup-token` from Terminal.app → got `sk-ant-oat01-...` token
2. Added token to `_build_clean_env()` as `CLAUDE_CODE_OAUTH_TOKEN`
3. Also added `CLAUDE_CODE_DONT_INHERIT_ENV=1` to prevent nested session leakage
4. Added `--include-partial-messages` to `base_cmd` (Finding C)
5. Added `proc.kill()` after result event to prevent hang (Finding D, Issue #25629)
6. Verified `--no-session-persistence` is valid flag (confirmed in `claude --help`)
7. Verified `.mcp-empty.json` has correct format `{"mcpServers":{}}`

**Result:** ✅ **CLAUDE -p IS NOW WORKING!**
- Test prompt "say hello in exactly 5 words" → Claude responded: `"Hello, Ahmed! Good morning today."`
- 144 chars of real output (not "Credit balance" or "OAuth expired")
- Pipeline progressed to Gemini auditor stage
- MCP validation "failed" as expected (test prompt has no MCP data to validate)

**Root cause chain (fully resolved):**
1. `CLAUDECODE=1` env var → zero output hang → FIXED by whitelist env
2. `ANTHROPIC_API_KEY` → "Credit balance too low" → FIXED by removing from env
3. OAuth expired + Keychain naming bug → silent auth failure → FIXED by `setup-token` bypass

### Full Pipeline E2E Test: ✅ PASSED
**Job:** `22ad00875683` — "analyze AAPL concise"
- **Stage 1 (Generator):** 16/16 MCP tools OK → Claude produced 5,951 chars
- **Stage 2 (Auditor):** Gemini produced 4,318 chars audit
- **Stage 3 (Resolver):** Claude merged → 13,799 chars final report
- **Vault:** Saved to `AAPL_CONCISE_2026-03-01_1628.md` (14,040 bytes)
- **All fixes confirmed working:** setup-token auth, `--include-partial-messages` streaming, `proc.kill()` after result

---

## Deep Research Findings (March 2026)

The following are verified findings from examining Claude Code CLI source, GitHub issues, and official docs. These explain remaining failure modes and what to fix next.

### Finding A: OAuth credentials storage and the Keychain naming bug

Claude Code stores OAuth tokens in **two places** on macOS:
1. **macOS Keychain** (primary): service name used for writing is `"Claude Code-credentials"`, but the read path looks for `"Claude Code"` — a known naming mismatch (GitHub Issue #9403).
2. **`~/.claude/.credentials.json`** (fallback): JSON file with this structure:

```json
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-oat01-...",
    "refreshToken": "sk-ant-ort01-...",
    "expiresAt": 1748658860401,
    "scopes": ["user:inference", "user:profile"],
    "subscriptionType": "max"
  }
}
```

Access tokens have a **~15-hour lifetime**. Refresh tokens are **single-use** — after one use, the old token is invalidated.

**Auth resolution order** (no API key in env):
`macOS Keychain` → `CLAUDE_CODE_OAUTH_TOKEN` env var → `~/.claude/.credentials.json` → `ANTHROPIC_API_KEY` → `apiKeyHelper` setting

Since `HOME` is whitelisted, the subprocess CAN reach `~/.claude/.credentials.json`. However, Issue #25069 documents that on macOS, a failed Keychain lookup can preempt the file fallback and return "not logged in" without checking the file.

**Fix for Keychain naming bug:** If OAuth errors persist after `claude auth login`, manually copy the credential from the write path to the read path:
```bash
CREDS=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null)
if [ -n "$CREDS" ]; then
  security add-generic-password -a "$USER" -s "Claude Code" -w "$CREDS" 2>/dev/null || true
fi
```

**Most reliable auth for subprocess** — generate a long-lived token with:
```bash
claude setup-token   # outputs a token starting with sk-ant-oat01-
```
Then pass it explicitly in `_build_clean_env()`:
```python
env["CLAUDE_CODE_OAUTH_TOKEN"] = "sk-ant-oat01-..."  # from setup-token, not VS Code session
```
This bypasses Keychain entirely and avoids the naming bug.

---

### Finding B: DEEP_SESSION_ID is not a real Claude Code variable

Extensive search across Claude Code source, GitHub issues, and docs found **zero references to `DEEP_SESSION_ID`** as a Claude Code variable. It was either confused with an internal identifier or a proposed but never-implemented `CLAUDE_SESSION_ID`. Do not rely on stripping it for session detection prevention.

**Confirmed real session-detection variables to strip:**
- `CLAUDECODE=1` — the primary "you're nested" flag; Claude Code exits immediately if this is set
- `CLAUDE_CODE_ENTRYPOINT` — values: `cli`, `sdk-py`, `claude-vscode`; signals parent session type
- `CLAUDE_CODE_ACTION` — may affect behavior in nested contexts
- `TERM_PROGRAM=vscode` — Claude Code actively checks this and changes permission behavior (Issue #9642)
- `VSCODE_GIT_ASKPASS_MAIN`, `VSCODE_INJECTION`, `VSCODE_GIT_IPC_HANDLE` — VS Code signals

**Useful env var to ADD to clean env:**
```python
env["CLAUDE_CODE_DONT_INHERIT_ENV"] = "1"
```
When set, Claude Code's own subprocess spawning uses an empty base env instead of inheriting `process.env`, preventing `CLAUDECODE=1` from leaking into any nested Claude invocations.

---

### Finding C: `--include-partial-messages` is REQUIRED for streaming

**This is a critical missing flag in the current implementation.**

Without `--include-partial-messages`, the output event sequence from `--output-format stream-json` is:
```
{"type":"system","subtype":"init","session_id":"..."}
{"type":"assistant","message":{"content":[{"type":"text","text":"COMPLETE response all at once"}]}}
{"type":"result","subtype":"success","cost_usd":...}
```

The `assistant` event arrives only **after the model finishes its entire response** — there are no incremental `content_block_delta` events at all.

**With `--include-partial-messages`**, you get real streaming:
```
{"type":"system","subtype":"init",...}
{"type":"stream_event","event":{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}}
{"type":"stream_event","event":{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" world"}}}
...
{"type":"assistant","message":{...}}
{"type":"result","subtype":"success",...}
```

**Current code in `_run_claude_once()` handles `content_block_delta` events but will NEVER see them** because `--include-partial-messages` is not in `base_cmd`. The code path for `assistant` message parsing is the one actually firing.

**Add this flag to `base_cmd`:**
```python
base_cmd = [CLAUDE_BIN, "-p", "--dangerously-skip-permissions",
            "--output-format", "stream-json", "--verbose",
            "--input-format", "stream-json",
            "--include-partial-messages"]  # ← ADD THIS
```

---

### Finding D: Three open GitHub bugs that directly affect this server

**Bug 1 — Process hangs after result event (Issue #25629, OPEN)**
After writing `{"type":"result","subtype":"success"}`, the CLI process hangs indefinitely — stdout stays open, process never exits. If `_run_claude_once()` waits for process exit after receiving result, it will hang forever.

**Fix:** Kill the process immediately after receiving the result event:
```python
elif etype == "result":
    result_text = ev.get("result", "")
    if result_text and not text_parts:
        push(pq, stage, "streaming", "", result_text)
    # ← ADD: kill the process after result to avoid hang (Issue #25629)
    try:
        proc.kill()
    except Exception:
        pass
    break
```

**Bug 2 — Missing final result event (Issue #1920, Closed not planned)**
The CLI intermittently fails to emit the `result` event after tool execution. The same query sometimes works, sometimes hangs for 30+ minutes. The server's hard timeout handles this, but the timeout should be the safety net — not the primary exit.

**Fix (already in code):** The `IDLE_TIMEOUT = 300` is the correct fallback. Also ensure the `assistant` message path collects text correctly when `result` never arrives.

**Bug 3 — Empty `result` field (Issues #7124, #8126, OPEN)**
The final `result` message sometimes has an empty `result` string despite successful execution. **The current code already handles this correctly** — it collects `text_parts` from `content_block_delta` events and falls back to `result_text = "".join(text_parts).strip()`.

**Additional bug — 60-second latency on all `--print` requests (Issue #20527)**
Reported on macOS M4 with OAuth/Max subscription specifically in subprocess/popen use. Every request takes exactly 60–63 seconds. Likely cause: Keychain timeout during OAuth token read, then falling back to file. If the server sees 60s startup delays, the Keychain fix (Finding A) should resolve it.

**Additional issue — Sandbox debug output contaminating stdout (Issue #12007)**
On some macOS builds, `[SandboxDebug]...` lines appear on stdout even with `--output-format stream-json`, breaking JSON parsing. The server already has `try/except json.JSONDecodeError: continue` in the parse loop — this is correctly handled.

---

### Finding E: stdin JSON format is correct

The server's current input format is confirmed correct by official Anthropic documentation:
```json
{"type":"user","message":{"role":"user","content":[{"type":"text","text":"Your prompt here"}]}}
```
No changes needed to the stdin feeding code.

---

### Finding F: OAuth race condition with 3 concurrent `claude -p` processes

Refresh tokens are single-use. When multiple `claude -p` processes try to refresh simultaneously, only one succeeds — the rest get HTTP 400 invalidated (Issues #24317, #27933). The server supports up to 3 concurrent jobs, each running `claude -p` for Stage 1 (generator) and Stage 3 (resolver) = up to 6 concurrent Claude processes in the worst case.

**Risk:** Two Stage 1 generators starting simultaneously could race on token refresh, causing OAuth failures for all but the first.

**Mitigation options (in order of simplicity):**
1. Use `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` — this is a long-lived access token that doesn't need refreshing during the pipeline run, eliminating the race entirely.
2. Add a file lock around `_run_claude_once()` that serializes the first API call (which triggers token refresh) then releases:
```python
import fcntl
_token_refresh_lock = threading.Lock()
# In _run_claude_once(), hold the lock for the first 30s of startup:
with _token_refresh_lock:
    time.sleep(30)  # give token refresh time to complete
```
Option 1 is simpler and recommended.

---

### Finding G: Flag validity — `--no-session-persistence` is unconfirmed

| Flag | Status | Notes |
|------|--------|-------|
| `--input-format stream-json` | ✅ Valid | Requires `-p` |
| `--output-format stream-json` | ✅ Valid | |
| `--include-partial-messages` | ✅ Valid | **Missing from current code — add it** |
| `--strict-mcp-config` | ✅ Valid | Only uses MCP from `--mcp-config`, ignores all others |
| `--mcp-config <file>` | ✅ Valid | Use `{"mcpServers":{}}` (not bare `{}`) |
| `--dangerously-skip-permissions` | ✅ Valid | Does NOT affect auth |
| `--no-session-persistence` | ⚠️ Unconfirmed | Not found in `claude --help` dumps (Aug–Oct 2025). May exist in newer versions. If `claude --help` doesn't list it, remove it from the resolver command — it will cause a startup error. |

**Verify with:**
```bash
/Users/AhmedE/.nvm/versions/node/v22.20.0/bin/claude --help 2>&1 | grep session
```

**Empty MCP config file content — use this exact format:**
```json
{"mcpServers":{}}
```
NOT bare `{}` — the `mcpServers` key is what the parser looks for.

---

### Finding H: Official Claude Agent SDK — the long-term path

Anthropic now ships `claude-agent-sdk` (Python), which wraps the same `claude -p --output-format stream-json --input-format stream-json` subprocess pattern with proper lifecycle management. It handles pipe management, JSON parsing, process cleanup, and typed errors (`CLINotFoundError`, `CLIConnectionError`, `ProcessError`).

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="Generate the report",
    options=ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        env={"CLAUDECODE": ""},  # clear nested-session flag
    )
):
    if message.type == "assistant":
        print(message.message.content)
```

**This is NOT the immediate fix** — migrating now would be a larger refactor. But it is the right long-term direction once the current approach is validated end-to-end. The SDK solves the hang bug (#25629), the missing result bug (#1920), and process cleanup automatically.

---

## Root Cause Summary (All Layers)

| Layer | Problem | Status | Fix |
|-------|---------|--------|-----|
| 1 | `CLAUDECODE=1` + VS Code env vars causing hang | ✅ SOLVED | `_build_clean_env()` whitelist |
| 2 | `ANTHROPIC_API_KEY` → "Credit balance too low" | ✅ SOLVED | Removed from clean env |
| 3 | OAuth token expired | ✅ SOLVED (Trial 11 — `claude auth login` done) |
| 4 | Token may expire again / Keychain naming bug | ⚠️ LATENT | Use `claude setup-token` for persistent token |
| 5 | `--include-partial-messages` missing | 🔴 NOT FIXED | Add to `base_cmd` in `_run_claude_once()` |
| 6 | Process hangs after result event (#25629) | 🔴 NOT FIXED | Kill proc after receiving result event |
| 7 | `--no-session-persistence` may be invalid flag | ⚠️ UNVERIFIED | Check with `claude --help \| grep session` |
| 8 | Concurrent token refresh race (3 jobs) | ⚠️ LATENT | Use `claude setup-token` long-lived token |
| 9 | `DEEP_SESSION_ID` stripping is unnecessary | ℹ️ INFO | Not a real var; no action needed |

---

## Current Code State

### `_build_clean_env()` (line ~790 in analyst_server.py)
Whitelist env builder. Passes: HOME, USER, SHELL, PATH, LANG, TERM, NVM_DIR, SSL certs, XDG dirs, TMPDIR.
Does NOT pass: ANTHROPIC_API_KEY, CLAUDECODE, CLAUDE_CODE_ENTRYPOINT, CLAUDE_CODE_OAUTH_TOKEN.
**Currently relying on `~/.claude/.credentials.json` for auth — correct approach post `claude auth login`.**

### `_run_claude_once()` (line ~551)
- Uses `--input-format stream-json` ✅
- Feeds prompt as `{"type":"user","message":{"role":"user","content":[...]}}` ✅
- Uses `--output-format stream-json` ✅
- Handles `assistant`, `content_block_delta`, `result` event types ✅
- Missing `--include-partial-messages` flag 🔴
- Does NOT kill process after `result` event — will hang per Issue #25629 🔴
- Debug logging for outputs < 500 chars ✅

### `CLAUDE_BIN` (line ~75)
`/Users/AhmedE/.nvm/versions/node/v22.20.0/bin/claude`

---

## TODO — Ordered by Priority

### IMMEDIATE (do these first — unblocking the pipeline)

- [ ] **Verify Trial 11 outcome** — did `claude auth login` fix the OAuth error?
  ```bash
  # From Terminal.app (NOT VS Code terminal):
  env -i HOME="$HOME" PATH="$PATH" /Users/AhmedE/.nvm/versions/node/v22.20.0/bin/claude \
    -p "say hello in 5 words" --output-format text
  # Expected: 5-word greeting
  # If still OAuth error: proceed to "Fix Keychain naming bug" below
  ```

- [ ] **Add `--include-partial-messages` to `base_cmd`** in `_run_claude_once()` (Finding C)
  ```python
  # Line ~560 in analyst_server.py — change:
  base_cmd = [CLAUDE_BIN, "-p", "--dangerously-skip-permissions",
              "--output-format", "stream-json", "--verbose",
              "--input-format", "stream-json"]
  # To:
  base_cmd = [CLAUDE_BIN, "-p", "--dangerously-skip-permissions",
              "--output-format", "stream-json", "--verbose",
              "--input-format", "stream-json",
              "--include-partial-messages"]
  ```

- [ ] **Fix process hang after result event** — kill proc after receiving result (Finding D, Issue #25629)
  ```python
  # In _run_claude_once(), in the elif etype == "result": block, BEFORE break:
  try:
      proc.kill()
  except Exception:
      pass
  ```

- [ ] **Verify `--no-session-persistence` is a valid flag** for the installed claude version
  ```bash
  /Users/AhmedE/.nvm/versions/node/v22.20.0/bin/claude --help 2>&1 | grep -i session
  ```
  If it's NOT listed: remove `"--no-session-persistence"` from the resolver's `base_cmd` additions in `_run_claude_once()` (the `if not needs_mcp:` branch).

- [ ] **Verify the empty MCP config file format** — check `.mcp-empty.json` contains `{"mcpServers":{}}` not bare `{}`
  ```bash
  cat /Users/AhmedE/git/investor-agent/.mcp-empty.json
  # Should output: {"mcpServers":{}}
  ```

### STABILIZATION (do these after pipeline is confirmed working)

- [ ] **Fix Keychain naming bug** to prevent future OAuth failures (Finding A, Issue #9403)
  ```bash
  # Run once from Terminal.app to copy credential to the read path:
  CREDS=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null)
  if [ -n "$CREDS" ]; then
    security add-generic-password -a "$USER" -s "Claude Code" -w "$CREDS" 2>/dev/null || true
    echo "Keychain credential copied to read path"
  else
    echo "No credential found at write path — auth may still be using file fallback"
  fi
  ```

- [ ] **Generate a persistent `setup-token`** to replace OAuth credential dependency (Finding A, F)
  ```bash
  # From Terminal.app:
  claude setup-token
  # Copy the output token (starts with sk-ant-oat01-)
  ```
  Then add to `_build_clean_env()`:
  ```python
  # Replace the comment about OAuth with:
  env["CLAUDE_CODE_OAUTH_TOKEN"] = "sk-ant-oat01-PASTE_TOKEN_HERE"
  ```
  This eliminates Keychain dependency, prevents 60-second latency (Issue #20527), and fixes the token race condition for concurrent jobs.

- [ ] **Add `CLAUDE_CODE_DONT_INHERIT_ENV=1`** to clean env (Finding B)
  ```python
  env["CLAUDE_CODE_DONT_INHERIT_ENV"] = "1"
  ```
  Prevents any nested `claude` invocations from inheriting `CLAUDECODE=1`.

- [ ] **Strip `TERM_PROGRAM`** from clean env (Finding B, Issue #9642)
  Ensure `TERM_PROGRAM` is NOT in `_build_clean_env()` — VS Code sets it to `"vscode"` and Claude Code checks it.
  ```python
  # Do NOT add this line (it's currently absent — confirm it stays absent):
  # env["TERM_PROGRAM"] = os.environ.get("TERM_PROGRAM", "")  ← keep this OUT
  ```

### END-TO-END TESTING

- [ ] **Submit minimal test job** after applying immediate fixes:
  ```bash
  curl -u admin:admin -X POST localhost:7799/analyze \
    -H "Content-Type: application/json" \
    -d '{"prompt":"say hello in exactly 5 words","name":"TEST"}'
  ```
  Expected: Generator stage produces 5+ words, not "Credit balance" or OAuth error.

- [ ] **Check log for streaming events** — with `--include-partial-messages` added, you should now see `content_block_delta` events in the log:
  ```
  [generator] Event: content_block_delta  ← should appear now
  ```
  If you only see `[generator] Event: assistant`, the flag is not being applied.

- [ ] **Submit real analysis job** — e.g. `analyze AAPL concise`

- [ ] **Full pipeline test** — Claude → Gemini → Claude → Vault → Email

- [ ] **Tunnel test** — via Cloudflare tunnel on mobile

---

## LOOP PREVENTION NOTES

**Do NOT repeat these:**

1. Blacklist env stripping — doesn't work (Trials 1-3)
2. Changing CLAUDE_BIN to VS Code native binary — doesn't help
3. `env -i` from command line with `-p` flag — still only 25 chars
4. Testing `claude -p "say hi"` from VS Code terminal — always contaminated by parent env
5. **Passing ANTHROPIC_API_KEY to claude subprocess** — causes "Credit balance is too low" (25 chars)
6. **Passing VS Code's `CLAUDE_CODE_OAUTH_TOKEN` as-is** — session-scoped, doesn't work standalone (Trial 7)
7. **Trusting `claude auth status` to validate the token** — it only checks cached config, not live API

**What IS confirmed working:**

- `_build_clean_env()` whitelist approach fixed the zero-output hang ✅
- `--input-format stream-json` stdin pipe approach starts correctly ✅
- Stdin JSON format `{"type":"user","message":{"role":"user","content":[...]}}` is correct ✅
- MCP data gathering (docker exec) works perfectly: 16/16 tools OK ✅
- Gemini stage works fine ✅
- Server UI, SSE, jobs API all work ✅
- Debug logging correctly captures short output content ✅

**What is NOT yet confirmed working:**

- End-to-end `claude -p` → full report (still untested post Trial 11) ❓
- `--include-partial-messages` streaming (flag not in code yet) 🔴
- Process termination after result event (hang bug not patched yet) 🔴
- Concurrent jobs without token race condition 🔴
