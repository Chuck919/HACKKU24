from flask import Flask, render_template
from flask_mail import Mail, Message
import sqlite3
import http.client
import urllib.parse
from datetime import datetime, timedelta
import json
from config import Config
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter
import pandas as pd
import numpy as np
import io
import base64
import os
import time
import requests

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Flask-Mail
mail = Mail(app)

# Alpha Vantage API Keys - Primary and Fallback
ALPHAVANTAGE_KEYS = [
    app.config.get('ALPHAVANTAGE_API_KEY'),
    app.config.get('ALPHAVANTAGE_API_KEY_BACKUP')
]
# Filter out None values in case backup key isn't configured
ALPHAVANTAGE_KEYS = [key for key in ALPHAVANTAGE_KEYS if key]
current_key_index = 0

def get_api_key():
    """Get current Alpha Vantage API key"""
    global current_key_index
    if current_key_index < len(ALPHAVANTAGE_KEYS):
        return ALPHAVANTAGE_KEYS[current_key_index]
    return ALPHAVANTAGE_KEYS[0]  # Fallback to first key

def switch_api_key():
    """Switch to next available API key"""
    global current_key_index
    current_key_index += 1
    if current_key_index >= len(ALPHAVANTAGE_KEYS):
        current_key_index = 0  # Cycle back to first key
    new_key = get_api_key()
    key_preview = new_key[:12] + "..." if new_key else "None"
    print(f"    Switching to API key #{current_key_index + 1}: {key_preview}")
    print(f"    Available keys in list: {len(ALPHAVANTAGE_KEYS)}")
    return new_key

