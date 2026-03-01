# Analyst Server — 3-Stage AI Pipeline

**File:** `analyst_server.py`
**Port:** `7799`
**UI:** `http://localhost:7799`

A local web application that routes every financial analysis request through three sequential AI stages: generation with live MCP data, adversarial audit by a second model, and manager-level resolution — then saves all three versions to your Obsidian vault and emails the final report.

---

## Why This Exists

A single AI model auditing its own output is structurally limited — it shares the same blind spots it created. This pipeline separates generation from auditing using a different model (Gemini), then brings in a third Claude Code session as an objective judge. No stage can see what it said in a previous session, which eliminates the confirmation bias that makes self-review unreliable for real-money decisions.

---

## Architecture

```
Your Prompt
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 1 — GENERATOR                                     │
│  Claude Code CLI  (your logged-in session)              │
│                                                          │
│  Context injected first:                                 │
│    • CLAUDE.md          (accounts, rules, MCP priority)  │
│    • instructions.md    (10-phase framework, tools)      │
│                                                          │
│  Then: your prompt                                       │
│  Uses: all 80+ investor-agent MCP tools                 │
│  Pulls: live Questrade data, technical analysis,        │
│         options chain, Dalio metrics, Brooks patterns    │
└──────────────────────┬──────────────────────────────────┘
                       │  DRAFT report
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 2 — ADVERSARIAL AUDITOR                           │
│  Gemini 2.0 Flash  (via curl, no SDK)                   │
│                                                          │
│  Mandate: find every error. Paid per finding.           │
│  Checks:  math, options mechanics, CCPC tax rules,      │
│           Brooks probabilities, Dalio interpretations,   │
│           internal contradictions, missing risks         │
│  Output:  numbered FINDING blocks with QUOTE /          │
│           ERROR_TYPE / CORRECT_ANSWER / CONFIDENCE      │
└──────────────────────┬──────────────────────────────────┘
                       │  AUDIT report
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 3 — RESOLVER / MANAGER                            │
│  Claude Code CLI  (fresh session, no memory of Stage 1) │
│                                                          │
│  Receives: original draft + Gemini audit                │
│  Produces: RESOLUTION_LOG  (VALID / INVALID / UNCERTAIN) │
│            FINAL_REPORT    (corrected, actionable)      │
│            CONFIDENCE_SUMMARY  (per section)            │
│            HUMAN_REVIEW_REQUIRED  (what to verify)      │
└──────────────────────┬──────────────────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
         Obsidian Vault      Email
   /Ahmed/Trading Reports/   ahalaa@yahoo.com
   NAME_DRAFT_DATE.md
   NAME_AUDIT_DATE.md
   NAME_FINAL_DATE.md
```

---

## Context Loading

At startup the server reads two files and holds them in memory:

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Account numbers, Questrade token rules, MCP tool priority, vault paths, data integrity rules |
| `reportsGenerator/instructions.md` | 10-phase framework, all tool signatures, McMillan/Brooks/Dalio methodology, 5-gate validation, report templates |

These are injected verbatim at the top of every Stage 1 prompt — before your question — so Claude Code has full methodology context without relying on its training memory. The generator starts every session knowing your exact account numbers, the options sizing rules, CCPC tax structure, and which MCP tools to call in which order.

If you update either file, restart the server and the new content is picked up automatically.

---

## Vault Output

Three markdown files are written to `/Users/AhmedE/Ahmed/Trading Reports/` after every run:

| File | Contents |
|------|----------|
| `NAME_DRAFT_YYYY-MM-DD_HHMM.md` | Raw output from Stage 1 — Claude Code's first attempt with live data |
| `NAME_AUDIT_YYYY-MM-DD_HHMM.md` | Gemini's full audit with all FINDING blocks |
| `NAME_FINAL_YYYY-MM-DD_HHMM.md` | Resolver's corrected report — this is what you act on |

The DRAFT is kept because it shows what the MCP tools actually returned before any corrections, useful for debugging data quality issues.

---

## Email Setup

Email is sent via Gmail SMTP using an App Password. Regular Gmail passwords do not work.

**Step 1 — Generate an App Password:**
1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Create a password named `Analyst`
3. Copy the 16-character code (format: `abcd efgh ijkl mnop`)

**Step 2 — Add to `.env`:**
```
GMAIL_USER=your_gmail_address@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
```

**Without credentials:** The server still runs. Email is skipped and the status bar shows `EMAIL_SKIPPED`. Vault saving always works regardless.

**Email format:** The final report is sent as both plain text and styled HTML with the report name and timestamp in the subject line.

---

## Running the Server

```bash
cd /Users/AhmedE/git/investor-agent
python3 analyst_server.py
```

Open `http://localhost:7799` in any browser. Stop with `Ctrl+C`.

**Requirements:**
- Python 3.12+
- `claude` CLI in PATH (Claude Code, logged in) — verify with `which claude`
- `curl` available (standard on macOS)
- investor-agent Docker container running for MCP tools: `docker ps | grep investor-agent`

---

## UI Walkthrough

### Header
Three pills — Generator, Auditor, Resolver — pulse gold while their stage is active and turn green on completion.

### Chat area (left)
- Your prompt appears as a gold bubble (right-aligned)
- A pipeline block appears for each stage showing streaming output word-by-word
- Generator and Auditor cards auto-collapse 1.8 seconds after finishing
- Resolver stays open — it contains the final report
- Two confirmation banners appear at the bottom when complete:
  - `⬡ 3 files saved — DRAFT · AUDIT · FINAL`
  - `✉ Sent → ahalaa@yahoo.com`

