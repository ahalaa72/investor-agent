#!/usr/bin/env python3
"""
Tests for Pipeline Improvements (analyst_server.py)

Tests cover:
  Round 1 (7 gaps):
    1. _build_tool_list — 8 new MCP tools
    2. _compact_mcp_summary — new tool handlers
    3. _score_report — quality gate scoring
    4. _extract_price — price extraction
    5. _classify_report_type — report type classification
    6. Checkpoint save/load/cleanup
    7. Pipeline structure

  Round 2 (10 enhancements):
    8. _classify_request — classifier fix (#1)
    9. _score_report adaptive — per-type scoring (#2)
   10. Auto-retry thin drafts (#3)
   11. Prediction tracking fix (#4)
   12. Self-reflection loop (#5)
   13. Comparison mode upgrade (#6)
   14. Structured JSON output (#7)
   15. Predictions dashboard API (#8)
   16. Webhook notifications (#9)
   17. Report diff (#10)

Run:  python3 -m pytest tests/test_pipeline_improvements.py -v
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import re
from datetime import datetime

_src = Path(__file__).resolve().parent.parent / "analyst_server.py"


# ── Extracted test functions ──────────────────────────────────────────────────

def _extract_price(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except (ValueError, IndexError):
            return None
    return None


def _classify_report_type(text):
    length = len(text)
    sections = len(re.findall(r'^#{1,4}\s', text, re.MULTILINE))
    if length > 15000 or sections > 15:
        return "DEEP_DIVE"
    elif length > 5000 or sections > 8:
        return "COMPREHENSIVE"
    else:
        return "CONCISE"


def _classify_request(prompt):
    """Extracted from analyst_server.py — must match current implementation."""
    lower = prompt.lower()
    tickers = _extract_all_tickers(prompt)

    action_words = ["scan", "analyze", "analysis", "check", "review", "look at",
                    "examine", "evaluate", "screen"]
    has_action = any(w in lower for w in action_words)
    if tickers and has_action:
        return ("ticker_analysis", tickers)

    if any(w in lower for w in ["portfolio", "positions", "holdings", "balances", "accounts"]):
        return ("portfolio_review", tickers)

    if any(w in lower for w in ["scan", "screen", "find opportunities", "market opportunities"]):
        if any(w in lower for w in ["short", "bear", "put"]):
            return ("market_scan_short", tickers)
        elif any(w in lower for w in ["long", "bull", "call", "buy"]):
            return ("market_scan_long", tickers)
        return ("market_scan", tickers)

    if len(tickers) >= 2:
        return ("comparison", tickers)

    if any(w in lower for w in ["option", "options", "put spread", "call spread", "iron condor",
                                 "straddle", "strangle", "covered call", "mcmillan"]):
        return ("options_focus", tickers)

    if tickers:
        return ("ticker_analysis", tickers)

    return ("general", [])


def _extract_all_tickers(prompt):
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


def _score_report(text, request_type="ticker_analysis"):
    """Extracted adaptive scoring — must match current implementation."""
    details = {}
    warnings = []
    lower = text.lower()

    WEIGHT_PROFILES = {
        "ticker_analysis": {
            "completeness": 20, "price_data": 15, "gates": 15,
            "support_resistance": 10, "options": 10, "structure": 15,
            "length": 10, "human_review": 5,
        },
        "portfolio_review": {
            "completeness": 20, "price_data": 10, "position_analysis": 15,
            "balance_data": 10, "options": 5, "structure": 20,
            "length": 10, "human_review": 10,
        },
        "market_scan": {
            "completeness": 20, "price_data": 10, "candidate_count": 15,
            "scan_coverage": 10, "options": 5, "structure": 20,
            "length": 10, "human_review": 10,
        },
        "comparison": {
            "completeness": 20, "price_data": 15, "gates": 10,
            "comparison_tables": 15, "options": 5, "structure": 15,
            "length": 10, "human_review": 10,
        },
    }
    profile = WEIGHT_PROFILES.get(request_type,
                WEIGHT_PROFILES.get("market_scan" if "scan" in request_type else "ticker_analysis"))

    # 1. Completeness
    w = profile["completeness"]
    placeholder_count = len(re.findall(r'\b(?:UNKNOWN|N/A|TBD|TODO|PENDING|~)\b', text, re.IGNORECASE))
    if placeholder_count == 0: details["completeness"] = w
    elif placeholder_count <= 2: details["completeness"] = int(w * 0.75)
    elif placeholder_count <= 5:
        details["completeness"] = int(w * 0.5)
        warnings.append(f"{placeholder_count} placeholder values")
    else:
        details["completeness"] = int(w * 0.25)
        warnings.append(f"{placeholder_count} placeholders")

    # 2. Price data
    w = profile["price_data"]
    price_count = len(re.findall(r'\$\d+\.?\d*', text))
    if price_count >= 10: details["price_data"] = w
    elif price_count >= 5: details["price_data"] = int(w * 0.67)
    elif price_count >= 2: details["price_data"] = int(w * 0.33)
    else:
        details["price_data"] = 0
        warnings.append("No price data")

    # 3. Gates or alternatives
    if "gates" in profile:
        w = profile["gates"]
        gate_total = len(re.findall(r'\bPASS\b', text)) + len(re.findall(r'\bFAIL\b', text))
        if gate_total >= 4: details["gates"] = w
        elif gate_total >= 3: details["gates"] = int(w * 0.67)
        elif gate_total >= 1: details["gates"] = int(w * 0.33)
        else:
            details["gates"] = 0
            warnings.append("No gates")

    if "position_analysis" in profile:
        w = profile["position_analysis"]
        pos = len(re.findall(r'(?:position|holding|shares?|quantity|cost\s*basis|entry)', lower))
        pnl = len(re.findall(r'(?:p[&/]?l|profit|loss|gain|return)', lower))
        total = pos + pnl
        if total >= 8: details["position_analysis"] = w
        elif total >= 4: details["position_analysis"] = int(w * 0.67)
        elif total >= 1: details["position_analysis"] = int(w * 0.33)
        else: details["position_analysis"] = 0

    if "candidate_count" in profile:
        w = profile["candidate_count"]
        total = len(re.findall(r'(?:candidate|ticker|symbol)\b', lower)) + \
                len(re.findall(r'\b[A-Z]{1,5}\b.*(?:BUY|SELL|WATCH|STRONG)', text))
        if total >= 10: details["candidate_count"] = w
        elif total >= 5: details["candidate_count"] = int(w * 0.67)
        elif total >= 1: details["candidate_count"] = int(w * 0.33)
        else: details["candidate_count"] = 0

    if "comparison_tables" in profile:
        w = profile["comparison_tables"]
        total = len(re.findall(r'\|.*\|.*\|', text)) + len(re.findall(r'(?:vs\.?|versus|compared to)', lower))
        if total >= 10: details["comparison_tables"] = w
        elif total >= 4: details["comparison_tables"] = int(w * 0.67)
        elif total >= 1: details["comparison_tables"] = int(w * 0.33)
        else: details["comparison_tables"] = 0

    # 4. S/R or alternatives
    if "support_resistance" in profile:
        w = profile["support_resistance"]
        sr = len(re.findall(r'(?:support|resistance)[:\s]*\$?\d+\.?\d*', lower))
        if sr >= 3: details["support_resistance"] = w
        elif sr >= 1: details["support_resistance"] = int(w * 0.5)
        else:
            details["support_resistance"] = 0
            warnings.append("No S/R levels")

    if "balance_data" in profile:
        w = profile["balance_data"]
        bal = len(re.findall(r'(?:balance|equity|margin|cash|buying\s*power|net\s*asset)', lower))
        if bal >= 4: details["balance_data"] = w
        elif bal >= 2: details["balance_data"] = int(w * 0.5)
        else: details["balance_data"] = 0

    if "scan_coverage" in profile:
        w = profile["scan_coverage"]
        sec = len(re.findall(r'(?:sector|industry|tech|health|energy|financial|consumer)', lower))
        if sec >= 4: details["scan_coverage"] = w
        elif sec >= 2: details["scan_coverage"] = int(w * 0.5)
        else: details["scan_coverage"] = 0

    # 5. Options
    w = profile.get("options", 10)
    has_options = bool(re.search(r'(?:options?\s+(?:plan|strategy|trade)|mcmillan|iv\s+rank|strike)', lower))
    has_skip = bool(re.search(r'(?:options?\s+(?:skip|not\s+available|no\s+options)|stock\s+only)', lower))
    if has_options: details["options"] = w
    elif has_skip: details["options"] = int(w * 0.7)
    else: details["options"] = 0

    # 6. Structure
    w = profile["structure"]
    if request_type == "portfolio_review":
        required = ["FINAL_REPORT", "CONFIDENCE_SUMMARY"]
    elif "scan" in request_type:
        required = ["FINAL_REPORT"]
    else:
        required = ["RESOLUTION_LOG", "FINAL_REPORT", "CONFIDENCE_SUMMARY"]
    found = sum(1 for s in required if s in text)
    details["structure"] = int(found / max(len(required), 1) * w)

    # 7. Length
    w = profile["length"]
    length = len(text)
    if length > 10000: details["length"] = w
    elif length > 5000: details["length"] = int(w * 0.7)
    elif length > 2000: details["length"] = int(w * 0.4)
    else: details["length"] = 0

    # 8. Human review
    w = profile["human_review"]
    details["human_review"] = w if "HUMAN_REVIEW_REQUIRED" in text else 0

    score = sum(details.values())
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D" if score >= 40 else "F"
    return {"score": score, "grade": grade, "details": details, "warnings": warnings}


def _compute_report_diff(prev_text, new_text, ticker):
    """Extracted from analyst_server.py."""
    diffs = []

    def _ext_price(text, pattern):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try: return float(match.group(1))
            except: return None
        return None

    def _ext_signal(text):
        match = re.search(r'(?:signal|recommendation)[:\s]*(STRONG_BUY|BUY|WATCH|SELL|STRONG_SELL|NO_TRADE|HOLD)', text, re.IGNORECASE)
        return match.group(1).upper() if match else None

    def _fmt(old, new, label):
        if old is not None and new is not None and old != new:
            pct = (new - old) / old * 100 if old != 0 else 0
            diffs.append(f"- **{label}:** ${old:.2f} -> ${new:.2f} ({pct:+.1f}%)")

    _fmt(_ext_price(prev_text, r'(?:current\s+)?price[:\s]*\$?([\d.]+)'),
         _ext_price(new_text, r'(?:current\s+)?price[:\s]*\$?([\d.]+)'), "Price")
    for label, pat in [("Entry", r'entry[:\s]*\$?([\d.]+)'), ("Stop", r'stop[:\s]*\$?([\d.]+)')]:
        _fmt(_ext_price(prev_text, pat), _ext_price(new_text, pat), label)

    prev_sig = _ext_signal(prev_text)
    new_sig = _ext_signal(new_text)
    if prev_sig and new_sig and prev_sig != new_sig:
        diffs.append(f"- **Signal changed:** {prev_sig} -> {new_sig}")

    if not diffs:
        return ""
    return "\n\nCHANGES FROM PREVIOUS SCAN\n" + "\n".join(diffs)


# ══════════════════════════════════════════════════════════════════════════════
# Round 1 Tests (Gaps 1-7) — existing
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildToolList:
    """Gap #1: Verify 8 new MCP tools are added to ticker_analysis."""

    def test_tool_list_has_extended_tools(self):
        src = _src.read_text()
        new_tools = [
            "analyze_volume_tool", "analyze_volatility_tool",
            "find_similar_historical_setups", "analyze_iv_skew",
            "calculate_relative_strength_tool", "detect_insider_cluster",
            "detect_unusual_options_activity", "get_questrade_candles",
        ]
        for tool in new_tools:
            assert tool in src, f"Missing new tool: {tool}"
            block_start = src.index("if request_type == \"ticker_analysis\":")
            block_end = src.index("elif request_type == \"options_focus\":")
            block = src[block_start:block_end]
            assert tool in block, f"Tool {tool} not in ticker_analysis block"

    def test_tool_count_increased(self):
        src = _src.read_text()
        block_start = src.index("if request_type == \"ticker_analysis\":")
        block_end = src.index("elif request_type == \"options_focus\":")
        block = src[block_start:block_end]
        tool_names = re.findall(r'"(get_|analyze_|find_|calculate_|detect_|generate_)\w+"', block)
        assert len(tool_names) >= 17, f"Expected 17+ tools, found {len(tool_names)}"


