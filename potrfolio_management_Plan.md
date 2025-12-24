# Professional ETF and Mutual Fund Analysis for Algorithmic Trading

Building institutional-quality fund analysis capabilities for an MCP server requires mastery of **five core domains**: metrics calculation, data acquisition, Canadian market specifics, technical application, and portfolio-level synthesis. This research provides specific formulas, Python implementations, and decision frameworks ready for production deployment.

The most critical finding across all research: **expense ratio is the single most reliable predictor of future fund performance**—cheapest quintile funds succeed 62% of the time versus 20% for the most expensive. Build every analysis tool with cost efficiency as a primary lens.

## Core risk-adjusted metrics with exact implementations

Professional fund analysis relies on eight risk-adjusted return metrics, each serving distinct purposes. The **Sharpe ratio** remains the industry standard but penalizes upside volatility equally with downside—use `(Rp - Rf) / σp` with returns annualized by multiplying mean by 252 and standard deviation by √252. For investors who care only about downside risk, the **Sortino ratio** substitutes downside deviation, calculated using only returns below the minimum acceptable return (typically 0 or risk-free rate).

```python
def comprehensive_risk_metrics(returns, benchmark_returns, rf=0.01, N=252):
    excess = returns.mean() * N - rf
    sharpe = excess / (returns.std() * np.sqrt(N))
    downside = returns[returns < 0].std() * np.sqrt(N)
    sortino = excess / downside
    
    # Information ratio for active management assessment
    active_return = (returns - benchmark_returns).mean() * N
    tracking_error = (returns - benchmark_returns).std() * np.sqrt(N)
    info_ratio = active_return / tracking_error
    
    # Maximum drawdown for risk capacity
    cumulative = (1 + returns).cumprod()
    drawdown = (cumulative - cumulative.expanding().max()) / cumulative.expanding().max()
    max_dd = drawdown.min()
    calmar = (returns.mean() * N) / abs(max_dd)
    
    return {'sharpe': sharpe, 'sortino': sortino, 'info_ratio': info_ratio, 
            'max_drawdown': max_dd, 'calmar': calmar, 'tracking_error': tracking_error}
```

For active funds, **Information Ratio** (active return ÷ tracking error) measures skill—top-quartile managers achieve approximately **0.5 annualized**. Values of 0.4-0.6 indicate good risk-adjusted outperformance. **Jensen's Alpha** (`Rp - [Rf + β(Rm - Rf)]`) isolates CAPM-based excess returns, though statistical significance requires at least 36 months of data.

## ETF-specific metrics for quality assessment

ETFs require specialized metrics beyond mutual fund analysis. **Tracking error** (annualized standard deviation of return differences) reveals index replication quality—large-cap equity ETFs should achieve **<0.10%**, while international equity tolerates **<0.50%**. Tracking difference (cumulative return gap) should approximate the negative expense ratio; if worse by **>30 basis points**, the fund has structural problems.

**Premium/discount to NAV** indicates arbitrage efficiency. For domestic equity ETFs, deviations beyond ±0.10% are concerning; emerging market ETFs tolerate ±0.50%. Calculate in real-time using `(market_price - NAV) / NAV × 100`. The **iNAV** (indicative NAV) updates every 15 seconds during trading but becomes stale for funds holding international securities.

**Implied liquidity**—the most sophisticated ETF metric—calculates tradeable shares based on underlying holdings:

```python
def calculate_implied_liquidity(holdings_df, etf_price, participation_rate=0.10):
    """Calculate ETF liquidity from underlying securities"""
    holdings_df['tradable_value'] = holdings_df['adv'] * holdings_df['price'] * participation_rate
    holdings_df['implied_etf_shares'] = holdings_df['tradable_value'] / holdings_df['weight'] / etf_price
    return holdings_df['implied_etf_shares'].min()  # Most constraining holding
```

Bid-ask spreads provide immediate cost visibility: large-cap US ETFs average **1-3 basis points**, emerging markets **10-30 bps**. Total cost of ownership combines TER, bid-ask spread impact, premium/discount changes, and transaction costs over the holding period.

## Data architecture for US and Canadian funds

**SEC EDGAR N-PORT filings** provide the richest US fund data: complete holdings with CUSIP/ISIN, securities lending details, flow data, and risk metrics. Filed monthly but only Q3 publicly disclosed. Use `edgartools` (free) for parsing or `sec-api` (commercial) for query-based access. Rate limit: 10 requests/second.