# Top 10 S&P 500 stocks by percentage weight (as of 2025)
# Sorted by actual S&P 500 index weight, not market cap
TOP_10_SP500 = ['NVDA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'AVGO', 'GOOG', 'META',  'TSLA', 'BRK.B']

def fetch_insider_transactions(symbols_list):
    """
    Fetch insider transactions for multiple symbols using batch approach
    Returns dict with symbol as key and list of transactions as value
    """
    print(f"  Fetching insider transactions for {len(symbols_list)} companies...")
    
    if not app.config.get('ALPHAVANTAGE_API_KEY'):
        print("    WARNING: No Alpha Vantage API key configured")
        return {}
    
    insider_data = {}
    api_key = app.config['ALPHAVANTAGE_API_KEY']
    
    # Limit to first 5 symbols to avoid rate limiting (5 calls per minute limit)
    for symbol in symbols_list[:5]:
        try:
            params = {
                'function': 'INSIDER_TRANSACTIONS',
                'symbol': symbol,
                'apikey': api_key
            }
            
            response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
            data = response.json()
            
            if 'data' in data and len(data['data']) > 0:
                # Get most recent 3 transactions
                transactions = []
                for tx in data['data'][:3]:
                    transactions.append({
                        'name': tx.get('name', 'Unknown'),
                        'shares': tx.get('acquisition_or_disposition', 'N/A'),
                        'shares_traded': tx.get('securities_transacted', '0'),
                        'price': tx.get('securities_owned', 'N/A'),
                        'date': tx.get('transaction_date', 'N/A')
                    })
                
                insider_data[symbol] = transactions
                print(f"    SUCCESS: {symbol}: {len(transactions)} transactions")
            
        except Exception as e:
            print(f"    ✗ {symbol} failed: {str(e)[:50]}")
            continue
    
    return insider_data

def fetch_market_news_sentiment(topics=None, tickers=None, limit=10):
    """
    Fetch market news with sentiment analysis
    Uses condensed API call to get news for multiple tickers/topics
    NOTE: Alpha Vantage NEWS_SENTIMENT only supports 'tickers' parameter, not 'topics'
    """
    print(f"  Fetching market news & sentiment...")
    print(f"    Tickers: {tickers}")
    print(f"    Limit: {limit}")
    
    if not app.config.get('ALPHAVANTAGE_API_KEY'):
        print("    WARNING: No Alpha Vantage API key configured")
        return []
    
    try:
        params = {
            'function': 'NEWS_SENTIMENT',
            'apikey': app.config['ALPHAVANTAGE_API_KEY'],
            'sort': 'LATEST'
        }
        
        # Add tickers if provided (comma-separated for batch request)
        # NOTE: Do NOT add limit parameter - causes "Invalid inputs" error
        if tickers:
            params['tickers'] = ','.join(tickers[:10])  # Limit to 10 tickers
            print(f"    Added tickers to params: {params['tickers']}")
        
        print(f"    Making request to Alpha Vantage NEWS_SENTIMENT API...")
        response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
        print(f"    Response status code: {response.status_code}")
        
        data = response.json()
        print(f"    Response keys: {list(data.keys())}")
        
        # Check for errors or rate limiting
        if 'Error Message' in data:
            print(f"    ERROR: {data['Error Message']}")
            return []
        
        if 'Note' in data:
            print(f"    RATE LIMIT: {data['Note']}")
            return []
        
        if 'Information' in data:
            print(f"    INFO: {data['Information']}")
            return []
        
        if 'feed' in data:
            print(f"    Feed contains {len(data['feed'])} items")
            news_items = []
            for item in data['feed'][:limit]:
                # Get ticker sentiments
                ticker_sentiments = {}
                if 'ticker_sentiment' in item:
                    for ts in item['ticker_sentiment'][:3]:  # Top 3 tickers mentioned
                        ticker_sentiments[ts.get('ticker', 'N/A')] = {
                            'relevance': float(ts.get('relevance_score', 0)),
                            'sentiment': ts.get('ticker_sentiment_label', 'Neutral')
                        }
                
                news_items.append({
                    'title': item.get('title', 'No title'),
                    'url': item.get('url', '#'),
                    'time_published': item.get('time_published', 'N/A'),
                    'source': item.get('source', 'Unknown'),
                    'summary': item.get('summary', 'No summary')[:200] + '...',
                    'overall_sentiment': item.get('overall_sentiment_label', 'Neutral'),
                    'sentiment_score': float(item.get('overall_sentiment_score', 0)),
                    'ticker_sentiments': ticker_sentiments
                })
            
            print(f"    SUCCESS: Retrieved {len(news_items)} news articles")
            return news_items
        else:
            print(f"    WARNING: No 'feed' key in response")
            print(f"    Response data: {str(data)[:200]}")
            return []
        
    except requests.exceptions.RequestException as e:
        print(f"    ERROR: Request failed: {str(e)[:100]}")
        return []
    except Exception as e:
        print(f"    ERROR: News fetch failed: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return []

def fetch_alphavantage_data(symbol, api_key):
    """
    Fetch stock data from Alpha Vantage API
    Returns dict with OHLC data or None if failed
    """
    try:
        # Map common symbols to Alpha Vantage format
        symbol_map = {
            '^GSPC': 'SPY',      # S&P 500 ETF as proxy
            '^IXIC': 'QQQ',      # NASDAQ 100 ETF as proxy
            'BTC-USD': 'BTC'     # Bitcoin
        }
        
        av_symbol = symbol_map.get(symbol, symbol)
        
        # Determine function based on asset type
        if av_symbol == 'BTC':
            function = 'DIGITAL_CURRENCY_DAILY'
            params = {
                'function': function,
                'symbol': 'BTC',
                'market': 'USD',
                'apikey': api_key
            }
        else:
            function = 'TIME_SERIES_DAILY'
            params = {
                'function': function,
                'symbol': av_symbol,
                'outputsize': 'compact',  # Last 100 days
                'apikey': api_key
            }
        
        # Build request using requests library
        response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
        data = response.json()
        
        # Debug: Print response
        print(f"    Alpha Vantage Response Keys: {list(data.keys())}")
        if 'Note' in data:
            print(f"    Response Note: {data['Note']}")
        if 'Information' in data:
            print(f"    Response Information: {data['Information']}")
        if 'Error Message' in data:
            print(f"    Response Error: {data['Error Message']}")
        
        # Check for rate limit and switch API key
        if 'Note' in data or 'Information' in data:
            print(f"    Alpha Vantage rate limit, switching key...")
            new_api_key = switch_api_key()
            params['apikey'] = new_api_key
            time.sleep(2)
            response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
            data = response.json()
            
            # Debug: Print retry response
            print(f"    Retry Response Keys: {list(data.keys())}")
            if 'Note' in data:
                print(f"    Retry Note: {data['Note']}")
            if 'Information' in data:
                print(f"    Retry Information: {data['Information']}")
        
        # Check for errors
        if 'Error Message' in data:
            print(f"    Alpha Vantage error: {data['Error Message']}")
            return None
        
        # Parse response based on function type
        if av_symbol == 'BTC':
            time_series_key = 'Time Series (Digital Currency Daily)'
            open_key = '1. open'
            high_key = '2. high'
            low_key = '3. low'
            close_key = '4. close'
        else:
            time_series_key = 'Time Series (Daily)'
            open_key = '1. open'
            high_key = '2. high'
            low_key = '3. low'
            close_key = '4. close'
        
        if time_series_key not in data:
            return None
        
        time_series = data[time_series_key]
        
        # Convert to OHLC dict
        ohlc_data = {
            'dates': [],
            'open': [],
            'high': [],
            'low': [],
            'close': []
        }
        
        # Get most recent 100 days (sort descending, take first 100, then reverse for chronological order)
        sorted_dates = sorted(time_series.items(), reverse=True)[:100]
        sorted_dates.reverse()  # Reverse to get chronological order (oldest to newest)
        
        for date, values in sorted_dates:
            ohlc_data['dates'].append(date)
            ohlc_data['open'].append(float(values[open_key]))
            ohlc_data['high'].append(float(values[high_key]))
            ohlc_data['low'].append(float(values[low_key]))
            ohlc_data['close'].append(float(values[close_key]))
        
        if len(ohlc_data['close']) >= 5:
            return ohlc_data
        
        return None
        
    except Exception as e:
        print(f"    Alpha Vantage error: {str(e)[:100]}")
        return None

def generate_market_charts(user_prefs=None):
    """
    Generate candlestick charts for requested markets
    user_prefs: dict with keys like 'sp500', 'nasdaq', 'bitcoin'
    Returns a dictionary with base64 encoded images
    """
    if user_prefs is None:
        user_prefs = {'sp500': True, 'nasdaq': True, 'bitcoin': True}
    
    charts = {}
    
    # Define the tickers based on user preferences
    tickers = {}
    if user_prefs.get('sp500', False):
        tickers['S&P 500'] = '^GSPC'
    if user_prefs.get('nasdaq', False):
        tickers['NASDAQ'] = '^IXIC'
    if user_prefs.get('bitcoin', False):
        tickers['Bitcoin'] = 'BTC-USD'
    
    if not tickers:
        return charts
    
    # Try to get real data first
    print(f"  Attempting to fetch market data for {len(tickers)} charts...")
    
    for name, ticker in tickers.items():
        try:
            print(f"  Generating candlestick chart for {name}...")
            
            # Try Alpha Vantage with key switching fallback
            ohlc_data = None
            data_source = "unknown"
            
            # Try with primary API key
            if get_api_key():
                try:
                    print(f"    Trying Alpha Vantage with primary key...")
                    api_key = get_api_key()
                    ohlc_data = fetch_alphavantage_data(ticker, api_key)
                    if ohlc_data and len(ohlc_data['close']) >= 5:
                        data_source = "Alpha Vantage"
                        print(f"    SUCCESS: Alpha Vantage: {len(ohlc_data['close'])} candles")
                except Exception as e:
                    print(f"    ERROR: Alpha Vantage primary key failed: {str(e)[:50]}")
            
            # If primary failed and we have backup key, try backup
            if ohlc_data is None and len(ALPHAVANTAGE_KEYS) > 1:
                try:
                    print(f"    Trying Alpha Vantage with backup key...")
                    backup_key = ALPHAVANTAGE_KEYS[1] if len(ALPHAVANTAGE_KEYS) > 1 else None
                    if backup_key:
                        ohlc_data = fetch_alphavantage_data(ticker, backup_key)
                        if ohlc_data and len(ohlc_data['close']) >= 5:
                            data_source = "Alpha Vantage (Backup)"
                            print(f"    SUCCESS: Backup key: {len(ohlc_data['close'])} candles")
                except Exception as e:
                    print(f"    ERROR: Alpha Vantage backup key failed: {str(e)[:50]}")
            
            # Use mock data as final fallback
            if ohlc_data is None or len(ohlc_data['close']) < 5:
                print(f"    Using mock data (all APIs unavailable)")
                ohlc_data = generate_mock_ohlc_data(name, 100)
                data_source = "Mock Data"
            
            # Create candlestick chart
            chart_img = create_candlestick_chart(name, ohlc_data, data_source)
            if chart_img:
                charts[name] = chart_img
                print(f"  SUCCESS: Chart generated for {name}")
            
        except Exception as e:
            print(f"  ERROR: Error generating chart for {name}: {str(e)[:100]}")
            continue
    
    return charts

def create_candlestick_chart(name, ohlc_data, data_source):
    """Create a candlestick chart from OHLC data"""
    try:
        fig, ax = plt.subplots(figsize=(12, 6))
        
        opens = np.array(ohlc_data['open'])
        highs = np.array(ohlc_data['high'])
        lows = np.array(ohlc_data['low'])
        closes = np.array(ohlc_data['close'])
        
        # Calculate percentage change
        pct_change = ((closes[-1] - closes[0]) / closes[0]) * 100
        change_text = f"{'+' if pct_change >= 0 else ''}{pct_change:.2f}%"
        change_color = 'green' if pct_change >= 0 else 'red'
        
        # Plot candlesticks
        for i in range(len(opens)):
            # Determine color
            if closes[i] >= opens[i]:
                color = '#26a69a'  # Green for up
                body_color = color
                edge_color = color
            else:
                color = '#ef5350'  # Red for down
                body_color = color
                edge_color = color
            
            # Draw high-low line
            ax.plot([i, i], [lows[i], highs[i]], color=edge_color, linewidth=1, solid_capstyle='round')
            
            # Draw open-close body
            body_height = abs(closes[i] - opens[i])
            body_bottom = min(opens[i], closes[i])
            
            rect = Rectangle((i - 0.3, body_bottom), 0.6, body_height,
                           facecolor=body_color, edgecolor=edge_color, linewidth=1.5)
            ax.add_patch(rect)
        
        # Set proper y-axis limits with padding
        y_min = min(lows) * 0.995
        y_max = max(highs) * 1.005
        ax.set_ylim(y_min, y_max)
        
        # Formatting - use actual number of candles instead of hardcoded "30 Days"
        num_candles = len(opens)
        ax.set_title(f'{name} - Last {num_candles} Days ({change_text}) [{data_source}]', 
                    fontsize=14, fontweight='bold', color=change_color)
        ax.set_xlabel('Days', fontsize=10)
        ax.set_ylabel('Price (USD)', fontsize=10)
        ax.grid(True, alpha=0.2, linestyle='--', axis='y')
        ax.set_xlim(-1, len(opens))
        
        # Format y-axis as currency
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        # Adjust layout
        plt.tight_layout()
        
        # Save to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        
        # Encode to base64
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        
        # Close the plot
        plt.close(fig)
        buf.close()
        
        return img_base64
        
    except Exception as e:
        print(f"  Error creating candlestick chart: {str(e)}")
        return None

def generate_mock_ohlc_data(asset_name, num_days=30):
    """Generate realistic mock OHLC data"""
    # Base prices for different assets
    base_prices = {
        'S&P 500': 4500.0,
        'NASDAQ': 15000.0,
        'Bitcoin': 35000.0
    }
    
    base_price = base_prices.get(asset_name, 1000.0)
    
    # Generate random walk
    np.random.seed(hash(asset_name) % (2**32))
    
    ohlc_data = {
        'dates': [],
        'open': [],
        'high': [],
        'low': [],
        'close': []
    }
    
    current_price = base_price
    for i in range(num_days):
        open_price = current_price
        
        # Daily change
        daily_change = np.random.normal(0.001, 0.02)
        close_price = float(open_price * (1 + daily_change))
        
        # High and low
        high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.01)))
        low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.01)))
        
        ohlc_data['dates'].append(f'Day {i+1}')
        ohlc_data['open'].append(float(open_price))
        ohlc_data['high'].append(float(high_price))
        ohlc_data['low'].append(float(low_price))
        ohlc_data['close'].append(float(close_price))
        
        current_price = close_price
    
    return ohlc_data