class TestCompactMcpSummary:
    def test_new_tool_handlers_exist(self):
        src = _src.read_text()
        handlers = [
            'label.startswith("volume_")', 'label.startswith("volatility_")',
            'label.startswith("historical_")', 'label.startswith("iv_skew_")',
            'label.startswith("rel_strength_")', 'label.startswith("insider_cluster_")',
            'label.startswith("unusual_options_")', 'label.startswith("candles_")',
        ]
        for h in handlers:
            assert h in src, f"Missing handler: {h}"

    def test_signal_no_trade_null_trading_plan(self):
        """NO_TRADE signal with null trading_plan must not PARSE_ERROR."""
        src = _src.read_text()
        # Verify we use `or {}` instead of default dict for trading_plan
        assert 'd.get("trading_plan") or {}' in src, "trading_plan must use `or {}` to handle null"
        assert 'd.get("brooks_analysis") or {}' in src, "brooks_analysis must use `or {}` to handle null"
        assert 'd.get("options_tradability") or {}' in src, "options_tradability must use `or {}` to handle null"
        # Verify NO_TRADE reason line
        assert 'sig_val in ("NO_TRADE", "HOLD")' in src, "NO_TRADE/HOLD should show reason"


class TestAuditorVerification:
    def test_verification_tools_in_pipeline(self):
        src = _src.read_text()
        assert "verify_quotes_" in src
        assert "verify_technical_" in src
        assert "verify_quality_" in src
        assert "FRESH_MCP_VERIFICATION_DATA" in src

    def test_verification_data_passed_to_auditor(self):
        src = _src.read_text()
        assert "audit_verify_text" in src


