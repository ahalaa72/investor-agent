#!/usr/bin/env python3
"""
Ahmed's AI Analyst Pipeline — Multi-Session Async Architecture
  Stage 1  Claude Code CLI  (Generator with MCP tools) — SUBSCRIPTION, NO API CREDITS
  Stage 2  Gemini CLI       (Adversarial Auditor)       — GOOGLE LOGIN, NO API KEY
  Stage 3  Claude Code CLI  (Resolver / Manager)        — SUBSCRIPTION, NO API CREDITS
  Save     /Users/AhmedE/Ahmed/  (Obsidian vault)

Run:   python3 analyst_server.py
Open:  http://localhost:7799
Auth:  admin / admin (HTTP Basic Auth)

Supports up to 3 concurrent scans. Each scan gets a job ID and independent SSE stream.
Jobs auto-cleanup after 4 hours.
"""

import os, json, subprocess, threading, queue, time, re, smtplib, select, uuid, base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs


# ── Auth ──────────────────────────────────────────────────────────────────────
AUTH_USER = "admin"
AUTH_PASS = "admin"


# ── BroadcastQueue ────────────────────────────────────────────────────────────

class BroadcastQueue:
    """Queue-like object that stores events and broadcasts to all subscribers."""

    def __init__(self):
        self._events = []
        self._subs = []
        self._lock = threading.Lock()

    def put(self, event):
        with self._lock:
            self._events.append(event)
            for sq in self._subs:
                sq.put(event)

    def subscribe(self):
        """Subscribe and get a personal Queue pre-loaded with past events."""
        sq = queue.Queue()
        with self._lock:
            for ev in self._events:
                sq.put(ev)
            self._subs.append(sq)
        return sq

    def unsubscribe(self, sq):
        with self._lock:
            try:
                self._subs.remove(sq)
            except ValueError:
                pass


# ── Job Store ─────────────────────────────────────────────────────────────────
_jobs = {}                              # job_id → job dict
_jobs_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=3)


# ── Config ────────────────────────────────────────────────────────────────────
PORT        = 7799
REPO        = Path("/Users/AhmedE/git/investor-agent")
VAULT       = Path("/Users/AhmedE/Ahmed/Trading Reports")
CLAUDE_BIN  = "/Users/AhmedE/.nvm/versions/node/v22.20.0/bin/claude"
GEMINI_BIN  = "/Users/AhmedE/.nvm/versions/node/v22.20.0/bin/gemini"
CLAUDE_PATH = "/Users/AhmedE/.nvm/versions/node/v22.20.0/bin"   # node + gemini live here
EMAIL_FROM  = "aalaa72@gmail.com"
EMAIL_TO    = "ahalaa@yahoo.com"

# Context files injected into every Stage 1 prompt
CONTEXT_FILES = [
    REPO / "CLAUDE.md",
    REPO / "reportsGenerator" / "SCANNER_INSTRUCTIONS.md",
    REPO / "reportsGenerator" / "SCANNER_REPORT_GENERATOR.md",
]

# All 7 Questrade accounts — check positions in ALL of them
QUESTRADE_ACCOUNTS = [
    "40036271",  # Cash Corp
    "40070512",  # Cash Ind
    "29455571",  # Margin Ind
    "29458646",  # Margin Corp
    "51673853",  # TFSA
    "53469766",  # RRSP
    "53507295",  # LIRA
]

# Slim context: just the report format (for parallel MCP path — data already gathered)
REPORT_FORMAT_FILE = REPO / "reportsGenerator" / "SCANNER_REPORT_GENERATOR.md"

# ── Load context files at startup ─────────────────────────────────────────────
def load_context() -> str:
    parts = []
    for path in CONTEXT_FILES:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            parts.append(f"\n{'='*70}\nFILE: {path.name}\n{'='*70}\n{content}\n")
            print(f"  ✓ Loaded: {path.name} ({len(content):,} chars)")
        else:
            print(f"  ✗ Missing: {path}")
    return "\n".join(parts)

print("\nLoading context files...")
CONTEXT = load_context()
print(f"  Total context: {len(CONTEXT):,} chars")

# Slim context for parallel MCP path (report format only — 70K vs 133K)
REPORT_FORMAT = ""
if REPORT_FORMAT_FILE.exists():
    REPORT_FORMAT = REPORT_FORMAT_FILE.read_text(encoding="utf-8")
    print(f"  Report format: {len(REPORT_FORMAT):,} chars (slim context for parallel path)")
print()

# ── Load email credentials from .env ─────────────────────────────────────────
def load_env():
    env_file = REPO / ".env"
    creds = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip()
    return creds

ENV = load_env()
GMAIL_PASS = ENV.get("GMAIL_APP_PASSWORD", "")

# ── System prompts ────────────────────────────────────────────────────────────

AUDITOR_SYS = """You are a hostile financial auditor. You are paid per error found. Zero reward for agreement.

Your mandate:
- Recalculate every number from scratch
- Challenge every options mechanic (ITM/OTM direction, premium flow, assignment risk, Greeks)
- Verify every Canadian CCPC tax claim against actual CRA rules (interest ~50.17%, cap gains ~25.08%, RDTOH)
- Find internal contradictions between sections
- Flag missing risks, exit conditions, unsupported recommendations
- Challenge every Al Brooks pattern interpretation and probability claim
- Verify McMillan options strategy matches stated IV environment

For EVERY error use EXACTLY this format:

FINDING #[n]
QUOTE: [exact verbatim text from report]
ERROR_TYPE: [Math | Options_Mechanics | Tax | Logic | Omission | Contradiction | Brooks | Dalio]
WHAT_IS_WRONG: [specific explanation]
CORRECT_ANSWER: [corrected version with reasoning]
CONFIDENCE: [High | Medium | Low]

If a section is clean: SECTION_CLEAR: [section name]

End with:
AUDIT_SUMMARY
Total findings: [N] | High: [N] | Medium: [N] | Low: [N]
Most critical: [one sentence on the most dangerous error Ahmed could act on]"""

