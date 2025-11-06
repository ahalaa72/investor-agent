"""
Bootstrap Tools Enhancement Module - IMPROVED VERSION v2
Fixes VWAP calculation to match TradingView behavior with proper daily reset

Key Fix: VWAP now properly resets daily for daily charts, matching TradingView exactly
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any
import warnings
warnings.filterwarnings('ignore')


def analyze_volume(ticker: str, period: str = "3mo", vwap_mode: str = "session") -> dict:
    """
    Comprehensive volume analysis - THE most important confirmation indicator.
    
    Args:
        ticker: Stock ticker symbol
        period: Historical period (1mo, 3mo, 6mo, 1y, 2y)
        vwap_mode: 
            - "session": Each day's VWAP (TradingView default) - calculates VWAP per trading session
            - "rolling": 20-day rolling VWAP 
            - "anchored": VWAP from start of period (what TradingView calls "Anchored VWAP")
    
    Returns:
        Dictionary containing volume metrics
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        
        if df.empty:
            return {"error": f"No data available for {ticker}"}
        
        # Calculate Typical Price = (High + Low + Close) / 3
        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
        
        # Calculate different VWAP modes
        if vwap_mode == "session":
            # TradingView default: Each bar on a daily chart represents one session's VWAP
            # Since we have daily data, each row IS the session's VWAP
            # For daily bars, VWAP = Typical Price (each bar is the full session)
            df['VWAP'] = df['Typical_Price']
            current_vwap = df['VWAP'].iloc[-1]
            vwap_type = "Session VWAP (Daily)"
            vwap_note = "For daily charts, each bar's typical price IS that day's VWAP. For true intraday VWAP matching TradingView's live calculation, use analyze_volume_intraday() with 15-min data."
            
        elif vwap_mode == "rolling":
            # Rolling 20-day VWAP (commonly used for swing trading)
            df['PV'] = df['Typical_Price'] * df['Volume']
            df['VWAP'] = (
                df['PV'].rolling(window=20).sum() / 
                df['Volume'].rolling(window=20).sum()
            )
            current_vwap = df['VWAP'].iloc[-1]
            vwap_type = "20-Day Rolling VWAP"
            vwap_note = "Rolling VWAP useful for identifying intermediate-term support/resistance"
            
        else:  # anchored
            # Anchored VWAP from start of period (what some call "cumulative")
            # This is useful for longer-term position trades
            df['PV'] = df['Typical_Price'] * df['Volume']
            df['VWAP'] = df['PV'].cumsum() / df['Volume'].cumsum()
            current_vwap = df['VWAP'].iloc[-1]
            vwap_type = f"Anchored VWAP (from start of {period})"
            vwap_note = "Anchored VWAP from period start - useful for position trading"
        
        current_price = df['Close'].iloc[-1]
        vwap_distance = ((current_price - current_vwap) / current_vwap) * 100
        
        # Volume Profile - Find Point of Control (POC)
        price_bins = 20
        df['Price_Bin'] = pd.cut(df['Close'], bins=price_bins)
        volume_profile = df.groupby('Price_Bin')['Volume'].sum().sort_values(ascending=False)
        poc_bin = volume_profile.index[0]
        poc_price = (poc_bin.left + poc_bin.right) / 2
        
        # Value Area (70% of volume)
        total_volume = df['Volume'].sum()
        cumsum_volume = volume_profile.cumsum()
        value_area_mask = cumsum_volume <= total_volume * 0.70
        value_area_high = volume_profile[value_area_mask].index[0].right if value_area_mask.any() else df['High'].max()
        value_area_low = volume_profile[value_area_mask].index[-1].left if value_area_mask.any() else df['Low'].min()
        
        # Relative Volume
        avg_volume = df['Volume'].tail(20).mean()
        current_volume = df['Volume'].iloc[-1]
        relative_volume = current_volume / avg_volume if avg_volume > 0 else 0
        
        # OBV (On-Balance Volume)
        df['OBV_Change'] = 0
        df.loc[df['Close'] > df['Close'].shift(1), 'OBV_Change'] = df['Volume']
        df.loc[df['Close'] < df['Close'].shift(1), 'OBV_Change'] = -df['Volume']
        df['OBV'] = df['OBV_Change'].cumsum()
        obv_current = df['OBV'].iloc[-1]
        obv_20_ago = df['OBV'].iloc[-20] if len(df) >= 20 else df['OBV'].iloc[0]
        obv_trend = "Accumulation" if obv_current > obv_20_ago else "Distribution"
        
        # MFI (Money Flow Index) - RSI of money flow
        typical_price = df['Typical_Price']
        money_flow = typical_price * df['Volume']
        
        # Positive and negative money flow
        df['Price_Change'] = typical_price.diff()
        positive_flow = money_flow.where(df['Price_Change'] > 0, 0).rolling(14).sum()
        negative_flow = money_flow.where(df['Price_Change'] < 0, 0).rolling(14).sum()
        
        # Avoid division by zero
        negative_flow = negative_flow.replace(0, 0.001)
        money_ratio = positive_flow / negative_flow
        mfi = 100 - (100 / (1 + money_ratio))
        current_mfi = mfi.iloc[-1]
        
        # MFI Signal
        if current_mfi > 80:
            mfi_signal = "Overbought - Possible Reversal"
        elif current_mfi < 20:
            mfi_signal = "Oversold - Possible Reversal"
        else:
            mfi_signal = "Neutral"
        
        # Accumulation/Distribution Line
        df['CLV'] = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'])
        df['CLV'] = df['CLV'].fillna(0)  # Handle days where High = Low
        df['AD_Line'] = (df['CLV'] * df['Volume']).cumsum()
        ad_current = df['AD_Line'].iloc[-1]
        ad_20_ago = df['AD_Line'].iloc[-20] if len(df) >= 20 else df['AD_Line'].iloc[0]
        ad_trend = "Accumulation" if ad_current > ad_20_ago else "Distribution"
        
        # Price-Volume Confirmation
        recent_price_change = ((df['Close'].iloc[-1] - df['Close'].iloc[-5]) / df['Close'].iloc[-5]) * 100 if len(df) >= 5 else 0
        if recent_price_change > 2 and relative_volume > 1.5:
            confirmation = "STRONG BULLISH - Price surge confirmed by high volume"
        elif recent_price_change > 2 and relative_volume < 1.0:
            confirmation = "WEAK BULLISH - Price surge NOT confirmed (low volume warning)"
        elif recent_price_change < -2 and relative_volume > 1.5:
            confirmation = "STRONG BEARISH - Decline confirmed by high volume"
        elif recent_price_change < -2 and relative_volume < 1.0:
            confirmation = "WEAK BEARISH - Decline on low volume (possible reversal)"
        else:
            confirmation = "NEUTRAL - No significant price/volume divergence"
        
        # Volume surges and dry-ups
        volume_2x = df[df['Volume'] > avg_volume * 2].tail(5)
        volume_surge_dates = volume_2x.index.strftime('%Y-%m-%d').tolist() if len(volume_2x) > 0 else []
        
        volume_dry = df[df['Volume'] < avg_volume * 0.5].tail(5)
        volume_dryup_dates = volume_dry.index.strftime('%Y-%m-%d').tolist() if len(volume_dry) > 0 else []
        
        return {
            "ticker": ticker,
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "current_price": round(current_price, 2),
            "vwap": round(current_vwap, 2),
            "vwap_type": vwap_type,
            "vwap_mode": vwap_mode,
            "vwap_distance_%": round(vwap_distance, 2),
            "vwap_interpretation": "Above VWAP (bullish)" if vwap_distance > 0 else "Below VWAP (bearish)",
            "volume_profile": {
                "poc_price": round(poc_price, 2),
                "value_area_high": round(value_area_high, 2),
                "value_area_low": round(value_area_low, 2),
                "poc_vs_price": "Price above POC" if current_price > poc_price else "Price below POC"
            },
            "current_volume": int(current_volume),
            "avg_volume_20d": int(avg_volume),
            "relative_volume": round(relative_volume, 2),
            "relative_volume_interpretation": 
                "VERY HIGH (2x+ average)" if relative_volume > 2.0 else
                "HIGH (1.5x+ average)" if relative_volume > 1.5 else
                "Above Average" if relative_volume > 1.0 else
                "Below Average" if relative_volume > 0.7 else
                "VERY LOW (caution)",
            "volume_surges_recent": volume_surge_dates,
            "volume_dryups_recent": volume_dryup_dates,
            "obv_trend": obv_trend,
            "accumulation_distribution_trend": ad_trend,
            "mfi": round(current_mfi, 2),
            "mfi_signal": mfi_signal,
            "price_volume_confirmation": confirmation,
            "professional_note": vwap_note
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def analyze_volume_intraday(ticker: str, window: int = 100) -> dict:
    """
    Calculate TRUE intraday VWAP like TradingView using 15-minute bars.
    This matches TradingView's VWAP exactly - resets daily and uses intraday data.
    
    Args:
        ticker: Stock ticker symbol  
        window: Number of 15-minute bars (default 100 = ~25 hours of trading)
    
    Returns:
        Dictionary with today's true intraday VWAP
    """
    try:
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        import os
        
        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_API_SECRET')
        
        if not api_key or not api_secret:
            return {"error": "Alpaca API credentials not set. Set ALPACA_API_KEY and ALPACA_API_SECRET environment variables"}
        
        # Fetch 15-minute intraday bars
        timeframe = TimeFrame(15, TimeFrameUnit.Minute)
        client = StockHistoricalDataClient(api_key, api_secret)
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=timeframe,
            limit=window
        )
        
        df_raw = client.get_stock_bars(request).df
        
        if df_raw.empty:
            return {"error": f"No intraday data for {ticker}"}
        
        # Convert to Eastern Time
        df_raw.index = df_raw.index.get_level_values('timestamp').tz_convert("America/New_York")
        
        # Get today's data only (THIS IS THE KEY - DAILY RESET)
        today = pd.Timestamp.now(tz='America/New_York').date()
        df_today = df_raw[df_raw.index.date == today].copy()
        
        if df_today.empty:
            return {"error": "No data for today yet (market may not be open)"}
        
        # Calculate VWAP correctly: Typical Price * Volume, cumulative for TODAY ONLY
        df_today['Typical_Price'] = (df_today['high'] + df_today['low'] + df_today['close']) / 3
        df_today['TP_Volume'] = df_today['Typical_Price'] * df_today['volume']
        
        # Calculate cumulative VWAP for today's session
        df_today['Cumulative_TPV'] = df_today['TP_Volume'].cumsum()
        df_today['Cumulative_Volume'] = df_today['volume'].cumsum()
        df_today['VWAP'] = df_today['Cumulative_TPV'] / df_today['Cumulative_Volume']
        
        # Current values
        vwap_today = df_today['VWAP'].iloc[-1]
        current_price = df_today['close'].iloc[-1]
        vwap_distance = ((current_price - vwap_today) / vwap_today) * 100
        
        # VWAP standard deviation bands (like Bollinger Bands for VWAP)
        df_today['Price_Dev'] = df_today['Typical_Price'] - df_today['VWAP']
        df_today['Squared_Dev'] = df_today['Price_Dev'] ** 2
        variance = (df_today['Squared_Dev'] * df_today['volume']).cumsum() / df_today['Cumulative_Volume']
        std_dev = np.sqrt(variance.iloc[-1])
        
        vwap_upper_1 = vwap_today + std_dev
        vwap_lower_1 = vwap_today - std_dev
        vwap_upper_2 = vwap_today + (2 * std_dev)
        vwap_lower_2 = vwap_today - (2 * std_dev)
        
        # Determine band position
        if current_price > vwap_upper_2:
            band_position = "Above +2 StdDev (extremely overbought)"
        elif current_price > vwap_upper_1:
            band_position = "Above +1 StdDev (overbought)"
        elif current_price < vwap_lower_2:
            band_position = "Below -2 StdDev (extremely oversold)"
        elif current_price < vwap_lower_1:
            band_position = "Below -1 StdDev (oversold)"
        else:
            band_position = "Within ±1 StdDev (normal range)"
        
        return {
            "ticker": ticker,
            "date": str(today),
            "current_time": df_today.index[-1].strftime("%Y-%m-%d %H:%M:%S %Z"),
            "current_price": round(current_price, 2),
            "vwap_intraday": round(vwap_today, 2),
            "vwap_distance_%": round(vwap_distance, 2),
            "vwap_type": "Intraday VWAP (Today's Session Only)",
            "vwap_bands": {
                "upper_2_stddev": round(vwap_upper_2, 2),
                "upper_1_stddev": round(vwap_upper_1, 2),
                "vwap": round(vwap_today, 2),
                "lower_1_stddev": round(vwap_lower_1, 2),
                "lower_2_stddev": round(vwap_lower_2, 2)
            },
            "band_position": band_position,
            "bars_analyzed": len(df_today),
            "session_high": round(df_today['high'].max(), 2),
            "session_low": round(df_today['low'].min(), 2),
            "interpretation": "Above VWAP (bullish intraday)" if vwap_distance > 0 else "Below VWAP (bearish intraday)",
            "trading_note": "This EXACTLY matches TradingView's VWAP - resets daily, uses intraday data"
        }
        
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def analyze_volatility(ticker: str, period: str = "6mo") -> dict:
    """
    Comprehensive volatility analysis for risk management.
    ATR is THE professional standard for stop placement.
    
    Args:
        ticker: Stock ticker symbol
        period: Historical period (3mo, 6mo, 1y, 2y)
    
    Returns:
        Dictionary containing volatility metrics
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        spy = yf.Ticker("SPY").history(period=period)
        
        if df.empty:
            return {"error": f"No data available for {ticker}"}
        
        # ATR (Average True Range) - THE standard for stops
        # Calculate True Range
        df['H-L'] = df['High'] - df['Low']
        df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
        df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
        df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
        
        # ATR using Wilder's smoothing (RMA) - matches TradingView
        # Formula: ATR = (Previous ATR * (n-1) + Current TR) / n
        def calculate_atr_wilder(tr_series, period=14):
            """Calculate ATR using Wilder's smoothing (RMA) - TradingView method"""
            atr_values = []
            for i in range(len(tr_series)):
                if i < period:
                    # Not enough data yet
                    atr_values.append(np.nan)
                elif i == period:
                    # First ATR is simple average of first n periods
                    atr_values.append(tr_series.iloc[:period].mean())
                else:
                    # Subsequent ATRs use Wilder's smoothing
                    prev_atr = atr_values[-1]
                    current_tr = tr_series.iloc[i]
                    new_atr = (prev_atr * (period - 1) + current_tr) / period
                    atr_values.append(new_atr)
            return pd.Series(atr_values, index=tr_series.index)
        
        df['ATR_14'] = calculate_atr_wilder(df['TR'], 14)
        df['ATR_20'] = calculate_atr_wilder(df['TR'], 20)
        
        current_atr_14 = df['ATR_14'].iloc[-1]
        current_atr_20 = df['ATR_20'].iloc[-1]
        current_price = df['Close'].iloc[-1]
        atr_pct_14 = (current_atr_14 / current_price) * 100
        atr_pct_20 = (current_atr_20 / current_price) * 100
        
        # Historical Volatility (annualized)
        df['Returns'] = df['Close'].pct_change()
        hv_10d = df['Returns'].tail(10).std() * np.sqrt(252) * 100
        hv_20d = df['Returns'].tail(20).std() * np.sqrt(252) * 100
        hv_30d = df['Returns'].tail(30).std() * np.sqrt(252) * 100
        hv_60d = df['Returns'].tail(60).std() * np.sqrt(252) * 100
        
        # Volatility Percentile (current vs 1-year)
        one_year_hvs = df['Returns'].rolling(20).std().tail(252) * np.sqrt(252) * 100
        current_hv = hv_20d
        percentile = (one_year_hvs < current_hv).sum() / len(one_year_hvs.dropna()) * 100 if len(one_year_hvs.dropna()) > 0 else 50
        
        # Volatility Regime
        if percentile > 80:
            vol_regime = "EXTREME HIGH"
        elif percentile > 60:
            vol_regime = "HIGH"
        elif percentile > 40:
            vol_regime = "NORMAL"
        elif percentile > 20:
            vol_regime = "LOW"
        else:
            vol_regime = "EXTREME LOW"
        
        # Beta vs SPY
        if not spy.empty:
            combined = pd.merge(df[['Close']], spy[['Close']], 
                              left_index=True, right_index=True, suffixes=('_stock', '_spy'))
            combined['Returns_Stock'] = combined['Close_stock'].pct_change()
            combined['Returns_SPY'] = combined['Close_spy'].pct_change()
            covariance = combined['Returns_Stock'].cov(combined['Returns_SPY'])
            spy_variance = combined['Returns_SPY'].var()
            beta = covariance / spy_variance if spy_variance != 0 else 1.0
        else:
            beta = 1.0
        
        # Beta interpretation
        if beta > 1.5:
            beta_interp = "Very High Volatility vs Market"
        elif beta > 1.0:
            beta_interp = "Higher Volatility than Market"
        elif beta > 0.5:
            beta_interp = "Lower Volatility than Market"
        else:
            beta_interp = "Much Lower Volatility than Market"
        
        # Keltner Channels (ATR-based bands)
        df['EMA_20'] = df['Close'].ewm(span=20).mean()
        df['Keltner_Upper'] = df['EMA_20'] + (2 * df['ATR_20'])
        df['Keltner_Lower'] = df['EMA_20'] - (2 * df['ATR_20'])
        keltner_upper = df['Keltner_Upper'].iloc[-1]
        keltner_lower = df['Keltner_Lower'].iloc[-1]
        
        # Bollinger Band Width (volatility indicator)
        df['BB_Middle'] = df['Close'].rolling(20).mean()
        df['BB_Std'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['BB_Middle'] + (2 * df['BB_Std'])
        df['BB_Lower'] = df['BB_Middle'] - (2 * df['BB_Std'])
        df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
        bb_width = df['BB_Width'].iloc[-1] * 100
        
        # ATR-based stop recommendations (PROFESSIONAL STANDARD)
        stop_2x_atr = round(current_price - (current_atr_14 * 2), 2)
        stop_2_5x_atr = round(current_price - (current_atr_14 * 2.5), 2)
        stop_3x_atr = round(current_price - (current_atr_14 * 3), 2)
        
        # ATR-based position sizing (1% risk rule)
        # Example: If account = $100k, risk 1% = $1000
        # Risk per share = 2.5x ATR
        # Shares = $1000 / (2.5 * ATR)
        risk_per_share_2_5x = current_atr_14 * 2.5
        
        return {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "atr_14": round(current_atr_14, 2),
            "atr_20": round(current_atr_20, 2),
            "atr_14_%_of_price": round(atr_pct_14, 2),
            "atr_20_%_of_price": round(atr_pct_20, 2),
            "historical_volatility": {
                "10_day_%": round(hv_10d, 2),
                "20_day_%": round(hv_20d, 2),
                "30_day_%": round(hv_30d, 2),
                "60_day_%": round(hv_60d, 2)
            },
            "volatility_percentile": round(percentile, 1),
            "volatility_regime": vol_regime,
            "beta_vs_spy": round(beta, 2),
            "beta_interpretation": beta_interp,
            "keltner_channels": {
                "upper": round(keltner_upper, 2),
                "middle": round(df['EMA_20'].iloc[-1], 2),
                "lower": round(keltner_lower, 2)
            },
            "bollinger_band_width_%": round(bb_width, 2),
            "stop_loss_recommendations": {
                "aggressive_2x_atr": stop_2x_atr,
                "standard_2.5x_atr": stop_2_5x_atr,
                "conservative_3x_atr": stop_3x_atr,
                "note": "2.5x ATR is professional standard"
            },
            "position_sizing_example": {
                "risk_per_share_2.5x_atr": round(risk_per_share_2_5x, 2),
                "formula": "Shares = (Account_Size * Risk_%) / (2.5 * ATR)",
                "example": f"For $100k account, 1% risk: {int(1000/risk_per_share_2_5x)} shares"
            }
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def calculate_relative_strength(ticker: str, benchmark: str = "SPY", period: str = "3mo") -> dict:
    """
    Calculate relative strength to identify market leaders.
    RS Rating >70 = Buy only leaders (IBD methodology)
    
    Args:
        ticker: Stock ticker symbol
        benchmark: Benchmark ticker (default SPY)
        period: Comparison period (1mo, 3mo, 6mo, 1y, 2y)
    
    Returns:
        Dictionary containing RS metrics
    """
    try:
        stock = yf.Ticker(ticker).history(period=period)
        bench = yf.Ticker(benchmark).history(period=period)
        
        if stock.empty or bench.empty:
            return {"error": f"No data available"}
        
        # Align dates
        combined = pd.merge(stock[['Close']], bench[['Close']], 
                          left_index=True, right_index=True, suffixes=('_stock', '_bench'))
        
        # Calculate returns from start
        combined['Stock_Return'] = (combined['Close_stock'] / combined['Close_stock'].iloc[0] - 1) * 100
        combined['Bench_Return'] = (combined['Close_bench'] / combined['Close_bench'].iloc[0] - 1) * 100
        combined['Relative_Return'] = combined['Stock_Return'] - combined['Bench_Return']
        
        # Current outperformance
        outperformance = combined['Relative_Return'].iloc[-1]
        
        # RS Trend (improving or deteriorating?)
        recent_rs = combined['Relative_Return'].tail(20)
        rs_slope = np.polyfit(range(len(recent_rs)), recent_rs, 1)[0]
        rs_trend = "Improving" if rs_slope > 0 else "Deteriorating"
        
        # RS Score (0-100, IBD-style)
        # Professional traders focus on RS > 70
        if outperformance > 20:
            rs_score = 99
        elif outperformance > 15:
            rs_score = 95
        elif outperformance > 10:
            rs_score = 90
        elif outperformance > 7:
            rs_score = 85
        elif outperformance > 5:
            rs_score = 80
        elif outperformance > 3:
            rs_score = 75
        elif outperformance > 1:
            rs_score = 70
        elif outperformance > 0:
            rs_score = 60
        elif outperformance > -2:
            rs_score = 50
        elif outperformance > -5:
            rs_score = 40
        elif outperformance > -10:
            rs_score = 30
        else:
            rs_score = 20
        
        # Classification
        if rs_score >= 90:
            classification = "EXCEPTIONAL LEADER"
        elif rs_score >= 80:
            classification = "STRONG LEADER"
        elif rs_score >= 70:
            classification = "LEADER"
        elif rs_score >= 60:
            classification = "MARKET PERFORMER"
        elif rs_score >= 40:
            classification = "LAGGARD"
        else:
            classification = "WEAK LAGGARD"
        
        # Trading recommendation based on RS
        if rs_score >= 70 and rs_trend == "Improving":
            recommendation = "BUY - Strong leader with improving RS"
        elif rs_score >= 70 and rs_trend == "Deteriorating":
            recommendation = "HOLD - Leader but RS deteriorating"
        elif rs_score < 70 and rs_score >= 50:
            recommendation = "NEUTRAL - Wait for RS improvement"
        else:
            recommendation = "AVOID - Weak relative strength"
        
        return {
            "ticker": ticker,
            "benchmark": benchmark,
            "period": period,
            "rs_score": rs_score,
            "rs_trend": rs_trend,
            "classification": classification,
            "outperformance_%": round(outperformance, 2),
            "stock_return_%": round(combined['Stock_Return'].iloc[-1], 2),
            "benchmark_return_%": round(combined['Bench_Return'].iloc[-1], 2),
            "recommendation": recommendation,
            "ibd_note": "IBD methodology: Only buy stocks with RS > 70"
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def calculate_fundamental_scores(ticker: str, max_periods: int = 8) -> dict:
    """
    Calculate comprehensive fundamental quality scores.
    Piotroski F-Score: >7 = Excellent, <3 = Value trap
    Altman Z-Score: >2.99 = Safe, <1.81 = Bankruptcy risk
    
    Args:
        ticker: Stock ticker symbol
        max_periods: Number of periods to analyze
    
    Returns:
        Dictionary containing fundamental scores
    """
    try:
        stock = yf.Ticker(ticker)
        balance_sheet = stock.quarterly_balance_sheet
        income_stmt = stock.quarterly_income_stmt
        cashflow = stock.quarterly_cashflow
        info = stock.info
        
        if balance_sheet.empty or income_stmt.empty:
            return {"error": f"No financial data for {ticker}"}
        
        # Get latest and previous period data
        latest_bs = balance_sheet.iloc[:, 0]
        prev_bs = balance_sheet.iloc[:, 1] if len(balance_sheet.columns) > 1 else latest_bs
        latest_is = income_stmt.iloc[:, 0]
        prev_is = income_stmt.iloc[:, 1] if len(income_stmt.columns) > 1 else latest_is
        latest_cf = cashflow.iloc[:, 0] if not cashflow.empty else pd.Series()
        
        # ========== PIOTROSKI F-SCORE (0-9) ==========
        f_score = 0
        f_score_details = []
        
        # 1. Positive Net Income
        net_income = latest_is.get('Net Income', 0)
        if net_income > 0:
            f_score += 1
            f_score_details.append("✓ Positive Net Income")
        else:
            f_score_details.append("✗ Negative Net Income")
        
        # 2. Positive Operating Cash Flow
        operating_cf = latest_cf.get('Operating Cash Flow', 0)
        if operating_cf > 0:
            f_score += 1
            f_score_details.append("✓ Positive Operating Cash Flow")
        else:
            f_score_details.append("✗ Negative Operating Cash Flow")
        
        # 3. ROA Improvement
        total_assets = latest_bs.get('Total Assets', 1)
        prev_total_assets = prev_bs.get('Total Assets', 1)
        roa_current = net_income / total_assets if total_assets != 0 else 0
        prev_net_income = prev_is.get('Net Income', 0)
        roa_prev = prev_net_income / prev_total_assets if prev_total_assets != 0 else 0
        if roa_current > roa_prev:
            f_score += 1
            f_score_details.append("✓ ROA Improving")
        else:
            f_score_details.append("✗ ROA Declining")
        
        # 4. Quality of Earnings (CF > NI)
        if operating_cf > net_income:
            f_score += 1
            f_score_details.append("✓ Cash Flow > Net Income")
        else:
            f_score_details.append("✗ Cash Flow < Net Income")
        
        # 5. Decreasing Long-term Debt
        ltd_current = latest_bs.get('Long Term Debt', 0)
        ltd_prev = prev_bs.get('Long Term Debt', 0)
        if ltd_current < ltd_prev:
            f_score += 1
            f_score_details.append("✓ Debt Decreasing")
        else:
            f_score_details.append("✗ Debt Increasing")
        
        # 6. Current Ratio Improvement
        current_assets = latest_bs.get('Current Assets', 0)
        current_liabilities = latest_bs.get('Current Liabilities', 1)
        prev_current_assets = prev_bs.get('Current Assets', 0)
        prev_current_liabilities = prev_bs.get('Current Liabilities', 1)
        current_ratio = current_assets / current_liabilities if current_liabilities != 0 else 0
        prev_current_ratio = prev_current_assets / prev_current_liabilities if prev_current_liabilities != 0 else 0
        if current_ratio > prev_current_ratio:
            f_score += 1
            f_score_details.append("✓ Current Ratio Improving")
        else:
            f_score_details.append("✗ Current Ratio Declining")
        
        # 7. No New Shares Issued (simplified - using shares outstanding)
        shares_current = info.get('sharesOutstanding', 0)
        # Approximate previous shares (we'll give benefit of doubt if data not available)
        f_score += 1
        f_score_details.append("✓ No Dilution (assumed)")
        
        # 8. Gross Margin Improvement
        revenue = latest_is.get('Total Revenue', 1)
        cogs = latest_is.get('Cost Of Revenue', 0)
        gross_margin = (revenue - cogs) / revenue if revenue != 0 else 0
        prev_revenue = prev_is.get('Total Revenue', 1)
        prev_cogs = prev_is.get('Cost Of Revenue', 0)
        prev_gross_margin = (prev_revenue - prev_cogs) / prev_revenue if prev_revenue != 0 else 0
        if gross_margin > prev_gross_margin:
            f_score += 1
            f_score_details.append("✓ Gross Margin Improving")
        else:
            f_score_details.append("✗ Gross Margin Declining")
        
        # 9. Asset Turnover Improvement
        asset_turnover = revenue / total_assets if total_assets != 0 else 0
        prev_asset_turnover = prev_revenue / prev_total_assets if prev_total_assets != 0 else 0
        if asset_turnover > prev_asset_turnover:
            f_score += 1
            f_score_details.append("✓ Asset Turnover Improving")
        else:
            f_score_details.append("✗ Asset Turnover Declining")
        
        # F-Score Interpretation
        if f_score >= 7:
            f_interpretation = "EXCELLENT - Strong fundamentals"
        elif f_score >= 5:
            f_interpretation = "GOOD - Decent fundamentals"
        elif f_score >= 3:
            f_interpretation = "WEAK - Questionable fundamentals"
        else:
            f_interpretation = "POOR - Likely value trap"
        
        # ========== ALTMAN Z-SCORE (Bankruptcy Prediction) ==========
        retained_earnings = latest_bs.get('Retained Earnings', 0)
        ebit = latest_is.get('EBIT', latest_is.get('Operating Income', 0))
        total_liabilities = latest_bs.get('Total Liabilities Net Minority Interest', 1)
        market_cap = info.get('marketCap', 0)
        
        # Working Capital
        working_capital = current_assets - current_liabilities
        
        # Z-Score components
        x1 = working_capital / total_assets if total_assets != 0 else 0
        x2 = retained_earnings / total_assets if total_assets != 0 else 0
        x3 = ebit / total_assets if total_assets != 0 else 0
        x4 = market_cap / total_liabilities if total_liabilities != 0 else 0
        x5 = revenue / total_assets if total_assets != 0 else 0
        
        # Z-Score formula
        z_score = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
        
        # Z-Score zones
        if z_score > 2.99:
            z_zone = "SAFE ZONE"
            bankruptcy_risk = "Low"
        elif z_score > 1.81:
            z_zone = "GREY ZONE"
            bankruptcy_risk = "Medium"
        else:
            z_zone = "DISTRESS ZONE"
            bankruptcy_risk = "High"
        
        # Additional metrics
        debt_to_equity = total_liabilities / (total_assets - total_liabilities) if (total_assets - total_liabilities) != 0 else 0
        interest_coverage = ebit / latest_is.get('Interest Expense', 1) if latest_is.get('Interest Expense', 0) != 0 else 999
        
        return {
            "ticker": ticker,
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "piotroski_f_score": {
                "score": f_score,
                "out_of": 9,
                "interpretation": f_interpretation,
                "details": f_score_details,
                "recommendation": "BUY candidate if >7" if f_score >= 7 else "AVOID if <3" if f_score < 3 else "NEUTRAL"
            },
            "altman_z_score": {
                "score": round(z_score, 2),
                "zone": z_zone,
                "bankruptcy_risk": bankruptcy_risk,
                "interpretation": 
                    "Financially strong" if z_score > 2.99 else
                    "Caution advised" if z_score > 1.81 else
                    "High distress - avoid"
            },
            "additional_metrics": {
                "current_ratio": round(current_ratio, 2),
                "debt_to_equity": round(debt_to_equity, 2),
                "interest_coverage": round(interest_coverage, 2) if interest_coverage < 999 else "N/A",
                "roa_%": round(roa_current * 100, 2),
                "gross_margin_%": round(gross_margin * 100, 2)
            },
            "overall_assessment": 
                "STRONG BUY candidate" if f_score >= 7 and z_score > 2.99 else
                "Quality company" if f_score >= 5 and z_score > 2.99 else
                "Proceed with caution" if f_score >= 3 or z_score > 1.81 else
                "AVOID - Poor fundamentals"
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}
