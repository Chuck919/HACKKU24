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

def calculate_composite_sentiment(news_items, target_ticker=None):
    """
    Calculate composite sentiment score from news items
    
    Uses SIMPLE AVERAGE (not weighted) of sentiment scores because
    Alpha Vantage thresholds are designed for raw sentiment values.
    Relevance is used only for FILTERING (include articles with relevance > 0.1)
    
    Returns dict with:
        - composite_score: Simple average sentiment (-1 to 1)
        - composite_label: Bearish/Somewhat-Bearish/Neutral/Somewhat-Bullish/Bullish
        - article_count: Number of articles analyzed
        - avg_relevance: Average relevance of articles (for reference)
    """
    if not news_items:
        return {
            'composite_score': 0,
            'composite_label': 'Neutral',
            'article_count': 0,
            'avg_relevance': 0
        }
    
    sentiment_scores = []
    relevances = []
    
    for item in news_items:
        # Get overall sentiment for the article
        sentiment_score = item.get('overall_sentiment_score', 0)
        relevance = 0.5  # Default relevance
        
        # If filtering by ticker, use ticker-specific sentiment and relevance
        if target_ticker and 'ticker_sentiment' in item:
            ticker_found = False
            for ts in item['ticker_sentiment']:
                # Match ticker exactly (including CRYPTO: prefix for crypto)
                if ts.get('ticker', '') == target_ticker:
                    sentiment_score = float(ts.get('ticker_sentiment_score', sentiment_score))
                    relevance = float(ts.get('relevance_score', 0.5))
                    ticker_found = True
                    break
            
            if not ticker_found:
                continue  # Skip articles that don't mention the target ticker
        else:
            # Use overall article relevance (average of topic relevances)
            if 'topics' in item and item['topics']:
                relevance = sum(float(t.get('relevance_score', 0)) for t in item['topics']) / len(item['topics'])
        
        # Only include articles with meaningful relevance (> 0.1)
        if relevance > 0.1:
            sentiment_scores.append(sentiment_score)
            relevances.append(relevance)
    
    if not sentiment_scores:
        return {
            'composite_score': 0,
            'composite_label': 'Neutral',
            'article_count': 0,
            'avg_relevance': 0
        }
    
    # Calculate SIMPLE AVERAGE (not weighted)
    # This preserves the Alpha Vantage threshold scale
    composite_score = sum(sentiment_scores) / len(sentiment_scores)
    avg_relevance = sum(relevances) / len(relevances)
    
    # Determine label based on Alpha Vantage's scale
    if composite_score <= -0.35:
        label = 'Bearish'
    elif composite_score <= -0.15:
        label = 'Somewhat-Bearish'
    elif composite_score < 0.15:
        label = 'Neutral'
    elif composite_score < 0.35:
        label = 'Somewhat-Bullish'
    else:
        label = 'Bullish'
    
    return {
        'composite_score': round(composite_score, 4),
        'composite_label': label,
        'article_count': len(sentiment_scores),
        'avg_relevance': round(avg_relevance, 4)
    }


