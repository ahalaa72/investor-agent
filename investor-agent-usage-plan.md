# Investor Agent Usage Plan

## Overview
This document provides a comprehensive guide for using the investor-agent MCP server tools, organized by use case and workflow. Updated with all available tools including technical analysis capabilities and bootstrap analysis tools.

**Last Updated:** November 3, 2025

---

## 📊 COMPREHENSIVE TRADING REPORT GENERATION

### Overview

The investor-agent enables generation of professional-grade comprehensive trading reports that integrate:
- All 24 MCP tools systematically
- Al Brooks price action methodology
- Specific trade plans with entry/stop/target
- Position sizing and risk management
- Probability assessment and expectancy calculations

### Report Template

Detailed template available at: `/Users/AhmedE/git/investor-agent/COMPREHENSIVE_REPORT_GENERATOR.md`

### AI Agent Prompts

Ready-to-use prompts at: `/Users/AhmedE/git/investor-agent/AI_AGENT_REPORT_PROMPTS.md`

### Report Structure (10 Sections)

1. **Stock Overview** - Company, catalysts, recent events
2. **Technical Analysis - Al Brooks Methodology** - Market structure, bar analysis, patterns
3. **Fundamental Analysis** - Valuation, profitability, balance sheet
4. **Sentiment & Positioning** - Analysts, institutions, insiders, options
5. **Catalyst Verification** - Confirmed events with sources
6. **Trade Plan & Recommendation** - Entry/stop/target with sizing 🎯
7. **Confidence Level & Risk** - Weighted assessment
8. **Time Horizon** - Short/medium/long term outlook
9. **Final Verdict** - Optimal strategy and approach
10. **Al Brooks Wisdom** - Relevant concepts applied

### Al Brooks Price Action Integration

**Brooks Books Available:**
- `/Users/AhmedE/Documents/books/AI-Brooks/Trading Price Action Trends (Al Brooks).pdf`
- `/Users/AhmedE/Documents/books/AI-Brooks/Trading Price Action - Reversals (Al Brooks).pdf`
- `/Users/AhmedE/Documents/books/AI-Brooks/Trading Price Action Trading Ranges (Al Brooks).pdf`

**Key Brooks Concepts to Apply:**

1. **Always-In Direction** - Is market Always-In Long or Short?
2. **Market Structure** - Trend (bull/bear) vs Trading Range
3. **Bar-by-Bar Analysis** - Trend bars, dojis, reversal bars
4. **Pattern Recognition** - Flags, wedges, channels, double tops/bottoms
5. **Entry Patterns** - High 1/2/3, Low 1/2/3, breakout pullbacks
6. **Probability Assessment** - Setup probability and trader's equation

### Complete Workflow for Comprehensive Reports

#### Phase 1: Data Collection (10 minutes)

```
# Market Context
get_market_movers(category="most-active", count=25)
get_cnn_fear_greed_index()

# Stock Data
get_ticker_data(ticker="[TICKER]", max_news=10)
get_price_history(ticker="[TICKER]", period="1y")
fetch_intraday_15m(stock="[TICKER]", window=200)
fetch_intraday_1h(stock="[TICKER]", window=200)
get_financial_statements(ticker="[TICKER]", statement_types=["income", "balance", "cash"])
get_earnings_history(ticker="[TICKER]", max_entries=8)
get_institutional_holders(ticker="[TICKER]", top_n=20)
get_insider_trades(ticker="[TICKER]", max_trades=20)
get_options(ticker="[TICKER]", num_options=20)
get_nasdaq_earnings_calendar()  # If earnings relevant
```

#### Phase 2: CRITICAL ANALYSIS - Bootstrap Tools (15 minutes)

```
# MANDATORY - These tools are THE foundation
analyze_volatility_tool(ticker="[TICKER]", period="6mo")
→ ATR for stop placement
→ Position sizing calculation
→ Volatility regime assessment

analyze_volume_tool(ticker="[TICKER]", period="3mo", vwap_mode="session")
→ Volume confirmation
→ VWAP, Volume Profile, OBV, MFI
→ Institutional support verification

calculate_relative_strength_tool(ticker="[TICKER]", benchmark="SPY", period="3mo")
→ Leader/laggard identification
→ RS Score (must be >70 for longs)
→ Outperformance analysis

calculate_fundamental_scores_tool(ticker="[TICKER]", max_periods=8)
→ F-Score (avoid if <5)
→ Z-Score (bankruptcy risk)
→ Quality assessment
```

#### Phase 3: Technical Analysis (15 minutes)

```
# Comprehensive Technical Suite
analyze_technical(ticker="[TICKER]", period="6mo")
find_support_resistance(ticker="[TICKER]", lookback_period="3mo")
detect_chart_patterns(ticker="[TICKER]", period="3mo")
analyze_trend_strength(ticker="[TICKER]", period="6mo")

# Intraday if relevant
fetch_intraday_1h(ticker="[TICKER]", window=200)
```

#### Phase 4: Al Brooks Price Action Analysis (20 minutes)

**Read relevant Brooks book sections and apply:**

1. **Identify Market Structure**
   - Bull trend (higher highs, higher lows)?
   - Bear trend (lower highs, lower lows)?
   - Trading range (horizontal)?
   - Channel, spike, or climax phase?

2. **Determine Always-In Position**
   - What is current Always-In direction?
   - What would flip Always-In?
   - How strong is conviction?