def generate_mock_price_data(asset_name, num_days=90):
    """
    Generate realistic mock price data for demonstration when API is unavailable
    """
    import numpy as np
    
    # Base prices for different assets
    base_prices = {
        'S&P 500': 4500.0,
        'NASDAQ': 15000.0,
        'Bitcoin': 35000.0
    }
    
    base_price = base_prices.get(asset_name, 1000.0)
    
    # Generate random walk with slight upward trend
    np.random.seed(hash(asset_name) % (2**32))  # Consistent data for same asset
    
    prices = [base_price]
    for i in range(num_days - 1):
        # Random daily change between -2% and +2.5% (slight bull bias)
        change_pct = np.random.normal(0.001, 0.015)
        new_price = float(prices[-1] * (1 + change_pct))
        prices.append(new_price)
    
    return np.array(prices)

def calculate_rsi(prices, period=14):
    """Calculate RSI from price data using Wilder's smoothing method"""
    if len(prices) < period + 1:
        return None
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    # Initial average gain/loss (simple average of first 14 periods)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    # Apply Wilder's smoothing for subsequent periods
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    # Calculate RSI
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def calculate_obv(closes, volumes):
    """Calculate On-Balance Volume (OBV)"""
    obv = np.zeros(len(closes))
    obv[0] = volumes[0]
    
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]:
            obv[i] = obv[i-1] + volumes[i]
        elif closes[i] < closes[i-1]:
            obv[i] = obv[i-1] - volumes[i]
        else:
            obv[i] = obv[i-1]
    
    return obv

def calculate_sma(data, period):
    """Calculate Simple Moving Average"""
    if len(data) < period:
        return None
    return np.mean(data[-period:])

