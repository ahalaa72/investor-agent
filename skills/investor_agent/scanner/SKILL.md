---
name: scanner
description: Market opportunity discovery. TWO MODES - ROLE 1 (market scan = list top candidates) and ROLE 2 (ticker scan = full deep analysis with 6 sections A-F + Obsidian vault save). Always follow SCANNER_INSTRUCTIONS.md and SCANNER_REPORT_GENERATOR.md.
---

# Scanner - Market Opportunity Discovery

## AUTHORITATIVE REFERENCES (MUST FOLLOW)

1. **Instructions:** `reportsGenerator/SCANNER_INSTRUCTIONS.md` — Complete workflow, tools, gates, signal classification
2. **Report Template:** `reportsGenerator/SCANNER_REPORT_GENERATOR.md` — Full report format with 6 sections per stock

**These files define ALL scanner behavior. Read and follow them exactly.**

---

## TWO OPERATING MODES

| Mode | Trigger | Action |
|------|---------|--------|
| **ROLE 1: Market Scan** | "scan the market", "find opportunities" (no specific ticker) | List Top 5 LONG + Top 5 SHORT, then STOP |
| **ROLE 2: Ticker Scan** | "scan WMT", "scan AAPL" (specific ticker named) | Full deep analysis: ALL 6 sections (A-F) + save to Obsidian vault |

**If user names a specific ticker, that is ALWAYS ROLE 2.**

---

## Questrade Token Protection

**NEVER write Python scripts to scan or get quotes** — use MCP tools only.

---

## ROLE 1: Market Scan (List Mode)

Follow `SCANNER_INSTRUCTIONS.md` ROLE 1 section:

1. **Cache-First:** `get_best_cached_trades()` → show immediately
2. **Fetch Raw:** `get_raw_scan_candidates()` for LONG and/or SHORT
3. **Filter:** Remove cached tickers
4. **Validate:** Parallel single-stock MCP calls (5 per wave)
5. **Store (MANDATORY):** 3+ gate passes → `store_trading_prediction()` immediately
6. **Present:** Summary table, then STOP

## ROLE 2: Ticker Scan (Full Deep Analysis)

Follow `SCANNER_INSTRUCTIONS.md` ROLE 2 section + `SCANNER_REPORT_GENERATOR.md` template:

1. **Gather ALL data:** Run every tool listed in ROLE 2 Step 1 (Phase 0 + Sections A-F)
2. **Generate full report:** ALL 6 sections per SCANNER_REPORT_GENERATOR.md template
3. **Save to Obsidian vault:** `/Users/AhmedE/Ahmed/Trading Reports/TICKER_SCAN_YYYY-MM-DD.md`
4. **Store in DB:** `store_trading_prediction()` if 3+ gates pass

### ROLE 2 Required Tools (ALL must be called)

```
Phase 0: get_questrade_quotes(symbols=[ticker])
Sec A:   get_ticker_data(ticker), calculate_quality_score(ticker)
Sec B:   detect_catalyst_strength(ticker), get_earnings_history(ticker),
         detect_insider_cluster(ticker), get_institutional_holders(ticker)
Sec C:   analyze_options_mcmillan(ticker), detect_unusual_options_activity(ticker)
Sec D:   analyze_technical(ticker), calculate_relative_strength_tool(ticker),
         analyze_volume_tool(ticker), analyze_competitors(ticker)
Sec E:   (uses dalio_metrics from analyze_volume_tool)
Sec F:   generate_trading_signal(ticker, direction, account_size=10000)
```

### ROLE 2 Report Sections (ALL required)

- **Section A:** Company Overview + Quality Score
- **Section B:** Catalyst Verification (MANDATORY — NO CATALYST = NO TRADE)
- **Section C:** McMillan Options Strategy + Smart Money
- **Section D:** Al Brooks Price Action (CENTRAL)
- **Section E:** Dalio Economic Machine
- **Section F:** Trading Signal + 5-Gate Validation + Trading Plan

---

## MANDATORY: DB Storage

**Every ticker passing 3+ gates MUST be stored via `store_trading_prediction()` immediately.**

- If `status: "error"` returned, **report the error to user** (never silently swallow)
- If multiple stores fail, warn user about MSSQL status
- Failed stores do NOT stop the scan

---

## Post-Entry Management

| Position Type | Use Skill |
|--------------|-----------|
| Stock | Portfolio (4-gate validation) |
| Options | Position (5-rule management) |
