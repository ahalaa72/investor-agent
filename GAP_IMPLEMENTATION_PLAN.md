# Pipeline Gap Analysis & Implementation Plan

**Date:** 2026-03-03
**Status:** Implementation in Progress
**File:** `analyst_server.py`

---

## Architecture Overview

```
Current Pipeline (3 stages):

  [User Request]
       │
       ▼
  ┌─────────────────────┐
  │ REQUEST CLASSIFIER   │  _classify_request() → type + tickers
  │ TOOL SELECTOR        │  _build_tool_list() → 9-16 MCP tools
  └──────────┬──────────┘
             ▼
  ┌─────────────────────┐
  │ MCP DATA GATHERING   │  gather_mcp_data() → parallel docker exec
  │ (11 tools for ticker │  Token warmup → parallel batch
  │  analysis currently) │  _mcp_lock serializes across jobs
  └──────────┬──────────┘
             │
             ├── mcp_text (50-100KB full JSON)    → Generator only
             ├── mcp_compact (2-4KB key numbers)  → Auditor + Resolver
             ▼
  ┌─────────────────────┐
  │ STAGE 1: GENERATOR   │  Claude CLI + MCP data injected
  │ (Claude, no MCP)     │  Writes draft report (~20-40KB)
  └──────────┬──────────┘
             ▼
  ┌─────────────────────┐
  │ STAGE 2: AUDITOR     │  Gemini CLI + compact MCP ref
  │ (Gemini, web only)   │  Finds errors (8-15 findings typical)
  └──────────┬──────────┘
             ▼
  ┌─────────────────────┐
  │ STAGE 3: RESOLVER    │  Claude CLI + compact MCP ref
  │ (Claude, no MCP)     │  Resolves findings → FINAL report
  └──────────┬──────────┘
             ▼
  ┌─────────────────────┐
  │ VAULT + EMAIL        │  Save .md → /Users/AhmedE/Ahmed/Trading Reports/
  │                      │  Email via Gmail SMTP
  └─────────────────────┘
```

---

## Gap #1: Only 11 of 73 MCP Tools Used

### Problem
`_build_tool_list()` for `ticker_analysis` uses 9 unique tools + 7 position queries = 16 calls.
But 8 high-value tools are completely unused:

| Tool | What It Provides | Why It Matters |
|------|-----------------|----------------|
| `analyze_volume_tool` | Volume profile, accumulation/distribution, VWAP analysis | Confirms conviction — high volume at breakout = real move |
| `analyze_volatility_tool` | HV vs IV, volatility regime, Bollinger squeeze | Essential for options strategy selection |
| `find_similar_historical_setups` | Pattern matching against historical data | ML-backed probability, not just Brooks intuition |
| `analyze_iv_skew` | Put/call IV skew, tail risk pricing | Reveals institutional hedging activity |
| `calculate_relative_strength_tool` | Sector-relative performance, RS ranking | Is the stock leading or lagging its sector? |
| `detect_insider_cluster` | Clustered insider buys/sells with timing | Strongest signal — insiders know their company |
| `detect_unusual_options_activity` | Smart money flow, unusual volume/OI | Front-running institutional positioning |
| `get_questrade_candles` | Intraday price action, candle patterns | Al Brooks analysis needs actual candles |

### Implementation
**File:** `analyst_server.py` line ~419 (`_build_tool_list`)
**Change:** Add 8 new tools to `ticker_analysis` tool list.
**Risk:** More MCP calls = longer gather time. Mitigate: all run in parallel after warmup.
**Test:** Run `scan AAPL`, verify all 8 new tools appear in logs with data.

---

## Gap #2: Auditor Has No MCP Verification Access

### Problem
Auditor (Gemini) receives only `mcp_compact` (2-4KB). It can web search for external facts but **cannot independently verify MCP-sourced numbers**. If Generator says "RSI = 72" but actual RSI = 52, Auditor has no way to catch it.

### Implementation
**File:** `analyst_server.py` line ~1581
**Change:** Before calling Auditor, run a **verification subset** of MCP tools (quotes, technical, quality_score — 3 tools). Include this fresh data alongside the compact summary so Gemini can cross-check.
**Risk:** Extra 30-60s for 3 MCP calls. Worth it for accuracy.
**Test:** Intentionally check that Auditor findings reference MCP verification data.

---

## Gap #3: Lossy Compact Summary (3% of original data)

### Problem
`_compact_mcp_summary()` crushes 50-100KB → 2-4KB. Auditor and Resolver work with ~3% of original data. Key details lost: full order book, volume profile, earnings history patterns, institutional holder changes.

### Implementation
**File:** `analyst_server.py` line ~597
**Change:** Create `_rich_mcp_summary()` that produces 15-20KB (vs 2-4KB compact). Include:
- Full technical indicators (not just RSI/MACD summary)
- All support/resistance levels with volume confirmation
- Options chain data (top 5 strikes by OI)
- Earnings history (last 4 quarters with surprise %)
- Insider transactions (last 6 months)
- Volume analysis details

