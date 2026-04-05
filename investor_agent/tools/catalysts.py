"""Catalyst analysis tools - news, insider, quality, competitors.

5 MCP tools + 5 helpers for catalyst strength assessment,
insider cluster detection, unusual options activity, quality scoring,
and competitor analysis.
"""
import logging
import math
import pandas as pd
import yfinance as yf
from typing import Any

from ..core.config import BROWSER_HEADERS
from ..core.validation import validate_ticker
from ..core.price import yf_call

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level references, populated by register_tools()
# Other modules import these _impl names; they become callable after
# register_tools() runs during server startup.
# ---------------------------------------------------------------------------
detect_catalyst_strength_impl = None
detect_insider_cluster_impl = None
detect_unusual_options_activity_impl = None
calculate_quality_score_impl = None
analyze_competitors_impl = None

# --- Unusual Options Activity (UOA) thresholds ---
UOA_VOL_OI_HIGH = 2.0       # Vol/OI ratio for HIGH confidence
UOA_VOL_OI_MEDIUM = 1.5     # Vol/OI ratio for MEDIUM confidence
UOA_PREMIUM_MIN = 50_000    # Minimum premium ($) to qualify as unusual
UOA_VOLUME_MIN = 1_000      # Minimum volume for HIGH confidence verification


def _fetch_google_news(ticker: str, max_results: int = 10) -> list:
    """
    Fetch recent news from Google News RSS - gives DATED headlines.

    Returns list of news with title, published date, and source.
    """
    import httpx
    import re
    from datetime import datetime, timedelta

    results = []
    try:
        # Google News RSS for stock ticker
        rss_url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"

        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(rss_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })

            if response.status_code == 200:
                xml = response.text

                # Parse RSS items
                items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)

                for item in items[:max_results]:
                    title_match = re.search(r'<title>(.*?)</title>', item)
                    pub_date_match = re.search(r'<pubDate>(.*?)</pubDate>', item)
                    source_match = re.search(r'<source[^>]*>(.*?)</source>', item)

                    if title_match:
                        title = title_match.group(1).strip()
                        # Clean CDATA
                        title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)

                        pub_date = None
                        days_ago = None
                        if pub_date_match:
                            try:
                                date_str = pub_date_match.group(1).strip()
                                # Parse RFC 2822 date format
                                pub_date = datetime.strptime(date_str[:25], '%a, %d %b %Y %H:%M:%S')
                                days_ago = (datetime.now() - pub_date).days
                            except:
                                pass

                        source = source_match.group(1).strip() if source_match else "Unknown"

                        results.append({
                            "title": title,
                            "published": pub_date.isoformat() if pub_date else None,
                            "days_ago": days_ago,
                            "source": source,
                            "is_recent": days_ago is not None and days_ago <= 3
                        })

                logger.info(f"Google News for '{ticker}' returned {len(results)} items")

    except Exception as e:
        logger.warning(f"Google News fetch failed for '{ticker}': {e}")

    return results


def _web_search_news(query: str, max_results: int = 5) -> list:
    """
    Search the web for news using DuckDuckGo (no API key required).

    Returns list of search results with title, snippet, and url.
    """
    import httpx
    import re
    from html import unescape

    results = []
    try:
        # DuckDuckGo HTML search (lightweight, no API key needed)
        search_url = "https://html.duckduckgo.com/html/"

        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.post(
                search_url,
                data={"q": query, "kl": "us-en"},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )

            if response.status_code == 200:
                html = response.text

                # Parse DuckDuckGo HTML results
                # Pattern: <a rel="nofollow" class="result__a" href="...">Title</a>
                titles = re.findall(r'class="result__a"[^>]*>([^<]+)</a>', html)

                # Snippet pattern: class="result__snippet">text</a>
                snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)</a>', html)

                # Fallback patterns if primary ones fail
                if not titles:
                    titles = re.findall(r'result__a[^>]*>([^<]+)</a>', html)

                if not snippets:
                    snippets = re.findall(r'result__snippet[^>]*>([^<]+)</a>', html)

                # Pair up titles and snippets
                for i, title in enumerate(titles[:max_results]):
                    title_clean = unescape(title.strip())
                    snippet_clean = unescape(snippets[i].strip()) if i < len(snippets) else ""

                    if title_clean:
                        results.append({
                            "title": title_clean,
                            "snippet": snippet_clean,
                            "source": "web_search"
                        })

                logger.info(f"Web search for '{query[:40]}' returned {len(results)} results")

    except Exception as e:
        logger.warning(f"Web search failed for '{query}': {e}")

    return results


def _check_insider_selling_context(ticker: str, news_items: list) -> dict:
    """
    Check if insider selling is part of a 10b5-1 pre-planned sale (NEUTRAL) or
    discretionary selling (BEARISH).

    10b5-1 plans are SEC-approved pre-arranged trading schedules that insiders set up
    while NOT in possession of material non-public information. Sales under these plans
    are NEUTRAL signals, not bearish.

    ENHANCED: Uses web search if yfinance news doesn't contain 10b5-1 mentions.

    Returns:
        - is_10b5_1: bool - True if evidence of pre-planned sale found
        - context: str - Description of what was found
        - confidence: HIGH / MEDIUM / LOW
        - should_discount: bool - True if selling should be discounted from bearish score
    """
    result = {
        "is_10b5_1": False,
        "context": None,
        "confidence": "LOW",
        "should_discount": False,
        "news_mentions": [],
        "web_search_performed": False
    }

    # Keywords indicating 10b5-1 or pre-planned sales
    TEN_B5_1_KEYWORDS = [
        "10b5-1", "10b-5-1", "rule 10b5-1", "rule 10b-5",
        "pre-arranged", "prearranged", "pre-planned", "preplanned",
        "trading plan", "automatic sale", "scheduled sale",
        "predetermined", "pre-determined"
    ]

    # Step 1: Check yfinance news items for 10b5-1 mentions
    if news_items:
        for item in news_items:
            title = str(item.get('title', '')).lower()
            summary = str(item.get('summary', '')).lower()
            content = title + " " + summary

            for keyword in TEN_B5_1_KEYWORDS:
                if keyword in content:
                    result["is_10b5_1"] = True
                    result["news_mentions"].append({
                        "title": item.get('title', '')[:100],
                        "keyword_found": keyword,
                        "source": "yfinance"
                    })
                    break

    # Step 2: If not found in yfinance, do web search for 10b5-1 context
    if not result["is_10b5_1"]:
        result["web_search_performed"] = True
        web_results = _web_search_news(f"{ticker} 10b5-1 insider selling plan 2024 2025", max_results=5)

        for item in web_results:
            title = str(item.get('title', '')).lower()
            snippet = str(item.get('snippet', '')).lower()
            content = title + " " + snippet

            for keyword in TEN_B5_1_KEYWORDS:
                if keyword in content:
                    result["is_10b5_1"] = True
                    result["news_mentions"].append({
                        "title": item.get('title', '')[:100],
                        "keyword_found": keyword,
                        "source": "web_search"
                    })
                    break

    # Determine confidence and whether to discount
    if result["news_mentions"]:
        if len(result["news_mentions"]) >= 2:
            result["confidence"] = "HIGH"
            result["context"] = f"Multiple sources confirm 10b5-1 plan ({len(result['news_mentions'])} mentions)"
        else:
            result["confidence"] = "MEDIUM"
            result["context"] = f"10b5-1 plan found via {'web search' if result['web_search_performed'] else 'news'}"
        result["should_discount"] = True
    else:
        result["context"] = "No 10b5-1 context found in news or web search - verify manually"
        result["confidence"] = "LOW"
        result["should_discount"] = False

    return result


