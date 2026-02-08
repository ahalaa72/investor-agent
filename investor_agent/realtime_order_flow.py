"""
Real-Time Order Flow Analysis using Questrade Level 1 Data.

This module provides TRUE order flow analysis by leveraging Questrade's
lastTradeTick field to classify trades as buyer or seller initiated.

Key Features:
- Trade Flow Classification (Up/Down/Equal tick)
- True Cumulative Volume Delta (CVD)
- Bid-Ask Imbalance Monitoring
- Large Trade Detection
- Real-Time VWAP Calculation

Reference: REALTIME_ORDER_FLOW_IMPLEMENTATION_PLAN.md
"""

import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import threading

from .questrade import QuestradeClient

logger = logging.getLogger(__name__)


class RealtimeOrderFlowMonitor:
    """
    Background service to poll Questrade Level 1 quotes and accumulate order flow data.

    Usage:
        monitor = RealtimeOrderFlowMonitor(["AAPL", "TSLA"], poll_interval=5)
        monitor.start()

        # Later...
        flow_data = monitor.get_trade_flow("AAPL")
        cvd_data = monitor.get_cvd("AAPL")

        monitor.stop()
    """

    def __init__(self, tickers: List[str], poll_interval_seconds: int = 5):
        """
        Initialize the order flow monitor.

        Args:
            tickers: List of ticker symbols to monitor
            poll_interval_seconds: How often to poll for new quotes (default 5 seconds)
        """
        self.tickers = [t.upper() for t in tickers]
        self.poll_interval = poll_interval_seconds
        self.client = QuestradeClient()

        # Accumulated data per ticker
        self.trade_history: Dict[str, List[dict]] = defaultdict(list)
        self.last_quote: Dict[str, dict] = {}

        # Threading
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        """Start background polling."""
        if self._running:
            logger.warning("Monitor already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info(f"Started order flow monitor for {self.tickers}")

    def stop(self):
        """Stop background polling."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Stopped order flow monitor")

    def _poll_loop(self):
        """Main polling loop."""
        while self._running:
            try:
                self._poll_quotes()
            except Exception as e:
                logger.error(f"Error polling quotes: {e}")
            time.sleep(self.poll_interval)

    def _poll_quotes(self):
        """Fetch quotes and process."""
        try:
            quotes = self.client.get_quotes(self.tickers)
            for quote in quotes.get('quotes', []):
                self._process_quote(quote)
        except Exception as e:
            logger.error(f"Failed to fetch quotes: {e}")

    def _process_quote(self, quote: dict):
        """Process a single quote and accumulate data."""
        symbol = quote.get('symbol')
        if not symbol:
            return

        with self._lock:
            # Check if this is a new trade (different from last)
            last = self.last_quote.get(symbol, {})
            last_trade_time = quote.get('lastTradeTime')
            prev_trade_time = last.get('lastTradeTime')

            if last_trade_time and last_trade_time != prev_trade_time:
                # New trade detected
                trade = {
                    'time': last_trade_time,
                    'price': quote.get('lastTradePrice'),
                    'size': quote.get('lastTradeSize', 0),
                    'tick': quote.get('lastTradeTick', 'Equal'),
                    'bid_price': quote.get('bidPrice'),
                    'bid_size': quote.get('bidSize', 0),
                    'ask_price': quote.get('askPrice'),
                    'ask_size': quote.get('askSize', 0),
                    'volume': quote.get('volume', 0)
                }
                self.trade_history[symbol].append(trade)

                # Keep only last 2 hours of data to prevent memory bloat
                cutoff = datetime.now() - timedelta(hours=2)
                self.trade_history[symbol] = [
                    t for t in self.trade_history[symbol]
                    if self._parse_time(t['time']) > cutoff
                ]

            self.last_quote[symbol] = quote

    def _parse_time(self, time_str: str) -> datetime:
        """Parse Questrade time string to datetime (timezone-naive for comparison)."""
        if not time_str:
            return datetime.now()
        try:
            # Handle ISO format with Z or timezone
            if 'Z' in time_str:
                time_str = time_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(time_str)
            # Convert to naive datetime for comparison with datetime.now()
            if dt.tzinfo is not None:
                # Remove timezone info to make comparable
                return dt.replace(tzinfo=None)
            return dt
        except Exception:
            return datetime.now()

    # -------------------------------------------------------------------------
    # Analysis Methods
    # -------------------------------------------------------------------------

    def get_trade_flow(self, ticker: str, duration_minutes: int = 30) -> dict:
        """
        Get trade flow analysis for a ticker.

        Classifies trades using lastTradeTick:
        - "Up" = Buyer hitting ask (BULLISH)
        - "Down" = Seller hitting bid (BEARISH)
        - "Equal" = Neutral

        Args:
            ticker: Stock symbol
            duration_minutes: How many minutes of data to analyze

        Returns:
            Trade flow analysis with buy/sell volumes and bias
        """
        ticker = ticker.upper()
        trades = self._get_recent_trades(ticker, duration_minutes)

        buy_volume = sum(t['size'] for t in trades if t['tick'] == 'Up')
        sell_volume = sum(t['size'] for t in trades if t['tick'] == 'Down')
        neutral_volume = sum(t['size'] for t in trades if t['tick'] == 'Equal')
        total_volume = buy_volume + sell_volume + neutral_volume

        # Calculate tick ratio (excluding neutral)
        buy_sell_total = buy_volume + sell_volume
        if buy_sell_total > 0:
            tick_ratio = buy_volume / buy_sell_total
        else:
            tick_ratio = 0.5  # Default to neutral if no trades

        # Determine bias based on tick ratio
        if tick_ratio > 0.55:
            bias = "BULLISH"
        elif tick_ratio < 0.45:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        # Detect large trades (> 2x average)
        if trades:
            avg_size = sum(t['size'] for t in trades) / len(trades)
            large_trades = [
                {
                    'time': t['time'],
                    'price': t['price'],
                    'size': t['size'],
                    'direction': 'BUY' if t['tick'] == 'Up' else 'SELL' if t['tick'] == 'Down' else 'NEUTRAL',
                    'size_vs_avg': round(t['size'] / avg_size, 1) if avg_size > 0 else 0
                }
                for t in trades if t['size'] > avg_size * 2
            ]
        else:
            avg_size = 0
            large_trades = []

        return {
            "ticker": ticker,
            "duration_minutes": duration_minutes,
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "neutral_volume": neutral_volume,
            "total_volume": total_volume,
            "tick_ratio": round(tick_ratio, 3),
            "aggression_bias": bias,
            "trade_count": len(trades),
            "avg_trade_size": round(avg_size, 0),
            "large_trade_count": len(large_trades),
            "large_trade_details": large_trades[-5:] if large_trades else [],
            "interpretation": f"{bias} order flow - {len(large_trades)} large trades detected"
        }

    def get_cvd(self, ticker: str, interval_minutes: int = 5) -> dict:
        """
        Get Cumulative Volume Delta (CVD) analysis.

        TRUE CVD using lastTradeTick classification, not OHLCV approximation.

        Args:
            ticker: Stock symbol
            interval_minutes: Interval for aggregation (for trend detection)

        Returns:
            CVD analysis with trend and divergence detection
        """
        ticker = ticker.upper()
        with self._lock:
            trades = list(self.trade_history.get(ticker, []))

        # Calculate cumulative delta
        buy_vol = sum(t['size'] for t in trades if t['tick'] == 'Up')
        sell_vol = sum(t['size'] for t in trades if t['tick'] == 'Down')
        cvd = buy_vol - sell_vol

        # Determine trend (compare first half to second half)
        if len(trades) >= 4:
            mid = len(trades) // 2
            first_half = trades[:mid]
            second_half = trades[mid:]

            first_delta = sum(
                t['size'] if t['tick'] == 'Up' else -t['size'] if t['tick'] == 'Down' else 0
                for t in first_half
            )
            second_delta = sum(
                t['size'] if t['tick'] == 'Up' else -t['size'] if t['tick'] == 'Down' else 0
                for t in second_half
            )

            if len(first_half) > 0 and len(second_half) > 0:
                if second_delta > first_delta * 1.1:
                    trend = "RISING"
                elif second_delta < first_delta * 0.9:
                    trend = "FALLING"
                else:
                    trend = "FLAT"
            else:
                trend = "INSUFFICIENT_DATA"
        else:
            trend = "INSUFFICIENT_DATA"
            first_delta = 0
            second_delta = 0

        # Calculate delta per interval
        delta_series = self._calculate_delta_series(trades, interval_minutes)

        return {
            "ticker": ticker,
            "cvd_current": cvd,
            "buy_volume": buy_vol,
            "sell_volume": sell_vol,
            "cvd_trend": trend,
            "trade_count": len(trades),
            "first_half_delta": first_delta,
            "second_half_delta": second_delta,
            "delta_series": delta_series[-10:],  # Last 10 intervals
            "interpretation": f"CVD {trend} - {'Buyers' if cvd > 0 else 'Sellers'} in control"
        }

    def _calculate_delta_series(self, trades: List[dict], interval_minutes: int) -> List[dict]:
        """Calculate delta per time interval."""
        if not trades:
            return []

        series = []
        current_interval_start = None
        interval_buy = 0
        interval_sell = 0

        for trade in trades:
            trade_time = self._parse_time(trade['time'])

            if current_interval_start is None:
                current_interval_start = trade_time.replace(second=0, microsecond=0)

            # Check if we've moved to a new interval
            while trade_time >= current_interval_start + timedelta(minutes=interval_minutes):
                if interval_buy > 0 or interval_sell > 0:
                    series.append({
                        'time': current_interval_start.isoformat(),
                        'buy': interval_buy,
                        'sell': interval_sell,
                        'delta': interval_buy - interval_sell
                    })
                current_interval_start += timedelta(minutes=interval_minutes)
                interval_buy = 0
                interval_sell = 0

            # Accumulate
            if trade['tick'] == 'Up':
                interval_buy += trade['size']
            elif trade['tick'] == 'Down':
                interval_sell += trade['size']

        # Add final interval if has data
        if interval_buy > 0 or interval_sell > 0:
            series.append({
                'time': current_interval_start.isoformat() if current_interval_start else datetime.now().isoformat(),
                'buy': interval_buy,
                'sell': interval_sell,
                'delta': interval_buy - interval_sell
            })

        return series

    def get_bid_ask_imbalance(self, ticker: str) -> dict:
        """
        Get current bid/ask size imbalance.

        High bid/ask ratio = More demand than supply = Bullish
        Low bid/ask ratio = More supply than demand = Bearish

        Args:
            ticker: Stock symbol

        Returns:
            Bid/ask imbalance analysis with signal
        """
        ticker = ticker.upper()
        with self._lock:
            quote = self.last_quote.get(ticker, {})

        bid_size = quote.get('bidSize', 0)
        ask_size = quote.get('askSize', 0)
        bid_price = quote.get('bidPrice', 0)
        ask_price = quote.get('askPrice', 0)

        # Calculate imbalance
        if ask_size > 0:
            imbalance = bid_size / ask_size
        else:
            imbalance = 1.0

        total = bid_size + ask_size
        if total > 0:
            imbalance_pct = (bid_size - ask_size) / total * 100
        else:
            imbalance_pct = 0

        # Determine signal
        if imbalance > 2.0:
            signal = "STRONG_BID"
        elif imbalance > 1.2:
            signal = "WEAK_BID"
        elif imbalance < 0.5:
            signal = "STRONG_ASK"
        elif imbalance < 0.8:
            signal = "WEAK_ASK"
        else:
            signal = "BALANCED"

        # Calculate spread in basis points
        mid_price = (bid_price + ask_price) / 2 if (bid_price + ask_price) > 0 else 1
        spread = ask_price - bid_price
        spread_bps = (spread / mid_price) * 10000 if mid_price > 0 else 0

        # Identify liquidity wall
        if bid_size > ask_size:
            liquidity_wall = {
                "side": "BID",
                "size": bid_size,
                "price": bid_price
            }
        else:
            liquidity_wall = {
                "side": "ASK",
                "size": ask_size,
                "price": ask_price
            }

        return {
            "ticker": ticker,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "bid_price": bid_price,
            "ask_price": ask_price,
            "imbalance_ratio": round(imbalance, 2),
            "imbalance_pct": round(imbalance_pct, 1),
            "signal": signal,
            "spread": round(spread, 4),
            "spread_bps": round(spread_bps, 1),
            "liquidity_wall": liquidity_wall,
            "interpretation": f"{'Buyers' if imbalance > 1 else 'Sellers'} have size advantage ({signal})"
        }

    def detect_large_trades(
        self,
        ticker: str,
        threshold_multiplier: float = 3.0,
        duration_minutes: int = 60
    ) -> dict:
        """
        Detect and classify large trades (potential block trades).

        Large trades often indicate institutional activity.

        Args:
            ticker: Stock symbol
            threshold_multiplier: What multiple of average size is "large" (default 3x)
            duration_minutes: How far back to look

        Returns:
            Large trade analysis with direction and size
        """
        ticker = ticker.upper()
        trades = self._get_recent_trades(ticker, duration_minutes)

        if not trades:
            return {
                "ticker": ticker,
                "large_trades": [],
                "count": 0,
                "avg_trade_size": 0,
                "threshold": 0,
                "interpretation": "No trade data available"
            }

        avg_size = sum(t['size'] for t in trades) / len(trades)
        threshold = avg_size * threshold_multiplier

        large_trades = []
        for t in trades:
            if t['size'] > threshold:
                large_trades.append({
                    'time': t['time'],
                    'price': t['price'],
                    'size': t['size'],
                    'direction': 'BUY' if t['tick'] == 'Up' else 'SELL' if t['tick'] == 'Down' else 'NEUTRAL',
                    'size_vs_avg': round(t['size'] / avg_size, 1) if avg_size > 0 else 0,
                    'is_block_trade': t['size'] >= 10000  # 10,000+ shares
                })

        # Aggregate direction
        buy_large = sum(1 for t in large_trades if t['direction'] == 'BUY')
        sell_large = sum(1 for t in large_trades if t['direction'] == 'SELL')

        if buy_large > sell_large * 1.5:
            net_direction = "BULLISH"
        elif sell_large > buy_large * 1.5:
            net_direction = "BEARISH"
        else:
            net_direction = "MIXED"

        return {
            "ticker": ticker,
            "large_trades": large_trades[-10:],  # Last 10
            "count": len(large_trades),
            "buy_large_count": buy_large,
            "sell_large_count": sell_large,
            "net_direction": net_direction,
            "avg_trade_size": round(avg_size, 0),
            "threshold": round(threshold, 0),
            "block_trades": sum(1 for t in large_trades if t.get('is_block_trade')),
            "interpretation": f"{len(large_trades)} large trades detected - {net_direction}"
        }

    def calculate_realtime_vwap(self, ticker: str) -> dict:
        """
        Calculate true intraday VWAP from accumulated trades.

        VWAP = Sum(Price * Volume) / Sum(Volume)

        Args:
            ticker: Stock symbol

        Returns:
            Real-time VWAP with bands and position
        """
        ticker = ticker.upper()
        with self._lock:
            trades = list(self.trade_history.get(ticker, []))
            quote = self.last_quote.get(ticker, {})

        if not trades:
            return {
                "ticker": ticker,
                "realtime_vwap": 0,
                "current_price": quote.get('lastTradePrice', 0),
                "deviation_pct": 0,
                "position": "NO_DATA",
                "interpretation": "Insufficient trade data for VWAP"
            }

        # Calculate VWAP
        total_pv = sum(t['price'] * t['size'] for t in trades if t['price'] and t['size'])
        total_vol = sum(t['size'] for t in trades if t['size'])

        if total_vol > 0:
            vwap = total_pv / total_vol
        else:
            vwap = 0

        # Calculate standard deviation for bands
        if len(trades) > 1 and vwap > 0:
            squared_diffs = [
                ((t['price'] - vwap) ** 2) * t['size']
                for t in trades if t['price'] and t['size']
            ]
            variance = sum(squared_diffs) / total_vol
            std_dev = variance ** 0.5
        else:
            std_dev = 0

        current_price = quote.get('lastTradePrice', 0)

        # Calculate deviation
        if vwap > 0:
            deviation_pct = ((current_price - vwap) / vwap) * 100
            sigma_distance = (current_price - vwap) / std_dev if std_dev > 0 else 0
        else:
            deviation_pct = 0
            sigma_distance = 0

        # Determine position relative to VWAP bands
        if sigma_distance > 2:
            position = "ABOVE_2SD"
        elif sigma_distance > 1:
            position = "ABOVE_1SD"
        elif sigma_distance < -2:
            position = "BELOW_2SD"
        elif sigma_distance < -1:
            position = "BELOW_1SD"
        else:
            position = "AT_VWAP"

        return {
            "ticker": ticker,
            "realtime_vwap": round(vwap, 2),
            "current_price": current_price,
            "deviation_pct": round(deviation_pct, 2),
            "sigma_distance": round(sigma_distance, 2),
            "std_dev": round(std_dev, 2),
            "bands": {
                "upper_2sd": round(vwap + 2 * std_dev, 2) if vwap else 0,
                "upper_1sd": round(vwap + std_dev, 2) if vwap else 0,
                "vwap": round(vwap, 2),
                "lower_1sd": round(vwap - std_dev, 2) if vwap else 0,
                "lower_2sd": round(vwap - 2 * std_dev, 2) if vwap else 0
            },
            "position": position,
            "trade_count": len(trades),
            "total_volume": total_vol,
            "interpretation": f"Price is {position} - {'Extended' if abs(sigma_distance) > 1.5 else 'Normal'}"
        }

    def analyze_spread_dynamics(self, ticker: str) -> dict:
        """
        Analyze spread dynamics for liquidity assessment.

        Widening spread = Lower liquidity, higher volatility expected
        Tightening spread = Higher liquidity, stability

        Args:
            ticker: Stock symbol

        Returns:
            Spread analysis with liquidity grade
        """
        ticker = ticker.upper()
        with self._lock:
            quote = self.last_quote.get(ticker, {})
            trades = list(self.trade_history.get(ticker, []))

        bid_price = quote.get('bidPrice', 0)
        ask_price = quote.get('askPrice', 0)
        bid_size = quote.get('bidSize', 0)
        ask_size = quote.get('askSize', 0)

        # Current spread
        spread = ask_price - bid_price
        mid_price = (bid_price + ask_price) / 2 if (bid_price + ask_price) > 0 else 1
        spread_bps = (spread / mid_price) * 10000 if mid_price > 0 else 0

        # Calculate historical spread from trades
        historical_spreads = []
        for t in trades:
            if t.get('bid_price') and t.get('ask_price'):
                h_spread = t['ask_price'] - t['bid_price']
                h_mid = (t['bid_price'] + t['ask_price']) / 2
                if h_mid > 0:
                    historical_spreads.append((h_spread / h_mid) * 10000)

        if historical_spreads:
            avg_spread_bps = sum(historical_spreads) / len(historical_spreads)
            spread_vs_avg = spread_bps / avg_spread_bps if avg_spread_bps > 0 else 1.0
        else:
            avg_spread_bps = spread_bps
            spread_vs_avg = 1.0

        # Determine trend
        if spread_vs_avg > 1.3:
            trend = "WIDENING"
        elif spread_vs_avg < 0.7:
            trend = "TIGHTENING"
        else:
            trend = "STABLE"

        # Liquidity grade based on spread and size
        total_size = bid_size + ask_size
        if spread_bps < 5 and total_size > 1000:
            grade = "A"  # Excellent
        elif spread_bps < 10 and total_size > 500:
            grade = "B"  # Good
        elif spread_bps < 20 and total_size > 100:
            grade = "C"  # Average
        elif spread_bps < 50:
            grade = "D"  # Poor
        else:
            grade = "F"  # Very poor

        return {
            "ticker": ticker,
            "current_spread": round(spread, 4),
            "spread_bps": round(spread_bps, 1),
            "avg_spread_bps": round(avg_spread_bps, 1),
            "spread_vs_avg": round(spread_vs_avg, 2),
            "spread_trend": trend,
            "liquidity_grade": grade,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "total_depth": bid_size + ask_size,
            "interpretation": f"Liquidity {grade} - Spread {trend.lower()}"
        }

    def _get_recent_trades(self, ticker: str, duration_minutes: int) -> List[dict]:
        """Get trades from last N minutes."""
        cutoff = datetime.now() - timedelta(minutes=duration_minutes)
        with self._lock:
            return [
                t for t in self.trade_history.get(ticker, [])
                if self._parse_time(t['time']) > cutoff
            ]

    def get_snapshot(self, ticker: str) -> dict:
        """
        Get a comprehensive snapshot of all order flow metrics.

        Combines trade flow, CVD, bid-ask imbalance, and VWAP into one call.

        Args:
            ticker: Stock symbol

        Returns:
            Complete order flow snapshot
        """
        ticker = ticker.upper()

        return {
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "trade_flow": self.get_trade_flow(ticker),
            "cvd": self.get_cvd(ticker),
            "bid_ask_imbalance": self.get_bid_ask_imbalance(ticker),
            "vwap": self.calculate_realtime_vwap(ticker),
            "spread_dynamics": self.analyze_spread_dynamics(ticker),
            "large_trades": self.detect_large_trades(ticker)
        }


# -------------------------------------------------------------------------
# Standalone Functions (for MCP tool wrappers without background monitor)
# -------------------------------------------------------------------------

def analyze_trade_flow_snapshot(ticker: str) -> dict:
    """
    Get a point-in-time trade flow analysis using Questrade quote.

    This is a simpler version that doesn't require the background monitor.
    It fetches current quote data and returns bid-ask analysis.

    Args:
        ticker: Stock symbol

    Returns:
        Trade flow snapshot from current quote
    """
    client = QuestradeClient()
    quotes = client.get_quote(ticker)

    if not quotes.get('quotes'):
        return {"error": f"No quote data for {ticker}"}

    q = quotes['quotes'][0]

    bid_size = q.get('bidSize') or 0
    ask_size = q.get('askSize') or 0
    bid_price = q.get('bidPrice') or 0
    ask_price = q.get('askPrice') or 0
    last_tick = q.get('lastTradeTick') or 'Equal'
    last_size = q.get('lastTradeSize') or 0
    last_price = q.get('lastTradePrice') or 0

    # Imbalance
    if ask_size > 0:
        imbalance = bid_size / ask_size
    else:
        imbalance = 1.0

    # Signal
    if imbalance > 2.0:
        signal = "STRONG_BID"
    elif imbalance > 1.2:
        signal = "WEAK_BID"
    elif imbalance < 0.5:
        signal = "STRONG_ASK"
    elif imbalance < 0.8:
        signal = "WEAK_ASK"
    else:
        signal = "BALANCED"

    # Spread
    mid_price = (bid_price + ask_price) / 2 if (bid_price + ask_price) > 0 else 1
    spread = ask_price - bid_price
    spread_bps = (spread / mid_price) * 10000 if mid_price > 0 else 0

    return {
        "ticker": ticker.upper(),
        "last_trade": {
            "price": last_price,
            "size": last_size,
            "tick": last_tick,
            "direction": "BUY" if last_tick == "Up" else "SELL" if last_tick == "Down" else "NEUTRAL"
        },
        "bid_ask": {
            "bid_price": bid_price,
            "bid_size": bid_size,
            "ask_price": ask_price,
            "ask_size": ask_size,
            "spread": round(spread, 4),
            "spread_bps": round(spread_bps, 1)
        },
        "imbalance": {
            "ratio": round(imbalance, 2),
            "signal": signal
        },
        "interpretation": f"Last trade: {last_tick} ({last_size} shares) | {signal}"
    }