def calculate_trading_signal(symbol, api_key):
    """
    Calculate trading signal using SMA50/SMA100 + RSI + OBV strategy
    Fetches full time series (100 candles) and calculates all indicators locally
    
    Signal Logic:
    - STRONG BUY: Price > SMA50 > SMA100, slopes positive, OBV up, RSI < 50
    - BUY: Price > SMA100, OBV up/neutral, RSI 50-60
    - HOLD: Mixed signals, flat slopes, RSI 45-70
    - SELL: Price < SMA50 < SMA100, OBV down, RSI 30-45
    - STRONG SELL: Price << SMAs, OBV down, RSI < 30 or bearish divergence
    
    Returns: dict with signal, sma50, sma100, rsi, obv, current_price, or None if failed
    """
    try:
        print(f"\n      {'='*60}")
        print(f"      CALCULATING TRADING SIGNAL FOR {symbol}")
        print(f"      {'='*60}")
        print(f"      Step 1: Fetching time series data...")
        
        # Fetch TIME_SERIES_DAILY with 100 data points
        params = {
            'function': 'TIME_SERIES_DAILY',
            'symbol': symbol,
            'outputsize': 'compact',  # Returns latest 100 data points
            'apikey': api_key
        }
        
        response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
        data = response.json()
        
        # Check for rate limit and switch API key if needed
        if 'Note' in data or 'Information' in data:
            print(f"      WARNING: Rate limit hit, switching API key...")
            print(f"      Message: {data.get('Note') or data.get('Information')}")
            api_key = switch_api_key()
            params['apikey'] = api_key
            time.sleep(2)
            response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
            data = response.json()
        
        # Check for errors
        if 'Time Series (Daily)' not in data:
            print(f"      ERROR: No time series data returned")
            print(f"      Response keys: {list(data.keys())}")
            return None
        
        time_series = data['Time Series (Daily)']
        print(f"      SUCCESS: Received {len(time_series)} candles from API")
        
        # Sort dates and extract data
        sorted_dates = sorted(time_series.keys(), reverse=True)  # Newest first
        
        if len(sorted_dates) < 100:
            print(f"      WARNING: Not enough data (only {len(sorted_dates)} candles, need 100)")
            if len(sorted_dates) < 50:
                print(f"      ERROR: Insufficient data for SMA50/SMA100 calculation")
                return None
        
        # Extract arrays (reverse to get oldest->newest for calculations)
        closes = []
        volumes = []
        
        for date in reversed(sorted_dates[:100]):  # Take latest 100, reverse to oldest->newest
            closes.append(float(time_series[date]['4. close']))
            volumes.append(float(time_series[date]['5. volume']))
        
        closes = np.array(closes)
        volumes = np.array(volumes)
        
        print(f"      Step 2: Processing {len(closes)} candles (oldest to newest)")
        print(f"      Date range: {sorted_dates[-1]} to {sorted_dates[0]}")
        
        # Current price
        current_price = closes[-1]
        print(f"\n      CURRENT PRICE: ${current_price:.2f}")
        
        # Calculate indicators
        print(f"      Step 3: Calculating technical indicators...")
        sma50 = calculate_sma(closes, 50)
        sma100 = calculate_sma(closes, 100)
        rsi = calculate_rsi(closes, 14)
        obv = calculate_obv(closes, volumes)
        obv_sma20 = calculate_sma(obv, 20)
        
        if sma50 is None or sma100 is None or rsi is None or obv_sma20 is None:
            print(f"      ERROR: Not enough data to calculate indicators")
            print(f"      SMA50: {sma50}, SMA100: {sma100}, RSI: {rsi}, OBV_SMA20: {obv_sma20}")
            return None
        
        # Calculate slopes (5-day lookback)
        # We need to calculate the SMA values from 5 days ago using data up to that point
        if len(closes) >= 105:  # Need at least 105 days for SMA100 from 5 days ago
            # Calculate SMA50 and SMA100 from 5 days ago (using data up to index -5)
            closes_5days_ago = closes[:-5]
            sma50_5days_ago = np.mean(closes_5days_ago[-50:]) if len(closes_5days_ago) >= 50 else sma50
            sma100_5days_ago = np.mean(closes_5days_ago[-100:]) if len(closes_5days_ago) >= 100 else sma100
        elif len(closes) >= 55:  # Can calculate SMA50 from 5 days ago but not SMA100
            closes_5days_ago = closes[:-5]
            sma50_5days_ago = np.mean(closes_5days_ago[-50:])
            sma100_5days_ago = sma100  # Not enough data, use current
        else:
            sma50_5days_ago = sma50  # Not enough data, use current
            sma100_5days_ago = sma100
        
        slope_50 = sma50 - sma50_5days_ago
        slope_100 = sma100 - sma100_5days_ago
        
        # Current OBV
        obv_current = obv[-1]
        
        rsi_status = 'Oversold' if rsi < 30 else 'Overbought' if rsi > 70 else 'Neutral'
        obv_status = 'Above avg' if obv_current > obv_sma20 else 'Below avg'
        
        print(f"\n      TECHNICAL INDICATORS:")
        print(f"      ├─ SMA50:       ${sma50:>12,.2f}  (5-day slope: {slope_50:>+8.2f})")
        print(f"      ├─ SMA100:      ${sma100:>12,.2f}  (5-day slope: {slope_100:>+8.2f})")
        print(f"      ├─ RSI(14):     {rsi:>12.2f}  [{rsi_status}]")
        print(f"      ├─ OBV:         {obv_current:>12,.0f}")
        print(f"      └─ OBV_SMA20:   {obv_sma20:>12,.0f}  [{obv_status}]")
        
        price_vs_sma50 = '>' if current_price > sma50 else '<'
        sma50_vs_sma100 = '>' if sma50 > sma100 else '<'
        rsi_zone = '<50' if rsi < 50 else '50-60' if 50 <= rsi <= 60 else '60-70' if 60 < rsi <= 70 else '>70'
        
        print(f"\n      CONDITION CHECKS:")
        print(f"      ├─ Price vs SMAs:    Price({current_price:.2f}) {price_vs_sma50} SMA50({sma50:.2f}) {sma50_vs_sma100} SMA100({sma100:.2f})")
        print(f"      ├─ SMA Slopes:       SMA50: {slope_50:+.2f}, SMA100: {slope_100:+.2f}")
        print(f"      ├─ OBV Trend:        OBV({obv_current:,.0f}) vs SMA20({obv_sma20:,.0f}) = {obv_current - obv_sma20:+,.0f}")
        print(f"      └─ RSI Zone:         {rsi:.2f} ({rsi_zone})")
        
        # Apply classification rules
        print(f"\n      EVALUATING SIGNAL RULES:")
        
        if (current_price > sma50 and sma50 > sma100 and 
            slope_50 > 0 and slope_100 > 0 and 
            obv_current > obv_sma20 and rsi < 50):
            signal = 'STRONG BUY'
            signal_color = 'green'
            print(f"      STRONG BUY conditions met:")
            print(f"         • Price > SMA50 > SMA100: YES")
            print(f"         • Slopes positive: YES")
            print(f"         • OBV > OBV_SMA20: YES")
            print(f"         • RSI < 50: YES")
            
        elif (current_price > sma100 and 
              ((sma50 > sma100) or (sma50 <= sma100 and slope_50 > 0)) and 
              obv_current >= obv_sma20 and 50 <= rsi <= 60):
            signal = 'BUY'
            signal_color = 'darkgreen'
            print(f"      BUY conditions met:")
            print(f"         • Price > SMA100: YES")
            print(f"         • SMA trend favorable: YES")
            print(f"         • OBV >= avg: YES")
            print(f"         • RSI 50-60: YES")
            
        elif (current_price < sma50 and sma50 < sma100 and 
              obv_current < obv_sma20 and 30 <= rsi < 45):
            signal = 'SELL'
            signal_color = 'darkred'
            print(f"      SELL conditions met:")
            print(f"         • Price < SMA50 < SMA100: YES")
            print(f"         • OBV declining: YES")
            print(f"         • RSI 30-45: YES")
            
        elif (current_price < sma50 and current_price < sma100 and 
              (obv_current < obv_sma20 or rsi < 30)):
            signal = 'STRONG SELL'
            signal_color = 'red'
            print(f"      STRONG SELL conditions met:")
            print(f"         • Price < Both SMAs: YES")
            print(f"         • OBV bearish or RSI oversold: YES")
            
        else:
            # Hold conditions: mixed signals, flat slopes, or RSI in neutral zone
            signal = 'HOLD'
            signal_color = 'orange'
            print(f"      HOLD conditions (mixed signals):")
            print(f"         • No clear buy/sell pattern detected")
        
        print(f"\n      FINAL SIGNAL: {signal}")
        print(f"      {'='*60}\n")
        
        return {
            'signal': signal,
            'signal_color': signal_color,
            'rsi': rsi,
            'sma50': sma50,
            'sma100': sma100,
            'obv': obv_current,
            'obv_sma20': obv_sma20,
            'current_price': current_price
        }
        
    except Exception as e:
        print(f"\n      EXCEPTION OCCURRED:")
        print(f"      Error type: {type(e).__name__}")
        print(f"      Error message: {str(e)}")
        import traceback
        print(f"      Traceback:")
        traceback.print_exc()
        print(f"      {'='*60}\n")
        return None