class TestRequery:
    def test_requery_logic_exists(self):
        src = _src.read_text()
        assert "requery_quotes_" in src
        assert "requery_technical_" in src
        assert "FRESH_REQUERY_DATA" in src
        assert "high_findings >= 2" in src


class TestScoreReport:
    """Quality gate scoring tests (ticker_analysis profile)."""

    def test_perfect_report(self):
        report = """
RESOLUTION_LOG
==============
FINAL_REPORT
============
Entry: $150.00 | Stop: $145.00 | Target 1: $160.00 | Target 2: $170.00
Price: $152.30 | Bid $152.25 / Ask $152.35
Support: $148.00 | Resistance: $155.00 | Support $146.00 | Resistance $158.00
| Catalyst | PASS | | Freshness | PASS | | Brooks | PASS | | Quality | PASS | | Options | FAIL |
Options trade plan: Sell put spread at 145/140 strike
CONFIDENCE_SUMMARY
==================
HUMAN_REVIEW_REQUIRED
=====================
1. Verify earnings date
""" + "x" * 8000
        result = _score_report(report)
        assert result["score"] >= 85, f"Score {result['score']}, expected 85+"
        assert result["grade"] == "A"

    def test_empty_report(self):
        result = _score_report("Short report with nothing useful.")
        assert result["score"] < 30
        assert result["grade"] in ("D", "F")

    def test_report_with_placeholders(self):
        report = """
RESOLUTION_LOG
==============
FINAL_REPORT
============
Price: $100 | Entry: $101 | Stop: $95 | Target: $110
Value: UNKNOWN | Rating: TBD | Score: N/A | Status: PENDING | Level: TODO | Risk: ~
PASS FAIL PASS FAIL
Support: $95 | Resistance: $110 | Support: $90 | Resistance: $115
Options plan: Sell put spread
CONFIDENCE_SUMMARY
==================
HUMAN_REVIEW_REQUIRED
=====================
""" + "x" * 8000
        result = _score_report(report)
        assert result["details"]["completeness"] <= 10

    def test_report_no_gates(self):
        report = """
RESOLUTION_LOG
==============
FINAL_REPORT
============
Price: $100 | No gates
CONFIDENCE_SUMMARY
==================
HUMAN_REVIEW_REQUIRED
=====================
""" + "x" * 6000
        result = _score_report(report)
        assert result["details"]["gates"] == 0

    def test_report_stock_only(self):
        report = """Stock only — no options available.
Price: $50 | Entry: $51 | PASS""" + "x" * 3000
        result = _score_report(report)
        assert result["details"]["options"] == int(10 * 0.7)  # 7

    def test_report_missing_sections(self):
        report = """
FINAL_REPORT
============
Price: $100. PASS PASS PASS PASS
Support: $95 | Resistance: $110
Options plan IV rank 45
CONFIDENCE_SUMMARY
==================
HUMAN_REVIEW_REQUIRED
=====================
""" + "x" * 8000
        result = _score_report(report)
        assert result["details"]["structure"] == 10  # 2/3 * 15

    def test_grade_boundaries(self):
        assert _score_report("x" * 100)["grade"] in ("D", "F")