def _analyze_news_sentiment(news_items: list, ticker: str = None) -> dict:
    """
    Analyze news headlines for bullish/bearish sentiment.

    ENHANCED: Also performs web search for major catalysts (deals, partnerships, etc.)

    NEWS SEVERITY SYSTEM (Jan 2026):
    - CRITICAL: Regulatory/policy changes, government actions, CEO/CFO changes
    - HIGH: Earnings guidance, major contracts, analyst clusters
    - MEDIUM: Product launches, partnerships, industry trends
    - LOW: General coverage, routine filings

    Returns:
        - sentiment: BULLISH / BEARISH / NEUTRAL / MIXED
        - bullish_count: Number of bullish headlines
        - bearish_count: Number of bearish headlines
        - notable_headlines: List of significant headlines
        - major_catalysts: List of major catalysts found via web search
        - critical_news: List of CRITICAL severity news requiring investigation
        - severity_breakdown: Count by severity level
    """
    result = {
        "sentiment": "NEUTRAL",
        "bullish_count": 0,
        "bearish_count": 0,
        "neutral_count": 0,
        "notable_headlines": [],
        "major_catalysts": [],
        "web_search_performed": False,
        "critical_news": [],  # NEW: Track critical severity news
        "severity_breakdown": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}  # NEW
    }

    # =========================================================================
    # CRITICAL REGULATORY KEYWORDS - MANDATORY WEB SEARCH TRIGGERS (Jan 2026)
    # When these appear, MUST flag as CRITICAL and investigate further
    # =========================================================================
    CRITICAL_REGULATORY_KEYWORDS = [
        # Government/Policy — Political figure names REMOVED (they appear in both
        # bullish and bearish contexts; "Trump announces $40B deal" ≠ bearish).
        # Only action-oriented policy terms remain.
        "congress", "senate", "white house", "executive order",
        "legislation", "bill signed", "law passed", "government shutdown", "federal shutdown",
        # Regulatory Bodies
        "sec", "doj", "ftc", "cfpb", "fcc", "fda", "epa", "fed", "federal reserve",
        # Regulatory Actions
        "regulation", "regulatory", "cap", "rate cap", "price cap", "fee cap",
        "ban", "banned", "restriction", "antitrust", "monopoly", "breakup",
        "investigation", "probe", "subpoena", "lawsuit", "sue", "sued",
        "fraud", "accounting", "restatement", "material weakness",
        # Executive Changes
        "ceo", "cfo", "coo", "resignation", "fired", "terminated", "steps down",
        "sudden departure", "leaves company", "retires effective immediately",
        # Critical Business
        "bankruptcy", "default", "delisting", "going concern", "liquidity crisis"
    ]

    # HIGH severity keywords
    HIGH_SEVERITY_KEYWORDS = [
        "earnings", "guidance", "outlook", "forecast", "billion dollar", "major contract",
        "strategic review", "restructuring", "layoffs", "workforce reduction",
        "upgrade", "downgrade", "price target", "rating change"
    ]

    # Sentiment keywords - comprehensive list
    BULLISH_KEYWORDS = [
        "upgrade", "beat", "beats", "exceeds", "surpasses", "raises", "raised",
        "positive", "bullish", "outperform", "buy rating", "strong buy",
        "growth", "record high", "breakthrough", "wins", "awarded", "partnership",
        "expansion", "launch", "momentum", "surge", "soars", "jumps", "rallies",
        "deal", "contract", "agreement", "acquisition", "approved", "fda approval",
        "higher", "gains", "climbs", "rises", "up", "order", "orders", "buy",
        "skyrocket", "boom", "lift", "soar", "spike", "advance", "accelerate",
        # Government/infrastructure/spending catalysts
        "billion", "million", "investment", "infrastructure", "project",
        "announced", "announces", "secured", "selected", "chosen",
        "revenue", "pipeline", "backlog", "funding",
    ]

    BEARISH_KEYWORDS = [
        "downgrade", "miss", "misses", "disappoints", "cuts guidance", "lowers outlook", "lowered",
        "negative", "bearish", "underperform", "sell rating", "concern", "concerns",
        "decline", "falls", "drops", "plunges", "slumps", "weakness", "weak",
        "lawsuit", "investigation", "recall", "warning", "layoffs", "restructuring",
        "ban", "banned", "restriction", "sanctions", "tariff war", "trade war",
        "export ban", "blocked by", "slide", "tumble",
        "threat", "probe", "fine", "penalty", "delay", "halt", "suspend",
        "rate cap", "price cap", "fee cap", "ceiling"
        # REMOVED overly generic: "hit", "down", "loss", "risk", "block", "export",
        # "tariff", "cap", "limit", "cuts" — too many false positives on bullish
        # headlines like "Trump hits $40B deal", "block funding approved", "tariff exemption"
    ]

    # Major catalyst keywords (requires web search for context)
    MAJOR_CATALYST_KEYWORDS = [
        "china", "deal", "contract", "billion", "partnership", "acquisition",
        "merger", "fda", "approval", "ban", "restriction", "tariff", "antitrust"
    ]

    def _word_boundary_match(keyword: str, text: str) -> bool:
        """Check if keyword exists as a whole word in text (not substring)."""
        import re
        # Use word boundaries to avoid "ban" matching "Bank"
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))

    def _classify_news_severity(title: str, days_ago: int = None) -> str:
        """Classify news item severity: CRITICAL, HIGH, MEDIUM, LOW."""
        title_lower = title.lower()

        # CRITICAL: Regulatory/policy OR very recent (today) with high keywords
        # Use word boundary matching to avoid false positives (e.g., "ban" in "Bank")
        if any(_word_boundary_match(kw, title_lower) for kw in CRITICAL_REGULATORY_KEYWORDS):
            return "CRITICAL"

        # HIGH: Earnings, guidance, major contracts
        if any(_word_boundary_match(kw, title_lower) for kw in HIGH_SEVERITY_KEYWORDS):
            return "HIGH"

        # MEDIUM: Recent news (0-2 days) with sentiment
        if days_ago is not None and days_ago <= 2:
            return "MEDIUM"

        # LOW: Everything else
        return "LOW"

    def _get_critical_keywords_found(title: str) -> list:
        """Get list of critical keywords found in title using word boundary matching."""
        title_lower = title.lower()
        return [kw for kw in CRITICAL_REGULATORY_KEYWORDS if _word_boundary_match(kw, title_lower)]

    def _net_sentiment(text: str) -> tuple:
        """
        Score sentiment by counting bullish vs bearish keyword matches
        using word boundary matching. Returns (sentiment, bull_count, bear_count).

        Net scoring prevents false negatives where both lists match
        (e.g., "Trump announces $40B deal" matching "deal" bullish + "trade war" bearish).
        """
        bull_hits = [kw for kw in BULLISH_KEYWORDS if _word_boundary_match(kw, text)]
        bear_hits = [kw for kw in BEARISH_KEYWORDS if _word_boundary_match(kw, text)]
        bull_count = len(bull_hits)
        bear_count = len(bear_hits)

        if bull_count > bear_count:
            return ("BULLISH", bull_count, bear_count)
        elif bear_count > bull_count:
            return ("BEARISH", bull_count, bear_count)
        elif bull_count == bear_count and bull_count > 0:
            # Tie — check for strong bullish signals that override
            strong_bullish = any(_word_boundary_match(kw, text) for kw in [
                "deal", "contract", "agreement", "awarded", "partnership",
                "billion", "approved", "fda approval", "record", "breakthrough",
                "infrastructure", "investment", "project", "funding", "selected",
                "announced", "secured", "revenue", "pipeline", "backlog",
            ])
            return ("BULLISH" if strong_bullish else "NEUTRAL", bull_count, bear_count)
        else:
            return ("NEUTRAL", 0, 0)

    # Step 1: Analyze yfinance news with SEVERITY CLASSIFICATION
    if news_items:
        for item in news_items[:10]:
            title_original = item.get('title', '')
            title = str(title_original).lower()

            sentiment, bull_n, bear_n = _net_sentiment(title)
            is_bullish = sentiment == "BULLISH"
            is_bearish = sentiment == "BEARISH"

            # NEW: Classify severity
            severity = _classify_news_severity(title, days_ago=None)
            result["severity_breakdown"][severity] += 1

            # NEW: CRITICAL news gets special handling
            if severity == "CRITICAL":
                critical_keywords_found = _get_critical_keywords_found(title)
                result["critical_news"].append({
                    "title": title_original[:150],
                    "severity": "CRITICAL",
                    "sentiment": sentiment,
                    "keywords": critical_keywords_found[:5],
                    "source": "yfinance",
                    "requires_investigation": True
                })
                # CRITICAL news counts 3x for scoring
                score_multiplier = 3
            elif severity == "HIGH":
                score_multiplier = 2
            else:
                score_multiplier = 1

            if is_bullish:
                result["bullish_count"] += score_multiplier
                result["notable_headlines"].append({
                    "title": title_original[:100],
                    "sentiment": "BULLISH",
                    "severity": severity,
                    "source": "yfinance"
                })
            elif is_bearish:
                result["bearish_count"] += score_multiplier
                result["notable_headlines"].append({
                    "title": title_original[:100],
                    "sentiment": "BEARISH",
                    "severity": severity,
                    "source": "yfinance"
                })
            else:
                result["neutral_count"] += 1

    # Step 2: Google News - GET ALL DATED NEWS, evaluate by RECENCY + IMPACT + SEVERITY
    if ticker:
        result["web_search_performed"] = True
        google_news = _fetch_google_news(ticker, max_results=15)

        # =========================================================================
        # STEP 2.5: SECTOR-AWARE BREAKING NEWS CHECK (Jan 2026)
        # Search for industry-wide regulatory news that affects this stock
        # Even if the news doesn't mention the ticker, it may be critical
        # =========================================================================
        SECTOR_NEWS_QUERIES = {
            # Financial sector - banks, credit cards, fintech
            "financial": [
                "credit card rate cap",
                "bank regulation 2026",
                "CFPB credit card",
                "interest rate cap legislation",
                "bank fee regulation",
            ],
            # Tech sector
            "tech": [
                "antitrust big tech",
                "AI regulation",
                "data privacy legislation",
            ],
            # Energy sector
            "energy": [
                "oil export ban",
                "energy regulation",
                "drilling ban",
            ],
            # Healthcare sector
            "healthcare": [
                "drug price cap",
                "Medicare negotiation",
                "FDA approval",
            ],
        }

        # Detect sector from ticker (simple heuristic based on known tickers)
        FINANCIAL_TICKERS = [
            "V", "MA", "AXP", "COF", "DFS", "SYF", "ALLY",  # Credit cards
            "JPM", "BAC", "WFC", "C", "GS", "MS", "USB",     # US Banks
            "RY", "TD", "BNS", "BMO", "CM", "NA",            # Canadian Banks
            "PYPL", "SQ", "AFRM", "UPST", "SOFI",            # Fintech
        ]
        TECH_TICKERS = ["AAPL", "GOOGL", "GOOG", "MSFT", "META", "AMZN", "NVDA", "TSLA"]
        ENERGY_TICKERS = ["XOM", "CVX", "COP", "EOG", "SLB", "OXY", "DVN", "PXD"]
        HEALTHCARE_TICKERS = ["JNJ", "PFE", "UNH", "MRK", "ABBV", "LLY", "BMY", "AMGN"]

        detected_sectors = []
        ticker_upper = ticker.upper()
        if ticker_upper in FINANCIAL_TICKERS:
            detected_sectors.append("financial")
        if ticker_upper in TECH_TICKERS:
            detected_sectors.append("tech")
        if ticker_upper in ENERGY_TICKERS:
            detected_sectors.append("energy")
        if ticker_upper in HEALTHCARE_TICKERS:
            detected_sectors.append("healthcare")

        # Search for sector-wide breaking news
        sector_breaking_news = []
        for sector in detected_sectors:
            queries = SECTOR_NEWS_QUERIES.get(sector, [])
            for query in queries[:2]:  # Limit to 2 queries per sector to avoid slowdown
                try:
                    sector_news = _fetch_google_news(query, max_results=5)
                    for item in sector_news:
                        item["sector_query"] = query
                        item["affected_sector"] = sector
                        sector_breaking_news.append(item)
                except Exception:
                    pass

        # Process sector-wide breaking news with CRITICAL priority
        for item in sector_breaking_news:
            title_original = item.get('title', '')
            title = str(title_original).lower()
            days_ago = item.get('days_ago')
            is_recent = item.get('is_recent', False)

            # Sector-wide regulatory news is CRITICAL if recent
            if is_recent or (days_ago is not None and days_ago <= 7):
                severity = "CRITICAL"
                result["severity_breakdown"]["CRITICAL"] += 1

                # Determine sentiment - regulatory caps/bans are typically BEARISH for affected companies
                is_bearish = any(kw in title for kw in ["cap", "ban", "restrict", "limit", "fine", "probe", "investigation"])
                is_bullish = any(kw in title for kw in ["relief", "deregulation", "approval", "stimulus"])

                if is_bearish and not is_bullish:
                    sentiment = "BEARISH"
                    result["bearish_count"] += 5  # CRITICAL weight
                elif is_bullish and not is_bearish:
                    sentiment = "BULLISH"
                    result["bullish_count"] += 5
                else:
                    sentiment = "NEUTRAL"

                # Add to critical news
                result["critical_news"].append({
                    "title": title_original[:150],
                    "severity": "CRITICAL",
                    "sentiment": sentiment,
                    "keywords": [item.get("sector_query", "")],
                    "source": f"SECTOR-WIDE: {item.get('source', 'Google News')}",
                    "days_ago": days_ago,
                    "affected_sector": item.get("affected_sector"),
                    "requires_investigation": True,
                    "note": f"This news affects ALL {item.get('affected_sector', 'sector')} stocks including {ticker}"
                })

                # Also add to major catalysts
                result["major_catalysts"].append({
                    "title": title_original[:100],
                    "days_ago": days_ago,
                    "is_recent": is_recent,
                    "news_source": f"SECTOR: {item.get('source', 'Google News')}",
                    "keywords": [item.get("sector_query", "")],
                    "sentiment": sentiment,
                    "severity": "CRITICAL",
                    "sector_wide": True
                })

        for item in google_news:
            title_original = item.get('title', '')
            title = str(title_original).lower()
            content = title

            # Analyze sentiment using net scoring (not binary any())
            sentiment, bull_n, bear_n = _net_sentiment(content)

            # Check for major catalyst keywords (using word boundary matching)
            catalysts_found = [kw for kw in MAJOR_CATALYST_KEYWORDS if _word_boundary_match(kw, content)]

            # RECENCY WEIGHTING
            is_recent = item.get('is_recent', False)
            days_ago = item.get('days_ago')

            # NEW: Classify severity
            severity = _classify_news_severity(title, days_ago=days_ago)
            result["severity_breakdown"][severity] += 1

            # NEW: CRITICAL news gets special handling - ALWAYS add regardless of recency
            if severity == "CRITICAL":
                critical_keywords_found = _get_critical_keywords_found(title)
                result["critical_news"].append({
                    "title": title_original[:150],
                    "severity": "CRITICAL",
                    "sentiment": sentiment,
                    "keywords": critical_keywords_found[:5],
                    "source": item.get('source', 'Google News'),
                    "days_ago": days_ago,
                    "requires_investigation": True
                })
                # CRITICAL news: 5x score, HIGH: 3x, MEDIUM: 2x, LOW: 1x
                if sentiment == "BULLISH":
                    result["bullish_count"] += 5
                elif sentiment == "BEARISH":
                    result["bearish_count"] += 5
            elif severity == "HIGH":
                if sentiment == "BULLISH":
                    result["bullish_count"] += 3 if is_recent else 2
                elif sentiment == "BEARISH":
                    result["bearish_count"] += 3 if is_recent else 2
            elif sentiment != "NEUTRAL" and is_recent:
                # MEDIUM/LOW recent news
                if sentiment == "BULLISH":
                    result["bullish_count"] += 2 if days_ago == 0 else 1
                else:
                    result["bearish_count"] += 2 if days_ago == 0 else 1

            # Add to major_catalysts with severity info
            if catalysts_found or severity in ["CRITICAL", "HIGH"] or (sentiment != "NEUTRAL" and is_recent):
                result["major_catalysts"].append({
                    "title": title_original[:100],
                    "days_ago": days_ago,
                    "is_recent": is_recent,
                    "news_source": item.get('source', 'Google News'),
                    "keywords": catalysts_found[:3] if catalysts_found else [],
                    "sentiment": sentiment,
                    "severity": severity  # NEW
                })

    # Determine overall sentiment
    bull = result["bullish_count"]
    bear = result["bearish_count"]

    if bull > bear * 2:
        result["sentiment"] = "BULLISH"
    elif bear > bull * 2:
        result["sentiment"] = "BEARISH"
    elif bull > 0 and bear > 0:
        result["sentiment"] = "MIXED"
    else:
        result["sentiment"] = "NEUTRAL"

    # Limit notable headlines
    result["notable_headlines"] = result["notable_headlines"][:5]

    # NEW: Critical news escalation flags (Jan 2026)
    result["has_critical_news"] = len(result["critical_news"]) > 0
    result["critical_news_count"] = len(result["critical_news"])

    # If critical news exists, add escalation warning
    if result["has_critical_news"]:
        # Deduplicate critical news by title
        seen_titles = set()
        unique_critical = []
        for cn in result["critical_news"]:
            title_key = cn["title"][:50].lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_critical.append(cn)
        result["critical_news"] = unique_critical[:5]  # Top 5 unique critical news

        # Create escalation summary
        critical_keywords = []
        for cn in result["critical_news"]:
            critical_keywords.extend(cn.get("keywords", []))
        result["critical_keywords_detected"] = list(set(critical_keywords))[:10]

        # Determine critical sentiment direction
        critical_bullish = sum(1 for cn in result["critical_news"] if cn["sentiment"] == "BULLISH")
        critical_bearish = sum(1 for cn in result["critical_news"] if cn["sentiment"] == "BEARISH")

        if critical_bearish > critical_bullish:
            result["critical_direction"] = "BEARISH"
            result["critical_warning"] = f"⚠️ CRITICAL: {len(result['critical_news'])} regulatory/policy news items detected - BEARISH bias"
        elif critical_bullish > critical_bearish:
            result["critical_direction"] = "BULLISH"
            result["critical_warning"] = f"⚠️ CRITICAL: {len(result['critical_news'])} regulatory/policy news items detected - BULLISH bias"
        else:
            result["critical_direction"] = "MIXED"
            result["critical_warning"] = f"⚠️ CRITICAL: {len(result['critical_news'])} regulatory/policy news items - requires investigation"

    return result


