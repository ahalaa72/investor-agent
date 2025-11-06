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
    
    @staticmethod
    def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Average True Range (ATR) for volatility measurement."""
        # True Range calculation
        high_low = high - low
        high_close = np.abs(high - np.roll(close, 1))
        low_close = np.abs(low - np.roll(close, 1))
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        true_range[0] = high_low[0]  # First value
        
        # ATR is EMA of True Range
        atr = pd.Series(true_range).ewm(span=period, adjust=False).mean().values
        
        return atr
    
    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> float:
        """Volume Weighted Average Price."""
        typical_price = (df['High'] + df['Low'] + df['Close']) / 3
        vwap = (typical_price * df['Volume']).sum() / df['Volume'].sum()
        return vwap
    
    @staticmethod
    def calculate_obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """On Balance Volume."""
        obv = np.zeros(len(close))
        obv[0] = volume[0]
        
        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                obv[i] = obv[i-1] + volume[i]
            elif close[i] < close[i-1]:
                obv[i] = obv[i-1] - volume[i]
            else:
                obv[i] = obv[i-1]
        
        return obv
    
    @staticmethod
    def calculate_mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray, 
                     volume: np.ndarray, period: int = 14) -> np.ndarray:
        """Money Flow Index."""
        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume
        
        mfi = np.zeros(len(close))
        
        for i in range(period, len(close)):
            positive_flow = 0
            negative_flow = 0
            
            for j in range(i - period + 1, i + 1):
                if typical_price[j] > typical_price[j-1]:
                    positive_flow += money_flow[j]
                elif typical_price[j] < typical_price[j-1]:
                    negative_flow += money_flow[j]
            
            if negative_flow == 0:
                mfi[i] = 100
            else:
                money_ratio = positive_flow / negative_flow
                mfi[i] = 100 - (100 / (1 + money_ratio))
        
        return mfi


class VolumeAnalysis:
    """Volume-specific analysis tools."""
    
    @staticmethod
    def calculate_volume_profile(df: pd.DataFrame, num_bins: int = 20) -> Dict[str, Any]:
        """Calculate volume profile (volume by price level)."""
        # Create price bins
        price_range = df['High'].max() - df['Low'].min()
        bin_size = price_range / num_bins
        
        # Initialize bins
        volume_by_price = {}
        
        for _, row in df.iterrows():
            # Approximate which price bin this bar contributed to
            avg_price = (row['High'] + row['Low'] + row['Close']) / 3
            bin_index = int((avg_price - df['Low'].min()) / bin_size)
            bin_index = min(bin_index, num_bins - 1)  # Cap at max bin
            
            bin_price = df['Low'].min() + (bin_index * bin_size) + (bin_size / 2)
            
            if bin_price not in volume_by_price:
                volume_by_price[bin_price] = 0
            volume_by_price[bin_price] += row['Volume']
        
        # Find POC (Point of Control) - price with most volume
        poc_price = max(volume_by_price, key=volume_by_price.get)
        max_volume = volume_by_price[poc_price]
        
        # Calculate Value Area (70% of volume)
        sorted_prices = sorted(volume_by_price.items(), key=lambda x: x[1], reverse=True)
        total_volume = sum(volume_by_price.values())
        value_area_volume = total_volume * 0.70
        
        cumulative_volume = 0
        value_area_prices = []
        
        for price, vol in sorted_prices:
            cumulative_volume += vol
            value_area_prices.append(price)
            if cumulative_volume >= value_area_volume:
                break
        
        value_area_high = max(value_area_prices)
        value_area_low = min(value_area_prices)
        
        return {
            "poc": poc_price,
            "value_area_high": value_area_high,
            "value_area_low": value_area_low,
            "volume_by_price": volume_by_price
        }
    
    @staticmethod
    def detect_volume_surges(df: pd.DataFrame, threshold: float = 2.0) -> List[Dict[str, Any]]:
        """Detect volume surges above average."""
        avg_volume = df['Volume'].rolling(window=20).mean()
        surges = []
        
        for i in range(20, len(df)):
            if df['Volume'].iloc[i] > avg_volume.iloc[i] * threshold:
                price_change = (df['Close'].iloc[i] - df['Close'].iloc[i-1]) / df['Close'].iloc[i-1] * 100
                
                surges.append({
                    "date": df.index[i].strftime('%Y-%m-%d'),
                    "volume": int(df['Volume'].iloc[i]),
                    "vs_average": df['Volume'].iloc[i] / avg_volume.iloc[i],
                    "price_change": price_change
                })
        
        return surges[-5:]  # Return last 5 surges


class VolatilityAnalysis:
    """Volatility-specific analysis tools."""
    
    @staticmethod
    def calculate_historical_volatility(returns: np.ndarray, period: int, annualize: bool = True) -> float:
        """Calculate historical volatility."""
        if len(returns) < period:
            return np.nan
        
        recent_returns = returns[-period:]
        volatility = np.std(recent_returns)
        
        if annualize:
            volatility *= np.sqrt(252)  # Annualize
        
        return volatility * 100  # Return as percentage
    
    @staticmethod
    def classify_volatility_regime(current_vol: float, historical_vols: np.ndarray) -> Tuple[float, str]:
        """Classify current volatility regime."""
        percentile = (historical_vols < current_vol).sum() / len(historical_vols) * 100
        
        if percentile < 25:
            regime = "Low"
        elif percentile < 75:
            regime = "Normal"
        elif percentile < 90:
            regime = "High"
        else:
            regime = "Extreme"
        
        return percentile, regime


class RelativeStrengthAnalysis:
    """Relative Strength analysis tools."""
    
    @staticmethod
    def calculate_rs_score(stock_returns: np.ndarray, benchmark_returns: np.ndarray) -> float:
        """Calculate IBD-style Relative Strength score (0-100)."""
        # Calculate cumulative returns
        stock_cumulative = (1 + stock_returns).prod() - 1
        benchmark_cumulative = (1 + benchmark_returns).prod() - 1
        
        # RS Line = Stock / Benchmark performance
        rs_value = stock_cumulative - benchmark_cumulative
        
        # Normalize to 0-100 scale (simplified version)
        # In real IBD, this is percentile ranked against all stocks
        # Here we use a simpler normalization
        if rs_value > 0.5:
            score = 90 + (rs_value - 0.5) * 20  # 90-100 range
        elif rs_value > 0.2:
            score = 70 + (rs_value - 0.2) * 66.67  # 70-90 range
        elif rs_value > -0.2:
            score = 30 + (rs_value + 0.2) * 100  # 30-70 range
        elif rs_value > -0.5:
            score = 10 + (rs_value + 0.5) * 66.67  # 10-30 range
        else:
            score = max(0, 10 + rs_value * 20)  # 0-10 range
        
        return min(100, max(0, score))


class FundamentalScoring:
    """Fundamental analysis scoring systems."""
    
    @staticmethod
    def calculate_piotroski_f_score(financials: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Calculate Piotroski F-Score (0-9)."""
        score = 0
        details = {}
        
        try:
            # Get income statement and balance sheet
            income = financials.get('income')
            balance = financials.get('balance')
            cash_flow = financials.get('cash')
            
            if income is None or balance is None:
                return {"score": 0, "error": "Insufficient financial data"}
            
            # PROFITABILITY (4 points)
            # 1. Positive ROA
            try:
                net_income = income.iloc[:, 0].get('Net Income', 0)
                total_assets = balance.iloc[:, 0].get('Total Assets', 1)
                roa = net_income / total_assets if total_assets != 0 else 0
                
                if roa > 0:
                    score += 1
                    details['positive_roe'] = True
                else:
                    details['positive_roe'] = False
            except:
                details['positive_roe'] = False
            
            # 2. Positive Operating Cash Flow
            if cash_flow is not None:
                try:
                    operating_cf = cash_flow.iloc[:, 0].get('Operating Cash Flow', 0)
                    if operating_cf > 0:
                        score += 1
                        details['positive_operating_cf'] = True
                    else:
                        details['positive_operating_cf'] = False
                except:
                    details['positive_operating_cf'] = False
            
            # 3. ROA increase (compare to previous period)
            if len(income.columns) >= 2 and len(balance.columns) >= 2:
                try:
                    net_income_prev = income.iloc[:, 1].get('Net Income', 0)
                    total_assets_prev = balance.iloc[:, 1].get('Total Assets', 1)
                    roa_prev = net_income_prev / total_assets_prev if total_assets_prev != 0 else 0
                    
                    if roa > roa_prev:
                        score += 1
                        details['roa_increase'] = True
                    else:
                        details['roa_increase'] = False
                except:
                    details['roa_increase'] = False
            
            # 4. CF > NI (quality of earnings)
            if cash_flow is not None:
                try:
                    operating_cf = cash_flow.iloc[:, 0].get('Operating Cash Flow', 0)
                    net_income = income.iloc[:, 0].get('Net Income', 0)
                    
                    if operating_cf > net_income:
                        score += 1
                        details['cf_vs_ni'] = True
                    else:
                        details['cf_vs_ni'] = False
                except:
                    details['cf_vs_ni'] = False
            
            # LEVERAGE/LIQUIDITY (3 points)
            # 5. Decrease in long-term debt
            if len(balance.columns) >= 2:
                try:
                    lt_debt = balance.iloc[:, 0].get('Long Term Debt', 0)
                    lt_debt_prev = balance.iloc[:, 1].get('Long Term Debt', 0)
                    
                    if lt_debt < lt_debt_prev:
                        score += 1
                        details['debt_decrease'] = True
                    else:
                        details['debt_decrease'] = False
                except:
                    details['debt_decrease'] = False
            
            # 6. Increase in current ratio
            if len(balance.columns) >= 2:
                try:
                    current_assets = balance.iloc[:, 0].get('Current Assets', 0)
                    current_liab = balance.iloc[:, 0].get('Current Liabilities', 1)
                    current_ratio = current_assets / current_liab if current_liab != 0 else 0
                    
                    current_assets_prev = balance.iloc[:, 1].get('Current Assets', 0)
                    current_liab_prev = balance.iloc[:, 1].get('Current Liabilities', 1)
                    current_ratio_prev = current_assets_prev / current_liab_prev if current_liab_prev != 0 else 0
                    
                    if current_ratio > current_ratio_prev:
                        score += 1
                        details['current_ratio_increase'] = True
                    else:
                        details['current_ratio_increase'] = False
                except:
                    details['current_ratio_increase'] = False
            
            # 7. No new shares issued (simplified - check if shares outstanding decreased)
            details['shares_decrease'] = False  # Placeholder
            
            # OPERATING EFFICIENCY (2 points)
            # 8. Increase in gross margin
            if len(income.columns) >= 2:
                try:
                    revenue = income.iloc[:, 0].get('Total Revenue', 1)
                    gross_profit = income.iloc[:, 0].get('Gross Profit', 0)
                    margin = gross_profit / revenue if revenue != 0 else 0
                    
                    revenue_prev = income.iloc[:, 1].get('Total Revenue', 1)
                    gross_profit_prev = income.iloc[:, 1].get('Gross Profit', 0)
                    margin_prev = gross_profit_prev / revenue_prev if revenue_prev != 0 else 0
                    
                    if margin > margin_prev:
                        score += 1
                        details['margin_increase'] = True
                    else:
                        details['margin_increase'] = False
                except:
                    details['margin_increase'] = False
            
            # 9. Increase in asset turnover
            details['turnover_increase'] = False  # Placeholder
            
            return {
                "score": score,
                "max_score": 9,
                "details": details
            }
        
        except Exception as e:
            return {
                "score": 0,
                "error": f"Error calculating F-Score: {str(e)}"
            }
    
    @staticmethod
    def calculate_altman_z_score(balance: pd.DataFrame, income: pd.DataFrame) -> Dict[str, Any]:
        """Calculate Altman Z-Score for bankruptcy prediction."""
        try:
            # Get most recent period data
            total_assets = balance.iloc[:, 0].get('Total Assets', 1)
            current_assets = balance.iloc[:, 0].get('Current Assets', 0)
            current_liabilities = balance.iloc[:, 0].get('Current Liabilities', 0)
            total_liabilities = balance.iloc[:, 0].get('Total Liabilities Net Minority Interest', 0)
            retained_earnings = balance.iloc[:, 0].get('Retained Earnings', 0)
            ebit = income.iloc[:, 0].get('EBIT', 0)
            total_equity = balance.iloc[:, 0].get('Total Equity Gross Minority Interest', 1)
            revenue = income.iloc[:, 0].get('Total Revenue', 0)
            
            # Altman Z-Score formula for public companies
            # Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
            
            x1 = (current_assets - current_liabilities) / total_assets  # Working Capital / Total Assets
            x2 = retained_earnings / total_assets  # Retained Earnings / Total Assets
            x3 = ebit / total_assets  # EBIT / Total Assets
            x4 = total_equity / total_liabilities if total_liabilities != 0 else 0  # Market Value of Equity / Total Liabilities
            x5 = revenue / total_assets  # Sales / Total Assets
            
            z_score = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
            
            # Interpret Z-Score
            if z_score > 2.99:
                zone = "Safe"
                risk = "Low"
            elif z_score > 1.81:
                zone = "Grey"
                risk = "Medium"
            else:
                zone = "Distress"
                risk = "High"
            
            return {
                "score": round(z_score, 2),
                "zone": zone,
                "bankruptcy_risk": risk,
                "components": {
                    "working_capital_ratio": round(x1, 3),
                    "retained_earnings_ratio": round(x2, 3),
                    "ebit_ratio": round(x3, 3),
                    "equity_to_liab_ratio": round(x4, 3),
                    "asset_turnover": round(x5, 3)
                }
            }
        
        except Exception as e:
            return {
                "score": 0,
                "error": f"Error calculating Z-Score: {str(e)}"
            }


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