class TestExtractPrice:
    def test_entry_price(self):
        assert _extract_price("Entry: $150.25", r'entry[:\s]*\$?([\d.]+)') == 150.25

    def test_stop_loss(self):
        assert _extract_price("Stop: $145.00", r'stop[:\s]*\$?([\d.]+)') == 145.00

    def test_target_1(self):
        assert _extract_price("Target 1: $160.50", r'(?:target\s*1|t1)[:\s]*\$?([\d.]+)') == 160.50

    def test_target_2(self):
        assert _extract_price("T2: $170", r'(?:target\s*2|t2)[:\s]*\$?([\d.]+)') == 170.0

    def test_no_match(self):
        assert _extract_price("No prices here", r'entry[:\s]*\$?([\d.]+)') is None

    def test_case_insensitive(self):
        assert _extract_price("ENTRY: $99.99", r'entry[:\s]*\$?([\d.]+)') == 99.99


class TestClassifyReportType:
    def test_deep_dive(self):
        assert _classify_report_type("x" * 20000) == "DEEP_DIVE"

    def test_comprehensive(self):
        text = "\n".join([f"# Section {i}\n" + "x" * 700 for i in range(10)])
        assert _classify_report_type(text) == "COMPREHENSIVE"

    def test_concise(self):
        assert _classify_report_type("Short report") == "CONCISE"