RESOLVER_SYS = """You are Ahmed's senior portfolio manager and final decision-maker.

You receive an original analysis and an adversarial audit from Gemini AI.
Act as objective judge — zero favoritism to either side.

For each Gemini finding:
  VALID     — error is real, apply the correction
  INVALID   — explain precisely why original was correct
  UNCERTAIN — flag for Ahmed's manual review before trading

OUTPUT STRUCTURE (use exactly these headers):

RESOLUTION_LOG
==============
[One line per finding: FINDING #N → VALID/INVALID/UNCERTAIN + reason]

FINAL_REPORT
============
[Complete corrected analysis — this is what Ahmed acts on.
 Include: Executive Summary, Technical Analysis, Options Strategy,
 Trade Plan with entry/stop/targets, Risk Assessment, CCPC Tax, Position Sizing.]

CONFIDENCE_SUMMARY
==================
[Per section: HIGH / MEDIUM / LOW with brief note]

HUMAN_REVIEW_REQUIRED
=====================
[Numbered list of anything Ahmed must personally verify before placing any trade]

CONTEXT:
- Ahmed trades Canadian CCPC accounts (7 Questrade accounts)
- War context: US-Israel struck Iran Feb 28 2026. Hormuz threatened.
- Hedges active: VIXY 250 shares, ZGLD.TO 200 shares, GLD 10 shares, SLV 200 shares
- Options: McMillan + TastyTrade. 50% profit target. 21 DTE roll. 16-delta. Half-Kelly. NO stops.
- Tax: Interest ~50.17%, Capital gains ~25.08%, RDTOH mechanism"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def push(pq, stage, status, message="", chunk=""):
    pq.put({"stage": stage, "status": status, "message": message, "chunk": chunk})


# ── Direct MCP Tool Calls (parallel, bypass claude -p) ───────────────────────

def _call_mcp_tool(tool_name: str, arguments: dict, timeout: int = 120) -> dict:
    """Call a single MCP tool via docker exec + JSON-RPC. Returns result dict."""
    init_req = json.dumps({
        "jsonrpc": "2.0", "method": "initialize", "id": 0,
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "analyst", "version": "1.0"}}
    })
    init_notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
    tool_req = json.dumps({
        "jsonrpc": "2.0", "method": "tools/call", "id": 1,
        "params": {"name": tool_name, "arguments": arguments}
    })
    stdin_data = init_req + "\n" + init_notif + "\n" + tool_req + "\n"

    try:
        proc = subprocess.run(
            ["docker", "exec", "-i", "investor-agent-mcp",
             "python", "-m", "investor_agent.server_modular"],
            input=stdin_data, capture_output=True, text=True, timeout=timeout,
        )
        for line in proc.stdout.splitlines():
            try:
                resp = json.loads(line)
                if resp.get("id") == 1:
                    # Extract text content from MCP result
                    content = resp.get("result", {}).get("content", [])
                    texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                    return {"tool": tool_name, "data": "\n".join(texts)}
            except json.JSONDecodeError:
                continue
        return {"tool": tool_name, "error": f"No response. stderr: {proc.stderr[:200]}"}
    except subprocess.TimeoutExpired:
        return {"tool": tool_name, "error": f"Timeout ({timeout}s)"}
    except Exception as e:
        return {"tool": tool_name, "error": str(e)}


# ── Request Classification & Dynamic Tool Selection ──────────────────────────

def _classify_request(prompt: str) -> tuple:
    """Classify the request and return (request_type, tickers_list).
    Returns one of: ticker_analysis, market_scan_long, market_scan_short,
    market_scan, portfolio_review, options_focus, comparison, general.
    """
    lower = prompt.lower()
    tickers = _extract_all_tickers(prompt)

    # Portfolio / positions review
    if any(w in lower for w in ["portfolio", "positions", "holdings", "balances", "accounts"]):
        return ("portfolio_review", tickers)

    # Market scanning — but if a specific ticker is given with "scan", treat as ticker analysis
    if any(w in lower for w in ["scan", "screen", "find opportunities", "market opportunities"]):
        if tickers:
            # "scan AAPL" = analyze AAPL, not full market scan
            return ("ticker_analysis", tickers)
        if any(w in lower for w in ["short", "bear", "put"]):
            return ("market_scan_short", tickers)
        elif any(w in lower for w in ["long", "bull", "call", "buy"]):
            return ("market_scan_long", tickers)
        return ("market_scan", tickers)

    # Comparison (2+ tickers)
    if len(tickers) >= 2:
        return ("comparison", tickers)

    # Options-focused
    if any(w in lower for w in ["option", "options", "put spread", "call spread", "iron condor",
                                 "straddle", "strangle", "covered call", "mcmillan"]):
        return ("options_focus", tickers)

    # Single ticker analysis (default if ticker found)
    if tickers:
        return ("ticker_analysis", tickers)

    # General / unknown — let Claude use MCP directly
    return ("general", [])


def _extract_all_tickers(prompt: str) -> list:
    """Extract ALL stock tickers from prompt. Returns list."""
    skip = {"THE", "AND", "FOR", "ALL", "USE", "MCP", "RSI", "MACD", "ETF",
            "NOT", "GET", "SET", "PUT", "CALL", "RUN", "END", "NEW", "OLD",
            "WAR", "TAX", "BUY", "SELL", "HOLD", "ADD", "EOD", "DTE", "OTM",
            "ITM", "ATM", "CCPC", "CRA", "RDTOH", "TFSA", "RRSP", "LIRA",
            "FULL", "DEEP", "DIVE", "REPORT", "ANALYSIS", "MONDAY", "AHMED",
            "LONG", "SHORT", "SCAN", "FIND", "SHOW", "LIST", "CHECK", "IRON",
            "BULL", "BEAR", "TRADE", "PLAN", "MARKET", "SECTOR", "OPTIONS",
            "DAILY", "WEEKLY", "TODAY", "STOCK", "STOCKS", "OPEN", "HIGH",
            "LOW", "CLOSE", "VOLUME", "PRICE", "ENTRY", "EXIT", "STOP",
            "TARGET", "RISK", "REWARD", "SETUP", "GRADE", "SIGNAL", "GATE"}
    found = []
    for match in re.finditer(r'\b([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b', prompt):
        t = match.group(1)
        if t not in skip and t not in found:
            found.append(t)
    return found


def _build_tool_list(request_type: str, tickers: list) -> list:
    """Build the right tool list based on request type. Returns [(label, real_tool_name, args)]."""
    tools = []

    if request_type == "ticker_analysis":
        t = tickers[0]
        # Full analysis battery
        tools += [
            (f"quotes_{t}",              "get_questrade_quotes",      {"symbols": [t]}),
            (f"signal_{t}",              "generate_trading_signal",   {"ticker": t}),
            (f"catalysts_{t}",           "detect_catalyst_strength",  {"ticker": t}),
            (f"technical_{t}",           "analyze_technical",         {"ticker": t}),
            (f"ticker_data_{t}",         "get_ticker_data",           {"ticker": t}),
            (f"options_mcmillan_{t}",    "analyze_options_mcmillan",  {"ticker": t}),
            (f"support_resistance_{t}",  "find_support_resistance",   {"ticker": t}),
            (f"quality_{t}",             "calculate_quality_score",   {"ticker": t}),
            (f"options_plan_{t}",        "generate_options_trade_plan", {"ticker": t}),
        ]
        # Positions across all accounts
        for acct in QUESTRADE_ACCOUNTS:
            tools.append((f"positions_{acct}", "get_questrade_positions", {"account_number": acct}))

    elif request_type == "options_focus":
        t = tickers[0] if tickers else ""
        if t:
            tools += [
                (f"quotes_{t}",            "get_questrade_quotes",        {"symbols": [t]}),
                (f"technical_{t}",         "analyze_technical",           {"ticker": t}),
                (f"options_mcmillan_{t}",  "analyze_options_mcmillan",    {"ticker": t}),
                (f"options_plan_{t}",      "generate_options_trade_plan", {"ticker": t}),
                (f"signal_{t}",            "generate_trading_signal",     {"ticker": t}),
                (f"catalysts_{t}",         "detect_catalyst_strength",    {"ticker": t}),
                (f"ticker_data_{t}",       "get_ticker_data",             {"ticker": t}),
            ]
            for acct in QUESTRADE_ACCOUNTS:
                tools.append((f"positions_{acct}", "get_questrade_positions", {"account_number": acct}))

    elif request_type == "comparison":
        for t in tickers[:4]:  # max 4 tickers
            tools += [
                (f"quotes_{t}",     "get_questrade_quotes",    {"symbols": [t]}),
                (f"signal_{t}",     "generate_trading_signal", {"ticker": t}),
                (f"technical_{t}",  "analyze_technical",       {"ticker": t}),
                (f"catalysts_{t}",  "detect_catalyst_strength",{"ticker": t}),
                (f"quality_{t}",    "calculate_quality_score", {"ticker": t}),
            ]

    elif request_type == "market_scan_long":
        tools += [
            ("fear_greed",       "get_cnn_fear_greed_index",  {}),  # light — token warmup
            ("scan_long",        "scan_long_candidates",     {}),
            ("scan_market",      "scan_market_opportunities", {}),
        ]

    elif request_type == "market_scan_short":
        tools += [
            ("fear_greed",       "get_cnn_fear_greed_index",  {}),  # light — token warmup
            ("scan_short",       "scan_short_candidates",     {}),
            ("scan_market",      "scan_market_opportunities", {}),
        ]

    elif request_type == "market_scan":
        tools += [
            ("fear_greed",       "get_cnn_fear_greed_index",  {}),  # light — runs first as token warmup
            ("scan_long",        "scan_long_candidates",      {}),
            ("scan_short",       "scan_short_candidates",     {}),
            ("scan_market",      "scan_market_opportunities", {}),
        ]

    elif request_type == "portfolio_review":
        for acct in QUESTRADE_ACCOUNTS:
            tools.append((f"positions_{acct}", "get_questrade_positions", {"account_number": acct}))
            tools.append((f"balances_{acct}",  "get_questrade_balances",  {"account_number": acct}))
        tools.append(("accounts", "get_questrade_accounts", {}))
        # If specific ticker mentioned, add its analysis too
        for t in tickers[:3]:
            tools += [
                (f"quotes_{t}",   "get_questrade_quotes",    {"symbols": [t]}),
                (f"signal_{t}",   "generate_trading_signal", {"ticker": t}),
            ]

    return tools


def gather_mcp_data(tools: list, pq, stage: str = "generator") -> dict:
    """Fire a list of MCP tools in PARALLEL. tools = [(label, real_tool_name, args)].
    Runs the FIRST tool alone to warm up the Questrade token (single-use refresh),
    then fires the rest in parallel using the cached access_token.
    """
    log = lambda msg: print(f"  [{stage}] {msg}", flush=True)
    total = len(tools)
    log(f"Firing {total} MCP tools ({total-1} parallel after token warmup)")
    push(pq, stage, "running", f"Firing {total} MCP tools ({total-1} parallel after token warmup)…")
    results = {}

    # ── Token warmup: run first tool alone so token refresh is single-threaded ──
    # Questrade refresh tokens are SINGLE USE. If multiple processes refresh
    # simultaneously, only one succeeds → rest get HTTP 400. Running one first
    # ensures the access_token is cached for all subsequent parallel calls.
    if tools:
        first_label, first_name, first_args = tools[0]
        log(f"Warmup: {first_label}")
        push(pq, stage, "running", f"→ {first_label} (token warmup)")
        try:
            result = _call_mcp_tool(first_name, first_args)
            results[first_label] = result
            if "error" in result:
                log(f"✗ {first_label}: {result['error'][:80]}")
                push(pq, stage, "running", f"✗ {first_label}: {result['error'][:60]}")
            else:
                data_len = len(result.get("data", ""))
                log(f"✓ {first_label} ({data_len:,} chars)")
                push(pq, stage, "running", f"✓ {first_label} ({data_len:,} chars)")
        except Exception as e:
            results[first_label] = {"tool": first_label, "error": str(e)}
            log(f"✗ {first_label}: {e}")
            push(pq, stage, "running", f"✗ {first_label}: {e}")

    remaining = tools[1:]
    if remaining:
        log(f"Parallel: {len(remaining)} tools")
    with ThreadPoolExecutor(max_workers=max(len(remaining), 1)) as pool:
        futures = {}
        for label, real_name, args in remaining:
            f = pool.submit(_call_mcp_tool, real_name, args)
            futures[f] = label
            push(pq, stage, "running", f"→ {label}")

        for future in as_completed(futures):
            label = futures[future]
            try:
                result = future.result()
                results[label] = result
                if "error" in result:
                    log(f"✗ {label}: {result['error'][:80]}")
                    push(pq, stage, "running", f"✗ {label}: {result['error'][:60]}")
                else:
                    data_len = len(result.get("data", ""))
                    log(f"✓ {label} ({data_len:,} chars)")
                    push(pq, stage, "running", f"✓ {label} ({data_len:,} chars)")
            except Exception as e:
                results[label] = {"tool": label, "error": str(e)}
                log(f"✗ {label}: {e}")
                push(pq, stage, "running", f"✗ {label}: {e}")

    push(pq, stage, "running", f"All {total} tools complete")
    return results


def _format_mcp_results(results: dict) -> str:
    """Format gathered MCP tool results into text for Claude prompt injection."""
    sections = []
    for tool_name, result in results.items():
        if "error" in result:
            sections.append(f"## {tool_name}\n[ERROR: {result['error']}]")
        else:
            sections.append(f"## {tool_name}\n{result.get('data', '[No data]')}")
    return "\n\n" + "=" * 70 + "\nPRE-FETCHED MCP DATA (live from investor-agent)\n" + "=" * 70 + "\n\n" + "\n\n---\n\n".join(sections) + "\n"


def _extract_ticker(prompt: str) -> str:
    """Extract first stock ticker from prompt. Returns '' if not found."""
    tickers = _extract_all_tickers(prompt)
    return tickers[0] if tickers else ""


def _mcp_output_valid(text: str) -> bool:
    """Check if Claude output contains real MCP data vs 'tools not available' failure."""
    lower = text.lower()
    # Failure markers — Claude couldn't connect to MCP or just narrated about tools
    fail_markers = [
        "mcp tools not available", "mcp server connection", "tools are not available",
        "cannot access", "not available in my current tool set", "no tools found",
        "mcp tools from investor-agent", "need to restart",
        "let me wait for", "waiting for the tool", "once i receive",
    ]
    for fm in fail_markers:
        if fm in lower:
            return False
    # Must have actual data — numbers with $ or % (not just narrative about tools)
    import re
    has_price = bool(re.search(r'\$\d+\.?\d*', text))          # $123.45
    has_pct = bool(re.search(r'\d+\.?\d*%', text))             # 65.3%
    has_rsi = bool(re.search(r'rsi[:\s]+\d', lower))           # RSI: 54
    has_gate = bool(re.search(r'gate[s]?\s*(?:passed|failed|:)', lower))  # gates passed
    hits = sum([has_price, has_pct, has_rsi, has_gate])
    if hits < 2:
        return False
    # Also need minimum length — real reports are 2000+ chars
    return len(text) > 2000



def _drain_stderr(proc, log_fn):
    """Drain stderr in background thread to prevent pipe buffer deadlock. Log ALL lines."""
    try:
        for line in proc.stderr:
            line = line.strip()
            if line:
                if log_fn:
                    log_fn(f"STDERR: {line[:300]}")
                else:
                    print(f"  [stderr] {line[:300]}", flush=True)
    except Exception:
        pass

# Track active Claude processes — kill stale ones before starting new
_active_claude: dict = {}  # {pid: {"proc": Popen, "stage": str, "started": float}}
_active_claude_lock = threading.Lock()

def _cleanup_stale_claude(log):
    """Kill any previous Claude processes that are still running."""
    with _active_claude_lock:
        to_remove = []
        for pid, info in _active_claude.items():
            proc = info["proc"]
            if proc.poll() is None:
                age = time.time() - info["started"]
                log(f"Killing stale Claude PID {pid} ({info['stage']}, {age:.0f}s old)")
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
            to_remove.append(pid)
        for pid in to_remove:
            del _active_claude[pid]

def _track_claude(proc, stage):
    """Register a Claude process for cleanup tracking."""
    with _active_claude_lock:
        _active_claude[proc.pid] = {"proc": proc, "stage": stage, "started": time.time()}

def _untrack_claude(proc):
    """Remove a Claude process from tracking."""
    with _active_claude_lock:
        _active_claude.pop(proc.pid, None)


def _run_claude_once(prompt: str, stage: str, pq, env: dict, needs_mcp: bool = True) -> str:
    """Single claude -p execution with stream-json output for live tool visibility.
    needs_mcp=True  → prompt as CLI arg, loads MCP tools (investor-agent).
    needs_mcp=False → prompt as CLI arg, --strict-mcp-config skips all plugins (fast).
    """
    log = lambda msg: print(f"  [{stage}] {msg}", flush=True)

    # Kill any stale Claude processes from previous jobs before starting a new one
    _cleanup_stale_claude(log)

    if needs_mcp:
        # MCP mode: prompt as CLI arg, loads investor-agent MCP tools
        cmd = [CLAUDE_BIN, "-p", prompt, "--dangerously-skip-permissions",
               "--output-format", "stream-json", "--verbose"]
    else:
        # No-MCP mode: prompt as CLI arg, --strict-mcp-config skips all plugins (fast)
        cmd = [CLAUDE_BIN, "-p", prompt, "--dangerously-skip-permissions",
               "--output-format", "stream-json", "--verbose",
               "--no-session-persistence",
               "--mcp-config", str(REPO / ".mcp-empty.json"), "--strict-mcp-config"]
    stdin_mode = subprocess.DEVNULL

    log(f"CMD: claude -p <{len(prompt):,} chars> (mcp={'ON' if needs_mcp else 'SKIP, strict-empty'})")

    text_parts = []       # collected final text output
    result_text = ""
    _chars_logged = [0]   # mutable counter for periodic progress logging
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=stdin_mode,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env, cwd=str(REPO),
            text=True, bufsize=1, start_new_session=True,
        )

        _track_claude(proc, stage)
        log(f"PID {proc.pid} started")

        # Drain stderr in background to prevent deadlock
        stderr_thread = threading.Thread(target=_drain_stderr, args=(proc, log), daemon=True)
        stderr_thread.start()

        fd = proc.stdout.fileno()
        last_activity = time.time()
        STARTUP_TIMEOUT = 600
        IDLE_TIMEOUT = 300    # longer — tool calls can take 60s+ each
        empty_reads = 0

        while True:
            ready, _, _ = select.select([fd], [], [], 5.0)
            if ready:
                line = proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    empty_reads += 1
                    if empty_reads > 10:
                        # Prevent busy loop on empty reads — check heartbeat
                        elapsed = time.time() - last_activity
                        if elapsed > 5:
                            mins = int(elapsed) // 60
                            secs = int(elapsed) % 60
                            push(pq, stage, "running", f"Claude generating… {mins}m{secs:02d}s")
                        if proc.poll() is not None:
                            log(f"Process died during empty reads! rc={proc.returncode}")
                            break
                        time.sleep(0.5)
                        empty_reads = 0
                    continue
                empty_reads = 0
                last_activity = time.time()

                # Parse stream-json event
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    log(f"Non-JSON: {line[:120]}")
                    continue

                etype = ev.get("type", "")

                # System init event (stream-json input mode)
                if etype == "system":
                    log(f"System init (session={ev.get('session_id', '')[:12]})")
                    last_activity = time.time()
                    continue

                # Full assistant message (stream-json input mode)
                elif etype == "assistant":
                    content = ev.get("message", {}).get("content", [])
                    for block in content:
                        if block.get("type") == "text":
                            txt = block.get("text", "")
                            if txt:
                                text_parts.append(txt)
                                push(pq, stage, "streaming", "", txt)

                # Tool use — show which MCP tool is being called
                elif etype == "content_block_start":
                    cb = ev.get("content_block", {})
                    if cb.get("type") == "tool_use":
                        tool_name = cb.get("name", "?")
                        log(f"Tool call: {tool_name}")
                        push(pq, stage, "running", f"Calling {tool_name}…")

                # Tool result — show tool completed
                elif etype == "content_block_stop":
                    idx = ev.get("index", -1)
                    push(pq, stage, "running", f"Tool #{idx} done")

                # Text delta — actual report output streaming
                elif etype == "content_block_delta":
                    delta = ev.get("delta", {})
                    if delta.get("type") == "text_delta":
                        txt = delta.get("text", "")
                        if txt:
                            text_parts.append(txt)
                            push(pq, stage, "streaming", "", txt)
                            # Log markdown headings — console + UI status
                            for ln in txt.split("\n"):
                                stripped = ln.strip()
                                if stripped.startswith("#"):
                                    heading = stripped[:80]
                                    log(f"  {heading}")
                                    push(pq, stage, "running", f"Writing: {heading}")
                            # Log progress every 5K chars — console + UI status
                            total_chars = sum(len(p) for p in text_parts)
                            if total_chars - _chars_logged[0] >= 5000:
                                msg = f"Writing… {total_chars:,} chars"
                                log(f"  ...{msg}")
                                push(pq, stage, "running", msg)
                                _chars_logged[0] = total_chars

                # Result message — final combined output
                elif etype == "result":
                    result_text = ev.get("result", "")
                    # Push result to UI so user sees Claude output (not just Gemini)
                    if result_text and not text_parts:
                        # No streaming deltas arrived — push full result as chunk
                        push(pq, stage, "streaming", "", result_text)
                    break

                # Message start/stop — informational
                elif etype == "message_start":
                    push(pq, stage, "running", "Claude thinking…")
                elif etype == "error":
                    err = ev.get("error", {}).get("message", str(ev))
                    log(f"Stream error: {err}")
                    push(pq, stage, "running", f"Error: {err[:80]}")
                else:
                    log(f"Event: {etype}")

            else:
                elapsed = time.time() - last_activity
                timeout = STARTUP_TIMEOUT if not text_parts else IDLE_TIMEOUT
                if elapsed > timeout:
                    log(f"TIMEOUT: No activity for {elapsed:.0f}s — killing")
                    proc.kill()
                    proc.wait()
                    result_text = f"[TIMEOUT — no activity for {elapsed:.0f}s]"
                    break
                # Heartbeat so UI shows progress during MCP init
                if elapsed > 5:
                    mins = int(elapsed) // 60
                    secs = int(elapsed) % 60
                    push(pq, stage, "running", f"Waiting for Claude… {mins}m{secs:02d}s")
                if proc.poll() is not None:
                    log(f"Process died! rc={proc.returncode} after {elapsed:.0f}s idle")
                    # Drain remaining stdout
                    for line in proc.stdout:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            ev = json.loads(line)
                            if ev.get("type") == "result":
                                result_text = ev.get("result", "")
                                if result_text and not text_parts:
                                    push(pq, stage, "streaming", "", result_text)
                            elif ev.get("type") == "content_block_delta":
                                d = ev.get("delta", {})
                                if d.get("type") == "text_delta":
                                    txt = d.get("text", "")
                                    if txt:
                                        text_parts.append(txt)
                                        push(pq, stage, "streaming", "", txt)
                        except json.JSONDecodeError:
                            pass
                    break

        if not result_text:
            try:
                proc.wait(timeout=30)
            except Exception:
                proc.kill()
            result_text = "".join(text_parts).strip()

        log(f"Done code={proc.returncode} output={len(result_text):,} chars ({len(text_parts)} parts)")

    except subprocess.TimeoutExpired:
        proc.kill()
        result_text = "[Timed out]"
    except Exception as e:
        result_text = f"[Error: {e}]"
        log(f"ERROR: {e}")
    finally:
        _untrack_claude(proc)

    return result_text


def run_claude(prompt: str, stage: str, pq,
               validate_mcp: bool = False, max_retries: int = 2,
               needs_mcp: bool = True) -> str:
    """
    Run Claude Code CLI → return output text.
    If validate_mcp=True, checks output for real MCP data and retries on failure.
    needs_mcp=False → skip MCP server loading (saves 30-60s startup).
    """
    log = lambda msg: print(f"  [{stage}] {msg}", flush=True)
    push(pq, stage, "running", f"{stage} starting…")

    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY_HELPER", None)
    env.pop("CLAUDECODE", None)  # Allow launching claude -p from within a Claude session
    env["PATH"] = f"{CLAUDE_PATH}:{env.get('PATH', '/usr/bin:/bin')}"

    result_text = _run_claude_once(prompt, stage, pq, env, needs_mcp=needs_mcp)

    # Retry loop for MCP validation failures
    if validate_mcp and not _mcp_output_valid(result_text):
        for attempt in range(1, max_retries + 1):
            log(f"MCP VALIDATION FAILED — retry {attempt}/{max_retries}")
            push(pq, stage, "running",
                 f"MCP tools didn't load — retrying ({attempt}/{max_retries})…")
            time.sleep(5)
            result_text = _run_claude_once(prompt, stage, pq, env, needs_mcp=needs_mcp)
            if _mcp_output_valid(result_text):
                log(f"MCP VALIDATION PASSED on retry {attempt}")
                break
        else:
            log("MCP VALIDATION FAILED after all retries — using last output")
            push(pq, stage, "running", "WARNING: MCP tools may not have loaded")

    log(f"Done: {len(result_text):,} chars")
    push(pq, stage, "done", f"{stage.title()} done ({len(result_text):,} chars)")
    return result_text


def run_gemini(prompt: str, stage: str, pq) -> str:
    """Run Gemini CLI → return output text. Plain text mode (no stream-json)."""
    log = lambda msg: print(f"  [{stage}] {msg}", flush=True)
    push(pq, stage, "running", f"{stage} starting…")

    env = os.environ.copy()
    env.pop("GEMINI_API_KEY", None)
    env["PATH"] = f"{CLAUDE_PATH}:{env.get('PATH', '/usr/bin:/bin')}"

    cmd = [GEMINI_BIN, "-p", ""]
    log(f"CMD: gemini -p")
    log(f"Prompt: {len(prompt):,} chars")

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env, cwd=str(REPO),
            text=True, bufsize=1, start_new_session=True,
        )

        def feed():
            try:
                proc.stdin.write(prompt)
                proc.stdin.close()
            except Exception:
                pass
        threading.Thread(target=feed, daemon=True).start()

        output_parts = []
        _gem_chars = [0]
        fd = proc.stdout.fileno()
        last_output = time.time()

        while True:
            ready, _, _ = select.select([fd], [], [], 5.0)
            if ready:
                line = proc.stdout.readline()
                if not line:
                    break
                output_parts.append(line)
                push(pq, stage, "streaming", "", line)
                last_output = time.time()
                # Log headings and progress — console + UI status
                stripped = line.strip()
                if stripped.startswith("#"):
                    heading = stripped[:80]
                    log(f"  {heading}")
                    push(pq, stage, "running", f"Writing: {heading}")
                _gem_chars[0] += len(line)
                if _gem_chars[0] % 2000 < len(line):
                    msg = f"Writing… {_gem_chars[0]:,} chars"
                    log(f"  ...{msg}")
                    push(pq, stage, "running", msg)
            else:
                elapsed = time.time() - last_output
                timeout = 300 if not output_parts else 180
                if elapsed > timeout:
                    log(f"TIMEOUT: No output for {elapsed:.0f}s — killing")
                    proc.kill()
                    proc.wait()
                    output_parts.append(f"\n[TIMEOUT — {elapsed:.0f}s]\n")
                    break
                if proc.poll() is not None:
                    break

        proc.wait(timeout=30)
        result = "".join(output_parts).strip()
        log(f"Done code={proc.returncode} output={len(result):,} chars")

    except subprocess.TimeoutExpired:
        proc.kill()
        result = "[Timed out]"
    except Exception as e:
        result = f"[Error: {e}]"
        log(f"ERROR: {e}")

    log(f"Done: {len(result):,} chars")
    push(pq, stage, "done", f"{stage.title()} done ({len(result):,} chars)")
    return result


def send_email(subject: str, body: str) -> str:
    """Send final report via Gmail SMTP."""
    if not GMAIL_PASS:
        return "EMAIL_SKIPPED: No GMAIL_APP_PASSWORD in .env"
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO
        html = f"""<html><body>