### Sidebar tracker (right)
Five steps with animated connecting lines that fill in as the pipeline progresses:

```
① Generator   Claude Code + MCP
② Auditor     Gemini 2.0 Flash        [N findings] badge
③ Resolver    Claude Code (judge)
⬡  Vault      Trading Reports/
✉  Email      ahalaa@yahoo.com
```

The Auditor step shows a blue badge with the finding count, or a green "Clean ✓" badge if Gemini found nothing.

### Input area (bottom)
- **Report name field** (left, 145px) — used as the vault file prefix
- **Prompt textarea** — auto-resizes up to 85px, Ctrl+Enter to submit
- **Quick prompts** — five pre-filled chips for common requests

---

## Quick Prompts

| Chip | Use case |
|------|----------|
| Full Monday war portfolio report — all 7 accounts | Weekly portfolio review across all Questrade accounts |
| AVGO puts — both CCPC accounts, roll or close? | Position management decision for corporate accounts |
| VIXY 250 shares — optimal spike exit timing | War hedge timing analysis |
| OKTA — war risk + earnings double risk + CCPC tax | Multi-factor risk analysis |
| Monday EOD action list — all open positions | End-of-day checklist |

---

## Auditor Error Types

Gemini classifies each finding by type:

| Type | Description |
|------|-------------|
| `Math` | Arithmetic error, wrong percentage, incorrect calculation |
| `Options_Mechanics` | Wrong ITM/OTM direction, incorrect premium flow, Greeks error |
| `Tax` | CCPC tax rate error, incorrect RDTOH claim, wrong capital gains treatment |
| `Logic` | Contradictory recommendation, circular reasoning |
| `Omission` | Missing risk, no exit condition, absent sizing logic |
| `Contradiction` | Two sections making incompatible claims |
| `Brooks` | Incorrect pattern identification or probability claim |
| `Dalio` | Wrong ratio interpretation or dollar flow direction |

---

## Resolver Output Sections

The final report from Stage 3 always contains four sections in this order:

**RESOLUTION_LOG** — one line per Gemini finding: `FINDING #N → VALID/INVALID/UNCERTAIN + reason`

**FINAL_REPORT** — the complete corrected analysis you act on, including executive summary, technical analysis, options strategy, trade plan with entry/stop/targets, CCPC tax implications, and position sizing

**CONFIDENCE_SUMMARY** — per-section confidence rating (HIGH / MEDIUM / LOW) so you know where the analysis is solid and where to apply more scrutiny

**HUMAN_REVIEW_REQUIRED** — numbered list of UNCERTAIN items that cannot be resolved from data alone, requiring your manual verification before placing any trade

---

## File Structure

```
investor-agent/
├── analyst_server.py          ← the server (run this)
├── ANALYST_SERVER.md          ← this file
├── CLAUDE.md                  ← injected as Stage 1 context
├── reportsGenerator/
│   └── instructions.md        ← injected as Stage 1 context
└── .env                       ← add GMAIL_USER + GMAIL_APP_PASSWORD here

/Users/AhmedE/Ahmed/Trading Reports/
├── NAME_DRAFT_2026-03-01_1430.md
├── NAME_AUDIT_2026-03-01_1430.md
└── NAME_FINAL_2026-03-01_1430.md
```

---

## Configuration Reference

All configuration is at the top of `analyst_server.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `7799` | Local server port |
| `REPO` | `/Users/AhmedE/git/investor-agent` | Repo root, used to find context files |
| `VAULT` | `/Users/AhmedE/Ahmed/Trading Reports` | Obsidian vault output directory |
| `GEMINI_KEY` | hardcoded | Gemini API key for Stage 2 |
| `GEMINI_URL` | `gemini-2.0-flash` | Model endpoint |
| `CLAUDE_BIN` | `claude` | Claude Code CLI binary name |
| `EMAIL_TO` | `ahalaa@yahoo.com` | Final report recipient |
| `CONTEXT_FILES` | `CLAUDE.md`, `instructions.md` | Files injected into every Stage 1 prompt |

To add more context files (e.g. `COMPREHENSIVE_REPORT_GENERATOR.md`), add them to the `CONTEXT_FILES` list.

---

## Troubleshooting

**Server won't start:**
```bash
which claude          # must return a path
python3 --version     # must be 3.12+
lsof -i :7799         # check if port is already in use
```

**Stage 1 produces no output / exits immediately:**
```bash
claude --version      # confirm Claude Code is logged in
claude -p "hello"     # test CLI directly
```

**Gemini returns a parse error:**
The curl output will appear in the Auditor block. Common causes: API key expired, network proxy blocking `generativelanguage.googleapis.com`, or Gemini rate limit. The pipeline continues — Stage 3 will note the audit was unavailable.

**Email not sending:**
Check `.env` has both `GMAIL_USER` and `GMAIL_APP_PASSWORD`. Confirm the App Password was generated at `myaccount.google.com/apppasswords` (not your regular Gmail password). Gmail must have 2FA enabled before App Passwords work.

**Vault files not appearing:**
Check `/Users/AhmedE/Ahmed/Trading Reports/` exists. The server creates it automatically but will fail if parent `/Users/AhmedE/Ahmed/` doesn't exist.