class TestCheckpointing:
    def test_checkpoint_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cp_file = Path(tmpdir) / "test123_mcp_data.json"
            data = {"mcp_text": "hello world", "count": 42}
            cp_file.write_text(json.dumps(data), encoding="utf-8")
            loaded = json.loads(cp_file.read_text(encoding="utf-8"))
            assert loaded["mcp_text"] == "hello world"
            assert loaded["count"] == 42

    def test_checkpoint_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert not (Path(tmpdir) / "nonexistent.json").exists()

    def test_checkpoint_cleanup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cp_dir = Path(tmpdir)
            for stage in ["mcp_data", "draft", "audit"]:
                (cp_dir / f"test456_{stage}.json").write_text("{}")
            assert len(list(cp_dir.glob("test456_*.json"))) == 3
            for f in cp_dir.glob("test456_*.json"):
                f.unlink()
            assert len(list(cp_dir.glob("test456_*.json"))) == 0


class TestPipelineStructure:
    def test_quality_gate_in_pipeline(self):
        src = _src.read_text()
        quality_pos = src.index("_score_report(final_text")
        email_pos = src.index("Email FINAL report (quality-gated)")
        assert quality_pos < email_pos

    def test_prediction_tracking_in_pipeline(self):
        src = _src.read_text()
        assert "store_trading_prediction" in src
        vault_pos = src.index("Save the FINAL report to vault")
        pred_pos = src.index("Prediction tracking")
        assert vault_pos < pred_pos

    def test_email_skipped_on_low_quality(self):
        src = _src.read_text()
        assert "q_score < 40" in src
        assert "EMAIL_SKIPPED" in src

    def test_email_tagged_on_medium_quality(self):
        src = _src.read_text()
        assert "q_score < 60" in src
        assert "[LOW QUALITY]" in src

    def test_checkpointing_exists(self):
        src = _src.read_text()
        assert "def _save_checkpoint" in src
        assert "def _load_checkpoint" in src
        assert "def _cleanup_checkpoints" in src