def fetch_market_news_sentiment(topics=None, tickers=None, limit=10):
    """
    Fetch market news with sentiment analysis from Alpha Vantage
    
    NOTE: Alpha Vantage NEWS_SENTIMENT supports:
    - ONE ticker at a time (use tickers=['AAPL', 'MSFT'] for individual stocks)
    - MULTIPLE topics at once (use topics=['financial_markets', 'technology'])
    - For crypto, use CRYPTO: prefix (e.g., 'CRYPTO:BTC')
    - Topics work better for broad market coverage than ETF tickers
    
    Args:
        topics: List of topic strings (e.g., ['financial_markets', 'technology'])
        tickers: List of ticker symbols (e.g., ['AAPL', 'MSFT', 'CRYPTO:BTC'])
        limit: Number of articles per ticker/topic
        
    Returns:
        Dict with sentiment analysis and composite scores
    """
    print(f"  Fetching market news & sentiment...")
    print(f"    Topics: {topics}")
    print(f"    Tickers: {tickers}")
    print(f"    Limit per query: {limit}")
    
    if not get_api_key():
        print("    WARNING: No Alpha Vantage API key configured")
        return None
    
    all_news_items = []
    seen_urls = set()  # Track URLs to avoid duplicates
    
    try:
        api_key = get_api_key()
        
        # Make separate API call for each ticker
        if tickers:
            for idx, ticker in enumerate(tickers, 1):
                print(f"\n    [{idx}/{len(tickers)}] Fetching news for {ticker}...")
                
                params = {
                    'function': 'NEWS_SENTIMENT',
                    'apikey': api_key,
                    'tickers': ticker,  # Single ticker only
                    'sort': 'LATEST',
                    'limit': str(limit)  # Alpha Vantage accepts limit as string
                }
                
                response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
                print(f"       Response status: {response.status_code}")
                
                data = response.json()
                print(f"       Response keys: {list(data.keys())}")
                
                # Check for rate limiting and switch API key
                if 'Note' in data or ('Information' in data and 'rate limit' in data.get('Information', '').lower()):
                    print(f"       RATE LIMIT: {data.get('Note') or data.get('Information')}")
                    print(f"       Switching to backup API key...")
                    api_key = switch_api_key()
                    params['apikey'] = api_key
                    time.sleep(2)
                    response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
                    data = response.json()
                    print(f"       Retry Response keys: {list(data.keys())}")
                    
                    # If still failing after switch, skip this ticker
                    if 'Note' in data or 'Information' in data:
                        print(f"       WARNING: Both API keys exhausted, skipping {ticker}")
                        continue
                
                # Check for errors
                if 'Error Message' in data:
                    print(f"       ERROR: {data['Error Message']}")
                    continue
                
                if 'feed' in data:
                    print(f"       Feed contains {len(data['feed'])} items")
                    for item in data['feed']:
                        # Skip duplicates
                        url = item.get('url', '')
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        
                        # Store the raw item WITH all fields for composite sentiment calculation
                        # But also add display-friendly fields for the email template
                        all_news_items.append({
                            # Raw API fields (needed for calculate_composite_sentiment)
                            'overall_sentiment_score': float(item.get('overall_sentiment_score', 0)),
                            'ticker_sentiment': item.get('ticker_sentiment', []),
                            'topics': item.get('topics', []),
                            
                            # Display fields (for email template)
                            'title': item.get('title', 'No title'),
                            'url': url,
                            'time_published': item.get('time_published', 'N/A'),
                            'source': item.get('source', 'Unknown'),
                            'summary': item.get('summary', 'No summary')[:200] + '...',
                            'overall_sentiment': item.get('overall_sentiment_label', 'Neutral'),
                            'sentiment_score': float(item.get('overall_sentiment_score', 0))
                        })
                else:
                    print(f"       WARNING: No feed data for {ticker}")
                
                # Brief pause between ticker requests
                if idx < len(tickers):
                    time.sleep(1)
        
        # Fetch by topics if provided (better for broad market coverage)
        if topics:
            # Make separate API call for each topic
            for topic_idx, topic in enumerate(topics, 1):
                print(f"\n    [{topic_idx}/{len(topics)}] Fetching news for topic: {topic}...")
                
                params = {
                    'function': 'NEWS_SENTIMENT',
                    'apikey': api_key,
                    'topics': topic,  # Single topic only
                    'sort': 'LATEST',
                    'limit': str(limit)
                }
                
                response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
                print(f"       Response status: {response.status_code}")
                
                data = response.json()
                print(f"       Response keys: {list(data.keys())}")
                
                # Check for rate limiting
                if 'Note' in data or ('Information' in data and 'rate limit' in data.get('Information', '').lower()):
                    print(f"       RATE LIMIT: {data.get('Note') or data.get('Information')}")
                    print(f"       Switching to backup API key...")
                    api_key = switch_api_key()
                    params['apikey'] = api_key
                    time.sleep(2)
                    response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
                    data = response.json()
                    print(f"       Retry Response keys: {list(data.keys())}")
                    
                    # If still failing after switch, skip this topic
                    if 'Note' in data or 'Information' in data:
                        print(f"       WARNING: Both API keys exhausted, skipping {topic}")
                        continue
                
                if 'feed' in data:
                    print(f"       Feed contains {len(data['feed'])} items")
                    for item in data['feed']:
                        url = item.get('url', '')
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        
                        # Store the raw item WITH all fields for composite sentiment calculation
                        all_news_items.append({
                            # Raw API fields (needed for calculate_composite_sentiment)
                            'overall_sentiment_score': float(item.get('overall_sentiment_score', 0)),
                            'ticker_sentiment': item.get('ticker_sentiment', []),
                            'topics': item.get('topics', []),
                            
                            # Display fields (for email template)
                            'title': item.get('title', 'No title'),
                            'url': url,
                            'time_published': item.get('time_published', 'N/A'),
                            'source': item.get('source', 'Unknown'),
                            'summary': item.get('summary', 'No summary')[:200] + '...',
                            'overall_sentiment': item.get('overall_sentiment_label', 'Neutral'),
                            'sentiment_score': float(item.get('overall_sentiment_score', 0))
                        })
                else:
                    print(f"       WARNING: No feed data for {topic}")
                
                # Brief pause between topic requests
                if topic_idx < len(topics):
                    time.sleep(1)
        
        # If no tickers or topics, get general market news
        if not tickers and not topics:
            print(f"    Fetching general market news...")
            params = {
                'function': 'NEWS_SENTIMENT',
                'apikey': api_key,
                'sort': 'LATEST',
                'limit': str(limit * 3)  # Get more since we're not filtering by ticker
            }
            
            response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
            data = response.json()
            
            # Check for rate limiting
            if 'Note' in data or 'Information' in data:
                print(f"    RATE LIMIT: {data.get('Note') or data.get('Information')}")
                api_key = switch_api_key()
                params['apikey'] = api_key
                time.sleep(2)
                response = requests.get('https://www.alphavantage.co/query', params=params, timeout=10)
                data = response.json()
            
            if 'feed' in data:
                for item in data['feed'][:limit]:
                    # Store the raw item WITH all fields for composite sentiment calculation
                    all_news_items.append({
                        # Raw API fields (needed for calculate_composite_sentiment)
                        'overall_sentiment_score': float(item.get('overall_sentiment_score', 0)),
                        'ticker_sentiment': item.get('ticker_sentiment', []),
                        'topics': item.get('topics', []),
                        
                        # Display fields (for email template)
                        'title': item.get('title', 'No title'),
                        'url': item.get('url', '#'),
                        'time_published': item.get('time_published', 'N/A'),
                        'source': item.get('source', 'Unknown'),
                        'summary': item.get('summary', 'No summary')[:200] + '...',
                        'overall_sentiment': item.get('overall_sentiment_label', 'Neutral'),
                        'sentiment_score': float(item.get('overall_sentiment_score', 0))
                    })
        
        if all_news_items:
            print(f"\n    SUCCESS: Retrieved {len(all_news_items)} unique news articles")
            
            # Calculate composite sentiment scores
            print(f"\n    Calculating composite sentiment...")
            
            # Overall market sentiment (all articles)
            market_sentiment = calculate_composite_sentiment(all_news_items)
            print(f"      Market Sentiment: {market_sentiment['composite_label']} ({market_sentiment['composite_score']:.3f})")
            print(f"      Based on {market_sentiment['article_count']} articles, avg relevance: {market_sentiment['avg_relevance']:.3f}")
            
            # Ticker-specific sentiments
            ticker_sentiments = {}
            if tickers:
                for ticker in tickers:
                    ticker_sentiment = calculate_composite_sentiment(all_news_items, target_ticker=ticker)
                    if ticker_sentiment['article_count'] > 0:
                        ticker_sentiments[ticker] = ticker_sentiment
                        print(f"      {ticker}: {ticker_sentiment['composite_label']} ({ticker_sentiment['composite_score']:.3f}) - {ticker_sentiment['article_count']} articles")
            
            return {
                'articles': all_news_items[:limit],  # Limit total results
                'market_sentiment': market_sentiment,
                'ticker_sentiments': ticker_sentiments
            }
        else:
            print(f"    WARNING: No news items retrieved")
            return None
        
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