<h2 style="font-family:sans-serif;color:#333">{subject}</h2>
<pre style="font-family:monospace;font-size:13px;line-height:1.6;background:#f5f5f5;
            padding:20px;border-radius:4px;white-space:pre-wrap">{body}</pre>
</body></html>"""
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL_FROM, GMAIL_PASS)
            s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        return f"EMAIL_SENT → {EMAIL_TO}"
    except Exception as e:
        return f"EMAIL_FAILED: {e}"


# ── Pipeline ──────────────────────────────────────────────────────────────────

def pipeline(job_id, prompt, name, pq):
    """
    File-based async pipeline:
      Stage 1 → DRAFT file   (Claude + MCP tools)
      Stage 2 → AUDIT file   (Gemini reads DRAFT)
      Stage 3 → FINAL file   (Claude reads DRAFT + AUDIT)
      Email   → sends FINAL
    Each stage is independent — reads input from files, writes output to files.
    """
    def update_job(**kwargs):
        with _jobs_lock:
            if job_id in _jobs:
                for k, v in kwargs.items():
                    _jobs[job_id][k] = v

    try:
        update_job(status="running", stage="generator")
        VAULT.mkdir(parents=True, exist_ok=True)
        date = datetime.now().strftime("%Y-%m-%d_%H%M")
        safe = re.sub(r"[^A-Z0-9_]", "_", name.upper())[:35]

        final_file = VAULT / f"{safe}_{date}.md"

        # ── Stage 1: Generator (Claude) → draft text in memory ──────────
        req_type, tickers = _classify_request(prompt)
        tool_list = _build_tool_list(req_type, tickers)
        ticker = tickers[0] if tickers else ""
        print(f"  [generator] Type: {req_type} | Tickers: {tickers} | Tools: {len(tool_list)}", flush=True)

        if tool_list:
            # ── Parallel MCP path: gather data first, then Claude writes report ──
            mcp_data = gather_mcp_data(tool_list, pq, "generator")
            mcp_text = _format_mcp_results(mcp_data)
            successful = sum(1 for r in mcp_data.values() if "error" not in r)
            print(f"  [generator] MCP data gathered: {successful}/{len(mcp_data)} tools OK", flush=True)

            gen_prompt = f"""You are Ahmed's senior financial analyst. Write a comprehensive trading report using the LIVE MCP data below.