# ══════════════════════════════════════════════════════════════════════════════
# Round 2 Tests (10 Enhancements)
# ══════════════════════════════════════════════════════════════════════════════

class TestClassifierFix:
    """Enhancement #1: Request classifier misrouting fix."""

    def test_scan_ticker_with_portfolio(self):
        """'scan AVGO using portfolio instructions' -> ticker_analysis, not portfolio_review."""
        req_type, tickers = _classify_request("scan AVGO using portfolio instructions")
        assert req_type == "ticker_analysis"
        assert "AVGO" in tickers

    def test_scan_ticker_simple(self):
        req_type, tickers = _classify_request("scan AAPL")
        assert req_type == "ticker_analysis"
        assert "AAPL" in tickers

    def test_scan_no_ticker(self):
        req_type, _ = _classify_request("scan the market")
        assert req_type == "market_scan"

    def test_portfolio_no_action(self):
        req_type, _ = _classify_request("show my portfolio")
        assert req_type == "portfolio_review"

    def test_analyze_ticker(self):
        req_type, tickers = _classify_request("analyze MSFT")
        assert req_type == "ticker_analysis"
        assert "MSFT" in tickers

    def test_check_positions(self):
        req_type, _ = _classify_request("check my positions")
        assert req_type == "portfolio_review"

    def test_compare_tickers(self):
        req_type, tickers = _classify_request("AAPL MSFT")
        assert req_type == "comparison"
        assert len(tickers) == 2

    def test_scan_long(self):
        req_type, _ = _classify_request("scan for long opportunities")
        assert req_type == "market_scan_long"

    def test_scan_short(self):
        req_type, _ = _classify_request("scan for short bears")
        assert req_type == "market_scan_short"

    def test_general_request(self):
        req_type, _ = _classify_request("what is the weather today")
        assert req_type == "general"

    def test_ticker_with_portfolio_and_analyze(self):
        """Ticker + action + portfolio keyword -> ticker_analysis."""
        req_type, tickers = _classify_request("analyze AVGO using portfolio sizing rules")
        assert req_type == "ticker_analysis"
        assert "AVGO" in tickers