def fetch_top10_sp500_stocks():
    """
    Fetch top 10 S&P 500 stocks with current price and daily change
    Uses Alpha Vantage API for each ticker
    NOTE: Alpha Vantage has a rate limit of 5 calls/minute
    This function will take ~5 minutes to complete all 10 stocks
    """
    print("  Fetching Top 10 S&P 500 stocks...")
    print("  NOTE: Rate limit is 5 calls/minute, this will take ~5 minutes")
    
    if not get_api_key():
        print("    WARNING: No Alpha Vantage API key configured, using mock data")
        return generate_mock_top10_data()
    
    stocks_data = []
    api_key = get_api_key()
    
    for idx, symbol in enumerate(TOP_10_SP500, 1):
        try:
            print(f"\n    {'─'*60}")
            print(f"    [{idx}/{len(TOP_10_SP500)}] Processing {symbol}")
            print(f"    {'─'*60}")
            
            # Fetch data from Alpha Vantage using requests library (more reliable on PythonAnywhere)
            url = 'https://www.alphavantage.co/query'
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': api_key
            }
            
            print(f"    Step 1: Fetching current price quote...")
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            # Debug: Print response keys
            print(f"    Response Keys: {list(data.keys())}")
            
            # Check for rate limit message and switch API key immediately
            if 'Note' in data or 'Information' in data:
                print(f"    WARNING: API RATE LIMIT REACHED")
                print(f"    Message: {data.get('Note') or data.get('Information')}")
                print(f"    Switching to backup API key and retrying...")
                api_key = switch_api_key()
                params['apikey'] = api_key
                time.sleep(2)  # Brief pause before retry
                response = requests.get(url, params=params, timeout=10)
                data = response.json()
                
                # Debug: Print retry response
                print(f"    Retry Response Keys: {list(data.keys())}")
                
                # If still failing after switch, skip this stock
                if 'Note' in data or 'Information' in data:
                    print(f"    Retry Message: {data.get('Note') or data.get('Information')}")
                    print(f"    ERROR: Both API keys exhausted, skipping {symbol}")
                    continue
            
            if 'Global Quote' in data and data['Global Quote']:
                quote = data['Global Quote']
                current_price = float(quote.get('05. price', 0))
                previous_close = float(quote.get('08. previous close', 0))
                
                print(f"    SUCCESS: Quote received:")
                print(f"       Current Price:   ${current_price:>10.2f}")
                print(f"       Previous Close:  ${previous_close:>10.2f}")
                
                if current_price > 0 and previous_close > 0:
                    daily_change = current_price - previous_close
                    daily_change_pct = (daily_change / previous_close) * 100
                    
                    direction_text = 'UP' if daily_change >= 0 else 'DOWN'
                    print(f"       Daily Change:    ${daily_change:>+10.2f} ({daily_change_pct:>+6.2f}%)")
                    print(f"       Direction:       {direction_text}")
                    
                    stock_info = {
                        'symbol': symbol,
                        'price': current_price,
                        'change': daily_change,
                        'change_pct': daily_change_pct,
                        'direction': 'up' if daily_change >= 0 else 'down',
                        'signal': 'N/A',
                        'signal_color': 'gray'
                    }
                    
                    # Get trading signal (RSI + SMA + OBV strategy)
                    print(f"\n    Step 2: Calculating trading indicators...")
                    trading_signal = calculate_trading_signal(symbol, api_key)
                    if trading_signal:
                        stock_info['signal'] = trading_signal['signal']
                        stock_info['signal_color'] = trading_signal['signal_color']
                        stock_info['rsi'] = trading_signal.get('rsi', 0)
                        print(f"    SUCCESS: Signal Generated: {trading_signal['signal']}")
                    else:
                        print(f"    WARNING: Could not generate trading signal (using default: N/A)")
                    
                    stocks_data.append(stock_info)
                    print(f"\n    SUCCESS: {symbol} data collected")
                    print(f"       Final: ${current_price:.2f} ({daily_change_pct:+.2f}%) - {stock_info['signal']}")
                else:
                    print(f"    ERROR: Invalid price data (price={current_price}, prev_close={previous_close})")
            else:
                print(f"    ERROR: No quote data in API response")
                print(f"    Response keys: {list(data.keys())}")
            
            # Rate limiting: Wait 15 seconds between stocks to avoid rate limit
            if idx < len(TOP_10_SP500):
                wait_time = 15
                print(f"\n    Rate limit pause: Waiting {wait_time}s before next stock...")
                print(f"    Progress: {idx}/{len(TOP_10_SP500)} stocks processed")
                time.sleep(wait_time)
                
        except requests.exceptions.RequestException as e:
            print(f"    ERROR: {symbol} request failed: {str(e)[:100]}")
            continue
        except Exception as e:
            print(f"    ERROR: {symbol} failed: {str(e)[:50]}")
            continue
    
    if len(stocks_data) >= 5:
        print(f"  SUCCESS: Successfully fetched {len(stocks_data)}/10 stocks")
        return stocks_data
    else:
        print(f"  WARNING: Not enough data ({len(stocks_data)}/10), using mock data")
        return generate_mock_top10_data()