```python
from sec_edgar_downloader import Downloader
dl = Downloader("YourCompany", "email@example.com")
dl.get("NPORT-P", "0000036405", limit=1)  # Download by CIK
```

**Questrade API** provides only market data—no holdings, expense ratios, or NAV data. Use it exclusively for execution and position monitoring.

**Canadian data is significantly more challenging**. SEDAR+ has no public API—only web-based access to Fund Facts documents, MRFPs, and prospectuses. QuoteMedia offers the only programmatic access via `getCompanyFilings` (commercial). For free Canadian data, scrape fund company websites directly: BMO at `bmo.com/assets/pdfs/gam/etf/`, Vanguard Canada at `fund-docs.vanguard.com/`.

**Yahoo Finance (yfinance)** provides price history reliably but expense ratios return `None` for most ETFs—do not depend on it for fund metadata. For iShares holdings, use the Python scraper at `github.com/talsan/ishares` which parses CSV downloads programmatically.

## Canadian fund analysis considerations

The **Management Expense Ratio (MER)** in Canada includes management fees, operating expenses, trailing commissions (Series A only), and GST/HST—more comprehensive than US expense ratios. **Trading Expense Ratio (TER)** adds brokerage costs. Total cost: **FER = MER + TER**. Typical equity fund MER: 2.0-2.5% (Series A) or 0.8-1.2% (Series F fee-based).

DSC funds were banned June 2022 in most provinces. Identify fund series by code: A/T = trailer-paying retail, F/TF = fee-based no trailer, D = discount brokerage. The trailer commission difference between Series A and F typically ranges **0.5-1.0%** annually.

**Withholding tax optimization** drives significant returns for US equity exposure:

| Account Type | US-Listed US Equity | CAD-Listed US Equity |
|--------------|---------------------|---------------------|
| **RRSP/RRIF** | **0% WHT** (treaty) | 15% WHT |
| TFSA | 15% WHT (non-recoverable) | 15% WHT |
| Non-registered | 15% (recoverable FTC) | 15% (recoverable) |

For RRSP accounts, **always use US-listed ETFs** (VTI, VXUS) to eliminate withholding tax. For TFSAs, the 15% is unavoidable regardless of structure.

**Currency hedging costs** approximately **0.5-1.7% annually** in tracking error plus 5-15 bps in direct forward contract costs. Use hedged versions (XSP, VSP) only when CAD strengthening is expected or for fixed income where volatility reduction matters more.

Canada's **superficial loss rule** (equivalent to US wash sale) applies to "identical property" within 30 days. Two index funds tracking the *same* index are identical, but different indexes are not—XIU.TO (S&P/TSX 60) and VCN.TO (FTSE Canada All Cap) are acceptable tax-loss harvesting pairs.

## Fund replacement decision framework

Academic research consistently shows **past performance does not predict future performance**—except for bottom-decile funds, which persistently underperform. Build replacement triggers around cost and consistent failure:

```python
def fund_replacement_score(fund):
    score = 0
    if fund['rolling_3yr_alpha'] < 0: score += 2
    if fund['category_percentile_rank'] > 75: score += 2  # Bottom quartile
    if fund['consecutive_years_underperforming'] >= 3: score += 3
    if fund['expense_ratio'] > fund['category_median'] * 1.25: score += 2
    if fund['manager_tenure'] < 3: score += 1
    # Score ≥ 5 = strong replacement candidate
    return score
```

**Active Share** (sum of absolute weight differences from benchmark ÷ 2) distinguishes truly active management from closet indexing. Values **<60%** indicate closet indexing; pay index fund fees for such exposure. High active share combined with high tracking error suggests concentrated stock picking; high active share with low tracking error suggests factor-neutral diversified selection.

Before switching, calculate **transition costs**: trading commissions, bid-ask spreads (both positions), market impact using the square-root model (`Impact = k × √(trade_size/ADV)`), and opportunity cost during execution. Break-even period = transition costs ÷ annual expense savings. Switch only when break-even is **under 3 years**.

## Technical analysis applications to ETFs

Al Brooks price action methodology applies directly to liquid ETFs (SPY, QQQ, IWM) using 5-minute candlesticks. Key adaptation: ETF prices are driven by underlying holdings, not pure supply/demand—creation/redemption mechanisms can override technical signals.

**Volume analysis differs fundamentally for ETFs**. High volume with premium indicates AP creation activity; high volume with discount indicates redemption. ETF liquidity equals the minimum of secondary market volume and underlying securities liquidity. Calculate relative volume (`current_volume / 20-day_average`) and combine with premium/discount for creation/redemption signals.