REPORT FORMAT (follow EXACTLY):
{REPORT_FORMAT}

{mcp_text}

AHMED'S REQUEST: {prompt}

INSTRUCTIONS:
- The MCP data above is LIVE from {len(mcp_data)} parallel tool calls — use it directly. Do NOT call any tools.
- Follow the report format above EXACTLY.
- Apply 5-gate validation: Catalyst + Freshness + Al Brooks + Quality + Institutional.
- Include ALL data: price, signal, catalysts, technicals, support/resistance, quality score.
- POSITIONS: Data includes positions from all 7 Questrade accounts. Report any holdings of analyzed tickers with account, quantity, cost basis, P&L. If none, state clearly.
- OPTIONS: Include full McMillan analysis and options trade plan with specific strikes, expiries, strategy.

End with:
AUDIT_TARGETS
=============
[Numbered list of every verifiable claim]
"""
            draft_text = run_claude(gen_prompt, "generator", pq, validate_mcp=False, needs_mcp=False)
        else:
            # ── Fallback: no tools selected (general/unknown) → Claude uses MCP directly ──
            print(f"  [generator] General request — Claude will use MCP tools directly", flush=True)
            gen_prompt = f"""You are Ahmed's senior financial analyst. Use the investor-agent MCP tools to execute this request.

{CONTEXT}

AHMED'S REQUEST: {prompt}

Call whatever MCP tools are needed. Follow the report format from SCANNER_REPORT_GENERATOR.md. Use SCANNER_INSTRUCTIONS.md for methodology.

End with:
AUDIT_TARGETS
=============
[Numbered list of every verifiable claim]
"""
            draft_text = run_claude(gen_prompt, "generator", pq, validate_mcp=True)

        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["stage"] = "auditor"

        if len(draft_text.strip()) < 100:
            push(pq, "error", "error", "Generator failed — no draft produced")
            update_job(status="error", error="Generator failed — no draft produced")
            return

        # ── Stage 2: Auditor (Gemini) reads draft → audit text in memory ─
        audit_prompt = f"""{AUDITOR_SYS}

Audit this financial analysis aggressively:

{draft_text}"""
        audit_text = run_gemini(audit_prompt, "auditor", pq)

        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["stage"] = "resolver"

        # ── Stage 3: Resolver (Claude) reads draft + audit → FINAL file ──
        res_prompt = f"""{RESOLVER_SYS}

{'='*70}
ORIGINAL REPORT (Claude Code with live MCP data)
{'='*70}
{draft_text}

{'='*70}
GEMINI ADVERSARIAL AUDIT
{'='*70}
{audit_text or "[No audit]"}