Pass rich summary to Auditor/Resolver instead of compact.
**Risk:** Larger prompt = more tokens. Gemini 1.5 handles this easily.
**Test:** Compare compact vs rich summary size. Verify Auditor can reference specific details.

---

## Gap #4: No Quality Gate Before Email

### Problem
No automated check on output quality. A report with 3 "UNKNOWN" fields, missing options section, and stale prices gets emailed identically to a perfect report. No way to distinguish bad reports from good ones.

### Implementation
**File:** `analyst_server.py` after line ~1614 (post-process)
**Change:** Add `_score_report(text)` function that returns a quality score (0-100) based on:
- All table cells filled (no UNKNOWN, N/A, TBD) — 20 pts
- Price data present with $ amounts — 15 pts
- At least 4/5 gates have definitive PASS/FAIL — 15 pts
- Support/resistance levels are numeric — 10 pts
- Options section has real data or explicit SKIP reason — 10 pts
- Has RESOLUTION_LOG, FINAL_REPORT, CONFIDENCE_SUMMARY sections — 15 pts
- Report length > 5000 chars — 10 pts
- Has HUMAN_REVIEW_REQUIRED section — 5 pts

Score < 60 → mark email subject as "[LOW QUALITY]" and log warning.
Score < 40 → skip email, save draft only, alert user.
**Test:** Create test strings with known deficiencies, verify scores match expectations.

---

## Gap #5: No Re-Query After Audit Findings

### Problem
Auditor finds errors → Resolver patches text. But Resolver has no fresh data to verify corrections. It's editing prose, not fixing analysis. If Auditor says "RSI is wrong", Resolver guesses instead of re-querying.

### Implementation
**File:** `analyst_server.py` line ~1594 (between Auditor and Resolver)
**Change:** After Auditor produces findings, parse `FINDING #N` entries. For each finding with ERROR_TYPE in {Math, Options_Mechanics, Contradiction}:
- Extract the relevant ticker
- Run targeted MCP calls: `get_questrade_quotes`, `analyze_technical` (lightweight)
- Include fresh data in Resolver prompt as "VERIFICATION DATA FOR DISPUTED FINDINGS"

**Risk:** Extra MCP calls. Limit to max 3 re-query tools, only when audit has 3+ high-confidence findings.
**Test:** Submit a scan, verify re-query tools fire when audit has numerical disputes.

---

## Gap #6: No Prediction Tracking

### Problem
Reports make predictions (entry/stop/target) but there's no tracking. Already have `store_trading_prediction` and `update_prediction_outcomes` MCP tools but they're unused.

### Implementation
**File:** `analyst_server.py` after vault save (line ~1638)
**Change:** After saving FINAL report:
1. Extract entry_price, stop_loss, target_1, target_2 from report text
2. Call `store_trading_prediction` MCP tool with extracted data
3. Log prediction_id for tracking

**Separate daily job (future):** Call `update_prediction_outcomes` for open predictions.
**Test:** Run scan, verify `store_trading_prediction` is called and returns prediction_id.

---

## Gap #7: No Checkpointing / Resume

### Problem
Pipeline crash at Stage 2 loses all Stage 1 work. Must restart from scratch, wasting 5-10 minutes of MCP gathering + Claude generation.

### Implementation
**File:** `analyst_server.py` in `pipeline()` function
**Change:** Save intermediate artifacts to VAULT:
- `{job_id}_mcp_raw.json` — after MCP gathering
- `{job_id}_draft.md` — after Generator
- `{job_id}_audit.md` — after Auditor

On job start, check for existing checkpoint files. If found, resume from last completed stage.
Add `GET /jobs/{id}/resume` endpoint to manually trigger resume.
**Test:** Kill pipeline mid-auditor, restart, verify it picks up from draft checkpoint.

---

## Implementation Order & Testing

### Phase 1: Data Quality (Gaps 1, 3)
1. Add 8 MCP tools to `_build_tool_list` → verify all fire in logs
2. Create `_rich_mcp_summary()` → verify output is 15-20KB

### Phase 2: Verification (Gaps 2, 5)
3. Add Auditor MCP verification pass → verify cross-check data in audit
4. Add re-query loop → verify fresh data used for disputed findings

### Phase 3: Quality & Tracking (Gaps 4, 6)
5. Add `_score_report()` quality gate → verify scoring against known inputs
6. Add prediction tracking → verify `store_trading_prediction` called

### Phase 4: Reliability (Gap 7)
7. Add checkpointing → verify resume works after simulated crash

### Evidence of Testing
Each implementation step will include:
- Console log output showing the change in action
- Before/after comparison (e.g., tool count, summary size, score)
- Error cases tested (missing data, empty responses, parse failures)
