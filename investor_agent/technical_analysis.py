"""
Technical Analysis Module for Investor Agent
Pure Python implementations that don't require TA-Lib
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
from typing import Dict, List, Any, Tuple


class TechnicalIndicators:
    """Pure Python technical indicators implementation."""
    
    @staticmethod
    def calculate_sma(data: np.ndarray, period: int) -> np.ndarray:
        """Simple Moving Average."""
        return pd.Series(data).rolling(window=period).mean().values
    
    @staticmethod
    def calculate_ema(data: np.ndarray, period: int) -> np.ndarray:
        """Exponential Moving Average."""
        return pd.Series(data).ewm(span=period, adjust=False).mean().values
    
    @staticmethod
    def calculate_rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
        """Relative Strength Index."""
        deltas = np.diff(data)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        
        if down == 0:
            return np.full(len(data), 100.0)
        
        rs = up / down
        rsi = np.zeros_like(data)
        rsi[:period] = 100. - 100./(1. + rs)
        
        for i in range(period, len(data)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta
            
            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            
            rs = up / down if down != 0 else 0
            rsi[i] = 100. - 100./(1. + rs)
        
        return rsi
    
    @staticmethod
    def calculate_macd(data: np.ndarray, 
                      fast_period: int = 12, 
                      slow_period: int = 26, 
                      signal_period: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """MACD (Moving Average Convergence Divergence)."""
        ema_fast = TechnicalIndicators.calculate_ema(data, fast_period)
        ema_slow = TechnicalIndicators.calculate_ema(data, slow_period)
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.calculate_ema(macd_line, signal_period)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_bollinger_bands(data: np.ndarray, 
                                  period: int = 20, 
                                  std_dev: int = 2) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Bollinger Bands."""
        sma = TechnicalIndicators.calculate_sma(data, period)
        rolling_std = pd.Series(data).rolling(window=period).std().values
        
        upper_band = sma + (rolling_std * std_dev)
        lower_band = sma - (rolling_std * std_dev)
        
        return upper_band, sma, lower_band
    
    @staticmethod
    def calculate_stochastic(high: np.ndarray, 
                            low: np.ndarray, 
                            close: np.ndarray, 
                            period: int = 14,
                            smooth_k: int = 3,
                            smooth_d: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """Stochastic Oscillator."""
        lowest_low = pd.Series(low).rolling(window=period).min().values
        highest_high = pd.Series(high).rolling(window=period).max().values
        
        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        k = pd.Series(k).rolling(window=smooth_k).mean().values
        d = pd.Series(k).rolling(window=smooth_d).mean().values
        
        return k, d


class TechnicalAnalysis:
    """Advanced technical analysis functions."""
    
    @staticmethod
    def calculate_comprehensive_indicators(df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate all technical indicators at once."""
        closes = df['Close'].values
        highs = df['High'].values
        lows = df['Low'].values
        
        # Calculate indicators
        rsi = TechnicalIndicators.calculate_rsi(closes)
        macd, signal, histogram = TechnicalIndicators.calculate_macd(closes)
        upper_bb, middle_bb, lower_bb = TechnicalIndicators.calculate_bollinger_bands(closes)
        sma_20 = TechnicalIndicators.calculate_sma(closes, 20)
        sma_50 = TechnicalIndicators.calculate_sma(closes, 50)
        sma_200 = TechnicalIndicators.calculate_sma(closes, 200)
        ema_20 = TechnicalIndicators.calculate_ema(closes, 20)
        stoch_k, stoch_d = TechnicalIndicators.calculate_stochastic(highs, lows, closes)
        
        current_price = closes[-1]
        current_rsi = rsi[-1] if not np.isnan(rsi[-1]) else 50
        current_macd = macd[-1] if not np.isnan(macd[-1]) else 0
        current_signal = signal[-1] if not np.isnan(signal[-1]) else 0
        
        return {
            "current_price": f"${current_price:.2f}",
            "rsi": {
                "value": f"{current_rsi:.2f}",
                "signal": "Overbought" if current_rsi > 70 else "Oversold" if current_rsi < 30 else "Neutral"
            },
            "macd": {
                "macd": f"{current_macd:.4f}",
                "signal": f"{current_signal:.4f}",
                "histogram": f"{histogram[-1]:.4f}" if not np.isnan(histogram[-1]) else "N/A",
                "trend": "Bullish" if current_macd > current_signal else "Bearish"
            },
            "bollinger_bands": {
                "upper": f"${upper_bb[-1]:.2f}" if not np.isnan(upper_bb[-1]) else "N/A",
                "middle": f"${middle_bb[-1]:.2f}" if not np.isnan(middle_bb[-1]) else "N/A",
                "lower": f"${lower_bb[-1]:.2f}" if not np.isnan(lower_bb[-1]) else "N/A",
                "position": TechnicalAnalysis._bb_position(current_price, upper_bb[-1], lower_bb[-1])
            },
            "moving_averages": {
                "sma_20": f"${sma_20[-1]:.2f}" if not np.isnan(sma_20[-1]) else "N/A",
                "sma_50": f"${sma_50[-1]:.2f}" if not np.isnan(sma_50[-1]) else "N/A",
                "sma_200": f"${sma_200[-1]:.2f}" if not np.isnan(sma_200[-1]) else "N/A",
                "ema_20": f"${ema_20[-1]:.2f}" if not np.isnan(ema_20[-1]) else "N/A",
                "trend": TechnicalAnalysis._determine_trend(current_price, sma_50[-1], sma_200[-1])
            },
            "stochastic": {
                "k": f"{stoch_k[-1]:.2f}" if not np.isnan(stoch_k[-1]) else "N/A",
                "d": f"{stoch_d[-1]:.2f}" if not np.isnan(stoch_d[-1]) else "N/A",
                "signal": TechnicalAnalysis._stoch_signal(stoch_k[-1])
            }
        }
    
    @staticmethod
    def _bb_position(price: float, upper: float, lower: float) -> str:
        """Determine price position relative to Bollinger Bands."""
        if np.isnan(upper) or np.isnan(lower):
            return "N/A"
        if price > upper:
            return "Above Upper Band"
        elif price < lower:
            return "Below Lower Band"
        else:
            return "Within Bands"
    
    @staticmethod
    def _determine_trend(price: float, sma50: float, sma200: float) -> str:
        """Determine overall trend."""
        if np.isnan(sma50) or np.isnan(sma200):
            return "Insufficient Data"
        if price > sma50 and price > sma200:
            return "Bullish"
        elif price < sma50 and price < sma200:
            return "Bearish"
        else:
            return "Mixed"
    
    @staticmethod
    def _stoch_signal(k_value: float) -> str:
        """Determine stochastic signal."""
        if np.isnan(k_value):
            return "N/A"
        if k_value > 80:
            return "Overbought"
        elif k_value < 20:
            return "Oversold"
        else:
            return "Neutral"
    
    @staticmethod
    def find_support_resistance(df: pd.DataFrame, order: int = 5) -> Dict[str, Any]:
        """Find support and resistance levels using local extrema."""
        highs = df['High'].values
        lows = df['Low'].values
        closes = df['Close'].values
        
        # Find local maxima (resistance) and minima (support)
        resistance_indices = argrelextrema(highs, np.greater, order=order)[0]
        support_indices = argrelextrema(lows, np.less, order=order)[0]
        
        # Get the levels
        resistance_levels = sorted(highs[resistance_indices], reverse=True)[:3]
        support_levels = sorted(lows[support_indices])[:3]
        
        return {
            "current_price": f"${closes[-1]:.2f}",
            "resistance_levels": [f"${level:.2f}" for level in resistance_levels],
            "support_levels": [f"${level:.2f}" for level in support_levels],
            "nearest_resistance": f"${resistance_levels[0]:.2f}" if resistance_levels else "N/A",
            "nearest_support": f"${support_levels[-1]:.2f}" if support_levels else "N/A"
        }
    
    @staticmethod
    def calculate_trend_strength(df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate trend strength score."""
        closes = df['Close'].values
        
        indicators = TechnicalAnalysis.calculate_comprehensive_indicators(df)
        
        # Calculate strength score (0-100)
        score = 0
        analysis = []
        
        # RSI contribution (25 points)
        rsi_val = float(indicators['rsi']['value'])
        if 40 < rsi_val < 70:
            score += 25
            analysis.append("RSI in healthy range")
        elif rsi_val > 70:
            score += 10
            analysis.append("RSI overbought (caution)")
        elif rsi_val < 30:
            score += 10
            analysis.append("RSI oversold (potential reversal)")
        
        # MACD contribution (25 points)
        if indicators['macd']['trend'] == "Bullish":
            score += 25
            analysis.append("MACD bullish crossover")
        else:
            analysis.append("MACD bearish")
        
        # Moving average trend (30 points)
        if indicators['moving_averages']['trend'] == "Bullish":
            score += 30
            analysis.append("Price above key moving averages")
        elif indicators['moving_averages']['trend'] == "Bearish":
            analysis.append("Price below key moving averages")
        
        # Bollinger bands position (20 points)
        bb_pos = indicators['bollinger_bands']['position']
        if bb_pos == "Within Bands":
            score += 20
            analysis.append("Trading within Bollinger Bands")
        elif bb_pos == "Above Upper Band":
            score += 10
            analysis.append("Extended above Bollinger Bands")
        
        # Overall assessment
        if score >= 70:
            overall = "Strong Bullish Trend"
        elif score >= 50:
            overall = "Moderate Bullish Trend"
        elif score >= 30:
            overall = "Weak Bullish / Consolidating"
        else:
            overall = "Bearish or Weak"
        
        return {
            "trend_strength_score": score,
            "max_score": 100,
            "overall_assessment": overall,
            "analysis_points": analysis,
            "indicators_summary": indicators
        }
    
    @staticmethod
    def screen_stocks(stock_data: Dict[str, pd.DataFrame], 
                     criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Screen stocks based on technical criteria."""
        results = []
        
        for symbol, df in stock_data.items():
            try:
                indicators = TechnicalAnalysis.calculate_comprehensive_indicators(df)
                
                matches = True
                matched_criteria = []
                
                # Check RSI criteria
                if 'rsi_below' in criteria:
                    rsi_val = float(indicators['rsi']['value'])
                    if rsi_val >= criteria['rsi_below']:
                        matches = False
                    else:
                        matched_criteria.append(f"RSI below {criteria['rsi_below']}")
                
                if 'rsi_above' in criteria:
                    rsi_val = float(indicators['rsi']['value'])
                    if rsi_val <= criteria['rsi_above']:
                        matches = False
                    else:
                        matched_criteria.append(f"RSI above {criteria['rsi_above']}")
                
                # Check moving average criteria
                if criteria.get('above_sma50'):
                    if indicators['moving_averages']['trend'] not in ["Bullish", "Mixed"]:
                        matches = False
                    else:
                        matched_criteria.append("Above SMA50")
                
                # Check MACD criteria
                if criteria.get('macd_bullish'):
                    if indicators['macd']['trend'] != "Bullish":
                        matches = False
                    else:
                        matched_criteria.append("MACD Bullish")
                
                if matches:
                    results.append({
                        "symbol": symbol,
                        "current_price": indicators['current_price'],
                        "rsi": indicators['rsi']['value'],
                        "rsi_signal": indicators['rsi']['signal'],
                        "macd_trend": indicators['macd']['trend'],
                        "ma_trend": indicators['moving_averages']['trend'],
                        "matched_criteria": matched_criteria
                    })
            
            except Exception as e:
                # Skip stocks that error
                continue
        
        return results
    
    @staticmethod
    def detect_patterns(df: pd.DataFrame) -> Dict[str, Any]:
        """Detect common chart patterns."""
        closes = df['Close'].values
        highs = df['High'].values
        lows = df['Low'].values
        
        patterns_detected = []
        
        # Simple pattern detection
        recent_closes = closes[-20:]
        
        # Golden Cross / Death Cross
        sma_50 = TechnicalIndicators.calculate_sma(closes, 50)
        sma_200 = TechnicalIndicators.calculate_sma(closes, 200)
        
        if len(sma_50) > 1 and len(sma_200) > 1:
            if sma_50[-2] < sma_200[-2] and sma_50[-1] > sma_200[-1]:
                patterns_detected.append({
                    "pattern": "Golden Cross",
                    "description": "50-day MA crossed above 200-day MA",
                    "signal": "Bullish"
                })
            elif sma_50[-2] > sma_200[-2] and sma_50[-1] < sma_200[-1]:
                patterns_detected.append({
                    "pattern": "Death Cross",
                    "description": "50-day MA crossed below 200-day MA",
                    "signal": "Bearish"
                })
        
        # Bullish/Bearish trends
        if len(recent_closes) >= 10:
            if np.all(np.diff(recent_closes[-10:]) > 0):
                patterns_detected.append({
                    "pattern": "Strong Uptrend",
                    "description": "Consistent upward movement in last 10 days",
                    "signal": "Bullish"
                })
            elif np.all(np.diff(recent_closes[-10:]) < 0):
                patterns_detected.append({
                    "pattern": "Strong Downtrend",
                    "description": "Consistent downward movement in last 10 days",
                    "signal": "Bearish"
                })
        
        # Consolidation
        recent_std = np.std(recent_closes)
        overall_std = np.std(closes)
        if recent_std < overall_std * 0.5:
            patterns_detected.append({
                "pattern": "Consolidation",
                "description": "Price trading in narrow range",
                "signal": "Neutral"
            })
        
        return {
            "patterns_found": len(patterns_detected),
            "patterns": patterns_detected if patterns_detected else [{"pattern": "None", "description": "No clear patterns detected", "signal": "Neutral"}]
        }