def calculate_rsi(prices, period=21):
    """
    Calculate RSI from price data using Wilder's smoothing method
    Default period increased to 21 for longer-term view and fewer whipsaws
    Research shows 20-25 day RSI produces more reliable signals than shorter periods
    """
    if len(prices) < period + 1:
        return None
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    # Initial average gain/loss (simple average of first period)
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

def calculate_adx(highs, lows, closes, period=14):
    """
    Calculate Average Directional Index (ADX) to measure trend strength
    ADX > 25 indicates strong trend, < 20 indicates weak/sideways market
    Returns ADX value or None if insufficient data
    
    Properly implements all 6 steps:
    1-3: Calculate TR, +DM, -DM and smooth them
    4: Calculate +DI and -DI
    5: Calculate DX
    6: Smooth DX to get ADX (this is the proper ADX calculation)
    """
    if len(closes) < period * 2:  # Need extra data for ADX smoothing
        return None
    
    # Calculate True Range (TR)
    tr_list = []
    for i in range(1, len(closes)):
        high_low = highs[i] - lows[i]
        high_close = abs(highs[i] - closes[i-1])
        low_close = abs(lows[i] - closes[i-1])
        tr = max(high_low, high_close, low_close)
        tr_list.append(tr)
    
    tr_array = np.array(tr_list)
    
    # Calculate +DM and -DM (Directional Movement)
    plus_dm = []
    minus_dm = []
    for i in range(1, len(highs)):
        high_diff = highs[i] - highs[i-1]
        low_diff = lows[i-1] - lows[i]
        
        if high_diff > low_diff and high_diff > 0:
            plus_dm.append(high_diff)
        else:
            plus_dm.append(0)
        
        if low_diff > high_diff and low_diff > 0:
            minus_dm.append(low_diff)
        else:
            minus_dm.append(0)
    
    plus_dm = np.array(plus_dm)
    minus_dm = np.array(minus_dm)
    
    # Smooth TR, +DM, -DM using Wilder's smoothing
    atr = np.mean(tr_array[:period])
    smoothed_plus_dm = np.mean(plus_dm[:period])
    smoothed_minus_dm = np.mean(minus_dm[:period])
    
    # Track DX values for smoothing into ADX
    dx_values = []
    
    for i in range(period, len(tr_array)):
        # Smooth ATR, +DM, -DM
        atr = (atr * (period - 1) + tr_array[i]) / period
        smoothed_plus_dm = (smoothed_plus_dm * (period - 1) + plus_dm[i]) / period
        smoothed_minus_dm = (smoothed_minus_dm * (period - 1) + minus_dm[i]) / period
        
        # Calculate +DI and -DI
        if atr == 0:
            continue
        
        plus_di = (smoothed_plus_dm / atr) * 100
        minus_di = (smoothed_minus_dm / atr) * 100
        
        # Calculate DX
        if plus_di + minus_di == 0:
            continue
        
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        dx_values.append(dx)
    
    # Step 6: Smooth DX values to get ADX
    if len(dx_values) < period:
        return None
    
    # Initial ADX is the average of first 'period' DX values
    adx = np.mean(dx_values[:period])
    
    # Apply Wilder's smoothing to remaining DX values
    for i in range(period, len(dx_values)):
        adx = (adx * (period - 1) + dx_values[i]) / period
    
    return adx