**Gamma exposure (GEX)** analysis for SPY, QQQ, and IWM options provides market regime signals:

```python
def calculate_gex(options_chain, spot_price):
    gex = 0
    for _, row in options_chain.iterrows():
        sign = 1 if row['type'] == 'call' else -1
        gex += sign * row['gamma'] * row['open_interest'] * 100 * spot_price
    return gex  # Positive = volatility-suppressing; Negative = volatility-amplifying
```

Positive GEX regimes see market makers hedging by selling into strength and buying weakness (mean-reverting conditions). Negative GEX amplifies moves as hedging follows price direction.

## Portfolio-level analysis for holdings aggregation

**Holdings overlap** prevents hidden concentration. Weight-adjusted overlap sums minimum weights across common holdings—**>50%** indicates significant redundancy warranting consolidation. SPY and QQQ share 7 of 10 top holdings, often surprising investors expecting diversification.

```python
def calculate_holdings_overlap(fund1_holdings, fund2_holdings):
    merged = pd.merge(fund1_holdings, fund2_holdings, on='ticker', suffixes=('_1', '_2'))
    merged['min_weight'] = merged[['weight_1', 'weight_2']].min(axis=1)
    return merged['min_weight'].sum() * 100  # Percentage overlap
```

**Factor exposure aggregation** uses the Fama-French 5-factor model (MKT-RF, SMB, HML, RMW, CMA) via regression. Kenneth French Data Library provides free factor returns. Weight-average exposures across portfolio funds to detect unintended bets—flag when `|actual - target| > 0.2` for any factor.

**Rebalancing signals** should use a **5% threshold with quarterly monitoring** (hybrid approach). Pure calendar rebalancing adds trading costs without return benefit; pure threshold misses opportunities during stable periods. Calculate trades needed: `target_value - current_value` per asset class, with minimum trade threshold to avoid excessive small transactions.

For **tax-loss harvesting**, maintain correlation matrices between fund pairs. Acceptable pairs require different index methodology (e.g., VTI tracking CRSP vs. SCHB tracking Dow Jones) with correlation **<0.95** for wash sale safety. In Canada, confirm the underlying index differs to avoid superficial loss rule.

## Robo-advisor methodologies as implementation blueprints

Wealthsimple and Betterment use nearly identical approaches: **Modern Portfolio Theory optimization using exclusively low-cost ETFs**. Selection criteria prioritize expense ratio (<0.10%), tracking error, AUM (>$100M), and bid-ask spread. Portfolio construction allocates equity percentage based on risk score (typically `30% + risk_score × 7%`), subdivided geographically: 50% US, 30% international developed, 10% emerging, 10% REITs.

Automatic rebalancing triggers at 5% drift thresholds. Tax-loss harvesting activates for accounts above $100K using pre-defined pairs. Tax-location optimization places bonds in tax-advantaged accounts, equities in taxable accounts, and international equities in taxable to capture foreign tax credits.

## Implementation priorities for the MCP server

Build tools in this order based on value delivered and complexity:

1. **Expense ratio analyzer** with category comparison—most predictive metric
2. **Holdings overlap calculator** using CUSIP/ISIN matching across N-PORT data
3. **Risk metrics suite** (Sharpe, Sortino, Information Ratio, Max Drawdown, Calmar)
4. **ETF quality scorer** combining tracking error, premium/discount volatility, liquidity, and expense efficiency
5. **Fund replacement framework** with transition cost calculator
6. **Factor exposure aggregator** using Fama-French regression
7. **Rebalancing signal generator** with tax-aware trade optimization
8. **Canadian fund analyzer** with MER/TER parsing and withholding tax optimization

For data pipelines, combine SEC EDGAR N-PORT parsing (quarterly holdings), yfinance (daily prices), and Kenneth French Data Library (factor returns). Store historical allocations for drift tracking. For Canadian funds, build PDF scrapers for Fund Facts documents from SEDAR+ and fund company websites.

The Morningstar star rating uses a risk-adjusted return methodology with 50% weight on 10-year performance, 30% on 5-year, and 20% on 3-year for mature funds. Distribution: top 10% = 5 stars, next 22.5% = 4 stars, middle 35% = 3 stars, next 22.5% = 2 stars, bottom 10% = 1 star. However, **star ratings have weak predictive power for future returns**—use them for screening, not selection.

The academic evidence is unambiguous: focus the MCP server on cost minimization, factor exposure control, and tax efficiency. Performance chasing through alpha prediction has no empirical support except for avoiding persistent losers.