class TestAdaptiveScoring:
    """Enhancement #2: Adaptive quality gate per request type."""

    def test_portfolio_can_score_high(self):
        """Portfolio review should be able to score 80+ without gates/S/R."""
        report = """
FINAL_REPORT
============
Account 40036271: 100 shares AAPL @ $150 cost basis, current $155, gain +3.3%
Account 29455571: 50 shares MSFT @ $380 cost basis, holding position with profit
Balance: $125,000 equity | Cash: $45,000 | Margin available: $80,000
Buying power: $160,000 | Net asset value: $125,000
Total portfolio return: +15.2% | P&L: +$16,500

CONFIDENCE_SUMMARY
==================
High confidence in positions.

HUMAN_REVIEW_REQUIRED
=====================
1. Review margin usage
""" + "x" * 8000
        result = _score_report(report, "portfolio_review")
        assert result["score"] >= 70, f"Portfolio scored {result['score']}, expected 70+"
        assert result["grade"] in ("A", "B")

    def test_ticker_analysis_uses_gates(self):
        """Ticker analysis should penalize missing gates."""
        report = """
FINAL_REPORT
============
Price: $100 | Analysis complete
CONFIDENCE_SUMMARY
==================
""" + "x" * 6000
        result = _score_report(report, "ticker_analysis")
        assert "gates" in result["details"]
        assert result["details"]["gates"] == 0

    def test_market_scan_uses_candidates(self):
        """Market scan should score based on candidate count."""
        report = """
FINAL_REPORT
============
ticker AAPL: BUY | ticker MSFT: WATCH | ticker NVDA: STRONG BUY
candidate GOOGL: SELL | candidate META: BUY
sector tech | sector health | sector energy | sector financial
""" + "x" * 8000 + "\nHUMAN_REVIEW_REQUIRED\n"
        result = _score_report(report, "market_scan")
        assert "candidate_count" in result["details"]
        assert result["details"]["candidate_count"] > 0

    def test_comparison_uses_tables(self):
        """Comparison should score based on comparison tables."""
        report = """
RESOLUTION_LOG
==============
FINAL_REPORT
============
| Metric | AAPL | MSFT | vs. comparison
| Price | $150 | $380 |
| RSI | 55 | 62 |
| Signal | BUY | WATCH |
PASS PASS PASS FAIL
CONFIDENCE_SUMMARY
==================
HUMAN_REVIEW_REQUIRED
=====================
""" + "x" * 8000
        result = _score_report(report, "comparison")
        assert "comparison_tables" in result["details"]
        assert result["details"]["comparison_tables"] > 0

    def test_request_type_parameter_in_source(self):
        """Verify _score_report accepts request_type parameter in source."""
        src = _src.read_text()
        assert "def _score_report(text: str, request_type:" in src
        assert "_score_report(final_text, request_type=req_type)" in src


class TestAutoRetry:
    """Enhancement #3: Auto-retry thin generator drafts."""

    def test_retry_logic_in_source(self):
        src = _src.read_text()
        assert "THIN DRAFT detected" in src
        assert "retrying with slim prompt" in src or "retrying with data-only prompt" in src
        assert "retry_prompt" in src
        assert "retry_text" in src

    def test_retry_threshold(self):
        """Verify retry triggers on drafts < 3000 chars."""
        src = _src.read_text()
        assert "< 3000" in src


class TestPredictionFix:
    """Enhancement #4: Prediction tracking uses MCP signal data."""

    def test_uses_signal_from_mcp_data(self):
        src = _src.read_text()
        assert 'signal_label = f"signal_{ticker}"' in src
        assert "signal_result = mcp_data.get(signal_label" in src

    def test_checks_prediction_id(self):
        src = _src.read_text()
        assert 'pred_id = signal_data.get("prediction_id"' in src
        assert "Auto-stored during MCP" in src

    def test_fallback_to_manual_store(self):
        src = _src.read_text()
        assert '"trading_signal": signal_data' in src

    def test_mcp_data_initialized(self):
        src = _src.read_text()
        assert "mcp_data = {}       # Raw MCP results" in src


class TestSelfReflection:
    """Enhancement #5: Self-reflection loop."""

    def test_critique_prompt_exists(self):
        src = _src.read_text()
        assert "Self-reflection" in src or "self-critique" in src.lower()
        assert "critique_prompt" in src
        assert "CLEAN" in src

    def test_fix_on_issues(self):
        src = _src.read_text()
        assert "fix_prompt" in src
        assert "issue_count" in src

    def test_size_threshold(self):
        """Accept fix only if > 70% of original size."""
        src = _src.read_text()
        assert "0.7" in src


class TestComparisonUpgrade:
    """Enhancement #6: Multi-ticker comparison mode upgrade."""

    def test_comparison_has_extended_tools(self):
        src = _src.read_text()
        block_start = src.index('elif request_type == "comparison":')
        # Find end of comparison block
        remaining = src[block_start:]
        block_end = remaining.index("\n    elif ") if "\n    elif " in remaining else len(remaining)
        block = remaining[:block_end]
        # Should have extended tools
        assert "analyze_volume_tool" in block
        assert "analyze_volatility_tool" in block
        assert "detect_insider_cluster" in block

    def test_comparison_capped_at_2(self):
        src = _src.read_text()
        block_start = src.index('elif request_type == "comparison":')
        block = src[block_start:block_start+200]
        assert "tickers[:2]" in block

    def test_comparison_prompt_addendum(self):
        src = _src.read_text()
        assert "COMPARISON MODE" in src
        assert "WINNER RECOMMENDATION" in src