def check_obv_trend(obv, lookback=5):
    """
    Check if OBV has a consistent trend over multiple days
    Returns: 'rising' if OBV trending up, 'falling' if down, 'flat' if mixed
    """
    if len(obv) < lookback + 1:
        return 'flat'
    
    recent_obv = obv[-lookback:]
    
    # Count rising vs falling days
    rising_days = 0
    falling_days = 0
    
    for i in range(1, len(recent_obv)):
        if recent_obv[i] > recent_obv[i-1]:
            rising_days += 1
        elif recent_obv[i] < recent_obv[i-1]:
            falling_days += 1
    
    # Need at least 60% of days in one direction for trend
    threshold = lookback * 0.6
    
    if rising_days >= threshold:
        return 'rising'
    elif falling_days >= threshold:
        return 'falling'
    else:
        return 'flat'

def calculate_trading_signal(symbol, api_key, is_crypto=False):
    """
    Calculate trading signal using enhanced SMA50/SMA200 + RSI(21) + OBV + ADX strategy
    
    ENHANCEMENTS (Research-Backed):
    - RSI period increased to 21 days (from 14) for fewer whipsaws and more reliable signals
    - SMA200 instead of SMA100 for better long-term trend identification
    - Proper ADX calculation with DX smoothing (6-step process, not just DX)
    - ADX(14) filter: <20 (no trend), >=20 (trend present), >=25 (strong trend)
    - Multi-day OBV trend: 5-day consistency check (rising/falling/flat)
    - RSI thresholds optimized: <45 for strong signals, <55 for normal signals
    - Signal ordering: STRONG signals evaluated first to prevent conflicts
    
    Args:
        symbol: Stock ticker or crypto symbol (BTC, ETH)
        api_key: Alpha Vantage API key
        is_crypto: Whether this is crypto (uses DIGITAL_CURRENCY_DAILY endpoint)
    
    Signal Logic (evaluated in order):
    STRONG BUY: Price>=SMA50>SMA200, ADX>=25, RSI<45, OBV rising
    STRONG SELL: Price<SMA200, SMA50<SMA200, ADX>=25, RSI<45, OBV falling
    BUY: Price>=SMA200, ADX>=20, RSI<55
    SELL: Price<SMA50<SMA200, ADX>=20, RSI>45
    HOLD: Price between SMAs OR ADX<20 OR RSI 55-70 OR OBV neutral
    
    Returns: dict with signal, sma50, sma200, sma_position, rsi, obv, adx, current_price, previous_close
    """
    try:
        print(f"\n      {'='*60}")
        print(f"      CALCULATING TRADING SIGNAL FOR {symbol}")
        print(f"      {'='*60}")
        
        # Fetch time series data based on asset type
        print(f"      Step 1: Fetching time series data...")
        
        if not api_key:
            print(f"      ERROR: API key required")
            return None
        
        # Use different API endpoint for crypto vs stocks
        if is_crypto:
            params = {
                'function': 'DIGITAL_CURRENCY_DAILY',
                'symbol': symbol,
                'market': 'USD',
                'apikey': api_key
            }
            time_series_key = 'Time Series (Digital Currency Daily)'
        else:
            params = {
                'function': 'TIME_SERIES_DAILY',
                'symbol': symbol,
                'outputsize': 'full',  # Returns full historical data for SMA200
                'apikey': api_key
            }
            time_series_key = 'Time Series (Daily)'
        
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
        if time_series_key not in data:
            print(f"      ERROR: No time series data returned")
            print(f"      Response keys: {list(data.keys())}")
            return None
        
        time_series = data[time_series_key]
        
        print(f"      SUCCESS: Received {len(time_series)} candles from API")
        
        # Sort dates oldest to newest and take the most recent 200 for SMA200
        all_dates = sorted(time_series.keys())  # Oldest to newest
        
        if len(all_dates) < 200:
            print(f"      WARNING: Not enough data (only {len(all_dates)} candles, need 200)")
            if len(all_dates) < 50:
                print(f"      ERROR: Insufficient data for SMA50/SMA200 calculation")
                return None
        
        # Take the most recent 200 dates (already in oldest->newest order)
        recent_dates = all_dates[-200:] if len(all_dates) >= 200 else all_dates
        
        # Extract arrays (already oldest->newest for calculations)
        closes = []
        volumes = []
        highs = []
        lows = []
        
        for date in recent_dates:
            closes.append(float(time_series[date]['4. close']))
            volumes.append(float(time_series[date]['5. volume']))
            highs.append(float(time_series[date]['2. high']))
            lows.append(float(time_series[date]['3. low']))
        
        closes = np.array(closes)
        volumes = np.array(volumes)
        highs = np.array(highs)
        lows = np.array(lows)
        
        print(f"      Step 2: Processing {len(closes)} candles (oldest to newest)")
        print(f"      Date range: {recent_dates[0]} to {recent_dates[-1]}")
        
        # Current price
        current_price = closes[-1]
        print(f"\n      CURRENT PRICE: ${current_price:.2f}")
        
        # Calculate indicators
        print(f"      Step 3: Calculating technical indicators...")
        sma50 = calculate_sma(closes, 50)
        sma200 = calculate_sma(closes, 200)
        rsi = calculate_rsi(closes, 21)  # Increased to 21-day for fewer whipsaws
        obv = calculate_obv(closes, volumes)
        obv_sma20 = calculate_sma(obv, 20)
        adx = calculate_adx(highs, lows, closes, 14)  # ADX for trend strength
        obv_trend = check_obv_trend(obv, lookback=5)  # Multi-day OBV trend
        
        if sma50 is None or sma200 is None or rsi is None or obv_sma20 is None:
            print(f"      ERROR: Not enough data to calculate indicators")
            print(f"      SMA50: {sma50}, SMA200: {sma200}, RSI(21): {rsi}, OBV_SMA20: {obv_sma20}")
            return None
        
        # Calculate slopes (5-day lookback)
        # We need historical SMA values to calculate slope properly
        # For SMA200, we need 200 candles for current + 5 more for lookback = 205 total
        if len(closes) >= 205:
            # We have enough data for both SMAs
            # Calculate what SMA values were 5 days ago
            sma50_5days_ago = np.mean(closes[-55:-5])  # SMA50 from 5 days ago
            sma200_5days_ago = np.mean(closes[-205:-5])  # SMA200 from 5 days ago
        elif len(closes) >= 55:
            # Can calculate SMA50 slope but not SMA200
            sma50_5days_ago = np.mean(closes[-55:-5])
            sma200_5days_ago = sma200  # Not enough data, slope will be 0
        else:
            # Not enough data for either slope
            sma50_5days_ago = sma50
            sma200_5days_ago = sma200
        
        slope_50 = sma50 - sma50_5days_ago
        slope_200 = sma200 - sma200_5days_ago
        
        # Current OBV
        obv_current = obv[-1]
        
        # Enhanced status indicators
        rsi_status = 'Oversold' if rsi < 30 else 'Overbought' if rsi > 70 else 'Neutral'
        obv_status = f'{obv_trend.capitalize()} trend' if obv_trend != 'flat' else 'Flat/Mixed'
        
        # ADX status with granular thresholds
        if adx is None:
            adx_status = 'N/A'
        elif adx < 20:
            adx_status = 'No trend'
        elif 20 <= adx < 25:
            adx_status = 'Trend forming'
        else:  # adx >= 25
            adx_status = 'Strong trend'
        
        print(f"\n      TECHNICAL INDICATORS:")
        print(f"      ├─ SMA50:       ${sma50:>12,.2f}  (5-day slope: {slope_50:>+8.2f})")
        print(f"      ├─ SMA200:      ${sma200:>12,.2f}  (5-day slope: {slope_200:>+8.2f})")
        print(f"      ├─ RSI(21):     {rsi:>12.2f}  [{rsi_status}]")
        print(f"      ├─ ADX(14):     {adx if adx else 'N/A':>12}  [{adx_status}]")
        print(f"      ├─ OBV:         {obv_current:>12,.0f}")
        print(f"      ├─ OBV_SMA20:   {obv_sma20:>12,.0f}  [Current: {obv_status}]")
        print(f"      └─ OBV Trend:   {obv_trend.upper()} (5-day consistency check)")
        
        price_vs_sma50 = '>' if current_price > sma50 else '<'
        price_vs_sma200 = '>' if current_price > sma200 else '<'
        sma50_vs_sma200 = '>' if sma50 > sma200 else '<'
        
        # Determine price position relative to SMAs (top/middle/bottom)
        sma_positions = [
            ('Price', current_price),
            ('SMA50', sma50),
            ('SMA200', sma200)
        ]
        sma_positions_sorted = sorted(sma_positions, key=lambda x: x[1], reverse=True)
        position_order = f"{sma_positions_sorted[0][0]} (top) > {sma_positions_sorted[1][0]} (middle) > {sma_positions_sorted[2][0]} (bottom)"
        
        # Check if price is in "no man's land" (between SMAs)
        price_between_smas = (current_price > min(sma50, sma200) and 
                             current_price < max(sma50, sma200))
        
        print(f"\n      CONDITION CHECKS:")
        print(f"      ├─ Price vs SMAs:    Price({current_price:.2f}) {price_vs_sma50} SMA50({sma50:.2f}) {sma50_vs_sma200} SMA200({sma200:.2f})")
        print(f"      │                    Position: {position_order}")
        if price_between_smas:
            print(f"      │                    ⚠ Price in NO MAN'S LAND (between SMAs)")
        print(f"      ├─ SMA Slopes:       SMA50: {slope_50:+.2f}, SMA200: {slope_200:+.2f}")
        print(f"      ├─ OBV vs SMA20:     {obv_current - obv_sma20:+,.0f} ({obv_trend})")
        print(f"      ├─ ADX Level:        {f'{adx:.1f}' if adx else 'N/A'} ({adx_status})")
        print(f"      └─ RSI Level:        {rsi:.2f}")
        
        # Apply updated signal classification rules (ordered: STRONG signals first, then normal, then HOLD)
        print(f"\n      EVALUATING SIGNAL RULES:")
        
        # STRONG BUY: Price >= SMA50 > SMA200, ADX >= 25, RSI < 45, OBV rising
        if (current_price >= sma50 and sma50 > sma200 and 
            adx is not None and adx >= 25 and 
            rsi < 45 and obv_trend == 'rising'):
            signal = 'STRONG BUY'
            signal_color = 'green'
            print(f"      STRONG BUY:")
            print(f"         - Price >= SMA50 > SMA200: YES ({current_price:.2f} >= {sma50:.2f} > {sma200:.2f})")
            print(f"         - ADX >= 25 (strong trend): YES ({adx:.1f})")
            print(f"         - RSI < 45 (dip in uptrend): YES ({rsi:.1f})")
            print(f"         - OBV rising trend: YES")
            print(f"         -> Strong uptrend with pullback, BUY THE DIP")
            
        # STRONG SELL: Price < SMA200, SMA50 < SMA200, ADX >= 25, RSI < 45, OBV falling
        elif (current_price < sma200 and sma50 < sma200 and 
              adx is not None and adx >= 25 and 
              rsi < 45 and obv_trend == 'falling'):
            signal = 'STRONG SELL'
            signal_color = 'red'
            print(f"      STRONG SELL:")
            print(f"         - Price < SMA200: YES ({current_price:.2f} < {sma200:.2f})")
            print(f"         - SMA50 < SMA200 (bearish): YES ({sma50:.2f} < {sma200:.2f})")
            print(f"         - ADX >= 25 (strong bearish trend): YES ({adx:.1f})")
            print(f"         - RSI < 45 (momentum breakdown): YES ({rsi:.1f})")
            print(f"         - OBV falling trend: YES")
            print(f"         -> Long-term downtrend confirmed, EXIT COMPLETELY")
            
        # BUY: Price >= SMA200, ADX >= 20, RSI < 55
        elif (current_price >= sma200 and 
              adx is not None and adx >= 20 and 
              rsi < 55):
            signal = 'BUY'
            signal_color = 'darkgreen'
            print(f"      BUY:")
            print(f"         - Price >= SMA200: YES ({current_price:.2f} >= {sma200:.2f})")
            print(f"         - ADX >= 20 (trend present): YES ({adx:.1f})")
            print(f"         - RSI < 55 (not overbought): YES ({rsi:.1f})")
            print(f"         -> Bullish trend forming")
            
        # SELL: Price < SMA50 < SMA200, ADX >= 20, RSI > 45
        elif (current_price < sma50 and sma50 < sma200 and 
              adx is not None and adx >= 20 and 
              rsi > 45):
            signal = 'SELL'
            signal_color = 'darkred'
            print(f"      SELL:")
            print(f"         - Price < SMA50 < SMA200: YES ({current_price:.2f} < {sma50:.2f} < {sma200:.2f})")
            print(f"         - ADX >= 20 (downtrend present): YES ({adx:.1f})")
            print(f"         - RSI > 45 (momentum breaking down): YES ({rsi:.1f})")
            print(f"         -> Downtrend beginning, REDUCE EXPOSURE")
            
        # HOLD: Multiple conditions trigger hold
        else:
            signal = 'HOLD'
            signal_color = 'orange'
            print(f"      HOLD:")
            
            hold_reasons = []
            
            # Check all HOLD conditions
            if price_between_smas:
                hold_reasons.append(f"Price in no man's land (between SMAs: {min(sma50, sma200):.2f} - {max(sma50, sma200):.2f})")
            
            if adx is not None and adx < 20:
                hold_reasons.append(f"ADX < 20 (weak/no trend: {adx:.1f})")
            
            if 55 <= rsi <= 70:
                hold_reasons.append(f"RSI 55-70 (neutral/overbought zone: {rsi:.1f})")
            
            if obv_trend == 'flat':
                hold_reasons.append(f"OBV neutral/mixed (no clear direction)")
            
            # If no specific HOLD reason, it's just mixed signals
            if not hold_reasons:
                hold_reasons.append("Mixed signals - not a clear entry/exit point")
            
            for reason in hold_reasons:
                print(f"         - {reason}")
            
            print(f"         -> Wait for clearer signal")
        
        print(f"\n      FINAL SIGNAL: {signal}")
        print(f"      {'='*60}\n")
        
        # Get previous close (second to last in the array)
        previous_close = closes[-2] if len(closes) >= 2 else current_price
        
        return {
            'signal': signal,
            'signal_color': signal_color,
            'rsi': rsi,
            'adx': adx,
            'obv_trend': obv_trend,
            'sma50': sma50,
            'sma200': sma200,
            'sma_position': position_order,
            'obv': obv_current,
            'obv_sma20': obv_sma20,
            'current_price': current_price,
            'previous_close': previous_close
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
            
            # Fetch TIME_SERIES_DAILY (combines price quote + indicators in one call)
            print(f"    Fetching time series data (includes price + indicators)...")
            trading_signal = calculate_trading_signal(symbol, api_key)
            
            if trading_signal:
                # Extract price and change info from the signal response
                current_price = trading_signal.get('current_price', 0)
                previous_close = trading_signal.get('previous_close', 0)
                
                if current_price > 0 and previous_close > 0:
                    daily_change = current_price - previous_close
                    daily_change_pct = (daily_change / previous_close) * 100
                    
                    direction_text = 'UP' if daily_change >= 0 else 'DOWN'
                    print(f"    SUCCESS: Data retrieved:")
                    print(f"       Current Price:   ${current_price:>10.2f}")
                    print(f"       Previous Close:  ${previous_close:>10.2f}")
                    print(f"       Daily Change:    ${daily_change:>+10.2f} ({daily_change_pct:>+6.2f}%)")
                    print(f"       Direction:       {direction_text}")
                    print(f"       Signal:          {trading_signal['signal']}")
                    
                    stock_info = {
                        'symbol': symbol,
                        'price': current_price,
                        'change': daily_change,
                        'change_pct': daily_change_pct,
                        'direction': 'up' if daily_change >= 0 else 'down',
                        'signal': trading_signal['signal'],
                        'signal_color': trading_signal['signal_color'],
                        'rsi': trading_signal.get('rsi', 0),
                        'adx': trading_signal.get('adx'),
                        'obv_trend': trading_signal.get('obv_trend', 'flat'),
                        'sma50': trading_signal.get('sma50', 0),
                        'sma200': trading_signal.get('sma200', 0),
                        'sma_position': trading_signal.get('sma_position', 'N/A')
                    }
                    
                    stocks_data.append(stock_info)
                    print(f"\n    SUCCESS: {symbol} data collected")
                    print(f"       Final: ${current_price:.2f} ({daily_change_pct:+.2f}%) - {stock_info['signal']}")
                else:
                    print(f"    ERROR: Invalid price data from time series")
            else:
                print(f"    WARNING: Could not fetch time series data for {symbol}")
            
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
    Uses calculate_trading_signal() just like stocks
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
            print(f"\n    {'─'*60}")
            print(f"    [{idx}/{len(cryptos)}] Processing {crypto['name']} ({symbol})")
            print(f"    {'─'*60}")
            
            # Use the same calculate_trading_signal function as stocks
            print(f"    Fetching time series data (includes price + indicators)...")
            trading_signal = calculate_trading_signal(symbol, api_key, is_crypto=True)
            
            if trading_signal:
                # Extract price and change info from the signal response
                current_price = trading_signal.get('current_price', 0)
                previous_close = trading_signal.get('previous_close', 0)
                
                if current_price > 0 and previous_close > 0:
                    daily_change = current_price - previous_close
                    daily_change_pct = (daily_change / previous_close) * 100
                    
                    direction_text = 'UP' if daily_change >= 0 else 'DOWN'
                    print(f"    SUCCESS: Data retrieved:")
                    print(f"       Current Price:   ${current_price:>10.2f}")
                    print(f"       Previous Close:  ${previous_close:>10.2f}")
                    print(f"       Daily Change:    ${daily_change:>+10.2f} ({daily_change_pct:>+6.2f}%)")
                    print(f"       Direction:       {direction_text}")
                    print(f"       Signal:          {trading_signal['signal']}")
                    
                    crypto_info = {
                        'symbol': symbol,
                        'name': crypto['name'],
                        'price': current_price,
                        'change': daily_change,
                        'change_pct': daily_change_pct,
                        'direction': 'up' if daily_change >= 0 else 'down',
                        'signal': trading_signal['signal'],
                        'signal_color': trading_signal['signal_color'],
                        'rsi': trading_signal.get('rsi'),
                        'adx': trading_signal.get('adx'),
                        'obv_trend': trading_signal.get('obv_trend', 'flat'),
                        'sma50': trading_signal.get('sma50', 0),
                        'sma200': trading_signal.get('sma200', 0),
                        'sma_position': trading_signal.get('sma_position', 'N/A')
                    }
                    
                    crypto_data.append(crypto_info)
                else:
                    print(f"    WARNING: {symbol}: Invalid price data returned")
            else:
                print(f"    WARNING: {symbol}: No trading signal calculated")
            
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
        adx = np.random.uniform(15, 35)
        obv_trend = np.random.choice(['rising', 'falling', 'flat'])
        sma50 = crypto['base_price'] * np.random.uniform(0.95, 1.05)
        sma200 = crypto['base_price'] * np.random.uniform(0.90, 1.10)
        
        # Determine position order
        positions = [
            ('Price', crypto['base_price']),
            ('SMA50', sma50),
            ('SMA200', sma200)
        ]
        positions_sorted = sorted(positions, key=lambda x: x[1], reverse=True)
        position_order = f"{positions_sorted[0][0]} (top) > {positions_sorted[1][0]} (middle) > {positions_sorted[2][0]} (bottom)"
        
        crypto_data.append({
            'symbol': crypto['symbol'],
            'name': crypto['name'],
            'price': crypto['base_price'],
            'change': daily_change,
            'change_pct': daily_change_pct,
            'direction': 'up' if daily_change >= 0 else 'down',
            'signal': signal,
            'signal_color': signal_colors[signal],
            'rsi': rsi,
            'adx': adx,
            'obv_trend': obv_trend,
            'sma50': sma50,
            'sma200': sma200,
            'sma_position': position_order
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
                        # Use topics for better broad market coverage
                        # Topics: financial_markets, technology
                        user_market_news = fetch_market_news_sentiment(
                            topics=['financial_markets', 'technology'],
                            tickers=['CRYPTO:BTC'],  # Add Bitcoin for crypto coverage
                            limit=50  # Get 50 articles for accurate composite sentiment
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