def generate_mock_top10_data():
    """Generate mock data for top 10 stocks"""
    stocks_data = []
    # Base prices matching TOP_10_SP500 = ['NVDA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'AVGO', 'GOOG', 'META', 'TSLA', 'BRK.B']
    base_prices = {
        'NVDA': 500.0,
        'AAPL': 175.0,
        'MSFT': 380.0,
        'AMZN': 145.0,
        'GOOGL': 140.0,
        'AVGO': 170.0,
        'GOOG': 138.0,
        'META': 330.0,
        'TSLA': 245.0,
        'BRK.B': 360.0
    }
    
    signals = ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL']
    signal_colors = {
        'STRONG BUY': 'green', 
        'BUY': 'darkgreen', 
        'HOLD': 'orange', 
        'SELL': 'darkred',
        'STRONG SELL': 'red'
    }
    
    np.random.seed(42)
    for symbol in TOP_10_SP500:
        base_price = base_prices[symbol]
        daily_change_pct = np.random.normal(0, 1.5)
        daily_change = base_price * (daily_change_pct / 100)
        
        # Random signal and RSI for mock data
        signal = np.random.choice(signals)
        rsi = np.random.uniform(25, 75)  # RSI between 25-75
        
        stocks_data.append({
            'symbol': symbol,
            'price': base_price,
            'change': daily_change,
            'change_pct': daily_change_pct,
            'direction': 'up' if daily_change >= 0 else 'down',
            'signal': signal,
            'signal_color': signal_colors[signal],
            'rsi': rsi
        })
    
    return stocks_data