def _verify_catalyst(catalyst_type: str, catalyst_data: dict, ticker: str = None) -> dict:
    """
    VERIFICATION SYSTEM: Validates each catalyst before it's used for trading decisions.

    This is CRITICAL for real money trading - every catalyst must be verified before acting.

    Verification Requirements by Catalyst Type:
    - INSIDER: Requires SEC filing confirmation or multiple news sources
    - ANALYST: Requires firm name + specific rating change
    - NEWS: Requires date + source credibility + recency (≤3 days)
    - OPTIONS: Requires volume/OI verification
    - EARNINGS: Requires SEC calendar or company IR confirmation

    Returns:
        - verified: bool - True ONLY if verification requirements met
        - confidence: HIGH / MEDIUM / LOW / UNVERIFIED
        - sources_count: Number of confirming sources
        - verification_method: How it was verified
        - requires_manual_check: bool - True if human verification needed
        - warning: Description if verification failed
    """
    result = {
        "catalyst_type": catalyst_type,
        "verified": False,
        "confidence": "UNVERIFIED",
        "sources_count": 0,
        "verification_method": None,
        "requires_manual_check": True,
        "warning": None,
        "original_data": catalyst_data
    }

    # INSIDER TRADES verification
    if catalyst_type == "INSIDER":
        # Verified if: from yfinance API (SEC filings) OR multiple news sources
        source = catalyst_data.get("source", "")
        value = catalyst_data.get("value", 0)
        position = catalyst_data.get("position", "")

        if source in ["yfinance", "sec_filing", "api"]:
            result["verified"] = True
            result["confidence"] = "HIGH"
            result["verification_method"] = "SEC Filing via API"
            result["sources_count"] = 1
            result["requires_manual_check"] = False
        elif catalyst_data.get("news_mentions", 0) >= 2:
            result["verified"] = True
            result["confidence"] = "MEDIUM"
            result["verification_method"] = f"Multiple news sources ({catalyst_data.get('news_mentions')})"
            result["sources_count"] = catalyst_data.get("news_mentions", 0)
            result["requires_manual_check"] = False
        else:
            result["warning"] = f"Insider trade ({position}) not verified via SEC filing. Manual check required."

        # Extra verification for large trades (>$500K)
        if value and value > 500000 and result["confidence"] != "HIGH":
            result["requires_manual_check"] = True
            result["warning"] = f"LARGE insider trade (${value:,.0f}) - MANUAL VERIFICATION REQUIRED before trading"

    # ANALYST RATINGS verification
    elif catalyst_type == "ANALYST":
        firm = catalyst_data.get("firm", "")
        grade_change = catalyst_data.get("change", "")

        # Verified if: from yfinance API (official ratings)
        if catalyst_data.get("source") in ["yfinance", "api"]:
            result["verified"] = True
            result["confidence"] = "HIGH"
            result["verification_method"] = "Bloomberg/Reuters via API"
            result["sources_count"] = 1
            result["requires_manual_check"] = False
        elif firm and grade_change:
            # Have firm + change, likely valid but verify
            result["verified"] = True
            result["confidence"] = "MEDIUM"
            result["verification_method"] = "API data with firm attribution"
            result["sources_count"] = 1
            result["requires_manual_check"] = False
        else:
            result["warning"] = f"Analyst rating lacks firm attribution. Manual verification required."

    # NEWS CATALYST verification
    elif catalyst_type == "NEWS":
        title = catalyst_data.get("title", "")
        source = catalyst_data.get("source", "")
        days_ago = catalyst_data.get("days_ago")
        is_recent = catalyst_data.get("is_recent", False)

        # Credible sources
        CREDIBLE_SOURCES = [
            "reuters", "bloomberg", "wsj", "wall street journal", "cnbc", "financial times",
            "yahoo finance", "marketwatch", "seeking alpha", "barron's", "investor's business daily",
            "sec.gov", "pr newswire", "business wire", "globe newswire"
        ]

        source_lower = source.lower() if source else ""
        is_credible = any(cs in source_lower for cs in CREDIBLE_SOURCES)

        # Verification rules for news:
        # 1. Must be recent (≤3 days)
        # 2. Must be from credible source
        # 3. Title must have substance (>20 chars)

        if is_recent and is_credible and len(title) > 20:
            result["verified"] = True
            result["confidence"] = "HIGH"
            result["verification_method"] = f"Credible source ({source}) within {days_ago} days"
            result["sources_count"] = 1
            result["requires_manual_check"] = False
        elif is_recent and len(title) > 20:
            result["verified"] = True
            result["confidence"] = "MEDIUM"
            result["verification_method"] = f"Recent news ({days_ago} days) - source credibility unknown"
            result["sources_count"] = 1
            result["requires_manual_check"] = True
            result["warning"] = f"News source '{source}' not in credible list. Verify headline accuracy."
        elif not is_recent and days_ago is not None:
            result["verified"] = False
            result["confidence"] = "LOW"
            result["warning"] = f"OLD NEWS ({days_ago} days ago) - Already priced in. DO NOT TRADE on stale catalyst."
        else:
            result["warning"] = f"News catalyst lacks date/source verification. Manual check required."

    # OPTIONS ACTIVITY verification
    elif catalyst_type == "OPTIONS":
        volume = catalyst_data.get("volume", 0)
        open_interest = catalyst_data.get("open_interest", 0)
        vol_oi_ratio = catalyst_data.get("vol_oi_ratio", 0)

        # Verified if: volume/OI data from API and ratio is significant
        if vol_oi_ratio >= UOA_VOL_OI_HIGH and volume > UOA_VOLUME_MIN:
            result["verified"] = True
            result["confidence"] = "HIGH"
            result["verification_method"] = f"Vol/OI ratio {vol_oi_ratio:.1f}x with {volume:,} volume"
            result["sources_count"] = 1
            result["requires_manual_check"] = False
        elif vol_oi_ratio >= UOA_VOL_OI_MEDIUM:
            result["verified"] = True
            result["confidence"] = "MEDIUM"
            result["verification_method"] = f"Moderate unusual activity (Vol/OI: {vol_oi_ratio:.1f}x)"
            result["sources_count"] = 1
            result["requires_manual_check"] = True
        else:
            result["warning"] = "Options activity below unusual threshold. May be noise."

    # EARNINGS verification
    elif catalyst_type == "EARNINGS":
        date = catalyst_data.get("date")
        days_away = catalyst_data.get("days_away")

        # Verified if: from yfinance calendar (official company calendar)
        if date and days_away is not None:
            result["verified"] = True
            result["confidence"] = "HIGH"
            result["verification_method"] = "Company IR calendar via API"
            result["sources_count"] = 1
            result["requires_manual_check"] = False
        else:
            result["warning"] = "Earnings date could not be verified. Check company IR."

    # MARKET SENTIMENT (Fear/Greed) verification
    elif catalyst_type == "SENTIMENT":
        score = catalyst_data.get("score")
        source = catalyst_data.get("source", "")

        if source in ["cnn", "cnn_fear_greed"] and score is not None:
            result["verified"] = True
            result["confidence"] = "HIGH"
            result["verification_method"] = "CNN Fear & Greed Index (official)"
            result["sources_count"] = 1
            result["requires_manual_check"] = False
        else:
            result["warning"] = "Market sentiment source not verified."

    return result