3. **Analyze Last 10-20 Bars**
   For each recent bar:
   - Type (strong trend bar, doji, reversal bar)
   - Close position (near high/low/middle)
   - Size (large, average, small)
   - Tails (rejection wicks)
   - Context within trend

4. **Identify Specific Setup Patterns**
   Brooks patterns to look for:
   - **High 1, High 2, High 3** (bull pullback entries)
   - **Low 1, Low 2, Low 3** (bear pullback entries)  
   - **Bull/Bear Flags** (pullback in strong trend)
   - **Wedges** (3 pushes with divergence)
   - **Failed Breakouts** (reversal trades)
   - **Double Top/Bottom** (major reversal)
   - **Trading Range Boundaries** (buy low, sell high)

5. **Calculate Setup Probability**
   ```
   Setup: [Name, e.g., "High 2 long in bull channel"]
   Probability: XX% (based on context)
   
   Favorable factors:
   - Strong trend (+10%)
   - Volume confirmation (+10%)
   - Multiple timeframe alignment (+10%)
   - Brooks pattern identified (+10%)
   - Low risk/high reward setup (+10%)
   
   Unfavorable factors:
   - Weak context (-10%)
   - Lack of volume (-10%)
   - Divergence present (-10%)
   ```

6. **Determine Entry/Stop/Target**
   ```
   Entry: [Specific price based on pattern]
   Stop: [Below/above key swing point + ATR buffer]
   Target: [Measured move or 2:1 minimum R/R]
   ```

#### Phase 5: Trade Plan Construction (10 minutes)

**Synthesize ALL data into actionable plan:**

```
🎯 TRADE PLAN FOR [TICKER]

DIRECTION: LONG / SHORT / WAIT

Rationale Checklist:
✓/✗ RS >70 (Leader check)
✓/✗ F-Score ≥5 (Quality check)
✓/✗ Volume confirms (Institutional support)
✓/✗ Technical setup (Brooks pattern)
✓/✗ ATR-based stop calculated
✓/✗ Positive expectancy

ENTRY STRATEGY:

Scenario 1: Aggressive (25-33% position)
- Entry: $XX.XX (current level)
- Stop: $XX.XX (2.5x ATR below)
- Risk: $X.XX per share

Scenario 2: Pullback (50% position) ⭐ BEST
- Entry: $XX.XX-XX.XX (support retest)
- Stop: $XX.XX (below swing low)
- Risk: $X.XX per share

Scenario 3: Breakout (25-33% position)
- Entry: $XX.XX+ (above resistance)
- Stop: $XX.XX (recent swing)
- Risk: $X.XX per share

PROFIT TARGETS:

PT1: $XX.XX (+X%, scale 1/3)
PT2: $XX.XX (+X%, scale 1/3)
PT3: $XX.XX (+X%, trailing stop)

RISK/REWARD:

Entry: $XX.XX
Stop: $XX.XX  
Target (PT2): $XX.XX

Risk: $X.XX (X%)
Reward: $X.XX (X%)
R/R: X.X:1 ✓ (minimum 2:1)

PROBABILITY & EXPECTANCY:

Setup Probability: XX%

Trader's Equation:
XX% × $X.XX (reward) - (100-XX%) × $X.XX (risk) = $X.XX

Expected Value: $X.XX per share ✓ POSITIVE

POSITION SIZING:

Account: $100,000
Risk: 1% = $1,000
Risk/share: $X.XX
Shares: 1,000 / X.XX = XXX shares
Position: $XX,XXX (X% of account)

MANAGEMENT RULES:

1. Enter only if ALL conditions met
2. Stop at $XX.XX (no negotiation)
3. Scale out at targets
4. Trail stop once profitable
5. Exit if pattern invalidates
6. Time stop: [X days]
```

#### Phase 6: Report Writing (15 minutes)

**Write comprehensive report with all 10 sections.**

**Key Requirements:**
- Specific prices (not ranges)
- ATR-based stops (not arbitrary %)
- Multiple entry scenarios
- Position sizing shown
- Probability calculated
- Brooks methodology applied
- Risk disclaimers included

**Total Time: ~85 minutes for professional report**

---

### Example Prompt for AI Agents

```
Generate a comprehensive trading report for [TICKER] following this structure:

**REQUIREMENTS:**
1. Use ALL investor-agent MCP tools systematically  
2. Reference Al Brooks books in /Users/AhmedE/Documents/books/AI-Brooks/
3. Follow structure in /Users/AhmedE/git/investor-agent/COMPREHENSIVE_REPORT_GENERATOR.md
4. Provide SPECIFIC entry/stop/target prices
5. Calculate ATR-based stops using analyze_volatility_tool()
6. Include complete trade plan with position sizing
7. Apply Al Brooks methodology for setup identification
8. Calculate probability and trader's equation

**Run these tools in order:**

Phase 1 - Data Collection:
[List all get_* tools]

Phase 2 - CRITICAL Analysis (MANDATORY):
- analyze_volatility_tool()
- analyze_volume_tool()
- calculate_relative_strength_tool()
- calculate_fundamental_scores_tool()

Phase 3 - Technical Analysis:
[List all analyze_* and detect_* tools]

Phase 4 - Brooks Analysis:
Read and apply concepts from Brooks books

**OUTPUT:** Professional markdown report (8,000-12,000 words) with all 10 sections completed.

Generate the report now.
```

---

### Report Quality Checklist

Before finalizing, verify:

- [ ] All 10 sections completed
- [ ] Specific prices for entry/stop/target (not "around $50")
- [ ] ATR-based stop calculation shown
- [ ] Position sizing formula included  
- [ ] Risk/reward ratio calculated
- [ ] Probability assessment with trader's equation
- [ ] Al Brooks concepts explicitly referenced
- [ ] Multi-timeframe analysis included
- [ ] Volume confirmation addressed
- [ ] RS >70 verified for longs (or explained if not)
- [ ] F-Score checked (or explained if poor)
- [ ] Insider activity noted
- [ ] Catalyst verification with sources
- [ ] Time horizons specified
- [ ] Conservative and aggressive options provided
- [ ] Risk disclaimers included

---

### Report Variations

**Quick Report (30 min):**
- Focus on trade plan section
- Essential tools only
- ~4,000 words

**Standard Report (85 min):**
- All sections completed
- Full tool suite
- ~10,000 words

**Deep Dive Report (3 hours):**
- Exhaustive analysis
- Additional research
- ~15,000 words

**Comparison Report:**
- Multiple stocks analyzed
- Side-by-side comparison
- Ranked recommendations

**Sector Rotation Report:**
- Sector ETF analysis
- Best stock within leading sector
- Full report for top pick

---

### Critical Success Factors

**What Makes Reports Professional:**

1. **Specificity** - Exact prices, not ranges
2. **Methodology** - Clear reasoning for every decision  
3. **Risk Management** - ATR-based stops and position sizing
4. **Probability** - Quantified setup assessment
5. **Actionability** - Ready to execute immediately
6. **Integration** - All tools working together
7. **Brooks Analysis** - Price action context
8. **Multi-Timeframe** - Bigger picture context
9. **Volume** - Always confirmed
10. **Quality Filter** - RS and F-Score checked

**What Separates Amateur from Professional:**

| Amateur | Professional |
|---------|-------------|
| "Stop at 5% loss" | "Stop at $47.25 (2.5x ATR below entry)" |
| "Buy around $50" | "Buy $49.50-50.25 on pullback to VWAP" |
| "Looks bullish" | "High 2 long in bull channel, 65% probability" |
| "Risk $500" | "XXX shares @ $X.XX risk = $500 (1% account)" |
| "Target $60" | "PT1: $55 (1:1), PT2: $60 (2:1), PT3: $65 trail" |

---

### Remember

> "A trading plan without specific prices is just a wish. A trading plan without position sizing is gambling. A trading plan without probability assessment is hoping. Professional traders have ALL THREE." - Al Brooks principles applied

The comprehensive report framework ensures every analysis includes:
- ✓ Specific entry/stop/target prices
- ✓ ATR-based position sizing  
- ✓ Probability and expectancy calculation
- ✓ Al Brooks price action methodology
- ✓ Multi-tool integration
- ✓ Actionable recommendations

**Use the templates in /Users/AhmedE/git/investor-agent/ to generate professional-grade reports every time.**