def fetch_crypto_data():
    """
    Fetch Bitcoin and Ethereum data with trading indicators
    Uses Alpha Vantage DIGITAL_CURRENCY_DAILY endpoint
    Returns list of crypto data with signals
    """
    print("  Fetching Cryptocurrency data (BTC & ETH)...")
    
    if not get_api_key():
        print("    WARNING: No Alpha Vantage API key configured, using mock data")
        return generate_mock_crypto_data()
    
    crypto_data = []
    api_key = get_api_key()
    cryptos = [
        {'symbol': 'BTC', 'name': 'Bitcoin'},
        {'symbol': 'ETH', 'name': 'Ethereum'}
    ]
    
    for idx, crypto in enumerate(cryptos, 1):
        try:
            symbol = crypto['symbol']
            print(f"    Fetching {crypto['name']} ({symbol})...")
            
            # Fetch current price using DIGITAL_CURRENCY_DAILY
            url = 'https://www.alphavantage.co/query'
            params = {
                'function': 'DIGITAL_CURRENCY_DAILY',
                'symbol': symbol,
                'market': 'USD',
                'apikey': api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            # Debug: Print response
            print(f"    Response Keys: {list(data.keys())}")
            if 'Note' in data:
                print(f"    Response Note: {data['Note']}")
            if 'Information' in data:
                print(f"    Response Information: {data['Information']}")
            
            # Check for rate limit and retry with backup key
            if 'Note' in data or 'Information' in data:
                print(f"    WARNING: {symbol}: API rate limit reached, switching key...")
                api_key = switch_api_key()
                params['apikey'] = api_key
                time.sleep(2)
                response = requests.get(url, params=params, timeout=10)
                data = response.json()
                
                # Debug: Print retry response
                print(f"    Retry Response Keys: {list(data.keys())}")
                
                # If still failing, skip this crypto
                if 'Note' in data or 'Information' in data:
                    print(f"    Retry Message: {data.get('Note') or data.get('Information')}")
                    print(f"    ERROR: {symbol}: Both API keys exhausted, skipping")
                    continue
            
            if 'Time Series (Digital Currency Daily)' in data:
                time_series = data['Time Series (Digital Currency Daily)']
                
                # Get most recent date
                latest_date = sorted(time_series.keys(), reverse=True)[0]
                latest = time_series[latest_date]
                
                # Get previous day for change calculation
                dates_sorted = sorted(time_series.keys(), reverse=True)
                if len(dates_sorted) >= 2:
                    prev_date = dates_sorted[1]
                    prev = time_series[prev_date]
                    
                    # Digital currency data returns base values (not USD)
                    # Keys are: '1. open', '2. high', '3. low', '4. close', '5. volume'
                    # We need to fetch from USD market, not EUR
                    current_price = float(latest['4. close'])
                    previous_close = float(prev['4. close'])
                    
                    if current_price > 0 and previous_close > 0:
                        daily_change = current_price - previous_close
                        daily_change_pct = (daily_change / previous_close) * 100
                        
                        crypto_info = {
                            'symbol': symbol,
                            'name': crypto['name'],
                            'price': current_price,
                            'change': daily_change,
                            'change_pct': daily_change_pct,
                            'direction': 'up' if daily_change >= 0 else 'down',
                            'signal': 'N/A',
                            'signal_color': 'gray',
                            'rsi': None
                        }
                        
                        # Get trading signal using standard RSI + SMA strategy
                        # For crypto, we can use stock ticker equivalents: BTC-USD, ETH-USD work with Alpha Vantage indicators
                        print(f"      Fetching trading indicators for {symbol}...")
                        crypto_ticker = f"{symbol}-USD"  # Convert BTC -> BTC-USD for technical indicators
                        trading_signal = calculate_trading_signal(crypto_ticker, api_key)
                        if trading_signal:
                            crypto_info['signal'] = trading_signal['signal']
                            crypto_info['signal_color'] = trading_signal['signal_color']
                            crypto_info['rsi'] = trading_signal.get('rsi', 0)
                            print(f"      Trading Signal: {trading_signal['signal']}")
                        else:
                            # Fallback if technical indicators don't work
                            crypto_info['signal'] = 'HOLD'
                            crypto_info['signal_color'] = 'orange'
                            print(f"      Could not fetch technical indicators, defaulting to HOLD")
                        
                        crypto_data.append(crypto_info)
                        print(f"    SUCCESS: {symbol}: ${current_price:,.2f} ({daily_change_pct:+.2f}%)")
                    else:
                        print(f"    WARNING: {symbol}: Invalid price data")
                else:
                    print(f"    WARNING: {symbol}: Not enough historical data")
            else:
                print(f"    WARNING: {symbol}: No data returned from API")
            
            # Rate limiting: Wait 15 seconds between cryptos
            if idx < len(cryptos):
                wait_time = 15
                print(f"    [{idx}/{len(cryptos)}] Waiting {wait_time}s for rate limit...")
                time.sleep(wait_time)
                
        except requests.exceptions.RequestException as e:
            print(f"    ERROR: {crypto['symbol']} request failed: {str(e)[:100]}")
            continue
        except Exception as e:
            print(f"    ERROR: {crypto['symbol']} failed: {str(e)[:100]}")
            continue
    
    if len(crypto_data) >= 1:
        print(f"  SUCCESS: Successfully fetched {len(crypto_data)}/2 cryptos")
        return crypto_data
    else:
        print(f"  WARNING: No crypto data, using mock data")
        return generate_mock_crypto_data()

def generate_mock_crypto_data():
    """Generate mock data for cryptocurrencies"""
    signals = ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL']
    signal_colors = {
        'STRONG BUY': 'green', 
        'BUY': 'darkgreen', 
        'HOLD': 'orange', 
        'SELL': 'darkred',
        'STRONG SELL': 'red'
    }
    
    np.random.seed(99)
    cryptos = [
        {'symbol': 'BTC', 'name': 'Bitcoin', 'base_price': 43500.0},
        {'symbol': 'ETH', 'name': 'Ethereum', 'base_price': 2280.0}
    ]
    
    crypto_data = []
    for crypto in cryptos:
        daily_change_pct = np.random.normal(0, 3.0)  # Crypto is more volatile
        daily_change = crypto['base_price'] * (daily_change_pct / 100)
        signal = np.random.choice(signals)
        rsi = np.random.uniform(25, 75)
        
        crypto_data.append({
            'symbol': crypto['symbol'],
            'name': crypto['name'],
            'price': crypto['base_price'],
            'change': daily_change,
            'change_pct': daily_change_pct,
            'direction': 'up' if daily_change >= 0 else 'down',
            'signal': signal,
            'signal_color': signal_colors[signal],
            'rsi': rsi
        })
    
    return crypto_data

def send_email(email, articles, charts=None, top10_stocks=None, insider_data=None, market_news=None, crypto_data=None):
    try:
        print(f"\n{'='*60}")
        print(f"EMAIL SEND DEBUG for {email}")
        print(f"{'='*60}")
        
        # Check Flask-Mail configuration
        print(f"  Mail Configuration:")
        print(f"    MAIL_SERVER: {app.config.get('MAIL_SERVER', 'NOT SET')}")
        print(f"    MAIL_PORT: {app.config.get('MAIL_PORT', 'NOT SET')}")
        print(f"    MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS', 'NOT SET')}")
        print(f"    MAIL_USERNAME: {app.config.get('MAIL_USERNAME', 'NOT SET')}")
        print(f"    MAIL_PASSWORD: {'SET' if app.config.get('MAIL_PASSWORD') else 'NOT SET'}")
        
        # Check content
        print(f"\n  Email Content:")
        print(f"    Recipient: {email}")
        print(f"    Articles: {len(articles)} keyword(s), {sum(len(v) for v in articles.values())} total articles")
        print(f"    Charts: {len(charts) if charts else 0}")
        print(f"    Top 10 Stocks: {len(top10_stocks) if top10_stocks else 0}")
        print(f"    Crypto Data: {len(crypto_data) if crypto_data else 0}")
        print(f"    Insider Data: {len(insider_data) if insider_data else 0} symbols")
        print(f"    Market News: {len(market_news) if market_news else 0} items")
        
        msg = Message('AnyNews Daily Update',
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[email])
        
        print(f"\n  Rendering email template...")
        email_body = render_template('daily_mail.html', articles=articles, charts=charts, 
                                     top10_stocks=top10_stocks, insider_data=insider_data, 
                                     market_news=market_news, crypto_data=crypto_data)
        print(f"    Template rendered successfully (size: {len(email_body)} chars)")
        msg.html = email_body

        print(f"\n  Attempting to send via SMTP...")
        mail.send(msg)
        print(f"  SUCCESS: Email sent successfully to {email}")
        print(f"{'='*60}\n")
    except Exception as e:
        print(f"\n  ERROR DETAILS:")
        print(f"    Error Type: {type(e).__name__}")
        print(f"    Error Message: {str(e)}")
        import traceback
        print(f"    Full Traceback:")
        traceback.print_exc()
        print(f"{'='*60}\n")
        raise

def read_from_database():
    try:
        # Use absolute path for database to work with scheduled tasks
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'users.db')
        print(f"  Attempting to connect to database: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user')
        rows = cursor.fetchall()
        user_info = []
        for row in rows:
            user_info.append({
                'email': row[1],
                'text': row[2],
                'token': row[3],
                'include_charts': bool(row[4]) if len(row) > 4 else False,
                'include_sp500_chart': bool(row[5]) if len(row) > 5 else False,
                'include_nasdaq_chart': bool(row[6]) if len(row) > 6 else False,
                'include_bitcoin_chart': bool(row[7]) if len(row) > 7 else False,
                'include_top10_stocks': bool(row[8]) if len(row) > 8 else False,
                'include_stock_suite': bool(row[9]) if len(row) > 9 else False,
                'include_market_news': bool(row[10]) if len(row) > 10 else False
            })
        cursor.close()
        conn.close()
        return user_info
    except Exception as e:
        print("Error reading from database:", e)
        return []

def date():
    current_date = datetime.now().date()
    formatted_date = current_date.strftime('%Y-%m-%d')
    return str(formatted_date)

def fetch_news(keyword):
    try:
        today = date()
        params = {
            'access_key': app.config['MEDIASTACK_API_KEY'],
            'countries': 'us',
            'languages': 'en',
            'keywords': keyword,
            'date': today,
            'sort': 'published_desc',
            'limit': 3,
        }
        
        print(f"Fetching news for keyword: {keyword}")
        response = requests.get('http://api.mediastack.com/v1/news', params=params, timeout=10)
        articles = response.json()
        
        # Check for API errors
        if 'error' in articles:
            print(f"API Error: {articles['error']}")
            return []
        
        return articles.get('data', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching news for keyword '{keyword}': {e}")
        return []
    except Exception as e:
        print(f"Error fetching news for keyword '{keyword}': {e}")
        return []

if __name__ == '__main__':
    print("=" * 50)
    print("Starting AnyNews Daily Email Service")
    print("=" * 50)
    
    # Debug configuration
    print("\nSystem Configuration Check:")
    
    # Check if .env file exists
    import os
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    print(f"  .env file exists: {os.path.exists(env_path)}")
    if os.path.exists(env_path):
        print(f"  .env file path: {env_path}")
    
    print(f"  Python App Context: {'Active' if app.app_context else 'Inactive'}")
    print(f"  Database Path: instance/users.db")
    print(f"  MAIL_SERVER: {app.config.get('MAIL_SERVER', 'NOT CONFIGURED')}")
    print(f"  MAIL_PORT: {app.config.get('MAIL_PORT', 'NOT CONFIGURED')}")
    print(f"  MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS', 'NOT CONFIGURED')}")
    print(f"  MAIL_USERNAME: {app.config.get('MAIL_USERNAME', 'NOT CONFIGURED')}")
    print(f"  MAIL_PASSWORD: {'Configured (' + str(len(app.config.get('MAIL_PASSWORD', ''))) + ' chars)' if app.config.get('MAIL_PASSWORD') else 'NOT CONFIGURED'}")
    print(f"  MEDIASTACK_API_KEY: {'Configured' if app.config.get('MEDIASTACK_API_KEY') else 'NOT CONFIGURED'}")
    print(f"  ALPHAVANTAGE_API_KEY: {'Configured' if app.config.get('ALPHAVANTAGE_API_KEY') else 'NOT CONFIGURED'}")
    
    with app.app_context():
        user_info = read_from_database()
        print(f"\nFound {len(user_info) if user_info else 0} users in database")
        
        if user_info:
            for idx, user in enumerate(user_info, 1):
                email = user['email']
                keywords_text = user['text'].strip()
                include_charts = user.get('include_charts', False)
                include_sp500 = user.get('include_sp500_chart', False)
                include_nasdaq = user.get('include_nasdaq_chart', False)
                include_bitcoin = user.get('include_bitcoin_chart', False)
                include_top10 = user.get('include_top10_stocks', False)
                include_stock_suite = user.get('include_stock_suite', False)
                include_news_sentiment = user.get('include_market_news', False) if not include_stock_suite else True
                
                print(f"\n[{idx}/{len(user_info)}] Processing user: {email}")
                print(f"  Charts: SP500={include_sp500}, NASDAQ={include_nasdaq}, Bitcoin={include_bitcoin}")
                print(f"  Top 10 Stocks: {'Yes' if include_top10 else 'No'}")
                print(f"  Stock Suite: {'Yes' if include_stock_suite else 'No'}")
                print(f"  Market News: {'Yes' if include_news_sentiment else 'No'}")
                
                # Fetch keyword-based news articles
                articles_by_keyword = {}
                if keywords_text and not keywords_text.isspace():
                    keywords = [keyword.strip() for keyword in keywords_text.split(',') if keyword.strip()]
                    print(f"  Keywords: {', '.join(keywords)}")

                    for keyword in keywords:
                        articles = fetch_news(keyword)
                        print(f"  → Found {len(articles)} articles for '{keyword}'")
                        
                        articles_for_user = []
                        for article in articles:
                            try:
                                article_info = {
                                    'title': article.get('title', 'No title'),
                                    'description': article.get('description', 'No description'),
                                    'source': article.get('source', 'Unknown'),
                                    'link': article.get('url', '#')
                                }
                                articles_for_user.append(article_info)
                            except Exception as e:
                                print(f"  ERROR: Error processing article: {e}")
                        
                        if articles_for_user:
                            articles_by_keyword[keyword] = articles_for_user
                else:
                    print(f"  No keywords provided")
                
                # Check if user has ANY content to send (keywords OR stock features)
                has_stock_features = (include_sp500 or include_nasdaq or include_bitcoin or 
                                     include_top10 or include_news_sentiment)
                has_content = bool(articles_by_keyword) or has_stock_features
                
                if has_content:
                    total_articles = sum(len(arts) for arts in articles_by_keyword.values()) if articles_by_keyword else 0
                    print(f"  Preparing email with {total_articles} total articles...")
                    
                    # Generate charts only if user wants them
                    user_charts = {}
                    if include_sp500 or include_nasdaq or include_bitcoin:
                        user_prefs = {
                            'sp500': include_sp500,
                            'nasdaq': include_nasdaq,
                            'bitcoin': include_bitcoin
                        }
                        user_charts = generate_market_charts(user_prefs)
                    
                    # Get top 10 stocks if user wants them
                    user_top10 = fetch_top10_sp500_stocks() if include_top10 else None
                    
                    # Get crypto data (BTC & ETH)
                    user_crypto = fetch_crypto_data() if include_top10 else None
                    
                    # Get market news sentiment if user wants it
                    user_market_news = None
                    if include_news_sentiment:
                        # Track S&P 500, NASDAQ, and Bitcoin
                        user_market_news = fetch_market_news_sentiment(
                            tickers=['SPY', 'QQQ', 'BTC'],  # S&P 500, NASDAQ, and Bitcoin
                            limit=10
                        )
                    
                    print(f"  Attempting to send email to {email}...")
                    print(f"    Articles: {len(articles_by_keyword)} keyword(s)")
                    print(f"    Charts: {len(user_charts)} chart(s)")
                    print(f"    Top 10 stocks: {'Yes' if user_top10 else 'No'}")
                    print(f"    Crypto data: {'Yes' if user_crypto else 'No'}")
                    print(f"    Market news: {'Yes' if user_market_news else 'No'}")
                    
                    send_email(email, articles_by_keyword, user_charts, user_top10, None, user_market_news, user_crypto)
                else:
                    print(f"  WARNING: No content to send (no keywords and no stock features enabled)")
        else:
            print("\nWARNING: No users found in database")
    
    print("\n" + "=" * 50)
    print("Email service completed!")
    print("=" * 50)