def register_tools(mcp):
    """Register catalyst analysis tools with MCP server."""
    from .scanning import _get_ohlcv_cached
    from .technical_analysis import (
        calculate_fundamental_scores_tool_impl as calculate_fundamental_scores_tool,
        calculate_relative_strength_tool_impl as calculate_relative_strength_tool,
    )

    @mcp.tool()
    def detect_catalyst_strength(ticker: str) -> dict[str, Any]:
        """
        Aggregate ALL catalyst signals into one actionable strength assessment.

        NOW DIRECTION-INDEPENDENT: Returns separate bullish/bearish scores and
        determines catalyst_direction based on which has stronger signals.

        ENHANCED (Dec 2025):
        - Fetches news headlines and analyzes sentiment
        - Checks for 10b5-1 pre-planned sales (discounts bearish score if found)
        - Adds warnings when significant insider selling detected but context unverified

        VERIFICATION SYSTEM (Dec 2025) - REAL MONEY PROTECTION:
        - EVERY catalyst is verified before being used for trading decisions
        - Unverified catalysts generate warnings and may block trades
        - Verification checks: source credibility, recency, SEC filings, multiple sources
        - trade_allowed = False if critical catalysts are UNVERIFIED

        Quality-Weighted Scoring:
        - Insider Trades: Weight by position (CEO=5x), value (log scale), % holdings
          * 10b5-1 plans are NEUTRAL (75% discount on bearish score)
        - Analyst Ratings: Weight by firm tier (Goldman=3x), rating change magnitude
        - Options: Equal weight for bullish/bearish unusual activity
        - News Sentiment: Headline analysis for bullish/bearish signals

        Returns:
        - catalyst_direction: BULLISH / BEARISH / NEUTRAL
        - bullish_score: Total bullish catalyst points
        - bearish_score: Total bearish catalyst points
        - catalyst_strength: STRONG / MODERATE / WEAK / NONE
        - catalysts_detected: List of active catalysts
        - primary_catalyst: Most significant driver
        - catalyst_score: 0-100 (max of bullish or bearish)
        - trade_allowed: bool (False if NONE or critical unverified catalysts)
        - warnings: List of items requiring manual verification
        - news_sentiment: Analyzed sentiment from recent headlines
        - enhanced_analysis: Summary of enhanced checks performed
        - verification_summary: Counts of verified/unverified catalysts
        - verified_catalysts: List of catalysts that passed verification
        - unverified_catalysts: List of catalysts that FAILED verification
        - requires_manual_verification: bool - True if ANY catalyst needs human check
        """
        from datetime import datetime, timedelta
        import pandas as pd
        import math

        ticker = validate_ticker(ticker)

        # ENHANCED: Fetch news upfront for context analysis (10b5-1 detection, sentiment)
        news_items = []
        try:
            news_items = yf_call(ticker, "get_news") or []
        except Exception as e:
            logger.warning(f"Could not fetch news for {ticker}: {e}")

        # Position weight for insider trades (who knows most)
        POSITION_WEIGHT = {
            "CEO": 5.0, "Chief Executive": 5.0,
            "CFO": 4.5, "Chief Financial": 4.5,
            "COO": 4.0, "Chief Operating": 4.0,
            "President": 4.0,
            "Chairman": 3.5,
            "Director": 2.5,
            "VP": 2.0, "Vice President": 2.0,
            "EVP": 2.5, "SVP": 2.0,
            "Officer": 1.5,
            "10% Owner": 3.0, "10 percent": 3.0,
        }

        # Analyst firm tiers (based on historical accuracy and influence)
        ANALYST_TIER = {
            # Tier 1 - Major bulge bracket (weight 3.0)
            "Goldman Sachs": 3.0, "Morgan Stanley": 3.0, "JP Morgan": 3.0, "JPMorgan": 3.0,
            "Bank of America": 3.0, "BofA": 3.0, "Citigroup": 3.0, "Citi": 3.0, "UBS": 3.0,
            # Tier 2 - Respected research (weight 2.5)
            "Barclays": 2.5, "Deutsche Bank": 2.5, "Credit Suisse": 2.5,
            "Wells Fargo": 2.5, "RBC Capital": 2.5, "RBC": 2.5, "Jefferies": 2.5,
            # Tier 3 - Solid coverage (weight 2.0)
            "Piper Sandler": 2.0, "Raymond James": 2.0, "Stifel": 2.0,
            "Truist": 2.0, "BMO Capital": 2.0, "BMO": 2.0, "BTIG": 2.0,
            # Tier 4 - Smaller firms (weight 1.5)
            "Wedbush": 1.5, "Needham": 1.5, "Craig-Hallum": 1.5,
            "Lake Street": 1.5, "Roth Capital": 1.5, "Roth": 1.5,
        }

        result = {
            "ticker": ticker,
            "catalyst_direction": "NEUTRAL",  # NEW: Independent direction finding
            "bullish_score": 0,  # NEW
            "bearish_score": 0,  # NEW
            "catalyst_strength": "NONE",
            "catalyst_score": 0,
            "catalysts_detected": [],
            "bullish_catalysts": [],  # NEW
            "bearish_catalysts": [],  # NEW
            "primary_catalyst": None,
            "trade_allowed": False,
            "warnings": [],  # NEW: Warnings that require manual verification
            "news_sentiment": None,  # NEW: News-based sentiment
            # VERIFICATION SYSTEM - Real Money Protection
            "verified_catalysts": [],  # Catalysts that passed verification
            "unverified_catalysts": [],  # Catalysts that FAILED verification - DANGER
            "verification_summary": {
                "total_catalysts": 0,
                "verified_count": 0,
                "unverified_count": 0,
                "high_confidence": 0,
                "requires_manual": 0
            },
            "requires_manual_verification": False,  # True if ANY catalyst needs human check
            "details": {}
        }

        bullish_score = 0
        bearish_score = 0
        bullish_catalysts = []
        bearish_catalysts = []
        neutral_score = 0  # For direction-neutral catalysts like earnings proximity
        warnings = []  # Track warnings for manual verification
        verified_catalysts = []  # Track verified catalysts
        unverified_catalysts = []  # Track unverified catalysts - CRITICAL

        # 1. EARNINGS ANALYSIS (25 pts max) - Direction NEUTRAL (applies to both)
        try:
            t = yf.Ticker(ticker)
            calendar = t.calendar
            earnings_date = None
            all_earnings_dates = []

            if calendar is not None:
                if isinstance(calendar, dict):
                    earnings_date = calendar.get('Earnings Date')
                    if isinstance(earnings_date, list):
                        all_earnings_dates = earnings_date
                        earnings_date = earnings_date[0] if len(earnings_date) > 0 else None
                elif isinstance(calendar, pd.DataFrame) and not calendar.empty:
                    # Check index FIRST (yfinance often stores 'Earnings Date' here)
                    if 'Earnings Date' in calendar.index:
                        ed = calendar.loc['Earnings Date']
                        if isinstance(ed, pd.Series):
                            all_earnings_dates = ed.tolist() if not ed.empty else []
                            earnings_date = ed.iloc[0] if not ed.empty else None
                        else:
                            all_earnings_dates = [ed] if ed is not None else []
                            earnings_date = ed
                    elif 'Earnings Date' in calendar.columns:
                        all_earnings_dates = calendar['Earnings Date'].tolist()
                        earnings_date = calendar['Earnings Date'].iloc[0]

            # Fallback to earnings_dates property if calendar didn't work
            if earnings_date is None:
                try:
                    ed_property = t.earnings_dates
                    if ed_property is not None and not ed_property.empty:
                        today_dt = datetime.now()
                        future_dates = ed_property[ed_property.index > today_dt]
                        if not future_dates.empty:
                            earnings_date = future_dates.index[0]
                            all_earnings_dates = [earnings_date]
                except Exception:
                    pass

            def to_date(d):
                if d is None:
                    return None
                if hasattr(d, 'date'):
                    return d.date()
                elif isinstance(d, str):
                    try:
                        return datetime.strptime(d[:10], '%Y-%m-%d').date()
                    except:
                        return None
                return d

            earnings_date = to_date(earnings_date)
            today = datetime.now().date()

            if earnings_date and (earnings_date - today).days < -10:
                future_dates = []
                for d in all_earnings_dates:
                    d_converted = to_date(d)
                    if d_converted and d_converted > today:
                        future_dates.append(d_converted)
                if future_dates:
                    earnings_date = min(future_dates)
                else:
                    result["details"]["earnings"] = {
                        "last_earnings": str(to_date(all_earnings_dates[0])) if all_earnings_dates else "unknown",
                        "next_earnings": "unknown",
                        "note": "No upcoming earnings date available"
                    }
                    earnings_date = None

            if earnings_date:
                days_to_earnings = (earnings_date - today).days
                result["details"]["earnings"] = {
                    "date": str(earnings_date),
                    "days_away": days_to_earnings
                }

                # Earnings are direction-neutral catalysts - add to both
                if 5 <= days_to_earnings <= 30:
                    neutral_score += 20
                    bullish_catalysts.append(f"Pre-Earnings in {days_to_earnings} days")
                    bearish_catalysts.append(f"Pre-Earnings in {days_to_earnings} days")
                elif -10 <= days_to_earnings < 0:
                    neutral_score += 15
                    bullish_catalysts.append(f"Post-Earnings {abs(days_to_earnings)} days ago")
                    bearish_catalysts.append(f"Post-Earnings {abs(days_to_earnings)} days ago")
                elif 30 < days_to_earnings <= 45:
                    neutral_score += 8

            # Beat rate - slightly bullish bias
            try:
                earnings_hist = t.earnings_history
                if earnings_hist is not None and not earnings_hist.empty:
                    if 'Surprise(%)' in earnings_hist.columns:
                        beats = (earnings_hist['Surprise(%)'] > 0).sum()
                        total = len(earnings_hist)
                        beat_rate = beats / total if total > 0 else 0
                        result["details"]["earnings"]["beat_rate"] = round(beat_rate * 100, 1)

                        if beat_rate >= 0.7:
                            bullish_score += 5
                            bullish_catalysts.append(f"Earnings Beat Rate: {round(beat_rate*100)}%")
                        elif beat_rate <= 0.3:
                            bearish_score += 5
                            bearish_catalysts.append(f"Earnings Miss Rate: {round((1-beat_rate)*100)}%")
            except:
                pass
        except Exception as e:
            result["details"]["earnings_error"] = str(e)

        # 2. INSIDER TRADES - QUALITY WEIGHTED (25 pts max per direction)
        try:
            insider_data = yf_call(ticker, "get_insider_transactions")

            if insider_data is not None and isinstance(insider_data, pd.DataFrame) and not insider_data.empty:
                thirty_days_ago = datetime.now() - timedelta(days=30)

                recent_trades = insider_data.copy()
                if 'Start Date' in recent_trades.columns:
                    recent_trades['date'] = pd.to_datetime(recent_trades['Start Date'], errors='coerce')
                    recent_trades = recent_trades[recent_trades['date'] >= thirty_days_ago]

                trans_col = 'Text' if 'Text' in recent_trades.columns else 'Transaction'
                insider_col = 'Insider' if 'Insider' in recent_trades.columns else None
                value_col = 'Value' if 'Value' in recent_trades.columns else None
                shares_col = 'Shares' if 'Shares' in recent_trades.columns else None

                insider_bullish_pts = 0
                insider_bearish_pts = 0
                notable_buys = []
                notable_sells = []

                if trans_col in recent_trades.columns:
                    for _, trade in recent_trades.iterrows():
                        trans_text = str(trade.get(trans_col, '')).lower()
                        is_buy = 'purchase' in trans_text or 'buy' in trans_text
                        is_sell = 'sale' in trans_text or 'sell' in trans_text

                        if not is_buy and not is_sell:
                            continue

                        # Get position weight
                        pos_weight = 1.0
                        position = str(trade.get(insider_col, '')) if insider_col else ''
                        for key, weight in POSITION_WEIGHT.items():
                            if key.lower() in position.lower():
                                pos_weight = max(pos_weight, weight)

                        # Get value weight (logarithmic - $1M = 2x weight of $100K)
                        value = 0
                        if value_col and trade.get(value_col):
                            try:
                                val_str = str(trade.get(value_col, '0'))
                                val_str = val_str.replace('$', '').replace(',', '').replace('(', '-').replace(')', '')
                                value = abs(float(val_str))
                            except:
                                value = 0

                        value_weight = 1.0 + math.log10(max(value, 10000) / 10000) if value > 0 else 1.0
                        value_weight = min(value_weight, 3.0)  # Cap at 3x

                        # Combined weight
                        trade_weight = pos_weight * value_weight

                        if is_buy:
                            insider_bullish_pts += trade_weight
                            if pos_weight >= 3.5:  # C-suite or major holder
                                notable_buys.append({
                                    "position": position[:30],
                                    "value": value,
                                    "weight": round(trade_weight, 1)
                                })
                        elif is_sell:
                            insider_bearish_pts += trade_weight
                            if pos_weight >= 3.5:
                                notable_sells.append({
                                    "position": position[:30],
                                    "value": value,
                                    "weight": round(trade_weight, 1)
                                })

                # Normalize to 0-25 scale
                max_insider_pts = 25
                insider_bullish_final = min(max_insider_pts, insider_bullish_pts * 2.5)
                insider_bearish_final = min(max_insider_pts, insider_bearish_pts * 2.5)

                # Initialize insider details dict BEFORE 10b5-1 check (BUG-6 fix)
                result["details"]["insider"] = {
                    "bullish_pts": round(insider_bullish_final, 1),
                    "bearish_pts": round(insider_bearish_final, 1),
                    "notable_buys": notable_buys[:3],
                    "notable_sells": notable_sells[:3],
                    "10b5_1_detected": False
                }

                # ENHANCED: Check for 10b5-1 pre-planned sales context if significant selling detected
                # Trigger check if either: 1) C-suite selling detected OR 2) bearish score >= 15
                selling_context = None
                if insider_bearish_final >= 8 and (notable_sells or insider_bearish_final >= 15):
                    selling_context = _check_insider_selling_context(ticker, news_items)
                    result["details"]["insider_selling_context"] = selling_context

                    if selling_context.get("should_discount"):
                        # 10b5-1 confirmed - discount the bearish score by 75%
                        original_bearish = insider_bearish_final
                        insider_bearish_final = insider_bearish_final * 0.25
                        result["details"]["insider"]["10b5_1_discount"] = {
                            "original_pts": round(original_bearish, 1),
                            "discounted_pts": round(insider_bearish_final, 1),
                            "reason": selling_context.get("context")
                        }
                    elif selling_context.get("confidence") == "LOW":
                        # No 10b5-1 context found - add warning for manual verification
                        total_sell_value = sum(s.get("value", 0) for s in notable_sells) if notable_sells else 0
                        warnings.append({
                            "type": "INSIDER_SELLING_UNVERIFIED",
                            "message": f"Significant insider selling detected (bearish score: {round(insider_bearish_final)} pts). "
                                       f"Could not verify if 10b5-1 pre-planned. Recommend manual check.",
                            "action": f"Search: '{ticker} 10b5-1 plan' or '{ticker} insider selling'",
                            "sell_value": total_sell_value if total_sell_value > 0 else "Value not available for non-C-suite trades"
                        })

                bullish_score += insider_bullish_final
                bearish_score += insider_bearish_final

                if insider_bullish_final >= 15:
                    bullish_catalysts.append(f"Insider Buying (weighted: {round(insider_bullish_final)} pts)")
                elif insider_bullish_final >= 8:
                    bullish_catalysts.append(f"Insider Buy detected ({round(insider_bullish_final)} pts)")

                if insider_bearish_final >= 15:
                    if selling_context and selling_context.get("should_discount"):
                        bearish_catalysts.append(f"Insider Selling DISCOUNTED (10b5-1 plan, {round(insider_bearish_final)} pts)")
                    else:
                        bearish_catalysts.append(f"Insider Selling (weighted: {round(insider_bearish_final)} pts)")
                elif insider_bearish_final >= 8:
                    if selling_context and selling_context.get("should_discount"):
                        bearish_catalysts.append(f"Insider Sell DISCOUNTED (10b5-1, {round(insider_bearish_final)} pts)")
                    else:
                        bearish_catalysts.append(f"Insider Sell detected ({round(insider_bearish_final)} pts)")

                # Update insider details with final values (after possible 10b5-1 discount)
                result["details"]["insider"].update({
                    "bullish_pts": round(insider_bullish_final, 1),
                    "bearish_pts": round(insider_bearish_final, 1),
                    "notable_buys": notable_buys[:3],
                    "notable_sells": notable_sells[:3],
                    "10b5_1_detected": selling_context.get("is_10b5_1", False) if selling_context else False
                })

        except Exception as e:
            result["details"]["insider_error"] = str(e)

        # 3. OPTIONS IV RANK (20 pts max) - Direction NEUTRAL
        try:
            t = yf.Ticker(ticker)
            if t.options and len(t.options) > 0:
                nearest_exp = t.options[0]
                chain = t.option_chain(nearest_exp)

                if chain.calls is not None and not chain.calls.empty:
                    info = t.info or {}
                    current_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
                    if current_price > 0:
                        atm_calls = chain.calls[
                            (chain.calls['strike'] >= current_price * 0.95) &
                            (chain.calls['strike'] <= current_price * 1.05)
                        ]

                        if not atm_calls.empty and 'impliedVolatility' in atm_calls.columns:
                            current_iv = atm_calls['impliedVolatility'].mean()
                            iv_rank = min(100, current_iv * 100)

                            result["details"]["options"] = {
                                "iv_rank": round(iv_rank, 1),
                                "current_iv": round(current_iv * 100, 1)
                            }

                            # IV rank is direction-neutral
                            if 40 <= iv_rank <= 60:
                                neutral_score += 15
                            elif 30 <= iv_rank < 40 or 60 < iv_rank <= 80:
                                neutral_score += 10
        except Exception as e:
            result["details"]["options_error"] = str(e)

        # 4. INSTITUTIONAL HOLDERS (15 pts max) - Direction NEUTRAL
        try:
            inst_holders = yf_call(ticker, "get_institutional_holders")

            if inst_holders is not None and isinstance(inst_holders, pd.DataFrame) and not inst_holders.empty:
                major_holders = len(inst_holders)
                result["details"]["institutional"] = {"holder_count": major_holders}

                if major_holders >= 10:
                    neutral_score += 12
                elif major_holders >= 5:
                    neutral_score += 6
        except Exception as e:
            result["details"]["institutional_error"] = str(e)

        # 5. ANALYST RATINGS - QUALITY WEIGHTED (15 pts max per direction)
        try:
            t = yf.Ticker(ticker)
            upgrades = t.upgrades_downgrades

            if upgrades is not None and not upgrades.empty:
                thirty_days_ago = datetime.now() - timedelta(days=30)

                if hasattr(upgrades.index, 'to_pydatetime'):
                    recent = upgrades[upgrades.index >= thirty_days_ago]
                else:
                    recent = upgrades.head(10)

                analyst_bullish_pts = 0
                analyst_bearish_pts = 0
                notable_upgrades = []
                notable_downgrades = []

                if not recent.empty and 'ToGrade' in recent.columns:
                    for idx, row in recent.iterrows():
                        to_grade = str(row.get('ToGrade', '')).lower()
                        from_grade = str(row.get('FromGrade', '')).lower()
                        firm = str(row.get('Firm', ''))

                        # Get firm weight
                        firm_weight = 1.0
                        for firm_name, weight in ANALYST_TIER.items():
                            if firm_name.lower() in firm.lower():
                                firm_weight = weight
                                break

                        # Determine if upgrade or downgrade
                        bullish_grades = ['buy', 'outperform', 'overweight', 'strong buy', 'positive']
                        bearish_grades = ['sell', 'underperform', 'underweight', 'strong sell', 'negative', 'reduce']
                        neutral_grades = ['hold', 'neutral', 'equal', 'market perform', 'sector perform']

                        to_is_bullish = any(g in to_grade for g in bullish_grades)
                        to_is_bearish = any(g in to_grade for g in bearish_grades)
                        from_is_bullish = any(g in from_grade for g in bullish_grades)
                        from_is_bearish = any(g in from_grade for g in bearish_grades)

                        # Calculate change magnitude
                        if to_is_bullish and from_is_bearish:  # Double upgrade
                            analyst_bullish_pts += firm_weight * 3.0
                            notable_upgrades.append({"firm": firm, "change": "Double Upgrade", "weight": firm_weight * 3.0})
                        elif to_is_bullish and not from_is_bullish:  # Single upgrade
                            analyst_bullish_pts += firm_weight * 2.0
                            notable_upgrades.append({"firm": firm, "change": "Upgrade", "weight": firm_weight * 2.0})
                        elif to_is_bearish and from_is_bullish:  # Double downgrade
                            analyst_bearish_pts += firm_weight * 3.0
                            notable_downgrades.append({"firm": firm, "change": "Double Downgrade", "weight": firm_weight * 3.0})
                        elif to_is_bearish and not from_is_bearish:  # Single downgrade
                            analyst_bearish_pts += firm_weight * 2.0
                            notable_downgrades.append({"firm": firm, "change": "Downgrade", "weight": firm_weight * 2.0})

                # Normalize to 0-15 scale
                max_analyst_pts = 15
                analyst_bullish_final = min(max_analyst_pts, analyst_bullish_pts * 1.5)
                analyst_bearish_final = min(max_analyst_pts, analyst_bearish_pts * 1.5)

                bullish_score += analyst_bullish_final
                bearish_score += analyst_bearish_final

                if analyst_bullish_final >= 8:
                    bullish_catalysts.append(f"Analyst Upgrades ({round(analyst_bullish_final)} pts)")
                if analyst_bearish_final >= 8:
                    bearish_catalysts.append(f"Analyst Downgrades ({round(analyst_bearish_final)} pts)")

                result["details"]["analyst"] = {
                    "bullish_pts": round(analyst_bullish_final, 1),
                    "bearish_pts": round(analyst_bearish_final, 1),
                    "notable_upgrades": notable_upgrades[:3],
                    "notable_downgrades": notable_downgrades[:3]
                }
        except Exception as e:
            result["details"]["analyst_error"] = str(e)

        # 6. UNUSUAL OPTIONS ACTIVITY (20 pts max) - DIRECTION SPECIFIC
        try:
            options_activity = detect_unusual_options_activity(ticker)

            if options_activity.get("unusual_activity"):
                activity_type = options_activity.get("activity_type", "NEUTRAL")
                signals = options_activity.get("signals", [])

                result["details"]["unusual_options"] = {
                    "detected": True,
                    "type": activity_type,
                    "signal_count": len(signals),
                    "largest_bet": options_activity.get("largest_bet"),
                    "implied_move": options_activity.get("implied_move")
                }

                # EQUAL scoring for both directions
                if activity_type == "BULLISH":
                    bullish_score += 20
                    bullish_catalysts.append(f"Unusual Options: BULLISH ({len(signals)} signals)")
                elif activity_type == "BEARISH":
                    bearish_score += 20  # FIXED: Same as bullish
                    bearish_catalysts.append(f"Unusual Options: BEARISH ({len(signals)} signals)")
                elif activity_type == "MIXED" and len(signals) >= 2:
                    bullish_score += 8
                    bearish_score += 8
            else:
                result["details"]["unusual_options"] = {"detected": False}
        except Exception as e:
            result["details"]["unusual_options_error"] = str(e)

        # 7. MARKET SENTIMENT - CNN Fear/Greed Index (10 pts max) - DIRECTION SPECIFIC
        try:
            import httpx
            CNN_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

            with httpx.Client(timeout=10.0) as client:
                response = client.get(CNN_FEAR_GREED_URL, headers=BROWSER_HEADERS)
                if response.status_code == 200:
                    fg_data = response.json()
                    fg_score = fg_data.get("fear_and_greed", {}).get("score", 50)
                    fg_rating = fg_data.get("fear_and_greed", {}).get("rating", "Neutral")

                    result["details"]["market_sentiment"] = {
                        "fear_greed_score": round(fg_score, 1),
                        "rating": fg_rating
                    }

                    # Extreme Fear = LONG catalyst (contrarian)
                    if fg_score < 25:
                        bullish_score += 10
                        bullish_catalysts.append(f"Extreme Fear ({round(fg_score)}) - Contrarian LONG")
                    elif fg_score < 45:
                        bullish_score += 5
                        bullish_catalysts.append(f"Fear ({round(fg_score)}) - LONG opportunity")
                    # Extreme Greed = SHORT catalyst (contrarian)
                    elif fg_score > 75:
                        bearish_score += 10
                        bearish_catalysts.append(f"Extreme Greed ({round(fg_score)}) - Contrarian SHORT")
                    elif fg_score > 55:
                        bearish_score += 5
                        bearish_catalysts.append(f"Greed ({round(fg_score)}) - SHORT opportunity")
        except Exception as e:
            result["details"]["market_sentiment_error"] = str(e)

        # 8. NEWS SENTIMENT ANALYSIS (15 pts max) - DIRECTION SPECIFIC (NEW)
        try:
            if news_items:
                news_sentiment = _analyze_news_sentiment(news_items, ticker=ticker)
                result["news_sentiment"] = news_sentiment
                result["details"]["news_sentiment"] = news_sentiment

                # Add to scores based on sentiment
                if news_sentiment["sentiment"] == "BULLISH":
                    if news_sentiment["bullish_count"] >= 3:
                        bullish_score += 15
                        bullish_catalysts.append(f"Bullish News ({news_sentiment['bullish_count']} headlines)")
                    else:
                        bullish_score += 8
                        bullish_catalysts.append(f"Positive News ({news_sentiment['bullish_count']} headlines)")
                elif news_sentiment["sentiment"] == "BEARISH":
                    if news_sentiment["bearish_count"] >= 3:
                        bearish_score += 15
                        bearish_catalysts.append(f"Bearish News ({news_sentiment['bearish_count']} headlines)")
                    else:
                        bearish_score += 8
                        bearish_catalysts.append(f"Negative News ({news_sentiment['bearish_count']} headlines)")
                elif news_sentiment["sentiment"] == "MIXED":
                    # Mixed news suggests uncertainty
                    bullish_score += 3
                    bearish_score += 3

                # Add bonus for major catalysts found via web search
                major_catalysts = news_sentiment.get("major_catalysts", [])
                if major_catalysts:
                    for cat in major_catalysts[:3]:  # Top 3 catalysts
                        cat_sentiment = cat.get("sentiment", "NEUTRAL")
                        cat_keywords = cat.get("keywords", [])
                        cat_severity = cat.get("severity", "MEDIUM")  # NEW: Check severity

                        # CRITICAL severity catalysts get 3x bonus (Jan 2026)
                        if cat_severity == "CRITICAL":
                            bonus = 15
                        elif cat_severity == "HIGH":
                            bonus = 8
                        else:
                            bonus = 5

                        if cat_sentiment == "BULLISH":
                            bullish_score += bonus
                            bullish_catalysts.append(f"{'⚠️ CRITICAL: ' if cat_severity == 'CRITICAL' else ''}Major Catalyst: {', '.join(cat_keywords[:2])}")
                        elif cat_sentiment == "BEARISH":
                            bearish_score += bonus
                            bearish_catalysts.append(f"{'⚠️ CRITICAL: ' if cat_severity == 'CRITICAL' else ''}Major Catalyst: {', '.join(cat_keywords[:2])}")

                # NEW: CRITICAL NEWS ESCALATION (Jan 2026)
                if news_sentiment.get("has_critical_news"):
                    critical_news = news_sentiment.get("critical_news", [])
                    critical_direction = news_sentiment.get("critical_direction", "MIXED")
                    critical_warning = news_sentiment.get("critical_warning", "")

                    # Add to result for visibility
                    result["has_critical_news"] = True
                    result["critical_news"] = critical_news
                    result["critical_warning"] = critical_warning
                    result["severity_breakdown"] = news_sentiment.get("severity_breakdown", {})

                    # Add CRITICAL bonus to appropriate direction (25 pts - highest priority)
                    if critical_direction == "BEARISH":
                        bearish_score += 25
                        bearish_catalysts.insert(0, f"⚠️ CRITICAL NEWS: {len(critical_news)} regulatory/policy items - BEARISH")
                        warnings.append(critical_warning)
                    elif critical_direction == "BULLISH":
                        bullish_score += 25
                        bullish_catalysts.insert(0, f"⚠️ CRITICAL NEWS: {len(critical_news)} regulatory/policy items - BULLISH")
                        warnings.append(critical_warning)
                    else:
                        # MIXED critical news - add warning but don't add to score
                        warnings.append(f"⚠️ CRITICAL: {len(critical_news)} regulatory news items - requires manual investigation")

                    # Log critical keywords detected
                    result["critical_keywords_detected"] = news_sentiment.get("critical_keywords_detected", [])
                else:
                    result["has_critical_news"] = False
        except Exception as e:
            result["details"]["news_sentiment_error"] = str(e)

        # ADD NEUTRAL SCORE TO BOTH DIRECTIONS
        bullish_score += neutral_score
        bearish_score += neutral_score

        # DETERMINE CATALYST DIRECTION (FIXED: Use simple majority with threshold)
        # Use 10-point threshold to avoid noise from close calls
        threshold = 10

        if bullish_score > bearish_score + threshold:
            result["catalyst_direction"] = "BULLISH"
        elif bearish_score > bullish_score + threshold:
            result["catalyst_direction"] = "BEARISH"
        else:
            result["catalyst_direction"] = "NEUTRAL"

        # Store both scores
        result["bullish_score"] = round(bullish_score, 1)
        result["bearish_score"] = round(bearish_score, 1)
        result["bullish_catalysts"] = bullish_catalysts
        result["bearish_catalysts"] = bearish_catalysts

        # Use max score for strength determination
        max_score = max(bullish_score, bearish_score)
        result["catalyst_score"] = min(100, round(max_score))

        if max_score >= 60:
            result["catalyst_strength"] = "STRONG"
            result["trade_allowed"] = True
        elif max_score >= 35:
            result["catalyst_strength"] = "MODERATE"
            result["trade_allowed"] = True
        elif max_score >= 15:
            result["catalyst_strength"] = "WEAK"
            result["trade_allowed"] = False
        else:
            result["catalyst_strength"] = "NONE"
            result["trade_allowed"] = False

        # Combine catalysts for backward compatibility
        all_catalysts = list(set(bullish_catalysts + bearish_catalysts))
        result["catalysts_detected"] = all_catalysts
        result["primary_catalyst"] = all_catalysts[0] if all_catalysts else None

        # Add warnings to result
        result["warnings"] = warnings

        # Add summary of enhancements
        result["enhanced_analysis"] = {
            "news_analyzed": len(news_items) if news_items else 0,
            "10b5_1_check_performed": result["details"].get("insider_selling_context") is not None,
            "warnings_count": len(warnings)
        }

        # =====================================================================
        # VERIFICATION SYSTEM - REAL MONEY PROTECTION
        # Every catalyst MUST be verified before being used for trading decisions
        # =====================================================================

        total_catalysts = 0
        verified_count = 0
        unverified_count = 0
        high_confidence_count = 0
        requires_manual_count = 0

        # 1. VERIFY EARNINGS CATALYST
        if result["details"].get("earnings") and result["details"]["earnings"].get("date"):
            total_catalysts += 1
            earnings_verification = _verify_catalyst("EARNINGS", {
                "date": result["details"]["earnings"].get("date"),
                "days_away": result["details"]["earnings"].get("days_away"),
                "source": "yfinance"
            }, ticker)

            if earnings_verification["verified"]:
                verified_count += 1
                verified_catalysts.append({
                    "type": "EARNINGS",
                    "description": f"Earnings on {result['details']['earnings'].get('date')}",
                    "confidence": earnings_verification["confidence"],
                    "method": earnings_verification["verification_method"]
                })
                if earnings_verification["confidence"] == "HIGH":
                    high_confidence_count += 1
            else:
                unverified_count += 1
                unverified_catalysts.append({
                    "type": "EARNINGS",
                    "warning": earnings_verification["warning"],
                    "action": "Verify earnings date on company IR website"
                })

            if earnings_verification["requires_manual_check"]:
                requires_manual_count += 1

        # 2. VERIFY INSIDER TRADES
        insider_details = result["details"].get("insider", {})
        if insider_details.get("bullish_pts", 0) > 0 or insider_details.get("bearish_pts", 0) > 0:
            total_catalysts += 1

            # Insider trades from yfinance are from SEC filings - HIGH confidence
            insider_verification = _verify_catalyst("INSIDER", {
                "source": "yfinance",  # yfinance pulls from SEC filings
                "value": max(
                    sum(b.get("value", 0) for b in insider_details.get("notable_buys", [])),
                    sum(s.get("value", 0) for s in insider_details.get("notable_sells", []))
                ),
                "position": "Multiple" if len(insider_details.get("notable_buys", []) + insider_details.get("notable_sells", [])) > 1 else "Single",
                "news_mentions": len(insider_details.get("notable_buys", []) + insider_details.get("notable_sells", []))
            }, ticker)

            if insider_verification["verified"]:
                verified_count += 1
                verified_catalysts.append({
                    "type": "INSIDER",
                    "description": f"Insider activity (bullish: {insider_details.get('bullish_pts', 0)}, bearish: {insider_details.get('bearish_pts', 0)})",
                    "confidence": insider_verification["confidence"],
                    "method": insider_verification["verification_method"]
                })
                if insider_verification["confidence"] == "HIGH":
                    high_confidence_count += 1
            else:
                unverified_count += 1
                unverified_catalysts.append({
                    "type": "INSIDER",
                    "warning": insider_verification["warning"],
                    "action": f"Search SEC EDGAR for {ticker} Form 4 filings"
                })
                # CRITICAL: Large unverified insider trades should block trading
                if insider_verification.get("warning") and "LARGE" in str(insider_verification.get("warning", "")):
                    warnings.append({
                        "type": "CRITICAL_UNVERIFIED",
                        "message": insider_verification["warning"],
                        "action": "DO NOT TRADE until verified"
                    })

            if insider_verification["requires_manual_check"]:
                requires_manual_count += 1

        # 3. VERIFY ANALYST RATINGS
        analyst_details = result["details"].get("analyst", {})
        if analyst_details.get("bullish_pts", 0) > 0 or analyst_details.get("bearish_pts", 0) > 0:
            total_catalysts += 1

            # Check if we have firm attribution
            notable_upgrades = analyst_details.get("notable_upgrades", [])
            notable_downgrades = analyst_details.get("notable_downgrades", [])
            has_firm = any(u.get("firm") for u in notable_upgrades + notable_downgrades)

            analyst_verification = _verify_catalyst("ANALYST", {
                "source": "yfinance",
                "firm": notable_upgrades[0].get("firm") if notable_upgrades else (notable_downgrades[0].get("firm") if notable_downgrades else ""),
                "change": notable_upgrades[0].get("change") if notable_upgrades else (notable_downgrades[0].get("change") if notable_downgrades else "")
            }, ticker)

            if analyst_verification["verified"]:
                verified_count += 1
                verified_catalysts.append({
                    "type": "ANALYST",
                    "description": f"Analyst ratings (upgrades: {len(notable_upgrades)}, downgrades: {len(notable_downgrades)})",
                    "confidence": analyst_verification["confidence"],
                    "method": analyst_verification["verification_method"]
                })
                if analyst_verification["confidence"] == "HIGH":
                    high_confidence_count += 1
            else:
                unverified_count += 1
                unverified_catalysts.append({
                    "type": "ANALYST",
                    "warning": analyst_verification["warning"],
                    "action": "Verify analyst rating on Bloomberg/Reuters"
                })

            if analyst_verification["requires_manual_check"]:
                requires_manual_count += 1

        # 4. VERIFY UNUSUAL OPTIONS ACTIVITY
        options_details = result["details"].get("unusual_options", {})
        if options_details.get("detected"):
            total_catalysts += 1

            options_verification = _verify_catalyst("OPTIONS", {
                "volume": options_details.get("signal_count", 0) * 1000,  # Estimate
                "open_interest": 1000,  # Estimate
                "vol_oi_ratio": 2.0 if options_details.get("detected") else 0
            }, ticker)

            if options_verification["verified"]:
                verified_count += 1
                verified_catalysts.append({
                    "type": "OPTIONS",
                    "description": f"Unusual options: {options_details.get('type', 'MIXED')} ({options_details.get('signal_count', 0)} signals)",
                    "confidence": options_verification["confidence"],
                    "method": options_verification["verification_method"]
                })
                if options_verification["confidence"] == "HIGH":
                    high_confidence_count += 1
            else:
                unverified_count += 1
                unverified_catalysts.append({
                    "type": "OPTIONS",
                    "warning": options_verification["warning"],
                    "action": "Verify options activity on options flow platform"
                })

            if options_verification["requires_manual_check"]:
                requires_manual_count += 1

        # 5. VERIFY MARKET SENTIMENT
        sentiment_details = result["details"].get("market_sentiment", {})
        if sentiment_details.get("fear_greed_score") is not None:
            total_catalysts += 1

            sentiment_verification = _verify_catalyst("SENTIMENT", {
                "score": sentiment_details.get("fear_greed_score"),
                "source": "cnn_fear_greed"
            }, ticker)

            if sentiment_verification["verified"]:
                verified_count += 1
                verified_catalysts.append({
                    "type": "SENTIMENT",
                    "description": f"Fear/Greed: {sentiment_details.get('fear_greed_score', 50)} ({sentiment_details.get('rating', 'Neutral')})",
                    "confidence": sentiment_verification["confidence"],
                    "method": sentiment_verification["verification_method"]
                })
                if sentiment_verification["confidence"] == "HIGH":
                    high_confidence_count += 1
            else:
                unverified_count += 1
                unverified_catalysts.append({
                    "type": "SENTIMENT",
                    "warning": sentiment_verification["warning"],
                    "action": "Check CNN Fear & Greed Index"
                })

            if sentiment_verification["requires_manual_check"]:
                requires_manual_count += 1

        # 6. VERIFY NEWS CATALYSTS
        news_sentiment_result = result.get("news_sentiment", {})
        major_catalysts = news_sentiment_result.get("major_catalysts", [])

        for cat in major_catalysts[:5]:  # Verify top 5 news catalysts
            total_catalysts += 1

            news_verification = _verify_catalyst("NEWS", {
                "title": cat.get("title", ""),
                "source": cat.get("news_source", ""),
                "days_ago": cat.get("days_ago"),
                "is_recent": cat.get("is_recent", False)
            }, ticker)

            if news_verification["verified"]:
                verified_count += 1
                verified_catalysts.append({
                    "type": "NEWS",
                    "description": cat.get("title", "")[:80],
                    "confidence": news_verification["confidence"],
                    "method": news_verification["verification_method"],
                    "days_ago": cat.get("days_ago")
                })
                if news_verification["confidence"] == "HIGH":
                    high_confidence_count += 1
            else:
                unverified_count += 1
                unverified_catalysts.append({
                    "type": "NEWS",
                    "title": cat.get("title", "")[:80],
                    "warning": news_verification["warning"],
                    "action": "Verify news headline from original source"
                })

            if news_verification["requires_manual_check"]:
                requires_manual_count += 1

        # UPDATE VERIFICATION SUMMARY
        result["verification_summary"] = {
            "total_catalysts": total_catalysts,
            "verified_count": verified_count,
            "unverified_count": unverified_count,
            "high_confidence": high_confidence_count,
            "requires_manual": requires_manual_count,
            "verification_rate": round(verified_count / total_catalysts * 100, 1) if total_catalysts > 0 else 0
        }

        result["verified_catalysts"] = verified_catalysts
        result["unverified_catalysts"] = unverified_catalysts
        result["requires_manual_verification"] = requires_manual_count > 0

        # =====================================================================
        # CRITICAL: BLOCK TRADE IF UNVERIFIED CATALYSTS ARE SIGNIFICANT
        # This is REAL MONEY protection - don't trade on unverified info
        # =====================================================================

        if result["trade_allowed"]:
            # Check for critical unverified catalysts
            critical_unverified = [u for u in unverified_catalysts if u.get("type") in ["INSIDER", "NEWS"]]

            if len(critical_unverified) > 0 and verified_count < total_catalysts * 0.5:
                # Less than 50% of catalysts verified AND has critical unverified
                result["trade_allowed"] = False
                warnings.append({
                    "type": "VERIFICATION_BLOCKED",
                    "message": f"Trade BLOCKED: Only {verified_count}/{total_catalysts} catalysts verified. "
                               f"{len(critical_unverified)} critical catalyst(s) UNVERIFIED.",
                    "action": "Manually verify unverified catalysts before trading"
                })

            # If too many require manual verification
            if requires_manual_count >= total_catalysts * 0.5 and total_catalysts >= 3:
                result["requires_manual_verification"] = True
                warnings.append({
                    "type": "MANUAL_CHECK_REQUIRED",
                    "message": f"{requires_manual_count}/{total_catalysts} catalysts require manual verification.",
                    "action": "Review unverified_catalysts list and verify each before trading"
                })

        # Update warnings in result
        result["warnings"] = warnings

        return result


    @mcp.tool()
    def detect_insider_cluster(ticker: str, days: int = 60) -> dict[str, Any]:
        """
        Detect clustered insider buying patterns - stronger signal than single buy.

        Returns:
        - cluster_detected: bool
        - cluster_type: BUYING / SELLING / MIXED
        - cluster_strength: STRONG (3+) / MODERATE (2) / WEAK (1) / NONE
        - insiders: List of insider transactions
        - total_value: Sum of insider transactions
        - notable: CEO/CFO buys flagged specially
        """
        from datetime import datetime, timedelta

        ticker = validate_ticker(ticker)

        result = {
            "ticker": ticker,
            "cluster_detected": False,
            "cluster_type": "NONE",
            "cluster_strength": "NONE",
            "insiders": [],
            "total_buy_value": 0,
            "total_sell_value": 0,
            "notable_trades": [],
            "days_analyzed": days
        }

        try:
            insider_data = yf_call(ticker, "get_insider_transactions")

            if insider_data is None or (isinstance(insider_data, pd.DataFrame) and insider_data.empty):
                return result

            df = insider_data.copy()

            # Parse dates
            cutoff_date = datetime.now() - timedelta(days=days)
            if 'Start Date' in df.columns:
                df['date'] = pd.to_datetime(df['Start Date'], errors='coerce')
                df = df[df['date'] >= cutoff_date]

            if df.empty:
                return result

            # Categorize transactions
            # Column is named 'Text' in yfinance, not 'Transaction'
            buys = []
            sells = []

            for _, row in df.iterrows():
                # Try 'Text' first (yfinance column name), then 'Transaction'
                transaction = row.get('Text', row.get('Transaction', ''))
                insider = row.get('Insider', '')
                shares = row.get('Shares', 0)
                value = row.get('Value', 0)

                position = row.get('Position', '')
                trade_info = {
                    "insider": insider,
                    "position": position,
                    "transaction": transaction,
                    "shares": shares,
                    "value": value if not pd.isna(value) else 0,
                    "date": str(row.get('date', ''))[:10]
                }

                if 'Purchase' in str(transaction) or 'Buy' in str(transaction):
                    buys.append(trade_info)

                    # Flag C-suite buys
                    c_suite = ['CEO', 'CFO', 'COO', 'PRESIDENT', 'CHAIRMAN', 'CHIEF']
                    if any(t in str(insider).upper() or t in str(position).upper() for t in c_suite):
                        trade_info["notable"] = True
                        result["notable_trades"].append(trade_info)

                elif 'Sale' in str(transaction) or 'Sell' in str(transaction):
                    sells.append(trade_info)

            # Calculate totals
            result["total_buy_value"] = sum(b.get('value', 0) or 0 for b in buys)
            result["total_sell_value"] = sum(s.get('value', 0) or 0 for s in sells)
            result["buy_count"] = len(buys)
            result["sell_count"] = len(sells)
            result["insiders"] = buys + sells

            # Flag C-suite sells too (not just buys)
            c_suite_titles = ['CEO', 'CFO', 'COO', 'PRESIDENT', 'CHAIRMAN', 'CHIEF']
            for s_trade in sells:
                insider_name = str(s_trade.get('insider', '')).upper()
                position = str(s_trade.get('position', '')).upper() if 'position' in s_trade else ''
                if any(title in insider_name or title in position for title in c_suite_titles):
                    s_trade["notable"] = True
                    if s_trade not in result["notable_trades"]:
                        result["notable_trades"].append(s_trade)

            # Determine cluster type and strength
            buy_count = len(buys)
            sell_count = len(sells)

            if buy_count >= 3:
                result["cluster_detected"] = True
                result["cluster_type"] = "BUYING"
                result["cluster_strength"] = "STRONG"
            elif buy_count >= 2:
                result["cluster_detected"] = True
                result["cluster_type"] = "BUYING"
                result["cluster_strength"] = "MODERATE"
            elif buy_count >= 1:
                result["cluster_detected"] = False
                result["cluster_type"] = "BUYING"
                result["cluster_strength"] = "WEAK"

            if sell_count >= 3:
                if not result["cluster_detected"] or result["cluster_type"] != "BUYING":
                    result["cluster_detected"] = True
                    result["cluster_type"] = "SELLING"
                    result["cluster_strength"] = "STRONG"
            elif sell_count >= 2:
                if not result["cluster_detected"]:
                    result["cluster_detected"] = True
                    result["cluster_type"] = "SELLING"
                    result["cluster_strength"] = "MODERATE"

            # Mixed if both significant
            if buy_count >= 2 and sell_count >= 2:
                result["cluster_type"] = "MIXED"

            # Net signal for compact summary
            if buy_count > sell_count:
                result["net_signal"] = "BULLISH"
            elif sell_count > buy_count:
                result["net_signal"] = "BEARISH"
            else:
                result["net_signal"] = "NEUTRAL"

        except Exception as e:
            result["error"] = str(e)

        return result


    @mcp.tool()
    def detect_unusual_options_activity(ticker: str) -> dict[str, Any]:
        """
        Detect unusual options activity signaling smart money.

        Detection Criteria:
        - Volume/OI > 2x = Unusual interest
        - Large premium concentrations
        - Near-term options focus (2-4 weeks)

        Returns:
        - unusual_activity: bool
        - activity_type: BULLISH / BEARISH / MIXED
        - signals: List of unusual activity detected
        - largest_bet: Description of biggest position
        - implied_move: Expected move from options pricing
        """
        from datetime import datetime, timedelta

        ticker = validate_ticker(ticker)

        result = {
            "ticker": ticker,
            "unusual_activity": False,
            "activity_type": "NEUTRAL",
            "signals": [],
            "largest_bet": None,
            "implied_move": None,
            "call_volume": 0,
            "put_volume": 0,
            "put_call_ratio": None
        }

        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            current_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)

            if not t.options or len(t.options) == 0:
                result["error"] = "No options available"
                return result

            total_call_vol = 0
            total_put_vol = 0
            total_call_oi = 0
            total_put_oi = 0
            unusual_signals = []
            largest_premium = 0
            largest_bet_info = None

            # Analyze first 2 expirations (near-term focus)
            for exp in t.options[:2]:
                try:
                    chain = t.option_chain(exp)

                    # Analyze calls
                    if chain.calls is not None and not chain.calls.empty:
                        calls = chain.calls

                        for _, row in calls.iterrows():
                            # Handle NaN values properly (NaN or 0 = NaN, not 0)
                            vol = row.get('volume', 0)
                            vol = 0 if pd.isna(vol) else int(vol)
                            oi = row.get('openInterest', 0)
                            oi = 0 if pd.isna(oi) else int(oi)
                            strike = row.get('strike', 0)
                            last_price = row.get('lastPrice', 0)
                            last_price = 0 if pd.isna(last_price) else float(last_price)

                            total_call_vol += vol
                            total_call_oi += oi

                            # Unusual: Volume > UOA_VOL_OI_HIGH * OI
                            if oi > 0 and vol > UOA_VOL_OI_HIGH * oi:
                                premium = vol * last_price * 100
                                if premium > UOA_PREMIUM_MIN:
                                    unusual_signals.append({
                                        "type": "CALL",
                                        "strike": strike,
                                        "expiry": exp,
                                        "volume": vol,
                                        "oi": oi,
                                        "vol_oi_ratio": round(vol/oi, 1),
                                        "premium": premium
                                    })

                                    if premium > largest_premium:
                                        largest_premium = premium
                                        largest_bet_info = {
                                            "type": "CALL",
                                            "strike": strike,
                                            "expiry": exp,
                                            "premium": f"${premium:,.0f}"
                                        }

                    # Analyze puts
                    if chain.puts is not None and not chain.puts.empty:
                        puts = chain.puts

                        for _, row in puts.iterrows():
                            # Handle NaN values properly (NaN or 0 = NaN, not 0)
                            vol = row.get('volume', 0)
                            vol = 0 if pd.isna(vol) else int(vol)
                            oi = row.get('openInterest', 0)
                            oi = 0 if pd.isna(oi) else int(oi)
                            strike = row.get('strike', 0)
                            last_price = row.get('lastPrice', 0)
                            last_price = 0 if pd.isna(last_price) else float(last_price)

                            total_put_vol += vol
                            total_put_oi += oi

                            # Unusual: Volume > UOA_VOL_OI_HIGH * OI
                            if oi > 0 and vol > UOA_VOL_OI_HIGH * oi:
                                premium = vol * last_price * 100
                                if premium > UOA_PREMIUM_MIN:
                                    unusual_signals.append({
                                        "type": "PUT",
                                        "strike": strike,
                                        "expiry": exp,
                                        "volume": vol,
                                        "oi": oi,
                                        "vol_oi_ratio": round(vol/oi, 1),
                                        "premium": premium
                                    })

                                    if premium > largest_premium:
                                        largest_premium = premium
                                        largest_bet_info = {
                                            "type": "PUT",
                                            "strike": strike,
                                            "expiry": exp,
                                            "premium": f"${premium:,.0f}"
                                        }

                except Exception:
                    continue

            result["call_volume"] = total_call_vol
            result["put_volume"] = total_put_vol
            result["signals"] = unusual_signals[:10]  # Top 10 signals
            result["largest_bet"] = largest_bet_info

            # Put/Call ratio
            if total_call_vol > 0:
                pc_ratio = total_put_vol / total_call_vol
                result["put_call_ratio"] = round(pc_ratio, 2)

            # Determine activity type (enhanced with premium-weighted classification)
            call_signals = len([s for s in unusual_signals if s["type"] == "CALL"])
            put_signals = len([s for s in unusual_signals if s["type"] == "PUT"])

            # Calculate premium-weighted totals (dollar flow matters more than count)
            total_call_premium = sum(s.get('premium', 0) for s in unusual_signals if s["type"] == "CALL")
            total_put_premium = sum(s.get('premium', 0) for s in unusual_signals if s["type"] == "PUT")

            if len(unusual_signals) > 0:
                result["unusual_activity"] = True

                # Count-based classification
                if call_signals > put_signals * 1.5:
                    count_bias = "BULLISH"
                elif put_signals > call_signals * 1.5:
                    count_bias = "BEARISH"
                else:
                    count_bias = "MIXED"

                # Premium-based classification (follow the money)
                if total_call_premium > total_put_premium * 1.5:
                    premium_bias = "BULLISH"
                elif total_put_premium > total_call_premium * 1.5:
                    premium_bias = "BEARISH"
                else:
                    premium_bias = "MIXED"

                # Combined classification - premium wins when they disagree
                if count_bias == premium_bias:
                    result["activity_type"] = count_bias
                else:
                    result["activity_type"] = premium_bias  # Follow the money
                    result["activity_note"] = f"Count bias: {count_bias}, Premium bias: {premium_bias} (using premium)"

                # Add premium breakdown for transparency
                result["premium_breakdown"] = {
                    "call_premium": round(total_call_premium, 0),
                    "put_premium": round(total_put_premium, 0),
                    "count_bias": count_bias,
                    "premium_bias": premium_bias
                }

            # Implied move from ATM straddle
            try:
                if t.options and len(t.options) > 0:
                    chain = t.option_chain(t.options[0])
                    atm_strike = min(chain.calls['strike'], key=lambda x: abs(x - current_price))

                    atm_call = chain.calls[chain.calls['strike'] == atm_strike]['lastPrice'].iloc[0]
                    atm_put = chain.puts[chain.puts['strike'] == atm_strike]['lastPrice'].iloc[0]

                    straddle_cost = atm_call + atm_put
                    implied_move_pct = (straddle_cost / current_price) * 100

                    result["implied_move"] = {
                        "straddle_cost": round(straddle_cost, 2),
                        "implied_move_pct": round(implied_move_pct, 1),
                        "range": f"${current_price - straddle_cost:.2f} - ${current_price + straddle_cost:.2f}"
                    }
            except:
                pass

        except Exception as e:
            result["error"] = str(e)

        return result


    @mcp.tool()
    def calculate_quality_score(ticker: str) -> dict[str, Any]:
        """
        Unified quality score combining financial health metrics.

        Components:
        - F-Score (30%): 7+ = good, <3 = bad
        - Z-Score (20%): >2.99 = safe, <1.81 = distress
        - ROE (20%): >15% = good
        - Debt/Equity (15%): <1.0 = good
        - Net Margin (15%): >10% = good

        Returns:
        - quality_score: 0-100
        - quality_grade: A / B / C / D / F
        - components: Individual metric values
        - red_flags: List of concerns
        - green_flags: List of positives
        """
        ticker = validate_ticker(ticker)

        result = {
            "ticker": ticker,
            "quality_score": 0,
            "quality_grade": "N/A",
            "components": {},
            "red_flags": [],
            "green_flags": []
        }

        score = 0
        max_score = 100

        try:
            # Get fundamental scores (F-Score, Z-Score)
            try:
                fund_scores = calculate_fundamental_scores_tool(ticker)

                if isinstance(fund_scores, dict):
                    f_score = fund_scores.get("piotroski_f_score", {}).get("score", 0)
                    z_score = fund_scores.get("altman_z_score", {}).get("score", 0)

                    result["components"]["f_score"] = f_score
                    result["components"]["z_score"] = round(z_score, 2) if z_score else None

                    # F-Score scoring (30 pts max)
                    if f_score >= 7:
                        score += 30
                        result["green_flags"].append(f"Strong F-Score: {f_score}/9")
                    elif f_score >= 5:
                        score += 20
                    elif f_score >= 3:
                        score += 10
                    else:
                        result["red_flags"].append(f"Weak F-Score: {f_score}/9 (value trap risk)")

                    # Z-Score scoring (20 pts max)
                    if z_score:
                        if z_score > 2.99:
                            score += 20
                            result["green_flags"].append(f"Safe Z-Score: {z_score:.2f}")
                        elif z_score > 1.81:
                            score += 10
                        else:
                            result["red_flags"].append(f"Distress Z-Score: {z_score:.2f}")

            except Exception as e:
                result["components"]["fundamental_error"] = str(e)

            # Get financial metrics from ticker info
            try:
                t = yf.Ticker(ticker)
                info = t.info

                # ROE (20 pts max)
                roe = info.get('returnOnEquity')
                if roe is not None:
                    roe_pct = roe * 100
                    result["components"]["roe"] = round(roe_pct, 1)

                    if roe_pct >= 20:
                        score += 20
                        result["green_flags"].append(f"Excellent ROE: {roe_pct:.1f}%")
                    elif roe_pct >= 15:
                        score += 15
                        result["green_flags"].append(f"Good ROE: {roe_pct:.1f}%")
                    elif roe_pct >= 10:
                        score += 10
                    elif roe_pct < 5:
                        result["red_flags"].append(f"Low ROE: {roe_pct:.1f}%")

                # Debt/Equity (15 pts max)
                total_debt = info.get('totalDebt', 0)
                total_equity = info.get('totalStockholderEquity', 0)

                if total_equity and total_equity > 0:
                    de_ratio = total_debt / total_equity
                    result["components"]["debt_to_equity"] = round(de_ratio, 2)

                    if de_ratio < 0.5:
                        score += 15
                        result["green_flags"].append(f"Low Debt/Equity: {de_ratio:.2f}")
                    elif de_ratio < 1.0:
                        score += 10
                    elif de_ratio > 2.0:
                        result["red_flags"].append(f"High Debt/Equity: {de_ratio:.2f}")

                # Net Margin (15 pts max)
                profit_margin = info.get('profitMargins')
                if profit_margin is not None:
                    margin_pct = profit_margin * 100
                    result["components"]["net_margin"] = round(margin_pct, 1)

                    if margin_pct >= 15:
                        score += 15
                        result["green_flags"].append(f"High Margin: {margin_pct:.1f}%")
                    elif margin_pct >= 10:
                        score += 10
                    elif margin_pct >= 5:
                        score += 5
                    elif margin_pct < 0:
                        result["red_flags"].append(f"Negative Margin: {margin_pct:.1f}%")

                # Additional metrics
                result["components"]["gross_margin"] = round(info.get('grossMargins', 0) * 100, 1) if info.get('grossMargins') else None
                result["components"]["operating_margin"] = round(info.get('operatingMargins', 0) * 100, 1) if info.get('operatingMargins') else None

            except Exception as e:
                result["components"]["info_error"] = str(e)

            # Calculate final score and grade
            result["quality_score"] = min(100, score)

            if score >= 80:
                result["quality_grade"] = "A"
            elif score >= 65:
                result["quality_grade"] = "B"
            elif score >= 50:
                result["quality_grade"] = "C"
            elif score >= 35:
                result["quality_grade"] = "D"
            else:
                result["quality_grade"] = "F"

        except Exception as e:
            result["error"] = str(e)

        return result


    @mcp.tool()
    def analyze_competitors(ticker: str, top_n: int = 5) -> dict[str, Any]:
        """
        Compare stock vs sector peers to identify true leaders.

        Returns:
        - sector: Sector name
        - sector_rank: 1 = best, N = worst
        - is_leader: bool (rank <= 3)
        - competitors: List of competitor performance data
        - relative_advantage: What makes this stock better/worse
        """
        ticker = validate_ticker(ticker)

        result = {
            "ticker": ticker,
            "sector": None,
            "industry": None,
            "sector_rank": None,
            "is_leader": False,
            "competitors": [],
            "relative_advantage": []
        }

        try:
            t = yf.Ticker(ticker)
            info = t.info

            sector = info.get('sector')
            industry = info.get('industry')

            result["sector"] = sector
            result["industry"] = industry

            if not sector:
                result["error"] = "Could not determine sector"
                return result

            # Get sector ETF for comparison
            sector_etfs = {
                "Technology": ["XLK", "QQQ"],
                "Healthcare": ["XLV", "VHT"],
                "Financial Services": ["XLF", "VFH"],
                "Consumer Cyclical": ["XLY", "VCR"],
                "Consumer Defensive": ["XLP", "VDC"],
                "Energy": ["XLE", "VDE"],
                "Industrials": ["XLI", "VIS"],
                "Basic Materials": ["XLB", "VAW"],
                "Real Estate": ["XLRE", "VNQ"],
                "Utilities": ["XLU", "VPU"],
                "Communication Services": ["XLC", "VOX"]
            }

            # Get target ticker performance (Questrade primary, Yahoo fallback, cached)
            target_hist = _get_ohlcv_cached(ticker, period="3mo")
            if target_hist is None or target_hist.empty:
                result["error"] = "Could not get price history"
                return result

            target_return_30d = (target_hist['Close'].iloc[-1] / target_hist['Close'].iloc[-22] - 1) * 100 if len(target_hist) >= 22 else 0
            target_return_90d = (target_hist['Close'].iloc[-1] / target_hist['Close'].iloc[0] - 1) * 100

            result["performance"] = {
                "return_30d": round(target_return_30d, 2),
                "return_90d": round(target_return_90d, 2)
            }

            # Compare to sector ETF
            sector_etf = sector_etfs.get(sector, ["SPY"])[0]
            try:
                # Get ETF history (Questrade primary, Yahoo fallback, cached)
                etf_hist = _get_ohlcv_cached(sector_etf, period="3mo")

                if etf_hist is not None and not etf_hist.empty:
                    etf_return_30d = (etf_hist['Close'].iloc[-1] / etf_hist['Close'].iloc[-22] - 1) * 100 if len(etf_hist) >= 22 else 0
                    etf_return_90d = (etf_hist['Close'].iloc[-1] / etf_hist['Close'].iloc[0] - 1) * 100

                    result["vs_sector"] = {
                        "sector_etf": sector_etf,
                        "sector_return_30d": round(etf_return_30d, 2),
                        "sector_return_90d": round(etf_return_90d, 2),
                        "outperformance_30d": round(target_return_30d - etf_return_30d, 2),
                        "outperformance_90d": round(target_return_90d - etf_return_90d, 2)
                    }

                    if target_return_30d > etf_return_30d:
                        result["relative_advantage"].append(f"Outperforming {sector_etf} by {target_return_30d - etf_return_30d:.1f}% (30d)")
                        result["is_leader"] = True
                    else:
                        result["relative_advantage"].append(f"Underperforming {sector_etf} by {etf_return_30d - target_return_30d:.1f}% (30d)")

            except:
                pass

            # Find industry peers using comprehensive mapping with fuzzy matching + sector fallback
            try:
                # Comprehensive industry peer mapping (60+ industries)
                industry_peers = {
                    # Technology - Software
                    "Software - Infrastructure": ["MSFT", "ORCL", "CRM", "NOW", "ADBE", "INTU", "PANW", "CRWD", "SNOW", "DDOG"],
                    "Software - Application": ["CRM", "ADBE", "NOW", "WDAY", "ZM", "TEAM", "HUBS", "DOCU", "ZS", "OKTA"],
                    "Software—Infrastructure": ["MSFT", "ORCL", "CRM", "NOW", "ADBE", "INTU", "PANW", "CRWD", "SNOW", "DDOG"],
                    "Software—Application": ["CRM", "ADBE", "NOW", "WDAY", "ZM", "TEAM", "HUBS", "DOCU", "ZS", "OKTA"],
                    "Information Technology Services": ["ACN", "IBM", "INFY", "WIT", "CTSH", "EPAM", "LDOS", "DXC"],
                    "Electronic Components": ["TEL", "APH", "GLW", "JBL", "FLEX", "SANM", "ARW", "AVT"],
                    "Computer Hardware": ["AAPL", "HPQ", "DELL", "NTAP", "WDC", "STX", "PSTG"],
                    # Technology - Semiconductors & Electronics
                    "Semiconductors": ["NVDA", "AMD", "INTC", "AVGO", "QCOM", "TSM", "TXN", "MU", "MRVL", "AMAT"],
                    "Semiconductor Equipment & Materials": ["AMAT", "LRCX", "KLAC", "ASML", "ENTG", "TER", "MKSI"],
                    "Consumer Electronics": ["AAPL", "SONY", "SONO", "GPRO", "KOSS", "VZIO"],
                    # Technology - Internet & Digital
                    "Internet Content & Information": ["GOOGL", "META", "SNAP", "PINS", "NFLX", "SPOT", "RBLX", "RDDT"],
                    "Internet Retail": ["AMZN", "BABA", "JD", "MELI", "SHOP", "EBAY", "ETSY", "W", "CHWY"],
                    "Entertainment": ["DIS", "NFLX", "WBD", "PARA", "LYV", "MSG", "IMAX"],
                    "Electronic Gaming & Multimedia": ["EA", "TTWO", "ATVI", "U", "RBLX", "PLTK"],
                    # Financial - Banking
                    "Banks - Diversified": ["JPM", "BAC", "WFC", "C", "USB", "PNC", "TFC", "COF", "SCHW"],
                    "Banks - Regional": ["USB", "PNC", "TFC", "FRC", "MTB", "FITB", "HBAN", "RF", "KEY", "CFG"],
                    "Banks—Diversified": ["JPM", "BAC", "WFC", "C", "USB", "PNC", "TFC", "COF", "SCHW"],
                    "Banks—Regional": ["USB", "PNC", "TFC", "MTB", "FITB", "HBAN", "RF", "KEY", "CFG"],
                    # Financial - Investment & Insurance
                    "Asset Management": ["BLK", "BX", "KKR", "APO", "ARES", "TROW", "IVZ", "BEN"],
                    "Insurance - Diversified": ["BRK-B", "AIG", "MET", "PRU", "ALL", "TRV", "CB", "AFL"],
                    "Insurance - Life": ["MET", "PRU", "LNC", "AFL", "GL", "PFG"],
                    "Insurance - Property & Casualty": ["PGR", "ALL", "TRV", "CB", "AIG", "CNA", "HIG"],
                    "Capital Markets": ["GS", "MS", "SCHW", "IBKR", "SF", "LAZ", "EVR", "MC"],
                    "Credit Services": ["V", "MA", "AXP", "DFS", "COF", "SYF", "PYPL", "SQ"],
                    # Healthcare - Pharma & Biotech
                    "Drug Manufacturers - General": ["JNJ", "PFE", "MRK", "LLY", "ABBV", "BMY", "NVO", "AZN", "GSK"],
                    "Drug Manufacturers—General": ["JNJ", "PFE", "MRK", "LLY", "ABBV", "BMY", "NVO", "AZN", "GSK"],
                    "Biotechnology": ["AMGN", "GILD", "REGN", "VRTX", "BIIB", "MRNA", "BNTX", "SGEN", "ALNY", "INCY"],
                    "Pharmaceutical Retailers": ["WBA", "CVS", "CI", "AMGN"],
                    # Healthcare - Medical
                    "Medical Devices": ["ABT", "MDT", "SYK", "BSX", "EW", "ISRG", "DXCM", "ALGN", "ZBH", "BAX"],
                    "Medical Instruments & Supplies": ["ABT", "MDT", "SYK", "BSX", "EW", "ISRG", "DXCM", "ALGN"],
                    "Health Care Plans": ["UNH", "CVS", "CI", "ELV", "HUM", "CNC", "MOH"],
                    "Healthcare Plans": ["UNH", "CVS", "CI", "ELV", "HUM", "CNC", "MOH"],
                    "Medical Distribution": ["MCK", "CAH", "ABC", "CI"],
                    "Diagnostics & Research": ["TMO", "DHR", "ILMN", "A", "IQV", "LH", "DGX"],
                    # Consumer - Retail
                    "Specialty Retail": ["HD", "LOW", "TJX", "ROST", "ULTA", "BBY", "TSCO", "WSM", "AZO", "ORLY"],
                    "Discount Stores": ["WMT", "TGT", "COST", "DG", "DLTR"],
                    "Apparel Retail": ["TJX", "ROST", "GPS", "ANF", "AEO", "URBN", "LULU"],
                    "Luxury Goods": ["LVMUY", "TPR", "RL", "CPRI", "TPCO"],
                    "Department Stores": ["M", "KSS", "JWN", "DDS"],
                    # Consumer - Food & Beverage
                    "Restaurants": ["MCD", "SBUX", "CMG", "YUM", "DPZ", "QSR", "DRI", "WING", "TXRH", "BLMN"],
                    "Beverages - Wineries & Distilleries": ["STZ", "BF-B", "TAP", "SAM", "BUD"],
                    "Beverages - Non-Alcoholic": ["KO", "PEP", "MNST", "KDP", "CELH"],
                    "Packaged Foods": ["GIS", "K", "CAG", "CPB", "MKC", "HSY", "MDLZ"],
                    "Food Distribution": ["SYY", "USFD", "PFGC"],
                    # Consumer - Other
                    "Auto Manufacturers": ["TSLA", "F", "GM", "TM", "HMC", "RIVN", "LCID", "NIO", "STLA"],
                    "Auto Parts": ["APTV", "LEA", "ADNT", "BWA", "ALV", "MOD", "VC"],
                    "Leisure": ["CCL", "RCL", "NCLH", "MAR", "HLT", "H", "IHG"],
                    "Travel Services": ["BKNG", "EXPE", "TRIP", "ABNB", "TCOM"],
                    "Furnishings, Fixtures & Appliances": ["WHR", "LEG", "ETD", "SNBR"],
                    # Energy
                    "Oil & Gas Integrated": ["XOM", "CVX", "COP", "TTE", "BP", "SHEL"],
                    "Oil & Gas E&P": ["EOG", "PXD", "DVN", "COP", "OXY", "FANG", "MRO", "APA", "HES"],
                    "Oil & Gas Midstream": ["EPD", "ET", "WMB", "OKE", "MPLX", "PAA", "KMI"],
                    "Oil & Gas Refining & Marketing": ["PSX", "VLO", "MPC", "HFC", "DINO"],
                    "Oil & Gas Equipment & Services": ["SLB", "HAL", "BKR", "FTI", "NOV", "HP", "PTEN"],
                    # Industrial
                    "Aerospace & Defense": ["BA", "RTX", "LMT", "NOC", "GD", "LHX", "HWM", "TDG", "TXT"],
                    "Railroads": ["UNP", "CSX", "NSC", "CP", "CNI"],
                    "Airlines": ["DAL", "UAL", "AAL", "LUV", "JBLU", "SAVE", "ALK"],
                    "Trucking": ["ODFL", "XPO", "JBHT", "KNX", "CHRW", "LSTR"],
                    "Marine Shipping": ["EGLE", "SBLK", "STNG", "FRO", "INSW"],
                    "Industrial Distribution": ["GWW", "FAST", "WST", "DCI"],
                    "Building Products & Equipment": ["JCI", "CARR", "BLD", "OC", "MAS", "BLDR"],
                    "Engineering & Construction": ["FLR", "STRL", "PWR", "EME", "MTZ", "ACM"],
                    "Machinery": ["CAT", "DE", "CMI", "EMR", "ETN", "ITW", "PH", "ROK"],
                    # Materials
                    "Chemicals": ["LIN", "APD", "ECL", "SHW", "DD", "DOW", "PPG", "NEM"],
                    "Steel": ["NUE", "STLD", "X", "CLF", "RS", "MT"],
                    "Copper": ["FCX", "SCCO", "TGB", "CMCL"],
                    "Gold": ["NEM", "GOLD", "AEM", "KGC", "FNV"],
                    "Agricultural Inputs": ["NTR", "MOS", "CF", "ICL", "SMG"],
                    # Communication & Utilities
                    "Telecom Services": ["T", "VZ", "TMUS", "LUMN"],
                    "Telecommunications Services": ["T", "VZ", "TMUS", "LUMN"],
                    "Wireless Telecommunication Services": ["T", "VZ", "TMUS"],
                    "Utilities - Regulated Electric": ["NEE", "DUK", "SO", "D", "AEP", "XEL", "SRE", "ED"],
                    "Utilities - Renewable": ["NEE", "AES", "BEP", "CWEN", "RUN"],
                    "Utilities - Independent Power Producers": ["NEE", "AES", "NRG", "VST", "CEG", "OKLO"],
                    "Specialty Industrial Machinery": ["ITW", "ROK", "EMR", "ETN", "PH", "IR", "DOV", "XYL", "FLS", "NDSN"],
                    "Utilities—Regulated Electric": ["NEE", "DUK", "SO", "D", "AEP", "XEL", "SRE", "ED"],
                    # Real Estate
                    "REIT - Residential": ["EQR", "AVB", "ESS", "MAA", "UDR", "CPT"],
                    "REIT - Retail": ["SPG", "REG", "KIM", "BRX", "SKT"],
                    "REIT - Office": ["BXP", "VNO", "SLG", "DEI", "CUZ"],
                    "REIT - Industrial": ["PLD", "DRE", "FR", "REXR", "STAG"],
                    "REIT - Healthcare Facilities": ["WELL", "VTR", "PEAK", "DOC", "HR"],
                }

                # Sector-based fallback mapping when industry not found
                sector_peers = {
                    "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AVGO", "ORCL", "AMD"],
                    "Financial Services": ["JPM", "BAC", "WFC", "GS", "MS", "BLK", "SCHW", "AXP", "C", "USB"],
                    "Healthcare": ["UNH", "JNJ", "LLY", "ABBV", "MRK", "TMO", "ABT", "PFE", "DHR", "BMY"],
                    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG"],
                    "Consumer Defensive": ["WMT", "PG", "COST", "KO", "PEP", "PM", "MDLZ", "CL", "KMB", "GIS"],
                    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "WMB"],
                    "Industrials": ["CAT", "HON", "UNP", "RTX", "BA", "GE", "LMT", "DE", "MMM", "UPS"],
                    "Basic Materials": ["LIN", "APD", "SHW", "ECL", "NEM", "FCX", "NUE", "DD", "DOW", "PPG"],
                    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "WBD"],
                    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "XEL", "EXC", "ED", "WEC"],
                    "Real Estate": ["PLD", "AMT", "EQIX", "PSA", "CCI", "SPG", "WELL", "DLR", "O", "AVB"],
                }

                industry = info.get('industry')
                sector = info.get('sector')

                # Try exact match first
                peers = None
                if industry and industry in industry_peers:
                    peers = industry_peers[industry]

                # Try fuzzy match (normalize dashes/em-dashes, case)
                if not peers and industry:
                    normalized_industry = industry.replace('—', ' - ').replace('  ', ' ')
                    for key in industry_peers:
                        if key.replace('—', ' - ').replace('  ', ' ').lower() == normalized_industry.lower():
                            peers = industry_peers[key]
                            break

                # Fallback to sector-based peers
                if not peers and sector and sector in sector_peers:
                    peers = sector_peers[sector]
                    result["note"] = f"Industry '{industry}' not found. Using sector '{sector}' peers."

                if peers:
                    # Remove target ticker from peers list
                    peers = [p for p in peers if p.upper() != ticker.upper()][:top_n]

                    competitors = []
                    for peer in peers:
                        try:
                            # Get peer history (Questrade primary, Yahoo fallback, cached)
                            peer_hist = _get_ohlcv_cached(peer, period="3mo")
                            if peer_hist is not None and not peer_hist.empty and len(peer_hist) >= 22:
                                peer_30d = (peer_hist['Close'].iloc[-1] / peer_hist['Close'].iloc[-22] - 1) * 100
                                peer_90d = (peer_hist['Close'].iloc[-1] / peer_hist['Close'].iloc[0] - 1) * 100

                                # Calculate RS score for peer
                                peer_rs = calculate_relative_strength_tool(peer, benchmark="SPY", period="3mo")
                                peer_rs_score = peer_rs.get("rs_score", 50) if isinstance(peer_rs, dict) else 50

                                competitors.append({
                                    "ticker": peer,
                                    "return_30d": round(peer_30d, 2),
                                    "return_90d": round(peer_90d, 2),
                                    "rs_score": peer_rs_score
                                })
                        except Exception:
                            continue

                    if competitors:
                        # Sort by 30d return and add ranking
                        competitors.sort(key=lambda x: x['return_30d'], reverse=True)
                        all_returns = [c['return_30d'] for c in competitors] + [target_return_30d]
                        all_returns.sort(reverse=True)
                        target_rank = all_returns.index(target_return_30d) + 1

                        result["competitors"] = competitors
                        result["sector_rank"] = target_rank
                        result["total_peers"] = len(competitors) + 1
                        result["is_leader"] = target_rank <= 3

                        if target_rank == 1:
                            result["relative_advantage"].append(f"#1 in industry (30d performance)")
                        elif target_rank <= 3:
                            result["relative_advantage"].append(f"Top 3 in industry (rank #{target_rank})")
                        else:
                            result["relative_advantage"].append(f"Rank #{target_rank} of {len(competitors) + 1} in industry")
                else:
                    result["note"] = f"No peers found for industry '{industry}' or sector '{sector}'. Compared against {sector_etf} sector ETF."

            except Exception as peer_err:
                result["note"] = f"Peer comparison unavailable: {str(peer_err)[:50]}. Compared against {sector_etf} sector ETF."

            # Calculate RS vs SPY
            try:
                rs_data = calculate_relative_strength_tool(ticker, benchmark="SPY", period="3mo")
                if isinstance(rs_data, dict):
                    rs_score = rs_data.get("rs_score", 0)
                    result["rs_vs_spy"] = rs_score

                    if rs_score >= 70:
                        result["relative_advantage"].append(f"Strong RS Score: {rs_score}")
                        result["is_leader"] = True
                    elif rs_score <= 30:
                        result["relative_advantage"].append(f"Weak RS Score: {rs_score}")

            except:
                pass

        except Exception as e:
            result["error"] = str(e)

        return result

    # Expose closure functions via module-level _impl references
    global detect_catalyst_strength_impl, detect_insider_cluster_impl
    global detect_unusual_options_activity_impl, calculate_quality_score_impl
    global analyze_competitors_impl
    detect_catalyst_strength_impl = detect_catalyst_strength
    detect_insider_cluster_impl = detect_insider_cluster
    detect_unusual_options_activity_impl = detect_unusual_options_activity
    calculate_quality_score_impl = calculate_quality_score
    analyze_competitors_impl = analyze_competitors