Now produce RESOLUTION_LOG, then FINAL_REPORT, then CONFIDENCE_SUMMARY, then HUMAN_REVIEW_REQUIRED.
"""
        final_text = run_claude(res_prompt, "resolver", pq, needs_mcp=False)

        # ── Save only the FINAL report to vault ──────────────────────────
        header = f"# {name}\nGenerated: {datetime.now():%Y-%m-%d %H:%M}\n\n---\n\n"
        final_file.write_text(header + final_text, encoding="utf-8")
        print(f"  [vault] Saved: {final_file} ({final_file.stat().st_size:,} bytes)", flush=True)

        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["files"]["FINAL"] = str(final_file)
                _jobs[job_id]["stage"] = "email"

        # ── Email FINAL report ───────────────────────────────────────────
        push(pq, "email", "running", f"Emailing to {EMAIL_TO}…")
        subject = f"[Analyst] {name} — {datetime.now():%Y-%m-%d %H:%M}"
        email_status = send_email(subject, final_text)
        push(pq, "email", "done", email_status)

        final_files = {"FINAL": str(final_file)}
        update_job(status="done", stage="complete", files=final_files)
        pq.put({
            "stage": "complete", "status": "done", "message": "Pipeline complete",
            "files": final_files, "email_status": email_status,
        })

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"  [pipeline] EXCEPTION: {e}\n{tb}", flush=True)
        push(pq, "error", "error", str(e))
        update_job(status="error", error=str(e))


def _cleanup_old_jobs():
    """Remove jobs older than 4 hours in done/error state."""
    cutoff = time.time() - 4 * 3600
    with _jobs_lock:
        to_remove = [jid for jid, j in _jobs.items()
                     if j["status"] in ("done", "error") and j["created"] < cutoff]
        for jid in to_remove:
            del _jobs[jid]


# ── HTTP Server ───────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"   # HTTP/1.0 = read-until-close, natural for SSE
    def log_message(self, *a): pass
    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, BrokenPipeError):
            self.close_connection = True  # suppress noisy tracebacks from dropped connections

    def _check_auth(self):
        """Returns True if auth valid, sends 401 if not."""
        # Check Authorization header (fetch/curl)
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                user, pwd = decoded.split(":", 1)
                if user == AUTH_USER and pwd == AUTH_PASS:
                    return True
            except Exception:
                pass
        # Check ?token= query param (EventSource can't send headers)
        qs = parse_qs(urlparse(self.path).query)
        token = qs.get("token", [""])[0]
        if token:
            try:
                decoded = base64.b64decode(token).decode("utf-8")
                user, pwd = decoded.split(":", 1)
                if user == AUTH_USER and pwd == AUTH_PASS:
                    return True
            except Exception:
                pass
        body = json.dumps({"error": "Unauthorized"}).encode()
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Analyst Server"')
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors(); self.end_headers()
        self.wfile.write(body); self.wfile.flush()
        return False

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors(); self.end_headers()
        self.wfile.write(body); self.wfile.flush()

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")

    def do_OPTIONS(self):
        self.send_response(200); self._cors()
        self.send_header("Content-Length", "0"); self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Health check — no auth
        if path == "/health":
            with _jobs_lock:
                active = sum(1 for j in _jobs.values() if j["status"] in ("queued", "running"))
                total = len(_jobs)
            self._json(200, {
                "ok": True, "vault": str(VAULT), "context_chars": len(CONTEXT),
                "active_jobs": active, "total_jobs": total, "max_concurrent": 3,
                "email_from": EMAIL_FROM, "email_to": EMAIL_TO,
                "claude_bin": CLAUDE_BIN, "mode": "SUBSCRIPTION (no API credits)",
            })
            return

        # All other endpoints require auth
        if not self._check_auth():
            return

        if path in ("/", "/index.html"):
            body = UI.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors(); self.end_headers()
            self.wfile.write(body); self.wfile.flush()

        elif path == "/jobs":
            _cleanup_old_jobs()
            with _jobs_lock:
                jobs_list = [{
                    "id": j["id"], "name": j["name"], "status": j["status"],
                    "stage": j["stage"], "created": j["created"],
                    "files": j["files"], "error": j["error"],
                } for j in _jobs.values()]
            self._json(200, {"jobs": sorted(jobs_list, key=lambda x: x["created"], reverse=True)})

        elif path.startswith("/jobs/") and not path.endswith("/stream"):
            # /jobs/{id} — poll a single job's status (mobile fallback)
            parts = path.split("/")
            if len(parts) != 3:
                self._json(404, {"error": "Not found"}); return
            job_id = parts[2]
            with _jobs_lock:
                job = _jobs.get(job_id)
            if not job:
                self._json(404, {"error": "Job not found"}); return
            self._json(200, {
                "id": job["id"], "name": job["name"], "status": job["status"],
                "stage": job["stage"], "created": job["created"],
                "files": job["files"], "error": job["error"],
            })

        elif path.startswith("/jobs/") and path.endswith("/stream"):
            parts = path.split("/")
            if len(parts) != 4:
                self._json(404, {"error": "Not found"}); return
            job_id = parts[2]
            with _jobs_lock:
                job = _jobs.get(job_id)
            if not job:
                self._json(404, {"error": "Job not found"}); return

            bq = job["pq"]
            sq = bq.subscribe()
            print(f"  [SSE] Client connected for job {job_id}, {sq.qsize()} buffered events", flush=True)

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self._cors(); self.end_headers()
            # Tell EventSource to reconnect after 3s on drop (default is browser-specific)
            self.wfile.write(b"retry: 3000\n\n")
            self.wfile.flush()

            try:
                n = 0
                while True:
                    try:
                        ev = sq.get(timeout=15)  # 15s keepalive (Cloudflare times out idle at ~100s)
                        payload = f"data: {json.dumps(ev)}\n\n".encode()
                        self.wfile.write(payload)
                        self.wfile.flush()
                        n += 1
                        cur_stage = ev.get("stage", "")
                        if n == 1:
                            print(f"  [SSE] job={job_id[:8]} streaming started (stage={cur_stage})", flush=True)
                        if ev.get("stage") in ("complete", "error"):
                            print(f"  [SSE] job={job_id} stream complete after {n} events", flush=True)
                            break
                    except queue.Empty:
                        try:
                            self.wfile.write(b": keepalive\n\n"); self.wfile.flush()
                        except:
                            break
            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                print(f"  [SSE] job={job_id} client disconnected: {e}", flush=True)
            finally:
                bq.unsubscribe(sq)

        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path not in ("/analyze", "/notify"):
            self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return

        if not self._check_auth():
            return

        # ── /notify — send an email via the server's configured SMTP ─────
        if parsed.path == "/notify":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n))
            subject = body.get("subject", "Analyst Server Notification")
            message = body.get("message", "")
            if not message:
                self._json(400, {"error": "No message"}); return
            result = send_email(subject, message)
            self._json(200, {"result": result})
            return

        _cleanup_old_jobs()

        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n))
        prompt = body.get("prompt", "").strip()
        name   = body.get("name", "ANALYSIS").strip() or "ANALYSIS"

        if not prompt:
            self._json(400, {"error": "No prompt"}); return

        job_id = uuid.uuid4().hex[:12]
        pq = BroadcastQueue()
        job = {
            "id": job_id, "status": "queued", "name": name,
            "prompt": prompt, "created": time.time(),
            "stage": "queued", "pq": pq, "files": {}, "error": None,
        }

        with _jobs_lock:
            active = sum(1 for j in _jobs.values() if j["status"] in ("queued", "running"))
            if active >= 3:
                too_many = True
            else:
                too_many = False
                _jobs[job_id] = job

        if too_many:
            self._json(429, {"error": "Max 3 concurrent jobs. Wait for one to finish."}); return

        _pool.submit(pipeline, job_id, prompt, name, pq)
        self._json(200, {"job_id": job_id, "name": name})


# ── UI ────────────────────────────────────────────────────────────────────────

UI = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ahmed's Analyst</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,300;0,400;0,500;1,400&family=Cormorant+Garamond:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0c0c10;--surf:#111118;--card:#16161f;--b0:#1c1c2a;--b1:#282840;
  --gold:#d4a853;--goldDim:#7a5e28;--goldGlow:rgba(212,168,83,.1);
  --claude:#e07b5a;--gemini:#5b8ef0;--resolve:#4caf7d;--email:#b06ef0;
  --txt:#dddbe8;--dim:#6e6c84;--muted:#35334a;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden}
body{background:var(--bg);color:var(--txt);font-family:'IBM Plex Mono',monospace;
     display:grid;grid-template-rows:54px 1fr 90px}

header{background:var(--surf);border-bottom:1px solid var(--b0);
       display:flex;align-items:center;padding:0 22px;gap:14px}
.brand{font-family:'Cormorant Garamond',serif;font-size:20px;font-weight:700;
       color:var(--gold);letter-spacing:.04em}
.brand em{font-style:normal;font-size:9px;color:var(--dim);margin-left:8px;
           font-family:'IBM Plex Mono',monospace;letter-spacing:.12em;text-transform:uppercase}
.free-badge{background:rgba(76,175,125,.1);border:1px solid rgba(76,175,125,.2);
            color:var(--resolve);font-size:8.5px;padding:2px 8px;border-radius:20px;
            letter-spacing:.08em}
.pills{margin-left:auto;display:flex;gap:7px}
.pill{display:flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;
      border:1px solid var(--b0);font-size:9.5px;color:var(--dim);letter-spacing:.08em}
.pip{width:5px;height:5px;border-radius:50%;background:var(--muted);transition:all .3s}
.pill.on .pip{background:var(--gold);box-shadow:0 0 7px var(--gold);animation:bk 1s infinite}
.pill.ok .pip{background:var(--resolve)}
@keyframes bk{0%,100%{opacity:1}50%{opacity:.25}}

main{display:grid;grid-template-columns:1fr 290px;overflow:hidden}
.chat{display:flex;flex-direction:column;border-right:1px solid var(--b0);overflow:hidden}
.msgs{flex:1;overflow-y:auto;padding:22px;display:flex;flex-direction:column;gap:14px}
.msgs::-webkit-scrollbar{width:3px}
.msgs::-webkit-scrollbar-thumb{background:var(--b0)}

.msg{display:flex;flex-direction:column;gap:4px}
.msg.you{align-items:flex-end}
.lbl{font-size:8.5px;color:var(--muted);letter-spacing:.1em;text-transform:uppercase}
.bbl{padding:10px 14px;font-size:12px;line-height:1.75;max-width:88%;
     word-break:break-word;white-space:pre-wrap}
.msg.you .bbl{background:var(--gold);color:#0c0c10;font-weight:500;border-radius:2px 2px 0 2px}
.msg.ai{align-items:flex-start}
.msg.ai .bbl{background:var(--card);border:1px solid var(--b0);border-radius:0 2px 2px 2px}

.pw{width:100%;display:flex;flex-direction:column;gap:5px}
.pblock{border:1px solid var(--b0);border-radius:2px;overflow:hidden}
.ph{padding:7px 12px;display:flex;align-items:center;gap:8px;font-size:10px;
    letter-spacing:.07em;text-transform:uppercase;cursor:pointer;user-select:none}
.ph:hover{background:rgba(255,255,255,.02)}
.ph.gen{border-left:2px solid var(--claude)}
.ph.aud{border-left:2px solid var(--gemini)}
.ph.res{border-left:2px solid var(--resolve)}
.ph-name{flex:1;font-weight:500}
.ph-stat{font-size:9.5px;color:var(--dim)}
.tog{color:var(--muted);font-size:8.5px;transition:transform .2s}
.tog.open{transform:rotate(180deg)}
.pb{padding:11px 13px;font-size:11px;line-height:1.85;color:var(--dim);
    border-top:1px solid var(--b0);max-height:280px;overflow-y:auto;
    white-space:pre-wrap;word-break:break-word;display:none}
.pb.show{display:block}
.pb::-webkit-scrollbar{width:2px}
.pb::-webkit-scrollbar-thumb{background:var(--b1)}
.cur{display:inline-block;width:5px;height:12px;background:var(--gold);
     animation:bk .65s infinite;vertical-align:text-bottom;margin-left:1px}
/* Tool grid for parallel MCP execution */
.tgrid{display:flex;flex-wrap:wrap;gap:4px;padding:8px 0}
.tgrid .tp{font-size:9px;padding:3px 8px;border-radius:3px;font-family:var(--mono,monospace);
  letter-spacing:.03em;transition:all .3s ease}
.tgrid .tp.pending{background:rgba(255,255,255,.04);color:var(--dim);border:1px solid var(--b0)}
.tgrid .tp.running{background:rgba(212,168,83,.12);color:var(--gold);border:1px solid var(--gold);
  animation:tpulse 1.2s infinite}
.tgrid .tp.done{background:rgba(50,205,50,.12);color:#50d050;border:1px solid rgba(50,205,50,.3)}
.tgrid .tp.error{background:rgba(255,70,70,.12);color:#ff5555;border:1px solid rgba(255,70,70,.3)}
.tphase{font-size:9.5px;color:var(--gold);text-transform:uppercase;letter-spacing:.1em;
  padding:4px 0;font-weight:600}
.tphase.compile{color:#50d050}
.tsummary{font-size:9px;color:var(--dim);padding:2px 0}
@keyframes tpulse{0%,100%{opacity:1}50%{opacity:.5}}

.bdg{display:inline-flex;padding:1px 7px;border-radius:20px;font-size:9px;margin-left:5px}
.bdg.warn{background:rgba(91,142,240,.1);color:var(--gemini);border:1px solid rgba(91,142,240,.2)}
.bdg.good{background:rgba(76,175,125,.1);color:var(--resolve);border:1px solid rgba(76,175,125,.2)}

.saved{background:rgba(76,175,125,.07);border:1px solid rgba(76,175,125,.18);
       border-radius:2px;padding:8px 12px;font-size:10.5px;color:var(--resolve);width:100%}
.emailed{background:rgba(176,110,240,.07);border:1px solid rgba(176,110,240,.18);
         border-radius:2px;padding:8px 12px;font-size:10.5px;color:var(--email);width:100%}

.intro{display:flex;flex-direction:column;align-items:center;justify-content:center;
       gap:12px;color:var(--dim);text-align:center;padding:40px;flex:1}
.ititle{font-family:'Cormorant Garamond',serif;font-size:32px;font-weight:700;color:var(--gold)}
.intro p{font-size:11.5px;line-height:2;max-width:400px}
.iflow{display:flex;align-items:center;gap:7px;margin-top:6px;flex-wrap:wrap;justify-content:center}
.in{padding:4px 11px;border:1px solid var(--b0);border-radius:2px;font-size:9.5px;letter-spacing:.06em}
.in.c{border-color:var(--claude);color:var(--claude)}
.in.g{border-color:var(--gemini);color:var(--gemini)}
.in.r{border-color:var(--resolve);color:var(--resolve)}
.in.v{border-color:var(--gold);color:var(--gold)}
.in.e{border-color:var(--email);color:var(--email)}
.arr{color:var(--muted);font-size:11px}

.side{background:var(--surf);padding:18px;display:flex;flex-direction:column;
      gap:16px;overflow:hidden}
.st{font-size:8.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);
    padding-bottom:9px;border-bottom:1px solid var(--b0);display:flex;align-items:center;gap:8px}
.jcount{color:var(--gold);font-weight:500}

.joblist{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:6px;min-height:0}
.joblist::-webkit-scrollbar{width:2px}
.joblist::-webkit-scrollbar-thumb{background:var(--b1)}

.jcard{background:var(--bg);border:1px solid var(--b0);border-radius:2px;
       padding:10px 12px;cursor:pointer;transition:all .17s}
.jcard:hover{border-color:var(--goldDim)}
.jcard.sel{border-color:var(--gold);background:var(--goldGlow)}
.jcard-top{display:flex;align-items:center;gap:8px}
.jdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.jdot.queued{background:var(--muted)}
.jdot.running{background:var(--gold);animation:bk 1s infinite}
.jdot.done{background:var(--resolve)}
.jdot.error{background:var(--claude)}
.jname{font-size:11px;font-weight:500;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.jtime{font-size:9px;color:var(--dim)}
.jstage{font-size:9.5px;color:var(--dim);margin-top:4px;margin-left:15px}

.empty-jobs{font-size:10.5px;color:var(--muted);text-align:center;padding:20px 0}

.job-view{display:flex;flex-direction:column;gap:14px}

.et{font-size:8.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.chips{display:flex;flex-direction:column;gap:5px;margin-top:7px}
.chip{background:var(--bg);border:1px solid var(--b0);border-radius:2px;
      padding:7px 9px;font-size:10px;color:var(--dim);cursor:pointer;
      transition:all .17s;line-height:1.55}
.chip:hover{border-color:var(--goldDim);color:var(--gold);background:var(--goldGlow)}

.ia{border-top:1px solid var(--b0);padding:13px 22px;background:var(--surf);
    display:flex;flex-direction:column;gap:8px}
.irow{display:flex;gap:8px;align-items:flex-end}
.iname{background:var(--bg);border:1px solid var(--b0);color:var(--txt);
       font-family:'IBM Plex Mono',monospace;font-size:10.5px;
       padding:8px 11px;border-radius:2px;width:145px;outline:none;transition:border .2s}
.iname:focus{border-color:var(--goldDim)}
.iname::placeholder{color:var(--muted)}
.ibox{flex:1;background:var(--bg);border:1px solid var(--b0);border-radius:2px;
      display:flex;align-items:flex-end;padding:8px 11px;transition:border .2s}
.ibox:focus-within{border-color:var(--goldDim)}
textarea{flex:1;background:transparent;border:none;outline:none;color:var(--txt);
         font-family:'IBM Plex Mono',monospace;font-size:12px;resize:none;
         line-height:1.65;max-height:85px;overflow-y:auto}
textarea::placeholder{color:var(--muted)}
.run{background:var(--gold);border:none;border-radius:2px;color:#0c0c10;
     cursor:pointer;font-family:'IBM Plex Mono',monospace;font-size:11px;
     font-weight:500;padding:8px 18px;transition:all .17s;white-space:nowrap;align-self:flex-end}
.run:hover{background:#ddb860}
.hint{font-size:9px;color:var(--muted)}
/* ── Mobile: stack layout, hide sidebar by default ── */
@media(max-width:700px){
  main{grid-template-columns:1fr!important}
  .side{display:none}
  .chat{border-right:none}
  .msgs{padding:12px}
  header{padding:0 12px}
  .pills{display:none}
  .input-area{padding:8px}
  .pb{max-height:50vh}
}
</style>
</head>
<body>

<header>
  <div class="brand">Analyst <em>by Ahmed</em></div>
  <div class="free-badge">✓ Subscription — No API Credits</div>
  <div class="pills">
    <div class="pill" id="p1"><span class="pip"></span>Generator</div>
    <div class="pill" id="p2"><span class="pip"></span>Auditor</div>
    <div class="pill" id="p3"><span class="pip"></span>Resolver</div>
  </div>
</header>

<main>
  <div class="chat">
    <div class="msgs" id="msgs">
      <div class="intro" id="intro">
        <div class="ititle">⬡ Analyst</div>
        <p>Multi-session async pipeline — run up to 3 scans concurrently.<br>
           Each scan: Claude + Gemini + Claude → Vault → Email.<br>
           Zero API credits consumed (subscription mode).</p>
        <div class="iflow">
          <div class="in c">Claude (free)</div><div class="arr">→</div>
          <div class="in g">Gemini (free)</div><div class="arr">→</div>
          <div class="in r">Claude Resolve</div><div class="arr">→</div>
          <div class="in v">Vault</div><div class="arr">→</div>
          <div class="in e">Email</div>
        </div>
      </div>
    </div>
  </div>

  <div class="side">
    <div class="st">Jobs <span class="jcount" id="jobCount"></span></div>
    <div id="joblist" class="joblist">
      <div class="empty-jobs" id="emptyJobs">No jobs yet — submit a prompt to start</div>
    </div>

    <div>
      <div class="et">Quick Prompts</div>
      <div class="chips">
        <div class="chip" onclick="use(this)">Full Monday war portfolio report — all 7 accounts</div>
        <div class="chip" onclick="use(this)">AVGO puts — both CCPC accounts, roll or close?</div>
        <div class="chip" onclick="use(this)">VIXY 250 shares — optimal spike exit timing</div>
        <div class="chip" onclick="use(this)">OKTA — war risk + earnings double risk + CCPC tax</div>
        <div class="chip" onclick="use(this)">Monday EOD action list — all open positions</div>
      </div>
    </div>
  </div>
</main>

<div id="dbg" style="position:fixed;top:56px;right:8px;background:#1a1a2e;border:1px solid #d4a853;
  padding:6px 12px;font-size:10px;color:#d4a853;z-index:999;border-radius:3px;font-family:monospace;
  max-width:340px;pointer-events:none;opacity:0.9">SSE: idle</div>

<div class="ia">
  <div class="irow">
    <input class="iname" id="rname" placeholder="Report name…" value="ANALYSIS">
    <div class="ibox">
      <textarea id="prompt" rows="1"
        placeholder="Ask your analyst — up to 3 concurrent scans, subscription mode…"
        onkeydown="hk(event)" oninput="rz(this)"></textarea>
    </div>
    <button class="run" id="run" onclick="go()">▶ Run</button>
  </div>
  <div class="hint">Ctrl+Enter · Saves final report to vault · Emails ahalaa@yahoo.com · Up to 3 concurrent</div>
</div>

<script>
/* ── Auth ──────────────────────────────────────────────────────────────────── */
const _cred=btoa('admin:admin');
const authHdr={'Authorization':'Basic '+_cred};
function afetch(url,opts={}){
  opts.headers=Object.assign({},opts.headers||{},authHdr);
  return fetch(url,opts);
}

/* ── State ─────────────────────────────────────────────────────────────────── */
const jobs = {};       // jobId → { id, name, prompt, status, stage, created, bufs, blocks, es }
let selectedJobId = null;

/* ── Helpers ───────────────────────────────────────────────────────────────── */
function rz(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,85)+'px'}
function hk(e){if(e.key==='Enter'&&e.ctrlKey){e.preventDefault();go()}}
function use(el){document.getElementById('prompt').value=el.textContent.trim();rz(document.getElementById('prompt'))}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function scr(){const m=document.getElementById('msgs');m.scrollTop=m.scrollHeight}
function timeAgo(ts){
  const sec=Math.floor(Date.now()/1000-ts);
  if(sec<60)return sec+'s';if(sec<3600)return Math.floor(sec/60)+'m';
  return Math.floor(sec/3600)+'h';
}
function countF(t){return(t.match(/FINDING #\d+/g)||[]).length}

/* ── Sidebar ───────────────────────────────────────────────────────────────── */
function updateSidebar(){
  const list=document.getElementById('joblist');
  const empty=document.getElementById('emptyJobs');
  const count=document.getElementById('jobCount');
  const sorted=Object.values(jobs).sort((a,b)=>b.created-a.created);
  const active=sorted.filter(j=>j.status==='queued'||j.status==='running').length;
  count.textContent=active>0?'('+active+' active)':'';

  if(sorted.length===0){
    empty.style.display='';list.querySelectorAll('.jcard').forEach(c=>c.remove());return;
  }
  empty.style.display='none';

  // Rebuild cards
  list.querySelectorAll('.jcard').forEach(c=>c.remove());
  sorted.forEach(j=>{
    const c=document.createElement('div');c.className='jcard'+(j.id===selectedJobId?' sel':'');
    c.onclick=()=>selectJob(j.id);
    const stLabel=j.stage==='complete'?'Complete':j.stage==='queued'?'Queued':
      j.stage.charAt(0).toUpperCase()+j.stage.slice(1);
    c.innerHTML=`<div class="jcard-top"><span class="jdot ${j.status}"></span>`+
      `<span class="jname">${esc(j.name)}</span>`+
      `<span class="jtime">${timeAgo(j.created)}</span></div>`+
      `<div class="jstage">${stLabel}</div>`;
    list.appendChild(c);
  });
}

/* ── Header pills ──────────────────────────────────────────────────────────── */
function updatePills(){
  const order=['queued','generator','auditor','resolver','email','complete'];
  const job=selectedJobId?jobs[selectedJobId]:null;
  ['generator','auditor','resolver'].forEach((s,i)=>{
    const pill=document.getElementById('p'+(i+1));if(!pill)return;
    if(!job){pill.className='pill';return}
    const ji=order.indexOf(job.stage);const si=order.indexOf(s);
    if(ji>si)pill.className='pill ok';
    else if(ji===si&&(job.status==='running'))pill.className='pill on';
    else pill.className='pill';
  });
}

/* ── Job view management ───────────────────────────────────────────────────── */
function createJobView(jobId,name,prompt){
  const msgs=document.getElementById('msgs');
  const intro=document.getElementById('intro');if(intro)intro.style.display='none';

  const view=document.createElement('div');view.id='jv-'+jobId;view.className='job-view';
  view.style.display='none';

  // User prompt bubble
  const msg=document.createElement('div');msg.className='msg you';
  msg.innerHTML=`<div class="lbl">You</div><div class="bbl">${esc(prompt)}</div>`;
  view.appendChild(msg);

  // Pipeline widget container
  const pw=document.createElement('div');pw.className='msg ai';pw.style.width='100%';
  const lbl=document.createElement('div');lbl.className='lbl';lbl.textContent='Pipeline';
  const ctr=document.createElement('div');ctr.className='pw';ctr.id='pw-'+jobId;
  pw.appendChild(lbl);pw.appendChild(ctr);
  view.appendChild(pw);

  msgs.appendChild(view);
  return ctr;
}

function selectJob(jobId){
  // Hide all views
  document.querySelectorAll('.job-view').forEach(v=>v.style.display='none');
  const intro=document.getElementById('intro');

  let view=document.getElementById('jv-'+jobId);
  if(!view){
    const job=jobs[jobId];if(!job)return;
    if(intro)intro.style.display='none';
    const ctr=createJobView(jobId,job.name,job.prompt||'(loaded from server)');
    job.container=ctr;
    view=document.getElementById('jv-'+jobId);
    // If running, connect SSE for replay + live
    if((job.status==='queued'||job.status==='running')&&!job.es){connectSSE(jobId)}
  }

  if(view)view.style.display='';
  if(!view&&intro)intro.style.display='';
  selectedJobId=jobId;
  updateSidebar();updatePills();scr();
}

/* ── Pipeline blocks ───────────────────────────────────────────────────────── */
function mkBlock(container,stage,jobId){
  const icon={generator:'\u{1F535}',auditor:'\u{1F534}',resolver:'\u{1F7E2}'}[stage];
  const name={generator:'Claude Code \u2014 Generator (Subscription)',
    auditor:'Gemini CLI \u2014 Auditor (Google Login)',
    resolver:'Claude Code \u2014 Resolver (Subscription)'}[stage];
  const cls={generator:'gen',auditor:'aud',resolver:'res'}[stage];
  const b=document.createElement('div');b.className='pblock';
  const ph=document.createElement('div');ph.className='ph '+cls;
  ph.innerHTML=`<span>${icon}</span><span class="ph-name">${name}</span>`+
    `<span class="ph-stat" id="ps-${jobId}-${stage}">Running\u2026</span>`+
    `<span class="tog open" id="tg-${jobId}-${stage}">\u25BC</span>`;
  const pb=document.createElement('div');pb.className='pb show';pb.id=`pb-${jobId}-${stage}`;
  ph.onclick=()=>{pb.classList.toggle('show');document.getElementById(`tg-${jobId}-${stage}`).classList.toggle('open')};
  b.appendChild(ph);b.appendChild(pb);container.appendChild(b);return pb;
}

function addChunk(jobId,stage,chunk){
  const pb=document.getElementById(`pb-${jobId}-${stage}`);if(!pb)return;
  const c=pb.querySelector('.cur');if(c)c.remove();
  const job=jobs[jobId];job.bufs[stage]=(job.bufs[stage]||'')+chunk;
  pb.textContent=job.bufs[stage];
  const cur=document.createElement('span');cur.className='cur';pb.appendChild(cur);
  pb.scrollTop=pb.scrollHeight;if(selectedJobId===jobId)scr();
}

function donePB(jobId,stage,statHtml){
  const pb=document.getElementById(`pb-${jobId}-${stage}`);
  if(pb){const c=pb.querySelector('.cur');if(c)c.remove()}
  const ps=document.getElementById(`ps-${jobId}-${stage}`);if(ps)ps.innerHTML=statHtml;
  if(stage!=='resolver'){
    setTimeout(()=>{
      const pb2=document.getElementById(`pb-${jobId}-${stage}`);
      const tg=document.getElementById(`tg-${jobId}-${stage}`);
      if(pb2)pb2.classList.remove('show');if(tg)tg.classList.remove('open');
    },1800);
  }
}

/* ── SSE event handler ─────────────────────────────────────────────────────── */
function handleEvent(jobId,ev){
  const job=jobs[jobId];if(!job)return;
  const{stage,status,message,chunk}=ev;

  // Update job state
  if(stage==='complete'){job.status='done';job.stage='complete'}
  else if(stage==='error'){job.status='error'}
  else if(['generator','auditor','resolver'].includes(stage)){
    if(status==='running'||status==='streaming'){job.status='running';job.stage=stage}
    if(status==='done'){
      if(stage==='generator')job.stage='auditor';
      else if(stage==='auditor')job.stage='resolver';
      else if(stage==='resolver')job.stage='email';
    }
  }
  else if(stage==='email'){job.stage='email'}

  // Get or create container
  const ctr=document.getElementById('pw-'+jobId);
  if(!ctr)return;

  // Pipeline stage blocks
  if(['generator','auditor','resolver'].includes(stage)){
    if((status==='running'||status==='streaming')&&!job.blocks[stage]){
      job.blocks[stage]=mkBlock(ctr,stage,jobId);
    }
    if(chunk&&job.blocks[stage])addChunk(jobId,stage,chunk);

    // ── MCP Tool Grid: visual parallel tracker ──
    if(status==='running'&&message){
      const pb=job.blocks[stage];
      const ps=document.getElementById(`ps-${jobId}-${stage}`);

      // "Firing N MCP tools in parallel…" → create grid
      if(message.match(/^Firing \d+ MCP tools/)){
        if(!job._tgrid){
          const gw=document.createElement('div');gw.id=`tg-wrap-${jobId}`;
          const lbl=document.createElement('div');lbl.className='tphase';
          lbl.textContent='\u26A1 PLANNING \u2192 '+message;
          const grid=document.createElement('div');grid.className='tgrid';grid.id=`tgrid-${jobId}`;
          gw.appendChild(lbl);gw.appendChild(grid);
          if(pb)pb.prepend(gw);
          job._tgrid={};job._tgridEl=grid;job._tgridLbl=lbl;job._tStart=Date.now();
        }
        if(ps)ps.textContent=message;
      }
      // "→ tool_name" → add pending chip
      else if(message.startsWith('\u2192 ')&&job._tgrid){
        const tname=message.slice(2);
        const chip=document.createElement('span');chip.className='tp running';
        chip.textContent=tname;chip.id=`tc-${jobId}-${tname.replace(/[^a-zA-Z0-9_]/g,'_')}`;
        job._tgridEl.appendChild(chip);
        job._tgrid[tname]='running';
        if(ps)ps.textContent=Object.keys(job._tgrid).length+' tools running\u2026';
      }
      // "✓ tool_name (N chars)" → mark done
      else if(message.startsWith('\u2713 ')&&job._tgrid){
        const m2=message.match(/\u2713 ([^ ]+)/);
        if(m2){
          const tname=m2[1];
          const cid=`tc-${jobId}-${tname.replace(/[^a-zA-Z0-9_]/g,'_')}`;
          const chip=document.getElementById(cid);
          if(chip){chip.className='tp done';chip.textContent=message.slice(2)}
          job._tgrid[tname]='done';
          const total=Object.keys(job._tgrid).length;
          const done=Object.values(job._tgrid).filter(v=>v==='done').length;
          if(ps)ps.textContent=done+'/'+total+' tools complete';
        }
      }
      // "✗ tool_name: error" → mark error
      else if(message.startsWith('\u2717 ')&&job._tgrid){
        const m2=message.match(/\u2717 ([^:]+)/);
        if(m2){
          const tname=m2[1];
          const cid=`tc-${jobId}-${tname.replace(/[^a-zA-Z0-9_]/g,'_')}`;
          const chip=document.getElementById(cid);
          if(chip){chip.className='tp error';chip.textContent=message.slice(2)}
          job._tgrid[tname]='error';
        }
      }
      // "All N tools complete" → compile phase
      else if(message.match(/^All \d+ tools complete/)&&job._tgrid){
        const elapsed=((Date.now()-job._tStart)/1000).toFixed(1);
        const total=Object.keys(job._tgrid).length;
        const done=Object.values(job._tgrid).filter(v=>v==='done').length;
        job._tgridLbl.className='tphase compile';
        job._tgridLbl.textContent='\u2705 COMPILED '+done+'/'+total+' tools in '+elapsed+'s \u2192 writing report';
        if(ps)ps.textContent=done+'/'+total+' tools \u2192 Claude writing report\u2026';
        const sum=document.createElement('div');sum.className='tsummary';
        sum.textContent='Data compiled: '+done+'/'+total+' tools in '+elapsed+'s';
        job._tgridEl.parentElement.appendChild(sum);
      }
      // Regular messages (heartbeats, Claude thinking, etc)
      else if(!job._tgrid){
        if(ps)ps.textContent=message;
      }
      // Status updates during Claude writing (headings, progress, heartbeats)
      else if(message.match(/^Waiting for Claude|^Claude thinking|^Writing|^Calling /)){
        if(ps)ps.textContent=message;
      }
    }
    if(status==='done'){
      if(stage==='auditor'){
        const n=countF(job.bufs.auditor||'');
        donePB(jobId,stage,`\u2713 Done<span class="bdg ${n?'warn':'good'}">${n?n+' finding'+(n>1?'s':''):'\u2713 Clean'}</span>`);
      }else{donePB(jobId,stage,'\u2713 Done')}
    }
  }

  // Email
  if(stage==='email'&&status==='done'){
    const em=document.createElement('div');em.className='emailed';
    em.textContent=message.includes('SENT')?'\u2709 Sent \u2192 ahalaa@yahoo.com':'\u2709 '+message;
    ctr.appendChild(em);
  }

  // Complete
  if(stage==='complete'){
    const n=Object.values(ev.files||{}).filter(v=>!String(v).startsWith('E')).length;
    const sv=document.createElement('div');sv.className='saved';
    sv.textContent='\u2B21 Report saved to vault';
    ctr.appendChild(sv);
    // Close EventSource
    if(job.es){job.es.close();job.es=null}
  }

  // Error
  if(stage==='error'){
    const view=document.getElementById('jv-'+jobId);
    if(view){
      const err=document.createElement('div');err.className='msg ai';
      err.innerHTML=`<div class="lbl">Error</div><div class="bbl"><span style="color:var(--claude)">${esc(message)}</span></div>`;
      view.appendChild(err);
    }
    if(job.es){job.es.close();job.es=null}
  }

  updateSidebar();updatePills();
  if(selectedJobId===jobId)scr();
}

/* ── SSE connection with polling fallback ──────────────────────────────────── */
let _sseN=0;
const _dbg=()=>document.getElementById('dbg');
function connectSSE(jobId){
  _sseN=0;
  const job=jobs[jobId];if(!job)return;
  // Don't reconnect to finished jobs
  if(job.status==='done'||job.status==='error')return;
  // Close existing connection if any
  if(job.es){job.es.close();job.es=null}

  const url='/jobs/'+jobId+'/stream?token='+encodeURIComponent(_cred);
  if(_dbg())_dbg().textContent='SSE: connecting…';
  const es=new EventSource(url);
  job.es=es;
  job._sseDrops=(job._sseDrops||0);
  job._lastOpen=0;
  es.onopen=()=>{
    const now=Date.now();
    if(job._lastOpen&&(now-job._lastOpen)<10000)job._sseDrops++;
    else job._sseDrops=0;
    job._lastOpen=now;
    if(_dbg())_dbg().textContent='SSE: CONNECTED (drops='+job._sseDrops+')';
  };
  es.onmessage=(e)=>{
    _sseN++;
    let ev;try{ev=JSON.parse(e.data)}catch(err){if(_dbg())_dbg().textContent='SSE: parse error';return}
    if(_dbg())_dbg().textContent='SSE: #'+_sseN+' '+ev.stage+' '+ev.status+' '+(ev.message||'').slice(0,40);
    handleEvent(jobId,ev);
  };
  es.onerror=(e)=>{
    if(_dbg())_dbg().textContent='SSE: error (drops='+job._sseDrops+', n='+_sseN+')';
    if(job.status==='done'||job.status==='error'){
      es.close();job.es=null;
      if(_dbg())_dbg().textContent='SSE: closed (job '+job.status+')';
      return;
    }
    if(job._sseDrops>=3&&!job._polling){
      es.close();job.es=null;
      if(_dbg())_dbg().textContent='SSE drops 3x → polling';
      startPolling(jobId);
    }
  };
}

function startPolling(jobId){
  const job=jobs[jobId];if(!job||job._polling)return;
  job._polling=true;
  if(_dbg())_dbg().textContent='POLL: active for '+jobId.slice(0,8);
  const poll=async()=>{
    if(job.status==='done'||job.status==='error'){job._polling=false;return}
    try{
      const r=await afetch('/jobs/'+jobId);
      if(r.ok){
        const sj=await r.json();
        const oldStage=job.stage;
        job.status=sj.status;job.stage=sj.stage;
        if(_dbg())_dbg().textContent='POLL: '+sj.stage+' '+sj.status;
        // Create view if needed
        if(!document.getElementById('jv-'+jobId)){
          const ctr=createJobView(jobId,job.name,job.prompt||'(loaded)');
          job.container=ctr;selectJob(jobId);
        }
        // Create stage blocks for running stages
        const ctr=document.getElementById('pw-'+jobId);
        if(ctr&&['generator','auditor','resolver'].includes(sj.stage)){
          if(!job.blocks[sj.stage])job.blocks[sj.stage]=mkBlock(ctr,sj.stage,jobId);
          const ps=document.getElementById('ps-'+jobId+'-'+sj.stage);
          if(ps)ps.textContent=sj.status==='running'?'Running…':'Done';
        }
        if(sj.status==='done'){
          if(ctr){
            const sv=document.createElement('div');sv.className='saved';
            sv.textContent='\u2B21 Report saved to vault';ctr.appendChild(sv);
          }
          job._polling=false;
        }else if(sj.status==='error'){
          job._polling=false;
        }
        updateSidebar();updatePills();
      }
    }catch{}
    if(job._polling)setTimeout(poll,5000);
  };
  poll();
}

/* ── Submit ────────────────────────────────────────────────────────────────── */
async function go(){
  const promptEl=document.getElementById('prompt');
  const nameEl=document.getElementById('rname');
  const prompt=promptEl.value.trim();
  const name=nameEl.value.trim()||'ANALYSIS';
  if(!prompt)return;

  promptEl.value='';promptEl.style.height='auto';

  try{
    const r=await afetch('/analyze',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({prompt,name})});

    if(r.status===429){const j=await r.json();alert(j.error);return}
    if(!r.ok){const j=await r.json().catch(()=>({}));alert(j.error||'Request failed');return}

    const data=await r.json();
    const jobId=data.job_id;

    // Create client-side job
    jobs[jobId]={
      id:jobId,name:data.name,prompt,
      status:'queued',stage:'queued',created:Date.now()/1000,
      bufs:{generator:'',auditor:'',resolver:''},
      blocks:{},es:null
    };

    // Create DOM
    const ctr=createJobView(jobId,data.name,prompt);
    jobs[jobId].container=ctr;

    // Select and connect
    selectJob(jobId);
    connectSSE(jobId);

  }catch(e){alert('Connection failed: '+e.message)}
}

/* ── Load existing jobs from server ────────────────────────────────────────── */
async function loadJobs(){
  try{
    const r=await afetch('/jobs');
    if(!r.ok)return;
    const{jobs:serverJobs}=await r.json();
    serverJobs.forEach(sj=>{
      if(jobs[sj.id]){
        jobs[sj.id].status=sj.status;
        jobs[sj.id].stage=sj.stage;
      }else{
        jobs[sj.id]={
          id:sj.id,name:sj.name,prompt:'',
          status:sj.status,stage:sj.stage,created:sj.created,
          bufs:{generator:'',auditor:'',resolver:''},
          blocks:{},es:null
        };
        // Auto-connect SSE for running jobs (reconnect after page refresh / tunnel drop)
        if(sj.status==='queued'||sj.status==='running'){
          connectSSE(sj.id);
          if(!selectedJobId)selectJob(sj.id);
        }
      }
    });
    updateSidebar();
  }catch{}
}

// Initial load + periodic refresh
loadJobs();
setInterval(()=>{loadJobs();updateSidebar()},15000);
</script>
</body>
</html>"""


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"""
╔════════════════════════════════════════════════════════════╗
║     Ahmed's Analyst — Multi-Session Async Pipeline         ║
╠════════════════════════════════════════════════════════════╣
║  AUTH:  {AUTH_USER} / {AUTH_PASS} (HTTP Basic Auth)                     ║
║  MODE:  SUBSCRIPTION — Zero API credits consumed           ║
║  JOBS:  Up to 3 concurrent scans                           ║
╠════════════════════════════════════════════════════════════╣
║  ①  Claude Code  (Generator, subscription + MCP tools)    ║
║  ②  Gemini CLI   (Adversarial audit, Google login)        ║
║  ③  Claude Code  (Resolver, subscription)                 ║
║  ⬡   Vault  →  {str(VAULT):<42}║
║  ✉   Email  →  {EMAIL_TO:<42}║
╠════════════════════════════════════════════════════════════╣
║  Open: http://localhost:{PORT}                                ║
╚════════════════════════════════════════════════════════════╝
Ctrl+C to stop
""")
    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