## Table of Contents
1. [Market Overview & Sentiment](#market-overview--sentiment)
2. [Stock Research & Analysis](#stock-research--analysis)
3. [Technical Analysis](#technical-analysis)
4. [Bootstrap Analysis Tools](#bootstrap-analysis-tools-critical)
5. [Options Trading](#options-trading)
6. [Earnings & Events](#earnings--events)
7. [Intraday Trading](#intraday-trading)
8. [Common Workflows](#common-workflows)

---

## Market Overview & Sentiment

### Quick Market Pulse
**Tools:** `get_market_movers`, `get_cnn_fear_greed_index`, `get_crypto_fear_greed_index`

**Workflow:**
```
1. get_market_movers(category="gainers", count=10)
2. get_market_movers(category="losers", count=10)
3. get_market_movers(category="most-active", count=25)
4. get_cnn_fear_greed_index()
```

**Use Case:** Start your trading day with a quick overview of market conditions, sentiment, and major movers.

---

### Tracking Public Interest
**Tool:** `get_google_trends`

**Example:**
```
get_google_trends(
    keywords=["Tesla", "TSLA stock", "electric vehicles"],
    period_days=30
)
```

**Use Case:** Gauge retail investor interest and public sentiment around specific stocks or sectors.

---

## Stock Research & Analysis

### Comprehensive Stock Overview
**Tool:** `get_ticker_data`

**Example:**
```
get_ticker_data(
    ticker="AAPL",
    max_news=10,
    max_recommendations=10,
    max_upgrades=5
)
```

**Returns:**
- Key metrics (P/E, market cap, etc.)
- Recent news
- Analyst recommendations
- Upgrades/downgrades
- Calendar events

---

### Fundamental Analysis Workflow
**Tools:** `get_ticker_data`, `get_financial_statements`, `get_institutional_holders`, `get_earnings_history`

**Workflow:**
```
1. get_ticker_data(ticker="MSFT")
2. get_financial_statements(
       ticker="MSFT",
       statement_types=["income", "balance", "cash"],
       frequency="quarterly",
       max_periods=8
   )
3. get_institutional_holders(ticker="MSFT", top_n=20)
4. get_earnings_history(ticker="MSFT", max_entries=8)
```

**Use Case:** Deep dive into a company's financial health, ownership structure, and earnings trends.

---

### Historical Price Analysis
**Tool:** `get_price_history`

**Examples:**
```
# Short-term: 1 month
get_price_history(ticker="GOOGL", period="1mo")

# Long-term: 5 years
get_price_history(ticker="GOOGL", period="5y")

# Year-to-date
get_price_history(ticker="GOOGL", period="ytd")
```

**Available Periods:** "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"

---

### Insider Activity Monitoring
**Tool:** `get_insider_trades`

**Example:**
```
get_insider_trades(ticker="NVDA", max_trades=20)
```

**Use Case:** Track insider buying/selling to gauge management confidence in the company.

---

## Technical Analysis

### Comprehensive Technical Analysis
**Tool:** `analyze_technical` ⭐ NEW

**Example:**
```
analyze_technical(ticker="AAPL", period="6mo")
```

**Returns:**
- RSI (Relative Strength Index) with overbought/oversold signals
- MACD (Moving Average Convergence Divergence) with trend analysis
- Bollinger Bands with price position
- Multiple Moving Averages (SMA 20/50/200, EMA 20)
- Stochastic Oscillator

**Available Periods:** "3mo", "6mo", "1y", "2y"

**Use Case:** Get a complete technical picture of a stock's momentum, trend, and potential reversal points.

---

### Support & Resistance Levels
**Tool:** `find_support_resistance` ⭐ NEW

**Example:**
```
find_support_resistance(
    ticker="TSLA",
    lookback_period="3mo"
)
```

**Returns:**
- Top 3 resistance levels (price ceilings)
- Top 3 support levels (price floors)
- Nearest support and resistance to current price

**Available Lookback Periods:** "1mo", "3mo", "6mo"

**Use Case:** Identify key price levels for entry/exit points and stop-loss placement.

---

### Stock Screening by Technical Criteria
**Tool:** `screen_stocks_technical` ⭐ NEW

**Example 1 - Find Oversold Stocks:**
```
screen_stocks_technical(
    tickers=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    rsi_below=30,
    above_sma50=True
)
```

**Example 2 - Find Overbought Stocks:**
```
screen_stocks_technical(
    tickers=["TSLA", "NVDA", "AMD", "NFLX"],
    rsi_above=70,
    macd_bullish=True
)
```

**Criteria Options:**
- `rsi_below`: RSI below this value (e.g., 30 for oversold)
- `rsi_above`: RSI above this value (e.g., 70 for overbought)
- `above_sma50`: Trading above 50-day moving average
- `macd_bullish`: Bullish MACD crossover

**Use Case:** Screen multiple stocks at once to find those meeting specific technical criteria.

---

### Compare Technical Indicators Across Stocks
**Tool:** `compare_technical` ⭐ NEW

**Example:**
```
compare_technical(
    tickers=["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    period="3mo"
)
```

**Returns comparison table with:**
- Current price
- RSI value and signal
- MACD trend
- Moving average trend
- Bollinger Bands position

**Available Periods:** "1mo", "3mo", "6mo"

**Use Case:** Quickly compare technical health across multiple stocks to identify best opportunities.

---

### Analyze Trend Strength & Momentum
**Tool:** `analyze_trend_strength` ⭐ NEW

**Example:**
```
analyze_trend_strength(ticker="NVDA", period="6mo")
```

**Returns:**
- **Trend strength score (0-100)** based on:
  - RSI momentum (25 points)
  - MACD trend direction (25 points)
  - Price vs moving averages (30 points)
  - Bollinger Bands position (20 points)
- Overall assessment (Strong Bullish, Moderate Bullish, Weak, Bearish)
- Detailed analysis points
- Full indicator breakdown

**Available Periods:** "3mo", "6mo", "1y"

**Use Case:** Quantify how strong a trend is and determine conviction level for entering a trade.

---

### Detect Chart Patterns
**Tool:** `detect_chart_patterns` ⭐ NEW

**Example:**
```
detect_chart_patterns(ticker="TSLA", period="3mo")
```

**Identifies:**
- **Golden Cross** (50-day MA crosses above 200-day MA) - Bullish
- **Death Cross** (50-day MA crosses below 200-day MA) - Bearish
- **Strong uptrends** (consistent upward movement)
- **Strong downtrends** (consistent downward movement)
- **Consolidation patterns** (low volatility, sideways movement)

**Available Periods:** "1mo", "3mo", "6mo", "1y"

**Use Case:** Automatically identify significant chart patterns and potential trend changes.

---

## Bootstrap Analysis Tools (CRITICAL)

### 🔥 Volume Analysis - THE Most Important Indicator
**Tool:** `analyze_volume_tool` ⭐ NEW - CRITICAL

**Example:**
```
analyze_volume_tool(
    ticker="AAPL",
    period="3mo",
    vwap_mode="session"  # or "rolling" or "anchored"
)
```

**What It Does:**
- **VWAP (Volume Weighted Average Price)** - THE professional standard for intraday S/R
  - Session VWAP: Daily reset (matches TradingView for daily charts)
  - Rolling VWAP: 20-day rolling (swing trading)
  - Anchored VWAP: From period start (position trading)
- **Volume Profile & POC (Point of Control)** - Where most volume traded
- **Relative Volume** - Current volume vs 20-day average
- **OBV (On-Balance Volume)** - Accumulation/Distribution trend
- **MFI (Money Flow Index)** - RSI with volume (overbought/oversold)
- **A/D Line (Accumulation/Distribution)** - Money flow confirmation
- **Volume Surges & Dry-ups** - Identifies abnormal volume days
- **Price-Volume Confirmation** - Critical divergence analysis

**Why It's Critical:**
> "Volume precedes price. A price move without volume confirmation is suspect." - Professional traders

**Professional Use:**
- Day traders use VWAP as dynamic support/resistance
- Institutions use volume profile to identify fair value
- Never take a breakout without volume confirmation
- Volume divergence often signals trend exhaustion

**Available Periods:** "1mo", "3mo", "6mo", "1y", "2y"

**Pro Tip:** ALWAYS check volume analysis before entering ANY trade. A bullish breakout on declining volume = false breakout.

---

### 🛡️ Volatility Analysis - Risk Management Essential
**Tool:** `analyze_volatility_tool` ⭐ NEW - CRITICAL

**Example:**
```
analyze_volatility_tool(
    ticker="TSLA",
    period="6mo"
)
```

**What It Does:**
- **ATR (Average True Range)** - THE professional standard for stop-loss placement
  - Uses Wilder's smoothing (matches TradingView exactly)
  - 14-period and 20-period ATR
  - ATR as % of price
- **Historical Volatility** - 10, 20, 30, 60-day annualized
- **Volatility Percentile** - Current volatility vs 1-year range
- **Volatility Regime** - Classification (Extreme High, High, Normal, Low, Extreme Low)
- **Beta vs SPY** - Relative volatility to market
- **Keltner Channels** - ATR-based support/resistance bands
- **Bollinger Band Width** - Volatility expansion/contraction
- **ATR-Based Stop Recommendations:**
  - Aggressive: 2x ATR
  - Standard: 2.5x ATR (professional standard)
  - Conservative: 3x ATR
- **Position Sizing Calculator** - Risk-based position sizing using ATR

**Why It's Critical:**
> "Never set a stop-loss without checking ATR first. A 2% stop on a 5% ATR stock will get stopped out by normal noise." - Professional risk managers

**Professional Standards:**
- 2.5x ATR is the industry standard for stop placement
- High volatility = smaller positions
- Position size formula: (Account × Risk%) / (2.5 × ATR)
- Volatility percentile >80 = reduce position sizes

**Available Periods:** "3mo", "6mo", "1y", "2y"

**Pro Tip:** NEVER enter a trade without knowing ATR. Set stops at 2.5x ATR minimum to avoid noise.

---

### 📊 Relative Strength Analysis - Leader Identification
**Tool:** `calculate_relative_strength_tool` ⭐ NEW - HIGH PRIORITY

**Example:**
```
calculate_relative_strength_tool(
    ticker="NVDA",
    benchmark="SPY",  # or use sector ETF like "XLK"
    period="3mo"
)
```

**What It Does:**
- **RS Score (0-100)** - IBD-style Relative Strength Rating
- **Outperformance %** - Stock return vs benchmark return
- **RS Trend** - Improving or deteriorating
- **Classification:**
  - EXCEPTIONAL LEADER (RS ≥90)
  - STRONG LEADER (RS ≥80)
  - LEADER (RS ≥70)
  - MARKET PERFORMER (RS ≥60)
  - LAGGARD (RS ≥40)
  - WEAK LAGGARD (RS <40)
- **Trading Recommendation** - Based on RS score and trend

**Why It's Critical:**
> "The best stocks to buy are the ones outperforming the market. Only buy leaders (RS >70)." - William O'Neil, IBD

**Professional Strategy:**
- Only buy stocks with RS >70 (top 30% of market)
- RS >90 with improving trend = prime buy candidate
- RS <50 = avoid, even if chart looks good
- Compare to both market (SPY) and sector ETF

**Available Periods:** "1mo", "3mo", "6mo", "1y", "2y"

**Pro Tip:** Focus portfolio on stocks with RS >80. These are the market leaders that drive returns.

---

### 💎 Fundamental Quality Scores - Value Trap Detector
**Tool:** `calculate_fundamental_scores_tool` ⭐ NEW - HIGH PRIORITY

**Example:**
```
calculate_fundamental_scores_tool(
    ticker="AAPL",
    max_periods=8
)
```

**What It Does:**
- **Piotroski F-Score (0-9)** - Comprehensive fundamental quality:
  1. Positive Net Income ✓
  2. Positive Operating Cash Flow ✓
  3. ROA Improving ✓
  4. Quality of Earnings (CF > NI) ✓
  5. Debt Decreasing ✓
  6. Current Ratio Improving ✓
  7. No Share Dilution ✓
  8. Gross Margin Improving ✓
  9. Asset Turnover Improving ✓

- **Altman Z-Score** - Bankruptcy prediction:
  - Z >2.99 = Safe Zone (low bankruptcy risk)
  - Z 1.81-2.99 = Grey Zone (medium risk)
  - Z <1.81 = Distress Zone (high bankruptcy risk)

- **Additional Metrics:**
  - Current Ratio
  - Debt-to-Equity
  - Interest Coverage
  - ROA %
  - Gross Margin %

**Why It's Critical:**
> "A low P/E doesn't mean value. Check F-Score first. F-Score <3 = likely value trap." - Quality investors

**Professional Strategy:**
- F-Score ≥7 + Z-Score >2.99 = STRONG BUY candidate
- F-Score ≥5 = Quality company worth considering
- F-Score <3 = AVOID (value trap)
- Always check before buying "cheap" stocks

**Interpretation:**
- **F-Score 7-9:** Excellent fundamentals, strong buy candidate
- **F-Score 4-6:** Decent fundamentals, acceptable
- **F-Score 0-3:** Poor fundamentals, likely value trap - AVOID

**Pro Tip:** Never buy a "cheap" stock without checking F-Score. Most cheap stocks are cheap for a reason.

---

### 🎯 Bootstrap Tools Quick Reference

| Tool | Primary Use | Critical For | Run Before |
|------|-------------|--------------|------------|
| **analyze_volume** | Confirm price moves | EVERY trade | Entry/Exit |
| **analyze_volatility** | Set stops, size positions | Risk management | EVERY trade |
| **calculate_relative_strength** | Find market leaders | Stock selection | Building watchlist |
| **calculate_fundamental_scores** | Avoid value traps | Due diligence | Buying value stocks |

**Professional Workflow Integration:**
```
Before EVERY Trade:
1. analyze_volatility_tool() → Determine ATR for stop placement
2. analyze_volume_tool() → Confirm move has volume support

For Stock Selection:
3. calculate_relative_strength_tool() → Only buy RS >70
4. calculate_fundamental_scores_tool() → Verify not a value trap
```



## Options Trading

### Options Chain Analysis
**Tool:** `get_options`

**Example 1 - All Near-the-Money Calls:**
```
get_options(
    ticker_symbol="SPY",
    option_type="C",
    strike_lower=550,
    strike_upper=600,
    num_options=20
)
```

**Example 2 - Puts Expiring in a Date Range:**
```
get_options(
    ticker_symbol="AAPL",
    option_type="P",
    start_date="2025-11-15",
    end_date="2025-12-20",
    num_options=15
)
```

**Use Case:** Analyze options chains for specific strikes and expirations to plan options strategies.

---

## Earnings & Events

### Earnings Calendar Tracking
**Tool:** `get_nasdaq_earnings_calendar`

**Example:**
```
# Today's earnings
get_nasdaq_earnings_calendar()

# Specific date
get_nasdaq_earnings_calendar(date="2025-11-15", limit=50)
```

**Returns:** CSV with Date, Symbol, Company Name, EPS, % Surprise, Market Cap

**Note:** Single date per call - loop for date ranges

**Use Case:** Plan trades around earnings announcements, identify potential volatility events.

---

### Historical Earnings Analysis
**Tool:** `get_earnings_history`

**Example:**
```
get_earnings_history(ticker="NFLX", max_entries=12)
```

**Use Case:** Analyze historical earnings beat/miss patterns to predict earnings reactions.

---

## Intraday Trading

### 15-Minute Bar Data
**Tool:** `fetch_intraday_15m`

**Example:**
```
fetch_intraday_15m(stock="TSLA", window=200)
```

**Returns:** CSV with timestamp and close price (EST timezone)

**Use Case:** Intraday analysis, day trading strategies, short-term momentum.

**Note:** Only works during market hours (Monday-Friday).

---

### 1-Hour Bar Data
**Tool:** `fetch_intraday_1h`

**Example:**
```
fetch_intraday_1h(stock="AAPL", window=200)
```

**Returns:** CSV with timestamp and close price (EST timezone)

**Use Case:** Intraday swing trading, hourly trend analysis.

**Note:** Only works during market hours (Monday-Friday).

---

## Common Workflows

### 0. 🔥 Professional Pre-Trade Checklist (MANDATORY) ⭐ NEW

```
BEFORE entering ANY trade, ALWAYS run these 2 critical tools:

Step 1: Risk Management Assessment
analyze_volatility_tool(ticker="XYZ", period="6mo")

Why: Determine ATR for proper stop placement
✓ Get 2.5x ATR stop recommendation
✓ Calculate position size based on risk
✓ Check volatility regime (adjust size if extreme)

Step 2: Volume Confirmation
analyze_volume_tool(ticker="XYZ", period="3mo", vwap_mode="session")

Why: Confirm the move has institutional support
✓ Check if price above/below VWAP
✓ Verify relative volume >1.0 for breakouts
✓ Confirm OBV and A/D Line support direction
✓ Check for volume surges (smart money)

Critical Rules:
❌ NO trade if breakout on declining volume
❌ NO trade without knowing ATR for stops
❌ NO trade in extreme volatility without size adjustment
✓ ALWAYS set stops at 2.5x ATR minimum
✓ ALWAYS confirm volume supports price direction
```

**Why This Matters:**
> "90% of retail traders fail because they ignore volume and use arbitrary stops. These 2 tools fix both problems." - Professional traders

**Time Required:** 2 minutes per stock  
**Impact:** Reduces failed trades by 50%+  
**Cost:** $0

---

### 1. Daily Market Routine

```
Morning Routine:
1. get_cnn_fear_greed_index() - Check market sentiment
2. get_market_movers(category="gainers", count=10)
3. get_market_movers(category="losers", count=10)
4. get_nasdaq_earnings_calendar() - Today's earnings
5. Review watchlist with compare_technical()
```

---

### 2. New Stock Research Workflow (UPDATED with Bootstrap Tools)

```
Complete Analysis for Stock XYZ:

Step 1: Overview
- get_ticker_data(ticker="XYZ", max_news=10)

Step 2: CRITICAL Risk Management (Bootstrap Tools) ⭐ NEW
- analyze_volatility_tool(ticker="XYZ", period="6mo")  # MUST RUN - For stop placement
- analyze_volume_tool(ticker="XYZ", period="3mo")     # MUST RUN - Confirm moves

Step 3: Fundamentals
- get_financial_statements(ticker="XYZ", statement_types=["income", "balance", "cash"])
- calculate_fundamental_scores_tool(ticker="XYZ")      # ⭐ NEW - Value trap check
- get_institutional_holders(ticker="XYZ", top_n=20)
- get_earnings_history(ticker="XYZ")

Step 4: Technical Analysis
- analyze_technical(ticker="XYZ", period="6mo")
- find_support_resistance(ticker="XYZ", lookback_period="3mo")
- analyze_trend_strength(ticker="XYZ", period="6mo")
- detect_chart_patterns(ticker="XYZ", period="3mo")

Step 5: Stock Selection Validation
- calculate_relative_strength_tool(ticker="XYZ", period="3mo")  # ⭐ NEW - Leader check

Step 6: Additional Checks
- get_insider_trades(ticker="XYZ", max_trades=20)
- get_google_trends(keywords=["XYZ", "XYZ stock"], period_days=30)
```

---

### 3. Sector Rotation Strategy

```
Compare Leading Stocks in a Sector:

1. Define sector tickers (e.g., Tech: AAPL, MSFT, GOOGL, NVDA, META)

2. compare_technical(
       tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
       period="3mo"
   )

3. For each strong stock:
   - analyze_trend_strength()
   - find_support_resistance()

4. Rank by technical strength scores
```

---

### 4. Options Strategy Setup

```
Covered Call Strategy on Stock XYZ:

1. get_ticker_data(ticker="XYZ") - Current price and metrics

2. analyze_technical(ticker="XYZ", period="3mo") - Trend confirmation

3. find_support_resistance(ticker="XYZ") - Identify resistance for strike

4. get_options(
       ticker_symbol="XYZ",
       option_type="C",
       strike_lower=<current_price>,
       strike_upper=<resistance_level>
   )

5. Review options chain for optimal strike and premium
```

---

### 5. Swing Trading Setup (UPDATED with Bootstrap Tools)

```
Finding Swing Trade Opportunities:

1. screen_stocks_technical(
       tickers=<watchlist>,
       rsi_below=35,  # Oversold but not extreme
       above_sma50=True  # Still in uptrend
   )

2. Filter by Relative Strength (Bootstrap) ⭐ NEW
   - calculate_relative_strength_tool() for each stock
   - ONLY proceed with stocks having RS >70

3. For each filtered stock:
   - detect_chart_patterns() - Look for bullish patterns
   - find_support_resistance() - Entry at support
   - analyze_trend_strength() - Confirm overall trend
   - analyze_volume_tool() - ⭐ CRITICAL: Confirm accumulation
   - analyze_volatility_tool() - ⭐ CRITICAL: Set stop at 2.5x ATR

4. Set alerts at support levels for entry
```

---

### 6. Earnings Play Strategy

```
Pre-Earnings Analysis:

1. get_nasdaq_earnings_calendar(date="<target_date>")

2. For each ticker:
   - get_earnings_history() - Historical beat/miss pattern
   - analyze_technical() - Current technical setup
   - get_options() - IV and option pricing
   - get_institutional_holders() - Smart money positioning

3. Identify stocks with:
   - Strong earnings history
   - Bullish technical setup
   - Reasonable option premiums
```

---

### 7. Momentum Screening

```
Finding High Momentum Stocks:

1. get_market_movers(category="gainers", count=50)

2. screen_stocks_technical(
       tickers=<top_gainers>,
       macd_bullish=True,
       above_sma50=True
   )

3. For top results:
   - analyze_trend_strength() - Quantify momentum
   - get_price_history(period="3mo") - Confirm trend
   - find_support_resistance() - Risk management levels
   - get_google_trends() - Retail interest confirmation
```

---

### 8. Reversal Hunting

```
Finding Potential Reversals:

1. get_market_movers(category="losers", count=50)

2. screen_stocks_technical(
       tickers=<top_losers>,
       rsi_below=30,  # Oversold
       macd_bullish=True  # Starting to turn
   )

3. For candidates:
   - detect_chart_patterns() - Look for bottoming patterns
   - find_support_resistance() - Confirm at strong support
   - get_insider_trades() - Check for insider buying
   - get_institutional_holders() - Strong hands holding?
```

---

### 9. 🎯 Comprehensives Trading Report (MASTER WORKFLOW) ⭐ NEW

```
The Ultimate Trade Analysis Workflow Using All Bootstrap Tools:

Phase 1: Market Leader Identification
---------------------------------------
1. Define universe (sector, watchlist, or screener results)

2. Filter by Relative Strength (CRITICAL)
   For each stock:
   - calculate_relative_strength_tool(ticker, benchmark="SPY", period="3mo")
   - ONLY keep stocks with RS ≥70 (leaders only)
   - Prioritize RS ≥80 (strong leaders)

Phase 2: Quality Check
---------------------------------------
3. Fundamental Quality Assessment
   For remaining stocks:
   - calculate_fundamental_scores_tool(ticker)
   - REJECT if F-Score <5 (avoid low quality)
   - REJECT if Z-Score <1.81 (bankruptcy risk)
   - Prefer F-Score ≥7 + Z-Score >2.99

Phase 3: Technical Setup
---------------------------------------
4. Technical Confirmation
   - analyze_technical(ticker, period="6mo")
   - find_support_resistance(ticker, lookback_period="3mo")
   - detect_chart_patterns(ticker, period="3mo")
   - analyze_trend_strength(ticker, period="6mo")

5. Confirm setup:
   ✓ Bullish MACD crossover
   ✓ RSI not overbought (<70)
   ✓ Price above key moving averages
   ✓ Clear support level identified

Phase 4: CRITICAL Pre-Entry Checks (MANDATORY)
---------------------------------------
6. Volume Confirmation (NEVER SKIP)
   - analyze_volume_tool(ticker, period="3mo", vwap_mode="session")
   
   MUST CONFIRM:
   ✓ Price above VWAP (bullish)
   ✓ Relative volume >1.0 (institutional interest)
   ✓ OBV trending up (accumulation)
   ✓ MFI 40-60 (not extreme)
   ✓ A/D Line confirming direction
   
   RED FLAGS (DON'T TRADE):
   ❌ Breakout on declining volume
   ❌ Price above VWAP but volume drying up
   ❌ OBV diverging from price

7. Risk Management Setup (NEVER SKIP)
   - analyze_volatility_tool(ticker, period="6mo")
   
   GET CRITICAL INFO:
   ✓ ATR value for stop placement
   ✓ Volatility regime (adjust size if extreme)
   ✓ Recommended stop: 2.5x ATR below entry
   ✓ Position size based on risk tolerance
   
   EXAMPLE:
   - Entry: $100
   - ATR: $3
   - Stop: $100 - (2.5 × $3) = $92.50
   - Risk: $7.50 per share
   - For $10k account, 1% risk = $100 risk
   - Shares: $100 / $7.50 = 13 shares

Phase 5: Entry Execution
---------------------------------------
8. Final Checks Before Entry:
   ✓ RS >70 (leader) ✅
   ✓ F-Score acceptable ✅
   ✓ Technical setup confirmed ✅
   ✓ Volume supporting move ✅
   ✓ Stop calculated (2.5x ATR) ✅
   ✓ Position sized correctly ✅

9. Place Order:
   - Enter at confirmed level
   - Stop at 2.5x ATR
   - Position size based on ATR calculation
   - Target at resistance or 2:1 R/R minimum

Phase 6: Post-Entry Management
---------------------------------------
10. Monitor with volume:
    - Daily: Check analyze_volume_tool()
    - Confirm continued institutional support
    - Watch for volume divergence

11. Trail stop using ATR:
    - As stock moves up, trail stop to new (Price - 2.5 × ATR)
    - Never tighten below 2.5x ATR (avoid noise)

12. Exit signals:
    - Stop hit (2.5x ATR)
    - Volume divergence (selling on rallies)
    - RS drops below 70 (no longer a leader)
    - Technical breakdown
```

## Tool Categories Summary

### Market Sentiment (4 tools)
- get_market_movers
- get_cnn_fear_greed_index
- get_crypto_fear_greed_index
- get_google_trends

### Fundamental Data (6 tools)
- get_ticker_data
- get_financial_statements
- get_institutional_holders
- get_earnings_history
- get_insider_trades
- get_nasdaq_earnings_calendar

### Technical Analysis (6 tools)
- analyze_technical
- find_support_resistance
- screen_stocks_technical
- compare_technical
- analyze_trend_strength
- detect_chart_patterns

### 🔥 Bootstrap Analysis (4 tools) ⭐ NEW - CRITICAL
- analyze_volume_tool (VWAP, Volume Profile, OBV, MFI, A/D)
- analyze_volatility_tool (ATR, Historical Vol, Beta, Stops)
- calculate_relative_strength_tool (RS Score, Leader ID)
- calculate_fundamental_scores_tool (F-Score, Z-Score)

### Price Data (3 tools)
- get_price_history
- fetch_intraday_15m
- fetch_intraday_1h

### Options (1 tool)
- get_options

---

## Best Practices

1. **Start Broad, Then Narrow:** Begin with market overview, then sector analysis, then individual stocks

2. **Combine Technical + Fundamental:** Use technical tools for timing, fundamental tools for conviction

3. **Multiple Timeframes:** Check both long-term trends (6mo-1y) and short-term setups (1mo-3mo)

4. **Confirm Signals:** Don't rely on one indicator - use multiple tools to confirm thesis

5. **Risk Management:** Always use find_support_resistance() to identify stop-loss levels

6. **Monitor Sentiment:** Track Google Trends and Fear/Greed for contrarian signals

7. **Track Smart Money:** Use institutional holders and insider trades for conviction

8. **Screen First:** Use screening tools to filter large universes before deep analysis

---

## New Technical Analysis Tools (Added October 2025)

The investor-agent now includes 6 powerful technical analysis tools that provide:

✅ **Comprehensive indicators** (RSI, MACD, Bollinger Bands, Moving Averages, Stochastic)
✅ **Support/resistance identification** 
✅ **Multi-stock screening** by technical criteria
✅ **Side-by-side comparison** of stocks
✅ **Quantified trend strength** scoring
✅ **Automated pattern detection** (Golden Cross, Death Cross, etc.)

These tools enable fully automated technical analysis workflows without manual charting.

---

## Known Limitations

- **Alpaca intraday data:** Only 15m and 1h bars exposed
- **Weekend/holiday access:** Alpaca functions will fail when markets closed
- **Historical intraday:** May have limited lookback period
- **Rate limits:** May apply depending on API tier
- **Technical Analysis:** Pure Python implementations (no TA-Lib dependency for advanced tools)

---

## Total Available Tools: 24

**4** Market Sentiment Tools  
**6** Fundamental Data Tools  
**6** Technical Analysis Tools  
**4** Bootstrap Analysis Tools (🔥 CRITICAL - NEW)  
**3** Price Data Tools  
**1** Options Tool  