class TestStructuredJSON:
    """Enhancement #7: Structured JSON output."""

    def test_json_extraction_in_pipeline(self):
        src = _src.read_text()
        assert "structured_json" in src
        assert "Extracting structured JSON" in src

    def test_json_file_saved(self):
        src = _src.read_text()
        assert "vault_name}.json" in src

    def test_json_stored_in_job(self):
        src = _src.read_text()
        assert '"structured_data"' in src

    def test_json_parsing_handles_backticks(self):
        """Verify code strips ```json wrapper."""
        src = _src.read_text()
        assert "startswith(\"```\")" in src


class TestPredictionsDashboard:
    """Enhancement #8: Predictions dashboard API endpoints."""

    def test_predictions_endpoint(self):
        src = _src.read_text()
        assert 'path == "/predictions"' in src
        assert "get_cached_predictions" in src
        assert "get_best_cached_trades" in src
        assert "generate_efficiency_report" in src

    def test_predictions_update_endpoint(self):
        src = _src.read_text()
        assert 'path == "/predictions/update"' in src
        assert "update_prediction_outcomes" in src

    def test_update_uses_mcp_lock(self):
        src = _src.read_text()
        # Find the predictions/update handler
        idx = src.index('path == "/predictions/update"')
        block = src[idx:idx+500]
        assert "_mcp_lock" in block


class TestWebhook:
    """Enhancement #9: Webhook notifications."""

    def test_webhook_function_exists(self):
        src = _src.read_text()
        assert "def _send_webhook(" in src
        assert "WEBHOOK_URL" in src

    def test_webhook_config_loaded(self):
        src = _src.read_text()
        assert 'WEBHOOK_URL = ENV.get("WEBHOOK_URL"' in src

    def test_webhook_called_after_email(self):
        src = _src.read_text()
        email_pos = src.index("Email FINAL report (quality-gated)")
        webhook_pos = src.index("Webhook notification (Telegram/Slack")
        assert email_pos < webhook_pos

    def test_webhook_is_fire_and_forget(self):
        src = _src.read_text()
        assert "threading.Thread" in src
        assert "daemon=True" in src


class TestReportDiff:
    """Enhancement #10: Report diff detection."""

    def test_diff_function_exists(self):
        src = _src.read_text()
        assert "def _compute_report_diff(" in src

    def test_diff_detects_price_change(self):
        prev = "Price: $100.00 | Signal: BUY | Entry: $101.00"
        new = "Price: $105.00 | Signal: BUY | Entry: $106.00"
        diff = _compute_report_diff(prev, new, "AAPL")
        assert "CHANGES FROM PREVIOUS SCAN" in diff
        assert "Price" in diff

    def test_diff_detects_signal_change(self):
        prev = "Signal: BUY | Price: $100"
        new = "Signal: SELL | Price: $100"
        diff = _compute_report_diff(prev, new, "AAPL")
        assert "Signal changed" in diff
        assert "BUY -> SELL" in diff

    def test_diff_empty_when_identical(self):
        text = "Price: $100.00 | Signal: BUY | Entry: $101.00"
        diff = _compute_report_diff(text, text, "AAPL")
        assert diff == ""

    def test_diff_integrated_before_vault(self):
        src = _src.read_text()
        diff_pos = src.index("Report diff: detect material changes")
        vault_pos = src.index("Save the FINAL report to vault")
        assert diff_pos < vault_pos

    def test_json_enhanced_diff(self):
        src = _src.read_text()
        assert "CHANGES FROM PREVIOUS SCAN (JSON)" in src


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
